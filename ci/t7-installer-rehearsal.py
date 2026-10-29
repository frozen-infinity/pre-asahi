#!/usr/bin/env python3
"""Trace pinned external-wipe installer logic using synthetic disks and scratch-only files."""
import builtins
import contextlib
import io
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
from types import SimpleNamespace
from unittest.mock import patch

source, raw_path, profile_path, scratch = [Path(p).resolve() for p in sys.argv[1:]]
sys.dont_write_bytecode = True
sys.path[:0] = [str(source / 'src'), str(source)]
import main
import diskutil

EXTERNAL = 'SYNTHETIC_EXTERNAL'
INTERNAL = 'SYNTHETIC_INTERNAL'
profile = json.loads(profile_path.read_text())
scratch.mkdir(exist_ok=False)
(scratch / 'boot').mkdir()
(scratch / 'boot/m1n1.bin').write_bytes(raw_path.read_bytes())
trace = []
original_open = builtins.open


def denied(*args, **kwargs):
    raise RuntimeError('Real subprocess/network services are forbidden')


def confined_open(path, mode='r', *args, **kwargs):
    if any(c in mode for c in 'wax+') and not Path(path).resolve().is_relative_to(scratch):
        raise RuntimeError('Write outside scratch directory')
    return original_open(path, mode, *args, **kwargs)


class SyntheticDisk(diskutil.DiskUtil):
    def __init__(self):
        self.disk_parts = {EXTERNAL: {'Size': 1000204886016}}

    def action(self, *args, **kwargs):
        position = {'partitionDisk': 1, 'eraseVolume': 3, 'apfs': 2}.get(args[0] if args else None)
        if position is None or len(args) <= position or args[position] not in [EXTERNAL, EXTERNAL + 's1']:
            raise RuntimeError('Internal or unrecognized disk target rejected')
        trace.append(['diskutil', *args])

    def get_list(self):
        return None

    def get_partitions(self, disk):
        if disk != EXTERNAL:
            raise RuntimeError('Unexpected disk target')
        return [SimpleNamespace(name=EXTERNAL + 's1'), SimpleNamespace(name='SYNTHETIC_FREE')]

    def get_partition_info(self, part, refresh_apfs=False):
        if part != EXTERNAL + 's1':
            raise RuntimeError('Unexpected partition target')
        return SimpleNamespace(name=part, label='pre-asahi T7 Stage1')


class SyntheticStub:
    def __init__(self, *args):
        self.boot_obj_path = str(scratch / 'boot.bin')

    def load_ipsw(self, ipsw):
        if ipsw.version != '26.5.1':
            raise ValueError('Wrong paired firmware')
        trace.append(['synthetic_recovery_preflight', ipsw.version])

    def prepare_volume(self, part):
        trace.append(['synthetic_prepare_stub_volume'])

    def check_volume(self):
        trace.append(['synthetic_check_stub_volume'])

    def install_files(self, owner):
        trace.append(['synthetic_install_stub_files'])


with patch.object(subprocess, 'run', denied), patch.object(subprocess, 'Popen', denied), \
     patch.object(socket, 'create_connection', denied), patch('builtins.open', confined_open), \
     patch.object(main.stub, 'StubInstaller', SyntheticStub), \
     patch.object(main, 'input_prompt', return_value=''), contextlib.redirect_stdout(io.StringIO()):
    os.chdir(scratch)
    controller = main.InstallerMain.__new__(main.InstallerMain)
    controller.data = profile
    controller.expert = True
    controller.cur_disk, controller.sys_disk = EXTERNAL, INTERNAL
    controller.dutil = SyntheticDisk()
    controller.osinfo = None
    controller.cur_os = None
    controller.sysinfo = SimpleNamespace(sys_firmware='mBoot-20457.40.150.0.1', macos_ver='27.2',
        sfr_full_ver='26.2.91.5.7,0', chip_id=0x8132, device_class='j713ap')
    controller.device = main.DEVICES['j713ap']
    controller.flush_input = lambda: None

    def choice(prompt, options, default=None):
        if not options:
            raise RuntimeError('External profile was filtered out')
        return default if default is not None else 0

    controller.choice = choice
    controller.yesno = lambda prompt, default=False: prompt == 'Wipe my disk'
    controller.step2 = lambda report=False: trace.append(['authorization_boundary_not_executed'])
    # Real choose_os, get_os_size_and_info, choose_ipsw, action_wipe,
    # DiskUtil.partitionDisk, do_install, OSInstaller and m1n1.build execute.
    controller.action_wipe()
    commands = [row for row in trace if row[0] == 'diskutil']
    expected = [
        ['diskutil', 'partitionDisk', EXTERNAL, '1', 'GPT', 'free', 'free', '0'],
        ['diskutil', 'eraseVolume', 'apfs', 'pre-asahi T7 Stage1', EXTERNAL + 's1'],
        ['diskutil', 'apfs', 'resizeContainer', EXTERNAL + 's1', str(main.STUB_SIZE)]]
    if commands != expected:
        raise ValueError('Unexpected external partition command sequence')
    if trace.index(['synthetic_recovery_preflight', '26.5.1']) >= trace.index(commands[0]):
        raise ValueError('Partitioning preceded the synthetic recovery boundary')
    raw = raw_path.read_bytes()
    if (scratch / 'boot.bin').read_bytes() != raw + bytes(4 + (-(len(raw) + 4)) % 65536):
        raise ValueError('Actual boot-object builder appended unexpected bytes')
    if controller.osins.part_info or controller.osins.efi_part:
        raise ValueError('Unexpected Linux/ESP partition requests')
    negative_controls = 0
    try:
        controller.dutil.action('partitionDisk', INTERNAL, '1', 'GPT', 'free', 'free', '0')
    except RuntimeError:
        negative_controls += 1
    else:
        raise ValueError('Synthetic internal write was not rejected')
    controller.data = {'os_list': [dict(profile['os_list'][0], external_boot=False)]}
    try:
        controller.choose_os()
    except RuntimeError:
        negative_controls += 1
    else:
        raise ValueError('Non-external profile was not filtered out')

result = {'status': 'PINNED_EXTERNAL_INSTALLER_SYNTHETIC_DISK_TRACE_PASS',
          'trace': trace, 'negative_controls_rejected': negative_controls,
          'real_partition_dispatch_and_boot_builder_executed': True,
          'actual_recovery_preflight_executed': False, 'actual_stub_file_install_executed': False,
          'actual_authorization_executed': False, 'physical_disk_changed': False,
          'installation_enabled': False, 'external_native_boot_qualified': False,
          'note': 'External command selection only, with fake disk, stub and recovery services. '
                  'Not a formatting or startup-qualification result.'}
(scratch / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps(result, indent=2))

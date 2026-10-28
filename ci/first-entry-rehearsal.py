#!/usr/bin/env python3
"""Exercise real pinned installer methods against scratch files and denied disk services."""
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

source, installer, scratch = (Path(p).resolve() for p in sys.argv[1:])
sys.dont_write_bytecode = True
sys.path[:0] = [str(source / 'src'), str(source)]
import main
import osinstall

scratch.mkdir(exist_ok=False)
profile = json.loads((installer / 'installer_data.json').read_text())
template = profile['os_list'][0]
original_open = builtins.open


def no_services(*args, **kwargs):
    raise RuntimeError('Unexpected subprocess/network service in scratch-only rehearsal')


def confined_open(path, mode='r', *args, **kwargs):
    resolved = Path(path).resolve()
    if any(flag in mode for flag in 'wax+') and not resolved.is_relative_to(scratch):
        raise RuntimeError('Write outside rehearsal scratch')
    return original_open(path, mode, *args, **kwargs)


class DenyDisk:
    def __getattr__(self, name):
        raise RuntimeError('Unexpected diskutil service: ' + name)


with patch.object(subprocess, 'run', no_services), patch.object(subprocess, 'Popen', no_services), \
     patch.object(socket, 'create_connection', no_services), patch('builtins.open', confined_open), \
     contextlib.redirect_stdout(io.StringIO()):
    os.chdir(installer)
    obj = osinstall.OSInstaller(DenyDisk(), profile, template)
    if (obj.min_size, obj.min_recommended_size, obj.expandable, obj.needs_firmware) != (0, 0, False, False):
        raise ValueError('Empty-OS profile has unexpected partition/firmware requirements')
    obj.load_package()
    obj.partition_disk('SCRATCH-ONLY-NOT-A-DEVICE')
    if obj.part_info or obj.efi_part or obj.ucache or obj.idata_targets:
        raise ValueError('Unexpected partition, ESP, network package or installer-data target')
    boot = scratch / 'boot.bin'
    obj.install(SimpleNamespace(boot_obj_path=str(boot)))
    raw = (installer / 'boot/m1n1.bin').read_bytes()
    expected = raw + bytes(4 + (-(len(raw) + 4)) % 65536)
    if boot.read_bytes() != expected:
        raise ValueError('Actual installer did not produce the reviewed empty-variable layout')
    # Confirm a partition request reaches the denying service instead of silently passing.
    poisoned = dict(template, partitions=[{'name': 'EFI', 'type': 'EFI', 'size': '1GB'}])
    rejected = False
    try:
        osinstall.OSInstaller(DenyDisk(), profile, poisoned).partition_disk('SCRATCH')
    except RuntimeError as error:
        rejected = str(error).startswith('Unexpected diskutil service:')
    if not rejected:
        raise ValueError('Disk service negative control did not reject')
    # Actual firmware-selector logic, with synthetic host/SFR metadata only.
    selector = main.InstallerMain.__new__(main.InstallerMain)
    selector.sysinfo = SimpleNamespace(sys_firmware='mBoot-20457.40.150.0.1',
        macos_ver='27.2', sfr_full_ver='25.6.80.0.0,0', chip_id=0x8132, device_class='j713ap')
    selector.device = main.DEVICES['j713ap']
    selector.expert = True
    selector.choice = lambda prompt, options, default=None: default
    if selector.choose_ipsw(['26.5.1']).version != '26.5.1':
        raise ValueError('Actual selector did not retain the exact paired firmware')
    selector.expert = False
    try:
        selector.choose_ipsw(['26.5.1'])
    except SystemExit:
        pass
    else:
        raise ValueError('Non-expert firmware negative control did not reject')

result = {'status': 'REAL_INSTALLER_EMPTY_OS_SCRATCH_REHEARSAL_PASS',
          'actual_osinstaller_class_executed': True, 'actual_boot_object_builder_executed': True,
          'os_partition_bytes': 0, 'os_partitions_created': 0, 'esp_target_present': False,
          'empty_variable_boot_object_matches': True, 'partition_service_negative_control_rejected': True,
          'synthetic_host_selector_only': True, 'non_expert_negative_control_rejected': True,
          'boot_object_bytes': boot.stat().st_size, 'physical_disk_access_performed': False,
          'stub_install_files_executed': False, 'paired_recovery_step_executed': False,
          'native_entry_qualified': False, 'native_boot_proven': False}
(scratch / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps(result, indent=2))

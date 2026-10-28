#!/usr/bin/env python3
"""Build the selected U-Boot's QEMU target and test the real EFI DT Fixup callback."""
import argparse
import json
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tempfile
import time
import bringup
import efi_probe
from qemu_kernel import sha256

REQUIRED = ['CONFIG_EFI_LOADER=y', 'CONFIG_EFI_DT_FIXUP=y', 'CONFIG_CMD_BOOTEFI=y',
            'CONFIG_CMD_BOOTEFI_BINARY=y', 'CONFIG_BOOTDELAY=-1', 'CONFIG_ENV_IS_NOWHERE=y',
            'CONFIG_EFI_VARIABLE_NO_STORE=y']


def accepted(console, fixup=False, publication=False):
    required = ['U-Boot ', 'PRE_ASAHI_EFI_PROBE_STARTED',
                'PRE_ASAHI_DT_FIXUP_AVAILABLE', 'PRE_ASAHI_NO_LINUX_LAUNCH']
    if fixup:
        required += ['PRE_ASAHI_BUFFER_NEGOTIATED', 'PRE_ASAHI_INVALID_INPUT_REJECTED',
                     'PRE_ASAHI_FIXUP_APPLY_PASS']
    if publication:
        required += ['PRE_ASAHI_TABLE_PUBLISHED', 'PRE_ASAHI_TABLE_CONSUMER_PASS',
                     'PRE_ASAHI_TABLE_RESTORED', 'PRE_ASAHI_PUBLICATION_PASS']
    refused = ['PRE_ASAHI_FIXUP_FAILED', 'PRE_ASAHI_DT_FIXUP_ABSENT',
               'PRE_ASAHI_DT_FIXUP_LOOKUP_ERROR', 'PRE_ASAHI_DT_FIXUP_REVISION_UNSUPPORTED',
               'PRE_ASAHI_PUBLICATION_FAILED', 'PRE_ASAHI_PUBLICATION_RETAINED']
    return all(marker in console for marker in required) and not any(marker in console for marker in refused)



def check_config(text):
    lines = text.splitlines()
    if any(value not in lines for value in REQUIRED):
        raise ValueError('QEMU U-Boot required configuration did not resolve')
    if any(value in lines for value in ['CONFIG_ARCH_APPLE=y', 'CONFIG_ENV_IS_IN_FLASH=y',
                                        'CONFIG_EFI_VARIABLE_FILE_STORE=y', 'CONFIG_NET=y']):
        raise ValueError('Unexpected Apple/persistent/network profile in QEMU test')


def emulate(attempt, firmware, image, qemu, publication=False):
    logfile = attempt / ('publication-console.log' if publication else 'uboot-console.log')
    args = [qemu, '-machine', 'virt', '-accel', 'tcg', '-cpu', 'max', '-m', '1024',
            '-nodefaults', '-display', 'none', '-monitor', 'none', '-serial', 'stdio', '-nic', 'none',
            '-bios', str(firmware), '-device', 'loader,file=' + str(image) + ',addr=0x44000000,force-raw=on']
    sent = False
    status = 'UBOOT_EFI_PROBE_NOT_OBSERVED'
    started = time.monotonic()
    with logfile.open('wb') as output:
        process = subprocess.Popen(args, stdin=subprocess.PIPE, stdout=output, stderr=subprocess.STDOUT)
        try:
            while time.monotonic() - started < 90:
                if logfile.stat().st_size > 8 * 1024 * 1024:
                    status = 'UBOOT_LOG_LIMIT'
                    break
                console = logfile.read_text(errors='replace')
                if accepted(console, fixup=not publication, publication=publication):
                    status = 'EMULATED_UBOOT_EFI_PUBLICATION_PASS' if publication else 'EMULATED_UBOOT_EFI_FIXUP_APPLY_PASS'
                    break
                if process.poll() is not None:
                    break
                if sent and console.count('=>') >= 2:
                    status = 'UBOOT_RETURNED_WITHOUT_ACCEPTED_PROBE'
                    break
                if not sent and '=>' in console:
                    # A command to the emulated console only; no disk or host terminal involved.
                    # QEMU's RAM preload does not register U-Boot image metadata: supply the byte count.
                    process.stdin.write(('bootefi 0x44000000:%x\n' % image.stat().st_size).encode())
                    process.stdin.flush()
                    sent = True
                time.sleep(0.1)
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
            process.stdin.close()
    return {'status': status, 'command_sent_to_emulated_console': sent,
            'console_sha256': sha256(logfile), 'elapsed_seconds': round(time.monotonic() - started, 2),
            'qemu_version': bringup.capture([qemu, '--version']).splitlines()[0]}


def run(args):
    if platform.system() != 'Linux':
        raise ValueError('Use the disposable Linux CI runner for the U-Boot cross-build')
    for tool in ['git', 'make', args.cross_compile + 'gcc', args.clang, args.linker, args.qemu]:
        if not shutil.which(tool):
            raise ValueError('Missing build tool: ' + tool)
    if bringup.capture([args.cross_compile + 'gcc', '-dumpmachine']) != 'aarch64-linux-gnu':
        raise ValueError('Expected the AArch64 Linux cross compiler')
    pins = json.loads((bringup.ROOT / 'configs/candidate-stack.json').read_text())
    parent = bringup.WORK / 'uboot-efi-probe'
    parent.mkdir(parents=True, exist_ok=True)
    attempt = Path(tempfile.mkdtemp(prefix='attempt-', dir=parent))
    source, build = attempt / 'source', attempt / 'build'
    bringup.run(['git', 'init', source])
    bringup.run(['git', '-C', source, 'remote', 'add', 'origin', 'https://github.com/aurora-silicon/u-boot.git'])
    bringup.run(['git', '-C', source, 'fetch', '--depth=1', 'origin', pins['uboot_commit']])
    bringup.run(['git', '-C', source, 'checkout', '--detach', pins['uboot_commit']])
    if bringup.capture(['git', '-C', source, 'rev-parse', 'HEAD']) != pins['uboot_commit']:
        raise ValueError('Wrong U-Boot source revision')
    make = ['make', '-C', source, 'O=' + str(build), 'CROSS_COMPILE=' + args.cross_compile]
    bringup.run(make + ['qemu_arm64_defconfig'])
    config = build / '.config'
    edit = [source / 'scripts/config', '--file', config]
    for name in ['EFI_LOADER', 'EFI_DT_FIXUP', 'CMD_BOOTEFI', 'CMD_BOOTEFI_BINARY',
                 'ENV_IS_NOWHERE', 'EFI_VARIABLE_NO_STORE']:
        edit.extend(['--enable', name])
    for name in ['ENV_IS_IN_FLASH', 'EFI_VARIABLE_FILE_STORE', 'EFI_VARIABLE_SF_STORE',
                 'GENERATE_ACPI_TABLE', 'NET']:
        edit.extend(['--disable', name])
    edit.extend(['--set-val', 'BOOTDELAY', '-1'])
    bringup.run(edit)
    bringup.run(make + ['olddefconfig'])
    check_config(config.read_text())
    shutil.copyfile(config, attempt / 'qemu-resolved.config')
    bringup.run(make + ['-j4'])
    firmware = build / 'u-boot.bin'
    if not firmware.is_file() or not firmware.stat().st_size:
        raise ValueError('U-Boot QEMU firmware missing')
    _, built_image, compiler = efi_probe.build(args.clang, args.linker, fixup=True)
    image = attempt / 'pre-asahi-probe.efi'
    shutil.copyfile(built_image, image)
    observation = emulate(attempt, firmware, image, args.qemu)
    publication_observation = {'status': 'NOT_RUN_APPLY_CHECK_FAILED'}
    publication_compiler = None
    if observation['status'] == 'EMULATED_UBOOT_EFI_FIXUP_APPLY_PASS':
        _, built_publication, publication_compiler = efi_probe.build(args.clang, args.linker, publication=True)
        publication_image = attempt / 'pre-asahi-publication.efi'
        shutil.copyfile(built_publication, publication_image)
        publication_observation = emulate(attempt, firmware, publication_image, args.qemu, publication=True)
    linux_report = None
    overall = publication_observation['status']
    if args.linux_kernel_zip and overall == 'EMULATED_UBOOT_EFI_PUBLICATION_PASS':
        import linux_efi
        passed, linux_report = linux_efi.run(attempt, firmware, args.linux_kernel_zip, args)
        overall = linux_report['status']
    report = {'status': overall, 'uboot_commit': pins['uboot_commit'],
              'target': 'qemu_arm64_defconfig + explicit test overlay',
              'uboot_sha256': sha256(firmware), 'config_sha256': sha256(config),
              'cross_compiler': bringup.capture([args.cross_compile + 'gcc', '--version']).splitlines()[0],
              'efi_probe': compiler, 'emulation': observation,
              'linux_efi': linux_report, 'publication_probe': publication_compiler, 'publication_emulation': publication_observation,
              'apple_build_executed': False, 'j713_board_hook_executed': False,
              'native_boot_proven': False, 'fixup_apply_passed': observation['status'] == 'EMULATED_UBOOT_EFI_FIXUP_APPLY_PASS',
              'configuration_table_publication_passed': publication_observation['status'] == 'EMULATED_UBOOT_EFI_PUBLICATION_PASS', 'linux_launched': (True if linux_report and any(
                  x['status'] in ['LINUX_EFI_PID1_PASS', 'CONTROL_REJECTED_AT_PID1']
                  for x in linux_report['observations'].values()) else None if args.linux_kernel_zip else False),
              'linux_efi_consumer_passed': overall == 'EMULATED_LINUX_EFI_CONSUMER_PASS',
              'note': 'Real selected-source U-Boot EFI services on QEMU generic ARM64; Apple hardware/configuration excluded.'}
    bringup.save(attempt / 'result.json', report)
    print(json.dumps(report, indent=2))
    print('U-Boot EFI test files: ' + str(attempt))
    expected = 'EMULATED_LINUX_EFI_CONSUMER_PASS' if args.linux_kernel_zip else 'EMULATED_UBOOT_EFI_PUBLICATION_PASS'
    if report['status'] != expected:
        for log in attempt.glob('*console.log'):
            print('\n'.join(log.read_text(errors='replace').splitlines()[-40:]))
        return 1
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--linux-kernel-zip', type=Path, help='Opt-in: exact saved kernel ZIP for QEMU EFI/PID1 test')
    parser.add_argument('--cross-compile', default='aarch64-linux-gnu-')
    parser.add_argument('--clang', default='clang')
    parser.add_argument('--linker', default='lld-link')
    parser.add_argument('--qemu', default='qemu-system-aarch64')
    args = parser.parse_args()
    try:
        return run(args)
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        print('STOP: ' + str(error), file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())

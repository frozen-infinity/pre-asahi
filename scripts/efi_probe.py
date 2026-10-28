#!/usr/bin/env python3
"""Build a standalone ARM64 EFI discovery app and optionally boot it in QEMU/EDK2."""
import argparse
import json
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile
import time
import bringup
from qemu_kernel import sha256


def validate_pe(data):
    if len(data) < 64 or data[:2] != b'MZ':
        raise ValueError('Expected PE/COFF image')
    offset = struct.unpack_from('<I', data, 60)[0]
    if offset + 96 > len(data) or data[offset:offset + 4] != b'PE\0\0':
        raise ValueError('Invalid PE header')
    if struct.unpack_from('<H', data, offset + 4)[0] != 0xaa64:
        raise ValueError('Expected AArch64 PE machine')
    optional = offset + 24
    if struct.unpack_from('<H', data, optional)[0] != 0x20b or struct.unpack_from('<H', data, optional + 68)[0] != 10:
        raise ValueError('Expected PE32+ EFI application subsystem')


def build(clang, linker, fixup=False):
    directory = bringup.WORK / 'efi-probe'
    directory.mkdir(parents=True, exist_ok=True)
    attempt = Path(tempfile.mkdtemp(prefix='attempt-', dir=directory))
    obj = attempt / 'probe.obj'
    image = attempt / 'pre-asahi-probe.efi'
    source = bringup.ROOT / ('efi/fixup.c' if fixup else 'efi/probe.c')
    fixture = bringup.ROOT / 'efi/synthetic-test.dts'
    if fixup:
        dtb = attempt / 'synthetic.dtb'
        bringup.run(['dtc', '-I', 'dts', '-O', 'dtb', '-o', dtb, fixture])
        data = dtb.read_bytes()
        if not 40 <= len(data) <= 4096:
            raise ValueError('Unexpected synthetic DTB size')
        (attempt / 'synthetic-fdt.h').write_text('static const U8 fixture[] = {' + ','.join(str(b) for b in data) + '};\n')
    bringup.run([clang, '--target=aarch64-pc-windows-msvc', '-ffreestanding', '-fno-builtin',
                 '-fno-stack-protector', '-O2', '-Wall', '-Wextra', '-Werror', '-I', attempt, '-c', source, '-o', obj])
    bringup.run([linker, '/subsystem:efi_application', '/entry:efi_main', '/nodefaultlib',
                 '/machine:arm64', '/timestamp:0', '/out:' + str(image), str(obj)])
    validate_pe(image.read_bytes())
    return attempt, image, {'source_sha256': sha256(source), 'efi_sha256': sha256(image),
                            'shared_source_sha256': sha256(bringup.ROOT / 'efi/probe.c'),
                            'fixture_sha256': sha256(fixture) if fixup else None,
                            'compiled_fixture_sha256': sha256(attempt / 'synthetic.dtb') if fixup else None,
                            'clang': bringup.capture([clang, '--version']).splitlines()[0],
                            'linker': bringup.capture([linker, '--version']).splitlines()[0]}


def emulate(attempt, image, qemu, code, variables):
    # The only FAT device and variable store are fresh files in this ignored workspace.
    esp = attempt / 'virtual-esp/EFI/BOOT'
    esp.mkdir(parents=True)
    shutil.copyfile(image, esp / 'BOOTAA64.EFI')
    varcopy = attempt / 'qemu-vars.fd'
    shutil.copyfile(variables, varcopy)
    logfile = attempt / 'efi-console.log'
    args = [qemu, '-machine', 'virt', '-accel', 'tcg', '-cpu', 'max', '-m', '1024',
            '-nodefaults', '-display', 'none', '-monitor', 'none', '-serial', 'stdio', '-nic', 'none',
            '-drive', 'if=pflash,format=raw,readonly=on,file=' + str(code),
            '-drive', 'if=pflash,format=raw,file=' + str(varcopy),
            '-drive', 'if=none,format=raw,readonly=on,file=fat:ro:' + str(attempt / 'virtual-esp') + ',id=esp',
            '-device', 'virtio-blk-device,drive=esp']
    started = time.monotonic()
    status = 'EFI_PROBE_NOT_OBSERVED'
    with logfile.open('wb') as output:
        process = subprocess.Popen(args, stdin=subprocess.DEVNULL, stdout=output, stderr=subprocess.STDOUT)
        try:
            while time.monotonic() - started < 90:
                if logfile.stat().st_size > 4 * 1024 * 1024:
                    status = 'EFI_LOG_LIMIT'
                    break
                console = logfile.read_text(errors='replace')
                if ('PRE_ASAHI_EFI_PROBE_STARTED' in console and 'PRE_ASAHI_DT_FIXUP_ABSENT' in console and
                        'PRE_ASAHI_NO_LINUX_LAUNCH' in console):
                    status = 'EMULATED_EFI_DISCOVERY_PASS_PROTOCOL_ABSENT'
                    break
                if 'PRE_ASAHI_DT_FIXUP_AVAILABLE' in console:
                    status = 'UNEXPECTED_PROTOCOL_PRESENT_REVIEW_REQUIRED'
                    break
                if process.poll() is not None:
                    break
                time.sleep(0.1)
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
    return {'status': status, 'qemu': bringup.capture([qemu, '--version']).splitlines()[0],
            'firmware_sha256': sha256(code), 'initial_variables_sha256': sha256(variables),
            'console_sha256': sha256(logfile), 'elapsed_seconds': round(time.monotonic() - started, 2),
            'note': 'Actual ARM64 EFI app on emulated EDK2. Missing U-Boot-specific protocol is expected.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--clang', default='clang')
    parser.add_argument('--linker', default='lld-link')
    parser.add_argument('--qemu', default='qemu-system-aarch64')
    parser.add_argument('--firmware-code', type=Path)
    parser.add_argument('--firmware-vars', type=Path)
    args = parser.parse_args()
    if bool(args.firmware_code) != bool(args.firmware_vars):
        parser.error('Provide both firmware files for emulation, or neither for build-only')
    try:
        attempt, image, report = build(args.clang, args.linker)
        report.update({'status': 'EFI_PROBE_BUILT_ONLY', 'native_boot_proven': False,
                       'linux_launched': False, 'fixup_called': False})
        if args.firmware_code:
            report['emulation'] = emulate(attempt, image, args.qemu, args.firmware_code.resolve(), args.firmware_vars.resolve())
            report['status'] = report['emulation']['status']
        bringup.save(attempt / 'result.json', report)
        print(json.dumps(report, indent=2))
        print('EFI probe files: ' + str(attempt))
        return int(args.firmware_code is not None and report['status'] != 'EMULATED_EFI_DISCOVERY_PASS_PROTOCOL_ABSENT')
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        print('STOP: ' + str(error), file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())

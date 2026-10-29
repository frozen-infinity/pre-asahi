#!/usr/bin/env python3
"""Prepare a RAM-only shell and prove an interactive command on diskless QEMU."""
import argparse
import gzip
import json
from pathlib import Path
import secrets
import shutil
import subprocess
import tempfile
import time
import bringup
import build_busybox
import linux_efi
import qemu_kernel

INIT = b'''#!/bin/busybox sh
export PATH=/bin
/bin/busybox mount -t proc proc /proc || exit 1
/bin/busybox mount -t sysfs sysfs /sys || exit 1
/bin/busybox mount -t devtmpfs devtmpfs /dev || exit 1
echo M4AIR_RAM_SHELL_READY
/bin/busybox uname -a
if [ -r /sys/firmware/devicetree/base/compatible ]; then
    /bin/busybox tr '\\000' '\\n' < /sys/firmware/devicetree/base/compatible
fi
echo 'RAM-only shell: no physical filesystem is mounted. Exit restarts the shell.'
while :; do
    /bin/busybox sh -i </dev/console >/dev/console 2>&1
done
'''


def prepare(binary, receipt_path, output):
    receipt = json.loads(receipt_path.read_text())
    data = binary.read_bytes()
    bringup.validate_busybox(data)
    if (receipt.get('status') != 'USERSPACE_SMOKE_ONLY_NO_KERNEL_BOOT' or
            receipt.get('archive_sha256') != build_busybox.SHA256 or
            receipt.get('version') != build_busybox.VERSION or
            receipt.get('binary_sha256') != qemu_kernel.sha256(binary) or
            not build_busybox.REQUIRED_APPLETS <= set(receipt.get('required_applets', []))):
        raise ValueError('BusyBox build receipt mismatch')
    archive = bringup.newc([(x, 0o40755, b'') for x in ['bin', 'dev', 'proc', 'sys', 'tmp']] +
        [('dev/console', 0o20600, b'', 5, 1), ('bin/busybox', 0o100755, data), ('init', 0o100755, INIT)])
    with output.open('xb') as stream:
        with gzip.GzipFile(filename='', mode='wb', fileobj=stream, mtime=0) as compressed:
            compressed.write(archive)


def has_command_evidence(log, cookie):
    lines = log.replace('\r', '').splitlines()
    return ('M4AIR_RAM_SHELL_READY' in lines and 'M4AIR_RAM_COMMAND=' + cookie in lines and
            any('Linux version ' in line for line in lines) and 'linux,dummy-virt' in log and
            'Kernel panic' not in log)


def smoke(kernel_zip):
    parent = bringup.WORK / 'ram-shell'
    parent.mkdir(parents=True, exist_ok=True)
    attempt = Path(tempfile.mkdtemp(prefix='attempt-', dir=parent))
    print('RAM shell test: ' + str(attempt), flush=True)
    image, kernel = linux_efi.extract_kernel(kernel_zip, attempt)
    output = attempt / 'ram-shell.cpio.gz'
    busybox = bringup.WORK / 'artifacts/busybox'
    receipt = bringup.WORK / 'artifacts/busybox-build.json'
    prepare(busybox, receipt, output)
    qemu = shutil.which('qemu-system-aarch64')
    if not qemu:
        raise ValueError('Missing qemu-system-aarch64')
    cookie = secrets.token_hex(16)
    # No literal expected output line appears in input, so terminal echo cannot pass.
    command = 'prefix=M4AIR_RAM_; suffix=COMMAND; echo "${prefix}${suffix}=' + cookie + '"\n'
    logfile = attempt / 'qemu-console.log'
    accepted = False
    with logfile.open('wb') as log:
        process = subprocess.Popen(qemu_kernel.command(qemu, image, output), stdin=subprocess.PIPE,
                                   stdout=log, stderr=subprocess.STDOUT)
        sent = False
        start = time.monotonic()
        try:
            while time.monotonic() - start < 120:
                text = logfile.read_text(errors='replace')
                if logfile.stat().st_size > 8 * 1024**2 or 'Kernel panic' in text:
                    break
                if not sent and 'M4AIR_RAM_SHELL_READY' in text:
                    time.sleep(1)
                    process.stdin.write(command.encode())
                    process.stdin.flush()
                    sent = True
                if has_command_evidence(text, cookie):
                    accepted = True
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
                    process.wait(timeout=5)
    result = {'status': 'QEMU_RAM_INTERACTIVE_SHELL_PASS' if accepted else 'QEMU_RAM_SHELL_FAILED',
              'kernel': kernel, 'initramfs_sha256': qemu_kernel.sha256(output),
              'busybox_sha256': qemu_kernel.sha256(busybox), 'guest_command_result': accepted,
              'native_boot_proven': False, 'physical_disk_attached': False,
              'native_keyboard_or_usb_qualified': False,
              'note': 'QEMU virt shell only. Native entry, runtime DT, firmware, '
                      'USB and keyboard modules remain separate requirements.'}
    (attempt / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))
    if not accepted:
        print(logfile.read_text(errors='replace')[-5000:])
        raise ValueError('Interactive QEMU command was not observed')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--kernel-zip', type=Path, required=True)
    args = parser.parse_args()
    try:
        smoke(args.kernel_zip.resolve())
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
        raise SystemExit('STOP: ' + str(error))

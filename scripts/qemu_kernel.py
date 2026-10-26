#!/usr/bin/env python3
"""Boot local artifacts on QEMU virt only. Never connects to a Mac or disk."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile
import time
import bringup

MARKER = 'M4AIR_PHASE1_PID1'

def validate_image(header):
    if len(header) < 64 or header[56:60] != b'ARM\x64':
        raise ValueError('Expected an uncompressed AArch64 Linux Image')
    flags = struct.unpack_from('<Q', header, 24)[0]
    if flags & 1 or (flags >> 1) & 3 != 2:
        raise ValueError('Expected a little-endian kernel declaring 16 KiB pages')

def has_pid1_evidence(log):
    lines = log.splitlines()
    return (any('Linux version ' in x for x in lines) and
            MARKER in lines and 'linux,dummy-virt' in log and
            'Kernel panic' not in log)

def command(qemu, image, initramfs):
    # QEMU synthesizes the virt DT. Never pass the Apple DTB or m1n1 here.
    return [qemu, '-machine', 'virt,gic-version=3', '-accel', 'tcg',
            '-cpu', 'max', '-smp', '1', '-m', '1024', '-nodefaults',
            '-display', 'none', '-monitor', 'none', '-serial', 'stdio',
            '-nic', 'none', '-no-reboot', '-kernel', str(image),
            '-initrd', str(initramfs), '-append',
            'console=ttyAMA0 rdinit=/init loglevel=7 panic=-1']

def sha256(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()

def run_test(timeout):
    qemu = shutil.which('qemu-system-aarch64')
    if not qemu:
        raise ValueError('Install qemu-system-aarch64 on the Arch build host')
    image = bringup.WORK / 'build/j713/arch/arm64/boot/Image'
    initramfs = bringup.WORK / 'artifacts/initramfs.cpio.gz'
    config = bringup.WORK / 'build/j713/.config'
    with image.open('rb') as stream:
        validate_image(stream.read(64))
    settings = config.read_text().splitlines()
    required = ['CONFIG_ARM64_16K_PAGES=y', 'CONFIG_BLK_DEV_INITRD=y',
                'CONFIG_SERIAL_AMBA_PL011=y', 'CONFIG_SERIAL_AMBA_PL011_CONSOLE=y']
    missing = [x for x in required if x not in settings]
    if missing:
        raise ValueError('Existing kernel config lacks QEMU prerequisites: ' + ', '.join(missing))
    inputs = [image, initramfs, config, bringup.LOCK]
    hashes = {str(p.relative_to(bringup.ROOT)): sha256(p) for p in inputs}
    version = bringup.capture([qemu, '--version'])
    bringup.REPORTS.mkdir(parents=True, exist_ok=True)
    attempt = Path(tempfile.mkdtemp(prefix='qemu-virt-', dir=bringup.REPORTS))
    logfile = attempt / 'console.log'
    args = command(qemu, image, initramfs)
    print('Emulated QEMU virt test only. Logs: ' + str(attempt), flush=True)
    started = time.monotonic()
    status = 'TIMEOUT_NO_PID1_PROOF'
    process = None
    first_evidence = None
    try:
        with logfile.open('wb') as output:
            process = subprocess.Popen(args, stdin=subprocess.DEVNULL,
                                       stdout=output, stderr=subprocess.STDOUT)
            while time.monotonic() - started < timeout:
                if logfile.stat().st_size > 8 * 1024 * 1024:
                    status = 'LOG_LIMIT_REACHED'
                    break
                log = logfile.read_text(errors='replace')
                if 'Kernel panic' in log:
                    status = 'GUEST_PANIC'
                    break
                if has_pid1_evidence(log):
                    if first_evidence is None:
                        first_evidence = time.monotonic()
                    if time.monotonic() - first_evidence >= 2:
                        status = 'EMULATED_PID1_PASS'
                        break
                if process.poll() is not None:
                    status = 'QEMU_EXITED_BEFORE_ACCEPTANCE'
                    break
                time.sleep(0.1)
    finally:
        if process is not None and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
    if process is None:
        raise ValueError('QEMU did not start')
    result = {'status': status, 'platform': 'QEMU virt / TCG',
              'native_boot_proven': False, 'm1n1_tested': False,
              'kernel_page_size': 16384, 'qemu_version': version, 'command': args,
              'input_sha256': hashes, 'console_sha256': sha256(logfile),
              'qemu_exit_code_after_cleanup': process.returncode,
              'elapsed_seconds': round(time.monotonic() - started, 2),
              'note': 'QEMU is terminated after 2 seconds of PID1 evidence. No Mac hardware, disk or boot entry is used.'}
    bringup.save(attempt / 'result.json', result)
    print(json.dumps(result, indent=2))
    if status != 'EMULATED_PID1_PASS':
        print('Last console lines:\n' + '\n'.join(logfile.read_text(errors='replace').splitlines()[-25:]))
        return 1
    return 0

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--timeout', type=int, default=180)
    args = parser.parse_args()
    if not 10 <= args.timeout <= 600:
        parser.error('--timeout must be between 10 and 600 seconds')
    try:
        return run_test(args.timeout)
    except (OSError, ValueError, subprocess.SubprocessError) as e:
        print('STOP: ' + str(e), file=sys.stderr)
        return 1

if __name__ == '__main__':
    sys.exit(main())

#!/usr/bin/env python3
"""Test an explicitly selected candidate Image on diskless QEMU virt only."""
import argparse
import gzip
import json
from pathlib import Path
import platform
import subprocess
import sys
import bringup
import qemu_kernel


def check_result(result):
    receipt = json.loads((result / 'component-result.json').read_text())
    pins = json.loads((bringup.ROOT / 'configs/candidate-stack.json').read_text())
    if (receipt.get('status') != 'FULL_KERNEL_BUILT_QEMU_PENDING' or
            receipt.get('component') != 'kernel' or
            receipt.get('source_commit') != pins['kernel_commit'] or
            receipt.get('full_kernel_built') is not True or
            receipt.get('native_boot_proven') is not False):
        raise ValueError('Expected a full kernel build receipt matching the selected source pin')
    provenance = json.loads((result / 'provenance.json').read_text())
    if (provenance.get('status') != 'BUILD_ONLY_PASSED' or provenance.get('component') != 'kernel' or
            provenance.get('kernel_commit') != pins['kernel_commit'] or
            provenance.get('packaging_commit') != pins['packaging_commit']):
        raise ValueError('Candidate build provenance does not match the pinned stack')
    for name in ['kernel/Image', 'kernel-config/resolved.config', 'kernel/dtbs/t8132-j713.dtb']:
        if qemu_kernel.sha256(result / name) != provenance.get('output_sha256', {}).get(name):
            raise ValueError('Candidate build output hash mismatch: ' + name)
    image = result / 'kernel/Image'
    with image.open('rb') as stream:
        qemu_kernel.validate_image(stream.read(64))
    return image


def smoke(result):
    if platform.system() != 'Linux' or platform.machine() not in ('aarch64', 'arm64'):
        raise ValueError('This CI probe must be compiled on the disposable native ARM Linux runner')
    image = check_result(result)
    output = result / 'qemu'
    output.mkdir(exist_ok=True)
    binary = output / 'init'
    bringup.run(['gcc', '-static', '-O2', '-Wall', '-Wextra', '-Werror',
                 '-Wl,-z,max-page-size=0x10000', '-o', binary, bringup.ROOT / 'ci/qemu-pid1.c'])
    data = binary.read_bytes()
    bringup.validate_busybox(data)  # Shared ELF64/AArch64/static checks, independent of applets.
    archive = bringup.newc([(x, 0o40755, b'') for x in ['dev', 'proc', 'sys']] +
                             [('dev/console', 0o20600, b'', 5, 1), ('init', 0o100755, data)])
    initramfs = output / 'probe.cpio.gz'
    with initramfs.open('wb') as stream:
        with gzip.GzipFile(filename='', mode='wb', fileobj=stream, mtime=0) as compressed:
            compressed.write(archive)
    return qemu_kernel.run_test(180, image=image, initramfs=initramfs,
                               config=result / 'kernel-config/resolved.config',
                               report_dir=output, source_record=bringup.ROOT / 'configs/candidate-stack.json')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--result', type=Path, required=True)
    args = parser.parse_args()
    try:
        return smoke(args.result.resolve())
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
        print('STOP: ' + str(error), file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())

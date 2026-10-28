#!/usr/bin/env python3
"""Exact saved kernel -> real EFI stub -> PID 1 on diskless QEMU virt only."""
import gzip
import json
from pathlib import Path
import secrets
import shutil
import subprocess
import tempfile
import time
import bringup
import check_artifact_set as artifacts
import efi_probe
from qemu_kernel import sha256, validate_image

KERNEL_ADDRESS = 0x48000000
APP_ADDRESS = 0x44000000
INITRD_ADDRESS = 0x50000000
FDT_ADDRESS = 0x51000000
MAX_IMAGE = 64 * 1024 * 1024


def extract_kernel(path, attempt):
    spec = json.loads((bringup.ROOT / 'configs/artifact-set.json').read_text())['kernel']
    pins = json.loads((bringup.ROOT / 'configs/candidate-stack.json').read_text())
    archive = artifacts.Archive(path, spec)  # Exact ZIP bytes/digest and safe member inventory first.
    try:
        receipt = archive.json('provenance.json')
        result = archive.json('component-result.json')
        if (receipt.get('kernel_commit') != pins['kernel_commit'] or
                receipt.get('packaging_commit') != pins['packaging_commit'] or
                receipt.get('status') != 'BUILD_ONLY_PASSED' or
                receipt.get('container_exit_status') != 0 or
                result.get('source_commit') != pins['kernel_commit'] or
                result.get('status') != 'FULL_KERNEL_BUILT_QEMU_PENDING'):
            raise ValueError('Saved kernel source/build receipt mismatch')
        image = attempt / 'Image'
        entry = archive.entries[archive.root + 'kernel/Image']
        if not 64 <= entry.file_size <= MAX_IMAGE:
            raise ValueError('Unexpected saved kernel length')
        with archive.zip.open(entry) as source, image.open('wb') as destination:
            shutil.copyfileobj(source, destination, 1024 * 1024)
        config = archive.small('kernel-config/resolved.config')
        (attempt / 'kernel.config').write_bytes(config)
        expected = receipt['output_sha256']
        if (sha256(image) != expected.get('kernel/Image') or
                sha256(attempt / 'kernel.config') != expected.get('kernel-config/resolved.config')):
            raise ValueError('Saved kernel output digest mismatch')
        lines = config.decode().splitlines()
        for setting in ['CONFIG_EFI=y', 'CONFIG_EFI_STUB=y', 'CONFIG_OF_KOBJ=y',
                        'CONFIG_SYSFS=y', 'CONFIG_BLK_DEV_INITRD=y', 'CONFIG_ARM64_16K_PAGES=y',
                        'CONFIG_SERIAL_AMBA_PL011=y', 'CONFIG_SERIAL_AMBA_PL011_CONSOLE=y']:
            if setting not in lines:
                raise ValueError('Saved kernel lacks ' + setting)
        with image.open('rb') as stream:
            validate_image(stream.read(64))
        efi_probe.validate_pe(image.read_bytes())
        return image, {'kernel_commit': pins['kernel_commit'], 'artifact': spec,
                       'image_sha256': sha256(image), 'config_sha256': sha256(attempt / 'kernel.config')}
    finally:
        archive.zip.close()


def build_app(attempt, image, tree, install, clang, linker):
    variant = 'positive' if install else 'control'
    header_dir = attempt / variant
    header_dir.mkdir()
    data = tree.read_bytes()
    if not 40 <= len(data) <= 1024 * 1024:
        raise ValueError('QEMU DTB outside test bounds')
    (header_dir / 'linux-test-input.h').write_text(
        '#define TEST_INSTALL %d\n#define TEST_KERNEL_ADDRESS 0x%xULL\n#define TEST_KERNEL_SIZE %d\n' %
        (install, KERNEL_ADDRESS, image.stat().st_size) +
        'static const U8 test_tree[] = {' + ','.join(str(b) for b in data) + '};\n')
    objects = []
    for name in ['linux-entry', 'table-consumer']:
        obj = header_dir / (name + '.obj')
        bringup.run([clang, '--target=aarch64-pc-windows-msvc', '-ffreestanding', '-fno-builtin',
                     '-fno-stack-protector', '-O2', '-Wall', '-Wextra', '-Werror', '-I', header_dir,
                     '-c', bringup.ROOT / ('efi/' + name + '.c'), '-o', obj])
        objects.append(obj)
    app = attempt / ('linux-' + variant + '.efi')
    bringup.run([linker, '/subsystem:efi_application', '/entry:efi_main', '/nodefaultlib',
                 '/machine:arm64', '/timestamp:0', '/out:' + str(app)] + objects)
    efi_probe.validate_pe(app.read_bytes())
    return app


def outcome(console, cookie, control=False):
    lines = console.splitlines()
    if any(x in console for x in ['Kernel panic', 'PRE_ASAHI_LINUX_EFI_RETURNED']):
        return False
    if not (any('Linux version ' in x for x in lines) and 'EFI stub:' in console and
            any('efi: EFI v' in x for x in lines) and 'PRE_ASAHI_LINUX_EFI_PID1_REACHED' in lines and
            'PRE_ASAHI_STARTING_LINUX_EFI' in lines):
        return False
    if control:
        return ('PRE_ASAHI_LINUX_CONTROL_TREE' in lines and
                'PRE_ASAHI_LINUX_EFI_PID1_REJECTED' in lines and
                'PRE_ASAHI_LINUX_EFI_PID1_PASS' not in lines and
                'PRE_ASAHI_LINUX_TREE_PUBLISHED' not in lines)
    return ('PRE_ASAHI_LINUX_TREE_PUBLISHED' in lines and
            'PRE_ASAHI_LINUX_EFI_COOKIE=' + cookie in lines and
            'PRE_ASAHI_LINUX_EFI_FW_BITS=64' in lines and
            'PRE_ASAHI_LINUX_EFI_PID1_PASS' in lines and
            'PRE_ASAHI_LINUX_EFI_PID1_REJECTED' not in lines)


def emulate(attempt, firmware, image, initrd, dtb, app, qemu, cookie, control):
    log = attempt / ('linux-control-console.log' if control else 'linux-positive-console.log')
    args = [qemu, '-machine', 'virt,gic-version=3', '-accel', 'tcg', '-cpu', 'max', '-smp', '1',
            '-m', '1024', '-nodefaults', '-display', 'none', '-monitor', 'none',
            '-serial', 'stdio', '-nic', 'none', '-no-reboot', '-bios', str(firmware)]
    for path, address in [(app, APP_ADDRESS), (image, KERNEL_ADDRESS), (initrd, INITRD_ADDRESS), (dtb, FDT_ADDRESS)]:
        args += ['-device', 'loader,file=%s,addr=0x%x,force-raw=on' % (path, address)]
    command = 'bootefi %x:%x %x:%x %x\n' % (APP_ADDRESS, app.stat().st_size,
                                                  INITRD_ADDRESS, initrd.stat().st_size, FDT_ADDRESS)
    start = time.monotonic()
    sent = False
    first = None
    status = 'LINUX_EFI_NOT_OBSERVED'
    with log.open('wb') as output:
        process = subprocess.Popen(args, stdin=subprocess.PIPE, stdout=output, stderr=subprocess.STDOUT)
        try:
            while time.monotonic() - start < 180:
                if log.stat().st_size > 8 * 1024 * 1024:
                    status = 'LOG_LIMIT'; break
                console = log.read_text(errors='replace')
                if outcome(console, cookie, control):
                    if first is None:
                        first = time.monotonic()
                    if time.monotonic() - first >= 2:
                        status = 'CONTROL_REJECTED_AT_PID1' if control else 'LINUX_EFI_PID1_PASS'; break
                if 'Kernel panic' in console or 'PRE_ASAHI_LINUX_EFI_RETURNED' in console:
                    status = 'GUEST_FAILED'; break
                if not control and 'PRE_ASAHI_LINUX_EFI_PID1_REJECTED' in console:
                    status = 'POSITIVE_GUEST_REJECTED'; break
                if process.poll() is not None:
                    status = 'QEMU_EXITED'; break
                if sent and console.count('=>') >= 2:
                    status = 'UBOOT_RETURNED'; break
                if not sent and '=>' in console:
                    process.stdin.write(command.encode()); process.stdin.flush(); sent = True
                time.sleep(0.1)
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill(); process.wait()
            process.stdin.close()
    result = {'status': status, 'console_sha256': sha256(log),
              'elapsed_seconds': round(time.monotonic() - start, 2), 'command': command.rstrip(),
              'qemu_command': args}
    if status not in ['CONTROL_REJECTED_AT_PID1', 'LINUX_EFI_PID1_PASS']:
        print('\n'.join(log.read_text(errors='replace').splitlines()[-60:]))
    return result


def run(parent, firmware, kernel_zip, args):
    attempt = parent / 'linux-efi'
    attempt.mkdir()
    for name in ['dtc', 'fdtput', args.cross_compile + 'gcc']:
        if not shutil.which(name):
            raise ValueError('Linux EFI test requires ' + name)
    image, inputs = extract_kernel(kernel_zip, attempt)
    cookie = 'efi-linux-' + secrets.token_hex(16)
    # QEMU supplies a complete virt tree. Never pass an Apple DTB to this machine.
    dtb = attempt / 'control.dtb'
    bringup.run([args.qemu, '-machine', 'virt,gic-version=3,dumpdtb=' + str(dtb),
                 '-accel', 'tcg', '-cpu', 'max', '-smp', '1', '-m', '1024', '-nodefaults',
                 '-display', 'none', '-monitor', 'none', '-serial', 'none', '-nic', 'none',
                 '-bios', str(firmware)])
    bringup.run(['fdtput', '-t', 's', dtb, '/', 'pre-asahi,test-cookie', 'unpublished-control-tree'])
    private = attempt / 'private.dtb'
    shutil.copyfile(dtb, private)
    bringup.run(['fdtput', '-t', 's', private, '/', 'pre-asahi,test-cookie', cookie])
    (attempt / 'linux-test-cookie.h').write_text('#define TEST_COOKIE ' + json.dumps(cookie) + '\n')
    binary = attempt / 'init'
    bringup.run([args.cross_compile + 'gcc', '-static', '-O2', '-Wall', '-Wextra', '-Werror',
                 '-Wl,-z,max-page-size=0x10000', '-I', attempt,
                 '-o', binary, bringup.ROOT / 'ci/qemu-efi-pid1.c'])
    bringup.validate_busybox(binary.read_bytes())
    payload = bringup.newc([(x, 0o40755, b'') for x in ['dev', 'proc', 'sys']] +
                          [('dev/console', 0o20600, b'', 5, 1), ('init', 0o100755, binary.read_bytes())])
    initrd = attempt / 'initramfs.cpio.gz'
    with initrd.open('wb') as stream:
        with gzip.GzipFile(filename='', mode='wb', fileobj=stream, mtime=0) as compressed:
            compressed.write(payload)
    observations = {}
    for control in [True, False]:
        app = build_app(attempt, image, private, not control, args.clang, args.linker)
        observations['control' if control else 'positive'] = emulate(
            attempt, firmware, image, initrd, dtb, app, args.qemu, cookie, control)
    passed = (observations['control']['status'] == 'CONTROL_REJECTED_AT_PID1' and
              observations['positive']['status'] == 'LINUX_EFI_PID1_PASS')
    sources = ['efi/linux-entry.c', 'efi/probe.c', 'efi/abi.h', 'efi/table-consumer.c',
               'efi/table-consumer.h', 'ci/qemu-efi-pid1.c', 'scripts/linux_efi.py']
    report = {'status': 'EMULATED_LINUX_EFI_CONSUMER_PASS' if passed else 'LINUX_EFI_CONSUMER_FAILED',
              'native_boot_proven': False, 'j713_board_hook_executed': False,
              'platform': 'QEMU virt / TCG, selected U-Boot, exact saved 16 KiB kernel',
              'kernel_inputs': inputs, 'cookie': cookie, 'observations': observations,
              'source_sha256': {p: sha256(bringup.ROOT / p) for p in sources},
              'generated_header_sha256': {str(p.relative_to(attempt)): sha256(p) for p in attempt.rglob('*.h')},
              'clang': bringup.capture([args.clang, '--version']).splitlines()[0],
              'linker': bringup.capture([args.linker, '--version']).splitlines()[0],
              'qemu': bringup.capture([args.qemu, '--version']).splitlines()[0],
              'cross_compiler': bringup.capture([args.cross_compile + 'gcc', '--version']).splitlines()[0],
              'input_sha256': {p.name: sha256(p) for p in [firmware, initrd, dtb, private, binary] + list(attempt.glob('*.efi'))},
              'note': 'Actual EFI LoadImage/StartImage and Linux EFI stub -> RAM-only PID1; no Apple hardware or disks.'}
    bringup.save(attempt / 'result.json', report)
    print(json.dumps(report, indent=2))
    return passed, report

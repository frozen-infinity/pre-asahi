#!/usr/bin/env python3
"""Read-only verification of the three exact CI ZIPs; never extracts or executes them."""
import argparse
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import re
import stat
import struct
import sys
import tarfile
import zipfile
import bringup
import qemu_kernel

MAX_TOTAL = 8 * 1024 ** 3
MAX_SMALL = 16 * 1024 ** 2
STATUSES = {'aura': 'AURA_PACKAGE_BUILT', 'kernel': 'FULL_KERNEL_BUILT_QEMU_PENDING',
            'uboot': 'UBOOT_PACKAGE_BUILT'}


def digest(stream):
    value = hashlib.sha256()
    for block in iter(lambda: stream.read(1024 * 1024), b''):
        value.update(block)
    return value.hexdigest()


def safe_name(name):
    if (not name or '\\' in name or '\0' in name or name.startswith('/') or
            any(p in ('', '.', '..') for p in name.rstrip('/').split('/'))):
        raise ValueError('Unsafe archive path')
    return str(PurePosixPath(name))


class Archive:
    def __init__(self, path, expected):
        self.path = path
        if path.stat().st_size != expected['bytes']:
            raise ValueError('ZIP size mismatch (incomplete or wrong download): ' + path.name)
        with path.open('rb') as stream:
            if digest(stream) != expected['sha256']:
                raise ValueError('ZIP digest differs from the selected GitHub artifact: ' + path.name)
        self.zip = zipfile.ZipFile(path)
        try:
            self.entries = {}
            total = 0
            for entry in self.zip.infolist():
                name = safe_name(entry.filename)
                if entry.orig_filename != entry.filename or name in self.entries:
                    raise ValueError('Duplicate or ambiguous ZIP member')
                if entry.flag_bits & 1 or stat.S_IFMT(entry.external_attr >> 16) not in (0, stat.S_IFREG, stat.S_IFDIR):
                    raise ValueError('Encrypted or special ZIP member')
                total += entry.file_size
                if total > MAX_TOTAL or len(self.entries) >= 10000:
                    raise ValueError('ZIP resource limit exceeded')
                self.entries[name] = entry
            roots = [n[:-len('provenance.json')] for n in self.entries if n.endswith('/result/provenance.json')]
            if len(roots) != 1:
                raise ValueError('Expected one component result root')
            self.root = roots[0]
        except Exception:
            self.zip.close()
            raise

    def small(self, relative):
        entry = self.entries[self.root + safe_name(relative)]
        if entry.file_size > MAX_SMALL:
            raise ValueError('Metadata/payload size limit exceeded')
        return self.zip.read(entry)

    def json(self, relative):
        return json.loads(self.small(relative))

    def hash(self, relative):
        with self.zip.open(self.entries[self.root + safe_name(relative)]) as stream:
            return digest(stream)

    def one(self, prefix, suffix):
        matches = [n[len(self.root):] for n in self.entries
                   if n.startswith(self.root + prefix) and n.endswith(suffix)]
        if len(matches) != 1:
            raise ValueError('Expected one member matching ' + prefix + '*' + suffix)
        return matches[0]


def verify_component(archive, component, pins):
    receipt = archive.json('provenance.json')
    result = archive.json('component-result.json')
    if (receipt['status'] != 'BUILD_ONLY_PASSED' or receipt['component'] != component or
            receipt['container_exit_status'] != 0 or receipt['native_boot_proven'] is not False or
            result['status'] != STATUSES[component] or result['component'] != component or
            result['native_boot_proven'] is not False or result['installation_qualified'] is not False):
        raise ValueError('Unsuccessful or inconsistent component receipt')
    for field in ['packaging_commit', 'kernel_commit', 'aura_commit', 'base_sha256']:
        if receipt[field] != pins[field]:
            raise ValueError('Mixed stack pins: ' + field)
    field = component + '_commit'
    if result['source_commit'] != pins[field]:
        raise ValueError('Component source differs from selected pin')
    if component == 'uboot' and receipt['uboot_commit'] != pins['uboot_commit']:
        raise ValueError('U-Boot receipt pin mismatch')
    hashes = receipt['output_sha256']
    if not hashes:
        raise ValueError('Missing output hashes')
    for name, expected in hashes.items():
        if not re.fullmatch('[0-9a-f]{64}', expected) or archive.hash(name) != expected:
            raise ValueError('Build output hash mismatch: ' + name)
    return {'source_commit': result['source_commit'], 'verified_build_outputs': len(hashes)}


def package_files(archive, wanted):
    package = archive.one('packages/', '.pkg.tar.xz')
    selected = {}
    total = 0
    with tarfile.open(fileobj=io.BytesIO(archive.small(package)), mode='r:xz') as tar:
        names = set()
        for member in tar:
            name = safe_name(member.name)
            if name in names:
                raise ValueError('Duplicate package path')
            names.add(name)
            total += member.size
            if total > 128 * 1024 ** 2 or len(names) > 10000:
                raise ValueError('Package resource limit exceeded')
            if name in wanted:
                if not member.isfile() or member.size > MAX_SMALL:
                    raise ValueError('Expected bounded regular package payload')
                selected[name] = tar.extractfile(member).read(MAX_SMALL + 1)
    if set(selected) != set(wanted):
        raise ValueError('Required package payload missing')
    return selected


def verify_kernel(archive):
    image = 'kernel/Image'
    with archive.zip.open(archive.entries[archive.root + image]) as stream:
        qemu_kernel.validate_image(stream.read(64))
    dtb = archive.small('kernel/dtbs/t8132-j713.dtb')
    if len(dtb) < 40 or dtb[:4] != b'\xd0\x0d\xfe\xed' or struct.unpack_from('>I', dtb, 4)[0] != len(dtb):
        raise ValueError('Invalid J713 DTB header')
    # Check root compatible through the local FDT utility in a separate build step;
    # this offline reader checks the exact trusted artifact bytes/header only.
    config = archive.small('kernel-config/resolved.config').decode().splitlines()
    if any(x not in config for x in ['CONFIG_ARM64_16K_PAGES=y', 'CONFIG_RUST=y']):
        raise ValueError('Expected downstream 16 KiB/Rust configuration')
    result_path = archive.one('qemu/qemu-virt-', '/result.json')
    emulation = archive.json(result_path)
    console_path = result_path[:-len('result.json')] + 'console.log'
    if (emulation['status'] != 'EMULATED_PID1_PASS' or emulation['native_boot_proven'] is not False or
            emulation['m1n1_tested'] is not False or emulation['kernel_page_size'] != 16384 or
            emulation['console_sha256'] != archive.hash(console_path) or
            not qemu_kernel.has_pid1_evidence(archive.small(console_path).decode(errors='replace'))):
        raise ValueError('Invalid emulation evidence')
    for name in [image, 'kernel-config/resolved.config', 'qemu/probe.cpio.gz']:
        recorded = [h for p, h in emulation['input_sha256'].items() if p.endswith('/' + name)]
        if recorded != [archive.hash(name)]:
            raise ValueError('Emulation is bound to different inputs: ' + name)
    return {'status': emulation['status'], 'Image_sha256': archive.hash(image),
            'j713_dtb_sha256': archive.hash('kernel/dtbs/t8132-j713.dtb')}


def verify(paths, spec, pins):
    archives = {}
    try:
        summary = {}
        for component in ['aura', 'kernel', 'uboot']:
            archive = archives[component] = Archive(paths[component], spec[component])
            summary[component] = verify_component(archive, component, pins)
            summary[component]['artifact_sha256'] = spec[component]['sha256']
            summary[component]['run'] = spec[component]['run']
        aura = package_files(archives['aura'], ['usr/share/aura/stage1/aura.macho',
            'usr/share/aura/stage1/aura-raw.bin', 'usr/lib/asahi-boot/m1n1.bin'])
        macho = aura['usr/share/aura/stage1/aura.macho']
        if len(macho) < 32 or struct.unpack_from('<II', macho) != (0xfeedfacf, 0x100000c):
            raise ValueError('Expected ARM64 Mach-O Stage 1')
        if any(not data for data in aura.values()):
            raise ValueError('Empty Aura payload')
        summary['aura']['payload_sha256'] = {n: hashlib.sha256(b).hexdigest() for n, b in aura.items()}
        summary['kernel'].update(verify_kernel(archives['kernel']))
        uboot = archives['uboot']
        bringup.validate_busybox(uboot.small('uboot/u-boot.elf'))
        if 'CONFIG_APPLE_J713_FDT=y' not in uboot.small('uboot/resolved.config').decode().splitlines():
            raise ValueError('Missing J713 U-Boot handoff configuration')
        raw = uboot.small('uboot/u-boot-nodtb.bin')
        packaged = package_files(uboot, ['usr/lib/asahi-boot/u-boot-nodtb.bin'])
        if not raw or raw != packaged['usr/lib/asahi-boot/u-boot-nodtb.bin']:
            raise ValueError('Packaged U-Boot payload mismatch')
        return {'status': 'PINNED_ARTIFACT_SET_VERIFIED_NOT_BOOTABLE', 'native_boot_proven': False,
                'handoff_tested': False, 'installation_qualified': False, 'components': summary,
                'note': 'Byte/pin/package/emulation consistency only; no assembled image or hardware execution.'}
    finally:
        for archive in archives.values():
            archive.zip.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ['aura', 'kernel', 'uboot']:
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    try:
        report = verify(vars(args), json.loads((bringup.ROOT / 'configs/artifact-set.json').read_text()),
                        json.loads((bringup.ROOT / 'configs/candidate-stack.json').read_text()))
        output = bringup.REPORTS / 'artifact-set.json'
        bringup.save(output, report)
        print(json.dumps(report, indent=2))
        print('Report: ' + str(output))
        return 0
    except (OSError, ValueError, KeyError, tarfile.TarError, zipfile.BadZipFile) as error:
        print('STOP: ' + str(error), file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())

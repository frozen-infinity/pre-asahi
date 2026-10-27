#!/usr/bin/env python3
"""Prepare a review-only J713 OS DTB and probe it with synthetic runtime data."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import bringup
import check_artifact_set as artifacts
import j713_fixtures


def prepare(kernel_archive):
    pins = json.loads((bringup.ROOT / 'configs/candidate-stack.json').read_text())
    selected = json.loads((bringup.ROOT / 'configs/artifact-set.json').read_text())
    lock = json.loads((bringup.ROOT / 'configs/j713-fixtures.lock.json').read_text())
    if lock['commit'] != pins['uboot_commit']:
        raise ValueError('Importer source pin differs from U-Boot')
    root = bringup.WORK / 'j713-fixtures/sources'
    j713_fixtures.verify_sources(root, lock)
    archive = artifacts.Archive(kernel_archive, selected['kernel'])
    try:
        artifacts.verify_component(archive, 'kernel', pins)
        artifacts.verify_kernel(archive)
        raw = archive.small('kernel/dtbs/t8132-j713.dtb')
    finally:
        archive.zip.close()
    bringup.WORK.mkdir(parents=True, exist_ok=True)
    attempt = Path(tempfile.mkdtemp(prefix='os-dtb-review-', dir=bringup.WORK))
    (attempt / 'original.dtb').write_bytes(raw)
    spec = importlib.util.spec_from_file_location('pinned_os_fixture', root / 'test/py/tests/test_apple_j713_fdt.py')
    suite = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(suite)
    # This function generates invented data; never call the private-capture test.
    source = suite.compile_tree(attempt, 'SYNTHETIC-runtime', suite.fixture_tree(True, peripherals=True))
    lib = root / 'scripts/dtc/libfdt'
    names = ['fdt', 'fdt_ro', 'fdt_rw', 'fdt_sw', 'fdt_wip', 'fdt_empty_tree', 'fdt_strerror', 'fdt_addresses']
    binary = attempt / 'host-probe'
    bringup.run(['cc', '-D_GNU_SOURCE', '-std=gnu11', '-Wall', '-Wextra', '-Werror',
                 '-Wno-sign-compare', '-Wno-missing-field-initializers',
                 '-DJ713_IMPORTER_SOURCE="' + str(root / 'arch/arm/mach-apple/j713_fdt.c') + '"',
                 '-I', lib, bringup.ROOT / 'ci/j713-os-tree.c',
                 *[lib / (name + '.c') for name in names], '-o', binary], timeout=60)
    prepared = attempt / 'j713-STATIC-REVIEW-ONLY.dtb'
    probe = bringup.run([binary, attempt / 'original.dtb', source, prepared, pins['kernel_commit']],
                        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=30)
    observations = json.loads(probe.stdout)
    report = {'status': 'STATIC_OS_DTB_PREPARED_RUNTIME_UNVERIFIED', 'kernel_commit': pins['kernel_commit'],
              'uboot_commit': pins['uboot_commit'], 'original_sha256': hashlib.sha256(raw).hexdigest(),
              'prepared_sha256': hashlib.sha256(prepared.read_bytes()).hexdigest(),
              'source_marker': pins['kernel_commit'], 'probe': observations,
              'native_boot_proven': False, 'private_captures_used': False, 'installable': False,
              'synthetic_import_success': observations['synthetic_import_return'] == 1,
              'note': 'Prepared static input only. Never saves a synthetic runtime import as a boot DTB.'}
    bringup.save(attempt / 'result.json', report)
    print(json.dumps(report, indent=2))
    print('Review-only files: ' + str(attempt))
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--kernel', type=Path, required=True)
    args = parser.parse_args()
    try:
        return prepare(args.kernel)
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
        print('STOP: ' + str(error), file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())

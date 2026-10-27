#!/usr/bin/env python3
"""Exercise production EFI DT fixup/board sequencing on a host with mocked services."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import bringup
import j713_fixtures
import prepare_os_dtb


def board_hook(source):
    marker = 'int ft_board_setup(void *blob, struct bd_info *bd)\n'
    if source.count(marker) != 1:
        raise ValueError('Pinned board hook boundary changed')
    # This function is the pinned file's final definition; preserve its entire suffix.
    preamble = (source.split('#include', 1)[0] if source.startswith('// SPDX-License-Identifier:')
                else '/* Generated suffix of the locked U-Boot board.c (GPL-2.0+). */\n')
    return preamble + marker + source.split(marker, 1)[1]


def run(kernel, fetch):
    lock = json.loads((bringup.ROOT / 'configs/efi-handoff.lock.json').read_text())
    pins = json.loads((bringup.ROOT / 'configs/candidate-stack.json').read_text())
    if lock['commit'] != pins['uboot_commit'] or lock['repository'] != 'aurora-silicon/u-boot':
        raise ValueError('EFI source pin differs from the selected U-Boot')
    root = bringup.WORK / 'j713-fixtures/sources'
    if fetch:
        j713_fixtures.fetch_sources(root, lock)
    j713_fixtures.verify_sources(root, lock)
    attempt = prepare_os_dtb.prepare(kernel)  # Re-verifies artifact/importer and exercises saved OS tree first.
    hook = attempt / 'board-hook.c'
    hook.write_text(board_hook((root / 'arch/arm/mach-apple/board.c').read_text()))
    includes = attempt / 'efi-stub-includes'
    includes.mkdir()
    for name in ['efi_dt_fixup.h', 'efi_loader.h', 'efi_rng.h', 'fdtdec.h', 'mapmem.h']:
        (includes / name).write_text('#include "efi-host-stubs.h"\n')
    ci = bringup.ROOT / 'ci'
    lib = root / 'scripts/dtc/libfdt'
    names = ['fdt', 'fdt_ro', 'fdt_rw', 'fdt_sw', 'fdt_wip', 'fdt_empty_tree', 'fdt_strerror', 'fdt_addresses']
    binary = attempt / 'efi-host-sequence'
    bringup.run(['cc', '-D_GNU_SOURCE', '-std=gnu11', '-Wall', '-Wextra', '-Werror',
                 '-Wno-sign-compare', '-Wno-missing-field-initializers', '-Wno-unused-parameter',
                 '-DJ713_IMPORTER_SOURCE="' + str(root / 'arch/arm/mach-apple/j713_fdt.c') + '"',
                 '-DEFI_FIXUP_SOURCE="' + str(root / 'lib/efi_loader/efi_dt_fixup.c') + '"',
                 '-DBOARD_HOOK_SOURCE="' + str(hook) + '"', '-I', includes, '-I', ci, '-I', lib,
                 ci / 'efi-handoff-host.c', *[lib / (name + '.c') for name in names], '-o', binary], timeout=60)
    tested = bringup.run([binary, attempt / 'j713-STATIC-REVIEW-ONLY.dtb', attempt / 'SYNTHETIC-runtime.dtb'],
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=30)
    (attempt / 'efi-host.log').write_text(tested.stdout)
    observations = json.loads(tested.stdout.splitlines()[-1])
    report = {'status': observations['status'], 'uboot_commit': lock['commit'],
              'locked_source_sha256': lock['files'], 'board_hook_sha256': hashlib.sha256(hook.read_bytes()).hexdigest(),
              'observations': observations, 'native_boot_proven': False, 'real_efi_executed': False,
              'real_hardware_helper_executed': False,
              'note': 'Production EFI fixup and board hook, synthetic runtime, mocked image-setup adapter/EFI services/helper.'}
    bringup.save(attempt / 'efi-result.json', report)
    print(json.dumps(report, indent=2))
    print('EFI host results: ' + str(attempt))
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--kernel', type=Path, required=True)
    parser.add_argument('--fetch', action='store_true', help='Fetch only missing locked EFI/board source files')
    args = parser.parse_args()
    try:
        return run(args.kernel, args.fetch)
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
        print('STOP: ' + str(error), file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())

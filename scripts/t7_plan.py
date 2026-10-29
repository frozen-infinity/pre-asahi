#!/usr/bin/env python3
"""Read-only T7 layout proposal. No device selector or formatting operation."""
import json
import platform
from pathlib import Path
import macos_boot_context as boot

ROOT = Path(__file__).resolve().parents[1]
STUB_BYTES = 2499805184


def profile_contract(profile):
    if (profile.get('purpose') != 'EXPERIMENTAL_EXTERNAL_STUB_REHEARSAL_ONLY' or
            profile.get('installation_enabled') is not False or len(profile.get('os_list', [])) != 1):
        raise ValueError('Expected an installation-disabled external rehearsal profile')
    template = profile['os_list'][0]
    if (template.get('external_boot') is not True or template.get('expert') is not True or
            template.get('supported_fw') != ['26.5.1'] or template.get('partitions') != [] or
            template.get('boot_object') != 'm1n1.bin' or
            any(k in template for k in ['package', 'next_object', 'extras', 'icon'])):
        raise ValueError('Expected an empty-OS, no-ESP external stub proposal')
    return template


def candidate(info, ordinal, partition_types):
    summary = boot.external_summary(info, ordinal)
    size = summary['bytes']
    if (summary.get('transport') != 'USB' or summary.get('t7_name_match') is not True or
            type(size) is not int or not 990_000_000_000 <= size <= 1_010_000_000_000 or
            info.get('Writable') is not True or info.get('VirtualOrPhysical') == 'Virtual'):
        raise ValueError('Not a writable external whole USB T7-name/1TB candidate')
    # Names/sizes are review hints, never sufficient identity for erasing a disk.
    types = sorted({t for t in partition_types if t in {
        'Apple_APFS', 'EFI', 'Microsoft Basic Data', 'Windows_NTFS', 'Linux Filesystem', 'Apple_HFS'}})
    return {'external_index': ordinal, 'capacity_bytes': size,
            'current_partition_type_categories': types,
            'proposed_partition_scheme': 'GPT', 'proposed_apfs_stub_bytes': STUB_BYTES,
            'proposed_linux_partitions': [], 'remainder': 'leave unallocated for now',
            'would_erase_existing_t7_contents': True, 'internal_resize_required_by_layout': False,
            'internal_boot_metadata_writes_still_expected': True,
            'identity_sufficient_for_erasure': False, 'installation_enabled': False,
            'external_native_boot_qualified': False, 'disk_or_boot_state_changed': False}


def report(run_query=boot.query):
    profile_contract(json.loads((ROOT / 'configs/t7-first-entry.json').read_text()))
    listed, status = run_query(['/usr/sbin/diskutil', 'list', '-plist', 'external', 'physical'], True)
    if status != 'ok' or not isinstance(listed, dict):
        raise ValueError('External disk inventory unavailable')
    rows = listed.get('AllDisksAndPartitions')
    if not isinstance(rows, list) or len(rows) > 8:
        raise ValueError('Unexpected external disk inventory')
    candidates = []
    skipped = 0
    seen = set()
    for ordinal, row in enumerate(rows, 1):
        identifier = boot.safe_text(row.get('DeviceIdentifier'), r'disk[0-9]+')
        if not identifier or identifier in seen:
            raise ValueError('Invalid or duplicate external disk identifier')
        seen.add(identifier)
        info, state = run_query(['/usr/sbin/diskutil', 'info', '-plist', identifier], True)
        if state != 'ok':
            raise ValueError('External disk description unavailable')
        try:
            candidates.append(candidate(info, ordinal, [p.get('Content') for p in row.get('Partitions', [])]))
        except ValueError:
            skipped += 1
    return {'status': 'READ_ONLY_T7_EXTERNAL_STUB_PROPOSAL', 'candidates': candidates,
            'other_external_device_count': skipped, 'installation_enabled': False,
            'native_boot_proven': False, 'disk_or_boot_state_changed': False,
            'note': 'No device identifiers or volume names retained. Reporting indexes are not disk targets. '
                    'The proposal is not permission or qualification to erase/enroll.'}


if __name__ == '__main__':
    try:
        if platform.system() != 'Darwin':
            raise ValueError('This read-only inventory requires macOS')
        print(json.dumps(report(), indent=2))
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise SystemExit('STOP: ' + str(error))

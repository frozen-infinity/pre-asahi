#!/usr/bin/env python3
"""Read-only internal-stub storage feasibility; never resize or enroll."""
import json
import platform
import plistlib
import subprocess

STUB_BYTES = 2_499_805_184  # align_down(2.5 decimal GB, 1 MiB), reviewed installer constant
RESERVE = 38_000_000_000


def storage_plan(capacity, free, preferred):
    if (any(type(value) is not int for value in [capacity, free, preferred]) or
            not 0 <= free <= capacity or not 0 < preferred <= capacity):
        raise ValueError('Missing or inconsistent APFS size limits')
    proposed = (capacity - STUB_BYTES) // (1024**2) * (1024**2)
    return {'status': 'READ_ONLY_INTERNAL_STUB_STORAGE_PLAN',
            'stub_bytes': STUB_BYTES, 'macos_reserve_bytes': RESERVE,
            'container_capacity_bytes': capacity, 'container_free_bytes': free,
            'minimum_preferred_bytes': preferred,
            'apfs_limit_allows_stub_shrink': proposed >= preferred,
            'normal_reserve_allows_stub_shrink': free - (capacity - proposed) >= RESERVE,
            'existing_unallocated_gap_qualified': False,
            'internal_resize_candidate_available': proposed >= preferred and free - (capacity - proposed) >= RESERVE,
            'external_stub_qualified': False, 'installation_enabled': False,
            'disk_or_boot_state_changed': False, 'native_boot_proven': False,
            'note': 'Resize limits query only, no resize. Existing unallocated gaps are not '
                    'qualified by this helper. Expert mode must not lower the normal macOS reserve.'}


def query(args):
    return plistlib.loads(subprocess.check_output(['/usr/sbin/diskutil'] + args, stderr=subprocess.PIPE))


def main():
    if platform.system() != 'Darwin':
        raise ValueError('This read-only storage probe requires macOS')
    root = query(['info', '-plist', '/'])
    if root.get('Internal') is not True:
        raise ValueError('Expected current root storage to be internal')
    data = query(['apfs', 'list', '-plist'])
    containers = [c for c in data['Containers'] if c['ContainerReference'] == root['APFSContainerReference']]
    if len(containers) != 1 or len(containers[0].get('PhysicalStores', [])) != 1:
        raise ValueError('Ambiguous internal APFS container')
    container = containers[0]
    limits = query(['apfs', 'resizeContainer', container['ContainerReference'], 'limits', '-plist'])
    print(json.dumps(storage_plan(container['CapacityCeiling'], container['CapacityFree'],
                                  limits['MinimumSizePreferred']), indent=2))


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, KeyError, subprocess.SubprocessError) as error:
        raise SystemExit('STOP: Read-only APFS feasibility query failed: ' + type(error).__name__)

import copy
import json
from pathlib import Path
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import t7_plan


def info():
    return {'Internal': False, 'WholeDisk': True, 'Writable': True,
            'TotalSize': 1000204886016, 'BusProtocol': 'USB', 'MediaName': 'Samsung T7',
            'VirtualOrPhysical': 'Physical', 'DeviceIdentifier': 'PRIVATE_DEVICE',
            'DiskUUID': 'PRIVATE_UUID', 'VolumeName': 'PRIVATE_VOLUME'}


class T7PlanTests(unittest.TestCase):
    def test_proposal_does_not_select_or_authorize_erasure(self):
        result = t7_plan.candidate(info(), 1, ['Apple_APFS', 'EFI', 'PRIVATE_TYPE'])
        for flag in ['identity_sufficient_for_erasure', 'installation_enabled',
                     'external_native_boot_qualified', 'disk_or_boot_state_changed']:
            self.assertIs(result[flag], False)
        self.assertEqual(result['proposed_linux_partitions'], [])
        self.assertEqual(result['proposed_apfs_stub_bytes'], 2499805184)
        self.assertNotIn('PRIVATE', json.dumps(result))

    def test_internal_partition_wrong_size_readonly_and_virtual_candidates_reject(self):
        for key, value in [('Internal', True), ('WholeDisk', False), ('Writable', False),
                           ('TotalSize', 500000000000), ('BusProtocol', 'Thunderbolt'),
                           ('VirtualOrPhysical', 'Virtual'), ('MediaName', 'Other drive')]:
            changed = dict(info(), **{key: value})
            with self.subTest(key=key), self.assertRaises(ValueError):
                t7_plan.candidate(changed, 1, [])

    def test_query_unavailability_is_not_an_empty_disk_inventory(self):
        with self.assertRaises(ValueError):
            t7_plan.report(lambda *args: (None, 'unavailable'))

    def test_rehearsal_profile_cannot_become_a_live_installer_or_linux_layout(self):
        profile = json.loads((t7_plan.ROOT / 'configs/t7-first-entry.json').read_text())
        t7_plan.profile_contract(profile)
        for field, value in [('partitions', [{'name': 'EFI'}]), ('next_object', 'Image'),
                             ('supported_fw', ['27.2']), ('external_boot', False)]:
            changed = copy.deepcopy(profile)
            changed['os_list'][0][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                t7_plan.profile_contract(changed)
        profile['installation_enabled'] = True
        with self.assertRaises(ValueError):
            t7_plan.profile_contract(profile)


if __name__ == '__main__':
    unittest.main()

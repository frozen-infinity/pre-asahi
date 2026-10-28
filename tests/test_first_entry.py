import copy
import json
from pathlib import Path
import plistlib
import sys
import tempfile
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import first_entry_kit
import ram_shell
import recovery_payload
import first_entry_plan


class FirstEntryContracts(unittest.TestCase):
    def test_storage_limit_and_normal_reserve_are_independent(self):
        blocked = first_entry_plan.storage_plan(245107195904, 31242539008, 245107195904)
        self.assertFalse(blocked['apfs_limit_allows_stub_shrink'])
        self.assertFalse(blocked['normal_reserve_allows_stub_shrink'])
        for free, preferred in [(31_000_000_000, 150_000_000_000),
                                (80_000_000_000, 245107195904)]:
            result = first_entry_plan.storage_plan(245107195904, free, preferred)
            self.assertFalse(result['internal_resize_candidate_available'])
        result = first_entry_plan.storage_plan(245107195904, 80_000_000_000, 150_000_000_000)
        self.assertTrue(result['internal_resize_candidate_available'])
        self.assertFalse(result['installation_enabled'])

    def test_review_profile_cannot_enable_installation_or_append_os(self):
        profile = json.loads((first_entry_kit.bringup.ROOT / 'configs/first-entry.json').read_text())
        first_entry_kit.template_contract(profile)
        bad = copy.deepcopy(profile)
        bad['installation_enabled'] = True
        with self.assertRaises(ValueError):
            first_entry_kit.template_contract(bad)
        for field, value in [('external_boot', True), ('supported_fw', ['26.6.2']),
                             ('next_object', 'Image'), ('partitions', [{'name': 'EFI'}]),
                             ('package', 'anything.zip')]:
            bad = copy.deepcopy(profile)
            bad['os_list'][0][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                first_entry_kit.template_contract(bad)

    def test_command_echo_and_marker_alone_do_not_prove_a_shell_command(self):
        cookie = '0123456789abcdef'
        start = 'Linux version 7.3\nlinux,dummy-virt\nM4AIR_RAM_SHELL_READY\n'
        self.assertFalse(ram_shell.has_command_evidence(start, cookie))
        self.assertFalse(ram_shell.has_command_evidence(start + '# echo M4AIR_RAM_COMMAND=' + cookie, cookie))
        self.assertTrue(ram_shell.has_command_evidence(start + 'M4AIR_RAM_COMMAND=' + cookie + '\n', cookie))
        self.assertFalse(ram_shell.has_command_evidence(start + 'M4AIR_RAM_COMMAND=' + cookie + '\nKernel panic', cookie))

    def test_wrong_recovery_version_or_missing_enrollment_tools_fails(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            version = root / 'System/Library/CoreServices/SystemVersion.plist'
            version.parent.mkdir(parents=True)
            version.write_bytes(plistlib.dumps({'ProductVersion': '26.5.1', 'ProductBuildVersion': '25F80'}))
            with self.assertRaises(ValueError):
                recovery_payload.inspect_mount(root)
            tools = root / 'usr/bin'
            tools.mkdir(parents=True)
            for name in ['kmutil', 'bputil', 'bless', 'diskutil', 'sh']:
                (tools / name).write_bytes(b'synthetic; never executed')
            self.assertEqual(recovery_payload.inspect_mount(root)['build'], '25F80')
            version.write_bytes(plistlib.dumps({'ProductVersion': '26.6.2', 'ProductBuildVersion': '25G83'}))
            with self.assertRaises(ValueError):
                recovery_payload.inspect_mount(root)


if __name__ == '__main__':
    unittest.main()

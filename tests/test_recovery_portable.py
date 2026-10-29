import json
from pathlib import Path
import plistlib
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import inspect_recovery_portable as inspector


class PortableRecoveryTests(unittest.TestCase):
    def test_wrong_image_rejected_before_any_device_command(self):
        with tempfile.TemporaryDirectory() as folder:
            image = Path(folder) / 'BaseSystem.dmg'
            image.write_bytes(b'wrong')
            with patch.object(inspector.platform, 'system', return_value='Darwin'):
                with self.assertRaises(ValueError):
                    inspector.inspect(image, lambda *a: self.fail('Device command before image validation'))

    def scenario(self, timeout=False, eject_failure=False, preattached=False):
        image = Path('/synthetic/BaseSystem.dmg')
        state = {'attached': preattached, 'calls': []}
        def run(command, deadline):
            command = [str(a) for a in command]
            state['calls'].append(command)
            if command[:3] == ['/usr/bin/hdiutil', 'info', '-plist']:
                records = [{'image-path': str(image), 'system-entities': [
                    {'content-hint': 'GUID_partition_scheme', 'dev-entry': '/dev/disk987'}]}] if state['attached'] else []
                return plistlib.dumps({'images': records})
            if command[:2] == ['/usr/bin/hdiutil', 'attach']:
                self.assertIn('-readonly', command)
                state['attached'] = True
                return b''
            if '--read-mounted' in command:
                if timeout:
                    raise subprocess.TimeoutExpired(command, deadline)
                return json.dumps({'version': '26.5.1', 'build': '25F80', 'tools_present_not_executed': {}}).encode()
            if command[:2] == ['/usr/sbin/diskutil', 'eject']:
                self.assertEqual(command[2], '/dev/disk987')
                if eject_failure:
                    raise subprocess.CalledProcessError(1, command)
                state['attached'] = False
                return b''
            self.fail('Unexpected command: ' + repr(command))
        with patch.object(inspector, 'verify'), patch.object(inspector.platform, 'system', return_value='Darwin'):
            if preattached:
                with self.assertRaises(ValueError):
                    inspector.inspect(image, run)
                self.assertFalse(any(c[1] in ['attach', 'eject'] for c in state['calls']))
                return
            result = inspector.inspect(image, run)
        self.assertFalse(result['native_boot_proven'])
        self.assertFalse(result['boot_policy_changed'])
        return result, state

    def test_success_requires_cleanup_and_does_not_qualify_boot(self):
        result, state = self.scenario()
        self.assertEqual(result['status'], 'RECOVERY_CONTENT_INSPECTION_ONLY_PASS')
        self.assertTrue(result['cleanup_confirmed'])
        self.assertFalse(state['attached'])

    def test_read_timeout_still_ejects_only_the_image(self):
        result, state = self.scenario(timeout=True)
        self.assertEqual(result['status'], 'RECOVERY_CONTENT_INSPECTION_FAILED')
        self.assertEqual(result['error_stage'], 'read_contents')
        self.assertFalse(state['attached'])

    def test_eject_failure_cannot_produce_a_pass(self):
        result, state = self.scenario(eject_failure=True)
        self.assertEqual(result['status'], 'RECOVERY_INSPECTION_CLEANUP_UNCONFIRMED')
        self.assertTrue(state['attached'])

    def test_existing_attachment_is_never_reused_or_ejected(self):
        self.scenario(preattached=True)


if __name__ == '__main__':
    unittest.main()

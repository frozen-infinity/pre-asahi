import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('macos_firmware', Path(__file__).resolve().parents[1] / 'scripts/macos_firmware.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

class FirmwarePrivacyTests(unittest.TestCase):
    def test_report_excludes_identifiers_and_unknown_fields(self):
        data = {'SPHardwareDataType': [{'machine_model': 'Mac16,12',
                'boot_rom_version': 'example', 'serial_number': 'PRIVATE',
                'platform_UUID': 'PRIVATE', 'activation_lock_status': 'PRIVATE'}]}
        report = m.filtered_report(data)
        self.assertEqual(set(report['fields']), set(m.FIELDS))
        self.assertNotIn('PRIVATE', str(report))
        self.assertEqual(report['fields']['os_loader_version'], 'not reported')
        self.assertEqual(report['status'], 'IDENTIFICATION_ONLY_NO_BOOT_APPROVAL')

    def test_missing_hardware_record_fails(self):
        with self.assertRaises(ValueError):
            m.filtered_report({})

if __name__ == '__main__':
    unittest.main()

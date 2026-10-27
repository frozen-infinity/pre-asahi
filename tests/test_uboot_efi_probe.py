from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import uboot_efi_probe as probe


class UBootEFIResultTests(unittest.TestCase):
    def test_missing_or_refused_protocol_cannot_pass(self):
        valid = 'U-Boot 2026.07\nPRE_ASAHI_EFI_PROBE_STARTED\nPRE_ASAHI_DT_FIXUP_AVAILABLE\nPRE_ASAHI_NO_LINUX_LAUNCH\n'
        self.assertTrue(probe.accepted(valid))
        for invalid in [valid.replace('U-Boot ', ''), valid.replace('PRE_ASAHI_DT_FIXUP_AVAILABLE', 'PRE_ASAHI_DT_FIXUP_ABSENT'),
                        valid + 'PRE_ASAHI_DT_FIXUP_LOOKUP_ERROR\n', valid.replace('PRE_ASAHI_EFI_PROBE_STARTED', '')]:
            self.assertFalse(probe.accepted(invalid))

    def test_wrong_board_or_persistent_environment_fails_profile_check(self):
        valid = '\n'.join(probe.REQUIRED)
        probe.check_config(valid)
        for config in [valid.replace('CONFIG_EFI_DT_FIXUP=y', '# CONFIG_EFI_DT_FIXUP is not set'),
                       valid + '\nCONFIG_ARCH_APPLE=y', valid + '\nCONFIG_ENV_IS_IN_FLASH=y']:
            with self.assertRaises(ValueError):
                probe.check_config(config)


if __name__ == '__main__':
    unittest.main()

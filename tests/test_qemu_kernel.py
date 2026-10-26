import importlib.util
from pathlib import Path
import struct
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))

spec = importlib.util.spec_from_file_location('qemu_kernel', Path(__file__).resolve().parents[1] / 'scripts/qemu_kernel.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

class EmulatedEvidenceTests(unittest.TestCase):
    def header(self, flags):
        data = bytearray(64)
        data[56:60] = b'ARM\x64'
        struct.pack_into('<Q', data, 24, flags)
        return data

    def test_kernel_page_size_is_checked_in_image_header(self):
        m.validate_image(self.header(4))
        for data in [b'bad', self.header(2), self.header(6), self.header(5)]:
            with self.subTest(data=data):
                with self.assertRaises(ValueError):
                    m.validate_image(data)

    def test_marker_alone_or_commandline_echo_cannot_pass(self):
        valid = 'Linux version 7.1\nMachine model: linux,dummy-virt\nM4AIR_PHASE1_PID1\n'
        self.assertTrue(m.has_pid1_evidence(valid))
        self.assertFalse(m.has_pid1_evidence(m.MARKER))
        self.assertFalse(m.has_pid1_evidence(valid.replace('M4AIR_PHASE1_PID1\n', 'command line: M4AIR_PHASE1_PID1\n')))
        self.assertFalse(m.has_pid1_evidence(valid + 'Kernel panic - not syncing'))
        self.assertFalse(m.has_pid1_evidence(valid.replace('linux,dummy-virt', 'Apple M4')))

if __name__ == '__main__':
    unittest.main()

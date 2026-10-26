import importlib.util
from pathlib import Path
import struct
import unittest

spec = importlib.util.spec_from_file_location('bringup', Path(__file__).resolve().parents[1] / 'scripts/bringup.py')
b = importlib.util.module_from_spec(spec)
spec.loader.exec_module(b)

class PayloadTests(unittest.TestCase):
    def elf(self, machine=183, segment=1):
        data = bytearray(120)
        data[:6] = b'\x7fELF\x02\x01'
        struct.pack_into('<HH', data, 16, 2, machine)
        struct.pack_into('<Q', data, 32, 64)
        struct.pack_into('<HH', data, 54, 56, 1)
        struct.pack_into('<I', data, 64, segment)
        return data

    def test_elf_architecture_and_static_gate(self):
        b.validate_busybox(self.elf())
        for data in [b'bad', self.elf(machine=62), self.elf(segment=3), self.elf(segment=2)]:
            with self.assertRaises(ValueError):
                b.validate_busybox(data)

    def test_newc_layout_and_permissions(self):
        entries = [('dev/console', 0o20600, b'', 5, 1), ('bin', 0o40755, b''), ('init', 0o100755, b.INIT)]
        raw = b.newc(entries)
        self.assertEqual(raw, b.newc(entries))
        offset = 0
        decoded = []
        while True:
            self.assertEqual(raw[offset:offset+6], b'070701')
            fields = [int(raw[offset+6+i*8:offset+14+i*8], 16) for i in range(13)]
            offset += 110
            name = raw[offset:offset+fields[11]-1].decode()
            offset = (offset + fields[11] + 3) & ~3
            data = raw[offset:offset+fields[6]]
            offset = (offset + fields[6] + 3) & ~3
            if name == 'TRAILER!!!':
                break
            entry = (name, fields[1], data)
            if name == 'dev/console':
                entry += (fields[9], fields[10])
            decoded.append(entry)
        self.assertEqual(decoded, entries)
        self.assertEqual(len(raw) % 512, 0)
        self.assertIn(b'M4AIR_PHASE1_PID1', decoded[2][2])

if __name__ == '__main__':
    unittest.main()

from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import efi_probe


class EFIProbeTests(unittest.TestCase):
    def test_wrong_machine_or_subsystem_is_not_an_arm64_efi_app(self):
        data = bytearray(512)
        data[:2] = b'MZ'
        struct.pack_into('<I', data, 60, 128)
        data[128:132] = b'PE\0\0'
        struct.pack_into('<H', data, 132, 0xaa64)
        struct.pack_into('<H', data, 152, 0x20b)
        struct.pack_into('<H', data, 220, 10)
        efi_probe.validate_pe(data)
        struct.pack_into('<H', data, 132, 0x8664)
        with self.assertRaises(ValueError):
            efi_probe.validate_pe(data)
        struct.pack_into('<H', data, 132, 0xaa64)
        struct.pack_into('<H', data, 220, 3)
        with self.assertRaises(ValueError):
            efi_probe.validate_pe(data)

    @unittest.skipUnless(shutil.which('cc'), 'Host C compiler unavailable')
    def test_real_probe_entrypoint_handles_service_outcomes_without_calling_fixup(self):
        with tempfile.TemporaryDirectory() as name:
            binary = Path(name) / 'probe-host'
            source = Path(__file__).with_name('efi-probe-host.c')
            subprocess.run(['cc', '-std=c11', '-Wall', '-Wextra', '-Werror', str(source), '-o', str(binary)], check=True)
            result = subprocess.run([str(binary)], capture_output=True, text=True, check=True, timeout=10)
            self.assertEqual(result.stdout, 'EFI_PROBE_HOST_BRANCHES_PASS\n')

    @unittest.skipUnless(shutil.which('cc'), 'Host C compiler unavailable')
    def test_fixup_negotiation_failure_bounds_and_cleanup(self):
        with tempfile.TemporaryDirectory() as name:
            directory = Path(name)
            # Host mock does not parse FDT; actual ARM64 build uses dtc's full fixture.
            data = bytes.fromhex('d00dfeed00000028') + bytes(32)
            (directory / 'synthetic-fdt.h').write_text(
                'static const U8 fixture[] = {' + ','.join(str(b) for b in data) + '};\n')
            binary = directory / 'fixup-host'
            subprocess.run(['cc', '-std=c11', '-Wall', '-Wextra', '-Werror', '-I', name,
                            str(Path(__file__).with_name('efi-fixup-host.c')), '-o', str(binary)], check=True)
            subprocess.run([str(binary)], check=True, timeout=10)


if __name__ == '__main__':
    unittest.main()

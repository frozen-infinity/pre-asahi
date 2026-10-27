import hashlib
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import candidate_smoke as smoke


class CandidateSmokeInputs(unittest.TestCase):
    def fixture(self, result):
        pins = json.loads((smoke.bringup.ROOT / 'configs/candidate-stack.json').read_text())
        header = bytearray(64)
        header[56:60] = b'ARM\x64'
        struct.pack_into('<Q', header, 24, 4)
        files = {'kernel/Image': header, 'kernel-config/resolved.config': b'CONFIG_RUST=y\n',
                 'kernel/dtbs/t8132-j713.dtb': b'test DTB'}
        for name, content in files.items():
            path = result / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
        receipt = {'status': 'FULL_KERNEL_BUILT_QEMU_PENDING', 'component': 'kernel',
                   'source_commit': pins['kernel_commit'], 'full_kernel_built': True,
                   'native_boot_proven': False}
        provenance = {'status': 'BUILD_ONLY_PASSED', 'component': 'kernel',
                      'kernel_commit': pins['kernel_commit'], 'packaging_commit': pins['packaging_commit'],
                      'output_sha256': {name: hashlib.sha256(content).hexdigest()
                                        for name, content in files.items()}}
        (result / 'component-result.json').write_text(json.dumps(receipt))
        (result / 'provenance.json').write_text(json.dumps(provenance))
        return receipt

    def test_bound_inputs_pass_but_modified_image_fails(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            self.fixture(root)
            self.assertEqual(smoke.check_result(root), root / 'kernel/Image')
            (root / 'kernel/Image').write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError, 'output hash mismatch'):
                smoke.check_result(root)

    def test_configuration_only_or_different_source_is_rejected(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            for changes in [{'full_kernel_built': False}, {'component': 'kernel-config'},
                            {'source_commit': 'f' * 40}, {'native_boot_proven': True}]:
                receipt = self.fixture(root)
                receipt.update(changes)
                (root / 'component-result.json').write_text(json.dumps(receipt))
                with self.assertRaises(ValueError):
                    smoke.check_result(root)


if __name__ == '__main__':
    unittest.main()

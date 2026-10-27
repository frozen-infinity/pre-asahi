import hashlib
import json
from pathlib import Path
import stat
import sys
import tempfile
import unittest
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import check_artifact_set as review


class ArchiveChecks(unittest.TestCase):
    def archive(self, root, extra=None, receipt=None):
        path = root / 'input.zip'
        prefix = 'work/candidate-stack/aura-fixture/result/'
        with zipfile.ZipFile(path, 'w') as z:
            z.writestr(prefix + 'provenance.json', json.dumps(receipt or {}))
            if extra:
                z.writestr(*extra)
        return path, {'bytes': path.stat().st_size, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}

    def test_incomplete_or_modified_zip_never_reaches_member_reader(self):
        with tempfile.TemporaryDirectory() as name:
            path, pin = self.archive(Path(name))
            original = path.read_bytes()
            path.write_bytes(original[:-1])
            with self.assertRaisesRegex(ValueError, 'size mismatch'):
                review.Archive(path, pin)
            path.write_bytes(b'x' + original[1:])
            with self.assertRaisesRegex(ValueError, 'digest differs'):
                review.Archive(path, pin)

    def test_traversal_and_symlinks_are_rejected_even_with_matching_digest(self):
        link = zipfile.ZipInfo('link')
        link.create_system = 3
        link.external_attr = (stat.S_IFLNK | 0o777) << 16
        with tempfile.TemporaryDirectory() as name:
            for entry in [('../escape', b'x'), (link, b'/etc/passwd')]:
                path, pin = self.archive(Path(name), extra=entry)
                with self.assertRaises(ValueError):
                    review.Archive(path, pin)

    def test_component_source_mismatch_is_rejected(self):
        pins = {'packaging_commit': 'a', 'kernel_commit': 'b', 'aura_commit': 'c', 'base_sha256': 'd'}
        provenance = dict(pins, status='BUILD_ONLY_PASSED', component='aura',
                          container_exit_status=0, native_boot_proven=False)
        result = {'status': 'AURA_PACKAGE_BUILT', 'component': 'aura', 'native_boot_proven': False,
                  'installation_qualified': False, 'source_commit': 'different'}
        with tempfile.TemporaryDirectory() as name:
            path, pin = self.archive(Path(name), receipt=provenance,
                extra=('work/candidate-stack/aura-fixture/result/component-result.json', json.dumps(result)))
            archive = review.Archive(path, pin)
            try:
                with self.assertRaisesRegex(ValueError, 'source differs'):
                    review.verify_component(archive, 'aura', pins)
            finally:
                archive.zip.close()

    def test_unsafe_output_hash_path_cannot_escape_result_root(self):
        for name in ['/absolute', '../escape', 'a/../../escape', 'a\\b', 'a//b', 'a/./b']:
            with self.assertRaises(ValueError):
                review.safe_name(name)
        self.assertEqual(review.safe_name('kernel/Image'), 'kernel/Image')


if __name__ == '__main__':
    unittest.main()

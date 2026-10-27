import hashlib
import io
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import j713_fixtures as fixtures


class FixtureSourceBoundary(unittest.TestCase):
    def test_changed_cached_source_fails_closed(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            path = root / 'test.c'
            path.write_bytes(b'pinned')
            lock = {'files': {'test.c': hashlib.sha256(b'pinned').hexdigest()}}
            fixtures.verify_sources(root, lock)
            path.write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError, 'Changed source'):
                fixtures.verify_sources(root, lock)

    def test_download_mismatch_is_never_published(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            lock = {'commit': 'a' * 40, 'files': {'test.c': hashlib.sha256(b'pinned').hexdigest()}}
            with mock.patch.object(fixtures.urllib.request, 'urlopen', return_value=io.BytesIO(b'changed')):
                with self.assertRaisesRegex(ValueError, 'Download differs'):
                    fixtures.fetch_sources(root, lock)
            self.assertFalse((root / 'test.c').exists())

    def test_traversal_and_linked_sources_are_rejected(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            for relative in ['../escape.c', '/tmp/escape.c', 'a//b.c', 'a\\b.c']:
                with self.assertRaises(ValueError):
                    fixtures.source_path(root, relative)
            (root / 'real.c').write_bytes(b'pinned')
            (root / 'link.c').symlink_to(root / 'real.c')
            with self.assertRaisesRegex(ValueError, 'linked source'):
                fixtures.verify_sources(root, {'files': {'link.c': hashlib.sha256(b'pinned').hexdigest()}})


if __name__ == '__main__':
    unittest.main()

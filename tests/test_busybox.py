import io
import contextlib
import subprocess
from pathlib import Path
import sys
import tarfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import build_busybox as bb

class ArchiveTests(unittest.TestCase):
    def archive(self, name, kind=tarfile.REGTYPE):
        stream = io.BytesIO()
        with tarfile.open(fileobj=stream, mode='w') as out:
            member = tarfile.TarInfo(name)
            member.type = kind
            out.addfile(member)
        stream.seek(0)
        return tarfile.open(fileobj=stream)

    def test_rejects_traversal_absolute_and_links(self):
        for name, kind in [('busybox-1.38.0/../../escape', tarfile.REGTYPE),
                           ('/busybox-1.38.0/escape', tarfile.REGTYPE),
                           ('busybox-1.38.0/link', tarfile.SYMTYPE),
                           ('busybox-1.38.0/hardlink', tarfile.LNKTYPE),
                           ('unexpected/file', tarfile.REGTYPE)]:
            with self.subTest(name=name), self.archive(name, kind) as archive:
                with self.assertRaises(ValueError):
                    bb.checked_members(archive)

    def test_accepts_expected_regular_source_file(self):
        with self.archive('busybox-1.38.0/Makefile') as archive:
            self.assertEqual(len(bb.checked_members(archive)), 1)

class SmokeDiagnosticsTests(unittest.TestCase):
    def test_failed_guest_check_prints_its_error(self):
        errors = io.StringIO()
        args = [sys.executable, '-c',
                "import sys; print('busybox: applet not found', file=sys.stderr); sys.exit(127)"]
        with contextlib.redirect_stderr(errors):
            with self.assertRaises(subprocess.CalledProcessError) as caught:
                bb.smoke_capture(args)
        self.assertEqual(caught.exception.returncode, 127)
        self.assertIn('busybox: applet not found', errors.getvalue())

if __name__ == '__main__':
    unittest.main()

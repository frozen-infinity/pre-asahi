import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import dtb_candidate as review

ENTRY = 'arch/arm64/boot/dts/apple/t8132-j713.dts'

class IncludeAndReceiptTests(unittest.TestCase):
    def test_include_paths_are_confined(self):
        self.assertEqual(review.source_path(ENTRY, 't8132.dtsi', False),
                         'arch/arm64/boot/dts/apple/t8132.dtsi')
        self.assertEqual(review.source_path(ENTRY, 'dt-bindings/gpio/gpio.h', True),
                         'include/dt-bindings/gpio/gpio.h')
        for current, target in [(ENTRY, '/etc/passwd.h'),
                                (ENTRY, '../../../../../../etc/passwd.h'),
                                ('arch/arm64/boot/dts/apple/../../escape.dts', 'header.h')]:
            with self.subTest(target=target):
                with self.assertRaises(ValueError):
                    review.source_path(current, target, False)

    def test_comments_do_not_fetch_and_macro_includes_require_review(self):
        self.assertEqual(review.includes(ENTRY, '/* #include "not-real.h" */\n#include "t8132.dtsi"\n'),
                         ['arch/arm64/boot/dts/apple/t8132.dtsi'])
        with self.assertRaises(ValueError):
            review.includes(ENTRY, '#include COMPUTED_HEADER\n')

    def test_changed_cache_bytes_are_rejected(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            source = root / ENTRY
            source.parent.mkdir(parents=True)
            source.write_text('/dts-v1/;\n/ {};\n')
            profile = {'repository': 'example/kernel', 'commit': 'a' * 40, 'entry': ENTRY}
            receipt = dict(profile, files={ENTRY: review.digest(source.read_bytes())})
            (root / 'receipt.json').write_text(json.dumps(receipt))
            review.verify_cache(root, profile)
            source.write_text('/dts-v1/;\n/ { changed; };\n')
            with self.assertRaises(ValueError):
                review.verify_cache(root, profile)

    def test_download_graph_and_receipt_cover_all_dependencies(self):
        profile = {'repository': 'example/kernel', 'commit': 'a' * 40, 'entry': ENTRY}
        files = {ENTRY: b'#include "common.dtsi"\n#include <dt-bindings/gpio/gpio.h>\n',
                 'arch/arm64/boot/dts/apple/common.dtsi': b'/ {};\n',
                 'include/dt-bindings/gpio/gpio.h': b'#define GPIO_ACTIVE_HIGH 0\n'}
        prefix = 'https://raw.githubusercontent.com/example/kernel/' + 'a' * 40 + '/'
        def open_source(request, timeout):
            self.assertTrue(request.full_url.startswith(prefix))
            return io.BytesIO(files[request.full_url[len(prefix):]])
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            with mock.patch.object(review.urllib.request, 'urlopen', side_effect=open_source):
                receipt = review.fetch_graph(root, profile)
            self.assertEqual(set(receipt['files']), set(files))
            self.assertEqual(review.verify_cache(root, profile), receipt)

    def test_receipt_cannot_select_a_different_revision(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            profile = {'repository': 'example/kernel', 'commit': 'a' * 40, 'entry': ENTRY}
            (root / 'receipt.json').write_text(json.dumps(dict(profile, commit='b' * 40, files={})))
            with self.assertRaises(ValueError):
                review.verify_cache(root, profile)

if __name__ == '__main__':
    unittest.main()

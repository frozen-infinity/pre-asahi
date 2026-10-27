import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import candidate_build as candidate


class CandidateTrustTests(unittest.TestCase):
    def test_signature_requires_exact_expected_primary_or_subkey(self):
        key = 'A' * 40
        status = '[GNUPG:] VALIDSIG ' + key + ' 2026-01-01 1 0 4 0 1 10 00\n'
        self.assertTrue(candidate.expected_signature(status, key))
        self.assertTrue(candidate.expected_signature(status.replace(key, 'B' * 40).strip() + ' ' + key, key))
        for invalid in ('', '[GNUPG:] GOODSIG ' + key,
                        status.replace(key, 'B' * 40), status.replace(key, 'F' + key),
                        status + status.replace(key, 'B' * 40)):
            self.assertFalse(candidate.expected_signature(invalid, key))

    def test_base_size_and_hash_are_both_required(self):
        with tempfile.TemporaryDirectory() as name:
            archive = Path(name) / 'base'
            archive.write_bytes(b'pinned')
            base = {'bytes': 6, 'sha256': hashlib.sha256(b'pinned').hexdigest()}
            candidate.check_base_bytes(archive, base)
            archive.write_bytes(b'change')
            with self.assertRaises(ValueError):
                candidate.check_base_bytes(archive, base)
            archive.write_bytes(b'pinned-extra')
            with self.assertRaises(ValueError):
                candidate.check_base_bytes(archive, base)

    def test_packaging_manifest_recipe_and_base_must_agree(self):
        spec = {'kernel_commit': 'a' * 40, 'aura_commit': 'b' * 40, 'uboot_commit': 'e' * 40,
                'base_sha256': 'c' * 64, 'base_bytes': 123, 'base_signer': 'D' * 40}
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            (root / 'images').mkdir()
            (root / 'sources.json').write_text(json.dumps({
                'kernel-aurora': {'commit': spec['kernel_commit']},
                'aura': {'commit': spec['aura_commit']},
                'uboot-aurora': {'commit': spec['uboot_commit']}}))
            for package, key in [('linux-aurora', 'kernel_commit'), ('aura', 'aura_commit'),
                                 ('uboot-aurora', 'uboot_commit')]:
                directory = root / 'packages' / package
                directory.mkdir(parents=True)
                (directory / 'PKGBUILD').write_text('_commit=' + spec[key] + '\n')
            base = {'sha256': spec['base_sha256'], 'bytes': 123, 'signing_fingerprint': spec['base_signer']}
            (root / 'images/base.json').write_text(json.dumps(base))
            self.assertEqual(candidate.check_snapshot(root, spec), base)
            recipe = root / 'packages/aura/PKGBUILD'
            recipe.write_text('_commit=' + 'f' * 40 + '\n')
            with self.assertRaisesRegex(ValueError, 'Recipe/source'):
                candidate.check_snapshot(root, spec)
            recipe.write_text('_commit=' + spec['aura_commit'] + '\n')
            uboot = root / 'packages/uboot-aurora/PKGBUILD'
            uboot.write_text('_commit=' + '0' * 40 + '\n')
            with self.assertRaisesRegex(ValueError, 'Recipe/source.*uboot'):
                candidate.check_snapshot(root, spec)
            uboot.write_text('_commit=' + spec['uboot_commit'] + '\n')
            base['bytes'] += 1
            (root / 'images/base.json').write_text(json.dumps(base))
            with self.assertRaisesRegex(ValueError, 'base metadata'):
                candidate.check_snapshot(root, spec)

    def test_mac_and_intel_are_rejected_before_any_commands(self):
        for system, machine in [('Darwin', 'arm64'), ('Linux', 'x86_64')]:
            with mock.patch.object(candidate.platform, 'system', return_value=system), \
                 mock.patch.object(candidate.platform, 'machine', return_value=machine), \
                 mock.patch.object(candidate.bringup, 'run') as run:
                with self.assertRaisesRegex(ValueError, 'disposable native ARM64'):
                    candidate.build('aura')
                run.assert_not_called()


if __name__ == '__main__':
    unittest.main()

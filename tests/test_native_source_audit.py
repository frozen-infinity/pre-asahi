import importlib.util
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import native_source_audit as audit

class SourceAuditBoundaryTests(unittest.TestCase):
    def lock(self):
        return {name: {'commit': sha} for name, sha in audit.PINS.items()}

    def sources(self):
        files = {}
        for _, repo, path, needles in audit.RULES:
            files[(repo, path)] = files.get((repo, path), '') + '\n'.join(needles) + '\n'
        return files

    def test_matching_text_cannot_become_hardware_approval(self):
        report = audit.report_sources(self.lock(), self.sources())
        self.assertFalse(report['native_boot_proven'])
        self.assertFalse(report['hardware_actions_performed'])
        self.assertEqual(report['status'], 'STATIC_SOURCE_AUDIT_ONLY')
        self.assertEqual(report['missing_anchor_groups'], [])

    def test_changed_revision_requires_review(self):
        lock = self.lock()
        lock['m1n1']['commit'] = '0' * 40
        with self.assertRaises(ValueError):
            audit.report_sources(lock, self.sources())

    def test_missing_evidence_is_visible(self):
        files = self.sources()
        files[('linux', 'arch/arm64/kernel/idle.c')] = ''
        report = audit.report_sources(self.lock(), files)
        self.assertIn('kernel_idle_parameter', report['missing_anchor_groups'])

if __name__ == '__main__':
    unittest.main()

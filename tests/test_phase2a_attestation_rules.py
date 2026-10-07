"""Rule sources are actual attestation inputs, including canonical authority."""
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.workflow_eval.attestation import _rule_hashes
from tools.workflow_eval.context import digest


class AttestationCanonicalRules(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / 'AGENTS.md').write_text(
            '<!-- canonical-rules: agents version=phase2a-1 -->', encoding='utf-8')

    def test_missing_rule_authority_cannot_build_attestation_identity(self):
        with self.assertRaises(ValueError):
            _rule_hashes(self.root, [])

    def test_rule_catalog_exact_content_is_bound(self):
        shutil.copytree(ROOT / '.agents/rules', self.root / '.agents/rules')
        hashes = _rule_hashes(self.root, [])
        self.assertEqual(hashes['.agents/rules/canonical.json'],
                         digest((self.root / '.agents/rules/canonical.json').read_bytes()))

    def test_legacy_fixture_rules_remain_usable(self):
        (self.root / 'AGENTS.md').write_text('Read the full note.', encoding='utf-8')
        self.assertEqual(set(_rule_hashes(self.root, [])), {'AGENTS.md'})


if __name__ == '__main__':
    unittest.main()

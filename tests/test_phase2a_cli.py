"""Exercise usable canonical-rule and ledger CLI paths against real fixture Git."""
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).parent))
import test_decision_ledger as ledger_fixture


class Phase2ACli(unittest.TestCase):
    setUp = ledger_fixture.DecisionLedger.setUp
    git = ledger_fixture.DecisionLedger.git

    def save(self, name, value):
        directory = self.root / '.workflow-eval'
        directory.mkdir(exist_ok=True)
        target = directory / name
        target.write_text(json.dumps(value, ensure_ascii=False), encoding='utf-8')
        return str(target)

    def run_cli(self, *args, expected=0):
        result = subprocess.run([sys.executable, '-m', 'tools.workflow_eval.cli', *args],
            cwd=self.root, capture_output=True, env=os.environ | {'PYTHONPATH': str(ROOT), 'PYTHONUTF8': '1'})
        self.assertEqual(result.returncode, expected, result.stderr.decode('utf-8'))
        return result

    def test_create_validate_and_explicit_versioned_update(self):
        self.run_cli('ledger-create', self.save('inputs.json', self.inputs))
        ledger_path = self.root / '.workflow-eval/ledger-create.json'
        self.run_cli('ledger-validate', str(ledger_path))
        changes = dict(updated_at='2026-10-07T00:01:00Z',
            replacements=[dict(decision_id='heading-1',
                replacement=dict(id='heading-2', text='Retain concise headings.', provenance_ids=['task']),
                reason='Explicit wording clarification without a product change.')])
        self.run_cli('ledger-update', str(ledger_path), '--changes', self.save('changes.json', changes))
        updated = json.loads((self.root / '.workflow-eval/ledger-update.json').read_text(encoding='utf-8'))
        self.assertEqual(updated['ledger_version'], 2)
        self.assertEqual(updated['superseded_decisions'][0]['replacement_id'], 'heading-2')

    def test_invalid_ledger_render_acquires_full_authority_and_prior_specification(self):
        prior = self.root / '.workflow-eval/prior.md'
        invalid = self.save('invalid.json', {})
        prior.write_text('Write the developer note. Use concise headings.', encoding='utf-8')
        self.run_cli('ledger-render', invalid, '--authority', self.save('authority.json', self.authority_paths),
                     '--prior-spec-file', str(prior))
        rendered = json.loads((self.root / '.workflow-eval/ledger-render.json').read_text(encoding='utf-8'))
        self.assertEqual(rendered['route'], 'full_authority')
        self.assertTrue(rendered['independent_review_required'])
        self.assertEqual(set(rendered['payload']['authorities']), {'repository_rules', 'canonical_docs', 'source'})

    def test_rules_cli_resolves_full_body_and_rejects_wrong_version(self):
        agents = self.root / 'AGENTS.md'
        agents.write_bytes((ROOT / 'AGENTS.md').read_bytes())
        self.run_cli('rules-expand', str(agents), '--consumer', 'agents')
        expanded = json.loads((self.root / '.workflow-eval/expanded-rules.json').read_text(encoding='utf-8'))
        self.assertIn('Never place orders on a live account.', expanded['text'])
        agents.write_text(agents.read_text(encoding='utf-8').replace('phase2a-1', 'unknown-version'), encoding='utf-8')
        self.run_cli('rules-expand', str(agents), '--consumer', 'agents', expected=1)

    def test_unknown_json_schema_is_rejected_without_writing_success(self):
        self.run_cli('ledger-validate', self.save('unknown.json', {'schema_version': 99}), expected=1)
        self.assertFalse((self.root / '.workflow-eval/ledger-validate.json').exists())


if __name__ == '__main__':
    unittest.main()

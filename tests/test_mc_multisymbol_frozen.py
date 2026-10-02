"""Portable checks of the recorded twelve cases; never launches a Tester."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from tools.build_tester_mc_multisymbol import build
from tools.mc_multisymbol_runner import (
    build_cases, selection_copy, validate_result_binding, validate_replay_rows,
)
from tools.mc500k_batch import strict_rows

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / 'verification/mc_multisymbol_20261002_6230'


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8'))


def digest(data):
    return hashlib.sha256(data).hexdigest()


class FrozenEvidenceTest(unittest.TestCase):
    def setUp(self):
        self.manifest = read_json(EVIDENCE / 'matrix/manifest_final.json')

    def test_fixed_twelve_conditions_and_exact_input_bytes(self):
        keys = lambda rows: {(c['count'], c['mode'], c['load'], tuple(c['symbols'])) for c in rows}
        self.assertEqual(len(self.manifest), 12)
        self.assertEqual(keys(self.manifest), keys(build_cases()))
        baseline = read_json(EVIDENCE / 'baseline_inputs.json')
        self.assertEqual(digest(baseline['text'].encode(baseline['encoding'])), baseline['sha256'])
        for c in self.manifest:
            self.assertEqual(c['original_set_sha256'], baseline['sha256'])
            selected = selection_copy(baseline['text'], tuple(c['symbols']))
            self.assertEqual(digest(selected.encode('utf-16')), c['selected_set_sha256'])
            config = read_json(EVIDENCE / 'frozen_configs.json')[c['case']]
            self.assertEqual(digest(config.encode('utf-8')), c['config_sha256'])
        reference = read_json(EVIDENCE / 'finish_validation.json')['product_source']['sha256']
        for name, expected in reference.items():
            self.assertEqual(digest((ROOT / 'src' / name).read_bytes()), expected)

    def test_generated_sources_match_measured_bundles_bit_for_bit(self):
        for mode in (0, 2):
            with tempfile.TemporaryDirectory() as td:
                directory = Path(td) / 'generated'
                build(directory, mode)
                for c in (c for c in self.manifest if c['mode'] == mode):
                    for name, expected in c['source_sha256'].items():
                        data = (directory / name).read_bytes()
                        # The eight N2/N3 runs preceded the diagnostic duration
                        # capacity correction. Restore only that recorded limit.
                        if c['diagnostic_duration_capacity'] == 3000000 and name == 'TesterMCSchedulerValidation.mqh':
                            self.assertEqual(data.count(b'MCV_DURATION_LIMIT=12000000'), 1)
                            data = data.replace(b'MCV_DURATION_LIMIT=12000000', b'MCV_DURATION_LIMIT=3000000')
                        self.assertEqual(digest(data), expected, (c['case'], name))

    def test_recorded_replay_and_fresh_attempt_identity(self):
        total = 0
        for c in self.manifest:
            directory = EVIDENCE / 'native' / c['case']
            result = read_json(directory / 'result.json')
            validate_result_binding(result, c)
            attempt = read_json(directory / 'attempt.json')
            self.assertEqual(attempt['status'], 'COLLECTABLE')
            self.assertEqual(attempt['exit_code'], 0)
            for key in ('case', 'mode', 'load'):
                self.assertEqual(attempt[key], c[key])
            self.assertEqual(result['runtime_errors'], 0)
            self.assertEqual(result['warnings'], 0)
            names = [n for n in result['exports'] if n.endswith('_replay.csv')]
            self.assertEqual(len(names), 1)
            raw = (directory / names[0]).read_bytes()
            self.assertEqual(digest(raw), result['exports'][names[0]])
            rows = strict_rows(raw.decode('utf-8-sig'))
            count = int(result['scheduler']['comparisons'])
            validate_replay_rows(rows, count)
            total += count
        self.assertEqual(total, 1316)


if __name__ == '__main__':
    unittest.main()

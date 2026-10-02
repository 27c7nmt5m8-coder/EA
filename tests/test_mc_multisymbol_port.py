"""The Tester generator must preserve current canonical indicator semantics."""
import unittest
from pathlib import Path

from tools.build_tester_pipeline import instrument_state, replace_once


ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / 'src/MT3SymbolState.mqh'


class CanonicalPortTest(unittest.TestCase):
    def test_read_indicator_copybuffer_precedes_barscalculated_and_is_single_use(self):
        source = STATE.read_bytes()
        built = instrument_state(source).decode('utf-8-sig')
        start = built.index('bool ReadIndicator(')
        end = built.index('\n}', start)
        body = built[start:end]
        self.assertEqual(body.count('CopyBuffer(handle,buffer,shift,1,a)'), 1)
        self.assertEqual(body.count('BarsCalculated(handle)'), 1)
        self.assertLess(body.index('CopyBuffer(handle,buffer,shift,1,a)'),
                        body.index('BarsCalculated(handle)'))
        self.assertIn('TPCopyBufferResult(', body)
        self.assertIn('TPBarsCalculated(', body)
        self.assertIn('TPReadFailure(3)', body)

    def test_unrecognized_current_indicator_shape_fails_closed(self):
        source = STATE.read_bytes()
        mutated = replace_once(source, 'CopyBuffer(handle,buffer,shift,1,a)',
                               'CopyBuffer(handle,buffer,shift,2,a)')
        with self.assertRaisesRegex(ValueError, 'anchor missing or ambiguous'):
            instrument_state(mutated)


if __name__ == '__main__':
    unittest.main()

"""Canonical transport keeps every value while removing formatting overhead."""
import importlib
import math
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class CanonicalSerialization(unittest.TestCase):
    def api(self):
        from importlib.util import find_spec
        self.assertIsNotNone(find_spec('tools.workflow_eval.serialization'))
        return importlib.import_module('tools.workflow_eval.serialization')

    def test_key_order_unicode_and_exact_hash(self):
        m = self.api()
        a = {'z': [2, {'b': '本文', 'a': False}], 'a': None}
        b = {'a': None, 'z': [2, {'a': False, 'b': '本文'}]}
        self.assertEqual(m.canonical_json(a), '{"a":null,"z":[2,{"a":false,"b":"本文"}]}')
        self.assertEqual(m.canonical_hash(a), m.canonical_hash(b))
        import json
        self.assertEqual(json.loads(m.canonical_json(a)), a)
        self.assertNotEqual(m.canonical_hash(a), m.canonical_hash(dict(a, a=0)))

    def test_nonfinite_and_nonstring_keys_are_rejected(self):
        m = self.api()
        for value in [math.nan, math.inf, -math.inf, {1: 'ambiguous'}, {'x': {False: 1}}]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                m.canonical_json(value)


if __name__ == '__main__':
    unittest.main()

import unittest
from native_adapter import prepare


class Types(unittest.TestCase):
    def test_mql_widths_without_rewriting_literals_or_system_headers(self):
        value = prepare('#include <vector>\nlong x; ulong y; uint z; long long native; // long\nconst char*s="long";')
        self.assertIn('mql_long x; mql_ulong y; mql_uint z; long long native;', value)
        self.assertIn('// long', value)
        self.assertIn('"long"', value)
        self.assertLess(value.index('#include <vector>'), value.index('using mql_long'))
        self.assertIn('sizeof(datetime)==8', prepare('using datetime=long;'))


if __name__ == '__main__':
    unittest.main()

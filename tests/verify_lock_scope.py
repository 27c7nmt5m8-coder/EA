"""Byte-level scope audit against the uploaded v2.44 ZIP; not native compilation.

Only the four reviewed existence guards and eight explicit local initializers
may differ. Historical hashes and all other production bytes remain fixed.
"""
from pathlib import Path
import hashlib
import json

ROOT = Path(__file__).resolve().parents[1]
baseline = json.loads((ROOT / 'tests/v244_lock_fix_baseline.json').read_text())
keys = {
    'MT3SymbolState.mqh': ['g_lockKey'],
    'MTFAutoTrader_3Mode_AI_v2_44.mq5': ['g_execKey', 'g_propControllerKey'],
    'MTFAutoTrader_AI_Worker.mq5': ['g_workerRegistry+"owner"'],
}


def replace_once(data, old, new):
    old, new = old.encode(), new.encode()
    assert data.count(old) == 1, 'Missing or repeated reviewed source change: ' + old.decode()
    return data.replace(old, new, 1)


actual = {p.name for p in (ROOT / 'src').iterdir() if p.is_file()}
assert actual == set(baseline['source_sha256']), 'Unexpected production file addition/removal'
results = []
for name, expected in baseline['source_sha256'].items():
    original_bytes = (ROOT / 'src' / name).read_bytes()
    projected = original_bytes
    for key in keys.get(name, []):
        projected = replace_once(projected,
            '(!GlobalVariableCheck(' + key + ') && !GlobalVariableTemp(' + key + '))',
            '!GlobalVariableTemp(' + key + ')')
    if name == 'MT3SymbolState.mqh':
        for var in ['highShift1', 'highShift2', 'lowShift1', 'lowShift2']:
            projected = replace_once(projected, 'int ' + var + '=-1;', 'int ' + var + ';')
        for var in ['highPrice1', 'highPrice2', 'lowPrice1', 'lowPrice2']:
            projected = replace_once(projected, 'double ' + var + '=0.0;', 'double ' + var + ';')
    assert hashlib.sha256(projected).hexdigest() == expected, 'Unreviewed production change in ' + name
    results.append({'file': name, 'passed': True,
                    'byte_identical_to_input': original_bytes == projected,
                    'sha256': hashlib.sha256(original_bytes).hexdigest()})

result = {'scope': 'Exact production bytes after reversing only 4 lock creation guards and 8 safe local initializers.',
          'input_zip_sha256': baseline['input_zip_sha256'], 'passed': len(results), 'failed': 0,
          'lock_sites': 4, 'explicit_initializers': 8, 'files': results}
(ROOT / 'verification/lock_fix_scope.json').write_text(json.dumps(result, indent=2) + '\n')
print('PASS', len(results), 'production files: only 4 lock guards + 8 retained local initializers differ')

"""Byte-level scope audit against the uploaded v2.44 ZIP; not native compilation.

Only the four reviewed existence guards, eight explicit local initializers, and
the tester-only live connection exception may differ. Historical hashes and all
other production bytes remain fixed.
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
        projected = replace_once(projected,
            'string m_lastTesterDiagnosticStatus;\nint m_testerDiagnosticCount;\n', '')
        projected = replace_once(projected,
            'm_lastTesterDiagnosticStatus="";\nm_testerDiagnosticCount=0;\n', '')
        projected = replace_once(projected,
            '(!MQLInfoInteger(MQL_TESTER) && !TerminalInfoInteger(TERMINAL_CONNECTED))',
            '!TerminalInfoInteger(TERMINAL_CONNECTED)')
        for var in ['highShift1', 'highShift2', 'lowShift1', 'lowShift2']:
            projected = replace_once(projected, 'int ' + var + '=-1;', 'int ' + var + ';')
        for var in ['highPrice1', 'highPrice2', 'lowPrice1', 'lowPrice2']:
            projected = replace_once(projected, 'double ' + var + '=0.0;', 'double ' + var + ';')
    if name == 'MT3TradeJournal.mqh':
        helper = 'void TesterStatusDiagnostic()\n{\n if(!MQLInfoInteger(MQL_TESTER)) return;\n if(g_status==m_lastTesterDiagnosticStatus) return;\n m_lastTesterDiagnosticStatus=g_status;m_testerDiagnosticCount++;\n PrintFormat("[MT3 TESTER DIAG] symbol=%s status=%s scan=%d universe=%d connected=%d terminal_trade=%d mql_trade=%d account_trade=%d account_expert=%d history=%d mc_ready=%d mc_allowed=%d risk_mode=%s samples=%d mc_risk=%.4f account_unresolved=%d symbol_unresolved=%d exposure=%d",\n  m_symbol,g_status,(int)m_scanEnabled,(int)InUniverseNow(),(int)TerminalInfoInteger(TERMINAL_CONNECTED),\n  (int)TerminalInfoInteger(TERMINAL_TRADE_ALLOWED),(int)MQLInfoInteger(MQL_TRADE_ALLOWED),\n  (int)AccountInfoInteger(ACCOUNT_TRADE_ALLOWED),(int)AccountInfoInteger(ACCOUNT_TRADE_EXPERT),\n  (int)g_historyOK,(int)g_mcReady,(int)g_mcAllowed,EnumToString(RiskMode),g_sampleCount,g_mcRisk,\n  (int)AnyAccountUnresolved(),(int)HasUnresolvedOrder(),(int)EntryExposureBlocked());\n}\n'
        projected = replace_once(projected, helper, '')
        projected = replace_once(projected, ' TesterStatusDiagnostic();\n', '')
    assert hashlib.sha256(projected).hexdigest() == expected, 'Unreviewed production change in ' + name
    results.append({'file': name, 'passed': True,
                    'byte_identical_to_input': original_bytes == projected,
                    'sha256': hashlib.sha256(original_bytes).hexdigest()})

result = {'scope': 'Exact production bytes after reversing lock/initializer/tester exception and tester-only diagnostics.',
          'input_zip_sha256': baseline['input_zip_sha256'], 'passed': len(results), 'failed': 0,
          'lock_sites': 4, 'explicit_initializers': 8, 'tester_connection_exceptions': 1, 'tester_diagnostics': 1, 'files': results}
(ROOT / 'verification/lock_fix_scope.json').write_text(json.dumps(result, indent=2) + '\n')
print('PASS', len(results), 'production files: lock/initializer/tester exception + tester-only diagnostics only')

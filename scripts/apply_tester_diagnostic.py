from pathlib import Path


def replace_once(path, old, new):
    p = Path(path)
    s = p.read_text(encoding="utf-8-sig")
    count = s.count(old)
    if count != 1:
        raise SystemExit(f"{path}: expected exact text once, found {count}")
    p.write_text(s.replace(old, new, 1), encoding="utf-8")


replace_once("src/MT3SymbolState.mqh", "string g_status;\nstring LINE_PREFIX;", "string g_status;\nstring m_lastTesterDiagnosticStatus;\nint m_testerDiagnosticCount;\nstring LINE_PREFIX;")
replace_once("src/MT3SymbolState.mqh", 'g_status="Starting";\nLINE_PREFIX="MTFAUTO_";', 'g_status="Starting";\nm_lastTesterDiagnosticStatus="";\nm_testerDiagnosticCount=0;\nLINE_PREFIX="MTFAUTO_";')

helper = '''void TesterStatusDiagnostic()
{
 if(!MQLInfoInteger(MQL_TESTER)) return;
 if(g_status==m_lastTesterDiagnosticStatus) return;
 m_lastTesterDiagnosticStatus=g_status;m_testerDiagnosticCount++;
 PrintFormat("[MT3 TESTER DIAG] symbol=%s status=%s scan=%d universe=%d connected=%d terminal_trade=%d mql_trade=%d account_trade=%d account_expert=%d history=%d mc_ready=%d mc_allowed=%d risk_mode=%s samples=%d mc_risk=%.4f account_unresolved=%d symbol_unresolved=%d exposure=%d",
  m_symbol,g_status,(int)m_scanEnabled,(int)InUniverseNow(),(int)TerminalInfoInteger(TERMINAL_CONNECTED),
  (int)TerminalInfoInteger(TERMINAL_TRADE_ALLOWED),(int)MQLInfoInteger(MQL_TRADE_ALLOWED),
  (int)AccountInfoInteger(ACCOUNT_TRADE_ALLOWED),(int)AccountInfoInteger(ACCOUNT_TRADE_EXPERT),
  (int)g_historyOK,(int)g_mcReady,(int)g_mcAllowed,EnumToString(RiskMode),g_sampleCount,g_mcRisk,
  (int)AnyAccountUnresolved(),(int)HasUnresolvedOrder(),(int)EntryExposureBlocked());
}
'''
replace_once("src/MT3TradeJournal.mqh", "void JournalSample()\n{", helper + "void JournalSample()\n{\n TesterStatusDiagnostic();")

test_block = ''' reset();tester=true;permissions=false;SymbolState diag;setup(diag);int diagBefore=diag.m_testerDiagnosticCount;
 check(!diag.EntryPreflight(false),"tester diagnostic fixture reaches permission rejection");
 diag.JournalSample();
 check(diag.m_lastTesterDiagnosticStatus==u"Trading permission or broker connection is OFF"&&diag.m_testerDiagnosticCount==diagBefore+1,"tester diagnostic records preflight rejection status");
 diag.JournalSample();check(diag.m_testerDiagnosticCount==diagBefore+1,"tester diagnostic deduplicates unchanged status");
 diag.g_status=u"Waiting for all 7 timeframe indicators";diag.JournalSample();
 check(diag.m_lastTesterDiagnosticStatus==u"Waiting for all 7 timeframe indicators"&&diag.m_testerDiagnosticCount==diagBefore+2,"tester diagnostic records next pipeline status");diag.Shutdown();

 reset();permissions=false;SymbolState liveDiag;setup(liveDiag);
 check(!liveDiag.EntryPreflight(false),"live diagnostic fixture reaches permission rejection");liveDiag.JournalSample();
 check(liveDiag.m_lastTesterDiagnosticStatus==u""&&liveDiag.m_testerDiagnosticCount==0,"live mode emits no tester diagnostics");liveDiag.Shutdown();

'''
anchor = ''' for(bool testing:{false,true}){
  reset();tester=testing;connected=!testing;permissions=false;SymbolState s;setup(s);
  check(!s.EntryPreflight(false),testing?"tester still requires trading permissions":"live still requires trading permissions");s.Shutdown();
 }

 reset();tester=true;connected=false;ScanMode=CURRENT_SYMBOL;fixture_pattern(u"FX");'''
replacement = anchor.rsplit(' reset();tester=true;connected=false;ScanMode=CURRENT_SYMBOL;fixture_pattern(u"FX");',1)[0] + test_block + ' reset();tester=true;connected=false;ScanMode=CURRENT_SYMBOL;fixture_pattern(u"FX");'
replace_once("tests/scenarios.cpp", anchor, replacement)

replace_once("tests/verify_lock_scope.py", "    if name == 'MT3SymbolState.mqh':\n        projected = replace_once(projected,\n            '(!MQLInfoInteger(MQL_TESTER) && !TerminalInfoInteger(TERMINAL_CONNECTED))',", "    if name == 'MT3SymbolState.mqh':\n        projected = replace_once(projected,\n            'string m_lastTesterDiagnosticStatus;\\nint m_testerDiagnosticCount;\\n', '')\n        projected = replace_once(projected,\n            'm_lastTesterDiagnosticStatus=\"\";\\nm_testerDiagnosticCount=0;\\n', '')\n        projected = replace_once(projected,\n            '(!MQLInfoInteger(MQL_TESTER) && !TerminalInfoInteger(TERMINAL_CONNECTED))',")
scope_insert = "    if name == 'MT3TradeJournal.mqh':\n        helper = " + repr(helper) + "\n        projected = replace_once(projected, helper, '')\n        projected = replace_once(projected, ' TesterStatusDiagnostic();\\n', '')\n"
replace_once("tests/verify_lock_scope.py", "    assert hashlib.sha256(projected).hexdigest() == expected, 'Unreviewed production change in ' + name", scope_insert + "    assert hashlib.sha256(projected).hexdigest() == expected, 'Unreviewed production change in ' + name")
replace_once("tests/verify_lock_scope.py", "result = {'scope': 'Exact production bytes after reversing only 4 lock guards, 8 safe local initializers, and 1 tester connection exception.',\n          'input_zip_sha256': baseline['input_zip_sha256'], 'passed': len(results), 'failed': 0,\n          'lock_sites': 4, 'explicit_initializers': 8, 'tester_connection_exceptions': 1, 'files': results}\n(ROOT / 'verification/lock_fix_scope.json').write_text(json.dumps(result, indent=2) + '\\n')\nprint('PASS', len(results), 'production files: only 4 lock guards + 8 local initializers + 1 tester connection exception differ')", "result = {'scope': 'Exact production bytes after reversing lock/initializer/tester exception and tester-only diagnostics.',\n          'input_zip_sha256': baseline['input_zip_sha256'], 'passed': len(results), 'failed': 0,\n          'lock_sites': 4, 'explicit_initializers': 8, 'tester_connection_exceptions': 1, 'tester_diagnostics': 1, 'files': results}\n(ROOT / 'verification/lock_fix_scope.json').write_text(json.dumps(result, indent=2) + '\\n')\nprint('PASS', len(results), 'production files: lock/initializer/tester exception + tester-only diagnostics only')")

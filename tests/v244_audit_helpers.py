"""Project reviewed hooks, initializers, locks, tester exception and indicator ordering.

The exact text must be present once. Trading conditions and order arguments are
never masked; the projected functions still have to match the old SHA-256 values.
"""
from json_support import extract


def replace_once(code, old, new=''):
    if code.count(old) != 1:
        raise AssertionError('reviewed v2.44 hook changed: ' + old[:100])
    return code.replace(old, new, 1)


def legacy_lock_guards(code, keys):
    # Require the exact existence guard without masking compare-and-set, release,
    # ownership flags or any other production statement.
    for key in keys:
        code = replace_once(code,
            '(!GlobalVariableCheck(' + key + ') && !GlobalVariableTemp(' + key + '))',
            '!GlobalVariableTemp(' + key + ')')
    return code


def legacy_engine_function(name, code):
    code = extract(name, code)
    if name == 'ReadIndicator':
        code = replace_once(code,
            'CopyBuffer(handle,buffer,shift,1,a)!=1 || BarsCalculated(handle)<=shift',
            'BarsCalculated(handle)<=shift || CopyBuffer(handle,buffer,shift,1,a)!=1')
    elif name == 'EntryPreflight':
        code = replace_once(code,
            '(!MQLInfoInteger(MQL_TESTER) && !TerminalInfoInteger(TERMINAL_CONNECTED))',
            '!TerminalInfoInteger(TERMINAL_CONNECTED)')
    elif name == 'UpdateAutoTrendLines':
        # Preserve the previous warning fix and the historical fingerprints.
        for variable in ['highShift1', 'highShift2', 'lowShift1', 'lowShift2']:
            code = replace_once(code, 'int ' + variable + '=-1;', 'int ' + variable + ';')
        for variable in ['highPrice1', 'highPrice2', 'lowPrice1', 'lowPrice2']:
            code = replace_once(code, 'double ' + variable + '=0.0;', 'double ' + variable + ';')
    elif name == 'UpdatePropProtection':
        code = replace_once(code, 'ulong logId=(ulong)PositionGetInteger(POSITION_IDENTIFIER);')
        code = replace_once(code, 'else JournalMarkDD(logId);')
    elif name == 'ManagePositions':
        code = replace_once(code, '''else
  {
   double smart=buy?entry+r*SmartLockR(currentR):entry-r*SmartLockR(currentR);
   JournalMarkSL(id,EnableSmartBreakEven && MathAbs(candidate-smart)<=TickSize()?1:2,candidate);
  }''')
    elif name == 'Maintain':
        code = replace_once(code, 'ProcessAIReply();JournalSample();', 'ProcessAIReply();')
    elif name == 'TradeEvent':
        code = replace_once(code, 'm_journalDirty=true;')
    elif name == 'Init':
        code = legacy_lock_guards(code, ['g_lockKey'])
        code = replace_once(code, '''m_journalFrom=(datetime)StateGet(g_statePrefix+"log.from",(double)TimeCurrent());
 if(m_journalFrom<=0 || m_journalFrom>TimeCurrent()) m_journalFrom=TimeCurrent();
 m_portfolioRejects=StateGet(g_statePrefix+"log.portfolio.rejects");
 m_lastPortfolioRejectBar=(datetime)StateGet(g_statePrefix+"log.portfolio.bar");
 m_portfolioReportDirty=m_portfolioRejects>0;''')
    elif name == 'Shutdown':
        code = replace_once(code, 'CancelAIRequest();if(g_lockOwned) JournalMaintenance();', 'CancelAIRequest();')
    return code


def legacy_main(code):
    code = legacy_lock_guards(code, ['g_execKey', 'g_propControllerKey'])
    for name in ['RestoreJournalSymbols', 'ServiceTradeJournals']:
        code = replace_once(code, extract(name, code))
    for old, new in [
        ('#include "MT3PortfolioRisk.mqh"', ''), ('#include "MT3TradeLog.mqh"', ''),
        ('g_scanCursor=0,g_mcCursor=0,g_journalCursor=0;', 'g_scanCursor=0,g_mcCursor=0;'),
        ('DispatchQueue();ServiceTradeJournals();RenderDashboard();', 'DispatchQueue();RenderDashboard();'),
        ('g_chartSymbol=_Symbol;g_logRun="";g_journalCursor=0;', 'g_chartSymbol=_Symbol;'),
        ('RefreshAccountHistory(true);RefreshUniverse();RestoreJournalSymbols();', 'RefreshAccountHistory(true);RefreshUniverse();'),
    ]:
        code = replace_once(code, old, new)
    return code.replace('2.44', '2.42')


def legacy_worker(code):
    return legacy_lock_guards(code, ['g_workerRegistry+"owner"']).replace('2.44', '2.42')

"""Generate an isolated Tester copy with observational Monte Carlo timelines."""
import argparse
from pathlib import Path
import tempfile

try:
    from .build_tester_bottlenecks import build as base_build
    from .build_tester_pipeline import replace_once, SOURCE, MAIN, STATE
except ImportError:
    from build_tester_bottlenecks import build as base_build
    from build_tester_pipeline import replace_once, SOURCE, MAIN, STATE

TOOLS=Path(__file__).resolve().parent


def build(output):
    output=Path(output).resolve()
    if output==SOURCE.resolve() or SOURCE.resolve() in output.parents or output.exists():
        raise ValueError('Output must be a new directory outside canonical sources')
    with tempfile.TemporaryDirectory() as tmp:
        staged=Path(tmp)/'base';base_build(staged)
        files={p.name:p.read_bytes() for p in staged.iterdir()}
    main=replace_once(files[MAIN],'!TPOSelfTest() || !TPBSelfTest()',
                     '!TPOSelfTest() || !TPBSelfTest() || !TPMCSelfTest()')
    main=replace_once(main,'void OnTimer()\n{','void OnTimer()\n{\n g_tpmcTimer++;')
    main=replace_once(main,' TPPrintSummary(reason);TPOPrintSummary();TPBPrintSummary();',
                     ' for(int i=0;i<ArraySize(g_symbols);i++) g_symbols[i].TPMCStop();\n TPMCExport();\n TPPrintSummary(reason);TPOPrintSummary();TPBPrintSummary();')
    files[MAIN]=main
    diag=files['TesterBottleneckDiag.mqh']
    diag=replace_once(diag,'double scoreFirst,scoreMin,scoreMax;','double scoreFirst,scoreMin,scoreMax,scoreLast;')
    diag=replace_once(diag,' if(!g_tpb[i].scoreSeen)',' g_tpb[i].scoreLast=score;\n if(!g_tpb[i].scoreSeen)')
    diag=replace_once(diag,'"CodexBottleneck_20260927_"','"CodexMCTimelineDetail_20260927_"')
    files['TesterBottleneckDiag.mqh']=diag+b'\n#include "TesterMCTimelineDiag.mqh"\n'
    files['TesterOpportunityDiag.mqh']=replace_once(files['TesterOpportunityDiag.mqh'],
        '"CodexBottleneckLegacy_20260927_"','"CodexMCTimelineLegacy_20260927_"')
    files['TesterOpportunityMethods.mqh']=replace_once(files['TesterOpportunityMethods.mqh'],
        ' if(candidateNow) TPBCandidate(index,reason);',
        ' if(candidateNow) TPBCandidate(index,reason);\n TPMCObserve(index,candidateNow);')
    state=files[STATE]
    members='''int m_tpmcCycle,m_tpmcParent,m_tpmcHistoryVersion,m_tpmcInputVersion,m_tpmcStateVersion,m_tpmcCycleInput;
int m_tpmcCompleteCycle,m_tpmcValidCycle,m_tpmcCallPath,m_tpmcEligible,m_tpmcWins,m_tpmcLosses,m_tpmcLastOperations;
datetime m_tpmcCompleteTime,m_tpmcLastEligible;
ulong m_tpmcDirty,m_tpmcOperations,m_tpmcCalls,m_tpmcAdvanceUs,m_tpmcObserveTimer;
double m_tpmcReturns[],m_tpmcWinRate;
string m_tpmcDigest,m_tpmcSignature;'''
    init='''m_tpmcCycle=0;m_tpmcParent=0;m_tpmcHistoryVersion=0;m_tpmcInputVersion=0;m_tpmcStateVersion=0;m_tpmcCycleInput=0;
m_tpmcCompleteCycle=0;m_tpmcValidCycle=0;m_tpmcCallPath=0;m_tpmcEligible=-1;m_tpmcWins=0;m_tpmcLosses=0;m_tpmcLastOperations=0;
m_tpmcCompleteTime=0;m_tpmcLastEligible=0;m_tpmcDirty=1;m_tpmcOperations=0;m_tpmcCalls=0;m_tpmcAdvanceUs=0;m_tpmcObserveTimer=0;
m_tpmcWinRate=0;m_tpmcDigest="";m_tpmcSignature="";'''
    edits=[
      ('SymbolState *m_tpObserver;','SymbolState *m_tpObserver;\n'+members),
      ('SymbolState()\n{\nm_tpObserver=NULL;','SymbolState()\n{\nm_tpObserver=NULL;\n'+init),
      ('#include "TesterBottleneckMethods.mqh"','#include "TesterMCTimelineMethods.mqh"\n#include "TesterBottleneckMethods.mqh"'),
      (' g_historyDirty=false;g_historyOK=true;g_lastHistory=TimeCurrent();',
       ' g_historyDirty=false;g_historyOK=true;g_lastHistory=TimeCurrent();\n TPMCHistory();'),
      ('void UpdateMonteCarloRisk(bool force=false)\n{','void UpdateMonteCarloRisk(bool force=false,int tpmcPath=0)\n{\n m_tpmcCallPath=tpmcPath;'),
      ('if(g_historyOK) UpdateMonteCarloRisk(changed);','if(g_historyOK) UpdateMonteCarloRisk(changed,1);'),
      ('if(updateStats && g_historyOK) UpdateMonteCarloRisk(changed);','if(updateStats && g_historyOK) UpdateMonteCarloRisk(changed,2);'),
      ('UpdateMonteCarloRisk(true);','UpdateMonteCarloRisk(true,3);'),
      ('UpdateMonteCarloRisk(false);','UpdateMonteCarloRisk(false,3);'),
      (' if(force) m_mcActive=false;',' TPMCBeforeForce(force);\n if(force) m_mcActive=false;'),
      (' g_mcReady=false;g_mcAllowed=false;g_mcRisk=0;',' TPMCRequest(force);\n g_mcReady=false;g_mcAllowed=false;g_mcRisk=0;'),
      ('m_tpbMCOutcome=g_mcAllowed?TPB_MC_BASELINE_ALLOWED:TPB_MC_BASELINE_DENIED;return;',
       'm_tpbMCOutcome=g_mcAllowed?TPB_MC_BASELINE_ALLOWED:TPB_MC_BASELINE_DENIED;TPMCComplete(g_mcAllowed?"BASELINE_ALLOWED":"BASELINE_DENIED");return;'),
      ('m_tpbMCOutcome=TPB_MC_WINRATE_DENIED;return;',
       'm_tpbMCOutcome=TPB_MC_WINRATE_DENIED;TPMCComplete("MINIMUM_WIN_RATE_DENIED");return;'),
      ('m_tpbMCOutcome=TPB_MC_SEQUENCE_UNAVAILABLE;return;',
       'm_tpbMCOutcome=TPB_MC_SEQUENCE_UNAVAILABLE;TPMCEmit("CALCULATION_FAILED","ARRAY_ALLOCATION");return;'),
      ('m_tpbMCStarted=TimeCurrent();','m_tpbMCStarted=TimeCurrent();TPMCEmit("START");'),
      ('void AdvanceMonteCarlo(ulong deadline)','void AdvanceMonteCarloCore(ulong deadline)'),
      ('   PrintFormat("MC %s: samples=%d winrate=%.2f%% cap=%.4f%%",m_symbol,g_sampleCount,100*g_winRate,g_mcRisk);',
       '   m_tpmcLastOperations=operations;\n   PrintFormat("MC %s: samples=%d winrate=%.2f%% cap=%.4f%%",m_symbol,g_sampleCount,100*g_winRate,g_mcRisk);'),
      ('  m_mcCandidate--;m_mcRun=0;m_mcRandom=(uint)MonteCarloSeed;if(m_mcRandom==0) m_mcRandom=1;\n }\n}',
       '  m_mcCandidate--;m_mcRun=0;m_mcRandom=(uint)MonteCarloSeed;if(m_mcRandom==0) m_mcRandom=1;\n }\n m_tpmcLastOperations=operations;\n}'),
      (' if(trans.type==TRADE_TRANSACTION_DEAL_ADD || trans.type==TRADE_TRANSACTION_POSITION || trans.type==TRADE_TRANSACTION_HISTORY_ADD) g_historyDirty=true;',
       ' if(trans.type==TRADE_TRANSACTION_DEAL_ADD || trans.type==TRADE_TRANSACTION_POSITION || trans.type==TRADE_TRANSACTION_HISTORY_ADD) {g_historyDirty=true;TPMCDirty(trans.type==TRADE_TRANSACTION_DEAL_ADD?2:(trans.type==TRADE_TRANSACTION_POSITION?4:8));}'),
      ('  GlobalVariablesFlush();g_historyDirty=true;','  GlobalVariablesFlush();g_historyDirty=true;TPMCDirty(16);'),
      (' TPInc(TP_ORDER_SUCCEEDED);TPAcceptedOrderSpread(latest,m_point);',
       ' TPInc(TP_ORDER_SUCCEEDED);TPMCAccepted();TPAcceptedOrderSpread(latest,m_point);'),
      ('RecordEntryAttempt(manual,pattern);g_historyDirty=true;',
       'RecordEntryAttempt(manual,pattern);g_historyDirty=true;TPMCDirty(32);'),
      ('{if(ClearPendingOrder()) g_historyDirty=true;return;}',
       '{if(ClearPendingOrder()) {g_historyDirty=true;TPMCDirty(64);}return;}'),
      ('if(!OrderSelect(found) && PendingHistoryOrderFinal(found)) {if(ClearPendingOrder()) g_historyDirty=true;}',
       'if(!OrderSelect(found) && PendingHistoryOrderFinal(found)) {if(ClearPendingOrder()) {g_historyDirty=true;TPMCDirty(64);}}'),
      ('if(ClearPendingOrder()) {g_historyDirty=true;Print(',
       'if(ClearPendingOrder()) {g_historyDirty=true;TPMCDirty(64);Print('),
    ]
    for old,new in edits:state=replace_once(state,old,new)
    files[STATE]=state
    for name in ('TesterMCTimelineDiag.mqh','TesterMCTimelineMethods.mqh'):files[name]=(TOOLS/name).read_bytes()
    output.mkdir(parents=True)
    for name,data in files.items():(output/name).write_bytes(data)
    return output/MAIN


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    print(build(parser.parse_args().output))

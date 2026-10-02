"""Build isolated Tester diagnostics for Current20k versus fixed500k only.

The old generator is unmodified. All transforms fail closed on changed anchors.
Post-test RNG/index verification uses constant memory and never runs in the
actual trading callback. Endpoint fingerprints are witnesses, not collision-free
proofs of the actual callback's intermediate floating-point trajectory.
"""
import argparse
from pathlib import Path
import tempfile

try:
    from .build_tester_mc_scheduler import build as base_build, replay_core
    from .build_tester_pipeline import SOURCE, MAIN, STATE, replace_once
except ImportError:
    from build_tester_mc_scheduler import build as base_build, replay_core
    from build_tester_pipeline import SOURCE, MAIN, STATE, replace_once

TOOLS = Path(__file__).resolve().parent


def change(text, old, new):
    return replace_once(text.encode(), old, new).decode()


def validation_replay(source):
    text = replay_core(source)
    # Keep exactly the original RNG and the two requested scheduling cores.
    rng = text[:text.index('void Advance0(')]
    cores = []
    for mode, next_mode in ((0, 1), (2, 3)):
        core = text[text.index(f'void Advance{mode}('):text.index(f'void Advance{next_mode}(')]
        core = change(core,
            '  int k=(int)(NextMCRandom()%(uint)ArraySize(m_mcReturns));',
            '  int k=(int)(NextMCRandom()%(uint)ArraySize(m_mcReturns));\n  MCVVerifyDraw(k);')
        cores.append(core)
    return rng + ''.join(cores)


def validation_scheduler(text):
    text = change(text, ' ulong riskBits;uint rng;', ' ulong riskBits,operations;uint rng;')
    text = change(text, ' g_mcsCallbacks[n]=c;',
                  ' g_mcsCallbacks[n]=c;\n int snapshot=MCSFind(cycle);if(snapshot>=0) g_mcsSnapshots[snapshot].operations+=(ulong)operations;else g_mcsUnknown++;')
    text = change(text, ' string signature;\n bool Prepare', ''' string signature;
 uint mcvReferenceRng;int mcvReferenceCandidate;ulong mcvDraws,mcvSequenceErrors;
 void MCVVerifyDraw(const int sampleIndex)
 {
  // Constant-memory exact comparison, exclusively during post-OnTester replay.
  if(m_mcCandidate!=mcvReferenceCandidate)
  {
   if(m_mcCandidate!=mcvReferenceCandidate-1) mcvSequenceErrors++;
   mcvReferenceCandidate=m_mcCandidate;mcvReferenceRng=(uint)MonteCarloSeed;
   if(mcvReferenceRng==0) mcvReferenceRng=1;
  }
  uint expected=mcvReferenceRng;
  expected^=expected<<13;expected^=expected>>17;expected^=expected<<5;
  mcvReferenceRng=expected;mcvDraws++;
  if(m_mcRandom!=expected || sampleIndex!=(int)(expected%(uint)ArraySize(m_mcReturns))) mcvSequenceErrors++;
 }
 bool Prepare''')
    text = change(text, '  m_mcActive=true;g_historyDirty=false;',
                  '  mcvReferenceRng=(uint)MonteCarloSeed;if(mcvReferenceRng==0) mcvReferenceRng=1;\n  mcvReferenceCandidate=(int)MathFloor((MaximumRiskPercent-MinimumRiskPercent)/MonteCarloRiskStep+1e-8);mcvDraws=0;mcvSequenceErrors=0;\n  m_mcActive=true;g_historyDirty=false;')
    text = change(text,
        '   {case 0:Advance0(deadline);break;case 1:Advance1(deadline);break;case 2:Advance2(deadline);break;\n    case 3:Advance3(deadline);break;case 4:Advance4(deadline);break;case 5:Advance5(deadline);break;default:return false;}',
        '   {case 0:Advance0(deadline);break;case 2:Advance2(deadline);break;default:return false;}')
    text = change(text, '"p95_us","max_us"', '"p95_us","p99_us","max_us"')
    for var in ('g_mcsTickUs', 'g_mcsTimerUs'):
        text = change(text, f'MCSQuantile({var},.95),MCSQuantile({var},1)',
                      f'MCSQuantile({var},.95),MCSQuantile({var},.99),MCSQuantile({var},1)')
    text = change(text, 'for(int mode=0;mode<6;mode++)', 'for(int mode=0;mode<=2;mode+=2)')
    text = change(text, '"operations_min","operations_median","operations_max"',
                  '"operations_min","operations_median","operations_max","sequence_draws","sequence_errors","sequence_exact","actual_operations"')
    text = change(text, 'r.m_mcCandidate==referenceCandidate && r.totalOperations==referenceOps;',
                  'r.m_mcCandidate==referenceCandidate && r.totalOperations==referenceOps && r.mcvDraws==r.totalOperations && r.mcvSequenceErrors==0;')
    text = change(text, 's.candidate==r.m_mcCandidate);',
                  's.candidate==r.m_mcCandidate && s.operations==r.totalOperations);')
    text = change(text, 'MCSQuantile(r.callbackOps,1)))',
                  'MCSQuantile(r.callbackOps,1),r.mcvDraws,r.mcvSequenceErrors,(int)(r.mcvSequenceErrors==0 && r.mcvDraws==r.totalOperations),s.operations))')
    return text


def build(output, mode=0, qualified=False):
    if mode not in (0, 2):
        raise ValueError('validation supports only modes 0 and 2')
    output = Path(output).resolve()
    if output == SOURCE.resolve() or SOURCE.resolve() in output.parents or output.exists():
        raise ValueError('Output must be new and outside product src')
    with tempfile.TemporaryDirectory() as td:
        staged = Path(td) / 'base'
        base_build(staged, mode, qualified=qualified)
        files = {p.name: p.read_bytes() for p in staged.iterdir()}
    old_tag, tag = f'CodexMCSched{mode}_20260927', f'CodexMCV{mode}_20260927'
    files = {name: data.replace(old_tag.encode(), tag.encode()) for name, data in files.items()}
    scheduler = validation_scheduler(files['TesterMCSchedulerDiag.mqh'].decode())
    scheduler = change(scheduler, '"CodexMCSched"+IntegerToString(MCS_MODE)', '"CodexMCV"+IntegerToString(MCS_MODE)')
    files['TesterMCSchedulerDiag.mqh'] = (scheduler + '\n#include "TesterMCSchedulerValidation.mqh"\n').encode()
    files['TesterMCSchedulerCore.mqh'] = validation_replay((SOURCE / STATE).read_text(encoding='utf-8-sig')).encode()
    main = files[MAIN]
    main = replace_once(main, 'void OnTick() {ulong mcsTickStart=GetMicrosecondCount();',
        'void OnTick() {ulong mcsTickStart=GetMicrosecondCount();long mcvTickServer=(long)TimeCurrent();MqlTick mcvTick;long mcvQuote=SymbolInfoTick(_Symbol,mcvTick)?mcvTick.time_msc:0;')
    main = replace_once(main, 'MCSMeasure(0,GetMicrosecondCount()-mcsTickStart);',
        'ulong mcvTickEnd=GetMicrosecondCount();MCSMeasure(0,mcvTickEnd-mcsTickStart);MCVTickEnd(mcsTickStart,mcvTickEnd,mcvTickServer,mcvQuote);')
    main = replace_once(main, 'double OnTester() {MCSFinish();return 0;}',
        'double OnTester() {if(!MQLInfoInteger(MQL_TESTER)) return 0;MCVPrivacySelfTest();MCSFinish();MCVExport();return 0;}')
    files[MAIN] = main
    state = files[STATE]
    state = replace_once(state, 'SymbolState *m_tpObserver;',
        'SymbolState *m_tpObserver;\nMCVContext m_mcvObserverContext;\nint m_mcvLastRequestInput,m_mcvLastRequestState;')
    state = replace_once(state, 'SymbolState()\n{\nm_tpObserver=NULL;',
        'SymbolState()\n{\nm_tpObserver=NULL;\nZeroMemory(m_mcvObserverContext);m_mcvObserverContext.positionKind=-1;m_mcvLastRequestInput=-1;m_mcvLastRequestState=-1;')
    state = replace_once(state, '#include "TesterMCTimelineMethods.mqh"',
        '#include "TesterMCSchedulerValidationMethods.mqh"\n#include "TesterMCTimelineMethods.mqh"')
    state = replace_once(state, 'void UpdateMonteCarloRisk(bool force=false,int tpmcPath=0)\n{', '''void UpdateMonteCarloRisk(bool force=false,int tpmcPath=0)
{
 MCVRequest r;ZeroMemory(r);r.before=MCVReadContext();r.force=force;r.path=tpmcPath;r.symbol=m_symbol;r.server=(long)TimeCurrent();
 r.sameInput=m_mcvLastRequestInput==m_tpmcInputVersion;r.sameState=m_mcvLastRequestState==m_tpmcStateVersion;
 r.fresh=g_mcReady && !g_historyDirty && !m_mcActive && TimeCurrent()-g_lastMC<MonteCarloRecalculateMinutes*60;
 r.start=GetMicrosecondCount();
 UpdateMonteCarloRiskCore(force,tpmcPath);
 r.elapsed=GetMicrosecondCount()-r.start;
 MCVContext after=MCVReadContext();MCVRequestEnd(r,after,m_tpmcCycle!=r.before.cycle && m_mcActive);
 if(m_tpmcCycle!=r.before.cycle) {m_mcvLastRequestInput=m_tpmcInputVersion;m_mcvLastRequestState=m_tpmcStateVersion;}
}
void UpdateMonteCarloRiskCore(bool force=false,int tpmcPath=0)
{''')
    state = replace_once(state, 'void ManagePositions()\n{', '''void ManagePositions()
{
 ulong started=GetMicrosecondCount();long server=(long)TimeCurrent();
 ManagePositionsCore();
 ulong finished=GetMicrosecondCount();
 MCVManageEnd(started,finished,server);
}
void ManagePositionsCore()
{''')
    state = replace_once(state, ' bool ok=buy?trade.Buy(lot,m_symbol,latest.ask,sl,tp,orderComment):trade.Sell(lot,m_symbol,latest.bid,sl,tp,orderComment);',
        ' string mcvOrderId=MCVOwnedOpportunity(pattern);long mcvOrderServer=(long)TimeCurrent();ulong mcvOrderStart=GetMicrosecondCount();\n bool ok=buy?trade.Buy(lot,m_symbol,latest.ask,sl,tp,orderComment):trade.Sell(lot,m_symbol,latest.bid,sl,tp,orderComment);')
    state = replace_once(state, ' MqlTradeResult result={};trade.Result(result);uint rc=result.retcode;',
        ' ulong mcvOrderEnd=GetMicrosecondCount();\n MqlTradeResult result={};trade.Result(result);uint rc=result.retcode;\n MCVTimingAppend("ENTRY_SEND",m_symbol,mcvOrderId,mcvOrderStart,mcvOrderEnd,mcvOrderServer,(long)TimeCurrent(),latest.time_msc,rc,ok);')
    # Legacy mapping is observational and only follows the existing persistence.
    state = replace_once(state, ' GlobalVariableSet(g_statePrefix+"pat.side",(double)PatternDirection(pattern));',
        ' if(GlobalVariableSet(g_statePrefix+"pat.side",(double)PatternDirection(pattern))>0) MCVRemember(MCVLegacyKey(pattern),MCVOwnedOpportunity(pattern));')
    files[STATE] = state
    methods = files['TesterOpportunityMethods.mqh']
    methods = replace_once(methods, ' g_tpShadow=true;',
        ' m_tpObserver.m_mcvObserverContext=MCVReadContext();\n g_tpShadow=true;')
    files['TesterOpportunityMethods.mqh'] = methods
    patterns = files['MT3ReversalPatterns.mqh']
    patterns = replace_once(patterns, ' if(StateGet(PatternReceiptKey(PatternIdentity(p)))>0) return true;',
        ' if(StateGet(PatternReceiptKey(PatternIdentity(p)))>0) {MCVGuard(p,"RECEIPT",PatternReceiptKey(PatternIdentity(p)));return true;}')
    patterns = replace_once(patterns, ' return LegacyPatternAlreadyUsed(p);',
        ' bool used=LegacyPatternAlreadyUsed(p);if(used) MCVGuard(p,"LEGACY",MCVLegacyKey(p));return used;')
    patterns = replace_once(patterns, '  if(GlobalVariableSet(PatternReceiptKey(ids[i]),1)==0) {GlobalVariablesFlush();return false;}',
        '  if(GlobalVariableSet(PatternReceiptKey(ids[i]),1)==0) {GlobalVariablesFlush();return false;}\n  MCVClaim(p,ids[i]);')
    files['MT3ReversalPatterns.mqh'] = patterns
    # Output metadata only. The parser restores the alias in RAM before the
    # unchanged analytical ownership comparison. Dedicated roots cannot read
    # or append to product logs; core state keys and all AccountInfo calls stay.
    log = files['MT3TradeLog.mqh']
    log = replace_once(log, '"MT3Logs_v244', '"' + tag + '_TradeLogs')
    log = replace_once(log, 'JsonQuote(r.account)', 'JsonQuote("REDACTED_TESTER_ACCOUNT")')
    log = replace_once(log, 'LogCSVAdd(h,row,"Account",r.account,true);',
        'LogCSVAdd(h,row,"Account","REDACTED_TESTER_ACCOUNT",true);')
    log = replace_once(log, ' if(!j.GetString(0,"account",r.account)) return false;',
        ' if(!j.GetString(0,"account",r.account)) return false;\n if(MQLInfoInteger(MQL_TESTER) && r.account=="REDACTED_TESTER_ACCOUNT") r.account=g_account;')
    files['MT3TradeLog.mqh'] = log
    for name in ('TesterMCSchedulerValidation.mqh', 'TesterMCSchedulerValidationMethods.mqh'):
        files[name] = (TOOLS / name).read_bytes()
    output.mkdir(parents=True)
    for name, data in files.items():
        (output / name).write_bytes(data)
    return output / MAIN


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--mode', type=int, choices=(0, 2), default=0)
    args = parser.parse_args()
    print(build(args.output, args.mode))

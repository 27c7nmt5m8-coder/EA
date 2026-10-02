"""Extend a generated Tester copy with read-only score/position/MC accounting."""
import argparse
from pathlib import Path
import tempfile

try:
    from .build_tester_pipeline import build as base_build, replace_once, SOURCE, MAIN, STATE
except ImportError:
    from build_tester_pipeline import build as base_build, replace_once, SOURCE, MAIN, STATE

TOOLS=Path(__file__).resolve().parent


def build(output: Path) -> Path:
    output=output.resolve()
    if output==SOURCE.resolve() or SOURCE.resolve() in output.parents:
        raise ValueError('Diagnostic output must not overwrite canonical sources')
    if output.exists():raise ValueError('Output already exists')
    with tempfile.TemporaryDirectory() as tmp:
        stage=Path(tmp)/'base';base_build(stage,opportunity=True)
        files={p.name:p.read_bytes() for p in stage.iterdir()}
    main=replace_once(files[MAIN],' if(!TPOSelfTest()) return INIT_FAILED;',
                      ' if(!TPOSelfTest() || !TPBSelfTest()) return INIT_FAILED;')
    files[MAIN]=replace_once(main,' TPPrintSummary(reason);TPOPrintSummary();',
                             ' TPPrintSummary(reason);TPOPrintSummary();TPBPrintSummary();')
    diag=replace_once(files['TesterOpportunityDiag.mqh'],'TPO_REJECTED,TPO_STAGE_COUNT',
                      'TPO_REJECTED,TPO_POSITION_PASS,TPO_MC_READY,TPO_MC_PERMITTED,TPO_STAGE_COUNT')
    diag=replace_once(diag,'"CodexOOS_20260927_"','"CodexBottleneckLegacy_20260927_"')
    files['TesterOpportunityDiag.mqh']=diag+b'\n#include "TesterBottleneckDiag.mqh"\n'
    methods=files['TesterOpportunityMethods.mqh']
    for old,new in [
        ('int TPEvaluateOpportunity(const bool allowed,const int safetyReason)\n{',
         'int TPEvaluateOpportunity(const bool allowed,const int safetyReason,bool &candidateNow)\n{\n candidateNow=false;'),
        (' TPOStage(i,TPO_SIGNAL);',' TPOStage(i,TPO_SIGNAL);TPBIdentity(i,p,buy);'),
        (' double score=buy?CalculateFinalBuyScore(p,r):CalculateFinalSellScore(p,r);',
         ' double score=buy?CalculateFinalBuyScore(p,r):CalculateFinalSellScore(p,r);TPBScore(i,score);'),
        (' TPOStage(i,TPO_BEFORE_SAFETY);',' TPOStage(i,TPO_BEFORE_SAFETY);candidateNow=true;'),
        (' m_tpObserver.TPEvaluateOpportunity(allowed,reason);\n g_tpShadow=false;',
         ' bool candidateNow=false;\n int index=m_tpObserver.TPEvaluateOpportunity(allowed,reason,candidateNow);\n g_tpShadow=false;\n if(candidateNow) TPBCandidate(index,reason);'),
    ]:methods=replace_once(methods,old,new)
    files['TesterOpportunityMethods.mqh']=methods
    state=files[STATE]
    edits=[
      ('SymbolState *m_tpObserver;',
       'SymbolState *m_tpObserver;\nint m_tpbPositionKind,m_tpbMCOutcome;\nbool m_tpbPositionBuy,m_tpbPositionOwned,m_tpbNetting,m_tpbDDSeen;\ndouble m_tpbLastDD;\ndatetime m_tpbMCStarted;'),
      ('SymbolState()\n{\nm_tpObserver=NULL;',
       'SymbolState()\n{\nm_tpObserver=NULL;\nm_tpbPositionKind=-1;m_tpbMCOutcome=TPB_MC_INIT;\nm_tpbPositionBuy=false;m_tpbPositionOwned=false;m_tpbNetting=false;m_tpbDDSeen=false;m_tpbLastDD=0;m_tpbMCStarted=0;'),
      (' g_tpLastReject=-1;bool tpAllowed=EntryPreflight(false);',
       ' m_tpbPositionKind=-1;\n g_tpLastReject=-1;bool tpAllowed=EntryPreflight(false);'),
      ('#include "TesterOpportunityMethods.mqh"',
       '#include "TesterBottleneckMethods.mqh"\n#include "TesterOpportunityMethods.mqh"'),
      ('bool EntryExposureBlocked()\n{\n bool netting=AccountInfoInteger(ACCOUNT_MARGIN_MODE)!=ACCOUNT_MARGIN_MODE_RETAIL_HEDGING;',
       'bool EntryExposureBlocked()\n{\n bool netting=AccountInfoInteger(ACCOUNT_MARGIN_MODE)!=ACCOUNT_MARGIN_MODE_RETAIL_HEDGING;\n m_tpbPositionKind=0;m_tpbNetting=netting;'),
      ('  if(netting || OnePositionPerSymbol) return true;',
       '  if(netting || OnePositionPerSymbol) {m_tpbPositionKind=1;m_tpbPositionBuy=PositionGetInteger(POSITION_TYPE)==POSITION_TYPE_BUY;m_tpbPositionOwned=(ulong)PositionGetInteger(POSITION_MAGIC)==MagicNumber;return true;}'),
      ('  if(OrderGetTicket(i)>0 && OrderGetString(ORDER_SYMBOL)==m_symbol) return true;',
       '  if(OrderGetTicket(i)>0 && OrderGetString(ORDER_SYMBOL)==m_symbol) {m_tpbPositionKind=2;return true;}'),
      (' g_mcReady=false;g_mcAllowed=false;g_mcRisk=0;',
       ' g_mcReady=false;g_mcAllowed=false;g_mcRisk=0;\n m_tpbMCOutcome=TPB_MC_INIT;m_tpbDDSeen=false;'),
      (' {g_mcRisk=LimitRisk(BaseRiskPercent);g_mcReady=true;g_mcAllowed=g_mcRisk>0;g_lastMC=TimeCurrent();return;}',
       ' {g_mcRisk=LimitRisk(BaseRiskPercent);g_mcReady=true;g_mcAllowed=g_mcRisk>0;g_lastMC=TimeCurrent();m_tpbMCOutcome=g_mcAllowed?TPB_MC_BASELINE_ALLOWED:TPB_MC_BASELINE_DENIED;return;}'),
      (' {g_mcReady=true;g_lastMC=TimeCurrent();return;}',
       ' {g_mcReady=true;g_lastMC=TimeCurrent();m_tpbMCOutcome=TPB_MC_WINRATE_DENIED;return;}'),
      (' if(ArrayCopy(m_mcReturns,g_returns)!=ArraySize(g_returns) || ArrayResize(m_mcDDs,MonteCarloRuns)!=MonteCarloRuns) return;',
       ' if(ArrayCopy(m_mcReturns,g_returns)!=ArraySize(g_returns) || ArrayResize(m_mcDDs,MonteCarloRuns)!=MonteCarloRuns) {m_tpbMCOutcome=TPB_MC_SEQUENCE_UNAVAILABLE;return;}'),
      (' m_mcActive=true;',' m_mcActive=true;m_tpbMCOutcome=TPB_MC_CALCULATING;m_tpbMCStarted=TimeCurrent();'),
      ('  double dd=m_mcDDs[(int)MathCeil(0.95*MonteCarloRuns)-1];',
       '  double dd=m_mcDDs[(int)MathCeil(0.95*MonteCarloRuns)-1];\n  m_tpbLastDD=dd;m_tpbDDSeen=true;'),
      ('   g_mcAllowed=g_mcRisk>0;g_mcReady=true;g_lastMC=TimeCurrent();m_mcActive=false;',
       '   g_mcAllowed=g_mcRisk>0;g_mcReady=true;g_lastMC=TimeCurrent();m_mcActive=false;\n   m_tpbMCOutcome=g_mcAllowed?TPB_MC_PERMITTED:TPB_MC_BOUNDARY_DENIED;'),
    ]
    for old,new in edits:state=replace_once(state,old,new)
    files[STATE]=state
    for name in ('TesterBottleneckDiag.mqh','TesterBottleneckMethods.mqh'):
        files[name]=(TOOLS/name).read_bytes()
    output.mkdir(parents=True)
    for name,data in files.items():(output/name).write_bytes(data)
    return output/MAIN


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();print(build(args.output))

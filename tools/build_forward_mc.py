"""Build a local Demo candidate, never install, launch or connect a terminal."""
import argparse
import hashlib
import json
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[1] / 'src'
MAIN = 'MTFAutoTrader_3Mode_AI_v2_44.mq5'
STATE = 'MT3SymbolState.mqh'
HEADER = Path(__file__).with_name('ForwardMCObserver.mqh')


def substitutions(name):
    if name == MAIN:
        return [
            ('#include "MT3Config.mqh"', '#include "MT3Config.mqh"\n#include "ForwardMCObserver.mqh"'),
            ('void OnTimer()\n{', 'void OnTimer()\n{\n if(!FOAllowed()) {FOUnknown();return;}g_foTimer++;ulong foTimerStart=GetMicrosecondCount();FOOriginalOnTimer();FOFlush();FODuration(_Symbol,3,foTimerStart,GetMicrosecondCount());\n}\nvoid FOOriginalOnTimer()\n{'),
            ('void OnTick() {MaintainExposure();}', 'void OnTick() {if(!FOAllowed()) {FOUnknown();return;}g_foTicks++;ulong foTickStart=GetMicrosecondCount();MaintainExposure();FODuration(_Symbol,4,foTickStart,GetMicrosecondCount());}'),
            ('void OnTradeTransaction(const MqlTradeTransaction &trans,const MqlTradeRequest &request,const MqlTradeResult &result)\n{', 'void OnTradeTransaction(const MqlTradeTransaction &trans,const MqlTradeRequest &request,const MqlTradeResult &result)\n{\n if(!FOAllowed()) {FOUnknown();return;}FOTrade(trans,request,result);FOOriginalOnTradeTransaction(trans,request,result);\n}\nvoid FOOriginalOnTradeTransaction(const MqlTradeTransaction &trans,const MqlTradeRequest &request,const MqlTradeResult &result)\n{'),
            ('void OnChartEvent(const int id,const long &lparam,const double &dparam,const string &sparam)\n{', 'void OnChartEvent(const int id,const long &lparam,const double &dparam,const string &sparam)\n{\n if(!FOAllowed()) {FOUnknown();return;}FOOriginalOnChartEvent(id,lparam,dparam,sparam);\n}\nvoid FOOriginalOnChartEvent(const int id,const long &lparam,const double &dparam,const string &sparam)\n{'),
            ('int OnInit()\n{', 'int OnInit()\n{\n if(!FOInit()) {Print("FORWARD_DEMO_CANDIDATE refused: environment/input guard");return INIT_FAILED;}int foInit=FOOriginalOnInit();ulong foNow=GetMicrosecondCount();FORecord("INIT",_Symbol,0,foNow,foNow,0,0,foInit);FOFlush(true);return foInit;\n}\nint FOOriginalOnInit()\n{'),
            ('void OnDeinit(const int reason)\n{', 'void OnDeinit(const int reason)\n{\n if(!g_foBound) return;if(FOAllowed()) FOOriginalOnDeinit(reason);else\n {\n  FOUnknown();EventKillTimer();\n  for(int i=0;i<ArraySize(g_symbols);i++)\n  {g_symbols[i].ReleaseIndicators();if(g_symbols[i].g_lockOwned) {GlobalVariableSetOnCondition(g_symbols[i].g_lockKey,0,1);g_symbols[i].g_lockOwned=false;}delete g_symbols[i];}\n  ArrayResize(g_symbols,0);ReleaseExecution();\n  if(g_propControllerOwned) {GlobalVariableSetOnCondition(g_propControllerKey,0,1);g_propControllerOwned=false;}GlobalVariablesFlush();\n }\n ulong foNow=GetMicrosecondCount();FORecord("DEINIT",_Symbol,0,foNow,foNow,0,0,reason);FOFlush(true);\n}\nvoid FOOriginalOnDeinit(const int reason)\n{'),
        ]
    if name == STATE:
        return [
            ('operations<20000', 'operations<500000'),
            (' if(force) m_mcActive=false;', ' if(force) {FOForce(m_symbol,m_mcActive);m_mcActive=false;}'),
            (' g_mcReady=false;g_mcAllowed=false;g_mcRisk=0;', ' FORequest(m_symbol,force,m_mcActive,g_sampleCount,g_mcReady,g_mcAllowed);FOPriorResult(m_symbol,(long)g_lastMC,MonteCarloRecalculateMinutes);g_mcReady=false;g_mcAllowed=false;g_mcRisk=0;'),
            (' g_historyDirty=false;g_historyOK=true;g_lastHistory=TimeCurrent();', ' g_historyDirty=false;g_historyOK=true;g_lastHistory=TimeCurrent();FOHistory(m_symbol,g_sampleCount,g_winRate);'),
            (' if(ArrayCopy(m_mcReturns,g_returns)!=ArraySize(g_returns) || ArrayResize(m_mcDDs,MonteCarloRuns)!=MonteCarloRuns) return;', ' if(ArrayCopy(m_mcReturns,g_returns)!=ArraySize(g_returns) || ArrayResize(m_mcDDs,MonteCarloRuns)!=MonteCarloRuns) {FOFailure(m_symbol);return;}'),
            (' {g_mcRisk=LimitRisk(BaseRiskPercent);g_mcReady=true;g_mcAllowed=g_mcRisk>0;g_lastMC=TimeCurrent();return;}', ' {g_mcRisk=LimitRisk(BaseRiskPercent);g_mcReady=true;g_mcAllowed=g_mcRisk>0;g_lastMC=TimeCurrent();FOImmediate(m_symbol,1,g_mcRisk,g_mcAllowed);return;}'),
            (' {g_mcReady=true;g_lastMC=TimeCurrent();return;}', ' {g_mcReady=true;g_lastMC=TimeCurrent();FOImmediate(m_symbol,2,g_mcRisk,g_mcAllowed);return;}'),
            (' m_mcActive=true;\n}', ' m_mcActive=true;FOStart(m_symbol,g_sampleCount,m_mcReturns);\n}'),
            ('  double dd=m_mcDDs[(int)MathCeil(0.95*MonteCarloRuns)-1];', '  double dd=m_mcDDs[(int)MathCeil(0.95*MonteCarloRuns)-1];FOLevel(m_symbol,m_mcCandidate,dd,m_mcRandom);'),
            ('void AdvanceMonteCarlo(ulong deadline)\n{', 'void AdvanceMonteCarlo(ulong deadline)\n{\n if(!m_mcActive || g_historyDirty) {FOOriginalAdvanceMonteCarlo(deadline);return;}ulong foStart=GetMicrosecondCount();FOOriginalAdvanceMonteCarlo(deadline);FODuration(m_symbol,0,foStart,GetMicrosecondCount());if(!m_mcActive) FOCycleSummary(m_symbol);\n}\nvoid FOOriginalAdvanceMonteCarlo(ulong deadline)\n{'),
            ('   g_mcAllowed=g_mcRisk>0;g_mcReady=true;g_lastMC=TimeCurrent();m_mcActive=false;', '   g_mcAllowed=g_mcRisk>0;g_mcReady=true;g_lastMC=TimeCurrent();m_mcActive=false;FOOperations(m_symbol,operations);FOComplete(m_symbol,g_mcReady,g_mcAllowed,g_mcRisk,m_mcRandom);'),
            (' }\n}\n\nbool InUniverseNow()', ' }\n FOOperations(m_symbol,operations);\n}\n\nbool InUniverseNow()'),
            ('void ManagePositions()\n{', 'void ManagePositions()\n{\n ulong foStart=GetMicrosecondCount();FOOriginalManagePositions();FODuration(m_symbol,1,foStart,GetMicrosecondCount());\n}\nvoid FOOriginalManagePositions()\n{'),
            ('void Scan()\n{', 'void Scan()\n{\n FOOriginalScan();FOBar(m_symbol,(long)g_lastBarTime);\n}\nvoid FOOriginalScan()\n{'),
            ('  if(!g_mcReady || !g_mcAllowed) {g_status="Monte Carlo blocks entry";return false;}', '  if(!g_mcReady || !g_mcAllowed) {FOMCWait(m_symbol,(long)g_lastBarTime,g_mcReady,g_mcAllowed,m_mcActive);g_status="Monte Carlo blocks entry";return false;}'),
            (' m_candidateSequence=was && previous==bar?sequence:++g_queueSequence;', ' m_candidateSequence=was && previous==bar?sequence:++g_queueSequence;FOCandidate(m_symbol,(long)bar,m_candidateSequence);'),
            (' bool ok=buy?trade.Buy(lot,m_symbol,latest.ask,sl,tp,orderComment):trade.Sell(lot,m_symbol,latest.bid,sl,tp,orderComment);', ' ulong foOrderStart=GetMicrosecondCount();\n bool ok=buy?trade.Buy(lot,m_symbol,latest.ask,sl,tp,orderComment):trade.Sell(lot,m_symbol,latest.bid,sl,tp,orderComment);\n ulong foOrderEnd=GetMicrosecondCount();'),
            (' MqlTradeResult result={};trade.Result(result);uint rc=result.retcode;', ' MqlTradeResult result={};trade.Result(result);uint rc=result.retcode;FOOrder(m_symbol,foOrderStart,foOrderEnd,rc,ok);'),
            ('   bool ok=trade.PositionClose(t,DeviationPoints());', '   ulong foCloseStart=GetMicrosecondCount();bool ok=trade.PositionClose(t,DeviationPoints());ulong foCloseEnd=GetMicrosecondCount();FOPositionOrder(m_symbol,foCloseStart,foCloseEnd,trade.ResultRetcode(),ok,1);'),
            ('  bool ok=trade.PositionModify(t,candidate,tp);', '  ulong foModifyStart=GetMicrosecondCount();bool ok=trade.PositionModify(t,candidate,tp);ulong foModifyEnd=GetMicrosecondCount();FOPositionOrder(m_symbol,foModifyStart,foModifyEnd,trade.ResultRetcode(),ok,2);'),
        ]
    return []


def replace_once(data, old, new):
    old,new=old.encode('utf-8'),new.encode('utf-8')
    if data.count(old)!=1:raise ValueError('canonical transform missing or ambiguous')
    return data.replace(old,new,1)


def restore(name, data):
    for old,new in reversed(substitutions(name)):
        data=replace_once(data,new,old)
    return data


def sha(data):return hashlib.sha256(data).hexdigest()


def build(output, source=SOURCE):
    output,source=Path(output).resolve(),Path(source).resolve()
    if output.exists() or output==source or source in output.parents or output==SOURCE.resolve() or SOURCE.resolve() in output.parents:
        raise ValueError('new destination outside canonical source required')
    original={p.name:p.read_bytes() for p in source.iterdir() if p.suffix in ('.mq5','.mqh')}
    if len(original)!=13 or original[MAIN].count(b'#property version "2.44"')!=1:
        raise ValueError('canonical source contract changed')
    generated={}
    for name,data in original.items():
        for old,new in substitutions(name):data=replace_once(data,old,new)
        if restore(name,data)!=original[name]:raise ValueError('projection is not exact')
        if b'TesterMC' in data or b'TPObserveBeforeSafety' in data:raise ValueError('Tester engine contamination')
        generated[name]=data
    generated[HEADER.name]=HEADER.read_bytes()
    proof=dict(operations_per_callback=500000,product_version='2.44',
        canonical_source_sha256={n:sha(d) for n,d in original.items()},
        generated_source_sha256={n:sha(d) for n,d in generated.items()},
        classification={n:'FORWARD_OBSERVER' if n==HEADER.name else 'PRODUCT_REQUIRED + FORWARD_OBSERVER' if n in (MAIN,STATE) else 'PRODUCT_REQUIRED' for n in generated},
        tester_only_files=[],runtime_started=False,real_account_allowed=False,
        projection='remove named observer substitutions and reverse operation cap -> canonical byte equality',
        arrival_timestamp='UNKNOWN',queue_depth='UNKNOWN',mc_wait_opportunity_causality='UNKNOWN_WITHOUT_OBSERVED_QUALIFICATION',
        builder_sha256=sha(Path(__file__).read_bytes()))
    output.mkdir(parents=True)
    for name,data in generated.items():(output/name).write_bytes(data)
    (output/'forward_source_manifest.json').write_text(json.dumps(proof,indent=2)+'\n',encoding='utf-8')
    return proof


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    result=build(parser.parse_args().output)
    print(json.dumps({'generated_files':len(result['generated_source_sha256']),'operations_per_callback':500000,'runtime_started':False}))

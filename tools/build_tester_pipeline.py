"""Build an instrumented, Tester-only copy of the locked v2.44 EA.

The 13 distributed MQL5 files are read only. Exact, single-use anchors fail closed
if the reviewed entry pipeline changes. No trading input or predicate is changed.
"""

import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "src"
MAIN = "MTFAutoTrader_3Mode_AI_v2_44.mq5"
STATE = "MT3SymbolState.mqh"


def replace_once(data: bytes, old: str, new: str) -> bytes:
    newline = "\r\n" if b"\r\n" in data else "\n"
    old_bytes = old.replace("\n", newline).encode("utf-8")
    new_bytes = new.replace("\n", newline).encode("utf-8")
    if data.count(old_bytes) != 1:
        raise ValueError(f"Tester diagnostic anchor missing or ambiguous: {old[:100]!r}")
    return data.replace(old_bytes, new_bytes, 1)


def instrument_main(data: bytes) -> bytes:
    edits = [
        ('#include "MT3SymbolState.mqh"',
         '#include "TesterPipelineDiag.mqh"\n#include "MT3SymbolState.mqh"'),
        ('void OnTick() {MaintainExposure();}',
         'void OnTick() {TPInc(TP_TICKS);MaintainExposure();}'),
        ('int OnInit()\n{\n g_chartSymbol=_Symbol;',
         'int OnInit()\n{\n if(!MQLInfoInteger(MQL_TESTER)) {Print("Tester diagnostic EA cannot run outside Strategy Tester");return INIT_FAILED;}\n g_chartSymbol=_Symbol;'),
        ('void OnDeinit(const int reason)\n{\n EventKillTimer();',
         'void OnDeinit(const int reason)\n{\n TPPrintSummary(reason);\n EventKillTimer();'),
    ]
    for old, new in edits:
        data = replace_once(data, old, new)
    return data


def instrument_state(data: bytes) -> bytes:
    edits = [
        (' if(handle==INVALID_HANDLE || CopyBuffer(handle,buffer,shift,1,a)!=1 || BarsCalculated(handle)<=shift) return false;',
         ' if(handle==INVALID_HANDLE) {TPReadFailure(0);return false;}\n int copied=CopyBuffer(handle,buffer,shift,1,a);TPCopyBufferResult(copied,GetLastError());\n if(copied!=1) return false;\n int tpCalculated=BarsCalculated(handle);TPBarsCalculated(tpCalculated,shift,GetLastError());\n if(tpCalculated<=shift) return false;'),
        (' if(!MathIsValidNumber(a[0]) || a[0]==EMPTY_VALUE) return false;\n v=a[0]; return true;',
         ' if(!MathIsValidNumber(a[0]) || a[0]==EMPTY_VALUE) {TPReadFailure(3);return false;}\n v=a[0]; return true;'),
        # Indicator failures: observe the original single Bars() call and each
        # existing early return without requesting extra market data.
        (' if(Bars(m_symbol,timeframe)<EMASlowPeriod+EMASlopeBars+10) return false;',
         ' int tpBars=Bars(m_symbol,timeframe);\n if(tpBars<EMASlowPeriod+EMASlopeBars+10) {TPIndicatorFail(timeframe,0,tpBars,EMASlowPeriod+EMASlopeBars+10);return false;}'),
        ('result.bar=iTime(m_symbol,timeframe,0);if(result.bar<=0) return false;',
         'result.bar=iTime(m_symbol,timeframe,0);if(result.bar<=0) {TPIndicatorFail(timeframe,1);return false;}'),
        ('result.previousFast<=0 || result.previousMiddle<=0 || result.previousSlow<=0) return false;',
         'result.previousFast<=0 || result.previousMiddle<=0 || result.previousSlow<=0) {TPIndicatorFail(timeframe,2);TPIndicatorCoreFail(result);return false;}'),
        ('!GetMACDValues(timeframe,1,result.macdMain,result.macdSignal,result.macdHistogram)) return false;',
         '!GetMACDValues(timeframe,1,result.macdMain,result.macdSignal,result.macdHistogram)) {TPIndicatorFail(timeframe,3);return false;}'),
        ('double pm,ps;if(!GetMACDValues(timeframe,2,pm,ps,result.previousHistogram)) return false;',
         'double pm,ps;if(!GetMACDValues(timeframe,2,pm,ps,result.previousHistogram)) {TPIndicatorFail(timeframe,4);return false;}'),
        (' return result.bar==iTime(m_symbol,timeframe,0);',
         ' if(result.bar!=iTime(m_symbol,timeframe,0)) {TPIndicatorFail(timeframe,5);return false;}\n return true;'),
        # Existing preflight reasons are retained verbatim; only the return is counted.
        ('g_status="Symbol outside entry universe";return false;',
         'g_status="Symbol outside entry universe";return TPReject(TP_ENTRY_UNIVERSE);'),
        ('g_status="Account has an unresolved order";return false;',
         'g_status="Account has an unresolved order";return TPReject(TP_SAFETY_ACCOUNT_ORDER);'),
        ('g_status="Selected execution mode does not allow this entry";return false;',
         'g_status="Selected execution mode does not allow this entry";return TPReject(TP_ENTRY_MODE);'),
        ('g_status="ORDER UNRESOLVED | reconcile token "+PendingOrderToken();return false;',
         'g_status="ORDER UNRESOLVED | reconcile token "+PendingOrderToken();return TPReject(TP_SAFETY_SYMBOL_ORDER);'),
        ('g_status="Existing exposure blocks entry";return false;',
         'g_status="Existing exposure blocks entry";return TPReject(TP_SAFETY_POSITION);'),
        ('g_status="Trading permission or broker connection is OFF";return false;',
         'g_status="Trading permission or broker connection is OFF";return TPReject(TP_SAFETY_PERMISSION);'),
        ('g_status="Waiting for trade history";return false;',
         'g_status="Waiting for trade history";return TPReject(TP_SAFETY_HISTORY);'),
        ('g_status="Monte Carlo blocks entry";return false;',
         'g_status="Monte Carlo blocks entry";return TPReject(TP_SAFETY_MC);'),
        ('if(MathMin(risk,PropRiskCap())<=0) {g_status="Risk / loss-streak / DD protection blocked entry";return false;}',
         'if(MathMin(risk,PropRiskCap())<=0) {g_status="Risk / loss-streak / DD protection blocked entry";return TPReject(TP_SAFETY_RISK_CAP);}'),
        # Scan counts available M1 data and a newly observed bar once per symbol.
        (' g_lastBarTime=iTime(m_symbol,PERIOD_M1,0);\n if(ExecutionMode!=EXECUTION_MANUAL) RefreshCandidate();',
         ' datetime tpPreviousBar=g_lastBarTime;\n g_lastBarTime=iTime(m_symbol,PERIOD_M1,0);\n if(g_lastBarTime>0) {TPInc(TP_MARKET_READY);if(g_lastBarTime!=tpPreviousBar) TPInc(TP_NEW_BARS);}\n if(ExecutionMode!=EXECUTION_MANUAL) RefreshCandidate();'),
        # Candidate pipeline. Splits preserve the original left-to-right short circuit.
        (' if(!InUniverseNow() || !EntryPreflight(false) || g_aiRequest.active) return false;',
         ' if(!InUniverseNow()) return TPReject(TP_ENTRY_UNIVERSE);\n if(!EntryPreflight(false)) return false;\n if(g_aiRequest.active) return TPReject(TP_ENTRY_AI_BUSY);'),
        (' if(bar<=0 || bar==g_lastTradeBar || bar==g_lastAttemptBar ||\n    ((ExecutionMode==EXECUTION_AI || ExecutionMode==EXECUTION_HYBRID) && bar==g_aiLastBar)) return false;',
         ' if(bar<=0 || bar==g_lastTradeBar || bar==g_lastAttemptBar ||\n    ((ExecutionMode==EXECUTION_AI || ExecutionMode==EXECUTION_HYBRID) && bar==g_aiLastBar)) return TPReject(TP_ENTRY_COOLDOWN);'),
        ('if(!AnalyzeAllTimeframes(r)) {g_status="Waiting for all 7 timeframe indicators";return false;}',
         'if(!AnalyzeAllTimeframes(r)) {g_status="Waiting for all 7 timeframe indicators";return TPReject(TP_ENTRY_INDICATOR);}\n TPInc(TP_INDICATOR_READY);TPInc(TP_PATTERN_REACHED);'),
        ('  if(!b && !s) return false;\n  buy=b && (!s || bs>=ss);',
         '  if(!b && !s) return TPReject(TP_ENTRY_AGREEMENT);\n  buy=b && (!s || bs>=ss);\n  TPInc(buy?TP_SIGNAL_BUY:TP_SIGNAL_SELL);'),
        ('if(!SelectReversalPattern(r,p)) {g_status="Waiting for fresh neckline breakout";return false;}',
         'if(!SelectReversalPattern(r,p)) {g_status="Waiting for fresh neckline breakout";return TPReject(TP_ENTRY_PATTERN_NONE);}'),
        ('  if(IsPatternAlreadyUsed(p)) return false;',
         '  if(IsPatternAlreadyUsed(p)) return TPReject(TP_ENTRY_PATTERN_USED);'),
        ('if(buy?!BuySignalOK(p,r):!SellSignalOK(p,r)) {g_status="Weighted agreement / strong opposition";return false;}',
         'if(buy?!BuySignalOK(p,r):!SellSignalOK(p,r)) {g_status="Weighted agreement / strong opposition";return TPReject(TP_ENTRY_AGREEMENT);}\n  TPInc(buy?TP_SIGNAL_BUY:TP_SIGNAL_SELL);'),
        ('  if(buy?!IsBuyAllowed():!IsSellAllowed()) return false;',
         '  if(buy?!IsBuyAllowed():!IsSellAllowed()) return TPReject(TP_ENTRY_DIRECTION);'),
        ('if(score<MinimumSignalScore) {g_status=StringFormat("Local score %.1f < %.1f",score,MinimumSignalScore);return false;}',
         'TPScoreObserve(score,MinimumSignalScore,buy?CalculateBuyMTFScore(r):CalculateSellMTFScore(r),GetPatternScore(p),CalculateLineScore(buy?ENTRY_BUY:ENTRY_SELL));\n if(score<MinimumSignalScore) {MqlTick tpScoreTick;if(SymbolInfoTick(m_symbol,tpScoreTick)) TPSpreadObserveSkipped(m_symbol,tpScoreTick,r[0].atr);g_status=StringFormat("Local score %.1f < %.1f",score,MinimumSignalScore);return TPReject(TP_ENTRY_SCORE);}' ),
        (' if(!SymbolDirectionAllowed(buy) || !FreshQuote(tick) || !BuildEntryStops(buy,tick,p,sl,tp,slSource,slFallback) || !SpreadOK(tick,sl,buy) || !PatternEntryLocationOK(p,tick,buy))\n {g_status="Quote / relative cost / stop geometry blocks entry";return false;}',
         ' if(!SymbolDirectionAllowed(buy)) {g_status="Quote / relative cost / stop geometry blocks entry";return TPReject(TP_ENTRY_DIRECTION);}\n if(!FreshQuote(tick)) {g_status="Quote / relative cost / stop geometry blocks entry";return TPReject(TP_ENTRY_QUOTE);}\n if(!BuildEntryStops(buy,tick,p,sl,tp,slSource,slFallback)) {TPSpreadObserveSkipped(m_symbol,tick,r[0].atr,1);g_status="Quote / relative cost / stop geometry blocks entry";return TPReject(TP_ENTRY_STOPS);}\n g_tpSpreadSignalContext=true;bool tpSpreadPass=SpreadOK(tick,sl,buy);g_tpSpreadSignalContext=false;\n if(!tpSpreadPass) {g_status="Quote / relative cost / stop geometry blocks entry";return TPReject(TP_ENTRY_SPREAD);}\n if(!PatternEntryLocationOK(p,tick,buy)) {g_status="Quote / relative cost / stop geometry blocks entry";return TPReject(TP_ENTRY_LOCATION);}' ),
        (' if(bar!=iTime(m_symbol,PERIOD_M1,0) || !MTFSnapshotCurrent()) return false;\n m_candidate=true;',
         ' if(bar!=iTime(m_symbol,PERIOD_M1,0) || !MTFSnapshotCurrent()) return TPReject(TP_ENTRY_SNAPSHOT);\n TPInc(TP_ENTRY_CANDIDATE);\n m_candidate=true;'),
        ('bool SpreadOK(MqlTick &tick,double sl=0,bool buy=true)\n{\n double atr=GetATR(PERIOD_M1,14,1),spread=tick.ask-tick.bid;\n if(atr<=0 || spread<0 || spread>atr*MaxSpreadATR+TickSize()*1e-8) return false;\n if(MaxSpreadPoints>0 && spread>MaxSpreadPoints*m_point) return false;\n if(sl>0)\n {\n  double distance=MathAbs((buy?tick.ask:tick.bid)-sl);\n  if(distance<=0 || spread>distance*MaxSpreadSL+TickSize()*1e-8) return false;\n }\n return true;\n}',
         'bool SpreadOK(MqlTick &tick,double sl=0,bool buy=true)\n{\n double atr=GetATR(PERIOD_M1,14,1),spread=tick.ask-tick.bid;\n if(atr<=0 || spread<0 || spread>atr*MaxSpreadATR+TickSize()*1e-8) {TPSpreadObserveGate(m_symbol,tick,sl,buy,atr,MaxSpreadATR,MaxSpreadPoints,MaxSpreadSL,m_point,1);return false;}\n if(MaxSpreadPoints>0 && spread>MaxSpreadPoints*m_point) {TPSpreadObserveGate(m_symbol,tick,sl,buy,atr,MaxSpreadATR,MaxSpreadPoints,MaxSpreadSL,m_point,2);return false;}\n if(sl>0)\n {\n  double distance=MathAbs((buy?tick.ask:tick.bid)-sl);\n  if(distance<=0 || spread>distance*MaxSpreadSL+TickSize()*1e-8) {TPSpreadObserveGate(m_symbol,tick,sl,buy,atr,MaxSpreadATR,MaxSpreadPoints,MaxSpreadSL,m_point,3);return false;}\n }\n TPSpreadObserveGate(m_symbol,tick,sl,buy,atr,MaxSpreadATR,MaxSpreadPoints,MaxSpreadSL,m_point,0);\n return true;\n}'),
        # Order pipeline. The existing sizing and order checks retain their predicates.
        ('if(!SymbolDirectionAllowed(buy)) {g_status="Symbol trade direction disabled";return false;}',
         'if(!SymbolDirectionAllowed(buy)) {g_status="Symbol trade direction disabled";return TPReject(TP_ENTRY_DIRECTION);}' ),
        ('if(!manual && pattern.valid && IsPatternAlreadyUsed(pattern)) {g_status="Pattern already consumed";return false;}',
         'if(!manual && pattern.valid && IsPatternAlreadyUsed(pattern)) {g_status="Pattern already consumed";return TPReject(TP_ENTRY_PATTERN_USED);}' ),
        (' if(!EntryPreflight(manual) || (buy?!IsBuyAllowed():!IsSellAllowed())) return false;',
         ' if(!EntryPreflight(manual)) return false;\n if(buy?!IsBuyAllowed():!IsSellAllowed()) return TPReject(TP_ENTRY_DIRECTION);'),
        ('{g_status="One entry/attempt per M1 bar; wait for next bar";return false;}',
         '{g_status="One entry/attempt per M1 bar; wait for next bar";return TPReject(TP_ENTRY_COOLDOWN);}' ),
        (' MqlTick tick;if(!FreshQuote(tick)) return false;\n if(!AIExecutionFresh(decisionBar,decisionStarted,referenceEntry,buy,tick))',
         ' MqlTick tick;if(!FreshQuote(tick)) return TPReject(TP_ENTRY_QUOTE);\n if(!AIExecutionFresh(decisionBar,decisionStarted,referenceEntry,buy,tick))'),
        ('if(!AIExecutionFresh(decisionBar,decisionStarted,referenceEntry,buy,tick)) {g_status="AI decision expired before sizing";return false;}',
         'if(!AIExecutionFresh(decisionBar,decisionStarted,referenceEntry,buy,tick)) {g_status="AI decision expired before sizing";return TPReject(TP_ENTRY_AI_FRESHNESS);}' ),
        ('if(!SpreadOK(tick) || !PatternEntryLocationOK(pattern,tick,buy)) {g_status="Spread / pattern price invalid";return false;}',
         'if(!SpreadOK(tick)) {g_status="Spread / pattern price invalid";return TPReject(TP_ENTRY_SPREAD);}\n if(!PatternEntryLocationOK(pattern,tick,buy)) {g_status="Spread / pattern price invalid";return TPReject(TP_ENTRY_LOCATION);}' ),
        (' double risk=manual?CalculateManualRisk():CalculateFinalRisk(score);',
         ' TPInc(TP_RISK_REACHED);\n double risk=manual?CalculateManualRisk():CalculateFinalRisk(score);'),
        ('if(risk<=0) {g_status="Risk / loss-streak / DD protection blocked entry";return false;}',
         'if(risk<=0) {g_status="Risk / loss-streak / DD protection blocked entry";TPInc(TP_RISK_FAILED);return TPReject(TP_SAFETY_RISK_CAP);}' ),
        ('if(lot<=0) {g_status="Lot below minimum or insufficient margin";return false;}',
         'if(lot<=0) {g_status="Lot below minimum or insufficient margin";TPInc(TP_RISK_FAILED);return TPReject(TP_SAFETY_OTHER);}' ),
        ('if(!stopsOK) {g_status="SL is on wrong side, too close, or invalid";return false;}',
         'if(!stopsOK) {g_status="SL is on wrong side, too close, or invalid";return TPReject(TP_ENTRY_STOPS);}' ),
        ('if(EnablePortfolioRiskLimit && !ManagedPortfolioRisk(portfolioBefore,portfolioReason)) {ReportPortfolioReject(portfolioReason);return false;}',
         'if(EnablePortfolioRiskLimit && !ManagedPortfolioRisk(portfolioBefore,portfolioReason)) {ReportPortfolioReject(portfolioReason);return TPReject(TP_SAFETY_PORTFOLIO);}' ),
        (' if(!CheckPortfolioEntry(buy,tick,sl,lot,portfolioBefore,plannedRisk)) return false;',
         ' if(!CheckPortfolioEntry(buy,tick,sl,lot,portfolioBefore,plannedRisk)) return TPReject(TP_SAFETY_PORTFOLIO);'),
        (' if(!OrderCheck(req,check)) {g_status="OrderCheck: "+check.comment;Print(g_status);return false;}',
         ' TPInc(TP_ORDER_VALIDATION);\n if(!OrderCheck(req,check)) {g_status="OrderCheck: "+check.comment;Print(g_status);return TPReject(TP_ENTRY_ORDER_CHECK);}' ),
        (' MqlTick latest;if(!FreshQuote(latest) || !AIExecutionFresh(decisionBar,decisionStarted,referenceEntry,buy,latest))\n {g_status="AI decision expired during order preparation";return false;}',
         ' MqlTick latest;if(!FreshQuote(latest)) {g_status="AI decision expired during order preparation";return TPReject(TP_ENTRY_QUOTE);}\n if(!AIExecutionFresh(decisionBar,decisionStarted,referenceEntry,buy,latest)) {g_status="AI decision expired during order preparation";return TPReject(TP_ENTRY_AI_FRESHNESS);}' ),
        (' if(bar!=iTime(m_symbol,PERIOD_M1,0) || !SpreadOK(latest,sl,buy)) return false;',
         ' if(bar!=iTime(m_symbol,PERIOD_M1,0)) return TPReject(TP_ENTRY_SNAPSHOT);\n if(!SpreadOK(latest,sl,buy)) return TPReject(TP_ENTRY_SPREAD);'),
        ('{g_status="Quote moved beyond sizing reserve during preparation";return false;}',
         '{g_status="Quote moved beyond sizing reserve during preparation";return TPReject(TP_ENTRY_PRICE_DRIFT);}' ),
        ('if(!BeginPendingOrder()) {g_status="Could not persist order intent / previous order unresolved";return false;}',
         'if(!BeginPendingOrder()) {g_status="Could not persist order intent / previous order unresolved";return TPReject(TP_SAFETY_INTENT);}' ),
        ('if(GlobalVariableSet(g_statePrefix+"attempt.bar",(double)bar)==0) {ClearPendingOrder();return false;}',
         'if(GlobalVariableSet(g_statePrefix+"attempt.bar",(double)bar)==0) {ClearPendingOrder();return TPReject(TP_SAFETY_PERSISTENCE);}' ),
        ('if(!manual && !PersistPatternClaims(pattern)) {ClearPendingOrder();g_status="Pattern receipt persistence failed";return false;}',
         'if(!manual && !PersistPatternClaims(pattern)) {ClearPendingOrder();g_status="Pattern receipt persistence failed";return TPReject(TP_SAFETY_PERSISTENCE);}' ),
        ('if(!CheckPortfolioEntry(buy,tick,sl,lot,portfolioBefore,plannedRisk)) {ClearPendingOrder();return false;}',
         'if(!CheckPortfolioEntry(buy,tick,sl,lot,portfolioBefore,plannedRisk)) {ClearPendingOrder();return TPReject(TP_SAFETY_PORTFOLIO);}' ),
        (' if(!FreshQuote(latest) || !PatternEntryLocationOK(pattern,latest,buy) || bar!=iTime(m_symbol,PERIOD_M1,0) || !AIExecutionFresh(decisionBar,decisionStarted,referenceEntry,buy,latest) ||\n    !SpreadOK(latest,sl,buy) || MathAbs((buy?latest.ask:latest.bid)-(buy?tick.ask:tick.bid))>req.deviation*m_point+m_point*1e-8)\n {ClearPendingOrder();g_status="Decision / quote changed before send";return false;}',
         ' int tpLastReason=-1;\n if(!FreshQuote(latest)) tpLastReason=TP_ENTRY_QUOTE;\n else if(!PatternEntryLocationOK(pattern,latest,buy)) tpLastReason=TP_ENTRY_LOCATION;\n else if(bar!=iTime(m_symbol,PERIOD_M1,0)) tpLastReason=TP_ENTRY_SNAPSHOT;\n else if(!AIExecutionFresh(decisionBar,decisionStarted,referenceEntry,buy,latest)) tpLastReason=TP_ENTRY_AI_FRESHNESS;\n else if(!SpreadOK(latest,sl,buy)) tpLastReason=TP_ENTRY_SPREAD;\n else if(MathAbs((buy?latest.ask:latest.bid)-(buy?tick.ask:tick.bid))>req.deviation*m_point+m_point*1e-8) tpLastReason=TP_ENTRY_PRICE_DRIFT;\n if(tpLastReason>=0) {ClearPendingOrder();g_status="Decision / quote changed before send";return TPReject(tpLastReason);}' ),
        ('{ClearPendingOrder();g_status="Stops invalid at latest quote";return false;}',
         '{ClearPendingOrder();g_status="Stops invalid at latest quote";return TPReject(TP_ENTRY_STOPS);}' ),
        (' bool ok=buy?trade.Buy(lot,m_symbol,latest.ask,sl,tp,orderComment):trade.Sell(lot,m_symbol,latest.bid,sl,tp,orderComment);',
         ' TPInc(TP_ORDER_REQUESTS);\n bool ok=buy?trade.Buy(lot,m_symbol,latest.ask,sl,tp,orderComment):trade.Sell(lot,m_symbol,latest.bid,sl,tp,orderComment);'),
        ('  Print(g_status);return false;\n }\n RecordEntryAttempt(manual,pattern);g_historyDirty=true;',
         '  TPInc(TP_ORDER_FAILED);Print(g_status);return false;\n }\n TPInc(TP_ORDER_SUCCEEDED);TPAcceptedOrderSpread(latest,m_point);\n RecordEntryAttempt(manual,pattern);g_historyDirty=true;'),
    ]
    for old, new in edits:
        data = replace_once(data, old, new)
    return data


def add_opportunity_observer(staged: dict[str, bytes]) -> None:
    """Add a separate read-only observer; keep the actual preflight early return."""
    main = staged[MAIN]
    main = replace_once(main, ' g_chartSymbol=_Symbol;',
                        ' if(!TPOSelfTest()) return INIT_FAILED;\n g_chartSymbol=_Symbol;')
    main = replace_once(main, 'TPInc(TP_TICKS);MaintainExposure();',
                        'TPInc(TP_TICKS);TPORecordTick();MaintainExposure();')
    main = replace_once(main, ' TPPrintSummary(reason);',
                        ' TPPrintSummary(reason);TPOPrintSummary();')
    staged[MAIN] = main
    state = staged[STATE]
    state = replace_once(state, 'CTrade trade;', 'CTrade trade;\nSymbolState *m_tpObserver;')
    state = replace_once(state, 'SymbolState()\n{', 'SymbolState()\n{\nm_tpObserver=NULL;')
    state = replace_once(state, ' if(!EntryPreflight(false)) return false;',
                        ' g_tpLastReject=-1;bool tpAllowed=EntryPreflight(false);\n int tpSafetyReason=g_tpLastReject;\n TPObserveBeforeSafety(tpAllowed,tpSafetyReason);\n if(!tpAllowed) return false;')
    state = replace_once(state, 'void ReleaseIndicators()\n{',
                        'void ReleaseIndicators()\n{\n if(m_tpObserver!=NULL) {m_tpObserver.ReleaseIndicators();delete m_tpObserver;m_tpObserver=NULL;}')
    state = replace_once(state, ' if(!AcquireExecution()) {g_status="Account execution busy";return false;}',
                        ' g_tpOrderOpportunity=TPOFind(m_symbol,iTime(m_symbol,PERIOD_M1,0),PatternIdentity(pattern),buy,false);\n if(g_tpOrderOpportunity<0) g_tpoUnknown++;\n if(!AcquireExecution()) {TPOReason(g_tpOrderOpportunity,TP_ENTRY_OTHER,false,true);g_tpOrderOpportunity=-1;g_status="Account execution busy";return false;}')
    state = replace_once(state, ' ReleaseExecution();return ok;',
                        ' ReleaseExecution();g_tpOrderOpportunity=-1;return ok;')
    state = replace_once(state, 'if(lot<=0) {g_status="Lot below minimum or insufficient margin";TPInc(TP_RISK_FAILED);return TPReject(TP_SAFETY_OTHER);}',
                        'if(lot<=0) {g_status="Lot below minimum or insufficient margin";TPInc(TP_RISK_FAILED);return TPReject(TP_SAFETY_OTHER);}\n TPOStage(g_tpOrderOpportunity,TPO_RISK_PASS);')
    state = replace_once(state, '#include "MT3ReversalPatterns.mqh"',
                        '#include "TesterOpportunityMethods.mqh"\n#include "MT3ReversalPatterns.mqh"')
    staged[STATE] = state
    staged['MT3PatternStops.mqh'] = replace_once(staged['MT3PatternStops.mqh'],
        '  Print("SL fallback ",m_symbol," ",PatternName(p.type),": ",fallback);',
        '  if(!g_tpShadow) Print("SL fallback ",m_symbol," ",PatternName(p.type),": ",fallback);')
    diag = staged['TesterPipelineDiag.mqh']
    diag = replace_once(diag, 'ulong g_tpCounters[TP_COUNT];',
                        '#include "TesterOpportunityDiag.mqh"\nulong g_tpCounters[TP_COUNT];')
    diag = diag.replace(b'if(!MQLInfoInteger(MQL_TESTER)) return;',
                        b'if(!MQLInfoInteger(MQL_TESTER) || g_tpShadow) return;')
    diag = replace_once(diag,
        ' if(MQLInfoInteger(MQL_TESTER) && counter>=0 && counter<TP_COUNT) g_tpCounters[counter]++;',
        ' if(!g_tpShadow && MQLInfoInteger(MQL_TESTER) && counter>=0 && counter<TP_COUNT) {g_tpCounters[counter]++;TPOActual(counter);}')
    diag = replace_once(diag, ' TPInc(reason);\n return false;',
                        ' if(!g_tpShadow) {g_tpLastReject=reason;TPORejectTick(reason);TPOReason(g_tpOrderOpportunity,reason,false,true);}\n TPInc(reason);\n return false;')
    staged['TesterPipelineDiag.mqh'] = diag
    for name in ('TesterOpportunityDiag.mqh', 'TesterOpportunityMethods.mqh'):
        staged[name] = (ROOT / 'tools' / name).read_bytes()


def build(output: Path, *, opportunity: bool = False) -> Path:
    output = output.resolve()
    if output == SOURCE.resolve() or SOURCE.resolve() in output.parents:
        raise ValueError("Diagnostic output must not overwrite the canonical source")
    if output.exists():
        raise ValueError(f"Diagnostic output already exists: {output}")
    originals = {p.name: p.read_bytes() for p in SOURCE.iterdir()
                 if p.is_file() and p.suffix in (".mq5", ".mqh")}
    if len(originals) != 13 or MAIN not in originals or STATE not in originals:
        raise ValueError("Unexpected canonical MQL5 distribution")
    staged = dict(originals)
    staged[MAIN] = instrument_main(originals[MAIN])
    staged[STATE] = instrument_state(originals[STATE])
    staged["TesterPipelineDiag.mqh"] = (ROOT / "tools" / "TesterPipelineDiag.mqh").read_bytes()
    staged["TesterSignalDiag.mqh"] = (ROOT / "tools" / "TesterSignalDiag.mqh").read_bytes()
    if opportunity:
        add_opportunity_observer(staged)
    output.mkdir(parents=True)
    for name, content in staged.items():
        (output / name).write_bytes(content)
    return output / MAIN


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--opportunity", action="store_true", help="Add independent, read-only opportunity diagnostics")
    args = parser.parse_args()
    print(build(args.output, opportunity=args.opportunity))

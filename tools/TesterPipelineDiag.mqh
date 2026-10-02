// Generated Tester EA only. Never include this file in the distributed EA.
#include "TesterSignalDiag.mqh"
enum TesterPipelineCounter
{
 TP_TICKS, TP_NEW_BARS, TP_MARKET_READY, TP_INDICATOR_READY,
 TP_PATTERN_REACHED, TP_SIGNAL_BUY, TP_SIGNAL_SELL, TP_ENTRY_CANDIDATE,
 TP_RISK_REACHED, TP_RISK_FAILED, TP_ORDER_VALIDATION, TP_ORDER_REQUESTS,
 TP_ORDER_SUCCEEDED, TP_ORDER_FAILED,
 TP_ENTRY_UNIVERSE, TP_ENTRY_MODE, TP_ENTRY_AI_BUSY, TP_ENTRY_COOLDOWN,
 TP_ENTRY_INDICATOR, TP_ENTRY_PATTERN_NONE, TP_ENTRY_PATTERN_USED,
 TP_ENTRY_AGREEMENT, TP_ENTRY_DIRECTION, TP_ENTRY_SCORE,
 TP_ENTRY_QUOTE, TP_ENTRY_STOPS, TP_ENTRY_SPREAD, TP_ENTRY_LOCATION,
 TP_ENTRY_SNAPSHOT, TP_ENTRY_AI_FRESHNESS, TP_ENTRY_PRICE_DRIFT,
 TP_ENTRY_ORDER_CHECK, TP_ENTRY_OTHER,
 TP_SAFETY_ACCOUNT_ORDER, TP_SAFETY_SYMBOL_ORDER, TP_SAFETY_POSITION,
 TP_SAFETY_PERMISSION, TP_SAFETY_HISTORY, TP_SAFETY_MC, TP_SAFETY_RISK_CAP,
 TP_SAFETY_PORTFOLIO, TP_SAFETY_INTENT, TP_SAFETY_PERSISTENCE,
 TP_SAFETY_OTHER, TP_COUNT
};
ulong g_tpCounters[TP_COUNT];
ulong g_tpIndicatorFailByTF[7];
ulong g_tpIndicatorFailByCause[7];
string g_tpFirstIndicatorTF="none",g_tpFirstIndicatorCause="none";
int g_tpFirstBars=-1,g_tpRequiredBars=-1;
ulong g_tpCoreZero[8];
ulong g_tpReadFailure[4];
int g_tpFirstCalculated=2147483647,g_tpLastCalculated=2147483647;
int g_tpFirstReadError=-1,g_tpLastReadError=-1;
ulong g_tpBarsCalculatedCalls=0,g_tpBarsCalculatedMinusOne=0,g_tpBarsCalculatedReady=0;
ulong g_tpCopyBufferCalls=0,g_tpCopyBufferOK=0,g_tpCopyBufferFail=0;
ulong g_tpAcceptedSpreadCount=0,g_tpAcceptedSpreadInvalid=0;
double g_tpAcceptedSpreadPointsSum=0;
void TPAcceptedOrderSpread(MqlTick &tick,const double point)
{
 if(!MQLInfoInteger(MQL_TESTER)) return;
 double spread=tick.ask-tick.bid;
 if(point<=0 || !MathIsValidNumber(spread) || spread<0)
 {g_tpAcceptedSpreadInvalid++;return;}
 g_tpAcceptedSpreadPointsSum+=spread/point;
 g_tpAcceptedSpreadCount++;
}
void TPReadFailure(const int cause,const int calculated=2147483647,const int error=-1)
{
 if(!MQLInfoInteger(MQL_TESTER)) return;
 if(cause>=0 && cause<4) g_tpReadFailure[cause]++;
 if(g_tpFirstCalculated==2147483647 && calculated!=2147483647) g_tpFirstCalculated=calculated;
 if(calculated!=2147483647) g_tpLastCalculated=calculated;
 if(g_tpFirstReadError<0 && error>=0) g_tpFirstReadError=error;
 if(error>=0) g_tpLastReadError=error;
}
void TPBarsCalculated(const int calculated,const int shift,const int error)
{
 if(!MQLInfoInteger(MQL_TESTER)) return;
 g_tpBarsCalculatedCalls++;
 if(g_tpFirstCalculated==2147483647) g_tpFirstCalculated=calculated;
 g_tpLastCalculated=calculated;
 if(calculated==-1) g_tpBarsCalculatedMinusOne++;
 if(calculated>shift) g_tpBarsCalculatedReady++;
 else TPReadFailure(1,calculated,error);
}
void TPCopyBufferResult(const int copied,const int error)
{
 if(!MQLInfoInteger(MQL_TESTER)) return;
 g_tpCopyBufferCalls++;
 if(copied==1) g_tpCopyBufferOK++;
 else {g_tpCopyBufferFail++;TPReadFailure(2,2147483647,error);}
}

int TPTFIndex(const ENUM_TIMEFRAMES tf)
{
 switch(tf) {case PERIOD_M1:return 0;case PERIOD_M5:return 1;case PERIOD_M15:return 2;
 case PERIOD_M30:return 3;case PERIOD_H1:return 4;case PERIOD_H4:return 5;case PERIOD_D1:return 6;}
 return -1;
}
void TPIndicatorFail(const ENUM_TIMEFRAMES tf,const int cause,const int bars=-1,const int required=-1)
{
 if(!MQLInfoInteger(MQL_TESTER)) return;
 int i=TPTFIndex(tf);
 if(i>=0) g_tpIndicatorFailByTF[i]++;
 if(cause>=0 && cause<7) g_tpIndicatorFailByCause[cause]++;
 if(g_tpFirstIndicatorCause=="none")
 {
  string causes[7]={"bars","bar_time","core_values","adx_macd","previous_macd","snapshot","unknown"};
  g_tpFirstIndicatorTF=EnumToString(tf);
  g_tpFirstIndicatorCause=causes[cause>=0 && cause<7?cause:6];
  g_tpFirstBars=bars;g_tpRequiredBars=required;
 }
}
void TPIndicatorCoreFail(MTFResult &r)
{
 if(!MQLInfoInteger(MQL_TESTER)) return;
 if(r.atr<=0) g_tpCoreZero[0]++;
 if(r.close<=0) g_tpCoreZero[1]++;
 if(r.emaFast<=0) g_tpCoreZero[2]++;
 if(r.emaMiddle<=0) g_tpCoreZero[3]++;
 if(r.emaSlow<=0) g_tpCoreZero[4]++;
 if(r.previousFast<=0) g_tpCoreZero[5]++;
 if(r.previousMiddle<=0) g_tpCoreZero[6]++;
 if(r.previousSlow<=0) g_tpCoreZero[7]++;
}

void TPInc(const int counter)
{
 if(MQLInfoInteger(MQL_TESTER) && counter>=0 && counter<TP_COUNT) g_tpCounters[counter]++;
}
bool TPReject(const int reason)
{
 TPInc(reason);
 return false;
}
void TPField(string &summary,const string name,const int counter)
{
 summary+=StringFormat(" %s=%I64u",name,g_tpCounters[counter]);
}
void TPReasonField(string &summary,const string name,const int counter)
{
 if(g_tpCounters[counter]>0) TPField(summary,name,counter);
}
void TPPrintSummary(const int deinitReason)
{
 if(!MQLInfoInteger(MQL_TESTER)) return;
 string summary=StringFormat("TESTER_PIPELINE_SUMMARY deinit_reason=%d",deinitReason);
 TPField(summary,"ticks",TP_TICKS);
 TPField(summary,"new_bars",TP_NEW_BARS);
 TPField(summary,"market_ready",TP_MARKET_READY);
 TPField(summary,"indicator_ready",TP_INDICATOR_READY);
 TPField(summary,"pattern_reached",TP_PATTERN_REACHED);
 TPField(summary,"signal_buy",TP_SIGNAL_BUY);
 TPField(summary,"signal_sell",TP_SIGNAL_SELL);
 TPField(summary,"entry_candidate",TP_ENTRY_CANDIDATE);
 TPField(summary,"risk_reached",TP_RISK_REACHED);
 TPField(summary,"risk_failed",TP_RISK_FAILED);
 TPField(summary,"order_validation",TP_ORDER_VALIDATION);
 TPField(summary,"order_requests",TP_ORDER_REQUESTS);
 TPField(summary,"orders_sent",TP_ORDER_SUCCEEDED);
 TPField(summary,"orders_failed",TP_ORDER_FAILED);
 TPReasonField(summary,"entry_blocked_universe",TP_ENTRY_UNIVERSE);
 TPReasonField(summary,"entry_blocked_mode",TP_ENTRY_MODE);
 TPReasonField(summary,"entry_blocked_ai_busy",TP_ENTRY_AI_BUSY);
 TPReasonField(summary,"cooldown_reject",TP_ENTRY_COOLDOWN);
 TPReasonField(summary,"entry_blocked_indicator",TP_ENTRY_INDICATOR);
 TPReasonField(summary,"entry_blocked_pattern_none",TP_ENTRY_PATTERN_NONE);
 TPReasonField(summary,"entry_blocked_pattern_used",TP_ENTRY_PATTERN_USED);
 TPReasonField(summary,"entry_blocked_agreement",TP_ENTRY_AGREEMENT);
 TPReasonField(summary,"entry_blocked_direction",TP_ENTRY_DIRECTION);
 TPReasonField(summary,"entry_blocked_score",TP_ENTRY_SCORE);
 TPReasonField(summary,"entry_blocked_quote",TP_ENTRY_QUOTE);
 TPReasonField(summary,"entry_blocked_stops",TP_ENTRY_STOPS);
 TPReasonField(summary,"spread_reject",TP_ENTRY_SPREAD);
 TPReasonField(summary,"entry_blocked_location",TP_ENTRY_LOCATION);
 TPReasonField(summary,"entry_blocked_snapshot",TP_ENTRY_SNAPSHOT);
 TPReasonField(summary,"entry_blocked_ai_freshness",TP_ENTRY_AI_FRESHNESS);
 TPReasonField(summary,"entry_blocked_price_drift",TP_ENTRY_PRICE_DRIFT);
 TPReasonField(summary,"entry_blocked_order_check",TP_ENTRY_ORDER_CHECK);
 TPReasonField(summary,"entry_blocked_other",TP_ENTRY_OTHER);
 TPReasonField(summary,"safety_blocked_account_order",TP_SAFETY_ACCOUNT_ORDER);
 TPReasonField(summary,"safety_blocked_symbol_order",TP_SAFETY_SYMBOL_ORDER);
 TPReasonField(summary,"position_exists_reject",TP_SAFETY_POSITION);
 TPReasonField(summary,"safety_blocked_permission",TP_SAFETY_PERMISSION);
 TPReasonField(summary,"safety_blocked_history",TP_SAFETY_HISTORY);
 TPReasonField(summary,"safety_blocked_monte_carlo",TP_SAFETY_MC);
 TPReasonField(summary,"safety_blocked_risk_cap",TP_SAFETY_RISK_CAP);
 TPReasonField(summary,"safety_blocked_portfolio",TP_SAFETY_PORTFOLIO);
 TPReasonField(summary,"safety_blocked_intent",TP_SAFETY_INTENT);
 TPReasonField(summary,"safety_blocked_persistence",TP_SAFETY_PERSISTENCE);
 TPReasonField(summary,"safety_blocked_other",TP_SAFETY_OTHER);
 summary+=" trading_hours_reject=0 trading_hours_filter=absent";
 Print(summary);
 Print(StringFormat("TESTER_ORDER_SPREAD accepted_n=%I64u average_points=%.6f invalid=%I64u",
  g_tpAcceptedSpreadCount,g_tpAcceptedSpreadCount>0?g_tpAcceptedSpreadPointsSum/g_tpAcceptedSpreadCount:0.0,
  g_tpAcceptedSpreadInvalid));
 string indicator=StringFormat("TESTER_INDICATOR_SUMMARY bars_calculated_calls=%I64u bars_calculated_minus1=%I64u bars_calculated_ready=%I64u copybuffer_calls=%I64u copybuffer_ok=%I64u copybuffer_fail=%I64u first_failure_tf=%s first_failure_cause=%s first_bars=%d required_bars=%d",
  g_tpBarsCalculatedCalls,g_tpBarsCalculatedMinusOne,g_tpBarsCalculatedReady,g_tpCopyBufferCalls,g_tpCopyBufferOK,g_tpCopyBufferFail,
  g_tpFirstIndicatorTF,g_tpFirstIndicatorCause,g_tpFirstBars,g_tpRequiredBars);
 for(int i=0;i<7;i++) if(g_tpIndicatorFailByTF[i]>0) indicator+=StringFormat(" tf%d_fail=%I64u",i,g_tpIndicatorFailByTF[i]);
 for(int i=0;i<7;i++) if(g_tpIndicatorFailByCause[i]>0) indicator+=StringFormat(" cause%d=%I64u",i,g_tpIndicatorFailByCause[i]);
 string coreNames[8]={"atr","close","ema_fast","ema_middle","ema_slow","previous_fast","previous_middle","previous_slow"};
 for(int i=0;i<8;i++) if(g_tpCoreZero[i]>0) indicator+=StringFormat(" core_zero_%s=%I64u",coreNames[i],g_tpCoreZero[i]);
 string readNames[4]={"invalid_handle","bars_not_calculated","copybuffer_failed","invalid_value"};
 for(int i=0;i<4;i++) if(g_tpReadFailure[i]>0) indicator+=StringFormat(" read_%s=%I64u",readNames[i],g_tpReadFailure[i]);
 if(g_tpFirstCalculated!=2147483647) indicator+=StringFormat(" first_bars_calculated=%d last_bars_calculated=%d",g_tpFirstCalculated,g_tpLastCalculated);
 if(g_tpFirstReadError>=0) indicator+=StringFormat(" first_read_error=%d last_read_error=%d",g_tpFirstReadError,g_tpLastReadError);
 Print(indicator);
 TPPrintSignalSummary();
}

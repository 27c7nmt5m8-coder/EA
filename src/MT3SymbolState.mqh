#ifndef MT3_SYMBOL_STATE_MQH
#define MT3_SYMBOL_STATE_MQH
class SymbolState
{
public:
CTrade trade;
ThemePropertySnapshot g_themeProperties[];
bool g_themeShiftSaved;
double g_themeShiftBefore;
bool g_manualBusy;
ulong g_manualLastClick;
datetime g_manualAnalysisBar;
string g_manualMessage;
string g_manualAnalysis;
string g_aiLastDecision;
datetime g_aiLastBar;
datetime g_lastBarTime;
datetime g_lastTradeBar;
int g_consecutiveLosses;
int g_consecutiveWins;
double g_currentRiskPercent;
IndicatorSlot g_indicators[];
string g_statePrefix;
string g_propPrefix;
string g_lockKey;
bool g_lockOwned;
bool g_historyDirty;
bool g_historyOK;
bool g_mcAllowed;
bool g_mcReady;
double g_mcRisk;
double g_winRate;
double g_dailyReference;
int g_sampleCount;
int g_propDay;
int g_propStop;
datetime g_lastMC;
datetime g_lastHistory;
datetime g_lastAttemptBar;
datetime g_lastLineBar;
datetime g_lastObservedUTC;
double g_lastObservedEquity;
double g_lastObservedBalance;
double g_returns[];
string g_status;
string m_lastTesterDiagnosticStatus;
int m_testerDiagnosticCount;
// Tester AUTO diagnostics only; no persistence and no decision inputs.
bool m_diagActive,m_diagCandidate,m_diagFinished,m_diagQueued;
string m_diagReason;
int m_diagEvaluations,m_diagCandidates,m_diagRejections,m_diagQueuePasses;
int m_diagAttempts,m_diagAccepted,m_diagOrderRejected,m_diagCost,m_diagDropped;
string m_diagKeys[];
int m_diagCounts[];
string LINE_PREFIX;
PendingAIDecision g_aiRequest;
ulong g_aiLastTry;
ulong g_lastSymbolTickMs;
string m_symbol;
double m_point;
int m_digits;
bool m_isChart;
bool m_scanEnabled;
bool m_wanted;
bool m_candidate;
bool m_candidateBuy;
bool m_quoteSeen;
double m_candidateScore;
datetime m_candidateBar;
datetime m_lastCloseAttempt;
ulong m_candidateSequence;
long m_quoteTimeMsc;
PatternSignal m_candidatePattern;
MTFResult m_mtf[];
VirtualLevel m_levels[];
VirtualTrend m_trends[2];
bool m_mcActive;
double m_mcReturns[];
double m_mcDDs[];
int m_mcCandidate;
int m_mcRun;
int m_mcTrade;
uint m_mcRandom;
double m_mcEquity;
double m_mcPeak;
double m_mcDD;
datetime m_lastSLFallbackBar,m_lastPortfolioRejectBar,m_lastLogWarning,m_lastJournalAt,m_journalFrom;
string m_lastSLFallbackReason,m_logPendingToken,m_entryAIResult;
double m_portfolioRejects,m_entryAIConfidence;
bool m_portfolioReportDirty,m_journalDirty,m_entryAIUsed;
TradeLogRecord m_logPending;
TradeLogRecord m_journal[];
SymbolState()
{
m_lastSLFallbackBar=0;m_lastPortfolioRejectBar=0;m_lastLogWarning=0;m_lastJournalAt=0;m_journalFrom=0;
m_lastSLFallbackReason="";m_logPendingToken="";m_entryAIResult="";m_portfolioRejects=0;m_entryAIConfidence=-1;
m_portfolioReportDirty=false;m_journalDirty=true;m_entryAIUsed=false;ZeroMemory(m_logPending);
g_themeShiftSaved=false;
g_themeShiftBefore=0;
g_manualBusy=false;
g_manualLastClick=0;
g_manualAnalysisBar=0;
g_manualMessage="";
g_manualAnalysis="Analysis loading";
g_aiLastDecision="AI idle";
g_aiLastBar=0;
g_lastBarTime=0;
g_lastTradeBar=0;
g_consecutiveLosses=0;
g_consecutiveWins=0;
g_currentRiskPercent=0.0;
g_statePrefix="";
g_propPrefix="";
g_lockKey="";
g_lockOwned=false;
g_historyDirty=true;
g_historyOK=false;
g_mcAllowed=true;
g_mcReady=false;
g_mcRisk=0;
g_winRate=0;
g_dailyReference=0;
g_sampleCount=0;
g_propDay=0;
g_propStop=0;
g_lastMC=0;
g_lastHistory=0;
g_lastAttemptBar=0;
g_lastLineBar=0;
g_lastObservedUTC=0;
g_lastObservedEquity=0;
g_lastObservedBalance=0;
g_status="Starting";
m_lastTesterDiagnosticStatus="";
m_testerDiagnosticCount=0;
m_diagActive=false;m_diagCandidate=false;m_diagFinished=false;m_diagQueued=false;m_diagReason="";
m_diagEvaluations=0;m_diagCandidates=0;m_diagRejections=0;m_diagQueuePasses=0;
m_diagAttempts=0;m_diagAccepted=0;m_diagOrderRejected=0;m_diagCost=0;m_diagDropped=0;
LINE_PREFIX="MTFAUTO_";
ZeroMemory(g_aiRequest);
g_aiLastTry=0;
g_lastSymbolTickMs=0;
m_symbol="";
m_point=0;
m_digits=0;
m_isChart=false;
m_scanEnabled=false;
m_wanted=false;
m_candidate=false;
m_candidateBuy=false;
m_quoteSeen=false;
m_candidateScore=0;
m_candidateBar=0;
m_lastCloseAttempt=0;
m_candidateSequence=0;
m_quoteTimeMsc=0;
ZeroMemory(m_candidatePattern);
m_mcActive=false;
m_mcCandidate=0;
m_mcRun=0;
m_mcTrade=0;
m_mcRandom=1;
m_mcEquity=100;
m_mcPeak=100;
m_mcDD=0;
int allocated=ArrayResize(m_mtf,7);for(int i=0;i<allocated;i++) ZeroMemory(m_mtf[i]);
for(int i=0;i<2;i++) ZeroMemory(m_trends[i]);
}

// An assessment after pattern selection is a candidate. Queue revalidation
// reuses it; a fresh scan after a terminal rejection is a new assessment.
void DiagBegin(bool reuse=false)
{
 m_diagActive=MQLInfoInteger(MQL_TESTER) && ExecutionMode==EXECUTION_AUTO;
 if(!m_diagActive) return;
 m_diagEvaluations++;m_diagCandidate=reuse;m_diagFinished=false;m_diagQueued=reuse;m_diagReason="";
}
void DiagReuse(bool reuse)
{if(m_diagActive) {m_diagCandidate=reuse;m_diagQueued=reuse;}}
void DiagCandidate()
{if(m_diagActive && !m_diagCandidate) {m_diagCandidate=true;m_diagCandidates++;}}
bool DiagReject(bool rejected,string reason)
{if(m_diagActive && rejected && m_diagReason=="") m_diagReason=reason;return rejected;}
bool DiagPass(bool passed,string reason)
{DiagReject(!passed,reason);return passed;}
void DiagCount(string key)
{
 for(int i=0;i<ArraySize(m_diagKeys);i++) if(m_diagKeys[i]==key) {m_diagCounts[i]++;return;}
 int n=ArraySize(m_diagKeys);
 if(ArrayResize(m_diagCounts,n+1)!=n+1 || ArrayResize(m_diagKeys,n+1)!=n+1) {m_diagDropped++;return;}
 m_diagKeys[n]=key;m_diagCounts[n]=1;
 PrintFormat("[MT3 ENTRY FIRST] symbol=%s candidate_id=%d key=%s",m_symbol,m_diagCandidate?m_diagCandidates:0,key);
}
bool DiagEnd(bool passed,string gate)
{
 if(!m_diagActive || m_diagFinished) return passed;
 if(!passed)
 {
  if(m_diagReason=="") m_diagReason=gate;
  DiagCount((m_diagCandidate?"candidate/":"pre_candidate/")+gate+"/"+m_diagReason);
  if(m_diagCandidate) m_diagRejections++;
  if(gate=="cost_or_stop_gate") m_diagCost++;
  m_diagFinished=true;
 }
 else if(gate=="queued") {if(!m_diagQueued) m_diagQueuePasses++;m_diagQueued=true;}
 else m_diagFinished=true;
 m_diagActive=false;return passed;
}
void DiagExecution(bool manual)
{
 m_diagActive=MQLInfoInteger(MQL_TESTER) && ExecutionMode==EXECUTION_AUTO && !manual && m_diagCandidate && !m_diagFinished;
 if(m_diagActive) m_diagReason="";
}
void DiagOrderAttempt()
{if(m_diagActive) {m_diagAttempts++;PrintFormat("[MT3 ENTRY ORDER] symbol=%s candidate_id=%d event=attempt",m_symbol,m_diagCandidates);}}
void DiagOrderResult(bool ok,uint rc)
{
 if(!m_diagActive) return;
 // Accepted submission is not a filled trade/deal; keep broker outcome separate.
 if(ok && (rc==TRADE_RETCODE_DONE || rc==TRADE_RETCODE_DONE_PARTIAL || rc==TRADE_RETCODE_PLACED)) m_diagAccepted++;
 else m_diagOrderRejected++;
 PrintFormat("[MT3 ENTRY ORDER] symbol=%s candidate_id=%d event=result ok=%d retcode=%u",m_symbol,m_diagCandidates,(int)ok,rc);
}
void DiagSummary()
{
 if(!MQLInfoInteger(MQL_TESTER) || ExecutionMode!=EXECUTION_AUTO) return;
 PrintFormat("[MT3 ENTRY SUMMARY] symbol=%s evaluations=%d candidates=%d rejections=%d queue_passes=%d order_attempts=%d order_accepted=%d order_rejected=%d cost_or_stop_gate=%d dropped=%d",m_symbol,m_diagEvaluations,m_diagCandidates,m_diagRejections,m_diagQueuePasses,m_diagAttempts,m_diagAccepted,m_diagOrderRejected,m_diagCost,m_diagDropped);
 for(int i=0;i<ArraySize(m_diagKeys);i++) PrintFormat("[MT3 ENTRY REASON] symbol=%s key=%s count=%d",m_symbol,m_diagKeys[i],m_diagCounts[i]);
}

color ThemeRed() {return C'242,54,69';}

color ThemeBlue() {return C'41,98,255';}

color PanelForeground()
{return EnableTradingViewTheme?C'209,212,220':(color)ChartGetInteger(0,CHART_COLOR_FOREGROUND);}

bool SetThemeProperty(ENUM_CHART_PROPERTY_INTEGER property,long value)
{
 long previous=0;
 if(!ChartGetInteger(0,property,0,previous)) return false;
 if(!ChartSetInteger(0,property,value)) return false;
 int n=ArraySize(g_themeProperties);ArrayResize(g_themeProperties,n+1);
 g_themeProperties[n].property=property;g_themeProperties[n].before=previous;g_themeProperties[n].applied=value;
 return true;
}

void RestoreChartTheme()
{
 if(!m_isChart) return;

 // Restore only values still owned by this theme; keep subsequent user adjustments.
 for(int i=ArraySize(g_themeProperties)-1;i>=0;i--)
 {
  long current=0;
  if(ChartGetInteger(0,g_themeProperties[i].property,0,current) && current==g_themeProperties[i].applied)
   ChartSetInteger(0,g_themeProperties[i].property,g_themeProperties[i].before);
 }
 if(g_themeShiftSaved)
 {
  double current=0;
  if(ChartGetDouble(0,CHART_SHIFT_SIZE,0,current) && MathAbs(current-ThemeRightMarginPercent)<0.00001)
   ChartSetDouble(0,CHART_SHIFT_SIZE,g_themeShiftBefore);
 }
 ArrayResize(g_themeProperties,0);g_themeShiftSaved=false;ChartRedraw();
}

void ApplyChartTheme()
{
 if(!m_isChart) return;

 if(!EnableTradingViewTheme) return;
 bool ok=true;
 if(!SetThemeProperty(CHART_MODE,CHART_CANDLES)) ok=false;
 if(!SetThemeProperty(CHART_COLOR_BACKGROUND,C'19,23,34')) ok=false;
 if(!SetThemeProperty(CHART_COLOR_FOREGROUND,C'209,212,220')) ok=false;
 if(!SetThemeProperty(CHART_COLOR_GRID,C'42,46,57')) ok=false;
 if(!SetThemeProperty(CHART_COLOR_CHART_UP,ThemeRed())) ok=false;
 if(!SetThemeProperty(CHART_COLOR_CANDLE_BULL,ThemeRed())) ok=false;
 if(!SetThemeProperty(CHART_COLOR_CHART_DOWN,ThemeBlue())) ok=false;
 if(!SetThemeProperty(CHART_COLOR_CANDLE_BEAR,ThemeBlue())) ok=false;
 if(!SetThemeProperty(CHART_COLOR_CHART_LINE,C'209,212,220')) ok=false;
 if(!SetThemeProperty(CHART_COLOR_VOLUME,C'120,123,134')) ok=false;
 if(!SetThemeProperty(CHART_COLOR_BID,C'120,123,134')) ok=false;
 if(!SetThemeProperty(CHART_COLOR_ASK,C'255,183,77')) ok=false;
 if(!SetThemeProperty(CHART_COLOR_LAST,C'209,212,220')) ok=false;
 if(!SetThemeProperty(CHART_COLOR_STOP_LEVEL,C'255,183,77')) ok=false;
 if(!SetThemeProperty(CHART_SHOW_GRID,ThemeShowGrid)) ok=false;
 if(!SetThemeProperty(CHART_SHOW_PERIOD_SEP,false)) ok=false;
 if(!SetThemeProperty(CHART_SHOW_VOLUMES,CHART_VOLUME_HIDE)) ok=false;
 if(!SetThemeProperty(CHART_SHOW_BID_LINE,true)) ok=false;
 if(!SetThemeProperty(CHART_SHOW_ASK_LINE,true)) ok=false;
 if(!SetThemeProperty(CHART_SHOW_TRADE_LEVELS,true)) ok=false;
 if(!SetThemeProperty(CHART_FOREGROUND,false)) ok=false;
 if(!SetThemeProperty(CHART_SCALE,ThemeChartScale)) ok=false;
 if(!SetThemeProperty(CHART_SHIFT,true)) ok=false;
 if(!SetThemeProperty(CHART_SHOW_PRICE_SCALE,true)) ok=false;
 if(!SetThemeProperty(CHART_SHOW_DATE_SCALE,true)) ok=false;
 if(ChartGetDouble(0,CHART_SHIFT_SIZE,0,g_themeShiftBefore))
 {
  if(ChartSetDouble(0,CHART_SHIFT_SIZE,ThemeRightMarginPercent)) g_themeShiftSaved=true;
  else ok=false;
 }
 else ok=false;
 ChartRedraw();
 if(!ok) Print("Some chart theme properties could not be applied. Trading settings are unchanged.");
}

double GetBid()
  {
   double value = 0.0;

   if(!SymbolInfoDouble(m_symbol,SYMBOL_BID,value))
      return 0.0;

   return value;
  }

double GetAsk()
  {
   double value = 0.0;

   if(!SymbolInfoDouble(m_symbol,SYMBOL_ASK,value))
      return 0.0;

   return value;
  }

double GetPointValue()
  {
   return SymbolInfoDouble(m_symbol,SYMBOL_POINT);
  }

int GetDigitsValue()
  {
   return (int)SymbolInfoInteger(m_symbol,SYMBOL_DIGITS);
  }

double NormalizePrice(double price)
{
 double tick=SymbolInfoDouble(m_symbol,SYMBOL_TRADE_TICK_SIZE);
 if(tick<=0) return 0;
 return NormalizeDouble(MathRound(price/tick)*tick,m_digits);
}

double GetSpreadPoints()
  {
   double bid = GetBid();
   double ask = GetAsk();

   if(bid <= 0 || ask <= 0)
      return 999999;

   double point = GetPointValue();

   if(point <= 0)
      return 999999;

   return (ask-bid)/point;
  }

bool IsNewBar(ENUM_TIMEFRAMES timeframe)
  {
   datetime currentTime = iTime(m_symbol,timeframe,0);

   if(currentTime <= 0)
      return false;

   if(currentTime != g_lastBarTime)
     {
      g_lastBarTime = currentTime;
      return true;
     }

   return false;
  }

double NormalizeVolume(double volume)
{
 double lo=SymbolInfoDouble(m_symbol,SYMBOL_VOLUME_MIN);
 double hi=SymbolInfoDouble(m_symbol,SYMBOL_VOLUME_MAX);
 double step=SymbolInfoDouble(m_symbol,SYMBOL_VOLUME_STEP);
 if(DiagReject(step<=0,"lot_step_invalid") || DiagReject(volume<lo,"lot_below_min")) return 0;
 double v=NormalizeDouble(MathFloor(MathMin(volume,hi)/step+1e-9)*step,8);
 if(DiagReject(v>volume+1e-8,"lot_rounding_exceeds_request") || DiagReject(v<lo-1e-8,"lot_below_min")) return 0;
 return v;
}

double ClampRisk(double risk)
{
 if(risk<=0 || !MathIsValidNumber(risk)) return 0;
 return MathMin(risk,MaximumRiskPercent);
}

bool IsBuyAllowed()
  {
   if(EntryDirection == ENTRY_SELL)
      return false;

   return true;
  }

bool IsSellAllowed()
  {
   if(EntryDirection == ENTRY_BUY)
      return false;

   return true;
  }

int CountOurPositions()
  {
   int count = 0;

   for(int i=PositionsTotal()-1; i>=0; i--)
     {
      ulong ticket = PositionGetTicket(i);

      if(ticket == 0)
         continue;

      if(!PositionSelectByTicket(ticket))
         continue;

      string symbol = PositionGetString(POSITION_SYMBOL);

      long magic = PositionGetInteger(POSITION_MAGIC);

      if(symbol == m_symbol && magic == (long)MagicNumber)
         count++;
     }

   return count;
  }

bool HasOurPosition()
  {
   return (CountOurPositions() > 0);
  }

void LogMessage(string text)
  {
   Print("[MTFAutoTrader] ",text);
  }

int CachedIndicator(int kind,ENUM_TIMEFRAMES tf,int period)
{
 for(int i=0;i<ArraySize(g_indicators);i++)
  if(g_indicators[i].kind==kind && g_indicators[i].tf==tf && g_indicators[i].period==period)
   return g_indicators[i].handle;
 int h=INVALID_HANDLE;
 if(kind==0) h=iATR(m_symbol,tf,period);
 if(kind==1) h=iMA(m_symbol,tf,period,0,MODE_EMA,PRICE_CLOSE);
 if(kind==2) h=iADX(m_symbol,tf,period);
 if(kind==3) {int fast,slow,signal;MACDParameters(tf,fast,slow,signal);h=iMACD(m_symbol,tf,fast,slow,signal,PRICE_CLOSE);}
 if(h==INVALID_HANDLE) return h;
 int n=ArraySize(g_indicators); if(ArrayResize(g_indicators,n+1)!=n+1) {IndicatorRelease(h);return INVALID_HANDLE;}
 g_indicators[n].kind=kind; g_indicators[n].tf=tf; g_indicators[n].period=period; g_indicators[n].handle=h;
 return h;
}

bool ReadIndicator(int handle,int buffer,int shift,double &v)
{
 v=0; double a[1];
 if(handle==INVALID_HANDLE || CopyBuffer(handle,buffer,shift,1,a)!=1 || BarsCalculated(handle)<=shift) return false;
 if(!MathIsValidNumber(a[0]) || a[0]==EMPTY_VALUE) return false;
 v=a[0]; return true;
}

double GetATR(ENUM_TIMEFRAMES timeframe,int period,int shift)
{
 double v=0; if(!ReadIndicator(CachedIndicator(0,timeframe,period),0,shift,v)) return 0;
 return v;
}

bool IsSwingHigh(ENUM_TIMEFRAMES timeframe,
                 int shift,
                 int depth)
  {
   if(shift<=depth) return false;
   int bars = Bars(m_symbol,timeframe);

   if(bars <= shift + depth + 2)
      return false;

   double price = iHigh(m_symbol,timeframe,shift);

   if(price <= 0)
      return false;

   for(int i=1;i<=depth;i++)
     {
      double left  = iHigh(m_symbol,timeframe,shift-i);
      double right = iHigh(m_symbol,timeframe,shift+i);

      if(left >= price)
         return false;

      if(right >= price)
         return false;
     }

   return true;
  }

bool IsSwingLow(ENUM_TIMEFRAMES timeframe,
                int shift,
                int depth)
  {
   if(shift<=depth) return false;
   int bars = Bars(m_symbol,timeframe);

   if(bars <= shift + depth + 2)
      return false;

   double price = iLow(m_symbol,timeframe,shift);

   if(price <= 0)
      return false;

   for(int i=1;i<=depth;i++)
     {
      double left  = iLow(m_symbol,timeframe,shift-i);
      double right = iLow(m_symbol,timeframe,shift+i);

      if(left <= price)
         return false;

      if(right <= price)
         return false;
     }

   return true;
  }

bool GetRecentSwingLows(ENUM_TIMEFRAMES timeframe,
                        int depth,
                        int lookback,
                        int &shift1,
                        double &price1,
                        int &shift2,
                        double &price2,
                        int &shift3,
                        double &price3)
  {
   shift1 = -1;
   shift2 = -1;
   shift3 = -1;

   price1 = 0;
   price2 = 0;
   price3 = 0;

   int bars = Bars(m_symbol,timeframe);

   if(bars < depth*2 + 20)
      return false;

   int maxBars = MathMin(lookback,bars-depth-2);

   int found = 0;

   for(int shift=depth+1;shift<=maxBars;shift++)
     {
      if(!IsSwingLow(timeframe,shift,depth))
         continue;

      double price = iLow(m_symbol,timeframe,shift);

      if(found == 0)
        {
         shift1 = shift;
         price1 = price;
         found++;
        }
      else if(found == 1)
        {
         shift2 = shift;
         price2 = price;
         found++;
        }
      else if(found == 2)
        {
         shift3 = shift;
         price3 = price;
         found++;
         break;
        }
     }

   return (found >= 2);
  }

bool GetRecentSwingHighs(ENUM_TIMEFRAMES timeframe,
                         int depth,
                         int lookback,
                         int &shift1,
                         double &price1,
                         int &shift2,
                         double &price2,
                         int &shift3,
                         double &price3)
  {
   shift1 = -1;
   shift2 = -1;
   shift3 = -1;

   price1 = 0;
   price2 = 0;
   price3 = 0;

   int bars = Bars(m_symbol,timeframe);

   if(bars < depth*2 + 20)
      return false;

   int maxBars = MathMin(lookback,bars-depth-2);

   int found = 0;

   for(int shift=depth+1;shift<=maxBars;shift++)
     {
      if(!IsSwingHigh(timeframe,shift,depth))
         continue;

      double price = iHigh(m_symbol,timeframe,shift);

      if(found == 0)
        {
         shift1 = shift;
         price1 = price;
         found++;
        }
      else if(found == 1)
        {
         shift2 = shift;
         price2 = price;
         found++;
        }
      else if(found == 2)
        {
         shift3 = shift;
         price3 = price;
         found++;
         break;
        }
     }

   return (found >= 2);
  }

double PriceDifferencePercent(double price1,double price2)
  {
   double average = (price1+price2)/2.0;

   if(average <= 0)
      return 999.0;

   return MathAbs(price1-price2)/average*100.0;
  }

bool DetectDoubleBottom(PatternSignal &signal)
  {
   signal.valid = false;
   signal.buySignal = false;
   signal.sellSignal = false;
   signal.type = PATTERN_NONE;

   int s1,s2,s3;

   double p1,p2,p3;

   if(!GetRecentSwingLows(PERIOD_M1,
                          SwingDepth,
                          PatternLookbackBars,
                          s1,p1,
                          s2,p2,
                          s3,p3))
      return false;

   // 最新側の安値
   double recentLow = p1;

   // 1つ前の安値
   double previousLow = p2;

   double atr = GetATR(PERIOD_M1,14,1);

   if(atr <= 0)
      return false;

   // 2つの安値の差
   double difference = MathAbs(recentLow-previousLow);

   if(difference > atr*PatternToleranceATR)
      return false;

   // 安値間の最高値＝ネックライン
   int startShift = MathMin(s1,s2);

   int endShift = MathMax(s1,s2);

   double neckline = 0.0;

   for(int shift=endShift;
       shift>=startShift;
       shift--)
     {
      double high = iHigh(m_symbol,PERIOD_M1,shift);

      if(high > neckline)
         neckline = high;
     }

   if(neckline <= 0)
      return false;

   // 現在の確定足
   double close1 = iClose(m_symbol,PERIOD_M1,1);

   // ネックライン突破
   double close2=iClose(m_symbol,PERIOD_M1,2);
   double level=neckline+atr*NecklineToleranceATR;
   bool breakout = (close2>0 && close2<=level && close1>level);

   if(!breakout)
      return false;

   signal.type = PATTERN_DOUBLE_BOTTOM;

   signal.valid = true;

   signal.buySignal = true;

   signal.sellSignal = false;

   signal.firstPoint = previousLow;

   signal.secondPoint = recentLow;

   signal.headPoint = 0;

   signal.neckline = neckline;

   signal.entryLevel = close1;

   signal.patternStrength = 70.0;

   signal.firstTime =
      iTime(m_symbol,PERIOD_M1,s2);

   signal.secondTime =
      iTime(m_symbol,PERIOD_M1,s1);

   signal.necklineTime =
      iTime(m_symbol,PERIOD_M1,startShift);

   return true;
  }

bool DetectDoubleTop(PatternSignal &signal)
  {
   signal.valid = false;
   signal.buySignal = false;
   signal.sellSignal = false;
   signal.type = PATTERN_NONE;

   int s1,s2,s3;

   double p1,p2,p3;

   if(!GetRecentSwingHighs(PERIOD_M1,
                           SwingDepth,
                           PatternLookbackBars,
                           s1,p1,
                           s2,p2,
                           s3,p3))
      return false;

   double recentHigh = p1;

   double previousHigh = p2;

   double atr = GetATR(PERIOD_M1,14,1);

   if(atr <= 0)
      return false;

   double difference =
      MathAbs(recentHigh-previousHigh);

   if(difference > atr*PatternToleranceATR)
      return false;

   int startShift = MathMin(s1,s2);

   int endShift = MathMax(s1,s2);

   double neckline = DBL_MAX;

   for(int shift=endShift;
       shift>=startShift;
       shift--)
     {
      double low = iLow(m_symbol,PERIOD_M1,shift);

      if(low < neckline)
         neckline = low;
     }

   if(neckline <= 0 || neckline == DBL_MAX)
      return false;

   double close1 = iClose(m_symbol,PERIOD_M1,1);

   double close2=iClose(m_symbol,PERIOD_M1,2);
   double level=neckline-atr*NecklineToleranceATR;
   bool breakout = (close2>0 && close2>=level && close1<level);

   if(!breakout)
      return false;

   signal.type = PATTERN_DOUBLE_TOP;

   signal.valid = true;

   signal.buySignal = false;

   signal.sellSignal = true;

   signal.firstPoint = previousHigh;

   signal.secondPoint = recentHigh;

   signal.headPoint = 0;

   signal.neckline = neckline;

   signal.entryLevel = close1;

   signal.patternStrength = 70.0;

   signal.firstTime =
      iTime(m_symbol,PERIOD_M1,s2);

   signal.secondTime =
      iTime(m_symbol,PERIOD_M1,s1);

   signal.necklineTime =
      iTime(m_symbol,PERIOD_M1,startShift);

   return true;
  }

bool DetectInverseHeadShoulders(PatternSignal &signal)
  {
   signal.valid = false;
   signal.buySignal = false;
   signal.sellSignal = false;
   signal.type = PATTERN_NONE;

   int s1,s2,s3;

   double p1,p2,p3;

   if(!GetRecentSwingLows(PERIOD_M1,
                          SwingDepth,
                          PatternLookbackBars,
                          s1,p1,
                          s2,p2,
                          s3,p3))
      return false;

   if(s3<0 || p3<=0) return false;

   // 3つの安値
   if(s3<0 || p3<=0) return false;

   // p3 = 左肩
   // p2 = ヘッド
   // p1 = 右肩

   double leftShoulder  = p3;

   double head          = p2;

   double rightShoulder = p1;

   double atr = GetATR(PERIOD_M1,14,1);

   if(atr <= 0)
      return false;

   // ヘッドが左右の肩より明確に低い
   if(head >= leftShoulder-atr*0.20)
      return false;

   if(head >= rightShoulder-atr*0.20)
      return false;

   // 左右の肩の高さが近い
   double shoulderDiff =
      MathAbs(leftShoulder-rightShoulder);

   if(shoulderDiff > atr*PatternToleranceATR*2.0)
      return false;

   // ネックライン
   int leftShift  = s3;

   int rightShift = s1;

   int startShift = MathMin(leftShift,rightShift);

   int endShift = MathMax(leftShift,rightShift);

   double neckline = 0.0;

   for(int shift=endShift;
       shift>=startShift;
       shift--)
     {
      double high = iHigh(m_symbol,PERIOD_M1,shift);

      if(high > neckline)
         neckline = high;
     }

   if(neckline <= 0)
      return false;

   double close1 = iClose(m_symbol,PERIOD_M1,1);

   double close2=iClose(m_symbol,PERIOD_M1,2);
   double level=neckline+atr*NecklineToleranceATR;
   bool breakout = (close2>0 && close2<=level && close1>level);

   if(!breakout)
      return false;

   signal.type =
      PATTERN_INVERSE_HEAD_SHOULDERS;

   signal.valid = true;

   signal.buySignal = true;

   signal.sellSignal = false;

   signal.firstPoint = leftShoulder;

   signal.secondPoint = rightShoulder;

   signal.headPoint = head;

   signal.neckline = neckline;

   signal.entryLevel = close1;

   signal.patternStrength = 85.0;

   signal.firstTime =
      iTime(m_symbol,PERIOD_M1,s3);

   signal.headTime =
      iTime(m_symbol,PERIOD_M1,s2);

   signal.secondTime =
      iTime(m_symbol,PERIOD_M1,s1);

   return true;
  }

bool DetectHeadShoulders(PatternSignal &signal)
  {
   signal.valid = false;
   signal.buySignal = false;
   signal.sellSignal = false;
   signal.type = PATTERN_NONE;

   int s1,s2,s3;

   double p1,p2,p3;

   if(!GetRecentSwingHighs(PERIOD_M1,
                           SwingDepth,
                           PatternLookbackBars,
                           s1,p1,
                           s2,p2,
                           s3,p3))
      return false;

   if(s3<0 || p3<=0) return false;

   // p3 = 左肩
   // p2 = ヘッド
   // p1 = 右肩

   double leftShoulder  = p3;

   double head          = p2;

   double rightShoulder = p1;

   double atr = GetATR(PERIOD_M1,14,1);

   if(atr <= 0)
      return false;

   // ヘッドが左右の肩より高い
   if(head <= leftShoulder+atr*0.20)
      return false;

   if(head <= rightShoulder+atr*0.20)
      return false;

   // 左右の肩の高さが近い
   double shoulderDiff =
      MathAbs(leftShoulder-rightShoulder);

   if(shoulderDiff > atr*PatternToleranceATR*2.0)
      return false;

   // ネックライン
   int leftShift  = s3;

   int rightShift = s1;

   int startShift = MathMin(leftShift,rightShift);

   int endShift = MathMax(leftShift,rightShift);

   double neckline = DBL_MAX;

   for(int shift=endShift;
       shift>=startShift;
       shift--)
     {
      double low = iLow(m_symbol,PERIOD_M1,shift);

      if(low < neckline)
         neckline = low;
     }

   if(neckline <= 0 || neckline == DBL_MAX)
      return false;

   double close1 = iClose(m_symbol,PERIOD_M1,1);

   double close2=iClose(m_symbol,PERIOD_M1,2);
   double level=neckline-atr*NecklineToleranceATR;
   bool breakout = (close2>0 && close2>=level && close1<level);

   if(!breakout)
      return false;

   signal.type =
      PATTERN_HEAD_SHOULDERS;

   signal.valid = true;

   signal.buySignal = false;

   signal.sellSignal = true;

   signal.firstPoint = leftShoulder;

   signal.secondPoint = rightShoulder;

   signal.headPoint = head;

   signal.neckline = neckline;

   signal.entryLevel = close1;

   signal.patternStrength = 85.0;

   signal.firstTime =
      iTime(m_symbol,PERIOD_M1,s3);

   signal.headTime =
      iTime(m_symbol,PERIOD_M1,s2);

   signal.secondTime =
      iTime(m_symbol,PERIOD_M1,s1);

   return true;
  }

bool DetectTriplePattern(bool bottom,PatternSignal &signal)
{
 ZeroMemory(signal);
 signal.type=PATTERN_NONE;
 if(bottom?!EnableTripleBottom:!EnableTripleTop) return false;
 int s1,s2,s3; double p1,p2,p3;
 bool found=bottom?
   GetRecentSwingLows(PERIOD_M1,SwingDepth,PatternLookbackBars,s1,p1,s2,p2,s3,p3):
   GetRecentSwingHighs(PERIOD_M1,SwingDepth,PatternLookbackBars,s1,p1,s2,p2,s3,p3);
 // s1 is newest. Require three fully confirmed pivots and intervening bars.
 if(!found || s1<=SwingDepth || s2<=s1+1 || s3<=s2+1 || p1<=0 || p2<=0 || p3<=0) return false;
 double atr=GetATR(PERIOD_M1,14,1);
 if(atr<=0) return false;
 double highest=MathMax(p1,MathMax(p2,p3)),lowest=MathMin(p1,MathMin(p2,p3));
 if(highest-lowest>atr*PatternToleranceATR) return false;
 double nearNeck=bottom?0.0:DBL_MAX,farNeck=nearNeck;
 for(int shift=s1+1;shift<s2;shift++)
 {
  double price=bottom?iHigh(m_symbol,PERIOD_M1,shift):iLow(m_symbol,PERIOD_M1,shift);
  if(price<=0) return false;
  nearNeck=bottom?MathMax(nearNeck,price):MathMin(nearNeck,price);
 }
 for(int shift=s2+1;shift<s3;shift++)
 {
  double price=bottom?iHigh(m_symbol,PERIOD_M1,shift):iLow(m_symbol,PERIOD_M1,shift);
  if(price<=0) return false;
  farNeck=bottom?MathMax(farNeck,price):MathMin(farNeck,price);
 }
 double rebound=atr*TripleMinimumReboundATR;
 if(bottom)
 {
  if(nearNeck-MathMax(p1,p2)<rebound || farNeck-MathMax(p2,p3)<rebound) return false;
 }
 else
 {
  if(MathMin(p1,p2)-nearNeck<rebound || MathMin(p2,p3)-farNeck<rebound) return false;
 }
 double neckline=bottom?MathMax(nearNeck,farNeck):MathMin(nearNeck,farNeck);
 double level=neckline+(bottom?1.0:-1.0)*atr*NecklineToleranceATR;
 double close1=iClose(m_symbol,PERIOD_M1,1),close2=iClose(m_symbol,PERIOD_M1,2);
 if(close1<=0 || close2<=0) return false;
 if(bottom?!(close2<=level && close1>level):!(close2>=level && close1<level)) return false;
 signal.type=bottom?PATTERN_TRIPLE_BOTTOM:PATTERN_TRIPLE_TOP;
 signal.valid=true;signal.buySignal=bottom;signal.sellSignal=!bottom;
 signal.firstPoint=p3;signal.secondPoint=p1;
 // Middle pivot stored in the existing head fields for diagnostics only.
 signal.headPoint=p2;signal.firstTime=iTime(m_symbol,PERIOD_M1,s3);
 signal.headTime=iTime(m_symbol,PERIOD_M1,s2);signal.secondTime=iTime(m_symbol,PERIOD_M1,s1);
 signal.neckline=neckline;signal.entryLevel=close1;
 signal.patternStrength=70.0; // Same initial score as double patterns; no assumed superiority.
 return true;
}

bool DetectTripleBottom(PatternSignal &signal) {return DetectTriplePattern(true,signal);}

bool DetectTripleTop(PatternSignal &signal) {return DetectTriplePattern(false,signal);}

bool DetectLegacyReversalPattern(PatternSignal &signal)
  {
   signal.valid = false;

   signal.buySignal = false;

   signal.sellSignal = false;

   signal.type = PATTERN_NONE;

   // -------------------------------------------------------------
   // Triple patterns take precedence over overlapping double patterns.
   if(DetectTripleBottom(signal)) return true;
   if(DetectTripleTop(signal)) return true;

   // Double Bottom
   // -------------------------------------------------------------

   if(DetectDoubleBottom(signal))
      return true;

   // -------------------------------------------------------------
   // Double Top
   // -------------------------------------------------------------

   if(DetectDoubleTop(signal))
      return true;

   // -------------------------------------------------------------
   // Inverse Head & Shoulders
   // -------------------------------------------------------------

   if(DetectInverseHeadShoulders(signal))
      return true;

   // -------------------------------------------------------------
   // Head & Shoulders
   // -------------------------------------------------------------

   if(DetectHeadShoulders(signal))
      return true;

   return false;
  }

string PatternName(ENUM_PATTERN_TYPE type)
  {
   switch(type)
     {
      case PATTERN_BULLISH_123: return "BULLISH_123_REVERSAL";
      case PATTERN_BEARISH_123: return "BEARISH_123_REVERSAL";
      case PATTERN_BULLISH_FAILED_BREAKOUT: return "BULLISH_FAILED_BREAKOUT";
      case PATTERN_BEARISH_FAILED_BREAKOUT: return "BEARISH_FAILED_BREAKOUT";

      case PATTERN_TRIPLE_BOTTOM:
         return "TRIPLE BOTTOM";

      case PATTERN_TRIPLE_TOP:
         return "TRIPLE TOP";

      case PATTERN_DOUBLE_BOTTOM:
         return "DOUBLE BOTTOM";

      case PATTERN_DOUBLE_TOP:
         return "DOUBLE TOP";

      case PATTERN_INVERSE_HEAD_SHOULDERS:
         return "INVERSE H&S";

      case PATTERN_HEAD_SHOULDERS:
         return "HEAD & SHOULDERS";

      default:
         return "NONE";
     }
  }

ENUM_ENTRY_DIRECTION PatternDirection(PatternSignal &signal)
{
 if(signal.valid && signal.buySignal) return ENTRY_BUY;
 if(signal.valid && signal.sellSignal) return ENTRY_SELL;
 return ENTRY_BOTH;
}

void PrintPatternSignal(PatternSignal &signal)
  {
   if(!signal.valid)
      return;

   string direction = "NONE";

   if(signal.buySignal)
      direction = "BUY";

   if(signal.sellSignal)
      direction = "SELL";

   Print(
      "[Pattern] ",
      PatternName(signal.type),
      " / ",
      direction,
      " / Neckline=",
      DoubleToString(signal.neckline,GetDigitsValue()),
      " / Entry=",
      DoubleToString(signal.entryLevel,GetDigitsValue()),
      " / Strength=",
      DoubleToString(signal.patternStrength,1)
   );
  }

double GetEMA(ENUM_TIMEFRAMES timeframe,int period,int shift)
{
 double v=0; if(!ReadIndicator(CachedIndicator(1,timeframe,period),0,shift,v)) return 0;
 return v;
}

bool GetADXValues(ENUM_TIMEFRAMES timeframe,int period,int shift,double &adx,double &plusDI,double &minusDI)
{
 int h=CachedIndicator(2,timeframe,period);
 return ReadIndicator(h,0,shift,adx) && ReadIndicator(h,1,shift,plusDI) && ReadIndicator(h,2,shift,minusDI);
}

bool GetMACDValues(ENUM_TIMEFRAMES timeframe,int shift,double &mainValue,double &signalValue,double &histogram)
{
 int h=CachedIndicator(3,timeframe,0);
 if(!ReadIndicator(h,0,shift,mainValue) || !ReadIndicator(h,1,shift,signalValue)) return false;
 histogram=mainValue-signalValue; return true;
}

bool AnalyzeTimeframe(ENUM_TIMEFRAMES timeframe,MTFResult &result)
{
 ZeroMemory(result);result.timeframe=timeframe;
 // Creating the handle first lets MT5 initiate asynchronous history loading.
 CachedIndicator(1,timeframe,EMASlowPeriod);
 if(Bars(m_symbol,timeframe)<EMASlowPeriod+EMASlopeBars+10) return false;
 result.bar=iTime(m_symbol,timeframe,0);if(result.bar<=0) return false;
 result.atr=GetATR(timeframe,14,1);result.close=iClose(m_symbol,timeframe,1);
 result.emaFast=GetEMA(timeframe,EMAFastPeriod,1);
 result.emaMiddle=GetEMA(timeframe,EMAMiddlePeriod,1);
 result.emaSlow=GetEMA(timeframe,EMASlowPeriod,1);
 result.previousFast=GetEMA(timeframe,EMAFastPeriod,1+EMASlopeBars);
 result.previousMiddle=GetEMA(timeframe,EMAMiddlePeriod,1+EMASlopeBars);
 result.previousSlow=GetEMA(timeframe,EMASlowPeriod,1+EMASlopeBars);
 if(result.atr<=0 || result.close<=0 || result.emaFast<=0 || result.emaMiddle<=0 || result.emaSlow<=0 ||
    result.previousFast<=0 || result.previousMiddle<=0 || result.previousSlow<=0) return false;
 if(!GetADXValues(timeframe,ADXPeriod,1,result.adx,result.plusDI,result.minusDI) ||
    !GetMACDValues(timeframe,1,result.macdMain,result.macdSignal,result.macdHistogram)) return false;
 double pm,ps;if(!GetMACDValues(timeframe,2,pm,ps,result.previousHistogram)) return false;
 ScoreEvidence(result);
 return result.bar==iTime(m_symbol,timeframe,0);
}

bool AnalyzeAllTimeframes(MTFResult &results[])
{
 if(ArrayResize(results,7)!=7 || ArraySize(m_mtf)!=7) return false;
 for(int i=0;i<7;i++)
 {
  ENUM_TIMEFRAMES tf=MT3Timeframe(i);datetime bar=iTime(m_symbol,tf,0);
  if(bar<=0 || m_mtf[i].bar!=bar || m_mtf[i].atr<=0)
  {if(!AnalyzeTimeframe(tf,m_mtf[i])) return false;}
  results[i]=m_mtf[i];
 }
 return MTFSnapshotCurrent();
}

int CountBullishTimeframes(MTFResult &results[])
  {
   int count=0;

   int size=ArraySize(results);

   for(int i=0;i<size;i++)
     {
      if(results[i].trendDirection>0)
         count++;
     }

   return count;
  }

int CountBearishTimeframes(MTFResult &results[])
  {
   int count=0;

   int size=ArraySize(results);

   for(int i=0;i<size;i++)
     {
      if(results[i].trendDirection<0)
         count++;
     }

   return count;
  }

int CountBullishMACD(MTFResult &results[])
  {
   int count=0;

   int size=ArraySize(results);

   for(int i=0;i<size;i++)
     {
      if(results[i].macdDirection>0)
         count++;
     }

   return count;
  }

int CountBearishMACD(MTFResult &results[])
  {
   int count=0;

   int size=ArraySize(results);

   for(int i=0;i<size;i++)
     {
      if(results[i].macdDirection<0)
         count++;
     }

   return count;
  }

double CalculateBuyMTFScore(MTFResult &r[]) {return WeightedMTFScore(r,true);}

double CalculateSellMTFScore(MTFResult &r[]) {return WeightedMTFScore(r,false);}

bool HigherTimeframeBuyOK(MTFResult &r[]) {return !StrongHigherOpposition(r,true);}

bool HigherTimeframeSellOK(MTFResult &r[]) {return !StrongHigherOpposition(r,false);}

string TimeframeToString(ENUM_TIMEFRAMES tf)
  {
   switch(tf)
     {
      case PERIOD_M1:
         return "M1";

      case PERIOD_M2:
         return "M2";

      case PERIOD_M3:
         return "M3";

      case PERIOD_M5:
         return "M5";

      case PERIOD_M15:
         return "M15";

      case PERIOD_M30:
         return "M30";

      case PERIOD_H1:
         return "H1";

      case PERIOD_H4:
         return "H4";

      case PERIOD_D1:
         return "D1";

      case PERIOD_W1:
         return "W1";

      case PERIOD_MN1:
         return "MN1";
     }

   return "?";
  }

void PrintMTFResults(MTFResult &results[])
  {
   int size=ArraySize(results);

   for(int i=0;i<size;i++)
     {
      Print(
         "[MTF] ",
         TimeframeToString(results[i].timeframe),
         " Trend=",
         IntegerToString(results[i].trendDirection),
         " TrendScore=",
         DoubleToString(results[i].trendScore,1),
         " MACD=",
         IntegerToString(results[i].macdDirection),
         " MACDScore=",
         DoubleToString(results[i].macdScore,1),
         " Total=",
         DoubleToString(results[i].totalScore,1),
         " ADX=",
         DoubleToString(results[i].adx,1)
      );
     }
  }

bool CreateOrUpdateHLine(string name,
                         double price,
                         color lineColor,
                         ENUM_LINE_STYLE style=STYLE_DOT,
                         int width=1)
  {
 StoreLevel(name,NormalizePrice(price));if(!m_isChart) return true;

   price=NormalizePrice(price);

   if(ObjectFind(0,name)<0)
     {
      if(!ObjectCreate(0,name,OBJ_HLINE,0,0,price))
         return false;
     }
   else
     {
      ObjectSetDouble(0,name,OBJPROP_PRICE,price);
     }

   ObjectSetInteger(0,name,OBJPROP_COLOR,lineColor);
   ObjectSetInteger(0,name,OBJPROP_STYLE,style);
   ObjectSetInteger(0,name,OBJPROP_WIDTH,width);
   ObjectSetInteger(0,name,OBJPROP_BACK,true);
   ObjectSetInteger(0,name,OBJPROP_SELECTABLE,false);

   return true;
  }

bool CreateOrUpdateTrendLine(string name,
                             datetime time1,
                             double price1,
                             datetime time2,
                             double price2,
                             color lineColor,
                             ENUM_LINE_STYLE style=STYLE_SOLID,
                             int width=1)
  {
 StoreTrend(name,time1,price1,time2,price2);if(!m_isChart) return true;

   if(time1<=0 || time2<=0)
      return false;

   price1=NormalizePrice(price1);
   price2=NormalizePrice(price2);

   if(ObjectFind(0,name)<0)
     {
      if(!ObjectCreate(0,
                       name,
                       OBJ_TREND,
                       0,
                       time1,
                       price1,
                       time2,
                       price2))
         return false;
     }
   else
     {
      ObjectMove(0,name,0,time1,price1);
      ObjectMove(0,name,1,time2,price2);
     }

   ObjectSetInteger(0,name,OBJPROP_COLOR,lineColor);
   ObjectSetInteger(0,name,OBJPROP_STYLE,style);
   ObjectSetInteger(0,name,OBJPROP_WIDTH,width);
   ObjectSetInteger(0,name,OBJPROP_RAY_RIGHT,true);
   ObjectSetInteger(0,name,OBJPROP_BACK,true);
   ObjectSetInteger(0,name,OBJPROP_SELECTABLE,false);

   return true;
  }

bool IsPriceNear(double price1,
                 double price2,
                 double tolerance)
  {
   return (MathAbs(price1-price2)<=tolerance);
  }

bool GetLatestSwingLow(ENUM_TIMEFRAMES timeframe,
                       int depth,
                       int lookback,
                       int &shift,
                       double &price)
  {
   shift=-1;
   price=0.0;

   int bars=Bars(m_symbol,timeframe);

   if(bars<=depth*2+10)
      return false;

   int maxBars=
      MathMin(lookback,bars-depth-2);

   for(int i=depth+1;i<=maxBars;i++)
     {
      if(IsSwingLow(timeframe,i,depth))
        {
         shift=i;
         price=iLow(m_symbol,timeframe,i);
         return true;
        }
     }

   return false;
  }

bool GetSecondSwingLow(ENUM_TIMEFRAMES timeframe,
                       int depth,
                       int lookback,
                       int firstShift,
                       int &shift,
                       double &price)
  {
   shift=-1;
   price=0.0;

   int bars=Bars(m_symbol,timeframe);

   if(bars<=depth*2+10)
      return false;

   int maxBars=
      MathMin(lookback,bars-depth-2);

   for(int i=firstShift+depth;
       i<=maxBars;
       i++)
     {
      if(IsSwingLow(timeframe,i,depth))
        {
         shift=i;
         price=iLow(m_symbol,timeframe,i);
         return true;
        }
     }

   return false;
  }

bool GetLatestSwingHigh(ENUM_TIMEFRAMES timeframe,
                        int depth,
                        int lookback,
                        int &shift,
                        double &price)
  {
   shift=-1;
   price=0.0;

   int bars=Bars(m_symbol,timeframe);

   if(bars<=depth*2+10)
      return false;

   int maxBars=
      MathMin(lookback,bars-depth-2);

   for(int i=depth+1;i<=maxBars;i++)
     {
      if(IsSwingHigh(timeframe,i,depth))
        {
         shift=i;
         price=iHigh(m_symbol,timeframe,i);
         return true;
        }
     }

   return false;
  }

bool GetSecondSwingHigh(ENUM_TIMEFRAMES timeframe,
                        int depth,
                        int lookback,
                        int firstShift,
                        int &shift,
                        double &price)
  {
   shift=-1;
   price=0.0;

   int bars=Bars(m_symbol,timeframe);

   if(bars<=depth*2+10)
      return false;

   int maxBars=
      MathMin(lookback,bars-depth-2);

   for(int i=firstShift+depth;
       i<=maxBars;
       i++)
     {
      if(IsSwingHigh(timeframe,i,depth))
        {
         shift=i;
         price=iHigh(m_symbol,timeframe,i);
         return true;
        }
     }

   return false;
  }

bool IsDuplicateHorizontalLevel(double price,double tolerance,int &count)
{
 count=ArraySize(m_levels);
 for(int i=0;i<count;i++) if(MathAbs(price-m_levels[i].price)<=tolerance) return true;
 return false;
}

void DeleteAutoHorizontalLines()
  {
 ArrayResize(m_levels,0);if(!m_isChart) return;

   int total=ObjectsTotal(0,-1,-1);

   for(int i=total-1;i>=0;i--)
     {
      string name=ObjectName(0,i,-1,-1);

      if(StringFind(name,
                    LINE_PREFIX+"HLINE_")==0)
        {
         ObjectDelete(0,name);
        }
     }
  }

void DeleteAutoTrendLines()
  {
 for(int i=0;i<2;i++) ZeroMemory(m_trends[i]);if(!m_isChart) return;

   int total=ObjectsTotal(0,-1,-1);

   for(int i=total-1;i>=0;i--)
     {
      string name=ObjectName(0,i,-1,-1);

      if(StringFind(name,
                    LINE_PREFIX+"TREND_")==0)
        {
         ObjectDelete(0,name);
        }
     }
  }

void UpdateAutoHorizontalLines()
  {
   if(!EnableAutoHorizontalLines)
      return;

   DeleteAutoHorizontalLines();

   ENUM_TIMEFRAMES tf=LineTimeframe;

   int bars=Bars(m_symbol,tf);

   if(bars<=SwingDepth*2+20)
      return;

   int maxBars=
      MathMin(PatternLookbackBars,
              bars-SwingDepth-2);

   double atr=
      GetATR(tf,14,1);

   if(atr<=0)
      return;

   double tolerance=
      atr*HorizontalLineToleranceATR;

   int resistanceCount=0;
   int supportCount=0;

   // -------------------------------------------------------------
   // Swing High → Resistance
   // -------------------------------------------------------------

   for(int shift=SwingDepth+1;
       shift<=maxBars;
       shift++)
     {
      if(resistanceCount>=MaxHorizontalLines)
         break;

      if(!IsSwingHigh(tf,shift,SwingDepth))
         continue;

      double price=
         iHigh(m_symbol,tf,shift);

      int dummy=0;

      if(IsDuplicateHorizontalLevel(price,
                                    tolerance,
                                    dummy))
         continue;

      string name=
         LINE_PREFIX+
         "HLINE_RES_"+
         IntegerToString(resistanceCount);

      if(CreateOrUpdateHLine(name,
                             price,
                             (EnableTradingViewTheme?ThemeRed():clrTomato),
                             STYLE_DOT,
                             1))
        {
         resistanceCount++;
        }
     }

   // -------------------------------------------------------------
   // Swing Low → Support
   // -------------------------------------------------------------

   for(int shift=SwingDepth+1;
       shift<=maxBars;
       shift++)
     {
      if(supportCount>=MaxHorizontalLines)
         break;

      if(!IsSwingLow(tf,shift,SwingDepth))
         continue;

      double price=
         iLow(m_symbol,tf,shift);

      int dummy=0;

      if(IsDuplicateHorizontalLevel(price,
                                    tolerance,
                                    dummy))
         continue;

      string name=
         LINE_PREFIX+
         "HLINE_SUP_"+
         IntegerToString(supportCount);

      if(CreateOrUpdateHLine(name,
                             price,
                             (EnableTradingViewTheme?ThemeBlue():clrDeepSkyBlue),
                             STYLE_DOT,
                             1))
        {
         supportCount++;
        }
     }

   // -------------------------------------------------------------
   // 前日高値・安値
   // -------------------------------------------------------------

   double previousHigh=
      iHigh(m_symbol,PERIOD_D1,1);

   double previousLow=
      iLow(m_symbol,PERIOD_D1,1);

   if(previousHigh>0)
     {
      CreateOrUpdateHLine(
         LINE_PREFIX+"HLINE_PD_HIGH",
         previousHigh,
         clrOrange,
         STYLE_DASH,
         1);
     }

   if(previousLow>0)
     {
      CreateOrUpdateHLine(
         LINE_PREFIX+"HLINE_PD_LOW",
         previousLow,
         clrOrange,
         STYLE_DASH,
         1);
     }
  }

void UpdateAutoTrendLines()
  {
   if(!EnableAutoTrendLines)
      return;

   DeleteAutoTrendLines();

   ENUM_TIMEFRAMES tf=LineTimeframe;

   int highShift1=-1;
   int highShift2=-1;

   int lowShift1=-1;
   int lowShift2=-1;

   double highPrice1=0.0;
   double highPrice2=0.0;

   double lowPrice1=0.0;
   double lowPrice2=0.0;

   // -------------------------------------------------------------
   // 高値側トレンドライン
   // -------------------------------------------------------------

   bool highOK=
      GetLatestSwingHigh(tf,
                         TrendLineSwingDepth,
                         PatternLookbackBars,
                         highShift1,
                         highPrice1);

   if(highOK)
     {
      highOK=
         GetSecondSwingHigh(tf,
                            TrendLineSwingDepth,
                            PatternLookbackBars,
                            highShift1,
                            highShift2,
                            highPrice2);
     }

   if(highOK)
     {
      datetime time1=
         iTime(m_symbol,tf,highShift2);

      datetime time2=
         iTime(m_symbol,tf,highShift1);

      CreateOrUpdateTrendLine(
         LINE_PREFIX+"TREND_RESISTANCE",
         time1,
         highPrice2,
         time2,
         highPrice1,
         (EnableTradingViewTheme?ThemeRed():clrTomato),
         STYLE_SOLID,
         2);
     }

   // -------------------------------------------------------------
   // 安値側トレンドライン
   // -------------------------------------------------------------

   bool lowOK=
      GetLatestSwingLow(tf,
                        TrendLineSwingDepth,
                        PatternLookbackBars,
                        lowShift1,
                        lowPrice1);

   if(lowOK)
     {
      lowOK=
         GetSecondSwingLow(tf,
                           TrendLineSwingDepth,
                           PatternLookbackBars,
                           lowShift1,
                           lowShift2,
                           lowPrice2);
     }

   if(lowOK)
     {
      datetime time1=
         iTime(m_symbol,tf,lowShift2);

      datetime time2=
         iTime(m_symbol,tf,lowShift1);

      CreateOrUpdateTrendLine(
         LINE_PREFIX+"TREND_SUPPORT",
         time1,
         lowPrice2,
         time2,
         lowPrice1,
         (EnableTradingViewTheme?ThemeBlue():clrDeepSkyBlue),
         STYLE_SOLID,
         2);
     }
  }

double GetNearestSupportDistance(double price) {return NearestLevel(price,true);}

double GetNearestResistanceDistance(double price) {return NearestLevel(price,false);}

bool BuySupportConfirmation()
  {
   double price=GetAsk();

   double atr=GetATR(PERIOD_M1,14,1);

   if(price<=0 || atr<=0)
      return false;

   double distance=
      GetNearestSupportDistance(price);

   if(distance<0)
      return false;

   // ATR 0.5以内ならサポート近辺
   return (distance<=atr*0.50);
  }

bool SellResistanceConfirmation()
  {
   double price=GetBid();

   double atr=GetATR(PERIOD_M1,14,1);

   if(price<=0 || atr<=0)
      return false;

   double distance=
      GetNearestResistanceDistance(price);

   if(distance<0)
      return false;

   return (distance<=atr*0.50);
  }

bool BuyTrendLineConfirmation() {return NearTrend(true);}

bool SellTrendLineConfirmation() {return NearTrend(false);}

void UpdateAllAutoLines()
  {
   UpdateAutoHorizontalLines();

   UpdateAutoTrendLines();

   if(m_isChart) ChartRedraw();
  }

double CalculateLineScore(
   ENUM_ENTRY_DIRECTION direction)
  {
   double score=0.0;

   if(direction==ENTRY_BUY)
     {
      if(BuySupportConfirmation())
         score+=10.0;

      if(BuyTrendLineConfirmation())
         score+=10.0;
     }

   else if(direction==ENTRY_SELL)
     {
      if(SellResistanceConfirmation())
         score+=10.0;

      if(SellTrendLineConfirmation())
         score+=10.0;
     }

   return MathMin(score,20.0);
  }

double GetPatternScore(
   PatternSignal &pattern)
  {
   if(pattern.type==PATTERN_NONE)
      return 0.0;

   double score=
      pattern.patternStrength;

   if(score<=0.0)
      score=70.0;

   if(score>100.0)
      score=100.0;

   return score;
  }

double CalculateFinalBuyScore(PatternSignal &p,MTFResult &r[])
{return FinalSignalScore(CalculateBuyMTFScore(r),GetPatternScore(p),CalculateLineScore(ENTRY_BUY));}

double CalculateFinalSellScore(PatternSignal &p,MTFResult &r[])
{return FinalSignalScore(CalculateSellMTFScore(r),GetPatternScore(p),CalculateLineScore(ENTRY_SELL));}

bool BuySignalOK(PatternSignal &p,MTFResult &r[])
{return PatternDirection(p)==ENTRY_BUY && WeightedSignalOK(r,true);}

bool SellSignalOK(PatternSignal &p,MTFResult &r[])
{return PatternDirection(p)==ENTRY_SELL && WeightedSignalOK(r,false);}

string PositionKey(ulong id,string suffix)
{ return g_statePrefix+StringFormat("%I64u",id)+suffix; }

double StateGet(string key,double fallback=0)
{ return GlobalVariableCheck(key)?GlobalVariableGet(key):fallback; }

bool PositionIdOpen(ulong id)
{
 for(int i=0;i<PositionsTotal();i++)
  if(PositionGetTicket(i)>0 && (ulong)PositionGetInteger(POSITION_IDENTIFIER)==id) return true;
 return false;
}

bool PositionResult(ulong id,double &net,double &initialMoney,double &distance,datetime &closed,bool &ours)
{
 net=0; initialMoney=0; distance=0; closed=0; ours=false;
 if(!HistorySelectByPosition(id)) return false;
 double vin=0,vout=0,weightedDistance=0;
 bool mixed=false;
 for(int i=0;i<HistoryDealsTotal();i++)
 {
  ulong d=HistoryDealGetTicket(i);
  long dt=HistoryDealGetInteger(d,DEAL_TYPE);
  if(dt!=DEAL_TYPE_BUY && dt!=DEAL_TYPE_SELL) continue;
  if(HistoryDealGetString(d,DEAL_SYMBOL)!=m_symbol) { mixed=true; continue; }
  long entry=HistoryDealGetInteger(d,DEAL_ENTRY);
  double v=HistoryDealGetDouble(d,DEAL_VOLUME);
  net+=HistoryDealGetDouble(d,DEAL_PROFIT)+HistoryDealGetDouble(d,DEAL_SWAP)
      +HistoryDealGetDouble(d,DEAL_COMMISSION)+HistoryDealGetDouble(d,DEAL_FEE);
  if(entry==DEAL_ENTRY_INOUT) mixed=true;
  if(entry==DEAL_ENTRY_IN)
  {
   if((ulong)HistoryDealGetInteger(d,DEAL_MAGIC)==MagicNumber) ours=true;
   else mixed=true;
   vin+=v;
   double open=HistoryDealGetDouble(d,DEAL_PRICE),sl=HistoryDealGetDouble(d,DEAL_SL),p=0;
   if(sl<=0)
   {
    ulong order=(ulong)HistoryDealGetInteger(d,DEAL_ORDER);
    sl=HistoryOrderGetDouble(order,ORDER_SL);
   }
   bool correct=(dt==DEAL_TYPE_BUY ? sl>0 && sl<open : sl>open);
   if(correct && OrderCalcProfit((ENUM_ORDER_TYPE)(dt==DEAL_TYPE_BUY?ORDER_TYPE_BUY:ORDER_TYPE_SELL),m_symbol,v,open,sl,p))
   {
    initialMoney+=MathAbs(p);
    weightedDistance+=MathAbs(open-sl)*v;
   }
  }
  if(entry==DEAL_ENTRY_OUT || entry==DEAL_ENTRY_OUT_BY)
  {
   vout+=v;
   closed=(datetime)MathMax((long)closed,HistoryDealGetInteger(d,DEAL_TIME));
  }
 }
 if(mixed) { ours=false; return false; }
 if(vin>0) distance=weightedDistance/vin;
 // Preserve actual entry-time account-currency risk where available.
 // Entry-time money is scaled by total opening volume, including partial fills.
 double unitMoney=StateGet(PositionKey(id,".unit"));
 if(unitMoney>0) initialMoney=unitMoney*vin;
 distance=StateGet(PositionKey(id,".r"),distance);
 return ours && vin>0 && MathAbs(vin-vout)<1e-7 && closed>0;
}

void RefreshHistory()
{
 g_historyOK=false;
 if(!HistorySelect(0,TimeCurrent())) return;
 // Identify original ownership first so manual exits are included without using exit magic.
 ulong ownIds[];
 for(int i=0;i<HistoryDealsTotal();i++)
 {
  ulong d=HistoryDealGetTicket(i);
  if(HistoryDealGetString(d,DEAL_SYMBOL)!=m_symbol || (ulong)HistoryDealGetInteger(d,DEAL_MAGIC)!=MagicNumber ||
     HistoryDealGetInteger(d,DEAL_ENTRY)!=DEAL_ENTRY_IN) continue;
  ulong id=(ulong)HistoryDealGetInteger(d,DEAL_POSITION_ID);
  int n=ArraySize(ownIds);ArrayResize(ownIds,n+1);ownIds[n]=id;
 }
 if(ArraySize(ownIds)>0) ArraySort(ownIds);
 ulong ids[];
 for(int i=HistoryDealsTotal()-1;i>=0 && ArraySize(ids)<HistoryTradeLimit;i--)
 {
  ulong d=HistoryDealGetTicket(i);
  if(HistoryDealGetString(d,DEAL_SYMBOL)!=m_symbol) continue;
  long e=HistoryDealGetInteger(d,DEAL_ENTRY);
  if(e!=DEAL_ENTRY_OUT && e!=DEAL_ENTRY_OUT_BY) continue;
  ulong id=(ulong)HistoryDealGetInteger(d,DEAL_POSITION_ID);
  if(id==0 || ArraySize(ownIds)==0 || PositionIdOpen(id)) continue;
  int found=ArrayBsearch(ownIds,id);
  if(found<0 || ownIds[found]!=id) continue;
  bool seen=false;
  for(int k=0;k<ArraySize(ids);k++) if(ids[k]==id) {seen=true;break;}
  if(seen) continue;
  int n=ArraySize(ids);ArrayResize(ids,n+1);ids[n]=id;
 }
 ArrayResize(g_returns,0);g_consecutiveLosses=0;g_consecutiveWins=0;
 int wins=0,decisive=0;
 for(int i=ArraySize(ids)-1;i>=0;i--)
 {
  double net,money,distance;datetime closed;bool ours;
  if(!PositionResult(ids[i],net,money,distance,closed,ours)) continue;
  if(MathAbs(net)>BreakEvenMoneyTolerance)
  {
   decisive++;if(net>0) wins++;
   if(closed>=LossStreakResetTime)
   {
    if(net>0) {g_consecutiveWins++;g_consecutiveLosses=0;}
    else {g_consecutiveLosses++;g_consecutiveWins=0;}
   }
  }
  if(money>0 && MathIsValidNumber(net/money))
  {
   int n=ArraySize(g_returns);ArrayResize(g_returns,n+1);g_returns[n]=net/money;
  }
 }
 g_sampleCount=ArraySize(g_returns);
 g_winRate=decisive>0?(double)wins/decisive:0;
 g_historyDirty=false;g_historyOK=true;g_lastHistory=TimeCurrent();
}

double LimitRisk(double risk) { return ClampRisk(risk); }

double CalculateFixedAdjustedRisk(double score)
{
 if(StopAfterConsecutiveLosses>0 && g_consecutiveLosses>=StopAfterConsecutiveLosses) return 0;
 double risk=BaseRiskPercent;
 if(g_consecutiveLosses>=5) risk=MathMin(risk,RiskAfter5Loss);
 else if(g_consecutiveLosses>=4) risk=MathMin(risk,RiskAfter4Loss);
 else if(g_consecutiveLosses>=3) risk=MathMin(risk,RiskAfter3Loss);
 else if(g_consecutiveLosses>=2) risk=MathMin(risk,RiskAfter2Loss);
 if(score>=90) risk=MathMin(risk,RiskScore90);
 else if(score>=80) risk=MathMin(risk,RiskScore80);
 else if(score>=70) risk=MathMin(risk,RiskScore70);
 return LimitRisk(risk);
}

double CalculateMonteCarlo95DD(double risk)
{
 if(ArraySize(g_returns)==0) return 100;
 double dds[];ArrayResize(dds,MonteCarloRuns);
 // Identical samples for all candidate risk levels; deterministic tester runs.
 MathSrand(MonteCarloSeed);
 for(int run=0;run<MonteCarloRuns;run++)
 {
  double equity=100,peak=100,dd=0;
  for(int t=0;t<MonteCarloTrades;t++)
  {
   uint rnd=((uint)MathRand()<<15)|(uint)MathRand();
   int k=(int)(rnd%(uint)ArraySize(g_returns));
   equity*=MathMax(0.0,1.0+risk/100.0*g_returns[k]);
   peak=MathMax(peak,equity);
   dd=MathMax(dd,(peak-equity)/peak*100.0);
   if(equity<=0) break;
  }
  dds[run]=dd;
 }
 ArraySort(dds);
 return dds[(int)MathCeil(0.95*MonteCarloRuns)-1];
}

void UpdateMonteCarloRisk(bool force=false)
{
 if(RiskMode==RISK_FIXED_ADJUST || !EnableMonteCarlo) return;
 if(force) m_mcActive=false;
 if(m_mcActive || (!force && g_mcReady && TimeCurrent()-g_lastMC<MonteCarloRecalculateMinutes*60)) return;
 g_mcReady=false;g_mcAllowed=false;g_mcRisk=0;
 if(g_sampleCount<MonteCarloMinimumSamples)
 {g_mcRisk=LimitRisk(BaseRiskPercent);g_mcReady=true;g_mcAllowed=g_mcRisk>0;g_lastMC=TimeCurrent();return;}
 if(g_winRate<MonteCarloMinimumWinRate)
 {g_mcReady=true;g_lastMC=TimeCurrent();return;}
 if(ArrayCopy(m_mcReturns,g_returns)!=ArraySize(g_returns) || ArrayResize(m_mcDDs,MonteCarloRuns)!=MonteCarloRuns) return;
 m_mcCandidate=(int)MathFloor((MaximumRiskPercent-MinimumRiskPercent)/MonteCarloRiskStep+1e-8);
 m_mcRun=0;m_mcTrade=0;m_mcEquity=100;m_mcPeak=100;m_mcDD=0;
 m_mcRandom=(uint)MonteCarloSeed;if(m_mcRandom==0) m_mcRandom=1;
 m_mcActive=true;
}

datetime UTCNow()
{
 if(MQLInfoInteger(MQL_TESTER)) return TimeCurrent()-TesterServerUTCOffsetHours*3600;
 return TimeGMT();
}

int UTCDay(datetime t) {return (int)((long)t/86400);}

double DailyLimit()
{ return (FintokeiPlan==FINTOKEI_PROTRADER || FintokeiPlan==FINTOKEI_PROTRADER_SWING)?5.0:3.0; }

double OverallLimit()
{ return (FintokeiPlan==FINTOKEI_PROTRADER || FintokeiPlan==FINTOKEI_PROTRADER_SWING)?10.0:6.0; }

bool SavePropDay(int day,double reference)
{
 if(reference<=0) return false;
 string key=g_propPrefix+"ref."+IntegerToString(day);
 // One prop EA per account/terminal; do not overwrite an already established day.
 if(GlobalVariableCheck(key)) reference=GlobalVariableGet(key);
 else if(GlobalVariableSet(key,reference)==0) return false;
 g_propDay=day;g_dailyReference=reference;
 GlobalVariablesFlush();return true;
}

void UpdatePropDay()
{
 if(AccountMode!=FINTOKEI) return;
 datetime now=UTCNow();int day=UTCDay(now);
 double equity=AccountInfoDouble(ACCOUNT_EQUITY),balance=AccountInfoDouble(ACCOUNT_BALANCE);
 if(day!=g_propDay)
 {
  g_propDay=day;g_dailyReference=0;
  string key=g_propPrefix+"ref."+IntegerToString(day);
  if(GlobalVariableCheck(key)) g_dailyReference=GlobalVariableGet(key);
  else if(FintokeiDailyReference>0 && UTCDay(FintokeiReferenceDateUTC)==day)
   SavePropDay(day,FintokeiDailyReference);
  else if(MQLInfoInteger(MQL_TESTER) && g_lastObservedUTC==0)
   SavePropDay(day,FintokeiPlan==FINTOKEI_PROTRADER_SWING?balance:equity);
  else if(g_lastObservedUTC>0 && UTCDay(g_lastObservedUTC)==day-1 && now-g_lastObservedUTC<=5 && (long)now%86400<=5)
  {
   // Conservative adjacent snapshots. Exact official baseline can differ with open trades.
   double ref=FintokeiPlan==FINTOKEI_PROTRADER_SWING?
     MathMax(balance,g_lastObservedBalance):MathMax(equity,g_lastObservedEquity);
   SavePropDay(day,ref);
  }
 }
 g_lastObservedUTC=now;g_lastObservedEquity=equity;g_lastObservedBalance=balance;
}

double DailyFloor()
{ return g_dailyReference*(1.0-DailyLimit()*FintokeiSafetyMargin/100.0); }

double OverallFloor()
{ return FintokeiInitialBalance*(1.0-OverallLimit()*FintokeiSafetyMargin/100.0); }

void UpdatePropProtection()
{
 if(AccountMode!=FINTOKEI) return;
 UpdatePropDay();
 double equity=AccountInfoDouble(ACCOUNT_EQUITY);
 string ds=g_propPrefix+"stop."+IntegerToString(g_propDay),os=g_propPrefix+"overall";
 if(equity<=OverallFloor()) GlobalVariableSet(os,1);
 if(g_dailyReference>0 && equity<=DailyFloor()) GlobalVariableSet(ds,1);
 g_propStop=StateGet(os)>0?2:(StateGet(ds)>0?1:0);
 if(g_propStop>0)
 {
  
  if(TimeCurrent()==m_lastCloseAttempt) return;
  m_lastCloseAttempt=TimeCurrent();
  // Retry rejected closes on following timer/tick; never clear the stop latch on recovery.
  for(int i=PositionsTotal()-1;i>=0;i--)
  {
   ulong t=PositionGetTicket(i);
   if(t==0 || PositionGetString(POSITION_SYMBOL)!=m_symbol || (ulong)PositionGetInteger(POSITION_MAGIC)!=MagicNumber) continue;
   if(!SolePositionOwner(t)) continue;
   ulong logId=(ulong)PositionGetInteger(POSITION_IDENTIFIER);
   bool ok=trade.PositionClose(t,DeviationPoints());
   if(!ok || (trade.ResultRetcode()!=TRADE_RETCODE_DONE && trade.ResultRetcode()!=TRADE_RETCODE_DONE_PARTIAL))
    Print("DD close not completed: ",trade.ResultRetcodeDescription());
   else JournalMarkDD(logId);
  }
  GlobalVariablesFlush();
 }
}

bool OpenRiskReserve(double &reserve)
{
 reserve=0;
 if(OrdersTotal()>0) return false; // Unknown pending exposure blocks a new prop entry.
 for(int i=0;i<PositionsTotal();i++)
 {
  if(PositionGetTicket(i)==0) return false;
  string symbol=PositionGetString(POSITION_SYMBOL);
  double sl=PositionGetDouble(POSITION_SL),v=PositionGetDouble(POSITION_VOLUME),p=0;
  if(sl<=0) return false;
  MqlTick tick;if(!SymbolInfoTick(symbol,tick)) return false;
  bool buy=PositionGetInteger(POSITION_TYPE)==POSITION_TYPE_BUY;
  double current=buy?tick.bid:tick.ask;
  if(!OrderCalcProfit(buy?ORDER_TYPE_BUY:ORDER_TYPE_SELL,symbol,v,current,sl,p)) return false;
  reserve+=MathMax(0.0,-p);
 }
 return true;
}

double PropRiskCap()
{
 if(AccountMode!=FINTOKEI) return MaximumRiskPercent;
 UpdatePropProtection();
 if(g_propStop>0 || g_dailyReference<=0) return 0;
 if(!g_accountHistoryOK || g_accountLossStreak>=FintokeiMaxConsecutiveLosses || g_consecutiveLosses>=FintokeiMaxConsecutiveLosses) return 0;
 double equity=AccountInfoDouble(ACCOUNT_EQUITY),reserve=0;
 if(equity<=0 || !OpenRiskReserve(reserve)) return 0;
 double remaining=MathMin(equity-DailyFloor(),equity-OverallFloor())-reserve
   -FintokeiInitialBalance*FintokeiExtraReservePercent/100.0;
 if(remaining<=0) return 0;
 double dailyRatio=MathMax(0.0,(g_dailyReference-equity)/g_dailyReference*100.0/DailyLimit());
 double overallRatio=MathMax(0.0,(FintokeiInitialBalance-equity)/FintokeiInitialBalance*100.0/OverallLimit());
 double risk=FintokeiMaxRiskPerTrade;
 if(dailyRatio>=0.5) risk*=0.5;
 if(dailyRatio>=0.7) risk*=0.5;
 if(overallRatio>=0.5) risk*=0.5;
 if(overallRatio>=0.7) risk*=0.5;
 return MathMin(risk,remaining/equity*100.0);
}

double CalculateFinalRisk(double score)
{
 if(!g_historyOK) return 0;
 double fixed=CalculateFixedAdjustedRisk(score),risk=fixed;
 if(RiskMode!=RISK_FIXED_ADJUST)
 {
  if(!g_mcReady || !g_mcAllowed) return 0;
  risk=RiskMode==RISK_MONTE_CARLO?g_mcRisk:MathMin(fixed,g_mcRisk);
 }
 return LimitRisk(MathMin(risk,PropRiskCap()));
}

double PriceFloor(double p)
{
 double tick=SymbolInfoDouble(m_symbol,SYMBOL_TRADE_TICK_SIZE);
 if(tick<=0) return 0;
 return NormalizeDouble(MathFloor(p/tick+1e-9)*tick,m_digits);
}

double PriceCeil(double p)
{
 double tick=SymbolInfoDouble(m_symbol,SYMBOL_TRADE_TICK_SIZE);
 if(tick<=0) return 0;
 return NormalizeDouble(MathCeil(p/tick-1e-9)*tick,m_digits);
}

bool EntryExposureBlocked()
{
 bool netting=AccountInfoInteger(ACCOUNT_MARGIN_MODE)!=ACCOUNT_MARGIN_MODE_RETAIL_HEDGING;
 for(int i=0;i<PositionsTotal();i++)
 {
  if(PositionGetTicket(i)==0 || PositionGetString(POSITION_SYMBOL)!=m_symbol) continue;
  if(netting || OnePositionPerSymbol) return true;
 }
 for(int i=0;i<OrdersTotal();i++)
 {
  if(OrderGetTicket(i)>0 && OrderGetString(ORDER_SYMBOL)==m_symbol) return true;
 }
 return false;
}

bool BuildStops(bool buy,MqlTick &tick,double &sl,double &tp)
{
 int shift=-1;double price=0;
 if(UseSwingStopLoss)
 {
  bool ok=buy?GetLatestSwingLow(PERIOD_M1,SwingDepth,PatternLookbackBars,shift,price):
              GetLatestSwingHigh(PERIOD_M1,SwingDepth,PatternLookbackBars,shift,price);
  if(DiagReject(!ok,"swing_not_found")) return false;
 }
 else
 {
  shift=buy?iLowest(m_symbol,PERIOD_M1,MODE_LOW,StopSwingLookback,1):
            iHighest(m_symbol,PERIOD_M1,MODE_HIGH,StopSwingLookback,1);
  if(DiagReject(shift<1,"swing_index_missing")) return false;
  price=buy?iLow(m_symbol,PERIOD_M1,shift):iHigh(m_symbol,PERIOD_M1,shift);
 }
 double entry=buy?tick.ask:tick.bid;
 if(DiagReject(price<=0,"swing_price_invalid") || DiagReject((buy?price>=entry:price<=entry),"swing_wrong_side")) return false;
 double minDistance=(double)SymbolInfoInteger(m_symbol,SYMBOL_TRADE_STOPS_LEVEL)*m_point
   +SymbolInfoDouble(m_symbol,SYMBOL_TRADE_TICK_SIZE);
 if(buy)
 {
  sl=PriceFloor(MathMin(price-StopBuffer(),tick.bid-minDistance));
  tp=PriceCeil(entry+(entry-sl)*RiskRewardRatio);
  if(DiagReject(tp<tick.bid+minDistance,"tp_broker_gap")) return false;
 }
 else
 {
  sl=PriceCeil(MathMax(price+StopBuffer(),tick.ask+minDistance));
  tp=PriceFloor(entry-(sl-entry)*RiskRewardRatio);
  if(DiagReject(tp>tick.ask-minDistance,"tp_broker_gap")) return false;
 }
 return DiagPass(sl>0,"invalid_sl") && DiagPass(tp>0,"invalid_tp");
}

double CalculateLotByRisk(bool buy,MqlTick &tick,double sl,double riskPercent)
{
 if(!SpreadOK(tick,sl,buy)) return 0;

 if(DiagReject(riskPercent<=0,"risk_limit")) return 0;
 double money=AccountInfoDouble(ACCOUNT_EQUITY)*riskPercent/100.0;
 double testLot=SymbolInfoDouble(m_symbol,SYMBOL_VOLUME_MIN),profit=0;
 double entry=buy?tick.ask+DeviationPoints()*m_point:tick.bid-DeviationPoints()*m_point;
 double exit=buy?sl-StopSlippage():sl+StopSlippage();
 if(DiagReject(testLot<=0,"broker_min_lot_invalid") || DiagReject(exit<=0,"sizing_exit_invalid") || DiagReject(!OrderCalcProfit(buy?ORDER_TYPE_BUY:ORDER_TYPE_SELL,m_symbol,testLot,entry,exit,profit),"profit_calculation_failed")) return 0;
 double lossPerLot=MathAbs(profit)/testLot+RoundTurnCommissionPerLot;
 if(DiagReject(lossPerLot<=0,"loss_per_lot_invalid")) return 0;
 double lot=NormalizeVolume(MathMin(money/lossPerLot,AvailableDirectionalVolume(buy)));
 if(lot<=0) return 0;
 double margin=0;
 if(DiagReject(!OrderCalcMargin(buy?ORDER_TYPE_BUY:ORDER_TYPE_SELL,m_symbol,lot,entry,margin),"margin_calculation_failed")) return 0;
 double free=AccountInfoDouble(ACCOUNT_MARGIN_FREE)*0.95;
 if(margin>free && margin>0) {lot=NormalizeVolume(lot*free/margin);if(m_diagActive && lot<=0) m_diagReason="insufficient_margin_min_lot";}
 // Never raise to broker minimum: zero means skip the trade.
 return lot;
}

bool HasUnresolvedOrder()
{return StateGet(g_statePrefix+"ord.state")>0 || StateGet(g_statePrefix+"manual.pending")>0 || AIState(AccountIntent(m_symbol))>0;}

string PendingOrderToken()
{return AIHex((uint)StateGet(g_statePrefix+"ord.tag.hi"))+AIHex((uint)StateGet(g_statePrefix+"ord.tag.lo"));}

string PendingOrderComment() {return "MT3#"+PendingOrderToken();}

bool ClearPendingOrder()
{
 bool ok=GlobalVariableSet(g_statePrefix+"ord.state",0)>0;
 ok=GlobalVariableSet(g_statePrefix+"manual.pending",0)>0 && ok;
 GlobalVariablesFlush();
 if(ok) ok=GlobalVariableSet(AccountIntent(m_symbol),0)>0;
 GlobalVariablesFlush();return ok && !HasUnresolvedOrder();
}

bool BeginPendingOrder()
{
 if(HasUnresolvedOrder()) return false;
 ulong tag=((ulong)(uint)TimeLocal()<<32)|(ulong)(uint)GetMicrosecondCount();
 // Mix a time/chart/sequence ID into the intent tag to distinguish fast restarts.
 tag^=(ulong)AIHash(NewAIId());
 bool ok=SaveU64(g_statePrefix+"ord.tag",tag);
 ok=SaveU64(g_statePrefix+"ord.ticket",0) && ok;
 ok=SaveU64(g_statePrefix+"ord.deal",0) && ok;
 ok=GlobalVariableSet(g_statePrefix+"ord.at",(double)TimeCurrent())>0 && ok;
 ok=GlobalVariableSet(g_statePrefix+"ord.legacy",0)>0 && ok;
 if(!ok) return false;
 if(GlobalVariableSet(AccountIntent(m_symbol),1)==0) return false;
 if(GlobalVariableSet(g_statePrefix+"ord.state",1)==0) {GlobalVariablesFlush();return false;}
 GlobalVariablesFlush();return true; // Intent must be durable before OrderSend.
}

bool DefinitiveEntryRejection(uint rc)
{
 switch(rc)
 {
  case TRADE_RETCODE_REQUOTE:case TRADE_RETCODE_REJECT:case TRADE_RETCODE_INVALID:
  case TRADE_RETCODE_INVALID_VOLUME:case TRADE_RETCODE_INVALID_PRICE:case TRADE_RETCODE_INVALID_STOPS:
  case TRADE_RETCODE_TRADE_DISABLED:case TRADE_RETCODE_MARKET_CLOSED:case TRADE_RETCODE_NO_MONEY:
  case TRADE_RETCODE_PRICE_CHANGED:case TRADE_RETCODE_PRICE_OFF:case TRADE_RETCODE_INVALID_EXPIRATION:
  case TRADE_RETCODE_TOO_MANY_REQUESTS:case TRADE_RETCODE_INVALID_FILL:
  case TRADE_RETCODE_SERVER_DISABLES_AT:case TRADE_RETCODE_CLIENT_DISABLES_AT:
   return true;
 }
 return false; // Unknown server outcomes are never treated as definite rejection.
}

bool PendingHistoryOrderFinal(ulong ticket)
{
 if(!HistoryOrderSelect(ticket) || HistoryOrderGetString(ticket,ORDER_SYMBOL)!=m_symbol ||
    (ulong)HistoryOrderGetInteger(ticket,ORDER_MAGIC)!=MagicNumber) return false;
 long state=HistoryOrderGetInteger(ticket,ORDER_STATE);
 bool terminal=state==ORDER_STATE_FILLED || state==ORDER_STATE_CANCELED || state==ORDER_STATE_REJECTED || state==ORDER_STATE_EXPIRED;
 if(!terminal) return false;
 double filled=HistoryOrderGetDouble(ticket,ORDER_VOLUME_INITIAL)-HistoryOrderGetDouble(ticket,ORDER_VOLUME_CURRENT);
 if(state!=ORDER_STATE_FILLED && filled<=1e-8) return true;
 // A final order report can arrive before the position. Retain reservation until exposure is visible.
 ulong id=(ulong)HistoryOrderGetInteger(ticket,ORDER_POSITION_ID);
 if(id==0) return false;
 if(PositionIdOpen(id)) return true;
 double net,money,distance;datetime closed;bool ours;
 return PositionResult(id,net,money,distance,closed,ours) && ours;
}

void ReconcilePendingOrder()
{
 if(!HasUnresolvedOrder()) return;
 // v2.40 manual uncertainty has no correlation ID. It needs explicit reconciliation.
 if(StateGet(g_statePrefix+"ord.state")==0 && StateGet(g_statePrefix+"manual.pending")>0)
 {
  ulong tag=((ulong)(uint)TimeLocal()<<32)|(ulong)AIHash(NewAIId());
  if(!SaveU64(g_statePrefix+"ord.tag",tag)) return;
  GlobalVariableSet(g_statePrefix+"ord.legacy",1);GlobalVariableSet(g_statePrefix+"ord.state",2);GlobalVariablesFlush();
 }
 ulong ticket=LoadU64(g_statePrefix+"ord.ticket");
 if(StateGet(g_statePrefix+"ord.legacy")==0)
 {
  ulong deal=LoadU64(g_statePrefix+"ord.deal");
  if(ticket==0 && deal>0 && HistoryDealSelect(deal) && HistoryDealGetString(deal,DEAL_SYMBOL)==m_symbol &&
     (ulong)HistoryDealGetInteger(deal,DEAL_MAGIC)==MagicNumber && HistoryDealGetInteger(deal,DEAL_ENTRY)==DEAL_ENTRY_IN)
  {
   ticket=(ulong)HistoryDealGetInteger(deal,DEAL_ORDER);
   if(ticket>0) {SaveU64(g_statePrefix+"ord.ticket",ticket);GlobalVariablesFlush();}
  }
  if(ticket>0 && OrderSelect(ticket)) return; // Working/partially filled order still active.
  if(ticket>0 && PendingHistoryOrderFinal(ticket))
  {if(ClearPendingOrder()) g_historyDirty=true;return;}
  string tag=PendingOrderComment();
  for(int i=0;i<OrdersTotal();i++)
  {
   ulong order=OrderGetTicket(i);
   if(order>0 && OrderGetString(ORDER_SYMBOL)==m_symbol && (ulong)OrderGetInteger(ORDER_MAGIC)==MagicNumber && OrderGetString(ORDER_COMMENT)==tag)
   {SaveU64(g_statePrefix+"ord.ticket",order);GlobalVariablesFlush();return;}
  }
  datetime at=(datetime)StateGet(g_statePrefix+"ord.at");
  if(at>0 && HistorySelect((datetime)MathMax(0,(long)at-300),TimeCurrent()))
  {
   ulong found=0;
   for(int i=HistoryOrdersTotal()-1;i>=0;i--)
   {
    ulong order=HistoryOrderGetTicket(i);
    if(HistoryOrderGetString(order,ORDER_SYMBOL)==m_symbol && (ulong)HistoryOrderGetInteger(order,ORDER_MAGIC)==MagicNumber && HistoryOrderGetString(order,ORDER_COMMENT)==tag)
    {found=order;break;}
   }
   if(found>0)
   {
    SaveU64(g_statePrefix+"ord.ticket",found);GlobalVariablesFlush();
    if(!OrderSelect(found) && PendingHistoryOrderFinal(found)) {if(ClearPendingOrder()) g_historyDirty=true;}
    return;
   }
  }
 }
 // Absence in the terminal is not proof that the broker rejected the order.
 // A user may release only this exact unresolved intent after broker reconciliation.
 if(ReconciledOrderToken!="" && ReconciledOrderToken==PendingOrderToken() &&
    TerminalInfoInteger(TERMINAL_CONNECTED) && CountOurPositions()==0)
 {
  for(int i=0;i<OrdersTotal();i++) if(OrderGetTicket(i)>0 && OrderGetString(ORDER_SYMBOL)==m_symbol) return;
  if(!HistorySelect(0,TimeCurrent())) return;
  if(ClearPendingOrder()) {g_historyDirty=true;Print("Order uncertainty released with one-use reconciliation token: ",ReconciledOrderToken);}
 }
}

void RefreshEntryState()
{
 ReconcilePendingOrder();bool changed=g_historyDirty;
 CaptureInitialRisks();RefreshHistory();
 if(g_historyOK) UpdateMonteCarloRisk(changed);
}

bool EntryPreflight(bool manual)
{
 if(!manual && !InUniverseNow()) {g_status="Symbol outside entry universe";return DiagPass(false,"outside_universe");}
 if(AnyAccountUnresolved()) {g_status="Account has an unresolved order";return DiagPass(false,"account_unresolved_order");}

 if(!EntryModeAllowed(manual)) {g_status="Selected execution mode does not allow this entry";return DiagPass(false,"entry_mode");}
 if(HasUnresolvedOrder()) {g_status="ORDER UNRESOLVED | reconcile token "+PendingOrderToken();return DiagPass(false,"symbol_unresolved_order");}
 if(EntryExposureBlocked()) {g_status="Existing exposure blocks entry";return DiagPass(false,"existing_exposure");}
 if((!MQLInfoInteger(MQL_TESTER) && !TerminalInfoInteger(TERMINAL_CONNECTED)) || !TerminalInfoInteger(TERMINAL_TRADE_ALLOWED) || !MQLInfoInteger(MQL_TRADE_ALLOWED) ||
    !AccountInfoInteger(ACCOUNT_TRADE_ALLOWED) || !AccountInfoInteger(ACCOUNT_TRADE_EXPERT))
 {g_status="Trading permission or broker connection is OFF";return DiagPass(false,"trading_permission");}
 if(!g_historyOK) {g_status="Waiting for trade history";return DiagPass(false,"history_wait");}
 double risk=RiskMode==RISK_MONTE_CARLO?MaximumRiskPercent:ManualFixedRisk(); // Score-independent base and loss cap, also used for AI preflight.
 if(RiskMode!=RISK_FIXED_ADJUST)
 {
  if(!g_mcReady || !g_mcAllowed) {g_status="Monte Carlo blocks entry";return DiagPass(false,"monte_carlo");}
  risk=RiskMode==RISK_MONTE_CARLO?g_mcRisk:MathMin(risk,g_mcRisk);
 }
 if(MathMin(risk,PropRiskCap())<=0) {g_status="Risk / loss-streak / DD protection blocked entry";return DiagPass(false,"risk_limit");}
 return true;
}

string TFName(ENUM_TIMEFRAMES tf) {return EnumToString(tf);}

bool BuildAISnapshot(MTFResult &results[],bool hybrid,bool proposedBuy,double localScore,string patternName,MqlTick &tick,string &snapshot)
{
 MqlRates bars[];ArraySetAsSeries(bars,true);
 if(CopyRates(m_symbol,PERIOD_M1,1,OpenAIM1Bars,bars)!=OpenAIM1Bars || !MTFSnapshotCurrent()) return false;
 double atr=GetATR(PERIOD_M1,14,1);if(atr<=0) return false;
 snapshot=StringFormat("symbol=%s; bid=%.*f; ask=%.*f; spread/ATR=%.5f; local_proposal=%s; local_score=%.2f; pattern=%s; ",
  m_symbol,m_digits,tick.bid,m_digits,tick.ask,(tick.ask-tick.bid)/atr,proposedBuy?"BUY":"SELL",localScore,patternName);
 snapshot+="MTF CLOSED-bar indicators; scores below are signed evidence [-100,100]: ";
 for(int i=0;i<ArraySize(results);i++)
 {
  int f,s,g;MACDParameters(results[i].timeframe,f,s,g);
  snapshot+=StringFormat("%s{weight=%.0f,ema%d=%.*f,ema%d=%.*f,ema%d=%.*f,ATR=%.8g,slopeATR=%.5f,adx=%.2f,+di=%.2f,-di=%.2f,macd(%d,%d,%d)=%.8g,signal=%.8g,trend=%.2f,macdScore=%.2f}; ",
   TFName(results[i].timeframe),MT3Weight(results[i].timeframe),EMAFastPeriod,m_digits,results[i].emaFast,
   EMAMiddlePeriod,m_digits,results[i].emaMiddle,EMASlowPeriod,m_digits,results[i].emaSlow,
   results[i].atr,results[i].slopeATR,results[i].adx,results[i].plusDI,results[i].minusDI,
   f,s,g,results[i].macdMain,results[i].macdSignal,results[i].trendScore,results[i].macdScore);
 }
 snapshot+="M1 CLOSED bars, newest first: ";
 for(int i=0;i<ArraySize(bars);i++)
  snapshot+=StringFormat("[%s O=%.*f H=%.*f L=%.*f C=%.*f V=%I64d] ",TimeToString(bars[i].time,TIME_DATE|TIME_MINUTES),
   m_digits,bars[i].open,m_digits,bars[i].high,m_digits,bars[i].low,m_digits,bars[i].close,bars[i].tick_volume);
 return true;
}

void CancelAIRequest()
{
 if(!g_aiRequest.active) return;
 FileDelete(AIFile(g_aiRequest.id,".req"),FILE_COMMON);FileDelete(AIFile(g_aiRequest.id,".res"),FILE_COMMON);
 if(AIState(g_aiRequest.registry+"busy")!=g_aiRequest.token) GlobalVariableSetOnCondition(g_aiRequest.registry+"slot",0,g_aiRequest.token);
 g_aiRequest.active=false;
}

bool AIContextFresh(PendingAIDecision &request)
{
 MqlTick tick;ulong now=GetTickCount64();
 return InUniverseNow() && request.bar>0 && request.bar==iTime(m_symbol,PERIOD_M1,0) &&
  now>=request.started && now-request.started<(ulong)OpenAIMaxDecisionAgeMs && FreshQuote(tick,OpenAIMaxQuoteAgeMs);
}

bool AIPriceFresh(PendingAIDecision &request,bool buy,MqlTick &tick)
{
 double before=buy?request.ask:request.bid,current=buy?tick.ask:tick.bid;
 double atr=GetATR(PERIOD_M1,14,1);if(before<=0 || current<=0 || atr<=0) return false;
 double limit=atr*OpenAIMaxPriceDriftATR;
 if(OpenAIMaxPriceDriftPoints>0) limit=MathMin(limit,OpenAIMaxPriceDriftPoints*m_point);
 return MathAbs(current-before)<=limit+TickSize()*1e-8;
}

bool StartAIRequest(MTFResult &results[],bool hybrid,bool buy,double score,PatternSignal &pattern)
{
 if(score<MinimumSignalScore || !WeightedSignalOK(results,buy) || !MTFSnapshotCurrent()) return false;

 if(g_aiRequest.active || !EntryPreflight(false)) return false;
 datetime bar=iTime(m_symbol,PERIOD_M1,0);
 if(bar<=0 || bar==g_aiLastBar || bar==g_lastTradeBar || bar==g_lastAttemptBar) return false;
 string registry=AIRegistry();ulong now=GetTickCount64();
 long worker=(long)LoadU64(registry+"chart");
 if(AIState(registry+"version")!=MT3_AI_PROTOCOL || AIState(registry+"owner")!=1 || AIState(registry+"lease")<(double)now || worker<=0)
 {g_aiLastDecision="Attach MTFAutoTrader_AI_Worker to another chart and set its API key";g_status=g_aiLastDecision;return false;}
 MqlTick tick;if(!FreshQuote(tick)) return false;
 double sl,tp;string slSource,slFallback;if(!BuildEntryStops(buy,tick,pattern,sl,tp,slSource,slFallback) || !SpreadOK(tick,sl,buy) || !PatternEntryLocationOK(pattern,tick,buy)) return false;
 double previewLot=CalculateLotByRisk(buy,tick,sl,CalculateFinalRisk(score)),before=0,planned=0;
 if(previewLot<=0 || !CheckPortfolioEntry(buy,tick,sl,previewLot,before,planned)) return false;
 string snapshot;if(!BuildAISnapshot(results,hybrid,buy,score,PatternName(pattern.type),tick,snapshot))
 {g_status="Waiting for complete M1 snapshot";return false;}
 if(bar!=iTime(m_symbol,PERIOD_M1,0) || !MTFSnapshotCurrent()) return false;
 string id=NewAIId();double token=(double)AIHash(id);if(token==0) token=1;
 if(!GlobalVariableSetOnCondition(registry+"slot",token,0)) {g_status="AI worker busy; waiting within this M1 bar";return false;}
 ZeroMemory(g_aiRequest);g_aiRequest.active=true;g_aiRequest.id=id;g_aiRequest.registry=registry;
 g_aiRequest.worker=worker;g_aiRequest.token=token;g_aiRequest.started=GetTickCount64();g_aiRequest.bar=bar;
 g_aiRequest.bid=tick.bid;g_aiRequest.ask=tick.ask;g_aiRequest.hybrid=hybrid;g_aiRequest.buy=buy;g_aiRequest.score=score;g_aiRequest.pattern=pattern;
 string body=BuildOpenAIRequest(OpenAIModel,OpenAIReasoningEffort,snapshot,true,buy);
 string request="{\"protocol\":242,\"id\":"+JsonQuote(id)+",\"chart\":"+JsonQuote(StringFormat("%I64d",ChartID()))+
  ",\"created_ms\":"+StringFormat("%I64u",g_aiRequest.started)+",\"max_age_ms\":"+IntegerToString(OpenAIMaxDecisionAgeMs)+",\"body\":"+JsonQuote(body)+"}";
 if(!WriteAIFile(AIFile(id,".req"),request) || !EventChartCustom(worker,MT3_AI_REQUEST_EVENT,ChartID(),token,id))
 {CancelAIRequest();g_status="AI request could not be queued";return false;}
 g_aiLastBar=bar;GlobalVariableSet(g_statePrefix+"ai.bar",(double)bar);GlobalVariablesFlush();
 g_aiLastDecision="AI request pending";g_status="Waiting for AI; position management remains active";return true;
}

void ProcessAIReply()
{
 if(!g_aiRequest.active) return;
 if(!AIContextFresh(g_aiRequest))
 {CancelAIRequest();g_aiLastDecision="AI request expired / M1 bar or quote changed";g_status=g_aiLastDecision;return;}
 string raw;if(!ReadAIFile(AIFile(g_aiRequest.id,".res"),raw)) return;
 PendingAIDecision saved=g_aiRequest;CancelAIRequest(); // Consume before validation/execution: duplicates cannot replay.
 CMT3Json j;string id,chart,status,decision,reason;double protocol,confidence;
 bool valid=j.Parse(raw) && j.Kind(0)==J_OBJECT && j.Count(0)==7 && j.GetNumber(0,"protocol",protocol) && protocol==MT3_AI_PROTOCOL &&
  j.GetString(0,"id",id) && id==saved.id && j.GetString(0,"chart",chart) && chart==StringFormat("%I64d",ChartID()) &&
  j.GetString(0,"status",status) && j.GetString(0,"decision",decision) && j.GetNumber(0,"confidence",confidence) &&
  j.GetString(0,"reason",reason) && MathIsValidNumber(confidence) && confidence>=0 && confidence<=1 && StringLen(reason)<=1024 &&
  (decision=="BUY" || decision=="SELL" || decision=="WAIT");
 if(!valid) {g_aiLastDecision="Invalid worker response; entry skipped";g_status=g_aiLastDecision;return;}
 bool fallback=status=="transport_error" && saved.hybrid && OpenAIFailOpen && decision=="WAIT" && confidence==0;
 if(status!="ok" && !fallback) {g_aiLastDecision="AI skipped: "+reason;g_status=g_aiLastDecision;return;}
 if(!fallback && (decision=="WAIT" || confidence<OpenAIMinConfidence || (decision!=(saved.buy?"BUY":"SELL"))))
 {g_aiLastDecision="AI veto / confidence below threshold: "+reason;g_status=g_aiLastDecision;return;}
 bool buy=fallback?saved.buy:decision=="BUY";
 RefreshEntryState();UpdatePropProtection();ManagePositions();
 MqlTick tick;
 if(!AIContextFresh(saved) || !SymbolInfoTick(m_symbol,tick) || !AIPriceFresh(saved,buy,tick))
 {g_aiLastDecision="AI result discarded: bar, age, quote or price drift limit";g_status=g_aiLastDecision;return;}
 if(!EntryPreflight(false) || saved.bar==g_lastTradeBar || saved.bar==g_lastAttemptBar) return;
 PatternSignal pattern=saved.pattern;double score=saved.score;
 if(saved.hybrid)
 {
  MTFResult current[];PatternSignal check;ZeroMemory(check);
  if(!AnalyzeAllTimeframes(current) || !SelectReversalPattern(current,check) || check.type!=pattern.type || PatternIdentity(check)!=PatternIdentity(pattern) ||
     PatternDirection(check)!=PatternDirection(pattern) || IsPatternAlreadyUsed(pattern) || (buy?!BuySignalOK(pattern,current):!SellSignalOK(pattern,current)))
  {g_status="Hybrid signal no longer valid";return;}
  pattern=check; // Keep all concurrently matched structure claims after revalidation.
  score=buy?CalculateFinalBuyScore(pattern,current):CalculateFinalSellScore(pattern,current);
  if(score<MinimumSignalScore) {g_status="Hybrid score no longer sufficient";return;}
 }
 else
 {
  MTFResult current[];
  if(!AnalyzeAllTimeframes(current) || !WeightedSignalOK(current,buy)) return;
  score=WeightedMTFScore(current,buy);if(score<MinimumSignalScore) return;
  ZeroMemory(pattern);pattern.type=PATTERN_NONE;pattern.valid=true;pattern.buySignal=buy;pattern.sellSignal=!buy;
 }
 g_aiLastDecision=fallback?"HYBRID LOCAL FALLBACK (transport error)":StringFormat("AI %s score %.0f%% | %s",decision,confidence*100,reason);
 m_entryAIUsed=true;m_entryAIConfidence=confidence;m_entryAIResult=fallback?"LOCAL_FALLBACK: "+reason:decision+": "+reason;
 ExecuteEntry(buy,score,pattern,false,0,saved.bar,saved.started,buy?saved.ask:saved.bid);
 m_entryAIUsed=false;m_entryAIConfidence=-1;m_entryAIResult="";
}

void MarkAIBarUsed()
{
 g_lastTradeBar=iTime(m_symbol,PERIOD_M1,0); GlobalVariableSet(g_statePrefix+"bar",(double)g_lastTradeBar); GlobalVariablesFlush();
}

void MarkPatternUsed(PatternSignal &pattern)
{
 PersistPatternClaims(pattern);
 GlobalVariableSet(g_statePrefix+"pat.time",(double)pattern.secondTime);
 GlobalVariableSet(g_statePrefix+"pat.type",(double)pattern.type);
 GlobalVariableSet(g_statePrefix+"pat.side",(double)PatternDirection(pattern));
 g_lastTradeBar=iTime(m_symbol,PERIOD_M1,0);
 GlobalVariableSet(g_statePrefix+"bar",(double)g_lastTradeBar);
 GlobalVariablesFlush();
}

bool LegacyPatternAlreadyUsed(PatternSignal &pattern)
{
 if(StateGet(g_statePrefix+"pat.time")!=(double)pattern.secondTime) return false;
 int side=(int)StateGet(g_statePrefix+"pat.side");
 if(side==0)
 {
  // Recover direction from v2.00's stored enum values without resetting state.
  int type=(int)StateGet(g_statePrefix+"pat.type");
  if(type==PATTERN_DOUBLE_BOTTOM || type==PATTERN_INVERSE_HEAD_SHOULDERS || type==PATTERN_TRIPLE_BOTTOM) side=ENTRY_BUY;
  else if(type==PATTERN_DOUBLE_TOP || type==PATTERN_HEAD_SHOULDERS || type==PATTERN_TRIPLE_TOP) side=ENTRY_SELL;
 }
 return side==(int)PatternDirection(pattern);
}

void CaptureInitialRisks()
{
 bool changed=false;
 for(int i=PositionsTotal()-1;i>=0;i--)
 {
  ulong t=PositionGetTicket(i);
  if(t==0 || PositionGetString(POSITION_SYMBOL)!=m_symbol || (ulong)PositionGetInteger(POSITION_MAGIC)!=MagicNumber) continue;
  ulong id=(ulong)PositionGetInteger(POSITION_IDENTIFIER);
  if(GlobalVariableCheck(PositionKey(id,".r")) && GlobalVariableCheck(PositionKey(id,".unit"))) continue;
  double open=PositionGetDouble(POSITION_PRICE_OPEN),sl=PositionGetDouble(POSITION_SL),v=PositionGetDouble(POSITION_VOLUME);
  bool buy=PositionGetInteger(POSITION_TYPE)==POSITION_TYPE_BUY;
  // History preserves original SL when reattaching after SL has been trailed.
  double net,money,dist;datetime closed;bool ours;
  PositionResult(id,net,money,dist,closed,ours);
  if(!ours) continue;
  // If original history is unavailable, leave management inactive until it arrives.
  if(money<=0 && dist>0)
  {
   double p=0;
   if(OrderCalcProfit(buy?ORDER_TYPE_BUY:ORDER_TYPE_SELL,m_symbol,v,open,buy?open-dist:open+dist,p)) money=MathAbs(p);
  }
  if(dist>0) {GlobalVariableSet(PositionKey(id,".r"),dist);changed=true;}
  double originalVolume=0;
  for(int j=0;j<HistoryDealsTotal();j++)
  {
   ulong d=HistoryDealGetTicket(j);
   if(HistoryDealGetInteger(d,DEAL_ENTRY)==DEAL_ENTRY_IN) originalVolume+=HistoryDealGetDouble(d,DEAL_VOLUME);
  }
  if(money>0 && originalVolume>0) GlobalVariableSet(PositionKey(id,".unit"),money/originalVolume);
 }
 if(changed) GlobalVariablesFlush();
}

bool AIExecutionFresh(datetime bar,ulong started,double reference,bool buy,MqlTick &tick)
{
 if(bar==0) return true;
 PendingAIDecision request;ZeroMemory(request);request.bar=bar;request.started=started;request.ask=reference;request.bid=reference;
 return AIContextFresh(request) && AIPriceFresh(request,buy,tick);
}

void RecordEntryAttempt(bool manual,PatternSignal &pattern)
{
 if(!manual && pattern.type!=PATTERN_NONE) {MarkPatternUsed(pattern);return;}
 // Manual or AI-only entry: consume the bar but do not overwrite automatic-pattern identity.
 MarkAIBarUsed();
}

double ManualFixedRisk()
{
 if(StopAfterConsecutiveLosses>0 && g_consecutiveLosses>=StopAfterConsecutiveLosses) return 0;
 double risk=BaseRiskPercent;
 if(g_consecutiveLosses>=5) risk=MathMin(risk,RiskAfter5Loss);
 else if(g_consecutiveLosses>=4) risk=MathMin(risk,RiskAfter4Loss);
 else if(g_consecutiveLosses>=3) risk=MathMin(risk,RiskAfter3Loss);
 else if(g_consecutiveLosses>=2) risk=MathMin(risk,RiskAfter2Loss);
 return LimitRisk(risk);
}

double CalculateManualRisk()
{
 if(!g_historyOK) return 0;
 double fixed=ManualFixedRisk(),risk=fixed;
 if(RiskMode!=RISK_FIXED_ADJUST)
 {
  if(!g_mcReady || !g_mcAllowed) return 0;
  risk=RiskMode==RISK_MONTE_CARLO?g_mcRisk:MathMin(fixed,g_mcRisk);
 }
 return LimitRisk(MathMin(risk,PropRiskCap()));
}

bool EntryModeAllowed(bool manual)
{
 if(manual) return EnableManualTrading && ExecutionMode==EXECUTION_MANUAL;
 if(!EnableAutoTrading) return false;
 return ExecutionMode==EXECUTION_AUTO || ExecutionMode==EXECUTION_AI || ExecutionMode==EXECUTION_HYBRID;
}

bool BuildManualStops(bool buy,MqlTick &tick,double requestedSL,double &sl,double &tp)
{
 sl=0;tp=0;
 if(!MathIsValidNumber(requestedSL) || requestedSL<=0 || tick.bid<=0 || tick.ask<tick.bid) return false;
 // Round to the symbol's price tick; do not silently move a user's SL farther away.
 sl=NormalizePrice(requestedSL);
 double minDistance=(double)SymbolInfoInteger(m_symbol,SYMBOL_TRADE_STOPS_LEVEL)*m_point
   +SymbolInfoDouble(m_symbol,SYMBOL_TRADE_TICK_SIZE);
 double entry=buy?tick.ask:tick.bid;
 if(buy)
 {
  if(sl<=0 || sl>tick.bid-minDistance) return false;
  tp=PriceCeil(entry+(entry-sl)*RiskRewardRatio);
  if(tp<tick.bid+minDistance) return false;
 }
 else
 {
  if(sl<tick.ask+minDistance) return false;
  tp=PriceFloor(entry-(sl-entry)*RiskRewardRatio);
  if(tp>tick.ask-minDistance) return false;
 }
 return tp>0;
}

string ManualName(string suffix) {return LINE_PREFIX+"MANUAL_"+suffix;}

void ManualLabel(string suffix,string text,int y,color c)
{
 if(!m_isChart) return;

 string name=ManualName(suffix);
 if(ObjectFind(0,name)<0 && !ObjectCreate(0,name,OBJ_LABEL,0,0,0)) return;
 ObjectSetInteger(0,name,OBJPROP_CORNER,CORNER_LEFT_UPPER);
 ObjectSetInteger(0,name,OBJPROP_ANCHOR,ANCHOR_LEFT_UPPER);
 ObjectSetInteger(0,name,OBJPROP_XDISTANCE,12);ObjectSetInteger(0,name,OBJPROP_YDISTANCE,y);
 ObjectSetInteger(0,name,OBJPROP_COLOR,c);ObjectSetInteger(0,name,OBJPROP_FONTSIZE,10);
 ObjectSetInteger(0,name,OBJPROP_SELECTABLE,false);
 ObjectSetString(0,name,OBJPROP_FONT,"Arial");ObjectSetString(0,name,OBJPROP_TEXT,text);
}

void ManualButton(string suffix,int x,color c,bool ready)
{
 if(!m_isChart) return;

 string name=ManualName(suffix);
 if(ObjectFind(0,name)<0 && !ObjectCreate(0,name,OBJ_BUTTON,0,0,0)) return;
 ObjectSetInteger(0,name,OBJPROP_CORNER,CORNER_LEFT_UPPER);
 ObjectSetInteger(0,name,OBJPROP_XDISTANCE,x);ObjectSetInteger(0,name,OBJPROP_YDISTANCE,220);
 ObjectSetInteger(0,name,OBJPROP_XSIZE,120);ObjectSetInteger(0,name,OBJPROP_YSIZE,34);
 ObjectSetInteger(0,name,OBJPROP_BGCOLOR,ready?c:clrDimGray);
 ObjectSetInteger(0,name,OBJPROP_COLOR,clrWhite);ObjectSetInteger(0,name,OBJPROP_FONTSIZE,11);
 ObjectSetInteger(0,name,OBJPROP_SELECTABLE,false);ObjectSetInteger(0,name,OBJPROP_ZORDER,10);
 ObjectSetString(0,name,OBJPROP_TEXT,suffix+(ready?"":" [WAIT]"));
}

void InitializeManualPanel()
{
 if(!m_isChart) return;

 if(ExecutionMode!=EXECUTION_MANUAL) return;
 string name=ManualName("SL");
 if(ObjectFind(0,name)>=0) return;
 MqlTick tick;if(!SymbolInfoTick(m_symbol,tick) || tick.bid<=0) return;
 double level=ManualInitialSL>0?ManualInitialSL:StateGet(g_statePrefix+"manual.sl");
 if(level<=0)
 {
  double distance=GetATR(PERIOD_M1,14,1)*2.0;
  if(distance<=0) return;
  distance=MathMax(distance,StopBuffer());
  level=PriceFloor(tick.bid-distance);
 }
 level=NormalizePrice(level);
 if(level<=0 || !ObjectCreate(0,name,OBJ_HLINE,0,0,level)) return;
 ObjectSetInteger(0,name,OBJPROP_COLOR,clrOrange);ObjectSetInteger(0,name,OBJPROP_WIDTH,2);
 ObjectSetInteger(0,name,OBJPROP_SELECTABLE,true);ObjectSetInteger(0,name,OBJPROP_SELECTED,true);
 ObjectSetInteger(0,name,OBJPROP_ZORDER,5);
 ObjectSetString(0,name,OBJPROP_TEXT,"MANUAL SL - drag for next order");
 g_manualMessage="Drag SL below Bid for BUY, above Ask for SELL. Buttons place market orders.";
}

void DeleteManualPanel()
{
 if(!m_isChart) return;

 for(int i=ObjectsTotal(0,-1,-1)-1;i>=0;i--)
 {
  string name=ObjectName(0,i,-1,-1);
  if(StringFind(name,ManualName(""))==0) ObjectDelete(0,name);
 }
}

void UpdateManualAnalysis()
{
 if(!m_isChart || ExecutionMode!=EXECUTION_MANUAL) return;
 MTFResult r[];if(!AnalyzeAllTimeframes(r)) {g_manualAnalysis="MTF data loading (manual entry independent)";return;}
 g_manualAnalysis=StringFormat("Agreement BUY %.0f%% / SELL %.0f%% | score %.1f / %.1f",
  WeightedAgreement(r,true),WeightedAgreement(r,false),WeightedMTFScore(r,true),WeightedMTFScore(r,false));
}

void RefreshManualPanel()
{
 if(!m_isChart) return;

 if(ExecutionMode!=EXECUTION_MANUAL) return;
 InitializeManualPanel();
 string name=ManualName("SL");
 if(ObjectFind(0,name)<0) return;
 MqlTick tick;if(!FreshQuote(tick)) return;
 double requested=ObjectGetDouble(0,name,OBJPROP_PRICE),risk=CalculateManualRisk();
 bool permissions=TerminalInfoInteger(TERMINAL_TRADE_ALLOWED) && MQLInfoInteger(MQL_TRADE_ALLOWED) &&
   AccountInfoInteger(ACCOUNT_TRADE_ALLOWED) && AccountInfoInteger(ACCOUNT_TRADE_EXPERT);
 bool blocked=!EntryModeAllowed(true) || !permissions || EntryExposureBlocked() || risk<=0 || HasUnresolvedOrder() || AnyAccountUnresolved();
 if(MaxSpreadPoints>0 && GetSpreadPoints()>MaxSpreadPoints) blocked=true;
 datetime bar=iTime(m_symbol,PERIOD_M1,0);
 if(OneEntryPerBar && (bar==g_lastTradeBar || bar==g_lastAttemptBar)) blocked=true;
 double bs=0,bt=0,ss=0,st=0,bl=0,sellLot=0;
 bool buyOK=BuildManualStops(true,tick,requested,bs,bt) && IsBuyAllowed() && SymbolDirectionAllowed(true) && SpreadOK(tick,bs,true);
 bool sellOK=BuildManualStops(false,tick,requested,ss,st) && IsSellAllowed() && SymbolDirectionAllowed(false) && SpreadOK(tick,ss,false);
 if(buyOK) bl=CalculateLotByRisk(true,tick,bs,risk);
 if(sellOK) sellLot=CalculateLotByRisk(false,tick,ss,risk);
 ManualButton("BUY",12,EnableTradingViewTheme?ThemeRed():clrCrimson,!blocked && buyOK && bl>0);
 ManualButton("SELL",142,EnableTradingViewTheme?ThemeBlue():clrRoyalBlue,!blocked && sellOK && sellLot>0);
 string buyText=buyOK?StringFormat("BUY  lots %.4f | entry %.*f | SL %.*f | TP %.*f",bl,m_digits,tick.ask,m_digits,bs,m_digits,bt):"BUY: SL must be below Bid and meet broker minimum distance";
 string sellText=sellOK?StringFormat("SELL lots %.4f | entry %.*f | SL %.*f | TP %.*f",sellLot,m_digits,tick.bid,m_digits,ss,m_digits,st):"SELL: SL must be above Ask and meet broker minimum distance";
 ManualLabel("HEADER",StringFormat("MANUAL | risk %.4f%% | RR %.2f | %s",risk,RiskRewardRatio,blocked?"ENTRY BLOCKED":"Ready"),195,clrOrange);
 ManualLabel("BUY_INFO",buyText,262,PanelForeground());ManualLabel("SELL_INFO",sellText,282,PanelForeground());
 ManualLabel("ANALYSIS",g_manualAnalysis,302,PanelForeground());
 ManualLabel("MESSAGE",HasUnresolvedOrder()?"ORDER UNRESOLVED - token "+PendingOrderToken():g_manualMessage,324,clrOrange);
 string tpName=ManualName("TP");
 if(buyOK || sellOK)
 {
  CreateOrUpdateHLine(tpName,buyOK?bt:st,clrLimeGreen,STYLE_DASH,1);
  ObjectSetString(0,tpName,OBJPROP_TEXT,"MANUAL TP PREVIEW (next order)");
 }
 else ObjectDelete(0,tpName);
 ChartRedraw();
}

void HandleManualEntry(bool buy)
{
 if(!m_isChart) return;

 if(!EntryModeAllowed(true)) {g_manualMessage="Manual entries disabled in settings";RefreshManualPanel();return;}
 if(g_manualBusy) return;
 ulong now=GetTickCount64();
 if(g_manualLastClick>0 && now-g_manualLastClick<1500) return;
 g_manualLastClick=now;g_manualBusy=true;
 // Read current line, history and quote again: preview prices are only estimates.
 string name=ManualName("SL");
 if(ObjectFind(0,name)<0) {g_manualMessage="SL line missing; reattach EA to restore.";g_manualBusy=false;return;}
 double sl=ObjectGetDouble(0,name,OBJPROP_PRICE);
 if(g_historyDirty) {CaptureInitialRisks();RefreshHistory();UpdateMonteCarloRisk(true);}
 else UpdateMonteCarloRisk(false);
 PatternSignal empty;ZeroMemory(empty);empty.type=PATTERN_NONE;
 bool ok=ExecuteEntry(buy,0,empty,true,sl);
 g_manualMessage=g_status;
 if(HasUnresolvedOrder()) g_manualMessage="Order status pending: check Terminal and README before retry";
 if(ok) GlobalVariableSet(g_statePrefix+"manual.sl",NormalizePrice(sl));
 GlobalVariablesFlush();g_manualBusy=false;
 RefreshManualPanel();UpdatePanel();
}

double SmartLockR(double currentR)
{
 if(currentR>=ProfitLock2TriggerR) return ProfitLock2R;
 if(currentR>=ProfitLockTriggerR) return ProfitLockR;
 if(currentR>=BreakEvenTriggerR) return BreakEvenLockR;
 return -1;
}

void ManagePositions()
{
 for(int i=PositionsTotal()-1;i>=0;i--)
 {
  ulong t=PositionGetTicket(i);
  if(t==0 || PositionGetString(POSITION_SYMBOL)!=m_symbol || (ulong)PositionGetInteger(POSITION_MAGIC)!=MagicNumber) continue;
   if(!SolePositionOwner(t)) continue;
  ulong id=(ulong)PositionGetInteger(POSITION_IDENTIFIER);
  double r=StateGet(PositionKey(id,".r"));
  if(r<=0) continue; // Never redefine R from a modified SL.
  double entry=PositionGetDouble(POSITION_PRICE_OPEN),sl=PositionGetDouble(POSITION_SL),tp=PositionGetDouble(POSITION_TP);
  bool buy=PositionGetInteger(POSITION_TYPE)==POSITION_TYPE_BUY;
  MqlTick tick;if(!FreshQuote(tick)) continue;
  double price=buy?tick.bid:tick.ask,currentR=(buy?price-entry:entry-price)/r;
  double candidate=sl;bool proposed=false;
  if(EnableSmartBreakEven)
  {
   double lock=SmartLockR(currentR);
   if(lock>=0) {candidate=buy?entry+r*lock:entry-r*lock;proposed=true;}
  }
  if(currentR>=ProfitLockTriggerR)
  {
   if(EnableATRTrailing)
   {
    double atr=GetATR(PERIOD_M1,14,1);
    if(atr>0)
    {
     double trail=buy?price-atr*ATRTrailingMultiplier:price+atr*ATRTrailingMultiplier;
     trail=buy?MathMax(trail,entry+r*BreakEvenLockR):MathMin(trail,entry-r*BreakEvenLockR);
     candidate=!proposed?trail:(buy?MathMax(candidate,trail):MathMin(candidate,trail));proposed=true;
    }
   }
   if(EnableStructureTrailing)
   {
    int shift=buy?iLowest(m_symbol,PERIOD_M1,MODE_LOW,StructureTrailingLookback,1):
                  iHighest(m_symbol,PERIOD_M1,MODE_HIGH,StructureTrailingLookback,1);
    if(shift>=1)
    {
     double level=buy?iLow(m_symbol,PERIOD_M1,shift)-StopBuffer():
                      iHigh(m_symbol,PERIOD_M1,shift)+StopBuffer();
     if(level>0 && (buy?level>entry:level<entry))
     {candidate=!proposed?level:(buy?MathMax(candidate,level):MathMin(candidate,level));proposed=true;}
    }
   }
  }
  if(!proposed) continue;
  long stops=SymbolInfoInteger(m_symbol,SYMBOL_TRADE_STOPS_LEVEL),freeze=SymbolInfoInteger(m_symbol,SYMBOL_TRADE_FREEZE_LEVEL);
  double gap=(double)MathMax(stops,freeze)*m_point+SymbolInfoDouble(m_symbol,SYMBOL_TRADE_TICK_SIZE);
  candidate=buy?PriceFloor(MathMin(candidate,price-gap)):PriceCeil(MathMax(candidate,price+gap));
  double improve=MathMax(MinimumSLImprovementPoints*m_point,MathMax(GetATR(PERIOD_M1,14,1)*MinimumSLImprovementATR,TickSize()));
  if(candidate<=0 || (sl>0 && (buy?candidate<sl+improve:candidate>sl-improve))) continue;
  // Do not downgrade the requested profit floor just to satisfy StopsLevel.
  double requiredLock=EnableSmartBreakEven?MathMax(BreakEvenLockR,SmartLockR(currentR)):BreakEvenLockR;
  if(buy?candidate<entry+r*requiredLock-m_point:candidate>entry-r*requiredLock+m_point) continue;
  if(sl>0 && MathAbs(price-sl)<=freeze*m_point) continue;
  if(tp>0 && MathAbs(price-tp)<=freeze*m_point) continue;
  bool ok=trade.PositionModify(t,candidate,tp);
  if(!ok || (trade.ResultRetcode()!=TRADE_RETCODE_DONE && trade.ResultRetcode()!=TRADE_RETCODE_NO_CHANGES))
   Print("SL modify not completed: ",trade.ResultRetcodeDescription());
  else
  {
   double smart=buy?entry+r*SmartLockR(currentR):entry-r*SmartLockR(currentR);
   JournalMarkSL(id,EnableSmartBreakEven && MathAbs(candidate-smart)<=TickSize()?1:2,candidate);
  }
 }
}

bool ValidateInputs()
{
 if(!ValidateFinalWeights()) return false;
 if(!MathIsValidNumber(MaxPortfolioRiskPercent) || MaxPortfolioRiskPercent<=0 || MaxPortfolioRiskPercent>100)
 {Print("MaxPortfolioRiskPercent must be finite, greater than 0 and at most 100.");return false;}
 if(ScanMode<CURRENT_SYMBOL || ScanMode>ALL_TRADABLE_SYMBOLS || ScanTimerMilliseconds<100 || ScanTimerMilliseconds>60000 ||
    SymbolsPerTimer<1 || ScanBudgetMilliseconds<1 || UniverseRefreshSeconds<1 || MaxEntriesPerTimer<1 || MaxEntriesPerTimer>20 ||
    DashboardRows<1 || DashboardRows>30 || MonteCarloTimerBudgetMs<1 || MaxQuoteAgeMs<100 || MaxQuoteAgeMs>10000) return false;
 if(ScanMode==CUSTOM_LIST && StringLen(CustomSymbols)==0) return false;
 if(EMASlopeBars<1 || EMASlopeBars>100 || MinimumWeightedAgreement<0 || MinimumWeightedAgreement>100 || MinimumSignalScore<0 || MinimumSignalScore>100) return false;
 if(MaxSpreadATR<=0 || MaxSpreadSL<=0 || SLBufferATR<0 || SlippageATR<0 || StopSlippageATR<0 || MinimumSLImprovementATR<0 || OpenAIMaxPriceDriftATR<=0) return false;
 for(int i=0;i<7;i++) {int fast,slow,signal;MACDParameters(MT3Timeframe(i),fast,slow,signal);if(fast<1 || slow<=fast || signal<1) return false;}


 if(ThemeChartScale<0 || ThemeChartScale>5 || !MathIsValidNumber(ThemeRightMarginPercent) || ThemeRightMarginPercent<10 || ThemeRightMarginPercent>50) return false;
 if(MagicNumber==0 || BaseRiskPercent<=0 || MinimumRiskPercent<=0 || MaximumRiskPercent<MinimumRiskPercent || MaximumRiskPercent>=100) return false;
 if(BaseRiskPercent>MaximumRiskPercent || RiskRewardRatio<=0 || SwingDepth<1 || PatternLookbackBars<3*SwingDepth+10) return false;
 if(EMAFastPeriod<1 || EMAMiddlePeriod<=EMAFastPeriod || EMASlowPeriod<=EMAMiddlePeriod || ADXPeriod<1) return false;
 if(SlippagePoints<0 || StopSlippageBufferPoints<0 || MaxSpreadPoints<0 || RoundTurnCommissionPerLot<0 || SLBufferPoints<0) return false;
 if(StopSwingLookback<1 || StructureTrailingLookback<1 || TrendLineSwingDepth<1 || MaxHorizontalLines<1) return false;
 if(ManualInitialSL<0 || !MathIsValidNumber(ManualInitialSL)) return false;
 if(TripleMinimumReboundATR<=0) return false;
 if(PatternToleranceATR<=0 || NecklineToleranceATR<0 || HorizontalLineToleranceATR<=0) return false;
 if(RiskAfter2Loss<0 || RiskAfter3Loss<0 || RiskAfter4Loss<0 || RiskAfter5Loss<0 || StopAfterConsecutiveLosses<0) return false;
 if(RiskScore90<0 || RiskScore80<0 || RiskScore70<0 || BreakEvenMoneyTolerance<0) return false;
 if(HistoryTradeLimit<30 || HistoryTradeLimit>5000 || MonteCarloMinimumSamples<2 || MonteCarloMinimumSamples>HistoryTradeLimit) return false;
 if(RiskMode!=RISK_FIXED_ADJUST && !EnableMonteCarlo) return false;
 if(MonteCarloRuns<100 || MonteCarloRuns>100000 || MonteCarloTrades<1 || MonteCarloTrades>2000 || MonteCarloRiskStep<=0) return false;
 if((MaximumRiskPercent-MinimumRiskPercent)/MonteCarloRiskStep>100 || MonteCarloRecalculateMinutes<1) return false;
 if(MonteCarloMaxDrawdownPercent<=0 || MonteCarloMaxDrawdownPercent>=100 || MonteCarloSafetyFactor<=0 || MonteCarloSafetyFactor>1) return false;
 if(MonteCarloMinimumWinRate<0 || MonteCarloMinimumWinRate>1) return false;
 if(BreakEvenTriggerR<=0 || ProfitLockTriggerR<=BreakEvenTriggerR || ProfitLock2TriggerR<=ProfitLockTriggerR) return false;
 if(BreakEvenLockR<0 || BreakEvenLockR>=BreakEvenTriggerR || ProfitLockR<BreakEvenLockR || ProfitLockR>=ProfitLockTriggerR) return false;
 if(ProfitLock2R<ProfitLockR || ProfitLock2R>=ProfitLock2TriggerR || ATRTrailingMultiplier<=0 || MinimumSLImprovementPoints<0) return false;
 if(AccountMode==FINTOKEI && (FintokeiInitialBalance<=0 || FintokeiSafetyMargin<=0 || FintokeiSafetyMargin>=1 ||
    FintokeiMaxRiskPerTrade<=0 || FintokeiMaxConsecutiveLosses<1 || FintokeiExtraReservePercent<0 || FintokeiDailyReference<0)) return false;
 if((ExecutionMode==EXECUTION_AI || ExecutionMode==EXECUTION_HYBRID) && !EnableOpenAI) return false;
 if(OpenAIMaxDecisionAgeMs<1000 || OpenAIMaxDecisionAgeMs>60000 || OpenAIMaxQuoteAgeMs<100 || OpenAIMaxQuoteAgeMs>10000 ||
    !MathIsValidNumber(OpenAIMaxPriceDriftPoints) || OpenAIMaxPriceDriftPoints<0 || !MathIsValidNumber(OpenAIMinConfidence) ||
    OpenAIMinConfidence<0 || OpenAIMinConfidence>1 || OpenAIM1Bars<5 || OpenAIM1Bars>100) return false;
 if((ExecutionMode==EXECUTION_AI || ExecutionMode==EXECUTION_HYBRID) && StringLen(OpenAIModel)<1) return false;
 if(OpenAIReasoningEffort!="" && OpenAIReasoningEffort!="none" && OpenAIReasoningEffort!="low" && OpenAIReasoningEffort!="medium" &&
    OpenAIReasoningEffort!="high" && OpenAIReasoningEffort!="xhigh" && OpenAIReasoningEffort!="max") return false;
 return true;
}

bool SelfTests()
{
 // Checks use the active input values; no orders or persistent changes.
 bool ok=true;
 if(LimitRisk(0)!=0 || LimitRisk(-1)!=0) ok=false;
 double minLot=SymbolInfoDouble(m_symbol,SYMBOL_VOLUME_MIN);
 if(NormalizeVolume(minLot*0.5)!=0) ok=false;
 if(MathAbs(SmartLockR(BreakEvenTriggerR)-BreakEvenLockR)>1e-10) ok=false;
 if(MathAbs(SmartLockR(ProfitLockTriggerR)-ProfitLockR)>1e-10) ok=false;
 if(MathAbs(SmartLockR(ProfitLock2TriggerR)-ProfitLock2R)>1e-10) ok=false;
 if(SmartLockR(BreakEvenTriggerR*0.5)>=0) ok=false;
 Print(ok?"SELF TEST PASS":"SELF TEST FAILED");return ok;
}

void UpdatePanel() {}

void Maintain(bool updateStats)
{
 MqlTick tick;FreshQuote(tick);
 UpdatePropProtection();ManagePositions();ReconcilePendingOrder();
 bool changed=g_historyDirty;
 if(updateStats && (changed || TimeCurrent()-g_lastHistory>=60)) {CaptureInitialRisks();RefreshHistory();}
 if(updateStats && g_historyOK) UpdateMonteCarloRisk(changed);
 ProcessAIReply();JournalSample();
 if(HasUnresolvedOrder()) g_status="ORDER UNRESOLVED | token "+PendingOrderToken();
 else if(AccountMode==FINTOKEI && g_propStop>0) g_status="DD stop latched; own positions being closed";
 if(m_isChart && ExecutionMode==EXECUTION_MANUAL)
 {if(updateStats) UpdateManualAnalysis();RefreshManualPanel();}
}

void TradeEvent(const MqlTradeTransaction &trans,const MqlTradeRequest &request,const MqlTradeResult &result)
{
 m_journalDirty=true;
 if(trans.type==TRADE_TRANSACTION_DEAL_ADD || trans.type==TRADE_TRANSACTION_POSITION || trans.type==TRADE_TRANSACTION_HISTORY_ADD) g_historyDirty=true;
 if(trans.type==TRADE_TRANSACTION_REQUEST && HasUnresolvedOrder() && request.symbol==m_symbol && request.magic==MagicNumber && request.comment==PendingOrderComment())
 {
  if(result.order>0) SaveU64(g_statePrefix+"ord.ticket",result.order);
  if(result.deal>0) SaveU64(g_statePrefix+"ord.deal",result.deal);
  if(DefinitiveEntryRejection(result.retcode)) ClearPendingOrder();
  GlobalVariablesFlush();g_historyDirty=true;
 }
}

void ChartEvent(const int id,const long &lparam,const double &dparam,const string &sparam)
{
 if(!m_isChart) return;

 if(id==CHARTEVENT_CUSTOM+MT3_AI_REPLY_EVENT)
 {
  if(g_aiRequest.active && lparam==g_aiRequest.worker && sparam==g_aiRequest.id) {ProcessAIReply();UpdatePanel();}
  return;
 }
 if(ExecutionMode!=EXECUTION_MANUAL) return;
 if((id==CHARTEVENT_OBJECT_DRAG || id==CHARTEVENT_OBJECT_CHANGE) && sparam==ManualName("SL"))
 {
  double level=NormalizePrice(ObjectGetDouble(0,sparam,OBJPROP_PRICE));
  if(level>0)
  {
   GlobalVariableSet(g_statePrefix+"manual.sl",level);GlobalVariablesFlush();
   g_manualMessage="SL updated for NEXT entry. Existing positions keep their own SL.";
  }
  RefreshManualPanel();return;
 }
 if(id==CHARTEVENT_OBJECT_CLICK && (sparam==ManualName("BUY") || sparam==ManualName("SELL")))
 {
  ObjectSetInteger(0,sparam,OBJPROP_STATE,false);
  HandleManualEntry(sparam==ManualName("BUY"));
 }
}

bool ExecuteEntryLocked(bool buy,double score,PatternSignal &pattern,bool manual=false,double requestedSL=0,
                  datetime decisionBar=0,ulong decisionStarted=0,double referenceEntry=0)
{
 RefreshAccountHistory(true);
 if(!SymbolDirectionAllowed(buy)) {g_status="Symbol trade direction disabled";return DiagPass(false,"symbol_direction");}
 if(!manual && pattern.valid && IsPatternAlreadyUsed(pattern)) {g_status="Pattern already consumed";return DiagPass(false,"pattern_consumed");}
 trade.SetDeviationInPoints(DeviationPoints());

 RefreshEntryState();
 if(!EntryPreflight(manual) || (buy?!IsBuyAllowed():!IsSellAllowed())) return DiagPass(false,"preflight_or_entry_direction");
 datetime bar=iTime(m_symbol,PERIOD_M1,0);
 if((OneEntryPerBar || !manual) && (bar<=0 || bar==g_lastTradeBar || bar==g_lastAttemptBar))
 {g_status="One entry/attempt per M1 bar; wait for next bar";return DiagPass(false,"duplicate_m1");}
 MqlTick tick;if(!FreshQuote(tick)) return DiagPass(false,"quote_invalid");
 if(!AIExecutionFresh(decisionBar,decisionStarted,referenceEntry,buy,tick)) {g_status="AI decision expired before sizing";return DiagPass(false,"ai_price_or_age_before_sizing");}
 if(!SpreadOK(tick) || !PatternEntryLocationOK(pattern,tick,buy)) {g_status="Spread / pattern price invalid";return DiagPass(false,"spread_or_pattern_location");}
 double risk=manual?CalculateManualRisk():CalculateFinalRisk(score);
 if(risk<=0) {g_status="Risk / loss-streak / DD protection blocked entry";return DiagPass(false,"risk_limit");}
 double sl,tp;string slSource=manual?"MANUAL":"",slFallback="";
 bool stopsOK=manual?BuildManualStops(buy,tick,requestedSL,sl,tp):BuildEntryStops(buy,tick,pattern,sl,tp,slSource,slFallback);
 stopsOK=stopsOK && EntryStopsValid(buy,tick,sl,tp);
 if(!stopsOK) {g_status="SL is on wrong side, too close, or invalid";return DiagPass(false,"stop_validation");}
 double portfolioBefore=0,plannedRisk=0;string portfolioReason;
 if(EnablePortfolioRiskLimit && !ManagedPortfolioRisk(portfolioBefore,portfolioReason)) {ReportPortfolioReject(portfolioReason);return DiagPass(false,"portfolio_unknown");}
 double lot=CalculateLotByRisk(buy,tick,sl,risk);
 if(lot<=0) {g_status="Lot below minimum or insufficient margin";return DiagPass(false,"lot_invalid");}
 if(!CheckPortfolioEntry(buy,tick,sl,lot,portfolioBefore,plannedRisk)) return DiagPass(false,"portfolio_risk_limit");
 MqlTradeRequest req={};MqlTradeCheckResult check={};
 req.action=TRADE_ACTION_DEAL;req.magic=MagicNumber;req.symbol=m_symbol;
 req.type=buy?ORDER_TYPE_BUY:ORDER_TYPE_SELL;req.volume=lot;
 req.price=buy?tick.ask:tick.bid;req.sl=sl;req.tp=tp;req.deviation=DeviationPoints();
 long filling=SymbolInfoInteger(m_symbol,SYMBOL_FILLING_MODE);
 if((filling&SYMBOL_FILLING_FOK)!=0) req.type_filling=ORDER_FILLING_FOK;
 else if((filling&SYMBOL_FILLING_IOC)!=0) req.type_filling=ORDER_FILLING_IOC;
 else req.type_filling=ORDER_FILLING_RETURN;
 if(!OrderCheck(req,check)) {g_status="OrderCheck: "+check.comment;Print(g_status);return DiagPass(false,"order_check");}
 MqlTick latest;if(!FreshQuote(latest) || !AIExecutionFresh(decisionBar,decisionStarted,referenceEntry,buy,latest))
 {g_status="AI decision expired during order preparation";return DiagPass(false,"ai_price_or_age_preparation");}
 if(bar!=iTime(m_symbol,PERIOD_M1,0) || !SpreadOK(latest,sl,buy)) return DiagPass(false,"bar_or_spread_changed");
 if(MathAbs((buy?latest.ask:latest.bid)-(buy?tick.ask:tick.bid))>req.deviation*m_point+m_point*1e-8)
 {g_status="Quote moved beyond sizing reserve during preparation";return DiagPass(false,"sizing_price_drift");}
 if(!BeginPendingOrder()) {g_status="Could not persist order intent / previous order unresolved";return DiagPass(false,"order_intent_persistence");}
 g_lastAttemptBar=bar;
 if(GlobalVariableSet(g_statePrefix+"attempt.bar",(double)bar)==0) {ClearPendingOrder();return DiagPass(false,"attempt_bar_persistence");}
 GlobalVariablesFlush();
 if(!manual && !PersistPatternClaims(pattern)) {ClearPendingOrder();g_status="Pattern receipt persistence failed";return DiagPass(false,"pattern_receipt_persistence");}
 PrepareTradeJournal(buy,manual,score,pattern,tick,sl,tp,lot,slSource,slFallback,portfolioBefore,plannedRisk);
 // Re-read all managed symbols and equity inside the account mutex after order preparation/log I/O.
 if(!CheckPortfolioEntry(buy,tick,sl,lot,portfolioBefore,plannedRisk)) {ClearPendingOrder();return DiagPass(false,"portfolio_risk_limit");}
 if(!FreshQuote(latest) || !PatternEntryLocationOK(pattern,latest,buy) || bar!=iTime(m_symbol,PERIOD_M1,0) || !AIExecutionFresh(decisionBar,decisionStarted,referenceEntry,buy,latest) ||
    !SpreadOK(latest,sl,buy) || MathAbs((buy?latest.ask:latest.bid)-(buy?tick.ask:tick.bid))>req.deviation*m_point+m_point*1e-8)
 {ClearPendingOrder();g_status="Decision / quote changed before send";return DiagPass(false,"decision_or_quote_before_send");}
 if(!EntryStopsValid(buy,latest,sl,tp))
 {ClearPendingOrder();g_status="Stops invalid at latest quote";return DiagPass(false,"latest_stop_validation");}
 string orderComment=PendingOrderComment();
 DiagOrderAttempt();
 bool ok=buy?trade.Buy(lot,m_symbol,latest.ask,sl,tp,orderComment):trade.Sell(lot,m_symbol,latest.bid,sl,tp,orderComment);
 MqlTradeResult result={};trade.Result(result);uint rc=result.retcode;
 DiagOrderResult(ok,rc);
 if(result.order>0) SaveU64(g_statePrefix+"ord.ticket",result.order);
 if(result.deal>0) SaveU64(g_statePrefix+"ord.deal",result.deal);
 GlobalVariableSet(g_statePrefix+"ord.state",2);GlobalVariablesFlush();
 JournalAfterSend(portfolioBefore,plannedRisk);
 if(!ok || (rc!=TRADE_RETCODE_DONE && rc!=TRADE_RETCODE_DONE_PARTIAL && rc!=TRADE_RETCODE_PLACED))
 {
  if(DefinitiveEntryRejection(rc)) ClearPendingOrder();
  else RecordEntryAttempt(manual,pattern);
  g_status="Order result: "+trade.ResultRetcodeDescription();
  if(HasUnresolvedOrder()) g_status+=" | UNRESOLVED token "+PendingOrderToken();
  Print(g_status);return DiagPass(false,"order_result");
 }
 RecordEntryAttempt(manual,pattern);g_historyDirty=true;ReconcilePendingOrder();CaptureInitialRisks();
 g_currentRiskPercent=risk;
 g_status=StringFormat("%s %s | score %.1f | risk %.4f%% | lot %.4f",buy?"BUY":"SELL",manual?"MANUAL":PatternName(pattern.type),score,risk,lot);
 if(HasUnresolvedOrder()) g_status+=" | awaiting order reconciliation";
 Print(g_status);return true;
}

bool MTFSnapshotCurrent()
{
 if(ArraySize(m_mtf)!=7) return false;
 for(int i=0;i<7;i++) if(m_mtf[i].bar<=0 || m_mtf[i].bar!=iTime(m_symbol,MT3Timeframe(i),0) || m_mtf[i].atr<=0) return false;
 return true;
}

double TickSize() {return SymbolInfoDouble(m_symbol,SYMBOL_TRADE_TICK_SIZE);}

double StopBuffer()
{return MathMax(SLBufferPoints*m_point,MathMax(GetATR(PERIOD_M1,14,1)*SLBufferATR,
 MathMax((double)SymbolInfoInteger(m_symbol,SYMBOL_TRADE_STOPS_LEVEL)*m_point+TickSize(),2*TickSize())));}

ulong DeviationPoints()
{
 if(m_point<=0) return 0;
 return (ulong)MathCeil(MathMax(SlippagePoints*m_point,MathMax(TickSize(),GetATR(PERIOD_M1,14,1)*SlippageATR))/m_point);
}

double StopSlippage()
{return MathMax(StopSlippageBufferPoints*m_point,MathMax(TickSize(),GetATR(PERIOD_M1,14,1)*StopSlippageATR));}

bool SymbolDirectionAllowed(bool buy)
{
 long mode=SymbolInfoInteger(m_symbol,SYMBOL_TRADE_MODE);
 return mode==SYMBOL_TRADE_MODE_FULL || (buy?mode==SYMBOL_TRADE_MODE_LONGONLY:mode==SYMBOL_TRADE_MODE_SHORTONLY);
}

bool FreshQuote(MqlTick &tick,int ageLimit=0)
{
 if(DiagReject(!SymbolInfoTick(m_symbol,tick),"quote_unavailable") || DiagReject(!MathIsValidNumber(tick.bid),"invalid_bid") || DiagReject(!MathIsValidNumber(tick.ask),"invalid_ask") ||
    DiagReject(tick.bid<=0,"invalid_bid") || DiagReject(tick.ask<tick.bid,"invalid_bid_ask") || DiagReject(tick.time_msc<=0,"quote_timestamp_missing")) return false;
 ulong now=GetTickCount64();
 if(tick.time_msc!=m_quoteTimeMsc)
 {m_quoteTimeMsc=tick.time_msc;g_lastSymbolTickMs=now;m_quoteSeen=true;}
 if(ageLimit<=0) ageLimit=MaxQuoteAgeMs;
 long serverMs=(long)(MQLInfoInteger(MQL_TESTER)?TimeCurrent():TimeTradeServer())*1000;
 if(DiagReject(serverMs<=0,"server_time_missing") || DiagReject(tick.time_msc>serverMs+1000,"quote_from_future") || DiagReject(serverMs-tick.time_msc>ageLimit,"quote_stale")) return false;
 // Polling the same quote must not refresh the monotonic receipt timestamp.
 if(!MQLInfoInteger(MQL_TESTER) && (!m_quoteSeen || now<g_lastSymbolTickMs || now-g_lastSymbolTickMs>(ulong)ageLimit)) return false;
 return true;
}

bool SpreadOK(MqlTick &tick,double sl=0,bool buy=true)
{
 double atr=GetATR(PERIOD_M1,14,1),spread=tick.ask-tick.bid;
 if(DiagReject(atr<=0,"spread_atr_unavailable") || DiagReject(spread<0,"invalid_spread") || DiagReject(spread>atr*MaxSpreadATR+TickSize()*1e-8,"spread_atr_limit")) return false;
 if(DiagReject(MaxSpreadPoints>0 && spread>MaxSpreadPoints*m_point,"spread_points_limit")) return false;
 if(sl>0)
 {
  double distance=MathAbs((buy?tick.ask:tick.bid)-sl);
  if(DiagReject(distance<=0,"sl_distance_zero") || DiagReject(spread>distance*MaxSpreadSL+TickSize()*1e-8,"spread_sl_limit")) return false;
 }
 return true;
}

double AvailableDirectionalVolume(bool buy)
{
 double limit=SymbolInfoDouble(m_symbol,SYMBOL_VOLUME_LIMIT);if(limit<=0) return DBL_MAX;
 double used=0;
 for(int i=0;i<PositionsTotal();i++)
  if(PositionGetTicket(i)>0 && PositionGetString(POSITION_SYMBOL)==m_symbol &&
     (PositionGetInteger(POSITION_TYPE)==POSITION_TYPE_BUY)==buy) used+=PositionGetDouble(POSITION_VOLUME);
 for(int i=0;i<OrdersTotal();i++)
 {
  if(OrderGetTicket(i)==0 || OrderGetString(ORDER_SYMBOL)!=m_symbol) continue;
  long type=OrderGetInteger(ORDER_TYPE);
  bool longOrder=type==ORDER_TYPE_BUY || type==ORDER_TYPE_BUY_LIMIT || type==ORDER_TYPE_BUY_STOP || type==ORDER_TYPE_BUY_STOP_LIMIT;
  if(longOrder==buy) used+=OrderGetDouble(ORDER_VOLUME_CURRENT);
 }
 return MathMax(0.0,limit-used);
}

bool ExecuteEntry(bool buy,double score,PatternSignal &pattern,bool manual=false,double requestedSL=0,
                  datetime decisionBar=0,ulong decisionStarted=0,double referenceEntry=0)
{
 DiagExecution(manual);
 if(!AcquireExecution()) {g_status="Account execution busy";return DiagEnd(false,"execution_lock");}
 bool ok=ExecuteEntryLocked(buy,score,pattern,manual,requestedSL,decisionBar,decisionStarted,referenceEntry);
 ReleaseExecution();return DiagEnd(ok,"execution");
}

bool SolePositionOwner(ulong ticket)
{
 if(!PositionSelectByTicket(ticket)) return false;
 if(AccountInfoInteger(ACCOUNT_MARGIN_MODE)==ACCOUNT_MARGIN_MODE_RETAIL_HEDGING) return true;
 ulong id=(ulong)PositionGetInteger(POSITION_IDENTIFIER);
 if(!HistorySelectByPosition(id)) return false;
 bool ours=false;
 for(int i=0;i<HistoryDealsTotal();i++)
 {
  ulong d=HistoryDealGetTicket(i);long entry=HistoryDealGetInteger(d,DEAL_ENTRY);
  if(entry==DEAL_ENTRY_INOUT) return false;
  if(entry==DEAL_ENTRY_IN)
  {
   if((ulong)HistoryDealGetInteger(d,DEAL_MAGIC)!=MagicNumber || HistoryDealGetString(d,DEAL_SYMBOL)!=m_symbol) return false;
   ours=true;
  }
 }
 return ours && PositionSelectByTicket(ticket);
}

void StoreLevel(string name,double price)
{
 if(StringFind(name,LINE_PREFIX+"HLINE_")!=0) return;
 for(int i=0;i<ArraySize(m_levels);i++) if(m_levels[i].name==name) {m_levels[i].price=price;return;}
 int n=ArraySize(m_levels);if(ArrayResize(m_levels,n+1)!=n+1) return;
 m_levels[n].name=name;m_levels[n].price=price;
 m_levels[n].support=StringFind(name,"HLINE_SUP_")>=0 || StringFind(name,"PD_LOW")>=0;
}

double NearestLevel(double price,bool support)
{
 double nearest=DBL_MAX;
 for(int i=0;i<ArraySize(m_levels);i++)
 {
  if(m_levels[i].support!=support) continue;
  double d=support?price-m_levels[i].price:m_levels[i].price-price;
  if(d>=0) nearest=MathMin(nearest,d);
 }
 return nearest==DBL_MAX?-1:nearest;
}

void StoreTrend(string name,datetime t1,double p1,datetime t2,double p2)
{
 bool support=name==LINE_PREFIX+"TREND_SUPPORT";int i=support?0:1;
 m_trends[i].t1=t1;m_trends[i].t2=t2;m_trends[i].p1=p1;m_trends[i].p2=p2;
}

bool NearTrend(bool support)
{
 int i=support?0:1;
 if(m_trends[i].t1<=0 || m_trends[i].t2<=m_trends[i].t1) return false;
 double line=m_trends[i].p1+(m_trends[i].p2-m_trends[i].p1)*
  (double)(TimeCurrent()-m_trends[i].t1)/(double)(m_trends[i].t2-m_trends[i].t1);
 double price=support?GetAsk():GetBid(),atr=GetATR(PERIOD_M1,14,1);
 return line>0 && price>0 && atr>0 && MathAbs(price-line)<=atr*0.50;
}

uint NextMCRandom()
{
 // Per-symbol RNG: scanner interleaving cannot affect another symbol's bootstrap.
 m_mcRandom^=m_mcRandom<<13;m_mcRandom^=m_mcRandom>>17;m_mcRandom^=m_mcRandom<<5;
 return m_mcRandom;
}

void AdvanceMonteCarlo(ulong deadline)
{
 if(!m_mcActive || g_historyDirty) return;
 int operations=0;
 while(m_mcActive && GetTickCount64()<deadline && operations<20000)
 {
  double risk=MinimumRiskPercent+m_mcCandidate*MonteCarloRiskStep;
  int k=(int)(NextMCRandom()%(uint)ArraySize(m_mcReturns));
  m_mcEquity*=MathMax(0.0,1.0+risk/100.0*m_mcReturns[k]);
  m_mcPeak=MathMax(m_mcPeak,m_mcEquity);
  m_mcDD=MathMax(m_mcDD,(m_mcPeak-m_mcEquity)/m_mcPeak*100.0);
  m_mcTrade++;operations++;
  if(m_mcTrade<MonteCarloTrades && m_mcEquity>0) continue;
  m_mcDDs[m_mcRun++]=m_mcDD;m_mcTrade=0;m_mcEquity=100;m_mcPeak=100;m_mcDD=0;
  if(m_mcRun<MonteCarloRuns) continue;
  ArraySort(m_mcDDs);
  double dd=m_mcDDs[(int)MathCeil(0.95*MonteCarloRuns)-1];
  if(dd<=MonteCarloMaxDrawdownPercent*MonteCarloSafetyFactor || m_mcCandidate==0)
  {
   g_mcRisk=dd<=MonteCarloMaxDrawdownPercent*MonteCarloSafetyFactor?risk:0;
   g_mcAllowed=g_mcRisk>0;g_mcReady=true;g_lastMC=TimeCurrent();m_mcActive=false;
   PrintFormat("MC %s: samples=%d winrate=%.2f%% cap=%.4f%%",m_symbol,g_sampleCount,100*g_winRate,g_mcRisk);
   return;
  }
  m_mcCandidate--;m_mcRun=0;m_mcRandom=(uint)MonteCarloSeed;if(m_mcRandom==0) m_mcRandom=1;
 }
}

bool InUniverseNow()
{
 if(!m_scanEnabled) return false;
 if(ScanMode==MARKET_WATCH && !SymbolInfoInteger(m_symbol,SYMBOL_VISIBLE)) return false;
 return TradableSymbol(m_symbol);
}

bool RefreshCandidate()
{
 bool was=m_candidate;datetime previous=m_candidateBar;ulong sequence=m_candidateSequence;m_candidate=false;
 DiagBegin(was);
 if(!InUniverseNow() || !EntryPreflight(false) || g_aiRequest.active) return DiagEnd(false,"preflight");
 datetime bar=iTime(m_symbol,PERIOD_M1,0);
 DiagReuse(was && previous==bar);
 if(bar<=0 || bar==g_lastTradeBar || bar==g_lastAttemptBar ||
    ((ExecutionMode==EXECUTION_AI || ExecutionMode==EXECUTION_HYBRID) && bar==g_aiLastBar)) return DiagEnd(false,"bar_or_ai_lock");
 MTFResult r[];
 if(!AnalyzeAllTimeframes(r)) {g_status="Waiting for all 7 timeframe indicators";return DiagEnd(false,"indicator_wait");}
 PatternSignal p;ZeroMemory(p);bool buy=true;double score=0;
 if(ExecutionMode==EXECUTION_AI)
 {
  double bs=WeightedMTFScore(r,true),ss=WeightedMTFScore(r,false);
  bool b=IsBuyAllowed() && SymbolDirectionAllowed(true) && WeightedSignalOK(r,true);
  bool s=IsSellAllowed() && SymbolDirectionAllowed(false) && WeightedSignalOK(r,false);
  if(!b && !s) return false;
  buy=b && (!s || bs>=ss);score=buy?bs:ss;
  p.valid=true;p.type=PATTERN_NONE;p.buySignal=buy;p.sellSignal=!buy;
 }
 else
 {
  if(!SelectReversalPattern(r,p)) {g_status="Waiting for fresh neckline breakout";return DiagEnd(false,"pattern_wait");}
  DiagCandidate();
  if(IsPatternAlreadyUsed(p)) return DiagEnd(false,"pattern_consumed");
  buy=PatternDirection(p)==ENTRY_BUY;
  if(buy?!BuySignalOK(p,r):!SellSignalOK(p,r)) {g_status="Weighted agreement / strong opposition";return DiagEnd(false,"weighted_agreement_or_opposition");}
  if(buy?!IsBuyAllowed():!IsSellAllowed()) return DiagEnd(false,"entry_direction");
  score=buy?CalculateFinalBuyScore(p,r):CalculateFinalSellScore(p,r);
 }
 if(score<MinimumSignalScore) {g_status=StringFormat("Local score %.1f < %.1f",score,MinimumSignalScore);return DiagEnd(false,"score_below_threshold");}
 MqlTick tick;double sl,tp;string slSource,slFallback;
 if(!DiagPass(SymbolDirectionAllowed(buy),"symbol_direction") || !FreshQuote(tick) || !BuildEntryStops(buy,tick,p,sl,tp,slSource,slFallback) || !SpreadOK(tick,sl,buy) || !PatternEntryLocationOK(p,tick,buy))
 {g_status="Quote / relative cost / stop geometry blocks entry";return DiagEnd(false,"cost_or_stop_gate");}
 if(bar!=iTime(m_symbol,PERIOD_M1,0) || !MTFSnapshotCurrent()) return DiagEnd(false,"snapshot_changed");
 m_candidate=true;m_candidateBuy=buy;m_candidateScore=score;m_candidatePattern=p;m_candidateBar=bar;
 m_candidateSequence=was && previous==bar?sequence:++g_queueSequence;
 g_status=StringFormat("Candidate %s score %.1f | agreement %.0f%%",buy?"BUY":"SELL",score,WeightedAgreement(r,buy));
 return DiagEnd(true,"queued");
}

bool DispatchCandidate()
{
 if(!m_candidate || !RefreshCandidate()) return false;
 if(ExecutionMode==EXECUTION_AUTO)
 {
  ExecuteEntry(m_candidateBuy,m_candidateScore,m_candidatePattern);m_candidate=false;return true;
 }
 MTFResult r[];if(!AnalyzeAllTimeframes(r)) return false;
 bool sent=StartAIRequest(r,ExecutionMode==EXECUTION_HYBRID,m_candidateBuy,m_candidateScore,m_candidatePattern);
 if(sent) m_candidate=false;
 return sent;
}

bool MigrateLegacy()
{
 if(MQLInfoInteger(MQL_TESTER)) return GlobalVariableSet(g_statePrefix+"migrated241",1)>0;
 if(StateGet(g_statePrefix+"migrated241")>0) return true;
 string old="MT3."+IntegerToString((long)TextHash(SymbolScope(m_symbol)))+".";
 string keys[];double values[];
 for(int i=0;i<GlobalVariablesTotal();i++)
 {
  string key=GlobalVariableName(i);if(StringFind(key,old)!=0) continue;
  int n=ArraySize(keys);if(ArrayResize(keys,n+1)!=n+1 || ArrayResize(values,n+1)!=n+1) return false;
  keys[n]=g_statePrefix+StringSubstr(key,StringLen(old));values[n]=GlobalVariableGet(key);
 }
 for(int i=0;i<ArraySize(keys);i++) if(!GlobalVariableCheck(keys[i]) && GlobalVariableSet(keys[i],values[i])==0) return false;
 if(GlobalVariableSet(g_statePrefix+"migrated241",1)==0) return false;
 GlobalVariablesFlush();return true;
}

bool Init(string symbol,bool chart,bool scan)
{
 m_symbol=symbol;m_isChart=chart;m_scanEnabled=scan;
 if(!SymbolSelect(symbol,true)) return false;
 m_point=SymbolInfoDouble(symbol,SYMBOL_POINT);m_digits=(int)SymbolInfoInteger(symbol,SYMBOL_DIGITS);
 if(m_point<=0 || TickSize()<=0 || ArraySize(m_mtf)!=7) return false;
 g_statePrefix=SymbolPrefix(symbol);
 m_journalFrom=(datetime)StateGet(g_statePrefix+"log.from",(double)TimeCurrent());
 if(m_journalFrom<=0 || m_journalFrom>TimeCurrent()) m_journalFrom=TimeCurrent();
 m_portfolioRejects=StateGet(g_statePrefix+"log.portfolio.rejects");
 m_lastPortfolioRejectBar=(datetime)StateGet(g_statePrefix+"log.portfolio.bar");
 m_portfolioReportDirty=m_portfolioRejects>0;
 g_propPrefix="MT3P."+IntegerToString((long)TextHash(g_account+"/"+EnumToString(FintokeiPlan)+"/"+DoubleToString(FintokeiInitialBalance,2)))+".";
 // Keep v2.41's symbol lock name so an older instance cannot co-own this symbol.
 g_lockKey="MT3L."+IntegerToString((long)TextHash(g_account+"/"+symbol));
 if((!GlobalVariableCheck(g_lockKey) && !GlobalVariableTemp(g_lockKey)) || !GlobalVariableSetOnCondition(g_lockKey,1,0)) return false;
 g_lockOwned=true;
 if(MQLInfoInteger(MQL_TESTER)) {GlobalVariablesDeleteAll(g_statePrefix);GlobalVariableDel(AccountIntent(symbol));}
 if(!MigrateLegacy()) return false;
 LINE_PREFIX="MT3_"+IntegerToString((long)ChartID())+"_";
 trade.SetExpertMagicNumber(MagicNumber);trade.SetAsyncMode(false);trade.SetMarginMode();
 if(!trade.SetTypeFillingBySymbol(symbol)) return false;
 g_lastTradeBar=(datetime)StateGet(g_statePrefix+"bar");g_lastAttemptBar=(datetime)StateGet(g_statePrefix+"attempt.bar");
 g_aiLastBar=(datetime)StateGet(g_statePrefix+"ai.bar");
 if(HasUnresolvedOrder() && GlobalVariableSet(AccountIntent(symbol),1)==0) return false;
 ReconcilePendingOrder();
 g_lastBarTime=iTime(symbol,PERIOD_M1,0);
 if(RunSelfTestsOnInit && !SelfTests()) return false;
 if(m_isChart) ApplyChartTheme();
 g_status="Loading symbol data";
 return true;
}

void ReleaseIndicators()
{
 for(int i=0;i<ArraySize(g_indicators);i++) IndicatorRelease(g_indicators[i].handle);
 ArrayResize(g_indicators,0);
 for(int i=0;i<ArraySize(m_mtf);i++) ZeroMemory(m_mtf[i]);
}

void Shutdown()
{
 CancelAIRequest();if(g_lockOwned) JournalMaintenance();
 if(g_lockOwned)
 {
  if(m_isChart) {DeleteManualPanel();DeleteAutoHorizontalLines();DeleteAutoTrendLines();RestoreChartTheme();}
  GlobalVariableSetOnCondition(g_lockKey,0,1);g_lockOwned=false;
 }
 DiagSummary();
 ReleaseIndicators();GlobalVariablesFlush();
}

void SetScanEnabled(bool enabled)
{
 if(m_scanEnabled==enabled) return;
 m_scanEnabled=enabled;
 if(!enabled) {m_candidate=false;CancelAIRequest();g_status="Removed from entry universe; managing exposure";}
}

void Scan()
{
 Maintain(true);
 if(!m_scanEnabled) return;
 datetime line=iTime(m_symbol,LineTimeframe,0);
 if(line>0 && line!=g_lastLineBar && GetATR(LineTimeframe,14,1)>0)
 {UpdateAllAutoLines();g_lastLineBar=line;}
 g_lastBarTime=iTime(m_symbol,PERIOD_M1,0);
 if(ExecutionMode!=EXECUTION_MANUAL) RefreshCandidate();
}
#include "MT3ReversalPatterns.mqh"
#include "MT3PatternStops.mqh"
#include "MT3TradeJournal.mqh"
};
#endif

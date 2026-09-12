// Included inside SymbolState. The legacy BuildStops remains the fallback implementation.
bool ValidPatternPrice(double price) {return MathIsValidNumber(price) && price>0;}
bool EntryStopsValid(bool buy,MqlTick &tick,double sl,double tp)
{
 double step=TickSize();if(step<=0 || !ValidPatternPrice(sl) || !ValidPatternPrice(tp) || tick.bid<=0 || tick.ask<tick.bid) return false;
 long stops=SymbolInfoInteger(m_symbol,SYMBOL_TRADE_STOPS_LEVEL),freeze=SymbolInfoInteger(m_symbol,SYMBOL_TRADE_FREEZE_LEVEL);
 double gap=(double)MathMax(stops,freeze)*m_point+step,eps=step*1e-8;
 double entry=buy?tick.ask:tick.bid;
 if(MathAbs(sl/step-MathRound(sl/step))>1e-6 || MathAbs(tp/step-MathRound(tp/step))>1e-6) return false;
 return buy?(sl<entry && sl<=tick.bid-gap+eps && tp>=tick.bid+gap-eps):
            (sl>entry && sl>=tick.ask+gap-eps && tp<=tick.ask-gap+eps);
}
bool PatternStopAnchor(bool buy,PatternSignal &p,double &anchor,string &source,string &why)
{
 anchor=0;source="";why="";
 if(!p.valid || p.type==PATTERN_NONE) {why="No valid local pattern";return false;}
 if(PatternDirection(p)!=(buy?ENTRY_BUY:ENTRY_SELL)) {why="Pattern direction mismatch";return false;}
 switch(p.type)
 {
  case PATTERN_BULLISH_123:case PATTERN_BEARISH_123:
   anchor=p.secondPoint;source="PATTERN_123_P3";break;
  case PATTERN_BULLISH_FAILED_BREAKOUT:case PATTERN_BEARISH_FAILED_BREAKOUT:
   anchor=p.headPoint;source="PATTERN_FAILED_BREAK_EXTREME";break;
  case PATTERN_DOUBLE_BOTTOM:case PATTERN_DOUBLE_TOP:
   if(!ValidPatternPrice(p.firstPoint) || !ValidPatternPrice(p.secondPoint)) {why="Missing double pivot";return false;}
   anchor=buy?MathMin(p.firstPoint,p.secondPoint):MathMax(p.firstPoint,p.secondPoint);source="PATTERN_DOUBLE_EXTREME";break;
  case PATTERN_TRIPLE_BOTTOM:case PATTERN_TRIPLE_TOP:
   if(!ValidPatternPrice(p.firstPoint) || !ValidPatternPrice(p.secondPoint) || !ValidPatternPrice(p.headPoint)) {why="Missing triple pivot";return false;}
   anchor=buy?MathMin(p.firstPoint,MathMin(p.secondPoint,p.headPoint)):MathMax(p.firstPoint,MathMax(p.secondPoint,p.headPoint));source="PATTERN_TRIPLE_EXTREME";break;
  case PATTERN_INVERSE_HEAD_SHOULDERS:case PATTERN_HEAD_SHOULDERS:
   anchor=p.headPoint;source="PATTERN_HS_HEAD";break;
  default:why="Unsupported pattern SL";return false;
 }
 if(!ValidPatternPrice(anchor)) {why="Missing/nonfinite pattern anchor";return false;}
 return true;
}
bool BuildEntryStops(bool buy,MqlTick &tick,PatternSignal &p,double &sl,double &tp,string &source,string &fallback)
{
 sl=0;tp=0;source="";fallback="";double anchor=0;
 bool hasPattern=p.valid && p.type!=PATTERN_NONE;
 if(PatternStopAnchor(buy,p,anchor,source,fallback))
 {
  double buffer=StopBuffer(),entry=buy?tick.ask:tick.bid;
  if(GetATR(PERIOD_M1,14,1)<=0 || !MathIsValidNumber(buffer) || buffer<=0) fallback="ATR/buffer unavailable";
  else if(buy?anchor>=entry:anchor<=entry) fallback="Pattern anchor on wrong side of entry";
  else
  {
   sl=buy?PriceFloor(anchor-buffer):PriceCeil(anchor+buffer);
   tp=buy?PriceCeil(entry+(entry-sl)*RiskRewardRatio):PriceFloor(entry-(sl-entry)*RiskRewardRatio);
   // Do not push a valid structural stop farther away to satisfy broker constraints.
   if(EntryStopsValid(buy,tick,sl,tp) && (buy?sl<anchor:sl>anchor)) return true;
   fallback="Pattern stop distance/tick/broker constraints invalid";
  }
 }
 source=hasPattern?"GENERIC_SWING_FALLBACK":"GENERIC_SWING";
 if(hasPattern && (m_lastSLFallbackBar!=iTime(m_symbol,PERIOD_M1,0) || m_lastSLFallbackReason!=fallback))
 {
  Print("SL fallback ",m_symbol," ",PatternName(p.type),": ",fallback);
  m_lastSLFallbackBar=iTime(m_symbol,PERIOD_M1,0);m_lastSLFallbackReason=fallback;
 }
 if(!BuildStops(buy,tick,sl,tp) || !EntryStopsValid(buy,tick,sl,tp)) return false;
 return true;
}
bool PlannedPortfolioRisk(bool buy,MqlTick &tick,double sl,double lot,double &planned)
{
 planned=0;double profit=0;
 double open=buy?tick.ask+DeviationPoints()*m_point:tick.bid-DeviationPoints()*m_point;
 double exit=buy?sl-StopSlippage():sl+StopSlippage();
 if(lot<=0 || open<=0 || exit<=0 || !OrderCalcProfit(buy?ORDER_TYPE_BUY:ORDER_TYPE_SELL,m_symbol,lot,open,exit,profit) || !MathIsValidNumber(profit)) return false;
 planned=MathMax(0.0,-profit)+lot*RoundTurnCommissionPerLot;
 return MathIsValidNumber(planned) && planned>=0;
}
void ReportPortfolioReject(string reason)
{
 g_status="PORTFOLIO RISK REJECT: "+reason;
 datetime bar=iTime(m_symbol,PERIOD_M1,0);
 if(bar>0 && bar!=m_lastPortfolioRejectBar)
 {
  m_lastPortfolioRejectBar=bar;m_portfolioRejects++;
  // Analytical counters are not execution reservations; failure cannot approve a trade.
  if(GlobalVariableSet(g_statePrefix+"log.portfolio.rejects",m_portfolioRejects)==0 ||
     GlobalVariableSet(g_statePrefix+"log.portfolio.bar",(double)bar)==0) Print("TradeLog warning: cannot persist reject count/bar ",m_symbol);
  Print(g_status," | ",m_symbol);m_portfolioReportDirty=true;
 }
}
bool CheckPortfolioEntry(bool buy,MqlTick &tick,double sl,double lot,double &before,double &planned)
{
 string why;bool known=ManagedPortfolioRisk(before,why);
 bool plannedOK=PlannedPortfolioRisk(buy,tick,sl,lot,planned);
 if(!known) before=-1;
 if(!plannedOK) planned=-1;
 if(!EnablePortfolioRiskLimit) return true;
 if(!known) {ReportPortfolioReject(why);return false;}
 if(!plannedOK) {ReportPortfolioReject("Cannot calculate new planned risk");return false;}
 if(!PortfolioBudgetAllows(before,planned,AccountInfoDouble(ACCOUNT_EQUITY)))
 {ReportPortfolioReject(StringFormat("current %.2f + planned %.2f exceeds %.2f",before,planned,AccountInfoDouble(ACCOUNT_EQUITY)*MaxPortfolioRiskPercent/100.0));return false;}
 return true;
}

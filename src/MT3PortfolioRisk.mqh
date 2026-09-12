#ifndef MT3_PORTFOLIO_RISK_MQH
#define MT3_PORTFOLIO_RISK_MQH
// Opening price -> CURRENT SL, in account currency. Profitable stops never offset losses.
bool ManagedPortfolioRisk(double &risk,string &reason)
{
 risk=0;reason="";
 for(int i=0;i<OrdersTotal();i++)
 {
  ulong ticket=OrderGetTicket(i);
  if(ticket==0) {reason="Order list unavailable";return false;}
  if((ulong)OrderGetInteger(ORDER_MAGIC)==MagicNumber)
  {reason="Managed working order has unresolved exposure";return false;}
 }
 bool hedging=AccountInfoInteger(ACCOUNT_MARGIN_MODE)==ACCOUNT_MARGIN_MODE_RETAIL_HEDGING;
 for(int i=0;i<PositionsTotal();i++)
 {
  ulong ticket=PositionGetTicket(i);
  if(ticket==0) {reason="Position list unavailable";return false;}
  string symbol=PositionGetString(POSITION_SYMBOL);
  ulong id=(ulong)PositionGetInteger(POSITION_IDENTIFIER);
  bool owned=(ulong)PositionGetInteger(POSITION_MAGIC)==MagicNumber;
  if(!hedging)
  {
   if(!HistorySelectByPosition(id)) {reason="Netting ownership history unavailable: "+symbol;return false;}
   bool ours=false,foreign=false,reversed=false;
   for(int j=0;j<HistoryDealsTotal();j++)
   {
    ulong deal=HistoryDealGetTicket(j);long entry=HistoryDealGetInteger(deal,DEAL_ENTRY);
    if(entry!=DEAL_ENTRY_IN && entry!=DEAL_ENTRY_INOUT) continue;
    if(entry==DEAL_ENTRY_INOUT) reversed=true;
    if((ulong)HistoryDealGetInteger(deal,DEAL_MAGIC)==MagicNumber && HistoryDealGetString(deal,DEAL_SYMBOL)==symbol) ours=true;
    else foreign=true;
   }
   if((owned || ours) && (!ours || foreign || reversed)) {reason="Mixed/ambiguous netting ownership: "+symbol;return false;}
   owned=owned || ours;
   if(!PositionSelectByTicket(ticket)) {reason="Position changed during risk calculation";return false;}
  }
  if(!owned) continue;
  double open=PositionGetDouble(POSITION_PRICE_OPEN),sl=PositionGetDouble(POSITION_SL),volume=PositionGetDouble(POSITION_VOLUME),profit=0;
  long type=PositionGetInteger(POSITION_TYPE);
  if(!MathIsValidNumber(open) || !MathIsValidNumber(sl) || !MathIsValidNumber(volume) || open<=0 || sl<=0 || volume<=0 ||
     (type!=POSITION_TYPE_BUY && type!=POSITION_TYPE_SELL))
  {reason="Managed position has no valid SL/price/volume: "+symbol;return false;}
  if(!OrderCalcProfit(type==POSITION_TYPE_BUY?ORDER_TYPE_BUY:ORDER_TYPE_SELL,symbol,volume,open,sl,profit) || !MathIsValidNumber(profit))
  {reason="OrderCalcProfit unavailable: "+symbol;return false;}
  risk+=MathMax(0.0,-profit);
  if(!MathIsValidNumber(risk)) {reason="Portfolio risk overflow";return false;}
 }
 return true;
}
bool PortfolioBudgetAllows(double current,double planned,double equity)
{
 return MathIsValidNumber(current) && MathIsValidNumber(planned) && MathIsValidNumber(equity) &&
        current>=0 && planned>=0 && equity>0 && current+planned<=equity*MaxPortfolioRiskPercent/100.0+MathMax(1e-8,equity*1e-12);
}
#endif

// Symbol-scoped analytics. Failures here must never stop protection or change execution approval.
void JournalWarn(string message)
{
 if(m_lastLogWarning==0 || TimeCurrent()-m_lastLogWarning>=10)
 {m_lastLogWarning=TimeCurrent();LogWarning(m_symbol+": "+message);}
}
void JournalMarkSL(ulong id,int kind,double price)
{
 if(!EnableTradeLog) return;
 if(GlobalVariableSet(PositionKey(id,".log.slkind"),kind)==0 || GlobalVariableSet(PositionKey(id,".log.slprice"),price)==0) JournalWarn("SL classification persistence failed");
}
void JournalMarkDD(ulong id)
{
 if(EnableTradeLog && GlobalVariableSet(PositionKey(id,".log.dd"),(double)TimeCurrent())==0) JournalWarn("DD classification persistence failed");
}
string JournalActiveFile() {return TradeLogRoot()+ScopeDigest(m_symbol)+"_active.json";}
void PrepareTradeJournal(bool buy,bool manual,double score,PatternSignal &p,MqlTick &tick,double sl,double tp,double lot,
                         string source,string fallback,double before,double planned)
{
 ZeroMemory(m_logPending);m_logPendingToken=PendingOrderToken();
 if(!EnableTradeLog) return;
 m_logPending.symbol=m_symbol;m_logPending.account=g_account;m_logPending.magic=MagicNumber;m_logPending.dataset=TradeLogRoot();
 m_logPending.buy=buy;m_logPending.hasContext=true;m_logPending.dirty=true;m_logPending.entryTime=TimeCurrent();
 m_logPending.entry=buy?tick.ask:tick.bid;m_logPending.sl=sl;m_logPending.tp=tp;m_logPending.lot=lot;
 m_logPending.entryEquity=AccountInfoDouble(ACCOUNT_EQUITY);m_logPending.score=score;
 m_logPending.mode=EnumToString(ExecutionMode);m_logPending.riskMode=EnumToString(RiskMode);
 m_logPending.pattern=manual?"MANUAL":(p.type==PATTERN_NONE?"AI_ONLY":PatternName(p.type));
 m_logPending.patternId=(!manual && p.type!=PATTERN_NONE)?PatternIdentity(p):"";
 m_logPending.mtf=WeightedMTFScore(m_mtf,buy);m_logPending.patternScore=manual?0:Score100(GetPatternScore(p));
 m_logPending.line=Score100(CalculateLineScore(buy?ENTRY_BUY:ENTRY_SELL)*5);
 m_logPending.agreement=WeightedAgreement(m_mtf,buy);
 m_logPending.spread=tick.ask-tick.bid;m_logPending.atr=GetATR(PERIOD_M1,14,1);
 m_logPending.spreadATR=m_logPending.atr>0?m_logPending.spread/m_logPending.atr:0;
 m_logPending.spreadSL=MathAbs(m_logPending.entry-sl)>0?m_logPending.spread/MathAbs(m_logPending.entry-sl):0;
 m_logPending.portfolioBefore=before;m_logPending.plannedRisk=planned;m_logPending.portfolioAfter=before>=0 && planned>=0?before+planned:-1;
 m_logPending.aiUsed=m_entryAIUsed;m_logPending.aiConfidence=m_entryAIUsed?m_entryAIConfidence:-1;m_logPending.aiResult=m_entryAIUsed?m_entryAIResult:"NOT_USED";
 m_logPending.p1=p.firstPoint;m_logPending.p2=p.headPoint;m_logPending.p3=p.secondPoint;
 if(p.type==PATTERN_DOUBLE_BOTTOM || p.type==PATTERN_DOUBLE_TOP) {m_logPending.p2=p.secondPoint;m_logPending.p3=0;}
 m_logPending.reference=IsFailedBreakout(p.type)?p.referencePrice:0;
 double anchor=0;string anchorSource,why;if(PatternStopAnchor(buy,p,anchor,anchorSource,why)) m_logPending.extreme=anchor;
 m_logPending.slSource=source;m_logPending.slFallback=fallback;m_logPending.excursionCoverage="SAMPLED";
 if(!WriteAIFile(LogIntentFile(m_symbol,m_logPendingToken),TradeRecordJSON(m_logPending))) JournalWarn("entry context write failed; execution safety records are separate");
 if(!WriteAIFile(JournalActiveFile(),"{\"symbol\":"+JsonQuote(m_symbol)+"}")) JournalWarn("active-symbol recovery marker write failed");
}
void JournalAfterSend(double before,double planned)
{
 if(!EnableTradeLog) return;
 m_logPending.portfolioBefore=before;m_logPending.plannedRisk=planned;m_logPending.portfolioAfter=before>=0 && planned>=0?before+planned:-1;
 if(m_logPending.hasContext && !WriteAIFile(LogIntentFile(m_symbol,m_logPendingToken),TradeRecordJSON(m_logPending))) JournalWarn("post-send context write failed; retained in memory");
 m_journalDirty=true;
}
bool JournalAddId(ulong &ids[],ulong id)
{
 if(id==0) return true;
 for(int i=0;i<ArraySize(ids);i++) if(ids[i]==id) return true;
 int n=ArraySize(ids);if(ArrayResize(ids,n+1)!=n+1) {JournalWarn("history ID allocation failed");return false;}
 ids[n]=id;return true;
}
void JournalIdText(string &list,ulong id)
{
 string value=LogU64(id);if(StringFind(";"+list+";",";"+value+";")>=0) return;
 if(list!="") list+=";";list+=value;
}
bool JournalLoadFile(string name,TradeLogRecord &r)
{
 string text;if(!FileIsExist(name,FILE_COMMON)) return false;
 if(!ReadAIFile(name,text) || !ParseTradeRecord(text,r) || r.symbol!=m_symbol || r.dataset!=TradeLogRoot())
 {JournalWarn("invalid/unreadable analytical record "+name);return false;}
 return true;
}
string JournalExitReason(TradeLogRecord &r,long reason,double exitSL)
{
 if(reason==DEAL_REASON_CLIENT || reason==DEAL_REASON_MOBILE || reason==DEAL_REASON_WEB) return "MANUAL_CLOSE";
 if(reason==DEAL_REASON_TP) return "TAKE_PROFIT";
 if(reason==DEAL_REASON_SL)
 {
  double eps=TickSize()*1.5,managed=StateGet(PositionKey(r.position,".log.slprice"));
  if(exitSL<=0) return "OTHER";
  if(MathAbs(exitSL-r.entry)<=eps) return "BREAKEVEN";
  if(MathAbs(exitSL-r.sl)<=eps) return "INITIAL_SL";
  if(managed>0 && MathAbs(exitSL-managed)<=eps && StateGet(PositionKey(r.position,".log.slkind"))==1) return "BREAKEVEN";
  return "TRAILING_SL";
 }
 if(reason==DEAL_REASON_EXPERT && StateGet(PositionKey(r.position,".log.dd"))>0) return "DD_PROTECTION";
 return "OTHER";
}
bool JournalReadHistory(ulong id,TradeLogRecord &r,bool &owned)
{
 owned=false;if(!HistorySelectByPosition(id)) return false;
 bool frozen=r.riskMoney>0 && r.riskDistance>0 && r.lot>0 && r.dealIds!="";
 double oldVolume=frozen?r.lot:0;
 double vin=0,vout=0,inPrice=0,outPrice=0,money=frozen?r.riskMoney:0,distance=frozen?r.riskDistance*r.lot:0;
 string capturedDeals=";"+r.dealIds+";";
 double gross=0,commission=0,swap=0,fee=0,exitSL=0;
 datetime opened=0,closed=0;ulong first=0,firstOrder=0,last=0;long exitReason=0;
 string orderIds="",dealIds="";bool buy=false,sideKnown=false,working=false;
 for(int i=0;i<HistoryDealsTotal();i++)
 {
  ulong deal=HistoryDealGetTicket(i);long type=HistoryDealGetInteger(deal,DEAL_TYPE);
  if(type!=DEAL_TYPE_BUY && type!=DEAL_TYPE_SELL) continue;
  long entry=HistoryDealGetInteger(deal,DEAL_ENTRY);
  if(HistoryDealGetString(deal,DEAL_SYMBOL)!=m_symbol || entry==DEAL_ENTRY_INOUT) return true; // Mixed netting: do not attribute.
  if(entry==DEAL_ENTRY_IN && (ulong)HistoryDealGetInteger(deal,DEAL_MAGIC)!=MagicNumber) return true;
  double volume=HistoryDealGetDouble(deal,DEAL_VOLUME),price=HistoryDealGetDouble(deal,DEAL_PRICE);
  if(!ValidPatternPrice(price) || volume<=0 || !MathIsValidNumber(volume)) return false;
  datetime at=(datetime)HistoryDealGetInteger(deal,DEAL_TIME);ulong order=(ulong)HistoryDealGetInteger(deal,DEAL_ORDER);
  JournalIdText(orderIds,order);JournalIdText(dealIds,deal);
  gross+=HistoryDealGetDouble(deal,DEAL_PROFIT);commission+=HistoryDealGetDouble(deal,DEAL_COMMISSION);
  swap+=HistoryDealGetDouble(deal,DEAL_SWAP);fee+=HistoryDealGetDouble(deal,DEAL_FEE);
  if(entry==DEAL_ENTRY_IN)
  {
   bool side=type==DEAL_TYPE_BUY;if(sideKnown && side!=buy) return true;
   buy=side;sideKnown=true;
   if(opened==0 || at<opened || (at==opened && deal<first)) {opened=at;first=deal;firstOrder=order;}
   vin+=volume;inPrice+=volume*price;
   double originalSL=r.sl;
   if(originalSL<=0) originalSL=HistoryDealGetDouble(deal,DEAL_SL);
   if(originalSL<=0) originalSL=HistoryOrderGetDouble(order,ORDER_SL);
   if(r.sl<=0) r.sl=originalSL;
   if(r.tp<=0) r.tp=HistoryDealGetDouble(deal,DEAL_TP);
   double profit=0;bool captured=frozen && StringFind(capturedDeals,";"+LogU64(deal)+";")>=0;
   if(!captured && originalSL>0 && (buy?originalSL<price:originalSL>price) && OrderCalcProfit(buy?ORDER_TYPE_BUY:ORDER_TYPE_SELL,m_symbol,volume,price,originalSL,profit))
   {money+=MathMax(0.0,-profit);distance+=volume*MathAbs(price-originalSL);}
   else if(!captured && r.hasContext) return false;
   if(OrderSelect(order)) working=true;
  }
  else if(entry==DEAL_ENTRY_OUT || entry==DEAL_ENTRY_OUT_BY)
  {
   vout+=volume;outPrice+=volume*price;
   if(at>closed || (at==closed && deal>last))
   {closed=at;last=deal;exitReason=HistoryDealGetInteger(deal,DEAL_REASON);exitSL=HistoryDealGetDouble(deal,DEAL_SL);}
  }
 }
 if(!sideKnown || vin<=0) return true;
 if(vin<oldVolume-1e-7) return false; // Incomplete history must not rewrite frozen initial risk.
 if(!frozen)
 {
  double unit=StateGet(PositionKey(id,".unit")),initialDistance=StateGet(PositionKey(id,".r"));
  // Reuse entry-time conversion only when the core snapshot covers the same fills.
  // Different-price partial fills must retain their volume-weighted actual SL distance.
  if(unit>0 && initialDistance>0 && MathAbs(initialDistance-distance/vin)<=TickSize()*1e-6) money=unit*vin;
 }
 owned=true;r.position=id;r.order=firstOrder;r.deal=first;r.exitDeal=last;r.buy=buy;
 r.orderIds=orderIds;r.dealIds=dealIds;r.entryTime=opened;r.entry=inPrice/vin;r.lot=vin;
 r.riskMoney=money;r.riskDistance=distance/vin;r.riskPercent=r.entryEquity>0?money/r.entryEquity*100.0:0;
 r.closed=!PositionIdOpen(id) && !working && MathAbs(vin-vout)<1e-7 && closed>0;
 r.gross=gross;r.commission=commission;r.swap=swap;r.fee=fee;r.net=gross+commission+swap+fee;
 if(r.closed)
 {
  r.exitTime=closed;r.exitPrice=outPrice/vout;r.realizedR=money>0?r.net/money:0;
  r.exitReason=JournalExitReason(r,exitReason,exitSL);
  double change=(buy?1.0:-1.0)*(r.exitPrice-r.entry);r.mfe=MathMax(r.mfe,change);r.mae=MathMax(r.mae,-change);
 }
 r.dirty=true;return true;
}
int JournalIndex(ulong id)
{for(int i=0;i<ArraySize(m_journal);i++) if(m_journal[i].position==id) return i;return -1;}
bool JournalQueue(ulong id)
{
 int idx=JournalIndex(id);
 if(idx>=0) {bool ours;return JournalReadHistory(id,m_journal[idx],ours);}
 TradeLogRecord r;ZeroMemory(r);bool restored=JournalLoadFile(LogPositionBase(m_symbol,id)+".json",r);
 if(restored && r.closed)
 {
  bool owned=false;if(!JournalReadHistory(id,r,owned)) return false;
  if(!owned) return true;
  string csv;if(ReadAIFile(LogPositionBase(m_symbol,id)+".csv",csv) && csv==TradeRecordCSV(r)) return true;
 }
 if(!restored)
 {
  if(!HistorySelectByPosition(id)) return false;
  string token="";bool ours=false;
  for(int i=0;i<HistoryDealsTotal();i++)
  {
   ulong d=HistoryDealGetTicket(i);
   if(HistoryDealGetInteger(d,DEAL_ENTRY)!=DEAL_ENTRY_IN || (ulong)HistoryDealGetInteger(d,DEAL_MAGIC)!=MagicNumber || HistoryDealGetString(d,DEAL_SYMBOL)!=m_symbol) continue;
   ours=true;ulong order=(ulong)HistoryDealGetInteger(d,DEAL_ORDER);string comment=HistoryOrderGetString(order,ORDER_COMMENT);
   if(StringFind(comment,"MT3#")==0) {token=StringSubstr(comment,4);break;}
  }
  if(!ours) return true;
  bool loaded=false;
  if(token!="" && token==m_logPendingToken && m_logPending.hasContext) {r=m_logPending;loaded=true;}
  else if(StringLen(token)==16) loaded=JournalLoadFile(LogIntentFile(m_symbol,token),r);
  if(!loaded)
  {
   ZeroMemory(r);r.account=g_account;r.symbol=m_symbol;r.magic=MagicNumber;r.dataset=TradeLogRoot();
   r.pattern="UNKNOWN";r.mode="UNKNOWN";r.slSource="UNKNOWN_LEGACY";r.riskMode="UNKNOWN";
   r.aiConfidence=-1;r.portfolioBefore=-1;r.portfolioAfter=-1;r.plannedRisk=-1;r.aiResult="UNKNOWN";
   r.excursionCoverage="SAMPLED_WITH_GAPS";
  }
 }
 else {r.restored=true;if(!r.closed) r.excursionCoverage="SAMPLED_WITH_GAPS";}
 bool owned=false;if(!JournalReadHistory(id,r,owned)) return false;
 if(!owned) return true;
 int n=ArraySize(m_journal);if(ArrayResize(m_journal,n+1)!=n+1) {JournalWarn("record allocation failed");return false;}
 m_journal[n]=r;return true;
}
void JournalSample()
{
 if(!EnableTradeLog) return;
 MqlTick tick;if(!FreshQuote(tick)) return;
 for(int i=0;i<ArraySize(m_journal);i++)
 {
  if(m_journal[i].closed || !PositionIdOpen(m_journal[i].position)) continue;
  double change=(m_journal[i].buy?tick.bid-m_journal[i].entry:m_journal[i].entry-tick.ask);
  if(change>m_journal[i].mfe || -change>m_journal[i].mae)
  {m_journal[i].mfe=MathMax(m_journal[i].mfe,change);m_journal[i].mae=MathMax(m_journal[i].mae,-change);m_journal[i].dirty=true;}
 }
}
bool JournalPersist(TradeLogRecord &r)
{
 string base=LogPositionBase(m_symbol,r.position);
 r.lastSaved=TimeCurrent();
 if(!WriteAIFile(base+".json",TradeRecordJSON(r)) || !WriteAIFile(base+".csv",TradeRecordCSV(r)))
 {JournalWarn("record/CSV write failed for "+LogU64(r.position)+"; will retry");return false;}
 r.dirty=false;return true;
}
void JournalMaintenance()
{
 if(!EnableTradeLog) return;
 JournalSample();datetime now=TimeCurrent();
 if(!m_journalDirty && now-m_lastJournalAt<15) return;
 m_lastJournalAt=now;bool ok=true;
 if(HistorySelect((datetime)MathMax(0,(long)m_journalFrom-300),now))
 {
  ulong ids[];
  for(int i=0;i<HistoryDealsTotal();i++)
  {
   ulong d=HistoryDealGetTicket(i);if(HistoryDealGetString(d,DEAL_SYMBOL)==m_symbol)
    if(!JournalAddId(ids,(ulong)HistoryDealGetInteger(d,DEAL_POSITION_ID))) ok=false;
  }
  for(int i=0;i<PositionsTotal();i++)
   if(PositionGetTicket(i)>0 && PositionGetString(POSITION_SYMBOL)==m_symbol && (ulong)PositionGetInteger(POSITION_MAGIC)==MagicNumber)
    if(!JournalAddId(ids,(ulong)PositionGetInteger(POSITION_IDENTIFIER))) ok=false;
  for(int i=0;i<ArraySize(ids);i++) if(!JournalQueue(ids[i])) ok=false;
 }
 else {ok=false;JournalWarn("history unavailable for log reconciliation");}
 for(int i=ArraySize(m_journal)-1;i>=0;i--)
 {
  if(m_journal[i].dirty && !JournalPersist(m_journal[i])) {ok=false;continue;}
  if(m_journal[i].closed && !m_journal[i].dirty)
  {int last=ArraySize(m_journal)-1;if(i!=last) m_journal[i]=m_journal[last];ArrayResize(m_journal,last);}
 }
 if(ok)
 {
  m_journalFrom=now;
  if(GlobalVariableSet(g_statePrefix+"log.from",(double)now)==0) JournalWarn("analytical history cursor write failed");
 }
 if(m_portfolioReportDirty)
 {
  string h="",row="";LogCSVAdd(h,row,"DatasetID",TradeLogRoot(),true);LogCSVAdd(h,row,"Symbol",m_symbol,true);
  LogCSVAdd(h,row,"PortfolioRiskRejects",LogNumber(m_portfolioRejects));LogCSVAdd(h,row,"CountingUnit","REJECTED_SYMBOL_M1_BARS",true);
  if(WriteAIFile(TradeLogRoot()+ScopeDigest(m_symbol)+"_risk_rejects.csv",ShortToString(0xFEFF)+h+"\r\n"+row+"\r\n")) m_portfolioReportDirty=false;
  else {JournalWarn("portfolio reject report write failed");ok=false;}
 }
 if(ArraySize(m_journal)==0 && !HasOurPosition() && !HasUnresolvedOrder()) FileDelete(JournalActiveFile(),FILE_COMMON);
 m_journalDirty=!ok;
}

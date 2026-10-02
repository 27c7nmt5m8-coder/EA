// Optional Tester-only observer. No account identifiers or order tickets are exported.
enum TPOStageId
{
 TPO_SIGNAL,TPO_SCORE,TPO_VALID_STOP,TPO_SPREAD_EVALUATED,TPO_SPREAD_PASS,
 TPO_BEFORE_SAFETY,TPO_AFTER_SAFETY,TPO_RISK_REACHED,TPO_RISK_PASS,TPO_RISK_FAIL,
 TPO_ORDER_REQUEST,TPO_ACCEPTED,TPO_REJECTED,TPO_STAGE_COUNT
};
struct TPORecord
{
 string key,symbol; datetime bar; ulong stages,reasons;
 int safetyReason,nonSafetyReason,orderReason;
};
TPORecord g_tpo[];
bool g_tpShadow=false;
int g_tpLastReject=-1,g_tpOrderOpportunity=-1;
ulong g_tpoUnknown=0;
ulong g_tpoTickSequence=0,g_tpoTickBlocks[TP_COUNT],g_tpoLastBlockedTick[TP_COUNT];
struct TPODay {datetime day;ulong ticks;int minutes;long lastMinute,lastMsc,maxGap;};
TPODay g_tpoDays[];

int TPOFind(const string symbol,const datetime bar,const string identity,const bool buy,const bool create=true)
{
 string key=symbol+"/"+IntegerToString(bar)+"/"+identity+(buy?"/B":"/S");
 for(int i=ArraySize(g_tpo)-1;i>=0;i--)
 {
  if(g_tpo[i].key==key) return i;
 }
 if(!create) return -1;
 int n=ArraySize(g_tpo);
 if(ArrayResize(g_tpo,n+1,256)!=n+1) {g_tpoUnknown++;return -1;}
 g_tpo[n].key=key;g_tpo[n].symbol=symbol;g_tpo[n].bar=bar;
 g_tpo[n].stages=0;g_tpo[n].reasons=0;
 g_tpo[n].safetyReason=-1;g_tpo[n].nonSafetyReason=-1;g_tpo[n].orderReason=-1;
 return n;
}
bool TPOHas(const int index,const int stage)
{return index>=0 && index<ArraySize(g_tpo) && (g_tpo[index].stages&((ulong)1<<stage))!=0;}
void TPOStage(const int index,const int stage)
{if(index>=0 && index<ArraySize(g_tpo)) g_tpo[index].stages|=((ulong)1<<stage);}
void TPOReason(const int index,const int reason,const bool safety=false,const bool order=false)
{
 if(index<0 || index>=ArraySize(g_tpo) || reason<0 || reason>=TP_COUNT) return;
 g_tpo[index].reasons|=((ulong)1<<reason);
 if(order) g_tpo[index].orderReason=reason;
 else if(safety) g_tpo[index].safetyReason=reason;
 else g_tpo[index].nonSafetyReason=reason;
}
void TPOActual(const int counter)
{
 if(g_tpShadow || g_tpOrderOpportunity<0) return;
 int stage=-1;
 if(counter==TP_RISK_REACHED) stage=TPO_RISK_REACHED;
 else if(counter==TP_RISK_FAILED) stage=TPO_RISK_FAIL;
 else if(counter==TP_ORDER_REQUESTS) stage=TPO_ORDER_REQUEST;
 else if(counter==TP_ORDER_SUCCEEDED) stage=TPO_ACCEPTED;
 else if(counter==TP_ORDER_FAILED) stage=TPO_REJECTED;
 if(stage>=0) TPOStage(g_tpOrderOpportunity,stage);
}
void TPORejectTick(const int reason)
{
 if(reason<0 || reason>=TP_COUNT || g_tpoTickSequence==0) return;
 if(g_tpoLastBlockedTick[reason]!=g_tpoTickSequence)
 {g_tpoLastBlockedTick[reason]=g_tpoTickSequence;g_tpoTickBlocks[reason]++;}
}
int TPOCount(const int stage)
{int n=0;for(int i=0;i<ArraySize(g_tpo);i++) if(TPOHas(i,stage)) n++;return n;}
int TPOBlockedOnly()
{int n=0;for(int i=0;i<ArraySize(g_tpo);i++) if(TPOHas(i,TPO_BEFORE_SAFETY) && !TPOHas(i,TPO_AFTER_SAFETY)) n++;return n;}
bool TPOHasReason(const int i,const int reason)
{return (g_tpo[i].reasons&((ulong)1<<reason))!=0;}
int TPOTerminalReason(const int i)
{
 if(TPOHas(i,TPO_ACCEPTED)) return -1;
 if(TPOHas(i,TPO_AFTER_SAFETY)) return g_tpo[i].orderReason>=0?g_tpo[i].orderReason:TP_ENTRY_OTHER;
 if(TPOHas(i,TPO_BEFORE_SAFETY)) return g_tpo[i].safetyReason;
 // Stage masks mean "ever passed". A later upstream failure must not hide
 // the furthest gate reached earlier by this same opportunity.
 if(TPOHas(i,TPO_SPREAD_PASS))
 {
  if(TPOHasReason(i,TP_ENTRY_SNAPSHOT)) return TP_ENTRY_SNAPSHOT;
  if(TPOHasReason(i,TP_ENTRY_LOCATION)) return TP_ENTRY_LOCATION;
  return TP_ENTRY_OTHER;
 }
 if(TPOHas(i,TPO_SPREAD_EVALUATED)) return TP_ENTRY_SPREAD;
 if(TPOHas(i,TPO_SCORE))
 {
  if(TPOHasReason(i,TP_ENTRY_STOPS)) return TP_ENTRY_STOPS;
  if(TPOHasReason(i,TP_ENTRY_QUOTE)) return TP_ENTRY_QUOTE;
  if(TPOHasReason(i,TP_ENTRY_DIRECTION)) return TP_ENTRY_DIRECTION;
  return TP_ENTRY_OTHER;
 }
 if(TPOHasReason(i,TP_ENTRY_SCORE)) return TP_ENTRY_SCORE;
 if(TPOHasReason(i,TP_ENTRY_DIRECTION)) return TP_ENTRY_DIRECTION;
 return TP_ENTRY_OTHER;
}
bool TPOSelfTest()
{
 ArrayResize(g_tpo,0);
 int a=TPOFind("SYNTH",60,"pattern",true),same=TPOFind("SYNTH",60,"pattern",true);
 int b=TPOFind("SYNTH",120,"pattern",true);
 TPOStage(a,TPO_SIGNAL);TPOStage(a,TPO_SIGNAL);TPOStage(a,TPO_BEFORE_SAFETY);
 TPOReason(a,TP_SAFETY_RISK_CAP,true);TPOStage(a,TPO_AFTER_SAFETY);TPOStage(a,TPO_ACCEPTED);
 TPOStage(b,TPO_SIGNAL);TPOStage(b,TPO_BEFORE_SAFETY);TPOReason(b,TP_SAFETY_POSITION,true);
 bool ok=a==same && a!=b && TPOCount(TPO_SIGNAL)==2 && TPOCount(TPO_BEFORE_SAFETY)==2 &&
         TPOCount(TPO_AFTER_SAFETY)==1 && TPOBlockedOnly()==1 && TPOTerminalReason(a)==-1 &&
         TPOTerminalReason(b)==TP_SAFETY_POSITION;
 // A disabled direction is rejected before score evaluation. Do not call it a score failure.
 int c=TPOFind("SYNTH",180,"direction",false);TPOStage(c,TPO_SIGNAL);
 TPOReason(c,TP_ENTRY_DIRECTION);
 ok=ok && TPOTerminalReason(c)==TP_ENTRY_DIRECTION;
 // Symbols can have asynchronous bars; an older record must not hide a newer key.
 TPOFind("OTHER",30,"old_bar",true);
 ok=ok && TPOFind("SYNTH",120,"pattern",true,false)==b &&
         TPOFind("SYNTH",120,"pattern",true)==b && ArraySize(g_tpo)==4;
 int d=TPOFind("SYNTH",240,"furthest",true);
 TPOStage(d,TPO_SIGNAL);TPOStage(d,TPO_SCORE);TPOStage(d,TPO_SPREAD_EVALUATED);TPOStage(d,TPO_SPREAD_PASS);
 TPOReason(d,TP_ENTRY_LOCATION);TPOReason(d,TP_ENTRY_SPREAD);
 ok=ok && TPOTerminalReason(d)==TP_ENTRY_LOCATION;
 ArrayResize(g_tpo,0);g_tpoUnknown=0;
 Print("TESTER_OPPORTUNITY_SELFTEST ",ok?"PASS":"FAIL");return ok;
}
void TPORecordTick()
{
 g_tpoTickSequence++;
 MqlTick t;if(!SymbolInfoTick(_Symbol,t) || t.time_msc<=0) {g_tpoUnknown++;return;}
 datetime day=(datetime)((long)t.time/86400*86400);int n=ArraySize(g_tpoDays),i=n-1;
 if(n==0 || g_tpoDays[i].day!=day)
 {
  if(ArrayResize(g_tpoDays,n+1)!=n+1) {g_tpoUnknown++;return;}
  i=n;g_tpoDays[i].day=day;g_tpoDays[i].ticks=0;g_tpoDays[i].minutes=0;
  g_tpoDays[i].lastMinute=-1;g_tpoDays[i].lastMsc=0;g_tpoDays[i].maxGap=0;
 }
 g_tpoDays[i].ticks++;
 long minute=t.time_msc/60000;
 if(minute!=g_tpoDays[i].lastMinute) {g_tpoDays[i].minutes++;g_tpoDays[i].lastMinute=minute;}
 if(g_tpoDays[i].lastMsc>0) g_tpoDays[i].maxGap=MathMax(g_tpoDays[i].maxGap,t.time_msc-g_tpoDays[i].lastMsc);
 g_tpoDays[i].lastMsc=t.time_msc;
}
void TPOPrintSummary()
{
 int before=TPOCount(TPO_BEFORE_SAFETY),after=TPOCount(TPO_AFTER_SAFETY),blocked=TPOBlockedOnly(),blockedAny=0;
 for(int i=0;i<ArraySize(g_tpo);i++) if(TPOHas(i,TPO_BEFORE_SAFETY) && g_tpo[i].safetyReason>=0) blockedAny++;
 if(before!=after+blocked) g_tpoUnknown++;
 Print(StringFormat("TESTER_OPPORTUNITY_SUMMARY unit=symbol_bar_pattern_direction signals=%d score_pass=%d valid_stop=%d spread_evaluated=%d spread_pass=%d before_safety=%d safety_blocked_only=%d safety_blocked_any=%d after_safety=%d risk_reached=%d risk_pass=%d risk_fail=%d order_request=%d accepted=%d rejected=%d unknown=%I64u",
  TPOCount(TPO_SIGNAL),TPOCount(TPO_SCORE),TPOCount(TPO_VALID_STOP),TPOCount(TPO_SPREAD_EVALUATED),TPOCount(TPO_SPREAD_PASS),before,blocked,blockedAny,after,
  TPOCount(TPO_RISK_REACHED),TPOCount(TPO_RISK_PASS),TPOCount(TPO_RISK_FAIL),TPOCount(TPO_ORDER_REQUEST),TPOCount(TPO_ACCEPTED),TPOCount(TPO_REJECTED),g_tpoUnknown));
 for(int reason=TP_ENTRY_UNIVERSE;reason<TP_COUNT;reason++)
 {
  int ever=0,terminal=0,blockedCandidate=0;
  for(int i=0;i<ArraySize(g_tpo);i++)
  {
   if((g_tpo[i].reasons&((ulong)1<<reason))!=0) ever++;
   if(TPOTerminalReason(i)==reason) terminal++;
   if(TPOHas(i,TPO_BEFORE_SAFETY) && !TPOHas(i,TPO_AFTER_SAFETY) && g_tpo[i].safetyReason==reason) blockedCandidate++;
  }
  if(ever>0 || terminal>0) Print(StringFormat("TESTER_OPPORTUNITY_BLOCK reason=%d ever=%d terminal=%d candidate_blocked_only=%d",reason,ever,terminal,blockedCandidate));
  if(g_tpoTickBlocks[reason]>0) Print(StringFormat("TESTER_TICK_BLOCK reason=%d unique_ticks=%I64u",reason,g_tpoTickBlocks[reason]));
 }
 for(int i=0;i<ArraySize(g_tpoDays);i++)
  Print(StringFormat("TESTER_OPPORTUNITY_DAY date=%s ticks=%I64u quote_minutes=%d max_gap_seconds=%.3f",TimeToString(g_tpoDays[i].day,TIME_DATE),g_tpoDays[i].ticks,g_tpoDays[i].minutes,g_tpoDays[i].maxGap/1000.0));
 string start=ArraySize(g_tpoDays)>0?TimeToString(g_tpoDays[0].day,TIME_DATE):"none";
 string file="CodexOOS_20260927_"+_Symbol+"_"+start+"_A"+DoubleToString(MaxSpreadATR,2)+"_S"+DoubleToString(MaxSpreadSL,2)+".csv";
 int h=FileOpen(file,FILE_WRITE|FILE_CSV|FILE_ANSI|FILE_COMMON,',');
 if(h==INVALID_HANDLE) {Print("TESTER_OPPORTUNITY_EXPORT FAIL error=",GetLastError());return;}
 FileWrite(h,"opportunity","symbol","bar","stage_mask","reason_mask","safety_reason","non_safety_reason","order_reason");
 for(int i=0;i<ArraySize(g_tpo);i++)
  FileWrite(h,i,g_tpo[i].symbol,(long)g_tpo[i].bar,g_tpo[i].stages,g_tpo[i].reasons,g_tpo[i].safetyReason,g_tpo[i].nonSafetyReason,g_tpo[i].orderReason);
 FileFlush(h);FileClose(h);
 Print(StringFormat("TESTER_OPPORTUNITY_EXPORT OK rows=%d file=%s",ArraySize(g_tpo),file));
}

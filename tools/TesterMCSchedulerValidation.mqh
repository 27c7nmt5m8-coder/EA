// Tester-only, observational storage. Scoped receipt keys remain in RAM only.
struct MCVContext
{
 int cycle,inputVersion,stateVersion,historyVersion,positionKind;
 bool ready,allowed,active,historyOK,historyDirty;
 string digest;
};
struct MCVRequest
{
 MCVContext before,after;ulong start,elapsed;long server;bool force,sameInput,sameState,fresh,heavy;
 int path;string symbol;
};
struct MCVClaimRecord {string key,claimant;};
struct MCVGuardRecord
{
 string id,symbol,reason,prior;long bar,first,last;ulong count;bool shadow,actual;int next;
 MCVContext firstContext,lastContext;
};
struct MCVTiming
{
 string event,symbol,id;ulong start,finish;long serverStart,serverEnd,quoteMsc;
 uint retcode;bool success;
};
MCVRequest g_mcvRequests[];
MCVClaimRecord g_mcvClaims[];
MCVGuardRecord g_mcvGuards[];
int g_mcvGuardHeads[8192];
MCVTiming g_mcvTimings[];
ulong g_mcvManageUs[],g_mcvNoRequestUs[];
struct MCVTimeSummary
{
 ulong count,firstEntry,lastExit;long firstServer,lastServer,firstQuote,lastQuote;
 ulong knownQuotes,unknownQuotes;
};
MCVTimeSummary g_mcvTickSummary,g_mcvManageSummary,g_mcvNoRequestSummary;
ulong g_mcvUnknown=0,g_mcvPriorUnknown=0;
int MCV_LIMIT=2000000;
const int MCV_DURATION_LIMIT=3000000;

void MCVSummarize(MCVTimeSummary &s,const ulong start,const ulong finish,const long serverStart,const long serverEnd,const long quoteMsc)
{
 if(s.count==0) {s.firstEntry=start;s.firstServer=serverStart;s.firstQuote=quoteMsc;}
 s.count++;s.lastExit=finish;s.lastServer=serverEnd;s.lastQuote=quoteMsc;
 if(quoteMsc>0) s.knownQuotes++;else s.unknownQuotes++;
}
void MCVDuration(ulong &values[],const ulong duration)
{
 int n=ArraySize(values);
 if(n>=MCV_DURATION_LIMIT || ArrayResize(values,n+1,8192)!=n+1) {g_mcvUnknown++;return;}
 values[n]=duration;
}
void MCVRequestEnd(MCVRequest &r,const MCVContext &after,const bool heavy)
{
 if(!MQLInfoInteger(MQL_TESTER)) return;
 r.after=after;r.heavy=heavy;
 if(!r.force && r.before.cycle==after.cycle)
 {
  MCVDuration(g_mcvNoRequestUs,r.elapsed);
  MCVSummarize(g_mcvNoRequestSummary,r.start,r.start+r.elapsed,r.server,(long)TimeCurrent(),0);
  return;
 }
 int n=ArraySize(g_mcvRequests);
 if(n>=MCV_LIMIT || ArrayResize(g_mcvRequests,n+1,8192)!=n+1) {g_mcvUnknown++;return;}
 g_mcvRequests[n]=r;
}
string MCVPrior(const string key)
{
 for(int i=ArraySize(g_mcvClaims)-1;i>=0;i--) if(g_mcvClaims[i].key==key) return g_mcvClaims[i].claimant;
 return "UNKNOWN";
}
void MCVRemember(const string key,const string claimant)
{
 if(!MQLInfoInteger(MQL_TESTER)) return;
 for(int i=ArraySize(g_mcvClaims)-1;i>=0;i--)
  if(g_mcvClaims[i].key==key) {g_mcvClaims[i].claimant=claimant;return;}
 int n=ArraySize(g_mcvClaims);
 if(n>=MCV_LIMIT || ArrayResize(g_mcvClaims,n+1,256)!=n+1) {g_mcvUnknown++;return;}
 g_mcvClaims[n].key=key;g_mcvClaims[n].claimant=claimant;
}
void MCVGuardAppend(const string id,const string symbol,const long bar,const string reason,const string prior,const MCVContext &c)
{
 if(!MQLInfoInteger(MQL_TESTER)) return;
 long now=(long)TimeCurrent();
 int bucket=(int)(TextHash(id+"/"+reason+"/"+IntegerToString(bar))%8192);
 for(int entry=g_mcvGuardHeads[bucket];entry>0;)
 {
  int i=entry-1;entry=g_mcvGuards[i].next;
  if(g_mcvGuards[i].id==id && g_mcvGuards[i].reason==reason && g_mcvGuards[i].bar==bar)
  {
   g_mcvGuards[i].last=now;g_mcvGuards[i].count++;g_mcvGuards[i].lastContext=c;
   g_mcvGuards[i].shadow=g_mcvGuards[i].shadow || g_tpShadow;g_mcvGuards[i].actual=g_mcvGuards[i].actual || !g_tpShadow;
   // Keep the first causal claimant; an unexpected change is explicitly unknown.
   if(g_mcvGuards[i].prior!=prior) {g_mcvGuards[i].prior="UNKNOWN";g_mcvUnknown++;}
   return;
  }
 }
 int n=ArraySize(g_mcvGuards);
 if(n>=MCV_LIMIT || ArrayResize(g_mcvGuards,n+1,1024)!=n+1) {g_mcvUnknown++;return;}
 MCVGuardRecord r;ZeroMemory(r);r.id=id;r.symbol=symbol;r.bar=bar;r.reason=reason;r.prior=prior;
 r.first=now;r.last=now;r.count=1;r.firstContext=c;r.lastContext=c;r.shadow=g_tpShadow;r.actual=!g_tpShadow;
 r.next=g_mcvGuardHeads[bucket];g_mcvGuards[n]=r;g_mcvGuardHeads[bucket]=n+1;
 if(prior=="UNKNOWN") g_mcvPriorUnknown++;
}
void MCVTimingAppend(const string event,const string symbol,const string id,const ulong start,const ulong finish,
                     const long serverStart,const long serverEnd,const long quoteMsc,const uint retcode=0,const bool success=false)
{
 if(!MQLInfoInteger(MQL_TESTER)) return;
 int n=ArraySize(g_mcvTimings);
 if(n>=MCV_LIMIT || ArrayResize(g_mcvTimings,n+1,8192)!=n+1) {g_mcvUnknown++;return;}
 MCVTiming t;t.event=event;t.symbol=symbol;t.id=id;t.start=start;t.finish=finish;t.serverStart=serverStart;
 t.serverEnd=serverEnd;t.quoteMsc=quoteMsc;t.retcode=retcode;t.success=success;g_mcvTimings[n]=t;
}
void MCVTickEnd(const ulong start,const ulong finish,const long serverStart,const long quoteMsc)
{
 if(!MQLInfoInteger(MQL_TESTER)) return;
 MCVSummarize(g_mcvTickSummary,start,finish,serverStart,(long)TimeCurrent(),quoteMsc);
}
void MCVManageEnd(const ulong start,const ulong finish,const long serverStart)
{
 if(!MQLInfoInteger(MQL_TESTER)) return;
 MCVDuration(g_mcvManageUs,finish-start);
 MCVSummarize(g_mcvManageSummary,start,finish,serverStart,(long)TimeCurrent(),0);
}
void MCVSummaryWrite(const int h,const string event,MCVTimeSummary &s,ulong &values[])
{
 ArraySort(values);
 if(!FileWrite(h,event,s.count,ArraySize(values),MCSSum(values),MCSQuantile(values,.5),MCSQuantile(values,.9),MCSQuantile(values,.95),MCSQuantile(values,.99),MCSQuantile(values,1),s.firstEntry,s.lastExit,s.firstServer,s.lastServer,s.firstQuote,s.lastQuote,s.knownQuotes,s.unknownQuotes,"UNKNOWN")) g_mcvUnknown++;
}

bool MCVPrivacySelfTest()
{
 if(!MQLInfoInteger(MQL_TESTER)) return false;
 // Synthetic in-memory fixture only. Never print/serialize this record to disk.
 TradeLogRecord original;ZeroMemory(original);
 original.account=g_account;original.magic=MagicNumber;original.symbol=_Symbol;original.dataset=TradeLogRoot();
 original.position=9007199254741009;original.order=21;original.deal=22;original.exitDeal=23;
 original.entryTime=100;original.exitTime=200;original.lastSaved=201;
 original.buy=true;original.closed=true;original.hasContext=true;original.dirty=true;
 original.entry=128.125;original.sl=127.25;original.tp=130.5;
 original.riskDistance=.875;original.riskMoney=16.5;original.riskPercent=.125;original.lot=.25;
 original.score=87.5;original.mtf=81.25;original.patternScore=75.125;original.line=62.5;original.agreement=.875;
 original.spread=.015625;original.spreadATR=.03125;original.spreadSL=.0625;original.atr=.5;
 original.portfolioBefore=.125;original.portfolioAfter=.25;original.plannedRisk=.125;original.aiConfidence=-1;
 original.p1=124.5;original.p2=123.25;original.p3=125.125;original.reference=126.25;original.extreme=123.125;
 original.exitPrice=130.5;original.gross=32.25;original.commission=-.125;original.swap=-.25;original.fee=-.0625;
 original.net=31.8125;original.realizedR=1.5;original.mfe=2.125;original.mae=.375;original.entryEquity=10000.5;
 original.mode="SYNTHETIC";original.pattern="SYNTHETIC";original.patternId="SYNTHETIC";
 original.aiResult="synthetic quoted \"value\"";original.orderIds="21";original.dealIds="22;23";
 string json=TradeRecordJSON(original),csv=TradeRecordCSV(original);
 bool ok=StringLen(g_account)>0 && StringFind(json,g_account)<0 && StringFind(csv,g_account)<0 &&
  StringFind(json,JsonQuote(g_account))<0 && StringFind(csv,CSVCell(g_account,true))<0 &&
  StringFind(json,JsonQuote("REDACTED_TESTER_ACCOUNT"))>=0 && StringFind(csv,CSVCell("REDACTED_TESTER_ACCOUNT",true))>=0;
 TradeLogRecord restored;bool parsed=ParseTradeRecord(json,restored);
 ok=ok && parsed;
 if(parsed)
 {
  // 17-digit numeric serialization plus an identical reserialization checks
  // every serialized field. Explicit bit/64-bit witnesses cover core values.
  ok=ok && restored.account==g_account && restored.magic==MagicNumber && restored.symbol==_Symbol &&
   restored.dataset==TradeLogRoot() && TradeRecordJSON(restored)==json && TradeRecordCSV(restored)==csv &&
   restored.position==original.position && restored.order==original.order && restored.deal==original.deal && restored.exitDeal==original.exitDeal &&
   MCSBitPattern(restored.entry)==MCSBitPattern(original.entry) && MCSBitPattern(restored.sl)==MCSBitPattern(original.sl) &&
   MCSBitPattern(restored.tp)==MCSBitPattern(original.tp) && MCSBitPattern(restored.riskDistance)==MCSBitPattern(original.riskDistance) &&
   MCSBitPattern(restored.riskMoney)==MCSBitPattern(original.riskMoney) && MCSBitPattern(restored.net)==MCSBitPattern(original.net);
 }
 string expectedRoot="CodexMCV"+IntegerToString(MCS_MODE)+"_20260927_TradeLogs\\";
 ok=ok && StringFind(original.dataset,expectedRoot)==0;
 TradeLogRecord wrongMagic=original,rejected;wrongMagic.magic=original.magic^1;
 ok=ok && !ParseTradeRecord(TradeRecordJSON(wrongMagic),rejected);
 string wrongAccount=json;
 int replaced=StringReplace(wrongAccount,JsonQuote("REDACTED_TESTER_ACCOUNT"),JsonQuote("SYNTHETIC_FOREIGN_ACCOUNT"));
 ok=ok && replaced==1 && !ParseTradeRecord(wrongAccount,rejected);
 if(!ok) g_mcvUnknown++;
 Print("TESTER_MC_PRIVACY_SELFTEST ",ok?"PASS":"FAIL");return ok;
}

void MCVExport()
{
 if(!MQLInfoInteger(MQL_TESTER)) return;
 int h=MCSOpen("_requests");
 if(h!=INVALID_HANDLE)
 {
  if(!FileWrite(h,"symbol","server_s","wall_us","elapsed_us","force","path","cycle_before","cycle_after","input_before","input_after","state_before","state_after","history_before","history_after","input_digest","same_input","same_state","fresh","heavy_start","classification","ready_before","allowed_before","active_before","history_ok_before","history_dirty_before","ready_after","allowed_after","active_after","history_ok_after","history_dirty_after")) g_mcvUnknown++;
  for(int i=0;i<ArraySize(g_mcvRequests);i++)
  {
   MCVRequest r=g_mcvRequests[i];MCVContext b=r.before,a=r.after;
   if(!FileWrite(h,r.symbol,r.server,r.start,r.elapsed,(int)r.force,r.path,b.cycle,a.cycle,b.inputVersion,a.inputVersion,b.stateVersion,a.stateVersion,b.historyVersion,a.historyVersion,a.digest,(int)r.sameInput,(int)r.sameState,(int)r.fresh,(int)r.heavy,r.heavy?"HEAVY_START":(a.cycle!=b.cycle?"IMMEDIATE_REQUEST":"NO_REQUEST"),(int)b.ready,(int)b.allowed,(int)b.active,(int)b.historyOK,(int)b.historyDirty,(int)a.ready,(int)a.allowed,(int)a.active,(int)a.historyOK,(int)a.historyDirty)) g_mcvUnknown++;
  }
  FileFlush(h);FileClose(h);
 }
 h=MCSOpen("_guards");
 if(h!=INVALID_HANDLE)
 {
  if(!FileWrite(h,"opp_id","symbol","bar","reason","first_s","last_s","observations","receipt","legacy","prior_claimant_id","shadow_seen","actual_seen","first_cycle","last_cycle","first_input","last_input","first_state","last_state","first_history","last_history","first_position_kind","last_position_kind","score","sl","spread","last_ready","last_allowed","last_active","last_history_ok","last_history_dirty")) g_mcvUnknown++;
  for(int i=0;i<ArraySize(g_mcvGuards);i++)
  {
   MCVGuardRecord r=g_mcvGuards[i];MCVContext a=r.firstContext,b=r.lastContext;
   if(!FileWrite(h,r.id,r.symbol,r.bar,r.reason,r.first,r.last,r.count,(int)(r.reason=="RECEIPT"),(int)(r.reason=="LEGACY"),r.prior,(int)r.shadow,(int)r.actual,a.cycle,b.cycle,a.inputVersion,b.inputVersion,a.stateVersion,b.stateVersion,a.historyVersion,b.historyVersion,a.positionKind,b.positionKind,"UNKNOWN","UNKNOWN","UNKNOWN",(int)b.ready,(int)b.allowed,(int)b.active,(int)b.historyOK,(int)b.historyDirty)) g_mcvUnknown++;
  }
  FileFlush(h);FileClose(h);
 }
 h=MCSOpen("_timings");
 if(h!=INVALID_HANDLE)
 {
  if(!FileWrite(h,"event","symbol","opp_id","entry_us","exit_us","elapsed_us","server_start_s","server_end_s","quote_msc","retcode","success","enqueue_latency_us")) g_mcvUnknown++;
  for(int i=0;i<ArraySize(g_mcvTimings);i++)
  {
   MCVTiming t=g_mcvTimings[i];
   if(!FileWrite(h,t.event,t.symbol,t.id,t.start,t.finish,t.finish-t.start,t.serverStart,t.serverEnd,t.quoteMsc,t.retcode,(int)t.success,"UNKNOWN")) g_mcvUnknown++;
  }
  FileFlush(h);FileClose(h);
 }
 h=MCSOpen("_timing_summary");
 if(h!=INVALID_HANDLE)
 {
  if(!FileWrite(h,"event","count","measured_count","total_us","median_us","p90_us","p95_us","p99_us","max_us","first_entry_us","last_exit_us","first_server_s","last_server_s","first_quote_msc","last_quote_msc","known_quotes","unknown_quotes","enqueue_latency_us")) g_mcvUnknown++;
  MCVSummaryWrite(h,"OnTick",g_mcvTickSummary,g_mcsTickUs);
  MCVSummaryWrite(h,"ManagePositions",g_mcvManageSummary,g_mcvManageUs);
  MCVSummaryWrite(h,"MC_NO_REQUEST",g_mcvNoRequestSummary,g_mcvNoRequestUs);
  FileFlush(h);FileClose(h);
 }
 Print(StringFormat("TESTER_MC_VALIDATION %s requests=%d no_requests=%I64u guards=%d order_timings=%d unknown=%I64u prior_unknown=%I64u",g_mcvUnknown==0 && g_mcsUnknown==0?"PASS":"FAIL",ArraySize(g_mcvRequests),g_mcvNoRequestSummary.count,ArraySize(g_mcvGuards),ArraySize(g_mcvTimings),g_mcvUnknown,g_mcvPriorUnknown));
}

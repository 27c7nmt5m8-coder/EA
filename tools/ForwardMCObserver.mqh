// Demo candidate observer. No orders, history queries, RNG or product state writes.
#ifndef MT3_FORWARD_MC_OBSERVER
#define MT3_FORWARD_MC_OBSERVER
const int FO_LIMIT=65536;
union FOBits {double d;ulong u;};
ulong FOBitPattern(const double v) {FOBits b;b.d=v;return b.u;}
struct FORow {ulong seq,start,end,count,max,total,cycle,active;long server,utc,reason;string event,symbol;bool ready,allowed;double risk;uint rng;};
FORow g_foRows[];
struct FOState {ulong cycle,counts[5],total[5],max[5],hist[5][12],inputVersion,historyRefresh,cycleCallbacks,cycleUs,cycleMax,cycleOps,candidate,positionLast;double inputs[];bool active;long bar,waitBar,candidateBar;};
FOState g_foState[4];
ulong g_foSeq=0,g_foLastFlush=0,g_foUnknown=0,g_foTimer=0,g_foTicks=0;
long g_foIdentity=0;string g_foServer="",g_foPath="";bool g_foBound=false,g_foWarned=false,g_foFileFailed=false;
bool FOGuardIdentity(int mode,long identity,string server,long expected,string expectedServer)
{return mode==ACCOUNT_TRADE_MODE_DEMO && identity>0 && expected>0 && identity==expected && server!="" && server==expectedServer;}
bool FOAllowed()
{return g_foBound && FOGuardIdentity((int)AccountInfoInteger(ACCOUNT_TRADE_MODE),AccountInfoInteger(ACCOUNT_LOGIN),AccountInfoString(ACCOUNT_SERVER),g_foIdentity,g_foServer);}
int FOIndex(const string symbol)
{if(symbol=="USDJPY") return 0;if(symbol=="EURUSD") return 1;if(symbol=="EURJPY") return 2;if(symbol=="XAUUSD") return 3;return -1;}
string FOSymbol(const int i)
{if(i==0) return "USDJPY";if(i==1) return "EURUSD";if(i==2) return "EURJPY";if(i==3) return "XAUUSD";return "UNKNOWN";}
ulong FOActive() {ulong n=0;for(int i=0;i<4;i++) if(g_foState[i].active) n++;return n;}
void FOUnknown()
{g_foUnknown++;if(!g_foWarned) {Print("FORWARD_OBSERVER_WARNING UNKNOWN; stop-review required; product decisions unchanged");g_foWarned=true;}}
void FORecord(const string event,const string symbol,const ulong cycle,const ulong start,const ulong end,const ulong count=0,const ulong maximum=0,const long reason=0,const bool ready=false,const bool allowed=false,const double risk=0,const uint rng=0,const ulong total=0)
{
 int n=ArraySize(g_foRows);if(n>=FO_LIMIT || end<start || ArrayResize(g_foRows,n+1,256)!=n+1) {FOUnknown();return;}
 FORow r;r.seq=++g_foSeq;r.event=event;r.symbol=symbol;r.cycle=cycle;r.start=start;r.end=end;r.count=count;r.max=maximum;
 r.total=total;r.reason=reason;r.ready=ready;r.allowed=allowed;r.risk=risk;r.rng=rng;r.active=FOActive();r.server=(long)TimeCurrent();r.utc=(long)TimeGMT();g_foRows[n]=r;
}
ulong FOUpper(const int b)
{ulong bins[]={100,250,500,1000,2000,5000,10000,20000,50000,100000,500000,0};return bins[b];}
void FODuration(const string symbol,const int metric,const ulong start,const ulong end)
{
 int i=FOIndex(symbol);if(i<0 || metric<0 || metric>=5 || end<start) {FOUnknown();return;}
 ulong d=end-start;g_foState[i].counts[metric]++;g_foState[i].total[metric]+=d;
 if(d>g_foState[i].max[metric]) g_foState[i].max[metric]=d;
 int bucket=0;while(bucket<11 && d>FOUpper(bucket)) bucket++;g_foState[i].hist[metric][bucket]++;
 if(metric==0) {g_foState[i].cycleCallbacks++;g_foState[i].cycleUs+=d;if(d>g_foState[i].cycleMax) g_foState[i].cycleMax=d;}
 if(metric==1 && (g_foState[i].positionLast==0 || end-g_foState[i].positionLast>=60000000 || d>=25000))
 {FORecord("POSITION_SAMPLE",symbol,g_foState[i].cycle,start,end,1,d);g_foState[i].positionLast=end;}
 // 25ms is a retention trigger only, never an acceptance/trading threshold.
 if(d>=25000) FORecord("DURATION_OUTLIER",symbol,g_foState[i].cycle,start,end,1,d,metric);
}
void FORequest(const string symbol,const bool force,const bool active,const int samples,const bool ready,const bool allowed)
{
 int i=FOIndex(symbol);if(i<0) {FOUnknown();return;}
 g_foState[i].cycle++;
 ulong now=GetMicrosecondCount();FORecord("MC_REQUEST",symbol,g_foState[i].cycle,now,now,(ulong)samples,0,(long)force,ready,allowed);
}
void FOForce(const string symbol,const bool active)
{
 int i=FOIndex(symbol);if(i<0) {FOUnknown();return;}
 ulong forceNow=GetMicrosecondCount();FORecord("MC_FORCE_REQUEST",symbol,g_foState[i].cycle,forceNow,forceNow,0,0,(long)active);
 if(active && g_foState[i].active) {ulong now=GetMicrosecondCount();FORecord("MC_CANCEL_FORCE",symbol,g_foState[i].cycle,now,now,g_foState[i].cycleCallbacks,g_foState[i].cycleMax,0,false,false,0,0,g_foState[i].cycleUs);g_foState[i].active=false;}
}
void FOImmediate(const string symbol,const int reason,const double risk,const bool allowed)
{int i=FOIndex(symbol);if(i<0) {FOUnknown();return;}ulong now=GetMicrosecondCount();FORecord("MC_IMMEDIATE_DECISION",symbol,g_foState[i].cycle,now,now,0,0,reason,true,allowed,risk);}
void FOHistory(const string symbol,const int samples,const double winrate)
{int i=FOIndex(symbol);if(i<0) {FOUnknown();return;}g_foState[i].historyRefresh++;ulong now=GetMicrosecondCount();FORecord("HISTORY_REFRESH",symbol,g_foState[i].cycle,now,now,(ulong)samples,0,(long)g_foState[i].historyRefresh,false,false,winrate);}
void FOPriorResult(const string symbol,const long last,const int expiryMinutes)
{int i=FOIndex(symbol);if(i<0) {FOUnknown();return;}ulong now=GetMicrosecondCount();FORecord("MC_PRIOR_RESULT",symbol,g_foState[i].cycle,now,now,(ulong)last,0,expiryMinutes);}
void FOFailure(const string symbol)
{int i=FOIndex(symbol);if(i<0) {FOUnknown();return;}ulong now=GetMicrosecondCount();FORecord("MC_PREPARATION_FAILED",symbol,g_foState[i].cycle,now,now);FOUnknown();}
void FOStart(const string symbol,const int samples,const double &returns[])
{
 int i=FOIndex(symbol);if(i<0) {FOUnknown();return;}
 if(g_foState[i].active) FOUnknown();
 g_foState[i].active=true;g_foState[i].cycleCallbacks=0;g_foState[i].cycleUs=0;g_foState[i].cycleMax=0;g_foState[i].cycleOps=0;ulong now=GetMicrosecondCount();
 FORecord("MC_START",symbol,g_foState[i].cycle,now,now,(ulong)samples);
 bool changed=ArraySize(g_foState[i].inputs)!=ArraySize(returns);
 if(!changed) for(int j=0;j<ArraySize(returns);j++) if(FOBitPattern(g_foState[i].inputs[j])!=FOBitPattern(returns[j])) {changed=true;break;}
 if(changed)
 {
  g_foState[i].inputVersion++;
  if(ArrayCopy(g_foState[i].inputs,returns)!=ArraySize(returns)) {FOUnknown();return;}
  for(int j=0;j<ArraySize(returns);j++) FORecord("MC_INPUT",symbol,g_foState[i].cycle,now,now,(ulong)j,0,(long)g_foState[i].inputVersion,false,false,returns[j]);
 }
 FORecord("MC_INPUT_VERSION",symbol,g_foState[i].cycle,now,now,g_foState[i].inputVersion);
}
void FOLevel(const string symbol,const int candidate,const double dd,const uint rng)
{int i=FOIndex(symbol);if(i<0) {FOUnknown();return;}ulong now=GetMicrosecondCount();FORecord("MC_DD95",symbol,g_foState[i].cycle,now,now,0,0,candidate,false,false,dd,rng);}
void FOComplete(const string symbol,const bool ready,const bool allowed,const double risk,const uint rng)
{
 int i=FOIndex(symbol);if(i<0 || !g_foState[i].active) {FOUnknown();return;}
 ulong now=GetMicrosecondCount();FORecord("MC_COMPLETE",symbol,g_foState[i].cycle,now,now,0,0,0,ready,allowed,risk,rng);g_foState[i].active=false;
}
void FOOperations(const string symbol,const int operations)
{int i=FOIndex(symbol);if(i<0 || operations<0) {FOUnknown();return;}g_foState[i].cycleOps+=(ulong)operations;}
void FOCycleSummary(const string symbol)
{int i=FOIndex(symbol);if(i<0) {FOUnknown();return;}ulong now=GetMicrosecondCount();FORecord("MC_CYCLE_CALLBACKS",symbol,g_foState[i].cycle,now,now,g_foState[i].cycleCallbacks,g_foState[i].cycleMax,0,false,false,0,0,g_foState[i].cycleUs);FORecord("MC_CYCLE_OPERATIONS",symbol,g_foState[i].cycle,now,now,g_foState[i].cycleOps);}
void FOMCWait(const string symbol,const long bar,const bool ready,const bool allowed,const bool active)
{
 int i=FOIndex(symbol);if(i<0 || bar<=0) return;
 if(active && g_foState[i].waitBar!=bar)
 {
  ulong now=GetMicrosecondCount();
  if(g_foState[i].waitBar>0 && bar>g_foState[i].waitBar) FORecord("MC_WAIT_WINDOW_END",symbol,g_foState[i].cycle,now,now,0,0,1);
  g_foState[i].waitBar=bar;FORecord("MC_PREFLIGHT_WAIT_BAR",symbol,g_foState[i].cycle,now,now,0,0,0,ready,allowed);
 }
}
void FOBar(const string symbol,const long bar)
{
 int i=FOIndex(symbol);if(i<0 || bar<=0 || bar==g_foState[i].bar) return;
 ulong now=GetMicrosecondCount();
 if(g_foState[i].waitBar>0 && bar>g_foState[i].waitBar)
 {FORecord("MC_WAIT_WINDOW_END",symbol,g_foState[i].cycle,now,now,0,0,(long)g_foState[i].active);g_foState[i].waitBar=0;}
 g_foState[i].bar=bar;FORecord("BAR",symbol,g_foState[i].cycle,now,now,(ulong)bar);
}
void FOCandidate(const string symbol,const long bar,const ulong identity)
{int i=FOIndex(symbol);if(i<0) {FOUnknown();return;}if(g_foState[i].candidate==identity && g_foState[i].candidateBar==bar) return;g_foState[i].candidate=identity;g_foState[i].candidateBar=bar;ulong now=GetMicrosecondCount();FORecord("CANDIDATE",symbol,g_foState[i].cycle,now,now,identity,0,bar);}
void FOOrder(const string symbol,const ulong start,const ulong end,const uint code,const bool success)
{int i=FOIndex(symbol);if(i<0) {FOUnknown();return;}FORecord("ORDER_RESULT",symbol,g_foState[i].cycle,start,end,1,end-start,(long)code,false,success);}
void FOPositionOrder(const string symbol,const ulong start,const ulong end,const uint code,const bool success,const int kind)
{int i=FOIndex(symbol);if(i<0) {FOUnknown();return;}FORecord(kind==1?"POSITION_CLOSE_RESULT":"POSITION_MODIFY_RESULT",symbol,g_foState[i].cycle,start,end,1,end-start,(long)code,false,success);}
void FOTrade(const MqlTradeTransaction &trans,const MqlTradeRequest &request,const MqlTradeResult &result)
{
 string symbol=trans.symbol!=""?trans.symbol:request.symbol;
 if(FOIndex(symbol)<0) return;ulong now=GetMicrosecondCount();
 FORecord("TRADE_TRANSACTION",symbol,0,now,now,1,0,(long)trans.type);
 if(trans.type==TRADE_TRANSACTION_DEAL_ADD)
 {
  FORecord("DEAL_PRICE",symbol,0,now,now,1,0,(long)trans.deal_type,false,false,trans.price);
  FORecord("DEAL_VOLUME",symbol,0,now,now,1,0,(long)trans.deal_type,false,false,trans.volume);
 }
 // Request/result identity, raw order/deal tickets and comments never export.
 if(trans.type==TRADE_TRANSACTION_REQUEST) FORecord("TRADE_REQUEST_RESULT",symbol,0,now,now,1,0,(long)result.retcode);
}
bool FOInit()
{
 // A fresh program load is required. Do not silently rebind account or reuse a run.
 if(g_foBound) {FOUnknown();return false;}
 if(MQLInfoInteger(MQL_TESTER) || !TerminalInfoInteger(TERMINAL_CONNECTED) || ExecutionMode!=EXECUTION_AUTO || EnableOpenAI || ScanMode!=CUSTOM_LIST || CustomSymbols!="USDJPY,EURUSD,EURJPY,XAUUSD" || _Symbol!="USDJPY" || _Period!=PERIOD_M1) return false;
 g_foIdentity=AccountInfoInteger(ACCOUNT_LOGIN);g_foServer=AccountInfoString(ACCOUNT_SERVER);
 if(!FOGuardIdentity((int)AccountInfoInteger(ACCOUNT_TRADE_MODE),g_foIdentity,g_foServer,g_foIdentity,g_foServer)) {g_foIdentity=0;g_foServer="";return false;}
 g_foBound=true;g_foPath="ForwardMC500k_"+IntegerToString((long)TimeGMT())+"_"+IntegerToString((long)ChartID())+".csv";
 return true;
}
void FOFlush(const bool force=false)
{
 ulong now=GetMicrosecondCount();if(!g_foBound || g_foFileFailed || (!force && g_foLastFlush>0 && now-g_foLastFlush<60000000)) return;
 int h=FileOpen(g_foPath,FILE_READ|FILE_WRITE|FILE_CSV|FILE_ANSI,',');if(h==INVALID_HANDLE) {g_foFileFailed=true;FOUnknown();return;}
 if(FileSize(h)==0 && !FileWrite(h,"seq","event","symbol","cycle","start_wall_us","end_wall_us","server_s","utc_s","count","max_us","total_us","reason","ready","allowed_or_success","value_bits","rng","active_symbols","arrival_us","queue_depth","observer_unknown")) {FileClose(h);g_foFileFailed=true;FOUnknown();return;}
 if(!FileSeek(h,0,SEEK_END)) {FileClose(h);g_foFileFailed=true;FOUnknown();return;}bool ok=true;
 for(int i=0;i<4;i++) for(int m=0;m<5;m++) if(g_foState[i].counts[m]>0)
 {
  FORecord("DURATION_TOTAL",FOSymbol(i),g_foState[i].cycle,now,now,g_foState[i].counts[m],g_foState[i].max[m],m,false,false,0,0,g_foState[i].total[m]);
  for(int b=0;b<12;b++) if(g_foState[i].hist[m][b]>0) FORecord("DURATION_HIST",FOSymbol(i),g_foState[i].cycle,now,now,g_foState[i].hist[m][b],FOUpper(b),m);
 }
 FORecord("PROGRESSION",_Symbol,0,now,now,g_foTicks,g_foTimer);
 for(int n=0;n<ArraySize(g_foRows);n++)
 {
  FORow r=g_foRows[n];
  if(!FileWrite(h,r.seq,r.event,r.symbol,r.cycle,r.start,r.end,r.server,r.utc,r.count,r.max,r.total,r.reason,r.ready,r.allowed,StringFormat("%I64X",FOBitPattern(r.risk)),r.rng,r.active,"UNKNOWN","UNKNOWN",g_foUnknown)) {ok=false;break;}
 }
 ResetLastError();FileFlush(h);int flushError=GetLastError();FileClose(h);if(!ok || flushError!=0) {g_foFileFailed=true;FOUnknown();return;}
 ArrayResize(g_foRows,0);g_foLastFlush=now;
 FODuration(_Symbol,2,now,GetMicrosecondCount());
}
#endif

// Generated Tester copies only: bounded RAM spans, exported once at OnTester.
struct SCSpan
{
 int parent,timer,timeframe,detail,result;long server;
 string symbol,context,section;ulong start,end;
};
const int SC_LIMIT=32768;
SCSpan g_scSpans[32768];
int g_scCount=0,g_scTop=-1,g_scTimer=-1,g_scUnknown=0;
bool g_scActive=false;
int SCEnter(const string symbol,const string section,const bool observer,const int timeframe=0)
{
 if(!g_scActive) return -1;
 if(g_scCount>=SC_LIMIT) {g_scUnknown++;return -1;}
 int i=g_scCount++;SCSpan s;ZeroMemory(s);s.parent=g_scTop;s.timer=g_scTimer;
 s.symbol=symbol;s.context=observer?"OBSERVER":"ACTUAL";s.section=section;
 s.timeframe=timeframe;s.server=(long)TimeCurrent();s.start=GetMicrosecondCount();
 g_scSpans[i]=s;g_scTop=i;return i;
}
void SCLeave(const int index,const int detail=0,const int result=0)
{
 if(index<0) return;
 ulong now=GetMicrosecondCount();
 if(index!=g_scTop || now<g_scSpans[index].start) {g_scUnknown++;return;}
 g_scSpans[index].end=now;g_scSpans[index].detail=detail;g_scSpans[index].result=result;
 g_scTop=g_scSpans[index].parent;
}
void SCBegin(const ulong timer,const ulong start)
{
 if(!MQLInfoInteger(MQL_TESTER) || timer>100) return;
 if(g_scActive || g_scTop!=-1) {g_scUnknown++;return;}
 g_scActive=true;g_scTimer=(int)timer;
 int i=SCEnter("ALL",timer==0?"initialization":"timer",false);
 if(i>=0) g_scSpans[i].start=start;
}
void SCFinish(const ulong end)
{
 if(!g_scActive) return;
 if(g_scTop<0 || g_scSpans[g_scTop].parent!=-1) {g_scUnknown++;g_scActive=false;return;}
 int i=g_scTop;SCLeave(i);g_scSpans[i].end=end;g_scActive=false;
}
int SCBars(const string symbol,const ENUM_TIMEFRAMES tf)
{int i=SCEnter(symbol,"series_bars",g_tpShadow,(int)tf);int v=Bars(symbol,tf);SCLeave(i,0,v);return v;}
datetime SCTime(const string symbol,const ENUM_TIMEFRAMES tf,const int shift)
{
 // Target the four cold scans only: leave steady-state iTime untouched.
 if(!g_scActive || g_scTimer<1 || g_scTimer>4) return iTime(symbol,tf,shift);
 int i=SCEnter(symbol,"series_time",g_tpShadow,(int)tf);
 datetime value=iTime(symbol,tf,shift);SCLeave(i,shift,value>0?1:0);return value;
}
double SCClose(const string symbol,const ENUM_TIMEFRAMES tf,const int shift)
{int i=SCEnter(symbol,"series_close",g_tpShadow,(int)tf);double v=iClose(symbol,tf,shift);SCLeave(i,shift,v>0?1:0);return v;}
int SCATR(const string symbol,const ENUM_TIMEFRAMES tf,const int period)
{int i=SCEnter(symbol,"create_atr",g_tpShadow,(int)tf);int h=iATR(symbol,tf,period);SCLeave(i,period,h!=INVALID_HANDLE?1:0);return h;}
int SCMA(const string symbol,const ENUM_TIMEFRAMES tf,const int period)
{int i=SCEnter(symbol,"create_ema",g_tpShadow,(int)tf);int h=iMA(symbol,tf,period,0,MODE_EMA,PRICE_CLOSE);SCLeave(i,period,h!=INVALID_HANDLE?1:0);return h;}
int SCADX(const string symbol,const ENUM_TIMEFRAMES tf,const int period)
{int i=SCEnter(symbol,"create_adx",g_tpShadow,(int)tf);int h=iADX(symbol,tf,period);SCLeave(i,period,h!=INVALID_HANDLE?1:0);return h;}
int SCMACD(const string symbol,const ENUM_TIMEFRAMES tf,const int fast,const int slow,const int signal)
{int i=SCEnter(symbol,"create_macd",g_tpShadow,(int)tf);int h=iMACD(symbol,tf,fast,slow,signal,PRICE_CLOSE);SCLeave(i,signal,h!=INVALID_HANDLE?1:0);return h;}
void SCExport()
{
 if(!MQLInfoInteger(MQL_TESTER)) return;
 if(g_scActive || g_scTop!=-1) g_scUnknown++;
 int h=MCSOpen("_startup_scan");if(h==INVALID_HANDLE) {g_mcsUnknown++;return;}
 if(!FileWrite(h,"span_id","parent_id","timer_id","server_s","symbol","context","section","start_wall_us","end_wall_us","duration_us","timeframe","detail","result")) g_mcsUnknown++;
 for(int i=0;i<g_scCount;i++)
 {
  SCSpan r=g_scSpans[i];if(r.end<r.start) {g_scUnknown++;continue;}
  if(!FileWrite(h,i+1,r.parent+1,r.timer,r.server,r.symbol,r.context,r.section,r.start,r.end,r.end-r.start,r.timeframe,r.detail,r.result)) g_mcsUnknown++;
 }
 FileFlush(h);FileClose(h);
 // Existing chronological Timer measurements: partition/sort copies only at exit.
 // First four scans define STARTUP in this frozen four-symbol experiment;
 // 5..100 is the existing probe WARMUP window, not a trading threshold.
 h=MCSOpen("_startup_population");if(h==INVALID_HANDLE) {g_mcsUnknown++;return;}
 if(!FileWrite(h,"phase","count","total_us","median_us","p95_us","p99_us","max_us")) g_mcsUnknown++;
 int count=ArraySize(g_mcsTimerUs);
 for(int phase=0;phase<3;phase++)
 {
  int from=phase==0?0:(phase==1?4:100),to=phase==0?MathMin(count,4):(phase==1?MathMin(count,100):count);
  int n=MathMax(0,to-from);ulong values[];
  if(ArrayResize(values,n)!=n || (n>0 && ArrayCopy(values,g_mcsTimerUs,0,from,n)!=n)) {g_scUnknown++;continue;}
  ArraySort(values);
  if(!FileWrite(h,phase==0?"STARTUP":(phase==1?"WARMUP":"STEADY_STATE"),n,MCSSum(values),MCSQuantile(values,.5),MCSQuantile(values,.95),MCSQuantile(values,.99),MCSQuantile(values,1))) g_mcsUnknown++;
 }
 FileFlush(h);FileClose(h);
 if(g_scUnknown>0) g_mcsUnknown+=g_scUnknown;
}

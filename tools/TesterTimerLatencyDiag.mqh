// Tester-only observation. Fixed storage, no files/prints in event handlers.
// Top-256 records are censored; totals/maxima cover ALL callbacks.
struct TLFrame
{
 ulong timer,start,finish,total,phase[8],scan[4],detail[24],copyOK[8],copyFail[8];
 int copyError[8];long server;uint seen;bool probed;
};
TLFrame g_tlFrame,g_tlTop[256];
string g_tlSymbols[4];
ulong g_tlCount=0,g_tlTotal=0,g_tlMax=0,g_tlPhaseTotal[8],g_tlPhaseMax[8];
ulong g_tlLast=0,g_tlBookkeepingMax=0,g_tlMinTotal=0,g_tlUnknown=0;
int g_tlRecorded=0,g_tlMinIndex=0,g_tlNext=0,g_tlScanIndex=-1;
bool g_tlActive=false;

void TLBegin(const ulong started)
{
 if(!MQLInfoInteger(MQL_TESTER)) return;
 if(g_tlActive) g_tlUnknown++;
 ZeroMemory(g_tlFrame);g_tlFrame.timer=g_tpmcTimer;g_tlFrame.start=started;
 g_tlFrame.server=(long)TimeCurrent();g_tlFrame.probed=TL_NESTED==1 && g_tlFrame.timer<=100;
 g_tlLast=started;g_tlNext=0;g_tlScanIndex=-1;g_tlActive=true;
}
void TLStartScan(const int index) {g_tlScanIndex=index;}
ulong TLProbeClock()
{if(!g_tlActive || !g_tlFrame.probed || g_tlScanIndex<0 || g_tlScanIndex>=4) return 0;return GetMicrosecondCount();}
void TLPart(const int stage,const ulong started)
{
 if(started==0) return;
 ulong now=GetMicrosecondCount();
 if(g_tlScanIndex<0 || g_tlScanIndex>=4 || stage<0 || stage>=4 || now<started) {g_tlUnknown++;return;}
 g_tlFrame.detail[g_tlScanIndex*6+stage]+=now-started;
}
void TLReadCopy(const bool observer,const int copied,const int error,const ulong duration)
{
 if(g_tlScanIndex<0 || g_tlScanIndex>=4 || !g_tlFrame.probed) {g_tlUnknown++;return;}
 int side=observer?1:0,index=g_tlScanIndex*2+side;
 g_tlFrame.detail[g_tlScanIndex*6+4+side]+=duration;
 if(copied==1) g_tlFrame.copyOK[index]++;else g_tlFrame.copyFail[index]++;
 g_tlFrame.copyError[index]=error;
}
void TLMark(const int stage)
{
 if(!g_tlActive) return;
 ulong now=GetMicrosecondCount();
 if(stage!=g_tlNext || stage<0 || stage>=8 || now<g_tlLast) {g_tlUnknown++;return;}
 g_tlFrame.phase[stage]=now-g_tlLast;g_tlLast=now;g_tlNext++;
}
void TLScan(const int index,const string symbol,const ulong started)
{
 if(!g_tlActive) return;
 ulong now=GetMicrosecondCount();
 if(index<0 || index>=4 || now<started || StringLen(symbol)==0) {g_tlUnknown++;return;}
 if(StringLen(g_tlSymbols[index])>0 && g_tlSymbols[index]!=symbol) {g_tlUnknown++;return;}
 if(StringLen(g_tlSymbols[index])==0) g_tlSymbols[index]=symbol;
 g_tlFrame.scan[index]+=now-started;g_tlFrame.seen|=(uint)(1<<index);g_tlScanIndex=-1;
}
void TLFinish(const ulong finished)
{
 if(!g_tlActive) return;
 ulong bookkeeping=GetMicrosecondCount();g_tlActive=false;
 if(g_tlNext!=8 || finished<g_tlLast) {g_tlUnknown++;return;}
 g_tlFrame.finish=finished;g_tlFrame.total=finished-g_tlFrame.start;
 g_tlCount++;g_tlTotal+=g_tlFrame.total;
 if(g_tlFrame.total>g_tlMax) g_tlMax=g_tlFrame.total;
 for(int i=0;i<8;i++)
 {g_tlPhaseTotal[i]+=g_tlFrame.phase[i];if(g_tlFrame.phase[i]>g_tlPhaseMax[i]) g_tlPhaseMax[i]=g_tlFrame.phase[i];}
 if(g_tlRecorded<256)
 {
  int i=g_tlRecorded;g_tlTop[i]=g_tlFrame;g_tlRecorded++;
  if(i==0 || g_tlFrame.total<g_tlMinTotal) {g_tlMinTotal=g_tlFrame.total;g_tlMinIndex=i;}
 }
 else if(g_tlFrame.total>g_tlMinTotal)
 {
  g_tlTop[g_tlMinIndex]=g_tlFrame;g_tlMinTotal=g_tlTop[0].total;g_tlMinIndex=0;
  for(int i=1;i<256;i++) if(g_tlTop[i].total<g_tlMinTotal) {g_tlMinTotal=g_tlTop[i].total;g_tlMinIndex=i;}
 }
 ulong cost=GetMicrosecondCount()-bookkeeping;if(cost>g_tlBookkeepingMax) g_tlBookkeepingMax=cost;
}
string TLStage(const int i)
{
 switch(i)
 {case 0:return "maintain";case 1:return "universe";case 2:return "scan";case 3:return "mc";
  case 4:return "shadow";case 5:return "dispatch";case 6:return "journal";case 7:return "dashboard";}
 return "UNKNOWN";
}
string TLDetail(const int i)
{switch(i) {case 0:return "scan_maintain";case 1:return "scan_lines";case 2:return "scan_bar";
 case 3:return "scan_candidate";case 4:return "indicator_actual";case 5:return "indicator_observer";}return "UNKNOWN";}
void TLExport()
{
 if(!MQLInfoInteger(MQL_TESTER)) return;
 int h=MCSOpen("_timer_sections");if(h==INVALID_HANDLE) return;
 if(!FileWrite(h,"timer_id","server_s","start_wall_us","end_wall_us","stage","symbol","duration_us","total_us")) g_mcsUnknown++;
 for(int i=0;i<g_tlRecorded;i++)
 {
  TLFrame r=g_tlTop[i];
  for(int j=0;j<8;j++) if(!FileWrite(h,r.timer,r.server,r.start,r.finish,TLStage(j),"ALL",r.phase[j],r.total)) g_mcsUnknown++;
  for(int j=0;j<4;j++)
  {
   if((r.seen & (uint)(1<<j))==0) continue;
   if(!FileWrite(h,r.timer,r.server,r.start,r.finish,"symbol_scan",g_tlSymbols[j],r.scan[j],r.total)) g_mcsUnknown++;
   if(!r.probed) continue;
   for(int k=0;k<6;k++) if(!FileWrite(h,r.timer,r.server,r.start,r.finish,TLDetail(k),g_tlSymbols[j],r.detail[j*6+k],r.total)) g_mcsUnknown++;
  }
 }
 FileFlush(h);FileClose(h);
 h=MCSOpen("_timer_copies");if(h==INVALID_HANDLE) return;
 if(!FileWrite(h,"timer_id","server_s","symbol","context","calls","successful","failed","last_error","elapsed_us")) g_mcsUnknown++;
 for(int i=0;i<g_tlRecorded;i++)
 {
  TLFrame r=g_tlTop[i];if(!r.probed) continue;
  for(int j=0;j<4;j++)
  {
   if((r.seen & (uint)(1<<j))==0) continue;
   for(int k=0;k<2;k++)
   {
    int at=j*2+k;ulong calls=r.copyOK[at]+r.copyFail[at];if(calls==0) continue;
    if(!FileWrite(h,r.timer,r.server,g_tlSymbols[j],k==0?"ACTUAL":"OBSERVER",calls,r.copyOK[at],r.copyFail[at],r.copyError[at],r.detail[j*6+4+k])) g_mcsUnknown++;
   }
  }
 }
 FileFlush(h);FileClose(h);
 h=MCSOpen("_timer_summary");if(h==INVALID_HANDLE) return;
 if(!FileWrite(h,"stage","count","total_us","max_us","recorded","unknown","bookkeeping_max_us")) g_mcsUnknown++;
 if(!FileWrite(h,"OnTimer",g_tlCount,g_tlTotal,g_tlMax,g_tlRecorded,g_tlUnknown,g_tlBookkeepingMax)) g_mcsUnknown++;
 for(int i=0;i<8;i++) if(!FileWrite(h,TLStage(i),g_tlCount,g_tlPhaseTotal[i],g_tlPhaseMax[i],g_tlRecorded,g_tlUnknown,g_tlBookkeepingMax)) g_mcsUnknown++;
 FileFlush(h);FileClose(h);
 if(g_tlUnknown>0) g_mcsUnknown+=(int)g_tlUnknown;
}

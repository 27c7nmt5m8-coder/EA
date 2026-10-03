// Tester-only Journal observation. Fixed storage lives in TLFrame.
int g_tjIndex=-1;
string g_tjSymbols[4];
ulong TJEnter(const int index,const string symbol)
{
 if(!g_tlActive || g_tlNext!=6) return 0;
 ulong started=GetMicrosecondCount();
 if(index<0 || index>=4 || StringLen(symbol)==0 || g_tjIndex!=-1) {g_tlUnknown++;return 0;}
 if((g_tlFrame.jseen & (uint)(1<<index))!=0) {g_tlUnknown++;return 0;}
 if(StringLen(g_tjSymbols[index])>0 && g_tjSymbols[index]!=symbol) {g_tlUnknown++;return 0;}
 if(StringLen(g_tjSymbols[index])==0) g_tjSymbols[index]=symbol;
 g_tjIndex=index;g_tlFrame.jseen|=(uint)(1<<index);return started;
}
ulong TJClock()
{if(!g_tlActive || g_tjIndex<0 || g_tjIndex>=4) return 0;return GetMicrosecondCount();}
void TJPart(const int phase,const ulong started)
{
 if(started==0) return;
 ulong now=GetMicrosecondCount();
 if(g_tjIndex<0 || g_tjIndex>=4 || phase<0 || phase>=8 || now<started) {g_tlUnknown++;return;}
 int at=g_tjIndex*8+phase;g_tlFrame.jdetail[at]+=now-started;g_tlFrame.jcalls[at]++;
}
void TJLeave(const ulong started)
{
 if(started==0) return;
 ulong now=GetMicrosecondCount();
 if(g_tjIndex<0 || g_tjIndex>=4 || now<started) {g_tlUnknown++;g_tjIndex=-1;return;}
 g_tlFrame.journal[g_tjIndex]+=now-started;g_tjIndex=-1;
}
string TJStage(const int i)
{
 switch(i) {case 0:return "sample_guard";case 1:return "history_select";case 2:return "collect_ids";
 case 3:return "queue";case 4:return "persist";case 5:return "cursor";case 6:return "portfolio";case 7:return "cleanup";}
 return "UNKNOWN";
}
void TJExport()
{
 if(!MQLInfoInteger(MQL_TESTER)) return;
 int h=MCSOpen("_journal_sections");if(h==INVALID_HANDLE) return;
 if(!FileWrite(h,"timer_id","server_s","start_wall_us","end_wall_us","stage","symbol","duration_us","total_us","calls")) g_mcsUnknown++;
 for(int i=0;i<g_tlRecorded;i++)
 {
  TLFrame r=g_tlTop[i];int visits=0;
  for(int j=0;j<4;j++) if((r.jseen & (uint)(1<<j))!=0) visits++;
  if(!FileWrite(h,r.timer,r.server,r.start,r.finish,"journal_root","ALL",r.phase[6],r.total,visits)) g_mcsUnknown++;
  for(int j=0;j<4;j++)
  {
   if((r.jseen & (uint)(1<<j))==0) continue;
   if(!FileWrite(h,r.timer,r.server,r.start,r.finish,"symbol_journal",g_tjSymbols[j],r.journal[j],r.total,1)) g_mcsUnknown++;
   for(int k=0;k<8;k++) if(!FileWrite(h,r.timer,r.server,r.start,r.finish,TJStage(k),g_tjSymbols[j],r.jdetail[j*8+k],r.total,r.jcalls[j*8+k])) g_mcsUnknown++;
  }
 }
 FileFlush(h);FileClose(h);
}

// Only JournalPersist uses the observed clone. Original WriteAIFile is unchanged.
ulong TJIClock() {return TJClock();}
void TJIRecord(const int phase,const ulong started)
{
 if(started==0) return;
 ulong now=GetMicrosecondCount();
 if(g_tjIndex<0 || g_tjIndex>=4 || phase<0 || phase>=10 || now<started) {g_tlUnknown++;return;}
 int at=g_tjIndex*10+phase;g_tlFrame.io[at]+=now-started;g_tlFrame.iocalls[at]++;
}
string TJIRecordJSON(TradeLogRecord &r)
{ulong started=TJIClock();string result=TradeRecordJSON(r);TJIRecord(0,started);return result;}
string TJIRecordCSV(TradeLogRecord &r)
{ulong started=TJIClock();string result=TradeRecordCSV(r);TJIRecord(1,started);return result;}
bool TJIFileMove(const string source,const int common,const string target,const int flags)
{ulong started=TJIClock();bool result=FileMove(source,common,target,flags);TJIRecord(7,started);return result;}
bool TJIFileDelete(const string name,const int common)
{ulong started=TJIClock();bool result=FileDelete(name,common);TJIRecord(8,started);return result;}
bool TJIWriteAIFile(string name,const string text)
{ulong started=TJIClock();bool result=TJIWriteCore(name,text);TJIRecord(9,started);return result;}
string TJIStage(const int i)
{
 switch(i) {case 0:return "serialize_json";case 1:return "serialize_csv";case 2:return "convert";
 case 3:return "open";case 4:return "write";case 5:return "flush";case 6:return "close";
 case 7:return "move";case 8:return "delete";case 9:return "write_total";}return "UNKNOWN";
}
void TJIExport()
{
 if(!MQLInfoInteger(MQL_TESTER)) return;
 int h=MCSOpen("_journal_io");if(h==INVALID_HANDLE) return;
 if(!FileWrite(h,"timer_id","server_s","start_wall_us","end_wall_us","stage","symbol","duration_us","total_us","calls")) g_mcsUnknown++;
 for(int i=0;i<g_tlRecorded;i++)
 {
  TLFrame r=g_tlTop[i];
  for(int j=0;j<4;j++)
  {
   if((r.jseen & (uint)(1<<j))==0) continue;
   for(int k=0;k<10;k++) if(!FileWrite(h,r.timer,r.server,r.start,r.finish,TJIStage(k),g_tjSymbols[j],r.io[j*10+k],r.total,r.iocalls[j*10+k])) g_mcsUnknown++;
  }
 }
 FileFlush(h);FileClose(h);
}

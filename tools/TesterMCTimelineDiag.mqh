// Observational data only; no account/ticket/return-sequence export.
struct TPMCEvent
{
 string event,symbol,trigger,inputDigest,oppId,eligibleId;
 ulong seq,wallUs,timer,dirtyMask,operations,calls,advanceUs,eligibleTimer;
 long server,quoteMsc,lastComplete,lastEligible,bar;
 int cycle,parent,historyVersion,inputVersion,stateVersion,samples,run,trade,candidate,callPath;
 int previousComplete,validCycle,positionKind,positionMask,accepted;
 bool ready,allowed,active,historyOK,historyDirty;
 double winRate,risk,score;
};
TPMCEvent g_tpmcEvents[];
ulong g_tpmcTimer=0,g_tpmcUnknown=0;
int g_tpmcAccepted=0;

bool TPMCAppend(TPMCEvent &e)
{
 int n=ArraySize(g_tpmcEvents);
 if(ArrayResize(g_tpmcEvents,n+1,1024)!=n+1) {g_tpmcUnknown++;return false;}
 e.seq=n+1;g_tpmcEvents[n]=e;return true;
}
bool TPMCSelfTest()
{
 TPMCEvent e;ZeroMemory(e);e.event="SYNTHETIC";e.oppId="SYNTH-ID";e.server=100;e.wallUs=250000;
 bool ok=TPMCAppend(e) && g_tpmcEvents[0].oppId=="SYNTH-ID" && g_tpmcEvents[0].server==100 && g_tpmcEvents[0].wallUs==250000;
 ArrayResize(g_tpmcEvents,0);g_tpmcUnknown=0;
 Print("TESTER_MC_TIMELINE_SELFTEST ",ok?"PASS":"FAIL");return ok;
}
void TPMCExport()
{
 string start=ArraySize(g_tpoDays)>0?TimeToString(g_tpoDays[0].day,TIME_DATE):"none";
 string name="CodexMCTimeline_20260927_"+_Symbol+"_"+start+"_A"+DoubleToString(MaxSpreadATR,2)+"_S"+DoubleToString(MaxSpreadSL,2)+".csv";
 int h=FileOpen(name,FILE_WRITE|FILE_CSV|FILE_ANSI|FILE_COMMON,',');
 if(h==INVALID_HANDLE) {Print("TESTER_MC_TIMELINE_EXPORT FAIL open");return;}
 bool ok=FileWrite(h,"event","seq","symbol","cycle","parent","server_s","quote_msc","wall_us","timer","trigger","dirty_mask","history_version","input_version","input_digest","state_version","samples","win_rate","ready","allowed","active","history_ok","history_dirty","mc_run","mc_trade","mc_candidate","operations","advance_calls","advance_us","previous_complete_cycle","previous_complete_s","valid_cycle","opp_id","bar","score","position_kind","position_mask","accepted_total","eligible_id","eligible_timer","last_eligible_s","risk","call_path")>0;
 for(int i=0;i<ArraySize(g_tpmcEvents);i++)
 {
  TPMCEvent e=g_tpmcEvents[i];
  if(FileWrite(h,e.event,e.seq,e.symbol,e.cycle,e.parent,e.server,e.quoteMsc,e.wallUs,e.timer,e.trigger,e.dirtyMask,e.historyVersion,e.inputVersion,e.inputDigest,e.stateVersion,e.samples,DoubleToString(e.winRate,10),(int)e.ready,(int)e.allowed,(int)e.active,(int)e.historyOK,(int)e.historyDirty,e.run,e.trade,e.candidate,e.operations,e.calls,e.advanceUs,e.previousComplete,e.lastComplete,e.validCycle,e.oppId,e.bar,DoubleToString(e.score,10),e.positionKind,e.positionMask,e.accepted,e.eligibleId,e.eligibleTimer,e.lastEligible,DoubleToString(e.risk,10),e.callPath)==0) ok=false;
 }
 FileFlush(h);FileClose(h);
 Print(StringFormat("TESTER_MC_TIMELINE_EXPORT %s rows=%d unknown=%I64u file=%s",ok && g_tpmcUnknown==0?"OK":"FAIL",ArraySize(g_tpmcEvents),g_tpmcUnknown,name));
}

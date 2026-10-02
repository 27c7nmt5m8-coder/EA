// Generated Tester copy only. Account identifiers, tickets and RNG sequences are not exported.
enum TPBPositionFlag {TPB_SAME_SYMBOL,TPB_SAME_DIRECTION,TPB_OPPOSITE_DIRECTION,TPB_NETTING,TPB_HEDGING,
 TPB_SINGLE_POSITION,TPB_PENDING,TPB_UNRESOLVED,TPB_OWN,TPB_FOREIGN,TPB_POSITION_OTHER};
enum TPBMCReason {TPB_MC_INIT,TPB_MC_CALCULATING,TPB_MC_HISTORY_STATE,TPB_MC_SEQUENCE_UNAVAILABLE,
 TPB_MC_BASELINE_ALLOWED,TPB_MC_BASELINE_DENIED,TPB_MC_WINRATE_DENIED,TPB_MC_BOUNDARY_DENIED,
 TPB_MC_PERMITTED,TPB_MC_OTHER_NOTREADY,TPB_MC_OTHER_DENIED,TPB_MC_BYPASS};
struct TPBRecord
{
 string id;bool buy,scoreSeen,scoreInvalid;
 double scoreFirst,scoreMin,scoreMax;
 ulong positionMask,mcMask,mcBlockMask;
 int lastMCReason,lastPositionMask;
 bool mcReady,mcAllowed,mcActive,historyOK,historyDirty,ddSeen;
 int samples,returnsCount,bootstrapCount,mcRun,mcTrade,mcCandidate;
 double winRate,risk,dd,ddLimit,elapsedMax;
 datetime firstCandidate,lastCandidate;
};
TPBRecord g_tpb[];
bool TPBEnsure(const int i)
{
 if(i<0 || i>=ArraySize(g_tpo)) return false;
 int n=ArraySize(g_tpb);
 if(i>=n)
 {
  if(ArrayResize(g_tpb,i+1,256)!=i+1) {g_tpoUnknown++;return false;}
  for(int j=n;j<=i;j++) ZeroMemory(g_tpb[j]);
 }
 return true;
}
void TPBScore(const int i,const double score)
{
 if(!TPBEnsure(i)) return;
 if(!MathIsValidNumber(score) || score==EMPTY_VALUE) {g_tpb[i].scoreInvalid=true;g_tpoUnknown++;return;}
 if(!g_tpb[i].scoreSeen)
 {g_tpb[i].scoreFirst=score;g_tpb[i].scoreMin=score;g_tpb[i].scoreMax=score;g_tpb[i].scoreSeen=true;}
 else {g_tpb[i].scoreMin=MathMin(g_tpb[i].scoreMin,score);g_tpb[i].scoreMax=MathMax(g_tpb[i].scoreMax,score);}
}
int TPBMCClassify(const bool required,const bool historyOK,const bool dirty,const bool ready,
 const bool allowed,const bool active,const int source,const int sequenceSize)
{
 if(!required) return TPB_MC_BYPASS;
 if(!ready)
 {
  if(!historyOK || dirty) return TPB_MC_HISTORY_STATE;
  if(source==TPB_MC_SEQUENCE_UNAVAILABLE || (active && sequenceSize<=0)) return TPB_MC_SEQUENCE_UNAVAILABLE;
  if(active) return TPB_MC_CALCULATING;
  if(source==TPB_MC_INIT) return TPB_MC_INIT;
  return TPB_MC_OTHER_NOTREADY;
 }
 if(allowed) return source==TPB_MC_BASELINE_ALLOWED?TPB_MC_BASELINE_ALLOWED:TPB_MC_PERMITTED;
 if(source==TPB_MC_BASELINE_DENIED || source==TPB_MC_WINRATE_DENIED || source==TPB_MC_BOUNDARY_DENIED) return source;
 return TPB_MC_OTHER_DENIED;
}
bool TPBSelfTest()
{
 ArrayResize(g_tpo,0);ArrayResize(g_tpb,0);
 int a=TPOFind("SYNTH",60,"A",true);TPBScore(a,64);TPBScore(a,70);TPBScore(a,66);
 Print(StringFormat("TESTER_BOTTLENECK_STRING_CHECK zero_length=%d equals_empty=%d",StringLen(g_tpb[a].id),(int)(g_tpb[a].id=="")));
 bool ok=StringLen(g_tpb[a].id)==0;
 g_tpb[a].id="SYNTH-ID";g_tpb[a].buy=true;
 TPBRecord copy=g_tpb[a];
 ok=ok && copy.id==g_tpb[a].id && copy.buy==g_tpb[a].buy;
 ok=ok && ArraySize(g_tpb)==1 && g_tpb[a].scoreFirst==64 && g_tpb[a].scoreMin==64 && g_tpb[a].scoreMax==70;
 ok=ok && TPBMCClassify(true,true,false,false,false,true,TPB_MC_CALCULATING,30)==TPB_MC_CALCULATING &&
 TPBMCClassify(true,true,false,true,false,false,TPB_MC_BOUNDARY_DENIED,30)==TPB_MC_BOUNDARY_DENIED &&
 TPBMCClassify(true,true,false,true,true,false,TPB_MC_BASELINE_ALLOWED,0)==TPB_MC_BASELINE_ALLOWED &&
 TPBMCClassify(true,false,true,false,false,false,TPB_MC_INIT,0)==TPB_MC_HISTORY_STATE &&
 TPBMCClassify(true,true,false,false,false,false,TPB_MC_INIT,0)==TPB_MC_INIT &&
 TPBMCClassify(true,true,false,false,false,true,TPB_MC_CALCULATING,0)==TPB_MC_SEQUENCE_UNAVAILABLE &&
 TPBMCClassify(true,true,false,true,false,false,TPB_MC_WINRATE_DENIED,30)==TPB_MC_WINRATE_DENIED;
 ArrayResize(g_tpo,0);ArrayResize(g_tpb,0);g_tpoUnknown=0;
 Print("TESTER_BOTTLENECK_SELFTEST ",ok?"PASS":"FAIL");return ok;
}
void TPBPrintSummary()
{
 int missing=0,invalid=0;
 for(int i=0;i<ArraySize(g_tpo);i++)
 {
  if(!TPBEnsure(i)) {missing++;continue;}
  if(StringLen(g_tpb[i].id)==0 || !g_tpb[i].scoreSeen) missing++;
  if(g_tpb[i].scoreInvalid) invalid++;
 }
 Print(StringFormat("TESTER_BOTTLENECK_SUMMARY signals=%d position_pass=%d mc_ready=%d mc_permitted=%d other_safety_pass=%d missing=%d invalid_score=%d unknown=%I64u threshold=%.8f",
  TPOCount(TPO_SIGNAL),TPOCount(TPO_POSITION_PASS),TPOCount(TPO_MC_READY),TPOCount(TPO_MC_PERMITTED),TPOCount(TPO_AFTER_SAFETY),missing,invalid,g_tpoUnknown,MinimumSignalScore));
 if(missing>0 || invalid>0 || ArraySize(g_tpb)!=ArraySize(g_tpo))
 {Print("TESTER_BOTTLENECK_EXPORT FAIL incomplete_records");return;}
 string start=ArraySize(g_tpoDays)>0?TimeToString(g_tpoDays[0].day,TIME_DATE):"none";
 string file="CodexBottleneck_20260927_"+_Symbol+"_"+start+"_A"+DoubleToString(MaxSpreadATR,2)+"_S"+DoubleToString(MaxSpreadSL,2)+".csv";
 int h=FileOpen(file,FILE_WRITE|FILE_CSV|FILE_ANSI|FILE_COMMON,',');
 if(h==INVALID_HANDLE) {Print("TESTER_BOTTLENECK_EXPORT FAIL error=",GetLastError());return;}
 FileWrite(h,"id","symbol","bar","buy","stage_mask","reason_mask","safety_reason","order_reason","terminal_reason",
 "score_seen","score_invalid","score_first","score_min","score_max","threshold","position_mask","last_position_mask",
 "mc_mask","mc_block_mask","last_mc_reason","mc_ready","mc_allowed","mc_active","history_ok","history_dirty",
 "samples","returns_count","bootstrap_count","mc_run","mc_trade","mc_candidate","win_rate","mc_risk","dd_seen","dd","dd_limit","mc_elapsed_max","candidate_first","candidate_last");
 for(int i=0;i<ArraySize(g_tpo);i++)
 {
  TPBRecord r=g_tpb[i];
  FileWrite(h,r.id,g_tpo[i].symbol,(long)g_tpo[i].bar,(int)r.buy,g_tpo[i].stages,g_tpo[i].reasons,g_tpo[i].safetyReason,g_tpo[i].orderReason,TPOTerminalReason(i),
   (int)r.scoreSeen,(int)r.scoreInvalid,DoubleToString(r.scoreFirst,10),DoubleToString(r.scoreMin,10),DoubleToString(r.scoreMax,10),DoubleToString(MinimumSignalScore,10),r.positionMask,r.lastPositionMask,
   r.mcMask,r.mcBlockMask,r.lastMCReason,(int)r.mcReady,(int)r.mcAllowed,(int)r.mcActive,(int)r.historyOK,(int)r.historyDirty,
   r.samples,r.returnsCount,r.bootstrapCount,r.mcRun,r.mcTrade,r.mcCandidate,DoubleToString(r.winRate,10),DoubleToString(r.risk,10),(int)r.ddSeen,DoubleToString(r.dd,10),DoubleToString(r.ddLimit,10),r.elapsedMax,(long)r.firstCandidate,(long)r.lastCandidate);
 }
 FileFlush(h);FileClose(h);
 Print(StringFormat("TESTER_BOTTLENECK_EXPORT OK rows=%d file=%s",ArraySize(g_tpo),file));
}

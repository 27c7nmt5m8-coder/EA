// Tester-only independent shadow contexts. They never enter product SymbolState.
const int MCM_MAX=4;
const int MCM_ARM_LIMIT=600;
string g_mcmSymbols[4];
MCSReplay g_mcmShadow[4];
int g_mcmCount=0,g_mcmCursor=0,g_mcmArmAttempts=0,g_mcmUnknown=0;
bool g_mcmArmed=false,g_mcmArmFailed=false,g_mcmNaturalActive=false;
long g_mcmEpoch=0;
ulong g_mcmOverlapStart=0,g_mcmOverlapEnd=0,g_mcmNaturalOverlapUs=0;
ulong g_mcmQuoteSamples[4],g_mcmQuoteAdvances[4],g_mcmQuoteRegressions[4];
ulong g_mcmBarSamples[4],g_mcmBarAdvances[4];
long g_mcmLastQuoteMsc[4],g_mcmLastBarS[4];

bool MCMNamed(const string symbol)
{return symbol=="USDJPY" || symbol=="EURUSD" || symbol=="EURJPY" || symbol=="XAUUSD";}

void MCMRegisterSymbol(const string symbol)
{
 if(!MQLInfoInteger(MQL_TESTER) || g_mcmArmed || g_mcmArmFailed || !MCMNamed(symbol)) return;
 for(int i=0;i<g_mcmCount;i++) if(g_mcmSymbols[i]==symbol) return;
 if(g_mcmCount>=MCM_MAX) {g_mcmUnknown++;g_mcmArmFailed=true;return;}
 g_mcmSymbols[g_mcmCount++]=symbol;
}

int MCMOverlapActive()
{
 int active=0;
 for(int i=0;i<g_mcmCount;i++) if(g_mcmShadow[i].m_mcActive) active++;
 return active;
}

void MCMSetNaturalActive(const bool active)
{g_mcmNaturalActive=active;}

void MCMArm()
{
 if(!MQLInfoInteger(MQL_TESTER) || g_mcmArmed || g_mcmArmFailed) return;
 if(++g_mcmArmAttempts>MCM_ARM_LIMIT) {g_mcmUnknown++;g_mcmArmFailed=true;return;}
 if(g_mcmCount<2) return;
 for(int i=0;i<g_mcmCount;i++)
 {
  MqlTick quote;
  if(!SymbolInfoTick(g_mcmSymbols[i],quote) || quote.time_msc<=0 || iBars(g_mcmSymbols[i],PERIOD_M1)<=0) return;
 }
 double synthetic[];
 if(ArrayResize(synthetic,30)!=30) {g_mcmUnknown++;g_mcmArmFailed=true;return;}
 for(int j=0;j<30;j++) synthetic[j]=(j%2==0)?1:-1;
 g_mcmEpoch=(long)TimeCurrent();
 for(int i=0;i<g_mcmCount;i++)
 {
  MCSCapture(g_mcmSymbols[i],"SHADOW",1,synthetic,"SYNTH_ALTERNATING_30",1,0);
  int snapshot=MCSFind(g_mcmSymbols[i],"SHADOW",1);
  if(snapshot<0 || !g_mcmShadow[i].Prepare(g_mcsSnapshots[snapshot]))
  {g_mcmUnknown++;g_mcmArmFailed=true;return;}
 }
 g_mcmArmed=true;g_mcmOverlapStart=GetMicrosecondCount();
}

void MCMObserveQuotes()
{
 for(int i=0;i<g_mcmCount;i++)
 {
  MqlTick tick;
  if(SymbolInfoTick(g_mcmSymbols[i],tick) && tick.time_msc>0)
  {
   g_mcmQuoteSamples[i]++;
   if(g_mcmLastQuoteMsc[i]>0 && tick.time_msc>g_mcmLastQuoteMsc[i]) g_mcmQuoteAdvances[i]++;
   if(g_mcmLastQuoteMsc[i]>0 && tick.time_msc<g_mcmLastQuoteMsc[i]) {g_mcmQuoteRegressions[i]++;g_mcmUnknown++;}
   g_mcmLastQuoteMsc[i]=tick.time_msc;
  }
  long bar=(long)iTime(g_mcmSymbols[i],PERIOD_M1,0);
  if(bar>0)
  {
   g_mcmBarSamples[i]++;
   if(g_mcmLastBarS[i]>0 && bar>g_mcmLastBarS[i]) g_mcmBarAdvances[i]++;
   if(g_mcmLastBarS[i]>0 && bar<g_mcmLastBarS[i]) g_mcmUnknown++;
   g_mcmLastBarS[i]=bar;
  }
 }
}

void MCMAdvance(MCSReplay &r,const ulong deadline)
{
 r.lastOperations=0;
 if(MCS_MODE==0) r.Advance0(deadline);
 else r.Advance2(deadline);
}

void MCMService(const ulong deadline)
{
 if(!MQLInfoInteger(MQL_TESTER)) return;
 MCMObserveQuotes();
 if(!g_mcmArmed || g_mcmArmFailed) return;
 ulong started=GetMicrosecondCount();
 int active=MCMOverlapActive();
 bool serviced=false;
 for(int n=0;n<g_mcmCount && GetTickCount64()<deadline;n++)
 {
  int i=g_mcmCursor%g_mcmCount;g_mcmCursor=(g_mcmCursor+1)%g_mcmCount;
  if(!g_mcmShadow[i].m_mcActive) continue;
  ulong before=GetMicrosecondCount();
  MCMAdvance(g_mcmShadow[i],deadline);
  ulong after=GetMicrosecondCount();
  int snapshot=MCSFind(g_mcmSymbols[i],"SHADOW",1);
  if(snapshot<0) {g_mcmUnknown++;return;}
  MCSActualCallback(g_mcmSymbols[i],"SHADOW",1,g_mcmShadow[i].lastOperations,before,after,1,0);
  if(g_mcmShadow[i].lastOperations>0) serviced=true;
  g_mcmShadow[i].totalOperations+=(ulong)g_mcmShadow[i].lastOperations;
  if(!g_mcmShadow[i].m_mcActive)
  {
   g_mcsSnapshots[snapshot].signature=g_mcmShadow[i].signature;
   MCSActualComplete(g_mcmSymbols[i],"SHADOW",1,g_mcmShadow[i].g_mcRisk,g_mcmShadow[i].g_mcAllowed,g_mcmShadow[i].m_mcRandom,g_mcmShadow[i].m_mcCandidate);
   if(g_mcmShadow[i].mcvSequenceErrors!=0 || g_mcmShadow[i].mcvDraws!=g_mcmShadow[i].totalOperations) g_mcmUnknown++;
  }
 }
 if(active>=2 && MCMOverlapActive()<2 && g_mcmOverlapEnd==0) g_mcmOverlapEnd=GetMicrosecondCount();
 if(active>=2 && g_mcmNaturalActive && serviced) g_mcmNaturalOverlapUs+=GetMicrosecondCount()-started;
}

string MCMValidationStatus()
{
 if(g_mcmUnknown>0 || g_mcsUnknown>0 || g_mcsMismatches>0 || !g_mcmArmed || g_mcmArmFailed) return "UNKNOWN";
 int complete=0;
 for(int i=0;i<g_mcmCount;i++)
 {
  int k=MCSFind(g_mcmSymbols[i],"SHADOW",1);
  if(k>=0 && g_mcsSnapshots[k].completed && g_mcsSnapshots[k].operations>0) complete++;
 }
 if(complete!=g_mcmCount || g_mcmCount<2 || g_mcmOverlapStart==0 || g_mcmOverlapEnd<=g_mcmOverlapStart) return "UNKNOWN";
 return "PASS";
}

int MCMCompletedCount()
{
 int result=0;
 for(int i=0;i<g_mcmCount;i++) {int k=MCSFind(g_mcmSymbols[i],"SHADOW",1);if(k>=0 && g_mcsSnapshots[k].completed) result++;}
 return result;
}

void MCMExport()
{
 if(!MQLInfoInteger(MQL_TESTER)) return;
 int h=MCSOpen("_multi_summary");
 if(h==INVALID_HANDLE) {g_mcmUnknown++;return;}
 if(!FileWrite(h,"symbol","kind","cycle","server_epoch_s","registered","completed","operations","callbacks","risk_bits","allowed","rng","candidate","input_digest","input_version","history_version","start_wall_us","end_wall_us","duration_us","quote_samples","quote_advances","quote_regressions","last_quote_msc","bar_samples","bar_advances","last_bar_s","input_arrivals","shadow_overlap_s","natural_shadow_overlap","queue_depth","broker_latency","status")) g_mcmUnknown++;
 ulong overlap=(g_mcmOverlapEnd>g_mcmOverlapStart)?g_mcmOverlapEnd-g_mcmOverlapStart:0;
 string natural=g_mcmNaturalOverlapUs>0?"OBSERVED":"UNKNOWN";
 string status=MCMValidationStatus();
 for(int i=0;i<g_mcmCount;i++)
 {
  int k=MCSFind(g_mcmSymbols[i],"SHADOW",1);MCSSnapshot s;ZeroMemory(s);
  if(k>=0) s=g_mcsSnapshots[k];else g_mcmUnknown++;
  int callbacks=0;
  for(int j=0;j<ArraySize(g_mcsCallbacks);j++) if(g_mcsCallbacks[j].symbol==g_mcmSymbols[i] && g_mcsCallbacks[j].kind=="SHADOW" && g_mcsCallbacks[j].cycle==1) callbacks++;
  if(!FileWrite(h,g_mcmSymbols[i],"SHADOW",1,g_mcmEpoch,1,(int)s.completed,s.operations,callbacks,
     StringFormat("%I64X",s.riskBits),(int)s.allowed,s.rng,s.candidate,s.inputDigest,s.inputVersion,s.historyVersion,
     s.wallStart,s.wallEnd,s.completed?s.wallEnd-s.wallStart:0,g_mcmQuoteSamples[i],g_mcmQuoteAdvances[i],g_mcmQuoteRegressions[i],
     g_mcmLastQuoteMsc[i],g_mcmBarSamples[i],g_mcmBarAdvances[i],g_mcmLastBarS[i],"UNKNOWN",(double)overlap/1000000.0,
     natural,"UNKNOWN","UNKNOWN",status)) g_mcmUnknown++;
 }
 FileFlush(h);FileClose(h);
 Print(StringFormat("TESTER_MC_MULTI %s symbols=%d shadow_completed=%d shadow_overlap_s=%.6f natural_shadow_overlap=%s unknown=%d replay_mismatch=%d",
   status,g_mcmCount,MCMCompletedCount(),(double)overlap/1000000.0,natural,g_mcmUnknown,g_mcsMismatches));
}

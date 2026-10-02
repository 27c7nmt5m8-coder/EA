// Tester-only observations and post-test replay. No replay result enters the EA.
union MCSBits {double d;ulong u;};
ulong MCSBitPattern(const double v) {MCSBits b;b.d=v;return b.u;}
string MCSLevelKey(const int candidate,const double dd,const uint rng)
{return StringFormat("%d/%I64X/%u;",candidate,MCSBitPattern(dd),rng);}
struct MCSSnapshot
{
 int cycle,offset,count,candidate;long requested;bool completed,allowed;
 ulong riskBits;uint rng;string inputDigest,signature;
};
struct MCSCallback {int cycle,operations;long server;ulong timer,elapsed;};
MCSSnapshot g_mcsSnapshots[];
MCSCallback g_mcsCallbacks[];
double g_mcsInput[];
ulong g_mcsTickUs[],g_mcsTimerUs[];
int g_mcsUnknown=0;

void MCSMeasure(const int kind,const ulong elapsed)
{
 if(kind==0) {int n=ArraySize(g_mcsTickUs);if(ArrayResize(g_mcsTickUs,n+1,8192)==n+1) g_mcsTickUs[n]=elapsed;else g_mcsUnknown++;}
 else {int n=ArraySize(g_mcsTimerUs);if(ArrayResize(g_mcsTimerUs,n+1,8192)==n+1) g_mcsTimerUs[n]=elapsed;else g_mcsUnknown++;}
}
int MCSFind(const int cycle)
{for(int i=ArraySize(g_mcsSnapshots)-1;i>=0;i--) if(g_mcsSnapshots[i].cycle==cycle) return i;return -1;}
void MCSCapture(const int cycle,double &returnsData[],const string digest)
{
 int n=ArraySize(g_mcsSnapshots),offset=ArraySize(g_mcsInput),count=ArraySize(returnsData);
 if(count<=0 || MCSFind(cycle)>=0 || ArrayResize(g_mcsInput,offset+count)!=offset+count ||
    ArrayCopy(g_mcsInput,returnsData,offset,0,count)!=count || ArrayResize(g_mcsSnapshots,n+1,64)!=n+1)
 {g_mcsUnknown++;return;}
 MCSSnapshot s;ZeroMemory(s);s.cycle=cycle;s.offset=offset;s.count=count;s.requested=(long)TimeCurrent();s.inputDigest=digest;
 g_mcsSnapshots[n]=s;
}
void MCSActualLevel(const int cycle,const int candidate,const double dd,const uint rng)
{int i=MCSFind(cycle);if(i<0) {g_mcsUnknown++;return;}g_mcsSnapshots[i].signature+=MCSLevelKey(candidate,dd,rng);}
void MCSActualComplete(const int cycle,const double risk,const bool allowed,const uint rng,const int candidate)
{
 int i=MCSFind(cycle);if(i<0) {g_mcsUnknown++;return;}
 g_mcsSnapshots[i].completed=true;g_mcsSnapshots[i].riskBits=MCSBitPattern(risk);
 g_mcsSnapshots[i].allowed=allowed;g_mcsSnapshots[i].rng=rng;g_mcsSnapshots[i].candidate=candidate;
}
void MCSActualCallback(const int cycle,const int operations,const ulong elapsed)
{
 int n=ArraySize(g_mcsCallbacks);
 if(ArrayResize(g_mcsCallbacks,n+1,4096)!=n+1) {g_mcsUnknown++;return;}
 MCSCallback c;c.cycle=cycle;c.operations=operations;c.elapsed=elapsed;c.server=(long)TimeCurrent();c.timer=g_tpmcTimer;
 g_mcsCallbacks[n]=c;
}
double MCSQuantile(ulong &values[],const double p)
{
 int n=ArraySize(values);if(n==0) return 0;
 double at=(n-1)*p;int low=(int)MathFloor(at),high=(int)MathCeil(at);
 return (double)values[low]+((double)values[high]-(double)values[low])*(at-low);
}
ulong MCSSum(ulong &values[])
{ulong sum=0;for(int i=0;i<ArraySize(values);i++) sum+=values[i];return sum;}

class MCSReplay
{
public:
 double m_mcReturns[],m_mcDDs[],m_mcEquity,m_mcPeak,m_mcDD,g_mcRisk;
 int m_mcCandidate,m_mcRun,m_mcTrade,lastOperations;
 uint m_mcRandom;
 bool m_mcActive,g_historyDirty,g_mcAllowed,g_mcReady;
 datetime g_lastMC;
 ulong callbackUs[],callbackOps[],totalOperations;
 string signature;
 bool Prepare(const MCSSnapshot &s)
 {
  if(ArrayResize(m_mcReturns,s.count)!=s.count || ArrayCopy(m_mcReturns,g_mcsInput,0,s.offset,s.count)!=s.count || ArrayResize(m_mcDDs,MonteCarloRuns)!=MonteCarloRuns) return false;
  m_mcCandidate=(int)MathFloor((MaximumRiskPercent-MinimumRiskPercent)/MonteCarloRiskStep+1e-8);
  m_mcRun=0;m_mcTrade=0;m_mcEquity=100;m_mcPeak=100;m_mcDD=0;
  m_mcRandom=(uint)MonteCarloSeed;if(m_mcRandom==0) m_mcRandom=1;
  m_mcActive=true;g_historyDirty=false;g_mcAllowed=false;g_mcReady=false;g_mcRisk=0;g_lastMC=0;
  ArrayResize(callbackUs,0);ArrayResize(callbackOps,0);totalOperations=0;signature="";lastOperations=0;
  return true;
 }
 void Level(const double dd) {signature+=MCSLevelKey(m_mcCandidate,dd,m_mcRandom);}
 #include "TesterMCSchedulerCore.mqh"
 bool Run(const int mode)
 {
  while(m_mcActive)
  {
   int n=ArraySize(callbackUs);if(n>=100000) return false;
   lastOperations=0;ulong start=GetMicrosecondCount(),deadline=GetTickCount64()+20;
   switch(mode)
   {case 0:Advance0(deadline);break;case 1:Advance1(deadline);break;case 2:Advance2(deadline);break;
    case 3:Advance3(deadline);break;case 4:Advance4(deadline);break;case 5:Advance5(deadline);break;default:return false;}
   ulong elapsed=GetMicrosecondCount()-start;
   if(ArrayResize(callbackUs,n+1,2048)!=n+1 || ArrayResize(callbackOps,n+1,2048)!=n+1) return false;
   callbackUs[n]=elapsed;callbackOps[n]=(ulong)lastOperations;totalOperations+=(ulong)lastOperations;
  }
  return g_mcReady;
 }
};

string MCSPrefix()
{
 string start=ArraySize(g_tpoDays)>0?TimeToString(g_tpoDays[0].day,TIME_DATE):"none";
 return "CodexMCSched"+IntegerToString(MCS_MODE)+"_20260927_"+_Symbol+"_"+start+"_A"+DoubleToString(MaxSpreadATR,2)+"_S"+DoubleToString(MaxSpreadSL,2);
}
int MCSOpen(const string suffix)
{int h=FileOpen(MCSPrefix()+suffix+".csv",FILE_WRITE|FILE_CSV|FILE_ANSI|FILE_COMMON,',');if(h==INVALID_HANDLE) g_mcsUnknown++;return h;}
void MCSExportActual()
{
 int h=MCSOpen("_callbacks");if(h==INVALID_HANDLE) return;
 if(!FileWrite(h,"cycle","server_s","timer","operations","elapsed_us")) g_mcsUnknown++;
 for(int i=0;i<ArraySize(g_mcsCallbacks);i++)
 {MCSCallback c=g_mcsCallbacks[i];if(!FileWrite(h,c.cycle,c.server,c.timer,c.operations,c.elapsed)) g_mcsUnknown++;}
 FileFlush(h);FileClose(h);
 h=MCSOpen("_events");if(h==INVALID_HANDLE) return;
 if(!FileWrite(h,"event","count","total_us","median_us","p90_us","p95_us","max_us")) g_mcsUnknown++;
 ArraySort(g_mcsTickUs);ArraySort(g_mcsTimerUs);
 if(!FileWrite(h,"OnTick",ArraySize(g_mcsTickUs),MCSSum(g_mcsTickUs),MCSQuantile(g_mcsTickUs,.5),MCSQuantile(g_mcsTickUs,.9),MCSQuantile(g_mcsTickUs,.95),MCSQuantile(g_mcsTickUs,1))) g_mcsUnknown++;
 if(!FileWrite(h,"OnTimer",ArraySize(g_mcsTimerUs),MCSSum(g_mcsTimerUs),MCSQuantile(g_mcsTimerUs,.5),MCSQuantile(g_mcsTimerUs,.9),MCSQuantile(g_mcsTimerUs,.95),MCSQuantile(g_mcsTimerUs,1))) g_mcsUnknown++;
 FileFlush(h);FileClose(h);
}
void MCSFinish()
{
 if(!MQLInfoInteger(MQL_TESTER)) return;
 MCSExportActual();int actualSnapshots=ArraySize(g_mcsSnapshots);
 // Synthetic inputs exercise ordinary simulation and zero-equity early termination.
 double synthetic[];ArrayResize(synthetic,30);
 for(int i=0;i<30;i++) synthetic[i]=(i%2==0)?1:-1;
 MCSCapture(-1,synthetic,"SYNTH_ALTERNATING");
 for(int i=0;i<30;i++) synthetic[i]=(i%2==0)?1000:-1000;
 MCSCapture(-2,synthetic,"SYNTH_ZERO_EQUITY");
 int h=MCSOpen("_replay");if(h==INVALID_HANDLE) return;
 if(!FileWrite(h,"cycle","mode","samples","input_digest","actual_compared","actual_equal","equal_reference","risk_bits","allowed","rng","candidate","operations","callbacks","compute_us","wall_us","callback_median_us","callback_p90_us","callback_p95_us","callback_max_us","operations_min","operations_median","operations_max")) g_mcsUnknown++;
 int comparisons=0,mismatches=0;
 for(int i=0;i<ArraySize(g_mcsSnapshots);i++)
 {
  MCSSnapshot s=g_mcsSnapshots[i];string reference="";ulong referenceRisk=0,referenceOps=0;bool referenceAllowed=false;uint referenceRng=0;int referenceCandidate=0;
  for(int mode=0;mode<6;mode++)
  {
   MCSReplay r;if(!r.Prepare(s)) {g_mcsUnknown++;continue;}
   ulong started=GetMicrosecondCount();if(!r.Run(mode)) {g_mcsUnknown++;continue;}ulong wall=GetMicrosecondCount()-started;
   ulong risk=MCSBitPattern(r.g_mcRisk);
   if(mode==0) {reference=r.signature;referenceRisk=risk;referenceAllowed=r.g_mcAllowed;referenceRng=r.m_mcRandom;referenceCandidate=r.m_mcCandidate;referenceOps=r.totalOperations;}
   bool equal=r.signature==reference && risk==referenceRisk && r.g_mcAllowed==referenceAllowed && r.m_mcRandom==referenceRng && r.m_mcCandidate==referenceCandidate && r.totalOperations==referenceOps;
   bool actual=!s.completed || (s.signature==r.signature && s.riskBits==risk && s.allowed==r.g_mcAllowed && s.rng==r.m_mcRandom && s.candidate==r.m_mcCandidate);
   comparisons++;if(!equal || !actual) mismatches++;
   ulong compute=MCSSum(r.callbackUs);ArraySort(r.callbackUs);ArraySort(r.callbackOps);
   if(!FileWrite(h,s.cycle,mode,s.count,s.inputDigest,(int)s.completed,(int)actual,(int)equal,StringFormat("%I64X",risk),(int)r.g_mcAllowed,r.m_mcRandom,r.m_mcCandidate,r.totalOperations,ArraySize(r.callbackUs),compute,wall,MCSQuantile(r.callbackUs,.5),MCSQuantile(r.callbackUs,.9),MCSQuantile(r.callbackUs,.95),MCSQuantile(r.callbackUs,1),MCSQuantile(r.callbackOps,0),MCSQuantile(r.callbackOps,.5),MCSQuantile(r.callbackOps,1))) g_mcsUnknown++;
  }
 }
 FileFlush(h);FileClose(h);
 Print(StringFormat("TESTER_MC_SCHEDULER %s mode=%d snapshots=%d comparisons=%d mismatch=%d unknown=%d prefix=%s",mismatches==0 && g_mcsUnknown==0?"PASS":"FAIL",MCS_MODE,actualSnapshots,comparisons,mismatches,g_mcsUnknown,MCSPrefix()));
}

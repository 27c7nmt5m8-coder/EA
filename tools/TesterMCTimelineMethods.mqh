// Included in generated SymbolState. Only diagnostic members are assigned here.
void TPMCEmit(const string kind,const string trigger="",const int opportunity=-1)
{
 if(g_tpShadow || !MQLInfoInteger(MQL_TESTER)) return;
 TPMCEvent e;ZeroMemory(e);
 e.event=kind;e.symbol=m_symbol;e.trigger=trigger;e.inputDigest=m_tpmcDigest;
 e.server=(long)TimeCurrent();e.wallUs=GetMicrosecondCount();e.timer=g_tpmcTimer;
 MqlTick tick;if(SymbolInfoTick(m_symbol,tick)) e.quoteMsc=tick.time_msc;
 e.cycle=m_tpmcCycle;e.parent=m_tpmcParent;e.dirtyMask=m_tpmcDirty;e.callPath=m_tpmcCallPath;
 e.historyVersion=m_tpmcHistoryVersion;e.inputVersion=m_tpmcInputVersion;e.stateVersion=m_tpmcStateVersion;
 e.samples=g_sampleCount;e.winRate=g_winRate;e.risk=g_mcRisk;
 e.ready=g_mcReady;e.allowed=g_mcAllowed;e.active=m_mcActive;e.historyOK=g_historyOK;e.historyDirty=g_historyDirty;
 e.run=m_mcRun;e.trade=m_mcTrade;e.candidate=m_mcCandidate;
 e.operations=m_tpmcOperations;e.calls=m_tpmcCalls;e.advanceUs=m_tpmcAdvanceUs;
 e.previousComplete=m_tpmcCompleteCycle;e.lastComplete=m_tpmcCompleteTime;e.validCycle=m_tpmcValidCycle;
 e.accepted=g_tpmcAccepted;e.positionKind=m_tpbPositionKind;e.oppId="";e.eligibleId="";
 e.lastEligible=m_tpmcLastEligible;e.eligibleTimer=m_tpmcObserveTimer;
 if(m_tpmcEligible>=0 && m_tpmcEligible<ArraySize(g_tpb)) e.eligibleId=g_tpb[m_tpmcEligible].id;
 if(opportunity>=0 && opportunity<ArraySize(g_tpb))
 {e.oppId=g_tpb[opportunity].id;e.bar=(long)g_tpo[opportunity].bar;e.score=g_tpb[opportunity].scoreLast;e.positionMask=g_tpb[opportunity].lastPositionMask;}
 TPMCAppend(e);
}
void TPMCDirty(const int reason)
{
 if(g_tpShadow) return;
 bool fresh=(m_tpmcDirty&((ulong)reason))==0;m_tpmcDirty|=(ulong)reason;
 if(fresh) TPMCEmit("DIRTY_MARK",IntegerToString(reason));
}
void TPMCHistory()
{
 if(g_tpShadow) return;
 m_tpmcHistoryVersion++;
 bool changed=m_tpmcInputVersion==0 || ArraySize(m_tpmcReturns)!=ArraySize(g_returns) || m_tpmcWinRate!=g_winRate;
 if(!changed) for(int i=0;i<ArraySize(g_returns);i++) if(m_tpmcReturns[i]!=g_returns[i]) {changed=true;break;}
 bool stateChanged=changed || m_tpmcLosses!=g_consecutiveLosses || m_tpmcWins!=g_consecutiveWins;
 if(changed)
 {
  if(ArrayResize(m_tpmcReturns,ArraySize(g_returns))!=ArraySize(g_returns) || ArrayCopy(m_tpmcReturns,g_returns)!=ArraySize(g_returns)) g_tpmcUnknown++;
  m_tpmcInputVersion++;m_tpmcWinRate=g_winRate;
  string fingerprint=IntegerToString(g_sampleCount)+"/"+StringFormat("%.17g",g_winRate);
  for(int i=0;i<ArraySize(g_returns);i++) fingerprint+="/"+StringFormat("%.17g",g_returns[i]);
  m_tpmcDigest=ScopeDigest(fingerprint);
 }
 if(stateChanged) {m_tpmcStateVersion++;m_tpmcLosses=g_consecutiveLosses;m_tpmcWins=g_consecutiveWins;}
 if(changed || stateChanged || m_tpmcDirty!=0) TPMCEmit("HISTORY_REFRESH",changed?"INPUT_CHANGED":"SAME_INPUT");
}
string TPMCTrigger(const bool force)
{
 if(m_tpmcCycle==0) return "INITIAL";
 if(force) return m_tpmcCycleInput!=m_tpmcInputVersion?"HISTORY_CHANGED":"FORCED_SAME_INPUT";
 if(g_mcReady) return "PERIODIC_EXPIRY";
 return "RETRY_NOT_READY";
}
void TPMCBeforeForce(const bool force)
{
 if(force && m_mcActive) TPMCEmit("CANCEL",TPMCTrigger(force));
}
void TPMCRequest(const bool force)
{
 string reason=TPMCTrigger(force);
 if(g_mcReady) {TPMCEmit("INVALIDATE",reason);m_tpmcValidCycle=0;}
 m_tpmcParent=m_tpmcCycle;m_tpmcCycle++;m_tpmcCycleInput=m_tpmcInputVersion;
 m_tpmcOperations=0;m_tpmcCalls=0;m_tpmcAdvanceUs=0;
 TPMCEmit("REQUEST",reason);m_tpmcDirty=0;
}
void TPMCComplete(const string reason)
{
 TPMCEmit("COMPLETE",reason);
 m_tpmcCompleteCycle=m_tpmcCycle;m_tpmcCompleteTime=TimeCurrent();m_tpmcValidCycle=m_tpmcCycle;
}
void TPMCObserve(const int i,const bool candidateNow)
{
 int current=candidateNow?i:-1;
 if(m_tpmcEligible>=0 && current!=m_tpmcEligible)
 {
  string cause=TPOHas(m_tpmcEligible,TPO_ACCEPTED)?"ENTERED":
   ((long)TimeCurrent()>=(long)g_tpo[m_tpmcEligible].bar+60?"BAR_EXPIRED":"NO_LONGER_ELIGIBLE");
  TPMCEmit("ELIGIBILITY_END",cause,m_tpmcEligible);m_tpmcSignature="";
 }
 m_tpmcEligible=current;m_tpmcObserveTimer=g_tpmcTimer;
 if(current<0) return;
 m_tpmcLastEligible=TimeCurrent();
 string signature=StringFormat("%d/%d/%d/%d/%d/%d/%d/%d/%.10f",i,m_tpmcCycle,m_tpmcInputVersion,m_tpbPositionKind,(int)g_mcReady,(int)g_mcAllowed,(int)m_mcActive,g_tpb[i].lastPositionMask,g_tpb[i].scoreLast);
 if(signature!=m_tpmcSignature) {m_tpmcSignature=signature;TPMCEmit("ELIGIBLE","",i);}
}
void TPMCAccepted()
{g_tpmcAccepted++;TPMCEmit("ACCEPTED","",g_tpOrderOpportunity);}
void AdvanceMonteCarlo(ulong deadline)
{
 bool computing=m_mcActive && !g_historyDirty;
 ulong start=GetMicrosecondCount();m_tpmcLastOperations=0;
 AdvanceMonteCarloCore(deadline);
 if(computing)
 {
  m_tpmcAdvanceUs+=GetMicrosecondCount()-start;m_tpmcOperations+=(ulong)m_tpmcLastOperations;m_tpmcCalls++;
  if(g_mcReady && !m_mcActive) TPMCComplete(g_mcAllowed?"BOOTSTRAP_ALLOWED":"BOOTSTRAP_DENIED");
 }
}
void TPMCStop()
{
 if(m_tpmcEligible>=0) TPMCEmit("ELIGIBILITY_END","RUN_END",m_tpmcEligible);
 TPMCEmit("RUN_END");
}

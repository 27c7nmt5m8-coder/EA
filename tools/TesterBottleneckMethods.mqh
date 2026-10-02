// Included inside generated SymbolState; observes existing decisions, never evaluates new orders.
void TPBIdentity(const int i,PatternSignal &p,const bool buy)
{
 if(!TPBEnsure(i)) return;
 if(StringLen(g_tpb[i].id)>0) return;
 string signature;
 if(IsFailedBreakout(p.type)) signature=StringFormat("FB/%d/%I64d",(int)PatternDirection(p),(long)p.referenceTime);
 else if(p.type==PATTERN_BULLISH_123 || p.type==PATTERN_BEARISH_123)
  signature=StringFormat("123/%d/%I64d/%I64d/%I64d",(int)PatternDirection(p),(long)p.firstTime,(long)p.headTime,(long)p.secondTime);
 else signature=StringFormat("L/%d/%I64d/%I64d/%I64d",(int)p.type,(long)p.firstTime,(long)p.headTime,(long)p.secondTime);
 string id=ScopeDigest(m_symbol+"/"+IntegerToString(g_tpo[i].bar)+"/"+signature);
 for(int j=0;j<ArraySize(g_tpb);j++) if(j!=i && g_tpb[j].id==id) g_tpoUnknown++;
 g_tpb[i].id=id;g_tpb[i].buy=buy;
}
void TPBCandidate(const int i,const int safetyReason)
{
 if(!TPBEnsure(i)) return;
 if(g_tpb[i].firstCandidate==0) g_tpb[i].firstCandidate=TimeCurrent();
 g_tpb[i].lastCandidate=TimeCurrent();
 ulong mask=0;
 bool unresolved=safetyReason==TP_SAFETY_ACCOUNT_ORDER || safetyReason==TP_SAFETY_SYMBOL_ORDER;
 bool positionPass=m_tpbPositionKind==0 && !unresolved;
 if(unresolved) mask|=(ulong)1<<TPB_UNRESOLVED;
 else if(m_tpbPositionKind==1)
 {
  mask|=(ulong)1<<TPB_SAME_SYMBOL;
  mask|=(ulong)1<<(m_tpbPositionBuy==g_tpb[i].buy?TPB_SAME_DIRECTION:TPB_OPPOSITE_DIRECTION);
  mask|=(ulong)1<<(m_tpbNetting?TPB_NETTING:TPB_HEDGING);
  if(OnePositionPerSymbol) mask|=(ulong)1<<TPB_SINGLE_POSITION;
  mask|=(ulong)1<<(m_tpbPositionOwned?TPB_OWN:TPB_FOREIGN);
 }
 else if(m_tpbPositionKind==2) mask|=(ulong)1<<TPB_PENDING;
 else if(!positionPass) mask|=(ulong)1<<TPB_POSITION_OTHER;
 g_tpb[i].positionMask|=mask;
 g_tpb[i].lastPositionMask=(int)mask;
 if(!positionPass) return;
 TPOStage(i,TPO_POSITION_PASS);
 bool required=RiskMode!=RISK_FIXED_ADJUST;
 bool ready=!required || g_mcReady,allowed=!required || g_mcAllowed;
 int reason=TPBMCClassify(required,g_historyOK,g_historyDirty,ready,allowed,m_mcActive,m_tpbMCOutcome,ArraySize(m_mcReturns));
 g_tpb[i].mcMask|=(ulong)1<<reason;
 if(ready) TPOStage(i,TPO_MC_READY);
 if(ready && allowed) TPOStage(i,TPO_MC_PERMITTED);
 else g_tpb[i].mcBlockMask|=(ulong)1<<reason;
 g_tpb[i].lastMCReason=reason;g_tpb[i].mcReady=ready;g_tpb[i].mcAllowed=allowed;g_tpb[i].mcActive=m_mcActive;
 g_tpb[i].historyOK=g_historyOK;g_tpb[i].historyDirty=g_historyDirty;
 g_tpb[i].samples=g_sampleCount;g_tpb[i].returnsCount=ArraySize(g_returns);g_tpb[i].bootstrapCount=ArraySize(m_mcReturns);
 g_tpb[i].mcRun=m_mcRun;g_tpb[i].mcTrade=m_mcTrade;g_tpb[i].mcCandidate=m_mcCandidate;
 g_tpb[i].winRate=g_winRate;g_tpb[i].risk=g_mcRisk;g_tpb[i].ddSeen=m_tpbDDSeen;g_tpb[i].dd=m_tpbLastDD;
 g_tpb[i].ddLimit=MonteCarloMaxDrawdownPercent*MonteCarloSafetyFactor;
 if(m_mcActive && m_tpbMCStarted>0) g_tpb[i].elapsedMax=MathMax(g_tpb[i].elapsedMax,(double)(TimeCurrent()-m_tpbMCStarted));
}

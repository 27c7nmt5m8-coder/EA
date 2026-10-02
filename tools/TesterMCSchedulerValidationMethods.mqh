// Included only inside generated SymbolState; product fields are read, never assigned.
MCVContext MCVReadContext()
{
 MCVContext c;c.cycle=m_tpmcCycle;c.inputVersion=m_tpmcInputVersion;c.stateVersion=m_tpmcStateVersion;
 c.historyVersion=m_tpmcHistoryVersion;c.positionKind=m_tpbPositionKind;c.digest=m_tpmcDigest;
 c.ready=g_mcReady;c.allowed=g_mcAllowed;c.active=m_mcActive;c.historyOK=g_historyOK;c.historyDirty=g_historyDirty;return c;
}
string MCVIdentity(PatternSignal &p,const datetime bar)
{
 string signature;
 if(IsFailedBreakout(p.type)) signature=StringFormat("FB/%d/%I64d",(int)PatternDirection(p),(long)p.referenceTime);
 else if(p.type==PATTERN_BULLISH_123 || p.type==PATTERN_BEARISH_123)
  signature=StringFormat("123/%d/%I64d/%I64d/%I64d",(int)PatternDirection(p),(long)p.firstTime,(long)p.headTime,(long)p.secondTime);
 else signature=StringFormat("L/%d/%I64d/%I64d/%I64d",(int)p.type,(long)p.firstTime,(long)p.headTime,(long)p.secondTime);
 return ScopeDigest(m_symbol+"/"+IntegerToString(bar)+"/"+signature);
}
string MCVOwnedOpportunity(PatternSignal &p)
{
 datetime bar=iTime(m_symbol,PERIOD_M1,0);
 string id=MCVIdentity(p,bar);
 int i=g_tpOrderOpportunity;
 // Do not attribute stale/global observer state to another symbol or pattern.
 if(i>=0 && i<ArraySize(g_tpo) && i<ArraySize(g_tpb) && g_tpo[i].symbol==m_symbol && g_tpo[i].bar==bar && g_tpb[i].id==id)
  return g_tpb[i].id;
 return id;
}
string MCVLegacyKey(PatternSignal &p)
{return g_statePrefix+"/MCV_LEGACY/"+IntegerToString(p.secondTime)+"/"+IntegerToString((int)PatternDirection(p));}
void MCVGuard(PatternSignal &p,const string reason,const string key)
{
 if(!MQLInfoInteger(MQL_TESTER)) return;
 datetime bar=iTime(m_symbol,PERIOD_M1,0);MCVContext c=MCVReadContext();
 // The shadow owns indicators but borrows only an observational snapshot.
 if(g_tpShadow) c=m_mcvObserverContext;
 MCVGuardAppend(MCVIdentity(p,bar),m_symbol,(long)bar,reason,MCVPrior(key),c);
}
void MCVClaim(PatternSignal &p,const string scopedId)
{
 if(!MQLInfoInteger(MQL_TESTER) || g_tpShadow) return;
 string claimant=MCVOwnedOpportunity(p);MCVRemember(PatternReceiptKey(scopedId),claimant);
 MCVContext c=MCVReadContext();
 MCVGuardAppend(claimant,m_symbol,(long)iTime(m_symbol,PERIOD_M1,0),"CLAIM_WRITE",claimant,c);
}

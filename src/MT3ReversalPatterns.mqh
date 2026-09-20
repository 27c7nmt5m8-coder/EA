// v2.43 methods included inside SymbolState. All data and receipts are symbol-scoped.
bool IsNewReversal(ENUM_PATTERN_TYPE type)
{return type==PATTERN_BULLISH_123 || type==PATTERN_BEARISH_123 || type==PATTERN_BULLISH_FAILED_BREAKOUT || type==PATTERN_BEARISH_FAILED_BREAKOUT;}
bool IsFailedBreakout(ENUM_PATTERN_TYPE type)
{return type==PATTERN_BULLISH_FAILED_BREAKOUT || type==PATTERN_BEARISH_FAILED_BREAKOUT;}
string PatternIdentity(PatternSignal &p)
{
 string signature;
 if(IsFailedBreakout(p.type))
  signature=StringFormat("FB/%d/%I64d",(int)PatternDirection(p),(long)p.referenceTime);
 else if(p.type==PATTERN_BULLISH_123 || p.type==PATTERN_BEARISH_123)
  signature=StringFormat("123/%d/%I64d/%I64d/%I64d",(int)PatternDirection(p),(long)p.firstTime,(long)p.headTime,(long)p.secondTime);
 else
  signature=StringFormat("L/%d/%I64d/%I64d/%I64d",(int)p.type,(long)p.firstTime,(long)p.headTime,(long)p.secondTime);
 return ScopeDigest(g_statePrefix+"/"+signature);
}
string PatternReceiptKey(string id) {return g_statePrefix+"p243."+id;}
bool IsPatternAlreadyUsed(PatternSignal &p)
{
 if(StateGet(PatternReceiptKey(PatternIdentity(p)))>0) return true;
 // Retain v2.42's same-pivot/direction guard, including migrated legacy enum values.
 return LegacyPatternAlreadyUsed(p);
}
bool PersistPatternClaims(PatternSignal &p)
{
 if(!p.valid || p.type==PATTERN_NONE) return true;
 string ids[];string claims=p.matchedIds;
 if(claims=="") claims=PatternIdentity(p);
 if(StringSplit(claims,';',ids)<1) return false;
 for(int i=0;i<ArraySize(ids);i++)
 {
  if(StringLen(ids[i])!=16) return false;
  if(GlobalVariableSet(PatternReceiptKey(ids[i]),1)==0) {GlobalVariablesFlush();return false;}
 }
 GlobalVariablesFlush();return true;
}
int PatternMaxShift()
{return (int)MathMin(PatternLookbackBars,Bars(m_symbol,PERIOD_M1)-SwingDepth-2);}
bool FindPatternPivot(bool low,int first,int last,int &shift,double &price)
{
 shift=-1;price=0;
 for(int i=(int)MathMax(first,SwingDepth+1);i<=last;i++)
 {
  if(low?!IsSwingLow(PERIOD_M1,i,SwingDepth):!IsSwingHigh(PERIOD_M1,i,SwingDepth)) continue;
  shift=i;price=low?iLow(m_symbol,PERIOD_M1,i):iHigh(m_symbol,PERIOD_M1,i);return price>0;
 }
 return false;
}
bool Detect123Reversal(bool buy,PatternSignal &signal)
{
 ZeroMemory(signal);double atr=GetATR(PERIOD_M1,14,1),eps=TickSize()*1e-8;
 if(atr<=0) return false;
 int maxShift=PatternMaxShift();
 int p3Max=(int)MathMin(maxShift,3*(SwingDepth+1));
 int s1,s2,s3;double p1,p2,p3;
 if(!FindPatternPivot(buy,SwingDepth+1,p3Max,s3,p3) ||
    !FindPatternPivot(!buy,s3+1,maxShift,s2,p2) ||
    !FindPatternPivot(buy,s2+1,maxShift,s1,p1)) return false;
 int side=buy?1:-1;
 double improvement=side*(p3-p1),leg=side*(p2-p1),pullback=side*(p2-p3);
 if(improvement<-eps || leg+eps<0.35*atr || pullback+eps<0.20*atr) return false;
 double level=p2+side*atr*NecklineToleranceATR;
 double close1=iClose(m_symbol,PERIOD_M1,1),close2=iClose(m_symbol,PERIOD_M1,2);
 if(close1<=0 || close2<=0 || side*(close1-level)<=eps || side*(close2-level)>eps) return false;
 // This must be the first closed-bar trigger after P3; discard broken P1 structures.
 for(int i=2;i<s3;i++)
 {
  double c=iClose(m_symbol,PERIOD_M1,i),edge=buy?iLow(m_symbol,PERIOD_M1,i):iHigh(m_symbol,PERIOD_M1,i);
  if(c<=0 || edge<=0 || side*(c-level)>eps || side*(edge-p1)<-eps) return false;
 }
 double triggerEdge=buy?iLow(m_symbol,PERIOD_M1,1):iHigh(m_symbol,PERIOD_M1,1);
 if(triggerEdge<=0 || side*(triggerEdge-p1)<-eps) return false;
 signal.type=buy?PATTERN_BULLISH_123:PATTERN_BEARISH_123;
 signal.valid=true;signal.buySignal=buy;signal.sellSignal=!buy;
 signal.firstPoint=p1;signal.headPoint=p2;signal.secondPoint=p3;
 signal.firstTime=iTime(m_symbol,PERIOD_M1,s1);signal.headTime=iTime(m_symbol,PERIOD_M1,s2);signal.secondTime=iTime(m_symbol,PERIOD_M1,s3);
 signal.neckline=p2;signal.necklineTime=signal.headTime;signal.entryLevel=close1;
 signal.triggerTime=iTime(m_symbol,PERIOD_M1,1);signal.referenceTime=signal.headTime;signal.referencePrice=p2;
 // Equal low/high is allowed; a clear HL/LH earns up to 20 additional points.
 signal.patternStrength=Score100(60+20*MathMin(1.0,MathMax(0.0,improvement)/(atr*0.35))+
  10*MathMin(1.0,MathMax(0.0,leg/atr-0.35)/0.65)+10*MathMin(1.0,MathMax(0.0,pullback/atr-0.20)/0.50));
 signal.patternId=PatternIdentity(signal);
 if(IsPatternAlreadyUsed(signal)) {ZeroMemory(signal);return false;}
 return true;
}
bool DetectBullish123(PatternSignal &signal) {return Detect123Reversal(true,signal);}
bool DetectBearish123(PatternSignal &signal) {return Detect123Reversal(false,signal);}
bool DetectFailedBreakout(bool buy,PatternSignal &signal)
{
 ZeroMemory(signal);double atr=GetATR(PERIOD_M1,14,1),eps=TickSize()*1e-8;
 if(atr<=0) return false;
 int side=buy?1:-1,maxShift=PatternMaxShift();
 double close=iClose(m_symbol,PERIOD_M1,1),open=iOpen(m_symbol,PERIOD_M1,1);
 double high=iHigh(m_symbol,PERIOD_M1,1),low=iLow(m_symbol,PERIOD_M1,1);
 if(close<=0 || open<=0 || low<=0 || high<MathMax(close,open)-eps || low>MathMin(close,open)+eps || high-low<TickSize()) return false;
 // A distinct, CLOSED outside bar is required. Same-bar wicks never qualify.
 for(int broken=2;broken<=4;broken++)
 {
  int ref;double level;
  // The reference pivot had to be fully confirmed before the breakout happened.
  if(!FindPatternPivot(buy,broken+SwingDepth+1,maxShift,ref,level)) continue;
  double outside=iClose(m_symbol,PERIOD_M1,broken),before=iClose(m_symbol,PERIOD_M1,broken+1);
  if(outside<=0 || before<=0 || side*(outside-level)>=-eps || side*(before-level)<-eps ||
     side*(close-level)<=eps || side*(close-level)>0.35*atr+eps) continue;
  double edge=buy?iLow(m_symbol,PERIOD_M1,broken):iHigh(m_symbol,PERIOD_M1,broken);
  if(edge<=0 || side*(level-edge)<0.05*atr-eps) continue;
  bool valid=true;double extreme=edge;
  for(int i=1;i<=broken;i++)
  {
   double c=iClose(m_symbol,PERIOD_M1,i),e=buy?iLow(m_symbol,PERIOD_M1,i):iHigh(m_symbol,PERIOD_M1,i);
   if(c<=0 || e<=0 || (i>1 && i<broken && side*(c-level)>eps)) {valid=false;break;}
   extreme=buy?MathMin(extreme,e):MathMax(extreme,e);
  }
  double penetration=side*(level-extreme);
  if(!valid || penetration>0.30*atr+eps) continue;
  // A previously failed/broken level cannot be resurrected by a later return.
  for(int i=broken+1;i<ref-SwingDepth;i++)
  {
   double c=iClose(m_symbol,PERIOD_M1,i),e=buy?iLow(m_symbol,PERIOD_M1,i):iHigh(m_symbol,PERIOD_M1,i);
   if(c<=0 || e<=0 || side*(c-level)<-eps || side*(level-e)>=0.05*atr-eps) {valid=false;break;}
  }
  if(!valid) continue;
  signal.type=buy?PATTERN_BULLISH_FAILED_BREAKOUT:PATTERN_BEARISH_FAILED_BREAKOUT;
  signal.valid=true;signal.buySignal=buy;signal.sellSignal=!buy;
  signal.firstPoint=level;signal.secondPoint=level;signal.headPoint=extreme;signal.neckline=level;
  signal.firstTime=iTime(m_symbol,PERIOD_M1,ref);signal.secondTime=signal.firstTime;
  signal.headTime=iTime(m_symbol,PERIOD_M1,broken);signal.necklineTime=signal.firstTime;
  signal.referenceTime=signal.firstTime;signal.referencePrice=level;signal.breakoutTime=signal.headTime;
  signal.triggerTime=iTime(m_symbol,PERIOD_M1,1);signal.entryLevel=close;
  double body=MathAbs(close-open)/atr,position=buy?(close-low)/(high-low):(high-close)/(high-low);
  double bodyGrade=side*(close-open)>0?MathMin(1.0,body/0.20):0;
  signal.patternStrength=Score100(55+20*bodyGrade+15*position+5*(4-broken));
  if(body<0.03 || side*(close-open)<=0) signal.patternStrength=MathMin(60.0,signal.patternStrength);
  signal.patternId=PatternIdentity(signal);
  if(IsPatternAlreadyUsed(signal)) {ZeroMemory(signal);return false;}
  return true;
 }
 return false;
}
bool DetectBullishFailedBreakout(PatternSignal &signal) {return DetectFailedBreakout(true,signal);}
bool DetectBearishFailedBreakout(PatternSignal &signal) {return DetectFailedBreakout(false,signal);}
bool AppendPattern(PatternSignal &candidates[],PatternSignal &p)
{
 if(!p.valid || IsPatternAlreadyUsed(p)) return true;
 int n=ArraySize(candidates);if(ArrayResize(candidates,n+1)!=n+1) return false;
 p.patternStrength=Score100(GetPatternScore(p));p.patternId=PatternIdentity(p);
 candidates[n]=p;return true;
}
bool GatherPatterns(PatternSignal &candidates[])
{
 ArrayResize(candidates,0);PatternSignal p;
 // Legacy order supplies a deterministic tie-break, without awarding extra votes.
 ZeroMemory(p);if(DetectTripleBottom(p) && !AppendPattern(candidates,p)) return false;
 ZeroMemory(p);if(DetectTripleTop(p) && !AppendPattern(candidates,p)) return false;
 ZeroMemory(p);if(DetectDoubleBottom(p) && !AppendPattern(candidates,p)) return false;
 ZeroMemory(p);if(DetectDoubleTop(p) && !AppendPattern(candidates,p)) return false;
 ZeroMemory(p);if(DetectInverseHeadShoulders(p) && !AppendPattern(candidates,p)) return false;
 ZeroMemory(p);if(DetectHeadShoulders(p) && !AppendPattern(candidates,p)) return false;
 ZeroMemory(p);if(DetectBullish123(p) && !AppendPattern(candidates,p)) return false;
 ZeroMemory(p);if(DetectBearish123(p) && !AppendPattern(candidates,p)) return false;
 ZeroMemory(p);if(DetectBullishFailedBreakout(p) && !AppendPattern(candidates,p)) return false;
 ZeroMemory(p);if(DetectBearishFailedBreakout(p) && !AppendPattern(candidates,p)) return false;
 return true;
}
bool ChoosePattern(PatternSignal &candidates[],bool allowBuy,bool allowSell,PatternSignal &signal)
{
 ZeroMemory(signal);int best=-1;bool bull=false,bear=false;string claims="";
 for(int i=0;i<ArraySize(candidates);i++)
 {
  PatternSignal p=candidates[i];int direction=(int)PatternDirection(p);
  if(!p.valid || IsPatternAlreadyUsed(p) || (direction!=ENTRY_BUY && direction!=ENTRY_SELL)) continue;
  if(direction==ENTRY_BUY && !allowBuy) continue;
  if(direction==ENTRY_SELL && !allowSell) continue;
  bull=bull || direction==ENTRY_BUY;bear=bear || direction==ENTRY_SELL;
  if(best<0 || Score100(GetPatternScore(p))>Score100(GetPatternScore(candidates[best]))) best=i;
 }
 if(best<0 || (bull && bear)) return false;
 signal=candidates[best];signal.patternStrength=Score100(GetPatternScore(signal));signal.patternId=PatternIdentity(signal);
 for(int i=0;i<ArraySize(candidates);i++)
  if(candidates[i].valid && PatternDirection(candidates[i])==PatternDirection(signal) && !IsPatternAlreadyUsed(candidates[i]))
  {if(claims!="") claims+=";";claims+=PatternIdentity(candidates[i]);}
 signal.matchedIds=claims;return true;
}
bool DetectReversalPattern(PatternSignal &signal)
{
 ZeroMemory(signal);PatternSignal candidates[];
 if(!GatherPatterns(candidates)) {g_status="Pattern candidate allocation failed";return false;}
 return ChoosePattern(candidates,true,true,signal);
}
bool SelectReversalPattern(MTFResult &r[],PatternSignal &signal)
{
 ZeroMemory(signal);PatternSignal candidates[];
 if(!GatherPatterns(candidates)) {g_status="Pattern candidate allocation failed";return false;}
 return ChoosePattern(candidates,WeightedSignalOK(r,true),WeightedSignalOK(r,false),signal);
}
bool PatternEntryLocationOK(PatternSignal &p,MqlTick &tick,bool buy)
{
 if(!IsNewReversal(p.type)) return true;
 if(DiagReject(!p.valid,"pattern_invalid") || DiagReject(p.triggerTime!=iTime(m_symbol,PERIOD_M1,1),"pattern_bar_stale") || DiagReject(buy!=p.buySignal,"pattern_direction_mismatch")) return false;
 double entry=buy?tick.ask:tick.bid,side=buy?1.0:-1.0;
 double atr=GetATR(PERIOD_M1,14,1);if(DiagReject(atr<=0,"pattern_atr_unavailable") || DiagReject(p.referencePrice<=0,"pattern_reference_invalid")) return false;
 if(DiagReject(side*(entry-p.referencePrice)<=0,"pattern_entry_wrong_side")) return false;
 if(DiagReject(IsFailedBreakout(p.type) && MathAbs(entry-p.referencePrice)>0.35*atr+TickSize()*1e-8,"failed_breakout_price_drift")) return false;
 return true;
}

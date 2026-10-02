// Tester-only observations. This header is copied into a generated EA, never src/.
bool g_tpSpreadSignalContext=false;
double g_tpScores[],g_tpRejectedScores[],g_tpSpreadPoints[],g_tpRejectedSpreadPoints[];
double g_tpSpreadLimits[],g_tpATRLimits[],g_tpSLLimits[],g_tpATRPoints[],g_tpSLDistancePoints[];
double g_tpRequiredATR[],g_tpRequiredSL[],g_tpPairSpreadPoints[];
double g_tpPairSpreadPrice[],g_tpPairATRPrice[],g_tpPairSLDistancePrice[],g_tpPairEpsilonPrice[],g_tpPairCurrentPass[];
long g_tpFirstPairTimestamp=0;
double g_tpCoreRequiredATR[],g_tpCoreRequiredSL[],g_tpCoreSpreadPoints[];
double g_tpScoreMTFSum=0,g_tpScorePatternSum=0,g_tpScoreLineSum=0;
double g_tpPoint=0,g_tpFirstAsk=0,g_tpFirstBid=0,g_tpMinAsk=0,g_tpMaxAsk=0,g_tpMinBid=0,g_tpMaxBid=0;
double g_tpMaxSymbolSpreadDelta=0;
int g_tpDigits=-1;
ulong g_tpScoreInvalid=0,g_tpScoreOutsideScale=0,g_tpScoreRebuildMismatch=0;
ulong g_tpSpreadNotEvaluated=0,g_tpSpreadSkippedScore=0,g_tpSpreadSkippedStops=0;
ulong g_tpSpreadGateChecks=0,g_tpSpreadGatePass=0,g_tpSpreadGateReject=0;
ulong g_tpSpreadReason[4],g_tpSpreadInvalid=0,g_tpSymbolSpreadMismatch=0,g_tpSymbolSpreadSamples=0;
ulong g_tpHourSignals[24],g_tpHourRejects[24];

void TPAppend(double &values[],const double value)
{
 int n=ArraySize(values);
 ArrayResize(values,n+1,4096);
 values[n]=value;
}
double TPQuantile(double &values[],const double fraction)
{
 int n=ArraySize(values);
 if(n==0) return 0;
 double sorted[];ArrayCopy(sorted,values);ArraySort(sorted);
 double position=(n-1)*fraction;
 int low=(int)MathFloor(position),high=(int)MathCeil(position);
 return sorted[low]+(sorted[high]-sorted[low])*(position-low);
}
string TPDistribution(const string name,double &values[])
{
 int n=ArraySize(values);
 if(n==0) return StringFormat("%s_n=0",name);
 double minimum=values[0],maximum=values[0],sum=0;
 for(int i=0;i<n;i++) {minimum=MathMin(minimum,values[i]);maximum=MathMax(maximum,values[i]);sum+=values[i];}
 return StringFormat("%s_n=%d min=%.6f median=%.6f p90=%.6f p95=%.6f p99=%.6f max=%.6f avg=%.6f",
  name,n,minimum,TPQuantile(values,0.50),TPQuantile(values,0.90),TPQuantile(values,0.95),
  TPQuantile(values,0.99),maximum,sum/n);
}
void TPScoreObserve(const double actual,const double required,const double mtf,const double pattern,const double line)
{
 if(!MQLInfoInteger(MQL_TESTER)) return;
 if(!MathIsValidNumber(actual) || !MathIsValidNumber(required) || !MathIsValidNumber(mtf) ||
    !MathIsValidNumber(pattern) || !MathIsValidNumber(line)) {g_tpScoreInvalid++;return;}
 TPAppend(g_tpScores,actual);
 if(actual<required) TPAppend(g_tpRejectedScores,actual);
 if(actual<0 || actual>100 || mtf<0 || mtf>100 || pattern<0 || pattern>100 || line<0 || line>20)
  g_tpScoreOutsideScale++;
 if(MathAbs(FinalSignalScore(mtf,pattern,line)-actual)>1e-8) g_tpScoreRebuildMismatch++;
 g_tpScoreMTFSum+=mtf;g_tpScorePatternSum+=pattern;g_tpScoreLineSum+=line;
}
void TPSpreadRaw(const string symbol,MqlTick &tick,const double atr,const bool rejected)
{
 double point=SymbolInfoDouble(symbol,SYMBOL_POINT);
 int digits=(int)SymbolInfoInteger(symbol,SYMBOL_DIGITS);
 double spread=tick.ask-tick.bid;
 if(!MathIsValidNumber(spread) || !MathIsValidNumber(point) || point<=0 ||
    tick.ask<=0 || tick.bid<=0 || spread<0) {g_tpSpreadInvalid++;return;}
 double points=spread/point;
 TPAppend(g_tpSpreadPoints,points);
 if(rejected) TPAppend(g_tpRejectedSpreadPoints,points);
 if(atr>0) {TPAppend(g_tpATRLimits,atr*MaxSpreadATR/point);TPAppend(g_tpATRPoints,atr/point);}
 if(g_tpDigits<0) {g_tpDigits=digits;g_tpPoint=point;g_tpFirstAsk=tick.ask;g_tpFirstBid=tick.bid;
  g_tpMinAsk=tick.ask;g_tpMaxAsk=tick.ask;g_tpMinBid=tick.bid;g_tpMaxBid=tick.bid;}
 g_tpMinAsk=MathMin(g_tpMinAsk,tick.ask);g_tpMaxAsk=MathMax(g_tpMaxAsk,tick.ask);
 g_tpMinBid=MathMin(g_tpMinBid,tick.bid);g_tpMaxBid=MathMax(g_tpMaxBid,tick.bid);
 long quoted=SymbolInfoInteger(symbol,SYMBOL_SPREAD);
 double delta=MathAbs((double)quoted-MathRound(points));
 g_tpSymbolSpreadSamples++;g_tpMaxSymbolSpreadDelta=MathMax(g_tpMaxSymbolSpreadDelta,delta);
 if(delta>0.5) g_tpSymbolSpreadMismatch++;
 MqlDateTime stamp;
 if(TimeToStruct(tick.time,stamp) && stamp.hour>=0 && stamp.hour<24)
 {g_tpHourSignals[stamp.hour]++;if(rejected) g_tpHourRejects[stamp.hour]++;}
}
void TPSpreadObserveSkipped(const string symbol,MqlTick &tick,const double atr,const int stage=0)
{
 if(!MQLInfoInteger(MQL_TESTER)) return;
 g_tpSpreadNotEvaluated++;
 if(stage==1) g_tpSpreadSkippedStops++;else g_tpSpreadSkippedScore++;
 TPSpreadRaw(symbol,tick,atr,false);
}
void TPSpreadObserveGate(const string symbol,MqlTick &tick,const double sl,const bool buy,
 const double atr,const double maxATR,const int maxPoints,const double maxSL,const double point,const int reason)
{
 if(!MQLInfoInteger(MQL_TESTER) || !g_tpSpreadSignalContext) return;
 g_tpSpreadGateChecks++;
 if(reason==0) g_tpSpreadGatePass++;else g_tpSpreadGateReject++;
 if(reason>=0 && reason<4) g_tpSpreadReason[reason]++;
 TPSpreadRaw(symbol,tick,atr,reason!=0);
 if(point>0 && atr>0)
 {
  double limit=atr*maxATR/point;
  if(maxPoints>0) limit=MathMin(limit,(double)maxPoints);
  if(sl>0)
  {
   double distance=MathAbs((buy?tick.ask:tick.bid)-sl);
   double slLimit=distance*maxSL/point;
   TPAppend(g_tpSLLimits,slLimit);
   TPAppend(g_tpSLDistancePoints,distance/point);
   limit=MathMin(limit,slLimit);
   if(distance>0)
   {
    double spread=tick.ask-tick.bid;
    if(g_tpFirstPairTimestamp==0) g_tpFirstPairTimestamp=(long)tick.time;
    TPAppend(g_tpRequiredATR,spread/atr);
    TPAppend(g_tpRequiredSL,spread/distance);
    TPAppend(g_tpPairSpreadPoints,spread/point);
    TPAppend(g_tpPairSpreadPrice,spread);
    TPAppend(g_tpPairATRPrice,atr);
    TPAppend(g_tpPairSLDistancePrice,distance);
    TPAppend(g_tpPairEpsilonPrice,SymbolInfoDouble(symbol,SYMBOL_TRADE_TICK_SIZE)*1e-8);
    TPAppend(g_tpPairCurrentPass,reason==0?1.0:0.0);
    MqlDateTime stamp;
    if(TimeToStruct(tick.time,stamp) && stamp.hour>=7 && stamp.hour<=20)
    {
     TPAppend(g_tpCoreRequiredATR,spread/atr);
     TPAppend(g_tpCoreRequiredSL,spread/distance);
     TPAppend(g_tpCoreSpreadPoints,spread/point);
    }
   }
  }
  TPAppend(g_tpSpreadLimits,limit);
 }
}
void TPPrintSignalSummary()
{
 if(!MQLInfoInteger(MQL_TESTER)) return;
 int n=ArraySize(g_tpScores);
 Print(StringFormat("TESTER_SCORE_SUMMARY required=%.6f scale=0..100 signals=%d pass=%d reject=%d invalid=%I64u outside_scale=%I64u rebuild_mismatch=%I64u mtf_weight=%.3f pattern_weight=%.3f line_weight=%.3f mtf_avg=%.6f pattern_avg=%.6f line_raw_avg=%.6f",
  MinimumSignalScore,n,n-ArraySize(g_tpRejectedScores),ArraySize(g_tpRejectedScores),g_tpScoreInvalid,
  g_tpScoreOutsideScale,g_tpScoreRebuildMismatch,FinalMTFWeight,FinalPatternWeight,FinalLineWeight,
  n>0?g_tpScoreMTFSum/n:0,n>0?g_tpScorePatternSum/n:0,n>0?g_tpScoreLineSum/n:0));
 Print("TESTER_SCORE_ALL "+TPDistribution("score",g_tpScores));
 Print("TESTER_SCORE_REJECTED "+TPDistribution("score",g_tpRejectedScores));
 double pip=g_tpPoint*((g_tpDigits==3 || g_tpDigits==5)?10.0:1.0);
 Print(StringFormat("TESTER_SPREAD_SUMMARY max_atr=%.6f max_sl=%.6f max_points=%d point=%.8f digits=%d pip_size=%.8f observed_n=%d gate_not_evaluated=%I64u score_reject_observed=%I64u stops_reject_observed=%I64u gate_checks=%I64u gate_pass=%I64u gate_reject=%I64u reason_atr_or_invalid=%I64u reason_points=%I64u reason_sl=%I64u invalid_quote=%I64u symbol_spread_samples=%I64u symbol_spread_mismatch=%I64u max_symbol_spread_delta_points=%.2f first_ask=%.6f first_bid=%.6f ask_min=%.6f ask_max=%.6f bid_min=%.6f bid_max=%.6f",
  MaxSpreadATR,MaxSpreadSL,MaxSpreadPoints,g_tpPoint,g_tpDigits,pip,ArraySize(g_tpSpreadPoints),
  g_tpSpreadNotEvaluated,g_tpSpreadSkippedScore,g_tpSpreadSkippedStops,
  g_tpSpreadGateChecks,g_tpSpreadGatePass,g_tpSpreadGateReject,
  g_tpSpreadReason[1],g_tpSpreadReason[2],g_tpSpreadReason[3],g_tpSpreadInvalid,
  g_tpSymbolSpreadSamples,g_tpSymbolSpreadMismatch,g_tpMaxSymbolSpreadDelta,
  g_tpFirstAsk,g_tpFirstBid,g_tpMinAsk,g_tpMaxAsk,g_tpMinBid,g_tpMaxBid));
 Print("TESTER_SPREAD_ALL_POINTS "+TPDistribution("spread_points",g_tpSpreadPoints));
 Print("TESTER_SPREAD_REJECTED_POINTS "+TPDistribution("spread_points",g_tpRejectedSpreadPoints));
 Print("TESTER_SPREAD_ATR_POINTS "+TPDistribution("atr_points",g_tpATRPoints));
 Print("TESTER_SPREAD_SL_DISTANCE_POINTS "+TPDistribution("sl_distance_points",g_tpSLDistancePoints));
 Print("TESTER_SPREAD_ATR_LIMIT_POINTS "+TPDistribution("atr_limit_points",g_tpATRLimits));
 Print("TESTER_SPREAD_SL_LIMIT_POINTS "+TPDistribution("sl_limit_points",g_tpSLLimits));
 Print("TESTER_SPREAD_EFFECTIVE_LIMIT_POINTS "+TPDistribution("limit_points",g_tpSpreadLimits));
 TPPrintBoundaries();
 TPExportPairs();
 for(int start=0;start<24;start+=6)
 {
  string line=StringFormat("TESTER_SPREAD_HOURLY server_hour=%02d-%02d",start,start+5);
  for(int hour=start;hour<start+6;hour++) line+=StringFormat(" h%02d=%I64u/%I64u",hour,g_tpHourSignals[hour],g_tpHourRejects[hour]);
  Print(line);
 }
}

void TPExportPairs()
{
 if(!MQLInfoInteger(MQL_TESTER)) return;
 int n=ArraySize(g_tpPairSpreadPrice);
 if(n<=0 || n!=ArraySize(g_tpPairATRPrice) || n!=ArraySize(g_tpPairSLDistancePrice) ||
    n!=ArraySize(g_tpPairEpsilonPrice) || n!=ArraySize(g_tpPairCurrentPass) ||
    n!=ArraySize(g_tpRequiredATR))
 {
  Print(StringFormat("TESTER_PAIR_EXPORT status=INVALID_COUNTS n=%d",n));
  return;
 }
 string filename="CodexJointPairs_20260924_"+_Symbol+"_"+IntegerToString(g_tpFirstPairTimestamp)+
  "_A"+DoubleToString(MaxSpreadATR,2)+"_S"+DoubleToString(MaxSpreadSL,2)+".csv";
 ResetLastError();
 int file=FileOpen(filename,FILE_WRITE|FILE_CSV|FILE_ANSI|FILE_COMMON,',');
 if(file==INVALID_HANDLE)
 {
  Print(StringFormat("TESTER_PAIR_EXPORT status=OPEN_FAILED error=%d",GetLastError()));
  return;
 }
 FileWrite(file,"spread","atr","sl_distance","epsilon","point","current_pass");
 for(int i=0;i<n;i++)
  FileWrite(file,DoubleToString(g_tpPairSpreadPrice[i],16),DoubleToString(g_tpPairATRPrice[i],16),
   DoubleToString(g_tpPairSLDistancePrice[i],16),DoubleToString(g_tpPairEpsilonPrice[i],16),
   DoubleToString(g_tpPoint,16),(int)g_tpPairCurrentPass[i]);
 FileClose(file);
 Print(StringFormat("TESTER_PAIR_EXPORT status=OK file=%s n=%d",filename,n));
}

double TPRequiredBoundary(double &values[],const double fraction)
{
 int n=ArraySize(values);
 if(n<=0) return -1;
 double sorted[];ArrayCopy(sorted,values);ArraySort(sorted);
 int rank=(int)MathCeil(fraction*n)-1;
 return sorted[MathMax(0,MathMin(n-1,rank))];
}
int TPJointPass(double &atrRatios[],double &slRatios[],double &spreadPoints[],
 const double atrLimit,const double slLimit)
{
 int n=ArraySize(atrRatios),passed=0;
 if(n!=ArraySize(slRatios) || n!=ArraySize(spreadPoints)) return -1;
 for(int i=0;i<n;i++)
  if(atrRatios[i]<=atrLimit && slRatios[i]<=slLimit &&
     (MaxSpreadPoints<=0 || spreadPoints[i]<=MaxSpreadPoints)) passed++;
 return passed;
}
void TPPrintBoundaries()
{
 int n=ArraySize(g_tpRequiredATR),core=ArraySize(g_tpCoreRequiredATR);
 Print(StringFormat("TESTER_SPREAD_PAIRED n=%d sl_n=%d spread_n=%d current_joint=%d actual_gate_pass=%I64u ratio_rule=AND point_cap=%d",
  n,ArraySize(g_tpRequiredSL),ArraySize(g_tpPairSpreadPoints),
  TPJointPass(g_tpRequiredATR,g_tpRequiredSL,g_tpPairSpreadPoints,MaxSpreadATR,MaxSpreadSL),
  g_tpSpreadGatePass,MaxSpreadPoints));
 Print(StringFormat("TESTER_SPREAD_CORE_HOURS server_hour=07-20 n=%d current_joint=%d",
  core,TPJointPass(g_tpCoreRequiredATR,g_tpCoreRequiredSL,g_tpCoreSpreadPoints,MaxSpreadATR,MaxSpreadSL)));
 if(n<=0) {Print("TESTER_SPREAD_BOUNDARY unavailable=no_score_pass_signal");return;}
 int targets[5]={10,25,50,75,90};
 for(int i=0;i<5;i++)
 {
  int q=targets[i];
  double atrRequired=TPRequiredBoundary(g_tpRequiredATR,q/100.0);
  double slRequired=TPRequiredBoundary(g_tpRequiredSL,q/100.0);
  Print(StringFormat("TESTER_SPREAD_BOUNDARY target=%d%% marginal_atr=%.8f marginal_sl=%.8f atr_only_joint=%d sl_only_joint=%d",
   q,atrRequired,slRequired,
   TPJointPass(g_tpRequiredATR,g_tpRequiredSL,g_tpPairSpreadPoints,atrRequired,MaxSpreadSL),
   TPJointPass(g_tpRequiredATR,g_tpRequiredSL,g_tpPairSpreadPoints,MaxSpreadATR,slRequired)));
 }
}

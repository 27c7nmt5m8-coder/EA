// Included only inside the generated Tester SymbolState class.
// This observer owns its indicator cache and cannot dispatch or persist trades.
int TPEvaluateOpportunity(const bool allowed,const int safetyReason)
{
 datetime bar=iTime(m_symbol,PERIOD_M1,0);
 if(bar<=0 || bar==g_lastTradeBar || bar==g_lastAttemptBar) return -1;
 MTFResult r[];if(!AnalyzeAllTimeframes(r)) return -1;
 PatternSignal p;ZeroMemory(p);
 if(!SelectReversalPattern(r,p) || IsPatternAlreadyUsed(p)) return -1;
 bool buy=PatternDirection(p)==ENTRY_BUY;
 if(buy?!BuySignalOK(p,r):!SellSignalOK(p,r)) return -1;
 int i=TPOFind(m_symbol,bar,PatternIdentity(p),buy);if(i<0) return -1;
 TPOStage(i,TPO_SIGNAL);
 if(buy?!IsBuyAllowed():!IsSellAllowed()) {TPOReason(i,TP_ENTRY_DIRECTION);return i;}
 double score=buy?CalculateFinalBuyScore(p,r):CalculateFinalSellScore(p,r);
 if(score<MinimumSignalScore) {TPOReason(i,TP_ENTRY_SCORE);return i;}
 TPOStage(i,TPO_SCORE);
 if(!SymbolDirectionAllowed(buy)) {TPOReason(i,TP_ENTRY_DIRECTION);return i;}
 MqlTick tick;if(!FreshQuote(tick)) {TPOReason(i,TP_ENTRY_QUOTE);return i;}
 double sl,tp;string source,fallback;
 if(!BuildEntryStops(buy,tick,p,sl,tp,source,fallback)) {TPOReason(i,TP_ENTRY_STOPS);return i;}
 TPOStage(i,TPO_VALID_STOP);TPOStage(i,TPO_SPREAD_EVALUATED);
 if(!SpreadOK(tick,sl,buy)) {TPOReason(i,TP_ENTRY_SPREAD);return i;}
 TPOStage(i,TPO_SPREAD_PASS);
 if(!PatternEntryLocationOK(p,tick,buy)) {TPOReason(i,TP_ENTRY_LOCATION);return i;}
 if(bar!=iTime(m_symbol,PERIOD_M1,0) || !MTFSnapshotCurrent()) {TPOReason(i,TP_ENTRY_SNAPSHOT);return i;}
 TPOStage(i,TPO_BEFORE_SAFETY);
 if(allowed) TPOStage(i,TPO_AFTER_SAFETY);
 else TPOReason(i,safetyReason>=0?safetyReason:TP_ENTRY_OTHER,true);
 return i;
}
void TPObserveBeforeSafety(const bool allowed,const int reason)
{
 if(!MQLInfoInteger(MQL_TESTER) || ExecutionMode!=EXECUTION_AUTO) {g_tpoUnknown++;return;}
 if(m_tpObserver==NULL) m_tpObserver=new SymbolState;
 if(m_tpObserver==NULL) {g_tpoUnknown++;return;}
 m_tpObserver.m_symbol=m_symbol;m_tpObserver.m_point=m_point;m_tpObserver.m_digits=m_digits;
 m_tpObserver.g_statePrefix=g_statePrefix;m_tpObserver.LINE_PREFIX=LINE_PREFIX;
 m_tpObserver.g_lastTradeBar=g_lastTradeBar;m_tpObserver.g_lastAttemptBar=g_lastAttemptBar;
 int levels=ArraySize(m_levels);
 if(ArrayResize(m_tpObserver.m_levels,levels)!=levels) {g_tpoUnknown++;return;}
 for(int i=0;i<levels;i++) m_tpObserver.m_levels[i]=m_levels[i];
 for(int i=0;i<2;i++) m_tpObserver.m_trends[i]=m_trends[i];
 g_tpShadow=true;
 m_tpObserver.TPEvaluateOpportunity(allowed,reason);
 g_tpShadow=false;
}

// v2.43 additions. The existing v2.42 scenarios execute before this suite.
void fixture123(string symbol,bool buy=true,double p1=98,double p2=102,double p3=99.2,int s1=30,int s2=18,int s3=6){
 Series r;double lo=std::max(p1,p3)+(p2-std::max(p1,p3))*.15,hi=p2-(p2-p3)*.15;
 r.low.assign(200,lo);r.high.assign(200,hi);r.close.assign(200,(lo+hi)/2);r.open=r.close;
 r.low[s1]=p1;r.high[s2]=p2;r.low[s3]=p3;
 r.close[2]=p2-.04;r.high[2]=std::max(hi,p2-.02);r.low[2]=std::min(lo,p2-.06);r.open[2]=r.close[2];
 r.close[1]=p2+.30;r.open[1]=p2+.04;r.low[1]=p2+.02;r.high[1]=p2+.40;
 if(!buy)for(int i=0;i<200;i++){double low=r.low[i];r.low[i]=200-r.high[i];r.high[i]=200-low;r.close[i]=200-r.close[i];r.open[i]=200-r.open[i];}
 series[symbol]=r;symbols[symbol].bid=r.close[1]+(buy?.05:-.07);symbols[symbol].ask=symbols[symbol].bid+.02;
}
void fixtureFailed(string symbol,bool buy=true,int broken=2,int ref=12){
 Series r;r.high.assign(200,101);r.low.assign(200,100.4);r.close.assign(200,100.6);r.open=r.close;
 r.low[ref]=100;
 for(int i=2;i<=broken;i++){r.low[i]=99.7;r.high[i]=100.2;r.open[i]=100.1;r.close[i]=99.85;}
 r.low[1]=99.85;r.high[1]=100.5;r.open[1]=99.9;r.close[1]=100.25;
 if(!buy)for(int i=0;i<200;i++){double low=r.low[i];r.low[i]=200-r.high[i];r.high[i]=200-low;r.close[i]=200-r.close[i];r.open[i]=200-r.open[i];}
 series[symbol]=r;symbols[symbol].bid=r.close[1]+(buy?.02:-.04);symbols[symbol].ask=symbols[symbol].bid+.02;
}
void scaleFixture(string symbol,double k){auto&s=symbols[symbol];s.bid*=k;s.ask*=k;s.atr*=k;s.tick*=k;s.point*=k;
 auto&r=series[symbol];for(auto*a:{&r.high,&r.low,&r.open,&r.close})for(auto&v:*a)v*=k;}
void check123(){
 reset();fixture123(u"FX");SymbolState s;setup(s);PatternSignal p;
 check(s.DetectBullish123(p)&&p.type==PATTERN_BULLISH_123&&p.buySignal,"123 bullish normal");
 check(p.firstTime<p.headTime&&p.headTime<p.secondTime&&p.secondTime<p.triggerTime,"123 chronological pivots");
 double strictScore=p.patternStrength;string firstId=p.patternId;
 fixture123(u"FX",true,98,102,98);check(s.DetectBullish123(p)&&p.patternStrength<strictScore,"123 equal bottom allowed at lower score than HL");
 fixture123(u"FX",false);check(s.DetectBearish123(p)&&p.type==PATTERN_BEARISH_123&&p.sellSignal,"123 bearish normal");
 fixture123(u"FX",true,98,102,97.9);check(!s.DetectBullish123(p),"123 P3 below P1 rejected");
 fixture123(u"FX",false,98,102,97.9);check(!s.DetectBearish123(p),"123 P3 above P1 rejected");
 fixture123(u"FX",true,100,100.6,100.1);check(!s.DetectBullish123(p),"123 P1 P2 leg below .35 ATR rejected");
 fixture123(u"FX",true,98,102,101.7);check(!s.DetectBullish123(p),"123 P2 P3 pullback below .20 ATR rejected");
 fixture123(u"FX");series[u"FX"].close[0]=105;series[u"FX"].close[1]=102.1;check(!s.DetectBullish123(p),"123 forming bar breakout cannot trigger");
 fixture123(u"FX",true,98,102,99.2,160,18,6);check(!s.DetectBullish123(p),"123 P1 outside lookback rejected");
 fixture123(u"FX",true,98,102,99.2,60,45,30);check(!s.DetectBullish123(p),"123 old P3 rejected");
 fixture123(u"FX");series[u"FX"].close[3]=102.3;check(!s.DetectBullish123(p),"123 previously crossed structure cannot be revived");
 fixture123(u"FX");check(s.DetectBullish123(p)&&p.patternId==firstId,"123 same structure stable identity");
 check(s.PersistPatternClaims(p),"123 receipt persisted");check(!s.DetectBullish123(p),"123 same structure reuse rejected");
 s.Shutdown();SymbolState again;setup(again);check(!again.DetectBullish123(p),"123 receipt survives restart");
 for(double k:{.01,1.0,100.0}){reset();fixture123(u"FX");scaleFixture(u"FX",k);SymbolState a;setup(a);check(a.DetectBullish123(p)&&near(p.patternStrength,strictScore),"123 ATR scale invariance");}
}
void checkFailed(){
 reset();fixtureFailed(u"FX");SymbolState s;setup(s);PatternSignal p;
 check(s.DetectBullishFailedBreakout(p)&&p.buySignal,"failed breakout bullish normal");
 check(p.referenceTime<p.breakoutTime&&p.breakoutTime<p.triggerTime,"failed breakout confirmed prior reference and distinct recovery bar");
 double full=p.patternStrength;
 fixtureFailed(u"FX",false);check(s.DetectBearishFailedBreakout(p)&&p.sellSignal,"failed breakout bearish normal");
 fixtureFailed(u"FX");series[u"FX"].low[2]=99.98;series[u"FX"].close[2]=99.99;check(!s.DetectBullishFailedBreakout(p),"failed breakout too small sweep rejected");
 fixtureFailed(u"FX");series[u"FX"].low[2]=99.3;check(!s.DetectBullishFailedBreakout(p),"failed breakout deep sweep rejected");
 fixtureFailed(u"FX");series[u"FX"].low[1]=99.3;check(!s.DetectBullishFailedBreakout(p),"failed breakout recovery bar deep excursion rejected");
 fixtureFailed(u"FX");series[u"FX"].close[1]=99.95;check(!s.DetectBullishFailedBreakout(p),"failed breakout no closed reclaim rejected");
 fixtureFailed(u"FX");series[u"FX"].close[2]=100.1;check(!s.DetectBullishFailedBreakout(p),"failed breakout one wick without outside close rejected");
 fixtureFailed(u"FX");series[u"FX"].close[0]=100.25;series[u"FX"].close[1]=99.95;check(!s.DetectBullishFailedBreakout(p),"failed breakout forming bar recovery rejected");
 fixtureFailed(u"FX",true,5,15);check(!s.DetectBullishFailedBreakout(p),"failed breakout return after more than three bars rejected");
 fixtureFailed(u"FX",true,4,12);check(s.DetectBullishFailedBreakout(p)&&p.patternStrength<full,"failed breakout third bar return allowed at lower score");
 fixtureFailed(u"FX");series[u"FX"].open[1]=100.249;check(s.DetectBullishFailedBreakout(p)&&p.patternStrength<=60,"failed breakout tiny recovery body low score");
 fixtureFailed(u"FX");series[u"FX"].close[1]=100.8;series[u"FX"].high[1]=100.9;check(!s.DetectBullishFailedBreakout(p),"failed breakout distant reclaim rejected");
 fixtureFailed(u"FX");series[u"FX"].low[5]=99.7;check(!s.DetectBullishFailedBreakout(p),"failed breakout old sweep not reused");
 fixtureFailed(u"FX",true,2,160);check(!s.DetectBullishFailedBreakout(p),"failed breakout reference outside lookback rejected");
 fixtureFailed(u"FX");check(s.DetectBullishFailedBreakout(p),"failed breakout fresh receipt fixture");string key=s.PatternReceiptKey(p.patternId);
 check(s.PersistPatternClaims(p)&&AIState(key)>0,"failed breakout receipt persisted");check(!s.DetectBullishFailedBreakout(p),"failed breakout same level reuse rejected");
 newbar();fixtureFailed(u"FX",true,2,13);check(!s.DetectBullishFailedBreakout(p),"failed breakout new episode at same reference time blocked");
 s.Shutdown();SymbolState again;setup(again);check(!again.DetectBullishFailedBreakout(p),"failed breakout receipt survives restart");
 for(double k:{.01,1.0,100.0}){reset();fixtureFailed(u"FX");scaleFixture(u"FX",k);SymbolState a;setup(a);check(a.DetectBullishFailedBreakout(p)&&near(p.patternStrength,full),"failed breakout ATR scale invariance");}
}
PatternSignal syntheticPattern(ENUM_PATTERN_TYPE type,bool buy,double score,datetime pivot){
 auto p=pattern();p.type=type;p.buySignal=buy;p.sellSignal=!buy;p.patternStrength=score;
 p.firstTime=pivot-120;p.headTime=pivot-60;p.secondTime=pivot;p.referenceTime=pivot;
 p.triggerTime=iTime(u"FX",PERIOD_M1,1);p.referencePrice=100;return p;
}
void checkCompetition(){
 reset();fixture123(u"FX",true,98,102,98);SymbolState s;setup(s);std::vector<PatternSignal> pool;PatternSignal selected;
 s.GatherPatterns(pool);bool d=false,t=false;for(auto&p:pool){d|=p.type==PATTERN_DOUBLE_BOTTOM;t|=p.type==PATTERN_BULLISH_123;}
 check(d&&t,"Double and 123 real OHLC simultaneous detection");
 check(s.ChoosePattern(pool,true,true,selected)&&selected.type==PATTERN_BULLISH_123,"highest pattern score wins real Double plus 123");
 check(s.ExecuteEntry(true,91,selected),"one selected pattern may execute");s.ExecuteEntry(true,91,selected);check(order_calls==1,"coincident patterns never multiply orders within one M1");
 for(auto &p:pool)check(s.IsPatternAlreadyUsed(p),"all same direction coincident structures consumed");
 for(int which=0;which<2;which++){
  reset();SymbolState a;setup(a);std::vector<PatternSignal> candidates;
  candidates.push_back(syntheticPattern(which==0?PATTERN_TRIPLE_BOTTOM:PATTERN_BULLISH_123,true,80,server_time-600));
  candidates.push_back(syntheticPattern(PATTERN_BULLISH_FAILED_BREAKOUT,true,90,server_time-900));
  check(a.ChoosePattern(candidates,true,true,selected)&&selected.type==PATTERN_BULLISH_FAILED_BREAKOUT,"Triple or 123 plus Failed Breakout selects highest score");
  check(a.PersistPatternClaims(selected)&&a.IsPatternAlreadyUsed(candidates[0])&&a.IsPatternAlreadyUsed(candidates[1]),"competition receipt consumes winner and supporting structure");
 }
 reset();SymbolState a;setup(a);pool={syntheticPattern(PATTERN_BULLISH_123,true,80,server_time-600),syntheticPattern(PATTERN_BEARISH_FAILED_BREAKOUT,false,99,server_time-900)};
 check(!a.ChoosePattern(pool,true,true,selected),"opposite patterns with ambiguous direction rejected");
 check(a.ChoosePattern(pool,true,false,selected)&&selected.buySignal,"MTF-qualified direction precedes higher opposing pattern score");
 pool[0].patternStrength=120;check(a.ChoosePattern(pool,true,false,selected)&&selected.patternStrength==100,"pattern score capped at 100");
}
void checkFinalWeights(){
 reset();double weights[][3]={{80,15,5},{85,10,5},{75,20,5}};double expected[]={77,77.5,76.5};
 for(int i=0;i<3;i++){FinalMTFWeight=weights[i][0];FinalPatternWeight=weights[i][1];FinalLineWeight=weights[i][2];
  check(ValidateFinalWeights()&&near(FinalSignalScore(80,70,10),expected[i]),"requested final ratio arithmetic");
  check(near(FinalSignalScore(100,100,20),100)&&FinalSignalScore(200,120,30)==100,"all scores normalized before weighting");
 }
 double invalid[][3]={{80,15,4},{80,15,6},{-1,96,5},{101,0,0}};
 for(auto &w:invalid){FinalMTFWeight=w[0];FinalPatternWeight=w[1];FinalLineWeight=w[2];check(OnInit()==INIT_PARAMETERS_INCORRECT,"invalid final weights reject OnInit");check(FinalMTFWeight==w[0]&&FinalPatternWeight==w[1]&&FinalLineWeight==w[2],"input weights never auto normalized");}
 FinalMTFWeight=80;FinalPatternWeight=15;FinalLineWeight=5.0005;check(ValidateFinalWeights(),"floating tolerance accepted");
 FinalLineWeight=5.002;check(!ValidateFinalWeights(),"outside floating tolerance rejected");
 FinalLineWeight=5;FinalMTFWeight=std::numeric_limits<double>::quiet_NaN();check(!ValidateFinalWeights(),"nonfinite weight rejected");
 FinalMTFWeight=80;check(FinalSignalScore(-1,-2,-3)==0,"negative source score normalized to zero");
}
void checkNewSymbolAndAI(){
 reset();fixture123(u"FX");fixture123(u"GOLD");SymbolState a,b;setup(a);setup(b,u"GOLD");PatternSignal p,q;
 check(a.DetectBullish123(p)&&b.DetectBullish123(q)&&p.patternId!=q.patternId,"123 IDs scoped by symbol");
 a.PersistPatternClaims(p);check(a.IsPatternAlreadyUsed(p)&&!b.IsPatternAlreadyUsed(q),"123 receipt does not cross symbols");
 reset();fixtureFailed(u"FX");fixtureFailed(u"GOLD");SymbolState c,d;setup(c);setup(d,u"GOLD");
 check(c.DetectBullishFailedBreakout(p)&&d.DetectBullishFailedBreakout(q)&&p.patternId!=q.patternId,"failed breakout IDs scoped by symbol");
 c.PersistPatternClaims(p);check(c.IsPatternAlreadyUsed(p)&&!d.IsPatternAlreadyUsed(q),"failed breakout receipt does not cross symbols");
 reset();ExecutionMode=EXECUTION_HYBRID;fixture123(u"FX");fixtureFailed(u"GOLD");OnInit();worker_start();reply_fixture();
 for(auto s:g_symbols){s->Maintain(true);s->RefreshCandidate();}
 int aidx=FindSymbolState(u"FX"),bidx=FindSymbolState(u"GOLD");
 check(g_symbols[aidx]->m_candidate&&g_symbols[bidx]->m_candidate,"both new patterns qualify before shared AI queue");
 DispatchQueue();int active=g_symbols[aidx]->g_aiRequest.active?aidx:bidx;check(g_symbols[active]->g_aiRequest.active,"new-pattern AI queue starts only one request");
 auto first=g_symbols[active]->g_aiRequest.pattern;deliver_worker();g_symbols[active]->ProcessAIReply();check(order_calls==1,"first new pattern HYBRID approved");
 DispatchQueue();int second=active==aidx?bidx:aidx;check(g_symbols[second]->g_aiRequest.active,"shared worker next symbol processed");
 deliver_worker();g_symbols[second]->ProcessAIReply();check(order_calls==2,"independent new pattern symbols both complete");
 check(StringFind(last_http_body,u"FAILED_BREAKOUT")>=0||StringFind(last_http_body,u"123_REVERSAL")>=0,"AI snapshot identifies added pattern");OnDeinit(0);
 reset();fixture123(u"FX");SymbolState fail;setup(fail);fail.DetectBullish123(p);fail_global=fail.PatternReceiptKey(p.patternId);
 fail.ExecuteEntry(true,91,p);check(order_calls==0,"receipt write failure blocks broker send");
 reset();fixtureFailed(u"FX");SymbolState price;setup(price);price.DetectBullishFailedBreakout(p);symbols[u"FX"].bid=100.8;symbols[u"FX"].ask=100.82;symbols[u"FX"].tickMs++;
 check(!price.RefreshCandidate()&&order_calls==0,"failed breakout live quote too far from reference rejected");
}
void checkOHLCCombinations(){
 for(int which=0;which<2;which++){
  reset();ScanMode=CURRENT_SYMBOL;Series r;
  r.high.assign(200,100.4);r.low.assign(200,100.3);r.close.assign(200,100.35);r.open=r.close;
  if(which==0){for(int n:{12,24,36})r.low[n]=100;r.high[18]=r.high[30]=100.44;}
  else {r.low[36]=98;r.high[24]=100.5;r.low[12]=100.05;r.low[2]=99.75;}
  r.low[2]=which==0?99.7:99.75;r.high[2]=100.2;r.close[2]=99.9;r.open[2]=100.1;
  r.low[1]=99.9;r.high[1]=100.8;r.close[1]=which==0?100.68:100.72;r.open[1]=99.9;
  series[u"FX"]=r;symbols[u"FX"].bid=r.close[1];symbols[u"FX"].ask=r.close[1]+.02;
  check(OnInit()==INIT_SUCCEEDED,"real coincident pattern AUTO controller init");SymbolState &a=*g_symbols[0];
  std::vector<PatternSignal> pool;check(a.GatherPatterns(pool),"real simultaneous pattern collection complete");
  bool structure=false,failed=false;for(auto &p:pool){structure|=p.type==(which==0?PATTERN_TRIPLE_BOTTOM:PATTERN_BULLISH_123);failed|=p.type==PATTERN_BULLISH_FAILED_BREAKOUT;}
  check(structure&&failed,which==0?"Triple plus Failed Breakout real closed OHLC":"123 plus Failed Breakout real closed OHLC");
  OnTimer();OnTimer();check(order_calls==1,"coincident real structures execute once through AUTO timer");
  bool consumed=true;for(auto &p:pool)consumed&=a.IsPatternAlreadyUsed(p);check(consumed,"all real coincident structures cannot be reused after AUTO attempt");OnDeinit(0);
 }
}
void checkPatternAllocation(){
 reset();fixture123(u"FX",true,98,102,98);SymbolState s;setup(s);PatternSignal p;
 pattern_array_failure_at=2;check(!s.DetectReversalPattern(p)&&!p.valid,"incomplete pattern collection fails closed on allocation failure");
 pattern_array_failure_at=-1;check(s.DetectReversalPattern(p),"complete pattern collection recovers after allocation failure");
}
void v243_tests(){
 check123();checkFailed();checkCompetition();checkFinalWeights();checkNewSymbolAndAI();checkPatternAllocation();checkOHLCCombinations();
}

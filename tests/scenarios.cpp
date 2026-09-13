int checks=0;
void check(bool value,const char*name){if(!value){std::cerr<<"FAIL: "<<name<<"\n";std::exit(1);}checks++;}
bool MockDurableIntent(string s,ulong magic){return magic==MagicNumber && AIState(SymbolPrefix(s)+u"ord.state")>0 && AIState(AccountIntent(s))>0;}
bool near(double a,double b,double e=1e-8){return std::abs(a-b)<=e;}
void reset(){
 if(!g_symbols.empty())OnDeinit(0);
 globals.clear();symbols.clear();indicators.clear();series.clear();positions.clear();active_orders.clear();history_orders.clear();history_deals.clear();
 files.clear();open_files.clear();events.clear();objects.clear();hist_order_view.clear();hist_deal_view.clear();
 mono=100000;server_time=1700000041;chart_id=1;tester=false;permissions=connected=history_ok=queue_ok=file_ok=true;
 fail_global=u"";order_calls=http_calls=modify_calls=close_calls=chart_operations=0;ordercheck_advance=0;broker_retcode=TRADE_RETCODE_DONE;
 fill_visible=position_visible=true;deal_only=false;during_http={};during_ordercheck={};http_code=200;
 margin_mode=ACCOUNT_MARGIN_MODE_RETAIL_HEDGING;equity=balance=free_margin=100000;
 symbols[u"FX"]=MockSymbol{};symbols[u"GOLD"]=MockSymbol{};
 RiskMode=RISK_FIXED_ADJUST;AccountMode=NORMAL;ExecutionMode=EXECUTION_AUTO;UseSwingStopLoss=false;
 ScanMode=MARKET_WATCH;CustomSymbols=u"";EnableTradingViewTheme=false;EnableAutoTrading=EnableManualTrading=true;OneEntryPerBar=OnePositionPerSymbol=true;
 EnableOpenAI=true;OpenAIFailOpen=false;ReconciledOrderToken=u"";OpenAIMinConfidence=.7;MinimumSignalScore=70;MinimumWeightedAgreement=55;
 FinalMTFWeight=80;FinalPatternWeight=15;FinalLineWeight=5;
 EnablePortfolioRiskLimit=true;MaxPortfolioRiskPercent=3;EnableTradeLog=true;g_logRun=u"";g_journalCursor=0;fail_file_pattern=u"";profit_ok=true;log_warning_count=0;
 BaseRiskPercent=.5;MaximumRiskPercent=1;MinimumRiskPercent=.1;RiskAfter2Loss=.4;RiskAfter3Loss=.3;RiskAfter4Loss=.2;RiskAfter5Loss=.1;
 MaxSpreadATR=.1;MaxSpreadSL=.15;MaxSpreadPoints=SlippagePoints=StopSlippageBufferPoints=0;SLBufferPoints=0;
 MaxQuoteAgeMs=OpenAIMaxQuoteAgeMs=3000;OpenAIMaxDecisionAgeMs=10000;OpenAIMaxPriceDriftPoints=0;OpenAIMaxPriceDriftATR=.1;
 EntryDirection=ENTRY_BOTH;StopAfterConsecutiveLosses=6;LossStreakResetTime=0;EnableTripleBottom=EnableTripleTop=true;
 EnableAutoHorizontalLines=EnableAutoTrendLines=true;MinimumSLImprovementPoints=0;ManualInitialSL=0;
 g_account=u"MOCK_SERVER/123456";g_chartSymbol=u"FX";g_accountPrefix=u"MT3A."+ScopeDigest(g_account)+u".";g_execKey=u"MT3EXEC."+ScopeDigest(g_account);
 g_execOwned=g_propControllerOwned=false;g_accountHistoryOK=true;g_accountHistoryDirty=true;g_accountHistoryAt=0;g_accountLossStreak=0;
 g_queueSequence=0;g_scanCursor=g_mcCursor=0;g_universeAt=0;
 g_workerOwned=false;g_workerRegistry=u"";g_cleanupFiles.clear();g_cleanupTimes.clear();g_observedSlot=0;g_slotObservedAt=0;
 ResetLastError();
}
void setup(SymbolState &s,string symbol=u"FX",bool chart=false){check(s.Init(symbol,chart,true),"symbol init");s.Maintain(true);}
PatternSignal pattern(){PatternSignal p{};p.type=PATTERN_TRIPLE_BOTTOM;p.valid=true;p.buySignal=true;p.secondTime=server_time-600;p.patternStrength=70;return p;}
void newbar(){server_time+=60;mono+=60000;for(auto&[k,v]:symbols)v.tickMs=server_time*1000;}
void worker_start(){chart_id=2;OpenAIAPIKey=u"FAKE_OFFLINE_TEST_KEY";check(WorkerInit()==INIT_SUCCEEDED,"worker init");chart_id=1;}
void deliver_worker(){for(size_t i=0;i<events.size();i++)if(events[i].dest==2){auto e=events[i];events.erase(events.begin()+i);chart_id=2;WorkerEvent(CHARTEVENT_CUSTOM+e.event,e.sender,e.token,e.id);chart_id=1;return;}}
void reply_fixture(string decision=u"BUY",double confidence=.91){
 string payload=u"{\"decision\":"+JsonQuote(decision)+u",\"confidence\":"+StringFormat(u"%.17g",confidence)+u",\"reason\":\"offline\"}";
 http_fixture=u"{\"status\":\"completed\",\"error\":null,\"output\":[{\"type\":\"message\",\"status\":\"completed\",\"role\":\"assistant\",\"content\":[{\"type\":\"output_text\",\"text\":"+JsonQuote(payload)+u"}]}]}";
}
void inject_reply(SymbolState&s,string status=u"ok",string decision=u"BUY",double confidence=.91,string id=u""){
 if(id.empty())id=s.g_aiRequest.id;
 string text=u"{\"protocol\":242,\"id\":"+JsonQuote(id)+u",\"chart\":\"1\",\"status\":"+JsonQuote(status)+u",\"decision\":"+JsonQuote(decision)+u",\"confidence\":"+StringFormat(u"%.17g",confidence)+u",\"reason\":\"offline\"}";
 WriteAIFile(AIFile(s.g_aiRequest.id,u".res"),text);
}
bool request(SymbolState&s){s.RefreshCandidate();return s.DispatchCandidate();}
void closed_trade(ulong id,string symbol,double net,datetime time,bool mixed=false){
 MockDeal in;in.id=id*2;in.order=id;in.position=id;in.symbol=symbol;in.time=time-60;history_deals[in.id]=in;
 MockDeal out=in;out.id++;out.entry=DEAL_ENTRY_OUT;out.magic=0;out.time=time;out.profit=net;history_deals[out.id]=out;
 if(mixed)history_deals[in.id].magic=987;
}
void fixture_pattern(string symbol,bool bottom=true,bool head=false){
 Series r;r.high.assign(180,101);r.low.assign(180,100);r.close.assign(180,100.5);
 if(bottom){for(int k:{6,18,30})r.low[k]=99;r.close[1]=101.4;r.close[2]=101;if(head)r.low[18]=97;symbols[symbol].bid=101.5;symbols[symbol].ask=101.52;}
 else{for(int k:{6,18,30})r.high[k]=103;r.close[1]=99.6;r.close[2]=100;if(head)r.high[18]=105;symbols[symbol].bid=99.5;symbols[symbol].ask=99.52;}
 series[symbol]=r;
}
void scoring_tests(){
 reset();SymbolState a,b;setup(a);setup(b,u"GOLD");
 std::vector<MTFResult> r;check(a.AnalyzeAllTimeframes(r),"seven indicators complete");
 double w=0;int weights[]={20,25,22,15,10,5,3};for(int i=0;i<7;i++){check(MT3Weight(MT3Timeframe(i))==weights[i],"specified frame weight");w+=weights[i];}
 check(w==100,"weights total 100");check(near(r[0].totalScore,r[0].trendScore*.7+r[0].macdScore*.3),"trend MACD 70/30");
 for(int i=0;i<7;i++){int f,s,g;MACDParameters(MT3Timeframe(i),f,s,g);check(i<2?(f==8&&s==21&&g==5):(f==12&&s==26&&g==9),"per timeframe MACD defaults");}
 check(a.g_indicators[0].handle!=b.CachedIndicator(0,PERIOD_M1,14),"independent indicator handles");
 MTFResult scaled=r[0];double *vals[]={&scaled.atr,&scaled.close,&scaled.emaFast,&scaled.emaMiddle,&scaled.emaSlow,&scaled.previousFast,&scaled.previousMiddle,&scaled.previousSlow,&scaled.macdMain,&scaled.macdSignal,&scaled.macdHistogram,&scaled.previousHistogram};
 for(auto p:vals)*p*=10000;ScoreEvidence(scaled);check(near(scaled.trendScore,r[0].trendScore,1e-7)&&near(scaled.macdScore,r[0].macdScore,1e-7),"ATR scale invariance");
 check(near(ADXStrength(15),.25)&&near(ADXStrength(20),.45)&&near(ADXStrength(25),.65)&&near(ADXStrength(35),1),"continuous ADX knots");
 check(ADXStrength(24.99)<ADXStrength(25.01)&&ADXStrength(25.01)-ADXStrength(24.99)<.001,"no ADX25 jump gate");
 for(auto &v:r){v.trendDirection=0;v.trendScore=0;v.macdScore=0;v.macdHistogram=0;v.totalScore=0;}
 r[0].trendDirection=r[1].trendDirection=r[4].trendDirection=1;
 check(WeightedAgreement(r,true)==55&&WeightedSignalOK(r,true),"55 percent boundary inclusive with three frames");
 r[4].trendDirection=0;check(!WeightedSignalOK(r,true),"below weighted threshold rejected");
 r[4].trendDirection=1;r[6].trendDirection=-1;r[6].trendScore=-100;r[6].minusDI=99;
 check(WeightedSignalOK(r,true),"D1 alone cannot veto");
 for(int i:{4,5}){r[i].trendScore=-60;r[i].adx=30;r[i].plusDI=5;r[i].minusDI=30;}
 check(StrongHigherOpposition(r,true),"H1 and H4 strong opposite veto");r[5].trendScore=-40;check(!StrongHigherOpposition(r,true),"one strong higher frame not veto");
 for(int i=0;i<2;i++){r[i].macdScore=-60;r[i].macdHistogram=-.05*r[i].atr;}
 check(StrongFastMACDOpposition(r,true),"both fast MACD strong opposite");r[1].macdScore=-30;check(!StrongFastMACDOpposition(r,true),"single fast MACD not hard gate");
 r[6].timeframe=PERIOD_H4;check(!CompleteMTF(r),"duplicate frame rejected");
 check(DirectionalScore(0,true)==50&&DirectionalScore(0,false)==50,"neutral directional score");
 symbols[u"FX"].ready=false;a.ReleaseIndicators();check(!a.AnalyzeAllTimeframes(r),"missing history cannot renormalize weights");
}
void pattern_tests(){
 reset();SymbolState s;setup(s);PatternSignal p;
 fixture_pattern(u"FX");check(s.DetectTripleBottom(p)&&p.type==PATTERN_TRIPLE_BOTTOM,"triple bottom neckline");
 check(s.DetectDoubleBottom(p),"double bottom retained");check(s.DetectLegacyReversalPattern(p)&&p.type==PATTERN_TRIPLE_BOTTOM,"legacy triple routing priority retained");
 series[u"FX"].close[2]=101.5;check(!s.DetectTripleBottom(p),"old breakout rejected");
 fixture_pattern(u"FX",false);check(s.DetectTripleTop(p)&&p.type==PATTERN_TRIPLE_TOP,"triple top neckline");check(s.DetectDoubleTop(p),"double top retained");
 fixture_pattern(u"FX",true,true);check(s.DetectInverseHeadShoulders(p),"inverse head shoulders retained");
 fixture_pattern(u"FX",false,true);check(s.DetectHeadShoulders(p),"head shoulders retained");
}
void adaptive_tests(){
 reset();SymbolState a,b;setup(a);setup(b,u"GOLD");MqlTick t;
 check(a.g_statePrefix!=b.g_statePrefix&&a.m_symbol!=b.m_symbol,"symbol state namespace isolation");
 a.m_lastCloseAttempt=server_time;check(b.m_lastCloseAttempt==0,"DD retry clock isolated");
 a.StoreLevel(a.LINE_PREFIX+u"HLINE_SUP_0",99);b.StoreLevel(b.LINE_PREFIX+u"HLINE_SUP_0",50);
 check(a.GetNearestSupportDistance(100)==1&&b.GetNearestSupportDistance(100)==50,"virtual support independent");
 int before=chart_operations;a.UpdateAllAutoLines();check(chart_operations==before,"off-chart lines do not mutate host chart");
 check(a.FreshQuote(t),"fresh symbol tick");mono+=3001;check(!a.FreshQuote(t),"polling unchanged quote stays stale");
 symbols[u"FX"].tickMs++;check(a.FreshQuote(t),"new tick renews receipt time");
 symbols[u"FX"].tickMs=server_time*1000-4000;check(!a.FreshQuote(t),"server timestamp stale");
 symbols[u"FX"].tickMs=server_time*1000;symbols[u"FX"].ask=100.2;a.FreshQuote(t);
 check(a.SpreadOK(t,98,true),"spread ATR10 percent inclusive");symbols[u"FX"].ask=100.201;a.FreshQuote(t);check(!a.SpreadOK(t,98,true),"spread ATR excess");
 symbols[u"FX"].ask=100.1;a.FreshQuote(t);check(!a.SpreadOK(t,99.6,true),"spread SL15 percent rejects expensive tight stop");
 symbols[u"FX"].ask=100.02;a.FreshQuote(t);check(near(a.StopBuffer(),.1),"ATR stop buffer floor");symbols[u"FX"].stops=20;check(a.StopBuffer()>=.21,"broker stops buffer floor");
 symbols[u"FX"].stops=0;symbols[u"FX"].volumeLimit=1;positions[9]={9,987,u"FX",POSITION_TYPE_BUY,.8,100,98,102};
 check(near(a.AvailableDirectionalVolume(true),.2),"volume limit includes other owners");
 double lots=a.CalculateLotByRisk(true,t,98,.5);check(lots<=.2+1e-8&&lots>0,"lot sizing observes directional limit");
 OnePositionPerSymbol=false;check(!a.EntryExposureBlocked(),"hedging option permits additional positions");margin_mode=ACCOUNT_MARGIN_MODE_RETAIL_NETTING;check(a.EntryExposureBlocked(),"netting blocks merge into any owner");
 positions.clear();symbols[u"FX"].volumeLimit=0;
 for(auto label:{u"FX",u"GOLD",u"INDEX",u"OIL",u"CRYPTO"}){
  string name=label;MockSymbol spec;double scale=name==u"FX"?1:name==u"GOLD"?20:name==u"INDEX"?50:name==u"OIL"?.7:500;
  spec.bid=100*scale;spec.ask=spec.bid+.02*scale;spec.atr=2*scale;spec.point=spec.tick=.01*scale;spec.contract=1000/scale;spec.tickMs=server_time*1000;
  symbols[name]=spec;SymbolState s;if(name==u"FX"||name==u"GOLD"){GlobalVariableSet(a.g_lockKey,0);GlobalVariableSet(b.g_lockKey,0);}setup(s,name);
  s.FreshQuote(t);double lot=s.CalculateLotByRisk(true,t,spec.bid-2*scale,.5);double profit=0;
  OrderCalcProfit(ORDER_TYPE_BUY,name,lot,t.ask+s.DeviationPoints()*s.m_point,spec.bid-2*scale-s.StopSlippage(),profit);
  check(lot>0&&std::abs(profit)<=500+1e-7,"cross asset account currency risk bound");s.Shutdown();
 }
}
void order_tests(){
 for(int mode:{EXECUTION_AUTO,EXECUTION_MANUAL,EXECUTION_AI,EXECUTION_HYBRID}){
  reset();ExecutionMode=(ENUM_EXECUTION_MODE)mode;SymbolState a,b;setup(a);setup(b,u"GOLD");auto p=pattern();broker_retcode=TRADE_RETCODE_TIMEOUT;
  a.ExecuteEntry(true,91,p,mode==EXECUTION_MANUAL,98);
  check(order_calls==1&&a.HasUnresolvedOrder(),"all modes persist timeout intent");
  b.ExecuteEntry(true,91,p,mode==EXECUTION_MANUAL,98);check(order_calls==1,"unresolved symbol blocks another symbol");
  newbar();a.ExecuteEntry(true,91,p,mode==EXECUTION_MANUAL,98);check(order_calls==1,"new M1 cannot retry unresolved order");
 }
 reset();SymbolState a;setup(a);auto p=pattern();broker_retcode=TRADE_RETCODE_REJECT;a.ExecuteEntry(true,91,p);
 check(!a.HasUnresolvedOrder()&&!AnyAccountUnresolved(),"definite reject releases account intent");
 a.ExecuteEntry(true,91,p);check(order_calls==1,"definite reject still one attempt per bar");
 reset();SymbolState b;setup(b);p=pattern();position_visible=false;b.ExecuteEntry(true,91,p);
 check(b.HasUnresolvedOrder(),"filled order before position keeps reservation");
 ulong id=last_result.order;positions[id]={id,MagicNumber,u"FX",POSITION_TYPE_BUY,.1,100,98,102};b.ReconcilePendingOrder();check(!b.HasUnresolvedOrder(),"visible position resolves fill");
 reset();SymbolState c;setup(c);p=pattern();broker_retcode=TRADE_RETCODE_CONNECTION;c.ExecuteEntry(true,91,p);
 string token=c.PendingOrderToken();c.Shutdown();SymbolState restored;setup(restored);check(restored.HasUnresolvedOrder()&&restored.PendingOrderToken()==token,"restart retains unresolved identity");
 ReconciledOrderToken=u"WRONG";restored.ReconcilePendingOrder();check(restored.HasUnresolvedOrder(),"wrong reconciliation token ignored");
 ReconciledOrderToken=token;restored.ReconcilePendingOrder();check(!restored.HasUnresolvedOrder()&&!AnyAccountUnresolved(),"exact reconciliation token releases");
 newbar();p.secondTime-=60;restored.ExecuteEntry(true,91,p);check(restored.PendingOrderToken()!=token,"new intent uses new one-use token");restored.ReconcilePendingOrder();check(restored.HasUnresolvedOrder(),"old token cannot release new uncertainty");
 reset();SymbolState d;setup(d);p=pattern();GlobalVariableTemp(g_execKey);GlobalVariableSet(g_execKey,1);d.ExecuteEntry(true,91,p);check(order_calls==0,"account mutex blocks competing execution");
 GlobalVariableSet(g_execKey,0);fail_global=AccountIntent(u"FX");d.ExecuteEntry(true,91,p);check(order_calls==0,"intent persistence failure prevents send");
 reset();SymbolState e;setup(e);p=pattern();broker_retcode=TRADE_RETCODE_PLACED;e.ExecuteEntry(true,91,p);check(e.HasUnresolvedOrder()&&OrdersTotal()==1,"placed order remains unresolved");
 reset();SymbolState f;setup(f);p=pattern();deal_only=true;f.ExecuteEntry(true,91,p);check(!f.HasUnresolvedOrder(),"deal-only response reconciles exact parent order");
 reset();string legacy=u"MT3."+IntegerToString((long)TextHash(SymbolScope(u"FX")))+u".";
 GlobalVariableSet(legacy+u"bar",777);GlobalVariableSet(legacy+u"manual.sl",98);SymbolState m;setup(m);
 check(m.g_lastTradeBar==777&&AIState(m.g_statePrefix+u"manual.sl")==98,"v241 persistent state migration");
}
void ai_tests(){
 reset();ExecutionMode=EXECUTION_AI;SymbolState a,b;setup(a);setup(b,u"GOLD");worker_start();reply_fixture();
 check(request(a)&&a.g_aiRequest.active&&http_calls==0,"main queues qualifying candidate without HTTP");
 check(!request(b)&&!b.g_aiRequest.active,"one worker slot shared by symbols");
 deliver_worker();check(http_calls==1,"worker alone executes HTTP mock");a.ProcessAIReply();check(order_calls==1&&positions.begin()->second.symbol==u"FX","AI response executes originating symbol");a.ProcessAIReply();check(order_calls==1,"duplicate reply cannot replay");
 reset();ExecutionMode=EXECUTION_AI;SymbolState weak;setup(weak);worker_start();MinimumSignalScore=100;
 check(!request(weak)&&events.empty()&&http_calls==0,"below minimum local score never reaches AI");
 reset();ExecutionMode=EXECUTION_AI;SymbolState cancel,other;setup(cancel);setup(other,u"GOLD");worker_start();reply_fixture();request(cancel);
 bool busyProtected=false;during_http=[&](){cancel.CancelAIRequest();busyProtected=!request(other)&&AIState(AIRegistry()+u"slot")>0;};deliver_worker();during_http={};
 check(busyProtected&&AIState(AIRegistry()+u"slot")==0,"cancel during HTTP retains slot until worker completion");check(order_calls==0&&!cancel.g_aiRequest.active,"cancelled response cannot execute");
 for(int failure=0;failure<8;failure++){
  reset();ExecutionMode=EXECUTION_AI;SymbolState s;setup(s);worker_start();check(request(s),"fresh AI request fixture");inject_reply(s);
  if(failure==0)newbar();
  if(failure==1)mono+=OpenAIMaxDecisionAgeMs;
  if(failure==2)symbols[u"FX"].tickMs-=4000;
  if(failure==3){symbols[u"FX"].bid+=.3;symbols[u"FX"].ask+=.3;symbols[u"FX"].tickMs++;}
  if(failure==4)inject_reply(s,u"ok",u"BUY",.91,u"WRONG");
  if(failure==5)inject_reply(s,u"ok",u"SELL");
  if(failure==6)symbols[u"FX"].visible=false;
  if(failure==7)ordercheck_advance=10001;
  s.ProcessAIReply();check(order_calls==0,"AI age/bar/quote/drift/id/direction/universe/preparation guards");
 }
 reset();ExecutionMode=EXECUTION_AI;SymbolState prec;setup(prec);worker_start();reply_fixture(u"BUY",.699999999);request(prec);deliver_worker();prec.ProcessAIReply();check(order_calls==0,"confidence below .70 not rounded up by worker");
 reset();ExecutionMode=EXECUTION_AI;OpenAIFailOpen=true;SymbolState nofallback;setup(nofallback);worker_start();request(nofallback);inject_reply(nofallback,u"transport_error",u"WAIT",0);nofallback.ProcessAIReply();check(order_calls==0,"AI-only fail open prohibited");
 reset();ExecutionMode=EXECUTION_HYBRID;OpenAIFailOpen=true;fixture_pattern(u"FX");SymbolState hybrid;setup(hybrid);worker_start();check(request(hybrid),"hybrid local pattern candidate");inject_reply(hybrid,u"transport_error",u"WAIT",0);hybrid.ProcessAIReply();check(order_calls==1,"explicit HYBRID transport fallback preserves local checks");
 reset();ExecutionMode=EXECUTION_HYBRID;OpenAIFailOpen=true;fixture_pattern(u"FX");SymbolState invalid;setup(invalid);worker_start();request(invalid);inject_reply(invalid,u"invalid",u"WAIT",0);invalid.ProcessAIReply();check(order_calls==0,"invalid response never fail-opens");
 reset();ExecutionMode=EXECUTION_AI;SymbolState old;setup(old);worker_start();GlobalVariableSet(AIRegistry()+u"version",241);check(!request(old),"old worker protocol rejected");
}
void scanner_tests(){
 reset();symbols[u"GOLD"].visible=false;check(OnInit()==INIT_SUCCEEDED,"market watch controller init");check(g_symbols.size()==1,"market watch visible symbols only");OnDeinit(0);
 reset();ScanMode=CUSTOM_LIST;CustomSymbols=u" FX ; GOLD,FX\nMISSING";check(OnInit()==INIT_SUCCEEDED&&g_symbols.size()==2,"custom delimiters exact names deduplicated");
 OnTimer();check(g_symbols[1]->g_historyOK,"timer scans off-chart symbol without OnTick");OnDeinit(0);
 reset();ScanMode=CURRENT_SYMBOL;OnInit();check(g_symbols.size()==1&&g_symbols[0]->m_scanEnabled,"current symbol mode");OnDeinit(0);
 reset();ScanMode=ALL_TRADABLE_SYMBOLS;symbols[u"GOLD"].visible=false;symbols[u"OFF"]=MockSymbol{};symbols[u"OFF"].mode=SYMBOL_TRADE_MODE_DISABLED;
 OnInit();check(g_symbols.size()==2,"all tradable discovers off-watch and skips disabled");OnDeinit(0);
 reset();ExecutionMode=EXECUTION_AI;OnInit();OnTimer();worker_start();
 for(auto s:g_symbols)s->RefreshCandidate();g_symbols[0]->m_candidateScore=75;g_symbols[1]->m_candidateScore=90;DispatchQueue();
 check(g_symbols[1]->g_aiRequest.active&&!g_symbols[0]->g_aiRequest.active,"higher score candidate dispatched first");
 g_symbols[1]->SetScanEnabled(false);check(!g_symbols[1]->g_aiRequest.active,"retirement cancels pending AI");OnDeinit(0);
 reset();tester=true;check(OnInit()==INIT_SUCCEEDED,"AUTO tester permitted");OnDeinit(0);ExecutionMode=EXECUTION_AI;check(OnInit()==INIT_PARAMETERS_INCORRECT,"AI tester refused explicitly");
 reset();fixture_pattern(u"FX");OnInit();OnTimer();check(order_calls==1,"AUTO candidate trades from timer path");OnTimer();check(order_calls==1,"AUTO duplicate timer does not duplicate entry");OnDeinit(0);
}
void risk_tests(){
 reset();SymbolState a,b;setup(a);setup(b,u"GOLD");
 a.g_consecutiveLosses=3;check(near(a.CalculateFixedAdjustedRisk(91),.3)&&near(b.CalculateFixedAdjustedRisk(91),.5),"loss streak sizing isolated");
 a.g_consecutiveLosses=6;check(a.CalculateFixedAdjustedRisk(91)==0,"fixed loss stop retained");
 closed_trade(1,u"FX",-10,server_time-200);closed_trade(2,u"GOLD",-10,server_time-100);
 AccountMode=FINTOKEI;RefreshAccountHistory(true);check(g_accountHistoryOK&&g_accountLossStreak==2,"prop loss streak aggregates all owned symbols and manual exits");
 closed_trade(3,u"FX",10,server_time-10);RefreshAccountHistory(true);check(g_accountLossStreak==0,"account win resets aggregate streak");
 FintokeiInitialBalance=100000;FintokeiDailyReference=100000;FintokeiReferenceDateUTC=server_time;equity=90000;
 positions[10]={10,MagicNumber,u"FX",POSITION_TYPE_BUY,.1,100,98,102};positions[11]={11,MagicNumber,u"GOLD",POSITION_TYPE_BUY,.1,100,98,102};
 a.UpdatePropProtection();b.UpdatePropProtection();check(close_calls==2&&positions.empty(),"DD closes both symbols during same server second");
 reset();SymbolState trail;setup(trail);positions[10]={10,MagicNumber,u"FX",POSITION_TYPE_BUY,.1,98,96,105};
 GlobalVariableSet(trail.PositionKey(10,u".r"),2);trail.ManagePositions();check(modify_calls==1&&positions[10].sl>98,"BE and trailing improve SL using initial risk");
 double sl=positions[10].sl;symbols[u"FX"].bid=99.8;symbols[u"FX"].ask=99.82;symbols[u"FX"].tickMs++;trail.ManagePositions();check(positions[10].sl>=sl,"trailing never loosens existing SL");
 margin_mode=ACCOUNT_MARGIN_MODE_RETAIL_NETTING;MockDeal own;own.id=100;own.position=10;own.symbol=u"FX";own.time=server_time;history_deals[100]=own;MockDeal foreign=own;foreign.id=101;foreign.magic=999;history_deals[101]=foreign;
 check(!trail.SolePositionOwner(10),"mixed netting ownership cannot be managed as ours");
 reset();RiskMode=RISK_MONTE_CARLO;MonteCarloRuns=200;MonteCarloTrades=50;MonteCarloMaxDrawdownPercent=10;MonteCarloSafetyFactor=.8;MonteCarloRiskStep=.05;
 SymbolState m,n;setup(m);setup(n,u"GOLD");m.g_returns.assign(40,-1);n.g_returns=m.g_returns;
 m.g_sampleCount=n.g_sampleCount=40;m.g_winRate=n.g_winRate=.5;m.g_historyDirty=n.g_historyDirty=false;
 m.UpdateMonteCarloRisk(true);n.UpdateMonteCarloRisk(true);check(m.m_mcActive&&!m.g_mcReady,"MC calculation incremental and blocks that symbol until ready");
 m.g_returns[0]=99;check(m.m_mcReturns[0]==-1,"MC job uses immutable returns snapshot");
 for(int i=0;i<200 && (m.m_mcActive||n.m_mcActive);i++){m.AdvanceMonteCarlo(mono+1);n.AdvanceMonteCarlo(mono+1);}
 check(m.g_mcReady&&n.g_mcReady&&near(m.g_mcRisk,n.g_mcRisk)&&m.g_mcRisk>0,"MC jobs deterministic across symbols/interleaving");
 m.UpdateMonteCarloRisk(true);m.g_historyDirty=true;int run=m.m_mcRun;m.AdvanceMonteCarlo(mono+1);check(m.m_mcRun==run,"dirty history pauses old MC job");
}
void tester_connection_tests(){
 // A tester has no live broker connection requirement. Keep the two mocked
 // terminal properties independent so both tester and live paths are exercised.
 struct ConnectionCase {bool testing;bool online;bool allowed;const char *name;};
 ConnectionCase cases[]={
  {false,true,true,"live connected preflight permits eligible entry"},
  {false,false,false,"live disconnected preflight refuses entry"},
  {true,false,true,"tester disconnected preflight permits eligible entry"},
  {true,true,true,"tester connected preflight still permits eligible entry"}
 };
 for(auto c:cases){
  reset();tester=c.testing;connected=c.online;SymbolState s;setup(s);
  check(s.EntryPreflight(false)==c.allowed,c.name);s.Shutdown();
 }
 for(bool testing:{false,true}){
  reset();tester=testing;connected=!testing;permissions=false;SymbolState s;setup(s);
  check(!s.EntryPreflight(false),testing?"tester still requires trading permissions":"live still requires trading permissions");s.Shutdown();
 }

 reset();tester=true;permissions=false;SymbolState diag;setup(diag);int diagBefore=diag.m_testerDiagnosticCount;
 check(!diag.EntryPreflight(false),"tester diagnostic fixture reaches permission rejection");
 diag.JournalSample();
 check(diag.m_lastTesterDiagnosticStatus==u"Trading permission or broker connection is OFF"&&diag.m_testerDiagnosticCount==diagBefore+1,"tester diagnostic records preflight rejection status");
 diag.JournalSample();check(diag.m_testerDiagnosticCount==diagBefore+1,"tester diagnostic deduplicates unchanged status");
 diag.g_status=u"Waiting for all 7 timeframe indicators";diag.JournalSample();
 check(diag.m_lastTesterDiagnosticStatus==u"Waiting for all 7 timeframe indicators"&&diag.m_testerDiagnosticCount==diagBefore+2,"tester diagnostic records next pipeline status");diag.Shutdown();

 reset();permissions=false;SymbolState liveDiag;setup(liveDiag);
 check(!liveDiag.EntryPreflight(false),"live diagnostic fixture reaches permission rejection");liveDiag.JournalSample();
 check(liveDiag.m_lastTesterDiagnosticStatus==u""&&liveDiag.m_testerDiagnosticCount==0,"live mode emits no tester diagnostics");liveDiag.Shutdown();

 reset();tester=true;connected=false;ScanMode=CURRENT_SYMBOL;fixture_pattern(u"FX");
 check(OnInit()==INIT_SUCCEEDED,"disconnected tester AUTO initializes");
 OnTimer();
 check(order_calls==1&&positions.size()==1&&positions.begin()->second.symbol==u"FX","disconnected tester eligible timer candidate produces a simulated trade");
 OnTimer();check(order_calls==1,"disconnected tester does not duplicate the same M1 entry");OnDeinit(0);

 reset();connected=false;ScanMode=CURRENT_SYMBOL;fixture_pattern(u"FX");
 check(OnInit()==INIT_SUCCEEDED,"disconnected live AUTO initializes for later reconnection");
 OnTimer();check(order_calls==0&&positions.empty(),"disconnected live timer never submits an order");
 connected=true;OnTimer();check(order_calls==1,"live eligible candidate can trade after reconnection");OnDeinit(0);

 reset();tester=true;connected=false;ScanMode=CURRENT_SYMBOL;fixture_pattern(u"FX");MaxPortfolioRiskPercent=.1;
 check(OnInit()==INIT_SUCCEEDED,"disconnected tester initializes with tight portfolio limit");
 OnTimer();check(order_calls==0&&g_symbols[0]->m_portfolioRejects==1,"disconnected tester still enforces portfolio risk before sending");OnDeinit(0);

 reset();tester=true;connected=false;SymbolState unresolved;setup(unresolved);
 GlobalVariableSet(AccountIntent(u"GOLD"),1);
 check(!unresolved.EntryPreflight(false)&&order_calls==0,"disconnected tester still blocks an unresolved account order");unresolved.Shutdown();
}
void v243_tests();void v244_tests();void v244_lock_tests(const std::string &only="");
int main(int argc,char **argv){
 if(argc>1)v244_lock_tests(argv[1]);
 else {scoring_tests();pattern_tests();adaptive_tests();order_tests();ai_tests();scanner_tests();risk_tests();v243_tests();v244_tests();v244_lock_tests();tester_connection_tests();}
 std::cout<<"{\"passed\":"<<checks<<",\"failed\":0}\n";
}

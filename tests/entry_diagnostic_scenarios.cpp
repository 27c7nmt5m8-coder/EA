// Exercise actual source and its emitted aggregate contract, not a copied gate.
void entry_diagnostic_summary_tests(){
 reset();tester=true;connected=false;ScanMode=CURRENT_SYMBOL;fixture_pattern(u"FX");
 diagnostic_output.clear();
 check(OnInit()==INIT_SUCCEEDED,"diagnostic AUTO fixture initializes");
 OnTimer();check(order_calls==1,"diagnostic fixture retains the eligible order");
 OnDeinit(0);
 bool found=false;
 for(auto &line:diagnostic_output)if(line.find(u"[MT3 ENTRY SUMMARY]")==0)found=true;
 check(found,"tester emits candidate and first-rejection summary");
}

void entry_diagnostic_reason_tests(){
 struct Case {const char* label;string reason;std::function<bool(SymbolState&,MqlTick&,PatternSignal&)> run;};
 Case cases[]={
  {"invalid bid",u"invalid_bid",[](auto&s,auto&t,auto&p){symbols[u"FX"].bid=0;return s.FreshQuote(t);}},
  {"crossed quote",u"invalid_bid_ask",[](auto&s,auto&t,auto&p){symbols[u"FX"].ask=99;return s.FreshQuote(t);}},
  {"stale quote",u"quote_stale",[](auto&s,auto&t,auto&p){symbols[u"FX"].tickMs-=10000;return s.FreshQuote(t);}},
  {"future quote",u"quote_from_future",[](auto&s,auto&t,auto&p){symbols[u"FX"].tickMs+=10000;return s.FreshQuote(t);}},
  {"ATR missing",u"spread_atr_unavailable",[](auto&s,auto&t,auto&p){symbols[u"FX"].atr=0;return s.SpreadOK(t);}},
  {"ATR spread",u"spread_atr_limit",[](auto&s,auto&t,auto&p){t.ask=t.bid+1;return s.SpreadOK(t);}},
  {"points spread",u"spread_points_limit",[](auto&s,auto&t,auto&p){MaxSpreadPoints=1;return s.SpreadOK(t);}},
  {"SL relative spread",u"spread_sl_limit",[](auto&s,auto&t,auto&p){return s.SpreadOK(t,t.ask-.05,true);}},
  {"zero SL distance",u"sl_distance_zero",[](auto&s,auto&t,auto&p){return s.SpreadOK(t,t.ask,true);}},
  {"invalid SL",u"invalid_sl",[](auto&s,auto&t,auto&p){return s.EntryStopsValid(true,t,0,102);}},
  {"invalid TP",u"invalid_tp",[](auto&s,auto&t,auto&p){return s.EntryStopsValid(true,t,99,0);}},
  {"SL tick alignment",u"sl_tick_alignment",[](auto&s,auto&t,auto&p){return s.EntryStopsValid(true,t,99.005,102);}},
  {"TP tick alignment",u"tp_tick_alignment",[](auto&s,auto&t,auto&p){return s.EntryStopsValid(true,t,99,102.005);}},
  {"SL wrong side",u"sl_wrong_side",[](auto&s,auto&t,auto&p){return s.EntryStopsValid(true,t,101,102);}},
  {"SL broker gap",u"sl_broker_gap",[](auto&s,auto&t,auto&p){return s.EntryStopsValid(true,t,100,102);}},
  {"TP broker gap",u"tp_broker_gap",[](auto&s,auto&t,auto&p){return s.EntryStopsValid(true,t,99,100);}},
  {"lot below min",u"lot_below_min",[](auto&s,auto&t,auto&p){return s.NormalizeVolume(.001)>0;}},
  {"lot step",u"lot_step_invalid",[](auto&s,auto&t,auto&p){symbols[u"FX"].step=0;return s.NormalizeVolume(1)>0;}},
  {"insufficient margin",u"insufficient_margin_min_lot",[](auto&s,auto&t,auto&p){free_margin=0;return s.CalculateLotByRisk(true,t,99,.5)>0;}},
  {"portfolio limit",u"portfolio_risk_limit",[](auto&s,auto&t,auto&p){double before,planned;MaxPortfolioRiskPercent=.001;return s.CheckPortfolioEntry(true,t,99,1,before,planned);}},
  {"unresolved",u"account_unresolved_order",[](auto&s,auto&t,auto&p){GlobalVariableSet(AccountIntent(u"GOLD"),1);return s.EntryPreflight(false);}},
  {"permissions",u"trading_permission",[](auto&s,auto&t,auto&p){permissions=false;return s.EntryPreflight(false);}},
  {"MC guard",u"monte_carlo",[](auto&s,auto&t,auto&p){RiskMode=RISK_COMBINED;s.g_mcReady=false;return s.EntryPreflight(false);}},
  {"pattern reference",u"pattern_reference_invalid",[](auto&s,auto&t,auto&p){p.referencePrice=0;return s.PatternEntryLocationOK(p,t,true);}},
  {"pattern wrong side",u"pattern_entry_wrong_side",[](auto&s,auto&t,auto&p){p.referencePrice=t.ask+1;return s.PatternEntryLocationOK(p,t,true);}},
  {"failed breakout drift",u"failed_breakout_price_drift",[](auto&s,auto&t,auto&p){p.type=PATTERN_BULLISH_FAILED_BREAKOUT;p.referencePrice=t.ask-1;return s.PatternEntryLocationOK(p,t,true);}}
 };
 for(auto &c:cases){
  reset();tester=true;SymbolState s;setup(s);MqlTick t;s.FreshQuote(t);PatternSignal p=pattern();
  p.type=PATTERN_BULLISH_123;p.triggerTime=iTime(u"FX",PERIOD_M1,1);p.referencePrice=99;
  s.DiagBegin();s.DiagCandidate();
  check(!c.run(s,t,p),c.label);
  check(s.m_diagReason==c.reason,"actual rejection maps to expected detailed reason");
  s.DiagPass(false,u"later_reason");s.DiagEnd(false,u"fixture");s.DiagEnd(false,u"duplicate");
  check(s.m_diagReason==c.reason&&s.m_diagCandidates==1&&s.m_diagRejections==1&&s.m_diagCounts[0]==1,"first rejection retained and counted once");
  s.Shutdown();
 }
}

void entry_diagnostic_flow_tests(){
 for(bool enabled:{false,true}){
  reset();tester=enabled;fixture_pattern(u"FX");SymbolState s;setup(s);diagnostic_output.clear();
  check(s.RefreshCandidate(),"parity candidate qualifies with diagnostic on and off");
  auto score=s.m_candidateScore;auto selected=s.m_candidatePattern.type;
  check(s.DispatchCandidate()&&order_calls==1&&positions.size()==1,"parity dispatch sends once with diagnostic on and off");
  check(s.m_candidateScore==score&&s.m_candidatePattern.type==selected,"diagnostic leaves selected pattern and score intact");
  check(s.m_diagCandidates==(enabled?1:0)&&s.m_diagAttempts==(enabled?1:0)&&s.m_diagAccepted==(enabled?1:0)&&s.m_diagRejections==0,"queue revalidation reuses one candidate and records accepted order separately");
  auto status=s.g_status;s.JournalSample();auto transitions=s.m_testerDiagnosticCount;s.JournalSample();
  check(s.g_status==status&&s.m_testerDiagnosticCount==transitions,"status and unchanged transition dedup remain compatible");
  s.Shutdown();
  if(!enabled)check(diagnostic_output.empty(),"live mode emits no diagnostic output");
 }
 reset();tester=true;fixture_pattern(u"FX");SymbolState s;setup(s);MaxSpreadATR=.001;
 check(!s.RefreshCandidate()&&s.g_status==u"Quote / relative cost / stop geometry blocks entry","cost category preserves original status and rejection");
 check(s.m_diagCandidates==1&&s.m_diagRejections==1&&s.m_diagCost==1&&s.m_diagReason==u"spread_atr_limit","cost rejection counted as candidate not status transition");
 s.DiagEnd(false,u"duplicate");check(s.m_diagRejections==1,"caller cannot double count completed rejection");
 s.Shutdown();
 reset();tester=true;SymbolState fallback;setup(fallback);MqlTick t;fallback.FreshQuote(t);PatternSignal p=pattern();
 p.type=PATTERN_BULLISH_123;p.secondPoint=99.999;symbols[u"FX"].freeze=10;
 double sl,tp;string source,why;fallback.DiagBegin();fallback.DiagCandidate();
 // An invalid structural anchor can recover; intermediate failure is not final.
 p.secondPoint=101;check(fallback.BuildEntryStops(true,t,p,sl,tp,source,why),"existing generic fallback still succeeds");
 check(fallback.m_diagReason==u""&&fallback.m_diagRejections==0,"successful fallback does not retain an intermediate rejection");
 fallback.Shutdown();
 reset();tester=true;fixture_pattern(u"FX");SymbolState lock;setup(lock);check(lock.RefreshCandidate(),"lock fixture queues candidate");
 GlobalVariableTemp(g_execKey);GlobalVariableSet(g_execKey,1);
 check(lock.DispatchCandidate()&&order_calls==0&&lock.m_diagReason==u"execution_lock"&&lock.m_diagRejections==1,"execution lock remains enforced and classified");lock.Shutdown();
}

void entry_diagnostic_tests(){entry_diagnostic_summary_tests();entry_diagnostic_reason_tests();entry_diagnostic_flow_tests();}

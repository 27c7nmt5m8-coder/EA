// v2.44 regression: real production portfolio, SL and logging methods with simulated MT5 services.
void portfolio_tests_244(){
 reset();double risk=0;string why;
 check(ManagedPortfolioRisk(risk,why)&&risk==0&&PortfolioBudgetAllows(risk,1000,100000),"portfolio empty plus 1 percent allowed");
 positions[1]={1,MagicNumber,u"FX",POSITION_TYPE_BUY,1,100,98,102};
 check(ManagedPortfolioRisk(risk,why)&&near(risk,2000)&&PortfolioBudgetAllows(risk,1000,100000),"portfolio 2 plus 1 percent inclusive");
 positions[1].sl=97.9;check(ManagedPortfolioRisk(risk,why)&&!PortfolioBudgetAllows(risk,1000,100000),"portfolio 2.1 plus 1 percent rejected");
 positions[1].sl=100;check(ManagedPortfolioRisk(risk,why)&&risk==0,"portfolio break-even SL risk zero");
 positions[1].sl=101;check(ManagedPortfolioRisk(risk,why)&&risk==0,"portfolio profitable SL never negative credit");
 positions[2]={2,MagicNumber,u"GOLD",POSITION_TYPE_SELL,1,100,101,98};
 check(ManagedPortfolioRisk(risk,why)&&near(risk,1000),"BUY profit cannot offset SELL SL loss");
 positions[1].sl=0;check(!ManagedPortfolioRisk(risk,why),"managed missing SL blocks risk approval");
 positions[1].magic=987;check(ManagedPortfolioRisk(risk,why)&&near(risk,1000),"foreign hedging position excluded by magic");
 positions.erase(1);symbols[u"INDEX"]=MockSymbol{};symbols[u"INDEX"].contract=10;
 positions[3]={3,MagicNumber,u"INDEX",POSITION_TYPE_BUY,2,100,90,120};positions[4]={4,MagicNumber,u"FX",POSITION_TYPE_BUY,.4,100,98,102};
 check(ManagedPortfolioRisk(risk,why)&&near(risk,2000),"FX Gold index mixed account currency risk");
 positions[5]={5,MagicNumber,u"FX",POSITION_TYPE_SELL,.2,100,101,98};
 check(ManagedPortfolioRisk(risk,why)&&near(risk,2200),"hedging multiple tickets all counted");
 profit_ok=false;check(!ManagedPortfolioRisk(risk,why),"risk calc failure fails closed");profit_ok=true;
 reset();margin_mode=ACCOUNT_MARGIN_MODE_RETAIL_NETTING;positions[1]={1,MagicNumber,u"FX",POSITION_TYPE_BUY,1,100,98,102};
 check(!ManagedPortfolioRisk(risk,why),"netting unknown ownership history blocked");
 MockDeal in;in.id=11;in.position=1;in.symbol=u"FX";in.time=server_time;in.volume=1;history_deals[11]=in;
 check(ManagedPortfolioRisk(risk,why)&&near(risk,2000),"netting sole owner risk calculation");
 in.id=12;in.magic=987;history_deals[12]=in;check(!ManagedPortfolioRisk(risk,why),"mixed netting ownership blocks entry");
 positions[1].magic=987;check(!ManagedPortfolioRisk(risk,why),"netting current foreign magic cannot hide original EA exposure");
 reset();SymbolState s;setup(s);MqlTick t;s.FreshQuote(t);positions[2]={2,MagicNumber,u"GOLD",POSITION_TYPE_BUY,1,100,0,102};
 double planned;EnablePortfolioRiskLimit=false;check(s.CheckPortfolioEntry(true,t,98,.1,risk,planned)&&risk<0,"explicitly disabled portfolio limit does not invent known risk");
 reset();fixture_pattern(u"FX");fixture_pattern(u"GOLD");MaxPortfolioRiskPercent=.75;
 check(OnInit()==INIT_SUCCEEDED,"portfolio timer controller init");OnTimer();
 check(order_calls==1&&positions.size()==1,"same timer second candidate blocked after first adds risk");
 double rejects=0;for(auto st:g_symbols)rejects+=st->m_portfolioRejects;check(rejects==1,"portfolio rejected symbol bar counted once");OnDeinit(0);
 reset();ExecutionMode=EXECUTION_AI;SymbolState a;setup(a,u"GOLD");worker_start();check(request(a),"AI request fits portfolio before wait");
 positions[1]={1,MagicNumber,u"FX",POSITION_TYPE_BUY,1.5,100,98,102};inject_reply(a);a.ProcessAIReply();
 check(order_calls==0&&a.m_portfolioRejects==1,"AI approval cannot bypass increased portfolio exposure");
 reset();fixture123(u"FX");SymbolState late;setup(late);PatternSignal p;late.DetectBullish123(p);
 during_ordercheck=[](){check(g_execOwned,"order preparation held account execution mutex");positions[1]={1,MagicNumber,u"GOLD",POSITION_TYPE_BUY,1.5,100,98,102};};
 late.ExecuteEntry(true,91,p);check(order_calls==0&&late.m_portfolioRejects==1,"portfolio recalculated after order preparation before send");during_ordercheck={};
 reset();MaxPortfolioRiskPercent=-1;check(OnInit()==INIT_PARAMETERS_INCORRECT,"negative portfolio limit rejected");
 MaxPortfolioRiskPercent=0;check(OnInit()==INIT_PARAMETERS_INCORRECT,"zero portfolio limit rejected");
 MaxPortfolioRiskPercent=std::numeric_limits<double>::quiet_NaN();check(OnInit()==INIT_PARAMETERS_INCORRECT,"nonfinite portfolio limit rejected");
}
void pattern_sl_tests_244(){
 for(int which=0;which<5;which++)for(bool buy:{true,false}){
  reset();SymbolState s;setup(s);PatternSignal p=pattern();p.buySignal=buy;p.sellSignal=!buy;
  p.firstPoint=buy?97:103;p.headPoint=buy?96:104;p.secondPoint=buy?98:102;
  ENUM_PATTERN_TYPE bull[]={PATTERN_BULLISH_123,PATTERN_BULLISH_FAILED_BREAKOUT,PATTERN_DOUBLE_BOTTOM,PATTERN_TRIPLE_BOTTOM,PATTERN_INVERSE_HEAD_SHOULDERS};
  ENUM_PATTERN_TYPE bear[]={PATTERN_BEARISH_123,PATTERN_BEARISH_FAILED_BREAKOUT,PATTERN_DOUBLE_TOP,PATTERN_TRIPLE_TOP,PATTERN_HEAD_SHOULDERS};
  string sources[]={u"PATTERN_123_P3",u"PATTERN_FAILED_BREAK_EXTREME",u"PATTERN_DOUBLE_EXTREME",u"PATTERN_TRIPLE_EXTREME",u"PATTERN_HS_HEAD"};
  p.type=buy?bull[which]:bear[which];double anchor=which==0?p.secondPoint:which==2?p.firstPoint:p.headPoint;
  MqlTick tick;s.FreshQuote(tick);double sl,tp;string source,why;
  check(s.BuildEntryStops(buy,tick,p,sl,tp,source,why)&&source==sources[which],"all ten pattern directions select correct SL source");
  check((buy?sl<=anchor-s.StopBuffer()+1e-8:sl>=anchor+s.StopBuffer()-1e-8)&&s.EntryStopsValid(buy,tick,sl,tp),"pattern stop strictly outside invalidation with adaptive buffer");
 }
 reset();SymbolState s;setup(s);PatternSignal p=pattern();p.type=PATTERN_BULLISH_123;p.secondPoint=99.85;
 MqlTick tick;s.FreshQuote(tick);double sl,tp;string source,why;symbols[u"FX"].stops=10;
 check(s.BuildEntryStops(true,tick,p,sl,tp,source,why)&&sl<=99.74+1e-8,"broker StopsLevel contributes to adaptive pattern buffer");
 symbols[u"FX"].stops=0;symbols[u"FX"].tick=.25;p.secondPoint=98.13;
 check(s.BuildEntryStops(true,tick,p,sl,tp,source,why)&&near(sl/.25,std::round(sl/.25))&&sl<=97.63,"nondecimal tick step rounds structural stop outward");
 symbols[u"FX"].tick=.01;p.secondPoint=std::numeric_limits<double>::quiet_NaN();
 check(s.BuildEntryStops(true,tick,p,sl,tp,source,why)&&source==u"GENERIC_SWING_FALLBACK"&&!why.empty(),"invalid pattern price falls back with reason");
 p.secondPoint=101;check(s.BuildEntryStops(true,tick,p,sl,tp,source,why)&&source==u"GENERIC_SWING_FALLBACK","wrong side pattern anchor uses generic fallback");
 p.secondPoint=99.95;symbols[u"FX"].freeze=50;
 check(s.BuildEntryStops(true,tick,p,sl,tp,source,why)&&source==u"GENERIC_SWING_FALLBACK","too close pattern SL falls back under FreezeLevel");
 symbols[u"FX"].freeze=1000;
 check(!s.BuildEntryStops(true,tick,p,sl,tp,source,why),"invalid pattern and generic stops rejected without arbitrary widening");
}
ulong loggedEntry(SymbolState &s,PatternSignal &p){
 fixture123(u"FX");setup(s);check(s.DetectBullish123(p),"logged 123 fixture detected");check(s.ExecuteEntry(true,91,p),"logged 123 entry executed");s.JournalMaintenance();return positions.begin()->first;
}
TradeLogRecord loggedRecord(SymbolState&s,ulong id){TradeLogRecord r;check(s.JournalLoadFile(LogPositionBase(s.m_symbol,id)+u".json",r),"persisted analytical record readable");return r;}
void closeLogged(ulong id,double price,long reason,double volume=0){
 auto pos=positions.at(id);if(volume<=0)volume=pos.volume;server_time+=60;mono+=60000;for(auto &kv:symbols)kv.second.tickMs=server_time*1000;
 MockDeal d;d.id=9000+history_deals.size();d.magic=reason==DEAL_REASON_CLIENT?0:MagicNumber;d.position=id;d.order=d.id;d.symbol=pos.symbol;
 d.type=pos.type==POSITION_TYPE_BUY?DEAL_TYPE_SELL:DEAL_TYPE_BUY;d.entry=DEAL_ENTRY_OUT;d.reason=reason;d.time=server_time;d.volume=volume;d.price=price;d.sl=pos.sl;d.tp=pos.tp;
 OrderCalcProfit(pos.type==POSITION_TYPE_BUY?ORDER_TYPE_BUY:ORDER_TYPE_SELL,pos.symbol,volume,pos.open,price,d.profit);history_deals[d.id]=d;
 if(volume>=pos.volume-1e-8)positions.erase(id);else positions[id].volume-=volume;
}
int positionCSVCount(){int count=0;for(auto &kv:files)if(kv.first.find(u"_position_")!=string::npos&&kv.first.size()>4&&kv.first.substr(kv.first.size()-4)==u".csv")count++;return count;}
void journal_tests_244(){
 reset();SymbolState s;PatternSignal p;ulong id=loggedEntry(s,p);auto r=loggedRecord(s,id);
 check(r.pattern==u"BULLISH_123_REVERSAL"&&r.slSource==u"PATTERN_123_P3"&&r.patternId==p.patternId,"entry log pattern ID name and SL source");
 check(r.hasContext&&r.order>0&&r.deal>0&&r.position==id&&r.mode==EnumToString(EXECUTION_AUTO),"entry log actual identifiers and execution mode");
 check(near(r.riskMoney,(r.entry-r.sl)*r.lot*symbols[u"FX"].contract)&&near(r.riskDistance,r.entry-r.sl),"entry initial risk saved in price and account currency");
 check(r.portfolioBefore==0&&r.portfolioAfter>0&&r.plannedRisk>=r.riskMoney,"entry portfolio before after and conservative new reserve");
 double initial=r.riskMoney;positions[id].sl=r.entry+.2;s.JournalMarkSL(id,2,positions[id].sl);closeLogged(id,positions[id].sl,DEAL_REASON_SL);s.m_journalDirty=true;s.JournalMaintenance();r=loggedRecord(s,id);
 check(r.closed&&r.exitReason==u"TRAILING_SL"&&near(r.riskMoney,initial)&&near(r.realizedR,r.net/initial),"trailing exit R uses original SL risk");
 check(r.exitTime>r.entryTime&&r.net>0&&positionCSVCount()==1,"completed log updates same single position file");
 string csv;ReadAIFile(LogPositionBase(u"FX",id)+u".csv",csv);check(csv.find(u"\"RealizedR\"")!=string::npos&&csv.find(u"\"CLOSED\"")!=string::npos,"CSV contains joined entry and completed exit fields");
 s.Shutdown();SymbolState again;setup(again);again.JournalMaintenance();string repeat;ReadAIFile(LogPositionBase(u"FX",id)+u".csv",repeat);
 check(positionCSVCount()==1&&csv==repeat,"restart and repeated close history cannot duplicate a trade");
 for(int how=0;how<5;how++){
  reset();SymbolState a;ulong n=loggedEntry(a,p);auto x=loggedRecord(a,n);double exit=x.sl;long reason=DEAL_REASON_SL;string expected=u"INITIAL_SL";
  if(how==1){positions[n].sl=x.entry;exit=x.entry;expected=u"BREAKEVEN";}
  if(how==2){exit=x.tp;reason=DEAL_REASON_TP;expected=u"TAKE_PROFIT";}
  if(how==3){exit=x.entry+.1;reason=DEAL_REASON_CLIENT;expected=u"MANUAL_CLOSE";}
  if(how==4){exit=x.entry-.1;reason=DEAL_REASON_EXPERT;a.JournalMarkDD(n);expected=u"DD_PROTECTION";}
  closeLogged(n,exit,reason);a.m_journalDirty=true;a.JournalMaintenance();x=loggedRecord(a,n);
  check(x.closed&&x.exitReason==expected,"initial SL BE TP manual and DD exit reasons");
  if(how==1)check(near(x.realizedR,0)&&x.net==0,"break-even result uses original risk with zero realized R");
 }
 reset();SymbolState partial;id=loggedEntry(partial,p);r=loggedRecord(partial,id);
 auto in=history_deals.at(r.deal);in.id=3000;in.volume=.05;in.price+=.02;history_deals[in.id]=in;
 positions[id].open=(positions[id].open*positions[id].volume+in.price*in.volume)/(positions[id].volume+in.volume);positions[id].volume+=in.volume;
 partial.m_journalDirty=true;partial.JournalMaintenance();r=loggedRecord(partial,id);
 check(near(r.lot,positions[id].volume)&&positionCSVCount()==1,"multiple entry fills aggregate into one position record");
 closeLogged(id,positions[id].open+.1,DEAL_REASON_CLIENT,positions[id].volume/2);partial.m_journalDirty=true;partial.JournalMaintenance();r=loggedRecord(partial,id);
 check(!r.closed,"partial exit is not a completed trade statistic");
 closeLogged(id,positions[id].open+.2,DEAL_REASON_CLIENT);partial.m_journalDirty=true;partial.JournalMaintenance();r=loggedRecord(partial,id);
 check(r.closed&&positionCSVCount()==1&&r.dealIds.find(u";")!=string::npos,"all partial fills and exits finalize once");
 reset();SymbolState failure;fixture123(u"FX");setup(failure);failure.DetectBullish123(p);fail_file_pattern=u".csv";
 check(failure.ExecuteEntry(true,91,p),"analytical CSV failure does not block authorized order");failure.JournalMaintenance();
 check(log_warning_count>0&&positionCSVCount()==0,"CSV failure produces Journal warning without false success");
 id=positions.begin()->first;double dist=positions[id].open-positions[id].sl;symbols[u"FX"].bid=positions[id].open+dist*2;symbols[u"FX"].ask=symbols[u"FX"].bid+.02;symbols[u"FX"].tickMs++;
 failure.Maintain(false);check(modify_calls>0,"existing position BE trailing protection continues while CSV unavailable");
 fail_file_pattern=u"";failure.JournalMaintenance();check(positionCSVCount()==1,"analytical file retry repairs one record");
 reset();fixture123(u"FX");fixtureFailed(u"GOLD");OnInit();OnTimer();
 check(order_calls==2&&positionCSVCount()==2,"multi-symbol fills write separate CSV records");
 bool symbolsOK=true;for(auto &kv:positions){TradeLogRecord x;auto st=g_symbols[FindSymbolState(kv.second.symbol)];symbolsOK&=st->JournalLoadFile(LogPositionBase(kv.second.symbol,kv.first)+u".json",x)&&x.symbol==kv.second.symbol;}
 check(symbolsOK,"multi-symbol journal metadata never crosses symbols");OnDeinit(0);
 reset();TradeLogRecord raw;ZeroMemory(raw);raw.account=g_account;raw.symbol=u"FX";raw.magic=MagicNumber;raw.dataset=TradeLogRoot();raw.position=9007199254741009ULL;raw.aiResult=u"quoted \"AI\", line\n日本語";raw.hasContext=true;
 TradeLogRecord back;check(ParseTradeRecord(TradeRecordJSON(raw),back)&&back.position==raw.position&&back.aiResult==raw.aiResult,"log codec preserves 64-bit IDs and Unicode quoted data");
 check(CSVCell(u"=1+1",true)==u"\"'=1+1\""&&TradeRecordCSV(raw).find(u"\"\"AI\"\"")!=string::npos,"CSV escapes strings and neutralizes formula text");
 string live=TradeLogRoot();tester=true;g_logRun=u"";string test=TradeLogRoot();g_logRun=u"";string test2=TradeLogRoot();check(test!=live&&test!=test2,"tester sessions isolated from live and each other");
}
void journal_risk_currency_test(){
 reset();SymbolState s;PatternSignal p;ulong id=loggedEntry(s,p);auto r=loggedRecord(s,id);double initial=r.riskMoney,dist=r.riskDistance;
 symbols[u"FX"].contract*=1.5; // Simulate a changed profit-currency conversion at a later observation.
 s.m_journalDirty=true;s.JournalMaintenance();r=loggedRecord(s,id);check(near(r.riskMoney,initial),"initial log risk money does not float with later conversion rates");
 closeLogged(id,r.tp,DEAL_REASON_TP);s.m_journalDirty=true;s.JournalMaintenance();r=loggedRecord(s,id);
 check(near(r.riskMoney,initial)&&near(r.riskDistance,dist)&&near(r.realizedR,r.net/initial),"exit uses frozen entry-time money and distance");
 double before=r.net;history_deals[r.exitDeal].commission=-2;s.m_journalDirty=true;s.JournalMaintenance();r=loggedRecord(s,id);
 check(near(r.net,before-2)&&near(r.realizedR,r.net/initial)&&positionCSVCount()==1,"late linked deal commission update repairs same closed record");
}
void journal_recovery_tests_244(){
 reset();ExecutionMode=EXECUTION_AI;SymbolState ai;setup(ai);worker_start();check(request(ai),"AI logging request qualified locally");
 inject_reply(ai,u"ok",u"BUY",.93);ai.ProcessAIReply();ai.JournalMaintenance();ulong id=positions.begin()->first;
 auto r=loggedRecord(ai,id);check(r.aiUsed&&near(r.aiConfidence,.93)&&r.aiResult==u"BUY: offline"&&r.pattern==u"AI_ONLY","AI confidence result and pattern-free mode recorded");
 reset();SymbolState lost;PatternSignal p;id=loggedEntry(lost,p);lost.Shutdown();files.clear();
 SymbolState missing;setup(missing);missing.JournalMaintenance();r=loggedRecord(missing,id);
 check(!r.hasContext&&r.pattern==u"UNKNOWN"&&r.slSource==u"UNKNOWN_LEGACY"&&r.riskMoney>0,"missing analytical context stays unknown while initial risk can recover");
 check(TradeRecordCSV(r).find(u"MISSING_ENTRY_CONTEXT")!=string::npos,"CSV explicitly marks unavailable entry attribution");
 reset();fixture123(u"FX");SymbolState delayed;setup(delayed);delayed.DetectBullish123(p);broker_retcode=TRADE_RETCODE_TIMEOUT;
 delayed.ExecuteEntry(true,91,p);string comment=delayed.PendingOrderComment();auto pending=delayed.m_logPending;
 check(delayed.HasUnresolvedOrder()&&positionCSVCount()==0,"unknown order result is not logged as an actual fill");delayed.Shutdown();
 id=777;MockOrder order;order.id=id;order.position=id;order.magic=MagicNumber;order.symbol=u"FX";order.comment=comment;order.sl=pending.sl;order.initial=pending.lot;history_orders[id]=order;
 MockDeal deal;deal.id=778;deal.position=id;deal.order=id;deal.magic=MagicNumber;deal.symbol=u"FX";deal.time=server_time;deal.price=pending.entry;deal.sl=pending.sl;deal.tp=pending.tp;deal.volume=pending.lot;history_deals[deal.id]=deal;
 positions[id]={id,MagicNumber,u"FX",POSITION_TYPE_BUY,pending.lot,pending.entry,pending.sl,pending.tp};
 SymbolState resumed;setup(resumed);resumed.JournalMaintenance();r=loggedRecord(resumed,id);
 check(!resumed.HasUnresolvedOrder()&&r.hasContext&&r.patternId==pending.patternId&&positionCSVCount()==1,"delayed fill after restart recovers intent metadata and reconciles order");
 reset();fixture123(u"GOLD");SymbolState gold;setup(gold,u"GOLD");gold.DetectBullish123(p);gold.ExecuteEntry(true,91,p);gold.JournalMaintenance();id=positions.begin()->first;gold.Shutdown();
 newbar();closeLogged(id,101,DEAL_REASON_CLIENT);ScanMode=CURRENT_SYMBOL;EnableAutoTrading=false;OnInit();
 int index=FindSymbolState(u"GOLD");check(index>=0&&!g_symbols[index]->m_scanEnabled,"off-universe analytical active marker restores state without new-entry scanning");
 ServiceTradeJournals();r=loggedRecord(*g_symbols[index],id);check(r.closed&&r.pattern==u"BULLISH_123_REVERSAL","position closed offline finalizes outside current scan universe");OnDeinit(0);
 reset();fixture123(u"FX");SymbolState jf;setup(jf);jf.DetectBullish123(p);fail_file_pattern=u".json";
 check(jf.ExecuteEntry(true,91,p),"analytical intent JSON failure cannot change order approval");jf.JournalMaintenance();
 check(log_warning_count>0&&!jf.HasUnresolvedOrder(),"JSON failure warns while safety order reconciliation remains separate");
 fail_file_pattern=u"";jf.JournalMaintenance();id=positions.begin()->first;r=loggedRecord(jf,id);check(r.hasContext&&r.pattern==u"BULLISH_123_REVERSAL","in-memory context retries after JSON failure");
 reset();SymbolState count;setup(count);count.ReportPortfolioReject(u"fixture");count.Shutdown();SymbolState countAgain;setup(countAgain);countAgain.ReportPortfolioReject(u"fixture");
 check(countAgain.m_portfolioRejects==1,"same M1 rejection counter deduplicates across restart");
 reset();fixture123(u"FX");SymbolState fills;setup(fills);fills.DetectBullish123(p);fills.ExecuteEntry(true,91,p);id=positions.begin()->first;
 auto first=history_deals.begin()->second;auto extra=first;extra.id=4444;extra.volume=.05;extra.price+=.12;history_deals[extra.id]=extra;
 positions[id].open=(first.price*first.volume+extra.price*extra.volume)/(first.volume+extra.volume);positions[id].volume+=extra.volume;
 fills.JournalMaintenance();r=loggedRecord(fills,id);double expected=((first.price-first.sl)*first.volume+(extra.price-extra.sl)*extra.volume)*symbols[u"FX"].contract;
 check(near(r.riskMoney,expected)&&near(r.riskDistance,positions[id].open-first.sl),"different-price partial fills before first log retain actual weighted initial risk");
}
void v244_tests(){portfolio_tests_244();pattern_sl_tests_244();journal_tests_244();journal_risk_currency_test();journal_recovery_tests_244();}

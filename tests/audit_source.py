"""Static checks of the distributed MQL sources; no native compiler is available."""
from pathlib import Path
import re,json,hashlib
from json_support import extract
from v244_audit_helpers import legacy_engine_function,legacy_main
ROOT=Path(__file__).resolve().parents[1];SRC=ROOT/'src'
code={p.name:p.read_text(encoding='utf-8-sig') for p in sorted(SRC.iterdir()) if p.is_file()}
main=code['MTFAutoTrader_3Mode_AI_v2_44.mq5'];engine=code['MT3SymbolState.mqh']
patterns=code['MT3ReversalPatterns.mqh'];types=code['MT3Types.mqh'];
config=code['MT3Config.mqh'];worker=code['MTFAutoTrader_AI_Worker.mq5'];protocol=code['MT3AIProtocol.mqh'];scoring=code['MT3Scoring.mqh']
cases=[]
def check(name,ok):
    cases.append({'case':name,'passed':bool(ok)})
    if not ok:raise AssertionError(name)
def mask(s):
    return re.sub(r'''//[^\n]*|/\*[\s\S]*?\*/|'(?:\\.|[^'\\])*'|"(?:\\.|[^"\\])*"''',lambda m:'\n'*m[0].count('\n')+' ',s)
for name,s in code.items():
    stack=[];pairs={')':'(',']':'[','}':'{'}
    for ch in mask(s):
        if ch in '([{':stack.append(ch)
        elif ch in ')]}':
            assert stack and stack.pop()==pairs[ch],(name,ch)
    check(name+' delimiters balanced',not stack)
    check(name+' local includes resolved',all((SRC/n).exists() for n in re.findall(r'#include "([^"]+)"',s)))
refs=[]
for name,s in code.items():
    for n,line in enumerate(s.splitlines(),1):
        if re.search(r'\b_Symbol\b',mask(line)):refs.append({'file':name,'line':n,'text':line.strip()})
check('only intentional host chart _Symbol reference',len(refs)==1 and refs[0]['text']=='g_chartSymbol=_Symbol;g_logRun="";g_journalCursor=0;')
check('no _Point _Digits _Period or PERIOD_CURRENT in engine',not re.search(r'\b(?:_Point|_Digits|_Period|PERIOD_CURRENT)\b',mask(engine+patterns)))
check('no old 4/7 or higher 2/3 hard-filter inputs',not re.search(r'\b(?:MinimumTrendAgreement|RequireMACDAgreement|RequireHigherTFTrend|ADXMinimum)\b',mask(engine+config)))
check('MinimumSignalScore 70 preserved',bool(re.search(r'MinimumSignalScore\s*=\s*70\.0',config)))
check('default MARKET_WATCH',bool(re.search(r'ScanMode\s*=\s*MARKET_WATCH',config)))
check('versions coordinated',all('"2.44"' in s for s in [main,worker]) and '#define MT3_AI_PROTOCOL 242' in protocol)
check('no HTTP in main/engine',not re.search(r'\bWebRequest\s*\(',mask(main+engine)))
check('worker does not place orders',not re.search(r'\b(?:CTrade|OrderSend|OrderSendAsync)\b',mask(worker)))
check('ATR-normalized EMA slope',all(t in scoring for t in ['r.atr*EMASlopeBars','r.slopeATR/0.10']))
check('trend MACD 70/30 blend','r.trendScore*0.70+r.macdScore*0.30' in scoring)
check('all seven frame identities checked','r[i].timeframe!=MT3Timeframe(i)' in scoring)
check('D1 excluded from higher veto','for(int i=4;i<=5;i++)' in extract('StrongHigherOpposition',scoring))
check('state fields inside class',engine.index('class SymbolState')<engine.index('CTrade trade;') and all(t in engine for t in ['MTFResult m_mtf[]','PendingAIDecision g_aiRequest;','datetime g_lastTradeBar;','PatternSignal m_candidatePattern;']))
check('no function-static state in symbol engine',not re.search(r'\bstatic\b',mask(engine+patterns)))
check('constructor initializes state',all(t in engine for t in ['SymbolState()','m_mcActive=false;','g_lockOwned=false;','ZeroMemory(g_aiRequest);']))
check('dual-hash scope includes account symbol magic','AIHash("MT3.242/"+scope)' in main and 'g_account+"/"+symbol+StringFormat("/%I64u",MagicNumber)' in main)
check('loaded state hash collision rejected','State hash collision; symbol rejected' in main)
check('v241 migration retained','migrated241' in engine and 'string old="MT3."' in engine)
check('intent durable before broker send',engine.index('if(!BeginPendingOrder())')<engine.index('trade.Buy(lot,') and 'GlobalVariablesFlush();return true; // Intent must be durable before OrderSend.' in engine)
check('account execution mutex wraps whole order','ExecuteEntryLocked(buy,score' in engine and 'GlobalVariableSetOnCondition(g_execKey,1,0)' in main)
check('account unresolved order gate','if(AnyAccountUnresolved())' in extract('EntryPreflight',engine))
check('final order awaits visible or fully closed position','if(PositionIdOpen(id)) return true;' in extract('PendingHistoryOrderFinal',engine) and 'PositionResult(id,' in extract('PendingHistoryOrderFinal',engine))
check('all modes share ExecuteEntry','ExecuteEntry(buy,0,empty,true,sl)' in engine and 'ExecuteEntry(m_candidateBuy' in engine and 'ExecuteEntry(buy,score,pattern,false,0,saved.bar' in engine)
check('exact one-use reconcile token','ReconciledOrderToken==PendingOrderToken()' in engine)
check('netting mixed ownership guard',all(t in extract('SolePositionOwner',engine) for t in ['HistorySelectByPosition','DEAL_ENTRY_INOUT','DEAL_MAGIC']))
check('all-owner directional volume limit','SYMBOL_VOLUME_LIMIT' in extract('AvailableDirectionalVolume',engine) and 'DEAL_MAGIC' not in extract('AvailableDirectionalVolume',engine))
check('relative spread thresholds before sizing','SpreadOK(tick,sl,buy)' in extract('CalculateLotByRisk',engine))
check('fresh quote polling tracks symbol time_msc','tick.time_msc!=m_quoteTimeMsc' in engine and 'now-g_lastSymbolTickMs' in extract('FreshQuote',engine))
check('M1/age/drift rechecked before send','Decision / quote changed before send' in engine and 'bar!=iTime(m_symbol,PERIOD_M1,0)' in extract('ExecuteEntryLocked',engine))
check('AI only locally qualified candidates','score<MinimumSignalScore' in extract('StartAIRequest',engine) and 'WeightedSignalOK(results,buy)' in extract('StartAIRequest',engine))
check('AI snapshots include actual timeframe MACD','MACDParameters(results[i].timeframe,f,s,g)' in engine)
check('worker protocol checked before reservation','AIState(registry+"version")!=MT3_AI_PROTOCOL' in engine)
check('cancellation preserves busy worker slot','AIState(g_aiRequest.registry+"busy")!=g_aiRequest.token' in engine)
check('worker releases only matching nonce','GlobalVariableSetOnCondition(g_workerRegistry+"busy",0,token)' in worker and 'GlobalVariableSetOnCondition(g_workerRegistry+"slot",0,token)' in worker)
check('worker confidence precision preserved','StringFormat("%.17g",confidence)' in worker)
check('queue score and FIFO tie-break','m_candidateScore>g_symbols[best].m_candidateScore' in main and 'm_candidateSequence<g_symbols[best].m_candidateSequence' in main)
check('timer drives scanning independent of ticks','g_symbols[i].Scan();' in extract('OnTimer',main) and 'void OnTick() {MaintainExposure();}' in main)
check('retired universe cancels requests','m_candidate=false;CancelAIRequest();' in extract('SetScanEnabled',engine))
check('manual chart operations host-only','if(!m_isChart) return;' in extract('ChartEvent',engine))
check('chart draw independent of virtual levels','StoreLevel(name,NormalizePrice(price));if(!m_isChart) return true;' in engine)
check('incremental MC per-symbol random state','m_mcRandom^=m_mcRandom<<13' in engine and 'AdvanceMonteCarlo(deadline)' in main)
check('old blocking MC helper not called',len(re.findall(r'\bCalculateMonteCarlo95DD\s*\(',mask(engine+patterns)))==1)
check('MC immutable return snapshot','ArrayCopy(m_mcReturns,g_returns)' in engine)
check('Fintokei completed-position account loss streak','g_accountLossStreak>=FintokeiMaxConsecutiveLosses' in engine and 'HistorySelectByPosition(closedIds[i])' in main)
check('AUTO tester allowed AI explicitly rejected','MQL_TESTER) && (ExecutionMode==EXECUTION_AI || ExecutionMode==EXECUTION_HYBRID)' in main)
for name,before in json.loads((ROOT/'tests/baseline_functions.json').read_text()).items():
    after=extract('DetectLegacyReversalPattern' if name=='DetectReversalPattern' else name,engine).replace('DetectLegacyReversalPattern(', 'DetectReversalPattern(')
    for a,b in [('_Symbol','m_symbol'),('_Point','m_point'),('_Digits','m_digits')]:before=re.sub(r'\b'+a+r'\b',b,before)
    check('v241 preserved function '+name,re.sub(r'\s+','',mask(before))==re.sub(r'\s+','',mask(after)))

# v2.42 fingerprints retain string literals; only comments and whitespace are ignored.
def canonical(s):
    token=r'''//[^\n]*|/\*[\s\S]*?\*/|'(?:\\.|[^'\\])*'|"(?:\\.|[^"\\])*"'''
    out=[];last=0
    for m in re.finditer(token,s):
        out.append(re.sub(r'\s+','',s[last:m.start()]))
        out.append('' if m[0].startswith('/') else m[0]);last=m.end()
    out.append(re.sub(r'\s+','',s[last:]));return ''.join(out)
def digest(s):return hashlib.sha256(canonical(s).encode()).hexdigest()
baseline=json.loads((ROOT/'tests/v242_safety_baseline.json').read_text())
for old,record in baseline['functions'].items():
    after=legacy_engine_function(record['v243_name'],engine)
    after=after.replace(record['v243_name']+'(',old+'(',1)
    check('v242 safety fingerprint (reviewed analytics hooks removed) '+old,digest(after)==record['sha256'])
for old in ['MT3AIProtocol.mqh','MT3Json.mqh','MTFAutoTrader_3Mode_AI_v2_42.mq5','MTFAutoTrader_AI_Worker.mq5']:
    now='MTFAutoTrader_3Mode_AI_v2_44.mq5' if old.endswith('v2_42.mq5') else old
    after=legacy_main(code[now]) if old.endswith('v2_42.mq5') else code[now].replace('2.44','2.42') if now.endswith('.mq5') else code[now]
    check('v242 protocol/controller preserved after reviewed hooks '+old,digest(after)==baseline['whole_files'][old])
old_scoring=scoring[:scoring.index('\ndouble Score100(')]+'\n#endif\n'
check('all old weighted scoring math unchanged',digest(old_scoring)==baseline['whole_files']['MT3Scoring.mqh'])
old_config=config[:config.index('input group "=== v2.43 Final Score Weights')]+ '#endif\n'
check('all existing inputs and defaults unchanged',digest(old_config)==baseline['whole_files']['MT3Config.mqh'])
inputs=re.findall(r'(?m)^input\s+(?!group\b)[^;]+;',config)
added=[x for x in inputs if x not in baseline['input_declarations']]
check('v243 three final weights and v244 three inputs only',added[:3]==['input double FinalMTFWeight = 80.0;','input double FinalPatternWeight = 15.0;','input double FinalLineWeight = 5.0;'] and added[3:]==['input bool EnablePortfolioRiskLimit = true;','input double MaxPortfolioRiskPercent = 3.0;','input bool EnableTradeLog = true;'])
enums=re.search(r'enum ENUM_PATTERN_TYPE\s*\{([^}]+)',types)[1]
check('all legacy enum IDs retained in original order',canonical(enums).startswith(canonical(baseline['legacy_pattern_enums'])+','))
check('four new pattern directions appended',all(n in enums for n in ['PATTERN_BULLISH_123','PATTERN_BEARISH_123','PATTERN_BULLISH_FAILED_BREAKOUT','PATTERN_BEARISH_FAILED_BREAKOUT']))
weights=extract('ValidateFinalWeights',scoring)
check('weight finiteness and individual range enforced',all(t in weights for t in ['MathIsValidNumber('+x+')' for x in ['FinalMTFWeight','FinalPatternWeight','FinalLineWeight']]+[x+op for x in ['FinalMTFWeight','FinalPatternWeight','FinalLineWeight'] for op in ['<0','>100']]))
check('weight sum tolerance is .001 with explicit error','MathAbs(sum-100.0)>0.001' in weights and 'PrintFormat(' in weights)
check('weight validation participates in OnInit rejection','if(!ValidateFinalWeights()) return false;' in extract('ValidateInputs',engine) and 'INIT_PARAMETERS_INCORRECT' in extract('OnInit',main))
check('weights never automatically reassigned',not re.search(r'Final(?:MTF|Pattern|Line)Weight\s*=(?!=)',mask(main+engine+scoring+patterns)))
final=extract('FinalSignalScore',scoring)
check('all final components normalized to 0..100',all(t in final for t in ['Score100(line*5.0)','Score100(mtf)','Score100(pattern)']))
check('both entry directions use new final score',all('FinalSignalScore(' in extract(n,engine) for n in ['CalculateFinalBuyScore','CalculateFinalSellScore']))
d123=extract('Detect123Reversal',patterns);dfb=extract('DetectFailedBreakout',patterns)
check('123 confirmed M1 bars and ATR basis',all(t in d123 for t in ['GetATR(PERIOD_M1,14,1)','iClose(m_symbol,PERIOD_M1,1)','iClose(m_symbol,PERIOD_M1,2)','SwingDepth+1']))
check('123 geometry and age bounds',all(t in d123 for t in ['improvement<-eps','0.35*atr','0.20*atr','3*(SwingDepth+1)','PatternMaxShift()']))
check('123 rejects earlier closed triggers and P1 breaches','side*(c-level)>eps || side*(edge-p1)<-eps' in d123)
check('123 HL LH preference capped at 100','signal.patternStrength=Score100(' in d123 and 'improvement)/(atr*0.35)' in d123)
check('new detectors never read forming OHLC bar',not re.search(r'i(?:Open|High|Low|Close)\([^;\n]*,0\)',mask(d123+dfb)))
check('FB reference confirmed before break','broken+SwingDepth+1' in dfb)
check('FB requires separate closed outside bar','broken=2;broken<=4;broken++' in dfb and 'side*(outside-level)>=-eps' in dfb)
check('FB min max penetration and distance preserved',all(t in dfb for t in ['0.05*atr','0.30*atr','0.35*atr']))
check('FB measures deepest excursion through reclaim','for(int i=1;i<=broken;i++)' in dfb and 'MathMin(extreme,e)' in dfb)
check('FB rejects revived old sweeps','for(int i=broken+1;i<ref-SwingDepth;i++)' in dfb)
check('FB small bodies capped without lowering entry threshold','body<0.03' in dfb and 'MathMin(60.0,signal.patternStrength)' in dfb)
gather=extract('GatherPatterns',patterns)
check('all ten directional patterns gathered',len(re.findall(r'if\(Detect\w+\(p\)',gather))==10)
check('each detector receives cleared independent signal',gather.count('ZeroMemory(p);')==10)
check('incomplete candidate allocation fails closed',all('if(!GatherPatterns(candidates))' in extract(n,patterns) for n in ['DetectReversalPattern','SelectReversalPattern']) and 'return false' in extract('AppendPattern',patterns))
choose=extract('ChoosePattern',patterns)
check('highest PatternScore wins deterministic ties','>Score100(GetPatternScore(candidates[best]))' in choose)
check('ambiguous opposite direction safely rejected','(bull && bear)' in choose)
check('MTF eligibility resolves directional conflict','WeightedSignalOK(r,true),WeightedSignalOK(r,false)' in extract('SelectReversalPattern',patterns))
check('all coincident same-side identities consumed','signal.matchedIds=claims' in choose and 'PatternDirection(candidates[i])==PatternDirection(signal)' in choose)
idfn=extract('PatternIdentity',patterns)
check('pattern IDs contain per-symbol account magic scope','ScopeDigest(g_statePrefix+"/"+signature)' in idfn)
check('FB identity uses reference pivot, not breakout episode','(long)p.referenceTime' in idfn and 'p.breakoutTime' not in idfn)
check('new receipts persist independently of last-pattern guard','p243.' in extract('PatternReceiptKey',patterns) and 'LegacyPatternAlreadyUsed(p)' in extract('IsPatternAlreadyUsed',patterns))
order=extract('ExecuteEntryLocked',engine)
check('pattern claims durable before any broker submission',order.index('PersistPatternClaims(pattern)')<order.index('trade.Buy(lot,'))
check('receipt persistence failure blocks execution','if(!manual && !PersistPatternClaims(pattern)) {ClearPendingOrder();' in order)
check('one attempted order per symbol M1 bar unchanged','(OneEntryPerBar || !manual)' in order and 'bar==g_lastAttemptBar' in order and 'attempt.bar' in order)
check('new live price guard enforced prequeue and presend',all('PatternEntryLocationOK(' in extract(n,engine) for n in ['StartAIRequest','RefreshCandidate','ExecuteEntryLocked']))
check('AI revalidates full structure ID','PatternIdentity(check)!=PatternIdentity(pattern)' in extract('ProcessAIReply',engine))
check('AI carries currently matched structure claims','pattern=check;' in extract('ProcessAIReply',engine))
check('AUTO HYBRID use new routing without full-universe AI sends','SelectReversalPattern(r,p)' in extract('RefreshCandidate',engine) and 'if(score<MinimumSignalScore)' in extract('RefreshCandidate',engine))

# v2.44 additions, alongside every retained v2.43 structural audit gate.
v243=json.loads((ROOT/'tests/v243_safety_baseline.json').read_text())
expected_changed=['UpdatePropProtection','ValidateInputs','StartAIRequest','ProcessAIReply','ManagePositions','Init','Shutdown','Maintain','TradeEvent','ExecuteEntryLocked','RefreshCandidate']
check('v244 changed engine functions are explicitly bounded',set(v243['reviewed_changed_functions'])==set(expected_changed))
for name,h in v243['functions'].items():
    if name not in expected_changed:check('v243 engine function unchanged '+name,digest(extract(name,engine))==h)
for name,h in v243['whole_files'].items():check('v243 entire module unchanged '+name,digest(code[name])==h)
check('all v243 input declarations and defaults unchanged',inputs[:len(v243['input_declarations'])]==v243['input_declarations'])
check('three v244 new inputs only',inputs[len(v243['input_declarations']):]==['input bool EnablePortfolioRiskLimit = true;','input double MaxPortfolioRiskPercent = 3.0;','input bool EnableTradeLog = true;'])
portfolio=code['MT3PortfolioRisk.mqh'];stops=code['MT3PatternStops.mqh'];journal=code['MT3TradeJournal.mqh'];codec=code['MT3TradeLog.mqh']
check('new modules use no implicit chart symbol/period properties',not re.search(r'\b(?:_Symbol|_Point|_Digits|_Period|PERIOD_CURRENT)\b',mask(portfolio+stops+journal+codec)))
check('portfolio limit finite positive at initialization',all(t in extract('ValidateInputs',engine) for t in ['!MathIsValidNumber(MaxPortfolioRiskPercent)','MaxPortfolioRiskPercent<=0','MaxPortfolioRiskPercent>100']))
pr=extract('ManagedPortfolioRisk',portfolio)
check('portfolio enumerates positions across entire account','i<PositionsTotal()' in pr and 'ScanMode' not in pr and 'm_symbol' not in pr)
check('portfolio from entry to current SL via OrderCalcProfit',all(t in pr for t in ['POSITION_PRICE_OPEN','POSITION_SL','POSITION_VOLUME',',symbol,volume,open,sl,profit)']))
check('profitable stops never offset losing risk','risk+=MathMax(0.0,-profit)' in pr)
check('missing SL and failed calculation block risk approval','sl<=0' in pr and '!OrderCalcProfit(' in pr and 'return false' in pr)
check('portfolio ownership hedging/netting and mixed history guards',all(t in pr for t in ['ACCOUNT_MARGIN_MODE_RETAIL_HEDGING','POSITION_MAGIC','DEAL_MAGIC','DEAL_ENTRY_INOUT','HistorySelectByPosition','foreign || reversed']))
check('working managed orders block unknown portfolio exposure','OrdersTotal()' in pr and 'ORDER_MAGIC' in pr)
check('portfolio uses equity cap with small numerical tolerance','equity*MaxPortfolioRiskPercent/100.0+MathMax(1e-8,equity*1e-12)' in extract('PortfolioBudgetAllows',portfolio))
check('risk is recalculated before lot sizing inside locked execution',order.index('ManagedPortfolioRisk(')<order.index('CalculateLotByRisk('))
check('latest risk check follows analytical preparation precedes final quote and send',order.index('PrepareTradeJournal(')<order.rindex('CheckPortfolioEntry(')<order.rindex('FreshQuote(latest)')<order.index('trade.Buy(lot,'))
check('risk over budget rejects without lot cutting','ReportPortfolioReject' in extract('CheckPortfolioEntry',stops) and 'return false' in extract('CheckPortfolioEntry',stops))
check('new risk reserve includes existing entry deviation stop slippage and commission',all(t in extract('PlannedPortfolioRisk',stops) for t in ['DeviationPoints()*m_point','StopSlippage()','RoundTurnCommissionPerLot']))
check('AI preview risk checked before sending worker request',extract('StartAIRequest',engine).index('CheckPortfolioEntry(')<extract('StartAIRequest',engine).index('BuildAISnapshot('))
check('original generic SL and sizing remain available',all(n in v243['functions'] and digest(extract(n,engine))==v243['functions'][n] for n in ['BuildStops','StopBuffer','CalculateLotByRisk','BuildManualStops']))
anchor=extract('PatternStopAnchor',stops)
check('all ten pattern SL cases and five source categories',len(re.findall(r'case PATTERN_',anchor))==10 and all(t in anchor for t in ['PATTERN_123_P3','PATTERN_FAILED_BREAK_EXTREME','PATTERN_DOUBLE_EXTREME','PATTERN_TRIPLE_EXTREME','PATTERN_HS_HEAD']))
check('123 uses P3 and failed breakout uses episode extreme','anchor=p.secondPoint;source="PATTERN_123_P3"' in anchor and 'anchor=p.headPoint;source="PATTERN_FAILED_BREAK_EXTREME"' in anchor)
bs=extract('BuildEntryStops',stops)
check('pattern SL tick rounding outward with reused adaptive buffer','PriceFloor(anchor-buffer)' in bs and 'PriceCeil(anchor+buffer)' in bs and 'buffer=StopBuffer()' in bs)
check('invalid pattern stop falls back with explicit reason','GENERIC_SWING_FALLBACK' in bs and 'Print("SL fallback "' in bs and '!BuildStops(buy,tick,sl,tp)' in bs)
check('broker constraints not silently used to stretch pattern anchor','MathMax(' not in bs and 'MathMin(' not in bs)
check('StopsLevel FreezeLevel latest price tick lattice verified',all(t in extract('EntryStopsValid',stops) for t in ['SYMBOL_TRADE_STOPS_LEVEL','SYMBOL_TRADE_FREEZE_LEVEL','MathRound(sl/step)','tick.bid-gap','tick.ask+gap']))
check('analytics calls never decide approval',all(t in journal for t in ['void PrepareTradeJournal(', 'void JournalAfterSend(', 'void JournalMaintenance(']) and not re.search(r'if\s*\(\s*!?\s*(?:PrepareTradeJournal|JournalAfterSend|JournalMaintenance)\s*\(',engine))
check('safety persistence gates remain mandatory before send','if(!BeginPendingOrder())' in order and 'if(!manual && !PersistPatternClaims(pattern))' in order)
check('actual position identity drives journal filenames','StringFormat("_position_%I64u",id)' in codec)
check('analytical path includes terminal account magic and test session',all(t in codec for t in ['TERMINAL_DATA_PATH','g_account','MagicNumber','MQL_TESTER','TEST_','LIVE']))
check('CSV contains 63 required entry/exit columns',extract('TradeRecordCSV',codec).count('LogCSVAdd(h,row,')==63 and all('"'+x+'"' in extract('TradeRecordCSV',codec) for x in ['InitialRiskAccountCurrency','PatternName','RealizedR','NormalizedLineScore','PortfolioRiskAfterEntry','AIConfidence','SLSource','ExitReason','Fees','ContextStatus']))
check('CSV strings escape quotes and spreadsheet formula prefixes','StringReplace(value,"\\\"","\\\"\\\"")' in codec and "c=='='" in codec and '0xFEFF' in codec)
check('JSON log uses exact ulong text parser and account/magic validation','LogParseU64' in codec and 'r.account==g_account && r.magic==MagicNumber' in codec)
check('logging remains per-symbol with no static mutable engine state','TradeLogRecord m_journal[];' in engine and not re.search(r'\bstatic\b',mask(journal+stops)))
check('all partial fill and exit deals join one position row',all(t in journal for t in ['JournalIndex(id)','vin+=volume','vout+=volume','MathAbs(vin-vout)<1e-7','!PositionIdOpen(id) && !working']))
check('initial money risk frozen across later currency conversion','captured=frozen' in journal and 'money=frozen?r.riskMoney:0' in journal and 'r.realizedR=money>0?r.net/money:0' in journal)
check('net profit includes both entry/exit deal fees','r.net=gross+commission+swap+fee' in journal)
check('all requested exit reason categories present',all('"'+s+'"' in journal for s in ['INITIAL_SL','TRAILING_SL','BREAKEVEN','TAKE_PROFIT','DD_PROTECTION','MANUAL_CLOSE','OTHER']))
check('analysis failure warns and retries without deleting dirty record','JournalWarn("record/CSV write failed' in journal and 'if(m_journal[i].dirty && !JournalPersist(m_journal[i])) {ok=false;continue;}' in journal)
check('memory failure does not advance analytical history cursor','if(!JournalAddId(' in journal and 'if(ok)\n {' in journal)
check('recovery markers restore off-universe state without new entries','AddSymbolState(symbol,false)' in extract('RestoreJournalSymbols',main) and 'FileFindClose(search)' in main)
check('journal service runs after exposure protection and queue','MaintainExposure();' in extract('OnTimer',main) and 'DispatchQueue();ServiceTradeJournals();' in main)
check('MFE MAE labelled sampled including restart gaps','SAMPLED_WITH_GAPS' in journal and 'ExcursionCoverage' in codec)
check('reject counter separated from safety reservation and per-bar persisted','log.portfolio.bar' in stops and 'log.portfolio.rejects' in stops and 'log.portfolio.bar' in engine)

result={'scope':'Static source audit, not a native MT5 compilation.','passed':len(cases),'failed':0,'cases':cases,'symbol_references':refs,
        'source_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(SRC.iterdir()) if p.is_file()}}
(ROOT/'verification/source_audit.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print('PASS',len(cases),'static source assertions')

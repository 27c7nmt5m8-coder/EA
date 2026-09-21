// MTFAutoTrader v2.45: one controller, isolated SymbolState engines.
#property strict
#property version "2.45"
#property description "Weighted M1 multi-symbol trader with asynchronous AI worker"
#include <Trade/Trade.mqh>
#include "MT3AIProtocol.mqh"
#include "MT3Types.mqh"
#include "MT3Config.mqh"
#include "MT3Scoring.mqh"

string g_chartSymbol="",g_account="",g_accountPrefix="",g_execKey="",g_propControllerKey="";
bool g_propControllerOwned=false,g_execOwned=false,g_accountHistoryOK=false,g_accountHistoryDirty=true;
int g_accountLossStreak=0;
datetime g_accountHistoryAt=0;
ulong g_queueSequence=0;
uint TextHash(string text) {return AIHash(text);}
string ScopeDigest(string scope) {return AIHex(AIHash(scope))+AIHex(AIHash("MT3.242/"+scope));}
string SymbolScope(string symbol) {return g_account+"/"+symbol+StringFormat("/%I64u",MagicNumber);}
string SymbolPrefix(string symbol) {return "MT3S."+ScopeDigest(SymbolScope(symbol))+".";}
string AccountIntent(string symbol) {return g_accountPrefix+"I."+ScopeDigest(SymbolScope(symbol));}
bool AcquireExecution()
{
 if(g_execOwned || (!GlobalVariableCheck(g_execKey) && !GlobalVariableTemp(g_execKey)) || !GlobalVariableSetOnCondition(g_execKey,1,0)) return false;
 g_execOwned=true;return true;
}
void ReleaseExecution()
{if(g_execOwned) {GlobalVariableSetOnCondition(g_execKey,0,1);g_execOwned=false;}}
bool AnyAccountUnresolved()
{
 string prefix=g_accountPrefix+"I.";
 for(int i=GlobalVariablesTotal()-1;i>=0;i--)
 {string key=GlobalVariableName(i);if(StringFind(key,prefix)==0 && AIState(key)>0) return true;}
 return false;
}
bool TradableSymbol(string symbol)
{
 if(symbol=="" || SymbolInfoInteger(symbol,SYMBOL_CUSTOM)) return false;
 long mode=SymbolInfoInteger(symbol,SYMBOL_TRADE_MODE),orders=SymbolInfoInteger(symbol,SYMBOL_ORDER_MODE);
 return (mode==SYMBOL_TRADE_MODE_FULL || mode==SYMBOL_TRADE_MODE_LONGONLY || mode==SYMBOL_TRADE_MODE_SHORTONLY) &&
        (orders&SYMBOL_ORDER_MARKET)!=0 && (orders&SYMBOL_ORDER_SL)!=0 && (orders&SYMBOL_ORDER_TP)!=0;
}
bool AccountPositionOpen(ulong id)
{
 for(int i=0;i<PositionsTotal();i++)
  if(PositionGetTicket(i)>0 && (ulong)PositionGetInteger(POSITION_IDENTIFIER)==id) return true;
 return false;
}
void RefreshAccountHistory(bool force=false)
{
 if(AccountMode!=FINTOKEI) {g_accountHistoryOK=true;return;}
 if(!force && !g_accountHistoryDirty && TimeCurrent()-g_accountHistoryAt<60) return;
 g_accountHistoryOK=false;
 if(!HistorySelect(0,TimeCurrent())) return;
 ulong owners[],closedIds[];
 for(int i=0;i<HistoryDealsTotal();i++)
 {
  ulong d=HistoryDealGetTicket(i);
  if((ulong)HistoryDealGetInteger(d,DEAL_MAGIC)!=MagicNumber || HistoryDealGetInteger(d,DEAL_ENTRY)!=DEAL_ENTRY_IN) continue;
  int n=ArraySize(owners);if(ArrayResize(owners,n+1)!=n+1) return;owners[n]=(ulong)HistoryDealGetInteger(d,DEAL_POSITION_ID);
 }
 ArraySort(owners);
 for(int i=HistoryDealsTotal()-1;i>=0;i--)
 {
  ulong d=HistoryDealGetTicket(i);long e=HistoryDealGetInteger(d,DEAL_ENTRY);
  if(e!=DEAL_ENTRY_OUT && e!=DEAL_ENTRY_OUT_BY) continue;
  ulong id=(ulong)HistoryDealGetInteger(d,DEAL_POSITION_ID);
  if(id==0 || AccountPositionOpen(id) || ArraySize(owners)==0) continue;
  int found=ArrayBsearch(owners,id);if(found<0 || owners[found]!=id) continue;
  bool seen=false;for(int k=0;k<ArraySize(closedIds);k++) if(closedIds[k]==id) {seen=true;break;}
  if(seen) continue;
  int n=ArraySize(closedIds);if(ArrayResize(closedIds,n+1)!=n+1) return;closedIds[n]=id;
 }
 g_accountLossStreak=0;
 for(int i=0;i<ArraySize(closedIds);i++)
 {
  if(!HistorySelectByPosition(closedIds[i])) return;
  bool mixed=false,ours=false;double vin=0,vout=0,net=0;datetime closed=0;
  for(int j=0;j<HistoryDealsTotal();j++)
  {
   ulong d=HistoryDealGetTicket(j);long type=HistoryDealGetInteger(d,DEAL_TYPE);
   if(type!=DEAL_TYPE_BUY && type!=DEAL_TYPE_SELL) continue;
   long e=HistoryDealGetInteger(d,DEAL_ENTRY);double v=HistoryDealGetDouble(d,DEAL_VOLUME);
   net+=HistoryDealGetDouble(d,DEAL_PROFIT)+HistoryDealGetDouble(d,DEAL_SWAP)+HistoryDealGetDouble(d,DEAL_COMMISSION)+HistoryDealGetDouble(d,DEAL_FEE);
   if(e==DEAL_ENTRY_INOUT) mixed=true;
   if(e==DEAL_ENTRY_IN) {vin+=v;if((ulong)HistoryDealGetInteger(d,DEAL_MAGIC)==MagicNumber) ours=true;else mixed=true;}
   if(e==DEAL_ENTRY_OUT || e==DEAL_ENTRY_OUT_BY) {vout+=v;closed=(datetime)MathMax((long)closed,HistoryDealGetInteger(d,DEAL_TIME));}
  }
  if(mixed || !ours || vin<=0 || MathAbs(vin-vout)>1e-7 || closed<=0) continue;
  if(closed<LossStreakResetTime || net>BreakEvenMoneyTolerance) break;
  if(net<-BreakEvenMoneyTolerance) g_accountLossStreak++;
 }
 g_accountHistoryAt=TimeCurrent();g_accountHistoryDirty=false;g_accountHistoryOK=true;
}

#include "MT3PortfolioRisk.mqh"
#include "MT3TradeLog.mqh"
#include "MT3SymbolState.mqh"

SymbolState *g_symbols[];
int g_scanCursor=0,g_mcCursor=0,g_journalCursor=0;
datetime g_universeAt=0;
int FindSymbolState(string symbol)
{for(int i=0;i<ArraySize(g_symbols);i++) if(g_symbols[i].m_symbol==symbol) return i;return -1;}
bool HasManagedExposure(string symbol)
{
 for(int i=0;i<PositionsTotal();i++)
  if(PositionGetTicket(i)>0 && PositionGetString(POSITION_SYMBOL)==symbol && (ulong)PositionGetInteger(POSITION_MAGIC)==MagicNumber) return true;
 for(int i=0;i<OrdersTotal();i++)
  if(OrderGetTicket(i)>0 && OrderGetString(ORDER_SYMBOL)==symbol && (ulong)OrderGetInteger(ORDER_MAGIC)==MagicNumber) return true;
 return false;
}
bool AddSymbolState(string symbol,bool scan)
{
 int found=FindSymbolState(symbol);
 if(found>=0) {if(scan) g_symbols[found].m_wanted=true;return true;}
 string prefix=SymbolPrefix(symbol);
 for(int i=0;i<ArraySize(g_symbols);i++)
  if(g_symbols[i].g_statePrefix==prefix) {Print("State hash collision; symbol rejected: ",symbol);return false;}
 SymbolState *state=new SymbolState;
 if(state==NULL) return false;
 if(!state.Init(symbol,symbol==g_chartSymbol,scan)) {state.Shutdown();delete state;Print("Cannot initialize symbol: ",symbol);return false;}
 state.m_wanted=scan;int n=ArraySize(g_symbols);
 if(ArrayResize(g_symbols,n+1)!=n+1) {state.Shutdown();delete state;return false;}
 g_symbols[n]=state;return true;
}
void RefreshUniverse()
{
 for(int i=0;i<ArraySize(g_symbols);i++) g_symbols[i].m_wanted=false;
 string names[];
 if(ScanMode==CURRENT_SYMBOL) {ArrayResize(names,1);names[0]=g_chartSymbol;}
 else if(ScanMode==CUSTOM_LIST)
 {
  string list=CustomSymbols;StringReplace(list,";",",");StringReplace(list,"\r",",");StringReplace(list,"\n",",");
  StringSplit(list,',',names);
 }
 else
 {
  // Snapshot before SymbolSelect: selecting another instrument can change Market Watch.
  bool watch=ScanMode==MARKET_WATCH;int total=SymbolsTotal(watch);
  for(int i=0;i<total;i++)
  {
   string name=SymbolName(i,watch);if(name=="" || (watch && !SymbolInfoInteger(name,SYMBOL_VISIBLE))) continue;
   int n=ArraySize(names);if(ArrayResize(names,n+1)==n+1) names[n]=name;
  }
 }
 for(int i=0;i<ArraySize(names);i++)
 {
  string name=names[i];StringTrimLeft(name);StringTrimRight(name);if(name=="") continue;
  if(!TradableSymbol(name)) {Print("Entry universe skips unavailable/unsupported symbol: ",name);continue;}
  AddSymbolState(name,true);
 }
 // Always preserve chart UI and ownership management outside the entry universe.
 AddSymbolState(g_chartSymbol,false);
 string owned[];
 for(int i=0;i<PositionsTotal();i++)
  if(PositionGetTicket(i)>0 && (ulong)PositionGetInteger(POSITION_MAGIC)==MagicNumber)
  {int n=ArraySize(owned);if(ArrayResize(owned,n+1)==n+1) owned[n]=PositionGetString(POSITION_SYMBOL);}
 for(int i=0;i<OrdersTotal();i++)
  if(OrderGetTicket(i)>0 && (ulong)OrderGetInteger(ORDER_MAGIC)==MagicNumber)
  {int n=ArraySize(owned);if(ArrayResize(owned,n+1)==n+1) owned[n]=OrderGetString(ORDER_SYMBOL);}
 for(int i=0;i<ArraySize(owned);i++) AddSymbolState(owned[i],false);
 for(int i=0;i<SymbolsTotal(false);i++)
 {
  string symbol=SymbolName(i,false),prefix=SymbolPrefix(symbol);
  string legacy="MT3."+IntegerToString((long)TextHash(SymbolScope(symbol)))+".";
  if(AIState(AccountIntent(symbol))>0 || AIState(prefix+"ord.state")>0 || AIState(prefix+"manual.pending")>0 ||
     (AIState(prefix+"migrated241")==0 && (AIState(legacy+"ord.state")>0 || AIState(legacy+"manual.pending")>0))) AddSymbolState(symbol,false);
 }
 for(int i=0;i<ArraySize(g_symbols);i++)
 {
  g_symbols[i].SetScanEnabled(g_symbols[i].m_wanted);
  if(!g_symbols[i].m_scanEnabled && !g_symbols[i].m_isChart && !g_symbols[i].HasUnresolvedOrder() && !HasManagedExposure(g_symbols[i].m_symbol))
   g_symbols[i].ReleaseIndicators();
 }
 g_universeAt=TimeCurrent();
}
void RestoreJournalSymbols()
{
 if(!EnableTradeLog || MQLInfoInteger(MQL_TESTER)) return;
 string name;long search=FileFindFirst(TradeLogRoot()+"*_active.json",name,FILE_COMMON);
 if(search==INVALID_HANDLE) return;
 do
 {
  string data,symbol;CMT3Json j;
  if(ReadAIFile(TradeLogRoot()+name,data) && j.Parse(data) && j.GetString(0,"symbol",symbol) && symbol!="") AddSymbolState(symbol,false);
 } while(FileFindNext(search,name));
 FileFindClose(search);
}
void ServiceTradeJournals()
{
 if(!EnableTradeLog) return;
 int count=ArraySize(g_symbols);ulong start=GetTickCount64();
 for(int n=0;n<count && GetTickCount64()-start<20;n++)
 {int i=g_journalCursor%count;g_journalCursor=(g_journalCursor+1)%count;g_symbols[i].JournalMaintenance();}
}
void RenderDashboard()
{
 int active=0;for(int i=0;i<ArraySize(g_symbols);i++) if(g_symbols[i].m_scanEnabled) active++;
 string text=StringFormat("MTF AutoTrader v2.45 | %s | %s\n%s | scanning %d symbols | agreement >= %.0f%% | score >= %.0f\n",
  EnumToString(ExecutionMode),EnumToString(RiskMode),EnumToString(ScanMode),active,MinimumWeightedAgreement,MinimumSignalScore);
 if(AnyAccountUnresolved()) text+="ACCOUNT ENTRY BLOCK: ORDER UNRESOLVED\n";
 int chart=FindSymbolState(g_chartSymbol);
 if(chart>=0)
 {
  string mc=RiskMode==RISK_FIXED_ADJUST?"OFF":(g_symbols[chart].m_mcActive?"CALCULATING":
    (g_symbols[chart].g_sampleCount<MonteCarloMinimumSamples?"WARM-UP":"EMPIRICAL R"));
  text+=StringFormat("%s | last risk %.4f%% | losses %d | MC %s cap %.4f%% n=%d\n",g_chartSymbol,
   g_symbols[chart].g_currentRiskPercent,g_symbols[chart].g_consecutiveLosses,mc,g_symbols[chart].g_mcRisk,g_symbols[chart].g_sampleCount);
  if(AccountMode==FINTOKEI) text+=StringFormat("DD ref %.2f | daily floor %.2f | overall %.2f | stop %d | account losses %d\n",
   g_symbols[chart].g_dailyReference,g_symbols[chart].DailyFloor(),g_symbols[chart].OverallFloor(),g_symbols[chart].g_propStop,g_accountLossStreak);
 }
 int rows=ExecutionMode==EXECUTION_MANUAL?(int)MathMin(DashboardRows,3):DashboardRows;
 int shown=0;
 for(int pass=0;pass<2;pass++) for(int i=0;i<ArraySize(g_symbols) && shown<rows;i++)
 {
  bool urgent=g_symbols[i].HasUnresolvedOrder() || g_symbols[i].g_aiRequest.active;
  if(urgent!=(pass==0)) continue;
  if(!urgent && !g_symbols[i].m_scanEnabled && !g_symbols[i].m_isChart) continue;
  string status=g_symbols[i].g_status;
  if(ExecutionMode==EXECUTION_MANUAL && g_symbols[i].m_isChart && !urgent && g_symbols[i].g_propStop==0)
   status=g_symbols[i].g_manualReadiness;
  text+=g_symbols[i].m_symbol+" | "+status+"\n";shown++;
 }
 Comment(text);
}
void MaintainExposure()
{
 RefreshAccountHistory();
 for(int i=0;i<ArraySize(g_symbols);i++)
  if(g_symbols[i].m_isChart || g_symbols[i].HasUnresolvedOrder() || g_symbols[i].g_aiRequest.active || HasManagedExposure(g_symbols[i].m_symbol))
   g_symbols[i].Maintain(false);
}
void DispatchQueue()
{
 for(int attempt=0;attempt<MaxEntriesPerTimer;attempt++)
 {
  int best=-1;
  for(int i=0;i<ArraySize(g_symbols);i++)
  {
   if(!g_symbols[i].m_candidate) continue;
   if(g_symbols[i].m_candidateBar!=iTime(g_symbols[i].m_symbol,PERIOD_M1,0)) {g_symbols[i].m_candidate=false;continue;}
   if(best<0 || g_symbols[i].m_candidateScore>g_symbols[best].m_candidateScore ||
      (g_symbols[i].m_candidateScore==g_symbols[best].m_candidateScore && g_symbols[i].m_candidateSequence<g_symbols[best].m_candidateSequence)) best=i;
  }
  if(best<0) return;
  bool sent=g_symbols[best].DispatchCandidate();
  if(ExecutionMode!=EXECUTION_AUTO && sent) return;
  if(!sent && g_symbols[best].m_candidate) return; // Shared worker busy: retain highest-priority candidate.
 }
}
void OnTimer()
{
 MaintainExposure();
 if(TimeCurrent()-g_universeAt>=UniverseRefreshSeconds) RefreshUniverse();
 int count=ArraySize(g_symbols),visited=0,scanned=0;ulong start=GetTickCount64();
 while(count>0 && visited<count && scanned<SymbolsPerTimer && GetTickCount64()-start<(ulong)ScanBudgetMilliseconds)
 {
  int i=g_scanCursor%count;g_scanCursor=(g_scanCursor+1)%count;visited++;
  if(!g_symbols[i].m_scanEnabled && !g_symbols[i].m_isChart && !HasManagedExposure(g_symbols[i].m_symbol) && !g_symbols[i].HasUnresolvedOrder()) continue;
  g_symbols[i].Scan();scanned++;
 }
 ulong deadline=GetTickCount64()+(ulong)MonteCarloTimerBudgetMs;
 for(int n=0;n<count && GetTickCount64()<deadline;n++)
 {int i=g_mcCursor%count;g_mcCursor=(g_mcCursor+1)%count;g_symbols[i].AdvanceMonteCarlo(deadline);}
 DispatchQueue();ServiceTradeJournals();RenderDashboard();
}
void OnTick() {MaintainExposure();}
void OnTradeTransaction(const MqlTradeTransaction &trans,const MqlTradeRequest &request,const MqlTradeResult &result)
{
 g_accountHistoryDirty=true;
 string symbol=trans.symbol!=""?trans.symbol:request.symbol;
 if(symbol!="" && FindSymbolState(symbol)<0 && HasManagedExposure(symbol)) AddSymbolState(symbol,false);
 for(int i=0;i<ArraySize(g_symbols);i++) if(symbol=="" || g_symbols[i].m_symbol==symbol) g_symbols[i].TradeEvent(trans,request,result);
}
void OnChartEvent(const int id,const long &lparam,const double &dparam,const string &sparam)
{
 if(id==CHARTEVENT_CUSTOM+MT3_AI_REPLY_EVENT)
 {
  for(int i=0;i<ArraySize(g_symbols);i++) if(g_symbols[i].g_aiRequest.active && g_symbols[i].g_aiRequest.id==sparam && g_symbols[i].g_aiRequest.worker==lparam)
   {g_symbols[i].ProcessAIReply();break;}
 }
 else {int i=FindSymbolState(g_chartSymbol);if(i>=0) g_symbols[i].ChartEvent(id,lparam,dparam,sparam);}
 RenderDashboard();
}
int OnInit()
{
 g_chartSymbol=_Symbol;g_logRun="";g_journalCursor=0;
 if(MQLInfoInteger(MQL_TESTER) && (ExecutionMode==EXECUTION_AI || ExecutionMode==EXECUTION_HYBRID))
 {Print("AUTO supports Strategy Tester; AI/HYBRID require the external live worker.");return INIT_PARAMETERS_INCORRECT;}
 SymbolState validator;if(!validator.ValidateInputs()) {Print("Invalid inputs. See README_JA.md.");return INIT_PARAMETERS_INCORRECT;}
 g_account=AccountInfoString(ACCOUNT_SERVER)+StringFormat("/%I64d",AccountInfoInteger(ACCOUNT_LOGIN));
 g_accountPrefix="MT3A."+ScopeDigest(g_account)+".";g_execKey="MT3EXEC."+ScopeDigest(g_account);
 if(AccountMode==FINTOKEI)
 {
  g_propControllerKey="MT3L."+IntegerToString((long)TextHash(g_account+"/PROP"));
  if((!GlobalVariableCheck(g_propControllerKey) && !GlobalVariableTemp(g_propControllerKey)) || !GlobalVariableSetOnCondition(g_propControllerKey,1,0))
  {Print("Another prop controller owns this account.");return INIT_FAILED;}
  g_propControllerOwned=true;
 }
 if(MQLInfoInteger(MQL_TESTER))
 {
  GlobalVariablesDeleteAll(g_accountPrefix);
  string prop="MT3P."+IntegerToString((long)TextHash(g_account+"/"+EnumToString(FintokeiPlan)+"/"+DoubleToString(FintokeiInitialBalance,2)))+".";
  GlobalVariablesDeleteAll(prop);
 }
 RefreshAccountHistory(true);RefreshUniverse();RestoreJournalSymbols();
 if(ArraySize(g_symbols)==0 || FindSymbolState(g_chartSymbol)<0) return INIT_FAILED;
 if(!EventSetMillisecondTimer(ScanTimerMilliseconds)) return INIT_FAILED;
 RenderDashboard();return INIT_SUCCEEDED;
}
void OnDeinit(const int reason)
{
 EventKillTimer();
 for(int i=0;i<ArraySize(g_symbols);i++) {g_symbols[i].Shutdown();delete g_symbols[i];}
 ArrayResize(g_symbols,0);ReleaseExecution();
 if(g_propControllerOwned) {GlobalVariableSetOnCondition(g_propControllerKey,0,1);g_propControllerOwned=false;}
 Comment("");GlobalVariablesFlush();
}

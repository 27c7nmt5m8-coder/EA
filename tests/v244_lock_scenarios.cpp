// Regression coverage for retained terminal Global Variables across EA lifecycles.
// Calls the adapted production methods. MT5 services remain offline doubles.

void lock_mock_contract_tests(){
 reset();string key=u"TEMP_CONTRACT";
 check(GlobalVariableTemp(key)&&GlobalVariableGet(key)==0,"new temporary Global Variable starts at zero");
 ResetLastError();
 check(!GlobalVariableTemp(key)&&GetLastError()==4502&&GlobalVariableGet(key)==0,"existing zero temporary variable returns GLOBALVARIABLE_EXISTS");
 GlobalVariableSet(key,1);ResetLastError();
 check(!GlobalVariableTemp(key)&&GetLastError()==4502&&GlobalVariableGet(key)==1,"existing held variable is rejected without overwriting its value");
}

void lock_symbol_reinit_tests(){
 reset();SymbolState first;
 check(first.Init(u"FX",false,true),"symbol initial Init succeeds");
 string key=first.g_lockKey;
 first.Shutdown();
 check(GlobalVariableCheck(key)&&GlobalVariableGet(key)==0&&!first.g_lockOwned,"symbol Shutdown retains an unlocked Global Variable");
 check(first.Init(u"FX",false,true),"same SymbolState Init after Shutdown succeeds");
 check(first.g_lockOwned&&GlobalVariableGet(key)==1,"reinitialized SymbolState owns its lock");
 first.Shutdown();SymbolState replacement;
 check(replacement.Init(u"FX",false,true),"new SymbolState for same symbol reinitializes after Shutdown");
 replacement.Shutdown();
}

void lock_chartchange_tests(){
 reset();
 check(OnInit()==INIT_SUCCEEDED&&g_symbols.size()==2,"multi-symbol controller initial OnInit succeeds");
 string fx=g_symbols[FindSymbolState(u"FX")]->g_lockKey;
 string gold=g_symbols[FindSymbolState(u"GOLD")]->g_lockKey;
 OnDeinit(REASON_CHARTCHANGE);
 check(g_symbols.empty()&&GlobalVariableCheck(fx)&&GlobalVariableCheck(gold)&&GlobalVariableGet(fx)==0&&GlobalVariableGet(gold)==0,"chart change deinit retains both unlocked symbol keys");
 check(OnInit()==INIT_SUCCEEDED,"OnInit after OnDeinit REASON_CHARTCHANGE succeeds");
 check(g_symbols.size()==2&&FindSymbolState(u"FX")>=0&&FindSymbolState(u"GOLD")>=0&&GlobalVariableGet(fx)==1&&GlobalVariableGet(gold)==1,"chart change restores both monitored symbol owners");
 OnDeinit(REASON_CHARTCHANGE);
 check(OnInit()==INIT_SUCCEEDED&&g_symbols.size()==2,"repeated chart changes continue to initialize");
 OnDeinit(REASON_CHARTCHANGE);
}

void lock_execution_reacquire_tests(){
 reset();string key=g_execKey;
 check(AcquireExecution()&&g_execOwned&&GlobalVariableGet(key)==1,"execution mutex first Acquire succeeds");
 check(!AcquireExecution()&&g_execOwned&&GlobalVariableGet(key)==1,"execution mutex rejects recursive Acquire");
 ReleaseExecution();
 check(GlobalVariableCheck(key)&&GlobalVariableGet(key)==0&&!g_execOwned,"execution Release retains unlocked mutex");
 check(AcquireExecution()&&g_execOwned&&GlobalVariableGet(key)==1,"execution mutex Acquire Release reAcquire succeeds");
 ReleaseExecution();
}

void lock_worker_reinit_tests(){
 reset();OpenAIAPIKey=u"FAKE_OFFLINE_TEST_KEY";chart_id=2;
 check(WorkerInit()==INIT_SUCCEEDED,"worker initial Init succeeds");
 string registry=g_workerRegistry,key=registry+u"owner";
 WorkerDeinit(REASON_CHARTCHANGE);
 check(GlobalVariableCheck(key)&&GlobalVariableGet(key)==0&&!g_workerOwned,"worker Deinit retains unlocked owner variable");
 check(WorkerInit()==INIT_SUCCEEDED,"worker Init Deinit reInit succeeds");
 check(g_workerOwned&&GlobalVariableGet(key)==1&&AIState(registry+u"version")==242&&AIState(registry+u"lease")>mono,"reinitialized worker restores protocol and live registration");
 WorkerDeinit(REASON_CHARTCHANGE);chart_id=1;
}

void lock_fintokei_reinit_tests(){
 reset();AccountMode=FINTOKEI;FintokeiInitialBalance=100000;
 check(OnInit()==INIT_SUCCEEDED&&g_propControllerOwned,"Fintokei controller initial Init succeeds");
 string key=g_propControllerKey;
 OnDeinit(REASON_CHARTCHANGE);
 check(GlobalVariableCheck(key)&&GlobalVariableGet(key)==0&&!g_propControllerOwned,"Fintokei Deinit retains unlocked controller key");
 check(OnInit()==INIT_SUCCEEDED,"Fintokei controller reinitialization succeeds");
 check(g_propControllerOwned&&GlobalVariableGet(key)==1&&g_symbols.size()==2,"Fintokei reinitialization restores controller and symbol ownership");
 OnDeinit(REASON_CHARTCHANGE);FintokeiInitialBalance=0;
}

void lock_contention_tests(){
 reset();SymbolState owner,other;
 check(owner.Init(u"FX",false,true),"symbol contention first instance owns lock");
 string key=owner.g_lockKey;
 check(!other.Init(u"FX",false,true)&&!other.g_lockOwned,"symbol contention second instance rejected");
 other.Shutdown();
 check(owner.g_lockOwned&&GlobalVariableCheck(key)&&GlobalVariableGet(key)==1,"rejected SymbolState shutdown preserves first owner");
 owner.Shutdown();
 check(other.Init(u"FX",false,true),"second SymbolState can acquire after first owner releases");other.Shutdown();

 reset();check(AcquireExecution(),"execution contention first instance owns lock");key=g_execKey;
 // Switch only instance-local ownership, keeping terminal globals shared.
 bool ownerExec=g_execOwned;g_execOwned=false;
 check(!AcquireExecution()&&!g_execOwned,"execution contention independent second instance rejected");
 ReleaseExecution();
 check(GlobalVariableCheck(key)&&GlobalVariableGet(key)==1,"rejected execution owner cannot release another instance's mutex");
 g_execOwned=ownerExec;ReleaseExecution();

 reset();OpenAIAPIKey=u"FAKE_OFFLINE_TEST_KEY";chart_id=2;
 check(WorkerInit()==INIT_SUCCEEDED,"worker contention first instance owns lock");
 string registry=g_workerRegistry;key=registry+u"owner";
 GlobalVariableSet(registry+u"slot",73);GlobalVariableSet(registry+u"busy",73);
 double lease=AIState(registry+u"lease");
 // Simulate the second EA's initially false local flag, sharing terminal state.
 bool ownerWorker=g_workerOwned;g_workerOwned=false;chart_id=3;
 check(WorkerInit()==INIT_FAILED&&!g_workerOwned,"worker contention second instance rejected");
 WorkerDeinit(REASON_INITFAILED);
 check(GlobalVariableCheck(key)&&AIState(key)==1&&AIState(registry+u"slot")==73&&AIState(registry+u"busy")==73&&AIState(registry+u"version")==242&&AIState(registry+u"lease")==lease,"rejected worker deinit preserves owner and active registration");
 g_workerOwned=ownerWorker;chart_id=2;WorkerDeinit(REASON_CHARTCHANGE);chart_id=1;

 reset();AccountMode=FINTOKEI;FintokeiInitialBalance=100000;
 check(OnInit()==INIT_SUCCEEDED,"Fintokei contention first controller owns lock");key=g_propControllerKey;
 // Give the contender an empty local state array; retain the first instance.
 std::vector<SymbolState*> ownerSymbols;ownerSymbols.swap(g_symbols);
 bool ownerProp=g_propControllerOwned;g_propControllerOwned=false;chart_id=3;
 check(OnInit()==INIT_FAILED&&!g_propControllerOwned&&g_symbols.empty(),"Fintokei contention second controller rejected before symbol setup");
 OnDeinit(REASON_INITFAILED);
 check(GlobalVariableCheck(key)&&AIState(key)==1&&ownerSymbols.size()==2&&ownerSymbols[0]->g_lockOwned&&AIState(ownerSymbols[0]->g_lockKey)==1,"rejected Fintokei deinit preserves first controller and symbol locks");
 g_symbols.swap(ownerSymbols);g_propControllerOwned=ownerProp;chart_id=1;
 OnDeinit(REASON_CHARTCHANGE);FintokeiInitialBalance=0;
}

void lock_failure_tests(){
 reset();SymbolState s;fail_global=u"MT3L."+IntegerToString((long)TextHash(g_account+u"/FX"));
 check(!s.Init(u"FX",false,true)&&!s.g_lockOwned&&!GlobalVariableCheck(fail_global),"symbol temporary creation failure refuses ownership");s.Shutdown();
 reset();fail_global=g_execKey;
 check(!AcquireExecution()&&!g_execOwned&&!GlobalVariableCheck(g_execKey),"execution temporary creation failure refuses ownership");
 fail_global=u"";GlobalVariableTemp(g_execKey);fail_global=g_execKey;
 check(!AcquireExecution()&&!g_execOwned&&GlobalVariableGet(g_execKey)==0,"execution compare-and-set failure refuses ownership without changing zero");
 reset();OpenAIAPIKey=u"FAKE_OFFLINE_TEST_KEY";fail_global=AIRegistry()+u"owner";
 check(WorkerInit()==INIT_FAILED&&!g_workerOwned&&!GlobalVariableCheck(fail_global),"worker temporary creation failure refuses registration");WorkerDeinit(REASON_INITFAILED);
 reset();AccountMode=FINTOKEI;FintokeiInitialBalance=100000;
 fail_global=u"MT3L."+IntegerToString((long)TextHash(g_account+u"/PROP"));
 check(OnInit()==INIT_FAILED&&!g_propControllerOwned&&!GlobalVariableCheck(fail_global),"Fintokei temporary creation failure refuses ownership");OnDeinit(REASON_INITFAILED);FintokeiInitialBalance=0;
}

void v244_lock_tests(const std::string &only){
 struct Case {const char *name;void (*run)();};
 Case cases[]={{"mock",lock_mock_contract_tests},{"symbol",lock_symbol_reinit_tests},{"chartchange",lock_chartchange_tests},{"execution",lock_execution_reacquire_tests},{"worker",lock_worker_reinit_tests},{"fintokei",lock_fintokei_reinit_tests},{"contention",lock_contention_tests},{"failure",lock_failure_tests}};
 bool found=false;
 for(auto &test:cases)if(only.empty()||only==test.name){found=true;test.run();}
 if(!found){std::cerr<<"Unknown lock regression group: "<<only<<"\n";std::exit(2);}
}

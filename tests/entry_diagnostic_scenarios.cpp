// Exercise actual source and its emitted aggregate contract, not a copied gate.
void entry_diagnostic_tests(){
 reset();tester=true;connected=false;ScanMode=CURRENT_SYMBOL;fixture_pattern(u"FX");
 diagnostic_output.clear();
 check(OnInit()==INIT_SUCCEEDED,"diagnostic AUTO fixture initializes");
 OnTimer();check(order_calls==1,"diagnostic fixture retains the eligible order");
 OnDeinit(0);
 bool found=false;
 for(auto &line:diagnostic_output)if(line.find(u"[MT3 ENTRY SUMMARY]")==0)found=true;
 check(found,"tester emits candidate and first-rejection summary");
}

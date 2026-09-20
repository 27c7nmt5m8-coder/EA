void v245_tests(){
 reset();ExecutionMode=EXECUTION_MANUAL;ScanMode=CURRENT_SYMBOL;symbols[u"FX"].ready=false;
 check(OnInit()==INIT_SUCCEEDED,"MANUAL initializes without indicator history");
 SymbolState &s=*g_symbols[0];
 check(ObjectFind(0,s.ManualName(u"BUY"))>=0&&ObjectFind(0,s.ManualName(u"SELL"))>=0,"MANUAL panel exists before ATR readiness");
 check(object_text[s.ManualName(u"BUY")]==u"BUY [WAIT]"&&object_text[s.ManualName(u"BUY_INFO")].find(u"M1 ATR not ready")!=string::npos,"ATR wait is visible without a false SL error");
 OnDeinit(0);
}

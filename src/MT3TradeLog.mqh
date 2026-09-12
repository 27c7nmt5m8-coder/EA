#ifndef MT3_TRADE_LOG_MQH
#define MT3_TRADE_LOG_MQH
// Analytical data only. Never used to approve an order or redefine core initial risk R.
struct TradeLogRecord
{
 ulong position,order,deal,exitDeal,magic;
 datetime entryTime,exitTime,lastSaved;
 bool buy,closed,aiUsed,hasContext,dirty,restored;
 double entry,sl,tp,riskDistance,riskMoney,riskPercent,lot,score,mtf,patternScore,line,agreement,spread,spreadATR,spreadSL,atr,portfolioBefore,portfolioAfter,plannedRisk,aiConfidence,p1,p2,p3,reference,extreme,exitPrice,gross,commission,swap,fee,net,realizedR,mfe,mae,entryEquity;
 string symbol,account,dataset,mode,pattern,patternId,riskMode,slSource,aiResult,slFallback,exitReason,orderIds,dealIds,excursionCoverage;
};
string g_logRun="";
string TradeLogRoot()
{
 string scope=ScopeDigest(TerminalInfoString(TERMINAL_DATA_PATH)+"/"+g_account+StringFormat("/%I64u",MagicNumber));
 if(MQLInfoInteger(MQL_TESTER) && g_logRun=="") g_logRun="TEST_"+NewAIId();
 return "MT3Logs_v244\\"+scope+"\\"+(MQLInfoInteger(MQL_TESTER)?g_logRun:"LIVE")+"\\";
}
string LogPositionBase(string symbol,ulong id)
{return TradeLogRoot()+ScopeDigest(symbol)+StringFormat("_position_%I64u",id);}
string LogIntentFile(string symbol,string token)
{return TradeLogRoot()+ScopeDigest(symbol)+"_intent_"+token+".json";}
string LogNumber(double n) {return MathIsValidNumber(n)?StringFormat("%.17g",n):"";}
string LogU64(ulong n) {return StringFormat("%I64u",n);}
bool LogParseU64(string value,ulong &result)
{
 result=0;if(StringLen(value)<1 || StringLen(value)>20) return false;
 ulong maximum=~(ulong)0;
 for(int i=0;i<StringLen(value);i++)
 {
  ushort c=StringGetCharacter(value,i);if(c<'0' || c>'9') return false;
  ulong digit=(ulong)(c-'0');if(result>(maximum-digit)/10) return false;
  result=result*10+digit;
 }
 return true;
}
string LogDate(datetime t) {return t>0?TimeToString(t,TIME_DATE|TIME_SECONDS):"";}
string CSVCell(string value,bool text=false)
{
 if(text && StringLen(value)>0)
 {
  ushort c=StringGetCharacter(value,0);
  if(c=='=' || c=='+' || c=='-' || c=='@' || c==9 || c==13) value="'"+value;
 }
 StringReplace(value,"\"","\"\"");return "\""+value+"\"";
}
void LogCSVAdd(string &header,string &row,string name,string value,bool text=false)
{
 if(header!="") {header+=",";row+=",";}
 header+=CSVCell(name);row+=CSVCell(value,text);
}
void LogWarning(string message) {Print("TradeLog warning: ",message,". Trading protection remains active.");}

string TradeRecordJSON(TradeLogRecord &r)
{
 string s="{\"schema\":244";
 s+=",\"position\":"+JsonQuote(LogU64(r.position));
 s+=",\"order\":"+JsonQuote(LogU64(r.order));
 s+=",\"deal\":"+JsonQuote(LogU64(r.deal));
 s+=",\"exitDeal\":"+JsonQuote(LogU64(r.exitDeal));
 s+=",\"magic\":"+JsonQuote(LogU64(r.magic));
 s+=",\"entryTime\":"+IntegerToString((long)r.entryTime);
 s+=",\"exitTime\":"+IntegerToString((long)r.exitTime);
 s+=",\"lastSaved\":"+IntegerToString((long)r.lastSaved);
 s+=",\"buy\":"+IntegerToString(r.buy?1:0);
 s+=",\"closed\":"+IntegerToString(r.closed?1:0);
 s+=",\"aiUsed\":"+IntegerToString(r.aiUsed?1:0);
 s+=",\"hasContext\":"+IntegerToString(r.hasContext?1:0);
 s+=",\"dirty\":"+IntegerToString(r.dirty?1:0);
 s+=",\"restored\":"+IntegerToString(r.restored?1:0);
 s+=",\"entry\":"+(MathIsValidNumber(r.entry)?LogNumber(r.entry):"0");
 s+=",\"sl\":"+(MathIsValidNumber(r.sl)?LogNumber(r.sl):"0");
 s+=",\"tp\":"+(MathIsValidNumber(r.tp)?LogNumber(r.tp):"0");
 s+=",\"riskDistance\":"+(MathIsValidNumber(r.riskDistance)?LogNumber(r.riskDistance):"0");
 s+=",\"riskMoney\":"+(MathIsValidNumber(r.riskMoney)?LogNumber(r.riskMoney):"0");
 s+=",\"riskPercent\":"+(MathIsValidNumber(r.riskPercent)?LogNumber(r.riskPercent):"0");
 s+=",\"lot\":"+(MathIsValidNumber(r.lot)?LogNumber(r.lot):"0");
 s+=",\"score\":"+(MathIsValidNumber(r.score)?LogNumber(r.score):"0");
 s+=",\"mtf\":"+(MathIsValidNumber(r.mtf)?LogNumber(r.mtf):"0");
 s+=",\"patternScore\":"+(MathIsValidNumber(r.patternScore)?LogNumber(r.patternScore):"0");
 s+=",\"line\":"+(MathIsValidNumber(r.line)?LogNumber(r.line):"0");
 s+=",\"agreement\":"+(MathIsValidNumber(r.agreement)?LogNumber(r.agreement):"0");
 s+=",\"spread\":"+(MathIsValidNumber(r.spread)?LogNumber(r.spread):"0");
 s+=",\"spreadATR\":"+(MathIsValidNumber(r.spreadATR)?LogNumber(r.spreadATR):"0");
 s+=",\"spreadSL\":"+(MathIsValidNumber(r.spreadSL)?LogNumber(r.spreadSL):"0");
 s+=",\"atr\":"+(MathIsValidNumber(r.atr)?LogNumber(r.atr):"0");
 s+=",\"portfolioBefore\":"+(MathIsValidNumber(r.portfolioBefore)?LogNumber(r.portfolioBefore):"0");
 s+=",\"portfolioAfter\":"+(MathIsValidNumber(r.portfolioAfter)?LogNumber(r.portfolioAfter):"0");
 s+=",\"plannedRisk\":"+(MathIsValidNumber(r.plannedRisk)?LogNumber(r.plannedRisk):"0");
 s+=",\"aiConfidence\":"+(MathIsValidNumber(r.aiConfidence)?LogNumber(r.aiConfidence):"0");
 s+=",\"p1\":"+(MathIsValidNumber(r.p1)?LogNumber(r.p1):"0");
 s+=",\"p2\":"+(MathIsValidNumber(r.p2)?LogNumber(r.p2):"0");
 s+=",\"p3\":"+(MathIsValidNumber(r.p3)?LogNumber(r.p3):"0");
 s+=",\"reference\":"+(MathIsValidNumber(r.reference)?LogNumber(r.reference):"0");
 s+=",\"extreme\":"+(MathIsValidNumber(r.extreme)?LogNumber(r.extreme):"0");
 s+=",\"exitPrice\":"+(MathIsValidNumber(r.exitPrice)?LogNumber(r.exitPrice):"0");
 s+=",\"gross\":"+(MathIsValidNumber(r.gross)?LogNumber(r.gross):"0");
 s+=",\"commission\":"+(MathIsValidNumber(r.commission)?LogNumber(r.commission):"0");
 s+=",\"swap\":"+(MathIsValidNumber(r.swap)?LogNumber(r.swap):"0");
 s+=",\"fee\":"+(MathIsValidNumber(r.fee)?LogNumber(r.fee):"0");
 s+=",\"net\":"+(MathIsValidNumber(r.net)?LogNumber(r.net):"0");
 s+=",\"realizedR\":"+(MathIsValidNumber(r.realizedR)?LogNumber(r.realizedR):"0");
 s+=",\"mfe\":"+(MathIsValidNumber(r.mfe)?LogNumber(r.mfe):"0");
 s+=",\"mae\":"+(MathIsValidNumber(r.mae)?LogNumber(r.mae):"0");
 s+=",\"entryEquity\":"+(MathIsValidNumber(r.entryEquity)?LogNumber(r.entryEquity):"0");
 s+=",\"symbol\":"+JsonQuote(r.symbol);
 s+=",\"account\":"+JsonQuote(r.account);
 s+=",\"dataset\":"+JsonQuote(r.dataset);
 s+=",\"mode\":"+JsonQuote(r.mode);
 s+=",\"pattern\":"+JsonQuote(r.pattern);
 s+=",\"patternId\":"+JsonQuote(r.patternId);
 s+=",\"riskMode\":"+JsonQuote(r.riskMode);
 s+=",\"slSource\":"+JsonQuote(r.slSource);
 s+=",\"aiResult\":"+JsonQuote(r.aiResult);
 s+=",\"slFallback\":"+JsonQuote(r.slFallback);
 s+=",\"exitReason\":"+JsonQuote(r.exitReason);
 s+=",\"orderIds\":"+JsonQuote(r.orderIds);
 s+=",\"dealIds\":"+JsonQuote(r.dealIds);
 s+=",\"excursionCoverage\":"+JsonQuote(r.excursionCoverage);
 return s+"}";
}
bool ParseTradeRecord(string text,TradeLogRecord &r)
{
 ZeroMemory(r);CMT3Json j;double n=0;string value;
 if(!j.Parse(text) || !j.GetNumber(0,"schema",n) || n!=244) return false;
 if(!j.GetString(0,"position",value) || !LogParseU64(value,r.position)) return false;
 if(!j.GetString(0,"order",value) || !LogParseU64(value,r.order)) return false;
 if(!j.GetString(0,"deal",value) || !LogParseU64(value,r.deal)) return false;
 if(!j.GetString(0,"exitDeal",value) || !LogParseU64(value,r.exitDeal)) return false;
 if(!j.GetString(0,"magic",value) || !LogParseU64(value,r.magic)) return false;
 if(!j.GetNumber(0,"entryTime",n) || n<0 || n>1e12) return false;r.entryTime=(datetime)n;
 if(!j.GetNumber(0,"exitTime",n) || n<0 || n>1e12) return false;r.exitTime=(datetime)n;
 if(!j.GetNumber(0,"lastSaved",n) || n<0 || n>1e12) return false;r.lastSaved=(datetime)n;
 if(!j.GetNumber(0,"buy",n) || (n!=0 && n!=1)) return false;r.buy=n==1;
 if(!j.GetNumber(0,"closed",n) || (n!=0 && n!=1)) return false;r.closed=n==1;
 if(!j.GetNumber(0,"aiUsed",n) || (n!=0 && n!=1)) return false;r.aiUsed=n==1;
 if(!j.GetNumber(0,"hasContext",n) || (n!=0 && n!=1)) return false;r.hasContext=n==1;
 if(!j.GetNumber(0,"dirty",n) || (n!=0 && n!=1)) return false;r.dirty=n==1;
 if(!j.GetNumber(0,"restored",n) || (n!=0 && n!=1)) return false;r.restored=n==1;
 if(!j.GetNumber(0,"entry",r.entry) || !MathIsValidNumber(r.entry)) return false;
 if(!j.GetNumber(0,"sl",r.sl) || !MathIsValidNumber(r.sl)) return false;
 if(!j.GetNumber(0,"tp",r.tp) || !MathIsValidNumber(r.tp)) return false;
 if(!j.GetNumber(0,"riskDistance",r.riskDistance) || !MathIsValidNumber(r.riskDistance)) return false;
 if(!j.GetNumber(0,"riskMoney",r.riskMoney) || !MathIsValidNumber(r.riskMoney)) return false;
 if(!j.GetNumber(0,"riskPercent",r.riskPercent) || !MathIsValidNumber(r.riskPercent)) return false;
 if(!j.GetNumber(0,"lot",r.lot) || !MathIsValidNumber(r.lot)) return false;
 if(!j.GetNumber(0,"score",r.score) || !MathIsValidNumber(r.score)) return false;
 if(!j.GetNumber(0,"mtf",r.mtf) || !MathIsValidNumber(r.mtf)) return false;
 if(!j.GetNumber(0,"patternScore",r.patternScore) || !MathIsValidNumber(r.patternScore)) return false;
 if(!j.GetNumber(0,"line",r.line) || !MathIsValidNumber(r.line)) return false;
 if(!j.GetNumber(0,"agreement",r.agreement) || !MathIsValidNumber(r.agreement)) return false;
 if(!j.GetNumber(0,"spread",r.spread) || !MathIsValidNumber(r.spread)) return false;
 if(!j.GetNumber(0,"spreadATR",r.spreadATR) || !MathIsValidNumber(r.spreadATR)) return false;
 if(!j.GetNumber(0,"spreadSL",r.spreadSL) || !MathIsValidNumber(r.spreadSL)) return false;
 if(!j.GetNumber(0,"atr",r.atr) || !MathIsValidNumber(r.atr)) return false;
 if(!j.GetNumber(0,"portfolioBefore",r.portfolioBefore) || !MathIsValidNumber(r.portfolioBefore)) return false;
 if(!j.GetNumber(0,"portfolioAfter",r.portfolioAfter) || !MathIsValidNumber(r.portfolioAfter)) return false;
 if(!j.GetNumber(0,"plannedRisk",r.plannedRisk) || !MathIsValidNumber(r.plannedRisk)) return false;
 if(!j.GetNumber(0,"aiConfidence",r.aiConfidence) || !MathIsValidNumber(r.aiConfidence)) return false;
 if(!j.GetNumber(0,"p1",r.p1) || !MathIsValidNumber(r.p1)) return false;
 if(!j.GetNumber(0,"p2",r.p2) || !MathIsValidNumber(r.p2)) return false;
 if(!j.GetNumber(0,"p3",r.p3) || !MathIsValidNumber(r.p3)) return false;
 if(!j.GetNumber(0,"reference",r.reference) || !MathIsValidNumber(r.reference)) return false;
 if(!j.GetNumber(0,"extreme",r.extreme) || !MathIsValidNumber(r.extreme)) return false;
 if(!j.GetNumber(0,"exitPrice",r.exitPrice) || !MathIsValidNumber(r.exitPrice)) return false;
 if(!j.GetNumber(0,"gross",r.gross) || !MathIsValidNumber(r.gross)) return false;
 if(!j.GetNumber(0,"commission",r.commission) || !MathIsValidNumber(r.commission)) return false;
 if(!j.GetNumber(0,"swap",r.swap) || !MathIsValidNumber(r.swap)) return false;
 if(!j.GetNumber(0,"fee",r.fee) || !MathIsValidNumber(r.fee)) return false;
 if(!j.GetNumber(0,"net",r.net) || !MathIsValidNumber(r.net)) return false;
 if(!j.GetNumber(0,"realizedR",r.realizedR) || !MathIsValidNumber(r.realizedR)) return false;
 if(!j.GetNumber(0,"mfe",r.mfe) || !MathIsValidNumber(r.mfe)) return false;
 if(!j.GetNumber(0,"mae",r.mae) || !MathIsValidNumber(r.mae)) return false;
 if(!j.GetNumber(0,"entryEquity",r.entryEquity) || !MathIsValidNumber(r.entryEquity)) return false;
 if(!j.GetString(0,"symbol",r.symbol)) return false;
 if(!j.GetString(0,"account",r.account)) return false;
 if(!j.GetString(0,"dataset",r.dataset)) return false;
 if(!j.GetString(0,"mode",r.mode)) return false;
 if(!j.GetString(0,"pattern",r.pattern)) return false;
 if(!j.GetString(0,"patternId",r.patternId)) return false;
 if(!j.GetString(0,"riskMode",r.riskMode)) return false;
 if(!j.GetString(0,"slSource",r.slSource)) return false;
 if(!j.GetString(0,"aiResult",r.aiResult)) return false;
 if(!j.GetString(0,"slFallback",r.slFallback)) return false;
 if(!j.GetString(0,"exitReason",r.exitReason)) return false;
 if(!j.GetString(0,"orderIds",r.orderIds)) return false;
 if(!j.GetString(0,"dealIds",r.dealIds)) return false;
 if(!j.GetString(0,"excursionCoverage",r.excursionCoverage)) return false;
 return r.account==g_account && r.magic==MagicNumber;
}
string TradeRecordCSV(TradeLogRecord &r)
{
 string h="",row="";
 LogCSVAdd(h,row,"SchemaVersion","244");
 LogCSVAdd(h,row,"DatasetID",r.dataset,true);
 LogCSVAdd(h,row,"RecordKey",r.dataset+"/"+ScopeDigest(r.symbol)+"/"+LogU64(r.position),true);
 LogCSVAdd(h,row,"Status",r.closed?"CLOSED":"OPEN",true);
 LogCSVAdd(h,row,"DateTime",LogDate(r.entryTime),true);
 LogCSVAdd(h,row,"Account",r.account,true);
 LogCSVAdd(h,row,"Symbol",r.symbol,true);
 LogCSVAdd(h,row,"MagicNumber",LogU64(r.magic));
 LogCSVAdd(h,row,"PositionIdentifier",LogU64(r.position));
 LogCSVAdd(h,row,"OrderID",LogU64(r.order));
 LogCSVAdd(h,row,"DealID",LogU64(r.deal));
 LogCSVAdd(h,row,"OrderIDs",r.orderIds,true);
 LogCSVAdd(h,row,"DealIDs",r.dealIds,true);
 LogCSVAdd(h,row,"ExecutionMode",r.mode,true);
 LogCSVAdd(h,row,"PatternName",r.pattern,true);
 LogCSVAdd(h,row,"PatternDirection",r.buy?"BUY":"SELL",true);
 LogCSVAdd(h,row,"PatternID",r.patternId,true);
 LogCSVAdd(h,row,"EntryPrice",LogNumber(r.entry));
 LogCSVAdd(h,row,"InitialSL",LogNumber(r.sl));
 LogCSVAdd(h,row,"InitialTP",LogNumber(r.tp));
 LogCSVAdd(h,row,"InitialRiskPriceDistance",r.riskDistance>0?LogNumber(r.riskDistance):"");
 LogCSVAdd(h,row,"InitialRiskAccountCurrency",r.riskMoney>0?LogNumber(r.riskMoney):"");
 LogCSVAdd(h,row,"InitialRiskPercent",r.riskPercent>0?LogNumber(r.riskPercent):"");
 LogCSVAdd(h,row,"LotSize",LogNumber(r.lot));
 LogCSVAdd(h,row,"FinalScore",r.hasContext?LogNumber(r.score):"");
 LogCSVAdd(h,row,"MTFScore",r.hasContext?LogNumber(r.mtf):"");
 LogCSVAdd(h,row,"PatternScore",r.hasContext?LogNumber(r.patternScore):"");
 LogCSVAdd(h,row,"NormalizedLineScore",r.hasContext?LogNumber(r.line):"");
 LogCSVAdd(h,row,"WeightedAgreement",r.hasContext?LogNumber(r.agreement):"");
 LogCSVAdd(h,row,"Spread",r.hasContext?LogNumber(r.spread):"");
 LogCSVAdd(h,row,"SpreadATRRatio",r.hasContext?LogNumber(r.spreadATR):"");
 LogCSVAdd(h,row,"SpreadSLRatio",r.hasContext?LogNumber(r.spreadSL):"");
 LogCSVAdd(h,row,"ATR_M1",r.hasContext?LogNumber(r.atr):"");
 LogCSVAdd(h,row,"RiskMode",r.riskMode,true);
 LogCSVAdd(h,row,"PortfolioRiskBeforeEntry",r.portfolioBefore>=0?LogNumber(r.portfolioBefore):"");
 LogCSVAdd(h,row,"PortfolioRiskAfterEntry",r.portfolioAfter>=0?LogNumber(r.portfolioAfter):"");
 LogCSVAdd(h,row,"PlannedNewTradeRisk",r.plannedRisk>=0?LogNumber(r.plannedRisk):"");
 LogCSVAdd(h,row,"AIUsed",r.aiUsed?"1":"0");
 LogCSVAdd(h,row,"AIConfidence",r.aiConfidence>=0?LogNumber(r.aiConfidence):"");
 LogCSVAdd(h,row,"AIResult",r.aiResult,true);
 LogCSVAdd(h,row,"P1",r.hasContext?LogNumber(r.p1):"");
 LogCSVAdd(h,row,"P2",r.hasContext?LogNumber(r.p2):"");
 LogCSVAdd(h,row,"P3",r.hasContext?LogNumber(r.p3):"");
 LogCSVAdd(h,row,"FailedBreakoutReference",r.hasContext?LogNumber(r.reference):"");
 LogCSVAdd(h,row,"PatternExtreme",r.hasContext?LogNumber(r.extreme):"");
 LogCSVAdd(h,row,"SLSource",r.slSource,true);
 LogCSVAdd(h,row,"SLFallbackReason",r.slFallback,true);
 LogCSVAdd(h,row,"ContextStatus",r.hasContext?"CAPTURED":"MISSING_ENTRY_CONTEXT",true);
 LogCSVAdd(h,row,"EntryEquity",r.entryEquity>0?LogNumber(r.entryEquity):"");
 LogCSVAdd(h,row,"ExitDateTime",LogDate(r.exitTime),true);
 LogCSVAdd(h,row,"ExitPrice",r.closed?LogNumber(r.exitPrice):"");
 LogCSVAdd(h,row,"ExitReason",r.closed?r.exitReason:"",true);
 LogCSVAdd(h,row,"GrossProfit",r.closed?LogNumber(r.gross):"");
 LogCSVAdd(h,row,"Commission",r.closed?LogNumber(r.commission):"");
 LogCSVAdd(h,row,"Swap",r.closed?LogNumber(r.swap):"");
 LogCSVAdd(h,row,"Fees",r.closed?LogNumber(r.fee):"");
 LogCSVAdd(h,row,"NetProfit",r.closed?LogNumber(r.net):"");
 LogCSVAdd(h,row,"RealizedR",r.closed && r.riskMoney>0?LogNumber(r.realizedR):"");
 LogCSVAdd(h,row,"HoldingTimeSeconds",r.closed?IntegerToString((long)MathMax(0,r.exitTime-r.entryTime)):"");
 LogCSVAdd(h,row,"MFE_R",r.riskDistance>0?LogNumber(r.mfe/r.riskDistance):"");
 LogCSVAdd(h,row,"MAE_R",r.riskDistance>0?LogNumber(r.mae/r.riskDistance):"");
 LogCSVAdd(h,row,"ExcursionCoverage",r.excursionCoverage,true);
 LogCSVAdd(h,row,"Result",!r.closed?"":(r.net>BreakEvenMoneyTolerance?"WIN":(r.net<-BreakEvenMoneyTolerance?"LOSS":"BREAKEVEN")),true);
 return ShortToString(0xFEFF)+h+"\r\n"+row+"\r\n";
}
#endif

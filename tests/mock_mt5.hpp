// Offline test doubles. They exercise source control flow, not a broker implementation.
double MathFloor(double x){return std::floor(x);}double MathCeil(double x){return std::ceil(x);}double MathRound(double x){return std::round(x);}
double NormalizeDouble(double x,int d){double p=std::pow(10,d);return std::round(x*p)/p;}
uint mock_rng=1;void MathSrand(int n){mock_rng=n;}int MathRand(){mock_rng=mock_rng*1103515245+12345;return (mock_rng>>16)&32767;}
template<class T,size_t N>int ArraySize(const T(&)[N]){return N;}
template<class T>int ArrayCopy(std::vector<T>&out,const std::vector<T>&in){out=in;return out.size();}
template<class T>int ArrayBsearch(const std::vector<T>&a,T n){auto p=std::lower_bound(a.begin(),a.end(),n);return p==a.end()?(a.empty()?-1:(int)a.size()-1):(int)(p-a.begin());}
template<class T>void ArraySetAsSeries(T&,bool){}
int StringReplace(string&s,string a,string b){int n=0;size_t p=0;while((p=s.find(a,p))!=string::npos){s.replace(p,a.size(),b);p+=b.size();n++;}return n;}
int StringTrimLeft(string&s){int n=0;while(!s.empty() && std::isspace((char)s[0])){s.erase(s.begin());n++;}return n;}
int StringTrimRight(string&s){int n=0;while(!s.empty() && std::isspace((char)s.back())){s.pop_back();n++;}return n;}
int StringSplit(string s,ushort sep,std::vector<string>&a){a.clear();size_t start=0;while(true){size_t p=s.find(sep,start);a.push_back(s.substr(start,p==string::npos?p:p-start));if(p==string::npos)break;start=p+1;}return a.size();}
template<class T>string EnumToString(T n){return IntegerToString((int)n);}
ulong mono=100000;datetime server_time=1700000041;long chart_id=1;
bool profit_ok=true;string fail_file_pattern=u"";
bool tester=false,permissions=true,connected=true,history_ok=true,queue_ok=true,file_ok=true;
string fail_global=u"";int chart_operations=0,order_calls=0,http_calls=0,modify_calls=0,close_calls=0;
ulong ordercheck_advance=0;uint broker_retcode=TRADE_RETCODE_DONE;bool fill_visible=true,position_visible=true,deal_only=false;
string http_fixture,last_http_body;int http_code=200;
long margin_mode=ACCOUNT_MARGIN_MODE_RETAIL_HEDGING;double equity=100000,balance=100000,free_margin=100000;
datetime TimeCurrent(){return server_time;}datetime TimeTradeServer(){return server_time;}
datetime TimeLocal(){return 1800000000;}datetime TimeGMT(){return server_time;}
ulong GetTickCount64(){return mono;}ulong GetMicrosecondCount(){static ulong serial=0;return mono*1000+(++serial);}
long ChartID(){return chart_id;}
string TimeToString(datetime n,int){return IntegerToString(n);}
string _Symbol=u"FX";
std::map<string,double> globals;
const int ERR_GLOBALVARIABLE_EXISTS=4502;
int mock_last_error=0;
bool GlobalVariableCheck(string k){return globals.count(k);}
double GlobalVariableGet(string k){return globals.count(k)?globals[k]:0;}
datetime GlobalVariableSet(string k,double v){if(k==fail_global)return 0;globals[k]=v;return server_time;}
bool GlobalVariableSetOnCondition(string k,double v,double expected){if(k==fail_global || !globals.count(k) || globals[k]!=expected)return false;globals[k]=v;return true;}
bool GlobalVariableTemp(string k){if(globals.count(k)){mock_last_error=ERR_GLOBALVARIABLE_EXISTS;return false;}if(k==fail_global)return false;globals[k]=0;return true;}
bool GlobalVariableDel(string k){return globals.erase(k);}
int GlobalVariablesTotal(){return globals.size();}
string GlobalVariableName(int i){auto p=globals.begin();std::advance(p,i);return p->first;}
int GlobalVariablesDeleteAll(string prefix){int n=0;for(auto p=globals.begin();p!=globals.end();)if(p->first.find(prefix)==0){p=globals.erase(p);n++;}else ++p;return n;}
void GlobalVariablesFlush(){}
long TerminalInfoInteger(int k){return k==TERMINAL_CONNECTED?connected:permissions;}
long MQLInfoInteger(int k){return k==MQL_TESTER?tester:permissions;}
long AccountInfoInteger(int k){return k==ACCOUNT_LOGIN?123456:k==ACCOUNT_MARGIN_MODE?margin_mode:permissions;}
double AccountInfoDouble(int k){return k==ACCOUNT_EQUITY?equity:k==ACCOUNT_BALANCE?balance:free_margin;}
string AccountInfoString(int){return u"MOCK_SERVER";}string TerminalInfoString(int){return u"MOCK_TERMINAL";}
struct MqlTick{datetime time=0;double bid=0,ask=0,last=0;ulong volume=0;long time_msc=0;uint flags=0;double volume_real=0;};
struct MqlRates{datetime time;double open,high,low,close;long tick_volume;int spread;long real_volume;};
struct MqlTradeRequest{int action=0;ulong magic=0;string symbol,comment;int type=0,type_filling=0;double volume=0,price=0,sl=0,tp=0;ulong deviation=0;};
struct MqlTradeCheckResult{uint retcode=0;string comment;};
struct MqlTradeResult{uint retcode=0;ulong order=0,deal=0;};
struct MqlTradeTransaction{int type=0;string symbol;};
struct MockSymbol{
 double point=.01,tick=.01,bid=100,ask=100.02,atr=2,minLot=.01,maxLot=100,step=.01,volumeLimit=0,contract=1000,marginPerLot=100;
 int digits=2,stops=0,freeze=0,mode=SYMBOL_TRADE_MODE_FULL;bool visible=true,selected=true,custom=false,ready=true;
 long tickMs=server_time*1000;int orderMode=SYMBOL_ORDER_MARKET|SYMBOL_ORDER_SL|SYMBOL_ORDER_TP;
};
std::map<string,MockSymbol> symbols;
struct Series {std::vector<double> high,low,close,open;};std::map<string,Series> series;
double SymbolInfoDouble(string s,int k){if(!symbols.count(s))return 0;auto &v=symbols.at(s);
 if(k==SYMBOL_POINT)return v.point;if(k==SYMBOL_TRADE_TICK_SIZE)return v.tick;
 if(k==SYMBOL_VOLUME_MIN)return v.minLot;if(k==SYMBOL_VOLUME_MAX)return v.maxLot;if(k==SYMBOL_VOLUME_STEP)return v.step;
 if(k==SYMBOL_VOLUME_LIMIT)return v.volumeLimit;if(k==SYMBOL_BID)return v.bid;if(k==SYMBOL_ASK)return v.ask;return 0;}
bool SymbolInfoDouble(string s,int k,double &v){v=SymbolInfoDouble(s,k);return symbols.count(s);}
long SymbolInfoInteger(string s,int k){if(!symbols.count(s))return 0;auto &v=symbols.at(s);
 if(k==SYMBOL_DIGITS)return v.digits;if(k==SYMBOL_TRADE_STOPS_LEVEL)return v.stops;if(k==SYMBOL_TRADE_FREEZE_LEVEL)return v.freeze;
 if(k==SYMBOL_TRADE_MODE)return v.mode;if(k==SYMBOL_ORDER_MODE)return v.orderMode;if(k==SYMBOL_CUSTOM)return v.custom;
 if(k==SYMBOL_VISIBLE)return v.visible;if(k==SYMBOL_SELECT)return v.selected;if(k==SYMBOL_FILLING_MODE)return SYMBOL_FILLING_FOK;
 return 0;}
bool SymbolInfoTick(string s,MqlTick&t){if(!symbols.count(s))return false;auto &v=symbols.at(s);t.bid=v.bid;t.ask=v.ask;t.time_msc=v.tickMs;t.time=t.time_msc/1000;return true;}
bool SymbolSelect(string s,bool select){if(!symbols.count(s))return false;symbols[s].selected=select;return true;}
int SymbolsTotal(bool selected){int n=0;for(auto &[k,v]:symbols)if(!selected || v.selected)n++;return n;}
string SymbolName(int i,bool selected){for(auto &[k,v]:symbols)if(!selected || v.selected){if(i--==0)return k;}return u"";}
int PeriodSeconds(int tf){if(tf==PERIOD_M1)return 60;if(tf==PERIOD_M5)return 300;if(tf==PERIOD_M15)return 900;if(tf==PERIOD_M30)return 1800;if(tf==PERIOD_H1)return 3600;if(tf==PERIOD_H4)return 14400;if(tf==PERIOD_D1)return 86400;return 60;}
datetime iTime(string s,int tf,int shift){return symbols.count(s)?server_time/PeriodSeconds(tf)*PeriodSeconds(tf)-shift*PeriodSeconds(tf):0;}
int Bars(string s,int){return symbols.count(s) && symbols[s].ready?1000:0;}
double iClose(string s,int tf,int shift){if(tf==PERIOD_M1 && series.count(s) && shift<(int)series[s].close.size())return series[s].close[shift];return symbols.count(s)?symbols[s].bid-shift*symbols[s].atr*.05:0;}
double iOpen(string s,int tf,int shift){if(tf==PERIOD_M1 && series.count(s) && shift<(int)series[s].open.size())return series[s].open[shift];return iClose(s,tf,shift);}
double iHigh(string s,int tf,int shift){if(tf==PERIOD_M1 && series.count(s) && shift<(int)series[s].high.size())return series[s].high[shift];return iClose(s,tf,shift)+symbols[s].atr*.2;}
double iLow(string s,int tf,int shift){if(tf==PERIOD_M1 && series.count(s) && shift<(int)series[s].low.size())return series[s].low[shift];return iClose(s,tf,shift)-symbols[s].atr*.2;}
int iLowest(string,int,int,int,int start){return start;}int iHighest(string,int,int,int,int start){return start;}
int CopyRates(string s,int tf,int shift,int count,std::vector<MqlRates>&r){if(!symbols.count(s)||!symbols[s].ready)return -1;r.resize(count);for(int i=0;i<count;i++){r[i]={iTime(s,tf,i+shift),iClose(s,tf,i+shift),iHigh(s,tf,i+shift),iLow(s,tf,i+shift),iClose(s,tf,i+shift),100,2,100};}return count;}
struct Indicator{string symbol;int kind,tf,period,fast=0,slow=0,signal=0;bool requested=false;};std::map<int,Indicator> indicators;int next_handle=1;
int AddIndicator(string s,int kind,int tf,int period,int f=0,int slow=0,int sig=0){int h=next_handle++;indicators[h]={s,kind,tf,period,f,slow,sig};return h;}
int iATR(string s,int tf,int p){return AddIndicator(s,0,tf,p);}int iMA(string s,int tf,int p,int,int,int){return AddIndicator(s,1,tf,p);}
int iADX(string s,int tf,int p){return AddIndicator(s,2,tf,p);}int iMACD(string s,int tf,int f,int slow,int sig,int){return AddIndicator(s,3,tf,0,f,slow,sig);}
// Non-visual MT5 tests calculate indicators on buffer demand, not handle creation.
int BarsCalculated(int h){return indicators.count(h) && symbols[indicators[h].symbol].ready && (!tester || indicators[h].requested)?1000:0;}
bool IndicatorRelease(int h){return indicators.erase(h);}
template<class T>int CopyBuffer(int h,int buffer,int shift,int,T&a){if(!indicators.count(h) || !symbols[indicators[h].symbol].ready)return -1;
 auto &d=indicators.at(h);d.requested=true;auto &s=symbols.at(d.symbol);double v=0;
 if(d.kind==0)v=s.atr;
 if(d.kind==1)v=s.bid-s.atr*(d.period==20?.20:d.period==50?.5:1.8)-(shift-1)*s.atr*.10;
 if(d.kind==2)v=buffer==0?32:buffer==1?35:10;
 if(d.kind==3)v=s.atr*(buffer==0?.25:.10)-(shift-1)*(buffer==0?s.atr*.025:0);
 a[0]=v;return 1;}
struct MockOrder{ulong id=0,magic=26090201,position=0;string symbol,comment;long state=ORDER_STATE_FILLED,type=ORDER_TYPE_BUY;double initial=.1,current=0,sl=0;};
struct MockDeal{ulong id=0,magic=26090201,order=0,position=0;string symbol;long type=DEAL_TYPE_BUY,entry=DEAL_ENTRY_IN;datetime time=0;double volume=.1,price=100,sl=98,profit=0,swap=0,commission=0,fee=0,tp=0;long reason=DEAL_REASON_EXPERT;};
struct MockPosition{ulong id=0,magic=26090201;string symbol;long type=POSITION_TYPE_BUY;double volume=.1,open=100,sl=98,tp=102;};
std::map<ulong,MockOrder> active_orders,history_orders;std::map<ulong,MockDeal> history_deals;std::map<ulong,MockPosition> positions;
std::vector<ulong> hist_order_view,hist_deal_view;ulong selected_order=0,selected_position=0;
int PositionsTotal(){return positions.size();}int OrdersTotal(){return active_orders.size();}
ulong PositionGetTicket(int i){auto p=positions.begin();std::advance(p,i);selected_position=p->first;return selected_position;}
bool PositionSelectByTicket(ulong n){selected_position=n;return positions.count(n);}
string PositionGetString(int){return positions.at(selected_position).symbol;}
long PositionGetInteger(int k){auto &p=positions.at(selected_position);return k==POSITION_MAGIC?p.magic:k==POSITION_IDENTIFIER?p.id:p.type;}
double PositionGetDouble(int k){auto &p=positions.at(selected_position);return k==POSITION_VOLUME?p.volume:k==POSITION_PRICE_OPEN?p.open:k==POSITION_SL?p.sl:p.tp;}
ulong OrderGetTicket(int i){auto p=active_orders.begin();std::advance(p,i);selected_order=p->first;return selected_order;}
bool OrderSelect(ulong n){selected_order=n;return active_orders.count(n);}
string OrderGetString(int k){auto&o=active_orders.at(selected_order);return k==ORDER_SYMBOL?o.symbol:o.comment;}
long OrderGetInteger(int k){auto&o=active_orders.at(selected_order);return k==ORDER_MAGIC?o.magic:k==ORDER_TYPE?o.type:o.state;}
double OrderGetDouble(int){return active_orders.at(selected_order).current;}
bool HistorySelect(datetime from,datetime to){if(!history_ok)return false;hist_order_view.clear();hist_deal_view.clear();for(auto &[k,v]:history_orders)hist_order_view.push_back(k);for(auto &[k,v]:history_deals)if(v.time>=from && v.time<=to)hist_deal_view.push_back(k);return true;}
bool HistorySelectByPosition(ulong id){if(!history_ok)return false;hist_order_view.clear();hist_deal_view.clear();for(auto &[k,v]:history_orders)if(v.position==id)hist_order_view.push_back(k);for(auto &[k,v]:history_deals)if(v.position==id)hist_deal_view.push_back(k);return !hist_deal_view.empty();}
bool HistoryOrderSelect(ulong n){return history_ok && history_orders.count(n);}
bool HistoryDealSelect(ulong n){return history_ok && history_deals.count(n);}
int HistoryOrdersTotal(){return hist_order_view.size();}int HistoryDealsTotal(){return hist_deal_view.size();}
ulong HistoryOrderGetTicket(int i){return hist_order_view.at(i);}ulong HistoryDealGetTicket(int i){return hist_deal_view.at(i);}
string HistoryOrderGetString(ulong n,int k){if(!history_orders.count(n))return u"";auto&o=history_orders.at(n);return k==ORDER_SYMBOL?o.symbol:o.comment;}
long HistoryOrderGetInteger(ulong n,int k){if(!history_orders.count(n))return 0;auto&o=history_orders.at(n);return k==ORDER_MAGIC?o.magic:k==ORDER_STATE?o.state:o.position;}
double HistoryOrderGetDouble(ulong n,int k){if(!history_orders.count(n))return 0;auto&o=history_orders.at(n);return k==ORDER_VOLUME_INITIAL?o.initial:k==ORDER_VOLUME_CURRENT?o.current:o.sl;}
string HistoryDealGetString(ulong n,int){return history_deals.count(n)?history_deals.at(n).symbol:u"";}
long HistoryDealGetInteger(ulong n,int k){if(!history_deals.count(n))return 0;auto&d=history_deals.at(n);return k==DEAL_MAGIC?d.magic:k==DEAL_TYPE?d.type:k==DEAL_ENTRY?d.entry:k==DEAL_ORDER?d.order:k==DEAL_POSITION_ID?d.position:k==DEAL_REASON?d.reason:d.time;}
double HistoryDealGetDouble(ulong n,int k){if(!history_deals.count(n))return 0;auto&d=history_deals.at(n);return k==DEAL_VOLUME?d.volume:k==DEAL_PRICE?d.price:k==DEAL_SL?d.sl:k==DEAL_TP?d.tp:k==DEAL_PROFIT?d.profit:k==DEAL_SWAP?d.swap:k==DEAL_COMMISSION?d.commission:d.fee;}
bool OrderCalcProfit(int type,string s,double lot,double open,double close,double &profit){if(!profit_ok || !symbols.count(s))return false;profit=(type==ORDER_TYPE_BUY?close-open:open-close)*lot*symbols[s].contract;return true;}
bool OrderCalcMargin(int,string s,double lot,double,double &margin){margin=lot*symbols[s].marginPerLot;return true;}
std::function<void()> during_ordercheck;
MqlTradeRequest last_check;MqlTradeResult last_result;
bool OrderCheck(MqlTradeRequest&r,MqlTradeCheckResult&c){last_check=r;mono+=ordercheck_advance;if(during_ordercheck)during_ordercheck();c.retcode=TRADE_RETCODE_DONE;return true;}
bool MockDurableIntent(string,ulong);
class CTrade{ulong magic=0,deviation=0;public:
 void SetExpertMagicNumber(ulong n){magic=n;}void SetDeviationInPoints(ulong n){deviation=n;}
 void SetAsyncMode(bool){}void SetMarginMode(){}bool SetTypeFillingBySymbol(string){return true;}
 bool Send(bool buy,double lot,string symbol,double price,double sl,double tp,string comment){
  if(!MockDurableIntent(symbol,magic)){std::cerr<<"Intent missing before order\n";std::exit(4);}
  order_calls++;last_result={broker_retcode,0,0};
  if(broker_retcode==TRADE_RETCODE_DONE || broker_retcode==TRADE_RETCODE_DONE_PARTIAL || broker_retcode==TRADE_RETCODE_PLACED){
   ulong id=1000+order_calls;last_result.order=deal_only?0:id;last_result.deal=id+1000;
   MockOrder o;o.id=id;o.magic=magic;o.position=id;o.symbol=symbol;o.comment=comment;o.sl=sl;o.initial=lot;
   o.type=buy?ORDER_TYPE_BUY:ORDER_TYPE_SELL;o.state=broker_retcode==TRADE_RETCODE_PLACED?ORDER_STATE_PLACED:ORDER_STATE_FILLED;
   if(fill_visible){if(broker_retcode==TRADE_RETCODE_PLACED){o.current=lot;active_orders[id]=o;}else history_orders[id]=o;
    MockDeal d;d.id=id+1000;d.magic=magic;d.position=id;d.order=id;d.symbol=symbol;d.type=buy?DEAL_TYPE_BUY:DEAL_TYPE_SELL;d.time=server_time;d.volume=lot;d.price=price;d.sl=sl;d.tp=tp;history_deals[d.id]=d;
    if(position_visible && broker_retcode!=TRADE_RETCODE_PLACED)positions[id]={id,magic,symbol,buy?POSITION_TYPE_BUY:POSITION_TYPE_SELL,lot,price,sl,tp};}
   return true;
  }return false;
 }
 bool Buy(double lot,string s,double p,double sl,double tp,string c){return Send(true,lot,s,p,sl,tp,c);}
 bool Sell(double lot,string s,double p,double sl,double tp,string c){return Send(false,lot,s,p,sl,tp,c);}
 void Result(MqlTradeResult&r){r=last_result;}uint ResultRetcode(){return last_result.retcode;}
 string ResultRetcodeDescription(){return IntegerToString(last_result.retcode);}
 bool PositionModify(ulong id,double sl,double tp){if(!positions.count(id))return false;positions[id].sl=sl;positions[id].tp=tp;modify_calls++;last_result.retcode=TRADE_RETCODE_DONE;return true;}
 bool PositionClose(ulong id,ulong){close_calls++;last_result.retcode=TRADE_RETCODE_DONE;return positions.erase(id);}
};
std::map<string,std::vector<uchar>> files;
struct OpenFile{string name;int flags;};std::map<int,OpenFile> open_files;int next_file=1;
int FileOpen(string name,int flags){if(!file_ok || ((flags&FILE_WRITE)&&!fail_file_pattern.empty()&&name.find(fail_file_pattern)!=string::npos) || ((flags&FILE_READ)&&!files.count(name)))return INVALID_HANDLE;int h=next_file++;open_files[h]={name,flags};return h;}
template<class T>uint FileWriteArray(int h,const std::vector<T>&a,int start,int count){if(!open_files.count(h))return 0;files[open_files[h].name]=std::vector<uchar>(a.begin()+start,a.begin()+start+count);return count;}
template<class T>uint FileReadArray(int h,std::vector<T>&a,int start,int count){if(!open_files.count(h))return 0;auto&v=files[open_files[h].name];a.assign(v.begin(),v.end());return a.size();}
void FileFlush(int){}void FileClose(int h){open_files.erase(h);}ulong FileSize(int h){return files[open_files[h].name].size();}
bool FileDelete(string n,int){return files.erase(n);}bool FileIsExist(string n,int){return files.count(n);}
bool FileMove(string from,int,string to,int){if(!file_ok || !files.count(from))return false;files[to]=files[from];files.erase(from);return true;}
template<class T>int StringToCharArray(const string&s,std::vector<T>&v,int,int,int){auto b=utf8(s);v.assign(b.begin(),b.end());v.push_back(0);return v.size();}
template<class T>string CharArrayToString(const std::vector<T>&v,int start,int count,int){if(count<0)count=v.size()-start;return wide(std::string(v.begin()+start,v.begin()+start+count));}
struct Event{long dest;int event;long sender;double token;string id;};std::vector<Event> events;
bool EventChartCustom(long dest,int event,long sender,double token,string id){if(!queue_ok)return false;events.push_back({dest,event,sender,token,id});return true;}
bool EventSetTimer(int){return true;}bool EventSetMillisecondTimer(int){return true;}void EventKillTimer(){}
void ResetLastError(){mock_last_error=0;}int GetLastError(){return mock_last_error;}std::function<void()> during_http;
int WebRequest(string,string,string,int,const std::vector<char>&data,std::vector<char>&result,string&){http_calls++;last_http_body=wide(std::string(data.begin(),data.end()));if(during_http)during_http();auto b=utf8(http_fixture);result.assign(b.begin(),b.end());return http_code;}
template<class...T>void Comment(T...){}
std::map<string,double> objects;
int ObjectFind(long,string s){return objects.count(s)?0:-1;}
template<class...T>bool ObjectCreate(long,string s,T...){objects[s]=100;chart_operations++;return true;}
bool ObjectDelete(long,string s){chart_operations++;return objects.erase(s);}
int ObjectsTotal(long,int,int){return objects.size();}string ObjectName(long,int i,int,int){auto p=objects.begin();std::advance(p,i);return p->first;}
bool ObjectSetDouble(long,string s,int,double v){objects[s]=v;chart_operations++;return true;}
double ObjectGetDouble(long,string s,int){return objects[s];}long ObjectGetInteger(long,string,int){return OBJ_HLINE;}
template<class...T>bool ObjectSetInteger(T...){chart_operations++;return true;}template<class...T>bool ObjectSetString(T...){chart_operations++;return true;}
template<class...T>bool ObjectMove(T...){chart_operations++;return true;}
long ChartGetInteger(long,int){return 0;}bool ChartGetInteger(long,int,int,long&v){v=0;return true;}
bool ChartGetDouble(long,int,int,double&v){v=0;return true;}
template<class...T>bool ChartSetInteger(T...){chart_operations++;return true;}template<class...T>bool ChartSetDouble(T...){chart_operations++;return true;}
void ChartRedraw(){chart_operations++;}

std::map<long,std::vector<string>> file_searches;std::map<long,int> file_search_at;long next_search=1;
long FileFindFirst(string pattern,string &name,int){
 auto at=pattern.find('*');string prefix=pattern.substr(0,at),suffix=at==string::npos?u"":pattern.substr(at+1);std::vector<string> found;
 for(auto &kv:files){auto key=kv.first;if(key.find(prefix)!=0||key.size()<prefix.size()+suffix.size()||key.substr(key.size()-suffix.size())!=suffix)continue;auto sep=key.find_last_of(u"\\/");found.push_back(sep==string::npos?key:key.substr(sep+1));}
 if(found.empty())return INVALID_HANDLE;long h=next_search++;file_searches[h]=found;file_search_at[h]=0;name=found[0];return h;
}
bool FileFindNext(long h,string &name){if(!file_searches.count(h))return false;int n=++file_search_at[h];if(n>=(int)file_searches[h].size())return false;name=file_searches[h][n];return true;}
void FileFindClose(long h){file_searches.erase(h);file_search_at.erase(h);}

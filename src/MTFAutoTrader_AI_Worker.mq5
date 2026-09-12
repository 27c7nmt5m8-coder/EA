#property strict
#property version "2.44"
#property description "OpenAI communication worker for MTFAutoTrader. This EA never sends trade orders."
#include "MT3AIProtocol.mqh"
input string OpenAIAPIKey="";
input int OpenAITimeoutMs=8000;
// This worker intentionally uses only the official HTTPS endpoint.
const string OpenAIEndpoint="https://api.openai.com/v1/responses";
string g_workerRegistry="";
bool g_workerOwned=false;
double g_observedSlot=0;
ulong g_slotObservedAt=0;
string g_cleanupFiles[];
ulong g_cleanupTimes[];
void WorkerHeartbeat(int allowanceMs=5000)
{GlobalVariableSet(g_workerRegistry+"lease",(double)(GetTickCount64()+(ulong)allowanceMs));}
void WorkerRelease(double token)
{GlobalVariableSetOnCondition(g_workerRegistry+"busy",0,token);GlobalVariableSetOnCondition(g_workerRegistry+"slot",0,token);WorkerHeartbeat();}
void WorkerReply(long chart,string id,double token,string status,string decision,double confidence,string reason)
{
 if(FileIsExist(AIFile(id,".req"),FILE_COMMON))
 {
  string body="{\"protocol\":242,\"id\":"+JsonQuote(id)+",\"chart\":"+JsonQuote(StringFormat("%I64d",chart))+
   ",\"status\":"+JsonQuote(status)+",\"decision\":"+JsonQuote(decision)+",\"confidence\":"+StringFormat("%.17g",confidence)+",\"reason\":"+JsonQuote(reason)+"}";
  string file=AIFile(id,".res");
  if(WriteAIFile(file,body))
  {
   EventChartCustom(chart,MT3_AI_REPLY_EVENT,ChartID(),token,id);
   int n=ArraySize(g_cleanupFiles);ArrayResize(g_cleanupFiles,n+1);ArrayResize(g_cleanupTimes,n+1);
   g_cleanupFiles[n]=file;g_cleanupTimes[n]=GetTickCount64()+120000;
  }
 }
 WorkerRelease(token);
}
int OnInit()
{
 if(MQLInfoInteger(MQL_TESTER)) {Print("AI worker cannot run in Strategy Tester.");return INIT_PARAMETERS_INCORRECT;}
 if(StringLen(OpenAIAPIKey)<10 || StringFind(OpenAIAPIKey,"\r")>=0 || StringFind(OpenAIAPIKey,"\n")>=0 || OpenAITimeoutMs<1000 || OpenAITimeoutMs>60000)
 {Print("Set the API key and a timeout between 1000 and 60000 ms on the worker.");return INIT_PARAMETERS_INCORRECT;}
 g_workerRegistry=AIRegistry();
 if(!GlobalVariableTemp(g_workerRegistry+"owner") || !GlobalVariableSetOnCondition(g_workerRegistry+"owner",1,0))
 {Print("Keep one AI worker in this terminal/account. Remove the previous worker before starting another.");return INIT_FAILED;}
 g_workerOwned=true;
 if(!SaveU64(g_workerRegistry+"chart",(ulong)ChartID()) || GlobalVariableSet(g_workerRegistry+"slot",0)==0 || GlobalVariableSet(g_workerRegistry+"busy",0)==0 ||
     GlobalVariableSet(g_workerRegistry+"version",MT3_AI_PROTOCOL)==0)
 {Print("Worker registration failed.");return INIT_FAILED;}
 WorkerHeartbeat();
 if(!EventSetTimer(1)) return INIT_FAILED;
 Comment("MTF AI Worker v2.44\nReady | communication only\nAllow https://api.openai.com in MT5 WebRequest settings.");
 return INIT_SUCCEEDED;
}
void OnDeinit(const int reason)
{
 EventKillTimer();
 if(g_workerOwned)
 {
  GlobalVariableSet(g_workerRegistry+"busy",0);GlobalVariableSet(g_workerRegistry+"version",0);GlobalVariableSet(g_workerRegistry+"lease",0);GlobalVariableSet(g_workerRegistry+"slot",0);
  GlobalVariableSet(g_workerRegistry+"owner",0);Comment("");g_workerOwned=false;
 }
 for(int i=0;i<ArraySize(g_cleanupFiles);i++) FileDelete(g_cleanupFiles[i],FILE_COMMON);
}
void OnTimer()
{
 WorkerHeartbeat();ulong now=GetTickCount64();double slot=AIState(g_workerRegistry+"slot");
 if(slot!=g_observedSlot){g_observedSlot=slot;g_slotObservedAt=now;}
 else if(slot>0 && now-g_slotObservedAt>65000) WorkerRelease(slot); // Abandoned reservation; never executes a trade.
 for(int i=ArraySize(g_cleanupFiles)-1;i>=0;i--)
  if(now>=g_cleanupTimes[i])
  {
   FileDelete(g_cleanupFiles[i],FILE_COMMON);int last=ArraySize(g_cleanupFiles)-1;
   g_cleanupFiles[i]=g_cleanupFiles[last];g_cleanupTimes[i]=g_cleanupTimes[last];
   ArrayResize(g_cleanupFiles,last);ArrayResize(g_cleanupTimes,last);
  }
}
void OnChartEvent(const int event,const long &chart,const double &token,const string &id)
{
 if(event!=CHARTEVENT_CUSTOM+MT3_AI_REQUEST_EVENT || !ValidAIId(id) || chart<=0 || token<=0 || AIState(g_workerRegistry+"slot")!=token) return;
 if(!GlobalVariableSetOnCondition(g_workerRegistry+"busy",token,0)) return;
 if(AIState(g_workerRegistry+"slot")!=token) {WorkerRelease(token);return;}
 string request;CMT3Json j;string requestId,sourceChart,body;double protocol,created,maxAge;
 bool valid=ReadAIFile(AIFile(id,".req"),request) && j.Parse(request) && j.Kind(0)==J_OBJECT &&
  j.GetNumber(0,"protocol",protocol) && protocol==MT3_AI_PROTOCOL && j.GetString(0,"id",requestId) && requestId==id &&
  j.GetString(0,"chart",sourceChart) && sourceChart==StringFormat("%I64d",chart) &&
  j.GetNumber(0,"created_ms",created) && j.GetNumber(0,"max_age_ms",maxAge) && j.GetString(0,"body",body);
 ulong now=GetTickCount64();
 if(!valid || maxAge<1000 || maxAge>60000 || created<0 || created>(double)now || (double)now-created>=maxAge)
 {WorkerReply(chart,id,token,"invalid","WAIT",0,"Invalid or expired request");return;}
 CMT3Json apiBody;if(!apiBody.Parse(body) || apiBody.Kind(0)!=J_OBJECT)
 {WorkerReply(chart,id,token,"invalid","WAIT",0,"Invalid API request JSON");return;}
 int remaining=(int)(maxAge-((double)now-created));int timeout=(int)MathMin(OpenAITimeoutMs,remaining);
 if(timeout<1000) {WorkerReply(chart,id,token,"expired","WAIT",0,"Request expired before HTTP");return;}
 WorkerHeartbeat(timeout+5000);
 if(!TerminalInfoInteger(TERMINAL_TRADE_ALLOWED))
 {WorkerReply(chart,id,token,"blocked","WAIT",0,"Terminal trading disabled before HTTP");return;}
 char data[];char result[];int count=StringToCharArray(body,data,0,WHOLE_ARRAY,CP_UTF8)-1;
 if(count<1 || ArrayResize(data,count)!=count) {WorkerReply(chart,id,token,"invalid","WAIT",0,"Request encoding failed");return;}
 string headers="Content-Type: application/json\r\nAuthorization: Bearer "+OpenAIAPIKey+"\r\n",responseHeaders;
 if(!FileIsExist(AIFile(id,".req"),FILE_COMMON) || AIState(g_workerRegistry+"slot")!=token)
 {WorkerRelease(token);return;}
 ResetLastError();int code=WebRequest("POST",OpenAIEndpoint,headers,timeout,data,result,responseHeaders);
 if(code<0 || code==408 || code==429 || code>=500)
 {WorkerReply(chart,id,token,"transport_error","WAIT",0,StringFormat("AI transport/HTTP error %d",code));return;}
 if(code<200 || code>=300)
 {WorkerReply(chart,id,token,"invalid","WAIT",0,StringFormat("AI HTTP %d; check worker key/model settings",code));return;}
 if(ArraySize(result)>524288) {WorkerReply(chart,id,token,"invalid","WAIT",0,"AI response too large");return;}
 string response=CharArrayToString(result,0,-1,CP_UTF8),decision,reason,error;double confidence;
 if(!ParseOpenAIResponse(response,decision,confidence,reason,error))
 {WorkerReply(chart,id,token,"invalid","WAIT",0,error);return;}
 WorkerReply(chart,id,token,"ok",decision,confidence,reason);
}

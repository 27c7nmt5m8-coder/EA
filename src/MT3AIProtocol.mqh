#ifndef MT3_AI_PROTOCOL_MQH
#define MT3_AI_PROTOCOL_MQH
#include "MT3Json.mqh"
#define MT3_AI_REQUEST_EVENT 3041
#define MT3_AI_REPLY_EVENT 3042
#define MT3_AI_PROTOCOL 242
uint AIHash(string value)
{uint h=2166136261;for(int i=0;i<StringLen(value);i++) h=(h^(uint)StringGetCharacter(value,i))*16777619;return h;}
string AIHex(uint n) {return StringFormat("%08X",n);}
string AIScope()
{return AIHex(AIHash(TerminalInfoString(TERMINAL_DATA_PATH)+"/"+AccountInfoString(ACCOUNT_SERVER)+StringFormat("/%I64d",AccountInfoInteger(ACCOUNT_LOGIN))));}
string AIRegistry() {return "MT3AI.W."+AIScope()+".";}
string AIFile(string id,string extension) {return "MT3AI\\"+AIScope()+"_"+id+extension;}
bool ValidAIId(string id)
{
 if(StringLen(id)!=32) return false;
 for(int i=0;i<32;i++){ushort c=StringGetCharacter(id,i);if(!((c>='0' && c<='9') || (c>='A' && c<='F'))) return false;}
 return true;
}
double AIState(string key) {return GlobalVariableCheck(key)?GlobalVariableGet(key):0;}
bool SaveU64(string key,ulong value)
{return GlobalVariableSet(key+".hi",(double)(uint)(value>>32))>0 && GlobalVariableSet(key+".lo",(double)(uint)value)>0;}
ulong LoadU64(string key) {return ((ulong)(uint)AIState(key+".hi")<<32)|(ulong)(uint)AIState(key+".lo");}
string NewAIId()
{
 static uint sequence=0;sequence++;
 return AIHex((uint)TimeLocal())+AIHex((uint)GetMicrosecondCount())+AIHex(AIHash(StringFormat("%I64d",ChartID())))+AIHex(sequence);
}
bool WriteAIFile(string name,const string text)
{
 // Publish only after a complete binary UTF-8 write; readers never see a partial file.
 string tmp=name+".tmp";uchar bytes[];int count=StringToCharArray(text,bytes,0,WHOLE_ARRAY,CP_UTF8)-1;
 if(count<0 || count>524288) return false;
 int h=FileOpen(tmp,FILE_WRITE|FILE_BIN|FILE_COMMON);if(h==INVALID_HANDLE) return false;
 uint n=FileWriteArray(h,bytes,0,count);FileFlush(h);FileClose(h);
 if(n!=(uint)count || !FileMove(tmp,FILE_COMMON,name,FILE_COMMON|FILE_REWRITE)) {FileDelete(tmp,FILE_COMMON);return false;}
 return true;
}
bool ReadAIFile(string name,string &text)
{
 text="";int h=FileOpen(name,FILE_READ|FILE_BIN|FILE_COMMON|FILE_SHARE_READ);if(h==INVALID_HANDLE) return false;
 ulong n=FileSize(h);if(n==0 || n>524288){FileClose(h);return false;}
 uchar bytes[];uint count=FileReadArray(h,bytes,0,(int)n);FileClose(h);if(count!=(uint)n) return false;
 text=CharArrayToString(bytes,0,(int)n,CP_UTF8);return true;
}
string BuildOpenAIRequest(string model,string effort,string snapshot,bool hybrid,bool proposedBuy)
{
 string instruction=hybrid?
  "You are a conservative FX/CFD trade gate. Approve only the same direction as the supplied local proposal, otherwise WAIT. Use only the supplied closed bars and indicators. Do not infer news. The EA controls all execution and risk. Confidence is a subjective score, not a measured win probability."
  :"You are a conservative FX/CFD signal classifier. Use only the supplied closed bars and indicators. Return BUY, SELL, or WAIT. Prefer WAIT with mixed evidence. Do not infer news. The EA controls all execution and risk. Confidence is a subjective score, not a measured win probability.";
 if(hybrid) {instruction+=" Proposed direction: ";instruction+=(proposedBuy?"BUY":"SELL");}
 string schema="{\"type\":\"object\",\"properties\":{\"decision\":{\"type\":\"string\",\"enum\":[\"BUY\",\"SELL\",\"WAIT\"]},\"confidence\":{\"type\":\"number\",\"minimum\":0,\"maximum\":1},\"reason\":{\"type\":\"string\"}},\"required\":[\"decision\",\"confidence\",\"reason\"],\"additionalProperties\":false}";
 return "{\"model\":"+JsonQuote(model)+",\"store\":false,\"max_output_tokens\":2048"+
  (effort==""?"":",\"reasoning\":{\"effort\":"+JsonQuote(effort)+"}")+
  ",\"input\":[{\"role\":\"system\",\"content\":"+JsonQuote(instruction)+"},{\"role\":\"user\",\"content\":"+JsonQuote(snapshot)+"}],\"text\":{\"format\":{\"type\":\"json_schema\",\"name\":\"trade_decision\",\"strict\":true,\"schema\":"+schema+"}}}";
}
#endif

#ifndef MT3_JSON_MQH
#define MT3_JSON_MQH
// Strict, bounded JSON parser. MQL strings are UTF-16; do not narrow to uchar.
enum ENUM_MT3_JSON { J_BAD=-1,J_NULL=0,J_BOOL=1,J_NUMBER=2,J_STRING=3,J_ARRAY=4,J_OBJECT=5 };
struct MT3JsonNode { int kind,child,next; string key,text; double number; };
class CMT3Json
{
private:
 MT3JsonNode m_nodes[];
 string m_source;
 int m_pos,m_length;
 void Space() { while(m_pos<m_length && (At()==32 || At()==9 || At()==10 || At()==13)) m_pos++; }
 ushort At() { return m_pos<m_length?StringGetCharacter(m_source,m_pos):0; }
 bool Take(ushort c) { if(m_pos>=m_length || At()!=c) return false; m_pos++;return true; }
 int Add(int kind,string key)
 {
  int n=ArraySize(m_nodes);if(n>=8192 || ArrayResize(m_nodes,n+1)!=n+1) return -1;
  m_nodes[n].kind=kind;m_nodes[n].child=-1;m_nodes[n].next=-1;
  m_nodes[n].key=key;m_nodes[n].text="";m_nodes[n].number=0;return n;
 }
 int Hex(ushort c)
 { if(c>='0' && c<='9') return c-'0';if(c>='a' && c<='f') return c-'a'+10;if(c>='A' && c<='F') return c-'A'+10;return -1; }
 bool Hex4(ushort &v)
 {
  if(m_pos+4>m_length) return false;int n=0;
  for(int i=0;i<4;i++){int h=Hex(At());if(h<0) return false;n=n*16+h;m_pos++;}
  v=(ushort)n;return true;
 }
 bool ReadStringValue(string &v)
 {
  v="";if(!Take('"')) return false;
  while(m_pos<m_length)
  {
   ushort c=At();m_pos++;
   if(c=='"') return true;
   if(c<32) return false;
   if(c=='\\')
   {
    if(m_pos>=m_length) return false;c=At();m_pos++;
    if(c=='"' || c=='\\' || c=='/') v+=ShortToString(c);
    else if(c=='b') v+=ShortToString(8);
    else if(c=='f') v+=ShortToString(12);
    else if(c=='n') v+="\n";
    else if(c=='r') v+="\r";
    else if(c=='t') v+="\t";
    else if(c=='u')
    {
     ushort u;if(!Hex4(u)) return false;
     if(u>=0xD800 && u<=0xDBFF)
     {
      ushort low;if(!Take('\\') || !Take('u') || !Hex4(low) || low<0xDC00 || low>0xDFFF) return false;
      v+=ShortToString(u)+ShortToString(low);
     }
     else {if(u>=0xDC00 && u<=0xDFFF) return false;v+=ShortToString(u);}
    }
    else return false;
   }
   else
   {
    if(c>=0xD800 && c<=0xDBFF)
    {
     ushort low=At();if(m_pos>=m_length || low<0xDC00 || low>0xDFFF) return false;
     m_pos++;v+=ShortToString(c)+ShortToString(low);
    }
    else {if(c>=0xDC00 && c<=0xDFFF) return false;v+=ShortToString(c);}
   }
  }
  return false;
 }
 bool Digit(ushort c) { return c>='0' && c<='9'; }
 bool ReadNumberValue(string &v,double &number)
 {
  int start=m_pos;if(At()=='-') m_pos++;
  if(At()=='0') {m_pos++;if(Digit(At())) return false;}
  else {if(At()<'1' || At()>'9') return false;while(Digit(At()) && m_pos<m_length) m_pos++;}
  if(At()=='.') {m_pos++;if(!Digit(At())) return false;while(Digit(At()) && m_pos<m_length) m_pos++;}
  if(At()=='e' || At()=='E')
  {m_pos++;if(At()=='+' || At()=='-') m_pos++;if(!Digit(At())) return false;while(Digit(At()) && m_pos<m_length) m_pos++;}
  v=StringSubstr(m_source,start,m_pos-start);number=StringToDouble(v);return MathIsValidNumber(number);
 }
 int Value(string key,int depth)
 {
  if(depth>32) return -1;Space();ushort c=At();int n=-1;
  if(c=='{' || c=='[')
  {
   bool object=c=='{';m_pos++;n=Add(object?J_OBJECT:J_ARRAY,key);if(n<0) return -1;
   Space();ushort end=object?'}':']';if(Take(end)) return n;int last=-1;
   while(m_pos<m_length)
   {
    string childKey="";Space();
    if(object)
    {
     if(!ReadStringValue(childKey)) return -1;Space();if(!Take(':')) return -1;
     if(Member(n,childKey)>=0) return -1; // Duplicate keys are ambiguous.
    }
    int item=Value(childKey,depth+1);if(item<0) return -1;
    if(last<0) m_nodes[n].child=item;else m_nodes[last].next=item;last=item;
    Space();if(Take(end)) return n;if(!Take(',')) return -1;
   }
   return -1;
  }
  if(c=='"') {string v;if(!ReadStringValue(v)) return -1;n=Add(J_STRING,key);if(n>=0) m_nodes[n].text=v;return n;}
  if(c=='-' || Digit(c))
  {string v;double d;if(!ReadNumberValue(v,d)) return -1;n=Add(J_NUMBER,key);if(n>=0){m_nodes[n].text=v;m_nodes[n].number=d;}return n;}
  string literal=c=='t'?"true":(c=='f'?"false":(c=='n'?"null":""));
  if(literal=="" || StringSubstr(m_source,m_pos,StringLen(literal))!=literal) return -1;
  m_pos+=StringLen(literal);n=Add(c=='n'?J_NULL:J_BOOL,key);if(n>=0) m_nodes[n].text=literal;return n;
 }
public:
 bool Parse(const string src)
 {
  ArrayResize(m_nodes,0);m_source=src;m_pos=0;m_length=StringLen(src);
  if(m_length<1 || m_length>524288) return false;
  int root=Value("",0);Space();if(root!=0 || m_pos!=m_length){ArrayResize(m_nodes,0);return false;}return true;
 }
 int Kind(int n) {return n>=0 && n<ArraySize(m_nodes)?m_nodes[n].kind:J_BAD;}
 int Child(int n) {return n>=0 && n<ArraySize(m_nodes)?m_nodes[n].child:-1;}
 int Next(int n) {return n>=0 && n<ArraySize(m_nodes)?m_nodes[n].next:-1;}
 string Text(int n) {return n>=0 && n<ArraySize(m_nodes)?m_nodes[n].text:"";}
 double Number(int n) {return n>=0 && n<ArraySize(m_nodes)?m_nodes[n].number:0;}
 int Member(int object,string key)
 {if(Kind(object)!=J_OBJECT) return -1;for(int n=Child(object);n>=0;n=Next(n)) if(m_nodes[n].key==key) return n;return -1;}
 int Count(int object) {int count=0;for(int n=Child(object);n>=0;n=Next(n)) count++;return count;}
 bool GetString(int object,string key,string &v)
 {int n=Member(object,key);if(Kind(n)!=J_STRING) return false;v=Text(n);return true;}
 bool GetNumber(int object,string key,double &v)
 {int n=Member(object,key);if(Kind(n)!=J_NUMBER) return false;v=Number(n);return true;}
};
string JsonQuote(const string value)
{
 string out="\"";
 for(int i=0;i<StringLen(value);i++)
 {
  ushort c=StringGetCharacter(value,i);
  if(c=='"') out+="\\\"";else if(c=='\\') out+="\\\\";
  else if(c<32) out+=StringFormat("\\u%04X",(uint)c);else out+=ShortToString(c);
 }
 return out+"\"";
}
bool ParseTradeDecision(const string payload,string &decision,double &confidence,string &reason)
{
 decision="WAIT";confidence=0;reason="";CMT3Json j;
 if(!j.Parse(payload) || j.Kind(0)!=J_OBJECT || j.Count(0)!=3) return false;
 if(!j.GetString(0,"decision",decision) || !j.GetNumber(0,"confidence",confidence) || !j.GetString(0,"reason",reason)) return false;
 if(decision!="BUY" && decision!="SELL" && decision!="WAIT") return false;
 return MathIsValidNumber(confidence) && confidence>=0 && confidence<=1 && StringLen(reason)<=1024;
}
bool ParseOpenAIResponse(const string response,string &decision,double &confidence,string &reason,string &error)
{
 decision="WAIT";confidence=0;reason="";error="Invalid API response";CMT3Json j;
 if(!j.Parse(response) || j.Kind(0)!=J_OBJECT) return false;
 string status;if(!j.GetString(0,"status",status) || status!="completed") {error="AI response is not completed";return false;}
 int e=j.Member(0,"error");if(e>=0 && j.Kind(e)!=J_NULL) return false;
 int out=j.Member(0,"output");if(j.Kind(out)!=J_ARRAY) return false;
 string payload="";int textCount=0;
 for(int m=j.Child(out);m>=0;m=j.Next(m))
 {
  string type;if(!j.GetString(m,"type",type)) return false;
  if(type=="reasoning") continue;
  if(type!="message") return false;
  string role,ms,phase;
  if(!j.GetString(m,"role",role) || role!="assistant" || !j.GetString(m,"status",ms) || ms!="completed") return false;
  j.GetString(m,"phase",phase);if(phase=="commentary") continue;
  if(phase!="" && phase!="final_answer") return false;
  int content=j.Member(m,"content");if(j.Kind(content)!=J_ARRAY) return false;
  for(int c=j.Child(content);c>=0;c=j.Next(c))
  {
   if(!j.GetString(c,"type",type)) return false;
   if(type=="refusal") {error="AI refusal";return false;}
   if(type!="output_text" || !j.GetString(c,"text",payload)) return false;
   textCount++;
  }
 }
 if(textCount!=1 || !ParseTradeDecision(payload,decision,confidence,reason)) return false;
 error="";return true;
}
#endif

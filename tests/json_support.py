from pathlib import Path
import itertools,json,re,subprocess
ROOT=Path(__file__).resolve().parent
TEST=ROOT/'verification'
TEST.mkdir(exist_ok=True)

HEADER=r'''
#include <algorithm>
#include <cmath>
#include <codecvt>
#include <cstdio>
#include <cstdlib>
#include <fstream>
#include <iostream>
#include <iterator>
#include <locale>
#include <map>
#include <string>
#include <tuple>
#include <type_traits>
#include <vector>
using string=std::u16string;
using uchar=unsigned char;using ushort=unsigned short;using datetime=long;
std::string utf8(const string&s){return std::wstring_convert<std::codecvt_utf8_utf16<char16_t>,char16_t>{}.to_bytes(s);}
string wide(const std::string&s){return std::wstring_convert<std::codecvt_utf8_utf16<char16_t>,char16_t>{}.from_bytes(s);}
int StringLen(const string&s){return (int)s.size();}
int StringFind(const string&s,const string&sub,int start=0){auto p=s.find(sub,start);return p==string::npos?-1:(int)p;}
string StringSubstr(const string&s,int start,int len=-1){return start<0 || start>(int)s.size()?string{}:s.substr(start,len<0?string::npos:(size_t)len);}
ushort StringGetCharacter(const string&s,int i){return (ushort)s.at(i);}
string ShortToString(ushort c){return string(1,(char16_t)c);}
double StringToDouble(const string&s){return std::strtod(utf8(s).c_str(),nullptr);}
bool MathIsValidNumber(double n){return std::isfinite(n);}
string IntegerToString(long n){return wide(std::to_string(n));}
string DoubleToString(double n,int digits){char b[200];std::snprintf(b,sizeof b,"%.*f",digits,n);return wide(b);}
template<class T>int ArraySize(const std::vector<T>&v){return (int)v.size();}
template<class T>int ArrayResize(std::vector<T>&v,int n){if(n<0)return -1;v.resize(n);return n;}
template<class T>void ArraySort(std::vector<T>&v){std::sort(v.begin(),v.end());}
template<class T>void ZeroMemory(T &v){v=T{};}
template<class A,class B>auto MathMin(A a,B b){using C=std::common_type_t<A,B>;return std::min((C)a,(C)b);}
template<class A,class B>auto MathMax(A a,B b){using C=std::common_type_t<A,B>;return std::max((C)a,(C)b);}
template<class T>auto MathAbs(T v){return std::abs(v);}
template<class T>struct FArg {T value;auto get(){if constexpr(std::is_same_v<T,ulong>)return (unsigned long long)value;else if constexpr(std::is_same_v<T,long>)return (long long)value;else return value;}};
template<>struct FArg<string>{std::string value;FArg(string s):value(utf8(s)){}const char *get(){return value.c_str();}};
template<>struct FArg<const char16_t*>{std::string value;FArg(const char16_t*s):value(utf8(string(s))){}const char *get(){return value.c_str();}};
template<class T>FArg<T> box(T t){return FArg<T>{t};}
template<class... A>string StringFormat(const string&fmt,A... args){
 std::string f=utf8(fmt);size_t p;while((p=f.find("I64"))!=std::string::npos)f.replace(p,3,"ll");
 auto values=std::make_tuple(box(args)...);
 return std::apply([&](auto &...a){int n=std::snprintf(nullptr,0,f.c_str(),a.get()...);std::vector<char>b(n+1);std::snprintf(b.data(),b.size(),f.c_str(),a.get()...);return wide(std::string(b.data()));},values);
}
template<class... A>void Print(A...){ }
template<class... A>void PrintFormat(A...){ }
'''

def adapt(code):
    code=re.sub(r'(?m)^#(?:include|property).*\n','',code)
    code=re.sub(r'\b(MT3JsonNode|MTFResult|MqlRates|char|uchar|double|ulong|string)\s+([A-Za-z_]\w*)\[\];',r'std::vector<\1> \2;',code)
    code=re.sub(r'\b(MTFResult|MqlRates)\s+&([A-Za-z_]\w*)\[\]',r'std::vector<\1> &\2',code)
    # MQL string literals denote UTF-16. Prefix literals for C++'s equivalent type.
    tokens=r'''//[^\n]*|/\*[\s\S]*?\*/|'(?:\\.|[^'\\])*'|"(?:\\.|[^"\\])*"'''
    return re.sub(tokens,lambda m:('u'+m[0]) if m[0].startswith('"') else m[0],code)

def compile_run(name,code,args=()):
    path=TEST/(name+'.cpp');binary=TEST/name
    path.write_text(HEADER+adapt((ROOT/'MT3Json.mqh').read_text())+code)
    p=subprocess.run(['g++','-std=c++17','-O2','-Wall','-Wextra',str(path),'-o',str(binary)],capture_output=True,text=True)
    if p.returncode:raise RuntimeError(p.stderr)
    return subprocess.run([str(binary),*map(str,args)],capture_output=True,text=True,check=True).stdout

def extract(name,source):
    match=re.search(r'(?m)^(?:string|bool|void|double|int|ulong|uint|datetime)\s+'+name+r'\s*\(',source)
    if not match:raise ValueError(name)
    start=source.index('{',match.end());pos=start;depth=0
    tokens=re.compile(r'''//[^\n]*|/\*[\s\S]*?\*/|'(?:\\.|[^'\\])*'|"(?:\\.|[^"\\])*"''')
    while pos<len(source):
        token=tokens.match(source,pos)
        if token:pos=token.end();continue
        if source[pos]=='{':depth+=1
        elif source[pos]=='}':
            depth-=1
            if depth==0:return source[match.start():pos+1]
        pos+=1
    raise ValueError('Unterminated '+name)

def verify():
    main=r'''
int main(int argc,char**argv){
 if(argc!=3)return 2;std::ifstream in(argv[2]);string src=wide(std::string(std::istreambuf_iterator<char>(in),{}));
 string d,r,e;double c=0;bool ok=false;
 if(std::string(argv[1])=="payload")ok=ParseTradeDecision(src,d,c,r);
 else ok=ParseOpenAIResponse(src,d,c,r,e);
 std::cout<<ok<<"\t"<<utf8(d)<<"\t"<<c<<"\n";
 if(ok)std::cout<<utf8(r);
}
'''
    # Compile once, then exercise the same extracted parser against generated fixtures.
    dummy=TEST/'initial.json';dummy.write_text('{}')
    compile_run('json_test',main,['response',dummy])
    binary=TEST/'json_test'
    cases=[]
    good={'decision':'BUY','confidence':.91,'reason':'根拠: EMA支持。 😀 "確認" \\ next\nline'}
    def env(payload):
        return {'id':'resp_fixture','object':'response','status':'completed','error':None,
                'output':[{'type':'reasoning','summary':[]},{'type':'message','status':'completed','role':'assistant','content':[{'text':payload,'type':'output_text'}]}]}
    def run(name,value,expected,mode='response',reason=None):
        file=TEST/'case.json';file.write_text(value)
        lines=subprocess.run([str(binary),mode,str(file)],check=True,capture_output=True,text=True).stdout.split('\n',1)
        ok=lines[0].split('\t')[0]=='1'
        assert ok==expected,(name,lines)
        if reason is not None:assert lines[1]==reason,(name,lines[1],reason)
        cases.append({'case':name,'passed':True})
    for perm in itertools.permutations(good):
        for ensure_ascii in [True,False]:
            for sep in [(',',':'),(', ', ' : ')]:
                payload=json.dumps({k:good[k] for k in perm},ensure_ascii=ensure_ascii,separators=sep)
                response=json.dumps(env(payload),ensure_ascii=ensure_ascii,indent=2)
                run('valid_order_space_unicode_'+str(len(cases)),response,True,reason=good['reason'])
    run('valid_exponent', '{"decision":"SELL","confidence":9.1e-1,"reason":"ok"}',True,'payload',reason='ok')
    for name,payload in [
        ('truncated','{"decision":"BUY","confidence":0.91'),
        ('missing_reason','{"decision":"BUY","confidence":0.91}'),
        ('out_of_range','{"decision":"BUY","confidence":1.2,"reason":"x"}'),
        ('negative','{"decision":"BUY","confidence":-0.1,"reason":"x"}'),
        ('string_number','{"decision":"BUY","confidence":"0.9","reason":"x"}'),
        ('leading_plus','{"decision":"BUY","confidence":+0.9,"reason":"x"}'),
        ('leading_zero','{"decision":"BUY","confidence":00.9,"reason":"x"}'),
        ('truncated_exponent','{"decision":"BUY","confidence":0.9e,"reason":"x"}'),
        ('nan','{"decision":"BUY","confidence":NaN,"reason":"x"}'),
        ('overflow','{"decision":"BUY","confidence":1e999,"reason":"x"}'),
        ('trailing_json','{"decision":"BUY","confidence":0.9,"reason":"x"}{}'),
        ('duplicate_key','{"decision":"BUY","decision":"SELL","confidence":0.9,"reason":"x"}'),
        ('duplicate_escaped_key','{"decision":"BUY","\\u0064ecision":"SELL","confidence":0.9,"reason":"x"}'),
        ('extra_field','{"decision":"BUY","confidence":0.9,"reason":"x","extra":1}'),
        ('lone_surrogate','{"decision":"BUY","confidence":0.9,"reason":"\\uD800"}'),
        ('invalid_escape','{"decision":"BUY","confidence":0.9,"reason":"\\q"}'),
        ('wrong_decision','{"decision":"LONG","confidence":0.9,"reason":"x"}'),
    ]:run(name,json.dumps(env(payload)),False)
    payload=json.dumps(good)
    for status in ['incomplete','failed','queued','in_progress','cancelled']:
        e=env(payload);e['status']=status;run('status_'+status,json.dumps(e),False)
    e=env('{"decision":"BUY","confidence":0.91');e['status']='incomplete'
    run('original_R1',json.dumps(e),False)
    e=env(payload);e['output'][1]['status']='incomplete';run('message_incomplete',json.dumps(e),False)
    e=env(payload);e['output'][1]['role']='user';run('wrong_role',json.dumps(e),False)
    e=env(payload);e['error']={'message':'error'};run('error_envelope',json.dumps(e),False)
    e=env(payload);e['output'][1]['content'].append({'type':'refusal','refusal':'no'});run('mixed_refusal',json.dumps(e),False)
    e=env(payload);e['output'][1]['content']*=2;run('ambiguous_multiple_outputs',json.dumps(e),False)
    e=env(payload);e['output'].insert(1,{'type':'message','status':'completed','role':'assistant','phase':'commentary','content':[{'type':'output_text','text':'Processing'}]})
    run('commentary_then_final',json.dumps(e),True,reason=good['reason'])
    run('depth_limit','['*40+'0'+']'*40,False)
    result={'scope':'Actual MT3Json.mqh parser adapted to UTF-16 C++ with MQL primitive shims. No API call or MT5 compiler.','cases':cases}
    (TEST/'json_results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print('PASS',len(cases),'strict JSON, UTF-16, response-state and schema scenarios')
if __name__=='__main__':verify()

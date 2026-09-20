"""Compile actual EA/worker code as C++17 with MT5 mocks; NOT a native MQL compile."""
from pathlib import Path
import re,json,subprocess,hashlib,sys
from json_support import HEADER
ROOT=Path(__file__).resolve().parents[1];SRC=ROOT/'src';TEST=ROOT/'verification'
TEST.mkdir(exist_ok=True)

def expand(path,seen):
    if path.name in seen:return ''
    seen.add(path.name)
    code=path.read_text(encoding='utf-8-sig')
    return re.sub(r'(?m)^#include "([^"]+)"',lambda m:expand(SRC/m[1],seen),code)

def adapt(code):
    code=re.sub(r'(?m)^#(?:include|property).*\n','',code)
    code=re.sub(r'(?m)^input group[^\n]*\n','',code)
    code=re.sub(r'\binput\s+','',code)
    code=re.sub(r"C'\d+,\d+,\d+'",'0',code)
    code=re.sub(r'\b(\w+)\s+&\s*(\w+)\[\]',r'std::vector<\1> &\2',code)
    code=re.sub(r'\b(\w+)\s+(\w+\[\](?:,\w+\[\])+);',lambda m:'std::vector<'+m[1]+'> '+m[2].replace('[]','')+';',code)
    code=re.sub(r'\b(\w+)\s+(\*)?\s*(\w+)\[\];',lambda m:'std::vector<'+m[1]+('*' if m[2] else '')+'> '+m[3]+';',code)
    code=code.replace('m_mcReturns[],m_mcDDs[]','m_mcReturns,m_mcDDs')
    code=re.sub(r'g_symbols\[([^\]]+)\]\.',r'g_symbols[\1]->',code)
    code=re.sub(r'\bstate\.(Init|Shutdown|m_wanted)',r'state->\1',code)
    tokens=r'''//[^\n]*|/\*[\s\S]*?\*/|'(?:\\.|[^'\\])*'|"(?:\\.|[^"\\])*"'''
    return re.sub(tokens,lambda m:'u'+m[0] if m[0].startswith('"') else m[0],code)

def constants(source):
    # Enum values in the product remain declared by the actual source.
    declared=set()
    for e in re.findall(r'enum\s+\w+\s*\{([^}]+)\}',source):
        e=re.sub(r'//[^\n]*','',e)
        declared.update(re.findall(r'\b[A-Z][A-Z0-9_]+\b',e))
    declared.update(re.findall(r'#define\s+(\w+)',source))
    aliases=set(re.findall(r'\bENUM_[A-Z_]+\b',source))-set(re.findall(r'enum\s+(\w+)',source))
    prefixes=r'(?:PERIOD|ACCOUNT|SYMBOL|POSITION|ORDER|DEAL|TRADE|TERMINAL|MQL|CHART|CHARTEVENT|OBJ|OBJPROP|CORNER|ANCHOR|STYLE|MODE|PRICE|TIME|FILE|CP|INIT)_\w+'
    names=set(re.findall(r'\b'+prefixes+r'\b',source))-declared-aliases
    values={'INVALID_HANDLE':-1,'WHOLE_ARRAY':-1,'EMPTY_VALUE':1e100,'DBL_MAX':1e100}
    for i,n in enumerate(sorted(names),100):values[n]=i
    values.update({'REASON_CHARTCHANGE':3,'REASON_INITFAILED':8,'SYMBOL_ORDER_MARKET':1,'SYMBOL_ORDER_SL':16,'SYMBOL_ORDER_TP':32,'SYMBOL_FILLING_FOK':1,'SYMBOL_FILLING_IOC':2,
                   'CHARTEVENT_CUSTOM':1000,'INIT_SUCCEEDED':0,'FILE_READ':1,'FILE_WRITE':2,'FILE_BIN':4,'FILE_COMMON':8,'FILE_SHARE_READ':16,'FILE_REWRITE':32})
    names.update(values)
    out='\n'.join('using '+n+'=int;' for n in sorted(aliases))+'\nusing color=int;\n'
    out+='\n'.join('const '+('double' if n in ['DBL_MAX','EMPTY_VALUE'] else 'int')+' '+n+'='+str(values[n])+';' for n in sorted(names))
    colors=set(re.findall(r'\bclr\w+',source));out+='\n'+'\n'.join('const color '+n+'=0;' for n in colors)
    return out

def run():
    product=expand(SRC/'MTFAutoTrader_3Mode_AI_v2_44.mq5',set())
    worker=(SRC/'MTFAutoTrader_AI_Worker.mq5').read_text()
    for old,new in [('OnInit','WorkerInit'),('OnDeinit','WorkerDeinit'),('OnTimer','WorkerTimer'),('OnChartEvent','WorkerEvent')]:worker=worker.replace(old+'(',new+'(')
    source=product+'\n'+worker
    # Inject allocation failure only for PatternSignal vectors; production source stays unchanged.
    header=HEADER.replace('template<class T>int ArrayResize(std::vector<T>&v,int n){if(n<0)return -1;v.resize(n);return n;}',
        'struct PatternSignal;int pattern_array_failure_at=-1;\n'
        'template<class T>int ArrayResize(std::vector<T>&v,int n){if(n<0)return -1;if constexpr(std::is_same_v<T,PatternSignal>){if(n==pattern_array_failure_at)return -1;}v.resize(n);return n;}')
    header=header.replace('template<class... A>void Print(A...){ }',
        'int log_warning_count=0;template<class... A>void Print(const char16_t* first,A...){if(string(first).find(u"TradeLog warning:")==0)log_warning_count++;}\n'
        'template<class... A>void Print(A...){ }')
    scenarios='\n'.join((ROOT/'tests'/name).read_text() for name in ['scenarios.cpp','new_scenarios.cpp','v244_scenarios.cpp','v244_lock_scenarios.cpp','v245_scenarios.cpp'])
    header+='\n#include <set>\n#include <limits>\n#include <functional>\n#include <cstring>\n'+constants(source+(ROOT/'tests/mock_mt5.hpp').read_text()+scenarios)+'\n'
    code=header+(ROOT/'tests/mock_mt5.hpp').read_text()+adapt(source)+'\n'+scenarios
    (TEST/'integration.cpp').write_text(code)
    result=subprocess.run(['g++','-std=c++17','-O1','-Wall','-Wextra',str(TEST/'integration.cpp'),'-o',str(TEST/'integration')],capture_output=True,text=True)
    (TEST/'cpp_diagnostics.txt').write_text(result.stderr)
    if result.returncode:
        print(result.stderr[:14000]);raise SystemExit(result.returncode)
    run=subprocess.run([str(TEST/'integration'),*sys.argv[1:]],capture_output=True,text=True)
    print(run.stdout);print(run.stderr)
    if run.returncode:raise SystemExit(run.returncode)
    if len(sys.argv)>1:return  # A focused run must not overwrite the full-suite report.
    data=json.loads(run.stdout)
    data['scope']='Actual main EA, headers and worker adapted to UTF-16 C++17 using simulated MT5 services. No MetaEditor compilation, real trading, market backtest, or API call.'
    data['source_sha256']={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(SRC.iterdir()) if p.is_file()}
    (TEST/'integration_results.json').write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')

if __name__=='__main__':run()

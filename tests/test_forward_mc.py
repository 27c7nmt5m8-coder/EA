"""Forward preparation must never install/launch or mutate product sources."""
import json
import importlib.util
from pathlib import Path
import tempfile
import unittest
import re
import shutil
import subprocess
import sys
import csv
import io


class ForwardGenerationTests(unittest.TestCase):
    def builder(self):
        self.assertIsNotNone(importlib.util.find_spec('tools.build_forward_mc'), 'Forward generator not implemented')
        from tools import build_forward_mc
        return build_forward_mc

    def test_generated_candidate_projects_exactly_to_all_product_bytes(self):
        mod = self.builder()
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / 'candidate'
            proof = mod.build(target)
            self.assertEqual(proof['operations_per_callback'], 500000)
            self.assertEqual(proof['product_version'], '2.44')
            self.assertEqual(len(proof['canonical_source_sha256']), 13)
            for path in mod.SOURCE.iterdir():
                if path.suffix in ('.mqh', '.mq5'):
                    self.assertEqual(mod.restore(path.name, (target/path.name).read_bytes()), path.read_bytes())
            self.assertFalse(any(p.name.startswith('Tester') for p in target.iterdir()))

    def test_destination_reuse_is_rejected_without_writes(self):
        mod = self.builder()
        with tempfile.TemporaryDirectory() as td:
            target = Path(td)/'candidate';target.mkdir();sentinel=target/'keep.txt';sentinel.write_bytes(b'keep')
            with self.assertRaises(ValueError):mod.build(target)
            self.assertEqual(sentinel.read_bytes(), b'keep')

    def test_product_destination_is_rejected(self):
        mod=self.builder()
        with self.assertRaises(ValueError):mod.build(mod.SOURCE/'forward')
        self.assertFalse((mod.SOURCE/'forward').exists())

    def test_unexpected_core_fails_before_destination_creation(self):
        mod=self.builder()
        with tempfile.TemporaryDirectory() as td:
            source=Path(td)/'source';source.mkdir()
            for p in mod.SOURCE.iterdir():
                if p.suffix in ('.mqh','.mq5'):(source/p.name).write_bytes(p.read_bytes())
            p=source/'MT3SymbolState.mqh';p.write_bytes(p.read_bytes().replace(b'operations<20000',b'operations<25000'))
            target=Path(td)/'candidate'
            with self.assertRaises(ValueError):mod.build(target,source)
            self.assertFalse(target.exists())

    def test_manifest_binds_observer_and_sources_without_secrets(self):
        mod=self.builder()
        with tempfile.TemporaryDirectory() as td:
            target=Path(td)/'candidate';proof=mod.build(target)
            saved=json.loads((target/'forward_source_manifest.json').read_text(encoding='utf-8'))
            self.assertEqual(saved,proof)
            self.assertEqual(saved['classification']['ForwardMCObserver.mqh'],'FORWARD_OBSERVER')
            self.assertEqual(saved['tester_only_files'],[])
            self.assertEqual(saved['runtime_started'],False)
            self.assertEqual(saved['real_account_allowed'],False)

    def test_mql_observer_identity_cycle_and_dedup_behavior(self):
        """Execute actual bounded MQL function bodies; long uses the MQL64 ABI."""
        compiler=shutil.which('g++')
        if not compiler:self.skipTest('C++ compiler unavailable; native CI required')
        sys.path.insert(0,str(Path(__file__).resolve().parent))
        from native_preflight import preflight
        if preflight()['status']=='BLOCKED':self.skipTest('Application Control blocked; native CI required')
        mod=self.builder();source=mod.HEADER.read_text(encoding='utf-8')
        functions=[]
        for name in ('FOGuardIdentity','FORequest','FOCandidate','FOUpper','FODuration','FOOperations','FOComplete','FOMCWait','FOBar','FOTrade','FOInit'):
            found=re.search(r'^(?:bool|void|ulong) '+name+r'\(',source,re.M)
            self.assertIsNotNone(found)
            start=source.index('{',found.start());depth=1;end=start+1
            while depth:
                depth+=(source[end]=='{')-(source[end]=='}');end+=1
            functions.append(re.sub(r'\blong\b','std::int64_t',source[found.start():end]))
        harness=r'''
#include <string>
#include <cstdint>
#include <cassert>
#include <vector>
using string=std::string;using ulong=std::uint64_t;using uint=std::uint32_t;
const int ACCOUNT_TRADE_MODE_DEMO=0;
struct State {ulong cycle=0,counts[5]={},total[5]={},max[5]={},hist[5][12]={},cycleCallbacks=0,cycleUs=0,cycleMax=0,cycleOps=0,candidate=0,positionLast=0;std::int64_t candidateBar=0,bar=0,waitBar=0;bool active=false;};
State g_foState[4];int unknown=0;
struct Row {string event;ulong cycle;std::int64_t reason;};std::vector<Row> rows;
int FOIndex(const string s){return s=="USDJPY"?0:-1;}
void FOUnknown(){unknown++;}
ulong GetMicrosecondCount(){return 1000;}
void FORecord(const string event,const string symbol,const ulong cycle,const ulong start,const ulong end,const ulong count=0,const ulong maximum=0,const std::int64_t reason=0,const bool ready=false,const bool allowed=false,const double risk=0,const uint rng=0,const ulong total=0){rows.push_back({event,cycle,reason});}
const int TRADE_TRANSACTION_DEAL_ADD=6,TRADE_TRANSACTION_REQUEST=10;
struct MqlTradeTransaction {string symbol;int type=10,deal_type=0;double price=0,volume=0;};
struct MqlTradeRequest {string symbol;};struct MqlTradeResult {uint retcode=10009;};
struct MockSymbol {bool g_lockOwned=true;string g_lockKey="owned-old";void ReleaseIndicators(){}};
std::vector<MockSymbol*> g_symbols;
bool g_foBound=true,guardAllowed=false,g_propControllerOwned=true;string g_propControllerKey="prop-old",_Symbol="USDJPY";
std::int64_t g_foIdentity=0,accountIdentity=5000000000LL;string g_foServer,g_foPath;
const int MQL_TESTER=0,TERMINAL_CONNECTED=1,EXECUTION_AUTO=0,CUSTOM_LIST=2,PERIOD_M1=1,ACCOUNT_LOGIN=2,ACCOUNT_SERVER=3,ACCOUNT_TRADE_MODE=4;
int ExecutionMode=0,ScanMode=2,_Period=1;bool EnableOpenAI=false;string CustomSymbols="USDJPY,EURUSD,EURJPY,XAUUSD";
int MQLInfoInteger(int){return 0;}int TerminalInfoInteger(int){return 1;}
std::int64_t AccountInfoInteger(int key){return key==ACCOUNT_LOGIN?accountIdentity:0;}
string AccountInfoString(int){return "demo";}
std::int64_t TimeGMT(){return 100;}std::int64_t ChartID(){return 1;}
string IntegerToString(std::int64_t value){return std::to_string(value);}
int killed=0,originalDeinit=0;std::vector<string> released;
bool FOAllowed(){return guardAllowed;}
void FOOriginalOnDeinit(int){originalDeinit++;}
void EventKillTimer(){killed++;}
void GlobalVariableSetOnCondition(string key,int,int){released.push_back(key);}
void GlobalVariablesFlush(){}
void ReleaseExecution(){released.push_back("execution-old");}
template<class T> int ArraySize(const std::vector<T>& values){return int(values.size());}
template<class T> void ArrayResize(std::vector<T>& values,int n){values.resize(n);}
void FOFlush(bool){}
'''
        generated=mod.SOURCE.joinpath(mod.MAIN).read_bytes()
        for old,new in mod.substitutions(mod.MAIN):generated=mod.replace_once(generated,old,new)
        text=generated.decode('utf-8');start=text.index('void OnDeinit(const int reason)');body=text.index('{',start);depth=1;end=body+1
        while depth:
            depth+=(text[end]=='{')-(text[end]=='}');end+=1
        # MQL object-pointer member syntax, limited to this extracted wrapper.
        cleanup=text[start:end].replace('g_symbols[i].','g_symbols[i]->')
        main=r'''
int main(){
 const std::int64_t id=5000000000LL;
 assert(FOGuardIdentity(0,id,"demo",id,"demo"));
 assert(!FOGuardIdentity(2,id,"demo",id,"demo"));
 assert(!FOGuardIdentity(1,id,"demo",id,"demo"));
 assert(!FOGuardIdentity(0,id,"demo",id+1,"demo"));
 assert(!FOGuardIdentity(0,id,"changed",id,"demo"));
 assert(!FOGuardIdentity(0,0,"demo",0,"demo"));
 assert(!FOGuardIdentity(0,id,"",id,""));
 FORequest("USDJPY",false,false,30,false,false);
 assert(rows.back().cycle==1 && g_foState[0].cycle==1);
 FOCandidate("USDJPY",60,4);auto count=rows.size();
 FOCandidate("USDJPY",60,4);assert(rows.size()==count);
 FOCandidate("USDJPY",120,4);assert(rows.size()==count+1);
 FODuration("USDJPY",0,100,5100);FOOperations("USDJPY",500000);
 assert(g_foState[0].cycleCallbacks==1 && g_foState[0].cycleUs==5000 && g_foState[0].cycleOps==500000);
 assert(g_foState[0].hist[0][5]==1);
 g_foState[0].active=true;FOComplete("USDJPY",true,true,.1,123);
 assert(rows.back().cycle==1 && !g_foState[0].active);
 FOComplete("USDJPY",true,true,.1,123);assert(unknown==1);
 FODuration("USDJPY",1,20,10);assert(unknown==2);
 g_foState[0].active=true;
 FOMCWait("USDJPY",60,false,false,true);FOBar("USDJPY",60);
 auto before=rows.size();FOMCWait("USDJPY",120,false,false,true);FOBar("USDJPY",120);
 assert(rows[before].event=="MC_WAIT_WINDOW_END" && rows[before].reason==1);
 assert(rows[before+1].event=="MC_PREFLIGHT_WAIT_BAR");
 before=rows.size();FODuration("USDJPY",1,100,200);
 assert(rows[before].event=="POSITION_SAMPLE");
 FODuration("USDJPY",1,300,400);assert(rows.size()==before+1);
 MqlTradeTransaction trans;MqlTradeRequest request;MqlTradeResult result;request.symbol="USDJPY";
 FOTrade(trans,request,result);assert(rows.back().event=="TRADE_REQUEST_RESULT" && rows.back().reason==10009);
 g_symbols.push_back(new MockSymbol());OnDeinit(5);
 assert(killed==1 && originalDeinit==0 && g_symbols.empty());
 assert(released==std::vector<string>({"owned-old","execution-old","prop-old"}));
 guardAllowed=true;OnDeinit(0);assert(originalDeinit==1);
 g_foBound=false;assert(FOInit());auto bound=g_foIdentity;
 accountIdentity++;assert(!FOInit() && g_foIdentity==bound);
 return 0;
}'''
        with tempfile.TemporaryDirectory() as td:
            cpp=Path(td)/'observer.cpp';exe=Path(td)/'observer.exe'
            cpp.write_text(harness+'\n'.join(functions)+cleanup+main,encoding='utf-8')
            subprocess.run([compiler,'-std=c++17',str(cpp),'-o',str(exe)],check=True,capture_output=True,timeout=60)
            subprocess.run([str(exe)],check=True,capture_output=True,timeout=10)


class ForwardAnalysisTests(unittest.TestCase):
    def analyzer(self):
        self.assertIsNotNone(importlib.util.find_spec('tools.analyze_forward_mc'), 'Forward analyzer not implemented')
        from tools import analyze_forward_mc
        return analyze_forward_mc

    def rows(self, mod, events):
        for seq,(event,symbol,cycle,start,end) in enumerate(events,1):
            row={key:'0' for key in mod.FIELDS}
            row.update(seq=str(seq),event=event,symbol=symbol,cycle=str(cycle),start_wall_us=str(start),end_wall_us=str(end),arrival_us='UNKNOWN',queue_depth='UNKNOWN',value_bits='0')
            yield row

    def test_actual_overlap_and_incomplete_coverage_are_distinct(self):
        mod=self.analyzer()
        events=[('MC_REQUEST','USDJPY',1,0,0),('MC_START','USDJPY',1,10,10),('MC_REQUEST','EURJPY',1,11,11),('MC_START','EURJPY',1,12,12),('MC_COMPLETE','USDJPY',1,20,20),('MC_COMPLETE','EURJPY',1,25,25)]
        rows=list(self.rows(mod,events))
        for row,active in zip(rows,[0,1,1,2,2,1]):row['active_symbols']=str(active)
        result=mod.analyze(rows)
        self.assertEqual(result['actual_max_overlap'],2)
        self.assertEqual(result['overlap_intervals'][0]['symbols'],['EURJPY','USDJPY'])
        self.assertEqual(result['overlap_intervals'][0]['duration_us'],8)
        self.assertEqual(result['coverage']['3_symbol'],'UNOBSERVED')
        self.assertEqual(result['coverage']['2_symbol'],'OBSERVED_COMPLETE')
        self.assertEqual(result['queue_wait'],'UNKNOWN')
        self.assertEqual(result['completed_cycles'],2)
        self.assertEqual(result['open_cycles'],0)

    def test_unknown_or_duplicate_records_never_become_success(self):
        mod=self.analyzer();rows=list(self.rows(mod,[('MC_REQUEST','USDJPY',1,1,1)]))
        for key,value in [('symbol','private-sensitive'),('event','SECRET'),('seq','invalid')]:
            altered=[dict(rows[0],**{key:value})]
            with self.assertRaisesRegex(ValueError,'invalid observer evidence'):mod.analyze(altered)
        with self.assertRaises(ValueError):mod.analyze(rows+rows)
        rows[0]['observer_unknown']='1'
        self.assertEqual(mod.analyze(rows)['status'],'INCOMPLETE')

    def test_wait_bars_are_not_fabricated_opportunities(self):
        mod=self.analyzer();rows=list(self.rows(mod,[('MC_PREFLIGHT_WAIT_BAR','USDJPY',1,1,1),('MC_WAIT_WINDOW_END','USDJPY',1,2,2)]))
        result=mod.analyze(rows)
        self.assertEqual(result['mc_wait_bar_observations'],1)
        self.assertEqual(result['eligible_opportunity_expiry'],'UNKNOWN')
        self.assertEqual(result['numerical_equivalence'],'NOT_RUN')

    def test_overlap_errors_and_zero_length_overlap_are_not_complete(self):
        mod=self.analyzer();rows=list(self.rows(mod,[('MC_REQUEST','USDJPY',1,1,1)]))
        rows[0]['observer_unknown']='1'
        self.assertEqual(mod.analyze(rows)['coverage']['2_symbol'],'INVALID')
        rows[0]['observer_unknown']='0';rows[0]['ready']='2'
        with self.assertRaises(ValueError):mod.analyze(rows)
        rows[0]['ready']='0';rows[0]['seq']='2'
        with self.assertRaises(ValueError):mod.analyze(rows)
        events=[('MC_REQUEST','USDJPY',1,1,1),('MC_START','USDJPY',1,1,1),('MC_REQUEST','EURJPY',1,1,1),('MC_START','EURJPY',1,1,1),('MC_COMPLETE','USDJPY',1,1,1),('MC_COMPLETE','EURJPY',1,1,1)]
        rows=list(self.rows(mod,events))
        for row,active in zip(rows,[0,1,1,2,2,1]):row['active_symbols']=str(active)
        self.assertEqual(mod.analyze(rows)['coverage']['2_symbol'],'PARTIAL')

    def test_complete_without_start_and_empty_capture_are_incomplete(self):
        mod=self.analyzer()
        self.assertEqual(mod.analyze([])['status'],'INCOMPLETE')
        rows=list(self.rows(mod,[('MC_COMPLETE','USDJPY',1,1,1)]))
        self.assertEqual(mod.analyze(rows)['status'],'INCOMPLETE')

    def test_csv_schema_is_strict_and_never_echoes_payload(self):
        mod=self.analyzer();bad=io.StringIO('secret_field\nprivate-sensitive\n')
        with self.assertRaisesRegex(ValueError,'invalid observer evidence'):mod.read_rows(bad)


if __name__=='__main__':unittest.main()

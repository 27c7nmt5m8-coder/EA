"""Allowlisted, resumable local Tester collection for the fixed 28-case experiment.

This module never prints raw terminal journals, account fields or environment values.
The existing terminal owns its native logs; only diagnostic CSVs are copied here.
"""
import argparse
from collections import Counter
import csv
import ctypes
import hashlib
from html.parser import HTMLParser
import io
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time

try:
    from .analyze_tester_bottlenecks import analyze_rows, outcome, has, quantile
    from .analyze_mc_timeline import analyze
except ImportError:
    from analyze_tester_bottlenecks import analyze_rows, outcome, has, quantile
    from analyze_mc_timeline import analyze

REPO=Path(__file__).resolve().parents[1]
ROOT=Path.home()/'AppData/Roaming/MetaQuotes/Terminal/E3E3B02889D32F38295D39BF94B6AD4A'
COMMON=ROOT.parent/'Common/Files'
LOGROOT=Path.home()/'AppData/Roaming/MetaQuotes/Tester/E3E3B02889D32F38295D39BF94B6AD4A/Agent-127.0.0.1-3000/logs'
TERMINAL=Path('C:/Program Files/HFM Metatrader 5/terminal64.exe')
PROFILE='CodexTesterPipeline_20260924'
DEST=REPO/'verification/mc500k_20260927'
FIELDS=('Expert','ExpertParameters','Symbol','Period','Optimization','Model','FromDate','ToDate',
        'ForwardMode','Deposit','Currency','Leverage','ExecutionMode','Visual','UseLocal','UseRemote',
        'UseCloud','Report','ReplaceReport','ShutdownTerminal')
FIXED=dict(Period='M1',Optimization='0',Model='4',ForwardMode='0',Deposit='100000',Currency='USD',
           Leverage='1000',ExecutionMode='0',Visual='0',UseLocal='1',UseRemote='0',UseCloud='0',
           ReplaceReport='0',ShutdownTerminal='1')
MARKERS=('TESTER_PIPELINE_SUMMARY','TESTER_SPREAD_SUMMARY','TESTER_OPPORTUNITY_SUMMARY',
         'TESTER_BOTTLENECK_SUMMARY','TESTER_MC_SCHEDULER','TESTER_MC_VALIDATION',
         'TESTER_MC_PRIVACY_SELFTEST',
         'TESTER_MC_TIMELINE_EXPORT','TESTER_BOTTLENECK_EXPORT','TESTER_OPPORTUNITY_SELFTEST',
         'TESTER_BOTTLENECK_SELFTEST','TESTER_MC_TIMELINE_SELFTEST','TESTER_TICK_BLOCK')


class BatchFailure(ValueError):
    """Only static, internally authored failure codes belong in this exception."""


class RunnerLock:
    def __enter__(self):
        self.kernel=ctypes.WinDLL('kernel32',use_last_error=True)
        self.kernel.CreateMutexW.argtypes=[ctypes.c_void_p,ctypes.c_bool,ctypes.c_wchar_p]
        self.kernel.CreateMutexW.restype=ctypes.c_void_p
        self.kernel.ReleaseMutex.argtypes=[ctypes.c_void_p]
        self.kernel.CloseHandle.argtypes=[ctypes.c_void_p]
        self.handle=self.kernel.CreateMutexW(None,True,'Local\\CodexMCV28Runner20260927')
        if not self.handle:raise BatchFailure('runner lock unavailable')
        if ctypes.get_last_error()==183:
            self.kernel.CloseHandle(self.handle);raise BatchFailure('runner already active')
        return self
    def __exit__(self,*args):
        self.kernel.ReleaseMutex(self.handle);self.kernel.CloseHandle(self.handle)


def read_text(path):
    data=Path(path).read_bytes()
    encoding='utf-16' if data.startswith((b'\xff\xfe',b'\xfe\xff')) else ('utf-16-le' if b'\x00' in data[:512] else 'utf-8-sig')
    return data.decode(encoding)


def tester_config(text,expert,report):
    values={}
    for line in text.splitlines():
        line=line.strip()
        if not line or line=='[Tester]':continue
        if '=' not in line:raise BatchFailure('unknown configuration line')
        key,value=line.split('=',1)
        if key not in FIELDS or key in values:raise BatchFailure('unknown/duplicate configuration field')
        values[key]=value
    if set(values)!=set(FIELDS) or any(values.get(k)!=v for k,v in FIXED.items()):
        raise BatchFailure('baseline configuration mismatch')
    values.update(Expert=expert,Report=report)
    return '[Tester]\n'+'\n'.join(k+'='+values[k] for k in FIELDS)+'\n'


def strict_rows(text):
    reader=csv.DictReader(io.StringIO(text))
    if not reader.fieldnames or len(set(reader.fieldnames))!=len(reader.fieldnames):
        raise BatchFailure('missing/duplicate CSV header')
    rows=list(reader)
    if any(None in r or None in r.values() for r in rows):raise BatchFailure('incomplete CSV row')
    return rows


def percentiles(values):
    values=list(values)
    return dict(n=len(values),minimum=min(values) if values else None,
                median=quantile(values,.5),p10=quantile(values,.1),p25=quantile(values,.25),
                p90=quantile(values,.9),p95=quantile(values,.95),p99=quantile(values,.99),
                maximum=max(values) if values else None,total=sum(values))


def safe_markers(text,allowed=None):
    if allowed is None:allowed={'unknown'}
    result=[]
    for line in text.splitlines():
        for marker in MARKERS:
            at=line.find(marker+' ')
            if at>=0:
                # Export only a known diagnostic payload; terminal prefix is excluded.
                payload=line[at:].strip();tokens=payload.split()[1:]
                for token in tokens:
                    if token in ('PASS','FAIL','OK'):continue
                    if '=' not in token:raise BatchFailure('unexpected marker token')
                    key,value=token.split('=',1)
                    if key not in allowed:raise BatchFailure('unexpected marker field')
                    if not (re.fullmatch(r'[-+0-9.]+',value) or value=='symbol_bar_pattern_direction' or
                            (key=='trading_hours_filter' and value=='absent') or
                            re.fullmatch(r'CodexMCV[02]_20260927[A-Za-z0-9_.]*',value)):
                        raise BatchFailure('unexpected marker value')
                result.append(payload);break
    return result


def fields(line):return dict(re.findall(r'(\w+)=([^\s]+)',line))
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def dump(path,obj):
    path=Path(path);temporary=path.with_suffix(path.suffix+'.writing')
    temporary.write_text(json.dumps(obj,ensure_ascii=True,indent=2)+'\n',encoding='utf-8');temporary.replace(path)


def validate_replay(rows,snapshots,completed):
    if len(rows)!=(snapshots+2)*2:raise BatchFailure('numerical row coverage')
    pairs={}
    for r in rows:
        cid=int(r['cycle']);mode=int(r['mode'])
        if mode not in (0,2) or mode in pairs.setdefault(cid,{}):raise BatchFailure('numerical pair duplicate/mode')
        pairs[cid][mode]=r
        if any(r.get(k)!='1' for k in ('equal_reference','actual_equal','sequence_exact')) or r.get('sequence_errors')!='0' or r['sequence_draws']!=r['operations']:
            raise BatchFailure('numerical witness failure')
    if set(pairs).intersection({-1,-2})!={-1,-2} or any(set(m)!={0,2} for m in pairs.values()):raise BatchFailure('numerical pair missing')
    for pair in pairs.values():
        for key in ('samples','input_digest','operations','risk_bits','allowed','rng','candidate','actual_compared'):
            if pair[0].get(key)!=pair[2].get(key):raise BatchFailure('numerical pair input/output mismatch')
    if sum(int(r['actual_compared']) for r in rows)!=completed*2:raise BatchFailure('actual witness coverage')


def resume_valid(case,out):
    path=out/'result.json'
    if not path.exists():return False
    try:
        r=json.loads(path.read_text(encoding='utf-8'))
        valid=(r['status']=='PASS' and r['case']==case and r['exit_code']==0 and r['runtime_errors']==0 and
               r['warnings']==0 and r['deinit']==1 and r['exports'] and
               all((out/n).is_file() and sha(out/n)==h for n,h in r['exports'].items()))
    except (KeyError,TypeError,json.JSONDecodeError):valid=False
    if not valid:raise BatchFailure('invalid saved completion')
    return True


def schema_contract(bundle):
    sources='\n'.join(read_text(p) for p in bundle.glob('Tester*.mqh'))
    schemas=set()
    for match in re.finditer(r'FileWrite\(h,\s*((?:"[^"\r\n]*"\s*,\s*)*"[^"\r\n]*")\s*\)',sources):
        schemas.add(tuple(re.findall(r'"([^"\r\n]*)"',match.group(1))))
    marker_fields=set(re.findall(r'\b([a-z][a-z0-9_]*)=',sources))
    marker_fields.update(re.findall(r'TP(?:Append|Field|ReasonField)\(summary,\s*"([^"]+)"',sources))
    suffixes=set(re.findall(r'MCSOpen\("([^"]+)"\)',sources))
    return schemas,marker_fields,suffixes


class PrivacyGuard:
    """Private values stay in RAM; only a fixed error code may leave this object."""
    def __init__(self):
        self.values={v for k,v in os.environ.items() if v and re.search(r'(?:API_KEY|PASSWORD|CREDENTIAL|ACCESS_TOKEN)$',k,re.I)}
        for p in COMMON.rglob('*.json'):
            try:account=json.loads(read_text(p)).get('account')
            except (UnicodeError,ValueError,AttributeError):continue
            if isinstance(account,str) and account and 'REDACTED' not in account:
                self.values.add(account);self.values.update(re.findall(r'(?<!\d)\d{5,}(?!\d)',account))
                break
    def check(self,text):
        if any(v in text if not v.isdigit() else re.search(r'(?<!\d)'+re.escape(v)+r'(?!\d)',text) for v in self.values):
            raise BatchFailure('private value in export')


class ReportRows(HTMLParser):
    def __init__(self):super().__init__();self.rows=[];self.row=None;self.cell=None
    def handle_starttag(self,t,a):
        if t=='tr':self.row=[]
        elif t in ('td','th') and self.row is not None:self.cell=[]
    def handle_endtag(self,t):
        if t in ('td','th') and self.cell is not None:self.row.append(''.join(self.cell).strip());self.cell=None
        elif t=='tr' and self.row is not None:self.rows.append(self.row);self.row=None
    def handle_data(self,d):
        if self.cell is not None:self.cell.append(d)


def report_metrics(path):
    parser=ReportRows();parser.feed(read_text(path))
    values={r[i].rstrip(':'):r[i+1] for r in parser.rows for i in range(len(r)-1) if r[i].endswith(':')}
    def number(key):return float(re.sub(r'[\s,]','',re.match(r'[-+]?\d[\d\s,]*(?:\.\d+)?',values[key]).group()))
    return {'trades':int(number('取引数')),'history_quality':number('ヒストリー品質'),
            'ticks':int(number('ティック'))}


def prepare(bundle0,bundle2):
    old=json.loads((REPO/'verification/oos_bottleneck_results_20260927.json').read_text(encoding='utf-8'))['cases']
    if len(old)!=28:raise BatchFailure('expected established28 cases')
    manifest=[];seen=set();configs=ROOT/'MQL5/Profiles/Tester'
    for c in old:
        identity=f"{c['symbol']}_{c['week']}_{c['tier']}"
        if identity in seen:raise BatchFailure('duplicate baseline case')
        seen.add(identity);old_tier='XAU' if c['tier']=='Candidate' else c['tier']
        original=configs/f"CodexBottleneck_{c['symbol']}_{c['week']}_{old_tier}_20260927.ini"
        text=read_text(original);values=dict(line.split('=',1) for line in text.splitlines() if '=' in line)
        if (values['Symbol'],values['FromDate'],values['ToDate'])!=(c['symbol'],c['start'],c['end']):
            raise BatchFailure('case dates/symbol changed')
        for mode,bundle in ((0,bundle0),(2,bundle2)):
            report=f'CodexMCV{mode}_{identity}_20260927'
            config=configs/(report+'.ini');config.write_text(tester_config(text,bundle+'\\MTFAutoTrader_3Mode_AI_v2_44.ex5',report),encoding='utf-8')
            binary=ROOT/'MQL5/Experts'/bundle/'MTFAutoTrader_3Mode_AI_v2_44.ex5'
            header=read_text(binary.parent/'TesterMCSchedulerDiag.mqh')
            if not re.search(r'^#define MCS_MODE '+str(mode)+r'\s*$',header,re.M):raise BatchFailure('bundle mode mismatch')
            manifest.append(dict(case=identity,mode=mode,symbol=c['symbol'],week=c['week'],tier=c['tier'],
                start=c['start'],end=c['end'],max_atr=c['max_atr'],max_sl=c['max_sl'],config=str(config),
                config_sha256=sha(config),set_path=str(configs/values['ExpertParameters']),
                set_sha256=sha(configs/values['ExpertParameters']),report=str(ROOT/(report+'.htm')),bundle=bundle,
                binary=str(binary),binary_sha256=sha(binary),source_hashes={p.name:sha(p) for p in binary.parent.iterdir() if p.suffix in ('.mqh','.mq5')}))
    # Diagnose known causal cases first; all other cases retain original order.
    manifest.sort(key=lambda x:(0 if x['case']=='USDJPY_Sep14_Medium' else 1 if x['case']=='USDJPY_Sep14_Low' else 2))
    DEST.mkdir(parents=True,exist_ok=True);dump(DEST/'manifest.json',manifest)
    return manifest


def reason_names():
    enum=(REPO/'tools/TesterPipelineDiag.mqh').read_text(encoding='utf-8').split('enum TesterPipelineCounter')[1].split('};')[0]
    return dict(enumerate(re.findall(r'\bTP_[A-Z_]+\b',enum)))


def collect(case,destination,started,offsets,exit_code,elapsed,privacy):
    text=''
    for p in LOGROOT.glob('*.log'):
        with p.open('rb') as f:
            f.seek(offsets.get(str(p),2));data=f.read()
        text+=data.decode('utf-16-le')
    if f"Experts\\{case['bundle']}\\" not in text or 'Test passed in' not in text:
        raise BatchFailure('fresh completed test not observed')
    bundle=ROOT/'MQL5/Experts'/case['bundle'];schemas,marker_fields,suffixes=schema_contract(bundle)
    markers=safe_markers(text,marker_fields)
    privacy.check('\n'.join(markers))
    def last(marker):
        found=[fields(x) for x in markers if x.startswith(marker+' ')]
        if not found:raise BatchFailure('required diagnostic marker missing')
        return found[-1]
    pipe=last('TESTER_PIPELINE_SUMMARY');detail=last('TESTER_BOTTLENECK_SUMMARY');mc=last('TESTER_MC_SCHEDULER')
    validation=last('TESTER_MC_VALIDATION')
    if int(mc['mode'])!=case['mode'] or int(validation['unknown']) or int(pipe['deinit_reason'])!=1:
        raise BatchFailure('mode/validation/deinit mismatch')
    if any(' FAIL' in x for x in markers):raise BatchFailure('native diagnostic FAIL')
    if exit_code!=0 or int(mc['mismatch']) or int(mc['unknown']) or any(int(detail[k]) for k in ('unknown','missing','invalid_score')):
        raise BatchFailure('test/diagnostic validation failed')
    for marker in ('TESTER_OPPORTUNITY_SELFTEST','TESTER_BOTTLENECK_SELFTEST','TESTER_MC_TIMELINE_SELFTEST','TESTER_MC_PRIVACY_SELFTEST'):
        if not any(x.startswith(marker+' PASS') for x in markers):raise BatchFailure('selftest missing')
    prefix=mc['prefix'];expected=f"CodexMCV{case['mode']}_20260927_{case['symbol']}_{case['start']}_A{case['max_atr']:.2f}_S{case['max_sl']:.2f}"
    if prefix!=expected:raise BatchFailure('actual case prefix mismatch')
    filenames={last('TESTER_MC_TIMELINE_EXPORT')['file'],last('TESTER_BOTTLENECK_EXPORT')['file']}
    filenames.update(prefix+s+'.csv' for s in suffixes)
    if any(Path(n).name!=n or not n.startswith('CodexMCV') for n in filenames):raise BatchFailure('invalid export filename')
    files=[COMMON/n for n in sorted(filenames)]
    exports={}
    for p in files:
        if p.stat().st_mtime<started-1:raise BatchFailure('stale diagnostic export')
        raw=p.read_text(encoding='ascii');privacy.check(raw)
        reader=csv.reader(io.StringIO(raw));header=tuple(next(reader))
        if header not in schemas:raise BatchFailure('unexpected export schema')
        exports[p.name]=strict_rows(raw)
    def get(name):
        if name not in exports:raise BatchFailure('required CSV absent')
        return exports[name]
    events=get(last('TESTER_MC_TIMELINE_EXPORT')['file']);details=get(last('TESTER_BOTTLENECK_EXPORT')['file'])
    callbacks=get(prefix+'_callbacks.csv');replay=get(prefix+'_replay.csv');durations=get(prefix+'_events.csv')
    if len(replay)!=int(mc['comparisons']) or len(events)!=int(last('TESTER_MC_TIMELINE_EXPORT')['rows']) or len(details)!=int(last('TESTER_BOTTLENECK_EXPORT')['rows']) or len(details)!=int(detail['signals']):raise BatchFailure('export row count mismatch')
    for suffix,key in (('_requests','requests'),('_guards','guards'),('_timings','order_timings')):
        if len(get(prefix+suffix+'.csv'))!=int(validation[key]):raise BatchFailure('validation row count mismatch')
    report=Path(case['report'])
    if report.stat().st_mtime<started-1:raise BatchFailure('stale report')
    metrics=report_metrics(report);a=analyze_rows(details,reason_names());timeline=analyze(events,details)
    validate_replay(replay,int(mc['snapshots']),timeline['metrics']['completed_calculations'])
    if len(callbacks)!=sum(int(c['terminal']['advance_calls']) for c in timeline['cycles'].values() if c['start_s'] is not None):raise BatchFailure('callback count mismatch')
    if metrics['trades']!=a['funnel']['accepted']:raise BatchFailure('trades/accepted mismatch')
    if metrics['history_quality']!=100:raise BatchFailure('history quality changed')
    errors=sum(any(k in line.lower() for k in ('array out of range','zero divide','critical runtime error','initialization failed','cannot load expert')) for line in text.splitlines())
    warnings=sum(bool(re.search(r'\bwarning\b',line,re.I)) for line in text.splitlines())
    if errors or warnings:raise BatchFailure('runtime warning/error')
    for p in files:shutil.copyfile(p,destination/p.name)
    result=dict(status='PASS',case=case,exit_code=exit_code,process_seconds=elapsed,started=started,report_metrics=metrics,
        funnel=a['funnel'],outcomes=dict(Counter(outcome(r,reason_names()) for r in details)),
        timeline=timeline,details=details,events=events,call_counters=pipe,tick_markers=[x for x in markers if x.startswith('TESTER_TICK_BLOCK ')],
        callback_us=percentiles(int(x['elapsed_us']) for x in callbacks),event_durations=durations,
        scheduler=mc,validation=validation,numerical_rows=len(replay),actual_reference_rows=sum(int(r['actual_compared']) for r in replay),
        runtime_errors=errors,warnings=warnings,deinit=int(pipe['deinit_reason']),markers=markers,
        exports={name:sha(destination/name) for name in exports},extra_exports=[x for x in exports if x not in (prefix+'_callbacks.csv',prefix+'_replay.csv',prefix+'_events.csv')])
    dump(destination/'result.json',result)
    return result


def terminal_count():
    p=subprocess.run(['powershell','-NoProfile','-Command','@(Get-Process terminal64 -ErrorAction SilentlyContinue).Count'],capture_output=True,text=True,check=True)
    return int(p.stdout.strip())


def run(manifest,only=None,limit=None):
    completed=0;privacy=PrivacyGuard()
    for c in manifest:
        if only and c['case']!=only:continue
        out=DEST/c['case']/('current' if c['mode']==0 else 'fixed500k')
        if sha(c['config'])!=c['config_sha256'] or sha(c['set_path'])!=c['set_sha256']:raise BatchFailure('config/set changed')
        if sha(c['binary'])!=c['binary_sha256'] or any(sha(Path(c['binary']).parent/n)!=h for n,h in c['source_hashes'].items()):raise BatchFailure('bundle changed')
        if resume_valid(c,out):continue
        if terminal_count():raise BatchFailure('existing terminal is running')
        privacy.check(read_text(c['set_path']));privacy.check(read_text(c['config']))
        out.mkdir(parents=True,exist_ok=True);offsets={str(p):p.stat().st_size for p in LOGROOT.glob('*.log')}
        startup=subprocess.STARTUPINFO();startup.dwFlags|=subprocess.STARTF_USESHOWWINDOW;startup.wShowWindow=0
        started=time.time();stage='launch';code=None
        dump(out/'attempt.json',dict(case=c,started=started,offsets=offsets))
        try:
            p=subprocess.Popen([str(TERMINAL),'/profile:'+PROFILE,'/config:'+c['config']],startupinfo=startup,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            dump(DEST/'active.json',dict(status='RUNNING',case=c['case'],mode=c['mode'],pid=p.pid,started=started))
            stage='wait'
            try:code=p.wait(timeout=1800)
            except subprocess.TimeoutExpired:
                p.terminate();p.wait(timeout=30);raise BatchFailure('owned test process timeout')
            elapsed=time.time()-started;stage='collect'
            dump(out/'attempt.json',dict(case=c,started=started,offsets=offsets,exit_code=code,elapsed=elapsed))
            r=collect(c,out,started,offsets,code,elapsed,privacy)
        except Exception as e:
            failure=dict(status='BLOCKED',type=type(e).__name__,stage=stage,exit_code=code,seconds=time.time()-started,
                         code=str(e) if isinstance(e,BatchFailure) else 'UNCLASSIFIED',case=c['case'],mode=c['mode'])
            dump(out/'failure.json',failure);dump(DEST/'active.json',failure);raise
        dump(DEST/'active.json',dict(status='COMPLETED',case=c['case'],mode=c['mode'],ended=time.time()))
        print(json.dumps(dict(case=c['case'],mode=c['mode'],seconds=round(elapsed,2),trades=r['report_metrics']['trades'],runtime=r['runtime_errors'],warnings=r['warnings'],comparisons=r['numerical_rows'])),flush=True)
        completed+=1;time.sleep(3)
        if limit and completed>=limit:break


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--prepare',action='store_true');parser.add_argument('--run',action='store_true')
    parser.add_argument('--bundle0');parser.add_argument('--bundle2');parser.add_argument('--only');parser.add_argument('--limit',type=int)
    args=parser.parse_args()
    try:
        if args.prepare:
            if not args.bundle0 or not args.bundle2:raise BatchFailure('bundle paths required')
            manifest=prepare(args.bundle0,args.bundle2);print('Prepared '+str(len(manifest))+' runs')
        else:manifest=json.loads((DEST/'manifest.json').read_text(encoding='utf-8'))
        if args.run:
            with RunnerLock():run(manifest,args.only,args.limit)
    except Exception as error:
        # Deliberately exclude exception text: a parser may contain native data.
        print(json.dumps(dict(status='BLOCKED',exception=type(error).__name__)),flush=True);sys.exit(1)

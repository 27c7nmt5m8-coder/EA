"""Tester-only atomic-write observation, limited to JournalPersist calls."""
import argparse
from pathlib import Path
from collections import defaultdict
try:
    from .build_tester_journal_latency import build as journal_build, analyze_journal_trace
    from .build_tester_timer_latency import integer
    from .build_tester_pipeline import MAIN,replace_once
except ImportError:
    from build_tester_journal_latency import build as journal_build, analyze_journal_trace
    from build_tester_timer_latency import integer
    from build_tester_pipeline import MAIN,replace_once

IO_STAGES=('serialize_json','serialize_csv','convert','open','write','flush','close','move','delete','write_total')


def edits_for(name):
    if name==MAIN:return (
        ('#include "TesterJournalLatencyDiag.mqh"','#include "TesterJournalLatencyDiag.mqh"\n#include "TesterJournalIOLatencyDiag.mqh"'),
        ('TJExport();MCSFinish();','TJExport();TJIExport();MCSFinish();'))
    if name=='TesterTimerLatencyDiag.mqh':return (
        ('ulong journal[4],jdetail[32],jcalls[32];uint jseen;',
         'ulong journal[4],jdetail[32],jcalls[32];uint jseen;\n ulong io[40],iocalls[40];'),)
    if name=='MT3TradeJournal.mqh':return (
        (' if(!WriteAIFile(base+".json",TradeRecordJSON(r)) || !WriteAIFile(base+".csv",TradeRecordCSV(r)))',
         ' if(!TJIWriteAIFile(base+".json",TJIRecordJSON(r)) || !TJIWriteAIFile(base+".csv",TJIRecordCSV(r)))'),)
    return ()


def atomic_function(data):
    if data.count(b'bool WriteAIFile(')!=1 or data.count(b'bool ReadAIFile(')!=1:raise ValueError('ambiguous atomic helper')
    return data[data.index(b'bool WriteAIFile('):data.index(b'bool ReadAIFile(')]


def atomic_edits():
    return (
        ('bool WriteAIFile(string name,const string text)','bool TJIWriteCore(string name,const string text)'),
        (' string tmp=name+".tmp";uchar bytes[];int count=StringToCharArray(text,bytes,0,WHOLE_ARRAY,CP_UTF8)-1;',
         ' ulong ioPart=TJIClock();string tmp=name+".tmp";uchar bytes[];int count=StringToCharArray(text,bytes,0,WHOLE_ARRAY,CP_UTF8)-1;TJIRecord(2,ioPart);'),
        (' int h=FileOpen(tmp,FILE_WRITE|FILE_BIN|FILE_COMMON);if(h==INVALID_HANDLE) return false;',
         ' ioPart=TJIClock();int h=FileOpen(tmp,FILE_WRITE|FILE_BIN|FILE_COMMON);TJIRecord(3,ioPart);if(h==INVALID_HANDLE) return false;'),
        (' uint n=FileWriteArray(h,bytes,0,count);FileFlush(h);FileClose(h);',
         ' ioPart=TJIClock();uint n=FileWriteArray(h,bytes,0,count);TJIRecord(4,ioPart);\n ioPart=TJIClock();FileFlush(h);TJIRecord(5,ioPart);\n ioPart=TJIClock();FileClose(h);TJIRecord(6,ioPart);'),
        ('!FileMove(tmp,FILE_COMMON,name,FILE_COMMON|FILE_REWRITE)','!TJIFileMove(tmp,FILE_COMMON,name,FILE_COMMON|FILE_REWRITE)'),
        ('FileDelete(tmp,FILE_COMMON);return false;','TJIFileDelete(tmp,FILE_COMMON);return false;'),
    )


def restore_file(name,data):
    for old,new in reversed(edits_for(name)):data=replace_once(data,new,old)
    return data


def restore_atomic_function(header):
    if header.count(b'// ATOMIC_BEGIN\n')!=1 or header.count(b'// ATOMIC_END\n')!=1:raise ValueError('atomic observation marker mismatch')
    data=header.split(b'// ATOMIC_BEGIN\n')[1].split(b'// ATOMIC_END\n')[0]
    for old,new in reversed(atomic_edits()):data=replace_once(data,new,old)
    return data


def build(output,mode=2):
    main=journal_build(Path(output),mode)
    core=atomic_function((main.parent/'MT3AIProtocol.mqh').read_bytes())
    instrumented=core
    for old,new in atomic_edits():instrumented=replace_once(instrumented,old,new)
    header=Path(__file__).with_name('TesterJournalIOLatencyDiag.mqh').read_bytes()+b'\n// ATOMIC_BEGIN\n'+instrumented+b'// ATOMIC_END\n'
    if restore_atomic_function(header)!=core:raise ValueError('atomic helper behavior changed')
    for name in (MAIN,'MT3TradeJournal.mqh','TesterTimerLatencyDiag.mqh'):
        p=main.parent/name;original=p.read_bytes();data=original
        for old,new in edits_for(name):data=replace_once(data,old,new)
        if restore_file(name,data)!=original:raise ValueError('IO transform not reversible')
        p.write_bytes(data)
    (main.parent/'TesterJournalIOLatencyDiag.mqh').write_bytes(header)
    return main


def analyze_io_trace(rows,journal,timers,summaries):
    attribution=analyze_journal_trace(journal,timers,summaries)
    parents={(integer(r['timer_id']),r['symbol']):r for r in journal if r['stage']=='persist'}
    groups=defaultdict(dict)
    for r in rows:
        key=(integer(r['timer_id']),r['symbol']);stage=r['stage']
        if key not in parents or stage not in IO_STAGES or stage in groups[key]:raise ValueError('unknown/duplicate IO partition')
        parent=parents[key]
        if any(integer(r[k])!=integer(parent[k]) for k in ('server_s','start_wall_us','end_wall_us','total_us')):raise ValueError('mixed IO clocks')
        calls,duration=integer(r['calls']),integer(r['duration_us'])
        if not calls and duration:raise ValueError('unvisited IO phase has duration')
        groups[key][stage]=(calls,duration)
    if set(groups)!=set(parents):raise ValueError('IO symbol coverage mismatch')
    for key,g in groups.items():
        if set(g)!=set(IO_STAGES):raise ValueError('incomplete IO phases')
        n={s:g[s][0] for s in IO_STAGES};d={s:g[s][1] for s in IO_STAGES}
        if (n['serialize_csv']>n['serialize_json'] or n['write_total']!=n['serialize_json']+n['serialize_csv'] or
            n['convert']!=n['write_total'] or n['open']>n['convert'] or n['write']>n['open'] or
            n['flush']!=n['write'] or n['close']!=n['write'] or n['move']>n['write'] or n['delete']>n['write']):
            raise ValueError('impossible atomic IO call counts')
        # Every written attempt ends with move or failure cleanup. A successful
        # JSON write necessarily triggers CSV, which contributes at most one
        # more success. These are aggregate bounds, including short circuits.
        successes=n['write']-n['delete']
        if (n['move']+n['delete']<n['write'] or
            not n['serialize_csv']<=successes<=2*n['serialize_csv']):
            raise ValueError('impossible completed atomic IO outcomes')
        if not integer(parents[key]['calls']) and any(n.values()):
            raise ValueError('unvisited persist has IO calls')
        if sum(d[s] for s in IO_STAGES[2:9])>d['write_total']:raise ValueError('atomic IO partitions overlap')
        if d['serialize_json']+d['serialize_csv']+d['write_total']>integer(parents[key]['duration_us']):raise ValueError('IO exceeds persist parent')
    timer=attribution['maximum_journal_timer_id'];symbol=attribution['dominant_symbol']
    if (timer,symbol) not in groups:return dict(attribution='UNKNOWN',reason='maximum has no persist context')
    g=groups[timer,symbol];durations={s:g[s][1] for s in IO_STAGES}
    persist=integer(parents[timer,symbol]['duration_us'])
    residual=persist-durations['serialize_json']-durations['serialize_csv']-durations['write_total']
    atomic_residual=durations['write_total']-sum(durations[s] for s in IO_STAGES[2:9])
    dominant=max(IO_STAGES[:9],key=durations.get)
    if durations[dominant]<=max(residual,atomic_residual):dominant='UNKNOWN'
    return dict(maximum_journal_timer_id=timer,symbol=symbol,persist_us=persist,
                dominant_io_stage=dominant,dominant_io_us=durations.get(dominant,0),
                io_us=durations,io_calls={s:g[s][0] for s in IO_STAGES},persist_unpartitioned_us=residual,
                atomic_unpartitioned_us=atomic_residual,flush_success_status='UNKNOWN_VOID_RETURN',
                queue_depth='UNKNOWN',wall_time_is_cpu_time=False)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--mode',type=int,choices=(0,2),default=2);a=p.parse_args();print(build(a.output,a.mode))

"""Reversible Tester-only JournalMaintenance partition; no product I/O changes."""
import argparse
from collections import defaultdict
from pathlib import Path

try:
    from .build_tester_timer_latency import build as timer_build, analyze_timer_trace, integer
    from .build_tester_pipeline import MAIN, replace_once
except ImportError:
    from build_tester_timer_latency import build as timer_build, analyze_timer_trace, integer
    from build_tester_pipeline import MAIN, replace_once

JOURNAL_STAGES=('sample_guard','history_select','collect_ids','queue','persist','cursor','portfolio','cleanup')


def edits_for(name):
    if name==MAIN:
        return (
            ('#include "TesterTimerLatencyDiag.mqh"','#include "TesterTimerLatencyDiag.mqh"\n#include "TesterJournalLatencyDiag.mqh"'),
            ('g_symbols[i].JournalMaintenance();}',
             'ulong tjStart=TJEnter(i,g_symbols[i].m_symbol);g_symbols[i].JournalMaintenance();TJLeave(tjStart);}'),
            ('TLExport();MCSFinish();','TLExport();TJExport();MCSFinish();'),
        )
    if name=='TesterTimerLatencyDiag.mqh':
        return (('int copyError[8];long server;uint seen;bool probed;',
                 'int copyError[8];long server;uint seen;bool probed;\n ulong journal[4],jdetail[32],jcalls[32];uint jseen;'),)
    if name=='MT3TradeJournal.mqh':
        return (
            (' if(!EnableTradeLog) return;\n JournalSample();datetime now=TimeCurrent();',
             ' if(!EnableTradeLog) return;\n ulong tjPart=TJClock();JournalSample();datetime now=TimeCurrent();TJPart(0,tjPart);'),
            (' m_lastJournalAt=now;bool ok=true;\n if(HistorySelect',
             ' m_lastJournalAt=now;bool ok=true;tjPart=TJClock();\n if(HistorySelect'),
            (' {\n  ulong ids[];\n  for(int i=0;i<HistoryDealsTotal();i++)',
             ' {\n  TJPart(1,tjPart);tjPart=TJClock();\n  ulong ids[];\n  for(int i=0;i<HistoryDealsTotal();i++)'),
            ('  for(int i=0;i<ArraySize(ids);i++) if(!JournalQueue(ids[i])) ok=false;\n }',
             '  TJPart(2,tjPart);tjPart=TJClock();\n  for(int i=0;i<ArraySize(ids);i++) if(!JournalQueue(ids[i])) ok=false;\n  TJPart(3,tjPart);\n }'),
            (' else {ok=false;JournalWarn("history unavailable for log reconciliation");}\n for(int i=ArraySize(m_journal)-1;i>=0;i--)',
             ' else {TJPart(1,tjPart);ok=false;JournalWarn("history unavailable for log reconciliation");}\n tjPart=TJClock();\n for(int i=ArraySize(m_journal)-1;i>=0;i--)'),
            (' if(ok)\n {\n  m_journalFrom=now;',
             ' TJPart(4,tjPart);tjPart=TJClock();\n if(ok)\n {\n  m_journalFrom=now;'),
            (' if(m_portfolioReportDirty)\n {',
             ' TJPart(5,tjPart);tjPart=TJClock();\n if(m_portfolioReportDirty)\n {'),
            (' if(ArraySize(m_journal)==0 && !HasOurPosition() && !HasUnresolvedOrder()) FileDelete(JournalActiveFile(),FILE_COMMON);\n m_journalDirty=!ok;',
             ' TJPart(6,tjPart);tjPart=TJClock();\n if(ArraySize(m_journal)==0 && !HasOurPosition() && !HasUnresolvedOrder()) FileDelete(JournalActiveFile(),FILE_COMMON);\n m_journalDirty=!ok;TJPart(7,tjPart);'),
        )
    return ()


def restore_file(name,data):
    for old,new in reversed(edits_for(name)):
        data=replace_once(data,new,old)
    return data


def build(output,mode=2):
    main=timer_build(Path(output),mode,nested=True)
    for name in (MAIN,'TesterTimerLatencyDiag.mqh','MT3TradeJournal.mqh'):
        p=main.parent/name
        original=p.read_bytes();data=original
        for old,new in edits_for(name):data=replace_once(data,old,new)
        if restore_file(name,data)!=original:raise ValueError('Journal transform is not reversible')
        p.write_bytes(data)
    (main.parent/'TesterJournalLatencyDiag.mqh').write_bytes(Path(__file__).with_name('TesterJournalLatencyDiag.mqh').read_bytes())
    return main


def analyze_journal_trace(rows,timers,summaries):
    analyze_timer_trace(timers,summaries)
    witness={integer(r['timer_id']):r for r in timers if r['stage']=='journal'}
    roots={};groups=defaultdict(dict)
    for r in rows:
        key=integer(r['timer_id']);duration=integer(r['duration_us']);calls=integer(r['calls'])
        if key not in witness:raise ValueError('Journal timer is not retained')
        w=witness[key]
        if any(integer(r[k])!=integer(w[k]) for k in ('server_s','start_wall_us','end_wall_us','total_us')):
            raise ValueError('mixed Journal/body clocks')
        stage,symbol=r['stage'],r['symbol']
        if stage=='journal_root':
            if symbol!='ALL' or key in roots or duration!=integer(w['duration_us']):raise ValueError('invalid/duplicate Journal root')
            roots[key]=r;continue
        if symbol not in ('USDJPY','EURUSD','EURJPY','XAUUSD') or stage not in set(JOURNAL_STAGES)|{'symbol_journal'}:
            raise ValueError('unknown Journal symbol/stage')
        group=groups[key,symbol]
        if stage in group or calls>1 or (calls==0 and duration!=0):raise ValueError('duplicate or contradictory Journal measurement')
        group[stage]=r
    if set(roots)!=set(witness):raise ValueError('missing retained Journal roots')
    parent_sums=defaultdict(int);visits=defaultdict(int)
    residuals={}
    for (key,symbol),g in groups.items():
        if set(g)!=set(JOURNAL_STAGES)|{'symbol_journal'}:raise ValueError('missing Journal partition')
        parent=integer(g['symbol_journal']['duration_us'])
        if integer(g['symbol_journal']['calls'])!=1:raise ValueError('Journal parent must represent one invocation')
        counts=tuple(integer(g[s]['calls']) for s in JOURNAL_STAGES)
        if counts not in ((1,0,0,0,0,0,0,0),(1,1,0,0,1,1,1,1),(1,1,1,1,1,1,1,1)):
            raise ValueError('impossible Journal phase sequence')
        partitioned=sum(integer(g[s]['duration_us']) for s in JOURNAL_STAGES)
        if partitioned>parent:raise ValueError('Journal partitions exceed parent')
        residuals[key,symbol]=parent-partitioned
        parent_sums[key]+=parent;visits[key]+=1
    for key,r in roots.items():
        if parent_sums[key]>integer(r['duration_us']) or visits[key]!=integer(r['calls']):raise ValueError('Journal parent/root mismatch')
    key=max(roots,key=lambda i:integer(roots[i]['duration_us']))
    maximum=integer(roots[key]['duration_us'])
    expected=integer(next(r for r in summaries if r['stage']=='journal')['max_us'])
    if maximum!=expected:raise ValueError('population Journal maximum not retained')
    available=[(symbol,g) for (timer,symbol),g in groups.items() if timer==key]
    dominant=max(available,key=lambda pair:integer(pair[1]['symbol_journal']['duration_us'])) if available else None
    outer_residual=maximum-parent_sums[key]
    phase=max(JOURNAL_STAGES,key=lambda s:integer(dominant[1][s]['duration_us'])) if dominant else 'UNKNOWN'
    if dominant and (integer(dominant[1][phase]['duration_us'])<=residuals[key,dominant[0]] or
                     integer(dominant[1]['symbol_journal']['duration_us'])<=outer_residual):phase='UNKNOWN'
    return dict(maximum_journal_timer_id=key,maximum_journal_us=maximum,
                dominant_symbol=dominant[0] if dominant else 'UNKNOWN',
                dominant_phase=phase,
                symbol_phases={symbol:{s:integer(g[s]['duration_us']) for s in ('symbol_journal',)+JOURNAL_STAGES} for symbol,g in available},
                unattributed_journal_us=outer_residual,
                symbol_unattributed_us={symbol:residuals[key,symbol] for symbol,g in available},
                total_unpartitioned_journal_us=outer_residual+sum(residuals[key,symbol] for symbol,g in available),
                population_p95='UNKNOWN',queue_depth='UNKNOWN')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,required=True);p.add_argument('--mode',type=int,choices=(0,2),default=2)
    a=p.parse_args();print(build(a.output,a.mode))

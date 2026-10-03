"""Reversible, Tester-only OnTimer stage measurements; no MC/trading edits."""
import argparse
from collections import defaultdict
from pathlib import Path
import re
import tempfile

try:
    from .build_tester_mc_multisymbol import build as baseline_build
    from .build_tester_pipeline import MAIN, STATE, SOURCE, replace_once
except ImportError:
    from build_tester_mc_multisymbol import build as baseline_build
    from build_tester_pipeline import MAIN, STATE, SOURCE, replace_once

STAGES = ('maintain', 'universe', 'scan', 'mc', 'shadow', 'dispatch', 'journal', 'dashboard')
NESTED_STAGES = ('scan_maintain','scan_lines','scan_bar','scan_candidate','indicator_actual','indicator_observer')


def edits():
    return (
        ('#include "MT3SymbolState.mqh"', '#include "MT3SymbolState.mqh"\n#include "TesterTimerLatencyDiag.mqh"'),
        ('g_tpmcTimer++;ulong mcsTimerStart=GetMicrosecondCount();',
         'g_tpmcTimer++;ulong mcsTimerStart=GetMicrosecondCount();TLBegin(mcsTimerStart);'),
        (' MaintainExposure();\n if(TimeCurrent()-g_universeAt>=UniverseRefreshSeconds) RefreshUniverse();',
         ' MaintainExposure();TLMark(0);\n if(TimeCurrent()-g_universeAt>=UniverseRefreshSeconds) RefreshUniverse();\n TLMark(1);'),
        ('  g_symbols[i].Scan();scanned++;',
         '  ulong tlScanStart=GetMicrosecondCount();TLStartScan(i);g_symbols[i].Scan();TLScan(i,g_symbols[i].m_symbol,tlScanStart);scanned++;'),
        (' ulong deadline=GetTickCount64()+(ulong)MonteCarloTimerBudgetMs;',
         ' TLMark(2);\n ulong deadline=GetTickCount64()+(ulong)MonteCarloTimerBudgetMs;'),
        (' bool mcmNatural=false;', ' TLMark(3);\n bool mcmNatural=false;'),
        (' DispatchQueue();ServiceTradeJournals();RenderDashboard();\n MCSMeasure(1,GetMicrosecondCount()-mcsTimerStart);',
         ' TLMark(4);\n DispatchQueue();TLMark(5);ServiceTradeJournals();TLMark(6);RenderDashboard();TLMark(7);\n ulong tlEnd=GetMicrosecondCount();MCSMeasure(1,tlEnd-mcsTimerStart);TLFinish(tlEnd);'),
        ('MCSFinish();MCVExport();MCMExport();return 0;',
         'TLExport();MCSFinish();MCVExport();MCMExport();return 0;'),
    )


def restore_main(data: bytes) -> bytes:
    for old, new in reversed(edits()):
        data = replace_once(data, new, old)
    return data


def state_edits():
    return (
        ('void Scan()\n{\n Maintain(true);',
         'void Scan()\n{\n ulong tlPart=TLProbeClock();Maintain(true);TLPart(0,tlPart);'),
        (' if(!m_scanEnabled) return;\n datetime line=iTime(m_symbol,LineTimeframe,0);',
         ' if(!m_scanEnabled) return;\n tlPart=TLProbeClock();\n datetime line=iTime(m_symbol,LineTimeframe,0);'),
        (' {UpdateAllAutoLines();g_lastLineBar=line;}\n datetime tpPreviousBar=g_lastBarTime;',
         ' {UpdateAllAutoLines();g_lastLineBar=line;}\n TLPart(1,tlPart);tlPart=TLProbeClock();\n datetime tpPreviousBar=g_lastBarTime;'),
        (' if(ExecutionMode!=EXECUTION_MANUAL) RefreshCandidate();\n}\n#include "TesterMCSchedulerValidationMethods.mqh"',
         ' TLPart(2,tlPart);tlPart=TLProbeClock();\n if(ExecutionMode!=EXECUTION_MANUAL) RefreshCandidate();\n TLPart(3,tlPart);\n}\n#include "TesterMCSchedulerValidationMethods.mqh"'),
        (' int copied=CopyBuffer(handle,buffer,shift,1,a);TPCopyBufferResult(copied,GetLastError());',
         ' ulong tlCopyStart=TLProbeClock();\n int copied=CopyBuffer(handle,buffer,shift,1,a);int tlCopyError=GetLastError();\n ulong tlCopyEnd=tlCopyStart>0?GetMicrosecondCount():0;TPCopyBufferResult(copied,tlCopyError);\n if(tlCopyStart>0) TLReadCopy(g_tpShadow,copied,tlCopyError,tlCopyEnd-tlCopyStart);'),
    )


def restore_state(data: bytes) -> bytes:
    for old,new in reversed(state_edits()):
        data=replace_once(data,new,old)
    return data


def build(output: Path, mode: int = 2, nested: bool = False) -> Path:
    output = Path(output).resolve()
    if mode not in (0, 2) or output.exists() or output == SOURCE.resolve() or SOURCE.resolve() in output.parents:
        raise ValueError('new Tester-only destination and Current20k/fixed500k required')
    with tempfile.TemporaryDirectory() as tmp:
        staged = baseline_build(Path(tmp) / 'bundle', mode).parent
        files = {p.name: p.read_bytes() for p in staged.iterdir()}
    original = files[MAIN]
    for old, new in edits():
        files[MAIN] = replace_once(files[MAIN], old, new)
    if restore_main(files[MAIN]) != original:
        raise ValueError('timer instrumentation is not reversible')
    if nested:
        original_state=files[STATE]
        for old,new in state_edits():
            files[STATE]=replace_once(files[STATE],old,new)
        if restore_state(files[STATE])!=original_state:
            raise ValueError('nested probe is not reversible')
    files['TesterTimerLatencyDiag.mqh'] = (f'#define TL_NESTED {1 if nested else 0}\n'.encode() +
        Path(__file__).with_name('TesterTimerLatencyDiag.mqh').read_bytes())
    output.mkdir(parents=True)
    for name, data in files.items():
        (output / name).write_bytes(data)
    return output / MAIN


def integer(value) -> int:
    if not isinstance(value, str) or not re.fullmatch(r'0|[1-9][0-9]*', value):
        raise ValueError('unknown/non-integer timing field')
    return int(value)


def analyze_timer_trace(rows: list[dict], summaries: list[dict]) -> dict:
    """Top records explain observed maxima, never population percentiles/queue delay."""
    overall = [r for r in summaries if r.get('stage') == 'OnTimer']
    if len(overall) != 1 or len(summaries) != 9 or {r.get('stage') for r in summaries} != set(STAGES) | {'OnTimer'}:
        raise ValueError('missing/duplicate population summary')
    s = overall[0]
    count, recorded, maximum = (integer(s[k]) for k in ('count', 'recorded', 'max_us'))
    if (integer(s['unknown']) or count == 0 or recorded != min(count, 256) or
            not maximum <= integer(s['total_us']) <= count * maximum):
        raise ValueError('incomplete/corrupt population summary')
    totals = {}
    maxima = {}
    for row in summaries:
        if (integer(row['count']) != count or integer(row['recorded']) != recorded or integer(row['unknown']) or
                not integer(row['max_us']) <= integer(row['total_us']) <= count * integer(row['max_us']) or integer(row['max_us']) > maximum or
                integer(row['bookkeeping_max_us']) != integer(s['bookkeeping_max_us'])):
            raise ValueError('contradictory population summary')
        totals[row['stage']] = integer(row['total_us'])
        maxima[row['stage']] = integer(row['max_us'])
    if sum(totals[stage] for stage in STAGES) > totals['OnTimer']:
        raise ValueError('population partitions exceed OnTimer total')
    frames = defaultdict(dict)
    nested = defaultdict(list)
    detail = defaultdict(list)
    for row in rows:
        key = integer(row['timer_id'])
        if not 1 <= key <= count:
            raise ValueError('invalid timer identity')
        parsed = {k: integer(row[k]) for k in ('server_s', 'start_wall_us', 'end_wall_us', 'duration_us', 'total_us')}
        if parsed['end_wall_us'] - parsed['start_wall_us'] != parsed['total_us'] or parsed['duration_us'] > parsed['total_us']:
            raise ValueError('inconsistent clock/duration')
        stage = row['stage']
        if stage == 'symbol_scan' or stage in NESTED_STAGES:
            if stage in NESTED_STAGES and key > 100:
                raise ValueError('nested detail outside first-100 probe window')
            if row['symbol'] not in ('USDJPY', 'EURUSD', 'EURJPY', 'XAUUSD'):
                raise ValueError('unknown diagnostic symbol')
            (nested if stage=='symbol_scan' else detail)[key].append(row)
            continue
        if stage not in STAGES or row['symbol'] != 'ALL' or stage in frames[key]:
            raise ValueError('unknown/duplicate stage')
        frames[key][stage] = parsed
    if len(frames) != recorded or (set(nested) | set(detail)) - set(frames):
        raise ValueError('retained timer coverage mismatch')
    for key, phases in frames.items():
        if set(phases) != set(STAGES):
            raise ValueError('incomplete timer partition')
        witness = phases[STAGES[0]]
        if any(any(p[k] != witness[k] for k in ('server_s','start_wall_us','end_wall_us','total_us')) for p in phases.values()):
            raise ValueError('mixed timer clocks')
        if sum(p['duration_us'] for p in phases.values()) > witness['total_us']:
            raise ValueError('partition exceeds OnTimer duration')
        if any(p['duration_us'] > maxima[stage] for stage,p in phases.items()):
            raise ValueError('retained stage exceeds population maximum')
        scans = nested[key]
        if any(any(integer(r[k]) != witness[k] for k in ('server_s','start_wall_us','end_wall_us','total_us')) for r in scans):
            raise ValueError('mixed nested timer clocks')
        if len({r['symbol'] for r in scans}) != len(scans) or sum(integer(r['duration_us']) for r in scans) > phases['scan']['duration_us']:
            raise ValueError('contradictory nested Scan timing')
        outer={r['symbol']:integer(r['duration_us']) for r in scans}
        if detail[key] and {r['symbol'] for r in detail[key]} != set(outer):
            raise ValueError('missing probed symbol detail group')
        seen=set()
        for row in detail[key]:
            pair=(row['symbol'],row['stage'])
            if pair in seen or row['symbol'] not in outer or integer(row['duration_us'])>outer[row['symbol']]:
                raise ValueError('contradictory nested phase')
            seen.add(pair)
            if any(integer(row[k])!=witness[k] for k in ('server_s','start_wall_us','end_wall_us','total_us')):
                raise ValueError('mixed nested phase clocks')
        for symbol in {r['symbol'] for r in detail[key]}:
            durations={r['stage']:integer(r['duration_us']) for r in detail[key] if r['symbol']==symbol}
            if set(durations)!=set(NESTED_STAGES) or sum(durations[s] for s in NESTED_STAGES[:4])>outer[symbol]:
                raise ValueError('incomplete/overlapping Scan partition')
            if durations['indicator_actual']+durations['indicator_observer']>sum(durations[s] for s in NESTED_STAGES[:4]):
                raise ValueError('sequential indicator requests exceed Scan partition')
    if (sum(frame['maintain']['total_us'] for frame in frames.values()) > totals['OnTimer'] or
            any(sum(frame[stage]['duration_us'] for frame in frames.values()) > totals[stage] for stage in STAGES)):
        raise ValueError('retained records exceed population totals')
    key = max(frames, key=lambda i: frames[i]['maintain']['total_us'])
    frame = frames[key]
    if frame['maintain']['total_us'] != maximum:
        raise ValueError('population maximum missing from retained records')
    stages = {stage: p['duration_us'] for stage,p in frame.items()}
    return dict(observed_timer_count=count, retained_timer_count=recorded, maximum_timer_id=key,
                maximum_us=maximum, dominant_stage=max(stages,key=stages.get), maximum_stages_us=stages,
                maximum_symbol_scans=[dict(symbol=r['symbol'],duration_us=integer(r['duration_us'])) for r in nested[key]],
                maximum_nested_scans=[dict(stage=r['stage'],symbol=r['symbol'],duration_us=integer(r['duration_us'])) for r in detail[key]],
                unattributed_us=maximum-sum(stages.values()), bookkeeping_max_us=integer(s['bookkeeping_max_us']),
                population_p95_us='UNKNOWN', event_arrival_delay='UNKNOWN', queue_depth='UNKNOWN')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--mode',type=int,choices=(0,2),default=2)
    parser.add_argument('--nested',action='store_true',help='Scan/CopyBuffer probe, first 100 Timer callbacks only')
    args = parser.parse_args()
    print(build(args.output,args.mode,args.nested))

"""Read only hash-bound allowlisted exports; never read native journals."""
import argparse
import json
from pathlib import Path
import sys

# Direct script invocation and module execution use the same repository tools.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.analyze_mc_multisymbol import describe_case, require_export
from tools.build_tester_timer_latency import analyze_timer_trace
from tools.build_tester_journal_latency import analyze_journal_trace
from tools.build_tester_journal_io import analyze_io_trace
from tools.mc500k_batch import PrivacyGuard


def analyze(directory, baseline):
    directory, baseline = Path(directory), Path(baseline)
    result = json.loads((directory/'result.json').read_text(encoding='utf-8'))
    timers = require_export(directory, result, '_timer_sections.csv')
    summaries = require_export(directory, result, '_timer_summary.csv')
    journal = require_export(directory, result, '_journal_sections.csv')
    io = require_export(directory, result, '_journal_io.csv')
    current, prior = describe_case(directory), describe_case(baseline)
    comparisons = {key: current[key] == prior[key] for key in
                   ('chart_processed_ticks', 'symbol_bar_process_total', 'trades')}
    if set(current['symbols']) != set(prior['symbols']):
        raise ValueError('baseline symbol set differs')
    for symbol in current['symbols']:
        for key in ('funnel', 'outcomes', 'order_acceptance'):
            comparisons[symbol+'_'+key] = current['symbols'][symbol][key] == prior['symbols'][symbol][key]
    if not all(comparisons.values()):
        raise ValueError('unexplained tick/bar/funnel/trade difference')
    if result['runtime_errors'] or result['warnings']:
        raise ValueError('runtime error or warning requires investigation')
    return dict(timer=analyze_timer_trace(timers, summaries),
                journal=analyze_journal_trace(journal, timers, summaries),
                io=analyze_io_trace(io, journal, timers, summaries),
                comparison=comparisons, runtime_errors=result['runtime_errors'],
                warnings=result['warnings'], replay_rows=result['replay_rows'],
                processed_ticks=current['chart_processed_ticks'],
                processed_bars=current['symbol_bar_process_total'], trades=current['trades'],
                orders_accepted={s:c['order_acceptance'] for s,c in current['symbols'].items()})


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    parser.add_argument('baseline', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    data = analyze(args.directory, args.baseline)
    text = json.dumps(data, indent=2)+'\n'
    PrivacyGuard().check(text)
    args.output.write_text(text, encoding='utf-8')
    print(json.dumps({k:data[k] for k in ('runtime_errors', 'warnings', 'replay_rows', 'trades')}))

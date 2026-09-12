"""Independent numerical examples for the offline CSV aggregator."""
from pathlib import Path
import csv
import hashlib
import importlib.util
import json
import tempfile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('stats', ROOT / 'tools/build_pattern_stats.py')
stats = importlib.util.module_from_spec(spec)
spec.loader.exec_module(stats)
cases = []


def check(name, condition):
    cases.append({'case': name, 'passed': bool(condition)})
    assert condition, name


def record(index, **kwargs):
    row = {key: '' for key in sorted(stats.REQUIRED)}
    row.update(SchemaVersion='244', DatasetID='LIVE_A', RecordKey=f'LIVE_A/{index}', Account='broker/1',
               Symbol='FX', MagicNumber='24301', PositionIdentifier=str(9007199254741000 + index),
               Status='CLOSED', PatternName='BULLISH_123_REVERSAL', SLSource='PATTERN_123_P3',
               ExitDateTime=f'2026.09.08 01:00:{index:02}', NetProfit='100', RealizedR='1', Result='WIN',
               FinalScore='80', MTFScore='85', PatternScore='90', SpreadATRRatio='0.05')
    row.update(kwargs)
    return row


with tempfile.TemporaryDirectory() as directory:
    root = Path(directory); source = root / 'source'; output = root / 'output'
    rows = [record(1, NetProfit='200', RealizedR='2'),
            record(2, Symbol='GOLD', NetProfit='-100', RealizedR='-1', Result='LOSS'),
            record(3, NetProfit='-50', RealizedR='-0.5', Result='LOSS'),
            record(4, NetProfit='0', RealizedR='0', Result='BREAKEVEN'),
            record(5, PatternName='BEARISH_FAILED_BREAKOUT', SLSource='PATTERN_FAILED_BREAK_EXTREME',
                   FinalScore='', MTFScore='', PatternScore='', SpreadATRRatio='', RealizedR=''),
            record(6, DatasetID='TEST_A', RecordKey='TEST_A/6', NetProfit='999', RealizedR='9.99'),
            record(7, Status='OPEN', NetProfit='', RealizedR='', Result='', ExitDateTime='')]
    for i, row in enumerate(rows):
        stats.write_csv(source / f'x_position_{i}.csv', sorted(stats.REQUIRED), [row])
    stats.write_csv(source / 'copies/x_position_0.csv', sorted(stats.REQUIRED), [rows[0]])
    old = dict(rows[1], Status='OPEN', NetProfit='', RealizedR='', Result='', ExitDateTime='')
    stats.write_csv(source / 'old/x_position_1.csv', sorted(stats.REQUIRED), [old])
    reject_columns = ['DatasetID', 'Symbol', 'PortfolioRiskRejects', 'CountingUnit']
    for symbol, count in [('FX', '4'), ('GOLD', '3')]:
        stats.write_csv(source / f'{symbol}_risk_rejects.csv', reject_columns,
                        [dict(zip(reject_columns, ['LIVE_A', symbol, count, 'REJECTED_SYMBOL_M1_BARS']))])
    result = stats.build(source, output)
    check('duplicate snapshots merge by immutable RecordKey', result['positions'] == 7 and result['duplicate_copies_skipped'] == 2)
    check('partial/open trades excluded from completed counts', result['closed'] == 6)
    patterns = stats.csv_rows(output / 'PatternStats.csv')[1]
    p = next(r for r in patterns if r['DatasetID'] == 'LIVE_A' and r['PatternName'] == 'BULLISH_123_REVERSAL')
    check('123 pattern names and cross-symbol grouping', int(p['Trades']) == 4 and int(p['Wins']) == 1 and int(p['Losses']) == 2 and int(p['Breakevens']) == 1)
    check('win rate denominator includes break-even', float(p['WinRate']) == 25)
    check('known initial R total and average', float(p['TotalR']) == .5 and float(p['AverageR']) == .125)
    check('profit factor uses summed net wins/losses', abs(float(p['ProfitFactor']) - 200/150) < 1e-12)
    check('expectancy uses account-currency net profit', float(p['Expectancy']) == 12.5)
    check('chronological maximum consecutive losses', int(p['MaxConsecutiveLosses']) == 2)
    check('score and spread averages', float(p['AverageFinalScore']) == 80 and float(p['AverageMTFScore']) == 85 and float(p['AveragePatternScore']) == 90 and float(p['AverageSpreadATR']) == .05)
    unknown = next(r for r in patterns if r['PatternName'] == 'BEARISH_FAILED_BREAKOUT')
    check('unknown initial R and scores stay unknown', unknown['AverageR'] == '' and unknown['KnownRTrades'] == '0' and unknown['AverageFinalScore'] == '')
    check('PF with wins and no losses is explicit INF', unknown['ProfitFactor'] == 'INF')
    check('tester and live datasets are separated', len(patterns) == 3 and result['datasets'] == 2)
    sl = stats.csv_rows(output / 'SLSourceStats.csv')[1]
    check('SL source groups preserve structural reasons', {r['SLSource'] for r in sl} == {'PATTERN_123_P3', 'PATTERN_FAILED_BREAK_EXTREME'})
    run = next(r for r in stats.csv_rows(output / 'RunSummary.csv')[1] if r['DatasetID'] == 'LIVE_A')
    check('portfolio rejection counters summed once per symbol', run['PortfolioRiskRejects'] == '7')
    merged = stats.csv_rows(output / 'MTFAutoTrader_v244_TradeLog.csv')[1]
    check('64-bit IDs retained as exact decimal text', merged[0]['PositionIdentifier'] == '9007199254741001')
    before = (output / 'PatternStats.csv').read_bytes(); stats.build(source, output)
    check('repeated aggregation produces no double counting', (output / 'PatternStats.csv').read_bytes() == before)
    check('output has Excel UTF-8 BOM', before.startswith(b'\xef\xbb\xbf'))
    conflicting = dict(rows[0], NetProfit='199')
    stats.write_csv(source / 'conflict/x_position_0.csv', sorted(stats.REQUIRED), [conflicting])
    try:
        stats.build(source, output)
        check('conflicting closed revisions rejected', False)
    except ValueError:
        check('conflicting closed revisions rejected', True)
    check('input errors leave previous output intact', (output / 'PatternStats.csv').read_bytes() == before)
    stats.write_csv(source / 'conflict/x_position_0.csv', sorted(stats.REQUIRED), [dict(rows[0], NetProfit='nan')])
    try:
        stats.build(source, output)
        check('nonfinite financial values rejected', False)
    except ValueError:
        check('nonfinite financial values rejected', True)

result = {'passed': len(cases), 'failed': 0, 'scope': 'Offline Python CSV aggregation with independent numerical fixtures.',
          'cases': cases, 'tool_sha256': hashlib.sha256((ROOT / 'tools/build_pattern_stats.py').read_bytes()).hexdigest()}
(ROOT / 'verification/stats_results.json').write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps({'passed': len(cases), 'failed': 0}))

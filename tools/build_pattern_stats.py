#!/usr/bin/env python3
"""Merge v2.44 per-position CSV files and aggregate CLOSED positions, offline.

Python 3 standard library only. No terminal, broker or trading access.
Run against an MT3Logs_v244 directory copied from MT5 Common/Files.
"""
import argparse
import csv
import json
import math
from collections import defaultdict
from pathlib import Path


REQUIRED = {
    'SchemaVersion', 'DatasetID', 'RecordKey', 'Status', 'Account', 'Symbol',
    'MagicNumber', 'PositionIdentifier', 'PatternName', 'SLSource', 'ExitDateTime',
    'NetProfit', 'RealizedR', 'Result', 'FinalScore', 'MTFScore', 'PatternScore',
    'SpreadATRRatio',
}
METRICS = [
    'Trades', 'Wins', 'Losses', 'Breakevens', 'WinRate', 'NetProfit',
    'Expectancy', 'KnownRTrades', 'TotalR', 'AverageR', 'ProfitFactor',
    'AverageFinalScore', 'AverageMTFScore', 'AveragePatternScore',
    'AverageSpreadATR', 'MaxConsecutiveLosses',
]


def number(value):
    """Missing data stay unknown. Never turn absent entry context into zero."""
    if value in ('', None):
        return None
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f'non-finite CSV number: {value!r}')
    return result


def clean(value):
    if value is None:
        return ''
    if isinstance(value, float):
        return format(value, '.15g')
    return value


def csv_rows(path):
    with path.open(encoding='utf-8-sig', newline='') as stream:
        reader = csv.DictReader(stream)
        columns = reader.fieldnames
        rows = list(reader)
    if not columns or len(columns) != len(set(columns)):
        raise ValueError(f'{path}: missing/duplicate column names')
    if any(None in row or any(value is None for value in row.values()) for row in rows):
        raise ValueError(f'{path}: malformed CSV row')
    return columns, rows


def write_csv(path, columns, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + '.tmp')
    with temp.open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        writer.writerows({key: clean(row.get(key, '')) for key in columns} for row in rows)
    temp.replace(path)


def merge_positions(source):
    records = {}
    columns = None
    duplicates = 0
    paths = sorted(source.rglob('*_position_*.csv'))
    if not paths:
        raise ValueError(f'No *_position_*.csv files found in {source}')
    for path in paths:
        fields, rows = csv_rows(path)
        if not REQUIRED.issubset(fields) or len(rows) != 1:
            raise ValueError(f'{path}: expected one v2.44 position record')
        if columns is None:
            columns = fields
        elif columns != fields:
            raise ValueError(f'{path}: inconsistent schema/column order')
        row = rows[0]
        if (row['SchemaVersion'] != '244' or not row['RecordKey'] or
                not row['DatasetID'] or row['Status'] not in ('OPEN', 'CLOSED')):
            raise ValueError(f'{path}: invalid v2.44 record identity/status')
        if row['Status'] == 'CLOSED':
            if (not row['ExitDateTime'] or row['Result'] not in ('WIN', 'LOSS', 'BREAKEVEN') or
                    number(row['NetProfit']) is None):
                raise ValueError(f'{path}: incomplete closed position')
        for name in ['NetProfit', 'RealizedR', 'FinalScore', 'MTFScore', 'PatternScore', 'SpreadATRRatio']:
            number(row[name])
        key = row['RecordKey']
        if key in records:
            previous = records[key]
            duplicates += 1
            if previous == row:
                continue
            # A copied OPEN snapshot and its CLOSED successor can be reconciled.
            if {previous['Status'], row['Status']} == {'OPEN', 'CLOSED'}:
                identity = ['DatasetID', 'Account', 'Symbol', 'MagicNumber', 'PositionIdentifier']
                if any(previous[n] != row[n] for n in identity):
                    raise ValueError(f'{path}: conflicting record identity {key}')
                if row['Status'] == 'CLOSED':
                    records[key] = row
                continue
            # Different closed revisions (fees etc.) cannot be resolved using file mtime.
            raise ValueError(f'{path}: conflicting copies of {key}; keep the latest terminal export')
        records[key] = row
    return columns, sorted(records.values(), key=lambda row: (row['DatasetID'], row.get('DateTime', ''), row['RecordKey'])), duplicates


def mean(rows, field):
    values = [number(row[field]) for row in rows if row[field] != '']
    return sum(values) / len(values) if values else None


def metrics(rows):
    rows = sorted(rows, key=lambda row: (row['ExitDateTime'], row['RecordKey']))
    trades = len(rows)
    wins = sum(row['Result'] == 'WIN' for row in rows)
    losses = sum(row['Result'] == 'LOSS' for row in rows)
    profits = [number(row['NetProfit']) for row in rows]
    gains = sum(max(0, n) for n in profits)
    costs = sum(max(0, -n) for n in profits)
    rs = [number(row['RealizedR']) for row in rows if row['RealizedR'] != '']
    streak = maximum = 0
    for row in rows:
        streak = streak + 1 if row['Result'] == 'LOSS' else 0
        maximum = max(maximum, streak)
    return {
        'Trades': trades, 'Wins': wins, 'Losses': losses, 'Breakevens': trades - wins - losses,
        'WinRate': wins / trades * 100 if trades else None,
        'NetProfit': sum(profits), 'Expectancy': sum(profits) / trades if trades else None,
        'KnownRTrades': len(rs), 'TotalR': sum(rs) if rs else None,
        'AverageR': sum(rs) / len(rs) if rs else None,
        'ProfitFactor': gains / costs if costs else ('INF' if gains else ''),
        'AverageFinalScore': mean(rows, 'FinalScore'), 'AverageMTFScore': mean(rows, 'MTFScore'),
        'AveragePatternScore': mean(rows, 'PatternScore'), 'AverageSpreadATR': mean(rows, 'SpreadATRRatio'),
        'MaxConsecutiveLosses': maximum,
    }


def grouped(rows, keys):
    groups = defaultdict(list)
    for row in rows:
        if row['Status'] == 'CLOSED':
            groups[tuple(row[key] for key in keys)].append(row)
    return [dict(zip(keys, key), **metrics(values)) for key, values in sorted(groups.items())]


def rejection_rows(source):
    rows = {}
    for path in sorted(source.rglob('*_risk_rejects.csv')):
        fields, found = csv_rows(path)
        if fields != ['DatasetID', 'Symbol', 'PortfolioRiskRejects', 'CountingUnit'] or len(found) != 1:
            raise ValueError(f'{path}: invalid portfolio reject report')
        row = found[0]
        value = number(row['PortfolioRiskRejects'])
        if value is None or value < 0 or value != int(value) or row['CountingUnit'] != 'REJECTED_SYMBOL_M1_BARS':
            raise ValueError(f'{path}: invalid reject counter')
        key = (row['DatasetID'], row['Symbol'])
        if key not in rows or value > number(rows[key]['PortfolioRiskRejects']):
            rows[key] = row
    return [row for _, row in sorted(rows.items())]


def build(source, output):
    source, output = Path(source), Path(output)
    columns, rows, duplicates = merge_positions(source)
    rejects = rejection_rows(source)
    scope = ['DatasetID', 'Account', 'MagicNumber']
    pattern = grouped(rows, scope + ['PatternName'])
    sl = grouped(rows, scope + ['SLSource'])
    summary = grouped(rows, scope)
    for row in summary:
        counts = [int(number(r['PortfolioRiskRejects'])) for r in rejects if r['DatasetID'] == row['DatasetID']]
        row['PortfolioRiskRejects'] = sum(counts) if counts else ''
    # Resolve all input errors before writing any output.
    write_csv(output / 'MTFAutoTrader_v244_TradeLog.csv', columns, rows)
    write_csv(output / 'PatternStats.csv', scope + ['PatternName'] + METRICS, pattern)
    write_csv(output / 'SLSourceStats.csv', scope + ['SLSource'] + METRICS, sl)
    write_csv(output / 'RunSummary.csv', scope + METRICS + ['PortfolioRiskRejects'], summary)
    write_csv(output / 'PortfolioRejects.csv', ['DatasetID', 'Symbol', 'PortfolioRiskRejects', 'CountingUnit'], rejects)
    result = {
        'positions': len(rows), 'closed': sum(row['Status'] == 'CLOSED' for row in rows),
        'datasets': len({row['DatasetID'] for row in rows}), 'duplicate_copies_skipped': duplicates,
        'pattern_groups': len(pattern), 'sl_groups': len(sl),
        'notes': ['Datasets/accounts/magics are never pooled.', 'WinRate is a percent of all CLOSED positions, including breakevens.',
                  'PF and expectancy use net account-currency profit. Unknown R/scores are excluded from their averages.',
                  'Max drawdown requires the MT5 equity report; this tool does not infer it from closed positions.'],
    }
    temp = output / 'AggregationReport.json.tmp'
    temp.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temp.replace(output / 'AggregationReport.json')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path, help='Copied MT3Logs_v244 folder, LIVE folder, or TEST_<id> folder')
    parser.add_argument('--output', type=Path, required=True, help='Directory for combined CSVs and summary')
    args = parser.parse_args()
    try:
        print(json.dumps(build(args.source, args.output), ensure_ascii=False, indent=2))
    except (OSError, ValueError, csv.Error) as exc:
        parser.exit(1, f'Aggregation failed: {exc}\n')


if __name__ == '__main__':
    main()

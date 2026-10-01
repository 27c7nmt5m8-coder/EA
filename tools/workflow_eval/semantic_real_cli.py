"""Explicit separate command; exclusive files, no synthetic/real-task writes."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time

from . import semantic_real as real


def add_parser(sub):
    parser = sub.add_parser('semantic-real', help='Independent real-derived shadow classification')
    parser.add_argument('--cases', default='tests/fixtures/workflow_semantic_real_cases.json')
    parser.add_argument('--base-sha')
    parser.add_argument('--rows', help='Reaggregate existing metadata only, without provider calls')
    parser.add_argument('--live', action='store_true', help='Explicit Sol 6.1/high and Jev calls')


def exclusive_output(directory, name, value):
    directory.mkdir(exist_ok=True)
    target = directory / name
    if directory.is_symlink() or target.is_symlink(): raise ValueError('unsafe_output_path')
    with target.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write('\n')
    return target


def execute(args, root):
    if args.live and args.rows: raise ValueError('choose_live_or_rows')
    historical_rows = None
    if args.rows:
        historical_rows = json.loads(Path(args.rows).read_text(encoding='utf-8'))
        if not isinstance(historical_rows, list):
            raise ValueError('invalid_semantic_real_rows')
        row_bases = {row.get('base_sha') for row in historical_rows if isinstance(row, dict)}
        if len(row_bases) != 1:
            raise ValueError('mixed_or_missing_row_base')
        inferred_base = next(iter(row_bases))
    else:
        inferred_base = subprocess.check_output(
            ['git', 'rev-parse', 'origin/main'], cwd=real.ROOT, text=True, encoding='utf-8').strip()
    base = args.base_sha or inferred_base
    if not isinstance(base, str) or len(base) != 40 or any(c not in '0123456789abcdef' for c in base):
        raise ValueError('invalid_base_sha')
    if args.rows and args.base_sha and args.base_sha != inferred_base:
        raise ValueError('row_base_mismatch')

    # Source PR SHAs are historical provenance, not an ancestry requirement for
    # the integrated tool. Frozen manifest hashes remain the offline authority.
    cases, sha = real.load_cases(args.cases, root=real.ROOT, require_source_objects=False)
    prefix = 'semantic-real-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%f')
    directory = Path(root) / '.workflow-eval'
    live_available = bool(os.environ.get('TYPESAFE_API_KEY')) if args.live else None
    freeze = dict(experiment=real.COHORT, base_sha=base, dataset_sha256=sha,
                  provenance_sha256=hashlib.sha256(real.MANIFEST.read_bytes()).hexdigest(),
                  credential_present=live_available, live_requested=args.live,
                  sol_model=real.SOL_MODEL, sol_effort=real.SOL_EFFORT)
    if args.live:
        from .experimental_cli import _live_base, _live_fixture
        _live_fixture(args.cases)
        _live_fixture(real.MANIFEST)
        current_main = _live_base(base)
        head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=real.ROOT,
                                       text=True, encoding='utf-8').strip()
        freeze.update(execution_head=head, execution_main=current_main,
                      source_objects_verified=False,
                      source_provenance='frozen_manifest_with_case_fingerprints',
                      sol_identity_evidence='requested_CLI_flags_backend_identity_not_exposed')
    exclusive_output(directory, prefix+'-preflight.json', freeze)
    started = time.perf_counter()
    if args.rows:
        rows = historical_rows
    else:
        rows = []
        for case in cases:
            row = real.run_case(case, base_sha=base, dataset_sha256=sha,
                                sol_evaluator=real.call_sol if args.live and live_available else None,
                                jev_evaluator=real.call_jev if args.live and live_available else None)
            rows.append(row)
            exclusive_output(directory, prefix+'-'+case['id']+'.json', row)
            if args.live and live_available:
                print(case['id'] + ': Sol=' + row['a']['status'] + ', Jev=' + row['b']['status'], flush=True)
                unavailable = {'timeout', 'missing_credentials', 'nonzero_exit', 'network_unavailable', 'model_unavailable'}
                if any(row[arm]['reason'] in unavailable for arm in ('a', 'b')):
                    break
        exclusive_output(directory, prefix+'-rows.json', rows)
    report = real.summarize(rows, cases, base_sha=base, dataset_sha256=sha)
    report.update(live_executed=args.live and live_available is True,
                  measurement_wall_seconds=round(time.perf_counter()-started, 6) if not args.rows else None,
                  reaggregated_from_existing_rows=bool(args.rows))
    if args.live and not live_available:
        report.update(verdict='UNAVAILABLE', live_reason='missing_credentials')
    return exclusive_output(directory, prefix+'-report.json', report)


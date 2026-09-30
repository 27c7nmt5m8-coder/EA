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
    parser.add_argument('--base-sha', default='ca2f7da9d65cf68433fd7d791e6dafe16ea3c1f1')
    parser.add_argument('--rows', help='Reaggregate existing metadata only, without provider calls')
    parser.add_argument('--live', action='store_true', help='Explicit Sol 6.1/xhigh and Jev calls')


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
    manifest = json.loads(real.MANIFEST.read_text(encoding='utf-8'))
    if args.base_sha != manifest['source_heads']['18']:
        raise ValueError('wrong_stacked_dependency_base')
    cases, sha = real.load_cases(args.cases, root=real.ROOT, require_source_objects=args.live)
    prefix = 'semantic-real-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%f')
    directory = Path(root) / '.workflow-eval'
    live_available = bool(os.environ.get('TYPESAFE_API_KEY')) if args.live else None
    freeze = dict(experiment=real.COHORT, base_sha=args.base_sha, dataset_sha256=sha,
                  provenance_sha256=hashlib.sha256(real.MANIFEST.read_bytes()).hexdigest(),
                  credential_present=live_available, live_requested=args.live,
                  sol_model=real.SOL_MODEL, sol_effort=real.SOL_EFFORT)
    if args.live:
        from .experimental_cli import _live_fixture
        _live_fixture(args.cases)
        _live_fixture(real.MANIFEST)
        head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=real.ROOT, text=True).strip()
        ancestor = subprocess.run(['git', 'merge-base', '--is-ancestor', args.base_sha, head], cwd=real.ROOT)
        if ancestor.returncode: raise ValueError('not_stacked_on_dependency')
        freeze.update(execution_head=head, source_objects_verified=True,
                      sol_identity_evidence='requested_CLI_flags_backend_identity_not_exposed')
    exclusive_output(directory, prefix+'-preflight.json', freeze)
    started = time.perf_counter()
    if args.rows:
        rows = json.loads(Path(args.rows).read_text(encoding='utf-8'))
    else:
        rows = []
        for case in cases:
            row = real.run_case(case, base_sha=args.base_sha, dataset_sha256=sha,
                                sol_evaluator=real.call_sol if args.live and live_available else None,
                                jev_evaluator=real.call_jev if args.live and live_available else None)
            rows.append(row)
            # Save each safe observation as it completes; process interruption
            # cannot discard completed measurements. Reaggregation never reruns.
            exclusive_output(directory, prefix+'-'+case['id']+'.json', row)
            if args.live and live_available:
                print(case['id'] + ': Sol=' + row['a']['status'] + ', Jev=' + row['b']['status'], flush=True)
                unavailable = {'timeout', 'missing_credentials', 'nonzero_exit', 'network_unavailable', 'model_unavailable'}
                if any(row[arm]['reason'] in unavailable for arm in ('a', 'b')):
                    break  # No silent model/provider substitution or repeated outage calls.
        exclusive_output(directory, prefix+'-rows.json', rows)
    report = real.summarize(rows, cases, base_sha=args.base_sha, dataset_sha256=sha)
    report.update(live_executed=args.live and live_available is True,
                  measurement_wall_seconds=round(time.perf_counter()-started, 6) if not args.rows else None,
                  reaggregated_from_existing_rows=bool(args.rows))
    if args.live and not live_available:
        report.update(verdict='UNAVAILABLE', live_reason='missing_credentials')
    return exclusive_output(directory, prefix+'-report.json', report)

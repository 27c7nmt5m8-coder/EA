"""Explicit shadow commands; never write to the real-task cohort."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess


SHA = re.compile(r'[0-9a-f]{40}\Z')


def add_parsers(sub):
    from .jevgrep_benchmark import CURRENT_SOL_MODEL, HISTORICAL_SOL_MODEL
    trace = sub.add_parser('trace-benchmark')
    trace.add_argument('--cases', default='tests/fixtures/workflow_trace_cases.json')
    trace.add_argument('--base-sha')
    trace.add_argument('--observations', help='Local metadata observations keyed by task_id')
    trace.add_argument('--live', action='store_true', help='Explicit Sol and Jev calls on safe synthetic fixtures')

    semantic = sub.add_parser('semantic-regression')
    semantic.add_argument('--cases', default='tests/fixtures/workflow_semantic_regression_cases.json')
    semantic.add_argument('--base-sha')
    semantic.add_argument('--live', action='store_true', help='Explicit Sol and Jev calls on safe synthetic fixtures')

    grep = sub.add_parser('jevgrep-benchmark')
    grep.add_argument('--cases', default='tests/fixtures/workflow_jevgrep_cases.json')
    grep.add_argument('--base-sha')
    grep.add_argument('--sol-model', choices=(CURRENT_SOL_MODEL, HISTORICAL_SOL_MODEL),
                      default=CURRENT_SOL_MODEL,
                      help='Current model by default; legacy model is for offline historical observations only')
    grep.add_argument('--a-observations', help='Local A-arm metadata keyed by case id')
    grep.add_argument('--b-observations', help='Local B-arm metadata keyed by case id')
    grep.add_argument('--discovery-rows', help='Earlier live retrieval rows bound to B Sol observations')
    grep.add_argument('--source-allowlist', help='JSON array of explicitly approved source paths')
    grep.add_argument('--jg-executable', default='jg')
    grep.add_argument('--live', action='store_true', help='Explicit Jevgrep discovery; no install')

    report = sub.add_parser('experimental-report')
    report.add_argument('--trace-rows')
    report.add_argument('--trace-cases', default='tests/fixtures/workflow_trace_cases.json')
    report.add_argument('--semantic-rows')
    report.add_argument('--semantic-cases', default='tests/fixtures/workflow_semantic_regression_cases.json')
    report.add_argument('--jevgrep-rows')
    report.add_argument('--jevgrep-cases', default='tests/fixtures/workflow_jevgrep_cases.json')
    report.add_argument('--base-sha')


def _base(args, root, *, fixture_base=None):
    value = args.base_sha
    if value is None:
        value = fixture_base
    if value is None:
        repository_root = Path(__file__).resolve().parents[2]
        value = subprocess.check_output(['git', 'rev-parse', 'origin/main'], cwd=repository_root,
                                        text=True, encoding='utf-8').strip()
    if not isinstance(value, str) or not SHA.fullmatch(value):
        raise ValueError('invalid_base_sha')
    return value


def _fixture_base(cases):
    values = {case.get('base_sha') for case in cases if isinstance(case, dict)}
    if len(values) != 1:
        raise ValueError('mixed_or_missing_fixture_base')
    value = next(iter(values))
    if not isinstance(value, str) or not SHA.fullmatch(value):
        raise ValueError('invalid_fixture_base')
    return value


def _live_base(base):
    repository_root = Path(__file__).resolve().parents[2]
    current = subprocess.check_output(['git', 'rev-parse', 'origin/main'], cwd=repository_root,
                                      text=True, encoding='utf-8').strip()
    if subprocess.run(['git', 'merge-base', '--is-ancestor', base, current],
                      cwd=repository_root, capture_output=True).returncode:
        raise ValueError('stale_live_base_sha')
    head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=repository_root,
                                   text=True, encoding='utf-8').strip()
    if subprocess.run(['git', 'merge-base', '--is-ancestor', current, head],
                      cwd=repository_root, capture_output=True).returncode:
        raise ValueError('live_head_not_descendant_of_main')
    return current


def _live_fixture(path):
    repository_root = Path(__file__).resolve().parents[2]
    candidate = Path(path).resolve()
    fixture_root = (repository_root / 'tests' / 'fixtures').resolve()
    if not candidate.is_relative_to(fixture_root):
        raise ValueError('live_fixture_outside_reviewed_fixtures')
    relative = candidate.relative_to(repository_root).as_posix()
    tracked = subprocess.run(['git', 'ls-files', '--error-unmatch', '--', relative],
                             cwd=repository_root, capture_output=True)
    clean = subprocess.run(['git', 'diff', '--quiet', 'HEAD', '--', relative],
                           cwd=repository_root, capture_output=True)
    if tracked.returncode or clean.returncode:
        raise ValueError('live_fixture_untracked_or_changed')


def _run_name(prefix):
    return prefix + '-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%f')


def _observations(path):
    if path is None:
        return {}
    value = json.loads(Path(path).read_text(encoding='utf-8'))
    if not isinstance(value, dict) or any(not isinstance(k, str) or not isinstance(v, dict)
                                          for k, v in value.items()):
        raise ValueError('invalid_observations')
    return value


def merge_discovery(discovery, sol, discovery_rows_sha256, identity):
    """Bind later Sol measurements to one exact prior Jevgrep discovery file."""
    from .jevgrep_benchmark import METRICS
    retrieval_metrics = {'source_bytes', 'context_bytes', 'jevgrep_tokens',
                         'elapsed_seconds', 'source_universe_coverage'}
    if discovery.get('status') in ('UNAVAILABLE', 'FAIL'):
        return dict(identity, status=discovery['status'], reason=discovery.get('reason'),
                    found_files=[])
    allowed = set(identity) | {'discovery_rows_sha256', 'sol_status', 'task_success',
                               'sol_elapsed_seconds', 'cost_provenance'} | (
                                   set(METRICS) - retrieval_metrics)
    sol_status = 'UNAVAILABLE' if sol is None else sol.get('sol_status')
    if sol is None:
        sol = dict(identity, discovery_rows_sha256=discovery_rows_sha256,
                   sol_status='UNAVAILABLE')
    if (not isinstance(sol, dict) or set(sol) - allowed or
            any(sol.get(key) != value for key, value in identity.items()) or
            sol.get('discovery_rows_sha256') != discovery_rows_sha256 or
            sol.get('sol_status') not in ('OK', 'FAIL', 'UNAVAILABLE') or discovery.get('status') != 'OK'):
        raise ValueError('invalid_discovery_sol_binding')
    metrics = discovery.get('metrics')
    if not isinstance(metrics, dict):
        raise ValueError('invalid_discovery_metrics')
    prior_time = metrics.get('elapsed_seconds', {}).get('value')
    sol_time = sol.get('sol_elapsed_seconds')
    elapsed = prior_time + sol_time if type(prior_time) in (int, float) and type(sol_time) in (int, float) else None
    result = dict(identity, status='OK', sol_status=sol_status,
                  reason=discovery.get('reason'),
                  found_files=discovery.get('found_files'),
                  cache_bypassed=discovery.get('cache_bypassed'),
                  source_sha256=discovery.get('source_sha256'),
                  stage_file_count=discovery.get('stage_file_count'),
                  jg_version=discovery.get('jg_version'),
                  source_bytes=metrics.get('source_bytes'),
                  context_bytes=metrics.get('context_bytes'),
                  jevgrep_tokens=metrics.get('jevgrep_tokens'),
                  source_universe_coverage=metrics.get('source_universe_coverage'),
                  elapsed_seconds=elapsed if elapsed is not None else
                      dict(value=None, reason='not_reported', coverage=0),
                  task_success=sol.get('task_success') if sol_status == 'OK' else None)
    for key in set(METRICS) - retrieval_metrics:
        if key in sol and sol_status == 'OK':
            result[key] = sol[key]
    if 'cost_provenance' in sol and sol_status == 'OK':
        result['cost_provenance'] = sol['cost_provenance']
    return result


def _trace(args, root, output):
    from .trace_eval import (case_fingerprint, run_trace_case, summarize_trace,
                             execute_trace_case, trace_sol_review, call_trace_jev)
    raw_dataset = Path(args.cases).read_bytes()
    dataset_sha = hashlib.sha256(raw_dataset).hexdigest()
    dataset = json.loads(raw_dataset)
    if not isinstance(dataset, dict) or dataset.get('schema_version') != 1 or not isinstance(dataset.get('cases'), list):
        raise ValueError('invalid_trace_dataset')
    cases = dataset['cases']
    base = _base(args, root, fixture_base=_fixture_base(cases))
    if args.live:
        _live_base(base)
        _live_fixture(args.cases)
    identities = [c.get('task_id') for c in cases]
    if not cases or len(set(identities)) != len(identities):
        raise ValueError('duplicate_or_empty_trace_dataset')
    for case in cases:
        case_fingerprint(case)
        if case['base_sha'] != base:
            raise ValueError('stale_trace_fixture')
    if args.live and args.observations:
        raise ValueError('choose_live_or_observations')
    supplied = _observations(args.observations)
    if set(supplied) - set(identities):
        raise ValueError('unknown_trace_observation')
    rows = []
    for case in cases:
        if args.live:
            row = execute_trace_case(case, trace_sol_review,
                                     lambda c: call_trace_jev(c, live=True),
                                     live=True, current_base_sha=base)
        else:
            observation = supplied.get(case['task_id'], {})
            row = run_trace_case(case, observation.get('a', {'status': 'NOT_RUN'}),
                                 observation.get('b', {'status': 'NOT_RUN'}),
                                 observation.get('jev', {'status': 'NOT_RUN'}))
        row['dataset_sha256'] = dataset_sha
        rows.append(row)
    name = _run_name('trace-eval')
    output(root, name + '-rows.json', rows)
    report = summarize_trace(rows, expected_task_ids=identities)
    report.update(base_sha=base, dataset_sha256=dataset_sha,
                  live_executed=args.live, real_task_cohort_included=False)
    return output(root, name + '-report.json', report)


def _semantic(args, root, output):
    from .semantic_regression import load_cases, run_cases, summarize
    base = _base(args, root)
    if args.live:
        _live_base(base)
        _live_fixture(args.cases)
    cases, dataset_sha = load_cases(args.cases)
    rows = run_cases(cases, base_sha=base, dataset_sha256=dataset_sha, live=args.live)
    name = _run_name('semantic-regression')
    output(root, name + '-rows.json', rows)
    report = summarize(rows, current_base_sha=base, dataset_sha256=dataset_sha,
                       expected_case_ids=[case['id'] for case in cases])
    report.update(live_executed=args.live, real_task_cohort_included=False)
    return output(root, name + '-report.json', report)


def _jevgrep(args, root, output):
    from .jevgrep_benchmark import (load_cases, run_discovery, evaluate_pair,
                                    summarize_pairs, source_fingerprint, CURRENT_SOL_MODEL)
    if args.live and args.sol_model != CURRENT_SOL_MODEL:
        raise ValueError('legacy_sol_model_not_live')
    repository_root = Path(__file__).resolve().parents[2]
    cases = load_cases(args.cases, repository_root)
    base = _base(args, root, fixture_base=_fixture_base(cases))
    if args.live:
        _live_base(base)
        _live_fixture(args.cases)
    dataset_sha = hashlib.sha256(Path(args.cases).read_bytes()).hexdigest()
    if args.live and (args.b_observations or args.discovery_rows):
        raise ValueError('choose_live_or_b_observations')
    a_observations = _observations(args.a_observations)
    b_observations = _observations(args.b_observations)
    discovery_rows = None
    discovery_digest = None
    if args.discovery_rows:
        if not args.b_observations:
            raise ValueError('discovery_requires_b_sol_observations')
        raw = Path(args.discovery_rows).read_bytes()
        discovery_digest = hashlib.sha256(raw).hexdigest()
        records = json.loads(raw)
        if not isinstance(records, list) or len({r.get('case_id') for r in records if isinstance(r, dict)}) != len(records):
            raise ValueError('invalid_discovery_rows')
        discovery_rows = {r['case_id']: r for r in records}
    if (set(a_observations) | set(b_observations)) - {c['id'] for c in cases}:
        raise ValueError('unknown_jevgrep_observation')
    source_paths = None
    if args.source_allowlist:
        source_paths = json.loads(Path(args.source_allowlist).read_text(encoding='utf-8'))
        if not isinstance(source_paths, list) or any(not isinstance(p, str) for p in source_paths):
            raise ValueError('invalid_source_allowlist')
    if args.discovery_rows and source_paths is None:
        raise ValueError('discovery_merge_requires_source_allowlist')
    rows = []
    for case in cases:
        if case['base_sha'] != base:
            raise ValueError('stale_jevgrep_fixture')
        identity = dict(task_id=case['id'], base_sha=base,
                        sol_model=args.sol_model, sol_effort='high' if args.sol_model == CURRENT_SOL_MODEL else 'xhigh')
        a = dict(identity, **a_observations.get(case['id'], {'status': 'UNAVAILABLE', 'reason': 'observation_unavailable', 'found_files': []}))
        if args.live:
            b = dict(identity, **run_discovery(case, repository_root, live=True,
                                               jg_executable=args.jg_executable,
                                               source_paths=source_paths))
        elif discovery_rows is not None:
            prior = discovery_rows.get(case['id'])
            if (not isinstance(prior, dict) or prior.get('base_sha') != trace_base or
                    prior.get('dataset_sha256') != dataset_sha or
                    prior.get('retrieval_only') is not True):
                raise ValueError('stale_or_missing_discovery')
            b = merge_discovery(prior['b'], b_observations.get(case['id']),
                                discovery_digest, identity)
        else:
            b = dict(identity, **b_observations.get(case['id'], {'status': 'UNAVAILABLE', 'reason': 'observation_unavailable', 'found_files': []}))
        expected_source = (source_fingerprint(repository_root, source_paths, base)
                           if b['status'] == 'OK' and source_paths is not None else None)
        row = evaluate_pair(case, a, b, current_base_sha=base,
                            expected_source_sha256=expected_source,
                            expected_source_paths=source_paths)
        row.update(dataset_sha256=dataset_sha, retrieval_only=args.live)
        rows.append(row)
    name = _run_name('jevgrep')
    output(root, name + '-rows.json', rows)
    report = summarize_pairs(rows, expected_case_ids=[case['id'] for case in cases])
    if args.live and not report['coverage_missing_data']['comparable_pairs']:
        unavailable_os = all(row['b']['status'] == 'UNAVAILABLE' and
                             row['b']['reason'] == 'unsupported_environment' for row in rows)
        if not report['critical_file_miss_cases']:
            report['pilot_status'] = 'UNAVAILABLE' if unavailable_os else 'RETRIEVAL_ONLY'
    report.update(base_sha=base, dataset_sha256=dataset_sha, live_executed=args.live,
                  real_task_cohort_included=False)
    return output(root, name + '-report.json', report)


def _report(args, root, output):
    from .trace_eval import summarize_trace
    from .semantic_regression import load_cases, summarize as summarize_semantic
    from .jevgrep_benchmark import summarize_pairs
    requested_base = args.base_sha
    if requested_base is not None and (not isinstance(requested_base, str) or not SHA.fullmatch(requested_base)):
        raise ValueError('invalid_base_sha')
    def read(path):
        if path is None:
            return None
        value = json.loads(Path(path).read_text(encoding='utf-8'))
        if not isinstance(value, list):
            raise ValueError('invalid_experimental_rows')
        return value
    trace_rows, semantic_rows, grep_rows = (read(args.trace_rows), read(args.semantic_rows),
                                            read(args.jevgrep_rows))
    def row_base(rows, label):
        if rows is None:
            return None
        values = {row.get('base_sha') for row in rows if isinstance(row, dict)}
        if len(values) != 1:
            raise ValueError('mixed_' + label + '_base')
        value = next(iter(values))
        if not isinstance(value, str) or not SHA.fullmatch(value):
            raise ValueError('invalid_' + label + '_base')
        if requested_base is not None and value != requested_base:
            raise ValueError('stale_' + label + '_rows')
        return value
    trace_base = row_base(trace_rows, 'trace')
    semantic_base = row_base(semantic_rows, 'semantic')
    grep_base = row_base(grep_rows, 'jevgrep')
    if trace_rows is not None:
        from .trace_eval import case_fingerprint
        trace_raw = Path(args.trace_cases).read_bytes()
        trace_fixture = json.loads(trace_raw)
        trace_dataset_sha = hashlib.sha256(trace_raw).hexdigest()
        expected_trace = {case['task_id']: case_fingerprint(case)
                          for case in trace_fixture['cases']}
        if len(expected_trace) != len(trace_fixture['cases']) or any(
                r.get('base_sha') != trace_base or
                r.get('dataset_sha256') != trace_dataset_sha or
                r.get('case_fingerprint') != expected_trace.get(r.get('task_id'))
                for r in trace_rows):
            raise ValueError('stale_trace_rows')
    if grep_rows is not None:
        grep_fixture = json.loads(Path(args.jevgrep_cases).read_text(encoding='utf-8'))
        expected_grep_ids = {case['id'] for case in grep_fixture['cases']}
        grep_dataset_sha = hashlib.sha256(Path(args.jevgrep_cases).read_bytes()).hexdigest()
        if len(expected_grep_ids) != len(grep_fixture['cases']) or any(
                r.get('base_sha') != grep_base or r.get('case_id') not in expected_grep_ids or
                r.get('dataset_sha256') != grep_dataset_sha for r in grep_rows):
            raise ValueError('stale_jevgrep_rows')
    trace = summarize_trace(trace_rows, expected_task_ids=list(expected_trace)) if trace_rows is not None else None
    semantic = None
    if semantic_rows is not None:
        semantic_cases, dataset_sha = load_cases(args.semantic_cases)
        semantic = summarize_semantic(semantic_rows, current_base_sha=semantic_base,
                                      dataset_sha256=dataset_sha,
                                      expected_case_ids=[case['id'] for case in semantic_cases])
    grep = summarize_pairs(grep_rows, expected_case_ids=list(expected_grep_ids)) if grep_rows is not None else None
    missing = dict(value=None, reason='experiment_rows_not_provided', coverage=0)
    trace_blocked = bool(trace and trace['decision'] == 'BLOCKED_CRITICAL_MISS')
    grep_blocked = bool(grep and (grep.get('critical_file_miss_cases') or
                                  grep.get('pilot_status') == 'BLOCKED_CRITICAL_FILE_MISS'))
    grep_unavailable_os = bool(grep_rows and all(
        r['b']['status'] == 'UNAVAILABLE' and r['b']['reason'] == 'unsupported_environment'
        for r in grep_rows))
    bases = dict(trace=trace_base, semantic=semantic_base, jevgrep=grep_base)
    provided_bases = {value for value in bases.values() if value is not None}
    shared_base = next(iter(provided_bases)) if len(provided_bases) == 1 else None
    report = dict(scope='shadow_experiments_only', base_sha=shared_base,
                  base_sha_by_experiment=bases,
                  pilot_status={'trace': 'BLOCKED_CRITICAL_MISS' if trace_blocked else 'UNMEASURED' if trace is None or not trace['comparable_pairs'] else trace['decision'],
                                'semantic': 'UNMEASURED' if semantic is None else semantic['verdict'],
                                'jevgrep': 'BLOCKED_CRITICAL_FILE_MISS' if grep_blocked else 'UNAVAILABLE' if grep_unavailable_os else
                                            'RETRIEVAL_ONLY' if grep_rows and any(r.get('retrieval_only') for r in grep_rows) else
                                            'UNMEASURED' if grep is None or not grep['coverage_missing_data']['comparable_pairs'] else
                                            grep.get('pilot_status', grep['adoption_status'])},
                  quality={'trace': trace.get('quality', missing) if trace else missing,
                           'semantic': semantic['quality'] if semantic else missing,
                           'jevgrep': grep.get('quality', missing) if grep else missing},
                  tokens={'trace': trace.get('token', missing) if trace else missing,
                          'semantic': semantic['tokens'] if semantic else missing,
                          'jevgrep': grep.get('token', missing) if grep else missing},
                  cost={'trace': trace.get('cost', missing) if trace else missing,
                        'semantic': semantic['cost'] if semantic else missing,
                        'jevgrep': grep.get('cost', missing) if grep else missing},
                  time={'trace': trace.get('elapsed_seconds', missing) if trace else missing,
                        'semantic': semantic['time'] if semantic else missing,
                        'jevgrep': grep.get('time', missing) if grep else missing},
                  context_retrieval={'trace': trace.get('context_retrieval', missing) if trace else missing,
                                     'semantic': semantic['context_retrieval'] if semantic else missing,
                                     'jevgrep': grep.get('context_retrieval', missing) if grep else missing},
                  rework_test_failure={'trace': trace.get('rework_test_failure', missing) if trace else missing,
                                       'semantic': semantic['rework_test_failure'] if semantic else missing,
                                       'jevgrep': grep.get('rework_test_failure', missing) if grep else missing},
                  coverage_missing_data={'trace': trace.get('coverage', missing) if trace else missing,
                                         'semantic': semantic['coverage'] if semantic else missing,
                                         'jevgrep': grep.get('coverage_missing_data', missing) if grep else missing},
                  limitations={'trace': trace.get('limitations', ['not_measured']) if trace else ['not_measured'],
                               'semantic': semantic['limitations'] if semantic else ['not_measured'],
                               'jevgrep': grep.get('limitations', ['not_measured']) if grep else ['not_measured']},
                  review_skip_enabled=False, real_task_cohort_included=False,
                  adoption_authorized=False)
    return output(root, 'experimental-summary.json', report)


def execute(args, root, output):
    if args.command == 'trace-benchmark':
        return _trace(args, root, output)
    if args.command == 'semantic-regression':
        return _semantic(args, root, output)
    if args.command == 'jevgrep-benchmark':
        return _jevgrep(args, root, output)
    if args.command == 'experimental-report':
        return _report(args, root, output)
    raise ValueError('unknown_experiment_command')

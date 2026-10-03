"""Run with python -m tools.workflow_eval.cli. Network calls require explicit flags."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sys

from .context import build_bundle, build_context_packet, expand_context_packet, is_current, digest
from .telemetry import capture, validate_event, summarize_events
from .triage import route, call_jev, mandatory_reasons, policy
from .report import summarize
from .experimental_cli import add_parsers as add_experimental_parsers, execute as execute_experiment


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def load_packet_evidence(path):
    def unique_fields(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('duplicate_json_field')
            result[key] = value
        return result

    def finite_only(value):
        raise ValueError('nonfinite_json_value')

    return json.loads(Path(path).read_text(encoding='utf-8'),
                      object_pairs_hook=unique_fields, parse_constant=finite_only)


def dataset_cases(dataset):
    return [dict(case, context_blocks=case['context_blocks']+dataset.get('common_context_blocks', []))
            for case in dataset['cases']]


def output_path(root, name):
    if not re.fullmatch(r'[A-Za-z0-9_.-]+', name):
        raise ValueError('invalid_output_name')
    directory = Path(root) / '.workflow-eval'
    if not directory.resolve().is_relative_to(Path(root).resolve()):
        raise ValueError('output_outside_repository')
    directory.mkdir(exist_ok=True)
    path = directory / name
    if not path.resolve().is_relative_to(Path(root).resolve()):
        raise ValueError('output_outside_repository')
    return path


def output(root, name, value):
    path = output_path(root, name)
    temporary = path.with_suffix(path.suffix + '.tmp')
    if not temporary.resolve().is_relative_to(Path(root).resolve()):
        raise ValueError('output_outside_repository')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)+'\n', encoding='utf-8')
    temporary.replace(path)
    return path


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('capture'); p.add_argument('session'); p.add_argument('--name', default='capture.json')
    p = sub.add_parser('event'); p.add_argument('event_file')
    p = sub.add_parser('events-report'); p.add_argument('events_file')
    p = sub.add_parser('bundle'); p.add_argument('--base', default='origin/main'); p.add_argument('--task-file', required=True); p.add_argument('--related', action='append', default=[])
    p = sub.add_parser('packet'); p.add_argument('bundle'); p.add_argument('--prior'); p.add_argument('--test-evidence'); p.add_argument('--expand', action='append', default=[])
    p.add_argument('--recipient-has-content', action='store_true', help='Emit handles only for an existing recipient retaining the exact prior full text; never for a fresh reviewer')
    p = sub.add_parser('spawn-request', help='Generate explicit tool arguments; does not spawn or enforce host policy')
    p.add_argument('bundle'); p.add_argument('--packet'); p.add_argument('--test-evidence')
    p.add_argument('--role', choices=['explorer', 'worker', 'researcher', 'reviewer'], required=True)
    p.add_argument('--task-name', required=True); p.add_argument('--spec-file', required=True)
    p.add_argument('--question', action='append', default=[])
    p.add_argument('--complex-work', action='store_true')
    p.add_argument('--fork-turns', default='none', help='String none, or role-bounded positive turn count; all is incompatible with overrides on this host')
    p = sub.add_parser('triage'); p.add_argument('bundle'); p.add_argument('--test-evidence'); p.add_argument('--live-jev', action='store_true')
    p = sub.add_parser('report'); p.add_argument('rows')
    p = sub.add_parser('decompose'); p.add_argument('rows')
    p = sub.add_parser('cohort-record'); p.add_argument('record'); p.add_argument('--update-audit', action='store_true')
    p = sub.add_parser('cohort-report')
    p = sub.add_parser('benchmark'); p.add_argument('--cases', default='tests/fixtures/workflow_eval_cases.json'); p.add_argument('--split', choices=['calibration', 'holdout'], required=True); p.add_argument('--live-jev', action='store_true'); p.add_argument('--workers', type=int, default=2)
    add_experimental_parsers(sub)
    from .semantic_real_cli import add_parser as add_real_parser
    add_real_parser(sub)
    args = parser.parse_args(argv)
    root = Path.cwd()
    rules = policy()
    if args.command == 'capture':
        path = output(root, args.name, capture(args.session))
    elif args.command == 'event':
        event = validate_event(load(args.event_file))
        event.setdefault('timestamp', datetime.now(timezone.utc).isoformat())
        path = output_path(root, 'events.jsonl')
        with path.open('a', encoding='utf-8') as f:
            f.write(json.dumps(event, allow_nan=False)+'\n')
    elif args.command == 'events-report':
        with Path(args.events_file).open(encoding='utf-8') as f:
            metrics = summarize_events(json.loads(line) for line in f if line.strip())
        path = output(root, 'events-report.json', metrics)
    elif args.command == 'bundle':
        task = Path(args.task_file).read_text(encoding='utf-8')
        path = output(root, 'bundle.json', build_bundle(root, args.base, args.related, task))
    elif args.command == 'packet':
        bundle = load_packet_evidence(args.bundle)
        prior = load_packet_evidence(args.prior) if args.prior else None
        verification = load_packet_evidence(args.test_evidence) if args.test_evidence else None
        packet = build_context_packet(bundle, prior=prior, verification=verification,
                                      root=root, recipient_has_content=args.recipient_has_content)
        if args.expand:
            packet = expand_context_packet(packet, bundle, args.expand, root=root)
        path = output(root, 'context-packet.json', packet)
    elif args.command == 'spawn-request':
        from .spawn import build_spawn_request
        bundle = load_packet_evidence(args.bundle)
        packet = load_packet_evidence(args.packet) if args.packet else None
        verification = load_packet_evidence(args.test_evidence) if args.test_evidence else None
        request = build_spawn_request(root, args.role, args.task_name, bundle,
                                      specification=Path(args.spec_file).read_text(encoding='utf-8'),
                                      repository_rules=(root / 'AGENTS.md').read_text(encoding='utf-8'),
                                      unresolved_questions=args.question, packet=packet,
                                      verification=verification, complex_work=args.complex_work,
                                      fork_turns=args.fork_turns)
        path = output(root, 'spawn-request.json', request)
    elif args.command == 'triage':
        bundle = load(args.bundle)
        test = load(args.test_evidence) if args.test_evidence else {}
        facts = dict(paths=bundle['changed_paths'], dependency=bundle['dependency'],
                     module_count=len(bundle['changed_paths']), tests=test.get('status', 'UNKNOWN'),
                     changed_lines=bundle.get('changed_lines'),
                     missing_context=bundle['expansion_required'], sensitive=False, scope_ok=True,
                     current=is_current(root, bundle) and test.get('fingerprint') == bundle['fingerprint'],
                     protected=bundle['protected'])
        jev = dict(status='NOT_RUN', answer=None, usage=None, attempts=0)
        if args.live_jev and not mandatory_reasons(facts) and rules['mode'] == 'shadow':
            evidence = bundle['patch'] + '\n' + '\n'.join(b['text'] for b in bundle['blocks'])
            jev = call_jev(dict(task=bundle['task'], evidence=evidence))
        path = output(root, 'triage.json', dict(facts=facts, jev=jev, routing=route(facts, jev.get('answer'))))
    elif args.command == 'report':
        path = output(root, 'report.json', summarize(load(args.rows)))
    elif args.command == 'decompose':
        from .analysis import decompose
        path = output(root, 'decomposition.json', decompose(load(args.rows)))
    elif args.command == 'cohort-record':
        from .real_tasks import validate_record, update_record, task_identity, summarize as real_summary
        row = validate_record(load(args.record))
        target = output_path(root, 'real-tasks.json')
        rows = load(target) if target.is_file() else []
        identity = task_identity(row)
        prior = next((r for r in rows if task_identity(r)==identity),None)
        if prior is not None:
            if not args.update_audit: raise ValueError('duplicate_real_task_use_explicit_audit_update')
            row=update_record(prior,row)
            output(root, 'prior-audit-'+digest(json.dumps(prior,sort_keys=True).encode())+'.json', prior)
            rows[rows.index(prior)]=row
        else:
            if args.update_audit: raise ValueError('audit_update_requires_existing_task')
            rows.append(row)
        real_summary(rows)
        path = output(root, 'real-tasks.json', rows)
    elif args.command == 'cohort-report':
        from .real_tasks import summarize as real_summary
        target = output_path(root, 'real-tasks.json')
        path = output(root, 'real-cohort-report.json', real_summary(load(target) if target.is_file() else []))
    elif args.command == 'semantic-real':
        from .semantic_real_cli import execute as execute_real
        path = execute_real(args, root)
    elif args.command in ('trace-benchmark', 'semantic-regression', 'jevgrep-benchmark', 'experimental-report'):
        path = execute_experiment(args, root, output)
    else:
        from .benchmark import run_cases
        dataset = load(args.cases)
        cases = [c for c in dataset_cases(dataset) if c['split'] == args.split]
        if len(cases) != (10 if args.split == 'calibration' else 20):
            raise ValueError('unexpected_split_size')
        run = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%f')
        target = output_path(root, args.split + '-' + run + '-rows.json')
        measured = run_cases(cases, target, args.live_jev, args.workers)
        metrics = summarize(measured['rows'])
        metrics.update(wall_seconds=measured['wall_seconds'], split=args.split,
                       dataset_sha256=digest(Path(args.cases).read_bytes()), policy=rules,
                       actual_review_skip_implemented=False, calibration_applied=False)
        path = output(root, args.split + '-' + run + '-report.json', metrics)
    print('Saved:', path)
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (ValueError, KeyError, OSError, TypeError):
        print('Evaluation failed: invalid, unavailable or unsafe evidence. No reviews skipped.', file=sys.stderr)
        sys.exit(1)

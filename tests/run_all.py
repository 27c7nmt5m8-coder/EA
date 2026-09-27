"""Five offline gates with fail-closed, exact-commit Windows CI delegation."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import urllib.request
from native_preflight import preflight

ROOT = Path(__file__).resolve().parents[1]
GATES = ['verify_v244.py', 'verify_json_regression.py', 'verify_stats.py', 'audit_source.py', 'verify_lock_scope.py']
CI_STEPS = ['Exact checkout', 'ABI and native deterministic gates', 'Upload native evidence']
REPORTS = ['cpp_diagnostics.txt', 'integration_results.json', 'json_results.json',
           'stats_results.json', 'source_audit.json', 'lock_fix_scope.json']


def combined_status(states, ci_pass):
    if len(states) != 5:
        return 'INCOMPLETE'
    if 'FAIL' in states:
        return 'FAIL'
    effective = [s == 'PASS' or (i < 2 and s in ('BLOCKED', 'DELEGATED_TO_CI') and ci_pass)
                 for i, s in enumerate(states)]
    return 'PASS' if all(effective) else 'INCOMPLETE'


def release_status(full, ci_pass, meta, scope, dirty):
    return 'PASS' if full == 'PASS' and ci_pass and meta == scope == 'PASS' and not dirty else 'INCOMPLETE'


def valid_ci(run, jobs, repo, branch, sha):
    identity = (run.get('repository', {}).get('full_name') == repo and run.get('head_sha') == sha
                and run.get('head_branch') == branch and run.get('path') == '.github/workflows/ci.yml'
                and run.get('event') in ('push', 'workflow_dispatch')
                and run.get('status') == 'completed' and run.get('conclusion') == 'success')
    native = [j for j in jobs if j.get('name') == 'native-windows']
    if not identity or len(native) != 1:
        return False
    job = native[0]
    steps = {s['name']: s.get('conclusion') for s in job.get('steps', [])}
    return (job.get('head_sha') == sha and job.get('status') == 'completed'
            and job.get('conclusion') == 'success' and all(steps.get(n) == 'success' for n in CI_STEPS))


def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT, text=True, encoding='utf-8').strip()


def input_fingerprint():
    paths = git('ls-files', '-z').split('\0') + git('ls-files', '--others', '--exclude-standard', '-z').split('\0')
    outputs = {'verification/' + name for name in REPORTS}
    return {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() if (ROOT / name).is_file() else None
            for name in paths if name and name not in outputs}


def github(path):
    headers = {'Accept': 'application/vnd.github+json', 'User-Agent': 'EA-validation'}
    token = os.environ.get('GH_TOKEN') or os.environ.get('GITHUB_TOKEN')
    if token:
        headers['Authorization'] = 'Bearer ' + token
    request = urllib.request.Request('https://api.github.com/' + path, headers=headers)
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def ci_evidence(run_id, repo, branch, sha):
    prefix = f'repos/{repo}/actions/runs/{run_id}'
    run = github(prefix)
    attempt = run['run_attempt']
    jobs = github(f'{prefix}/attempts/{attempt}/jobs?per_page=100')['jobs']
    artifacts = github(prefix + '/artifacts?per_page=100')['artifacts']
    name = f'native-windows-{sha}-{attempt}'
    artifact_ok = any(a['name'] == name and not a['expired']
                      and a.get('workflow_run', {}).get('head_sha') == sha for a in artifacts)
    passed = valid_ci(run, jobs, repo, branch, sha) and artifact_ok
    return {'status': 'PASS' if passed else 'UNKNOWN', 'run_id': run_id, 'attempt': attempt,
            'url': run.get('html_url'), 'commit': run.get('head_sha'), 'branch': run.get('head_branch'),
            'repository': repo, 'native_job': 'native-windows', 'artifact': name,
            'equivalence': 'EQUIVALENT' if passed else 'UNKNOWN'}


def execute_gate(index, out):
    env = dict(os.environ, PYTHONUTF8='1', PYTHONDONTWRITEBYTECODE='1')
    p = subprocess.run([sys.executable, '-X', 'utf8', str(ROOT / 'tests' / GATES[index])],
                       cwd=ROOT, env=env, text=True, encoding='utf-8', errors='replace', capture_output=True)
    text = p.stdout + p.stderr
    (out / (GATES[index] + '.log')).write_text(text, encoding='utf-8')
    status = 'PASS' if p.returncode == 0 else 'FAIL'
    if index < 2 and re.search(r'\[WinError (4551|577|1260)\]', text):
        status = 'BLOCKED'
    print(f'Gate {index+1} {GATES[index]}: {status}', flush=True)
    if status == 'FAIL':
        print(text[-2500:], flush=True)
    return status


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--native-only', action='store_true', help='CI gates 1 and 2; no full PASS')
    parser.add_argument('--ci-run', type=int, help='Exact-HEAD push/workflow_dispatch CI run')
    parser.add_argument('--metaeditor', help='MetaEditor64.exe; compile only')
    parser.add_argument('--mql-include', help='Installed MQL5 root containing Include/Trade/Trade.mqh')
    parser.add_argument('--base', default='origin/main', help='Product scope comparison base')
    args = parser.parse_args()
    out = ROOT / '.validation'
    out.mkdir(exist_ok=True)
    sha, branch = git('rev-parse', 'HEAD'), git('branch', '--show-current')
    match = re.fullmatch(r'(?:https://github.com/|git@github.com:)([\w.-]+/[\w.-]+?)(?:\.git)?', git('remote', 'get-url', 'origin'))
    repo = match[1] if match else None
    dirty = bool(git('status', '--porcelain'))
    inputs = input_fingerprint()
    result = {'repository': repo, 'branch': branch, 'commit': sha, 'dirty': dirty,
              'gates': ['NOT_RUN'] * 5, 'ci_native': {'status': 'NOT_RUN'},
              'metaeditor': {'status': 'NOT_RUN'}, 'full_gate': 'INCOMPLETE', 'authoritative_release': 'INCOMPLETE'}
    before = {name: (ROOT / 'verification' / name).read_bytes()
              if (ROOT / 'verification' / name).exists() else None for name in REPORTS}
    try:
        for name in REPORTS:
            (ROOT / 'verification' / name).unlink(missing_ok=True)
            (out / name).unlink(missing_ok=True)
        evidence = preflight()
        result['preflight'] = evidence
        blocked = evidence.get('status') == 'BLOCKED'
        if blocked:
            print('LOCAL_NATIVE = BLOCKED_BY_APPLICATION_CONTROL; use authoritative CI native gate', flush=True)
        for index in range(2 if args.native_only else 5):
            if index < 2 and blocked:
                result['gates'][index] = 'BLOCKED'
                print(f'Gate {index+1} {GATES[index]}: BLOCKED (Application Control / Code Integrity)', flush=True)
                continue
            result['gates'][index] = execute_gate(index, out)
            if index < 2 and result['gates'][index] == 'BLOCKED':
                blocked = True
        if args.native_only and result['gates'][:2] == ['PASS', 'PASS']:
            integration = json.loads((ROOT / 'verification/integration_results.json').read_text(encoding='utf-8'))
            strict_json = json.loads((ROOT / 'verification/json_results.json').read_text(encoding='utf-8'))
            assert integration['passed'] == 582 and integration['failed'] == 0
            assert len(strict_json['cases']) == 55 and all(c['passed'] for c in strict_json['cases'])
            assert integration['abi']['contract'] == 'mql64-v1'
            result['native_assertions'] = {'integration': 582, 'json': 55, 'abi': integration['abi']}
        if args.metaeditor:
            from metaeditor_compile import compile_sources
            result['metaeditor'] = compile_sources(args.metaeditor, args.mql_include, out, sha)
        result['product_scope'] = 'FAIL' if git('diff', args.base, '--', 'src', '*.set') else 'PASS'
        if args.ci_run and repo and not dirty:
            try:
                result['ci_native'] = ci_evidence(args.ci_run, repo, branch, sha)
            except (OSError, ValueError, KeyError):
                result['ci_native'] = {'status': 'UNKNOWN', 'reason': 'GitHub evidence unavailable or incomplete'}
        result['full_gate'] = combined_status(result['gates'], result['ci_native']['status'] == 'PASS')
        result['authoritative_release'] = release_status(result['full_gate'], result['ci_native']['status'] == 'PASS',
                                                        result['metaeditor']['status'], result['product_scope'], dirty)
        if sha != git('rev-parse', 'HEAD') or branch != git('branch', '--show-current') or inputs != input_fingerprint():
            result['authoritative_release'] = 'INCOMPLETE'
        print('Full offline gate:', result['full_gate'])
        print('Authoritative release gate:', result['authoritative_release'])
        if args.native_only:
            return 0 if result['gates'][:2] == ['PASS', 'PASS'] and 'native_assertions' in result else 1
        return 0 if result['authoritative_release' if args.ci_run else 'full_gate'] == 'PASS' else 1
    finally:
        for name, content in before.items():
            path = ROOT / 'verification' / name
            if path.exists():
                shutil.copyfile(path, out / name)
            if content is None:
                path.unlink(missing_ok=True)
            else:
                path.write_bytes(content)
        (out / 'gate_result.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    sys.exit(main())

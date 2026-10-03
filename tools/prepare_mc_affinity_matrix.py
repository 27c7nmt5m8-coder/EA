"""Compile and freeze the existing September matrix under a new Tester namespace."""
import argparse
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time

from tools.mc500k_batch import ROOT, PROFILE as TEMPLATE_PROFILE, PrivacyGuard, read_text
from tools.mc_isolated_contention import PROFILE, build, hidden_startup, profile_state, safe_error_code
from tools.mc_multisymbol_runner import prepare_matrix, verify_engine, sha256


def prepare(reference, working, evidence, namespace):
    reference, working, evidence = map(Path, (reference, working, evidence))
    case = json.loads(reference.read_text(encoding='utf-8'))[0]
    verify_engine(case)
    native = Path(case['set_path']).parents[2]
    if native.resolve() != (ROOT / 'MQL5').resolve() or working.exists() or evidence.exists():
        raise ValueError('new local diagnostic destinations and existing test root required')
    template, profile = native / 'Profiles/Charts' / TEMPLATE_PROFILE, native / 'Profiles/Charts' / PROFILE
    charts = list(template.glob('*.chr'))
    if len(charts) != 4 or any('<expert>' in read_text(p) for p in charts):
        raise ValueError('template profile is not EA-free')
    template_hashes = {p.name: sha256(p) for p in charts}
    if profile.exists():
        own_charts = list(profile.glob('*.chr'))
        if len(own_charts) != 4 or any('<expert>' in read_text(p) for p in own_charts):
            raise ValueError('dedicated test profile changed; no overwrite')
    else:
        shutil.copytree(template, profile)
    bundles, compiles = {}, []
    for mode in (0, 2):
        main = build(working / f'bundle{mode}', mode)
        log, binary, started = main.with_suffix('.mq5.log'), main.with_suffix('.ex5'), time.time()
        completed = subprocess.run(['C:/Program Files/HFM Metatrader 5/metaeditor64.exe',
                                    '/compile:' + str(main), '/inc:' + str(native), '/log:' + str(log)],
                                   timeout=180, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                   startupinfo=hidden_startup())
        text = log.read_text(encoding='utf-16') if log.exists() else ''
        counts = re.search(r'Result: (\d+) errors?, (\d+) warnings?', text)
        fresh = binary.is_file() and binary.stat().st_mtime >= started
        if not counts or counts.groups() != ('0', '0') or not fresh:
            raise ValueError('diagnostic native compilation failed; inspect local strict log')
        bundles[mode] = main.parent
        compiles.append(dict(mode=mode, errors=0, warnings=0, fresh_ex5=True,
                             cli_exit=completed.returncode, log_sha256=sha256(log), binary_sha256=sha256(binary)))
    rows = prepare_matrix(native / 'Profiles/Tester/CodexSpreadCompare_High_20260924.set',
                          read_text(Path(case['config'])), bundles, native, evidence / 'matrix',
                          case['original_set_sha256'], namespace, case['engine_sha256'])
    profile_hashes = profile_state(profile)
    for row in rows:
        row['profile_sha256'] = profile_hashes
    (evidence / 'matrix/manifest.json').write_text(json.dumps(rows,indent=2)+'\n',encoding='utf-8')
    metadata = dict(compiles=compiles, cases=len(rows), namespace=namespace, profile=PROFILE,
                    template_profile_hashes=template_hashes,dedicated_profile_hashes=profile_hashes,reference_sha256=sha256(reference),
                    profile_experts=0, affinity_changes=0, priority_changes=0, system_changes='NONE')
    PrivacyGuard().check(json.dumps(metadata))
    (evidence / 'compile_results.json').write_text(json.dumps(metadata, indent=2) + '\n', encoding='utf-8')
    return metadata


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reference', type=Path, required=True)
    parser.add_argument('--working', type=Path, required=True)
    parser.add_argument('--evidence', type=Path, required=True)
    parser.add_argument('--namespace', required=True)
    args = parser.parse_args()
    try:
        result = prepare(args.reference, args.working, args.evidence, args.namespace)
        print(json.dumps(dict(prepared=result['cases'], compiles=result['compiles'], profile=result['profile'])))
    except Exception as error:
        print(json.dumps(dict(status='BLOCKED',exception=type(error).__name__,reason=safe_error_code(error))))
        sys.exit(1)

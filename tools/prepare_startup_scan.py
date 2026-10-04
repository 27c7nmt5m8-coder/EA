"""Freeze only four-symbol NORMAL minimal/detailed startup diagnostic pairs."""
import argparse
import json
import re
import subprocess
import time
from pathlib import Path
from tools import mc500k_batch as batch
from tools import mc_multisymbol_runner as matrix
from tools.mc_isolated_contention import PROFILE, profile_state, hidden_startup
from tools.build_tester_journal_io import build as minimal_build
from tools.build_tester_startup_scan import build as detailed_build, SafeDiagnosticParser


def prepare(reference,working,evidence,namespace,variant):
    reference,working,evidence=map(Path,(reference,working,evidence))
    rows=json.loads(reference.read_text(encoding='utf-8'))
    case=next(r for r in rows if r['count']==4 and r['mode']==0 and r['load']=='NORMAL')
    matrix.verify_staged(case)
    if variant not in ('minimal','detailed') or working.exists() or evidence.exists():raise ValueError('new diagnostic destinations required')
    native=batch.ROOT/'MQL5';profile=profile_state(native/'Profiles/Charts'/PROFILE)
    if profile!=case['profile_sha256']:raise ValueError('dedicated profile changed')
    bundles={};compiles=[]
    for mode in (0,2):
        main=(minimal_build if variant=='minimal' else detailed_build)(working/f'bundle{mode}',mode)
        log=main.with_suffix('.mq5.log');binary=main.with_suffix('.ex5');started=time.time()
        result=subprocess.run(['C:/Program Files/HFM Metatrader 5/metaeditor64.exe','/compile:'+str(main),
                               '/inc:'+str(native),'/log:'+str(log)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
                              startupinfo=hidden_startup(),timeout=180)
        text=log.read_text(encoding='utf-16') if log.exists() else ''
        counts=re.search(r'Result: (\d+) errors?, (\d+) warnings?',text)
        if not counts or counts.groups()!=('0','0') or not binary.exists() or binary.stat().st_mtime<started:
            raise ValueError('native diagnostic compilation failed; inspect masked local compile log')
        bundles[mode]=main.parent
        compiles.append(dict(mode=mode,errors=0,warnings=0,cli_exit=result.returncode,
                             binary_sha256=matrix.sha256(binary),log_sha256=matrix.sha256(log)))
    manifest=matrix.prepare_matrix(native/'Profiles/Tester/CodexSpreadCompare_High_20260924.set',
        batch.read_text(Path(case['config'])),bundles,native,evidence/'matrix',case['original_set_sha256'],
        namespace,case['engine_sha256'],counts=(4,),loads=('NORMAL',))
    for row in manifest:row['profile_sha256']=profile;row['startup_variant']=variant
    batch.dump(evidence/'matrix/manifest.json',manifest)
    batch.dump(evidence/'compile_results.json',dict(variant=variant,compiles=compiles,cases=2,
        reference_sha256=matrix.sha256(reference),source_base_commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()))
    return manifest


if __name__=='__main__':
    p=SafeDiagnosticParser(description=__doc__)
    for n in ('reference','working','evidence'):p.add_argument('--'+n,type=Path,required=True)
    p.add_argument('--namespace',required=True);p.add_argument('--variant',choices=('minimal','detailed'),required=True)
    try:
        a=p.parse_args();prepare(a.reference,a.working,a.evidence,a.namespace,a.variant);print(json.dumps(dict(status='PREPARED',variant=a.variant,cases=2)))
    except Exception as e:print(json.dumps(dict(status='BLOCKED',exception=type(e).__name__)));raise SystemExit(1) from None

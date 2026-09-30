"""Explicit future-only recorder. No live calls in CI or normal tests.

python -m tools.workflow_eval.semantic_prospective_cli --help
Sol normal reviews are externally executed, with this recorder's blinded ticket.
Only safe typed metadata is imported; never raw review streams/source/credentials.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
from urllib import request, error

from . import semantic_prospective as p
from .semantic_prospective_report import report
from .semantic_real import ROOT
from .semantic_real_adapters import call_jev, safe_payload
from .triage import NoRedirect

DIRECTORY=ROOT/'.workflow-eval/semantic-prospective'
SPEC_FIELDS={'items','known_requirements','known_protected_areas','test_evidence','prior_review_known','kind'}


def github(path):
    req=request.Request('https://api.github.com/repos/'+p.REPO+'/'+path,
        headers={'Accept':'application/vnd.github+json','User-Agent':'EA-prospective-shadow'})
    try:
        with request.urlopen(req,timeout=30) as response: return json.load(response)
    except (error.HTTPError,error.URLError,TimeoutError,ValueError): raise ValueError('github_unavailable') from None


def git(*args):
    return subprocess.check_output(['git',*args],cwd=ROOT,stderr=subprocess.DEVNULL)


def pr_info(number,fetcher=github):
    if type(number) is not int or number<=0: raise ValueError('invalid_pr_number')
    info=fetcher('pulls/'+str(number))
    if info.get('number')!=number or info.get('base',{}).get('repo',{}).get('full_name')!=p.REPO:
        raise ValueError('wrong_repository_or_pr')
    for key in ('base','head'): p.hexvalue(info[key]['sha'],40)
    return info


def freeze(ledger,number,spec,*,fetcher=github,git_runner=git,clock=p.now):
    p.fields(spec,SPEC_FIELDS); p.safe(spec)
    emit=lambda kind,tid,data: ledger.append(kind,tid,data,clock())
    if not spec['items'] or not spec['known_requirements']:
        return emit('preflight',None,dict(pr_number=number,reason='NOT_ELIGIBLE_CONTRACT_UNCLEAR'))
    try: info=pr_info(number,fetcher)
    except ValueError as exc:
        if str(exc)=='github_unavailable': return emit('preflight',None,dict(pr_number=number,reason='GITHUB_UNAVAILABLE'))
        raise
    if number<=ledger.protocol['tooling_pr']:
        return emit('preflight',None,dict(pr_number=number,reason='NOT_ELIGIBLE_HISTORICAL'))
    if p.stamp(info['created_at'])<=p.stamp(ledger.protocol['activated_at']):
        return emit('preflight',None,dict(pr_number=number,reason='NOT_ELIGIBLE_NOT_FUTURE'))
    reviews=fetcher('pulls/'+str(number)+'/reviews?per_page=1')
    if reviews or spec['prior_review_known'] is not False:
        return emit('preflight',None,dict(pr_number=number,reason='NOT_ELIGIBLE_PRIOR_REVIEW'))
    if info['state']!='open' or info.get('merged_at') is not None: raise ValueError('not_open_future_pr')
    base,head=info['base']['sha'],info['head']['sha']
    for sha in (base,head):
        try: git_runner('cat-file','-e',sha+'^{commit}')
        except subprocess.CalledProcessError: git_runner('fetch','origin',sha)
    merge=git_runner('merge-base',base,head).decode().strip(); p.hexvalue(merge,40)
    raw=git_runner('diff','--no-ext-diff','--no-textconv','--binary',merge,head,'--')
    paths=git_runner('diff','--name-only','-z',merge,head,'--').decode('utf-8').strip('\0').split('\0')
    observed=clock()
    s=dict(schema_version=1,repository=p.REPO,pr_number=number,task_id=p.task_id(ledger.protocol,number),
        base_sha=base,head_sha=head,merge_base_sha=merge,diff_digest=hashlib.sha256(raw).hexdigest(),
        source_fingerprint=p.digest(dict(base_tree=git_runner('rev-parse',base+'^{tree}').decode().strip(),
            head_tree=git_runner('rev-parse',head+'^{tree}').decode().strip(),merge_base=merge)),changed_files=paths,
        created_at=info['created_at'],observed_at=observed,snapshot_at=clock(),github_reviews=0,**spec)
    try: p.validate_snapshot(ledger.protocol,s)
    except ValueError as exc:
        if str(exc)=='tooling_only_not_eligible':
            return emit('preflight',None,dict(pr_number=number,reason='NOT_ELIGIBLE_TOOLING'))
        raise
    # Race check: reject a changed head/base or newly published review rather
    # than freezing stale discovery as the current candidate.
    again=pr_info(number,fetcher)
    if again['head']['sha']!=head or again['base']['sha']!=base or fetcher('pulls/'+str(number)+'/reviews?per_page=1'):
        raise ValueError('head_or_review_changed_during_freeze')
    return emit('snapshot',s['task_id'],s)


def task(ledger,tid):
    tasks=p.replay(ledger.protocol,ledger.read())
    if tid not in tasks: raise ValueError('unknown_task_id')
    return tasks[tid]


def raw_tracking_opener():
    metadata={'digest':None}
    opener=request.build_opener(NoRedirect())
    class Tracked:
        def __init__(self,response): self.response=response
        def __enter__(self): self.response.__enter__(); return self
        def __exit__(self,*args): return self.response.__exit__(*args)
        def read(self,n):
            raw=self.response.read(n); metadata['digest']=hashlib.sha256(raw).hexdigest(); return raw
    def open_request(req,timeout): return Tracked(opener.open(req,timeout=timeout))
    return open_request,metadata


def live_jev(ledger,tid,*,evaluator=call_jev,fetcher=github):
    t=task(ledger,tid); s=t['snapshot']
    if t['ticket'] is not None: raise ValueError('jev_after_review')
    info=pr_info(s['pr_number'],fetcher)
    if info['head']['sha']!=s['head_sha'] or fetcher('pulls/'+str(s['pr_number'])+'/reviews?per_page=1'):
        raise ValueError('stale_head_or_prior_review')
    # Presence is used internally only. Missing credentials still yield an
    # unavailable attempt, never a fake response or implicit provider fallback.
    for item in s['items']:
        if any(a['item_id']==item['item_id'] and a['status']=='OK' for a in t['jev']): continue
        payload={k:item[k] for k in ('requirement','baseline','candidate','evidence')}; safe_payload(payload)
        if t['pending_jev']: raise ValueError('provider_request_pending_recovery')
        started=p.now(); identity=p.new_id()
        reserved=dict(attempt_id=identity,item_id=item['item_id'],started_at=started,
            snapshot_digest=p.digest(s),contract_digest=p.digest(s['items']),
            head_sha=s['head_sha'],diff_digest=s['diff_digest'],source_fingerprint=s['source_fingerprint'])
        ledger.append('jev_request',tid,reserved)
        opener,raw=raw_tracking_opener()
        value=evaluator(payload,opener=opener)
        a=p.normalize_jev(value)
        a.update(attempt_id=identity,item_id=item['item_id'],requested_model=ledger.protocol['jev_model'],
            requested_effort=None,effective_effort=None,effective_identity_reason=None,
            raw_result_digest=raw['digest'],raw_digest_reason=None if raw['digest'] else 'no_response_bytes',
            execution='live',findings=None,exposed_to_jev=None,started_at=started,completed_at=p.now(),
            snapshot_digest=p.digest(s),contract_digest=p.digest(s['items']),
            head_sha=s['head_sha'],diff_digest=s['diff_digest'],source_fingerprint=s['source_fingerprint'])
        ledger.append('jev',tid,a)
        # No result choice/confidence/routing is emitted into a reviewer packet.
        if a['status']!='OK': break


def reviewer_packet(t):
    s=t['snapshot']
    return dict(repository=s['repository'],pr_number=s['pr_number'],head_sha=s['head_sha'],base_sha=s['base_sha'],
        merge_base_sha=s['merge_base_sha'],diff_digest=s['diff_digest'],source_fingerprint=s['source_fingerprint'],
        snapshot_digest=p.digest(s),contract_digest=p.digest(s['items']),items=s['items'],
        known_requirements=s['known_requirements'],known_protected_areas=s['known_protected_areas'],
        changed_files=s['changed_files'],test_evidence=s['test_evidence'],model=p.MODEL,effort=p.EFFORT,
        instructions='Perform the normal complete review of the pinned Git source, not a bounded classification. '
        'Use a fresh independent context. Do not inspect .workflow-eval or semantic experiment outputs. '
        'Record per-item judgments/findings counts and actual execution usage/time separately. '
        'Do not use this packet alone as complete source evidence; retrieve needed pinned dependencies.')


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__); sub=parser.add_subparsers(dest='command',required=True)
    q=sub.add_parser('init'); q.add_argument('--tooling-pr',type=int,required=True); q.add_argument('--completion-sha',required=True)
    q=sub.add_parser('freeze'); q.add_argument('--pr',type=int,required=True); q.add_argument('--contract-file',required=True)
    q=sub.add_parser('jev'); q.add_argument('task_id'); q.add_argument('--live',action='store_true',required=True)
    q=sub.add_parser('review-start'); q.add_argument('task_id'); q.add_argument('--blinded',action='store_true')
    q.add_argument('--no-prior-external-review',action='store_true',required=True)
    for name in ('sol-record','truth','revision','rework'):
        q=sub.add_parser(name); q.add_argument('task_id'); q.add_argument('metadata_file')
    sub.add_parser('report'); sub.add_parser('stop')
    args=parser.parse_args(argv)
    if not DIRECTORY.resolve().is_relative_to(ROOT.resolve()): raise ValueError('unsafe_cohort_directory')
    if subprocess.run(['git','check-ignore','-q',str(DIRECTORY/'protocol.json')],cwd=ROOT).returncode:
        raise ValueError('cohort_must_be_gitignored')
    if args.command=='init':
        info=pr_info(args.tooling_pr)
        if info['head']['sha']!=args.completion_sha: raise ValueError('wrong_tooling_completion_head')
        p.hexvalue(args.completion_sha,40)
        p.Ledger(DIRECTORY,p.make_protocol(p.now(),args.tooling_pr,args.completion_sha)); print('Initialized empty future-only shadow cohort.'); return
    ledger=p.Ledger(DIRECTORY)
    if args.command=='freeze':
        e=freeze(ledger,args.pr,json.loads(Path(args.contract_file).read_text(encoding='utf-8')))
        print(json.dumps(dict(kind=e['kind'],task_id=e['task_id'],receipt=e['event_digest'])))
    elif args.command=='jev': live_jev(ledger,args.task_id); print('Jev attempt metadata sealed; normal Sol xHigh review remains required.')
    elif args.command=='review-start':
        t=task(ledger,args.task_id); s=t['snapshot']; info=pr_info(s['pr_number'])
        if info['head']['sha']!=s['head_sha'] or github('pulls/'+str(s['pr_number'])+'/reviews?per_page=1'):
            raise ValueError('stale_head_or_prior_review')
        ledger.append('review_start',args.task_id,dict(model=p.MODEL,effort=p.EFFORT,blinded=args.blinded,
            snapshot_digest=p.digest(s),contract_digest=p.digest(s['items'])))
        print(json.dumps(reviewer_packet(t),ensure_ascii=False,indent=2))
    elif args.command in ('sol-record','truth','revision','rework'):
        data=json.loads(Path(args.metadata_file).read_text(encoding='utf-8')); p.safe(data)
        e=ledger.append('sol' if args.command=='sol-record' else args.command,args.task_id,data)
        print(json.dumps(dict(kind=e['kind'],receipt=e['event_digest'])))
    elif args.command=='stop': ledger.append('close',None,dict(reason='collection_stopped')); print('Collection stopped.')
    else: print(json.dumps(report(ledger.protocol,ledger.read()),ensure_ascii=False,indent=2,allow_nan=False))


if __name__=='__main__': main()

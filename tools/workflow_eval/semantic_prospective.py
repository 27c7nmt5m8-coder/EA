"""Immutable, isolated prospective protocol and append-only safe event ledger."""
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import re
import uuid

from .semantic_real import fingerprint as digest, LEAKAGE
from .semantic_regression import CHOICES, valid_answer
from .telemetry import usage_numbers
from .triage import SENSITIVE, PROTECTED, policy

REPO = '27c7nmt5m8-coder/EA'
MODEL, EFFORT = 'gpt-6.1-sol', 'xhigh'
AREAS = {'entry','sl_tp','be','trailing','risk','monte_carlo','fintokei','portfolio',
         'worker_failure','orders','ownership','mutex','persistent_state','model_routing','safety_policy'}
ORIGINS = {'user_requirement','task_spec','project_rules','changed_behavior','test_intent','protected_behavior'}
KINDS = {'test','compiler','ci','source','specification','review','accepted_finding','fixed_finding'}


def new_id(): return uuid.uuid4().hex
def now(): return datetime.now(timezone.utc).isoformat()
def fields(value, expected):
    if not isinstance(value, dict) or set(value) != set(expected): raise ValueError('invalid_schema_fields')
def stamp(value):
    try:
        result=datetime.fromisoformat(value)
        if result.tzinfo is None: raise ValueError()
        return result
    except (TypeError, ValueError): raise ValueError('invalid_timestamp') from None
def hexvalue(value,n):
    if not isinstance(value,str) or not re.fullmatch('[0-9a-f]{'+str(n)+'}',value): raise ValueError('invalid_digest_or_identity')
def number(value, integer=False):
    if type(value) not in ((int,) if integer else (int,float)) or not math.isfinite(value) or value<0:
        raise ValueError('invalid_nonnegative_number')
def safe(value):
    if SENSITIVE.search(json.dumps(value,ensure_ascii=False,allow_nan=False)): raise ValueError('sensitive_metadata')
def text(value):
    if (not isinstance(value,str) or not 1<=len(value)<=3000 or LEAKAGE.search(value) or
        re.search(r'(?i)(review findings|reviewer severity|expected final verdict|merge outcome|fix outcome|Sol (?:said|found))',value)):
        raise ValueError('unsafe_or_leaking_contract')
    safe(value)
    if re.search(r'[A-Za-z0-9+/=_-]{80,}',value): raise ValueError('opaque_contract')


def make_protocol(activated_at,tooling_pr,completion_sha):
    result=dict(schema_version=1,cohort='semantic_prospective_v1',cohort_id=new_id(),repository=REPO,
        activated_at=activated_at,tooling_pr=tooling_pr,completion_sha=completion_sha,
        confidence_threshold=.90,review_skip_enabled=False,sol_model=MODEL,sol_effort=EFFORT,
        jev_model=policy()['jev_model'],checkpoint=10,primary_goal=20,shadow_only=True)
    validate_protocol(result); return result


def validate_protocol(value):
    fields(value,{'schema_version','cohort','cohort_id','repository','activated_at','tooling_pr','completion_sha',
        'confidence_threshold','review_skip_enabled','sol_model','sol_effort','jev_model','checkpoint','primary_goal','shadow_only'})
    if (value['schema_version']!=1 or value['cohort']!='semantic_prospective_v1' or value['repository']!=REPO or
        value['confidence_threshold']!=.90 or value['review_skip_enabled'] is not False or
        value['sol_model']!=MODEL or value['sol_effort']!=EFFORT or value['jev_model']!=policy()['jev_model'] or
        value['checkpoint']!=10 or value['primary_goal']!=20 or value['shadow_only'] is not True or
        type(value['tooling_pr']) is not int or value['tooling_pr']<=20 or
        policy()['confidence_threshold']!=.90 or policy()['review_skip_enabled'] is not False):
        raise ValueError('unsafe_or_changed_protocol')
    stamp(value['activated_at']); hexvalue(value['cohort_id'],32); hexvalue(value['completion_sha'],40)


def task_id(protocol,pr): return 'semantic-prospective:'+protocol['cohort_id']+':EA#'+str(pr)


def validate_snapshot(protocol,s):
    fields(s,{'schema_version','repository','pr_number','task_id','base_sha','head_sha','merge_base_sha',
        'diff_digest','source_fingerprint','changed_files','items','known_requirements','known_protected_areas',
        'test_evidence','created_at','observed_at','snapshot_at','prior_review_known','github_reviews','kind'})
    if (s['schema_version']!=1 or s['repository']!=REPO or type(s['pr_number']) is not int or
        s['pr_number']<=protocol['tooling_pr'] or s['task_id']!=task_id(protocol,s['pr_number']) or
        s['kind']!='ea_development' or s['prior_review_known'] is not False or
        type(s['github_reviews']) is not int or s['github_reviews']!=0):
        raise ValueError('retrospective_tooling_or_prior_review')
    if not stamp(protocol['activated_at']) < stamp(s['created_at']) <= stamp(s['observed_at']) <= stamp(s['snapshot_at']):
        raise ValueError('not_future_or_invalid_freeze_order')
    for key in ('base_sha','head_sha','merge_base_sha'): hexvalue(s[key],40)
    for key in ('diff_digest','source_fingerprint'): hexvalue(s[key],64)
    paths=s['changed_files']
    if (not isinstance(paths,list) or not paths or len(set(paths))!=len(paths) or
        any(not isinstance(x,str) or not re.fullmatch(r'[A-Za-z0-9_./-]{1,250}',x) or '..' in Path(x).parts or
            Path(x).is_absolute() or x.startswith('/') for x in paths)):
        raise ValueError('unsafe_changed_paths')
    product=any(x.startswith('src/') or (x.startswith('tests/') and x.endswith('.cpp'))
                or x in ('README_JA.md','VALIDATION_JA.md') for x in paths)
    if not product: raise ValueError('tooling_only_not_eligible')
    if not isinstance(s['known_requirements'],list) or not s['known_requirements']: raise ValueError('contract_unclear')
    for value in s['known_requirements']: text(value)
    if not isinstance(s['known_protected_areas'],list) or set(s['known_protected_areas'])-AREAS:
        raise ValueError('invalid_protected_areas')
    if not isinstance(s['items'],list) or not s['items']: raise ValueError('contract_unclear')
    ids=set()
    for item in s['items']:
        fields(item,{'item_id','requirement','baseline','candidate','evidence','origins','dependency','protected_areas','critical_dependency'})
        if not isinstance(item['item_id'],str) or not re.fullmatch(r'I[0-9]{1,4}',item['item_id']) or item['item_id'] in ids:
            raise ValueError('duplicate_or_invalid_semantic_item')
        ids.add(item['item_id'])
        for key in ('requirement','baseline','candidate','evidence'): text(item[key])
        if (not isinstance(item['origins'],list) or not item['origins'] or set(item['origins'])-ORIGINS or
            item['dependency'] not in ('known','unknown') or type(item['critical_dependency']) is not bool or
            not isinstance(item['protected_areas'],list) or set(item['protected_areas'])-AREAS):
            raise ValueError('invalid_contract_metadata')
    if not isinstance(s['test_evidence'],list): raise ValueError('invalid_test_evidence')
    for e in s['test_evidence']:
        fields(e,{'kind','digest','status'}); hexvalue(e['digest'],64)
        if e['kind'] not in KINDS or e['status'] not in ('PASS','FAIL','BLOCKED','UNKNOWN','UNAVAILABLE'):
            raise ValueError('invalid_test_evidence')
    safe(s)


def mandatory(s,item):
    return (bool(s['known_protected_areas'] or item['protected_areas'] or item['critical_dependency']) or
            item['dependency']=='unknown' or any(x.startswith('src/') or PROTECTED.search(x) or
            x in ('AGENTS.md','tools/workflow_eval/policy.json') or x.startswith('.agents/') for x in s['changed_files']) or
            bool(PROTECTED.search(' '.join(s['known_requirements']+[item[k] for k in ('requirement','baseline','candidate','evidence')]))))


def route(s,item,attempt):
    if mandatory(s,item): return 'MANDATORY_XHIGH'
    if attempt is None or attempt['status']!='OK': return 'PROVIDER_ESCALATE'
    if attempt['choice']=='unknown': return 'UNKNOWN_ESCALATE'
    if attempt['confidence']<.90: return 'LOW_CONF_ESCALATE'
    return 'SHADOW_HIGH_CONF'


ATTEMPT_FIELDS={'attempt_id','item_id','status','reason','choice','confidence','probabilities','usage','usage_reason',
    'elapsed_seconds','requested_model','requested_effort','effective_model','effective_effort','effective_identity_reason',
    'raw_result_digest','raw_digest_reason','execution','findings','exposed_to_jev','started_at','completed_at',
    'snapshot_digest','contract_digest','head_sha','diff_digest','source_fingerprint'}


def validate_attempt(a,provider,s,event_at):
    fields(a,ATTEMPT_FIELDS); hexvalue(a['attempt_id'],32)
    if a['snapshot_digest']!=digest(s) or a['contract_digest']!=digest(s['items']): raise ValueError('stale_head_diff_or_contract')
    if any(a[k]!=s[k] for k in ('head_sha','diff_digest','source_fingerprint')): raise ValueError('wrong_reviewed_head_or_source')
    if not stamp(s['snapshot_at']) <= stamp(a['started_at']) <= stamp(a['completed_at']) <= stamp(event_at):
        raise ValueError('invalid_attempt_order')
    if a['execution'] not in ('live','offline_fixture'): raise ValueError('invalid_execution_provenance')
    if a['status'] not in ('OK','UNAVAILABLE'): raise ValueError('invalid_provider_status')
    if a['reason'] not in (None,'timeout','nonzero_exit','missing_credentials','network_unavailable','invalid_response','model_effort_mismatch'):
        raise ValueError('invalid_provider_reason')
    if a['status']=='OK' and a['reason'] is not None or a['status']=='UNAVAILABLE' and a['reason'] is None:
        raise ValueError('inconsistent_provider_status')
    if a['usage'] is not None and usage_numbers(a['usage'])!=a['usage']: raise ValueError('unsafe_usage')
    if a['usage_reason']!=('missing_usage' if a['usage'] is None else None): raise ValueError('unsafe_missing_reason')
    if a['elapsed_seconds'] is not None: number(a['elapsed_seconds'])
    if a['raw_result_digest'] is not None: hexvalue(a['raw_result_digest'],64)
    if a['raw_digest_reason'] != ('no_response_bytes' if a['raw_result_digest'] is None else None): raise ValueError('invalid_result_digest_reason')
    if a['effective_model'] is not None and not re.fullmatch(r'[a-zA-Z0-9_.-]{1,60}',a['effective_model']): raise ValueError('invalid_effective_model')
    if a['effective_effort'] not in (None,'none','minimal','low','medium','high','xhigh','max','ultra'): raise ValueError('invalid_effective_effort')
    if a['effective_identity_reason'] not in (None,'backend_not_exposed','model_effort_mismatch'): raise ValueError('invalid_backend_reason')
    if provider=='jev':
        if (a['item_id'] not in {i['item_id'] for i in s['items']} or a['requested_model']!=policy()['jev_model'] or
            a['requested_effort'] is not None or a['findings'] is not None or a['exposed_to_jev'] is not None):
            raise ValueError('invalid_jev_identity')
        answer=dict(type='choice',choice=a['choice'],confidence=a['confidence'],probabilities=a['probabilities'])
        if a['status']=='OK' and (not valid_answer(answer) or a['effective_model']!=policy()['jev_model']): raise ValueError('invalid_jev_answer')
        if a['status']!='OK' and any(a[k] is not None for k in ('choice','confidence','probabilities')): raise ValueError('failed_jev_has_choice')
    else:
        if (a['item_id'] is not None or a['requested_model']!=MODEL or a['requested_effort']!=EFFORT or
            any(a[k] is not None for k in ('choice','confidence','probabilities')) or type(a['exposed_to_jev']) is not bool):
            raise ValueError('invalid_sol_identity')
        if ((a['effective_model'] is not None and a['effective_model']!=MODEL) or
            (a['effective_effort'] is not None and a['effective_effort']!=EFFORT) or
            a['effective_identity_reason']=='model_effort_mismatch'):
            if a['status']!='UNAVAILABLE' or a['reason']!='model_effort_mismatch': raise ValueError('invalid_effective_floor')
        if a['status']=='OK':
            if not isinstance(a['findings'],list) or len(a['findings'])!=len(s['items']): raise ValueError('incomplete_sol_findings')
            ids=set()
            for finding in a['findings']:
                fields(finding,{'item_id','choice','counts'})
                if finding['item_id'] in ids or finding['item_id'] not in {i['item_id'] for i in s['items']} or finding['choice'] not in CHOICES:
                    raise ValueError('invalid_sol_item')
                ids.add(finding['item_id']); fields(finding['counts'],{'critical','important','minor'})
                for value in finding['counts'].values(): number(value,True)
        elif a['findings'] is not None: raise ValueError('failed_sol_has_findings')
    safe(a)


def normalize_jev(value):
    """Allowlisted metadata only, known usage survives any answer failure."""
    result=dict(status='UNAVAILABLE',reason='invalid_response',choice=None,confidence=None,probabilities=None,
        usage=None,usage_reason='missing_usage',elapsed_seconds=None,effective_model=None)
    if not isinstance(value,dict): return result
    try: result.update(usage=usage_numbers(value.get('usage')),usage_reason=None)
    except (TypeError,ValueError): pass
    duration=value.get('elapsed_seconds')
    if type(duration) in (int,float) and math.isfinite(duration) and duration>=0: result['elapsed_seconds']=duration
    model=value.get('model')
    if isinstance(model,str) and re.fullmatch(r'[A-Za-z0-9_.-]{1,60}',model): result['effective_model']=model
    if value.get('status')!='OK':
        if value.get('reason') in ('timeout','nonzero_exit','missing_credentials','network_unavailable'): result['reason']=value['reason']
        return result
    if model!=policy()['jev_model']: result['reason']='model_effort_mismatch'; return result
    if valid_answer(value.get('answer')):
        answer=value['answer']; result.update(status='OK',reason=None,choice=answer['choice'],confidence=answer['confidence'],probabilities=answer['probabilities'])
    return result


def replay(protocol,events):
    validate_protocol(protocol); tasks={}; ids=set(); prs=set(); previous=digest(protocol); last=stamp(protocol['activated_at']); closed=False
    for index,e in enumerate(events,1):
        fields(e,{'sequence','previous_digest','event_digest','event_id','at','kind','task_id','data'})
        unsigned={k:v for k,v in e.items() if k!='event_digest'}
        if e['sequence']!=index or e['previous_digest']!=previous or e['event_digest']!=digest(unsigned): raise ValueError('stale_or_tampered_ledger')
        hexvalue(e['event_id'],32)
        if e['event_id'] in ids or stamp(e['at'])<last or closed: raise ValueError('duplicate_or_invalid_event_order')
        ids.add(e['event_id']); previous=e['event_digest']; last=stamp(e['at']); safe(e)
        k,data=e['kind'],e['data']; tid=e['task_id']
        if k=='close':
            fields(data,{'reason'});
            if tid is not None or data['reason'] not in ('collection_stopped','protocol_replaced'): raise ValueError('invalid_close')
            closed=True; continue
        if k=='preflight':
            fields(data,{'pr_number','reason'})
            if tid is not None or type(data['pr_number']) is not int or data['reason'] not in (
                'NOT_ELIGIBLE_CONTRACT_UNCLEAR','NOT_ELIGIBLE_HISTORICAL','NOT_ELIGIBLE_PRIOR_REVIEW',
                'NOT_ELIGIBLE_TOOLING','GITHUB_UNAVAILABLE','NOT_ELIGIBLE_NOT_FUTURE'):
                raise ValueError('invalid_preflight')
            continue
        if k=='snapshot':
            validate_snapshot(protocol,data)
            if tid!=data['task_id'] or tid in tasks or data['pr_number'] in prs or stamp(data['snapshot_at'])>stamp(e['at']):
                raise ValueError('duplicate_pr_or_invalid_freeze')
            tasks[tid]=dict(snapshot=data,jev=[],sol=[],ticket=None,truth=None,revisions=[],rework=None,pending_jev={}); prs.add(data['pr_number']); continue
        if tid not in tasks: raise ValueError('unknown_task')
        task=tasks[tid]; s=task['snapshot']; items={i['item_id'] for i in s['items']}
        if k=='jev_request':
            fields(data,{'attempt_id','item_id','snapshot_digest','contract_digest','head_sha','diff_digest','source_fingerprint','started_at'})
            hexvalue(data['attempt_id'],32)
            if (task['ticket'] is not None or task['pending_jev'] or data['attempt_id'] in ids or data['item_id'] not in items or
                data['snapshot_digest']!=digest(s) or data['contract_digest']!=digest(s['items']) or
                any(data[x]!=s[x] for x in ('head_sha','diff_digest','source_fingerprint')) or
                not stamp(s['snapshot_at'])<=stamp(data['started_at'])<=stamp(e['at']) or
                (task['jev'] and stamp(data['started_at'])<stamp(task['jev'][-1]['completed_at']))):
                raise ValueError('invalid_provider_request_reservation')
            ids.add(data['attempt_id']); task['pending_jev'][data['attempt_id']]=data
        elif k in ('jev','sol'):
            validate_attempt(data,k,s,e['at'])
            if k=='jev':
                reserved=task['pending_jev'].get(data['attempt_id'])
                if reserved is None or any(data[x]!=reserved[x] for x in reserved): raise ValueError('unreserved_or_changed_jev_result')
                del task['pending_jev'][data['attempt_id']]
                if task['ticket'] is not None: raise ValueError('jev_after_review')
                if task['jev'] and stamp(data['started_at'])<stamp(task['jev'][-1]['completed_at']): raise ValueError('overlapping_provider_attempt')
            else:
                if data['attempt_id'] in ids: raise ValueError('duplicate_attempt')
                ids.add(data['attempt_id'])
                if task['ticket'] is None or stamp(data['started_at'])<stamp(task['ticket']['at']) or task['truth'] is not None:
                    raise ValueError('sol_before_jev_or_after_truth')
                if task['sol'] and stamp(data['started_at'])<stamp(task['sol'][-1]['completed_at']): raise ValueError('overlapping_review_attempt')
            task[k].append(data)
        elif k=='review_start':
            fields(data,{'model','effort','blinded','snapshot_digest','contract_digest'})
            if (task['ticket'] is not None or task['pending_jev'] or not task['jev'] or
                data['model']!=MODEL or data['effort']!=EFFORT or type(data['blinded']) is not bool or
                data['snapshot_digest']!=digest(s) or data['contract_digest']!=digest(s['items']) or
                any(stamp(a['completed_at'])>=stamp(e['at']) for a in task['jev'])):
                raise ValueError('invalid_review_ticket_or_freeze_order')
            task['ticket']=dict(data,at=e['at'])
        elif k=='truth':
            fields(data,{'items','snapshot_digest','head_sha','diff_digest'})
            if data['snapshot_digest']!=digest(s) or data['head_sha']!=s['head_sha'] or data['diff_digest']!=s['diff_digest']:
                raise ValueError('ground_truth_for_wrong_revision')
            if not task['sol'] or any(stamp(a['completed_at'])>=stamp(e['at']) for a in task['sol']): raise ValueError('truth_before_findings_freeze')
            if not isinstance(data['items'],list) or len(data['items'])!=len(items): raise ValueError('incomplete_ground_truth')
            seen=set(); old={i['item_id']:i for i in (task['truth'] or {}).get('items',[])}
            for i in data['items']:
                fields(i,{'item_id','state','choice','severity','evidence','adjudicator_model','adjudicator_effort'})
                if i['item_id'] in seen or i['item_id'] not in items or i['adjudicator_model']!=MODEL or i['adjudicator_effort']!=EFFORT:
                    raise ValueError('invalid_ground_truth_identity')
                seen.add(i['item_id'])
                if i['state']=='RESOLVED':
                    if i['choice'] not in ('regression','no_regression') or (i['severity'] not in ('critical','important','minor') if i['choice']=='regression' else i['severity'] is not None):
                        raise ValueError('invalid_ground_truth_label')
                    if not isinstance(i['evidence'],list): raise ValueError('missing_non_ai_evidence')
                    kinds=set()
                    for proof in i['evidence']:
                        fields(proof,{'kind','digest'}); hexvalue(proof['digest'],64)
                        if proof['kind'] not in KINDS: raise ValueError('invalid_evidence_kind')
                        kinds.add(proof['kind'])
                    if len(kinds)<2 or not kinds & {'test','compiler','ci','source','specification'}: raise ValueError('single_ai_ground_truth')
                elif i['state']!='GROUND_TRUTH_UNRESOLVED' or any(i[x] is not None for x in ('choice','severity')) or i['evidence']!=[]:
                    raise ValueError('invalid_unresolved_truth')
                if i['item_id'] in old and old[i['item_id']]['state']=='RESOLVED' and i!=old[i['item_id']]:
                    raise ValueError('cannot_rewrite_confirmed_oracle_or_miss')
            task['truth']=data
        elif k=='revision':
            fields(data,{'head_sha','diff_digest','fix_commits','red_green_tests'}); hexvalue(data['head_sha'],40); hexvalue(data['diff_digest'],64)
            for key in ('fix_commits','red_green_tests'):
                if data[key] is not None: number(data[key],True)
            task['revisions'].append(data)
        elif k=='rework':
            keys={'confirmed_findings','fix_commits','red_green_tests','review_rounds','reopened_issues','regressions_after_fix','context_retrieval','test_failures','orchestration_wall_seconds'}
            fields(data,keys)
            for key,value in data.items():
                if value is not None: number(value,key!='orchestration_wall_seconds')
            if task['rework'] is not None: raise ValueError('rework_already_frozen')
            task['rework']=data
        else: raise ValueError('unknown_event_kind')
    return tasks


class Ledger:
    def __init__(self,path,protocol=None):
        self.path=Path(path)
        if self.path.name!='semantic-prospective' or self.path.parent.name!='.workflow-eval' or any(p.is_symlink() for p in (self.path,self.path.parent)):
            raise ValueError('wrong_or_unsafe_cohort_storage')
        file=self.path/'protocol.json'
        if protocol is not None:
            validate_protocol(protocol); self.path.mkdir(parents=True,exist_ok=True)
            self.write_new(file,protocol)
        self.protocol=json.loads(file.read_text(encoding='utf-8')); validate_protocol(self.protocol)
    @staticmethod
    def write_new(path,value):
        if path.is_symlink(): raise ValueError('unsafe_output_path')
        with path.open('x',encoding='utf-8',newline='\n') as stream:
            json.dump(value,stream,ensure_ascii=False,indent=2,allow_nan=False); stream.write('\n')
    def read(self):
        validate_protocol(self.protocol)
        if json.loads((self.path/'protocol.json').read_text(encoding='utf-8'))!=self.protocol: raise ValueError('protocol_mutated')
        events=[]
        for index,path in enumerate(sorted(self.path.glob('event-*.json')),1):
            if path.name!='event-'+str(index).zfill(6)+'.json' or path.is_symlink(): raise ValueError('ledger_sequence_gap')
            events.append(json.loads(path.read_text(encoding='utf-8')))
        replay(self.protocol,events); return events
    def append(self,kind,tid,data,at=None):
        events=self.read()
        e=dict(sequence=len(events)+1,previous_digest=events[-1]['event_digest'] if events else digest(self.protocol),
               event_id=new_id(),at=at or now(),kind=kind,task_id=tid,data=data)
        e['event_digest']=digest(e)
        replay(self.protocol,events+[e])
        self.write_new(self.path/('event-'+str(e['sequence']).zfill(6)+'.json'),e)
        return e

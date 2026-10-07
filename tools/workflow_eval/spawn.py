"""Generate explicit collaboration.spawn_agent arguments; never execute a spawn.

Contract: this session's collaboration.spawn_agent tool accepts string none,
all, and positive integer strings. Omitted/all inherits parent model settings
and forbids explicit overrides. This adapter therefore refuses all: a reason
alone cannot satisfy the project's explicit model/effort requirement on this
host. Recheck the host contract before using this adapter on another host.
"""
import json
import re
from .serialization import canonical_json

from .context import build_context_packet, expand_context_packet, _safe_evidence
from .triage import ACTIVE_SOL_MODEL, PROTECTED

ROLE_SCOPES = {'explorer': {'none', '1', '2'},
               'researcher': {'none', '1', '2'},
               'worker': {'none', '1', '2', '3'},
               'reviewer': {'none'}}
COMPLEX = re.compile(r'(?i)\b(architecture|architectural|orchestration|concurrency|'
                     r'concurrent|state.management|unresolved.root.cause|'
                     r'unknown.root.cause|JEV|JEVGrep)\b')


def build_spawn_request(root, role, task_name, bundle, *, specification,
                        repository_rules, unresolved_questions, packet=None,
                        verification=None, complex_work=False, fork_turns='none',
                        full_history_reason=None):
    """Validate current evidence and prepare a fresh role's explicit tool call.

    complex_work is an additional caller assertion of any existing High trigger;
    False cannot lower detected protected/unknown/multiple-module work. Unknown
    dependencies are investigation tasks, never evidence of review completion.
    Read-only/independence instructions are prompt policy, not OS enforcement.
    """
    if not isinstance(role, str) or role not in ROLE_SCOPES:
        raise ValueError('invalid_spawn_role')
    if not isinstance(task_name, str) or not re.fullmatch(r'[a-z][a-z0-9_]*', task_name):
        raise ValueError('invalid_spawn_task_name')
    if fork_turns == 'all':
        raise ValueError('full_history_explicit_overrides_unsupported_use_none_and_packet')
    if (not isinstance(fork_turns, str) or fork_turns not in ROLE_SCOPES[role]
            or full_history_reason is not None):
        raise ValueError('unsupported_role_fork_turns')
    if (type(complex_work) is not bool
            or not isinstance(specification, str) or not specification.strip()
            or not isinstance(repository_rules, str) or not repository_rules.strip()
            or not isinstance(unresolved_questions, list)
            or any(not isinstance(q, str) or not q.strip() for q in unresolved_questions)):
        raise ValueError('explicit_spawn_context_required')
    _safe_evidence([specification, repository_rules, unresolved_questions])
    # Build through the existing validator even if an already-built packet is
    # supplied. Verification must have its exact safe original, not just a hash.
    current = build_context_packet(bundle, verification=verification, root=root)
    if packet is None:
        packet = current
    expanded = expand_context_packet(packet, bundle, root=root)
    if expanded['expansion_required']:
        raise ValueError('context_expansion_required_retrieve_and_rebuild_bundle')
    if expanded['verification'] != current['verification']:
        raise ValueError('verification_evidence_required_or_digest_mismatch')
    task_evidence = '\n'.join([expanded['task'], expanded['patch'], specification] + unresolved_questions)
    protected_task = expanded['protected'] or bool(PROTECTED.search(task_evidence))
    high = (complex_work or protected_task or expanded['dependency'] == 'unknown'
            or len(expanded['changed_paths']) > 1
            or COMPLEX.search(task_evidence))
    effort = 'high' if role == 'reviewer' or (role == 'worker' and high) else 'medium'
    payload = dict(role=role, read_only=role != 'worker', independent_context=role == 'reviewer',
                   specification=specification, repository_rules=repository_rules,
                   context_packet=expanded, verification_evidence=verification,
                   unresolved_questions=unresolved_questions,
                   protected_task=protected_task,
                   dependency_investigation_required=expanded['dependency'] == 'unknown',
                   instructions=[
                       'Read the actual evidence and acquire any relevant dependencies before deciding.',
                       'Unknown dependencies require investigation; never silently approve incomplete context.',
                       'Verification digests do not replace original records or required logs. Preserve warnings, failures and unexecuted checks.',
                       'Preserve mandatory independent Sol High review and deterministic verification; never place live orders.',
                       'Report actual host execution metadata only when observable; requested settings are not proof.'
                   ])
    if role == 'reviewer':
        payload['instructions'].append('Review independently from the specification and actual diff; do not inherit implementation conclusions.')
    if role != 'worker':
        payload['instructions'].append('Read-only: do not modify files or external state.')
    return dict(task_name=task_name, model=ACTIVE_SOL_MODEL, reasoning_effort=effort,
                fork_turns=fork_turns,
                message=canonical_json(payload))

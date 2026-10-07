---
name: model-orchestrator
description: Use when non-trivial software-engineering work would benefit from choosing among available model families or reasoning levels, escalating after evidence, or resolving a bounded semantic decision with TypeSafeAI/Jev.
---

# Model Orchestrator

Route development work using evidence and the project role floors; this skill is tooling guidance and does not add routing to the EA runtime.

<!-- canonical-rules: model-orchestrator version=phase2a-1 -->

Required rule IDs: every ID in `consumers.model-orchestrator` of [canonical.json](../../rules/canonical.json), version `phase2a-1`. Read all resolved bodies before use; `tools.workflow_eval.rules.expand_document_rules` validates version/hash/references and expands full text once. A reference or digest never replaces required context. Missing/unreadable/mismatched/circular rules stop use until retrieved/repaired. Follow [AGENTS.md](../../../AGENTS.md) and the explicit request; do not reproduce global rules in this skill.

Explorer/researcher use GPT-6.1 Sol Medium. Reviewers use independent Sol High contexts. These are summaries; all role floors, protected triggers, host-contract limits and review conditions are in the resolved rules.

## Workflow-specific operations

Create the existing bundle under ignored `.workflow-eval/` from the repository root, then generate explicit host arguments:

```text
python -m tools.workflow_eval.cli spawn-request .workflow-eval/bundle.json --role reviewer --task-name review_change --spec-file .workflow-eval/spec.md --test-evidence .workflow-eval/verification.json
```

Add `--packet` for an existing packet. Omit `--test-evidence` only when no verification record exists and report checks as unexecuted. The output `.workflow-eval/spawn-request.json` is a host-tool argument object; pass its exact fields to the supported host tool. `--complex-work` asserts additional worker High triggers. Consult the resolved spawn-host rule before any direct/helper call.

For an offline routing check, compare [fixture expectations](fixtures/routing_cases.json) and [dry-run observations](fixtures/routing_dry_run.json):

```text
python .agents/skills/model-orchestrator/scripts/evaluate_routing.py
```

Fixture evidence describes intended inspection order/preconditions, not actual test/model/Jev execution or live routing quality. Use representative privacy-safe observations before considering automatic switching. Consult [typesafe-ai](../typesafe-ai/SKILL.md) for current API, Choice/Score/Noul, question construction and uncertainty handling rather than duplicating those API instructions.

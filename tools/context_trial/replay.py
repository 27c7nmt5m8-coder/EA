"""Evidence-only Codex CLI replay; opt-in, ephemeral, read-only, no native tools.

Archive retrieval is an explicit ID protocol. Tool/file counters describe that
protocol, not hidden Codex internals. All attempted rounds count toward totals.
"""
import json
import os
from pathlib import Path
import subprocess
import time
from .core import UNKNOWN, add_measured, classify, selected, measured_usage

SCHEMA = {"type": "object", "additionalProperties": False, "properties": {
    "answer": {"type": "string"},
    "facts": {"type": "array", "items": {"type": "object", "additionalProperties": False,
        "properties": {"name": {"type": "string"}, "value": {"type": "string"}},
        "required": ["name", "value"]}},
    "restore_ids": {"type": "array", "items": {"type": "string"}},
    "referenced_ids": {"type": "array", "items": {"type": "string"}},
}, "required": ["answer", "facts", "restore_ids", "referenced_ids"]}


def parse_events(text):
    usages, messages, events, tool_items = [], [], [], set()
    invalid = False
    for line in text.splitlines():
        try:
            event = json.loads(line)
        except (ValueError, TypeError):
            invalid = True
            continue
        if not isinstance(event, dict):
            invalid = True
            continue
        events.append(event.get("type"))
        if event.get("type") == "turn.completed":
            usages.append(measured_usage(event))
        item = event.get("item", {})
        if item.get("type") in {"command_execution", "mcp_tool_call", "web_search", "file_change"}:
            tool_items.add(item.get("id", str(len(tool_items))))
        if event.get("type") == "item.completed" and item.get("type") == "agent_message":
            messages.append(item.get("text", ""))
    final = None
    if messages:
        try:
            candidate = json.loads(messages[-1])
            if isinstance(candidate, dict):
                final = candidate
        except ValueError:
            pass
    return {"input_tokens": add_measured(u["input_tokens"] for u in usages) if usages else UNKNOWN,
            "output_tokens": add_measured(u["output_tokens"] for u in usages) if usages else UNKNOWN,
            "native_tool_calls": len(tool_items), "final": final,
            "completed": bool(usages) and "turn.failed" not in events and not invalid,
            "event_types": sorted({e for e in events if isinstance(e, str)})}


def grade(final, expected):
    try:
        facts = final["facts"]
        actual = {f["name"]: f["value"] for f in facts}
        passed = len(actual) == len(facts) and actual == expected
    except (KeyError, TypeError):
        actual, passed = {}, False
    return {"passed": passed, "expected": expected, "actual": actual}


class CodexRunner:
    def __init__(self, cwd, schema_path):
        self.cwd = Path(cwd)
        self.schema_path = Path(schema_path)
        self.schema_path.write_text(json.dumps(SCHEMA), encoding="utf-8")

    def __call__(self, prompt, model, effort):
        args = ["codex", "exec", "--json", "--ephemeral", "--ignore-user-config",
                "--sandbox", "read-only", "--model", model, "--color", "never",
                "-c", f'model_reasoning_effort="{effort}"',
                "--disable", "shell_tool", "--disable", "unified_exec",
                "--disable", "multi_agent", "--disable", "hooks", "--disable", "plugins",
                "--output-schema", str(self.schema_path), "-"]
        # Do not expose provider credentials to child tools. Codex uses its normal
        # host authentication. Never copy or log auth files.
        env = {k: v for k, v in os.environ.items()
               if not any(s in k.upper() for s in ("API_KEY", "TOKEN", "SECRET", "PASSWORD", "CREDENTIAL"))}
        start = time.perf_counter()
        try:
            process = subprocess.run(args, input=prompt, cwd=self.cwd, env=env,
                capture_output=True, text=True, encoding="utf-8", timeout=180)
            result = parse_events(process.stdout)
            result["exit_code"] = process.returncode
            result["status"] = "completed" if process.returncode == 0 and result["completed"] and result["final"] else "incomplete"
            # Diagnostic enum only: no stderr text, raw errors or raw event logs.
            if "4551" in process.stderr or "4551" in process.stdout:
                result["status"] = "winerror_4551"
        except subprocess.TimeoutExpired:
            result = {"status": "timeout", "input_tokens": UNKNOWN, "output_tokens": UNKNOWN,
                      "native_tool_calls": UNKNOWN, "final": None}
        except OSError as exc:
            result = {"status": "winerror_4551" if getattr(exc, "winerror", None) == 4551 else "launch_unavailable",
                      "input_tokens": UNKNOWN, "output_tokens": UNKNOWN,
                      "native_tool_calls": UNKNOWN, "final": None}
        result["wall_seconds"] = time.perf_counter() - start
        result["prompt_utf8_bytes"] = len(prompt.encode("utf-8"))
        return result


def run_arm(task, classification, runner):
    entries = task["entries"]
    active = selected(entries, classification)
    by_id = {e.id: e for e in entries}
    ids = {e.id for e in active}
    # Every omitted original remains recoverable, even DROP_CANDIDATE. Nothing
    # is deleted in this experiment; a later request for a drop is a false drop.
    archived = {e.id: e for e in entries if e.id not in ids}
    catalog = [{"id": e.id, "source": e.source, "type": e.kind} for e in archived.values()]
    history, rounds, stages, restores, references = [], [], [], [], []
    start = time.perf_counter()
    for number, stage in enumerate(task["stages"], 1):
        stage_final = None
        for attempt in range(3):
            prompt = (
                "This is an isolated retrospective evidence replay, not an action task. "
                "Do not use native tools, browse, read files or change anything. Follow the safety rules in the evidence. "
                "All evidence is historical; do not present past tests as new executions. "
                "Answer the current stage only using the exact entries below. Return JSON matching the schema. "
                "facts values must be strings, booleans written true/false. Include referenced entry IDs. "
                "If evidence is missing, return restore_ids from the archive catalog and empty facts; "
                "the harness will return original entries. Do not guess missing facts. "
                "No answer key is supplied.\n" +
                json.dumps({"goal": task["goal"], "stage": number, "question": stage["question"],
                    "entries": [{"id": e.id, "source": e.source, "text": e.text} for e in active],
                    "archive_catalog": catalog, "previous_stages": history}, ensure_ascii=False))
            result = runner(prompt, task["model"], task["effort"])
            rounds.append(result)
            if result["status"] != "completed" or result["native_tool_calls"] != 0:
                break
            final = result["final"]
            requested = final.get("restore_ids", [])
            if not isinstance(requested, list) or any(not isinstance(i, str) or i not in archived for i in requested):
                result["status"] = "invalid_restore"
                break
            if requested:
                for id in dict.fromkeys(requested):
                    active.append(archived.pop(id))
                    restores.append(id)
                catalog = [c for c in catalog if c["id"] in archived]
                continue
            cited = final.get("referenced_ids", [])
            if (not isinstance(cited, list) or not cited
                    or any(not isinstance(i, str) or i not in {e.id for e in active} for i in cited)):
                result["status"] = "invalid_reference"
                break
            references.extend(cited)
            stage_final = final
            history.append(final)
            break
        passed = grade(stage_final or {}, stage["expected"])
        stages.append({"stage": number, "grade": passed, "final": stage_final})
        if stage_final is None:
            break
    inputs = add_measured(r["input_tokens"] for r in rounds)
    outputs = add_measured(r["output_tokens"] for r in rounds)
    return {"initial_context_utf8_bytes": sum(len(e.text.encode()) for e in entries),
            "retained_context_utf8_bytes": sum(len(e.text.encode()) for e in selected(entries, classification)),
            "final_context_utf8_bytes": sum(len(e.text.encode()) for e in active),
            "internal_context_tokens": UNKNOWN,
            "root_input_tokens": inputs, "root_output_tokens": outputs,
            "root_total_tokens": add_measured([inputs, outputs]),
            "wall_seconds": time.perf_counter() - start, "rounds": rounds, "stages": stages,
            "protocol_tool_calls": len(restores), "native_tool_calls": add_measured(r["native_tool_calls"] for r in rounds),
            "files_read": 0, "files_reread": 0, "file_count_scope": "explicit replay protocol only; original corpus preloaded",
            "repeated_investigation_count": UNKNOWN, "retry_count": 0,
            "archive_restore_count": len(restores), "restored_ids": restores,
            "referenced_ids": sorted(set(references)),
            "fact_rubric_result": "PASS" if len(stages) == len(task["stages"]) and all(s["grade"]["passed"] for s in stages) else "FAIL_OR_INCOMPLETE",
            "final_correctness": "PENDING_NARRATIVE_REVIEW" if len(stages) == len(task["stages"])
                and all(s["grade"]["passed"] and isinstance(s["final"].get("answer"), str)
                        and s["final"]["answer"].strip() for s in stages) else "FAIL_OR_INCOMPLETE",
            "test_result": "deterministic replay fact rubric; not EA execution",
            "compiler_result": "NOT_RUN_PRODUCT_UNCHANGED",
            "factual_consistency": "REQUIRES_NARRATIVE_REVIEW"}


def replay_pair(task, shadow, audit_result, runner):
    if not audit_result.get("replay_allowed"):
        raise ValueError("Shadow audit did not authorize replay")
    # A uses the exact same deterministic rules, with no semantic classifier.
    current = classify(task["entries"], task["goal"], None)
    arms = {}
    order = ("B", "A") if task["id"] == "B" else ("A", "B")
    for arm in order:
        arms[arm] = run_arm(task, current if arm == "A" else shadow, runner)
    a, b = arms["A"], arms["B"]
    jev_total = add_measured([shadow["input_tokens"], shadow["output_tokens"]])
    b["total_llm_tokens_with_jev"] = add_measured([b["root_total_tokens"], jev_total])
    a["total_llm_tokens_with_jev"] = a["root_total_tokens"]
    b["wall_seconds_with_filter"] = b["wall_seconds"] + shadow["wall_seconds"]
    a["wall_seconds_with_filter"] = a["wall_seconds"] + current["wall_seconds"]
    b["context_reduction_percent"] = 100 * (1 - b["retained_context_utf8_bytes"] / a["retained_context_utf8_bytes"])
    # Post-replay audit also catches a prelabel error: A's required citations or
    # B's restores may expose a critical false drop missed in retrospective labels.
    drops = {r["id"] for r in shadow["entries"] if r["class"] == "DROP_CANDIDATE"}
    observed_false_drops = sorted(drops & (set(a["referenced_ids"]) | set(b["restored_ids"])))
    return {"order": order, "arms": arms, "observed_critical_false_drop_ids": observed_false_drops}

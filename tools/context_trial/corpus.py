"""Curated retrospective replay of tracked, sanitized repository evidence.

No session content is exported. Text entries are exact git blob spans, never
LLM summaries. This small pilot is NOT a complete long-running task replay.
"""
import dataclasses
import hashlib
import json
import subprocess
from .core import Entry


def git_blob(root, revision, path):
    return subprocess.check_output(["git", "show", f"{revision}:{path}"], cwd=root).decode("utf-8")


def make_corpus(root, revision):
    def whole(id, path, kind, **kw):
        return Entry(id, git_blob(root, revision, path), kind, source=f"{revision}:{path}",
                     relation="current", **kw)

    def span(id, path, first, last, kind, **kw):
        text = "".join(git_blob(root, revision, path).splitlines(keepends=True)[first-1:last])
        return Entry(id, text, kind, source=f"{revision}:{path}:{first}-{last}",
                     relation="historical", **kw)

    # All repository rules and direct source evidence are deterministic pins.
    rules = whole("rules", "AGENTS.md", "safety")
    state = Entry("state", f"Frozen repository revision: {revision}\nNo live trading, no merge, no product edits.", "state", relation="current")
    validation = span("cause", "VALIDATION_JA.md", 3, 17, "root_cause")
    previous = span("previous", "VALIDATION_JA.md", 19, 69, "baseline")
    indicator = span("source", "src/MT3SymbolState.mqh", 391, 399, "working_code", direct=True)
    tester = whole("tester", "verification/indicator_demand.json", "tester")
    compiler = whole("compiler", "verification/native_compile.json", "compiler")
    old_tests = whole("old_tests", "verification/integration_results.json", "regression")
    source_audit = whole("source_audit", "verification/source_audit.json", "regression")
    csv_tests = whole("csv_tests", "verification/stats_results.json", "regression")
    # Hand-reviewed representations contain neither source code nor raw logs.
    # They describe existing exact spans; they are NOT replacements for them.
    license_note = whole("license", ".agents/skills/typesafe-ai/LICENSE", "documentation",
        reviewed=True, representation="Third party software license terms for a semantic classification library; no diagnostic or validation evidence.")
    file_table = span("file_table", "README_JA.md", 30, 45, "documentation", reviewed=True,
        representation="A package installation table listing the roles of the main program, worker and header files.")
    packaging = span("packaging", "README_JA.md", 451, 469, "documentation", reviewed=True,
        representation="A package file inventory and directions for finding developer validation documents.")

    common = [rules, state]
    task_a = dict(id="A", type="historical_cause_analysis", model="gpt-6-sol", effort="high",
        goal="Explain the historical indicator initialization stall and distinguish verified fixes from remaining unknowns.",
        entries=common + [validation, previous, indicator, tester, compiler, old_tests, file_table, packaging, license_note],
        stages=[
            {"question": "Trace the historical initial failure and mechanism using the original evidence. Give facts premature_bars_check_blocked_request (true/false), first_api_after_fix (API name), all_timeframes_required (true/false). Explain the causal sequence and why a past successful mock run alone was insufficient.",
             "expected": {"premature_bars_check_blocked_request": "true", "first_api_after_fix": "CopyBuffer", "all_timeframes_required": "true"}},
            {"question": "Compare before/after measured Tester results and whether fixing the stall solved zero trades. Give facts before_trades, after_trades, zero_trades_solved (true/false). Preserve downstream-gate uncertainty.",
             "expected": {"before_trades": "0", "after_trades": "0", "zero_trades_solved": "false"}},
            {"question": "Explain verification limits and the distinct older versus later mock results. Give facts old_mock_passed, latest_recorded_mock_passed, native_errors, native_warnings, live_verified (true/false). Do not claim a new compile or Tester execution.",
             "expected": {"old_mock_passed": "573", "latest_recorded_mock_passed": "582", "native_errors": "0", "native_warnings": "0", "live_verified": "false"}},
        ])
    counts = json.loads(tester.text)
    computed = {"listed_transition_sum": sum(counts["after_gate_transition_counts"].values()),
                "reported_transitions": counts["diagnostic_transitions_after"]}
    computed["unaccounted_transitions"] = computed["reported_transitions"] - computed["listed_transition_sum"]
    calculation = Entry("calculation", json.dumps(computed, sort_keys=True), "baseline", relation="current",
                        source="deterministic sum of tester.after_gate_transition_counts")
    task_b = dict(id="B", type="large_validation_log_analysis", model="gpt-6-luna", effort="medium",
        goal="Interpret historical Tester transition aggregates and large validation records without conflating denominators or execution environments.",
        entries=common + [tester, compiler, source_audit, old_tests, csv_tests, calculation, file_table, packaging, license_note],
        stages=[
            {"question": "Read the deterministic calculation and Tester artifact. Give facts listed_transition_sum, reported_transitions, unaccounted_transitions, counts_are_entry_attempts (true/false), after_trades. Explain the denominator discrepancy; do not invent a missing event reason.",
             "expected": {**{k: str(v) for k,v in computed.items()}, "counts_are_entry_attempts": "false", "after_trades": "0"}},
            {"question": "Distinguish historical mock, CSV, static, native, Tester and live verification. Give facts csv_passed, old_mock_passed, native_errors, live_verified (true/false), real_ai_verified (true/false). Large log success is not proof of profitability.",
             "expected": {"csv_passed": "20", "old_mock_passed": "573", "native_errors": "0", "live_verified": "false", "real_ai_verified": "false"}},
        ])
    task_c = dict(id="C", type="short_documentation_edit", model="gpt-6-luna", effort="low",
        goal="Draft a short validation note that accurately separates historical evidence from this context experiment.",
        entries=common + [validation, compiler, file_table, packaging, license_note],
        stages=[
            {"question": "Draft a short Japanese Markdown validation note (answer field) for a separate diagnostics document. State that historical native compile had zero errors/warnings, this context experiment did not rerun native compile or Strategy Tester, and live trading remains prohibited. Give facts product_changed (true/false), new_native_compile (true/false), new_tester (true/false), live_allowed (true/false). Do not modify any repository file.",
             "expected": {"product_changed": "false", "new_native_compile": "false", "new_tester": "false", "live_allowed": "false"}},
        ])
    for task in [task_a, task_b, task_c]:
        task["entries"] += [Entry("goal", task["goal"], "goal", relation="current")]
        task["audit_labels"] = {e.id: ("unnecessary" if e.id == "license" else
            "useful_background" if e.id in {"file_table", "packaging"} else "required")
            for e in task["entries"]}
        task["corpus_sha256"] = hashlib.sha256(json.dumps(
            [dataclasses.asdict(e) for e in task["entries"]], sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    return [task_a, task_b, task_c]

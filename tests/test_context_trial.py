"""Offline safety and measurement tests for the isolated experiment."""
import dataclasses
import json
import math
from pathlib import Path
import sys
import unittest
import urllib.error

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from context_trial.core import Entry, PIN_KINDS, NoRedirect, classify, audit, selected, validate_answer
from context_trial.replay import parse_events, grade, replay_pair, run_arm


def entry(id="e1", **kw):
    defaults = dict(text="An unrelated formatting note.", kind="note",
                    representation="A formatting preference from a different task.",
                    reviewed=True, relation="historical")
    defaults.update(kw)
    return Entry(id=id, **defaults)


def answer(label="DROP_CANDIDATE", confidence=0.99):
    labels = ["ACTIVE", "ARCHIVE", "DROP_CANDIDATE", "UNCERTAIN"]
    return {"answers": {
        "classification": {"type": "choice", "choice": label,
            "confidence": confidence,
            "probabilities": {k: float(k == label) for k in labels}},
        "relevance": {"type": "score", "score": 0.0, "confidence": 0.99,
            "probabilities": {"0": 1.0, "1": 0.0, "2": 0.0},
            "legend": {"0": "unrelated", "1": "possible later use", "2": "needed now"}}},
        "usage": {"input_tokens": 123, "output_tokens": 42}, "model": "jev-test"}


class ClassifierTests(unittest.TestCase):
    def run_shadow(self, entries, responder=lambda _: answer(), **kw):
        calls = []
        def call(payload):
            calls.append(payload)
            return responder(payload)
        result = classify(entries, "Review a historical diagnostic explanation.", call, **kw)
        return result, calls

    def test_all_required_pin_kinds_and_dependency_closure(self):
        entries = [entry(str(i), kind=k) for i, k in enumerate(PIN_KINDS)]
        entries += [entry("needed", dependencies=("dependency",), direct=True), entry("dependency")]
        result, calls = self.run_shadow(entries)
        self.assertTrue(all(r["class"] == "PINNED" for r in result["entries"]))
        self.assertEqual(calls, [])

    def test_shadow_never_mutates_originals(self):
        entries = [entry()]
        before = dataclasses.asdict(entries[0])
        result, _ = self.run_shadow(entries)
        self.assertEqual(before, dataclasses.asdict(entries[0]))
        self.assertEqual(result["entries"][0]["class"], "DROP_CANDIDATE")
        self.assertEqual(selected(entries, result, shadow=True), entries)

    def test_duplicates_are_deterministic_and_pins_win(self):
        entries = [entry("first"), entry("duplicate"), entry("pinned", kind="baseline")]
        result, calls = self.run_shadow(entries)
        self.assertEqual(len(calls), 1)
        self.assertEqual(result["entries"][1]["class"], "ARCHIVE")
        self.assertEqual(result["entries"][2]["class"], "PINNED")

    def test_bypass_and_no_client_make_no_calls(self):
        result, calls = self.run_shadow([entry()], bypass=True)
        self.assertEqual(calls, [])
        self.assertEqual(result["entries"][0]["class"], "ACTIVE")
        self.assertEqual(classify([entry()], "goal", None)["entries"][0]["class"], "ACTIVE")

    def test_privacy_skips_entire_payload(self):
        for fields in [dict(reviewed=False), dict(representation="person@example.invalid"),
                       dict(representation="password=fictional"), dict(representation="x" * 321)]:
            result, calls = self.run_shadow([entry(**fields)])
            self.assertEqual(calls, [])
            self.assertEqual(result["entries"][0]["class"], "ACTIVE")

    def test_only_allowed_minimal_state_sent(self):
        _, calls = self.run_shadow([entry(text="ORIGINAL MUST NOT BE SENT")])
        state = calls[0]["state"]
        self.assertEqual(set(state), {"current_goal", "entry_type", "representation", "state_relation", "dependency_flags"})
        self.assertNotIn("ORIGINAL", json.dumps(calls))

    def test_failure_and_low_confidence_keep(self):
        def fail(_):
            raise TimeoutError("secret error body must not be stored")
        for fn in [fail, lambda _: {}, lambda _: answer(confidence=0.2)]:
            result, _ = self.run_shadow([entry()], fn)
            self.assertEqual(result["entries"][0]["class"], "ACTIVE")
            self.assertNotIn("secret error", json.dumps(result))

    def test_auth_quota_rate_and_transport_failures_keep_without_logging(self):
        for error in [urllib.error.HTTPError("https://example.invalid", code, "private provider body", {}, None)
                      for code in [401, 422, 429, 529]] + [urllib.error.URLError("private transport detail")]:
            def fail(_, error=error):
                raise error
            result, calls = self.run_shadow([entry()], fail)
            self.assertEqual(len(calls), 1)
            self.assertEqual(result["entries"][0]["class"], "ACTIVE")
            self.assertEqual(result["input_tokens"], "UNKNOWN")
            self.assertNotIn("private", json.dumps(result))

    def test_redirects_never_forward_authorization(self):
        self.assertIsNone(NoRedirect().redirect_request(None, None, 302, "redirect", {}, "https://example.invalid"))

    def test_invalid_probabilities_and_nonfinite_scores_rejected(self):
        for value in [math.nan, math.inf, -1, 2]:
            data = answer()
            data["answers"]["classification"]["confidence"] = value
            with self.assertRaises(ValueError):
                validate_answer(data)

    def test_malformed_model_metadata_cannot_leave_drop_on_error(self):
        def malformed(_):
            value = answer()
            value["model"] = None
            return value
        result, _ = self.run_shadow([entry()], malformed)
        self.assertEqual(result["entries"][0]["class"], "ACTIVE")
        self.assertEqual(result["entries"][0]["action"], "KEEP")

    def test_bad_ids_and_dependencies_block(self):
        for entries in [[entry(), entry()], [entry(dependencies=("absent",))]]:
            with self.assertRaises(ValueError):
                self.run_shadow(entries)

    def test_false_drop_and_archive_miss_are_audited(self):
        entries = [entry()]
        result, _ = self.run_shadow(entries)
        report = audit(entries, result, {"e1": "later_reference"})
        self.assertEqual(report["critical_false_drop_count"], 1)
        self.assertFalse(report["replay_allowed"])
        archive, _ = self.run_shadow(entries, lambda _: answer("ARCHIVE"))
        report = audit(entries, archive, {"e1": "failed_hypothesis"})
        self.assertEqual(report["required_archive_count"], 1)

    def test_audit_requires_full_coverage_and_matching_hashes(self):
        entries = [entry()]
        result, _ = self.run_shadow(entries)
        self.assertFalse(audit(entries, result, {})["replay_allowed"])
        self.assertFalse(audit([entry(text="changed")], result, {"e1": "unnecessary"})["replay_allowed"])


class ReplayTests(unittest.TestCase):
    def fixture_task(self):
        return {"id": "C", "entries": [entry("keep", kind="baseline"), entry("later")],
                "goal": "Explain evidence", "model": "test", "effort": "low",
                "stages": [{"question": "Explain count", "expected": {"count": "2"}}]}

    def result(self, answer_text="A note", restores=None):
        return {"status": "completed", "native_tool_calls": 0, "input_tokens": 11,
                "output_tokens": 7, "wall_seconds": 0,
                "final": {"answer": answer_text, "facts": [{"name": "count", "value": "2"}],
                          "restore_ids": restores or [], "referenced_ids": ["keep"]}}

    def test_empty_or_contradictory_narrative_never_auto_passes(self):
        task = self.fixture_task()
        classification = classify(task["entries"], task["goal"], None)
        for answer_text in ["", "Count is three, not two."]:
            r = run_arm(task, classification, lambda *args: self.result(answer_text))
            self.assertNotEqual(r["final_correctness"], "PASS")

    def test_successful_archive_restore_preserves_text_and_counts_cost(self):
        task = self.fixture_task()
        shadow = classify(task["entries"], task["goal"], lambda _: answer("ARCHIVE"))
        prompts = []
        def runner(prompt, *args):
            prompts.append(prompt)
            return self.result(restores=["later"] if len(prompts) == 1 else [])
        r = run_arm(task, shadow, runner)
        self.assertEqual(r["archive_restore_count"], 1)
        self.assertEqual(r["root_total_tokens"], 36)
        self.assertIn(task["entries"][1].text, prompts[1])

    def test_usage_is_actual_or_unknown_not_estimated(self):
        r = parse_events('\n'.join(json.dumps(e) for e in [
            {"type": "turn.completed", "usage": {"input_tokens": 100, "output_tokens": 7, "cached_input_tokens": 30}},
            {"type": "turn.completed", "usage": {"input_tokens": 200, "output_tokens": 9}}]))
        self.assertEqual(r["input_tokens"], 300)
        self.assertEqual(r["output_tokens"], 16)
        self.assertEqual(parse_events('')["input_tokens"], "UNKNOWN")

    def test_rubric_rejects_missing_facts(self):
        self.assertFalse(grade({"facts": []}, {"count": "2"})["passed"])
        self.assertTrue(grade({"facts": [{"name": "count", "value": "2"}]}, {"count": "2"})["passed"])

    def test_no_replay_after_failed_audit(self):
        calls = []
        with self.assertRaises(ValueError):
            replay_pair({}, {}, {"replay_allowed": False}, lambda *a: calls.append(a))
        self.assertEqual(calls, [])


if __name__ == "__main__":
    unittest.main()

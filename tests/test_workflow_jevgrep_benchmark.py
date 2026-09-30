"""Offline tests: a fake jg replaces the provider-backed executable."""
import copy
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from tools.workflow_eval import jevgrep_benchmark as benchmark


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/workflow_jevgrep_cases.json"


class JevgrepBenchmarkTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cases = benchmark.load_cases(FIXTURE, ROOT)

    def setUp(self):
        self.case = self.cases[0]
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.fake_jg = Path(self.temp.name) / "jg.exe"
        self.fake_jg.write_text("fake executable", encoding="utf-8")

    def arm(self, files=None, **changes):
        row = {"task_id": self.case["id"], "base_sha": self.case["base_sha"],
               "sol_model": "gpt-6-sol", "sol_effort": "xhigh", "status": "OK",
               "found_files": files if files is not None else self.case["must_find_files"],
               "sol_input_tokens": 100, "sol_output_tokens": 20, "task_success": 1}
        row.update(changes)
        return row

    def fake_runner(self, args, timeout, cwd):
        if args[1] == "--version":
            return subprocess.CompletedProcess(args, 0, "@dzhng/jevgrep 0.4.4\n", "")
        self.assertEqual(args[-1], "--no-cache")
        self.assertNotEqual(Path(args[2]).resolve(), ROOT)
        return subprocess.CompletedProcess(args, 0, "src/MT3SymbolState.mqh:10\n", "")

    def test_ten_hand_labeled_cases_and_kinds(self):
        self.assertEqual(len(self.cases), 10)
        self.assertEqual({c["kind"] for c in self.cases}, benchmark.KINDS)
        self.assertEqual(sum(c["kind"] == "exact_lookup" for c in self.cases), 5)

    def test_live_requires_explicit_flag(self):
        result = benchmark.run_discovery(self.case, ROOT)
        self.assertEqual((result["status"], result["reason"]), ("UNAVAILABLE", "live_flag_required"))

    def test_native_windows_unavailable(self):
        result = benchmark.run_discovery(self.case, ROOT, live=True, platform="win32")
        self.assertEqual((result["status"], result["reason"]), ("UNAVAILABLE", "unsupported_environment"))

    def test_missing_jg_binary_no_install(self):
        result = benchmark.run_discovery(self.case, ROOT, live=True, platform="linux",
                                         source_paths=["src/MT3SymbolState.mqh"],
                                         jg_executable="jg-certainly-missing")
        self.assertEqual((result["status"], result["reason"]), ("UNAVAILABLE", "missing_jg_binary"))

    def test_fake_jg_discovery_returns_metadata_only(self):
        result = benchmark.run_discovery(self.case, ROOT, live=True, platform="linux",
                                         source_paths=["src/MT3SymbolState.mqh"],
                                         jg_executable=str(self.fake_jg), runner=self.fake_runner)
        self.assertEqual(result["status"], "OK")
        self.assertEqual(result["jg_version"], "@dzhng/jevgrep 0.4.4")
        self.assertEqual(result["found_files"], ["src/MT3SymbolState.mqh"])
        self.assertTrue(result["cache_bypassed"])
        self.assertIsNone(result["jevgrep_tokens"]["value"])
        self.assertIsNone(result["jevgrep_cost"]["value"])
        self.assertNotIn("g_mcRisk", json.dumps(result))

    def test_must_find_outside_allowlist_prevents_provider_call(self):
        called = []
        def runner(args, timeout, cwd):
            called.append(args)
            return self.fake_runner(args, timeout, cwd)
        result = benchmark.run_discovery(self.case, ROOT, live=True, platform="linux",
                     source_paths=["src/MT3Config.mqh"], jg_executable=str(self.fake_jg), runner=runner)
        self.assertEqual(result["status"], "UNAVAILABLE")
        self.assertEqual(result["reason"], "must_find_outside_source_allowlist")
        self.assertEqual(called, [])
        self.assertLess(result["source_universe_coverage"]["value"], 1)

    def test_relevant_universe_coverage_remains_visible(self):
        result = benchmark.run_discovery(self.case, ROOT, live=True, platform="linux",
                    source_paths=["src/MT3SymbolState.mqh"],
                    jg_executable=str(self.fake_jg), runner=self.fake_runner)
        scored = benchmark.score_arm(self.case, dict(self.arm(), **result))
        self.assertEqual(scored["metrics"]["source_universe_coverage"]["value"], 1 / 3)
        self.assertEqual(scored["jg_version"], "@dzhng/jevgrep 0.4.4")
        row = benchmark.evaluate_pair(self.case, self.arm(), dict(self.arm(), **result),
                   current_base_sha=self.case["base_sha"],
                   expected_source_sha256=result["source_sha256"])
        report = benchmark.summarize_pairs([row])
        self.assertEqual(report["jg_versions"], ["@dzhng/jevgrep 0.4.4"])

    def test_b_discovery_without_sol_outcome_is_excluded(self):
        discovery = benchmark.run_discovery(self.case, ROOT, live=True, platform="linux",
                    source_paths=["src/MT3SymbolState.mqh"],
                    jg_executable=str(self.fake_jg), runner=self.fake_runner)
        b = dict(task_id=self.case["id"], base_sha=self.case["base_sha"],
                 sol_model="gpt-6-sol", sol_effort="xhigh", **discovery)
        row = benchmark.evaluate_pair(self.case, self.arm(), b,
                   current_base_sha=self.case["base_sha"],
                   expected_source_sha256=discovery["source_sha256"])
        self.assertEqual(row["comparison_status"], "EXCLUDED")
        self.assertIn("b_sol_evidence_missing", row["exclusion_reasons"])
        self.assertIsNone(row["b"]["task_success"]["value"])

    def test_expected_dataset_missing_cases_make_pilot_incomplete(self):
        fingerprint = benchmark.source_fingerprint(ROOT, ["src/MT3SymbolState.mqh"],
                                                   self.case["base_sha"])
        b = self.arm(cache_bypassed=True, source_sha256=fingerprint, stage_file_count=1)
        row = benchmark.evaluate_pair(self.case, self.arm(), b,
                    current_base_sha=self.case["base_sha"], expected_source_sha256=fingerprint)
        report = benchmark.summarize_pairs([row], expected_case_ids=[c["id"] for c in self.cases])
        self.assertEqual(report["pilot_status"], "PILOT_INCOMPLETE")
        self.assertEqual(len(report["coverage_missing_data"]["missing_case_ids"]), 9)
        self.assertEqual(report["coverage_missing_data"]["dataset"]["coverage"], 0.1)

    def test_absolute_staged_path_is_found_but_unrelated_text_is_not(self):
        def runner(args, timeout, cwd):
            if args[1] == "--version":
                return self.fake_runner(args, timeout, cwd)
            output = ('Query echo: src/MT3Config.mqh\n'
                      f'- "{cwd / "src/MT3SymbolState.mqh"}" — selected source\n'
                      f'- "/elsewhere/src/MT3Config.mqh" — unrelated\n'
                      'End file list.\n')
            return subprocess.CompletedProcess(args, 0, output, "")
        result = benchmark.run_discovery(self.case, ROOT, live=True, platform="linux",
                    source_paths=["src/MT3SymbolState.mqh", "src/MT3Config.mqh"],
                    jg_executable=str(self.fake_jg), runner=runner)
        self.assertEqual(result["found_files"], ["src/MT3SymbolState.mqh"])

    def test_jg_timeout_and_nonzero_are_not_success(self):
        def timeout_runner(args, timeout, cwd):
            if args[1] == "--version":
                return self.fake_runner(args, timeout, cwd)
            raise subprocess.TimeoutExpired(args, timeout)
        kwargs = dict(live=True, platform="linux", source_paths=["src/MT3SymbolState.mqh"],
                      jg_executable=str(self.fake_jg))
        self.assertEqual(benchmark.run_discovery(self.case, ROOT, runner=timeout_runner, **kwargs)["reason"], "jg_timeout")
        def bad_runner(args, timeout, cwd):
            if args[1] == "--version":
                return self.fake_runner(args, timeout, cwd)
            return subprocess.CompletedProcess(args, 2, "src/MT3SymbolState.mqh", "private error")
        result = benchmark.run_discovery(self.case, ROOT, runner=bad_runner, **kwargs)
        self.assertEqual(result["status"], "FAIL")
        self.assertEqual(result["found_files"], [])
        self.assertNotIn("private error", json.dumps(result))

    def test_secret_content_rejected_before_jg(self):
        repository = Path(self.temp.name) / "repo"
        source = repository / "src/MT3SymbolState.mqh"
        source.parent.mkdir(parents=True)
        source.write_text('API_KEY = "secret-value-123"\n', encoding="utf-8")
        called = []
        def runner(args, timeout, cwd):
            called.append(args)
            return self.fake_runner(args, timeout, cwd)
        case = copy.deepcopy(self.case)
        for key in ("must_find_files", "relevant_files", "critical_files"):
            case[key] = ["src/MT3SymbolState.mqh"]
        case["important_files"] = []
        result = benchmark.run_discovery(case, repository, live=True, platform="linux",
                    source_paths=["src/MT3SymbolState.mqh"], jg_executable=str(self.fake_jg), runner=runner)
        self.assertEqual(result["status"], "UNAVAILABLE")
        self.assertEqual(result["reason"], "sensitive_source_content")
        self.assertEqual(called, [])

    def test_rejects_non_allowlisted_paths_even_if_ignore_would_skip(self):
        with tempfile.TemporaryDirectory() as stage:
            with self.assertRaises(ValueError):
                benchmark._stage(ROOT, [".env"], Path(stage))

    def test_must_find_and_priority_misses_survive_aggregation(self):
        b = self.arm(files=[])
        result = benchmark.evaluate_pair(self.case, self.arm(), b, current_base_sha=self.case["base_sha"])
        self.assertEqual(result["b"]["critical_file_misses"], ["src/MT3SymbolState.mqh"])
        summary = benchmark.summarize_pairs([result])
        self.assertEqual(summary["critical_file_miss_cases"], [self.case["id"]])
        self.assertEqual(summary["pilot_status"], "BLOCKED_CRITICAL_FILE_MISS")

    def test_missing_usage_stays_null_with_reason_and_coverage(self):
        result = benchmark.score_arm(self.case, self.arm(files=[]))
        usage = result["metrics"]["combined_total_tokens"]
        self.assertEqual(usage["value"], None)
        self.assertEqual(usage["coverage"], 0)
        self.assertEqual(result["metrics"]["combined_cost"]["reason"], "not_reported")

    def test_cost_requires_real_price_and_usage_provenance(self):
        with self.assertRaisesRegex(ValueError, "cost_requires"):
            benchmark.score_arm(self.case, self.arm(combined_cost=0))

    def test_task_success_is_binary(self):
        for value in (-1, 2, 0.5, True):
            with self.subTest(value=value), self.assertRaises(ValueError):
                benchmark.score_arm(self.case, self.arm(task_success=value))

    def test_reason_is_fixed_code_not_raw_private_text(self):
        with self.assertRaisesRegex(ValueError, "unsafe_jevgrep_reason"):
            benchmark.score_arm(self.case, self.arm(reason="private trace details"))

    def test_report_keeps_sections_and_kind_coverage(self):
        case_a = self.cases[0]
        case_b = self.cases[-1]
        self.case = case_a
        row_a = benchmark.evaluate_pair(case_a, self.arm(), self.arm(), current_base_sha=case_a["base_sha"])
        self.case = case_b
        row_b = benchmark.evaluate_pair(case_b, self.arm(), self.arm(), current_base_sha=case_b["base_sha"])
        report = benchmark.summarize_pairs([row_a, row_b])
        for section in ("quality", "token", "cost", "time", "context_retrieval",
                        "rework_test_failure", "coverage_missing_data", "limitations"):
            self.assertIn(section, report)
        self.assertEqual(report["by_kind"]["exact_lookup"]["unique_tasks"], 1)
        self.assertEqual(report["by_kind"]["semantic_discovery"]["unique_tasks"], 1)
        self.assertIsNone(report["cost"]["b"]["combined_cost"]["value"])
        self.assertEqual(report["cost"]["b"]["combined_cost"]["coverage"], 0)

    def test_pair_model_effort_mismatch_and_stale_base_excluded(self):
        b = self.arm(sol_effort="high")
        row = benchmark.evaluate_pair(self.case, self.arm(), b, current_base_sha="0" * 40)
        self.assertEqual(row["comparison_status"], "EXCLUDED")
        self.assertIn("sol_effort_mismatch", row["exclusion_reasons"])
        self.assertIn("stale_base_sha", row["exclusion_reasons"])

    def test_duplicate_task_does_not_inflate_summary(self):
        row = benchmark.evaluate_pair(self.case, self.arm(), self.arm(), current_base_sha=self.case["base_sha"])
        with self.assertRaisesRegex(ValueError, "duplicate_jevgrep_task"):
            benchmark.summarize_pairs([row, copy.deepcopy(row)])

    def test_stale_fixture_or_result_is_not_current(self):
        a = self.arm()
        b = self.arm(base_sha="0" * 40)
        row = benchmark.evaluate_pair(self.case, a, b, current_base_sha=self.case["base_sha"])
        self.assertIn("base_sha_mismatch", row["exclusion_reasons"])

    def test_imported_b_requires_fresh_uncached_source_provenance(self):
        sources = ["src/MT3SymbolState.mqh"]
        fingerprint = benchmark.source_fingerprint(ROOT, sources, self.case["base_sha"])
        b = self.arm(cache_bypassed=True, source_sha256=fingerprint, stage_file_count=1)
        row = benchmark.evaluate_pair(self.case, self.arm(), b,
                 current_base_sha=self.case["base_sha"], expected_source_sha256=fingerprint,
                 expected_source_paths=sources)
        self.assertEqual(row["comparison_status"], "COMPARABLE")
        cached = benchmark.evaluate_pair(self.case, self.arm(), dict(b, cache_bypassed=False),
                 current_base_sha=self.case["base_sha"], expected_source_sha256=fingerprint)
        self.assertIn("b_cache_not_bypassed", cached["exclusion_reasons"])
        stale = benchmark.evaluate_pair(self.case, self.arm(), dict(b, source_sha256="0" * 64),
                 current_base_sha=self.case["base_sha"], expected_source_sha256=fingerprint)
        self.assertIn("b_source_fingerprint_mismatch", stale["exclusion_reasons"])
        missing = benchmark.evaluate_pair(self.case, self.arm(), self.arm(),
                 current_base_sha=self.case["base_sha"], expected_source_sha256=fingerprint)
        self.assertEqual(missing["comparison_status"], "EXCLUDED")
        self.assertIn("b_cache_not_bypassed", missing["exclusion_reasons"])

    def test_excluded_critical_miss_still_blocks_pilot(self):
        b = self.arm(files=[], cache_bypassed=False, source_sha256="0" * 64,
                     stage_file_count=1)
        row = benchmark.evaluate_pair(self.case, self.arm(), b,
                    current_base_sha=self.case["base_sha"],
                    expected_source_sha256="1" * 64)
        self.assertEqual(row["comparison_status"], "EXCLUDED")
        self.assertEqual(benchmark.summarize_pairs([row],
                         expected_case_ids=[c["id"] for c in self.cases])["pilot_status"],
                         "BLOCKED_CRITICAL_FILE_MISS")

    def test_imported_files_must_belong_to_approved_search_universe(self):
        b = self.arm(cache_bypassed=True, source_sha256='1' * 64, stage_file_count=1)
        row = benchmark.evaluate_pair(self.case, self.arm(), b,
                     current_base_sha=self.case['base_sha'], expected_source_sha256='1' * 64,
                     expected_source_paths=['src/MT3Config.mqh'])
        self.assertEqual(row['comparison_status'], 'EXCLUDED')
        self.assertIn('b_files_outside_source_allowlist', row['exclusion_reasons'])
        self.assertIn('must_find_outside_source_allowlist', row['exclusion_reasons'])

    def test_imported_source_coverage_is_derived_from_allowlist(self):
        b = self.arm(cache_bypassed=True, source_sha256='1' * 64, stage_file_count=1,
                     source_universe_coverage=1)
        row = benchmark.evaluate_pair(self.case, self.arm(), b,
                     current_base_sha=self.case['base_sha'], expected_source_sha256='1' * 64,
                     expected_source_paths=self.case['must_find_files'])
        expected = len(set(self.case['must_find_files']) & set(self.case['relevant_files'])) / len(self.case['relevant_files'])
        self.assertLess(expected, 1)
        self.assertEqual(row['b']['metrics']['source_universe_coverage']['value'], expected)


if __name__ == "__main__":
    unittest.main()

"""Shadow-only, privacy-bounded Jevgrep repository-discovery experiment.

No call in this module installs a CLI, invokes an agent, or changes EA code.
The A and B agent observations are supplied separately and compared only when
task, base SHA, model and effort agree. Raw CLI output is never returned.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time

from .triage import SENSITIVE


SHA = re.compile(r"[0-9a-f]{40}\Z")
SAFE_ID = re.compile(r"[a-z][a-z0-9_-]{0,79}\Z")
SAFE_SOURCE = re.compile(r"src/[A-Za-z0-9_/-]+\.(?:mq5|mqh)\Z")
OPAQUE = re.compile(r"[A-Za-z0-9_+/=-]{80,}")
SECRET_LITERAL = re.compile(
    r"(?i)(?:api[_-]?key|password|secret|credential|access[_-]?token|private[_-]?key)"
    r"\s*[:=]\s*['\"][^'\"\r\n]{4,}['\"]"
)
SOURCE_SECRET = re.compile(
    r"(?i)(?:-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|"
    r"(?:sk-proj-|gh[pousr]_)[A-Za-z0-9_-]+|"
    r"bearer\s+[A-Za-z0-9._-]{12,}|"
    r"[\w.+-]+@[\w.-]+)"
)
FORBIDDEN_NAMES = re.compile(r"(?i)(?:\.env|credential|secret|private|account|\.pem|\.key)")
KINDS = {"semantic_discovery", "exact_lookup"}
CURRENT_SOL_MODEL = "gpt-6.1-sol"
HISTORICAL_SOL_MODEL = "gpt-6-sol"
CURRENT_SOL_EFFORT = "high"
HISTORICAL_SOL_EFFORT = "xhigh"
COMPARISON_SOL_MODELS = (CURRENT_SOL_MODEL, HISTORICAL_SOL_MODEL)
STATUSES = {"OK", "UNKNOWN", "UNAVAILABLE", "FAIL"}
REASONS = {None, "completed", "not_measured", "not_reported", "live_flag_required",
           "unsupported_environment", "source_allowlist_required", "missing_jg_binary",
           "jg_version_failure", "invalid_jg_version", "jg_timeout", "jg_execution_failure",
           "jg_nonzero_exit", "sensitive_source_content", "source_not_allowlisted",
           "sensitive_source_path", "unsafe_source_file", "unsafe_source_size_or_binary",
           "non_utf8_source", "stage_io_failure", "stale_or_untracked_source", "provider_usage_unavailable",
           "provider_price_or_usage_unavailable", "observation_unavailable",
           "must_find_outside_source_allowlist"}
METRIC_REASONS = REASONS | {"no_successful_file_result", "arm_not_successful",
                            "sol_or_jevgrep_usage_unavailable", "price_unavailable",
                            "usage_unavailable", "not_applicable"}
METRICS = ("sol_input_tokens", "sol_output_tokens", "sol_total_tokens",
           "jevgrep_tokens", "combined_total_tokens", "combined_cost",
           "elapsed_seconds", "additional_searches", "context_retrievals",
           "rework_count", "test_failures", "source_bytes", "context_bytes",
           "unnecessary_files_opened", "source_universe_coverage")


def _safe_path(value: str) -> str:
    if not isinstance(value, str) or not SAFE_SOURCE.fullmatch(value) or ".." in value.split("/"):
        raise ValueError("source_not_allowlisted")
    if FORBIDDEN_NAMES.search(value):
        raise ValueError("sensitive_source_path")
    return value


def _safe_text(value: str) -> None:
    if not isinstance(value, str) or SENSITIVE.search(value) or SECRET_LITERAL.search(value) or OPAQUE.search(value):
        raise ValueError("sensitive_source_content")


def _safe_source_text(value: str) -> None:
    # Source has variable names such as `token=String...` and a literal
    # `Bearer ` prefix; the generic prompt scanner would reject those.
    if SOURCE_SECRET.search(value) or SECRET_LITERAL.search(value) or OPAQUE.search(value):
        raise ValueError("sensitive_source_content")


def validate_case(case: dict, repository_root: Path | None = None) -> dict:
    if not isinstance(case, dict) or set(case) != {
        "id", "kind", "task", "query", "base_sha", "must_find_files", "relevant_files",
        "important_files", "critical_files"}:
        raise ValueError("invalid_jevgrep_case")
    if not SAFE_ID.fullmatch(case["id"]) or case["kind"] not in KINDS:
        raise ValueError("invalid_jevgrep_case")
    for field in ("task", "query"):
        if not isinstance(case[field], str) or not 1 <= len(case[field]) <= 500:
            raise ValueError("invalid_jevgrep_case")
        _safe_text(case[field])
    if not SHA.fullmatch(case["base_sha"]):
        raise ValueError("invalid_jevgrep_base")
    for field in ("must_find_files", "relevant_files", "important_files", "critical_files"):
        paths = case[field]
        if not isinstance(paths, list) or len(paths) != len(set(paths)):
            raise ValueError("invalid_jevgrep_files")
        for path in paths:
            _safe_path(path)
            if repository_root is not None and not (Path(repository_root) / path).is_file():
                raise ValueError("missing_expected_source")
    if not case["must_find_files"] or not case["relevant_files"]:
        raise ValueError("missing_human_ground_truth")
    if not set(case["must_find_files"]) <= set(case["relevant_files"]):
        raise ValueError("must_find_not_relevant")
    if not set(case["critical_files"] + case["important_files"]) <= set(case["must_find_files"]):
        raise ValueError("priority_file_not_required")
    return case


def load_cases(path: str | Path, repository_root: str | Path | None = None) -> list[dict]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict) or set(data) != {"schema_version", "cases"} or data["schema_version"] != 1:
        raise ValueError("invalid_jevgrep_fixture")
    cases = data["cases"]
    if not isinstance(cases, list) or len({c.get("id") for c in cases if isinstance(c, dict)}) != len(cases):
        raise ValueError("duplicate_jevgrep_case")
    return [validate_case(case, Path(repository_root) if repository_root else None) for case in cases]


def _stage(repository_root: Path, source_paths: list[str], stage_root: Path) -> tuple[list[str], int]:
    if not source_paths or len(source_paths) != len(set(source_paths)):
        raise ValueError("empty_or_duplicate_source_allowlist")
    repository_root = repository_root.resolve(strict=True)
    stage_root = stage_root.resolve(strict=True)
    if stage_root == repository_root or stage_root.is_relative_to(repository_root):
        raise ValueError("stage_must_be_outside_repository")
    approved = []
    source_bytes = 0
    for relative in source_paths:
        relative = _safe_path(relative)
        original = repository_root / relative
        if original.is_symlink() or not original.is_file() or not original.resolve().is_relative_to(repository_root):
            raise ValueError("unsafe_source_file")
        raw = original.read_bytes()
        if len(raw) > 2_000_000 or b"\x00" in raw:
            raise ValueError("unsafe_source_size_or_binary")
        try:
            content = raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ValueError("non_utf8_source") from exc
        _safe_source_text(content)
        target = stage_root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
        approved.append(relative)
        source_bytes += len(raw)
    return approved, source_bytes


def _source_digest(stage_root: Path, approved: list[str]) -> str:
    digest = hashlib.sha256()
    for relative in sorted(approved):
        digest.update(relative.encode("utf-8") + b"\x00")
        digest.update((stage_root / relative).read_bytes())
    return digest.hexdigest()


def source_fingerprint(repository_root: str | Path, source_paths: list[str], base_sha: str) -> str:
    """Fingerprint an explicit, safe allowlist at the fixed base for imported B rows."""
    if not isinstance(base_sha, str) or not SHA.fullmatch(base_sha):
        raise ValueError("invalid_jevgrep_base")
    with tempfile.TemporaryDirectory(prefix="workflow-jevgrep-fingerprint-") as temporary:
        stage = Path(temporary)
        approved, _ = _stage(Path(repository_root), source_paths, stage)
        if not _sources_match_base(Path(repository_root), base_sha, approved):
            raise ValueError("stale_or_untracked_source")
        return _source_digest(stage, approved)


def _missing(reason: str) -> dict:
    return {"value": None, "reason": reason, "coverage": 0}


def _known(value: int | float) -> dict:
    return {"value": value, "reason": None, "coverage": 1}


def _result(status: str, reason: str, elapsed: float | None = None) -> dict:
    return {"status": status, "reason": reason, "jg_version": None,
            "found_files": [], "source_bytes": _missing("not_measured"),
            "context_bytes": _missing("not_measured"),
            "source_universe_coverage": _missing("not_measured"),
            "jevgrep_tokens": _missing("provider_usage_unavailable"),
            "jevgrep_cost": _missing("provider_price_or_usage_unavailable"),
            "elapsed_seconds": _known(elapsed) if elapsed is not None else _missing("not_measured"),
            "stage_file_count": 0, "source_sha256": None}


def _cli_run(command: list[str], timeout: float, cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(command, cwd=cwd, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=timeout, check=False)


def _sources_match_base(repository_root: Path, base_sha: str, paths: list[str]) -> bool:
    # A changed source tree would invalidate hand-fixed ground truth and cache
    # freshness, even if its content passed the secret scan.
    try:
        tracked = subprocess.run(["git", "ls-files", "--error-unmatch", "--", *paths],
                                 cwd=repository_root, capture_output=True, timeout=10, check=False)
        if tracked.returncode != 0:
            return False
        diff = subprocess.run(["git", "diff", "--quiet", base_sha, "--", *paths],
                              cwd=repository_root, capture_output=True, timeout=10, check=False)
        return diff.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def _extract_found_files(stdout: str, approved: list[str], stage_root: Path) -> list[str]:
    """Read location records only, never arbitrary source lines or query echoes."""
    found = set()
    allowed = set(approved)
    patterns = (
        re.compile(r'^\s*-\s+"([^"]+)"\s+[—-]'),
        re.compile(r'^Source block "([^"]+)" lines '),
        re.compile(r'^\s*((?:/[^:\r\n]+)?src/[A-Za-z0-9_/.-]+\.(?:mq5|mqh)):\d+(?:\b|$)'),
    )
    for line in stdout.splitlines():
        candidate = next((match.group(1) for pattern in patterns
                          if (match := pattern.match(line))), None)
        if candidate is None:
            continue
        path = Path(candidate)
        if path.is_absolute():
            try:
                candidate = path.resolve().relative_to(stage_root.resolve()).as_posix()
            except ValueError:
                continue
        else:
            candidate = candidate.removeprefix("./")
        if candidate in allowed:
            found.add(candidate)
    return sorted(found)


def run_discovery(case: dict, repository_root: str | Path, *, live: bool = False,
                  jg_executable: str = "jg", source_paths: list[str] | None = None,
                  timeout: float = 90, platform: str | None = None,
                  runner=None) -> dict:
    """Run only B's discovery. The caller must explicitly set live=True.

    `source_paths` is a positive, case-independent allowlist. No repository root
    is ever passed to jg. The command's raw stdout/stderr is discarded.
    """
    validate_case(case, Path(repository_root))
    if not live:
        return _result("UNAVAILABLE", "live_flag_required")
    platform = platform or sys.platform
    if not (platform.startswith("linux") or platform == "darwin"):
        return _result("UNAVAILABLE", "unsupported_environment")
    if source_paths is None:
        return _result("UNAVAILABLE", "source_allowlist_required")
    if not isinstance(timeout, (float, int)) or not math.isfinite(timeout) or timeout <= 0:
        raise ValueError("invalid_timeout")
    if not isinstance(jg_executable, str) or not jg_executable:
        raise ValueError("invalid_jg_executable")
    executable = shutil.which(jg_executable)
    if executable is None:
        return _result("UNAVAILABLE", "missing_jg_binary")
    runner = runner or _cli_run
    start = time.perf_counter()
    with tempfile.TemporaryDirectory(prefix="workflow-jevgrep-") as temporary:
        stage_root = Path(temporary)
        try:
            approved, source_bytes = _stage(Path(repository_root), source_paths, stage_root)
        except OSError:
            return _result("UNAVAILABLE", "stage_io_failure", time.perf_counter() - start)
        except ValueError as exc:
            reason = str(exc)
            return _result("UNAVAILABLE", reason if reason in REASONS else "stage_io_failure",
                           time.perf_counter() - start)
        relevant = set(case["relevant_files"])
        universe_coverage = _known(len(relevant & set(approved)) / len(relevant))
        if not set(case["must_find_files"]) <= set(approved):
            result = _result("UNAVAILABLE", "must_find_outside_source_allowlist",
                             time.perf_counter() - start)
            result["source_universe_coverage"] = universe_coverage
            result["stage_file_count"] = len(approved)
            result["source_bytes"] = _known(source_bytes)
            return result
        if not _sources_match_base(Path(repository_root), case["base_sha"], approved):
            return _result("UNAVAILABLE", "stale_or_untracked_source", time.perf_counter() - start)
        source_digest = _source_digest(stage_root, approved)
        try:
            version_run = runner([executable, "--version"], min(timeout, 10), stage_root)
            if version_run.returncode != 0:
                return _result("UNAVAILABLE", "jg_version_failure", time.perf_counter() - start)
            version = version_run.stdout.strip().splitlines()[0][:80]
            if not re.fullmatch(r"[A-Za-z0-9@/._ +()-]{1,80}", version):
                return _result("UNAVAILABLE", "invalid_jg_version", time.perf_counter() - start)
            # Official CLI `--no-cache` bypasses previously validated scores;
            # old responses must never be credited as this run's discovery.
            completed = runner([executable, case["query"], str(stage_root), "--no-cache"], timeout, stage_root)
        except subprocess.TimeoutExpired:
            return _result("UNAVAILABLE", "jg_timeout", time.perf_counter() - start)
        except (OSError, IndexError):
            return _result("UNAVAILABLE", "jg_execution_failure", time.perf_counter() - start)
        elapsed = time.perf_counter() - start
        if completed.returncode != 0:
            result = _result("FAIL", "jg_nonzero_exit", elapsed)
        else:
            result = _result("OK", "completed", elapsed)
            result["found_files"] = _extract_found_files(completed.stdout, approved, stage_root)
            result["context_bytes"] = _known(len(completed.stdout.encode("utf-8")))
        result["jg_version"] = version
        result["cache_bypassed"] = True
        result["source_bytes"] = _known(source_bytes)
        result["source_universe_coverage"] = universe_coverage
        result["stage_file_count"] = len(approved)
        result["source_sha256"] = source_digest
        return result


def _metric(value, *, integer: bool = True) -> dict:
    if isinstance(value, dict) and set(value) == {"value", "reason", "coverage"}:
        item = value
    elif value is None:
        item = _missing("not_reported")
    else:
        item = _known(value)
    number = item["value"]
    if number is None:
        if item["reason"] not in METRIC_REASONS - {None} or item["coverage"] != 0:
            raise ValueError("missing_metric_requires_reason")
    elif (type(number) not in ((int,) if integer else (int, float)) or
          not math.isfinite(number) or number < 0 or item["reason"] is not None or item["coverage"] != 1):
        raise ValueError("invalid_jevgrep_metric")
    return item


def score_arm(case: dict, arm: dict) -> dict:
    """Score file retrieval and retain missing usage as null plus reason/coverage."""
    validate_case(case)
    if not isinstance(arm, dict) or arm.get("status") not in STATUSES:
        raise ValueError("invalid_jevgrep_arm")
    if arm.get("reason") not in REASONS:
        raise ValueError("unsafe_jevgrep_reason")
    if arm.get("sol_status") not in (None, "OK", "FAIL", "UNAVAILABLE"):
        raise ValueError("invalid_sol_status")
    source_sha = arm.get("source_sha256")
    if source_sha is not None and (not isinstance(source_sha, str) or
                                   not re.fullmatch(r"[0-9a-f]{64}", source_sha)):
        raise ValueError("invalid_source_fingerprint")
    if arm.get("cache_bypassed") not in (None, True, False) or type(arm.get("cache_bypassed")) not in (type(None), bool):
        raise ValueError("invalid_cache_provenance")
    count = arm.get("stage_file_count")
    if count is not None and (type(count) is not int or count < 0):
        raise ValueError("invalid_stage_file_count")
    jg_version = arm.get("jg_version")
    if jg_version is not None and (not isinstance(jg_version, str) or
                                   not re.fullmatch(r"[A-Za-z0-9@/._ +()-]{1,80}", jg_version)):
        raise ValueError("invalid_jg_version")
    files = arm.get("found_files")
    if not isinstance(files, list) or len(files) != len(set(files)):
        raise ValueError("invalid_found_files")
    found = {_safe_path(path) for path in files}
    relevant = set(case["relevant_files"])
    must = set(case["must_find_files"])
    successful = arm["status"] == "OK"
    if not successful and found:
        raise ValueError("failed_arm_claimed_files")
    metrics = {name: _metric(arm.get(name), integer=name not in
               ("elapsed_seconds", "combined_cost", "source_universe_coverage"))
               for name in METRICS}
    if (metrics["source_universe_coverage"]["value"] is not None and
            metrics["source_universe_coverage"]["value"] > 1):
        raise ValueError("invalid_source_universe_coverage")
    if metrics["combined_cost"]["value"] is not None:
        provenance = arm.get("cost_provenance")
        if (not isinstance(provenance, dict) or set(provenance) !=
                {"sol_price_source", "jevgrep_price_source", "usage_source"} or
                any(not isinstance(value, str) or not value.strip() or SENSITIVE.search(value)
                    for value in provenance.values())):
            raise ValueError("cost_requires_price_and_usage_provenance")
    if metrics["sol_input_tokens"]["value"] is not None and metrics["sol_output_tokens"]["value"] is not None:
        expected = metrics["sol_input_tokens"]["value"] + metrics["sol_output_tokens"]["value"]
        if metrics["sol_total_tokens"]["value"] not in (None, expected):
            raise ValueError("inconsistent_sol_usage")
        metrics["sol_total_tokens"] = _known(expected)
    if metrics["sol_total_tokens"]["value"] is not None and metrics["jevgrep_tokens"]["value"] is not None:
        expected = metrics["sol_total_tokens"]["value"] + metrics["jevgrep_tokens"]["value"]
        if metrics["combined_total_tokens"]["value"] not in (None, expected):
            raise ValueError("inconsistent_combined_usage")
        metrics["combined_total_tokens"] = _known(expected)
    else:
        metrics["combined_total_tokens"] = _missing("sol_or_jevgrep_usage_unavailable")
    missing = sorted(must - found) if successful else None
    task_success = _metric(arm.get("task_success")) if successful else _missing("arm_not_successful")
    if task_success["value"] is not None and task_success["value"] not in (0, 1):
        raise ValueError("task_success_must_be_binary")
    return {"status": arm["status"], "reason": arm.get("reason"),
            "sol_status": arm.get("sol_status"),
            "cache_bypassed": arm.get("cache_bypassed"),
            "source_sha256": source_sha, "stage_file_count": count,
            "jg_version": jg_version,
            "found_files": sorted(found), "must_find_misses": missing,
            "important_file_misses": sorted(set(case["important_files"]) - found) if successful else None,
            "critical_file_misses": sorted(set(case["critical_files"]) - found) if successful else None,
            "must_find_recall": _known(len(must & found) / len(must)) if successful else _missing("arm_not_successful"),
            "relevant_file_precision": _known(len(relevant & found) / len(found)) if successful and found else _missing("no_successful_file_result"),
            "relevant_file_recall": _known(len(relevant & found) / len(relevant)) if successful else _missing("arm_not_successful"),
            "task_success": task_success,
            "metrics": metrics}


def evaluate_pair(case: dict, a: dict, b: dict, *, current_base_sha: str,
                  expected_source_sha256: str | None = None,
                  expected_source_paths: list[str] | None = None) -> dict:
    validate_case(case)
    a_score, b_score = score_arm(case, a), score_arm(case, b)
    reasons = []
    if current_base_sha != case["base_sha"]:
        reasons.append("stale_base_sha")
    for field in ("task_id", "base_sha", "sol_model", "sol_effort"):
        if a.get(field) != b.get(field):
            reasons.append(field + "_mismatch")
    if a.get("task_id") != case["id"] or a.get("base_sha") != case["base_sha"]:
        reasons.append("case_identity_mismatch")
    # This reader accepts legacy observations without renaming their model.
    # New live execution is separately restricted to CURRENT_SOL_MODEL.
    model = a.get("sol_model")
    known_model = isinstance(model, str) and model in COMPARISON_SOL_MODELS
    effort = a.get("sol_effort")
    known_effort = ((model == CURRENT_SOL_MODEL and effort == CURRENT_SOL_EFFORT) or
                    (model == HISTORICAL_SOL_MODEL and effort == HISTORICAL_SOL_EFFORT))
    if not known_model or not known_effort:
        reasons.append("invalid_sol_comparison")
    if a_score["status"] != "OK" or b_score["status"] != "OK":
        reasons.append("incomplete_arm")
    for name, score in (("a", a_score), ("b", b_score)):
        if score.get("sol_status") not in (None, "OK"):
            reasons.append(name + "_sol_not_successful")
        if (score["task_success"]["value"] is None or
                score["metrics"]["sol_input_tokens"]["value"] is None or
                score["metrics"]["sol_output_tokens"]["value"] is None):
            reasons.append(name + "_sol_evidence_missing")
    if b_score["status"] == "OK":
        if expected_source_paths is None:
            reasons.append('expected_source_paths_missing')
        else:
            approved = {_safe_path(path) for path in expected_source_paths}
            b_score['metrics']['source_universe_coverage'] = _known(
                len(approved & set(case['relevant_files'])) / len(case['relevant_files']))
            if not set(b_score['found_files']) <= approved:
                reasons.append('b_files_outside_source_allowlist')
            if not set(case['must_find_files']) <= approved:
                reasons.append('must_find_outside_source_allowlist')
        if b_score["cache_bypassed"] is not True:
            reasons.append("b_cache_not_bypassed")
        if expected_source_sha256 is None or not re.fullmatch(r"[0-9a-f]{64}", expected_source_sha256):
            reasons.append("expected_source_fingerprint_missing")
        elif b_score["source_sha256"] != expected_source_sha256:
            reasons.append("b_source_fingerprint_mismatch")
        if b_score["stage_file_count"] is None or b_score["stage_file_count"] < 1:
            reasons.append("b_stage_provenance_missing")
    models_match = model == b.get("sol_model")
    provenance = ("mismatched" if not models_match else "unrecognized" if not known_model
                  else "current" if model == CURRENT_SOL_MODEL else "legacy_historical")
    # Declared observation identity is metadata, not proof of model execution.
    return {"case_id": case["id"], "kind": case["kind"], "base_sha": case["base_sha"],
            "sol_model": model if known_model and models_match else None,
            "sol_effort": effort if known_effort and a.get("sol_effort") == b.get("sol_effort") else None,
            "model_provenance": provenance,
            "comparison_status": "COMPARABLE" if not reasons else "EXCLUDED",
            "exclusion_reasons": sorted(set(reasons)), "a": a_score, "b": b_score}


def summarize_pairs(rows: list[dict], *, expected_case_ids: list[str] | None = None) -> dict:
    if not isinstance(rows, list) or len({row["case_id"] for row in rows}) != len(rows):
        raise ValueError("duplicate_jevgrep_task")
    if any(row.get("kind") not in KINDS or row.get("comparison_status") not in ("COMPARABLE", "EXCLUDED")
           or not isinstance(row.get("a"), dict) or not isinstance(row.get("b"), dict) for row in rows):
        raise ValueError("invalid_jevgrep_result")
    provenance_fields = {"sol_model", "sol_effort", "model_provenance"}
    provenance_kinds = ("current", "legacy_historical", "mismatched", "unrecognized", "not_recorded")
    for row in rows:
        present = provenance_fields.intersection(row)
        if not present:
            continue  # Preserve old rows without inferring a new model identity.
        model, effort, provenance = (row.get(field) for field in
                                      ("sol_model", "sol_effort", "model_provenance"))
        recognized = ((provenance == "current" and model == CURRENT_SOL_MODEL and effort == CURRENT_SOL_EFFORT) or
                      (provenance == "legacy_historical" and model == HISTORICAL_SOL_MODEL and effort == HISTORICAL_SOL_EFFORT))
        rejected = provenance in ("mismatched", "unrecognized") and model is None
        if (present != provenance_fields or not (recognized or rejected) or
                effort not in (None, "high", "xhigh") or
                row["comparison_status"] == "COMPARABLE" and not recognized):
            raise ValueError("invalid_sol_provenance")
    expected = None
    if expected_case_ids is not None:
        if (not isinstance(expected_case_ids, list) or
                any(not isinstance(item, str) or not SAFE_ID.fullmatch(item) for item in expected_case_ids) or
                len(expected_case_ids) != len(set(expected_case_ids)) or
                not {row["case_id"] for row in rows} <= set(expected_case_ids)):
            raise ValueError("invalid_expected_jevgrep_cases")
        expected = set(expected_case_ids)
    missing_case_ids = sorted(expected - {row["case_id"] for row in rows}) if expected is not None else None
    dataset_coverage = ({"value": len(rows) / len(expected) if expected else None,
                         "reason": "empty_expected_dataset" if not expected else
                                   "missing_cases" if missing_case_ids else None,
                         "coverage": len(rows) / len(expected) if expected else 0,
                         "expected_count": len(expected), "observed_count": len(rows)}
                        if expected is not None else
                        {"value": None, "reason": "expected_case_ids_not_provided", "coverage": 0,
                         "expected_count": None, "observed_count": len(rows)})

    def aggregate(items: list[dict]) -> dict:
        valid = [item["value"] for item in items if item["value"] is not None]
        missing_reasons = {}
        for item in items:
            if item["value"] is None:
                missing_reasons[item["reason"]] = missing_reasons.get(item["reason"], 0) + 1
        return {"value": sum(valid) / len(valid) if valid else None,
                "reason": None if len(valid) == len(items) and items else
                          ("no_cases" if not items else "partial_coverage" if valid else "unmeasured"),
                "coverage": len(valid) / len(items) if items else 0,
                "measured_count": len(valid), "missing_reasons": missing_reasons}

    def group(group_rows: list[dict]) -> dict:
        compared = [row for row in group_rows if row["comparison_status"] == "COMPARABLE"]
        arms = {}
        for arm in ("a", "b"):
            records = [row[arm] for row in group_rows]
            metric = lambda name: aggregate([record["metrics"][name] for record in records])
            arms[arm] = {
                "quality": {
                    "task_success": aggregate([record["task_success"] for record in records]),
                    "must_find_file_recall": aggregate([record["must_find_recall"] for record in records]),
                    "relevant_file_precision": aggregate([record["relevant_file_precision"] for record in records]),
                    "relevant_file_recall": aggregate([record["relevant_file_recall"] for record in records]),
                    "unnecessary_files_opened": metric("unnecessary_files_opened"),
                    "important_file_miss_cases": [row["case_id"] for row in group_rows if row[arm]["important_file_misses"]],
                    "critical_file_miss_cases": [row["case_id"] for row in group_rows if row[arm]["critical_file_misses"]],
                },
                "token": {name: metric(name) for name in ("sol_input_tokens", "sol_output_tokens",
                    "sol_total_tokens", "jevgrep_tokens", "combined_total_tokens")},
                "cost": {"combined_cost": metric("combined_cost")},
                "time": {"elapsed_seconds": metric("elapsed_seconds")},
                "context_retrieval": {name: metric(name) for name in
                    ("source_bytes", "context_bytes", "additional_searches", "context_retrievals",
                     "source_universe_coverage")},
                "rework_test_failure": {name: metric(name) for name in ("rework_count", "test_failures")},
                "jg_versions": sorted({record["jg_version"] for record in records
                                       if record["jg_version"] is not None}),
            }
        return {"unique_tasks": len(group_rows), "comparable_pairs": len(compared),
                "model_provenance": {kind: sum(row.get("model_provenance", "not_recorded") == kind
                                               for row in group_rows) for kind in provenance_kinds},
                "excluded_pairs": len(group_rows) - len(compared),
                "excluded_case_reasons": {row["case_id"]: row["exclusion_reasons"] for row in group_rows
                                          if row["comparison_status"] == "EXCLUDED"},
                "a": arms["a"], "b": arms["b"],
                "coverage_missing_data": {"comparison": aggregate([
                    _known(1) if row["comparison_status"] == "COMPARABLE" else _missing("excluded_pair")
                    for row in group_rows])}}

    overall = group(rows)
    comparable = [row for row in rows if row["comparison_status"] == "COMPARABLE"]
    paired_quality = {}
    for name, source in (("task_success", "task_success"),
                         ("must_find_file_recall", "must_find_recall"),
                         ("relevant_file_precision", "relevant_file_precision"),
                         ("relevant_file_recall", "relevant_file_recall")):
        pairs = [(row["a"][source]["value"], row["b"][source]["value"]) for row in comparable]
        observed = [(a, b) for a, b in pairs if a is not None and b is not None]
        paired_quality[name] = {"b_minus_a": sum(b - a for a, b in observed) / len(observed)
                                if observed else None,
                                "coverage": len(observed) / len(pairs) if pairs else 0,
                                "reason": None if observed and len(observed) == len(pairs)
                                else "partial_coverage" if observed else "unmeasured"}
    if overall["b"]["quality"]["critical_file_miss_cases"]:
        pilot_status = "BLOCKED_CRITICAL_FILE_MISS"
    elif any(item["b_minus_a"] is not None and item["b_minus_a"] < 0
             for name, item in paired_quality.items() if name in ("task_success", "must_find_file_recall")):
        pilot_status = "QUALITY_REGRESSION"
    elif expected is not None and (missing_case_ids or len(comparable) < len(expected)):
        pilot_status = "PILOT_INCOMPLETE"
    elif not comparable or paired_quality["task_success"]["b_minus_a"] is None:
        pilot_status = "UNMEASURED"
    else:
        pilot_status = "SHADOW_MEASURED_NOT_ADOPTED"
    return {"experiment": "jevgrep_shadow", "schema_version": 1,
            "model_provenance": overall["model_provenance"],
            "critical_file_miss_cases": overall["b"]["quality"]["critical_file_miss_cases"],
            "important_file_miss_cases": overall["b"]["quality"]["important_file_miss_cases"],
            "quality": {"a": overall["a"]["quality"], "b": overall["b"]["quality"],
                        "paired_b_minus_a": paired_quality},
            "token": {"a": overall["a"]["token"], "b": overall["b"]["token"]},
            "cost": {"a": overall["a"]["cost"], "b": overall["b"]["cost"]},
            "time": {"a": overall["a"]["time"], "b": overall["b"]["time"]},
            "context_retrieval": {"a": overall["a"]["context_retrieval"], "b": overall["b"]["context_retrieval"]},
            "rework_test_failure": {"a": overall["a"]["rework_test_failure"], "b": overall["b"]["rework_test_failure"]},
            "coverage_missing_data": {"unique_tasks": overall["unique_tasks"],
                "comparable_pairs": overall["comparable_pairs"], "excluded_pairs": overall["excluded_pairs"],
                "excluded_case_reasons": overall["excluded_case_reasons"],
                "comparison": overall["coverage_missing_data"]["comparison"],
                "dataset": dataset_coverage, "missing_case_ids": missing_case_ids},
            "jg_versions": overall["b"]["jg_versions"],
            "by_kind": {kind: group([row for row in rows if row["kind"] == kind]) for kind in sorted(KINDS)},
            "limitations": ["shadow_only", "small_curated_fixture", "MQL5_fallback_text_parsing",
                            "no_provider_cost_without_observed_usage_and_prices",
                            "retrieval_does_not_authorize_EA_change_or_review_skip"],
            "pilot_status": pilot_status, "adoption_status": "SHADOW_ONLY"}

#!/usr/bin/env python3
"""Compare offline routing observations with the skill's expected cases.

This script does not select models, contact Jev, or inspect EA runtime data.
Fixture evidence names describe intended inspection order, not completed checks.
"""

import argparse
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ALLOWED_CONTEXT = {
    "task_type", "risk_level", "candidate_count", "test_state",
    "failure_type", "changed_area", "uncertainty_reason",
}
CONTEXT_CATEGORIES = {
    "task_type": {"candidate_ranking", "routing_comparison", "implementation", "debugging", "review"},
    "risk_level": {"low", "medium", "high"},
    "test_state": {"not_run", "passed", "failed", "unknown"},
    "failure_type": {"none", "compiler", "test", "runtime", "environment", "unknown"},
    "changed_area": {"docs", "tests", "skill", "ea_source", "worker", "mixed"},
    "uncertainty_reason": {"semantic_priority", "route_disagreement", "ambiguous_log", "review_triage"},
}
VALID_ROUTES = {
    f"{family}/{level}"
    for family, levels in {
        "Luna": ("low", "medium", "high", "xhigh", "max"),
        "Sol": ("low", "medium", "high", "xhigh", "max", "ultra"),
        "Astra": ("low", "medium", "high", "xhigh", "max", "ultra"),
    }.items()
    for level in levels
}
ALLOWED_OBSERVATION = {
    "id", "default_route", "actual_route", "shadow_route", "jev", "evidence",
    "sent_context", "shadow_confidence", "shadow_reason", "shadow_outcome",
}
SENSITIVE = re.compile(
    r"(?i)(api[_ -]?key|password|credential|secret|token|bearer|account|"
    r"chat[_ -]?history|raw[_ -]?log|source[_ -]?code|prompt|"
    r"(?:sk-|gh[pousr]_)[A-Za-z0-9_-]{8,}|@|-----BEGIN)"
)


def read_cases(path):
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("version") != 1 or not isinstance(data.get("cases"), list):
        raise ValueError("expected version 1 and a cases array")
    cases = {item["id"]: item for item in data["cases"]}
    if len(cases) != len(data["cases"]):
        raise ValueError("duplicate case id")
    return cases


def check_context(context):
    if context is None:
        return None
    if not isinstance(context, dict) or set(context) - ALLOWED_CONTEXT:
        return "Jev context has non-allowlisted fields"
    for key, value in context.items():
        if key == "candidate_count":
            if not isinstance(value, int) or isinstance(value, bool) or not 0 <= value <= 10000:
                return "Jev context has an unsupported candidate count"
        elif not isinstance(value, str) or value not in CONTEXT_CATEGORIES[key] or SENSITIVE.search(value):
            return "Jev context has an unsupported category or sensitive text"
    return None


def evaluate(expected, observed):
    errors = []
    if not set("ABCDEFGHIJ").issubset(expected):
        errors.append("missing required A-J expectations")
    if set(expected) != set(observed):
        errors.append("case ids differ between expectations and observations")

    for case_id in sorted(set(expected) & set(observed)):
        rule = expected[case_id]["expected"]
        item = observed[case_id]
        if set(item) - ALLOWED_OBSERVATION:
            errors.append(f"{case_id}: observation has unexpected fields")
        jev = item.get("jev", {})
        actual = item.get("actual_route")
        default = item.get("default_route")
        shadow = item.get("shadow_route")
        evidence = item.get("evidence", [])
        if default not in rule["routes"]:
            errors.append(f"{case_id}: default route is outside expected lanes")
        if default not in VALID_ROUTES or (shadow is not None and shadow not in VALID_ROUTES):
            errors.append(f"{case_id}: unknown model or reasoning level")
        if actual != default:
            errors.append(f"{case_id}: actual route changed from default")
        if (jev.get("attempts"), jev.get("used"), jev.get("status")) != (
            rule["jev_attempts"], rule["jev_used"], rule["jev_status"]
        ):
            errors.append(f"{case_id}: Jev call/use/status differs")
        if not isinstance(evidence, list) or not evidence or evidence[0] != rule["first_evidence"]:
            errors.append(f"{case_id}: deterministic evidence was not first")
        if rule["shadow"] == "none" and shadow is not None:
            errors.append(f"{case_id}: unexpected shadow route")
        if rule["shadow"] == "different":
            if not shadow or shadow == default or jev.get("status") != "shadow":
                errors.append(f"{case_id}: missing distinct shadow recommendation")
            confidence = item.get("shadow_confidence")
            if not isinstance(confidence, (int, float)) or not 0 <= confidence <= 1:
                errors.append(f"{case_id}: invalid shadow confidence")
            if not item.get("shadow_reason") or item.get("shadow_outcome") != "not_applied":
                errors.append(f"{case_id}: shadow result lacks reason or non-application")
        context = item.get("sent_context")
        context_error = check_context(context)
        if context_error:
            errors.append(f"{case_id}: {context_error}")
        if jev.get("used") and context is None:
            errors.append(f"{case_id}: successful Jev judgment lacks a bounded context record")
        if jev.get("attempts") == 0 and context is not None:
            errors.append(f"{case_id}: context recorded without a Jev attempt")
    return errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--observed", type=Path, default=ROOT / "fixtures/routing_dry_run.json")
    args = parser.parse_args()
    expected = read_cases(ROOT / "fixtures/routing_cases.json")
    observed = read_cases(args.observed)
    errors = evaluate(expected, observed)
    if errors:
        for error in errors:
            print(f"FAIL {error}")
        raise SystemExit(1)
    print(f"PASS {len(expected)} offline routing cases (no Jev/API calls)")


if __name__ == "__main__":
    main()

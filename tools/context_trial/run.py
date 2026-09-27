"""Usage: python -B -m tools.context_trial.run --out <local-run-dir> [--live-jev] [--replay]."""
import argparse
from collections import Counter
import dataclasses
import json
from pathlib import Path
import subprocess
from .core import JevClient, classify, audit, selected, UNKNOWN
from .corpus import make_corpus
from .replay import CodexRunner, replay_pair


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--revision", default="f504c3988e5715baaf14647b4e5109e6c67c4222")
    parser.add_argument("--live-jev", action="store_true")
    parser.add_argument("--bypass-jev", action="store_true")
    parser.add_argument("--replay", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    branch = subprocess.check_output(["git", "branch", "--show-current"], cwd=root, text=True).strip()
    if branch != "trial/jev-context-compaction":
        raise SystemExit("Run only in the explicitly isolated trial branch")
    if args.out.exists():
        raise SystemExit("Output must be a new directory; preserve earlier trial results")
    args.out.mkdir(parents=True)
    corpus = make_corpus(root, args.revision)
    # Frozen original entries are retained locally; no session logs or credentials.
    write_json(args.out / "originals.json", [{**c, "entries": [dataclasses.asdict(e) for e in c["entries"]]} for c in corpus])
    results = []
    for task in corpus:
        shadow = classify(task["entries"], task["goal"], JevClient() if args.live_jev else None, bypass=args.bypass_jev)
        checked = audit(task["entries"], shadow, task["audit_labels"])
        record = {"task": task["id"], "type": task["type"], "model": task["model"], "effort": task["effort"],
                  "corpus_sha256": task["corpus_sha256"], "shadow": shadow, "audit": checked,
                  "classification_counts": dict(Counter(r["class"] for r in shadow["entries"])),
                  "initial_context_utf8_bytes": sum(len(e.text.encode()) for e in task["entries"]),
                  "retained_context_utf8_bytes": sum(len(e.text.encode()) for e in selected(task["entries"], shadow)),
                  "replay": "NOT_RUN"}
        results.append(record)
        write_json(args.out / "results.json", results)
        print(json.dumps({k: record[k] for k in ["task", "classification_counts", "audit"]}), flush=True)
    # All tasks must pass audit before ANY replay, and at least one live decision
    # must exist. A bypass/offline run cannot be reported as Jev-filtered A/B.
    ready = all(r["audit"]["replay_allowed"] for r in results) and any(
        e["reason"] == "jev_shadow" for r in results for e in r["shadow"]["entries"])
    if args.replay and ready:
        runner = CodexRunner(root, args.out / "response-schema.json")
        for task, record in zip(corpus, results):
            print(f"Replay {task['id']} starting", flush=True)
            record["replay"] = replay_pair(task, record["shadow"], record["audit"], runner)
            write_json(args.out / "results.json", results)
            print(json.dumps({"task": task["id"], "arms": {a: {k: v[k] for k in
                ["root_total_tokens", "total_llm_tokens_with_jev", "wall_seconds_with_filter", "final_correctness", "archive_restore_count"]}
                for a,v in record["replay"]["arms"].items()}}), flush=True)
    print("Trial recorded. No adoption decision is inferred from byte reduction.", flush=True)


if __name__ == "__main__":
    main()

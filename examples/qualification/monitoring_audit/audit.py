"""Freeze an episode audit, prepare adjudication, assess and review its JSON records."""

from __future__ import annotations

import argparse
from pathlib import Path

from nisayon.engine.io import decode_json, digest, write_json
from nisayon.qualification import (
    assess_monitoring_audit,
    freeze_monitoring_audit,
    monitoring_audit_panel,
)


def read(path):
    with Path(path).open("rb") as stream:
        data = stream.read(16 * 1024 * 1024 + 1)
    if len(data) > 16 * 1024 * 1024:
        raise ValueError("Audit JSON exceeds the 16 MiB example-reader bound")
    return decode_json(data)


def example(root):
    """Constructed software exercise; outcomes are authored and already exposed."""
    root.mkdir(parents=True, exist_ok=False)
    frame, truth = [], {}
    for decision, count in (
        ("accepted", 80),
        ("rejected", 16),
        ("abstained", 4),
        ("unanswered", 4),
    ):
        for i in range(count):
            episode = f"episode-{len(frame):04}"
            frame.append(
                {
                    "episode_id": episode,
                    "task_id": "constructed-software-control",
                    "session_id": "one-authored-session",
                    "execution_sha256": digest(["constructed episode witness", episode]),
                    "judge_input_sha256": digest(["constructed evaluator input", episode]),
                    "decision": decision,
                }
            )
            # Fixed before selection, solely to exercise the software.
            truth[episode] = {
                "episode_id": episode,
                "outcome": "failure" if i % 4 == 0 else "success",
            }
    bindings = {
        key + "_sha256": digest(["constructed protocol", key])
        for key in (
            "population",
            "policy",
            "runtime",
            "evaluator",
            "input_protocol",
            "reference_protocol",
        )
    }
    sizes = {"accepted": 16, "rejected": 8, "abstained": 2, "unanswered": 2}
    write_json(root / "frame.json", frame)
    write_json(root / "bindings.json", bindings)
    write_json(root / "sample-sizes.json", sizes)
    write_json(root / "constructed-truth.json", truth)
    plan = freeze_monitoring_audit(
        frame, bindings=bindings, sample_sizes=sizes, output=root / "plan.json"
    )
    write_json(root / "panel.json", monitoring_audit_panel(plan))
    labels = [
        {
            "audit_sha256": plan["sha256"],
            "episode_id": row["episode_id"],
            "outcome": truth[row["episode_id"]]["outcome"],
            "reference_sha256": digest(truth[row["episode_id"]]),
        }
        for row in plan["selected"]
    ]
    write_json(root / "adjudications.json", labels)
    write_json(root / "report.json", assess_monitoring_audit(plan, labels))
    write_json(
        root / "scope.json",
        {
            "status": "constructed_software_example",
            "labels": "Authored, exposed before sampling; not owner or human adjudication",
            "physical_executions": 0,
            "model_inferences": 0,
            "human_review_cost": None,
            "complete_cost": None,
            "deployment_decision": "unresolved",
        },
    )
    return review(root)


def review(root):
    plan, labels, expected = (
        read(root / name) for name in ("plan.json", "adjudications.json", "report.json")
    )
    result = assess_monitoring_audit(plan, labels)
    if digest(result) != digest(expected):
        raise ValueError("Saved assessment differs from reconstruction")
    if digest(monitoring_audit_panel(plan)) != digest(read(root / "panel.json")):
        raise ValueError("Saved panel differs from reconstruction")
    return {
        "audit_sha256": plan["sha256"],
        "review": "recomputed",
        "coverage": result["coverage"],
        "deployment_decision": result["deployment_decision"],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("plan")
    for name in ("frame", "bindings", "sizes", "out"):
        p.add_argument("--" + name, type=Path, required=True)
    p.add_argument("--confidence", type=float, default=0.95)
    for name in ("panel", "assess"):
        p = sub.add_parser(name)
        p.add_argument("--plan", type=Path, required=True)
        p.add_argument("--out", type=Path, required=True)
        if name == "assess":
            p.add_argument("--labels", type=Path, required=True)
    p = sub.add_parser("example")
    p.add_argument("--out", type=Path, required=True)
    p = sub.add_parser("review")
    p.add_argument("directory", type=Path)
    args = parser.parse_args()
    if args.command == "plan":
        result = freeze_monitoring_audit(
            read(args.frame),
            bindings=read(args.bindings),
            sample_sizes=read(args.sizes),
            output=args.out,
            confidence=args.confidence,
        )
        print({"audit_sha256": result["sha256"], "assigned": len(result["selected"])})
    elif args.command == "panel":
        write_json(args.out, monitoring_audit_panel(read(args.plan)))
    elif args.command == "assess":
        write_json(args.out, assess_monitoring_audit(read(args.plan), read(args.labels)))
    elif args.command == "example":
        print(example(args.out))
    else:
        print(review(args.directory))


if __name__ == "__main__":
    main()

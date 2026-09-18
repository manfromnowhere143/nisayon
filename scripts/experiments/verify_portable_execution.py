"""Check a copied real store and labelled byte/identity corruption controls."""

from __future__ import annotations

import argparse
import copy
import json
import shutil
import tempfile
from pathlib import Path

from nisayon.engine.history import verify_history
from nisayon.engine.io import digest, file_digest, write_json
from nisayon.engine.store import verify_execution
from nisayon.evaluation import evaluate_bundle


def outcome_projection(decision: dict) -> dict:
    """Compare outcomes without machine-local locators or evaluation duration."""
    confirmation = decision.get("confirmation") or {}
    return {
        "case_id": decision["case_id"],
        "decision": decision["decision"],
        "obligation": decision.get("obligation"),
        "reasons": decision["reasons"],
        "confirmation": {
            key: confirmation.get(key)
            for key in (
                "protocol",
                "candidate",
                "fresh_condition_ids",
                "reproduction_condition_ids",
                "consumed_condition_ids",
                "pairs",
                "summary",
            )
        },
        "runs": {
            run_id: {
                key: run[key]
                for key in (
                    "role",
                    "condition_id",
                    "process",
                    "measurement",
                    "outcome",
                    "progress",
                    "constraints",
                    "timing",
                    "metrics",
                    "identity",
                    "trace_digest",
                )
            }
            for run_id, run in decision["runs"].items()
        },
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--expected-decision", type=Path)
    args = parser.parse_args()
    args.root = args.root.resolve(strict=True)
    if args.output.resolve().is_relative_to(args.root):
        parser.error("Write the portability report outside the immutable source store")
    bundle = json.loads((args.root / "bundle.json").read_text())
    result = {
        "schema": "nisayon.portable-execution-check.v1",
        "evidence_origin": "artifact_verification_and_deliberately_tampered_copies",
        "source_bundle_sha256": file_digest(args.root / "bundle.json"),
        "source_artifact_manifest": bundle["artifact_manifest"],
        "controls": [],
    }
    with tempfile.TemporaryDirectory(prefix="nisayon-store-copy-") as temp:
        copied = Path(temp) / "store"
        shutil.copytree(args.root, copied)
        result["copied_store"] = verify_execution(bundle, copied)
        history = verify_history(copied, bundle.get("history", []))
        decision = evaluate_bundle(copied / "bundle.json", artifact_root=copied, history=history)
        result["copied_evaluation"] = decision["decision"]
        result["copied_history"] = bundle.get("history", [])
        result["outcome_projection_sha256"] = digest(outcome_projection(decision))
        if args.expected_decision:
            expected = json.loads(args.expected_decision.read_text())
            result["expected_decision_sha256"] = file_digest(args.expected_decision)
            result["expected_outcome_projection_sha256"] = digest(outcome_projection(expected))
            result["same_retained_outcomes"] = (
                result["outcome_projection_sha256"] == result["expected_outcome_projection_sha256"]
            )

        def must_reject(name, changed):
            try:
                verify_execution(changed, copied)
            except (ValueError, KeyError, OSError) as error:
                result["controls"].append({"name": name, "rejected": True, "reason": str(error)})
            else:
                result["controls"].append({"name": name, "rejected": False})

        artifact_name = next(
            a["path"] for a in bundle["runs"][0]["artifacts"] if a["path"].endswith(".jsonl.gz")
        )
        artifact = copied / artifact_name
        with artifact.open("ab") as stream:
            stream.write(b"tampered")
        must_reject("altered_raw_trace", bundle)
        artifact.unlink()
        must_reject("missing_raw_trace", bundle)
        shutil.copyfile(args.root / artifact_name, artifact)
        changed = copy.deepcopy(bundle)
        changed["runs"][0]["invocation_id"] = "wrong-invocation"
        must_reject("unbound_invocation", changed)
        changed = copy.deepcopy(bundle)
        changed["runs"][0]["configuration"]["deployment"]["transport_gripper_sign"] *= -1
        must_reject("changed_configuration", changed)
        changed = copy.deepcopy(bundle)
        changed["runs"] = changed["runs"][1:]
        must_reject("dropped_assigned_run", changed)
        if history:
            target = history[-1]
            original = target.read_bytes()
            target.write_bytes(original + b"tampered")
            must_reject("altered_confirmation_history", bundle)
            target.unlink()
            must_reject("missing_confirmation_history", bundle)
            target.write_bytes(original)
        result["copy_restored"] = verify_execution(bundle, copied)
    result["source_bundle_unchanged"] = (
        file_digest(args.root / "bundle.json") == result["source_bundle_sha256"]
    )
    result["all_controls_rejected"] = all(c["rejected"] for c in result["controls"])
    write_json(args.output, result)
    print(json.dumps(result, indent=2))
    if not (
        result["all_controls_rejected"]
        and result["source_bundle_unchanged"]
        and result.get("same_retained_outcomes", True)
    ):
        raise SystemExit(1)


if __name__ == "__main__":
    main()

"""Reconstruct source-bound review and prospective reuse plans; no native execution."""

import argparse
import importlib.util
import json
import shutil
import time
from pathlib import Path

from nisayon.engine.io import digest, file_digest, write_json
from nisayon.qualification import DependencyModel, EvidenceState, plan_applicability, record_check

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[2]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


scorer = load("transition_scorer", ROOT / "score.py")
selector = load(
    "retained_native_selector", REPO / "examples/qualification/applicability/native_selector.py"
)


def definition(root):
    kinds = {
        "code": "code",
        "runtime": "runtime",
        "procedure": "protocol",
        "diagnostics": "data",
        "confirmation_inputs": "data",
        "scoring": "scoring",
        "population": "population",
        "review_context": "other",
    }
    deps = {
        "observe": ["code", "runtime", "procedure", "diagnostics"],
        "score": ["observe", "scoring"],
        "confirm": ["code", "runtime", "procedure", "confirmation_inputs", "scoring", "population"],
        "review": ["score", "confirm", "review_context"],
    }
    data = {
        "schema": "nisayon.qualification.dependencies.v1",
        "id": "fsdp_source_transition",
        "scope": "Bounded CPU loader proof; prospective new decisions require fresh confirmation",
        "inputs": {k: {"kind": v, "description": k} for k, v in kinds.items()},
        "checks": {
            k: {
                "kind": v,
                "depends_on": deps[k],
                "refresh": "always" if k == "confirm" else "on_change",
            }
            for k, v in {
                "observe": "observation",
                "score": "analysis",
                "confirm": "confirmation",
                "review": "review",
            }.items()
        },
        "decisions": {
            "loader_contract": {"depends_on": ["review"], "description": "CPU loader contract only"}
        },
        "review": None,
    }
    model = DependencyModel.from_dict(data)
    review = {
        "schema": "nisayon.qualification.dependency_review.v1",
        "definition_sha256": model.definition_sha256,
        "reviewer": "source-bound development review",
        "coverage": "reviewed_for_declared_scope",
        "statement": "Reviewed loader function, frozen probe/scorer and retained runtime. Not independent owner review. Native observations remain historical; full integration and GPU stages unrun.",
    }
    write_json(root / "model-review.json", review)
    data["review"] = {
        "definition_sha256": model.definition_sha256,
        "reviewer": review["reviewer"],
        "artifact": {
            "path": "model-review.json",
            "sha256": file_digest(root / "model-review.json"),
        },
    }
    return DependencyModel.from_dict(data)


def identities(source):
    protocol = json.loads((ROOT / "protocol.json").read_text())
    return {
        "code": file_digest(source),
        "runtime": file_digest(ROOT / "environment-lock.txt"),
        "procedure": file_digest(ROOT / "probe.py"),
        "scoring": file_digest(ROOT / "score.py"),
        "diagnostics": digest(protocol["development"]),
        "confirmation_inputs": digest(protocol["confirmation"]),
        "population": digest("Finite CPU/Gloo toy models; no deployment population"),
        "review_context": digest(
            {
                "pr_head": "8c5efdca48fe03796171004c07a9c03461bfdbd2",
                "fork_head": "8023c5ff621e07a3f8e8a25baf496de728f89e8e",
                "upstream": "bd0703e3390ebb2b4eb1db5a0f1283f8edbc6091",
            }
        ),
    }


def prior(root, model, name, source, native):
    inputs = identities(source)
    native_dir = ROOT / "runs" / native
    result = scorer.score(native_dir, 20, inputs["code"], inputs["procedure"])
    execution = json.loads((native_dir / "execution.json").read_text())
    if execution["exit_code"] != 0 or execution["budget_stop"] or result["unresolved"]:
        raise ValueError("Cannot admit incomplete development execution")
    directory = root / name
    directory.mkdir()
    # Preserve actual producer bytes as text inside a source-bound local receipt.
    artifact = {
        "native_execution": execution,
        "producer_files": {
            f"rank-{rank}.json": (native_dir / f"rank-{rank}.json").read_text() for rank in (0, 1)
        },
    }
    write_json(directory / "observation.json", artifact)
    write_json(directory / "score.json", result)
    state = EvidenceState.from_dict(
        {
            "schema": "nisayon.qualification.evidence_state.v1",
            "model_sha256": model.sha256,
            "inputs": inputs,
            "checks": {},
        }
    )
    for check, filename in (("observe", "observation.json"), ("score", "score.json")):
        state = record_check(model, state, check, evidence_root=root, artifact=f"{name}/{filename}")
    write_json(directory / "state.json", state.record())
    return state


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--out", type=Path, default=ROOT / "applicability")
    root = parser.parse_args().out
    root.mkdir(exist_ok=False)
    started = time.perf_counter()
    model = definition(root)
    write_json(root / "model.json", model.record())
    base_source = ROOT / "sources/current-fsdp_utils.py.txt"
    candidate_source = ROOT / "candidate/src/accelerate/utils/fsdp_utils.py"
    base = prior(root, model, "base", base_source, "base-development-ipv4")
    candidate = prior(root, model, "candidate", candidate_source, "candidate-development")
    setup_seconds = time.perf_counter() - started
    changed_context = {
        **identities(candidate_source),
        "review_context": digest("description-only review refresh"),
    }
    cells = [
        ("unchanged_base", base, identities(base_source)),
        ("changed_loader", base, identities(candidate_source)),
        ("description_only", candidate, changed_context),
    ]
    records = []
    for name, old, proposed in cells:
        start = time.perf_counter()
        plan = plan_applicability(model, old, proposed, evidence_root=root)
        sdk_seconds = time.perf_counter() - start
        start = time.perf_counter()
        previous = old.record()
        available = {
            k
            for k, r in previous["checks"].items()
            if file_digest(root / r["artifact"]["path"]) == r["artifact"]["sha256"]
        }
        native = selector.required(previous["inputs"], proposed, available)
        native_seconds = time.perf_counter() - start
        choices = {k: v["action"] for k, v in plan["checks"].items()}
        assert plan["status"] == "planned" and choices == native
        write_json(root / f"{name}.json", plan)
        records.append(
            {
                "case": name,
                "sdk": choices,
                "native": native,
                "selection_equivalent": True,
                "sdk_plan_seconds": sdk_seconds,
                "native_hash_check_and_plan_seconds": native_seconds,
                "execution": "prospective plan only; no new native stages run by this reader",
                "decision": "unresolved until required fresh confirmation/review",
                "historical_development_decision": json.loads(
                    (
                        root
                        / ("candidate" if name == "description_only" else "base")
                        / "score.json"
                    ).read_text()
                )["status"],
            }
        )
    unknown = plan_applicability(
        model, candidate, {**identities(candidate_source), "code": None}, evidence_root=root
    )
    assert unknown["status"] == "unresolved" and not unknown["automatic_acceptance"]
    write_json(root / "unknown-code.json", unknown)
    tampered = root / "tampered-control"
    shutil.copytree(root / "candidate", tampered)
    original = candidate.record()
    for receipt in original["checks"].values():
        receipt["artifact"]["path"] = receipt["artifact"]["path"].replace(
            "candidate/", "tampered-control/"
        )
    with (tampered / "observation.json").open("ab") as stream:
        stream.write(b" ")
    adverse = plan_applicability(
        model, EvidenceState.from_dict(original), identities(candidate_source), evidence_root=root
    )
    assert adverse["checks"]["observe"]["action"] == adverse["checks"]["score"]["action"] == "run"
    write_json(root / "tampered-observation.json", adverse)
    result = {
        "setup_and_native_readback_seconds": setup_seconds,
        "cells": records,
        "unknown_refused": True,
        "tampered_observation_rechecks": True,
        "confirmation": "Always fresh for a new decision; no confirmation receipt was manufactured by this reader",
        "limits": "Equal plans, not a new end-to-end or human-review cost benchmark. Native wall costs are retained separately; no advantage claim.",
    }
    write_json(root / "comparison.json", result)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()

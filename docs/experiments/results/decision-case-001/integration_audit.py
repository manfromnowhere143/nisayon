"""Bind the combined DC01 readback to retained bytes and evaluation's named result."""

import argparse
import ast
import gzip
import importlib.metadata
import json
import subprocess
from pathlib import Path

from nisayon.engine.io import file_digest, write_json

RESULTS = Path("docs/experiments/results/decision-case-001")
EVALUATION = Path("docs/evaluation/results/decision-case-001")
ARTIFACTS = Path("artifacts/engine-integration-001/decision-case-001")
FULL_CHECK_SOURCE = "1375e10886ec5f4021b2d341c3f53ea95d52e889"


def read(path):
    return json.loads(path.read_text())


def git(*args):
    return subprocess.check_output(["git", *args], text=True).strip()


def scientific_pair(pair):
    result = {k: pair[k] for k in ("label", "state", "reading", "metric", "diagnostic")}
    for side in ("first", "second"):
        result[side] = {k: v for k, v in pair[side].items() if k not in ("execution_dir", "checks")}
    result["checks"] = {
        side: [(c["check"], c["status"]) for c in pair[side]["checks"]]
        for side in ("first", "second", "binding")
    }
    result["engine_audit"] = pair["engine_audit"]
    return result


def functions(source):
    return {
        node.name: ast.dump(node, include_attributes=False)
        for node in ast.parse(source).body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scoring", type=Path, required=True)
    parser.add_argument("--controls", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    location = read(RESULTS / "retained-location.json")
    root = Path(location["root"])
    for item in location["files"]:
        path = root / item["path"]
        assert path.stat().st_size == item["bytes"], path
        assert file_digest(path) == item["sha256"], path
    assert (
        gzip.decompress((RESULTS / "execution-bundle.json.gz").read_bytes())
        == (root / "execution/bundle.json").read_bytes()
    )

    plan = read(EVALUATION / "plan.v2.json")
    bindings = plan["bindings"]
    for name in ("scorer", "controls_generator", "original_plan"):
        binding = bindings[name]
        assert file_digest(Path(binding["path"])) == binding["sha256"], name
    for path, digest in bindings["execution_lane_files_at_bound_commit"].items():
        assert file_digest(Path(path)) == digest, path
    for path, digest in bindings["installed_sources"].items():
        distribution = importlib.metadata.distribution(path.split("/", 1)[0])
        assert file_digest(Path(distribution.locate_file(path))) == digest, path

    score = read(args.scoring / "pair-scores.json")
    owner = read(EVALUATION / "adjudication-001/pair-scores.json")
    assert (
        score["plan"]["sha256"]
        == owner["plan"]["sha256"]
        == file_digest(EVALUATION / "plan.v2.json")
    )
    assert score["scorer_sha256"] == owner["scorer_sha256"] == bindings["scorer"]["sha256"]
    assert score["aggregate"] == owner["aggregate"]
    assert list(map(scientific_pair, score["pairs"])) == list(map(scientific_pair, owner["pairs"]))
    assert score["executions_recorded"] == 6
    assert score["aggregate"]["counts"] == {"valid": 3, "invalid": 0, "unresolved": 0, "missing": 0}
    assert all(pair["reading"] == "E1" for pair in score["pairs"])
    controls = read(args.controls / "controls.json")
    assert controls["controls"] == controls["agreeing"] == 46
    assert controls["scorer_sha256"] == score["scorer_sha256"]
    assert controls["generator_sha256"] == bindings["controls_generator"]["sha256"]

    machinery = "src/nisayon/evaluation/first_case.py"
    old = functions(git("show", f"{FULL_CHECK_SOURCE}:{machinery}"))
    current = functions(Path(machinery).read_text())
    unchanged_helpers = (
        "_verify_raw_artifacts",
        "_verify_raw_trace",
        "producer_digest",
        "read_document",
    )
    for name in unchanged_helpers:
        assert old[name] == current[name], name
    source_changes = git(
        "diff",
        "--name-only",
        FULL_CHECK_SOURCE,
        "HEAD",
        "--",
        "src",
        "tests",
        "scripts",
        "pyproject.toml",
        "uv.lock",
        "Makefile",
    ).splitlines()
    result = {
        "checked_head": git("rev-parse", "HEAD"),
        "working_changes": git("status", "--porcelain").splitlines(),
        "execution_source": location["source_commit"],
        "retained_files_verified": len(location["files"]),
        "retained_bytes_verified": sum(item["bytes"] for item in location["files"]),
        "committed_compact_bundle_equals_raw_store": True,
        "frozen_plan_and_implementation_bindings_verified": True,
        "installed_source_bindings_verified": True,
        "evaluation_result_commit": "c5e4bf02141cfe3c1157bc79411a6c7931de4425",
        "independent_scoring_matches_owner": True,
        "pair_states": score["aggregate"],
        "controls": {
            "total": 46,
            "passed": 46,
            "sha256": file_digest(args.controls / "controls.json"),
        },
        "old_full_check_source": FULL_CHECK_SOURCE,
        "application_changes_since_old_full_check": source_changes,
        "first_case_at_plan_binding_sha256": bindings["evaluation_machinery"][machinery],
        "first_case_at_readback_sha256": file_digest(Path(machinery)),
        "unchanged_raw_verification_function_asts": list(unchanged_helpers),
        "scope": "Integrity and named-result readback; no physics, outcome change, custody or product-value claim. Later application changes require their own validation.",
    }
    write_json(args.out, result)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()

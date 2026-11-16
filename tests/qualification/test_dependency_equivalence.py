"""Finite differential checks of incremental execution, not robot-performance trials."""

import copy
import json
from pathlib import Path

import pytest

from nisayon.engine.io import file_digest, write_json
from nisayon.qualification import (
    DependencyModel,
    EvidenceState,
    execute_checks,
    export_checks,
    import_check_bundle,
    inspect_checks,
)

EDGES = [(source, target) for source in range(4) for target in range(source + 1, 4)]
KINDS = {
    "left": "data",
    "right": "data",
    "code": "code",
    "runtime": "runtime",
    "scoring": "scoring",
    "population": "population",
    "notes": "other",
    "procedure": "protocol",
}
CONFIRM_INPUTS = ("left", "right", "code", "runtime", "population")


def reference(mask, values):
    """Recompute the mathematical example without any engine graph/receipt helper."""

    def value(index):
        direct = (values["left" if index % 2 == 0 else "right"], values["code"], values["runtime"])
        predecessors = [
            value(source)
            for bit, (source, target) in enumerate(EDGES)
            if target == index and mask & (1 << bit)
        ]
        if any(item is None for item in (*direct, *predecessors)):
            return None
        return (index + 1) * direct[0] + direct[1] + direct[2] + sum(predecessors)

    computed = {f"n{index}": value(index) for index in range(4)}
    results = {key: {"value": result} for key, result in computed.items() if result is not None}
    if all(values[key] is not None for key in CONFIRM_INPUTS):
        results["confirm"] = {"value": sum(values[key] for key in CONFIRM_INPUTS)}
    if len(results) == 5 and values["scoring"] is not None:
        total = sum(row["value"] for row in results.values())
        results["review"] = {
            "value": total,
            "decision": "supported" if total <= values["scoring"] else "rejected",
        }
    return results


def assert_contract(report, artifacts, expected, expected_actions, *, complete):
    assert artifacts == expected, "Incremental results differ from fresh reference computation"
    assert {row["check"]: row["action"] for row in report["attempts"]} == expected_actions, (
        "Declared invalidation, mandatory confirmation or useful reuse changed"
    )
    assert report["status"] == ("completed" if complete else "unresolved")
    assert report["automatic_acceptance"] is False
    assert report["deployment_decision"] == "unresolved"


class Example:
    def __init__(self, directory, mask):
        self.mask = mask
        self.root = directory / "evidence"
        self.root.mkdir()
        self.values = {
            "left": 2,
            "right": 5,
            "code": 7,
            "runtime": 11,
            "scoring": 1_000_000,
            "population": 17,
            "notes": 19,
        }
        self.paths = {key: directory / f"{key}.json" for key in self.values}
        self.inputs = dict(self.paths)
        for key, value in self.values.items():
            self.set(key, value)
        self.previous = None
        self.previous_values = None
        checks, functions = {}, []
        for index in range(4):
            key = f"n{index}"
            data = "left" if index % 2 == 0 else "right"
            predecessors = [
                f"n{source}"
                for bit, (source, target) in enumerate(EDGES)
                if target == index and mask & (1 << bit)
            ]
            checks[key] = {
                "kind": "observation" if index < 2 else "analysis",
                "depends_on": [data, "code", "runtime", "procedure", *predecessors],
                "refresh": "on_change",
            }
            expression = (
                f"{index + 1} * ctx.input('{data}')['value']"
                " + ctx.input('code')['value'] + ctx.input('runtime')['value']"
            )
            expression += "".join(f" + ctx.upstream('{dep}')['value']" for dep in predecessors)
            functions.append(f"def {key}(ctx):\n    return {{'value': {expression}}}\n")
        checks["confirm"] = {
            "kind": "confirmation",
            "depends_on": [*CONFIRM_INPUTS, "procedure"],
            "refresh": "always",
        }
        checks["review"] = {
            "kind": "review",
            "depends_on": ["n0", "n1", "n2", "n3", "confirm", "scoring", "procedure"],
            "refresh": "on_change",
        }
        functions.append(
            "def confirm(ctx):\n    return {'value': "
            + " + ".join(f"ctx.input('{key}')['value']" for key in CONFIRM_INPUTS)
            + "}\n"
        )
        functions.append(
            "def review(ctx):\n    value = "
            + " + ".join(f"ctx.upstream('{key}')['value']" for key in (*checks,)[:-1])
            + "\n    return {'value': value, 'decision': "
            "'supported' if value <= ctx.input('scoring')['value'] else 'rejected'}\n"
        )
        source = directory / "handlers.py"
        source.write_text("\n".join(functions))
        namespace = {"__name__": "declared_equivalence_example"}
        exec(compile(source.read_text(), str(source), "exec"), namespace)
        self.handlers = {key: namespace[key] for key in checks}
        self.source = source
        definition = {
            "schema": "nisayon.qualification.dependencies.v1",
            "id": f"finite-graph-{mask}",
            "scope": "Exposed deterministic arithmetic; no physical confirmation or owner trial",
            "inputs": {key: {"kind": kind, "description": key} for key, kind in KINDS.items()},
            "checks": checks,
            "decisions": {
                "relation": {"depends_on": ["review"], "description": "Software example"}
            },
            "review": None,
        }
        model = DependencyModel.from_dict(definition)
        witness = self.root / "review.json"
        write_json(
            witness,
            {
                "schema": "nisayon.qualification.dependency_review.v1",
                "definition_sha256": model.definition_sha256,
                "reviewer": "exposed-development-control",
                "coverage": "reviewed_for_declared_scope",
                "statement": "Authored finite model; not independent scientific approval",
            },
        )
        definition["review"] = {
            "definition_sha256": model.definition_sha256,
            "reviewer": "exposed-development-control",
            "artifact": {"path": "review.json", "sha256": file_digest(witness)},
        }
        self.model = DependencyModel.from_dict(definition)

    def set(self, key, value):
        self.values[key] = value
        self.inputs[key] = self.paths[key] if value is not None else None
        if value is not None:
            self.paths[key].write_text(json.dumps({"value": value}))

    def expected_actions(self, previous, damaged):
        changed = (
            set(self.values)
            if previous is None
            else {key for key in self.values if self.values[key] != self.previous_values[key]}
        )
        prior_keys = set(previous.record()["checks"]) if previous is not None else set()
        dirty = set(damaged)
        for index in range(4):
            key = f"n{index}"
            data = "left" if index % 2 == 0 else "right"
            if (
                key not in prior_keys
                or {data, "code", "runtime"} & changed
                or any(
                    f"n{source}" in dirty
                    for bit, (source, target) in enumerate(EDGES)
                    if target == index and self.mask & (1 << bit)
                )
            ):
                dirty.add(key)
        dirty.update(("confirm", "review"))
        return {
            key: "run" if key in dirty else "reuse" for key in reference(self.mask, self.values)
        }

    def execute(self, name, *, fresh=False, damaged=()):
        previous = None if fresh else self.previous
        expected_actions = self.expected_actions(previous, damaged)
        expected = reference(self.mask, self.values)
        output = self.root / name
        report = execute_checks(
            self.model,
            inputs=self.inputs,
            handlers=self.handlers,
            implementation_files=[self.source],
            evidence_root=self.root,
            output=output,
            previous=previous,
            allow_partial=True,
        )
        artifacts = {
            key: json.loads((self.root / receipt["artifact"]["path"]).read_text())
            for key, receipt in report["state"]["checks"].items()
        }
        complete = all(value is not None for value in self.values.values())
        assert_contract(report, artifacts, expected, expected_actions, complete=complete)
        reviewed = inspect_checks(evidence_root=self.root, output=output)
        assert reviewed["status"] == ("verified_execution_records" if complete else "unresolved")
        assert reviewed["artifacts"] == (expected if complete else {})
        self.previous = EvidenceState.from_dict(report["state"])
        self.previous_values = dict(self.values)
        return report, artifacts

    def damage(self, key, *, missing):
        receipt = self.previous.record()["checks"][key]
        artifact = self.root / receipt["artifact"]["path"]
        if missing:
            artifact.unlink()
        else:
            artifact.write_text('{"value":999999999}')


@pytest.mark.parametrize("mask", range(64))
def test_every_four_node_forward_graph_matches_fresh_execution(tmp_path, mask):
    example = Example(tmp_path, mask)
    example.execute("initial")
    example.set("left", 23)
    _, incremental = example.execute("incremental")
    _, fresh = example.execute("fresh", fresh=True)
    assert incremental == fresh


@pytest.mark.parametrize("mask", [0, 41, 51, 63], ids=["empty", "chain", "diamond", "complete"])
def test_revision_damage_partial_and_portable_trace_preserves_result(tmp_path, mask):
    example = Example(tmp_path, mask)
    example.execute("initial")
    example.execute("unchanged")
    example.set("notes", 31)
    example.execute("irrelevant")
    example.set("scoring", -1)
    _, rejected = example.execute("rejecting_score")
    assert rejected["review"]["decision"] == "rejected"
    example.set("left", 23)
    example.execute("changed_data")
    example.damage("n1", missing=True)
    example.execute("missing_history", damaged=("n1",))
    example.damage("n2", missing=False)
    example.execute("changed_history", damaged=("n2",))
    example.set("population", None)
    partial, _ = example.execute("partial")
    assert len(partial["attempts"]) == 4
    example.set("population", 43)
    example.execute("rebound")
    example.set("scoring", 1_000_000)
    _, supported = example.execute("restored_score")
    assert supported["review"]["decision"] == "supported"
    bundle = tmp_path / "portable.zip"
    exported = export_checks(
        evidence_root=example.root, execution=example.root / "restored_score", output=bundle
    )
    admitted = import_check_bundle(
        bundle, expected_sha256=exported["bundle_sha256"], output=tmp_path / "imported"
    )
    assert admitted["automatic_acceptance"] is False
    assert admitted["deployment_decision"] == "unresolved"
    example.root = Path(admitted["evidence_root"])
    example.previous = EvidenceState.read(Path(admitted["state_path"]))
    _, relocated = example.execute("continued")
    assert relocated == supported


@pytest.mark.parametrize(
    "fault", ["stale", "missing", "decision", "cached_confirmation", "full_rerun", "refuse_all"]
)
def test_equivalence_assertions_detect_deliberate_faults(fault):
    expected = {
        "n0": {"value": 2},
        "confirm": {"value": 3},
        "review": {"value": 5, "decision": "supported"},
    }
    expected_actions = {"n0": "reuse", "confirm": "run", "review": "run"}
    report = {
        "status": "completed",
        "attempts": [{"check": key, "action": action} for key, action in expected_actions.items()],
        "automatic_acceptance": False,
        "deployment_decision": "unresolved",
    }
    artifacts = copy.deepcopy(expected)
    if fault == "stale":
        artifacts["n0"]["value"] = 1
    elif fault == "missing":
        del artifacts["n0"]
    elif fault == "decision":
        artifacts["review"]["decision"] = "rejected"
    elif fault == "cached_confirmation":
        report["attempts"][1]["action"] = "reuse"
    elif fault == "full_rerun":
        report["attempts"][0]["action"] = "run"
    else:
        report["status"] = "unresolved"
        report["attempts"] = []
        artifacts = {}
    with pytest.raises(AssertionError):
        assert_contract(report, artifacts, expected, expected_actions, complete=True)

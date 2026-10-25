"""Explicit evidence applicability under a reviewed, caller-declared dependency model.

This is a change planner, not dependency discovery, execution attestation or a
decision oracle. Hashes bind declarations and retained bytes, not physical truth.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

from nisayon.engine.io import canonical_bytes, decode_json, digest

from .context import project_file, tool_identity
from .models import fields, identifier, label, relative_file

MODEL_SCHEMA = "nisayon.qualification.dependencies.v1"
STATE_SCHEMA = "nisayon.qualification.evidence_state.v1"
REQUIRED_KINDS = {"code", "data", "runtime", "scoring", "population"}
INPUT_KINDS = REQUIRED_KINDS | {"state", "protocol", "weights", "other"}
MAX_RECORD_BYTES = 16 * 1024 * 1024


def _sha(value: object) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
        raise ValueError("Expected a lowercase SHA-256 digest")
    return value


def _mapping(value: object, name: str, *, empty: bool = False) -> dict:
    if not isinstance(value, dict) or not (0 if empty else 1) <= len(value) <= 256:
        raise ValueError(f"{name} must be a mapping with at most 256 entries")
    for key in value:
        identifier(key)
    return value


def _dependencies(value: object) -> list[str]:
    if not isinstance(value, list) or not 1 <= len(value) <= 256:
        raise ValueError("Dependencies must be a nonempty bounded list")
    for key in value:
        identifier(key)
    if len(set(value)) != len(value):
        raise ValueError("Duplicate dependency")
    return value


def _artifact(value: object) -> dict:
    record = fields(value, {"path", "sha256"})
    relative_file(record["path"])
    _sha(record["sha256"])
    return record


def _artifact_bytes(root: Path, name: str) -> bytes:
    # Hash the bytes consumed in this invocation, not a preceding stat/read pair.
    path = project_file(root.resolve(), relative_file(name))
    with path.open("rb") as stream:
        raw = stream.read(MAX_RECORD_BYTES + 1)
    if len(raw) > MAX_RECORD_BYTES:
        raise ValueError("Applicability artifacts must be at most 16 MiB")
    return raw


def _artifact_digest(root: Path, name: str) -> str:
    return hashlib.sha256(_artifact_bytes(root, name)).hexdigest()


def _verify_review(model: DependencyModel, root: Path) -> None:
    review = model.record()["review"]
    if review is None:
        raise ValueError("dependency_model_review_missing")
    artifact = review["artifact"]
    raw = _artifact_bytes(root, artifact["path"])
    if hashlib.sha256(raw).hexdigest() != artifact["sha256"]:
        raise ValueError("dependency_model_review_bytes_changed")
    record = fields(
        decode_json(raw), {"schema", "definition_sha256", "reviewer", "coverage", "statement"}
    )
    if (
        record["schema"] != "nisayon.qualification.dependency_review.v1"
        or record["definition_sha256"] != model.definition_sha256
        or record["reviewer"] != review["reviewer"]
    ):
        raise ValueError("dependency_model_review_identity_mismatch")
    label(record["statement"], "review statement")
    if record["coverage"] != "reviewed_for_declared_scope":
        raise ValueError("dependency_model_review_incomplete")


def _order(value: dict) -> list[str]:
    remaining = set(value["checks"])
    known = set(value["inputs"])
    order = []
    while remaining:
        ready = sorted(key for key in remaining if set(value["checks"][key]["depends_on"]) <= known)
        if not ready:
            raise ValueError("Check dependencies contain a cycle or an unknown node")
        order.extend(ready)
        known.update(ready)
        remaining.difference_update(ready)
    return order


def _closure(value: dict, nodes: list[str]) -> set[str]:
    result, pending = set(), list(nodes)
    while pending:
        key = pending.pop()
        if key not in result:
            result.add(key)
            if key in value["checks"]:
                pending.extend(value["checks"][key]["depends_on"])
    return result


@dataclass(frozen=True)
class DependencyModel:
    """Bounded DAG plus a review of its exact definition; missing review is explicit."""

    _bytes: bytes

    def __post_init__(self) -> None:
        value = fields(
            decode_json(self._bytes),
            {"schema", "id", "scope", "inputs", "checks", "decisions", "review"},
        )
        if value["schema"] != MODEL_SCHEMA:
            raise ValueError("Unsupported dependency model schema")
        identifier(value["id"])
        label(value["scope"], "scope")
        inputs = _mapping(value["inputs"], "inputs")
        checks = _mapping(value["checks"], "checks")
        decisions = _mapping(value["decisions"], "decisions")
        if set(inputs) & set(checks) or (set(inputs) | set(checks)) & set(decisions):
            raise ValueError("Input, check and decision IDs must be disjoint")
        for item in inputs.values():
            fields(item, {"kind", "description"})
            if item["kind"] not in INPUT_KINDS:
                raise ValueError("Unknown input kind")
            label(item["description"], "input description")
        for item in checks.values():
            fields(item, {"kind", "depends_on", "refresh"})
            if item["kind"] not in {"observation", "analysis", "confirmation", "review"}:
                raise ValueError("Unknown check kind")
            _dependencies(item["depends_on"])
            if item["refresh"] not in {"on_change", "always"}:
                raise ValueError("Unknown refresh rule")
            if item["kind"] == "confirmation" and item["refresh"] != "always":
                raise ValueError("Confirmation cannot be cached across decisions")
        _order(value)
        for item in decisions.values():
            fields(item, {"depends_on", "description"})
            label(item["description"], "decision description")
            if not set(_dependencies(item["depends_on"])) <= set(checks):
                raise ValueError("Decisions must depend on declared checks")
        review = value["review"]
        if review is not None:
            fields(review, {"definition_sha256", "reviewer", "artifact"})
            _sha(review["definition_sha256"])
            label(review["reviewer"], "reviewer")
            _artifact(review["artifact"])
            if review["definition_sha256"] != self.definition_sha256:
                raise ValueError("Review does not bind this dependency definition")
        object.__setattr__(self, "_bytes", canonical_bytes(value))

    @classmethod
    def from_dict(cls, value: dict) -> DependencyModel:
        return cls(canonical_bytes(value))

    @classmethod
    def read(cls, path: Path) -> DependencyModel:
        return cls(path.read_bytes())

    def record(self) -> dict:
        return decode_json(self._bytes)

    @property
    def sha256(self) -> str:
        return digest(self.record())

    @property
    def definition_sha256(self) -> str:
        return digest({k: v for k, v in self.record().items() if k != "review"})


@dataclass(frozen=True)
class EvidenceState:
    """Declared input identities and check receipts, including rejected observations.

    A receipt records bytes and declared dependencies, never that a test passed.
    Callers remain responsible for execution, oracles and dependency completeness.
    """

    _bytes: bytes

    def __post_init__(self) -> None:
        value = fields(decode_json(self._bytes), {"schema", "model_sha256", "inputs", "checks"})
        if value["schema"] != STATE_SCHEMA:
            raise ValueError("Unsupported evidence state schema")
        _sha(value["model_sha256"])
        for identity in _mapping(value["inputs"], "input identities").values():
            if identity is not None:
                _sha(identity)
        for receipt in _mapping(value["checks"], "check receipts", empty=True).values():
            fields(receipt, {"basis_sha256", "artifact"})
            _sha(receipt["basis_sha256"])
            _artifact(receipt["artifact"])
        object.__setattr__(self, "_bytes", canonical_bytes(value))

    @classmethod
    def from_dict(cls, value: dict) -> EvidenceState:
        return cls(canonical_bytes(value))

    @classmethod
    def read(cls, path: Path) -> EvidenceState:
        return cls(path.read_bytes())

    def record(self) -> dict:
        return decode_json(self._bytes)

    @property
    def sha256(self) -> str:
        return digest(self.record())


def _inputs(model: dict, inputs: dict) -> None:
    if not isinstance(inputs, dict) or set(inputs) != set(model["inputs"]):
        raise ValueError(
            "Input identities must cover exactly the declared inputs; use null for unknown"
        )
    for identity in inputs.values():
        if identity is not None:
            _sha(identity)


def _basis(model: DependencyModel, state: dict, key: str) -> str:
    dependencies = {}
    for dependency in model.record()["checks"][key]["depends_on"]:
        if dependency in state["inputs"]:
            identity = state["inputs"][dependency]
            if identity is None:
                raise ValueError(f"Unknown input: {dependency}")
            dependencies[dependency] = identity
        else:
            receipt = state["checks"].get(dependency)
            if receipt is None:
                raise ValueError(f"Missing upstream receipt: {dependency}")
            dependencies[dependency] = {
                "basis_sha256": receipt["basis_sha256"],
                "artifact_sha256": receipt["artifact"]["sha256"],
            }
    return digest(
        {
            "model_sha256": model.sha256,
            "tool": tool_identity(),
            "check": key,
            "dependencies": dependencies,
        }
    )


def _receipt_issues(model: DependencyModel, state: dict, root: Path) -> dict[str, str]:
    issues = {}
    for key in _order(model.record()):
        try:
            receipt = state["checks"].get(key)
            if receipt is None:
                raise ValueError("missing_receipt")
            dependencies = model.record()["checks"][key]["depends_on"]
            if any(dep in issues for dep in dependencies):
                raise ValueError("unavailable_upstream_evidence")
            if receipt["basis_sha256"] != _basis(model, state, key):
                raise ValueError("receipt_dependency_mismatch")
            artifact = receipt["artifact"]
            if _artifact_digest(root, artifact["path"]) != artifact["sha256"]:
                raise ValueError("artifact_bytes_changed")
        except (ValueError, OSError) as error:
            issues[key] = str(error)
    return issues


def record_check(
    model: DependencyModel,
    state: EvidenceState,
    check: str,
    *,
    evidence_root: Path,
    artifact: str,
) -> EvidenceState:
    """Bind an already produced artifact to declared inputs; does not run or approve it.

    Create a new state for each decision. Preserve old states and artifacts,
    including failed attempts; copying a receipt is never fresh confirmation.
    """
    value, declaration = state.record(), model.record()
    _inputs(declaration, value["inputs"])
    if value["model_sha256"] != model.sha256 or set(value["checks"]) - set(declaration["checks"]):
        raise ValueError("State does not belong to this model")
    if check not in declaration["checks"] or check in value["checks"]:
        raise ValueError("Check must be declared and must not overwrite a receipt")
    ancestors = _closure(declaration, declaration["checks"][check]["depends_on"])
    issues = _receipt_issues(model, value, evidence_root)
    if any(key in issues for key in ancestors & set(declaration["checks"])):
        raise ValueError("Cannot bind a check to unavailable upstream evidence")
    value["checks"][check] = {
        "basis_sha256": _basis(model, value, check),
        "artifact": {"path": artifact, "sha256": _artifact_digest(evidence_root, artifact)},
    }
    return EvidenceState.from_dict(value)


def plan_applicability(
    model: DependencyModel,
    previous: EvidenceState,
    proposed_inputs: dict[str, str | None],
    *,
    evidence_root: Path,
) -> dict:
    """Explain required checks; never execute a check or accept a deployment.

    Equivalent hashes are evidence identities, not distributional equivalence.
    Null identities, incomplete scope and missing review prevent applicability.
    """
    value, old = model.record(), previous.record()
    _inputs(value, proposed_inputs)
    same_model = old["model_sha256"] == model.sha256
    if same_model:
        _inputs(value, old["inputs"])
        if set(old["checks"]) - set(value["checks"]):
            raise ValueError("State contains an undeclared check")
    obligations = []
    try:
        _verify_review(model, evidence_root)
    except (OSError, ValueError) as error:
        obligations.append(str(error))
    review_valid = not obligations
    unknown = sorted(key for key, identity in proposed_inputs.items() if identity is None)
    obligations.extend(f"unknown_input:{key}" for key in unknown)
    changed = sorted(
        key for key in proposed_inputs if proposed_inputs[key] != old["inputs"].get(key)
    )
    issues = _receipt_issues(model, old, evidence_root) if same_model else {}
    checks = {}
    for key in _order(value):
        check = value["checks"][key]
        reasons = []
        if not same_model:
            reasons.append("dependency_model_changed")
        if not review_valid:
            reasons.append("dependency_model_review_unavailable")
        if key in issues:
            reasons.append(issues[key])
        if check["refresh"] == "always":
            reasons.append("fresh_check_required")
        affected = []
        for dependency in check["depends_on"]:
            if dependency in value["inputs"]:
                if dependency in unknown or old["inputs"].get(dependency) is None:
                    affected.append({"input": dependency, "reason": "unknown", "via": dependency})
                elif dependency in changed:
                    affected.append({"input": dependency, "reason": "changed", "via": dependency})
            else:
                upstream = checks[dependency]
                affected.extend({**item, "via": dependency} for item in upstream["affected_inputs"])
                if upstream["action"] == "run":
                    reasons.append(f"upstream_requires_check:{dependency}")
        affected = sorted(
            {canonical_bytes(item): item for item in affected}.values(),
            key=lambda item: (item["input"], item["reason"], item["via"]),
        )
        checks[key] = {
            "kind": check["kind"],
            "action": "run" if reasons or affected else "reuse",
            "reasons": sorted(reasons),
            "affected_inputs": affected,
            "prior_artifact": old["checks"].get(key, {}).get("artifact"),
        }
    decisions = {}
    for key, decision in sorted(value["decisions"].items()):
        closure = _closure(value, decision["depends_on"])
        kinds = {value["inputs"][node]["kind"] for node in closure & set(value["inputs"])}
        missing = sorted(REQUIRED_KINDS - kinds)
        decision_obligations = [f"uncovered_dependency_kind:{kind}" for kind in missing]
        relevant_checks = [node for node in checks if node in closure]
        if not any(checks[node]["kind"] == "confirmation" for node in relevant_checks):
            decision_obligations.append("fresh_confirmation_not_declared")
        decision_obligations.extend(f"unknown_input:{node}" for node in unknown if node in closure)
        if not review_valid:
            decision_obligations.append("dependency_model_review_unavailable")
        required = [node for node in relevant_checks if checks[node]["action"] == "run"]
        decisions[key] = {
            "applicability": "unresolved" if decision_obligations else "requires_checks",
            "required_checks": required,
            "reusable_checks": [
                node for node in relevant_checks if checks[node]["action"] == "reuse"
            ],
            "obligations": sorted(decision_obligations),
        }
        obligations.extend(f"{key}:{item}" for item in decision_obligations)
    return {
        "schema": "nisayon.qualification.applicability.v1",
        "model_sha256": model.sha256,
        "planner_tool": tool_identity(),
        "previous_state_sha256": previous.sha256,
        "proposed_inputs_sha256": digest(proposed_inputs),
        "status": "unresolved" if obligations else "planned",
        "changed_inputs": changed,
        "checks": checks,
        "decisions": decisions,
        "obligations": sorted(set(obligations)),
        "automatic_acceptance": False,
        "observations": "Historical evidence remains about its original execution only.",
        "limit": "Conditional on the reviewed dependency model, truthful receipts and complete input identities. No discovery of undeclared dependencies, execution attestation, statistical guarantee, physical acceptance or complete-cost saving.",
    }

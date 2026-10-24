"""Portable experiment declarations; no workspace, model or simulator imports."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from nisayon.engine.io import canonical_bytes, decode_json, digest

CASE_SCHEMA = "nisayon.qualification.case.v1"
LEGACY_PLAN_SCHEMA = "nisayon.qualification.plan.v1"
PLAN_SCHEMA = "nisayon.qualification.plan.v2"
READ_POLICY = "cpython_owner_reads_v1"
ROLES = ("reference", "negative_control", "candidate")


def fields(value: object, required: set[str], optional: set[str] | None = None) -> dict:
    if not isinstance(value, dict) or set(value) - required - (optional or set()):
        raise ValueError("Expected an object with only declared fields")
    if required - set(value):
        raise ValueError(f"Missing fields: {sorted(required - set(value))}")
    return value


def label(value: object, name: str) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > 500:
        raise ValueError(f"{name} must be a nonempty string of at most 500 characters")
    return value


def identifier(value: object) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_-]{0,79}", value):
        raise ValueError("IDs must be simple names of at most 80 characters")
    return value


def relative_file(value: object) -> str:
    if not isinstance(value, str):
        raise ValueError("Source path must be a relative POSIX path")
    path = PurePosixPath(value)
    if path.is_absolute() or not path.parts or ".." in path.parts or str(path) != value:
        raise ValueError("Source path must be normalized and stay within the owner project")
    return value


def positive(value: object, name: str, *, maximum: float) -> float:
    if type(value) not in (int, float) or not 0 < value <= maximum:
        raise ValueError(f"{name} must be finite, positive and at most {maximum}")
    return float(value)


@dataclass(frozen=True)
class CaseSpec:
    """An immutable JSON declaration. Expected outputs are owner-supplied premises."""

    _bytes: bytes

    def __post_init__(self) -> None:
        value = fields(
            decode_json(self._bytes),
            {
                "schema",
                "id",
                "question",
                "contract",
                "targets",
                "source_files",
                "premises",
                "probes",
            },
            {"effects", "feedback"},
        )
        if value["schema"] != CASE_SCHEMA:
            raise ValueError("Unsupported qualification case schema")
        identifier(value["id"])
        label(value["question"], "question")
        contract = fields(value["contract"], {"kind"}, {"atol", "rtol"})
        if contract["kind"] not in {"exact", "numerical", "behavioral"}:
            raise ValueError("Unknown equivalence contract")
        for name in ("atol", "rtol"):
            number = contract.get(name, 0)
            try:
                valid = type(number) in (int, float) and math.isfinite(number) and number >= 0
            except OverflowError:
                valid = False
            if not valid:
                raise ValueError("Tolerances must be finite and nonnegative")
            if contract["kind"] != "numerical" and number != 0:
                raise ValueError("Only a numerical contract accepts tolerances")
        targets = fields(value["targets"], set(ROLES))
        for target in targets.values():
            fields(target, {"path", "callable"}, {"required_calls"})
            relative_file(target["path"])
            symbol = label(target["callable"], "callable")
            if not all(
                part.isidentifier() and not part.startswith("__") for part in symbol.split(".")
            ):
                raise ValueError("Callable must be an explicit Python attribute path")
            required_calls = target.get("required_calls", [])
            if not isinstance(required_calls, list) or len(required_calls) > 64:
                raise ValueError("required_calls must be a bounded list of Python symbols")
            for required in required_calls:
                if not isinstance(required, str) or not all(
                    part.isidentifier() and not part.startswith("__")
                    for part in required.split(".")
                ):
                    raise ValueError("Required calls must be explicit Python symbols")
        files = value["source_files"]
        if not isinstance(files, list) or not files or len(files) > 1024:
            raise ValueError("Declare between 1 and 1024 source/data/lock files")
        if len(set(relative_file(path) for path in files)) != len(files):
            raise ValueError("Source files must be unique")
        if {target["path"] for target in targets.values()} - set(files):
            raise ValueError("All entry points must be declared source files")
        premises = value["premises"]
        if not isinstance(premises, dict) or not {"population", "state", "environment"} <= set(
            premises
        ):
            raise ValueError("Declare population, state and environment premises")
        for key, item in premises.items():
            label(key, "premise name")
            if item is not None:
                label(item, "premise")
        probes = value["probes"]
        if not isinstance(probes, list) or not 1 <= len(probes) <= 32:
            raise ValueError("Declare between 1 and 32 probes")
        seen = set()
        for probe in probes:
            fields(probe, {"id", "input", "expected"})
            name = identifier(probe["id"])
            if name in seen:
                raise ValueError("Probe IDs must be unique")
            seen.add(name)
        if value.get("effects", "software") not in {"software", "action"}:
            raise ValueError("effects must be software or action")
        if value.get("feedback", "not_applicable") not in {
            "not_applicable",
            "recomputed",
            "recorded_future",
        }:
            raise ValueError("Unknown feedback mode")
        object.__setattr__(self, "_bytes", canonical_bytes(value))

    @classmethod
    def from_dict(cls, value: dict) -> CaseSpec:
        return cls(canonical_bytes(value))

    @classmethod
    def read(cls, path: str | Path) -> CaseSpec:
        return cls(Path(path).read_bytes())

    def record(self) -> dict:
        return decode_json(self._bytes)

    @property
    def sha256(self) -> str:
        return digest(self.record())


@dataclass(frozen=True)
class ExperimentPlan:
    """A frozen declaration and measured execution identities."""

    _bytes: bytes

    def __post_init__(self) -> None:
        value = decode_json(self._bytes)
        if not isinstance(value, dict) or value.get("schema") not in {
            LEGACY_PLAN_SCHEMA,
            PLAN_SCHEMA,
        }:
            raise ValueError("Unsupported qualification plan schema")
        required = {"schema", "case", "context", "sources", "tool", "obligations", "assignments"}
        if value["schema"] == PLAN_SCHEMA:
            required.add("read_policy")
            if value.get("read_policy") != READ_POLICY:
                raise ValueError("Unsupported native read observation policy")
        fields(value, required)
        CaseSpec.from_dict(value["case"])
        object.__setattr__(self, "_bytes", canonical_bytes(value))

    @classmethod
    def from_dict(cls, value: dict) -> ExperimentPlan:
        return cls(canonical_bytes(value))

    @classmethod
    def read(cls, path: str | Path) -> ExperimentPlan:
        return cls(Path(path).read_bytes())

    def record(self) -> dict:
        return decode_json(self._bytes)

    @property
    def sha256(self) -> str:
        return digest(self.record())


@dataclass(frozen=True)
class RunEvidence:
    """Locator plus expected plan identity; assessment rereads retained bytes."""

    root: Path
    plan_sha256: str


@dataclass(frozen=True)
class Assessment:
    _bytes: bytes

    @classmethod
    def from_dict(cls, value: dict) -> Assessment:
        return cls(canonical_bytes(value))

    def record(self) -> dict:
        return decode_json(self._bytes)

    @property
    def decision(self) -> str:
        return self.record()["software_decision"]

    def write(self, path: str | Path) -> None:
        from nisayon.engine.io import write_json

        write_json(Path(path), self.record())

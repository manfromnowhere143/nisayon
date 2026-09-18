"""Checks for a future reserved evaluation, on openly labelled development examples.

Nothing here creates reserved answers, and nothing here is custody. The checks say
whether a sealed manifest, a comparison ledger and the retained development history
are consistent with a reserved screen: complete assignments, no leaked case, a
protocol and retrieval cutoff frozen before sealing, and a custody statement that
keeps the solver away from the answers. A missing custody boundary is a named gap
that leaves the reserved trial unrun.
"""

from __future__ import annotations

import hashlib
from datetime import datetime
from pathlib import Path

from .schema import (
    Malformed,
    integer,
    load_json,
    mapping,
    parse_wall_time,
    require,
    sequence,
    string,
)

MANIFEST_SCHEMA = "nisayon.reserved_manifest.v1"
CHECK_SCHEMA = "nisayon.reserved_check.v1"
DECLARED_FAMILIES = {
    "single_mechanism": 6,
    "interacting": 6,
    "invalid_control": 4,
    "non_identifiable": 2,
    "vacuous_trap": 2,
}
SOLVER_ACCESS_ALLOWED = {"none"}
BLOCKING = {
    "malformed_manifest",
    "custody_not_separated",
    "reserved_case_leaked",
    "sealed_case_mismatch",
    "answer_present_in_shared_tree",
    "assignment_incomplete",
    "protocol_not_frozen_before_seal",
    "family_counts_differ",
}


def _wall(obj: dict, key: str, path: str) -> datetime:
    return parse_wall_time({"value": obj.get(key), "clock": "wall_utc"}, f"{path}.{key}")


def parse_manifest(obj: object) -> dict:
    path = "manifest"
    data = mapping(obj, path)
    schema = string(data, "schema", path)
    if schema != MANIFEST_SCHEMA:
        raise Malformed(f"{path}.schema", f"expected {MANIFEST_SCHEMA}, found {schema!r}")
    custody = mapping(require(data, "custody", path), f"{path}.custody")
    protocol = mapping(require(data, "protocol", path), f"{path}.protocol")
    cutoff = mapping(
        require(protocol, "retrieval_cutoff", f"{path}.protocol"),
        f"{path}.protocol.retrieval_cutoff",
    )
    cases = []
    seen: set[str] = set()
    for index, item in enumerate(sequence(require(data, "cases", path), f"{path}.cases")):
        cpath = f"{path}.cases[{index}]"
        cdata = mapping(item, cpath)
        case_id = string(cdata, "id", cpath)
        if case_id in seen:
            raise Malformed(f"{cpath}.id", f"duplicate reserved case {case_id!r}")
        seen.add(case_id)
        cases.append(
            {
                "id": case_id,
                "family": string(cdata, "family", cpath, allowed=set(DECLARED_FAMILIES)),
                "sealed_sha256": string(cdata, "sealed_sha256", cpath),
                "answer_sha256": string(cdata, "answer_sha256", cpath),
            }
        )
    return {
        "suite_id": string(data, "suite_id", path),
        "evidence_origin": string(data, "evidence_origin", path),
        "sealed_at": _wall(data, "sealed_at", path),
        "sealed_by_role": string(data, "sealed_by_role", path),
        "custody": {
            "case_generation": string(custody, "case_generation", f"{path}.custody"),
            "solver_access": string(custody, "solver_access", f"{path}.custody"),
            "evaluator_access": string(custody, "evaluator_access", f"{path}.custody"),
            "statement": string(custody, "statement", f"{path}.custody"),
        },
        "protocol": {
            "obligation": string(protocol, "obligation", f"{path}.protocol"),
            "evaluator_commit": string(protocol, "evaluator_commit", f"{path}.protocol"),
            "frozen_at": _wall(protocol, "frozen_at", f"{path}.protocol"),
            "retrieval_cutoff_at": _wall(cutoff, "at", f"{path}.protocol.retrieval_cutoff"),
            "memory_tree_sha256": string(
                cutoff, "memory_tree_sha256", f"{path}.protocol.retrieval_cutoff"
            ),
        },
        "families": {
            name: integer(value, f"{path}.families.{name}", minimum=0)
            for name, value in mapping(require(data, "families", path), f"{path}.families").items()
        },
        "cases": cases,
        "arms": [str(a) for a in sequence(data.get("arms", []), f"{path}.arms")],
    }


def development_identifiers(paths: list[Path] | tuple[Path, ...]) -> tuple[set[str], set[str]]:
    """Case IDs and file digests present in development ledgers, decisions or documents."""
    ids: set[str] = set()
    digests: set[str] = set()
    for raw in paths:
        path = Path(raw)
        if path.is_dir():
            for file in path.rglob("*.json"):
                digests.add(hashlib.sha256(file.read_bytes()).hexdigest())
                try:
                    data = load_json(file)
                except Malformed:
                    continue
                ids.update(_case_ids(data))
            continue
        if not path.is_file():
            continue
        digests.add(hashlib.sha256(path.read_bytes()).hexdigest())
        try:
            data = load_json(path)
        except Malformed:
            continue
        ids.update(_case_ids(data))
    return ids, digests


def _case_ids(data: object) -> set[str]:
    found: set[str] = set()
    if isinstance(data, dict):
        for key in ("case_id", "id"):
            if isinstance(data.get(key), str) and data.get("schema") in (
                "nisayon.decision.v1",
                "nisayon.case.v1",
            ):
                found.add(data[key])
        for key in ("cases", "trials", "runs"):
            for item in data.get(key, []) or []:
                if isinstance(item, dict):
                    for id_key in ("id", "case_id"):
                        if isinstance(item.get(id_key), str):
                            found.add(item[id_key])
    return found


def check_reserved(
    manifest_obj: object,
    *,
    ledger: object | None = None,
    development: list[Path] | tuple[Path, ...] = (),
    case_dir: Path | None = None,
    shared_trees: list[Path] | tuple[Path, ...] = (),
    solver_started_at: datetime | None = None,
) -> dict:
    findings: list[dict] = []
    result: dict = {
        "schema": CHECK_SCHEMA,
        "ready": False,
        "suite_id": None,
        "evidence_origin": None,
        "counts": {},
        "findings": findings,
        "limits": [
            "These checks read records; they do not create custody. A solver with filesystem "
            "access to the answers defeats them whatever the manifest says.",
            "A sealed digest binds the case bytes; it does not make the case unseen by the "
            "session that wrote it.",
        ],
    }
    try:
        manifest = parse_manifest(manifest_obj)
    except Malformed as error:
        findings.append({"code": "malformed_manifest", "detail": str(error)})
        return result
    result["suite_id"] = manifest["suite_id"]
    result["evidence_origin"] = manifest["evidence_origin"]
    custody = manifest["custody"]
    if custody["solver_access"] not in SOLVER_ACCESS_ALLOWED:
        findings.append(
            {
                "code": "custody_not_separated",
                "detail": f"solver access to reserved cases is {custody['solver_access']!r}; a reserved "
                "trial needs none",
            }
        )
    if custody["case_generation"] == custody["evaluator_access"] == "shared":
        findings.append(
            {
                "code": "custody_not_separated",
                "detail": "case generation and evaluation share one authority",
            }
        )
    protocol = manifest["protocol"]
    if not protocol["frozen_at"] <= protocol["retrieval_cutoff_at"] <= manifest["sealed_at"]:
        findings.append(
            {
                "code": "protocol_not_frozen_before_seal",
                "detail": "the order must be protocol freeze, retrieval cutoff, seal",
            }
        )
    if solver_started_at is not None and solver_started_at < manifest["sealed_at"]:
        findings.append(
            {
                "code": "protocol_not_frozen_before_seal",
                "detail": "the solver session started before the manifest was sealed",
            }
        )
    counts: dict[str, int] = {}
    for case in manifest["cases"]:
        counts[case["family"]] = counts.get(case["family"], 0) + 1
    result["counts"] = counts
    declared = manifest["families"]
    if declared != DECLARED_FAMILIES:
        findings.append(
            {
                "code": "family_counts_differ",
                "detail": f"declared families {declared} differ from the research plan's {DECLARED_FAMILIES}",
            }
        )
    if counts != declared:
        findings.append(
            {
                "code": "family_counts_differ",
                "detail": f"sealed cases {counts} do not match the declared families {declared}",
            }
        )
    ids, digests = development_identifiers(development)
    for case in manifest["cases"]:
        if case["id"] in ids:
            findings.append(
                {
                    "code": "reserved_case_leaked",
                    "detail": f"reserved case {case['id']!r} appears in development records",
                }
            )
        if case["sealed_sha256"] in digests or case["answer_sha256"] in digests:
            findings.append(
                {
                    "code": "reserved_case_leaked",
                    "detail": f"reserved case {case['id']!r} bytes appear in development records",
                }
            )
    if case_dir is not None:
        for case in manifest["cases"]:
            target = Path(case_dir) / f"{case['id']}.json"
            if not target.is_file():
                findings.append(
                    {
                        "code": "sealed_case_mismatch",
                        "detail": f"reserved case file {target.name} is absent",
                    }
                )
                continue
            actual = hashlib.sha256(target.read_bytes()).hexdigest()
            if actual != case["sealed_sha256"]:
                findings.append(
                    {
                        "code": "sealed_case_mismatch",
                        "detail": f"reserved case {case['id']!r} bytes differ from the seal",
                    }
                )
    answer_digests = {case["answer_sha256"] for case in manifest["cases"]}
    for tree in shared_trees:
        root = Path(tree)
        if not root.is_dir():
            continue
        for file in root.rglob("*"):
            if file.is_file() and hashlib.sha256(file.read_bytes()).hexdigest() in answer_digests:
                findings.append(
                    {
                        "code": "answer_present_in_shared_tree",
                        "detail": f"a sealed answer's bytes are present at {file}",
                    }
                )
    if ledger is not None:
        try:
            ldata = mapping(ledger, "ledger")
            trials = sequence(ldata.get("trials", []), "ledger.trials")
            arms = {
                str(a.get("id"))
                for a in sequence(ldata.get("arms", []), "ledger.arms")
                if isinstance(a, dict)
            }
        except Malformed as error:
            findings.append(
                {"code": "assignment_incomplete", "detail": f"ledger unreadable: {error}"}
            )
            trials, arms = [], set()
        expected_arms = set(manifest["arms"]) or arms
        assigned = {
            (str(t.get("arm")), str(t.get("case_id"))) for t in trials if isinstance(t, dict)
        }
        for arm in sorted(expected_arms):
            for case in manifest["cases"]:
                if (arm, case["id"]) not in assigned:
                    findings.append(
                        {
                            "code": "assignment_incomplete",
                            "detail": f"arm {arm!r} has no trial for reserved case {case['id']!r}",
                        }
                    )
        extra = {c for _, c in assigned} - {case["id"] for case in manifest["cases"]}
        if extra:
            findings.append(
                {
                    "code": "assignment_incomplete",
                    "detail": f"trials name cases outside the sealed manifest: {sorted(extra)[:3]}",
                }
            )
    result["ready"] = not any(f["code"] in BLOCKING for f in findings)
    return result


def render_reserved(result: dict) -> str:
    lines = [
        f"Reserved screen check: {'ready' if result['ready'] else 'NOT READY'} · suite {result.get('suite_id')} · "
        f"evidence origin {result.get('evidence_origin')}",
        f"Sealed cases by family: {result.get('counts')}",
    ]
    if result["findings"]:
        lines.append("Findings:")
        for finding in result["findings"]:
            lines.append(f"  - {finding['code']}: {finding['detail']}")
    lines.append("Limits:")
    for limit in result["limits"]:
        lines.append(f"  - {limit}")
    return "\n".join(lines)

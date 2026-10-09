"""Constructed controls PBC01-PBC06 for the population-binding reference and diagnostic.

Every control is synthetic: a small three-episode "current" directory and, where a
parent is needed, an eight-episode parent population that contains those three episodes.
Statistics files are written by this module in the pinned upstream convention (numpy
float32 reduction). Nothing here establishes a real training lineage or a deployment
selector; the controls prove software rules only. Each control names what the reference
and the conventional diagnostic must both conclude, from the frozen contract.
"""

from __future__ import annotations

import hashlib
import json
import math
import struct
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from .conventional_population import diagnose
from .parquet_reader import write_parquet_lowdim
from .population_reference import assess_case, assess_producer_record

STATE_DIM, ACTION_DIM, FPS = 5, 3, 10
LENGTHS = [12, 15, 9, 20, 14, 11, 17, 13]  # eight parent episodes; the first three are shipped


def f32(value: float) -> float:
    return struct.unpack("<f", struct.pack("<f", value))[0]


def episode_rows(episode: int, length: int, *, state_dim: int = STATE_DIM) -> tuple[list, list]:
    """Deterministic synthetic rows; later episodes range wider than the first three."""
    scale = 1.0 + 0.6 * episode
    state = []
    action = []
    for t in range(length):
        phase = t / max(length - 1, 1)
        state.append(
            [
                f32(scale * math.sin(2.0 * math.pi * phase + k) + 0.1 * episode)
                for k in range(state_dim)
            ]
        )
        action.append(
            [
                f32(0.9375 * math.cos(3.0 * phase + k) * (1.0 + 0.2 * episode))
                for k in range(ACTION_DIM - 1)
            ]
            + [f32(1.0 if (t + episode) % 3 == 0 else 0.0)]
        )
    return state, action


def numpy_convention(rows: list[list[float]]) -> dict:
    import numpy as np

    array = np.asarray(rows, dtype=np.float32)
    return {
        "mean": np.mean(array, 0).tolist(),
        "std": np.std(array, 0).tolist(),
        "min": np.min(array, 0).tolist(),
        "max": np.max(array, 0).tolist(),
        "q01": np.quantile(array, 0.01, 0).tolist(),
        "q99": np.quantile(array, 0.99, 0).tolist(),
    }


def episode_entry(rows: list[list[float]]) -> dict:
    import numpy as np

    array = np.asarray(rows, dtype=np.float32)
    return {
        "min": np.min(array, 0).tolist(),
        "max": np.max(array, 0).tolist(),
        "mean": np.mean(array, 0).tolist(),
        "std": np.std(array, 0).tolist(),
        "count": [len(rows)],
    }


def info_document(state_dim: int = STATE_DIM) -> dict:
    return {
        "codebase_version": "v2.1",
        "fps": FPS,
        "total_episodes": 3,
        "features": {
            "observation.state": {"dtype": "float32", "shape": [state_dim]},
            "action": {"dtype": "float32", "shape": [ACTION_DIM]},
            "timestamp": {"dtype": "float32", "shape": [1]},
            "frame_index": {"dtype": "int64", "shape": [1]},
            "episode_index": {"dtype": "int64", "shape": [1]},
            "index": {"dtype": "int64", "shape": [1]},
            "task_index": {"dtype": "int64", "shape": [1]},
        },
    }


def write_dataset(
    folder: Path,
    *,
    shipped: int = 3,
    parent: int = 8,
    stats_over: int,
    enumerate_parent: bool,
    state_dim: int = STATE_DIM,
    corrupt: str | None = None,
) -> dict:
    """Write ``shipped`` episode files, info.json, stats.json over ``stats_over`` episodes."""
    folder.mkdir(parents=True, exist_ok=True)
    all_state: dict[int, list] = {}
    all_action: dict[int, list] = {}
    for episode in range(parent):
        all_state[episode], all_action[episode] = episode_rows(
            episode, LENGTHS[episode], state_dim=state_dim
        )
    files = []
    start = 0
    for episode in range(shipped):
        n = LENGTHS[episode]
        state = [list(r) for r in all_state[episode]]
        if corrupt == "non_finite" and episode == 1:
            state[3][2] = float("nan")
        if corrupt == "wrong_dimension" and episode == 2:
            state = [r[:-1] for r in state]
        columns = {
            "observation.state": state,
            "action": all_action[episode],
            "timestamp": [f32(t / FPS) for t in range(n)],
            "frame_index": list(range(n)),
            "episode_index": [episode] * n,
            "index": list(range(start, start + n)),
            "task_index": [episode % 2] * n,
        }
        path = folder / f"episode_{episode:06d}.parquet"
        data = write_parquet_lowdim(path, columns, list_columns=("observation.state", "action"))
        if corrupt == "truncated" and episode == 0:
            path.write_bytes(data[: len(data) // 2])
            data = path.read_bytes()
        files.append(
            {
                "path": path.name,
                "episode_index": episode,
                "declared_length": n,
                "sha256": hashlib.sha256(data).hexdigest(),
            }
        )
        start += n
    stats = {
        "observation.state": numpy_convention([r for e in range(stats_over) for r in all_state[e]]),
        "action": numpy_convention([r for e in range(stats_over) for r in all_action[e]]),
    }
    if corrupt == "non_finite_statistics":
        stats["action"]["std"][0] = float("nan")
    (folder / "stats.json").write_text(json.dumps(stats, indent=1, allow_nan=True) + "\n")
    (folder / "info.json").write_text(json.dumps(info_document(state_dim), indent=1) + "\n")
    if enumerate_parent:
        lines = [
            json.dumps(
                {
                    "episode_index": e,
                    "stats": {
                        "observation.state": episode_entry(all_state[e]),
                        "action": episode_entry(all_action[e]),
                    },
                }
            )
            for e in range(parent)
        ]
        (folder / "episodes_stats.jsonl").write_text("\n".join(lines) + "\n")
    invocation = folder / "invocation_fixture.txt"
    invocation.write_text(
        "constructed control: a fixture standing in for an observed invocation; not a real caller\n"
        "check_stats_validity(dataset, features)  # fixture symbol\n"
    )
    return {
        "files": files,
        "invocation_sha256": hashlib.sha256(invocation.read_bytes()).hexdigest(),
    }


def make_case(
    folder: Path,
    case_id: str,
    written: dict,
    *,
    enumeration: bool,
    declared_role: str | None,
    selection: dict | None,
) -> dict:
    return {
        "schema": "nisayon.population-case.v1",
        "case_id": case_id,
        "root": str(folder),
        "files": written["files"],
        "info": "info.json",
        "published_statistics": "stats.json",
        "features": ["observation.state", "action"],
        "episodes_stats": "episodes_stats.jsonl" if enumeration else None,
        "declared_role": declared_role,
        "selection_evidence": selection,
        "interpretation_evidence": None,
        "provenance": "constructed control; synthetic rows; no lineage or deployment claim",
    }


def observed_invocation(written: dict) -> dict:
    return {
        "kind": "observed_invocation",
        "source_path": "invocation_fixture.txt",
        "source_sha256": written["invocation_sha256"],
        "symbol": "check_stats_validity",
        "revision": "fixture",
        "detail": "constructed stand-in for an observed caller",
    }


@dataclass(frozen=True)
class Control:
    name: str
    question: str
    build: Callable[[Path], list[dict]]
    check: Callable[[list[dict]], list[str]]


def _expect(
    results: list[dict], case_id: str, *, operation: str, decision: str, role: str | None = None
) -> list[str]:
    failures = []
    row = next(r for r in results if r["case_id"] == case_id)
    ref = row["reference"]["operation"]
    if ref["operation"] != operation or ref["decision"] != decision:
        failures.append(
            f"{case_id}: reference gave {ref['operation']}/{ref['decision']}, expected {operation}/{decision}"
        )
    if role is not None and row["reference"].get("role", {}).get("role") != role:
        failures.append(
            f"{case_id}: reference role {row['reference'].get('role', {}).get('role')}, expected {role}"
        )
    prod = row["conventional"]["decision"]
    if prod["selected_operation"] != operation or prod["status"] != decision:
        failures.append(
            f"{case_id}: conventional gave {prod['selected_operation']}/{prod['status']}, expected {operation}/{decision}"
        )
    cmp = row["comparison"]
    if not cmp.get("agrees"):
        failures.append(f"{case_id}: reference and conventional disagree: {cmp}")
    return failures


def build_pbc01(folder: Path) -> list[dict]:
    written = write_dataset(folder, stats_over=3, enumerate_parent=False)
    return [
        make_case(
            folder, "PBC01-intact", written, enumeration=False, declared_role=None, selection=None
        )
    ]


def check_pbc01(results: list[dict]) -> list[str]:
    return _expect(
        results,
        "PBC01-intact",
        operation="reuse",
        decision="supported",
        role="current_population_summary",
    )


def build_pbc02(folder: Path) -> list[dict]:
    written = write_dataset(folder, stats_over=8, enumerate_parent=False)
    return [
        make_case(
            folder,
            "PBC02-mismatch-declared-current",
            written,
            enumeration=False,
            declared_role="current_population_summary",
            selection=None,
        )
    ]


def check_pbc02(results: list[dict]) -> list[str]:
    failures = _expect(
        results, "PBC02-mismatch-declared-current", operation="recompute", decision="rejected"
    )
    row = next(r for r in results if r["case_id"] == "PBC02-mismatch-declared-current")
    outside = row["reference"]["features"]["observation.state"]["role"]["subset_relation"][
        "coordinates_outside_subset"
    ]
    if outside == 0:
        failures.append(
            "the parent statistics must lie outside the shipped subset for this control to discriminate"
        )
    return failures


def build_pbc03(folder: Path) -> list[dict]:
    written = write_dataset(folder, stats_over=8, enumerate_parent=True)
    return [
        make_case(
            folder,
            "PBC03-bound-parent",
            written,
            enumeration=True,
            declared_role=None,
            selection=observed_invocation(written),
        )
    ]


def check_pbc03(results: list[dict]) -> list[str]:
    failures = _expect(
        results,
        "PBC03-bound-parent",
        operation="reuse",
        decision="supported",
        role="parent_population_summary",
    )
    row = next(r for r in results if r["case_id"] == "PBC03-bound-parent")
    direct = row["reference"]["features"]["observation.state"]["role"]["direct"]
    if direct["all_match"]:
        failures.append(
            "the subset moments must differ from the reference for this control to mean anything"
        )
    if row["reference"]["operation"].get("intent_note") is None:
        failures.append("reuse of a parent reference must carry the unresolved-intent note")
    return failures


def build_pbc04(folder: Path) -> list[dict]:
    a = folder / "no-selection"
    b = folder / "no-enumeration"
    wa = write_dataset(a, stats_over=8, enumerate_parent=True)
    wb = write_dataset(b, stats_over=8, enumerate_parent=False)
    return [
        make_case(
            a, "PBC04-no-selection", wa, enumeration=True, declared_role=None, selection=None
        ),
        make_case(
            b, "PBC04-no-enumeration", wb, enumeration=False, declared_role=None, selection=None
        ),
    ]


def check_pbc04(results: list[dict]) -> list[str]:
    failures = _expect(
        results,
        "PBC04-no-selection",
        operation="abstain",
        decision="unresolved",
        role="parent_population_summary",
    )
    failures += _expect(results, "PBC04-no-enumeration", operation="abstain", decision="unresolved")
    for case_id, word in (
        ("PBC04-no-selection", "selection"),
        ("PBC04-no-enumeration", "population"),
    ):
        row = next(r for r in results if r["case_id"] == case_id)
        if not any(m.startswith(word) for m in row["reference"]["operation"]["missing"]):
            failures.append(f"{case_id}: the missing evidence must be named ({word})")
    return failures


def build_pbc05(folder: Path) -> list[dict]:
    a = folder / "intact-with-reference-label"
    b = folder / "parent-with-reference-label"
    wa = write_dataset(a, stats_over=3, enumerate_parent=False)
    wb = write_dataset(b, stats_over=8, enumerate_parent=False)
    return [
        make_case(
            a,
            "PBC05-intact-labelled-external",
            wa,
            enumeration=False,
            declared_role="external_reference_normalizer",
            selection=None,
        ),
        make_case(
            b,
            "PBC05-parent-labelled-external",
            wb,
            enumeration=False,
            declared_role="external_reference_normalizer",
            selection={"kind": "label_only", "label": "verified_training_reference"},
        ),
    ]


def check_pbc05(results: list[dict]) -> list[str]:
    failures = _expect(
        results,
        "PBC05-intact-labelled-external",
        operation="reuse",
        decision="supported",
        role="current_population_summary",
    )
    failures += _expect(
        results, "PBC05-parent-labelled-external", operation="abstain", decision="unresolved"
    )
    row = next(r for r in results if r["case_id"] == "PBC05-intact-labelled-external")
    if not row["reference"]["operation"].get("declared_role_note"):
        failures.append("a declared role that differs from the evidence must be noted and ignored")
    return failures


def build_pbc06(folder: Path) -> list[dict]:
    cases = []
    for kind in ("truncated", "non_finite", "wrong_dimension", "non_finite_statistics"):
        sub = folder / kind
        written = write_dataset(sub, stats_over=3, enumerate_parent=False, corrupt=kind)
        cases.append(
            make_case(
                sub, f"PBC06-{kind}", written, enumeration=False, declared_role=None, selection=None
            )
        )
    empty = folder / "empty"
    empty.mkdir(parents=True, exist_ok=True)
    (empty / "info.json").write_text(json.dumps(info_document()) + "\n")
    (empty / "stats.json").write_text(json.dumps({"observation.state": {}, "action": {}}) + "\n")
    cases.append(
        {
            "schema": "nisayon.population-case.v1",
            "case_id": "PBC06-empty",
            "root": str(empty),
            "files": [],
            "info": "info.json",
            "published_statistics": "stats.json",
            "features": ["observation.state", "action"],
            "episodes_stats": None,
            "declared_role": None,
            "selection_evidence": None,
            "interpretation_evidence": None,
            "provenance": "constructed control",
        }
    )
    return cases


def check_pbc06(results: list[dict]) -> list[str]:
    failures = []
    kinds = {}
    for row in results:
        ref = row["reference"]["operation"]
        prod = row["conventional"]["decision"]
        if ref["operation"] != "invalid" or ref["decision"] != "invalid":
            failures.append(
                f"{row['case_id']}: reference must be invalid, got {ref['operation']}/{ref['decision']}"
            )
        if prod["selected_operation"] != "invalid" or prod["status"] != "invalid":
            failures.append(
                f"{row['case_id']}: conventional must be invalid, got {prod['selected_operation']}/{prod['status']}"
            )
        validity = row["conventional"]["observations"]["validity"]
        kinds[row["case_id"]] = validity[0]["kind"] if validity else None
    if len(set(kinds.values())) < 4:
        failures.append(f"invalid reasons must stay distinct, got {kinds}")
    return failures


CONTROLS: tuple[Control, ...] = (
    Control(
        "PBC01-intact-current-population",
        "Does a valid summary of the complete current population permit reuse?",
        build_pbc01,
        check_pbc01,
    ),
    Control(
        "PBC02-current-population-mismatch",
        "Is a mismatching summary declared as current detected and recomputed?",
        build_pbc02,
        check_pbc02,
    ),
    Control(
        "PBC03-bound-external-reference",
        "Is an enumerated parent reference reused although the subset's moments differ?",
        build_pbc03,
        check_pbc03,
    ),
    Control(
        "PBC04-missing-role-or-selection",
        "Does missing binding evidence produce a named abstention?",
        build_pbc04,
        check_pbc04,
    ),
    Control(
        "PBC05-unchanged-label-changed-content",
        "Do decisions follow content rather than a role or selection label?",
        build_pbc05,
        check_pbc05,
    ),
    Control(
        "PBC06-empty-invalid-nonfinite",
        "Are empty, malformed, non-finite and unsupported inputs distinct invalid results?",
        build_pbc06,
        check_pbc06,
    ),
)


def run_population_controls(out_dir: Path) -> dict:
    """Build every control, run the reference and the conventional diagnostic, check both."""
    results = []
    for control in CONTROLS:
        folder = out_dir / control.name
        cases = control.build(folder)
        rows = []
        cache: dict = {}
        for case in cases:
            case_path = folder / f"{case['case_id']}.case.json"
            case_path.write_text(json.dumps(case, indent=2, allow_nan=False) + "\n")
            reference = assess_case(case)
            conventional = diagnose(case, cache=cache)
            comparison = assess_producer_record(conventional, reference)
            (folder / f"{case['case_id']}.reference.json").write_text(
                json.dumps(reference, indent=2, allow_nan=False) + "\n"
            )
            (folder / f"{case['case_id']}.conventional.json").write_text(
                json.dumps(conventional, indent=2, allow_nan=False) + "\n"
            )
            rows.append(
                {
                    "case_id": case["case_id"],
                    "reference": reference,
                    "conventional": conventional,
                    "comparison": comparison,
                }
            )
        failures = control.check(rows)
        results.append(
            {
                "name": control.name,
                "question": control.question,
                "cases": [
                    {
                        "case_id": r["case_id"],
                        "reference": {
                            "operation": r["reference"]["operation"]["operation"],
                            "decision": r["reference"]["operation"]["decision"],
                            "role": r["reference"].get("role", {}).get("role"),
                        },
                        "conventional": {
                            "operation": r["conventional"]["decision"]["selected_operation"],
                            "status": r["conventional"]["decision"]["status"],
                        },
                        "agree": r["comparison"].get("agrees"),
                    }
                    for r in rows
                ],
                "failures": failures,
                "ok": not failures,
            }
        )
    return {
        "schema": "nisayon.population-controls.summary.v1",
        "controls": results,
        "all_ok": all(r["ok"] for r in results),
        "note": "constructed controls; synthetic rows; no lineage or deployment claim",
    }


def render_population_controls(summary: dict) -> str:
    lines = []
    for control in summary["controls"]:
        lines.append(
            f"{'ok  ' if control['ok'] else 'FAIL'} {control['name']:<40} {control['question']}"
        )
        for case in control["cases"]:
            ref = case["reference"]
            lines.append(
                f"       {case['case_id']:<36} reference {ref['operation']}/{ref['decision']} ({ref['role']})  conventional {case['conventional']['operation']}/{case['conventional']['status']}  agree={case['agree']}"
            )
        for failure in control["failures"]:
            lines.append(f"       ! {failure}")
    lines.append("all ok" if summary["all_ok"] else "some controls failed")
    return "\n".join(lines)

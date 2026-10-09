"""Frozen controls NX1–NX8 for normalizer-execution-001, run against both workflows.

Each control is a ``nisayon.normalizer-case.v1`` document built here with constructed
statistics and rows (marked constructed), or with the retained LIBERO rows for the two real
runs. The expected operation and decision come from the contract, not from either workflow.
Property checks (a constant coordinate maps to 0, an action z-score clips, a JSON round trip
is exact, the inverse loses what the contract says it loses) are evaluated on the reference's
emulation and reported next to the decisions.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np

from . import conventional_normalizer as conventional
from . import normalizer_reference as reference

CONTROLS_SCHEMA = "nisayon.normalizer-controls.v1"
PACKET = Path(
    "/Users/danielwahnich/.codex/reports/nisayon-next-evidence-decision-2026-09-20-8i17bt5a/sources"
)

MODALITY = {
    "state": {"a": {"start": 0, "end": 1}, "b": {"start": 1, "end": 3}},
    "action": {"u": {"start": 0, "end": 2}},
}
GROUPS = {"state": ["a", "b"], "action": ["u"]}
CONFIG = {
    "state": {
        "modality_keys": ["a", "b"],
        "sin_cos_embedding_keys": None,
        "mean_std_embedding_keys": None,
    },
    "action": {"modality_keys": ["u"], "mean_std_embedding_keys": None},
}
CONTRACT = {
    "state": {
        "a": {"min": [0.0], "max": [2.0], "mean": [1.0], "std": [0.5], "q01": [0.1], "q99": [1.9]},
        "b": {
            "min": [-1.0, 10.0],
            "max": [1.0, 12.0],
            "mean": [0.0, 11.0],
            "std": [0.5, 0.5],
            "q01": [-0.9, 10.1],
            "q99": [0.9, 11.9],
        },
    },
    "action": {
        "u": {
            "min": [-0.9375, 0.0],
            "max": [0.9375, 1.0],
            "mean": [0.0, 0.5],
            "std": [0.4, 0.5],
            "q01": [-0.9, 0.0],
            "q99": [0.9, 1.0],
        }
    },
}
ROWS = {
    "state": [[0.5, -0.25, 10.5], [1.5, 0.75, 11.75], [2.0, 1.0, 12.0]],
    "action": [[0.0, 1.0], [-0.5, 0.25], [0.9375, 0.0]],
}


def _copy(value):
    return json.loads(json.dumps(value))


def _case(case_id: str, **overrides) -> dict:
    case = {
        "schema": reference.CASE_SCHEMA,
        "case_id": case_id,
        "embodiment": "syn",
        "groups": _copy(GROUPS),
        "modality": _copy(MODALITY),
        "config": _copy(CONFIG),
        "flags": {
            "use_percentiles": False,
            "clip_outliers": True,
            "apply_sincos_state_encoding": False,
            "use_relative_action": False,
        },
        "dtype": "float32",
        "rows": {"inline": _copy(ROWS), "constructed": True},
        "contract_statistics": {"grouped": _copy(CONTRACT)},
        "existing_statistics": {"grouped": _copy(CONTRACT)},
        "candidate_statistics": None,
        "override": False,
        "declared_operation": "keep",
        "provenance": "constructed control",
    }
    case.update(overrides)
    return case


def _alt() -> dict:
    """A candidate that differs from the contract on used coordinates."""
    alt = _copy(CONTRACT)
    alt["state"]["a"]["max"] = [3.0]
    alt["action"]["u"]["min"] = [-1.0, 0.0]
    return alt


def _real_rows() -> list[dict]:
    files = []
    for i in range(5):
        path = PACKET / f"groot-episode-{i:06d}.parquet"
        files.append(
            {
                "path": str(path),
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "frames": [0, 1, 2],
            }
        )
    return files


_MOMENTS: dict = {}


def five_file_moments() -> dict:
    """Population moments of the five retained episodes, grouped by modality.json (computed once).

    Float64 two-pass mean and population standard deviation, exact extremes and numpy linear
    quantiles over all 1,406 rows; the candidate that a naive replacement would install.
    """
    if _MOMENTS:
        return _MOMENTS
    from .parquet_reader import read_parquet

    columns: dict[str, list] = {"observation.state": [], "action": []}
    for i in range(5):
        data = read_parquet(PACKET / f"groot-episode-{i:06d}.parquet")
        for key in columns:
            columns[key].extend(data["columns"][key])
    modality = json.loads((PACKET / "groot-demo-modality.json").read_text())
    grouped: dict = {}
    for name, key in (("state", "observation.state"), ("action", "action")):
        matrix = np.asarray(columns[key], dtype=np.float64)
        stats = {
            "min": matrix.min(axis=0),
            "max": matrix.max(axis=0),
            "mean": matrix.mean(axis=0),
            "std": matrix.std(axis=0),
            "q01": np.quantile(matrix, 0.01, axis=0),
            "q99": np.quantile(matrix, 0.99, axis=0),
        }
        grouped[name] = {}
        for group, span in modality[name].items():
            grouped[name][group] = {
                stat: [float(v) for v in values[span["start"] : span["end"]]]
                for stat, values in stats.items()
            }
    _MOMENTS.update(grouped)
    return _MOMENTS


def _real_case(case_id: str, override: bool, declared: str) -> dict | None:
    if not (PACKET / "groot-demo-stats.json").exists():
        return None
    stats = str(PACKET / "groot-demo-stats.json")
    sha = hashlib.sha256((PACKET / "groot-demo-stats.json").read_bytes()).hexdigest()
    groups = {
        "state": ["x", "y", "z", "roll", "pitch", "yaw", "gripper"],
        "action": ["x", "y", "z", "roll", "pitch", "yaw", "gripper"],
    }
    return {
        "schema": reference.CASE_SCHEMA,
        "case_id": case_id,
        "embodiment": "libero",
        "groups": groups,
        "modality_json": str(PACKET / "groot-demo-modality.json"),
        "config": {
            "state": {
                "modality_keys": groups["state"],
                "sin_cos_embedding_keys": None,
                "mean_std_embedding_keys": None,
            },
            "action": {"modality_keys": groups["action"], "mean_std_embedding_keys": None},
        },
        "flags": {
            "use_percentiles": False,
            "clip_outliers": True,
            "apply_sincos_state_encoding": False,
            "use_relative_action": False,
        },
        "dtype": "float32",
        "rows": {"parquet": _real_rows()},
        "contract_statistics": {"stats_json": stats, "sha256": sha},
        "existing_statistics": {"stats_json": stats, "sha256": sha},
        "candidate_statistics": {"grouped": five_file_moments()},
        "override": override,
        "declared_operation": declared,
        "provenance": "retained LIBERO rows (frames 0-2 of each episode) under the declared local invocation",
    }


def build_controls() -> list[dict]:
    """The twenty-three frozen runs, each with its contract expectation and property checks."""
    controls: list[dict] = []
    alt = _alt()

    # NX1 selection precedence
    controls.append(
        {
            "id": "NX1a",
            "family": "NX1",
            "case": _case(
                "NX1a",
                candidate_statistics={"grouped": alt},
                override=False,
                declared_operation="keep",
            ),
            "expect": ("keep", "supported"),
            "checks": ["outcome:kept", "mirror_is_candidate"],
        }
    )
    controls.append(
        {
            "id": "NX1b",
            "family": "NX1",
            "case": _case(
                "NX1b",
                candidate_statistics={"grouped": alt},
                contract_statistics={"grouped": alt},
                override=True,
                declared_operation="replace",
            ),
            "expect": ("replace", "supported"),
            "checks": ["outcome:replaced"],
        }
    )
    controls.append(
        {
            "id": "NX1c",
            "family": "NX1",
            "case": _case(
                "NX1c",
                existing_statistics=None,
                candidate_statistics={"grouped": alt},
                contract_statistics={"grouped": alt},
                override=False,
                declared_operation="replace",
            ),
            "expect": ("replace", "supported"),
            "checks": ["outcome:installed", "install_independent_of_override"],
        }
    )

    # NX2 parent reference versus subset moments (real rows)
    real_replace = _real_case("NX2a", True, "replace")
    if real_replace is not None:
        controls.append(
            {
                "id": "NX2a",
                "family": "NX2",
                "case": real_replace,
                "expect": ("replace", "rejected"),
                "checks": ["witness_present"],
            }
        )
    only_quantiles = _copy(CONTRACT)
    only_quantiles["state"]["a"]["q01"] = [0.3]
    only_quantiles["action"]["u"]["q99"] = [0.5, 0.5]
    controls.append(
        {
            "id": "NX2b",
            "family": "NX2",
            "case": _case(
                "NX2b",
                candidate_statistics={"grouped": only_quantiles},
                override=True,
                declared_operation="replace",
            ),
            "expect": ("replace", "supported"),
            "checks": ["parameters_differ"],
        }
    )

    # NX3 declarations versus bytes
    for label in ("current", "parent", "training_reference"):
        controls.append(
            {
                "id": f"NX3a-{label}",
                "family": "NX3",
                "run": "NX3a",
                "case": _case(
                    "NX3a",
                    candidate_statistics={"grouped": alt},
                    override=False,
                    declared_operation="keep",
                    provenance=label,
                    declared_role=label,
                ),
                "expect": ("keep", "supported"),
                "checks": ["same_as:NX3a"],
            }
        )
    changed = _copy(CONTRACT)
    changed["state"]["b"]["max"] = [1.001, 12.0]
    controls.append(
        {
            "id": "NX3b",
            "family": "NX3",
            "case": _case(
                "NX3b",
                candidate_statistics={"grouped": changed},
                override=True,
                declared_operation="replace",
            ),
            "expect": ("replace", "rejected"),
            "checks": ["witness_present"],
        }
    )

    # NX4 actual mode versus inert label
    flags_label = {
        "use_percentiles": False,
        "clip_outliers": True,
        "apply_sincos_state_encoding": False,
        "use_relative_action": False,
        "use_mean_std": True,
    }
    controls.append(
        {
            "id": "NX4a",
            "family": "NX4",
            "case": _case("NX4a", flags=flags_label),
            "expect": ("keep", "supported"),
            "checks": ["mode:state.a=minmax", "mode:action.u=minmax"],
        }
    )
    config_ms = _copy(CONFIG)
    config_ms["state"]["mean_std_embedding_keys"] = ["a"]
    config_ms["action"]["mean_std_embedding_keys"] = ["u"]
    rows_z = {"state": [[2.5, 0.0, 11.0], [-1.0, 0.5, 10.5]], "action": [[0.9, 1.0], [-0.9, 0.0]]}
    controls.append(
        {
            "id": "NX4b",
            "family": "NX4",
            "case": _case("NX4b", config=config_ms, rows={"inline": rows_z, "constructed": True}),
            "expect": ("keep", "supported"),
            "checks": [
                "mode:state.a=meanstd",
                "mode:action.u=meanstd",
                "state_unclipped",
                "action_clipped",
            ],
        }
    )

    # NX5 constants, near-constants, zero and tiny std
    const = _copy(CONTRACT)
    const["state"]["b"]["min"] = [-1.0, 10.0]
    const["state"]["b"]["max"] = [1.0, 10.0]
    controls.append(
        {
            "id": "NX5a",
            "family": "NX5",
            "case": _case(
                "NX5a",
                contract_statistics={"grouped": const},
                existing_statistics={"grouped": const},
                rows={
                    "inline": {"state": [[0.5, 0.0, 10.0]], "action": [[0.0, 0.5]]},
                    "constructed": True,
                },
            ),
            "expect": ("keep", "supported"),
            "checks": ["zero_at:state.b.1", "inverse_min_at:state.b.1"],
        }
    )
    near = _copy(CONTRACT)
    near["state"]["b"]["min"] = [-1.0, 1000.0]
    near["state"]["b"]["max"] = [1.0, 1000.005]
    controls.append(
        {
            "id": "NX5b",
            "family": "NX5",
            "case": _case(
                "NX5b",
                contract_statistics={"grouped": near},
                existing_statistics={"grouped": near},
                rows={
                    "inline": {"state": [[0.5, 0.0, 1000.004]], "action": [[0.0, 0.5]]},
                    "constructed": True,
                },
            ),
            "expect": ("keep", "supported"),
            "checks": ["zero_at:state.b.1", "inverse_midpoint_at:state.b.1"],
        }
    )
    zero_std = _copy(CONTRACT)
    zero_std["state"]["a"]["std"] = [0.0]
    controls.append(
        {
            "id": "NX5c",
            "family": "NX5",
            "case": _case(
                "NX5c",
                config=config_ms,
                contract_statistics={"grouped": zero_std},
                existing_statistics={"grouped": zero_std},
                rows={
                    "inline": {"state": [[0.75, 0.0, 11.0]], "action": [[0.0, 0.5]]},
                    "constructed": True,
                },
            ),
            "expect": ("keep", "supported"),
            "checks": ["passthrough_at:state.a.0"],
        }
    )
    tiny = _copy(CONTRACT)
    tiny["state"]["a"]["std"] = [1e-40]
    controls.append(
        {
            "id": "NX5d",
            "family": "NX5",
            "case": _case(
                "NX5d",
                config=config_ms,
                contract_statistics={"grouped": tiny},
                existing_statistics={"grouped": tiny},
                rows={
                    "inline": {"state": [[0.75, 0.0, 11.0]], "action": [[0.0, 0.5]]},
                    "constructed": True,
                },
            ),
            "expect": ("invalid", "invalid"),
            "checks": ["non_finite_reason"],
            "conventional_expected": ("keep", "supported"),
            "conventional_note": "a float64 transcription stays finite (about 2.5e39) and cannot see the float32 overflow that the executed operation produces; this is a false acceptance of the conventional workflow on a dtype boundary",
        }
    )

    # NX6 clipping and domain-qualified equivalence
    outside = {"state": [[2.5, -1.5, 13.0], [-0.5, 1.5, 9.0]], "action": [[1.5, 2.0], [-2.0, -1.0]]}
    controls.append(
        {
            "id": "NX6a",
            "family": "NX6",
            "case": _case("NX6a", rows={"inline": outside, "constructed": True}),
            "expect": ("keep", "supported"),
            "checks": ["all_clipped_outputs_are_pm1"],
        }
    )
    flags_noclip = {
        "use_percentiles": False,
        "clip_outliers": False,
        "apply_sincos_state_encoding": False,
        "use_relative_action": False,
    }
    controls.append(
        {
            "id": "NX6b",
            "family": "NX6",
            "case": _case(
                "NX6b", rows={"inline": outside, "constructed": True}, flags=flags_noclip
            ),
            "expect": ("keep", "supported"),
            "checks": ["outputs_beyond_pm1"],
        }
    )
    controls.append(
        {
            "id": "NX6c",
            "family": "NX6",
            "case": _case("NX6c"),
            "expect": ("keep", "supported"),
            "checks": ["json_roundtrip_exact"],
        }
    )
    eligible = {
        "state": [[0.5, -0.25, 10.5], [1.5, 0.75, 11.75]],
        "action": [[0.0, 1.0], [-0.5, 0.25]],
    }
    controls.append(
        {
            "id": "NX6d",
            "family": "NX6",
            "case": _case("NX6d", rows={"inline": eligible, "constructed": True}),
            "expect": ("keep", "supported"),
            "checks": ["inverse_roundtrip_eligible", "inverse_loss_ineligible"],
        }
    )

    # NX7 missing, invalid, clean acceptance
    config_extra = _copy(CONFIG)
    config_extra["state"]["modality_keys"] = ["a", "b", "c"]
    controls.append(
        {
            "id": "NX7a",
            "family": "NX7",
            "case": _case(
                "NX7a", groups={"state": ["a", "b", "c"], "action": ["u"]}, config=config_extra
            ),
            "expect": ("invalid", "invalid"),
            "checks": [],
        }
    )
    no_std = _copy(CONTRACT)
    del no_std["state"]["a"]["std"]
    controls.append(
        {
            "id": "NX7b",
            "family": "NX7",
            "case": _case(
                "NX7b",
                contract_statistics={"grouped": no_std},
                existing_statistics={"grouped": no_std},
            ),
            "expect": ("invalid", "invalid"),
            "checks": [],
        }
    )
    controls.append(
        {
            "id": "NX7c-width",
            "family": "NX7",
            "run": "NX7c",
            "case": _case(
                "NX7c",
                rows={
                    "inline": {"state": [[0.5, -0.25]], "action": [[0.0, 0.5]]},
                    "constructed": True,
                },
            ),
            "expect": ("invalid", "invalid"),
            "checks": [],
        }
    )
    controls.append(
        {
            "id": "NX7c-nan",
            "family": "NX7",
            "run": "NX7c",
            "case": _case(
                "NX7c",
                rows={
                    "inline": {"state": [[0.5, float("nan"), 10.5]], "action": [[0.0, 0.5]]},
                    "constructed": True,
                },
            ),
            "expect": ("invalid", "invalid"),
            "checks": [],
        }
    )
    real_keep = _real_case("NX7d", False, "keep")
    if real_keep is not None:
        controls.append(
            {
                "id": "NX7d",
                "family": "NX7",
                "case": real_keep,
                "expect": ("keep", "supported"),
                "checks": ["useful_acceptance"],
            }
        )

    # NX8 digest-correct wrong call path
    digests = {
        "processing_gr00t_n1d7.py": "612558f74a2da6aab6293778a00d6c0805648bc2a8847ac525bc8263a85c901d",
        "state_action_processor.py": "0151dd0bb6cb727fd401bf78121efc532e7184f2575e6ef25294085f629ac145",
        "data_utils.py": "fa765b240295d9884ab62326c8a21465ae21e6f10133a4b68ac321e8101e4ab7",
    }
    controls.append(
        {
            "id": "NX8a",
            "family": "NX8",
            "case": _case(
                "NX8a",
                execution_binding={
                    "source_sha256": digests,
                    "claims_selection": True,
                    "calls": [
                        {"function": "_compute_normalization_parameters"},
                        {"function": "set_statistics"},
                    ],
                },
            ),
            "expect": ("abstain", "unresolved"),
            "checks": [],
        }
    )
    controls.append(
        {
            "id": "NX8b",
            "family": "NX8",
            "case": _case(
                "NX8b",
                execution_binding={
                    "source_sha256": digests,
                    "claims_selection": True,
                    "calls": [
                        {"function": "set_statistics"},
                        {"function": "apply_state"},
                        {"function": "apply_action"},
                    ],
                    "outputs_match_declared_expectations": True,
                },
            ),
            "expect": ("abstain", "unresolved"),
            "checks": [],
        }
    )
    return controls


# --- property checks --------------------------------------------------------------------------


def _loaded(case: dict) -> dict:
    return reference.load_case(_copy(case))


def _check(
    check: str, control: dict, report: dict, loaded: dict | None, results_by_run: dict
) -> tuple[bool, str]:
    decision = report["decision"]
    if check.startswith("outcome:"):
        want = check.split(":", 1)[1]
        got = (decision.get("effective") or {}).get(control["case"]["embodiment"])
        return got == want, f"outcome {got}"
    if check == "mirror_is_candidate":
        sel = reference.effective_statistics(loaded["_existing"], loaded["_candidate"], False)
        emb = control["case"]["embodiment"]
        ok = (
            sel["mirror"].get(emb) == loaded["_candidate"][emb]
            and sel["nested"][emb] == loaded["_existing"][emb]
        )
        return ok, "mirror holds the candidate while the nested state keeps the existing statistics"
    if check == "install_independent_of_override":
        a = reference.effective_statistics({}, loaded["_candidate"], False)["nested"]
        b = reference.effective_statistics({}, loaded["_candidate"], True)["nested"]
        return a == b, "absent embodiment installed with either override value"
    if check == "witness_present":
        return decision.get("witness") is not None, f"witness {decision.get('witness')}"
    if check == "parameters_differ":
        emb = control["case"]["embodiment"]
        return loaded["_candidate"][emb] != loaded[
            "_contract"
        ], "candidate parameters differ from the contract while the maps agree"
    if check.startswith("same_as:"):
        run = check.split(":", 1)[1]
        peers = results_by_run.get(run, [])
        key = (
            decision["operation"],
            decision["decision"],
            json.dumps(decision.get("witness"), sort_keys=True),
        )
        return all(p == key for p in peers) if peers else True, f"{len(peers)} label variants agree"
    if check.startswith("mode:"):
        spec, want = check.split(":", 1)[1].split("=")
        modality, group = spec.split(".")
        got = report["groups"][modality][group]["mode"]
        return got == want, f"{modality}.{group} mode {got}"
    if check in (
        "state_unclipped",
        "action_clipped",
        "all_clipped_outputs_are_pm1",
        "outputs_beyond_pm1",
        "useful_acceptance",
    ):
        expected = reference.expected_outputs(
            loaded["_contract"],
            loaded["config"],
            loaded["_flags"],
            loaded["_rows"]["by_group"],
            loaded["groups"],
        )
        if check == "state_unclipped":
            y = expected["state"]["a"]["outputs"]
            return bool(np.max(np.abs(y)) > 1.0), f"state.a max |out| {float(np.max(np.abs(y)))}"
        if check == "action_clipped":
            y = expected["action"]["u"]["outputs"]
            return bool(
                np.max(np.abs(y)) == 1.0 and np.any(np.abs(y) == 1.0)
            ), f"action.u max |out| {float(np.max(np.abs(y)))}"
        if check == "all_clipped_outputs_are_pm1":
            ok = True
            for modality, groups in expected.items():
                for group, entry in groups.items():
                    x = loaded["_rows"]["by_group"][modality][group]
                    p = entry["params"]
                    outside = (x < p["min"]) | (x > p["max"])
                    ok &= bool(np.all(np.abs(entry["outputs"][outside]) == 1.0))
            return ok, "every out-of-range coordinate maps to exactly ±1"
        if check == "outputs_beyond_pm1":
            worst = max(
                float(np.max(np.abs(e["outputs"]))) for g in expected.values() for e in g.values()
            )
            return worst > 1.0, f"max |out| {worst}"
        if check == "useful_acceptance":
            return decision["operation"] == "keep" and decision[
                "decision"
            ] == "supported", "keep supported on retained rows"
    if (
        check.startswith("zero_at:")
        or check.startswith("inverse_min_at:")
        or check.startswith("inverse_midpoint_at:")
        or check.startswith("passthrough_at:")
    ):
        kind, spec = check.split(":", 1)
        modality, group, k = spec.split(".")
        k = int(k)
        expected = reference.expected_outputs(
            loaded["_contract"],
            loaded["config"],
            loaded["_flags"],
            loaded["_rows"]["by_group"],
            loaded["groups"],
        )
        entry = expected[modality][group]
        y = entry["outputs"]
        x = loaded["_rows"]["by_group"][modality][group]
        p = entry["params"]
        if kind == "zero_at":
            return bool(np.all(y[:, k] == 0.0)), f"output {y[:, k].tolist()}"
        if kind == "passthrough_at":
            return bool(
                np.all(y[:, k] == x[:, k])
            ), f"output {y[:, k].tolist()} input {x[:, k].tolist()}"
        inv = reference.emulate_inverse_minmax(y, p)
        if kind == "inverse_min_at":
            return bool(
                np.all(inv[:, k] == p["min"][k])
            ), f"inverse {inv[:, k].tolist()} min {float(p['min'][k])}"
        mid = (p["min"][k] + p["max"][k]) / 2.0
        return bool(
            np.allclose(inv[:, k], mid, rtol=0, atol=1e-9)
        ), f"inverse {inv[:, k].tolist()} midpoint {float(mid)}"
    if check == "non_finite_reason":
        return "non-finite" in (decision.get("reason") or ""), decision.get("reason") or ""
    if check == "json_roundtrip_exact":
        text = json.dumps(loaded["_contract"])
        back = json.loads(text)
        eq = reference.maps_equivalent(
            loaded["_contract"],
            back,
            loaded["config"],
            loaded["_flags"],
            loaded["_rows"]["by_group"],
            loaded["groups"],
        )
        return back == loaded["_contract"] and eq[
            "equivalent"
        ], "statistics and outputs identical after json.dumps/json.loads"
    if check in ("inverse_roundtrip_eligible", "inverse_loss_ineligible"):
        expected = reference.expected_outputs(
            loaded["_contract"],
            loaded["config"],
            loaded["_flags"],
            loaded["_rows"]["by_group"],
            loaded["groups"],
        )
        worst_rel = 0.0
        loss = []
        for modality, groups in expected.items():
            for group, entry in groups.items():
                x = loaded["_rows"]["by_group"][modality][group].astype(np.float64)
                p = entry["params"]
                y = entry["outputs"]
                inv = reference.emulate_inverse_minmax(y, p)
                span = p["max"] - p["min"]
                inside = (x >= p["min"]) & (x <= p["max"]) & ~reference.constant_mask(p)
                bound = 2.0**-21 * span + 2.0**-22 * np.abs(x)
                err = np.abs(inv - x)
                worst_rel = max(
                    worst_rel, float(np.max(err[inside] / bound[inside])) if inside.any() else 0.0
                )
                outside = ~inside
                if outside.any():
                    loss.append(float(np.max(err[outside])))
        if check == "inverse_roundtrip_eligible":
            return worst_rel <= 1.0, f"worst error / bound on eligible coordinates {worst_rel:.3g}"
        probe = {"state": [[2.5, -1.5, 13.0]], "action": [[1.5, 2.0]]}
        x = {m: np.asarray(v, dtype=np.float32) for m, v in probe.items()}
        losses = []
        for modality, groups in expected.items():
            for group, entry in groups.items():
                span = MODALITY[modality][group]
                xx = x[modality][:, span["start"] : span["end"]]
                p = entry["params"]
                y = reference.emulate_minmax(xx, p, True)
                inv = reference.emulate_inverse_minmax(y, p)
                losses.append(float(np.max(np.abs(inv - xx))))
        return max(losses) > 0.1, f"clipped probe returns the bound, max loss {max(losses):.3g}"
    return False, f"unknown check {check}"


def run_normalizer_controls(out_dir: Path | None = None) -> dict:
    controls = build_controls()
    results_by_run: dict[str, list] = {}
    rows = []
    passed = 0
    conventional_agreements = 0
    conventional_v2_agreements = 0
    for control in controls:
        case = control["case"]
        report = reference.assess_case(case)
        decision = report["decision"]
        record = conventional.diagnose(_copy(case))
        record_v2 = conventional.diagnose(_copy(case), arithmetic="input")
        loaded = None
        if decision["operation"] not in ("invalid",):
            try:
                loaded = _loaded(case)
            except Exception:  # noqa: BLE001 - a malformed control cannot be loaded for property checks
                loaded = None
        run = control.get("run", control["id"])
        key = (
            decision["operation"],
            decision["decision"],
            json.dumps(decision.get("witness"), sort_keys=True),
        )
        results_by_run.setdefault(run, []).append(key)
        expected = tuple(control["expect"])
        reference_ok = (decision["operation"], decision["decision"]) == expected
        conv_expected = tuple(control.get("conventional_expected", expected))
        conv_got = (record["decision"]["selected_operation"], record["decision"]["status"])
        conventional_ok = conv_got == conv_expected
        checks = []
        for check in control["checks"]:
            try:
                ok, note = (
                    _check(check, control, report, loaded, results_by_run)
                    if loaded is not None
                    or check == "non_finite_reason"
                    or check.startswith("same_as:")
                    or check == "witness_present"
                    else (False, "no loaded case")
                )
            except Exception as error:  # noqa: BLE001 - report the failing check, do not hide it
                ok, note = False, f"check raised {type(error).__name__}: {error}"
            checks.append({"check": check, "ok": ok, "note": note})
        ok = reference_ok and conventional_ok and all(c["ok"] for c in checks)
        passed += ok
        conventional_agreements += conv_got == (decision["operation"], decision["decision"])
        conv_v2 = (record_v2["decision"]["selected_operation"], record_v2["decision"]["status"])
        conventional_v2_agreements += conv_v2 == (decision["operation"], decision["decision"])
        rows.append(
            {
                "id": control["id"],
                "family": control["family"],
                "expected": list(expected),
                "reference": [decision["operation"], decision["decision"]],
                "reference_reason": decision.get("reason"),
                "conventional": list(conv_got),
                "conventional_reason": record["decision"].get("reason"),
                "conventional_expected": list(conv_expected),
                "conventional_v2": list(conv_v2),
                "conventional_note": control.get("conventional_note"),
                "checks": checks,
                "pass": ok,
                "rows_provenance": report["rows"]["provenance"],
            }
        )
        if out_dir is not None:
            out_dir.mkdir(parents=True, exist_ok=True)
            (out_dir / f"{control['id']}.case.json").write_text(
                json.dumps(case, indent=2, allow_nan=True) + "\n"
            )
            (out_dir / f"{control['id']}.reference.json").write_text(
                json.dumps(report, indent=2) + "\n"
            )
            (out_dir / f"{control['id']}.conventional.json").write_text(
                json.dumps(record, indent=2) + "\n"
            )
    families = sorted({c["family"] for c in controls})
    summary = {
        "schema": CONTROLS_SCHEMA,
        "contract": reference.CONTRACT_ID,
        "reference": reference.module_identity(),
        "families": families,
        "runs": len({c.get("run", c["id"]) for c in controls}),
        "cases_evaluated": len(controls),
        "passed": passed,
        "conventional_agreements": conventional_agreements,
        "conventional_v2_agreements": conventional_v2_agreements,
        "conventional_v2_disagreements": [
            r["id"] for r in rows if r["conventional_v2"] != r["reference"]
        ],
        "conventional_disagreements": [
            r["id"] for r in rows if r["conventional"] != r["reference"]
        ],
        "results": rows,
    }
    return summary


def render_normalizer_controls(summary: dict) -> str:
    lines = [
        f"normalizer controls: {summary['passed']}/{summary['cases_evaluated']} cases pass ({summary['runs']} runs, {len(summary['families'])} families); conventional agrees on {summary['conventional_agreements']}"
    ]
    for row in summary["results"]:
        flag = "ok " if row["pass"] else "FAIL"
        lines.append(
            f"  {flag} {row['id']:22s} ref={row['reference'][0]}/{row['reference'][1]:10s} conv={row['conventional'][0]}/{row['conventional'][1]:10s} expected={row['expected'][0]}/{row['expected'][1]}"
        )
        for check in row["checks"]:
            if not check["ok"]:
                lines.append(f"       check failed: {check['check']}: {check['note']}")
    if summary["conventional_disagreements"]:
        lines.append(f"  conventional disagrees on: {summary['conventional_disagreements']}")
    return "\n".join(lines)

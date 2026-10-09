"""Assess an execution-lane normalizer store against the reference.

The execution lane seals a store under ``artifacts/normalizer-execution-001/producer-NNN``
with one run record per real operation and per control. Each record carries the input
arrays, the outer and nested statistics before and after ``set_statistics``, the call
records, the executed output arrays, the saved and reloaded state and the producer's
decision. This module reads those records, rebuilds the declared invocation as a
``nisayon.normalizer-case.v1`` case, recomputes every expected output with the reference,
and compares the executed arrays at 0 ulp, the selected state against the override rule,
the persistence claims, the call record and the decision.

It reads the store and decides nothing from the producer's own verdict; expected decisions
come from the contract. The producer's statistics digest convention (sha256 of compact,
key-sorted JSON) is reproduced here rather than imported.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np

from . import normalizer_reference as reference
from .schema import Malformed, load_json

STORE_ASSESSMENT_SCHEMA = "nisayon.normalizer-store-assessment.v1"
OPERATION_MAP = {
    "keep_existing": "keep",
    "replace_with_candidate": "replace",
    "install_when_absent": "replace",
    "abstain": "abstain",
    "invalid": "invalid",
}
EXPECTED_CONTROLS = {
    "NX1a": ("keep", "supported"),
    "NX1b": ("replace", "supported"),
    "NX1c": ("replace", "supported"),
    "NX2a": ("replace", "rejected"),
    "NX2b": ("replace", "supported"),
    "NX3a": ("keep", "supported"),
    "NX3b": ("replace", "rejected"),
    "NX4a": ("keep", "supported"),
    "NX4b": ("keep", "supported"),
    "NX5a": ("keep", "supported"),
    "NX5b": ("keep", "supported"),
    "NX5c": ("keep", "supported"),
    "NX5d": ("invalid", "invalid"),
    "NX6a": ("keep", "supported"),
    "NX6b": ("keep", "supported"),
    "NX6c": ("keep", "supported"),
    "NX6d": ("keep", "supported"),
    "NX7a": ("invalid", "invalid"),
    "NX7b": ("invalid", "invalid"),
    "NX7c": ("invalid", "invalid"),
    "NX7d": ("keep", "supported"),
    "NX8a": ("abstain", "unresolved"),
    "NX8b": ("abstain", "unresolved"),
}
EXPECTED_REAL = {"real-keep": ("keep", "supported"), "real-replace": ("replace", "rejected")}


def canonical_digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _array(record: dict, dtype: str) -> np.ndarray:
    return np.asarray(record["values"], dtype=np.dtype(dtype)).reshape(record["shape"])


def _array_digest(array: np.ndarray) -> str:
    return hashlib.sha256(np.ascontiguousarray(array).tobytes()).hexdigest()


def _strip(statistics: dict) -> dict:
    """Keep only the six statistic keys, the form the reference reads."""
    return {
        modality: {
            group: {k: list(v) for k, v in stats.items() if k in reference.STATS}
            for group, stats in groups.items()
        }
        for modality, groups in statistics.items()
        if modality in ("state", "action")
    }


def _resolve_statistics(run: dict, wanted: str | None, embodiment: str) -> dict | None:
    """Find the statistics set whose producer digest equals ``wanted`` among the recorded sets."""
    if wanted is None:
        return None
    selection = run["execution"]["selection"]
    for key in (
        "constructor_nested_statistics",
        "selected_outer_statistics",
        "selected_nested_statistics",
    ):
        candidate = selection.get(key) or {}
        if canonical_digest(candidate) == wanted and embodiment in candidate:
            return candidate[embodiment]
    extra = run.get("statistics") or {}
    for value in extra.values():
        if canonical_digest(value) == wanted and embodiment in value:
            return value[embodiment]
    return None


def build_case(run: dict, *, modality_map: dict | None) -> tuple[dict, list[str]]:
    """Rebuild the declared invocation from a run record; return the case and any gaps."""
    gaps: list[str] = []
    setup = run["setup"]
    settings = setup.get("settings") or {}
    execution = run.get("execution") or (run.get("observations") or {}).get("execution")
    if not isinstance(execution, dict):
        raise Malformed("run.execution", "no execution record")
    selection = execution["selection"]
    embodiment = selection.get("embodiment")
    if not embodiment:
        raise Malformed("run.execution.selection", "no embodiment")
    inputs = run.get("inputs")
    dtype = settings.get("input_dtype", "float32")
    if not isinstance(inputs, dict):
        raise Malformed("run.inputs", "input arrays are not recorded")
    groups = {m: list(inputs[m].keys()) for m in ("state", "action") if m in inputs}
    modality: dict = {}
    inline: dict = {}
    for m, names in groups.items():
        modality[m] = {}
        cursor = 0
        columns = []
        for group in names:
            array = _array(inputs[m][group], dtype)
            modality[m][group] = {"start": cursor, "end": cursor + array.shape[1]}
            cursor += array.shape[1]
            columns.append(array)
        inline[m] = np.concatenate(columns, axis=1).tolist()
    if modality_map is not None:
        for m in groups:
            if {g: modality_map[m][g] for g in groups[m]} != modality[m]:
                gaps.append(f"{m}: recorded group widths differ from modality.json slices")
    config = setup.get("modality_configs") or execution.get("modality_configs")
    if config is None:
        config = {
            m: {
                "modality_keys": names,
                "sin_cos_embedding_keys": None,
                "mean_std_embedding_keys": None,
            }
            for m, names in groups.items()
        }
        gaps.append("modality configuration not recorded in the run; selector keys assumed None")
    else:
        config = {
            m: {
                "modality_keys": names,
                "sin_cos_embedding_keys": (config.get(embodiment, config).get(m) or {}).get(
                    "sin_cos_embedding_keys"
                ),
                "mean_std_embedding_keys": (config.get(embodiment, config).get(m) or {}).get(
                    "mean_std_embedding_keys"
                ),
            }
            for m, names in groups.items()
        }
    existing_all = selection.get("constructor_nested_statistics") or {}
    existing = _strip(existing_all[embodiment]) if embodiment in existing_all else None
    candidate_all = selection.get("selected_outer_statistics") or {}
    candidate = _strip(candidate_all[embodiment]) if embodiment in candidate_all else None
    obligation = _resolve_statistics(run, setup.get("obligation_sha256"), embodiment)
    if obligation is None:
        gaps.append("obligation statistics not recoverable from the run by digest")
    case = {
        "schema": reference.CASE_SCHEMA,
        "case_id": run["id"],
        "embodiment": embodiment,
        "groups": groups,
        "modality": modality,
        "config": config,
        "flags": {
            "use_percentiles": bool(settings.get("use_percentiles", False)),
            "clip_outliers": bool(settings.get("clip_outliers", True)),
            "apply_sincos_state_encoding": bool(settings.get("apply_sincos_state_encoding", False)),
            "use_relative_action": bool(settings.get("use_relative_action", False)),
        },
        "dtype": dtype,
        "rows": {"inline": inline, "constructed": "real" not in run["id"]},
        "contract_statistics": {"grouped": _strip(obligation)} if obligation else None,
        "existing_statistics": {"grouped": existing} if existing else None,
        "candidate_statistics": {"grouped": candidate} if candidate else None,
        "override": bool(setup.get("override", False)),
        "declared_operation": OPERATION_MAP.get(setup.get("operation")),
        "provenance": f"rebuilt from the execution store run {run['id']}",
    }
    return case, gaps


def _infer_modes(case: dict, execution: dict) -> list[tuple[str, str, str]]:
    """When the run record omits the selector keys, find which groups executed mean/std.

    The record's outputs are compared with both emulations; a group that matches mean/std
    and not min/max is reported as inferred. A group matching neither stays min/max and the
    0-ulp comparison reports the difference.
    """
    try:
        loaded = reference.load_case(json.loads(json.dumps(case)))
    except Malformed:
        return []
    active = reference.effective_statistics(
        loaded["_existing"], loaded["_candidate"], bool(case.get("override", False))
    )
    embodiment = case["embodiment"]
    if embodiment not in active["nested"]:
        return []
    statistics = active["nested"][embodiment]
    inferred = []
    for modality, names in case["groups"].items():
        for group in names:
            observed = (execution.get("outputs") or {}).get(modality, {}).get(group)
            stats = (statistics.get(modality) or {}).get(group)
            if observed is None or stats is None:
                continue
            try:
                params = reference.group_parameters(
                    stats, use_percentiles=loaded["_flags"]["use_percentiles"], path=group
                )
            except Malformed:
                continue
            x = loaded["_rows"]["by_group"][modality][group]
            if x.shape[1] != params["dim"]:
                continue
            try:
                got = np.asarray(
                    [[_float(v) for v in row] for row in observed["values"]], dtype=x.dtype
                )
            except (TypeError, ValueError):
                continue
            minmax = reference.emulate_minmax(
                x, params, reference.clip_applies(modality, "minmax", loaded["_flags"])
            )
            meanstd = reference.emulate_meanstd(
                x, params, reference.clip_applies(modality, "meanstd", loaded["_flags"])
            )
            same_minmax = got.shape == minmax.shape and np.array_equal(got, minmax, equal_nan=True)
            same_meanstd = got.shape == meanstd.shape and np.array_equal(
                got, meanstd, equal_nan=True
            )
            if same_meanstd and not same_minmax:
                inferred.append((modality, group, "meanstd"))
    return inferred


def _float(value: object) -> float:
    if isinstance(value, str):
        return {"NaN": float("nan"), "Infinity": float("inf"), "-Infinity": float("-inf")}[value]
    return float(value)


def assess_run(run: dict, *, modality_map: dict | None, persistence_dir: Path | None) -> dict:
    """Recompute the run with the reference and compare every executed claim."""
    result: dict = {"run_id": run["id"], "process_status": run.get("process_status")}
    try:
        case, gaps = build_case(run, modality_map=modality_map)
    except (Malformed, KeyError, TypeError, ValueError) as error:
        result["status"] = "not_rebuilt"
        result["reason"] = f"{type(error).__name__}: {error}"
        return result
    result["gaps"] = gaps
    execution = run.get("execution") or (run.get("observations") or {}).get("execution")
    inferred = _infer_modes(case, execution)
    if inferred:
        for modality, group, _mode in inferred:
            case["config"][modality]["mean_std_embedding_keys"] = sorted(
                set(case["config"][modality].get("mean_std_embedding_keys") or []) | {group}
            )
        result["modes_inferred_from_outputs"] = [f"{m}.{g}={mode}" for m, g, mode in inferred]
    report = reference.assess_case(case)
    result["reference"] = {
        "operation": report["decision"]["operation"],
        "decision": report["decision"]["decision"],
        "reason": report["decision"]["reason"],
        "witness": report["decision"].get("witness"),
        "effective": report["decision"].get("effective"),
    }
    selection = execution["selection"]
    embodiment = case["embodiment"]
    # outputs at 0 ulp
    outputs = {}
    all_match = True
    if report["decision"]["operation"] != "invalid":
        loaded = reference.load_case(json.loads(json.dumps(case)))
        active = reference.effective_statistics(
            loaded["_existing"],
            loaded["_candidate"],
            loaded["override"] if "override" in loaded else case["override"],
        )
        expected = reference.expected_outputs(
            active["nested"][embodiment],
            loaded["config"],
            loaded["_flags"],
            loaded["_rows"]["by_group"],
            loaded["groups"],
        )
        for modality, names in case["groups"].items():
            for group in names:
                observed = (execution.get("outputs") or {}).get(modality, {}).get(group)
                if observed is None:
                    outputs[f"{modality}.{group}"] = {"status": "missing"}
                    all_match = False
                    continue
                exp = expected[modality][group]["outputs"]
                got = np.asarray(
                    [[_float(v) for v in row] for row in observed["values"]], dtype=exp.dtype
                )
                comparison = reference.compare_arrays(exp, got, path=f"{modality}.{group}")
                comparison["mode"] = expected[modality][group]["mode"]
                comparison["dtype_recorded"] = observed.get("dtype")
                comparison["digest_recorded"] = observed.get("bytes_sha256")
                comparison["digest_expected"] = _array_digest(exp)
                if comparison["status"] != "matches" or observed.get("dtype") != str(exp.dtype):
                    all_match = False
                outputs[f"{modality}.{group}"] = comparison
        # selected state against the override rule
        nested_after = (selection.get("selected_nested_statistics") or {}).get(embodiment)
        outer_after = (selection.get("selected_outer_statistics") or {}).get(embodiment)
        result["selection"] = {
            "outcome": active["outcome"].get(embodiment),
            "nested_matches_rule": _strip(nested_after or {}) == active["nested"].get(embodiment)
            if nested_after
            else False,
            "outer_matches_mirror": _strip(outer_after or {}) == active["mirror"].get(embodiment)
            if outer_after
            else active["mirror"].get(embodiment) is None,
            "outer_equals_nested": canonical_digest(nested_after) == canonical_digest(outer_after)
            if nested_after and outer_after
            else None,
        }
        # persistence
        persistence: dict = {"claimed": run.get("persistence_comparison") is not None}
        reloaded = execution.get("reloaded")
        if reloaded:
            persistence["reloaded_nested_equals_selected"] = canonical_digest(
                reloaded.get("nested_statistics")
            ) == canonical_digest(selection.get("selected_nested_statistics"))
            same = True
            for modality, names in case["groups"].items():
                for group in names:
                    a = (
                        (execution.get("outputs") or {})
                        .get(modality, {})
                        .get(group, {})
                        .get("bytes_sha256")
                    )
                    b = (reloaded.get(modality) or {}).get(group, {}).get("bytes_sha256")
                    same &= a is not None and a == b
            persistence["reloaded_outputs_equal_outputs"] = same
        saved = execution.get("saved")
        if saved and persistence_dir is not None and (persistence_dir / "statistics.json").exists():
            on_disk = load_json(persistence_dir / "statistics.json")
            persistence["statistics_json_equals_selected_nested"] = canonical_digest(
                on_disk
            ) == canonical_digest(selection.get("selected_nested_statistics"))
            persistence["statistics_json_sha256"] = _sha(persistence_dir / "statistics.json")
        result["persistence"] = persistence
    result["outputs"] = outputs
    result["outputs_all_match"] = all_match
    calls = [c.get("callable") for c in execution.get("call_records") or []]
    statuses = {c.get("callable"): c.get("status") for c in execution.get("call_records") or []}
    result["call_record"] = {
        "callables": calls,
        "selection_called": any("set_statistics" in c for c in calls),
        "transform_called": any(c.endswith("apply") for c in calls),
        "all_returned": all(s == "returned" for s in statuses.values()) if statuses else False,
        "network_attempts": (execution.get("network") or {}).get("attempts"),
    }
    decision = run.get("decision") or {}
    producer_record = {
        "decision": {
            "selected_operation": decision.get("operation"),
            "status": decision.get("status"),
        }
    }
    result["producer"] = {
        "operation": decision.get("operation"),
        "status": decision.get("status"),
        "reason": decision.get("reason"),
        "obligations": decision.get("obligations"),
    }
    result["comparison"] = reference.assess_producer(producer_record, report)
    expected_pair = EXPECTED_REAL.get(run["id"]) or EXPECTED_CONTROLS.get(run["id"].split("-")[0])
    if run["id"].split("-")[0] == "NX1b":
        # contract v1.2: graded against the obligation the record declares
        expected_pair = (
            ("replace", "supported")
            if run["setup"].get("obligation_sha256") == run["setup"].get("candidate_sha256")
            else ("replace", "rejected")
        )
    result["expected_under_contract"] = list(expected_pair) if expected_pair else None
    result["producer_matches_contract"] = (
        (OPERATION_MAP.get(decision.get("operation")), decision.get("status")) == expected_pair
        if expected_pair
        else None
    )
    result["reference_matches_contract"] = (
        (report["decision"]["operation"], report["decision"]["decision"]) == expected_pair
        if expected_pair
        else None
    )
    return result


def _assess_special(run: object, store: Path, run_id: str) -> dict | None:
    """Records that carry no numeric execution of their own: aliases, observed-invalid inputs,
    binding controls and the domain property. Each is checked for what it claims."""
    if not isinstance(run, dict):
        return None
    status = run.get("process_status")
    decision = run.get("decision") or {}
    expected = EXPECTED_CONTROLS.get(run_id.split("-")[0])
    base = {
        "run_id": run_id,
        "process_status": status,
        "producer": {
            "operation": decision.get("operation"),
            "status": decision.get("status"),
            "reason": decision.get("reason"),
        },
        "expected_under_contract": list(expected) if expected else None,
    }
    if status == "reused_retained_execution":
        evidence = run.get("evidence") or {}
        target = store / evidence.get("path", "")
        ok = target.exists() and _sha(target) == evidence.get("sha256")
        if run_id.split("-")[0] == "NX2a":
            # contract v1.2: either half of NX2a may be carried by the corresponding real run
            expected = EXPECTED_REAL.get(target.stem, expected)
            base["expected_under_contract"] = list(expected) if expected else None
        base.update(
            kind="alias",
            evidence=evidence,
            evidence_digest_verified=ok,
            note="decision copied from the referenced real run; assessed there",
        )
        base["producer_matches_contract"] = (
            (OPERATION_MAP.get(decision.get("operation")), decision.get("status")) == expected
            if expected
            else None
        )
        return base
    if status == "completed_with_observed_invalid_input":
        observations = run.get("observations") or {}
        base.update(
            kind="observed_invalid",
            observations={k: v for k, v in observations.items() if k != "execution"},
        )
        executed = "execution" in observations
        base["executed_source_bodies"] = executed
        if executed:
            outputs = observations["execution"].get("outputs") or {}
            base["non_finite_outputs"] = {
                f"{m}.{g}": not v.get("finite", True)
                for m, groups in outputs.items()
                for g, v in groups.items()
            }
            base["inputs_recorded"] = run.get("inputs") is not None
        base["producer_matches_contract"] = (
            (OPERATION_MAP.get(decision.get("operation")), decision.get("status")) == expected
            if expected
            else None
        )
        base["reason_wording"] = (
            "the reason names the input as the violation"
            if "input violates" in (decision.get("reason") or "")
            else None
        )
        return base
    if status == "completed_without_numeric_call":
        base.update(
            kind="binding",
            attached_expected_arrays=run.get("attached_expected_arrays"),
            numeric_call_made=False,
        )
        base["producer_matches_contract"] = (
            (OPERATION_MAP.get(decision.get("operation")), decision.get("status")) == expected
            if expected
            else None
        )
        return base
    if decision.get("operation") == "domain_property":
        observations = run.get("observations") or {}
        eligible_in = observations.get("eligible_input", {}).get("values")
        eligible_out = observations.get("eligible_roundtrip", {}).get("values")
        ineligible_in = observations.get("ineligible_input", {}).get("values")
        ineligible_out = observations.get("ineligible_roundtrip", {}).get("values")
        base.update(
            kind="domain_property",
            eligible_roundtrip_exact=eligible_in == eligible_out,
            ineligible_loss=ineligible_in != ineligible_out,
            observations={
                "eligible": [eligible_in, eligible_out],
                "ineligible": [ineligible_in, ineligible_out],
            },
            note="statistics of the property run are not in the record; the observed values are checked as a round trip only",
        )
        base["producer_matches_contract"] = bool(
            base["eligible_roundtrip_exact"] and base["ineligible_loss"]
        )
        return base
    return None


def _row_identity(store: Path, runs: dict, packet: Path | None) -> dict:
    """Bind the real runs' input arrays to the retained Parquet rows named by the membership."""
    membership_file = store / "observations" / "membership-and-coverage.json"
    if not membership_file.exists():
        return {"status": "no membership record"}
    membership = (load_json(membership_file) or {}).get("membership") or []
    from .parquet_reader import read_parquet

    files: dict = {}
    result: dict = {"membership_rows": len(membership), "runs": {}}
    for run_id in ("real-keep", "real-replace"):
        path = store / "runs" / f"{run_id}.json"
        if not path.exists():
            continue
        run = load_json(path)
        inputs = run.get("inputs") or {}
        ok = True
        detail = []
        for modality, key in (("state", "observation.state"), ("action", "action")):
            groups = inputs.get(modality) or {}
            if not groups:
                ok = False
                detail.append(f"{modality}: no inputs")
                continue
            recorded = np.concatenate(
                [
                    np.asarray(v["values"], dtype=np.float32).reshape(v["shape"])
                    for v in groups.values()
                ],
                axis=1,
            )
            rows = []
            for entry in membership:
                episode = int(entry["episode_index"])
                if episode not in files:
                    candidates = [
                        store
                        / "inputs"
                        / "sources"
                        / f"episode-{episode}"
                        / f"groot-episode-{episode:06d}.parquet"
                    ]
                    if packet is not None:
                        candidates.append(packet / f"groot-episode-{episode:06d}.parquet")
                    source = next((c for c in candidates if c.exists()), None)
                    files[episode] = read_parquet(source) if source else None
                data = files[episode]
                if data is None:
                    ok = False
                    detail.append(f"episode {episode}: parquet not retained")
                    break
                rows.append(data["columns"][key][int(entry["frame_index"])])
            if len(rows) != len(membership):
                continue
            retained = np.asarray(rows, dtype=np.float32)
            same = retained.shape == recorded.shape and np.array_equal(retained, recorded)
            ok &= bool(same)
            detail.append(
                f"{modality}: {'identical' if same else 'DIFFERS'} ({recorded.shape[0]} rows)"
            )
        result["runs"][run_id] = {"bound": ok, "detail": detail}
    result["parquet_sha256"] = {str(k): v["sha256"] for k, v in files.items() if v}
    return result


def _conventional_on_real_runs(store: Path) -> dict:
    """The competing workflow's decision on the producer's exact real rows and statistics."""
    from . import conventional_normalizer as conventional

    result: dict = {}
    for run_id in ("real-keep", "real-replace"):
        path = store / "runs" / f"{run_id}.json"
        if not path.exists():
            continue
        try:
            case, _gaps = build_case(load_json(path), modality_map=None)
        except (Malformed, KeyError, TypeError, ValueError) as error:
            result[run_id] = {"status": "not_rebuilt", "reason": str(error)}
            continue
        record = conventional.diagnose(case)
        result[run_id] = {
            "operation": record["decision"]["selected_operation"],
            "status": record["decision"]["status"],
            "reason": record["decision"]["reason"],
        }
    return result


def _candidate_agreement(store: Path) -> dict:
    """The producer's fresh five-episode moments against this lane's own computation (T1)."""
    membership_file = store / "observations" / "membership-and-coverage.json"
    if not membership_file.exists():
        return {"status": "no membership record"}
    fresh = (load_json(membership_file) or {}).get("fresh_subset_statistics")
    if not isinstance(fresh, dict):
        return {"status": "no fresh statistics in the record"}
    try:
        from .normalizer_controls import five_file_moments

        mine = five_file_moments()
    except (OSError, Malformed) as error:
        return {"status": f"own moments unavailable: {error}"}
    modality = load_json(store / "inputs" / "sources" / "modality" / "groot-demo-modality.json")
    worst = 0.0
    for name, key in (("state", "observation.state"), ("action", "action")):
        for group, span in modality[name].items():
            for stat in reference.STATS:
                theirs = np.asarray(fresh[key][stat][span["start"] : span["end"]], dtype=np.float64)
                ours = np.asarray(mine[name][group][stat], dtype=np.float64)
                rel = np.abs(theirs - ours) / np.maximum(np.abs(ours), 1e-6)
                worst = max(worst, float(rel.max()))
    return {"status": "compared", "worst_relative_difference": worst, "within_1e-5": worst <= 1e-5}


def assess_store(store: Path, *, packet: Path | None = None) -> dict:
    store = Path(store)
    out: dict = {
        "schema": STORE_ASSESSMENT_SCHEMA,
        "contract": reference.CONTRACT_ID,
        "store": str(store),
        "reference": reference.module_identity(),
    }
    seal = store / "seal.json"
    out["sealed"] = seal.exists()
    if seal.exists():
        sealed = load_json(seal)
        out["seal"] = sealed
        checks = {}
        for key in ("summary", "frozen_case", "artifact_manifest"):
            entry = sealed.get(key) if isinstance(sealed, dict) else None
            if isinstance(entry, dict) and (store / entry.get("path", "")).exists():
                checks[entry["path"]] = _sha(store / entry["path"]) == entry.get("sha256")
        manifest_path = (
            (sealed.get("artifact_manifest") or {}).get("path")
            if isinstance(sealed, dict)
            else None
        )
        if manifest_path and (store / manifest_path).exists():
            manifest = load_json(store / manifest_path)
            entries = manifest.get("files") if isinstance(manifest, dict) else None
            bad: list = []
            if isinstance(entries, list):
                for entry in entries:
                    path = store / entry.get("path", "")
                    if not path.exists() or _sha(path) != entry.get("sha256"):
                        bad.append(entry.get("path"))
                checks["manifest_entries"] = len(entries)
                checks["manifest_entries_bad"] = bad
            elif isinstance(entries, dict):
                bad = [
                    name
                    for name, digest in entries.items()
                    if not (store / name).exists() or _sha(store / name) != digest
                ]
                checks["manifest_entries"] = len(entries)
                checks["manifest_entries_bad"] = bad
        out["seal_checks"] = checks
    modality_map = None
    candidates = [store / "inputs/sources/modality/groot-demo-modality.json"]
    if packet is not None:
        candidates.append(packet / "groot-demo-modality.json")
    for path in candidates:
        if path.exists():
            modality_map = load_json(path)
            out["modality_json_sha256"] = _sha(path)
            break
    runs = []
    for directory in ("runs", "controls"):
        if (store / directory).exists():
            runs.extend(sorted((store / directory).glob("*.json")))
    out["runs"] = {}
    counts = {
        "useful_acceptance": 0,
        "false_acceptance": 0,
        "false_refusal": 0,
        "unjustified_replacement": 0,
        "unjustified_reuse": 0,
        "unresolved": 0,
        "invalid": 0,
        "agreements": 0,
        "compared": 0,
        "not_rebuilt": 0,
    }
    for path in runs:
        run = load_json(path)
        special = _assess_special(run, store, path.stem)
        if special is not None:
            out["runs"][path.stem] = special
            continue
        if not isinstance(run, dict) or "setup" not in run:
            out["runs"][path.stem] = {
                "run_id": path.stem,
                "status": "not_a_run",
                "keys": sorted(run) if isinstance(run, dict) else None,
            }
            continue
        result = assess_run(
            run,
            modality_map=modality_map if "real" in path.stem else None,
            persistence_dir=store / "persistence" / path.stem,
        )
        result["record_sha256"] = _sha(path)
        out["runs"][path.stem] = result
        comparison = result.get("comparison") or {}
        if comparison.get("status") == "compared":
            counts["compared"] += 1
            counts["agreements"] += bool(comparison["agrees"])
            for key, value in comparison["counts"].items():
                counts[key] += bool(value)
        elif result.get("status") == "not_rebuilt":
            counts["not_rebuilt"] += 1
    out["counts"] = counts
    out["row_identity"] = _row_identity(store, out["runs"], packet)
    out["conventional_on_real_runs"] = _conventional_on_real_runs(store)
    out["candidate_agreement"] = _candidate_agreement(store)
    out["real_runs_outputs_all_match"] = all(
        r.get("outputs_all_match") for k, r in out["runs"].items() if k.startswith("real")
    )
    out["producer_contract_mismatches"] = [
        k for k, r in out["runs"].items() if r.get("producer_matches_contract") is False
    ]
    out["reference_contract_mismatches"] = [
        k for k, r in out["runs"].items() if r.get("reference_matches_contract") is False
    ]
    return out


def render(assessment: dict) -> str:
    lines = [
        f"store {assessment['store']}: sealed={assessment['sealed']} counts={assessment['counts']}"
    ]
    for run_id, r in assessment["runs"].items():
        if r.get("status") == "not_rebuilt":
            lines.append(f"  {run_id:14s} not rebuilt: {r['reason']}")
            continue
        if r.get("status") == "not_a_run":
            lines.append(f"  {run_id:14s} not a run record: keys {r.get('keys')}")
            continue
        if r.get("kind"):
            p = r["producer"]
            lines.append(
                f"  {run_id:14s} {r['kind']}: producer={p['operation']}/{p['status']} expected={r['expected_under_contract']} matches={r.get('producer_matches_contract')}"
            )
            continue
        p = r["producer"]
        ref = r["reference"]
        lines.append(
            f"  {run_id:14s} producer={p['operation']}/{p['status']} reference={ref['operation']}/{ref['decision']} outputs_match={r['outputs_all_match']} expected={r['expected_under_contract']} gaps={r['gaps']}"
        )
    if assessment["producer_contract_mismatches"]:
        lines.append(
            f"  producer differs from the contract on: {assessment['producer_contract_mismatches']}"
        )
    if assessment["reference_contract_mismatches"]:
        lines.append(
            f"  reference differs from the contract on: {assessment['reference_contract_mismatches']}"
        )
    return "\n".join(lines)

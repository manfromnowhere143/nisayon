"""Run and seal the population-binding producer against frozen inputs and controls."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import shutil
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from nisayon.engine.io import digest, file_digest, write_json
from nisayon.engine.population_binding import decide_population_binding
from nisayon.engine.store import create_manifest, verify_manifest

CASE_SCHEMA = "nisayon.population-binding-case.v1"
CASE_CORRECTION_SCHEMA = "nisayon.population-binding-case.v2"
CASE_LOCATOR_CORRECTION_SCHEMA = "nisayon.population-binding-case.v3"
SUMMARY_SCHEMA = "nisayon.population-binding-summary.v1"
SEAL_SCHEMA = "nisayon.population-binding-seal.v1"


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def _constant(token: str) -> None:
    raise ValueError(f"Non-finite JSON constant: {token}")


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_bytes(), object_pairs_hook=_pairs, parse_constant=_constant)
    if not isinstance(value, dict):
        raise ValueError(f"JSON input must be an object: {path}")
    return value


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open("rb") as stream:
        for number, payload in enumerate(stream, 1):
            value = json.loads(payload, object_pairs_hook=_pairs, parse_constant=_constant)
            if not isinstance(value, dict):
                raise ValueError(f"JSONL row {number} is not an object: {path}")
            rows.append(value)
    if not rows:
        raise ValueError(f"JSONL input is empty: {path}")
    return rows


def _load_case(
    repo: Path, case_path: Path, seen: frozenset[Path] = frozenset()
) -> tuple[dict[str, Any], list[Path]]:
    resolved_case_path = case_path.resolve()
    if resolved_case_path in seen:
        raise ValueError("Corrected case inheritance contains a cycle")
    description = _read_json(case_path)
    if description.get("schema") == CASE_SCHEMA:
        return description, []
    if description.get("schema") not in {
        CASE_CORRECTION_SCHEMA,
        CASE_LOCATOR_CORRECTION_SCHEMA,
    }:
        return description, []
    inherited = description.get("inherits")
    if not isinstance(inherited, dict):
        raise ValueError("Corrected case lacks an inherited case identity")
    base_path = Path(inherited.get("path", ""))
    if not base_path.is_absolute():
        base_path = repo / base_path
    if not base_path.is_file() or file_digest(base_path) != inherited.get("sha256"):
        raise ValueError("Corrected case does not bind its inherited case bytes")
    base, ancestors = _load_case(repo, base_path, seen | {resolved_case_path})
    if base.get("id") != description.get("id"):
        raise ValueError("Corrected case inherits an unsupported base case")
    additions = description.get("added_constructed_controls")
    if additions is not None and not isinstance(additions, list):
        raise ValueError("Corrected case controls are malformed")
    if description.get("schema") == CASE_CORRECTION_SCHEMA and not additions:
        raise ValueError("Corrected case has no added controls")
    effective = json.loads(json.dumps(base))
    effective["schema"] = description["schema"]
    effective["correction"] = description.get("correction")
    effective["constructed_controls"].extend(additions or [])
    locator_additions = description.get("source_locator_additions", {})
    if not isinstance(locator_additions, dict):
        raise ValueError("Corrected case source locators are malformed")
    sources_by_id = {source["id"]: source for source in effective["sources"]}
    for source_id, locators in locator_additions.items():
        if source_id not in sources_by_id or not isinstance(locators, list) or not locators:
            raise ValueError(f"Corrected case locator target is invalid: {source_id}")
        for locator in locators:
            if not isinstance(locator, str) or not locator:
                raise ValueError(f"Corrected case locator is invalid: {source_id}")
            if locator not in sources_by_id[source_id]["locators"]:
                sources_by_id[source_id]["locators"].append(locator)
    effective["stopping_rule"] = description.get("stopping_rule")
    return effective, [base_path, *ancestors]


def _git(repo: Path, *args: str) -> str:
    return subprocess.check_output(["git", "-C", str(repo), *args], text=True).strip()


def _source_snapshot(repo: Path) -> dict[str, Any]:
    if _git(repo, "status", "--porcelain"):
        raise ValueError("Commit and preserve source changes before scored execution")
    names = (
        "src/nisayon/engine/population_binding.py",
        "scripts/experiments/run_population_binding.py",
        "src/nisayon/engine/io.py",
        "src/nisayon/engine/store.py",
        "pyproject.toml",
        "uv.lock",
    )
    return {
        "commit": _git(repo, "rev-parse", "HEAD"),
        "files": {name: file_digest(repo / name) for name in names},
        "interpreter": {
            "implementation": platform.python_implementation(),
            "version": platform.python_version(),
        },
        "dependency_lock_sha256": file_digest(repo / "uv.lock"),
    }


def _resolve_source(repo: Path, source: dict[str, Any]) -> Path:
    locators = source.get("locators")
    if not isinstance(locators, list) or not locators:
        raise ValueError(f"Source {source.get('id')} has no locators")
    for locator in locators:
        if not isinstance(locator, str) or not locator:
            continue
        candidate = Path(locator)
        if not candidate.is_absolute():
            candidate = repo / candidate
        if (
            candidate.is_file()
            and candidate.stat().st_size == source.get("bytes")
            and file_digest(candidate) == source.get("sha256")
        ):
            return candidate.resolve()
    raise ValueError(f"No exact source locator is available: {source.get('id')}")


def _copy_once(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    with source.open("rb") as incoming, target.open("xb") as outgoing:
        shutil.copyfileobj(incoming, outgoing)
        outgoing.flush()
        os.fsync(outgoing.fileno())


def _retain_sources(repo: Path, case: dict[str, Any], output: Path) -> dict[str, Path]:
    paths = {}
    index = []
    for source in case["sources"]:
        source_path = _resolve_source(repo, source)
        member = f"inputs/sources/{source['id']}/{source_path.name}"
        target = output / member
        _copy_once(source_path, target)
        paths[source["id"]] = target
        index.append(
            {
                "id": source["id"],
                "role": source["role"],
                "revision": source["revision"],
                "bytes": source["bytes"],
                "sha256": source["sha256"],
                "member": member,
                "selected_locator": str(source_path),
                "rights_scope": source["rights_scope"],
            }
        )
    write_json(
        output / "inputs/source-index.json",
        {
            "schema": "nisayon.population-binding-source-index.v1",
            "sources": index,
            "rights": "Private retained experiment evidence; inclusion does not grant redistribution rights.",
        },
    )
    return paths


def _published_statistics(document: dict[str, Any]) -> dict[str, Any]:
    features = ("observation.state", "action")
    if not all(isinstance(document.get(feature), dict) for feature in features):
        raise ValueError("Published source lacks state/action statistics")
    return {feature: document[feature] for feature in features}


def _original_input(case: dict[str, Any], sources: dict[str, Path]) -> dict[str, Any]:
    original = case["original_input"]
    published_source = sources[original["published_statistics_source"]]
    parent_source = sources[original["parent_enumeration_source"]]
    identity_source = sources[original["population_identity_source"]]
    path_source = sources[original["upstream_path_observation_source"]]
    published = _published_statistics(_read_json(published_source))
    parent = _read_jsonl(parent_source)
    identity = _read_json(identity_source)
    path_observation = _read_json(path_source)

    identity_inputs = identity.get("inputs", {})
    if identity_inputs.get("published_stats", {}).get("sha256") != file_digest(
        published_source
    ) or identity_inputs.get("episodes_stats", {}).get("sha256") != file_digest(parent_source):
        raise ValueError("Population identity record is not bound to retained sources")
    observation = path_observation.get("observations", {})
    if not (
        observation.get("cache_valid") is True
        and observation.get("calculate_dataset_statistics_calls") == 0
        and observation.get("statistics_writer_calls") == 0
        and observation.get("statistics_sha256_before") == file_digest(published_source)
        and observation.get("statistics_sha256_after") == file_digest(published_source)
    ):
        raise ValueError("Upstream path observation does not establish unchanged cache reuse")

    interpretation = original["normalization_interpretation"].copy()
    evidence_source = interpretation.pop("evidence_source")
    interpretation_path = sources[evidence_source]
    interpretation["evidence"] = {
        "source_text": interpretation_path.read_text(),
        "source_sha256": file_digest(interpretation_path),
        "required_markers": ["normalization_formula", "unresolved"],
    }
    invocation_text = path_source.read_text()
    return {
        "id": original["id"],
        "label": original["label"],
        "role_obligation": "parent_population_summary",
        "published_statistics": published,
        "parent_episode_statistics": parent,
        "subset_observations": identity["per_episode_versus_episodes_stats"],
        "subset_members": len(identity["membership"]),
        "selection": {
            "kind": "observed_invocation",
            "observed": True,
            "selected_statistics_sha256": digest(published),
            "scope": "scoped_cache_generation_invocation",
            "evidence": {
                "source_text": invocation_text,
                "source_sha256": file_digest(path_source),
                "required_markers": [
                    "processor_set_statistics_calls",
                    "statistics_sha256_before",
                    "cache_valid",
                ],
            },
        },
        "normalization_interpretation": interpretation,
    }


def _materialize_control(control: dict[str, Any]) -> dict[str, Any]:
    value = json.loads(json.dumps(control))
    mutation = value.pop("fixture_mutation", None)
    if mutation == "non_finite_current_row":
        value["current_rows"] = {"state": [[1.0], [float("nan")]]}
    elif mutation == "non_finite_statistics":
        value["published_statistics"]["state"]["std"][0] = float("nan")
    published = value.get("published_statistics")
    if value.pop("bind_selection_to_published", False):
        source_text = value.pop(
            "selection_source_text",
            "constructed control observed invocation selected the retained statistics\n",
        )
        value["selection"] = {
            "kind": "observed_invocation",
            "observed": True,
            "selected_statistics_sha256": digest(published),
            "scope": "constructed_control",
            "evidence": {
                "source_text": source_text,
                "source_sha256": hashlib.sha256(source_text.encode()).hexdigest(),
                "required_markers": ["observed invocation", "selected"],
            },
        }
    external = value.get("external_reference")
    if isinstance(external, dict) and external.get("reference_sha256") == "bind_published":
        external["reference_sha256"] = digest(published)
    selection = value.get("selection")
    if (
        isinstance(selection, dict)
        and selection.get("selected_statistics_sha256") == "bind_published"
    ):
        selection["selected_statistics_sha256"] = digest(published)
    return value


def _validate_case(case: dict[str, Any]) -> None:
    if (
        case.get("schema")
        not in {CASE_SCHEMA, CASE_CORRECTION_SCHEMA, CASE_LOCATOR_CORRECTION_SCHEMA}
        or case.get("id") != "population-binding-001"
    ):
        raise ValueError("Unsupported population-binding case")
    sources = case.get("sources")
    if not isinstance(sources, list) or len(sources) != len(
        {source.get("id") for source in sources if isinstance(source, dict)}
    ):
        raise ValueError("Source identities are missing or duplicated")
    controls = case.get("constructed_controls")
    if not isinstance(controls, list) or len(controls) != len(
        {control.get("id") for control in controls if isinstance(control, dict)}
    ):
        raise ValueError("Control identities are missing or duplicated")
    if case.get("budget", {}).get("process_cpu_seconds") != 30:
        raise ValueError("Unexpected process CPU allocation")


def run_case(case_path: Path, output: Path) -> dict[str, Any]:
    started_at = datetime.now(UTC).isoformat()
    start_wall = time.perf_counter()
    start_cpu = time.process_time()
    repo = Path(__file__).resolve().parents[2]
    case, inherited_case_paths = _load_case(repo, case_path)
    _validate_case(case)
    source_identity = _source_snapshot(repo)
    output.mkdir(parents=True, exist_ok=False)
    _copy_once(case_path, output / "inputs/frozen-case.json")
    for index, inherited_case_path in enumerate(inherited_case_paths, 1):
        _copy_once(inherited_case_path, output / f"inputs/inherited-case-{index:03d}.json")
    sources = _retain_sources(repo, case, output)
    invocation = {
        "schema": "nisayon.population-binding-invocation.v1",
        "id": case["id"],
        "started_at": started_at,
        "case_sha256": file_digest(case_path),
        "effective_case_sha256": digest(case),
        "inherited_case_sha256": (
            file_digest(inherited_case_paths[0]) if inherited_case_paths else None
        ),
        "inherited_case_chain_sha256": [file_digest(path) for path in inherited_case_paths],
        "command_record_id": os.environ.get("NISAYON_COMMAND_RECORD_ID"),
        "source_identity": source_identity,
    }
    write_json(output / "invocation.json", invocation)

    original = decide_population_binding(_original_input(case, sources))
    write_json(output / "decisions/original.json", original)
    controls = []
    for control in case["constructed_controls"]:
        decision = decide_population_binding(_materialize_control(control))
        write_json(output / f"decisions/controls/{control['id']}.json", decision)
        controls.append(
            {
                "id": control["id"],
                "path": f"decisions/controls/{control['id']}.json",
                "sha256": file_digest(output / f"decisions/controls/{control['id']}.json"),
                "operation": decision["decision"]["selected_operation"],
                "status": decision["decision"]["status"],
            }
        )

    process_cpu = time.process_time() - start_cpu
    if process_cpu > case["budget"]["process_cpu_seconds"]:
        raise ValueError("Population-binding process CPU allocation exceeded")
    summary = {
        "schema": SUMMARY_SCHEMA,
        "case_id": case["id"],
        "interface": case["interface"],
        "evaluation_contract": case["evaluation_contract"],
        "invocation": invocation,
        "original": {
            "path": "decisions/original.json",
            "sha256": file_digest(output / "decisions/original.json"),
            "role": original["role"],
            "operation": original["decision"]["selected_operation"],
            "status": original["decision"]["status"],
        },
        "controls": controls,
        "failures": case["retained_failures"],
        "costs": {
            "outer_wall_seconds_before_summary": time.perf_counter() - start_wall,
            "outer_process_cpu_seconds_before_summary": process_cpu,
            "command_record_id": os.environ.get("NISAYON_COMMAND_RECORD_ID"),
            "dependency_download_bytes": 0,
            "new_source_download_bytes": 0,
            "source_copy_bytes": sum(source["bytes"] for source in case["sources"]),
            "engineering_effort": None,
            "provider_charges": None,
            "energy": None,
            "network_overhead": None,
            "unsampled_peak_memory": None,
        },
        "limits": {
            "full_upstream_import_executed": False,
            "model_or_policy_executed": False,
            "simulator_or_robot_executed": False,
            "reserved_incidents_accessed": 0,
            "constructed_controls": len(controls),
        },
        "producer_authority": "proposal for independent evaluation; not acceptance",
    }
    write_json(output / "summary.json", summary)
    retained_before_seal = sum(path.stat().st_size for path in output.rglob("*") if path.is_file())
    if retained_before_seal > case["budget"]["artifact_bytes"]:
        raise ValueError("Population-binding artifact allocation exceeded")
    members = [path.relative_to(output).as_posix() for path in output.rglob("*") if path.is_file()]
    manifest = create_manifest(output, members)
    write_json(
        output / "seal.json",
        {
            "schema": SEAL_SCHEMA,
            "case_sha256": file_digest(output / "inputs/frozen-case.json"),
            "summary_sha256": file_digest(output / "summary.json"),
            "artifact_manifest": manifest,
        },
    )
    if (
        sum(path.stat().st_size for path in output.rglob("*") if path.is_file())
        > case["budget"]["artifact_bytes"]
    ):
        raise ValueError("Population-binding artifact allocation exceeded after sealing")
    return inspect_store(output)


def inspect_store(output: Path) -> dict[str, Any]:
    seal = _read_json(output / "seal.json")
    if seal.get("schema") != SEAL_SCHEMA:
        raise ValueError("Unsupported population-binding seal")
    members = verify_manifest(output, seal["artifact_manifest"])
    if file_digest(output / "summary.json") != seal["summary_sha256"]:
        raise ValueError("Population-binding summary digest differs")
    if file_digest(output / "inputs/frozen-case.json") != seal["case_sha256"]:
        raise ValueError("Population-binding case digest differs")
    summary = _read_json(output / "summary.json")
    for row in [summary["original"], *summary["controls"]]:
        if row["path"] not in members or members[row["path"]]["sha256"] != row["sha256"]:
            raise ValueError(f"Decision is absent from the sealed manifest: {row['path']}")
    return {
        "schema": "nisayon.population-binding-readback.v1",
        "store": str(output.resolve()),
        "seal_sha256": file_digest(output / "seal.json"),
        "manifest_files": len(members),
        "summary": summary,
        "retained_bytes": sum(path.stat().st_size for path in output.rglob("*") if path.is_file()),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--inspect", action="store_true")
    args = parser.parse_args()
    if args.inspect:
        if args.case is not None:
            parser.error("--case is not accepted with --inspect")
        result = inspect_store(args.output)
    else:
        if args.case is None:
            parser.error("--case is required unless --inspect is used")
        result = run_case(args.case, args.output)
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()

import hashlib
import importlib.util
import json
import math
from pathlib import Path

import pytest

from nisayon.engine.io import file_digest
from nisayon.engine.population_binding import calculate_statistics

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/experiments/run_population_binding.py"


def _module():
    spec = importlib.util.spec_from_file_location("run_population_binding", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _stats(rows):
    return {
        key: value for key, value in calculate_statistics(rows).items() if key not in {"n", "width"}
    }


def _write(path, value):
    path.write_text(json.dumps(value) + "\n")
    return path


def _fixture(tmp_path):
    state_episodes = [
        {"count": [2], "mean": [1.0], "std": [1.0], "min": [0.0], "max": [2.0]},
        {"count": [2], "mean": [5.0], "std": [1.0], "min": [4.0], "max": [6.0]},
    ]
    action_episodes = [
        {"count": [2], "mean": [2.0], "std": [1.0], "min": [1.0], "max": [3.0]},
        {"count": [2], "mean": [6.0], "std": [1.0], "min": [5.0], "max": [7.0]},
    ]
    episodes = [
        {
            "episode_index": index,
            "stats": {
                "observation.state": state_episodes[index],
                "action": action_episodes[index],
            },
        }
        for index in range(2)
    ]
    published = {
        "observation.state": {
            "mean": [3.0],
            "std": [math_sqrt_five()],
            "min": [0.0],
            "max": [6.0],
            "q01": [0.0],
            "q99": [6.0],
        },
        "action": {
            "mean": [4.0],
            "std": [math_sqrt_five()],
            "min": [1.0],
            "max": [7.0],
            "q01": [1.0],
            "q99": [7.0],
        },
    }
    published_path = _write(tmp_path / "stats.json", published)
    episodes_path = tmp_path / "episodes_stats.jsonl"
    episodes_path.write_text("".join(json.dumps(row) + "\n" for row in episodes))
    identity = {
        "inputs": {
            "published_stats": {"sha256": file_digest(published_path)},
            "episodes_stats": {"sha256": file_digest(episodes_path)},
        },
        "membership": [{"episode_index": 0}],
        "per_episode_versus_episodes_stats": [
            {
                "episode_index": 0,
                "max_abs_difference": {
                    feature: {
                        "min": 0.0,
                        "max": 0.0,
                        "mean": 0.0,
                        "std": 0.0,
                        "count": 2,
                    }
                    for feature in ("observation.state", "action")
                },
            }
        ],
    }
    identity_path = _write(tmp_path / "identity.json", identity)
    path_observation = {
        "observations": {
            "cache_valid": True,
            "calculate_dataset_statistics_calls": 0,
            "statistics_writer_calls": 0,
            "statistics_sha256_before": file_digest(published_path),
            "statistics_sha256_after": file_digest(published_path),
            "processor_set_statistics_calls": [{"override_argument": False}],
        }
    }
    observation_path = _write(tmp_path / "path.json", path_observation)
    normalizer_path = tmp_path / "normalizer.py"
    normalizer_path.write_text("denominator = std + eps\n")
    paths = {
        "published": published_path,
        "parent": episodes_path,
        "identity": identity_path,
        "path": observation_path,
        "normalizer": normalizer_path,
    }
    sources = [
        {
            "id": name,
            "role": name,
            "revision": "fixture",
            "bytes": path.stat().st_size,
            "sha256": file_digest(path),
            "locators": [str(path)],
            "rights_scope": "constructed_test_fixture",
        }
        for name, path in paths.items()
    ]
    control_rows = [[1.0], [3.0]]
    control_published = {"state": _stats(control_rows)}
    case = {
        "schema": "nisayon.population-binding-case.v1",
        "id": "population-binding-001",
        "interface": {"schema": "nisayon.population-binding-record-interface.v2"},
        "evaluation_contract": {"sha256": "a" * 64},
        "sources": sources,
        "original_input": {
            "id": "original",
            "label": "demo",
            "published_statistics_source": "published",
            "parent_enumeration_source": "parent",
            "population_identity_source": "identity",
            "upstream_path_observation_source": "path",
            "normalization_interpretation": {
                "status": "supported",
                "evidence_source": "normalizer",
            },
        },
        "constructed_controls": [
            {
                "id": "PBC01",
                "label": "fixture",
                "role_obligation": "current_population_summary",
                "role_evidence": {"current_obligation": True},
                "current_rows": {"state": control_rows},
                "published_statistics": control_published,
                "bind_selection_to_published": True,
                "normalization_interpretation": {"status": "unresolved"},
            }
        ],
        "retained_failures": [],
        "budget": {"process_cpu_seconds": 30, "artifact_bytes": 2 * 1024**2},
    }
    case_path = _write(tmp_path / "case.json", case)
    return case_path


def math_sqrt_five():
    return 5.0**0.5


def test_store_seals_content_derived_original_and_control(tmp_path, monkeypatch):
    module = _module()
    monkeypatch.setattr(module, "_source_snapshot", lambda _repo: {"commit": "fixture"})
    case = _fixture(tmp_path)
    output = tmp_path / "store"

    readback = module.run_case(case, output)

    assert readback["summary"]["original"] == {
        "path": "decisions/original.json",
        "sha256": file_digest(output / "decisions/original.json"),
        "role": "parent_population_summary",
        "operation": "reuse",
        "status": "supported",
    }
    assert readback["summary"]["controls"][0]["operation"] == "reuse"
    assert readback["summary"]["costs"]["new_source_download_bytes"] == 0


def test_store_detects_decision_tampering(tmp_path, monkeypatch):
    module = _module()
    monkeypatch.setattr(module, "_source_snapshot", lambda _repo: {"commit": "fixture"})
    output = tmp_path / "store"
    module.run_case(_fixture(tmp_path), output)
    original = output / "decisions/original.json"
    original.write_text(original.read_text() + " ")

    with pytest.raises(ValueError, match="Artifact bytes mismatch"):
        module.inspect_store(output)


def test_store_binds_source_digests_before_output(tmp_path, monkeypatch):
    module = _module()
    monkeypatch.setattr(module, "_source_snapshot", lambda _repo: {"commit": "fixture"})
    case_path = _fixture(tmp_path)
    case = json.loads(case_path.read_text())
    case["sources"][0]["sha256"] = hashlib.sha256(b"different").hexdigest()
    case_path.write_text(json.dumps(case))

    with pytest.raises(ValueError, match="No exact source locator"):
        module.run_case(case_path, tmp_path / "store")


def test_corrected_case_binds_and_retains_its_base(tmp_path, monkeypatch):
    module = _module()
    monkeypatch.setattr(module, "_source_snapshot", lambda _repo: {"commit": "fixture"})
    base_path = _fixture(tmp_path)
    correction = {
        "schema": "nisayon.population-binding-case.v2",
        "id": "population-binding-001",
        "inherits": {"path": str(base_path), "sha256": file_digest(base_path)},
        "correction": {"finding": "constructed"},
        "added_constructed_controls": [_current_control() | {"id": "PBC07"}],
        "stopping_rule": "one correction run",
    }
    correction_path = _write(tmp_path / "case-v2.json", correction)

    readback = module.run_case(correction_path, tmp_path / "store-v2")

    assert len(readback["summary"]["controls"]) == 2
    assert readback["summary"]["invocation"]["inherited_case_sha256"] == file_digest(base_path)
    assert (tmp_path / "store-v2/inputs/inherited-case-001.json").is_file()


def test_locator_correction_can_inherit_the_control_correction(tmp_path):
    module = _module()
    base_path = _fixture(tmp_path)
    correction = {
        "schema": "nisayon.population-binding-case.v2",
        "id": "population-binding-001",
        "inherits": {"path": str(base_path), "sha256": file_digest(base_path)},
        "correction": {"finding": "constructed"},
        "added_constructed_controls": [_current_control() | {"id": "PBC07"}],
        "stopping_rule": "one correction run",
    }
    correction_path = _write(tmp_path / "case-v2.json", correction)
    locator = tmp_path / "retained-normalizer.json"
    locator.write_text("retained\n")
    locator_correction = {
        "schema": "nisayon.population-binding-case.v3",
        "id": "population-binding-001",
        "inherits": {
            "path": str(correction_path),
            "sha256": file_digest(correction_path),
        },
        "correction": {"failure": "source locator"},
        "source_locator_additions": {"normalizer": [str(locator)]},
        "stopping_rule": "one retry",
    }
    locator_path = _write(tmp_path / "case-v3.json", locator_correction)

    effective, ancestors = module._load_case(tmp_path, locator_path)

    assert [path.name for path in ancestors] == ["case-v2.json", "case.json"]
    assert effective["schema"] == "nisayon.population-binding-case.v3"
    assert len(effective["constructed_controls"]) == 2
    source = next(row for row in effective["sources"] if row["id"] == "normalizer")
    assert source["locators"][-1] == str(locator)


@pytest.mark.parametrize(
    ("mutation", "path"),
    [
        ("non_finite_current_row", ("current_rows", "state", 1, 0)),
        ("non_finite_statistics", ("published_statistics", "state", "std", 0)),
    ],
)
def test_control_adapter_materializes_non_finite_without_nonstandard_json(mutation, path):
    module = _module()
    case = _current_control()
    case["fixture_mutation"] = mutation

    result = module._materialize_control(case)

    value = result
    for part in path:
        value = value[part]
    assert math.isnan(value)
    assert "fixture_mutation" not in result


def _current_control():
    rows = [[1.0], [3.0]]
    return {
        "id": "control",
        "role_obligation": "current_population_summary",
        "role_evidence": {"current_obligation": True},
        "current_rows": {"state": rows},
        "published_statistics": {"state": _stats(rows)},
        "normalization_interpretation": {"status": "unresolved"},
    }

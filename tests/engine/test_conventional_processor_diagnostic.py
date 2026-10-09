import ast
import copy
import importlib.util
import json
import struct
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/experiments/conventional_processor_diagnostic.py"
PLAN = ROOT / "docs/experiments/results/baseline-qualification-001/qualification-plan.v1.json"


def _module():
    spec = importlib.util.spec_from_file_location("conventional_processor_diagnostic", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _safetensors(path, tensors):
    offset = 0
    header = {}
    payload = bytearray()
    for name, values in tensors.items():
        packed = struct.pack(f"<{len(values)}f", *values)
        header[name] = {
            "dtype": "F32",
            "shape": [len(values)],
            "data_offsets": [offset, offset + len(packed)],
        }
        payload.extend(packed)
        offset += len(packed)
    encoded = json.dumps(header, separators=(",", ":")).encode()
    path.write_bytes(struct.pack("<Q", len(encoded)) + encoded + payload)


@pytest.fixture
def plan_context(tmp_path):
    diagnostic = _module()
    plan = diagnostic._read_json(PLAN)
    source_root = tmp_path / "sources"
    source_root.mkdir()
    explicit_action = plan["incident_candidates"][2]["statistics"]["action"]
    tensors = {
        "so100-blue.buffer.action.mean": [2.0] * 6,
        "so100-blue.buffer.action.std": [3.0] * 6,
        "so100-red.buffer.action.mean": [4.0] * 6,
        "so100-red.buffer.action.std": [5.0] * 6,
        "so100.buffer.action.mean": explicit_action["mean"],
        "so100.buffer.action.std": explicit_action["std"],
    }
    pre_stats = source_root / "pre.safetensors"
    post_stats = source_root / "post.safetensors"
    _safetensors(pre_stats, tensors)
    _safetensors(post_stats, tensors)
    features = {
        "observation.state": {"type": "STATE", "shape": [6]},
        "observation.image": {"type": "VISUAL", "shape": [6]},
        "action": {"type": "ACTION", "shape": [6]},
    }
    norm_map = {"VISUAL": "IDENTITY", "STATE": "MEAN_STD", "ACTION": "MEAN_STD"}
    pre_config = source_root / "pre.json"
    pre_config.write_text(
        json.dumps(
            {
                "steps": [
                    {
                        "registry_name": "normalizer_processor",
                        "config": {"eps": 1e-8, "features": features, "norm_map": norm_map},
                        "state_file": pre_stats.name,
                    }
                ]
            }
        )
    )
    post_config = source_root / "post.json"
    post_config.write_text(
        json.dumps(
            {
                "steps": [
                    {
                        "registry_name": "unnormalizer_processor",
                        "config": {
                            "eps": 1e-8,
                            "features": {"action": features["action"]},
                            "norm_map": norm_map,
                        },
                        "state_file": post_stats.name,
                    }
                ]
            }
        )
    )
    source = source_root / "normalize.py"
    source.write_text(
        """class _NormalizationMixin:
    def load_state_dict(self, state):
        flat_key = next(iter(state))
        flat_key.rsplit(\".\", 1)

    def _normalize_observation(self, observation):
        return observation

    def _normalize_action(self, action):
        return action

    def _apply_transform(self, tensor, key):
        if key not in self._tensor_stats:
            return tensor
        tensor * std + mean
        return (tensor - mean) / denom
"""
    )
    files = {
        "preprocessor_config": pre_config,
        "postprocessor_config": post_config,
        "preprocessor_stats": pre_stats,
        "postprocessor_stats": post_stats,
        "processor_source": source,
    }
    plan["sources"] = {
        role: {
            "path": path.name,
            "bytes": path.stat().st_size,
            "sha256": diagnostic._file_digest(path),
        }
        for role, path in files.items()
    }
    return diagnostic, plan, diagnostic._load_context(plan, source_root)


def test_standalone_diagnostic_imports_no_nisayon_module():
    tree = ast.parse(SCRIPT.read_text())
    imported = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.append(node.module or "")
    assert not [name for name in imported if name == "nisayon" or name.startswith("nisayon.")]


def test_frozen_controls_follow_candidate_contents_not_identifiers(plan_context):
    diagnostic, plan, context = plan_context

    controls, qualification = diagnostic._run_controls(plan, context)

    assert qualification["passed"] is True
    assert all(control["matches_expectation"] for control in controls)
    by_id = {
        candidate["id"]: candidate for control in controls for candidate in control["candidates"]
    }
    assert by_id["opaque-zeta"]["outcome"] == "supported_software_correction"
    assert by_id["opaque-alpha"]["outcome"] == "rejected_candidate"
    assert by_id["opaque-mu"]["outcome"] == "rejected_candidate"
    assert by_id["C2_explicit_override"]["outcome"] == "rejected_candidate"
    assert by_id["C0_as_is"]["outcome"] == "supported_software_correction"


def test_incident_decision_is_computed_and_binding_stays_unresolved(plan_context):
    diagnostic, plan, context = plan_context

    candidates = diagnostic._run_candidates(plan["incident_candidates"], context, plan["witnesses"])

    assert [candidate["outcome"] for candidate in candidates] == [
        "rejected_candidate",
        "rejected_candidate",
        "supported_software_correction",
    ]
    explicit = candidates[2]
    assert explicit["deployment_applicability"] == "unresolved"
    assert all(
        observation["meets_obligation"]
        for observation in explicit["observations"]
        if observation["feature"] in {"observation.state", "action"}
    )
    suffix_actions = [
        observation
        for observation in candidates[1]["observations"]
        if observation["feature"] == "action"
    ]
    assert len(suffix_actions) == 2
    assert suffix_actions[0]["output"] != suffix_actions[1]["output"]
    assert all(observation["class"] == "ambiguous" for observation in suffix_actions)
    explicit_identity = next(
        observation
        for observation in explicit["observations"]
        if observation["class"] == "identity_mode"
    )
    assert explicit_identity["statistics_provenance"] == "artifact"


def test_declared_provenance_and_selector_labels_cannot_promote_binding(plan_context):
    diagnostic, plan, context = plan_context
    candidate = copy.deepcopy(plan["incident_candidates"][2])
    candidate["selector_evidence"] = {
        "status": "verified_deployment_record",
        "detail": "Constructed label-only control; no deployment record was added.",
    }
    candidate["statistics_provenance"] = {
        "action": "verified_training_statistics",
        "observation.state": "verified_training_statistics",
    }

    result = diagnostic._run_candidate(candidate, context, plan["witnesses"])

    assert result["outcome"] == "supported_software_correction"
    assert result["deployment_applicability"] == "unresolved"
    assert "declarations only" in result["deployment_reason"]


def test_sealed_readback_detects_changed_member(tmp_path):
    diagnostic = _module()
    result = {
        "schema": diagnostic.RESULT_SCHEMA,
        "qualification": {
            "passed": True,
            "scientific_status": "baseline_qualified_for_future_comparison",
        },
        "incident": {
            "overall": "supported_software_correction",
            "deployment_applicability": "unresolved",
        },
    }
    observation = {"schema": diagnostic.OBSERVATION_SCHEMA}
    result_path = tmp_path / "result.json"
    observation_path = tmp_path / "observation.json"
    diagnostic._write_once(result_path, result)
    diagnostic._write_once(observation_path, observation)
    members = {
        path.name: {"bytes": path.stat().st_size, "sha256": diagnostic._file_digest(path)}
        for path in (result_path, observation_path)
    }
    diagnostic._write_once(
        tmp_path / "seal.json",
        {
            "schema": diagnostic.SEAL_SCHEMA,
            "members": members,
            "plan_sha256": "0" * 64,
            "implementation_commit": "test",
        },
    )

    assert diagnostic.inspect(tmp_path)["integrity"] == "verified_complete_store"
    observation_path.write_text(json.dumps(observation, indent=4))
    with pytest.raises(ValueError, match="Sealed member differs"):
        diagnostic.inspect(tmp_path)

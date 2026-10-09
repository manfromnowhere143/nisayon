import json
import shutil
import struct
from dataclasses import dataclass, field
from pathlib import Path

import pytest

from nisayon.cli import parser
from nisayon.engine import processor_case
from nisayon.engine.io import file_digest, write_json


@dataclass
class _TestNormalizationMixin:
    features: dict
    norm_map: dict
    stats: dict | None = None
    device: str | None = None
    dtype: object | None = None
    eps: float = 1e-8
    normalize_observation_keys: set[str] | None = None
    _tensor_stats: dict = field(default_factory=dict, init=False)

    def __post_init__(self):
        import torch

        self._explicit = bool(self.stats)
        self._tensor_stats = {
            key: {name: torch.tensor(value, dtype=torch.float32) for name, value in values.items()}
            for key, values in (self.stats or {}).items()
        }

    def load_state_dict(self, state):
        if self._explicit:
            return
        self._tensor_stats = {}
        for flat_key, tensor in state.items():
            key, name = flat_key.rsplit(".", 1)
            self._tensor_stats.setdefault(key, {})[name] = tensor

    def _apply_transform(self, tensor, key, feature_type, *, inverse=False):
        mode = self.norm_map.get(str(feature_type), self.norm_map.get(feature_type, "IDENTITY"))
        if mode == "IDENTITY" or key not in self._tensor_stats:
            return tensor
        stats = self._tensor_stats[key]
        if mode != "MEAN_STD":
            raise ValueError(f"Unsupported mode: {mode}")
        if "mean" not in stats or "std" not in stats:
            raise ValueError("MEAN_STD requires mean and std")
        if inverse:
            return tensor * stats["std"] + stats["mean"]
        return (tensor - stats["mean"]) / (stats["std"] + self.eps)

    def _normalize_action(self, action, inverse):
        return self._apply_transform(action, "action", "ACTION", inverse=inverse)

    def _normalize_observation(self, observation, inverse):
        result = dict(observation)
        for key, value in observation.items():
            result[key] = self._apply_transform(
                value, key, self.features[key]["type"], inverse=inverse
            )
        return result


def _safetensors(path: Path, tensors: dict[str, list[float]]) -> None:
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


def _build_case(tmp_path: Path) -> tuple[Path, Path, dict]:
    source_root = tmp_path / "sources"
    source_root.mkdir()
    tensors = {}
    for index, prefix in enumerate(
        ["dataset-blue.buffer.action", "dataset-red.buffer.action", "dataset.buffer.action"]
    ):
        tensors[f"{prefix}.mean"] = [float(index + 1)] * 6
        tensors[f"{prefix}.std"] = [float(index + 2)] * 6
    pre_state = source_root / "pre.safetensors"
    post_state = source_root / "post.safetensors"
    _safetensors(pre_state, tensors)
    shutil.copyfile(pre_state, post_state)

    normalizer = {
        "registry_name": "normalizer_processor",
        "config": {
            "eps": 1e-8,
            "features": {
                "observation.state": {"type": "STATE", "shape": [6]},
                "observation.image": {"type": "VISUAL", "shape": [6]},
                "action": {"type": "ACTION", "shape": [6]},
            },
            "norm_map": {"VISUAL": "IDENTITY", "STATE": "MEAN_STD", "ACTION": "MEAN_STD"},
        },
        "state_file": pre_state.name,
    }
    steps = [{"registry_name": f"step-{index}", "config": {}} for index in range(5)]
    steps.append(normalizer)
    pre_config = source_root / "pre.json"
    write_json(pre_config, {"name": "policy_preprocessor", "steps": steps})
    post_config = source_root / "post.json"
    write_json(
        post_config,
        {
            "name": "policy_postprocessor",
            "steps": [
                {
                    **normalizer,
                    "registry_name": "unnormalizer_processor",
                    "state_file": post_state.name,
                    "config": {
                        **normalizer["config"],
                        "features": {"action": {"type": "ACTION", "shape": [6]}},
                    },
                }
            ],
        },
    )
    model = source_root / "model.json"
    write_json(
        model,
        {
            "normalization_mapping": {
                "VISUAL": "IDENTITY",
                "STATE": "MEAN_STD",
                "ACTION": "MEAN_STD",
            }
        },
    )
    other = {
        "external-report": ("external_report", "report.json", "private test fixture"),
        "normalize-source": ("normalizer_implementation", "normalize.py", "test fixture"),
        "factory-source": ("factory_call_path", "factory.py", "test fixture"),
        "pipeline-source": ("pipeline_loader_call_path", "pipeline.py", "test fixture"),
        "policy-factory-source": (
            "policy_specific_factory_boundary",
            "policy_factory.py",
            "test fixture",
        ),
    }
    fixture_source = {
        "factory.py": (
            "_make_pretrained_processors_from_policy_config(\n"
            "PolicyProcessorPipeline.from_pretrained(\n"
        ),
        "pipeline.py": (
            "load_file(state_path)\nstep_instance.load_state_dict(load_file(state_path))\n"
        ),
    }
    for _, filename, _ in other.values():
        (source_root / filename).write_text(fixture_source.get(filename, "{}\n"))
    declarations = {
        "model-config": ("model_config", model),
        "preprocessor-config": ("preprocessor_config", pre_config),
        "postprocessor-config": ("postprocessor_config", post_config),
        "preprocessor-state": ("preprocessor_state", pre_state),
        "postprocessor-state": ("postprocessor_state", post_state),
    }
    sources = []
    for source_id, (role, path) in declarations.items():
        sources.append(
            {
                "id": source_id,
                "role": role,
                "path": path.name,
                "sha256": file_digest(path),
                "bytes": path.stat().st_size,
                "revision": "test",
                "rights_scope": "labelled local test fixture",
            }
        )
    for source_id, (role, filename, rights) in other.items():
        path = source_root / filename
        sources.append(
            {
                "id": source_id,
                "role": role,
                "path": filename,
                "sha256": file_digest(path),
                "bytes": path.stat().st_size,
                "revision": "test",
                "rights_scope": rights,
            }
        )
    by_role = {row["role"]: row for row in sources}
    sources = [by_role[role] for role in processor_case.REQUIRED_SOURCE_ROLES]
    explicit = {
        "action": {"mean": [3.0] * 6, "std": [4.0] * 6},
        "observation.state": {"mean": [10.0] * 6, "std": [2.0] * 6},
    }
    case = {
        "schema": processor_case.CASE_SCHEMA,
        "id": "processor-test",
        "evaluation": {
            "commit": "a" * 40,
            "files": [{"path": "evaluation/plan.json", "sha256": "b" * 64}],
        },
        "sources": sources,
        "processors": {
            "preprocessor": {
                "config_source": "preprocessor-config",
                "state_source": "preprocessor-state",
                "step_index": 5,
                "registry_name": "normalizer_processor",
            },
            "postprocessor": {
                "config_source": "postprocessor-config",
                "state_source": "postprocessor-state",
                "step_index": 0,
                "registry_name": "unnormalizer_processor",
            },
        },
        "witnesses": {
            "state": [0.0, 1.0, 2.0, 3.0, 4.0, 5.0],
            "action": [0.5] * 6,
            "visual": [0.0, 0.25, 0.5, 0.75, 1.0, -0.25],
        },
        "candidates": [
            {"id": "C0_as_is"},
            {"id": "C1_suffix_match"},
            {"id": "C2_explicit_override", "selector": "so100", "stats": explicit},
            {"id": "C3_remigration"},
        ],
        "suffix_orders": [
            ["dataset-blue.buffer.action", "dataset-red.buffer.action", "dataset.buffer.action"],
            ["dataset.buffer.action", "dataset-red.buffer.action", "dataset-blue.buffer.action"],
        ],
        "assignments": list(processor_case.ASSIGNMENT_IDS),
        "obligations": [{"id": name} for name in ("O1", "O2", "O3", "O4")],
        "budget": {"cpu_seconds": 60, "artifact_bytes": 4 * 1024 * 1024},
    }
    case_path = tmp_path / "case.json"
    write_json(case_path, case)
    return case_path, source_root, case


def test_malformed_safetensors_overlap_is_rejected(tmp_path):
    path = tmp_path / "bad.safetensors"
    header = {
        "one": {"dtype": "F32", "shape": [1], "data_offsets": [0, 4]},
        "two": {"dtype": "F32", "shape": [1], "data_offsets": [0, 4]},
    }
    encoded = json.dumps(header).encode()
    path.write_bytes(struct.pack("<Q", len(encoded)) + encoded + struct.pack("<f", 1.0))
    with pytest.raises(ValueError, match="Overlapping"):
        processor_case.read_safetensors(path)


def test_interrupted_prefix_requires_explicit_resume_and_retains_useful_paths(
    tmp_path, monkeypatch
):
    pytest.importorskip("torch", reason="requires the locked simulation extra")
    case_path, source_root, case = _build_case(tmp_path)
    processor_case.validate_case(case)
    monkeypatch.setattr(
        processor_case,
        "extract_mixin",
        lambda _path: (
            _TestNormalizationMixin,
            {
                "implementation_sha256": file_digest(_path),
                "callable": "_NormalizationMixin._apply_transform",
                "class_lines": [1, 1],
                "apply_transform_lines": [1, 1],
            },
        ),
    )
    store = tmp_path / "store"
    identity = {
        "commit": "test",
        "files": {},
        "interpreter": {},
        "dependency_lock_sha256": "0" * 64,
    }
    with pytest.raises(processor_case.PlannedInterruption):
        processor_case.run_case(
            case_path,
            source_root,
            store,
            interrupt_at="incident-C0-state",
            source_identity=identity,
        )
    prefix = processor_case.inspect_store(store)
    assert prefix["integrity"] == "verified_prefix"
    assert prefix["completed_assignments"] == 0
    assert prefix["dangling_attempts"] == [
        {
            "assignment_id": "incident-C0-state",
            "attempts": 1,
            "state": "intent_retained_completion_unknown",
        }
    ]

    completed = processor_case.run_case(
        case_path,
        source_root,
        store,
        resume=True,
        source_identity=identity,
    )
    assert completed["integrity"] == "verified_complete_store"
    assert completed["completed_assignments"] == len(processor_case.ASSIGNMENT_IDS)
    decisions = completed["summary"]["decisions"]
    assert decisions["software_decision"] == "supported_software_correction"
    assert [row["outcome"] for row in decisions["candidates"]] == [
        "rejected_candidate",
        "rejected_candidate",
        "supported_software_correction",
        "unresolved",
    ]
    assert decisions["observed_predicates"]["constructed_controls"]["identity_mode_visual"]
    assert decisions["observed_predicates"]["constructed_controls"][
        "suffix_partial_state_still_skips"
    ]
    assert len(list((store / "recoveries").glob("*.json"))) == 1

    saved = processor_case.inspect_store(store)
    assert saved["execution_performed"] is False
    assert saved["retry_performed"] is False
    assert saved["integrity"] == "verified_complete_store"


def test_prefix_readback_rejects_source_index_rebinding(tmp_path, monkeypatch):
    pytest.importorskip("torch", reason="requires the locked simulation extra")
    case_path, source_root, _case = _build_case(tmp_path)
    monkeypatch.setattr(
        processor_case,
        "extract_mixin",
        lambda _path: (
            _TestNormalizationMixin,
            {
                "implementation_sha256": file_digest(_path),
                "callable": "_NormalizationMixin._apply_transform",
                "class_lines": [1, 1],
                "apply_transform_lines": [1, 1],
            },
        ),
    )
    store = tmp_path / "store"
    identity = {
        "commit": "test",
        "files": {},
        "interpreter": {},
        "dependency_lock_sha256": "0" * 64,
    }
    with pytest.raises(processor_case.PlannedInterruption):
        processor_case.run_case(
            case_path,
            source_root,
            store,
            interrupt_at="incident-C0-state",
            source_identity=identity,
        )
    index_path = store / "inputs/source-index.json"
    index = json.loads(index_path.read_text())
    index["sources"][0]["rights_scope"] = "caller-rebound declaration"
    index_path.write_text(json.dumps(index))
    readback = processor_case.inspect_store(store)
    assert readback["integrity"] == "invalid"
    assert readback["errors"] == [
        f"ValueError: Retained source index declaration differs: {index['sources'][0]['id']}"
    ]


def test_public_command_parses_run_and_saved_readback():
    run = parser().parse_args(
        [
            "external-decision",
            "run",
            "--case",
            "case.json",
            "--sources",
            "sources",
            "--out",
            "result",
            "--interrupt-at",
            "incident-C0-state",
        ]
    )
    assert run.external_command == "run"
    inspect = parser().parse_args(["external-decision", "inspect", "result"])
    assert inspect.external_command == "inspect"

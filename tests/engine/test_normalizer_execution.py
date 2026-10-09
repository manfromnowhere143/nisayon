import copy
import hashlib
import json
from pathlib import Path

import numpy as np
import pytest

from nisayon.engine.io import digest
from nisayon.engine.normalizer_execution import (
    arrays_record,
    compare_arrays,
    decide_operation,
    execute_invocation,
    load_upstream_runtime,
    nest_statistics,
    numerical_map_signature,
    reference_outputs,
    validate_source_counter,
)

UTILS = """
import numpy as np

def apply_sin_cos_encoding(values):
    return np.concatenate([np.sin(values), np.cos(values)], axis=-1)

def nested_dict_to_numpy(data):
    if isinstance(data, dict):
        return {key: nested_dict_to_numpy(value) for key, value in data.items()}
    if isinstance(data, list):
        return np.array(data)
    return data

def normalize_values_minmax(values, params):
    result = np.zeros_like(values)
    mask = ~np.isclose(params["max"], params["min"])
    result[..., mask] = 2 * (values[..., mask] - params["min"][..., mask]) / (params["max"][..., mask] - params["min"][..., mask]) - 1
    return result

def unnormalize_values_minmax(values, params):
    return (np.clip(values, -1, 1) + 1) / 2 * (params["max"] - params["min"]) + params["min"]

def normalize_values_meanstd(values, params):
    result = np.zeros_like(values)
    mask = params["std"] != 0
    result[..., mask] = (values[..., mask] - params["mean"][..., mask]) / params["std"][..., mask]
    result[..., ~mask] = values[..., ~mask]
    return result

def unnormalize_values_meanstd(values, params):
    result = np.zeros_like(values)
    mask = params["std"] != 0
    result[..., mask] = values[..., mask] * params["std"][..., mask] + params["mean"][..., mask]
    result[..., ~mask] = values[..., ~mask]
    return result

def to_json_serializable(value):
    if is_dataclass(value) and not isinstance(value, type):
        return to_json_serializable(asdict(value))
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, dict):
        return {key: to_json_serializable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_json_serializable(item) for item in value]
    return value

def parse_modality_configs(configs):
    result = {}
    for embodiment, by_modality in configs.items():
        result[embodiment] = {}
        for modality, config in by_modality.items():
            result[embodiment][modality] = ModalityConfig(**config) if isinstance(config, dict) else config
    return result
"""

STATE_ACTION = """
class StateActionProcessor:
    def __init__(self, modality_configs, statistics=None, use_percentiles=False, clip_outliers=True, apply_sincos_state_encoding=False, use_relative_action=False):
        self.modality_configs = parse_modality_configs(modality_configs)
        self.statistics = {}
        self.norm_params = {}
        self.use_percentiles = use_percentiles
        self.clip_outliers = clip_outliers
        self.apply_sincos_state_encoding = apply_sincos_state_encoding
        self.use_relative_action = use_relative_action
        if statistics is not None:
            self.set_statistics(statistics)
        self.train()

    def train(self):
        self.training = True

    def set_statistics(self, statistics, override=False):
        for key in statistics:
            if key not in self.statistics or override:
                self.statistics[key] = deepcopy(statistics[key])
        self._compute_normalization_parameters()

    def _compute_normalization_parameters(self):
        for embodiment, modalities in self.statistics.items():
            self.norm_params[embodiment] = {}
            for modality in ("state", "action"):
                self.norm_params[embodiment][modality] = {}
                for key, stats in modalities[modality].items():
                    self.norm_params[embodiment][modality][key] = {
                        "min": np.array(stats["q01"] if self.use_percentiles else stats["min"]),
                        "max": np.array(stats["q99"] if self.use_percentiles else stats["max"]),
                        "mean": np.array(stats["mean"]),
                        "std": np.array(stats["std"]),
                        "dim": np.array(len(stats["mean"])),
                    }

    def apply_state(self, state, embodiment_tag):
        result = {}
        config = self.modality_configs[embodiment_tag]["state"]
        for key in config.modality_keys:
            params = self.norm_params[embodiment_tag]["state"][key]
            if config.mean_std_embedding_keys and key in config.mean_std_embedding_keys:
                result[key] = normalize_values_meanstd(state[key], params)
            else:
                result[key] = normalize_values_minmax(state[key], params)
                if self.clip_outliers:
                    result[key] = np.clip(result[key], -1, 1)
        return result

    def apply_action(self, action, embodiment_tag, state=None):
        result = {}
        config = self.modality_configs[embodiment_tag]["action"]
        for key in config.modality_keys:
            params = self.norm_params[embodiment_tag]["action"][key]
            if config.mean_std_embedding_keys and key in config.mean_std_embedding_keys:
                result[key] = normalize_values_meanstd(action[key], params)
            else:
                result[key] = normalize_values_minmax(action[key], params)
            if self.clip_outliers:
                result[key] = np.clip(result[key], -1, 1)
        return result

    def apply(self, state, action, embodiment_tag):
        return self.apply_state(state, embodiment_tag), self.apply_action(action, embodiment_tag, state)

    def get_action_dim(self, embodiment_tag):
        return sum(self.norm_params[embodiment_tag]["action"][key]["dim"].item() for key in self.modality_configs[embodiment_tag]["action"].modality_keys)
"""

PROCESSOR = """
class Gr00tN1d7Processor:
    def set_statistics(self, statistics, override=False):
        for key in statistics:
            if key not in self.statistics or override:
                self.statistics[key] = deepcopy(statistics[key])
        self.state_action_processor.set_statistics(statistics, override=override)
        self.action_dim = {}
        for embodiment_tag in self.state_action_processor.statistics:
            self.action_dim[embodiment_tag] = self.state_action_processor.get_action_dim(embodiment_tag)

    def save_pretrained(self, save_directory: str | Path):
        save_directory = Path(save_directory)
        save_directory.mkdir(parents=True, exist_ok=True)
        config_file = save_directory / "processor_config.json"
        statistics_file = save_directory / "statistics.json"
        embodiment_file = save_directory / "embodiment_id.json"
        config = {"processor_kwargs": {"modality_configs": to_json_serializable(self.modality_configs), "use_percentiles": self.use_percentiles, "use_mean_std": self.use_mean_std, "clip_outliers": self.clip_outliers, "apply_sincos_state_encoding": self.apply_sincos_state_encoding, "use_relative_action": self.use_relative_action}}
        config_file.write_text(json.dumps(config))
        statistics_file.write_text(json.dumps(to_json_serializable(self.state_action_processor.statistics)))
        embodiment_file.write_text(json.dumps(self.embodiment_id_mapping))
        return [config_file, statistics_file, embodiment_file]

    @classmethod
    def from_pretrained(cls, pretrained_model_name_or_path: str | Path, **kwargs):
        root = Path(pretrained_model_name_or_path)
        config = json.loads((root / "processor_config.json").read_text())
        statistics = json.loads((root / "statistics.json").read_text())
        processor_kwargs = config["processor_kwargs"]
        processor_kwargs["statistics"] = statistics
        processor_kwargs["embodiment_id_mapping"] = json.loads((root / "embodiment_id.json").read_text())
        return cls(**processor_kwargs)
"""


def _write_sources(tmp_path: Path):
    paths = {
        "utils": tmp_path / "utils.py",
        "state": tmp_path / "state_action.py",
        "processor": tmp_path / "processor.py",
    }
    for key, source in (("utils", UTILS), ("state", STATE_ACTION), ("processor", PROCESSOR)):
        paths[key].write_text(source)
    runtime = load_upstream_runtime(
        paths["processor"],
        paths["state"],
        paths["utils"],
        expected_processor_sha256=hashlib.sha256(PROCESSOR.encode()).hexdigest(),
        expected_state_action_sha256=hashlib.sha256(STATE_ACTION.encode()).hexdigest(),
        expected_data_utils_sha256=hashlib.sha256(UTILS.encode()).hexdigest(),
    )
    return runtime


def _config(mean_std=()):
    return {
        "demo": {
            "state": {"modality_keys": ["s"], "mean_std_embedding_keys": list(mean_std)},
            "action": {
                "modality_keys": ["a"],
                "mean_std_embedding_keys": list(mean_std),
                "action_configs": None,
            },
        }
    }


def _statistics(low, high, *, mean=5.0, std=2.0):
    values = {
        "min": [low],
        "max": [high],
        "mean": [mean],
        "std": [std],
        "q01": [low],
        "q99": [high],
    }
    return {"demo": {"state": {"s": copy.deepcopy(values)}, "action": {"a": values}}}


def _settings(**updates):
    result = {
        "input_dtype": "float32",
        "use_percentiles": False,
        "clip_outliers": True,
        "apply_sincos_state_encoding": False,
        "use_relative_action": False,
        "use_mean_std": False,
    }
    result.update(updates)
    return result


def test_exact_selection_body_distinguishes_outer_mirror_from_nested_state(tmp_path):
    runtime = _write_sources(tmp_path)
    initial, candidate = _statistics(0.0, 10.0), _statistics(0.0, 20.0)
    inputs = {"s": np.array([[5.0]], dtype=np.float32)}
    actions = {"a": np.array([[5.0]], dtype=np.float32)}

    execution = execute_invocation(
        runtime=runtime,
        modality_configs=_config(),
        initial_statistics=initial,
        candidate_statistics=candidate,
        override=False,
        embodiment="demo",
        state=inputs,
        action=actions,
        settings=_settings(),
        save_directory=tmp_path / "saved",
    )

    assert execution["selection"]["constructor_outer_statistics"] == {}
    assert execution["selection"]["selected_outer_sha256"] == digest(candidate)
    assert execution["selection"]["selected_nested_sha256"] == digest(initial)
    assert execution["outputs"]["state"]["s"].tolist() == [[0.0]]
    assert execution["reloaded"]["nested_statistics"] == initial
    assert execution["reloaded"]["state"]["s"].tolist() == [[0.0]]
    assert execution["network"]["attempts"] == []


def test_operation_decision_uses_active_numeric_state_and_persistence(tmp_path):
    runtime = _write_sources(tmp_path)
    initial, candidate = _statistics(0.0, 10.0), _statistics(0.0, 20.0)
    values = {
        "state": {"s": np.array([[5.0]], dtype=np.float32)},
        "action": {"a": np.array([[5.0]], dtype=np.float32)},
    }
    execution = execute_invocation(
        runtime=runtime,
        modality_configs=_config(),
        initial_statistics=initial,
        candidate_statistics=candidate,
        override=False,
        embodiment="demo",
        state=values["state"],
        action=values["action"],
        settings=_settings(),
        save_directory=tmp_path / "saved",
    )
    expected = reference_outputs(
        inputs=values,
        statistics=initial,
        embodiment="demo",
        mean_std_keys={"state": [], "action": []},
        sin_cos_state_keys=[],
        use_percentiles=False,
        clip_outliers=True,
    )
    comparison = compare_arrays(
        execution["outputs"]["state"], expected["state"], rtol=1e-6, atol=1e-7
    )
    persistence = compare_arrays(
        execution["outputs"]["state"], execution["reloaded"]["state"], rtol=0, atol=0
    )

    accepted = decide_operation(
        declared_operation="keep_existing",
        obligated_statistics=initial,
        candidate_statistics=candidate,
        execution=execution,
        reference_comparison=comparison,
        persistence_comparison=persistence,
    )
    refused = decide_operation(
        declared_operation="replace_with_candidate",
        obligated_statistics=candidate,
        candidate_statistics=candidate,
        execution=execution,
        reference_comparison=comparison,
        persistence_comparison=persistence,
    )

    assert accepted["status"] == "supported"
    assert refused["status"] == "rejected"
    assert refused["obligations"]["selection_procedure"] == "rejected"


def test_operation_decision_uses_effective_map_not_unused_percentiles(tmp_path):
    runtime = _write_sources(tmp_path)
    obligation = _statistics(0.0, 10.0)
    candidate = copy.deepcopy(obligation)
    for modality, key in (("state", "s"), ("action", "a")):
        candidate["demo"][modality][key]["q01"] = [-100.0]
        candidate["demo"][modality][key]["q99"] = [100.0]
    values = {
        "state": {"s": np.array([[2.5]], dtype=np.float32)},
        "action": {"a": np.array([[7.5]], dtype=np.float32)},
    }
    execution = execute_invocation(
        runtime=runtime,
        modality_configs=_config(),
        initial_statistics=obligation,
        candidate_statistics=candidate,
        override=True,
        embodiment="demo",
        state=values["state"],
        action=values["action"],
        settings=_settings(),
    )
    expected = reference_outputs(
        inputs=values,
        statistics=obligation,
        embodiment="demo",
        mean_std_keys={"state": [], "action": []},
        sin_cos_state_keys=[],
        use_percentiles=False,
        clip_outliers=True,
    )
    comparison = compare_arrays(
        {
            "state.s": execution["outputs"]["state"]["s"],
            "action.a": execution["outputs"]["action"]["a"],
        },
        {"state.s": expected["state"]["s"], "action.a": expected["action"]["a"]},
        rtol=0,
        atol=0,
    )

    decision = decide_operation(
        declared_operation="replace_with_candidate",
        obligated_statistics=obligation,
        candidate_statistics=candidate,
        execution=execution,
        reference_comparison=comparison,
        persistence_comparison=None,
    )

    assert decision["status"] == "supported"
    assert decision["observations"]["selected_is_candidate"] is True
    assert decision["observations"]["selected_exactly_obligation"] is False


def test_install_is_scoped_to_absence_of_target_embodiment(tmp_path):
    runtime = _write_sources(tmp_path)
    config = _config()
    config["other"] = copy.deepcopy(config["demo"])
    initial = {"other": _statistics(-1.0, 1.0)["demo"]}
    candidate = _statistics(0.0, 10.0)
    values = {
        "state": {"s": np.array([[5.0]], dtype=np.float32)},
        "action": {"a": np.array([[5.0]], dtype=np.float32)},
    }
    execution = execute_invocation(
        runtime=runtime,
        modality_configs=config,
        initial_statistics=initial,
        candidate_statistics=candidate,
        override=False,
        embodiment="demo",
        state=values["state"],
        action=values["action"],
        settings=_settings(),
    )
    expected = reference_outputs(
        inputs=values,
        statistics=candidate,
        embodiment="demo",
        mean_std_keys={"state": [], "action": []},
        sin_cos_state_keys=[],
        use_percentiles=False,
        clip_outliers=True,
    )
    comparison = compare_arrays(execution["outputs"]["state"], expected["state"], rtol=0, atol=0)

    decision = decide_operation(
        declared_operation="install_when_absent",
        obligated_statistics=candidate,
        candidate_statistics=candidate,
        execution=execution,
        reference_comparison=comparison,
        persistence_comparison=None,
    )

    assert set(execution["selection"]["selected_nested_statistics"]) == {"other", "demo"}
    assert decision["status"] == "supported"


def test_operation_decision_requires_call_record_bound_to_retained_outputs(tmp_path):
    runtime = _write_sources(tmp_path)
    statistics = _statistics(0.0, 10.0)
    values = {
        "state": {"s": np.array([[5.0]], dtype=np.float32)},
        "action": {"a": np.array([[5.0]], dtype=np.float32)},
    }
    execution = execute_invocation(
        runtime=runtime,
        modality_configs=_config(),
        initial_statistics=statistics,
        candidate_statistics=statistics,
        override=False,
        embodiment="demo",
        state=values["state"],
        action=values["action"],
        settings=_settings(),
    )
    execution["call_records"][2]["output_sha256"] = "0" * 64

    decision = decide_operation(
        declared_operation="keep_existing",
        obligated_statistics=statistics,
        candidate_statistics=statistics,
        execution=execution,
        reference_comparison={"matches": True},
        persistence_comparison=None,
    )

    assert decision["operation"] == "abstain"
    assert decision["status"] == "unresolved"


def test_nonfinite_executed_output_has_strict_json_call_binding(tmp_path):
    runtime = _write_sources(tmp_path)
    statistics = _statistics(0.0, 2.0, mean=1.0, std=1e-40)
    values = {
        "state": {"s": np.array([[0.75]], dtype=np.float32)},
        "action": {"a": np.array([[0.5]], dtype=np.float32)},
    }

    with np.errstate(over="ignore", invalid="ignore"):
        execution = execute_invocation(
            runtime=runtime,
            modality_configs=_config(["s"]),
            initial_statistics=statistics,
            candidate_statistics=statistics,
            override=False,
            embodiment="demo",
            state=values["state"],
            action=values["action"],
            settings=_settings(),
        )

    output_record = {
        "state": arrays_record(execution["outputs"]["state"]),
        "action": arrays_record(execution["outputs"]["action"]),
    }
    assert output_record["state"]["s"]["values"] == [["-Infinity"]]
    assert execution["call_records"][2]["output_sha256"] == digest(output_record)


def test_reference_tracks_effective_mode_constants_and_action_clipping():
    values = {
        "state": {"s": np.array([[8.0]], dtype=np.float32)},
        "action": {"a": np.array([[8.0]], dtype=np.float32)},
    }
    statistics = _statistics(1.0, 1.0 + 1e-10, mean=3.0, std=0.0)
    minmax = reference_outputs(
        inputs=values,
        statistics=statistics,
        embodiment="demo",
        mean_std_keys={"state": [], "action": []},
        sin_cos_state_keys=[],
        use_percentiles=False,
        clip_outliers=True,
    )
    meanstd = reference_outputs(
        inputs=values,
        statistics=statistics,
        embodiment="demo",
        mean_std_keys={"state": ["s"], "action": ["a"]},
        sin_cos_state_keys=[],
        use_percentiles=False,
        clip_outliers=True,
    )

    assert minmax["state"]["s"].tolist() == [[0.0]]
    assert meanstd["state"]["s"].tolist() == [[8.0]]
    assert meanstd["action"]["a"].tolist() == [[1.0]]


def test_signature_reports_inert_zero_std_and_constant_range():
    meanstd = numerical_map_signature(
        statistics=_statistics(0, 1, mean=99, std=0),
        modality_configs=_config(["s"]),
        embodiment="demo",
        settings=_settings(),
    )
    constant = numerical_map_signature(
        statistics=_statistics(1, 1 + 1e-10),
        modality_configs=_config(),
        embodiment="demo",
        settings=_settings(),
    )

    assert meanstd["state"]["s"]["coordinates"] == [{"kind": "identity_zero_std"}]
    assert constant["state"]["s"]["coordinates"] == [{"kind": "constant_zero"}]


def test_nested_statistics_preserve_declared_group_order():
    flat = {
        "observation.state": {
            name: [1.0, 2.0] for name in ("min", "max", "mean", "std", "q01", "q99")
        },
        "action": {name: [3.0] for name in ("min", "max", "mean", "std", "q01", "q99")},
    }
    nested = nest_statistics(
        flat,
        "demo",
        [{"key": "x", "start": 0, "end": 1}, {"key": "y", "start": 1, "end": 2}],
        [{"key": "a", "start": 0, "end": 1}],
    )

    assert list(nested["demo"]["state"]) == ["x", "y"]
    assert nested["demo"]["state"]["y"]["mean"] == [2.0]


def test_missing_execution_is_unresolved_and_counter_refuses_without_transport():
    result = decide_operation(
        declared_operation="keep_existing",
        obligated_statistics=_statistics(0, 1),
        candidate_statistics=_statistics(0, 2),
        execution=None,
        reference_comparison=None,
        persistence_comparison=None,
    )
    assert result["operation"] == "abstain"
    assert result["status"] == "unresolved"

    with pytest.raises(ValueError, match="exhausted before transport"):
        validate_source_counter(used=12, requested=1, maximum=12)
    assert validate_source_counter(used=4, requested=1, maximum=12)["remaining"] == 8


def test_source_digest_mismatch_refuses_before_compilation(tmp_path):
    runtime_paths = {
        "utils": tmp_path / "utils.py",
        "state": tmp_path / "state.py",
        "processor": tmp_path / "processor.py",
    }
    runtime_paths["utils"].write_text(UTILS)
    runtime_paths["state"].write_text(STATE_ACTION)
    runtime_paths["processor"].write_text(PROCESSOR)

    with pytest.raises(ValueError, match="Pinned upstream source mismatch"):
        load_upstream_runtime(
            runtime_paths["processor"],
            runtime_paths["state"],
            runtime_paths["utils"],
            expected_processor_sha256="0" * 64,
            expected_state_action_sha256=hashlib.sha256(STATE_ACTION.encode()).hexdigest(),
            expected_data_utils_sha256=hashlib.sha256(UTILS.encode()).hexdigest(),
        )


def test_array_comparison_rejects_dtype_even_when_values_match():
    result = compare_arrays(
        {"x": np.array([[1]], dtype=np.float32)},
        {"x": np.array([[1]], dtype=np.float64)},
        rtol=0,
        atol=0,
    )
    assert result["matches"] is False
    assert result["by_group"]["x"]["numeric_equal"] is True
    assert json.loads(json.dumps(result))["by_group"]["x"]["dtype_equal"] is False

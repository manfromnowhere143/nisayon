"""Run the reachable pinned statistics path without claiming a full GR00T import."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import logging
import os
import shutil
import subprocess
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np

from nisayon.engine.io import file_digest, write_json

EXPECTED = {
    "stats": "54fffdaa0a2bcf5356926e4d73b10dbbb9c848e0a56582427e4252f054938c74",
    "loader": "10eb986f35d298fc3e099f8891532a907978b34e0a2f88a9c62620c554d9726d",
    "mixture": "f452072c1191249adef45d98bf75239c792e019f4a088bc8dc09f10f7a7441a3",
}


def _function_module(source: Path, names: set[str], constants: set[str]) -> ast.Module:
    tree = ast.parse(source.read_text())
    body = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in names:
            body.append(node)
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            if any(isinstance(target, ast.Name) and target.id in constants for target in targets):
                body.append(node)
    return ast.fix_missing_locations(ast.Module(body=body, type_ignores=[]))


def _method_module(source: Path, class_name: str, names: set[str]) -> ast.Module:
    tree = ast.parse(source.read_text())
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            methods = [
                method
                for method in node.body
                if isinstance(method, (ast.FunctionDef, ast.AsyncFunctionDef))
                and method.name in names
            ]
            return ast.fix_missing_locations(ast.Module(body=methods, type_ignores=[]))
    raise ValueError(f"Missing class {class_name} in {source}")


def _exec(module: ast.Module, source: Path, namespace: dict[str, Any]) -> dict[str, Any]:
    exec(compile(module, str(source), "exec"), namespace)
    return namespace


class Sentinel:
    def __init__(self) -> None:
        self.calls = 0

    def __call__(self, *_args, **_kwargs):
        self.calls += 1
        raise AssertionError("Unreached upstream branch was called")


class DatasetRecorder:
    def __init__(self, statistics: dict[str, Any]) -> None:
        self.embodiment_tag = SimpleNamespace(value="libero")
        self.statistics = statistics
        self.processor = None

    def get_dataset_statistics(self) -> dict[str, Any]:
        return self.statistics

    def set_processor(self, processor: Any) -> None:
        self.processor = processor


class ProcessorRecorder:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def set_statistics(self, statistics: dict[str, Any], *, override: bool) -> None:
        encoded = json.dumps(statistics, sort_keys=True, separators=(",", ":")).encode()
        self.calls.append(
            {
                "override_argument": override,
                "statistics_sha256": hashlib.sha256(encoded).hexdigest(),
                "statistics": statistics,
            }
        )


def _copy_metadata(packet: Path, dataset: Path) -> None:
    mapping = {
        "groot-demo-info.json": "info.json",
        "groot-demo-episodes.jsonl": "episodes.jsonl",
        "groot-demo-tasks.jsonl": "tasks.jsonl",
        "groot-demo-modality.json": "modality.json",
        "groot-demo-stats.json": "stats.json",
    }
    meta = dataset / "meta"
    meta.mkdir(parents=True)
    for source, target in mapping.items():
        shutil.copyfile(packet / source, meta / target)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--packet-sources", type=Path, required=True)
    parser.add_argument("--captured-sources", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    stats_source = args.packet_sources / "groot-stats-1a1837.py"
    loader_source = args.captured_sources / "groot-lerobot-episode-loader-1a1837.py"
    mixture_source = args.captured_sources / "groot-sharded-mixture-dataset-1a1837.py"
    for name, source in (
        ("stats", stats_source),
        ("loader", loader_source),
        ("mixture", mixture_source),
    ):
        if file_digest(source) != EXPECTED[name]:
            raise ValueError(f"Pinned source digest mismatch: {source}")

    started_at = datetime.now(UTC).isoformat()
    start_wall = time.perf_counter()
    start_cpu = time.process_time()
    calculate_sentinel = Sentinel()
    writer_sentinel = Sentinel()

    with tempfile.TemporaryDirectory(prefix="nisayon-population-path-") as temporary:
        dataset = Path(temporary) / "dataset"
        _copy_metadata(args.packet_sources, dataset)
        stats_before = file_digest(dataset / "meta/stats.json")

        stats_namespace: dict[str, Any] = {
            "Any": Any,
            "Path": Path,
            "hashlib": hashlib,
            "json": json,
            "logger": logging.getLogger("population-path-probe"),
            "calculate_dataset_statistics": calculate_sentinel,
            "_dump_stats_cache_atomic": writer_sentinel,
        }
        stats_functions = {
            "_load_stats_cache",
            "_compute_stats_fingerprint",
            "_stale_features",
            "check_stats_validity",
            "generate_stats",
        }
        stats_constants = {
            "LE_ROBOT_DATA_FILENAME",
            "LE_ROBOT_INFO_FILENAME",
            "LE_ROBOT_STATS_FILENAME",
            "STATS_FINGERPRINTS_KEY",
        }
        _exec(
            _function_module(stats_source, stats_functions, stats_constants),
            stats_source,
            stats_namespace,
        )
        info = json.loads((dataset / "meta/info.json").read_text())
        float_features = [
            feature
            for feature, metadata in info["features"].items()
            if "float" in metadata["dtype"]
        ]
        cache_valid = stats_namespace["check_stats_validity"](dataset, float_features)
        stats_namespace["generate_stats"](dataset)
        stats_after = file_digest(dataset / "meta/stats.json")

        loader_namespace: dict[str, Any] = {
            "Any": Any,
            "Path": Path,
            "defaultdict": __import__("collections").defaultdict,
            "json": json,
        }
        _exec(
            _function_module(loader_source, {"_rec_defaultdict", "_to_plain_dict"}, set()),
            loader_source,
            loader_namespace,
        )
        _exec(
            _function_module(
                loader_source,
                set(),
                {
                    "LEROBOT_META_DIR_NAME",
                    "LEROBOT_INFO_FILENAME",
                    "LEROBOT_EPISODES_FILENAME",
                    "LEROBOT_TASKS_FILENAME",
                    "LEROBOT_MODALITY_FILENAME",
                    "LEROBOT_STATS_FILE_NAME",
                    "LEROBOT_RELATIVE_STATS_FILE_NAME",
                },
            ),
            loader_source,
            loader_namespace,
        )
        _exec(
            _method_module(
                loader_source, "LeRobotEpisodeLoader", {"_load_metadata", "get_dataset_statistics"}
            ),
            loader_source,
            loader_namespace,
        )
        loader = SimpleNamespace(dataset_path=dataset)
        loader_namespace["_load_metadata"](loader)
        loader.modality_configs = {
            name: SimpleNamespace(modality_keys=list(loader.modality_meta[name]))
            for name in ("state", "action")
        }
        statistics = loader_namespace["get_dataset_statistics"](loader)

        mixture_namespace: dict[str, Any] = {"np": np}
        _exec(
            _function_module(mixture_source, {"merge_statistics"}, set()),
            mixture_source,
            mixture_namespace,
        )
        mixture_method = _method_module(
            mixture_source, "ShardedMixtureDataset", {"merge_statistics"}
        )
        mixture_method.body[0].name = "_run_mixture_merge_statistics"
        _exec(mixture_method, mixture_source, mixture_namespace)
        processor_calls = []
        for override in (False, True):
            processor = ProcessorRecorder()
            recorded_dataset = DatasetRecorder(statistics)
            mixture = SimpleNamespace(
                datasets=[recorded_dataset],
                weights=[1.0],
                processor=processor,
                override_pretraining_statistics=override,
            )
            mixture_namespace["_run_mixture_merge_statistics"](mixture)
            processor_calls.extend(processor.calls)
            if recorded_dataset.processor is not processor:
                raise AssertionError("Pinned mixture method did not install the processor")

    result = {
        "schema": "nisayon.population-upstream-path-observation.v1",
        "case_id": "population-binding-001",
        "created_at": started_at,
        "producer_identity": {
            "command_record_id": os.environ.get("NISAYON_COMMAND_RECORD_ID"),
            "executed_source_commit": subprocess.check_output(
                ["git", "rev-parse", "HEAD"], text=True
            ).strip(),
        },
        "source": {
            "repository": "NVIDIA/Isaac-GR00T",
            "revision": "1a1837f20538b7d7e21f977a11a5aee14f99803c",
            "digests": EXPECTED,
        },
        "observations": {
            "float_features_checked": float_features,
            "cache_valid": cache_valid,
            "calculate_dataset_statistics_calls": calculate_sentinel.calls,
            "statistics_writer_calls": writer_sentinel.calls,
            "statistics_sha256_before": stats_before,
            "statistics_sha256_after": stats_after,
            "metadata_episode_count": len(loader.episodes_metadata),
            "statistics_groups": {
                modality: {key: len(values["mean"]) for key, values in groups.items()}
                for modality, groups in statistics.items()
            },
            "processor_set_statistics_calls": processor_calls,
        },
        "interpretation_boundary": {
            "established": [
                "The unchanged generate_stats body accepts the copied published schema fingerprints and does not reach recomputation or writing.",
                "The unchanged loader methods load that stats.json and slice it into state/action groups.",
                "The unchanged one-dataset mixture methods pass those values and the override_pretraining_statistics boolean to processor.set_statistics.",
            ],
            "unresolved": [
                "The unavailable BaseProcessor implementation's false/true precedence semantics.",
                "The historical invocation's override_pretraining_statistics value.",
                "The population that originally produced the published numeric values.",
                "A full upstream import or CLI execution.",
            ],
        },
        "substitutions": [
            "Selected function and method bodies were compiled unchanged from digest-verified pinned sources instead of importing the unavailable GR00T package.",
            "A temporary metadata-only dataset replaced video and Parquet access; the actual cache-hit branch did not request Parquet.",
            "One recorded dataset replaced sharding/distributed setup.",
            "A processor recorder captured set_statistics arguments but did not implement or infer precedence.",
            "The extracted mixture method was renamed only in the harness namespace to avoid shadowing the pinned module-level function of the same name.",
        ],
        "process": {"status": "completed", "exit_code": 0},
        "costs": {
            "inner_wall_seconds_before_write": time.perf_counter() - start_wall,
            "inner_process_cpu_seconds_before_write": time.process_time() - start_cpu,
            "dependency_download_bytes": 0,
            "temporary_dependency_bytes": 0,
            "unknown": [
                "active engineering effort",
                "energy",
                "provider charges",
                "unsampled memory peak",
            ],
        },
        "scientific_status": "neutral_observation_not_a_population_or_operation_verdict",
    }
    write_json(args.output, result)
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()

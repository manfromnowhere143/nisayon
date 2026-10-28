"""Exact camera comparisons must preserve JSON value types."""

import copy
import importlib.util
import json
import tarfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def load(name):
    path = ROOT / "examples/qualification/scoped_checks" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"scoped_camera_{name}", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def observation():
    path = ROOT / "docs/experiments/results/camera-slot-qualification-2026-10-28/evidence.tar.gz"
    with tarfile.open(path) as archive:
        prefix = "native/pr5129-17/"
        return {
            "actual": json.load(archive.extractfile(prefix + "actual.json")),
            "expected": {
                mode: json.load(archive.extractfile(prefix + f"expected-{mode}.json"))
                for mode in ("configured_budget", "all_configured_slots")
            },
        }


@pytest.fixture(params=["producer", "reviewer"])
def score(request):
    if request.param == "producer":
        module = load("score")

        def evaluate(observation, mode):
            module.MODE = mode
            return module.evaluate(observation)

        return evaluate
    module = load("review")
    return lambda observation, mode: module.camera_score(
        observation["actual"], observation["expected"][mode], mode
    )


@pytest.mark.parametrize("mutation", ["integer_mask", "float_mask", "float_shape", "integer_flag"])
def test_typed_mismatch_cannot_count_as_exact_camera_success(observation, score, mutation):
    altered = copy.deepcopy(observation)
    row = next(row for row in altered["actual"]["conditions"] if "masks" in row)
    if mutation == "integer_mask":
        row["masks"][0]["values"][0] = 1
    elif mutation == "float_mask":
        row["masks"][0]["values"][0] = 1.0
    elif mutation == "float_shape":
        row["masks"][0]["shape"][0] = 2.0
    else:
        row["input_unchanged"] = 1
    result = score(altered, "configured_budget")
    assert result == {
        "mode": "configured_budget",
        "matched": 351,
        "assigned": 352,
        "holds": False,
    }


@pytest.mark.parametrize(
    "mode,matched", [("configured_budget", 352), ("all_configured_slots", 316)]
)
def test_original_positive_and_negative_camera_rows_keep_their_scores(
    observation, score, mode, matched
):
    result = score(observation, mode)
    assert result == {
        "mode": mode,
        "matched": matched,
        "assigned": 352,
        "holds": matched == 352,
    }

"""Controlled wrapper of OpenPI's native statistics loader, not a robot policy."""

from pathlib import Path

import native


def reference(value):
    # Independent fixed oracle: the calibration specified by this constructed case.
    return {"action": [(item - 10) / 10 for item in value["position"]]}


def candidate(value):
    stats = native.load(Path(__file__).parent / "stats")["action"]
    return {
        "action": [
            (item - float(mean)) / float(std)
            for item, mean, std in zip(value["position"], stats.mean, stats.std, strict=True)
        ]
    }


def negative_control(value):
    result = candidate(value)
    result["action"][0] *= -1
    return result

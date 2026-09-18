"""One public frozen policy; verify bytes before loading the upstream pickle."""

import json
import time
import urllib.request
from pathlib import Path

from .io import file_digest

POLICY_NAME = "lift_ph_low_dim_epoch_1000_succ_100.pth"
POLICY_URL = (
    "https://downloads.cs.stanford.edu/downloads/rt_benchmark/model_zoo/lift/bc_rnn/" + POLICY_NAME
)
POLICY_SHA256 = "3ee222cab41f78ba27afca7ef6f70f9f21bd3cc0a37bd79c0b2351dbede51605"


def translate_checkpoint(checkpoint: dict) -> dict:
    """Supply three newly required defaults; preserve all original config values.

    Transformer is disabled for this LSTM. Optimizer defaults are needed during
    construction only; the checkpoint runs in eval mode without optimizer steps.
    robomimic's own update_config translates its old observation encoder format.
    """
    translated = dict(checkpoint)
    config = json.loads(checkpoint["config"])
    config["algo"].setdefault("transformer", {"enabled": False})
    optimizer = config["algo"]["optim_params"]["policy"]
    optimizer.setdefault("optimizer_type", "adam")
    optimizer["learning_rate"].setdefault("scheduler_type", "multistep")
    translated["config"] = json.dumps(config)
    return translated


def prepare_policy(directory: Path) -> tuple[Path, dict]:
    start = time.perf_counter()
    path = directory / POLICY_NAME
    directory.mkdir(parents=True, exist_ok=True)
    downloaded = not path.exists()
    if downloaded:
        partial = path.with_suffix(".partial")
        urllib.request.urlretrieve(POLICY_URL, partial)
        if file_digest(partial) != POLICY_SHA256:
            raise ValueError(f"Policy digest mismatch; retained download: {partial}")
        partial.rename(path)
    if file_digest(path) != POLICY_SHA256:
        raise ValueError(f"Policy digest mismatch: {path}")
    return path, {
        "url": POLICY_URL,
        "sha256": POLICY_SHA256,
        "bytes": path.stat().st_size,
        "downloaded": downloaded,
        "preparation_wall_s": time.perf_counter() - start,
        "training": "public frozen BC-RNN checkpoint; no local training",
        "code_terms": "robomimic MIT; robosuite MIT; MuJoCo Apache-2.0",
        "checkpoint_terms": "Public model-zoo download; separate weights license not specified",
        "distribution": "download recipe only; weights excluded from Git",
    }

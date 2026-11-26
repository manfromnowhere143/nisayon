"""Execute pinned native input handling, with no learned model or task run."""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import platform
import resource
import site
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
parser = argparse.ArgumentParser(__doc__)
parser.add_argument("--fallback-site", type=Path, required=True)
parser.add_argument("--out", type=Path)
parser.add_argument("--freeze", action="store_true")
args = parser.parse_args()
site.addsitedir(str(args.fallback_site))

import numpy as np
import torch
from lerobot.configs.types import FeatureType, PolicyFeature
from lerobot.inference import FeatureSpec, ObservationSnapshot, PolicyRunner
from lerobot.policies.pi05.configuration_pi05 import PI05Config
from lerobot.policies.pi05.modeling_pi05 import PI05Policy
from lerobot.processor import PolicyProcessorPipeline

from candidates import all_visual_optional, synthetic_only

torch.set_num_threads(1)
A, B, STATE = "observation.images.image", "observation.images.image2", "observation.state"
BASE_CASES = (
    "all_supplied", "omit_synthetic", "missing_first_real", "missing_last_real",
    "missing_state", "unknown_feature", "bad_camera_shape", "bad_state_shape",
    "wrong_camera_kind", "duplicate_feature", "no_visual", "black_real",
    "reverse_request_keys", "request_missing", "request_extra", "request_dtype",
    "request_shape", "request_nan",
)
VARIANTS = ("original", "synthetic_only", "all_visual_optional")
ASSIGNMENT = [
    {"resolution": [h, w], "empty_cameras": n, "case": case, "variant": variant}
    for h, w in ((8, 10), (256, 256))
    for n in (0, 1, 2)
    for case in BASE_CASES
    for variant in VARIANTS
]


class Narrow(PI05Policy):
    validate_chunk_input_features = synthetic_only


class Broad(PI05Policy):
    validate_chunk_input_features = all_visual_optional


def digest(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def expected(case: str, n: int, variant: str) -> bool:
    if case in ("all_supplied", "black_real", "reverse_request_keys"):
        return True
    if case == "omit_synthetic":
        return n == 0 or variant != "original"
    if case in ("missing_first_real", "missing_last_real"):
        return variant == "all_visual_optional"
    return False


def runtime():
    packages = {}
    for name in ("torch", "torchvision", "numpy", "transformers", "draccus",
                 "huggingface-hub", "safetensors", "einops", "gymnasium",
                 "pillow", "packaging"):
        packages[name] = importlib.metadata.version(name)
    import lerobot.policies.pi05.modeling_pi05 as pi
    import lerobot.policies.pretrained as pretrained
    import lerobot.inference.policy_runner as runner
    import lerobot.utils.feature_spec as feature_spec
    modules = [pi, pretrained, runner, feature_spec]
    return {
        "python": sys.version, "platform": platform.platform(),
        "packages": packages,
        "native_files": {str(Path(m.__file__).resolve()): digest(Path(m.__file__)) for m in modules},
        "loaded_network_weights": False, "learned_model_constructed": False,
        "processor_pipeline": "empty; preprocessing/tokenization/normalization not tested",
    }


def spec(cfg, name, shape=None, kind=None):
    pf = cfg.input_features[name]
    if pf.type == FeatureType.VISUAL:
        return FeatureSpec(name, shape or (pf.shape[1], pf.shape[2], pf.shape[0]),
                           "uint8", kind=kind or "rgb", semantics="Synthetic RGB HWC uint8 camera test pattern")
    return FeatureSpec(name, shape or tuple(pf.shape), "float32", kind=kind or "tensor", semantics="Synthetic state vector; physical units unbound")


def setup(row):
    h, w = row["resolution"]
    rh, rw = (224, 224) if (h, w) == (256, 256) else (h, w)
    n, case, variant = row["empty_cameras"], row["case"], row["variant"]
    cfg = PI05Config(
        device="cpu", compile_model=False, empty_cameras=n, image_resolution=(rh, rw),
        chunk_size=4, n_action_steps=4,
        input_features={
            A: PolicyFeature(FeatureType.VISUAL, (3, h, w)),
            B: PolicyFeature(FeatureType.VISUAL, (3, h, w)),
            STATE: PolicyFeature(FeatureType.STATE, (8,)),
        },
        output_features={"action": PolicyFeature(FeatureType.ACTION, (7,))},
    )
    cfg.validate_features()
    cls = {"original": PI05Policy, "synthetic_only": Narrow, "all_visual_optional": Broad}[variant]
    policy = cls.__new__(cls)
    torch.nn.Module.__init__(policy)
    policy.config = cfg
    policy.register_parameter("_device_probe", torch.nn.Parameter(torch.zeros(()), requires_grad=False))
    arrays = {
        A: (np.arange(h*w*3).reshape(h,w,3) % 256).astype(np.uint8),
        B: ((np.arange(h*w*3).reshape(h,w,3) * 7 + 31) % 256).astype(np.uint8),
        STATE: np.arange(8, dtype=np.float32),
    }
    for i in range(n):
        arrays[f"observation.images.empty_camera_{i}"] = np.zeros((rh,rw,3), dtype=np.uint8)
    names = list(cfg.input_features)
    if case == "omit_synthetic":
        names = [A, B, STATE]
    if case == "missing_first_real":
        names.remove(A)
    if case == "missing_last_real":
        names.remove(B)
    if case == "missing_state":
        names.remove(STATE)
    if case == "no_visual":
        names = [STATE]
    features = [spec(cfg, name) for name in names]
    if case == "unknown_feature":
        features.append(FeatureSpec("unknown", (1,), "float32", semantics="Intentionally undeclared test input"))
        arrays["unknown"] = np.zeros(1, dtype=np.float32)
    if case == "bad_camera_shape":
        features[0] = spec(cfg, A, shape=(h+1,w,3))
    if case == "bad_state_shape":
        features[names.index(STATE)] = spec(cfg, STATE, shape=(9,))
    if case == "wrong_camera_kind":
        features[0] = spec(cfg, A, kind="tensor")
    if case == "duplicate_feature":
        features.append(features[0])
    request = {name: arrays[name].copy() for name in names}
    if case == "black_real":
        request[A].fill(0)
    if case == "reverse_request_keys":
        request = dict(reversed(list(request.items())))
    if case == "request_missing":
        del request[A]
    if case == "request_extra":
        request["unknown"] = np.zeros(1, dtype=np.float32)
    if case == "request_dtype":
        request[A] = request[A].astype(np.float32)
    if case == "request_shape":
        request[A] = request[A][:-1]
    if case == "request_nan":
        request[STATE][0] = np.nan
    return policy, tuple(features), request


def tensor_record(value):
    a = value.detach().cpu().numpy().copy()
    return {"shape": list(a.shape), "dtype": a.dtype.name,
            "sha256": hashlib.sha256(a.tobytes(order="C")).hexdigest(),
            "values": a.tolist() if a.size <= 16 else None}


def main():
    paths = [HERE / p for p in ("PROTOCOL.md", "AMENDMENT-01.md", "candidates.py", "matrix_v2.py", "records/source-acquisition.json", "records/checkpoint-config.json")]
    identity = {str(p.relative_to(HERE)): digest(p) for p in paths}
    freeze_path = HERE / "records/freeze-v2.json"
    if args.freeze:
        if freeze_path.exists():
            raise ValueError("Freeze already exists")
        freeze = {
            "schema": "nisayon.research.serving_intake.freeze.v1",
            "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "files": identity, "runtime": runtime(),
            "assignment": [{**r, "expected_accept": expected(r["case"], r["empty_cameras"], r["variant"])}
                           for r in ASSIGNMENT],
            "scope": "native feature and request preparation only; no deployment acceptance",
            "confirmation": "32 fresh paired tasks not run",
        }
        freeze_path.write_text(json.dumps(freeze, indent=2, allow_nan=False)+"\n")
        print(json.dumps({"frozen_rows": len(ASSIGNMENT), "sha256": digest(freeze_path)}))
        return
    freeze = json.loads(freeze_path.read_text())
    if freeze["files"] != identity or freeze["runtime"] != runtime():
        raise ValueError("Source/runtime changed since freeze")
    if freeze["assignment"] != [
        {**r, "expected_accept": expected(r["case"], r["empty_cameras"], r["variant"])} for r in ASSIGNMENT
    ]:
        raise ValueError("Assignment changed")
    if args.out is None:
        raise ValueError("--out required")
    args.out.mkdir(parents=True, exist_ok=False)
    raw = {}
    rows = []
    start = time.perf_counter()
    with (args.out / "rows.jsonl").open("x") as stream:
        for index, assignment in enumerate(freeze["assignment"]):
            record = {"index": index, **assignment, "stage": "configuration"}
            policy, features, request = setup(assignment)
            for name, value in request.items():
                raw[f"row{index}_input_{name}"] = value
            try:
                record["stage"] = "negotiation"
                runner = PolicyRunner(
                    policy, PolicyProcessorPipeline(steps=[]), PolicyProcessorPipeline(steps=[]),
                    action_interval=.1, features=features,
                    action_feature=FeatureSpec("action", (7,), "float32", semantics="Unused action shape; no learned inference or execution"),
                )
                record["stage"] = "request"
                snapshot = ObservationSnapshot(request, capture_time=1., task="intake software probe")
                batch = runner._batch(snapshot)
                record["stage"] = "images"
                images, masks = policy._preprocess_images(batch)
                # Independent conversion uses NumPy, bypassing runner._batch.
                direct = {
                    name: torch.from_numpy(
                        (value.transpose(2,0,1).astype(np.float32) / np.float32(255))[None].copy()
                        if value.ndim == 3 else value[None].copy()
                    ) for name, value in request.items()
                }
                d_images, d_masks = policy._preprocess_images(direct)
                record["direct_match"] = (len(images) == len(d_images)
                    and all(torch.equal(x,y) for x,y in zip(images, d_images))
                    and all(torch.equal(x,y) for x,y in zip(masks, d_masks)))
                record["images"] = [tensor_record(v) for v in images]
                record["masks"] = [tensor_record(v) for v in masks]
                for k,v in enumerate(images):
                    raw[f"row{index}_image{k}"] = v.detach().cpu().numpy().copy()
                for k,v in enumerate(masks):
                    raw[f"row{index}_mask{k}"] = v.detach().cpu().numpy().copy()
                record["accepted"] = True
                record["stage"] = "complete"
            except ValueError as error:
                # Expected native refusal only. Other exceptions abort, preserving prefix.
                record.update(accepted=False, exception_type=type(error).__name__, error=str(error))
            record["matches_frozen_expectation"] = record["accepted"] == record["expected_accept"]
            rows.append(record)
            stream.write(json.dumps(record, allow_nan=False)+"\n")
            stream.flush()
    np.savez_compressed(args.out / "arrays.npz", **raw)
    summary = {
        "rows": len(rows), "accepted": sum(r["accepted"] for r in rows),
        "unexpected": sum(not r["matches_frozen_expectation"] for r in rows),
        "direct_mismatches": sum(r.get("direct_match") is False for r in rows),
        "matrix_seconds": time.perf_counter()-start,
        "peak_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        "freeze_sha256": digest(freeze_path),
        "arrays_sha256": digest(args.out / "arrays.npz"),
        "rows_sha256": digest(args.out / "rows.jsonl"),
        "scope": freeze["scope"], "confirmation": freeze["confirmation"],
    }
    (args.out / "summary.json").write_text(json.dumps(summary, indent=2)+"\n")
    print(json.dumps(summary))
    if summary["unexpected"] or summary["direct_mismatches"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

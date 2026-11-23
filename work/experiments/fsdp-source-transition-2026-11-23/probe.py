"""Bounded CPU/Gloo observation of reviewed FSDP2 loader functions.

This executes only the pinned function AST, never the upstream module/package.
Native broadcast, DTensor distribution and load_state_dict are not mocked.
The observer records pre-assignment ownership; score.py decides the contract.
"""

import argparse
import ast
import hashlib
import inspect
import json
import math
import os
import traceback
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import torch
import torch.distributed as dist
from torch.distributed.device_mesh import init_device_mesh
from torch.distributed.fsdp import fully_shard
from torch.distributed.tensor import DTensor


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def loader_from(path):
    source = Path(path).read_text()
    tree = ast.parse(source)
    nodes = [
        n
        for n in tree.body
        if isinstance(n, ast.FunctionDef) and n.name == "fsdp2_load_full_state_dict"
    ]
    assert len(nodes) == 1 and not nodes[0].decorator_list
    # The exact reviewed function has no dependency on upstream module globals
    # other than torch. This is scope isolation, not a sandbox.
    namespace = {"torch": torch}
    code = compile(ast.Module(body=nodes, type_ignores=[]), str(path), "exec")
    exec(code, namespace)
    return namespace[nodes[0].name]


def conditions(phase):
    rows = []
    if phase == "development":
        for size in (1, 9):
            for nonmain in ("empty", "meta", "different"):
                for owned in (False, True):
                    rows.append(
                        dict(
                            rows=size,
                            layout="managed",
                            nonmain=nonmain,
                            owned=owned,
                            offload_flag=False,
                            dtype="float32",
                            offset=0,
                        )
                    )
        for dtype in ("float32", "bfloat16"):
            for owned in (False, True):
                for flag in (False, True):
                    rows.append(
                        dict(
                            rows=5,
                            layout="mixed",
                            nonmain="empty" if dtype == "float32" else "different",
                            owned=owned,
                            offload_flag=flag,
                            dtype=dtype,
                            offset=0,
                        )
                    )
    elif phase == "confirmation":
        for dtype in ("float32", "bfloat16"):
            for owned in (False, True):
                for flag in (False, True):
                    rows.append(
                        dict(
                            rows=3,
                            layout="mixed",
                            nonmain="meta",
                            owned=owned,
                            offload_flag=flag,
                            dtype=dtype,
                            offset=30,
                        )
                    )
    else:
        rows.append(
            dict(
                rows=5,
                layout="mixed",
                nonmain="empty",
                owned=False,
                offload_flag=False,
                dtype="float32",
                offset=0,
            )
        )
    return [{"case": i, **r} for i, r in enumerate(rows)]


class TinyState(torch.nn.Module):
    def __init__(self, rows, dtype, mixed):
        super().__init__()
        self.managed = torch.nn.Linear(8, rows, device="meta", dtype=dtype)
        if mixed:
            self.ignored = torch.nn.Linear(8, 2, bias=False, device="meta", dtype=dtype)
            self.register_buffer("scale", torch.empty(3, device="meta", dtype=dtype))
            self.register_buffer("counter", torch.empty((), device="meta", dtype=torch.int64))


def values(spec, index, offset):
    shape, dtype = spec
    return (
        torch.arange(math.prod(shape), dtype=torch.int64).reshape(shape) + index * 17 + offset
    ).to(dtype)


def observe(loader, condition, rank, mesh):
    dtype = getattr(torch, condition["dtype"])
    model = TinyState(condition["rows"], dtype, condition["layout"] == "mixed")
    specs = {k: (v.shape, v.dtype) for k, v in model.state_dict().items()}
    ignored = {model.ignored.weight} if condition["layout"] == "mixed" else set()
    fully_shard(model, mesh=mesh, ignored_params=ignored)
    full = {
        name: values(spec, i, condition["offset"] + rank * 100)
        for i, (name, spec) in enumerate(specs.items())
    }
    if rank == 1 and condition["nonmain"] == "empty":
        full.clear()
    elif rank == 1 and condition["nonmain"] == "meta":
        full = {k: v.to("meta") for k, v in full.items()}
    before = {k: v.clone() for k, v in full.items()}
    object_ids = {k: id(v) for k, v in full.items()}
    assignments = []
    native_load = model.load_state_dict

    def observe_assignment(*args, **kwargs):
        assignments.append({"source_keys": sorted(full), "assign": kwargs.get("assign")})
        return native_load(*args, **kwargs)

    outcome = {
        **condition,
        "rank": rank,
        "status": "not_run",
        "assignments": assignments,
        "source_keys_before": sorted(full),
        "value_checks": [],
        "borrowed_unchanged": None,
        "consumption_argument_supported": "consume_full_state_dict"
        in inspect.signature(loader).parameters,
    }
    try:
        options = {"cpu_offload": condition["offload_flag"]}
        if condition["owned"] and outcome["consumption_argument_supported"]:
            options["consume_full_state_dict"] = True
        accelerator = SimpleNamespace(is_main_process=rank == 0, device=torch.device("cpu"))
        with patch.object(model, "load_state_dict", side_effect=observe_assignment):
            returned = loader(accelerator, model, full, **options)
        outcome["returned_original_model"] = returned is model
        outcome["source_keys_after"] = sorted(full)
        borrowed = full.keys() == before.keys()
        if borrowed:
            for name, previous in before.items():
                value = full[name]
                borrowed = (
                    borrowed
                    and id(value) == object_ids[name]
                    and value.dtype == previous.dtype
                    and value.device == previous.device
                )
                if value.device.type != "meta":
                    borrowed = borrowed and torch.equal(value, previous)
        outcome["borrowed_unchanged"] = bool(borrowed)
        actual = model.state_dict()
        outcome["state_keys_match"] = actual.keys() == specs.keys()
        for i, (name, spec) in enumerate(specs.items()):
            expected = values(spec, i, condition["offset"])
            value = actual[name]
            sharded = isinstance(value, DTensor)
            if sharded:
                shard_size = math.ceil(expected.shape[0] / 2)
                expected = expected[rank * shard_size : (rank + 1) * shard_size]
                value = value.to_local()
            outcome["value_checks"].append(
                {
                    "name": name,
                    "sharded": sharded,
                    "expected_sharded": name.startswith("managed."),
                    "shape": list(value.shape),
                    "expected_shape": list(expected.shape),
                    "dtype": str(value.dtype),
                    "expected_dtype": str(expected.dtype),
                    "device": str(value.device),
                    "exact_values": bool(torch.equal(value.cpu(), expected)),
                }
            )
        outcome["status"] = "executed"
    except Exception as exc:
        outcome.update(
            status="error",
            error_type=type(exc).__name__,
            error=str(exc),
            traceback=traceback.format_exc(),
        )
    return outcome


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--source-sha256", required=True)
    parser.add_argument(
        "--phase", choices=("development", "confirmation", "old-composition"), required=True
    )
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    assert digest(args.source) == args.source_sha256
    loader = loader_from(args.source)
    dist.init_process_group("gloo", timeout=timedelta(seconds=20))
    rank = dist.get_rank()
    assert dist.get_world_size() == 2
    torch.set_num_threads(1)
    try:
        mesh = init_device_mesh("cpu", (2,))
        rows = [observe(loader, c, rank, mesh) for c in conditions(args.phase)]
        dist.barrier()
        assert digest(args.source) == args.source_sha256
        payload = {
            "schema": "nisayon.fsdp_source_transition.observations.v1",
            "source_sha256": args.source_sha256,
            "probe_sha256": digest(__file__),
            "torch": torch.__version__,
            "rank": rank,
            "world_size": 2,
            "backend": "gloo",
            "device": "cpu",
            "phase": args.phase,
            "rows": rows,
            "limits": [
                "CPU loader flag is not CUDA CPUOffloadPolicy execution",
                "No forward, backward, optimizer, full prepare_model or GPU memory measurement",
                "Dictionary lifetime is not proof all backing storage was freed",
            ],
        }
        with (args.out / f"rank-{rank}.json").open("x") as stream:
            json.dump(payload, stream, indent=2)
            stream.write("\n")
        print(
            json.dumps(
                {
                    "rank": rank,
                    "rows": len(rows),
                    "executed": sum(r["status"] == "executed" for r in rows),
                }
            ),
            flush=True,
        )
    finally:
        dist.destroy_process_group()


if __name__ == "__main__":
    os.environ.setdefault("OMP_NUM_THREADS", "1")
    main()

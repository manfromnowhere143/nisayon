"""Execute the already exposed camera matrix in its separately locked environment."""

import os
import subprocess
import time

from nisayon.engine.io import decode_json, write_json
from nisayon.qualification import ExecutionContext
from nisayon.qualification.context import environment_record


def collect(ctx, seed_key):
    runtime, panel = ctx.input("runtime"), ctx.input("panel")
    expected = runtime["native_context"]
    context = ExecutionContext.from_project(
        expected["project"],
        output_dir=expected["output_dir"],
        python=expected["python"],
        timeout_seconds=expected["timeout_seconds"],
        total_seconds=expected["total_seconds"],
    )
    if context.record() != expected or environment_record() != runtime["host_environment"]:
        raise ValueError("Execution environment changed")
    output = ctx.directory / "native"
    command = [
        expected["python"],
        "-B",
        runtime["runner"],
        expected["project"],
        str(panel[seed_key]),
        str(output),
    ]
    write_json(ctx.directory / "native-intent.json", {"command": command, "seed": panel[seed_key]})
    started = time.perf_counter()
    with (ctx.directory / "native.log").open("x") as log:
        result = subprocess.run(
            command,
            stdout=log,
            stderr=subprocess.STDOUT,
            timeout=120,
            env=dict(
                os.environ,
                PYTHONDONTWRITEBYTECODE="1",
                HF_HUB_OFFLINE="1",
                TRANSFORMERS_OFFLINE="1",
                CUDA_VISIBLE_DEVICES="",
                OMP_NUM_THREADS="1",
            ),
        )
    write_json(
        ctx.directory / "native-completion.json",
        {
            "returncode": result.returncode,
            "whole_process_seconds": time.perf_counter() - started,
        },
    )
    if result.returncode != 0:
        raise ValueError("Native attempt failed; original prefix retained")
    if context.record() != expected or environment_record() != runtime["host_environment"]:
        raise ValueError("Execution environment changed")
    return {
        "seed": panel[seed_key],
        "actual": decode_json((output / "actual.json").read_bytes()),
        "expected": {
            mode: decode_json((output / f"expected-{mode}.json").read_bytes())
            for mode in panel["modes"]
        },
    }

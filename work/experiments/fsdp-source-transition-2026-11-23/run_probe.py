"""Run the frozen local CPU probe with timeout/RSS accounting; no installation."""

import argparse
import hashlib
import importlib.util
import json
import os
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

import psutil

ROOT = Path(__file__).resolve().parent


def run(source, phase, output):
    source, output = Path(source).resolve(), Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    probe_hash = hashlib.sha256((ROOT / "probe.py").read_bytes()).hexdigest()
    protocol = json.loads((ROOT / "protocol.json").read_text())
    assert probe_hash == protocol["frozen_files"]["probe.py"]["sha256"]
    assert (
        hashlib.sha256((ROOT / "score.py").read_bytes()).hexdigest()
        == protocol["frozen_files"]["score.py"]["sha256"]
    )
    # Use numeric loopback: this host's standalone rendezvous selected an
    # unresolvable IPv6 reverse name. A port collision is an execution failure.
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as reservation:
        reservation.bind(("127.0.0.1", 0))
        port = reservation.getsockname()[1]
    command = [
        sys.executable,
        "-m",
        "torch.distributed.run",
        "--nnodes=1",
        "--rdzv_backend=static",
        "--master_addr=127.0.0.1",
        f"--master_port={port}",
        "--nproc_per_node=2",
        str(ROOT / "probe.py"),
        "--source",
        str(source),
        "--source-sha256",
        source_hash,
        "--phase",
        phase,
        "--out",
        str(output),
    ]
    start, peak, stop = time.perf_counter(), 0, None
    with (output / "native.log").open("x") as log:
        process = subprocess.Popen(
            command,
            stdout=log,
            stderr=subprocess.STDOUT,
            cwd=ROOT,
            env={
                **os.environ,
                "OMP_NUM_THREADS": "1",
                "GLOO_SOCKET_IFNAME": "lo0" if sys.platform == "darwin" else "lo",
            },
            start_new_session=True,
        )
        while process.poll() is None:
            try:
                tree = [psutil.Process(process.pid)]
                tree += tree[0].children(recursive=True)
                rss = sum(p.memory_info().rss for p in tree if p.is_running())
                peak = max(peak, rss)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
            if time.perf_counter() - start > protocol["budget"]["seconds_per_native_run"]:
                stop = "timeout"
            if peak > protocol["budget"]["sampled_process_tree_rss_bytes"]:
                stop = "rss_budget"
            if stop:
                os.killpg(process.pid, signal.SIGTERM)
                try:
                    process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                break
            time.sleep(0.05)
        returncode = process.wait()
    native_seconds = time.perf_counter() - start
    spec = importlib.util.spec_from_file_location("frozen_score", ROOT / "score.py")
    scorer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(scorer)
    score_start = time.perf_counter()
    expected = {"development": 20, "confirmation": 8, "old-composition": 1}[phase]
    result = scorer.score(output, expected, source_hash, probe_hash)
    if returncode != 0 or stop:
        result["status"] = "unresolved"
        result["unresolved"].append(f"runner exit={returncode}, budget_stop={stop}")
    record = {
        "command": command,
        "exit_code": returncode,
        "budget_stop": stop,
        "source_sha256": source_hash,
        "probe_sha256": probe_hash,
        "scorer_sha256": protocol["frozen_files"]["score.py"]["sha256"],
        "native_seconds": native_seconds,
        "score_seconds": time.perf_counter() - score_start,
        "total_seconds": time.perf_counter() - start,
        "sampled_process_tree_peak_rss": peak,
        "memory_scope": "sampled process-tree RSS; shared pages may be double-counted, not a patch memory benchmark",
        "result": result,
    }
    (output / "execution.json").write_text(json.dumps(record, indent=2) + "\n")
    print(
        json.dumps(
            {
                "output": str(output),
                "exit": returncode,
                "status": result["status"],
                "failures": len(result["failures"]),
                "unresolved": result["unresolved"][:3],
                "seconds": record["total_seconds"],
                "peak_rss": peak,
            }
        ),
        flush=True,
    )
    return record


if __name__ == "__main__":
    p = argparse.ArgumentParser(__doc__)
    p.add_argument("--source", required=True)
    p.add_argument(
        "--phase", required=True, choices=("development", "confirmation", "old-composition")
    )
    p.add_argument("--out", required=True)
    a = p.parse_args()
    run(a.source, a.phase, a.out)

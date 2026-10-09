"""Frozen read-only profiling, bounded CPU use and retained partial results."""

from __future__ import annotations

import argparse
import cProfile
import json
import math
import pstats
import resource
import signal
import sys
import time
from pathlib import Path

from nisayon.engine.confirmation_view import INPUTS, build_view, dependencies
from nisayon.engine.io import canonical_bytes, digest, file_digest, write_json


def cpu_seconds():
    own = resource.getrusage(resource.RUSAGE_SELF)
    children = resource.getrusage(resource.RUSAGE_CHILDREN)
    return own.ru_utime + own.ru_stime + children.ru_utime + children.ru_stime


def peak_bytes():
    value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return value if sys.platform == "darwin" else value * 1024


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inputs", type=Path, default=Path(INPUTS))
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--prior-profile", type=Path)
    args = parser.parse_args()
    spec = json.loads(args.inputs.read_text())
    frozen = spec["profiling"]
    prior_cpu = 0.0
    if args.prior_profile:
        previous = json.loads(args.prior_profile.read_text())
        prior_cpu = previous.get("initial_profile_budget_cpu_s", previous["cumulative_cpu_s"])
    args.out.mkdir(parents=True, exist_ok=False)
    report = {
        "schema": "nisayon.confirmation-profile.v1",
        "input_spec_sha256": file_digest(args.inputs),
        "profiler_source_sha256": file_digest(Path(__file__)),
        "dependencies": dependencies(Path.cwd()),
        "order": frozen,
        "instrumentation": "cProfile on every read, same checks and inputs; peak RSS is cumulative for this fresh process and excludes Git child peaks",
        "reads": [],
        "status": "partial",
        "new_simulator_runs": 0,
        "experimental_model_calls": 0,
        "prior_profile": {
            "path": str(args.prior_profile),
            "sha256": file_digest(args.prior_profile),
            "cpu_s": prior_cpu,
        }
        if args.prior_profile
        else None,
    }
    started_cpu, started_wall = cpu_seconds(), time.perf_counter()

    def limited(signum, frame):
        raise TimeoutError(f"profiling limit reached (signal {signum})")

    signal.signal(signal.SIGXCPU, limited)
    signal.signal(signal.SIGALRM, limited)
    limit = frozen["cpu_limit_s"]
    own = resource.getrusage(resource.RUSAGE_SELF)
    if prior_cpu >= limit:
        raise ValueError("Initial profiling budget already exhausted")
    soft = math.ceil(own.ru_utime + own.ru_stime + limit - prior_cpu)
    resource.setrlimit(resource.RLIMIT_CPU, (soft, soft + 5))
    signal.alarm(650)
    try:
        for index, label in enumerate(frozen["reads"]):
            if prior_cpu + cpu_seconds() - started_cpu >= limit:
                raise TimeoutError("cumulative parent/child CPU cap reached")
            profile = cProfile.Profile()
            cpu_start = cpu_seconds()
            profile.enable()
            try:
                view, timing = build_view(Path.cwd(), spec, selection=frozen["trials_in_order"])
                assert [row["trial"] for row in timing["trials"]] == frozen["trials_in_order"]
            finally:
                profile.disable()
                profile.dump_stats(str(args.out / f"read-{index}.pstats"))
            serial_start, serial_cpu = time.perf_counter(), cpu_seconds()
            data = canonical_bytes(view)
            timing.update(
                serialization_s=time.perf_counter() - serial_start,
                serialization_cpu_s=cpu_seconds() - serial_cpu,
                read_and_serialization_cpu_s=cpu_seconds() - cpu_start,
                output_bytes=len(data),
                view_content_sha256=digest(view),
                cumulative_process_peak_rss_bytes=peak_bytes(),
            )
            stats = pstats.Stats(profile)
            top = sorted(stats.stats.items(), key=lambda item: item[1][3], reverse=True)[:30]
            timing["hotspots"] = [
                {
                    "function": f"{key[0]}:{key[1]}:{key[2]}",
                    "primitive_calls": value[0],
                    "calls": value[1],
                    "profile_self_s": value[2],
                    "profile_cumulative_s": value[3],
                }
                for key, value in top
            ]
            item = {"label": label, **timing}
            report["reads"].append(item)
            write_json(args.out / f"read-{index}.json", item)
            del view, data
        report["status"] = "complete"
        report["identical_views_across_reads"] = (
            len({r["view_content_sha256"] for r in report["reads"]}) == 1
        )
    except TimeoutError as error:
        report["reason"] = str(error)
    finally:
        signal.alarm(0)
        report.update(
            cumulative_cpu_s=cpu_seconds() - started_cpu,
            initial_profile_budget_cpu_s=prior_cpu + cpu_seconds() - started_cpu,
            outer_wall_s=time.perf_counter() - started_wall,
            cumulative_process_peak_rss_bytes=peak_bytes(),
        )
        write_json(args.out / "profile.json", report)
    print(json.dumps({k: v for k, v in report.items() if k not in ("reads", "dependencies")}))
    return 0 if report["status"] == "complete" else 2


if __name__ == "__main__":
    raise SystemExit(main())

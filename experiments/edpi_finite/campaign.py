"""Run the frozen finite campaign; emit all observations before independent audit."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

from finite import assess
from physics import pair

HERE = Path(__file__).resolve().parent


def write(path: Path, value: object) -> None:
    with path.open("x") as stream:
        json.dump(value, stream, sort_keys=True, allow_nan=False, separators=(",", ":"))
        stream.write("\n")


def sandbox_command(output: Path) -> list[str]:
    sandbox = Path("/usr/bin/sandbox-exec")
    if not sandbox.is_file():
        raise RuntimeError(
            "this frozen run requires macOS sandbox-exec; qualify a platform isolation adapter separately"
        )
    denied = [HERE / "case-inputs.json", HERE / "campaign-protocol.json", HERE / "reference.py"]
    rules = " ".join(f"(literal {json.dumps(str(p))})" for p in denied)
    profile = f"(version 1)(allow default)(deny network*)(deny file-write*)(deny file-read* {rules} (subpath {json.dumps(str(output))}))"
    return [
        str(sandbox),
        "-p",
        profile,
        sys.executable,
        "-I",
        "-B",
        str(HERE / "selector_worker.py"),
    ]


def trial(
    case: dict, protocol: dict, method: str, budget: int, seed: int, output: Path, number: int
) -> dict:
    started = time.perf_counter()
    tasks = protocol["tasks"]
    probes = [{key: t[key] for key in ("id", "weight", "cost")} for t in tasks]
    reserve = sum(t["cost"] for t in protocol["confirmation_tasks"])
    spent, resets, selector_seconds = 0, 0, 0.0
    observations, raw, choices = {}, [], []
    command = sandbox_command(output)
    with subprocess.Popen(
        command,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=os.environ | {"PYTHONDONTWRITEBYTECODE": "1"},
    ) as child:
        try:
            while True:
                current = assess(probes, observations)
                if method != "exhaustive" and current["decision"] != "unresolved":
                    break
                request = {
                    "probes": probes,
                    "observations": observations,
                    "method": method,
                    "remaining": budget - reserve - spent,
                    "seed": seed,
                }
                then = time.perf_counter()
                child.stdin.write(json.dumps(request) + "\n")
                child.stdin.flush()
                answer = child.stdout.readline()
                selector_seconds += time.perf_counter() - then
                if not answer:
                    raise RuntimeError("selector failed: " + child.stderr.read())
                choice = json.loads(answer)
                choices.append(
                    {
                        "observations": dict(observations),
                        "remaining": request["remaining"],
                        **choice,
                    }
                )
                if choice["probe"] is None:
                    break
                task = next(t for t in tasks if t["id"] == choice["probe"])
                if task["id"] in observations or task["cost"] > request["remaining"]:
                    raise ValueError("selector exceeded its authority")
                result = pair(
                    case["reference"],
                    case["candidate"],
                    task,
                    reset_id=f"trial-{number}:{task['id']}",
                )
                raw.append({"task": task, "pair": result})
                observations[task["id"]] = result["difference"]
                spent += result["controls"]
                resets += result["resets"]
        finally:
            child.stdin.close()
            try:
                child.wait(timeout=5)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait()
        if child.returncode != 0:
            raise RuntimeError("nonzero selector exit")
    diagnostic = assess(probes, observations)
    confirmation, confirmed = [], None
    if diagnostic["decision"] == "supported":
        for task in protocol["confirmation_tasks"]:
            result = pair(
                case["reference"],
                case["candidate"],
                task,
                reset_id=f"trial-{number}:confirmation:{task['id']}",
            )
            confirmation.append({"task": task, "pair": result})
            spent += result["controls"]
            resets += result["resets"]
        confirmed = assess(
            protocol["confirmation_tasks"],
            {r["task"]["id"]: r["pair"]["difference"] for r in confirmation},
        )
    decision = diagnostic["decision"]
    if decision == "supported" and (confirmed is None or confirmed["decision"] != "supported"):
        decision = (
            "contradicted"
            if confirmed and confirmed["decision"] == "contradicted"
            else "unresolved"
        )
    if spent > budget:
        raise ValueError("control-step budget exceeded")
    record = {
        "schema": "nisayon.edpi.trial.v1",
        "number": number,
        "case": case["id"],
        "method": method,
        "seed": seed,
        "budget": budget,
        "diagnostic": diagnostic,
        "confirmation": confirmed,
        "decision": decision,
        "raw": raw,
        "confirmation_raw": confirmation,
        "choices": choices,
        "controls": spent,
        "resets": resets,
        "probe_pairs": len(raw),
        "confirmation_pairs": len(confirmation),
        "reused_pairs": 0,
        "selector_seconds_including_startup_ipc": selector_seconds,
        "wall_seconds": time.perf_counter() - started,
    }
    write(output / f"trial-{number:04}.json", record)
    return {k: v for k, v in record.items() if k not in ("raw", "confirmation_raw", "choices")}


def main() -> int:
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    output = args.out.resolve()
    output.mkdir(parents=True, exist_ok=False)
    freeze = json.loads((HERE / "campaign-freeze.json").read_text())
    for name, expected in freeze["sha256"].items():
        if hashlib.sha256((HERE / name).read_bytes()).hexdigest() != expected:
            raise ValueError(f"changed frozen source: {name}")
    protocol = json.loads((HERE / "campaign-protocol.json").read_text())
    cases = json.loads((HERE / "case-inputs.json").read_text())
    if (
        hashlib.sha256(json.dumps(cases, sort_keys=True).encode()).hexdigest()
        != protocol["cases_sha256"]
    ):
        raise ValueError("case identity mismatch")
    # Test the actual OS boundary used by every selector, before any experiment.
    probe = subprocess.run(
        sandbox_command(output) + ["--isolation-probe", str(HERE / "case-inputs.json")],
        capture_output=True,
        text=True,
        timeout=15,
    )
    write(
        output / "isolation.json",
        {
            "returncode": probe.returncode,
            "stdout": probe.stdout,
            "stderr": probe.stderr,
            "scope": "tested denied case-file read; no independent human/blind-builder claim",
        },
    )
    if probe.returncode or probe.stdout.strip() != "protected_input_refused":
        raise RuntimeError("evaluation isolation unavailable")
    rows = []
    for budget in protocol["budgets_control_steps"]:
        for case in cases:
            for method in protocol["methods"]:
                seeds = protocol["random_seeds"] if method == "random" else [protocol["other_seed"]]
                for seed in seeds:
                    rows.append(trial(case, protocol, method, budget, seed, output, len(rows)))
            print(
                json.dumps({"budget": budget, "case": case["id"], "finished_trials": len(rows)}),
                flush=True,
            )
    write(
        output / "summary.json",
        {
            "schema": "nisayon.edpi.campaign.v1",
            "rows": rows,
            "source_freeze": hashlib.sha256(
                (HERE / "campaign-freeze.json").read_bytes()
            ).hexdigest(),
            "human_effort": None,
            "energy_joule": None,
            "provider_cost": None,
        },
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

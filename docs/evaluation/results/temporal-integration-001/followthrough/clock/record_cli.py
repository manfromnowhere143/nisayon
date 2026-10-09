"""Run the public evaluator command on the clock-boundary inputs under the recorder.

Inputs: the four committed C-case traces under both remedies (the counterexample) and the
labelled diagnostic copies written by make_inputs.py. One recorded command per input; a
non-zero exit is retained as the outcome, never retried.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[5]
P = "docs/experiments/results/temporal-integration-001/clock-conformance-execution-001/traces"
COMMITTED = {
    f"{case}--{remedy}": f"{P}/{case}--{remedy}.json"
    for case in (
        "C01-single-fresh-mapping",
        "C02-conflicting-fresh-first",
        "C03-conflicting-stale-first",
        "C04-single-stale-mapping",
    )
    for remedy in ("unfenced_queue_control", "conventional")
}


def main() -> int:
    stage = sys.argv[1]
    out = HERE / stage / "cli"
    out.mkdir(parents=True, exist_ok=True)
    inputs = dict(COMMITTED)
    manifest_inputs = json.loads((HERE / "inputs" / "manifest.json").read_text())["inputs"]
    inputs.update({f"diagnostic-{name}": entry["path"] for name, entry in manifest_inputs.items()})
    manifest = {}
    runs_dir = REPO / ".nisayon" / "runs"
    for name, relative in inputs.items():
        before = {p.name for p in runs_dir.iterdir()}
        target = out / f"{name}.json"
        command = [
            "uv",
            "run",
            "--frozen",
            "nisayon",
            "run",
            "--label",
            f"temporal-clock-{stage}-cli-{name}",
            "--",
            "uv",
            "run",
            "--frozen",
            "python",
            "-m",
            "nisayon.evaluation",
            "temporal",
            relative,
            "--json",
            "--out",
            str(target.relative_to(REPO)),
        ]
        completed = subprocess.run(command, cwd=REPO, capture_output=True, text=True)
        new = [p for p in runs_dir.iterdir() if p.name not in before]
        run = json.loads((new[0] / "run.json").read_text()) if len(new) == 1 else None
        stderr_tail = None
        if run is not None:
            log = new[0] / "stderr.log"
            if log.exists() and log.stat().st_size:
                stderr_tail = log.read_text().strip().splitlines()[-1]
        data = (REPO / relative).read_bytes()
        manifest[name] = {
            "trace_path": relative,
            "trace_sha256": hashlib.sha256(data).hexdigest(),
            "output": str(target.relative_to(REPO)) if target.exists() else None,
            "output_sha256": hashlib.sha256(target.read_bytes()).hexdigest()
            if target.exists()
            else None,
            "recorder_run_id": run["id"] if run else None,
            "returncode": run["returncode"] if run else completed.returncode,
            "stderr_last_line": stderr_tail,
            "wall_seconds": run["wall_seconds"] if run else None,
            "git_head": run["git"]["head"] if run else None,
        }
        print(
            name, manifest[name]["recorder_run_id"], manifest[name]["returncode"], stderr_tail or ""
        )
    (out / "manifest.json").write_text(json.dumps(manifest, indent=1, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

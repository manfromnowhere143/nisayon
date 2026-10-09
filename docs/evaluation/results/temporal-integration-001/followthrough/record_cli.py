"""Run the public evaluator command on the representative traces under the recorder.

Each invocation is one recorded command (`nisayon run`), so its identity, wall time and
exit code are retained in `.nisayon/runs/<id>/run.json`; the JSON assessment is written
next to this script under the chosen stage directory. Reading only; no execution.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[5]
HERE = Path(__file__).resolve().parent
P = "docs/experiments/results/temporal-integration-001"
REPRESENTATIVES = {
    "A-T01-conventional": f"{P}/execution-001/traces/T01-healthy--conventional.json",
    "B-X03-unfenced": f"{P}/boundary-execution-001/traces/X03-configuration-aba--unfenced_queue_control.json",
    "B-R11-unfenced": f"{P}/aba-reduction-execution-001/traces/R11-reuse-original-observation--unfenced_queue_control.json",
    "B-R11-conventional": f"{P}/aba-reduction-execution-001/traces/R11-reuse-original-observation--conventional.json",
    "C-X04-unfenced": f"{P}/boundary-execution-001/traces/X04-duplicate-with-lost-first-ack--unfenced_queue_control.json",
    "D-X05-unfenced": f"{P}/boundary-execution-001/traces/X05-clock-crosses-zero--unfenced_queue_control.json",
    "E-X06-unfenced": f"{P}/precision-execution-001/traces/X06-deadline-resolution-boundary--unfenced_queue_control.json",
    "F-T02-unfenced": f"{P}/execution-001/traces/T02-queued-reset--unfenced_queue_control.json",
    "P-prefix-after-dispatch": "docs/evaluation/results/temporal-integration-001/followthrough/inputs/prefix-after_dispatch_before_ack.json",
}


def main() -> int:
    stage = sys.argv[1]
    out = HERE / stage / "cli"
    out.mkdir(parents=True, exist_ok=True)
    manifest = {}
    runs_dir = REPO / ".nisayon" / "runs"
    for name, relative in REPRESENTATIVES.items():
        before = {p.name for p in runs_dir.iterdir()}
        target = out / f"{name}.json"
        command = [
            "uv",
            "run",
            "--frozen",
            "nisayon",
            "run",
            "--label",
            f"temporal-followthrough-{stage}-cli-{name}",
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
        data = (REPO / relative).read_bytes()
        manifest[name] = {
            "trace_path": relative,
            "trace_sha256": hashlib.sha256(data).hexdigest(),
            "trace_bytes": len(data),
            "output": str(target.relative_to(REPO)),
            "output_sha256": hashlib.sha256(target.read_bytes()).hexdigest()
            if target.exists()
            else None,
            "recorder_run_id": run["id"] if run else None,
            "returncode": run["returncode"] if run else completed.returncode,
            "wall_seconds": run["wall_seconds"] if run else None,
            "git_head": run["git"]["head"] if run else None,
        }
        print(
            name,
            manifest[name]["recorder_run_id"],
            manifest[name]["returncode"],
            manifest[name]["wall_seconds"],
        )
        if completed.returncode != 0:
            print(completed.stdout[-2000:], completed.stderr[-2000:])
    (out / "manifest.json").write_text(json.dumps(manifest, indent=1, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

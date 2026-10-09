"""Show that a saved version-1 assessment refuses reuse under the version-2 reference.

Runs the execution lane's read-only verifier (`temporal_experiment read-assessment`) from
this worktree against a retained saved assessment (`aba-reduction-001`, 22 assignments bound to version 1, or
`clock-conformance-001`, 8 assignments bound to version 2) in the
execution lane's artifact store. Nothing is executed or reassessed; the store's listing
and digests are snapshotted before and after to show it was not touched.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[4]
STORES = {
    "aba-reduction-001": Path(
        "/Users/danielwahnich/workspace/nisayon-codex/artifacts/engine-integration-001/"
        "temporal-integration-001/aba-reduction-001"
    ),
    "clock-conformance-001": Path(
        "/Users/danielwahnich/workspace/nisayon-codex/artifacts/engine-integration-001/"
        "temporal-integration-001/clock-conformance-001"
    ),
}
STORE = STORES[sys.argv[1] if len(sys.argv) > 1 else "aba-reduction-001"]
OUTPUT = sys.argv[2] if len(sys.argv) > 2 else "reuse-invalidation.json"


def snapshot(root: Path) -> dict[str, str]:
    return {
        p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(root.rglob("*"))
        if p.is_file()
    }


def main() -> int:
    before = snapshot(STORE)
    started = time.perf_counter()
    completed = subprocess.run(
        [
            "uv",
            "run",
            "--frozen",
            "python",
            "-m",
            "nisayon.engine.temporal_experiment",
            "read-assessment",
            str(STORE / "assessment"),
            str(STORE / "execution"),
        ],
        cwd=REPO,
        capture_output=True,
        text=True,
    )
    wall = time.perf_counter() - started
    after = snapshot(STORE)
    module = REPO / "src/nisayon/evaluation/temporal.py"
    saved = json.loads((STORE / "assessment" / "assessment.json").read_text())
    record = {
        "schema": "nisayon.temporal-followthrough-reuse-invalidation.v1",
        "saved_assessment": str(STORE / "assessment"),
        "saved_reference_module_sha256": saved["assessment_identity"]["implementation_files"][
            "evaluation/temporal.py"
        ],
        "saved_reuse_status": saved.get("reuse_status"),
        "saved_assessment_schema": saved["assessment_identity"]["schema"],
        "current_reference_module_sha256": hashlib.sha256(module.read_bytes()).hexdigest(),
        "returncode": completed.returncode,
        "stdout": completed.stdout[-2000:],
        "stderr_tail": completed.stderr.strip().splitlines()[-1:] if completed.stderr else [],
        "store_files": len(before),
        "store_unchanged": before == after,
        "wall_s": wall,
        "boundary": "read-only verification of retained bytes; no execution, no reassessment",
    }
    (HERE / OUTPUT).write_text(json.dumps(record, indent=1) + "\n")
    print(json.dumps({k: v for k, v in record.items() if k != "stdout"}, indent=1))
    return 0 if completed.returncode != 0 and before == after else 1


if __name__ == "__main__":
    sys.exit(main())

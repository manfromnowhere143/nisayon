"""Measure scalar comparison overhead, separately from decision validity."""

import argparse
import runpy
import statistics
import time
from pathlib import Path

from nisayon.engine.io import decode_json, file_digest, write_json
from nisayon.qualification.compare import difference

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--spec", type=Path, required=True)
parser.add_argument("--out", type=Path, required=True)
args = parser.parse_args()
spec = decode_json(args.spec.read_bytes())
old_path = args.spec.parent / "compare-before.py.txt"
new_path = Path(__file__).resolve().parents[2] / "src/nisayon/qualification/compare.py"
if (
    file_digest(old_path) != spec["old_source_sha256"]
    or file_digest(new_path) != spec["new_source_sha256"]
):
    raise ValueError("Timing sources differ from the frozen specification")
functions = {"old": runpy.run_path(str(old_path))["difference"], "new": difference}
rows = []
for repeat in range(-spec["warmup"], spec["repeats"]):
    for label in ["old", "new"] if repeat % 2 == 0 else ["new", "old"]:
        started = time.perf_counter()
        calls = 0
        for left, right in spec["pairs"]:
            for _ in range(spec["calls_per_pair"]):
                functions[label](left, right, spec["contract"])
                calls += 1
        rows.append(
            {
                "repeat": repeat,
                "warmup": repeat < 0,
                "method": label,
                "calls": calls,
                "seconds": time.perf_counter() - started,
            }
        )
result = {
    "scope": spec["scope"],
    "spec_sha256": file_digest(args.spec),
    "rows": rows,
    "median_seconds_per_call": {
        label: statistics.median(
            row["seconds"] / row["calls"]
            for row in rows
            if row["method"] == label and not row["warmup"]
        )
        for label in functions
    },
}
write_json(args.out, result)
print(result["median_seconds_per_call"])

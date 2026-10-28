"""Ordinary native comparator; no Nisayon import and no policy-weight download."""

import importlib.metadata
import json
import platform
import resource
import sys
import time
from pathlib import Path

started = time.perf_counter()
owner, seed, output = Path(sys.argv[1]).resolve(), int(sys.argv[2]), Path(sys.argv[3])
output.mkdir(parents=True, exist_ok=False)
sys.path.insert(0, str(owner))

import entry  # noqa: E402
from camera_contract import POLICIES  # noqa: E402

value = {"seed": seed, "mode": "configured_budget", "scope": "all"}
actual = entry.candidate(value)
(output / "actual.json").write_text(json.dumps(actual, indent=2) + "\n")
reports = {}
for mode in ("configured_budget", "all_configured_slots"):
    reference = entry.reference(dict(value, mode=mode))
    (output / f"expected-{mode}.json").write_text(json.dumps(reference, indent=2) + "\n")
    expected = {row["id"]: row for row in reference["conditions"]}
    groups = {}
    for policy in POLICIES:
        rows = [row for row in actual["conditions"] if row["id"].startswith(policy + "-")]
        failures = [row["id"] for row in rows if row != expected[row["id"]]]
        groups[policy] = {
            "assigned": len(rows),
            "matched": len(rows) - len(failures),
            "mismatches": failures,
        }
    reports[mode] = groups
usage = resource.getrusage(resource.RUSAGE_SELF)
environment = {
    "python": sys.version,
    "platform": platform.platform(),
    "packages": {d.metadata["Name"]: d.version for d in importlib.metadata.distributions()},
}
result = {
    "seed": seed,
    "rows": len(actual["conditions"]),
    "comparisons": reports,
    "worker_seconds": time.perf_counter() - started,
    "cpu_user_seconds": usage.ru_utime,
    "cpu_system_seconds": usage.ru_stime,
    "peak_rss_native_units": usage.ru_maxrss,
    "peak_rss_unit": "bytes" if sys.platform == "darwin" else "KiB",
    "environment": environment,
}
(output / "report.json").write_text(json.dumps(result, indent=2) + "\n")
print(
    json.dumps(
        {
            "seed": seed,
            "rows": result["rows"],
            "comparisons": {
                mode: {name: [r["matched"], r["assigned"]] for name, r in groups.items()}
                for mode, groups in reports.items()
            },
        }
    ),
    flush=True,
)

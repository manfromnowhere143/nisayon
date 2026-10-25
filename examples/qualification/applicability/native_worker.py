"""Shared native execution for both comparison arms; no Nisayon import."""

import hashlib
import json
import sys
from pathlib import Path


def main():
    project, request_file = map(Path, sys.argv[1:])
    request = json.loads(request_file.read_bytes())
    files = ["native.py", "policy.py", "stats/norm_stats.json"]

    def identities():
        return {name: hashlib.sha256((project / name).read_bytes()).hexdigest() for name in files}

    before = identities()
    sys.path.insert(0, str(project))
    import policy

    calls = 0

    def profile(frame, event, arg):
        nonlocal calls
        if (
            event == "call"
            and frame.f_code.co_name == "load"
            and Path(frame.f_code.co_filename) == project / "native.py"
        ):
            calls += 1

    rows = []
    sys.setprofile(profile)
    try:
        for position in request["positions"]:
            rows.append(
                {
                    "input": position,
                    "reference": policy.reference({"position": position}),
                    "negative_control": policy.negative_control({"position": position}),
                    "candidate": policy.candidate({"position": position}),
                }
            )
    finally:
        sys.setprofile(None)
    after = identities()
    print(
        json.dumps(
            {
                "sources_before": before,
                "sources_after": after,
                "native_load_calls": calls,
                "rows": rows,
                "valid": before == after == request["sources"] and calls == 2 * len(rows),
            },
            allow_nan=False,
        )
    )


if __name__ == "__main__":
    main()

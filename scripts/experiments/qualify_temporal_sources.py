"""Retain the exact parent/fix files for the historical LeRobot reset control.

This fetches a small, pinned source packet. It imports and executes no upstream
module. All payloads, including a failed bounded response, remain accounted for.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

from nisayon.engine.io import write_json

FIX = "6163daaaa4fa193d0e37468a94d90e07ef3c95ce"
BASELINE_BYTES = 3_837_443
LANE_CAP = 3 * 1024**2
FILES = {
    "control": "lerobot/common/robot_devices/control_utils.py",
    "caller": "lerobot/scripts/control_robot.py",
    "act": "lerobot/common/policies/act/modeling_act.py",
    "license": "LICENSE",
}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=False)
    started = time.perf_counter()
    records = []
    transferred = 0

    def fetch(name: str, url: str) -> bytes:
        nonlocal transferred
        remaining = LANE_CAP - transferred
        if remaining <= 0:
            raise ValueError("Execution lane source-payload allowance exhausted")
        request = urllib.request.Request(
            url, headers={"User-Agent": "Nisayon-source-qualification"}
        )
        response_start = time.perf_counter()
        status = None
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                status = response.status
                payload = response.read(remaining + 1)
        except urllib.error.HTTPError as error:
            status = error.code
            payload = error.read(remaining + 1)
        transferred += len(payload)
        path = args.out / name
        path.write_bytes(payload)
        records.append(
            {
                "path": name,
                "url": url,
                "http_status": status,
                "bytes": len(payload),
                "sha256": hashlib.sha256(payload).hexdigest(),
                "git_blob_sha1": hashlib.sha1(
                    b"blob " + str(len(payload)).encode() + b"\0" + payload
                ).hexdigest(),
                "retrieved_at": datetime.now(UTC).isoformat(),
                "request_wall_s": time.perf_counter() - response_start,
            }
        )
        if transferred > LANE_CAP:
            raise ValueError("Bounded response exceeded remaining source-payload allowance")
        if status != 200:
            raise ValueError(f"Source retrieval returned HTTP {status}: {url}")
        return payload

    failure = None
    parent = None
    try:
        metadata = json.loads(
            fetch(
                "fix-commit.json", f"https://api.github.com/repos/huggingface/lerobot/commits/{FIX}"
            )
        )
        if metadata["sha"] != FIX or not metadata["parents"]:
            raise ValueError("Returned commit does not identify the expected fix and parent")
        parent = metadata["parents"][0]["sha"]
        for label, revision in (("parent", parent), ("fixed", FIX)):
            for kind, source_path in FILES.items():
                fetch(
                    f"{label}-{kind}.txt",
                    f"https://raw.githubusercontent.com/huggingface/lerobot/{revision}/{source_path}",
                )
    except Exception as error:
        failure = {"type": type(error).__name__, "message": str(error)}
    record = {
        "schema": "nisayon.temporal-source-retrieval.v1",
        "recorded_at": datetime.now(UTC).isoformat(),
        "fixed_commit": FIX,
        "first_parent_commit": parent,
        "files": records,
        "status": "retrieved_not_yet_qualified" if failure is None else "incomplete",
        "failure": failure,
        "retained_source_payload_bytes": transferred,
        "execution_lane_source_payload_cap_bytes": LANE_CAP,
        "inherited_source_payload_bytes": BASELINE_BYTES,
        "known_subtotal_excluding_later_evaluation_downloads": BASELINE_BYTES + transferred,
        "wall_s": time.perf_counter() - started,
        "boundary": "Retained payload bytes; network headers, web-tool attempts and other overhead unmeasured. No upstream import, policy inference or hardware operation.",
    }
    write_json(args.out / "retrieval.json", record)
    print(json.dumps(record, indent=2))
    if failure:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

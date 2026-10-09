"""Capture only the pinned upstream files named by a population-binding request plan."""

from __future__ import annotations

import argparse
import hashlib
import json
import time
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

from nisayon.engine.io import write_json

REVISION = "1a1837f20538b7d7e21f977a11a5aee14f99803c"
MAX_RESPONSES = 8
MAX_BODY_BYTES = 1_144_503
MAX_ONE_BODY_BYTES = 768 * 1024


def digest(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def write_once(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_bytes() != payload:
            raise ValueError(f"Existing source differs: {path}")
        return
    with path.open("xb") as stream:
        stream.write(payload)


def prior_usage(output: Path) -> tuple[int, int]:
    responses = 0
    body_bytes = 0
    for path in output.glob("receipt-*.json"):
        receipt = json.loads(path.read_text())
        responses += len(receipt["new_responses"])
        body_bytes += sum(int(row["bytes"]) for row in receipt["new_responses"])
    return responses, body_bytes


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args()

    if args.receipt.exists():
        raise FileExistsError(
            f"Receipt already exists; refusing a repeated request: {args.receipt}"
        )
    plan_bytes = args.plan.read_bytes()
    plan = json.loads(plan_bytes)
    requests = plan["requests"]
    previous_responses, previous_bytes = prior_usage(args.output)
    if previous_responses + len(requests) > MAX_RESPONSES:
        raise ValueError("Execution response reservation exhausted")

    started = datetime.now(UTC).isoformat()
    start_wall = time.perf_counter()
    start_cpu = time.process_time()
    rows = []
    new_bytes = 0
    for item in requests:
        url = item["url"]
        if REVISION not in url:
            raise ValueError(f"Source URL is not pinned to {REVISION}: {url}")
        request = urllib.request.Request(
            url,
            headers={"Accept-Encoding": "identity", "User-Agent": "nisayon-source-capture/1"},
        )
        with urllib.request.urlopen(request, timeout=30) as response:
            declared = response.headers.get("Content-Length")
            if declared is not None and int(declared) > MAX_ONE_BODY_BYTES:
                raise ValueError(f"Declared response exceeds {MAX_ONE_BODY_BYTES} bytes: {url}")
            payload = response.read(MAX_ONE_BODY_BYTES + 1)
            if len(payload) > MAX_ONE_BODY_BYTES:
                raise ValueError(f"Response exceeds {MAX_ONE_BODY_BYTES} bytes: {url}")
            headers = {
                key.lower(): response.headers[key]
                for key in ("ETag", "Content-Type", "Content-Length", "X-RateLimit-Remaining")
                if response.headers.get(key) is not None
            }
            status = response.status
            final_url = response.geturl()
        new_bytes += len(payload)
        if previous_bytes + new_bytes > MAX_BODY_BYTES:
            raise ValueError("Execution source-body reservation exhausted")
        target = args.output / item["relative_path"]
        write_once(target, payload)
        rows.append(
            {
                "id": item["id"],
                "decision_changed": item["decision_changed"],
                "path": str(target.resolve()),
                "url": url,
                "final_url": final_url,
                "status": status,
                "bytes": len(payload),
                "sha256": digest(payload),
                "headers": headers,
            }
        )

    receipt = {
        "schema": "nisayon.population-source-capture.v1",
        "started_at": started,
        "ended_at": datetime.now(UTC).isoformat(),
        "revision": REVISION,
        "request_plan": str(args.plan),
        "request_plan_sha256": digest(plan_bytes),
        "new_responses": rows,
        "new_response_count": len(rows),
        "new_body_bytes": new_bytes,
        "cumulative_execution_response_count": previous_responses + len(rows),
        "cumulative_execution_body_bytes": previous_bytes + new_bytes,
        "execution_response_reservation": MAX_RESPONSES,
        "execution_body_reservation_bytes": MAX_BODY_BYTES,
        "wall_seconds_before_receipt_write": time.perf_counter() - start_wall,
        "process_cpu_seconds_before_receipt_write": time.process_time() - start_cpu,
        "network_overhead_bytes": None,
        "rights": "Pinned upstream source is retained as private research evidence; redistribution is not established by this receipt.",
        "limits": {
            "model_weights_retrieved": False,
            "model_or_policy_executed": False,
            "simulator_or_robot_executed": False,
        },
    }
    write_json(args.receipt, receipt)
    print(json.dumps(receipt, sort_keys=True))


if __name__ == "__main__":
    main()

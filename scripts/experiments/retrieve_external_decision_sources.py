"""Retain the bounded, pinned source set for external-decision-001.

The script copies the prepared coordinator sources and retrieves only explicit
small model configuration, processor-statistic and loader-source files. It
refuses model weights, caps every response, and records the exact bytes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import time
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

from nisayon.engine.io import write_json

REPORT = Path("/Users/danielwahnich/.codex/reports/nisayon-joint-value-mission-2026-09-20-zcxntg6t")
MODEL = "https://huggingface.co/lerobot/smolvla_base/resolve"
SOURCE = "https://raw.githubusercontent.com/huggingface/lerobot"
OLD_REVISION = "3326b100334ffc0a0bd1ec27e3afb1cfa2a6000c"
NEW_REVISION = "c83c3163b8ca9b7e67c509fffd9121e66cb96205"
LEROBOT_REVISION = "5aa74557f84c54d4b458f8b9643c5aa2982acfed"
MAX_FILE_BYTES = 512 * 1024
MAX_RETRIEVED_BYTES = 2 * 1024**2

PREPARED = (
    "SOURCE_LEDGER.json",
    "SOURCE_REVIEW.md",
    "READBACK.json",
    "sources/issue-4415.json",
    "sources/issue-4415-comments.json",
    "sources/lerobot-license.json",
    "sources/lerobot-main.json",
    "sources/normalize_processor.py",
    "sources/smolvla-3326b100334f.json",
    "sources/smolvla-c83c3163b8ca.json",
)

RETRIEVALS = (
    ("model/old/README.md", f"{MODEL}/{OLD_REVISION}/README.md", "model_repository"),
    ("model/old/config.json", f"{MODEL}/{OLD_REVISION}/config.json", "model_repository"),
    ("model/new/README.md", f"{MODEL}/{NEW_REVISION}/README.md", "model_repository"),
    ("model/new/config.json", f"{MODEL}/{NEW_REVISION}/config.json", "model_repository"),
    (
        "model/new/policy_preprocessor.json",
        f"{MODEL}/{NEW_REVISION}/policy_preprocessor.json",
        "model_repository",
    ),
    (
        "model/new/policy_postprocessor.json",
        f"{MODEL}/{NEW_REVISION}/policy_postprocessor.json",
        "model_repository",
    ),
    (
        "model/new/policy_preprocessor_step_5_normalizer_processor.safetensors",
        f"{MODEL}/{NEW_REVISION}/policy_preprocessor_step_5_normalizer_processor.safetensors",
        "model_repository",
    ),
    (
        "model/new/policy_postprocessor_step_0_unnormalizer_processor.safetensors",
        f"{MODEL}/{NEW_REVISION}/policy_postprocessor_step_0_unnormalizer_processor.safetensors",
        "model_repository",
    ),
    (
        "lerobot/factory.py",
        f"{SOURCE}/{LEROBOT_REVISION}/src/lerobot/policies/factory.py",
        "apache_2_0_source",
    ),
    (
        "lerobot/pipeline.py",
        f"{SOURCE}/{LEROBOT_REVISION}/src/lerobot/processor/pipeline.py",
        "apache_2_0_source",
    ),
    (
        "lerobot/processor_smolvla.py",
        f"{SOURCE}/{LEROBOT_REVISION}/src/lerobot/policies/smolvla/processor_smolvla.py",
        "apache_2_0_source",
    ),
)


def digest(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def write_once(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_bytes() != payload:
            raise ValueError(f"Existing retained source differs: {path}")
        return
    with path.open("xb") as stream:
        stream.write(payload)


def prepared_sources(output: Path) -> list[dict]:
    ledger = json.loads((REPORT / "SOURCE_LEDGER.json").read_text())
    indexed = {row["path"]: row for row in ledger["sources"]}
    rows = []
    for relative in PREPARED:
        source = REPORT / relative
        payload = source.read_bytes()
        target = output / "coordinator" / relative
        write_once(target, payload)
        expected = indexed.get(relative.removeprefix("sources/"))
        if expected and expected["sha256"] != digest(payload):
            raise ValueError(f"Coordinator digest mismatch: {relative}")
        rows.append(
            {
                "path": str(target),
                "source_path": str(source),
                "bytes": len(payload),
                "sha256": digest(payload),
                "source_payload_counted_by_coordinator": relative.startswith("sources/"),
                "network_retrieval_repeated": False,
            }
        )
    return rows


def retrieve(output: Path) -> tuple[list[dict], int]:
    rows = []
    total = 0
    for relative, url, rights_scope in RETRIEVALS:
        if "model.safetensors" in url or "model-" in url:
            raise ValueError(f"Model weight retrieval forbidden: {url}")
        request = urllib.request.Request(
            url,
            headers={"Accept-Encoding": "identity", "User-Agent": "nisayon-source-capture/1"},
        )
        with urllib.request.urlopen(request, timeout=30) as response:
            declared = response.headers.get("Content-Length")
            if declared is not None and int(declared) > MAX_FILE_BYTES:
                raise ValueError(f"Declared file exceeds {MAX_FILE_BYTES} bytes: {url}")
            payload = response.read(MAX_FILE_BYTES + 1)
            if len(payload) > MAX_FILE_BYTES:
                raise ValueError(f"Response exceeds {MAX_FILE_BYTES} bytes: {url}")
            final_url = response.geturl()
            status = response.status
            headers = {
                key.lower(): response.headers[key]
                for key in ("ETag", "X-Repo-Commit", "Content-Type", "Content-Length")
                if response.headers.get(key) is not None
            }
        total += len(payload)
        if total > MAX_RETRIEVED_BYTES:
            raise ValueError("Execution-lane retained source allocation exhausted")
        target = output / relative
        write_once(target, payload)
        rows.append(
            {
                "path": str(target),
                "url": url,
                "final_url": final_url,
                "status": status,
                "bytes": len(payload),
                "sha256": digest(payload),
                "headers": headers,
                "rights_scope": rights_scope,
            }
        )
    return rows, total


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    start_wall = time.perf_counter()
    start_cpu = time.process_time()
    started_at = datetime.now(UTC).isoformat()
    prepared = prepared_sources(args.output)
    fetched, fetched_bytes = retrieve(args.output)
    result = {
        "schema": "nisayon.external-source-capture.v1",
        "started_at": started_at,
        "ended_at": datetime.now(UTC).isoformat(),
        "prepared": prepared,
        "retrieved": fetched,
        "prepared_copy_bytes": sum(row["bytes"] for row in prepared),
        "new_retrieved_source_bytes": fetched_bytes,
        "execution_source_cap_bytes": MAX_RETRIEVED_BYTES,
        "wall_seconds_before_final_write": time.perf_counter() - start_wall,
        "process_cpu_seconds_before_final_write": time.process_time() - start_cpu,
        "network_overhead_bytes": None,
        "limits": {
            "weights_retrieved": False,
            "model_or_policy_executed": False,
            "robot_physics_executed": False,
        },
        "rights_boundary": (
            "Pinned LeRobot source files carry Apache-2.0 headers. Exact model-repository "
            "README metadata is retained per revision; issue text remains user-contributed "
            "and private local research retention is not redistribution authorization."
        ),
    }
    write_json(args.output / "manifest.json", result)
    shutil.copyfile(args.output / "manifest.json", args.output / "manifest.readback.json")
    print(
        json.dumps(
            {
                "new_retrieved_source_bytes": fetched_bytes,
                "prepared_copy_bytes": result["prepared_copy_bytes"],
                "manifest": str(args.output / "manifest.json"),
            }
        )
    )


if __name__ == "__main__":
    main()

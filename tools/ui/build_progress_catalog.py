"""Bind public contribution discovery to Nisayon's registered repositories.

Only selected public PR metadata enters the instrument. Private discussions,
review notes, logs and local paths are never projected. Live public status reads
are separate from the frozen scientific catalog and cannot change its verdicts.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
READBACK = ROOT / "work/implementations/spatial-instrument-2026-10-22/upstream-readback.json"


def build(engine: Path) -> dict:
    remote = subprocess.check_output(
        ["git", "remote", "get-url", "research"], cwd=engine, text=True
    ).strip()
    if remote != "https://github.com/manfromnowhere143/nisayon.git":
        raise ValueError("Expected canonical Nisayon registry")
    raw = (engine / "work/engagements.json").read_bytes()
    registry = json.loads(raw)
    repos = sorted({row["key"].split("#")[0] for row in registry["threads"]})
    if (
        not repos
        or len(repos) > 60
        or any(not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repo) for repo in repos)
    ):
        raise ValueError("Unsupported public discovery scope")
    account = registry["account"]
    if account != "manfromnowhere143":
        raise ValueError("Unexpected contribution author")
    checked = json.loads(READBACK.read_bytes())
    records = []
    for row in checked["records"]:
        if row["author"] != account:
            continue
        repository = row["url"].removeprefix("https://github.com/").split("/pull/")[0]
        if (
            repository not in repos
            or row["url"] != f"https://github.com/{repository}/pull/{row['number']}"
        ):
            raise ValueError("Public contribution leaves its registered scope")
        status = (
            "merged"
            if row["merged"]
            else ("closed" if row["state"] == "closed" else "draft" if row["draft"] else "open")
        )
        records.append(
            {
                "id": row["url"],
                "url": row["url"],
                "repository": repository,
                "title": row["title"],
                "status": status,
                "date": (row["merged_at"] or row["updated_at"])[:10],
                "updatedAt": row["updated_at"],
                "kind": "contribution",
            }
        )
    if len(records) != len({row["id"] for row in records}):
        raise ValueError("Duplicate contribution")
    return {
        "schema": "nisayon.public-progress.v1",
        "account": account,
        "since": "2026-09-17",
        "repositories": repos,
        "checkedAt": checked["checkedAt"].replace(" UTC", "Z").replace(" ", "T"),
        "source": {
            "registrySha256": hashlib.sha256(raw).hexdigest(),
            "readbackSha256": hashlib.sha256(READBACK.read_bytes()).hexdigest(),
        },
        "records": sorted(records, key=lambda r: r["updatedAt"], reverse=True),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--engine", type=Path, default=ROOT.parent / "nisayon")
    args = parser.parse_args()
    value = build(args.engine.resolve())
    (ROOT / "apps/instrument/src/research/progressSeed.json").write_text(
        json.dumps(value, indent=2, ensure_ascii=False) + "\n"
    )
    print(
        f"Public progress: {len(value['records'])} contributions in {len(value['repositories'])} registered repositories"
    )

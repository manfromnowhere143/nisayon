"""Curate reviewed, exact projection bytes from three independent source freezes.

No raw archive, payload, host path or diagnostic is exported. Labels describe
exposed controls; they are not engine-bound experimental context.
"""

import hashlib
import json
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
ROOT = APP.parents[1]
TARGET = APP / "public/examples/check-records"
TARGET.mkdir(parents=True, exist_ok=True)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def packet(path, index_path, index_sha, manifest_sha, source):
    folder = ROOT / path
    raw = (folder / index_path).read_bytes()
    manifest = (folder / "MANIFEST.json").read_bytes()
    assert digest(raw) == index_sha, path
    assert digest(manifest) == manifest_sha, path
    files = json.loads(manifest)["files"]
    if isinstance(files, list):
        files = {row["path"]: row for row in files}
    return {
        "folder": folder,
        "index": json.loads(raw),
        "files": files,
        "source": source,
        "index_sha256": index_sha,
        "manifest_sha256": manifest_sha,
    }


measurement = packet(
    "work/research/ui-engine-integration-2026-11-16",
    "fixtures-index.json",
    "ed02f04c260426fb132224588e38cf4d739c00778923cc27b5a4f69e4db67f2f",
    "938ded3e54b3a183f8f053dadd91266c8fbaeb5fa54b9a567bb35738ff524635",
    "6e7db24bfdfcbb4bf1b6ffc7f88c5e1a49df1816",
)
explanation = packet(
    "work/experiments/check-explanation-2026-11-16",
    "examples/index.json",
    "81a714e603dfc245149af4f682fbf0cb261fe0a1c6f65e7a6f7208495cf4168c",
    "ad902514057e9da189c7ebbae759d9a7f16068cd5a807ab67255efc1cabffebc",
    "12afda5f7e388744a0f6d64ac585663ea7f48112",
)
underflow = packet(
    "work/experiments/json-underflow-2026-11-16",
    "examples/index.json",
    "0e693999052c1748ec19d764649f9e17143252e6538767d0456c6069c6d3bf57",
    "1c4d392f193f24b78c26d95eb12631bb7b97d4074c1a280e13bd40359f19b061",
    "298a0a1b271afbaa8edd960800d5193583ae11be",
)
rows = []


def add(source, key, title, description, group, projections):
    row = {
        "id": key,
        "title": title,
        "description": description,
        "group": group,
        "sourceCommit": source["source"],
        "summary": None,
        "measurement": None,
        "explanation": None,
    }
    for role, (path, expected) in projections.items():
        raw = (source["folder"] / path).read_bytes()
        assert digest(raw) == expected == source["files"][path]["sha256"], path
        # Reviewed samples only. This check is an additional tripwire, not a
        # general redactor or proof that arbitrary records are safe to publish.
        assert not any(mark in raw for mark in [b"/Users/", b"/home/", b"Bearer ", b"PRIVATE KEY"])
        filename = f"{key}.{role}.json"
        target = TARGET / filename
        if target.exists():
            assert target.read_bytes() == raw, f"Refuse rebinding existing sample: {filename}"
        else:
            target.write_bytes(raw)
        row[role] = {"file": filename, "sha256": expected}
    rows.append(row)


fixtures = {row["id"]: row for row in explanation["index"]["rows"]}
for fixture_id, key, title, description in [
    (
        "scoring_change",
        "scoring-change",
        "A scoring change reuses an observation",
        "Authored software continuation. The scoring input changed; observation evidence was reused while analysis and confirmation ran. No robot trial.",
    ),
    (
        "unattempted_reuse",
        "unattempted-reuse",
        "Reuse planned, never attempted",
        "Authored software control. An unknown population input blocked execution. Planned reusable checks remain unattempted.",
    ),
    (
        "missing_history",
        "missing-history",
        "A previous receipt needs a new check",
        "Authored software control with a removed historical observation artifact. The public explanation deliberately withholds diagnostic text; receipt presence alone does not establish reusable evidence.",
    ),
]:
    fixture = fixtures[fixture_id]
    add(
        explanation,
        key,
        title,
        description,
        "Dependency decisions",
        {
            role: ("examples/" + fixture[role], fixture[role + "_sha256"])
            for role in ["summary", "explanation"]
        },
    )

for fixture in underflow["index"]["examples"]:
    nonzero = fixture["id"] == "nonzero_refused"
    add(
        underflow,
        "nonzero-refused" if nonzero else "literal-zero",
        "A tiny nonzero value is refused" if nonzero else "Literal zero retains its meaning",
        "Authored numeric-transport control using 1e-400. Its observation read failed before assessment; this example context is not a diagnosis of arbitrary failed imports."
        if nonzero
        else "Authored numeric-transport control using 0e-400. The declared equality is supported and agrees with the saved assessment. This is a software control, not a task or hardware result.",
        "Numeric transport controls",
        {
            role: ("examples/" + record["path"], record["sha256"])
            for role, record in fixture["projection_files"].items()
        },
    )

fixtures = {row["id"]: row for row in measurement["index"]["rows"]}
for fixture_id, key, title, description in [
    (
        "newton_reconstruct",
        "recorded-relation",
        "A recorded relation holds",
        "Analysis of retained Newton records. Lower tracked allocation and equal sampled payloads; the solver remains unconverged. No new simulator run.",
    ),
    (
        "newton_rescore_equal_memory",
        "rejected-relation",
        "A recorded relation fails",
        "An exposed scoring control over historical Newton data. A matching rejection is a legitimate result.",
    ),
    (
        "software_claim_mismatch",
        "claim-disagreement",
        "A saved claim disagrees",
        "Authored adversarial software control. The handler deliberately saved a supported verdict over a rejected relation.",
    ),
    (
        "newton_substitute_factor_metric",
        "unresolved-semantics",
        "Measurement meaning is unresolved",
        "An exposed metric-substitution control. The recorded measurement does not meet the declared contract's semantics.",
    ),
    (
        "newton_incomplete",
        "incomplete-execution",
        "An execution is incomplete",
        "An exposed incomplete-data control over retained Newton records. No complete measurement assessment is released.",
    ),
    (
        "software_acquisition_failed",
        "acquisition-failed",
        "Input acquisition failed",
        "Authored software execution control. Input acquisition failed before any check was attempted.",
    ),
]:
    fixture = fixtures[fixture_id]
    projections = {"summary": (fixture["summary"], fixture["summary_sha256"])}
    if fixture.get("measurement_review"):
        projections["measurement"] = (
            fixture["measurement_review"],
            fixture["measurement_review_sha256"],
        )
    add(measurement, key, title, description, "Measurement records", projections)

(APP / "src/qualification/projectionExamples.ts").write_text(
    "// Curated author labels, distinct from engine-bound experimental context.\nexport const PROJECTION_EXAMPLES = "
    + json.dumps(rows, indent=2)
    + " as const;\n"
)
(TARGET / "sources.json").write_text(
    json.dumps(
        {
            "status": "Recorded authored controls and historical analyses; no new robot or simulator execution",
            "sources": [
                {k: value[k] for k in ["source", "index_sha256", "manifest_sha256"]}
                for value in [measurement, explanation, underflow]
            ],
            "examples": rows,
        },
        indent=2,
    )
    + "\n"
)
print(
    f"Curated {len(rows)} examples with independent source freezes; original sample bytes unchanged."
)

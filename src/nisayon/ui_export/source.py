"""Admit retained bytes before deriving a display. No acceptance logic lives here."""

import gzip
import io
import json
from pathlib import Path

from .bytes import (
    MAX_BUNDLE_BYTES,
    ExportError,
    canonical,
    check_bytes,
    decompress,
    inside,
    parse,
    read,
    sha256,
)


def producer_digest(value: object) -> str:
    return sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    )


class Sources:
    def __init__(self):
        self.entries = {}

    def add(self, identifier: str, data: bytes, encoding: str, label: str, value=None) -> str:
        entry = {
            "id": identifier,
            "sha256": sha256(data),
            "byte_length": len(data),
            "encoding": encoding,
            "label": label,
            "canonical_json_sha256": None,
        }
        if value is not None:
            entry["canonical_json_sha256"] = sha256(canonical(value))
        if identifier in self.entries:
            if any(entry[k] != self.entries[identifier][k] for k in entry if k != "label"):
                raise ExportError("duplicate source identity with different bytes")
            return identifier
        self.entries[identifier] = entry
        return identifier


def admit_bundle(compact_path: Path, raw_root: Path | None, sources: Sources, label: str):
    packed = read(compact_path, MAX_BUNDLE_BYTES)
    decoded = decompress(packed)
    bundle = parse(decoded, MAX_BUNDLE_BYTES)
    if (
        bundle.get("schema") != "nisayon.first_case.v1"
        or bundle.get("record_contract") != "nisayon.execution.v2"
    ):
        raise ExportError("unsupported retained bundle schema")
    if raw_root is not None:
        raw_bundle = read(raw_root / "bundle.json", MAX_BUNDLE_BYTES)
        if raw_bundle != decoded:
            raise ExportError("compact and raw bundle bytes disagree")
    ids = [run["id"] for run in bundle["runs"]]
    if len(ids) != len(set(ids)):
        raise ExportError("duplicate run identity")
    for run in bundle["runs"]:
        if run["case_id"] != bundle["case"]["id"]:
            raise ExportError("run bound to a different case")
        steps = [row["step"] for row in run["trace"]]
        if len(steps) != len(set(steps)):
            raise ExportError("duplicate source step")
    sid = "bundle:" + sha256(decoded)
    sources.add("compressed:" + sha256(packed), packed, "gzip-json", label + "/bundle.json.gz")
    sources.add(sid, decoded, "json", label + "/bundle.json (decoded exact bytes)", bundle)
    return bundle, sid, sha256(decoded)


def admit_raw(raw_root: Path, run: dict, sources: Sources, label: str):
    expected = {item["path"]: item["sha256"] for item in run["artifacts"]}
    if len(expected) != len(run["artifacts"]):
        raise ExportError("duplicate artifact identity")
    name = run["id"] + ".jsonl.gz"
    path = inside(raw_root, name)
    packed = read(path, MAX_BUNDLE_BYTES)
    check_bytes(packed, expected[name])
    sid = sources.add("raw:" + sha256(packed), packed, "gzip-jsonl", label + "/" + name)

    # Iterate lines: never retain the recurrent tensors for a whole run.
    def rows():
        with gzip.GzipFile(fileobj=io.BytesIO(packed)) as stream:
            header = parse(stream.readline(2 * 1024 * 1024), 2 * 1024 * 1024)
            if producer_digest(header.get("reset")) != run["initial_state_sha256"]:
                raise ExportError("initial state digest mismatch")
            if header.get("policy_reset_event") != run.get("policy_reset"):
                raise ExportError("episode reset binding mismatch")
            total = 0
            for index, row in enumerate(run["trace"]):
                line = stream.readline(2 * 1024 * 1024)
                total += len(line)
                if total > MAX_BUNDLE_BYTES:
                    raise ExportError("raw stream decoded byte limit exceeded")
                raw = parse(line, 2 * 1024 * 1024)
                admit_row(raw, row)
                yield index, row, raw
            if stream.read(1):
                raise ExportError("raw stream has unbound extra rows")

    return sid, rows()


def admit_row(raw: dict, row: dict) -> None:
    if raw.get("step") != row.get("step"):
        raise ExportError("raw and compact step mismatch")
    pairs = [
        ("state_before", "state_before_sha256"),
        ("state_after", "state_after_sha256"),
        ("observation", "observation_sha256"),
        ("next_observation", "next_observation_sha256"),
        ("captured_observation", "captured_observation_sha256"),
        ("policy_state_before", "policy_state_sha256"),
        ("policy_state_after", "policy_state_after_sha256"),
    ]
    for field, digest_field in pairs:
        if digest_field not in row or field not in raw:
            raise ExportError(f"missing source field: {field}")
        if row[digest_field] is None:
            if raw[field] is not None:
                raise ExportError(f"unavailable source has a value: {field}")
        elif producer_digest(raw[field]) != row[digest_field]:
            raise ExportError(f"source value digest mismatch: {field}")
    for field in [
        "intended_action",
        "executed_action",
        "observation_capture",
        "next_observation_capture",
        "captured_observation_capture",
    ]:
        if raw.get(field) != row.get(field):
            raise ExportError(f"raw/compact value mismatch: {field}")
    for phase, time_field in [("before", "action_sim_time_s"), ("after", "next_sim_time_s")]:
        state = raw.get("state_" + phase)
        if not isinstance(state, dict) or state.get("sim_time_s") != row[time_field]:
            raise ExportError("state phase/time mismatch")


def project_private_paths(value, redactions: list[str]):
    """Replace path text only; retain literal reason codes, quantities and status."""
    if isinstance(value, str):
        import re

        projected, count = re.subn(r"/Users/[^\s\"'\)\],;]+", "[local source path]", value)
        if count and "local filesystem paths" not in redactions:
            redactions.append("local filesystem paths")
        return projected
    if isinstance(value, dict):
        return {key: project_private_paths(child, redactions) for key, child in value.items()}
    if isinstance(value, list):
        return [project_private_paths(child, redactions) for child in value]
    return value


def admit_decision(path: Path, bundle: dict, bundle_sha: str, stage: str, sources: Sources):
    data = read(path)
    original = parse(data)
    semantic = sha256(canonical(bundle))
    if original.get("bundle_sha256") != "sha256:" + semantic:
        raise ExportError("decision canonical bundle binding mismatch")
    if original.get("case_id") != bundle["case"]["id"]:
        raise ExportError("decision case binding mismatch")
    if set(original.get("runs", {})) != {r["id"] for r in bundle["runs"]}:
        raise ExportError("decision run identities disagree")
    sid = sources.add("decision:" + sha256(data), data, "json", stage + "/" + path.name, original)
    redactions = []
    result = {
        "schema": "nisayon.ui-decision.v1",
        "source": {"source_id": sid, "pointer": ""},
        "bundle_sha256": bundle_sha,
        "source_canonical_bundle_sha256": semantic,
        "stage": stage,
        **{
            key: project_private_paths(original[key], redactions)
            for key in ["decision", "scope", "reasons", "premises", "evaluator", "runs"]
        },
        "projection_redactions": redactions,
    }
    return result, original

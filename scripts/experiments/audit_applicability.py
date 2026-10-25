"""Read-only audit of the two retained, exposed applicability comparison packets."""

from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from pathlib import Path


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def audit(directory):
    declaration = json.loads((directory / "audit.json").read_bytes())
    output = {}
    seen_vectors = set()
    procedures = set()
    for name, expected in declaration["runs"].items():
        path = directory / f"{name}.zip"
        require(
            hashlib.sha256(path.read_bytes()).hexdigest() == expected["archive_sha256"],
            "Archive bytes changed",
        )
        with zipfile.ZipFile(path) as archive:
            members = archive.infolist()
            require(
                len({item.filename for item in members}) == len(members), "Duplicate archive member"
            )
            require(
                sum(item.file_size for item in members) <= 64 * 1024 * 1024, "Oversized archive"
            )
            require(all(item.file_size <= 16 * 1024 * 1024 for item in members), "Oversized member")
            manifest = json.loads(archive.read("PACKET-MANIFEST.json"))["files"]
            require(
                set(archive.namelist())
                == set(manifest) | {"PACKET-MANIFEST.json", "OPENPI_LICENSE"},
                "Archive membership changed",
            )
            for filename, sha in manifest.items():
                require(
                    hashlib.sha256(archive.read(filename)).hexdigest() == sha,
                    f"Changed record: {filename}",
                )

            def read(filename):
                return json.loads(archive.read(filename))

            freeze = read("freeze.json")
            procedures.add(json.dumps(freeze["procedure"], sort_keys=True))
            require(freeze["model_sha256"] == expected["model_sha256"], "Model identity changed")
            vectors = {tuple(row) for item in freeze["cases"] for row in item["confirmation"]}
            require(
                len(vectors) == 192 and not vectors & seen_vectors, "Confirmation vectors reused"
            )
            seen_vectors |= vectors
            counts = {}
            for arm in ("native", "nisayon"):
                count = 0
                for entry in freeze["cases"]:
                    case, mean, tolerance, population, decision = entry["case"]
                    base = f"{arm}/{case}/"
                    require(
                        read(base + "result.json")["decision"] == decision, "Wrong scoped decision"
                    )
                    for prefix in ("diagnostic", "fresh"):
                        filename = base + prefix + "-stdout.json"
                        if filename not in manifest:
                            continue
                        request_name = base + prefix + "-request.json"
                        intent = read(base + prefix + "-intent.json")
                        require(
                            hashlib.sha256(archive.read(request_name)).hexdigest()
                            == intent["request_sha256"],
                            "Request changed",
                        )
                        request, observed = read(request_name), read(filename)
                        require(
                            observed["sources_before"]
                            == observed["sources_after"]
                            == request["sources"],
                            "Native source binding failed",
                        )
                        require(
                            observed["native_load_calls"] == 2 * len(request["positions"]),
                            "Native calls missing",
                        )
                        require(
                            len(observed["rows"]) == len(request["positions"]),
                            "Observation count changed",
                        )
                        for row, position in zip(
                            observed["rows"], request["positions"], strict=True
                        ):
                            reference = [(x - 10) / 10 for x in position]
                            candidate = [
                                (x - m) / 10 for x, m in zip(position, [mean, 10, 10], strict=True)
                            ]
                            negative = candidate.copy()
                            negative[0] *= -1
                            require(row["input"] == position, "Native input changed")
                            require(row["reference"]["action"] == reference, "Reference differs")
                            require(row["candidate"]["action"] == candidate, "Candidate differs")
                            require(
                                row["negative_control"]["action"] == negative, "Control differs"
                            )
                        count += len(observed["rows"]) * 3
                require(count == 528, "Missing raw role outputs")
                counts[arm] = count
            old = read("nisayon/initial/state.json")["checks"]
            new = read("nisayon/strict_score/state.json")["checks"]
            require(old["observe"] == new["observe"], "Scoring change did not reuse observations")
            require(
                old["score"]["artifact"]["sha256"] != new["score"]["artifact"]["sha256"],
                "Scoring change did not rescore",
            )
            output[name] = {"verified_files": len(manifest), "raw_role_outputs": counts}
    require(len(procedures) == 1, "Procedure changed between runs")
    return {
        "status": "verified_exposed_packets",
        "runs": output,
        "limit": "Read-only integrity and finite numeric checks; no authenticity, independent selection or complete-cost claim.",
    }


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    print(json.dumps(audit(args.directory), indent=2))


if __name__ == "__main__":
    main()

"""Audit published aggregates and hypothetical loss, without running a robot."""

from __future__ import annotations

import argparse
import copy
import gzip
import hashlib
import itertools
import json
import re
from fractions import Fraction as F
from html.parser import HTMLParser
from pathlib import Path


class Tables(HTMLParser):
    """Extract text cells without evaluating scripts or fetching linked content."""

    def __init__(self) -> None:
        super().__init__()
        self.tables: list[list[list[str]]] = []
        self.depth = 0
        self.table: list[list[str]] = []
        self.row: list[str] = []
        self.cell: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list) -> None:
        if tag == "table":
            self.depth += 1
            if self.depth == 1:
                self.table = []
        if self.depth == 1 and tag == "tr":
            self.row = []
        if self.depth == 1 and tag in ("td", "th"):
            self.cell = []

    def handle_data(self, data: str) -> None:
        if self.cell is not None:
            self.cell.append(data)

    def handle_endtag(self, tag: str) -> None:
        if self.depth == 1 and tag in ("td", "th") and self.cell is not None:
            self.row.append(" ".join("".join(self.cell).split()))
            self.cell = None
        if self.depth == 1 and tag == "tr":
            self.table.append(self.row)
        if tag == "table":
            if self.depth == 1:
                self.tables.append(self.table)
            self.depth -= 1


def verify_source(data: dict, source: Path) -> dict:
    raw = source.read_bytes()
    if source.suffix == ".gz":
        raw = gzip.decompress(raw)
    digest = hashlib.sha256(raw).hexdigest()
    parser = Tables()
    parser.feed(raw.decode())
    rows = [row for table in parser.tables for row in table]
    selected = [r for r in rows if r and r[0] == "Cross-sim replay"]
    if len(selected) != 2:
        raise ValueError("Expected exactly two cross-simulator rows")
    by_source = {r[1]: r for r in selected}
    columns = {"completion": 4, "reported": 5, "observable": 6, "settled": 7}
    for cell in data["cells"]:
        index = columns[cell["property"]]
        for side, source_name in (("base", "SimuHome"), ("candidate", "S5-HES")):
            pair = re.fullmatch(r"(\d+)/(\d+)†?", by_source[source_name][index])
            expected = (cell[f"{side}_failures"], cell[f"{side}_eligible"])
            if pair is None or tuple(map(int, pair.groups())) != expected:
                raise ValueError(f"Source count mismatch: {cell['property']}, {side}")
    labels = {
        "profile": "SimVerity Brier",
        "strong_lookup": "Strong-lookup Brier",
        "path_only": "Path-only Brier",
    }
    for key, label in labels.items():
        matching = [r for r in rows if r and r[0] == label]
        if len(matching) != 1:
            raise ValueError(f"Expected one source Brier row: {label}")
        for index, cohort in enumerate(("cohort_1", "cohort_2"), start=1):
            if F(matching[0][index]) != F(data["brier"][cohort][key]):
                raise ValueError(f"Source Brier mismatch: {cohort}, {key}")
    return {
        "scope": "transcription only; no verification of physical outcomes",
        "sha256": digest,
        "matches_retained_html": digest == data["source"]["html_sha256"],
        "property_counts_checked": 8,
        "brier_values_checked": 6,
    }


def validate(data: dict) -> None:
    properties = [cell["property"] for cell in data["cells"]]
    if len(properties) != 4 or set(properties) != {
        "completion",
        "reported",
        "observable",
        "settled",
    }:
        raise ValueError("Expected exactly the four reported properties")
    premises = data["source_reported_premises"]
    if (
        premises.get("candidate_eligibility_is_subset") is not True
        or premises.get("same_frozen_physical_anchors") is not True
        or type(premises.get("overlapping_verdict_disagreements")) is not int
        or premises["overlapping_verdict_disagreements"] != 0
    ):
        raise ValueError("Subset accounting needs declared correspondence premises")
    assigned = premises["assigned_anchors"]
    if type(assigned) is not int or assigned <= 0:
        raise ValueError("Assigned count must be a positive integer")
    for cell in data["cells"]:
        bn, bf, cn, cf = (
            cell[k]
            for k in (
                "base_eligible",
                "base_failures",
                "candidate_eligible",
                "candidate_failures",
            )
        )
        if any(type(x) is not int for x in (bn, bf, cn, cf)):
            raise ValueError("Counts must be integers, not booleans")
        if not (bn == assigned and 0 < cn <= bn and 0 <= cf <= cn and cf <= bf <= bn):
            raise ValueError("Impossible eligible or failure counts")
        if bf - cf > bn - cn:
            raise ValueError("Excluded failures exceed excluded cases")


def gain(cell: dict, loss: F, query: F, escalation: F, preparation: F) -> F:
    if any(c < 0 for c in (loss, query, escalation, preparation)):
        raise ValueError("Hypothetical costs must be nonnegative")
    excluded = cell["base_eligible"] - cell["candidate_eligible"]
    avoided = cell["base_failures"] - cell["candidate_failures"]
    return avoided * loss - cell["base_eligible"] * query - excluded * escalation - preparation


def controls(data: dict) -> dict:
    rejected = []
    mutations = [
        ("unknown_subset", "premise", "candidate_eligibility_is_subset", None),
        ("unknown_correspondence", "premise", "same_frozen_physical_anchors", None),
        ("unknown_agreement", "premise", "overlapping_verdict_disagreements", None),
        ("more_candidate_cases", "cell", "candidate_eligible", 161),
        ("more_candidate_failures", "cell", "candidate_failures", 31),
        ("impossible_excluded_failures", "cell", "candidate_eligible", 159),
        ("boolean_count", "cell", "base_failures", True),
    ]
    for name, kind, key, value in mutations:
        altered = copy.deepcopy(data)
        target = (
            altered["source_reported_premises"]
            if kind == "premise"
            else next(c for c in altered["cells"] if c["property"] == "observable")
        )
        target[key] = value
        try:
            validate(altered)
        except ValueError:
            rejected.append(name)
        else:
            raise AssertionError(f"Invalid input accepted: {name}")
    try:
        gain(
            next(c for c in data["cells"] if c["property"] == "observable"), F(1), F(-1), F(0), F(0)
        )
    except ValueError:
        rejected.append("negative_cost")
    else:
        raise AssertionError("Negative cost accepted")

    checks = 0
    for cell in data["cells"]:
        # Construct compatible rows to check arithmetic, not to invent original trials.
        n = cell["base_eligible"]
        kept = cell["candidate_eligible"]
        kept_bad = cell["candidate_failures"]
        excluded_bad = cell["base_failures"] - kept_bad
        rows = [(True, i < kept_bad) for i in range(kept)]
        rows += [(False, i < excluded_bad) for i in range(n - kept)]
        for query, escalation, preparation in itertools.product(
            (F(0), F(1, 100), F(1, 10)),
            (F(0), F(1, 10), F(9, 40), F(1, 2), F(1)),
            (F(0), F(1), F(10)),
        ):
            baseline_loss = sum(F(bad) for _, bad in rows)
            candidate_loss = preparation + sum(
                query + (F(bad) if eligible else escalation) for eligible, bad in rows
            )
            if baseline_loss - candidate_loss != gain(cell, F(1), query, escalation, preparation):
                raise AssertionError("Constructed row losses disagree with aggregate arithmetic")
            checks += 1
    return {"invalid_inputs_rejected": rejected, "constructed_pointwise_loss_checks": checks}


def audit(data: dict) -> dict:
    validate(data)
    cells = []
    for cell in data["cells"]:
        bn, cn = cell["base_eligible"], cell["candidate_eligible"]
        bf, cf = cell["base_failures"], cell["candidate_failures"]
        cells.append(
            {
                "property": cell["property"],
                "base_conditional_failure_rate": str(F(bf, bn)),
                "candidate_conditional_failure_rate": str(F(cf, cn)),
                "conditional_rate_reduction": str(F(bf, bn) - F(cf, cn)),
                "assigned_anchors": bn,
                "candidate_coverage": str(F(cn, bn)),
                "excluded_cases": bn - cn,
                "failures_in_excluded_cases": bf - cf,
                "hypothetical_loss_gain": f"{bf - cf} L - {bn} Q - {bn - cn} E - A",
            }
        )
    comparisons = {
        cohort: {
            "profile_minus_strong_lookup": str(F(values["profile"]) - F(values["strong_lookup"])),
            "profile_minus_path_only": str(F(values["profile"]) - F(values["path_only"])),
            "interpretation": "Descriptive reported Brier difference; no pooling or new significance test",
        }
        for cohort, values in data["brier"].items()
    }
    observable = next(c for c in data["cells"] if c["property"] == "observable")
    cheap = gain(observable, F(1), F(0), F(1, 10), F(0))
    costly = gain(observable, F(1), F(1, 10), F(1, 10), F(0))
    if cheap != 5 or costly != -11:
        raise AssertionError("The declared observable cost reversal did not reproduce")
    return {
        "status": "published_aggregate_arithmetic_checked",
        "source": data["source"],
        "cells": cells,
        "brier_comparisons": comparisons,
        "hypothetical_cost_reversal": {
            "positive_gain": str(cheap),
            "negative_gain": str(costly),
            "parameters": "L=1, E=1/10, A=0; Q=0 then Q=1/10",
            "premises": "Commensurate hypothetical units and perfect escalation; no owner costs measured",
        },
        "controls": controls(data),
        "owner_value": "unresolved",
        "physical_confirmation": "not_run",
        "reuse": "not_tested",
        "limits": [
            "Source-reported correspondence and aggregates, not original episode records.",
            "Agreement does not establish independent error detection.",
            "Arithmetic controls are exposed constructed cases, not new physical samples.",
            "Loss tradeoffs do not establish matched task quality or complete engineering savings.",
            "No production acceptance or confirmation sample requirement changes.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--observations", type=Path, default=Path(__file__).with_name("source-observations.json")
    )
    parser.add_argument("--source-html", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    data = json.loads(args.observations.read_text())
    result = audit(data)
    result["source_check"] = (
        verify_source(data, args.source_html) if args.source_html else {"status": "not_requested"}
    )
    with args.out.open("x") as stream:
        json.dump(result, stream, indent=2)
        stream.write("\n")
    print(json.dumps({"status": result["status"], "controls": result["controls"]}, indent=2))


if __name__ == "__main__":
    main()

"""Identity and coverage checks for retained temporal assessments, not an oracle.

Membership comes from committed frozen plans. Results cannot choose their own
denominator, conflate repeated case names, or silently omit the ordinary arm.
"""

from __future__ import annotations

from collections import Counter

from .io import digest
from .temporal_experiment import validate_suite

PAIR_ROLES = {
    "same_conventional_remedy_through_intervention_interface": "competent_ordinary_remedy",
    "same_combined_remedy_through_intervention_interface": "competent_ordinary_combined_deadline_remedy",
}


class CoverageError(ValueError):
    def __init__(self, code: str, **details):
        self.details = {"code": code, **details}
        super().__init__(str(self.details))


def exact_index(rows: list, expected: list, *, key, scope: str) -> dict:
    """Reject lost or repeated identities before constructing a lookup."""
    if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
        raise CoverageError("malformed_rows", scope=scope)
    try:
        ids = [key(row) for row in rows]
        counts = Counter(ids)
        expected_counts = Counter(expected)
    except (KeyError, TypeError) as error:
        raise CoverageError("malformed_identity", scope=scope) from error
    duplicate = [identity for identity, count in counts.items() if count != 1]
    expected_duplicate = [identity for identity, count in expected_counts.items() if count != 1]
    missing = [identity for identity in expected if identity not in counts]
    extra = [identity for identity in ids if identity not in expected_counts]
    if duplicate or expected_duplicate or missing or extra:
        raise CoverageError(
            "membership_mismatch",
            scope=scope,
            duplicates=duplicate,
            expected_duplicates=expected_duplicate,
            missing=missing,
            extra=extra,
        )
    return dict(zip(ids, rows, strict=True))


def declared_pairs(suite: dict) -> list[dict]:
    validate_suite(suite)
    pairs = []
    for selected in suite["remedies"]:
        baseline_role = PAIR_ROLES.get(selected.get("role"))
        if baseline_role is None:
            continue
        candidates = [r for r in suite["remedies"] if r.get("role") == baseline_role]
        if len(candidates) != 1:
            raise CoverageError("ambiguous_comparator_role", selected=selected["id"])
        conventional = candidates[0]

        def policy(remedy):
            return {k: v for k, v in remedy.items() if k not in {"id", "role"}}

        if policy(selected) != policy(conventional):
            raise CoverageError("unequal_declared_policies", selected=selected["id"])
        for case in suite["cases"]:
            pairs.append(
                {
                    "case_id": case["id"],
                    "selected": case["id"] + "--" + selected["id"],
                    "conventional": case["id"] + "--" + conventional["id"],
                    "selected_role": selected["role"],
                    "conventional_role": baseline_role,
                    "policy_sha256": digest(policy(selected)),
                    "case_sha256": digest(case),
                }
            )
    return pairs


def owner_index(coverage: dict, manifest: dict, full: dict, expected_source: dict) -> dict:
    """Bind complete owner results to source and actual population/trace identity.

    The owner's manifest may label populations differently; the frozen coverage
    manifest names that mapping explicitly. Missing coverage raises with exact
    assignment identities, and is never reported as agreement.
    """
    if manifest.get("schema") != "nisayon.temporal-followthrough-reassessment.v1":
        raise CoverageError("unsupported_owner_manifest")
    source = manifest.get("source", {})
    if source != expected_source:
        raise CoverageError("owner_source_mismatch", expected=expected_source, actual=source)
    expected_populations = [*coverage["populations"], coverage["prefix_population"]]
    names = [p["owner_population"] for p in expected_populations]
    # Diagnose omitted populations in terms of every missing assignment.
    supplied = manifest.get("populations", [])
    if not isinstance(supplied, list) or not all(isinstance(p, dict) for p in supplied):
        raise CoverageError("malformed_owner_populations")
    supplied_names = [p.get("name") for p in supplied]
    missing = [
        [p["name"], r["identity"]]
        for p in expected_populations
        if p["owner_population"] not in supplied_names or p["owner_population"] not in full
        for r in p["members"]
    ]
    if missing:
        raise CoverageError("incomplete_owner_coverage", missing=missing)
    populations = exact_index(supplied, names, key=lambda p: p["name"], scope="owner populations")
    if set(full) != set(names):
        raise CoverageError("owner_full_population_mismatch", actual=sorted(full), expected=names)
    results = {}
    for expected in expected_populations:
        name = expected["name"]
        owner_name = expected["owner_population"]
        population = populations[owner_name]
        ids = [r["identity"] for r in expected["members"]]
        metadata = exact_index(
            population["rows"],
            ids,
            key=lambda r: r["assignment_id"],
            scope=name + ":owner metadata",
        )
        assessments = exact_index(
            full[owner_name], ids, key=lambda r: r["assignment_id"], scope=name + ":owner results"
        )
        if (
            population.get("expected") != len(ids)
            or population.get("count") != len(ids)
            or population.get("complete") is not True
        ):
            raise CoverageError("owner_population_not_complete", population=name)
        for member in expected["members"]:
            identity, assignment = member["identity"], member["assignment"]
            meta = metadata[identity]
            assessment = assessments[identity]["assessment"]
            if (
                meta.get("case_id") != assignment["case_id"]
                or meta.get("remedy_id") != assignment["remedy_id"]
                or meta.get("trace_canonical_sha256") != member["trace_sha256"]
                or meta.get("assessment_sha256") != digest(assessment)
                or assessment.get("case_id") != assignment["case_id"]
                or assessment.get("schema") != source["assessment_schema"]
            ):
                raise CoverageError(
                    "owner_input_or_result_binding", population=name, identity=identity
                )
            results[(name, identity)] = assessment
    return results


def changed_paths(before: object, after: object, path: str = "") -> list[str]:
    """Name every changed field; complete before/after objects stay in their files."""
    if before == after:
        return []
    if isinstance(before, dict) and isinstance(after, dict):
        result = []
        for key in sorted(before.keys() | after.keys()):
            child = path + "/" + key
            if key not in before or key not in after:
                result.append(child)
            else:
                result.extend(changed_paths(before[key], after[key], child))
        return result
    return [path or "/"]

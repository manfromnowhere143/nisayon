"""Check retained QP witnesses without a simulator, policy or optimization solver."""

import argparse
import math
from pathlib import Path

import numpy as np

from nisayon.engine.io import decode_json

from .evidence import sha256, write_json


def maximum_violation(A, lower, upper, tolerance, solution) -> float:
    """Independent scalar dot products; original per-row tolerance is the unit."""
    if A.ndim != 2 or solution.shape != (A.shape[1],):
        raise ValueError("matrix/solution dimensions disagree")
    n = A.shape[0]
    if any(x.shape != (n,) for x in (lower, upper, tolerance)):
        raise ValueError("constraint dimensions disagree")
    if (
        not np.all(np.isfinite(A))
        or not np.all(np.isfinite(solution))
        or not np.all(np.isfinite(tolerance))
        or not np.all(tolerance > 0)
        or np.any(np.isnan(lower))
        or np.any(np.isnan(upper))
        or np.any(lower > upper)
    ):
        raise ValueError("invalid numerical constraints")
    result = 0.0
    for row, lo, hi, tol in zip(A, lower, upper, tolerance, strict=True):
        value = math.fsum(float(a) * float(x) for a, x in zip(row, solution, strict=True))
        result = max(result, max(0.0, lo - value, value - hi) / tol)
    return float(result)


def verify(directory: Path) -> dict:
    report = decode_json((directory / "result.json").read_bytes())
    findings = []
    for episode in report["episodes"]:
        for row in episode["rejections"]:
            reference = row.get("independent_feasibility")
            if reference is None:
                continue
            name = reference["matrix_witness"]
            if Path(name).name != name:
                raise ValueError("unsafe witness name")
            path = directory / name
            if path.stat().st_size > 2_000_000 or sha256(path) != reference["matrix_sha256"]:
                raise ValueError("matrix identity mismatch")
            with np.load(path, allow_pickle=False) as data:
                A, lo, hi, tol = (data[k] for k in ("A", "lower", "upper", "tolerances"))
                accepted = maximum_violation(A, lo, hi, tol, data["reference_solution"])
                rejected = maximum_violation(A, lo, hi, tol, data["osqp_solution"])
            if accepted > 1 or rejected <= 1:
                raise ValueError("reference or rejected solution does not support finding")
            findings.append(
                {"matrix": name, "reference_violation": accepted, "rejected_violation": rejected}
            )
    if len(findings) != 9:
        raise ValueError("incomplete declared terminal witness set")
    return {
        "schema": "ricci.rb02.witness-review.v1",
        "matrices": findings,
        "scope": "Scalar feasibility arithmetic on retained matrices only; no physical feasibility, optimality, authenticity or control promotion.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        raise FileExistsError(args.out)
    write_json(args.out, verify(args.directory))


if __name__ == "__main__":
    main()

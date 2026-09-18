"""Checks on the execution lane's screen package (``nisayon.screen.execution-package.v1``).

The package freezes the sources, obligation and budgets a future reserved screen would
run under. These checks say whether the evaluator it binds is the evaluator in this
checkout, whether the obligation it names is the evaluator's, and which capabilities a
reserved screen still lacks. They run nothing and establish no custody.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from .case import OBLIGATION_V02
from .schema import Malformed, mapping

PACKAGE_SCHEMA = "nisayon.screen.execution-package.v1"
REPORT_SCHEMA = "nisayon.screen.package_check.v1"
EVALUATOR_PREFIX = "src/nisayon/evaluation/"
BLOCKING = {
    "package_schema_unknown",
    "obligation_differs",
    "evaluator_sources_unbound",
    "evaluator_sources_stale",
    "ceiling_unset",
    "capability_missing",
    "budget_undeclared",
    "confirmation_obligation_differs",
}
LIMITS = [
    "A package that passes binds the evaluator in this checkout; it says nothing about "
    "custody of reserved cases, which no record can establish.",
    "Unset ceilings and missing capabilities are what the package itself declares; the "
    "check cannot see an isolated provider that the package does not name.",
    "Source digests cover the files the package lists plus the evaluator directory in "
    "this checkout; installed dependencies are compared only when the package lists them "
    "by digest and this checkout can read the same records.",
]


def _finding(code: str, detail: str) -> dict:
    return {"code": code, "detail": detail, "blocking": code in BLOCKING}


def check_package(package: object, root: Path | None = None) -> dict:
    findings: list[dict] = []
    try:
        data = mapping(package, "package")
    except Malformed as error:
        return {
            "schema": REPORT_SCHEMA,
            "ready_for_reserved_screen": False,
            "findings": [_finding("package_schema_unknown", str(error))],
            "limits": LIMITS,
        }
    if data.get("schema") != PACKAGE_SCHEMA:
        findings.append(
            _finding(
                "package_schema_unknown",
                f"expected {PACKAGE_SCHEMA}, found {data.get('schema')!r}",
            )
        )
    predicates = data.get("predicates") if isinstance(data.get("predicates"), dict) else {}
    if predicates.get("protocol_id") != OBLIGATION_V02:
        findings.append(
            _finding(
                "obligation_differs",
                f"the package names obligation {predicates.get('protocol_id')!r}; the evaluator "
                f"decides under {OBLIGATION_V02!r}",
            )
        )
    code = data.get("code") if isinstance(data.get("code"), dict) else {}
    sources = code.get("sources") if isinstance(code.get("sources"), dict) else {}
    evaluator = {
        path: digest
        for path, digest in sources.items()
        if isinstance(path, str) and path.startswith(EVALUATOR_PREFIX) and isinstance(digest, str)
    }
    changed: list[str] = []
    missing: list[str] = []
    unlisted: list[str] = []
    if not evaluator:
        findings.append(
            _finding(
                "evaluator_sources_unbound",
                "the package binds no file under src/nisayon/evaluation/",
            )
        )
    elif root is not None:
        for path, digest in sorted(evaluator.items()):
            target = Path(root) / path
            if not target.is_file():
                missing.append(path)
            elif hashlib.sha256(target.read_bytes()).hexdigest() != digest.removeprefix("sha256:"):
                changed.append(path)
        here = Path(root) / EVALUATOR_PREFIX
        if here.is_dir():
            for target in sorted(here.glob("*.py")):
                relative = EVALUATOR_PREFIX + target.name
                if relative not in evaluator:
                    unlisted.append(relative)
        if changed or missing or unlisted:
            findings.append(
                _finding(
                    "evaluator_sources_stale",
                    f"the evaluator in this checkout is not the one the package froze at "
                    f"{data.get('frozen_at')} (git head {code.get('git_head')}): "
                    f"{len(changed)} changed, {len(missing)} missing, {len(unlisted)} unlisted; "
                    "re-freeze the package before any reserved screen",
                )
            )
    for key in ("agent_token_ceiling", "monetary_ceiling"):
        if data.get(key) is None:
            findings.append(
                _finding("ceiling_unset", f"{key} is unset; equal measured budgets are required")
            )
    capabilities = data.get("capabilities") if isinstance(data.get("capabilities"), dict) else {}
    for key in ("matched_isolated_agent_provider", "reserved_custody_boundary"):
        if capabilities.get(key) is None:
            findings.append(
                _finding("capability_missing", f"capabilities.{key} is absent; the screen is unrun")
            )
    budget = data.get("diagnostic_budget_per_arm")
    if not isinstance(budget, dict) or any(
        not isinstance(budget.get(key), int | float) for key in ("max_rollouts", "max_wall_seconds")
    ):
        findings.append(
            _finding(
                "budget_undeclared",
                "diagnostic_budget_per_arm must declare max_rollouts and max_wall_seconds",
            )
        )
    obligation = (
        data.get("confirmation_obligation")
        if isinstance(data.get("confirmation_obligation"), dict)
        else {}
    )
    if (
        obligation.get("paired_conditions") != 32
        or obligation.get("post_freeze_reproduction") is not True
        or obligation.get("retain_every_assigned_outcome") is not True
    ):
        findings.append(
            _finding(
                "confirmation_obligation_differs",
                "the package's confirmation obligation is not 32 fresh pairs with a post-freeze "
                "reproduction and every assigned outcome retained",
            )
        )
    if data.get("development_evidence") is None:
        findings.append(
            _finding(
                "development_evidence_absent",
                "the package names no completed development ledger; it describes an interface, "
                "not a qualified procedure",
            )
        )
    return {
        "schema": REPORT_SCHEMA,
        "package_schema": data.get("schema"),
        "package_frozen_at": data.get("frozen_at"),
        "package_git_head": code.get("git_head"),
        "obligation": predicates.get("protocol_id"),
        "evaluator_files_bound": len(evaluator),
        "evaluator_files_changed": changed,
        "evaluator_files_missing": missing,
        "evaluator_files_unlisted": unlisted,
        "ready_for_reserved_screen": not any(f["blocking"] for f in findings),
        "findings": findings,
        "limits": LIMITS,
    }


def render_package(report: dict) -> str:
    lines = [
        "Screen package: "
        + ("READY for a reserved screen" if report["ready_for_reserved_screen"] else "NOT READY")
        + (
            f" · frozen {report.get('package_frozen_at')} at {report.get('package_git_head')}"
            if report.get("package_frozen_at")
            else ""
        ),
        f"Obligation: {report.get('obligation')} · evaluator files bound: "
        f"{report.get('evaluator_files_bound', 0)} · changed {len(report.get('evaluator_files_changed', []))}"
        f" · missing {len(report.get('evaluator_files_missing', []))}"
        f" · unlisted {len(report.get('evaluator_files_unlisted', []))}",
    ]
    if report["findings"]:
        lines.append("Findings:")
        for finding in report["findings"]:
            marker = "blocking" if finding["blocking"] else "reported"
            lines.append(f"  - {finding['code']} ({marker}): {finding['detail']}")
    lines.append("Limits:")
    lines.extend(f"  - {limit}" for limit in report["limits"])
    return "\n".join(lines)

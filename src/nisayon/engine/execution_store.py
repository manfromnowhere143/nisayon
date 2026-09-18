"""Append execution intents before running, then seal immutable measured records.

Intents survive an interruption before a run record is returned. They are not
claims that the assigned rollout completed. Recovery reports inspect both.
"""

from __future__ import annotations

import copy
import json
import re
from datetime import UTC, datetime
from pathlib import Path

from .configuration import Deployment, EpisodePrefix
from .io import digest, file_digest, write_json
from .store import create_manifest, verify_execution


class ExecutionStore:
    def __init__(self, root: Path, header: dict, executor, preparation_costs: dict):
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=False)
        self.header = copy.deepcopy(header)
        self.header["attempt_contract"] = "nisayon.execution.attempt.v1"
        self.executor = executor
        self.runs: list[dict] = []
        self.assignments: list[dict] = []
        self.sealed = False
        self.snapshots = 0
        write_json(self.root / "invocation.json", executor.invocation)
        write_json(self.root / "preparation-costs.json", preparation_costs)
        self.header["preparation_cost_ledger"] = {
            "path": "preparation-costs.json",
            "sha256": file_digest(self.root / "preparation-costs.json"),
        }
        self.header["invocation"] = {
            "path": "invocation.json",
            "sha256": file_digest(self.root / "invocation.json"),
        }
        write_json(self.root / "bundle-header.json", self.header)

    def _intent(self, assignment: dict, configuration: dict) -> None:
        if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_-]{0,127}", assignment["run_id"]):
            raise ValueError("Run ID must be a simple artifact name")
        if self.sealed:
            raise RuntimeError("A sealed execution store cannot accept another attempt")
        if any(a["run_id"] == assignment["run_id"] for a in self.assignments):
            raise ValueError("Execution assignment already attempted; retain it and use a new ID")
        if self.header.get("assignments"):
            expected = next(
                (a for a in self.header["assignments"] if a["run_id"] == assignment["run_id"]), None
            )
            if expected != assignment:
                raise ValueError("Execution differs from the frozen assignment")
        write_json(
            self.root / "attempts" / (assignment["run_id"] + ".json"),
            {
                "schema": "nisayon.execution.attempt.v1",
                "assignment": assignment,
                "configuration": configuration,
                "configuration_sha256": digest(configuration),
                "declared_at": datetime.now(UTC).isoformat(),
                "status": "attempt_declared_before_execution",
                "invocation_id": self.executor.invocation["id"],
            },
        )
        self.assignments.append(assignment)

    def run(
        self,
        *,
        mode: str,
        seed: int,
        run_id: str,
        role: str,
        deployment: Deployment,
        prefix: EpisodePrefix | None = None,
        telemetry_profile: str = "full",
    ) -> dict:
        if prefix:
            prefix_configuration = self.executor.configuration_for(
                "prefix-reference",
                deployment=Deployment(),
                horizon=prefix.steps,
                stop_on_success=False,
                telemetry_profile=telemetry_profile,
            )
            self._intent(
                {
                    "mode": "prefix-reference",
                    "seed": prefix.seed,
                    "run_id": run_id + "-prefix",
                    "role": "executed_prefix_context",
                    "candidate_sha256": digest(prefix_configuration["deployment"]),
                },
                prefix_configuration,
            )
        configuration = self.executor.configuration_for(
            mode,
            deployment=deployment,
            prefix=prefix,
            telemetry_profile=telemetry_profile,
        )
        self._intent(
            {
                "mode": mode,
                "seed": seed,
                "run_id": run_id,
                "role": role,
                "candidate_sha256": digest(deployment.record()),
            },
            configuration,
        )
        run = self.executor.run(
            mode=mode,
            seed=seed,
            run_id=run_id,
            directory=self.root,
            deployment=deployment,
            prefix=prefix,
            case_id=self.header["case"]["id"],
            telemetry_profile=telemetry_profile,
        )
        run["assignment_role"] = role
        write_json(self.root / (run_id + ".run.json"), run)
        if run.get("prefix_run"):
            self.runs.append(json.loads((self.root / run["prefix_run"]["path"]).read_text()))
        self.runs.append(run)
        return run

    def snapshot(self) -> tuple[Path, dict]:
        """Seal a read-only prefix of diagnostic evidence for an early check."""
        if self.sealed or self.header.get("confirmation") is not None:
            raise RuntimeError("Snapshots are only for unsealed diagnostic evidence")
        self.snapshots += 1
        stem = f"snapshots/{self.snapshots:03d}"
        manifest = create_manifest(
            self.root,
            [str(p.relative_to(self.root)) for p in self.root.rglob("*") if p.is_file()],
            name=stem + ".manifest.json",
        )
        bundle = {
            **self.header,
            "assignments": self.assignments,
            "runs": self.runs,
            "artifact_manifest": manifest,
        }
        path = self.root / (stem + ".bundle.json")
        write_json(path, bundle)
        return path, verify_execution(bundle, self.root)

    def seal(self) -> tuple[Path, dict]:
        if self.sealed:
            raise RuntimeError("Execution store already sealed")
        if self.header.get("assignments"):
            assigned = {a["run_id"]: a for a in self.header["assignments"]}
            attempted = {a["run_id"]: a for a in self.assignments}
            if assigned != attempted:
                raise ValueError(
                    "Not all frozen assignments were attempted; recover the partial store"
                )
        manifest = create_manifest(
            self.root, [str(p.relative_to(self.root)) for p in self.root.rglob("*") if p.is_file()]
        )
        bundle = {
            **self.header,
            "assignments": self.header.get("assignments") or self.assignments,
            "runs": self.runs,
            "artifact_manifest": manifest,
        }
        path = self.root / "bundle.json"
        write_json(path, bundle)
        self.sealed = True
        try:
            verification = verify_execution(bundle, self.root)
        except (ValueError, KeyError, OSError, StopIteration) as error:
            verification = {"status": "invalid", "error": f"{type(error).__name__}: {error}"}
        write_json(self.root / "integrity.json", verification)
        return path, verification

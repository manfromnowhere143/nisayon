"""Project a reviewed, finite set of research results from committed Nisayon bytes.

This is an explicit publication adapter, not discovery or scientific assessment.
It reads only the named, already exposed results. No execution or reserved data.
Old content-addressed catalogs are retained so shared selections stay reproducible.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RESULTS = "docs/experiments/results/"


def build(engine: Path, revision: str) -> dict:
    def git(*args: str) -> bytes:
        return subprocess.check_output(["git", *args], cwd=engine)

    if (
        git("remote", "get-url", "research").decode().strip()
        != "https://github.com/manfromnowhere143/nisayon.git"
    ):
        raise ValueError("Expected the Nisayon research remote")
    commit = git("rev-parse", "--verify", f"{revision}^{{commit}}").decode().strip()
    sources: dict[str, dict] = {}

    def bind(path: str) -> bytes:
        raw = git("show", f"{commit}:{path}")
        sources[path] = {"path": path, "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}
        return raw

    def read(path: str) -> dict:
        return json.loads(bind(path))

    def result(folder: str, name: str) -> dict:
        return read(f"{RESULTS}{folder}/{name}")

    b2 = result("b2-semantic-transfer-001", "readback.json")
    convention = result("b2-semantic-transfer-001", "source-finding.json")
    terminal = result("terminal-observation-followthrough-001", "results.json")
    copy = result("eval-copy-native-001", "evidence.json")
    probe = result("decision-probes-001", "readback.json")
    probe_checks = result("decision-probes-001", "validation.json")
    routing = result("native-routing-001", "result.json")
    audit = result("prediction-audit-001", "challenge.json")
    a1 = result("a1-runtime-001", "completed-runtime-assessment-readback-001.json")
    setup = read("work/continuations/n049-native-baseline/result.json")
    adoption = read("work/continuations/n047-xpolicylab-reply/verification.json")
    reporter_root = f"{RESULTS}reporter-followthrough-001/"
    reporter = read(reporter_root + "controls-result.json")
    reporter_report = bind(reporter_root + "README.md").decode()
    if (
        reporter["passed"] != 12
        or reporter["failed_or_invalid"] != 0
        or "adopting the correction" not in reporter_report
    ):
        raise ValueError("Reviewed Arisole adoption evidence changed")

    dispatch_root = "work/continuations/n052-dispatch-timing/"
    dispatch = read(dispatch_root + "result.json")
    dispatch_protocol = read(dispatch_root + "protocol.json")
    dispatch_publication = read(dispatch_root + "publication-summary.json")
    dispatch_tests = bind(dispatch_root + "test_rollout_dispatch_timing.py")
    read(dispatch_root + "setup-amendment.json")
    if hashlib.sha256(dispatch_tests).hexdigest() != dispatch_protocol["test_files"][0]["sha256"]:
        raise ValueError("Dispatch controls differ from their frozen binding")
    if not dispatch_publication["draft"] or dispatch_publication["state"] != "open":
        raise ValueError("Reviewed dispatch contribution status changed")
    dispatch_runs = {}
    for name in ("baseline", "baseline-amended", "candidate"):
        tree = ET.fromstring(bind(dispatch_root + f"checks/{name}.xml"))
        controls = [
            {
                "name": test.attrib["name"],
                "status": "failed" if test.find("failure") is not None else "passed",
            }
            for test in tree.findall(".//testcase")
        ]
        if (
            len(controls) != 76
            or len({c["name"] for c in controls}) != 76
            or tree.findall(".//error")
            or tree.findall(".//skipped")
        ):
            raise ValueError("Dispatch control allocation changed")
        if sum(c["status"] == "failed" for c in controls) != dispatch[name]["failed"]:
            raise ValueError("Dispatch result and retained cases disagree")
        dispatch_runs[name] = controls
    if [dispatch[n]["failed"] for n in dispatch_runs] != [9, 7, 0] or any(
        {c["name"] for c in controls} != {c["name"] for c in dispatch_runs["baseline"]}
        for controls in dispatch_runs.values()
    ):
        raise ValueError("Reviewed dispatch comparison changed")

    promotion_root = "work/continuations/n051-promotion-integrity/"
    promotion = read(promotion_root + "results.json")
    promotion_publication = read(promotion_root + "publication-verification.json")
    promotion_tests = bind(promotion_root + "test_promote_manifest.py")
    read(promotion_root + "protocol.json")
    if not (
        promotion["unique_controls"] == 28
        and promotion["native_unchanged"] == 9
        and promotion["freeze_unchanged"]
    ):
        raise ValueError("Promotion control allocation changed")
    promotion_before = promotion["runs"]["baseline"]
    promotion_after = promotion["runs"]["publication-candidate"]
    for run in (promotion_before, promotion_after):
        if run["tests"] != 28 or run["errors"] or run["skipped"] or len(run["cases"]) != 28:
            raise ValueError("Promotion controls changed")
    if (
        promotion_before["failures"] != 11
        or promotion_after["failures"] != 0
        or set(promotion_before["cases"]) != set(promotion_after["cases"])
    ):
        raise ValueError("Promotion before/after evidence changed")
    if promotion_publication["merged"] or promotion_publication["state"] != "open":
        raise ValueError("Reviewed promotion contribution status changed")
    if not all(
        part in promotion_tests
        for part in (
            b"test_unlisted_sidecar_cannot_override_embedded_failure",
            b'"BLOCK"',
            b'"ROLLBACK"',
            b'"packet_manifest_hashes"',
        )
    ):
        raise ValueError("Reviewed promotion witness changed")
    terminal_report = f"{RESULTS}terminal-observation-followthrough-001/README.md"
    report = bind(terminal_report).decode()
    if not ("[41, 141]" in report and "[41, 42]" in report):
        raise ValueError("Committed evidence no longer matches the reviewed projection")
    b2_protocol = result("b2-semantic-transfer-001", "protocol.json")
    if not (b2_protocol):
        raise ValueError("Committed evidence no longer matches the reviewed projection")

    attention_root = "work/continuations/n050-frontier-investigation/"
    attention_protocol = read(attention_root + "protocol.json")
    attention_binding = read(attention_root + "test-source-binding.json")
    attention_publication = read(attention_root + "publication-receipt.json")
    attention_tests = bind(attention_root + "test_state_attention.py.txt")
    if hashlib.sha256(attention_tests).hexdigest() != attention_binding["tests_sha256"]:
        raise ValueError("Attention test bytes differ from the frozen binding")
    if sources[attention_root + "protocol.json"]["sha256"] != attention_binding["protocol_sha256"]:
        raise ValueError("Attention protocol differs from the frozen binding")

    def attention_run(name: str) -> dict:
        tree = ET.fromstring(bind(attention_root + name + ".xml"))
        suite = tree.find("testsuite")
        if suite is None:
            raise ValueError("Missing retained attention controls")
        tests, failures, errors, skipped = (
            int(suite.attrib[k]) for k in ("tests", "failures", "errors", "skipped")
        )
        cases = [
            {
                "name": test.attrib["name"],
                "status": "failed" if test.find("failure") is not None else "passed",
            }
            for test in suite.findall("testcase")
        ]
        if (
            errors
            or skipped
            or tests != 26
            or len(cases) != tests
            or len({c["name"] for c in cases}) != tests
        ):
            raise ValueError("Attention control membership changed")
        return {
            "counts": {
                "passed": tests - failures,
                "failed": failures,
                "error": errors,
                "skipped": skipped,
            },
            "cases": cases,
        }

    attention_before = attention_run("baseline")
    attention_after = attention_run("candidate")
    if attention_before["counts"]["failed"] != 22 or attention_after["counts"]["passed"] != 26:
        raise ValueError("Reviewed attention outcome changed")
    if {c["name"] for c in attention_before["cases"]} != {
        c["name"] for c in attention_after["cases"]
    }:
        raise ValueError("Attention before/after controls differ")
    if not attention_publication["draft"] or attention_publication["merged"]:
        raise ValueError("Attention contribution status changed")
    if not all(value in attention_tests for value in [b"6.0", b"1.5", b"2.25", b"1.125"]):
        raise ValueError("Reviewed attention witness changed")

    # Fail if the reviewed interpretation no longer fits the committed record.
    if not (len(b2["pairs"]) == 10 and b2["corrected_successes"] == 9):
        raise ValueError("Committed evidence no longer matches the reviewed projection")
    if not (b2["unchanged_successes"] == 0 and b2["paired_regressions"] == 0):
        raise ValueError("Committed evidence no longer matches the reviewed projection")
    if not (b2["remaining_failure"]["seed"] == 180104):
        raise ValueError("Committed evidence no longer matches the reviewed projection")
    if not (terminal["baseline"]["counts"]["failed"] == 8):
        raise ValueError("Committed evidence no longer matches the reviewed projection")
    if not (terminal["candidate"]["counts"]["passed"] == 48):
        raise ValueError("Committed evidence no longer matches the reviewed projection")
    if not (copy["results"]["candidate"]["passed"] == 13):
        raise ValueError("Committed evidence no longer matches the reviewed projection")
    if not (
        probe["decision_plan"]["total_cost"]
        == probe["competent_conventional_decision_plan"]["total_cost"]
    ):
        raise ValueError("Committed evidence no longer matches the reviewed projection")
    if not (a1["development"]["successes"] == 1):
        raise ValueError("Committed evidence no longer matches the reviewed projection")
    if not (setup["executed_native_cases"] == 0):
        raise ValueError("Committed evidence no longer matches the reviewed projection")

    def refs(*paths: str) -> list[dict]:
        return [sources[path] for path in paths]

    def rrefs(folder: str, *names: str) -> list[dict]:
        return refs(*(f"{RESULTS}{folder}/{name}" for name in names))

    def case(
        id: str,
        code: str,
        title: str,
        question: str,
        kind: str,
        status: str,
        date: str,
        finding: str,
        mechanism: str,
        limit: str,
        source: list[dict],
        data: dict,
        links: list[dict] | None = None,
    ) -> dict:
        return dict(
            id=id,
            code=code,
            title=title,
            question=question,
            kind=kind,
            status=status,
            date=date,
            finding=finding,
            mechanism=mechanism,
            limit=limit,
            sources=source,
            data=data,
            links=links or [],
        )

    cases = [
        case(
            "transfer",
            "B2",
            "Same shape. Reversed meaning.",
            "Why did the same policy stop lifting?",
            "Robot simulation",
            "supported",
            "2026-10-09",
            "Correcting three input values restored 9 of 10 fresh paired tasks. Unchanged inputs completed none.",
            "The object vector kept its ten dimensions. Across robosuite versions, its last three values reversed direction. The adapter negates only object[7:10] for this exact legacy checkpoint; every later state is recomputed.",
            "One failure remains. These twenty episodes are spent development conditions. General reliability, independent replication and a complete-cost advantage are unestablished.",
            rrefs(
                "b2-semantic-transfer-001", "readback.json", "source-finding.json", "protocol.json"
            ),
            {
                "pairs": b2["pairs"],
                "inputWitnesses": b2["network_input_array_witnesses_checked"],
                "unchanged": b2["unchanged_successes"],
                "corrected": b2["corrected_successes"],
                "oldExpression": convention["old"]["expression"],
                "newExpression": convention["new"]["expression"],
                "required": 8,
                "weightsUnchanged": b2["weights_unchanged"],
            },
            [
                {"title": f"robosuite {version} source", "url": url}
                for version, url in zip(
                    ["1.4.1", "1.5.1"], convention["primary_links"], strict=True
                )
            ],
        ),
        case(
            "terminal",
            "N031",
            "An episode must keep its ending.",
            "Which observation belongs to the task that just ended?",
            "Native CPU software",
            "supported",
            "2026-10-12",
            "The correction passes all 48 native controls. Eight SAME_STEP recording controls fail on the unchanged base.",
            "Autoreset returns the next episode's reset observation to the policy. The recorder must separately retain final_obs from the episode that produced the action. The live observation stays unchanged.",
            "Scripted policies and action-dependent environments test native software. No learned model, GPU, physics simulator or hardware result follows. The first invalid fixture attempt remains separate.",
            rrefs("terminal-observation-followthrough-001", "results.json", "README.md"),
            {
                "baseline": terminal["baseline"]["counts"],
                "corrected": terminal["candidate"]["counts"],
                "controls": [
                    {
                        "name": c["name"],
                        "before": c["status"],
                        "after": next(
                            x["status"]
                            for x in terminal["candidate"]["cases"]
                            if x["name"] == c["name"]
                        ),
                    }
                    for c in terminal["baseline"]["cases"]
                ],
                "invalid": terminal["invalid_fixture"]["counts"],
                "witness": {"start": 41, "terminal": 42, "reset": 141},
            },
            [
                {
                    "title": "LeRobot terminal-observation contribution",
                    "url": "https://github.com/huggingface/lerobot/pull/4943",
                },
                {
                    "title": "Separate upstream scoring correction #4485",
                    "url": "https://github.com/huggingface/lerobot/pull/4485",
                },
            ],
        ),
        case(
            "processors",
            "N021",
            "Copy the relationship, too.",
            "Can two copied processors still share the current state?",
            "Native CPU software",
            "supported",
            "2026-10-11",
            "One linked copy restores the native evaluator's state relationship: 13 controls pass; the base fails four.",
            "Separate deepcopy calls break the shared reference between relative-action and absolute-action processors. Copying them together preserves that relationship within each worker.",
            "The upstream authors own the original shared-state diagnosis and worker design. This contribution supplies a linked-processor counterexample. Arbitrary policy copying and robot performance remain unqualified.",
            rrefs("eval-copy-native-001", "evidence.json"),
            {
                "baseline": copy["results"]["baseline"]["passed"],
                "corrected": copy["results"]["candidate"]["passed"],
                "total": 13,
                "currentState": 10,
                "staleState": 100,
                "relativeAction": 1,
                "actual": 101,
                "required": 11,
                "sourceCommit": copy["source_commit"],
            },
            [{"title": "LeRobot worker-state proposal", "url": copy["upstream_url"]}],
        ),
        case(
            "decisions",
            "N042",
            "Different causes. One decision.",
            "How much must we learn before choosing a correction?",
            "Constructed finite model",
            "supported",
            "2026-10-15",
            "One declared probe separates the two correction choices. Two possible causes remain. Competent conventional grouping ties the cost.",
            "The offline procedure separates hypotheses only when their frozen correction and confirmation labels differ. It does not execute probes or accept a robot repair.",
            "Predictions, error bounds, hypotheses and label equivalence are supplied premises. Complete engineering effort is unmeasured. Fresh task confirmation is still required.",
            rrefs("decision-probes-001", "readback.json", "validation.json"),
            {
                "labels": probe["declared_labels"],
                "probes": probe["candidate_probes"],
                "outcomes": [
                    {
                        "hypothesis": x["constructed_hypothesis"],
                        "survivors": x["assessment"]["survivors"],
                        "label": x["assessment"]["decision"]["label"],
                    }
                    for x in probe["constructed_outcomes"]
                ],
                "fullCost": probe["full_identification_plan"]["total_cost"],
                "decisionCost": probe["decision_plan"]["total_cost"],
                "nativeCost": probe["competent_conventional_decision_plan"]["total_cost"],
                "controls": probe_checks["controls"]["passed"],
            },
        ),
        case(
            "routing",
            "N044",
            "Two clients became one.",
            "Can a queue mistake different senders for the same client?",
            "Native CPU software",
            "supported",
            "2026-10-15",
            "The corrected identity encoding preserves all 1,464 declared envelope identities. The original has 304 colliding inputs.",
            "Joining binary frames with a zero separator is ambiguous. A length-prefixed key retains frame boundaries so one client's queued request cannot replace another's.",
            "These are extracted native transport and queue controls. They establish neither model inference nor robot behavior, and add no transport backend to Nisayon.",
            rrefs("native-routing-001", "result.json"),
            {
                "original": routing["variants"]["original"]["finite_injectivity"],
                "corrected": routing["variants"]["corrected"]["finite_injectivity"],
                "before": routing["variants"]["original"]["transport_cases"][0],
                "after": routing["variants"]["corrected"]["transport_cases"][0],
                "sourceCommit": routing["upstream_revision"],
            },
        ),
        case(
            "cost",
            "N045",
            "Price the whole experiment.",
            "Does an apparent saving survive setup, resets and adoption?",
            "Constructed probability model",
            "exploratory",
            "2026-10-16",
            "Even the favorable construction leaves only 4.735 execution cost units for all extra work. Integration can erase the saving.",
            "Prediction-aided auditing can reduce expected execution acquisitions while requiring more contexts. Charge both, together with predictor and setup costs, against the same native decision requirement.",
            "This is an arithmetic sensitivity view of a constructed model. An owner's signal, valid sampling and complete measured costs are unavailable. The finite production confirmation rule is unchanged.",
            rrefs("prediction-audit-001", "challenge.json"),
            {
                "saving": audit["cost_model"]["acquisition_saving_in_execution_cost_units"][
                    "decimal"
                ],
                "extraContexts": audit["cost_model"]["extra_contexts"]["decimal"],
                "breakEven": audit["cost_model"][
                    "common_context_cost_break_even_relative_to_execution"
                ]["decimal"],
                "unmeasured": audit["cost_model"]["unmeasured"],
            },
        ),
        case(
            "competence",
            "A1",
            "A working runtime can fail the task.",
            "Is this checkpoint a competent reference?",
            "Robot simulation",
            "rejected",
            "2026-10-09",
            "The runtime passes its qualification checks. The checkpoint completes 1 of 10 tasks against 8 required and is rejected as a competent reference.",
            "Execution validity and task competence are separate obligations. All ten episodes completed normally; nine reached their horizon without lifting the object.",
            "The result does not isolate training quality as the cause. Historical trajectory fidelity remains limited. These exposed development episodes cannot serve as fresh confirmation.",
            rrefs("a1-runtime-001", "completed-runtime-assessment-readback-001.json"),
            {
                "successes": a1["development"]["successes"],
                "required": a1["development"]["required_successes"],
                "episodes": [
                    {"seed": x["seed"], "steps": x["steps"], "outcome": x["outcome"]}
                    for x in a1["development"]["episodes"]
                ],
                "criteria": a1["verdicts"]["criteria"],
            },
        ),
        case(
            "deployment",
            "N049",
            "The experiment has not started.",
            "Can the declared deployment dependencies coexist?",
            "Dependency resolution",
            "blocked",
            "2026-10-17",
            "The declared NumPy requirements have an empty intersection. None of the 44 selected native tests ran.",
            "Long-WAM requires NumPy below 2. Its infra extra selects LeRobot 0.4.1, whose allowed Rerun versions require NumPy 2 or newer. Separate resolution controls reproduce the contradiction.",
            "No environment was installed and no constraint was bypassed. A consistent deployment profile is needed before the original baseline; a migration comparison also needs a candidate port.",
            refs("work/continuations/n049-native-baseline/result.json"),
            {
                "planned": setup["planned_native_cases"],
                "executed": setup["executed_native_cases"],
                "sourceCommit": setup["source_revision"],
                "controls": setup["diagnostic_controls"],
                "numpy": ">=1.26,<2",
                "rerunNumpy": ">=2",
                "lerobot": "0.4.1",
                "rerun": ">=0.24.0,<0.27.0",
            },
            [
                {
                    "title": "Reported deployment dependency conflict",
                    "url": "https://github.com/NVlabs/LongLive/issues/112",
                }
            ],
        ),
    ]
    cases.append(
        case(
            "attention",
            "N050",
            "Same weights. Different information.",
            "Does cached attention preserve the training contract?",
            "Native CPU attention",
            "supported",
            "2026-10-17",
            "Separating state queries restores the frozen attention contract: 26 controls pass. The original passes four and fails 22.",
            "Training restricts each state query to its own state block. Cached inference also exposed video and action context. One narrow split preserves the state context while retaining video/action outputs and the video cache. Issue #61's reporter, boqian-li, identified the mismatch and proposed direction.",
            "The draft contribution is not adopted. These exposed CPU fixtures use Torch 2.11.0, not the declared 2.8.0 profile. GPU, compilation, complete package import, checkpoint quality and task outcomes remain unqualified. The extra attention call has unmeasured cost.",
            refs(
                *(
                    attention_root + name
                    for name in [
                        "protocol.json",
                        "test-source-binding.json",
                        "test_state_attention.py.txt",
                        "baseline.xml",
                        "candidate.xml",
                        "publication-receipt.json",
                    ]
                )
            ),
            {
                "baseline": attention_before["counts"],
                "corrected": attention_after["counts"],
                "controls": [
                    {
                        "name": c["name"],
                        "before": c["status"],
                        "after": next(
                            x["status"] for x in attention_after["cases"] if x["name"] == c["name"]
                        ),
                    }
                    for c in attention_before["cases"]
                ],
                "trainingState": 6,
                "originalState": 1.5,
                "correctedState": 6,
                "trainingAction": 2.25,
                "originalAction": 1.125,
                "correctedAction": 2.25,
                "values": [0, 0, 0, 6],
                "sourceCommit": attention_protocol["source_commit"],
                "contributionCommit": attention_publication["head"],
                "draft": attention_publication["draft"],
            },
            [
                {
                    "title": "Original state-query diagnosis · boqian-li",
                    "url": "https://github.com/dreamzero0/dreamzero/issues/61",
                },
                {
                    "title": "Draft correction and portable controls",
                    "url": attention_publication["url"],
                },
            ],
        )
    )
    cases.append(
        case(
            "promotion",
            "N051",
            "A decision must bind what it reads.",
            "Can an unlisted file turn a blocked deployment into a promotion?",
            "Native CPU promotion controls",
            "supported",
            "2026-10-17",
            "Required hashes and consumed-file coverage restore the gate: 28 controls pass, versus 17 before correction.",
            "An unlisted passing policy sidecar could override an embedded failure. The correction checks that the manifest binds the receipt and every consumed policy sidecar before accepting the decision. Valid packets and explicitly optional hash profiles remain valid.",
            "The contribution is open, not merged. These are 28 exposed software controls, including nine unchanged upstream tests. Repeating them after publication does not add independent cases. Full upstream tests, unsigned evidence authenticity, concurrent file replacement, robot outcomes and owner savings remain unqualified. Stable local files are a premise.",
            refs(
                *(
                    promotion_root + name
                    for name in [
                        "protocol.json",
                        "test_promote_manifest.py",
                        "results.json",
                        "publication-verification.json",
                    ]
                )
            ),
            {
                "baseline": {"passed": 17, "failed": 11, "error": 0, "skipped": 0},
                "corrected": {"passed": 28, "failed": 0, "error": 0, "skipped": 0},
                "controls": [
                    {
                        "name": name,
                        "before": "passed" if before == "pass" else "failed",
                        "after": "passed" if promotion_after["cases"][name] == "pass" else "failed",
                    }
                    for name, before in promotion_before["cases"].items()
                ],
                "nativeControls": 9,
                "sourceCommit": promotion_publication["base"],
                "contributionCommit": promotion_publication["head"],
                "merged": False,
            },
            [
                {"title": "Native reproduction", "url": promotion_publication["issue"]},
                {"title": "Proposed correction and controls", "url": promotion_publication["pr"]},
            ],
        )
    )
    cases.append(
        case(
            "dispatch",
            "N052",
            "Ready before the next control.",
            "Can a plan finish in time and still miss its dispatch?",
            "Native CPU scheduling",
            "supported",
            "2026-10-17",
            "Collecting a completed plan after pacing changes seven failures and 69 passes to 76 passes. All 59 unchanged upstream controls remain included.",
            "The original engine checks readiness before waiting for the next control tick. A plan that finishes during that wait is missed. The correction collects it after pacing, then selects and materializes the command. Genuinely late chunks remain rejected as a whole.",
            "A controlled clock and synthetic planner test the native engine, including one real worker. No hardware deadline, model backend, task success or latency gain is established. Materialization cost after pacing is unmeasured. The first attempt retains two import setup failures and an explicit PYTHONPATH amendment. The contribution remains draft and unmerged.",
            refs(
                *(
                    dispatch_root + name
                    for name in [
                        "protocol.json",
                        "test_rollout_dispatch_timing.py",
                        "checks/baseline.xml",
                        "checks/baseline-amended.xml",
                        "checks/candidate.xml",
                        "result.json",
                        "setup-amendment.json",
                        "publication-summary.json",
                    ]
                )
            ),
            {
                "baseline": {"passed": 69, "failed": 7, "error": 0, "skipped": 0},
                "corrected": {"passed": 76, "failed": 0, "error": 0, "skipped": 0},
                "initial": {"passed": 67, "failed": 9, "error": 0, "skipped": 0},
                "controls": [
                    {
                        "name": c["name"],
                        "before": c["status"],
                        "after": next(
                            x["status"]
                            for x in dispatch_runs["candidate"]
                            if x["name"] == c["name"]
                        ),
                    }
                    for c in dispatch_runs["baseline-amended"]
                ],
                "nativeControls": 59,
                "newControls": 17,
                "sourceCommit": dispatch_publication["base"],
                "contributionCommit": dispatch_publication["head"],
                "draft": True,
                "witness": {"readyAt": 0.5, "dispatchAt": 1, "oldCommand": 11, "newCommand": 100},
            },
            [{"title": "OpenWAM dispatch correction · draft", "url": dispatch_publication["url"]}],
        )
    )
    modules = []
    for path in (
        git(
            "ls-tree",
            "-r",
            "--name-only",
            commit,
            "src/nisayon/engine",
            "src/nisayon/evaluation",
            "src/nisayon/qualification",
        )
        .decode()
        .splitlines()
    ):
        if (
            not path.endswith(".py")
            or Path(path).name.startswith("__")
            or Path(path).parent.name not in {"engine", "evaluation", "qualification"}
        ):
            continue
        tree = ast.parse(bind(path))
        modules.append(
            {
                "name": Path(path).stem,
                "package": Path(path).parent.name,
                "description": ast.get_docstring(tree)
                or "Implementation source; inspect the named entry points for its scope.",
                "entries": [
                    {
                        "name": node.name,
                        "kind": "class" if isinstance(node, ast.ClassDef) else "function",
                        "line": node.lineno,
                    }
                    for node in tree.body
                    if isinstance(node, (ast.FunctionDef, ast.ClassDef))
                    and not node.name.startswith("_")
                ],
                "source": sources[path],
            }
        )
    return {
        "schema": "nisayon.research-catalog.v4",
        "asOf": "2026-10-17",
        "sourceCommit": commit,
        "scope": "Reviewed projections of exposed retained results. No execution connection.",
        "modules": modules,
        "upstream": [
            {
                "title": "XPolicyLab · Cartesian pose correction",
                "status": "merged",
                "date": "2026-10-17",
                "url": "https://github.com/XPolicyLab/XPolicyLab/pull/181",
                "source": sources["work/continuations/n047-xpolicylab-reply/verification.json"],
            },
            {
                "title": "Arisole 0.1.3 · label coverage correction",
                "status": "released",
                "date": "2026-10-12",
                "url": "https://github.com/huggingface/lerobot/pull/4927#issuecomment-6127308467",
                "source": sources[reporter_root + "README.md"],
            },
        ],
        "adoption": {
            "date": "2026-10-17",
            "title": "XPolicyLab merged the Cartesian pose correction.",
            "revision": adoption["revision"],
            "passed": adoption["passed"],
            "unchangedJointOutputs": len(adoption["joint_outputs_equal_original_baseline"]),
            "scope": adoption["scope"],
            "url": "https://github.com/XPolicyLab/XPolicyLab/pull/181",
            "source": sources["work/continuations/n047-xpolicylab-reply/verification.json"],
        },
        "cases": cases,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--engine", type=Path, required=True)
    parser.add_argument("--revision", required=True)
    parser.add_argument(
        "--check", action="store_true", help="Verify the catalog and pin without writing"
    )
    args = parser.parse_args()
    catalog = build(args.engine.resolve(), args.revision)
    raw = (json.dumps(catalog, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode()
    digest = hashlib.sha256(raw).hexdigest()
    target = ROOT / "apps/instrument/public/research" / digest / "catalog.json"
    pin = ROOT / "apps/instrument/src/research/catalogPin.ts"
    pin_text = f'// Exact bytes projected by tools/ui/build_research_catalog.py.\nexport const CATALOG_SHA =\n  "{digest}";\n'
    if args.check:
        if not target.exists() or target.read_bytes() != raw or pin.read_text() != pin_text:
            raise ValueError(
                "Published projection or source pin differs from the committed evidence"
            )
        print(
            json.dumps(
                {
                    "verified": True,
                    "sha256": digest,
                    "sourceCommit": catalog["sourceCommit"],
                    "cases": len(catalog["cases"]),
                    "modules": len(catalog["modules"]),
                }
            )
        )
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() and target.read_bytes() != raw:
        raise ValueError("Immutable catalog collision")
    target.write_bytes(raw)
    pin.parent.mkdir(parents=True, exist_ok=True)
    pin.write_text(pin_text)
    print(
        json.dumps(
            {
                "sha256": digest,
                "bytes": len(raw),
                "cases": len(catalog["cases"]),
                "sourceCommit": catalog["sourceCommit"],
            }
        )
    )


if __name__ == "__main__":
    main()

"""Exercise native evaluator entrypoints with controlled task/rollout boundaries.

Set EMERGE_SOURCE to the pinned or patched source directory. No simulator,
agent, model server, policy inference, or physical robot is executed.
"""

from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path

import pytest

SOURCE = Path(os.environ["EMERGE_SOURCE"]).resolve()


def load(name, relative):
    spec = importlib.util.spec_from_file_location(name, SOURCE / relative)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


BASE = load("eval_libero_agent", "scripts/Libero_eval/eval_libero_agent.py")
PLUS = load("eval_libero_plus_agent", "scripts/LiberoPlus_eval/eval_libero_plus_agent.py")
PRO = load("eval_libero_pro_agent", "scripts/LiberoPro_eval/eval_libero_pro_agent.py")


class BetweenEpisodes(Exception):
    """Controlled interruption after the first persisted episode."""


class Campaign:
    def __init__(self, kind, tmp_path, monkeypatch):
        self.kind = kind
        self.module = {"base": BASE, "plus": PLUS, "pro": PRO}[kind]
        self.root = tmp_path / "campaign"
        self.monkeypatch = monkeypatch
        self.calls = []
        self.interrupt = False
        config = tmp_path / "driver.json"
        config.write_text(json.dumps({"libero": {"libero_source_path": str(tmp_path)}}))
        profile = tmp_path / "profile.md"
        profile.write_text("Controlled profile. No robot execution.\n")
        self.argv = [
            str(self.module.__file__),
            "--output-dir",
            str(self.root),
            "--driver-config",
            str(config),
            "--profile-path",
            str(profile),
            "--policy-backend",
            "vla",
            "--skip-policy-server-check",
            "--workers",
            "1",
        ]
        dimension = {"base": None, "plus": "Camera Viewpoints", "pro": "Object"}[kind]
        specs = [
            {
                "key": f"controlled-{kind}-{i}",
                "suite": "libero_spatial_object" if kind == "pro" else "libero_spatial",
                "base_suite": "libero_spatial",
                "benchmark_suite": "libero_spatial_object",
                "task_id": i,
                "trial": 0,
                "seed": 7,
                "instruction": "Controlled task, not a robot outcome",
                "filename_instruction": "controlled",
                "task_name": f"controlled_{i}",
                "bddl_file": str(tmp_path / "controlled.bddl"),
                "initial_state": [0.0],
                **({"dimension": dimension, "dimension_slug": kind} if dimension else {}),
            }
            for i in range(2)
        ]
        monkeypatch.setattr(BASE, "_prepare_libero_config", lambda *a: None)
        if kind == "base":
            self.argv += ["--task-ids", "0,1"]
            monkeypatch.setattr(BASE, "_build_episode_specs", lambda **kw: specs)
        elif kind == "plus":
            self.argv += ["--dimension", "camera_viewpoints", "--count", "2"]
            monkeypatch.setattr(PLUS, "_ensure_imagemagick_env", lambda: None)
            monkeypatch.setattr(PLUS, "_install_robosuite_compat", lambda: None)
            categories = {"libero_spatial": {0: dimension, 1: dimension}}
            selected = {dimension: {suite: [] for suite in PLUS.LIBERO_PLUS_SUITES}}
            selected[dimension]["libero_spatial"] = [0, 1]
            monkeypatch.setattr(PLUS, "_load_task_categories", lambda *a: categories)
            monkeypatch.setattr(PLUS, "_select_task_ids_by_dimension", lambda *a, **kw: selected)
            monkeypatch.setattr(PLUS, "_build_dimension_specs", lambda **kw: specs)
            monkeypatch.setattr(PLUS, "_validate_bddl_sources", lambda *a: None)
        else:
            self.argv += ["--dimension", "object", "--count", "2"]
            selected = {dimension: {suite: [] for suite in PRO.BASE_SUITE_ORDER}}
            selected[dimension]["libero_spatial"] = [0, 1]
            excluded = {dimension: {suite: [] for suite in PRO.BASE_SUITE_ORDER}}
            monkeypatch.setattr(PRO, "_install_robosuite_compat", lambda: None)
            monkeypatch.setattr(PRO, "_prepare_libero_pro_config", lambda *a: None)
            monkeypatch.setattr(PRO, "_resolve_dimensions", lambda *a: [dimension])
            monkeypatch.setattr(PRO, "_load_benchmark_dict", lambda *a: {})
            monkeypatch.setattr(
                PRO, "_select_task_ids_by_dimension", lambda *a, **kw: (selected, excluded)
            )
            monkeypatch.setattr(PRO, "_build_episode_specs", lambda *a, **kw: specs)
            monkeypatch.setattr(PRO, "_git_revision", lambda *a: "controlled-source-revision")

        def rollout(spec, *, args, output_dir, **kwargs):
            self.calls.append(spec["key"])
            if self.interrupt and len(self.calls) == 2:
                raise BetweenEpisodes()
            attempt = output_dir / f"controlled_attempt_{len(self.calls)}"
            attempt.mkdir(parents=True)
            result = {
                **spec,
                "episode_key": spec["key"],
                "success": False,
                "termination_reason": "controlled_task_failure",
                "action_steps": 1,
                "duration_s": 0.0,
                "attempt_dir": str(attempt),
                "max_action_steps": args.max_steps or BASE.MAX_STEPS[spec["base_suite"]],
                "controlled_settings": {
                    "num_steps_wait": args.num_steps_wait,
                    "episode_timeout_s": args.episode_timeout_s,
                    "max_agent_feedback_rounds": args.max_agent_feedback_rounds,
                },
            }
            (attempt / "result.json").write_text(json.dumps(result) + "\n")
            return result

        monkeypatch.setattr(BASE, "_run_episode", rollout)

    def invoke(self, extra=()):
        self.monkeypatch.setattr(sys, "argv", self.argv + list(extra))
        return self.module.main()

    def interrupted(self, extra=()):
        self.interrupt = True
        with pytest.raises(BetweenEpisodes):
            self.invoke(extra)
        self.interrupt = False
        assert len(self.results()) == 1

    def results(self):
        return [json.loads(line) for line in (self.root / "results.jsonl").read_text().splitlines()]

    def retained_bytes(self):
        return {
            str(path.relative_to(self.root)): path.read_bytes()
            for path in self.root.rglob("*")
            if path.is_file()
        }


@pytest.fixture(params=["base", "plus", "pro"])
def campaign(request, tmp_path, monkeypatch):
    return Campaign(request.param, tmp_path, monkeypatch)


def test_same_settings_resume_without_repeating_completed_episode(campaign):
    campaign.interrupted(["--max-steps", "16"])
    prefix = (campaign.root / "results.jsonl").read_bytes()
    assert campaign.invoke(["--resume", "--max-steps", "16"]) == 0
    assert (campaign.root / "results.jsonl").read_bytes().startswith(prefix)
    assert campaign.calls == [
        f"controlled-{campaign.kind}-0",
        f"controlled-{campaign.kind}-1",
        f"controlled-{campaign.kind}-1",
    ]
    assert len(campaign.results()) == 2
    assert [r["max_action_steps"] for r in campaign.results()] == [16, 16]
    assert json.loads((campaign.root / "summary.json").read_text())["episodes"] == 2


@pytest.mark.parametrize(
    ("option", "before", "after"),
    [
        ("--max-steps", "16", "620"),
        ("--num-steps-wait", "0", "50"),
        ("--episode-timeout-s", "60", "900"),
        ("--max-agent-feedback-rounds", "0", "2"),
    ],
)
def test_changed_budget_rejected_before_any_retained_write(campaign, option, before, after):
    campaign.interrupted([option, before])
    retained = campaign.retained_bytes()
    calls = list(campaign.calls)
    with pytest.raises(SystemExit) as exc:
        campaign.invoke(["--resume", option, after])
    assert exc.value.code == 2
    assert campaign.calls == calls
    assert campaign.retained_bytes() == retained
    assert campaign.invoke(["--resume", option, before]) == 0
    assert len(campaign.results()) == 2


def test_explicit_effective_default_is_compatible(campaign):
    campaign.interrupted()
    assert campaign.invoke(["--resume", "--max-steps", "620"]) == 0
    assert [r["max_action_steps"] for r in campaign.results()] == [620, 620]


def test_changed_effective_default_rejected(campaign, monkeypatch):
    campaign.interrupted()
    retained = campaign.retained_bytes()
    calls = list(campaign.calls)
    monkeypatch.setitem(BASE.MAX_STEPS, "libero_spatial", 621)
    with pytest.raises(SystemExit) as exc:
        campaign.invoke(["--resume"])
    assert exc.value.code == 2
    assert campaign.calls == calls
    assert campaign.retained_bytes() == retained


@pytest.mark.parametrize("missing", ["field", "file"])
def test_legacy_plan_cannot_be_silently_rebound(campaign, missing):
    campaign.interrupted()
    path = campaign.root / "evaluation_plan.json"
    plan = json.loads(path.read_text())
    if missing == "field":
        plan.pop("execution_settings", None)
        path.write_text(json.dumps(plan) + "\n")
    else:
        path.unlink()
    retained = campaign.retained_bytes()
    calls = list(campaign.calls)
    with pytest.raises(SystemExit) as exc:
        campaign.invoke(["--resume"])
    assert exc.value.code == 2
    assert campaign.calls == calls
    assert campaign.retained_bytes() == retained


def test_resume_in_new_directory_can_initialize_a_plan(campaign):
    assert campaign.invoke(["--resume"]) == 0
    assert len(campaign.results()) == 2

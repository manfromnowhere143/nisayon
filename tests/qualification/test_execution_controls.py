"""Execution failures that a plausible output or successful process must not hide."""

from __future__ import annotations

import json
import os
import shutil
import signal
import subprocess
import sys
import time
import venv
from pathlib import Path

import psutil
import pytest

import nisayon
from nisayon.engine.io import write_json
from nisayon.qualification import CaseSpec, inspect_run, plan_change, run_plan

from .test_native_qualification import execute, reseal


@pytest.mark.parametrize("venv_in_project", [False, True])
def test_installed_sdk_does_not_shadow_native_environment_dependencies(
    native, tmp_path, venv_in_project
):
    declaration, context = native
    host = tmp_path / "sdk-host-site-packages"
    shutil.copytree(
        Path(nisayon.__file__).parent,
        host / "nisayon",
        ignore=shutil.ignore_patterns("__pycache__"),
    )
    (host / "native_dependency.py").write_text("raise RuntimeError('wrong host dependency')\n")
    native_venv = (context.project if venv_in_project else tmp_path) / "native-venv"
    venv.EnvBuilder(with_pip=False).create(native_venv)
    native_python = native_venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    site = subprocess.run(
        [str(native_python), "-I", "-c", "import sysconfig; print(sysconfig.get_path('purelib'))"],
        text=True,
        capture_output=True,
        check=True,
    ).stdout.strip()
    Path(site, "native_dependency.py").write_text("VALUE = 1\n")
    source = context.project / "policy.py"
    source.write_text(
        "import native_dependency\nassert native_dependency.VALUE == 1\n" + source.read_text()
    )
    case_path = tmp_path / "case.json"
    write_json(case_path, declaration)
    script = (
        f"import sys; sys.path.insert(0, {str(host)!r}); "
        "from nisayon.qualification import *; "
        f"c = CaseSpec.read({str(case_path)!r}); "
        f"x = ExecutionContext.from_project({str(context.project)!r}, "
        f"output_dir={str(context.output_dir)!r}, python={str(native_python)!r}); "
        "p = plan_change(c, context=x); e = run_plan(p, context=x); "
        "print(assess_change(c, e).decision)"
    )
    result = subprocess.run(
        [sys.executable, "-I", "-c", script],
        cwd=tmp_path,
        text=True,
        capture_output=True,
        check=True,
    )
    assert result.stdout.strip() == "adopt", result.stderr


def test_changed_runtime_record_cannot_support_acceptance(native):
    _, _, evidence, _ = execute(native)
    path = evidence.root / "candidate-offset/observation.json"
    observed = json.loads(path.read_text())
    observed["runtime"]["prefix"] = "/a/different/native/environment"
    path.write_text(json.dumps(observed))
    reseal(evidence.root)
    assessment = inspect_run(evidence.root).record()
    assert assessment["software_decision"] == "unresolved"
    assert "native_environment_differs_from_plan:candidate-offset" in assessment["obligations"]


def test_environment_changed_after_planning_prevents_execution(native, monkeypatch):
    declaration, context = native
    plan = plan_change(CaseSpec.from_dict(declaration), context=context)
    record = context.record()
    record["native_environment"]["packages"].append(
        {"name": "changed-dependency", "version": "2.0", "record_sha256": None}
    )
    # Model an installation between plan and run without altering the test interpreter.
    monkeypatch.setattr(type(context), "record", lambda self: record)
    with pytest.raises(ValueError, match="no longer matches"):
        run_plan(plan, context=context)
    assert not context.output_dir.exists()


def test_source_changed_by_native_call_invalidates_the_observation(native):
    declaration, context = native
    declaration["targets"]["candidate"]["callable"] = "mutate"
    source = context.project / "policy.py"
    source.write_text(
        source.read_text() + "\ndef mutate(value):\n"
        "    from pathlib import Path\n"
        "    source = Path(__file__)\n"
        "    source.write_text(source.read_text() + '\\n# changed during execution\\n')\n"
        "    return normalize(value)\n"
    )
    _, _, _, assessment = execute(native)
    assert assessment["software_decision"] == "unresolved"
    assert assessment["execution_validity"] == "invalid"


@pytest.mark.skipif(os.name != "posix", reason="Process-group cleanup is a POSIX contract")
def test_cli_interrupt_retains_prefix_and_terminates_native_descendants(native, tmp_path):
    declaration, context = native
    source = context.project / "policy.py"
    source.write_text(
        source.read_text() + "\ndef interruptible(value):\n"
        "    import subprocess, sys, time\n"
        "    child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)'])\n"
        "    print(child.pid, flush=True)\n"
        "    time.sleep(30)\n"
        "    return normalize(value)\n"
    )
    declaration["targets"]["candidate"]["callable"] = "interruptible"
    plan = plan_change(CaseSpec.from_dict(declaration), context=context)
    plan_path = tmp_path / "frozen.json"
    write_json(plan_path, plan.record())
    process = subprocess.Popen(
        [sys.executable, "-m", "nisayon.qualification", "run", str(plan_path)],
        cwd=context.project,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    prefix = context.output_dir / "candidate-offset/stdout.txt"
    try:
        deadline = time.monotonic() + 15
        while not prefix.exists() or not prefix.read_text().strip():
            assert process.poll() is None, "Runner exited before entering native call"
            assert time.monotonic() < deadline, "Native call did not start"
            time.sleep(0.02)
        descendant = int(prefix.read_text().strip())
        process.send_signal(signal.SIGINT)
        stdout, stderr = process.communicate(timeout=10)
        assert process.returncode == 3, stderr
        assessment = json.loads(stdout)
        assert assessment["software_decision"] == "unresolved"
        assert assessment["execution_validity"] == "incomplete"
        assert assessment["attempts"][-1]["error"] == "operator_interrupt"
        assert assessment["costs"]["attempts_with_measured_wall"] == 3
        assert inspect_run(context.output_dir).record() == assessment
        assert not psutil.pid_exists(descendant) or psutil.Process(descendant).status() == (
            psutil.STATUS_ZOMBIE
        )
        record = json.loads((prefix.parent / "record.json").read_text())
        assert Path(record["argv"][0]) == context.python
    finally:
        if process.poll() is None:
            process.send_signal(signal.SIGINT)
            process.communicate(timeout=10)

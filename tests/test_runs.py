import hashlib
import json
import os
import signal
import subprocess
import sys
import time

from nisayon import runs


def test_command_preserves_arguments_and_records_logs(workspace):
    literal = 'spaces; $(nothing) "quotes"'
    result = runs.run_command(
        workspace,
        [
            sys.executable,
            "-c",
            "import sys; print(sys.argv[1]); print('detail', file=sys.stderr)",
            literal,
        ],
        "literal",
    )
    assert result["process_status"] == "completed"
    assert result["scientific_status"] == "not_assessed"
    assert (
        result["logs"]["stdout.log"]["sha256"]
        == hashlib.sha256((literal + "\n").encode()).hexdigest()
    )
    assert runs.run_inspect(workspace, result["id"])["tails"]["stderr.log"] == "detail\n"


def test_failed_and_missing_commands_remain_distinct(workspace):
    failed = runs.run_command(workspace, [sys.executable, "-c", "raise SystemExit(7)"], "failure")
    missing = runs.run_command(workspace, ["/nonexistent/nisayon-test-command"], "missing")
    assert (failed["process_status"], failed["returncode"]) == ("nonzero", 7)
    assert missing["process_status"] == "spawn_error"
    assert len(runs.run_list(workspace)) == 2


def test_timeout_kills_child_that_ignores_term(workspace):
    child = "import signal,time; signal.signal(signal.SIGTERM, signal.SIG_IGN); time.sleep(30)"
    parent = (
        "import subprocess,sys,time; "
        f"p=subprocess.Popen([sys.executable,'-c',{child!r}]); "
        "print(p.pid,flush=True); time.sleep(30)"
    )
    result = runs.run_command(workspace, [sys.executable, "-c", parent], "timeout", timeout=0.6)
    assert result["process_status"] == "timeout"
    child_pid = int(runs.run_inspect(workspace, result["id"])["tails"]["stdout.log"].strip())
    # A killed orphan can briefly remain as a zombie awaiting the host's reaper.
    state = subprocess.run(
        ["ps", "-p", str(child_pid), "-o", "stat="], capture_output=True, text=True
    ).stdout.strip()
    assert not state or state.startswith("Z")


def test_keyboard_interrupt_leaves_completed_metadata(workspace):
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "nisayon.cli",
            "run",
            "--label",
            "interrupt",
            "--",
            sys.executable,
            "-c",
            "import time; time.sleep(30)",
        ],
        cwd=workspace,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
    )
    try:
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            records = runs.run_list(workspace)
            if records and records[0].get("pid"):
                break
            time.sleep(0.02)
        else:
            raise AssertionError("Command did not start")
        os.kill(process.pid, signal.SIGINT)
        stdout, stderr = process.communicate(timeout=5)
        assert process.returncode == 1, stderr
        result = json.loads(stdout)
        assert result["process_status"] == "interrupted"
        assert result["ended_at"]
        assert runs.run_list(workspace)[0]["process_status"] == "interrupted"
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()

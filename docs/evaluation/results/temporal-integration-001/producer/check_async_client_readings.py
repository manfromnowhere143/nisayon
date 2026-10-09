"""Check, by parsing the pinned LeRobot async client, the structural facts behind the
reachability readings in qualification.json. Nothing is executed or imported.

Facts checked on src/lerobot/async_inference/robot_client.py at 5aa74557 (sha256 pinned):
1. RobotClient.start() calls self.stub.Ready before sending policy instructions.
2. self.latest_action is assigned only in __init__ (to -1) and in control_loop_action:
   there is no in-process reset of the timestep identity.
3. _aggregate_action_queues builds a fresh Queue and iterates over incoming_actions only,
   then assigns it to self.action_queue: queued actions the incoming chunk does not cover
   are dropped, and overlapping steps take the arriving action by default.
4. receive_actions makes one self.stub.GetActions call per loop iteration and no other
   receiver exists: chunks arrive in production order.
5. control_loop_observation stamps the observation with time.time() and timestep
   max(latest_action, 0): the wire identity is a client wall-clock stamp and a step.

Usage: check_async_client_readings.py PATH_TO_robot_client.py OUT_DIR
"""

from __future__ import annotations

import ast
import hashlib
import json
import sys
from pathlib import Path

PINNED_SHA256 = "804f850e87d444b49f5b182d794ef1e9af2f059e0e95369f633fe8d15d5db5fb"


def method(tree: ast.Module, cls: str, name: str) -> ast.FunctionDef | None:
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == cls:
            for item in node.body:
                if isinstance(item, ast.FunctionDef) and item.name == name:
                    return item
    return None


def calls(node: ast.AST) -> list[str]:
    names = []
    for sub in ast.walk(node):
        if isinstance(sub, ast.Call):
            names.append(ast.unparse(sub.func))
    return names


def assigned_attrs(node: ast.AST, attr: str) -> int:
    count = 0
    for sub in ast.walk(node):
        if isinstance(sub, ast.Assign):
            for target in sub.targets:
                if isinstance(target, ast.Attribute) and target.attr == attr:
                    count += 1
    return count


def main(argv: list[str]) -> int:
    path, out = Path(argv[1]), Path(argv[2])
    data = path.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    facts: dict[str, dict] = {
        "file_sha256": {
            "expected": PINNED_SHA256,
            "actual": digest,
            "holds": digest == PINNED_SHA256,
        }
    }
    tree = ast.parse(data.decode())
    start = method(tree, "RobotClient", "start")
    start_calls = calls(start) if start else []
    facts["1_start_calls_Ready_before_SendPolicyInstructions"] = {
        "holds": "self.stub.Ready" in start_calls
        and "self.stub.SendPolicyInstructions" in start_calls
        and start_calls.index("self.stub.Ready")
        < start_calls.index("self.stub.SendPolicyInstructions"),
        "calls": [c for c in start_calls if c.startswith("self.stub")],
    }
    assignments = {}
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == "RobotClient":
            for item in node.body:
                if isinstance(item, ast.FunctionDef):
                    n = assigned_attrs(item, "latest_action")
                    if n:
                        assignments[item.name] = n
    facts["2_latest_action_assigned_only_in_init_and_control_loop_action"] = {
        "holds": set(assignments) == {"__init__", "control_loop_action"},
        "assignments": assignments,
    }
    agg = method(tree, "RobotClient", "_aggregate_action_queues")
    loops = [n for n in ast.walk(agg) if isinstance(n, ast.For)] if agg else []
    loop_iters = [ast.unparse(loop.iter) for loop in loops]
    agg_src = ast.unparse(agg) if agg else ""
    facts["3_aggregation_rebuilds_the_queue_from_incoming_actions_only"] = {
        "holds": loop_iters == ["incoming_actions"]
        and "future_action_queue = Queue()" in agg_src
        and "self.action_queue = future_action_queue" in agg_src
        and "return x2" in agg_src,
        "loop_iterables": loop_iters,
    }
    recv = method(tree, "RobotClient", "receive_actions")
    recv_calls = calls(recv) if recv else []
    whiles = [n for n in ast.walk(recv) if isinstance(n, ast.While)] if recv else []
    facts["4_single_sequential_receiver"] = {
        "holds": recv_calls.count("self.stub.GetActions") == 1
        and len(whiles) == 1
        and ast.unparse(whiles[0].test) == "self.running"
        and not any("Thread" in c or "Pool" in c for c in recv_calls),
        "GetActions_calls": recv_calls.count("self.stub.GetActions"),
    }
    obs = method(tree, "RobotClient", "control_loop_observation")
    obs_src = ast.unparse(obs) if obs else ""
    facts["5_observation_identity_is_wall_stamp_and_step"] = {
        "holds": "timestamp=time.time()" in obs_src and "timestep=max(latest_action, 0)" in obs_src,
    }
    cl = method(tree, "RobotClient", "control_loop")
    cl_src = ast.unparse(cl) if cl else ""
    facts["6_control_loop_has_no_reset_path"] = {
        "holds": "reset" not in cl_src.lower(),
    }
    result = {
        "schema": "nisayon.temporal-integration.async-client-readings.v1",
        "file": str(path),
        "facts": facts,
        "all_hold": all(f["holds"] for f in facts.values()),
        "scope": "structural facts parsed from the pinned bytes; nothing executed; they support the reachability readings in qualification.json and prove nothing about behavior under other callers",
    }
    out.mkdir(parents=True, exist_ok=True)
    (out / "async-client-readings.json").write_text(json.dumps(result, indent=2) + "\n")
    for name, fact in facts.items():
        print(f"{'ok ' if fact['holds'] else 'BAD'} {name}")
    return 0 if result["all_hold"] else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

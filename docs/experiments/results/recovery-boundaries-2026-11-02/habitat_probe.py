"""Real Torch, unchanged source-extracted Habitat methods; no Habitat rollout."""

import ast
import copy
import hashlib
import inspect
import json
import logging
import math
from pathlib import Path

import torch
from torch import nn, optim

HERE = Path(__file__).resolve().parent
SOURCES = {
    "base": HERE / "records/habitat-5.py.txt",
    "candidate": HERE / "records/habitat-3.py.txt",
}
SOURCE_DIGESTS = {
    "habitat-5.py.txt": "639063d9adc1aa8d2bfdd0054958177edd362d90ed43cd2be05c74a2436c3ecf",
    "habitat-3.py.txt": "5cd9200bf2072511e307e33644988f1dbd9fa85de6e1dc930a83852a77070e50",
}


def methods(source):
    if hashlib.sha256(source.read_bytes()).hexdigest() != SOURCE_DIGESTS[source.name]:
        raise ValueError("Habitat source bytes differ from the qualified revision")
    tree = ast.parse(source.read_text())
    ppo = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "PPO")
    selected = [
        node
        for node in ppo.body
        if isinstance(node, ast.FunctionDef) and node.name in {"before_step", "_create_optimizer"}
    ]
    assert len(selected) == 2 and all(not node.decorator_list for node in selected)
    namespace = dict(
        torch=torch, nn=nn, optim=optim, inspect=inspect, logger=logging.getLogger("probe")
    )
    exec(compile(ast.Module(body=selected, type_ignores=[]), str(source), "exec"), namespace)
    return {node.name: namespace[node.name] for node in selected}


class Actor(nn.Module):
    def __init__(self):
        super().__init__()
        self.policy = nn.Parameter(torch.tensor([0.4, -0.2], dtype=torch.float64))
        self.auxiliary = nn.Parameter(torch.tensor([0.3], dtype=torch.float64))

    def policy_parameters(self):
        return [self.policy]

    def aux_loss_parameters(self):
        return {"aux": [self.auxiliary]}


class Fixture(nn.Module):
    def __init__(self, source="candidate", optimizer="adam"):
        super().__init__()
        self.actor_critic = Actor()
        self.coefficient = nn.Parameter(torch.tensor([0.1], dtype=torch.float64))
        self.non_ac_params = [self.coefficient]
        self.max_grad_norm = 0.5
        extracted = methods(SOURCES[source])
        self.before_step = extracted["before_step"].__get__(self)
        self.optimizer = (
            extracted["_create_optimizer"](self, lr=0.01, eps=1e-5)
            if optimizer == "adam"
            else optim.SGD(self.parameters(), lr=0.01)
        )


def finite_grads(model, scale=1.0):
    for index, parameter in enumerate(model.parameters()):
        parameter.grad = torch.full_like(parameter, scale * 0.1 * (index + 1))


def advance(model):
    norm = model.before_step()
    model.optimizer.step()
    return float(norm)


def snapshot(model):
    return copy.deepcopy(
        {"parameters": model.state_dict(), "optimizer": model.optimizer.state_dict()}
    )


def equal(left, right):
    if isinstance(left, torch.Tensor):
        return (
            isinstance(right, torch.Tensor)
            and left.dtype == right.dtype
            and torch.equal(left, right)
        )
    if isinstance(left, dict):
        return left.keys() == right.keys() and all(equal(left[k], right[k]) for k in left)
    if isinstance(left, (list, tuple)):
        return (
            type(left) is type(right)
            and len(left) == len(right)
            and all(equal(a, b) for a, b in zip(left, right, strict=True))
        )
    return left == right


def restore(model, state):
    model.load_state_dict(copy.deepcopy(state["parameters"]))
    model.optimizer.load_state_dict(copy.deepcopy(state["optimizer"]))


def probe(source="candidate", fault="nan", group="policy", optimizer="adam", warm=True, guard=None):
    model = Fixture(source, optimizer)
    if warm:
        for i in range(3):
            finite_grads(model, scale=i + 1)
            advance(model)
    before = snapshot(model)
    reference = Fixture(source, optimizer)
    restore(reference, before)
    for parameter in model.parameters():
        parameter.grad = torch.zeros_like(parameter)
    target = {
        "policy": model.actor_critic.policy,
        "auxiliary": model.actor_critic.auxiliary,
        "coefficient": model.coefficient,
    }[group]
    target.grad.flatten()[0] = float(fault)
    refused = False
    norm = None
    try:
        if guard is not None:
            guard(model)
        norm = advance(model)
    except FloatingPointError:
        refused = True
    after = snapshot(model)
    deltas = [
        float((before["parameters"][k] - v).abs().max()) for k, v in after["parameters"].items()
    ]
    delta = max(deltas) if all(math.isfinite(value) for value in deltas) else "nonfinite"
    result = {
        "source": source,
        "source_sha256": hashlib.sha256(SOURCES[source].read_bytes()).hexdigest(),
        "fault": fault,
        "group": group,
        "optimizer": optimizer,
        "warm": warm,
        "guard": guard is not None,
        "refused": refused,
        "weights_finite": all(bool(torch.isfinite(p).all()) for p in model.parameters()),
        "parameters_unchanged": equal(before["parameters"], after["parameters"]),
        "optimizer_unchanged": equal(before["optimizer"], after["optimizer"]),
        "max_parameter_delta": delta,
        "reported_grad_norm": norm
        if norm is None or abs(norm) != float("inf") and norm == norm
        else str(norm),
        "step_counters": [
            float(v["step"]) for v in after["optimizer"]["state"].values() if "step" in v
        ],
    }
    for branch in (model, reference):
        finite_grads(branch, scale=0.7)
        advance(branch)
    result["next_update_matches_skipped_reference"] = equal(snapshot(model), snapshot(reference))
    return result


if __name__ == "__main__":
    rows = [
        probe(source=source, fault=fault, group=group)
        for source in SOURCES
        for fault in ("nan", "inf", "-inf")
        for group in ("policy", "auxiliary", "coefficient")
    ]
    rows += [probe(optimizer="sgd", warm=False)]
    print(
        json.dumps(
            {"torch": torch.__version__, "scope": "source-extracted methods on CPU", "rows": rows},
            indent=2,
            allow_nan=False,
        )
    )

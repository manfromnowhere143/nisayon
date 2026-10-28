"""Finite exposed camera contracts, shared by ordinary Python and the SDK.

The reference specifies pixels, masks and documented placeholder budgets. It
does not execute a learned policy or supply deployment outcome authority.
"""

from __future__ import annotations

import hashlib
from types import SimpleNamespace

import torch

KEYS = tuple(f"observation.images.{name}" for name in ("front", "wrist", "side"))
POLICIES = ("pi0", "pi05", "pi0_fast", "smolvla", "xvla", "evo1")
MODES = ("configured_budget", "all_configured_slots")


def conditions():
    for policy in POLICIES:
        layouts = ["bchw"]
        if policy in ("pi0", "pi05", "pi0_fast"):
            layouts.append("bhwc")
        if policy == "pi05":
            layouts += ["btchw", "bthwc"]
        elif policy in ("smolvla", "xvla", "evo1"):
            layouts.append("btchw")
        budgets = (0, 1, 3) if policy in ("smolvla", "evo1") else (3,)
        for layout in layouts:
            for budget in budgets:
                for subset in range(8):
                    for reverse in (False, True):
                        yield {
                            "id": f"{policy}-{layout}-b{budget}-s{subset}-r{int(reverse)}",
                            "policy": policy,
                            "layout": layout,
                            "budget": budget,
                            "subset": subset,
                            "reverse": reverse,
                        }


def tensor_record(value):
    value = value.detach().cpu().contiguous()
    return {
        "shape": list(value.shape),
        "dtype": str(value.dtype),
        "sha256": hashlib.sha256(value.numpy().tobytes()).hexdigest(),
    }


def make_batch(condition, seed):
    layout = condition["layout"]
    temporal = layout.startswith("bt")
    pairs = []
    for slot, key in enumerate(KEYS):
        if not condition["subset"] & (1 << slot):
            continue
        generator = torch.Generator(device="cpu").manual_seed(seed + slot * 101)
        shape = (2, 3, 3, 8, 10) if temporal else (2, 3, 8, 10)
        frame = torch.randint(0, 256, shape, generator=generator).to(torch.float32) / 255
        if layout == "bhwc":
            frame = frame.permute(0, 2, 3, 1)
        elif layout == "bthwc":
            frame = frame.permute(0, 1, 3, 4, 2)
        pairs.append((key, frame))
        if condition["policy"] == "pi05" and temporal:
            pad = torch.tensor([[False, slot % 2 == 0, False], [True, False, slot == 2]])
            pairs.append((f"{key}_is_pad", pad))
        if condition["policy"] == "smolvla":
            pairs.append((f"{key}_padding_mask", torch.tensor([slot != 1, slot != 2])))
    return dict(reversed(pairs) if condition["reverse"] else pairs)


def expected(condition, batch, mode):
    policy = condition["policy"]
    present = [slot for slot, key in enumerate(KEYS) if key in batch]
    missing = 3 - len(present)
    if not present or (policy == "evo1" and missing > condition["budget"]):
        return {"error": "ValueError", "input_unchanged": True}
    images, masks = [], []
    template = batch[KEYS[present[0]]]
    if policy in ("smolvla", "xvla", "evo1") and template.ndim == 5:
        template = template[:, -1]
    pad_value = 0 if policy in ("xvla", "evo1") else -1
    mask_shape = (2, 3) if policy == "pi05" and template.ndim == 5 else (2,)
    placeholders = 0
    for slot, key in enumerate(KEYS):
        if key in batch:
            value = batch[key]
            if policy in ("smolvla", "xvla", "evo1") and value.ndim == 5:
                value = value[:, -1]
            if policy not in ("xvla", "evo1"):
                value = value * 2 - 1
            images.append(value)
            if policy == "smolvla":
                masks.append(batch[f"{key}_padding_mask"].bool())
            elif policy == "pi05" and value.ndim == 5:
                masks.append(~batch[f"{key}_is_pad"].bool())
            else:
                masks.append(torch.ones(mask_shape, dtype=torch.bool))
        else:
            if policy == "smolvla" and mode == "configured_budget":
                if placeholders >= condition["budget"]:
                    continue
                placeholders += 1
            if policy != "evo1" or slot < max(present):
                images.append(torch.full_like(template, pad_value))
            masks.append(torch.zeros(mask_shape, dtype=torch.bool))
    return {
        "images": [tensor_record(x) for x in images],
        "masks": [{"shape": list(x.shape), "values": x.tolist()} for x in masks],
        "input_unchanged": True,
    }


def invoke(condition, batch, method):
    config = SimpleNamespace(
        image_features=dict.fromkeys(KEYS),
        image_resolution=(8, 10),
        resize_imgs_with_padding=None,
        empty_cameras=condition["budget"],
        num_image_views=3,
        max_views=3,
    )
    policy = SimpleNamespace(
        config=config, parameters=lambda: iter([torch.zeros(1)]), _camera_keys=list(KEYS)
    )
    before = {key: tensor_record(value) for key, value in batch.items()}
    try:
        images, masks = method(policy, batch)
        if condition["policy"] == "xvla":
            images, masks = list(images.unbind(1)), list(masks.unbind(1))
        elif condition["policy"] == "evo1":
            masks = list(masks.unbind(1))
        result = {
            "images": [tensor_record(x) for x in images],
            "masks": [{"shape": list(x.shape), "values": x.tolist()} for x in masks],
        }
    except ValueError:
        result = {"error": "ValueError"}
    result["input_unchanged"] = before == {
        key: tensor_record(value) for key, value in batch.items()
    }
    return result


def evaluate(value, methods=None):
    assert set(value) == {"seed", "mode", "scope"}, "Unexpected probe field"
    assert type(value["seed"]) is int and value["seed"] in (17, 67)
    assert value["mode"] in MODES
    assert value["scope"] in ("all", "changed_three")
    torch.set_num_threads(1)
    records = []
    for condition in conditions():
        if value["scope"] == "changed_three" and condition["policy"] not in (
            "pi0",
            "pi05",
            "smolvla",
        ):
            continue
        batch = make_batch(condition, value["seed"])
        row = (
            expected(condition, batch, value["mode"])
            if methods is None
            else invoke(condition, batch, methods[condition["policy"]])
        )
        records.append({"id": condition["id"], **row})
    return {"conditions": records}


def reference(value):
    return evaluate(value)

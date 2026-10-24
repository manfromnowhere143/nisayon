"""Contract observations; independent Beta oracle and rectangle/label checks.

No supplied Kornia implementation is edited. Full precision is compared with
the exact supplied upstream base; half precision has its own scalar oracle.
"""

import hashlib
import json
import math

from observer import observe, serialize
from scope import validate_conditions


def safe(value):
    if isinstance(value, float) and not math.isfinite(value):
        return str(value)
    if isinstance(value, dict):
        return {k: safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [safe(v) for v in value]
    return value


def digest(value):
    return hashlib.sha256(
        json.dumps(safe(value), sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


def tensor(row, torch):
    return torch.tensor(row["values"], dtype=getattr(torch, row["dtype"].split(".")[-1]))


def obligations(c, row, torch):
    p = {k: tensor(v, torch) for k, v in row["params"].items()}
    b, channels, h, w = c["shape"]
    m = c.get("num_mix", 1)
    same = c.get("same_on_batch", False)
    patch = c["kind"] == "patchmix"
    pairs = p["mix_pairs"]
    expected_pair_shape = [b] if patch else [m, b]
    result = {
        "finite_parameters": all(bool(torch.isfinite(v).all()) for v in p.values()),
        "pair_shape": list(pairs.shape) == expected_pair_shape,
        "pair_permutation": bool(
            torch.equal(pairs.sort(dim=-1).values, torch.arange(b).expand(pairs.shape))
        ),
        "pair_dtype": pairs.dtype == torch.int64,
    }
    # Reproduce only the documented pairing convention, using native Torch RNG
    # primitives, independently of Kornia's sampling helpers.
    dtype = getattr(torch, c["dtype"])
    torch.manual_seed(c["seed"])
    if not patch:
        torch.distributions.Bernoulli(torch.tensor(1.0, dtype=dtype)).sample(
            (1 if same else b * m,)
        )
    dist = torch.distributions.Uniform(
        torch.tensor(0.0, dtype=dtype), torch.tensor(1.0, dtype=dtype)
    )
    expected_pairs = dist.sample((b,) if patch else (m, b)).to(torch.float32).argsort(dim=-1)
    result["native_pairing_convention"] = bool(torch.equal(pairs, expected_pairs))
    if patch:
        coords, lam = p["patch_coords"], p["lam"]
        size = c["patch_size"]
        result.update(
            {
                "geometry_shape": list(coords.shape) == [b, 2],
                "coefficient_shape": list(lam.shape) == [b],
                "geometry_bounds": bool(
                    ((coords >= 0) & (coords <= torch.tensor([w - size, h - size]))).all()
                ),
                "integer_geometry": coords.dtype == torch.int64,
                "coefficient_bounds": bool(((lam >= 0) & (lam <= 1)).all()),
                "shared_geometry": not same
                or bool(torch.equal(coords, coords[:1].expand_as(coords))),
                "shared_coefficients": not same or bool(torch.equal(lam, lam[:1].expand_as(lam))),
            }
        )
    else:
        crop = p["crop_src"]
        x0, y0 = crop[..., 0, 0], crop[..., 0, 1]
        x1, y1 = crop[..., 2, 0], crop[..., 2, 1]
        widths, heights = x1 - x0 + 1, y1 - y0 + 1
        result.update(
            {
                "geometry_shape": list(crop.shape) == [m, b, 4, 2],
                "image_shape": p["image_shape"].tolist() == [h, w],
                "integer_geometry": bool(torch.equal(crop, crop.floor())),
                "geometry_bounds": bool(
                    (
                        (widths >= 0)
                        & (heights >= 0)
                        & (widths <= w)
                        & (heights <= h)
                        & (x0 >= 0)
                        & (y0 >= 0)
                        & (x0 <= w - widths)
                        & (y0 <= h - heights)
                    ).all()
                ),
                "rectangle_vertices": bool(
                    torch.equal(crop[..., 1, 0], x1)
                    and torch.equal(crop[..., 1, 1], y0)
                    and torch.equal(crop[..., 3, 0], x0)
                    and torch.equal(crop[..., 3, 1], y1)
                ),
                "shared_geometry": not same or bool(torch.equal(crop, crop[:, :1].expand_as(crop))),
                "shared_coefficients": not same
                or bool(torch.equal(widths * heights, (widths * heights)[:, :1].expand_as(widths))),
            }
        )
        if c["kind"] == "module":
            before, after, output = (
                tensor(row[k], torch) for k in ("input", "input_after", "output")
            )
            labels, out_labels = tensor(row["labels"], torch), tensor(row["output_labels"], torch)
            expected = before.clone()
            # Each mix takes source pixels from the caller's original image;
            # later overlapping rectangles overwrite earlier destinations.
            for mix in range(m):
                for batch in range(b):
                    x, y = int(x0[mix, batch]), int(y0[mix, batch])
                    cw, ch = int(widths[mix, batch]), int(heights[mix, batch])
                    source = int(pairs[mix, batch])
                    expected[batch, :, y : y + ch, x : x + cw] = before[
                        source, :, y : y + ch, x : x + cw
                    ]
            class_dtype = torch.float64 if dtype == torch.float64 else torch.float32
            expected_lambda = 1 - widths.to(class_dtype) * heights.to(class_dtype) / (h * w)
            result.update(
                {
                    "output_shape_dtype": output.shape == before.shape
                    and output.dtype == before.dtype,
                    "caller_input_preserved": bool(torch.equal(before, after)),
                    "rectangle_copy_semantics": bool(torch.equal(output, expected)),
                    "class_shape_dtype": list(out_labels.shape) == [m, b, 3]
                    and out_labels.dtype == class_dtype,
                    "original_class_ids": bool(
                        torch.equal(out_labels[..., 0], labels.to(class_dtype).expand(m, b))
                    ),
                    "permuted_class_ids": bool(
                        torch.equal(out_labels[..., 1], labels[pairs].to(class_dtype))
                    ),
                    "correct_area_lambda": bool(torch.equal(out_labels[..., 2], expected_lambda)),
                    "finite_outputs": bool(
                        torch.isfinite(output).all() and torch.isfinite(out_labels).all()
                    ),
                }
            )
    return result


def expected_obligations(c):
    keys = [
        "finite_parameters",
        "pair_shape",
        "pair_permutation",
        "pair_dtype",
        "native_pairing_convention",
        "geometry_shape",
        "geometry_bounds",
        "integer_geometry",
        "shared_geometry",
        "shared_coefficients",
    ]
    keys += (
        ["coefficient_shape", "coefficient_bounds"]
        if c["kind"] == "patchmix"
        else ["image_shape", "rectangle_vertices"]
    )
    if c["kind"] == "module":
        keys += [
            "output_shape_dtype",
            "caller_input_preserved",
            "rectangle_copy_semantics",
            "class_shape_dtype",
            "original_class_ids",
            "permuted_class_ids",
            "correct_area_lambda",
            "finite_outputs",
        ]
    return dict.fromkeys(keys, True)


def projection(row):
    return {
        k: row[k]
        for k in ("params", "input", "input_after", "labels", "output", "output_labels")
        if k in row
    }


def run(value, native, reference=False):
    validate_conditions(value["conditions"])
    torch = native[0]
    result = []
    for c in value["conditions"]:
        full = c["dtype"] in ("float32", "float64")
        if reference:
            dtype = getattr(torch, c["dtype"]) if full else torch.float32
            concentration = torch.tensor(c["beta"], dtype=dtype)
            torch.manual_seed(c["seed"] + 1)
            draws = torch.distributions.Beta(concentration, concentration).sample((16,))
            item = {
                "id": c["id"],
                "status": "ok",
                "concentration1": serialize(concentration),
                "concentration0": serialize(concentration),
                "beta_draws": serialize(draws),
                "obligations": expected_obligations(c),
            }
            if full:
                row = observe(c, native)
                print(
                    json.dumps(
                        {"role": "reference_base", "observation": safe(row)}, allow_nan=False
                    )
                )
                if row["status"] != "ok":
                    raise AssertionError((c["id"], row))
                checks = obligations(c, row, torch)
                if not all(checks.values()):
                    raise AssertionError((c["id"], checks))
                item["full_precision_base_sha256"] = digest(projection(row))
        else:
            row = observe(c, native)
            print(json.dumps({"role": "observed", "observation": safe(row)}, allow_nan=False))
            item = {"id": c["id"], "status": row["status"]}
            if row["status"] == "ok":
                item.update(
                    {k: safe(row[k]) for k in ("concentration1", "concentration0", "beta_draws")}
                )
                item["obligations"] = obligations(c, row, torch)
                if full:
                    item["full_precision_base_sha256"] = digest(projection(row))
            else:
                item["error_type"], item["error"] = row["error_type"], row["error"]
        result.append(item)
    return {"conditions": result}

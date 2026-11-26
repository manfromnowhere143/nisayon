"""Independent NumPy readback. No LeRobot, Torch, simulator or model is imported."""
from __future__ import annotations
import argparse
import copy
import hashlib
import json
from pathlib import Path
import numpy as np

SCOPE = "native feature and request preparation only; no deployment acceptance"
A, B, STATE = "observation.images.image", "observation.images.image2", "observation.state"
CASES = ("all_supplied", "omit_synthetic", "missing_first_real", "missing_last_real",
         "missing_state", "unknown_feature", "bad_camera_shape", "bad_state_shape",
         "wrong_camera_kind", "duplicate_feature", "no_visual", "black_real",
         "reverse_request_keys", "request_missing", "request_extra", "request_dtype",
         "request_shape", "request_nan")
VARIANTS = ("original", "synthetic_only", "all_visual_optional")


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


def sha(a):
    return hashlib.sha256(a.tobytes(order="C")).hexdigest()


def expected(case, n, variant):
    accepted = {"all_supplied", "black_real", "reverse_request_keys"}
    if n == 0 or variant != "original":
        accepted.add("omit_synthetic")
    if variant == "all_visual_optional":
        accepted |= {"missing_first_real", "missing_last_real"}
    return case in accepted


def audit(rows, arrays, frozen, summary):
    assignment = [
        {"resolution": [h,w], "empty_cameras": n, "case": c, "variant": v,
         "expected_accept": expected(c,n,v)}
        for h,w in ((8,10),(256,256)) for n in (0,1,2) for c in CASES for v in VARIANTS
    ]
    require(frozen["assignment"] == assignment, "Frozen assignment/decisions differ")
    require(len(rows) == len(assignment), "Incomplete or duplicated rows")
    require(summary["scope"] == SCOPE, "Scope promoted")
    require(summary["confirmation"] == "32 fresh paired tasks not run", "Confirmation promoted")
    accepted = dict.fromkeys(VARIANTS, 0)
    expected_arrays = set()
    for i, (r,e) in enumerate(zip(rows,assignment)):
        require(r["index"] == i and all(r[k] == v for k,v in e.items()), "Assignment mismatch")
        require(type(r["accepted"]) is bool and r["accepted"] == e["expected_accept"], "Wrong decision")
        require(r["matches_frozen_expectation"] is True, "Producer reports mismatch")
        h,w = e["resolution"]
        n,case = e["empty_cameras"], e["case"]
        configured = [A,B] + [f"observation.images.empty_camera_{j}" for j in range(n)]
        names = [A,B,STATE] + configured[2:]
        if case == "omit_synthetic": names = [A,B,STATE]
        if case == "missing_first_real": names.remove(A)
        if case == "missing_last_real": names.remove(B)
        if case == "missing_state": names.remove(STATE)
        if case == "no_visual": names = [STATE]
        if case == "request_missing": names.remove(A)
        if case == "request_extra": names.append("unknown")
        expected_arrays |= {f"row{i}_input_{name}" for name in names}
        for name in names:
            key = f"row{i}_input_{name}"
            require(key in arrays, "Missing raw input")
        if not r["accepted"]:
            require(r["stage"] == ("request" if case.startswith("request_") else "negotiation"),
                    "Refusal at wrong boundary")
            require(r["exception_type"] == "ValueError" and bool(r["error"]), "Unclassified refusal")
            require("images" not in r and "direct_match" not in r, "Refused row carries success")
            continue
        accepted[e["variant"]] += 1
        require(r["stage"] == "complete" and r["direct_match"] is True, "Native direct comparison failed")
        require(len(r["images"]) == 2+n and len(r["masks"]) == 2+n, "Missing output")
        present = [name for name in configured if name in names]
        height,width = (224,224) if h == 256 else (h,w)
        for j in range(2+n):
            image_key,mask_key = f"row{i}_image{j}",f"row{i}_mask{j}"
            expected_arrays |= {image_key,mask_key}
            image,mask = arrays[image_key],arrays[mask_key]
            require(image.dtype == np.float32 and image.shape == (1,3,height,width), "Image type/shape")
            require(np.isfinite(image).all() and np.max(image)<=1 and np.min(image)>=-1, "Image range")
            require(mask.dtype == np.bool_ and mask.shape == (1,), "Mask type/shape")
            require(bool(mask[0]) == (j<len(present)), "Wrong mask semantics")
            for value,metadata in ((image,r["images"][j]),(mask,r["masks"][j])):
                require(metadata["sha256"] == sha(value)
                        and metadata["shape"] == list(value.shape)
                        and metadata["dtype"] == value.dtype.name, "Typed bytes mismatch")
                if value.size <= 16:
                    require(metadata["values"] == value.tolist(), "Scalar readback mismatch")
            if j >= len(present):
                require(np.all(image == -1), "Absent placeholder is not -1")
            else:
                source = arrays[f"row{i}_input_{present[j]}"]
                if source.shape[:2] == (height,width):
                    independent = (source.astype(np.float32)/np.float32(255)*np.float32(2)-np.float32(1))
                    require(np.array_equal(image, independent.transpose(2,0,1)[None]), "Pixel arithmetic")
                elif np.all(source == 0):
                    require(np.all(image == -1), "Black-image arithmetic")
                # Other resized images are retained native outputs. This checker
                # does not reimplement or independently certify bilinear resize.
    require(set(arrays.files if hasattr(arrays,"files") else arrays) == expected_arrays,
            "Raw array inventory differs")
    require(summary["rows"] == len(rows) and summary["accepted"] == sum(accepted.values())
            and summary["unexpected"] == 0 and summary["direct_mismatches"] == 0, "Summary differs")
    pairs = []
    for size in ([8,10],[256,256]):
        for n in (1,2):
            source = next(r for r in rows if r["resolution"]==size and r["empty_cameras"]==n
                          and r["case"]=="all_supplied" and r["variant"]=="original")
            target = next(r for r in rows if r["resolution"]==size and r["empty_cameras"]==n
                          and r["case"]=="omit_synthetic" and r["variant"]=="synthetic_only")
            require(source["images"] == target["images"], "Image bytes changed in mask-only comparison")
            require([m["values"] for m in source["masks"]] == [[True]]*(2+n), "Original mask")
            require([m["values"] for m in target["masks"]] == [[True]]*2+[[False]]*n, "Corrected mask")
            pairs.append([source["index"],target["index"]])
    return {"rows":len(rows), "accepted_by_variant":accepted,
            "mask_only_pairs":pairs, "scope":SCOPE,
            "independent_resize_reference":False, "execution_authenticity":False,
            "owner_acceptance":False, "task_confirmation":False}


def controls(rows, arrays, freeze, summary):
    def check(name, mutate):
        rr,ff,ss = copy.deepcopy(rows),copy.deepcopy(freeze),copy.deepcopy(summary)
        aa = dict(arrays)
        mutate(rr,aa,ff,ss)
        try:
            audit(rr,aa,ff,ss)
        except (ValueError,KeyError):
            return name
        raise RuntimeError("Mutation escaped: "+name)
    controls = []
    controls.append(check("missing row",lambda r,a,f,s:r.pop()))
    controls.append(check("duplicate row",lambda r,a,f,s:r.__setitem__(1,copy.deepcopy(r[0]))))
    controls.append(check("promoted deployment scope",lambda r,a,f,s:s.update(scope="deployment accepted")))
    controls.append(check("invented confirmation",lambda r,a,f,s:s.update(confirmation="confirmed")))
    controls.append(check("changed frozen decision",lambda r,a,f,s:f["assignment"][0].update(expected_accept=False)))
    controls.append(check("false native match",lambda r,a,f,s:r[0].update(direct_match=False)))
    controls.append(check("missing raw array",lambda r,a,f,s:a.pop("row0_image0")))
    target = next(r["index"] for r in rows if r["case"]=="omit_synthetic"
                  and r["empty_cameras"]==1 and r["variant"]=="synthetic_only")
    def mask(r,a,f,s):
        key=f"row{target}_mask2";a[key]=np.array([True],dtype=np.bool_)
        r[target]["masks"][2].update(sha256=sha(a[key]),values=[True])
    controls.append(check("wrong mask with rewritten digest",mask))
    def pixel(r,a,f,s):
        a["row0_image0"]=a["row0_image0"].copy();a["row0_image0"][0,0,0,0]=.5
        r[0]["images"][0]["sha256"]=sha(a["row0_image0"])
    controls.append(check("wrong pixel with rewritten digest",pixel))
    def decision(r,a,f,s):
        row=next(x for x in r if x["case"]=="missing_first_real" and x["variant"]=="synthetic_only")
        row["accepted"]=True
    controls.append(check("broadened narrow admission",decision))
    return controls


def main():
    p=argparse.ArgumentParser(__doc__);p.add_argument("packet",type=Path);p.add_argument("--fault-controls",action="store_true")
    args=p.parse_args();root=args.packet
    freeze=json.loads((root/"records/freeze-v2.json").read_text())
    for name,d in freeze["files"].items():
        require(hashlib.sha256((root/name).read_bytes()).hexdigest()==d,"Frozen file changed: "+name)
    run=root/"records/native-02";summary=json.loads((run/"summary.json").read_text())
    for name,field in (("rows.jsonl","rows_sha256"),("arrays.npz","arrays_sha256")):
        require(hashlib.sha256((run/name).read_bytes()).hexdigest()==summary[field],"Payload digest")
    require(hashlib.sha256((root/"records/freeze-v2.json").read_bytes()).hexdigest()==summary["freeze_sha256"],"Freeze digest")
    rows=[json.loads(s) for s in (run/"rows.jsonl").read_text().splitlines()]
    with np.load(run/"arrays.npz",allow_pickle=False) as archive:
        arrays={k:archive[k] for k in archive.files}
    result=audit(rows,arrays,freeze,summary)
    if args.fault_controls: result["fault_controls_refused"]=controls(rows,arrays,freeze,summary)
    print(json.dumps(result,indent=2))


if __name__=="__main__": main()

"""Inspect one captured OpenPI dependency graph without installing or importing it."""

from __future__ import annotations

import argparse
import hashlib
import json
import time
import tomllib
from pathlib import Path

import packaging
from packaging.markers import Marker, default_environment
from packaging.requirements import Requirement

COMMIT = "215abfb217dbac7d5f1273282331b9b1866c0479"


def audit(captures: Path) -> dict:
    started = time.perf_counter()
    ledger = json.loads((captures / "sources.json").read_text())
    required = {
        "openpi-uv-lock",
        "openpi-pyproject",
        "torch271-pypi",
        "cuda-plugin053-pypi",
    }
    inputs = {}
    for name in sorted(required):
        record = next(item for item in ledger if item["name"] == name)
        path = captures / Path(record["path"]).name
        data = path.read_bytes()
        assert hashlib.sha256(data).hexdigest() == record["sha256"], name
        assert len(data) == record["bytes"], name
        if name.startswith("openpi-"):
            assert f"/{COMMIT}/" in record["url"], name
        inputs[name] = data.decode()

    project = tomllib.loads(inputs["openpi-pyproject"])
    assert "jax[cuda12]==0.5.3" in project["project"]["dependencies"]
    assert "torch==2.7.1" in project["project"]["dependencies"]
    packages = tomllib.loads(inputs["openpi-uv-lock"])["package"]
    plugin = next(p for p in packages if p["name"] == "jax-cuda12-plugin")
    selections = {}
    environments = {}
    for arch in ("x86_64", "aarch64"):
        env = default_environment()
        env.update(
            platform_machine=arch,
            sys_platform="linux",
            platform_system="Linux",
            python_version="3.11",
            python_full_version="3.11.13",
        )
        environments[arch] = env
        selected = {}
        for dep in plugin["optional-dependencies"]["with-cuda"]:
            if "marker" in dep and not Marker(dep["marker"]).evaluate(env):
                continue
            matches = [
                p
                for p in packages
                if p["name"] == dep["name"]
                and ("version" not in dep or p["version"] == dep["version"])
                and (
                    not p.get("resolution-markers")
                    or any(Marker(m).evaluate(env) for m in p["resolution-markers"])
                )
            ]
            assert len(matches) == 1, (arch, dep["name"])
            selected[dep["name"]] = matches[0]["version"]
        selections[arch] = selected

    torch_metadata = json.loads(inputs["torch271-pypi"])["info"]
    assert torch_metadata["version"] == "2.7.1"
    torch_req = next(
        req
        for text in torch_metadata["requires_dist"]
        if (req := Requirement(text)).name == "nvidia-cudnn-cu12"
        and (not req.marker or req.marker.evaluate(environments["x86_64"]))
    )
    plugin_metadata = json.loads(inputs["cuda-plugin053-pypi"])["info"]
    assert plugin_metadata["version"] == plugin["version"] == "0.5.3"
    plugin_req = next(
        req
        for text in plugin_metadata["requires_dist"]
        if (req := Requirement(text)).name == "nvidia-cudnn-cu12"
    )
    checks = {
        "linux_x86_cudnn_and_runtime_pins": selections["x86_64"]["nvidia-cudnn-cu12"] == "9.5.1.17"
        and selections["x86_64"]["nvidia-cuda-runtime-cu12"] == "12.6.77",
        "linux_arm_selects_different_versions": selections["aarch64"]["nvidia-cudnn-cu12"]
        == "9.10.1.4"
        and selections["aarch64"]["nvidia-cuda-runtime-cu12"] == "12.9.37",
        "jax_plugin_permits_both_cudnn_versions": all(
            plugin_req.specifier.contains(v) for v in ("9.5.1.17", "9.7.1.26")
        ),
        "torch_exact_pin_rejects_single_cudnn_upgrade": str(torch_req.specifier) == "==9.5.1.17"
        and not torch_req.specifier.contains("9.7.1.26"),
    }
    assert all(checks.values()), checks
    return {
        "schema": "nisayon.openpi-lock-inspection.v1",
        "status": "static_dependency_findings_supported",
        "source_commit": COMMIT,
        "reporter_revision_verified": False,
        "packaging_version": packaging.__version__,
        "target_python": "3.11.13",
        "linux_platform_selections": selections,
        "torch_cudnn_requirement": str(torch_req),
        "jax_plugin_cudnn_requirement": str(plugin_req),
        "checks": checks,
        "limits": [
            "No dependency installation, resolver execution or GPU library import.",
            "Platform branches are inspected; neither platform is hardware-qualified.",
            "Vendor support matrices require separate source review.",
            "Reporter revision, installed/loaded libraries and driver remain unknown.",
            "No root cause, repaired training run or economic advantage is established.",
        ],
        "audit_wall_seconds": time.perf_counter() - started,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--captures", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    args.out.write_text(json.dumps(audit(args.captures), indent=2) + "\n")

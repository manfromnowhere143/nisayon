"""Inventory already-held policy-task assets under a frozen, zero-network screen."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import resource
import shutil
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from nisayon.engine.io import write_json

SCHEMA = "nisayon.policy-task-held-asset-inventory.v1"
CASE = "task-qualification-001"
CPU_LIMIT_SECONDS = 60
MAX_CANDIDATES = 12
MAX_HASH_BYTES = 32 * 1024**2

HOME = Path("/Users/danielwahnich")
WORKSPACE = HOME / "workspace"
CACHE = HOME / ".cache"
REPORTS = HOME / ".codex/reports"
LOCAL_SHARE = HOME / ".local/share"
HOMEBREW = Path("/opt/homebrew")

WEIGHT_SUFFIXES = {".bin", ".ckpt", ".pth", ".pt", ".safetensors"}
DATA_SUFFIXES = {".h5", ".hdf5", ".parquet"}
ROBOTICS_TERMS = (
    "act",
    "diffusion",
    "groot",
    "lerobot",
    "libero",
    "lift",
    "octo",
    "openvla",
    "robomimic",
    "robot",
    "smolvla",
    "vla",
)
PRUNE = {
    ".git",
    ".mypy_cache",
    ".nisayon",
    ".pytest_cache",
    ".ruff_cache",
    "__pycache__",
    "node_modules",
}


def _cpu_seconds(start_self: float, start_children: tuple[float, float]) -> float:
    children = resource.getrusage(resource.RUSAGE_CHILDREN)
    child_delta = (children.ru_utime - start_children[0]) + (children.ru_stime - start_children[1])
    return time.process_time() - start_self + child_delta


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _identity(path: Path, *, hash_large: bool = False) -> dict[str, Any]:
    target = path.resolve()
    stat = target.stat()
    result: dict[str, Any] = {
        "path": str(path),
        "resolved_path": str(target),
        "bytes": stat.st_size,
        "symlink": path.is_symlink(),
    }
    if stat.st_size <= MAX_HASH_BYTES or hash_large:
        result["sha256"] = _sha256(target)
    else:
        result["sha256"] = None
        result["digest_status"] = (
            f"not hashed during inventory because bytes exceed {MAX_HASH_BYTES}"
        )
    return result


def _walk_files(root: Path, *, max_depth: int | None) -> tuple[list[Path], dict[str, Any]]:
    matches: list[Path] = []
    visited_files = 0
    visited_directories = 0
    errors: list[dict[str, str]] = []
    if not root.exists():
        return matches, {
            "root": str(root),
            "exists": False,
            "visited_files": 0,
            "visited_directories": 0,
            "errors": [],
        }
    for current, directories, files in os.walk(root, followlinks=False):
        current_path = Path(current)
        depth = len(current_path.relative_to(root).parts)
        directories[:] = sorted(name for name in directories if name not in PRUNE)
        if max_depth is not None and depth >= max_depth:
            directories[:] = []
        visited_directories += 1
        for name in sorted(files):
            visited_files += 1
            path = current_path / name
            suffix = path.suffix.lower()
            lowered = str(path).lower()
            if suffix in WEIGHT_SUFFIXES or suffix in DATA_SUFFIXES:
                matches.append(path)
            elif name in {"config.json", "model_index.json", "README.md", "pyvenv.cfg"} and any(
                term in lowered for term in ROBOTICS_TERMS
            ):
                matches.append(path)
        if _current_cpu() >= CPU_LIMIT_SECONDS - 3:
            errors.append({"kind": "cpu_stop", "path": str(current_path)})
            directories[:] = []
            break
    return matches, {
        "root": str(root),
        "exists": True,
        "visited_files": visited_files,
        "visited_directories": visited_directories,
        "errors": errors,
    }


_START_SELF = 0.0
_START_CHILDREN = (0.0, 0.0)


def _current_cpu() -> float:
    return _cpu_seconds(_START_SELF, _START_CHILDREN)


def _package_inventory() -> list[dict[str, Any]]:
    environments: list[Path] = []
    for root in sorted(WORKSPACE.glob("*/.venv")):
        if (root / "pyvenv.cfg").is_file():
            environments.append(root)
    conda_root = HOME / ".conda/envs"
    for root in sorted(conda_root.glob("*")) if conda_root.is_dir() else []:
        if (root / "pyvenv.cfg").is_file() or (root / "conda-meta").is_dir():
            environments.append(root)

    packages = (
        "gym",
        "gymnasium",
        "libero",
        "lerobot",
        "mujoco",
        "robomimic",
        "robosuite",
        "torch",
        "transformers",
    )
    result: list[dict[str, Any]] = []
    for environment in environments:
        site_roots = sorted(environment.glob("lib/python*/site-packages"))
        discovered: dict[str, dict[str, Any]] = {}
        for site_root in site_roots:
            for package in packages:
                package_paths = sorted(site_root.glob(f"{package}*"))
                if not package_paths:
                    continue
                entries = [str(path) for path in package_paths]
                version = None
                license_text = None
                for metadata in sorted(
                    site_root.glob(f"{package.replace('-', '_')}*.dist-info/METADATA")
                ):
                    try:
                        for line in metadata.read_text(errors="replace").splitlines():
                            if line.startswith("Version: ") and version is None:
                                version = line.removeprefix("Version: ")
                            if line.startswith("License: ") and license_text is None:
                                license_text = line.removeprefix("License: ")
                    except OSError:
                        pass
                discovered[package] = {
                    "version": version,
                    "declared_license": license_text,
                    "paths": entries,
                }
        result.append(
            {
                "environment": str(environment),
                "python": str(environment / "bin/python"),
                "packages": discovered,
            }
        )
    return result


def _huggingface_models(files: list[Path]) -> list[dict[str, Any]]:
    grouped: dict[str, list[Path]] = {}
    hub = CACHE / "huggingface/hub"
    for path in files:
        try:
            relative = path.relative_to(hub)
        except ValueError:
            continue
        if not relative.parts or not relative.parts[0].startswith("models--"):
            continue
        grouped.setdefault(relative.parts[0], []).append(path)
    result: list[dict[str, Any]] = []
    for model, paths in sorted(grouped.items()):
        weight_paths = sorted(path for path in paths if path.suffix.lower() in WEIGHT_SUFFIXES)
        if not weight_paths:
            continue
        metadata_paths = sorted(path for path in paths if path.name in {"README.md", "config.json"})
        declared_license = None
        for readme in metadata_paths:
            if readme.name != "README.md":
                continue
            try:
                for line in readme.read_text(errors="replace")[:131072].splitlines():
                    if line.strip().lower().startswith("license:"):
                        declared_license = line.split(":", 1)[1].strip()
                        break
            except OSError:
                pass
        result.append(
            {
                "model_cache": model,
                "declared_license": declared_license,
                "weights": [_identity(path) for path in weight_paths],
                "metadata": [str(path) for path in metadata_paths],
            }
        )
    return result


def _docker_inventory() -> dict[str, Any]:
    executable = shutil.which("docker")
    sockets = [
        Path("/var/run/docker.sock"),
        HOME / ".docker/run/docker.sock",
        HOME / ".colima/default/docker.sock",
    ]
    reachable_socket = next((str(path) for path in sockets if path.exists()), None)
    result: dict[str, Any] = {
        "executable": executable,
        "reachable_socket": reachable_socket,
        "command_run": False,
        "images": [],
    }
    if executable is None or reachable_socket is None:
        return result
    completed = subprocess.run(
        [executable, "image", "ls", "--no-trunc", "--format", "{{json .}}"],
        capture_output=True,
        text=True,
        timeout=3,
        check=False,
        env={**os.environ, "DOCKER_CLI_HINTS": "false"},
    )
    result.update(
        {
            "command_run": True,
            "returncode": completed.returncode,
            "stderr": completed.stderr[:4096],
            "images": [
                json.loads(line)
                for line in completed.stdout.splitlines()
                if line.strip().startswith("{")
            ],
        }
    )
    return result


def _candidate_priority(path: Path) -> tuple[int, str]:
    lowered = str(path).lower()
    if "lift_ph_low_dim_epoch_1000_succ_100.pth" in lowered:
        return (0, lowered)
    if any(term in lowered for term in ROBOTICS_TERMS):
        return (1, lowered)
    return (2, lowered)


def inventory() -> dict[str, Any]:
    scans: list[dict[str, Any]] = []
    files: list[Path] = []

    discovered, reading = _walk_files(WORKSPACE, max_depth=3)
    files.extend(discovered)
    scans.append({**reading, "declared_scope": "workspace depth 3"})

    for cache_root in (CACHE / "huggingface", CACHE / "lerobot", CACHE / "torch"):
        discovered, reading = _walk_files(cache_root, max_depth=None)
        files.extend(discovered)
        scans.append({**reading, "declared_scope": "model and dataset cache"})

    discovered, reading = _walk_files(REPORTS, max_depth=None)
    files.extend(discovered)
    scans.append({**reading, "declared_scope": "retained assignment packets, read-only"})

    discovered, reading = _walk_files(LOCAL_SHARE, max_depth=5)
    files.extend(discovered)
    scans.append({**reading, "declared_scope": "installed local shared assets, depth 5"})

    # Homebrew is large and does not hold policy checkpoints in this installation. Record
    # only robotics-relevant paths within the opt prefix and executable identities.
    brew_paths = []
    for name in ("mujoco", "mujoco-py", "robosuite", "libero", "docker"):
        candidates = (
            [
                *HOMEBREW.glob(f"Cellar/{name}*"),
                *HOMEBREW.glob(f"opt/{name}*"),
                *HOMEBREW.glob(f"bin/{name}*"),
            ]
            if HOMEBREW.exists()
            else []
        )
        for path in sorted(candidates)[:20]:
            brew_paths.append(str(path))
    scans.append(
        {
            "root": str(HOMEBREW),
            "exists": HOMEBREW.exists(),
            "declared_scope": "robotics-relevant installed paths and executables",
            "matches": sorted(set(brew_paths)),
            "visited_files": None,
            "visited_directories": None,
            "errors": [],
        }
    )

    unique_files = sorted({path for path in files if path.exists()}, key=lambda item: str(item))
    checkpoint_files = [path for path in unique_files if path.suffix.lower() in WEIGHT_SUFFIXES]
    data_files = [path for path in unique_files if path.suffix.lower() in DATA_SUFFIXES]

    selected_checkpoint_paths = sorted(checkpoint_files, key=_candidate_priority)[:MAX_CANDIDATES]
    selected_checkpoint_identities = [_identity(path) for path in selected_checkpoint_paths]
    omitted_checkpoint_count = max(0, len(checkpoint_files) - MAX_CANDIDATES)

    prior_receipt = Path("artifacts/normalizer-execution-001/private-main-closeout-001.json")
    disk = shutil.disk_usage(Path.cwd())
    result = {
        "schema": SCHEMA,
        "case": CASE,
        "recorded_at": datetime.now(UTC).isoformat(),
        "host": {
            "platform": platform.platform(),
            "machine": platform.machine(),
            "python": platform.python_version(),
            "logical_cpus": os.cpu_count(),
        },
        "selection_rule": {
            "commit": "d673b603a53bf6470c6aa5f88e6929846ab52c28",
            "sha256": "b28898b3c9560f81ca5c2ee6b3901985691e0e1be5559db204c4e6680540d8ad",
            "maximum_candidates": MAX_CANDIDATES,
            "process_cpu_cap_seconds": CPU_LIMIT_SECONDS,
        },
        "network_requests": 0,
        "new_source_bytes": 0,
        "new_dependency_bytes": 0,
        "root_scans": scans,
        "checkpoints_found": len(checkpoint_files),
        "checkpoint_candidates": selected_checkpoint_identities,
        "checkpoint_candidates_omitted_by_cap": omitted_checkpoint_count,
        "task_data_files": [
            {
                "path": str(path),
                "resolved_path": str(path.resolve()),
                "bytes": path.resolve().stat().st_size,
            }
            for path in data_files[:64]
        ],
        "task_data_files_omitted": max(0, len(data_files) - 64),
        "huggingface_models_with_weights": _huggingface_models(selected_checkpoint_paths),
        "python_environments": _package_inventory(),
        "docker": _docker_inventory(),
        "disk_preflight": {
            "free_bytes": disk.free,
            "minimum_free_bytes": 5 * 1024**3,
            "total_bytes": disk.total,
            "prior_closeout_receipt": _identity(prior_receipt),
        },
        "cost": {
            "process_cpu_seconds_before_write": _current_cpu(),
            "outer_wall_seconds_before_write": time.perf_counter() - _START_WALL,
            "process_cpu_cap_seconds": CPU_LIMIT_SECONDS,
            "waiting_time_included_as_effort": False,
        },
        "limits": {
            "candidate_cap_respected": len(selected_checkpoint_identities) <= MAX_CANDIDATES,
            "cpu_cap_respected_before_write": _current_cpu() <= CPU_LIMIT_SECONDS,
            "disk_floor_respected": disk.free > 5 * 1024**3,
        },
    }
    return result


_START_WALL = 0.0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    global _START_SELF, _START_CHILDREN, _START_WALL
    usage = resource.getrusage(resource.RUSAGE_CHILDREN)
    _START_CHILDREN = (usage.ru_utime, usage.ru_stime)
    _START_SELF = time.process_time()
    _START_WALL = time.perf_counter()
    resource.setrlimit(resource.RLIMIT_CPU, (CPU_LIMIT_SECONDS, CPU_LIMIT_SECONDS + 1))

    if args.out.exists():
        raise FileExistsError(f"Refusing to overwrite inventory: {args.out}")
    result = inventory()
    if result["cost"]["process_cpu_seconds_before_write"] > CPU_LIMIT_SECONDS:
        raise RuntimeError("Inventory CPU cap exceeded")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    write_json(args.out, result)
    print(json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

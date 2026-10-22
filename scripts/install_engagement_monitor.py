"""Install or remove the authorized read-only Nisayon LaunchAgent on macOS."""

from __future__ import annotations

import argparse
import os
import plistlib
import shutil
import subprocess
import sys
from pathlib import Path

from nisayon import engagements, workspace


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["install", "remove"])
    args = parser.parse_args()
    root = workspace.project_root()
    common = Path(workspace.git(root, "rev-parse", "--path-format=absolute", "--git-common-dir"))
    if sys.platform != "darwin" or common.resolve().parent != root:
        raise ValueError("Install from the canonical macOS checkout only")
    gh = shutil.which("gh")
    python = root / ".venv/bin/python"
    if not gh or not python.exists():
        raise ValueError("Existing gh and project Python are required")
    config = engagements.registry(root)
    label = "org.nisayon.engagement-monitor"
    target = f"gui/{os.getuid()}/{label}"
    folder = engagements.store_path(root)
    folder.mkdir(parents=True, exist_ok=True)
    path = Path.home() / "Library/LaunchAgents" / f"{label}.plist"
    data = {
        "Label": label,
        "ProgramArguments": [str(python), "-m", "nisayon.cli", "engagements", "scan"],
        "WorkingDirectory": str(root),
        "EnvironmentVariables": {
            "PATH": str(Path(gh).parent) + ":/usr/bin:/bin:/usr/sbin:/sbin",
            "PYTHONPATH": str(root / "src"),
            "PYTHONDONTWRITEBYTECODE": "1",
        },
        "StartInterval": config["interval_seconds"],
        "RunAtLoad": True,
        "ProcessType": "Background",
        "StandardOutPath": str(folder / "launchd.stdout.log"),
        "StandardErrorPath": str(folder / "launchd.stderr.log"),
    }
    if path.exists() and plistlib.loads(path.read_bytes()) != data:
        raise ValueError("Existing LaunchAgent differs; inspect it before replacement")
    loaded = (
        subprocess.run(["launchctl", "print", target], capture_output=True, check=False).returncode
        == 0
    )
    if args.action == "remove":
        if loaded:
            subprocess.run(["launchctl", "bootout", target], check=True)
        path.unlink(missing_ok=True)
        print("Removed Nisayon engagement monitor; retained local evidence and reviews.")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        with path.open("xb") as output:
            plistlib.dump(data, output)
    if not loaded:
        subprocess.run(["launchctl", "bootstrap", f"gui/{os.getuid()}", str(path)], check=True)
    print(
        f"Installed {label}: read-only scan every {config['interval_seconds']} seconds while logged in."
    )


if __name__ == "__main__":
    main()

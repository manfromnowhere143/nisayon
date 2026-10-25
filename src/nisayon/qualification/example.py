"""Create the exposed software example without a source checkout or execution."""

from importlib.resources import files
from pathlib import Path


def create_example(destination: str | Path) -> dict:
    """Copy public demonstration inputs into a new directory; never replace user files."""
    root = Path(destination).absolute()
    source = files("nisayon.qualification").joinpath("example_data")
    # Read the installed resources before creating any destination.
    contents = {
        name: source.joinpath(name).read_bytes()
        for name in ("case.json", "policy.py", "sdk_example.py")
    }
    root.mkdir(parents=True, exist_ok=False)
    for name, raw in contents.items():
        with (root / name).open("xb") as output:
            output.write(raw)
    return {
        "example": str(root),
        "files": sorted(contents),
        "execution": "not_started",
        "scope": "Two exposed normalization vectors, not a robot or learned-policy benchmark.",
    }

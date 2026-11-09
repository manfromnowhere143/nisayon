"""Validate an exported generation without simulator dependencies."""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from nisayon.ui_export.validate import validate_generation  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument(
        "--sha256", help="open this immutable generation, independently of discovery"
    )
    parser.add_argument("--strict-optional", action="store_true")
    args = parser.parse_args()
    result = validate_generation(
        args.root, expected_sha256=args.sha256, strict_optional=args.strict_optional
    )
    print(
        json.dumps(
            {
                "generation_sha256": result["generation_sha256"],
                "cases": list(result["cases"]),
                "verified_objects": len(result["objects"]),
                "unavailable_optional_objects": result["unavailable"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()

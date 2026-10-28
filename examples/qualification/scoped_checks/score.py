"""The copied file is changed between the two declared software questions."""

from nisayon.engine.io import canonical_bytes

MODE = "configured_budget"


def evaluate(observation):
    actual = observation["actual"]["conditions"]
    expected = observation["expected"][MODE]["conditions"]
    if [row["id"] for row in actual] != [row["id"] for row in expected] or not actual:
        raise ValueError("Incomplete or misaligned camera observations")
    matched = sum(
        canonical_bytes(a) == canonical_bytes(b) for a, b in zip(actual, expected, strict=True)
    )
    return {
        "mode": MODE,
        "matched": matched,
        "assigned": len(actual),
        "holds": matched == len(actual),
    }


def run(ctx):
    return evaluate(ctx.upstream("observe"))

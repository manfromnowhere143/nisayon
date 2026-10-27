"""Exercise the native serialization boundary before a numerical decision is allowed."""

import json
import math
import subprocess
import sys

import pytest

from nisayon.engine.io import canonical_bytes, decode_json
from nisayon.qualification import CaseSpec, inspect_run, plan_change, run_plan
from nisayon.qualification.compare import difference


@pytest.mark.parametrize(
    ("expression", "reference", "decision"),
    [
        ("__import__('numpy').float64(value['number'])", 1.25, "adopt"),
        ("__import__('numpy').float64(value['number'])", 2**53 + 1, "reject"),
        ("__import__('numpy').int64(value['number'])", 1, "unresolved"),
        ("__import__('numpy').float32(value['number'])", 0.5, "unresolved"),
        ("__import__('fractions').Fraction(1, 2)", 0.5, "unresolved"),
        ("__import__('decimal').Decimal('0.5')", 0.5, "unresolved"),
        ("__import__('numpy').float64('inf')", 1, "unresolved"),
    ],
)
def test_native_numeric_outputs_retain_or_refuse_their_json_meaning(
    native, expression, reference, decision
):
    declaration, context = native
    (context.project / "policy.py").write_text(
        "def reference(value): return value['number']\n"
        f"def candidate(value): return {expression}\n"
        "def negative(value): return {'invalid': True}\n"
    )
    declaration["contract"] = {"kind": "numerical", "atol": 0, "rtol": 0}
    declaration["targets"] = {
        role: {"path": "policy.py", "callable": name}
        for role, name in [
            ("reference", "reference"),
            ("candidate", "candidate"),
            ("negative_control", "negative"),
        ]
    }
    declaration["probes"] = [{"id": "value", "input": {"number": reference}, "expected": reference}]
    evidence = run_plan(
        plan_change(CaseSpec.from_dict(declaration), context=context), context=context
    )
    result = inspect_run(evidence.root).record()
    assert result["software_decision"] == decision
    assert result["deployment_decision"] == "unresolved"
    attempt = json.loads((evidence.root / "candidate-value/record.json").read_text())
    if decision == "unresolved":
        assert attempt["status"] == "failed"
        assert not (evidence.root / "candidate-value/observation.json").exists()
        assert (evidence.root / "candidate-value/stderr.txt").stat().st_size > 0
    else:
        assert attempt["status"] == "completed"
        observation = json.loads((evidence.root / "candidate-value/observation.json").read_text())
        assert type(observation["value"]) is float


@pytest.mark.parametrize("value", [2**53 + 1, -(2**200 + 1), 0.0, -0.0, 2**-1074, 1e308])
def test_round_trip_preserves_the_declared_numeric_value_and_type(value):
    restored = decode_json(canonical_bytes({"nested": [value]}))["nested"][0]
    assert type(restored) is type(value)
    assert restored == value
    if type(value) is float:
        assert restored.hex() == value.hex()


def test_zero_subnormal_and_tolerance_edges_have_distinct_contracts():
    strict = {"kind": "numerical", "atol": 0, "rtol": 0}
    assert difference(-0.0, 0.0, strict) is None
    assert difference(-0.0, 0.0, {"kind": "exact"}) is not None
    smallest = math.ulp(0.0)
    assert difference(0.0, smallest, strict) is not None
    assert difference(0.0, smallest, {**strict, "atol": smallest}) is None
    # 0.1 + 0.2 and 0.3 are distinct represented binary values, not exact decimal fractions.
    assert difference(0.1 + 0.2, 0.3, strict) is not None
    assert difference(0.1 + 0.2, 0.3, {**strict, "atol": math.ulp(0.3)}) is None


def test_overlong_integer_is_refused_within_a_bounded_process():
    # 100 KB is deliberately small enough to avoid exhausting the host. The
    # worker's Python JSON boundary must refuse excessive integer conversion.
    code = (
        "import sys\n"
        "from nisayon.engine.io import decode_json\n"
        "sys.set_int_max_str_digits(4300)\n"
        "try:\n"
        "    decode_json('9' * 100_000)\n"
        "except ValueError:\n"
        "    print('refused')\n"
        "else:\n"
        "    raise SystemExit('unexpected acceptance')\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, timeout=5, check=True
    )
    assert result.stdout == "refused\n"


def test_large_supported_integer_uses_exact_arithmetic_within_a_bounded_process():
    code = (
        "from nisayon.qualification.compare import difference\n"
        "value = 10**4000\n"
        "contract = {'kind': 'numerical'}\n"
        "assert difference(value, value, contract) is None\n"
        "assert difference(value, value + 1, contract) is not None\n"
        "assert difference(value, value + 1, {**contract, 'atol': 1}) is None\n"
        "print('preserved')\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, timeout=5, check=True
    )
    assert result.stdout == "preserved\n"


def test_oversized_retained_numeric_record_yields_invalid_unresolved(native):
    declaration, context = native
    evidence = run_plan(
        plan_change(CaseSpec.from_dict(declaration), context=context), context=context
    )
    # A record exceeding the documented reader cap is refused before JSON conversion.
    with (evidence.root / "manifest.json").open("wb") as stream:
        stream.write(b"9" * (16 * 1024 * 1024 + 1))
    result = inspect_run(evidence.root).record()
    assert result["software_decision"] == "unresolved"
    assert result["execution_validity"] == "invalid"
    assert any("Oversized protocol record" in item for item in result["obligations"])

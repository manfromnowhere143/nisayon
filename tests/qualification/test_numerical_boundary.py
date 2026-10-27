"""False acceptance at numeric representation boundaries must remain impossible."""

import math
from decimal import Decimal, Inexact, Rounded, localcontext

import pytest

from nisayon.qualification import CaseSpec, assess_change, plan_change, run_plan
from nisayon.qualification.compare import difference


@pytest.mark.parametrize("sign", [-1, 1])
@pytest.mark.parametrize("exponent", [53, 54, 63, 80, 200])
def test_mixed_numbers_do_not_round_away_a_real_difference(sign, exponent):
    integer = sign * (2**exponent + 1)
    rounded = float(integer)
    contract = {"kind": "numerical", "atol": 0, "rtol": 0}
    assert difference(integer, rounded, contract) is not None
    assert difference(rounded, integer, contract) is not None
    assert difference(integer, rounded, {**contract, "atol": 1}) is None


def test_relative_tolerance_is_evaluated_on_the_exact_represented_reference():
    reference = 2**53 + 1
    candidate = float(reference)
    assert difference(reference, candidate, {"kind": "numerical", "rtol": 2**-53}) is None
    assert difference(reference, candidate, {"kind": "numerical", "rtol": 2**-54}) is not None


def test_exact_contract_and_non_numeric_types_keep_their_meaning():
    assert difference(1, 1.0, {"kind": "exact"}) is not None
    assert difference(1, 1.0, {"kind": "numerical"}) is None
    assert difference(True, 1, {"kind": "numerical"}) is not None
    result = difference({"a/b": [2**53 + 1]}, {"a/b": [float(2**53)]}, {"kind": "numerical"})
    assert result["path"] == "/a~1b/0"


@pytest.mark.parametrize("value", [math.inf, -math.inf, math.nan])
def test_nonfinite_direct_inputs_never_agree(value):
    assert difference(value, value, {"kind": "numerical"}) is not None


def test_deterministic_grid_agrees_with_independent_decimal_oracle():
    # Both signs, normal/subnormal floats, mixed exact integers and tolerance
    # boundaries. Decimal traps make insufficient oracle precision a failure.
    values = [0, -0.0, 1, -1, 0.1, 0.3, 2**-1074, 1e-300, 1e300]
    for exponent in [52, 53, 54, 63, 80, 200]:
        for sign in [-1, 1]:
            integer = sign * (2**exponent + 1)
            values.extend([integer, float(integer), math.nextafter(float(integer), math.inf)])
    for atol, rtol in [(0, 0), (0.5, 0), (1, 0), (0, 2**-53), (2**-1074, 1e-10)]:
        contract = {"kind": "numerical", "atol": atol, "rtol": rtol}
        for left in values:
            for right in values:
                with localcontext() as context:
                    context.prec = 5000
                    context.traps[Inexact] = True
                    context.traps[Rounded] = True
                    expected = abs(Decimal(right) - Decimal(left)) <= (
                        Decimal(atol) + Decimal(rtol) * abs(Decimal(left))
                    )
                assert (difference(left, right, contract) is None) == expected


@pytest.mark.parametrize("invalid_reference", [False, True])
def test_native_assessment_cannot_adopt_a_rounded_integer(native, invalid_reference):
    declaration, context = native
    big = 2**53 + 1
    (context.project / "policy.py").write_text(
        "def reference(value): return value['reference']\n"
        "def candidate(value): return value['candidate']\n"
        "def negative(value): return {'invalid': True}\n"
    )
    declaration["contract"] = {"kind": "numerical", "atol": 0, "rtol": 0}
    declaration["targets"] = {
        role: {"path": "policy.py", "callable": symbol}
        for role, symbol in [
            ("reference", "reference"),
            ("candidate", "candidate"),
            ("negative_control", "negative"),
        ]
    }
    declaration["probes"] = [
        {
            "id": "large_integer",
            "input": {
                "reference": float(big) if invalid_reference else big,
                "candidate": float(big),
            },
            "expected": big,
        }
    ]
    case = CaseSpec.from_dict(declaration)
    result = assess_change(case, run_plan(plan_change(case, context=context), context=context))
    assert result.decision == ("unresolved" if invalid_reference else "reject")
    assert result.record()["deployment_decision"] == "unresolved"

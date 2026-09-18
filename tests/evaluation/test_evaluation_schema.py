"""Strict parsing: finite numbers, explicit missingness, clock domains and units."""

from __future__ import annotations

import json

import pytest

from nisayon.evaluation.schema import (
    Malformed,
    canonical_json,
    digest_of,
    load_json,
    parse_duration,
    parse_quantity,
    parse_sim_time,
    parse_wall_time,
)


def test_nan_and_infinity_are_rejected_when_loading(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text('{"value": NaN}')
    with pytest.raises(Malformed, match="non-finite"):
        load_json(path)
    path.write_text('{"value": -Infinity}')
    with pytest.raises(Malformed, match="non-finite"):
        load_json(path)


def test_quantity_requires_a_missingness_reason_for_null():
    assert parse_quantity({"value": 1.5, "unit": "s"}, "q").value == 1.5
    missing = parse_quantity({"value": None, "unit": "s", "missing": "not measured"}, "q")
    assert (missing.value, missing.missing) == (None, "not measured")
    with pytest.raises(Malformed, match="q.missing"):
        parse_quantity({"value": None, "unit": "s"}, "q")
    with pytest.raises(Malformed, match="finite"):
        parse_quantity({"value": True, "unit": "s"}, "q")
    with pytest.raises(Malformed, match="expected unit 'm'"):
        parse_quantity({"value": 1, "unit": "cm"}, "q", unit="m")


def test_durations_convert_only_declared_units():
    assert parse_duration({"value": 60, "unit": "ms"}, "d") == pytest.approx(0.06)
    assert parse_duration({"value": 0.5, "unit": "s"}, "d") == 0.5
    with pytest.raises(Malformed, match="expected one of"):
        parse_duration({"value": 1, "unit": "min"}, "d")


def test_sim_time_needs_the_declared_clock_domain():
    assert parse_sim_time({"value": 1, "unit": "s", "clock": "sim"}, "t", "sim") == 1.0
    with pytest.raises(Malformed, match="clock domain 'wall_utc' does not match"):
        parse_sim_time({"value": 1, "unit": "s", "clock": "wall_utc"}, "t", "sim")
    with pytest.raises(Malformed, match="t.clock: missing"):
        parse_sim_time({"value": 1, "unit": "s"}, "t", "sim")


def test_wall_time_needs_an_offset():
    stamp = parse_wall_time({"value": "2026-09-17T18:00:00+00:00", "clock": "wall_utc"}, "w")
    assert stamp.isoformat() == "2026-09-17T18:00:00+00:00"
    with pytest.raises(Malformed, match="UTC offset"):
        parse_wall_time({"value": "2026-09-17T18:00:00", "clock": "wall_utc"}, "w")
    with pytest.raises(Malformed, match="expected one of"):
        parse_wall_time({"value": "2026-09-17T18:00:00+00:00", "clock": "sim"}, "w")


def test_canonical_digest_is_order_independent_and_refuses_nan():
    a = {"b": [1, 2.5], "a": {"y": "ü", "x": None}}
    b = {"a": {"x": None, "y": "ü"}, "b": [1, 2.5]}
    assert canonical_json(a) == canonical_json(b) == '{"a":{"x":null,"y":"ü"},"b":[1,2.5]}'
    assert digest_of(a) == digest_of(b)
    assert digest_of(a).startswith("sha256:")
    with pytest.raises(ValueError):
        canonical_json({"x": float("nan")})
    assert json.loads(canonical_json(a)) == a

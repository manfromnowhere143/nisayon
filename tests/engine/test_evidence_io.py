import json

import pytest

from nisayon.engine.io import canonical_bytes, decode_json, digest, write_json


def test_unknown_numeric_values_cannot_be_disguised_as_nonfinite(tmp_path):
    for value in [float("nan"), float("inf"), -float("inf")]:
        with pytest.raises(ValueError):
            digest({"measurement": value})


def test_record_write_preserves_previous_attempt(tmp_path):
    path = tmp_path / "run.json"
    write_json(path, {"process_status": "failed"})
    with pytest.raises(FileExistsError):
        write_json(path, {"process_status": "completed"})
    assert '"failed"' in path.read_text()


@pytest.mark.parametrize(
    "data",
    [
        '{"outcome": "failed", "outcome": "completed"}',
        '{"nested": [{"value": 1, "value": 1}]}',
        r'{"value": 0, "\u0076alue": 1}',
    ],
)
def test_ambiguous_evidence_objects_are_rejected_at_any_depth(data):
    with pytest.raises(ValueError, match="Duplicate JSON key"):
        decode_json(data)


@pytest.mark.parametrize("number", ["NaN", "Infinity", "-Infinity", "1e999", "-1e999"])
def test_decoding_rejects_nonfinite_numbers_including_exponent_overflow(number):
    with pytest.raises(ValueError, match="Non-finite JSON number"):
        decode_json('{"measurements": [' + number + "]}")


@pytest.mark.parametrize("encoding", [str, bytes, bytearray])
@pytest.mark.parametrize(
    "number",
    ["1e-400", "-1e-400", "1E-324", "-2.4e-324", "0." + "0" * 400 + "1"],
)
def test_nonzero_json_underflow_is_refused_before_it_becomes_zero(number, encoding):
    source = '{"measurements": [' + number + "]}"
    data = source if encoding is str else encoding(source, "utf-8")
    with pytest.raises(ValueError, match="underflows to zero"):
        decode_json(data)


@pytest.mark.parametrize(
    "number",
    ["0.0", "-0.0", "0e-400", "-0.00E+9999", "0.0e9999", "3e-324", "-5e-324", "0.1"],
)
def test_literal_zeros_and_nonzero_binary_floats_keep_their_representation(number):
    restored = decode_json(number)
    assert type(restored) is float
    assert restored.hex() == float(number).hex()
    assert canonical_bytes(restored) == canonical_bytes(json.loads(number))


def test_valid_numbers_missingness_and_strings_keep_their_existing_digest():
    source = b'{"observed": false, "value": null, "count": 0, "finite": 1e300, "label": "NaN"}'
    decoded = decode_json(source)
    assert decoded["value"] is None and decoded["observed"] is False
    assert type(decoded["count"]) is int and decoded["label"] == "NaN"
    assert canonical_bytes(decoded) == canonical_bytes(json.loads(source))
    assert decode_json(bytearray(source)) == decoded


@pytest.mark.parametrize("opening,closing", [("[", "]"), ('{"nested":', "}")])
def test_excessive_json_nesting_is_a_declared_input_error(opening, closing):
    with pytest.raises(ValueError, match="nesting"):
        decode_json(opening * 10000 + "0" + closing * 10000)

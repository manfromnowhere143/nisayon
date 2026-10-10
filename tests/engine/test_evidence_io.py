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


def test_valid_numbers_missingness_and_strings_keep_their_existing_digest():
    source = b'{"observed": false, "value": null, "count": 0, "finite": 1e300, "label": "NaN"}'
    decoded = decode_json(source)
    assert decoded["value"] is None and decoded["observed"] is False
    assert type(decoded["count"]) is int and decoded["label"] == "NaN"
    assert canonical_bytes(decoded) == canonical_bytes(json.loads(source))
    assert decode_json(bytearray(source)) == decoded

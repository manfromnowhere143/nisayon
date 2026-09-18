import pytest

from nisayon.engine.io import digest, write_json


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

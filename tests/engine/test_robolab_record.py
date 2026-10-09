import json
from pathlib import Path

import pytest

from nisayon.engine.io import file_digest
from nisayon.engine.robolab_record import compact_record, read_record, read_sample

h5py = pytest.importorskip("h5py")
np = pytest.importorskip("numpy")


def make_record(path, *, episodes=1, rows=3):
    with h5py.File(path, "w") as handle:
        data = handle.create_group("data")
        data.attrs["total"] = episodes * rows
        data.attrs["recorded_at"] = "producer-recording-date-only"
        for index in range(episodes):
            episode = data.create_group(f"demo_{index}")
            episode.attrs.update(num_samples=rows, success=True)
            episode.create_dataset(
                "actions", data=np.arange(rows * 8, dtype=np.float32).reshape(rows, 8) + index
            )
            episode.create_dataset(
                "states/articulation/robot/joint_position",
                data=np.zeros((rows, 13), dtype=np.float32),
            )
            episode.create_dataset(
                "states/rigid_object/cube/root_pose", data=np.zeros((rows, 7), dtype=np.float32)
            )
            episode.create_dataset(
                "initial_state/articulation/robot/joint_position",
                data=np.zeros((2, 13), dtype=np.float32),
            )
    return path


def read(path):
    return read_record(
        path, {"sim": {"dt": 1 / 120}, "decimation": 8}, evidence_origin="synthetic_development"
    )


def test_episode_membership_values_and_emission_axis_are_preserved(tmp_path):
    result = read(make_record(tmp_path / "record.hdf5", episodes=2))
    assert len(result["episodes"]) == 2
    for index, episode in enumerate(result["episodes"]):
        assert episode["id"] == f"demo_{index}"
        assert episode["fields"]["actions"]["values"][0][0] == index
        initial = episode["fields"]["initial_state/articulation/robot/joint_position"]
        assert initial["shape"] == [2, 13] and len(initial["values"]) == 2
        assert episode["initial_state"]["native_selected_row"] is None
        assert episode["initial_state"]["rows_identical"] is True
        assert episode["producer_success"]["status"] == "producer_claim_only"
        assert episode["alignment"]["row_index_is_timestamp"] is False
    compact = compact_record(result)
    assert "values" not in compact["episodes"][0]["fields"]["actions"]
    assert "values" in result["episodes"][0]["fields"]["actions"]
    assert "acquisition_times" in result["missing_obligations"]
    assert not result["mapping_issues"]


@pytest.mark.parametrize(
    "fault",
    [
        "short_state",
        "inconsistent_initial",
        "different_initial",
        "bad_width",
        "nonfinite",
        "bad_count",
    ],
)
def test_invalid_or_ambiguous_fields_do_not_erase_usable_measurements(tmp_path, fault):
    path = make_record(tmp_path / "record.hdf5")
    with h5py.File(path, "a") as handle:
        episode = handle["data/demo_0"]
        if fault == "short_state":
            del episode["states/articulation/robot/joint_position"]
            episode.create_dataset(
                "states/articulation/robot/joint_position", data=np.zeros((2, 13), dtype=np.float32)
            )
        elif fault == "inconsistent_initial":
            episode.create_dataset(
                "initial_state/rigid_object/cube/root_pose", data=np.zeros((1, 7), dtype=np.float32)
            )
        elif fault == "different_initial":
            episode["initial_state/articulation/robot/joint_position"][1, 0] = 1.0
        elif fault == "bad_width":
            del episode["actions"]
            episode.create_dataset("actions", data=np.zeros((3, 7), dtype=np.float32))
        elif fault == "nonfinite":
            episode["actions"][0, 0] = np.nan
        else:
            episode.attrs["num_samples"] = 1
    result = read(path)
    assert result["mapping_issues"] and result["measurement_status"] == "partial"
    assert (
        result["episodes"][0]["fields"]["states/rigid_object/cube/root_pose"]["values"] is not None
    )
    json.dumps(result, allow_nan=False)


def test_lfs_pointer_external_links_and_decompression_growth_are_refused(tmp_path):
    pointer = tmp_path / "pointer.hdf5"
    pointer.write_text("version https://git-lfs.github.com/spec/v1\noid sha256:abc\nsize 123\n")
    with pytest.raises(ValueError, match="LFS pointer"):
        read(pointer)
    path = make_record(tmp_path / "record.hdf5")
    with h5py.File(path, "a") as handle:
        handle["data/demo_0/outside"] = h5py.ExternalLink("outside.hdf5", "/data")
    with pytest.raises(ValueError, match="External or soft"):
        read(path)
    with h5py.File(path, "a") as handle:
        del handle["data/demo_0/outside"]
        handle["data/demo_0"].create_dataset(
            "too_large", shape=(2_000_001,), dtype="f4", chunks=True
        )
    with pytest.raises(ValueError, match="element limit"):
        read(path)


def test_unknown_numeric_field_remains_readable_without_invented_semantics(tmp_path):
    path = make_record(tmp_path / "record.hdf5")
    with h5py.File(path, "a") as handle:
        handle["data/demo_0"].create_dataset(
            "unknown_sensor", data=np.zeros((3, 2), dtype=np.float32)
        )
    field = read(path)["episodes"][0]["fields"]["unknown_sensor"]
    assert field["mapping"]["status"] == "unsupported"
    assert field["mapping"]["units"] is None and field["values"] == [[0.0, 0.0]] * 3
    assert field["mapping"]["alignment"] is None


def test_joint_and_end_effector_measurements_keep_their_distinct_frame_premises(tmp_path):
    path = make_record(tmp_path / "record.hdf5")
    with h5py.File(path, "a") as handle:
        episode = handle["data/demo_0"]
        for leaf in ("position", "linear_velocity"):
            episode.create_dataset("ee_pose/" + leaf, data=np.zeros((3, 3), dtype=np.float32))
    fields = read(path)["episodes"][0]["fields"]
    joint = fields["states/articulation/robot/joint_position"]["mapping"]
    assert joint["units"] is None and "joint coordinates" in joint["frame"]
    assert "world" not in joint["frame"]
    assert fields["ee_pose/position"]["mapping"]["frame"] == "robot-root frame"
    assert fields["ee_pose/linear_velocity"]["mapping"]["frame"] == "world axes"
    assert "not attested" in fields["ee_pose/position"]["mapping"]["premise"]


def test_unknown_field_names_do_not_inherit_known_measurement_or_row_semantics(tmp_path):
    path = make_record(tmp_path / "record.hdf5")
    unknowns = ("states/rigid_object/cube/temperature", "ee_pose/unrecognized", "new_sensor")
    with h5py.File(path, "a") as handle:
        for name in unknowns:
            handle["data/demo_0"].create_dataset(name, data=np.int64(2**62 + 1))
    result = read(path)
    for name in unknowns:
        field = result["episodes"][0]["fields"][name]
        assert field["mapping"]["status"] == "unsupported"
        assert field["mapping"]["semantic"] is field["mapping"]["alignment"] is None
        assert field["minimum"] == field["maximum"] == field["values"] == 2**62 + 1
    assert not result["mapping_issues"]


def test_unsupported_dataset_preserves_membership_shape_and_dtype(tmp_path):
    path = make_record(tmp_path / "record.hdf5")
    with h5py.File(path, "a") as handle:
        handle["data/demo_0"].create_dataset("named_sensor", data=np.array([b"value"], dtype="S5"))
    result = read(path)
    unsupported = result["unsupported_datasets"]
    assert len(unsupported) == 1
    assert unsupported[0]["source_dataset"] == "/data/demo_0/named_sensor"
    assert unsupported[0]["shape"] == [1] and unsupported[0]["dtype"] == "|S5"
    assert result["episodes"][0]["fields"]["actions"]["values"] is not None


def test_rebound_manifest_cannot_relabel_a_different_companion_as_the_pinned_sample(tmp_path):
    root = Path(__file__).resolve().parents[2]
    manifest = json.loads(
        (root / "docs/experiments/results/robolab-record-001/sample-manifest.json").read_text()
    )
    config = next(r for r in manifest["records"] if r["path"] == "env_cfg.json")
    config["sha256"] = "0" * 64
    (tmp_path / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="pinned source member: env_cfg.json"):
        read_sample(tmp_path)


def test_packet_consumes_verified_companion_snapshot_despite_later_file_changes(
    tmp_path, monkeypatch
):
    from nisayon.engine import robolab_record as reader

    # Replace pins only inside this synthetic unit test. No fixture is labelled
    # as an upstream observation or mixed into the retained real import.
    make_record(tmp_path / "data.hdf5")
    for name, content in {
        "env_cfg.json": '{"sim":{"dt":0.25},"fixture":"synthetic_development"}',
        "log_0.json": "[{}]",
        "LICENSE": "synthetic test text",
        "replay.md": "synthetic test text",
        "data.hdf5.lfs-pointer": "synthetic test pointer",
    }.items():
        (tmp_path / name).write_text(content)
    records = [
        {"path": p.name, "sha256": file_digest(p), "bytes": p.stat().st_size}
        for p in sorted(tmp_path.iterdir())
    ]
    manifest = {
        "upstream": "https://github.com/NVlabs/RoboLab",
        "commit": reader.ROBO_COMMIT,
        "records": records,
    }
    (tmp_path / "manifest.json").write_text(json.dumps(manifest))
    manifest_sha = file_digest(tmp_path / "manifest.json")
    monkeypatch.setattr(
        reader, "SAMPLE_MEMBERS", {r["path"]: (r["sha256"], r["bytes"]) for r in records}
    )
    monkeypatch.setattr(reader, "SAMPLE_SHA256", file_digest(tmp_path / "data.hdf5"))
    original = reader.read_record

    def changed_companions(path, config, **kwargs):
        (tmp_path / "env_cfg.json").write_text('{"sim":{"dt":999}}')
        (tmp_path / "log_0.json").write_text("not JSON now")
        (tmp_path / "manifest.json").write_text("changed after verification")
        return original(path, config, evidence_origin="synthetic_development")

    monkeypatch.setattr(reader, "read_record", changed_companions)
    result = reader.read_sample(tmp_path)
    assert result["evidence_origin"] == "synthetic_development"
    assert result["producer_configuration"]["sim_dt"] == 0.25
    assert result["companion_log"]["entries"] == 1
    assert result["source_packet"]["manifest_sha256"] == manifest_sha
    # Restore source metadata, then change HDF5 only after initial verification.
    (tmp_path / "manifest.json").write_text(json.dumps(manifest))
    (tmp_path / "env_cfg.json").write_text('{"sim":{"dt":0.25},"fixture":"synthetic_development"}')
    (tmp_path / "log_0.json").write_text("[{}]")

    def changed_hdf5(path, config, **kwargs):
        with h5py.File(path, "a") as handle:
            handle["data/demo_0/actions"][0, 0] = 123
        return original(path, config, evidence_origin="synthetic_development")

    monkeypatch.setattr(reader, "read_record", changed_hdf5)
    with pytest.raises(ValueError, match="HDF5 bytes changed"):
        reader.read_sample(tmp_path)

"""Full model identity without a retained serialization buffer or extra copy."""

import gzip
import weakref

import pytest

mj = pytest.importorskip("mujoco")
np = pytest.importorskip("numpy")

import nisayon.qualification.native_measurements as measurements  # noqa: E402
from nisayon.qualification.native_measurements import (  # noqa: E402
    _model_bytes,
    reassess_native_measurements,
)

from .test_native_measurements import XML, NativeProducer, finish, setup  # noqa: E402

TEXTURED_XML = XML.replace(
    b"<worldbody>",
    b'<asset><texture name="pixels" type="2d" builtin="checker" width="32" '
    b'height="32" rgb1=".1 .2 .3" rgb2=".7 .8 .9"/></asset><worldbody>',
)


def mutate(model, field):
    array = {
        "gravity": model.opt.gravity,
        "geometry": model.geom_size,
        "texture": model.tex_data,
    }[field]
    array.flat[0] += 1


class ModelMutator(NativeProducer):
    mutation = None

    def success(self):
        result = super().success()
        if self.mutation:
            mutate(self.model, self.mutation)
        return result


@pytest.mark.parametrize("field", ["gravity", "geometry", "texture"])
@pytest.mark.parametrize("when", ["before_call", "during_call"])
def test_every_call_checks_full_model_before_and_after_producer(tmp_path, field, when):
    writer, model, data, native = setup(
        tmp_path / "packet", xml=TEXTURED_XML, producer_type=ModelMutator
    )
    if when == "before_call":
        mutate(model, field)
        error = "live_model_changed"
    else:
        native.mutation = field
        error = "native_producer_changed_model"
    with pytest.raises(ValueError, match=error):
        writer.capture(data, episode="case", step=0)
    assert writer.failed and writer.index == 0
    assert not (writer.root / "frames.jsonl").read_bytes()
    with pytest.raises(ValueError, match="incomplete_capture"):
        writer.finalize()
    assert not (writer.root / "seal.json").exists()


@pytest.mark.parametrize("failure", [False, True])
def test_full_model_snapshots_do_not_outlive_identity_checks(tmp_path, monkeypatch, failure):
    references = []
    save = measurements._save_model

    def observed_save(*args, **kwargs):
        snapshot = save(*args, **kwargs)
        references.append(weakref.ref(snapshot))
        return snapshot

    monkeypatch.setattr(measurements, "_save_model", observed_save)
    writer, model, data, _ = setup(tmp_path / "packet", xml=TEXTURED_XML)
    assert references and all(ref() is None for ref in references)
    if failure:
        mutate(model, "texture")
        with pytest.raises(ValueError, match="live_model_changed"):
            writer.capture(data, episode="case", step=0)
        assert writer.failed
    else:
        assert finish(writer, data)["status"] == "consistent"
    assert all(ref() is None for ref in references)


def test_complete_archive_stays_immutable_across_later_captures(tmp_path):
    writer, model, data, _ = setup(
        tmp_path / "packet",
        [{"episode": "case", "step": 0}, {"episode": "case", "step": 1}],
        xml=TEXTURED_XML,
    )
    archive = (writer.root / "model.mjb.gz").read_bytes()
    expected = _model_bytes(mj, np, model)
    assert gzip.decompress(archive) == expected
    writer.capture(data, episode="case", step=0)
    data.time += 0.01
    mj.mj_forward(model, data)
    writer.capture(data, episode="case", step=1)
    assert (writer.root / "model.mjb.gz").read_bytes() == archive
    writer.finalize()
    assert reassess_native_measurements(writer.root)["status"] == "consistent"

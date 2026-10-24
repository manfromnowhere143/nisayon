"""Exercise actual OpenPI image modules; no model weights or import stubs."""

import os
from types import SimpleNamespace

import pytest
import torch
from openpi.models_pytorch import preprocessing_pytorch as preprocessing
from openpi.shared import image_tools

SEED = int(os.environ.get("NISAYON_INPUT_SEED", "17"))
SHAPE_ONLY = os.environ.get("NISAYON_SHAPE_ONLY") == "1"
SIZES = [(224, 224), (480, 640), (641, 479)]
torch.set_num_threads(1)


def patterned(batch, height, width, dtype, offset=0):
    values = (
        torch.arange(batch * height * width * 3, dtype=torch.int64) * 37 + SEED + offset
    ) % 251
    pixels = values.reshape(batch, height, width, 3).to(torch.uint8)
    return pixels if dtype == torch.uint8 else pixels.to(torch.float32) / 127.5 - 1.0


def to_layout(images, layout):
    if layout == "last":
        return images
    return images.permute(2, 0, 1) if images.ndim == 3 else images.permute(0, 3, 1, 2)


def to_last(images, layout):
    if layout == "last":
        return images
    return images.permute(1, 2, 0) if images.ndim == 3 else images.permute(0, 2, 3, 1)


@pytest.mark.parametrize("dtype", [torch.uint8, torch.float32])
@pytest.mark.parametrize("layout", ["first", "last"])
@pytest.mark.parametrize("batch", [0, 1, 2])
@pytest.mark.parametrize("size", SIZES)
def test_resize_rank_values_layout_and_batch(dtype, layout, batch, size):
    canonical = patterned(max(batch, 1), *size, dtype)
    if batch == 0:
        canonical = canonical[0]
    images = to_layout(canonical, layout)
    unchanged = images.clone()
    result = image_tools.resize_with_pad_torch(images, 224, 224)
    expected = (224, 224, 3) if layout == "last" else (3, 224, 224)
    if batch:
        expected = (batch, *expected)
    assert tuple(result.shape) == expected
    assert result.dtype == dtype
    assert torch.equal(images, unchanged), "Caller image was mutated"

    other_layout = "first" if layout == "last" else "last"
    other = image_tools.resize_with_pad_torch(to_layout(canonical, other_layout), 224, 224)
    assert torch.equal(to_last(result, layout), to_last(other, other_layout))
    if size == (224, 224):
        assert torch.equal(result, images), "Identity resize changed pixel ordering or values"
    else:
        channels_last = to_last(result, layout)
        if not batch:
            channels_last = channels_last.unsqueeze(0)
        border = channels_last[:, 0] if size[1] > size[0] else channels_last[:, :, 0]
        fill = 0 if dtype == torch.uint8 else -1.0
        assert torch.all(border == fill), "Padding does not preserve the declared black value"
    if batch:
        separate = torch.stack(
            [image_tools.resize_with_pad_torch(item, 224, 224) for item in images]
        )
        assert torch.equal(result, separate), "Batching changed image semantics"


def observation(batch, size, layout):
    images = {
        key: to_layout(patterned(batch, *size, torch.float32, offset=i * 19), layout)
        for i, key in enumerate(preprocessing.IMAGE_KEYS)
    }
    return SimpleNamespace(
        images=images,
        image_masks={
            "base_0_rgb": torch.arange(batch) % 2 == 0,
            "right_wrist_0_rgb": torch.zeros(batch, dtype=torch.bool),
        },
        state=torch.arange(batch * 4, dtype=torch.float32).reshape(batch, 4),
        tokenized_prompt=torch.arange(batch * 6, dtype=torch.int32).reshape(batch, 6),
        tokenized_prompt_mask=torch.ones(batch, 6, dtype=torch.bool),
        token_ar_mask=None,
        token_loss_mask=None,
    )


@pytest.mark.parametrize("batch", [1, 2])
@pytest.mark.parametrize("size", SIZES)
@pytest.mark.parametrize("train", [False, True])
def test_preprocessing_preserves_camera_semantics(batch, size, train):
    outputs = []
    for layout in ("first", "last"):
        obs = observation(batch, size, layout)
        before = {key: image.clone() for key, image in obs.images.items()}
        state_before = obs.state.clone()
        prompt_before = obs.tokenized_prompt.clone()
        torch.manual_seed(SEED)
        processed = preprocessing.preprocess_observation_pytorch(obs, train=train)
        for key, image in processed.images.items():
            assert tuple(image.shape) == (batch, 3, 224, 224)
            assert torch.isfinite(image).all()
            if SHAPE_ONLY:
                continue
            assert torch.equal(obs.images[key], before[key]), "Caller image was mutated"
            if not train and size == (224, 224):
                expected = (
                    obs.images[key] if layout == "first" else obs.images[key].permute(0, 3, 1, 2)
                )
                assert torch.equal(image, expected), (
                    "Correct shape concealed incorrect pixel ordering"
                )
            expected_mask = obs.image_masks.get(key, torch.ones(batch, dtype=torch.bool))
            assert torch.equal(processed.image_masks[key], expected_mask)
        assert torch.equal(obs.state, state_before)
        assert torch.equal(obs.tokenized_prompt, prompt_before)
        assert processed.state is obs.state
        assert processed.tokenized_prompt is obs.tokenized_prompt
        outputs.append(processed)
    if not SHAPE_ONLY:
        for key in preprocessing.IMAGE_KEYS:
            assert torch.equal(outputs[0].images[key], outputs[1].images[key]), (
                "Layout changed camera values"
            )

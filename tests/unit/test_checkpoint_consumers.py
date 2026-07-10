from pathlib import Path
from types import SimpleNamespace

import pytest
import torch

from tools import export_ai_router_onnx
from train import train_pipeline
from train.checkpoint_contracts import (
    CheckpointStateCoverageError,
    canonical_model_state_dict,
    load_state_dict_fail_closed,
)
from train.runtime_inputs import current_runtime_input_schema_metadata


class _TinyModel(torch.nn.Module):
    def __init__(self):
        super().__init__()
        self.first = torch.nn.Linear(3, 4)
        self.second = torch.nn.Linear(4, 2)


class _CompiledLikeWrapper(torch.nn.Module):
    def __init__(self, original):
        super().__init__()
        self._orig_mod = original


def _write_checkpoint(path: Path, state_dict) -> None:
    torch.save(
        {
            "state_dict": state_dict,
            "runtime_input_schema": current_runtime_input_schema_metadata(),
        },
        path,
    )


def test_shared_non_strict_loader_allows_extras_but_requires_full_current_coverage():
    source = _TinyModel()
    target = _TinyModel()
    state = dict(source.state_dict())
    state["retired.extra"] = torch.ones((1,))
    info = load_state_dict_fail_closed(target, state, strict=False)
    assert info["tensor_numel_coverage"] == pytest.approx(1.0)
    assert info["missing_keys_count"] == 0
    assert info["unexpected_keys_count"] == 1

    missing = dict(source.state_dict())
    missing.pop("second.bias")
    with pytest.raises(CheckpointStateCoverageError, match="does not fully cover"):
        load_state_dict_fail_closed(target, missing, strict=False)

    wrong_dtype = dict(source.state_dict())
    wrong_dtype["second.bias"] = wrong_dtype["second.bias"].double()
    with pytest.raises(CheckpointStateCoverageError, match="dtype_mismatch=1"):
        load_state_dict_fail_closed(target, wrong_dtype, strict=False)

    nonfinite = dict(source.state_dict())
    nonfinite["first.weight"] = nonfinite["first.weight"].clone()
    nonfinite["first.weight"][0, 0] = float("nan")
    with pytest.raises(CheckpointStateCoverageError, match="non-finite"):
        load_state_dict_fail_closed(target, nonfinite, strict=False)


def test_compiled_wrapper_is_saved_in_canonical_unprefixed_key_space():
    model = _TinyModel()
    wrapper = _CompiledLikeWrapper(model)
    assert all(key.startswith("_orig_mod.") for key in wrapper.state_dict())
    canonical = canonical_model_state_dict(wrapper)
    assert set(canonical) == set(model.state_dict())
    assert all(not key.startswith("_orig_mod.") for key in canonical)
    target = _TinyModel()
    info = load_state_dict_fail_closed(target, canonical, strict=False)
    assert info["tensor_numel_coverage"] == pytest.approx(1.0)


@pytest.mark.parametrize("consumer", ["train", "onnx"])
def test_train_and_onnx_consumers_accept_exact_schema_and_complete_state(
    tmp_path, monkeypatch, consumer
):
    source = _TinyModel()
    target = _TinyModel()
    checkpoint = Path(tmp_path) / f"{consumer}-complete.pth"
    _write_checkpoint(checkpoint, source.state_dict())
    if consumer == "train":
        monkeypatch.setattr(
            train_pipeline, "config", SimpleNamespace(DEVICE=torch.device("cpu"))
        )
        info = train_pipeline._load_checkpoint_if_requested(
            target, str(checkpoint), strict=False
        )
    else:
        info = export_ai_router_onnx._load_checkpoint_if_any(
            target, str(checkpoint), strict=False
        )
    assert info["loaded"] is True
    assert info["missing_keys_count"] == 0
    assert info["tensor_numel_coverage"] == pytest.approx(1.0)
    for source_parameter, target_parameter in zip(source.parameters(), target.parameters()):
        assert torch.equal(source_parameter, target_parameter)


@pytest.mark.parametrize("consumer", ["train", "onnx"])
def test_train_and_onnx_consumers_reject_schema_wrapped_partial_state(
    tmp_path, monkeypatch, consumer
):
    target = _TinyModel()
    partial = {"first.weight": target.state_dict()["first.weight"].clone()}
    checkpoint = Path(tmp_path) / f"{consumer}-partial.pth"
    _write_checkpoint(checkpoint, partial)
    if consumer == "train":
        monkeypatch.setattr(
            train_pipeline, "config", SimpleNamespace(DEVICE=torch.device("cpu"))
        )
        loader = train_pipeline._load_checkpoint_if_requested
    else:
        loader = export_ai_router_onnx._load_checkpoint_if_any
    with pytest.raises(CheckpointStateCoverageError, match="does not fully cover"):
        loader(target, str(checkpoint), strict=False)

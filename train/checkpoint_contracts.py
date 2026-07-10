"""Fail-closed state-dict loading shared by legacy AI checkpoint consumers."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

import torch


class CheckpointStateCoverageError(RuntimeError):
    """A checkpoint does not cover the model state required for execution."""


DEFAULT_STATE_DICT_KEYS = (
    "state_dict",
    "model_state_dict",
    "airouter_state_dict",
    "model",
    "weights",
)


def canonical_model_state_dict(model: torch.nn.Module) -> Mapping[str, Any]:
    """Return the unprefixed state namespace beneath ``torch.compile`` wrappers."""

    current = model
    seen: set[int] = set()
    while isinstance(current, torch.nn.Module) and id(current) not in seen:
        seen.add(id(current))
        original = getattr(current, "_orig_mod", None)
        if not isinstance(original, torch.nn.Module):
            break
        current = original
    return current.state_dict()


def resolve_checkpoint_state_dict(
    payload: object,
    *,
    candidate_keys: Sequence[str] = DEFAULT_STATE_DICT_KEYS,
) -> tuple[Mapping[str, Any], str]:
    """Resolve a nested state dict while retaining narrow raw-state compatibility.

    Runtime schema validation is a separate mandatory step for the consumers in
    this repository, so a raw state dict will still be rejected there before it
    can be loaded.  Keeping resolution independent makes the contract testable.
    """

    if isinstance(payload, Mapping):
        for key in candidate_keys:
            candidate = payload.get(key)
            if isinstance(candidate, Mapping):
                return candidate, str(key)
        if payload:
            has_tensor_value = any(torch.is_tensor(value) for value in payload.values())
            if has_tensor_value and all(isinstance(key, str) for key in payload):
                return payload, "root"
    raise ValueError("checkpoint payload does not contain a recognizable model state_dict")


def load_state_dict_fail_closed(
    model: torch.nn.Module,
    state_dict: Mapping[str, Any],
    *,
    strict: bool = False,
    allow_partial: bool = False,
) -> dict[str, object]:
    """Load weights without allowing silent random/uninitialized model regions.

    ``strict=False`` permits extra checkpoint keys, but by default every key in
    the current model must still be present with a compatible tensor shape.
    Intentional transfer learning must opt into ``allow_partial=True`` and must
    contain at least one compatible current-model key.
    """

    if not isinstance(state_dict, Mapping):
        raise TypeError("state_dict must be a mapping")
    model_state = model.state_dict()
    if not model_state:
        raise CheckpointStateCoverageError("target model exposes no state to load")

    filtered_state: dict[str, Any] = {}
    unexpected_keys: list[str] = []
    shape_mismatch_keys: list[str] = []
    type_mismatch_keys: list[str] = []
    dtype_mismatch_keys: list[str] = []
    nonfinite_keys: list[str] = []
    for raw_key, value in state_dict.items():
        key = str(raw_key)
        if key not in model_state:
            unexpected_keys.append(key)
            continue
        reference = model_state[key]
        if torch.is_tensor(value) != torch.is_tensor(reference):
            type_mismatch_keys.append(key)
            continue
        if torch.is_tensor(value):
            if tuple(value.shape) != tuple(reference.shape):
                shape_mismatch_keys.append(key)
                continue
            if value.dtype != reference.dtype:
                dtype_mismatch_keys.append(key)
                continue
            if (value.is_floating_point() or value.is_complex()) and not bool(
                torch.isfinite(value).all().item()
            ):
                nonfinite_keys.append(key)
                continue
        filtered_state[key] = value

    matched_keys = list(filtered_state)
    missing_keys = [key for key in model_state if key not in filtered_state]
    if not matched_keys:
        raise CheckpointStateCoverageError(
            "checkpoint has zero compatible keys for the current model"
        )
    if nonfinite_keys:
        raise CheckpointStateCoverageError(
            "checkpoint contains non-finite current-model tensors: "
            + ", ".join(nonfinite_keys[:8])
        )
    incompatible_keys = (
        missing_keys
        or shape_mismatch_keys
        or type_mismatch_keys
        or dtype_mismatch_keys
    )
    if bool(strict) and (incompatible_keys or unexpected_keys):
        raise CheckpointStateCoverageError(
            "strict checkpoint key/type/shape/dtype coverage failed: "
            f"missing={len(missing_keys)}, unexpected={len(unexpected_keys)}, "
            f"shape_mismatch={len(shape_mismatch_keys)}, "
            f"type_mismatch={len(type_mismatch_keys)}, "
            f"dtype_mismatch={len(dtype_mismatch_keys)}"
        )
    if incompatible_keys and not bool(allow_partial):
        raise CheckpointStateCoverageError(
            "checkpoint does not fully cover the current model: "
            f"missing={len(missing_keys)}, shape_mismatch={len(shape_mismatch_keys)}, "
            f"type_mismatch={len(type_mismatch_keys)}, "
            f"dtype_mismatch={len(dtype_mismatch_keys)}; partial loading requires "
            "an explicit allow_partial=True development-only decision"
        )
    load_result = model.load_state_dict(filtered_state, strict=bool(strict))

    returned_missing = list(getattr(load_result, "missing_keys", []))
    returned_unexpected = list(getattr(load_result, "unexpected_keys", []))
    if not bool(allow_partial) and (returned_missing or returned_unexpected):
        raise CheckpointStateCoverageError(
            "PyTorch reported incomplete checkpoint coverage after validation"
        )

    model_tensor_numel = sum(
        int(value.numel()) for value in model_state.values() if torch.is_tensor(value)
    )
    matched_tensor_numel = sum(
        int(model_state[key].numel())
        for key in matched_keys
        if key in model_state and torch.is_tensor(model_state[key])
    )
    tensor_coverage = (
        float(matched_tensor_numel) / float(model_tensor_numel)
        if model_tensor_numel > 0
        else float(len(matched_keys)) / float(len(model_state))
    )
    return {
        "strict": bool(strict),
        "allow_partial": bool(allow_partial),
        "model_keys_count": int(len(model_state)),
        "matched_keys_count": int(len(matched_keys)),
        "tensor_numel_coverage": float(tensor_coverage),
        "missing_keys_count": int(len(missing_keys)),
        "missing_keys": missing_keys[:64],
        "unexpected_keys_count": int(len(unexpected_keys)),
        "unexpected_keys": unexpected_keys[:64],
        "shape_mismatch_count": int(len(shape_mismatch_keys)),
        "shape_mismatch_keys": shape_mismatch_keys[:64],
        "type_mismatch_count": int(len(type_mismatch_keys)),
        "type_mismatch_keys": type_mismatch_keys[:64],
        "dtype_mismatch_count": int(len(dtype_mismatch_keys)),
        "dtype_mismatch_keys": dtype_mismatch_keys[:64],
        "nonfinite_keys_count": int(len(nonfinite_keys)),
        "nonfinite_keys": nonfinite_keys[:64],
    }

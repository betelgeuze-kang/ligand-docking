"""Fail-closed checkpoint loading for Engine v2 runtime consumers."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

import torch

from betelgeuze_engine_v2.contracts import CHECKPOINT_SCHEMA_VERSION
from betelgeuze_engine_v2.runtime import (
    RESIDUE_VOCABULARY,
    model_architecture_fingerprint,
    runtime_contract_fingerprint,
    state_dict_fingerprint,
)


CHECKPOINT_CONTRACT_SCHEMA_ID = (
    f"betelgeuze.engine_v2_checkpoint/{CHECKPOINT_SCHEMA_VERSION}"
)
DEFAULT_STATE_DICT_KEYS = (
    "state_dict",
    "model_state_dict",
    "airouter_state_dict",
    "model",
    "weights",
)


class CheckpointContractError(RuntimeError):
    """Checkpoint metadata is absent, incompatible, or internally inconsistent."""


class CheckpointStateCoverageError(CheckpointContractError):
    """Checkpoint state does not fully and safely cover the target model."""


def canonical_model(model: torch.nn.Module) -> torch.nn.Module:
    current = model
    seen: set[int] = set()
    while isinstance(current, torch.nn.Module) and id(current) not in seen:
        seen.add(id(current))
        original = getattr(current, "_orig_mod", None)
        if not isinstance(original, torch.nn.Module):
            break
        current = original
    return current


def canonical_model_state_dict(model: torch.nn.Module) -> Mapping[str, Any]:
    return canonical_model(model).state_dict()


def resolve_checkpoint_state_dict(
    payload: object,
    *,
    candidate_keys: Sequence[str] = DEFAULT_STATE_DICT_KEYS,
) -> tuple[Mapping[str, Any], str]:
    if isinstance(payload, Mapping):
        for key in candidate_keys:
            candidate = payload.get(key)
            if isinstance(candidate, Mapping):
                return candidate, str(key)
        if payload:
            has_tensor_value = any(torch.is_tensor(value) for value in payload.values())
            if has_tensor_value and all(isinstance(key, str) for key in payload):
                return payload, "root"
    raise CheckpointContractError(
        "checkpoint payload does not contain a recognizable model state_dict"
    )


def checkpoint_contract_metadata(
    model: torch.nn.Module,
    state_dict: Mapping[str, Any],
    *,
    runtime_input_schema: Mapping[str, object],
    config: Mapping[str, object],
) -> dict[str, object]:
    architecture_sha = model_architecture_fingerprint(canonical_model(model))
    runtime_sha = runtime_contract_fingerprint(
        architecture_fingerprint_sha256=architecture_sha,
        runtime_input_schema=runtime_input_schema,
        vocabulary_metadata=RESIDUE_VOCABULARY.to_dict(),
        config=config,
    )
    return {
        "schema_id": CHECKPOINT_CONTRACT_SCHEMA_ID,
        "architecture_fingerprint_sha256": architecture_sha,
        "runtime_contract_fingerprint_sha256": runtime_sha,
        "residue_vocabulary_fingerprint_sha256": RESIDUE_VOCABULARY.fingerprint_sha256,
        "state_dict_fingerprint_sha256": state_dict_fingerprint(state_dict),
        "strict_state_coverage_required": True,
        "partial_state_loading_allowed": False,
    }


def require_checkpoint_contract(
    payload: object,
    model: torch.nn.Module,
    state_dict: Mapping[str, Any],
    *,
    runtime_input_schema: Mapping[str, object],
    config: Mapping[str, object],
) -> Mapping[str, object]:
    if not isinstance(payload, Mapping):
        raise CheckpointContractError("checkpoint payload must be a mapping")
    metadata = payload.get("checkpoint_contract")
    if not isinstance(metadata, Mapping):
        raise CheckpointContractError(
            "checkpoint has no Engine v2 checkpoint_contract metadata"
        )
    expected = checkpoint_contract_metadata(
        model,
        state_dict,
        runtime_input_schema=runtime_input_schema,
        config=config,
    )
    if metadata.get("schema_id") != CHECKPOINT_CONTRACT_SCHEMA_ID:
        raise CheckpointContractError("checkpoint contract schema mismatch")
    keys = (
        "architecture_fingerprint_sha256",
        "runtime_contract_fingerprint_sha256",
        "residue_vocabulary_fingerprint_sha256",
        "state_dict_fingerprint_sha256",
    )
    mismatched = [key for key in keys if metadata.get(key) != expected[key]]
    if mismatched:
        raise CheckpointContractError(
            "checkpoint fingerprint mismatch for: " + ", ".join(mismatched)
        )
    if metadata.get("strict_state_coverage_required") is not True:
        raise CheckpointContractError("checkpoint does not require strict state coverage")
    if metadata.get("partial_state_loading_allowed") is not False:
        raise CheckpointContractError("checkpoint permits unsafe partial state loading")
    return metadata


def load_state_dict_fail_closed(
    model: torch.nn.Module,
    state_dict: Mapping[str, Any],
    *,
    strict: bool = True,
    allow_partial: bool = False,
) -> dict[str, object]:
    """Load only finite, dtype/shape-compatible, fully covering model state."""

    if allow_partial:
        raise CheckpointStateCoverageError(
            "partial loading is not allowed by the Engine v2 checkpoint contract"
        )
    if not strict:
        raise CheckpointStateCoverageError(
            "strict=False is not allowed by the Engine v2 checkpoint contract"
        )
    if not isinstance(state_dict, Mapping):
        raise TypeError("state_dict must be a mapping")

    target = canonical_model(model)
    model_state = target.state_dict()
    if not model_state:
        raise CheckpointStateCoverageError("target model exposes no state to load")

    state_keys = {str(key) for key in state_dict}
    model_keys = set(model_state)
    missing_keys = sorted(model_keys - state_keys)
    unexpected_keys = sorted(state_keys - model_keys)
    shape_mismatch: list[str] = []
    type_mismatch: list[str] = []
    dtype_mismatch: list[str] = []
    nonfinite: list[str] = []
    normalized: dict[str, Any] = {}

    for key in sorted(model_keys & state_keys):
        value = state_dict[key]
        reference = model_state[key]
        if torch.is_tensor(value) != torch.is_tensor(reference):
            type_mismatch.append(key)
            continue
        if torch.is_tensor(value):
            if tuple(value.shape) != tuple(reference.shape):
                shape_mismatch.append(key)
                continue
            if value.dtype != reference.dtype:
                dtype_mismatch.append(key)
                continue
            if (value.is_floating_point() or value.is_complex()) and not bool(
                torch.isfinite(value).all().item()
            ):
                nonfinite.append(key)
                continue
        normalized[key] = value

    if missing_keys or unexpected_keys or shape_mismatch or type_mismatch or dtype_mismatch or nonfinite:
        raise CheckpointStateCoverageError(
            "strict checkpoint coverage failed: "
            f"missing={len(missing_keys)}, unexpected={len(unexpected_keys)}, "
            f"shape={len(shape_mismatch)}, type={len(type_mismatch)}, "
            f"dtype={len(dtype_mismatch)}, nonfinite={len(nonfinite)}"
        )

    load_result = target.load_state_dict(normalized, strict=True)
    returned_missing = list(getattr(load_result, "missing_keys", []))
    returned_unexpected = list(getattr(load_result, "unexpected_keys", []))
    if returned_missing or returned_unexpected:
        raise CheckpointStateCoverageError(
            "PyTorch reported incomplete strict checkpoint coverage"
        )

    tensor_numel = sum(
        int(value.numel())
        for value in model_state.values()
        if torch.is_tensor(value)
    )
    return {
        "strict": True,
        "allow_partial": False,
        "model_keys_count": len(model_state),
        "matched_keys_count": len(normalized),
        "tensor_numel_coverage": 1.0,
        "tensor_numel": tensor_numel,
        "state_dict_fingerprint_sha256": state_dict_fingerprint(normalized),
    }


def load_checkpoint_payload_fail_closed(
    model: torch.nn.Module,
    payload: object,
    *,
    runtime_input_schema: Mapping[str, object],
    config: Mapping[str, object],
) -> dict[str, object]:
    state_dict, state_source = resolve_checkpoint_state_dict(payload)
    require_checkpoint_contract(
        payload,
        model,
        state_dict,
        runtime_input_schema=runtime_input_schema,
        config=config,
    )
    report = load_state_dict_fail_closed(model, state_dict)
    report["state_source"] = state_source
    report["checkpoint_contract_schema_id"] = CHECKPOINT_CONTRACT_SCHEMA_ID
    return report


__all__ = [
    "CHECKPOINT_CONTRACT_SCHEMA_ID",
    "CheckpointContractError",
    "CheckpointStateCoverageError",
    "canonical_model",
    "canonical_model_state_dict",
    "checkpoint_contract_metadata",
    "load_checkpoint_payload_fail_closed",
    "load_state_dict_fail_closed",
    "require_checkpoint_contract",
    "resolve_checkpoint_state_dict",
]

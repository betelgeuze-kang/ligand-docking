"""Deterministic fingerprints for runtime and checkpoint compatibility."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping

import torch


class FingerprintError(ValueError):
    """A payload cannot be represented by the deterministic fingerprint contract."""


def canonical_json_sha256(payload: object) -> str:
    try:
        encoded = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise FingerprintError("payload is not canonical JSON data") from exc
    return hashlib.sha256(encoded).hexdigest()


def model_architecture_payload(model: torch.nn.Module) -> dict[str, Any]:
    state = model.state_dict()
    return {
        "model_class": f"{model.__class__.__module__}.{model.__class__.__qualname__}",
        "state": [
            {
                "key": str(key),
                "shape": list(value.shape) if torch.is_tensor(value) else None,
                "dtype": str(value.dtype).removeprefix("torch.")
                if torch.is_tensor(value)
                else type(value).__name__,
                "tensor": bool(torch.is_tensor(value)),
            }
            for key, value in sorted(state.items())
        ],
    }


def model_architecture_fingerprint(model: torch.nn.Module) -> str:
    return canonical_json_sha256(model_architecture_payload(model))


def _tensor_bytes(value: torch.Tensor) -> bytes:
    tensor = value.detach().cpu().contiguous()
    if tensor.layout != torch.strided:
        raise FingerprintError("checkpoint fingerprint supports strided tensors only")
    byte_view = tensor.view(torch.uint8).reshape(-1)
    return bytes(byte_view.tolist())


def state_dict_fingerprint(state_dict: Mapping[str, Any]) -> str:
    """Hash state keys, tensor metadata, and raw tensor bytes without NumPy."""

    digest = hashlib.sha256()
    for raw_key, value in sorted(state_dict.items(), key=lambda item: str(item[0])):
        key = str(raw_key)
        digest.update(key.encode("utf-8"))
        digest.update(b"\0")
        if not torch.is_tensor(value):
            digest.update(b"non_tensor\0")
            digest.update(canonical_json_sha256(value).encode("ascii"))
            continue
        digest.update(str(value.dtype).encode("ascii"))
        digest.update(b"\0")
        digest.update(str(tuple(value.shape)).encode("ascii"))
        digest.update(b"\0")
        digest.update(_tensor_bytes(value))
        digest.update(b"\0")
    return digest.hexdigest()


def runtime_contract_payload(
    *,
    architecture_fingerprint_sha256: str,
    runtime_input_schema: Mapping[str, object],
    vocabulary_metadata: Mapping[str, object],
    config: Mapping[str, object],
) -> dict[str, object]:
    return {
        "architecture_fingerprint_sha256": str(architecture_fingerprint_sha256),
        "runtime_input_schema": dict(runtime_input_schema),
        "vocabulary": dict(vocabulary_metadata),
        "config": dict(config),
    }


def runtime_contract_fingerprint(
    *,
    architecture_fingerprint_sha256: str,
    runtime_input_schema: Mapping[str, object],
    vocabulary_metadata: Mapping[str, object],
    config: Mapping[str, object],
) -> str:
    return canonical_json_sha256(
        runtime_contract_payload(
            architecture_fingerprint_sha256=architecture_fingerprint_sha256,
            runtime_input_schema=runtime_input_schema,
            vocabulary_metadata=vocabulary_metadata,
            config=config,
        )
    )


__all__ = [
    "FingerprintError",
    "canonical_json_sha256",
    "model_architecture_fingerprint",
    "model_architecture_payload",
    "runtime_contract_fingerprint",
    "runtime_contract_payload",
    "state_dict_fingerprint",
]

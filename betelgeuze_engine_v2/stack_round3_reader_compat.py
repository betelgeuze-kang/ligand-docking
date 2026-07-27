"""Separate strict canonical byte artifacts from compatible JSON text input.

The historical convenience API accepted JSON text produced by standard
``json.dumps`` settings. Byte artifacts now remain byte-canonical, while text
input is parsed with duplicate-key and resource checks and normalized to the
canonical representation before reconstruction.
"""

from __future__ import annotations

import hashlib
import json
import sys

import torch


STACK_ROUND3_READER_COMPAT_SCHEMA_ID = (
    "betelgeuze.engine_v2_stack_round3_reader_compat/1.0.0"
)


def install_stack_round3_reader_compat() -> str:
    marker = "_betelgeuze_stack_round3_reader_compat_sha256"
    existing = getattr(sys, marker, None)
    if isinstance(existing, str):
        return existing

    from betelgeuze_engine_v2 import molecular as molecular_package
    from betelgeuze_engine_v2 import stack_round3_molecular as round3
    from betelgeuze_engine_v2.molecular import serialization

    strict_byte_reader = serialization.all_atom_system_from_canonical_json

    def compatible_reader(
        source: str | bytes,
        *,
        device: torch.device | str = "cpu",
    ):
        if isinstance(source, bytes):
            return strict_byte_reader(source, device=device)
        if not isinstance(source, str):
            raise TypeError("canonical system source must be str or bytes")
        raw = source.encode("utf-8")
        if not raw or len(raw) > round3.CANONICAL_SYSTEM_MAX_BYTES:
            raise serialization.CanonicalSerializationError(
                "canonical system document exceeds its byte bound"
            )
        try:
            text = raw.decode("ascii")
            parsed = json.loads(
                text,
                object_pairs_hook=round3._reject_duplicate_pairs,
            )
            round3._bounded_json_walk(parsed)
            round3._validate_tensor_dtypes(parsed)
            canonical = json.dumps(
                parsed,
                ensure_ascii=True,
                allow_nan=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("ascii")
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
            raise serialization.CanonicalSerializationError(
                "canonical system text is invalid or ambiguous"
            ) from exc
        return strict_byte_reader(canonical, device=device)

    serialization.all_atom_system_from_canonical_json = compatible_reader
    molecular_package.all_atom_system_from_canonical_json = compatible_reader

    receipt = hashlib.sha256(
        json.dumps(
            {
                "schema_id": STACK_ROUND3_READER_COMPAT_SCHEMA_ID,
                "byte_artifacts_require_canonical_bytes": True,
                "text_input_is_canonicalized_after_duplicate_key_checks": True,
                "text_resource_bounds_enforced": True,
                "scientifically_validated": False,
                "claim_safe": False,
            },
            ensure_ascii=True,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("ascii")
    ).hexdigest()
    setattr(sys, marker, receipt)
    return receipt


__all__ = [
    "STACK_ROUND3_READER_COMPAT_SCHEMA_ID",
    "install_stack_round3_reader_compat",
]

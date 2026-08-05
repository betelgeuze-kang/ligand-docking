"""Compatibility receipt for canonical one-shot result binding.

The canonical writer lives in ``source_paired_clearance_one_shot_result``. This
module intentionally performs no import-time mutation.
"""

from __future__ import annotations

import hashlib
import json


SOURCE_PAIRED_CLEARANCE_ONE_SHOT_RESULT_BINDING_SCHEMA_ID = (
    "betelgeuze.engine_v2_source_paired_clearance_one_shot_result_binding/2.0.0"
)


def _sha256(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("ascii")
    ).hexdigest()


def install_source_paired_clearance_one_shot_result_binding() -> str:
    """Return a compatibility receipt without replacing result functions."""

    return _sha256(
        {
            "schema_id": (
                SOURCE_PAIRED_CLEARANCE_ONE_SHOT_RESULT_BINDING_SCHEMA_ID
            ),
            "canonical_result_module_owns_writer": True,
            "module_mutation_performed": False,
            "historical_ab_execution_authorized": False,
            "fresh_execution_authorized": False,
            "product_execution_authorized": False,
            "public_or_scientific_claim_authorized": False,
        }
    )


__all__ = [
    "SOURCE_PAIRED_CLEARANCE_ONE_SHOT_RESULT_BINDING_SCHEMA_ID",
    "install_source_paired_clearance_one_shot_result_binding",
]

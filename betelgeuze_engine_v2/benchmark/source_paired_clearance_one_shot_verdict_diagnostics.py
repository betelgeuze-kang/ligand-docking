"""Compatibility metadata for canonical nonblocking verdict diagnostics.

The canonical verdict builder emits the legacy diagnostic fields directly after
deriving the hard No-Go decision. This module performs no import-time mutation.
"""

from __future__ import annotations

import hashlib
import json


SOURCE_PAIRED_CLEARANCE_ONE_SHOT_VERDICT_DIAGNOSTICS_SCHEMA_ID = (
    "betelgeuze.engine_v2_source_paired_clearance_one_shot_verdict_diagnostics/2.0.0"
)
LEGACY_NONBLOCKING_DIAGNOSTIC_KEYS = (
    "shadow_eligible_candidate_without_new_case_recovery",
    "no_exact_valid_case_increase",
    "no_invalid_top1_reduction",
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


def install_source_paired_clearance_one_shot_verdict_diagnostics() -> str:
    """Return a compatibility receipt without replacing the verdict builder."""

    return _sha256(
        {
            "schema_id": (
                SOURCE_PAIRED_CLEARANCE_ONE_SHOT_VERDICT_DIAGNOSTICS_SCHEMA_ID
            ),
            "legacy_nonblocking_diagnostic_keys": list(
                LEGACY_NONBLOCKING_DIAGNOSTIC_KEYS
            ),
            "canonical_verdict_builder_emits_diagnostics": True,
            "diagnostics_do_not_participate_in_verdict": True,
            "module_mutation_performed": False,
            "fresh_execution_authorized": False,
            "product_execution_authorized": False,
            "public_or_scientific_claim_authorized": False,
        }
    )


__all__ = [
    "LEGACY_NONBLOCKING_DIAGNOSTIC_KEYS",
    "SOURCE_PAIRED_CLEARANCE_ONE_SHOT_VERDICT_DIAGNOSTICS_SCHEMA_ID",
    "install_source_paired_clearance_one_shot_verdict_diagnostics",
]

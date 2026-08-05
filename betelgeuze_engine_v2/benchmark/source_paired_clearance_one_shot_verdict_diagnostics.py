"""Retain legacy one-shot decision diagnostics without granting veto authority."""

from __future__ import annotations

import hashlib
import json
import sys


SOURCE_PAIRED_CLEARANCE_ONE_SHOT_VERDICT_DIAGNOSTICS_SCHEMA_ID = (
    "betelgeuze.engine_v2_source_paired_clearance_one_shot_verdict_diagnostics/1.0.0"
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
    """Add historical diagnostic fields after the coherent verdict is decided."""

    marker = "_betelgeuze_source_paired_clearance_one_shot_verdict_diagnostics_sha256"
    existing = getattr(sys, marker, None)
    if isinstance(existing, str):
        return existing

    from . import source_paired_clearance_one_shot_ab as one_shot

    original = one_shot.build_verdict
    if not getattr(original, "_betelgeuze_legacy_nonblocking_diagnostics", False):

        def build_verdict(inputs, *, policy_sha256: str):
            receipt = original(inputs, policy_sha256=policy_sha256)
            no_go_criteria = dict(receipt["no_go_criteria"])
            primary_go = any(receipt["go_criteria"].values())
            no_go_criteria.update(
                {
                    "shadow_eligible_candidate_without_new_case_recovery": (
                        inputs.shadow_eligible_candidate_count > 0 and not primary_go
                    ),
                    "no_exact_valid_case_increase": not receipt["go_criteria"][
                        "new_exact_valid_candidate_in_previously_uncovered_case"
                    ],
                    "no_invalid_top1_reduction": (
                        len(set(inputs.experimental_invalid_top1_case_ids))
                        >= len(set(inputs.baseline_invalid_top1_case_ids))
                    ),
                }
            )
            receipt["no_go_criteria"] = no_go_criteria
            receipt["receipt_sha256"] = one_shot.sha256_payload(
                {key: value for key, value in receipt.items() if key != "receipt_sha256"}
            )
            return receipt

        build_verdict._betelgeuze_legacy_nonblocking_diagnostics = True
        one_shot.build_verdict = build_verdict

    receipt = _sha256(
        {
            "schema_id": (
                SOURCE_PAIRED_CLEARANCE_ONE_SHOT_VERDICT_DIAGNOSTICS_SCHEMA_ID
            ),
            "legacy_nonblocking_diagnostic_keys": list(
                LEGACY_NONBLOCKING_DIAGNOSTIC_KEYS
            ),
            "diagnostics_do_not_participate_in_verdict": True,
            "hard_no_go_keys_come_only_from_policy_1_1_0": True,
            "fresh_execution_authorized": False,
            "product_execution_authorized": False,
            "public_or_scientific_claim_authorized": False,
        }
    )
    setattr(sys, marker, receipt)
    return receipt


__all__ = [
    "LEGACY_NONBLOCKING_DIAGNOSTIC_KEYS",
    "SOURCE_PAIRED_CLEARANCE_ONE_SHOT_VERDICT_DIAGNOSTICS_SCHEMA_ID",
    "install_source_paired_clearance_one_shot_verdict_diagnostics",
]

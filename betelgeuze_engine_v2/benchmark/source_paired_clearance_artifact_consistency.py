"""Fail-closed pose-artifact to coordinate consistency for clearance evidence.

The activation receipt models a pose artifact SHA-256 as the identity of immutable
serialized pose bytes. One artifact identity therefore cannot legitimately bind two
different coordinate identities in one arm or across the paired A/B arms.
"""

from __future__ import annotations

import hashlib
import json
import sys
from collections.abc import Sequence


SOURCE_PAIRED_CLEARANCE_ARTIFACT_CONSISTENCY_SCHEMA_ID = (
    "betelgeuze.engine_v2_source_paired_clearance_artifact_consistency/1.2.0"
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


def _assert_pose_artifact_coordinate_consistency(
    rows: Sequence[object],
    *,
    scope: str,
) -> None:
    from .source_paired_clearance_activation import (
        SourcePairedClearanceActivationEvidenceError,
        SourcePairedClearanceCandidateEvidenceV1,
    )

    bindings: dict[str, str] = {}
    for row in rows:
        if type(row) is not SourcePairedClearanceCandidateEvidenceV1:
            raise TypeError("pose-artifact consistency rows must be exact candidate evidence")
        previous = bindings.setdefault(
            row.pose_artifact_sha256,
            row.coordinate_sha256,
        )
        if previous != row.coordinate_sha256:
            raise SourcePairedClearanceActivationEvidenceError(
                f"{scope} reuses one pose artifact for different coordinates"
            )


def install_source_paired_clearance_artifact_consistency() -> str:
    """Install idempotent activation, one-shot, and result-state guards."""

    marker = "_betelgeuze_source_paired_clearance_artifact_consistency_sha256"
    existing = getattr(sys, marker, None)
    if isinstance(existing, str):
        return existing

    from .source_paired_clearance_activation import (
        SourcePairedClearanceArmRankingReceiptV1,
        SourcePairedClearanceSelectionActivationReceiptV1,
    )
    from .source_paired_clearance_one_shot_binding import (
        install_source_paired_clearance_one_shot_binding,
    )
    from .source_paired_clearance_one_shot_result_binding import (
        install_source_paired_clearance_one_shot_result_binding,
    )
    from .source_paired_clearance_one_shot_verdict_diagnostics import (
        install_source_paired_clearance_one_shot_verdict_diagnostics,
    )

    arm_type = SourcePairedClearanceArmRankingReceiptV1
    outer_type = SourcePairedClearanceSelectionActivationReceiptV1
    original_arm_post_init = arm_type.__post_init__
    original_outer_post_init = outer_type.__post_init__
    original_arm_receipt = arm_type.receipt_sha256.fget
    original_outer_receipt = outer_type.receipt_sha256.fget
    if original_arm_receipt is None or original_outer_receipt is None:
        raise RuntimeError("clearance receipt SHA properties are unavailable")

    def arm_post_init(self) -> None:
        original_arm_post_init(self)
        _assert_pose_artifact_coordinate_consistency(
            self.candidate_rows,
            scope=f"{self.arm} arm",
        )

    def arm_receipt_sha256(self) -> str:
        _assert_pose_artifact_coordinate_consistency(
            self.candidate_rows,
            scope=f"{self.arm} arm",
        )
        return original_arm_receipt(self)

    def outer_post_init(self) -> None:
        original_outer_post_init(self)
        _assert_pose_artifact_coordinate_consistency(
            (*self.baseline_arm.candidate_rows, *self.experimental_arm.candidate_rows),
            scope="paired activation arms",
        )

    def outer_receipt_sha256(self) -> str:
        _assert_pose_artifact_coordinate_consistency(
            (*self.baseline_arm.candidate_rows, *self.experimental_arm.candidate_rows),
            scope="paired activation arms",
        )
        return original_outer_receipt(self)

    arm_type.__post_init__ = arm_post_init
    arm_type.receipt_sha256 = property(arm_receipt_sha256)
    outer_type.__post_init__ = outer_post_init
    outer_type.receipt_sha256 = property(outer_receipt_sha256)

    one_shot_binding_sha256 = install_source_paired_clearance_one_shot_binding()
    verdict_diagnostics_sha256 = (
        install_source_paired_clearance_one_shot_verdict_diagnostics()
    )
    result_binding_sha256 = install_source_paired_clearance_one_shot_result_binding()
    receipt = _sha256(
        {
            "schema_id": SOURCE_PAIRED_CLEARANCE_ARTIFACT_CONSISTENCY_SCHEMA_ID,
            "within_arm_pose_artifact_coordinate_consistency_required": True,
            "cross_arm_pose_artifact_coordinate_consistency_required": True,
            "construction_time_check": True,
            "receipt_access_time_check": True,
            "one_shot_source_policy_binding_sha256": one_shot_binding_sha256,
            "one_shot_verdict_diagnostics_sha256": verdict_diagnostics_sha256,
            "one_shot_result_binding_sha256": result_binding_sha256,
            "historical_ab_execution_authorized": False,
            "fresh_execution_authorized": False,
            "product_or_claim_authority": False,
        }
    )
    setattr(sys, marker, receipt)
    return receipt


__all__ = [
    "SOURCE_PAIRED_CLEARANCE_ARTIFACT_CONSISTENCY_SCHEMA_ID",
    "install_source_paired_clearance_artifact_consistency",
]

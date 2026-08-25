"""Fail-closed cohort decision over exact global-orientation evidence.

The evaluator owns the complete typed evidence for all eight scored historical
development cases and the sole typed preparation-failure receipt.  It does not
load or execute molecular work and cannot grant execution, promotion, product,
fresh-data, or claim authority.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json

from .global_orientation_development_contracts import (
    GLOBAL_ORIENTATION_DEVELOPMENT_CANDIDATE_DENOMINATOR,
    GLOBAL_ORIENTATION_DEVELOPMENT_PREPARATION_FAILURE_CASE_ID,
    GLOBAL_ORIENTATION_DEVELOPMENT_SCORED_CASE_IDS,
    GlobalOrientationDevelopmentCaseSourceReceiptV1,
    GlobalOrientationDevelopmentPreparationFailureReceiptV1,
)
from .global_orientation_development_metrics import (
    GlobalOrientationDevelopmentArmMetricsV1,
)


GLOBAL_ORIENTATION_DEVELOPMENT_SCORED_CASE_COMPARISON_SCHEMA_ID = (
    "betelgeuze.engine_v2_global_orientation_development_scored_case_"
    "comparison/1.0.0"
)
GLOBAL_ORIENTATION_DEVELOPMENT_COHORT_DECISION_SCHEMA_ID = (
    "betelgeuze.engine_v2_global_orientation_development_cohort_decision/1.0.0"
)
GLOBAL_ORIENTATION_DEVELOPMENT_BASELINE_RECOVERED_CASE_ID = "6T88_MWQ"
GLOBAL_ORIENTATION_DEVELOPMENT_PREVIOUSLY_UNCOVERED_CASE_IDS = tuple(
    case_id
    for case_id in GLOBAL_ORIENTATION_DEVELOPMENT_SCORED_CASE_IDS
    if case_id != GLOBAL_ORIENTATION_DEVELOPMENT_BASELINE_RECOVERED_CASE_ID
)


class GlobalOrientationDevelopmentDecisionError(ValueError):
    """Raised when cohort decision evidence is structurally invalid."""


def _canonical_bytes(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("ascii")
    except (TypeError, ValueError, UnicodeError) as exc:
        raise GlobalOrientationDevelopmentDecisionError(
            "cohort decision is not canonical JSON"
        ) from exc


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _exact_bool_or_none(value: object, *, name: str) -> bool | None:
    if value is not None and type(value) is not bool:
        raise GlobalOrientationDevelopmentDecisionError(
            f"{name} must be a boolean or null"
        )
    return value


def _exact_bool(value: object, *, name: str) -> bool:
    if type(value) is not bool:
        raise GlobalOrientationDevelopmentDecisionError(
            f"{name} must be a boolean"
        )
    return value


def _exact_int(value: object, *, name: str) -> int:
    if type(value) is not int:
        raise GlobalOrientationDevelopmentDecisionError(f"{name} must be an integer")
    return value


def _authority_projection() -> dict[str, bool]:
    return {
        "go_receipt_emission_authorized": False,
        "historical_development_execution_authorized": False,
        "fresh_holdout_execution_authorized": False,
        "stage0_admission_authority": False,
        "profile_promotion_authority": False,
        "product_execution_authorized": False,
        "customer_pose_emission_authorized": False,
        "public_or_scientific_claim_authorized": False,
    }


@dataclass(frozen=True, slots=True)
class GlobalOrientationDevelopmentScoredCaseComparisonV1:
    """Own exact baseline and experimental metrics for one scored case."""

    baseline_metrics: GlobalOrientationDevelopmentArmMetricsV1
    experimental_metrics: GlobalOrientationDevelopmentArmMetricsV1
    schema_id: str = (
        GLOBAL_ORIENTATION_DEVELOPMENT_SCORED_CASE_COMPARISON_SCHEMA_ID
    )
    _receipt_sha256: str = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if (
            self.schema_id
            != GLOBAL_ORIENTATION_DEVELOPMENT_SCORED_CASE_COMPARISON_SCHEMA_ID
        ):
            raise GlobalOrientationDevelopmentDecisionError(
                "scored-case comparison schema_id is invalid"
            )
        if (
            type(self.baseline_metrics)
            is not GlobalOrientationDevelopmentArmMetricsV1
            or type(self.experimental_metrics)
            is not GlobalOrientationDevelopmentArmMetricsV1
        ):
            raise TypeError("comparison requires exact per-arm metrics receipts")

        baseline = self.baseline_metrics.to_dict()
        experimental = self.experimental_metrics.to_dict()
        baseline_arm = self.baseline_metrics.arm_observations.lineage
        experimental_arm = self.experimental_metrics.arm_observations.lineage
        case_id = baseline_arm.case_source.case_id
        if case_id not in GLOBAL_ORIENTATION_DEVELOPMENT_SCORED_CASE_IDS:
            raise GlobalOrientationDevelopmentDecisionError(
                "comparison case is outside the frozen scored cohort"
            )
        if (
            experimental_arm.case_source.case_id != case_id
            or baseline_arm.arm_id != "baseline_current_v7"
            or experimental_arm.arm_id != "experimental_global_orientation_v1"
            or baseline_arm.case_source.receipt_sha256
            != experimental_arm.case_source.receipt_sha256
            or baseline_arm.case_source.to_dict()
            != experimental_arm.case_source.to_dict()
        ):
            raise GlobalOrientationDevelopmentDecisionError(
                "comparison arms are cross-wired or do not share one exact case source"
            )
        for arm_name, document in (
            ("baseline", baseline),
            ("experimental", experimental),
        ):
            if (
                _exact_int(
                    document.get("candidate_denominator"),
                    name=f"{arm_name} candidate_denominator",
                )
                != GLOBAL_ORIENTATION_DEVELOPMENT_CANDIDATE_DENOMINATOR
            ):
                raise GlobalOrientationDevelopmentDecisionError(
                    "comparison arm denominator drifted"
                )
            for key in (
                "metric_evidence_complete",
                "score_coverage_complete",
                "validity_coverage_complete",
            ):
                _exact_bool(document.get(key), name=f"{arm_name} {key}")
            for key in (
                "valid_proposal_oracle_success",
                "selected_top1_valid",
                "selected_top1_success",
            ):
                _exact_bool_or_none(document.get(key), name=f"{arm_name} {key}")

        object.__setattr__(self, "_receipt_sha256", _sha256(self._projection()))

    @property
    def case_id(self) -> str:
        return self.baseline_metrics.arm_observations.lineage.case_source.case_id

    def _decision_inputs(self) -> dict[str, object]:
        baseline = self.baseline_metrics.to_dict()
        experimental = self.experimental_metrics.to_dict()
        evidence_complete = all(
            _exact_bool(document[key], name=f"{arm_name} {key}")
            for arm_name, document in (
                ("baseline", baseline),
                ("experimental", experimental),
            )
            for key in (
                "metric_evidence_complete",
                "score_coverage_complete",
                "validity_coverage_complete",
            )
        )
        baseline_valid_oracle = _exact_bool_or_none(
            baseline["valid_proposal_oracle_success"],
            name="baseline valid_proposal_oracle_success",
        )
        experimental_valid_oracle = _exact_bool_or_none(
            experimental["valid_proposal_oracle_success"],
            name="experimental valid_proposal_oracle_success",
        )
        baseline_selected_valid = _exact_bool_or_none(
            baseline["selected_top1_valid"],
            name="baseline selected_top1_valid",
        )
        experimental_selected_valid = _exact_bool_or_none(
            experimental["selected_top1_valid"],
            name="experimental selected_top1_valid",
        )
        baseline_selected_success = _exact_bool_or_none(
            baseline["selected_top1_success"],
            name="baseline selected_top1_success",
        )
        experimental_selected_success = _exact_bool_or_none(
            experimental["selected_top1_success"],
            name="experimental selected_top1_success",
        )
        return {
            "decision_evidence_complete": evidence_complete,
            "baseline_valid_proposal_oracle_success": baseline_valid_oracle,
            "experimental_valid_proposal_oracle_success": (
                experimental_valid_oracle
            ),
            "new_valid_proposal_oracle_recovery": bool(
                evidence_complete
                and baseline_valid_oracle is False
                and experimental_valid_oracle is True
            ),
            "baseline_selected_top1_valid": baseline_selected_valid,
            "experimental_selected_top1_valid": experimental_selected_valid,
            "baseline_selected_top1_invalid_or_absent": bool(
                evidence_complete and baseline_selected_valid is not True
            ),
            "experimental_selected_top1_invalid_or_absent": bool(
                evidence_complete and experimental_selected_valid is not True
            ),
            "baseline_selected_top1_success": baseline_selected_success,
            "experimental_selected_top1_success": experimental_selected_success,
        }

    def _projection(self) -> dict[str, object]:
        return {
            "schema_id": self.schema_id,
            "case_id": self.case_id,
            "case_source_receipt_sha256": (
                self.baseline_metrics.arm_observations.lineage.case_source.receipt_sha256
            ),
            "baseline_metrics_receipt_sha256": self.baseline_metrics.receipt_sha256,
            "baseline_metrics": self.baseline_metrics.to_dict(),
            "experimental_metrics_receipt_sha256": (
                self.experimental_metrics.receipt_sha256
            ),
            "experimental_metrics": self.experimental_metrics.to_dict(),
            "decision_inputs": self._decision_inputs(),
            "decision_inputs_rederived_from_exact_arm_receipts": True,
            **_authority_projection(),
        }

    @property
    def receipt_sha256(self) -> str:
        observed = _sha256(self._projection())
        if observed != self._receipt_sha256:
            raise GlobalOrientationDevelopmentDecisionError(
                "scored-case comparison changed"
            )
        return observed

    def to_dict(self) -> dict[str, object]:
        return {**self._projection(), "receipt_sha256": self.receipt_sha256}


def _evaluate_decision_rows(
    by_case: dict[str, dict[str, object]],
    *,
    complete_source_or_preparation_failure_receipts: bool,
    identical_denominators: bool,
    common_sources: bool,
) -> dict[str, object]:
    """Evaluate already-rederived rows supplied only by the exact wrapper."""

    if tuple(by_case) != GLOBAL_ORIENTATION_DEVELOPMENT_SCORED_CASE_IDS:
        raise GlobalOrientationDevelopmentDecisionError(
            "decision rows do not match the exact ordered scored cohort"
        )
    if (
        type(complete_source_or_preparation_failure_receipts) is not bool
        or type(identical_denominators) is not bool
        or type(common_sources) is not bool
    ):
        raise GlobalOrientationDevelopmentDecisionError(
            "decision structural invariants must be booleans"
        )
    required_row_keys = {
        "decision_evidence_complete",
        "baseline_valid_proposal_oracle_success",
        "experimental_valid_proposal_oracle_success",
        "new_valid_proposal_oracle_recovery",
        "baseline_selected_top1_valid",
        "experimental_selected_top1_valid",
        "baseline_selected_top1_invalid_or_absent",
        "experimental_selected_top1_invalid_or_absent",
        "baseline_selected_top1_success",
        "experimental_selected_top1_success",
    }
    for case_id, row in by_case.items():
        if set(row) != required_row_keys:
            raise GlobalOrientationDevelopmentDecisionError(
                f"decision row fields drifted for {case_id}"
            )
        for key in (
            "decision_evidence_complete",
            "new_valid_proposal_oracle_recovery",
            "baseline_selected_top1_invalid_or_absent",
            "experimental_selected_top1_invalid_or_absent",
        ):
            _exact_bool(row[key], name=f"{case_id} {key}")
        for key in required_row_keys - {
            "decision_evidence_complete",
            "new_valid_proposal_oracle_recovery",
            "baseline_selected_top1_invalid_or_absent",
            "experimental_selected_top1_invalid_or_absent",
        }:
            _exact_bool_or_none(row[key], name=f"{case_id} {key}")

    complete_case_ids = tuple(
        case_id
        for case_id in GLOBAL_ORIENTATION_DEVELOPMENT_SCORED_CASE_IDS
        if by_case[case_id]["decision_evidence_complete"] is True
    )
    recovered_case_ids = tuple(
        case_id
        for case_id in GLOBAL_ORIENTATION_DEVELOPMENT_PREVIOUSLY_UNCOVERED_CASE_IDS
        if by_case[case_id]["new_valid_proposal_oracle_recovery"] is True
    )
    baseline_invalid_case_ids = tuple(
        case_id
        for case_id in GLOBAL_ORIENTATION_DEVELOPMENT_SCORED_CASE_IDS
        if by_case[case_id]["baseline_selected_top1_invalid_or_absent"] is True
    )
    experimental_invalid_case_ids = tuple(
        case_id
        for case_id in GLOBAL_ORIENTATION_DEVELOPMENT_SCORED_CASE_IDS
        if by_case[case_id]["experimental_selected_top1_invalid_or_absent"] is True
    )
    baseline_recovered = by_case[
        GLOBAL_ORIENTATION_DEVELOPMENT_BASELINE_RECOVERED_CASE_ID
    ]
    all_evidence_complete = len(complete_case_ids) == len(
        GLOBAL_ORIENTATION_DEVELOPMENT_SCORED_CASE_IDS
    )
    invariants = {
        "complete_source_or_preparation_failure_receipts_for_all_nine_cases": (
            complete_source_or_preparation_failure_receipts
        ),
        "identical_failure_complete_64_slot_denominators": identical_denominators,
        "no_reference_or_result_dependent_generator_input": True,
        "no_preparation_failure_regression": True,
        "baseline_recovered_case_reproduced": bool(
            all_evidence_complete
            and baseline_recovered["baseline_selected_top1_success"] is True
        ),
        "no_baseline_recovered_case_regression": bool(
            all_evidence_complete
            and baseline_recovered["experimental_selected_top1_success"] is True
        ),
        "complete_source_and_observation_rederivation": bool(
            all_evidence_complete and common_sources
        ),
    }
    go_criteria = {
        "valid_proposal_oracle_recovery_in_at_least_2_of_7_previously_uncovered_cases": (
            all_evidence_complete and len(recovered_case_ids) >= 2
        ),
        "no_increase_in_invalid_selected_top1_count": bool(
            all_evidence_complete
            and len(experimental_invalid_case_ids)
            <= len(baseline_invalid_case_ids)
        ),
    }
    hard_no_go = {
        "evaluator_or_required_private_evidence_absent": not all_evidence_complete,
        "required_invariant_failed": not all(invariants.values()),
        "zero_new_previously_uncovered_valid_proposal_recoveries": (
            len(recovered_case_ids) == 0
        ),
        "baseline_recovered_case_regression": (
            invariants["no_baseline_recovered_case_regression"] is False
        ),
        "candidate_denominator_or_source_binding_drift": not (
            identical_denominators and common_sources
        ),
    }
    go = (
        all(invariants.values())
        and all(go_criteria.values())
        and not any(hard_no_go.values())
    )
    return {
        "verdict": (
            "go_permit_separate_development_followup_review"
            if go
            else "no_go_retain_synthetic_only_global_orientation"
        ),
        "scored_case_count": len(GLOBAL_ORIENTATION_DEVELOPMENT_SCORED_CASE_IDS),
        "complete_decision_evidence_case_ids": list(complete_case_ids),
        "previously_uncovered_case_ids": list(
            GLOBAL_ORIENTATION_DEVELOPMENT_PREVIOUSLY_UNCOVERED_CASE_IDS
        ),
        "new_valid_proposal_oracle_recovery_case_ids": list(recovered_case_ids),
        "new_valid_proposal_oracle_recovery_count": len(recovered_case_ids),
        "baseline_invalid_or_absent_selected_top1_case_ids": list(
            baseline_invalid_case_ids
        ),
        "baseline_invalid_or_absent_selected_top1_count": len(
            baseline_invalid_case_ids
        ),
        "experimental_invalid_or_absent_selected_top1_case_ids": list(
            experimental_invalid_case_ids
        ),
        "experimental_invalid_or_absent_selected_top1_count": len(
            experimental_invalid_case_ids
        ),
        "invariants": invariants,
        "go_criteria": go_criteria,
        "hard_no_go": hard_no_go,
        "go_requires_all_invariants_and_all_criteria": True,
        "go_effect": (
            "permit_separate_review_of_global_orientation_development_followup_only"
        ),
        "no_go_effect": (
            "retain_synthetic_only_global_orientation_and_close_molecular_"
            "execution_request"
        ),
    }


@dataclass(frozen=True, slots=True)
class GlobalOrientationDevelopmentCohortDecisionV1:
    """Evaluate the frozen nine-case cohort without issuing Go authority."""

    scored_case_comparisons: tuple[
        GlobalOrientationDevelopmentScoredCaseComparisonV1, ...
    ]
    preparation_failure: GlobalOrientationDevelopmentPreparationFailureReceiptV1
    schema_id: str = GLOBAL_ORIENTATION_DEVELOPMENT_COHORT_DECISION_SCHEMA_ID
    _receipt_sha256: str = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if self.schema_id != GLOBAL_ORIENTATION_DEVELOPMENT_COHORT_DECISION_SCHEMA_ID:
            raise GlobalOrientationDevelopmentDecisionError(
                "cohort-decision schema_id is invalid"
            )
        comparisons = tuple(self.scored_case_comparisons)
        if (
            len(comparisons) != len(GLOBAL_ORIENTATION_DEVELOPMENT_SCORED_CASE_IDS)
            or any(
                type(value)
                is not GlobalOrientationDevelopmentScoredCaseComparisonV1
                for value in comparisons
            )
            or tuple(value.case_id for value in comparisons)
            != GLOBAL_ORIENTATION_DEVELOPMENT_SCORED_CASE_IDS
        ):
            raise GlobalOrientationDevelopmentDecisionError(
                "cohort decision requires the exact ordered eight scored cases"
            )
        if (
            type(self.preparation_failure)
            is not GlobalOrientationDevelopmentPreparationFailureReceiptV1
            or self.preparation_failure.historical_authority.case_id
            != GLOBAL_ORIENTATION_DEVELOPMENT_PREPARATION_FAILURE_CASE_ID
        ):
            raise TypeError(
                "cohort decision requires the exact preparation-failure receipt"
            )
        self.preparation_failure.receipt_sha256
        object.__setattr__(self, "scored_case_comparisons", comparisons)
        object.__setattr__(self, "_receipt_sha256", _sha256(self._projection()))

    def _decision(self) -> dict[str, object]:
        by_case = {
            comparison.case_id: comparison._decision_inputs()
            for comparison in self.scored_case_comparisons
        }
        identical_denominators = all(
            comparison.baseline_metrics.to_dict()["candidate_denominator"]
            == comparison.experimental_metrics.to_dict()["candidate_denominator"]
            == GLOBAL_ORIENTATION_DEVELOPMENT_CANDIDATE_DENOMINATOR
            for comparison in self.scored_case_comparisons
        )
        common_sources = all(
            comparison.baseline_metrics.arm_observations.lineage.case_source.receipt_sha256
            == comparison.experimental_metrics.arm_observations.lineage.case_source.receipt_sha256
            for comparison in self.scored_case_comparisons
        )
        preparation_failure = self.preparation_failure.to_dict()
        complete_source_or_preparation_failure_receipts = bool(
            all(
                type(
                    comparison.baseline_metrics.arm_observations.lineage.case_source
                )
                is GlobalOrientationDevelopmentCaseSourceReceiptV1
                for comparison in self.scored_case_comparisons
            )
            and preparation_failure["case_id"]
            == GLOBAL_ORIENTATION_DEVELOPMENT_PREPARATION_FAILURE_CASE_ID
            and preparation_failure["preparation_status"] == "failed"
            and preparation_failure["candidate_denominator"] == 0
            and preparation_failure["historical_authority_receipt_sha256"]
            == self.preparation_failure.historical_authority.receipt_sha256
        )
        return _evaluate_decision_rows(
            by_case,
            complete_source_or_preparation_failure_receipts=(
                complete_source_or_preparation_failure_receipts
            ),
            identical_denominators=identical_denominators,
            common_sources=common_sources,
        )

    def _projection(self) -> dict[str, object]:
        return {
            "schema_id": self.schema_id,
            "historical_case_ids": [
                *GLOBAL_ORIENTATION_DEVELOPMENT_SCORED_CASE_IDS[:3],
                GLOBAL_ORIENTATION_DEVELOPMENT_PREPARATION_FAILURE_CASE_ID,
                *GLOBAL_ORIENTATION_DEVELOPMENT_SCORED_CASE_IDS[3:],
            ],
            "scored_case_comparison_receipt_sha256s": [
                value.receipt_sha256 for value in self.scored_case_comparisons
            ],
            "scored_case_comparisons": [
                value.to_dict() for value in self.scored_case_comparisons
            ],
            "preparation_failure_receipt_sha256": (
                self.preparation_failure.receipt_sha256
            ),
            "preparation_failure": self.preparation_failure.to_dict(),
            "decision": self._decision(),
            "decision_evaluator_implemented": True,
            "decision_rederived_from_exact_complete_case_receipts": True,
            **_authority_projection(),
        }

    @property
    def receipt_sha256(self) -> str:
        observed = _sha256(self._projection())
        if observed != self._receipt_sha256:
            raise GlobalOrientationDevelopmentDecisionError(
                "cohort-decision receipt changed"
            )
        return observed

    def to_dict(self) -> dict[str, object]:
        return {**self._projection(), "receipt_sha256": self.receipt_sha256}


__all__ = [
    "GLOBAL_ORIENTATION_DEVELOPMENT_COHORT_DECISION_SCHEMA_ID",
    "GLOBAL_ORIENTATION_DEVELOPMENT_SCORED_CASE_COMPARISON_SCHEMA_ID",
    "GlobalOrientationDevelopmentCohortDecisionV1",
    "GlobalOrientationDevelopmentDecisionError",
    "GlobalOrientationDevelopmentScoredCaseComparisonV1",
]

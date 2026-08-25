"""Deterministic decision evaluator for the fixed global-orientation protocol.

This module consumes only post-generation development observations. It cannot
run docking, open fresh data, promote a profile, enable a product path, or
authorize a scientific claim.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
import math
from typing import Sequence


DECISION_SCHEMA_ID = (
    "betelgeuze.engine_v2_global_orientation_development_decision/1.0.0"
)
CASE_IDS = (
    "5SD5_HWI",
    "5SIS_JSM",
    "6M2B_EZO",
    "6M73_FNR",
    "6T88_MWQ",
    "6TW5_9M2",
    "6TW7_NZB",
    "6VTA_AKN",
    "6WTN_RXT",
)
SCORED_CASE_IDS = tuple(case_id for case_id in CASE_IDS if case_id != "6M73_FNR")
UNCOVERED_CASE_IDS = (
    "5SD5_HWI",
    "5SIS_JSM",
    "6M2B_EZO",
    "6TW5_9M2",
    "6TW7_NZB",
    "6VTA_AKN",
    "6WTN_RXT",
)
BASELINE_RECOVERED_CASE_IDS = ("6T88_MWQ",)
RMSD_THRESHOLD_ANGSTROM = 2.0
CANDIDATE_DENOMINATOR_PER_ARM = 64
_RECOVERY_GO_CRITERION = (
    "valid_proposal_oracle_recovery_in_at_least_2_of_7_previously_uncovered_cases"
)
_INVALID_TOP1_GO_CRITERION = "no_increase_in_invalid_selected_top1_count"
_INVARIANT_FAILURE_ORDER = (
    "complete_source_and_observation_rederivation",
    "no_preparation_failure_regression",
    "identical_failure_complete_64_slot_denominators",
)
_HARD_NO_GO_ORDER = (
    "required_invariant_failed",
    "zero_new_previously_uncovered_valid_proposal_recoveries",
    "baseline_recovered_case_regression",
    "candidate_denominator_or_source_binding_drift",
)


class GlobalOrientationDevelopmentDecisionError(ValueError):
    """Raised when development decision evidence is incomplete or invalid."""


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _metric(value: object, *, name: str, required: bool) -> float | None:
    if value is None:
        if required:
            raise GlobalOrientationDevelopmentDecisionError(f"{name} is required")
        return None
    if type(value) not in {int, float}:
        raise GlobalOrientationDevelopmentDecisionError(
            f"{name} must be a finite non-negative number"
        )
    observed = float(value)
    if not math.isfinite(observed) or observed < 0.0:
        raise GlobalOrientationDevelopmentDecisionError(
            f"{name} must be a finite non-negative number"
        )
    return observed


def _require_ordered_subset(
    value: object,
    allowed: tuple[str, ...],
    *,
    name: str,
) -> tuple[str, ...]:
    if type(value) is not tuple or any(type(item) is not str for item in value):
        raise GlobalOrientationDevelopmentDecisionError(
            f"{name} must be a tuple of strings"
        )
    if value != tuple(item for item in allowed if item in value):
        raise GlobalOrientationDevelopmentDecisionError(
            f"{name} must be a unique protocol-ordered subset"
        )
    return value


@dataclass(frozen=True, slots=True)
class CaseComparisonObservation:
    case_id: str
    baseline_preparation_succeeded: bool
    experimental_preparation_succeeded: bool
    baseline_candidate_count: int
    experimental_candidate_count: int
    baseline_valid_proposal_oracle_rmsd: float | None
    experimental_valid_proposal_oracle_rmsd: float | None
    baseline_selected_top1_rmsd: float | None
    experimental_selected_top1_rmsd: float | None
    baseline_selected_top1_valid: bool | None
    experimental_selected_top1_valid: bool | None
    source_geometry_evidence_complete: bool
    observation_evidence_complete: bool

    def __post_init__(self) -> None:
        if self.case_id not in CASE_IDS:
            raise GlobalOrientationDevelopmentDecisionError(
                "case_id is outside the fixed cohort"
            )
        for name in (
            "baseline_preparation_succeeded",
            "experimental_preparation_succeeded",
            "source_geometry_evidence_complete",
            "observation_evidence_complete",
        ):
            if type(getattr(self, name)) is not bool:
                raise GlobalOrientationDevelopmentDecisionError(
                    f"{name} must be boolean"
                )
        for name in ("baseline_candidate_count", "experimental_candidate_count"):
            value = getattr(self, name)
            if type(value) is not int or value < 0:
                raise GlobalOrientationDevelopmentDecisionError(
                    f"{name} must be a non-negative integer"
                )

        preparation_failure = self.case_id == "6M73_FNR"
        if preparation_failure:
            if (
                self.baseline_preparation_succeeded
                or self.experimental_preparation_succeeded
                or self.baseline_candidate_count != 0
                or self.experimental_candidate_count != 0
            ):
                raise GlobalOrientationDevelopmentDecisionError(
                    "the fixed preparation-failure row must remain failure complete"
                )
            metric_required = False
            if (
                self.baseline_selected_top1_valid is not None
                or self.experimental_selected_top1_valid is not None
            ):
                raise GlobalOrientationDevelopmentDecisionError(
                    "preparation-failure validity must remain unavailable"
                )
        else:
            if (
                not self.baseline_preparation_succeeded
                or not self.experimental_preparation_succeeded
            ):
                raise GlobalOrientationDevelopmentDecisionError(
                    "scored cases require successful preparation in both arms"
                )
            if (
                self.baseline_candidate_count != CANDIDATE_DENOMINATOR_PER_ARM
                or self.experimental_candidate_count != CANDIDATE_DENOMINATOR_PER_ARM
            ):
                raise GlobalOrientationDevelopmentDecisionError(
                    "scored cases require identical 64-slot denominators"
                )
            metric_required = True
            if (
                type(self.baseline_selected_top1_valid) is not bool
                or type(self.experimental_selected_top1_valid) is not bool
            ):
                raise GlobalOrientationDevelopmentDecisionError(
                    "scored selected-Top-1 validity must be boolean"
                )

        for name in (
            "baseline_valid_proposal_oracle_rmsd",
            "experimental_valid_proposal_oracle_rmsd",
            "baseline_selected_top1_rmsd",
            "experimental_selected_top1_rmsd",
        ):
            object.__setattr__(
                self,
                name,
                _metric(getattr(self, name), name=name, required=metric_required),
            )

    @property
    def evidence_complete(self) -> bool:
        return (
            self.source_geometry_evidence_complete
            and self.observation_evidence_complete
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "case_id": self.case_id,
            "baseline_preparation_succeeded": self.baseline_preparation_succeeded,
            "experimental_preparation_succeeded": self.experimental_preparation_succeeded,
            "baseline_candidate_count": self.baseline_candidate_count,
            "experimental_candidate_count": self.experimental_candidate_count,
            "baseline_valid_proposal_oracle_rmsd": self.baseline_valid_proposal_oracle_rmsd,
            "experimental_valid_proposal_oracle_rmsd": self.experimental_valid_proposal_oracle_rmsd,
            "baseline_selected_top1_rmsd": self.baseline_selected_top1_rmsd,
            "experimental_selected_top1_rmsd": self.experimental_selected_top1_rmsd,
            "baseline_selected_top1_valid": self.baseline_selected_top1_valid,
            "experimental_selected_top1_valid": self.experimental_selected_top1_valid,
            "source_geometry_evidence_complete": self.source_geometry_evidence_complete,
            "observation_evidence_complete": self.observation_evidence_complete,
        }


@dataclass(frozen=True, slots=True)
class GlobalOrientationDevelopmentDecision:
    verdict: str
    invariant_failures: tuple[str, ...]
    hard_no_go_triggers: tuple[str, ...]
    go_criteria: tuple[str, ...]
    new_valid_proposal_recovery_case_ids: tuple[str, ...]
    baseline_invalid_selected_top1_count: int
    experimental_invalid_selected_top1_count: int
    baseline_recovered_regression_case_ids: tuple[str, ...]
    observation_receipt_sha256s: tuple[str, ...]
    schema_id: str = DECISION_SCHEMA_ID
    _receipt_sha256: str = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if self.schema_id != DECISION_SCHEMA_ID:
            raise GlobalOrientationDevelopmentDecisionError(
                "decision schema is invalid"
            )
        if self.verdict not in {"go", "no_go"}:
            raise GlobalOrientationDevelopmentDecisionError(
                "decision verdict is invalid"
            )
        invariant_failures = _require_ordered_subset(
            self.invariant_failures,
            _INVARIANT_FAILURE_ORDER,
            name="invariant_failures",
        )
        hard_no_go = _require_ordered_subset(
            self.hard_no_go_triggers,
            _HARD_NO_GO_ORDER,
            name="hard_no_go_triggers",
        )
        recoveries = _require_ordered_subset(
            self.new_valid_proposal_recovery_case_ids,
            UNCOVERED_CASE_IDS,
            name="new_valid_proposal_recovery_case_ids",
        )
        regressions = _require_ordered_subset(
            self.baseline_recovered_regression_case_ids,
            BASELINE_RECOVERED_CASE_IDS,
            name="baseline_recovered_regression_case_ids",
        )
        for name in (
            "baseline_invalid_selected_top1_count",
            "experimental_invalid_selected_top1_count",
        ):
            value = getattr(self, name)
            if type(value) is not int or not 0 <= value <= len(SCORED_CASE_IDS):
                raise GlobalOrientationDevelopmentDecisionError(
                    f"{name} must be an integer within the scored cohort"
                )
        expected_go_criteria = tuple(
            criterion
            for criterion, achieved in (
                (_RECOVERY_GO_CRITERION, len(recoveries) >= 2),
                (
                    _INVALID_TOP1_GO_CRITERION,
                    self.experimental_invalid_selected_top1_count
                    <= self.baseline_invalid_selected_top1_count,
                ),
            )
            if achieved
        )
        if self.go_criteria != expected_go_criteria:
            raise GlobalOrientationDevelopmentDecisionError(
                "go_criteria are inconsistent with decision observations"
            )
        required_trigger_relationships = (
            ("required_invariant_failed", bool(invariant_failures)),
            (
                "zero_new_previously_uncovered_valid_proposal_recoveries",
                not recoveries,
            ),
            ("baseline_recovered_case_regression", bool(regressions)),
        )
        if any(
            (trigger in hard_no_go) is not required
            for trigger, required in required_trigger_relationships
        ):
            raise GlobalOrientationDevelopmentDecisionError(
                "hard_no_go_triggers are inconsistent with decision observations"
            )
        expected_verdict = (
            "go" if not hard_no_go and len(expected_go_criteria) == 2 else "no_go"
        )
        if self.verdict != expected_verdict:
            raise GlobalOrientationDevelopmentDecisionError(
                "decision verdict is inconsistent with protocol criteria"
            )
        if (
            type(self.observation_receipt_sha256s) is not tuple
            or len(self.observation_receipt_sha256s) != len(CASE_IDS)
            or any(
                type(digest) is not str
                or len(digest) != 64
                or any(character not in "0123456789abcdef" for character in digest)
                for digest in self.observation_receipt_sha256s
            )
        ):
            raise GlobalOrientationDevelopmentDecisionError(
                "observation receipts must contain nine lowercase SHA-256 digests"
            )
        object.__setattr__(self, "_receipt_sha256", _sha256(self._projection()))

    def _projection(self) -> dict[str, object]:
        return {
            "schema_id": self.schema_id,
            "verdict": self.verdict,
            "invariant_failures": list(self.invariant_failures),
            "hard_no_go_triggers": list(self.hard_no_go_triggers),
            "go_criteria": list(self.go_criteria),
            "new_valid_proposal_recovery_case_ids": list(
                self.new_valid_proposal_recovery_case_ids
            ),
            "baseline_invalid_selected_top1_count": self.baseline_invalid_selected_top1_count,
            "experimental_invalid_selected_top1_count": self.experimental_invalid_selected_top1_count,
            "baseline_recovered_regression_case_ids": list(
                self.baseline_recovered_regression_case_ids
            ),
            "observation_receipt_sha256s": list(self.observation_receipt_sha256s),
            "fresh_holdout_execution_authorized": False,
            "stage0_admission_authority": False,
            "profile_promotion_authority": False,
            "product_execution_authorized": False,
            "customer_pose_emission_authorized": False,
            "public_or_scientific_claim_authorized": False,
        }

    @property
    def receipt_sha256(self) -> str:
        observed = _sha256(self._projection())
        if observed != self._receipt_sha256:
            raise GlobalOrientationDevelopmentDecisionError(
                "decision changed after construction"
            )
        return observed

    def to_dict(self) -> dict[str, object]:
        return {**self._projection(), "receipt_sha256": self.receipt_sha256}


def evaluate_global_orientation_development(
    observations: Sequence[CaseComparisonObservation],
) -> GlobalOrientationDevelopmentDecision:
    """Evaluate the exact fixed protocol without granting execution authority."""

    rows = tuple(observations)
    if any(type(row) is not CaseComparisonObservation for row in rows):
        raise GlobalOrientationDevelopmentDecisionError(
            "observations must use the exact comparison type"
        )
    if len(rows) != len(CASE_IDS) or tuple(row.case_id for row in rows) != CASE_IDS:
        raise GlobalOrientationDevelopmentDecisionError(
            "observations must retain the exact ordered nine-case cohort"
        )

    invariant_failures: list[str] = []
    if any(not row.evidence_complete for row in rows):
        invariant_failures.append("complete_source_and_observation_rederivation")
    preparation_row = rows[CASE_IDS.index("6M73_FNR")]
    if (
        preparation_row.baseline_preparation_succeeded
        != preparation_row.experimental_preparation_succeeded
    ):
        invariant_failures.append("no_preparation_failure_regression")
    if any(
        row.baseline_candidate_count != row.experimental_candidate_count
        or (
            row.case_id in SCORED_CASE_IDS
            and row.baseline_candidate_count != CANDIDATE_DENOMINATOR_PER_ARM
        )
        for row in rows
    ):
        invariant_failures.append("identical_failure_complete_64_slot_denominators")

    new_recoveries = tuple(
        row.case_id
        for row in rows
        if row.case_id in UNCOVERED_CASE_IDS
        and row.baseline_valid_proposal_oracle_rmsd > RMSD_THRESHOLD_ANGSTROM
        and row.experimental_valid_proposal_oracle_rmsd <= RMSD_THRESHOLD_ANGSTROM
    )
    baseline_regressions = tuple(
        row.case_id
        for row in rows
        if row.case_id in BASELINE_RECOVERED_CASE_IDS
        and (
            not row.experimental_selected_top1_valid
            or row.experimental_selected_top1_rmsd > RMSD_THRESHOLD_ANGSTROM
        )
    )
    baseline_invalid = sum(
        not row.baseline_selected_top1_valid
        for row in rows
        if row.case_id in SCORED_CASE_IDS
    )
    experimental_invalid = sum(
        not row.experimental_selected_top1_valid
        for row in rows
        if row.case_id in SCORED_CASE_IDS
    )

    hard_no_go: list[str] = []
    if invariant_failures:
        hard_no_go.append("required_invariant_failed")
    if not new_recoveries:
        hard_no_go.append("zero_new_previously_uncovered_valid_proposal_recoveries")
    if baseline_regressions:
        hard_no_go.append("baseline_recovered_case_regression")

    go_criteria: list[str] = []
    if len(new_recoveries) >= 2:
        go_criteria.append(_RECOVERY_GO_CRITERION)
    if experimental_invalid <= baseline_invalid:
        go_criteria.append(_INVALID_TOP1_GO_CRITERION)

    verdict = "go" if not hard_no_go and len(go_criteria) == 2 else "no_go"
    observation_hashes = tuple(_sha256(row.to_dict()) for row in rows)
    return GlobalOrientationDevelopmentDecision(
        verdict=verdict,
        invariant_failures=tuple(invariant_failures),
        hard_no_go_triggers=tuple(hard_no_go),
        go_criteria=tuple(go_criteria),
        new_valid_proposal_recovery_case_ids=new_recoveries,
        baseline_invalid_selected_top1_count=baseline_invalid,
        experimental_invalid_selected_top1_count=experimental_invalid,
        baseline_recovered_regression_case_ids=baseline_regressions,
        observation_receipt_sha256s=observation_hashes,
    )


__all__ = [
    "BASELINE_RECOVERED_CASE_IDS",
    "CANDIDATE_DENOMINATOR_PER_ARM",
    "CASE_IDS",
    "CaseComparisonObservation",
    "DECISION_SCHEMA_ID",
    "GlobalOrientationDevelopmentDecision",
    "GlobalOrientationDevelopmentDecisionError",
    "RMSD_THRESHOLD_ANGSTROM",
    "SCORED_CASE_IDS",
    "UNCOVERED_CASE_IDS",
    "evaluate_global_orientation_development",
]

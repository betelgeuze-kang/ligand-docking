"""Deterministic decision evaluator for the fixed global-orientation protocol.

This module consumes only post-generation development observations. It cannot
run docking, open fresh data, promote a profile, enable a product path, or
authorize a scientific claim.
"""

from __future__ import annotations

from dataclasses import InitVar, dataclass, field
import hashlib
import json
from typing import Sequence

from .oracle_selection_evidence import OracleSelectionEvidence
from .source_paired_clearance_activation import (
    SourcePairedClearanceCaseSourceReceiptV1,
)
from ..docking.global_orientation import GLOBAL_ORIENTATION_GENERATOR_ID

DECISION_SCHEMA_ID = (
    "betelgeuze.engine_v2_global_orientation_development_decision/1.1.0"
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
CASE_ARM_EVIDENCE_SCHEMA_ID = (
    "betelgeuze.engine_v2_global_orientation_case_arm_evidence/1.0.0"
)
_DECISION_CONSTRUCTION_TOKEN = object()
_RECOVERY_GO_CRITERION = (
    "valid_proposal_oracle_recovery_in_at_least_2_of_7_previously_uncovered_cases"
)
_INVALID_TOP1_GO_CRITERION = "no_increase_in_invalid_selected_top1_count"
_INVARIANT_FAILURE_ORDER = ("baseline_recovered_case_not_reproduced",)
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


def _is_sha256(value: object) -> bool:
    return (
        type(value) is str
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


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
class CaseArmOracleEvidence:
    case_id: str
    arm_id: str
    proposal_authority: str
    case_source_receipt_sha256: str
    candidate_lineage_receipt_sha256: str
    oracle_evidence: OracleSelectionEvidence
    schema_id: str = CASE_ARM_EVIDENCE_SCHEMA_ID
    _receipt_sha256: str = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if self.schema_id != CASE_ARM_EVIDENCE_SCHEMA_ID:
            raise GlobalOrientationDevelopmentDecisionError(
                "case-arm evidence schema is invalid"
            )
        if self.case_id not in SCORED_CASE_IDS:
            raise GlobalOrientationDevelopmentDecisionError(
                "case-arm evidence is outside the scored cohort"
            )
        expected_authority = {
            "baseline_current_v7": "current_v7",
            "experimental_global_orientation_v1": GLOBAL_ORIENTATION_GENERATOR_ID,
        }.get(self.arm_id)
        if expected_authority is None or self.proposal_authority != expected_authority:
            raise GlobalOrientationDevelopmentDecisionError(
                "case-arm proposal authority is invalid"
            )
        if not _is_sha256(self.case_source_receipt_sha256) or not _is_sha256(
            self.candidate_lineage_receipt_sha256
        ):
            raise GlobalOrientationDevelopmentDecisionError(
                "case-arm source and lineage receipts must be SHA-256 identities"
            )
        if type(self.oracle_evidence) is not OracleSelectionEvidence:
            raise GlobalOrientationDevelopmentDecisionError(
                "case-arm evidence requires exact oracle-selection evidence"
            )
        object.__setattr__(self, "_receipt_sha256", _sha256(self._projection()))

    def _projection(self) -> dict[str, object]:
        return {
            "schema_id": self.schema_id,
            "case_id": self.case_id,
            "arm_id": self.arm_id,
            "proposal_authority": self.proposal_authority,
            "case_source_receipt_sha256": self.case_source_receipt_sha256,
            "candidate_lineage_receipt_sha256": (self.candidate_lineage_receipt_sha256),
            "oracle_selection_evidence_sha256": self.oracle_evidence.receipt_sha256,
            "candidate_observation_receipt_sha256s": list(
                self.oracle_evidence.report.observation_receipt_sha256s
            ),
            "development_only": True,
            "execution_authorized": False,
            "public_or_scientific_claim_authorized": False,
        }

    @property
    def receipt_sha256(self) -> str:
        observed = _sha256(self._projection())
        if observed != self._receipt_sha256:
            raise GlobalOrientationDevelopmentDecisionError(
                "case-arm evidence changed after construction"
            )
        return observed


@dataclass(frozen=True, slots=True)
class CaseComparisonObservation:
    case_id: str
    case_source_receipt: SourcePairedClearanceCaseSourceReceiptV1 | None
    preparation_failure_receipt_sha256: str | None
    baseline_evidence: CaseArmOracleEvidence | None
    experimental_evidence: CaseArmOracleEvidence | None

    def __post_init__(self) -> None:
        if self.case_id not in CASE_IDS:
            raise GlobalOrientationDevelopmentDecisionError(
                "case_id is outside the fixed cohort"
            )
        preparation_failure = self.case_id == "6M73_FNR"
        if preparation_failure:
            if (
                self.case_source_receipt is not None
                or self.baseline_evidence is not None
                or self.experimental_evidence is not None
            ):
                raise GlobalOrientationDevelopmentDecisionError(
                    "the fixed preparation-failure row must remain failure complete"
                )
            if not _is_sha256(self.preparation_failure_receipt_sha256):
                raise GlobalOrientationDevelopmentDecisionError(
                    "preparation failure requires an exact receipt identity"
                )
        else:
            if (
                type(self.case_source_receipt)
                is not SourcePairedClearanceCaseSourceReceiptV1
                or self.case_source_receipt.case_id != self.case_id
            ):
                raise GlobalOrientationDevelopmentDecisionError(
                    "scored cases require their exact frozen source receipt"
                )
            if self.preparation_failure_receipt_sha256 is not None:
                raise GlobalOrientationDevelopmentDecisionError(
                    "scored cases cannot carry a preparation-failure receipt"
                )
            if (
                type(self.baseline_evidence) is not CaseArmOracleEvidence
                or type(self.experimental_evidence) is not CaseArmOracleEvidence
            ):
                raise GlobalOrientationDevelopmentDecisionError(
                    "scored cases require complete oracle-selection evidence"
                )
            expected_bindings = (
                (
                    self.baseline_evidence,
                    "baseline_current_v7",
                    self.case_source_receipt.current_v7_candidate_lineage_sha256,
                ),
                (
                    self.experimental_evidence,
                    "experimental_global_orientation_v1",
                    None,
                ),
            )
            for evidence, arm_id, baseline_lineage in expected_bindings:
                if (
                    evidence.case_id != self.case_id
                    or evidence.arm_id != arm_id
                    or evidence.case_source_receipt_sha256
                    != self.case_source_receipt.receipt_sha256
                    or (
                        baseline_lineage is not None
                        and evidence.candidate_lineage_receipt_sha256
                        != baseline_lineage
                    )
                    or evidence.oracle_evidence.report.candidate_count
                    != CANDIDATE_DENOMINATOR_PER_ARM
                    or evidence.oracle_evidence.top_ks != (1, 5)
                    or evidence.oracle_evidence.report.rmsd_threshold_angstrom
                    != RMSD_THRESHOLD_ANGSTROM
                ):
                    raise GlobalOrientationDevelopmentDecisionError(
                        "scored evidence drifted from the fixed 64-slot protocol"
                    )

    @property
    def baseline_report(self):
        return (
            None
            if self.baseline_evidence is None
            else self.baseline_evidence.oracle_evidence.report
        )

    @property
    def experimental_report(self):
        return (
            None
            if self.experimental_evidence is None
            else self.experimental_evidence.oracle_evidence.report
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "case_id": self.case_id,
            "case_source_receipt_sha256": (
                None
                if self.case_source_receipt is None
                else self.case_source_receipt.receipt_sha256
            ),
            "preparation_failure_receipt_sha256": (
                self.preparation_failure_receipt_sha256
            ),
            "baseline_oracle_selection_evidence_sha256": (
                None
                if self.baseline_evidence is None
                else self.baseline_evidence.receipt_sha256
            ),
            "experimental_oracle_selection_evidence_sha256": (
                None
                if self.experimental_evidence is None
                else self.experimental_evidence.receipt_sha256
            ),
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
    _construction_token: InitVar[object] = None

    def __post_init__(self, _construction_token: object) -> None:
        if _construction_token is not _DECISION_CONSTRUCTION_TOKEN:
            raise GlobalOrientationDevelopmentDecisionError(
                "decisions must be constructed by the protocol evaluator"
            )
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
    baseline_recovered_row = rows[CASE_IDS.index("6T88_MWQ")]
    baseline_recovered_report = baseline_recovered_row.baseline_report
    if (
        not baseline_recovered_report.selected_top1_valid
        or baseline_recovered_report.selected_top1_rmsd_angstrom is None
        or baseline_recovered_report.selected_top1_rmsd_angstrom
        > RMSD_THRESHOLD_ANGSTROM
    ):
        invariant_failures.append("baseline_recovered_case_not_reproduced")

    new_recoveries = tuple(
        row.case_id
        for row in rows
        if row.case_id in UNCOVERED_CASE_IDS
        and (
            row.baseline_report.valid_proposal_oracle_rmsd_angstrom is None
            or row.baseline_report.valid_proposal_oracle_rmsd_angstrom
            > RMSD_THRESHOLD_ANGSTROM
        )
        and row.experimental_report.valid_proposal_oracle_rmsd_angstrom is not None
        and row.experimental_report.valid_proposal_oracle_rmsd_angstrom
        <= RMSD_THRESHOLD_ANGSTROM
    )
    baseline_regressions = tuple(
        row.case_id
        for row in rows
        if row.case_id in BASELINE_RECOVERED_CASE_IDS
        and (
            not row.experimental_report.selected_top1_valid
            or row.experimental_report.selected_top1_rmsd_angstrom is None
            or row.experimental_report.selected_top1_rmsd_angstrom
            > RMSD_THRESHOLD_ANGSTROM
        )
    )
    baseline_invalid = sum(
        not row.baseline_report.selected_top1_valid
        for row in rows
        if row.case_id in SCORED_CASE_IDS
    )
    experimental_invalid = sum(
        not row.experimental_report.selected_top1_valid
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
        _construction_token=_DECISION_CONSTRUCTION_TOKEN,
    )


__all__ = [
    "BASELINE_RECOVERED_CASE_IDS",
    "CANDIDATE_DENOMINATOR_PER_ARM",
    "CASE_ARM_EVIDENCE_SCHEMA_ID",
    "CASE_IDS",
    "CaseArmOracleEvidence",
    "CaseComparisonObservation",
    "DECISION_SCHEMA_ID",
    "GlobalOrientationDevelopmentDecision",
    "GlobalOrientationDevelopmentDecisionError",
    "RMSD_THRESHOLD_ANGSTROM",
    "SCORED_CASE_IDS",
    "UNCOVERED_CASE_IDS",
    "evaluate_global_orientation_development",
]

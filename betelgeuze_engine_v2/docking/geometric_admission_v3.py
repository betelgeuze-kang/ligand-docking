"""Failure-aware pre-refinement geometric admission for producer v3.

Admission consumes one sealed fixed64 producer batch, not caller coordinates.
It evaluates every generated candidate with the existing full-Cartesian Python
reference kernel while carrying allocation and runtime proposal failures through
their original slots.  No slot is removed or reallocated.

This component is synthetic and pre-activation. It does not refine, score,
rank, evaluate final pose validity, or authorize molecular/product execution.
"""

from __future__ import annotations

from dataclasses import InitVar, dataclass, field
import hashlib
import json
import re
from typing import Final

from .geometric_admission_v2 import (
    HARD_REJECTION_MINIMUM_VDW_RATIO,
    MAX_BATCH_EXACT_PAIR_EVALUATIONS,
    SEVERE_PENETRATION_REJECTION_CODE,
    GeometricAdmissionMetricsV2,
    GeometricAdmissionV2Error,
    evaluate_geometric_admission_metrics_one_python,
)
from .mixed64_allocation import FIXED_MIXED64_CANDIDATE_COUNT
from .mixed64_proposal_producer_v3 import (
    GENERATION_STATUS_FAILURE,
    GENERATION_STATUS_SUCCESS,
    MIXED64_PRODUCER_POLICY_SHA256,
    Mixed64ProposalGenerationRecordV1,
    Mixed64ProposalProducerBatchV1,
)
from .mixed64_proposal_geometry_v3 import SingleAnchorPlacementReceiptV1


GEOMETRIC_ADMISSION_V3_COMPONENT_ID: Final = (
    "betelgeuze.engine_v2_geometric_admission_v3/1.0.0"
)
GEOMETRIC_ADMISSION_V3_POLICY_SCHEMA_ID: Final = (
    "betelgeuze.engine_v2_geometric_admission_v3_policy/1.0.0"
)
GEOMETRIC_ADMISSION_V3_DECISION_SCHEMA_ID: Final = (
    "betelgeuze.engine_v2_geometric_admission_v3_decision/1.0.0"
)
GEOMETRIC_ADMISSION_V3_BATCH_SCHEMA_ID: Final = (
    "betelgeuze.engine_v2_geometric_admission_v3_batch/1.0.0"
)
GEOMETRIC_ADMISSION_V3_PROFILE_ID: Final = (
    "betelgeuze.engine_v2_failure_aware_pre_refinement_geometric_admission/1.0.0"
)

ACCEPTED_STATUS: Final = "accepted"
REJECTED_STATUS: Final = "rejected"
TYPED_ALLOCATION_FAILURE_STATUS: Final = "typed_allocation_failure"
TYPED_PROPOSAL_GENERATION_FAILURE_STATUS: Final = (
    "typed_proposal_generation_failure"
)
_DECISION_STATUSES: Final = {
    ACCEPTED_STATUS,
    REJECTED_STATUS,
    TYPED_ALLOCATION_FAILURE_STATUS,
    TYPED_PROPOSAL_GENERATION_FAILURE_STATUS,
}
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_DECISION_FACTORY_SEAL = object()
_BATCH_FACTORY_SEAL = object()


class GeometricAdmissionV3Error(ValueError):
    """Raised when producer-bound geometric admission fails closed."""


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


def _seal_projection(value: object) -> tuple[bytes, str]:
    payload = _canonical_bytes(value)
    return payload, hashlib.sha256(payload).hexdigest()


def _unseal_projection(payload: bytes) -> dict[str, object]:
    document = json.loads(payload)
    if type(document) is not dict:
        raise GeometricAdmissionV3Error("sealed projection is not an object")
    return document


def _verify_sealed_receipt(payload: bytes, expected: str, *, name: str) -> str:
    observed = hashlib.sha256(payload).hexdigest()
    if observed != expected:
        raise GeometricAdmissionV3Error(f"{name} sealed projection changed")
    return observed


def _digest(value: object, *, name: str) -> str:
    if type(value) is not str or _SHA256_RE.fullmatch(value) is None:
        raise GeometricAdmissionV3Error(f"{name} must be a lowercase SHA-256")
    return value


def frozen_geometric_admission_v3_policy() -> dict[str, object]:
    return {
        "schema_id": GEOMETRIC_ADMISSION_V3_POLICY_SCHEMA_ID,
        "component_id": GEOMETRIC_ADMISSION_V3_COMPONENT_ID,
        "profile_id": GEOMETRIC_ADMISSION_V3_PROFILE_ID,
        "producer_policy_sha256": MIXED64_PRODUCER_POLICY_SHA256,
        "candidate_denominator": FIXED_MIXED64_CANDIDATE_COUNT,
        "hard_rejection": {
            "metric": "minimum_vdw_ratio",
            "operator": "strictly_less_than",
            "threshold_binary64_hex": HARD_REJECTION_MINIMUM_VDW_RATIO.hex(),
            "rejection_code": SEVERE_PENETRATION_REJECTION_CODE,
        },
        "failure_semantics": {
            "allocation_failure_status": TYPED_ALLOCATION_FAILURE_STATUS,
            "proposal_generation_failure_status": (
                TYPED_PROPOSAL_GENERATION_FAILURE_STATUS
            ),
            "failure_coordinate_allowed": False,
            "failure_metrics_allowed": False,
            "failure_rank_eligible": False,
            "slot_reallocation_allowed": False,
        },
        "pair_work": {
            "traversal": "full_cartesian_ligand_index_major_receptor_index_minor",
            "maximum_batch_exact_pair_evaluations": (
                MAX_BATCH_EXACT_PAIR_EVALUATIONS
            ),
            "generated_candidates_only": True,
        },
        "authority": {
            "reservation_allowed": False,
            "molecular_execution_authorized": False,
            "historical_ab_authorized": False,
            "fresh_holdout_authorized": False,
            "product_mutation_authorized": False,
            "stage0_admission_authorized": False,
            "public_benchmark_authorized": False,
            "scientific_claim_authorized": False,
            "github_actions_production_authority_allowed": False,
            "test_double_production_authority_allowed": False,
        },
        "status": "synthetic_pre_refinement_admission_only",
    }


GEOMETRIC_ADMISSION_V3_POLICY_SHA256: Final = _sha256(
    frozen_geometric_admission_v3_policy()
)


@dataclass(frozen=True, slots=True)
class GeometricAdmissionDecisionV3:
    producer_record: Mixed64ProposalGenerationRecordV1 = field(repr=False)
    metrics: GeometricAdmissionMetricsV2 | None
    status: str
    rejection_code: str | None
    rank_eligible: bool
    _factory_seal: InitVar[object | None] = None
    schema_id: str = GEOMETRIC_ADMISSION_V3_DECISION_SCHEMA_ID
    _receipt_sha256: str = field(init=False, repr=False)
    _canonical_projection_bytes: bytes = field(init=False, repr=False)

    def __post_init__(self, _factory_seal: object | None) -> None:
        if _factory_seal is not _DECISION_FACTORY_SEAL:
            raise GeometricAdmissionV3Error(
                "geometric admission decision requires the bounded factory"
            )
        if self.schema_id != GEOMETRIC_ADMISSION_V3_DECISION_SCHEMA_ID:
            raise GeometricAdmissionV3Error("geometric admission v3 schema changed")
        if type(self.producer_record) is not Mixed64ProposalGenerationRecordV1:
            raise TypeError("producer_record must be exact")
        if self.status not in _DECISION_STATUSES:
            raise GeometricAdmissionV3Error("geometric admission status is invalid")
        if type(self.rank_eligible) is not bool:
            raise GeometricAdmissionV3Error("rank eligibility must be boolean")
        slot = self.producer_record.allocation.slots[self.slot_index]
        if self.producer_record.status == GENERATION_STATUS_SUCCESS:
            if type(self.metrics) is not GeometricAdmissionMetricsV2:
                raise TypeError("generated candidate requires exact metrics")
            accepted = (
                self.metrics.minimum_vdw_ratio
                >= HARD_REJECTION_MINIMUM_VDW_RATIO
            )
            expected_status = ACCEPTED_STATUS if accepted else REJECTED_STATUS
            expected_code = None if accepted else SEVERE_PENETRATION_REJECTION_CODE
            if (
                self.status != expected_status
                or self.rejection_code != expected_code
                or self.rank_eligible is not accepted
            ):
                raise GeometricAdmissionV3Error(
                    "generated decision changed the sole hard rejection rule"
                )
            if self.producer_record.source_coordinate_sha256 is None:
                raise GeometricAdmissionV3Error("generated coordinate identity is absent")
        else:
            failure = self.producer_record.failure_receipt
            if failure is None or self.metrics is not None or self.rank_eligible:
                raise GeometricAdmissionV3Error(
                    "typed generation failure fabricated metrics or eligibility"
                )
            expected_status = (
                TYPED_ALLOCATION_FAILURE_STATUS
                if not slot.generation_eligible
                else TYPED_PROPOSAL_GENERATION_FAILURE_STATUS
            )
            if (
                self.status != expected_status
                or self.rejection_code != failure.failure_code
            ):
                raise GeometricAdmissionV3Error(
                    "typed generation failure was relabeled"
                )
        sealed, receipt_sha256 = _seal_projection(self._projection())
        object.__setattr__(self, "_canonical_projection_bytes", sealed)
        object.__setattr__(self, "_receipt_sha256", receipt_sha256)

    @property
    def slot_index(self) -> int:
        return self.producer_record.slot_index

    @property
    def candidate_coordinate_sha256(self) -> str | None:
        return self.producer_record.source_coordinate_sha256

    @property
    def accepted(self) -> bool:
        return self.status == ACCEPTED_STATUS

    def _projection(self) -> dict[str, object]:
        slot = self.producer_record.allocation.slots[self.slot_index]
        return {
            "schema_id": self.schema_id,
            "component_id": GEOMETRIC_ADMISSION_V3_COMPONENT_ID,
            "policy_sha256": GEOMETRIC_ADMISSION_V3_POLICY_SHA256,
            "producer_generation_record_receipt_sha256": (
                self.producer_record.receipt_sha256
            ),
            "allocation_slot_receipt_sha256": slot.receipt_sha256,
            "slot_index": self.slot_index,
            "lane": slot.lane,
            "allocation_generation_eligible": slot.generation_eligible,
            "producer_generation_status": self.producer_record.status,
            "candidate_coordinate_sha256": self.candidate_coordinate_sha256,
            "metrics": None if self.metrics is None else self.metrics.to_dict(),
            "status": self.status,
            "rejection_code": self.rejection_code,
            "rank_eligible": self.rank_eligible,
            "hard_rejection_metric": (
                "minimum_vdw_ratio" if self.metrics is not None else None
            ),
            "hard_rejection_operator": (
                "strictly_less_than" if self.metrics is not None else None
            ),
            "hard_rejection_threshold_binary64_hex": (
                HARD_REJECTION_MINIMUM_VDW_RATIO.hex()
                if self.metrics is not None
                else None
            ),
            "slot_preserved_in_denominator": True,
        }

    @property
    def receipt_sha256(self) -> str:
        return _verify_sealed_receipt(
            self._canonical_projection_bytes,
            self._receipt_sha256,
            name="geometric admission decision",
        )

    def to_dict(self) -> dict[str, object]:
        return {
            **_unseal_projection(self._canonical_projection_bytes),
            "receipt_sha256": self.receipt_sha256,
        }


@dataclass(frozen=True, slots=True)
class GeometricAdmissionBatchV3:
    producer_batch: Mixed64ProposalProducerBatchV1 = field(repr=False)
    decisions: tuple[GeometricAdmissionDecisionV3, ...]
    _factory_seal: InitVar[object | None] = None
    profile_id: str = GEOMETRIC_ADMISSION_V3_PROFILE_ID
    schema_id: str = GEOMETRIC_ADMISSION_V3_BATCH_SCHEMA_ID
    _receipt_sha256: str = field(init=False, repr=False)
    _canonical_projection_bytes: bytes = field(init=False, repr=False)

    def __post_init__(self, _factory_seal: object | None) -> None:
        if _factory_seal is not _BATCH_FACTORY_SEAL:
            raise GeometricAdmissionV3Error(
                "geometric admission batch requires the bounded factory"
            )
        if (
            self.schema_id != GEOMETRIC_ADMISSION_V3_BATCH_SCHEMA_ID
            or self.profile_id != GEOMETRIC_ADMISSION_V3_PROFILE_ID
        ):
            raise GeometricAdmissionV3Error("geometric admission batch identity changed")
        if type(self.producer_batch) is not Mixed64ProposalProducerBatchV1:
            raise TypeError("producer_batch must be exact")
        if type(self.decisions) is not tuple or len(self.decisions) != 64:
            raise GeometricAdmissionV3Error("geometric admission denominator is not 64")
        if any(type(value) is not GeometricAdmissionDecisionV3 for value in self.decisions):
            raise TypeError("decisions must be exact")
        if tuple(value.slot_index for value in self.decisions) != tuple(range(64)):
            raise GeometricAdmissionV3Error("geometric admission slot order changed")
        for record, decision in zip(
            self.producer_batch.records,
            self.decisions,
            strict=True,
        ):
            if decision.producer_record.receipt_sha256 != record.receipt_sha256:
                raise GeometricAdmissionV3Error("producer decision binding changed")
        sealed, receipt_sha256 = _seal_projection(self._projection())
        object.__setattr__(self, "_canonical_projection_bytes", sealed)
        object.__setattr__(self, "_receipt_sha256", receipt_sha256)

    @property
    def accepted_count(self) -> int:
        return sum(value.status == ACCEPTED_STATUS for value in self.decisions)

    @property
    def geometric_rejected_count(self) -> int:
        return sum(value.status == REJECTED_STATUS for value in self.decisions)

    @property
    def typed_allocation_failure_count(self) -> int:
        return sum(
            value.status == TYPED_ALLOCATION_FAILURE_STATUS
            for value in self.decisions
        )

    @property
    def typed_proposal_generation_failure_count(self) -> int:
        return sum(
            value.status == TYPED_PROPOSAL_GENERATION_FAILURE_STATUS
            for value in self.decisions
        )

    @property
    def nonaccepted_count(self) -> int:
        return len(self.decisions) - self.accepted_count

    @property
    def exact_pair_evaluation_count(self) -> int:
        return sum(
            0 if decision.metrics is None else decision.metrics.exact_pair_count
            for decision in self.decisions
        )

    def _projection(self) -> dict[str, object]:
        return {
            "schema_id": self.schema_id,
            "component_id": GEOMETRIC_ADMISSION_V3_COMPONENT_ID,
            "profile_id": self.profile_id,
            "policy": frozen_geometric_admission_v3_policy(),
            "policy_sha256": GEOMETRIC_ADMISSION_V3_POLICY_SHA256,
            "producer_batch": self.producer_batch.to_dict(),
            "producer_batch_receipt_sha256": self.producer_batch.receipt_sha256,
            "candidate_denominator": len(self.decisions),
            "accepted_count": self.accepted_count,
            "geometric_rejected_count": self.geometric_rejected_count,
            "typed_allocation_failure_count": self.typed_allocation_failure_count,
            "typed_proposal_generation_failure_count": (
                self.typed_proposal_generation_failure_count
            ),
            "nonaccepted_count": self.nonaccepted_count,
            "exact_pair_evaluation_count": self.exact_pair_evaluation_count,
            "decision_receipt_sha256s": [
                value.receipt_sha256 for value in self.decisions
            ],
            "decisions": [value.to_dict() for value in self.decisions],
            "denominator_failure_complete": True,
            "pre_refinement_geometric_admission_complete": True,
            "post_refinement_geometric_admission_complete": False,
            "activation_evidence_eligible": False,
            "producer_attested": False,
            "score_or_validity_input_consumed": False,
            "reservation_allowed": False,
            "molecular_execution_authorized": False,
            "historical_or_fresh_execution_authorized": False,
            "product_or_stage0_authority": False,
            "public_or_scientific_claim_authorized": False,
        }

    @property
    def receipt_sha256(self) -> str:
        return _verify_sealed_receipt(
            self._canonical_projection_bytes,
            self._receipt_sha256,
            name="geometric admission batch",
        )

    def to_dict(self) -> dict[str, object]:
        return {
            **_unseal_projection(self._canonical_projection_bytes),
            "receipt_sha256": self.receipt_sha256,
        }


class GeometricAdmissionV3:
    """Apply failure-aware pre-refinement admission to one sealed producer batch."""

    __slots__ = ()
    component_id = GEOMETRIC_ADMISSION_V3_COMPONENT_ID
    profile_id = GEOMETRIC_ADMISSION_V3_PROFILE_ID

    def admit_producer_batch(
        self,
        producer_batch: Mixed64ProposalProducerBatchV1,
    ) -> GeometricAdmissionBatchV3:
        if type(producer_batch) is not Mixed64ProposalProducerBatchV1:
            raise TypeError("producer_batch must be exact")
        bundle = producer_batch.source_bundle
        generated_count = producer_batch.generated_count
        pair_work = (
            generated_count
            * len(bundle.ligand_vdw_radii)
            * len(bundle.receptor_coordinates)
        )
        if pair_work > MAX_BATCH_EXACT_PAIR_EVALUATIONS:
            raise GeometricAdmissionV3Error(
                "fixed64 generated exact pair work exceeds the fail-closed limit"
            )
        decisions: list[GeometricAdmissionDecisionV3] = []
        for record in producer_batch.records:
            if record.status == GENERATION_STATUS_FAILURE:
                slot = record.allocation.slots[record.slot_index]
                failure = record.failure_receipt
                if failure is None:
                    raise GeometricAdmissionV3Error("producer failure receipt is absent")
                decisions.append(
                    GeometricAdmissionDecisionV3(
                        producer_record=record,
                        metrics=None,
                        status=(
                            TYPED_ALLOCATION_FAILURE_STATUS
                            if not slot.generation_eligible
                            else TYPED_PROPOSAL_GENERATION_FAILURE_STATUS
                        ),
                        rejection_code=failure.failure_code,
                        rank_eligible=False,
                        _factory_seal=_DECISION_FACTORY_SEAL,
                    )
                )
                continue
            if record.status != GENERATION_STATUS_SUCCESS or record.output_coordinates is None:
                raise GeometricAdmissionV3Error("producer generation status is invalid")
            try:
                metrics = evaluate_geometric_admission_metrics_one_python(
                    record.output_coordinates,
                    ligand_vdw_radii=bundle.ligand_vdw_radii,
                    ligand_heavy_atom_mask=bundle.ligand_heavy_atom_mask,
                    receptor_coordinates=bundle.receptor_coordinates,
                    receptor_vdw_radii=bundle.receptor_vdw_radii,
                    pocket_center=bundle.pocket_center,
                    pocket_radius=bundle.pocket_radius,
                )
            except GeometricAdmissionV2Error as exc:
                raise GeometricAdmissionV3Error(
                    "producer coordinates failed the bounded geometric kernel"
                ) from exc
            placement = record.placement_receipt
            if (
                type(placement) is SingleAnchorPlacementReceiptV1
                and placement.geometric_metrics.receipt_sha256
                != metrics.receipt_sha256
            ):
                raise GeometricAdmissionV3Error(
                    "single-anchor precheck disagrees with admission replay"
                )
            accepted = metrics.minimum_vdw_ratio >= HARD_REJECTION_MINIMUM_VDW_RATIO
            decisions.append(
                GeometricAdmissionDecisionV3(
                    producer_record=record,
                    metrics=metrics,
                    status=ACCEPTED_STATUS if accepted else REJECTED_STATUS,
                    rejection_code=(
                        None if accepted else SEVERE_PENETRATION_REJECTION_CODE
                    ),
                    rank_eligible=accepted,
                    _factory_seal=_DECISION_FACTORY_SEAL,
                )
            )
        return GeometricAdmissionBatchV3(
            producer_batch=producer_batch,
            decisions=tuple(decisions),
            _factory_seal=_BATCH_FACTORY_SEAL,
        )


__all__ = [
    "ACCEPTED_STATUS",
    "GEOMETRIC_ADMISSION_V3_BATCH_SCHEMA_ID",
    "GEOMETRIC_ADMISSION_V3_COMPONENT_ID",
    "GEOMETRIC_ADMISSION_V3_DECISION_SCHEMA_ID",
    "GEOMETRIC_ADMISSION_V3_POLICY_SHA256",
    "GEOMETRIC_ADMISSION_V3_POLICY_SCHEMA_ID",
    "GEOMETRIC_ADMISSION_V3_PROFILE_ID",
    "GeometricAdmissionBatchV3",
    "GeometricAdmissionDecisionV3",
    "GeometricAdmissionV3",
    "GeometricAdmissionV3Error",
    "REJECTED_STATUS",
    "TYPED_ALLOCATION_FAILURE_STATUS",
    "TYPED_PROPOSAL_GENERATION_FAILURE_STATUS",
    "frozen_geometric_admission_v3_policy",
]

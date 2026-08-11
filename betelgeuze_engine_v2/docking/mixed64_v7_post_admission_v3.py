"""Synthetic-only current-V7 execution and post-refinement admission.

The executor consumes exact operational proposals, gives each materialized slot
one V7 attempt with the frozen 24-step budget, and immediately replays the
full-Cartesian geometric gate on every successful result. All 64 slots remain
present. No score, validity, ranking, reservation, or cohort authority exists.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import InitVar, dataclass, field
import hashlib
import json
import os
from pathlib import Path
import re
import stat
from typing import Final

from .geometric_admission_v2 import (
    HARD_REJECTION_MINIMUM_VDW_RATIO,
    MAX_BATCH_EXACT_PAIR_EVALUATIONS,
    SEVERE_PENETRATION_REJECTION_CODE,
    GeometricAdmissionMetricsV2,
    GeometricAdmissionV2Error,
    evaluate_geometric_admission_metrics_one_python,
)
from .geometric_admission_v3 import GEOMETRIC_ADMISSION_V3_POLICY_SHA256
from .mixed64_operational_proposal_policy_v3 import (
    MIXED64_OPERATIONAL_PROPOSAL_POLICY_SHA256,
)
from .mixed64_allocation import FIXED_MIXED64_CANDIDATE_COUNT
from .mixed64_operational_proposal_v3 import (
    MATERIALIZED_STATUS,
    Mixed64OperationalProposalBatchV1,
    Mixed64OperationalProposalRecordV1,
    Mixed64OperationalProposalV3Error,
)
from .mixed64_proposal_geometry_v3 import coordinate_sha256
from .mixed64_v7_post_admission_policy_v3 import (
    BOUND_GEOMETRIC_ADMISSION_V3_POLICY_SHA256,
    BOUND_OPERATIONAL_PROPOSAL_POLICY_SHA256,
    MAX_TYPED_V7_FAILURE_REASON_UTF8_BYTES,
    MAX_V7_IMPLEMENTATION_SOURCE_BYTES,
    MAX_V7_POST_ADMISSION_RECEIPT_CANONICAL_BYTES,
    MIXED64_V7_POST_ADMISSION_BATCH_SCHEMA_ID,
    MIXED64_V7_POST_ADMISSION_COMPONENT_ID,
    MIXED64_V7_POST_ADMISSION_POLICY_SHA256,
    MIXED64_V7_POST_ADMISSION_PROFILE_ID,
    MIXED64_V7_POST_ADMISSION_RECORD_SCHEMA_ID,
    POST_REFINEMENT_ACCEPTED_STATUS,
    POST_REFINEMENT_HARD_REJECTION_MINIMUM_VDW_RATIO,
    POST_REFINEMENT_MAX_BATCH_EXACT_PAIR_EVALUATIONS,
    POST_REFINEMENT_REJECTED_STATUS,
    TYPED_V7_REFINEMENT_FAILURE_CODE,
    TYPED_V7_REFINEMENT_FAILURE_STATUS,
    UPSTREAM_NOT_REFINED_STATUS,
    V7_REFINEMENT_MAX_STEPS,
    V7_TORSION_ELIGIBLE_SLOT_INDICES,
    frozen_mixed64_v7_post_admission_policy,
)
from .proposals import DockingProposal, DockingProposalError
from .torsion_contact_refinement import (
    INTERACTION_AWARE_TORSION_CONTACT_RECEIPT_V7_SCHEMA_ID,
    INTERACTION_AWARE_TORSION_CONTACT_REFINER_V7_ID,
    INTERACTION_AWARE_TORSION_CONTACT_REFINER_V7_VERSION,
    InteractionAwareTorsionContactEnsembleRefinerV7,
    TorsionContactRefinementError,
)
from . import torsion_contact_refinement as _refinement_module


_STATUSES: Final = {
    POST_REFINEMENT_ACCEPTED_STATUS,
    POST_REFINEMENT_REJECTED_STATUS,
    TYPED_V7_REFINEMENT_FAILURE_STATUS,
    UPSTREAM_NOT_REFINED_STATUS,
}
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_RECORD_FACTORY_SEAL = object()
_BATCH_FACTORY_SEAL = object()

if (
    MIXED64_OPERATIONAL_PROPOSAL_POLICY_SHA256
    != BOUND_OPERATIONAL_PROPOSAL_POLICY_SHA256
):
    raise RuntimeError("V7 post-admission operational policy binding changed")
if (
    GEOMETRIC_ADMISSION_V3_POLICY_SHA256 != BOUND_GEOMETRIC_ADMISSION_V3_POLICY_SHA256
    or HARD_REJECTION_MINIMUM_VDW_RATIO
    != POST_REFINEMENT_HARD_REJECTION_MINIMUM_VDW_RATIO
    or MAX_BATCH_EXACT_PAIR_EVALUATIONS
    != POST_REFINEMENT_MAX_BATCH_EXACT_PAIR_EVALUATIONS
):
    raise RuntimeError("V7 post-admission geometric policy binding changed")


class Mixed64V7PostAdmissionV3Error(ValueError):
    """Raised when V7 or post-admission evidence cannot remain exact."""


def _thaw(value: object) -> object:
    if isinstance(value, Mapping):
        return {str(key): _thaw(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_thaw(item) for item in value]
    return value


def _canonical_bytes(value: object) -> bytes:
    try:
        payload = json.dumps(
            _thaw(value),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("ascii")
    except (TypeError, ValueError, UnicodeError) as exc:
        raise Mixed64V7PostAdmissionV3Error(
            "V7 post-admission receipt is not canonical JSON"
        ) from exc
    if len(payload) > MAX_V7_POST_ADMISSION_RECEIPT_CANONICAL_BYTES:
        raise Mixed64V7PostAdmissionV3Error(
            "V7 post-admission receipt exceeds the byte bound"
        )
    return payload


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _seal_projection(value: object) -> tuple[bytes, str]:
    payload = _canonical_bytes(value)
    return payload, hashlib.sha256(payload).hexdigest()


def _unseal_projection(payload: bytes) -> dict[str, object]:
    document = json.loads(payload)
    if type(document) is not dict:
        raise Mixed64V7PostAdmissionV3Error(
            "sealed V7 post-admission receipt is not an object"
        )
    return document


def _verify_sealed_receipt(payload: bytes, expected: str, *, name: str) -> str:
    observed = hashlib.sha256(payload).hexdigest()
    if observed != expected:
        raise Mixed64V7PostAdmissionV3Error(f"{name} sealed receipt changed")
    return observed


def _verify_live_sealed_projection(
    payload: bytes,
    expected: str,
    projection: object,
    *,
    name: str,
) -> str:
    observed = _verify_sealed_receipt(payload, expected, name=name)
    if _canonical_bytes(projection) != payload:
        raise Mixed64V7PostAdmissionV3Error(f"{name} live projection changed")
    return observed


def _digest(value: object, *, name: str) -> str:
    if type(value) is not str or _SHA256_RE.fullmatch(value) is None:
        raise Mixed64V7PostAdmissionV3Error(f"{name} must be SHA-256")
    return value


def _typed_failure_reason(value: object) -> str:
    if type(value) is not str or not value.strip():
        raise Mixed64V7PostAdmissionV3Error(
            "typed V7 refinement failure reason is absent"
        )
    try:
        encoded = value.encode("utf-8")
    except UnicodeError as exc:
        raise Mixed64V7PostAdmissionV3Error(
            "typed V7 refinement failure reason is not UTF-8"
        ) from exc
    if len(encoded) > MAX_TYPED_V7_FAILURE_REASON_UTF8_BYTES:
        raise Mixed64V7PostAdmissionV3Error(
            "typed V7 refinement failure reason exceeds the byte bound"
        )
    return value


def _stable_source_sha256(path: Path) -> str:
    descriptor: int | None = None
    try:
        before_path = path.lstat()
        if (
            stat.S_ISLNK(before_path.st_mode)
            or not stat.S_ISREG(before_path.st_mode)
            or before_path.st_size <= 0
            or before_path.st_size > MAX_V7_IMPLEMENTATION_SOURCE_BYTES
        ):
            raise OSError("source is not a regular file")
        nofollow = getattr(os, "O_NOFOLLOW", None)
        if nofollow is None:
            raise OSError("no-follow source open is unavailable")
        flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | nofollow
        descriptor = os.open(path, flags)
        before_fd = os.fstat(descriptor)
        if (
            not stat.S_ISREG(before_fd.st_mode)
            or before_fd.st_size <= 0
            or before_fd.st_size > MAX_V7_IMPLEMENTATION_SOURCE_BYTES
            or (before_path.st_dev, before_path.st_ino)
            != (before_fd.st_dev, before_fd.st_ino)
        ):
            raise OSError("source identity changed before read")
        chunks: list[bytes] = []
        total = 0
        while True:
            read_size = min(
                1024 * 1024,
                MAX_V7_IMPLEMENTATION_SOURCE_BYTES + 1 - total,
            )
            chunk = os.read(descriptor, read_size)
            if not chunk:
                break
            chunks.append(chunk)
            total += len(chunk)
            if total > MAX_V7_IMPLEMENTATION_SOURCE_BYTES:
                raise OSError("source exceeds the byte bound")
        payload = b"".join(chunks)
        after_fd = os.fstat(descriptor)
        after_path = path.lstat()
    except OSError as exc:
        raise Mixed64V7PostAdmissionV3Error(
            "V7 implementation source is unavailable"
        ) from exc
    finally:
        if descriptor is not None:
            try:
                os.close(descriptor)
            except OSError as exc:
                raise Mixed64V7PostAdmissionV3Error(
                    "V7 implementation source descriptor did not close"
                ) from exc

    def identity(value: os.stat_result) -> tuple[int, int, int, int, int, int]:
        return (
            value.st_dev,
            value.st_ino,
            value.st_mode,
            value.st_size,
            value.st_mtime_ns,
            value.st_ctime_ns,
        )

    if (
        len(payload) != before_fd.st_size
        or identity(before_path) != identity(before_fd)
        or identity(before_fd) != identity(after_fd)
        or identity(after_fd) != identity(after_path)
    ):
        raise Mixed64V7PostAdmissionV3Error(
            "V7 implementation source changed during read"
        )
    return hashlib.sha256(payload).hexdigest()


def _coordinates(
    proposal: DockingProposal,
) -> tuple[tuple[float, float, float], ...]:
    proposal.assert_integrity()
    return tuple(
        tuple(float(component) for component in point)
        for point in proposal.coordinates.tolist()
    )


def _validate_refinement_receipt(
    *,
    source: DockingProposal,
    result: DockingProposal,
    receipt: Mapping[str, object],
    refiner_config_sha256: str,
) -> dict[str, object]:
    document = _thaw(receipt)
    if type(document) is not dict:
        raise Mixed64V7PostAdmissionV3Error("V7 receipt is not an object")
    embedded = document.pop("receipt_sha256", None)
    if (
        type(embedded) is not str
        or _SHA256_RE.fullmatch(embedded) is None
        or _sha256(document) != embedded
        or document.get("schema_id")
        != INTERACTION_AWARE_TORSION_CONTACT_RECEIPT_V7_SCHEMA_ID
        or document.get("source_proposal_sha256") != source.fingerprint_sha256
        or document.get("config_sha256") != refiner_config_sha256
        or document.get("pre_coordinates_sha256")
        != source.coordinate_fingerprint_sha256
        or document.get("post_coordinates_sha256")
        != result.coordinate_fingerprint_sha256
        or document.get("scientifically_validated") is not False
    ):
        raise Mixed64V7PostAdmissionV3Error(
            "V7 source receipt does not rederive or is cross-wired"
        )
    if (
        result.parent_proposal_fingerprint_sha256 != source.fingerprint_sha256
        or result.refinement_receipt_sha256 != embedded
        or result.refiner_id != INTERACTION_AWARE_TORSION_CONTACT_REFINER_V7_ID
        or result.refiner_version
        != INTERACTION_AWARE_TORSION_CONTACT_REFINER_V7_VERSION
    ):
        raise Mixed64V7PostAdmissionV3Error("V7 result proposal lineage is cross-wired")
    return {**document, "receipt_sha256": embedded}


@dataclass(frozen=True, slots=True)
class Mixed64V7PostAdmissionRecordV1:
    materialization_record: Mixed64OperationalProposalRecordV1 = field(repr=False)
    result_proposal: DockingProposal | None = field(repr=False)
    refinement_receipt: Mapping[str, object] | None = field(repr=False)
    post_refinement_metrics: GeometricAdmissionMetricsV2 | None
    status: str
    failure_code: str | None
    failure_reason: str | None
    rejection_code: str | None
    _factory_seal: InitVar[object | None] = None
    schema_id: str = MIXED64_V7_POST_ADMISSION_RECORD_SCHEMA_ID
    _canonical_projection_bytes: bytes = field(init=False, repr=False)
    _receipt_sha256: str = field(init=False, repr=False)

    def __post_init__(self, _factory_seal: object | None) -> None:
        if _factory_seal is not _RECORD_FACTORY_SEAL:
            raise Mixed64V7PostAdmissionV3Error(
                "V7 post-admission record requires the bounded factory"
            )
        if self.schema_id != MIXED64_V7_POST_ADMISSION_RECORD_SCHEMA_ID:
            raise Mixed64V7PostAdmissionV3Error(
                "V7 post-admission record schema changed"
            )
        if type(self.materialization_record) is not Mixed64OperationalProposalRecordV1:
            raise TypeError("materialization_record must be exact")
        if self.status not in _STATUSES:
            raise Mixed64V7PostAdmissionV3Error("V7 post-admission status is invalid")
        if self.status in {
            POST_REFINEMENT_ACCEPTED_STATUS,
            POST_REFINEMENT_REJECTED_STATUS,
        }:
            if (
                not self.materialization_record.materialized
                or type(self.result_proposal) is not DockingProposal
                or not isinstance(self.refinement_receipt, Mapping)
                or type(self.post_refinement_metrics) is not GeometricAdmissionMetricsV2
                or self.failure_code is not None
                or self.failure_reason is not None
            ):
                raise Mixed64V7PostAdmissionV3Error(
                    "successful V7 record lacks exact result evidence"
                )
            accepted = (
                self.post_refinement_metrics.minimum_vdw_ratio
                >= POST_REFINEMENT_HARD_REJECTION_MINIMUM_VDW_RATIO
            )
            if self.status != (
                POST_REFINEMENT_ACCEPTED_STATUS
                if accepted
                else POST_REFINEMENT_REJECTED_STATUS
            ) or self.rejection_code != (
                None if accepted else SEVERE_PENETRATION_REJECTION_CODE
            ):
                raise Mixed64V7PostAdmissionV3Error(
                    "post-refinement rejection semantics changed"
                )
        elif self.status == TYPED_V7_REFINEMENT_FAILURE_STATUS:
            if (
                not self.materialization_record.materialized
                or self.failure_code != TYPED_V7_REFINEMENT_FAILURE_CODE
                or _typed_failure_reason(self.failure_reason) != self.failure_reason
                or any(
                    value is not None
                    for value in (
                        self.result_proposal,
                        self.refinement_receipt,
                        self.post_refinement_metrics,
                        self.rejection_code,
                    )
                )
            ):
                raise Mixed64V7PostAdmissionV3Error(
                    "typed V7 refinement failure fabricated result evidence"
                )
        elif self.materialization_record.materialized or any(
            value is not None
            for value in (
                self.result_proposal,
                self.refinement_receipt,
                self.post_refinement_metrics,
                self.failure_code,
                self.failure_reason,
                self.rejection_code,
            )
        ):
            raise Mixed64V7PostAdmissionV3Error(
                "upstream nonmaterialized slot fabricated refinement evidence"
            )
        sealed, receipt_sha256 = _seal_projection(self._projection())
        object.__setattr__(self, "_canonical_projection_bytes", sealed)
        object.__setattr__(self, "_receipt_sha256", receipt_sha256)

    @property
    def slot_index(self) -> int:
        return self.materialization_record.slot_index

    @property
    def rank_eligible(self) -> bool:
        return self.status == POST_REFINEMENT_ACCEPTED_STATUS

    def _projection(self) -> dict[str, object]:
        source = self.materialization_record.operational_proposal
        result = self.result_proposal
        return {
            "schema_id": self.schema_id,
            "component_id": MIXED64_V7_POST_ADMISSION_COMPONENT_ID,
            "policy_sha256": MIXED64_V7_POST_ADMISSION_POLICY_SHA256,
            "slot_index": self.slot_index,
            "lane": self.materialization_record.to_dict()["lane"],
            "materialization_record_receipt_sha256": (
                self.materialization_record.receipt_sha256
            ),
            "source_operational_proposal_sha256": (
                None if source is None else source.fingerprint_sha256
            ),
            "source_operational_coordinate_fingerprint_sha256": (
                None if source is None else source.coordinate_fingerprint_sha256
            ),
            "result_operational_proposal_sha256": (
                None if result is None else result.fingerprint_sha256
            ),
            "result_operational_coordinate_fingerprint_sha256": (
                None if result is None else result.coordinate_fingerprint_sha256
            ),
            "result_evidence_coordinate_sha256": (
                None if result is None else coordinate_sha256(_coordinates(result))
            ),
            "result_proposal_identity": (
                None if result is None else result.identity_payload()
            ),
            "refinement_receipt": (
                None
                if self.refinement_receipt is None
                else _thaw(self.refinement_receipt)
            ),
            "post_refinement_geometric_metrics": (
                None
                if self.post_refinement_metrics is None
                else self.post_refinement_metrics.to_dict()
            ),
            "status": self.status,
            "failure_code": self.failure_code,
            "failure_reason": self.failure_reason,
            "failure_reason_sha256": (
                None
                if self.failure_reason is None
                else hashlib.sha256(self.failure_reason.encode("utf-8")).hexdigest()
            ),
            "rejection_code": self.rejection_code,
            "rank_eligible": self.rank_eligible,
            "slot_preserved_in_denominator": True,
            "producer_attested": False,
            "activation_evidence_eligible": False,
            "molecular_cohort_execution_authorized": False,
            "reservation_allowed": False,
            "product_or_stage0_authority": False,
            "public_or_scientific_claim_authorized": False,
        }

    @property
    def receipt_sha256(self) -> str:
        return _verify_sealed_receipt(
            self._canonical_projection_bytes,
            self._receipt_sha256,
            name="V7 post-admission record",
        )

    def assert_live_integrity(self) -> str:
        return self._assert_live_integrity(operational_already_verified=False)

    def _assert_live_integrity(self, *, operational_already_verified: bool) -> str:
        try:
            if not operational_already_verified:
                self.materialization_record.assert_live_integrity()
            if self.result_proposal is not None:
                self.result_proposal.assert_integrity()
            if self.post_refinement_metrics is not None:
                _ = self.post_refinement_metrics.receipt_sha256
            return _verify_live_sealed_projection(
                self._canonical_projection_bytes,
                self._receipt_sha256,
                self._projection(),
                name="V7 post-admission record",
            )
        except Mixed64V7PostAdmissionV3Error:
            raise
        except (
            DockingProposalError,
            GeometricAdmissionV2Error,
            Mixed64OperationalProposalV3Error,
        ) as exc:
            raise Mixed64V7PostAdmissionV3Error(
                "V7 post-admission record live integrity failed"
            ) from exc

    def to_dict(self) -> dict[str, object]:
        return {
            **_unseal_projection(self._canonical_projection_bytes),
            "receipt_sha256": self.receipt_sha256,
        }


@dataclass(frozen=True, slots=True)
class Mixed64V7PostAdmissionBatchV1:
    operational_batch: Mixed64OperationalProposalBatchV1 = field(repr=False)
    records: tuple[Mixed64V7PostAdmissionRecordV1, ...]
    refiner_config_sha256: str
    refiner_implementation_source_sha256: str
    _factory_seal: InitVar[object | None] = None
    schema_id: str = MIXED64_V7_POST_ADMISSION_BATCH_SCHEMA_ID
    profile_id: str = MIXED64_V7_POST_ADMISSION_PROFILE_ID
    _canonical_projection_bytes: bytes = field(init=False, repr=False)
    _receipt_sha256: str = field(init=False, repr=False)

    def __post_init__(self, _factory_seal: object | None) -> None:
        if _factory_seal is not _BATCH_FACTORY_SEAL:
            raise Mixed64V7PostAdmissionV3Error(
                "V7 post-admission batch requires the bounded factory"
            )
        if (
            self.schema_id != MIXED64_V7_POST_ADMISSION_BATCH_SCHEMA_ID
            or self.profile_id != MIXED64_V7_POST_ADMISSION_PROFILE_ID
        ):
            raise Mixed64V7PostAdmissionV3Error(
                "V7 post-admission batch identity changed"
            )
        if type(self.operational_batch) is not Mixed64OperationalProposalBatchV1:
            raise TypeError("operational_batch must be exact")
        if (
            type(self.records) is not tuple
            or len(self.records) != FIXED_MIXED64_CANDIDATE_COUNT
            or any(
                type(value) is not Mixed64V7PostAdmissionRecordV1
                for value in self.records
            )
            or tuple(value.slot_index for value in self.records)
            != tuple(range(FIXED_MIXED64_CANDIDATE_COUNT))
        ):
            raise Mixed64V7PostAdmissionV3Error(
                "V7 post-admission denominator or order changed"
            )
        for source, record in zip(
            self.operational_batch.records, self.records, strict=True
        ):
            if source.receipt_sha256 != record.materialization_record.receipt_sha256:
                raise Mixed64V7PostAdmissionV3Error(
                    "V7 post-admission source record is cross-wired"
                )
        bundle = self.operational_batch.admission_batch.producer_batch.source_bundle
        successful_count = sum(
            value.status
            in {POST_REFINEMENT_ACCEPTED_STATUS, POST_REFINEMENT_REJECTED_STATUS}
            for value in self.records
        )
        expected_pair_evaluations = (
            successful_count
            * len(bundle.ligand_vdw_radii)
            * len(bundle.receptor_coordinates)
        )
        if (
            expected_pair_evaluations > POST_REFINEMENT_MAX_BATCH_EXACT_PAIR_EVALUATIONS
            or self.exact_pair_evaluation_count != expected_pair_evaluations
        ):
            raise Mixed64V7PostAdmissionV3Error(
                "V7 post-admission exact pair denominator changed"
            )
        object.__setattr__(
            self,
            "refiner_config_sha256",
            _digest(self.refiner_config_sha256, name="refiner config"),
        )
        object.__setattr__(
            self,
            "refiner_implementation_source_sha256",
            _digest(
                self.refiner_implementation_source_sha256,
                name="refiner implementation source",
            ),
        )
        sealed, receipt_sha256 = _seal_projection(self._projection())
        object.__setattr__(self, "_canonical_projection_bytes", sealed)
        object.__setattr__(self, "_receipt_sha256", receipt_sha256)

    @property
    def post_refinement_accepted_count(self) -> int:
        return sum(
            value.status == POST_REFINEMENT_ACCEPTED_STATUS for value in self.records
        )

    @property
    def post_refinement_rejected_count(self) -> int:
        return sum(
            value.status == POST_REFINEMENT_REJECTED_STATUS for value in self.records
        )

    @property
    def typed_refinement_failure_count(self) -> int:
        return sum(
            value.status == TYPED_V7_REFINEMENT_FAILURE_STATUS for value in self.records
        )

    @property
    def upstream_not_refined_count(self) -> int:
        return sum(
            value.status == UPSTREAM_NOT_REFINED_STATUS for value in self.records
        )

    @property
    def exact_pair_evaluation_count(self) -> int:
        return sum(
            0
            if value.post_refinement_metrics is None
            else value.post_refinement_metrics.exact_pair_count
            for value in self.records
        )

    def _projection(self) -> dict[str, object]:
        return {
            "schema_id": self.schema_id,
            "component_id": MIXED64_V7_POST_ADMISSION_COMPONENT_ID,
            "profile_id": self.profile_id,
            "policy": frozen_mixed64_v7_post_admission_policy(),
            "policy_sha256": MIXED64_V7_POST_ADMISSION_POLICY_SHA256,
            "operational_batch_receipt_sha256": self.operational_batch.receipt_sha256,
            "operational_batch": self.operational_batch.to_dict(),
            "refiner_config_sha256": self.refiner_config_sha256,
            "refiner_implementation_source_sha256": (
                self.refiner_implementation_source_sha256
            ),
            "candidate_denominator": len(self.records),
            "post_refinement_accepted_count": self.post_refinement_accepted_count,
            "post_refinement_rejected_count": self.post_refinement_rejected_count,
            "typed_refinement_failure_count": self.typed_refinement_failure_count,
            "upstream_not_refined_count": self.upstream_not_refined_count,
            "exact_pair_evaluation_count": self.exact_pair_evaluation_count,
            "record_receipt_sha256s": [value.receipt_sha256 for value in self.records],
            "records": [value.to_dict() for value in self.records],
            "denominator_failure_complete": True,
            "synthetic_v7_refinement_executed": True,
            "post_refinement_geometric_admission_complete": True,
            "scoring_validity_ranking_executed": False,
            "producer_attested": False,
            "activation_evidence_eligible": False,
            "molecular_cohort_execution_authorized": False,
            "reservation_allowed": False,
            "historical_or_fresh_execution_authorized": False,
            "product_or_stage0_authority": False,
            "public_or_scientific_claim_authorized": False,
        }

    @property
    def receipt_sha256(self) -> str:
        return _verify_sealed_receipt(
            self._canonical_projection_bytes,
            self._receipt_sha256,
            name="V7 post-admission batch",
        )

    def assert_live_integrity(self) -> str:
        try:
            self.operational_batch.assert_live_integrity()
            for record in self.records:
                record._assert_live_integrity(operational_already_verified=True)
            return _verify_live_sealed_projection(
                self._canonical_projection_bytes,
                self._receipt_sha256,
                self._projection(),
                name="V7 post-admission batch",
            )
        except Mixed64V7PostAdmissionV3Error:
            raise
        except Mixed64OperationalProposalV3Error as exc:
            raise Mixed64V7PostAdmissionV3Error(
                "V7 post-admission batch live integrity failed"
            ) from exc

    def to_dict(self) -> dict[str, object]:
        return {
            **_unseal_projection(self._canonical_projection_bytes),
            "receipt_sha256": self.receipt_sha256,
        }


def execute_synthetic_mixed64_v7_post_admission(
    operational_batch: Mixed64OperationalProposalBatchV1,
    *,
    refiner: InteractionAwareTorsionContactEnsembleRefinerV7,
) -> Mixed64V7PostAdmissionBatchV1:
    """Run one synthetic V7 attempt per materialized slot and recheck geometry."""

    if type(operational_batch) is not Mixed64OperationalProposalBatchV1:
        raise TypeError("operational_batch must be exact")
    if type(refiner) is not InteractionAwareTorsionContactEnsembleRefinerV7:
        raise TypeError("refiner must be exact current V7")
    try:
        operational_batch.assert_live_integrity()
    except Mixed64OperationalProposalV3Error as exc:
        raise Mixed64V7PostAdmissionV3Error(
            "operational batch live integrity preflight failed"
        ) from exc
    if tuple(refiner._v3_proposal_indices) != V7_TORSION_ELIGIBLE_SLOT_INDICES:
        raise Mixed64V7PostAdmissionV3Error(
            "V7 torsion-eligible slot profile is cross-wired"
        )
    if refiner.receipts:
        raise Mixed64V7PostAdmissionV3Error("V7 refiner contains preexisting receipts")
    materialized = tuple(
        value for value in operational_batch.records if value.materialized
    )
    proposals = tuple(
        value.operational_proposal
        for value in materialized
        if value.operational_proposal is not None
    )
    if len(proposals) != len(materialized) or len(
        {value.fingerprint_sha256 for value in proposals}
    ) != len(proposals):
        raise Mixed64V7PostAdmissionV3Error(
            "materialized operational proposals are absent or duplicated"
        )
    if any(
        proposal.proposal_index != materialization.slot_index
        for materialization, proposal in zip(
            materialized,
            proposals,
            strict=True,
        )
    ):
        raise Mixed64V7PostAdmissionV3Error(
            "materialized operational proposal index is not the fixed64 slot"
        )
    problem_identities = {value.problem_fingerprint_sha256 for value in proposals}
    if problem_identities and problem_identities != {
        refiner.problem_fingerprint_sha256
    }:
        raise Mixed64V7PostAdmissionV3Error(
            "V7 refiner problem identity is cross-wired"
        )
    search_identities = {value.search_space_fingerprint_sha256 for value in proposals}
    if search_identities and search_identities != {
        refiner._search_space.fingerprint_sha256
    }:
        raise Mixed64V7PostAdmissionV3Error(
            "V7 refiner search-space identity is cross-wired"
        )
    bundle = operational_batch.admission_batch.producer_batch.source_bundle
    refiner_receptor_coordinates = tuple(
        tuple(float(component) for component in point)
        for point in refiner._receptor_coordinates.tolist()
    )
    if (
        coordinate_sha256(refiner_receptor_coordinates)
        != bundle.receptor_coordinate_sha256
        or tuple(float(value).hex() for value in refiner._receptor_radii.tolist())
        != tuple(float(value).hex() for value in bundle.receptor_vdw_radii)
        or tuple(float(value).hex() for value in refiner._ligand_radii.tolist())
        != tuple(float(value).hex() for value in bundle.ligand_vdw_radii)
    ):
        raise Mixed64V7PostAdmissionV3Error(
            "V7 refiner and geometric-admission context are cross-wired"
        )
    pair_work = (
        len(proposals) * len(bundle.ligand_vdw_radii) * len(bundle.receptor_coordinates)
    )
    if pair_work > POST_REFINEMENT_MAX_BATCH_EXACT_PAIR_EVALUATIONS:
        raise Mixed64V7PostAdmissionV3Error(
            "post-refinement exact pair work exceeds the fail-closed limit"
        )
    source_path = Path(str(_refinement_module.__file__))
    implementation_source_sha256 = _stable_source_sha256(source_path)
    if refiner.implementation_source_sha256 != implementation_source_sha256:
        raise Mixed64V7PostAdmissionV3Error(
            "V7 refiner implementation source identity is not exact"
        )
    config_sha256 = refiner.config_fingerprint_sha256
    outcomes: dict[str, DockingProposal | None] = {}
    failure_reasons: dict[str, str] = {}
    for proposal in proposals:
        try:
            result = refiner.refine(
                proposal,
                max_steps=V7_REFINEMENT_MAX_STEPS,
            )
        except TorsionContactRefinementError as exc:
            outcomes[proposal.fingerprint_sha256] = None
            failure_reasons[proposal.fingerprint_sha256] = _typed_failure_reason(
                str(exc)
            )
            continue
        if (
            type(result) is not DockingProposal
            or result.problem_fingerprint_sha256 != proposal.problem_fingerprint_sha256
            or result.search_space_fingerprint_sha256
            != proposal.search_space_fingerprint_sha256
            or result.proposal_index != proposal.proposal_index
            or result.seed != proposal.seed
        ):
            raise Mixed64V7PostAdmissionV3Error(
                "V7 result proposal identity is cross-wired"
            )
        outcomes[proposal.fingerprint_sha256] = result
    try:
        operational_batch.assert_live_integrity()
    except Mixed64OperationalProposalV3Error as exc:
        raise Mixed64V7PostAdmissionV3Error(
            "operational batch live integrity postflight failed"
        ) from exc
    if (
        _stable_source_sha256(source_path) != implementation_source_sha256
        or refiner.config_fingerprint_sha256 != config_sha256
    ):
        raise Mixed64V7PostAdmissionV3Error(
            "V7 implementation source or config changed during the batch"
        )
    receipts = refiner.receipts
    successful_fingerprints = {
        fingerprint for fingerprint, result in outcomes.items() if result is not None
    }
    failed_fingerprints = set(outcomes) - successful_fingerprints
    if set(failure_reasons) != failed_fingerprints:
        raise Mixed64V7PostAdmissionV3Error(
            "typed V7 failure-reason denominator changed"
        )
    if set(receipts) != successful_fingerprints:
        raise Mixed64V7PostAdmissionV3Error(
            "V7 receipt denominator disagrees with successful attempts"
        )
    records: list[Mixed64V7PostAdmissionRecordV1] = []
    for materialization in operational_batch.records:
        if materialization.status != MATERIALIZED_STATUS:
            records.append(
                Mixed64V7PostAdmissionRecordV1(
                    materialization_record=materialization,
                    result_proposal=None,
                    refinement_receipt=None,
                    post_refinement_metrics=None,
                    status=UPSTREAM_NOT_REFINED_STATUS,
                    failure_code=None,
                    failure_reason=None,
                    rejection_code=None,
                    _factory_seal=_RECORD_FACTORY_SEAL,
                )
            )
            continue
        source = materialization.operational_proposal
        if source is None:
            raise Mixed64V7PostAdmissionV3Error(
                "materialized operational proposal disappeared"
            )
        result = outcomes[source.fingerprint_sha256]
        if result is None:
            records.append(
                Mixed64V7PostAdmissionRecordV1(
                    materialization_record=materialization,
                    result_proposal=None,
                    refinement_receipt=None,
                    post_refinement_metrics=None,
                    status=TYPED_V7_REFINEMENT_FAILURE_STATUS,
                    failure_code=TYPED_V7_REFINEMENT_FAILURE_CODE,
                    failure_reason=failure_reasons[source.fingerprint_sha256],
                    rejection_code=None,
                    _factory_seal=_RECORD_FACTORY_SEAL,
                )
            )
            continue
        receipt = _validate_refinement_receipt(
            source=source,
            result=result,
            receipt=receipts[source.fingerprint_sha256],
            refiner_config_sha256=config_sha256,
        )
        try:
            metrics = evaluate_geometric_admission_metrics_one_python(
                _coordinates(result),
                ligand_vdw_radii=bundle.ligand_vdw_radii,
                ligand_heavy_atom_mask=bundle.ligand_heavy_atom_mask,
                receptor_coordinates=bundle.receptor_coordinates,
                receptor_vdw_radii=bundle.receptor_vdw_radii,
                pocket_center=bundle.pocket_center,
                pocket_radius=bundle.pocket_radius,
            )
        except GeometricAdmissionV2Error as exc:
            raise Mixed64V7PostAdmissionV3Error(
                "V7 result failed the bounded geometric kernel"
            ) from exc
        accepted = (
            metrics.minimum_vdw_ratio
            >= POST_REFINEMENT_HARD_REJECTION_MINIMUM_VDW_RATIO
        )
        records.append(
            Mixed64V7PostAdmissionRecordV1(
                materialization_record=materialization,
                result_proposal=result,
                refinement_receipt=receipt,
                post_refinement_metrics=metrics,
                status=(
                    POST_REFINEMENT_ACCEPTED_STATUS
                    if accepted
                    else POST_REFINEMENT_REJECTED_STATUS
                ),
                failure_code=None,
                failure_reason=None,
                rejection_code=(
                    None if accepted else SEVERE_PENETRATION_REJECTION_CODE
                ),
                _factory_seal=_RECORD_FACTORY_SEAL,
            )
        )
    batch = Mixed64V7PostAdmissionBatchV1(
        operational_batch=operational_batch,
        records=tuple(records),
        refiner_config_sha256=config_sha256,
        refiner_implementation_source_sha256=implementation_source_sha256,
        _factory_seal=_BATCH_FACTORY_SEAL,
    )
    try:
        batch.assert_live_integrity()
    except Mixed64V7PostAdmissionV3Error as exc:
        raise Mixed64V7PostAdmissionV3Error(
            "V7 post-admission output live integrity finalization failed"
        ) from exc
    if (
        _stable_source_sha256(source_path) != implementation_source_sha256
        or refiner.config_fingerprint_sha256 != config_sha256
    ):
        raise Mixed64V7PostAdmissionV3Error(
            "V7 implementation source or config changed during finalization"
        )
    return batch


__all__ = [
    "MIXED64_V7_POST_ADMISSION_POLICY_SHA256",
    "Mixed64V7PostAdmissionBatchV1",
    "Mixed64V7PostAdmissionRecordV1",
    "Mixed64V7PostAdmissionV3Error",
    "POST_REFINEMENT_ACCEPTED_STATUS",
    "POST_REFINEMENT_REJECTED_STATUS",
    "TYPED_V7_REFINEMENT_FAILURE_STATUS",
    "UPSTREAM_NOT_REFINED_STATUS",
    "V7_REFINEMENT_MAX_STEPS",
    "V7_TORSION_ELIGIBLE_SLOT_INDICES",
    "execute_synthetic_mixed64_v7_post_admission",
    "frozen_mixed64_v7_post_admission_policy",
]

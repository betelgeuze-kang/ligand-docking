"""Synthetic-only Scorer V1, pose-validity, and stable-rank execution.

Only post-refinement geometrically admitted fixed64 records are evaluated.
Every source slot remains present, complete ScorerV1Terms receipts are retained,
and primary ranking intentionally includes pose-invalid or validity-unavailable
scored states. This component grants no molecular or product authority.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import InitVar, dataclass, field
import hashlib
import json
import math
from pathlib import Path
import re
import stat
from typing import Final

from .contact_validity import ElementAwarePoseValidityContext
from .mixed64_scorer_validity_ranking_policy_v3 import (
    BOUND_V7_POST_ADMISSION_POLICY_SHA256,
    FROZEN_SCORER_V1_BACKEND_OPTIONS_SHA256,
    FROZEN_SCORER_V1_CONFIG_SHA256,
    FROZEN_VDW_CONTACT_POLICY_SHA256,
    MIXED64_SCORER_VALIDITY_RANKING_BATCH_SCHEMA_ID,
    MIXED64_SCORER_VALIDITY_RANKING_COMPONENT_ID,
    MIXED64_SCORER_VALIDITY_RANKING_POLICY_SHA256,
    MIXED64_SCORER_VALIDITY_RANKING_PROFILE_ID,
    MIXED64_SCORER_VALIDITY_RANKING_RECORD_SCHEMA_ID,
    SCORED_POSE_INVALID_STATUS,
    SCORED_POSE_VALID_STATUS,
    SCORED_VALIDITY_INCOMPLETE_STATUS,
    TYPED_SCORER_FAILURE_CODE,
    TYPED_SCORER_FAILURE_STATUS,
    TYPED_VALIDITY_FAILURE_CODE,
    TYPED_VALIDITY_FAILURE_STATUS,
    UPSTREAM_NOT_SCORED_STATUS,
    VALIDITY_INCOMPLETE_CODE,
    frozen_mixed64_scorer_validity_ranking_policy,
)
from .mixed64_v7_post_admission_policy_v3 import (
    MIXED64_V7_POST_ADMISSION_POLICY_SHA256,
)
from .mixed64_v7_post_admission_v3 import (
    Mixed64V7PostAdmissionBatchV1,
    Mixed64V7PostAdmissionRecordV1,
)
from .proposals import DockingProposal
from .scorer_v1 import (
    ChemistryPoseScorerV1,
    ScorerBackend,
    ScorerV1Terms,
)
from .search import DockingBatchScoreOutcome
from .validity import PoseValidityResult
from . import contact_validity as _contact_validity_module
from . import scorer_v1 as _scorer_module
from . import validity as _validity_module


_STATUSES: Final = {
    UPSTREAM_NOT_SCORED_STATUS,
    TYPED_SCORER_FAILURE_STATUS,
    TYPED_VALIDITY_FAILURE_STATUS,
    SCORED_VALIDITY_INCOMPLETE_STATUS,
    SCORED_POSE_VALID_STATUS,
    SCORED_POSE_INVALID_STATUS,
}
_REQUIRED_VALIDITY_CHECKS: Final = {
    "proper_rotation",
    "bond_lengths_preserved",
    "ligand_self_clash_free",
    "receptor_ligand_clash_free",
    "declared_chirality_preserved",
    "inside_declared_pocket",
    "element_vdw_ligand_overlap_free",
    "element_vdw_receptor_overlap_free",
}
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_RECORD_FACTORY_SEAL = object()
_BATCH_FACTORY_SEAL = object()
_MAX_CANONICAL_RECEIPT_BYTES: Final = 128 * 1024 * 1024
_MAX_VALIDITY_MEASUREMENTS: Final = 128
_MAX_VALIDITY_BLOCKERS: Final = 64

if (
    MIXED64_V7_POST_ADMISSION_POLICY_SHA256
    != BOUND_V7_POST_ADMISSION_POLICY_SHA256
):
    raise RuntimeError("scoring stage V7 post-admission policy binding changed")


class Mixed64ScorerValidityRankingV3Error(ValueError):
    """Raised when score, validity, or ranking evidence cannot remain exact."""


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
        raise Mixed64ScorerValidityRankingV3Error(
            "scoring evidence is not canonical JSON"
        ) from exc
    if len(payload) > _MAX_CANONICAL_RECEIPT_BYTES:
        raise Mixed64ScorerValidityRankingV3Error(
            "scoring evidence exceeds the receipt byte bound"
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
        raise Mixed64ScorerValidityRankingV3Error(
            "sealed scoring receipt is not an object"
        )
    return document


def _verify_sealed_receipt(payload: bytes, expected: str, *, name: str) -> str:
    observed = hashlib.sha256(payload).hexdigest()
    if observed != expected:
        raise Mixed64ScorerValidityRankingV3Error(f"{name} sealed receipt changed")
    return observed


def _digest(value: object, *, name: str) -> str:
    if type(value) is not str or _SHA256_RE.fullmatch(value) is None:
        raise Mixed64ScorerValidityRankingV3Error(f"{name} must be SHA-256")
    return value


def _stable_source_sha256(path: Path) -> str:
    try:
        if path.is_symlink():
            raise OSError("source is a symlink")
        before = path.stat()
        if not stat.S_ISREG(before.st_mode) or before.st_size <= 0:
            raise OSError("source is not a regular file")
        payload = path.read_bytes()
        after = path.stat()
    except OSError as exc:
        raise Mixed64ScorerValidityRankingV3Error(
            "scoring implementation source is unavailable"
        ) from exc
    if (
        len(payload) != before.st_size
        or (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
        != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)
    ):
        raise Mixed64ScorerValidityRankingV3Error(
            "scoring implementation source changed during read"
        )
    return hashlib.sha256(payload).hexdigest()


def _validate_terms(
    terms: ScorerV1Terms,
    *,
    proposal_sha256: str,
    authority_input_receipt_sha256: str,
    context_fingerprint_sha256: str,
    config_fingerprint_sha256: str,
    backend_receipt_sha256: str,
) -> None:
    if type(terms) is not ScorerV1Terms:
        raise Mixed64ScorerValidityRankingV3Error(
            "Scorer V1 outcome lacks exact terms"
        )
    terms.receipt_sha256
    if (
        terms.proposal_fingerprint_sha256 != proposal_sha256
        or terms.authority_input_receipt_sha256
        != authority_input_receipt_sha256
        or terms.context_fingerprint_sha256 != context_fingerprint_sha256
        or terms.config_fingerprint_sha256 != config_fingerprint_sha256
        or terms.backend_receipt_sha256 != backend_receipt_sha256
    ):
        raise Mixed64ScorerValidityRankingV3Error(
            "Scorer V1 terms are cross-wired"
        )
    document = terms.to_dict()
    expected_terms = {
        "typed_vdw_binary64_hex",
        "electrostatics_binary64_hex",
        "directional_hbond_binary64_hex",
        "hydrophobic_contact_binary64_hex",
        "desolvation_proxy_binary64_hex",
        "torsion_energy_binary64_hex",
        "ligand_strain_binary64_hex",
        "weak_pocket_prior_binary64_hex",
        "total_score_binary64_hex",
    }
    if not expected_terms.issubset(document):
        raise Mixed64ScorerValidityRankingV3Error(
            "Scorer V1 terms receipt is incomplete"
        )
    total = math.fsum(
        float(getattr(terms, name))
        for name in (
            "typed_vdw",
            "electrostatics",
            "directional_hbond",
            "hydrophobic_contact",
            "desolvation_proxy",
            "torsion_energy",
            "ligand_strain",
            "weak_pocket_prior",
        )
    )
    if not math.isclose(total, terms.total_score, rel_tol=0.0, abs_tol=1.0e-12):
        raise Mixed64ScorerValidityRankingV3Error(
            "Scorer V1 total does not rederive from all eight terms"
        )


def _validate_validity_result(result: PoseValidityResult) -> None:
    if type(result) is not PoseValidityResult:
        raise Mixed64ScorerValidityRankingV3Error(
            "pose validity result is not exact"
        )
    checks = dict(result.checks)
    evaluated = dict(result.evaluated_checks)
    reasons = dict(result.not_evaluated_reasons)
    if (
        set(checks) != _REQUIRED_VALIDITY_CHECKS
        or set(evaluated) != _REQUIRED_VALIDITY_CHECKS
        or any(type(value) is not bool for value in checks.values())
        or any(type(value) is not bool for value in evaluated.values())
        or type(result.complete) is not bool
        or type(result.valid_within_evaluated_scope) is not bool
    ):
        raise Mixed64ScorerValidityRankingV3Error(
            "pose validity result lacks exact check evidence"
        )
    if result.complete and (
        not all(evaluated.values())
        or reasons
        or result.valid_within_evaluated_scope is not all(checks.values())
        or result.valid is bool(result.blockers)
    ):
        raise Mixed64ScorerValidityRankingV3Error(
            "complete pose validity result does not rederive"
        )
    if not result.complete and set(reasons) != {
        name for name, was_evaluated in evaluated.items() if not was_evaluated
    }:
        raise Mixed64ScorerValidityRankingV3Error(
            "incomplete pose validity reasons do not match unevaluated checks"
        )
    if len(result.measurements) > _MAX_VALIDITY_MEASUREMENTS or len(
        result.blockers
    ) > _MAX_VALIDITY_BLOCKERS:
        raise Mixed64ScorerValidityRankingV3Error(
            "pose validity evidence exceeds its capacity"
        )
    for value in result.measurements.values():
        if (
            type(value) not in {int, float}
            or isinstance(value, bool)
            or not math.isfinite(float(value))
        ):
            raise Mixed64ScorerValidityRankingV3Error(
                "pose validity measurement is not finite numeric evidence"
            )
    if any(
        type(value) is not str or not value or value != value.strip()
        for value in result.blockers
    ) or len(set(result.blockers)) != len(result.blockers):
        raise Mixed64ScorerValidityRankingV3Error(
            "pose validity blocker evidence is invalid"
        )
    _canonical_bytes(result.to_dict())


@dataclass(frozen=True, slots=True)
class Mixed64ScorerValidityRankingRecordV1:
    post_admission_record: Mixed64V7PostAdmissionRecordV1 = field(repr=False)
    scorer_terms: ScorerV1Terms | None = field(repr=False)
    pose_validity_result: PoseValidityResult | None = field(repr=False)
    status: str
    failure_code: str | None
    stable_rank: int | None
    stable_valid_rank: int | None
    scorer_implementation_source_sha256: str
    validity_implementation_source_sha256: str
    base_validity_implementation_source_sha256: str
    scorer_authority_input_receipt_sha256: str
    scorer_context_fingerprint_sha256: str
    scorer_config_fingerprint_sha256: str
    scorer_backend_receipt_sha256: str
    validity_context_fingerprint_sha256: str
    validity_config_fingerprint_sha256: str
    contact_policy_fingerprint_sha256: str
    _factory_seal: InitVar[object | None] = None
    schema_id: str = MIXED64_SCORER_VALIDITY_RANKING_RECORD_SCHEMA_ID
    _canonical_projection_bytes: bytes = field(init=False, repr=False)
    _receipt_sha256: str = field(init=False, repr=False)

    def __post_init__(self, _factory_seal: object | None) -> None:
        if _factory_seal is not _RECORD_FACTORY_SEAL:
            raise Mixed64ScorerValidityRankingV3Error(
                "scoring record requires the bounded factory"
            )
        if self.schema_id != MIXED64_SCORER_VALIDITY_RANKING_RECORD_SCHEMA_ID:
            raise Mixed64ScorerValidityRankingV3Error(
                "scoring record schema changed"
            )
        if type(self.post_admission_record) is not Mixed64V7PostAdmissionRecordV1:
            raise TypeError("post_admission_record must be exact")
        if self.status not in _STATUSES:
            raise Mixed64ScorerValidityRankingV3Error("scoring status is invalid")
        for name in (
            "scorer_implementation_source_sha256",
            "validity_implementation_source_sha256",
            "base_validity_implementation_source_sha256",
            "scorer_authority_input_receipt_sha256",
            "scorer_context_fingerprint_sha256",
            "scorer_config_fingerprint_sha256",
            "scorer_backend_receipt_sha256",
            "validity_context_fingerprint_sha256",
            "validity_config_fingerprint_sha256",
            "contact_policy_fingerprint_sha256",
        ):
            object.__setattr__(
                self,
                name,
                _digest(getattr(self, name), name=name),
            )
        source_accepted = self.post_admission_record.rank_eligible
        terms = self.scorer_terms
        validity = self.pose_validity_result
        if not source_accepted:
            if (
                self.status != UPSTREAM_NOT_SCORED_STATUS
                or terms is not None
                or validity is not None
                or self.failure_code is not None
                or self.stable_rank is not None
                or self.stable_valid_rank is not None
            ):
                raise Mixed64ScorerValidityRankingV3Error(
                    "upstream-ineligible slot fabricated score evidence"
                )
        elif self.status == TYPED_SCORER_FAILURE_STATUS:
            if (
                terms is not None
                or validity is not None
                or self.failure_code != TYPED_SCORER_FAILURE_CODE
                or self.stable_rank is not None
                or self.stable_valid_rank is not None
            ):
                raise Mixed64ScorerValidityRankingV3Error(
                    "typed scoring failure fabricated downstream evidence"
                )
        else:
            result_proposal = self.post_admission_record.result_proposal
            if type(result_proposal) is not DockingProposal or terms is None:
                raise Mixed64ScorerValidityRankingV3Error(
                    "scored slot lacks result proposal or complete terms"
                )
            _validate_terms(
                terms,
                proposal_sha256=result_proposal.fingerprint_sha256,
                authority_input_receipt_sha256=(
                    self.scorer_authority_input_receipt_sha256
                ),
                context_fingerprint_sha256=(
                    self.scorer_context_fingerprint_sha256
                ),
                config_fingerprint_sha256=(
                    self.scorer_config_fingerprint_sha256
                ),
                backend_receipt_sha256=self.scorer_backend_receipt_sha256,
            )
            if type(self.stable_rank) is not int or self.stable_rank < 1:
                raise Mixed64ScorerValidityRankingV3Error(
                    "scored slot lacks a stable primary rank"
                )
            if self.status == TYPED_VALIDITY_FAILURE_STATUS:
                if (
                    validity is not None
                    or self.failure_code != TYPED_VALIDITY_FAILURE_CODE
                    or self.stable_valid_rank is not None
                ):
                    raise Mixed64ScorerValidityRankingV3Error(
                        "typed validity failure fabricated validity evidence"
                    )
            else:
                if validity is None:
                    raise Mixed64ScorerValidityRankingV3Error(
                        "completed validity status lacks its result"
                    )
                _validate_validity_result(validity)
                if self.status == SCORED_VALIDITY_INCOMPLETE_STATUS:
                    if (
                        validity.complete
                        or self.failure_code != VALIDITY_INCOMPLETE_CODE
                        or self.stable_valid_rank is not None
                    ):
                        raise Mixed64ScorerValidityRankingV3Error(
                            "incomplete validity status is inconsistent"
                        )
                elif self.status == SCORED_POSE_VALID_STATUS:
                    if (
                        not validity.valid
                        or self.failure_code is not None
                        or type(self.stable_valid_rank) is not int
                        or self.stable_valid_rank < 1
                    ):
                        raise Mixed64ScorerValidityRankingV3Error(
                            "valid pose status is inconsistent"
                        )
                elif (
                    self.status != SCORED_POSE_INVALID_STATUS
                    or not validity.complete
                    or validity.valid
                    or self.failure_code is not None
                    or self.stable_valid_rank is not None
                ):
                    raise Mixed64ScorerValidityRankingV3Error(
                        "invalid pose status is inconsistent"
                    )
        sealed, receipt_sha256 = _seal_projection(self._projection())
        object.__setattr__(self, "_canonical_projection_bytes", sealed)
        object.__setattr__(self, "_receipt_sha256", receipt_sha256)

    @property
    def slot_index(self) -> int:
        return self.post_admission_record.slot_index

    @property
    def rank_eligible(self) -> bool:
        return self.scorer_terms is not None

    @property
    def valid_rank_eligible(self) -> bool:
        return bool(
            self.pose_validity_result is not None
            and self.pose_validity_result.valid
        )

    @property
    def score_binary64_hex(self) -> str | None:
        return (
            None
            if self.scorer_terms is None
            else self.scorer_terms.total_score.hex()
        )

    def _projection(self) -> dict[str, object]:
        result = self.post_admission_record.result_proposal
        if result is not None:
            result.assert_integrity()
        validity_projection = (
            None
            if self.pose_validity_result is None
            else {
                "schema_id": (
                    "betelgeuze.engine_v2_mixed64_pose_validity_evidence/1.0.0"
                ),
                "result_proposal_sha256": result.fingerprint_sha256,
                "result_coordinate_fingerprint_sha256": (
                    result.coordinate_fingerprint_sha256
                ),
                "validity_context_fingerprint_sha256": (
                    self.validity_context_fingerprint_sha256
                ),
                "validity_config_fingerprint_sha256": (
                    self.validity_config_fingerprint_sha256
                ),
                "contact_policy_fingerprint_sha256": (
                    self.contact_policy_fingerprint_sha256
                ),
                "validity_implementation_source_sha256": (
                    self.validity_implementation_source_sha256
                ),
                "base_validity_implementation_source_sha256": (
                    self.base_validity_implementation_source_sha256
                ),
                "result": self.pose_validity_result.to_dict(),
            }
        )
        if validity_projection is not None:
            validity_projection["receipt_sha256"] = _sha256(validity_projection)
        scorer_projection = (
            None
            if self.scorer_terms is None
            else {
                "schema_id": (
                    "betelgeuze.engine_v2_mixed64_scorer_v1_evidence/1.0.0"
                ),
                "scorer_implementation_source_sha256": (
                    self.scorer_implementation_source_sha256
                ),
                "terms_receipt_sha256": self.scorer_terms.receipt_sha256,
                "terms": self.scorer_terms.to_dict(),
            }
        )
        if scorer_projection is not None:
            scorer_projection["receipt_sha256"] = _sha256(scorer_projection)
        return {
            "schema_id": self.schema_id,
            "component_id": MIXED64_SCORER_VALIDITY_RANKING_COMPONENT_ID,
            "policy_sha256": MIXED64_SCORER_VALIDITY_RANKING_POLICY_SHA256,
            "slot_index": self.slot_index,
            "post_admission_record_receipt_sha256": (
                self.post_admission_record.receipt_sha256
            ),
            "post_admission_status": self.post_admission_record.status,
            "result_proposal_sha256": (
                None if result is None else result.fingerprint_sha256
            ),
            "result_coordinate_fingerprint_sha256": (
                None if result is None else result.coordinate_fingerprint_sha256
            ),
            "scorer_authority_input_receipt_sha256": (
                self.scorer_authority_input_receipt_sha256
            ),
            "scorer_context_fingerprint_sha256": (
                self.scorer_context_fingerprint_sha256
            ),
            "scorer_config_fingerprint_sha256": (
                self.scorer_config_fingerprint_sha256
            ),
            "scorer_backend_receipt_sha256": self.scorer_backend_receipt_sha256,
            "scorer_evidence": scorer_projection,
            "pose_validity_evidence": validity_projection,
            "status": self.status,
            "failure_code": self.failure_code,
            "score_binary64_hex": self.score_binary64_hex,
            "rank_eligible": self.rank_eligible,
            "stable_rank": self.stable_rank,
            "top1_member": self.stable_rank == 1,
            "top5_member": (
                self.stable_rank is not None and self.stable_rank <= 5
            ),
            "valid_rank_eligible": self.valid_rank_eligible,
            "stable_valid_rank": self.stable_valid_rank,
            "valid_top1_member": self.stable_valid_rank == 1,
            "valid_top5_member": (
                self.stable_valid_rank is not None
                and self.stable_valid_rank <= 5
            ),
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
            name="scoring record",
        )

    def to_dict(self) -> dict[str, object]:
        return {
            **_unseal_projection(self._canonical_projection_bytes),
            "receipt_sha256": self.receipt_sha256,
        }


@dataclass(frozen=True, slots=True)
class Mixed64ScorerValidityRankingBatchV1:
    post_admission_batch: Mixed64V7PostAdmissionBatchV1 = field(repr=False)
    records: tuple[Mixed64ScorerValidityRankingRecordV1, ...]
    scorer_implementation_source_sha256: str
    validity_implementation_source_sha256: str
    base_validity_implementation_source_sha256: str
    _factory_seal: InitVar[object | None] = None
    schema_id: str = MIXED64_SCORER_VALIDITY_RANKING_BATCH_SCHEMA_ID
    profile_id: str = MIXED64_SCORER_VALIDITY_RANKING_PROFILE_ID
    _canonical_projection_bytes: bytes = field(init=False, repr=False)
    _receipt_sha256: str = field(init=False, repr=False)

    def __post_init__(self, _factory_seal: object | None) -> None:
        if _factory_seal is not _BATCH_FACTORY_SEAL:
            raise Mixed64ScorerValidityRankingV3Error(
                "scoring batch requires the bounded factory"
            )
        if (
            self.schema_id != MIXED64_SCORER_VALIDITY_RANKING_BATCH_SCHEMA_ID
            or self.profile_id != MIXED64_SCORER_VALIDITY_RANKING_PROFILE_ID
        ):
            raise Mixed64ScorerValidityRankingV3Error(
                "scoring batch identity changed"
            )
        if type(self.post_admission_batch) is not Mixed64V7PostAdmissionBatchV1:
            raise TypeError("post_admission_batch must be exact")
        if (
            type(self.records) is not tuple
            or len(self.records) != 64
            or any(
                type(value) is not Mixed64ScorerValidityRankingRecordV1
                for value in self.records
            )
            or tuple(value.slot_index for value in self.records) != tuple(range(64))
        ):
            raise Mixed64ScorerValidityRankingV3Error(
                "scoring denominator or order changed"
            )
        for source, record in zip(
            self.post_admission_batch.records,
            self.records,
            strict=True,
        ):
            if source.receipt_sha256 != record.post_admission_record.receipt_sha256:
                raise Mixed64ScorerValidityRankingV3Error(
                    "scoring source record is cross-wired"
                )
        for name in (
            "scorer_implementation_source_sha256",
            "validity_implementation_source_sha256",
            "base_validity_implementation_source_sha256",
        ):
            object.__setattr__(
                self,
                name,
                _digest(getattr(self, name), name=name),
            )
        if any(
            (
                value.scorer_implementation_source_sha256,
                value.validity_implementation_source_sha256,
                value.base_validity_implementation_source_sha256,
            )
            != (
                self.scorer_implementation_source_sha256,
                self.validity_implementation_source_sha256,
                self.base_validity_implementation_source_sha256,
            )
            for value in self.records
        ):
            raise Mixed64ScorerValidityRankingV3Error(
                "scorer or validity source identity is cross-wired across the batch"
            )
        shared_contexts = {
            (
                value.scorer_authority_input_receipt_sha256,
                value.scorer_context_fingerprint_sha256,
                value.scorer_config_fingerprint_sha256,
                value.scorer_backend_receipt_sha256,
                value.validity_context_fingerprint_sha256,
                value.validity_config_fingerprint_sha256,
                value.contact_policy_fingerprint_sha256,
            )
            for value in self.records
        }
        if len(shared_contexts) != 1:
            raise Mixed64ScorerValidityRankingV3Error(
                "scorer or validity context is cross-wired across the batch"
            )
        score_order = tuple(
            sorted(
                (value for value in self.records if value.rank_eligible),
                key=lambda value: (
                    value.scorer_terms.total_score,
                    value.slot_index,
                    value.post_admission_record.result_proposal.fingerprint_sha256,
                ),
            )
        )
        if tuple(value.stable_rank for value in score_order) != tuple(
            range(1, len(score_order) + 1)
        ):
            raise Mixed64ScorerValidityRankingV3Error(
                "primary score ranking does not rederive"
            )
        valid_order = tuple(value for value in score_order if value.valid_rank_eligible)
        if tuple(value.stable_valid_rank for value in valid_order) != tuple(
            range(1, len(valid_order) + 1)
        ):
            raise Mixed64ScorerValidityRankingV3Error(
                "valid-only ranking does not rederive"
            )
        sealed, receipt_sha256 = _seal_projection(self._projection())
        object.__setattr__(self, "_canonical_projection_bytes", sealed)
        object.__setattr__(self, "_receipt_sha256", receipt_sha256)

    @property
    def stable_ranking_slot_indices(self) -> tuple[int, ...]:
        return tuple(
            value.slot_index
            for value in sorted(
                (item for item in self.records if item.rank_eligible),
                key=lambda item: int(item.stable_rank or 0),
            )
        )

    @property
    def stable_valid_ranking_slot_indices(self) -> tuple[int, ...]:
        return tuple(
            value.slot_index
            for value in sorted(
                (item for item in self.records if item.valid_rank_eligible),
                key=lambda item: int(item.stable_valid_rank or 0),
            )
        )

    @property
    def top1_slot_index(self) -> int | None:
        return (
            None
            if not self.stable_ranking_slot_indices
            else self.stable_ranking_slot_indices[0]
        )

    @property
    def top5_slot_indices(self) -> tuple[int, ...]:
        return self.stable_ranking_slot_indices[:5]

    @property
    def valid_top1_slot_index(self) -> int | None:
        return (
            None
            if not self.stable_valid_ranking_slot_indices
            else self.stable_valid_ranking_slot_indices[0]
        )

    @property
    def valid_top5_slot_indices(self) -> tuple[int, ...]:
        return self.stable_valid_ranking_slot_indices[:5]

    @property
    def invalid_top1(self) -> bool | None:
        if self.top1_slot_index is None:
            return None
        validity = self.records[self.top1_slot_index].pose_validity_result
        return None if validity is None or not validity.complete else not validity.valid

    def _projection(self) -> dict[str, object]:
        return {
            "schema_id": self.schema_id,
            "component_id": MIXED64_SCORER_VALIDITY_RANKING_COMPONENT_ID,
            "profile_id": self.profile_id,
            "policy": frozen_mixed64_scorer_validity_ranking_policy(),
            "policy_sha256": MIXED64_SCORER_VALIDITY_RANKING_POLICY_SHA256,
            "post_admission_batch_receipt_sha256": (
                self.post_admission_batch.receipt_sha256
            ),
            "scorer_implementation_source_sha256": (
                self.scorer_implementation_source_sha256
            ),
            "validity_implementation_source_sha256": (
                self.validity_implementation_source_sha256
            ),
            "base_validity_implementation_source_sha256": (
                self.base_validity_implementation_source_sha256
            ),
            "candidate_denominator": len(self.records),
            "score_evidence_complete_count": sum(
                value.rank_eligible for value in self.records
            ),
            "pose_valid_count": sum(
                value.status == SCORED_POSE_VALID_STATUS for value in self.records
            ),
            "pose_invalid_count": sum(
                value.status == SCORED_POSE_INVALID_STATUS for value in self.records
            ),
            "typed_scorer_failure_count": sum(
                value.status == TYPED_SCORER_FAILURE_STATUS
                for value in self.records
            ),
            "typed_validity_failure_count": sum(
                value.status == TYPED_VALIDITY_FAILURE_STATUS
                for value in self.records
            ),
            "validity_incomplete_count": sum(
                value.status == SCORED_VALIDITY_INCOMPLETE_STATUS
                for value in self.records
            ),
            "upstream_not_scored_count": sum(
                value.status == UPSTREAM_NOT_SCORED_STATUS
                for value in self.records
            ),
            "stable_ranking_slot_indices": list(
                self.stable_ranking_slot_indices
            ),
            "top1_slot_index": self.top1_slot_index,
            "top5_slot_indices": list(self.top5_slot_indices),
            "invalid_top1": self.invalid_top1,
            "stable_valid_ranking_slot_indices": list(
                self.stable_valid_ranking_slot_indices
            ),
            "valid_top1_slot_index": self.valid_top1_slot_index,
            "valid_top5_slot_indices": list(self.valid_top5_slot_indices),
            "record_receipt_sha256s": [
                value.receipt_sha256 for value in self.records
            ],
            "records": [value.to_dict() for value in self.records],
            "denominator_failure_complete": True,
            "primary_ranking_includes_pose_invalid": True,
            "scorer_v1_terms_fully_preserved": True,
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
            name="scoring batch",
        )

    def to_dict(self) -> dict[str, object]:
        return {
            **_unseal_projection(self._canonical_projection_bytes),
            "receipt_sha256": self.receipt_sha256,
        }


def execute_synthetic_mixed64_scorer_validity_ranking(
    post_admission_batch: Mixed64V7PostAdmissionBatchV1,
    *,
    scorer: ChemistryPoseScorerV1,
) -> Mixed64ScorerValidityRankingBatchV1:
    """Score and evaluate accepted synthetic fixed64 states exactly once."""

    if type(post_admission_batch) is not Mixed64V7PostAdmissionBatchV1:
        raise TypeError("post_admission_batch must be exact")
    if type(scorer) is not ChemistryPoseScorerV1:
        raise TypeError("scorer must be exact Scorer V1")
    if (
        scorer.backend is not ScorerBackend.PYTHON_REFERENCE
        or scorer.config_fingerprint_sha256 != FROZEN_SCORER_V1_CONFIG_SHA256
        or scorer.backend_options.fingerprint_sha256
        != FROZEN_SCORER_V1_BACKEND_OPTIONS_SHA256
        or scorer.backend_options.max_batch_size != 64
    ):
        raise Mixed64ScorerValidityRankingV3Error(
            "Scorer V1 execution profile is not frozen"
        )
    validity_context = scorer._authority.validity_context
    if type(validity_context) is not ElementAwarePoseValidityContext:
        raise Mixed64ScorerValidityRankingV3Error(
            "Scorer V1 validity context is not exact element-aware validity"
        )
    if (
        validity_context.contact_policy.fingerprint_sha256
        != FROZEN_VDW_CONTACT_POLICY_SHA256
    ):
        raise Mixed64ScorerValidityRankingV3Error(
            "pose validity contact policy is not frozen"
        )
    validity_context.assert_integrity()
    accepted = tuple(
        value for value in post_admission_batch.records if value.rank_eligible
    )
    proposals = tuple(value.result_proposal for value in accepted)
    if (
        any(value is None for value in proposals)
        or len({value.fingerprint_sha256 for value in proposals}) != len(proposals)
    ):
        raise Mixed64ScorerValidityRankingV3Error(
            "accepted post-admission proposal identities are absent or duplicated"
        )
    problem_identities = {value.problem_fingerprint_sha256 for value in proposals}
    if problem_identities and problem_identities != {
        scorer.problem_fingerprint_sha256
    }:
        raise Mixed64ScorerValidityRankingV3Error(
            "Scorer V1 problem identity is cross-wired"
        )
    scorer_path = Path(str(_scorer_module.__file__))
    contact_validity_path = Path(str(_contact_validity_module.__file__))
    base_validity_path = Path(str(_validity_module.__file__))
    scorer_source_sha256 = _stable_source_sha256(scorer_path)
    validity_source_sha256 = _stable_source_sha256(contact_validity_path)
    base_validity_source_sha256 = _stable_source_sha256(base_validity_path)
    if scorer.implementation_source_sha256 != scorer_source_sha256:
        raise Mixed64ScorerValidityRankingV3Error(
            "Scorer V1 implementation source identity is not exact"
        )
    outcomes = scorer.score_batch(proposals) if proposals else ()
    if type(outcomes) is not tuple or len(outcomes) != len(proposals):
        raise Mixed64ScorerValidityRankingV3Error(
            "Scorer V1 batch outcome denominator changed"
        )
    evaluated: dict[int, tuple[ScorerV1Terms | None, PoseValidityResult | None, str, str | None]] = {}
    for source, proposal, outcome in zip(accepted, proposals, outcomes, strict=True):
        if type(outcome) is not DockingBatchScoreOutcome:
            raise Mixed64ScorerValidityRankingV3Error(
                "Scorer V1 batch outcome is not exact"
            )
        if outcome.error is not None:
            if outcome.score is not None or outcome.evidence is not None:
                raise Mixed64ScorerValidityRankingV3Error(
                    "failed Scorer V1 outcome fabricated score evidence"
                )
            evaluated[source.slot_index] = (
                None,
                None,
                TYPED_SCORER_FAILURE_STATUS,
                TYPED_SCORER_FAILURE_CODE,
            )
            continue
        terms = outcome.evidence
        _validate_terms(
            terms,
            proposal_sha256=proposal.fingerprint_sha256,
            authority_input_receipt_sha256=(
                scorer.authority_input_receipt_sha256
            ),
            context_fingerprint_sha256=scorer.context.fingerprint_sha256,
            config_fingerprint_sha256=scorer.config_fingerprint_sha256,
            backend_receipt_sha256=scorer.backend_receipt_sha256,
        )
        score = float(outcome.score)
        if not math.isfinite(score) or score.hex() != terms.total_score.hex():
            raise Mixed64ScorerValidityRankingV3Error(
                "Scorer V1 scalar score disagrees with complete terms"
            )
        try:
            validity = validity_context.evaluate(proposal)
        except Exception:
            evaluated[source.slot_index] = (
                terms,
                None,
                TYPED_VALIDITY_FAILURE_STATUS,
                TYPED_VALIDITY_FAILURE_CODE,
            )
            continue
        _validate_validity_result(validity)
        if not validity.complete:
            status = SCORED_VALIDITY_INCOMPLETE_STATUS
            failure_code = VALIDITY_INCOMPLETE_CODE
        elif validity.valid:
            status = SCORED_POSE_VALID_STATUS
            failure_code = None
        else:
            status = SCORED_POSE_INVALID_STATUS
            failure_code = None
        evaluated[source.slot_index] = (
            terms,
            validity,
            status,
            failure_code,
        )
    if (
        _stable_source_sha256(scorer_path) != scorer_source_sha256
        or _stable_source_sha256(contact_validity_path) != validity_source_sha256
        or _stable_source_sha256(base_validity_path) != base_validity_source_sha256
    ):
        raise Mixed64ScorerValidityRankingV3Error(
            "scorer or validity source changed during the batch"
        )
    validity_context.assert_integrity()
    score_order = tuple(
        sorted(
            (
                (slot_index, values[0])
                for slot_index, values in evaluated.items()
                if values[0] is not None
            ),
            key=lambda value: (
                value[1].total_score,
                value[0],
                post_admission_batch.records[
                    value[0]
                ].result_proposal.fingerprint_sha256,
            ),
        )
    )
    rank_by_slot = {
        slot_index: rank
        for rank, (slot_index, _) in enumerate(score_order, start=1)
    }
    valid_rank_by_slot = {
        slot_index: rank
        for rank, (slot_index, _) in enumerate(
            (
                value
                for value in score_order
                if evaluated[value[0]][1] is not None
                and evaluated[value[0]][1].valid
            ),
            start=1,
        )
    }
    shared = {
        "scorer_implementation_source_sha256": scorer_source_sha256,
        "validity_implementation_source_sha256": validity_source_sha256,
        "base_validity_implementation_source_sha256": (
            base_validity_source_sha256
        ),
        "scorer_authority_input_receipt_sha256": (
            scorer.authority_input_receipt_sha256
        ),
        "scorer_context_fingerprint_sha256": scorer.context.fingerprint_sha256,
        "scorer_config_fingerprint_sha256": scorer.config_fingerprint_sha256,
        "scorer_backend_receipt_sha256": scorer.backend_receipt_sha256,
        "validity_context_fingerprint_sha256": validity_context.fingerprint_sha256,
        "validity_config_fingerprint_sha256": (
            validity_context.config.fingerprint_sha256
        ),
        "contact_policy_fingerprint_sha256": (
            validity_context.contact_policy.fingerprint_sha256
        ),
    }
    records = []
    for source in post_admission_batch.records:
        if source.slot_index not in evaluated:
            terms = None
            validity = None
            status = UPSTREAM_NOT_SCORED_STATUS
            failure_code = None
        else:
            terms, validity, status, failure_code = evaluated[source.slot_index]
        records.append(
            Mixed64ScorerValidityRankingRecordV1(
                post_admission_record=source,
                scorer_terms=terms,
                pose_validity_result=validity,
                status=status,
                failure_code=failure_code,
                stable_rank=rank_by_slot.get(source.slot_index),
                stable_valid_rank=valid_rank_by_slot.get(source.slot_index),
                **shared,
                _factory_seal=_RECORD_FACTORY_SEAL,
            )
        )
    return Mixed64ScorerValidityRankingBatchV1(
        post_admission_batch=post_admission_batch,
        records=tuple(records),
        scorer_implementation_source_sha256=scorer_source_sha256,
        validity_implementation_source_sha256=validity_source_sha256,
        base_validity_implementation_source_sha256=base_validity_source_sha256,
        _factory_seal=_BATCH_FACTORY_SEAL,
    )


__all__ = [
    "MIXED64_SCORER_VALIDITY_RANKING_POLICY_SHA256",
    "Mixed64ScorerValidityRankingBatchV1",
    "Mixed64ScorerValidityRankingRecordV1",
    "Mixed64ScorerValidityRankingV3Error",
    "SCORED_POSE_INVALID_STATUS",
    "SCORED_POSE_VALID_STATUS",
    "SCORED_VALIDITY_INCOMPLETE_STATUS",
    "TYPED_SCORER_FAILURE_STATUS",
    "TYPED_VALIDITY_FAILURE_STATUS",
    "UPSTREAM_NOT_SCORED_STATUS",
    "execute_synthetic_mixed64_scorer_validity_ranking",
    "frozen_mixed64_scorer_validity_ranking_policy",
]

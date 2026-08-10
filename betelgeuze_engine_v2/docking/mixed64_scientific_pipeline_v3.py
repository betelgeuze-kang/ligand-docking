"""One sealed synthetic scientific core for the fixed64 Engine V2 stack.

The executor owns the exact stage order from source-bound proposal generation
through current-V7 refinement, post-refinement admission, Scorer V1, element-
aware pose validity, and stable ranking.  It is deliberately synthetic-only
and grants no reservation, molecular, product, Stage 0, benchmark, or claim
authority.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import InitVar, dataclass, field
import hashlib
import json
from pathlib import Path
import re
import stat
from typing import Final

from .geometric_admission_v3 import (
    GEOMETRIC_ADMISSION_V3_POLICY_SHA256,
    GeometricAdmissionBatchV3,
    GeometricAdmissionV3,
)
from .mixed64_operational_proposal_policy_v3 import (
    MIXED64_OPERATIONAL_PROPOSAL_POLICY_SHA256,
)
from .mixed64_operational_proposal_v3 import (
    Mixed64OperationalProposalBatchV1,
    materialize_mixed64_operational_proposals,
)
from .mixed64_proposal_producer_v3 import (
    MIXED64_PRODUCER_POLICY_SHA256,
    Mixed64ProposalProducerBatchV1,
    Mixed64ProposalSourceBundleV1,
    produce_fixed_mixed64_proposals,
)
from .mixed64_scientific_pipeline_policy_v3 import (
    BOUND_GEOMETRIC_ADMISSION_POLICY_SHA256,
    BOUND_OPERATIONAL_PROPOSAL_POLICY_SHA256,
    BOUND_PRODUCER_POLICY_SHA256,
    BOUND_SCORER_VALIDITY_RANKING_POLICY_SHA256,
    BOUND_V7_POST_ADMISSION_POLICY_SHA256,
    MIXED64_SCIENTIFIC_PIPELINE_COMPONENT_ID,
    MIXED64_SCIENTIFIC_PIPELINE_POLICY_SHA256,
    MIXED64_SCIENTIFIC_PIPELINE_PROFILE_ID,
    MIXED64_SCIENTIFIC_PIPELINE_RECEIPT_SCHEMA_ID,
    frozen_mixed64_scientific_pipeline_policy,
)
from .mixed64_scorer_validity_ranking_policy_v3 import (
    MIXED64_SCORER_VALIDITY_RANKING_POLICY_SHA256,
)
from .mixed64_scorer_validity_ranking_v3 import (
    Mixed64ScorerValidityRankingBatchV1,
    execute_synthetic_mixed64_scorer_validity_ranking,
)
from .mixed64_v7_post_admission_policy_v3 import (
    MIXED64_V7_POST_ADMISSION_POLICY_SHA256,
)
from .mixed64_v7_post_admission_v3 import (
    Mixed64V7PostAdmissionBatchV1,
    execute_synthetic_mixed64_v7_post_admission,
)
from .scorer_v1 import ChemistryPoseScorerV1
from .torsion_contact_refinement import (
    InteractionAwareTorsionContactEnsembleRefinerV7,
)


_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_RECEIPT_FACTORY_SEAL = object()
_MAX_CANONICAL_RECEIPT_BYTES: Final = 128 * 1024 * 1024
_STAGE_POLICY_BINDINGS: Final = {
    "fixed64_producer": (
        MIXED64_PRODUCER_POLICY_SHA256,
        BOUND_PRODUCER_POLICY_SHA256,
    ),
    "pre_refinement_geometric_admission": (
        GEOMETRIC_ADMISSION_V3_POLICY_SHA256,
        BOUND_GEOMETRIC_ADMISSION_POLICY_SHA256,
    ),
    "operational_proposal_materialization": (
        MIXED64_OPERATIONAL_PROPOSAL_POLICY_SHA256,
        BOUND_OPERATIONAL_PROPOSAL_POLICY_SHA256,
    ),
    "current_v7_post_admission": (
        MIXED64_V7_POST_ADMISSION_POLICY_SHA256,
        BOUND_V7_POST_ADMISSION_POLICY_SHA256,
    ),
    "scorer_v1_validity_stable_ranking": (
        MIXED64_SCORER_VALIDITY_RANKING_POLICY_SHA256,
        BOUND_SCORER_VALIDITY_RANKING_POLICY_SHA256,
    ),
}

if any(observed != expected for observed, expected in _STAGE_POLICY_BINDINGS.values()):
    raise RuntimeError("scientific pipeline stage policy binding changed")


class Mixed64ScientificPipelineV3Error(ValueError):
    """Raised when the exact fixed64 scientific pipeline cannot remain sealed."""


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
        raise Mixed64ScientificPipelineV3Error(
            "scientific pipeline receipt is not canonical JSON"
        ) from exc
    if len(payload) > _MAX_CANONICAL_RECEIPT_BYTES:
        raise Mixed64ScientificPipelineV3Error(
            "scientific pipeline receipt exceeds the byte bound"
        )
    return payload


def _seal_projection(value: object) -> tuple[bytes, str]:
    payload = _canonical_bytes(value)
    return payload, hashlib.sha256(payload).hexdigest()


def _unseal_projection(payload: bytes) -> dict[str, object]:
    document = json.loads(payload)
    if type(document) is not dict:
        raise Mixed64ScientificPipelineV3Error(
            "sealed scientific pipeline receipt is not an object"
        )
    return document


def _digest(value: object, *, name: str) -> str:
    if type(value) is not str or _SHA256_RE.fullmatch(value) is None:
        raise Mixed64ScientificPipelineV3Error(f"{name} must be SHA-256")
    return value


def _stable_source_sha256(path: Path) -> str:
    try:
        if path.is_symlink():
            raise OSError("source is a symlink")
        before = path.stat()
        if (
            not stat.S_ISREG(before.st_mode)
            or before.st_size <= 0
            or before.st_size > 4 * 1024 * 1024
        ):
            raise OSError("source is not bounded regular data")
        payload = path.read_bytes()
        after = path.stat()
    except OSError as exc:
        raise Mixed64ScientificPipelineV3Error(
            "scientific pipeline implementation source is unavailable"
        ) from exc
    if (
        len(payload) != before.st_size
        or (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
        != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)
    ):
        raise Mixed64ScientificPipelineV3Error(
            "scientific pipeline implementation source changed during read"
        )
    return hashlib.sha256(payload).hexdigest()


@dataclass(frozen=True, slots=True)
class Mixed64ScientificPipelineReceiptV1:
    source_bundle: Mixed64ProposalSourceBundleV1 = field(repr=False)
    producer_batch: Mixed64ProposalProducerBatchV1 = field(repr=False)
    admission_batch: GeometricAdmissionBatchV3 = field(repr=False)
    operational_batch: Mixed64OperationalProposalBatchV1 = field(repr=False)
    post_admission_batch: Mixed64V7PostAdmissionBatchV1 = field(repr=False)
    scoring_batch: Mixed64ScorerValidityRankingBatchV1 = field(repr=False)
    pipeline_implementation_source_sha256: str
    _factory_seal: InitVar[object | None] = None
    schema_id: str = MIXED64_SCIENTIFIC_PIPELINE_RECEIPT_SCHEMA_ID
    profile_id: str = MIXED64_SCIENTIFIC_PIPELINE_PROFILE_ID
    _canonical_projection_bytes: bytes = field(init=False, repr=False)
    _receipt_sha256: str = field(init=False, repr=False)

    def __post_init__(self, _factory_seal: object | None) -> None:
        if _factory_seal is not _RECEIPT_FACTORY_SEAL:
            raise Mixed64ScientificPipelineV3Error(
                "scientific pipeline receipt requires the bounded executor"
            )
        if (
            self.schema_id != MIXED64_SCIENTIFIC_PIPELINE_RECEIPT_SCHEMA_ID
            or self.profile_id != MIXED64_SCIENTIFIC_PIPELINE_PROFILE_ID
        ):
            raise Mixed64ScientificPipelineV3Error(
                "scientific pipeline receipt identity changed"
            )
        exact_types = (
            (self.source_bundle, Mixed64ProposalSourceBundleV1),
            (self.producer_batch, Mixed64ProposalProducerBatchV1),
            (self.admission_batch, GeometricAdmissionBatchV3),
            (self.operational_batch, Mixed64OperationalProposalBatchV1),
            (self.post_admission_batch, Mixed64V7PostAdmissionBatchV1),
            (self.scoring_batch, Mixed64ScorerValidityRankingBatchV1),
        )
        if any(type(value) is not expected for value, expected in exact_types):
            raise TypeError("scientific pipeline stages must be exact")
        object.__setattr__(
            self,
            "pipeline_implementation_source_sha256",
            _digest(
                self.pipeline_implementation_source_sha256,
                name="scientific pipeline implementation source",
            ),
        )
        self._validate_chain()
        sealed, receipt_sha256 = _seal_projection(self._projection())
        object.__setattr__(self, "_canonical_projection_bytes", sealed)
        object.__setattr__(self, "_receipt_sha256", receipt_sha256)

    def _validate_chain(self) -> None:
        if (
            _stable_source_sha256(Path(__file__))
            != self.pipeline_implementation_source_sha256
        ):
            raise Mixed64ScientificPipelineV3Error(
                "scientific pipeline implementation source identity changed"
            )
        source_bundle_sha256 = self.source_bundle.receipt_sha256
        allocation_sha256 = self.source_bundle.allocation.receipt_sha256
        if (
            self.producer_batch.source_bundle is not self.source_bundle
            or self.producer_batch.allocation is not self.source_bundle.allocation
            or self.producer_batch.source_bundle.receipt_sha256
            != source_bundle_sha256
            or self.producer_batch.allocation.receipt_sha256 != allocation_sha256
            or self.admission_batch.producer_batch is not self.producer_batch
            or self.operational_batch.admission_batch is not self.admission_batch
            or self.post_admission_batch.operational_batch is not self.operational_batch
            or self.scoring_batch.post_admission_batch
            is not self.post_admission_batch
        ):
            raise Mixed64ScientificPipelineV3Error(
                "scientific pipeline stage receipt is cross-wired"
            )
        stages = (
            self.producer_batch,
            self.admission_batch,
            self.operational_batch,
            self.post_admission_batch,
            self.scoring_batch,
        )
        stage_records = (
            self.producer_batch.records,
            self.admission_batch.decisions,
            self.operational_batch.records,
            self.post_admission_batch.records,
            self.scoring_batch.records,
        )
        if any(len(records) != 64 for records in stage_records):
            raise Mixed64ScientificPipelineV3Error(
                "scientific pipeline candidate denominator changed"
            )
        if any(
            tuple(record.slot_index for record in records) != tuple(range(64))
            for records in stage_records
        ):
            raise Mixed64ScientificPipelineV3Error(
                "scientific pipeline slot order changed"
            )
        for stage in stages:
            stage.receipt_sha256

    @property
    def stage_receipt_sha256s(self) -> dict[str, str]:
        return {
            "source_bundle": self.source_bundle.receipt_sha256,
            "allocation": self.source_bundle.allocation.receipt_sha256,
            "fixed64_producer": self.producer_batch.receipt_sha256,
            "pre_refinement_geometric_admission": self.admission_batch.receipt_sha256,
            "operational_proposal_materialization": self.operational_batch.receipt_sha256,
            "current_v7_post_admission": self.post_admission_batch.receipt_sha256,
            "scorer_v1_validity_stable_ranking": self.scoring_batch.receipt_sha256,
        }

    def _projection(self) -> dict[str, object]:
        final_scoring_batch = self.scoring_batch.to_dict()
        return {
            "schema_id": self.schema_id,
            "component_id": MIXED64_SCIENTIFIC_PIPELINE_COMPONENT_ID,
            "profile_id": self.profile_id,
            "policy": frozen_mixed64_scientific_pipeline_policy(),
            "policy_sha256": MIXED64_SCIENTIFIC_PIPELINE_POLICY_SHA256,
            "pipeline_implementation_source_sha256": (
                self.pipeline_implementation_source_sha256
            ),
            "source_bundle_receipt_sha256": self.source_bundle.receipt_sha256,
            "allocation_receipt_sha256": (
                self.source_bundle.allocation.receipt_sha256
            ),
            "exact_v11_source_receipt_sha256": (
                self.source_bundle.allocation.features.exact_v11_source_receipt_sha256
            ),
            "stage_receipt_sha256s": self.stage_receipt_sha256s,
            "candidate_denominator": 64,
            "stage_counts": {
                "generated": self.producer_batch.generated_count,
                "typed_generation_failure": self.producer_batch.typed_failure_count,
                "pre_refinement_accepted": self.admission_batch.accepted_count,
                "pre_refinement_rejected": (
                    self.admission_batch.geometric_rejected_count
                ),
                "typed_allocation_failure": (
                    self.admission_batch.typed_allocation_failure_count
                ),
                "typed_proposal_generation_failure": (
                    self.admission_batch.typed_proposal_generation_failure_count
                ),
                "materialized": self.operational_batch.materialized_count,
                "typed_materialization_failure": (
                    self.operational_batch.typed_materialization_failure_count
                ),
                "upstream_not_materialized": (
                    self.operational_batch.upstream_not_materialized_count
                ),
                "post_refinement_accepted": (
                    self.post_admission_batch.post_refinement_accepted_count
                ),
                "post_refinement_rejected": (
                    self.post_admission_batch.post_refinement_rejected_count
                ),
                "typed_refinement_failure": (
                    self.post_admission_batch.typed_refinement_failure_count
                ),
                "upstream_not_refined": (
                    self.post_admission_batch.upstream_not_refined_count
                ),
                "score_evidence_complete": final_scoring_batch[
                    "score_evidence_complete_count"
                ],
                "pose_valid": final_scoring_batch["pose_valid_count"],
                "pose_invalid": final_scoring_batch["pose_invalid_count"],
                "typed_scorer_failure": final_scoring_batch[
                    "typed_scorer_failure_count"
                ],
                "typed_validity_failure": final_scoring_batch[
                    "typed_validity_failure_count"
                ],
                "validity_incomplete": final_scoring_batch[
                    "validity_incomplete_count"
                ],
                "upstream_not_scored": final_scoring_batch[
                    "upstream_not_scored_count"
                ],
            },
            "stable_ranking_slot_indices": list(
                self.scoring_batch.stable_ranking_slot_indices
            ),
            "top1_slot_index": self.scoring_batch.top1_slot_index,
            "top5_slot_indices": list(self.scoring_batch.top5_slot_indices),
            "invalid_top1": self.scoring_batch.invalid_top1,
            "stable_valid_ranking_slot_indices": list(
                self.scoring_batch.stable_valid_ranking_slot_indices
            ),
            "valid_top1_slot_index": self.scoring_batch.valid_top1_slot_index,
            "valid_top5_slot_indices": list(
                self.scoring_batch.valid_top5_slot_indices
            ),
            "final_scoring_batch": final_scoring_batch,
            "denominator_failure_complete": True,
            "complete_scorer_v1_terms_preserved": True,
            "canonical_scientific_core_receipt": True,
            "producer_attested": False,
            "activation_evidence_eligible": False,
            "reservation_allowed": False,
            "molecular_cohort_execution_authorized": False,
            "historical_or_fresh_execution_authorized": False,
            "standalone_consumer_activation_authorized": False,
            "benchmark_consumer_activation_authorized": False,
            "api_consumer_activation_authorized": False,
            "product_shadow_consumer_activation_authorized": False,
            "product_or_stage0_authority": False,
            "hip_execution_authorized": False,
            "public_or_scientific_claim_authorized": False,
        }

    @property
    def receipt_sha256(self) -> str:
        self._validate_chain()
        observed = hashlib.sha256(self._canonical_projection_bytes).hexdigest()
        if observed != self._receipt_sha256:
            raise Mixed64ScientificPipelineV3Error(
                "sealed scientific pipeline receipt changed"
            )
        return observed

    def to_dict(self) -> dict[str, object]:
        return {
            **_unseal_projection(self._canonical_projection_bytes),
            "receipt_sha256": self.receipt_sha256,
        }


def execute_synthetic_mixed64_scientific_pipeline(
    source_bundle: Mixed64ProposalSourceBundleV1,
    *,
    refiner: InteractionAwareTorsionContactEnsembleRefinerV7,
    scorer: ChemistryPoseScorerV1,
) -> Mixed64ScientificPipelineReceiptV1:
    """Execute each frozen synthetic scientific stage exactly once."""

    if type(source_bundle) is not Mixed64ProposalSourceBundleV1:
        raise TypeError("source_bundle must be exact")
    if type(refiner) is not InteractionAwareTorsionContactEnsembleRefinerV7:
        raise TypeError("refiner must be exact current V7")
    if type(scorer) is not ChemistryPoseScorerV1:
        raise TypeError("scorer must be exact Scorer V1")
    source_path = Path(__file__)
    pipeline_source_sha256 = _stable_source_sha256(source_path)
    source_bundle_sha256 = source_bundle.receipt_sha256
    allocation_sha256 = source_bundle.allocation.receipt_sha256

    producer_batch = produce_fixed_mixed64_proposals(
        source_bundle.allocation,
        source_bundle=source_bundle,
    )
    admission_batch = GeometricAdmissionV3().admit_producer_batch(producer_batch)
    operational_batch = materialize_mixed64_operational_proposals(admission_batch)
    post_admission_batch = execute_synthetic_mixed64_v7_post_admission(
        operational_batch,
        refiner=refiner,
    )
    scoring_batch = execute_synthetic_mixed64_scorer_validity_ranking(
        post_admission_batch,
        scorer=scorer,
    )

    if (
        source_bundle.receipt_sha256 != source_bundle_sha256
        or source_bundle.allocation.receipt_sha256 != allocation_sha256
        or _stable_source_sha256(source_path) != pipeline_source_sha256
    ):
        raise Mixed64ScientificPipelineV3Error(
            "scientific pipeline source or input changed during execution"
        )
    return Mixed64ScientificPipelineReceiptV1(
        source_bundle=source_bundle,
        producer_batch=producer_batch,
        admission_batch=admission_batch,
        operational_batch=operational_batch,
        post_admission_batch=post_admission_batch,
        scoring_batch=scoring_batch,
        pipeline_implementation_source_sha256=pipeline_source_sha256,
        _factory_seal=_RECEIPT_FACTORY_SEAL,
    )


__all__ = [
    "Mixed64ScientificPipelineReceiptV1",
    "Mixed64ScientificPipelineV3Error",
    "execute_synthetic_mixed64_scientific_pipeline",
]

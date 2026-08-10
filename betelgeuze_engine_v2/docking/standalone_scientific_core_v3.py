"""Sealed repository-synthetic standalone execution over the fixed64 core.

This boundary accepts only the exact package-owned synthetic D0 request.  It
derives the source bundle, constructs the exact current-V7 and ScorerV1
executors, invokes the scientific pipeline once, and binds the complete chain
into one immutable receipt.  It grants no molecular, reservation, product,
benchmark, Stage 0, HIP, or claim authority.
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

from . import scorer_v1 as _scorer_module
from . import torsion_contact_refinement as _refinement_module
from .mixed64_scientific_pipeline_policy_v3 import (
    MIXED64_SCIENTIFIC_PIPELINE_POLICY_SHA256,
)
from .mixed64_scientific_pipeline_v3 import (
    Mixed64ScientificPipelineReceiptV1,
    execute_synthetic_mixed64_scientific_pipeline,
)
from .mixed64_scorer_validity_ranking_v3 import (
    SCORED_POSE_INVALID_STATUS,
    SCORED_POSE_VALID_STATUS,
    SCORED_VALIDITY_INCOMPLETE_STATUS,
    TYPED_SCORER_FAILURE_STATUS,
    TYPED_VALIDITY_FAILURE_STATUS,
    UPSTREAM_NOT_SCORED_STATUS,
    Mixed64ScorerValidityRankingRecordV1,
)
from .mixed64_v7_post_admission_policy_v3 import (
    V7_TORSION_ELIGIBLE_SLOT_INDICES,
)
from .pipeline import (
    PIPELINE_CLAIM_BLOCKERS,
    DockingPipelineRequestV1,
)
from .scorer_v1 import ChemistryPoseScorerV1
from .standalone_scientific_core_policy_v3 import (
    BOUND_REQUEST_SHA256,
    BOUND_SCIENTIFIC_PIPELINE_POLICY_SHA256,
    BOUND_SOURCE_ADAPTER_POLICY_SHA256,
    STANDALONE_SCIENTIFIC_CORE_COMPONENT_ID,
    STANDALONE_SCIENTIFIC_CORE_POLICY_SHA256,
    STANDALONE_SCIENTIFIC_CORE_PROFILE_ID,
    STANDALONE_SCIENTIFIC_CORE_RECEIPT_SCHEMA_ID,
    frozen_standalone_scientific_core_policy,
)
from .synthetic_d0_mixed64_source_policy_v3 import (
    SYNTHETIC_D0_MIXED64_SOURCE_POLICY_SHA256,
)
from .synthetic_d0_mixed64_source_v3 import (
    RepositorySyntheticD0Mixed64SourceReceiptV1,
    build_repository_synthetic_d0_mixed64_source,
)
from .torsion_contact_refinement import (
    InteractionAwareTorsionContactEnsembleRefinerV7,
)


_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_RECEIPT_FACTORY_SEAL = object()
_MAX_CANONICAL_RECEIPT_BYTES: Final = 256 * 1024 * 1024
STANDALONE_SCIENTIFIC_CORE_BLOCKERS: Final = (
    *PIPELINE_CLAIM_BLOCKERS,
    "fixed64_source_producer_not_attested",
    "standalone_scientific_core_not_product_qualified",
)
STANDALONE_SCIENTIFIC_CORE_COMPONENT_IDS: Final = {
    "source_adapter": (
        "betelgeuze.engine_v2_synthetic_d0_mixed64_source_v3/1.0.0"
    ),
    "proposal_generator": "betelgeuze.engine_v2_mixed64_proposal_producer_v3/1.0.0",
    "geometric_admission": "betelgeuze.engine_v2_geometric_admission_v3/1.0.0",
    "proposal_materializer": (
        "betelgeuze.engine_v2_mixed64_operational_proposal_v3/1.0.0"
    ),
    "refiner_and_post_admission": (
        "betelgeuze.engine_v2_mixed64_v7_post_admission_v3/1.0.0"
    ),
    "scorer_validity_ranker": (
        "betelgeuze.engine_v2_mixed64_scorer_validity_ranking_v3/1.0.0"
    ),
    "scientific_pipeline": (
        "betelgeuze.engine_v2_mixed64_scientific_pipeline_v3/1.0.0"
    ),
    "standalone_recorder": STANDALONE_SCIENTIFIC_CORE_COMPONENT_ID,
}

if (
    SYNTHETIC_D0_MIXED64_SOURCE_POLICY_SHA256
    != BOUND_SOURCE_ADAPTER_POLICY_SHA256
    or MIXED64_SCIENTIFIC_PIPELINE_POLICY_SHA256
    != BOUND_SCIENTIFIC_PIPELINE_POLICY_SHA256
):
    raise RuntimeError("standalone scientific core dependency policy changed")


class StandaloneScientificCoreV3Error(ValueError):
    """Raised when the sealed synthetic standalone boundary cannot rederive."""


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
        raise StandaloneScientificCoreV3Error(
            "standalone scientific receipt is not canonical JSON"
        ) from exc
    if len(payload) > _MAX_CANONICAL_RECEIPT_BYTES:
        raise StandaloneScientificCoreV3Error(
            "standalone scientific receipt exceeds the byte bound"
        )
    return payload


def _unseal(payload: bytes) -> dict[str, object]:
    document = json.loads(payload)
    if type(document) is not dict:
        raise StandaloneScientificCoreV3Error(
            "standalone scientific receipt is not an object"
        )
    return document


def _digest(value: object, *, name: str) -> str:
    if type(value) is not str or _SHA256_RE.fullmatch(value) is None:
        raise StandaloneScientificCoreV3Error(f"{name} must be SHA-256")
    return value


def _stable_source_sha256(path: Path) -> str:
    try:
        if path.is_symlink():
            raise OSError("source is a symlink")
        before = path.stat()
        if (
            not stat.S_ISREG(before.st_mode)
            or before.st_size <= 0
            or before.st_size > 8 * 1024 * 1024
        ):
            raise OSError("source is not bounded regular data")
        payload = path.read_bytes()
        after = path.stat()
    except OSError as exc:
        raise StandaloneScientificCoreV3Error(
            "standalone implementation source is unavailable"
        ) from exc
    if (
        len(payload) != before.st_size
        or (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
        != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)
    ):
        raise StandaloneScientificCoreV3Error(
            "standalone implementation source changed during read"
        )
    return hashlib.sha256(payload).hexdigest()


@dataclass(frozen=True, slots=True)
class StandaloneScientificCoreReceiptV1:
    request: DockingPipelineRequestV1 = field(repr=False, compare=False)
    source_adapter: RepositorySyntheticD0Mixed64SourceReceiptV1 = field(
        repr=False,
        compare=False,
    )
    scientific_pipeline: Mixed64ScientificPipelineReceiptV1 = field(
        repr=False,
        compare=False,
    )
    recorder_implementation_source_sha256: str
    scorer_implementation_source_sha256: str
    refiner_implementation_source_sha256: str
    _factory_seal: InitVar[object | None] = None
    schema_id: str = STANDALONE_SCIENTIFIC_CORE_RECEIPT_SCHEMA_ID
    profile_id: str = STANDALONE_SCIENTIFIC_CORE_PROFILE_ID
    _canonical_projection_bytes: bytes = field(init=False, repr=False)
    _receipt_sha256: str = field(init=False, repr=False)

    def __post_init__(self, _factory_seal: object | None) -> None:
        if _factory_seal is not _RECEIPT_FACTORY_SEAL:
            raise StandaloneScientificCoreV3Error(
                "standalone scientific receipt requires the bounded executor"
            )
        if (
            self.schema_id != STANDALONE_SCIENTIFIC_CORE_RECEIPT_SCHEMA_ID
            or self.profile_id != STANDALONE_SCIENTIFIC_CORE_PROFILE_ID
        ):
            raise StandaloneScientificCoreV3Error(
                "standalone scientific receipt identity changed"
            )
        if type(self.request) is not DockingPipelineRequestV1:
            raise TypeError("request must be exact DockingPipelineRequestV1")
        if type(self.source_adapter) is not RepositorySyntheticD0Mixed64SourceReceiptV1:
            raise TypeError("source_adapter must be exact")
        if type(self.scientific_pipeline) is not Mixed64ScientificPipelineReceiptV1:
            raise TypeError("scientific_pipeline must be exact")
        for name in (
            "recorder_implementation_source_sha256",
            "scorer_implementation_source_sha256",
            "refiner_implementation_source_sha256",
        ):
            object.__setattr__(
                self,
                name,
                _digest(getattr(self, name), name=name),
            )
        self._validate_chain()
        projection = _canonical_bytes(self._projection())
        object.__setattr__(self, "_canonical_projection_bytes", projection)
        object.__setattr__(
            self,
            "_receipt_sha256",
            hashlib.sha256(projection).hexdigest(),
        )

    @property
    def candidates(self) -> tuple[Mixed64ScorerValidityRankingRecordV1, ...]:
        return self.scientific_pipeline.scoring_batch.records

    @property
    def top_proposal_indices(self) -> tuple[int, ...]:
        return self.scientific_pipeline.scoring_batch.top5_slot_indices

    @property
    def top_valid_proposal_indices(self) -> tuple[int, ...]:
        return self.scientific_pipeline.scoring_batch.valid_top5_slot_indices

    @property
    def success_count(self) -> int:
        return sum(
            row.status in {SCORED_POSE_VALID_STATUS, SCORED_POSE_INVALID_STATUS}
            for row in self.candidates
        )

    @property
    def failure_count(self) -> int:
        return len(self.candidates) - self.success_count

    @property
    def abstained(self) -> bool:
        return len(self.top_proposal_indices) < 5

    @property
    def blockers(self) -> tuple[str, ...]:
        return STANDALONE_SCIENTIFIC_CORE_BLOCKERS

    @property
    def component_ids(self) -> dict[str, str]:
        return dict(STANDALONE_SCIENTIFIC_CORE_COMPONENT_IDS)

    @property
    def component_binding_mode(self) -> str:
        return "sealed_fixed64_scientific_components"

    def _validate_chain(self) -> None:
        self.request._assert_fixture_admission()
        source_sha256 = self.source_adapter.receipt_sha256
        pipeline_sha256 = self.scientific_pipeline.receipt_sha256
        scoring = self.scientific_pipeline.scoring_batch
        if (
            self.request.request_sha256 != BOUND_REQUEST_SHA256
            or self.source_adapter.request_sha256 != self.request.request_sha256
            or self.source_adapter.source_bundle.receipt_sha256
            != self.scientific_pipeline.source_bundle.receipt_sha256
            or self.scientific_pipeline.source_bundle
            is not self.source_adapter.source_bundle
            or len(scoring.records) != 64
            or tuple(row.slot_index for row in scoring.records) != tuple(range(64))
            or len(set(scoring.top5_slot_indices)) != len(scoring.top5_slot_indices)
            or len(set(scoring.valid_top5_slot_indices))
            != len(scoring.valid_top5_slot_indices)
            or source_sha256 != self.source_adapter.receipt_sha256
            or pipeline_sha256 != self.scientific_pipeline.receipt_sha256
        ):
            raise StandaloneScientificCoreV3Error(
                "standalone source, request, or scientific receipt is cross-wired"
            )
        recorder_path = Path(__file__)
        scorer_path = Path(str(_scorer_module.__file__))
        refiner_path = Path(str(_refinement_module.__file__))
        if (
            _stable_source_sha256(recorder_path)
            != self.recorder_implementation_source_sha256
            or _stable_source_sha256(scorer_path)
            != self.scorer_implementation_source_sha256
            or _stable_source_sha256(refiner_path)
            != self.refiner_implementation_source_sha256
            or scoring.scorer_implementation_source_sha256
            != self.scorer_implementation_source_sha256
            or self.scientific_pipeline.post_admission_batch.refiner_implementation_source_sha256
            != self.refiner_implementation_source_sha256
        ):
            raise StandaloneScientificCoreV3Error(
                "standalone scorer, refiner, or recorder source is cross-wired"
            )
        status_total = sum(
            row.status
            in {
                UPSTREAM_NOT_SCORED_STATUS,
                TYPED_SCORER_FAILURE_STATUS,
                TYPED_VALIDITY_FAILURE_STATUS,
                SCORED_VALIDITY_INCOMPLETE_STATUS,
                SCORED_POSE_VALID_STATUS,
                SCORED_POSE_INVALID_STATUS,
            }
            for row in scoring.records
        )
        if status_total != 64:
            raise StandaloneScientificCoreV3Error(
                "standalone scoring status denominator changed"
            )

    def _projection(self) -> dict[str, object]:
        source_document = self.source_adapter.to_dict()
        scientific_document = self.scientific_pipeline.to_dict()
        scoring = self.scientific_pipeline.scoring_batch
        return {
            "schema_id": self.schema_id,
            "component_id": STANDALONE_SCIENTIFIC_CORE_COMPONENT_ID,
            "profile_id": self.profile_id,
            "policy": frozen_standalone_scientific_core_policy(),
            "policy_sha256": STANDALONE_SCIENTIFIC_CORE_POLICY_SHA256,
            "request_sha256": self.request.request_sha256,
            "request": self.request.to_dict(),
            "pipeline_profile": self.request.profile.to_dict(),
            "fixture_id": self.request.fixture_admission.fixture_id,
            "fixture_manifest_sha256": (
                self.request.fixture_admission.manifest_sha256
            ),
            "fixture_admission_receipt_sha256": (
                self.request.fixture_admission.receipt_sha256
            ),
            "recorder_implementation_source_sha256": (
                self.recorder_implementation_source_sha256
            ),
            "source_adapter_implementation_source_sha256": (
                self.source_adapter.adapter_implementation_source_sha256
            ),
            "scientific_pipeline_implementation_source_sha256": (
                self.scientific_pipeline.pipeline_implementation_source_sha256
            ),
            "scorer_implementation_source_sha256": (
                self.scorer_implementation_source_sha256
            ),
            "refiner_implementation_source_sha256": (
                self.refiner_implementation_source_sha256
            ),
            "component_ids": dict(sorted(STANDALONE_SCIENTIFIC_CORE_COMPONENT_IDS.items())),
            "component_binding_mode": self.component_binding_mode,
            "source_adapter_receipt_sha256": self.source_adapter.receipt_sha256,
            "source_adapter_receipt": source_document,
            "scientific_pipeline_receipt_sha256": (
                self.scientific_pipeline.receipt_sha256
            ),
            "scientific_pipeline_receipt": scientific_document,
            "stage_receipt_sha256s": self.scientific_pipeline.stage_receipt_sha256s,
            "candidate_denominator": 64,
            "success_count": self.success_count,
            "failure_count": self.failure_count,
            "score_evidence_complete_count": sum(
                row.rank_eligible for row in self.candidates
            ),
            "pose_valid_count": sum(
                row.status == SCORED_POSE_VALID_STATUS for row in self.candidates
            ),
            "pose_invalid_count": sum(
                row.status == SCORED_POSE_INVALID_STATUS for row in self.candidates
            ),
            "top_proposal_indices": list(self.top_proposal_indices),
            "top_valid_proposal_indices": list(self.top_valid_proposal_indices),
            "invalid_top1": scoring.invalid_top1,
            "abstained": self.abstained,
            "blockers": list(self.blockers),
            "failure_denominator_preserved": True,
            "complete_scorer_v1_terms_preserved": True,
            "complete_pose_validity_preserved": True,
            "primary_and_valid_only_rank_preserved": True,
            "canonical_scientific_core_receipt": True,
            "canonical_components_sealed": True,
            "arbitrary_dependency_injection_used": False,
            "result_dependent_retry_performed": False,
            "network_fetch_performed": False,
            "external_reservation_requested": False,
            "producer_attested": False,
            "activation_evidence_eligible": False,
            "canonical_docking_pipeline_activation_authorized": True,
            "cli_activation_authorized": True,
            "api_activation_authorized": True,
            "benchmark_activation_authorized": True,
            "product_shadow_activation_authorized": True,
            "consumer_activation_scope": "exact_repository_synthetic_d0_only",
            "reservation_allowed": False,
            "molecular_cohort_execution_authorized": False,
            "historical_or_fresh_execution_authorized": False,
            "stage0_admission_authority": False,
            "product_execution_authorized": False,
            "product_mutation_authorized": False,
            "existing_rank_auto_change_authorized": False,
            "customer_pose_emission_authorized": False,
            "public_benchmark_execution_authorized": False,
            "hip_execution_authorized": False,
            "public_or_scientific_claim_authorized": False,
            "claim_safe": False,
        }

    @property
    def receipt_sha256(self) -> str:
        self._validate_chain()
        observed = hashlib.sha256(self._canonical_projection_bytes).hexdigest()
        if observed != self._receipt_sha256:
            raise StandaloneScientificCoreV3Error(
                "standalone scientific receipt changed"
            )
        return observed

    def to_dict(self) -> dict[str, object]:
        return {
            **_unseal(self._canonical_projection_bytes),
            "receipt_sha256": self.receipt_sha256,
        }


def execute_repository_synthetic_d0_standalone_scientific_core(
    request: DockingPipelineRequestV1,
) -> StandaloneScientificCoreReceiptV1:
    """Execute the exact package-owned synthetic D0 scientific core once."""

    if type(request) is not DockingPipelineRequestV1:
        raise TypeError("request must be exact DockingPipelineRequestV1")
    request._assert_fixture_admission()
    if request.request_sha256 != BOUND_REQUEST_SHA256:
        raise StandaloneScientificCoreV3Error(
            "request is not the exact repository synthetic D0 fixture"
        )
    recorder_path = Path(__file__)
    scorer_path = Path(str(_scorer_module.__file__))
    refiner_path = Path(str(_refinement_module.__file__))
    recorder_source_sha256 = _stable_source_sha256(recorder_path)
    scorer_source_sha256 = _stable_source_sha256(scorer_path)
    refiner_source_sha256 = _stable_source_sha256(refiner_path)

    source = build_repository_synthetic_d0_mixed64_source(request)
    source_receipt_sha256 = source.receipt_sha256
    refiner = InteractionAwareTorsionContactEnsembleRefinerV7(
        source.authority,
        request.receptor_system,
        request.ligand_system,
        implementation_source_sha256=refiner_source_sha256,
        v3_proposal_indices=V7_TORSION_ELIGIBLE_SLOT_INDICES,
    )
    scorer = ChemistryPoseScorerV1(
        source.authority,
        request.receptor_system,
        request.ligand_system,
        implementation_source_sha256=scorer_source_sha256,
    )
    scientific = execute_synthetic_mixed64_scientific_pipeline(
        source.source_bundle,
        refiner=refiner,
        scorer=scorer,
    )
    scientific_receipt_sha256 = scientific.receipt_sha256
    if (
        _stable_source_sha256(recorder_path) != recorder_source_sha256
        or _stable_source_sha256(scorer_path) != scorer_source_sha256
        or _stable_source_sha256(refiner_path) != refiner_source_sha256
        or request.request_sha256 != BOUND_REQUEST_SHA256
        or source.receipt_sha256 != source_receipt_sha256
        or scientific.receipt_sha256 != scientific_receipt_sha256
    ):
        raise StandaloneScientificCoreV3Error(
            "standalone implementation or input changed during execution"
        )
    return StandaloneScientificCoreReceiptV1(
        request=request,
        source_adapter=source,
        scientific_pipeline=scientific,
        recorder_implementation_source_sha256=recorder_source_sha256,
        scorer_implementation_source_sha256=scorer_source_sha256,
        refiner_implementation_source_sha256=refiner_source_sha256,
        _factory_seal=_RECEIPT_FACTORY_SEAL,
    )


__all__ = [
    "STANDALONE_SCIENTIFIC_CORE_BLOCKERS",
    "STANDALONE_SCIENTIFIC_CORE_COMPONENT_IDS",
    "StandaloneScientificCoreReceiptV1",
    "StandaloneScientificCoreV3Error",
    "execute_repository_synthetic_d0_standalone_scientific_core",
]

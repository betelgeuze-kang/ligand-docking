"""One claim-blocked CPU docking core shared by future product surfaces.

The pipeline composes the current V7/Scorer-v1 baseline from canonical,
already-prepared molecular systems.  It deliberately performs no parsing,
protonation, tautomer selection, atom typing, partial-charge generation,
pocket prediction, external reservation, or product action.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
from importlib import resources
import json
import math
from typing import Mapping, Protocol, runtime_checkable

import torch

from betelgeuze_engine_v2.molecular import (
    AllAtomSystem,
    canonical_system_sha256,
    require_valid_all_atom_system,
)
from .authority import AuthenticatedDockingProblem, PocketDefinition
from .contact_validity import (
    build_element_aware_authenticated_known_pocket_docking_problem,
)
from .guided_placement import (
    GuidedPlacementContext,
    GuidedPlacementPolicy,
    build_guided_placement_context,
    uniform_v3_ensemble_proposal_indices,
)
from .proposals import DockingBudget
from .scorer_v1 import (
    ChemistryPoseScorerV1,
    ScorerBackend,
    ScorerBackendOptions,
    ScorerV1GuidedSearchResult,
    ScorerV1Terms,
    run_authenticated_scorer_v1_guided_search,
)
from .torsion_contact_refinement import (
    InteractionAwareTorsionContactEnsembleRefinerV7,
)


PIPELINE_REQUEST_SCHEMA_ID = "betelgeuze.engine_v2_docking_pipeline_request/1.0.0"
PIPELINE_PROFILE_SCHEMA_ID = "betelgeuze.engine_v2_docking_pipeline_profile/1.0.0"
PIPELINE_CANDIDATE_SCHEMA_ID = "betelgeuze.engine_v2_docking_pipeline_candidate/1.0.0"
PIPELINE_RESULT_SCHEMA_ID = "betelgeuze.engine_v2_docking_pipeline_result/1.0.0"
CURRENT_V7_FIXED64_PROFILE_ID = (
    "betelgeuze.engine_v2_cpu_current_v7_scorer_v1_fixed64/1.0.0"
)
SYNTHETIC_TEST_PROFILE_ID = (
    "betelgeuze.engine_v2_cpu_synthetic_test_profile/1.0.0"
)
EXTERNAL_AUTHORITY_BLOCKERS = (
    "external_reservation_provider_not_operational",
    "external_reservation_endpoint_not_configured",
    "external_reservation_trust_anchor_not_configured",
    "historical_execution_operational_authority_false",
)
PIPELINE_CLAIM_BLOCKERS = (
    *EXTERNAL_AUTHORITY_BLOCKERS,
    "standalone_pipeline_test_only",
    "scorer_v1_not_validated_for_docking_ranking",
    "standalone_pipeline_product_integration_not_qualified",
    "public_or_scientific_claim_authority_false",
)


class DockingPipelineError(RuntimeError):
    """The standalone CPU pipeline failed closed."""


def _canonical_bytes(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("ascii")
    except (TypeError, ValueError) as exc:
        raise DockingPipelineError("pipeline evidence is not canonical JSON") from exc


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _digest(value: object, *, name: str) -> str:
    text = str(value or "").strip().lower()
    if len(text) != 64 or any(character not in "0123456789abcdef" for character in text):
        raise DockingPipelineError(f"{name} must be a lowercase SHA-256")
    return text


def _observed_docking_source_sha256(filename: str) -> str:
    try:
        payload = resources.files("betelgeuze_engine_v2.docking").joinpath(
            filename
        ).read_bytes()
    except (FileNotFoundError, ModuleNotFoundError, OSError) as exc:
        raise DockingPipelineError(
            f"installed docking source {filename!r} is unavailable"
        ) from exc
    if not payload:
        raise DockingPipelineError(f"installed docking source {filename!r} is empty")
    return hashlib.sha256(payload).hexdigest()


def observed_pipeline_source_sha256() -> str:
    """Hash the installed pipeline source without claiming pre-import attestation."""

    return _observed_docking_source_sha256("pipeline.py")


@dataclass(frozen=True, slots=True)
class DockingPipelineProfileV1:
    profile_id: str = CURRENT_V7_FIXED64_PROFILE_ID
    candidate_count: int = 64
    top_k: int = 5
    max_torsions: int = 32
    max_refinement_steps: int = 24
    translation_radius_angstrom: float = 4.0
    receptor_margin_angstrom: float = 4.0
    test_only_profile: bool = False
    _receipt_sha256: str = field(init=False, repr=False)

    def __post_init__(self) -> None:
        profile_id = str(self.profile_id or "").strip()
        if profile_id not in {
            CURRENT_V7_FIXED64_PROFILE_ID,
            SYNTHETIC_TEST_PROFILE_ID,
        }:
            raise DockingPipelineError("pipeline profile ID is not admitted")
        for name, value, lower, upper in (
            ("candidate_count", self.candidate_count, 1, 64),
            ("top_k", self.top_k, 1, 64),
            ("max_torsions", self.max_torsions, 0, 32),
            ("max_refinement_steps", self.max_refinement_steps, 1, 24),
        ):
            if type(value) is not int or not lower <= value <= upper:
                raise DockingPipelineError(f"pipeline {name} is outside its bound")
        if self.top_k > self.candidate_count:
            raise DockingPipelineError("pipeline top_k exceeds the candidate denominator")
        for name, value in (
            ("translation_radius_angstrom", self.translation_radius_angstrom),
            ("receptor_margin_angstrom", self.receptor_margin_angstrom),
        ):
            number = float(value)
            if not math.isfinite(number) or not 0.0 < number <= 20.0:
                raise DockingPipelineError(f"pipeline {name} is outside its bound")
            object.__setattr__(self, name, number)
        if profile_id == CURRENT_V7_FIXED64_PROFILE_ID and (
            self.candidate_count != 64
            or self.top_k != 5
            or self.max_torsions != 32
            or self.max_refinement_steps != 24
            or self.translation_radius_angstrom.hex() != (4.0).hex()
            or self.receptor_margin_angstrom.hex() != (4.0).hex()
            or self.test_only_profile is not False
        ):
            raise DockingPipelineError("the current V7 fixed64 profile was changed")
        if profile_id == SYNTHETIC_TEST_PROFILE_ID and self.test_only_profile is not True:
            raise DockingPipelineError("synthetic profiles must be explicitly test-only")
        object.__setattr__(self, "profile_id", profile_id)
        object.__setattr__(self, "_receipt_sha256", _sha256(self._projection()))

    @classmethod
    def synthetic_test(
        cls,
        *,
        candidate_count: int = 4,
        top_k: int = 2,
        max_torsions: int = 4,
        max_refinement_steps: int = 1,
    ) -> "DockingPipelineProfileV1":
        return cls(
            profile_id=SYNTHETIC_TEST_PROFILE_ID,
            candidate_count=candidate_count,
            top_k=top_k,
            max_torsions=max_torsions,
            max_refinement_steps=max_refinement_steps,
            translation_radius_angstrom=1.0,
            receptor_margin_angstrom=4.0,
            test_only_profile=True,
        )

    def _projection(self) -> dict[str, object]:
        return {
            "schema_id": PIPELINE_PROFILE_SCHEMA_ID,
            "profile_id": self.profile_id,
            "candidate_count": self.candidate_count,
            "top_k": self.top_k,
            "max_torsions": self.max_torsions,
            "max_refinement_steps": self.max_refinement_steps,
            "translation_radius_angstrom_binary64_hex": (
                self.translation_radius_angstrom.hex()
            ),
            "receptor_margin_angstrom_binary64_hex": (
                self.receptor_margin_angstrom.hex()
            ),
            "proposal_profile": "current_uniform_v3_ensemble",
            "scorer": "ScorerV1",
            "refiner": "V7",
            "geometric_admission": "pass_through_not_enabled",
            "clearance_shadow_selection_enabled": False,
            "result_dependent_allocation": False,
            "test_only_profile": self.test_only_profile,
            "stage0_eligible": False,
            "product_qualified": False,
            "claim_safe": False,
        }

    @property
    def receipt_sha256(self) -> str:
        observed = _sha256(self._projection())
        if observed != self._receipt_sha256:
            raise DockingPipelineError("pipeline profile changed")
        return observed

    def to_dict(self) -> dict[str, object]:
        return {**self._projection(), "receipt_sha256": self.receipt_sha256}


@dataclass(frozen=True, slots=True)
class DockingPipelineRequestV1:
    receptor_system: AllAtomSystem = field(repr=False, compare=False)
    ligand_system: AllAtomSystem = field(repr=False, compare=False)
    pocket: PocketDefinition = field(repr=False, compare=False)
    seed: int
    profile: DockingPipelineProfileV1 = field(
        default_factory=DockingPipelineProfileV1
    )
    test_only: bool = True
    _request_sha256: str = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if not isinstance(self.receptor_system, AllAtomSystem):
            raise TypeError("receptor_system must be AllAtomSystem")
        if not isinstance(self.ligand_system, AllAtomSystem):
            raise TypeError("ligand_system must be AllAtomSystem")
        if not isinstance(self.pocket, PocketDefinition):
            raise TypeError("pocket must be PocketDefinition")
        if type(self.seed) is not int or not 0 <= self.seed < 2**63:
            raise DockingPipelineError("pipeline seed is invalid")
        if type(self.profile) is not DockingPipelineProfileV1:
            raise TypeError("profile must be exact DockingPipelineProfileV1")
        if self.test_only is not True:
            raise DockingPipelineError(
                "standalone execution remains test-only until external admission"
            )
        object.__setattr__(self, "_request_sha256", _sha256(self._projection()))

    def _projection(self) -> dict[str, object]:
        return {
            "schema_id": PIPELINE_REQUEST_SCHEMA_ID,
            "receptor_system_sha256": canonical_system_sha256(self.receptor_system),
            "ligand_system_sha256": canonical_system_sha256(self.ligand_system),
            "pocket_fingerprint_sha256": self.pocket.fingerprint_sha256,
            "seed": self.seed,
            "profile_receipt_sha256": self.profile.receipt_sha256,
            "test_only": True,
            "external_reservation_requested": False,
            "molecular_experiment_authorized": False,
        }

    @property
    def request_sha256(self) -> str:
        observed = _sha256(self._projection())
        if observed != self._request_sha256:
            raise DockingPipelineError("pipeline request changed")
        return observed

    def to_dict(self) -> dict[str, object]:
        return {**self._projection(), "request_sha256": self.request_sha256}


@dataclass(frozen=True, slots=True)
class PreparedDockingInputsV1:
    receptor_system: AllAtomSystem = field(repr=False, compare=False)
    ligand_system: AllAtomSystem = field(repr=False, compare=False)
    pocket: PocketDefinition = field(repr=False, compare=False)
    request_sha256: str
    receipt_sha256: str


@dataclass(frozen=True, slots=True)
class ProposalGenerationPlanV1:
    context: GuidedPlacementContext = field(repr=False, compare=False)
    policy: GuidedPlacementPolicy = field(repr=False, compare=False)
    v3_proposal_indices: tuple[int, ...]
    receipt_sha256: str


@runtime_checkable
class InputPreparer(Protocol):
    component_id: str

    def prepare(self, request: DockingPipelineRequestV1) -> PreparedDockingInputsV1:
        ...


@runtime_checkable
class ConformerProvider(Protocol):
    component_id: str

    def bind(self, inputs: PreparedDockingInputsV1) -> str:
        ...


@runtime_checkable
class ProposalGenerator(Protocol):
    component_id: str

    def plan(
        self,
        authority: AuthenticatedDockingProblem,
        inputs: PreparedDockingInputsV1,
        budget: DockingBudget,
    ) -> ProposalGenerationPlanV1:
        ...


@runtime_checkable
class GeometricAdmission(Protocol):
    component_id: str

    def statuses(self, candidate_count: int) -> tuple[str, ...]:
        ...


@runtime_checkable
class ScorerProvider(Protocol):
    component_id: str

    def build(
        self,
        authority: AuthenticatedDockingProblem,
        inputs: PreparedDockingInputsV1,
        implementation_source_sha256: str,
    ) -> ChemistryPoseScorerV1:
        ...


@runtime_checkable
class RefinerProvider(Protocol):
    component_id: str

    def build(
        self,
        authority: AuthenticatedDockingProblem,
        inputs: PreparedDockingInputsV1,
        plan: ProposalGenerationPlanV1,
        implementation_source_sha256: str,
    ) -> InteractionAwareTorsionContactEnsembleRefinerV7:
        ...


@runtime_checkable
class ValidityEvaluator(Protocol):
    component_id: str

    def verify(self, result: ScorerV1GuidedSearchResult) -> None:
        ...


@runtime_checkable
class Ranker(Protocol):
    component_id: str

    def verify(
        self,
        result: ScorerV1GuidedSearchResult,
        profile: DockingPipelineProfileV1,
    ) -> tuple[int, ...]:
        ...


@runtime_checkable
class EvidenceRecorder(Protocol):
    component_id: str

    def record(
        self,
        *,
        request: DockingPipelineRequestV1,
        pipeline_source_sha256: str,
        scorer_source_sha256: str,
        refiner_source_sha256: str,
        prepared_input_receipt_sha256: str,
        conformer_receipt_sha256: str,
        authority_input_receipt_sha256: str,
        proposal_plan_receipt_sha256: str,
        result: ScorerV1GuidedSearchResult,
        refiner: InteractionAwareTorsionContactEnsembleRefinerV7,
        admission_statuses: tuple[str, ...],
        top_proposal_indices: tuple[int, ...],
        component_ids: Mapping[str, str],
    ) -> "DockingPipelineResultV1":
        ...


class CanonicalPreparedInputPreparer:
    component_id = "betelgeuze.engine_v2_canonical_prepared_input/1.0.0"

    def prepare(self, request: DockingPipelineRequestV1) -> PreparedDockingInputsV1:
        for role, system in (
            ("receptor", request.receptor_system),
            ("ligand", request.ligand_system),
        ):
            require_valid_all_atom_system(system)
            if (
                system.coordinates.device.type != "cpu"
                or system.coordinates.dtype != torch.float64
            ):
                raise DockingPipelineError(
                    f"prepared {role} must use CPU float64 coordinates"
                )
            if any(atom.partial_charge_e is None for atom in system.atoms):
                raise DockingPipelineError(
                    f"prepared {role} lacks explicit partial charges"
                )
        projection = {
            "component_id": self.component_id,
            "request_sha256": request.request_sha256,
            "receptor_system_sha256": canonical_system_sha256(
                request.receptor_system
            ),
            "ligand_system_sha256": canonical_system_sha256(request.ligand_system),
            "pocket_fingerprint_sha256": request.pocket.fingerprint_sha256,
            "chemistry_inference_performed": False,
            "pocket_prediction_performed": False,
        }
        return PreparedDockingInputsV1(
            receptor_system=request.receptor_system,
            ligand_system=request.ligand_system,
            pocket=request.pocket,
            request_sha256=request.request_sha256,
            receipt_sha256=_sha256(projection),
        )


class RetainedSourceConformerProvider:
    component_id = "betelgeuze.engine_v2_retained_source_conformer/1.0.0"

    def bind(self, inputs: PreparedDockingInputsV1) -> str:
        return _sha256(
            {
                "component_id": self.component_id,
                "ligand_system_sha256": canonical_system_sha256(
                    inputs.ligand_system
                ),
                "new_conformer_generated": False,
            }
        )


class CurrentV7ProposalGenerator:
    component_id = "betelgeuze.engine_v2_current_uniform_v3_proposals/1.0.0"

    def plan(
        self,
        authority: AuthenticatedDockingProblem,
        inputs: PreparedDockingInputsV1,
        budget: DockingBudget,
    ) -> ProposalGenerationPlanV1:
        context = build_guided_placement_context(
            authority,
            inputs.receptor_system,
            inputs.ligand_system,
        )
        policy = GuidedPlacementPolicy(uniform_v3_ensemble_enabled=True)
        indices = uniform_v3_ensemble_proposal_indices(context, budget, policy)
        receipt = _sha256(
            {
                "component_id": self.component_id,
                "authority_input_receipt_sha256": authority.input_receipt_sha256,
                "context_fingerprint_sha256": context.fingerprint_sha256,
                "policy_fingerprint_sha256": policy.fingerprint_sha256,
                "v3_proposal_indices": list(indices),
            }
        )
        return ProposalGenerationPlanV1(context, policy, indices, receipt)


class PassThroughGeometricAdmission:
    component_id = "betelgeuze.engine_v2_pass_through_geometric_admission/1.0.0"

    def statuses(self, candidate_count: int) -> tuple[str, ...]:
        if type(candidate_count) is not int or not 1 <= candidate_count <= 64:
            raise DockingPipelineError("geometric admission denominator is invalid")
        return ("not_enabled_in_current_v7_baseline",) * candidate_count


class CurrentScorerV1Provider:
    component_id = "betelgeuze.engine_v2_current_scorer_v1_provider/1.0.0"

    def build(
        self,
        authority: AuthenticatedDockingProblem,
        inputs: PreparedDockingInputsV1,
        implementation_source_sha256: str,
    ) -> ChemistryPoseScorerV1:
        return ChemistryPoseScorerV1(
            authority,
            inputs.receptor_system,
            inputs.ligand_system,
            implementation_source_sha256=implementation_source_sha256,
            backend=ScorerBackend.PYTHON_REFERENCE,
            backend_options=ScorerBackendOptions(thread_count=1),
        )


class CurrentV7RefinerProvider:
    component_id = "betelgeuze.engine_v2_current_v7_refiner_provider/1.0.0"

    def build(
        self,
        authority: AuthenticatedDockingProblem,
        inputs: PreparedDockingInputsV1,
        plan: ProposalGenerationPlanV1,
        implementation_source_sha256: str,
    ) -> InteractionAwareTorsionContactEnsembleRefinerV7:
        return InteractionAwareTorsionContactEnsembleRefinerV7(
            authority,
            inputs.receptor_system,
            inputs.ligand_system,
            implementation_source_sha256=implementation_source_sha256,
            v3_proposal_indices=plan.v3_proposal_indices,
        )


class EmbeddedElementAwareValidityEvaluator:
    component_id = "betelgeuze.engine_v2_embedded_element_validity/1.0.0"

    def verify(self, result: ScorerV1GuidedSearchResult) -> None:
        search = result.guided_search_result.authenticated_search_result.search_result
        for row in search.rows:
            if row.succeeded and (
                row.pose_validity is None or not row.pose_validity.complete
            ):
                raise DockingPipelineError(
                    "successful pipeline row lacks complete validity evidence"
                )


class EmbeddedStableScoreRanker:
    component_id = "betelgeuze.engine_v2_embedded_stable_score_ranker/1.0.0"

    def verify(
        self,
        result: ScorerV1GuidedSearchResult,
        profile: DockingPipelineProfileV1,
    ) -> tuple[int, ...]:
        search = result.guided_search_result.authenticated_search_result.search_result
        indices = tuple(row.proposal_index for row in search.top_rows)
        if len(indices) > profile.top_k or len(indices) != len(set(indices)):
            raise DockingPipelineError("pipeline Top-K evidence is invalid")
        if any(not row.selection_eligible for row in search.top_rows):
            raise DockingPipelineError("pipeline Top-K contains an ineligible pose")
        return indices


@dataclass(frozen=True, slots=True)
class CandidateEvidenceV1:
    candidate_id: str
    proposal_index: int
    status: str
    geometric_admission_status: str
    search_row_sha256: str
    source_proposal_fingerprint_sha256: str
    result_proposal_fingerprint_sha256: str
    score_binary64_hex: str | None
    selection_eligible: bool
    pose_validity: Mapping[str, object] | None
    scorer_terms: Mapping[str, object] | None
    refinement_receipt: Mapping[str, object] | None
    error_code: str

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_id": PIPELINE_CANDIDATE_SCHEMA_ID,
            "candidate_id": self.candidate_id,
            "proposal_index": self.proposal_index,
            "status": self.status,
            "geometric_admission_status": self.geometric_admission_status,
            "candidate_removed_from_denominator": False,
            "search_row_sha256": self.search_row_sha256,
            "source_proposal_fingerprint_sha256": (
                self.source_proposal_fingerprint_sha256
            ),
            "result_proposal_fingerprint_sha256": (
                self.result_proposal_fingerprint_sha256
            ),
            "score_binary64_hex": self.score_binary64_hex,
            "selection_eligible": self.selection_eligible,
            "pose_validity": None
            if self.pose_validity is None
            else dict(self.pose_validity),
            "scorer_terms": None
            if self.scorer_terms is None
            else dict(self.scorer_terms),
            "refinement_receipt": None
            if self.refinement_receipt is None
            else dict(self.refinement_receipt),
            "error_code": self.error_code,
            "baseline_disagreement": "not_evaluated",
            "claim_safe": False,
        }


@dataclass(frozen=True, slots=True)
class DockingPipelineResultV1:
    request: DockingPipelineRequestV1 = field(repr=False, compare=False)
    pipeline_source_sha256: str
    scorer_source_sha256: str
    refiner_source_sha256: str
    prepared_input_receipt_sha256: str
    conformer_receipt_sha256: str
    authority_input_receipt_sha256: str
    proposal_plan_receipt_sha256: str
    scorer_v1_result_receipt_sha256: str
    candidates: tuple[CandidateEvidenceV1, ...]
    top_proposal_indices: tuple[int, ...]
    component_ids: Mapping[str, str]
    blockers: tuple[str, ...]
    _receipt_sha256: str = field(init=False, repr=False)

    def __post_init__(self) -> None:
        source = _digest(self.pipeline_source_sha256, name="pipeline_source_sha256")
        scorer_source = _digest(
            self.scorer_source_sha256,
            name="scorer_source_sha256",
        )
        refiner_source = _digest(
            self.refiner_source_sha256,
            name="refiner_source_sha256",
        )
        prepared_input = _digest(
            self.prepared_input_receipt_sha256,
            name="prepared_input_receipt_sha256",
        )
        conformer = _digest(
            self.conformer_receipt_sha256,
            name="conformer_receipt_sha256",
        )
        authority = _digest(
            self.authority_input_receipt_sha256,
            name="authority_input_receipt_sha256",
        )
        proposal = _digest(
            self.proposal_plan_receipt_sha256,
            name="proposal_plan_receipt_sha256",
        )
        scorer = _digest(
            self.scorer_v1_result_receipt_sha256,
            name="scorer_v1_result_receipt_sha256",
        )
        candidates = tuple(self.candidates)
        if len(candidates) != self.request.profile.candidate_count:
            raise DockingPipelineError("pipeline candidate denominator changed")
        if tuple(row.proposal_index for row in candidates) != tuple(
            range(len(candidates))
        ):
            raise DockingPipelineError("pipeline candidate order is not index-stable")
        blockers = tuple(dict.fromkeys(str(value) for value in self.blockers))
        if any(value not in blockers for value in EXTERNAL_AUTHORITY_BLOCKERS):
            raise DockingPipelineError("pipeline result lost an external blocker")
        object.__setattr__(self, "pipeline_source_sha256", source)
        object.__setattr__(self, "scorer_source_sha256", scorer_source)
        object.__setattr__(self, "refiner_source_sha256", refiner_source)
        object.__setattr__(self, "prepared_input_receipt_sha256", prepared_input)
        object.__setattr__(self, "conformer_receipt_sha256", conformer)
        object.__setattr__(self, "authority_input_receipt_sha256", authority)
        object.__setattr__(self, "proposal_plan_receipt_sha256", proposal)
        object.__setattr__(self, "scorer_v1_result_receipt_sha256", scorer)
        object.__setattr__(self, "candidates", candidates)
        object.__setattr__(self, "component_ids", dict(self.component_ids))
        object.__setattr__(self, "blockers", blockers)
        object.__setattr__(self, "_receipt_sha256", _sha256(self._projection()))

    @property
    def success_count(self) -> int:
        return sum(row.status == "success" for row in self.candidates)

    @property
    def failure_count(self) -> int:
        return len(self.candidates) - self.success_count

    @property
    def abstained(self) -> bool:
        return len(self.top_proposal_indices) < self.request.profile.top_k

    def _projection(self) -> dict[str, object]:
        return {
            "schema_id": PIPELINE_RESULT_SCHEMA_ID,
            "request_sha256": self.request.request_sha256,
            "profile_receipt_sha256": self.request.profile.receipt_sha256,
            "pipeline_source_sha256": self.pipeline_source_sha256,
            "scorer_source_sha256": self.scorer_source_sha256,
            "refiner_source_sha256": self.refiner_source_sha256,
            "prepared_input_receipt_sha256": self.prepared_input_receipt_sha256,
            "conformer_receipt_sha256": self.conformer_receipt_sha256,
            "authority_input_receipt_sha256": self.authority_input_receipt_sha256,
            "proposal_plan_receipt_sha256": self.proposal_plan_receipt_sha256,
            "pipeline_source_binding_mode": (
                "observed_installed_package_resource_after_import_not_preimport_attested"
            ),
            "scorer_v1_result_receipt_sha256": (
                self.scorer_v1_result_receipt_sha256
            ),
            "candidate_count": len(self.candidates),
            "success_count": self.success_count,
            "failure_count": self.failure_count,
            "top_proposal_indices": list(self.top_proposal_indices),
            "abstained": self.abstained,
            "component_ids": dict(sorted(self.component_ids.items())),
            "candidate_evidence": [row.to_dict() for row in self.candidates],
            "blockers": list(self.blockers),
            "failure_denominator_preserved": True,
            "chemistry_inference_performed": False,
            "pocket_prediction_performed": False,
            "network_fetch_performed": False,
            "external_reservation_requested": False,
            "test_only": True,
            "historical_execution_authorized": False,
            "fresh_holdout_execution_authorized": False,
            "stage0_admission_authority": False,
            "product_execution_authorized": False,
            "customer_pose_emission_authorized": False,
            "public_or_scientific_claim_authorized": False,
            "claim_safe": False,
        }

    @property
    def receipt_sha256(self) -> str:
        observed = _sha256(self._projection())
        if observed != self._receipt_sha256:
            raise DockingPipelineError("pipeline result changed")
        return observed

    def to_dict(self) -> dict[str, object]:
        return {
            **self._projection(),
            "request": self.request.to_dict(),
            "profile": self.request.profile.to_dict(),
            "receipt_sha256": self.receipt_sha256,
        }


class CanonicalPipelineEvidenceRecorder:
    component_id = "betelgeuze.engine_v2_canonical_pipeline_evidence/1.0.0"

    def record(
        self,
        *,
        request: DockingPipelineRequestV1,
        pipeline_source_sha256: str,
        scorer_source_sha256: str,
        refiner_source_sha256: str,
        prepared_input_receipt_sha256: str,
        conformer_receipt_sha256: str,
        authority_input_receipt_sha256: str,
        proposal_plan_receipt_sha256: str,
        result: ScorerV1GuidedSearchResult,
        refiner: InteractionAwareTorsionContactEnsembleRefinerV7,
        admission_statuses: tuple[str, ...],
        top_proposal_indices: tuple[int, ...],
        component_ids: Mapping[str, str],
    ) -> DockingPipelineResultV1:
        search = result.guided_search_result.authenticated_search_result.search_result
        terms_by_index = {row.proposal_index: row.terms for row in result.rows}
        receipts = refiner.receipts
        candidates: list[CandidateEvidenceV1] = []
        for row, admission in zip(search.rows, admission_statuses, strict=True):
            terms = terms_by_index.get(row.proposal_index)
            refinement = receipts.get(row.proposal_fingerprint_sha256)
            if row.succeeded and (
                not isinstance(terms, ScorerV1Terms) or refinement is None
            ):
                raise DockingPipelineError(
                    "successful pipeline row lacks scorer/refinement evidence"
                )
            candidates.append(
                CandidateEvidenceV1(
                    candidate_id=row.candidate_id,
                    proposal_index=row.proposal_index,
                    status=row.status,
                    geometric_admission_status=admission,
                    search_row_sha256=_sha256(row.to_dict()),
                    source_proposal_fingerprint_sha256=(
                        row.proposal_fingerprint_sha256
                    ),
                    result_proposal_fingerprint_sha256=(
                        row.result_proposal_fingerprint_sha256
                    ),
                    score_binary64_hex=None
                    if row.score is None
                    else float(row.score).hex(),
                    selection_eligible=bool(row.selection_eligible),
                    pose_validity=None
                    if row.pose_validity is None
                    else row.pose_validity.to_dict(),
                    scorer_terms=None if terms is None else terms.to_dict(),
                    refinement_receipt=None
                    if refinement is None
                    else dict(refinement),
                    error_code=row.error_code,
                )
            )
        return DockingPipelineResultV1(
            request=request,
            pipeline_source_sha256=pipeline_source_sha256,
            scorer_source_sha256=scorer_source_sha256,
            refiner_source_sha256=refiner_source_sha256,
            prepared_input_receipt_sha256=prepared_input_receipt_sha256,
            conformer_receipt_sha256=conformer_receipt_sha256,
            authority_input_receipt_sha256=authority_input_receipt_sha256,
            proposal_plan_receipt_sha256=proposal_plan_receipt_sha256,
            scorer_v1_result_receipt_sha256=result.receipt_sha256,
            candidates=tuple(candidates),
            top_proposal_indices=top_proposal_indices,
            component_ids=component_ids,
            blockers=PIPELINE_CLAIM_BLOCKERS,
        )


class DockingPipeline:
    """Compose the current CPU baseline behind one dependency-injected core."""

    def __init__(
        self,
        input_preparer: InputPreparer | None = None,
        conformer_provider: ConformerProvider | None = None,
        proposal_generator: ProposalGenerator | None = None,
        geometric_admission: GeometricAdmission | None = None,
        scorer: ScorerProvider | None = None,
        refiner: RefinerProvider | None = None,
        validity_evaluator: ValidityEvaluator | None = None,
        ranker: Ranker | None = None,
        evidence_recorder: EvidenceRecorder | None = None,
    ) -> None:
        self.input_preparer = input_preparer or CanonicalPreparedInputPreparer()
        self.conformer_provider = conformer_provider or RetainedSourceConformerProvider()
        self.proposal_generator = proposal_generator or CurrentV7ProposalGenerator()
        self.geometric_admission = geometric_admission or PassThroughGeometricAdmission()
        self.scorer = scorer or CurrentScorerV1Provider()
        self.refiner = refiner or CurrentV7RefinerProvider()
        self.validity_evaluator = (
            validity_evaluator or EmbeddedElementAwareValidityEvaluator()
        )
        self.ranker = ranker or EmbeddedStableScoreRanker()
        self.evidence_recorder = evidence_recorder or CanonicalPipelineEvidenceRecorder()
        expected = (
            (self.input_preparer, InputPreparer, "input_preparer"),
            (self.conformer_provider, ConformerProvider, "conformer_provider"),
            (self.proposal_generator, ProposalGenerator, "proposal_generator"),
            (self.geometric_admission, GeometricAdmission, "geometric_admission"),
            (self.scorer, ScorerProvider, "scorer"),
            (self.refiner, RefinerProvider, "refiner"),
            (self.validity_evaluator, ValidityEvaluator, "validity_evaluator"),
            (self.ranker, Ranker, "ranker"),
            (self.evidence_recorder, EvidenceRecorder, "evidence_recorder"),
        )
        for value, protocol, name in expected:
            if not isinstance(value, protocol):
                raise TypeError(f"{name} does not satisfy the pipeline protocol")

    @property
    def component_ids(self) -> dict[str, str]:
        return {
            "input_preparer": self.input_preparer.component_id,
            "conformer_provider": self.conformer_provider.component_id,
            "proposal_generator": self.proposal_generator.component_id,
            "geometric_admission": self.geometric_admission.component_id,
            "scorer": self.scorer.component_id,
            "refiner": self.refiner.component_id,
            "validity_evaluator": self.validity_evaluator.component_id,
            "ranker": self.ranker.component_id,
            "evidence_recorder": self.evidence_recorder.component_id,
        }

    def run(self, request: DockingPipelineRequestV1) -> DockingPipelineResultV1:
        if type(request) is not DockingPipelineRequestV1:
            raise TypeError("request must be exact DockingPipelineRequestV1")
        inputs = self.input_preparer.prepare(request)
        conformer_receipt_sha256 = self.conformer_provider.bind(inputs)
        authority = build_element_aware_authenticated_known_pocket_docking_problem(
            inputs.receptor_system,
            inputs.ligand_system,
            inputs.pocket,
            receptor_margin_angstrom=request.profile.receptor_margin_angstrom,
        )
        budget = DockingBudget(
            candidate_count=request.profile.candidate_count,
            top_k=request.profile.top_k,
            max_torsions=request.profile.max_torsions,
            max_refinement_steps=request.profile.max_refinement_steps,
            translation_radius_angstrom=min(
                request.profile.translation_radius_angstrom,
                inputs.pocket.radius_angstrom,
            ),
            seed=request.seed,
        )
        plan = self.proposal_generator.plan(authority, inputs, budget)
        pipeline_source_sha256 = observed_pipeline_source_sha256()
        scorer_source_sha256 = _observed_docking_source_sha256("scorer_v1.py")
        refiner_source_sha256 = _observed_docking_source_sha256(
            "torsion_contact_refinement.py"
        )
        scorer = self.scorer.build(authority, inputs, scorer_source_sha256)
        refiner = self.refiner.build(
            authority,
            inputs,
            plan,
            refiner_source_sha256,
        )
        admission_statuses = self.geometric_admission.statuses(
            request.profile.candidate_count
        )
        result = run_authenticated_scorer_v1_guided_search(
            authority,
            budget,
            scorer,
            plan.context,
            receptor_system=inputs.receptor_system,
            ligand_system=inputs.ligand_system,
            refiner=refiner,
            guided_policy=plan.policy,
            diversity_rmsd_angstrom=0.0,
        )
        if len(result.rows) != request.profile.candidate_count:
            raise DockingPipelineError("pipeline search changed the denominator")
        self.validity_evaluator.verify(result)
        top_indices = self.ranker.verify(result, request.profile)
        return self.evidence_recorder.record(
            request=request,
            pipeline_source_sha256=pipeline_source_sha256,
            scorer_source_sha256=scorer_source_sha256,
            refiner_source_sha256=refiner_source_sha256,
            prepared_input_receipt_sha256=inputs.receipt_sha256,
            conformer_receipt_sha256=conformer_receipt_sha256,
            authority_input_receipt_sha256=authority.input_receipt_sha256,
            proposal_plan_receipt_sha256=plan.receipt_sha256,
            result=result,
            refiner=refiner,
            admission_statuses=admission_statuses,
            top_proposal_indices=top_indices,
            component_ids=self.component_ids,
        )


__all__ = [
    "CURRENT_V7_FIXED64_PROFILE_ID",
    "EXTERNAL_AUTHORITY_BLOCKERS",
    "PIPELINE_CANDIDATE_SCHEMA_ID",
    "PIPELINE_PROFILE_SCHEMA_ID",
    "PIPELINE_REQUEST_SCHEMA_ID",
    "PIPELINE_RESULT_SCHEMA_ID",
    "SYNTHETIC_TEST_PROFILE_ID",
    "CandidateEvidenceV1",
    "CanonicalPipelineEvidenceRecorder",
    "CanonicalPreparedInputPreparer",
    "ConformerProvider",
    "CurrentScorerV1Provider",
    "CurrentV7ProposalGenerator",
    "CurrentV7RefinerProvider",
    "DockingPipeline",
    "DockingPipelineError",
    "DockingPipelineProfileV1",
    "DockingPipelineRequestV1",
    "DockingPipelineResultV1",
    "EmbeddedElementAwareValidityEvaluator",
    "EmbeddedStableScoreRanker",
    "EvidenceRecorder",
    "GeometricAdmission",
    "InputPreparer",
    "PassThroughGeometricAdmission",
    "ProposalGenerator",
    "Ranker",
    "RefinerProvider",
    "RetainedSourceConformerProvider",
    "ScorerProvider",
    "ValidityEvaluator",
    "observed_pipeline_source_sha256",
]

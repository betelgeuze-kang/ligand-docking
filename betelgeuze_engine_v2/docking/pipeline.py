"""One claim-blocked CPU docking core shared by future product surfaces.

The pipeline composes the current V7/Scorer-v1 baseline from canonical,
already-prepared molecular systems.  It deliberately performs no parsing,
protonation, tautomer selection, atom typing, partial-charge generation,
pocket prediction, external reservation, or product action.
"""

from __future__ import annotations

from collections.abc import Mapping as MappingABC
from dataclasses import InitVar, dataclass, field
import hashlib
import hmac
from importlib import resources
import json
import math
import secrets
import threading
from types import MappingProxyType
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
    INTERACTION_AWARE_TORSION_CONTACT_RECEIPT_V7_SCHEMA_ID,
    InteractionAwareTorsionContactEnsembleRefinerV7,
)


PIPELINE_REQUEST_SCHEMA_ID = "betelgeuze.engine_v2_docking_pipeline_request/1.0.0"
PIPELINE_PROFILE_SCHEMA_ID = "betelgeuze.engine_v2_docking_pipeline_profile/1.0.0"
PIPELINE_CANDIDATE_SCHEMA_ID = "betelgeuze.engine_v2_docking_pipeline_candidate/1.0.0"
PIPELINE_RESULT_SCHEMA_ID = "betelgeuze.engine_v2_docking_pipeline_result/1.0.0"
PIPELINE_PROPOSAL_PLAN_SCHEMA_ID = (
    "betelgeuze.engine_v2_docking_pipeline_proposal_plan/1.0.0"
)
SYNTHETIC_D0_FIXTURE_ADMISSION_SCHEMA_ID = (
    "betelgeuze.engine_v2_synthetic_d0_fixture_admission/1.0.0"
)
SYNTHETIC_D0_FIXTURE_ADMISSION_RECEIPT_SCHEMA_ID = (
    "betelgeuze.engine_v2_synthetic_d0_fixture_admission_receipt/1.0.0"
)
CURRENT_V7_FIXED64_PROFILE_ID = (
    "betelgeuze.engine_v2_cpu_current_v7_scorer_v1_fixed64/1.0.0"
)
SYNTHETIC_TEST_PROFILE_ID = (
    "betelgeuze.engine_v2_cpu_synthetic_test_profile/1.0.0"
)
SYNTHETIC_ONLY_ACKNOWLEDGMENT = (
    "synthetic-fixture-only:no-reservation:no-molecular-experiment:"
    "no-product-action:no-public-or-scientific-claim"
)
SYNTHETIC_D0_FIXTURE_MANIFEST_RESOURCE = (
    "synthetic_d0_fixture_admission.json"
)
SYNTHETIC_D0_FIXTURE_MANIFEST_SHA256 = (
    "12919355ac208aaa11d9560ebc95db05a30a5d4379bf741f89e81482d131693b"
)
SYNTHETIC_D0_FIXTURE_REQUEST_SHA256 = (
    "bbf826bbdc30818f27c95f04763696bd09b7aa3e9cbd75c5d1597442d8129629"
)
SYNTHETIC_D0_FIXTURE_ID = (
    "betelgeuze.engine_v2.synthetic_d0_standalone_fixture/1.0.0"
)
SEALED_CANONICAL_COMPONENT_BINDING = "sealed_canonical_components"
UNVERIFIED_COMPONENT_BINDING = "internal_test_only_unverified_components"
UNVERIFIED_COMPONENT_BLOCKER = "arbitrary_dependency_injection_unverified"
UNVERIFIED_SIDE_EFFECT_BLOCKER = "unverified_component_side_effects_unknown"
SYNTHETIC_D0_FIXTURE_ONLY_BLOCKER = (
    "repository_synthetic_d0_fixture_only"
)
_INTERNAL_UNVERIFIED_EXECUTION_LATCH = object()
_PIPELINE_RECEIPT_FACTORY_SEAL = object()
_PIPELINE_RECORD_CAPABILITY_ISSUER = object()
_PIPELINE_CONSTRUCTION_PROOF_KEY = secrets.token_bytes(32)
_UNVERIFIED_COMPONENT_ID = "UNVERIFIED"
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
    SYNTHETIC_D0_FIXTURE_ONLY_BLOCKER,
    "public_or_scientific_claim_authority_false",
)
_PIPELINE_COMPONENT_ROLES = (
    "input_preparer",
    "conformer_provider",
    "proposal_generator",
    "geometric_admission",
    "scorer",
    "refiner",
    "validity_evaluator",
    "ranker",
    "evidence_recorder",
)
_AUTHORITY_FALSE_FIELDS = (
    "customer_pose_emission_allowed",
    "existing_rank_auto_change_allowed",
    "external_reservation_allowed",
    "fresh_holdout_execution_allowed",
    "historical_execution_allowed",
    "molecular_experiment_authorized",
    "product_mutation_allowed",
    "production_claim_allowed",
    "public_benchmark_execution_allowed",
)


class DockingPipelineError(RuntimeError):
    """The standalone CPU pipeline failed closed."""


def _normalize_json(
    value: object,
    *,
    path: str = "$",
    active_containers: set[int] | None = None,
) -> object:
    active = set() if active_containers is None else active_containers
    if isinstance(value, MappingABC):
        identity = id(value)
        if identity in active:
            raise DockingPipelineError(f"{path} contains a container cycle")
        active.add(identity)
        try:
            normalized: dict[str, object] = {}
            for key, item in value.items():
                if type(key) is not str or not key:
                    raise DockingPipelineError(
                        f"{path} mapping keys must be non-empty strings"
                    )
                if key in normalized:
                    raise DockingPipelineError(f"{path} contains a duplicate key")
                normalized[key] = _normalize_json(
                    item,
                    path=f"{path}.{key}",
                    active_containers=active,
                )
            return normalized
        finally:
            active.remove(identity)
    if isinstance(value, (list, tuple)):
        identity = id(value)
        if identity in active:
            raise DockingPipelineError(f"{path} contains a container cycle")
        active.add(identity)
        try:
            return [
                _normalize_json(
                    item,
                    path=f"{path}[{index}]",
                    active_containers=active,
                )
                for index, item in enumerate(value)
            ]
        finally:
            active.remove(identity)
    if value is None or type(value) in {str, bool, int}:
        return value
    if type(value) is float:
        if not math.isfinite(value):
            raise DockingPipelineError(f"{path} contains a non-finite float")
        return value
    raise DockingPipelineError(f"{path} contains a non-canonical JSON value")


def _freeze_json(value: object) -> object:
    if isinstance(value, dict):
        return MappingProxyType(
            {key: _freeze_json(item) for key, item in value.items()}
        )
    if isinstance(value, list):
        return tuple(_freeze_json(item) for item in value)
    return value


def _thaw_json(value: object) -> object:
    if isinstance(value, MappingABC):
        return {str(key): _thaw_json(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw_json(item) for item in value]
    return value


def _canonical_mapping(value: object, *, name: str) -> Mapping[str, object]:
    if not isinstance(value, MappingABC):
        raise DockingPipelineError(f"{name} must be a canonical JSON mapping")
    normalized = _normalize_json(value, path=name)
    if not isinstance(normalized, dict):  # pragma: no cover - type narrowing
        raise DockingPipelineError(f"{name} must be a canonical JSON mapping")
    return MappingProxyType(
        {key: _freeze_json(item) for key, item in normalized.items()}
    )


def _canonical_bytes(value: object) -> bytes:
    try:
        return json.dumps(
            _normalize_json(value),
            allow_nan=False,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("ascii")
    except (TypeError, ValueError) as exc:
        raise DockingPipelineError("pipeline evidence is not canonical JSON") from exc


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _construction_proof_sha256(value: object) -> str:
    return hmac.new(
        _PIPELINE_CONSTRUCTION_PROOF_KEY,
        _canonical_bytes(value),
        hashlib.sha256,
    ).hexdigest()


def _digest(value: object, *, name: str) -> str:
    if (
        type(value) is not str
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise DockingPipelineError(f"{name} must be an exact lowercase SHA-256")
    return value


def _reject_duplicate_json_pairs(
    pairs: list[tuple[str, object]],
) -> dict[str, object]:
    document: dict[str, object] = {}
    for key, value in pairs:
        if key in document:
            raise DockingPipelineError(
                "synthetic D0 fixture manifest contains duplicate keys"
            )
        document[key] = value
    return document


def _canonical_float_hex(value: object, *, name: str) -> str:
    if type(value) is not str:
        raise DockingPipelineError(f"{name} must be canonical binary64 hex")
    try:
        number = float.fromhex(value)
    except ValueError as exc:
        raise DockingPipelineError(f"{name} must be canonical binary64 hex") from exc
    if not math.isfinite(number) or number.hex() != value:
        raise DockingPipelineError(f"{name} must be canonical binary64 hex")
    return value


def _embedded_receipt_sha256(
    value: Mapping[str, object],
    *,
    name: str,
) -> str:
    document = _thaw_json(value)
    if not isinstance(document, dict):  # pragma: no cover - type narrowing
        raise DockingPipelineError(f"{name} must be a canonical receipt")
    observed = _digest(document.pop("receipt_sha256", ""), name=f"{name} receipt")
    if _sha256(document) != observed:
        raise DockingPipelineError(f"{name} receipt does not rederive")
    return observed


_SCORER_V1_FLOAT_TERM_NAMES = (
    "typed_vdw",
    "electrostatics",
    "directional_hbond",
    "hydrophobic_contact",
    "desolvation_proxy",
    "torsion_energy",
    "ligand_strain",
    "weak_pocket_prior",
    "total_score",
)
_SCORER_V1_COUNT_NAMES = (
    "receptor_candidate_pair_count",
    "ligand_pair_count",
    "hbond_count",
    "hydrophobic_contact_count",
    "buried_polar_count",
)
_REQUIRED_POSE_VALIDITY_CHECKS = {
    "proper_rotation",
    "bond_lengths_preserved",
    "ligand_self_clash_free",
    "receptor_ligand_clash_free",
    "declared_chirality_preserved",
    "inside_declared_pocket",
    "element_vdw_ligand_overlap_free",
    "element_vdw_receptor_overlap_free",
}


def _canonical_scorer_terms(
    value: object,
) -> Mapping[str, object]:
    frozen = _canonical_mapping(value, name="candidate scorer terms")
    document = _thaw_json(frozen)
    if not isinstance(document, dict):  # pragma: no cover - type narrowing
        raise DockingPipelineError("candidate scorer terms are invalid")
    expected_keys = {
        "schema_id",
        "score_id",
        "proposal_fingerprint_sha256",
        "authority_input_receipt_sha256",
        "context_fingerprint_sha256",
        "config_fingerprint_sha256",
        "backend_receipt_sha256",
        *(f"{name}_binary64_hex" for name in _SCORER_V1_FLOAT_TERM_NAMES),
        *_SCORER_V1_COUNT_NAMES,
        "calibrated",
        "scientifically_validated",
        "claim_safe",
        "receipt_sha256",
    }
    if set(document) != expected_keys or any(
        document.get(name) is not False
        for name in ("calibrated", "scientifically_validated", "claim_safe")
    ):
        raise DockingPipelineError("candidate ScorerV1Terms receipt is incomplete")
    for name in _SCORER_V1_COUNT_NAMES:
        if type(document[name]) is not int or document[name] < 0:
            raise DockingPipelineError("candidate ScorerV1Terms count is invalid")
    try:
        canonical = ScorerV1Terms(
            proposal_fingerprint_sha256=document[
                "proposal_fingerprint_sha256"
            ],
            authority_input_receipt_sha256=document[
                "authority_input_receipt_sha256"
            ],
            context_fingerprint_sha256=document["context_fingerprint_sha256"],
            config_fingerprint_sha256=document["config_fingerprint_sha256"],
            backend_receipt_sha256=document["backend_receipt_sha256"],
            **{
                name: float.fromhex(
                    _canonical_float_hex(
                        document[f"{name}_binary64_hex"],
                        name=f"ScorerV1Terms {name}",
                    )
                )
                for name in _SCORER_V1_FLOAT_TERM_NAMES
            },
            **{name: document[name] for name in _SCORER_V1_COUNT_NAMES},
        )
    except (TypeError, ValueError, RuntimeError) as exc:
        raise DockingPipelineError(
            "candidate ScorerV1Terms receipt does not independently rederive"
        ) from exc
    if canonical.to_dict() != document:
        raise DockingPipelineError(
            "candidate ScorerV1Terms receipt does not independently rederive"
        )
    return _canonical_mapping(canonical.to_dict(), name="candidate scorer terms")


def _canonical_pose_validity(value: object) -> Mapping[str, object]:
    frozen = _canonical_mapping(value, name="candidate pose validity")
    document = _thaw_json(frozen)
    if not isinstance(document, dict):  # pragma: no cover - type narrowing
        raise DockingPipelineError("candidate pose validity is invalid")
    if set(document) != {
        "valid",
        "checks",
        "evaluated_checks",
        "complete",
        "valid_within_evaluated_scope",
        "measurements",
        "blockers",
        "not_evaluated_reasons",
        "claim_safe",
    }:
        raise DockingPipelineError("candidate pose validity is incomplete")
    checks = document["checks"]
    evaluated = document["evaluated_checks"]
    measurements = document["measurements"]
    blockers = document["blockers"]
    reasons = document["not_evaluated_reasons"]
    if (
        not isinstance(checks, dict)
        or not isinstance(evaluated, dict)
        or set(checks) != _REQUIRED_POSE_VALIDITY_CHECKS
        or set(evaluated) != _REQUIRED_POSE_VALIDITY_CHECKS
        or any(type(value) is not bool for value in checks.values())
        or any(type(value) is not bool for value in evaluated.values())
        or not isinstance(measurements, dict)
        or any(
            type(value) not in {int, float}
            or (type(value) is float and not math.isfinite(value))
            for value in measurements.values()
        )
        or not isinstance(blockers, list)
        or any(
            type(value) is not str or not value or value != value.strip()
            for value in blockers
        )
        or len(blockers) != len(set(blockers))
        or not isinstance(reasons, dict)
        or any(
            type(key) is not str
            or not key
            or type(reason) is not str
            or not reason
            for key, reason in reasons.items()
        )
        or any(
            type(document[name]) is not bool
            for name in ("valid", "complete", "valid_within_evaluated_scope")
        )
        or document["claim_safe"] is not False
    ):
        raise DockingPipelineError("candidate pose validity is invalid")
    expected_complete = all(evaluated.values())
    expected_valid_within_scope = all(
        checks[name] for name, was_evaluated in evaluated.items() if was_evaluated
    )
    if (
        document["complete"] is not expected_complete
        or document["valid_within_evaluated_scope"]
        is not expected_valid_within_scope
        or document["valid"]
        is not (expected_complete and expected_valid_within_scope)
    ):
        raise DockingPipelineError("candidate pose validity is contradictory")
    return frozen


def _canonical_refinement_receipt(value: object) -> Mapping[str, object]:
    frozen = _canonical_mapping(value, name="candidate refinement receipt")
    required = {
        "schema_id",
        "source_proposal_sha256",
        "config_sha256",
        "pre_coordinates_sha256",
        "post_coordinates_sha256",
        "baseline_coordinates_sha256",
        "baseline_v6_receipt_sha256",
        "scientifically_validated",
        "receipt_sha256",
    }
    if (
        not required.issubset(frozen)
        or frozen.get("schema_id")
        != INTERACTION_AWARE_TORSION_CONTACT_RECEIPT_V7_SCHEMA_ID
        or frozen.get("scientifically_validated") is not False
    ):
        raise DockingPipelineError("candidate V7 refinement receipt is incomplete")
    for name in required & {
        "source_proposal_sha256",
        "config_sha256",
        "pre_coordinates_sha256",
        "post_coordinates_sha256",
        "baseline_coordinates_sha256",
        "baseline_v6_receipt_sha256",
    }:
        _digest(frozen[name], name=f"candidate refinement {name}")
    _embedded_receipt_sha256(frozen, name="candidate refinement")
    return frozen


def _budget_sha256(value: Mapping[str, object] | DockingBudget) -> str:
    budget = value.to_dict() if isinstance(value, DockingBudget) else _thaw_json(value)
    return _sha256(
        {
            "schema_id": "betelgeuze.engine_v2_docking_budget_identity/1.0.0",
            "budget": budget,
        }
    )


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
            "full_budget_receipt_required": True,
            "full_proposal_plan_receipt_required": True,
            "failure_denominator_required": self.candidate_count,
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
class SyntheticD0FixtureAdmissionV1:
    """Exact identity admission for one repository-owned fixed-64 fixture."""

    fixture_id: str
    manifest_sha256: str
    request_sha256: str
    receptor_system_sha256: str
    ligand_system_sha256: str
    pocket_fingerprint_sha256: str
    profile_id: str
    profile_receipt_sha256: str
    seed: int
    candidate_count: int
    top_k: int
    benchmark_scope: str
    benchmark_case_id: str
    python_api_context_id: str
    cli_context_id: str
    product_shadow_context_allowlist: tuple[str, ...]
    _factory_seal: InitVar[object | None] = None
    _receipt_sha256: str = field(init=False, repr=False)

    def __post_init__(self, _factory_seal: object | None) -> None:
        if _factory_seal is not _PIPELINE_RECEIPT_FACTORY_SEAL:
            raise DockingPipelineError(
                "synthetic D0 admission must come from the repository manifest"
            )
        if self.fixture_id != SYNTHETIC_D0_FIXTURE_ID:
            raise DockingPipelineError("synthetic D0 fixture ID is not exact")
        if (
            _digest(self.manifest_sha256, name="fixture manifest SHA-256")
            != SYNTHETIC_D0_FIXTURE_MANIFEST_SHA256
        ):
            raise DockingPipelineError("synthetic D0 manifest SHA-256 is not exact")
        if (
            _digest(self.request_sha256, name="fixture request SHA-256")
            != SYNTHETIC_D0_FIXTURE_REQUEST_SHA256
        ):
            raise DockingPipelineError("synthetic D0 request SHA-256 is not exact")
        for name in (
            "receptor_system_sha256",
            "ligand_system_sha256",
            "pocket_fingerprint_sha256",
            "profile_receipt_sha256",
        ):
            object.__setattr__(
                self,
                name,
                _digest(getattr(self, name), name=f"fixture {name}"),
            )
        if self.profile_id != CURRENT_V7_FIXED64_PROFILE_ID:
            raise DockingPipelineError("synthetic D0 profile ID is not fixed64")
        if type(self.seed) is not int or self.seed != 4301:
            raise DockingPipelineError("synthetic D0 seed is not exact")
        if type(self.candidate_count) is not int or self.candidate_count != 64:
            raise DockingPipelineError("synthetic D0 denominator is not fixed64")
        if type(self.top_k) is not int or self.top_k != 5:
            raise DockingPipelineError("synthetic D0 Top-K is not exact")
        if self.benchmark_scope != "d0_synthetic_test_fixture":
            raise DockingPipelineError("synthetic D0 benchmark scope is not exact")
        if self.benchmark_case_id != "synthetic-d0-standalone-001":
            raise DockingPipelineError("synthetic D0 benchmark case is not exact")
        if self.python_api_context_id != (
            "betelgeuze.engine_v2.synthetic_d0/python_api"
        ):
            raise DockingPipelineError("synthetic D0 Python context is not exact")
        if self.cli_context_id != "betelgeuze.engine_v2.synthetic_d0/cli":
            raise DockingPipelineError("synthetic D0 CLI context is not exact")
        allowlist = tuple(self.product_shadow_context_allowlist)
        if allowlist != (
            "betelgeuze.engine_v2.synthetic_d0/product_shadow_second_opinion",
        ):
            raise DockingPipelineError("synthetic D0 shadow context is not exact")
        object.__setattr__(self, "product_shadow_context_allowlist", allowlist)
        object.__setattr__(self, "_receipt_sha256", _sha256(self._projection()))

    def _projection(self) -> dict[str, object]:
        return {
            "schema_id": SYNTHETIC_D0_FIXTURE_ADMISSION_RECEIPT_SCHEMA_ID,
            "fixture_id": self.fixture_id,
            "manifest_sha256": self.manifest_sha256,
            "request_sha256": self.request_sha256,
            "receptor_system_sha256": self.receptor_system_sha256,
            "ligand_system_sha256": self.ligand_system_sha256,
            "pocket_fingerprint_sha256": self.pocket_fingerprint_sha256,
            "profile_id": self.profile_id,
            "profile_receipt_sha256": self.profile_receipt_sha256,
            "seed": self.seed,
            "candidate_count": self.candidate_count,
            "top_k": self.top_k,
            "benchmark_scope": self.benchmark_scope,
            "benchmark_case_id": self.benchmark_case_id,
            "python_api_context_id": self.python_api_context_id,
            "cli_context_id": self.cli_context_id,
            "product_shadow_context_allowlist": list(
                self.product_shadow_context_allowlist
            ),
            "repository_owned": True,
            "external_reservation_allowed": False,
            "historical_execution_allowed": False,
            "fresh_holdout_execution_allowed": False,
            "public_benchmark_execution_allowed": False,
            "molecular_experiment_authorized": False,
            "authority": False,
        }

    @property
    def receipt_sha256(self) -> str:
        observed = _sha256(self._projection())
        if observed != self._receipt_sha256:
            raise DockingPipelineError("synthetic D0 fixture admission changed")
        return observed

    def to_dict(self) -> dict[str, object]:
        return {**self._projection(), "receipt_sha256": self.receipt_sha256}

    def assert_request_identity(
        self,
        *,
        receptor_system_sha256: str,
        ligand_system_sha256: str,
        pocket_fingerprint_sha256: str,
        seed: int,
        profile: DockingPipelineProfileV1,
    ) -> None:
        self.receipt_sha256
        if (
            receptor_system_sha256 != self.receptor_system_sha256
            or ligand_system_sha256 != self.ligand_system_sha256
            or pocket_fingerprint_sha256 != self.pocket_fingerprint_sha256
            or seed != self.seed
            or type(profile) is not DockingPipelineProfileV1
            or profile.profile_id != self.profile_id
            or profile.receipt_sha256 != self.profile_receipt_sha256
            or profile.candidate_count != self.candidate_count
            or profile.top_k != self.top_k
        ):
            raise DockingPipelineError(
                "standalone core admits only the exact repository-owned "
                "synthetic D0 fixed64 request"
            )


def repository_synthetic_d0_fixture_admission() -> SyntheticD0FixtureAdmissionV1:
    """Load and authenticate the exact package-owned synthetic fixture."""

    try:
        raw = resources.files("betelgeuze_engine_v2.docking").joinpath(
            SYNTHETIC_D0_FIXTURE_MANIFEST_RESOURCE
        ).read_bytes()
    except (FileNotFoundError, ModuleNotFoundError, OSError) as exc:
        raise DockingPipelineError(
            "repository-owned synthetic D0 fixture manifest is unavailable"
        ) from exc
    if hashlib.sha256(raw).hexdigest() != SYNTHETIC_D0_FIXTURE_MANIFEST_SHA256:
        raise DockingPipelineError(
            "repository-owned synthetic D0 fixture manifest SHA-256 mismatch"
        )
    canonical = raw[:-1] if raw.endswith(b"\n") else raw
    if not canonical or b"\r" in raw or raw.endswith(b"\n\n"):
        raise DockingPipelineError("synthetic D0 fixture manifest is not canonical")
    try:
        document = json.loads(
            canonical.decode("ascii"),
            object_pairs_hook=_reject_duplicate_json_pairs,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise DockingPipelineError(
            "synthetic D0 fixture manifest is invalid"
        ) from exc
    if not isinstance(document, dict) or _canonical_bytes(document) != canonical:
        raise DockingPipelineError("synthetic D0 fixture manifest bytes changed")
    expected_keys = {
        "authority",
        "benchmark_case_id",
        "benchmark_scope",
        "candidate_count",
        "cli_context_id",
        "fixture_id",
        "ligand_system_sha256",
        "pocket_fingerprint_sha256",
        "product_shadow_context_allowlist",
        "profile_id",
        "profile_receipt_sha256",
        "python_api_context_id",
        "receptor_system_sha256",
        "request_sha256",
        "schema_id",
        "seed",
        "top_k",
    }
    if (
        set(document) != expected_keys
        or document.get("schema_id") != SYNTHETIC_D0_FIXTURE_ADMISSION_SCHEMA_ID
    ):
        raise DockingPipelineError("synthetic D0 fixture manifest schema changed")
    authority = document.get("authority")
    if (
        not isinstance(authority, dict)
        or set(authority) != set(_AUTHORITY_FALSE_FIELDS)
        or any(authority.get(name) is not False for name in _AUTHORITY_FALSE_FIELDS)
    ):
        raise DockingPipelineError("synthetic D0 fixture authority changed")
    allowlist = document.get("product_shadow_context_allowlist")
    if not isinstance(allowlist, list):
        raise DockingPipelineError("synthetic D0 shadow allowlist is invalid")
    return SyntheticD0FixtureAdmissionV1(
        fixture_id=document.get("fixture_id"),
        manifest_sha256=SYNTHETIC_D0_FIXTURE_MANIFEST_SHA256,
        request_sha256=document.get("request_sha256"),
        receptor_system_sha256=document.get("receptor_system_sha256"),
        ligand_system_sha256=document.get("ligand_system_sha256"),
        pocket_fingerprint_sha256=document.get("pocket_fingerprint_sha256"),
        profile_id=document.get("profile_id"),
        profile_receipt_sha256=document.get("profile_receipt_sha256"),
        seed=document.get("seed"),
        candidate_count=document.get("candidate_count"),
        top_k=document.get("top_k"),
        benchmark_scope=document.get("benchmark_scope"),
        benchmark_case_id=document.get("benchmark_case_id"),
        python_api_context_id=document.get("python_api_context_id"),
        cli_context_id=document.get("cli_context_id"),
        product_shadow_context_allowlist=tuple(allowlist),
        _factory_seal=_PIPELINE_RECEIPT_FACTORY_SEAL,
    )


@dataclass(frozen=True, slots=True)
class DockingPipelineRequestV1:
    receptor_system: AllAtomSystem = field(repr=False, compare=False)
    ligand_system: AllAtomSystem = field(repr=False, compare=False)
    pocket: PocketDefinition = field(repr=False, compare=False)
    seed: int
    synthetic_only_acknowledgment: str
    fixture_admission: SyntheticD0FixtureAdmissionV1 = field(
        repr=False,
        compare=False,
    )
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
        if type(self.fixture_admission) is not SyntheticD0FixtureAdmissionV1:
            raise TypeError(
                "fixture_admission must be exact SyntheticD0FixtureAdmissionV1"
            )
        if self.synthetic_only_acknowledgment != SYNTHETIC_ONLY_ACKNOWLEDGMENT:
            raise DockingPipelineError(
                "standalone execution requires the exact synthetic-only acknowledgment"
            )
        if self.test_only is not True:
            raise DockingPipelineError(
                "standalone execution remains test-only until external admission"
            )
        self._assert_fixture_admission()
        request_sha256 = _sha256(self._projection())
        if request_sha256 != self.fixture_admission.request_sha256:
            raise DockingPipelineError(
                "synthetic D0 request does not match its repository manifest"
            )
        object.__setattr__(self, "_request_sha256", request_sha256)

    def _assert_fixture_admission(self) -> None:
        self.fixture_admission.assert_request_identity(
            receptor_system_sha256=canonical_system_sha256(self.receptor_system),
            ligand_system_sha256=canonical_system_sha256(self.ligand_system),
            pocket_fingerprint_sha256=self.pocket.fingerprint_sha256,
            seed=self.seed,
            profile=self.profile,
        )

    def _projection(self) -> dict[str, object]:
        return {
            "schema_id": PIPELINE_REQUEST_SCHEMA_ID,
            "receptor_system_sha256": canonical_system_sha256(self.receptor_system),
            "ligand_system_sha256": canonical_system_sha256(self.ligand_system),
            "pocket_fingerprint_sha256": self.pocket.fingerprint_sha256,
            "seed": self.seed,
            "profile_receipt_sha256": self.profile.receipt_sha256,
            "fixture_id": self.fixture_admission.fixture_id,
            "fixture_scope": "repository_owned_synthetic_d0",
            "caller_acknowledged_input_scope": "synthetic_fixture_only",
            "synthetic_only_acknowledgment": self.synthetic_only_acknowledgment,
            "synthetic_fixture_identity_independently_verified": True,
            "test_only": True,
            "external_reservation_requested": False,
            "molecular_experiment_authorized": False,
        }

    @property
    def request_sha256(self) -> str:
        self._assert_fixture_admission()
        observed = _sha256(self._projection())
        if (
            observed != self._request_sha256
            or observed != self.fixture_admission.request_sha256
        ):
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
    component_id: str
    request_sha256: str
    authority_input_receipt_sha256: str
    budget: Mapping[str, object]
    _receipt_sha256: str = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if type(self.context) is not GuidedPlacementContext:
            raise TypeError("proposal plan context must be exact GuidedPlacementContext")
        if type(self.policy) is not GuidedPlacementPolicy:
            raise TypeError("proposal plan policy must be exact GuidedPlacementPolicy")
        if (
            type(self.component_id) is not str
            or not self.component_id
            or self.component_id != self.component_id.strip()
        ):
            raise DockingPipelineError("proposal plan component ID is empty")
        component_id = self.component_id
        request_sha256 = _digest(self.request_sha256, name="plan request_sha256")
        authority_sha256 = _digest(
            self.authority_input_receipt_sha256,
            name="plan authority_input_receipt_sha256",
        )
        if self.context.authority_input_receipt_sha256 != authority_sha256:
            raise DockingPipelineError("proposal plan context is cross-wired")
        budget = _canonical_mapping(self.budget, name="proposal plan budget")
        required_budget_keys = {
            "candidate_count",
            "top_k",
            "max_torsions",
            "max_refinement_steps",
            "translation_radius_angstrom",
            "seed",
        }
        if set(budget) != required_budget_keys:
            raise DockingPipelineError("proposal plan budget is incomplete")
        candidate_count = budget["candidate_count"]
        if type(candidate_count) is not int or not 1 <= candidate_count <= 64:
            raise DockingPipelineError("proposal plan denominator is invalid")
        for name, lower, upper in (
            ("top_k", 1, candidate_count),
            ("max_torsions", 0, 32),
            ("max_refinement_steps", 0, 24),
            ("seed", 0, 2**63 - 1),
        ):
            value = budget[name]
            if type(value) is not int or not lower <= value <= upper:
                raise DockingPipelineError(f"proposal plan {name} is invalid")
        translation_radius = budget["translation_radius_angstrom"]
        if (
            type(translation_radius) is not float
            or not math.isfinite(translation_radius)
            or not 0.0 <= translation_radius <= 20.0
        ):
            raise DockingPipelineError(
                "proposal plan translation radius is invalid"
            )
        if type(self.v3_proposal_indices) is not tuple:
            raise TypeError("proposal plan V3 allocation must be an exact tuple")
        indices = tuple(self.v3_proposal_indices)
        if (
            any(type(value) is not int for value in indices)
            or indices != tuple(sorted(set(indices)))
            or any(not 0 <= value < candidate_count for value in indices)
        ):
            raise DockingPipelineError("proposal plan V3 allocation is invalid")
        object.__setattr__(self, "component_id", component_id)
        object.__setattr__(self, "request_sha256", request_sha256)
        object.__setattr__(
            self,
            "authority_input_receipt_sha256",
            authority_sha256,
        )
        object.__setattr__(self, "budget", budget)
        object.__setattr__(self, "v3_proposal_indices", indices)
        object.__setattr__(self, "_receipt_sha256", _sha256(self._projection()))

    def _projection(self) -> dict[str, object]:
        return {
            "schema_id": PIPELINE_PROPOSAL_PLAN_SCHEMA_ID,
            "component_id": self.component_id,
            "request_sha256": self.request_sha256,
            "authority_input_receipt_sha256": (
                self.authority_input_receipt_sha256
            ),
            "guidance_context_fingerprint_sha256": self.context.fingerprint_sha256,
            "guided_policy_fingerprint_sha256": self.policy.fingerprint_sha256,
            "budget": _thaw_json(self.budget),
            "budget_sha256": _budget_sha256(self.budget),
            "v3_proposal_indices": list(self.v3_proposal_indices),
            "allocation_result_dependent": False,
            "full_budget_bound": True,
            "claim_safe": False,
        }

    @property
    def receipt_sha256(self) -> str:
        observed = _sha256(self._projection())
        if observed != self._receipt_sha256:
            raise DockingPipelineError("proposal generation plan changed")
        return observed

    def to_dict(self) -> dict[str, object]:
        return {**self._projection(), "receipt_sha256": self.receipt_sha256}


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
        return ProposalGenerationPlanV1(
            context=context,
            policy=policy,
            v3_proposal_indices=indices,
            component_id=self.component_id,
            request_sha256=inputs.request_sha256,
            authority_input_receipt_sha256=authority.input_receipt_sha256,
            budget=budget.to_dict(),
        )


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


def _sealed_component_ids() -> dict[str, str]:
    return {
        "input_preparer": CanonicalPreparedInputPreparer.component_id,
        "conformer_provider": RetainedSourceConformerProvider.component_id,
        "proposal_generator": CurrentV7ProposalGenerator.component_id,
        "geometric_admission": PassThroughGeometricAdmission.component_id,
        "scorer": CurrentScorerV1Provider.component_id,
        "refiner": CurrentV7RefinerProvider.component_id,
        "validity_evaluator": EmbeddedElementAwareValidityEvaluator.component_id,
        "ranker": EmbeddedStableScoreRanker.component_id,
        "evidence_recorder": _CanonicalPipelineEvidenceRecorder.component_id,
    }


def _unverified_component_ids() -> dict[str, str]:
    return {role: _UNVERIFIED_COMPONENT_ID for role in _PIPELINE_COMPONENT_ROLES}


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
    _construction_proof_sha256: str = field(
        default="",
        repr=False,
        compare=False,
    )
    _factory_seal: InitVar[object | None] = None
    _receipt_sha256: str = field(init=False, repr=False)

    def __post_init__(self, _factory_seal: object | None) -> None:
        if (
            type(self.candidate_id) is not str
            or not self.candidate_id
            or self.candidate_id != self.candidate_id.strip()
        ):
            raise DockingPipelineError("pipeline candidate ID is empty")
        candidate_id = self.candidate_id
        if type(self.proposal_index) is not int or self.proposal_index < 0:
            raise DockingPipelineError("pipeline candidate index is invalid")
        if type(self.status) is not str or self.status not in {"success", "failure"}:
            raise DockingPipelineError("pipeline candidate status is invalid")
        status = self.status
        if (
            type(self.geometric_admission_status) is not str
            or not self.geometric_admission_status
            or self.geometric_admission_status
            != self.geometric_admission_status.strip()
        ):
            raise DockingPipelineError("pipeline geometric admission status is empty")
        admission = self.geometric_admission_status
        search_row_sha256 = _digest(
            self.search_row_sha256,
            name="candidate search_row_sha256",
        )
        source_sha256 = _digest(
            self.source_proposal_fingerprint_sha256,
            name="candidate source proposal fingerprint",
        )
        if type(self.selection_eligible) is not bool:
            raise DockingPipelineError("candidate selection eligibility must be boolean")
        if (
            type(self.error_code) is not str
            or self.error_code != self.error_code.strip()
        ):
            raise DockingPipelineError("pipeline candidate error code is invalid")
        error_code = self.error_code
        pose_validity = (
            None
            if self.pose_validity is None
            else _canonical_pose_validity(self.pose_validity)
        )
        scorer_terms = (
            None
            if self.scorer_terms is None
            else _canonical_scorer_terms(self.scorer_terms)
        )
        refinement_receipt = (
            None
            if self.refinement_receipt is None
            else _canonical_refinement_receipt(self.refinement_receipt)
        )
        if status == "success":
            result_sha256 = _digest(
                self.result_proposal_fingerprint_sha256,
                name="candidate result proposal fingerprint",
            )
            score_hex = _canonical_float_hex(
                self.score_binary64_hex,
                name="candidate score_binary64_hex",
            )
            if (
                pose_validity is None
                or scorer_terms is None
                or refinement_receipt is None
            ):
                raise DockingPipelineError(
                    "successful pipeline candidate lacks complete evidence"
                )
            if error_code:
                raise DockingPipelineError(
                    "successful pipeline candidate cannot contain an error"
                )
            if (
                pose_validity.get("complete") is not True
                or type(pose_validity.get("valid")) is not bool
                or pose_validity.get("valid") is not self.selection_eligible
            ):
                raise DockingPipelineError(
                    "successful candidate validity and eligibility disagree"
                )
            if (
                scorer_terms.get("proposal_fingerprint_sha256") != result_sha256
                or scorer_terms.get("total_score_binary64_hex") != score_hex
            ):
                raise DockingPipelineError("candidate scorer evidence is cross-wired")
            if refinement_receipt.get("source_proposal_sha256") != source_sha256:
                raise DockingPipelineError(
                    "candidate refinement evidence is cross-wired"
                )
        else:
            if self.result_proposal_fingerprint_sha256 != "":
                raise DockingPipelineError(
                    "failed pipeline candidate cannot fabricate a result proposal"
                )
            result_sha256 = ""
            score_hex = None
            if (
                self.score_binary64_hex is not None
                or scorer_terms is not None
                or pose_validity is not None
                or self.selection_eligible
            ):
                raise DockingPipelineError(
                    "failed pipeline candidate cannot fabricate success evidence"
                )
            if not error_code:
                raise DockingPipelineError(
                    "failed pipeline candidate requires an error code"
                )
            if refinement_receipt is not None:
                if refinement_receipt.get("source_proposal_sha256") != source_sha256:
                    raise DockingPipelineError(
                        "failed candidate refinement evidence is cross-wired"
                    )
        object.__setattr__(self, "candidate_id", candidate_id)
        object.__setattr__(self, "status", status)
        object.__setattr__(self, "geometric_admission_status", admission)
        object.__setattr__(self, "search_row_sha256", search_row_sha256)
        object.__setattr__(
            self,
            "source_proposal_fingerprint_sha256",
            source_sha256,
        )
        object.__setattr__(
            self,
            "result_proposal_fingerprint_sha256",
            result_sha256,
        )
        object.__setattr__(self, "score_binary64_hex", score_hex)
        object.__setattr__(self, "pose_validity", pose_validity)
        object.__setattr__(self, "scorer_terms", scorer_terms)
        object.__setattr__(self, "refinement_receipt", refinement_receipt)
        object.__setattr__(self, "error_code", error_code)
        expected_proof = _construction_proof_sha256(self._projection())
        if _factory_seal is _PIPELINE_RECEIPT_FACTORY_SEAL:
            if self._construction_proof_sha256:
                raise DockingPipelineError(
                    "canonical recorder cannot accept a caller-supplied proof"
                )
            object.__setattr__(
                self,
                "_construction_proof_sha256",
                expected_proof,
            )
        else:
            observed_proof = _digest(
                self._construction_proof_sha256,
                name="candidate recorder construction proof",
            )
            if not hmac.compare_digest(observed_proof, expected_proof):
                raise DockingPipelineError(
                    "candidate canonical-recorder construction proof mismatch"
                )
        object.__setattr__(self, "_receipt_sha256", _sha256(self._projection()))

    def _structural_projection(self) -> dict[str, object]:
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
            else _thaw_json(self.pose_validity),
            "scorer_terms": None
            if self.scorer_terms is None
            else _thaw_json(self.scorer_terms),
            "refinement_receipt": None
            if self.refinement_receipt is None
            else _thaw_json(self.refinement_receipt),
            "error_code": self.error_code,
            "baseline_disagreement": "not_evaluated",
            "claim_safe": False,
        }

    def _projection(self) -> dict[str, object]:
        return {
            **self._structural_projection(),
            "canonical_recorder_factory_sealed": True,
            "construction_proof_scope": (
                "process_local_not_serialized_not_cryptographic_attestation"
            ),
        }

    def _assert_construction_proof(self) -> None:
        observed = _digest(
            self._construction_proof_sha256,
            name="candidate recorder construction proof",
        )
        expected = _construction_proof_sha256(self._projection())
        if not hmac.compare_digest(observed, expected):
            raise DockingPipelineError(
                "candidate canonical-recorder construction proof mismatch"
            )

    @property
    def receipt_sha256(self) -> str:
        self._assert_construction_proof()
        observed = _sha256(self._projection())
        if observed != self._receipt_sha256:
            raise DockingPipelineError("pipeline candidate evidence changed")
        return observed

    def to_dict(self) -> dict[str, object]:
        return {**self._projection(), "receipt_sha256": self.receipt_sha256}


@dataclass(frozen=True, slots=True)
class DockingPipelineResultV1:
    request: DockingPipelineRequestV1 = field(repr=False, compare=False)
    pipeline_source_sha256: str
    scorer_source_sha256: str | None
    refiner_source_sha256: str | None
    prepared_input_receipt_sha256: str
    conformer_receipt_sha256: str
    authority_input_receipt_sha256: str
    proposal_plan_receipt_sha256: str
    guided_placement_receipt_sha256: str
    authenticated_search_receipt_sha256: str
    scorer_v1_result_receipt_sha256: str
    budget: Mapping[str, object]
    proposal_plan: Mapping[str, object]
    candidates: tuple[CandidateEvidenceV1, ...]
    top_proposal_indices: tuple[int, ...]
    component_ids: Mapping[str, str]
    blockers: tuple[str, ...]
    component_binding_mode: str
    _construction_proof_sha256: str = field(
        default="",
        repr=False,
        compare=False,
    )
    _factory_seal: InitVar[object | None] = None
    _receipt_sha256: str = field(init=False, repr=False)

    def __post_init__(self, _factory_seal: object | None) -> None:
        if type(self.request) is not DockingPipelineRequestV1:
            raise TypeError("pipeline result request must be exact DockingPipelineRequestV1")
        if type(self.component_binding_mode) is not str:
            raise DockingPipelineError("pipeline component binding mode is invalid")
        binding_mode = self.component_binding_mode
        if binding_mode not in {
            SEALED_CANONICAL_COMPONENT_BINDING,
            UNVERIFIED_COMPONENT_BINDING,
        }:
            raise DockingPipelineError("pipeline component binding mode is invalid")
        source = _digest(self.pipeline_source_sha256, name="pipeline_source_sha256")
        if binding_mode == SEALED_CANONICAL_COMPONENT_BINDING:
            scorer_source = _digest(
                self.scorer_source_sha256,
                name="scorer_source_sha256",
            )
            refiner_source = _digest(
                self.refiner_source_sha256,
                name="refiner_source_sha256",
            )
        else:
            if (
                self.scorer_source_sha256 is not None
                or self.refiner_source_sha256 is not None
            ):
                raise DockingPipelineError(
                    "unverified dependency injection cannot claim scorer/refiner "
                    "implementation source identities"
                )
            scorer_source = None
            refiner_source = None
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
        guided = _digest(
            self.guided_placement_receipt_sha256,
            name="guided_placement_receipt_sha256",
        )
        authenticated_search = _digest(
            self.authenticated_search_receipt_sha256,
            name="authenticated_search_receipt_sha256",
        )
        scorer = _digest(
            self.scorer_v1_result_receipt_sha256,
            name="scorer_v1_result_receipt_sha256",
        )
        budget = _canonical_mapping(self.budget, name="pipeline result budget")
        expected_budget = {
            "candidate_count": self.request.profile.candidate_count,
            "top_k": self.request.profile.top_k,
            "max_torsions": self.request.profile.max_torsions,
            "max_refinement_steps": self.request.profile.max_refinement_steps,
            "translation_radius_angstrom": min(
                self.request.profile.translation_radius_angstrom,
                self.request.pocket.radius_angstrom,
            ),
            "seed": self.request.seed,
        }
        if _thaw_json(budget) != expected_budget:
            raise DockingPipelineError("pipeline result budget is cross-wired")
        proposal_plan = _canonical_mapping(
            self.proposal_plan,
            name="pipeline result proposal plan",
        )
        expected_plan_keys = {
            "schema_id",
            "component_id",
            "request_sha256",
            "authority_input_receipt_sha256",
            "guidance_context_fingerprint_sha256",
            "guided_policy_fingerprint_sha256",
            "budget",
            "budget_sha256",
            "v3_proposal_indices",
            "allocation_result_dependent",
            "full_budget_bound",
            "claim_safe",
            "receipt_sha256",
        }
        if (
            set(proposal_plan) != expected_plan_keys
            or proposal_plan.get("schema_id") != PIPELINE_PROPOSAL_PLAN_SCHEMA_ID
            or proposal_plan.get("receipt_sha256") != proposal
            or proposal_plan.get("request_sha256") != self.request.request_sha256
            or proposal_plan.get("authority_input_receipt_sha256") != authority
            or proposal_plan.get("budget_sha256") != _budget_sha256(budget)
            or proposal_plan.get("budget") != budget
            or proposal_plan.get("allocation_result_dependent") is not False
            or proposal_plan.get("full_budget_bound") is not True
            or proposal_plan.get("claim_safe") is not False
        ):
            raise DockingPipelineError("pipeline proposal plan is cross-wired")
        for name in (
            "guidance_context_fingerprint_sha256",
            "guided_policy_fingerprint_sha256",
        ):
            _digest(proposal_plan[name], name=f"proposal plan {name}")
        plan_v3_indices = proposal_plan["v3_proposal_indices"]
        if (
            not isinstance(plan_v3_indices, tuple)
            or any(type(value) is not int for value in plan_v3_indices)
            or plan_v3_indices != tuple(sorted(set(plan_v3_indices)))
            or any(
                not 0 <= value < self.request.profile.candidate_count
                for value in plan_v3_indices
            )
        ):
            raise DockingPipelineError("pipeline proposal plan allocation is invalid")
        _embedded_receipt_sha256(proposal_plan, name="pipeline proposal plan")
        if type(self.candidates) is not tuple:
            raise TypeError("pipeline candidates must be an exact tuple")
        untrusted_candidates = tuple(self.candidates)
        if any(type(row) is not CandidateEvidenceV1 for row in untrusted_candidates):
            raise TypeError("pipeline candidates must be exact CandidateEvidenceV1")
        candidates = tuple(untrusted_candidates)
        if len(candidates) != self.request.profile.candidate_count:
            raise DockingPipelineError("pipeline candidate denominator changed")
        if tuple(row.proposal_index for row in candidates) != tuple(
            range(len(candidates))
        ):
            raise DockingPipelineError("pipeline candidate order is not index-stable")
        if len({row.candidate_id for row in candidates}) != len(candidates):
            raise DockingPipelineError("pipeline candidate IDs are not unique")
        for row in candidates:
            row.receipt_sha256
        if type(self.top_proposal_indices) is not tuple:
            raise TypeError("pipeline Top-K indices must be an exact tuple")
        top_indices = tuple(self.top_proposal_indices)
        if (
            any(type(value) is not int for value in top_indices)
            or len(top_indices) > self.request.profile.top_k
            or len(top_indices) != len(set(top_indices))
            or any(not 0 <= value < len(candidates) for value in top_indices)
        ):
            raise DockingPipelineError("pipeline Top-K evidence is invalid")
        if any(
            candidates[value].status != "success"
            or not candidates[value].selection_eligible
            for value in top_indices
        ):
            raise DockingPipelineError(
                "pipeline Top-K must reference successful eligible candidates"
            )
        eligible = sorted(
            (
                row
                for row in candidates
                if row.status == "success" and row.selection_eligible
            ),
            key=lambda row: (
                float.fromhex(str(row.score_binary64_hex)),
                row.proposal_index,
                row.candidate_id,
            ),
        )
        expected_top_indices = tuple(
            row.proposal_index
            for row in eligible[: min(self.request.profile.top_k, len(eligible))]
        )
        if top_indices != expected_top_indices:
            raise DockingPipelineError(
                "pipeline Top-K is not the exact stable eligible ranking"
            )
        component_ids = _canonical_mapping(
            self.component_ids,
            name="pipeline component IDs",
        )
        if set(component_ids) != set(_PIPELINE_COMPONENT_ROLES) or any(
            type(value) is not str or not value or value != value.strip()
            for value in component_ids.values()
        ):
            raise DockingPipelineError("pipeline component IDs are incomplete")
        if type(self.blockers) is not tuple:
            raise TypeError("pipeline blockers must be an exact tuple")
        if any(
            type(value) is not str or not value or value != value.strip()
            for value in self.blockers
        ):
            raise DockingPipelineError("pipeline blockers must be exact strings")
        blockers = self.blockers
        if (
            any(not value for value in blockers)
            or len(blockers) != len(set(blockers))
            or any(value not in blockers for value in PIPELINE_CLAIM_BLOCKERS)
        ):
            raise DockingPipelineError("pipeline result lost a required claim blocker")
        if binding_mode == UNVERIFIED_COMPONENT_BINDING:
            if _thaw_json(component_ids) != _unverified_component_ids():
                raise DockingPipelineError(
                    "unverified dependency injection component identities must "
                    "remain fixed UNVERIFIED"
                )
            if proposal_plan.get("component_id") != _UNVERIFIED_COMPONENT_ID:
                raise DockingPipelineError(
                    "unverified proposal component identity must remain fixed "
                    "UNVERIFIED"
                )
            if any(
                blocker not in blockers
                for blocker in (
                    UNVERIFIED_COMPONENT_BLOCKER,
                    UNVERIFIED_SIDE_EFFECT_BLOCKER,
                )
            ):
                raise DockingPipelineError(
                    "unverified dependency injection lost its blocker"
                )
        elif any(
            blocker in blockers
            for blocker in (
                UNVERIFIED_COMPONENT_BLOCKER,
                UNVERIFIED_SIDE_EFFECT_BLOCKER,
            )
        ):
            raise DockingPipelineError(
                "sealed canonical components cannot carry the DI blocker"
            )
        elif _thaw_json(component_ids) != _sealed_component_ids():
            raise DockingPipelineError(
                "sealed canonical component identities changed"
            )
        elif proposal_plan.get("component_id") != component_ids["proposal_generator"]:
            raise DockingPipelineError("pipeline proposal component is cross-wired")
        object.__setattr__(self, "pipeline_source_sha256", source)
        object.__setattr__(self, "scorer_source_sha256", scorer_source)
        object.__setattr__(self, "refiner_source_sha256", refiner_source)
        object.__setattr__(self, "prepared_input_receipt_sha256", prepared_input)
        object.__setattr__(self, "conformer_receipt_sha256", conformer)
        object.__setattr__(self, "authority_input_receipt_sha256", authority)
        object.__setattr__(self, "proposal_plan_receipt_sha256", proposal)
        object.__setattr__(self, "guided_placement_receipt_sha256", guided)
        object.__setattr__(
            self,
            "authenticated_search_receipt_sha256",
            authenticated_search,
        )
        object.__setattr__(self, "scorer_v1_result_receipt_sha256", scorer)
        object.__setattr__(self, "budget", budget)
        object.__setattr__(self, "proposal_plan", proposal_plan)
        object.__setattr__(self, "candidates", candidates)
        object.__setattr__(self, "top_proposal_indices", top_indices)
        object.__setattr__(self, "component_ids", component_ids)
        object.__setattr__(self, "blockers", blockers)
        object.__setattr__(self, "component_binding_mode", binding_mode)
        expected_proof = _construction_proof_sha256(self._projection())
        if _factory_seal is _PIPELINE_RECEIPT_FACTORY_SEAL:
            if self._construction_proof_sha256:
                raise DockingPipelineError(
                    "canonical recorder cannot accept a caller-supplied proof"
                )
            object.__setattr__(
                self,
                "_construction_proof_sha256",
                expected_proof,
            )
        else:
            observed_proof = _digest(
                self._construction_proof_sha256,
                name="result recorder construction proof",
            )
            if not hmac.compare_digest(observed_proof, expected_proof):
                raise DockingPipelineError(
                    "pipeline canonical-recorder construction proof mismatch"
                )
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

    def _structural_projection(self) -> dict[str, object]:
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
            "guided_placement_receipt_sha256": (
                self.guided_placement_receipt_sha256
            ),
            "authenticated_search_receipt_sha256": (
                self.authenticated_search_receipt_sha256
            ),
            "pipeline_source_binding_mode": (
                "observed_installed_package_resource_after_import_not_preimport_attested"
            ),
            "scorer_refiner_source_binding_status": (
                "observed_canonical_package_resources"
                if self.component_binding_mode == SEALED_CANONICAL_COMPONENT_BINDING
                else "unknown_for_unverified_internal_components"
            ),
            "scorer_v1_result_receipt_sha256": (
                self.scorer_v1_result_receipt_sha256
            ),
            "budget": _thaw_json(self.budget),
            "budget_sha256": _budget_sha256(self.budget),
            "proposal_plan": _thaw_json(self.proposal_plan),
            "candidate_count": len(self.candidates),
            "success_count": self.success_count,
            "failure_count": self.failure_count,
            "top_proposal_indices": list(self.top_proposal_indices),
            "abstained": self.abstained,
            "component_ids": dict(sorted(self.component_ids.items())),
            "component_binding_mode": self.component_binding_mode,
            "canonical_components_sealed": (
                self.component_binding_mode == SEALED_CANONICAL_COMPONENT_BINDING
            ),
            "arbitrary_dependency_injection_used": (
                self.component_binding_mode == UNVERIFIED_COMPONENT_BINDING
            ),
            "component_chain_product_qualified": False,
            "evidence_record_capability_consumed": True,
            "evidence_record_capability_scope": (
                "one_run_process_local_not_serialized_not_cryptographic_attestation"
            ),
            "candidate_evidence": [row.to_dict() for row in self.candidates],
            "blockers": list(self.blockers),
            "failure_denominator_preserved": True,
            "chemistry_inference_performed": (
                False
                if self.component_binding_mode == SEALED_CANONICAL_COMPONENT_BINDING
                else None
            ),
            "pocket_prediction_performed": (
                False
                if self.component_binding_mode == SEALED_CANONICAL_COMPONENT_BINDING
                else None
            ),
            "network_fetch_performed": (
                False
                if self.component_binding_mode == SEALED_CANONICAL_COMPONENT_BINDING
                else None
            ),
            "external_reservation_requested": (
                False
                if self.component_binding_mode == SEALED_CANONICAL_COMPONENT_BINDING
                else None
            ),
            "side_effect_evidence_status": (
                "verified_absent_by_sealed_canonical_components"
                if self.component_binding_mode == SEALED_CANONICAL_COMPONENT_BINDING
                else "unknown_for_unverified_internal_components"
            ),
            "external_reservation_authorized": False,
            "caller_acknowledged_synthetic_fixture_only": True,
            "synthetic_fixture_identity_independently_verified": True,
            "synthetic_d0_fixture_id": self.request.fixture_admission.fixture_id,
            "synthetic_d0_fixture_manifest_sha256": (
                self.request.fixture_admission.manifest_sha256
            ),
            "synthetic_d0_fixture_admission_receipt_sha256": (
                self.request.fixture_admission.receipt_sha256
            ),
            "synthetic_only_acknowledgment": SYNTHETIC_ONLY_ACKNOWLEDGMENT,
            "test_only": True,
            "historical_execution_authorized": False,
            "fresh_holdout_execution_authorized": False,
            "stage0_admission_authority": False,
            "product_execution_authorized": False,
            "customer_pose_emission_authorized": False,
            "public_or_scientific_claim_authorized": False,
            "claim_safe": False,
        }

    def _projection(self) -> dict[str, object]:
        return {
            **self._structural_projection(),
            "canonical_evidence_recorder_factory_sealed": True,
            "construction_proof_scope": (
                "process_local_not_serialized_not_cryptographic_attestation"
            ),
        }

    def _assert_construction_proof(self) -> None:
        observed = _digest(
            self._construction_proof_sha256,
            name="result recorder construction proof",
        )
        expected = _construction_proof_sha256(self._projection())
        if not hmac.compare_digest(observed, expected):
            raise DockingPipelineError(
                "pipeline canonical-recorder construction proof mismatch"
            )

    @property
    def receipt_sha256(self) -> str:
        self._assert_construction_proof()
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


class _PipelineRecordCapability:
    """Opaque, process-local authority for exactly one recorder call."""

    __slots__ = (
        "_binding_proof_sha256",
        "_component_binding_mode",
        "_component_ids",
        "_consumed",
        "_nonce",
        "_object_ids",
        "_pipeline_source_sha256",
        "_recorder_identity",
        "_refiner_source_sha256",
        "_scorer_source_sha256",
    )

    def __init__(
        self,
        *,
        nonce: str,
        recorder_identity: int,
        binding_proof_sha256: str,
        object_ids: tuple[int, ...],
        pipeline_source_sha256: str,
        scorer_source_sha256: str,
        refiner_source_sha256: str,
        component_ids: Mapping[str, str],
        component_binding_mode: str,
        _issuer: object | None = None,
    ) -> None:
        if _issuer is not _PIPELINE_RECORD_CAPABILITY_ISSUER:
            raise DockingPipelineError(
                "pipeline record capability cannot be caller-created"
            )
        self._nonce = _digest(nonce, name="pipeline record capability nonce")
        if type(recorder_identity) is not int or recorder_identity <= 0:
            raise DockingPipelineError("pipeline recorder identity is invalid")
        self._recorder_identity = recorder_identity
        self._binding_proof_sha256 = _digest(
            binding_proof_sha256,
            name="pipeline record capability binding proof",
        )
        if (
            type(object_ids) is not tuple
            or len(object_ids) != 5
            or any(type(value) is not int or value <= 0 for value in object_ids)
        ):
            raise DockingPipelineError(
                "pipeline record capability object binding is invalid"
            )
        self._object_ids = object_ids
        self._pipeline_source_sha256 = _digest(
            pipeline_source_sha256,
            name="capability pipeline source SHA-256",
        )
        self._scorer_source_sha256 = _digest(
            scorer_source_sha256,
            name="capability scorer source SHA-256",
        )
        self._refiner_source_sha256 = _digest(
            refiner_source_sha256,
            name="capability refiner source SHA-256",
        )
        frozen_components = _canonical_mapping(
            component_ids,
            name="capability component IDs",
        )
        if set(frozen_components) != set(_PIPELINE_COMPONENT_ROLES):
            raise DockingPipelineError(
                "pipeline record capability component IDs are incomplete"
            )
        if component_binding_mode == SEALED_CANONICAL_COMPONENT_BINDING:
            expected_components = _sealed_component_ids()
        elif component_binding_mode == UNVERIFIED_COMPONENT_BINDING:
            expected_components = _unverified_component_ids()
        else:
            raise DockingPipelineError(
                "pipeline record capability binding mode is invalid"
            )
        if _thaw_json(frozen_components) != expected_components:
            raise DockingPipelineError(
                "pipeline record capability component binding is cross-wired"
            )
        self._component_ids = frozen_components
        self._component_binding_mode = component_binding_mode
        self._consumed = False


class _CanonicalPipelineEvidenceRecorder:
    component_id = "betelgeuze.engine_v2_canonical_pipeline_evidence/1.0.0"

    def __init__(self) -> None:
        self._capability_lock = threading.Lock()
        self._pending_capability_nonces: set[str] = set()

    @staticmethod
    def _validate_record_inputs(
        *,
        request: DockingPipelineRequestV1,
        budget: DockingBudget,
        proposal_plan: ProposalGenerationPlanV1,
        result: ScorerV1GuidedSearchResult,
        refiner: InteractionAwareTorsionContactEnsembleRefinerV7,
        admission_statuses: tuple[str, ...],
        top_proposal_indices: tuple[int, ...],
    ) -> None:
        if type(request) is not DockingPipelineRequestV1:
            raise TypeError("recorder request must be exact DockingPipelineRequestV1")
        if type(budget) is not DockingBudget:
            raise TypeError("recorder budget must be exact DockingBudget")
        if type(proposal_plan) is not ProposalGenerationPlanV1:
            raise TypeError(
                "recorder proposal plan must be exact ProposalGenerationPlanV1"
            )
        if type(result) is not ScorerV1GuidedSearchResult:
            raise TypeError(
                "recorder result must be exact ScorerV1GuidedSearchResult"
            )
        if type(refiner) is not InteractionAwareTorsionContactEnsembleRefinerV7:
            raise TypeError("recorder refiner must be exact V7 ensemble refiner")
        if type(admission_statuses) is not tuple or any(
            type(value) is not str or not value or value != value.strip()
            for value in admission_statuses
        ):
            raise TypeError("recorder admission statuses must be exact strings")
        if type(top_proposal_indices) is not tuple or any(
            type(value) is not int for value in top_proposal_indices
        ):
            raise TypeError("recorder Top-K indices must be an exact integer tuple")

    @staticmethod
    def _binding_projection(
        *,
        request: DockingPipelineRequestV1,
        prepared_input_receipt_sha256: str,
        conformer_receipt_sha256: str,
        authority_input_receipt_sha256: str,
        budget: DockingBudget,
        proposal_plan: ProposalGenerationPlanV1,
        result: ScorerV1GuidedSearchResult,
        refiner: InteractionAwareTorsionContactEnsembleRefinerV7,
        admission_statuses: tuple[str, ...],
        top_proposal_indices: tuple[int, ...],
        pipeline_source_sha256: str,
        scorer_source_sha256: str,
        refiner_source_sha256: str,
        component_ids: Mapping[str, str],
        component_binding_mode: str,
    ) -> dict[str, object]:
        return {
            "schema_id": (
                "betelgeuze.engine_v2_pipeline_record_capability_binding/1.0.0"
            ),
            "request_sha256": request.request_sha256,
            "prepared_input_receipt_sha256": _digest(
                prepared_input_receipt_sha256,
                name="capability prepared input receipt",
            ),
            "conformer_receipt_sha256": _digest(
                conformer_receipt_sha256,
                name="capability conformer receipt",
            ),
            "authority_input_receipt_sha256": _digest(
                authority_input_receipt_sha256,
                name="capability authority input receipt",
            ),
            "budget": budget.to_dict(),
            "budget_sha256": _budget_sha256(budget),
            "proposal_plan_receipt_sha256": proposal_plan.receipt_sha256,
            "scorer_v1_result_receipt_sha256": result.receipt_sha256,
            "refinement_receipts_sha256": _sha256(refiner.receipts),
            "admission_statuses": list(admission_statuses),
            "top_proposal_indices": list(top_proposal_indices),
            "pipeline_source_sha256": _digest(
                pipeline_source_sha256,
                name="capability pipeline source",
            ),
            "scorer_source_sha256": _digest(
                scorer_source_sha256,
                name="capability scorer source",
            ),
            "refiner_source_sha256": _digest(
                refiner_source_sha256,
                name="capability refiner source",
            ),
            "component_ids": _thaw_json(
                _canonical_mapping(component_ids, name="capability components")
            ),
            "component_binding_mode": component_binding_mode,
        }

    def _issue_capability(
        self,
        *,
        request: DockingPipelineRequestV1,
        prepared_input_receipt_sha256: str,
        conformer_receipt_sha256: str,
        authority_input_receipt_sha256: str,
        budget: DockingBudget,
        proposal_plan: ProposalGenerationPlanV1,
        result: ScorerV1GuidedSearchResult,
        refiner: InteractionAwareTorsionContactEnsembleRefinerV7,
        admission_statuses: tuple[str, ...],
        top_proposal_indices: tuple[int, ...],
        pipeline_source_sha256: str,
        scorer_source_sha256: str,
        refiner_source_sha256: str,
        component_ids: Mapping[str, str],
        component_binding_mode: str,
        _issuer: object | None = None,
    ) -> _PipelineRecordCapability:
        if _issuer is not _PIPELINE_RECORD_CAPABILITY_ISSUER:
            raise DockingPipelineError(
                "pipeline record capability requires the internal run issuer"
            )
        self._validate_record_inputs(
            request=request,
            budget=budget,
            proposal_plan=proposal_plan,
            result=result,
            refiner=refiner,
            admission_statuses=admission_statuses,
            top_proposal_indices=top_proposal_indices,
        )
        projection = self._binding_projection(
            request=request,
            prepared_input_receipt_sha256=prepared_input_receipt_sha256,
            conformer_receipt_sha256=conformer_receipt_sha256,
            authority_input_receipt_sha256=authority_input_receipt_sha256,
            budget=budget,
            proposal_plan=proposal_plan,
            result=result,
            refiner=refiner,
            admission_statuses=admission_statuses,
            top_proposal_indices=top_proposal_indices,
            pipeline_source_sha256=pipeline_source_sha256,
            scorer_source_sha256=scorer_source_sha256,
            refiner_source_sha256=refiner_source_sha256,
            component_ids=component_ids,
            component_binding_mode=component_binding_mode,
        )
        object_ids = (
            id(request),
            id(budget),
            id(proposal_plan),
            id(result),
            id(refiner),
        )
        with self._capability_lock:
            nonce = secrets.token_hex(32)
            while nonce in self._pending_capability_nonces:
                nonce = secrets.token_hex(32)
            capability = _PipelineRecordCapability(
                nonce=nonce,
                recorder_identity=id(self),
                binding_proof_sha256=_construction_proof_sha256(projection),
                object_ids=object_ids,
                pipeline_source_sha256=pipeline_source_sha256,
                scorer_source_sha256=scorer_source_sha256,
                refiner_source_sha256=refiner_source_sha256,
                component_ids=component_ids,
                component_binding_mode=component_binding_mode,
                _issuer=_PIPELINE_RECORD_CAPABILITY_ISSUER,
            )
            self._pending_capability_nonces.add(nonce)
        return capability

    def _consume_capability(
        self,
        capability: object,
        *,
        request: DockingPipelineRequestV1,
        prepared_input_receipt_sha256: str,
        conformer_receipt_sha256: str,
        authority_input_receipt_sha256: str,
        budget: DockingBudget,
        proposal_plan: ProposalGenerationPlanV1,
        result: ScorerV1GuidedSearchResult,
        refiner: InteractionAwareTorsionContactEnsembleRefinerV7,
        admission_statuses: tuple[str, ...],
        top_proposal_indices: tuple[int, ...],
    ) -> _PipelineRecordCapability:
        if type(capability) is not _PipelineRecordCapability:
            raise DockingPipelineError(
                "recorder requires an exact one-shot pipeline capability"
            )
        with self._capability_lock:
            if (
                capability._recorder_identity != id(self)
                or capability._nonce not in self._pending_capability_nonces
                or capability._consumed
            ):
                raise DockingPipelineError(
                    "pipeline record capability was not issued here or was consumed"
                )
            self._pending_capability_nonces.remove(capability._nonce)
            capability._consumed = True
        self._validate_record_inputs(
            request=request,
            budget=budget,
            proposal_plan=proposal_plan,
            result=result,
            refiner=refiner,
            admission_statuses=admission_statuses,
            top_proposal_indices=top_proposal_indices,
        )
        object_ids = (
            id(request),
            id(budget),
            id(proposal_plan),
            id(result),
            id(refiner),
        )
        if object_ids != capability._object_ids:
            raise DockingPipelineError(
                "pipeline record capability object identity is cross-wired"
            )
        if (
            capability._pipeline_source_sha256
            != observed_pipeline_source_sha256()
            or capability._scorer_source_sha256
            != _observed_docking_source_sha256("scorer_v1.py")
            or capability._refiner_source_sha256
            != _observed_docking_source_sha256("torsion_contact_refinement.py")
        ):
            raise DockingPipelineError(
                "pipeline record capability source identity changed"
            )
        projection = self._binding_projection(
            request=request,
            prepared_input_receipt_sha256=prepared_input_receipt_sha256,
            conformer_receipt_sha256=conformer_receipt_sha256,
            authority_input_receipt_sha256=authority_input_receipt_sha256,
            budget=budget,
            proposal_plan=proposal_plan,
            result=result,
            refiner=refiner,
            admission_statuses=admission_statuses,
            top_proposal_indices=top_proposal_indices,
            pipeline_source_sha256=capability._pipeline_source_sha256,
            scorer_source_sha256=capability._scorer_source_sha256,
            refiner_source_sha256=capability._refiner_source_sha256,
            component_ids=capability._component_ids,
            component_binding_mode=capability._component_binding_mode,
        )
        expected_proof = _construction_proof_sha256(projection)
        if not hmac.compare_digest(
            capability._binding_proof_sha256,
            expected_proof,
        ):
            raise DockingPipelineError(
                "pipeline record capability evidence binding is cross-wired"
            )
        return capability

    def _record(
        self,
        *,
        capability: object,
        request: DockingPipelineRequestV1,
        prepared_input_receipt_sha256: str,
        conformer_receipt_sha256: str,
        authority_input_receipt_sha256: str,
        budget: DockingBudget,
        proposal_plan: ProposalGenerationPlanV1,
        result: ScorerV1GuidedSearchResult,
        refiner: InteractionAwareTorsionContactEnsembleRefinerV7,
        admission_statuses: tuple[str, ...],
        top_proposal_indices: tuple[int, ...],
    ) -> DockingPipelineResultV1:
        consumed_capability = self._consume_capability(
            capability,
            request=request,
            prepared_input_receipt_sha256=prepared_input_receipt_sha256,
            conformer_receipt_sha256=conformer_receipt_sha256,
            authority_input_receipt_sha256=authority_input_receipt_sha256,
            budget=budget,
            proposal_plan=proposal_plan,
            result=result,
            refiner=refiner,
            admission_statuses=admission_statuses,
            top_proposal_indices=top_proposal_indices,
        )
        search = result.guided_search_result.authenticated_search_result.search_result
        guided_receipt = result.guided_search_result.guided_receipt
        authenticated_search = result.guided_search_result.authenticated_search_result
        if (
            search.budget.to_dict() != budget.to_dict()
            or guided_receipt.budget_sha256 != _budget_sha256(budget)
            or guided_receipt.authenticated_input_receipt_sha256
            != authority_input_receipt_sha256
            or guided_receipt.guidance_context_sha256
            != proposal_plan.context.fingerprint_sha256
            or guided_receipt.guided_policy_sha256
            != proposal_plan.policy.fingerprint_sha256
            or proposal_plan.budget != _canonical_mapping(
                budget.to_dict(),
                name="recorder budget",
            )
        ):
            raise DockingPipelineError(
                "recorder search budget or proposal plan is cross-wired"
            )
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
                    _factory_seal=_PIPELINE_RECEIPT_FACTORY_SEAL,
                )
            )
        proposal_plan_document = proposal_plan.to_dict()
        if (
            consumed_capability._component_binding_mode
            == UNVERIFIED_COMPONENT_BINDING
        ):
            proposal_plan_document.pop("receipt_sha256")
            proposal_plan_document["component_id"] = _UNVERIFIED_COMPONENT_ID
            proposal_plan_document["receipt_sha256"] = _sha256(
                proposal_plan_document
            )
        return DockingPipelineResultV1(
            request=request,
            pipeline_source_sha256=(
                consumed_capability._pipeline_source_sha256
            ),
            scorer_source_sha256=(
                consumed_capability._scorer_source_sha256
                if consumed_capability._component_binding_mode
                == SEALED_CANONICAL_COMPONENT_BINDING
                else None
            ),
            refiner_source_sha256=(
                consumed_capability._refiner_source_sha256
                if consumed_capability._component_binding_mode
                == SEALED_CANONICAL_COMPONENT_BINDING
                else None
            ),
            prepared_input_receipt_sha256=prepared_input_receipt_sha256,
            conformer_receipt_sha256=conformer_receipt_sha256,
            authority_input_receipt_sha256=authority_input_receipt_sha256,
            proposal_plan_receipt_sha256=proposal_plan_document[
                "receipt_sha256"
            ],
            guided_placement_receipt_sha256=guided_receipt.receipt_sha256,
            authenticated_search_receipt_sha256=(
                authenticated_search.receipt_sha256
            ),
            scorer_v1_result_receipt_sha256=result.receipt_sha256,
            budget=budget.to_dict(),
            proposal_plan=proposal_plan_document,
            candidates=tuple(candidates),
            top_proposal_indices=top_proposal_indices,
            component_ids=consumed_capability._component_ids,
            blockers=(
                PIPELINE_CLAIM_BLOCKERS
                if consumed_capability._component_binding_mode
                == SEALED_CANONICAL_COMPONENT_BINDING
                else (
                    *PIPELINE_CLAIM_BLOCKERS,
                    UNVERIFIED_COMPONENT_BLOCKER,
                    UNVERIFIED_SIDE_EFFECT_BLOCKER,
                )
            ),
            component_binding_mode=(
                consumed_capability._component_binding_mode
            ),
            _factory_seal=_PIPELINE_RECEIPT_FACTORY_SEAL,
        )


class DockingPipeline:
    """Compose the synthetic-only CPU baseline behind one shared core.

    The no-argument public path seals the exact canonical component types.
    Supplying any component is retained only as internal/test dependency
    injection and is permanently marked unverified in the result receipt.
    """

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
        *,
        _internal_unverified_execution_latch: object | None = None,
    ) -> None:
        supplied = (
            input_preparer,
            conformer_provider,
            proposal_generator,
            geometric_admission,
            scorer,
            refiner,
            validity_evaluator,
            ranker,
        )
        any_supplied = any(value is not None for value in supplied)
        if any_supplied and (
            _internal_unverified_execution_latch
            is not _INTERNAL_UNVERIFIED_EXECUTION_LATCH
        ):
            raise DockingPipelineError(
                "dependency-injected execution requires the internal test-only latch"
            )
        if not any_supplied and _internal_unverified_execution_latch is not None:
            raise DockingPipelineError(
                "the internal DI latch cannot be used with canonical components"
            )
        self._component_binding_mode = (
            UNVERIFIED_COMPONENT_BINDING
            if any_supplied
            else SEALED_CANONICAL_COMPONENT_BINDING
        )
        self.input_preparer = (
            CanonicalPreparedInputPreparer()
            if input_preparer is None
            else input_preparer
        )
        self.conformer_provider = (
            RetainedSourceConformerProvider()
            if conformer_provider is None
            else conformer_provider
        )
        self.proposal_generator = (
            CurrentV7ProposalGenerator()
            if proposal_generator is None
            else proposal_generator
        )
        self.geometric_admission = (
            PassThroughGeometricAdmission()
            if geometric_admission is None
            else geometric_admission
        )
        self.scorer = CurrentScorerV1Provider() if scorer is None else scorer
        self.refiner = CurrentV7RefinerProvider() if refiner is None else refiner
        self.validity_evaluator = (
            EmbeddedElementAwareValidityEvaluator()
            if validity_evaluator is None
            else validity_evaluator
        )
        self.ranker = EmbeddedStableScoreRanker() if ranker is None else ranker
        self._evidence_recorder = _CanonicalPipelineEvidenceRecorder()
        self._assert_component_contracts()

    @classmethod
    def _internal_test_only_with_unverified_components(
        cls,
        input_preparer: InputPreparer | None = None,
        conformer_provider: ConformerProvider | None = None,
        proposal_generator: ProposalGenerator | None = None,
        geometric_admission: GeometricAdmission | None = None,
        scorer: ScorerProvider | None = None,
        refiner: RefinerProvider | None = None,
        validity_evaluator: ValidityEvaluator | None = None,
        ranker: Ranker | None = None,
    ) -> "DockingPipeline":
        """Construct an explicitly unverified pipeline for unit tests only."""

        if all(
            value is None
            for value in (
                input_preparer,
                conformer_provider,
                proposal_generator,
                geometric_admission,
                scorer,
                refiner,
                validity_evaluator,
                ranker,
            )
        ):
            raise DockingPipelineError(
                "the internal DI path requires at least one supplied component"
            )
        return cls(
            input_preparer=input_preparer,
            conformer_provider=conformer_provider,
            proposal_generator=proposal_generator,
            geometric_admission=geometric_admission,
            scorer=scorer,
            refiner=refiner,
            validity_evaluator=validity_evaluator,
            ranker=ranker,
            _internal_unverified_execution_latch=(
                _INTERNAL_UNVERIFIED_EXECUTION_LATCH
            ),
        )

    def _assert_component_contracts(self) -> None:
        expected = (
            (self.input_preparer, InputPreparer, "input_preparer"),
            (self.conformer_provider, ConformerProvider, "conformer_provider"),
            (self.proposal_generator, ProposalGenerator, "proposal_generator"),
            (self.geometric_admission, GeometricAdmission, "geometric_admission"),
            (self.scorer, ScorerProvider, "scorer"),
            (self.refiner, RefinerProvider, "refiner"),
            (self.validity_evaluator, ValidityEvaluator, "validity_evaluator"),
            (self.ranker, Ranker, "ranker"),
        )
        for value, protocol, name in expected:
            if not isinstance(value, protocol):
                raise TypeError(f"{name} does not satisfy the pipeline protocol")
            component_id = getattr(value, "component_id", None)
            if (
                type(component_id) is not str
                or not component_id
                or component_id != component_id.strip()
            ):
                raise DockingPipelineError(f"{name} component ID is invalid")
        if type(self._evidence_recorder) is not _CanonicalPipelineEvidenceRecorder:
            raise TypeError(
                "pipeline internal evidence recorder identity changed"
            )
        if self._component_binding_mode == SEALED_CANONICAL_COMPONENT_BINDING:
            sealed_types = {
                "input_preparer": CanonicalPreparedInputPreparer,
                "conformer_provider": RetainedSourceConformerProvider,
                "proposal_generator": CurrentV7ProposalGenerator,
                "geometric_admission": PassThroughGeometricAdmission,
                "scorer": CurrentScorerV1Provider,
                "refiner": CurrentV7RefinerProvider,
                "validity_evaluator": EmbeddedElementAwareValidityEvaluator,
                "ranker": EmbeddedStableScoreRanker,
            }
            if any(
                type(getattr(self, role)) is not component_type
                for role, component_type in sealed_types.items()
            ):
                raise DockingPipelineError("sealed canonical component type changed")
            if self._observed_component_ids() != _sealed_component_ids():
                raise DockingPipelineError("sealed canonical component ID changed")

    def _observed_component_ids(self) -> dict[str, str]:
        return {
            "input_preparer": self.input_preparer.component_id,
            "conformer_provider": self.conformer_provider.component_id,
            "proposal_generator": self.proposal_generator.component_id,
            "geometric_admission": self.geometric_admission.component_id,
            "scorer": self.scorer.component_id,
            "refiner": self.refiner.component_id,
            "validity_evaluator": self.validity_evaluator.component_id,
            "ranker": self.ranker.component_id,
            "evidence_recorder": self._evidence_recorder.component_id,
        }

    @property
    def component_ids(self) -> dict[str, str]:
        if self._component_binding_mode == SEALED_CANONICAL_COMPONENT_BINDING:
            return self._observed_component_ids()
        return _unverified_component_ids()

    def run(self, request: DockingPipelineRequestV1) -> DockingPipelineResultV1:
        if type(request) is not DockingPipelineRequestV1:
            raise TypeError("request must be exact DockingPipelineRequestV1")
        request._assert_fixture_admission()
        if request.request_sha256 != request.fixture_admission.request_sha256:
            raise DockingPipelineError(
                "pipeline request is cross-wired from its synthetic D0 admission"
            )
        self._assert_component_contracts()
        inputs = self.input_preparer.prepare(request)
        if type(inputs) is not PreparedDockingInputsV1:
            raise TypeError("input preparer must return exact PreparedDockingInputsV1")
        if inputs.request_sha256 != request.request_sha256:
            raise DockingPipelineError("prepared inputs are cross-wired")
        conformer_receipt_sha256 = self.conformer_provider.bind(inputs)
        conformer_receipt_sha256 = _digest(
            conformer_receipt_sha256,
            name="conformer_receipt_sha256",
        )
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
        if type(plan) is not ProposalGenerationPlanV1:
            raise TypeError(
                "proposal generator must return exact ProposalGenerationPlanV1"
            )
        expected_v3_indices = uniform_v3_ensemble_proposal_indices(
            plan.context,
            budget,
            plan.policy,
        )
        if (
            plan.component_id != self.proposal_generator.component_id
            or plan.request_sha256 != request.request_sha256
            or plan.authority_input_receipt_sha256
            != authority.input_receipt_sha256
            or _thaw_json(plan.budget) != budget.to_dict()
            or plan.v3_proposal_indices != expected_v3_indices
            or plan.context.receptor_system_sha256
            != canonical_system_sha256(inputs.receptor_system)
            or plan.context.ligand_system_sha256
            != canonical_system_sha256(inputs.ligand_system)
        ):
            raise DockingPipelineError("pipeline proposal plan is cross-wired")
        plan.receipt_sha256
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
        if (
            type(admission_statuses) is not tuple
            or len(admission_statuses) != request.profile.candidate_count
            or any(
                type(value) is not str or not value or value != value.strip()
                for value in admission_statuses
            )
        ):
            raise DockingPipelineError(
                "geometric admission did not preserve the exact denominator"
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
        self._assert_component_contracts()
        component_ids = self.component_ids
        record_capability = self._evidence_recorder._issue_capability(
            request=request,
            prepared_input_receipt_sha256=inputs.receipt_sha256,
            conformer_receipt_sha256=conformer_receipt_sha256,
            authority_input_receipt_sha256=authority.input_receipt_sha256,
            budget=budget,
            proposal_plan=plan,
            result=result,
            refiner=refiner,
            admission_statuses=admission_statuses,
            top_proposal_indices=top_indices,
            pipeline_source_sha256=pipeline_source_sha256,
            scorer_source_sha256=scorer_source_sha256,
            refiner_source_sha256=refiner_source_sha256,
            component_ids=component_ids,
            component_binding_mode=self._component_binding_mode,
            _issuer=_PIPELINE_RECORD_CAPABILITY_ISSUER,
        )
        recorded = self._evidence_recorder._record(
            capability=record_capability,
            request=request,
            prepared_input_receipt_sha256=inputs.receipt_sha256,
            conformer_receipt_sha256=conformer_receipt_sha256,
            authority_input_receipt_sha256=authority.input_receipt_sha256,
            budget=budget,
            proposal_plan=plan,
            result=result,
            refiner=refiner,
            admission_statuses=admission_statuses,
            top_proposal_indices=top_indices,
        )
        if type(recorded) is not DockingPipelineResultV1:
            raise TypeError(
                "evidence recorder must return exact DockingPipelineResultV1"
            )
        recorded.receipt_sha256
        return recorded


__all__ = [
    "CURRENT_V7_FIXED64_PROFILE_ID",
    "EXTERNAL_AUTHORITY_BLOCKERS",
    "PIPELINE_CLAIM_BLOCKERS",
    "PIPELINE_CANDIDATE_SCHEMA_ID",
    "PIPELINE_PROFILE_SCHEMA_ID",
    "PIPELINE_PROPOSAL_PLAN_SCHEMA_ID",
    "PIPELINE_REQUEST_SCHEMA_ID",
    "PIPELINE_RESULT_SCHEMA_ID",
    "SEALED_CANONICAL_COMPONENT_BINDING",
    "SYNTHETIC_D0_FIXTURE_ADMISSION_RECEIPT_SCHEMA_ID",
    "SYNTHETIC_D0_FIXTURE_ADMISSION_SCHEMA_ID",
    "SYNTHETIC_D0_FIXTURE_ID",
    "SYNTHETIC_D0_FIXTURE_MANIFEST_SHA256",
    "SYNTHETIC_D0_FIXTURE_ONLY_BLOCKER",
    "SYNTHETIC_D0_FIXTURE_REQUEST_SHA256",
    "SYNTHETIC_ONLY_ACKNOWLEDGMENT",
    "SYNTHETIC_TEST_PROFILE_ID",
    "UNVERIFIED_COMPONENT_BINDING",
    "UNVERIFIED_COMPONENT_BLOCKER",
    "UNVERIFIED_SIDE_EFFECT_BLOCKER",
    "CandidateEvidenceV1",
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
    "GeometricAdmission",
    "InputPreparer",
    "PassThroughGeometricAdmission",
    "ProposalGenerator",
    "ProposalGenerationPlanV1",
    "Ranker",
    "RefinerProvider",
    "RetainedSourceConformerProvider",
    "ScorerProvider",
    "SyntheticD0FixtureAdmissionV1",
    "ValidityEvaluator",
    "observed_pipeline_source_sha256",
    "repository_synthetic_d0_fixture_admission",
]

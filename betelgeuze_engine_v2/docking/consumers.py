"""Sealed synthetic-D0 consumers over one claim-blocked docking core.

The public consumers in this module admit one repository-owned synthetic
request.  They never accept caller-supplied components, historical/public
benchmark scopes, Fresh holdouts, reservations, or molecular execution
authority.  Dependency injection remains available on :class:`DockingPipeline`
for internal unit tests only; it is not a public consumer construction path.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from enum import Enum
import hashlib
from importlib import resources
import json
from types import MappingProxyType
from typing import Literal

from .pipeline import (
    CanonicalPipelineEvidenceRecorder,
    CanonicalPreparedInputPreparer,
    CurrentScorerV1Provider,
    CurrentV7ProposalGenerator,
    CurrentV7RefinerProvider,
    DockingPipeline,
    DockingPipelineError,
    DockingPipelineRequestV1,
    DockingPipelineResultV1,
    EmbeddedElementAwareValidityEvaluator,
    EmbeddedStableScoreRanker,
    PassThroughGeometricAdmission,
    RetainedSourceConformerProvider,
)


CONSUMER_ENVELOPE_SCHEMA_ID = (
    "betelgeuze.engine_v2_standalone_consumer_envelope/1.1.0"
)
SYNTHETIC_D0_FIXTURE_ADMISSION_SCHEMA_ID = (
    "betelgeuze.engine_v2_synthetic_d0_fixture_admission/1.0.0"
)
SYNTHETIC_D0_FIXTURE_ADMISSION_RECEIPT_SCHEMA_ID = (
    "betelgeuze.engine_v2_synthetic_d0_fixture_admission_receipt/1.0.0"
)
SYNTHETIC_D0_FIXTURE_MANIFEST_RESOURCE = (
    "synthetic_d0_fixture_admission.json"
)
SYNTHETIC_D0_FIXTURE_MANIFEST_SHA256 = (
    "0e368e264964af07d0fb5d0d67eb94f095abd0b02a3a199cdb3607af5ac6ae7d"
)
SYNTHETIC_D0_FIXTURE_REQUEST_SHA256 = (
    "2edec33ba917fd41d9eb42029b92582ab4dcf5157e6d8a7c4794038ade89a9f1"
)
SYNTHETIC_D0_FIXTURE_ID = (
    "betelgeuze.engine_v2.synthetic_d0_standalone_fixture/1.0.0"
)
DIAGNOSTIC_BENCHMARK_SCOPE = "d0_synthetic_test_fixture"
SYNTHETIC_D0_BENCHMARK_CASE_ID = "synthetic-d0-standalone-001"
SYNTHETIC_D0_PYTHON_API_CONTEXT_ID = (
    "betelgeuze.engine_v2.synthetic_d0/python_api"
)
SYNTHETIC_D0_CLI_CONTEXT_ID = "betelgeuze.engine_v2.synthetic_d0/cli"
SYNTHETIC_D0_SHADOW_CONTEXT_ALLOWLIST = (
    "betelgeuze.engine_v2.synthetic_d0/product_shadow_second_opinion",
)

CANONICAL_COMPONENT_MANIFEST_SCHEMA_ID = (
    "betelgeuze.engine_v2_canonical_standalone_component_manifest/1.0.0"
)
CANONICAL_PIPELINE_FACTORY_ID = (
    "betelgeuze.engine_v2_canonical_standalone_pipeline_factory/1.0.0"
)
CANONICAL_COMPONENT_MANIFEST_SHA256 = (
    "ba534145711647f4d91a03078e4b2b762eb2c6fefcf6944c02434d9249c20239"
)
CONSUMER_SURFACE_POLICY_ID = (
    "betelgeuze.engine_v2_synthetic_d0_consumer_surface_policy/1.0.0"
)

ConsumerSurface = Literal[
    "python_api",
    "benchmark_adapter",
    "product_shadow",
    "cli",
]


_CANONICAL_COMPONENT_IDS = MappingProxyType(
    {
        "input_preparer": (
            "betelgeuze.engine_v2_canonical_prepared_input/1.0.0"
        ),
        "conformer_provider": (
            "betelgeuze.engine_v2_retained_source_conformer/1.0.0"
        ),
        "proposal_generator": (
            "betelgeuze.engine_v2_current_uniform_v3_proposals/1.0.0"
        ),
        "geometric_admission": (
            "betelgeuze.engine_v2_pass_through_geometric_admission/1.0.0"
        ),
        "scorer": "betelgeuze.engine_v2_current_scorer_v1_provider/1.0.0",
        "refiner": "betelgeuze.engine_v2_current_v7_refiner_provider/1.0.0",
        "validity_evaluator": (
            "betelgeuze.engine_v2_embedded_element_validity/1.0.0"
        ),
        "ranker": "betelgeuze.engine_v2_embedded_stable_score_ranker/1.0.0",
        "evidence_recorder": (
            "betelgeuze.engine_v2_canonical_pipeline_evidence/1.0.0"
        ),
    }
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
        raise DockingPipelineError("consumer evidence is not canonical JSON") from exc


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _require_sha256(value: object, *, name: str) -> str:
    text = str(value or "").strip().lower()
    if len(text) != 64 or any(character not in "0123456789abcdef" for character in text):
        raise DockingPipelineError(f"{name} must be a lowercase SHA-256")
    return text


def _reject_duplicate_pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise DockingPipelineError(
                "synthetic D0 fixture manifest contains duplicate keys"
            )
        result[key] = value
    return result


def canonical_standalone_component_manifest() -> dict[str, object]:
    """Return the exact component identifiers admitted on public surfaces."""

    projection = {
        "schema_id": CANONICAL_COMPONENT_MANIFEST_SCHEMA_ID,
        "factory_id": CANONICAL_PIPELINE_FACTORY_ID,
        "components": dict(_CANONICAL_COMPONENT_IDS),
    }
    if _sha256(projection) != CANONICAL_COMPONENT_MANIFEST_SHA256:
        raise DockingPipelineError("canonical component manifest identity changed")
    return {
        **projection,
        "manifest_sha256": CANONICAL_COMPONENT_MANIFEST_SHA256,
    }


def build_canonical_standalone_pipeline() -> DockingPipeline:
    """Build the one sealed component graph used by every public consumer."""

    canonical_standalone_component_manifest()
    pipeline = DockingPipeline(
        input_preparer=CanonicalPreparedInputPreparer(),
        conformer_provider=RetainedSourceConformerProvider(),
        proposal_generator=CurrentV7ProposalGenerator(),
        geometric_admission=PassThroughGeometricAdmission(),
        scorer=CurrentScorerV1Provider(),
        refiner=CurrentV7RefinerProvider(),
        validity_evaluator=EmbeddedElementAwareValidityEvaluator(),
        ranker=EmbeddedStableScoreRanker(),
        evidence_recorder=CanonicalPipelineEvidenceRecorder(),
    )
    if type(pipeline) is not DockingPipeline:
        raise DockingPipelineError("canonical pipeline factory returned a subclass")
    if pipeline.component_ids != dict(_CANONICAL_COMPONENT_IDS):
        raise DockingPipelineError("canonical pipeline component graph changed")
    return pipeline


@dataclass(frozen=True, slots=True)
class SyntheticD0FixtureAdmissionV1:
    """Identity-only admission for the repository-owned synthetic D0 request."""

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
    _receipt_sha256: str = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if self.fixture_id != SYNTHETIC_D0_FIXTURE_ID:
            raise DockingPipelineError("synthetic D0 fixture ID is not admitted")
        if (
            _require_sha256(self.manifest_sha256, name="fixture manifest SHA-256")
            != SYNTHETIC_D0_FIXTURE_MANIFEST_SHA256
        ):
            raise DockingPipelineError("synthetic D0 fixture manifest is not exact")
        if (
            _require_sha256(self.request_sha256, name="fixture request SHA-256")
            != SYNTHETIC_D0_FIXTURE_REQUEST_SHA256
        ):
            raise DockingPipelineError("synthetic D0 fixture request is not exact")
        for name in (
            "receptor_system_sha256",
            "ligand_system_sha256",
            "pocket_fingerprint_sha256",
            "profile_receipt_sha256",
        ):
            object.__setattr__(
                self,
                name,
                _require_sha256(getattr(self, name), name=name),
            )
        if self.benchmark_scope != DIAGNOSTIC_BENCHMARK_SCOPE:
            raise DockingPipelineError("synthetic D0 benchmark scope is not exact")
        if self.benchmark_case_id != SYNTHETIC_D0_BENCHMARK_CASE_ID:
            raise DockingPipelineError("synthetic D0 benchmark case ID is not exact")
        if self.python_api_context_id != SYNTHETIC_D0_PYTHON_API_CONTEXT_ID:
            raise DockingPipelineError("synthetic D0 Python API context is not exact")
        if self.cli_context_id != SYNTHETIC_D0_CLI_CONTEXT_ID:
            raise DockingPipelineError("synthetic D0 CLI context is not exact")
        allowlist = tuple(self.product_shadow_context_allowlist)
        if allowlist != SYNTHETIC_D0_SHADOW_CONTEXT_ALLOWLIST:
            raise DockingPipelineError("synthetic D0 shadow allowlist is not exact")
        if type(self.seed) is not int or self.seed != 4301:
            raise DockingPipelineError("synthetic D0 seed is not exact")
        if type(self.candidate_count) is not int or self.candidate_count != 2:
            raise DockingPipelineError("synthetic D0 denominator is not exact")
        if type(self.top_k) is not int or self.top_k != 1:
            raise DockingPipelineError("synthetic D0 Top-K is not exact")
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

    def assert_request(self, request: DockingPipelineRequestV1) -> None:
        if type(request) is not DockingPipelineRequestV1:
            raise TypeError("request must be exact DockingPipelineRequestV1")
        observed = request.to_dict()
        expected = {
            "request_sha256": self.request_sha256,
            "receptor_system_sha256": self.receptor_system_sha256,
            "ligand_system_sha256": self.ligand_system_sha256,
            "pocket_fingerprint_sha256": self.pocket_fingerprint_sha256,
            "profile_receipt_sha256": self.profile_receipt_sha256,
            "seed": self.seed,
        }
        if any(observed.get(key) != value for key, value in expected.items()):
            raise DockingPipelineError(
                "public standalone surfaces admit only the exact repository-owned "
                "synthetic D0 request"
            )
        if (
            request.profile.profile_id != self.profile_id
            or request.profile.candidate_count != self.candidate_count
            or request.profile.top_k != self.top_k
            or request.profile.test_only_profile is not True
            or request.test_only is not True
        ):
            raise DockingPipelineError(
                "public standalone surfaces admit only the exact repository-owned "
                "synthetic D0 profile"
            )


def repository_synthetic_d0_fixture_admission() -> SyntheticD0FixtureAdmissionV1:
    """Load and authenticate the package-owned fixture manifest bytes."""

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
            object_pairs_hook=_reject_duplicate_pairs,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise DockingPipelineError("synthetic D0 fixture manifest is invalid") from exc
    if not isinstance(document, dict) or _canonical_bytes(document) != canonical:
        raise DockingPipelineError("synthetic D0 fixture manifest bytes changed")
    if document.get("schema_id") != SYNTHETIC_D0_FIXTURE_ADMISSION_SCHEMA_ID:
        raise DockingPipelineError("synthetic D0 fixture manifest schema changed")
    authority = document.get("authority")
    if not isinstance(authority, dict) or set(authority) != set(_AUTHORITY_FALSE_FIELDS):
        raise DockingPipelineError("synthetic D0 fixture authority fields changed")
    if any(authority.get(field) is not False for field in _AUTHORITY_FALSE_FIELDS):
        raise DockingPipelineError("synthetic D0 fixture asserted forbidden authority")
    admission = SyntheticD0FixtureAdmissionV1(
        fixture_id=str(document.get("fixture_id", "")),
        manifest_sha256=SYNTHETIC_D0_FIXTURE_MANIFEST_SHA256,
        request_sha256=str(document.get("request_sha256", "")),
        receptor_system_sha256=str(document.get("receptor_system_sha256", "")),
        ligand_system_sha256=str(document.get("ligand_system_sha256", "")),
        pocket_fingerprint_sha256=str(
            document.get("pocket_fingerprint_sha256", "")
        ),
        profile_id=str(document.get("profile_id", "")),
        profile_receipt_sha256=str(document.get("profile_receipt_sha256", "")),
        seed=document.get("seed"),
        candidate_count=document.get("candidate_count"),
        top_k=document.get("top_k"),
        benchmark_scope=str(document.get("benchmark_scope", "")),
        benchmark_case_id=str(document.get("benchmark_case_id", "")),
        python_api_context_id=str(document.get("python_api_context_id", "")),
        cli_context_id=str(document.get("cli_context_id", "")),
        product_shadow_context_allowlist=tuple(
            document.get("product_shadow_context_allowlist", ())
        ),
    )
    if admission.request_sha256 != SYNTHETIC_D0_FIXTURE_REQUEST_SHA256:
        raise DockingPipelineError("synthetic D0 manifest request identity changed")
    return admission


class StandaloneAbstentionReason(str, Enum):
    NOT_ABSTAINED = "not_abstained"
    ALL_CANDIDATES_FAILED = "all_candidates_failed"
    INSUFFICIENT_SELECTION_ELIGIBLE_CANDIDATES = (
        "insufficient_selection_eligible_candidates"
    )


def _surface_policy(surface: ConsumerSurface) -> dict[str, object]:
    if surface not in {"python_api", "benchmark_adapter", "product_shadow", "cli"}:
        raise DockingPipelineError("standalone consumer surface is unsupported")
    return {
        "surface_policy_id": CONSUMER_SURFACE_POLICY_ID,
        "evidence_display_allowed": True,
        "operator_second_opinion_allowed": surface == "product_shadow",
        "existing_rank_auto_change_allowed": False,
        "customer_pose_emission_allowed": False,
        "production_claim_allowed": False,
        "product_state_mutated": False,
    }


def _expected_context(
    surface: ConsumerSurface,
    admission: SyntheticD0FixtureAdmissionV1,
) -> tuple[str, ...]:
    if surface == "python_api":
        return (admission.python_api_context_id,)
    if surface == "benchmark_adapter":
        return (f"{admission.benchmark_scope}:{admission.benchmark_case_id}",)
    if surface == "cli":
        return (admission.cli_context_id,)
    if surface == "product_shadow":
        return admission.product_shadow_context_allowlist
    raise DockingPipelineError("standalone consumer surface is unsupported")


@dataclass(frozen=True, slots=True)
class StandaloneConsumerEnvelopeV1:
    surface: ConsumerSurface
    result: DockingPipelineResultV1 = field(repr=False, compare=False)
    context_id: str
    fixture_admission: SyntheticD0FixtureAdmissionV1 = field(
        repr=False,
        compare=False,
    )
    canonical_component_manifest_sha256: str
    _receipt_sha256: str = field(init=False, repr=False)

    def __post_init__(self) -> None:
        policy = _surface_policy(self.surface)
        if type(self.result) is not DockingPipelineResultV1:
            raise TypeError("result must be exact DockingPipelineResultV1")
        if type(self.fixture_admission) is not SyntheticD0FixtureAdmissionV1:
            raise TypeError(
                "fixture_admission must be exact SyntheticD0FixtureAdmissionV1"
            )
        self.fixture_admission.assert_request(self.result.request)
        context = str(self.context_id or "").strip()
        if context not in _expected_context(self.surface, self.fixture_admission):
            raise DockingPipelineError("standalone consumer context ID is not admitted")
        component_manifest = _require_sha256(
            self.canonical_component_manifest_sha256,
            name="canonical component manifest SHA-256",
        )
        if component_manifest != CANONICAL_COMPONENT_MANIFEST_SHA256:
            raise DockingPipelineError("standalone component manifest is not exact")
        if self.result.component_ids != dict(_CANONICAL_COMPONENT_IDS):
            raise DockingPipelineError("standalone result component graph is not canonical")
        if policy["existing_rank_auto_change_allowed"] is not False:
            raise DockingPipelineError("standalone policy may not change existing rank")
        object.__setattr__(self, "context_id", context)
        object.__setattr__(
            self,
            "canonical_component_manifest_sha256",
            component_manifest,
        )
        object.__setattr__(self, "_receipt_sha256", _sha256(self._projection()))

    @property
    def abstention_reason(self) -> StandaloneAbstentionReason:
        if not self.result.abstained:
            return StandaloneAbstentionReason.NOT_ABSTAINED
        if self.result.failure_count == len(self.result.candidates):
            return StandaloneAbstentionReason.ALL_CANDIDATES_FAILED
        return StandaloneAbstentionReason.INSUFFICIENT_SELECTION_ELIGIBLE_CANDIDATES

    def _candidate_dispositions(self) -> list[dict[str, object]]:
        top_indices = set(self.result.top_proposal_indices)
        rows: list[dict[str, object]] = []
        for candidate in self.result.candidates:
            in_top_k = candidate.proposal_index in top_indices
            if candidate.status != "success":
                disposition = "retained_failure"
            elif in_top_k:
                disposition = "selected_top_k_evidence_only"
            elif not candidate.selection_eligible:
                disposition = "retained_ineligible_not_selected"
            else:
                disposition = "retained_eligible_not_selected"
            rows.append(
                {
                    "candidate_id": candidate.candidate_id,
                    "proposal_index": candidate.proposal_index,
                    "candidate_evidence_sha256": _sha256(candidate.to_dict()),
                    "status": candidate.status,
                    "error_code": candidate.error_code,
                    "selection_eligible": candidate.selection_eligible,
                    "in_top_k": in_top_k,
                    "disposition": disposition,
                    "candidate_removed_from_denominator": False,
                    "existing_rank_changed": False,
                    "customer_pose_emitted": False,
                    "product_state_mutated": False,
                    "claim_safe": False,
                }
            )
        return rows

    def _projection(self) -> dict[str, object]:
        policy = _surface_policy(self.surface)
        failures = Counter(
            row.error_code
            for row in self.result.candidates
            if row.status != "success"
        )
        return {
            "schema_id": CONSUMER_ENVELOPE_SCHEMA_ID,
            "surface": self.surface,
            "context_id": self.context_id,
            "surface_policy_id": policy["surface_policy_id"],
            "fixture_id": self.fixture_admission.fixture_id,
            "fixture_manifest_sha256": self.fixture_admission.manifest_sha256,
            "fixture_request_sha256": self.fixture_admission.request_sha256,
            "fixture_admission_receipt_sha256": (
                self.fixture_admission.receipt_sha256
            ),
            "canonical_component_manifest_sha256": (
                self.canonical_component_manifest_sha256
            ),
            "pipeline_result_receipt_sha256": self.result.receipt_sha256,
            "profile_id": self.result.request.profile.profile_id,
            "candidate_count": len(self.result.candidates),
            "success_count": self.result.success_count,
            "failure_count": self.result.failure_count,
            "failure_summary": {
                "failure_count": self.result.failure_count,
                "failure_codes": dict(sorted(failures.items())),
                "denominator_preserved": True,
            },
            "top_proposal_indices": list(self.result.top_proposal_indices),
            "top_k": {
                "requested_count": self.result.request.profile.top_k,
                "returned_count": len(self.result.top_proposal_indices),
                "proposal_indices": list(self.result.top_proposal_indices),
                "rank_source": "unmodified_canonical_core_receipt",
                "existing_rank_auto_change_allowed": False,
            },
            "abstention": {
                "abstained": self.result.abstained,
                "reason_code": self.abstention_reason.value,
                "requested_top_k": self.result.request.profile.top_k,
                "returned_top_k": len(self.result.top_proposal_indices),
            },
            "candidate_dispositions": self._candidate_dispositions(),
            "blockers": list(self.result.blockers),
            "evidence_display_allowed": policy["evidence_display_allowed"],
            "operator_second_opinion_allowed": policy[
                "operator_second_opinion_allowed"
            ],
            "existing_rank_auto_change_allowed": policy[
                "existing_rank_auto_change_allowed"
            ],
            "customer_pose_emission_allowed": policy[
                "customer_pose_emission_allowed"
            ],
            "production_claim_allowed": policy["production_claim_allowed"],
            "benchmark_dataset_accessed": False,
            "external_reservation_allowed": False,
            "external_reservation_requested": False,
            "molecular_experiment_authorized": False,
            "real_molecular_execution_allowed": False,
            "product_state_mutated": policy["product_state_mutated"],
            "authority": False,
            "claim_safe": False,
        }

    @property
    def receipt_sha256(self) -> str:
        observed = _sha256(self._projection())
        if observed != self._receipt_sha256:
            raise DockingPipelineError("standalone consumer envelope changed")
        return observed

    def to_dict(self, *, include_pipeline_result: bool = True) -> dict[str, object]:
        document = {**self._projection(), "receipt_sha256": self.receipt_sha256}
        if include_pipeline_result:
            document["pipeline_result"] = self.result.to_dict()
        return document


def _run_exact_surface(
    request: DockingPipelineRequestV1,
    *,
    surface: ConsumerSurface,
    context_id: str,
) -> StandaloneConsumerEnvelopeV1:
    admission = repository_synthetic_d0_fixture_admission()
    # Admission precedes factory construction and every molecular computation.
    admission.assert_request(request)
    pipeline = build_canonical_standalone_pipeline()
    result = pipeline.run(request)
    return StandaloneConsumerEnvelopeV1(
        surface=surface,
        result=result,
        context_id=context_id,
        fixture_admission=admission,
        canonical_component_manifest_sha256=(
            CANONICAL_COMPONENT_MANIFEST_SHA256
        ),
    )


class StandaloneDockingPythonApi:
    """Sealed Python API for the exact repository-owned synthetic D0 request."""

    def __init__(self) -> None:
        pass

    def run(
        self,
        request: DockingPipelineRequestV1,
    ) -> StandaloneConsumerEnvelopeV1:
        return _run_exact_surface(
            request,
            surface="python_api",
            context_id=SYNTHETIC_D0_PYTHON_API_CONTEXT_ID,
        )


class StandaloneDiagnosticBenchmarkAdapter:
    """Exact synthetic-D0 adapter with no historical/Fresh/public route."""

    def __init__(self) -> None:
        pass

    def run(
        self,
        request: DockingPipelineRequestV1,
        *,
        scope: str,
        case_id: str,
    ) -> StandaloneConsumerEnvelopeV1:
        if scope != DIAGNOSTIC_BENCHMARK_SCOPE:
            raise DockingPipelineError(
                "benchmark adapter admits only the exact synthetic D0 fixture scope"
            )
        if case_id != SYNTHETIC_D0_BENCHMARK_CASE_ID:
            raise DockingPipelineError(
                "benchmark adapter admits only the exact synthetic D0 fixture case"
            )
        return _run_exact_surface(
            request,
            surface="benchmark_adapter",
            context_id=f"{scope}:{case_id}",
        )


class StandaloneProductShadowAdapter:
    """Allowlisted evidence-only shadow with immutable core rank and no poses."""

    def __init__(self) -> None:
        pass

    def run(
        self,
        request: DockingPipelineRequestV1,
        *,
        operator_context_id: str,
    ) -> StandaloneConsumerEnvelopeV1:
        if operator_context_id not in SYNTHETIC_D0_SHADOW_CONTEXT_ALLOWLIST:
            raise DockingPipelineError("product shadow context is not allowlisted")
        return _run_exact_surface(
            request,
            surface="product_shadow",
            context_id=operator_context_id,
        )


class StandaloneDockingCliAdapter:
    """Sealed CLI adapter returning the same core receipt in an envelope."""

    def __init__(self) -> None:
        pass

    def run(
        self,
        request: DockingPipelineRequestV1,
    ) -> StandaloneConsumerEnvelopeV1:
        return _run_exact_surface(
            request,
            surface="cli",
            context_id=SYNTHETIC_D0_CLI_CONTEXT_ID,
        )


def run_standalone_docking(
    request: DockingPipelineRequestV1,
) -> StandaloneConsumerEnvelopeV1:
    """Run the sealed Python surface and return its claim-blocked envelope."""

    return StandaloneDockingPythonApi().run(request)


__all__ = [
    "CANONICAL_COMPONENT_MANIFEST_SCHEMA_ID",
    "CANONICAL_COMPONENT_MANIFEST_SHA256",
    "CANONICAL_PIPELINE_FACTORY_ID",
    "CONSUMER_ENVELOPE_SCHEMA_ID",
    "CONSUMER_SURFACE_POLICY_ID",
    "DIAGNOSTIC_BENCHMARK_SCOPE",
    "SYNTHETIC_D0_BENCHMARK_CASE_ID",
    "SYNTHETIC_D0_CLI_CONTEXT_ID",
    "SYNTHETIC_D0_FIXTURE_ADMISSION_RECEIPT_SCHEMA_ID",
    "SYNTHETIC_D0_FIXTURE_ADMISSION_SCHEMA_ID",
    "SYNTHETIC_D0_FIXTURE_ID",
    "SYNTHETIC_D0_FIXTURE_MANIFEST_SHA256",
    "SYNTHETIC_D0_FIXTURE_REQUEST_SHA256",
    "SYNTHETIC_D0_PYTHON_API_CONTEXT_ID",
    "SYNTHETIC_D0_SHADOW_CONTEXT_ALLOWLIST",
    "StandaloneAbstentionReason",
    "StandaloneConsumerEnvelopeV1",
    "StandaloneDiagnosticBenchmarkAdapter",
    "StandaloneDockingCliAdapter",
    "StandaloneDockingPythonApi",
    "StandaloneProductShadowAdapter",
    "SyntheticD0FixtureAdmissionV1",
    "build_canonical_standalone_pipeline",
    "canonical_standalone_component_manifest",
    "repository_synthetic_d0_fixture_admission",
    "run_standalone_docking",
]

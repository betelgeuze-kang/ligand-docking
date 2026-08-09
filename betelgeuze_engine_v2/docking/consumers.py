"""Claim-blocked consumers over the one sealed synthetic-D0 docking core.

These adapters add surface metadata around an unmodified pipeline receipt.
They do not provide a dependency-injection path, select a different profile,
rewrite ranking, reserve an experiment, or grant product/scientific authority.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
from typing import Literal

from .pipeline import (
    CURRENT_V7_FIXED64_PROFILE_ID,
    SEALED_CANONICAL_COMPONENT_BINDING,
    DockingPipeline,
    DockingPipelineError,
    DockingPipelineRequestV1,
    DockingPipelineResultV1,
    SyntheticD0FixtureAdmissionV1,
    repository_synthetic_d0_fixture_admission,
)


CONSUMER_ENVELOPE_SCHEMA_ID = "betelgeuze.engine_v2_standalone_consumer_envelope/1.2.0"
DIAGNOSTIC_BENCHMARK_SCOPE = "d0_synthetic_test_fixture"
ConsumerSurface = Literal["python_api", "benchmark_adapter", "product_shadow"]

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
    "real_molecular_execution_allowed",
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
        raise DockingPipelineError(
            "standalone consumer evidence is not canonical JSON"
        ) from exc


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _exact_admission_for_request(
    request: DockingPipelineRequestV1,
) -> SyntheticD0FixtureAdmissionV1:
    if type(request) is not DockingPipelineRequestV1:
        raise TypeError("request must be exact DockingPipelineRequestV1")
    admission = repository_synthetic_d0_fixture_admission()
    if (
        type(request.fixture_admission) is not SyntheticD0FixtureAdmissionV1
        or request.fixture_admission.receipt_sha256 != admission.receipt_sha256
        or request.request_sha256 != admission.request_sha256
        or request.profile.profile_id != CURRENT_V7_FIXED64_PROFILE_ID
        or request.profile.candidate_count != 64
        or request.profile.top_k != 5
        or request.test_only is not True
    ):
        raise DockingPipelineError(
            "standalone consumers admit only the exact package-owned "
            "synthetic D0 fixed64 request"
        )
    return admission


def _surface_context(
    admission: SyntheticD0FixtureAdmissionV1,
    *,
    surface: ConsumerSurface,
    context_id: str,
) -> str:
    expected = {
        "python_api": admission.python_api_context_id,
        "benchmark_adapter": (
            f"{admission.benchmark_scope}:{admission.benchmark_case_id}"
        ),
        "product_shadow": admission.product_shadow_context_allowlist[0],
    }[surface]
    if type(context_id) is not str or context_id != expected:
        raise DockingPipelineError(
            f"{surface} context is outside exact synthetic D0 admission"
        )
    return context_id


@dataclass(frozen=True, slots=True)
class StandaloneConsumerEnvelopeV1:
    """Surface receipt that embeds the exact, unmodified core result."""

    surface: ConsumerSurface
    result: DockingPipelineResultV1 = field(repr=False, compare=False)
    context_id: str
    evidence_display_allowed: bool
    operator_second_opinion_allowed: bool
    _receipt_sha256: str = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if self.surface not in {
            "python_api",
            "benchmark_adapter",
            "product_shadow",
        }:
            raise DockingPipelineError("standalone consumer surface is unsupported")
        if type(self.result) is not DockingPipelineResultV1:
            raise TypeError("result must be exact DockingPipelineResultV1")
        admission = _exact_admission_for_request(self.result.request)
        _surface_context(
            admission,
            surface=self.surface,
            context_id=self.context_id,
        )
        if self.result.component_binding_mode != SEALED_CANONICAL_COMPONENT_BINDING:
            raise DockingPipelineError(
                "standalone consumers require the sealed canonical core"
            )
        if (
            len(self.result.candidates) != 64
            or self.result.request.profile.top_k != 5
            or len(self.result.top_proposal_indices) > 5
        ):
            raise DockingPipelineError("standalone consumer denominator changed")
        if self.evidence_display_allowed is not True:
            raise DockingPipelineError("standalone consumers must expose evidence")
        expected_second_opinion = self.surface == "product_shadow"
        if self.operator_second_opinion_allowed is not expected_second_opinion:
            raise DockingPipelineError(
                "operator second-opinion authority is shadow-only"
            )
        self.result.receipt_sha256
        object.__setattr__(self, "_receipt_sha256", _sha256(self._projection()))

    def _projection(self) -> dict[str, object]:
        authority = {name: False for name in _AUTHORITY_FALSE_FIELDS}
        return {
            "schema_id": CONSUMER_ENVELOPE_SCHEMA_ID,
            "surface": self.surface,
            "context_id": self.context_id,
            "pipeline_result_receipt_sha256": self.result.receipt_sha256,
            "profile_id": self.result.request.profile.profile_id,
            "candidate_count": len(self.result.candidates),
            "top_k": self.result.request.profile.top_k,
            "top_proposal_indices": list(self.result.top_proposal_indices),
            "failure_count": self.result.failure_count,
            "abstained": self.result.abstained,
            "blockers": list(self.result.blockers),
            "evidence_display_allowed": self.evidence_display_allowed,
            "operator_second_opinion_allowed": (self.operator_second_opinion_allowed),
            "pipeline_result_embedded_unmodified": True,
            "pipeline_result_rewritten": False,
            "rank_or_selection_rewritten": False,
            "benchmark_dataset_accessed": False,
            "external_reservation_requested": False,
            **authority,
            "authority": False,
            "claim_safe": False,
        }

    @property
    def receipt_sha256(self) -> str:
        observed = _sha256(self._projection())
        if observed != self._receipt_sha256:
            raise DockingPipelineError("standalone consumer envelope changed")
        return observed

    def to_dict(self) -> dict[str, object]:
        document = {**self._projection(), "receipt_sha256": self.receipt_sha256}
        pipeline_result = self.result.to_dict()
        if (
            pipeline_result.get("receipt_sha256")
            != document["pipeline_result_receipt_sha256"]
        ):
            raise DockingPipelineError(
                "standalone consumer core result receipt changed"
            )
        document["pipeline_result"] = pipeline_result
        return document


def _run_exact_surface(
    request: DockingPipelineRequestV1,
    *,
    surface: ConsumerSurface,
    context_id: str,
) -> StandaloneConsumerEnvelopeV1:
    admission = _exact_admission_for_request(request)
    context = _surface_context(
        admission,
        surface=surface,
        context_id=context_id,
    )
    result = DockingPipeline().run(request)
    return StandaloneConsumerEnvelopeV1(
        surface=surface,
        result=result,
        context_id=context,
        evidence_display_allowed=True,
        operator_second_opinion_allowed=surface == "product_shadow",
    )


class StandaloneDockingPythonApi:
    """Exact synthetic-D0 Python surface over ``DockingPipeline().run``."""

    __slots__ = ()

    def run(
        self,
        request: DockingPipelineRequestV1,
    ) -> StandaloneConsumerEnvelopeV1:
        admission = _exact_admission_for_request(request)
        return _run_exact_surface(
            request,
            surface="python_api",
            context_id=admission.python_api_context_id,
        )


class StandaloneDiagnosticBenchmarkAdapter:
    """Exact synthetic D0 case only; no historical, Fresh, or public corpus."""

    __slots__ = ()

    def run(
        self,
        request: DockingPipelineRequestV1,
        *,
        scope: str,
        case_id: str,
    ) -> StandaloneConsumerEnvelopeV1:
        admission = _exact_admission_for_request(request)
        if scope != admission.benchmark_scope or case_id != admission.benchmark_case_id:
            raise DockingPipelineError(
                "benchmark adapter admits only the exact synthetic D0 fixture case"
            )
        return _run_exact_surface(
            request,
            surface="benchmark_adapter",
            context_id=f"{scope}:{case_id}",
        )


class StandaloneProductShadowAdapter:
    """Evidence display and operator second opinion without product mutation."""

    __slots__ = ()

    def run(
        self,
        request: DockingPipelineRequestV1,
        *,
        operator_context_id: str,
    ) -> StandaloneConsumerEnvelopeV1:
        admission = _exact_admission_for_request(request)
        if operator_context_id not in admission.product_shadow_context_allowlist:
            raise DockingPipelineError(
                "product shadow context is outside exact synthetic D0 admission"
            )
        return _run_exact_surface(
            request,
            surface="product_shadow",
            context_id=operator_context_id,
        )


def run_standalone_docking(
    request: DockingPipelineRequestV1,
) -> DockingPipelineResultV1:
    """Return the unwrapped, unmodified exact core receipt."""

    _exact_admission_for_request(request)
    return DockingPipeline().run(request)


__all__ = [
    "CONSUMER_ENVELOPE_SCHEMA_ID",
    "DIAGNOSTIC_BENCHMARK_SCOPE",
    "StandaloneConsumerEnvelopeV1",
    "StandaloneDiagnosticBenchmarkAdapter",
    "StandaloneDockingPythonApi",
    "StandaloneProductShadowAdapter",
    "run_standalone_docking",
]

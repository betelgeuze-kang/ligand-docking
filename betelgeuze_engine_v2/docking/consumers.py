"""Typed standalone consumers that share one claim-blocked docking core."""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
from typing import Literal

from .pipeline import (
    DockingPipeline,
    DockingPipelineError,
    DockingPipelineRequestV1,
    DockingPipelineResultV1,
)


CONSUMER_ENVELOPE_SCHEMA_ID = (
    "betelgeuze.engine_v2_standalone_consumer_envelope/1.0.0"
)
DIAGNOSTIC_BENCHMARK_SCOPE = "d0_synthetic_test_fixture"
ConsumerSurface = Literal["python_api", "benchmark_adapter", "product_shadow"]


def _sha256(value: object) -> str:
    try:
        payload = json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("ascii")
    except (TypeError, ValueError) as exc:
        raise DockingPipelineError("consumer evidence is not canonical JSON") from exc
    return hashlib.sha256(payload).hexdigest()


@dataclass(frozen=True, slots=True)
class StandaloneConsumerEnvelopeV1:
    surface: ConsumerSurface
    result: DockingPipelineResultV1 = field(repr=False, compare=False)
    context_id: str
    evidence_display_allowed: bool
    operator_second_opinion_allowed: bool
    _receipt_sha256: str = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if self.surface not in {"python_api", "benchmark_adapter", "product_shadow"}:
            raise DockingPipelineError("standalone consumer surface is unsupported")
        if type(self.result) is not DockingPipelineResultV1:
            raise TypeError("result must be exact DockingPipelineResultV1")
        context = str(self.context_id or "").strip()
        if not context or len(context) > 256:
            raise DockingPipelineError("standalone consumer context_id is invalid")
        if self.surface == "product_shadow":
            if self.evidence_display_allowed is not True:
                raise DockingPipelineError("product shadow must display evidence")
            if self.operator_second_opinion_allowed is not True:
                raise DockingPipelineError("product shadow must remain a second opinion")
        elif self.operator_second_opinion_allowed is not False:
            raise DockingPipelineError("second-opinion authority belongs only to shadow")
        object.__setattr__(self, "context_id", context)
        object.__setattr__(self, "_receipt_sha256", _sha256(self._projection()))

    def _projection(self) -> dict[str, object]:
        return {
            "schema_id": CONSUMER_ENVELOPE_SCHEMA_ID,
            "surface": self.surface,
            "context_id": self.context_id,
            "pipeline_result_receipt_sha256": self.result.receipt_sha256,
            "profile_id": self.result.request.profile.profile_id,
            "candidate_count": len(self.result.candidates),
            "evidence_display_allowed": self.evidence_display_allowed,
            "operator_second_opinion_allowed": self.operator_second_opinion_allowed,
            "existing_rank_auto_change_allowed": False,
            "customer_pose_emission_allowed": False,
            "production_claim_allowed": False,
            "benchmark_dataset_accessed": False,
            "external_reservation_requested": False,
            "product_state_mutated": False,
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


class StandaloneDockingPythonApi:
    """Direct Python API with the same authority as the underlying test-only core."""

    def __init__(self, pipeline: DockingPipeline | None = None) -> None:
        self.pipeline = pipeline or DockingPipeline()
        if type(self.pipeline) is not DockingPipeline:
            raise TypeError("pipeline must be exact DockingPipeline")

    def run(
        self,
        request: DockingPipelineRequestV1,
        *,
        context_id: str = "standalone-python-api",
    ) -> StandaloneConsumerEnvelopeV1:
        return StandaloneConsumerEnvelopeV1(
            surface="python_api",
            result=self.pipeline.run(request),
            context_id=context_id,
            evidence_display_allowed=True,
            operator_second_opinion_allowed=False,
        )


class StandaloneDiagnosticBenchmarkAdapter:
    """Synthetic D0 adapter that cannot access historical, Fresh, or public data."""

    def __init__(self, pipeline: DockingPipeline | None = None) -> None:
        self.pipeline = pipeline or DockingPipeline()
        if type(self.pipeline) is not DockingPipeline:
            raise TypeError("pipeline must be exact DockingPipeline")

    def run(
        self,
        request: DockingPipelineRequestV1,
        *,
        scope: str,
        case_id: str,
    ) -> StandaloneConsumerEnvelopeV1:
        if scope != DIAGNOSTIC_BENCHMARK_SCOPE:
            raise DockingPipelineError(
                "benchmark adapter admits only the synthetic D0 test fixture"
            )
        if request.profile.test_only_profile is not True:
            raise DockingPipelineError(
                "benchmark adapter requires the bounded synthetic profile"
            )
        return StandaloneConsumerEnvelopeV1(
            surface="benchmark_adapter",
            result=self.pipeline.run(request),
            context_id=f"{scope}:{case_id}",
            evidence_display_allowed=True,
            operator_second_opinion_allowed=False,
        )


class StandaloneProductShadowAdapter:
    """Evidence-only shadow: no rank mutation, pose emission, or product claim."""

    def __init__(self, pipeline: DockingPipeline | None = None) -> None:
        self.pipeline = pipeline or DockingPipeline()
        if type(self.pipeline) is not DockingPipeline:
            raise TypeError("pipeline must be exact DockingPipeline")

    def run(
        self,
        request: DockingPipelineRequestV1,
        *,
        operator_context_id: str,
    ) -> StandaloneConsumerEnvelopeV1:
        if request.profile.test_only_profile is not True:
            raise DockingPipelineError(
                "product shadow remains limited to the synthetic test profile"
            )
        return StandaloneConsumerEnvelopeV1(
            surface="product_shadow",
            result=self.pipeline.run(request),
            context_id=operator_context_id,
            evidence_display_allowed=True,
            operator_second_opinion_allowed=True,
        )


def run_standalone_docking(
    request: DockingPipelineRequestV1,
) -> DockingPipelineResultV1:
    """Small Python convenience API that returns the unmodified core result."""

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

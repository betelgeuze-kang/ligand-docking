"""Machine-verifiable, fail-closed Engine V2 HIP parity contracts.

The verifier operates only on supplied receipts.  It performs no GPU work and
never marks a HIP backend executable or permits an acceleration claim.  A
passing receipt means only that the bounded parity evidence passed every gate
encoded here for one exact GPU architecture.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import hashlib
import json
import math
import re
from typing import Mapping

from .backend_abi import (
    EngineV2Backend,
    EngineV2BackendReceipt,
    HIP_BACKENDS,
    SCORER_V1_TERM_NAMES,
    canonical_backend,
)


GPU_PARITY_EVIDENCE_SCHEMA_ID = "engine-v2-gpu-parity-evidence-v1"
GPU_ARCHITECTURE_QUALIFICATION_SCHEMA_ID = "engine-v2-gpu-architecture-qualification-v1"
GPU_CLAIM_QUALIFICATION_SCHEMA_ID = "engine-v2-gpu-claim-qualification-v1"
PARITY_PROBE_EXECUTION_SCHEMA_ID = "engine-v2-parity-probe-execution-v1"
PARITY_PROBE_EXECUTION_PURPOSE = "qualification_probe_only"
GPU_PARITY_QUALIFICATION_AUTHORITY_BLOCKER = (
    "gpu_parity_artifact_execution_authority_not_implemented"
)

# This is a pre-result governance value, not a caller-selected verifier option.
# A future tolerance change requires a new evidence schema and capability-policy
# version; widening it in response to observed GPU output is deliberately invalid.
SCORER_V1_ABSOLUTE_TOLERANCE = 1.0e-12
SCORER_V1_RELATIVE_TOLERANCE = 0.0

GPU_OOM_FAILURE_CODE = "engine_v2_gpu_oom"
GPU_PAIR_LIST_OVERFLOW_FAILURE_CODE = "engine_v2_gpu_pair_list_overflow"
POSE_VALIDITY_FLAG_NAMES = (
    "chemical_valid",
    "geometric_valid",
    "posebusters_valid",
    "selection_eligible",
)

GATE_DENOMINATOR = "candidate_denominator_identical"
GATE_FAILURE_CODES = "failure_codes_identical"
GATE_SCORER_TERMS = "scorer_v1_eight_terms_within_tolerance"
GATE_VALIDITY = "pose_validity_identical"
GATE_TOP1 = "top1_identical"
GATE_TOP5 = "top5_identical"
GATE_V7_DECISION = "v7_decision_identical"
GATE_REPEATED_RANK = "repeated_run_rank_stable"
GATE_OOM_FAIL_CLOSED = "oom_fail_closed"
GATE_OVERFLOW_FAIL_CLOSED = "overflow_fail_closed"
GATE_ARCHITECTURE = "exact_architecture_qualified"
GATE_HIP_SAFE_PRECEDENT = "hip_safe_precedes_hip_fast"

_GATE_ORDER = (
    GATE_DENOMINATOR,
    GATE_FAILURE_CODES,
    GATE_SCORER_TERMS,
    GATE_VALIDITY,
    GATE_TOP1,
    GATE_TOP5,
    GATE_V7_DECISION,
    GATE_REPEATED_RANK,
    GATE_OOM_FAIL_CLOSED,
    GATE_OVERFLOW_FAIL_CLOSED,
    GATE_ARCHITECTURE,
    GATE_HIP_SAFE_PRECEDENT,
)

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_HIP_ARCHITECTURE_RE = re.compile(r"^gfx[0-9a-f]+$")
_REASON_CODE_RE = re.compile(r"^[a-z][a-z0-9_.:-]{0,127}$")


class GPUParityError(ValueError):
    """Raised when parity evidence is structurally invalid."""


class FailClosedProbeKind(str, Enum):
    OOM = "oom"
    PAIR_LIST_OVERFLOW = "pair_list_overflow"


def _canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _digest(value: object, *, name: str) -> str:
    normalized = str(value or "").strip().lower()
    if not _SHA256_RE.fullmatch(normalized):
        raise GPUParityError(f"{name} must be a lowercase SHA-256 digest")
    return normalized


def _optional_digest(value: object, *, name: str) -> str:
    normalized = str(value or "").strip().lower()
    return _digest(normalized, name=name) if normalized else ""


def _non_empty(value: object, *, name: str) -> str:
    normalized = str(value or "").strip()
    if not normalized:
        raise GPUParityError(f"{name} must be non-empty")
    return normalized


def _architecture(value: object) -> str:
    normalized = str(value or "").strip().lower()
    if not _HIP_ARCHITECTURE_RE.fullmatch(normalized):
        raise GPUParityError("architecture must be an exact gfx identifier")
    return normalized


@dataclass(frozen=True, slots=True)
class ScorerV1TermTolerance:
    """Predeclared tolerance for all eight ScorerV1 terms."""

    absolute_by_term: Mapping[str, float] | tuple[tuple[str, float], ...]
    relative_tolerance: float = 0.0
    _fingerprint_sha256: str = field(init=False, repr=False)

    def __post_init__(self) -> None:
        try:
            values = dict(self.absolute_by_term)
        except (TypeError, ValueError) as exc:
            raise GPUParityError("absolute_by_term must be a term mapping") from exc
        if set(values) != set(SCORER_V1_TERM_NAMES):
            raise GPUParityError("tolerance must name exactly all eight ScorerV1 terms")
        normalized: list[tuple[str, float]] = []
        for name in SCORER_V1_TERM_NAMES:
            value = float(values[name])
            if not math.isfinite(value) or value < 0.0:
                raise GPUParityError("term tolerances must be finite and non-negative")
            normalized.append((name, value))
        relative = float(self.relative_tolerance)
        if not math.isfinite(relative) or relative < 0.0:
            raise GPUParityError("relative_tolerance must be finite and non-negative")
        if (
            any(value != SCORER_V1_ABSOLUTE_TOLERANCE for _, value in normalized)
            or relative != SCORER_V1_RELATIVE_TOLERANCE
        ):
            raise GPUParityError(
                "ScorerV1 tolerance must equal the frozen pre-result authority policy"
            )
        object.__setattr__(self, "absolute_by_term", tuple(normalized))
        object.__setattr__(self, "relative_tolerance", relative)
        object.__setattr__(self, "_fingerprint_sha256", _sha256(self._projection()))

    @classmethod
    def uniform(
        cls, absolute_tolerance: float, *, relative_tolerance: float = 0.0
    ) -> "ScorerV1TermTolerance":
        return cls(
            absolute_by_term={
                name: absolute_tolerance for name in SCORER_V1_TERM_NAMES
            },
            relative_tolerance=relative_tolerance,
        )

    @classmethod
    def frozen(cls) -> "ScorerV1TermTolerance":
        return cls.uniform(
            SCORER_V1_ABSOLUTE_TOLERANCE,
            relative_tolerance=SCORER_V1_RELATIVE_TOLERANCE,
        )

    def absolute_tolerance(self, name: str) -> float:
        return dict(self.absolute_by_term)[name]

    def _projection(self) -> dict[str, object]:
        return {
            "schema_id": GPU_PARITY_EVIDENCE_SCHEMA_ID,
            "scorer_terms": list(SCORER_V1_TERM_NAMES),
            "absolute_tolerance_binary64_hex_by_term": {
                name: value.hex() for name, value in self.absolute_by_term
            },
            "relative_tolerance_binary64_hex": self.relative_tolerance.hex(),
        }

    @property
    def fingerprint_sha256(self) -> str:
        observed = _sha256(self._projection())
        if observed != self._fingerprint_sha256:
            raise GPUParityError("ScorerV1 tolerance changed")
        return observed

    def to_dict(self) -> dict[str, object]:
        return {**self._projection(), "fingerprint_sha256": self.fingerprint_sha256}


@dataclass(frozen=True, slots=True)
class ParityCandidateEvidence:
    candidate_id: str
    failure_code: str
    scorer_terms: Mapping[str, float] | tuple[tuple[str, float], ...] | None
    pose_valid: bool | None
    v7_decision: str
    validity_flags: Mapping[str, bool] | tuple[tuple[str, bool], ...] | None = None
    validity_reason_codes: tuple[str, ...] | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "candidate_id", _non_empty(self.candidate_id, name="candidate_id")
        )
        failure_code = str(self.failure_code or "").strip()
        object.__setattr__(self, "failure_code", failure_code)
        decision = _non_empty(self.v7_decision, name="v7_decision")
        object.__setattr__(self, "v7_decision", decision)
        if self.pose_valid is not None and not isinstance(self.pose_valid, bool):
            raise TypeError("pose_valid must be bool or None")
        if self.scorer_terms is None:
            normalized_terms = None
        else:
            try:
                values = dict(self.scorer_terms)
            except (TypeError, ValueError) as exc:
                raise GPUParityError("scorer_terms must be a term mapping") from exc
            if set(values) != set(SCORER_V1_TERM_NAMES):
                raise GPUParityError(
                    "candidate evidence must contain exactly eight ScorerV1 terms"
                )
            normalized: list[tuple[str, float]] = []
            for name in SCORER_V1_TERM_NAMES:
                value = float(values[name])
                if not math.isfinite(value):
                    raise GPUParityError("ScorerV1 terms must be finite")
                normalized.append((name, value))
            normalized_terms = tuple(normalized)
        object.__setattr__(self, "scorer_terms", normalized_terms)
        if not failure_code:
            if normalized_terms is None or self.pose_valid is None:
                raise GPUParityError(
                    "successful candidate requires complete score terms and validity"
                )
            try:
                raw_flags = dict(self.validity_flags or {})
            except (TypeError, ValueError) as exc:
                raise GPUParityError("validity_flags must be a mapping") from exc
            if set(raw_flags) != set(POSE_VALIDITY_FLAG_NAMES) or any(
                type(raw_flags[name]) is not bool for name in POSE_VALIDITY_FLAG_NAMES
            ):
                raise GPUParityError(
                    "successful candidate requires the exact four validity flags"
                )
            normalized_flags = tuple(
                (name, raw_flags[name]) for name in POSE_VALIDITY_FLAG_NAMES
            )
            raw_reasons = self.validity_reason_codes
            if not isinstance(raw_reasons, tuple):
                raise GPUParityError("validity_reason_codes must be an exact tuple")
            normalized_reasons = tuple(
                str(value or "").strip() for value in raw_reasons
            )
            if (
                normalized_reasons != raw_reasons
                or normalized_reasons != tuple(sorted(normalized_reasons))
                or len(normalized_reasons) != len(set(normalized_reasons))
                or any(
                    _REASON_CODE_RE.fullmatch(value) is None
                    for value in normalized_reasons
                )
                or self.pose_valid is not all(value for _, value in normalized_flags)
                or bool(normalized_reasons) is self.pose_valid
            ):
                raise GPUParityError(
                    "candidate aggregate validity, flags, and reason codes are inconsistent"
                )
            object.__setattr__(self, "validity_flags", normalized_flags)
            object.__setattr__(self, "validity_reason_codes", normalized_reasons)
        if failure_code and (
            normalized_terms is not None
            or self.pose_valid is not None
            or self.validity_flags is not None
            or self.validity_reason_codes is not None
        ):
            raise GPUParityError(
                "failed candidate cannot claim score terms or pose validity"
            )

    @property
    def succeeded(self) -> bool:
        return not self.failure_code

    def term_dict(self) -> dict[str, float] | None:
        return dict(self.scorer_terms) if self.scorer_terms is not None else None

    def validity_identity(self) -> tuple[object, object, object]:
        return (
            self.pose_valid,
            self.validity_flags,
            self.validity_reason_codes,
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "candidate_id": self.candidate_id,
            "failure_code": self.failure_code,
            "scorer_terms_binary64_hex": (
                {name: value.hex() for name, value in self.scorer_terms}
                if self.scorer_terms is not None
                else None
            ),
            "pose_valid": self.pose_valid,
            "validity_flags": (
                dict(self.validity_flags) if self.validity_flags is not None else None
            ),
            "validity_reason_codes": (
                list(self.validity_reason_codes)
                if self.validity_reason_codes is not None
                else None
            ),
            "v7_decision": self.v7_decision,
        }


@dataclass(frozen=True, slots=True)
class ParityProbeExecutionReceipt:
    """Typed, non-product execution binding for one qualification probe."""

    backend_receipt: EngineV2BackendReceipt
    input_candidate_set_receipt_sha256: str
    runner_execution_receipt_sha256: str
    purpose: str = PARITY_PROBE_EXECUTION_PURPOSE
    customer_execution_allowed: bool = False
    production_execution_allowed: bool = False
    result_substitution_allowed: bool = False
    _receipt_sha256: str = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if not isinstance(self.backend_receipt, EngineV2BackendReceipt):
            raise TypeError("backend_receipt must be EngineV2BackendReceipt")
        for name in (
            "input_candidate_set_receipt_sha256",
            "runner_execution_receipt_sha256",
        ):
            object.__setattr__(self, name, _digest(getattr(self, name), name=name))
        purpose = _non_empty(self.purpose, name="parity probe purpose")
        object.__setattr__(self, "purpose", purpose)
        if purpose != PARITY_PROBE_EXECUTION_PURPOSE:
            raise GPUParityError("parity execution is qualification-probe-only")
        for name in (
            "customer_execution_allowed",
            "production_execution_allowed",
            "result_substitution_allowed",
        ):
            if not isinstance(getattr(self, name), bool):
                raise TypeError(f"{name} must be bool")
            if getattr(self, name):
                raise GPUParityError(
                    "parity probe cannot authorize customer, production, or result use"
                )
        object.__setattr__(self, "_receipt_sha256", _sha256(self._projection()))

    @property
    def backend(self) -> EngineV2Backend:
        return self.backend_receipt.backend

    @property
    def architecture(self) -> str:
        return self.backend_receipt.architecture

    def source_profile_key(self) -> tuple[str, str, str, str, str]:
        source = self.backend_receipt.source_binding
        return (
            source.exact_source_receipt_sha256,
            source.algorithm_profile_id,
            source.algorithm_profile_sha256,
            source.execution_profile_id,
            source.execution_profile_sha256,
        )

    def _projection(self) -> dict[str, object]:
        source = self.backend_receipt.source_binding
        return {
            "schema_id": PARITY_PROBE_EXECUTION_SCHEMA_ID,
            "purpose": self.purpose,
            "backend": self.backend.value,
            "architecture": self.architecture,
            "backend_receipt_sha256": self.backend_receipt.receipt_sha256,
            "source_binding_receipt_sha256": source.receipt_sha256,
            "exact_source_receipt_sha256": source.exact_source_receipt_sha256,
            "algorithm_profile_id": source.algorithm_profile_id,
            "algorithm_profile_sha256": source.algorithm_profile_sha256,
            "execution_profile_id": source.execution_profile_id,
            "execution_profile_sha256": source.execution_profile_sha256,
            "input_candidate_set_receipt_sha256": (
                self.input_candidate_set_receipt_sha256
            ),
            "runner_execution_receipt_sha256": self.runner_execution_receipt_sha256,
            "customer_execution_allowed": self.customer_execution_allowed,
            "production_execution_allowed": self.production_execution_allowed,
            "result_substitution_allowed": self.result_substitution_allowed,
        }

    @property
    def receipt_sha256(self) -> str:
        observed = _sha256(self._projection())
        if observed != self._receipt_sha256:
            raise GPUParityError("parity probe execution receipt changed")
        return observed

    def to_dict(self) -> dict[str, object]:
        return {
            **self._projection(),
            "backend_receipt": self.backend_receipt.to_dict(),
            "receipt_sha256": self.receipt_sha256,
        }


@dataclass(frozen=True, slots=True)
class ParityRunEvidence:
    run_id: str
    probe_execution: ParityProbeExecutionReceipt
    candidates: tuple[ParityCandidateEvidence, ...]
    ranked_candidate_ids: tuple[str, ...]
    _receipt_sha256: str = field(init=False, repr=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "run_id", _non_empty(self.run_id, name="run_id"))
        if not isinstance(self.probe_execution, ParityProbeExecutionReceipt):
            raise TypeError("probe_execution must be ParityProbeExecutionReceipt")
        candidates = tuple(self.candidates)
        if not candidates or any(
            not isinstance(value, ParityCandidateEvidence) for value in candidates
        ):
            raise GPUParityError("run requires candidate evidence")
        candidate_ids = tuple(value.candidate_id for value in candidates)
        if len(candidate_ids) != len(set(candidate_ids)):
            raise GPUParityError("candidate IDs must be unique within a run")
        object.__setattr__(self, "candidates", candidates)
        ranked = tuple(str(value or "").strip() for value in self.ranked_candidate_ids)
        if any(not value for value in ranked) or len(ranked) != len(set(ranked)):
            raise GPUParityError("ranked candidate IDs must be unique and non-empty")
        successful = {value.candidate_id for value in candidates if value.succeeded}
        if set(ranked) != successful:
            raise GPUParityError(
                "ranked candidate IDs must equal the successful candidate set"
            )
        object.__setattr__(self, "ranked_candidate_ids", ranked)
        object.__setattr__(self, "_receipt_sha256", _sha256(self._projection()))

    @property
    def backend_receipt(self) -> EngineV2BackendReceipt:
        return self.probe_execution.backend_receipt

    @property
    def backend(self) -> EngineV2Backend:
        return self.probe_execution.backend

    @property
    def backend_receipt_sha256(self) -> str:
        return self.backend_receipt.receipt_sha256

    @property
    def architecture(self) -> str:
        return self.probe_execution.architecture

    def candidate_map(self) -> dict[str, ParityCandidateEvidence]:
        return {value.candidate_id: value for value in self.candidates}

    def _projection(self) -> dict[str, object]:
        return {
            "schema_id": GPU_PARITY_EVIDENCE_SCHEMA_ID,
            "run_id": self.run_id,
            "backend": self.backend.value,
            "backend_receipt_sha256": self.backend_receipt_sha256,
            "architecture": self.architecture,
            "probe_execution_receipt_sha256": self.probe_execution.receipt_sha256,
            "candidates": [value.to_dict() for value in self.candidates],
            "ranked_candidate_ids": list(self.ranked_candidate_ids),
        }

    @property
    def receipt_sha256(self) -> str:
        observed = _sha256(self._projection())
        if observed != self._receipt_sha256:
            raise GPUParityError("parity run evidence changed")
        return observed

    def to_dict(self) -> dict[str, object]:
        return {
            **self._projection(),
            "probe_execution": self.probe_execution.to_dict(),
            "receipt_sha256": self.receipt_sha256,
        }


@dataclass(frozen=True, slots=True)
class FailClosedProbeEvidence:
    kind: FailClosedProbeKind
    probe_execution: ParityProbeExecutionReceipt
    trigger_observed: bool
    failure_code: str
    partial_results_emitted: bool
    implicit_fallback_used: bool
    _receipt_sha256: str = field(init=False, repr=False)

    def __post_init__(self) -> None:
        kind = self.kind
        if isinstance(kind, str):
            try:
                kind = FailClosedProbeKind(kind)
            except ValueError as exc:
                raise GPUParityError("unsupported fail-closed probe kind") from exc
            object.__setattr__(self, "kind", kind)
        if not isinstance(kind, FailClosedProbeKind):
            raise TypeError("kind must be FailClosedProbeKind")
        if not isinstance(self.probe_execution, ParityProbeExecutionReceipt):
            raise TypeError("probe_execution must be ParityProbeExecutionReceipt")
        if self.probe_execution.backend not in HIP_BACKENDS:
            raise GPUParityError("fail-closed probes require a HIP backend receipt")
        for name in (
            "trigger_observed",
            "partial_results_emitted",
            "implicit_fallback_used",
        ):
            if not isinstance(getattr(self, name), bool):
                raise TypeError(f"{name} must be bool")
        object.__setattr__(
            self, "failure_code", _non_empty(self.failure_code, name="failure_code")
        )
        object.__setattr__(self, "_receipt_sha256", _sha256(self._projection()))

    @property
    def passes(self) -> bool:
        expected = {
            FailClosedProbeKind.OOM: GPU_OOM_FAILURE_CODE,
            FailClosedProbeKind.PAIR_LIST_OVERFLOW: (
                GPU_PAIR_LIST_OVERFLOW_FAILURE_CODE
            ),
        }[self.kind]
        return (
            self.trigger_observed
            and self.failure_code == expected
            and not self.partial_results_emitted
            and not self.implicit_fallback_used
        )

    def _projection(self) -> dict[str, object]:
        return {
            "kind": self.kind.value,
            "probe_execution_receipt_sha256": self.probe_execution.receipt_sha256,
            "trigger_observed": self.trigger_observed,
            "failure_code": self.failure_code,
            "partial_results_emitted": self.partial_results_emitted,
            "implicit_fallback_used": self.implicit_fallback_used,
            "passes": self.passes,
        }

    @property
    def receipt_sha256(self) -> str:
        observed = _sha256(self._projection())
        if observed != self._receipt_sha256:
            raise GPUParityError("fail-closed probe evidence changed")
        return observed

    def to_dict(self) -> dict[str, object]:
        return {
            **self._projection(),
            "probe_execution": self.probe_execution.to_dict(),
            "receipt_sha256": self.receipt_sha256,
        }


@dataclass(frozen=True, slots=True)
class GPUArchitectureParityEvidence:
    expected_candidate_denominator: int
    reference_run: ParityRunEvidence
    gpu_runs: tuple[ParityRunEvidence, ...]
    term_tolerance: ScorerV1TermTolerance
    oom_probe: FailClosedProbeEvidence
    overflow_probe: FailClosedProbeEvidence
    hip_safe_qualification_receipt_sha256: str = ""
    _evidence_sha256: str = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if isinstance(self.expected_candidate_denominator, bool) or not isinstance(
            self.expected_candidate_denominator, int
        ):
            raise TypeError("expected_candidate_denominator must be an integer")
        if self.expected_candidate_denominator <= 0:
            raise GPUParityError("expected_candidate_denominator must be positive")
        if not isinstance(self.reference_run, ParityRunEvidence):
            raise TypeError("reference_run must be ParityRunEvidence")
        if self.reference_run.backend not in {
            EngineV2Backend.PYTHON_REFERENCE,
            EngineV2Backend.RUST_CPU,
        }:
            raise GPUParityError("reference run requires a CPU backend receipt")
        runs = tuple(self.gpu_runs)
        if not runs or any(not isinstance(value, ParityRunEvidence) for value in runs):
            raise GPUParityError("gpu_runs must contain parity run evidence")
        object.__setattr__(self, "gpu_runs", runs)
        if any(value.backend not in HIP_BACKENDS for value in runs):
            raise GPUParityError("GPU runs require hip_safe or hip_fast receipts")
        if len({value.backend for value in runs}) != 1:
            raise GPUParityError("GPU runs must use one exact backend")
        if len({value.architecture for value in runs}) != 1:
            raise GPUParityError("GPU runs must use one exact architecture")
        if len({value.backend_receipt_sha256 for value in runs}) != 1:
            raise GPUParityError("GPU runs must use one exact backend receipt")
        source_profile_keys = {
            value.probe_execution.source_profile_key()
            for value in (self.reference_run, *runs)
        }
        if len(source_profile_keys) != 1:
            raise GPUParityError(
                "reference and GPU runs must share exact source and profiles"
            )
        input_receipts = {
            value.probe_execution.input_candidate_set_receipt_sha256
            for value in (self.reference_run, *runs)
        }
        if len(input_receipts) != 1:
            raise GPUParityError(
                "reference and GPU runs must share one input candidate set"
            )
        if not isinstance(self.term_tolerance, ScorerV1TermTolerance):
            raise TypeError("term_tolerance must be ScorerV1TermTolerance")
        if not isinstance(self.oom_probe, FailClosedProbeEvidence):
            raise TypeError("oom_probe must be FailClosedProbeEvidence")
        if not isinstance(self.overflow_probe, FailClosedProbeEvidence):
            raise TypeError("overflow_probe must be FailClosedProbeEvidence")
        for probe in (self.oom_probe, self.overflow_probe):
            execution = probe.probe_execution
            if (
                execution.backend_receipt.receipt_sha256
                != runs[0].backend_receipt_sha256
                or execution.architecture != runs[0].architecture
                or execution.source_profile_key()
                != runs[0].probe_execution.source_profile_key()
            ):
                raise GPUParityError(
                    "fail-closed probes must bind the exact GPU backend/source/profile"
                )
        execution_receipts = tuple(
            value.probe_execution.runner_execution_receipt_sha256
            for value in (self.reference_run, *runs)
        ) + (
            self.oom_probe.probe_execution.runner_execution_receipt_sha256,
            self.overflow_probe.probe_execution.runner_execution_receipt_sha256,
        )
        if len(execution_receipts) != len(set(execution_receipts)):
            raise GPUParityError(
                "parity runs and fail-closed probes require distinct executions"
            )
        object.__setattr__(
            self,
            "hip_safe_qualification_receipt_sha256",
            _optional_digest(
                self.hip_safe_qualification_receipt_sha256,
                name="hip_safe_qualification_receipt_sha256",
            ),
        )
        backend_safe_receipt = runs[
            0
        ].backend_receipt.hip_safe_qualification_receipt_sha256
        if self.backend is EngineV2Backend.HIP_SAFE:
            if self.hip_safe_qualification_receipt_sha256 or backend_safe_receipt:
                raise GPUParityError("hip_safe evidence cannot claim a safe precedent")
        elif (
            not self.hip_safe_qualification_receipt_sha256
            or self.hip_safe_qualification_receipt_sha256 != backend_safe_receipt
        ):
            raise GPUParityError(
                "hip_fast evidence must bind its backend receipt safe precedent"
            )
        object.__setattr__(self, "_evidence_sha256", _sha256(self._projection()))

    @property
    def backend(self) -> EngineV2Backend:
        return self.gpu_runs[0].backend

    @property
    def architecture(self) -> str:
        return self.gpu_runs[0].architecture

    def _projection(self) -> dict[str, object]:
        return {
            "schema_id": GPU_PARITY_EVIDENCE_SCHEMA_ID,
            "backend": self.backend.value,
            "architecture": self.architecture,
            "expected_candidate_denominator": self.expected_candidate_denominator,
            "reference_run_receipt_sha256": self.reference_run.receipt_sha256,
            "gpu_run_receipt_sha256": [value.receipt_sha256 for value in self.gpu_runs],
            "term_tolerance_fingerprint_sha256": (
                self.term_tolerance.fingerprint_sha256
            ),
            "oom_probe": self.oom_probe.to_dict(),
            "overflow_probe": self.overflow_probe.to_dict(),
            "hip_safe_qualification_receipt_sha256": (
                self.hip_safe_qualification_receipt_sha256
            ),
        }

    @property
    def evidence_sha256(self) -> str:
        observed = _sha256(self._projection())
        if observed != self._evidence_sha256:
            raise GPUParityError("GPU architecture parity evidence changed")
        return observed

    def to_dict(self) -> dict[str, object]:
        return {**self._projection(), "evidence_sha256": self.evidence_sha256}


@dataclass(frozen=True, slots=True)
class GPUArchitectureQualificationReceipt:
    backend: EngineV2Backend
    architecture: str
    evidence_sha256: str
    gate_results: tuple[tuple[str, bool], ...]
    blockers: tuple[str, ...]
    parity_qualified: bool
    backend_execution_available: bool = False
    acceleration_claim_allowed: bool = False
    _receipt_sha256: str = field(init=False, repr=False)

    def __post_init__(self) -> None:
        backend = canonical_backend(self.backend)
        if backend not in HIP_BACKENDS:
            raise GPUParityError("architecture receipt requires a HIP backend")
        object.__setattr__(self, "backend", backend)
        object.__setattr__(self, "architecture", _architecture(self.architecture))
        object.__setattr__(
            self,
            "evidence_sha256",
            _digest(self.evidence_sha256, name="evidence_sha256"),
        )
        gates = tuple(self.gate_results)
        if tuple(name for name, _ in gates) != _GATE_ORDER:
            raise GPUParityError("qualification receipt has incomplete gate order")
        if any(not isinstance(value, bool) for _, value in gates):
            raise TypeError("gate results must be bool")
        object.__setattr__(self, "gate_results", gates)
        blockers = tuple(str(value or "").strip() for value in self.blockers)
        if any(not value for value in blockers) or len(blockers) != len(set(blockers)):
            raise GPUParityError("blockers must be unique non-empty strings")
        object.__setattr__(self, "blockers", blockers)
        if self.parity_qualified:
            raise GPUParityError(
                "this contract cannot issue GPU architecture qualification"
            )
        if GPU_PARITY_QUALIFICATION_AUTHORITY_BLOCKER not in blockers:
            raise GPUParityError("qualification authority blocker is required")
        failed_gate_blockers = {
            f"gpu_parity_gate_failed:{name}" for name, passed in gates if not passed
        }
        if not failed_gate_blockers.issubset(blockers):
            raise GPUParityError("failed parity gates require explicit blockers")
        if self.backend_execution_available or self.acceleration_claim_allowed:
            raise GPUParityError(
                "HIP execution and acceleration claims remain disabled in this phase"
            )
        object.__setattr__(self, "_receipt_sha256", _sha256(self._projection()))

    def _projection(self) -> dict[str, object]:
        return {
            "schema_id": GPU_ARCHITECTURE_QUALIFICATION_SCHEMA_ID,
            "backend": self.backend.value,
            "architecture": self.architecture,
            "evidence_sha256": self.evidence_sha256,
            "gate_results": dict(self.gate_results),
            "blockers": list(self.blockers),
            "parity_qualified": self.parity_qualified,
            "parity_gates_passed": all(value for _, value in self.gate_results),
            "backend_execution_available": self.backend_execution_available,
            "acceleration_claim_allowed": self.acceleration_claim_allowed,
        }

    @property
    def receipt_sha256(self) -> str:
        observed = _sha256(self._projection())
        if observed != self._receipt_sha256:
            raise GPUParityError("GPU architecture qualification receipt changed")
        return observed

    def to_dict(self) -> dict[str, object]:
        return {**self._projection(), "receipt_sha256": self.receipt_sha256}


def _terms_match(
    reference: ParityCandidateEvidence,
    observed: ParityCandidateEvidence,
    tolerance: ScorerV1TermTolerance,
) -> bool:
    reference_terms = reference.term_dict()
    observed_terms = observed.term_dict()
    if reference_terms is None or observed_terms is None:
        return reference_terms is None and observed_terms is None
    return all(
        math.isclose(
            observed_terms[name],
            reference_terms[name],
            rel_tol=tolerance.relative_tolerance,
            abs_tol=tolerance.absolute_tolerance(name),
        )
        for name in SCORER_V1_TERM_NAMES
    )


def verify_gpu_architecture_qualification(
    evidence: GPUArchitectureParityEvidence,
    *,
    hip_safe_qualification: GPUArchitectureQualificationReceipt | None = None,
) -> GPUArchitectureQualificationReceipt:
    """Verify all parity gates for one exact GPU architecture.

    Evidence mismatches become explicit blockers.  Structurally malformed
    objects raise :class:`GPUParityError`, which is also fail-closed because no
    qualification receipt is produced.
    """

    if not isinstance(evidence, GPUArchitectureParityEvidence):
        raise TypeError("evidence must be GPUArchitectureParityEvidence")
    reference = evidence.reference_run
    gpu_runs = evidence.gpu_runs
    reference_map = reference.candidate_map()
    reference_ids = set(reference_map)

    run_ids = tuple(value.run_id for value in gpu_runs)
    runner_execution_receipts = tuple(
        value.probe_execution.runner_execution_receipt_sha256 for value in gpu_runs
    )
    probe_execution_receipts = tuple(
        value.probe_execution.receipt_sha256 for value in gpu_runs
    )
    denominator_ok = len(
        reference.candidates
    ) == evidence.expected_candidate_denominator and all(
        len(value.candidates) == evidence.expected_candidate_denominator
        and set(value.candidate_map()) == reference_ids
        for value in gpu_runs
    )
    failure_codes_ok = denominator_ok and all(
        all(
            run.candidate_map()[candidate_id].failure_code
            == reference_map[candidate_id].failure_code
            for candidate_id in reference_ids
        )
        for run in gpu_runs
    )
    terms_ok = denominator_ok and all(
        all(
            _terms_match(
                reference_map[candidate_id],
                run.candidate_map()[candidate_id],
                evidence.term_tolerance,
            )
            for candidate_id in reference_ids
        )
        for run in gpu_runs
    )
    validity_ok = denominator_ok and all(
        all(
            run.candidate_map()[candidate_id].validity_identity()
            == reference_map[candidate_id].validity_identity()
            for candidate_id in reference_ids
        )
        for run in gpu_runs
    )
    top1_ok = all(
        run.ranked_candidate_ids[:1] == reference.ranked_candidate_ids[:1]
        for run in gpu_runs
    )
    top5_ok = all(
        run.ranked_candidate_ids[:5] == reference.ranked_candidate_ids[:5]
        for run in gpu_runs
    )
    v7_ok = denominator_ok and all(
        all(
            run.candidate_map()[candidate_id].v7_decision
            == reference_map[candidate_id].v7_decision
            for candidate_id in reference_ids
        )
        for run in gpu_runs
    )
    repeated_rank_ok = (
        len(gpu_runs) >= 2
        and len(run_ids) == len(set(run_ids))
        and len(runner_execution_receipts) == len(set(runner_execution_receipts))
        and len(probe_execution_receipts) == len(set(probe_execution_receipts))
        and all(
            run.ranked_candidate_ids == gpu_runs[0].ranked_candidate_ids
            for run in gpu_runs[1:]
        )
    )
    oom_ok = (
        evidence.oom_probe.kind is FailClosedProbeKind.OOM and evidence.oom_probe.passes
    )
    overflow_ok = (
        evidence.overflow_probe.kind is FailClosedProbeKind.PAIR_LIST_OVERFLOW
        and evidence.overflow_probe.passes
    )
    architecture_ok = (
        reference.backend
        in {EngineV2Backend.PYTHON_REFERENCE, EngineV2Backend.RUST_CPU}
        and all(run.backend is evidence.backend for run in gpu_runs)
        and all(run.architecture == evidence.architecture for run in gpu_runs)
        and len({run.backend_receipt_sha256 for run in gpu_runs}) == 1
    )
    safe_precedent_ok = (
        evidence.backend is EngineV2Backend.HIP_SAFE
        and not evidence.hip_safe_qualification_receipt_sha256
        and hip_safe_qualification is None
    ) or (
        evidence.backend is EngineV2Backend.HIP_FAST
        and isinstance(hip_safe_qualification, GPUArchitectureQualificationReceipt)
        and hip_safe_qualification.backend is EngineV2Backend.HIP_SAFE
        and hip_safe_qualification.architecture == evidence.architecture
        and hip_safe_qualification.parity_qualified
        and hip_safe_qualification.receipt_sha256
        == evidence.hip_safe_qualification_receipt_sha256
    )

    results = {
        GATE_DENOMINATOR: denominator_ok,
        GATE_FAILURE_CODES: failure_codes_ok,
        GATE_SCORER_TERMS: terms_ok,
        GATE_VALIDITY: validity_ok,
        GATE_TOP1: top1_ok,
        GATE_TOP5: top5_ok,
        GATE_V7_DECISION: v7_ok,
        GATE_REPEATED_RANK: repeated_rank_ok,
        GATE_OOM_FAIL_CLOSED: oom_ok,
        GATE_OVERFLOW_FAIL_CLOSED: overflow_ok,
        GATE_ARCHITECTURE: architecture_ok,
        GATE_HIP_SAFE_PRECEDENT: safe_precedent_ok,
    }
    gates = tuple((name, bool(results[name])) for name in _GATE_ORDER)
    gate_blockers = tuple(
        f"gpu_parity_gate_failed:{name}" for name, passed in gates if not passed
    )
    blockers = (*gate_blockers, GPU_PARITY_QUALIFICATION_AUTHORITY_BLOCKER)
    return GPUArchitectureQualificationReceipt(
        backend=evidence.backend,
        architecture=evidence.architecture,
        evidence_sha256=evidence.evidence_sha256,
        gate_results=gates,
        blockers=blockers,
        parity_qualified=False,
        backend_execution_available=False,
        acceleration_claim_allowed=False,
    )


@dataclass(frozen=True, slots=True)
class GPUClaimQualificationReceipt:
    backend: EngineV2Backend
    required_architectures: tuple[str, ...]
    architecture_receipt_sha256: tuple[str, ...]
    blockers: tuple[str, ...]
    all_architectures_parity_qualified: bool
    backend_execution_available: bool = False
    acceleration_claim_allowed: bool = False
    _receipt_sha256: str = field(init=False, repr=False)

    def __post_init__(self) -> None:
        backend = canonical_backend(self.backend)
        if backend not in HIP_BACKENDS:
            raise GPUParityError("GPU claim receipt requires a HIP backend")
        object.__setattr__(self, "backend", backend)
        architectures = tuple(
            _architecture(value) for value in self.required_architectures
        )
        if not architectures or len(architectures) != len(set(architectures)):
            raise GPUParityError("required architectures must be unique and non-empty")
        object.__setattr__(self, "required_architectures", architectures)
        receipts = tuple(
            _digest(value, name="architecture receipt SHA-256")
            for value in self.architecture_receipt_sha256
        )
        object.__setattr__(self, "architecture_receipt_sha256", receipts)
        blockers = tuple(str(value or "").strip() for value in self.blockers)
        if any(not value for value in blockers) or len(blockers) != len(set(blockers)):
            raise GPUParityError("blockers must be unique non-empty strings")
        object.__setattr__(self, "blockers", blockers)
        if self.all_architectures_parity_qualified:
            raise GPUParityError("this contract cannot qualify GPU claim coverage")
        if GPU_PARITY_QUALIFICATION_AUTHORITY_BLOCKER not in blockers:
            raise GPUParityError("qualification authority blocker is required")
        if self.backend_execution_available or self.acceleration_claim_allowed:
            raise GPUParityError(
                "HIP execution and acceleration claims remain disabled in this phase"
            )
        object.__setattr__(self, "_receipt_sha256", _sha256(self._projection()))

    def _projection(self) -> dict[str, object]:
        return {
            "schema_id": GPU_CLAIM_QUALIFICATION_SCHEMA_ID,
            "backend": self.backend.value,
            "required_architectures": list(self.required_architectures),
            "architecture_receipt_sha256": list(self.architecture_receipt_sha256),
            "blockers": list(self.blockers),
            "all_architectures_parity_qualified": (
                self.all_architectures_parity_qualified
            ),
            "backend_execution_available": self.backend_execution_available,
            "acceleration_claim_allowed": self.acceleration_claim_allowed,
        }

    @property
    def receipt_sha256(self) -> str:
        observed = _sha256(self._projection())
        if observed != self._receipt_sha256:
            raise GPUParityError("GPU claim qualification receipt changed")
        return observed

    def to_dict(self) -> dict[str, object]:
        return {**self._projection(), "receipt_sha256": self.receipt_sha256}


def verify_gpu_claim_qualification(
    *,
    backend: EngineV2Backend,
    required_architectures: tuple[str, ...],
    architecture_receipts: tuple[GPUArchitectureQualificationReceipt, ...],
) -> GPUClaimQualificationReceipt:
    """Verify exact per-architecture parity coverage without enabling claims."""

    canonical = canonical_backend(backend)
    if canonical not in HIP_BACKENDS:
        raise GPUParityError("GPU claim verification requires a HIP backend")
    required = tuple(_architecture(value) for value in required_architectures)
    if not required or len(required) != len(set(required)):
        raise GPUParityError("required architectures must be unique and non-empty")
    receipts = tuple(architecture_receipts)
    if any(
        not isinstance(value, GPUArchitectureQualificationReceipt) for value in receipts
    ):
        raise TypeError("architecture_receipts must contain qualification receipts")
    observed = tuple(value.architecture for value in receipts)
    blockers: list[str] = []
    if len(observed) != len(set(observed)):
        blockers.append("duplicate_gpu_architecture_qualification")
    missing = sorted(set(required) - set(observed))
    extra = sorted(set(observed) - set(required))
    blockers.extend(
        f"gpu_architecture_qualification_missing:{value}" for value in missing
    )
    blockers.extend(
        f"unexpected_gpu_architecture_qualification:{value}" for value in extra
    )
    blockers.extend(
        f"gpu_architecture_parity_not_qualified:{value.architecture}"
        for value in receipts
        if value.backend is not canonical or not value.parity_qualified
    )
    unique_blockers = tuple(dict.fromkeys(blockers))
    if GPU_PARITY_QUALIFICATION_AUTHORITY_BLOCKER not in unique_blockers:
        unique_blockers = (
            *unique_blockers,
            GPU_PARITY_QUALIFICATION_AUTHORITY_BLOCKER,
        )
    return GPUClaimQualificationReceipt(
        backend=canonical,
        required_architectures=required,
        architecture_receipt_sha256=tuple(value.receipt_sha256 for value in receipts),
        blockers=unique_blockers,
        all_architectures_parity_qualified=False,
        backend_execution_available=False,
        acceleration_claim_allowed=False,
    )


__all__ = [
    "FailClosedProbeEvidence",
    "FailClosedProbeKind",
    "GPUArchitectureParityEvidence",
    "GPUArchitectureQualificationReceipt",
    "GPUClaimQualificationReceipt",
    "GPUParityError",
    "GPU_OOM_FAILURE_CODE",
    "GPU_PAIR_LIST_OVERFLOW_FAILURE_CODE",
    "GPU_PARITY_QUALIFICATION_AUTHORITY_BLOCKER",
    "GATE_ARCHITECTURE",
    "GATE_DENOMINATOR",
    "GATE_FAILURE_CODES",
    "GATE_HIP_SAFE_PRECEDENT",
    "GATE_OOM_FAIL_CLOSED",
    "GATE_OVERFLOW_FAIL_CLOSED",
    "GATE_REPEATED_RANK",
    "GATE_SCORER_TERMS",
    "GATE_TOP1",
    "GATE_TOP5",
    "GATE_V7_DECISION",
    "GATE_VALIDITY",
    "ParityCandidateEvidence",
    "ParityProbeExecutionReceipt",
    "ParityRunEvidence",
    "PARITY_PROBE_EXECUTION_PURPOSE",
    "PARITY_PROBE_EXECUTION_SCHEMA_ID",
    "SCORER_V1_TERM_NAMES",
    "SCORER_V1_ABSOLUTE_TOLERANCE",
    "SCORER_V1_RELATIVE_TOLERANCE",
    "ScorerV1TermTolerance",
    "verify_gpu_architecture_qualification",
    "verify_gpu_claim_qualification",
]

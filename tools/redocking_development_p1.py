"""Opt-in observation and exact-byte evaluation reuse for development workers.

This module does not import a docking engine or use native poses for search.
The caller owns durable event storage. Evaluation caches live for one case and
are bound to the evaluator identity and exact receptor/reference/pose bytes.
"""

from __future__ import annotations

from contextlib import contextmanager
import hashlib
import json
import math
import re
import time
from typing import Callable, Iterator, Mapping, Sequence

PROFILE = "development_observation_v1"
SCHEMA = "betelgeuze.redocking_development_observation/1.0.0"
EVALUATION_POLICY = "posebusters-0.3.1/redock/full_report/fixed_receptor_frame"


class DevelopmentObservationError(RuntimeError):
    """Observation failed; a worker must not publish a successful receipt."""


def _sha(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _json_copy(payload):
    return json.loads(json.dumps(payload, sort_keys=True, allow_nan=False))


class DevelopmentObservation:
    """One-case sidecar recorder; no changes to numerical selection contracts."""

    profile = PROFILE

    def __init__(
        self,
        case_id: str,
        *,
        event_sink: Callable[[dict], None],
        evaluator_identity: str,
        reuse_evaluations: bool = True,
        reuse_prepared_inputs: bool = True,
    ) -> None:
        if not isinstance(case_id, str) or not re.fullmatch(
            r"[A-Za-z0-9_.-]+", case_id
        ):
            raise DevelopmentObservationError("invalid observation case identity")
        if not callable(event_sink):
            raise DevelopmentObservationError("event sink must be callable")
        if not isinstance(evaluator_identity, str) or not re.fullmatch(
            r"[0-9a-f]{64}", evaluator_identity
        ):
            raise DevelopmentObservationError("evaluator identity must be a SHA256")
        if (
            type(reuse_evaluations) is not bool
            or type(reuse_prepared_inputs) is not bool
        ):
            raise DevelopmentObservationError("reuse options must be boolean")
        self._case_id = case_id
        self._sink = event_sink
        self._evaluator_identity = evaluator_identity
        self._reuse = reuse_evaluations
        self._reuse_prepared = reuse_prepared_inputs
        self._sequence = 0
        self._started = time.perf_counter()
        self._failure: Exception | None = None
        self._core_starts: dict[tuple[str, object], float] = {}
        self._cache: dict[tuple, tuple[bytes, tuple]] = {}
        self._prepared: dict[tuple, tuple] = {}
        self._evaluation_calls = 0
        self._reused_records = 0
        self._prepared_hits = 0
        self._prepared_misses = 0

    @property
    def case_id(self) -> str:
        return self._case_id

    @property
    def evaluator_identity(self) -> str:
        """Expose the immutable cache identity for explicit runner strategies."""
        return self._evaluator_identity

    def assert_case(self, case_id: str) -> None:
        self.assert_healthy()
        if self.case_id != case_id:
            raise DevelopmentObservationError("observation is bound to another case")

    def assert_healthy(self) -> None:
        if self._failure is not None:
            raise DevelopmentObservationError(
                "observation event sink failed"
            ) from self._failure

    def _emit(
        self, stage: str, phase: str, details: Mapping, elapsed: float = 0.0
    ) -> None:
        self.assert_healthy()
        try:
            event = _json_copy(
                {
                    "schema_id": SCHEMA,
                    "profile": PROFILE,
                    "case_id": self.case_id,
                    "sequence": self._sequence + 1,
                    "stage": stage,
                    "phase": phase,
                    "elapsed_seconds": elapsed,
                    "monotonic_elapsed_seconds": time.perf_counter() - self._started,
                    "evaluator_identity": self._evaluator_identity,
                    "details": dict(details),
                }
            )
            self._sink(event)
            self._sequence += 1
        except Exception as exc:
            self._failure = exc
            raise DevelopmentObservationError("observation event sink failed") from exc

    @contextmanager
    def stage(self, name: str, **details) -> Iterator[None]:
        self._emit(name, "start", details)
        started = time.perf_counter()
        try:
            yield
        except BaseException as exc:
            self._emit(
                name,
                "error",
                {**details, "error_type": type(exc).__name__},
                time.perf_counter() - started,
            )
            raise
        else:
            self._emit(name, "complete", details, time.perf_counter() - started)

    def core_event(self, stage: str, phase: str, details: Mapping[str, object]) -> None:
        """Receive copied search evidence; evaluation labels are forbidden here."""
        self.assert_healthy()
        try:
            self._record_core_event(stage, phase, details)
        except Exception as exc:
            if self._failure is None:
                self._failure = exc
            raise

    def _record_core_event(
        self, stage: str, phase: str, details: Mapping[str, object]
    ) -> None:
        def check(value):
            if isinstance(value, Mapping):
                for key, nested in value.items():
                    if (
                        "rmsd" in str(key).lower()
                        or "native" in str(key).lower()
                        or "posebusters" in str(key).lower()
                    ):
                        raise DevelopmentObservationError(
                            "reference evaluation labels are forbidden in search observation"
                        )
                    check(nested)
            elif isinstance(value, (list, tuple)):
                for nested in value:
                    check(nested)

        check(details)
        if phase not in {"start", "complete", "error", "snapshot"}:
            raise DevelopmentObservationError("invalid core observation phase")
        key = (stage, details.get("proposal_index"))
        elapsed = 0.0
        if phase == "start":
            if key in self._core_starts:
                raise DevelopmentObservationError("duplicate core stage start")
            self._core_starts[key] = time.perf_counter()
        elif phase in {"complete", "error"}:
            if key not in self._core_starts:
                raise DevelopmentObservationError(
                    "core stage completion lacks its start"
                )
            elapsed = time.perf_counter() - self._core_starts.pop(key)
        self._emit(stage, phase, details, elapsed)

    def snapshot(self, stage: str, **details) -> None:
        self._emit(stage, "snapshot", details)

    def _context(
        self, native_payload: bytes, receptor_payload: bytes
    ) -> tuple[str, ...]:
        if not isinstance(native_payload, bytes) or not isinstance(
            receptor_payload, bytes
        ):
            raise DevelopmentObservationError("evaluator inputs must be pinned bytes")
        return (
            self._evaluator_identity,
            EVALUATION_POLICY,
            _sha(native_payload),
            _sha(receptor_payload),
        )

    @staticmethod
    def _validated_outcomes(result, count: int) -> tuple:
        if (
            not isinstance(result, tuple)
            or len(result) != 4
            or any(len(column) != count for column in result)
        ):
            raise DevelopmentObservationError("evaluation denominator mismatch")
        rmsds, geometric, chemical, failures = result
        if any(
            type(v) not in (int, float) or not math.isfinite(v) or v < 0 for v in rmsds
        ):
            raise DevelopmentObservationError("invalid evaluation RMSD")
        if any(type(v) is not bool for column in (geometric, chemical) for v in column):
            raise DevelopmentObservationError("invalid evaluation boolean")
        if any(
            not isinstance(row, (tuple, list))
            or any(not isinstance(v, str) or not v for v in row)
            for row in failures
        ):
            raise DevelopmentObservationError("invalid failed-check evidence")
        return (
            tuple(float(v) for v in rmsds),
            tuple(geometric),
            tuple(chemical),
            tuple(tuple(row) for row in failures),
        )

    def evaluate(
        self,
        records: Sequence[bytes],
        *,
        native_payload: bytes,
        receptor_payload: bytes,
        evaluate: Callable[[], tuple],
    ) -> tuple:
        """Reuse a complete record set only; otherwise evaluate the whole batch."""
        self.assert_healthy()
        records = tuple(records)
        if not 1 <= len(records) <= 64 or any(
            not isinstance(r, bytes) or not r.endswith(b"$$$$\n") for r in records
        ):
            raise DevelopmentObservationError("invalid serialized evaluation records")
        context = self._context(native_payload, receptor_payload)
        keys = tuple((*context, _sha(record)) for record in records)
        hits = (
            tuple(self._cache.get(key) for key in keys)
            if self._reuse
            else (None,) * len(records)
        )
        all_hit = all(
            hit is not None and hit[0] == record
            for hit, record in zip(hits, records, strict=True)
        )
        self.snapshot(
            "evaluation_cache_lookup",
            record_count=len(records),
            complete_hit=all_hit,
            record_sha256s=[key[-1] for key in keys],
            native_sha256=context[-2],
            receptor_sha256=context[-1],
        )
        if all_hit:
            result = tuple(tuple(hit[1][i] for hit in hits) for i in range(4))
            self._reused_records += len(records)
            return self._validated_outcomes(result, len(records))
        with self.stage("evaluation_batch", record_count=len(records)):
            result = self._validated_outcomes(evaluate(), len(records))
        self._evaluation_calls += 1
        pending = {}
        if self._reuse:
            for key, record, row in zip(
                keys, records, zip(*result, strict=True), strict=True
            ):
                previous = pending.get(key, self._cache.get(key))
                if previous is not None and previous != (record, row):
                    raise DevelopmentObservationError(
                        "same evaluator bytes produced inconsistent per-pose outcomes"
                    )
                pending[key] = (record, row)
            self._cache.update(pending)
        return result

    def decode_inputs(
        self,
        *,
        native_payload: bytes,
        receptor_payload: bytes,
        decode: Callable,
        clone: Callable,
    ) -> tuple:
        """Retain pristine references and pass fresh object copies to evaluation."""
        self.assert_healthy()
        context = self._context(native_payload, receptor_payload)
        cached = self._prepared.get(context) if self._reuse_prepared else None
        with self.stage(
            "evaluation_input_decode", prepared_reference_hit=cached is not None
        ):
            prepared = (
                None if cached is None else tuple(clone(value) for value in cached)
            )
            predicted, native, receptor = decode(prepared)
            if cached is None:
                self._prepared_misses += 1
                if self._reuse_prepared:
                    self._prepared[context] = (clone(native), clone(receptor))
            else:
                self._prepared_hits += 1
        return predicted, native, receptor

    def summary(self) -> dict:
        return {
            "profile": PROFILE,
            "case_id": self.case_id,
            "evaluator_identity": self._evaluator_identity,
            "evaluation_cache": {
                "evaluation_calls": self._evaluation_calls,
                "reused_records": self._reused_records,
                "cached_records": len(self._cache),
            },
            "prepared_inputs": {
                "cache_hits": self._prepared_hits,
                "cache_misses": self._prepared_misses,
            },
            "emitted_events": self._sequence,
            "healthy": self._failure is None,
            "incomplete_stages": [
                {"stage": stage, "proposal_index": index}
                for stage, index in self._core_starts
            ],
        }

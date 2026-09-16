"""Actual invocation work, separate from reproducible numerical ledger identities.

Durations are inclusive for nested stages and must not be added together.
A caller-owned meter preserves failed-call counts even when the operation raises.
These counters are observations, not CPU-time-equivalent budget weights.
"""
from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy
import hashlib
import time

from betelgeuze_product.reference_minimization_workflow import _read
from .provenance import ResearchError, exact_fields, integer, require_digest

STAGES = frozenset({
    "implementation.verify", "inputs.parse", "inputs.verify_bytes", "comparison.execute",
    "constraint.project", "geometry.build", "force.evaluate", "force.project",
    "restart.verify", "scorer.construct", "context.construct", "search.execute",
    "score.evaluate", "selection.final", "result.verify", "request.publish", "report.publish",
})


class WorkMeter:
    def __init__(self) -> None:
        self._stages: dict[str, dict[str, int]] = {}
        self._counters: dict[str, int] = {}

    @contextmanager
    def measure(self, stage: str):
        if stage not in STAGES:
            raise ResearchError("unknown work observation stage")
        row = self._stages.setdefault(stage, {"calls": 0, "completed": 0, "failed": 0,
                                             "wall_ns": 0, "cpu_ns": 0})
        row["calls"] += 1
        wall, cpu = time.perf_counter_ns(), time.process_time_ns()
        try:
            yield
        except BaseException:
            row["failed"] += 1
            raise
        else:
            row["completed"] += 1
        finally:
            row["wall_ns"] += time.perf_counter_ns() - wall
            row["cpu_ns"] += time.process_time_ns() - cpu

    def add_bytes(self, count: int) -> None:
        count = integer(count, 0, 1_000_000_000)
        self._counters["input_bytes_verified"] = self._counters.get("input_bytes_verified", 0) + count

    def counts(self, stage: str) -> dict[str, int]:
        return deepcopy(self._stages.get(stage, {"calls": 0, "completed": 0, "failed": 0,
                                               "wall_ns": 0, "cpu_ns": 0}))

    def snapshot(self) -> dict:
        return {"schema_id": "cpu_execution_work/1.2.0", "stages": deepcopy(self._stages),
                "counters": dict(self._counters), "durations_are_inclusive": True,
                "timing_is_numerical_identity": False}

    def numerical_calls(self) -> dict:
        force = self.counts("force.evaluate")
        return {"force_evaluation_calls": force["calls"],
                "failed_force_evaluation_calls": force["failed"],
                "restart_verification_calls": self.counts("restart.verify")["calls"],
                "constraint_projection_calls": self.counts("constraint.project")["calls"],
                "work": self.snapshot()}


def verify_admitted_bytes(reference: dict, meter: WorkMeter | None = None) -> int:
    """Re-read ALL bytes of an already parsed/admitted input; never reparse JSON.

    This is NOT an input parser. The initial prepared-input admission is still
    mandatory. The existing bounded, regular-file, no-symlink, before/after
    identity-checked reader is used without weakening any byte/hash check.
    """
    exact_fields(reference, {"path", "sha256"})
    require_digest(reference["sha256"])
    observer = WorkMeter() if meter is None else meter
    if type(observer) is not WorkMeter:
        raise ResearchError("explicit work meter required")
    with observer.measure("inputs.verify_bytes"):
        raw = _read(reference["path"])
        observer.add_bytes(len(raw))
        if hashlib.sha256(raw).hexdigest() != reference["sha256"]:
            raise ResearchError("input_sha256_mismatch")
    return len(raw)

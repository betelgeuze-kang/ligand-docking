"""Observed product refinement work, separate from frozen engine pose receipts.

An objective attempt is a call of an instrumented objective, including a call
that raises. Direction-only geometry work is counted separately. These counts
are not elapsed time, physical E/F calls, or a promise of a global work budget.
"""

from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass, field
from functools import wraps
import hashlib
import json


@dataclass(frozen=True)
class RefinementWorkV1:
    refiner_id: str
    source_proposal_sha256: str
    status: str
    selected_path_steps: int
    objective_attempts: int
    objective_completed: int
    objective_failed: int
    accepted_steps: int
    trial_objective_attempts: int
    direction_evaluations: int
    children: tuple["RefinementWorkV1", ...] = ()
    unknown_counters: tuple[str, ...] = ()

    def __post_init__(self):
        counts = (
            self.selected_path_steps,
            self.objective_attempts,
            self.objective_completed,
            self.objective_failed,
            self.accepted_steps,
            self.trial_objective_attempts,
            self.direction_evaluations,
        )
        if any(type(value) is not int or value < 0 for value in counts):
            raise ValueError("refinement work counts must be nonnegative integers")
        if self.objective_attempts != self.objective_completed + self.objective_failed:
            raise ValueError("objective work denominator mismatch")
        if self.status not in {"success", "failure"}:
            raise ValueError("invalid refinement work status")
        if any(type(child) is not RefinementWorkV1 for child in self.children):
            raise TypeError("typed refinement child work required")
        if tuple(sorted(set(self.unknown_counters))) != self.unknown_counters or any(
            name not in {"accepted_steps", "trial_objective_attempts"}
            for name in self.unknown_counters
        ):
            raise ValueError("invalid unknown refinement work counters")

    def total(self, name: str) -> int:
        """Observed lower bound; use counter_is_complete for an exact total."""
        if name not in {
            "objective_attempts",
            "objective_completed",
            "objective_failed",
            "accepted_steps",
            "trial_objective_attempts",
            "direction_evaluations",
        }:
            raise ValueError("unknown refinement work counter")
        return getattr(self, name) + sum(child.total(name) for child in self.children)

    def counter_is_complete(self, name: str) -> bool:
        self.total(name)  # Validate the requested counter name.
        return name not in self.unknown_counters and all(
            child.counter_is_complete(name) for child in self.children
        )

    def to_dict(self) -> dict:
        counters = (
            "objective_attempts",
            "objective_completed",
            "objective_failed",
            "accepted_steps",
            "trial_objective_attempts",
            "direction_evaluations",
        )
        total_steps = self.total("accepted_steps")
        return {
            "schema_id": "betelgeuze.refinement_work/1.0.0",
            "refiner_id": self.refiner_id,
            "source_proposal_sha256": self.source_proposal_sha256,
            "status": self.status,
            "selected_path_steps": self.selected_path_steps,
            "local": {
                name: None if name in self.unknown_counters else getattr(self, name)
                for name in counters
            },
            "total": {
                name: self.total(name) if self.counter_is_complete(name) else None
                for name in counters
            },
            "known_lower_bounds": {name: self.total(name) for name in counters},
            "unknown_counters": [
                name for name in counters if not self.counter_is_complete(name)
            ],
            "total_work_known": all(
                self.counter_is_complete(name) for name in counters
            ),
            "discarded_path_steps": (
                max(0, total_steps - self.selected_path_steps)
                if self.counter_is_complete("accepted_steps")
                else None
            ),
            "children": [child.to_dict() for child in self.children],
            "budget_semantics": "per_arm_steps_and_selected_path_limit_not_global_objective_limit",
            "physical_energy_force_calls": None,
        }

    @property
    def receipt_sha256(self) -> str:
        return hashlib.sha256(
            json.dumps(
                self.to_dict(), sort_keys=True, separators=(",", ":"), allow_nan=False
            ).encode("ascii")
        ).hexdigest()


@dataclass
class _Frame:
    objective_attempts: int = 0
    objective_completed: int = 0
    objective_failed: int = 0
    accepted_steps: int = 0
    trial_objective_attempts: int = 0
    direction_evaluations: int = 0
    children: list[RefinementWorkV1] = field(default_factory=list)
    unknown_counters: set[str] = field(default_factory=set)


_ACTIVE: ContextVar[_Frame | None] = ContextVar("refinement_work", default=None)


def refinement_work_records(refiner) -> tuple[RefinementWorkV1, ...]:
    """Return immutable records, including failed and repeated invocations."""
    return tuple(getattr(refiner, "_observed_refinement_work", ()))


def track_refinement(method):
    """Observe a synchronous arm without changing its numerical receipt."""

    @wraps(method)
    def wrapped(self, proposal, *, max_steps):
        source = getattr(proposal, "fingerprint_sha256", "")
        parent = _ACTIVE.get()
        frame = _Frame()
        token = _ACTIVE.set(frame)
        status = "failure"
        try:
            result = method(self, proposal, max_steps=max_steps)
            status = "success"
            return result
        finally:
            _ACTIVE.reset(token)
            receipt = (
                getattr(self, "_receipts", {}).get(source, {})
                if status == "success"
                else {}
            )
            work = RefinementWorkV1(
                self.refiner_id,
                source,
                status,
                int(receipt.get("accepted_steps", 0)),
                frame.objective_attempts,
                frame.objective_completed,
                frame.objective_failed,
                frame.accepted_steps,
                frame.trial_objective_attempts,
                frame.direction_evaluations,
                tuple(frame.children),
                tuple(sorted(frame.unknown_counters)),
            )
            if not hasattr(self, "_observed_refinement_work"):
                self._observed_refinement_work = []
            self._observed_refinement_work.append(work)
            if parent is not None:
                parent.children.append(work)

    return wrapped


def count_objective(method):
    @wraps(method)
    def wrapped(*args, **kwargs):
        frame = _ACTIVE.get()
        if frame is not None:
            frame.objective_attempts += 1
        try:
            result = method(*args, **kwargs)
        except BaseException:
            if frame is not None:
                frame.objective_failed += 1
            raise
        if frame is not None:
            frame.objective_completed += 1
        return result

    return wrapped


def count_direction(method):
    @wraps(method)
    def wrapped(*args, **kwargs):
        frame = _ACTIVE.get()
        if frame is not None:
            frame.direction_evaluations += 1
        return method(*args, **kwargs)

    return wrapped


def accepted_refinement_step() -> None:
    frame = _ACTIVE.get()
    if frame is not None:
        frame.accepted_steps += 1


def trial_objective_attempt() -> None:
    frame = _ACTIVE.get()
    if frame is not None:
        frame.trial_objective_attempts += 1


def completed_leaf_steps(receipt) -> None:
    """A completed original leaf receipt reports its whole accepted/trial path."""
    accepted = receipt["accepted_steps"]
    trials = receipt["line_search_evaluation_count"]
    if any(type(value) is not int or value < 0 for value in (accepted, trials)):
        raise ValueError("invalid completed leaf work receipt")
    frame = _ACTIVE.get()
    if frame is not None:
        frame.accepted_steps += accepted
        frame.trial_objective_attempts += trials


def failed_leaf_steps_unknown() -> None:
    """An interrupted original leaf exposes no exact partial step/trial receipt."""
    frame = _ACTIVE.get()
    if frame is not None:
        frame.unknown_counters.update({"accepted_steps", "trial_objective_attempts"})

"""Machine-readable docking score and component provenance contracts."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
import inspect
import json
import math
from numbers import Real
import re
from typing import Any


DOCKING_SCORE_BREAKDOWN_SCHEMA_ID = (
    "betelgeuze.engine_v2_docking_score_breakdown/1.0.0"
)
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class DockingScoringError(ValueError):
    """A docking score or term decomposition violates its explicit contract."""


def _finite_float(value: object, *, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise DockingScoringError(f"{name} must be a finite real number")
    number = float(value)
    if not math.isfinite(number):
        raise DockingScoringError(f"{name} must be finite")
    return number


def _optional_sha256(value: object, *, name: str) -> str:
    if not isinstance(value, str):
        raise DockingScoringError(f"{name} must be a string")
    digest = value.strip().lower()
    if digest and (
        len(digest) != 64
        or any(character not in "0123456789abcdef" for character in digest)
    ):
        raise DockingScoringError(f"{name} must be empty or a lowercase SHA-256")
    return digest


class ScoreDirection(str, Enum):
    MINIMIZE = "minimize"
    MAXIMIZE = "maximize"


@dataclass(frozen=True)
class DockingScoreDescriptor:
    score_id: str
    direction: ScoreDirection
    unit: str | None
    semantics: str
    calibrated: bool
    reference_method: str | None = None
    applicability_domain_id: str = ""

    def __post_init__(self) -> None:
        if not str(self.score_id or "").strip():
            raise ValueError("score_id must be non-empty")
        if not str(self.semantics or "").strip():
            raise ValueError("score semantics must be non-empty")
        if self.calibrated and not self.reference_method:
            raise ValueError("calibrated scores require a reference method")

    def to_dict(self) -> dict[str, object]:
        return {
            "score_id": self.score_id,
            "direction": self.direction.value,
            "unit": self.unit,
            "semantics": self.semantics,
            "calibrated": bool(self.calibrated),
            "reference_method": self.reference_method,
            "applicability_domain_id": self.applicability_domain_id,
        }

    @property
    def fingerprint_sha256(self) -> str:
        return _canonical_sha256(self.to_dict())


@dataclass(frozen=True)
class DockingScoreTerm:
    """One explicit, independently inspectable contribution to a docking score."""

    term_id: str
    raw_value: float
    weight: float
    unit: str | None
    semantics: str
    parameter_source_sha256: str = ""

    def __post_init__(self) -> None:
        term_id = str(self.term_id or "").strip()
        semantics = str(self.semantics or "").strip()
        if not term_id:
            raise DockingScoringError("score term_id must be non-empty")
        if not semantics:
            raise DockingScoringError("score term semantics must be non-empty")
        unit = None if self.unit is None else str(self.unit).strip()
        if unit == "":
            raise DockingScoringError("score term unit must be non-empty or None")
        object.__setattr__(self, "term_id", term_id)
        object.__setattr__(
            self,
            "raw_value",
            _finite_float(self.raw_value, name=f"score term {term_id} raw_value"),
        )
        object.__setattr__(
            self,
            "weight",
            _finite_float(self.weight, name=f"score term {term_id} weight"),
        )
        object.__setattr__(self, "unit", unit)
        object.__setattr__(self, "semantics", semantics)
        object.__setattr__(
            self,
            "parameter_source_sha256",
            _optional_sha256(
                self.parameter_source_sha256,
                name=f"score term {term_id} parameter_source_sha256",
            ),
        )

    @property
    def contribution(self) -> float:
        value = self.raw_value * self.weight
        if not math.isfinite(value):
            raise DockingScoringError(
                f"score term {self.term_id} contribution is not finite"
            )
        return value

    def to_dict(self) -> dict[str, object]:
        return {
            "term_id": self.term_id,
            "raw_value": float(self.raw_value),
            "weight": float(self.weight),
            "contribution": float(self.contribution),
            "unit": self.unit,
            "semantics": self.semantics,
            "parameter_source_sha256": self.parameter_source_sha256,
        }


@dataclass(frozen=True)
class DockingScoreBreakdown:
    """Complete term decomposition returned atomically with one scalar score."""

    terms: tuple[DockingScoreTerm, ...]
    complete: bool = True
    blockers: tuple[str, ...] = ()
    schema_id: str = DOCKING_SCORE_BREAKDOWN_SCHEMA_ID

    def __post_init__(self) -> None:
        if self.schema_id != DOCKING_SCORE_BREAKDOWN_SCHEMA_ID:
            raise DockingScoringError("unsupported docking score breakdown schema")
        terms = tuple(self.terms)
        if not terms or not all(isinstance(term, DockingScoreTerm) for term in terms):
            raise DockingScoringError(
                "score breakdown must contain at least one DockingScoreTerm"
            )
        term_ids = [term.term_id for term in terms]
        if len(term_ids) != len(set(term_ids)):
            raise DockingScoringError("score breakdown term IDs must be unique")
        if not isinstance(self.complete, bool):
            raise DockingScoringError("score breakdown complete must be boolean")
        blockers = tuple(str(value or "").strip() for value in self.blockers)
        if any(not value for value in blockers) or len(blockers) != len(set(blockers)):
            raise DockingScoringError(
                "score breakdown blockers must be unique non-empty strings"
            )
        object.__setattr__(self, "terms", terms)
        object.__setattr__(self, "blockers", blockers)
        _finite_float(self.total_score, name="score breakdown total_score")

    @property
    def total_score(self) -> float:
        return math.fsum(term.contribution for term in self.terms)

    @property
    def claim_safe(self) -> bool:
        return False

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_id": self.schema_id,
            "complete": bool(self.complete),
            "total_score": float(self.total_score),
            "terms": [term.to_dict() for term in self.terms],
            "blockers": list(self.blockers),
            "claim_safe": False,
        }


UNCALIBRATED_INTERNAL_DOCKING_SCORE = DockingScoreDescriptor(
    score_id="internal_unvalidated_docking_score",
    direction=ScoreDirection.MINIMIZE,
    unit=None,
    semantics="internal_unvalidated_pose_ordering_scalar",
    calibrated=False,
)


def _canonical_sha256(payload: object) -> str:
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _require_digest(
    value: object,
    *,
    name: str,
    allow_empty: bool = False,
) -> str:
    text = str(value or "").strip().lower()
    if allow_empty and not text:
        return ""
    if _SHA256_RE.fullmatch(text) is None:
        raise ValueError(f"{name} must be a lowercase SHA-256")
    return text


def component_problem_fingerprint(
    component: Any,
    *,
    kind: str,
    fallback_unbound_problem_fingerprint_sha256: str = "",
) -> str:
    """Return the exact docking problem declared by a scorer or refiner."""

    declared = getattr(component, "problem_fingerprint_sha256", "")
    if declared:
        return _require_digest(
            declared,
            name=f"{kind} problem_fingerprint_sha256",
        )
    if fallback_unbound_problem_fingerprint_sha256:
        return _require_digest(
            fallback_unbound_problem_fingerprint_sha256,
            name="unbound internal docking problem fingerprint",
        )
    raise ValueError(f"{kind} must declare problem_fingerprint_sha256")


def component_contract_fingerprint(
    component: Any,
    *,
    kind: str,
    expected_problem_fingerprint_sha256: str | None = None,
    allow_unbound_internal: bool = False,
) -> str:
    """Fingerprint a scorer/refiner contract and its immutable problem binding."""

    if kind not in {"scorer", "refiner"}:
        raise ValueError("component kind must be scorer or refiner")
    identifier = str(getattr(component, f"{kind}_id", "") or "").strip()
    version = str(getattr(component, f"{kind}_version", "") or "").strip()
    if not identifier or not version:
        raise ValueError(f"{kind} must declare ID and version")
    expected_problem = (
        ""
        if expected_problem_fingerprint_sha256 is None
        else _require_digest(
            expected_problem_fingerprint_sha256,
            name="expected docking problem fingerprint",
        )
    )
    declared_problem = getattr(component, "problem_fingerprint_sha256", "")
    unbound_compatibility = bool(allow_unbound_internal and not declared_problem)
    problem_fingerprint = component_problem_fingerprint(
        component,
        kind=kind,
        fallback_unbound_problem_fingerprint_sha256=(
            expected_problem if unbound_compatibility else ""
        ),
    )
    if expected_problem and problem_fingerprint != expected_problem:
        raise ValueError(
            f"{kind} problem_fingerprint_sha256 does not match the active docking problem"
        )
    declared_source_fingerprint = _require_digest(
        getattr(component, "implementation_source_sha256", ""),
        name=f"{kind} implementation_source_sha256",
        allow_empty=True,
    )
    source_fingerprint = declared_source_fingerprint
    if not source_fingerprint and component.__class__.__module__.startswith(
        "betelgeuze_engine_v2.docking."
    ):
        try:
            implementation_source = inspect.getsource(component.__class__).encode(
                "utf-8"
            )
        except (OSError, TypeError) as exc:
            raise ValueError(
                f"{kind} implementation source cannot be measured"
            ) from exc
        source_fingerprint = hashlib.sha256(implementation_source).hexdigest()
    config_fingerprint = _require_digest(
        getattr(component, "config_fingerprint_sha256", ""),
        name=f"{kind} config_fingerprint_sha256",
        allow_empty=True,
    )
    if not unbound_compatibility and not source_fingerprint:
        raise ValueError(f"{kind} must declare implementation_source_sha256")
    payload = {
        "schema_id": "betelgeuze.engine_v2_docking_component_contract/2.0.0",
        "kind": kind,
        "id": identifier,
        "version": version,
        "class": f"{component.__class__.__module__}.{component.__class__.__qualname__}",
        "problem_fingerprint_sha256": problem_fingerprint,
        "implementation_source_sha256": source_fingerprint,
        "config_fingerprint_sha256": config_fingerprint,
        "unbound_internal_compatibility": unbound_compatibility,
    }
    if kind == "scorer":
        payload["validated_for_docking_ranking"] = bool(
            getattr(component, "validated_for_docking_ranking", False)
        )
        payload["score_descriptor"] = scorer_descriptor(component).to_dict()
    return _canonical_sha256(payload)


def scorer_descriptor(scorer: Any) -> DockingScoreDescriptor:
    value = getattr(scorer, "score_descriptor", None)
    if value is None:
        return UNCALIBRATED_INTERNAL_DOCKING_SCORE
    if not isinstance(value, DockingScoreDescriptor):
        raise TypeError("score_descriptor must be DockingScoreDescriptor")
    return value


def score_sort_key(value: float, descriptor: DockingScoreDescriptor) -> float:
    score = float(value)
    if not math.isfinite(score):
        raise ValueError("score must be finite")
    return score if descriptor.direction is ScoreDirection.MINIMIZE else -score


__all__ = [
    "DOCKING_SCORE_BREAKDOWN_SCHEMA_ID",
    "DockingScoreBreakdown",
    "DockingScoreDescriptor",
    "DockingScoreTerm",
    "DockingScoringError",
    "ScoreDirection",
    "UNCALIBRATED_INTERNAL_DOCKING_SCORE",
    "component_contract_fingerprint",
    "component_problem_fingerprint",
    "score_sort_key",
    "scorer_descriptor",
]

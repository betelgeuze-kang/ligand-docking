"""Machine-readable docking score and component provenance contracts."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
import json
import math
import re
from typing import Any

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


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
    source_fingerprint = _require_digest(
        getattr(component, "implementation_source_sha256", ""),
        name=f"{kind} implementation_source_sha256",
        allow_empty=unbound_compatibility,
    )
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
        backend_receipt_sha256 = getattr(component, "backend_receipt_sha256", "")
        if backend_receipt_sha256:
            payload["backend_receipt_sha256"] = _require_digest(
                backend_receipt_sha256,
                name="scorer backend_receipt_sha256",
            )
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
    "DockingScoreDescriptor",
    "ScoreDirection",
    "UNCALIBRATED_INTERNAL_DOCKING_SCORE",
    "component_contract_fingerprint",
    "component_problem_fingerprint",
    "score_sort_key",
    "scorer_descriptor",
]

"""Machine-readable docking score and component provenance contracts."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
import json
import math
from typing import Any


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


def component_contract_fingerprint(component: Any, *, kind: str) -> str:
    """Fingerprint a scorer/refiner contract without serializing executable state."""

    identifier = str(getattr(component, f"{kind}_id", "") or "").strip()
    version = str(getattr(component, f"{kind}_version", "") or "").strip()
    if not identifier or not version:
        raise ValueError(f"{kind} must declare ID and version")
    config_fingerprint = str(
        getattr(component, "config_fingerprint_sha256", "") or ""
    ).lower()
    if config_fingerprint and (
        len(config_fingerprint) != 64
        or any(char not in "0123456789abcdef" for char in config_fingerprint)
    ):
        raise ValueError(f"{kind} config_fingerprint_sha256 must be a lowercase SHA-256")
    payload = {
        "kind": kind,
        "id": identifier,
        "version": version,
        "class": f"{component.__class__.__module__}.{component.__class__.__qualname__}",
        "config_fingerprint_sha256": config_fingerprint,
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
    "DockingScoreDescriptor",
    "ScoreDirection",
    "UNCALIBRATED_INTERNAL_DOCKING_SCORE",
    "component_contract_fingerprint",
    "score_sort_key",
    "scorer_descriptor",
]

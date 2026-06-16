from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

from betelgeuze_ai_md.contracts.claim_scope import TOPOLOGY_FIDELITY_PLACEHOLDER_ALANINE
from betelgeuze_ai_md.contracts.errors import ContractValidationError
from betelgeuze_ai_md.contracts.serialization import sha256_payload, to_plain


def _text(value: Any, field_name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ContractValidationError(f"{field_name} is required")
    return text


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _finite_float(value: Any, field_name: str) -> float:
    try:
        numeric = float(value)
    except (TypeError, ValueError) as exc:
        raise ContractValidationError(f"{field_name} must be numeric") from exc
    if not math.isfinite(numeric):
        raise ContractValidationError(f"{field_name} must be finite")
    return numeric


def _finite_trace(value: Any, field_name: str) -> list[float]:
    if not isinstance(value, list):
        raise ContractValidationError(f"{field_name} must be a list")
    return [_finite_float(item, field_name) for item in value]


@dataclass(frozen=True)
class TrajectorySummary:
    frame_count: int
    energy_trace: list[float] = field(default_factory=list)
    contact_trace: list[float] = field(default_factory=list)
    stability_score: float = 0.0
    mean_min_distance: float = 0.0
    escape_fraction: float = 0.0
    clash_fraction: float = 0.0

    def __post_init__(self) -> None:
        try:
            frame_count = int(self.frame_count)
        except (TypeError, ValueError) as exc:
            raise ContractValidationError("frame_count must be an integer") from exc
        if frame_count < 0:
            raise ContractValidationError("frame_count must be non-negative")
        object.__setattr__(self, "frame_count", frame_count)
        energy_trace = _finite_trace(self.energy_trace, "energy_trace")
        contact_trace = _finite_trace(self.contact_trace, "contact_trace")
        if len(energy_trace) > frame_count or len(contact_trace) > frame_count:
            raise ContractValidationError("trajectory traces cannot exceed frame_count")
        if any(value < 0.0 for value in contact_trace):
            raise ContractValidationError("contact_trace values must be non-negative")
        object.__setattr__(self, "energy_trace", energy_trace)
        object.__setattr__(self, "contact_trace", contact_trace)
        for key in ("stability_score", "mean_min_distance", "escape_fraction", "clash_fraction"):
            object.__setattr__(self, key, _finite_float(getattr(self, key), key))
        if not 0.0 <= self.stability_score <= 1.0:
            raise ContractValidationError("stability_score must be in [0, 1]")
        if self.mean_min_distance < 0.0:
            raise ContractValidationError("mean_min_distance must be non-negative")
        for key in ("escape_fraction", "clash_fraction"):
            if not 0.0 <= getattr(self, key) <= 1.0:
                raise ContractValidationError(f"{key} must be in [0, 1]")

    def to_dict(self) -> dict[str, Any]:
        return to_plain(self)

    def contract_hash(self) -> str:
        return sha256_payload(self)


@dataclass(frozen=True)
class BackmappedPose:
    pose_id: str
    structure_path: str
    structure_sha256: str
    repair_operations: list[str] = field(default_factory=list)
    chemical_validity_summary: dict[str, Any] = field(default_factory=dict)
    backmap_confidence: float = 0.0

    def __post_init__(self) -> None:
        object.__setattr__(self, "pose_id", _text(self.pose_id, "pose_id"))
        object.__setattr__(self, "structure_path", _text(self.structure_path, "structure_path"))
        object.__setattr__(self, "structure_sha256", _text(self.structure_sha256, "structure_sha256"))
        object.__setattr__(self, "backmap_confidence", float(self.backmap_confidence))
        if not 0.0 <= self.backmap_confidence <= 1.0:
            raise ContractValidationError("backmap_confidence must be in [0, 1]")

    def to_dict(self) -> dict[str, Any]:
        return to_plain(self)


@dataclass(frozen=True)
class InteractionEvidence:
    interaction_id: str
    interaction_type: str
    partners: list[str]
    distance: float | None = None
    angle: float | None = None
    occupancy: float = 0.0
    confidence: float = 0.0
    role_valid: bool = True
    claim_blocker: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "interaction_id", _text(self.interaction_id, "interaction_id"))
        object.__setattr__(self, "interaction_type", _text(self.interaction_type, "interaction_type"))
        if len(self.partners) < 2:
            raise ContractValidationError("interaction evidence requires at least two partners")
        object.__setattr__(self, "occupancy", float(self.occupancy))
        object.__setattr__(self, "confidence", float(self.confidence))
        if not 0.0 <= self.occupancy <= 1.0:
            raise ContractValidationError("occupancy must be in [0, 1]")
        if not 0.0 <= self.confidence <= 1.0:
            raise ContractValidationError("confidence must be in [0, 1]")


@dataclass(frozen=True)
class InteractionReport:
    interactions: list[InteractionEvidence] = field(default_factory=list)
    interaction_confidence: float = 0.0
    over_anchoring_detected: bool = False
    unsatisfied_donor_count: int = 0
    unsatisfied_acceptor_count: int = 0
    claim_blockers: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "interactions",
            [
                item if isinstance(item, InteractionEvidence) else InteractionEvidence(**item)
                for item in self.interactions
            ],
        )
        object.__setattr__(self, "interaction_confidence", float(self.interaction_confidence))
        if not 0.0 <= self.interaction_confidence <= 1.0:
            raise ContractValidationError("interaction_confidence must be in [0, 1]")
        blockers = list(self.claim_blockers)
        blockers.extend(item.claim_blocker for item in self.interactions if item.claim_blocker)
        object.__setattr__(self, "claim_blockers", sorted(set(blockers)))

    def to_dict(self) -> dict[str, Any]:
        return to_plain(self)


@dataclass(frozen=True)
class AIResidualReport:
    residual_mode: str = "disabled"
    correction_applied: bool = False
    uncertainty: float = 1.0
    abstained: bool = True
    calibration_family: str = ""
    model_hash: str = ""
    residual_delta: float = 0.0
    bounded_residual_delta: float = 0.0
    max_delta: float = 0.0
    guard: float = 0.0
    lambda_ai: float = 1.0
    active_score_col: str = ""
    base_score_col: str = ""
    ranking_changed: bool = False
    review_flags: list[str] = field(default_factory=list)
    guard_components: dict[str, float] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        object.__setattr__(self, "residual_mode", str(self.residual_mode or "disabled").strip())
        object.__setattr__(self, "uncertainty", float(self.uncertainty))
        if not 0.0 <= self.uncertainty <= 1.0:
            raise ContractValidationError("uncertainty must be in [0, 1]")
        for key in ("residual_delta", "bounded_residual_delta", "max_delta", "guard", "lambda_ai"):
            value = float(getattr(self, key))
            if not math.isfinite(value):
                raise ContractValidationError(f"{key} must be finite")
            object.__setattr__(self, key, value)
        if self.max_delta < 0.0:
            raise ContractValidationError("max_delta must be non-negative")
        if self.lambda_ai < 0.0:
            raise ContractValidationError("lambda_ai must be non-negative")
        if not 0.0 <= self.guard <= 1.0:
            raise ContractValidationError("guard must be in [0, 1]")
        guard_components = {
            str(key).strip(): float(value)
            for key, value in self.guard_components.items()
            if str(key).strip()
        }
        for key, value in guard_components.items():
            if not math.isfinite(value) or not 0.0 <= value <= 1.0:
                raise ContractValidationError(f"guard component {key} must be in [0, 1]")
        object.__setattr__(self, "guard_components", guard_components)
        object.__setattr__(self, "active_score_col", str(self.active_score_col or "").strip())
        object.__setattr__(self, "base_score_col", str(self.base_score_col or "").strip())
        object.__setattr__(self, "ranking_changed", bool(self.ranking_changed is True))
        if self.ranking_changed and not self.active_score_col:
            raise ContractValidationError("active_score_col is required when residual changes ranking")
        if self.max_delta > 0.0:
            max_abs_delta = self.lambda_ai * self.guard * self.max_delta + 1e-9
            if abs(self.bounded_residual_delta) > max_abs_delta:
                raise ContractValidationError("bounded_residual_delta exceeds guarded max_delta")
        flags = {str(item).strip() for item in self.review_flags if str(item).strip()}
        if max(abs(self.residual_delta), abs(self.bounded_residual_delta)) > 0.5:
            flags.add("residual_delta_review_required")
        object.__setattr__(self, "review_flags", sorted(flags))
        object.__setattr__(self, "notes", [str(item).strip() for item in self.notes if str(item).strip()])

    def to_dict(self) -> dict[str, Any]:
        return to_plain(self)


def fail_closed_topology_report(
    *,
    topology_fidelity: str = TOPOLOGY_FIDELITY_PLACEHOLDER_ALANINE,
    blockers: list[str] | None = None,
    notes: list[str] | None = None,
    status: str = "not_assessed",
    confidence: float = 0.0,
) -> "TopologyValidityReport":
    """Build an explicit not-assessed/fail-closed TopologyValidityReport.

    API adapters and any unknown-input path must use this helper so that
    placeholder or unassessed topology cannot accidentally satisfy
    claim-safe bundle validation.
    """
    resolved_fidelity = str(topology_fidelity or TOPOLOGY_FIDELITY_PLACEHOLDER_ALANINE).strip()
    if not resolved_fidelity:
        resolved_fidelity = TOPOLOGY_FIDELITY_PLACEHOLDER_ALANINE
    resolved_blockers = sorted(
        set(
            str(item).strip()
            for item in (blockers or ["topology_validity_not_assessed"])
            if str(item).strip()
        )
    )
    if not resolved_blockers:
        resolved_blockers = ["topology_validity_not_assessed"]
    return TopologyValidityReport(
        status=str(status or "not_assessed").strip() or "not_assessed",
        topology_fidelity=resolved_fidelity,
        confidence=float(confidence),
        validity_rows=[],
        claim_blockers=resolved_blockers,
        notes=[str(item) for item in (notes or []) if str(item).strip()],
    )


@dataclass(frozen=True)
class TopologyValidityReport:
    status: str
    topology_fidelity: str = TOPOLOGY_FIDELITY_PLACEHOLDER_ALANINE
    confidence: float = 0.0
    validity_rows: list[dict[str, Any]] = field(default_factory=list)
    claim_blockers: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_mapping(
        cls,
        value: dict[str, Any],
        *,
        default_fidelity: str = TOPOLOGY_FIDELITY_PLACEHOLDER_ALANINE,
    ) -> "TopologyValidityReport":
        raw = value if isinstance(value, dict) else {}
        if not raw:
            return fail_closed_topology_report(topology_fidelity=default_fidelity)
        known_keys = {"status", "topology_fidelity", "confidence", "validity_rows", "claim_blockers", "notes", "metadata"}
        metadata = _as_dict(raw.get("metadata"))
        metadata.update({str(key): val for key, val in raw.items() if key not in known_keys})
        blockers = [str(item) for item in _as_list(raw.get("claim_blockers")) if str(item).strip()]
        status = str(raw.get("status") or "not_assessed").strip() or "not_assessed"
        if status == "not_assessed":
            blockers.append("topology_validity_not_assessed")
        return cls(
            status=status,
            topology_fidelity=str(raw.get("topology_fidelity") or default_fidelity or TOPOLOGY_FIDELITY_PLACEHOLDER_ALANINE),
            confidence=float(raw.get("confidence") or 0.0),
            validity_rows=[_as_dict(item) for item in _as_list(raw.get("validity_rows"))],
            claim_blockers=blockers,
            notes=[str(item) for item in _as_list(raw.get("notes")) if str(item).strip()],
            metadata=metadata,
        )

    def __post_init__(self) -> None:
        status = str(self.status or "").strip()
        if not status:
            raise ContractValidationError("status is required")
        object.__setattr__(self, "status", status)
        object.__setattr__(
            self,
            "topology_fidelity",
            _text(self.topology_fidelity, "topology_fidelity") or TOPOLOGY_FIDELITY_PLACEHOLDER_ALANINE,
        )
        object.__setattr__(self, "confidence", float(self.confidence))
        if not 0.0 <= self.confidence <= 1.0:
            raise ContractValidationError("confidence must be in [0, 1]")
        rows = [_as_dict(item) for item in self.validity_rows]
        rows = [row for row in rows if row]
        object.__setattr__(self, "validity_rows", rows)
        blockers = sorted(
            set(str(item).strip() for item in self.claim_blockers if str(item).strip())
        )
        object.__setattr__(self, "claim_blockers", blockers)
        object.__setattr__(
            self,
            "notes",
            [str(item).strip() for item in self.notes if str(item).strip()],
        )
        object.__setattr__(self, "metadata", _as_dict(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return to_plain(self)

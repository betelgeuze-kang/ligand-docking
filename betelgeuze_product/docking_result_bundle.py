"""Common DockingResult bundle shared by every engine surface (roadmap §17).

Legacy, V2, and the external oracle previously reported results in their own
shapes, so a shadow comparison had to reconcile three schemas and could not
prove the three runs shared an input, a pocket, or a candidate budget.

This module defines the one result schema all three emit, with the fields the
roadmap requires:

- ``engine_surface`` (legacy_product / engine_v2 / external_oracle)
- ``engine_version``
- prepared input hashes
- pocket identity
- pose ensemble
- per-term score
- geometric validity
- chemistry validity
- uncertainty / abstention
- failure denominator
- runtime / budget
- benchmark profile
- claim scope
- evidence receipts

A bundle that omits a required field fails closed: an incomplete result must not
enter a comparison, because a missing failure denominator silently inflates a
success rate.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from typing import Any, Mapping, Sequence

from betelgeuze_product.preparation_packet import ENGINE_SURFACES

DOCKING_RESULT_BUNDLE_SCHEMA_VERSION = "docking_result_bundle_v1"

#: Every section the roadmap requires in a result bundle.
REQUIRED_BUNDLE_SECTIONS = (
    "engine_surface",
    "engine_version",
    "prepared_input_hashes",
    "pocket_identity",
    "pose_ensemble",
    "per_term_score",
    "geometric_validity",
    "chemistry_validity",
    "uncertainty",
    "failure_denominator",
    "runtime_budget",
    "benchmark_profile",
    "claim_scope",
    "evidence_receipts",
)

STATUS_READY = "docking_result_bundle_ready"
STATUS_BLOCKED = "blocked_docking_result_bundle"

CLAIM_BOUNDARY = (
    "Common docking result schema only. It carries engine surface identity, prepared-input hashes, per-term "
    "scores, validity, abstention, failure denominator, and runtime budget so results from different engines "
    "can be compared on equal terms. It does not itself dock, score, or promote a claim."
)


class DockingResultBundleError(ValueError):
    """Raised when a bundle is missing a required section or field."""


@dataclass(frozen=True)
class PoseRecord:
    """One reported pose with its identity, per-term score, and coordinates.

    The coordinates are part of the result schema because without them a pose is
    unfalsifiable: every RMSD-based metric the roadmap requires (top-1 <= 2 A,
    top-3/top-5 recovery) needs the actual atom positions, so a bundle that
    reported only scores could never be evaluated against a reference pose. They
    are optional so an external oracle that reported scores but withheld
    coordinates is recorded honestly rather than padded with zeros.
    """

    pose_id: str
    rank: int
    conformer_id: str
    cluster_id: int
    total_score: float
    per_term_score: dict[str, float] = field(default_factory=dict)
    geometric_valid: bool = False
    chemistry_valid: bool = False
    coordinates: tuple[tuple[float, float, float], ...] = field(default_factory=tuple)

    @property
    def coordinates_present(self) -> bool:
        return bool(self.coordinates)

    @property
    def atom_count(self) -> int:
        return len(self.coordinates)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        # Coordinates are rounded in the payload so a bundle hash stays stable
        # across platforms while remaining precise enough for a 2 A criterion.
        payload["coordinates"] = [
            [round(float(value), 4) for value in row] for row in self.coordinates
        ]
        payload["coordinates_present"] = self.coordinates_present
        payload["atom_count"] = self.atom_count
        return payload


@dataclass(frozen=True)
class FailureDenominator:
    """The denominator every rate must be computed against."""

    attempted_case_count: int
    scored_case_count: int
    failed_case_count: int
    abstained_case_count: int

    @property
    def accounted(self) -> bool:
        """Every attempted case must land in exactly one outcome bucket."""

        return int(self.attempted_case_count) == (
            int(self.scored_case_count)
            + int(self.failed_case_count)
            + int(self.abstained_case_count)
        )

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["accounted"] = self.accounted
        return payload


@dataclass(frozen=True)
class DockingResultBundle:
    """One engine surface's result for one case."""

    engine_surface: str
    engine_version: str
    prepared_input_hash: str
    receptor_input_hash: str
    ligand_input_hash: str
    pocket_identity: dict[str, Any]
    poses: tuple[PoseRecord, ...]
    failure_denominator: FailureDenominator
    runtime_seconds: float
    candidate_budget: int
    benchmark_profile: str
    claim_scope: str
    uncertainty: dict[str, Any] = field(default_factory=dict)
    evidence_receipts: dict[str, Any] = field(default_factory=dict)
    blockers: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if str(self.engine_surface) not in ENGINE_SURFACES:
            raise DockingResultBundleError(
                f"unsupported_engine_surface:{self.engine_surface or '<empty>'}"
            )
        for name in ("engine_version", "prepared_input_hash", "benchmark_profile", "claim_scope"):
            if not str(getattr(self, name) or "").strip():
                raise DockingResultBundleError(f"missing_required_field:{name}")
        if not self.failure_denominator.accounted:
            raise DockingResultBundleError("failure_denominator_not_accounted")

    @property
    def abstained(self) -> bool:
        return bool(self.uncertainty.get("abstained") is True)

    @property
    def status(self) -> str:
        if self.blockers:
            return STATUS_BLOCKED
        return STATUS_READY

    @property
    def top_pose(self) -> PoseRecord | None:
        ranked = sorted(self.poses, key=lambda pose: (pose.rank, pose.total_score))
        return ranked[0] if ranked else None

    @property
    def bundle_hash(self) -> str:
        return hashlib.sha256(
            json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"), default=str).encode(
                "utf-8"
            )
        ).hexdigest()

    def pocket_hash(self) -> str:
        """Hash of the pocket identity, used to prove surfaces shared a pocket."""

        return hashlib.sha256(
            json.dumps(
                dict(self.pocket_identity), sort_keys=True, separators=(",", ":"), default=str
            ).encode("utf-8")
        ).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": DOCKING_RESULT_BUNDLE_SCHEMA_VERSION,
            "status": self.status,
            "engine_surface": str(self.engine_surface),
            "engine_version": str(self.engine_version),
            "prepared_input_hashes": {
                "prepared_input_hash": str(self.prepared_input_hash),
                "receptor_input_hash": str(self.receptor_input_hash),
                "ligand_input_hash": str(self.ligand_input_hash),
            },
            "pocket_identity": dict(self.pocket_identity),
            "pose_ensemble": {
                "pose_count": len(self.poses),
                "poses": [pose.to_dict() for pose in self.poses],
            },
            "per_term_score": {
                pose.pose_id: dict(pose.per_term_score) for pose in self.poses
            },
            "geometric_validity": {
                "valid_pose_count": sum(1 for pose in self.poses if pose.geometric_valid),
                "invalid_pose_count": sum(1 for pose in self.poses if not pose.geometric_valid),
            },
            "chemistry_validity": {
                "valid_pose_count": sum(1 for pose in self.poses if pose.chemistry_valid),
                "invalid_pose_count": sum(1 for pose in self.poses if not pose.chemistry_valid),
            },
            "uncertainty": dict(self.uncertainty),
            "failure_denominator": self.failure_denominator.to_dict(),
            "runtime_budget": {
                "runtime_seconds": float(self.runtime_seconds),
                "candidate_budget": int(self.candidate_budget),
            },
            "benchmark_profile": str(self.benchmark_profile),
            "claim_scope": str(self.claim_scope),
            "evidence_receipts": dict(self.evidence_receipts),
            "blockers": list(self.blockers),
            "claim_boundary": CLAIM_BOUNDARY,
        }


def validate_bundle_payload(payload: Mapping[str, Any]) -> list[str]:
    """Return the list of missing required sections (empty == complete)."""

    if not isinstance(payload, Mapping):
        return ["bundle_payload_invalid"]
    return [section for section in REQUIRED_BUNDLE_SECTIONS if section not in payload]


def compare_bundles(bundles: Sequence[DockingResultBundle]) -> dict[str, Any]:
    """Pairwise-comparable view of several surfaces' results for one case.

    The comparison is only valid when every surface consumed the same prepared
    input and the same candidate budget. Otherwise a score delta could come from
    the inputs rather than the engines, so no delta is reported.
    """

    rows = list(bundles)
    reasons: list[str] = []
    if len(rows) < 2:
        reasons.append("need_at_least_two_engine_surfaces")
    surfaces = [bundle.engine_surface for bundle in rows]
    if len(set(surfaces)) != len(surfaces):
        reasons.append("duplicate_engine_surface")
    if len({bundle.prepared_input_hash for bundle in rows}) > 1:
        reasons.append("mismatched_prepared_input_hash")
    if len({bundle.pocket_hash() for bundle in rows}) > 1:
        reasons.append("mismatched_pocket_identity")
    if len({int(bundle.candidate_budget) for bundle in rows}) > 1:
        reasons.append("mismatched_candidate_budget")
    if len({bundle.benchmark_profile for bundle in rows}) > 1:
        reasons.append("mismatched_benchmark_profile")

    comparable = not reasons
    deltas: list[dict[str, Any]] = []
    if comparable:
        for i, left in enumerate(rows):
            for right in rows[i + 1 :]:
                left_top = left.top_pose
                right_top = right.top_pose
                deltas.append(
                    {
                        "left_engine_surface": left.engine_surface,
                        "right_engine_surface": right.engine_surface,
                        "left_top_score": None if left_top is None else float(left_top.total_score),
                        "right_top_score": (
                            None if right_top is None else float(right_top.total_score)
                        ),
                        "top_score_delta": (
                            None
                            if left_top is None or right_top is None
                            else float(right_top.total_score - left_top.total_score)
                        ),
                        "left_abstained": left.abstained,
                        "right_abstained": right.abstained,
                    }
                )
    return {
        "schema_version": DOCKING_RESULT_BUNDLE_SCHEMA_VERSION,
        "status": "docking_result_comparison_ready" if comparable else "blocked_docking_result_comparison",
        "comparable": comparable,
        "engine_surfaces": surfaces,
        "invalid_reasons": reasons,
        "pairwise_deltas": deltas,
        "claim_boundary": CLAIM_BOUNDARY,
    }


__all__ = [
    "CLAIM_BOUNDARY",
    "DOCKING_RESULT_BUNDLE_SCHEMA_VERSION",
    "REQUIRED_BUNDLE_SECTIONS",
    "STATUS_BLOCKED",
    "STATUS_READY",
    "DockingResultBundle",
    "DockingResultBundleError",
    "FailureDenominator",
    "PoseRecord",
    "compare_bundles",
    "validate_bundle_payload",
]

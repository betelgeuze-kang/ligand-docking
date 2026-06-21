from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from betelgeuze_ai_md.contracts.claim_scope import TOPOLOGY_FIDELITY_PLACEHOLDER_ALANINE
from betelgeuze_ai_md.contracts.errors import ContractValidationError
from betelgeuze_ai_md.contracts.output_schema import (
    AIResidualReport,
    BackmappedPose,
    InteractionReport,
    TopologyValidityReport,
    TrajectorySummary,
    fail_closed_topology_report,
)
from betelgeuze_ai_md.contracts.serialization import canonical_json, sha256_payload, to_plain
from betelgeuze_ai_md.contracts.verdict_schema import Verdict

REQUIRED_SOURCE_HASHES = ("input_hash", "config_hash", "model_hash", "executable_hash")
PASS_TOPOLOGY_STATUSES = {"pass", "topology_valid"}
PASS_CHEMICAL_VALIDITY_STATUSES = {"pass", "valid", "chemical_validity_pass"}
CLAIM_SAFE_MAX_AI_UNCERTAINTY = 0.35


@dataclass(frozen=True)
class EvidenceBundle:
    bundle_id: str
    project_id: str
    ranked_shortlist: list[dict[str, Any]]
    trajectory_summary: TrajectorySummary
    backmapped_poses: list[BackmappedPose]
    interaction_report: InteractionReport
    topology_report: TopologyValidityReport | dict[str, Any]
    ai_residual_report: AIResidualReport
    failure_flags: list[str]
    source_hashes: dict[str, str]
    viewer_assets: list[str]
    wetlab_handoff_table: list[dict[str, Any]]
    verdict: Verdict
    result_manifest: dict[str, Any] = field(default_factory=dict)
    bundle_schema_version: str = "ai_md_evidence_bundle_v1"
    claim_boundary: str = ""

    def __post_init__(self) -> None:
        if isinstance(self.trajectory_summary, dict):
            object.__setattr__(self, "trajectory_summary", TrajectorySummary(**self.trajectory_summary))
        if isinstance(self.ai_residual_report, dict):
            object.__setattr__(self, "ai_residual_report", AIResidualReport(**self.ai_residual_report))
        if isinstance(self.verdict, dict):
            object.__setattr__(self, "verdict", Verdict(**self.verdict))
        if not isinstance(self.result_manifest, dict):
            object.__setattr__(self, "result_manifest", {})
        if isinstance(self.interaction_report, dict):
            interactions = [
                item if isinstance(item, dict) else to_plain(item)
                for item in self.interaction_report.get("interactions", [])
            ]
            object.__setattr__(
                self,
                "interaction_report",
                InteractionReport(
                    **{
                        **self.interaction_report,
                        "interactions": interactions,
                    }
                ),
            )
        object.__setattr__(
            self,
            "backmapped_poses",
            [
                pose if isinstance(pose, BackmappedPose) else BackmappedPose(**pose)
                for pose in self.backmapped_poses
            ],
        )
        if not isinstance(self.topology_report, TopologyValidityReport):
            raw = self.topology_report if isinstance(self.topology_report, dict) else {}
            object.__setattr__(
                self,
                "topology_report",
                TopologyValidityReport.from_mapping(raw) if raw else fail_closed_topology_report(),
            )
        if not str(self.bundle_id or "").strip():
            raise ContractValidationError("bundle_id is required")
        if not str(self.project_id or "").strip():
            raise ContractValidationError("project_id is required")
        missing_hashes = [key for key in REQUIRED_SOURCE_HASHES if not str(self.source_hashes.get(key, "")).strip()]
        if missing_hashes:
            raise ContractValidationError(f"EvidenceBundle missing source hashes: {missing_hashes}")
        if self.verdict.claim_safe and self.failure_flags:
            raise ContractValidationError("claim_safe EvidenceBundle cannot contain failure_flags")
        topology_status = str(self.topology_report.status or "").strip()
        if self.verdict.claim_safe and topology_status not in PASS_TOPOLOGY_STATUSES:
            raise ContractValidationError("claim_safe EvidenceBundle requires a passing topology_report.status")
        if self.verdict.claim_safe and self.topology_report.claim_blockers:
            raise ContractValidationError("claim_safe EvidenceBundle cannot contain topology claim blockers")
        if (
            self.verdict.claim_safe
            and str(self.topology_report.topology_fidelity or "").strip()
            == TOPOLOGY_FIDELITY_PLACEHOLDER_ALANINE
        ):
            raise ContractValidationError(
                "claim_safe EvidenceBundle requires non-placeholder topology fidelity"
            )
        if (
            self.verdict.claim_safe
            and str(self.topology_report.topology_fidelity or "").strip()
            != str(self.verdict.topology_fidelity or "").strip()
        ):
            raise ContractValidationError(
                "claim_safe EvidenceBundle requires topology_report fidelity to match verdict fidelity"
            )
        if self.verdict.claim_safe and self.interaction_report.claim_blockers:
            raise ContractValidationError("claim_safe EvidenceBundle cannot contain interaction claim blockers")
        if self.verdict.claim_safe and not self.interaction_report.interactions:
            raise ContractValidationError("claim_safe EvidenceBundle requires interaction evidence")
        if self.verdict.claim_safe and self.interaction_report.interaction_confidence <= 0.0:
            raise ContractValidationError("claim_safe EvidenceBundle requires positive interaction confidence")
        if self.verdict.claim_safe and self.ai_residual_report.uncertainty > CLAIM_SAFE_MAX_AI_UNCERTAINTY:
            raise ContractValidationError("claim_safe EvidenceBundle cannot contain high AI uncertainty")
        if self.verdict.claim_safe and self.ai_residual_report.review_flags:
            raise ContractValidationError("claim_safe EvidenceBundle cannot contain AI residual review flags")
        if self.verdict.claim_safe and self.trajectory_summary.frame_count <= 0:
            raise ContractValidationError("claim_safe EvidenceBundle requires trajectory frames")
        if self.verdict.claim_safe and not self.trajectory_summary.energy_trace:
            raise ContractValidationError("claim_safe EvidenceBundle requires trajectory energy trace")
        if self.verdict.claim_safe and not self.backmapped_poses:
            raise ContractValidationError("claim_safe EvidenceBundle requires backmapped poses")
        if self.verdict.claim_safe:
            for pose in self.backmapped_poses:
                status = str(pose.chemical_validity_summary.get("status", "") or "").strip()
                if status and status not in PASS_CHEMICAL_VALIDITY_STATUSES:
                    raise ContractValidationError(
                        f"claim_safe EvidenceBundle has non-passing chemical validity for pose {pose.pose_id}"
                    )
                chemical_blockers = pose.chemical_validity_summary.get("claim_blockers", [])
                if isinstance(chemical_blockers, list) and any(str(item).strip() for item in chemical_blockers):
                    raise ContractValidationError(
                        f"claim_safe EvidenceBundle has chemical validity claim blockers for pose {pose.pose_id}"
                    )
        if self.verdict.claim_safe and not self.ranked_shortlist:
            raise ContractValidationError("claim_safe EvidenceBundle requires ranked shortlist")
        if self.verdict.claim_safe and not self.wetlab_handoff_table:
            raise ContractValidationError("claim_safe EvidenceBundle requires wetlab handoff table")
        if not self.claim_boundary:
            object.__setattr__(self, "claim_boundary", self.verdict.claim_boundary)

    def to_dict(self) -> dict[str, Any]:
        return to_plain(self)

    def canonical_json(self) -> str:
        return canonical_json(self)

    def fingerprint(self) -> str:
        return sha256_payload(self)

"""Typed AI-MD contracts for local-first evidence bundles."""

from __future__ import annotations

from betelgeuze_ai_md.contracts.claim_scope import (
    CLAIM_SCOPE_PRODUCT_LIGAND,
    CLAIM_SCOPE_RESTRICTED_LOCAL,
    GENERAL_MD_ACCURACY_CLAIM,
    PRODUCT_CLAIM_BOUNDARY_TEXT,
    TOPOLOGY_FIDELITY_PLACEHOLDER_ALANINE,
    TOPOLOGY_FIDELITY_SEQUENCE_MAPPED,
    validate_claim_fields,
)
from betelgeuze_ai_md.contracts.input_schema import (
    AtomRecord,
    BondRecord,
    CoarseState,
    MolecularProject,
    MolecularSystem,
)
from betelgeuze_ai_md.contracts.manifest import EvidenceBundle
from betelgeuze_ai_md.contracts.output_schema import (
    AIResidualReport,
    BackmappedPose,
    InteractionEvidence,
    InteractionReport,
    TopologyValidityReport,
    TrajectorySummary,
    fail_closed_topology_report,
)
from betelgeuze_ai_md.contracts.verdict_schema import Verdict
from betelgeuze_ai_md.contracts.api_adapter import build_api_evidence_bundle, write_api_evidence_bundle
from betelgeuze_ai_md.contracts.backmapping_adapter import build_backmapped_pose
from betelgeuze_ai_md.contracts.interaction_adapter import build_interaction_report
from betelgeuze_ai_md.contracts.runner_evidence_bundle import maybe_write_runner_native_evidence_bundle
from betelgeuze_ai_md.contracts.topology_adapter import build_topology_validity_report

__all__ = [
    "AIResidualReport",
    "AtomRecord",
    "BackmappedPose",
    "BondRecord",
    "CLAIM_SCOPE_PRODUCT_LIGAND",
    "CLAIM_SCOPE_RESTRICTED_LOCAL",
    "CoarseState",
    "EvidenceBundle",
    "GENERAL_MD_ACCURACY_CLAIM",
    "InteractionEvidence",
    "InteractionReport",
    "MolecularProject",
    "MolecularSystem",
    "PRODUCT_CLAIM_BOUNDARY_TEXT",
    "TOPOLOGY_FIDELITY_PLACEHOLDER_ALANINE",
    "TOPOLOGY_FIDELITY_SEQUENCE_MAPPED",
    "TopologyValidityReport",
    "TrajectorySummary",
    "Verdict",
    "build_api_evidence_bundle",
    "build_backmapped_pose",
    "build_interaction_report",
    "build_topology_validity_report",
    "fail_closed_topology_report",
    "validate_claim_fields",
    "write_api_evidence_bundle",
    "maybe_write_runner_native_evidence_bundle",
]

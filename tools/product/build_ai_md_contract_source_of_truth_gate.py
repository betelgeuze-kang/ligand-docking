#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Callable

import numpy as np

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT_JSON = "runs/ai_md_contract_source_of_truth_gate_current.json"
DEFAULT_OUT_CSV = "runs/ai_md_contract_source_of_truth_gate_current.csv"
DEFAULT_OUT_MD = "runs/ai_md_contract_source_of_truth_gate_current.md"

CLAIM_BOUNDARY = (
    "AI-MD contract source-of-truth gate only; it checks local typed contract, API evidence-bundle, "
    "and reference-oracle surfaces. It does not run docking, execute GPU jobs, promote model outputs, "
    "widen accuracy claims, assemble customer delivery bundles, or mutate external state."
)

REQUIRED_SOURCE_FILES = [
    "pyproject.toml",
    "api/job_store.py",
    "api/main.py",
    "api/models.py",
    "api/validated_runner.py",
    "api/worker.py",
    "betelgeuze_ai_md/__init__.py",
    "betelgeuze_ai_md/contracts/__init__.py",
    "betelgeuze_ai_md/contracts/api_adapter.py",
    "betelgeuze_ai_md/contracts/backmapping_adapter.py",
    "betelgeuze_ai_md/contracts/interaction_adapter.py",
    "betelgeuze_ai_md/contracts/topology_adapter.py",
    "betelgeuze_ai_md/contracts/claim_scope.py",
    "betelgeuze_ai_md/contracts/input_schema.py",
    "betelgeuze_ai_md/contracts/output_schema.py",
    "betelgeuze_ai_md/contracts/verdict_schema.py",
    "betelgeuze_ai_md/contracts/manifest.py",
    "betelgeuze_ai_md/contracts/serialization.py",
    "betelgeuze_ai_md/coarse_md/__init__.py",
    "betelgeuze_ai_md/coarse_md/numpy_ref.py",
    "tools/product/validate_api_runner_profiles.py",
    "tests/unit/test_api_job_store.py",
    "tests/unit/test_api_validated_runner_adapter.py",
    "tests/unit/test_betelgeuze_ai_md_contracts.py",
    "tests/unit/test_betelgeuze_ai_md_api_adapter.py",
    "tests/unit/test_betelgeuze_ai_md_backmapping_interaction_adapters.py",
    "tests/unit/test_betelgeuze_ai_md_topology_adapter.py",
    "tests/unit/test_betelgeuze_ai_md_numpy_ref.py",
]


def _resolve(path_like: str | Path, *, root: Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else root / path


def _sha256_file(path: Path) -> str:
    if not path.is_file():
        return ""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _row(
    *,
    check_id: str,
    category: str,
    passed: bool,
    observed: str,
    required: str,
    artifact_paths: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "check_id": check_id,
        "category": category,
        "status": "pass" if passed else "fail",
        "observed": observed,
        "required": required,
        "artifact_paths": artifact_paths or [],
        "artifact_path_count": len(artifact_paths or []),
        "release_blocker": not passed,
        "execution_enabled": False,
        "external_state_mutated": False,
    }


def _safe_check(check: Callable[[], dict[str, Any]]) -> dict[str, Any]:
    try:
        return check()
    except Exception as exc:
        return _row(
            check_id=getattr(check, "__name__", "unknown_check").removeprefix("_check_"),
            category="runtime_exception",
            passed=False,
            observed=f"{type(exc).__name__}: {exc}",
            required="check completes without exception",
        )


def _check_required_source_files(root: Path, required_source_files: list[str]) -> dict[str, Any]:
    missing = [path for path in required_source_files if not _resolve(path, root=root).is_file()]
    digest = hashlib.sha256()
    for path in required_source_files:
        resolved = _resolve(path, root=root)
        digest.update(path.encode("utf-8"))
        digest.update(_sha256_file(resolved).encode("utf-8"))
    return _row(
        check_id="required_source_files_present",
        category="contract_source_files",
        passed=not missing,
        observed=f"required={len(required_source_files)};missing={len(missing)}",
        required="all AI-MD contract, API adapter, reference oracle, and focused test files exist",
        artifact_paths=required_source_files,
    ) | {
        "missing_source_files": missing,
        "missing_source_file_count": len(missing),
        "source_set_sha256": digest.hexdigest(),
    }


def _check_pyproject_package_discovery(root: Path) -> dict[str, Any]:
    pyproject = _resolve("pyproject.toml", root=root)
    text = pyproject.read_text(encoding="utf-8") if pyproject.is_file() else ""
    required_fragment = '"betelgeuze_ai_md*"'
    passed = required_fragment in text
    return _row(
        check_id="pyproject_package_discovery",
        category="contract_source_files",
        passed=passed,
        observed=f"betelgeuze_ai_md_package_glob_present={passed}",
        required='pyproject package discovery includes "betelgeuze_ai_md*"',
        artifact_paths=["pyproject.toml"],
    )


def _check_contract_symbols_exported() -> dict[str, Any]:
    import betelgeuze_ai_md.contracts as contracts

    required_symbols = [
        "MolecularProject",
        "MolecularSystem",
        "CoarseState",
        "TrajectorySummary",
        "BackmappedPose",
        "InteractionEvidence",
        "InteractionReport",
        "AIResidualReport",
        "TopologyValidityReport",
        "Verdict",
        "EvidenceBundle",
        "build_api_evidence_bundle",
        "build_backmapped_pose",
        "build_interaction_report",
        "build_topology_validity_report",
        "write_api_evidence_bundle",
        "fail_closed_topology_report",
    ]
    missing = [symbol for symbol in required_symbols if not hasattr(contracts, symbol)]
    return _row(
        check_id="contract_symbols_exported",
        category="contract_layer",
        passed=not missing,
        observed=f"required_symbols={len(required_symbols)};missing={len(missing)}",
        required="contract package exports all required input, output, verdict, bundle, and API adapter symbols",
    ) | {"missing_symbols": missing, "missing_symbol_count": len(missing)}


def _check_claim_widening_guard() -> dict[str, Any]:
    from betelgeuze_ai_md.contracts import GENERAL_MD_ACCURACY_CLAIM, TOPOLOGY_FIDELITY_SEQUENCE_MAPPED, Verdict
    from betelgeuze_ai_md.contracts.errors import ContractValidationError

    blocked = False
    try:
        Verdict(
            claim_safe=False,
            verdict_label="blocked",
            topology_fidelity=TOPOLOGY_FIDELITY_SEQUENCE_MAPPED,
            accuracy_claim_grade=GENERAL_MD_ACCURACY_CLAIM,
        )
    except ContractValidationError:
        blocked = True
    return _row(
        check_id="claim_widening_guard",
        category="claim_boundary",
        passed=blocked,
        observed=f"general_md_accuracy_claim_blocked={blocked}",
        required="general-MD-accuracy promotion remains forbidden by contract validation",
    )


def _check_ai_residual_report_surface() -> dict[str, Any]:
    from betelgeuze_ai_md.contracts import AIResidualReport
    from betelgeuze_ai_md.contracts.errors import ContractValidationError

    bounded = AIResidualReport(
        residual_mode="assist",
        correction_applied=True,
        uncertainty=0.2,
        abstained=False,
        residual_delta=2.0,
        bounded_residual_delta=0.6,
        max_delta=1.0,
        guard=0.75,
        active_score_col="binding_score_composite_v7_residual_active",
        base_score_col="binding_score_composite_v7",
        ranking_changed=True,
        guard_components={"topology": 1.0, "domain": 0.75, "calibration": 1.0},
    )
    bounded_ok = (
        bounded.bounded_residual_delta == 0.6
        and bounded.active_score_col == "binding_score_composite_v7_residual_active"
        and bounded.ranking_changed is True
        and "residual_delta_review_required" in bounded.review_flags
    )
    unbounded_blocked = False
    try:
        AIResidualReport(
            residual_mode="assist",
            correction_applied=True,
            bounded_residual_delta=1.1,
            max_delta=1.0,
            guard=1.0,
        )
    except ContractValidationError:
        unbounded_blocked = True
    missing_active_score_blocked = False
    try:
        AIResidualReport(
            ranking_changed=True,
            bounded_residual_delta=0.1,
            max_delta=1.0,
            guard=1.0,
        )
    except ContractValidationError:
        missing_active_score_blocked = True

    passed = bounded_ok and unbounded_blocked and missing_active_score_blocked
    return _row(
        check_id="ai_residual_report_surface",
        category="contract_layer",
        passed=passed,
        observed=(
            f"bounded_ok={bounded_ok};unbounded_blocked={unbounded_blocked};"
            f"missing_active_score_blocked={missing_active_score_blocked}"
        ),
        required=(
            "AIResidualReport records bounded residual delta, active score column, guard components, "
            "review flag, and blocks unbounded or unreported ranking-changing corrections"
        ),
    ) | {
        "bounded_ok": bounded_ok,
        "unbounded_blocked": unbounded_blocked,
        "missing_active_score_blocked": missing_active_score_blocked,
    }


def _check_topology_validity_contract_surface() -> dict[str, Any]:
    from betelgeuze_ai_md.contracts import (
        CLAIM_SCOPE_RESTRICTED_LOCAL,
        EvidenceBundle,
        TOPOLOGY_FIDELITY_PLACEHOLDER_ALANINE,
        TOPOLOGY_FIDELITY_SEQUENCE_MAPPED,
        TopologyValidityReport,
        Verdict,
        fail_closed_topology_report,
    )
    from betelgeuze_ai_md.contracts.errors import ContractValidationError
    from betelgeuze_ai_md.contracts.output_schema import AIResidualReport, BackmappedPose, InteractionReport, TrajectorySummary

    placeholder_blocked = False
    try:
        EvidenceBundle(
            bundle_id="topology_blocked",
            project_id="topology_blocked",
            ranked_shortlist=[],
            trajectory_summary=TrajectorySummary(frame_count=0),
            backmapped_poses=[],
            interaction_report=InteractionReport(),
            topology_report=TopologyValidityReport(
                status="pass",
                topology_fidelity=TOPOLOGY_FIDELITY_PLACEHOLDER_ALANINE,
            ),
            ai_residual_report=AIResidualReport(uncertainty=0.35),
            failure_flags=[],
            source_hashes={
                "input_hash": "i" * 64,
                "config_hash": "c" * 64,
                "model_hash": "m" * 64,
                "executable_hash": "e" * 64,
            },
            viewer_assets=[],
            wetlab_handoff_table=[],
            verdict=Verdict(
                claim_safe=True,
                verdict_label="delivery_ready",
                claim_scope=CLAIM_SCOPE_RESTRICTED_LOCAL,
                topology_fidelity=TOPOLOGY_FIDELITY_PLACEHOLDER_ALANINE,
            ),
        )
    except ContractValidationError as exc:
        placeholder_blocked = "non-placeholder topology fidelity" in str(exc)

    blocker_blocked = False
    try:
        EvidenceBundle(
            bundle_id="topology_blocker",
            project_id="topology_blocker",
            ranked_shortlist=[],
            trajectory_summary=TrajectorySummary(frame_count=0),
            backmapped_poses=[],
            interaction_report=InteractionReport(),
            topology_report=TopologyValidityReport(
                status="pass",
                topology_fidelity=TOPOLOGY_FIDELITY_SEQUENCE_MAPPED,
                claim_blockers=["sequence_mapping_unresolved"],
            ),
            ai_residual_report=AIResidualReport(uncertainty=0.35),
            failure_flags=[],
            source_hashes={
                "input_hash": "i" * 64,
                "config_hash": "c" * 64,
                "model_hash": "m" * 64,
                "executable_hash": "e" * 64,
            },
            viewer_assets=[],
            wetlab_handoff_table=[],
            verdict=Verdict(
                claim_safe=True,
                verdict_label="delivery_ready",
                claim_scope=CLAIM_SCOPE_RESTRICTED_LOCAL,
                topology_fidelity=TOPOLOGY_FIDELITY_SEQUENCE_MAPPED,
            ),
        )
    except ContractValidationError as exc:
        blocker_blocked = "topology claim blockers" in str(exc)

    fail_closed = fail_closed_topology_report()
    fail_closed_ok = (
        fail_closed.status == "not_assessed"
        and fail_closed.topology_fidelity == TOPOLOGY_FIDELITY_PLACEHOLDER_ALANINE
        and "topology_validity_not_assessed" in fail_closed.claim_blockers
    )
    passed = placeholder_blocked and blocker_blocked and fail_closed_ok
    return _row(
        check_id="topology_validity_contract_surface",
        category="contract_layer",
        passed=passed,
        observed=(
            f"placeholder_blocked={placeholder_blocked};blocker_blocked={blocker_blocked};"
            f"fail_closed_ok={fail_closed_ok}"
        ),
        required=(
            "TopologyValidityReport blocks claim-safe with placeholder alanine or topology claim blockers "
            "and fail_closed_topology_report emits explicit not-assessed claim blockers"
        ),
    ) | {
        "placeholder_blocked": placeholder_blocked,
        "blocker_blocked": blocker_blocked,
        "fail_closed_ok": fail_closed_ok,
    }


def _check_evidence_bundle_trajectory_claim_gate() -> dict[str, Any]:
    from betelgeuze_ai_md.contracts import (
        CLAIM_SCOPE_RESTRICTED_LOCAL,
        EvidenceBundle,
        TOPOLOGY_FIDELITY_SEQUENCE_MAPPED,
        TopologyValidityReport,
        Verdict,
    )
    from betelgeuze_ai_md.contracts.errors import ContractValidationError
    from betelgeuze_ai_md.contracts.output_schema import (
        AIResidualReport,
        BackmappedPose,
        InteractionEvidence,
        InteractionReport,
        TrajectorySummary,
    )

    base_payload = {
        "bundle_id": "trajectory_claim_gate",
        "project_id": "trajectory_claim_gate",
        "ranked_shortlist": [{"ligand_id": "lig1", "rank": 1, "score": -1.0}],
        "backmapped_poses": [
            BackmappedPose(
                pose_id="pose_001",
                structure_path="runs/example/pose_001.sdf",
                structure_sha256="p" * 64,
                chemical_validity_summary={"status": "pass"},
                backmap_confidence=0.8,
            )
        ],
        "interaction_report": InteractionReport(
            interactions=[
                InteractionEvidence(
                    interaction_id="hbond_001",
                    interaction_type="hbond",
                    partners=["SER:OG", "lig1:O1"],
                    occupancy=0.6,
                    confidence=0.8,
                )
            ],
            interaction_confidence=0.7,
        ),
        "topology_report": TopologyValidityReport(
            status="pass",
            topology_fidelity=TOPOLOGY_FIDELITY_SEQUENCE_MAPPED,
        ),
        "ai_residual_report": AIResidualReport(uncertainty=0.35),
        "failure_flags": [],
        "source_hashes": {
            "input_hash": "i" * 64,
            "config_hash": "c" * 64,
            "model_hash": "m" * 64,
            "executable_hash": "e" * 64,
        },
        "viewer_assets": [],
        "wetlab_handoff_table": [{"ligand_id": "lig1", "recommendation": "review"}],
        "verdict": Verdict(
            claim_safe=True,
            verdict_label="delivery_ready",
            claim_scope=CLAIM_SCOPE_RESTRICTED_LOCAL,
            topology_fidelity=TOPOLOGY_FIDELITY_SEQUENCE_MAPPED,
        ),
    }
    empty_frame_blocked = False
    try:
        EvidenceBundle(**{**base_payload, "trajectory_summary": TrajectorySummary(frame_count=0)})
    except ContractValidationError as exc:
        empty_frame_blocked = "trajectory frames" in str(exc)
    empty_energy_trace_blocked = False
    try:
        EvidenceBundle(
            **{
                **base_payload,
                "trajectory_summary": TrajectorySummary(
                    frame_count=1,
                    energy_trace=[],
                    contact_trace=[0.0],
                    stability_score=0.5,
                    mean_min_distance=2.0,
                ),
            }
        )
    except ContractValidationError as exc:
        empty_energy_trace_blocked = "trajectory energy trace" in str(exc)
    ok_bundle = EvidenceBundle(
        **{
            **base_payload,
            "trajectory_summary": TrajectorySummary(
                frame_count=1,
                energy_trace=[0.0],
                contact_trace=[0.0],
                stability_score=0.5,
                mean_min_distance=2.0,
            ),
        }
    )
    positive_summary_ok = ok_bundle.trajectory_summary.frame_count == 1 and len(ok_bundle.fingerprint()) == 64
    passed = empty_frame_blocked and empty_energy_trace_blocked and positive_summary_ok
    return _row(
        check_id="evidence_bundle_trajectory_claim_gate",
        category="contract_layer",
        passed=passed,
        observed=(
            f"empty_frame_blocked={empty_frame_blocked};"
            f"empty_energy_trace_blocked={empty_energy_trace_blocked};"
            f"positive_summary_ok={positive_summary_ok}"
        ),
        required=(
            "claim_safe EvidenceBundle requires non-empty coarse dynamics trajectory frames and energy trace, "
            "while accepting a bounded positive TrajectorySummary"
        ),
    ) | {
        "empty_frame_blocked": empty_frame_blocked,
        "empty_energy_trace_blocked": empty_energy_trace_blocked,
        "positive_summary_ok": positive_summary_ok,
    }


def _check_evidence_bundle_backmapped_pose_claim_gate() -> dict[str, Any]:
    from betelgeuze_ai_md.contracts import (
        CLAIM_SCOPE_RESTRICTED_LOCAL,
        EvidenceBundle,
        TOPOLOGY_FIDELITY_SEQUENCE_MAPPED,
        TopologyValidityReport,
        Verdict,
    )
    from betelgeuze_ai_md.contracts.errors import ContractValidationError
    from betelgeuze_ai_md.contracts.output_schema import (
        AIResidualReport,
        BackmappedPose,
        InteractionEvidence,
        InteractionReport,
        TrajectorySummary,
    )

    base_payload = {
        "bundle_id": "backmapped_pose_claim_gate",
        "project_id": "backmapped_pose_claim_gate",
        "ranked_shortlist": [{"ligand_id": "lig1", "rank": 1, "score": -1.0}],
        "trajectory_summary": TrajectorySummary(
            frame_count=1,
            energy_trace=[0.0],
            contact_trace=[0.0],
            stability_score=0.5,
            mean_min_distance=2.0,
        ),
        "interaction_report": InteractionReport(
            interactions=[
                InteractionEvidence(
                    interaction_id="hbond_001",
                    interaction_type="hbond",
                    partners=["SER:OG", "lig1:O1"],
                    occupancy=0.6,
                    confidence=0.8,
                )
            ],
            interaction_confidence=0.7,
        ),
        "topology_report": TopologyValidityReport(
            status="pass",
            topology_fidelity=TOPOLOGY_FIDELITY_SEQUENCE_MAPPED,
        ),
        "ai_residual_report": AIResidualReport(uncertainty=0.35),
        "failure_flags": [],
        "source_hashes": {
            "input_hash": "i" * 64,
            "config_hash": "c" * 64,
            "model_hash": "m" * 64,
            "executable_hash": "e" * 64,
        },
        "viewer_assets": [],
        "wetlab_handoff_table": [{"ligand_id": "lig1", "recommendation": "review"}],
        "verdict": Verdict(
            claim_safe=True,
            verdict_label="delivery_ready",
            claim_scope=CLAIM_SCOPE_RESTRICTED_LOCAL,
            topology_fidelity=TOPOLOGY_FIDELITY_SEQUENCE_MAPPED,
        ),
    }
    empty_pose_blocked = False
    try:
        EvidenceBundle(**{**base_payload, "backmapped_poses": []})
    except ContractValidationError as exc:
        empty_pose_blocked = "backmapped poses" in str(exc)
    ok_bundle = EvidenceBundle(
        **{
            **base_payload,
            "backmapped_poses": [
                BackmappedPose(
                    pose_id="pose_001",
                    structure_path="runs/example/pose_001.sdf",
                    structure_sha256="p" * 64,
                    chemical_validity_summary={"status": "pass"},
                    backmap_confidence=0.8,
                )
            ],
        }
    )
    positive_pose_ok = len(ok_bundle.backmapped_poses) == 1 and len(ok_bundle.fingerprint()) == 64
    passed = empty_pose_blocked and positive_pose_ok
    return _row(
        check_id="evidence_bundle_backmapped_pose_claim_gate",
        category="contract_layer",
        passed=passed,
        observed=f"empty_pose_blocked={empty_pose_blocked};positive_pose_ok={positive_pose_ok}",
        required=(
            "claim_safe EvidenceBundle requires at least one all-atom backmapped pose while accepting "
            "a chemically passing positive pose"
        ),
    ) | {
        "empty_pose_blocked": empty_pose_blocked,
        "positive_pose_ok": positive_pose_ok,
    }


def _check_evidence_bundle_interaction_claim_gate() -> dict[str, Any]:
    from betelgeuze_ai_md.contracts import (
        CLAIM_SCOPE_RESTRICTED_LOCAL,
        EvidenceBundle,
        TOPOLOGY_FIDELITY_SEQUENCE_MAPPED,
        TopologyValidityReport,
        Verdict,
    )
    from betelgeuze_ai_md.contracts.errors import ContractValidationError
    from betelgeuze_ai_md.contracts.output_schema import (
        AIResidualReport,
        BackmappedPose,
        InteractionEvidence,
        InteractionReport,
        TrajectorySummary,
    )

    base_payload = {
        "bundle_id": "interaction_claim_gate",
        "project_id": "interaction_claim_gate",
        "ranked_shortlist": [{"ligand_id": "lig1", "rank": 1, "score": -1.0}],
        "trajectory_summary": TrajectorySummary(
            frame_count=1,
            energy_trace=[0.0],
            contact_trace=[0.0],
            stability_score=0.5,
            mean_min_distance=2.0,
        ),
        "backmapped_poses": [
            BackmappedPose(
                pose_id="pose_001",
                structure_path="runs/example/pose_001.sdf",
                structure_sha256="p" * 64,
                chemical_validity_summary={"status": "pass"},
                backmap_confidence=0.8,
            )
        ],
        "topology_report": TopologyValidityReport(
            status="pass",
            topology_fidelity=TOPOLOGY_FIDELITY_SEQUENCE_MAPPED,
        ),
        "ai_residual_report": AIResidualReport(uncertainty=0.35),
        "failure_flags": [],
        "source_hashes": {
            "input_hash": "i" * 64,
            "config_hash": "c" * 64,
            "model_hash": "m" * 64,
            "executable_hash": "e" * 64,
        },
        "viewer_assets": [],
        "wetlab_handoff_table": [{"ligand_id": "lig1", "recommendation": "review"}],
        "verdict": Verdict(
            claim_safe=True,
            verdict_label="delivery_ready",
            claim_scope=CLAIM_SCOPE_RESTRICTED_LOCAL,
            topology_fidelity=TOPOLOGY_FIDELITY_SEQUENCE_MAPPED,
        ),
    }
    empty_interaction_blocked = False
    try:
        EvidenceBundle(
            **{
                **base_payload,
                "interaction_report": InteractionReport(interactions=[], interaction_confidence=0.7),
            }
        )
    except ContractValidationError as exc:
        empty_interaction_blocked = "interaction evidence" in str(exc)
    zero_confidence_blocked = False
    try:
        EvidenceBundle(
            **{
                **base_payload,
                "interaction_report": InteractionReport(
                    interactions=[
                        InteractionEvidence(
                            interaction_id="hbond_001",
                            interaction_type="hbond",
                            partners=["SER:OG", "lig1:O1"],
                            occupancy=0.6,
                            confidence=0.8,
                        )
                    ],
                    interaction_confidence=0.0,
                ),
            }
        )
    except ContractValidationError as exc:
        zero_confidence_blocked = "positive interaction confidence" in str(exc)
    ok_bundle = EvidenceBundle(
        **{
            **base_payload,
            "interaction_report": InteractionReport(
                interactions=[
                    InteractionEvidence(
                        interaction_id="hbond_001",
                        interaction_type="hbond",
                        partners=["SER:OG", "lig1:O1"],
                        occupancy=0.6,
                        confidence=0.8,
                    )
                ],
                interaction_confidence=0.7,
            ),
        }
    )
    positive_interaction_ok = len(ok_bundle.interaction_report.interactions) == 1 and len(ok_bundle.fingerprint()) == 64
    passed = empty_interaction_blocked and zero_confidence_blocked and positive_interaction_ok
    return _row(
        check_id="evidence_bundle_interaction_claim_gate",
        category="contract_layer",
        passed=passed,
        observed=(
            f"empty_interaction_blocked={empty_interaction_blocked};"
            f"zero_confidence_blocked={zero_confidence_blocked};"
            f"positive_interaction_ok={positive_interaction_ok}"
        ),
        required=(
            "claim_safe EvidenceBundle requires non-empty H-bond/interaction evidence with positive "
            "interaction confidence while accepting a positive interaction report"
        ),
    ) | {
        "empty_interaction_blocked": empty_interaction_blocked,
        "zero_confidence_blocked": zero_confidence_blocked,
        "positive_interaction_ok": positive_interaction_ok,
    }


def _check_evidence_bundle_product_output_claim_gate() -> dict[str, Any]:
    from betelgeuze_ai_md.contracts import (
        CLAIM_SCOPE_RESTRICTED_LOCAL,
        EvidenceBundle,
        TOPOLOGY_FIDELITY_SEQUENCE_MAPPED,
        TopologyValidityReport,
        Verdict,
    )
    from betelgeuze_ai_md.contracts.errors import ContractValidationError
    from betelgeuze_ai_md.contracts.output_schema import (
        AIResidualReport,
        BackmappedPose,
        InteractionEvidence,
        InteractionReport,
        TrajectorySummary,
    )

    base_payload = {
        "bundle_id": "product_output_claim_gate",
        "project_id": "product_output_claim_gate",
        "trajectory_summary": TrajectorySummary(
            frame_count=1,
            energy_trace=[0.0],
            contact_trace=[0.0],
            stability_score=0.5,
            mean_min_distance=2.0,
        ),
        "backmapped_poses": [
            BackmappedPose(
                pose_id="pose_001",
                structure_path="runs/example/pose_001.sdf",
                structure_sha256="p" * 64,
                chemical_validity_summary={"status": "pass"},
                backmap_confidence=0.8,
            )
        ],
        "interaction_report": InteractionReport(
            interactions=[
                InteractionEvidence(
                    interaction_id="hbond_001",
                    interaction_type="hbond",
                    partners=["SER:OG", "lig1:O1"],
                    occupancy=0.6,
                    confidence=0.8,
                )
            ],
            interaction_confidence=0.7,
        ),
        "topology_report": TopologyValidityReport(
            status="pass",
            topology_fidelity=TOPOLOGY_FIDELITY_SEQUENCE_MAPPED,
        ),
        "ai_residual_report": AIResidualReport(uncertainty=0.35),
        "failure_flags": [],
        "source_hashes": {
            "input_hash": "i" * 64,
            "config_hash": "c" * 64,
            "model_hash": "m" * 64,
            "executable_hash": "e" * 64,
        },
        "viewer_assets": [],
        "verdict": Verdict(
            claim_safe=True,
            verdict_label="delivery_ready",
            claim_scope=CLAIM_SCOPE_RESTRICTED_LOCAL,
            topology_fidelity=TOPOLOGY_FIDELITY_SEQUENCE_MAPPED,
        ),
    }
    empty_shortlist_blocked = False
    try:
        EvidenceBundle(
            **{
                **base_payload,
                "ranked_shortlist": [],
                "wetlab_handoff_table": [{"ligand_id": "lig1", "recommendation": "review"}],
            }
        )
    except ContractValidationError as exc:
        empty_shortlist_blocked = "ranked shortlist" in str(exc)
    empty_handoff_blocked = False
    try:
        EvidenceBundle(
            **{
                **base_payload,
                "ranked_shortlist": [{"ligand_id": "lig1", "rank": 1, "score": -1.0}],
                "wetlab_handoff_table": [],
            }
        )
    except ContractValidationError as exc:
        empty_handoff_blocked = "wetlab handoff table" in str(exc)
    ok_bundle = EvidenceBundle(
        **{
            **base_payload,
            "ranked_shortlist": [{"ligand_id": "lig1", "rank": 1, "score": -1.0}],
            "wetlab_handoff_table": [{"ligand_id": "lig1", "recommendation": "review"}],
        }
    )
    positive_product_outputs_ok = (
        len(ok_bundle.ranked_shortlist) == 1
        and len(ok_bundle.wetlab_handoff_table) == 1
        and len(ok_bundle.fingerprint()) == 64
    )
    passed = empty_shortlist_blocked and empty_handoff_blocked and positive_product_outputs_ok
    return _row(
        check_id="evidence_bundle_product_output_claim_gate",
        category="contract_layer",
        passed=passed,
        observed=(
            f"empty_shortlist_blocked={empty_shortlist_blocked};"
            f"empty_handoff_blocked={empty_handoff_blocked};"
            f"positive_product_outputs_ok={positive_product_outputs_ok}"
        ),
        required=(
            "claim_safe EvidenceBundle requires ranked shortlist and wetlab handoff table product outputs "
            "while accepting positive output tables"
        ),
    ) | {
        "empty_shortlist_blocked": empty_shortlist_blocked,
        "empty_handoff_blocked": empty_handoff_blocked,
        "positive_product_outputs_ok": positive_product_outputs_ok,
    }


def _check_evidence_bundle_ai_uncertainty_claim_gate() -> dict[str, Any]:
    from betelgeuze_ai_md.contracts import (
        CLAIM_SCOPE_RESTRICTED_LOCAL,
        EvidenceBundle,
        TOPOLOGY_FIDELITY_SEQUENCE_MAPPED,
        TopologyValidityReport,
        Verdict,
    )
    from betelgeuze_ai_md.contracts.errors import ContractValidationError
    from betelgeuze_ai_md.contracts.output_schema import (
        AIResidualReport,
        BackmappedPose,
        InteractionEvidence,
        InteractionReport,
        TrajectorySummary,
    )

    base_payload = {
        "bundle_id": "ai_uncertainty_claim_gate",
        "project_id": "ai_uncertainty_claim_gate",
        "ranked_shortlist": [{"ligand_id": "lig1", "rank": 1, "score": -1.0}],
        "trajectory_summary": TrajectorySummary(
            frame_count=1,
            energy_trace=[0.0],
            contact_trace=[0.0],
            stability_score=0.5,
            mean_min_distance=2.0,
        ),
        "backmapped_poses": [
            BackmappedPose(
                pose_id="pose_001",
                structure_path="runs/example/pose_001.sdf",
                structure_sha256="p" * 64,
                chemical_validity_summary={"status": "pass"},
                backmap_confidence=0.8,
            )
        ],
        "interaction_report": InteractionReport(
            interactions=[
                InteractionEvidence(
                    interaction_id="hbond_001",
                    interaction_type="hbond",
                    partners=["SER:OG", "lig1:O1"],
                    occupancy=0.6,
                    confidence=0.8,
                )
            ],
            interaction_confidence=0.7,
        ),
        "topology_report": TopologyValidityReport(
            status="pass",
            topology_fidelity=TOPOLOGY_FIDELITY_SEQUENCE_MAPPED,
        ),
        "ai_residual_report": AIResidualReport(uncertainty=0.35),
        "failure_flags": [],
        "source_hashes": {
            "input_hash": "i" * 64,
            "config_hash": "c" * 64,
            "model_hash": "m" * 64,
            "executable_hash": "e" * 64,
        },
        "viewer_assets": [],
        "wetlab_handoff_table": [{"ligand_id": "lig1", "recommendation": "review"}],
        "verdict": Verdict(
            claim_safe=True,
            verdict_label="delivery_ready",
            claim_scope=CLAIM_SCOPE_RESTRICTED_LOCAL,
            topology_fidelity=TOPOLOGY_FIDELITY_SEQUENCE_MAPPED,
        ),
    }
    high_uncertainty_blocked = False
    try:
        EvidenceBundle(
            **{
                **base_payload,
                "ai_residual_report": AIResidualReport(uncertainty=0.36),
            }
        )
    except ContractValidationError as exc:
        high_uncertainty_blocked = "high AI uncertainty" in str(exc)
    review_flag_blocked = False
    try:
        EvidenceBundle(
            **{
                **base_payload,
                "ai_residual_report": AIResidualReport(
                    uncertainty=0.35,
                    review_flags=["manual_review_required"],
                ),
            }
        )
    except ContractValidationError as exc:
        review_flag_blocked = "AI residual review flags" in str(exc)
    ok_bundle = EvidenceBundle(**base_payload)
    low_uncertainty_ok = ok_bundle.ai_residual_report.uncertainty == 0.35 and len(ok_bundle.fingerprint()) == 64
    passed = high_uncertainty_blocked and review_flag_blocked and low_uncertainty_ok
    return _row(
        check_id="evidence_bundle_ai_uncertainty_claim_gate",
        category="contract_layer",
        passed=passed,
        observed=(
            f"high_uncertainty_blocked={high_uncertainty_blocked};"
            f"review_flag_blocked={review_flag_blocked};"
            f"low_uncertainty_ok={low_uncertainty_ok}"
        ),
        required=(
            "claim_safe EvidenceBundle rejects high AI uncertainty and any AI residual review flags "
            "while accepting uncertainty at the review threshold"
        ),
    ) | {
        "high_uncertainty_blocked": high_uncertainty_blocked,
        "review_flag_blocked": review_flag_blocked,
        "low_uncertainty_ok": low_uncertainty_ok,
    }


def _check_topology_factory_adapter() -> dict[str, Any]:
    import inspect
    from pathlib import Path

    from betelgeuze_ai_md.contracts import (
        TOPOLOGY_FIDELITY_PLACEHOLDER_ALANINE,
        TOPOLOGY_FIDELITY_SEQUENCE_MAPPED,
        build_topology_validity_report,
    )
    import betelgeuze_ai_md.contracts.topology_adapter as topology_adapter_mod

    adapter_source = Path(inspect.getsourcefile(topology_adapter_mod) or "")
    adapter_text = adapter_source.read_text(encoding="utf-8") if adapter_source.is_file() else ""
    no_torch_import = "import torch" not in adapter_text and "from torch" not in adapter_text

    placeholder = build_topology_validity_report(
        {
            "topology_fidelity": TOPOLOGY_FIDELITY_PLACEHOLDER_ALANINE,
            "n_res": 4,
        }
    )
    placeholder_ok = (
        placeholder.status == "not_assessed"
        and placeholder.topology_fidelity == TOPOLOGY_FIDELITY_PLACEHOLDER_ALANINE
        and "topology_validity_not_assessed" in placeholder.claim_blockers
        and "placeholder_topology_fidelity" in placeholder.claim_blockers
    )

    class _SequenceMappedTopology:
        n_res = 5
        residue_types_source = TOPOLOGY_FIDELITY_SEQUENCE_MAPPED
        claim_metadata = {"topology_fidelity": TOPOLOGY_FIDELITY_SEQUENCE_MAPPED}

        def topology_fidelity(self) -> str:
            return TOPOLOGY_FIDELITY_SEQUENCE_MAPPED

        class _ResidueTypes:
            shape = (5,)

        residue_types = _ResidueTypes()

    sequence_mapped = build_topology_validity_report(_SequenceMappedTopology())
    sequence_mapped_ok = (
        sequence_mapped.status == "pass"
        and sequence_mapped.topology_fidelity == TOPOLOGY_FIDELITY_SEQUENCE_MAPPED
        and sequence_mapped.validity_rows
        and not sequence_mapped.claim_blockers
        and any(row.get("check_id") == "residue_count_coherent" for row in sequence_mapped.validity_rows)
    )

    passed = no_torch_import and placeholder_ok and sequence_mapped_ok
    return _row(
        check_id="topology_factory_adapter_surface",
        category="contract_layer",
        passed=passed,
        observed=(
            f"no_torch_import={no_torch_import};placeholder_ok={placeholder_ok};"
            f"sequence_mapped_ok={sequence_mapped_ok}"
        ),
        required=(
            "topology adapter exports fail-closed placeholder and passing sequence-mapped "
            "TopologyValidityReport surfaces without importing torch at module import time"
        ),
    ) | {
        "no_torch_import": no_torch_import,
        "placeholder_ok": placeholder_ok,
        "sequence_mapped_ok": sequence_mapped_ok,
    }


def _check_backmapping_interaction_adapter_surface() -> dict[str, Any]:
    import inspect
    from pathlib import Path

    import betelgeuze_ai_md.contracts.backmapping_adapter as backmapping_adapter_mod
    import betelgeuze_ai_md.contracts.interaction_adapter as interaction_adapter_mod
    from betelgeuze_ai_md.contracts import build_backmapped_pose, build_interaction_report

    backmapping_source = Path(inspect.getsourcefile(backmapping_adapter_mod) or "")
    interaction_source = Path(inspect.getsourcefile(interaction_adapter_mod) or "")
    backmapping_text = backmapping_source.read_text(encoding="utf-8") if backmapping_source.is_file() else ""
    interaction_text = interaction_source.read_text(encoding="utf-8") if interaction_source.is_file() else ""
    no_torch_import = (
        "import torch" not in backmapping_text
        and "from torch" not in backmapping_text
        and "import torch" not in interaction_text
        and "from torch" not in interaction_text
    )

    ok_pose = build_backmapped_pose(
        {
            "pose_id": "pose_ok_001",
            "structure_path": "runs/pose_ok_001.sdf",
            "structure_sha256": "a" * 64,
            "repair_operations": ["kabsch_alignment"],
            "backmap_status": "ok",
            "site_count": 4,
            "elements": ["O", "N", "S", "P"],
            "roles": ["acceptor", "donor", "donor", "acceptor"],
            "backmap_confidence": 0.92,
        }
    )
    ok_pose_ok = (
        ok_pose.chemical_validity_summary.get("status") == "pass"
        and ok_pose.chemical_validity_summary.get("check_id") == "onsps_4bead_backmap"
        and ok_pose.chemical_validity_summary.get("site_count") == 4
        and 0.0 <= ok_pose.backmap_confidence <= 1.0
        and not ok_pose.chemical_validity_summary.get("claim_blockers")
    )

    no_sites_pose = build_backmapped_pose(
        {
            "pose_id": "pose_empty_001",
            "structure_path": "runs/pose_empty_001.sdf",
            "structure_sha256": "b" * 64,
            "backmap_status": "no_onsps_sites",
            "site_count": 0,
        }
    )
    no_sites_fail_closed = (
        no_sites_pose.chemical_validity_summary.get("status") == "not_assessed"
        and "backmapping_no_onsps_sites" in no_sites_pose.chemical_validity_summary.get(
            "claim_blockers", []
        )
        and no_sites_pose.backmap_confidence == 0.0
    )

    empty_pose = build_backmapped_pose(
        {
            "pose_id": "pose_empty_002",
            "structure_path": "runs/pose_empty_002.sdf",
            "structure_sha256": "c" * 64,
            "backmap_status": "empty_input",
        }
    )
    empty_fail_closed = (
        empty_pose.chemical_validity_summary.get("status") == "not_assessed"
        and "backmapping_empty_input" in empty_pose.chemical_validity_summary.get(
            "claim_blockers", []
        )
        and empty_pose.backmap_confidence == 0.0
    )

    missing_interactions = build_interaction_report()
    missing_ok = "interaction_evidence_missing" in missing_interactions.claim_blockers
    missing_confidence_zero = missing_interactions.interaction_confidence == 0.0

    role_invalid_report = build_interaction_report(
        interactions=[
            {
                "interaction_id": "hbond_001",
                "interaction_type": "hbond",
                "partners": ["SER:OG", "lig1:O1"],
                "distance": 2.9,
                "occupancy": 0.5,
                "confidence": 0.7,
                "role_valid": False,
            }
        ]
    )
    role_invalid_ok = (
        "interaction_role_invalid" in role_invalid_report.claim_blockers
        and role_invalid_report.interactions[0].role_valid is False
    )

    unsupported_report = build_interaction_report(
        interactions=[
            {
                "interaction_id": "weird_001",
                "interaction_type": "weird_chemistry",
                "partners": ["A", "B"],
                "occupancy": 0.4,
                "confidence": 0.6,
            }
        ]
    )
    unsupported_ok = "interaction_type_unsupported" in unsupported_report.claim_blockers

    passed = (
        no_torch_import
        and ok_pose_ok
        and no_sites_fail_closed
        and empty_fail_closed
        and missing_ok
        and missing_confidence_zero
        and role_invalid_ok
        and unsupported_ok
    )
    return _row(
        check_id="backmapping_interaction_adapter_surface",
        category="contract_layer",
        passed=passed,
        observed=(
            f"no_torch_import={no_torch_import};ok_pose_ok={ok_pose_ok};"
            f"no_sites_fail_closed={no_sites_fail_closed};empty_fail_closed={empty_fail_closed};"
            f"missing_ok={missing_ok};role_invalid_ok={role_invalid_ok};"
            f"unsupported_ok={unsupported_ok}"
        ),
        required=(
            "backmapping and interaction adapters emit typed BackmappedPose/InteractionReport with "
            "passing chemical validity for ONSPS-ok pose and explicit fail-closed blockers for "
            "missing/empty/role-invalid/unsupported inputs"
        ),
    ) | {
        "no_torch_import": no_torch_import,
        "ok_pose_ok": ok_pose_ok,
        "no_sites_fail_closed": no_sites_fail_closed,
        "empty_fail_closed": empty_fail_closed,
        "missing_ok": missing_ok,
        "role_invalid_ok": role_invalid_ok,
        "unsupported_ok": unsupported_ok,
    }


def _check_api_evidence_bundle_adapter() -> dict[str, Any]:
    from betelgeuze_ai_md.contracts.api_adapter import build_api_evidence_bundle
    from betelgeuze_ai_md.contracts.output_schema import TopologyValidityReport

    bundle = build_api_evidence_bundle(
        job_id="gate_smoke",
        request={"target_name": "gate_target", "runner_profile_id": "gate_profile"},
        result_manifest={
            "job_id": "gate_smoke",
            "status": "completed",
            "request_sha256": "i" * 64,
            "result_file": "",
            "result_file_sha256": "",
            "claim_scope": "product_ligand_htvs_backmapping",
            "topology_fidelity": "placeholder_alanine",
            "accuracy_claim_grade": "restricted-local-delivery",
            "signature_key_id": "gate",
        },
        result_payload={},
        runner_execution={},
        status_payload={"status": "completed"},
    )
    required_flags = {
        "backmapped_pose_contract_missing",
        "interaction_report_contract_missing",
        "topology_report_contract_missing",
        "delivery_bundle_validation_not_attached",
    }
    observed_flags = set(bundle.failure_flags)
    topology_typed = isinstance(bundle.topology_report, TopologyValidityReport)
    topology_fail_closed = (
        "topology_validity_not_assessed" in bundle.topology_report.claim_blockers
    )
    passed = (
        bundle.verdict.claim_safe is False
        and required_flags.issubset(observed_flags)
        and len(bundle.fingerprint()) == 64
        and topology_typed
        and topology_fail_closed
    )
    return _row(
        check_id="api_evidence_bundle_adapter_fail_closed",
        category="api_evidence_bundle",
        passed=passed,
        observed=(
            f"claim_safe={bundle.verdict.claim_safe};flags={len(observed_flags)};"
            f"topology_typed={topology_typed};topology_fail_closed={topology_fail_closed};"
            f"fingerprint_len={len(bundle.fingerprint())}"
        ),
        required=(
            "API adapter emits deterministic review-only EvidenceBundle with missing-evidence flags "
            "and a typed TopologyValidityReport carrying explicit not-assessed claim blockers"
        ),
    ) | {
        "failure_flags": sorted(observed_flags),
        "topology_typed": topology_typed,
        "topology_fail_closed": topology_fail_closed,
    }


def _check_api_job_store_evidence_bundle_persistence(root: Path) -> dict[str, Any]:
    job_store = _resolve("api/job_store.py", root=root)
    text = job_store.read_text(encoding="utf-8") if job_store.is_file() else ""
    required_fragments = [
        "evidence_bundle_path TEXT NOT NULL DEFAULT ''",
        "evidence_bundle_sha256 TEXT NOT NULL DEFAULT ''",
        'ADD COLUMN evidence_bundle_path TEXT NOT NULL DEFAULT',
        'ADD COLUMN evidence_bundle_sha256 TEXT NOT NULL DEFAULT',
        "evidence_bundle_path: str | None = None",
        "evidence_bundle_sha256: str | None = None",
        "evidence_bundle_path=''",
        "evidence_bundle_sha256=''",
    ]
    missing = [fragment for fragment in required_fragments if fragment not in text]
    return _row(
        check_id="api_job_store_evidence_bundle_persistence",
        category="api_evidence_bundle",
        passed=not missing,
        observed=f"required_fragments={len(required_fragments)};missing={len(missing)}",
        required=(
            "SQLite job store persists evidence_bundle_path and evidence_bundle_sha256 with "
            "migration and clears pointers on job recreation"
        ),
        artifact_paths=["api/job_store.py"],
    ) | {"missing_fragments": missing, "missing_fragment_count": len(missing)}


def _check_api_main_evidence_bundle_surface(root: Path) -> dict[str, Any]:
    main_py = _resolve("api/main.py", root=root)
    models_py = _resolve("api/models.py", root=root)
    main_text = main_py.read_text(encoding="utf-8") if main_py.is_file() else ""
    models_text = models_py.read_text(encoding="utf-8") if models_py.is_file() else ""
    required_fragments = [
        "result_manifest=_artifact_path",
        "evidence_bundle=_artifact_path",
        "evidence_bundle_sha256=_artifact_path",
        "Completed job missing result manifest provenance",
        "Completed job missing evidence bundle provenance",
        "Completed job missing evidence bundle fingerprint",
        "result_manifest: Optional[str] = None",
        "evidence_bundle: Optional[str] = None",
        "evidence_bundle_sha256: Optional[str] = None",
    ]
    missing = [fragment for fragment in required_fragments if fragment not in (main_text + models_text)]
    return _row(
        check_id="api_main_evidence_bundle_surface",
        category="api_evidence_bundle",
        passed=not missing,
        observed=f"required_fragments={len(required_fragments)};missing={len(missing)}",
        required=(
            "API status/results surfaces expose evidence bundle provenance and fail closed when "
            "completed jobs lack manifest or evidence bundle pointers"
        ),
        artifact_paths=["api/main.py", "api/models.py"],
    ) | {"missing_fragments": missing, "missing_fragment_count": len(missing)}


def _check_api_worker_attachment(root: Path) -> dict[str, Any]:
    worker = _resolve("api/worker.py", root=root)
    text = worker.read_text(encoding="utf-8") if worker.is_file() else ""
    required_fragments = [
        "write_api_evidence_bundle",
        "job_evidence_bundle_path",
        "write_job_evidence_bundle",
        '"evidence_bundle"',
        '"evidence_bundle_sha256"',
        "evidence_bundle_path=bundle_path",
        "evidence_bundle_sha256=bundle_hash",
        "read_json_object_file",
    ]
    missing = [fragment for fragment in required_fragments if fragment not in text]
    return _row(
        check_id="api_worker_evidence_bundle_attachment",
        category="api_evidence_bundle",
        passed=not missing,
        observed=f"required_fragments={len(required_fragments)};missing={len(missing)}",
        required="API worker completed-job flow writes evidence_bundle path and fingerprint without assuming result file JSON",
        artifact_paths=["api/worker.py"],
    ) | {"missing_fragments": missing, "missing_fragment_count": len(missing)}


def _check_api_validated_runner_native_evidence_bundle_support(root: Path) -> dict[str, Any]:
    validated_runner = _resolve("api/validated_runner.py", root=root)
    worker = _resolve("api/worker.py", root=root)
    profiles_validator = _resolve("tools/product/validate_api_runner_profiles.py", root=root)
    runner_text = validated_runner.read_text(encoding="utf-8") if validated_runner.is_file() else ""
    worker_text = worker.read_text(encoding="utf-8") if worker.is_file() else ""
    validator_text = profiles_validator.read_text(encoding="utf-8") if profiles_validator.is_file() else ""
    required_fragments = [
        ("validated_runner.evidence_bundle_template", '"evidence_bundle_template"', runner_text),
        ("validated_runner.context.evidence_bundle", '"evidence_bundle"', runner_text),
        ("validated_runner.EvidenceBundle_import", "from betelgeuze_ai_md.contracts import EvidenceBundle", runner_text),
        ("validated_runner.ContractValidationError_import", "ContractValidationError", runner_text),
        ("validated_runner.native_evidence_bundle_record", "native_evidence_bundle", runner_text),
        ("validated_runner.evidence_bundle_source", "evidence_bundle_source", runner_text),
        ("worker.adopt_validated_runner_native_evidence_bundle", "adopt_validated_runner_native_evidence_bundle", worker_text),
        ("worker.bundle.fingerprint()", "bundle.fingerprint()", worker_text),
        ("worker.final_evidence_bundle_path", "final_path = Path(job_evidence_bundle_path(job_id))", worker_text),
        ("validator.evidence_bundle_template_declared", "evidence_bundle_template_declared", validator_text),
    ]
    missing = [name for name, fragment, text in required_fragments if fragment not in text]
    return _row(
        check_id="api_validated_runner_native_evidence_bundle_support",
        category="api_evidence_bundle",
        passed=not missing,
        observed=f"required_fragments={len(required_fragments)};missing={len(missing)}",
        required=(
            "validated runner profile supports evidence_bundle_template, runner command context exposes "
            "{evidence_bundle}, native bundles are validated as EvidenceBundle with fingerprint, the worker "
            "adopts validated native bundles as final evidence_bundle.json, and the profile validator "
            "reports native bundle template presence"
        ),
        artifact_paths=[
            "api/validated_runner.py",
            "api/worker.py",
            "tools/product/validate_api_runner_profiles.py",
        ],
    ) | {"missing_fragments": missing, "missing_fragment_count": len(missing)}


def _check_numpy_reference_oracle() -> dict[str, Any]:
    from betelgeuze_ai_md.coarse_md.numpy_ref import (
        FEATURE_ACCEPTOR,
        FEATURE_DONOR,
        FEATURE_HYDROPHOBE,
        BeadKind,
        CoarseForceField,
        CoarseState,
        DirectionalHbondTerm,
        HydrophobicContactTerm,
        NeighborListBuilder,
        ScreenedElectrostaticTerm,
        SoftcoreContactTerm,
        build_bruteforce_neighbor_list,
        finite_difference_force,
    )

    electrostatic_state = CoarseState(
        x=np.array([[0.0, 0.0, 0.0], [5.5, 0.0, 0.0]], dtype=np.float32),
        v=np.zeros((2, 3), dtype=np.float32),
        mass=np.ones(2, dtype=np.float32) * 12.0,
        charge=np.array([1.0, -1.0], dtype=np.float32),
        radius=np.ones(2, dtype=np.float32) * 1.6,
        epsilon=np.zeros(2, dtype=np.float32),
        bead_type=np.array([BeadKind.LIGAND_CHARGED, BeadKind.LIGAND_CHARGED], dtype=np.int32),
        feature=np.zeros(2, dtype=np.int32),
        mol_id=np.array([0, 1], dtype=np.int32),
        fixed=np.zeros(2, dtype=bool),
    )
    electrostatic_neighbor_builder = NeighborListBuilder(cutoff=6.0, skin=0.0)
    electrostatic_forcefield = CoarseForceField(
        [ScreenedElectrostaticTerm(epsilon_r=20.0, kappa=0.15, r_switch=5.0, r_cut=6.0)],
        force_clip=1_000_000.0,
    )
    softcore_state = CoarseState(
        x=np.array([[0.0, 0.0, 0.0], [3.0, 0.0, 0.0]], dtype=np.float32),
        v=np.zeros((2, 3), dtype=np.float32),
        mass=np.ones(2, dtype=np.float32) * 12.0,
        charge=np.zeros(2, dtype=np.float32),
        radius=np.ones(2, dtype=np.float32),
        epsilon=np.ones(2, dtype=np.float32) * 0.2,
        bead_type=np.array([BeadKind.LIGAND_POLAR, BeadKind.LIGAND_POLAR], dtype=np.int32),
        feature=np.zeros(2, dtype=np.int32),
        mol_id=np.array([0, 1], dtype=np.int32),
        fixed=np.zeros(2, dtype=bool),
    )
    softcore_neighbor_builder = NeighborListBuilder(cutoff=5.0, skin=0.0)
    softcore_forcefield = CoarseForceField(
        [SoftcoreContactTerm(r_switch=2.5, r_cut=3.5)],
        force_clip=1_000_000.0,
    )
    neighbor_parity_state = CoarseState(
        x=np.array(
            [
                [0.0, 0.0, 0.0],
                [3.8, 0.2, 0.1],
                [1.8, 2.6, 0.2],
                [4.5, 2.8, -0.1],
            ],
            dtype=np.float32,
        ),
        v=np.zeros((4, 3), dtype=np.float32),
        mass=np.ones(4, dtype=np.float32) * 12.0,
        charge=np.array([-0.3, 0.1, 0.2, -0.2], dtype=np.float32),
        radius=np.ones(4, dtype=np.float32) * 1.8,
        epsilon=np.ones(4, dtype=np.float32) * 0.2,
        bead_type=np.array(
            [
                BeadKind.PROTEIN_CA,
                BeadKind.PROTEIN_SC,
                BeadKind.LIGAND_POLAR,
                BeadKind.LIGAND_HYDROPHOBE,
            ],
            dtype=np.int32,
        ),
        feature=np.array(
            [FEATURE_ACCEPTOR, FEATURE_HYDROPHOBE, FEATURE_DONOR, FEATURE_HYDROPHOBE],
            dtype=np.int32,
        ),
        mol_id=np.array([0, 0, 1, 1], dtype=np.int32),
        fixed=np.zeros(4, dtype=bool),
    )
    neighbor_parity_forcefield = CoarseForceField(
        [
            SoftcoreContactTerm(r_switch=5.0, r_cut=6.0),
            ScreenedElectrostaticTerm(epsilon_r=20.0, kappa=0.15, r_switch=5.0, r_cut=6.0),
            DirectionalHbondTerm(),
            HydrophobicContactTerm(),
        ],
        force_clip=1_000_000.0,
    )

    def _force_matches(
        state: CoarseState,
        forcefield: CoarseForceField,
        neighbor_builder: NeighborListBuilder,
    ) -> tuple[bool, bool, bool]:
        def energy_fn(x: np.ndarray) -> float:
            shifted = state.with_positions(x)
            return forcefield.compute(shifted, neighbor_builder.build(shifted.x)).energy

        result = forcefield.compute(state, neighbor_builder.build(state.x))
        fd_force = finite_difference_force(energy_fn, state.x, h=1e-3)
        force_matches = bool(np.allclose(result.forces, fd_force, rtol=3e-3, atol=3e-3))
        finite = bool(np.isfinite(result.energy) and np.isfinite(result.forces).all())
        return finite, force_matches, bool(finite and force_matches)

    def _compute_with_cell_neighbors(state: CoarseState, forcefield: CoarseForceField) -> Any:
        return forcefield.compute(state, NeighborListBuilder(cutoff=6.0, skin=0.0).build(state.x))

    def _permuted_state(state: CoarseState, order: np.ndarray) -> CoarseState:
        return CoarseState(
            x=state.x[order],
            v=state.v[order],
            mass=state.mass[order],
            charge=state.charge[order],
            radius=state.radius[order],
            epsilon=state.epsilon[order],
            bead_type=state.bead_type[order],
            feature=state.feature[order],
            mol_id=state.mol_id[order],
            fixed=state.fixed[order],
        )

    electrostatic_finite, electrostatic_force_matches, electrostatic_passed = _force_matches(
        electrostatic_state,
        electrostatic_forcefield,
        electrostatic_neighbor_builder,
    )
    softcore_finite, softcore_force_matches, softcore_passed = _force_matches(
        softcore_state,
        softcore_forcefield,
        softcore_neighbor_builder,
    )
    cell_neighbors = NeighborListBuilder(cutoff=6.0, skin=0.0).build(neighbor_parity_state.x)
    brute_neighbors = build_bruteforce_neighbor_list(neighbor_parity_state.x, cutoff=6.0, skin=0.0)
    cell_pairs = set(zip(cell_neighbors.pair_i.tolist(), cell_neighbors.pair_j.tolist()))
    brute_pairs = set(zip(brute_neighbors.pair_i.tolist(), brute_neighbors.pair_j.tolist()))
    cell_result = neighbor_parity_forcefield.compute(neighbor_parity_state, cell_neighbors)
    brute_result = neighbor_parity_forcefield.compute(neighbor_parity_state, brute_neighbors)
    neighbor_pair_matches = cell_pairs == brute_pairs
    neighbor_energy_matches = bool(np.isclose(cell_result.energy, brute_result.energy, rtol=1e-6, atol=1e-6))
    neighbor_force_matches = bool(np.allclose(cell_result.forces, brute_result.forces, rtol=1e-6, atol=1e-6))
    neighbor_full_pair_parity = bool(neighbor_pair_matches and neighbor_energy_matches and neighbor_force_matches)
    base_result = _compute_with_cell_neighbors(neighbor_parity_state, neighbor_parity_forcefield)
    shifted_state = neighbor_parity_state.with_positions(
        neighbor_parity_state.x + np.array([7.0, -3.0, 1.5], dtype=np.float32)
    )
    shifted_result = _compute_with_cell_neighbors(shifted_state, neighbor_parity_forcefield)
    translation_invariant = bool(
        np.isclose(shifted_result.energy, base_result.energy, rtol=1e-6, atol=1e-6)
        and np.allclose(shifted_result.forces, base_result.forces, rtol=3e-6, atol=3e-6)
    )
    theta = np.pi / 3.0
    rotation = np.array(
        [
            [np.cos(theta), -np.sin(theta), 0.0],
            [np.sin(theta), np.cos(theta), 0.0],
            [0.0, 0.0, 1.0],
        ],
        dtype=np.float32,
    )
    rotated_state = neighbor_parity_state.with_positions(neighbor_parity_state.x @ rotation.T)
    rotated_result = _compute_with_cell_neighbors(rotated_state, neighbor_parity_forcefield)
    rotation_invariant = bool(
        np.isclose(rotated_result.energy, base_result.energy, rtol=1e-5, atol=1e-5)
        and np.allclose(rotated_result.forces, base_result.forces @ rotation.T, rtol=1e-5, atol=1e-5)
    )
    order = np.array([2, 0, 3, 1], dtype=np.int64)
    inverse_order = np.argsort(order)
    permuted_result = _compute_with_cell_neighbors(
        _permuted_state(neighbor_parity_state, order),
        neighbor_parity_forcefield,
    )
    permutation_invariant = bool(
        np.isclose(permuted_result.energy, base_result.energy, rtol=1e-6, atol=1e-6)
        and np.allclose(permuted_result.forces[inverse_order], base_result.forces, rtol=1e-6, atol=1e-6)
    )
    cutoff_state = CoarseState(
        x=np.array([[0.0, 0.0, 0.0], [6.0, 0.0, 0.0]], dtype=np.float32),
        v=np.zeros((2, 3), dtype=np.float32),
        mass=np.ones(2, dtype=np.float32) * 12.0,
        charge=np.array([1.0, -1.0], dtype=np.float32),
        radius=np.ones(2, dtype=np.float32),
        epsilon=np.ones(2, dtype=np.float32) * 0.2,
        bead_type=np.array([BeadKind.LIGAND_CHARGED, BeadKind.LIGAND_CHARGED], dtype=np.int32),
        feature=np.zeros(2, dtype=np.int32),
        mol_id=np.array([0, 1], dtype=np.int32),
        fixed=np.zeros(2, dtype=bool),
    )
    cutoff_result = _compute_with_cell_neighbors(cutoff_state, neighbor_parity_forcefield)
    cutoff_boundary_stable = bool(
        np.isclose(cutoff_result.energy, 0.0, atol=1e-7)
        and np.allclose(cutoff_result.forces, 0.0, atol=1e-7)
    )
    stress_state = cutoff_state.with_positions(
        np.array([[0.0, 0.0, 0.0], [1e-4, 0.0, 0.0]], dtype=np.float32)
    )
    stress_result = _compute_with_cell_neighbors(stress_state, neighbor_parity_forcefield)
    stress_finite = bool(np.isfinite(stress_result.energy) and np.isfinite(stress_result.forces).all())
    reference_invariance_ready = bool(
        translation_invariant
        and rotation_invariant
        and permutation_invariant
        and cutoff_boundary_stable
        and stress_finite
    )
    passed = bool(
        electrostatic_passed
        and softcore_passed
        and neighbor_full_pair_parity
        and reference_invariance_ready
    )
    return _row(
        check_id="numpy_reference_oracle_smoke",
        category="numpy_reference_oracle",
        passed=passed,
        observed=(
            f"electrostatic_switch_finite={electrostatic_finite};"
            f"electrostatic_switch_force_matches_finite_difference={electrostatic_force_matches};"
            f"softcore_switch_finite={softcore_finite};"
            f"softcore_switch_force_matches_finite_difference={softcore_force_matches};"
            f"neighbor_full_pair_parity={neighbor_full_pair_parity};"
            f"reference_invariance_ready={reference_invariance_ready}"
        ),
        required=(
            "NumPy reference oracle produces finite energy/forces and matches finite-difference force "
            "for switched electrostatic and softcore contact terms, and cell-list forcefield output "
            "matches brute-force full-pair neighbor oracle output with translation, rotation, permutation, "
            "cutoff-boundary, and stress finite checks"
        ),
    ) | {
        "electrostatic_switch_force_matches": electrostatic_force_matches,
        "softcore_switch_force_matches": softcore_force_matches,
        "neighbor_pair_matches": neighbor_pair_matches,
        "neighbor_energy_matches": neighbor_energy_matches,
        "neighbor_force_matches": neighbor_force_matches,
        "neighbor_full_pair_parity": neighbor_full_pair_parity,
        "translation_invariant": translation_invariant,
        "rotation_invariant": rotation_invariant,
        "permutation_invariant": permutation_invariant,
        "cutoff_boundary_stable": cutoff_boundary_stable,
        "stress_finite": stress_finite,
        "reference_invariance_ready": reference_invariance_ready,
    }


def _check_numpy_trajectory_summary_surface() -> dict[str, Any]:
    from betelgeuze_ai_md.coarse_md.numpy_ref import (
        FEATURE_ACCEPTOR,
        FEATURE_DONOR,
        FEATURE_HYDROPHOBE,
        BeadKind,
        CoarseForceField,
        CoarseState,
        DirectionalHbondTerm,
        DynamicsEngine,
        HydrophobicContactTerm,
        IntegratorConfig,
        NeighborListBuilder,
        PocketWallTerm,
        ScreenedElectrostaticTerm,
        SoftcoreContactTerm,
        summarize_trajectory,
    )
    from betelgeuze_ai_md.contracts import TrajectorySummary
    from betelgeuze_ai_md.contracts.errors import ContractValidationError

    x = np.array(
        [
            [0.0, 0.0, 0.0],
            [4.0, 0.0, 0.0],
            [2.0, 1.0, 0.0],
            [2.8, 1.2, 0.0],
        ],
        dtype=np.float32,
    )
    state = CoarseState(
        x=x,
        v=np.zeros_like(x, dtype=np.float32),
        mass=np.ones(4, dtype=np.float32) * 12.0,
        charge=np.array([-0.3, 0.1, 0.2, -0.2], dtype=np.float32),
        radius=np.ones(4, dtype=np.float32) * 1.8,
        epsilon=np.ones(4, dtype=np.float32) * 0.2,
        bead_type=np.array(
            [
                BeadKind.PROTEIN_CA,
                BeadKind.PROTEIN_SC,
                BeadKind.LIGAND_POLAR,
                BeadKind.LIGAND_HYDROPHOBE,
            ],
            dtype=np.int32,
        ),
        feature=np.array(
            [FEATURE_ACCEPTOR, FEATURE_HYDROPHOBE, FEATURE_DONOR, FEATURE_HYDROPHOBE],
            dtype=np.int32,
        ),
        mol_id=np.array([0, 0, 1, 1], dtype=np.int32),
        fixed=np.array([True, True, False, False], dtype=bool),
    )
    forcefield = CoarseForceField(
        [
            SoftcoreContactTerm(),
            ScreenedElectrostaticTerm(),
            DirectionalHbondTerm(),
            HydrophobicContactTerm(),
            PocketWallTerm(np.array([2.0, 0.5, 0.0], dtype=np.float32), pocket_radius=5.0, ligand_mol_id=1),
        ],
        force_clip=250.0,
    )
    trajectory = DynamicsEngine(forcefield, NeighborListBuilder(cutoff=10.0, skin=2.0)).run(
        state,
        IntegratorConfig(max_steps=12, save_every=3, damping=0.95),
    )
    summary = summarize_trajectory(trajectory, state, ligand_mol_id=1)
    typed = isinstance(summary, TrajectorySummary)
    frame_count_ok = summary.frame_count == len(trajectory.frames) == 4
    traces_ok = len(summary.energy_trace) == summary.frame_count and len(summary.contact_trace) == summary.frame_count
    finite_ok = bool(
        np.isfinite(summary.energy_trace).all()
        and np.isfinite(summary.contact_trace).all()
        and np.isfinite(summary.stability_score)
        and np.isfinite(summary.mean_min_distance)
        and np.isfinite(summary.escape_fraction)
        and np.isfinite(summary.clash_fraction)
    )
    bounded_ok = bool(
        0.0 <= summary.stability_score <= 1.0
        and 0.0 <= summary.escape_fraction <= 1.0
        and 0.0 <= summary.clash_fraction <= 1.0
        and summary.mean_min_distance > 0.0
    )
    contract_hash_ok = len(summary.contract_hash()) == 64
    invalid_trace_blocked = False
    try:
        TrajectorySummary(frame_count=1, energy_trace=[float("nan")])
    except ContractValidationError:
        invalid_trace_blocked = True
    invalid_fraction_blocked = False
    try:
        TrajectorySummary(frame_count=1, escape_fraction=1.1)
    except ContractValidationError:
        invalid_fraction_blocked = True
    excessive_trace_blocked = False
    try:
        TrajectorySummary(frame_count=1, contact_trace=[0.0, 1.0])
    except ContractValidationError:
        excessive_trace_blocked = True
    fail_closed_ok = invalid_trace_blocked and invalid_fraction_blocked and excessive_trace_blocked
    passed = bool(
        typed
        and frame_count_ok
        and traces_ok
        and finite_ok
        and bounded_ok
        and contract_hash_ok
        and fail_closed_ok
    )
    return _row(
        check_id="numpy_trajectory_summary_surface",
        category="numpy_reference_oracle",
        passed=passed,
        observed=(
            f"typed={typed};frame_count_ok={frame_count_ok};traces_ok={traces_ok};"
            f"finite_ok={finite_ok};bounded_ok={bounded_ok};contract_hash_ok={contract_hash_ok};"
            f"fail_closed_ok={fail_closed_ok}"
        ),
        required=(
            "NumPy dynamics trajectory summarizes into typed TrajectorySummary with frame-aligned "
            "energy/contact traces, bounded stability/escape/clash metrics, finite distances, stable hash, "
            "and fail-closed rejection of invalid summary metrics"
        ),
    ) | {
        "typed": typed,
        "frame_count_ok": frame_count_ok,
        "traces_ok": traces_ok,
        "finite_ok": finite_ok,
        "bounded_ok": bounded_ok,
        "contract_hash_ok": contract_hash_ok,
        "invalid_trace_blocked": invalid_trace_blocked,
        "invalid_fraction_blocked": invalid_fraction_blocked,
        "excessive_trace_blocked": excessive_trace_blocked,
        "fail_closed_ok": fail_closed_ok,
    }


def build_ai_md_contract_source_of_truth_gate(
    *,
    root: str | Path = ROOT,
    required_source_files: list[str] | None = None,
) -> dict[str, Any]:
    root_path = Path(root)
    source_files = list(required_source_files or REQUIRED_SOURCE_FILES)
    checks = [
        lambda: _check_required_source_files(root_path, source_files),
        lambda: _check_pyproject_package_discovery(root_path),
        _check_contract_symbols_exported,
        _check_ai_residual_report_surface,
        _check_topology_validity_contract_surface,
        _check_evidence_bundle_trajectory_claim_gate,
        _check_evidence_bundle_backmapped_pose_claim_gate,
        _check_evidence_bundle_interaction_claim_gate,
        _check_evidence_bundle_product_output_claim_gate,
        _check_evidence_bundle_ai_uncertainty_claim_gate,
        _check_topology_factory_adapter,
        _check_backmapping_interaction_adapter_surface,
        _check_claim_widening_guard,
        _check_api_evidence_bundle_adapter,
        lambda: _check_api_job_store_evidence_bundle_persistence(root_path),
        lambda: _check_api_main_evidence_bundle_surface(root_path),
        lambda: _check_api_worker_attachment(root_path),
        lambda: _check_api_validated_runner_native_evidence_bundle_support(root_path),
        _check_numpy_reference_oracle,
        _check_numpy_trajectory_summary_surface,
    ]
    rows = [_safe_check(check) for check in checks]
    blockers = [row for row in rows if row["release_blocker"]]
    rows_by_id = {str(row["check_id"]): row for row in rows}
    category_ready = {
        category: all(row["status"] == "pass" for row in rows if row["category"] == category)
        for category in sorted({row["category"] for row in rows})
    }
    missing_source_file_count = sum(int(row.get("missing_source_file_count", 0)) for row in rows)
    ready = not blockers
    summary = {
        "packet_type": "ai_md_contract_source_of_truth_gate",
        "status": "ai_md_contract_source_of_truth_gate_ready" if ready else "blocked_ai_md_contract_source_of_truth_gate",
        "ai_md_contract_source_of_truth_gate_ready": ready,
        "ai_md_contract_layer_ready": bool(category_ready.get("contract_layer")),
        "api_evidence_bundle_attachment_ready": bool(category_ready.get("api_evidence_bundle")),
        "api_runtime_evidence_bundle_surface_ready": all(
            rows_by_id.get(check_id, {}).get("status") == "pass"
            for check_id in (
                "api_job_store_evidence_bundle_persistence",
                "api_main_evidence_bundle_surface",
                "api_worker_evidence_bundle_attachment",
                "api_validated_runner_native_evidence_bundle_support",
            )
        ),
        "numpy_reference_oracle_ready": bool(category_ready.get("numpy_reference_oracle")),
        "trajectory_summary_contract_ready": rows_by_id.get("numpy_trajectory_summary_surface", {}).get("status")
        == "pass",
        "evidence_bundle_trajectory_claim_ready": rows_by_id.get(
            "evidence_bundle_trajectory_claim_gate", {}
        ).get("status")
        == "pass",
        "evidence_bundle_backmapped_pose_claim_ready": rows_by_id.get(
            "evidence_bundle_backmapped_pose_claim_gate", {}
        ).get("status")
        == "pass",
        "evidence_bundle_interaction_claim_ready": rows_by_id.get(
            "evidence_bundle_interaction_claim_gate", {}
        ).get("status")
        == "pass",
        "evidence_bundle_product_output_claim_ready": rows_by_id.get(
            "evidence_bundle_product_output_claim_gate", {}
        ).get("status")
        == "pass",
        "evidence_bundle_ai_uncertainty_claim_ready": rows_by_id.get(
            "evidence_bundle_ai_uncertainty_claim_gate", {}
        ).get("status")
        == "pass",
        "claim_widening_guard_ready": bool(category_ready.get("claim_boundary")),
        "contract_source_files_ready": bool(category_ready.get("contract_source_files")),
        "ai_residual_contract_ready": rows_by_id.get("ai_residual_report_surface", {}).get("status")
        == "pass",
        "topology_validity_contract_ready": rows_by_id.get("topology_validity_contract_surface", {}).get("status")
        == "pass",
        "topology_factory_adapter_ready": rows_by_id.get("topology_factory_adapter_surface", {}).get("status")
        == "pass",
        "backmapping_interaction_adapter_ready": rows_by_id.get(
            "backmapping_interaction_adapter_surface", {}
        ).get("status")
        == "pass",
        "check_count": len(rows),
        "pass_count": len(rows) - len(blockers),
        "blocker_count": len(blockers),
        "missing_source_file_count": missing_source_file_count,
        "blocked_check_ids": [row["check_id"] for row in blockers],
        "required_source_file_count": len(source_files),
        "execution_enabled": False,
        "external_state_mutated": False,
        "docking_results_emitted": False,
        "full_commercial_claim_allowed": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "Wire this artifact into product release source-of-truth freshness and semantic-status rows."
            if ready
            else "Restore missing contract/API/reference files or fail-closed claim guards, then rerun this gate."
        ),
    }
    return {"summary": summary, "rows": rows, "blockers": blockers}


def _resolve_out(path_like: str | Path, *, root: Path) -> Path:
    return _resolve(path_like, root=root)


def _write_json(path_like: str | Path, payload: dict[str, Any], *, root: Path) -> None:
    path = _resolve_out(path_like, root=root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_markdown(path_like: str | Path, payload: dict[str, Any], *, root: Path) -> None:
    path = _resolve_out(path_like, root=root)
    summary = payload["summary"]
    lines = [
        "# AI-MD Contract Source Of Truth Gate",
        "",
        f"- status: `{summary['status']}`",
        f"- ready: `{summary['ai_md_contract_source_of_truth_gate_ready']}`",
        f"- blocker_count: `{summary['blocker_count']}`",
        f"- contract_source_files_ready: `{summary['contract_source_files_ready']}`",
        f"- ai_md_contract_layer_ready: `{summary['ai_md_contract_layer_ready']}`",
        f"- ai_residual_contract_ready: `{summary['ai_residual_contract_ready']}`",
        f"- api_evidence_bundle_attachment_ready: `{summary['api_evidence_bundle_attachment_ready']}`",
        f"- api_runtime_evidence_bundle_surface_ready: `{summary['api_runtime_evidence_bundle_surface_ready']}`",
        f"- numpy_reference_oracle_ready: `{summary['numpy_reference_oracle_ready']}`",
        f"- trajectory_summary_contract_ready: `{summary['trajectory_summary_contract_ready']}`",
        f"- evidence_bundle_trajectory_claim_ready: `{summary['evidence_bundle_trajectory_claim_ready']}`",
        f"- evidence_bundle_backmapped_pose_claim_ready: `{summary['evidence_bundle_backmapped_pose_claim_ready']}`",
        f"- evidence_bundle_interaction_claim_ready: `{summary['evidence_bundle_interaction_claim_ready']}`",
        f"- evidence_bundle_product_output_claim_ready: `{summary['evidence_bundle_product_output_claim_ready']}`",
        f"- evidence_bundle_ai_uncertainty_claim_ready: `{summary['evidence_bundle_ai_uncertainty_claim_ready']}`",
        f"- claim_widening_guard_ready: `{summary['claim_widening_guard_ready']}`",
        "",
        "## Checks",
        "",
        "| check | category | status | observed | required |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['check_id']}` | `{row['category']}` | `{row['status']}` | "
            f"`{row['observed']}` | `{row['required']}` |"
        )
    lines.extend(["", "## Claim Boundary", "", summary["claim_boundary"], "", "## Next Step", "", f"- {summary['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the AI-MD contract source-of-truth gate.")
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    root = Path(args.root)
    payload = build_ai_md_contract_source_of_truth_gate(root=root)
    _write_json(args.out_json, payload, root=root)
    write_csv_rows(_resolve_out(args.out_csv, root=root), payload["rows"])
    _write_markdown(args.out_md, payload, root=root)
    print(json.dumps(payload["summary"], indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

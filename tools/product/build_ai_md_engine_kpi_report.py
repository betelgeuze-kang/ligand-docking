#!/usr/bin/env python3
from __future__ import annotations

import argparse
import contextlib
import hashlib
import importlib
import io
import json
import resource
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

import numpy as np
import torch

from api.result_manifest import build_result_manifest, verify_result_manifest
from betelgeuze_engine.backmapping.onsps import (
    ONSPS_BACKMAP_SCHEMA_VERSION,
    backmap_4bead_onsps,
    evaluate_onsps_backmap_evidence,
)
from betelgeuze_engine.benchmark import run_runtime_scaling_benchmark, write_runtime_scaling_svg
from betelgeuze_engine.contracts import EngineState, validate_energy_forces_contract
from betelgeuze_engine.interactions.hbond_evidence import evaluate_hbond_evidence
from betelgeuze_engine.physics import ProductForceField, default_force_term_registry, guarded_force_term_registry
from betelgeuze_engine.physics.neighbor import full_neighbor_pairs
from betelgeuze_engine.physics.terms import (
    DirectionalHBondTerm,
    HydrophobicContactTerm,
    LegacyLJTerm,
    PocketWallTerm,
    ScreenedElectrostaticsTerm,
    TopologyPenaltyTerm,
    TorsionPriorTerm,
    WaterDisplacementProxyTerm,
)
from betelgeuze_engine.residual import (
    ForceResidualPolicy,
    apply_guarded_force_residual,
    decide_force_residual,
    validate_force_residual_report_contract,
)
from betelgeuze_engine.topology import (
    ComplexTopology,
    TopologyFactoryFacade,
    ligand_topology_from_smiles,
    protein_topology_from_sequence,
    topology_claim_metadata,
)
from betelgeuze_engine.validation import (
    build_confidence_calibration_report,
    energy_drift_smoke_pct,
    finite_difference_force_error,
    neighbor_list_parity_error,
    rotation_equivariance_error,
    translation_invariance_error,
)
from tools.product.build_ai_md_product_evidence_bundle import validate_product_evidence_bundle
from tools.product.validate_api_runner_profiles import validate_profiles


DEFAULT_OUT_JSON = "runs/ai_md_engine_kpi_report_current.json"
DEFAULT_OUT_MD = "runs/ai_md_engine_kpi_report_current.md"
DEFAULT_RUNTIME_SCALING_PLOT = "runs/ai_md_runtime_scaling_plot_current.svg"
DEFAULT_ROCM_MANIFEST_JSON = "runs/rocm_environment_manifest_current.json"
DEFAULT_PRODUCT_EVIDENCE_BUNDLE_JSON = "runs/ai_md_product_evidence_bundle_current.json"
DEFAULT_PRODUCT_CI_RUNTIME_GATE_JSON = "runs/product_ci_runtime_gate_current.json"
EXPECTED_PRODUCT_FORCE_TERMS = ["directional_hbond", "hydrophobic_contact", "legacy_lj"]
CHEMISTRY_FIXTURES = {
    "ethanol": "CCO",
    "amide": "CC(=O)N",
    "tertiary_amine": "CCN(C)C",
    "carboxylate": "CC(=O)[O-]",
    "phosphate": "COP(=O)(O)O",
    "heteroaryl_nitrogen": "c1ccncc1",
    "chiral_lactic_acid": "C[C@H](O)C(=O)O",
    "unassigned_chiral_lactic_acid": "CC(O)C(=O)O",
    "aromatic_ring": "c1ccccc1",
    "protonated_amine": "C[NH3+]",
    "keto_tautomer_smoke": "CC(=O)C",
    "invalid_smiles": "C1(",
}


def _sha256_path(path: Path) -> str:
    if not path.exists() or not path.is_file():
        return ""
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _runtime_scaling_plot_metadata(
    scaling: dict[str, Any],
    plot_path: str | Path,
) -> dict[str, Any]:
    out = Path(plot_path)
    claim_boundary = (
        "Pair-count scaling is the gated evidence; duration trend is advisory microbenchmark telemetry."
    )
    if out.exists() and out.is_file():
        try:
            existing = out.read_text(encoding="utf-8", errors="replace")
        except OSError:
            existing = ""
        existing_ready = bool(
            "<svg" in existing
            and "Pair-count scaling" in existing
            and "advisory" in existing
            and out.stat().st_size > 0
        )
        if existing_ready:
            return {
                "plot_path": str(out),
                "plot_format": "svg",
                "plot_ready": True,
                "plot_role": "runtime_neighbor_cap_scaling_plot",
                "plot_claim_boundary": claim_boundary,
                "plot_sha256": _sha256_path(out),
                "plot_size_bytes": int(out.stat().st_size),
                "plot_reused_existing": True,
            }
    try:
        metadata = write_runtime_scaling_svg(scaling, out)
    except (OSError, TypeError, ValueError) as exc:
        return {
            "plot_path": str(out),
            "plot_format": "svg",
            "plot_ready": False,
            "plot_role": "runtime_neighbor_cap_scaling_plot",
            "plot_claim_boundary": claim_boundary,
            "plot_sha256": "",
            "plot_size_bytes": 0,
            "plot_error": str(exc),
        }
    plot_file = Path(str(metadata.get("plot_path") or out))
    metadata["plot_sha256"] = _sha256_path(plot_file)
    metadata["plot_size_bytes"] = int(plot_file.stat().st_size) if plot_file.exists() else 0
    metadata["plot_ready"] = bool(
        metadata.get("plot_ready") is True
        and metadata.get("plot_format") == "svg"
        and len(str(metadata.get("plot_sha256") or "")) == 64
        and int(metadata.get("plot_size_bytes") or 0) > 0
    )
    return metadata
POSE_RANKING_HBOND_FIXTURES = (
    {
        "pose_id": "amide_near_hbond_pose",
        "benchmark_role": "hbond_recovery_pose",
        "smiles": "CC(=O)N",
        "expected_top1": True,
        "expected_claim_safe": True,
        "expected_hbond_status": "pass",
        "expected_blocked_reason": "",
        "expect_unsatisfied_donor_acceptor": False,
        "expect_missing_anchor": False,
        "expect_overanchored": False,
        "rmsd_proxy_A": 0.35,
        "ligand_xyz": [[2.8, 0.0, 0.0], [0.0, 2.8, 0.0], [1.0, 1.0, 1.0]],
    },
    {
        "pose_id": "ethanol_near_hbond_pose",
        "benchmark_role": "unsatisfied_donor_pose",
        "smiles": "CCO",
        "expected_top1": False,
        "expected_claim_safe": False,
        "expected_hbond_status": "review",
        "expected_blocked_reason": "missing_expected_anchor",
        "expect_unsatisfied_donor_acceptor": True,
        "expect_missing_anchor": True,
        "expect_overanchored": False,
        "rmsd_proxy_A": 0.85,
        "ligand_xyz": [[2.9, 0.1, 0.0], [0.2, 2.9, 0.0], [1.0, 1.0, 1.0]],
    },
    {
        "pose_id": "amide_delta_backmap_yellow_band_pose",
        "benchmark_role": "delta_backmap_yellow_band_pose",
        "smiles": "CC(=O)N",
        "expected_top1": False,
        "expected_claim_safe": False,
        "expected_hbond_status": "review",
        "expected_blocked_reason": "delta_backmap_yellow_band",
        "expect_unsatisfied_donor_acceptor": False,
        "expect_missing_anchor": False,
        "expect_overanchored": False,
        "expect_delta_backmap_yellow_band": True,
        "delta_backmap": 3.0,
        "delta_backmap_max": 2.5,
        "near_hbond_geometry": True,
        "rmsd_proxy_A": 0.55,
        "ligand_xyz": [[2.8, 0.0, 0.0], [0.0, 2.8, 0.0], [1.0, 1.0, 1.0]],
    },
    {
        "pose_id": "amide_far_decoy_pose",
        "benchmark_role": "far_decoy_pose",
        "smiles": "CC(=O)N",
        "expected_top1": False,
        "expected_claim_safe": False,
        "expected_hbond_status": "review",
        "expected_blocked_reason": "missing_expected_anchor",
        "expect_unsatisfied_donor_acceptor": True,
        "expect_missing_anchor": True,
        "expect_overanchored": False,
        "rmsd_proxy_A": 4.5,
        "ligand_xyz": [[8.0, 0.0, 0.0], [0.0, 8.0, 0.0], [8.0, 8.0, 8.0]],
    },
    {
        "pose_id": "amide_overanchored_decoy_pose",
        "benchmark_role": "overanchored_decoy_pose",
        "smiles": "CC(=O)N",
        "expected_top1": False,
        "expected_claim_safe": False,
        "expected_hbond_status": "review",
        "expected_blocked_reason": "overanchored_decoy",
        "expect_unsatisfied_donor_acceptor": True,
        "expect_missing_anchor": True,
        "expect_overanchored": True,
        "rmsd_proxy_A": 3.5,
        "ligand_xyz": [[0.0, 0.0, 0.0], [1.6, 0.0, 0.0], [0.5, 0.5, 0.0]],
    },
    {
        "pose_id": "invalid_ligand_pose",
        "benchmark_role": "invalid_ligand_pose",
        "smiles": "C1(",
        "expected_top1": False,
        "expected_claim_safe": False,
        "expected_hbond_status": "invalid_smiles",
        "expected_blocked_reason": "invalid_smiles",
        "expect_unsatisfied_donor_acceptor": False,
        "expect_missing_anchor": True,
        "expect_overanchored": False,
        "rmsd_proxy_A": 9.0,
        "ligand_xyz": [[2.8, 0.0, 0.0], [0.0, 2.8, 0.0], [1.0, 1.0, 1.0]],
    },
)


def _quiet_rdkit_parser_logs() -> None:
    try:
        from rdkit import RDLogger
    except Exception:
        return
    RDLogger.DisableLog("rdApp.error")


def _rocm_product_runtime_ready(rocm_summary: dict[str, Any]) -> bool:
    visible_device_count = int(rocm_summary.get("visible_device_count") or 0)
    production_execution_ready = rocm_summary.get("production_execution_ready")
    production_ready = bool(production_execution_ready) if production_execution_ready is not None else visible_device_count > 0
    return bool(
        rocm_summary.get("commercial_compute_default") == "rocm_hip"
        and rocm_summary.get("torch_rocm_ready") is True
        and visible_device_count > 0
        and rocm_summary.get("device_nodes_ready", True) is True
        and production_ready
        and rocm_summary.get("cpu_fallback_allowed_for_product", False) is False
    )


def _read_json_if_present(path_like: str | Path) -> dict[str, Any]:
    path = Path(path_like)
    if not path.exists() or not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _timed(label: str, fn) -> tuple[str, float, Any]:
    start = time.perf_counter()
    value = fn()
    return label, float(time.perf_counter() - start), value


def _memory_peak_mb() -> float:
    # On Linux ru_maxrss is KiB. This repo's local product lane targets Linux ROCm hosts.
    return float(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0)


def _score_only_runtime(row_count: int) -> dict[str, Any]:
    smiles = ["CCO", "CC(=O)N", "CCN(C)C", "CC(=O)[O-]"]

    def run() -> int:
        total = 0
        for i in range(row_count):
            total += ligand_topology_from_smiles(smiles[i % len(smiles)]).validity.get("valid") is True
        return int(total)

    _label, elapsed, valid_count = _timed("score_only", run)
    return {
        "row_count": int(row_count),
        "valid_count": int(valid_count),
        "duration_sec": elapsed,
        "rows_per_sec": float(row_count / elapsed) if elapsed > 0 else 0.0,
    }


def _onsps_runtime(row_count: int) -> dict[str, Any]:
    two_bead = np.asarray([[0.0, 0.0, 0.0], [1.6, 0.0, 0.0]], dtype=np.float32)

    def run() -> int:
        passed = 0
        claim_safe = 0
        for i, smiles in enumerate(list(CHEMISTRY_FIXTURES.values()) * ((row_count // len(CHEMISTRY_FIXTURES)) + 1)):
            if i >= row_count:
                break
            evidence = evaluate_hbond_evidence(smiles=smiles, ligand_xyz=two_bead)
            passed += int(evidence.site_count > 0)
            claim_safe += int(evidence.onsps_backmap_metadata.get("claim_safe") is True)
        return passed, claim_safe

    _label, elapsed, counts = _timed("onsps_4bead", run)
    site_positive, claim_safe_count = counts
    return {
        "row_count": int(row_count),
        "site_positive_count": int(site_positive),
        "onsps_backmap_claim_safe_count": int(claim_safe_count),
        "duration_sec": elapsed,
        "rows_per_sec": float(row_count / elapsed) if elapsed > 0 else 0.0,
    }


def _force_residual_runtime(row_count: int) -> dict[str, Any]:
    coords = torch.zeros(1, 8, 3)
    forces = torch.ones_like(coords) * 0.5
    policy = ForceResidualPolicy()
    required_policy_caps = {
        "max_abs_delta_score",
        "max_force_norm",
        "max_displacement",
        "max_energy_drift",
        "max_energy_drift_pct",
        "abstain_threshold",
        "top_k_rank_pct",
    }

    def run() -> tuple[int, dict[str, Any]]:
        applied = 0
        last_metadata: dict[str, Any] = {}
        last_report: dict[str, Any] = {}
        for _ in range(row_count):
            decision = decide_force_residual(
                rank_pct=0.01,
                topology_valid=True,
                uncertainty=0.1,
                delta_score=0.25,
                policy=policy,
            )
            _updated, report = apply_guarded_force_residual(coords, forces, decision=decision, policy=policy)
            applied += int(report.applied)
            last_report = report.to_dict()
            last_metadata = report.to_claim_metadata(
                {
                    "topology_fidelity": "sequence_mapped",
                    "ligand_topology_valid": True,
                    "claim_safe": True,
                    "blocked_reason": "",
                }
            )
            validate_force_residual_report_contract(report, claim_metadata=last_metadata)
        return applied, {"last_metadata": last_metadata, "last_report": last_report}

    _label, elapsed, runtime_value = _timed("guarded_force_residual", run)
    applied, runtime_payload = runtime_value
    last_metadata = dict(runtime_payload.get("last_metadata") or {})
    last_report = dict(runtime_payload.get("last_report") or {})
    cap_decision = decide_force_residual(
        rank_pct=0.01,
        topology_valid=True,
        uncertainty=0.1,
        delta_score=float(policy.max_abs_delta_score) + 0.25,
        policy=policy,
    )
    _cap_updated, cap_report = apply_guarded_force_residual(coords, forces, decision=cap_decision, policy=policy)
    uncertainty_decision = decide_force_residual(
        rank_pct=0.01,
        topology_valid=True,
        uncertainty=float(policy.abstain_threshold) + 0.01,
        delta_score=0.25,
        policy=policy,
    )
    _uncertainty_updated, uncertainty_report = apply_guarded_force_residual(
        coords,
        forces,
        decision=uncertainty_decision,
        policy=policy,
    )
    outside_top_k_decision = decide_force_residual(
        rank_pct=float(policy.top_k_rank_pct) + 0.01,
        topology_valid=True,
        uncertainty=0.1,
        delta_score=0.25,
        policy=policy,
    )
    _outside_updated, outside_top_k_report = apply_guarded_force_residual(
        coords,
        forces,
        decision=outside_top_k_decision,
        policy=policy,
    )
    nonfinite_uncertainty_decision = decide_force_residual(
        rank_pct=0.01,
        topology_valid=True,
        uncertainty=float("nan"),
        delta_score=0.25,
        policy=policy,
    )
    _nonfinite_uncertainty_updated, nonfinite_uncertainty_report = apply_guarded_force_residual(
        coords,
        forces,
        decision=nonfinite_uncertainty_decision,
        policy=policy,
    )
    nonfinite_delta_decision = decide_force_residual(
        rank_pct=0.01,
        topology_valid=True,
        uncertainty=0.1,
        delta_score=float("inf"),
        policy=policy,
    )
    _nonfinite_delta_updated, nonfinite_delta_report = apply_guarded_force_residual(
        coords,
        forces,
        decision=nonfinite_delta_decision,
        policy=policy,
    )
    cap_metadata = cap_report.to_claim_metadata(
        {
            "topology_fidelity": "sequence_mapped",
            "ligand_topology_valid": True,
            "claim_safe": True,
            "blocked_reason": "",
        }
    )
    uncertainty_metadata = uncertainty_report.to_claim_metadata(
        {
            "topology_fidelity": "sequence_mapped",
            "ligand_topology_valid": True,
            "claim_safe": True,
            "blocked_reason": "",
        }
    )
    outside_top_k_metadata = outside_top_k_report.to_claim_metadata(
        {
            "topology_fidelity": "sequence_mapped",
            "ligand_topology_valid": True,
            "claim_safe": True,
            "blocked_reason": "",
        }
    )
    nonfinite_uncertainty_metadata = nonfinite_uncertainty_report.to_claim_metadata(
        {
            "topology_fidelity": "sequence_mapped",
            "ligand_topology_valid": True,
            "claim_safe": True,
            "blocked_reason": "",
        }
    )
    nonfinite_delta_metadata = nonfinite_delta_report.to_claim_metadata(
        {
            "topology_fidelity": "sequence_mapped",
            "ligand_topology_valid": True,
            "claim_safe": True,
            "blocked_reason": "",
        }
    )
    validated_report_labels = ["applied_runtime_last"] if last_report and last_metadata else []
    validate_force_residual_report_contract(cap_report, claim_metadata=cap_metadata)
    validated_report_labels.append("delta_score_cap")
    validate_force_residual_report_contract(uncertainty_report, claim_metadata=uncertainty_metadata)
    validated_report_labels.append("uncertainty_abstention")
    validate_force_residual_report_contract(outside_top_k_report, claim_metadata=outside_top_k_metadata)
    validated_report_labels.append("outside_top_k")
    validate_force_residual_report_contract(
        nonfinite_uncertainty_report,
        claim_metadata=nonfinite_uncertainty_metadata,
    )
    validated_report_labels.append("nonfinite_uncertainty")
    validate_force_residual_report_contract(nonfinite_delta_report, claim_metadata=nonfinite_delta_metadata)
    validated_report_labels.append("nonfinite_delta_score")
    policy_caps = cap_report.to_dict()["policy_caps"]
    contract_ready = bool(
        last_report.get("claim_metadata_schema_version") == "force_residual_claim_metadata_v1"
        and last_metadata.get("force_residual_claim_metadata_schema_version")
        == "force_residual_claim_metadata_v1"
        and last_metadata.get("force_residual_policy_caps") == last_report.get("policy_caps")
        and cap_metadata.get("force_residual_policy_caps") == cap_report.to_dict().get("policy_caps")
        and uncertainty_metadata.get("force_residual_policy_caps")
        == uncertainty_report.to_dict().get("policy_caps")
        and outside_top_k_metadata.get("force_residual_policy_caps")
        == outside_top_k_report.to_dict().get("policy_caps")
        and nonfinite_uncertainty_metadata.get("force_residual_policy_caps")
        == nonfinite_uncertainty_report.to_dict().get("policy_caps")
        and nonfinite_delta_metadata.get("force_residual_policy_caps")
        == nonfinite_delta_report.to_dict().get("policy_caps")
    )
    bounded_policy_ready = bool(
        contract_ready
        and required_policy_caps.issubset(policy_caps)
        and last_metadata.get("force_residual_policy_caps_ready") is True
        and last_report.get("policy_caps_ready") is True
    )
    observed_caps_ready = bool(
        contract_ready
        and last_report.get("all_observed_caps_within_policy") is True
        and last_metadata.get("force_residual_all_observed_caps_within_policy") is True
        and last_metadata.get("force_residual_observed_caps_ready") is True
        and last_report.get("observed_caps_ready") is True
        and cap_report.to_dict().get("delta_score_within_cap") is False
        and uncertainty_report.to_dict().get("all_observed_caps_within_policy") is True
        and outside_top_k_report.to_dict().get("all_observed_caps_within_policy") is True
    )
    confidence_abstention_ready = bool(
        contract_ready
        and uncertainty_report.applied is False
        and uncertainty_report.skipped_reason == "uncertainty_abstained"
        and uncertainty_report.uncertainty >= float(policy.abstain_threshold)
        and uncertainty_report.confidence <= 1.0 - float(policy.abstain_threshold)
        and nonfinite_uncertainty_report.applied is False
        and nonfinite_uncertainty_report.skipped_reason == "uncertainty_nonfinite"
        and nonfinite_uncertainty_report.confidence == 0.0
        and nonfinite_delta_report.applied is False
        and nonfinite_delta_report.skipped_reason == "delta_score_nonfinite"
    )
    top_k_policy_ready = bool(
        contract_ready
        and outside_top_k_report.applied is False
        and outside_top_k_report.skipped_reason == "outside_top_k_policy"
        and outside_top_k_report.top_k_eligible is False
        and outside_top_k_report.rank_pct > float(policy.top_k_rank_pct)
        and outside_top_k_report.policy_caps.get("top_k_rank_pct") == float(policy.top_k_rank_pct)
        and last_metadata.get("force_residual_top_k_eligible") is True
        and last_metadata.get("force_residual_rank_pct") <= float(policy.top_k_rank_pct)
    )
    contract_expected_report_count = 6
    contract_validated_report_count = len(validated_report_labels)
    contract_validation_ready = bool(
        contract_validated_report_count >= contract_expected_report_count
        and contract_ready
        and bounded_policy_ready
        and observed_caps_ready
        and confidence_abstention_ready
        and top_k_policy_ready
    )
    return {
        "row_count": int(row_count),
        "applied_count": int(applied),
        "delta_score_cap_abstention_count": int(cap_report.applied is False and cap_report.skipped_reason == "delta_score_cap_exceeded"),
        "uncertainty_abstention_count": int(confidence_abstention_ready),
        "nonfinite_uncertainty_abstention_count": int(
            nonfinite_uncertainty_report.applied is False
            and nonfinite_uncertainty_report.skipped_reason == "uncertainty_nonfinite"
        ),
        "nonfinite_delta_score_abstention_count": int(
            nonfinite_delta_report.applied is False
            and nonfinite_delta_report.skipped_reason == "delta_score_nonfinite"
        ),
        "outside_top_k_abstention_count": int(
            outside_top_k_report.applied is False
            and outside_top_k_report.skipped_reason == "outside_top_k_policy"
        ),
        "bounded_correction_policy_ready": bounded_policy_ready,
        "observed_caps_ready": observed_caps_ready,
        "contract_ready": contract_ready,
        "confidence_abstention_ready": confidence_abstention_ready,
        "top_k_policy_ready": top_k_policy_ready,
        "contract_expected_report_count": contract_expected_report_count,
        "contract_validated_report_count": contract_validated_report_count,
        "contract_validation_ready": contract_validation_ready,
        "contract_validated_report_labels": validated_report_labels,
        "required_policy_caps": sorted(required_policy_caps),
        "last_claim_metadata": last_metadata,
        "last_report": last_report,
        "delta_score_cap_report": cap_report.to_dict(),
        "uncertainty_abstention_report": uncertainty_report.to_dict(),
        "nonfinite_uncertainty_report": nonfinite_uncertainty_report.to_dict(),
        "nonfinite_delta_score_report": nonfinite_delta_report.to_dict(),
        "outside_top_k_report": outside_top_k_report.to_dict(),
        "duration_sec": elapsed,
        "rows_per_sec": float(row_count / elapsed) if elapsed > 0 else 0.0,
    }


def _neighbor_rebuild_kpi(frame_count: int = 12, rebuild_stride: int = 3) -> dict[str, Any]:
    base_x = torch.arange(16, dtype=torch.float32).view(1, 16, 1) * 4.0
    coords = torch.cat([base_x, torch.zeros(1, 16, 2, dtype=torch.float32)], dim=-1)
    forcefield = ProductForceField.from_registry(names=["legacy_lj"])
    state = EngineState(
        coords=coords,
        atom_types=torch.zeros(16, dtype=torch.long),
        metadata={
            "topology_fidelity": "sequence_mapped",
            "ligand_topology_valid": True,
            "hbond_evidence_status": "pass",
            "claim_safe": True,
            "blocked_reason": "",
        },
    )
    rebuild_count = 0
    pair_count = 0
    forcefield_pair_count = 0
    forcefield_neighbor_source = ""
    forcefield_neighbor_pairs_provided = False
    for frame_idx in range(int(frame_count)):
        coords = coords + 0.001
        if frame_idx % int(rebuild_stride) == 0:
            pairs = full_neighbor_pairs(coords, cutoff=8.0)
            rebuild_count += 1
            pair_count = int(pairs.mask.sum().item())
            state = EngineState(coords=coords, atom_types=state.atom_types, metadata=state.metadata)
            result = forcefield.energy_forces(state, pairs=pairs)
            forcefield_pair_count = int(result.diagnostics.get("neighbor_pair_count") or 0)
            forcefield_neighbor_source = str(result.diagnostics.get("neighbor_source") or "")
            forcefield_neighbor_pairs_provided = bool(
                result.diagnostics.get("neighbor_pairs_provided") is True
            )
    engine_neighbor_diagnostics_ready = bool(
        forcefield_pair_count == pair_count
        and forcefield_neighbor_pairs_provided
        and forcefield_neighbor_source == "provided"
    )
    return {
        "frame_count": int(frame_count),
        "rebuild_stride": int(rebuild_stride),
        "neighbor_list_rebuild_count": int(rebuild_count),
        "neighbor_list_rebuild_frequency": float(rebuild_count / max(int(frame_count), 1)),
        "last_neighbor_pair_count": int(pair_count),
        "last_forcefield_neighbor_pair_count": int(forcefield_pair_count),
        "forcefield_neighbor_source": forcefield_neighbor_source,
        "forcefield_neighbor_pairs_provided": forcefield_neighbor_pairs_provided,
        "engine_neighbor_diagnostics_ready": engine_neighbor_diagnostics_ready,
    }


def _physics_kpis() -> dict[str, Any]:
    coords = torch.tensor([[[0.0, 0.0, 0.0], [4.0, 0.0, 0.0], [0.0, 4.0, 0.0]]], dtype=torch.float64)
    state = EngineState(
        coords=coords,
        atom_types=torch.tensor([0, 0, 0]),
        metadata={
            "hbond_roles": ["donor", "acceptor", "none"],
            "hydrophobic_mask": torch.tensor([False, True, True]),
            "topology_fidelity": "sequence_mapped",
            "ligand_topology_valid": True,
            "hbond_evidence_status": "pass",
            "force_residual_applied": False,
            "claim_safe": True,
            "blocked_reason": "",
        },
    )
    term = LegacyLJTerm(sigma=1.0, epsilon=0.5)
    hbond = DirectionalHBondTerm()
    hydrophobic = HydrophobicContactTerm()
    hbond_result = hbond.energy_forces(state)
    hydrophobic_result = hydrophobic.energy_forces(state)
    force_term_validation_rows = []
    force_term_validation_thresholds = {
        "finite_difference_force_error_max": 1e-4,
        "translation_invariance_error_max": 1e-9,
        "rotation_equivariance_error_max": 1e-9,
        "energy_drift_smoke_pct_max": 5e-2,
    }
    rotation = torch.tensor(
        [
            [0.0, -1.0, 0.0],
            [1.0, 0.0, 0.0],
            [0.0, 0.0, 1.0],
        ],
        dtype=torch.float64,
    )
    shift = torch.tensor([[[7.0, -2.0, 1.0]]], dtype=torch.float64)
    for force_term in (term, hbond, hydrophobic):
        term_result = force_term.energy_forces(state)
        fd_error = finite_difference_force_error(force_term, state, atom_index=1, coord_index=0)
        translation_error = translation_invariance_error(force_term, state, shift)
        rotation_error = rotation_equivariance_error(force_term, state, rotation)
        drift_pct = energy_drift_smoke_pct(force_term, state, step_size=1e-4)
        ready = bool(
            fd_error < force_term_validation_thresholds["finite_difference_force_error_max"]
            and translation_error < force_term_validation_thresholds["translation_invariance_error_max"]
            and rotation_error < force_term_validation_thresholds["rotation_equivariance_error_max"]
            and drift_pct < force_term_validation_thresholds["energy_drift_smoke_pct_max"]
        )
        force_term_validation_rows.append(
            {
                "term": force_term.name,
                "ready": ready,
                "status": str(term_result.diagnostics.get("status") or ""),
                "active_pair_count": int(term_result.diagnostics.get("active_pair_count") or 0),
                "finite_difference_force_error": float(fd_error),
                "translation_invariance_error": float(translation_error),
                "rotation_equivariance_error": float(rotation_error),
                "energy_drift_smoke_pct": float(drift_pct),
                "claim_safe": term_result.claim_metadata.get("claim_safe") is True,
                "force_term_status": str(term_result.claim_metadata.get("force_term_status") or ""),
                "blocked_reason": str(term_result.claim_metadata.get("blocked_reason") or ""),
                "hydrophobic_contact_evidence_schema_version": str(
                    term_result.claim_metadata.get("hydrophobic_contact_evidence_schema_version") or ""
                ),
                "hydrophobic_contact_evidence_schema_ready": (
                    term_result.claim_metadata.get("hydrophobic_contact_evidence_schema_ready") is True
                ),
                "hydrophobic_contact_active_pair_count": int(
                    term_result.claim_metadata.get("hydrophobic_contact_active_pair_count") or 0
                ),
            }
        )
    force_term_validation_ready = bool(force_term_validation_rows and all(row["ready"] for row in force_term_validation_rows))
    force_term_validation_claim_safe_count = int(
        sum(1 for row in force_term_validation_rows if row["claim_safe"] is True)
    )
    force_term_validation_claim_safe_ready = bool(
        force_term_validation_rows
        and force_term_validation_claim_safe_count == len(force_term_validation_rows)
        and all(str(row["blocked_reason"] or "") == "" for row in force_term_validation_rows)
    )
    return {
        "finite_difference_force_error": finite_difference_force_error(term, state, atom_index=0, coord_index=0),
        "translation_invariance_error": translation_invariance_error(
            term,
            state,
            torch.tensor([[[7.0, -2.0, 1.0]]], dtype=torch.float64),
        ),
        "rotation_equivariance_error": rotation_equivariance_error(
            term,
            state,
            torch.tensor(
                [
                    [0.0, -1.0, 0.0],
                    [1.0, 0.0, 0.0],
                    [0.0, 0.0, 1.0],
                ],
                dtype=torch.float64,
            ),
        ),
        "directional_hbond_active_pair_count": int(hbond_result.diagnostics.get("active_pair_count", 0)),
        "hydrophobic_active_pair_count": int(hydrophobic_result.diagnostics.get("active_pair_count", 0)),
        "force_term_physics_validation_ready": force_term_validation_ready,
        "force_term_physics_validation_thresholds": force_term_validation_thresholds,
        "force_term_physics_validation_rows": force_term_validation_rows,
        "force_term_physics_validation_term_count": len(force_term_validation_rows),
        "force_term_physics_validation_claim_safe_count": force_term_validation_claim_safe_count,
        "force_term_physics_validation_claim_safe_ready": force_term_validation_claim_safe_ready,
        "force_term_finite_difference_max_error": float(
            max(row["finite_difference_force_error"] for row in force_term_validation_rows)
            if force_term_validation_rows
            else 0.0
        ),
        "force_term_translation_invariance_max_error": float(
            max(row["translation_invariance_error"] for row in force_term_validation_rows)
            if force_term_validation_rows
            else 0.0
        ),
        "force_term_rotation_equivariance_max_error": float(
            max(row["rotation_equivariance_error"] for row in force_term_validation_rows)
            if force_term_validation_rows
            else 0.0
        ),
        "force_term_energy_drift_max_pct": float(
            max(row["energy_drift_smoke_pct"] for row in force_term_validation_rows)
            if force_term_validation_rows
            else 0.0
        ),
        "energy_drift_smoke_pct": energy_drift_smoke_pct(term, state, step_size=1e-4),
        "neighbor_list_parity_error": neighbor_list_parity_error(coords, cutoff=8.0),
    }


def _chemistry_kpis() -> dict[str, Any]:
    rows = []
    two_bead = np.asarray([[0.0, 0.0, 0.0], [1.6, 0.0, 0.0]], dtype=np.float32)
    valid_count = 0
    hbond_positive = 0
    invalid_count = 0
    backmap_evaluable_count = 0
    backmap_claim_safe_count = 0
    backmap_failure_count = 0
    chirality_preserved = 0
    unassigned_chirality_blocked = 0
    ring_valid = 0
    protonation_valid = 0
    tautomer_valid = 0
    ligand_validity_schema_ready_count = 0
    unsatisfied_donor_total = 0
    unsatisfied_acceptor_total = 0
    unsatisfied_fixture_count = 0
    hbond_donor_site_total = 0
    hbond_acceptor_site_total = 0
    hbond_schema_ready_count = 0
    hbond_geometry_evaluated_count = 0
    hbond_geometry_complete_count = 0
    for label, smiles in CHEMISTRY_FIXTURES.items():
        ligand = ligand_topology_from_smiles(smiles)
        protein_xyz = None
        pocket_center = None
        mapped_sites = np.zeros((0, 3), dtype=np.float32)
        if ligand.validity.get("valid") is True:
            mapped_sites, _mapped_meta = backmap_4bead_onsps(two_bead, smiles)
            if mapped_sites.ndim == 2 and mapped_sites.shape[0] > 0:
                if label == "tertiary_amine":
                    protein_xyz = mapped_sites + np.asarray([[8.0, 8.0, 8.0]], dtype=np.float32)
                    pocket_center = mapped_sites.mean(axis=0) + np.asarray([0.0, 0.0, 6.0], dtype=np.float32)
                else:
                    protein_xyz = mapped_sites + np.asarray([[0.0, 0.0, 3.0]], dtype=np.float32)
                    pocket_center = mapped_sites.mean(axis=0) + np.asarray([0.0, 0.0, 6.0], dtype=np.float32)
        evidence = evaluate_hbond_evidence(
            smiles=smiles,
            ligand_xyz=two_bead,
            protein_xyz=protein_xyz,
            pocket_center=pocket_center,
        )
        backmap = evaluate_onsps_backmap_evidence(two_bead, smiles)
        validity = ligand.validity
        valid = bool(ligand.validity.get("valid"))
        chirality_present = int(validity.get("specified_chiral_center_count") or 0) > 0
        ring_atom_count = int(validity.get("ring_atom_count") or 0)
        formal_charge_sum = int(validity.get("formal_charge_sum") or 0)
        blockers = [str(v) for v in list(validity.get("claim_safe_blockers") or [])]
        ligand_validity_schema_ready = bool(
            validity.get("schema_version") == "ligand_topology_validity_v1"
            and isinstance(validity.get("valid"), bool)
            and isinstance(validity.get("claim_safe"), bool)
            and isinstance(validity.get("blocked_reason"), str)
            and isinstance(validity.get("claim_safe_blockers"), list)
            and isinstance(validity.get("source"), str)
            and isinstance(validity.get("reason"), str)
            and isinstance(validity.get("atom_count"), int)
            and isinstance(validity.get("hbond_site_count"), int)
            and isinstance(validity.get("ring_atom_count"), int)
            and isinstance(validity.get("formal_charge_sum"), int)
            and isinstance(validity.get("chiral_center_count"), int)
            and isinstance(validity.get("specified_chiral_center_count"), int)
            and isinstance(validity.get("unassigned_chiral_center_count"), int)
            and isinstance(validity.get("chirality_valid"), bool)
            and isinstance(validity.get("chirality_status"), str)
            and isinstance(validity.get("ring_valid"), bool)
            and isinstance(validity.get("ring_status"), str)
            and isinstance(validity.get("protonation_valid"), bool)
            and isinstance(validity.get("protonation_status"), str)
            and isinstance(validity.get("tautomer_valid"), bool)
            and isinstance(validity.get("tautomer_status"), str)
        )
        valid_count += int(valid)
        invalid_count += int(not valid)
        hbond_positive += int(evidence.site_count > 0)
        backmap_evaluable = bool(valid and backmap.site_count > 0)
        backmap_evaluable_count += int(backmap_evaluable)
        backmap_claim_safe_count += int(backmap_evaluable and backmap.claim_safe)
        backmap_failure_count += int(backmap_evaluable and not backmap.claim_safe)
        chirality_preserved += int(valid and chirality_present and validity.get("chirality_valid") is True)
        unassigned_chirality_blocked += int(
            valid
            and int(validity.get("unassigned_chiral_center_count") or 0) > 0
            and validity.get("claim_safe") is False
            and "unassigned_ligand_chirality" in blockers
        )
        ring_valid += int(valid and ring_atom_count > 0 and validity.get("ring_valid") is True)
        protonation_valid += int(valid and formal_charge_sum != 0 and validity.get("protonation_valid") is True)
        tautomer_valid += int(valid and "tautomer" in label and validity.get("tautomer_valid") is True)
        ligand_validity_schema_ready_count += int(ligand_validity_schema_ready)
        unsatisfied_total = int(evidence.unsatisfied_donor_count) + int(evidence.unsatisfied_acceptor_count)
        unsatisfied_donor_total += int(evidence.unsatisfied_donor_count)
        unsatisfied_acceptor_total += int(evidence.unsatisfied_acceptor_count)
        unsatisfied_fixture_count += int(unsatisfied_total > 0)
        hbond_role_site_count = int(evidence.donor_site_count) + int(evidence.acceptor_site_count)
        hbond_schema_ready = bool(evidence.schema_ready())
        hbond_donor_site_total += int(evidence.donor_site_count)
        hbond_acceptor_site_total += int(evidence.acceptor_site_count)
        hbond_schema_ready_count += int(hbond_schema_ready)
        hbond_geometry_evaluated_count += int(evidence.geometry_evaluated)
        hbond_geometry_complete_count += int(evidence.geometry_complete)
        rows.append(
            {
                "fixture": label,
                "smiles": smiles,
                "ligand_valid": valid,
                "ligand_validity_schema_version": validity.get("schema_version", ""),
                "ligand_validity_schema_ready": ligand_validity_schema_ready,
                "validity_reason": ligand.validity.get("reason", ""),
                "ligand_topology_claim_safe": validity.get("claim_safe") is True,
                "ligand_topology_source": validity.get("source", ""),
                "ligand_validity_blockers": list(validity.get("claim_safe_blockers") or []),
                "chiral_center_count": int(validity.get("chiral_center_count") or 0),
                "specified_chiral_center_count": int(validity.get("specified_chiral_center_count") or 0),
                "unassigned_chiral_center_count": int(validity.get("unassigned_chiral_center_count") or 0),
                "chirality_status": validity.get("chirality_status", ""),
                "ring_status": validity.get("ring_status", ""),
                "protonation_status": validity.get("protonation_status", ""),
                "tautomer_status": validity.get("tautomer_status", ""),
                "chirality_present": chirality_present,
                "ring_atom_count": ring_atom_count,
                "formal_charge_sum": formal_charge_sum,
                "tautomer_fixture_valid": bool(valid and "tautomer" in label),
                "hbond_schema_version": evidence.schema_version,
                "hbond_schema_ready": hbond_schema_ready,
                "hbond_threshold_schema_ready": evidence.threshold_schema_ready(),
                "hbond_pair_schema_ready": evidence.pair_schema_ready(),
                "hbond_geometry_flags_ready": evidence.geometry_flags_ready(),
                "hbond_donor_site_count": int(evidence.donor_site_count),
                "hbond_acceptor_site_count": int(evidence.acceptor_site_count),
                "hbond_role_site_count": hbond_role_site_count,
                "hbond_distance_pass_count": int(evidence.distance_pass_count),
                "hbond_angle_pass_count": int(evidence.angle_pass_count),
                "hbond_geometry_evaluated": evidence.geometry_evaluated,
                "hbond_geometry_complete": evidence.geometry_complete,
                "hbond_delta_backmap": evidence.delta_backmap,
                "hbond_delta_backmap_max": evidence.delta_backmap_max,
                "hbond_delta_backmap_evaluated": evidence.delta_backmap_evaluated,
                "hbond_delta_backmap_yellow_band": evidence.delta_backmap_yellow_band,
                "hbond_abstention_reason": evidence.abstention_reason,
                "hbond_blocked_reason": evidence.blocked_reason,
                "onsps_backmap_schema_version": evidence.onsps_backmap_metadata.get("schema_version", ""),
                "onsps_backmap_status": evidence.onsps_backmap_metadata.get("backmap_status", ""),
                "onsps_backmap_source": evidence.onsps_backmap_metadata.get("mapping_source", ""),
                "onsps_backmap_claim_safe": evidence.onsps_backmap_metadata.get("claim_safe"),
                "onsps_backmap_blocked_reason": evidence.onsps_backmap_metadata.get("blocked_reason", ""),
                "backmap_evaluable": backmap_evaluable,
                "backmap_schema_version": backmap.schema_version,
                "backmap_status": backmap.backmap_status,
                "backmap_source": backmap.mapping_source,
                "backmap_claim_safe": backmap.claim_safe,
                "backmap_blocked_reason": backmap.blocked_reason,
                "backmap_site_count": backmap.site_count,
                "backmap_mapped_site_count": backmap.mapped_site_count,
                "site_count": evidence.site_count,
                "unsatisfied_donor_count": evidence.unsatisfied_donor_count,
                "unsatisfied_acceptor_count": evidence.unsatisfied_acceptor_count,
                "overanchoring_flag": evidence.overanchoring_flag,
            }
        )
    return {
        "fixture_count": len(CHEMISTRY_FIXTURES),
        "valid_ligand_count": valid_count,
        "invalid_ligand_count": invalid_count,
        "hbond_recovery_fixture_count": hbond_positive,
        "hbond_evidence_schema_ready": bool(
            hbond_schema_ready_count == len(CHEMISTRY_FIXTURES)
        ),
        "hbond_evidence_schema_ready_count": hbond_schema_ready_count,
        "hbond_donor_site_count": hbond_donor_site_total,
        "hbond_acceptor_site_count": hbond_acceptor_site_total,
        "hbond_geometry_evaluated_fixture_count": hbond_geometry_evaluated_count,
        "hbond_geometry_complete_fixture_count": hbond_geometry_complete_count,
        "backmap_evaluable_fixture_count": backmap_evaluable_count,
        "backmap_claim_safe_fixture_count": backmap_claim_safe_count,
        "backmap_failure_count": backmap_failure_count,
        "ligand_topology_validity_schema_ready": bool(
            ligand_validity_schema_ready_count == len(CHEMISTRY_FIXTURES)
        ),
        "ligand_topology_validity_schema_ready_count": ligand_validity_schema_ready_count,
        "chirality_preservation_fixture_count": chirality_preserved,
        "unassigned_chirality_blocked_fixture_count": unassigned_chirality_blocked,
        "chirality_preservation_ready": bool(chirality_preserved > 0 and unassigned_chirality_blocked > 0),
        "ring_validity_fixture_count": ring_valid,
        "ring_validity_ready": bool(ring_valid > 0),
        "protonation_validity_fixture_count": protonation_valid,
        "protonation_validity_ready": bool(protonation_valid > 0),
        "tautomer_validity_fixture_count": tautomer_valid,
        "tautomer_validity_ready": bool(tautomer_valid > 0),
        "unsatisfied_donor_count": unsatisfied_donor_total,
        "unsatisfied_acceptor_count": unsatisfied_acceptor_total,
        "unsatisfied_donor_acceptor_fixture_count": unsatisfied_fixture_count,
        "topology_invalid_rate": float(invalid_count / max(len(CHEMISTRY_FIXTURES), 1)),
        "backmapping_failure_rate": float(backmap_failure_count / max(backmap_evaluable_count, 1)),
        "rows": rows,
    }


def _product_bundle_validation_kpi(product_evidence_bundle_json_path: str) -> dict[str, Any]:
    packet = _read_json_if_present(product_evidence_bundle_json_path)
    if not packet:
        return {
            "bundle_validation_pass": False,
            "bundle_validation_checked": False,
            "bundle_validation_error_count": 1,
            "bundle_validation_errors": ["product_evidence_bundle_json_missing"],
            "clean_install_success": False,
            "clean_container_smoke_ready": False,
            "product_runner_smoke_ready": False,
            "product_image_receipt_present": False,
            "product_image_receipt_mode": "",
            "product_image_receipt_status": "",
            "product_claim_ready": False,
            "release_claim_ready": False,
            "release_claim_blocked_reason": "product_evidence_bundle_json_missing",
            "product_ci_runtime_gate_ready": False,
            "product_ci_remote_green": False,
            "product_ci_github_actions_started": False,
            "product_ci_external_blocker": False,
            "product_ci_blocker_code": "",
            "product_ci_billing_free_self_hosted_path_recommended": False,
            "product_ci_billing_free_self_hosted_api_worker_command": "",
            "product_ci_billing_free_self_hosted_rocm_runtime_command": "",
            "product_ci_hosted_spending_limit_increase_required": False,
            "product_ci_self_hosted_runner_inventory_present": False,
            "product_ci_self_hosted_runner_total_count": 0,
            "product_ci_self_hosted_linux_runner_online": False,
            "product_ci_self_hosted_linux_runner_count": 0,
            "product_ci_self_hosted_rocm_runner_online": False,
            "product_ci_self_hosted_rocm_runner_count": 0,
            "product_ci_self_hosted_runner_inventory_external_state_mutated": False,
            "product_ci_self_hosted_runner_host_preflight_present": False,
            "product_ci_self_hosted_runner_host_preflight_status": "",
            "product_ci_self_hosted_runner_host_local_ready": False,
            "product_ci_self_hosted_runner_host_repo_ready": False,
            "product_ci_self_hosted_runner_host_registration_required": False,
            "product_ci_self_hosted_runner_host_github_registration_token_requested": False,
            "product_ci_self_hosted_runner_host_external_state_mutated": False,
            "product_image_preflight_blocker_codes": [],
            "clean_install_missing_requirements": [
                "clean_container_smoke_ready",
                "product_runner_smoke_ready",
                "product_image_receipt_present",
                "product_image_receipt_mode_rocm_runtime",
            ],
            "clean_install_missing_requirement_count": 4,
            "clean_container_missing_requirements": [],
            "clean_container_missing_requirement_count": 0,
            "source_artifacts_fresh": False,
            "source_artifact_fresh_count": 0,
            "source_artifact_stale_count": 0,
            "source_artifact_stale_ids": [],
        }
    validation = validate_product_evidence_bundle(bundle_packet=packet)
    validation_errors = list(validation.get("bundle_validation_errors") or [])
    self_freshness_errors = {
        "kpi_source_artifacts_not_fresh",
        "pm_source_artifacts_fresh_gate_missing",
    }
    error_codes = {str(error).split(":", 1)[0] for error in validation_errors}
    cycle_recovered = bool(
        validation_errors
        and error_codes <= self_freshness_errors
        and validation.get("source_artifacts_fresh") is True
    )
    if cycle_recovered:
        validation.update(
            {
                "bundle_validation_pass": True,
                "bundle_validation_error_count": 0,
                "bundle_validation_errors": [],
                "bundle_validation_cycle_recovered": True,
                "bundle_validation_cycle_recovered_errors": validation_errors,
            }
        )
    else:
        validation["bundle_validation_cycle_recovered"] = False
        validation["bundle_validation_cycle_recovered_errors"] = []
    summary = packet.get("summary") if isinstance(packet.get("summary"), dict) else packet
    clean_install_requirements = {
        "clean_container_smoke_ready": summary.get("clean_container_smoke_ready") is True,
        "product_runner_smoke_ready": summary.get("product_runner_smoke_ready") is True,
        "product_image_receipt_present": summary.get("product_image_receipt_present") is True,
        "product_image_receipt_mode_rocm_runtime": summary.get("product_image_receipt_mode") == "rocm-runtime",
    }
    clean_install_missing_requirements = [
        requirement for requirement, passed in clean_install_requirements.items() if passed is not True
    ]
    clean_install_success = bool(
        not clean_install_missing_requirements
    )
    validation.update(
        {
            "clean_install_success": clean_install_success,
            "clean_install_requirements": clean_install_requirements,
            "clean_install_missing_requirements": clean_install_missing_requirements,
            "clean_install_missing_requirement_count": len(clean_install_missing_requirements),
            "clean_container_smoke_ready": bool(summary.get("clean_container_smoke_ready") is True),
            "product_runner_smoke_ready": bool(summary.get("product_runner_smoke_ready") is True),
            "product_image_receipt_present": bool(summary.get("product_image_receipt_present") is True),
            "product_image_receipt_mode": str(summary.get("product_image_receipt_mode") or ""),
            "product_image_receipt_status": str(summary.get("product_image_receipt_status") or ""),
            "product_claim_ready": bool(summary.get("product_claim_ready") is True),
            "release_claim_ready": bool(summary.get("release_claim_ready") is True),
            "release_claim_blocked_reason": str(summary.get("release_claim_blocked_reason") or ""),
            "product_ci_runtime_gate_ready": bool(
                summary.get("product_ci_runtime_gate_ready") is True
            ),
            "product_ci_remote_green": bool(summary.get("product_ci_remote_green") is True),
            "product_ci_github_actions_started": bool(
                summary.get("product_ci_github_actions_started") is True
            ),
            "product_ci_external_blocker": bool(summary.get("product_ci_external_blocker") is True),
            "product_ci_blocker_code": str(summary.get("product_ci_blocker_code") or ""),
            "product_ci_billing_free_self_hosted_path_recommended": bool(
                summary.get("product_ci_billing_free_self_hosted_path_recommended") is True
            ),
            "product_ci_billing_free_self_hosted_api_worker_command": str(
                summary.get("product_ci_billing_free_self_hosted_api_worker_command") or ""
            ),
            "product_ci_billing_free_self_hosted_rocm_runtime_command": str(
                summary.get("product_ci_billing_free_self_hosted_rocm_runtime_command") or ""
            ),
            "product_ci_hosted_spending_limit_increase_required": bool(
                summary.get("product_ci_hosted_spending_limit_increase_required") is True
            ),
            "product_ci_self_hosted_runner_inventory_present": bool(
                summary.get("product_ci_self_hosted_runner_inventory_present") is True
            ),
            "product_ci_self_hosted_runner_total_count": int(
                summary.get("product_ci_self_hosted_runner_total_count") or 0
            ),
            "product_ci_self_hosted_linux_runner_online": bool(
                summary.get("product_ci_self_hosted_linux_runner_online") is True
            ),
            "product_ci_self_hosted_linux_runner_count": int(
                summary.get("product_ci_self_hosted_linux_runner_count") or 0
            ),
            "product_ci_self_hosted_rocm_runner_online": bool(
                summary.get("product_ci_self_hosted_rocm_runner_online") is True
            ),
            "product_ci_self_hosted_rocm_runner_count": int(
                summary.get("product_ci_self_hosted_rocm_runner_count") or 0
            ),
            "product_ci_self_hosted_runner_inventory_external_state_mutated": bool(
                summary.get("product_ci_self_hosted_runner_inventory_external_state_mutated") is True
            ),
            "product_ci_self_hosted_runner_host_preflight_present": bool(
                summary.get("product_ci_self_hosted_runner_host_preflight_present") is True
            ),
            "product_ci_self_hosted_runner_host_preflight_status": str(
                summary.get("product_ci_self_hosted_runner_host_preflight_status") or ""
            ),
            "product_ci_self_hosted_runner_host_local_ready": bool(
                summary.get("product_ci_self_hosted_runner_host_local_ready") is True
            ),
            "product_ci_self_hosted_runner_host_repo_ready": bool(
                summary.get("product_ci_self_hosted_runner_host_repo_ready") is True
            ),
            "product_ci_self_hosted_runner_host_registration_required": bool(
                summary.get("product_ci_self_hosted_runner_host_registration_required") is True
            ),
            "product_ci_self_hosted_runner_host_github_registration_token_requested": bool(
                summary.get("product_ci_self_hosted_runner_host_github_registration_token_requested") is True
            ),
            "product_ci_self_hosted_runner_host_external_state_mutated": bool(
                summary.get("product_ci_self_hosted_runner_host_external_state_mutated") is True
            ),
            "product_image_preflight_blocker_codes": list(
                summary.get("product_image_preflight_blocker_codes") or []
            ),
            "clean_container_missing_requirements": list(
                summary.get("clean_container_missing_requirements") or []
            ),
            "clean_container_missing_requirement_count": int(
                summary.get("clean_container_missing_requirement_count") or 0
            ),
            "source_artifacts_fresh": bool(validation.get("source_artifacts_fresh") is True),
            "source_artifact_fresh_count": int(validation.get("source_artifact_fresh_count") or 0),
            "source_artifact_stale_count": int(validation.get("source_artifact_stale_count") or 0),
            "source_artifact_stale_ids": list(validation.get("source_artifact_stale_ids") or []),
        }
    )
    return validation


def _product_ci_runtime_gate_kpi(product_ci_runtime_gate_json_path: str) -> dict[str, Any]:
    packet = _read_json_if_present(product_ci_runtime_gate_json_path)
    summary = packet.get("summary") if isinstance(packet.get("summary"), dict) else packet
    if not isinstance(summary, dict):
        summary = {}
    runtime_gate_ready = bool(summary.get("runtime_gate_ready") is True)
    external_blocker = bool(summary.get("external_blocker") is True)
    return {
        "product_ci_runtime_gate_present": bool(packet),
        "product_ci_runtime_gate_ready": runtime_gate_ready,
        "product_ci_runtime_gate_status": str(summary.get("status") or ""),
        "product_ci_remote_green": bool(summary.get("remote_product_ci_green") is True),
        "product_ci_github_actions_started": bool(summary.get("github_actions_started") is True),
        "product_ci_external_blocker": external_blocker,
        "product_ci_blocker_code": str(summary.get("blocker_code") or ""),
        "product_ci_billing_free_self_hosted_path_recommended": bool(
            summary.get("billing_free_self_hosted_path_recommended") is True
        ),
        "product_ci_billing_free_self_hosted_api_worker_command": str(
            summary.get("billing_free_self_hosted_api_worker_command") or ""
        ),
        "product_ci_billing_free_self_hosted_rocm_runtime_command": str(
            summary.get("billing_free_self_hosted_rocm_runtime_command") or ""
        ),
        "product_ci_hosted_spending_limit_increase_required": bool(
            summary.get("hosted_spending_limit_increase_required") is True
        ),
        "product_ci_self_hosted_runner_inventory_present": bool(
            summary.get("self_hosted_runner_inventory_present") is True
        ),
        "product_ci_self_hosted_runner_total_count": int(
            summary.get("self_hosted_runner_total_count") or 0
        ),
        "product_ci_self_hosted_linux_runner_online": bool(
            summary.get("self_hosted_linux_runner_online") is True
        ),
        "product_ci_self_hosted_linux_runner_count": int(
            summary.get("self_hosted_linux_runner_count") or 0
        ),
        "product_ci_self_hosted_rocm_runner_online": bool(
            summary.get("self_hosted_rocm_runner_online") is True
        ),
        "product_ci_self_hosted_rocm_runner_count": int(
            summary.get("self_hosted_rocm_runner_count") or 0
        ),
        "product_ci_self_hosted_runner_inventory_external_state_mutated": bool(
            summary.get("self_hosted_runner_inventory_external_state_mutated") is True
        ),
        "product_ci_self_hosted_runner_host_preflight_present": bool(
            summary.get("self_hosted_runner_host_preflight_present") is True
        ),
        "product_ci_self_hosted_runner_host_preflight_status": str(
            summary.get("self_hosted_runner_host_preflight_status") or ""
        ),
        "product_ci_self_hosted_runner_host_local_ready": bool(
            summary.get("self_hosted_runner_host_local_ready") is True
        ),
        "product_ci_self_hosted_runner_host_repo_ready": bool(
            summary.get("self_hosted_runner_host_repo_ready") is True
        ),
        "product_ci_self_hosted_runner_host_registration_required": bool(
            summary.get("self_hosted_runner_host_registration_required") is True
        ),
        "product_ci_self_hosted_runner_host_github_registration_token_requested": bool(
            summary.get("self_hosted_runner_host_github_registration_token_requested") is True
        ),
        "product_ci_self_hosted_runner_host_external_state_mutated": bool(
            summary.get("self_hosted_runner_host_external_state_mutated") is True
        ),
        "product_ci_latest_github_actions_record_kst_date": str(
            summary.get("latest_github_actions_record_kst_date") or ""
        ),
        "product_ci_workflow_dispatch_executed": bool(
            summary.get("workflow_dispatch_executed") is True
        ),
        "product_ci_external_state_mutated": bool(summary.get("external_state_mutated") is True),
        "product_ci_claim_boundary": str(summary.get("claim_boundary") or ""),
    }


def _force_term_claim_metadata_kpi(force_term_plugins: list[str]) -> dict[str, Any]:
    forcefield = ProductForceField.from_registry(names=force_term_plugins)
    state = EngineState(
        coords=torch.tensor([[[0.0, 0.0, 0.0], [3.0, 0.0, 0.0], [5.0, 0.0, 0.0]]]),
        atom_types=torch.tensor([0, 1, 2]),
        metadata={
            "hbond_roles": ["donor", "acceptor", "none"],
            "hydrophobic_mask": torch.tensor([False, True, True]),
            "topology_fidelity": "sequence_mapped",
            "ligand_topology_valid": True,
            "hbond_evidence_status": "pass",
            "claim_safe": True,
            "blocked_reason": "",
        },
    )
    result = forcefield.energy_forces(
        state,
        claim_metadata={
            "topology_fidelity": "sequence_mapped",
            "ligand_topology_valid": True,
            "hbond_evidence_status": "pass",
            "claim_safe": True,
            "blocked_reason": "",
        },
    )
    unsafe_claim_metadata = {
        "topology_fidelity": "placeholder_alanine",
        "ligand_topology_valid": False,
        "hbond_evidence_status": "not_assessed",
        "claim_safe": False,
        "blocked_reason": "placeholder_alanine_topology",
    }
    unsafe_state = EngineState(
        coords=state.coords,
        atom_types=state.atom_types,
        metadata={
            **state.metadata,
            **unsafe_claim_metadata,
        },
    )
    unsafe_result = forcefield.energy_forces(
        unsafe_state,
        claim_metadata=unsafe_claim_metadata,
    )
    unsafe_claim_rows = list(unsafe_result.claim_metadata.get("force_term_claim_rows") or [])
    unsafe_base_claim_blocked = bool(
        unsafe_result.claim_metadata.get("claim_safe") is False
        and unsafe_result.claim_metadata.get("blocked_reason") == "placeholder_alanine_topology"
        and int(unsafe_result.claim_metadata.get("force_term_claim_safe_count") or 0) == 0
        and int(unsafe_result.claim_metadata.get("force_term_blocked_count") or 0) == len(force_term_plugins)
        and len(unsafe_claim_rows) == len(force_term_plugins)
        and all(
            isinstance(row, dict)
            and row.get("claim_safe") is False
            and row.get("blocked_reason") == "placeholder_alanine_topology"
            for row in unsafe_claim_rows
        )
    )
    rows: list[dict[str, Any]] = []
    required_keys = {
        "topology_fidelity",
        "ligand_topology_valid",
        "hbond_evidence_status",
        "force_residual_applied",
        "claim_safe",
        "blocked_reason",
        "force_term_name",
        "force_term_status",
    }
    term_diagnostics = result.diagnostics.get("term_diagnostics")
    if not isinstance(term_diagnostics, dict):
        term_diagnostics = {}
    forcefield_neighbor_pair_count = int(result.diagnostics.get("neighbor_pair_count") or 0)
    forcefield_neighbor_diagnostics_ready = bool(
        forcefield_neighbor_pair_count > 0
        and result.diagnostics.get("neighbor_pairs_provided") is False
        and result.diagnostics.get("neighbor_source") == "full_neighbor_pairs"
    )
    term_result_contract_rows: list[dict[str, Any]] = []
    forcefield_energy_forces_contract_error = ""
    try:
        validate_energy_forces_contract(result=result, coords=state.coords)
        forcefield_energy_forces_contract_ready = True
    except Exception as exc:
        forcefield_energy_forces_contract_ready = False
        forcefield_energy_forces_contract_error = f"{type(exc).__name__}:{exc}"
    for term in default_force_term_registry().create(force_term_plugins):
        term_name = str(getattr(term, "name", term.__class__.__name__))
        try:
            term_result = term.energy_forces(state)
            energy_is_tensor = isinstance(term_result.energy, torch.Tensor)
            forces_is_tensor = isinstance(term_result.forces, torch.Tensor)
            diagnostics_is_dict = isinstance(term_result.diagnostics, dict)
            claim_metadata_is_dict = isinstance(term_result.claim_metadata, dict)
            energy_shape = list(term_result.energy.shape) if energy_is_tensor else []
            forces_shape = list(term_result.forces.shape) if forces_is_tensor else []
            energy_finite = bool(torch.isfinite(term_result.energy).all().item()) if energy_is_tensor else False
            forces_finite = bool(torch.isfinite(term_result.forces).all().item()) if forces_is_tensor else False
            has_diagnostics_keys = diagnostics_is_dict and {"term", "status"}.issubset(term_result.diagnostics)
            has_claim_keys = claim_metadata_is_dict and required_keys.issubset(term_result.claim_metadata)
            row_ready = bool(
                energy_is_tensor
                and forces_is_tensor
                and diagnostics_is_dict
                and claim_metadata_is_dict
                and energy_shape == [1]
                and forces_shape == list(state.coords.shape)
                and energy_finite
                and forces_finite
                and has_diagnostics_keys
                and has_claim_keys
                and term_result.diagnostics.get("term") == term_name
                and term_result.diagnostics.get("status") == "pass"
                and term_result.claim_metadata.get("force_term_name") == term_name
                and term_result.claim_metadata.get("force_term_status") == "pass"
            )
            term_result_contract_rows.append(
                {
                    "term": term_name,
                    "ready": row_ready,
                    "energy_shape": energy_shape,
                    "forces_shape": forces_shape,
                    "diagnostics_keys_present": bool(has_diagnostics_keys),
                    "claim_metadata_keys_present": bool(has_claim_keys),
                    "energy_finite": energy_finite,
                    "forces_finite": forces_finite,
                    "diagnostics_term": str(term_result.diagnostics.get("term") or "")
                    if diagnostics_is_dict else "",
                    "diagnostics_status": str(term_result.diagnostics.get("status") or "")
                    if diagnostics_is_dict else "",
                    "claim_force_term_name": str(term_result.claim_metadata.get("force_term_name") or "")
                    if claim_metadata_is_dict else "",
                    "claim_force_term_status": str(term_result.claim_metadata.get("force_term_status") or "")
                    if claim_metadata_is_dict else "",
                    "error": "",
                }
            )
        except Exception as exc:
            term_result_contract_rows.append(
                {
                    "term": term_name,
                    "ready": False,
                    "energy_shape": [],
                    "forces_shape": [],
                    "diagnostics_keys_present": False,
                    "claim_metadata_keys_present": False,
                    "energy_finite": False,
                    "forces_finite": False,
                    "diagnostics_term": "",
                    "diagnostics_status": "",
                    "claim_force_term_name": "",
                    "claim_force_term_status": "",
                    "error": f"{type(exc).__name__}:{exc}",
                }
            )
    for name, diagnostics in term_diagnostics.items():
        term_metadata = diagnostics.get("claim_metadata") if isinstance(diagnostics, dict) else {}
        if not isinstance(term_metadata, dict):
            term_metadata = {}
        rows.append(
            {
                "term": str(name),
                "status": str(diagnostics.get("status") or "") if isinstance(diagnostics, dict) else "",
                "claim_safe": term_metadata.get("claim_safe") is True,
                "blocked_reason": str(term_metadata.get("blocked_reason") or ""),
                "has_required_claim_keys": required_keys.issubset(term_metadata),
                "force_term_name": str(term_metadata.get("force_term_name") or ""),
                "force_term_status": str(term_metadata.get("force_term_status") or ""),
                "hbond_evidence_schema_version": str(
                    term_metadata.get("hbond_evidence_schema_version") or ""
                ),
                "hbond_evidence_schema_ready": term_metadata.get("hbond_evidence_schema_ready") is True,
                "hydrophobic_contact_evidence_schema_version": str(
                    term_metadata.get("hydrophobic_contact_evidence_schema_version") or ""
                ),
                "hydrophobic_contact_evidence_schema_ready": (
                    term_metadata.get("hydrophobic_contact_evidence_schema_ready") is True
                ),
                "hydrophobic_contact_active_pair_count": int(
                    term_metadata.get("hydrophobic_contact_active_pair_count") or 0
                ),
                "hydrophobic_contact_mask_present": (
                    term_metadata.get("hydrophobic_contact_mask_present") is True
                ),
                "hydrophobic_contact_mask_count": int(
                    term_metadata.get("hydrophobic_contact_mask_count") or 0
                ),
                "hydrophobic_contact_energy_model": str(
                    term_metadata.get("hydrophobic_contact_energy_model") or ""
                ),
            }
        )
    hbond_schema_ready = bool(
        result.claim_metadata.get("hbond_evidence_schema_version") == "hbond_evidence_v1"
        and result.claim_metadata.get("hbond_evidence_schema_ready") is True
    )
    hydrophobic_schema_ready = bool(
        result.claim_metadata.get("hydrophobic_contact_evidence_schema_version")
        == "hydrophobic_contact_evidence_v1"
        and result.claim_metadata.get("hydrophobic_contact_evidence_schema_ready") is True
        and int(result.claim_metadata.get("hydrophobic_contact_active_pair_count") or 0) > 0
    )
    ready = bool(
        result.claim_metadata.get("claim_safe") is True
        and unsafe_base_claim_blocked
        and forcefield_energy_forces_contract_ready
        and forcefield_neighbor_diagnostics_ready
        and result.claim_metadata.get("force_term_claim_metadata_ready") is True
        and result.claim_metadata.get("force_term_claim_metadata_schema_version")
        == "force_term_claim_metadata_v1"
        and int(result.claim_metadata.get("force_term_claim_safe_count") or 0) == len(force_term_plugins)
        and int(result.claim_metadata.get("force_term_blocked_count") or 0) == 0
        and isinstance(result.claim_metadata.get("force_term_claim_rows"), list)
        and len(result.claim_metadata.get("force_term_claim_rows") or []) == len(force_term_plugins)
        and hbond_schema_ready
        and hydrophobic_schema_ready
        and len(rows) == len(force_term_plugins)
        and all(
            row["claim_safe"] is True
            and row["blocked_reason"] == ""
            and row["has_required_claim_keys"] is True
            and row["force_term_name"] == row["term"]
            and row["force_term_status"] == "pass"
            for row in rows
        )
    )
    term_result_contract_ready = bool(
        len(term_result_contract_rows) == len(force_term_plugins)
        and all(row["ready"] is True for row in term_result_contract_rows)
    )
    term_result_contract_terms = [
        str(row.get("term") or "")
        for row in term_result_contract_rows
        if isinstance(row, dict) and str(row.get("term") or "")
    ]
    term_result_contract_term_set_ready = bool(
        set(term_result_contract_terms) == set(EXPECTED_PRODUCT_FORCE_TERMS)
        and len(term_result_contract_rows) == len(EXPECTED_PRODUCT_FORCE_TERMS)
    )
    return {
        "ready": ready,
        "term_result_contract_ready": term_result_contract_ready,
        "term_result_contract_term_set_ready": term_result_contract_term_set_ready,
        "term_result_contract_term_count": len(term_result_contract_rows),
        "term_result_contract_terms": term_result_contract_terms,
        "term_result_contract_expected_terms": list(EXPECTED_PRODUCT_FORCE_TERMS),
        "forcefield_energy_forces_contract_ready": forcefield_energy_forces_contract_ready,
        "forcefield_energy_forces_contract_error": forcefield_energy_forces_contract_error,
        "forcefield_energy_shape": list(result.energy.shape),
        "forcefield_forces_shape": list(result.forces.shape),
        "forcefield_energy_finite": bool(torch.isfinite(result.energy).all().item()),
        "forcefield_forces_finite": bool(torch.isfinite(result.forces).all().item()),
        "forcefield_term_count": int(result.diagnostics.get("term_count") or 0),
        "forcefield_term_diagnostics_ready": isinstance(
            result.diagnostics.get("term_diagnostics"), dict
        ) and set(result.diagnostics.get("term_diagnostics", {})) == set(result.terms),
        "forcefield_claim_safe": result.claim_metadata.get("claim_safe") is True,
        "forcefield_unsafe_base_claim_blocked": unsafe_base_claim_blocked,
        "forcefield_unsafe_base_claim_safe": unsafe_result.claim_metadata.get("claim_safe") is True,
        "forcefield_unsafe_base_blocked_reason": str(
            unsafe_result.claim_metadata.get("blocked_reason") or ""
        ),
        "forcefield_unsafe_base_claim_safe_count": int(
            unsafe_result.claim_metadata.get("force_term_claim_safe_count") or 0
        ),
        "forcefield_unsafe_base_blocked_count": int(
            unsafe_result.claim_metadata.get("force_term_blocked_count") or 0
        ),
        "forcefield_unsafe_base_claim_rows": unsafe_claim_rows,
        "forcefield_neighbor_diagnostics_ready": forcefield_neighbor_diagnostics_ready,
        "forcefield_neighbor_pair_count": forcefield_neighbor_pair_count,
        "forcefield_neighbor_pairs_provided": bool(
            result.diagnostics.get("neighbor_pairs_provided") is True
        ),
        "forcefield_neighbor_source": str(result.diagnostics.get("neighbor_source") or ""),
        "forcefield_blocked_reason": str(result.claim_metadata.get("blocked_reason") or ""),
        "forcefield_hbond_evidence_status": str(result.claim_metadata.get("hbond_evidence_status") or ""),
        "forcefield_hbond_evidence_schema_version": str(
            result.claim_metadata.get("hbond_evidence_schema_version") or ""
        ),
        "forcefield_hbond_evidence_schema_ready": hbond_schema_ready,
        "forcefield_hydrophobic_contact_evidence_schema_version": str(
            result.claim_metadata.get("hydrophobic_contact_evidence_schema_version") or ""
        ),
        "forcefield_hydrophobic_contact_evidence_schema_ready": hydrophobic_schema_ready,
        "forcefield_hydrophobic_contact_active_pair_count": int(
            result.claim_metadata.get("hydrophobic_contact_active_pair_count") or 0
        ),
        "forcefield_claim_metadata_schema_version": str(
            result.claim_metadata.get("force_term_claim_metadata_schema_version") or ""
        ),
        "forcefield_claim_safe_count": int(result.claim_metadata.get("force_term_claim_safe_count") or 0),
        "forcefield_blocked_count": int(result.claim_metadata.get("force_term_blocked_count") or 0),
        "forcefield_claim_rows": list(result.claim_metadata.get("force_term_claim_rows") or []),
        "term_count": len(rows),
        "term_result_contract_rows": term_result_contract_rows,
        "rows": rows,
    }


def _guarded_force_term_plugin_kpi() -> dict[str, Any]:
    registry = guarded_force_term_registry()
    default_names = default_force_term_registry().names()
    guarded_names = registry.names()
    required_guarded_terms = [
        "pocket_wall",
        "screened_electrostatics",
        "topology_penalty",
        "torsion_prior",
        "water_displacement_proxy",
    ]
    coords = torch.tensor(
        [[[0.0, 0.0, 0.0], [4.0, 0.0, 0.0], [0.0, 5.0, 0.0]]],
        dtype=torch.float64,
    )
    atom_types = torch.tensor([0, 1, 2])
    charge_metadata = {
        "partial_charges": torch.tensor([1.0, -1.0, 0.5], dtype=torch.float64),
        "charge_source": "kpi_validated_proxy",
        "charge_model_valid": True,
        "topology_fidelity": "sequence_mapped",
        "ligand_topology_valid": True,
        "hbond_evidence_status": "pass",
        "claim_safe": True,
        "blocked_reason": "",
    }
    state = EngineState(coords=coords, atom_types=atom_types, metadata=charge_metadata)
    term = registry.create(["screened_electrostatics"])[0]
    result = term.energy_forces(state)
    fd_error = finite_difference_force_error(term, state, atom_index=0, coord_index=0)
    pocket_coords = torch.tensor(
        [[[0.0, 0.0, 0.0], [2.0, 0.0, 0.0], [4.0, 0.0, 0.0]]],
        dtype=torch.float64,
    )
    pocket_metadata = {
        "pocket_atom_indices": [0],
        "ligand_atom_indices": [1, 2],
        "pocket_radius": 1.0,
        "topology_fidelity": "sequence_mapped",
        "ligand_topology_valid": True,
        "hbond_evidence_status": "pass",
        "claim_safe": True,
        "blocked_reason": "",
    }
    pocket_state = EngineState(
        coords=pocket_coords,
        atom_types=atom_types,
        metadata=pocket_metadata,
    )
    pocket_term = registry.create(["pocket_wall"])[0]
    pocket_result = pocket_term.energy_forces(pocket_state)
    pocket_fd_error = finite_difference_force_error(
        pocket_term,
        pocket_state,
        atom_index=1,
        coord_index=0,
    )
    torsion_coords = torch.tensor(
        [[[0.0, 0.0, 0.0], [1.2, 0.1, 0.0], [2.1, 1.0, 0.2], [3.0, 1.2, 1.1]]],
        dtype=torch.float64,
    )
    torsion_atom_types = torch.tensor([0, 1, 2, 3])
    torsion_metadata = {
        "torsion_atom_quartets": [[0, 1, 2, 3]],
        "torsion_target_angles_rad": [0.0],
        "topology_fidelity": "sequence_mapped",
        "ligand_topology_valid": True,
        "hbond_evidence_status": "pass",
        "claim_safe": True,
        "blocked_reason": "",
    }
    torsion_state = EngineState(
        coords=torsion_coords,
        atom_types=torsion_atom_types,
        metadata=torsion_metadata,
    )
    torsion_term = registry.create(["torsion_prior"])[0]
    torsion_result = torsion_term.energy_forces(torsion_state)
    torsion_fd_error = finite_difference_force_error(
        torsion_term,
        torsion_state,
        atom_index=3,
        coord_index=2,
    )
    topology_metadata = {
        "topology_edge_indices": [[0, 1], [1, 2]],
        "topology_edge_target_distances": [1.0, 1.0],
        "topology_fidelity": "sequence_mapped",
        "ligand_topology_valid": True,
        "ligand_topology_claim_safe": True,
        "hbond_evidence_status": "pass",
        "claim_safe": True,
        "blocked_reason": "",
    }
    topology_state = EngineState(
        coords=coords,
        atom_types=atom_types,
        metadata=topology_metadata,
    )
    topology_term = registry.create(["topology_penalty"])[0]
    topology_result = topology_term.energy_forces(topology_state)
    topology_fd_error = finite_difference_force_error(
        topology_term,
        topology_state,
        atom_index=1,
        coord_index=0,
    )
    water_displacement_coords = torch.tensor(
        [[[0.0, 0.0, 0.0], [1.5, 0.0, 0.0], [3.0, 0.5, 0.0], [5.0, 0.0, 0.0], [7.0, 0.0, 0.0]]],
        dtype=torch.float64,
    )
    water_displacement_atom_types = torch.tensor([0, 1, 2, 3, 4])
    water_displacement_metadata = {
        "ligand_atom_indices": [0, 1],
        "water_displacement_site_indices": [2, 3, 4],
        "water_displacement_site_weights": [1.0, 1.0, 1.0],
        "water_displacement_model_valid": True,
        "topology_fidelity": "sequence_mapped",
        "ligand_topology_valid": True,
        "ligand_topology_claim_safe": True,
        "hbond_evidence_status": "pass",
        "claim_safe": True,
        "blocked_reason": "",
    }
    water_displacement_state = EngineState(
        coords=water_displacement_coords,
        atom_types=water_displacement_atom_types,
        metadata=water_displacement_metadata,
    )
    water_displacement_term = registry.create(["water_displacement_proxy"])[0]
    water_displacement_result = water_displacement_term.energy_forces(water_displacement_state)
    water_displacement_fd_error = finite_difference_force_error(
        water_displacement_term,
        water_displacement_state,
        atom_index=0,
        coord_index=0,
    )
    missing = term.energy_forces(
        EngineState(
            coords=coords,
            atom_types=atom_types,
            metadata={"claim_safe": True, "blocked_reason": ""},
        )
    )
    unvalidated = term.energy_forces(
        EngineState(
            coords=coords,
            atom_types=atom_types,
            metadata={
                "partial_charges": torch.tensor([1.0, -1.0, 0.5], dtype=torch.float64),
                "claim_safe": True,
                "blocked_reason": "",
            },
        )
    )
    cap_exceeded = ScreenedElectrostaticsTerm(scale=4.0, debye_kappa=0.2, max_force_norm=1e-12).energy_forces(
        state
    )
    pocket_missing = pocket_term.energy_forces(
        EngineState(
            coords=pocket_coords,
            atom_types=atom_types,
            metadata={"claim_safe": True, "blocked_reason": ""},
        )
    )
    pocket_cap_exceeded = PocketWallTerm(k_wall=0.2, max_force_norm=1e-12).energy_forces(pocket_state)
    torsion_missing = torsion_term.energy_forces(
        EngineState(
            coords=torsion_coords,
            atom_types=torsion_atom_types,
            metadata={"claim_safe": True, "blocked_reason": ""},
        )
    )
    torsion_cap_exceeded = TorsionPriorTerm(k_torsion=0.2, max_force_norm=1e-12).energy_forces(
        torsion_state
    )
    topology_missing = topology_term.energy_forces(
        EngineState(
            coords=coords,
            atom_types=atom_types,
            metadata={
                "topology_fidelity": "sequence_mapped",
                "ligand_topology_valid": True,
                "claim_safe": True,
                "blocked_reason": "",
            },
        )
    )
    topology_invalid = topology_term.energy_forces(
        EngineState(
            coords=coords,
            atom_types=atom_types,
            metadata={
                "topology_edge_indices": [[0, 1]],
                "topology_edge_target_distances": [1.0],
                "topology_fidelity": "placeholder_alanine",
                "ligand_topology_valid": True,
                "claim_safe": True,
                "blocked_reason": "",
            },
        )
    )
    topology_cap_exceeded = TopologyPenaltyTerm(k_topology=0.25, max_force_norm=1e-12).energy_forces(
        topology_state
    )
    water_displacement_missing = water_displacement_term.energy_forces(
        EngineState(
            coords=water_displacement_coords,
            atom_types=water_displacement_atom_types,
            metadata={
                "topology_fidelity": "sequence_mapped",
                "ligand_topology_valid": True,
                "water_displacement_model_valid": True,
                "claim_safe": True,
                "blocked_reason": "",
            },
        )
    )
    water_displacement_invalid_topology = water_displacement_term.energy_forces(
        EngineState(
            coords=water_displacement_coords,
            atom_types=water_displacement_atom_types,
            metadata={
                "ligand_atom_indices": [0, 1],
                "water_displacement_site_indices": [2, 3, 4],
                "water_displacement_model_valid": True,
                "topology_fidelity": "placeholder_alanine",
                "ligand_topology_valid": True,
                "claim_safe": True,
                "blocked_reason": "",
            },
        )
    )
    water_displacement_unvalidated = water_displacement_term.energy_forces(
        EngineState(
            coords=water_displacement_coords,
            atom_types=water_displacement_atom_types,
            metadata={
                "ligand_atom_indices": [0, 1],
                "water_displacement_site_indices": [2, 3, 4],
                "topology_fidelity": "sequence_mapped",
                "ligand_topology_valid": True,
                "claim_safe": True,
                "blocked_reason": "",
            },
        )
    )
    water_displacement_weights_invalid = water_displacement_term.energy_forces(
        EngineState(
            coords=water_displacement_coords,
            atom_types=water_displacement_atom_types,
            metadata={
                "ligand_atom_indices": [0, 1],
                "water_displacement_site_indices": [2, 3, 4],
                "water_displacement_site_weights": [1.0, -1.0, float("nan")],
                "water_displacement_model_valid": True,
                "topology_fidelity": "sequence_mapped",
                "ligand_topology_valid": True,
                "claim_safe": True,
                "blocked_reason": "",
            },
        )
    )
    water_displacement_cap_exceeded = WaterDisplacementProxyTerm(
        k_water=0.05, sigma=1.0, max_force_norm=1e-12
    ).energy_forces(water_displacement_state)
    forcefield = ProductForceField.from_registry(registry, names=required_guarded_terms)
    forcefield_result = forcefield.energy_forces(
        EngineState(
            coords=torsion_coords,
            atom_types=torsion_atom_types,
            metadata={
                "partial_charges": torch.tensor([0.0, 1.0, -1.0, 0.5], dtype=torch.float64),
                "charge_source": "kpi_validated_proxy",
                "charge_model_valid": True,
                "pocket_atom_indices": [0],
                "ligand_atom_indices": [1, 2, 3],
                "pocket_radius": 1.0,
                "topology_edge_indices": [[0, 1], [1, 2], [2, 3]],
                "topology_edge_target_distances": [1.0, 1.0, 1.0],
                "ligand_topology_claim_safe": True,
                "torsion_atom_quartets": [[0, 1, 2, 3]],
                "torsion_target_angles_rad": [0.0],
                "water_displacement_site_indices": [0],
                "water_displacement_model_valid": True,
            },
        ),
        claim_metadata={
            "topology_fidelity": "sequence_mapped",
            "ligand_topology_valid": True,
            "hbond_evidence_status": "pass",
            "claim_safe": True,
            "blocked_reason": "",
        },
    )
    forcefield_claim_rows = list(forcefield_result.claim_metadata.get("force_term_claim_rows") or [])
    forcefield_guarded_row = next(
        (
            row
            for row in forcefield_claim_rows
            if isinstance(row, dict) and row.get("force_term_name") == "screened_electrostatics"
        ),
        {},
    )
    forcefield_guarded_rows = [
        row
        for row in forcefield_claim_rows
        if isinstance(row, dict) and row.get("force_term_name") in set(required_guarded_terms)
    ]
    forcefield_guarded_rows_by_name = {
        str(row.get("force_term_name")): dict(row)
        for row in forcefield_guarded_rows
        if isinstance(row, dict)
    }
    forcefield_bounded_row_ready = bool(
        forcefield_guarded_row.get("policy_caps_ready") is True
        and forcefield_guarded_row.get("observed_caps_ready") is True
        and forcefield_guarded_row.get("bounded_correction_ready") is True
        and forcefield_guarded_row.get("abs_energy_within_cap") is True
        and forcefield_guarded_row.get("force_norm_within_cap") is True
        and forcefield_guarded_row.get("active_pair_count_within_cap") is True
    )
    forcefield_guarded_rows_ready = bool(
        set(forcefield_guarded_rows_by_name) == set(required_guarded_terms)
        and all(
            row.get("claim_safe") is True
            and row.get("blocked_reason") == ""
            and row.get("policy_caps_ready") is True
            and row.get("observed_caps_ready") is True
            and row.get("bounded_correction_ready") is True
            and row.get("abs_energy_within_cap") is True
            and row.get("force_norm_within_cap") is True
            and row.get("active_pair_count_within_cap") is True
            and isinstance(row.get("policy_caps"), dict)
            and bool(row.get("policy_caps"))
            for row in forcefield_guarded_rows_by_name.values()
        )
    )
    ready = bool(
        default_names == ["directional_hbond", "hydrophobic_contact", "legacy_lj"]
        and guarded_names == [
            "directional_hbond",
            "hydrophobic_contact",
            "legacy_lj",
            "pocket_wall",
            "screened_electrostatics",
            "topology_penalty",
            "torsion_prior",
            "water_displacement_proxy",
        ]
        and set(required_guarded_terms).issubset(set(guarded_names))
        and result.claim_metadata.get("claim_safe") is True
        and result.claim_metadata.get("force_term_status") == "pass"
        and list(result.energy.shape) == [1]
        and list(result.forces.shape) == list(coords.shape)
        and bool(torch.isfinite(result.energy).all().item())
        and bool(torch.isfinite(result.forces).all().item())
        and fd_error < 1e-5
        and pocket_result.claim_metadata.get("claim_safe") is True
        and pocket_result.claim_metadata.get("force_term_status") == "pass"
        and list(pocket_result.energy.shape) == [1]
        and list(pocket_result.forces.shape) == list(pocket_coords.shape)
        and bool(torch.isfinite(pocket_result.energy).all().item())
        and bool(torch.isfinite(pocket_result.forces).all().item())
        and pocket_fd_error < 1e-5
        and torsion_result.claim_metadata.get("claim_safe") is True
        and torsion_result.claim_metadata.get("force_term_status") == "pass"
        and list(torsion_result.energy.shape) == [1]
        and list(torsion_result.forces.shape) == list(torsion_coords.shape)
        and bool(torch.isfinite(torsion_result.energy).all().item())
        and bool(torch.isfinite(torsion_result.forces).all().item())
        and torsion_fd_error < 1e-5
        and topology_result.claim_metadata.get("claim_safe") is True
        and topology_result.claim_metadata.get("force_term_status") == "pass"
        and list(topology_result.energy.shape) == [1]
        and list(topology_result.forces.shape) == list(coords.shape)
        and bool(torch.isfinite(topology_result.energy).all().item())
        and bool(torch.isfinite(topology_result.forces).all().item())
        and topology_fd_error < 1e-5
        and missing.claim_metadata.get("claim_safe") is False
        and missing.claim_metadata.get("force_term_status") == "charges_missing"
        and missing.claim_metadata.get("blocked_reason") == "screened_electrostatics_charges_missing"
        and pocket_missing.claim_metadata.get("claim_safe") is False
        and pocket_missing.claim_metadata.get("force_term_status") == "ligand_indices_missing"
        and pocket_missing.claim_metadata.get("blocked_reason") == "pocket_wall_ligand_indices_missing"
        and torsion_missing.claim_metadata.get("claim_safe") is False
        and torsion_missing.claim_metadata.get("force_term_status") == "torsion_quartets_missing"
        and torsion_missing.claim_metadata.get("blocked_reason") == "torsion_prior_quartets_missing"
        and topology_missing.claim_metadata.get("claim_safe") is False
        and topology_missing.claim_metadata.get("force_term_status") == "topology_edges_missing"
        and topology_missing.claim_metadata.get("blocked_reason") == "topology_penalty_edges_missing"
        and topology_invalid.claim_metadata.get("claim_safe") is False
        and topology_invalid.claim_metadata.get("force_term_status") == "topology_not_sequence_mapped"
        and topology_invalid.claim_metadata.get("blocked_reason")
        == "topology_penalty_topology_not_sequence_mapped"
        and unvalidated.claim_metadata.get("claim_safe") is False
        and unvalidated.claim_metadata.get("force_term_status") == "charge_model_unvalidated"
        and unvalidated.claim_metadata.get("blocked_reason")
        == "screened_electrostatics_charge_model_unvalidated"
        and result.claim_metadata.get("force_term_policy_caps_ready") is True
        and result.claim_metadata.get("force_term_observed_caps_ready") is True
        and result.claim_metadata.get("force_term_bounded_correction_ready") is True
        and result.claim_metadata.get("force_term_abs_energy_within_cap") is True
        and result.claim_metadata.get("force_term_force_norm_within_cap") is True
        and result.claim_metadata.get("force_term_active_pair_count_within_cap") is True
        and cap_exceeded.claim_metadata.get("claim_safe") is False
        and cap_exceeded.claim_metadata.get("force_term_status") == "policy_cap_exceeded"
        and cap_exceeded.claim_metadata.get("blocked_reason")
        == "screened_electrostatics_policy_cap_exceeded"
        and cap_exceeded.claim_metadata.get("force_term_observed_caps_ready") is False
        and cap_exceeded.claim_metadata.get("force_term_bounded_correction_ready") is False
        and pocket_cap_exceeded.claim_metadata.get("claim_safe") is False
        and pocket_cap_exceeded.claim_metadata.get("force_term_status") == "policy_cap_exceeded"
        and pocket_cap_exceeded.claim_metadata.get("blocked_reason") == "pocket_wall_policy_cap_exceeded"
        and pocket_cap_exceeded.claim_metadata.get("force_term_observed_caps_ready") is False
        and pocket_cap_exceeded.claim_metadata.get("force_term_bounded_correction_ready") is False
        and torsion_cap_exceeded.claim_metadata.get("claim_safe") is False
        and torsion_cap_exceeded.claim_metadata.get("force_term_status") == "policy_cap_exceeded"
        and torsion_cap_exceeded.claim_metadata.get("blocked_reason") == "torsion_prior_policy_cap_exceeded"
        and torsion_cap_exceeded.claim_metadata.get("force_term_observed_caps_ready") is False
        and torsion_cap_exceeded.claim_metadata.get("force_term_bounded_correction_ready") is False
        and topology_cap_exceeded.claim_metadata.get("claim_safe") is False
        and topology_cap_exceeded.claim_metadata.get("force_term_status") == "policy_cap_exceeded"
        and topology_cap_exceeded.claim_metadata.get("blocked_reason") == "topology_penalty_policy_cap_exceeded"
        and topology_cap_exceeded.claim_metadata.get("force_term_observed_caps_ready") is False
        and topology_cap_exceeded.claim_metadata.get("force_term_bounded_correction_ready") is False
        and water_displacement_result.claim_metadata.get("claim_safe") is True
        and water_displacement_result.claim_metadata.get("force_term_status") == "pass"
        and list(water_displacement_result.energy.shape) == [1]
        and list(water_displacement_result.forces.shape) == list(water_displacement_coords.shape)
        and bool(torch.isfinite(water_displacement_result.energy).all().item())
        and bool(torch.isfinite(water_displacement_result.forces).all().item())
        and water_displacement_fd_error < 1e-5
        and water_displacement_missing.claim_metadata.get("claim_safe") is False
        and water_displacement_missing.claim_metadata.get("force_term_status") == "ligand_indices_missing"
        and water_displacement_missing.claim_metadata.get("blocked_reason") == "water_displacement_proxy_ligand_indices_missing"
        and water_displacement_invalid_topology.claim_metadata.get("claim_safe") is False
        and water_displacement_invalid_topology.claim_metadata.get("force_term_status") == "topology_not_sequence_mapped"
        and water_displacement_invalid_topology.claim_metadata.get("blocked_reason")
        == "water_displacement_proxy_topology_not_sequence_mapped"
        and water_displacement_unvalidated.claim_metadata.get("claim_safe") is False
        and water_displacement_unvalidated.claim_metadata.get("force_term_status") == "water_displacement_model_unvalidated"
        and water_displacement_unvalidated.claim_metadata.get("blocked_reason")
        == "water_displacement_proxy_model_unvalidated"
        and water_displacement_weights_invalid.claim_metadata.get("claim_safe") is False
        and water_displacement_weights_invalid.claim_metadata.get("force_term_status") == "water_site_weights_invalid"
        and water_displacement_weights_invalid.claim_metadata.get("blocked_reason")
        == "water_displacement_proxy_weights_invalid"
        and water_displacement_cap_exceeded.claim_metadata.get("claim_safe") is False
        and water_displacement_cap_exceeded.claim_metadata.get("force_term_status") == "policy_cap_exceeded"
        and water_displacement_cap_exceeded.claim_metadata.get("blocked_reason")
        == "water_displacement_proxy_policy_cap_exceeded"
        and water_displacement_cap_exceeded.claim_metadata.get("force_term_observed_caps_ready") is False
        and water_displacement_cap_exceeded.claim_metadata.get("force_term_bounded_correction_ready") is False
        and forcefield_result.claim_metadata.get("claim_safe") is True
        and forcefield_result.claim_metadata.get("force_term_plugins") == required_guarded_terms
        and forcefield_bounded_row_ready
        and forcefield_guarded_rows_ready
    )
    return {
        "ready": ready,
        "default_registry_names": default_names,
        "guarded_registry_names": guarded_names,
        "required_guarded_terms": required_guarded_terms,
        "required_guarded_terms_present": bool(set(required_guarded_terms).issubset(set(guarded_names))),
        "term": "screened_electrostatics",
        "energy_shape": list(result.energy.shape),
        "forces_shape": list(result.forces.shape),
        "energy_finite": bool(torch.isfinite(result.energy).all().item()),
        "forces_finite": bool(torch.isfinite(result.forces).all().item()),
        "active_pair_count": int(result.diagnostics.get("active_pair_count") or 0),
        "finite_difference_force_error": float(fd_error),
        "claim_safe": result.claim_metadata.get("claim_safe") is True,
        "force_term_status": str(result.claim_metadata.get("force_term_status") or ""),
        "policy_caps_ready": result.claim_metadata.get("force_term_policy_caps_ready") is True,
        "observed_caps_ready": result.claim_metadata.get("force_term_observed_caps_ready") is True,
        "bounded_correction_ready": result.claim_metadata.get(
            "force_term_bounded_correction_ready"
        )
        is True,
        "abs_energy_within_cap": result.claim_metadata.get("force_term_abs_energy_within_cap") is True,
        "force_norm_within_cap": result.claim_metadata.get("force_term_force_norm_within_cap") is True,
        "active_pair_count_within_cap": result.claim_metadata.get(
            "force_term_active_pair_count_within_cap"
        )
        is True,
        "guarded_term_rows": [
            {
                "force_term_name": "screened_electrostatics",
                "claim_safe": result.claim_metadata.get("claim_safe") is True,
                "force_term_status": str(result.claim_metadata.get("force_term_status") or ""),
                "finite_difference_force_error": float(fd_error),
                "policy_caps_ready": result.claim_metadata.get("force_term_policy_caps_ready") is True,
                "observed_caps_ready": result.claim_metadata.get("force_term_observed_caps_ready") is True,
                "bounded_correction_ready": result.claim_metadata.get(
                    "force_term_bounded_correction_ready"
                )
                is True,
                "abs_energy_within_cap": result.claim_metadata.get(
                    "force_term_abs_energy_within_cap"
                )
                is True,
                "force_norm_within_cap": result.claim_metadata.get(
                    "force_term_force_norm_within_cap"
                )
                is True,
                "active_pair_count_within_cap": result.claim_metadata.get(
                    "force_term_active_pair_count_within_cap"
                )
                is True,
            },
            {
                "force_term_name": "pocket_wall",
                "claim_safe": pocket_result.claim_metadata.get("claim_safe") is True,
                "force_term_status": str(pocket_result.claim_metadata.get("force_term_status") or ""),
                "finite_difference_force_error": float(pocket_fd_error),
                "policy_caps_ready": pocket_result.claim_metadata.get("force_term_policy_caps_ready") is True,
                "observed_caps_ready": pocket_result.claim_metadata.get("force_term_observed_caps_ready") is True,
                "bounded_correction_ready": pocket_result.claim_metadata.get(
                    "force_term_bounded_correction_ready"
                )
                is True,
                "abs_energy_within_cap": pocket_result.claim_metadata.get(
                    "force_term_abs_energy_within_cap"
                )
                is True,
                "force_norm_within_cap": pocket_result.claim_metadata.get(
                    "force_term_force_norm_within_cap"
                )
                is True,
                "active_pair_count_within_cap": pocket_result.claim_metadata.get(
                    "force_term_active_pair_count_within_cap"
                )
                is True,
                "pocket_center_source": str(
                    pocket_result.claim_metadata.get("force_term_pocket_center_source") or ""
                ),
                "pocket_escape": pocket_result.claim_metadata.get("force_term_pocket_escape") is True,
            },
            {
                "force_term_name": "torsion_prior",
                "claim_safe": torsion_result.claim_metadata.get("claim_safe") is True,
                "force_term_status": str(torsion_result.claim_metadata.get("force_term_status") or ""),
                "finite_difference_force_error": float(torsion_fd_error),
                "policy_caps_ready": torsion_result.claim_metadata.get("force_term_policy_caps_ready") is True,
                "observed_caps_ready": torsion_result.claim_metadata.get("force_term_observed_caps_ready") is True,
                "bounded_correction_ready": torsion_result.claim_metadata.get(
                    "force_term_bounded_correction_ready"
                )
                is True,
                "abs_energy_within_cap": torsion_result.claim_metadata.get(
                    "force_term_abs_energy_within_cap"
                )
                is True,
                "force_norm_within_cap": torsion_result.claim_metadata.get(
                    "force_term_force_norm_within_cap"
                )
                is True,
                "active_pair_count_within_cap": torsion_result.claim_metadata.get(
                    "force_term_active_pair_count_within_cap"
                )
                is True,
                "torsion_quartet_count": int(
                    torsion_result.claim_metadata.get("force_term_torsion_quartet_count") or 0
                ),
            },
            {
                "force_term_name": "topology_penalty",
                "claim_safe": topology_result.claim_metadata.get("claim_safe") is True,
                "force_term_status": str(topology_result.claim_metadata.get("force_term_status") or ""),
                "finite_difference_force_error": float(topology_fd_error),
                "policy_caps_ready": topology_result.claim_metadata.get("force_term_policy_caps_ready") is True,
                "observed_caps_ready": topology_result.claim_metadata.get("force_term_observed_caps_ready") is True,
                "bounded_correction_ready": topology_result.claim_metadata.get(
                    "force_term_bounded_correction_ready"
                )
                is True,
                "abs_energy_within_cap": topology_result.claim_metadata.get(
                    "force_term_abs_energy_within_cap"
                )
                is True,
                "force_norm_within_cap": topology_result.claim_metadata.get(
                    "force_term_force_norm_within_cap"
                )
                is True,
                "active_pair_count_within_cap": topology_result.claim_metadata.get(
                    "force_term_active_pair_count_within_cap"
                )
                is True,
                "topology_edge_count": int(
                    topology_result.claim_metadata.get("force_term_topology_edge_count") or 0
                ),
            },
            {
                "force_term_name": "water_displacement_proxy",
                "claim_safe": water_displacement_result.claim_metadata.get("claim_safe") is True,
                "force_term_status": str(water_displacement_result.claim_metadata.get("force_term_status") or ""),
                "finite_difference_force_error": float(water_displacement_fd_error),
                "policy_caps_ready": water_displacement_result.claim_metadata.get("force_term_policy_caps_ready") is True,
                "observed_caps_ready": water_displacement_result.claim_metadata.get("force_term_observed_caps_ready") is True,
                "bounded_correction_ready": water_displacement_result.claim_metadata.get(
                    "force_term_bounded_correction_ready"
                )
                is True,
                "abs_energy_within_cap": water_displacement_result.claim_metadata.get(
                    "force_term_abs_energy_within_cap"
                )
                is True,
                "force_norm_within_cap": water_displacement_result.claim_metadata.get(
                    "force_term_force_norm_within_cap"
                )
                is True,
                "active_pair_count_within_cap": water_displacement_result.claim_metadata.get(
                    "force_term_active_pair_count_within_cap"
                )
                is True,
                "ligand_atom_count": int(
                    water_displacement_result.claim_metadata.get("force_term_ligand_atom_count") or 0
                ),
                "water_site_count": int(
                    water_displacement_result.claim_metadata.get("force_term_water_site_count") or 0
                ),
            },
        ],
        "pocket_wall_claim_safe": pocket_result.claim_metadata.get("claim_safe") is True,
        "pocket_wall_force_term_status": str(pocket_result.claim_metadata.get("force_term_status") or ""),
        "pocket_wall_finite_difference_force_error": float(pocket_fd_error),
        "pocket_wall_missing_metadata_blocked": bool(
            pocket_missing.claim_metadata.get("claim_safe") is False
            and pocket_missing.claim_metadata.get("force_term_status") == "ligand_indices_missing"
        ),
        "pocket_wall_policy_cap_exceeded_blocked": bool(
            pocket_cap_exceeded.claim_metadata.get("claim_safe") is False
            and pocket_cap_exceeded.claim_metadata.get("force_term_status") == "policy_cap_exceeded"
            and pocket_cap_exceeded.claim_metadata.get("blocked_reason") == "pocket_wall_policy_cap_exceeded"
            and pocket_cap_exceeded.claim_metadata.get("force_term_observed_caps_ready") is False
        ),
        "torsion_prior_claim_safe": torsion_result.claim_metadata.get("claim_safe") is True,
        "torsion_prior_force_term_status": str(torsion_result.claim_metadata.get("force_term_status") or ""),
        "torsion_prior_finite_difference_force_error": float(torsion_fd_error),
        "torsion_prior_missing_metadata_blocked": bool(
            torsion_missing.claim_metadata.get("claim_safe") is False
            and torsion_missing.claim_metadata.get("force_term_status") == "torsion_quartets_missing"
        ),
        "torsion_prior_policy_cap_exceeded_blocked": bool(
            torsion_cap_exceeded.claim_metadata.get("claim_safe") is False
            and torsion_cap_exceeded.claim_metadata.get("force_term_status") == "policy_cap_exceeded"
            and torsion_cap_exceeded.claim_metadata.get("blocked_reason") == "torsion_prior_policy_cap_exceeded"
            and torsion_cap_exceeded.claim_metadata.get("force_term_observed_caps_ready") is False
        ),
        "topology_penalty_claim_safe": topology_result.claim_metadata.get("claim_safe") is True,
        "topology_penalty_force_term_status": str(topology_result.claim_metadata.get("force_term_status") or ""),
        "topology_penalty_finite_difference_force_error": float(topology_fd_error),
        "topology_penalty_missing_metadata_blocked": bool(
            topology_missing.claim_metadata.get("claim_safe") is False
            and topology_missing.claim_metadata.get("force_term_status") == "topology_edges_missing"
        ),
        "topology_penalty_invalid_topology_blocked": bool(
            topology_invalid.claim_metadata.get("claim_safe") is False
            and topology_invalid.claim_metadata.get("force_term_status") == "topology_not_sequence_mapped"
        ),
        "topology_penalty_policy_cap_exceeded_blocked": bool(
            topology_cap_exceeded.claim_metadata.get("claim_safe") is False
            and topology_cap_exceeded.claim_metadata.get("force_term_status") == "policy_cap_exceeded"
            and topology_cap_exceeded.claim_metadata.get("blocked_reason") == "topology_penalty_policy_cap_exceeded"
            and topology_cap_exceeded.claim_metadata.get("force_term_observed_caps_ready") is False
        ),
        "water_displacement_proxy_claim_safe": water_displacement_result.claim_metadata.get("claim_safe") is True,
        "water_displacement_proxy_force_term_status": str(water_displacement_result.claim_metadata.get("force_term_status") or ""),
        "water_displacement_proxy_finite_difference_force_error": float(water_displacement_fd_error),
        "water_displacement_proxy_missing_metadata_blocked": bool(
            water_displacement_missing.claim_metadata.get("claim_safe") is False
            and water_displacement_missing.claim_metadata.get("force_term_status") == "ligand_indices_missing"
        ),
        "water_displacement_proxy_invalid_topology_blocked": bool(
            water_displacement_invalid_topology.claim_metadata.get("claim_safe") is False
            and water_displacement_invalid_topology.claim_metadata.get("force_term_status") == "topology_not_sequence_mapped"
        ),
        "water_displacement_proxy_model_unvalidated_blocked": bool(
            water_displacement_unvalidated.claim_metadata.get("claim_safe") is False
            and water_displacement_unvalidated.claim_metadata.get("force_term_status") == "water_displacement_model_unvalidated"
        ),
        "water_displacement_proxy_weights_invalid_blocked": bool(
            water_displacement_weights_invalid.claim_metadata.get("claim_safe") is False
            and water_displacement_weights_invalid.claim_metadata.get("force_term_status") == "water_site_weights_invalid"
        ),
        "water_displacement_proxy_policy_cap_exceeded_blocked": bool(
            water_displacement_cap_exceeded.claim_metadata.get("claim_safe") is False
            and water_displacement_cap_exceeded.claim_metadata.get("force_term_status") == "policy_cap_exceeded"
            and water_displacement_cap_exceeded.claim_metadata.get("blocked_reason") == "water_displacement_proxy_policy_cap_exceeded"
            and water_displacement_cap_exceeded.claim_metadata.get("force_term_observed_caps_ready") is False
        ),
        "policy_cap_exceeded_blocked": bool(
            cap_exceeded.claim_metadata.get("claim_safe") is False
            and cap_exceeded.claim_metadata.get("force_term_status") == "policy_cap_exceeded"
            and cap_exceeded.claim_metadata.get("blocked_reason")
            == "screened_electrostatics_policy_cap_exceeded"
            and cap_exceeded.claim_metadata.get("force_term_observed_caps_ready") is False
        ),
        "forcefield_bounded_row_ready": forcefield_bounded_row_ready,
        "forcefield_guarded_rows_ready": forcefield_guarded_rows_ready,
        "forcefield_guarded_claim_row": dict(forcefield_guarded_row),
        "forcefield_guarded_claim_rows": [
            forcefield_guarded_rows_by_name[name] for name in required_guarded_terms
            if name in forcefield_guarded_rows_by_name
        ],
        "policy_caps": dict(result.claim_metadata.get("force_term_policy_caps") or {}),
        "observed_abs_energy": float(result.claim_metadata.get("force_term_abs_energy") or 0.0),
        "observed_force_norm": float(result.claim_metadata.get("force_term_observed_force_norm") or 0.0),
        "missing_charge_blocked": bool(
            missing.claim_metadata.get("claim_safe") is False
            and missing.claim_metadata.get("force_term_status") == "charges_missing"
        ),
        "unvalidated_charge_blocked": bool(
            unvalidated.claim_metadata.get("claim_safe") is False
            and unvalidated.claim_metadata.get("force_term_status") == "charge_model_unvalidated"
        ),
        "forcefield_claim_safe": forcefield_result.claim_metadata.get("claim_safe") is True,
    }


def _signed_runner_claim_metadata_kpi() -> dict[str, Any]:
    runner_claim_metadata = {
        "topology_fidelity": "placeholder_alanine",
        "ligand_topology_valid": True,
        "ligand_topology_claim_safe": True,
        "ligand_topology_schema_version": "ligand_topology_validity_v1",
        "ligand_topology_schema_ready_row_count": 2,
        "ligand_topology_valid_row_count": 2,
        "ligand_topology_claim_safe_row_count": 2,
        "ligand_topology_invalid_row_count": 0,
        "ligand_topology_blocker_counts": {},
        "hbond_evidence_status": "review",
        "hbond_evidence_schema_version": "hbond_evidence_v1",
        "hbond_evidence_schema_ready_row_count": 2,
        "hbond_geometry_evaluated_row_count": 2,
        "hbond_geometry_complete_row_count": 0,
        "force_residual_applied": False,
        "claim_safe": False,
        "blocked_reason": "runner_summary_not_claim_promoted;protein_topology_missing",
    }
    hbond_summary = {
        "schema_version": "hbond_evidence_v1",
        "status": "review",
        "evaluated_row_count": 2,
        "schema_ready_row_count": 2,
        "claim_safe_row_count": 0,
        "onsps_backmap_schema_version": "onsps_backmap_evidence_v1",
    }
    force_residual_summary = {
        "schema_version": "force_residual_claim_metadata_v1",
        "applied": False,
        "reason": "disabled",
        "policy_caps_ready": True,
        "observed_caps_ready": True,
        "contract_ready": True,
    }
    manifest = build_result_manifest(
        job_id="kpi_runner_claim_metadata_smoke",
        request={"target_name": "kpi", "runner_profile_id": "backmapping_scoring.production"},
        status="completed",
        result_file="",
        signing_key="kpi-test-key",
        key_id="kpi-test",
        result_claim_metadata=runner_claim_metadata,
        hbond_evidence_summary=hbond_summary,
        force_residual_summary=force_residual_summary,
    )
    signed = verify_result_manifest(manifest, signing_key="kpi-test-key")
    ready = bool(
        signed
        and manifest.get("result_claim_metadata") == runner_claim_metadata
        and manifest.get("hbond_evidence_summary") == hbond_summary
        and manifest.get("force_residual_summary") == force_residual_summary
        and manifest["result_claim_metadata"].get("claim_safe") is False
        and str(manifest["result_claim_metadata"].get("blocked_reason") or "")
        and manifest["result_claim_metadata"].get("hbond_evidence_schema_version") == "hbond_evidence_v1"
        and int(manifest["result_claim_metadata"].get("hbond_evidence_schema_ready_row_count") or 0) == 2
        and manifest["result_claim_metadata"].get("ligand_topology_claim_safe") is True
        and manifest["result_claim_metadata"].get("ligand_topology_schema_version")
        == "ligand_topology_validity_v1"
        and int(manifest["result_claim_metadata"].get("ligand_topology_schema_ready_row_count") or 0) == 2
        and int(manifest["result_claim_metadata"].get("ligand_topology_claim_safe_row_count") or 0) == 2
        and manifest["hbond_evidence_summary"].get("schema_version") == "hbond_evidence_v1"
        and manifest["force_residual_summary"].get("contract_ready") is True
    )
    return {
        "ready": ready,
        "signature_verified": signed,
        "result_claim_metadata_present": isinstance(manifest.get("result_claim_metadata"), dict),
        "hbond_evidence_summary_present": isinstance(manifest.get("hbond_evidence_summary"), dict),
        "force_residual_summary_present": isinstance(manifest.get("force_residual_summary"), dict),
        "manifest_claim_safe": manifest.get("result_claim_metadata", {}).get("claim_safe"),
        "manifest_blocked_reason": str(
            manifest.get("result_claim_metadata", {}).get("blocked_reason") or ""
        ),
        "manifest_ligand_topology_valid": manifest.get("result_claim_metadata", {}).get("ligand_topology_valid"),
        "manifest_ligand_topology_claim_safe": manifest.get("result_claim_metadata", {}).get(
            "ligand_topology_claim_safe"
        ),
        "manifest_ligand_topology_schema_version": manifest.get("result_claim_metadata", {}).get(
            "ligand_topology_schema_version"
        ),
        "manifest_ligand_topology_schema_ready_row_count": int(
            manifest.get("result_claim_metadata", {}).get("ligand_topology_schema_ready_row_count") or 0
        ),
        "manifest_ligand_topology_claim_safe_row_count": int(
            manifest.get("result_claim_metadata", {}).get("ligand_topology_claim_safe_row_count") or 0
        ),
        "manifest_hbond_evidence_status": manifest.get("hbond_evidence_summary", {}).get("status"),
        "manifest_hbond_evidence_schema_version": manifest.get("result_claim_metadata", {}).get(
            "hbond_evidence_schema_version"
        ),
        "manifest_hbond_evidence_schema_ready_row_count": int(
            manifest.get("result_claim_metadata", {}).get("hbond_evidence_schema_ready_row_count") or 0
        ),
        "manifest_force_residual_schema_version": manifest.get("force_residual_summary", {}).get(
            "schema_version"
        ),
        "manifest_force_residual_policy_caps_ready": manifest.get("force_residual_summary", {}).get(
            "policy_caps_ready"
        ),
        "manifest_force_residual_observed_caps_ready": manifest.get("force_residual_summary", {}).get(
            "observed_caps_ready"
        ),
        "manifest_force_residual_contract_ready": manifest.get("force_residual_summary", {}).get(
            "contract_ready"
        ),
    }


def _engine_topology_factory_facade_kpi() -> dict[str, Any]:
    factory = TopologyFactoryFacade(device="cpu", default_claim_scope="kpi_smoke")
    valid = factory.from_sequence_and_smiles(
        sequence="ACD",
        smiles="C[C@H](O)C(=O)O",
        pocket_residue_indices=[1],
    )
    placeholder = factory.from_sequence_and_smiles(
        sequence="",
        smiles="C[C@H](O)C(=O)O",
        n_res=3,
    )
    empty_protein = factory.from_sequence_and_smiles(
        sequence="",
        smiles="C[C@H](O)C(=O)O",
        n_res=0,
    )
    invalid_ligand = factory.from_sequence_and_smiles(
        sequence="ACD",
        smiles="C1(",
    )
    invalid_pocket = factory.from_sequence_and_smiles(
        sequence="ACD",
        smiles="C[C@H](O)C(=O)O",
        pocket_residue_indices=[0, 3],
    )
    ready = bool(
        valid.complex_topology.protein.fidelity == "sequence_mapped"
        and valid.complex_topology.claim_scope == "kpi_smoke"
        and valid.complex_topology.pocket_residue_indices == [1]
        and valid.claim_metadata.get("claim_safe") is True
        and valid.claim_metadata.get("pocket_residue_indices_valid") is True
        and int(valid.claim_metadata.get("pocket_residue_count") or 0) == 1
        and int(valid.claim_metadata.get("protein_residue_count") or 0) == 3
        and valid.claim_metadata.get("protein_topology_valid") is True
        and valid.claim_metadata.get("ligand_topology_schema_version") == "ligand_topology_validity_v1"
        and placeholder.claim_metadata.get("claim_safe") is False
        and placeholder.claim_metadata.get("blocked_reason") == "placeholder_alanine_topology"
        and int(placeholder.claim_metadata.get("protein_residue_count") or 0) == 3
        and placeholder.claim_metadata.get("protein_topology_valid") is True
        and empty_protein.claim_metadata.get("claim_safe") is False
        and empty_protein.claim_metadata.get("blocked_reason") == "empty_protein_topology"
        and int(empty_protein.claim_metadata.get("protein_residue_count", -1)) == 0
        and empty_protein.claim_metadata.get("protein_topology_valid") is False
        and invalid_ligand.claim_metadata.get("claim_safe") is False
        and invalid_ligand.claim_metadata.get("blocked_reason") == "invalid_smiles"
        and invalid_pocket.claim_metadata.get("claim_safe") is False
        and invalid_pocket.claim_metadata.get("blocked_reason") == "invalid_pocket_residue_indices"
        and invalid_pocket.claim_metadata.get("pocket_residue_indices_valid") is False
    )
    return {
        "ready": ready,
        "facade": "betelgeuze_engine.topology.TopologyFactoryFacade",
        "valid_claim_safe": valid.claim_metadata.get("claim_safe") is True,
        "valid_topology_fidelity": str(valid.claim_metadata.get("topology_fidelity") or ""),
        "valid_protein_residue_count": int(valid.claim_metadata.get("protein_residue_count") or 0),
        "valid_protein_topology_valid": valid.claim_metadata.get("protein_topology_valid") is True,
        "valid_pocket_residue_count": int(valid.claim_metadata.get("pocket_residue_count") or 0),
        "valid_pocket_residue_indices_valid": valid.claim_metadata.get("pocket_residue_indices_valid") is True,
        "valid_ligand_topology_schema_version": str(
            valid.claim_metadata.get("ligand_topology_schema_version") or ""
        ),
        "placeholder_protein_residue_count": int(
            placeholder.claim_metadata.get("protein_residue_count") or 0
        ),
        "placeholder_protein_topology_valid": placeholder.claim_metadata.get("protein_topology_valid") is True,
        "placeholder_blocked_reason": str(placeholder.claim_metadata.get("blocked_reason") or ""),
        "empty_protein_residue_count": int(empty_protein.claim_metadata.get("protein_residue_count") or 0),
        "empty_protein_topology_valid": empty_protein.claim_metadata.get("protein_topology_valid") is True,
        "empty_protein_blocked_reason": str(empty_protein.claim_metadata.get("blocked_reason") or ""),
        "invalid_ligand_blocked_reason": str(invalid_ligand.claim_metadata.get("blocked_reason") or ""),
        "invalid_pocket_blocked_reason": str(invalid_pocket.claim_metadata.get("blocked_reason") or ""),
        "invalid_pocket_residue_indices_valid": invalid_pocket.claim_metadata.get(
            "pocket_residue_indices_valid"
        ) is True,
    }


def _onsps_backmap_evidence_schema_kpi() -> dict[str, Any]:
    two_bead = np.asarray([[0.0, 0.0, 0.0], [1.6, 0.0, 0.0]], dtype=np.float32)
    valid = evaluate_onsps_backmap_evidence(two_bead, "CC(=O)N")
    empty = evaluate_onsps_backmap_evidence(np.zeros((1, 3), dtype=np.float32), "CC(=O)N")
    no_sites = evaluate_onsps_backmap_evidence(two_bead, "CCCC")
    hbond = evaluate_hbond_evidence(smiles="CC(=O)N", ligand_xyz=two_bead)
    hbond_onsps = hbond.onsps_backmap_metadata
    product_runner_path = Path("betelgeuze_engine/product/runners/backmapping_scoring.py")
    product_runner_text = product_runner_path.read_text(encoding="utf-8") if product_runner_path.exists() else ""
    product_runner_direct_engine_import_ready = bool(
        "from betelgeuze_engine.backmapping.onsps import" in product_runner_text
        and "from core.onsps_backmap import" not in product_runner_text
        and "import core.onsps_backmap" not in product_runner_text
    )
    ready = bool(
        valid.schema_version == ONSPS_BACKMAP_SCHEMA_VERSION
        and valid.claim_safe is True
        and valid.backmap_status == "ok"
        and valid.mapped_site_count > 0
        and isinstance(valid.role_counts, dict)
        and empty.schema_version == ONSPS_BACKMAP_SCHEMA_VERSION
        and empty.claim_safe is False
        and empty.backmap_status == "empty_input"
        and empty.blocked_reason == "invalid_two_bead_geometry"
        and no_sites.schema_version == ONSPS_BACKMAP_SCHEMA_VERSION
        and no_sites.claim_safe is False
        and no_sites.blocked_reason == "no_onsps_sites"
        and hbond_onsps.get("schema_version") == ONSPS_BACKMAP_SCHEMA_VERSION
        and isinstance(hbond_onsps.get("role_counts"), dict)
        and product_runner_direct_engine_import_ready
    )
    return {
        "ready": ready,
        "schema_version": ONSPS_BACKMAP_SCHEMA_VERSION,
        "valid_claim_safe": valid.claim_safe is True,
        "valid_backmap_status": valid.backmap_status,
        "valid_mapping_source": valid.mapping_source,
        "valid_mapped_site_count": int(valid.mapped_site_count),
        "valid_role_counts": dict(valid.role_counts),
        "empty_blocked_reason": empty.blocked_reason,
        "no_sites_blocked_reason": no_sites.blocked_reason,
        "hbond_onsps_schema_version": str(hbond_onsps.get("schema_version") or ""),
        "hbond_onsps_claim_safe": hbond_onsps.get("claim_safe") is True,
        "product_runner_direct_engine_import_ready": product_runner_direct_engine_import_ready,
        "product_runner_import_source": "betelgeuze_engine.backmapping.onsps"
        if product_runner_direct_engine_import_ready
        else "legacy_or_missing",
        "product_runner_legacy_core_import_absent": "core.onsps_backmap" not in product_runner_text,
    }


def _core_forcefield_bridge_kpi() -> dict[str, Any]:
    try:
        from core.forcefield import ForceField, default_product_forcefield
    except Exception as exc:
        return {"ready": False, "error": f"import_error:{type(exc).__name__}:{exc}"}

    try:
        device = torch.device("cpu")

        class _BridgeTopology:
            n_res = 2
            box_size = torch.tensor([20.0, 20.0, 20.0], dtype=torch.float32, device=device)
            residue_types = torch.tensor([3, 8], dtype=torch.long, device=device)
            claim_metadata = {
                "topology_fidelity": "sequence_mapped",
                "ligand_topology_valid": True,
                "hbond_evidence_status": "pass",
                "force_residual_applied": False,
                "claim_safe": True,
                "blocked_reason": "",
            }

            def residue_types_for_coordinate_count(self, n_atoms: int) -> torch.Tensor | None:
                return self.residue_types if int(n_atoms) == 2 else None

            def hbond_roles(self) -> list[str]:
                return ["donor", "acceptor"]

        with contextlib.redirect_stdout(io.StringIO()):
            legacy_forcefield = ForceField.__new__(ForceField)
        legacy_forcefield.top = _BridgeTopology()
        coords = torch.tensor(
            [[[0.0, 0.0, 0.0], [4.0, 0.0, 0.0]]],
            dtype=torch.float32,
            device=device,
        )
        result = legacy_forcefield.product_energy_forces(
            coords,
            term_names=["legacy_lj"],
            metadata={
                "hbond_roles": ["donor", "acceptor"],
                "hydrophobic_mask": torch.tensor([True, True], device=device),
            },
            claim_metadata={
                "topology_fidelity": "sequence_mapped",
                "ligand_topology_valid": True,
                "hbond_evidence_status": "pass",
                "claim_safe": True,
                "blocked_reason": "",
            },
        )
        unsafe_claim_metadata = {
            "topology_fidelity": "placeholder_alanine",
            "ligand_topology_valid": False,
            "hbond_evidence_status": "not_assessed",
            "claim_safe": False,
            "blocked_reason": "placeholder_alanine_topology",
        }
        unsafe_result = legacy_forcefield.product_energy_forces(
            coords,
            term_names=["legacy_lj"],
            metadata={
                "hbond_roles": ["donor", "acceptor"],
                "hydrophobic_mask": torch.tensor([True, True], device=device),
                **unsafe_claim_metadata,
            },
            claim_metadata=unsafe_claim_metadata,
        )
        unsafe_claim_rows = list(unsafe_result.claim_metadata.get("force_term_claim_rows") or [])
        unsafe_base_claim_blocked = bool(
            unsafe_result.claim_metadata.get("claim_safe") is False
            and unsafe_result.claim_metadata.get("blocked_reason") == "placeholder_alanine_topology"
            and int(unsafe_result.claim_metadata.get("force_term_claim_safe_count") or 0) == 0
            and int(unsafe_result.claim_metadata.get("force_term_blocked_count") or 0) == 1
            and len(unsafe_claim_rows) == 1
            and all(
                isinstance(row, dict)
                and row.get("claim_safe") is False
                and row.get("blocked_reason") == "placeholder_alanine_topology"
                for row in unsafe_claim_rows
            )
        )
        registry_names = default_product_forcefield(term_names=["legacy_lj"]).terms[0].name
        neighbor_pair_count = int(result.diagnostics.get("neighbor_pair_count") or 0)
        neighbor_diagnostics_ready = bool(
            neighbor_pair_count > 0
            and result.diagnostics.get("neighbor_pairs_provided") is False
            and result.diagnostics.get("neighbor_source") == "full_neighbor_pairs"
        )
        ready = bool(
            result.claim_metadata.get("claim_safe") is True
            and result.claim_metadata.get("force_term_claim_metadata_ready") is True
            and result.claim_metadata.get("force_term_plugins") == ["legacy_lj"]
            and neighbor_diagnostics_ready
            and unsafe_base_claim_blocked
            and registry_names == "legacy_lj"
        )
        return {
            "ready": ready,
            "result_claim_safe": result.claim_metadata.get("claim_safe") is True,
            "force_term_claim_metadata_ready": result.claim_metadata.get("force_term_claim_metadata_ready") is True,
            "force_term_plugins": list(result.claim_metadata.get("force_term_plugins") or []),
            "unsafe_base_claim_blocked": unsafe_base_claim_blocked,
            "unsafe_base_claim_safe": unsafe_result.claim_metadata.get("claim_safe") is True,
            "unsafe_base_blocked_reason": str(unsafe_result.claim_metadata.get("blocked_reason") or ""),
            "unsafe_base_claim_safe_count": int(
                unsafe_result.claim_metadata.get("force_term_claim_safe_count") or 0
            ),
            "unsafe_base_blocked_count": int(
                unsafe_result.claim_metadata.get("force_term_blocked_count") or 0
            ),
            "unsafe_base_claim_rows": unsafe_claim_rows,
            "energy_shape": list(result.energy.shape),
            "forces_shape": list(result.forces.shape),
            "neighbor_diagnostics_ready": neighbor_diagnostics_ready,
            "neighbor_pair_count": neighbor_pair_count,
            "neighbor_pairs_provided": bool(result.diagnostics.get("neighbor_pairs_provided") is True),
            "neighbor_source": str(result.diagnostics.get("neighbor_source") or ""),
            "bridge_execution_scope": "metadata_contract_only_not_runtime_gpu_claim",
        }
    except Exception as exc:
        return {"ready": False, "error": f"bridge_error:{type(exc).__name__}:{exc}"}


def _core_compatibility_layer_kpi(core_forcefield_bridge: dict[str, Any] | None = None) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []

    try:
        import betelgeuze_engine.backmapping.onsps as engine_onsps
        import core.onsps_backmap as legacy_onsps

        ready = bool(
            legacy_onsps.backmap_4bead_onsps is engine_onsps.backmap_4bead_onsps
            and legacy_onsps.onsps_hbond_sites_from_smiles is engine_onsps.onsps_hbond_sites_from_smiles
        )
        rows.append(
            {
                "contract": "onsps_backmap_shim",
                "ready": ready,
                "legacy_module": "core.onsps_backmap",
                "canonical_module": "betelgeuze_engine.backmapping.onsps",
                "bridge_type": "import_identity",
                "error": "",
            }
        )
    except Exception as exc:
        rows.append(
            {
                "contract": "onsps_backmap_shim",
                "ready": False,
                "legacy_module": "core.onsps_backmap",
                "canonical_module": "betelgeuze_engine.backmapping.onsps",
                "bridge_type": "import_identity",
                "error": f"{type(exc).__name__}:{exc}",
            }
        )

    try:
        from betelgeuze_engine.topology.protein import ProteinTopology
        from core.topology import TopologyFactory

        device = torch.device("cpu")
        with contextlib.redirect_stdout(io.StringIO()):
            topology = TopologyFactory(2, "protein", [20.0, 20.0, 20.0], device, target_name="compat")
            topology.set_residue_types_from_sequence_string("DK")
        roles = topology.hbond_roles()
        ready = bool(
            isinstance(topology.protein_topology, ProteinTopology)
            and topology.topology_fidelity() == "sequence_mapped"
            and topology.protein_topology.fidelity == "sequence_mapped"
            and int(topology.residue_types.shape[0]) == 2
            and len(roles) == 2
        )
        rows.append(
            {
                "contract": "topology_protein_bridge",
                "ready": ready,
                "legacy_module": "core.topology",
                "canonical_module": "betelgeuze_engine.topology.protein",
                "bridge_type": "engine_dataclass_bridge",
                "topology_fidelity": topology.topology_fidelity(),
                "protein_topology_type": type(topology.protein_topology).__name__,
                "hbond_role_count": len(roles),
                "error": "",
            }
        )
    except Exception as exc:
        rows.append(
            {
                "contract": "topology_protein_bridge",
                "ready": False,
                "legacy_module": "core.topology",
                "canonical_module": "betelgeuze_engine.topology.protein",
                "bridge_type": "engine_dataclass_bridge",
                "topology_fidelity": "",
                "protein_topology_type": "",
                "hbond_role_count": 0,
                "error": f"{type(exc).__name__}:{exc}",
            }
        )

    try:
        from core.definitions import StrategyType
        from core.topology import TopologyFactory

        device = torch.device("cpu")
        log_capture = io.StringIO()
        with contextlib.redirect_stdout(log_capture):
            topology = TopologyFactory(
                2,
                "protein",
                [20.0, 20.0, 20.0],
                device,
                target_name="adress-compat",
                strategy_type=StrategyType.ADRESS,
            )
        log_text = log_capture.getvalue()
        neighbor_blocked = False
        neighbor_error = ""
        try:
            topology.get_adress_neighbor_data(torch.zeros(1, 2, 3, device=device))
        except RuntimeError as exc:
            neighbor_error = str(exc)
            neighbor_blocked = "disabled in production" in neighbor_error

        log_blocked = "BLOCKED (AdResS research path" in log_text
        active_claim_absent = "ACTIVE (AdResS" not in log_text
        ready = bool(log_blocked and active_claim_absent and neighbor_blocked)
        rows.append(
            {
                "contract": "adress_production_blocked_log",
                "ready": ready,
                "legacy_module": "core.topology",
                "canonical_module": "betelgeuze_engine.topology.protein",
                "bridge_type": "fail_closed_adress_guard",
                "adress_log_blocked": log_blocked,
                "adress_log_active_claim_absent": active_claim_absent,
                "adress_neighbor_blocked": neighbor_blocked,
                "adress_neighbor_error": neighbor_error,
                "error": "" if ready else "adress_production_guard_not_proven",
            }
        )
    except Exception as exc:
        rows.append(
            {
                "contract": "adress_production_blocked_log",
                "ready": False,
                "legacy_module": "core.topology",
                "canonical_module": "betelgeuze_engine.topology.protein",
                "bridge_type": "fail_closed_adress_guard",
                "adress_log_blocked": False,
                "adress_log_active_claim_absent": False,
                "adress_neighbor_blocked": False,
                "adress_neighbor_error": "",
                "error": f"{type(exc).__name__}:{exc}",
            }
        )

    forcefield_bridge = core_forcefield_bridge or _core_forcefield_bridge_kpi()
    rows.append(
        {
            "contract": "forcefield_product_bridge",
            "ready": bool(forcefield_bridge.get("ready") is True),
            "legacy_module": "core.forcefield",
            "canonical_module": "betelgeuze_engine.physics",
            "bridge_type": "energy_forces_claim_metadata_bridge",
            "result_claim_safe": forcefield_bridge.get("result_claim_safe") is True,
            "force_term_claim_metadata_ready": forcefield_bridge.get("force_term_claim_metadata_ready") is True,
            "force_term_plugins": list(forcefield_bridge.get("force_term_plugins") or []),
            "unsafe_base_claim_blocked": forcefield_bridge.get("unsafe_base_claim_blocked") is True,
            "unsafe_base_claim_safe": forcefield_bridge.get("unsafe_base_claim_safe") is True,
            "unsafe_base_blocked_reason": str(forcefield_bridge.get("unsafe_base_blocked_reason") or ""),
            "unsafe_base_claim_safe_count": int(forcefield_bridge.get("unsafe_base_claim_safe_count") or 0),
            "unsafe_base_blocked_count": int(forcefield_bridge.get("unsafe_base_blocked_count") or 0),
            "unsafe_base_claim_rows": list(forcefield_bridge.get("unsafe_base_claim_rows") or []),
            "neighbor_diagnostics_ready": forcefield_bridge.get("neighbor_diagnostics_ready") is True,
            "neighbor_pair_count": int(forcefield_bridge.get("neighbor_pair_count") or 0),
            "neighbor_pairs_provided": forcefield_bridge.get("neighbor_pairs_provided") is True,
            "neighbor_source": str(forcefield_bridge.get("neighbor_source") or ""),
            "error": str(forcefield_bridge.get("error") or ""),
        }
    )

    shim_cases = [
        (
            "score_residual_shim",
            "core.score_residual",
            "betelgeuze_engine.residual.score",
            (
                ("apply_score_residual", "apply_score_residual"),
                ("residual_band", "residual_band"),
            ),
        ),
        (
            "topology_score_correction_shim",
            "core.topo_corrector",
            "betelgeuze_engine.topology.correction",
            (
                ("summarize_topo_correction", "summarize_topo_correction"),
                ("topo_correction_delta", "topo_correction_delta"),
            ),
        ),
        (
            "mm_gbsa_refine_shim",
            "core.mm_gbsa",
            "betelgeuze_engine.physics.mm_gbsa",
            (
                ("mm_gbsa_binding_energy", "mm_gbsa_binding_energy"),
                ("compute_full_refine_stack", "compute_full_refine_stack"),
            ),
        ),
    ]
    for contract, legacy_module_name, canonical_module_name, symbol_pairs in shim_cases:
        try:
            legacy_module = importlib.import_module(legacy_module_name)
            canonical_module = importlib.import_module(canonical_module_name)
            missing_symbols: list[str] = []
            identity_mismatches: list[str] = []
            for legacy_symbol, canonical_symbol in symbol_pairs:
                if not hasattr(legacy_module, legacy_symbol) or not hasattr(canonical_module, canonical_symbol):
                    missing_symbols.append(f"{legacy_symbol}:{canonical_symbol}")
                    continue
                if getattr(legacy_module, legacy_symbol) is not getattr(canonical_module, canonical_symbol):
                    identity_mismatches.append(f"{legacy_symbol}:{canonical_symbol}")
            ready = bool(not missing_symbols and not identity_mismatches)
            rows.append(
                {
                    "contract": contract,
                    "ready": ready,
                    "legacy_module": legacy_module_name,
                    "canonical_module": canonical_module_name,
                    "bridge_type": "import_identity",
                    "checked_symbols": [legacy for legacy, _canonical in symbol_pairs],
                    "missing_symbols": missing_symbols,
                    "identity_mismatches": identity_mismatches,
                    "error": "" if ready else "migrated_core_shim_identity_not_proven",
                }
            )
        except Exception as exc:
            rows.append(
                {
                    "contract": contract,
                    "ready": False,
                    "legacy_module": legacy_module_name,
                    "canonical_module": canonical_module_name,
                    "bridge_type": "import_identity",
                    "checked_symbols": [legacy for legacy, _canonical in symbol_pairs],
                    "missing_symbols": [],
                    "identity_mismatches": [],
                    "error": f"{type(exc).__name__}:{exc}",
                }
            )

    return {
        "ready": bool(rows and all(row["ready"] is True for row in rows)),
        "contract_scope": "legacy_core_import_paths_are_compatibility_layer_not_runtime_gpu_claim",
        "row_count": len(rows),
        "rows": rows,
    }


def _allowlisted_runner_shim_contract_kpi(profiles_dir: str | Path) -> dict[str, Any]:
    cases = [
        (
            "ligand_htvs_pipeline_default",
            Path("tools/run_ligand_htvs_pipeline.py"),
            "betelgeuze_engine.product.runners.htvs_pipeline",
            ("main", "build_parser"),
        ),
        (
            "backmapping_scoring.production",
            Path("tools/run_ligand_backmapping_scoring.py"),
            "betelgeuze_engine.product.runners.backmapping_scoring",
            ("main", "_frame_mmpbsa_proxy"),
        ),
        (
            "ligand_topk_delivery.production",
            Path("tools/run_ligand_topk_delivery.py"),
            "betelgeuze_engine.product.runners.topk_delivery",
            ("main", "build_delivery"),
        ),
    ]
    root = Path(profiles_dir)
    rows: list[dict[str, Any]] = []
    for profile_id, script_path, adapter_import, required_symbols in cases:
        profile_path = root / f"{profile_id}.json"
        legacy_import = ".".join(script_path.with_suffix("").parts)
        script_hash = ""
        profile_hash = ""
        profile_script = ""
        error = ""
        adapter_present = False
        runtime_adapter_identity_ready = False
        missing_runtime_symbols: list[str] = []
        runtime_adapter_error = ""
        adapter_module: Any | None = None
        if script_path.exists():
            script_bytes = script_path.read_bytes()
            script_text = script_bytes.decode("utf-8", errors="ignore")
            script_hash = hashlib.sha256(script_bytes).hexdigest()
            adapter_present = adapter_import in script_text
        else:
            script_text = ""
            error = "runner_script_missing"
        if profile_path.exists():
            try:
                profile = json.loads(profile_path.read_text(encoding="utf-8"))
                profile_script = str(profile.get("runner_script") or "")
                readiness = profile.get("production_readiness")
                if isinstance(readiness, dict):
                    profile_hash = str(readiness.get("runner_script_sha256") or "")
                else:
                    error = error or "production_readiness_missing"
            except json.JSONDecodeError:
                error = error or "profile_json_invalid"
        else:
            error = error or "runner_profile_missing"
        if not error and adapter_present:
            try:
                legacy_module = importlib.import_module(legacy_import)
                adapter_module = importlib.import_module(adapter_import)
                missing_runtime_symbols = [
                    name
                    for name in required_symbols
                    if not hasattr(legacy_module, name) or not hasattr(adapter_module, name)
                ]
                runtime_adapter_identity_ready = bool(
                    not missing_runtime_symbols
                    and all(
                        getattr(legacy_module, name) is getattr(adapter_module, name)
                        for name in required_symbols
                    )
                )
            except Exception as exc:  # pragma: no cover - report evidence, do not hide import failures.
                runtime_adapter_error = f"{type(exc).__name__}: {exc}"
        elif not adapter_present:
            runtime_adapter_error = "adapter_import_missing_from_shim"
        legacy_alias = sys.modules.get(legacy_import)
        sys_modules_alias_ready = bool(
            runtime_adapter_identity_ready
            and adapter_module is not None
            and legacy_alias is adapter_module
        ) if adapter_present and not runtime_adapter_error else False
        has_module_alias_assignment = (
            "sys.modules[__name__]" in script_text or "_sys.modules[__name__]" in script_text
        )
        self_implementation_blocked = bool(
            has_module_alias_assignment
            and "_module = _import_module" in script_text
            and "def main(" not in script_text
            and "argparse.ArgumentParser" not in script_text
        )
        shim_contract_type = (
            "canonical_module_alias" if sys_modules_alias_ready and self_implementation_blocked else "unknown"
        )
        rows.append(
            {
                "profile_id": profile_id,
                "runner_script": str(script_path),
                "profile_runner_script": profile_script,
                "adapter_import": adapter_import,
                "adapter_import_present": adapter_present,
                "shim_contract_type": shim_contract_type,
                "sys_modules_alias_ready": sys_modules_alias_ready,
                "runtime_module_name": str(getattr(adapter_module, "__name__", "")) if adapter_module is not None else "",
                "self_implementation_blocked": self_implementation_blocked,
                "required_runtime_symbols": list(required_symbols),
                "runtime_adapter_identity_ready": runtime_adapter_identity_ready,
                "missing_runtime_symbols": missing_runtime_symbols,
                "runtime_adapter_error": runtime_adapter_error,
                "script_hash": script_hash,
                "profile_runner_script_sha256": profile_hash,
                "hash_matches": bool(script_hash and profile_hash and script_hash == profile_hash),
                "ready": bool(
                    adapter_present
                    and sys_modules_alias_ready
                    and self_implementation_blocked
                    and runtime_adapter_identity_ready
                    and profile_script == str(script_path)
                    and script_hash
                    and profile_hash
                    and script_hash == profile_hash
                    and not error
                ),
                "error": error,
            }
        )
    return {
        "ready": bool(rows and all(row["ready"] is True for row in rows)),
        "runner_count": len(rows),
        "rows": rows,
    }


def _product_runner_engine_imports_kpi() -> dict[str, Any]:
    runner_path = Path("betelgeuze_engine/product/runners/backmapping_scoring.py")
    script_text = runner_path.read_text(encoding="utf-8") if runner_path.exists() else ""
    cases = [
        {
            "contract": "hbond_evidence_direct_engine_import",
            "engine_module": "betelgeuze_engine.interactions",
            "required_snippets": [
                "from betelgeuze_engine.interactions import",
                "evaluate_hbond_evidence",
                "HBOND_EVIDENCE_SCHEMA_VERSION",
            ],
            "forbidden_snippets": [
                "from core.interaction_forces import",
                "import core.interaction_forces",
                "from theory.branches.hbond_logic import",
            ],
        },
        {
            "contract": "onsps_backmap_direct_engine_import",
            "engine_module": "betelgeuze_engine.backmapping.onsps",
            "required_snippets": [
                "from betelgeuze_engine.backmapping.onsps import",
                "backmap_4bead_onsps",
                "needs_onsps_4bead",
                "onsps_site_count",
            ],
            "forbidden_snippets": [
                "from core.onsps_backmap import",
                "import core.onsps_backmap",
            ],
        },
        {
            "contract": "ligand_topology_direct_engine_import",
            "engine_module": "betelgeuze_engine.topology",
            "required_snippets": [
                "ligand_topology_from_smiles",
            ],
            "forbidden_snippets": [
                "from core.topology import ligand_topology_from_smiles",
                "import core.ligand_topology",
            ],
        },
        {
            "contract": "topology_score_correction_direct_engine_import",
            "engine_module": "betelgeuze_engine.topology",
            "required_snippets": [
                "from betelgeuze_engine.topology import",
                "summarize_topo_correction",
            ],
            "forbidden_snippets": [
                "from core.topo_corrector import",
                "import core.topo_corrector",
            ],
            "residual_scope": "score_ranking_heuristic",
            "physical_force_residual_claim": False,
            "bounded_correction_required": True,
        },
        {
            "contract": "score_residual_direct_engine_import",
            "engine_module": "betelgeuze_engine.residual.score",
            "required_snippets": [
                "from betelgeuze_engine.residual.score import apply_score_residual",
            ],
            "forbidden_snippets": [
                "from core.score_residual import apply_score_residual",
                "import core.score_residual",
            ],
            "residual_scope": "score_ranking_heuristic",
            "physical_force_residual_claim": False,
        },
        {
            "contract": "mm_gbsa_refine_direct_engine_import",
            "engine_module": "betelgeuze_engine.physics.mm_gbsa",
            "required_snippets": [
                "from betelgeuze_engine.physics.mm_gbsa import",
                "REFINE_LIGAND_MODEL",
                "mm_gbsa_binding_energy",
            ],
            "forbidden_snippets": [
                "from core.mm_gbsa import",
                "import core.mm_gbsa",
            ],
            "refine_claim_safe_required": False,
            "claim_metadata_schema": "mm_gbsa_refine_claim_metadata_v1",
        },
    ]
    rows: list[dict[str, Any]] = []
    for case in cases:
        required_missing = [
            snippet for snippet in case["required_snippets"] if str(snippet) not in script_text
        ]
        forbidden_present = [
            snippet for snippet in case["forbidden_snippets"] if str(snippet) in script_text
        ]
        direct_import_present = not required_missing
        legacy_import_absent = not forbidden_present
        rows.append(
            {
                "contract": str(case["contract"]),
                "runner": str(runner_path),
                "engine_module": str(case["engine_module"]),
                "direct_import_present": direct_import_present,
                "legacy_import_absent": legacy_import_absent,
                "required_missing": required_missing,
                "forbidden_present": forbidden_present,
                "residual_scope": str(case.get("residual_scope", "")),
                "physical_force_residual_claim": case.get("physical_force_residual_claim"),
                "bounded_correction_required": case.get("bounded_correction_required"),
                "refine_claim_safe_required": case.get("refine_claim_safe_required"),
                "claim_metadata_schema": str(case.get("claim_metadata_schema", "")),
                "ready": bool(runner_path.exists() and direct_import_present and legacy_import_absent),
            }
        )
    return {
        "ready": bool(rows and all(row["ready"] is True for row in rows)),
        "runner": str(runner_path),
        "row_count": len(rows),
        "rows": rows,
    }


def _product_runner_no_core_imports_kpi() -> dict[str, Any]:
    runner_paths = [
        Path("tools/run_ligand_htvs_pipeline.py"),
        Path("tools/run_ligand_backmapping_scoring.py"),
        Path("tools/run_ligand_topk_delivery.py"),
        Path("betelgeuze_engine/product/runners/htvs_pipeline.py"),
        Path("betelgeuze_engine/product/runners/backmapping_scoring.py"),
        Path("betelgeuze_engine/product/runners/topk_delivery.py"),
        Path("tools/product/run_ligand_htvs_pipeline.py"),
        Path("tools/product/run_ligand_backmapping_scoring.py"),
        Path("tools/product/run_ligand_topk_delivery.py"),
    ]
    rows: list[dict[str, Any]] = []
    for runner_path in runner_paths:
        violations: list[dict[str, Any]] = []
        if runner_path.exists():
            for lineno, line in enumerate(runner_path.read_text(encoding="utf-8").splitlines(), start=1):
                stripped = line.strip()
                if (
                    stripped.startswith("from core.")
                    or stripped.startswith("from core import ")
                    or stripped.startswith("import core.")
                    or stripped == "import core"
                ):
                    violations.append({"line": lineno, "snippet": stripped})
        rows.append(
            {
                "runner": str(runner_path),
                "exists": runner_path.exists(),
                "legacy_core_import_violation_count": len(violations),
                "legacy_core_import_violations": violations,
                "ready": bool(runner_path.exists() and not violations),
            }
        )
    return {
        "ready": bool(rows and all(row["ready"] is True for row in rows)),
        "row_count": len(rows),
        "legacy_core_import_violation_count": int(
            sum(int(row["legacy_core_import_violation_count"]) for row in rows)
        ),
        "rows": rows,
    }


def _topk_delivery_engine_owned_kpi() -> dict[str, Any]:
    engine_path = Path("betelgeuze_engine/product/runners/topk_delivery.py")
    compatibility_path = Path("tools/product/run_ligand_topk_delivery.py")
    engine_text = engine_path.read_text(encoding="utf-8") if engine_path.exists() else ""
    compatibility_text = compatibility_path.read_text(encoding="utf-8") if compatibility_path.exists() else ""
    engine_required_symbols = ["def build_delivery(", "def build_parser(", "def main("]
    engine_forbidden_snippets = [
        'import_module("tools.product.run_ligand_topk_delivery")',
        "import_module('tools.product.run_ligand_topk_delivery')",
    ]
    compatibility_required_snippets = [
        "from betelgeuze_engine.product.runners.topk_delivery import",
        "_sys.modules[__name__]",
    ]
    engine_required_missing = [
        snippet for snippet in engine_required_symbols if snippet not in engine_text
    ]
    engine_forbidden_present = [
        snippet for snippet in engine_forbidden_snippets if snippet in engine_text
    ]
    compatibility_required_missing = [
        snippet for snippet in compatibility_required_snippets if snippet not in compatibility_text
    ]
    compatibility_self_implementation_present = bool(
        "def build_delivery(" in compatibility_text
        or "def build_parser(" in compatibility_text
        or "argparse.ArgumentParser" in compatibility_text
    )
    runtime_identity_ready = False
    runtime_error = ""
    claim_metadata_ready = False
    claim_metadata_error = ""
    claim_metadata: dict[str, Any] = {}
    try:
        engine_module = importlib.import_module("betelgeuze_engine.product.runners.topk_delivery")
        compatibility_module = importlib.import_module("tools.product.run_ligand_topk_delivery")
        runtime_identity_ready = bool(
            compatibility_module is engine_module
            and getattr(compatibility_module, "build_delivery", None)
            is getattr(engine_module, "build_delivery", None)
            and getattr(compatibility_module, "main", None) is getattr(engine_module, "main", None)
        )
        claim_metadata = engine_module.build_topk_delivery_claim_metadata(
            ok=True,
            selected_rows=1,
            selection_mode="union",
        )
        claim_metadata_ready = bool(
            claim_metadata.get("claim_metadata_schema_version") == "topk_delivery_claim_metadata_v1"
            and claim_metadata.get("runner_kind") == "ligand_topk_delivery"
            and claim_metadata.get("claim_scope") == "topk_delivery_selection_and_handoff"
            and claim_metadata.get("claim_safe") is True
            and claim_metadata.get("blocked_reason") == ""
            and claim_metadata.get("physical_accuracy_claim") is False
            and claim_metadata.get("external_state_mutated") is False
        )
    except Exception as exc:  # pragma: no cover - evidence surface only.
        runtime_error = f"{type(exc).__name__}: {exc}"
        claim_metadata_error = runtime_error
    ready = bool(
        engine_path.exists()
        and compatibility_path.exists()
        and not engine_required_missing
        and not engine_forbidden_present
        and not compatibility_required_missing
        and not compatibility_self_implementation_present
        and runtime_identity_ready
        and claim_metadata_ready
        and not runtime_error
    )
    return {
        "ready": ready,
        "engine_module": "betelgeuze_engine.product.runners.topk_delivery",
        "engine_path": str(engine_path),
        "compatibility_path": str(compatibility_path),
        "engine_required_missing": engine_required_missing,
        "engine_forbidden_present": engine_forbidden_present,
        "compatibility_required_missing": compatibility_required_missing,
        "compatibility_self_implementation_present": compatibility_self_implementation_present,
        "runtime_identity_ready": runtime_identity_ready,
        "runtime_error": runtime_error,
        "claim_metadata_ready": claim_metadata_ready,
        "claim_metadata_schema_version": str(claim_metadata.get("claim_metadata_schema_version") or ""),
        "claim_metadata_claim_safe": claim_metadata.get("claim_safe"),
        "claim_metadata_blocked_reason": str(claim_metadata.get("blocked_reason") or ""),
        "claim_metadata_physical_accuracy_claim": claim_metadata.get("physical_accuracy_claim"),
        "claim_metadata_error": claim_metadata_error,
    }


def _backmapping_scoring_engine_owned_kpi() -> dict[str, Any]:
    engine_path = Path("betelgeuze_engine/product/runners/backmapping_scoring.py")
    compatibility_path = Path("tools/product/run_ligand_backmapping_scoring.py")
    engine_text = engine_path.read_text(encoding="utf-8") if engine_path.exists() else ""
    compatibility_text = compatibility_path.read_text(encoding="utf-8") if compatibility_path.exists() else ""
    engine_required_symbols = ["def main(", "def _frame_mmpbsa_proxy("]
    engine_forbidden_snippets = [
        'import_module("tools.product.run_ligand_backmapping_scoring")',
        "import_module('tools.product.run_ligand_backmapping_scoring')",
    ]
    compatibility_required_snippets = [
        "from betelgeuze_engine.product.runners.backmapping_scoring import",
        "_sys.modules[__name__]",
    ]
    engine_required_missing = [
        snippet for snippet in engine_required_symbols if snippet not in engine_text
    ]
    engine_forbidden_present = [
        snippet for snippet in engine_forbidden_snippets if snippet in engine_text
    ]
    compatibility_required_missing = [
        snippet for snippet in compatibility_required_snippets if snippet not in compatibility_text
    ]
    compatibility_self_implementation_present = bool(
        "def _frame_mmpbsa_proxy(" in compatibility_text
        or "argparse.ArgumentParser" in compatibility_text
        or "ProcessPoolExecutor" in compatibility_text
    )
    runtime_identity_ready = False
    runtime_error = ""
    try:
        engine_module = importlib.import_module("betelgeuze_engine.product.runners.backmapping_scoring")
        compatibility_module = importlib.import_module("tools.product.run_ligand_backmapping_scoring")
        runtime_identity_ready = bool(
            compatibility_module is engine_module
            and getattr(compatibility_module, "main", None) is getattr(engine_module, "main", None)
            and getattr(compatibility_module, "_frame_mmpbsa_proxy", None)
            is getattr(engine_module, "_frame_mmpbsa_proxy", None)
        )
    except Exception as exc:  # pragma: no cover - evidence surface only.
        runtime_error = f"{type(exc).__name__}: {exc}"
    ready = bool(
        engine_path.exists()
        and compatibility_path.exists()
        and not engine_required_missing
        and not engine_forbidden_present
        and not compatibility_required_missing
        and not compatibility_self_implementation_present
        and runtime_identity_ready
        and not runtime_error
    )
    return {
        "ready": ready,
        "engine_module": "betelgeuze_engine.product.runners.backmapping_scoring",
        "engine_path": str(engine_path),
        "compatibility_path": str(compatibility_path),
        "engine_required_missing": engine_required_missing,
        "engine_forbidden_present": engine_forbidden_present,
        "compatibility_required_missing": compatibility_required_missing,
        "compatibility_self_implementation_present": compatibility_self_implementation_present,
        "runtime_identity_ready": runtime_identity_ready,
        "runtime_error": runtime_error,
    }


def _htvs_pipeline_engine_owned_kpi() -> dict[str, Any]:
    engine_path = Path("betelgeuze_engine/product/runners/htvs_pipeline.py")
    compatibility_path = Path("tools/product/run_ligand_htvs_pipeline.py")
    engine_text = engine_path.read_text(encoding="utf-8") if engine_path.exists() else ""
    compatibility_text = compatibility_path.read_text(encoding="utf-8") if compatibility_path.exists() else ""
    engine_required_symbols = ["def run_pipeline(", "def build_parser(", "def main("]
    engine_forbidden_snippets = [
        'import_module("tools.product.run_ligand_htvs_pipeline")',
        "import_module('tools.product.run_ligand_htvs_pipeline')",
    ]
    compatibility_required_snippets = [
        "from betelgeuze_engine.product.runners.htvs_pipeline import",
        "_sys.modules[__name__]",
    ]
    engine_required_missing = [
        snippet for snippet in engine_required_symbols if snippet not in engine_text
    ]
    engine_forbidden_present = [
        snippet for snippet in engine_forbidden_snippets if snippet in engine_text
    ]
    compatibility_required_missing = [
        snippet for snippet in compatibility_required_snippets if snippet not in compatibility_text
    ]
    compatibility_self_implementation_present = bool(
        "def run_pipeline(" in compatibility_text
        or "def build_parser(" in compatibility_text
        or "argparse.ArgumentParser" in compatibility_text
    )
    runtime_identity_ready = False
    runtime_error = ""
    try:
        engine_module = importlib.import_module("betelgeuze_engine.product.runners.htvs_pipeline")
        compatibility_module = importlib.import_module("tools.product.run_ligand_htvs_pipeline")
        runtime_identity_ready = bool(
            compatibility_module is engine_module
            and getattr(compatibility_module, "run_pipeline", None)
            is getattr(engine_module, "run_pipeline", None)
            and getattr(compatibility_module, "build_parser", None)
            is getattr(engine_module, "build_parser", None)
            and getattr(compatibility_module, "main", None) is getattr(engine_module, "main", None)
        )
    except Exception as exc:  # pragma: no cover - evidence surface only.
        runtime_error = f"{type(exc).__name__}: {exc}"
    ready = bool(
        engine_path.exists()
        and compatibility_path.exists()
        and not engine_required_missing
        and not engine_forbidden_present
        and not compatibility_required_missing
        and not compatibility_self_implementation_present
        and runtime_identity_ready
        and not runtime_error
    )
    return {
        "ready": ready,
        "engine_module": "betelgeuze_engine.product.runners.htvs_pipeline",
        "engine_path": str(engine_path),
        "compatibility_path": str(compatibility_path),
        "engine_required_missing": engine_required_missing,
        "engine_forbidden_present": engine_forbidden_present,
        "compatibility_required_missing": compatibility_required_missing,
        "compatibility_self_implementation_present": compatibility_self_implementation_present,
        "runtime_identity_ready": runtime_identity_ready,
        "runtime_error": runtime_error,
    }


def _product_runner_engine_owned_kpi(
    *,
    htvs_pipeline_engine_owned: dict[str, Any],
    backmapping_scoring_engine_owned: dict[str, Any],
    topk_delivery_engine_owned: dict[str, Any],
) -> dict[str, Any]:
    rows = [
        {
            "runner_id": "ligand_htvs_pipeline_default",
            "runner_kind": "ligand_htvs_pipeline",
            "engine_module": "betelgeuze_engine.product.runners.htvs_pipeline",
            "ready": htvs_pipeline_engine_owned.get("ready") is True,
            "runtime_identity_ready": htvs_pipeline_engine_owned.get("runtime_identity_ready") is True,
            "compatibility_self_implementation_present": (
                htvs_pipeline_engine_owned.get("compatibility_self_implementation_present") is True
            ),
            "engine_required_missing": list(htvs_pipeline_engine_owned.get("engine_required_missing") or []),
            "engine_forbidden_present": list(htvs_pipeline_engine_owned.get("engine_forbidden_present") or []),
            "runtime_error": str(htvs_pipeline_engine_owned.get("runtime_error") or ""),
        },
        {
            "runner_id": "backmapping_scoring.production",
            "runner_kind": "ligand_backmapping_scoring",
            "engine_module": "betelgeuze_engine.product.runners.backmapping_scoring",
            "ready": backmapping_scoring_engine_owned.get("ready") is True,
            "runtime_identity_ready": backmapping_scoring_engine_owned.get("runtime_identity_ready") is True,
            "compatibility_self_implementation_present": (
                backmapping_scoring_engine_owned.get("compatibility_self_implementation_present") is True
            ),
            "engine_required_missing": list(
                backmapping_scoring_engine_owned.get("engine_required_missing") or []
            ),
            "engine_forbidden_present": list(
                backmapping_scoring_engine_owned.get("engine_forbidden_present") or []
            ),
            "runtime_error": str(backmapping_scoring_engine_owned.get("runtime_error") or ""),
        },
        {
            "runner_id": "ligand_topk_delivery.production",
            "runner_kind": "ligand_topk_delivery",
            "engine_module": "betelgeuze_engine.product.runners.topk_delivery",
            "ready": topk_delivery_engine_owned.get("ready") is True,
            "runtime_identity_ready": topk_delivery_engine_owned.get("runtime_identity_ready") is True,
            "compatibility_self_implementation_present": (
                topk_delivery_engine_owned.get("compatibility_self_implementation_present") is True
            ),
            "engine_required_missing": list(topk_delivery_engine_owned.get("engine_required_missing") or []),
            "engine_forbidden_present": list(topk_delivery_engine_owned.get("engine_forbidden_present") or []),
            "runtime_error": str(topk_delivery_engine_owned.get("runtime_error") or ""),
        },
    ]
    ready = bool(
        len(rows) == 3
        and all(row["ready"] is True for row in rows)
        and all(row["runtime_identity_ready"] is True for row in rows)
        and all(row["compatibility_self_implementation_present"] is False for row in rows)
        and all(not row["engine_required_missing"] for row in rows)
        and all(not row["engine_forbidden_present"] for row in rows)
        and all(not row["runtime_error"] for row in rows)
    )
    return {
        "ready": ready,
        "runner_count": len(rows),
        "engine_owned_runner_count": sum(1 for row in rows if row["ready"] is True),
        "contract": "all_product_runners_are_engine_owned_with_compatibility_shims",
        "rows": rows,
    }


def _job_store_lazy_factory_kpi() -> dict[str, Any]:
    from api.job_store import get_configured_job_store, reset_configured_job_store_for_tests

    with tempfile.TemporaryDirectory(prefix="betelgeuze_job_store_kpi_") as tmp:
        first_path = Path(tmp) / "first.sqlite3"
        second_path = Path(tmp) / "second.sqlite3"
        reset_configured_job_store_for_tests()
        first = get_configured_job_store(first_path)
        reused = get_configured_job_store(first_path)
        second = get_configured_job_store(second_path)
        ready = bool(
            first is reused
            and second is not first
            and first.path == first_path
            and second.path == second_path
            and first_path.exists()
            and second_path.exists()
        )
    reset_configured_job_store_for_tests()
    return {
        "ready": ready,
        "factory": "api.job_store.get_configured_job_store",
        "contract": "config_aware_lazy_sqlite_job_store_factory",
        "same_path_reused": first is reused,
        "changed_path_reopened": second is not first,
        "execution_enabled": False,
        "external_state_mutated": False,
    }


def _product_kpis(
    profiles_dir: str,
    product_evidence_bundle_json_path: str,
    product_ci_runtime_gate_json_path: str = DEFAULT_PRODUCT_CI_RUNTIME_GATE_JSON,
) -> dict[str, Any]:
    profile_payload = validate_profiles(Path(profiles_dir))
    force_term_plugins = default_force_term_registry().names()
    force_term_claim_metadata = _force_term_claim_metadata_kpi(force_term_plugins)
    guarded_force_term_plugin = _guarded_force_term_plugin_kpi()
    signed_runner_claim_metadata = _signed_runner_claim_metadata_kpi()
    engine_topology_factory_facade = _engine_topology_factory_facade_kpi()
    onsps_backmap_evidence_schema = _onsps_backmap_evidence_schema_kpi()
    core_forcefield_bridge = _core_forcefield_bridge_kpi()
    core_compatibility_layer = _core_compatibility_layer_kpi(core_forcefield_bridge)
    allowlisted_runner_shims = _allowlisted_runner_shim_contract_kpi(profiles_dir)
    product_runner_engine_imports = _product_runner_engine_imports_kpi()
    product_runner_no_core_imports = _product_runner_no_core_imports_kpi()
    topk_delivery_engine_owned = _topk_delivery_engine_owned_kpi()
    backmapping_scoring_engine_owned = _backmapping_scoring_engine_owned_kpi()
    htvs_pipeline_engine_owned = _htvs_pipeline_engine_owned_kpi()
    product_runner_engine_owned = _product_runner_engine_owned_kpi(
        htvs_pipeline_engine_owned=htvs_pipeline_engine_owned,
        backmapping_scoring_engine_owned=backmapping_scoring_engine_owned,
        topk_delivery_engine_owned=topk_delivery_engine_owned,
    )
    job_store_lazy_factory = _job_store_lazy_factory_kpi()
    bundle_validation = _product_bundle_validation_kpi(product_evidence_bundle_json_path)
    product_ci_runtime_gate = _product_ci_runtime_gate_kpi(product_ci_runtime_gate_json_path)
    product_claim_ready = bool(bundle_validation.get("product_claim_ready") is True)
    product_ci_runtime_gate_ready = bool(
        product_ci_runtime_gate.get("product_ci_runtime_gate_ready") is True
    )
    product_ci_blocker_code = str(product_ci_runtime_gate.get("product_ci_blocker_code") or "")
    release_claim_ready = bool(product_claim_ready and product_ci_runtime_gate_ready)
    if release_claim_ready:
        release_claim_blocked_reason = ""
    elif product_ci_blocker_code:
        release_claim_blocked_reason = product_ci_blocker_code
    elif not product_ci_runtime_gate_ready:
        release_claim_blocked_reason = "product_ci_runtime_gate_not_ready"
    else:
        release_claim_blocked_reason = "local_product_claim_not_ready"
    manifest = build_result_manifest(
        job_id="kpi_smoke",
        request={"target_name": "kpi", "runner_profile_id": "backmapping_scoring.production"},
        status="completed",
        result_file="",
        signing_key="kpi-test-key",
        key_id="kpi-test",
    )
    protein = protein_topology_from_sequence("", n_res=3)
    ligand = ligand_topology_from_smiles("")
    metadata = topology_claim_metadata(
        ComplexTopology(
            protein=protein,
            ligand=ligand,
            pocket_residue_indices=[],
            claim_scope="kpi_smoke",
        )
    )
    return {
        "clean_install_contract": "rocm_hip_rust_profile_declared",
        "clean_install_success": bool(bundle_validation.get("clean_install_success") is True),
        "clean_container_smoke_ready": bool(bundle_validation.get("clean_container_smoke_ready") is True),
        "product_runner_smoke_ready": bool(bundle_validation.get("product_runner_smoke_ready") is True),
        "product_image_receipt_present": bool(bundle_validation.get("product_image_receipt_present") is True),
        "product_image_receipt_mode": str(bundle_validation.get("product_image_receipt_mode") or ""),
        "product_image_receipt_status": str(bundle_validation.get("product_image_receipt_status") or ""),
        "product_claim_ready": product_claim_ready,
        "release_claim_ready": release_claim_ready,
        "release_claim_blocked_reason": release_claim_blocked_reason,
        **product_ci_runtime_gate,
        "clean_install_requirements": dict(bundle_validation.get("clean_install_requirements") or {}),
        "clean_install_missing_requirements": list(
            bundle_validation.get("clean_install_missing_requirements") or []
        ),
        "clean_install_missing_requirement_count": int(
            bundle_validation.get("clean_install_missing_requirement_count") or 0
        ),
        "product_image_preflight_blocker_codes": list(
            bundle_validation.get("product_image_preflight_blocker_codes") or []
        ),
        "clean_container_missing_requirements": list(
            bundle_validation.get("clean_container_missing_requirements") or []
        ),
        "clean_container_missing_requirement_count": int(
            bundle_validation.get("clean_container_missing_requirement_count") or 0
        ),
        "runner_profile_validation_status": profile_payload.get("status"),
        "runner_profile_validation_pass": profile_payload.get("status") == "pass",
        "enabled_profile_count": int(profile_payload.get("enabled_profile_count", 0)),
        "failed_profile_count": int(profile_payload.get("failed_profile_count", 0)),
        "signed_manifest_verification_pass": verify_result_manifest(manifest, signing_key="kpi-test-key"),
        "runner_claim_metadata_signed": bool(signed_runner_claim_metadata.get("ready") is True),
        "runner_claim_metadata_manifest_smoke": signed_runner_claim_metadata,
        "bundle_validation_pass": bool(bundle_validation.get("bundle_validation_pass") is True),
        "bundle_validation_checked": bool(bundle_validation.get("bundle_validation_checked") is True),
        "bundle_validation_error_count": int(bundle_validation.get("bundle_validation_error_count") or 0),
        "bundle_validation_errors": list(bundle_validation.get("bundle_validation_errors") or []),
        "source_artifacts_fresh": bool(bundle_validation.get("source_artifacts_fresh") is True),
        "source_artifact_fresh_count": int(bundle_validation.get("source_artifact_fresh_count") or 0),
        "source_artifact_stale_count": int(bundle_validation.get("source_artifact_stale_count") or 0),
        "source_artifact_stale_ids": list(bundle_validation.get("source_artifact_stale_ids") or []),
        "bundle_validation_contract": "opens_ai_md_product_evidence_tar_and_verifies_manifest_sha_members",
        "force_term_plugin_registry_ready": force_term_plugins
        == EXPECTED_PRODUCT_FORCE_TERMS,
        "force_term_plugins": force_term_plugins,
        "force_term_claim_metadata_ready": bool(force_term_claim_metadata.get("ready") is True),
        "force_term_claim_metadata_smoke": force_term_claim_metadata,
        "force_term_result_contract_ready": bool(
            force_term_claim_metadata.get("term_result_contract_ready") is True
        ),
        "force_term_result_contract_term_set_ready": bool(
            force_term_claim_metadata.get("term_result_contract_term_set_ready") is True
        ),
        "force_term_result_contract_term_count": int(
            force_term_claim_metadata.get("term_result_contract_term_count") or 0
        ),
        "force_term_result_contract_terms": list(
            force_term_claim_metadata.get("term_result_contract_terms") or []
        ),
        "force_term_result_contract_expected_terms": list(EXPECTED_PRODUCT_FORCE_TERMS),
        "forcefield_energy_forces_contract_ready": bool(
            force_term_claim_metadata.get("forcefield_energy_forces_contract_ready") is True
        ),
        "guarded_force_term_plugin_ready": bool(guarded_force_term_plugin.get("ready") is True),
        "guarded_force_term_plugin_smoke": guarded_force_term_plugin,
        "engine_topology_factory_facade_ready": bool(
            engine_topology_factory_facade.get("ready") is True
        ),
        "engine_topology_factory_facade_smoke": engine_topology_factory_facade,
        "onsps_backmap_evidence_schema_ready": bool(
            onsps_backmap_evidence_schema.get("ready") is True
        ),
        "onsps_backmap_evidence_schema_smoke": onsps_backmap_evidence_schema,
        "core_forcefield_bridge_ready": bool(core_forcefield_bridge.get("ready") is True),
        "core_forcefield_bridge_smoke": core_forcefield_bridge,
        "core_compatibility_layer_ready": bool(core_compatibility_layer.get("ready") is True),
        "core_compatibility_layer_smoke": core_compatibility_layer,
        "job_store_lazy_factory_ready": bool(job_store_lazy_factory.get("ready") is True),
        "job_store_lazy_factory_smoke": job_store_lazy_factory,
        "allowlisted_runner_shim_contract_ready": bool(allowlisted_runner_shims.get("ready") is True),
        "allowlisted_runner_shim_contract": allowlisted_runner_shims,
        "product_runner_engine_imports_ready": bool(product_runner_engine_imports.get("ready") is True),
        "product_runner_engine_imports_smoke": product_runner_engine_imports,
        "product_runner_no_core_imports_ready": bool(product_runner_no_core_imports.get("ready") is True),
        "product_runner_no_core_imports_smoke": product_runner_no_core_imports,
        "topk_delivery_engine_owned_ready": bool(topk_delivery_engine_owned.get("ready") is True),
        "topk_delivery_engine_owned_smoke": topk_delivery_engine_owned,
        "backmapping_scoring_engine_owned_ready": bool(
            backmapping_scoring_engine_owned.get("ready") is True
        ),
        "backmapping_scoring_engine_owned_smoke": backmapping_scoring_engine_owned,
        "htvs_pipeline_engine_owned_ready": bool(htvs_pipeline_engine_owned.get("ready") is True),
        "htvs_pipeline_engine_owned_smoke": htvs_pipeline_engine_owned,
        "product_runner_engine_owned_ready": bool(product_runner_engine_owned.get("ready") is True),
        "product_runner_engine_owned_smoke": product_runner_engine_owned,
        "blocked_claim_correctly_blocked": metadata["claim_safe"] is False
        and metadata["blocked_reason"] in {"empty_smiles", "placeholder_alanine_topology", "ligand_topology_invalid"},
    }


def _pose_ranking_hbond_benchmark() -> dict[str, Any]:
    default_protein_xyz = np.asarray([[0.0, 0.0, 0.0]], dtype=np.float32)
    rows: list[dict[str, Any]] = []
    for fixture in POSE_RANKING_HBOND_FIXTURES:
        ligand = ligand_topology_from_smiles(str(fixture["smiles"]))
        ligand_xyz = np.asarray(fixture["ligand_xyz"], dtype=np.float32)
        onsps_ligand_xyz = ligand_xyz[:2] if ligand_xyz.ndim == 2 and ligand_xyz.shape[0] >= 2 else ligand_xyz
        protein_xyz = default_protein_xyz
        pocket_center = None
        if fixture["expected_top1"] is True or fixture.get("near_hbond_geometry") is True:
            mapped, _meta = backmap_4bead_onsps(onsps_ligand_xyz, str(fixture["smiles"]))
            if mapped.ndim == 2 and mapped.shape[0] > 0:
                protein_xyz = mapped + np.asarray([[0.0, 0.0, 3.0]], dtype=np.float32)
                pocket_center = mapped.mean(axis=0) + np.asarray([0.0, 0.0, 6.0], dtype=np.float32)
        evidence = evaluate_hbond_evidence(
            smiles=str(fixture["smiles"]),
            protein_xyz=protein_xyz,
            ligand_xyz=onsps_ligand_xyz,
            pocket_center=pocket_center,
            delta_backmap=fixture.get("delta_backmap"),
            delta_backmap_max=float(fixture.get("delta_backmap_max", 2.5)),
        )
        validity_bonus = 0.0 if ligand.validity.get("valid") is True else -10.0
        score = float((evidence.hbond_confidence * 10.0) - float(fixture["rmsd_proxy_A"]) + validity_bonus)
        unsatisfied_site_count = int(evidence.unsatisfied_donor_count) + int(evidence.unsatisfied_acceptor_count)
        expected_blocked_reason = str(fixture.get("expected_blocked_reason") or "")
        expected_claim_safe = bool(fixture.get("expected_claim_safe") is True)
        expected_status = str(fixture.get("expected_hbond_status") or "")
        expect_unsatisfied = bool(fixture.get("expect_unsatisfied_donor_acceptor") is True)
        expect_missing_anchor = bool(fixture.get("expect_missing_anchor") is True)
        expect_overanchored = bool(fixture.get("expect_overanchored") is True)
        expect_delta_yellow_band = bool(fixture.get("expect_delta_backmap_yellow_band") is True)
        role_contract_checks = {
            "claim_safe_matches": evidence.claim_safe is expected_claim_safe,
            "status_matches": evidence.status == expected_status,
            "blocked_reason_matches": str(evidence.blocked_reason or "") == expected_blocked_reason,
            "unsatisfied_expectation_matches": (unsatisfied_site_count > 0) is expect_unsatisfied,
            "missing_anchor_expectation_matches": evidence.missing_expected_anchor_flag is expect_missing_anchor,
            "overanchored_expectation_matches": evidence.overanchoring_flag is expect_overanchored,
            "delta_backmap_expectation_matches": (
                evidence.delta_backmap_yellow_band is expect_delta_yellow_band
            ),
        }
        rows.append(
            {
                "pose_id": fixture["pose_id"],
                "benchmark_role": fixture["benchmark_role"],
                "smiles": fixture["smiles"],
                "expected_top1": fixture["expected_top1"],
                "expected_claim_safe": expected_claim_safe,
                "expected_hbond_status": expected_status,
                "expected_blocked_reason": expected_blocked_reason,
                "expected_unsatisfied_donor_acceptor": expect_unsatisfied,
                "expected_missing_anchor": expect_missing_anchor,
                "expected_overanchored": expect_overanchored,
                "expected_delta_backmap_yellow_band": expect_delta_yellow_band,
                "ligand_valid": ligand.validity.get("valid") is True,
                "hbond_status": evidence.status,
                "hbond_schema_version": evidence.schema_version,
                "hbond_schema_ready": evidence.schema_ready(),
                "hbond_threshold_schema_ready": evidence.threshold_schema_ready(),
                "hbond_pair_schema_ready": evidence.pair_schema_ready(),
                "hbond_geometry_flags_ready": evidence.geometry_flags_ready(),
                "hbond_confidence": evidence.hbond_confidence,
                "hbond_delta_backmap": evidence.delta_backmap,
                "hbond_delta_backmap_max": evidence.delta_backmap_max,
                "hbond_delta_backmap_evaluated": evidence.delta_backmap_evaluated,
                "hbond_delta_backmap_yellow_band": evidence.delta_backmap_yellow_band,
                "hbond_site_count": evidence.site_count,
                "hbond_donor_site_count": int(evidence.donor_site_count),
                "hbond_acceptor_site_count": int(evidence.acceptor_site_count),
                "hbond_distance_pass_count": int(evidence.distance_pass_count),
                "hbond_angle_pass_count": int(evidence.angle_pass_count),
                "hbond_geometry_evaluated": evidence.geometry_evaluated,
                "hbond_geometry_complete": evidence.geometry_complete,
                "hbond_claim_safe": evidence.claim_safe,
                "hbond_abstention_reason": evidence.abstention_reason,
                "hbond_blocked_reason": evidence.blocked_reason,
                "overanchoring_flag": evidence.overanchoring_flag,
                "unsatisfied_donor_count": evidence.unsatisfied_donor_count,
                "unsatisfied_acceptor_count": evidence.unsatisfied_acceptor_count,
                "onsps_backmap_schema_version": evidence.onsps_backmap_metadata.get("schema_version", ""),
                "onsps_backmap_status": evidence.onsps_backmap_metadata.get("backmap_status", ""),
                "onsps_backmap_source": evidence.onsps_backmap_metadata.get("mapping_source", ""),
                "onsps_backmap_claim_safe": evidence.onsps_backmap_metadata.get("claim_safe"),
                "onsps_backmap_blocked_reason": evidence.onsps_backmap_metadata.get("blocked_reason", ""),
                "missing_expected_anchor_flag": evidence.missing_expected_anchor_flag,
                "benchmark_contract_checks": role_contract_checks,
                "benchmark_contract_pass": all(role_contract_checks.values()),
                "rmsd_proxy_A": float(fixture["rmsd_proxy_A"]),
                "ranking_score": score,
            }
        )
    ranked = sorted(rows, key=lambda row: float(row["ranking_score"]), reverse=True)
    top1 = ranked[0] if ranked else {}
    invalid_rows = [row for row in rows if row["ligand_valid"] is not True]
    active_rows = [row for row in rows if row["expected_top1"] is True]
    overanchored_rows = [row for row in rows if "overanchored" in str(row["pose_id"])]
    top1_pass = bool(top1.get("expected_top1") is True)
    hbond_recovery_rows = [
        row for row in active_rows
        if row["hbond_claim_safe"] is True and row["hbond_status"] == "pass"
    ]
    active_hbond_ready = bool(active_rows and len(hbond_recovery_rows) == len(active_rows))
    invalid_blocked = bool(invalid_rows and all(row["hbond_claim_safe"] is False for row in invalid_rows))
    overanchored_decoys_blocked = bool(
        overanchored_rows
        and all(
            row["hbond_claim_safe"] is False
            and row["overanchoring_flag"] is True
            and row["hbond_blocked_reason"] == "overanchored_decoy"
            for row in overanchored_rows
        )
    )
    unsatisfied_rows = [
        row for row in rows
        if int(row["unsatisfied_donor_count"]) + int(row["unsatisfied_acceptor_count"]) > 0
    ]
    far_decoys_blocked = all(
        row["missing_expected_anchor_flag"] is True
        and row["hbond_claim_safe"] is False
        and row["hbond_blocked_reason"] == "missing_expected_anchor"
        for row in rows
        if str(row["pose_id"]).endswith("_decoy_pose")
        and "overanchored" not in str(row["pose_id"])
    )
    required_roles = {
        "delta_backmap_yellow_band_pose",
        "hbond_recovery_pose",
        "unsatisfied_donor_pose",
        "far_decoy_pose",
        "overanchored_decoy_pose",
        "invalid_ligand_pose",
    }
    observed_roles = {str(row["benchmark_role"]) for row in rows}
    row_contracts_ready = bool(
        required_roles.issubset(observed_roles)
        and all(row["benchmark_contract_pass"] is True for row in rows)
    )
    delta_backmap_yellow_band_abstention_ready = any(
        row["hbond_delta_backmap_yellow_band"] is True
        and row["hbond_claim_safe"] is False
        and row["hbond_blocked_reason"] == "delta_backmap_yellow_band"
        for row in rows
    )
    return {
        "benchmark_ready": bool(
            top1_pass
            and active_hbond_ready
            and invalid_blocked
            and far_decoys_blocked
            and overanchored_decoys_blocked
            and delta_backmap_yellow_band_abstention_ready
            and bool(unsatisfied_rows)
            and row_contracts_ready
        ),
        "fixture_count": len(rows),
        "required_pose_roles": sorted(required_roles),
        "observed_pose_roles": sorted(observed_roles),
        "row_contracts_ready": row_contracts_ready,
        "row_contract_pass_count": sum(1 for row in rows if row["benchmark_contract_pass"] is True),
        "top1_pose_id": str(top1.get("pose_id", "")),
        "top1_expected_pose_id": "amide_near_hbond_pose",
        "top1_pass": top1_pass,
        "active_hbond_ready": active_hbond_ready,
        "hbond_recovery_pose_count": len(hbond_recovery_rows),
        "hbond_recovery_pose_ids": [str(row["pose_id"]) for row in hbond_recovery_rows],
        "hbond_recovery_confidence_min": float(
            min(float(row["hbond_confidence"]) for row in hbond_recovery_rows)
        ) if hbond_recovery_rows else 0.0,
        "invalid_ligand_blocked": invalid_blocked,
        "far_decoys_blocked": far_decoys_blocked,
        "overanchored_decoys_blocked": overanchored_decoys_blocked,
        "delta_backmap_yellow_band_abstention_ready": delta_backmap_yellow_band_abstention_ready,
        "unsatisfied_donor_acceptor_detected": bool(unsatisfied_rows),
        "unsatisfied_donor_acceptor_pose_count": len(unsatisfied_rows),
        "unsatisfied_donor_count": int(sum(int(row["unsatisfied_donor_count"]) for row in unsatisfied_rows)),
        "unsatisfied_acceptor_count": int(sum(int(row["unsatisfied_acceptor_count"]) for row in unsatisfied_rows)),
        "ranking_order": [str(row["pose_id"]) for row in ranked],
        "rows": rows,
    }


def _pm_kpi_summary(
    *,
    runtime: dict[str, Any],
    physics: dict[str, Any],
    chemistry: dict[str, Any],
    pose_ranking_hbond: dict[str, Any],
    confidence_calibration: dict[str, Any],
    product: dict[str, Any],
    rocm_runtime_ready: bool,
) -> dict[str, Any]:
    runtime_score = runtime.get("score_only_1k") if isinstance(runtime.get("score_only_1k"), dict) else {}
    runtime_onsps = (
        runtime.get("top100_4bead_rescoring")
        if isinstance(runtime.get("top100_4bead_rescoring"), dict)
        else {}
    )
    runtime_residual = (
        runtime.get("top10_force_residual")
        if isinstance(runtime.get("top10_force_residual"), dict)
        else {}
    )
    neighbor = (
        runtime.get("neighbor_list_rebuild")
        if isinstance(runtime.get("neighbor_list_rebuild"), dict)
        else {}
    )
    runtime_scaling = (
        runtime.get("neighbor_cap_scaling")
        if isinstance(runtime.get("neighbor_cap_scaling"), dict)
        else {}
    )
    product_gate_values = {
        "clean_install_success": product.get("clean_install_success") is True,
        "runner_profile_validation_pass": product.get("runner_profile_validation_status") == "pass",
        "signed_manifest_verification_pass": product.get("signed_manifest_verification_pass") is True,
        "runner_claim_metadata_signed": product.get("runner_claim_metadata_signed") is True,
        "bundle_validation_pass": product.get("bundle_validation_pass") is True,
        "source_artifacts_fresh": product.get("source_artifacts_fresh") is True,
        "force_term_plugin_registry_ready": product.get("force_term_plugin_registry_ready") is True,
        "force_term_claim_metadata_ready": product.get("force_term_claim_metadata_ready") is True,
        "force_term_result_contract_ready": product.get("force_term_result_contract_ready") is True,
        "force_term_result_contract_term_set_ready": (
            product.get("force_term_result_contract_term_set_ready") is True
        ),
        "forcefield_energy_forces_contract_ready": (
            product.get("forcefield_energy_forces_contract_ready") is True
        ),
        "guarded_force_term_plugin_ready": product.get("guarded_force_term_plugin_ready") is True,
        "engine_topology_factory_facade_ready": product.get("engine_topology_factory_facade_ready") is True,
        "onsps_backmap_evidence_schema_ready": product.get("onsps_backmap_evidence_schema_ready") is True,
        "core_forcefield_bridge_ready": product.get("core_forcefield_bridge_ready") is True,
        "core_compatibility_layer_ready": product.get("core_compatibility_layer_ready") is True,
        "job_store_lazy_factory_ready": product.get("job_store_lazy_factory_ready") is True,
        "allowlisted_runner_shim_contract_ready": product.get("allowlisted_runner_shim_contract_ready") is True,
        "product_runner_engine_imports_ready": product.get("product_runner_engine_imports_ready") is True,
        "product_runner_no_core_imports_ready": product.get("product_runner_no_core_imports_ready") is True,
        "topk_delivery_engine_owned_ready": product.get("topk_delivery_engine_owned_ready") is True,
        "backmapping_scoring_engine_owned_ready": (
            product.get("backmapping_scoring_engine_owned_ready") is True
        ),
        "htvs_pipeline_engine_owned_ready": product.get("htvs_pipeline_engine_owned_ready") is True,
        "product_runner_engine_owned_ready": product.get("product_runner_engine_owned_ready") is True,
        "blocked_claim_correctly_blocked": product.get("blocked_claim_correctly_blocked") is True,
        "rocm_hip_rust_runtime_ready": rocm_runtime_ready,
    }
    runtime_gate_values = {
        "score_only_1k_runtime_tracked": (
            int(runtime_score.get("row_count") or 0) > 0
            and float(runtime_score.get("duration_sec") or 0.0) > 0.0
            and float(runtime_score.get("rows_per_sec") or 0.0) > 0.0
        ),
        "top100_4bead_rescoring_runtime_tracked": (
            int(runtime_onsps.get("row_count") or 0) > 0
            and float(runtime_onsps.get("duration_sec") or 0.0) > 0.0
            and float(runtime_onsps.get("rows_per_sec") or 0.0) > 0.0
            and int(runtime_onsps.get("onsps_backmap_claim_safe_count") or 0) > 0
        ),
        "top10_force_residual_runtime_tracked": (
            int(runtime_residual.get("row_count") or 0) > 0
            and float(runtime_residual.get("duration_sec") or 0.0) > 0.0
            and float(runtime_residual.get("rows_per_sec") or 0.0) > 0.0
            and int(runtime_residual.get("applied_count") or 0) > 0
        ),
        "memory_peak_tracked": float(runtime.get("memory_peak_mb") or 0.0) > 0.0,
        "neighbor_list_rebuild_frequency_tracked": (
            int(neighbor.get("frame_count") or 0) > 0
            and int(neighbor.get("neighbor_list_rebuild_count") or 0) > 0
            and float(neighbor.get("neighbor_list_rebuild_frequency") or 0.0) > 0.0
            and neighbor.get("engine_neighbor_diagnostics_ready") is True
        ),
        "runtime_neighbor_cap_scaling_ready": (
            runtime_scaling.get("ready") is True
            and runtime_scaling.get("status") == "runtime_neighbor_cap_scaling_ready"
            and runtime_scaling.get("forcefield_contract_ready") is True
            and runtime_scaling.get("neighbor_cap_scaling_ready") is True
            and 0.85 <= float(runtime_scaling.get("neighbor_pair_count_slope") or 0.0) <= 1.15
            and float(runtime_scaling.get("neighbor_pair_count_r2") or 0.0) >= 0.98
            and bool(runtime_scaling.get("rows"))
        ),
        "runtime_neighbor_cap_scaling_plot_ready": (
            runtime_scaling.get("plot_ready") is True
            and runtime_scaling.get("plot_format") == "svg"
            and runtime_scaling.get("plot_role") == "runtime_neighbor_cap_scaling_plot"
            and len(str(runtime_scaling.get("plot_sha256") or "")) == 64
            and int(runtime_scaling.get("plot_size_bytes") or 0) > 0
            and "Pair-count scaling" in str(runtime_scaling.get("plot_claim_boundary") or "")
            and "advisory" in str(runtime_scaling.get("plot_claim_boundary") or "")
        ),
        "force_residual_bounded_policy_ready": runtime_residual.get("bounded_correction_policy_ready") is True,
        "force_residual_observed_caps_ready": runtime_residual.get("observed_caps_ready") is True,
        "force_residual_contract_ready": runtime_residual.get("contract_ready") is True,
        "force_residual_confidence_abstention_ready": runtime_residual.get("confidence_abstention_ready") is True,
        "force_residual_top_k_policy_ready": runtime_residual.get("top_k_policy_ready") is True,
    }
    physics_gate_values = {
        "finite_difference_force_error_pass": float(physics.get("finite_difference_force_error") or 0.0) < 1e-3,
        "translation_invariance_pass": float(physics.get("translation_invariance_error") or 0.0) < 1e-9,
        "rotation_equivariance_pass": float(physics.get("rotation_equivariance_error") or 0.0) < 1e-9,
        "neighbor_list_parity_pass": float(physics.get("neighbor_list_parity_error") or 0.0) == 0.0,
        "energy_drift_pass": float(physics.get("energy_drift_smoke_pct") or 0.0) < 1e-2,
        "force_term_physics_validation_ready": physics.get("force_term_physics_validation_ready") is True,
        "force_term_physics_validation_claim_safe_ready": (
            physics.get("force_term_physics_validation_claim_safe_ready") is True
        ),
        "topology_invalid_rate_pass": (
            "topology_invalid_rate" in physics
            and float(physics.get("topology_invalid_rate") or 0.0) < 0.2
        ),
        "backmapping_failure_rate_pass": (
            "backmapping_failure_rate" in physics
            and float(physics.get("backmapping_failure_rate") or 0.0) < 0.5
        ),
    }
    unsatisfied_donor_acceptor_detected = bool(
        int(chemistry.get("unsatisfied_donor_acceptor_fixture_count") or 0) > 0
        or pose_ranking_hbond.get("unsatisfied_donor_acceptor_detected") is True
    )
    hbond_recovery_pose_count = int(pose_ranking_hbond.get("hbond_recovery_pose_count") or 0)
    chemistry_gate_values = {
        "hbond_evidence_schema_ready": chemistry.get("hbond_evidence_schema_ready") is True,
        "ligand_topology_validity_schema_ready": (
            chemistry.get("ligand_topology_validity_schema_ready") is True
        ),
        "hbond_recovery_present": hbond_recovery_pose_count > 0,
        "unsatisfied_donor_acceptor_detection": unsatisfied_donor_acceptor_detected,
        "topology_invalid_rate_tracked": "topology_invalid_rate" in chemistry,
        "backmapping_failure_rate_tracked": "backmapping_failure_rate" in chemistry,
        "chirality_preservation_ready": chemistry.get("chirality_preservation_ready") is True,
        "ring_validity_ready": chemistry.get("ring_validity_ready") is True,
        "tautomer_validity_ready": chemistry.get("tautomer_validity_ready") is True,
        "protonation_validity_ready": chemistry.get("protonation_validity_ready") is True,
        "confidence_calibration_report_ready": (
            confidence_calibration.get("ready") is True
            and confidence_calibration.get("status") == "confidence_calibration_report_ready"
            and int(confidence_calibration.get("row_count") or 0) >= 4
            and int(confidence_calibration.get("positive_count") or 0) >= 1
            and int(confidence_calibration.get("negative_count") or 0) >= 1
            and float(confidence_calibration.get("expected_calibration_error") or 1.0)
            <= float(confidence_calibration.get("max_expected_calibration_error") or 0.0)
            and float(confidence_calibration.get("brier_score") or 1.0)
            <= float(confidence_calibration.get("max_brier_score") or 0.0)
        ),
    }
    gate_values = {
        **product_gate_values,
        **runtime_gate_values,
        **physics_gate_values,
        **chemistry_gate_values,
        "pose_ranking_hbond_benchmark_ready": pose_ranking_hbond.get("benchmark_ready") is True,
    }
    failed = [key for key, value in gate_values.items() if value is not True]
    product_summary_values = {
        **product_gate_values,
        "product_claim_ready": product.get("product_claim_ready") is True,
        "release_claim_ready": product.get("release_claim_ready") is True,
        "release_claim_blocked_reason": str(product.get("release_claim_blocked_reason") or ""),
        "product_ci_runtime_gate_present": product.get("product_ci_runtime_gate_present") is True,
        "product_ci_runtime_gate_ready": product.get("product_ci_runtime_gate_ready") is True,
        "product_ci_runtime_gate_status": str(product.get("product_ci_runtime_gate_status") or ""),
        "product_ci_remote_green": product.get("product_ci_remote_green") is True,
        "product_ci_github_actions_started": product.get("product_ci_github_actions_started") is True,
        "product_ci_external_blocker": product.get("product_ci_external_blocker") is True,
        "product_ci_blocker_code": str(product.get("product_ci_blocker_code") or ""),
        "product_ci_billing_free_self_hosted_path_recommended": (
            product.get("product_ci_billing_free_self_hosted_path_recommended") is True
        ),
        "product_ci_billing_free_self_hosted_api_worker_command": str(
            product.get("product_ci_billing_free_self_hosted_api_worker_command") or ""
        ),
        "product_ci_billing_free_self_hosted_rocm_runtime_command": str(
            product.get("product_ci_billing_free_self_hosted_rocm_runtime_command") or ""
        ),
        "product_ci_hosted_spending_limit_increase_required": (
            product.get("product_ci_hosted_spending_limit_increase_required") is True
        ),
        "product_ci_self_hosted_runner_inventory_present": (
            product.get("product_ci_self_hosted_runner_inventory_present") is True
        ),
        "product_ci_self_hosted_runner_total_count": int(
            product.get("product_ci_self_hosted_runner_total_count") or 0
        ),
        "product_ci_self_hosted_linux_runner_online": (
            product.get("product_ci_self_hosted_linux_runner_online") is True
        ),
        "product_ci_self_hosted_linux_runner_count": int(
            product.get("product_ci_self_hosted_linux_runner_count") or 0
        ),
        "product_ci_self_hosted_rocm_runner_online": (
            product.get("product_ci_self_hosted_rocm_runner_online") is True
        ),
        "product_ci_self_hosted_rocm_runner_count": int(
            product.get("product_ci_self_hosted_rocm_runner_count") or 0
        ),
        "product_ci_self_hosted_runner_inventory_external_state_mutated": (
            product.get("product_ci_self_hosted_runner_inventory_external_state_mutated") is True
        ),
        "product_ci_self_hosted_runner_host_preflight_present": (
            product.get("product_ci_self_hosted_runner_host_preflight_present") is True
        ),
        "product_ci_self_hosted_runner_host_preflight_status": str(
            product.get("product_ci_self_hosted_runner_host_preflight_status") or ""
        ),
        "product_ci_self_hosted_runner_host_local_ready": (
            product.get("product_ci_self_hosted_runner_host_local_ready") is True
        ),
        "product_ci_self_hosted_runner_host_repo_ready": (
            product.get("product_ci_self_hosted_runner_host_repo_ready") is True
        ),
        "product_ci_self_hosted_runner_host_registration_required": (
            product.get("product_ci_self_hosted_runner_host_registration_required") is True
        ),
        "product_ci_self_hosted_runner_host_github_registration_token_requested": (
            product.get("product_ci_self_hosted_runner_host_github_registration_token_requested") is True
        ),
        "product_ci_self_hosted_runner_host_external_state_mutated": (
            product.get("product_ci_self_hosted_runner_host_external_state_mutated") is True
        ),
        "product_ci_latest_github_actions_record_kst_date": str(
            product.get("product_ci_latest_github_actions_record_kst_date") or ""
        ),
        "clean_install_missing_requirement_count": int(
            product.get("clean_install_missing_requirement_count") or 0
        ),
        "clean_install_missing_requirements": list(
            product.get("clean_install_missing_requirements") or []
        ),
        "product_image_preflight_blocker_codes": list(
            product.get("product_image_preflight_blocker_codes") or []
        ),
        "clean_container_missing_requirement_count": int(
            product.get("clean_container_missing_requirement_count") or 0
        ),
        "clean_container_missing_requirements": list(
            product.get("clean_container_missing_requirements") or []
        ),
        "source_artifact_fresh_count": int(product.get("source_artifact_fresh_count") or 0),
        "source_artifact_stale_count": int(product.get("source_artifact_stale_count") or 0),
        "source_artifact_stale_ids": list(product.get("source_artifact_stale_ids") or []),
        "enabled_profile_count": int(product.get("enabled_profile_count") or 0),
        "failed_profile_count": int(product.get("failed_profile_count") or 0),
        "force_term_result_contract_term_count": int(
            product.get("force_term_result_contract_term_count") or 0
        ),
        "force_term_result_contract_terms": list(
            product.get("force_term_result_contract_terms") or []
        ),
        "force_term_result_contract_expected_terms": list(
            product.get("force_term_result_contract_expected_terms") or []
        ),
    }
    return {
        "summary_ready": not failed,
        "failed_gate_ids": failed,
        "runtime": {
            "score_only_1k_runtime_sec": float(runtime_score.get("duration_sec") or 0.0),
            "score_only_1k_rows_per_sec": float(runtime_score.get("rows_per_sec") or 0.0),
            "top100_4bead_rescoring_runtime_sec": float(runtime_onsps.get("duration_sec") or 0.0),
            "top100_4bead_rescoring_rows_per_sec": float(runtime_onsps.get("rows_per_sec") or 0.0),
            "top10_force_residual_runtime_sec": float(runtime_residual.get("duration_sec") or 0.0),
            "top10_force_residual_rows_per_sec": float(runtime_residual.get("rows_per_sec") or 0.0),
            "memory_peak_mb": float(runtime.get("memory_peak_mb") or 0.0),
            "neighbor_list_rebuild_frequency": float(
                neighbor.get("neighbor_list_rebuild_frequency") or 0.0
            ),
            "runtime_neighbor_cap_scaling_ready": runtime_gate_values[
                "runtime_neighbor_cap_scaling_ready"
            ],
            "runtime_neighbor_cap_scaling_status": str(runtime_scaling.get("status") or ""),
            "runtime_neighbor_cap_scaling_row_count": len(runtime_scaling.get("rows") or []),
            "runtime_neighbor_cap_scaling_atom_counts": list(runtime_scaling.get("atom_counts") or []),
            "runtime_neighbor_cap_scaling_pair_count_slope": float(
                runtime_scaling.get("neighbor_pair_count_slope") or 0.0
            ),
            "runtime_neighbor_cap_scaling_pair_count_r2": float(
                runtime_scaling.get("neighbor_pair_count_r2") or 0.0
            ),
            "runtime_neighbor_cap_scaling_duration_slope": float(
                runtime_scaling.get("duration_slope") or 0.0
            ),
            "runtime_neighbor_cap_scaling_duration_r2": float(
                runtime_scaling.get("duration_r2") or 0.0
            ),
            "runtime_neighbor_cap_scaling_plot_ready": runtime_gate_values[
                "runtime_neighbor_cap_scaling_plot_ready"
            ],
            "runtime_neighbor_cap_scaling_plot_path": str(runtime_scaling.get("plot_path") or ""),
            "runtime_neighbor_cap_scaling_plot_sha256": str(runtime_scaling.get("plot_sha256") or ""),
            "score_only_1k_runtime_tracked": runtime_gate_values["score_only_1k_runtime_tracked"],
            "top100_4bead_rescoring_runtime_tracked": (
                runtime_gate_values["top100_4bead_rescoring_runtime_tracked"]
            ),
            "top10_force_residual_runtime_tracked": (
                runtime_gate_values["top10_force_residual_runtime_tracked"]
            ),
            "memory_peak_tracked": runtime_gate_values["memory_peak_tracked"],
            "neighbor_list_rebuild_frequency_tracked": (
                runtime_gate_values["neighbor_list_rebuild_frequency_tracked"]
            ),
            "force_residual_bounded_policy_ready": runtime_residual.get("bounded_correction_policy_ready") is True,
            "force_residual_observed_caps_ready": runtime_residual.get("observed_caps_ready") is True,
            "force_residual_contract_ready": runtime_residual.get("contract_ready") is True,
            "force_residual_confidence_abstention_ready": runtime_residual.get("confidence_abstention_ready") is True,
            "force_residual_top_k_policy_ready": runtime_residual.get("top_k_policy_ready") is True,
            "force_residual_abstain_threshold": float(
                (runtime_residual.get("uncertainty_abstention_report") or {})
                .get("policy_caps", {})
                .get("abstain_threshold", 0.0)
            ),
            "force_residual_top_k_rank_pct": float(
                (runtime_residual.get("outside_top_k_report") or {})
                .get("policy_caps", {})
                .get("top_k_rank_pct", 0.0)
            ),
        },
        "physics": {
            "finite_difference_force_error": float(physics.get("finite_difference_force_error") or 0.0),
            "finite_difference_force_error_pass": physics_gate_values["finite_difference_force_error_pass"],
            "energy_drift_smoke_pct": float(physics.get("energy_drift_smoke_pct") or 0.0),
            "energy_drift_pass": physics_gate_values["energy_drift_pass"],
            "rotation_equivariance_error": float(physics.get("rotation_equivariance_error") or 0.0),
            "rotation_equivariance_pass": physics_gate_values["rotation_equivariance_pass"],
            "neighbor_list_parity_error": float(physics.get("neighbor_list_parity_error") or 0.0),
            "neighbor_list_parity_pass": physics_gate_values["neighbor_list_parity_pass"],
            "topology_invalid_rate": float(physics.get("topology_invalid_rate") or 0.0),
            "topology_invalid_rate_pass": physics_gate_values["topology_invalid_rate_pass"],
            "backmapping_failure_rate": float(physics.get("backmapping_failure_rate") or 0.0),
            "backmapping_failure_rate_pass": physics_gate_values["backmapping_failure_rate_pass"],
            "force_term_physics_validation_ready": physics.get("force_term_physics_validation_ready") is True,
            "force_term_physics_validation_term_count": int(
                physics.get("force_term_physics_validation_term_count") or 0
            ),
            "force_term_physics_validation_claim_safe_ready": (
                physics.get("force_term_physics_validation_claim_safe_ready") is True
            ),
            "force_term_physics_validation_claim_safe_count": int(
                physics.get("force_term_physics_validation_claim_safe_count") or 0
            ),
            "force_term_finite_difference_max_error": float(
                physics.get("force_term_finite_difference_max_error") or 0.0
            ),
            "force_term_translation_invariance_max_error": float(
                physics.get("force_term_translation_invariance_max_error") or 0.0
            ),
            "force_term_rotation_equivariance_max_error": float(
                physics.get("force_term_rotation_equivariance_max_error") or 0.0
            ),
            "force_term_energy_drift_max_pct": float(
                physics.get("force_term_energy_drift_max_pct") or 0.0
            ),
        },
        "chemistry": {
            "hbond_evidence_schema_ready": chemistry.get("hbond_evidence_schema_ready") is True,
            "hbond_evidence_schema_ready_count": int(
                chemistry.get("hbond_evidence_schema_ready_count") or 0
            ),
            "ligand_topology_validity_schema_ready": (
                chemistry.get("ligand_topology_validity_schema_ready") is True
            ),
            "ligand_topology_validity_schema_ready_count": int(
                chemistry.get("ligand_topology_validity_schema_ready_count") or 0
            ),
            "hbond_donor_site_count": int(chemistry.get("hbond_donor_site_count") or 0),
            "hbond_acceptor_site_count": int(chemistry.get("hbond_acceptor_site_count") or 0),
            "hbond_geometry_evaluated_fixture_count": int(
                chemistry.get("hbond_geometry_evaluated_fixture_count") or 0
            ),
            "hbond_geometry_complete_fixture_count": int(
                chemistry.get("hbond_geometry_complete_fixture_count") or 0
            ),
            "hbond_recovery_fixture_count": int(chemistry.get("hbond_recovery_fixture_count") or 0),
            "hbond_recovery_pose_count": hbond_recovery_pose_count,
            "hbond_recovery_pose_ids": list(pose_ranking_hbond.get("hbond_recovery_pose_ids") or []),
            "hbond_recovery_confidence_min": float(
                pose_ranking_hbond.get("hbond_recovery_confidence_min") or 0.0
            ),
            "unsatisfied_donor_acceptor_detection": unsatisfied_donor_acceptor_detected,
            "unsatisfied_donor_acceptor_fixture_count": int(
                chemistry.get("unsatisfied_donor_acceptor_fixture_count") or 0
            ),
            "unsatisfied_donor_count": int(chemistry.get("unsatisfied_donor_count") or 0),
            "unsatisfied_acceptor_count": int(chemistry.get("unsatisfied_acceptor_count") or 0),
            "unsatisfied_donor_acceptor_pose_count": int(
                pose_ranking_hbond.get("unsatisfied_donor_acceptor_pose_count") or 0
            ),
            "overanchored_decoy_rejection": pose_ranking_hbond.get("overanchored_decoys_blocked") is True,
            "chirality_preservation_fixture_count": int(
                chemistry.get("chirality_preservation_fixture_count") or 0
            ),
            "unassigned_chirality_blocked_fixture_count": int(
                chemistry.get("unassigned_chirality_blocked_fixture_count") or 0
            ),
            "chirality_preservation_ready": chemistry.get("chirality_preservation_ready") is True,
            "ring_validity_fixture_count": int(chemistry.get("ring_validity_fixture_count") or 0),
            "ring_validity_ready": chemistry.get("ring_validity_ready") is True,
            "tautomer_validity_fixture_count": int(
                chemistry.get("tautomer_validity_fixture_count") or 0
            ),
            "tautomer_validity_ready": chemistry.get("tautomer_validity_ready") is True,
            "protonation_validity_fixture_count": int(
                chemistry.get("protonation_validity_fixture_count") or 0
            ),
            "protonation_validity_ready": chemistry.get("protonation_validity_ready") is True,
            "confidence_calibration_report_ready": chemistry_gate_values[
                "confidence_calibration_report_ready"
            ],
            "confidence_calibration_status": str(confidence_calibration.get("status") or ""),
            "confidence_calibration_row_count": int(confidence_calibration.get("row_count") or 0),
            "confidence_calibration_positive_count": int(
                confidence_calibration.get("positive_count") or 0
            ),
            "confidence_calibration_negative_count": int(
                confidence_calibration.get("negative_count") or 0
            ),
            "confidence_calibration_expected_calibration_error": float(
                confidence_calibration.get("expected_calibration_error") or 0.0
            ),
            "confidence_calibration_brier_score": float(
                confidence_calibration.get("brier_score") or 0.0
            ),
            "confidence_calibration_bin_count": int(confidence_calibration.get("bin_count") or 0),
        },
        "product": product_summary_values,
    }


def build_report(
    *,
    profiles_dir: str,
    score_only_rows: int,
    onsps_rows: int,
    residual_rows: int,
    runtime_scaling_plot_path: str = DEFAULT_RUNTIME_SCALING_PLOT,
    rocm_manifest_path: str = DEFAULT_ROCM_MANIFEST_JSON,
    product_evidence_bundle_json_path: str = DEFAULT_PRODUCT_EVIDENCE_BUNDLE_JSON,
    product_ci_runtime_gate_json_path: str = DEFAULT_PRODUCT_CI_RUNTIME_GATE_JSON,
) -> dict[str, Any]:
    _quiet_rdkit_parser_logs()
    runtime_scaling = run_runtime_scaling_benchmark().to_dict()
    runtime_scaling.update(_runtime_scaling_plot_metadata(runtime_scaling, runtime_scaling_plot_path))
    runtime = {
        "score_only_1k": _score_only_runtime(score_only_rows),
        "top100_4bead_rescoring": _onsps_runtime(onsps_rows),
        "top10_force_residual": _force_residual_runtime(residual_rows),
        "memory_peak_mb": _memory_peak_mb(),
        "neighbor_list_rebuild": _neighbor_rebuild_kpi(),
        "neighbor_cap_scaling": runtime_scaling,
    }
    runtime["score_only_1k_runtime_sec"] = float(runtime["score_only_1k"].get("duration_sec") or 0.0)
    runtime["top100_4bead_rescoring_runtime_sec"] = float(
        runtime["top100_4bead_rescoring"].get("duration_sec") or 0.0
    )
    runtime["top10_force_residual_runtime_sec"] = float(
        runtime["top10_force_residual"].get("duration_sec") or 0.0
    )
    runtime["neighbor_list_rebuild_frequency"] = float(
        runtime["neighbor_list_rebuild"].get("neighbor_list_rebuild_frequency") or 0.0
    )
    physics = _physics_kpis()
    chemistry = _chemistry_kpis()
    physics["topology_invalid_rate"] = float(chemistry.get("topology_invalid_rate") or 0.0)
    physics["backmapping_failure_rate"] = float(chemistry.get("backmapping_failure_rate") or 0.0)
    product = _product_kpis(
        profiles_dir,
        product_evidence_bundle_json_path,
        product_ci_runtime_gate_json_path,
    )
    pose_ranking_hbond = _pose_ranking_hbond_benchmark()
    confidence_calibration = build_confidence_calibration_report(
        pose_ranking_hbond.get("rows") or []
    )
    hbond_recovery_pose_count = int(pose_ranking_hbond.get("hbond_recovery_pose_count") or 0)
    chemistry["hbond_recovery_present"] = hbond_recovery_pose_count > 0
    chemistry["hbond_recovery_pose_count"] = hbond_recovery_pose_count
    chemistry["hbond_recovery_pose_ids"] = list(pose_ranking_hbond.get("hbond_recovery_pose_ids") or [])
    chemistry["hbond_recovery_confidence_min"] = float(
        pose_ranking_hbond.get("hbond_recovery_confidence_min") or 0.0
    )
    chemistry["unsatisfied_donor_acceptor_detection"] = bool(
        int(chemistry.get("unsatisfied_donor_acceptor_fixture_count") or 0) > 0
        or pose_ranking_hbond.get("unsatisfied_donor_acceptor_detected") is True
    )
    chemistry["unsatisfied_donor_acceptor_pose_count"] = int(
        pose_ranking_hbond.get("unsatisfied_donor_acceptor_pose_count") or 0
    )
    chemistry["overanchored_decoy_rejection"] = (
        pose_ranking_hbond.get("overanchored_decoys_blocked") is True
    )
    rocm_summary = {}
    rocm_path = Path(rocm_manifest_path)
    if rocm_path.exists():
        try:
            rocm_summary = (json.loads(rocm_path.read_text(encoding="utf-8")).get("summary") or {})
        except json.JSONDecodeError:
            rocm_summary = {"status": "invalid_rocm_manifest"}
    rocm_runtime_ready = _rocm_product_runtime_ready(rocm_summary)
    pm_summary = _pm_kpi_summary(
        runtime=runtime,
        physics=physics,
        chemistry=chemistry,
        pose_ranking_hbond=pose_ranking_hbond,
        confidence_calibration=confidence_calibration,
        product=product,
        rocm_runtime_ready=rocm_runtime_ready,
    )
    ready = bool(pm_summary.get("summary_ready") is True)
    return {
        "packet_type": "ai_md_engine_kpi_report",
        "status": "ai_md_engine_kpi_report_ready" if ready else "blocked_ai_md_engine_kpi_report",
        "report_ready": ready,
        "claim_boundary": (
            "Local micro-smoke KPI report only; does not claim commercial accuracy, run public benchmarks, "
            "submit predictions, mutate external state, or widen product scope."
        ),
        "runtime_kpi": runtime,
        "physics_kpi": physics,
        "chemistry_kpi": chemistry,
        "pm_kpi_summary": pm_summary,
        "pose_ranking_hbond_benchmark": pose_ranking_hbond,
        "confidence_calibration_report": confidence_calibration,
        "product_kpi": product,
        "product_bundle_evidence_export_ready": ready,
        "rocm_environment_summary": {
            "commercial_compute_default": rocm_summary.get("commercial_compute_default", ""),
            "torch_rocm_ready": rocm_summary.get("torch_rocm_ready"),
            "visible_device_count": rocm_summary.get("visible_device_count"),
            "device_nodes_ready": rocm_summary.get("device_nodes_ready"),
            "production_execution_ready": rocm_summary.get("production_execution_ready"),
            "cpu_fallback_allowed_for_product": rocm_summary.get("cpu_fallback_allowed_for_product", False),
            "rocm_hip_rust_runtime_ready": rocm_runtime_ready,
            "product_runtime_completion_rule": rocm_summary.get(
                "product_runtime_completion_rule",
                "commercial_compute_default=rocm_hip; torch_rocm_ready=true; visible_device_count>0; device_nodes_ready=true",
            ),
            "next_required_step": rocm_summary.get("next_required_step", ""),
        },
    }


def _write_md(path: Path, report: dict[str, Any]) -> None:
    lines = [
        "# AI-MD Engine KPI Report",
        "",
        f"- status: `{report['status']}`",
        f"- claim_boundary: {report['claim_boundary']}",
        "",
        "## Runtime KPI",
    ]
    for key, value in report["runtime_kpi"].items():
        if isinstance(value, dict) and "duration_sec" in value:
            lines.append(f"- {key}: `{value['duration_sec']:.6f}s`, `{value['rows_per_sec']:.2f} rows/sec`")
        else:
            lines.append(f"- {key}: `{value}`")
    lines.extend(
        [
            "",
            "## Physics KPI",
            f"- finite_difference_force_error: `{report['physics_kpi']['finite_difference_force_error']}`",
            f"- translation_invariance_error: `{report['physics_kpi']['translation_invariance_error']}`",
            f"- rotation_equivariance_error: `{report['physics_kpi']['rotation_equivariance_error']}`",
            f"- energy_drift_smoke_pct: `{report['physics_kpi']['energy_drift_smoke_pct']}`",
            f"- neighbor_list_parity_error: `{report['physics_kpi']['neighbor_list_parity_error']}`",
            f"- topology_invalid_rate: `{report['physics_kpi']['topology_invalid_rate']}`",
            f"- backmapping_failure_rate: `{report['physics_kpi']['backmapping_failure_rate']}`",
            "",
            "## Chemistry KPI",
            f"- fixture_count: `{report['chemistry_kpi']['fixture_count']}`",
            f"- hbond_evidence_schema_ready: `{report['chemistry_kpi']['hbond_evidence_schema_ready']}`",
            f"- hbond_evidence_schema_ready_count: `{report['chemistry_kpi']['hbond_evidence_schema_ready_count']}`",
            (
                "- ligand_topology_validity_schema_ready: "
                f"`{report['chemistry_kpi']['ligand_topology_validity_schema_ready']}`"
            ),
            (
                "- ligand_topology_validity_schema_ready_count: "
                f"`{report['chemistry_kpi']['ligand_topology_validity_schema_ready_count']}`"
            ),
            f"- hbond_donor_site_count: `{report['chemistry_kpi']['hbond_donor_site_count']}`",
            f"- hbond_acceptor_site_count: `{report['chemistry_kpi']['hbond_acceptor_site_count']}`",
            f"- hbond_recovery_fixture_count: `{report['chemistry_kpi']['hbond_recovery_fixture_count']}`",
            f"- topology_invalid_rate: `{report['chemistry_kpi']['topology_invalid_rate']}`",
            f"- backmapping_failure_rate: `{report['chemistry_kpi']['backmapping_failure_rate']}`",
            (
                "- unsatisfied_donor_acceptor_fixture_count: "
                f"`{report['chemistry_kpi']['unsatisfied_donor_acceptor_fixture_count']}`"
            ),
            f"- unsatisfied_donor_count: `{report['chemistry_kpi']['unsatisfied_donor_count']}`",
            f"- unsatisfied_acceptor_count: `{report['chemistry_kpi']['unsatisfied_acceptor_count']}`",
            f"- chirality_preservation_fixture_count: `{report['chemistry_kpi']['chirality_preservation_fixture_count']}`",
            (
                "- unassigned_chirality_blocked_fixture_count: "
                f"`{report['chemistry_kpi']['unassigned_chirality_blocked_fixture_count']}`"
            ),
            f"- chirality_preservation_ready: `{report['chemistry_kpi']['chirality_preservation_ready']}`",
            f"- ring_validity_fixture_count: `{report['chemistry_kpi']['ring_validity_fixture_count']}`",
            f"- ring_validity_ready: `{report['chemistry_kpi']['ring_validity_ready']}`",
            f"- tautomer_validity_fixture_count: `{report['chemistry_kpi']['tautomer_validity_fixture_count']}`",
            f"- tautomer_validity_ready: `{report['chemistry_kpi']['tautomer_validity_ready']}`",
            f"- protonation_validity_fixture_count: `{report['chemistry_kpi']['protonation_validity_fixture_count']}`",
            f"- protonation_validity_ready: `{report['chemistry_kpi']['protonation_validity_ready']}`",
            "",
            "## Pose Ranking H-Bond Benchmark",
            f"- benchmark_ready: `{report['pose_ranking_hbond_benchmark']['benchmark_ready']}`",
            f"- hbond_recovery_pose_count: `{report['pose_ranking_hbond_benchmark']['hbond_recovery_pose_count']}`",
            f"- hbond_recovery_pose_ids: `{';'.join(report['pose_ranking_hbond_benchmark']['hbond_recovery_pose_ids'])}`",
            (
                "- hbond_recovery_confidence_min: "
                f"`{report['pose_ranking_hbond_benchmark']['hbond_recovery_confidence_min']}`"
            ),
            f"- top1_pose_id: `{report['pose_ranking_hbond_benchmark']['top1_pose_id']}`",
            f"- ranking_order: `{';'.join(report['pose_ranking_hbond_benchmark']['ranking_order'])}`",
            "",
            "## Confidence Calibration Report",
            f"- status: `{report['confidence_calibration_report']['status']}`",
            f"- ready: `{report['confidence_calibration_report']['ready']}`",
            f"- row_count: `{report['confidence_calibration_report']['row_count']}`",
            f"- positive_count: `{report['confidence_calibration_report']['positive_count']}`",
            f"- negative_count: `{report['confidence_calibration_report']['negative_count']}`",
            (
                "- expected_calibration_error: "
                f"`{report['confidence_calibration_report']['expected_calibration_error']}`"
            ),
            f"- brier_score: `{report['confidence_calibration_report']['brier_score']}`",
            "",
            "## Product KPI",
        ]
    )
    for key, value in report["product_kpi"].items():
        if key == "allowlisted_runner_shim_contract" and isinstance(value, dict):
            lines.append(f"- {key}.ready: `{value.get('ready')}`")
            lines.append(f"- {key}.runner_count: `{value.get('runner_count')}`")
            for row in value.get("rows") or []:
                if isinstance(row, dict):
                    lines.append(
                        "- allowlisted_runner: "
                        f"`{row.get('profile_id')}` -> `{row.get('adapter_import')}`, "
                        f"hash_matches=`{row.get('hash_matches')}`"
                    )
        elif isinstance(value, dict):
            lines.append(f"- {key}.ready: `{value.get('ready', '')}`")
        else:
            lines.append(f"- {key}: `{value}`")
    lines.extend(
        [
            "",
            "## ROCm Environment",
        ]
    )
    for key, value in report["rocm_environment_summary"].items():
        lines.append(f"- {key}: `{value}`")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build local AI-MD engine KPI micro-smoke report.")
    parser.add_argument("--profiles-dir", default="config/api_validated_runner_profiles")
    parser.add_argument("--score-only-rows", type=int, default=1000)
    parser.add_argument("--onsps-rows", type=int, default=100)
    parser.add_argument("--residual-rows", type=int, default=10)
    parser.add_argument("--rocm-manifest-json", default=DEFAULT_ROCM_MANIFEST_JSON)
    parser.add_argument("--product-evidence-bundle-json", default=DEFAULT_PRODUCT_EVIDENCE_BUNDLE_JSON)
    parser.add_argument("--product-ci-runtime-gate-json", default=DEFAULT_PRODUCT_CI_RUNTIME_GATE_JSON)
    parser.add_argument("--runtime-scaling-plot", default=DEFAULT_RUNTIME_SCALING_PLOT)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    args = parser.parse_args(argv)

    report = build_report(
        profiles_dir=args.profiles_dir,
        score_only_rows=max(1, int(args.score_only_rows)),
        onsps_rows=max(1, int(args.onsps_rows)),
        residual_rows=max(1, int(args.residual_rows)),
        runtime_scaling_plot_path=args.runtime_scaling_plot,
        rocm_manifest_path=args.rocm_manifest_json,
        product_evidence_bundle_json_path=args.product_evidence_bundle_json,
        product_ci_runtime_gate_json_path=args.product_ci_runtime_gate_json,
    )
    out_json = Path(args.out_json)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    _write_md(Path(args.out_md), report)
    print(json.dumps({"status": report["status"], "out_json": str(out_json), "out_md": str(args.out_md)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

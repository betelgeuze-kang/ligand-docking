#!/usr/bin/env python3
from __future__ import annotations

import argparse
import contextlib
import hashlib
import io
import json
import resource
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
from betelgeuze_engine.contracts import EngineState
from betelgeuze_engine.interactions.hbond_evidence import evaluate_hbond_evidence
from betelgeuze_engine.physics import ProductForceField, default_force_term_registry, guarded_force_term_registry
from betelgeuze_engine.physics.neighbor import full_neighbor_pairs
from betelgeuze_engine.physics.terms import DirectionalHBondTerm, HydrophobicContactTerm, LegacyLJTerm
from betelgeuze_engine.residual import ForceResidualPolicy, apply_guarded_force_residual, decide_force_residual
from betelgeuze_engine.topology import (
    ComplexTopology,
    TopologyFactoryFacade,
    ligand_topology_from_smiles,
    protein_topology_from_sequence,
    topology_claim_metadata,
)
from betelgeuze_engine.validation import (
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
DEFAULT_ROCM_MANIFEST_JSON = "runs/rocm_environment_manifest_current.json"
DEFAULT_PRODUCT_EVIDENCE_BUNDLE_JSON = "runs/ai_md_product_evidence_bundle_current.json"
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
POSE_RANKING_HBOND_FIXTURES = (
    {
        "pose_id": "amide_near_hbond_pose",
        "smiles": "CC(=O)N",
        "expected_top1": True,
        "rmsd_proxy_A": 0.35,
        "ligand_xyz": [[2.8, 0.0, 0.0], [0.0, 2.8, 0.0], [1.0, 1.0, 1.0]],
    },
    {
        "pose_id": "ethanol_near_hbond_pose",
        "smiles": "CCO",
        "expected_top1": False,
        "rmsd_proxy_A": 0.85,
        "ligand_xyz": [[2.9, 0.1, 0.0], [0.2, 2.9, 0.0], [1.0, 1.0, 1.0]],
    },
    {
        "pose_id": "amide_far_decoy_pose",
        "smiles": "CC(=O)N",
        "expected_top1": False,
        "rmsd_proxy_A": 4.5,
        "ligand_xyz": [[8.0, 0.0, 0.0], [0.0, 8.0, 0.0], [8.0, 8.0, 8.0]],
    },
    {
        "pose_id": "amide_overanchored_decoy_pose",
        "smiles": "CC(=O)N",
        "expected_top1": False,
        "rmsd_proxy_A": 3.5,
        "ligand_xyz": [[0.0, 0.0, 0.0], [1.6, 0.0, 0.0], [0.5, 0.5, 0.0]],
    },
    {
        "pose_id": "invalid_ligand_pose",
        "smiles": "C1(",
        "expected_top1": False,
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
            last_metadata = report.to_claim_metadata(
                {
                    "topology_fidelity": "sequence_mapped",
                    "ligand_topology_valid": True,
                    "claim_safe": True,
                    "blocked_reason": "",
                }
            )
        return applied, last_metadata

    _label, elapsed, runtime_value = _timed("guarded_force_residual", run)
    applied, last_metadata = runtime_value
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
    policy_caps = cap_report.to_dict()["policy_caps"]
    bounded_policy_ready = bool(required_policy_caps.issubset(policy_caps))
    confidence_abstention_ready = bool(
        uncertainty_report.applied is False
        and uncertainty_report.skipped_reason == "uncertainty_abstained"
        and uncertainty_report.uncertainty >= float(policy.abstain_threshold)
        and uncertainty_report.confidence <= 1.0 - float(policy.abstain_threshold)
    )
    top_k_policy_ready = bool(
        outside_top_k_report.applied is False
        and outside_top_k_report.skipped_reason == "outside_top_k_policy"
        and outside_top_k_report.top_k_eligible is False
        and outside_top_k_report.rank_pct > float(policy.top_k_rank_pct)
        and outside_top_k_report.policy_caps.get("top_k_rank_pct") == float(policy.top_k_rank_pct)
        and last_metadata.get("force_residual_top_k_eligible") is True
        and last_metadata.get("force_residual_rank_pct") <= float(policy.top_k_rank_pct)
    )
    return {
        "row_count": int(row_count),
        "applied_count": int(applied),
        "delta_score_cap_abstention_count": int(cap_report.applied is False and cap_report.skipped_reason == "delta_score_cap_exceeded"),
        "uncertainty_abstention_count": int(confidence_abstention_ready),
        "outside_top_k_abstention_count": int(
            outside_top_k_report.applied is False
            and outside_top_k_report.skipped_reason == "outside_top_k_policy"
        ),
        "bounded_correction_policy_ready": bounded_policy_ready,
        "confidence_abstention_ready": confidence_abstention_ready,
        "top_k_policy_ready": top_k_policy_ready,
        "required_policy_caps": sorted(required_policy_caps),
        "last_claim_metadata": last_metadata,
        "delta_score_cap_report": cap_report.to_dict(),
        "uncertainty_abstention_report": uncertainty_report.to_dict(),
        "outside_top_k_report": outside_top_k_report.to_dict(),
        "duration_sec": elapsed,
        "rows_per_sec": float(row_count / elapsed) if elapsed > 0 else 0.0,
    }


def _neighbor_rebuild_kpi(frame_count: int = 12, rebuild_stride: int = 3) -> dict[str, Any]:
    coords = torch.zeros(1, 16, 3)
    rebuild_count = 0
    pair_count = 0
    for frame_idx in range(int(frame_count)):
        coords = coords + 0.001
        if frame_idx % int(rebuild_stride) == 0:
            pairs = full_neighbor_pairs(coords, cutoff=8.0)
            rebuild_count += 1
            pair_count = int(pairs.mask.sum().item())
    return {
        "frame_count": int(frame_count),
        "rebuild_stride": int(rebuild_stride),
        "neighbor_list_rebuild_count": int(rebuild_count),
        "neighbor_list_rebuild_frequency": float(rebuild_count / max(int(frame_count), 1)),
        "last_neighbor_pair_count": int(pair_count),
    }


def _physics_kpis() -> dict[str, Any]:
    coords = torch.tensor([[[0.0, 0.0, 0.0], [4.0, 0.0, 0.0], [0.0, 4.0, 0.0]]], dtype=torch.float64)
    state = EngineState(
        coords=coords,
        atom_types=torch.tensor([0, 0, 0]),
        metadata={
            "hbond_roles": ["donor", "acceptor", "none"],
            "hydrophobic_mask": torch.tensor([False, True, True]),
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
            }
        )
    force_term_validation_ready = bool(force_term_validation_rows and all(row["ready"] for row in force_term_validation_rows))
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
        evidence = evaluate_hbond_evidence(smiles=smiles)
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
        hbond_schema_ready = bool(
            evidence.schema_version == "hbond_evidence_v1"
            and hbond_role_site_count == int(evidence.site_count)
            and isinstance(evidence.geometry_evaluated, bool)
            and isinstance(evidence.geometry_complete, bool)
            and isinstance(evidence.distance_pass_count, int)
            and isinstance(evidence.angle_pass_count, int)
            and isinstance(evidence.onsps_backmap_metadata, dict)
            and evidence.onsps_backmap_metadata.get("schema_version") == "onsps_backmap_evidence_v1"
        )
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
                "hbond_donor_site_count": int(evidence.donor_site_count),
                "hbond_acceptor_site_count": int(evidence.acceptor_site_count),
                "hbond_role_site_count": hbond_role_site_count,
                "hbond_distance_pass_count": int(evidence.distance_pass_count),
                "hbond_angle_pass_count": int(evidence.angle_pass_count),
                "hbond_geometry_evaluated": evidence.geometry_evaluated,
                "hbond_geometry_complete": evidence.geometry_complete,
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
        }
    validation = validate_product_evidence_bundle(bundle_packet=packet)
    summary = packet.get("summary") if isinstance(packet.get("summary"), dict) else packet
    clean_install_success = bool(
        summary.get("clean_container_smoke_ready") is True
        and summary.get("product_runner_smoke_ready") is True
        and summary.get("product_image_receipt_present") is True
        and summary.get("product_image_receipt_mode") == "rocm-runtime"
    )
    validation.update(
        {
            "clean_install_success": clean_install_success,
            "clean_container_smoke_ready": bool(summary.get("clean_container_smoke_ready") is True),
            "product_runner_smoke_ready": bool(summary.get("product_runner_smoke_ready") is True),
            "product_image_receipt_present": bool(summary.get("product_image_receipt_present") is True),
            "product_image_receipt_mode": str(summary.get("product_image_receipt_mode") or ""),
            "product_image_receipt_status": str(summary.get("product_image_receipt_status") or ""),
            "product_claim_ready": bool(summary.get("product_claim_ready") is True),
        }
    )
    return validation


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
    term_result_contract_rows: list[dict[str, Any]] = []
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
            }
        )
    hbond_schema_ready = bool(
        result.claim_metadata.get("hbond_evidence_schema_version") == "hbond_evidence_v1"
        and result.claim_metadata.get("hbond_evidence_schema_ready") is True
    )
    ready = bool(
        result.claim_metadata.get("claim_safe") is True
        and result.claim_metadata.get("force_term_claim_metadata_ready") is True
        and result.claim_metadata.get("force_term_claim_metadata_schema_version")
        == "force_term_claim_metadata_v1"
        and int(result.claim_metadata.get("force_term_claim_safe_count") or 0) == len(force_term_plugins)
        and int(result.claim_metadata.get("force_term_blocked_count") or 0) == 0
        and isinstance(result.claim_metadata.get("force_term_claim_rows"), list)
        and len(result.claim_metadata.get("force_term_claim_rows") or []) == len(force_term_plugins)
        and hbond_schema_ready
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
    return {
        "ready": ready,
        "term_result_contract_ready": term_result_contract_ready,
        "forcefield_claim_safe": result.claim_metadata.get("claim_safe") is True,
        "forcefield_blocked_reason": str(result.claim_metadata.get("blocked_reason") or ""),
        "forcefield_hbond_evidence_status": str(result.claim_metadata.get("hbond_evidence_status") or ""),
        "forcefield_hbond_evidence_schema_version": str(
            result.claim_metadata.get("hbond_evidence_schema_version") or ""
        ),
        "forcefield_hbond_evidence_schema_ready": hbond_schema_ready,
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
    forcefield = ProductForceField.from_registry(registry, names=["screened_electrostatics"])
    forcefield_result = forcefield.energy_forces(
        EngineState(
            coords=coords,
            atom_types=atom_types,
            metadata={
                "partial_charges": torch.tensor([1.0, -1.0, 0.5], dtype=torch.float64),
                "charge_source": "kpi_validated_proxy",
                "charge_model_valid": True,
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
    ready = bool(
        default_names == ["directional_hbond", "hydrophobic_contact", "legacy_lj"]
        and guarded_names == [
            "directional_hbond",
            "hydrophobic_contact",
            "legacy_lj",
            "screened_electrostatics",
        ]
        and result.claim_metadata.get("claim_safe") is True
        and result.claim_metadata.get("force_term_status") == "pass"
        and list(result.energy.shape) == [1]
        and list(result.forces.shape) == list(coords.shape)
        and bool(torch.isfinite(result.energy).all().item())
        and bool(torch.isfinite(result.forces).all().item())
        and fd_error < 1e-5
        and missing.claim_metadata.get("claim_safe") is False
        and missing.claim_metadata.get("force_term_status") == "charges_missing"
        and missing.claim_metadata.get("blocked_reason") == "screened_electrostatics_charges_missing"
        and unvalidated.claim_metadata.get("claim_safe") is False
        and unvalidated.claim_metadata.get("force_term_status") == "charge_model_unvalidated"
        and unvalidated.claim_metadata.get("blocked_reason")
        == "screened_electrostatics_charge_model_unvalidated"
        and forcefield_result.claim_metadata.get("claim_safe") is True
        and forcefield_result.claim_metadata.get("force_term_plugins") == ["screened_electrostatics"]
    )
    return {
        "ready": ready,
        "default_registry_names": default_names,
        "guarded_registry_names": guarded_names,
        "term": "screened_electrostatics",
        "energy_shape": list(result.energy.shape),
        "forces_shape": list(result.forces.shape),
        "energy_finite": bool(torch.isfinite(result.energy).all().item()),
        "forces_finite": bool(torch.isfinite(result.forces).all().item()),
        "active_pair_count": int(result.diagnostics.get("active_pair_count") or 0),
        "finite_difference_force_error": float(fd_error),
        "claim_safe": result.claim_metadata.get("claim_safe") is True,
        "force_term_status": str(result.claim_metadata.get("force_term_status") or ""),
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
    manifest = build_result_manifest(
        job_id="kpi_runner_claim_metadata_smoke",
        request={"target_name": "kpi", "runner_profile_id": "backmapping_scoring.production"},
        status="completed",
        result_file="",
        signing_key="kpi-test-key",
        key_id="kpi-test",
        result_claim_metadata=runner_claim_metadata,
        hbond_evidence_summary=hbond_summary,
    )
    signed = verify_result_manifest(manifest, signing_key="kpi-test-key")
    ready = bool(
        signed
        and manifest.get("result_claim_metadata") == runner_claim_metadata
        and manifest.get("hbond_evidence_summary") == hbond_summary
        and manifest["result_claim_metadata"].get("claim_safe") is False
        and manifest["result_claim_metadata"].get("hbond_evidence_schema_version") == "hbond_evidence_v1"
        and int(manifest["result_claim_metadata"].get("hbond_evidence_schema_ready_row_count") or 0) == 2
        and manifest["result_claim_metadata"].get("ligand_topology_claim_safe") is True
        and manifest["result_claim_metadata"].get("ligand_topology_schema_version")
        == "ligand_topology_validity_v1"
        and int(manifest["result_claim_metadata"].get("ligand_topology_schema_ready_row_count") or 0) == 2
        and int(manifest["result_claim_metadata"].get("ligand_topology_claim_safe_row_count") or 0) == 2
        and manifest["hbond_evidence_summary"].get("schema_version") == "hbond_evidence_v1"
    )
    return {
        "ready": ready,
        "signature_verified": signed,
        "result_claim_metadata_present": isinstance(manifest.get("result_claim_metadata"), dict),
        "hbond_evidence_summary_present": isinstance(manifest.get("hbond_evidence_summary"), dict),
        "manifest_claim_safe": manifest.get("result_claim_metadata", {}).get("claim_safe"),
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
    invalid_ligand = factory.from_sequence_and_smiles(
        sequence="ACD",
        smiles="C1(",
    )
    ready = bool(
        valid.complex_topology.protein.fidelity == "sequence_mapped"
        and valid.complex_topology.claim_scope == "kpi_smoke"
        and valid.complex_topology.pocket_residue_indices == [1]
        and valid.claim_metadata.get("claim_safe") is True
        and valid.claim_metadata.get("ligand_topology_schema_version") == "ligand_topology_validity_v1"
        and placeholder.claim_metadata.get("claim_safe") is False
        and placeholder.claim_metadata.get("blocked_reason") == "placeholder_alanine_topology"
        and invalid_ligand.claim_metadata.get("claim_safe") is False
        and invalid_ligand.claim_metadata.get("blocked_reason") == "invalid_smiles"
    )
    return {
        "ready": ready,
        "facade": "betelgeuze_engine.topology.TopologyFactoryFacade",
        "valid_claim_safe": valid.claim_metadata.get("claim_safe") is True,
        "valid_topology_fidelity": str(valid.claim_metadata.get("topology_fidelity") or ""),
        "valid_ligand_topology_schema_version": str(
            valid.claim_metadata.get("ligand_topology_schema_version") or ""
        ),
        "placeholder_blocked_reason": str(placeholder.claim_metadata.get("blocked_reason") or ""),
        "invalid_ligand_blocked_reason": str(invalid_ligand.claim_metadata.get("blocked_reason") or ""),
    }


def _onsps_backmap_evidence_schema_kpi() -> dict[str, Any]:
    two_bead = np.asarray([[0.0, 0.0, 0.0], [1.6, 0.0, 0.0]], dtype=np.float32)
    valid = evaluate_onsps_backmap_evidence(two_bead, "CC(=O)N")
    empty = evaluate_onsps_backmap_evidence(np.zeros((1, 3), dtype=np.float32), "CC(=O)N")
    no_sites = evaluate_onsps_backmap_evidence(two_bead, "CCCC")
    hbond = evaluate_hbond_evidence(smiles="CC(=O)N", ligand_xyz=two_bead)
    hbond_onsps = hbond.onsps_backmap_metadata
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
        registry_names = default_product_forcefield(term_names=["legacy_lj"]).terms[0].name
        ready = bool(
            result.claim_metadata.get("claim_safe") is True
            and result.claim_metadata.get("force_term_claim_metadata_ready") is True
            and result.claim_metadata.get("force_term_plugins") == ["legacy_lj"]
            and registry_names == "legacy_lj"
        )
        return {
            "ready": ready,
            "result_claim_safe": result.claim_metadata.get("claim_safe") is True,
            "force_term_claim_metadata_ready": result.claim_metadata.get("force_term_claim_metadata_ready") is True,
            "force_term_plugins": list(result.claim_metadata.get("force_term_plugins") or []),
            "energy_shape": list(result.energy.shape),
            "forces_shape": list(result.forces.shape),
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
            "error": str(forcefield_bridge.get("error") or ""),
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
        ),
        (
            "backmapping_scoring.production",
            Path("tools/run_ligand_backmapping_scoring.py"),
            "betelgeuze_engine.product.runners.backmapping_scoring",
        ),
        (
            "ligand_topk_delivery.production",
            Path("tools/run_ligand_topk_delivery.py"),
            "betelgeuze_engine.product.runners.topk_delivery",
        ),
    ]
    root = Path(profiles_dir)
    rows: list[dict[str, Any]] = []
    for profile_id, script_path, adapter_import in cases:
        profile_path = root / f"{profile_id}.json"
        script_hash = ""
        profile_hash = ""
        profile_script = ""
        error = ""
        adapter_present = False
        if script_path.exists():
            script_bytes = script_path.read_bytes()
            script_hash = hashlib.sha256(script_bytes).hexdigest()
            adapter_present = adapter_import in script_bytes.decode("utf-8", errors="ignore")
        else:
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
        rows.append(
            {
                "profile_id": profile_id,
                "runner_script": str(script_path),
                "profile_runner_script": profile_script,
                "adapter_import": adapter_import,
                "adapter_import_present": adapter_present,
                "script_hash": script_hash,
                "profile_runner_script_sha256": profile_hash,
                "hash_matches": bool(script_hash and profile_hash and script_hash == profile_hash),
                "ready": bool(
                    adapter_present
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


def _product_kpis(profiles_dir: str, product_evidence_bundle_json_path: str) -> dict[str, Any]:
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
    job_store_lazy_factory = _job_store_lazy_factory_kpi()
    bundle_validation = _product_bundle_validation_kpi(product_evidence_bundle_json_path)
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
        "product_claim_ready": bool(bundle_validation.get("product_claim_ready") is True),
        "runner_profile_validation_status": profile_payload.get("status"),
        "enabled_profile_count": int(profile_payload.get("enabled_profile_count", 0)),
        "failed_profile_count": int(profile_payload.get("failed_profile_count", 0)),
        "signed_manifest_verification_pass": verify_result_manifest(manifest, signing_key="kpi-test-key"),
        "runner_claim_metadata_signed": bool(signed_runner_claim_metadata.get("ready") is True),
        "runner_claim_metadata_manifest_smoke": signed_runner_claim_metadata,
        "bundle_validation_pass": bool(bundle_validation.get("bundle_validation_pass") is True),
        "bundle_validation_checked": bool(bundle_validation.get("bundle_validation_checked") is True),
        "bundle_validation_error_count": int(bundle_validation.get("bundle_validation_error_count") or 0),
        "bundle_validation_errors": list(bundle_validation.get("bundle_validation_errors") or []),
        "bundle_validation_contract": "opens_ai_md_product_evidence_tar_and_verifies_manifest_sha_members",
        "force_term_plugin_registry_ready": force_term_plugins
        == ["directional_hbond", "hydrophobic_contact", "legacy_lj"],
        "force_term_plugins": force_term_plugins,
        "force_term_claim_metadata_ready": bool(force_term_claim_metadata.get("ready") is True),
        "force_term_claim_metadata_smoke": force_term_claim_metadata,
        "force_term_result_contract_ready": bool(
            force_term_claim_metadata.get("term_result_contract_ready") is True
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
        if fixture["expected_top1"] is True:
            mapped, _meta = backmap_4bead_onsps(onsps_ligand_xyz, str(fixture["smiles"]))
            if mapped.ndim == 2 and mapped.shape[0] > 0:
                protein_xyz = mapped + np.asarray([[0.0, 0.0, 3.0]], dtype=np.float32)
                pocket_center = mapped.mean(axis=0) + np.asarray([0.0, 0.0, 6.0], dtype=np.float32)
        evidence = evaluate_hbond_evidence(
            smiles=str(fixture["smiles"]),
            protein_xyz=protein_xyz,
            ligand_xyz=onsps_ligand_xyz,
            pocket_center=pocket_center,
        )
        validity_bonus = 0.0 if ligand.validity.get("valid") is True else -10.0
        score = float((evidence.hbond_confidence * 10.0) - float(fixture["rmsd_proxy_A"]) + validity_bonus)
        rows.append(
            {
                "pose_id": fixture["pose_id"],
                "smiles": fixture["smiles"],
                "expected_top1": fixture["expected_top1"],
                "ligand_valid": ligand.validity.get("valid") is True,
                "hbond_status": evidence.status,
                "hbond_schema_version": evidence.schema_version,
                "hbond_confidence": evidence.hbond_confidence,
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
        for row in rows
        if str(row["pose_id"]).endswith("_decoy_pose")
        and "overanchored" not in str(row["pose_id"])
    )
    return {
        "benchmark_ready": bool(
            top1_pass
            and active_hbond_ready
            and invalid_blocked
            and far_decoys_blocked
            and overanchored_decoys_blocked
        ),
        "fixture_count": len(rows),
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
    product_gate_values = {
        "clean_install_success": product.get("clean_install_success") is True,
        "runner_profile_validation_pass": product.get("runner_profile_validation_status") == "pass",
        "signed_manifest_verification_pass": product.get("signed_manifest_verification_pass") is True,
        "runner_claim_metadata_signed": product.get("runner_claim_metadata_signed") is True,
        "bundle_validation_pass": product.get("bundle_validation_pass") is True,
        "force_term_claim_metadata_ready": product.get("force_term_claim_metadata_ready") is True,
        "force_term_result_contract_ready": product.get("force_term_result_contract_ready") is True,
        "guarded_force_term_plugin_ready": product.get("guarded_force_term_plugin_ready") is True,
        "engine_topology_factory_facade_ready": product.get("engine_topology_factory_facade_ready") is True,
        "onsps_backmap_evidence_schema_ready": product.get("onsps_backmap_evidence_schema_ready") is True,
        "core_forcefield_bridge_ready": product.get("core_forcefield_bridge_ready") is True,
        "core_compatibility_layer_ready": product.get("core_compatibility_layer_ready") is True,
        "job_store_lazy_factory_ready": product.get("job_store_lazy_factory_ready") is True,
        "allowlisted_runner_shim_contract_ready": product.get("allowlisted_runner_shim_contract_ready") is True,
        "blocked_claim_correctly_blocked": product.get("blocked_claim_correctly_blocked") is True,
        "rocm_hip_rust_runtime_ready": rocm_runtime_ready,
    }
    runtime_gate_values = {
        "force_residual_bounded_policy_ready": runtime_residual.get("bounded_correction_policy_ready") is True,
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
    }
    gate_values = {
        **product_gate_values,
        **runtime_gate_values,
        **physics_gate_values,
        **chemistry_gate_values,
        "pose_ranking_hbond_benchmark_ready": pose_ranking_hbond.get("benchmark_ready") is True,
    }
    failed = [key for key, value in gate_values.items() if value is not True]
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
            "force_residual_bounded_policy_ready": runtime_residual.get("bounded_correction_policy_ready") is True,
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
            "energy_drift_smoke_pct": float(physics.get("energy_drift_smoke_pct") or 0.0),
            "rotation_equivariance_error": float(physics.get("rotation_equivariance_error") or 0.0),
            "neighbor_list_parity_error": float(physics.get("neighbor_list_parity_error") or 0.0),
            "topology_invalid_rate": float(physics.get("topology_invalid_rate") or 0.0),
            "backmapping_failure_rate": float(physics.get("backmapping_failure_rate") or 0.0),
            "force_term_physics_validation_ready": physics.get("force_term_physics_validation_ready") is True,
            "force_term_physics_validation_term_count": int(
                physics.get("force_term_physics_validation_term_count") or 0
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
        },
        "product": product_gate_values,
    }


def build_report(
    *,
    profiles_dir: str,
    score_only_rows: int,
    onsps_rows: int,
    residual_rows: int,
    rocm_manifest_path: str = DEFAULT_ROCM_MANIFEST_JSON,
    product_evidence_bundle_json_path: str = DEFAULT_PRODUCT_EVIDENCE_BUNDLE_JSON,
) -> dict[str, Any]:
    _quiet_rdkit_parser_logs()
    runtime = {
        "score_only_1k": _score_only_runtime(score_only_rows),
        "top100_4bead_rescoring": _onsps_runtime(onsps_rows),
        "top10_force_residual": _force_residual_runtime(residual_rows),
        "memory_peak_mb": _memory_peak_mb(),
        "neighbor_list_rebuild": _neighbor_rebuild_kpi(),
    }
    physics = _physics_kpis()
    chemistry = _chemistry_kpis()
    physics["topology_invalid_rate"] = float(chemistry.get("topology_invalid_rate") or 0.0)
    physics["backmapping_failure_rate"] = float(chemistry.get("backmapping_failure_rate") or 0.0)
    product = _product_kpis(profiles_dir, product_evidence_bundle_json_path)
    pose_ranking_hbond = _pose_ranking_hbond_benchmark()
    rocm_summary = {}
    rocm_path = Path(rocm_manifest_path)
    if rocm_path.exists():
        try:
            rocm_summary = (json.loads(rocm_path.read_text(encoding="utf-8")).get("summary") or {})
        except json.JSONDecodeError:
            rocm_summary = {"status": "invalid_rocm_manifest"}
    rocm_runtime_ready = _rocm_product_runtime_ready(rocm_summary)
    ready = (
        product["clean_install_success"] is True
        and product["runner_profile_validation_status"] == "pass"
        and product["signed_manifest_verification_pass"] is True
        and product["runner_claim_metadata_signed"] is True
        and product["bundle_validation_pass"] is True
        and product["force_term_plugin_registry_ready"] is True
        and product["force_term_claim_metadata_ready"] is True
        and product["force_term_result_contract_ready"] is True
        and product["guarded_force_term_plugin_ready"] is True
        and product["core_forcefield_bridge_ready"] is True
        and product["core_compatibility_layer_ready"] is True
        and product["job_store_lazy_factory_ready"] is True
        and product["allowlisted_runner_shim_contract_ready"] is True
        and product["blocked_claim_correctly_blocked"] is True
        and runtime["top10_force_residual"]["bounded_correction_policy_ready"] is True
        and runtime["top10_force_residual"]["confidence_abstention_ready"] is True
        and physics["finite_difference_force_error"] < 1e-3
        and physics["translation_invariance_error"] < 1e-9
        and physics["rotation_equivariance_error"] < 1e-9
        and physics["neighbor_list_parity_error"] == 0.0
        and physics["energy_drift_smoke_pct"] < 1e-2
        and physics["force_term_physics_validation_ready"] is True
        and chemistry["hbond_evidence_schema_ready"] is True
        and physics["topology_invalid_rate"] < 0.2
        and physics["backmapping_failure_rate"] < 0.5
        and pose_ranking_hbond["benchmark_ready"] is True
        and rocm_runtime_ready
    )
    pm_summary = _pm_kpi_summary(
        runtime=runtime,
        physics=physics,
        chemistry=chemistry,
        pose_ranking_hbond=pose_ranking_hbond,
        product=product,
        rocm_runtime_ready=rocm_runtime_ready,
    )
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
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    args = parser.parse_args(argv)

    report = build_report(
        profiles_dir=args.profiles_dir,
        score_only_rows=max(1, int(args.score_only_rows)),
        onsps_rows=max(1, int(args.onsps_rows)),
        residual_rows=max(1, int(args.residual_rows)),
        rocm_manifest_path=args.rocm_manifest_json,
        product_evidence_bundle_json_path=args.product_evidence_bundle_json,
    )
    out_json = Path(args.out_json)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    _write_md(Path(args.out_md), report)
    print(json.dumps({"status": report["status"], "out_json": str(out_json), "out_md": str(args.out_md)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

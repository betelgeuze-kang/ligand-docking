from __future__ import annotations

import hashlib
import json
import tarfile
from pathlib import Path

from betelgeuze_engine.validation import build_confidence_calibration_report
from tools.product import build_ai_md_product_evidence_bundle as mod


def _write(path: Path, payload: str = "artifact\n") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(payload, encoding="utf-8")
    return path


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _runner_no_core_imports_smoke(*, ready: bool = True) -> dict:
    runners = [
        "tools/run_ligand_htvs_pipeline.py",
        "tools/run_ligand_backmapping_scoring.py",
        "tools/run_ligand_topk_delivery.py",
        "betelgeuze_engine/product/runners/htvs_pipeline.py",
        "betelgeuze_engine/product/runners/backmapping_scoring.py",
        "betelgeuze_engine/product/runners/topk_delivery.py",
        "tools/product/run_ligand_htvs_pipeline.py",
        "tools/product/run_ligand_backmapping_scoring.py",
        "tools/product/run_ligand_topk_delivery.py",
    ]
    return {
        "ready": ready,
        "row_count": len(runners) if ready else 0,
        "legacy_core_import_violation_count": 0 if ready else 1,
        "rows": [
            {
                "runner": runner,
                "exists": True,
                "legacy_core_import_violation_count": 0,
                "legacy_core_import_violations": [],
                "ready": True,
            }
            for runner in runners
        ] if ready else [],
    }


def _topk_delivery_engine_owned_smoke(*, ready: bool = True) -> dict:
    return {
        "ready": ready,
        "engine_module": "betelgeuze_engine.product.runners.topk_delivery",
        "engine_path": "betelgeuze_engine/product/runners/topk_delivery.py",
        "compatibility_path": "tools/product/run_ligand_topk_delivery.py",
        "engine_required_missing": [] if ready else ["def build_delivery("],
        "engine_forbidden_present": [] if ready else ['import_module("tools.product.run_ligand_topk_delivery")'],
        "compatibility_required_missing": [],
        "compatibility_self_implementation_present": False,
        "runtime_identity_ready": ready,
        "runtime_error": "",
        "claim_metadata_ready": ready,
        "claim_metadata_schema_version": "topk_delivery_claim_metadata_v1" if ready else "",
        "claim_metadata_claim_safe": True if ready else False,
        "claim_metadata_blocked_reason": "",
        "claim_metadata_physical_accuracy_claim": False,
        "claim_metadata_error": "",
    }


def _backmapping_scoring_engine_owned_smoke(*, ready: bool = True) -> dict:
    return {
        "ready": ready,
        "engine_module": "betelgeuze_engine.product.runners.backmapping_scoring",
        "engine_path": "betelgeuze_engine/product/runners/backmapping_scoring.py",
        "compatibility_path": "tools/product/run_ligand_backmapping_scoring.py",
        "engine_required_missing": [] if ready else ["def _frame_mmpbsa_proxy("],
        "engine_forbidden_present": [] if ready else ['import_module("tools.product.run_ligand_backmapping_scoring")'],
        "compatibility_required_missing": [],
        "compatibility_self_implementation_present": False,
        "runtime_identity_ready": ready,
        "runtime_error": "",
    }


def _htvs_pipeline_engine_owned_smoke(*, ready: bool = True) -> dict:
    return {
        "ready": ready,
        "engine_module": "betelgeuze_engine.product.runners.htvs_pipeline",
        "engine_path": "betelgeuze_engine/product/runners/htvs_pipeline.py",
        "compatibility_path": "tools/product/run_ligand_htvs_pipeline.py",
        "engine_required_missing": [] if ready else ["def run_pipeline("],
        "engine_forbidden_present": [] if ready else ['import_module("tools.product.run_ligand_htvs_pipeline")'],
        "compatibility_required_missing": [],
        "compatibility_self_implementation_present": False,
        "runtime_identity_ready": ready,
        "runtime_error": "",
    }


def _product_runner_engine_owned_smoke(*, ready: bool = True) -> dict:
    rows = [
        {
            "runner_id": "ligand_htvs_pipeline_default",
            "runner_kind": "ligand_htvs_pipeline",
            "engine_module": "betelgeuze_engine.product.runners.htvs_pipeline",
        },
        {
            "runner_id": "backmapping_scoring.production",
            "runner_kind": "ligand_backmapping_scoring",
            "engine_module": "betelgeuze_engine.product.runners.backmapping_scoring",
        },
        {
            "runner_id": "ligand_topk_delivery.production",
            "runner_kind": "ligand_topk_delivery",
            "engine_module": "betelgeuze_engine.product.runners.topk_delivery",
        },
    ]
    for row in rows:
        row.update(
            {
                "ready": ready,
                "runtime_identity_ready": ready,
                "compatibility_self_implementation_present": False,
                "engine_required_missing": [],
                "engine_forbidden_present": [],
                "runtime_error": "",
            }
        )
    return {
        "ready": ready,
        "runner_count": 3 if ready else 0,
        "engine_owned_runner_count": 3 if ready else 0,
        "contract": "all_product_runners_are_engine_owned_with_compatibility_shims",
        "rows": rows if ready else [],
    }


def _chemistry_kpi_packet(*, ready: bool = True) -> dict:
    fixtures = [
        "ethanol",
        "amide",
        "tertiary_amine",
        "carboxylate",
        "phosphate",
        "heteroaryl_nitrogen",
        "chiral_lactic_acid",
        "unassigned_chiral_lactic_acid",
        "aromatic_ring",
        "protonated_amine",
        "keto_tautomer_smoke",
        "invalid_smiles",
    ]
    rows = []
    for fixture in fixtures:
        row = {
            "fixture": fixture,
            "hbond_schema_ready": ready,
            "hbond_threshold_schema_ready": ready,
            "hbond_pair_schema_ready": ready,
            "hbond_geometry_flags_ready": ready,
            "hbond_geometry_evaluated": ready,
            "hbond_geometry_complete": ready,
            "hbond_distance_pass_count": 1 if ready else 0,
            "hbond_angle_pass_count": 1 if ready else 0,
            "ligand_validity_schema_ready": ready,
        }
        if ready:
            row.update(
                {
                    "ligand_topology_claim_safe": True,
                    "ligand_validity_blockers": [],
                    "chiral_center_count": 0,
                    "specified_chiral_center_count": 0,
                    "unassigned_chiral_center_count": 0,
                    "chirality_status": "not_applicable",
                    "ring_atom_count": 0,
                    "ring_status": "not_applicable",
                    "formal_charge_sum": 0,
                    "protonation_status": "neutral_state_parsed",
                    "tautomer_fixture_valid": False,
                    "tautomer_status": "connectivity_parsed_tautomer_not_canonicalized",
                }
            )
            if fixture == "chiral_lactic_acid":
                row.update({"chiral_center_count": 1, "specified_chiral_center_count": 1, "chirality_status": "specified"})
            elif fixture == "unassigned_chiral_lactic_acid":
                row.update(
                    {
                        "ligand_topology_claim_safe": False,
                        "ligand_validity_blockers": ["unassigned_ligand_chirality"],
                        "chiral_center_count": 1,
                        "unassigned_chiral_center_count": 1,
                        "chirality_status": "unassigned_chiral_centers",
                    }
                )
            elif fixture == "aromatic_ring":
                row.update({"ring_atom_count": 6, "ring_status": "present"})
            elif fixture == "protonated_amine":
                row.update({"formal_charge_sum": 1, "protonation_status": "charged_state_parsed"})
            elif fixture == "keto_tautomer_smoke":
                row.update({"tautomer_fixture_valid": True})
        rows.append(row)
    if not ready:
        rows = []
    fixture_count = len(rows)
    return {
        "fixture_count": fixture_count,
        "hbond_evidence_schema_ready": ready,
        "hbond_evidence_schema_ready_count": fixture_count if ready else 0,
        "ligand_topology_validity_schema_ready": ready,
        "ligand_topology_validity_schema_ready_count": fixture_count if ready else 0,
        "hbond_donor_site_count": 4 if ready else 0,
        "hbond_acceptor_site_count": 5 if ready else 0,
        "hbond_geometry_evaluated_fixture_count": fixture_count if ready else 0,
        "hbond_geometry_complete_fixture_count": fixture_count if ready else 0,
        "hbond_recovery_fixture_count": 5 if ready else 0,
        "unsatisfied_donor_acceptor_fixture_count": 1 if ready else 0,
        "unsatisfied_donor_count": 1 if ready else 0,
        "unsatisfied_acceptor_count": 1 if ready else 0,
        "chirality_preservation_ready": ready,
        "chirality_preservation_fixture_count": 1 if ready else 0,
        "unassigned_chirality_blocked_fixture_count": 1 if ready else 0,
        "ring_validity_ready": ready,
        "ring_validity_fixture_count": 1 if ready else 0,
        "tautomer_validity_ready": ready,
        "tautomer_validity_fixture_count": 1 if ready else 0,
        "protonation_validity_ready": ready,
        "protonation_validity_fixture_count": 1 if ready else 0,
        "backmap_evaluable_fixture_count": 6 if ready else 0,
        "backmap_claim_safe_fixture_count": 5 if ready else 0,
        "backmapping_failure_rate": 0.0 if ready else 1.0,
        "rows": rows,
    }


def _hbond_recovery_benchmark_packet(*, ready: bool = True) -> dict:
    rows = [
        {
            "pose_id": "active_hbond_recovered_pose",
            "benchmark_role": "active_recovery_pose",
            "schema_version": "hbond_recovery_benchmark_v1",
            "hbond_claim_safe": True,
            "hbond_blocked_reason": "",
            "hbond_unsatisfied_total_count": 0,
            "overanchoring_flag": False,
            "benchmark_contract_pass": True,
        },
        {
            "pose_id": "unsatisfied_donor_acceptor_pose",
            "benchmark_role": "unsatisfied_donor_pose",
            "schema_version": "hbond_recovery_benchmark_v1",
            "hbond_claim_safe": False,
            "hbond_blocked_reason": "missing_expected_anchor",
            "hbond_unsatisfied_total_count": 1,
            "overanchoring_flag": False,
            "benchmark_contract_pass": True,
        },
        {
            "pose_id": "amide_overanchored_decoy_pose",
            "benchmark_role": "overanchored_decoy_pose",
            "schema_version": "hbond_recovery_benchmark_v1",
            "hbond_claim_safe": False,
            "hbond_blocked_reason": "overanchored_decoy",
            "hbond_unsatisfied_total_count": 2,
            "overanchoring_flag": True,
            "benchmark_contract_pass": True,
        },
    ] if ready else []
    return {
        "ready": ready,
        "status": "hbond_recovery_benchmark_ready" if ready else "blocked_hbond_recovery_benchmark",
        "summary": {
            "schema_version": "hbond_recovery_benchmark_v1",
            "ready": ready,
            "fixture_count": len(rows),
            "benchmark_contract_pass_count": len(rows) if ready else 0,
            "hbond_recovery_present": ready,
            "hbond_recovery_pose_count": 1 if ready else 0,
            "unsatisfied_donor_acceptor_detected": ready,
            "unsatisfied_donor_acceptor_pose_count": 2 if ready else 0,
            "overanchored_decoys_blocked": ready,
            "overanchored_decoy_pose_count": 1 if ready else 0,
        },
        "rows": rows,
        "claim_metadata": {
            "claim_safe": False,
            "blocked_reason": (
                "hbond_recovery_benchmark_not_product_claim_promoted"
                if ready
                else "hbond_recovery_benchmark_not_ready"
            ),
        },
    }


def _force_term_physics_validation_packet(*, ready: bool = True) -> dict:
    thresholds = {
        "finite_difference_force_error_max": 1e-4,
        "translation_invariance_error_max": 1e-9,
        "rotation_equivariance_error_max": 1e-9,
        "energy_drift_smoke_pct_max": 5e-2,
    }
    rows = [
        {
            "term": term,
            "ready": ready,
            "status": "pass" if ready else "blocked",
            "active_pair_count": 1,
            "finite_difference_force_error": 1e-7 if ready else 1.0,
            "translation_invariance_error": 0.0 if ready else 1.0,
            "rotation_equivariance_error": 0.0 if ready else 1.0,
            "energy_drift_smoke_pct": 1e-4 if ready else 1.0,
            "claim_safe": ready,
            "force_term_status": "pass" if ready else "blocked",
            "blocked_reason": "" if ready else "physics_validation_failed",
            "hydrophobic_contact_evidence_schema_version": (
                "hydrophobic_contact_evidence_v1" if term == "hydrophobic_contact" and ready else ""
            ),
            "hydrophobic_contact_evidence_schema_ready": (
                term == "hydrophobic_contact" and ready
            ),
            "hydrophobic_contact_active_pair_count": 1 if term == "hydrophobic_contact" and ready else 0,
        }
        for term in ("directional_hbond", "hydrophobic_contact", "legacy_lj")
    ] if ready else []
    return {
        "thresholds": thresholds,
        "rows": rows,
        "term_count": len(rows),
        "claim_safe_count": sum(1 for row in rows if row["claim_safe"] is True),
        "finite_difference_max_error": max(
            (row["finite_difference_force_error"] for row in rows),
            default=0.0,
        ),
        "translation_invariance_max_error": max(
            (row["translation_invariance_error"] for row in rows),
            default=0.0,
        ),
        "rotation_equivariance_max_error": max(
            (row["rotation_equivariance_error"] for row in rows),
            default=0.0,
        ),
        "energy_drift_max_pct": max(
            (row["energy_drift_smoke_pct"] for row in rows),
            default=0.0,
        ),
    }


def _kpi_packet(
    *,
    ready: bool,
    runner_claim_metadata_signed: bool = True,
    force_residual_summary_signed: bool = True,
    force_term_claim_metadata_ready: bool = True,
    force_term_claim_metadata_schema_ready: bool = True,
    force_term_result_contract_ready: bool = True,
    guarded_force_term_plugin_ready: bool = True,
    onsps_backmap_evidence_schema_ready: bool = True,
    core_forcefield_bridge_ready: bool = True,
    core_compatibility_layer_ready: bool = True,
    job_store_lazy_factory_ready: bool = True,
    allowlisted_runner_shim_contract_ready: bool = True,
    force_residual_bounded_policy_ready: bool = True,
    force_residual_observed_caps_ready: bool = True,
    force_residual_contract_ready: bool = True,
    force_residual_confidence_abstention_ready: bool = True,
    force_term_physics_validation_ready: bool = True,
    force_term_physics_validation_claim_safe_ready: bool = True,
    manifest_ligand_topology_claim_safe: bool = True,
    chemistry_pm_gates_ready: bool = True,
    pose_ranking_hbond_benchmark_ready: bool = True,
) -> dict:
    force_term_rows = [
        {
            "force_term_name": "directional_hbond",
            "force_term_status": "pass",
            "claim_safe": True,
            "blocked_reason": "",
            "hbond_evidence_schema_version": "hbond_evidence_v1",
            "hbond_evidence_schema_ready": True,
        },
        {
            "force_term_name": "hydrophobic_contact",
            "force_term_status": "pass",
            "claim_safe": True,
            "blocked_reason": "",
            "hydrophobic_contact_evidence_schema_version": "hydrophobic_contact_evidence_v1",
            "hydrophobic_contact_evidence_schema_ready": True,
            "hydrophobic_contact_mask_present": True,
            "hydrophobic_contact_mask_count": 2,
            "hydrophobic_contact_active_pair_count": 1,
            "hydrophobic_contact_contact_distance_A": 4.5,
            "hydrophobic_contact_energy_model": "bounded_quadratic_contact",
        },
        {
            "force_term_name": "legacy_lj",
            "force_term_status": "pass",
            "claim_safe": True,
            "blocked_reason": "",
        },
    ] if force_term_claim_metadata_schema_ready else []
    force_term_contract_rows = [
        {
            "term": "directional_hbond",
            "ready": force_term_result_contract_ready,
            "energy_shape": [1],
            "forces_shape": [1, 3, 3],
            "diagnostics_keys_present": True,
            "claim_metadata_keys_present": True,
            "energy_finite": True,
            "forces_finite": True,
            "diagnostics_term": "directional_hbond",
            "diagnostics_status": "pass",
            "claim_force_term_name": "directional_hbond",
            "claim_force_term_status": "pass",
            "error": "",
        },
        {
            "term": "hydrophobic_contact",
            "ready": force_term_result_contract_ready,
            "energy_shape": [1],
            "forces_shape": [1, 3, 3],
            "diagnostics_keys_present": True,
            "claim_metadata_keys_present": True,
            "energy_finite": True,
            "forces_finite": True,
            "diagnostics_term": "hydrophobic_contact",
            "diagnostics_status": "pass",
            "claim_force_term_name": "hydrophobic_contact",
            "claim_force_term_status": "pass",
            "error": "",
        },
        {
            "term": "legacy_lj",
            "ready": force_term_result_contract_ready,
            "energy_shape": [1],
            "forces_shape": [1, 3, 3],
            "diagnostics_keys_present": True,
            "claim_metadata_keys_present": True,
            "energy_finite": True,
            "forces_finite": True,
            "diagnostics_term": "legacy_lj",
            "diagnostics_status": "pass",
            "claim_force_term_name": "legacy_lj",
            "claim_force_term_status": "pass",
            "error": "",
        },
    ] if force_term_claim_metadata_schema_ready else []
    pose_rows = [
        {
            "pose_id": "amide_near_hbond_pose",
            "benchmark_role": "hbond_recovery_pose",
            "expected_claim_safe": True,
            "expected_hbond_status": "pass",
            "expected_blocked_reason": "",
            "hbond_claim_safe": True,
            "hbond_status": "pass",
            "hbond_blocked_reason": "",
            "hbond_geometry_evaluated": True,
            "hbond_geometry_complete": True,
            "hbond_distance_pass_count": 2,
            "hbond_angle_pass_count": 2,
            "overanchoring_flag": False,
            "unsatisfied_donor_count": 0,
            "unsatisfied_acceptor_count": 0,
            "benchmark_contract_checks": {"claim_safe_matches": True},
            "benchmark_contract_pass": True,
        },
        {
            "pose_id": "ethanol_near_hbond_pose",
            "benchmark_role": "unsatisfied_donor_pose",
            "expected_claim_safe": False,
            "expected_hbond_status": "review",
            "expected_blocked_reason": "missing_expected_anchor",
            "hbond_claim_safe": False,
            "hbond_status": "review",
            "hbond_blocked_reason": "missing_expected_anchor",
            "hbond_geometry_evaluated": True,
            "hbond_geometry_complete": True,
            "hbond_distance_pass_count": 0,
            "hbond_angle_pass_count": 0,
            "overanchoring_flag": False,
            "unsatisfied_donor_count": 1,
            "unsatisfied_acceptor_count": 0,
            "benchmark_contract_checks": {"claim_safe_matches": True},
            "benchmark_contract_pass": True,
        },
        {
            "pose_id": "amide_far_decoy_pose",
            "benchmark_role": "far_decoy_pose",
            "expected_claim_safe": False,
            "expected_hbond_status": "review",
            "expected_blocked_reason": "missing_expected_anchor",
            "hbond_claim_safe": False,
            "hbond_status": "review",
            "hbond_blocked_reason": "missing_expected_anchor",
            "hbond_geometry_evaluated": True,
            "hbond_geometry_complete": True,
            "hbond_distance_pass_count": 0,
            "hbond_angle_pass_count": 0,
            "overanchoring_flag": False,
            "unsatisfied_donor_count": 1,
            "unsatisfied_acceptor_count": 1,
            "benchmark_contract_checks": {"claim_safe_matches": True},
            "benchmark_contract_pass": True,
        },
        {
            "pose_id": "amide_overanchored_decoy_pose",
            "benchmark_role": "overanchored_decoy_pose",
            "expected_claim_safe": False,
            "expected_hbond_status": "review",
            "expected_blocked_reason": "overanchored_decoy",
            "hbond_claim_safe": False,
            "hbond_status": "review",
            "hbond_blocked_reason": "overanchored_decoy",
            "hbond_geometry_evaluated": True,
            "hbond_geometry_complete": True,
            "hbond_distance_pass_count": 0,
            "hbond_angle_pass_count": 0,
            "overanchoring_flag": True,
            "unsatisfied_donor_count": 1,
            "unsatisfied_acceptor_count": 1,
            "benchmark_contract_checks": {"claim_safe_matches": True},
            "benchmark_contract_pass": True,
        },
        {
            "pose_id": "amide_delta_backmap_yellow_band_pose",
            "benchmark_role": "delta_backmap_yellow_band_pose",
            "expected_claim_safe": False,
            "expected_hbond_status": "review",
            "expected_blocked_reason": "delta_backmap_yellow_band",
            "hbond_claim_safe": False,
            "hbond_status": "review",
            "hbond_blocked_reason": "delta_backmap_yellow_band",
            "hbond_geometry_evaluated": True,
            "hbond_geometry_complete": True,
            "hbond_distance_pass_count": 2,
            "hbond_angle_pass_count": 2,
            "overanchoring_flag": False,
            "unsatisfied_donor_count": 0,
            "unsatisfied_acceptor_count": 0,
            "hbond_delta_backmap": 3.0,
            "hbond_delta_backmap_max": 2.5,
            "hbond_delta_backmap_evaluated": True,
            "hbond_delta_backmap_yellow_band": True,
            "benchmark_contract_checks": {"claim_safe_matches": True},
            "benchmark_contract_pass": True,
        },
        {
            "pose_id": "invalid_ligand_pose",
            "benchmark_role": "invalid_ligand_pose",
            "expected_claim_safe": False,
            "expected_hbond_status": "invalid_smiles",
            "expected_blocked_reason": "invalid_smiles",
            "hbond_claim_safe": False,
            "hbond_status": "invalid_smiles",
            "hbond_blocked_reason": "invalid_smiles",
            "hbond_geometry_evaluated": False,
            "hbond_geometry_complete": False,
            "hbond_distance_pass_count": 0,
            "hbond_angle_pass_count": 0,
            "overanchoring_flag": False,
            "unsatisfied_donor_count": 0,
            "unsatisfied_acceptor_count": 0,
            "benchmark_contract_checks": {"claim_safe_matches": True},
            "benchmark_contract_pass": True,
        },
    ] if pose_ranking_hbond_benchmark_ready else []
    for row in pose_rows:
        row.update(
            {
                "hbond_schema_ready": True,
                "hbond_threshold_schema_ready": True,
                "hbond_pair_schema_ready": True,
                "hbond_geometry_flags_ready": True,
                "hbond_delta_backmap": row.get("hbond_delta_backmap", 0.0),
                "hbond_delta_backmap_max": row.get("hbond_delta_backmap_max", 2.5),
                "hbond_delta_backmap_evaluated": row.get("hbond_delta_backmap_evaluated", False),
                "hbond_delta_backmap_yellow_band": row.get("hbond_delta_backmap_yellow_band", False),
                "hbond_confidence": {
                    "amide_near_hbond_pose": 1.0,
                    "amide_delta_backmap_yellow_band_pose": 0.4,
                }.get(str(row.get("pose_id") or ""), 0.0),
            }
        )
    confidence_calibration = build_confidence_calibration_report(pose_rows)
    pose_roles = sorted({str(row["benchmark_role"]) for row in pose_rows})
    ranking_order = (
        ["amide_near_hbond_pose"] + [row["pose_id"] for row in pose_rows if row["pose_id"] != "amide_near_hbond_pose"]
        if pose_ranking_hbond_benchmark_ready
        else []
    )
    hbond_recovery_benchmark = _hbond_recovery_benchmark_packet(
        ready=pose_ranking_hbond_benchmark_ready
    )
    force_term_physics = _force_term_physics_validation_packet(
        ready=force_term_physics_validation_ready
        and force_term_physics_validation_claim_safe_ready
    )
    chemistry_kpi = _chemistry_kpi_packet(ready=chemistry_pm_gates_ready)
    return {
        "packet_type": "ai_md_engine_kpi_report",
        "status": "ai_md_engine_kpi_report_ready" if ready else "blocked_ai_md_engine_kpi_report",
        "report_ready": ready,
        "product_kpi": {
            "runner_claim_metadata_signed": runner_claim_metadata_signed,
            "signed_manifest_verification_pass": runner_claim_metadata_signed,
            "bundle_validation_pass": ready,
            "product_claim_ready": ready,
            "release_claim_ready": False,
            "release_claim_blocked_reason": "product_ci_runtime_gate_not_ready",
            "product_ci_runtime_gate_present": False,
            "product_ci_runtime_gate_ready": False,
            "product_ci_runtime_gate_status": "",
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
            "product_ci_latest_github_actions_record_kst_date": "",
            "product_ci_workflow_dispatch_executed": False,
            "product_ci_external_state_mutated": False,
            "clean_install_missing_requirement_count": 0,
            "clean_install_missing_requirements": [],
            "product_image_preflight_blocker_codes": [],
            "clean_container_missing_requirement_count": 0,
            "clean_container_missing_requirements": [],
            "source_artifacts_fresh": ready,
            "source_artifact_fresh_count": 4 if ready else 0,
            "source_artifact_stale_count": 0,
            "source_artifact_stale_ids": [],
            "enabled_profile_count": 3 if ready else 0,
            "failed_profile_count": 0 if ready else 1,
            "runner_profile_validation_pass": ready,
            "runner_claim_metadata_manifest_smoke": {
                "ready": runner_claim_metadata_signed,
                "manifest_ligand_topology_valid": manifest_ligand_topology_claim_safe,
                "manifest_ligand_topology_claim_safe": manifest_ligand_topology_claim_safe,
                "manifest_ligand_topology_schema_version": "ligand_topology_validity_v1"
                if manifest_ligand_topology_claim_safe
                else "",
                "manifest_ligand_topology_schema_ready_row_count": 2
                if manifest_ligand_topology_claim_safe
                else 0,
                "manifest_ligand_topology_claim_safe_row_count": 2
                if manifest_ligand_topology_claim_safe
                else 0,
                "manifest_hbond_evidence_schema_version": "hbond_evidence_v1"
                if runner_claim_metadata_signed
                else "",
                "manifest_hbond_evidence_schema_ready_row_count": 2
                if runner_claim_metadata_signed
                else 0,
                "manifest_claim_safe": False,
                "manifest_blocked_reason": "runner_summary_not_claim_promoted;protein_topology_missing"
                if runner_claim_metadata_signed
                else "",
                "force_residual_summary_present": force_residual_summary_signed,
                "manifest_force_residual_schema_version": (
                    "force_residual_claim_metadata_v1" if force_residual_summary_signed else ""
                ),
                "manifest_force_residual_policy_caps_ready": force_residual_summary_signed,
                "manifest_force_residual_observed_caps_ready": force_residual_summary_signed,
                "manifest_force_residual_contract_ready": force_residual_summary_signed,
            },
            "force_term_claim_metadata_ready": force_term_claim_metadata_ready,
            "force_term_claim_metadata_smoke": {
                "ready": force_term_claim_metadata_ready,
                "term_result_contract_ready": force_term_result_contract_ready,
                "term_result_contract_term_set_ready": force_term_result_contract_ready,
                "term_result_contract_term_count": len(force_term_contract_rows),
                "term_result_contract_terms": [
                    "directional_hbond",
                    "hydrophobic_contact",
                    "legacy_lj",
                ] if force_term_claim_metadata_schema_ready else [],
                "term_result_contract_expected_terms": [
                    "directional_hbond",
                    "hydrophobic_contact",
                    "legacy_lj",
                ],
                "forcefield_neighbor_diagnostics_ready": force_term_claim_metadata_ready,
                "forcefield_neighbor_pair_count": 6 if force_term_claim_metadata_ready else 0,
                "forcefield_neighbor_pairs_provided": bool(force_term_claim_metadata_ready),
                "forcefield_neighbor_source": "provided_cell_list"
                if force_term_claim_metadata_ready
                else "",
                "forcefield_claim_metadata_schema_version": "force_term_claim_metadata_v1"
                if force_term_claim_metadata_schema_ready
                else "",
                "forcefield_hbond_evidence_schema_version": "hbond_evidence_v1"
                if force_term_claim_metadata_schema_ready
                else "",
                "forcefield_hydrophobic_contact_evidence_schema_version": (
                    "hydrophobic_contact_evidence_v1" if force_term_claim_metadata_schema_ready else ""
                ),
                "forcefield_hydrophobic_contact_evidence_schema_ready": (
                    force_term_claim_metadata_schema_ready
                ),
                "forcefield_hydrophobic_contact_active_pair_count": (
                    1 if force_term_claim_metadata_schema_ready else 0
                ),
                "forcefield_claim_safe_count": len(force_term_rows),
                "forcefield_blocked_count": 0,
                "forcefield_claim_rows": force_term_rows,
                "forcefield_unsafe_base_claim_blocked": force_term_claim_metadata_ready,
                "forcefield_unsafe_base_claim_safe": False,
                "forcefield_unsafe_base_blocked_reason": "placeholder_alanine_topology"
                if force_term_claim_metadata_ready
                else "",
                "forcefield_unsafe_base_claim_safe_count": 0,
                "forcefield_unsafe_base_blocked_count": len(force_term_rows)
                if force_term_claim_metadata_ready
                else 0,
                "forcefield_unsafe_base_claim_rows": [
                    {
                        **row,
                        "claim_safe": False,
                        "blocked_reason": "placeholder_alanine_topology",
                    }
                    for row in force_term_rows
                ] if force_term_claim_metadata_ready else [],
                "forcefield_energy_forces_contract_ready": force_term_result_contract_ready,
                "forcefield_energy_forces_contract_error": "",
                "forcefield_energy_shape": [1] if force_term_result_contract_ready else [],
                "forcefield_forces_shape": [1, 3, 3] if force_term_result_contract_ready else [],
                "forcefield_energy_finite": force_term_result_contract_ready,
                "forcefield_forces_finite": force_term_result_contract_ready,
                "forcefield_term_count": len(force_term_rows) if force_term_result_contract_ready else 0,
                "forcefield_term_diagnostics_ready": force_term_result_contract_ready,
                "term_result_contract_rows": force_term_contract_rows,
            },
            "force_term_result_contract_ready": force_term_result_contract_ready,
            "force_term_result_contract_term_set_ready": force_term_result_contract_ready,
            "force_term_result_contract_term_count": len(force_term_contract_rows),
            "force_term_result_contract_terms": [
                "directional_hbond",
                "hydrophobic_contact",
                "legacy_lj",
            ] if force_term_claim_metadata_schema_ready else [],
            "force_term_result_contract_expected_terms": [
                "directional_hbond",
                "hydrophobic_contact",
                "legacy_lj",
            ],
            "forcefield_energy_forces_contract_ready": force_term_result_contract_ready,
            "guarded_force_term_plugin_ready": guarded_force_term_plugin_ready,
            "guarded_force_term_plugin_smoke": {
                "ready": guarded_force_term_plugin_ready,
                "required_guarded_terms": [
                    "pocket_wall",
                    "screened_electrostatics",
                    "topology_penalty",
                    "torsion_prior",
                    "water_displacement_proxy",
                ]
                if guarded_force_term_plugin_ready
                else [],
                "required_guarded_terms_present": guarded_force_term_plugin_ready,
                "term": "screened_electrostatics",
                "claim_safe": guarded_force_term_plugin_ready,
                "force_term_status": "pass" if guarded_force_term_plugin_ready else "blocked",
                "missing_charge_blocked": guarded_force_term_plugin_ready,
                "unvalidated_charge_blocked": guarded_force_term_plugin_ready,
                "pocket_wall_missing_metadata_blocked": guarded_force_term_plugin_ready,
                "torsion_prior_missing_metadata_blocked": guarded_force_term_plugin_ready,
                "topology_penalty_missing_metadata_blocked": guarded_force_term_plugin_ready,
                "topology_penalty_invalid_topology_blocked": guarded_force_term_plugin_ready,
                "water_displacement_proxy_missing_metadata_blocked": guarded_force_term_plugin_ready,
                "water_displacement_proxy_invalid_topology_blocked": guarded_force_term_plugin_ready,
                "water_displacement_proxy_model_unvalidated_blocked": guarded_force_term_plugin_ready,
                "water_displacement_proxy_weights_invalid_blocked": guarded_force_term_plugin_ready,
                "water_displacement_proxy_policy_cap_exceeded_blocked": guarded_force_term_plugin_ready,
                "water_displacement_proxy_claim_safe": guarded_force_term_plugin_ready,
                "water_displacement_proxy_force_term_status": "pass" if guarded_force_term_plugin_ready else "blocked",
                "water_displacement_proxy_finite_difference_force_error": (
                    1e-7 if guarded_force_term_plugin_ready else 1.0
                ),
                "forcefield_claim_safe": guarded_force_term_plugin_ready,
                "finite_difference_force_error": 1e-7 if guarded_force_term_plugin_ready else 1.0,
                "pocket_wall_claim_safe": guarded_force_term_plugin_ready,
                "pocket_wall_force_term_status": "pass" if guarded_force_term_plugin_ready else "blocked",
                "pocket_wall_finite_difference_force_error": (
                    1e-7 if guarded_force_term_plugin_ready else 1.0
                ),
                "torsion_prior_claim_safe": guarded_force_term_plugin_ready,
                "torsion_prior_force_term_status": "pass" if guarded_force_term_plugin_ready else "blocked",
                "torsion_prior_finite_difference_force_error": (
                    1e-7 if guarded_force_term_plugin_ready else 1.0
                ),
                "topology_penalty_claim_safe": guarded_force_term_plugin_ready,
                "topology_penalty_force_term_status": "pass" if guarded_force_term_plugin_ready else "blocked",
                "topology_penalty_finite_difference_force_error": (
                    1e-7 if guarded_force_term_plugin_ready else 1.0
                ),
                "policy_caps_ready": guarded_force_term_plugin_ready,
                "observed_caps_ready": guarded_force_term_plugin_ready,
                "bounded_correction_ready": guarded_force_term_plugin_ready,
                "policy_cap_exceeded_blocked": guarded_force_term_plugin_ready,
                "pocket_wall_policy_cap_exceeded_blocked": guarded_force_term_plugin_ready,
                "torsion_prior_policy_cap_exceeded_blocked": guarded_force_term_plugin_ready,
                "topology_penalty_policy_cap_exceeded_blocked": guarded_force_term_plugin_ready,
                "forcefield_bounded_row_ready": guarded_force_term_plugin_ready,
                "forcefield_guarded_rows_ready": guarded_force_term_plugin_ready,
                "guarded_term_rows": [
                    {
                        "force_term_name": "screened_electrostatics",
                        "force_term_status": "pass",
                        "claim_safe": True,
                        "finite_difference_force_error": 1e-7,
                        "policy_caps_ready": True,
                        "observed_caps_ready": True,
                        "bounded_correction_ready": True,
                        "abs_energy_within_cap": True,
                        "force_norm_within_cap": True,
                        "active_pair_count_within_cap": True,
                    },
                    {
                        "force_term_name": "pocket_wall",
                        "force_term_status": "pass",
                        "claim_safe": True,
                        "finite_difference_force_error": 1e-7,
                        "policy_caps_ready": True,
                        "observed_caps_ready": True,
                        "bounded_correction_ready": True,
                        "abs_energy_within_cap": True,
                        "force_norm_within_cap": True,
                        "active_pair_count_within_cap": True,
                        "pocket_center_source": "pocket_atom_indices",
                        "pocket_escape": True,
                    },
                    {
                        "force_term_name": "torsion_prior",
                        "force_term_status": "pass",
                        "claim_safe": True,
                        "finite_difference_force_error": 1e-7,
                        "policy_caps_ready": True,
                        "observed_caps_ready": True,
                        "bounded_correction_ready": True,
                        "abs_energy_within_cap": True,
                        "force_norm_within_cap": True,
                        "active_pair_count_within_cap": True,
                        "torsion_quartet_count": 1,
                    },
                    {
                        "force_term_name": "topology_penalty",
                        "force_term_status": "pass",
                        "claim_safe": True,
                        "finite_difference_force_error": 1e-7,
                        "policy_caps_ready": True,
                        "observed_caps_ready": True,
                        "bounded_correction_ready": True,
                        "abs_energy_within_cap": True,
                        "force_norm_within_cap": True,
                        "active_pair_count_within_cap": True,
                        "topology_edge_count": 2,
                    },
                    {
                        "force_term_name": "water_displacement_proxy",
                        "force_term_status": "pass",
                        "claim_safe": True,
                        "finite_difference_force_error": 1e-7,
                        "policy_caps_ready": True,
                        "observed_caps_ready": True,
                        "bounded_correction_ready": True,
                        "abs_energy_within_cap": True,
                        "force_norm_within_cap": True,
                        "active_pair_count_within_cap": True,
                        "ligand_atom_count": 2,
                        "water_site_count": 3,
                    },
                ] if guarded_force_term_plugin_ready else [],
                "forcefield_guarded_claim_row": {
                    "force_term_name": "screened_electrostatics",
                    "force_term_status": "pass",
                    "claim_safe": True,
                    "blocked_reason": "",
                    "policy_caps_ready": True,
                    "observed_caps_ready": True,
                    "bounded_correction_ready": True,
                    "abs_energy_within_cap": True,
                    "force_norm_within_cap": True,
                    "active_pair_count_within_cap": True,
                    "policy_caps": {
                        "max_abs_energy": 50.0,
                        "max_force_norm": 25.0,
                        "max_active_pair_count": 4096.0,
                    },
                } if guarded_force_term_plugin_ready else {},
                "forcefield_guarded_claim_rows": [
                    {
                        "force_term_name": "pocket_wall",
                        "force_term_status": "pass",
                        "claim_safe": True,
                        "blocked_reason": "",
                        "policy_caps_ready": True,
                        "observed_caps_ready": True,
                        "bounded_correction_ready": True,
                        "abs_energy_within_cap": True,
                        "force_norm_within_cap": True,
                        "active_pair_count_within_cap": True,
                        "policy_caps": {
                            "max_abs_energy": 50.0,
                            "max_force_norm": 25.0,
                            "max_active_pair_count": 4096.0,
                        },
                    },
                    {
                        "force_term_name": "screened_electrostatics",
                        "force_term_status": "pass",
                        "claim_safe": True,
                        "blocked_reason": "",
                        "policy_caps_ready": True,
                        "observed_caps_ready": True,
                        "bounded_correction_ready": True,
                        "abs_energy_within_cap": True,
                        "force_norm_within_cap": True,
                        "active_pair_count_within_cap": True,
                        "policy_caps": {
                            "max_abs_energy": 50.0,
                            "max_force_norm": 25.0,
                            "max_active_pair_count": 4096.0,
                        },
                    },
                    {
                        "force_term_name": "torsion_prior",
                        "force_term_status": "pass",
                        "claim_safe": True,
                        "blocked_reason": "",
                        "policy_caps_ready": True,
                        "observed_caps_ready": True,
                        "bounded_correction_ready": True,
                        "abs_energy_within_cap": True,
                        "force_norm_within_cap": True,
                        "active_pair_count_within_cap": True,
                        "policy_caps": {
                            "max_abs_energy": 50.0,
                            "max_force_norm": 25.0,
                            "max_active_pair_count": 4096.0,
                        },
                    },
                    {
                        "force_term_name": "topology_penalty",
                        "force_term_status": "pass",
                        "claim_safe": True,
                        "blocked_reason": "",
                        "policy_caps_ready": True,
                        "observed_caps_ready": True,
                        "bounded_correction_ready": True,
                        "abs_energy_within_cap": True,
                        "force_norm_within_cap": True,
                        "active_pair_count_within_cap": True,
                        "policy_caps": {
                            "max_abs_energy": 50.0,
                            "max_force_norm": 25.0,
                            "max_active_pair_count": 4096.0,
                        },
                    },
                    {
                        "force_term_name": "water_displacement_proxy",
                        "force_term_status": "pass",
                        "claim_safe": True,
                        "blocked_reason": "",
                        "policy_caps_ready": True,
                        "observed_caps_ready": True,
                        "bounded_correction_ready": True,
                        "abs_energy_within_cap": True,
                        "force_norm_within_cap": True,
                        "active_pair_count_within_cap": True,
                        "policy_caps": {
                            "max_abs_energy": 20.0,
                            "max_force_norm": 10.0,
                            "max_active_pair_count": 4096.0,
                        },
                    },
                ] if guarded_force_term_plugin_ready else [],
                "abs_energy_within_cap": guarded_force_term_plugin_ready,
                "force_norm_within_cap": guarded_force_term_plugin_ready,
                "active_pair_count_within_cap": guarded_force_term_plugin_ready,
                "policy_caps": {
                    "max_abs_energy": 50.0,
                    "max_force_norm": 25.0,
                    "max_active_pair_count": 4096.0,
                } if guarded_force_term_plugin_ready else {},
                "observed_abs_energy": 0.5 if guarded_force_term_plugin_ready else 0.0,
                "observed_force_norm": 0.1 if guarded_force_term_plugin_ready else 0.0,
            },
            "onsps_backmap_evidence_schema_ready": onsps_backmap_evidence_schema_ready,
            "onsps_backmap_evidence_schema_smoke": {
                "ready": onsps_backmap_evidence_schema_ready,
                "schema_version": "onsps_backmap_evidence_v1" if onsps_backmap_evidence_schema_ready else "",
                "valid_claim_safe": onsps_backmap_evidence_schema_ready,
                "valid_backmap_status": "ok" if onsps_backmap_evidence_schema_ready else "",
                "valid_mapped_site_count": 1 if onsps_backmap_evidence_schema_ready else 0,
                "empty_blocked_reason": "invalid_two_bead_geometry"
                if onsps_backmap_evidence_schema_ready
                else "",
                "no_sites_blocked_reason": "no_onsps_sites" if onsps_backmap_evidence_schema_ready else "",
                "hbond_onsps_schema_version": "onsps_backmap_evidence_v1"
                if onsps_backmap_evidence_schema_ready
                else "",
                "product_runner_direct_engine_import_ready": onsps_backmap_evidence_schema_ready,
                "product_runner_import_source": "betelgeuze_engine.backmapping.onsps"
                if onsps_backmap_evidence_schema_ready
                else "",
                "product_runner_legacy_core_import_absent": onsps_backmap_evidence_schema_ready,
            },
            "engine_topology_factory_facade_ready": True,
            "engine_topology_factory_facade_smoke": {
                "ready": True,
                "facade": "betelgeuze_engine.topology.TopologyFactoryFacade",
                "valid_claim_safe": True,
                "valid_topology_fidelity": "sequence_mapped",
                "valid_protein_residue_count": 3,
                "valid_protein_topology_valid": True,
                "valid_pocket_residue_count": 1,
                "valid_pocket_residue_indices_valid": True,
                "valid_ligand_topology_schema_version": "ligand_topology_validity_v1",
                "placeholder_protein_residue_count": 3,
                "placeholder_protein_topology_valid": True,
                "placeholder_blocked_reason": "placeholder_alanine_topology",
                "empty_protein_residue_count": 0,
                "empty_protein_topology_valid": False,
                "empty_protein_blocked_reason": "empty_protein_topology",
                "invalid_ligand_blocked_reason": "invalid_smiles",
                "invalid_pocket_blocked_reason": "invalid_pocket_residue_indices",
                "invalid_pocket_residue_indices_valid": False,
            },
            "core_forcefield_bridge_ready": core_forcefield_bridge_ready,
            "core_forcefield_bridge_smoke": {
                "ready": core_forcefield_bridge_ready,
                "result_claim_safe": core_forcefield_bridge_ready,
                "force_term_claim_metadata_ready": core_forcefield_bridge_ready,
                "force_term_plugins": ["legacy_lj"] if core_forcefield_bridge_ready else [],
                "unsafe_base_claim_blocked": core_forcefield_bridge_ready,
                "unsafe_base_claim_safe": False,
                "unsafe_base_blocked_reason": "placeholder_alanine_topology"
                if core_forcefield_bridge_ready
                else "",
                "unsafe_base_claim_safe_count": 0,
                "unsafe_base_blocked_count": 1 if core_forcefield_bridge_ready else 0,
                "unsafe_base_claim_rows": [
                    {
                        "force_term_name": "legacy_lj",
                        "force_term_status": "pass",
                        "claim_safe": False,
                        "blocked_reason": "placeholder_alanine_topology",
                    },
                ] if core_forcefield_bridge_ready else [],
                "energy_shape": [1] if core_forcefield_bridge_ready else [],
                "forces_shape": [1, 2, 3] if core_forcefield_bridge_ready else [],
                "neighbor_diagnostics_ready": core_forcefield_bridge_ready,
                "neighbor_pair_count": 2 if core_forcefield_bridge_ready else 0,
                "neighbor_pairs_provided": bool(core_forcefield_bridge_ready),
                "neighbor_source": "provided_cell_list" if core_forcefield_bridge_ready else "",
                "bridge_execution_scope": "metadata_contract_only_not_runtime_gpu_claim"
                if core_forcefield_bridge_ready
                else "",
            },
            "core_compatibility_layer_ready": core_compatibility_layer_ready,
            "core_compatibility_layer_smoke": {
                "ready": core_compatibility_layer_ready,
                "contract_scope": "legacy_core_import_paths_are_compatibility_layer_not_runtime_gpu_claim",
                "row_count": 7 if core_compatibility_layer_ready else 0,
                "rows": [
                    {
                        "contract": "onsps_backmap_shim",
                        "ready": core_compatibility_layer_ready,
                        "legacy_module": "core.onsps_backmap",
                        "canonical_module": "betelgeuze_engine.backmapping.onsps",
                        "bridge_type": "import_identity",
                        "error": "",
                    },
                    {
                        "contract": "topology_protein_bridge",
                        "ready": core_compatibility_layer_ready,
                        "legacy_module": "core.topology",
                        "canonical_module": "betelgeuze_engine.topology.protein",
                        "bridge_type": "engine_dataclass_bridge",
                        "topology_fidelity": "sequence_mapped" if core_compatibility_layer_ready else "",
                        "protein_topology_type": "ProteinTopology" if core_compatibility_layer_ready else "",
                        "hbond_role_count": 2 if core_compatibility_layer_ready else 0,
                        "error": "",
                    },
                    {
                        "contract": "adress_production_blocked_log",
                        "ready": core_compatibility_layer_ready,
                        "legacy_module": "core.topology",
                        "canonical_module": "betelgeuze_engine.topology.protein",
                        "bridge_type": "fail_closed_adress_guard",
                        "adress_log_blocked": core_compatibility_layer_ready,
                        "adress_log_active_claim_absent": core_compatibility_layer_ready,
                        "adress_neighbor_blocked": core_compatibility_layer_ready,
                        "adress_neighbor_error": "AdResS neighbor path is disabled in production."
                        if core_compatibility_layer_ready
                        else "",
                        "error": "",
                    },
                    {
                        "contract": "forcefield_product_bridge",
                        "ready": core_compatibility_layer_ready,
                        "legacy_module": "core.forcefield",
                        "canonical_module": "betelgeuze_engine.physics",
                        "bridge_type": "energy_forces_claim_metadata_bridge",
                        "result_claim_safe": core_compatibility_layer_ready,
                        "force_term_claim_metadata_ready": core_compatibility_layer_ready,
                        "force_term_plugins": ["legacy_lj"] if core_compatibility_layer_ready else [],
                        "unsafe_base_claim_blocked": core_compatibility_layer_ready,
                        "unsafe_base_claim_safe": False,
                        "unsafe_base_blocked_reason": "placeholder_alanine_topology"
                        if core_compatibility_layer_ready
                        else "",
                        "unsafe_base_claim_safe_count": 0,
                        "unsafe_base_blocked_count": 1 if core_compatibility_layer_ready else 0,
                        "unsafe_base_claim_rows": [
                            {
                                "force_term_name": "legacy_lj",
                                "force_term_status": "pass",
                                "claim_safe": False,
                                "blocked_reason": "placeholder_alanine_topology",
                            },
                        ] if core_compatibility_layer_ready else [],
                        "neighbor_diagnostics_ready": core_compatibility_layer_ready,
                        "neighbor_pair_count": 2 if core_compatibility_layer_ready else 0,
                        "neighbor_pairs_provided": bool(core_compatibility_layer_ready),
                        "neighbor_source": "provided_cell_list" if core_compatibility_layer_ready else "",
                        "error": "",
                    },
                    {
                        "contract": "score_residual_shim",
                        "ready": core_compatibility_layer_ready,
                        "legacy_module": "core.score_residual",
                        "canonical_module": "betelgeuze_engine.residual.score",
                        "bridge_type": "import_identity",
                        "checked_symbols": ["apply_score_residual", "residual_band"],
                        "missing_symbols": [],
                        "identity_mismatches": [],
                        "error": "",
                    },
                    {
                        "contract": "topology_score_correction_shim",
                        "ready": core_compatibility_layer_ready,
                        "legacy_module": "core.topo_corrector",
                        "canonical_module": "betelgeuze_engine.topology.correction",
                        "bridge_type": "import_identity",
                        "checked_symbols": ["summarize_topo_correction", "topo_correction_delta"],
                        "missing_symbols": [],
                        "identity_mismatches": [],
                        "error": "",
                    },
                    {
                        "contract": "mm_gbsa_refine_shim",
                        "ready": core_compatibility_layer_ready,
                        "legacy_module": "core.mm_gbsa",
                        "canonical_module": "betelgeuze_engine.physics.mm_gbsa",
                        "bridge_type": "import_identity",
                        "checked_symbols": ["mm_gbsa_binding_energy", "compute_full_refine_stack"],
                        "missing_symbols": [],
                        "identity_mismatches": [],
                        "error": "",
                    },
                ] if core_compatibility_layer_ready else [],
            },
            "job_store_lazy_factory_ready": job_store_lazy_factory_ready,
            "job_store_lazy_factory_smoke": {"ready": job_store_lazy_factory_ready},
            "allowlisted_runner_shim_contract_ready": allowlisted_runner_shim_contract_ready,
            "product_runner_engine_imports_ready": ready,
            "product_runner_engine_imports_smoke": {
                "ready": ready,
                "runner": "tools/product/run_ligand_backmapping_scoring.py",
                "row_count": 6 if ready else 0,
                "rows": [
                    {
                        "contract": "hbond_evidence_direct_engine_import",
                        "runner": "tools/product/run_ligand_backmapping_scoring.py",
                        "engine_module": "betelgeuze_engine.interactions",
                        "direct_import_present": True,
                        "legacy_import_absent": True,
                        "required_missing": [],
                        "forbidden_present": [],
                        "ready": True,
                    },
                    {
                        "contract": "onsps_backmap_direct_engine_import",
                        "runner": "tools/product/run_ligand_backmapping_scoring.py",
                        "engine_module": "betelgeuze_engine.backmapping.onsps",
                        "direct_import_present": True,
                        "legacy_import_absent": True,
                        "required_missing": [],
                        "forbidden_present": [],
                        "ready": True,
                    },
                    {
                        "contract": "ligand_topology_direct_engine_import",
                        "runner": "tools/product/run_ligand_backmapping_scoring.py",
                        "engine_module": "betelgeuze_engine.topology",
                        "direct_import_present": True,
                        "legacy_import_absent": True,
                        "required_missing": [],
                        "forbidden_present": [],
                        "ready": True,
                    },
                    {
                        "contract": "topology_score_correction_direct_engine_import",
                        "runner": "tools/product/run_ligand_backmapping_scoring.py",
                        "engine_module": "betelgeuze_engine.topology",
                        "direct_import_present": True,
                        "legacy_import_absent": True,
                        "required_missing": [],
                        "forbidden_present": [],
                        "residual_scope": "score_ranking_heuristic",
                        "physical_force_residual_claim": False,
                        "bounded_correction_required": True,
                        "ready": True,
                    },
                    {
                        "contract": "score_residual_direct_engine_import",
                        "runner": "tools/product/run_ligand_backmapping_scoring.py",
                        "engine_module": "betelgeuze_engine.residual.score",
                        "direct_import_present": True,
                        "legacy_import_absent": True,
                        "required_missing": [],
                        "forbidden_present": [],
                        "residual_scope": "score_ranking_heuristic",
                        "physical_force_residual_claim": False,
                        "ready": True,
                    },
                    {
                        "contract": "mm_gbsa_refine_direct_engine_import",
                        "runner": "tools/product/run_ligand_backmapping_scoring.py",
                        "engine_module": "betelgeuze_engine.physics.mm_gbsa",
                        "direct_import_present": True,
                        "legacy_import_absent": True,
                        "required_missing": [],
                        "forbidden_present": [],
                        "refine_claim_safe_required": False,
                        "claim_metadata_schema": "mm_gbsa_refine_claim_metadata_v1",
                        "ready": True,
                    },
                ] if ready else [],
            },
            "product_runner_no_core_imports_ready": ready,
            "product_runner_no_core_imports_smoke": _runner_no_core_imports_smoke(ready=ready),
            "topk_delivery_engine_owned_ready": ready,
            "topk_delivery_engine_owned_smoke": _topk_delivery_engine_owned_smoke(ready=ready),
            "backmapping_scoring_engine_owned_ready": ready,
            "backmapping_scoring_engine_owned_smoke": _backmapping_scoring_engine_owned_smoke(ready=ready),
            "htvs_pipeline_engine_owned_ready": ready,
            "htvs_pipeline_engine_owned_smoke": _htvs_pipeline_engine_owned_smoke(ready=ready),
            "product_runner_engine_owned_ready": ready,
            "product_runner_engine_owned_smoke": _product_runner_engine_owned_smoke(ready=ready),
            "allowlisted_runner_shim_contract": {
                "ready": allowlisted_runner_shim_contract_ready,
                "runner_count": 3 if allowlisted_runner_shim_contract_ready else 0,
                "rows": [
                    {
                        "profile_id": "ligand_htvs_pipeline_default",
                        "runner_script": "tools/run_ligand_htvs_pipeline.py",
                        "profile_runner_script": "tools/run_ligand_htvs_pipeline.py",
                        "adapter_import": "betelgeuze_engine.product.runners.htvs_pipeline",
                        "adapter_import_present": True,
                        "shim_contract_type": "canonical_module_alias",
                        "sys_modules_alias_ready": True,
                        "runtime_module_name": "betelgeuze_engine.product.runners.htvs_pipeline",
                        "self_implementation_blocked": True,
                        "required_runtime_symbols": ["main", "build_parser"],
                        "runtime_adapter_identity_ready": True,
                        "missing_runtime_symbols": [],
                        "runtime_adapter_error": "",
                        "script_hash": "a" * 64,
                        "profile_runner_script_sha256": "a" * 64,
                        "hash_matches": True,
                        "ready": True,
                        "error": "",
                    },
                    {
                        "profile_id": "backmapping_scoring.production",
                        "runner_script": "tools/run_ligand_backmapping_scoring.py",
                        "profile_runner_script": "tools/run_ligand_backmapping_scoring.py",
                        "adapter_import": "betelgeuze_engine.product.runners.backmapping_scoring",
                        "adapter_import_present": True,
                        "shim_contract_type": "canonical_module_alias",
                        "sys_modules_alias_ready": True,
                        "runtime_module_name": "betelgeuze_engine.product.runners.backmapping_scoring",
                        "self_implementation_blocked": True,
                        "required_runtime_symbols": ["main", "_frame_mmpbsa_proxy"],
                        "runtime_adapter_identity_ready": True,
                        "missing_runtime_symbols": [],
                        "runtime_adapter_error": "",
                        "script_hash": "b" * 64,
                        "profile_runner_script_sha256": "b" * 64,
                        "hash_matches": True,
                        "ready": True,
                        "error": "",
                    },
                    {
                        "profile_id": "ligand_topk_delivery.production",
                        "runner_script": "tools/run_ligand_topk_delivery.py",
                        "profile_runner_script": "tools/run_ligand_topk_delivery.py",
                        "adapter_import": "betelgeuze_engine.product.runners.topk_delivery",
                        "adapter_import_present": True,
                        "shim_contract_type": "canonical_module_alias",
                        "sys_modules_alias_ready": True,
                        "runtime_module_name": "betelgeuze_engine.product.runners.topk_delivery",
                        "self_implementation_blocked": True,
                        "required_runtime_symbols": ["main", "build_delivery"],
                        "runtime_adapter_identity_ready": True,
                        "missing_runtime_symbols": [],
                        "runtime_adapter_error": "",
                        "script_hash": "c" * 64,
                        "profile_runner_script_sha256": "c" * 64,
                        "hash_matches": True,
                        "ready": True,
                        "error": "",
                    },
                ] if allowlisted_runner_shim_contract_ready else [],
            },
            "blocked_claim_correctly_blocked": True,
        },
        "pose_ranking_hbond_benchmark": {
            "benchmark_ready": pose_ranking_hbond_benchmark_ready,
            "top1_pose_id": "amide_near_hbond_pose" if pose_ranking_hbond_benchmark_ready else "amide_far_decoy_pose",
            "top1_expected_pose_id": "amide_near_hbond_pose",
            "hbond_recovery_pose_count": 1 if pose_ranking_hbond_benchmark_ready else 0,
            "hbond_recovery_pose_ids": ["amide_near_hbond_pose"] if pose_ranking_hbond_benchmark_ready else [],
            "hbond_recovery_confidence_min": 0.9 if pose_ranking_hbond_benchmark_ready else 0.0,
            "hbond_recovery_benchmark_schema_version": "hbond_recovery_benchmark_v1",
            "hbond_recovery_benchmark_ready": pose_ranking_hbond_benchmark_ready,
            "hbond_recovery_benchmark_status": hbond_recovery_benchmark["status"],
            "hbond_recovery_benchmark_fixture_count": (
                hbond_recovery_benchmark["summary"]["fixture_count"]
            ),
            "hbond_recovery_benchmark_contract_pass_count": (
                hbond_recovery_benchmark["summary"]["benchmark_contract_pass_count"]
            ),
            "hbond_recovery_benchmark": hbond_recovery_benchmark,
            "overanchored_decoys_blocked": pose_ranking_hbond_benchmark_ready,
            "delta_backmap_yellow_band_abstention_ready": pose_ranking_hbond_benchmark_ready,
            "unsatisfied_donor_acceptor_detected": pose_ranking_hbond_benchmark_ready,
            "unsatisfied_donor_acceptor_pose_count": 3 if pose_ranking_hbond_benchmark_ready else 0,
            "fixture_count": len(pose_rows),
            "required_pose_roles": [
                "delta_backmap_yellow_band_pose",
                "far_decoy_pose",
                "hbond_recovery_pose",
                "invalid_ligand_pose",
                "overanchored_decoy_pose",
                "unsatisfied_donor_pose",
            ],
            "observed_pose_roles": pose_roles,
            "ranking_order": ranking_order,
            "row_contracts_ready": pose_ranking_hbond_benchmark_ready,
            "row_contract_pass_count": len(pose_rows),
            "rows": pose_rows,
        },
        "confidence_calibration_report": confidence_calibration,
        "runtime_kpi": {
            "score_only_1k": {
                "row_count": 8,
                "valid_count": 8,
                "duration_sec": 0.01,
                "rows_per_sec": 800.0,
            },
            "top100_4bead_rescoring": {
                "row_count": 7,
                "site_positive_count": 5,
                "onsps_backmap_claim_safe_count": 2,
                "duration_sec": 0.02,
                "rows_per_sec": 350.0,
            },
            "top10_force_residual": {
                "row_count": 3,
                "applied_count": 3,
                "bounded_correction_policy_ready": force_residual_bounded_policy_ready,
                "observed_caps_ready": force_residual_observed_caps_ready,
                "contract_ready": force_residual_contract_ready,
                "confidence_abstention_ready": force_residual_confidence_abstention_ready,
                "nonfinite_uncertainty_abstention_count": 1,
                "nonfinite_delta_score_abstention_count": 1,
                "last_report": {
                    "applied": True,
                    "skipped_reason": "",
                    "claim_safe": True,
                    "rank_pct": 0.01,
                    "top_k_eligible": True,
                    "delta_score": 0.25,
                    "uncertainty": 0.1,
                    "confidence": 0.9,
                    "max_force_norm": 0.87,
                    "displacement_rmsd": 0.009,
                    "energy_drift_pct": 0.0,
                    "policy_caps_ready": True,
                    "observed_caps_ready": True,
                    "all_observed_caps_within_policy": True,
                    "delta_score_within_cap": True,
                    "force_norm_within_cap": True,
                    "displacement_within_cap": True,
                    "energy_drift_within_cap": True,
                    "policy_caps": {
                        "top_k_rank_pct": 0.05,
                        "max_abs_delta_score": 2.0,
                        "max_force_norm": 25.0,
                        "max_displacement": 0.25,
                        "max_energy_drift_pct": 5.0,
                    },
                },
                "nonfinite_uncertainty_report": {
                    "applied": False,
                    "skipped_reason": "uncertainty_nonfinite",
                    "uncertainty": 1.0,
                    "confidence": 0.0,
                    "observed_caps_ready": True,
                },
                "nonfinite_delta_score_report": {
                    "applied": False,
                    "skipped_reason": "delta_score_nonfinite",
                    "delta_score": 0.0,
                    "confidence": 0.9,
                    "observed_caps_ready": True,
                },
                "top_k_policy_ready": True,
                "contract_expected_report_count": 6,
                "contract_validated_report_count": 6,
                "contract_validation_ready": True,
                "contract_validated_report_labels": [
                    "applied_runtime_last",
                    "delta_score_cap",
                    "uncertainty_abstention",
                    "outside_top_k",
                    "nonfinite_uncertainty",
                    "nonfinite_delta_score",
                ],
                "outside_top_k_report": {
                    "applied": False,
                    "skipped_reason": "outside_top_k_policy",
                    "rank_pct": 0.06,
                    "top_k_eligible": False,
                    "policy_caps": {"top_k_rank_pct": 0.05},
                },
                "duration_sec": 0.03,
                "rows_per_sec": 100.0,
            },
            "memory_peak_mb": 256.0,
            "neighbor_list_rebuild": {
                "frame_count": 12,
                "neighbor_list_rebuild_count": 4,
                "neighbor_list_rebuild_frequency": 0.3333333333,
                "last_neighbor_pair_count": 240,
                "last_forcefield_neighbor_pair_count": 240,
                "forcefield_neighbor_source": "provided_cell_list",
                "forcefield_neighbor_pairs_provided": True,
                "neighbor_provider_status": "neighbor_provider_ready",
                "neighbor_provider_overflow": False,
                "neighbor_provider_nxn_allocation_observed": False,
                "engine_neighbor_diagnostics_ready": True,
            },
            "neighbor_cap_scaling": {
                "ready": True,
                "status": "runtime_neighbor_cap_scaling_ready",
                "forcefield_contract_ready": True,
                "neighbor_cap_scaling_ready": True,
                "nxn_allocation_observed": False,
                "coordinate_mode": "fixed_density_grid",
                "fixed_density_ready": True,
                "target_number_density": 1.0 / 27.0,
                "max_density_relative_error": 0.0,
                "release_atom_counts": [1000, 2000, 4000, 8000],
                "release_atom_counts_ready": False,
                "memory_per_atom_linear_ready": True,
                "max_memory_peak_mb_per_atom": 32.0,
                "total_rebuild_count": 6,
                "total_rebuild_duration_sec": 0.003,
                "atom_counts": [64, 125, 216],
                "neighbor_pair_counts": [384, 750, 1296],
                "neighbor_pair_count_slope": 1.0,
                "neighbor_pair_count_r2": 1.0,
                "duration_slope": 0.2,
                "duration_r2": 0.5,
                "plot_path": "runs/ai_md_runtime_scaling_plot_current.svg",
                "plot_format": "svg",
                "plot_ready": True,
                "plot_role": "runtime_neighbor_cap_scaling_plot",
                "plot_claim_boundary": (
                    "Pair-count scaling is the gated evidence; duration trend is advisory microbenchmark telemetry."
                ),
                "plot_sha256": "d" * 64,
                "plot_size_bytes": 1024,
                "rows": [
                    {
                        "atom_count": 64,
                        "duration_per_repeat_sec": 0.001,
                        "neighbor_pair_count": 384,
                        "neighbor_pairs_provided": True,
                        "neighbor_source": "provided_cell_list",
                        "neighbor_provider_status": "neighbor_provider_ready",
                        "neighbor_provider_overflow": False,
                        "nxn_allocation_observed": False,
                        "coordinate_mode": "fixed_density_grid",
                        "fixed_density": True,
                        "box_size": 12.0,
                        "target_number_density": 1.0 / 27.0,
                        "density_relative_error": 0.0,
                        "memory_peak_mb_per_atom": 32.0,
                        "energy_finite": True,
                        "forces_finite": True,
                        "claim_safe": True,
                        "row_ready": True,
                    },
                    {
                        "atom_count": 125,
                        "duration_per_repeat_sec": 0.002,
                        "neighbor_pair_count": 750,
                        "neighbor_pairs_provided": True,
                        "neighbor_source": "provided_cell_list",
                        "neighbor_provider_status": "neighbor_provider_ready",
                        "neighbor_provider_overflow": False,
                        "nxn_allocation_observed": False,
                        "coordinate_mode": "fixed_density_grid",
                        "fixed_density": True,
                        "box_size": 15.0,
                        "target_number_density": 1.0 / 27.0,
                        "density_relative_error": 0.0,
                        "memory_peak_mb_per_atom": 16.0,
                        "energy_finite": True,
                        "forces_finite": True,
                        "claim_safe": True,
                        "row_ready": True,
                    },
                    {
                        "atom_count": 216,
                        "duration_per_repeat_sec": 0.004,
                        "neighbor_pair_count": 1296,
                        "neighbor_pairs_provided": True,
                        "neighbor_source": "provided_cell_list",
                        "neighbor_provider_status": "neighbor_provider_ready",
                        "neighbor_provider_overflow": False,
                        "nxn_allocation_observed": False,
                        "coordinate_mode": "fixed_density_grid",
                        "fixed_density": True,
                        "box_size": 18.0,
                        "target_number_density": 1.0 / 27.0,
                        "density_relative_error": 0.0,
                        "memory_peak_mb_per_atom": 8.0,
                        "energy_finite": True,
                        "forces_finite": True,
                        "claim_safe": True,
                        "row_ready": True,
                    },
                ],
            },
        },
        "physics_kpi": {
            "finite_difference_force_error": 1e-7,
            "energy_drift_smoke_pct": 1e-4,
            "rotation_equivariance_error": 0.0,
            "neighbor_list_parity_error": 0.0,
            "topology_invalid_rate": 0.1,
            "backmapping_failure_rate": 0.0,
            "force_term_physics_validation_ready": force_term_physics_validation_ready,
            "force_term_physics_validation_claim_safe_ready": (
                force_term_physics_validation_claim_safe_ready
            ),
            "force_term_physics_validation_thresholds": force_term_physics["thresholds"],
            "force_term_physics_validation_rows": force_term_physics["rows"],
            "force_term_physics_validation_term_count": force_term_physics["term_count"],
            "force_term_physics_validation_claim_safe_count": (
                force_term_physics["claim_safe_count"]
            ),
            "force_term_finite_difference_max_error": (
                force_term_physics["finite_difference_max_error"]
            ),
            "force_term_translation_invariance_max_error": (
                force_term_physics["translation_invariance_max_error"]
            ),
            "force_term_rotation_equivariance_max_error": (
                force_term_physics["rotation_equivariance_max_error"]
            ),
            "force_term_energy_drift_max_pct": force_term_physics["energy_drift_max_pct"],
        },
        "chemistry_kpi": chemistry_kpi,
        "pm_kpi_summary": {
            "summary_ready": ready,
            "failed_gate_ids": [] if ready else ["clean_install_success"],
            "runtime": {
                "score_only_1k_runtime_sec": 0.01,
                "score_only_1k_rows_per_sec": 800.0,
                "top100_4bead_rescoring_runtime_sec": 0.02,
                "top100_4bead_rescoring_rows_per_sec": 350.0,
                "top10_force_residual_runtime_sec": 0.03,
                "top10_force_residual_rows_per_sec": 100.0,
                "memory_peak_mb": 256.0,
                "neighbor_list_rebuild_frequency": 0.3333333333,
                "score_only_1k_runtime_tracked": True,
                "top100_4bead_rescoring_runtime_tracked": True,
                "top10_force_residual_runtime_tracked": True,
                "memory_peak_tracked": True,
                "neighbor_list_rebuild_frequency_tracked": True,
                "runtime_neighbor_cap_scaling_ready": True,
                "runtime_neighbor_cap_scaling_status": "runtime_neighbor_cap_scaling_ready",
                "runtime_neighbor_cap_scaling_row_count": 3,
                "runtime_neighbor_cap_scaling_atom_counts": [64, 125, 216],
                "runtime_neighbor_cap_scaling_pair_count_slope": 1.0,
                "runtime_neighbor_cap_scaling_pair_count_r2": 1.0,
                "runtime_neighbor_cap_scaling_duration_slope": 0.2,
                "runtime_neighbor_cap_scaling_duration_r2": 0.5,
                "runtime_neighbor_cap_scaling_fixed_density_ready": True,
                "runtime_neighbor_cap_scaling_target_number_density": 1.0 / 27.0,
                "runtime_neighbor_cap_scaling_max_density_relative_error": 0.0,
                "runtime_neighbor_cap_scaling_release_atom_counts": [1000, 2000, 4000, 8000],
                "runtime_neighbor_cap_scaling_release_atom_counts_ready": False,
                "runtime_neighbor_cap_scaling_nxn_allocation_observed": False,
                "runtime_neighbor_cap_scaling_memory_per_atom_linear_ready": True,
                "runtime_neighbor_cap_scaling_max_memory_peak_mb_per_atom": 32.0,
                "runtime_neighbor_cap_scaling_total_rebuild_count": 6,
                "runtime_neighbor_cap_scaling_total_rebuild_duration_sec": 0.003,
                "runtime_neighbor_cap_scaling_plot_ready": True,
                "runtime_neighbor_cap_scaling_plot_path": "runs/ai_md_runtime_scaling_plot_current.svg",
                "runtime_neighbor_cap_scaling_plot_sha256": "d" * 64,
                "force_residual_bounded_policy_ready": force_residual_bounded_policy_ready,
                "force_residual_observed_caps_ready": force_residual_observed_caps_ready,
                "force_residual_contract_ready": force_residual_contract_ready,
                "force_residual_confidence_abstention_ready": force_residual_confidence_abstention_ready,
                "force_residual_top_k_policy_ready": True,
            },
            "physics": {
                "finite_difference_force_error_pass": True,
                "energy_drift_pass": True,
                "rotation_equivariance_pass": True,
                "neighbor_list_parity_pass": True,
                "topology_invalid_rate_pass": True,
                "backmapping_failure_rate_pass": True,
                "force_term_physics_validation_ready": force_term_physics_validation_ready,
                "force_term_physics_validation_claim_safe_ready": (
                    force_term_physics_validation_claim_safe_ready
                ),
            },
            "product": {
                "runner_claim_metadata_signed": runner_claim_metadata_signed,
                "signed_manifest_verification_pass": runner_claim_metadata_signed,
                "bundle_validation_pass": ready,
                "product_claim_ready": ready,
                "release_claim_ready": False,
                "release_claim_blocked_reason": "product_ci_runtime_gate_not_ready",
                "product_ci_runtime_gate_present": False,
                "product_ci_runtime_gate_ready": False,
                "product_ci_runtime_gate_status": "",
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
                "product_ci_latest_github_actions_record_kst_date": "",
                "clean_install_missing_requirement_count": 0,
                "clean_install_missing_requirements": [],
                "product_image_preflight_blocker_codes": [],
                "clean_container_missing_requirement_count": 0,
                "clean_container_missing_requirements": [],
                "source_artifacts_fresh": ready,
                "source_artifact_fresh_count": 4 if ready else 0,
                "source_artifact_stale_count": 0,
                "source_artifact_stale_ids": [],
                "enabled_profile_count": 3 if ready else 0,
                "failed_profile_count": 0 if ready else 1,
                "runner_profile_validation_pass": ready,
                "force_term_claim_metadata_ready": force_term_claim_metadata_ready,
                "force_term_result_contract_ready": force_term_result_contract_ready,
                "force_term_result_contract_term_set_ready": force_term_result_contract_ready,
                "force_term_result_contract_term_count": len(force_term_contract_rows),
                "force_term_result_contract_terms": [
                    "directional_hbond",
                    "hydrophobic_contact",
                    "legacy_lj",
                ] if force_term_claim_metadata_schema_ready else [],
                "force_term_result_contract_expected_terms": [
                    "directional_hbond",
                    "hydrophobic_contact",
                    "legacy_lj",
                ],
                "forcefield_energy_forces_contract_ready": force_term_result_contract_ready,
                "guarded_force_term_plugin_ready": guarded_force_term_plugin_ready,
                "onsps_backmap_evidence_schema_ready": onsps_backmap_evidence_schema_ready,
                "engine_topology_factory_facade_ready": True,
                "core_forcefield_bridge_ready": core_forcefield_bridge_ready,
                "core_compatibility_layer_ready": core_compatibility_layer_ready,
                "job_store_lazy_factory_ready": job_store_lazy_factory_ready,
                "allowlisted_runner_shim_contract_ready": allowlisted_runner_shim_contract_ready,
                "product_runner_engine_imports_ready": ready,
                "product_runner_no_core_imports_ready": ready,
                "topk_delivery_engine_owned_ready": ready,
                "backmapping_scoring_engine_owned_ready": ready,
                "htvs_pipeline_engine_owned_ready": ready,
                "product_runner_engine_owned_ready": ready,
                "blocked_claim_correctly_blocked": True,
            },
            "chemistry": {
                "hbond_evidence_schema_ready": chemistry_pm_gates_ready,
                "hbond_evidence_schema_ready_count": chemistry_kpi["hbond_evidence_schema_ready_count"],
                "ligand_topology_validity_schema_ready": chemistry_pm_gates_ready,
                "ligand_topology_validity_schema_ready_count": (
                    chemistry_kpi["ligand_topology_validity_schema_ready_count"]
                ),
                "hbond_donor_site_count": chemistry_kpi["hbond_donor_site_count"],
                "hbond_acceptor_site_count": chemistry_kpi["hbond_acceptor_site_count"],
                "hbond_geometry_evaluated_fixture_count": (
                    chemistry_kpi["hbond_geometry_evaluated_fixture_count"]
                ),
                "hbond_geometry_complete_fixture_count": (
                    chemistry_kpi["hbond_geometry_complete_fixture_count"]
                ),
                "hbond_recovery_fixture_count": chemistry_kpi["hbond_recovery_fixture_count"],
                "hbond_recovery_pose_count": 1 if chemistry_pm_gates_ready else 0,
                "hbond_recovery_pose_ids": ["amide_near_hbond_pose"] if chemistry_pm_gates_ready else [],
                "hbond_recovery_confidence_min": 0.9 if chemistry_pm_gates_ready else 0.0,
                "hbond_recovery_benchmark_ready": pose_ranking_hbond_benchmark_ready,
                "hbond_recovery_benchmark_schema_version": "hbond_recovery_benchmark_v1",
                "hbond_recovery_benchmark_fixture_count": (
                    hbond_recovery_benchmark["summary"]["fixture_count"]
                ),
                "hbond_recovery_benchmark_contract_pass_count": (
                    hbond_recovery_benchmark["summary"]["benchmark_contract_pass_count"]
                ),
                "unsatisfied_donor_acceptor_detection": chemistry_pm_gates_ready,
                "unsatisfied_donor_acceptor_fixture_count": (
                    chemistry_kpi["unsatisfied_donor_acceptor_fixture_count"]
                ),
                "unsatisfied_donor_count": chemistry_kpi["unsatisfied_donor_count"],
                "unsatisfied_acceptor_count": chemistry_kpi["unsatisfied_acceptor_count"],
                "unsatisfied_donor_acceptor_pose_count": 3 if chemistry_pm_gates_ready else 0,
                "overanchored_decoy_rejection": chemistry_pm_gates_ready,
                "chirality_preservation_fixture_count": (
                    chemistry_kpi["chirality_preservation_fixture_count"]
                ),
                "unassigned_chirality_blocked_fixture_count": (
                    chemistry_kpi["unassigned_chirality_blocked_fixture_count"]
                ),
                "chirality_preservation_ready": chemistry_pm_gates_ready,
                "ring_validity_fixture_count": chemistry_kpi["ring_validity_fixture_count"],
                "ring_validity_ready": chemistry_pm_gates_ready,
                "tautomer_validity_fixture_count": chemistry_kpi["tautomer_validity_fixture_count"],
                "tautomer_validity_ready": chemistry_pm_gates_ready,
                "protonation_validity_fixture_count": chemistry_kpi["protonation_validity_fixture_count"],
                "protonation_validity_ready": chemistry_pm_gates_ready,
                "confidence_calibration_report_ready": confidence_calibration.get("ready") is True,
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
        },
    }


def _rocm_packet(*, ready: bool) -> dict:
    return {
        "summary": {
            "status": "rocm_environment_manifest_ready",
            "manifest_ready": True,
            "commercial_compute_default": "rocm_hip",
            "torch_rocm_ready": ready,
            "visible_device_count": 1 if ready else 0,
            "device_nodes_ready": ready,
            "production_execution_ready": ready,
            "cpu_fallback_allowed_for_product": False,
        }
    }


def _image_preflight_packet(
    *,
    clean_ready: bool,
    docker_cli_present: bool = True,
    blocker_codes: list[str] | None = None,
) -> dict:
    blockers = [{"code": code} for code in (blocker_codes or [])]
    return {
        "summary": {
            "status": "product_image_smoke_preflight_ready" if clean_ready else "blocked_product_image_smoke_preflight",
            "preflight_ready": clean_ready,
            "docker_cli_present": docker_cli_present,
            "next_required_step": (
                "Attach clean container smoke receipt to the product evidence bundle."
                if clean_ready
                else (
                    "Expose a Docker CLI/daemon to this ROCm host, then run PRODUCT_IMAGE_VERIFY_MODE=rocm-runtime "
                    "bash deploy/verify_product_image.sh."
                    if not docker_cli_present
                    else "Run PRODUCT_IMAGE_VERIFY_MODE=rocm-runtime bash deploy/verify_product_image.sh on a Docker-enabled ROCm host."
                )
            ),
            "clean_container_smoke_ready": clean_ready,
            "receipt_present": clean_ready,
            "receipt_status": "product_image_smoke_ready" if clean_ready else "",
            "receipt_mode": "rocm-runtime" if clean_ready else "",
            "receipt_simulate_missing_profile_http": 422 if clean_ready else 0,
            "container_runtime_receipt_ready": clean_ready,
            "container_runtime_proof_schema_version": "rocm_container_runtime_proof_v1" if clean_ready else "",
            "container_runtime_in_container": clean_ready,
            "container_runtime_device_nodes_ready": clean_ready,
            "container_runtime_torch_rocm_ready": clean_ready,
            "container_runtime_torch_cuda_available": clean_ready,
            "container_runtime_visible_device_count": 1 if clean_ready else 0,
            "container_runtime_rust_hip_backend_enabled": clean_ready,
            "runtime_neighbor_release_scaling_ready": clean_ready,
            "runtime_neighbor_release_scaling_status": (
                "runtime_neighbor_release_scaling_ready" if clean_ready else ""
            ),
            "runtime_neighbor_release_atom_counts_ready": clean_ready,
            "runtime_neighbor_release_atom_counts": [1000, 2000, 4000, 8000] if clean_ready else [],
            "runtime_neighbor_release_pair_count_slope": 1.0 if clean_ready else 0.0,
            "runtime_neighbor_release_pair_count_r2": 1.0 if clean_ready else 0.0,
            "runtime_neighbor_release_nxn_allocation_observed": False,
            "product_runner_smoke_ready": clean_ready,
            "product_runner_claim_metadata_ready": clean_ready,
            "tier_alpha_result_manifest_signature_verified": clean_ready,
            "tier_alpha_result_manifest_status": "completed" if clean_ready else "",
            "backmapping_runner_claim_metadata_ready": clean_ready,
            "backmapping_ligand_topology_valid": clean_ready,
            "backmapping_ligand_topology_claim_safe": clean_ready,
            "backmapping_ligand_topology_claim_safe_row_count": 2 if clean_ready else 0,
            "backmapping_ligand_topology_invalid_row_count": 0,
            "backmapping_ligand_topology_schema_version": "ligand_topology_validity_v1"
            if clean_ready
            else "",
            "backmapping_ligand_topology_schema_ready_row_count": 2 if clean_ready else 0,
            "backmapping_ligand_topology_receipt_ready": clean_ready,
            "backmapping_hbond_evidence_schema_version": "hbond_evidence_v1" if clean_ready else "",
            "backmapping_hbond_claim_metadata_schema_version": "hbond_evidence_v1" if clean_ready else "",
            "backmapping_hbond_claim_metadata_schema_ready_row_count": 2 if clean_ready else 0,
            "backmapping_onsps_backmap_schema_version": "onsps_backmap_evidence_v1" if clean_ready else "",
            "backmapping_hbond_evaluated_row_count": 2 if clean_ready else 0,
            "backmapping_onsps_backmap_claim_safe_row_count": 1 if clean_ready else 0,
            "backmapping_hbond_evidence_receipt_ready": clean_ready,
            "backmapping_onsps_backmap_receipt_ready": clean_ready,
        },
        "blockers": blockers,
    }


def _artifact_specs(tmp_path: Path, *, kpi_packet: dict | None = None) -> list[dict[str, object]]:
    kpi_packet = kpi_packet or _kpi_packet(ready=True)
    runtime_plot = _write(
        tmp_path / "runtime_scaling.svg",
        (
            "<svg xmlns=\"http://www.w3.org/2000/svg\">"
            "<text>Capped neighbor pairs</text><text>Pair-count scaling advisory</text>"
            "</svg>\n"
        ),
    )
    runtime_scaling = kpi_packet["runtime_kpi"]["neighbor_cap_scaling"]
    runtime_scaling["plot_path"] = str(runtime_plot)
    runtime_scaling["plot_sha256"] = _sha256(runtime_plot)
    runtime_scaling["plot_size_bytes"] = runtime_plot.stat().st_size
    pm_runtime = kpi_packet["pm_kpi_summary"]["runtime"]
    pm_runtime["runtime_neighbor_cap_scaling_plot_path"] = str(runtime_plot)
    pm_runtime["runtime_neighbor_cap_scaling_plot_sha256"] = _sha256(runtime_plot)
    return [
        {
            "artifact_id": "kpi_json",
            "artifact_path": str(_write(tmp_path / "kpi.json", json.dumps(kpi_packet))),
            "role": "local_pc_runtime_report",
            "required": True,
        },
        {
            "artifact_id": "kpi_md",
            "artifact_path": str(_write(tmp_path / "kpi.md")),
            "role": "human_readable_runtime_report",
            "required": True,
        },
        {
            "artifact_id": "runtime_scaling_plot",
            "artifact_path": str(runtime_plot),
            "role": "runtime_neighbor_cap_scaling_plot",
            "required": True,
        },
        {
            "artifact_id": "rocm",
            "artifact_path": str(_write(tmp_path / "rocm.json", json.dumps(_rocm_packet(ready=True)))),
            "role": "gpu_rocm_hip_runtime_gate",
            "required": True,
        },
        {
            "artifact_id": "image_preflight",
            "artifact_path": str(_write(tmp_path / "image_preflight.json", json.dumps(_image_preflight_packet(clean_ready=True)))),
            "role": "clean_container_smoke_gate",
            "required": True,
        },
        {
            "artifact_id": "doc",
            "artifact_path": str(_write(tmp_path / "next.md")),
            "role": "engineering_plan",
            "required": True,
        },
    ]


def test_ai_md_product_evidence_bundle_exports_claim_ready_tar(tmp_path: Path) -> None:
    out_tar = tmp_path / "bundle.tar.gz"
    kpi_packet = _kpi_packet(ready=True)

    payload = mod.build_payload(
        kpi_packet=kpi_packet,
        rocm_manifest_packet=_rocm_packet(ready=True),
        product_image_preflight_packet=_image_preflight_packet(clean_ready=True),
        artifact_specs=_artifact_specs(tmp_path, kpi_packet=kpi_packet),
        out_tar=str(out_tar),
    )

    summary = payload["summary"]
    assert summary["status"] == "ai_md_product_evidence_bundle_ready"
    assert summary["bundle_export_ready"] is True
    assert summary["product_claim_ready"] is True
    assert summary["kpi_failed_gate_count"] == 0
    assert summary["kpi_failed_gate_ids"] == []
    assert summary["runner_claim_metadata_signed"] is True
    assert summary["force_residual_summary_signed"] is True
    assert summary["force_term_claim_metadata_ready"] is True
    assert summary["force_term_result_contract_ready"] is True
    assert summary["forcefield_energy_forces_contract_ready"] is True
    assert summary["guarded_force_term_plugin_ready"] is True
    assert summary["runtime_neighbor_cap_scaling_plot_ready"] is True
    assert summary["runtime_neighbor_cap_scaling_plot_path"].endswith("runtime_scaling.svg")
    assert len(summary["runtime_neighbor_cap_scaling_plot_sha256"]) == 64
    assert summary["onsps_backmap_evidence_schema_ready"] is True
    assert summary["core_forcefield_bridge_ready"] is True
    assert summary["core_compatibility_layer_ready"] is True
    assert summary["job_store_lazy_factory_ready"] is True
    assert summary["allowlisted_runner_shim_contract_ready"] is True
    assert summary["product_runner_engine_imports_ready"] is True
    assert summary["product_runner_no_core_imports_ready"] is True
    assert summary["topk_delivery_engine_owned_ready"] is True
    assert summary["backmapping_scoring_engine_owned_ready"] is True
    assert summary["htvs_pipeline_engine_owned_ready"] is True
    assert summary["product_runner_engine_owned_ready"] is True
    assert summary["chemistry_pm_gates_ready"] is True
    assert summary["pose_ranking_hbond_benchmark_ready"] is True
    assert summary["confidence_calibration_report_ready"] is True
    assert summary["confidence_calibration_status"] == "confidence_calibration_report_ready"
    assert summary["confidence_calibration_row_count"] == 6
    assert summary["confidence_calibration_expected_calibration_error"] <= 0.2
    assert summary["confidence_calibration_brier_score"] <= 0.2
    assert summary["pose_ranking_hbond_row_contracts_ready"] is True
    assert summary["pose_ranking_hbond_row_contract_pass_count"] == 6
    assert summary["hbond_recovery_pose_count"] == 1
    assert summary["hbond_recovery_benchmark_ready"] is True
    assert summary["hbond_recovery_benchmark_schema_version"] == "hbond_recovery_benchmark_v1"
    assert summary["hbond_recovery_benchmark_fixture_count"] == 3
    assert summary["hbond_recovery_benchmark_contract_pass_count"] == 3
    assert summary["overanchored_decoy_rejection"] is True
    assert summary["unsatisfied_donor_acceptor_detection"] is True
    assert summary["kpi_claim_metadata_gates_validated"] is True
    assert summary["kpi_claim_metadata_gate_count"] == 1
    assert summary["kpi_claim_metadata_gate_validated_count"] == 1
    assert summary["rocm_hip_rust_runtime_ready"] is True
    assert summary["clean_container_smoke_ready"] is True
    assert summary["clean_container_missing_requirement_count"] == 0
    assert summary["clean_container_missing_requirements"] == []
    assert summary["product_image_preflight_status"] == "product_image_smoke_preflight_ready"
    assert summary["product_image_preflight_ready"] is True
    assert summary["product_image_docker_cli_present"] is True
    assert summary["product_image_preflight_blocker_count"] == 0
    assert summary["product_image_preflight_blocker_codes"] == []
    assert summary["product_image_receipt_present"] is True
    assert summary["container_runtime_receipt_ready"] is True
    assert summary["container_runtime_proof_schema_version"] == "rocm_container_runtime_proof_v1"
    assert summary["container_runtime_in_container"] is True
    assert summary["container_runtime_visible_device_count"] == 1
    assert summary["container_runtime_rust_hip_backend_enabled"] is True
    assert summary["product_runner_smoke_ready"] is True
    assert summary["product_runner_claim_metadata_ready"] is True
    assert summary["product_image_receipt_mode"] == "rocm-runtime"
    assert summary["tier_alpha_result_manifest_signature_verified"] is True
    assert summary["tier_alpha_result_manifest_status"] == "completed"
    assert summary["backmapping_runner_claim_metadata_ready"] is True
    assert summary["backmapping_ligand_topology_schema_version"] == "ligand_topology_validity_v1"
    assert summary["backmapping_ligand_topology_schema_ready_row_count"] == 2
    assert summary["backmapping_ligand_topology_receipt_ready"] is True
    assert summary["backmapping_ligand_topology_valid"] is True
    assert summary["backmapping_ligand_topology_claim_safe"] is True
    assert summary["backmapping_ligand_topology_claim_safe_row_count"] == 2
    assert summary["backmapping_ligand_topology_invalid_row_count"] == 0
    assert summary["backmapping_hbond_evidence_receipt_ready"] is True
    assert summary["backmapping_onsps_backmap_receipt_ready"] is True
    assert summary["backmapping_hbond_evidence_schema_version"] == "hbond_evidence_v1"
    assert summary["backmapping_hbond_claim_metadata_schema_version"] == "hbond_evidence_v1"
    assert summary["backmapping_hbond_claim_metadata_schema_ready_row_count"] == 2
    assert summary["backmapping_onsps_backmap_schema_version"] == "onsps_backmap_evidence_v1"
    assert summary["backmapping_hbond_evaluated_row_count"] == 2
    assert summary["backmapping_onsps_backmap_claim_safe_row_count"] == 1
    assert summary["cpu_fallback_allowed_for_product"] is False
    assert summary["bundle_validation_pass"] is True
    assert summary["bundle_validation_error_count"] == 0
    assert summary["bundle_validation_errors"] == []
    assert summary["source_artifacts_fresh"] is True
    assert summary["source_artifact_fresh_count"] == summary["included_artifact_count"]
    assert summary["source_artifact_stale_count"] == 0
    assert summary["source_artifact_stale_ids"] == []
    assert len(summary["bundle_tar_sha256"]) == 64
    assert payload["blockers"] == []
    assert all(row["execution_enabled"] is False for row in payload["rows"])
    assert all(row["external_state_mutated"] is False for row in payload["rows"])

    with tarfile.open(out_tar, "r:gz") as tar:
        assert set(tar.getnames()) == {row["bundle_arcname"] for row in payload["rows"]}
    validation = mod.validate_product_evidence_bundle(bundle_packet=payload)
    assert validation["bundle_validation_pass"] is True
    assert validation["kpi_claim_metadata_gates_validated"] is True
    assert validation["bundle_validation_error_count"] == 0
    assert validation["source_artifacts_fresh"] is True

    source_kpi = Path(payload["rows"][0]["artifact_path"])
    source_kpi.write_text("local source changed after tar export\n", encoding="utf-8")
    validation_after_local_change = mod.validate_product_evidence_bundle(bundle_packet=payload)
    assert validation_after_local_change["bundle_validation_pass"] is True
    assert validation_after_local_change["bundle_validation_error_count"] == 0
    assert validation_after_local_change["source_artifacts_fresh"] is False
    assert validation_after_local_change["source_artifact_stale_count"] == 1
    assert validation_after_local_change["source_artifact_stale_ids"] == ["kpi_json"]


def test_ai_md_product_evidence_bundle_keeps_local_claim_ready_when_self_hosted_runners_missing(
    tmp_path: Path,
) -> None:
    out_tar = tmp_path / "bundle.tar.gz"
    kpi_packet = _kpi_packet(ready=True)
    ci_packet = {
        "summary": {
            "status": "blocked_product_ci_runtime_gate",
            "runtime_gate_ready": False,
            "remote_product_ci_green": False,
            "github_actions_started": False,
            "external_blocker": True,
            "blocker_code": "github_actions_billing_or_spending_limit",
            "billing_free_self_hosted_path_recommended": True,
            "billing_free_self_hosted_api_worker_command": (
                "gh workflow run product-api-worker.yml -f runner_labels_json='[\"self-hosted\",\"linux\"]'"
            ),
            "billing_free_self_hosted_rocm_runtime_command": (
                "gh workflow run product-image-smoke.yml -f verify_mode=rocm-runtime"
            ),
            "hosted_spending_limit_increase_required": False,
            "self_hosted_runner_inventory_present": True,
            "self_hosted_runner_total_count": 0,
            "self_hosted_linux_runner_online": False,
            "self_hosted_linux_runner_count": 0,
            "self_hosted_rocm_runner_online": False,
            "self_hosted_rocm_runner_count": 0,
            "self_hosted_runner_inventory_external_state_mutated": False,
            "self_hosted_runner_host_preflight_present": True,
            "self_hosted_runner_host_preflight_status": "blocked_github_self_hosted_runner_registration_required",
            "self_hosted_runner_host_local_ready": True,
            "self_hosted_runner_host_repo_ready": False,
            "self_hosted_runner_host_registration_required": True,
            "self_hosted_runner_host_github_registration_token_requested": False,
            "self_hosted_runner_host_external_state_mutated": False,
            "latest_github_actions_record_kst_date": "2026-06-21",
            "workflow_dispatch_executed": False,
            "external_state_mutated": False,
        }
    }

    payload = mod.build_payload(
        kpi_packet=kpi_packet,
        rocm_manifest_packet=_rocm_packet(ready=True),
        product_image_preflight_packet=_image_preflight_packet(clean_ready=True),
        artifact_specs=_artifact_specs(tmp_path, kpi_packet=kpi_packet),
        product_ci_runtime_gate_packet=ci_packet,
        out_tar=str(out_tar),
    )
    summary = payload["summary"]

    assert summary["bundle_validation_pass"] is True
    assert summary["product_claim_ready"] is True
    assert summary["release_claim_ready"] is False
    assert summary["release_claim_blocked_reason"] == "github_actions_billing_or_spending_limit"
    assert summary["product_ci_billing_free_self_hosted_path_recommended"] is True
    assert summary["product_ci_self_hosted_runner_inventory_present"] is True
    assert summary["product_ci_self_hosted_runner_total_count"] == 0
    assert summary["product_ci_self_hosted_linux_runner_online"] is False
    assert summary["product_ci_self_hosted_rocm_runner_online"] is False
    assert "register/start repo self-hosted Linux and ROCm runners" in summary["next_required_step"]


def test_ai_md_product_evidence_bundle_exports_blocked_claim_when_gpu_not_visible(tmp_path: Path) -> None:
    out_tar = tmp_path / "bundle.tar.gz"

    payload = mod.build_payload(
        kpi_packet=_kpi_packet(ready=False),
        rocm_manifest_packet=_rocm_packet(ready=False),
        product_image_preflight_packet=_image_preflight_packet(clean_ready=True),
        artifact_specs=_artifact_specs(tmp_path),
        out_tar=str(out_tar),
    )

    summary = payload["summary"]
    assert summary["status"] == "ai_md_product_evidence_bundle_ready"
    assert summary["bundle_export_ready"] is True
    assert summary["product_claim_ready"] is False
    assert summary["rocm_hip_rust_runtime_ready"] is False
    assert {"code": "rocm_hip_rust_runtime_not_ready"} in payload["blockers"]
    assert summary["kpi_failed_gate_count"] == 1
    assert summary["kpi_failed_gate_ids"] == ["clean_install_success"]
    assert {
        "code": "kpi_report_not_ready",
        "failed_gate_ids": ["clean_install_success"],
    } in payload["blockers"]


def test_ai_md_product_evidence_bundle_blocks_product_claim_without_clean_container_smoke(tmp_path: Path) -> None:
    out_tar = tmp_path / "bundle.tar.gz"

    payload = mod.build_payload(
        kpi_packet=_kpi_packet(ready=True),
        rocm_manifest_packet=_rocm_packet(ready=True),
        product_image_preflight_packet=_image_preflight_packet(clean_ready=False),
        artifact_specs=_artifact_specs(tmp_path),
        out_tar=str(out_tar),
    )

    summary = payload["summary"]
    assert summary["status"] == "ai_md_product_evidence_bundle_ready"
    assert summary["bundle_export_ready"] is True
    assert summary["product_claim_ready"] is False
    assert summary["clean_container_smoke_ready"] is False
    assert summary["clean_container_missing_requirement_count"] > 0
    assert "clean_container_smoke_receipt_ready" in summary["clean_container_missing_requirements"]
    assert "product_image_receipt_mode_rocm_runtime" in summary["clean_container_missing_requirements"]
    assert "container_runtime_receipt_ready" in summary["clean_container_missing_requirements"]
    assert summary["next_required_step"].startswith("Run PRODUCT_IMAGE_VERIFY_MODE=rocm-runtime")
    clean_container_blocker = next(
        row for row in payload["blockers"] if row["code"] == "clean_container_smoke_not_ready"
    )
    assert clean_container_blocker["missing_requirements"] == summary["clean_container_missing_requirements"]


def test_ai_md_product_evidence_bundle_surfaces_product_image_preflight_blockers(tmp_path: Path) -> None:
    out_tar = tmp_path / "bundle.tar.gz"

    payload = mod.build_payload(
        kpi_packet=_kpi_packet(ready=True),
        rocm_manifest_packet=_rocm_packet(ready=True),
        product_image_preflight_packet=_image_preflight_packet(
            clean_ready=False,
            docker_cli_present=False,
            blocker_codes=["docker_cli_missing"],
        ),
        artifact_specs=_artifact_specs(tmp_path),
        out_tar=str(out_tar),
    )

    summary = payload["summary"]
    assert summary["status"] == "ai_md_product_evidence_bundle_ready"
    assert summary["product_claim_ready"] is False
    assert summary["rocm_hip_rust_runtime_ready"] is True
    assert summary["clean_container_smoke_ready"] is False
    assert summary["product_image_preflight_status"] == "blocked_product_image_smoke_preflight"
    assert summary["product_image_preflight_ready"] is False
    assert summary["product_image_docker_cli_present"] is False
    assert summary["product_image_preflight_blocker_count"] == 1
    assert summary["product_image_preflight_blocker_codes"] == ["docker_cli_missing"]
    assert summary["product_image_preflight_next_required_step"].startswith("Expose a Docker CLI/daemon")
    clean_container_blocker = next(
        row for row in payload["blockers"] if row["code"] == "clean_container_smoke_not_ready"
    )
    assert "clean_container_smoke_receipt_ready" in clean_container_blocker["missing_requirements"]
    assert {
        "code": "product_image_preflight_blocked",
        "preflight_blockers": ["docker_cli_missing"],
    } in payload["blockers"]


def test_ai_md_product_evidence_bundle_blocks_topology_factory_smoke_without_empty_protein_gate(
    tmp_path: Path,
) -> None:
    out_tar = tmp_path / "bundle.tar.gz"
    kpi_packet = _kpi_packet(ready=True)
    topology_smoke = kpi_packet["product_kpi"]["engine_topology_factory_facade_smoke"]
    topology_smoke["empty_protein_blocked_reason"] = ""
    topology_smoke["invalid_pocket_blocked_reason"] = ""
    topology_smoke["invalid_pocket_residue_indices_valid"] = True

    payload = mod.build_payload(
        kpi_packet=kpi_packet,
        rocm_manifest_packet=_rocm_packet(ready=True),
        product_image_preflight_packet=_image_preflight_packet(clean_ready=True),
        artifact_specs=_artifact_specs(tmp_path, kpi_packet=kpi_packet),
        out_tar=str(out_tar),
    )

    summary = payload["summary"]
    assert summary["bundle_export_ready"] is True
    assert summary["bundle_validation_pass"] is False
    assert summary["product_claim_ready"] is False
    assert {"code": "kpi_claim_metadata_gates_not_validated"} in payload["blockers"]
    assert any(
        error.startswith("kpi_topology_factory_empty_protein_blocker_invalid:")
        for error in summary["bundle_validation_errors"]
    )
    assert any(
        error.startswith("kpi_topology_factory_invalid_pocket_blocker_invalid:")
        for error in summary["bundle_validation_errors"]
    )
    assert any(
        error.startswith("kpi_topology_factory_invalid_pocket_not_blocked:")
        for error in summary["bundle_validation_errors"]
    )


def test_ai_md_product_evidence_bundle_rejects_clean_container_without_backmapping_schema_receipt(tmp_path: Path) -> None:
    out_tar = tmp_path / "bundle.tar.gz"
    image_packet = _image_preflight_packet(clean_ready=True)
    image_packet["summary"]["backmapping_hbond_evidence_schema_version"] = ""
    image_packet["summary"]["backmapping_hbond_evaluated_row_count"] = 0
    image_packet["summary"]["backmapping_hbond_evidence_receipt_ready"] = False

    payload = mod.build_payload(
        kpi_packet=_kpi_packet(ready=True),
        rocm_manifest_packet=_rocm_packet(ready=True),
        product_image_preflight_packet=image_packet,
        artifact_specs=_artifact_specs(tmp_path),
        out_tar=str(out_tar),
    )

    summary = payload["summary"]
    assert summary["bundle_export_ready"] is True
    assert summary["product_claim_ready"] is False
    assert summary["clean_container_smoke_ready"] is False
    assert summary["product_runner_smoke_ready"] is True
    assert summary["product_runner_claim_metadata_ready"] is True
    assert summary["backmapping_runner_claim_metadata_ready"] is True
    assert summary["backmapping_hbond_evidence_receipt_ready"] is False
    assert summary["backmapping_onsps_backmap_receipt_ready"] is True
    assert "backmapping_hbond_evidence_receipt_ready" in summary["clean_container_missing_requirements"]
    assert any(row["code"] == "clean_container_smoke_not_ready" for row in payload["blockers"])


def test_ai_md_product_evidence_bundle_rejects_clean_container_without_ligand_topology_receipt(tmp_path: Path) -> None:
    out_tar = tmp_path / "bundle.tar.gz"
    image_packet = _image_preflight_packet(clean_ready=True)
    image_packet["summary"]["backmapping_ligand_topology_claim_safe"] = False
    image_packet["summary"]["backmapping_ligand_topology_claim_safe_row_count"] = 0
    image_packet["summary"]["backmapping_ligand_topology_invalid_row_count"] = 1
    image_packet["summary"]["backmapping_ligand_topology_receipt_ready"] = False

    payload = mod.build_payload(
        kpi_packet=_kpi_packet(ready=True),
        rocm_manifest_packet=_rocm_packet(ready=True),
        product_image_preflight_packet=image_packet,
        artifact_specs=_artifact_specs(tmp_path),
        out_tar=str(out_tar),
    )

    summary = payload["summary"]
    assert summary["bundle_export_ready"] is True
    assert summary["product_claim_ready"] is False
    assert summary["clean_container_smoke_ready"] is False
    assert summary["backmapping_ligand_topology_valid"] is True
    assert summary["backmapping_ligand_topology_claim_safe"] is False
    assert summary["backmapping_ligand_topology_receipt_ready"] is False
    assert "backmapping_ligand_topology_receipt_ready" in summary["clean_container_missing_requirements"]
    assert any(row["code"] == "clean_container_smoke_not_ready" for row in payload["blockers"])


def test_ai_md_product_evidence_bundle_rejects_clean_container_without_ligand_topology_schema(tmp_path: Path) -> None:
    out_tar = tmp_path / "bundle.tar.gz"
    image_packet = _image_preflight_packet(clean_ready=True)
    image_packet["summary"]["backmapping_ligand_topology_schema_version"] = ""
    image_packet["summary"]["backmapping_ligand_topology_schema_ready_row_count"] = 0

    payload = mod.build_payload(
        kpi_packet=_kpi_packet(ready=True),
        rocm_manifest_packet=_rocm_packet(ready=True),
        product_image_preflight_packet=image_packet,
        artifact_specs=_artifact_specs(tmp_path),
        out_tar=str(out_tar),
    )

    summary = payload["summary"]
    assert summary["bundle_export_ready"] is True
    assert summary["product_claim_ready"] is False
    assert summary["clean_container_smoke_ready"] is False
    assert summary["backmapping_ligand_topology_schema_version"] == ""
    assert summary["backmapping_ligand_topology_schema_ready_row_count"] == 0
    assert summary["backmapping_ligand_topology_receipt_ready"] is False
    assert "backmapping_ligand_topology_receipt_ready" in summary["clean_container_missing_requirements"]
    assert any(row["code"] == "clean_container_smoke_not_ready" for row in payload["blockers"])


def test_ai_md_product_evidence_bundle_rejects_clean_container_without_runtime_proof(tmp_path: Path) -> None:
    out_tar = tmp_path / "bundle.tar.gz"
    image_packet = _image_preflight_packet(clean_ready=True)
    image_packet["summary"]["container_runtime_receipt_ready"] = False
    image_packet["summary"]["container_runtime_proof_schema_version"] = ""
    image_packet["summary"]["container_runtime_in_container"] = False
    image_packet["summary"]["container_runtime_visible_device_count"] = 0
    image_packet["summary"]["container_runtime_rust_hip_backend_enabled"] = False

    payload = mod.build_payload(
        kpi_packet=_kpi_packet(ready=True),
        rocm_manifest_packet=_rocm_packet(ready=True),
        product_image_preflight_packet=image_packet,
        artifact_specs=_artifact_specs(tmp_path),
        out_tar=str(out_tar),
    )

    summary = payload["summary"]
    assert summary["bundle_export_ready"] is True
    assert summary["product_claim_ready"] is False
    assert summary["clean_container_smoke_ready"] is False
    assert summary["container_runtime_receipt_ready"] is False
    assert summary["container_runtime_in_container"] is False
    assert summary["container_runtime_visible_device_count"] == 0
    assert summary["container_runtime_rust_hip_backend_enabled"] is False
    assert summary["product_runner_claim_metadata_ready"] is True
    assert "container_runtime_receipt_ready" in summary["clean_container_missing_requirements"]
    assert any(row["code"] == "clean_container_smoke_not_ready" for row in payload["blockers"])


def test_ai_md_product_evidence_bundle_blocks_product_claim_without_signed_runner_metadata_gate(tmp_path: Path) -> None:
    out_tar = tmp_path / "bundle.tar.gz"
    kpi_packet = _kpi_packet(ready=True, runner_claim_metadata_signed=False)

    payload = mod.build_payload(
        kpi_packet=kpi_packet,
        rocm_manifest_packet=_rocm_packet(ready=True),
        product_image_preflight_packet=_image_preflight_packet(clean_ready=True),
        artifact_specs=_artifact_specs(tmp_path, kpi_packet=kpi_packet),
        out_tar=str(out_tar),
    )

    summary = payload["summary"]
    assert summary["bundle_export_ready"] is True
    assert summary["bundle_validation_pass"] is False
    assert summary["product_claim_ready"] is False
    assert summary["runner_claim_metadata_signed"] is False
    assert summary["force_residual_summary_signed"] is True
    assert summary["kpi_claim_metadata_gates_validated"] is False
    assert {"code": "runner_claim_metadata_not_signed"} in payload["blockers"]
    assert {"code": "kpi_claim_metadata_gates_not_validated"} in payload["blockers"]
    assert any(
        error.startswith("kpi_runner_claim_metadata_not_signed:")
        for error in summary["bundle_validation_errors"]
    )
    assert any(
        error.startswith("kpi_signed_manifest_verification_gate_missing:")
        for error in summary["bundle_validation_errors"]
    )
    assert any(
        error.startswith("pm_signed_manifest_verification_gate_missing:")
        for error in summary["bundle_validation_errors"]
    )


def test_ai_md_product_evidence_bundle_blocks_without_signed_manifest_verification_gate(
    tmp_path: Path,
) -> None:
    out_tar = tmp_path / "bundle.tar.gz"
    kpi_packet = _kpi_packet(ready=True)
    kpi_packet["product_kpi"]["signed_manifest_verification_pass"] = False
    kpi_packet["pm_kpi_summary"]["product"]["signed_manifest_verification_pass"] = False

    payload = mod.build_payload(
        kpi_packet=kpi_packet,
        rocm_manifest_packet=_rocm_packet(ready=True),
        product_image_preflight_packet=_image_preflight_packet(clean_ready=True),
        artifact_specs=_artifact_specs(tmp_path, kpi_packet=kpi_packet),
        out_tar=str(out_tar),
    )

    summary = payload["summary"]
    assert summary["bundle_export_ready"] is True
    assert summary["bundle_validation_pass"] is False
    assert summary["product_claim_ready"] is False
    assert {"code": "kpi_claim_metadata_gates_not_validated"} in payload["blockers"]
    assert any(
        error.startswith("kpi_signed_manifest_verification_gate_missing:")
        for error in summary["bundle_validation_errors"]
    )
    assert any(
        error.startswith("pm_signed_manifest_verification_gate_missing:")
        for error in summary["bundle_validation_errors"]
    )


def test_ai_md_product_evidence_bundle_blocks_bundle_validation_pm_mismatch(
    tmp_path: Path,
) -> None:
    out_tar = tmp_path / "bundle.tar.gz"
    kpi_packet = _kpi_packet(ready=True)
    kpi_packet["product_kpi"]["bundle_validation_pass"] = False
    kpi_packet["pm_kpi_summary"]["product"]["bundle_validation_pass"] = True

    payload = mod.build_payload(
        kpi_packet=kpi_packet,
        rocm_manifest_packet=_rocm_packet(ready=True),
        product_image_preflight_packet=_image_preflight_packet(clean_ready=True),
        artifact_specs=_artifact_specs(tmp_path, kpi_packet=kpi_packet),
        out_tar=str(out_tar),
    )

    summary = payload["summary"]
    assert summary["bundle_export_ready"] is True
    assert summary["bundle_validation_pass"] is False
    assert summary["product_claim_ready"] is False
    assert {"code": "kpi_claim_metadata_gates_not_validated"} in payload["blockers"]
    assert any(
        error.startswith("pm_product_bundle_validation_gate_mismatch:")
        for error in summary["bundle_validation_errors"]
    )


def test_ai_md_product_evidence_bundle_blocks_product_pm_missing_requirement_mismatch(
    tmp_path: Path,
) -> None:
    out_tar = tmp_path / "bundle.tar.gz"
    kpi_packet = _kpi_packet(ready=True)
    pm_product = kpi_packet["pm_kpi_summary"]["product"]
    pm_product["clean_install_missing_requirement_count"] = 1
    pm_product["clean_install_missing_requirements"] = ["unexpected_clean_install_gap"]
    pm_product["product_image_preflight_blocker_codes"] = ["unexpected_blocker"]
    pm_product["clean_container_missing_requirement_count"] = 1
    pm_product["clean_container_missing_requirements"] = ["unexpected_container_gap"]

    payload = mod.build_payload(
        kpi_packet=kpi_packet,
        rocm_manifest_packet=_rocm_packet(ready=True),
        product_image_preflight_packet=_image_preflight_packet(clean_ready=True),
        artifact_specs=_artifact_specs(tmp_path, kpi_packet=kpi_packet),
        out_tar=str(out_tar),
    )

    summary = payload["summary"]
    assert summary["bundle_export_ready"] is True
    assert summary["bundle_validation_pass"] is False
    assert summary["product_claim_ready"] is False
    assert {"code": "kpi_claim_metadata_gates_not_validated"} in payload["blockers"]
    assert any(
        error.startswith("pm_product_clean_install_missing_count_mismatch:")
        for error in summary["bundle_validation_errors"]
    )
    assert any(
        error.startswith("pm_product_clean_install_missing_requirements_mismatch:")
        for error in summary["bundle_validation_errors"]
    )
    assert any(
        error.startswith("pm_product_image_preflight_blocker_codes_mismatch:")
        for error in summary["bundle_validation_errors"]
    )
    assert any(
        error.startswith("pm_product_clean_container_missing_count_mismatch:")
        for error in summary["bundle_validation_errors"]
    )
    assert any(
        error.startswith("pm_product_clean_container_missing_requirements_mismatch:")
        for error in summary["bundle_validation_errors"]
    )


def test_ai_md_product_evidence_bundle_blocks_source_artifact_freshness_mismatch(
    tmp_path: Path,
) -> None:
    out_tar = tmp_path / "bundle.tar.gz"
    kpi_packet = _kpi_packet(ready=True)
    product = kpi_packet["product_kpi"]
    pm_product = kpi_packet["pm_kpi_summary"]["product"]
    product["source_artifacts_fresh"] = False
    product["source_artifact_fresh_count"] = 3
    product["source_artifact_stale_count"] = 1
    product["source_artifact_stale_ids"] = ["kpi_json"]
    pm_product["source_artifacts_fresh"] = True
    pm_product["source_artifact_fresh_count"] = 4
    pm_product["source_artifact_stale_count"] = 0
    pm_product["source_artifact_stale_ids"] = []

    payload = mod.build_payload(
        kpi_packet=kpi_packet,
        rocm_manifest_packet=_rocm_packet(ready=True),
        product_image_preflight_packet=_image_preflight_packet(clean_ready=True),
        artifact_specs=_artifact_specs(tmp_path, kpi_packet=kpi_packet),
        out_tar=str(out_tar),
    )

    summary = payload["summary"]
    assert summary["bundle_export_ready"] is True
    assert summary["bundle_validation_pass"] is False
    assert summary["product_claim_ready"] is False
    assert {"code": "kpi_claim_metadata_gates_not_validated"} in payload["blockers"]
    assert any(
        error.startswith("kpi_source_artifacts_not_fresh:")
        for error in summary["bundle_validation_errors"]
    )
    assert any(
        error.startswith("pm_product_source_artifact_fresh_count_mismatch:")
        for error in summary["bundle_validation_errors"]
    )
    assert any(
        error.startswith("pm_product_source_artifact_stale_count_mismatch:")
        for error in summary["bundle_validation_errors"]
    )
    assert any(
        error.startswith("pm_product_source_artifact_stale_ids_mismatch:")
        for error in summary["bundle_validation_errors"]
    )


def test_ai_md_product_evidence_bundle_blocks_when_manifest_claim_is_not_blocked(tmp_path: Path) -> None:
    out_tar = tmp_path / "bundle.tar.gz"
    kpi_packet = _kpi_packet(ready=True)
    manifest_smoke = kpi_packet["product_kpi"]["runner_claim_metadata_manifest_smoke"]
    manifest_smoke["manifest_claim_safe"] = True
    manifest_smoke["manifest_blocked_reason"] = ""
    kpi_packet["product_kpi"]["blocked_claim_correctly_blocked"] = False
    kpi_packet["pm_kpi_summary"]["product"]["blocked_claim_correctly_blocked"] = False

    payload = mod.build_payload(
        kpi_packet=kpi_packet,
        rocm_manifest_packet=_rocm_packet(ready=True),
        product_image_preflight_packet=_image_preflight_packet(clean_ready=True),
        artifact_specs=_artifact_specs(tmp_path, kpi_packet=kpi_packet),
        out_tar=str(out_tar),
    )

    summary = payload["summary"]
    assert summary["bundle_export_ready"] is True
    assert summary["bundle_validation_pass"] is False
    assert summary["product_claim_ready"] is False
    assert {"code": "kpi_claim_metadata_gates_not_validated"} in payload["blockers"]
    assert any(
        error.startswith("kpi_manifest_blocked_claim_not_blocked:")
        for error in summary["bundle_validation_errors"]
    )
    assert any(
        error.startswith("kpi_manifest_blocked_reason_missing:")
        for error in summary["bundle_validation_errors"]
    )
    assert any(
        error.startswith("kpi_blocked_claim_gate_missing:")
        for error in summary["bundle_validation_errors"]
    )
    assert any(
        error.startswith("pm_blocked_claim_gate_missing:")
        for error in summary["bundle_validation_errors"]
    )


def test_ai_md_product_evidence_bundle_blocks_without_signed_force_residual_summary(tmp_path: Path) -> None:
    out_tar = tmp_path / "bundle.tar.gz"
    kpi_packet = _kpi_packet(ready=True, force_residual_summary_signed=False)

    payload = mod.build_payload(
        kpi_packet=kpi_packet,
        rocm_manifest_packet=_rocm_packet(ready=True),
        product_image_preflight_packet=_image_preflight_packet(clean_ready=True),
        artifact_specs=_artifact_specs(tmp_path, kpi_packet=kpi_packet),
        out_tar=str(out_tar),
    )

    summary = payload["summary"]
    assert summary["bundle_export_ready"] is True
    assert summary["bundle_validation_pass"] is False
    assert summary["product_claim_ready"] is False
    assert summary["runner_claim_metadata_signed"] is True
    assert summary["force_residual_summary_signed"] is False
    assert summary["kpi_claim_metadata_gates_validated"] is False
    assert {"code": "force_residual_summary_not_signed"} in payload["blockers"]
    assert {"code": "kpi_claim_metadata_gates_not_validated"} in payload["blockers"]
    assert any(
        error.startswith("kpi_manifest_force_residual_summary_missing:")
        for error in summary["bundle_validation_errors"]
    )
    assert any(
        error.startswith("kpi_manifest_force_residual_schema_missing:")
        for error in summary["bundle_validation_errors"]
    )
    assert any(
        error.startswith("kpi_manifest_force_residual_policy_caps_not_ready:")
        for error in summary["bundle_validation_errors"]
    )
    assert any(
        error.startswith("kpi_manifest_force_residual_observed_caps_not_ready:")
        for error in summary["bundle_validation_errors"]
    )


def test_ai_md_product_evidence_bundle_blocks_without_runtime_kpi_tracking(tmp_path: Path) -> None:
    out_tar = tmp_path / "bundle.tar.gz"
    kpi_packet = _kpi_packet(ready=True)
    kpi_packet["runtime_kpi"]["memory_peak_mb"] = 0.0
    kpi_packet["runtime_kpi"]["neighbor_list_rebuild"]["neighbor_list_rebuild_frequency"] = 0.0
    kpi_packet["runtime_kpi"]["neighbor_list_rebuild"]["engine_neighbor_diagnostics_ready"] = False
    kpi_packet["runtime_kpi"]["neighbor_list_rebuild"]["last_forcefield_neighbor_pair_count"] = 0
    kpi_packet["pm_kpi_summary"]["runtime"]["memory_peak_tracked"] = False
    kpi_packet["pm_kpi_summary"]["runtime"]["neighbor_list_rebuild_frequency_tracked"] = False

    payload = mod.build_payload(
        kpi_packet=kpi_packet,
        rocm_manifest_packet=_rocm_packet(ready=True),
        product_image_preflight_packet=_image_preflight_packet(clean_ready=True),
        artifact_specs=_artifact_specs(tmp_path, kpi_packet=kpi_packet),
        out_tar=str(out_tar),
    )

    summary = payload["summary"]
    assert summary["bundle_export_ready"] is True
    assert summary["bundle_validation_pass"] is False
    assert summary["product_claim_ready"] is False
    assert {"code": "kpi_claim_metadata_gates_not_validated"} in payload["blockers"]
    assert any(
        error.startswith("kpi_runtime_memory_peak_missing:")
        for error in summary["bundle_validation_errors"]
    )
    assert any(
        error.startswith("kpi_runtime_neighbor_list_rebuild_missing:")
        for error in summary["bundle_validation_errors"]
    )
    assert any(
        error.startswith("pm_memory_peak_gate_missing:")
        for error in summary["bundle_validation_errors"]
    )
    assert any(
        error.startswith("pm_neighbor_list_rebuild_frequency_gate_missing:")
        for error in summary["bundle_validation_errors"]
    )


def test_ai_md_product_evidence_bundle_blocks_without_runtime_neighbor_cap_scaling(
    tmp_path: Path,
) -> None:
    out_tar = tmp_path / "bundle.tar.gz"
    kpi_packet = _kpi_packet(ready=True)
    scaling = kpi_packet["runtime_kpi"]["neighbor_cap_scaling"]
    scaling["ready"] = False
    scaling["status"] = "blocked_runtime_neighbor_cap_scaling"
    scaling["neighbor_pair_count_slope"] = 1.8
    scaling["rows"][0]["row_ready"] = False
    kpi_packet["pm_kpi_summary"]["runtime"]["runtime_neighbor_cap_scaling_ready"] = False
    kpi_packet["pm_kpi_summary"]["runtime"]["runtime_neighbor_cap_scaling_pair_count_slope"] = 0.0

    payload = mod.build_payload(
        kpi_packet=kpi_packet,
        rocm_manifest_packet=_rocm_packet(ready=True),
        product_image_preflight_packet=_image_preflight_packet(clean_ready=True),
        artifact_specs=_artifact_specs(tmp_path, kpi_packet=kpi_packet),
        out_tar=str(out_tar),
    )

    summary = payload["summary"]
    assert summary["bundle_export_ready"] is True
    assert summary["bundle_validation_pass"] is False
    assert summary["product_claim_ready"] is False
    assert {"code": "kpi_claim_metadata_gates_not_validated"} in payload["blockers"]
    assert any(
        error.startswith("kpi_runtime_neighbor_cap_scaling_not_ready:")
        for error in summary["bundle_validation_errors"]
    )
    assert any(
        error.startswith("kpi_runtime_neighbor_cap_scaling_rows_invalid:")
        for error in summary["bundle_validation_errors"]
    )
    assert any(
        error.startswith("pm_runtime_neighbor_cap_scaling_gate_missing:")
        for error in summary["bundle_validation_errors"]
    )
    assert any(
        error.startswith("pm_runtime_neighbor_cap_scaling_slope_mismatch:")
        for error in summary["bundle_validation_errors"]
    )


def test_ai_md_product_evidence_bundle_blocks_without_runtime_scaling_plot_metadata(
    tmp_path: Path,
) -> None:
    out_tar = tmp_path / "bundle.tar.gz"
    kpi_packet = _kpi_packet(ready=True)
    scaling = kpi_packet["runtime_kpi"]["neighbor_cap_scaling"]
    scaling["plot_ready"] = False
    scaling["plot_role"] = "runtime_plot_without_claim_role"
    scaling["plot_claim_boundary"] = "duration chart only"
    kpi_packet["pm_kpi_summary"]["runtime"]["runtime_neighbor_cap_scaling_plot_ready"] = False

    payload = mod.build_payload(
        kpi_packet=kpi_packet,
        rocm_manifest_packet=_rocm_packet(ready=True),
        product_image_preflight_packet=_image_preflight_packet(clean_ready=True),
        artifact_specs=_artifact_specs(tmp_path, kpi_packet=kpi_packet),
        out_tar=str(out_tar),
    )

    summary = payload["summary"]
    assert summary["bundle_export_ready"] is True
    assert summary["bundle_validation_pass"] is False
    assert summary["product_claim_ready"] is False
    assert summary["runtime_neighbor_cap_scaling_plot_ready"] is False
    assert {"code": "kpi_claim_metadata_gates_not_validated"} in payload["blockers"]
    assert any(
        error.startswith("kpi_runtime_neighbor_cap_scaling_plot_missing:")
        for error in summary["bundle_validation_errors"]
    )
    assert any(
        error.startswith("pm_runtime_neighbor_cap_scaling_plot_gate_missing:")
        for error in summary["bundle_validation_errors"]
    )


def test_ai_md_product_evidence_bundle_blocks_runtime_pm_numeric_mismatch(tmp_path: Path) -> None:
    out_tar = tmp_path / "bundle.tar.gz"
    kpi_packet = _kpi_packet(ready=True)
    pm_runtime = kpi_packet["pm_kpi_summary"]["runtime"]
    pm_runtime["score_only_1k_runtime_sec"] = 99.0
    pm_runtime["top10_force_residual_rows_per_sec"] = 1.0
    pm_runtime["memory_peak_mb"] = 1.0
    pm_runtime["neighbor_list_rebuild_frequency"] = 0.01

    payload = mod.build_payload(
        kpi_packet=kpi_packet,
        rocm_manifest_packet=_rocm_packet(ready=True),
        product_image_preflight_packet=_image_preflight_packet(clean_ready=True),
        artifact_specs=_artifact_specs(tmp_path, kpi_packet=kpi_packet),
        out_tar=str(out_tar),
    )

    summary = payload["summary"]
    assert summary["bundle_export_ready"] is True
    assert summary["bundle_validation_pass"] is False
    assert summary["product_claim_ready"] is False
    assert {"code": "kpi_claim_metadata_gates_not_validated"} in payload["blockers"]
    assert any(
        error.startswith("pm_runtime_score_only_duration_mismatch:")
        for error in summary["bundle_validation_errors"]
    )
    assert any(
        error.startswith("pm_runtime_top10_force_residual_rows_per_sec_mismatch:")
        for error in summary["bundle_validation_errors"]
    )
    assert any(
        error.startswith("pm_runtime_memory_peak_mismatch:")
        for error in summary["bundle_validation_errors"]
    )
    assert any(
        error.startswith("pm_runtime_neighbor_list_rebuild_frequency_mismatch:")
        for error in summary["bundle_validation_errors"]
    )


def test_ai_md_product_evidence_bundle_blocks_without_physics_kpi_gates(tmp_path: Path) -> None:
    out_tar = tmp_path / "bundle.tar.gz"
    kpi_packet = _kpi_packet(ready=True)
    kpi_packet["physics_kpi"]["energy_drift_smoke_pct"] = 0.25
    kpi_packet["physics_kpi"]["neighbor_list_parity_error"] = 0.5
    kpi_packet["pm_kpi_summary"]["physics"]["energy_drift_pass"] = False
    kpi_packet["pm_kpi_summary"]["physics"]["neighbor_list_parity_pass"] = False

    payload = mod.build_payload(
        kpi_packet=kpi_packet,
        rocm_manifest_packet=_rocm_packet(ready=True),
        product_image_preflight_packet=_image_preflight_packet(clean_ready=True),
        artifact_specs=_artifact_specs(tmp_path, kpi_packet=kpi_packet),
        out_tar=str(out_tar),
    )

    summary = payload["summary"]
    assert summary["bundle_export_ready"] is True
    assert summary["bundle_validation_pass"] is False
    assert summary["product_claim_ready"] is False
    assert {"code": "kpi_claim_metadata_gates_not_validated"} in payload["blockers"]
    assert any(
        error.startswith("kpi_physics_energy_drift_high:")
        for error in summary["bundle_validation_errors"]
    )
    assert any(
        error.startswith("kpi_physics_neighbor_list_parity_error:")
        for error in summary["bundle_validation_errors"]
    )
    assert any(
        error.startswith("pm_energy_drift_gate_missing:")
        for error in summary["bundle_validation_errors"]
    )
    assert any(
        error.startswith("pm_neighbor_list_parity_gate_missing:")
        for error in summary["bundle_validation_errors"]
    )


def test_ai_md_product_evidence_bundle_blocks_without_signed_ligand_topology_metadata(tmp_path: Path) -> None:
    out_tar = tmp_path / "bundle.tar.gz"
    kpi_packet = _kpi_packet(ready=True, manifest_ligand_topology_claim_safe=False)

    payload = mod.build_payload(
        kpi_packet=kpi_packet,
        rocm_manifest_packet=_rocm_packet(ready=True),
        product_image_preflight_packet=_image_preflight_packet(clean_ready=True),
        artifact_specs=_artifact_specs(tmp_path, kpi_packet=kpi_packet),
        out_tar=str(out_tar),
    )

    summary = payload["summary"]
    assert summary["bundle_export_ready"] is True
    assert summary["bundle_validation_pass"] is False
    assert summary["product_claim_ready"] is False
    assert {"code": "kpi_claim_metadata_gates_not_validated"} in payload["blockers"]
    assert any(
        error.startswith("kpi_manifest_ligand_topology_claim_safe_missing:")
        for error in summary["bundle_validation_errors"]
    )
    assert any(
        error.startswith("kpi_manifest_ligand_topology_schema_missing:")
        for error in summary["bundle_validation_errors"]
    )
    assert any(
        error.startswith("kpi_manifest_ligand_topology_schema_rows_missing:")
        for error in summary["bundle_validation_errors"]
    )
    assert any(
        error.startswith("kpi_manifest_ligand_topology_claim_safe_rows_missing:")
        for error in summary["bundle_validation_errors"]
    )


def test_ai_md_product_evidence_bundle_blocks_without_force_term_claim_schema(tmp_path: Path) -> None:
    out_tar = tmp_path / "bundle.tar.gz"
    kpi_packet = _kpi_packet(ready=True, force_term_claim_metadata_schema_ready=False)

    payload = mod.build_payload(
        kpi_packet=kpi_packet,
        rocm_manifest_packet=_rocm_packet(ready=True),
        product_image_preflight_packet=_image_preflight_packet(clean_ready=True),
        artifact_specs=_artifact_specs(tmp_path, kpi_packet=kpi_packet),
        out_tar=str(out_tar),
    )

    summary = payload["summary"]
    assert summary["bundle_export_ready"] is True
    assert summary["bundle_validation_pass"] is False
    assert summary["product_claim_ready"] is False
    assert {"code": "kpi_claim_metadata_gates_not_validated"} in payload["blockers"]
    assert any(
        error.startswith("kpi_force_term_claim_metadata_schema_missing:")
        for error in summary["bundle_validation_errors"]
    )
    assert any(
        error.startswith("kpi_force_term_claim_rows_missing:")
        for error in summary["bundle_validation_errors"]
    )


def test_ai_md_product_evidence_bundle_blocks_without_forcefield_neighbor_diagnostics(tmp_path: Path) -> None:
    out_tar = tmp_path / "bundle.tar.gz"
    kpi_packet = _kpi_packet(ready=True)
    smoke = kpi_packet["product_kpi"]["force_term_claim_metadata_smoke"]
    smoke["forcefield_neighbor_diagnostics_ready"] = False
    smoke["forcefield_neighbor_pair_count"] = 0
    smoke["forcefield_neighbor_source"] = ""

    payload = mod.build_payload(
        kpi_packet=kpi_packet,
        rocm_manifest_packet=_rocm_packet(ready=True),
        product_image_preflight_packet=_image_preflight_packet(clean_ready=True),
        artifact_specs=_artifact_specs(tmp_path, kpi_packet=kpi_packet),
        out_tar=str(out_tar),
    )

    summary = payload["summary"]
    assert summary["bundle_export_ready"] is True
    assert summary["bundle_validation_pass"] is False
    assert summary["product_claim_ready"] is False
    assert {"code": "kpi_claim_metadata_gates_not_validated"} in payload["blockers"]
    assert any(
        error.startswith("kpi_forcefield_neighbor_diagnostics_missing:")
        for error in summary["bundle_validation_errors"]
    )


def test_ai_md_product_evidence_bundle_blocks_force_term_claim_safe_row_with_blocker(
    tmp_path: Path,
) -> None:
    out_tar = tmp_path / "bundle.tar.gz"
    kpi_packet = _kpi_packet(ready=True)
    smoke = kpi_packet["product_kpi"]["force_term_claim_metadata_smoke"]
    smoke["forcefield_claim_rows"][0]["blocked_reason"] = "physics_validation_failed"

    payload = mod.build_payload(
        kpi_packet=kpi_packet,
        rocm_manifest_packet=_rocm_packet(ready=True),
        product_image_preflight_packet=_image_preflight_packet(clean_ready=True),
        artifact_specs=_artifact_specs(tmp_path, kpi_packet=kpi_packet),
        out_tar=str(out_tar),
    )

    summary = payload["summary"]
    assert summary["bundle_export_ready"] is True
    assert summary["bundle_validation_pass"] is False
    assert summary["product_claim_ready"] is False
    assert {"code": "kpi_claim_metadata_gates_not_validated"} in payload["blockers"]
    assert any(
        error.startswith("kpi_force_term_claim_rows_not_safe:")
        for error in summary["bundle_validation_errors"]
    )


def test_ai_md_product_evidence_bundle_blocks_forcefield_unsafe_base_claim_promotion(
    tmp_path: Path,
) -> None:
    out_tar = tmp_path / "bundle.tar.gz"
    kpi_packet = _kpi_packet(ready=True)
    smoke = kpi_packet["product_kpi"]["force_term_claim_metadata_smoke"]
    smoke["forcefield_unsafe_base_claim_blocked"] = False
    smoke["forcefield_unsafe_base_claim_safe"] = True
    smoke["forcefield_unsafe_base_blocked_reason"] = ""
    smoke["forcefield_unsafe_base_claim_safe_count"] = 3
    smoke["forcefield_unsafe_base_blocked_count"] = 0
    smoke["forcefield_unsafe_base_claim_rows"][0]["claim_safe"] = True
    smoke["forcefield_unsafe_base_claim_rows"][0]["blocked_reason"] = ""

    payload = mod.build_payload(
        kpi_packet=kpi_packet,
        rocm_manifest_packet=_rocm_packet(ready=True),
        product_image_preflight_packet=_image_preflight_packet(clean_ready=True),
        artifact_specs=_artifact_specs(tmp_path, kpi_packet=kpi_packet),
        out_tar=str(out_tar),
    )

    summary = payload["summary"]
    assert summary["bundle_export_ready"] is True
    assert summary["bundle_validation_pass"] is False
    assert summary["product_claim_ready"] is False
    assert {"code": "kpi_claim_metadata_gates_not_validated"} in payload["blockers"]
    assert any(
        error.startswith("kpi_forcefield_unsafe_base_claim_not_blocked:")
        for error in summary["bundle_validation_errors"]
    )


def test_ai_md_product_evidence_bundle_blocks_without_force_term_result_contract_gate(
    tmp_path: Path,
) -> None:
    out_tar = tmp_path / "bundle.tar.gz"
    kpi_packet = _kpi_packet(ready=True, force_term_result_contract_ready=False)

    payload = mod.build_payload(
        kpi_packet=kpi_packet,
        rocm_manifest_packet=_rocm_packet(ready=True),
        product_image_preflight_packet=_image_preflight_packet(clean_ready=True),
        artifact_specs=_artifact_specs(tmp_path, kpi_packet=kpi_packet),
        out_tar=str(out_tar),
    )

    summary = payload["summary"]
    assert summary["bundle_export_ready"] is True
    assert summary["bundle_validation_pass"] is False
    assert summary["product_claim_ready"] is False
    assert summary["force_term_result_contract_ready"] is False
    assert {"code": "force_term_result_contract_not_ready"} in payload["blockers"]
    assert {"code": "kpi_claim_metadata_gates_not_validated"} in payload["blockers"]
    assert any(
        error.startswith("kpi_force_term_result_contract_not_ready:")
        for error in summary["bundle_validation_errors"]
    )
    assert any(
        error.startswith("pm_force_term_result_contract_gate_missing:")
        for error in summary["bundle_validation_errors"]
    )


def test_ai_md_product_evidence_bundle_blocks_without_forcefield_energy_forces_contract_gate(
    tmp_path: Path,
) -> None:
    out_tar = tmp_path / "bundle.tar.gz"
    kpi_packet = _kpi_packet(ready=True)
    kpi_packet["product_kpi"]["forcefield_energy_forces_contract_ready"] = False
    smoke = kpi_packet["product_kpi"]["force_term_claim_metadata_smoke"]
    smoke["forcefield_energy_forces_contract_ready"] = False
    smoke["forcefield_forces_finite"] = False
    smoke["forcefield_energy_forces_contract_error"] = "ValueError:product forcefield returned nonfinite forces"
    kpi_packet["pm_kpi_summary"]["product"]["forcefield_energy_forces_contract_ready"] = False

    payload = mod.build_payload(
        kpi_packet=kpi_packet,
        rocm_manifest_packet=_rocm_packet(ready=True),
        product_image_preflight_packet=_image_preflight_packet(clean_ready=True),
        artifact_specs=_artifact_specs(tmp_path, kpi_packet=kpi_packet),
        out_tar=str(out_tar),
    )

    summary = payload["summary"]
    assert summary["bundle_export_ready"] is True
    assert summary["bundle_validation_pass"] is False
    assert summary["product_claim_ready"] is False
    assert summary["forcefield_energy_forces_contract_ready"] is False
    assert {"code": "forcefield_energy_forces_contract_not_ready"} in payload["blockers"]
    assert {"code": "kpi_claim_metadata_gates_not_validated"} in payload["blockers"]
    assert any(
        error.startswith("kpi_forcefield_energy_forces_contract_not_ready:")
        for error in summary["bundle_validation_errors"]
    )
    assert any(
        error.startswith("kpi_forcefield_energy_forces_contract_smoke_not_ready:")
        for error in summary["bundle_validation_errors"]
    )
    assert any(
        error.startswith("kpi_forcefield_energy_forces_contract_fields_invalid:")
        for error in summary["bundle_validation_errors"]
    )
    assert any(
        error.startswith("pm_forcefield_energy_forces_contract_gate_missing:")
        for error in summary["bundle_validation_errors"]
    )


def test_ai_md_product_evidence_bundle_blocks_without_runner_profile_validation_gate(
    tmp_path: Path,
) -> None:
    out_tar = tmp_path / "bundle.tar.gz"
    kpi_packet = _kpi_packet(ready=True)
    kpi_packet["product_kpi"]["runner_profile_validation_pass"] = False
    kpi_packet["pm_kpi_summary"]["product"]["runner_profile_validation_pass"] = False

    payload = mod.build_payload(
        kpi_packet=kpi_packet,
        rocm_manifest_packet=_rocm_packet(ready=True),
        product_image_preflight_packet=_image_preflight_packet(clean_ready=True),
        artifact_specs=_artifact_specs(tmp_path, kpi_packet=kpi_packet),
        out_tar=str(out_tar),
    )

    summary = payload["summary"]
    assert summary["bundle_export_ready"] is True
    assert summary["bundle_validation_pass"] is False
    assert summary["product_claim_ready"] is False
    assert {"code": "kpi_claim_metadata_gates_not_validated"} in payload["blockers"]
    assert any(
        error.startswith("kpi_runner_profile_validation_not_pass:")
        for error in summary["bundle_validation_errors"]
    )
    assert any(
        error.startswith("pm_runner_profile_validation_gate_missing:")
        for error in summary["bundle_validation_errors"]
    )


def test_ai_md_product_evidence_bundle_blocks_runner_profile_count_mismatch(
    tmp_path: Path,
) -> None:
    out_tar = tmp_path / "bundle.tar.gz"
    kpi_packet = _kpi_packet(ready=True)
    product = kpi_packet["product_kpi"]
    pm_product = kpi_packet["pm_kpi_summary"]["product"]
    product["enabled_profile_count"] = 2
    product["failed_profile_count"] = 1
    pm_product["enabled_profile_count"] = 3
    pm_product["failed_profile_count"] = 0

    payload = mod.build_payload(
        kpi_packet=kpi_packet,
        rocm_manifest_packet=_rocm_packet(ready=True),
        product_image_preflight_packet=_image_preflight_packet(clean_ready=True),
        artifact_specs=_artifact_specs(tmp_path, kpi_packet=kpi_packet),
        out_tar=str(out_tar),
    )

    summary = payload["summary"]
    assert summary["bundle_export_ready"] is True
    assert summary["bundle_validation_pass"] is False
    assert summary["product_claim_ready"] is False
    assert {"code": "kpi_claim_metadata_gates_not_validated"} in payload["blockers"]
    assert any(
        error.startswith("kpi_runner_profile_enabled_count_low:")
        for error in summary["bundle_validation_errors"]
    )
    assert any(
        error.startswith("kpi_runner_profile_failed_count_nonzero:")
        for error in summary["bundle_validation_errors"]
    )
    assert any(
        error.startswith("pm_product_enabled_profile_count_mismatch:")
        for error in summary["bundle_validation_errors"]
    )
    assert any(
        error.startswith("pm_product_failed_profile_count_mismatch:")
        for error in summary["bundle_validation_errors"]
    )


def test_ai_md_product_evidence_bundle_blocks_without_guarded_force_term_plugin_gate(
    tmp_path: Path,
) -> None:
    out_tar = tmp_path / "bundle.tar.gz"
    kpi_packet = _kpi_packet(ready=True, guarded_force_term_plugin_ready=False)

    payload = mod.build_payload(
        kpi_packet=kpi_packet,
        rocm_manifest_packet=_rocm_packet(ready=True),
        product_image_preflight_packet=_image_preflight_packet(clean_ready=True),
        artifact_specs=_artifact_specs(tmp_path, kpi_packet=kpi_packet),
        out_tar=str(out_tar),
    )

    summary = payload["summary"]
    assert summary["bundle_export_ready"] is True
    assert summary["bundle_validation_pass"] is False
    assert summary["product_claim_ready"] is False
    assert summary["guarded_force_term_plugin_ready"] is False
    assert {"code": "guarded_force_term_plugin_not_ready"} in payload["blockers"]
    assert {"code": "kpi_claim_metadata_gates_not_validated"} in payload["blockers"]
    assert any(
        error.startswith("kpi_guarded_force_term_plugin_not_ready:")
        for error in summary["bundle_validation_errors"]
    )
    assert any(
        error.startswith("kpi_guarded_force_term_plugin_smoke_not_ready:")
        for error in summary["bundle_validation_errors"]
    )
    assert any(
        error.startswith("pm_guarded_force_term_plugin_gate_missing:")
        for error in summary["bundle_validation_errors"]
    )


def test_ai_md_product_evidence_bundle_blocks_without_onsps_backmap_schema_gate(
    tmp_path: Path,
) -> None:
    out_tar = tmp_path / "bundle.tar.gz"
    kpi_packet = _kpi_packet(ready=True, onsps_backmap_evidence_schema_ready=False)

    payload = mod.build_payload(
        kpi_packet=kpi_packet,
        rocm_manifest_packet=_rocm_packet(ready=True),
        product_image_preflight_packet=_image_preflight_packet(clean_ready=True),
        artifact_specs=_artifact_specs(tmp_path, kpi_packet=kpi_packet),
        out_tar=str(out_tar),
    )

    summary = payload["summary"]
    assert summary["bundle_export_ready"] is True
    assert summary["bundle_validation_pass"] is False
    assert summary["product_claim_ready"] is False
    assert summary["onsps_backmap_evidence_schema_ready"] is False
    assert {"code": "onsps_backmap_evidence_schema_not_ready"} in payload["blockers"]
    assert {"code": "kpi_claim_metadata_gates_not_validated"} in payload["blockers"]
    assert any(
        error.startswith("kpi_onsps_backmap_evidence_schema_not_ready:")
        for error in summary["bundle_validation_errors"]
    )
    assert any(
        error.startswith("kpi_onsps_backmap_evidence_schema_smoke_not_ready:")
        for error in summary["bundle_validation_errors"]
    )
    assert any(
        error.startswith("pm_onsps_backmap_evidence_schema_gate_missing:")
        for error in summary["bundle_validation_errors"]
    )


def test_ai_md_product_evidence_bundle_blocks_force_term_contract_detail_mismatch(
    tmp_path: Path,
) -> None:
    out_tar = tmp_path / "bundle.tar.gz"
    kpi_packet = _kpi_packet(ready=True)
    rows = kpi_packet["product_kpi"]["force_term_claim_metadata_smoke"]["term_result_contract_rows"]
    rows[0]["claim_force_term_name"] = "other_term"

    payload = mod.build_payload(
        kpi_packet=kpi_packet,
        rocm_manifest_packet=_rocm_packet(ready=True),
        product_image_preflight_packet=_image_preflight_packet(clean_ready=True),
        artifact_specs=_artifact_specs(tmp_path, kpi_packet=kpi_packet),
        out_tar=str(out_tar),
    )

    summary = payload["summary"]
    assert summary["bundle_export_ready"] is True
    assert summary["bundle_validation_pass"] is False
    assert summary["product_claim_ready"] is False
    assert {"code": "kpi_claim_metadata_gates_not_validated"} in payload["blockers"]
    assert any(
        error.startswith("kpi_force_term_result_contract_rows_invalid:")
        for error in summary["bundle_validation_errors"]
    )


def test_ai_md_product_evidence_bundle_blocks_force_term_contract_term_set_mismatch(
    tmp_path: Path,
) -> None:
    out_tar = tmp_path / "bundle.tar.gz"
    kpi_packet = _kpi_packet(ready=True)
    rows = kpi_packet["product_kpi"]["force_term_claim_metadata_smoke"]["term_result_contract_rows"]
    rows[2] = dict(rows[1])

    payload = mod.build_payload(
        kpi_packet=kpi_packet,
        rocm_manifest_packet=_rocm_packet(ready=True),
        product_image_preflight_packet=_image_preflight_packet(clean_ready=True),
        artifact_specs=_artifact_specs(tmp_path, kpi_packet=kpi_packet),
        out_tar=str(out_tar),
    )

    summary = payload["summary"]
    assert summary["bundle_export_ready"] is True
    assert summary["bundle_validation_pass"] is False
    assert summary["product_claim_ready"] is False
    assert {"code": "kpi_claim_metadata_gates_not_validated"} in payload["blockers"]
    assert any(
        error.startswith("kpi_force_term_result_contract_terms_invalid:")
        for error in summary["bundle_validation_errors"]
    )


def test_ai_md_product_evidence_bundle_blocks_pm_force_term_contract_term_set_mismatch(
    tmp_path: Path,
) -> None:
    out_tar = tmp_path / "bundle.tar.gz"
    kpi_packet = _kpi_packet(ready=True)
    pm_product = kpi_packet["pm_kpi_summary"]["product"]
    pm_product["force_term_result_contract_term_set_ready"] = False
    pm_product["force_term_result_contract_terms"] = [
        "directional_hbond",
        "hydrophobic_contact",
        "hydrophobic_contact",
    ]

    payload = mod.build_payload(
        kpi_packet=kpi_packet,
        rocm_manifest_packet=_rocm_packet(ready=True),
        product_image_preflight_packet=_image_preflight_packet(clean_ready=True),
        artifact_specs=_artifact_specs(tmp_path, kpi_packet=kpi_packet),
        out_tar=str(out_tar),
    )

    summary = payload["summary"]
    assert summary["bundle_export_ready"] is True
    assert summary["bundle_validation_pass"] is False
    assert summary["product_claim_ready"] is False
    assert {"code": "kpi_claim_metadata_gates_not_validated"} in payload["blockers"]
    assert any(
        error.startswith("pm_force_term_result_contract_term_set_gate_missing:")
        for error in summary["bundle_validation_errors"]
    )
    assert any(
        error.startswith("pm_force_term_result_contract_terms_mismatch:")
        for error in summary["bundle_validation_errors"]
    )


def test_ai_md_product_evidence_bundle_blocks_guarded_plugin_detail_mismatch(
    tmp_path: Path,
) -> None:
    out_tar = tmp_path / "bundle.tar.gz"
    kpi_packet = _kpi_packet(ready=True)
    kpi_packet["product_kpi"]["guarded_force_term_plugin_smoke"]["missing_charge_blocked"] = False

    payload = mod.build_payload(
        kpi_packet=kpi_packet,
        rocm_manifest_packet=_rocm_packet(ready=True),
        product_image_preflight_packet=_image_preflight_packet(clean_ready=True),
        artifact_specs=_artifact_specs(tmp_path, kpi_packet=kpi_packet),
        out_tar=str(out_tar),
    )

    summary = payload["summary"]
    assert summary["bundle_export_ready"] is True
    assert summary["bundle_validation_pass"] is False
    assert summary["product_claim_ready"] is False
    assert {"code": "kpi_claim_metadata_gates_not_validated"} in payload["blockers"]
    assert any(
        error.startswith("kpi_guarded_force_term_plugin_missing_charge_not_blocked:")
        for error in summary["bundle_validation_errors"]
    )


def test_ai_md_product_evidence_bundle_blocks_guarded_plugin_missing_pocket_wall_rows(
    tmp_path: Path,
) -> None:
    out_tar = tmp_path / "bundle.tar.gz"
    kpi_packet = _kpi_packet(ready=True)
    guarded = kpi_packet["product_kpi"]["guarded_force_term_plugin_smoke"]
    guarded["required_guarded_terms"] = ["screened_electrostatics"]
    guarded["required_guarded_terms_present"] = False
    guarded["pocket_wall_claim_safe"] = False
    guarded["pocket_wall_missing_metadata_blocked"] = False
    guarded["pocket_wall_policy_cap_exceeded_blocked"] = False
    guarded["forcefield_guarded_rows_ready"] = False
    guarded["guarded_term_rows"] = [
        row for row in guarded["guarded_term_rows"]
        if row["force_term_name"] != "pocket_wall"
    ]
    guarded["forcefield_guarded_claim_rows"] = [
        row for row in guarded["forcefield_guarded_claim_rows"]
        if row["force_term_name"] != "pocket_wall"
    ]

    payload = mod.build_payload(
        kpi_packet=kpi_packet,
        rocm_manifest_packet=_rocm_packet(ready=True),
        product_image_preflight_packet=_image_preflight_packet(clean_ready=True),
        artifact_specs=_artifact_specs(tmp_path, kpi_packet=kpi_packet),
        out_tar=str(out_tar),
    )

    summary = payload["summary"]
    assert summary["bundle_export_ready"] is True
    assert summary["bundle_validation_pass"] is False
    assert summary["product_claim_ready"] is False
    assert {"code": "kpi_claim_metadata_gates_not_validated"} in payload["blockers"]
    assert any(
        error.startswith("kpi_guarded_force_term_required_terms_missing:")
        for error in summary["bundle_validation_errors"]
    )
    assert any(
        error.startswith("kpi_guarded_force_term_plugin_pocket_wall_invalid:")
        for error in summary["bundle_validation_errors"]
    )
    assert any(
        error.startswith("kpi_guarded_force_term_plugin_rows_invalid:")
        for error in summary["bundle_validation_errors"]
    )
    assert any(
        error.startswith("kpi_guarded_force_term_plugin_forcefield_guarded_rows_invalid:")
        for error in summary["bundle_validation_errors"]
    )


def test_ai_md_product_evidence_bundle_blocks_guarded_plugin_without_bounded_caps(
    tmp_path: Path,
) -> None:
    out_tar = tmp_path / "bundle.tar.gz"
    kpi_packet = _kpi_packet(ready=True)
    guarded = kpi_packet["product_kpi"]["guarded_force_term_plugin_smoke"]
    guarded["policy_caps_ready"] = False
    guarded["observed_caps_ready"] = False
    guarded["bounded_correction_ready"] = False
    guarded["policy_cap_exceeded_blocked"] = False
    guarded["forcefield_bounded_row_ready"] = False
    guarded["forcefield_guarded_claim_row"] = {}

    payload = mod.build_payload(
        kpi_packet=kpi_packet,
        rocm_manifest_packet=_rocm_packet(ready=True),
        product_image_preflight_packet=_image_preflight_packet(clean_ready=True),
        artifact_specs=_artifact_specs(tmp_path, kpi_packet=kpi_packet),
        out_tar=str(out_tar),
    )

    summary = payload["summary"]
    assert summary["bundle_export_ready"] is True
    assert summary["bundle_validation_pass"] is False
    assert summary["product_claim_ready"] is False
    assert {"code": "kpi_claim_metadata_gates_not_validated"} in payload["blockers"]
    assert any(
        error.startswith("kpi_guarded_force_term_plugin_policy_caps_not_ready:")
        for error in summary["bundle_validation_errors"]
    )
    assert any(
        error.startswith("kpi_guarded_force_term_plugin_observed_caps_not_ready:")
        for error in summary["bundle_validation_errors"]
    )
    assert any(
        error.startswith("kpi_guarded_force_term_plugin_bounded_correction_not_ready:")
        for error in summary["bundle_validation_errors"]
    )
    assert any(
        error.startswith("kpi_guarded_force_term_plugin_cap_exceeded_not_blocked:")
        for error in summary["bundle_validation_errors"]
    )
    assert any(
        error.startswith("kpi_guarded_force_term_plugin_forcefield_bounded_row_missing:")
        for error in summary["bundle_validation_errors"]
    )
    assert any(
        error.startswith("kpi_guarded_force_term_plugin_forcefield_bounded_row_invalid:")
        for error in summary["bundle_validation_errors"]
    )


def test_ai_md_product_evidence_bundle_blocks_guarded_plugin_aggregate_row_cap_metadata_drift(
    tmp_path: Path,
) -> None:
    out_tar = tmp_path / "bundle.tar.gz"
    kpi_packet = _kpi_packet(ready=True)
    guarded = kpi_packet["product_kpi"]["guarded_force_term_plugin_smoke"]
    guarded["forcefield_guarded_claim_row"]["abs_energy_within_cap"] = False
    guarded["forcefield_guarded_claim_row"]["force_norm_within_cap"] = False
    guarded["forcefield_guarded_claim_row"]["active_pair_count_within_cap"] = False
    guarded["forcefield_guarded_claim_row"]["policy_caps"] = {}

    payload = mod.build_payload(
        kpi_packet=kpi_packet,
        rocm_manifest_packet=_rocm_packet(ready=True),
        product_image_preflight_packet=_image_preflight_packet(clean_ready=True),
        artifact_specs=_artifact_specs(tmp_path, kpi_packet=kpi_packet),
        out_tar=str(out_tar),
    )

    summary = payload["summary"]
    assert summary["bundle_export_ready"] is True
    assert summary["bundle_validation_pass"] is False
    assert summary["product_claim_ready"] is False
    assert {"code": "kpi_claim_metadata_gates_not_validated"} in payload["blockers"]
    assert any(
        error.startswith("kpi_guarded_force_term_plugin_forcefield_bounded_row_invalid:")
        for error in summary["bundle_validation_errors"]
    )


def test_ai_md_product_evidence_bundle_blocks_guarded_plugin_aggregate_row_missing_cap_metadata(
    tmp_path: Path,
) -> None:
    out_tar = tmp_path / "bundle.tar.gz"
    kpi_packet = _kpi_packet(ready=True)
    guarded = kpi_packet["product_kpi"]["guarded_force_term_plugin_smoke"]
    for key in (
        "abs_energy_within_cap",
        "force_norm_within_cap",
        "active_pair_count_within_cap",
        "policy_caps",
    ):
        guarded["forcefield_guarded_claim_row"].pop(key, None)

    payload = mod.build_payload(
        kpi_packet=kpi_packet,
        rocm_manifest_packet=_rocm_packet(ready=True),
        product_image_preflight_packet=_image_preflight_packet(clean_ready=True),
        artifact_specs=_artifact_specs(tmp_path, kpi_packet=kpi_packet),
        out_tar=str(out_tar),
    )

    summary = payload["summary"]
    assert summary["bundle_export_ready"] is True
    assert summary["bundle_validation_pass"] is False
    assert summary["product_claim_ready"] is False
    assert {"code": "kpi_claim_metadata_gates_not_validated"} in payload["blockers"]
    assert any(
        error.startswith("kpi_guarded_force_term_plugin_forcefield_bounded_row_invalid:")
        for error in summary["bundle_validation_errors"]
    )


def test_ai_md_product_evidence_bundle_blocks_onsps_detail_mismatch(
    tmp_path: Path,
) -> None:
    out_tar = tmp_path / "bundle.tar.gz"
    kpi_packet = _kpi_packet(ready=True)
    kpi_packet["product_kpi"]["onsps_backmap_evidence_schema_smoke"]["empty_blocked_reason"] = ""

    payload = mod.build_payload(
        kpi_packet=kpi_packet,
        rocm_manifest_packet=_rocm_packet(ready=True),
        product_image_preflight_packet=_image_preflight_packet(clean_ready=True),
        artifact_specs=_artifact_specs(tmp_path, kpi_packet=kpi_packet),
        out_tar=str(out_tar),
    )

    summary = payload["summary"]
    assert summary["bundle_export_ready"] is True
    assert summary["bundle_validation_pass"] is False
    assert summary["product_claim_ready"] is False
    assert {"code": "kpi_claim_metadata_gates_not_validated"} in payload["blockers"]
    assert any(
        error.startswith("kpi_onsps_backmap_empty_blocker_missing:")
        for error in summary["bundle_validation_errors"]
    )


def test_ai_md_product_evidence_bundle_blocks_onsps_runner_legacy_import_drift(
    tmp_path: Path,
) -> None:
    out_tar = tmp_path / "bundle.tar.gz"
    kpi_packet = _kpi_packet(ready=True)
    smoke = kpi_packet["product_kpi"]["onsps_backmap_evidence_schema_smoke"]
    smoke["product_runner_direct_engine_import_ready"] = False
    smoke["product_runner_import_source"] = "core.onsps_backmap"
    smoke["product_runner_legacy_core_import_absent"] = False

    payload = mod.build_payload(
        kpi_packet=kpi_packet,
        rocm_manifest_packet=_rocm_packet(ready=True),
        product_image_preflight_packet=_image_preflight_packet(clean_ready=True),
        artifact_specs=_artifact_specs(tmp_path, kpi_packet=kpi_packet),
        out_tar=str(out_tar),
    )

    summary = payload["summary"]
    assert summary["bundle_export_ready"] is True
    assert summary["bundle_validation_pass"] is False
    assert summary["product_claim_ready"] is False
    assert {"code": "kpi_claim_metadata_gates_not_validated"} in payload["blockers"]
    assert any(
        error.startswith("kpi_onsps_product_runner_direct_engine_import_missing:")
        for error in summary["bundle_validation_errors"]
    )


def test_ai_md_product_evidence_bundle_blocks_product_claim_without_core_forcefield_bridge_gate(tmp_path: Path) -> None:
    out_tar = tmp_path / "bundle.tar.gz"
    kpi_packet = _kpi_packet(ready=True, core_forcefield_bridge_ready=False)

    payload = mod.build_payload(
        kpi_packet=kpi_packet,
        rocm_manifest_packet=_rocm_packet(ready=True),
        product_image_preflight_packet=_image_preflight_packet(clean_ready=True),
        artifact_specs=_artifact_specs(tmp_path, kpi_packet=kpi_packet),
        out_tar=str(out_tar),
    )

    summary = payload["summary"]
    assert summary["bundle_export_ready"] is True
    assert summary["bundle_validation_pass"] is False
    assert summary["product_claim_ready"] is False
    assert summary["core_forcefield_bridge_ready"] is False
    assert summary["kpi_claim_metadata_gates_validated"] is False
    assert {"code": "core_forcefield_bridge_not_ready"} in payload["blockers"]
    assert {"code": "kpi_claim_metadata_gates_not_validated"} in payload["blockers"]
    assert any(
        error.startswith("kpi_core_forcefield_bridge_not_ready:")
        for error in summary["bundle_validation_errors"]
    )


def test_ai_md_product_evidence_bundle_blocks_core_forcefield_bridge_detail_mismatch(
    tmp_path: Path,
) -> None:
    out_tar = tmp_path / "bundle.tar.gz"
    kpi_packet = _kpi_packet(ready=True)
    kpi_packet["product_kpi"]["core_forcefield_bridge_smoke"]["force_term_plugins"] = ["directional_hbond"]

    payload = mod.build_payload(
        kpi_packet=kpi_packet,
        rocm_manifest_packet=_rocm_packet(ready=True),
        product_image_preflight_packet=_image_preflight_packet(clean_ready=True),
        artifact_specs=_artifact_specs(tmp_path, kpi_packet=kpi_packet),
        out_tar=str(out_tar),
    )

    summary = payload["summary"]
    assert summary["bundle_export_ready"] is True
    assert summary["bundle_validation_pass"] is False
    assert summary["product_claim_ready"] is False
    assert {"code": "kpi_claim_metadata_gates_not_validated"} in payload["blockers"]
    assert any(
        error.startswith("kpi_core_forcefield_bridge_plugins_invalid:")
        for error in summary["bundle_validation_errors"]
    )


def test_ai_md_product_evidence_bundle_blocks_core_forcefield_bridge_unsafe_claim_promotion(
    tmp_path: Path,
) -> None:
    out_tar = tmp_path / "bundle.tar.gz"
    kpi_packet = _kpi_packet(ready=True)
    bridge = kpi_packet["product_kpi"]["core_forcefield_bridge_smoke"]
    bridge["unsafe_base_claim_blocked"] = False
    bridge["unsafe_base_claim_safe"] = True
    bridge["unsafe_base_blocked_reason"] = ""
    bridge["unsafe_base_claim_safe_count"] = 1
    bridge["unsafe_base_blocked_count"] = 0
    bridge["unsafe_base_claim_rows"][0]["claim_safe"] = True
    bridge["unsafe_base_claim_rows"][0]["blocked_reason"] = ""
    rows = kpi_packet["product_kpi"]["core_compatibility_layer_smoke"]["rows"]
    forcefield_row = next(row for row in rows if row["contract"] == "forcefield_product_bridge")
    forcefield_row["unsafe_base_claim_blocked"] = False
    forcefield_row["unsafe_base_claim_safe"] = True
    forcefield_row["unsafe_base_blocked_reason"] = ""
    forcefield_row["unsafe_base_claim_safe_count"] = 1
    forcefield_row["unsafe_base_blocked_count"] = 0
    forcefield_row["unsafe_base_claim_rows"][0]["claim_safe"] = True
    forcefield_row["unsafe_base_claim_rows"][0]["blocked_reason"] = ""

    payload = mod.build_payload(
        kpi_packet=kpi_packet,
        rocm_manifest_packet=_rocm_packet(ready=True),
        product_image_preflight_packet=_image_preflight_packet(clean_ready=True),
        artifact_specs=_artifact_specs(tmp_path, kpi_packet=kpi_packet),
        out_tar=str(out_tar),
    )

    summary = payload["summary"]
    assert summary["bundle_export_ready"] is True
    assert summary["bundle_validation_pass"] is False
    assert summary["product_claim_ready"] is False
    assert {"code": "kpi_claim_metadata_gates_not_validated"} in payload["blockers"]
    assert any(
        error.startswith("kpi_core_forcefield_bridge_unsafe_base_claim_not_blocked:")
        for error in summary["bundle_validation_errors"]
    )
    assert any(
        error.startswith("kpi_core_forcefield_compat_unsafe_base_claim_not_blocked:")
        for error in summary["bundle_validation_errors"]
    )


def test_ai_md_product_evidence_bundle_blocks_core_forcefield_bridge_without_neighbor_diagnostics(
    tmp_path: Path,
) -> None:
    out_tar = tmp_path / "bundle.tar.gz"
    kpi_packet = _kpi_packet(ready=True)
    bridge = kpi_packet["product_kpi"]["core_forcefield_bridge_smoke"]
    bridge["neighbor_diagnostics_ready"] = False
    bridge["neighbor_pair_count"] = 0
    bridge["neighbor_source"] = ""
    rows = kpi_packet["product_kpi"]["core_compatibility_layer_smoke"]["rows"]
    forcefield_row = next(row for row in rows if row["contract"] == "forcefield_product_bridge")
    forcefield_row["neighbor_diagnostics_ready"] = False
    forcefield_row["neighbor_pair_count"] = 0
    forcefield_row["neighbor_source"] = ""

    payload = mod.build_payload(
        kpi_packet=kpi_packet,
        rocm_manifest_packet=_rocm_packet(ready=True),
        product_image_preflight_packet=_image_preflight_packet(clean_ready=True),
        artifact_specs=_artifact_specs(tmp_path, kpi_packet=kpi_packet),
        out_tar=str(out_tar),
    )

    summary = payload["summary"]
    assert summary["bundle_export_ready"] is True
    assert summary["bundle_validation_pass"] is False
    assert summary["product_claim_ready"] is False
    assert {"code": "kpi_claim_metadata_gates_not_validated"} in payload["blockers"]
    assert any(
        error.startswith("kpi_core_forcefield_bridge_neighbor_diagnostics_missing:")
        for error in summary["bundle_validation_errors"]
    )
    assert any(
        error.startswith("kpi_core_forcefield_compat_neighbor_diagnostics_missing:")
        for error in summary["bundle_validation_errors"]
    )


def test_ai_md_product_evidence_bundle_blocks_product_claim_without_core_compatibility_layer_gate(
    tmp_path: Path,
) -> None:
    out_tar = tmp_path / "bundle.tar.gz"
    kpi_packet = _kpi_packet(ready=True, core_compatibility_layer_ready=False)

    payload = mod.build_payload(
        kpi_packet=kpi_packet,
        rocm_manifest_packet=_rocm_packet(ready=True),
        product_image_preflight_packet=_image_preflight_packet(clean_ready=True),
        artifact_specs=_artifact_specs(tmp_path, kpi_packet=kpi_packet),
        out_tar=str(out_tar),
    )

    summary = payload["summary"]
    assert summary["bundle_export_ready"] is True
    assert summary["bundle_validation_pass"] is False
    assert summary["product_claim_ready"] is False
    assert summary["core_compatibility_layer_ready"] is False
    assert summary["kpi_claim_metadata_gates_validated"] is False
    assert {"code": "core_compatibility_layer_not_ready"} in payload["blockers"]
    assert {"code": "kpi_claim_metadata_gates_not_validated"} in payload["blockers"]
    assert any(
        error.startswith("kpi_core_compatibility_layer_not_ready:")
        for error in summary["bundle_validation_errors"]
    )


def test_ai_md_product_evidence_bundle_blocks_core_compatibility_layer_detail_mismatch(
    tmp_path: Path,
) -> None:
    out_tar = tmp_path / "bundle.tar.gz"
    kpi_packet = _kpi_packet(ready=True)
    rows = kpi_packet["product_kpi"]["core_compatibility_layer_smoke"]["rows"]
    rows[1]["canonical_module"] = "core.topology"

    payload = mod.build_payload(
        kpi_packet=kpi_packet,
        rocm_manifest_packet=_rocm_packet(ready=True),
        product_image_preflight_packet=_image_preflight_packet(clean_ready=True),
        artifact_specs=_artifact_specs(tmp_path, kpi_packet=kpi_packet),
        out_tar=str(out_tar),
    )

    summary = payload["summary"]
    assert summary["bundle_export_ready"] is True
    assert summary["bundle_validation_pass"] is False
    assert summary["product_claim_ready"] is False
    assert {"code": "kpi_claim_metadata_gates_not_validated"} in payload["blockers"]
    assert any(
        error.startswith("kpi_core_compatibility_layer_canonical_module_invalid:")
        for error in summary["bundle_validation_errors"]
    )


def test_ai_md_product_evidence_bundle_blocks_core_forcefield_bridge_energy_forces_shape_drift(
    tmp_path: Path,
) -> None:
    out_tar = tmp_path / "bundle.tar.gz"
    kpi_packet = _kpi_packet(ready=True)
    bridge = kpi_packet["product_kpi"]["core_forcefield_bridge_smoke"]
    bridge["energy_shape"] = [2]
    bridge["forces_shape"] = "not_a_list"

    payload = mod.build_payload(
        kpi_packet=kpi_packet,
        rocm_manifest_packet=_rocm_packet(ready=True),
        product_image_preflight_packet=_image_preflight_packet(clean_ready=True),
        artifact_specs=_artifact_specs(tmp_path, kpi_packet=kpi_packet),
        out_tar=str(out_tar),
    )

    summary = payload["summary"]
    assert summary["bundle_export_ready"] is True
    assert summary["bundle_validation_pass"] is False
    assert summary["product_claim_ready"] is False
    assert {"code": "kpi_claim_metadata_gates_not_validated"} in payload["blockers"]
    assert any(
        error.startswith("kpi_core_forcefield_bridge_energy_shape_invalid:")
        for error in summary["bundle_validation_errors"]
    )
    assert any(
        error.startswith("kpi_core_forcefield_bridge_forces_shape_missing:")
        for error in summary["bundle_validation_errors"]
    )


def test_ai_md_product_evidence_bundle_blocks_core_forcefield_bridge_claim_metadata_drift(
    tmp_path: Path,
) -> None:
    out_tar = tmp_path / "bundle.tar.gz"
    kpi_packet = _kpi_packet(ready=True)
    bridge = kpi_packet["product_kpi"]["core_forcefield_bridge_smoke"]
    bridge["result_claim_safe"] = False
    bridge["force_term_claim_metadata_ready"] = False
    rows = kpi_packet["product_kpi"]["core_compatibility_layer_smoke"]["rows"]
    forcefield_row = next(row for row in rows if row["contract"] == "forcefield_product_bridge")
    forcefield_row["result_claim_safe"] = False
    forcefield_row["force_term_claim_metadata_ready"] = False

    payload = mod.build_payload(
        kpi_packet=kpi_packet,
        rocm_manifest_packet=_rocm_packet(ready=True),
        product_image_preflight_packet=_image_preflight_packet(clean_ready=True),
        artifact_specs=_artifact_specs(tmp_path, kpi_packet=kpi_packet),
        out_tar=str(out_tar),
    )

    summary = payload["summary"]
    assert summary["bundle_export_ready"] is True
    assert summary["bundle_validation_pass"] is False
    assert summary["product_claim_ready"] is False
    assert {"code": "kpi_claim_metadata_gates_not_validated"} in payload["blockers"]
    assert any(
        error.startswith("kpi_core_forcefield_bridge_claim_not_safe:")
        for error in summary["bundle_validation_errors"]
    )
    assert any(
        error.startswith("kpi_core_forcefield_bridge_claim_metadata_not_ready:")
        for error in summary["bundle_validation_errors"]
    )
    assert any(
        error.startswith("kpi_core_forcefield_compat_claim_not_safe:")
        for error in summary["bundle_validation_errors"]
    )
    assert any(
        error.startswith("kpi_core_forcefield_compat_claim_metadata_not_ready:")
        for error in summary["bundle_validation_errors"]
    )


def test_ai_md_product_evidence_bundle_blocks_core_forcefield_bridge_execution_scope_drift(
    tmp_path: Path,
) -> None:
    out_tar = tmp_path / "bundle.tar.gz"
    kpi_packet = _kpi_packet(ready=True)
    kpi_packet["product_kpi"]["core_forcefield_bridge_smoke"]["bridge_execution_scope"] = (
        "runtime_gpu_product_engine_claim"
    )

    payload = mod.build_payload(
        kpi_packet=kpi_packet,
        rocm_manifest_packet=_rocm_packet(ready=True),
        product_image_preflight_packet=_image_preflight_packet(clean_ready=True),
        artifact_specs=_artifact_specs(tmp_path, kpi_packet=kpi_packet),
        out_tar=str(out_tar),
    )

    summary = payload["summary"]
    assert summary["bundle_export_ready"] is True
    assert summary["bundle_validation_pass"] is False
    assert summary["product_claim_ready"] is False
    assert {"code": "kpi_claim_metadata_gates_not_validated"} in payload["blockers"]
    assert any(
        error.startswith("kpi_core_forcefield_bridge_scope_invalid:")
        for error in summary["bundle_validation_errors"]
    )


def test_ai_md_product_evidence_bundle_blocks_core_topology_bridge_sequence_mapped_drift(
    tmp_path: Path,
) -> None:
    out_tar = tmp_path / "bundle.tar.gz"
    kpi_packet = _kpi_packet(ready=True)
    rows = kpi_packet["product_kpi"]["core_compatibility_layer_smoke"]["rows"]
    topology_row = next(row for row in rows if row["contract"] == "topology_protein_bridge")
    topology_row["topology_fidelity"] = "placeholder_alanine"

    payload = mod.build_payload(
        kpi_packet=kpi_packet,
        rocm_manifest_packet=_rocm_packet(ready=True),
        product_image_preflight_packet=_image_preflight_packet(clean_ready=True),
        artifact_specs=_artifact_specs(tmp_path, kpi_packet=kpi_packet),
        out_tar=str(out_tar),
    )

    summary = payload["summary"]
    assert summary["bundle_export_ready"] is True
    assert summary["bundle_validation_pass"] is False
    assert summary["product_claim_ready"] is False
    assert {"code": "kpi_claim_metadata_gates_not_validated"} in payload["blockers"]
    assert any(
        error.startswith("kpi_core_topology_bridge_fidelity_invalid:")
        for error in summary["bundle_validation_errors"]
    )


def test_ai_md_product_evidence_bundle_blocks_core_topology_bridge_protein_type_and_hbond_roles_drift(
    tmp_path: Path,
) -> None:
    out_tar = tmp_path / "bundle.tar.gz"
    kpi_packet = _kpi_packet(ready=True)
    rows = kpi_packet["product_kpi"]["core_compatibility_layer_smoke"]["rows"]
    topology_row = next(row for row in rows if row["contract"] == "topology_protein_bridge")
    topology_row["protein_topology_type"] = "LegacyTopology"
    topology_row["hbond_role_count"] = 0

    payload = mod.build_payload(
        kpi_packet=kpi_packet,
        rocm_manifest_packet=_rocm_packet(ready=True),
        product_image_preflight_packet=_image_preflight_packet(clean_ready=True),
        artifact_specs=_artifact_specs(tmp_path, kpi_packet=kpi_packet),
        out_tar=str(out_tar),
    )

    summary = payload["summary"]
    assert summary["bundle_export_ready"] is True
    assert summary["bundle_validation_pass"] is False
    assert summary["product_claim_ready"] is False
    assert {"code": "kpi_claim_metadata_gates_not_validated"} in payload["blockers"]
    assert any(
        error.startswith("kpi_core_topology_bridge_type_invalid:")
        for error in summary["bundle_validation_errors"]
    )
    assert any(
        error.startswith("kpi_core_topology_bridge_hbond_roles_missing:")
        for error in summary["bundle_validation_errors"]
    )


def test_ai_md_product_evidence_bundle_blocks_core_adress_production_guard_drift(
    tmp_path: Path,
) -> None:
    out_tar = tmp_path / "bundle.tar.gz"
    kpi_packet = _kpi_packet(ready=True)
    rows = kpi_packet["product_kpi"]["core_compatibility_layer_smoke"]["rows"]
    adress_row = next(row for row in rows if row["contract"] == "adress_production_blocked_log")
    adress_row["adress_log_blocked"] = False
    adress_row["adress_log_active_claim_absent"] = False
    adress_row["adress_neighbor_blocked"] = False

    payload = mod.build_payload(
        kpi_packet=kpi_packet,
        rocm_manifest_packet=_rocm_packet(ready=True),
        product_image_preflight_packet=_image_preflight_packet(clean_ready=True),
        artifact_specs=_artifact_specs(tmp_path, kpi_packet=kpi_packet),
        out_tar=str(out_tar),
    )

    summary = payload["summary"]
    assert summary["bundle_export_ready"] is True
    assert summary["bundle_validation_pass"] is False
    assert summary["product_claim_ready"] is False
    assert {"code": "kpi_claim_metadata_gates_not_validated"} in payload["blockers"]
    assert any(
        error.startswith("kpi_core_adress_blocked_log_missing:")
        for error in summary["bundle_validation_errors"]
    )
    assert any(
        error.startswith("kpi_core_adress_active_claim_present:")
        for error in summary["bundle_validation_errors"]
    )
    assert any(
        error.startswith("kpi_core_adress_neighbor_not_blocked:")
        for error in summary["bundle_validation_errors"]
    )


def test_ai_md_product_evidence_bundle_blocks_core_onsps_backmap_shim_import_identity_drift(
    tmp_path: Path,
) -> None:
    out_tar = tmp_path / "bundle.tar.gz"
    kpi_packet = _kpi_packet(ready=True)
    rows = kpi_packet["product_kpi"]["core_compatibility_layer_smoke"]["rows"]
    onsps_row = next(row for row in rows if row["contract"] == "onsps_backmap_shim")
    onsps_row["legacy_module"] = "core.onsps"
    onsps_row["canonical_module"] = "betelgeuze_engine.backmapping.legacy_onsps"
    onsps_row["bridge_type"] = "reexport_wrapper"

    payload = mod.build_payload(
        kpi_packet=kpi_packet,
        rocm_manifest_packet=_rocm_packet(ready=True),
        product_image_preflight_packet=_image_preflight_packet(clean_ready=True),
        artifact_specs=_artifact_specs(tmp_path, kpi_packet=kpi_packet),
        out_tar=str(out_tar),
    )

    summary = payload["summary"]
    assert summary["bundle_export_ready"] is True
    assert summary["bundle_validation_pass"] is False
    assert summary["product_claim_ready"] is False
    assert {"code": "kpi_claim_metadata_gates_not_validated"} in payload["blockers"]
    assert any(
        error.startswith("kpi_core_compatibility_layer_legacy_module_invalid:")
        for error in summary["bundle_validation_errors"]
    )
    assert any(
        error.startswith("kpi_core_compatibility_layer_canonical_module_invalid:")
        for error in summary["bundle_validation_errors"]
    )
    assert any(
        error.startswith("kpi_core_compatibility_layer_bridge_type_invalid:")
        for error in summary["bundle_validation_errors"]
    )


def test_ai_md_product_evidence_bundle_blocks_without_job_store_lazy_factory_gate(
    tmp_path: Path,
) -> None:
    out_tar = tmp_path / "bundle.tar.gz"
    kpi_packet = _kpi_packet(ready=True, job_store_lazy_factory_ready=False)

    payload = mod.build_payload(
        kpi_packet=kpi_packet,
        rocm_manifest_packet=_rocm_packet(ready=True),
        product_image_preflight_packet=_image_preflight_packet(clean_ready=True),
        artifact_specs=_artifact_specs(tmp_path, kpi_packet=kpi_packet),
        out_tar=str(out_tar),
    )

    summary = payload["summary"]
    assert summary["bundle_export_ready"] is True
    assert summary["bundle_validation_pass"] is False
    assert summary["product_claim_ready"] is False
    assert summary["job_store_lazy_factory_ready"] is False
    assert summary["kpi_claim_metadata_gates_validated"] is False
    assert {"code": "job_store_lazy_factory_not_ready"} in payload["blockers"]
    assert {"code": "kpi_claim_metadata_gates_not_validated"} in payload["blockers"]
    assert any(
        error.startswith("kpi_job_store_lazy_factory_not_ready:")
        for error in summary["bundle_validation_errors"]
    )


def test_ai_md_product_evidence_bundle_blocks_without_allowlisted_runner_shim_gate(
    tmp_path: Path,
) -> None:
    out_tar = tmp_path / "bundle.tar.gz"
    kpi_packet = _kpi_packet(ready=True, allowlisted_runner_shim_contract_ready=False)

    payload = mod.build_payload(
        kpi_packet=kpi_packet,
        rocm_manifest_packet=_rocm_packet(ready=True),
        product_image_preflight_packet=_image_preflight_packet(clean_ready=True),
        artifact_specs=_artifact_specs(tmp_path, kpi_packet=kpi_packet),
        out_tar=str(out_tar),
    )

    summary = payload["summary"]
    assert summary["bundle_export_ready"] is True
    assert summary["bundle_validation_pass"] is False
    assert summary["product_claim_ready"] is False
    assert summary["allowlisted_runner_shim_contract_ready"] is False
    assert summary["kpi_claim_metadata_gates_validated"] is False
    assert {"code": "allowlisted_runner_shim_contract_not_ready"} in payload["blockers"]
    assert {"code": "kpi_claim_metadata_gates_not_validated"} in payload["blockers"]
    assert any(
        error.startswith("kpi_allowlisted_runner_shim_contract_not_ready:")
        for error in summary["bundle_validation_errors"]
    )
    assert any(
        error.startswith("pm_allowlisted_runner_shim_contract_gate_missing:")
        for error in summary["bundle_validation_errors"]
    )


def test_ai_md_product_evidence_bundle_blocks_allowlisted_runner_self_implementation(
    tmp_path: Path,
) -> None:
    out_tar = tmp_path / "bundle.tar.gz"
    kpi_packet = _kpi_packet(ready=True)
    row = kpi_packet["product_kpi"]["allowlisted_runner_shim_contract"]["rows"][0]
    row["shim_contract_type"] = "local_implementation"
    row["sys_modules_alias_ready"] = False
    row["self_implementation_blocked"] = False

    payload = mod.build_payload(
        kpi_packet=kpi_packet,
        rocm_manifest_packet=_rocm_packet(ready=True),
        product_image_preflight_packet=_image_preflight_packet(clean_ready=True),
        artifact_specs=_artifact_specs(tmp_path, kpi_packet=kpi_packet),
        out_tar=str(out_tar),
    )

    summary = payload["summary"]
    assert summary["bundle_export_ready"] is True
    assert summary["bundle_validation_pass"] is False
    assert summary["product_claim_ready"] is False
    assert {"code": "kpi_claim_metadata_gates_not_validated"} in payload["blockers"]
    assert any(
        error.startswith("kpi_allowlisted_runner_shim_contract_type_invalid:")
        for error in summary["bundle_validation_errors"]
    )
    assert any(
        error.startswith("kpi_allowlisted_runner_shim_sys_modules_alias_not_ready:")
        for error in summary["bundle_validation_errors"]
    )
    assert any(
        error.startswith("kpi_allowlisted_runner_shim_self_implementation_not_blocked:")
        for error in summary["bundle_validation_errors"]
    )


def test_ai_md_product_evidence_bundle_blocks_allowlisted_runner_identity_drift(
    tmp_path: Path,
) -> None:
    out_tar = tmp_path / "bundle.tar.gz"
    kpi_packet = _kpi_packet(ready=True)
    row = kpi_packet["product_kpi"]["allowlisted_runner_shim_contract"]["rows"][1]
    row["runner_script"] = "tools/run_ligand_backmapping_scoring_drift.py"
    row["profile_runner_script"] = "tools/run_ligand_backmapping_scoring_drift.py"
    row["adapter_import"] = "betelgeuze_engine.product.runners.backmapping_drift"

    payload = mod.build_payload(
        kpi_packet=kpi_packet,
        rocm_manifest_packet=_rocm_packet(ready=True),
        product_image_preflight_packet=_image_preflight_packet(clean_ready=True),
        artifact_specs=_artifact_specs(tmp_path, kpi_packet=kpi_packet),
        out_tar=str(out_tar),
    )

    summary = payload["summary"]
    assert summary["bundle_export_ready"] is True
    assert summary["bundle_validation_pass"] is False
    assert summary["product_claim_ready"] is False
    assert {"code": "kpi_claim_metadata_gates_not_validated"} in payload["blockers"]
    assert any(
        error.startswith("kpi_allowlisted_runner_shim_runner_script_invalid:")
        for error in summary["bundle_validation_errors"]
    )
    assert any(
        error.startswith("kpi_allowlisted_runner_shim_profile_runner_script_invalid:")
        for error in summary["bundle_validation_errors"]
    )
    assert any(
        error.startswith("kpi_allowlisted_runner_shim_adapter_import_invalid:")
        for error in summary["bundle_validation_errors"]
    )


def test_ai_md_product_evidence_bundle_blocks_allowlisted_runner_profile_id_drift(
    tmp_path: Path,
) -> None:
    out_tar = tmp_path / "bundle.tar.gz"
    kpi_packet = _kpi_packet(ready=True)
    row = kpi_packet["product_kpi"]["allowlisted_runner_shim_contract"]["rows"][1]
    row["profile_id"] = "backmapping_scoring.drifted"

    payload = mod.build_payload(
        kpi_packet=kpi_packet,
        rocm_manifest_packet=_rocm_packet(ready=True),
        product_image_preflight_packet=_image_preflight_packet(clean_ready=True),
        artifact_specs=_artifact_specs(tmp_path, kpi_packet=kpi_packet),
        out_tar=str(out_tar),
    )

    summary = payload["summary"]
    assert summary["bundle_validation_pass"] is False
    assert any(
        error.startswith("kpi_allowlisted_runner_shim_profile_identities_invalid:")
        for error in summary["bundle_validation_errors"]
    )
    assert any(
        error.startswith("kpi_allowlisted_runner_shim_row_missing:")
        for error in summary["bundle_validation_errors"]
    )


def test_ai_md_product_evidence_bundle_blocks_allowlisted_runner_hash_and_runtime_drift(
    tmp_path: Path,
) -> None:
    out_tar = tmp_path / "bundle.tar.gz"
    kpi_packet = _kpi_packet(ready=True)
    row = kpi_packet["product_kpi"]["allowlisted_runner_shim_contract"]["rows"][2]
    row["script_hash"] = "d" * 64
    row["profile_runner_script_sha256"] = "e" * 64
    row["hash_matches"] = False
    row["missing_runtime_symbols"] = "main"
    row["runtime_adapter_error"] = "ImportError: missing adapter"
    row["runtime_adapter_identity_ready"] = False
    row["error"] = "runner_profile_missing"
    row["ready"] = False

    payload = mod.build_payload(
        kpi_packet=kpi_packet,
        rocm_manifest_packet=_rocm_packet(ready=True),
        product_image_preflight_packet=_image_preflight_packet(clean_ready=True),
        artifact_specs=_artifact_specs(tmp_path, kpi_packet=kpi_packet),
        out_tar=str(out_tar),
    )

    summary = payload["summary"]
    assert summary["bundle_export_ready"] is True
    assert summary["bundle_validation_pass"] is False
    assert summary["product_claim_ready"] is False
    assert {"code": "kpi_claim_metadata_gates_not_validated"} in payload["blockers"]
    assert any(
        error.startswith("kpi_allowlisted_runner_shim_hash_mismatch:")
        for error in summary["bundle_validation_errors"]
    )
    assert any(
        error.startswith("kpi_allowlisted_runner_shim_hash_matches_not_true:")
        for error in summary["bundle_validation_errors"]
    )
    assert any(
        error.startswith("kpi_allowlisted_runner_shim_missing_runtime_symbols:")
        for error in summary["bundle_validation_errors"]
    )
    assert any(
        error.startswith("kpi_allowlisted_runner_shim_runtime_adapter_error:")
        for error in summary["bundle_validation_errors"]
    )
    assert any(
        error.startswith("kpi_allowlisted_runner_shim_runtime_adapter_identity_not_ready:")
        for error in summary["bundle_validation_errors"]
    )
    assert any(
        error.startswith("kpi_allowlisted_runner_shim_row_error:")
        for error in summary["bundle_validation_errors"]
    )
    assert any(
        error.startswith("kpi_allowlisted_runner_shim_row_not_ready:")
        for error in summary["bundle_validation_errors"]
    )


def test_ai_md_product_evidence_bundle_blocks_allowlisted_runner_extra_row(
    tmp_path: Path,
) -> None:
    out_tar = tmp_path / "bundle.tar.gz"
    kpi_packet = _kpi_packet(ready=True)
    contract = kpi_packet["product_kpi"]["allowlisted_runner_shim_contract"]
    contract["runner_count"] = 4
    contract["rows"].append(dict(contract["rows"][0]))

    payload = mod.build_payload(
        kpi_packet=kpi_packet,
        rocm_manifest_packet=_rocm_packet(ready=True),
        product_image_preflight_packet=_image_preflight_packet(clean_ready=True),
        artifact_specs=_artifact_specs(tmp_path, kpi_packet=kpi_packet),
        out_tar=str(out_tar),
    )

    summary = payload["summary"]
    assert summary["bundle_validation_pass"] is False
    assert any(
        error.startswith("kpi_allowlisted_runner_shim_runner_count_mismatch:")
        for error in summary["bundle_validation_errors"]
    )
    assert any(
        error.startswith("kpi_allowlisted_runner_shim_rows_count_mismatch:")
        for error in summary["bundle_validation_errors"]
    )


def test_ai_md_product_evidence_bundle_blocks_product_runner_engine_import_drift(
    tmp_path: Path,
) -> None:
    out_tar = tmp_path / "bundle.tar.gz"
    kpi_packet = _kpi_packet(ready=True)
    imports = kpi_packet["product_kpi"]["product_runner_engine_imports_smoke"]
    row = imports["rows"][0]
    row["direct_import_present"] = False
    row["legacy_import_absent"] = False
    row["ready"] = False
    row["required_missing"] = ["evaluate_hbond_evidence"]
    row["forbidden_present"] = ["from theory.branches.hbond_logic import"]
    imports["ready"] = False
    kpi_packet["product_kpi"]["product_runner_engine_imports_ready"] = False
    kpi_packet["pm_kpi_summary"]["product"]["product_runner_engine_imports_ready"] = False

    payload = mod.build_payload(
        kpi_packet=kpi_packet,
        rocm_manifest_packet=_rocm_packet(ready=True),
        product_image_preflight_packet=_image_preflight_packet(clean_ready=True),
        artifact_specs=_artifact_specs(tmp_path, kpi_packet=kpi_packet),
        out_tar=str(out_tar),
    )

    summary = payload["summary"]
    assert summary["bundle_export_ready"] is True
    assert summary["bundle_validation_pass"] is False
    assert summary["product_claim_ready"] is False
    assert summary["product_runner_engine_imports_ready"] is False
    assert {"code": "product_runner_engine_imports_not_ready"} in payload["blockers"]
    assert {"code": "kpi_claim_metadata_gates_not_validated"} in payload["blockers"]
    assert any(
        error.startswith("kpi_product_runner_engine_imports_not_ready:")
        for error in summary["bundle_validation_errors"]
    )
    assert any(
        error.startswith("kpi_product_runner_engine_imports_smoke_not_ready:")
        for error in summary["bundle_validation_errors"]
    )
    assert any(
        error.startswith("kpi_product_runner_engine_import_missing:")
        for error in summary["bundle_validation_errors"]
    )
    assert any(
        error.startswith("kpi_product_runner_legacy_import_present:")
        for error in summary["bundle_validation_errors"]
    )
    assert any(
        error.startswith("pm_product_runner_engine_imports_gate_missing:")
        for error in summary["bundle_validation_errors"]
    )


def test_ai_md_product_evidence_bundle_blocks_product_runner_core_import_drift(
    tmp_path: Path,
) -> None:
    out_tar = tmp_path / "bundle.tar.gz"
    kpi_packet = _kpi_packet(ready=True)
    no_core = kpi_packet["product_kpi"]["product_runner_no_core_imports_smoke"]
    row = no_core["rows"][0]
    row["legacy_core_import_violation_count"] = 1
    row["legacy_core_import_violations"] = [{"line": 3, "snippet": "from core.mm_gbsa import mm_gbsa_binding_energy"}]
    row["ready"] = False
    no_core["legacy_core_import_violation_count"] = 1
    no_core["ready"] = False
    kpi_packet["product_kpi"]["product_runner_no_core_imports_ready"] = False
    kpi_packet["pm_kpi_summary"]["product"]["product_runner_no_core_imports_ready"] = False

    payload = mod.build_payload(
        kpi_packet=kpi_packet,
        rocm_manifest_packet=_rocm_packet(ready=True),
        product_image_preflight_packet=_image_preflight_packet(clean_ready=True),
        artifact_specs=_artifact_specs(tmp_path, kpi_packet=kpi_packet),
        out_tar=str(out_tar),
    )

    summary = payload["summary"]
    assert summary["bundle_validation_pass"] is False
    assert summary["product_claim_ready"] is False
    assert summary["product_runner_no_core_imports_ready"] is False
    assert {"code": "product_runner_no_core_imports_not_ready"} in payload["blockers"]
    assert any(
        error.startswith("kpi_product_runner_no_core_imports_not_ready:")
        for error in summary["bundle_validation_errors"]
    )
    assert any(
        error.startswith("kpi_product_runner_no_core_imports_smoke_not_ready:")
        for error in summary["bundle_validation_errors"]
    )
    assert any(
        error.startswith("kpi_product_runner_no_core_import_violation_count_nonzero:")
        for error in summary["bundle_validation_errors"]
    )
    assert any(
        error.startswith("kpi_product_runner_core_import_present:")
        for error in summary["bundle_validation_errors"]
    )
    assert any(
        error.startswith("pm_product_runner_no_core_imports_gate_missing:")
        for error in summary["bundle_validation_errors"]
    )


def test_ai_md_product_evidence_bundle_blocks_topk_delivery_adapter_regression(
    tmp_path: Path,
) -> None:
    out_tar = tmp_path / "bundle.tar.gz"
    kpi_packet = _kpi_packet(ready=True)
    topk = kpi_packet["product_kpi"]["topk_delivery_engine_owned_smoke"]
    topk["ready"] = False
    topk["engine_forbidden_present"] = ['import_module("tools.product.run_ligand_topk_delivery")']
    topk["compatibility_self_implementation_present"] = True
    topk["runtime_identity_ready"] = False
    topk["claim_metadata_ready"] = False
    topk["claim_metadata_schema_version"] = ""
    topk["claim_metadata_claim_safe"] = False
    topk["claim_metadata_physical_accuracy_claim"] = True
    kpi_packet["product_kpi"]["topk_delivery_engine_owned_ready"] = False
    kpi_packet["pm_kpi_summary"]["product"]["topk_delivery_engine_owned_ready"] = False

    payload = mod.build_payload(
        kpi_packet=kpi_packet,
        rocm_manifest_packet=_rocm_packet(ready=True),
        product_image_preflight_packet=_image_preflight_packet(clean_ready=True),
        artifact_specs=_artifact_specs(tmp_path, kpi_packet=kpi_packet),
        out_tar=str(out_tar),
    )

    summary = payload["summary"]
    assert summary["bundle_validation_pass"] is False
    assert summary["product_claim_ready"] is False
    assert summary["topk_delivery_engine_owned_ready"] is False
    assert {"code": "topk_delivery_engine_owned_not_ready"} in payload["blockers"]
    assert any(
        error.startswith("kpi_topk_delivery_engine_owned_not_ready:")
        for error in summary["bundle_validation_errors"]
    )
    assert any(
        error.startswith("kpi_topk_delivery_engine_legacy_adapter_present:")
        for error in summary["bundle_validation_errors"]
    )
    assert any(
        error.startswith("kpi_topk_delivery_compatibility_self_implementation_present:")
        for error in summary["bundle_validation_errors"]
    )
    assert any(
        error.startswith("kpi_topk_delivery_runtime_identity_not_ready:")
        for error in summary["bundle_validation_errors"]
    )
    assert any(
        error.startswith("kpi_topk_delivery_claim_metadata_not_ready:")
        for error in summary["bundle_validation_errors"]
    )
    assert any(
        error.startswith("kpi_topk_delivery_claim_metadata_schema_invalid:")
        for error in summary["bundle_validation_errors"]
    )
    assert any(
        error.startswith("kpi_topk_delivery_claim_metadata_physical_claim_invalid:")
        for error in summary["bundle_validation_errors"]
    )
    assert any(
        error.startswith("pm_topk_delivery_engine_owned_gate_missing:")
        for error in summary["bundle_validation_errors"]
    )


def test_ai_md_product_evidence_bundle_blocks_score_residual_force_claim_drift(
    tmp_path: Path,
) -> None:
    out_tar = tmp_path / "bundle.tar.gz"
    kpi_packet = _kpi_packet(ready=True)
    imports = kpi_packet["product_kpi"]["product_runner_engine_imports_smoke"]
    row = next(
        item
        for item in imports["rows"]
        if item["contract"] == "score_residual_direct_engine_import"
    )
    row["residual_scope"] = "force_residual"
    row["physical_force_residual_claim"] = True

    payload = mod.build_payload(
        kpi_packet=kpi_packet,
        rocm_manifest_packet=_rocm_packet(ready=True),
        product_image_preflight_packet=_image_preflight_packet(clean_ready=True),
        artifact_specs=_artifact_specs(tmp_path, kpi_packet=kpi_packet),
        out_tar=str(out_tar),
    )

    summary = payload["summary"]
    assert summary["bundle_validation_pass"] is False
    assert summary["product_claim_ready"] is False
    assert any(
        error.startswith("kpi_product_runner_score_residual_scope_invalid:")
        for error in summary["bundle_validation_errors"]
    )
    assert any(
        error.startswith("kpi_product_runner_score_residual_force_claim_invalid:")
        for error in summary["bundle_validation_errors"]
    )


def test_ai_md_product_evidence_bundle_blocks_topology_correction_claim_drift(
    tmp_path: Path,
) -> None:
    out_tar = tmp_path / "bundle.tar.gz"
    kpi_packet = _kpi_packet(ready=True)
    imports = kpi_packet["product_kpi"]["product_runner_engine_imports_smoke"]
    row = next(
        item
        for item in imports["rows"]
        if item["contract"] == "topology_score_correction_direct_engine_import"
    )
    row["residual_scope"] = "force_residual"
    row["physical_force_residual_claim"] = True
    row["bounded_correction_required"] = False

    payload = mod.build_payload(
        kpi_packet=kpi_packet,
        rocm_manifest_packet=_rocm_packet(ready=True),
        product_image_preflight_packet=_image_preflight_packet(clean_ready=True),
        artifact_specs=_artifact_specs(tmp_path, kpi_packet=kpi_packet),
        out_tar=str(out_tar),
    )

    summary = payload["summary"]
    assert summary["bundle_validation_pass"] is False
    assert summary["product_claim_ready"] is False
    assert any(
        error.startswith("kpi_product_runner_topology_correction_scope_invalid:")
        for error in summary["bundle_validation_errors"]
    )
    assert any(
        error.startswith("kpi_product_runner_topology_correction_force_claim_invalid:")
        for error in summary["bundle_validation_errors"]
    )
    assert any(
        error.startswith("kpi_product_runner_topology_correction_bounded_gate_missing:")
        for error in summary["bundle_validation_errors"]
    )


def test_ai_md_product_evidence_bundle_blocks_mm_gbsa_claim_schema_drift(
    tmp_path: Path,
) -> None:
    out_tar = tmp_path / "bundle.tar.gz"
    kpi_packet = _kpi_packet(ready=True)
    imports = kpi_packet["product_kpi"]["product_runner_engine_imports_smoke"]
    row = next(
        item
        for item in imports["rows"]
        if item["contract"] == "mm_gbsa_refine_direct_engine_import"
    )
    row["refine_claim_safe_required"] = True
    row["claim_metadata_schema"] = ""

    payload = mod.build_payload(
        kpi_packet=kpi_packet,
        rocm_manifest_packet=_rocm_packet(ready=True),
        product_image_preflight_packet=_image_preflight_packet(clean_ready=True),
        artifact_specs=_artifact_specs(tmp_path, kpi_packet=kpi_packet),
        out_tar=str(out_tar),
    )

    summary = payload["summary"]
    assert summary["bundle_validation_pass"] is False
    assert summary["product_claim_ready"] is False
    assert any(
        error.startswith("kpi_product_runner_mm_gbsa_claim_safe_gate_invalid:")
        for error in summary["bundle_validation_errors"]
    )
    assert any(
        error.startswith("kpi_product_runner_mm_gbsa_claim_schema_invalid:")
        for error in summary["bundle_validation_errors"]
    )


def test_ai_md_product_evidence_bundle_blocks_without_force_residual_bounded_policy_gate(tmp_path: Path) -> None:
    out_tar = tmp_path / "bundle.tar.gz"
    kpi_packet = _kpi_packet(ready=True, force_residual_bounded_policy_ready=False)

    payload = mod.build_payload(
        kpi_packet=kpi_packet,
        rocm_manifest_packet=_rocm_packet(ready=True),
        product_image_preflight_packet=_image_preflight_packet(clean_ready=True),
        artifact_specs=_artifact_specs(tmp_path, kpi_packet=kpi_packet),
        out_tar=str(out_tar),
    )

    summary = payload["summary"]
    assert summary["bundle_export_ready"] is True
    assert summary["bundle_validation_pass"] is False
    assert summary["product_claim_ready"] is False
    assert {"code": "kpi_claim_metadata_gates_not_validated"} in payload["blockers"]
    assert any(
        error.startswith("pm_force_residual_bounded_policy_gate_missing:")
        for error in summary["bundle_validation_errors"]
    )


def test_ai_md_product_evidence_bundle_blocks_without_force_residual_observed_caps_gate(
    tmp_path: Path,
) -> None:
    out_tar = tmp_path / "bundle.tar.gz"
    kpi_packet = _kpi_packet(ready=True, force_residual_observed_caps_ready=False)

    payload = mod.build_payload(
        kpi_packet=kpi_packet,
        rocm_manifest_packet=_rocm_packet(ready=True),
        product_image_preflight_packet=_image_preflight_packet(clean_ready=True),
        artifact_specs=_artifact_specs(tmp_path, kpi_packet=kpi_packet),
        out_tar=str(out_tar),
    )

    summary = payload["summary"]
    assert summary["bundle_export_ready"] is True
    assert summary["bundle_validation_pass"] is False
    assert summary["product_claim_ready"] is False
    assert {"code": "kpi_claim_metadata_gates_not_validated"} in payload["blockers"]
    assert any(
        error.startswith("pm_force_residual_observed_caps_gate_missing:")
        for error in summary["bundle_validation_errors"]
    )


def test_ai_md_product_evidence_bundle_blocks_without_force_residual_contract_gate(
    tmp_path: Path,
) -> None:
    out_tar = tmp_path / "bundle.tar.gz"
    kpi_packet = _kpi_packet(ready=True, force_residual_contract_ready=False)

    payload = mod.build_payload(
        kpi_packet=kpi_packet,
        rocm_manifest_packet=_rocm_packet(ready=True),
        product_image_preflight_packet=_image_preflight_packet(clean_ready=True),
        artifact_specs=_artifact_specs(tmp_path, kpi_packet=kpi_packet),
        out_tar=str(out_tar),
    )

    summary = payload["summary"]
    assert summary["bundle_export_ready"] is True
    assert summary["bundle_validation_pass"] is False
    assert summary["product_claim_ready"] is False
    assert {"code": "kpi_claim_metadata_gates_not_validated"} in payload["blockers"]
    assert any(
        error.startswith("kpi_runtime_top10_force_residual_contract_not_ready:")
        for error in summary["bundle_validation_errors"]
    )
    assert any(
        error.startswith("pm_force_residual_contract_gate_missing:")
        for error in summary["bundle_validation_errors"]
    )


def test_ai_md_product_evidence_bundle_blocks_invalid_force_residual_applied_report(
    tmp_path: Path,
) -> None:
    out_tar = tmp_path / "bundle.tar.gz"
    kpi_packet = _kpi_packet(ready=True)
    applied_report = kpi_packet["runtime_kpi"]["top10_force_residual"]["last_report"]
    applied_report["claim_safe"] = False
    applied_report["max_force_norm"] = 26.0
    applied_report["force_norm_within_cap"] = False
    applied_report["rank_pct"] = 0.06

    payload = mod.build_payload(
        kpi_packet=kpi_packet,
        rocm_manifest_packet=_rocm_packet(ready=True),
        product_image_preflight_packet=_image_preflight_packet(clean_ready=True),
        artifact_specs=_artifact_specs(tmp_path, kpi_packet=kpi_packet),
        out_tar=str(out_tar),
    )

    summary = payload["summary"]
    assert summary["bundle_export_ready"] is True
    assert summary["bundle_validation_pass"] is False
    assert summary["product_claim_ready"] is False
    assert {"code": "kpi_claim_metadata_gates_not_validated"} in payload["blockers"]
    assert any(
        error.startswith("kpi_runtime_top10_force_residual_applied_report_invalid:")
        for error in summary["bundle_validation_errors"]
    )


def test_ai_md_product_evidence_bundle_blocks_missing_force_residual_applied_report(
    tmp_path: Path,
) -> None:
    out_tar = tmp_path / "bundle.tar.gz"
    kpi_packet = _kpi_packet(ready=True)
    del kpi_packet["runtime_kpi"]["top10_force_residual"]["last_report"]

    payload = mod.build_payload(
        kpi_packet=kpi_packet,
        rocm_manifest_packet=_rocm_packet(ready=True),
        product_image_preflight_packet=_image_preflight_packet(clean_ready=True),
        artifact_specs=_artifact_specs(tmp_path, kpi_packet=kpi_packet),
        out_tar=str(out_tar),
    )

    summary = payload["summary"]
    assert summary["bundle_export_ready"] is True
    assert summary["bundle_validation_pass"] is False
    assert summary["product_claim_ready"] is False
    assert {"code": "kpi_claim_metadata_gates_not_validated"} in payload["blockers"]
    assert any(
        error.startswith("kpi_runtime_top10_force_residual_applied_report_invalid:")
        for error in summary["bundle_validation_errors"]
    )


def test_ai_md_product_evidence_bundle_blocks_nonfinite_force_residual_applied_report(
    tmp_path: Path,
) -> None:
    out_tar = tmp_path / "bundle.tar.gz"
    kpi_packet = _kpi_packet(ready=True)
    applied_report = kpi_packet["runtime_kpi"]["top10_force_residual"]["last_report"]
    applied_report["rank_pct"] = "nan"
    applied_report["max_force_norm"] = "inf"
    applied_report["energy_drift_pct"] = "-inf"

    payload = mod.build_payload(
        kpi_packet=kpi_packet,
        rocm_manifest_packet=_rocm_packet(ready=True),
        product_image_preflight_packet=_image_preflight_packet(clean_ready=True),
        artifact_specs=_artifact_specs(tmp_path, kpi_packet=kpi_packet),
        out_tar=str(out_tar),
    )

    summary = payload["summary"]
    assert summary["bundle_export_ready"] is True
    assert summary["bundle_validation_pass"] is False
    assert summary["product_claim_ready"] is False
    assert {"code": "kpi_claim_metadata_gates_not_validated"} in payload["blockers"]
    assert any(
        error.startswith("kpi_runtime_top10_force_residual_applied_report_invalid:")
        for error in summary["bundle_validation_errors"]
    )


def test_ai_md_product_evidence_bundle_blocks_without_nonfinite_force_residual_smoke(
    tmp_path: Path,
) -> None:
    out_tar = tmp_path / "bundle.tar.gz"
    kpi_packet = _kpi_packet(ready=True)
    residual = kpi_packet["runtime_kpi"]["top10_force_residual"]
    residual["nonfinite_uncertainty_abstention_count"] = 0
    residual["nonfinite_delta_score_report"]["skipped_reason"] = ""

    payload = mod.build_payload(
        kpi_packet=kpi_packet,
        rocm_manifest_packet=_rocm_packet(ready=True),
        product_image_preflight_packet=_image_preflight_packet(clean_ready=True),
        artifact_specs=_artifact_specs(tmp_path, kpi_packet=kpi_packet),
        out_tar=str(out_tar),
    )

    summary = payload["summary"]
    assert summary["bundle_export_ready"] is True
    assert summary["bundle_validation_pass"] is False
    assert summary["product_claim_ready"] is False
    assert {"code": "kpi_claim_metadata_gates_not_validated"} in payload["blockers"]
    assert any(
        error.startswith("kpi_runtime_force_residual_nonfinite_uncertainty_abstention_missing:")
        for error in summary["bundle_validation_errors"]
    )
    assert any(
        error.startswith("kpi_runtime_force_residual_nonfinite_delta_report_invalid:")
        for error in summary["bundle_validation_errors"]
    )


def test_ai_md_product_evidence_bundle_blocks_without_force_residual_top_k_policy_gate(
    tmp_path: Path,
) -> None:
    out_tar = tmp_path / "bundle.tar.gz"
    kpi_packet = _kpi_packet(ready=True)
    residual = kpi_packet["runtime_kpi"]["top10_force_residual"]
    residual["top_k_policy_ready"] = False
    residual["outside_top_k_report"]["top_k_eligible"] = True
    kpi_packet["pm_kpi_summary"]["runtime"]["force_residual_top_k_policy_ready"] = False

    payload = mod.build_payload(
        kpi_packet=kpi_packet,
        rocm_manifest_packet=_rocm_packet(ready=True),
        product_image_preflight_packet=_image_preflight_packet(clean_ready=True),
        artifact_specs=_artifact_specs(tmp_path, kpi_packet=kpi_packet),
        out_tar=str(out_tar),
    )

    summary = payload["summary"]
    assert summary["bundle_export_ready"] is True
    assert summary["bundle_validation_pass"] is False
    assert summary["product_claim_ready"] is False
    assert {"code": "kpi_claim_metadata_gates_not_validated"} in payload["blockers"]
    assert any(
        error.startswith("kpi_runtime_top10_force_residual_top_k_policy_not_ready:")
        for error in summary["bundle_validation_errors"]
    )
    assert any(
        error.startswith("kpi_runtime_top10_force_residual_top_k_report_invalid:")
        for error in summary["bundle_validation_errors"]
    )
    assert any(
        error.startswith("pm_force_residual_top_k_policy_gate_missing:")
        for error in summary["bundle_validation_errors"]
    )


def test_ai_md_product_evidence_bundle_blocks_without_force_residual_contract_count_fields(
    tmp_path: Path,
) -> None:
    out_tar = tmp_path / "bundle.tar.gz"
    kpi_packet = _kpi_packet(ready=True)
    residual = kpi_packet["runtime_kpi"]["top10_force_residual"]
    del residual["contract_expected_report_count"]
    residual["contract_validated_report_count"] = 5
    residual["contract_validation_ready"] = False

    payload = mod.build_payload(
        kpi_packet=kpi_packet,
        rocm_manifest_packet=_rocm_packet(ready=True),
        product_image_preflight_packet=_image_preflight_packet(clean_ready=True),
        artifact_specs=_artifact_specs(tmp_path, kpi_packet=kpi_packet),
        out_tar=str(out_tar),
    )

    summary = payload["summary"]
    assert summary["bundle_export_ready"] is True
    assert summary["bundle_validation_pass"] is False
    assert summary["product_claim_ready"] is False
    assert {"code": "kpi_claim_metadata_gates_not_validated"} in payload["blockers"]
    assert any(
        error.startswith("kpi_runtime_top10_force_residual_contract_expected_count_low:")
        for error in summary["bundle_validation_errors"]
    )
    assert any(
        error.startswith("kpi_runtime_top10_force_residual_contract_validation_not_ready:")
        for error in summary["bundle_validation_errors"]
    )


def test_ai_md_product_evidence_bundle_blocks_force_residual_contract_count_too_low(
    tmp_path: Path,
) -> None:
    out_tar = tmp_path / "bundle.tar.gz"
    kpi_packet = _kpi_packet(ready=True)
    residual = kpi_packet["runtime_kpi"]["top10_force_residual"]
    residual["contract_expected_report_count"] = 6
    residual["contract_validated_report_count"] = 3
    residual["contract_validation_ready"] = False

    payload = mod.build_payload(
        kpi_packet=kpi_packet,
        rocm_manifest_packet=_rocm_packet(ready=True),
        product_image_preflight_packet=_image_preflight_packet(clean_ready=True),
        artifact_specs=_artifact_specs(tmp_path, kpi_packet=kpi_packet),
        out_tar=str(out_tar),
    )

    summary = payload["summary"]
    assert summary["bundle_export_ready"] is True
    assert summary["bundle_validation_pass"] is False
    assert summary["product_claim_ready"] is False
    assert {"code": "kpi_claim_metadata_gates_not_validated"} in payload["blockers"]
    assert any(
        error.startswith("kpi_runtime_top10_force_residual_contract_validated_count_low:")
        for error in summary["bundle_validation_errors"]
    )
    assert any(
        error.startswith("kpi_runtime_top10_force_residual_contract_validation_not_ready:")
        for error in summary["bundle_validation_errors"]
    )


def test_ai_md_product_evidence_bundle_blocks_force_residual_contract_count_inconsistent(
    tmp_path: Path,
) -> None:
    out_tar = tmp_path / "bundle.tar.gz"
    kpi_packet = _kpi_packet(ready=True)
    residual = kpi_packet["runtime_kpi"]["top10_force_residual"]
    residual["contract_validation_ready"] = False

    payload = mod.build_payload(
        kpi_packet=kpi_packet,
        rocm_manifest_packet=_rocm_packet(ready=True),
        product_image_preflight_packet=_image_preflight_packet(clean_ready=True),
        artifact_specs=_artifact_specs(tmp_path, kpi_packet=kpi_packet),
        out_tar=str(out_tar),
    )

    summary = payload["summary"]
    assert summary["bundle_export_ready"] is True
    assert summary["bundle_validation_pass"] is False
    assert summary["product_claim_ready"] is False
    assert {"code": "kpi_claim_metadata_gates_not_validated"} in payload["blockers"]
    assert any(
        error.startswith("kpi_runtime_top10_force_residual_contract_count_inconsistent:")
        for error in summary["bundle_validation_errors"]
    )


def test_ai_md_product_evidence_bundle_blocks_without_force_term_physics_gate(tmp_path: Path) -> None:
    out_tar = tmp_path / "bundle.tar.gz"
    kpi_packet = _kpi_packet(ready=True, force_term_physics_validation_ready=False)

    payload = mod.build_payload(
        kpi_packet=kpi_packet,
        rocm_manifest_packet=_rocm_packet(ready=True),
        product_image_preflight_packet=_image_preflight_packet(clean_ready=True),
        artifact_specs=_artifact_specs(tmp_path, kpi_packet=kpi_packet),
        out_tar=str(out_tar),
    )

    summary = payload["summary"]
    assert summary["bundle_export_ready"] is True
    assert summary["bundle_validation_pass"] is False
    assert summary["product_claim_ready"] is False
    assert {"code": "kpi_claim_metadata_gates_not_validated"} in payload["blockers"]
    assert any(
        error.startswith("pm_force_term_physics_validation_gate_missing:")
        for error in summary["bundle_validation_errors"]
    )


def test_ai_md_product_evidence_bundle_blocks_without_force_term_physics_claim_safe_gate(
    tmp_path: Path,
) -> None:
    out_tar = tmp_path / "bundle.tar.gz"
    kpi_packet = _kpi_packet(
        ready=True,
        force_term_physics_validation_claim_safe_ready=False,
    )

    payload = mod.build_payload(
        kpi_packet=kpi_packet,
        rocm_manifest_packet=_rocm_packet(ready=True),
        product_image_preflight_packet=_image_preflight_packet(clean_ready=True),
        artifact_specs=_artifact_specs(tmp_path, kpi_packet=kpi_packet),
        out_tar=str(out_tar),
    )

    summary = payload["summary"]
    assert summary["bundle_export_ready"] is True
    assert summary["bundle_validation_pass"] is False
    assert summary["product_claim_ready"] is False
    assert {"code": "kpi_claim_metadata_gates_not_validated"} in payload["blockers"]
    assert any(
        error.startswith("pm_force_term_physics_validation_claim_safe_gate_missing:")
        for error in summary["bundle_validation_errors"]
    )


def test_ai_md_product_evidence_bundle_blocks_without_raw_force_term_physics_rows(
    tmp_path: Path,
) -> None:
    out_tar = tmp_path / "bundle.tar.gz"
    kpi_packet = _kpi_packet(ready=True)
    physics = kpi_packet["physics_kpi"]
    physics["force_term_finite_difference_max_error"] = 1.0
    physics["force_term_physics_validation_rows"][0]["ready"] = False
    physics["force_term_physics_validation_rows"][0]["finite_difference_force_error"] = 1.0

    payload = mod.build_payload(
        kpi_packet=kpi_packet,
        rocm_manifest_packet=_rocm_packet(ready=True),
        product_image_preflight_packet=_image_preflight_packet(clean_ready=True),
        artifact_specs=_artifact_specs(tmp_path, kpi_packet=kpi_packet),
        out_tar=str(out_tar),
    )

    summary = payload["summary"]
    assert summary["bundle_export_ready"] is True
    assert summary["bundle_validation_pass"] is False
    assert summary["product_claim_ready"] is False
    assert {"code": "kpi_claim_metadata_gates_not_validated"} in payload["blockers"]
    assert any(
        error.startswith("kpi_physics_force_term_finite_difference_high:")
        for error in summary["bundle_validation_errors"]
    )
    assert any(
        error.startswith("kpi_physics_force_term_validation_row_not_ready:")
        for error in summary["bundle_validation_errors"]
    )
    assert any(
        error.startswith("kpi_physics_force_term_validation_row_finite_difference_high:")
        for error in summary["bundle_validation_errors"]
    )


def test_ai_md_product_evidence_bundle_blocks_without_chemistry_pm_gates(
    tmp_path: Path,
) -> None:
    out_tar = tmp_path / "bundle.tar.gz"
    kpi_packet = _kpi_packet(ready=True, chemistry_pm_gates_ready=False)

    payload = mod.build_payload(
        kpi_packet=kpi_packet,
        rocm_manifest_packet=_rocm_packet(ready=True),
        product_image_preflight_packet=_image_preflight_packet(clean_ready=True),
        artifact_specs=_artifact_specs(tmp_path, kpi_packet=kpi_packet),
        out_tar=str(out_tar),
    )

    summary = payload["summary"]
    assert summary["bundle_export_ready"] is True
    assert summary["bundle_validation_pass"] is False
    assert summary["product_claim_ready"] is False
    assert summary["chemistry_pm_gates_ready"] is False
    assert {"code": "chemistry_pm_gates_not_ready"} in payload["blockers"]
    assert {"code": "kpi_claim_metadata_gates_not_validated"} in payload["blockers"]
    assert any(
        error.startswith("pm_hbond_evidence_schema_gate_missing:")
        for error in summary["bundle_validation_errors"]
    )
    assert any(
        error.startswith("pm_ligand_topology_validity_schema_gate_missing:")
        for error in summary["bundle_validation_errors"]
    )
    assert any(
        error.startswith("pm_hbond_recovery_pose_gate_missing:")
        for error in summary["bundle_validation_errors"]
    )
    assert any(
        error.startswith("pm_hbond_geometry_evaluated_gate_missing:")
        for error in summary["bundle_validation_errors"]
    )
    assert any(
        error.startswith("pm_hbond_geometry_complete_gate_missing:")
        for error in summary["bundle_validation_errors"]
    )
    assert any(
        error.startswith("pm_overanchored_decoy_rejection_gate_missing:")
        for error in summary["bundle_validation_errors"]
    )


def test_ai_md_product_evidence_bundle_blocks_chemistry_pm_numeric_mismatch(
    tmp_path: Path,
) -> None:
    out_tar = tmp_path / "bundle.tar.gz"
    kpi_packet = _kpi_packet(ready=True)
    pm_chemistry = kpi_packet["pm_kpi_summary"]["chemistry"]
    pm_chemistry["hbond_donor_site_count"] = 999
    pm_chemistry["hbond_geometry_evaluated_fixture_count"] = 0
    pm_chemistry["hbond_geometry_complete_fixture_count"] = 0
    pm_chemistry["hbond_recovery_pose_ids"] = ["wrong_pose"]
    pm_chemistry["unsatisfied_donor_count"] = 999
    pm_chemistry["ring_validity_fixture_count"] = 0

    payload = mod.build_payload(
        kpi_packet=kpi_packet,
        rocm_manifest_packet=_rocm_packet(ready=True),
        product_image_preflight_packet=_image_preflight_packet(clean_ready=True),
        artifact_specs=_artifact_specs(tmp_path, kpi_packet=kpi_packet),
        out_tar=str(out_tar),
    )

    summary = payload["summary"]
    assert summary["bundle_export_ready"] is True
    assert summary["bundle_validation_pass"] is False
    assert summary["product_claim_ready"] is False
    assert {"code": "kpi_claim_metadata_gates_not_validated"} in payload["blockers"]
    assert any(
        error.startswith("pm_chemistry_hbond_donor_site_count_mismatch:")
        for error in summary["bundle_validation_errors"]
    )
    assert any(
        error.startswith("pm_chemistry_hbond_recovery_pose_ids_mismatch:")
        for error in summary["bundle_validation_errors"]
    )
    assert any(
        error.startswith("pm_chemistry_hbond_geometry_evaluated_count_mismatch:")
        for error in summary["bundle_validation_errors"]
    )
    assert any(
        error.startswith("pm_chemistry_hbond_geometry_complete_count_mismatch:")
        for error in summary["bundle_validation_errors"]
    )
    assert any(
        error.startswith("pm_chemistry_unsatisfied_donor_count_mismatch:")
        for error in summary["bundle_validation_errors"]
    )
    assert any(
        error.startswith("pm_chemistry_ring_fixture_count_mismatch:")
        for error in summary["bundle_validation_errors"]
    )


def test_ai_md_product_evidence_bundle_blocks_without_raw_chemistry_kpi_evidence(
    tmp_path: Path,
) -> None:
    out_tar = tmp_path / "bundle.tar.gz"
    kpi_packet = _kpi_packet(ready=True)
    chemistry = kpi_packet["chemistry_kpi"]
    chemistry["hbond_evidence_schema_ready_count"] = 0
    chemistry["chirality_preservation_fixture_count"] = 0
    chemistry["rows"][0]["hbond_pair_schema_ready"] = False
    chemistry["rows"][1]["hbond_geometry_evaluated"] = False
    chemistry["rows"][2]["hbond_geometry_complete"] = False
    chemistry["rows"][6]["chirality_status"] = "not_applicable"
    chemistry["rows"][7]["ligand_validity_blockers"] = []
    chemistry["rows"][8]["ring_status"] = "not_applicable"
    chemistry["rows"][9]["formal_charge_sum"] = 0
    chemistry["rows"][10]["tautomer_fixture_valid"] = False
    for row in chemistry["rows"]:
        row["hbond_angle_pass_count"] = 0

    payload = mod.build_payload(
        kpi_packet=kpi_packet,
        rocm_manifest_packet=_rocm_packet(ready=True),
        product_image_preflight_packet=_image_preflight_packet(clean_ready=True),
        artifact_specs=_artifact_specs(tmp_path, kpi_packet=kpi_packet),
        out_tar=str(out_tar),
    )

    summary = payload["summary"]
    assert summary["bundle_export_ready"] is True
    assert summary["bundle_validation_pass"] is False
    assert summary["product_claim_ready"] is False
    assert {"code": "kpi_claim_metadata_gates_not_validated"} in payload["blockers"]
    assert any(
        error.startswith("kpi_chemistry_hbond_schema_ready_count_mismatch:")
        for error in summary["bundle_validation_errors"]
    )
    assert any(
        error.startswith("kpi_chemistry_chirality_fixture_missing:")
        for error in summary["bundle_validation_errors"]
    )
    assert any(
        error.startswith("kpi_chemistry_row_hbond_pair_schema_not_ready:")
        for error in summary["bundle_validation_errors"]
    )
    assert any(
        error.startswith("kpi_chemistry_hbond_geometry_evaluated_count_mismatch:")
        for error in summary["bundle_validation_errors"]
    )
    assert any(
        error.startswith("kpi_chemistry_hbond_geometry_complete_count_mismatch:")
        for error in summary["bundle_validation_errors"]
    )
    assert any(
        error.startswith("kpi_chemistry_hbond_angle_pass_rows_missing:")
        for error in summary["bundle_validation_errors"]
    )
    assert any(
        error.startswith("kpi_chemistry_chirality_specified_row_invalid:")
        for error in summary["bundle_validation_errors"]
    )
    assert any(
        error.startswith("kpi_chemistry_unassigned_chirality_row_invalid:")
        for error in summary["bundle_validation_errors"]
    )
    assert any(
        error.startswith("kpi_chemistry_ring_fixture_row_invalid:")
        for error in summary["bundle_validation_errors"]
    )
    assert any(
        error.startswith("kpi_chemistry_protonation_fixture_row_invalid:")
        for error in summary["bundle_validation_errors"]
    )
    assert any(
        error.startswith("kpi_chemistry_tautomer_fixture_row_invalid:")
        for error in summary["bundle_validation_errors"]
    )


def test_ai_md_product_evidence_bundle_blocks_without_pose_ranking_hbond_benchmark(
    tmp_path: Path,
) -> None:
    out_tar = tmp_path / "bundle.tar.gz"
    kpi_packet = _kpi_packet(ready=True, pose_ranking_hbond_benchmark_ready=False)

    payload = mod.build_payload(
        kpi_packet=kpi_packet,
        rocm_manifest_packet=_rocm_packet(ready=True),
        product_image_preflight_packet=_image_preflight_packet(clean_ready=True),
        artifact_specs=_artifact_specs(tmp_path, kpi_packet=kpi_packet),
        out_tar=str(out_tar),
    )

    summary = payload["summary"]
    assert summary["bundle_export_ready"] is True
    assert summary["bundle_validation_pass"] is False
    assert summary["product_claim_ready"] is False
    assert summary["pose_ranking_hbond_benchmark_ready"] is False
    assert {"code": "pose_ranking_hbond_benchmark_not_ready"} in payload["blockers"]
    assert {"code": "kpi_claim_metadata_gates_not_validated"} in payload["blockers"]
    assert any(
        error.startswith("kpi_pose_ranking_hbond_benchmark_not_ready:")
        for error in summary["bundle_validation_errors"]
    )
    assert any(
        error.startswith("kpi_pose_ranking_top1_not_expected:")
        for error in summary["bundle_validation_errors"]
    )
    assert any(
        error.startswith("kpi_pose_ranking_hbond_recovery_missing:")
        for error in summary["bundle_validation_errors"]
    )
    assert any(
        error.startswith("kpi_pose_ranking_row_contracts_not_ready:")
        for error in summary["bundle_validation_errors"]
    )
    assert any(
        error.startswith("kpi_pose_ranking_rows_missing:")
        for error in summary["bundle_validation_errors"]
    )


def test_ai_md_product_evidence_bundle_blocks_pose_row_without_hbond_schema_contract(
    tmp_path: Path,
) -> None:
    out_tar = tmp_path / "bundle.tar.gz"
    kpi_packet = _kpi_packet(ready=True)
    rows = kpi_packet["pose_ranking_hbond_benchmark"]["rows"]
    rows[0]["hbond_pair_schema_ready"] = False
    rows[0]["hbond_angle_pass_count"] = 0
    rows[1]["hbond_status"] = "pass"
    rows[2]["unsatisfied_donor_count"] = 0
    rows[2]["unsatisfied_acceptor_count"] = 0
    rows[3]["overanchoring_flag"] = False

    payload = mod.build_payload(
        kpi_packet=kpi_packet,
        rocm_manifest_packet=_rocm_packet(ready=True),
        product_image_preflight_packet=_image_preflight_packet(clean_ready=True),
        artifact_specs=_artifact_specs(tmp_path, kpi_packet=kpi_packet),
        out_tar=str(out_tar),
    )

    summary = payload["summary"]
    assert summary["bundle_export_ready"] is True
    assert summary["bundle_validation_pass"] is False
    assert summary["product_claim_ready"] is False
    assert {"code": "kpi_claim_metadata_gates_not_validated"} in payload["blockers"]
    assert any(
        error.startswith("kpi_pose_ranking_row_hbond_pair_schema_not_ready:")
        for error in summary["bundle_validation_errors"]
    )
    assert any(
        error.startswith("kpi_pose_ranking_top1_geometry_evidence_missing:")
        for error in summary["bundle_validation_errors"]
    )
    assert any(
        error.startswith("kpi_pose_ranking_row_status_mismatch:")
        for error in summary["bundle_validation_errors"]
    )
    assert any(
        error.startswith("kpi_pose_ranking_blocked_role_unsatisfied_evidence_missing:")
        for error in summary["bundle_validation_errors"]
    )
    assert any(
        error.startswith("kpi_pose_ranking_overanchored_flag_missing:")
        for error in summary["bundle_validation_errors"]
    )


def _pose_drift_payload(
    tmp_path: Path,
    *,
    mutate,
) -> dict:
    out_tar = tmp_path / "bundle.tar.gz"
    kpi_packet = _kpi_packet(ready=True)
    mutate(kpi_packet["pose_ranking_hbond_benchmark"])
    return mod.build_payload(
        kpi_packet=kpi_packet,
        rocm_manifest_packet=_rocm_packet(ready=True),
        product_image_preflight_packet=_image_preflight_packet(clean_ready=True),
        artifact_specs=_artifact_specs(tmp_path, kpi_packet=kpi_packet),
        out_tar=str(out_tar),
    )


def test_ai_md_product_evidence_bundle_rejects_pose_benchmark_fixture_count_drift(tmp_path: Path) -> None:
    payload = _pose_drift_payload(
        tmp_path,
        mutate=lambda bench: bench.__setitem__("fixture_count", bench["fixture_count"] + 1),
    )
    summary = payload["summary"]
    assert summary["bundle_validation_pass"] is False
    assert summary["product_claim_ready"] is False
    assert {"code": "kpi_claim_metadata_gates_not_validated"} in payload["blockers"]
    assert any(
        error.startswith("kpi_pose_ranking_fixture_count_mismatch:")
        for error in summary["bundle_validation_errors"]
    )


def test_ai_md_product_evidence_bundle_rejects_pose_benchmark_row_contract_pass_count_drift(tmp_path: Path) -> None:
    payload = _pose_drift_payload(
        tmp_path,
        mutate=lambda bench: bench.__setitem__("row_contract_pass_count", bench["row_contract_pass_count"] + 1),
    )
    summary = payload["summary"]
    assert summary["bundle_validation_pass"] is False
    assert summary["product_claim_ready"] is False
    assert any(
        error.startswith("kpi_pose_ranking_row_contract_pass_count_mismatch:")
        for error in summary["bundle_validation_errors"]
    )


def test_ai_md_product_evidence_bundle_rejects_missing_hbond_recovery_benchmark(tmp_path: Path) -> None:
    payload = _pose_drift_payload(
        tmp_path,
        mutate=lambda bench: bench.pop("hbond_recovery_benchmark", None),
    )
    summary = payload["summary"]
    assert summary["bundle_validation_pass"] is False
    assert summary["product_claim_ready"] is False
    assert any(
        error.startswith("kpi_hbond_recovery_benchmark_not_ready:")
        for error in summary["bundle_validation_errors"]
    )
    assert any(
        error.startswith("kpi_hbond_recovery_benchmark_summary_schema_missing:")
        for error in summary["bundle_validation_errors"]
    )


def test_ai_md_product_evidence_bundle_rejects_pose_benchmark_required_pose_roles_drift(tmp_path: Path) -> None:
    payload = _pose_drift_payload(
        tmp_path,
        mutate=lambda bench: bench.__setitem__("required_pose_roles", bench["required_pose_roles"][:-1]),
    )
    summary = payload["summary"]
    assert summary["bundle_validation_pass"] is False
    assert summary["product_claim_ready"] is False
    assert any(
        error.startswith("kpi_pose_ranking_required_pose_roles_drift:")
        for error in summary["bundle_validation_errors"]
    )


def test_ai_md_product_evidence_bundle_rejects_pose_benchmark_observed_pose_roles_drift(tmp_path: Path) -> None:
    payload = _pose_drift_payload(
        tmp_path,
        mutate=lambda bench: bench.__setitem__("observed_pose_roles", bench["observed_pose_roles"] + ["phantom_role"]),
    )
    summary = payload["summary"]
    assert summary["bundle_validation_pass"] is False
    assert summary["product_claim_ready"] is False
    assert any(
        error.startswith("kpi_pose_ranking_observed_pose_roles_drift:")
        for error in summary["bundle_validation_errors"]
    )


def test_ai_md_product_evidence_bundle_rejects_missing_confidence_calibration_report(
    tmp_path: Path,
) -> None:
    out_tar = tmp_path / "bundle.tar.gz"
    kpi_packet = _kpi_packet(ready=True)
    kpi_packet["confidence_calibration_report"]["ready"] = False
    kpi_packet["confidence_calibration_report"]["status"] = "blocked_confidence_calibration_report"
    kpi_packet["confidence_calibration_report"]["rows"] = []
    kpi_packet["pm_kpi_summary"]["chemistry"]["confidence_calibration_report_ready"] = False

    payload = mod.build_payload(
        kpi_packet=kpi_packet,
        rocm_manifest_packet=_rocm_packet(ready=True),
        product_image_preflight_packet=_image_preflight_packet(clean_ready=True),
        artifact_specs=_artifact_specs(tmp_path, kpi_packet=kpi_packet),
        out_tar=str(out_tar),
    )

    summary = payload["summary"]
    assert summary["bundle_validation_pass"] is False
    assert summary["product_claim_ready"] is False
    assert summary["confidence_calibration_report_ready"] is False
    assert {"code": "confidence_calibration_report_not_ready"} in payload["blockers"]
    assert any(
        error.startswith("kpi_confidence_calibration_report_not_ready:")
        for error in summary["bundle_validation_errors"]
    )
    assert any(
        error.startswith("pm_confidence_calibration_gate_missing:")
        for error in summary["bundle_validation_errors"]
    )


def test_ai_md_product_evidence_bundle_rejects_confidence_calibration_pm_mirror_drift(
    tmp_path: Path,
) -> None:
    out_tar = tmp_path / "bundle.tar.gz"
    kpi_packet = _kpi_packet(ready=True)
    kpi_packet["confidence_calibration_report"]["blocked_reasons"] = ["manually_injected_blocker"]
    pm_chemistry = kpi_packet["pm_kpi_summary"]["chemistry"]
    pm_chemistry["confidence_calibration_status"] = "wrong_status"
    pm_chemistry["confidence_calibration_positive_count"] = 999
    pm_chemistry["confidence_calibration_negative_count"] = 999
    pm_chemistry["confidence_calibration_bin_count"] = 999
    pm_chemistry["confidence_calibration_brier_score"] = 0.99

    payload = mod.build_payload(
        kpi_packet=kpi_packet,
        rocm_manifest_packet=_rocm_packet(ready=True),
        product_image_preflight_packet=_image_preflight_packet(clean_ready=True),
        artifact_specs=_artifact_specs(tmp_path, kpi_packet=kpi_packet),
        out_tar=str(out_tar),
    )

    summary = payload["summary"]
    assert summary["bundle_validation_pass"] is False
    assert summary["product_claim_ready"] is False
    assert any(
        error.startswith("kpi_confidence_calibration_ready_with_blockers:")
        for error in summary["bundle_validation_errors"]
    )
    assert any(
        error.startswith("pm_confidence_calibration_status_mismatch:")
        for error in summary["bundle_validation_errors"]
    )
    assert any(
        error.startswith("pm_confidence_calibration_positive_count_mismatch:")
        for error in summary["bundle_validation_errors"]
    )
    assert any(
        error.startswith("pm_confidence_calibration_negative_count_mismatch:")
        for error in summary["bundle_validation_errors"]
    )
    assert any(
        error.startswith("pm_confidence_calibration_bin_count_mismatch:")
        for error in summary["bundle_validation_errors"]
    )
    assert any(
        error.startswith("pm_confidence_calibration_brier_mismatch:")
        for error in summary["bundle_validation_errors"]
    )


def test_ai_md_product_evidence_bundle_rejects_pose_benchmark_delta_backmap_yellow_band_missing(
    tmp_path: Path,
) -> None:
    def mutate(bench):
        bench["delta_backmap_yellow_band_abstention_ready"] = False
        for row in bench["rows"]:
            if row["benchmark_role"] == "delta_backmap_yellow_band_pose":
                row["hbond_delta_backmap_yellow_band"] = False
                row["hbond_blocked_reason"] = ""

    payload = _pose_drift_payload(tmp_path, mutate=mutate)
    summary = payload["summary"]
    assert summary["bundle_validation_pass"] is False
    assert summary["product_claim_ready"] is False
    assert any(
        error.startswith("kpi_pose_ranking_delta_backmap_yellow_band_not_ready:")
        for error in summary["bundle_validation_errors"]
    )
    assert any(
        error.startswith("kpi_pose_ranking_delta_backmap_yellow_band_row_missing:")
        for error in summary["bundle_validation_errors"]
    )


def test_ai_md_product_evidence_bundle_rejects_pose_benchmark_ranking_order_missing(tmp_path: Path) -> None:
    payload = _pose_drift_payload(
        tmp_path,
        mutate=lambda bench: bench.pop("ranking_order"),
    )
    summary = payload["summary"]
    assert summary["bundle_validation_pass"] is False
    assert summary["product_claim_ready"] is False
    assert any(
        error.startswith("kpi_pose_ranking_ranking_order_missing:")
        for error in summary["bundle_validation_errors"]
    )


def test_ai_md_product_evidence_bundle_rejects_pose_benchmark_ranking_order_head_drift(tmp_path: Path) -> None:
    def mutate(bench):
        order = list(bench["ranking_order"])
        order.reverse()
        bench["ranking_order"] = order

    payload = _pose_drift_payload(tmp_path, mutate=mutate)
    summary = payload["summary"]
    assert summary["bundle_validation_pass"] is False
    assert summary["product_claim_ready"] is False
    assert any(
        error.startswith("kpi_pose_ranking_top1_not_ranking_order_head:")
        for error in summary["bundle_validation_errors"]
    )


def test_ai_md_product_evidence_bundle_rejects_pose_benchmark_top1_not_hbond_recovery(tmp_path: Path) -> None:
    def mutate(bench):
        bench["top1_pose_id"] = "amide_far_decoy_pose"
        bench["top1_expected_pose_id"] = "amide_far_decoy_pose"

    payload = _pose_drift_payload(tmp_path, mutate=mutate)
    summary = payload["summary"]
    assert summary["bundle_validation_pass"] is False
    assert summary["product_claim_ready"] is False
    assert any(
        error.startswith("kpi_pose_ranking_top1_role_not_hbond_recovery:")
        for error in summary["bundle_validation_errors"]
    )


def test_ai_md_product_evidence_bundle_rejects_pose_benchmark_hbond_recovery_count_drift(tmp_path: Path) -> None:
    payload = _pose_drift_payload(
        tmp_path,
        mutate=lambda bench: bench.__setitem__("hbond_recovery_pose_count", bench["hbond_recovery_pose_count"] + 1),
    )
    summary = payload["summary"]
    assert summary["bundle_validation_pass"] is False
    assert summary["product_claim_ready"] is False
    assert any(
        error.startswith("kpi_pose_ranking_hbond_recovery_count_drift:")
        for error in summary["bundle_validation_errors"]
    )


def test_ai_md_product_evidence_bundle_rejects_pose_benchmark_overanchored_summary_drift(tmp_path: Path) -> None:
    payload = _pose_drift_payload(
        tmp_path,
        mutate=lambda bench: bench.__setitem__("overanchored_decoys_blocked", False),
    )
    summary = payload["summary"]
    assert summary["bundle_validation_pass"] is False
    assert summary["product_claim_ready"] is False
    assert any(
        error.startswith("kpi_pose_ranking_overanchored_summary_drift:")
        for error in summary["bundle_validation_errors"]
    )


def test_ai_md_product_evidence_bundle_rejects_pose_benchmark_unsatisfied_detected_summary_drift(tmp_path: Path) -> None:
    payload = _pose_drift_payload(
        tmp_path,
        mutate=lambda bench: bench.__setitem__("unsatisfied_donor_acceptor_detected", False),
    )
    summary = payload["summary"]
    assert summary["bundle_validation_pass"] is False
    assert summary["product_claim_ready"] is False
    assert any(
        error.startswith("kpi_pose_ranking_unsatisfied_detected_summary_drift:")
        for error in summary["bundle_validation_errors"]
    )


def test_ai_md_product_evidence_bundle_rejects_pose_benchmark_blocked_role_not_blocked(tmp_path: Path) -> None:
    def mutate(bench):
        for row in bench["rows"]:
            if row["benchmark_role"] == "far_decoy_pose":
                row["hbond_claim_safe"] = True
                row["expected_claim_safe"] = True
                row["hbond_blocked_reason"] = ""
                row["expected_blocked_reason"] = ""

    payload = _pose_drift_payload(tmp_path, mutate=mutate)
    summary = payload["summary"]
    assert summary["bundle_validation_pass"] is False
    assert summary["product_claim_ready"] is False
    assert any(
        error.startswith("kpi_pose_ranking_blocked_role_not_blocked:")
        and error.endswith(":far_decoy_pose")
        for error in summary["bundle_validation_errors"]
    )


def test_ai_md_product_evidence_bundle_rejects_build_mode_receipt_for_product_claim(tmp_path: Path) -> None:
    out_tar = tmp_path / "bundle.tar.gz"
    image_packet = _image_preflight_packet(clean_ready=True)
    image_packet["summary"]["receipt_mode"] = "build"

    payload = mod.build_payload(
        kpi_packet=_kpi_packet(ready=True),
        rocm_manifest_packet=_rocm_packet(ready=True),
        product_image_preflight_packet=image_packet,
        artifact_specs=_artifact_specs(tmp_path),
        out_tar=str(out_tar),
    )

    summary = payload["summary"]
    assert summary["bundle_export_ready"] is True
    assert summary["bundle_validation_pass"] is True
    assert summary["product_claim_ready"] is False
    assert summary["clean_container_smoke_ready"] is False
    assert summary["product_image_receipt_mode"] == "build"
    assert summary["next_required_step"].startswith("Run PRODUCT_IMAGE_VERIFY_MODE=rocm-runtime")
    assert "product_image_receipt_mode_rocm_runtime" in summary["clean_container_missing_requirements"]
    assert any(row["code"] == "clean_container_smoke_not_ready" for row in payload["blockers"])


def test_ai_md_product_evidence_bundle_blocks_missing_required_artifact(tmp_path: Path) -> None:
    out_tar = tmp_path / "bundle.tar.gz"
    specs = _artifact_specs(tmp_path)
    specs.append(
        {
            "artifact_id": "missing_required",
            "artifact_path": str(tmp_path / "missing.json"),
            "role": "required_evidence",
            "required": True,
        }
    )

    payload = mod.build_payload(
        kpi_packet=_kpi_packet(ready=True),
        rocm_manifest_packet=_rocm_packet(ready=True),
        product_image_preflight_packet=_image_preflight_packet(clean_ready=True),
        artifact_specs=specs,
        out_tar=str(out_tar),
    )

    assert payload["summary"]["status"] == "blocked_ai_md_product_evidence_bundle"
    assert payload["summary"]["bundle_export_ready"] is False
    assert payload["summary"]["required_artifact_missing_count"] == 1
    assert not out_tar.exists()


def test_ai_md_product_evidence_bundle_cli_writes_outputs(tmp_path: Path) -> None:
    kpi_packet = _kpi_packet(ready=True)
    runtime_plot = _write(
        tmp_path / "runtime_scaling.svg",
        "<svg xmlns=\"http://www.w3.org/2000/svg\"><text>Pair-count scaling advisory</text></svg>\n",
    )
    scaling = kpi_packet["runtime_kpi"]["neighbor_cap_scaling"]
    scaling["plot_path"] = str(runtime_plot)
    scaling["plot_sha256"] = _sha256(runtime_plot)
    scaling["plot_size_bytes"] = runtime_plot.stat().st_size
    pm_runtime = kpi_packet["pm_kpi_summary"]["runtime"]
    pm_runtime["runtime_neighbor_cap_scaling_plot_path"] = str(runtime_plot)
    pm_runtime["runtime_neighbor_cap_scaling_plot_sha256"] = _sha256(runtime_plot)
    kpi_json = _write(tmp_path / "kpi.json", json.dumps(kpi_packet))
    kpi_md = _write(tmp_path / "kpi.md")
    rocm_json = _write(tmp_path / "rocm.json", json.dumps(_rocm_packet(ready=True)))
    image_preflight_json = _write(tmp_path / "image_preflight.json", json.dumps(_image_preflight_packet(clean_ready=True)))
    next_doc = _write(tmp_path / "next.md")
    out_tar = tmp_path / "bundle.tar.gz"
    out_json = tmp_path / "bundle.json"
    out_csv = tmp_path / "bundle.csv"
    out_md = tmp_path / "bundle.md"

    rc = mod.main(
        [
            "--kpi-json",
            str(kpi_json),
            "--kpi-md",
            str(kpi_md),
            "--runtime-scaling-plot",
            str(runtime_plot),
            "--rocm-manifest-json",
            str(rocm_json),
            "--product-image-preflight-json",
            str(image_preflight_json),
            "--next-steps-doc",
            str(next_doc),
            "--out-tar",
            str(out_tar),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ]
    )

    assert rc == 0
    assert json.loads(out_json.read_text(encoding="utf-8"))["summary"]["bundle_export_ready"] is True
    assert out_tar.exists()
    assert out_csv.read_text(encoding="utf-8").startswith("artifact_id,")
    assert out_md.read_text(encoding="utf-8").startswith("# AI-MD Product Evidence Bundle")

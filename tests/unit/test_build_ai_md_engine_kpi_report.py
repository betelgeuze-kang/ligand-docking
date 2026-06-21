from __future__ import annotations

import hashlib
import json
from pathlib import Path

from tools.product.build_ai_md_engine_kpi_report import build_report, main
from tools.product import build_ai_md_product_evidence_bundle as bundle_mod


def _write_rocm_manifest(path: Path, *, ready: bool) -> None:
    path.write_text(
        json.dumps(
            {
                "summary": {
                    "status": "rocm_environment_manifest_ready",
                    "manifest_ready": True,
                    "commercial_compute_default": "rocm_hip",
                    "torch_rocm_ready": ready,
                    "visible_device_count": 1 if ready else 0,
                    "device_nodes_ready": ready,
                    "production_execution_ready": ready,
                    "cpu_fallback_allowed_for_product": False,
                    "product_runtime_completion_rule": (
                        "commercial_compute_default=rocm_hip; torch_rocm_ready=true; "
                        "visible_device_count>0; device_nodes_ready=true; cpu_fallback_allowed_for_product=false"
                    ),
                    "next_required_step": "Build AMD hardware throughput scorecard next."
                    if ready
                    else "Expose a visible ROCm/HIP AMD GPU device to PyTorch before production regeneration.",
                }
            }
        )
        + "\n",
        encoding="utf-8",
    )


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


def _write_product_evidence_bundle(
    path: Path,
    *,
    ready: bool = True,
    clean_ready: bool = True,
) -> Path:
    root = path.parent
    out_tar = root / "bundle.tar.gz"
    force_term_physics = _force_term_physics_validation_packet(ready=ready)
    chemistry_kpi = _chemistry_kpi_packet(ready=ready)
    kpi_packet = {
        "packet_type": "ai_md_engine_kpi_report",
        "status": "ai_md_engine_kpi_report_ready" if ready else "blocked_ai_md_engine_kpi_report",
        "report_ready": ready,
        "product_kpi": {
            "runner_claim_metadata_signed": True,
            "signed_manifest_verification_pass": True,
            "bundle_validation_pass": True,
            "product_claim_ready": True,
            "release_claim_ready": True,
            "release_claim_blocked_reason": "",
            "product_ci_runtime_gate_present": True,
            "product_ci_runtime_gate_ready": True,
            "product_ci_runtime_gate_status": "product_ci_runtime_gate_ready",
            "product_ci_remote_green": True,
            "product_ci_github_actions_started": True,
            "product_ci_external_blocker": False,
            "product_ci_blocker_code": "",
            "product_ci_billing_free_self_hosted_path_recommended": False,
            "product_ci_billing_free_self_hosted_api_worker_command": "",
            "product_ci_billing_free_self_hosted_rocm_runtime_command": "",
            "product_ci_hosted_spending_limit_increase_required": False,
            "product_ci_self_hosted_runner_inventory_present": True,
            "product_ci_self_hosted_runner_total_count": 2,
            "product_ci_self_hosted_linux_runner_online": True,
            "product_ci_self_hosted_linux_runner_count": 2,
            "product_ci_self_hosted_rocm_runner_online": True,
            "product_ci_self_hosted_rocm_runner_count": 1,
            "product_ci_self_hosted_runner_inventory_external_state_mutated": False,
            "product_ci_self_hosted_runner_host_preflight_present": True,
            "product_ci_self_hosted_runner_host_preflight_status": "github_self_hosted_runner_host_preflight_ready",
            "product_ci_self_hosted_runner_host_local_ready": True,
            "product_ci_self_hosted_runner_host_repo_ready": True,
            "product_ci_self_hosted_runner_host_registration_required": False,
            "product_ci_self_hosted_runner_host_github_registration_token_requested": False,
            "product_ci_self_hosted_runner_host_external_state_mutated": False,
            "product_ci_latest_github_actions_record_kst_date": "2026-06-21",
            "product_ci_workflow_dispatch_executed": False,
            "product_ci_external_state_mutated": False,
            "clean_install_missing_requirement_count": 0,
            "clean_install_missing_requirements": [],
            "product_image_preflight_blocker_codes": [],
            "clean_container_missing_requirement_count": 0,
            "clean_container_missing_requirements": [],
            "source_artifacts_fresh": True,
            "source_artifact_fresh_count": 4,
            "source_artifact_stale_count": 0,
            "source_artifact_stale_ids": [],
            "enabled_profile_count": 3,
            "failed_profile_count": 0,
            "runner_profile_validation_pass": True,
            "runner_claim_metadata_manifest_smoke": {
                "ready": True,
                "manifest_ligand_topology_valid": True,
                "manifest_ligand_topology_claim_safe": True,
                "manifest_ligand_topology_schema_version": "ligand_topology_validity_v1",
                "manifest_ligand_topology_schema_ready_row_count": 2,
                "manifest_ligand_topology_claim_safe_row_count": 2,
                "manifest_hbond_evidence_schema_version": "hbond_evidence_v1",
                "manifest_hbond_evidence_schema_ready_row_count": 2,
                "manifest_claim_safe": False,
                "manifest_blocked_reason": "runner_summary_not_claim_promoted;protein_topology_missing",
                "force_residual_summary_present": True,
                "manifest_force_residual_schema_version": "force_residual_claim_metadata_v1",
                "manifest_force_residual_policy_caps_ready": True,
                "manifest_force_residual_observed_caps_ready": True,
                "manifest_force_residual_contract_ready": True,
            },
            "force_term_claim_metadata_ready": True,
            "force_term_claim_metadata_smoke": {
                "ready": True,
                "term_result_contract_ready": True,
                "term_result_contract_term_set_ready": True,
                "term_result_contract_term_count": 3,
                "term_result_contract_terms": [
                    "directional_hbond",
                    "hydrophobic_contact",
                    "legacy_lj",
                ],
                "term_result_contract_expected_terms": [
                    "directional_hbond",
                    "hydrophobic_contact",
                    "legacy_lj",
                ],
                "forcefield_neighbor_diagnostics_ready": True,
                "forcefield_neighbor_pair_count": 6,
                "forcefield_neighbor_pairs_provided": True,
                "forcefield_neighbor_source": "provided_cell_list",
                "forcefield_claim_metadata_schema_version": "force_term_claim_metadata_v1",
                "forcefield_hbond_evidence_schema_version": "hbond_evidence_v1",
                "forcefield_hydrophobic_contact_evidence_schema_version": (
                    "hydrophobic_contact_evidence_v1"
                ),
                "forcefield_hydrophobic_contact_evidence_schema_ready": True,
                "forcefield_hydrophobic_contact_active_pair_count": 1,
                "forcefield_claim_safe_count": 3,
                "forcefield_blocked_count": 0,
                "forcefield_energy_forces_contract_ready": True,
                "forcefield_energy_forces_contract_error": "",
                "forcefield_energy_shape": [1],
                "forcefield_forces_shape": [1, 3, 3],
                "forcefield_energy_finite": True,
                "forcefield_forces_finite": True,
                "forcefield_term_count": 3,
                "forcefield_term_diagnostics_ready": True,
                "forcefield_claim_rows": [
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
                ],
                "forcefield_unsafe_base_claim_blocked": True,
                "forcefield_unsafe_base_claim_safe": False,
                "forcefield_unsafe_base_blocked_reason": "placeholder_alanine_topology",
                "forcefield_unsafe_base_claim_safe_count": 0,
                "forcefield_unsafe_base_blocked_count": 3,
                "forcefield_unsafe_base_claim_rows": [
                    {
                        "force_term_name": "directional_hbond",
                        "force_term_status": "pass",
                        "claim_safe": False,
                        "blocked_reason": "placeholder_alanine_topology",
                    },
                    {
                        "force_term_name": "hydrophobic_contact",
                        "force_term_status": "pass",
                        "claim_safe": False,
                        "blocked_reason": "placeholder_alanine_topology",
                    },
                    {
                        "force_term_name": "legacy_lj",
                        "force_term_status": "pass",
                        "claim_safe": False,
                        "blocked_reason": "placeholder_alanine_topology",
                    },
                ],
                "term_result_contract_rows": [
                    {
                        "term": "directional_hbond",
                        "ready": True,
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
                    },
                    {
                        "term": "hydrophobic_contact",
                        "ready": True,
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
                    },
                    {
                        "term": "legacy_lj",
                        "ready": True,
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
                    },
                ],
            },
            "force_term_result_contract_ready": True,
            "force_term_result_contract_term_set_ready": True,
            "force_term_result_contract_term_count": 3,
            "force_term_result_contract_terms": [
                "directional_hbond",
                "hydrophobic_contact",
                "legacy_lj",
            ],
            "force_term_result_contract_expected_terms": [
                "directional_hbond",
                "hydrophobic_contact",
                "legacy_lj",
            ],
            "forcefield_energy_forces_contract_ready": True,
            "guarded_force_term_plugin_ready": True,
            "guarded_force_term_plugin_smoke": {
                "ready": True,
                "required_guarded_terms": [
                    "pocket_wall",
                    "screened_electrostatics",
                    "topology_penalty",
                    "torsion_prior",
                    "water_displacement_proxy",
                ],
                "required_guarded_terms_present": True,
                "term": "screened_electrostatics",
                "claim_safe": True,
                "force_term_status": "pass",
                "missing_charge_blocked": True,
                "unvalidated_charge_blocked": True,
                "pocket_wall_missing_metadata_blocked": True,
                "torsion_prior_missing_metadata_blocked": True,
                "topology_penalty_missing_metadata_blocked": True,
                "topology_penalty_invalid_topology_blocked": True,
                "water_displacement_proxy_missing_metadata_blocked": True,
                "water_displacement_proxy_invalid_topology_blocked": True,
                "water_displacement_proxy_model_unvalidated_blocked": True,
                "water_displacement_proxy_weights_invalid_blocked": True,
                "water_displacement_proxy_policy_cap_exceeded_blocked": True,
                "water_displacement_proxy_claim_safe": True,
                "water_displacement_proxy_force_term_status": "pass",
                "water_displacement_proxy_finite_difference_force_error": 1e-7,
                "forcefield_claim_safe": True,
                "finite_difference_force_error": 1e-7,
                "pocket_wall_claim_safe": True,
                "pocket_wall_force_term_status": "pass",
                "pocket_wall_finite_difference_force_error": 1e-7,
                "torsion_prior_claim_safe": True,
                "torsion_prior_force_term_status": "pass",
                "torsion_prior_finite_difference_force_error": 1e-7,
                "topology_penalty_claim_safe": True,
                "topology_penalty_force_term_status": "pass",
                "topology_penalty_finite_difference_force_error": 1e-7,
                "policy_caps_ready": True,
                "observed_caps_ready": True,
                "bounded_correction_ready": True,
                "policy_cap_exceeded_blocked": True,
                "pocket_wall_policy_cap_exceeded_blocked": True,
                "torsion_prior_policy_cap_exceeded_blocked": True,
                "topology_penalty_policy_cap_exceeded_blocked": True,
                "forcefield_bounded_row_ready": True,
                "forcefield_guarded_rows_ready": True,
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
                ],
                "forcefield_guarded_claim_row": {
                    "force_term_name": "screened_electrostatics",
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
                ],
                "abs_energy_within_cap": True,
                "force_norm_within_cap": True,
                "active_pair_count_within_cap": True,
            },
            "onsps_backmap_evidence_schema_ready": True,
            "onsps_backmap_evidence_schema_smoke": {
                "ready": True,
                "schema_version": "onsps_backmap_evidence_v1",
                "valid_claim_safe": True,
                "valid_backmap_status": "ok",
                "valid_mapped_site_count": 1,
                "empty_blocked_reason": "invalid_two_bead_geometry",
                "no_sites_blocked_reason": "no_onsps_sites",
                "hbond_onsps_schema_version": "onsps_backmap_evidence_v1",
                "product_runner_direct_engine_import_ready": True,
                "product_runner_import_source": "betelgeuze_engine.backmapping.onsps",
                "product_runner_legacy_core_import_absent": True,
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
            "core_forcefield_bridge_ready": True,
            "core_forcefield_bridge_smoke": {
                "ready": True,
                "result_claim_safe": True,
                "force_term_claim_metadata_ready": True,
                "force_term_plugins": ["legacy_lj"],
                "unsafe_base_claim_blocked": True,
                "unsafe_base_claim_safe": False,
                "unsafe_base_blocked_reason": "placeholder_alanine_topology",
                "unsafe_base_claim_safe_count": 0,
                "unsafe_base_blocked_count": 1,
                "unsafe_base_claim_rows": [
                    {
                        "force_term_name": "legacy_lj",
                        "force_term_status": "pass",
                        "claim_safe": False,
                        "blocked_reason": "placeholder_alanine_topology",
                    },
                ],
                "energy_shape": [1],
                "forces_shape": [1, 2, 3],
                "neighbor_diagnostics_ready": True,
                "neighbor_pair_count": 2,
                "neighbor_pairs_provided": True,
                "neighbor_source": "provided_cell_list",
                "bridge_execution_scope": "metadata_contract_only_not_runtime_gpu_claim",
            },
            "core_compatibility_layer_ready": True,
            "core_compatibility_layer_smoke": {
                "ready": True,
                "contract_scope": "legacy_core_import_paths_are_compatibility_layer_not_runtime_gpu_claim",
                "row_count": 7,
                "rows": [
                    {
                        "contract": "onsps_backmap_shim",
                        "ready": True,
                        "legacy_module": "core.onsps_backmap",
                        "canonical_module": "betelgeuze_engine.backmapping.onsps",
                        "bridge_type": "import_identity",
                        "error": "",
                    },
                    {
                        "contract": "topology_protein_bridge",
                        "ready": True,
                        "legacy_module": "core.topology",
                        "canonical_module": "betelgeuze_engine.topology.protein",
                        "bridge_type": "engine_dataclass_bridge",
                        "topology_fidelity": "sequence_mapped",
                        "protein_topology_type": "ProteinTopology",
                        "hbond_role_count": 2,
                        "error": "",
                    },
                    {
                        "contract": "adress_production_blocked_log",
                        "ready": True,
                        "legacy_module": "core.topology",
                        "canonical_module": "betelgeuze_engine.topology.protein",
                        "bridge_type": "fail_closed_adress_guard",
                        "adress_log_blocked": True,
                        "adress_log_active_claim_absent": True,
                        "adress_neighbor_blocked": True,
                        "adress_neighbor_error": "AdResS neighbor path is disabled in production.",
                        "error": "",
                    },
                    {
                        "contract": "forcefield_product_bridge",
                        "ready": True,
                        "legacy_module": "core.forcefield",
                        "canonical_module": "betelgeuze_engine.physics",
                        "bridge_type": "energy_forces_claim_metadata_bridge",
                        "result_claim_safe": True,
                        "force_term_claim_metadata_ready": True,
                        "force_term_plugins": ["legacy_lj"],
                        "unsafe_base_claim_blocked": True,
                        "unsafe_base_claim_safe": False,
                        "unsafe_base_blocked_reason": "placeholder_alanine_topology",
                        "unsafe_base_claim_safe_count": 0,
                        "unsafe_base_blocked_count": 1,
                        "unsafe_base_claim_rows": [
                            {
                                "force_term_name": "legacy_lj",
                                "force_term_status": "pass",
                                "claim_safe": False,
                                "blocked_reason": "placeholder_alanine_topology",
                            },
                        ],
                        "neighbor_diagnostics_ready": True,
                        "neighbor_pair_count": 2,
                        "neighbor_pairs_provided": True,
                        "neighbor_source": "provided_cell_list",
                        "error": "",
                    },
                    {
                        "contract": "score_residual_shim",
                        "ready": True,
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
                        "ready": True,
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
                        "ready": True,
                        "legacy_module": "core.mm_gbsa",
                        "canonical_module": "betelgeuze_engine.physics.mm_gbsa",
                        "bridge_type": "import_identity",
                        "checked_symbols": ["mm_gbsa_binding_energy", "compute_full_refine_stack"],
                        "missing_symbols": [],
                        "identity_mismatches": [],
                        "error": "",
                    },
                ],
            },
            "job_store_lazy_factory_ready": True,
            "job_store_lazy_factory_smoke": {"ready": True},
            "allowlisted_runner_shim_contract_ready": True,
            "allowlisted_runner_shim_contract": {
                "ready": True,
                "runner_count": 3,
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
                ],
            },
            "product_runner_engine_imports_ready": True,
            "product_runner_engine_imports_smoke": {
                "ready": True,
                "runner": "tools/product/run_ligand_backmapping_scoring.py",
                "row_count": 6,
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
                ],
            },
            "product_runner_no_core_imports_ready": True,
            "product_runner_no_core_imports_smoke": _runner_no_core_imports_smoke(),
            "topk_delivery_engine_owned_ready": True,
            "topk_delivery_engine_owned_smoke": _topk_delivery_engine_owned_smoke(),
            "backmapping_scoring_engine_owned_ready": True,
            "backmapping_scoring_engine_owned_smoke": _backmapping_scoring_engine_owned_smoke(),
            "htvs_pipeline_engine_owned_ready": True,
            "htvs_pipeline_engine_owned_smoke": _htvs_pipeline_engine_owned_smoke(),
            "product_runner_engine_owned_ready": True,
            "product_runner_engine_owned_smoke": _product_runner_engine_owned_smoke(),
            "blocked_claim_correctly_blocked": True,
        },
        "pose_ranking_hbond_benchmark": {
            "benchmark_ready": True,
            "top1_pose_id": "amide_near_hbond_pose",
            "top1_expected_pose_id": "amide_near_hbond_pose",
            "hbond_recovery_pose_count": 1,
            "hbond_recovery_pose_ids": ["amide_near_hbond_pose"],
            "hbond_recovery_confidence_min": 0.9,
            "hbond_recovery_benchmark_schema_version": "hbond_recovery_benchmark_v1",
            "hbond_recovery_benchmark_ready": True,
            "hbond_recovery_benchmark_status": "hbond_recovery_benchmark_ready",
            "hbond_recovery_benchmark_fixture_count": 3,
            "hbond_recovery_benchmark_contract_pass_count": 3,
            "hbond_recovery_benchmark": _hbond_recovery_benchmark_packet(),
            "overanchored_decoys_blocked": True,
            "delta_backmap_yellow_band_abstention_ready": True,
            "unsatisfied_donor_acceptor_detected": True,
            "unsatisfied_donor_acceptor_pose_count": 3,
            "fixture_count": 6,
            "required_pose_roles": [
                "delta_backmap_yellow_band_pose",
                "far_decoy_pose",
                "hbond_recovery_pose",
                "invalid_ligand_pose",
                "overanchored_decoy_pose",
                "unsatisfied_donor_pose",
            ],
            "observed_pose_roles": [
                "delta_backmap_yellow_band_pose",
                "far_decoy_pose",
                "hbond_recovery_pose",
                "invalid_ligand_pose",
                "overanchored_decoy_pose",
                "unsatisfied_donor_pose",
            ],
            "ranking_order": [
                "amide_near_hbond_pose",
                "ethanol_near_hbond_pose",
                "amide_delta_backmap_yellow_band_pose",
                "amide_far_decoy_pose",
                "amide_overanchored_decoy_pose",
                "invalid_ligand_pose",
            ],
            "row_contracts_ready": True,
            "row_contract_pass_count": 6,
            "rows": [
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
                    "hbond_schema_ready": True,
                    "hbond_threshold_schema_ready": True,
                    "hbond_pair_schema_ready": True,
                    "hbond_geometry_flags_ready": True,
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
                    "hbond_schema_ready": True,
                    "hbond_threshold_schema_ready": True,
                    "hbond_pair_schema_ready": True,
                    "hbond_geometry_flags_ready": True,
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
                    "hbond_schema_ready": True,
                    "hbond_threshold_schema_ready": True,
                    "hbond_pair_schema_ready": True,
                    "hbond_geometry_flags_ready": True,
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
                    "hbond_schema_ready": True,
                    "hbond_threshold_schema_ready": True,
                    "hbond_pair_schema_ready": True,
                    "hbond_geometry_flags_ready": True,
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
                    "hbond_schema_ready": True,
                    "hbond_threshold_schema_ready": True,
                    "hbond_pair_schema_ready": True,
                    "hbond_geometry_flags_ready": True,
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
                    "hbond_schema_ready": True,
                    "hbond_threshold_schema_ready": True,
                    "hbond_pair_schema_ready": True,
                    "hbond_geometry_flags_ready": True,
                    "benchmark_contract_checks": {"claim_safe_matches": True},
                    "benchmark_contract_pass": True,
                },
            ],
        },
        "confidence_calibration_report": {
            "schema_version": "confidence_calibration_v1",
            "status": "confidence_calibration_report_ready",
            "ready": True,
            "confidence_calibration_ready": True,
            "blocked_reasons": [],
            "row_count": 6,
            "source_row_count": 6,
            "positive_count": 1,
            "negative_count": 5,
            "bin_count": 5,
            "bins": [
                {
                    "bin_index": 0,
                    "confidence_low": 0.0,
                    "confidence_high": 0.2,
                    "row_count": 4,
                    "mean_confidence": 0.0,
                    "accuracy": 0.0,
                    "calibration_gap": 0.0,
                },
                {
                    "bin_index": 1,
                    "confidence_low": 0.2,
                    "confidence_high": 0.4,
                    "row_count": 0,
                    "mean_confidence": 0.0,
                    "accuracy": 0.0,
                    "calibration_gap": 0.0,
                },
                {
                    "bin_index": 2,
                    "confidence_low": 0.4,
                    "confidence_high": 0.6,
                    "row_count": 1,
                    "mean_confidence": 0.4,
                    "accuracy": 0.0,
                    "calibration_gap": 0.4,
                },
                {
                    "bin_index": 3,
                    "confidence_low": 0.6,
                    "confidence_high": 0.8,
                    "row_count": 0,
                    "mean_confidence": 0.0,
                    "accuracy": 0.0,
                    "calibration_gap": 0.0,
                },
                {
                    "bin_index": 4,
                    "confidence_low": 0.8,
                    "confidence_high": 1.0,
                    "row_count": 1,
                    "mean_confidence": 1.0,
                    "accuracy": 1.0,
                    "calibration_gap": 0.0,
                },
            ],
            "expected_calibration_error": 0.06666666666666667,
            "max_expected_calibration_error": 0.2,
            "brier_score": 0.02666666666666667,
            "max_brier_score": 0.2,
            "mean_confidence": 0.2333333333333333,
            "mean_accuracy": 0.16666666666666666,
            "rows": [
                {
                    "pose_id": "amide_near_hbond_pose",
                    "benchmark_role": "hbond_recovery_pose",
                    "confidence": 1.0,
                    "expected_claim_safe": True,
                    "outcome": 1.0,
                    "prediction_error": 0.0,
                },
                {
                    "pose_id": "amide_delta_backmap_yellow_band_pose",
                    "benchmark_role": "delta_backmap_yellow_band_pose",
                    "confidence": 0.4,
                    "expected_claim_safe": False,
                    "outcome": 0.0,
                    "prediction_error": 0.4,
                },
                {
                    "pose_id": "ethanol_near_hbond_pose",
                    "benchmark_role": "unsatisfied_donor_pose",
                    "confidence": 0.0,
                    "expected_claim_safe": False,
                    "outcome": 0.0,
                    "prediction_error": 0.0,
                },
                {
                    "pose_id": "amide_far_decoy_pose",
                    "benchmark_role": "far_decoy_pose",
                    "confidence": 0.0,
                    "expected_claim_safe": False,
                    "outcome": 0.0,
                    "prediction_error": 0.0,
                },
                {
                    "pose_id": "amide_overanchored_decoy_pose",
                    "benchmark_role": "overanchored_decoy_pose",
                    "confidence": 0.0,
                    "expected_claim_safe": False,
                    "outcome": 0.0,
                    "prediction_error": 0.0,
                },
                {
                    "pose_id": "invalid_ligand_pose",
                    "benchmark_role": "invalid_ligand_pose",
                    "confidence": 0.0,
                    "expected_claim_safe": False,
                    "outcome": 0.0,
                    "prediction_error": 0.0,
                },
            ],
            "claim_boundary": "Internal synthetic pose/H-bond benchmark confidence calibration only.",
        },
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
                "bounded_correction_policy_ready": True,
                "observed_caps_ready": True,
                "contract_ready": True,
                "confidence_abstention_ready": True,
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
            "force_term_physics_validation_ready": True,
            "force_term_physics_validation_claim_safe_ready": True,
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
                "force_residual_bounded_policy_ready": True,
                "force_residual_observed_caps_ready": True,
                "force_residual_contract_ready": True,
                "force_residual_confidence_abstention_ready": True,
                "force_residual_top_k_policy_ready": True,
            },
            "physics": {
                "finite_difference_force_error_pass": True,
                "energy_drift_pass": True,
                "rotation_equivariance_pass": True,
                "neighbor_list_parity_pass": True,
                "topology_invalid_rate_pass": True,
                "backmapping_failure_rate_pass": True,
                "force_term_physics_validation_ready": True,
                "force_term_physics_validation_claim_safe_ready": True,
            },
            "product": {
                "runner_claim_metadata_signed": True,
                "signed_manifest_verification_pass": True,
                "bundle_validation_pass": True,
                "product_claim_ready": True,
                "release_claim_ready": True,
                "release_claim_blocked_reason": "",
                "product_ci_runtime_gate_present": True,
                "product_ci_runtime_gate_ready": True,
                "product_ci_runtime_gate_status": "product_ci_runtime_gate_ready",
                "product_ci_remote_green": True,
                "product_ci_github_actions_started": True,
                "product_ci_external_blocker": False,
                "product_ci_blocker_code": "",
                "product_ci_billing_free_self_hosted_path_recommended": False,
                "product_ci_billing_free_self_hosted_api_worker_command": "",
                "product_ci_billing_free_self_hosted_rocm_runtime_command": "",
                "product_ci_hosted_spending_limit_increase_required": False,
                "product_ci_self_hosted_runner_inventory_present": True,
                "product_ci_self_hosted_runner_total_count": 2,
                "product_ci_self_hosted_linux_runner_online": True,
                "product_ci_self_hosted_linux_runner_count": 2,
                "product_ci_self_hosted_rocm_runner_online": True,
                "product_ci_self_hosted_rocm_runner_count": 1,
                "product_ci_self_hosted_runner_inventory_external_state_mutated": False,
                "product_ci_self_hosted_runner_host_preflight_present": True,
                "product_ci_self_hosted_runner_host_preflight_status": "github_self_hosted_runner_host_preflight_ready",
                "product_ci_self_hosted_runner_host_local_ready": True,
                "product_ci_self_hosted_runner_host_repo_ready": True,
                "product_ci_self_hosted_runner_host_registration_required": False,
                "product_ci_self_hosted_runner_host_github_registration_token_requested": False,
                "product_ci_self_hosted_runner_host_external_state_mutated": False,
                "product_ci_latest_github_actions_record_kst_date": "2026-06-21",
                "clean_install_missing_requirement_count": 0,
                "clean_install_missing_requirements": [],
                "product_image_preflight_blocker_codes": [],
                "clean_container_missing_requirement_count": 0,
                "clean_container_missing_requirements": [],
                "source_artifacts_fresh": True,
                "source_artifact_fresh_count": 4,
                "source_artifact_stale_count": 0,
                "source_artifact_stale_ids": [],
                "enabled_profile_count": 3,
                "failed_profile_count": 0,
                "runner_profile_validation_pass": True,
                "force_term_claim_metadata_ready": True,
                "force_term_result_contract_ready": True,
                "force_term_result_contract_term_set_ready": True,
                "force_term_result_contract_term_count": 3,
                "force_term_result_contract_terms": [
                    "directional_hbond",
                    "hydrophobic_contact",
                    "legacy_lj",
                ],
                "force_term_result_contract_expected_terms": [
                    "directional_hbond",
                    "hydrophobic_contact",
                    "legacy_lj",
                ],
                "forcefield_energy_forces_contract_ready": True,
                "guarded_force_term_plugin_ready": True,
                "onsps_backmap_evidence_schema_ready": True,
                "engine_topology_factory_facade_ready": True,
                "core_forcefield_bridge_ready": True,
                "core_compatibility_layer_ready": True,
                "job_store_lazy_factory_ready": True,
                "allowlisted_runner_shim_contract_ready": True,
                "product_runner_engine_imports_ready": True,
                "product_runner_no_core_imports_ready": True,
                "topk_delivery_engine_owned_ready": True,
                "backmapping_scoring_engine_owned_ready": True,
                "htvs_pipeline_engine_owned_ready": True,
                "product_runner_engine_owned_ready": True,
                "blocked_claim_correctly_blocked": True,
            },
            "chemistry": {
                "hbond_evidence_schema_ready": True,
                "hbond_evidence_schema_ready_count": chemistry_kpi["hbond_evidence_schema_ready_count"],
                "ligand_topology_validity_schema_ready": True,
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
                "hbond_recovery_pose_count": 1,
                "hbond_recovery_pose_ids": ["amide_near_hbond_pose"],
                "hbond_recovery_confidence_min": 0.9,
                "hbond_recovery_benchmark_ready": True,
                "hbond_recovery_benchmark_schema_version": "hbond_recovery_benchmark_v1",
                "hbond_recovery_benchmark_fixture_count": 3,
                "hbond_recovery_benchmark_contract_pass_count": 3,
                "unsatisfied_donor_acceptor_detection": True,
                "unsatisfied_donor_acceptor_fixture_count": (
                    chemistry_kpi["unsatisfied_donor_acceptor_fixture_count"]
                ),
                "unsatisfied_donor_count": chemistry_kpi["unsatisfied_donor_count"],
                "unsatisfied_acceptor_count": chemistry_kpi["unsatisfied_acceptor_count"],
                "unsatisfied_donor_acceptor_pose_count": 3,
                "overanchored_decoy_rejection": True,
                "chirality_preservation_fixture_count": (
                    chemistry_kpi["chirality_preservation_fixture_count"]
                ),
                "unassigned_chirality_blocked_fixture_count": (
                    chemistry_kpi["unassigned_chirality_blocked_fixture_count"]
                ),
                "chirality_preservation_ready": True,
                "ring_validity_fixture_count": chemistry_kpi["ring_validity_fixture_count"],
                "ring_validity_ready": True,
                "tautomer_validity_fixture_count": chemistry_kpi["tautomer_validity_fixture_count"],
                "tautomer_validity_ready": True,
                "protonation_validity_fixture_count": chemistry_kpi["protonation_validity_fixture_count"],
                "protonation_validity_ready": True,
                "confidence_calibration_report_ready": True,
                "confidence_calibration_status": "confidence_calibration_report_ready",
                "confidence_calibration_row_count": 6,
                "confidence_calibration_positive_count": 1,
                "confidence_calibration_negative_count": 5,
                "confidence_calibration_expected_calibration_error": 0.06666666666666667,
                "confidence_calibration_brier_score": 0.02666666666666667,
                "confidence_calibration_bin_count": 5,
            }
        },
    }
    rocm_packet = {
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
    image_packet = {
        "summary": {
            "status": "product_image_smoke_preflight_ready"
            if clean_ready
            else "blocked_product_image_smoke_preflight",
            "preflight_ready": True,
            "clean_container_smoke_ready": clean_ready,
            "receipt_present": clean_ready,
            "receipt_status": "product_image_smoke_ready" if clean_ready else "blocked_product_image_smoke",
            "receipt_mode": "rocm-runtime" if clean_ready else "build",
            "receipt_simulate_missing_profile_http": 422 if clean_ready else 0,
            "container_runtime_receipt_ready": clean_ready,
            "container_runtime_proof_schema_version": "rocm_container_runtime_proof_v1"
            if clean_ready
            else "",
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
            "backmapping_ligand_topology_schema_version": "ligand_topology_validity_v1"
            if clean_ready
            else "",
            "backmapping_ligand_topology_schema_ready_row_count": 2 if clean_ready else 0,
            "backmapping_ligand_topology_valid": clean_ready,
            "backmapping_ligand_topology_claim_safe": clean_ready,
            "backmapping_ligand_topology_claim_safe_row_count": 2 if clean_ready else 0,
            "backmapping_ligand_topology_invalid_row_count": 0,
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
        "blockers": [] if clean_ready else [{"code": "docker_cli_missing"}],
    }
    product_ci_packet = {
        "summary": {
            "status": "product_ci_runtime_gate_ready",
            "runtime_gate_ready": True,
            "remote_product_ci_green": True,
            "github_actions_started": True,
            "external_blocker": False,
            "blocker_code": "",
            "billing_free_self_hosted_path_recommended": False,
            "billing_free_self_hosted_api_worker_command": "",
            "billing_free_self_hosted_rocm_runtime_command": "",
            "hosted_spending_limit_increase_required": False,
            "self_hosted_runner_inventory_present": True,
            "self_hosted_runner_total_count": 2,
            "self_hosted_linux_runner_online": True,
            "self_hosted_linux_runner_count": 2,
            "self_hosted_rocm_runner_online": True,
            "self_hosted_rocm_runner_count": 1,
            "self_hosted_runner_inventory_external_state_mutated": False,
            "self_hosted_runner_host_preflight_present": True,
            "self_hosted_runner_host_preflight_status": "github_self_hosted_runner_host_preflight_ready",
            "self_hosted_runner_host_local_ready": True,
            "self_hosted_runner_host_repo_ready": True,
            "self_hosted_runner_host_registration_required": False,
            "self_hosted_runner_host_github_registration_token_requested": False,
            "self_hosted_runner_host_external_state_mutated": False,
            "latest_github_actions_record_kst_date": "2026-06-21",
            "workflow_dispatch_executed": False,
            "external_state_mutated": False,
            "claim_boundary": "test fixture product CI runtime gate",
        },
        "blockers": [],
    }
    runtime_plot = _write(
        root / "bundle_runtime_scaling.svg",
        (
            "<svg xmlns=\"http://www.w3.org/2000/svg\">"
            "<text>Capped neighbor pairs</text><text>Pair-count scaling advisory</text>"
            "</svg>\n"
        ),
    )
    kpi_packet["runtime_kpi"]["neighbor_cap_scaling"]["plot_path"] = str(runtime_plot)
    kpi_packet["runtime_kpi"]["neighbor_cap_scaling"]["plot_sha256"] = _sha256(runtime_plot)
    kpi_packet["runtime_kpi"]["neighbor_cap_scaling"]["plot_size_bytes"] = runtime_plot.stat().st_size
    kpi_packet["pm_kpi_summary"]["runtime"]["runtime_neighbor_cap_scaling_plot_path"] = str(runtime_plot)
    kpi_packet["pm_kpi_summary"]["runtime"]["runtime_neighbor_cap_scaling_plot_sha256"] = _sha256(runtime_plot)
    specs = [
        {
            "artifact_id": "kpi_json",
            "artifact_path": str(_write(root / "bundle_kpi.json", json.dumps(kpi_packet))),
            "role": "local_pc_runtime_report",
            "required": True,
        },
        {
            "artifact_id": "kpi_md",
            "artifact_path": str(_write(root / "bundle_kpi.md")),
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
            "artifact_path": str(_write(root / "bundle_rocm.json", json.dumps(rocm_packet))),
            "role": "gpu_rocm_hip_runtime_gate",
            "required": True,
        },
        {
            "artifact_id": "image_preflight",
            "artifact_path": str(_write(root / "bundle_preflight.json", json.dumps(image_packet))),
            "role": "clean_container_smoke_gate",
            "required": True,
        },
        {
            "artifact_id": "doc",
            "artifact_path": str(_write(root / "bundle_next.md")),
            "role": "engineering_plan",
            "required": True,
        },
    ]
    payload = bundle_mod.build_payload(
        kpi_packet=kpi_packet,
        rocm_manifest_packet=rocm_packet,
        product_image_preflight_packet=image_packet,
        product_ci_runtime_gate_packet=product_ci_packet,
        artifact_specs=specs,
        out_tar=str(out_tar),
    )
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def test_build_ai_md_engine_kpi_report_contract(tmp_path: Path) -> None:
    rocm = tmp_path / "rocm.json"
    bundle_json = _write_product_evidence_bundle(tmp_path / "bundle.json")
    product_ci = tmp_path / "product_ci_runtime_gate.json"
    product_ci.write_text(
        json.dumps(
            {
                "summary": {
                    "status": "product_ci_runtime_gate_ready",
                    "runtime_gate_ready": True,
                    "remote_product_ci_green": True,
                    "github_actions_started": True,
                    "external_blocker": False,
                    "blocker_code": "",
                    "billing_free_self_hosted_path_recommended": False,
                    "billing_free_self_hosted_api_worker_command": "",
                    "billing_free_self_hosted_rocm_runtime_command": "",
                    "hosted_spending_limit_increase_required": False,
                    "self_hosted_runner_inventory_present": True,
                    "self_hosted_runner_total_count": 2,
                    "self_hosted_linux_runner_online": True,
                    "self_hosted_linux_runner_count": 2,
                    "self_hosted_rocm_runner_online": True,
                    "self_hosted_rocm_runner_count": 1,
                    "self_hosted_runner_inventory_external_state_mutated": False,
                    "self_hosted_runner_host_preflight_present": True,
                    "self_hosted_runner_host_preflight_status": "github_self_hosted_runner_host_preflight_ready",
                    "self_hosted_runner_host_local_ready": True,
                    "self_hosted_runner_host_repo_ready": True,
                    "self_hosted_runner_host_registration_required": False,
                    "self_hosted_runner_host_github_registration_token_requested": False,
                    "self_hosted_runner_host_external_state_mutated": False,
                    "latest_github_actions_record_kst_date": "2026-06-21",
                    "workflow_dispatch_executed": False,
                    "external_state_mutated": False,
                    "claim_boundary": "test fixture product CI runtime gate",
                }
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    _write_rocm_manifest(rocm, ready=True)
    report = build_report(
        profiles_dir="config/api_validated_runner_profiles",
        score_only_rows=8,
        onsps_rows=7,
        residual_rows=3,
        rocm_manifest_path=str(rocm),
        product_evidence_bundle_json_path=str(bundle_json),
        product_ci_runtime_gate_json_path=str(product_ci),
    )

    assert report["packet_type"] == "ai_md_engine_kpi_report"
    assert report["status"] == "ai_md_engine_kpi_report_ready"
    assert report["pm_kpi_summary"]["summary_ready"] is True
    assert report["report_ready"] == report["pm_kpi_summary"]["summary_ready"]
    assert report["pm_kpi_summary"]["failed_gate_ids"] == []
    assert report["pm_kpi_summary"]["product"]["clean_install_success"] is True
    assert report["product_kpi"]["runner_profile_validation_status"] == "pass"
    assert report["product_kpi"]["clean_install_success"] is True
    assert report["product_kpi"]["product_ci_billing_free_self_hosted_path_recommended"] is False
    assert report["pm_kpi_summary"]["product"]["product_ci_billing_free_self_hosted_path_recommended"] is False
    assert report["product_kpi"]["product_ci_hosted_spending_limit_increase_required"] is False
    assert report["pm_kpi_summary"]["product"]["product_ci_hosted_spending_limit_increase_required"] is False
    assert report["product_kpi"]["product_ci_self_hosted_runner_inventory_present"] is True
    assert report["pm_kpi_summary"]["product"]["product_ci_self_hosted_runner_inventory_present"] is True
    assert report["product_kpi"]["product_ci_self_hosted_runner_total_count"] == 2
    assert report["pm_kpi_summary"]["product"]["product_ci_self_hosted_runner_total_count"] == 2
    assert report["product_kpi"]["product_ci_self_hosted_linux_runner_online"] is True
    assert report["pm_kpi_summary"]["product"]["product_ci_self_hosted_linux_runner_online"] is True
    assert report["product_kpi"]["product_ci_self_hosted_rocm_runner_online"] is True
    assert report["pm_kpi_summary"]["product"]["product_ci_self_hosted_rocm_runner_online"] is True
    assert report["product_kpi"]["clean_container_smoke_ready"] is True
    assert report["product_kpi"]["product_runner_smoke_ready"] is True
    assert report["product_kpi"]["product_image_receipt_mode"] == "rocm-runtime"
    assert report["product_kpi"]["clean_install_missing_requirement_count"] == 0
    assert report["product_kpi"]["clean_install_missing_requirements"] == []
    assert report["product_kpi"]["product_image_preflight_blocker_codes"] == []
    assert report["product_kpi"]["clean_container_missing_requirement_count"] == 0
    assert report["product_kpi"]["clean_container_missing_requirements"] == []
    assert report["pm_kpi_summary"]["product"]["clean_install_missing_requirement_count"] == 0
    assert report["pm_kpi_summary"]["product"]["clean_install_missing_requirements"] == []
    assert report["pm_kpi_summary"]["product"]["clean_container_missing_requirement_count"] == 0
    assert report["pm_kpi_summary"]["product"]["clean_container_missing_requirements"] == []
    assert report["product_kpi"]["signed_manifest_verification_pass"] is True
    assert report["product_kpi"]["runner_claim_metadata_signed"] is True
    assert report["pm_kpi_summary"]["product"]["runner_claim_metadata_signed"] is True
    runner_manifest_smoke = report["product_kpi"]["runner_claim_metadata_manifest_smoke"]
    assert runner_manifest_smoke["signature_verified"] is True
    assert runner_manifest_smoke["result_claim_metadata_present"] is True
    assert runner_manifest_smoke["hbond_evidence_summary_present"] is True
    assert runner_manifest_smoke["force_residual_summary_present"] is True
    assert runner_manifest_smoke["manifest_claim_safe"] is False
    assert runner_manifest_smoke["manifest_blocked_reason"] == (
        "runner_summary_not_claim_promoted;protein_topology_missing"
    )
    assert runner_manifest_smoke["manifest_ligand_topology_valid"] is True
    assert runner_manifest_smoke["manifest_ligand_topology_claim_safe"] is True
    assert runner_manifest_smoke["manifest_ligand_topology_schema_version"] == "ligand_topology_validity_v1"
    assert runner_manifest_smoke["manifest_ligand_topology_schema_ready_row_count"] == 2
    assert runner_manifest_smoke["manifest_ligand_topology_claim_safe_row_count"] == 2
    assert runner_manifest_smoke["manifest_hbond_evidence_status"] == "review"
    assert runner_manifest_smoke["manifest_hbond_evidence_schema_version"] == "hbond_evidence_v1"
    assert runner_manifest_smoke["manifest_hbond_evidence_schema_ready_row_count"] == 2
    assert runner_manifest_smoke["manifest_force_residual_schema_version"] == "force_residual_claim_metadata_v1"
    assert runner_manifest_smoke["manifest_force_residual_policy_caps_ready"] is True
    assert runner_manifest_smoke["manifest_force_residual_observed_caps_ready"] is True
    assert runner_manifest_smoke["manifest_force_residual_contract_ready"] is True
    assert report["product_kpi"]["bundle_validation_pass"] is True
    assert report["product_kpi"]["bundle_validation_error_count"] == 0
    assert report["product_kpi"]["source_artifacts_fresh"] is True
    assert report["product_kpi"]["source_artifact_stale_count"] == 0
    assert report["product_kpi"]["source_artifact_stale_ids"] == []
    assert report["pm_kpi_summary"]["product"]["source_artifacts_fresh"] is True
    assert report["pm_kpi_summary"]["product"]["force_term_plugin_registry_ready"] is True
    assert report["product_kpi"]["force_term_plugin_registry_ready"] is True
    assert report["product_kpi"]["force_term_plugins"] == [
        "directional_hbond",
        "hydrophobic_contact",
        "legacy_lj",
    ]
    assert report["product_kpi"]["force_term_claim_metadata_ready"] is True
    assert report["pm_kpi_summary"]["product"]["force_term_claim_metadata_ready"] is True
    assert report["product_kpi"]["force_term_result_contract_ready"] is True
    assert report["pm_kpi_summary"]["product"]["force_term_result_contract_ready"] is True
    assert report["product_kpi"]["force_term_result_contract_term_set_ready"] is True
    assert report["pm_kpi_summary"]["product"]["force_term_result_contract_term_set_ready"] is True
    assert report["product_kpi"]["force_term_result_contract_term_count"] == 3
    assert report["pm_kpi_summary"]["product"]["force_term_result_contract_term_count"] == 3
    assert report["product_kpi"]["force_term_result_contract_terms"] == [
        "directional_hbond",
        "hydrophobic_contact",
        "legacy_lj",
    ]
    assert report["pm_kpi_summary"]["product"]["force_term_result_contract_terms"] == [
        "directional_hbond",
        "hydrophobic_contact",
        "legacy_lj",
    ]
    assert report["product_kpi"]["forcefield_energy_forces_contract_ready"] is True
    assert report["pm_kpi_summary"]["product"]["forcefield_energy_forces_contract_ready"] is True
    assert report["product_kpi"]["guarded_force_term_plugin_ready"] is True
    assert report["pm_kpi_summary"]["product"]["guarded_force_term_plugin_ready"] is True
    assert report["product_kpi"]["engine_topology_factory_facade_ready"] is True
    assert report["pm_kpi_summary"]["product"]["engine_topology_factory_facade_ready"] is True
    topology_factory_smoke = report["product_kpi"]["engine_topology_factory_facade_smoke"]
    assert topology_factory_smoke["facade"] == "betelgeuze_engine.topology.TopologyFactoryFacade"
    assert topology_factory_smoke["valid_claim_safe"] is True
    assert topology_factory_smoke["valid_protein_residue_count"] == 3
    assert topology_factory_smoke["valid_protein_topology_valid"] is True
    assert topology_factory_smoke["valid_pocket_residue_count"] == 1
    assert topology_factory_smoke["valid_pocket_residue_indices_valid"] is True
    assert topology_factory_smoke["valid_ligand_topology_schema_version"] == "ligand_topology_validity_v1"
    assert topology_factory_smoke["placeholder_protein_residue_count"] == 3
    assert topology_factory_smoke["placeholder_protein_topology_valid"] is True
    assert topology_factory_smoke["placeholder_blocked_reason"] == "placeholder_alanine_topology"
    assert topology_factory_smoke["empty_protein_residue_count"] == 0
    assert topology_factory_smoke["empty_protein_topology_valid"] is False
    assert topology_factory_smoke["empty_protein_blocked_reason"] == "empty_protein_topology"
    assert topology_factory_smoke["invalid_ligand_blocked_reason"] == "invalid_smiles"
    assert topology_factory_smoke["invalid_pocket_blocked_reason"] == "invalid_pocket_residue_indices"
    assert topology_factory_smoke["invalid_pocket_residue_indices_valid"] is False
    assert report["product_kpi"]["onsps_backmap_evidence_schema_ready"] is True
    assert report["pm_kpi_summary"]["product"]["onsps_backmap_evidence_schema_ready"] is True
    onsps_schema_smoke = report["product_kpi"]["onsps_backmap_evidence_schema_smoke"]
    assert onsps_schema_smoke["schema_version"] == "onsps_backmap_evidence_v1"
    assert onsps_schema_smoke["valid_claim_safe"] is True
    assert onsps_schema_smoke["valid_backmap_status"] == "ok"
    assert onsps_schema_smoke["valid_mapped_site_count"] >= 1
    assert onsps_schema_smoke["empty_blocked_reason"] == "invalid_two_bead_geometry"
    assert onsps_schema_smoke["no_sites_blocked_reason"] == "no_onsps_sites"
    assert onsps_schema_smoke["hbond_onsps_schema_version"] == "onsps_backmap_evidence_v1"
    assert onsps_schema_smoke["product_runner_direct_engine_import_ready"] is True
    assert onsps_schema_smoke["product_runner_import_source"] == "betelgeuze_engine.backmapping.onsps"
    assert onsps_schema_smoke["product_runner_legacy_core_import_absent"] is True
    guarded_plugin = report["product_kpi"]["guarded_force_term_plugin_smoke"]
    assert guarded_plugin["ready"] is True
    assert guarded_plugin["default_registry_names"] == [
        "directional_hbond",
        "hydrophobic_contact",
        "legacy_lj",
    ]
    assert guarded_plugin["guarded_registry_names"] == [
        "directional_hbond",
        "hydrophobic_contact",
        "legacy_lj",
        "pocket_wall",
        "screened_electrostatics",
        "topology_penalty",
        "torsion_prior",
        "water_displacement_proxy",
    ]
    assert guarded_plugin["required_guarded_terms"] == [
        "pocket_wall",
        "screened_electrostatics",
        "topology_penalty",
        "torsion_prior",
        "water_displacement_proxy",
    ]
    assert guarded_plugin["required_guarded_terms_present"] is True
    assert guarded_plugin["term"] == "screened_electrostatics"
    assert guarded_plugin["claim_safe"] is True
    assert guarded_plugin["force_term_status"] == "pass"
    assert guarded_plugin["missing_charge_blocked"] is True
    assert guarded_plugin["unvalidated_charge_blocked"] is True
    assert guarded_plugin["pocket_wall_missing_metadata_blocked"] is True
    assert guarded_plugin["torsion_prior_missing_metadata_blocked"] is True
    assert guarded_plugin["topology_penalty_missing_metadata_blocked"] is True
    assert guarded_plugin["topology_penalty_invalid_topology_blocked"] is True
    assert guarded_plugin["forcefield_claim_safe"] is True
    assert guarded_plugin["finite_difference_force_error"] < 1e-5
    assert guarded_plugin["pocket_wall_claim_safe"] is True
    assert guarded_plugin["pocket_wall_force_term_status"] == "pass"
    assert guarded_plugin["pocket_wall_finite_difference_force_error"] < 1e-5
    assert guarded_plugin["torsion_prior_claim_safe"] is True
    assert guarded_plugin["torsion_prior_force_term_status"] == "pass"
    assert guarded_plugin["torsion_prior_finite_difference_force_error"] < 1e-5
    assert guarded_plugin["topology_penalty_claim_safe"] is True
    assert guarded_plugin["topology_penalty_force_term_status"] == "pass"
    assert guarded_plugin["topology_penalty_finite_difference_force_error"] < 1e-5
    assert guarded_plugin["water_displacement_proxy_missing_metadata_blocked"] is True
    assert guarded_plugin["water_displacement_proxy_invalid_topology_blocked"] is True
    assert guarded_plugin["water_displacement_proxy_model_unvalidated_blocked"] is True
    assert guarded_plugin["water_displacement_proxy_weights_invalid_blocked"] is True
    assert guarded_plugin["water_displacement_proxy_policy_cap_exceeded_blocked"] is True
    assert guarded_plugin["water_displacement_proxy_claim_safe"] is True
    assert guarded_plugin["water_displacement_proxy_force_term_status"] == "pass"
    assert guarded_plugin["water_displacement_proxy_finite_difference_force_error"] < 1e-5
    assert guarded_plugin["policy_caps_ready"] is True
    assert guarded_plugin["observed_caps_ready"] is True
    assert guarded_plugin["bounded_correction_ready"] is True
    assert guarded_plugin["policy_cap_exceeded_blocked"] is True
    assert guarded_plugin["pocket_wall_policy_cap_exceeded_blocked"] is True
    assert guarded_plugin["torsion_prior_policy_cap_exceeded_blocked"] is True
    assert guarded_plugin["topology_penalty_policy_cap_exceeded_blocked"] is True
    assert guarded_plugin["forcefield_neighbor_product_required"] is True
    assert guarded_plugin["forcefield_neighbor_pairs_provided"] is True
    assert guarded_plugin["forcefield_neighbor_source"] == "provided_cell_list"
    assert guarded_plugin["forcefield_neighbor_nxn_allocation_observed"] is False
    assert guarded_plugin["forcefield_bounded_row_ready"] is True
    assert guarded_plugin["forcefield_guarded_rows_ready"] is True
    assert guarded_plugin["forcefield_guarded_claim_row"]["force_term_name"] == "screened_electrostatics"
    assert guarded_plugin["forcefield_guarded_claim_row"]["policy_caps_ready"] is True
    assert guarded_plugin["forcefield_guarded_claim_row"]["observed_caps_ready"] is True
    assert guarded_plugin["forcefield_guarded_claim_row"]["bounded_correction_ready"] is True
    assert [row["force_term_name"] for row in guarded_plugin["forcefield_guarded_claim_rows"]] == [
        "pocket_wall",
        "screened_electrostatics",
        "topology_penalty",
        "torsion_prior",
        "water_displacement_proxy",
    ]
    assert all(row["claim_safe"] is True for row in guarded_plugin["forcefield_guarded_claim_rows"])
    assert all(row["bounded_correction_ready"] is True for row in guarded_plugin["forcefield_guarded_claim_rows"])
    assert [row["force_term_name"] for row in guarded_plugin["guarded_term_rows"]] == [
        "screened_electrostatics",
        "pocket_wall",
        "torsion_prior",
        "topology_penalty",
        "water_displacement_proxy",
    ]
    assert guarded_plugin["abs_energy_within_cap"] is True
    assert guarded_plugin["force_norm_within_cap"] is True
    assert guarded_plugin["active_pair_count_within_cap"] is True
    assert guarded_plugin["policy_caps"]["max_abs_energy"] == 50.0
    assert guarded_plugin["policy_caps"]["max_force_norm"] == 25.0
    assert guarded_plugin["observed_abs_energy"] > 0.0
    assert guarded_plugin["observed_force_norm"] > 0.0
    force_term_smoke = report["product_kpi"]["force_term_claim_metadata_smoke"]
    assert force_term_smoke["forcefield_energy_forces_contract_ready"] is True
    assert force_term_smoke["forcefield_energy_forces_contract_error"] == ""
    assert force_term_smoke["forcefield_energy_shape"] == [1]
    assert force_term_smoke["forcefield_forces_shape"] == [1, 3, 3]
    assert force_term_smoke["forcefield_energy_finite"] is True
    assert force_term_smoke["forcefield_forces_finite"] is True
    assert force_term_smoke["forcefield_term_count"] == 3
    assert force_term_smoke["forcefield_term_diagnostics_ready"] is True
    assert force_term_smoke["forcefield_claim_safe"] is True
    assert force_term_smoke["forcefield_unsafe_base_claim_blocked"] is True
    assert force_term_smoke["forcefield_unsafe_base_claim_safe"] is False
    assert force_term_smoke["forcefield_unsafe_base_blocked_reason"] == "placeholder_alanine_topology"
    assert force_term_smoke["forcefield_unsafe_base_claim_safe_count"] == 0
    assert force_term_smoke["forcefield_unsafe_base_blocked_count"] == 3
    assert {
        row["force_term_name"]
        for row in force_term_smoke["forcefield_unsafe_base_claim_rows"]
    } == {"directional_hbond", "hydrophobic_contact", "legacy_lj"}
    assert all(
        row["claim_safe"] is False
        and row["blocked_reason"] == "placeholder_alanine_topology"
        for row in force_term_smoke["forcefield_unsafe_base_claim_rows"]
    )
    assert force_term_smoke["forcefield_blocked_reason"] == ""
    assert force_term_smoke["forcefield_hbond_evidence_status"] == "pass"
    assert force_term_smoke["forcefield_hbond_evidence_schema_version"] == "hbond_evidence_v1"
    assert force_term_smoke["forcefield_claim_metadata_schema_version"] == "force_term_claim_metadata_v1"
    assert force_term_smoke["forcefield_neighbor_diagnostics_ready"] is True
    assert force_term_smoke["forcefield_neighbor_pair_count"] > 0
    assert force_term_smoke["forcefield_neighbor_pairs_provided"] is True
    assert force_term_smoke["forcefield_neighbor_source"] == "provided_cell_list"
    assert force_term_smoke["forcefield_claim_safe_count"] == 3
    assert force_term_smoke["forcefield_blocked_count"] == 0
    assert {
        row["force_term_name"]
        for row in force_term_smoke["forcefield_claim_rows"]
    } == {"directional_hbond", "hydrophobic_contact", "legacy_lj"}
    assert all(row["claim_safe"] is True for row in force_term_smoke["forcefield_claim_rows"])
    assert any(
        row["force_term_name"] == "directional_hbond"
        and row["hbond_evidence_schema_version"] == "hbond_evidence_v1"
        and row["hbond_evidence_schema_ready"] is True
        for row in force_term_smoke["forcefield_claim_rows"]
    )
    assert force_term_smoke["term_count"] == 3
    assert force_term_smoke["term_result_contract_ready"] is True
    assert force_term_smoke["term_result_contract_term_set_ready"] is True
    assert force_term_smoke["term_result_contract_term_count"] == 3
    assert force_term_smoke["term_result_contract_terms"] == [
        "directional_hbond",
        "hydrophobic_contact",
        "legacy_lj",
    ]
    assert force_term_smoke["term_result_contract_expected_terms"] == [
        "directional_hbond",
        "hydrophobic_contact",
        "legacy_lj",
    ]
    assert len(force_term_smoke["term_result_contract_rows"]) == 3
    assert all(row["ready"] is True for row in force_term_smoke["term_result_contract_rows"])
    assert all(row["energy_shape"] == [1] for row in force_term_smoke["term_result_contract_rows"])
    assert all(row["forces_shape"] == [1, 3, 3] for row in force_term_smoke["term_result_contract_rows"])
    assert all(row["energy_finite"] is True for row in force_term_smoke["term_result_contract_rows"])
    assert all(row["forces_finite"] is True for row in force_term_smoke["term_result_contract_rows"])
    assert all(row["diagnostics_keys_present"] is True for row in force_term_smoke["term_result_contract_rows"])
    assert all(row["claim_metadata_keys_present"] is True for row in force_term_smoke["term_result_contract_rows"])
    assert all(row["has_required_claim_keys"] is True for row in force_term_smoke["rows"])
    assert all(row["claim_safe"] is True for row in force_term_smoke["rows"])
    assert report["product_kpi"]["core_forcefield_bridge_ready"] is True
    assert report["pm_kpi_summary"]["product"]["core_forcefield_bridge_ready"] is True
    core_bridge_smoke = report["product_kpi"]["core_forcefield_bridge_smoke"]
    assert core_bridge_smoke["ready"] is True
    assert core_bridge_smoke["result_claim_safe"] is True
    assert core_bridge_smoke["force_term_plugins"] == ["legacy_lj"]
    assert core_bridge_smoke["unsafe_base_claim_blocked"] is True
    assert core_bridge_smoke["unsafe_base_claim_safe"] is False
    assert core_bridge_smoke["unsafe_base_blocked_reason"] == "placeholder_alanine_topology"
    assert core_bridge_smoke["unsafe_base_claim_safe_count"] == 0
    assert core_bridge_smoke["unsafe_base_blocked_count"] == 1
    assert core_bridge_smoke["unsafe_base_claim_rows"][0]["claim_safe"] is False
    assert core_bridge_smoke["unsafe_base_claim_rows"][0]["blocked_reason"] == "placeholder_alanine_topology"
    assert core_bridge_smoke["neighbor_diagnostics_ready"] is True
    assert core_bridge_smoke["neighbor_pair_count"] > 0
    assert core_bridge_smoke["neighbor_pairs_provided"] is True
    assert core_bridge_smoke["neighbor_source"] == "provided_cell_list"
    assert report["product_kpi"]["core_compatibility_layer_ready"] is True
    assert report["pm_kpi_summary"]["product"]["core_compatibility_layer_ready"] is True
    core_compatibility = report["product_kpi"]["core_compatibility_layer_smoke"]
    assert core_compatibility["ready"] is True
    assert core_compatibility["row_count"] == 7
    assert {
        row["contract"] for row in core_compatibility["rows"]
    } == {
        "onsps_backmap_shim",
        "topology_protein_bridge",
        "adress_production_blocked_log",
        "forcefield_product_bridge",
        "score_residual_shim",
        "topology_score_correction_shim",
        "mm_gbsa_refine_shim",
    }
    assert all(row["ready"] is True for row in core_compatibility["rows"])
    for contract in {"score_residual_shim", "topology_score_correction_shim", "mm_gbsa_refine_shim"}:
        migrated_row = next(row for row in core_compatibility["rows"] if row["contract"] == contract)
        assert migrated_row["bridge_type"] == "import_identity"
        assert migrated_row["missing_symbols"] == []
        assert migrated_row["identity_mismatches"] == []
    adress_compat = next(
        row for row in core_compatibility["rows"] if row["contract"] == "adress_production_blocked_log"
    )
    assert adress_compat["adress_log_blocked"] is True
    assert adress_compat["adress_log_active_claim_absent"] is True
    assert adress_compat["adress_neighbor_blocked"] is True
    forcefield_compat = next(
        row for row in core_compatibility["rows"] if row["contract"] == "forcefield_product_bridge"
    )
    assert forcefield_compat["unsafe_base_claim_blocked"] is True
    assert forcefield_compat["unsafe_base_claim_safe"] is False
    assert forcefield_compat["unsafe_base_blocked_reason"] == "placeholder_alanine_topology"
    assert forcefield_compat["unsafe_base_claim_safe_count"] == 0
    assert forcefield_compat["unsafe_base_blocked_count"] == 1
    assert forcefield_compat["unsafe_base_claim_rows"][0]["claim_safe"] is False
    assert forcefield_compat["unsafe_base_claim_rows"][0]["blocked_reason"] == "placeholder_alanine_topology"
    assert forcefield_compat["neighbor_diagnostics_ready"] is True
    assert forcefield_compat["neighbor_pair_count"] > 0
    assert forcefield_compat["neighbor_pairs_provided"] is True
    assert forcefield_compat["neighbor_source"] == "provided_cell_list"
    assert report["product_kpi"]["job_store_lazy_factory_ready"] is True
    assert report["pm_kpi_summary"]["product"]["job_store_lazy_factory_ready"] is True
    job_store_smoke = report["product_kpi"]["job_store_lazy_factory_smoke"]
    assert job_store_smoke["ready"] is True
    assert job_store_smoke["factory"] == "api.job_store.get_configured_job_store"
    assert job_store_smoke["same_path_reused"] is True
    assert job_store_smoke["changed_path_reopened"] is True
    assert report["product_kpi"]["allowlisted_runner_shim_contract_ready"] is True
    assert report["pm_kpi_summary"]["product"]["allowlisted_runner_shim_contract_ready"] is True
    shim_contract = report["product_kpi"]["allowlisted_runner_shim_contract"]
    from api.validated_runner import ALLOWED_RUNNER_SCRIPTS

    assert shim_contract["runner_count"] == 3
    assert {row["runner_script"] for row in shim_contract["rows"]} == ALLOWED_RUNNER_SCRIPTS
    assert all(row["ready"] is True for row in shim_contract["rows"])
    assert all(row["adapter_import_present"] is True for row in shim_contract["rows"])
    assert all(row["runtime_adapter_identity_ready"] is True for row in shim_contract["rows"])
    assert all(row["shim_contract_type"] == "canonical_module_alias" for row in shim_contract["rows"])
    assert all(row["sys_modules_alias_ready"] is True for row in shim_contract["rows"])
    assert all(row["self_implementation_blocked"] is True for row in shim_contract["rows"])
    assert all(row["missing_runtime_symbols"] == [] for row in shim_contract["rows"])
    assert all(row["runtime_adapter_error"] == "" for row in shim_contract["rows"])
    assert {
        row["adapter_import"] for row in shim_contract["rows"]
    } == {
        "betelgeuze_engine.product.runners.htvs_pipeline",
        "betelgeuze_engine.product.runners.backmapping_scoring",
        "betelgeuze_engine.product.runners.topk_delivery",
    }
    assert report["product_kpi"]["product_runner_engine_imports_ready"] is True
    assert report["pm_kpi_summary"]["product"]["product_runner_engine_imports_ready"] is True
    runner_imports = report["product_kpi"]["product_runner_engine_imports_smoke"]
    assert runner_imports["ready"] is True
    assert runner_imports["row_count"] == 6
    assert {
        row["contract"] for row in runner_imports["rows"]
    } == {
        "hbond_evidence_direct_engine_import",
        "onsps_backmap_direct_engine_import",
        "ligand_topology_direct_engine_import",
        "topology_score_correction_direct_engine_import",
        "score_residual_direct_engine_import",
        "mm_gbsa_refine_direct_engine_import",
    }
    assert all(row["direct_import_present"] is True for row in runner_imports["rows"])
    assert all(row["legacy_import_absent"] is True for row in runner_imports["rows"])
    score_residual_row = next(
        row for row in runner_imports["rows"] if row["contract"] == "score_residual_direct_engine_import"
    )
    assert score_residual_row["residual_scope"] == "score_ranking_heuristic"
    assert score_residual_row["physical_force_residual_claim"] is False
    topology_correction_row = next(
        row
        for row in runner_imports["rows"]
        if row["contract"] == "topology_score_correction_direct_engine_import"
    )
    assert topology_correction_row["residual_scope"] == "score_ranking_heuristic"
    assert topology_correction_row["physical_force_residual_claim"] is False
    assert topology_correction_row["bounded_correction_required"] is True
    mm_gbsa_row = next(
        row for row in runner_imports["rows"] if row["contract"] == "mm_gbsa_refine_direct_engine_import"
    )
    assert mm_gbsa_row["refine_claim_safe_required"] is False
    assert mm_gbsa_row["claim_metadata_schema"] == "mm_gbsa_refine_claim_metadata_v1"
    assert report["product_kpi"]["product_runner_no_core_imports_ready"] is True
    assert report["pm_kpi_summary"]["product"]["product_runner_no_core_imports_ready"] is True
    runner_no_core = report["product_kpi"]["product_runner_no_core_imports_smoke"]
    assert runner_no_core["ready"] is True
    assert runner_no_core["row_count"] == 9
    assert runner_no_core["legacy_core_import_violation_count"] == 0
    assert all(row["ready"] is True for row in runner_no_core["rows"])
    assert all(row["legacy_core_import_violation_count"] == 0 for row in runner_no_core["rows"])
    assert report["product_kpi"]["topk_delivery_engine_owned_ready"] is True
    assert report["pm_kpi_summary"]["product"]["topk_delivery_engine_owned_ready"] is True
    topk_owned = report["product_kpi"]["topk_delivery_engine_owned_smoke"]
    assert topk_owned["ready"] is True
    assert topk_owned["engine_forbidden_present"] == []
    assert topk_owned["compatibility_self_implementation_present"] is False
    assert topk_owned["runtime_identity_ready"] is True
    assert topk_owned["claim_metadata_ready"] is True
    assert topk_owned["claim_metadata_schema_version"] == "topk_delivery_claim_metadata_v1"
    assert topk_owned["claim_metadata_claim_safe"] is True
    assert topk_owned["claim_metadata_physical_accuracy_claim"] is False
    assert report["product_kpi"]["backmapping_scoring_engine_owned_ready"] is True
    assert report["pm_kpi_summary"]["product"]["backmapping_scoring_engine_owned_ready"] is True
    backmapping_owned = report["product_kpi"]["backmapping_scoring_engine_owned_smoke"]
    assert backmapping_owned["ready"] is True
    assert backmapping_owned["engine_module"] == "betelgeuze_engine.product.runners.backmapping_scoring"
    assert backmapping_owned["engine_required_missing"] == []
    assert backmapping_owned["engine_forbidden_present"] == []
    assert backmapping_owned["compatibility_required_missing"] == []
    assert backmapping_owned["compatibility_self_implementation_present"] is False
    assert backmapping_owned["runtime_identity_ready"] is True
    assert backmapping_owned["runtime_error"] == ""
    assert report["product_kpi"]["htvs_pipeline_engine_owned_ready"] is True
    assert report["pm_kpi_summary"]["product"]["htvs_pipeline_engine_owned_ready"] is True
    htvs_owned = report["product_kpi"]["htvs_pipeline_engine_owned_smoke"]
    assert htvs_owned["ready"] is True
    assert htvs_owned["engine_module"] == "betelgeuze_engine.product.runners.htvs_pipeline"
    assert htvs_owned["engine_required_missing"] == []
    assert htvs_owned["engine_forbidden_present"] == []
    assert htvs_owned["compatibility_required_missing"] == []
    assert htvs_owned["compatibility_self_implementation_present"] is False
    assert htvs_owned["runtime_identity_ready"] is True
    assert htvs_owned["runtime_error"] == ""
    assert report["product_kpi"]["product_runner_engine_owned_ready"] is True
    assert report["pm_kpi_summary"]["product"]["product_runner_engine_owned_ready"] is True
    runner_owned = report["product_kpi"]["product_runner_engine_owned_smoke"]
    assert runner_owned["ready"] is True
    assert runner_owned["runner_count"] == 3
    assert runner_owned["engine_owned_runner_count"] == 3
    assert runner_owned["contract"] == "all_product_runners_are_engine_owned_with_compatibility_shims"
    assert {
        row["runner_id"] for row in runner_owned["rows"]
    } == {
        "ligand_htvs_pipeline_default",
        "backmapping_scoring.production",
        "ligand_topk_delivery.production",
    }
    assert all(row["ready"] is True for row in runner_owned["rows"])
    assert all(row["runtime_identity_ready"] is True for row in runner_owned["rows"])
    assert all(row["compatibility_self_implementation_present"] is False for row in runner_owned["rows"])
    assert report["product_kpi"]["blocked_claim_correctly_blocked"] is True
    assert report["pm_kpi_summary"]["product"]["blocked_claim_correctly_blocked"] is True
    assert report["product_kpi"]["runner_profile_validation_pass"] is True
    assert report["pm_kpi_summary"]["product"]["runner_profile_validation_pass"] is True
    assert report["physics_kpi"]["finite_difference_force_error"] < 1e-3
    assert report["pm_kpi_summary"]["physics"]["finite_difference_force_error_pass"] is True
    assert report["physics_kpi"]["rotation_equivariance_error"] < 1e-9
    assert report["pm_kpi_summary"]["physics"]["rotation_equivariance_error"] < 1e-9
    assert report["pm_kpi_summary"]["physics"]["rotation_equivariance_pass"] is True
    assert report["physics_kpi"]["energy_drift_smoke_pct"] < 1e-2
    assert report["pm_kpi_summary"]["physics"]["energy_drift_pass"] is True
    assert report["physics_kpi"]["neighbor_list_parity_error"] == 0.0
    assert report["pm_kpi_summary"]["physics"]["neighbor_list_parity_pass"] is True
    assert report["physics_kpi"]["force_term_physics_validation_ready"] is True
    assert report["pm_kpi_summary"]["physics"]["force_term_physics_validation_ready"] is True
    assert report["physics_kpi"]["force_term_physics_validation_term_count"] == 3
    assert report["pm_kpi_summary"]["physics"]["force_term_physics_validation_term_count"] == 3
    assert report["physics_kpi"]["force_term_physics_validation_claim_safe_ready"] is True
    assert report["pm_kpi_summary"]["physics"]["force_term_physics_validation_claim_safe_ready"] is True
    assert report["physics_kpi"]["force_term_physics_validation_claim_safe_count"] == 3
    assert report["pm_kpi_summary"]["physics"]["force_term_physics_validation_claim_safe_count"] == 3
    assert {
        row["term"] for row in report["physics_kpi"]["force_term_physics_validation_rows"]
    } == {"directional_hbond", "hydrophobic_contact", "legacy_lj"}
    assert all(row["ready"] is True for row in report["physics_kpi"]["force_term_physics_validation_rows"])
    assert all(row["force_term_status"] == "pass" for row in report["physics_kpi"]["force_term_physics_validation_rows"])
    assert all(row["claim_safe"] is True for row in report["physics_kpi"]["force_term_physics_validation_rows"])
    assert all(row["blocked_reason"] == "" for row in report["physics_kpi"]["force_term_physics_validation_rows"])
    assert report["physics_kpi"]["force_term_finite_difference_max_error"] < 1e-4
    assert report["physics_kpi"]["force_term_translation_invariance_max_error"] < 1e-9
    assert report["physics_kpi"]["force_term_rotation_equivariance_max_error"] < 1e-9
    assert report["physics_kpi"]["force_term_energy_drift_max_pct"] < 5e-2
    assert report["physics_kpi"]["topology_invalid_rate"] == report["chemistry_kpi"]["topology_invalid_rate"]
    assert report["physics_kpi"]["backmapping_failure_rate"] == report["chemistry_kpi"]["backmapping_failure_rate"]
    assert report["pm_kpi_summary"]["physics"]["topology_invalid_rate"] == report["physics_kpi"]["topology_invalid_rate"]
    assert report["pm_kpi_summary"]["physics"]["backmapping_failure_rate"] == report["physics_kpi"]["backmapping_failure_rate"]
    assert report["pm_kpi_summary"]["physics"]["topology_invalid_rate_pass"] is True
    assert report["pm_kpi_summary"]["physics"]["backmapping_failure_rate_pass"] is True
    assert report["runtime_kpi"]["score_only_1k"]["row_count"] == 8
    assert report["runtime_kpi"]["top100_4bead_rescoring"]["onsps_backmap_claim_safe_count"] >= 1
    assert report["pm_kpi_summary"]["runtime"]["score_only_1k_runtime_tracked"] is True
    assert report["pm_kpi_summary"]["runtime"]["top100_4bead_rescoring_runtime_tracked"] is True
    assert report["pm_kpi_summary"]["runtime"]["top10_force_residual_runtime_tracked"] is True
    scaling_kpi = report["runtime_kpi"]["neighbor_cap_scaling"]
    assert scaling_kpi["ready"] is True
    assert scaling_kpi["status"] == "runtime_neighbor_cap_scaling_ready"
    assert scaling_kpi["forcefield_contract_ready"] is True
    assert scaling_kpi["neighbor_cap_scaling_ready"] is True
    assert 0.85 <= scaling_kpi["neighbor_pair_count_slope"] <= 1.15
    assert scaling_kpi["neighbor_pair_count_r2"] >= 0.98
    assert len(scaling_kpi["rows"]) >= 3
    assert all(row["neighbor_pairs_provided"] is True for row in scaling_kpi["rows"])
    assert all(row["neighbor_source"] == "provided_cell_list" for row in scaling_kpi["rows"])
    assert all(row["neighbor_provider_status"] == "neighbor_provider_ready" for row in scaling_kpi["rows"])
    assert all(row["neighbor_provider_overflow"] is False for row in scaling_kpi["rows"])
    assert all(row["nxn_allocation_observed"] is False for row in scaling_kpi["rows"])
    assert all(row["coordinate_mode"] == "fixed_density_grid" for row in scaling_kpi["rows"])
    assert all(row["fixed_density"] is True for row in scaling_kpi["rows"])
    assert all(row["box_size"] > 0.0 for row in scaling_kpi["rows"])
    assert all(row["density_relative_error"] <= 1e-9 for row in scaling_kpi["rows"])
    assert all(row["memory_peak_mb_per_atom"] > 0.0 for row in scaling_kpi["rows"])
    assert all(row["row_ready"] is True for row in scaling_kpi["rows"])
    assert scaling_kpi["nxn_allocation_observed"] is False
    assert scaling_kpi["coordinate_mode"] == "fixed_density_grid"
    assert scaling_kpi["fixed_density_ready"] is True
    assert scaling_kpi["target_number_density"] > 0.0
    assert scaling_kpi["max_density_relative_error"] <= 1e-9
    assert scaling_kpi["release_atom_counts"] == [1000, 2000, 4000, 8000]
    assert scaling_kpi["release_atom_counts_ready"] is False
    assert scaling_kpi["memory_per_atom_linear_ready"] is True
    assert scaling_kpi["max_memory_peak_mb_per_atom"] > 0.0
    assert scaling_kpi["total_rebuild_count"] > 0
    plot_path = Path(scaling_kpi["plot_path"])
    assert scaling_kpi["plot_ready"] is True
    assert scaling_kpi["plot_format"] == "svg"
    assert scaling_kpi["plot_role"] == "runtime_neighbor_cap_scaling_plot"
    assert len(scaling_kpi["plot_sha256"]) == 64
    assert scaling_kpi["plot_size_bytes"] > 0
    assert "Pair-count scaling" in scaling_kpi["plot_claim_boundary"]
    assert "advisory" in scaling_kpi["plot_claim_boundary"]
    assert plot_path.exists()
    assert "Capped neighbor pairs" in plot_path.read_text(encoding="utf-8")
    assert report["pm_kpi_summary"]["runtime"]["runtime_neighbor_cap_scaling_ready"] is True
    assert (
        report["pm_kpi_summary"]["runtime"]["runtime_neighbor_cap_scaling_nxn_allocation_observed"]
        is False
    )
    assert (
        report["pm_kpi_summary"]["runtime"]["runtime_neighbor_cap_scaling_memory_per_atom_linear_ready"]
        is True
    )
    assert (
        report["pm_kpi_summary"]["runtime"]["runtime_neighbor_cap_scaling_fixed_density_ready"]
        is True
    )
    assert (
        report["pm_kpi_summary"]["runtime"]["runtime_neighbor_cap_scaling_release_atom_counts_ready"]
        is False
    )
    assert (
        report["pm_kpi_summary"]["runtime"]["runtime_neighbor_cap_scaling_max_memory_peak_mb_per_atom"]
        == scaling_kpi["max_memory_peak_mb_per_atom"]
    )
    assert (
        report["pm_kpi_summary"]["runtime"]["runtime_neighbor_cap_scaling_total_rebuild_count"]
        == scaling_kpi["total_rebuild_count"]
    )
    assert report["pm_kpi_summary"]["runtime"]["runtime_neighbor_cap_scaling_plot_ready"] is True
    assert (
        report["pm_kpi_summary"]["runtime"]["runtime_neighbor_cap_scaling_plot_path"]
        == scaling_kpi["plot_path"]
    )
    assert (
        report["pm_kpi_summary"]["runtime"]["runtime_neighbor_cap_scaling_plot_sha256"]
        == scaling_kpi["plot_sha256"]
    )
    assert (
        report["pm_kpi_summary"]["runtime"]["runtime_neighbor_cap_scaling_pair_count_slope"]
        == scaling_kpi["neighbor_pair_count_slope"]
    )
    assert (
        report["pm_kpi_summary"]["runtime"]["runtime_neighbor_cap_scaling_pair_count_r2"]
        == scaling_kpi["neighbor_pair_count_r2"]
    )
    residual_kpi = report["runtime_kpi"]["top10_force_residual"]
    assert residual_kpi["applied_count"] == 3
    assert residual_kpi["delta_score_cap_abstention_count"] == 1
    assert residual_kpi["uncertainty_abstention_count"] == 1
    assert residual_kpi["nonfinite_uncertainty_abstention_count"] == 1
    assert residual_kpi["nonfinite_delta_score_abstention_count"] == 1
    assert residual_kpi["outside_top_k_abstention_count"] == 1
    assert residual_kpi["bounded_correction_policy_ready"] is True
    assert residual_kpi["observed_caps_ready"] is True
    assert residual_kpi["contract_ready"] is True
    assert residual_kpi["confidence_abstention_ready"] is True
    assert residual_kpi["top_k_policy_ready"] is True
    assert residual_kpi["contract_expected_report_count"] == 6
    assert residual_kpi["contract_validated_report_count"] == 6
    assert residual_kpi["contract_validation_ready"] is True
    assert residual_kpi["contract_validated_report_labels"] == [
        "applied_runtime_last",
        "delta_score_cap",
        "uncertainty_abstention",
        "outside_top_k",
        "nonfinite_uncertainty",
        "nonfinite_delta_score",
    ]
    assert report["pm_kpi_summary"]["runtime"]["force_residual_bounded_policy_ready"] is True
    assert report["pm_kpi_summary"]["runtime"]["force_residual_observed_caps_ready"] is True
    assert report["pm_kpi_summary"]["runtime"]["force_residual_contract_ready"] is True
    assert report["pm_kpi_summary"]["runtime"]["force_residual_confidence_abstention_ready"] is True
    assert report["pm_kpi_summary"]["runtime"]["force_residual_top_k_policy_ready"] is True
    assert report["pm_kpi_summary"]["runtime"]["force_residual_abstain_threshold"] == 0.75
    assert report["pm_kpi_summary"]["runtime"]["force_residual_top_k_rank_pct"] == 0.05
    assert residual_kpi["last_claim_metadata"]["force_residual_applied"] is True
    assert residual_kpi["last_claim_metadata"]["force_residual_delta_score"] == 0.25
    assert residual_kpi["last_claim_metadata"]["force_residual_confidence"] == 0.9
    assert residual_kpi["last_claim_metadata"]["force_residual_abstain_threshold"] == 0.75
    assert residual_kpi["last_claim_metadata"]["force_residual_rank_pct"] == 0.01
    assert residual_kpi["last_claim_metadata"]["force_residual_top_k_rank_pct"] == 0.05
    assert residual_kpi["last_claim_metadata"]["force_residual_top_k_eligible"] is True
    assert residual_kpi["last_claim_metadata"]["force_residual_force_norm_within_cap"] is True
    assert residual_kpi["last_claim_metadata"]["force_residual_energy_drift_within_cap"] is True
    assert residual_kpi["last_claim_metadata"]["force_residual_displacement_within_cap"] is True
    assert residual_kpi["last_claim_metadata"]["force_residual_delta_score_within_cap"] is True
    assert residual_kpi["last_claim_metadata"]["force_residual_all_observed_caps_within_policy"] is True
    assert residual_kpi["last_claim_metadata"]["force_residual_claim_metadata_schema_version"] == "force_residual_claim_metadata_v1"
    assert residual_kpi["last_claim_metadata"]["force_residual_policy_caps_ready"] is True
    assert residual_kpi["last_claim_metadata"]["force_residual_observed_caps_ready"] is True
    assert residual_kpi["last_report"]["all_observed_caps_within_policy"] is True
    assert residual_kpi["last_report"]["claim_metadata_schema_version"] == "force_residual_claim_metadata_v1"
    assert residual_kpi["last_report"]["policy_caps_ready"] is True
    assert residual_kpi["last_report"]["observed_caps_ready"] is True
    assert residual_kpi["delta_score_cap_report"]["skipped_reason"] == "delta_score_cap_exceeded"
    assert residual_kpi["delta_score_cap_report"]["delta_score_within_cap"] is False
    assert residual_kpi["delta_score_cap_report"]["all_observed_caps_within_policy"] is False
    assert residual_kpi["delta_score_cap_report"]["policy_caps_ready"] is True
    assert residual_kpi["delta_score_cap_report"]["observed_caps_ready"] is False
    assert residual_kpi["delta_score_cap_report"]["policy_caps"]["max_abs_delta_score"] == 2.0
    assert residual_kpi["delta_score_cap_report"]["policy_caps"]["max_force_norm"] == 25.0
    assert residual_kpi["delta_score_cap_report"]["policy_caps"]["max_displacement"] == 0.25
    assert residual_kpi["delta_score_cap_report"]["policy_caps"]["max_energy_drift"] == 5.0
    assert residual_kpi["delta_score_cap_report"]["policy_caps"]["max_energy_drift_pct"] == 5.0
    assert residual_kpi["delta_score_cap_report"]["policy_caps"]["abstain_threshold"] == 0.75
    assert {
        "max_abs_delta_score",
        "max_force_norm",
        "max_displacement",
        "max_energy_drift",
        "top_k_rank_pct",
        "abstain_threshold",
    }.issubset(set(residual_kpi["required_policy_caps"]))
    assert residual_kpi["uncertainty_abstention_report"]["skipped_reason"] == "uncertainty_abstained"
    assert residual_kpi["uncertainty_abstention_report"]["confidence"] < 0.25
    assert residual_kpi["uncertainty_abstention_report"]["all_observed_caps_within_policy"] is True
    assert residual_kpi["uncertainty_abstention_report"]["policy_caps"]["abstain_threshold"] == 0.75
    assert residual_kpi["nonfinite_uncertainty_report"]["skipped_reason"] == "uncertainty_nonfinite"
    assert residual_kpi["nonfinite_uncertainty_report"]["uncertainty"] == 1.0
    assert residual_kpi["nonfinite_uncertainty_report"]["confidence"] == 0.0
    assert residual_kpi["nonfinite_uncertainty_report"]["observed_caps_ready"] is True
    assert residual_kpi["nonfinite_delta_score_report"]["skipped_reason"] == "delta_score_nonfinite"
    assert residual_kpi["nonfinite_delta_score_report"]["delta_score"] == 0.0
    assert residual_kpi["nonfinite_delta_score_report"]["confidence"] == 0.9
    assert residual_kpi["nonfinite_delta_score_report"]["observed_caps_ready"] is True
    assert residual_kpi["outside_top_k_report"]["skipped_reason"] == "outside_top_k_policy"
    assert residual_kpi["outside_top_k_report"]["rank_pct"] > residual_kpi["outside_top_k_report"]["policy_caps"]["top_k_rank_pct"]
    assert residual_kpi["outside_top_k_report"]["top_k_eligible"] is False
    assert residual_kpi["outside_top_k_report"]["policy_caps"]["top_k_rank_pct"] == 0.05
    assert report["runtime_kpi"]["memory_peak_mb"] > 0
    assert report["runtime_kpi"]["neighbor_list_rebuild"]["neighbor_list_rebuild_count"] > 0
    assert report["runtime_kpi"]["neighbor_list_rebuild"]["neighbor_list_rebuild_frequency"] > 0
    assert report["runtime_kpi"]["neighbor_list_rebuild"]["engine_neighbor_diagnostics_ready"] is True
    assert report["runtime_kpi"]["neighbor_list_rebuild"]["forcefield_neighbor_pairs_provided"] is True
    assert report["runtime_kpi"]["neighbor_list_rebuild"]["forcefield_neighbor_source"] == "provided_cell_list"
    assert report["runtime_kpi"]["neighbor_list_rebuild"]["neighbor_provider_status"] == "neighbor_provider_ready"
    assert report["runtime_kpi"]["neighbor_list_rebuild"]["neighbor_provider_overflow"] is False
    assert report["runtime_kpi"]["neighbor_list_rebuild"]["neighbor_provider_nxn_allocation_observed"] is False
    assert (
        report["runtime_kpi"]["neighbor_list_rebuild"]["last_forcefield_neighbor_pair_count"]
        == report["runtime_kpi"]["neighbor_list_rebuild"]["last_neighbor_pair_count"]
    )
    assert report["pm_kpi_summary"]["runtime"]["memory_peak_tracked"] is True
    assert report["pm_kpi_summary"]["runtime"]["neighbor_list_rebuild_frequency_tracked"] is True
    assert report["chemistry_kpi"]["fixture_count"] >= 7
    assert report["chemistry_kpi"]["hbond_evidence_schema_ready"] is True
    assert report["pm_kpi_summary"]["chemistry"]["hbond_evidence_schema_ready"] is True
    assert (
        report["chemistry_kpi"]["hbond_evidence_schema_ready_count"]
        == report["chemistry_kpi"]["fixture_count"]
    )
    assert report["chemistry_kpi"]["ligand_topology_validity_schema_ready"] is True
    assert (
        report["chemistry_kpi"]["ligand_topology_validity_schema_ready_count"]
        == report["chemistry_kpi"]["fixture_count"]
    )
    assert report["pm_kpi_summary"]["chemistry"]["ligand_topology_validity_schema_ready"] is True
    assert report["chemistry_kpi"]["hbond_donor_site_count"] >= 1
    assert report["chemistry_kpi"]["hbond_acceptor_site_count"] >= 1
    assert report["pm_kpi_summary"]["chemistry"]["hbond_donor_site_count"] == report["chemistry_kpi"]["hbond_donor_site_count"]
    assert report["pm_kpi_summary"]["chemistry"]["hbond_acceptor_site_count"] == report["chemistry_kpi"]["hbond_acceptor_site_count"]
    assert report["chemistry_kpi"]["chirality_preservation_fixture_count"] >= 1
    assert report["chemistry_kpi"]["unassigned_chirality_blocked_fixture_count"] >= 1
    assert report["chemistry_kpi"]["chirality_preservation_ready"] is True
    assert report["pm_kpi_summary"]["chemistry"]["chirality_preservation_ready"] is True
    assert report["chemistry_kpi"]["ring_validity_fixture_count"] >= 1
    assert report["chemistry_kpi"]["ring_validity_ready"] is True
    assert report["pm_kpi_summary"]["chemistry"]["ring_validity_ready"] is True
    assert report["chemistry_kpi"]["tautomer_validity_fixture_count"] >= 1
    assert report["chemistry_kpi"]["tautomer_validity_ready"] is True
    assert report["pm_kpi_summary"]["chemistry"]["tautomer_validity_ready"] is True
    assert report["chemistry_kpi"]["protonation_validity_fixture_count"] >= 1
    assert report["chemistry_kpi"]["protonation_validity_ready"] is True
    assert report["pm_kpi_summary"]["chemistry"]["protonation_validity_ready"] is True
    assert report["chemistry_kpi"]["backmap_evaluable_fixture_count"] >= 1
    assert report["chemistry_kpi"]["backmap_claim_safe_fixture_count"] >= 1
    assert report["chemistry_kpi"]["backmapping_failure_rate"] == 0.0
    calibration = report["confidence_calibration_report"]
    assert calibration["schema_version"] == "confidence_calibration_v1"
    assert calibration["status"] == "confidence_calibration_report_ready"
    assert calibration["ready"] is True
    assert calibration["row_count"] == report["pose_ranking_hbond_benchmark"]["fixture_count"]
    assert calibration["positive_count"] >= 1
    assert calibration["negative_count"] >= 1
    assert calibration["expected_calibration_error"] <= calibration["max_expected_calibration_error"]
    assert calibration["brier_score"] <= calibration["max_brier_score"]
    assert len(calibration["bins"]) == calibration["bin_count"]
    assert len(calibration["rows"]) == calibration["row_count"]
    assert report["pm_kpi_summary"]["chemistry"]["confidence_calibration_report_ready"] is True
    assert (
        report["pm_kpi_summary"]["chemistry"]["confidence_calibration_row_count"]
        == calibration["row_count"]
    )
    assert (
        report["pm_kpi_summary"]["chemistry"]["confidence_calibration_expected_calibration_error"]
        == calibration["expected_calibration_error"]
    )
    assert (
        report["pm_kpi_summary"]["chemistry"]["confidence_calibration_brier_score"]
        == calibration["brier_score"]
    )
    assert report["pm_kpi_summary"]["chemistry"]["hbond_recovery_pose_count"] >= 1
    assert report["pm_kpi_summary"]["chemistry"]["hbond_recovery_confidence_min"] >= 0.5
    assert report["pm_kpi_summary"]["chemistry"]["hbond_recovery_pose_ids"] == ["amide_near_hbond_pose"]
    assert report["pm_kpi_summary"]["chemistry"]["hbond_recovery_benchmark_ready"] is True
    assert (
        report["pm_kpi_summary"]["chemistry"]["hbond_recovery_benchmark_schema_version"]
        == "hbond_recovery_benchmark_v1"
    )
    assert report["pm_kpi_summary"]["chemistry"]["hbond_recovery_benchmark_fixture_count"] == 3
    assert report["pm_kpi_summary"]["chemistry"]["hbond_recovery_benchmark_contract_pass_count"] == 3
    assert report["chemistry_kpi"]["unsatisfied_donor_acceptor_fixture_count"] >= 1
    assert report["chemistry_kpi"]["unsatisfied_donor_count"] + report["chemistry_kpi"]["unsatisfied_acceptor_count"] >= 1
    assert report["pm_kpi_summary"]["chemistry"]["unsatisfied_donor_acceptor_detection"] is True
    assert report["pm_kpi_summary"]["chemistry"]["unsatisfied_donor_acceptor_fixture_count"] == report["chemistry_kpi"]["unsatisfied_donor_acceptor_fixture_count"]
    assert any(row["hbond_schema_version"] == "hbond_evidence_v1" for row in report["chemistry_kpi"]["rows"])
    assert all(row["hbond_schema_ready"] is True for row in report["chemistry_kpi"]["rows"])
    assert all(
        row["ligand_validity_schema_version"] == "ligand_topology_validity_v1"
        and row["ligand_validity_schema_ready"] is True
        for row in report["chemistry_kpi"]["rows"]
    )
    assert all(
        row["hbond_role_site_count"] == row["site_count"]
        for row in report["chemistry_kpi"]["rows"]
    )
    assert all(
        isinstance(row["hbond_geometry_evaluated"], bool)
        and isinstance(row["hbond_geometry_complete"], bool)
        for row in report["chemistry_kpi"]["rows"]
    )
    assert all(
        isinstance(row["hbond_delta_backmap"], float)
        and isinstance(row["hbond_delta_backmap_max"], float)
        and isinstance(row["hbond_delta_backmap_evaluated"], bool)
        and isinstance(row["hbond_delta_backmap_yellow_band"], bool)
        for row in report["chemistry_kpi"]["rows"]
    )
    assert report["chemistry_kpi"]["hbond_geometry_evaluated_fixture_count"] >= 1
    assert report["chemistry_kpi"]["hbond_geometry_complete_fixture_count"] >= 1
    assert (
        report["pm_kpi_summary"]["chemistry"]["hbond_geometry_evaluated_fixture_count"]
        == report["chemistry_kpi"]["hbond_geometry_evaluated_fixture_count"]
    )
    assert (
        report["pm_kpi_summary"]["chemistry"]["hbond_geometry_complete_fixture_count"]
        == report["chemistry_kpi"]["hbond_geometry_complete_fixture_count"]
    )
    assert all(
        row["onsps_backmap_schema_version"] == "onsps_backmap_evidence_v1"
        for row in report["chemistry_kpi"]["rows"]
    )
    assert all(
        isinstance(row["onsps_backmap_claim_safe"], bool)
        for row in report["chemistry_kpi"]["rows"]
    )
    assert any(
        row["backmap_schema_version"] == "onsps_backmap_evidence_v1"
        for row in report["chemistry_kpi"]["rows"]
        if row["backmap_status"]
    )
    chiral_row = next(row for row in report["chemistry_kpi"]["rows"] if row["fixture"] == "chiral_lactic_acid")
    assert chiral_row["ligand_topology_claim_safe"] is True
    assert chiral_row["ligand_topology_source"] == "rdkit"
    assert chiral_row["specified_chiral_center_count"] == 1
    assert chiral_row["unassigned_chiral_center_count"] == 0
    assert chiral_row["chirality_status"] == "specified"
    assert chiral_row["backmap_evaluable"] is True
    assert chiral_row["backmap_claim_safe"] is True
    assert chiral_row["backmap_source"] == "rdkit_etkdg"
    unassigned_chiral_row = next(
        row for row in report["chemistry_kpi"]["rows"] if row["fixture"] == "unassigned_chiral_lactic_acid"
    )
    assert unassigned_chiral_row["ligand_valid"] is True
    assert unassigned_chiral_row["ligand_topology_claim_safe"] is False
    assert unassigned_chiral_row["unassigned_chiral_center_count"] == 1
    assert unassigned_chiral_row["chirality_status"] == "unassigned_chiral_centers"
    assert "unassigned_ligand_chirality" in unassigned_chiral_row["ligand_validity_blockers"]
    protonated_row = next(row for row in report["chemistry_kpi"]["rows"] if row["fixture"] == "protonated_amine")
    assert protonated_row["protonation_status"] == "charged_state_parsed"
    ring_row = next(row for row in report["chemistry_kpi"]["rows"] if row["fixture"] == "aromatic_ring")
    assert ring_row["ring_status"] == "present"
    assert report["pose_ranking_hbond_benchmark"]["benchmark_ready"] is True
    assert report["pose_ranking_hbond_benchmark"]["top1_pose_id"] == "amide_near_hbond_pose"
    assert report["pose_ranking_hbond_benchmark"]["hbond_recovery_pose_count"] == 1
    assert report["pose_ranking_hbond_benchmark"]["hbond_recovery_pose_ids"] == ["amide_near_hbond_pose"]
    assert report["pose_ranking_hbond_benchmark"]["hbond_recovery_confidence_min"] >= 0.5
    assert (
        report["pose_ranking_hbond_benchmark"]["hbond_recovery_benchmark_schema_version"]
        == "hbond_recovery_benchmark_v1"
    )
    assert report["pose_ranking_hbond_benchmark"]["hbond_recovery_benchmark_ready"] is True
    assert report["pose_ranking_hbond_benchmark"]["hbond_recovery_benchmark_fixture_count"] == 3
    assert report["pose_ranking_hbond_benchmark"]["hbond_recovery_benchmark_contract_pass_count"] == 3
    assert report["pose_ranking_hbond_benchmark"]["hbond_recovery_benchmark"]["ready"] is True
    assert report["pose_ranking_hbond_benchmark"]["invalid_ligand_blocked"] is True
    assert report["pose_ranking_hbond_benchmark"]["overanchored_decoys_blocked"] is True
    assert report["pose_ranking_hbond_benchmark"]["delta_backmap_yellow_band_abstention_ready"] is True
    assert report["pose_ranking_hbond_benchmark"]["unsatisfied_donor_acceptor_detected"] is True
    assert report["pose_ranking_hbond_benchmark"]["unsatisfied_donor_acceptor_pose_count"] >= 1
    assert report["pose_ranking_hbond_benchmark"]["row_contracts_ready"] is True
    assert report["pose_ranking_hbond_benchmark"]["row_contract_pass_count"] == report["pose_ranking_hbond_benchmark"]["fixture_count"]
    assert set(report["pose_ranking_hbond_benchmark"]["required_pose_roles"]).issubset(
        set(report["pose_ranking_hbond_benchmark"]["observed_pose_roles"])
    )
    top_pose = next(
        row for row in report["pose_ranking_hbond_benchmark"]["rows"]
        if row["pose_id"] == "amide_near_hbond_pose"
    )
    assert top_pose["benchmark_role"] == "hbond_recovery_pose"
    assert top_pose["expected_claim_safe"] is True
    assert top_pose["expected_hbond_status"] == "pass"
    assert top_pose["expected_blocked_reason"] == ""
    assert top_pose["benchmark_contract_pass"] is True
    assert all(top_pose["benchmark_contract_checks"].values())
    assert top_pose["onsps_backmap_schema_version"] == "onsps_backmap_evidence_v1"
    assert top_pose["onsps_backmap_status"] == "ok"
    assert top_pose["onsps_backmap_claim_safe"] is True
    assert top_pose["hbond_schema_ready"] is True
    assert top_pose["hbond_threshold_schema_ready"] is True
    assert top_pose["hbond_pair_schema_ready"] is True
    assert top_pose["hbond_geometry_flags_ready"] is True
    assert top_pose["hbond_donor_site_count"] + top_pose["hbond_acceptor_site_count"] == top_pose["hbond_site_count"]
    assert top_pose["hbond_distance_pass_count"] >= 1
    assert top_pose["hbond_angle_pass_count"] >= 1
    assert top_pose["hbond_geometry_evaluated"] is True
    assert top_pose["hbond_geometry_complete"] is True
    overanchored_pose = next(
        row for row in report["pose_ranking_hbond_benchmark"]["rows"]
        if row["pose_id"] == "amide_overanchored_decoy_pose"
    )
    assert overanchored_pose["hbond_claim_safe"] is False
    assert overanchored_pose["overanchoring_flag"] is True
    assert overanchored_pose["hbond_blocked_reason"] == "overanchored_decoy"
    assert overanchored_pose["benchmark_role"] == "overanchored_decoy_pose"
    assert overanchored_pose["expected_claim_safe"] is False
    assert overanchored_pose["expected_blocked_reason"] == "overanchored_decoy"
    assert overanchored_pose["expected_overanchored"] is True
    assert overanchored_pose["benchmark_contract_pass"] is True
    assert overanchored_pose["onsps_backmap_schema_version"] == "onsps_backmap_evidence_v1"
    assert overanchored_pose["hbond_schema_ready"] is True
    assert overanchored_pose["hbond_threshold_schema_ready"] is True
    assert overanchored_pose["hbond_pair_schema_ready"] is True
    assert overanchored_pose["hbond_geometry_flags_ready"] is True
    assert overanchored_pose["hbond_geometry_evaluated"] is True
    assert overanchored_pose["hbond_geometry_complete"] is True
    delta_pose = next(
        row for row in report["pose_ranking_hbond_benchmark"]["rows"]
        if row["pose_id"] == "amide_delta_backmap_yellow_band_pose"
    )
    assert delta_pose["benchmark_role"] == "delta_backmap_yellow_band_pose"
    assert delta_pose["expected_claim_safe"] is False
    assert delta_pose["expected_blocked_reason"] == "delta_backmap_yellow_band"
    assert delta_pose["hbond_claim_safe"] is False
    assert delta_pose["hbond_delta_backmap"] == 3.0
    assert delta_pose["hbond_delta_backmap_max"] == 2.5
    assert delta_pose["hbond_delta_backmap_evaluated"] is True
    assert delta_pose["hbond_delta_backmap_yellow_band"] is True
    assert delta_pose["hbond_blocked_reason"] == "delta_backmap_yellow_band"
    assert delta_pose["benchmark_contract_pass"] is True
    assert any(
        row["hbond_blocked_reason"] == "invalid_smiles"
        for row in report["pose_ranking_hbond_benchmark"]["rows"]
    )
    assert report["rocm_environment_summary"]["rocm_hip_rust_runtime_ready"] is True
    assert report["product_bundle_evidence_export_ready"] is True


def test_build_ai_md_engine_kpi_report_blocks_without_visible_rocm_gpu(tmp_path: Path) -> None:
    rocm = tmp_path / "rocm.json"
    bundle_json = _write_product_evidence_bundle(tmp_path / "bundle.json")
    _write_rocm_manifest(rocm, ready=False)

    report = build_report(
        profiles_dir="config/api_validated_runner_profiles",
        score_only_rows=4,
        onsps_rows=4,
        residual_rows=2,
        rocm_manifest_path=str(rocm),
        product_evidence_bundle_json_path=str(bundle_json),
    )

    assert report["status"] == "blocked_ai_md_engine_kpi_report"
    assert report["report_ready"] is False
    assert report["report_ready"] == report["pm_kpi_summary"]["summary_ready"]
    assert report["rocm_environment_summary"]["rocm_hip_rust_runtime_ready"] is False
    assert report["product_bundle_evidence_export_ready"] is False


def test_build_ai_md_engine_kpi_report_blocks_without_clean_install_success(tmp_path: Path) -> None:
    rocm = tmp_path / "rocm.json"
    bundle_json = _write_product_evidence_bundle(tmp_path / "bundle.json", clean_ready=False)
    _write_rocm_manifest(rocm, ready=True)

    report = build_report(
        profiles_dir="config/api_validated_runner_profiles",
        score_only_rows=4,
        onsps_rows=4,
        residual_rows=2,
        rocm_manifest_path=str(rocm),
        product_evidence_bundle_json_path=str(bundle_json),
    )

    assert report["status"] == "blocked_ai_md_engine_kpi_report"
    assert report["report_ready"] is False
    assert report["product_kpi"]["clean_install_success"] is False
    assert report["product_kpi"]["product_image_receipt_mode"] == "build"
    assert report["product_kpi"]["clean_install_missing_requirements"] == [
        "clean_container_smoke_ready",
        "product_runner_smoke_ready",
        "product_image_receipt_present",
        "product_image_receipt_mode_rocm_runtime",
    ]
    assert report["product_kpi"]["clean_install_missing_requirement_count"] == 4
    assert report["product_kpi"]["product_image_preflight_blocker_codes"] == ["docker_cli_missing"]
    assert report["product_kpi"]["clean_container_missing_requirement_count"] == 14
    assert "container_runtime_receipt_ready" in report["product_kpi"]["clean_container_missing_requirements"]
    assert "runtime_neighbor_release_scaling_ready" in report["product_kpi"]["clean_container_missing_requirements"]
    assert "backmapping_hbond_evidence_receipt_ready" in report["product_kpi"]["clean_container_missing_requirements"]
    assert report["pm_kpi_summary"]["product"]["clean_install_missing_requirements"] == [
        "clean_container_smoke_ready",
        "product_runner_smoke_ready",
        "product_image_receipt_present",
        "product_image_receipt_mode_rocm_runtime",
    ]
    assert report["pm_kpi_summary"]["product"]["clean_container_missing_requirement_count"] == 14
    assert (
        report["pm_kpi_summary"]["product"]["clean_container_missing_requirements"]
        == report["product_kpi"]["clean_container_missing_requirements"]
    )
    assert "clean_install_success" in report["pm_kpi_summary"]["failed_gate_ids"]
    assert report["product_bundle_evidence_export_ready"] is False


def test_build_ai_md_engine_kpi_report_blocks_stale_bundle_sources(tmp_path: Path) -> None:
    rocm = tmp_path / "rocm.json"
    bundle_json = _write_product_evidence_bundle(tmp_path / "bundle.json")
    _write_rocm_manifest(rocm, ready=True)
    bundle_payload = json.loads(bundle_json.read_text(encoding="utf-8"))
    source_kpi = Path(bundle_payload["rows"][0]["artifact_path"])
    source_kpi.write_text("source changed after evidence bundle export\n", encoding="utf-8")

    report = build_report(
        profiles_dir="config/api_validated_runner_profiles",
        score_only_rows=4,
        onsps_rows=4,
        residual_rows=2,
        rocm_manifest_path=str(rocm),
        product_evidence_bundle_json_path=str(bundle_json),
    )

    assert report["status"] == "blocked_ai_md_engine_kpi_report"
    assert report["report_ready"] is False
    assert report["product_kpi"]["bundle_validation_pass"] is True
    assert report["product_kpi"]["source_artifacts_fresh"] is False
    assert report["product_kpi"]["source_artifact_stale_count"] == 1
    assert report["product_kpi"]["source_artifact_stale_ids"] == ["kpi_json"]
    assert report["pm_kpi_summary"]["product"]["source_artifacts_fresh"] is False
    assert "source_artifacts_fresh" in report["pm_kpi_summary"]["failed_gate_ids"]
    assert report["product_bundle_evidence_export_ready"] is False


def test_build_ai_md_engine_kpi_report_writes_artifacts(tmp_path: Path) -> None:
    out_json = tmp_path / "kpi.json"
    out_md = tmp_path / "kpi.md"
    runtime_plot = tmp_path / "runtime_scaling.svg"
    rocm = tmp_path / "rocm.json"
    bundle_json = _write_product_evidence_bundle(tmp_path / "bundle.json")
    _write_rocm_manifest(rocm, ready=True)

    rc = main(
        [
            "--score-only-rows",
            "4",
            "--onsps-rows",
            "4",
            "--residual-rows",
            "2",
            "--rocm-manifest-json",
            str(rocm),
            "--product-evidence-bundle-json",
            str(bundle_json),
            "--runtime-scaling-plot",
            str(runtime_plot),
            "--out-json",
            str(out_json),
            "--out-md",
            str(out_md),
        ]
    )

    assert rc == 0
    assert runtime_plot.exists()
    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["status"] == "ai_md_engine_kpi_report_ready"
    assert payload["runtime_kpi"]["neighbor_cap_scaling"]["plot_path"] == str(runtime_plot)
    assert payload["runtime_kpi"]["neighbor_cap_scaling"]["plot_ready"] is True
    md = out_md.read_text(encoding="utf-8")
    assert "Runtime KPI" in md
    assert "topology_invalid_rate" in md
    assert "backmapping_failure_rate" in md
    assert "hbond_recovery_pose_count" in md
    assert "unsatisfied_donor_acceptor_fixture_count" in md
    assert "Pose Ranking H-Bond Benchmark" in out_md.read_text(encoding="utf-8")

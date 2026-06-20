from __future__ import annotations

import json
import tarfile
from pathlib import Path

from tools.product import build_ai_md_product_evidence_bundle as mod


def _write(path: Path, payload: str = "artifact\n") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(payload, encoding="utf-8")
    return path


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
            "expected_blocked_reason": "",
            "hbond_claim_safe": True,
            "hbond_blocked_reason": "",
            "benchmark_contract_checks": {"claim_safe_matches": True},
            "benchmark_contract_pass": True,
        },
        {
            "pose_id": "ethanol_near_hbond_pose",
            "benchmark_role": "unsatisfied_donor_pose",
            "expected_claim_safe": False,
            "expected_blocked_reason": "missing_expected_anchor",
            "hbond_claim_safe": False,
            "hbond_blocked_reason": "missing_expected_anchor",
            "benchmark_contract_checks": {"claim_safe_matches": True},
            "benchmark_contract_pass": True,
        },
        {
            "pose_id": "amide_far_decoy_pose",
            "benchmark_role": "far_decoy_pose",
            "expected_claim_safe": False,
            "expected_blocked_reason": "missing_expected_anchor",
            "hbond_claim_safe": False,
            "hbond_blocked_reason": "missing_expected_anchor",
            "benchmark_contract_checks": {"claim_safe_matches": True},
            "benchmark_contract_pass": True,
        },
        {
            "pose_id": "amide_overanchored_decoy_pose",
            "benchmark_role": "overanchored_decoy_pose",
            "expected_claim_safe": False,
            "expected_blocked_reason": "overanchored_decoy",
            "hbond_claim_safe": False,
            "hbond_blocked_reason": "overanchored_decoy",
            "benchmark_contract_checks": {"claim_safe_matches": True},
            "benchmark_contract_pass": True,
        },
        {
            "pose_id": "invalid_ligand_pose",
            "benchmark_role": "invalid_ligand_pose",
            "expected_claim_safe": False,
            "expected_blocked_reason": "invalid_smiles",
            "hbond_claim_safe": False,
            "hbond_blocked_reason": "invalid_smiles",
            "benchmark_contract_checks": {"claim_safe_matches": True},
            "benchmark_contract_pass": True,
        },
    ] if pose_ranking_hbond_benchmark_ready else []
    pose_roles = sorted({str(row["benchmark_role"]) for row in pose_rows})
    return {
        "packet_type": "ai_md_engine_kpi_report",
        "status": "ai_md_engine_kpi_report_ready" if ready else "blocked_ai_md_engine_kpi_report",
        "report_ready": ready,
        "product_kpi": {
            "runner_claim_metadata_signed": runner_claim_metadata_signed,
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
            },
            "force_term_claim_metadata_ready": force_term_claim_metadata_ready,
            "force_term_claim_metadata_smoke": {
                "ready": force_term_claim_metadata_ready,
                "term_result_contract_ready": force_term_result_contract_ready,
                "forcefield_neighbor_diagnostics_ready": force_term_claim_metadata_ready,
                "forcefield_neighbor_pair_count": 6 if force_term_claim_metadata_ready else 0,
                "forcefield_neighbor_pairs_provided": False,
                "forcefield_neighbor_source": "full_neighbor_pairs"
                if force_term_claim_metadata_ready
                else "",
                "forcefield_claim_metadata_schema_version": "force_term_claim_metadata_v1"
                if force_term_claim_metadata_schema_ready
                else "",
                "forcefield_hbond_evidence_schema_version": "hbond_evidence_v1"
                if force_term_claim_metadata_schema_ready
                else "",
                "forcefield_claim_safe_count": len(force_term_rows),
                "forcefield_blocked_count": 0,
                "forcefield_claim_rows": force_term_rows,
                "term_result_contract_rows": force_term_contract_rows,
            },
            "force_term_result_contract_ready": force_term_result_contract_ready,
            "guarded_force_term_plugin_ready": guarded_force_term_plugin_ready,
            "guarded_force_term_plugin_smoke": {
                "ready": guarded_force_term_plugin_ready,
                "term": "screened_electrostatics",
                "claim_safe": guarded_force_term_plugin_ready,
                "force_term_status": "pass" if guarded_force_term_plugin_ready else "blocked",
                "missing_charge_blocked": guarded_force_term_plugin_ready,
                "unvalidated_charge_blocked": guarded_force_term_plugin_ready,
                "forcefield_claim_safe": guarded_force_term_plugin_ready,
                "finite_difference_force_error": 1e-7 if guarded_force_term_plugin_ready else 1.0,
                "policy_caps_ready": guarded_force_term_plugin_ready,
                "observed_caps_ready": guarded_force_term_plugin_ready,
                "bounded_correction_ready": guarded_force_term_plugin_ready,
                "policy_cap_exceeded_blocked": guarded_force_term_plugin_ready,
                "forcefield_bounded_row_ready": guarded_force_term_plugin_ready,
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
                } if guarded_force_term_plugin_ready else {},
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
            },
            "engine_topology_factory_facade_ready": True,
            "engine_topology_factory_facade_smoke": {
                "ready": True,
                "facade": "betelgeuze_engine.topology.TopologyFactoryFacade",
                "valid_claim_safe": True,
                "valid_topology_fidelity": "sequence_mapped",
                "valid_protein_residue_count": 3,
                "valid_protein_topology_valid": True,
                "valid_ligand_topology_schema_version": "ligand_topology_validity_v1",
                "placeholder_protein_residue_count": 3,
                "placeholder_protein_topology_valid": True,
                "placeholder_blocked_reason": "placeholder_alanine_topology",
                "empty_protein_residue_count": 0,
                "empty_protein_topology_valid": False,
                "empty_protein_blocked_reason": "empty_protein_topology",
                "invalid_ligand_blocked_reason": "invalid_smiles",
            },
            "core_forcefield_bridge_ready": core_forcefield_bridge_ready,
            "core_forcefield_bridge_smoke": {
                "ready": core_forcefield_bridge_ready,
                "result_claim_safe": core_forcefield_bridge_ready,
                "force_term_claim_metadata_ready": core_forcefield_bridge_ready,
                "force_term_plugins": ["legacy_lj"] if core_forcefield_bridge_ready else [],
                "energy_shape": [1] if core_forcefield_bridge_ready else [],
                "forces_shape": [1, 2, 3] if core_forcefield_bridge_ready else [],
                "neighbor_diagnostics_ready": core_forcefield_bridge_ready,
                "neighbor_pair_count": 2 if core_forcefield_bridge_ready else 0,
                "neighbor_pairs_provided": False,
                "neighbor_source": "full_neighbor_pairs" if core_forcefield_bridge_ready else "",
                "bridge_execution_scope": "metadata_contract_only_not_runtime_gpu_claim"
                if core_forcefield_bridge_ready
                else "",
            },
            "core_compatibility_layer_ready": core_compatibility_layer_ready,
            "core_compatibility_layer_smoke": {
                "ready": core_compatibility_layer_ready,
                "contract_scope": "legacy_core_import_paths_are_compatibility_layer_not_runtime_gpu_claim",
                "row_count": 3 if core_compatibility_layer_ready else 0,
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
                        "contract": "forcefield_product_bridge",
                        "ready": core_compatibility_layer_ready,
                        "legacy_module": "core.forcefield",
                        "canonical_module": "betelgeuze_engine.physics",
                        "bridge_type": "energy_forces_claim_metadata_bridge",
                        "result_claim_safe": core_compatibility_layer_ready,
                        "force_term_claim_metadata_ready": core_compatibility_layer_ready,
                        "force_term_plugins": ["legacy_lj"] if core_compatibility_layer_ready else [],
                        "neighbor_diagnostics_ready": core_compatibility_layer_ready,
                        "neighbor_pair_count": 2 if core_compatibility_layer_ready else 0,
                        "neighbor_pairs_provided": False,
                        "neighbor_source": "full_neighbor_pairs" if core_compatibility_layer_ready else "",
                        "error": "",
                    },
                ] if core_compatibility_layer_ready else [],
            },
            "job_store_lazy_factory_ready": job_store_lazy_factory_ready,
            "job_store_lazy_factory_smoke": {"ready": job_store_lazy_factory_ready},
            "allowlisted_runner_shim_contract_ready": allowlisted_runner_shim_contract_ready,
            "allowlisted_runner_shim_contract": {
                "ready": allowlisted_runner_shim_contract_ready,
                "runner_count": 3 if allowlisted_runner_shim_contract_ready else 0,
                "rows": [
                    {
                        "profile_id": "ligand_htvs_pipeline_default",
                        "runner_script": "tools/run_ligand_htvs_pipeline.py",
                        "adapter_import": "betelgeuze_engine.product.runners.htvs_pipeline",
                        "shim_contract_type": "canonical_module_alias",
                        "sys_modules_alias_ready": True,
                        "self_implementation_blocked": True,
                        "runtime_adapter_identity_ready": True,
                        "missing_runtime_symbols": [],
                        "runtime_adapter_error": "",
                        "ready": True,
                    },
                    {
                        "profile_id": "backmapping_scoring.production",
                        "runner_script": "tools/run_ligand_backmapping_scoring.py",
                        "adapter_import": "betelgeuze_engine.product.runners.backmapping_scoring",
                        "shim_contract_type": "canonical_module_alias",
                        "sys_modules_alias_ready": True,
                        "self_implementation_blocked": True,
                        "runtime_adapter_identity_ready": True,
                        "missing_runtime_symbols": [],
                        "runtime_adapter_error": "",
                        "ready": True,
                    },
                    {
                        "profile_id": "ligand_topk_delivery.production",
                        "runner_script": "tools/run_ligand_topk_delivery.py",
                        "adapter_import": "betelgeuze_engine.product.runners.topk_delivery",
                        "shim_contract_type": "canonical_module_alias",
                        "sys_modules_alias_ready": True,
                        "self_implementation_blocked": True,
                        "runtime_adapter_identity_ready": True,
                        "missing_runtime_symbols": [],
                        "runtime_adapter_error": "",
                        "ready": True,
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
            "overanchored_decoys_blocked": pose_ranking_hbond_benchmark_ready,
            "unsatisfied_donor_acceptor_detected": pose_ranking_hbond_benchmark_ready,
            "required_pose_roles": [
                "far_decoy_pose",
                "hbond_recovery_pose",
                "invalid_ligand_pose",
                "overanchored_decoy_pose",
                "unsatisfied_donor_pose",
            ],
            "observed_pose_roles": pose_roles,
            "row_contracts_ready": pose_ranking_hbond_benchmark_ready,
            "row_contract_pass_count": len(pose_rows),
            "rows": pose_rows,
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
                "bounded_correction_policy_ready": force_residual_bounded_policy_ready,
                "observed_caps_ready": force_residual_observed_caps_ready,
                "confidence_abstention_ready": force_residual_confidence_abstention_ready,
                "top_k_policy_ready": True,
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
                "forcefield_neighbor_source": "provided",
                "forcefield_neighbor_pairs_provided": True,
                "engine_neighbor_diagnostics_ready": True,
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
        },
        "pm_kpi_summary": {
            "summary_ready": ready,
            "failed_gate_ids": [] if ready else ["clean_install_success"],
            "runtime": {
                "score_only_1k_runtime_tracked": True,
                "top100_4bead_rescoring_runtime_tracked": True,
                "top10_force_residual_runtime_tracked": True,
                "memory_peak_tracked": True,
                "neighbor_list_rebuild_frequency_tracked": True,
                "force_residual_bounded_policy_ready": force_residual_bounded_policy_ready,
                "force_residual_observed_caps_ready": force_residual_observed_caps_ready,
                "force_residual_confidence_abstention_ready": force_residual_confidence_abstention_ready,
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
                "runner_profile_validation_pass": ready,
                "force_term_claim_metadata_ready": force_term_claim_metadata_ready,
                "force_term_result_contract_ready": force_term_result_contract_ready,
                "guarded_force_term_plugin_ready": guarded_force_term_plugin_ready,
                "onsps_backmap_evidence_schema_ready": onsps_backmap_evidence_schema_ready,
                "engine_topology_factory_facade_ready": True,
                "core_forcefield_bridge_ready": core_forcefield_bridge_ready,
                "core_compatibility_layer_ready": core_compatibility_layer_ready,
                "job_store_lazy_factory_ready": job_store_lazy_factory_ready,
                "allowlisted_runner_shim_contract_ready": allowlisted_runner_shim_contract_ready,
                "blocked_claim_correctly_blocked": True,
            },
            "chemistry": {
                "hbond_evidence_schema_ready": chemistry_pm_gates_ready,
                "ligand_topology_validity_schema_ready": chemistry_pm_gates_ready,
                "hbond_recovery_pose_count": 1 if chemistry_pm_gates_ready else 0,
                "hbond_recovery_pose_ids": ["amide_near_hbond_pose"] if chemistry_pm_gates_ready else [],
                "unsatisfied_donor_acceptor_detection": chemistry_pm_gates_ready,
                "overanchored_decoy_rejection": chemistry_pm_gates_ready,
                "chirality_preservation_ready": chemistry_pm_gates_ready,
                "ring_validity_ready": chemistry_pm_gates_ready,
                "tautomer_validity_ready": chemistry_pm_gates_ready,
                "protonation_validity_ready": chemistry_pm_gates_ready,
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

    payload = mod.build_payload(
        kpi_packet=_kpi_packet(ready=True),
        rocm_manifest_packet=_rocm_packet(ready=True),
        product_image_preflight_packet=_image_preflight_packet(clean_ready=True),
        artifact_specs=_artifact_specs(tmp_path),
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
    assert summary["guarded_force_term_plugin_ready"] is True
    assert summary["onsps_backmap_evidence_schema_ready"] is True
    assert summary["core_forcefield_bridge_ready"] is True
    assert summary["core_compatibility_layer_ready"] is True
    assert summary["job_store_lazy_factory_ready"] is True
    assert summary["allowlisted_runner_shim_contract_ready"] is True
    assert summary["chemistry_pm_gates_ready"] is True
    assert summary["pose_ranking_hbond_benchmark_ready"] is True
    assert summary["pose_ranking_hbond_row_contracts_ready"] is True
    assert summary["pose_ranking_hbond_row_contract_pass_count"] == 5
    assert summary["hbond_recovery_pose_count"] == 1
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
    kpi_packet["product_kpi"]["engine_topology_factory_facade_smoke"][
        "empty_protein_blocked_reason"
    ] = ""

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
        error.startswith("kpi_allowlisted_runner_shim_contract_rows_invalid:")
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
        error.startswith("pm_overanchored_decoy_rejection_gate_missing:")
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
    kpi_json = _write(tmp_path / "kpi.json", json.dumps(_kpi_packet(ready=True)))
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

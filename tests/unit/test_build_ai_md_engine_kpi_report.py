from __future__ import annotations

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


def _write_product_evidence_bundle(
    path: Path,
    *,
    ready: bool = True,
    clean_ready: bool = True,
) -> Path:
    root = path.parent
    out_tar = root / "bundle.tar.gz"
    kpi_packet = {
        "packet_type": "ai_md_engine_kpi_report",
        "status": "ai_md_engine_kpi_report_ready" if ready else "blocked_ai_md_engine_kpi_report",
        "report_ready": ready,
        "product_kpi": {
            "runner_claim_metadata_signed": True,
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
            },
            "force_term_claim_metadata_ready": True,
            "force_term_claim_metadata_smoke": {
                "ready": True,
                "term_result_contract_ready": True,
                "forcefield_neighbor_diagnostics_ready": True,
                "forcefield_neighbor_pair_count": 6,
                "forcefield_neighbor_pairs_provided": False,
                "forcefield_neighbor_source": "full_neighbor_pairs",
                "forcefield_claim_metadata_schema_version": "force_term_claim_metadata_v1",
                "forcefield_hbond_evidence_schema_version": "hbond_evidence_v1",
                "forcefield_claim_safe_count": 3,
                "forcefield_blocked_count": 0,
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
                    },
                    {
                        "force_term_name": "legacy_lj",
                        "force_term_status": "pass",
                        "claim_safe": True,
                        "blocked_reason": "",
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
            "guarded_force_term_plugin_ready": True,
            "guarded_force_term_plugin_smoke": {
                "ready": True,
                "term": "screened_electrostatics",
                "claim_safe": True,
                "force_term_status": "pass",
                "missing_charge_blocked": True,
                "unvalidated_charge_blocked": True,
                "forcefield_claim_safe": True,
                "finite_difference_force_error": 1e-7,
                "policy_caps_ready": True,
                "observed_caps_ready": True,
                "bounded_correction_ready": True,
                "policy_cap_exceeded_blocked": True,
                "forcefield_bounded_row_ready": True,
                "forcefield_guarded_claim_row": {
                    "force_term_name": "screened_electrostatics",
                    "policy_caps_ready": True,
                    "observed_caps_ready": True,
                    "bounded_correction_ready": True,
                },
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
            "core_forcefield_bridge_ready": True,
            "core_forcefield_bridge_smoke": {
                "ready": True,
                "result_claim_safe": True,
                "force_term_claim_metadata_ready": True,
                "force_term_plugins": ["legacy_lj"],
                "energy_shape": [1],
                "forces_shape": [1, 2, 3],
                "neighbor_diagnostics_ready": True,
                "neighbor_pair_count": 2,
                "neighbor_pairs_provided": False,
                "neighbor_source": "full_neighbor_pairs",
                "bridge_execution_scope": "metadata_contract_only_not_runtime_gpu_claim",
            },
            "core_compatibility_layer_ready": True,
            "core_compatibility_layer_smoke": {
                "ready": True,
                "contract_scope": "legacy_core_import_paths_are_compatibility_layer_not_runtime_gpu_claim",
                "row_count": 3,
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
                        "contract": "forcefield_product_bridge",
                        "ready": True,
                        "legacy_module": "core.forcefield",
                        "canonical_module": "betelgeuze_engine.physics",
                        "bridge_type": "energy_forces_claim_metadata_bridge",
                        "result_claim_safe": True,
                        "force_term_claim_metadata_ready": True,
                        "force_term_plugins": ["legacy_lj"],
                        "neighbor_diagnostics_ready": True,
                        "neighbor_pair_count": 2,
                        "neighbor_pairs_provided": False,
                        "neighbor_source": "full_neighbor_pairs",
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
                ],
            },
            "blocked_claim_correctly_blocked": True,
        },
        "pose_ranking_hbond_benchmark": {
            "benchmark_ready": True,
            "top1_pose_id": "amide_near_hbond_pose",
            "top1_expected_pose_id": "amide_near_hbond_pose",
            "hbond_recovery_pose_count": 1,
            "hbond_recovery_pose_ids": ["amide_near_hbond_pose"],
            "overanchored_decoys_blocked": True,
            "unsatisfied_donor_acceptor_detected": True,
            "required_pose_roles": [
                "far_decoy_pose",
                "hbond_recovery_pose",
                "invalid_ligand_pose",
                "overanchored_decoy_pose",
                "unsatisfied_donor_pose",
            ],
            "observed_pose_roles": [
                "far_decoy_pose",
                "hbond_recovery_pose",
                "invalid_ligand_pose",
                "overanchored_decoy_pose",
                "unsatisfied_donor_pose",
            ],
            "row_contracts_ready": True,
            "row_contract_pass_count": 5,
            "rows": [
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
            ],
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
                "confidence_abstention_ready": True,
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
            "force_term_physics_validation_ready": True,
            "force_term_physics_validation_claim_safe_ready": True,
        },
        "pm_kpi_summary": {
            "runtime": {
                "score_only_1k_runtime_tracked": True,
                "top100_4bead_rescoring_runtime_tracked": True,
                "top10_force_residual_runtime_tracked": True,
                "memory_peak_tracked": True,
                "neighbor_list_rebuild_frequency_tracked": True,
                "force_residual_bounded_policy_ready": True,
                "force_residual_observed_caps_ready": True,
                "force_residual_confidence_abstention_ready": True,
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
                "runner_profile_validation_pass": True,
                "force_term_claim_metadata_ready": True,
                "force_term_result_contract_ready": True,
                "guarded_force_term_plugin_ready": True,
                "onsps_backmap_evidence_schema_ready": True,
                "engine_topology_factory_facade_ready": True,
                "core_forcefield_bridge_ready": True,
                "core_compatibility_layer_ready": True,
                "job_store_lazy_factory_ready": True,
                "allowlisted_runner_shim_contract_ready": True,
                "blocked_claim_correctly_blocked": True,
            },
            "chemistry": {
                "hbond_evidence_schema_ready": True,
                "ligand_topology_validity_schema_ready": True,
                "hbond_recovery_pose_count": 1,
                "hbond_recovery_pose_ids": ["amide_near_hbond_pose"],
                "unsatisfied_donor_acceptor_detection": True,
                "overanchored_decoy_rejection": True,
                "chirality_preservation_ready": True,
                "ring_validity_ready": True,
                "tautomer_validity_ready": True,
                "protonation_validity_ready": True,
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
        artifact_specs=specs,
        out_tar=str(out_tar),
    )
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def test_build_ai_md_engine_kpi_report_contract(tmp_path: Path) -> None:
    rocm = tmp_path / "rocm.json"
    bundle_json = _write_product_evidence_bundle(tmp_path / "bundle.json")
    _write_rocm_manifest(rocm, ready=True)
    report = build_report(
        profiles_dir="config/api_validated_runner_profiles",
        score_only_rows=8,
        onsps_rows=7,
        residual_rows=3,
        rocm_manifest_path=str(rocm),
        product_evidence_bundle_json_path=str(bundle_json),
    )

    assert report["packet_type"] == "ai_md_engine_kpi_report"
    assert report["status"] == "ai_md_engine_kpi_report_ready"
    assert report["pm_kpi_summary"]["summary_ready"] is True
    assert report["report_ready"] == report["pm_kpi_summary"]["summary_ready"]
    assert report["pm_kpi_summary"]["failed_gate_ids"] == []
    assert report["pm_kpi_summary"]["product"]["clean_install_success"] is True
    assert report["product_kpi"]["runner_profile_validation_status"] == "pass"
    assert report["product_kpi"]["clean_install_success"] is True
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
    assert report["product_kpi"]["guarded_force_term_plugin_ready"] is True
    assert report["pm_kpi_summary"]["product"]["guarded_force_term_plugin_ready"] is True
    assert report["product_kpi"]["engine_topology_factory_facade_ready"] is True
    assert report["pm_kpi_summary"]["product"]["engine_topology_factory_facade_ready"] is True
    topology_factory_smoke = report["product_kpi"]["engine_topology_factory_facade_smoke"]
    assert topology_factory_smoke["facade"] == "betelgeuze_engine.topology.TopologyFactoryFacade"
    assert topology_factory_smoke["valid_claim_safe"] is True
    assert topology_factory_smoke["valid_protein_residue_count"] == 3
    assert topology_factory_smoke["valid_protein_topology_valid"] is True
    assert topology_factory_smoke["valid_ligand_topology_schema_version"] == "ligand_topology_validity_v1"
    assert topology_factory_smoke["placeholder_protein_residue_count"] == 3
    assert topology_factory_smoke["placeholder_protein_topology_valid"] is True
    assert topology_factory_smoke["placeholder_blocked_reason"] == "placeholder_alanine_topology"
    assert topology_factory_smoke["empty_protein_residue_count"] == 0
    assert topology_factory_smoke["empty_protein_topology_valid"] is False
    assert topology_factory_smoke["empty_protein_blocked_reason"] == "empty_protein_topology"
    assert topology_factory_smoke["invalid_ligand_blocked_reason"] == "invalid_smiles"
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
        "screened_electrostatics",
    ]
    assert guarded_plugin["term"] == "screened_electrostatics"
    assert guarded_plugin["claim_safe"] is True
    assert guarded_plugin["force_term_status"] == "pass"
    assert guarded_plugin["missing_charge_blocked"] is True
    assert guarded_plugin["unvalidated_charge_blocked"] is True
    assert guarded_plugin["forcefield_claim_safe"] is True
    assert guarded_plugin["finite_difference_force_error"] < 1e-5
    assert guarded_plugin["policy_caps_ready"] is True
    assert guarded_plugin["observed_caps_ready"] is True
    assert guarded_plugin["bounded_correction_ready"] is True
    assert guarded_plugin["policy_cap_exceeded_blocked"] is True
    assert guarded_plugin["forcefield_bounded_row_ready"] is True
    assert guarded_plugin["forcefield_guarded_claim_row"]["force_term_name"] == "screened_electrostatics"
    assert guarded_plugin["forcefield_guarded_claim_row"]["policy_caps_ready"] is True
    assert guarded_plugin["forcefield_guarded_claim_row"]["observed_caps_ready"] is True
    assert guarded_plugin["forcefield_guarded_claim_row"]["bounded_correction_ready"] is True
    assert guarded_plugin["abs_energy_within_cap"] is True
    assert guarded_plugin["force_norm_within_cap"] is True
    assert guarded_plugin["active_pair_count_within_cap"] is True
    assert guarded_plugin["policy_caps"]["max_abs_energy"] == 50.0
    assert guarded_plugin["policy_caps"]["max_force_norm"] == 25.0
    assert guarded_plugin["observed_abs_energy"] > 0.0
    assert guarded_plugin["observed_force_norm"] > 0.0
    force_term_smoke = report["product_kpi"]["force_term_claim_metadata_smoke"]
    assert force_term_smoke["forcefield_claim_safe"] is True
    assert force_term_smoke["forcefield_blocked_reason"] == ""
    assert force_term_smoke["forcefield_hbond_evidence_status"] == "pass"
    assert force_term_smoke["forcefield_hbond_evidence_schema_version"] == "hbond_evidence_v1"
    assert force_term_smoke["forcefield_claim_metadata_schema_version"] == "force_term_claim_metadata_v1"
    assert force_term_smoke["forcefield_neighbor_diagnostics_ready"] is True
    assert force_term_smoke["forcefield_neighbor_pair_count"] > 0
    assert force_term_smoke["forcefield_neighbor_pairs_provided"] is False
    assert force_term_smoke["forcefield_neighbor_source"] == "full_neighbor_pairs"
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
    assert core_bridge_smoke["neighbor_diagnostics_ready"] is True
    assert core_bridge_smoke["neighbor_pair_count"] > 0
    assert core_bridge_smoke["neighbor_pairs_provided"] is False
    assert core_bridge_smoke["neighbor_source"] == "full_neighbor_pairs"
    assert report["product_kpi"]["core_compatibility_layer_ready"] is True
    assert report["pm_kpi_summary"]["product"]["core_compatibility_layer_ready"] is True
    core_compatibility = report["product_kpi"]["core_compatibility_layer_smoke"]
    assert core_compatibility["ready"] is True
    assert core_compatibility["row_count"] == 3
    assert {
        row["contract"] for row in core_compatibility["rows"]
    } == {
        "onsps_backmap_shim",
        "topology_protein_bridge",
        "forcefield_product_bridge",
    }
    assert all(row["ready"] is True for row in core_compatibility["rows"])
    forcefield_compat = next(
        row for row in core_compatibility["rows"] if row["contract"] == "forcefield_product_bridge"
    )
    assert forcefield_compat["neighbor_diagnostics_ready"] is True
    assert forcefield_compat["neighbor_pair_count"] > 0
    assert forcefield_compat["neighbor_pairs_provided"] is False
    assert forcefield_compat["neighbor_source"] == "full_neighbor_pairs"
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
    residual_kpi = report["runtime_kpi"]["top10_force_residual"]
    assert residual_kpi["applied_count"] == 3
    assert residual_kpi["delta_score_cap_abstention_count"] == 1
    assert residual_kpi["uncertainty_abstention_count"] == 1
    assert residual_kpi["outside_top_k_abstention_count"] == 1
    assert residual_kpi["bounded_correction_policy_ready"] is True
    assert residual_kpi["observed_caps_ready"] is True
    assert residual_kpi["confidence_abstention_ready"] is True
    assert residual_kpi["top_k_policy_ready"] is True
    assert report["pm_kpi_summary"]["runtime"]["force_residual_bounded_policy_ready"] is True
    assert report["pm_kpi_summary"]["runtime"]["force_residual_observed_caps_ready"] is True
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
    assert residual_kpi["outside_top_k_report"]["skipped_reason"] == "outside_top_k_policy"
    assert residual_kpi["outside_top_k_report"]["rank_pct"] > residual_kpi["outside_top_k_report"]["policy_caps"]["top_k_rank_pct"]
    assert residual_kpi["outside_top_k_report"]["top_k_eligible"] is False
    assert residual_kpi["outside_top_k_report"]["policy_caps"]["top_k_rank_pct"] == 0.05
    assert report["runtime_kpi"]["memory_peak_mb"] > 0
    assert report["runtime_kpi"]["neighbor_list_rebuild"]["neighbor_list_rebuild_count"] > 0
    assert report["runtime_kpi"]["neighbor_list_rebuild"]["neighbor_list_rebuild_frequency"] > 0
    assert report["runtime_kpi"]["neighbor_list_rebuild"]["engine_neighbor_diagnostics_ready"] is True
    assert report["runtime_kpi"]["neighbor_list_rebuild"]["forcefield_neighbor_pairs_provided"] is True
    assert report["runtime_kpi"]["neighbor_list_rebuild"]["forcefield_neighbor_source"] == "provided"
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
    assert report["pm_kpi_summary"]["chemistry"]["hbond_recovery_pose_count"] >= 1
    assert report["pm_kpi_summary"]["chemistry"]["hbond_recovery_confidence_min"] >= 0.5
    assert report["pm_kpi_summary"]["chemistry"]["hbond_recovery_pose_ids"] == ["amide_near_hbond_pose"]
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
    assert report["pose_ranking_hbond_benchmark"]["invalid_ligand_blocked"] is True
    assert report["pose_ranking_hbond_benchmark"]["overanchored_decoys_blocked"] is True
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
    assert overanchored_pose["hbond_geometry_evaluated"] is True
    assert overanchored_pose["hbond_geometry_complete"] is True
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
    assert report["product_kpi"]["clean_container_missing_requirement_count"] == 13
    assert "container_runtime_receipt_ready" in report["product_kpi"]["clean_container_missing_requirements"]
    assert "backmapping_hbond_evidence_receipt_ready" in report["product_kpi"]["clean_container_missing_requirements"]
    assert report["pm_kpi_summary"]["product"]["clean_install_missing_requirements"] == [
        "clean_container_smoke_ready",
        "product_runner_smoke_ready",
        "product_image_receipt_present",
        "product_image_receipt_mode_rocm_runtime",
    ]
    assert report["pm_kpi_summary"]["product"]["clean_container_missing_requirement_count"] == 13
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
            "--out-json",
            str(out_json),
            "--out-md",
            str(out_md),
        ]
    )

    assert rc == 0
    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["status"] == "ai_md_engine_kpi_report_ready"
    md = out_md.read_text(encoding="utf-8")
    assert "Runtime KPI" in md
    assert "topology_invalid_rate" in md
    assert "backmapping_failure_rate" in md
    assert "hbond_recovery_pose_count" in md
    assert "unsatisfied_donor_acceptor_fixture_count" in md
    assert "Pose Ranking H-Bond Benchmark" in out_md.read_text(encoding="utf-8")

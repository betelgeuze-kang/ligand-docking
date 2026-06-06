from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")


def write_capability_prerequisite_packets(runs_dir: Path) -> None:
    _write(
        runs_dir / "product_scope_breadth_contract_current.json",
        {
            "summary": {
                "status": "product_scope_breadth_contract_ready",
                "allowed_scope_families": ["gpcr", "ion_channel", "kinase"],
                "blocked_claim_scopes": [
                    "transporter_domain_promotion",
                    "general_protein_ligand_platform",
                ],
                "general_platform_claim_allowed": False,
            }
        },
    )
    _write(
        runs_dir / "product_readiness_gate_current.json",
        {
            "summary": {
                "status": "product_handoff_ready",
                "target_id": "ADRB2",
                "family": "gpcr",
                "ligand_count": 3,
                "request_contract_status": "pass",
                "execution_enabled": False,
                "docking_results_emitted": False,
                "external_state_mutated": False,
            }
        },
    )
    _write(
        runs_dir / "product_execution_work_order_current.json",
        {
            "summary": {
                "status": "product_execution_work_order_ready",
                "execution_enabled": False,
                "docking_results_emitted": False,
                "external_state_mutated": False,
            }
        },
    )
    _write(
        runs_dir / "product_execution_preflight_current.json",
        {
            "summary": {
                "status": "product_execution_preflight_ready",
                "unknown_arg_count": 0,
                "config_count": 1,
                "execution_enabled": False,
                "docking_results_emitted": False,
                "external_state_mutated": False,
            }
        },
    )
    _write(
        runs_dir / "product_structure_analysis_report_current.json",
        {
            "summary": {
                "status": "product_structure_analysis_report_ready",
                "local_structure_parsed": True,
                "atom_count": 42,
                "ligand_like_residue_count": 1,
                "execution_enabled": False,
                "docking_results_emitted": False,
                "external_state_mutated": False,
            }
        },
    )
    _write(
        runs_dir / "product_bundle_contract_current.json",
        {
            "summary": {
                "status": "product_bundle_contract_ready",
                "bundle_parser_status": "parsed",
                "bundle_unknown_arg_count": 0,
                "expected_bundle_dir": "runs/local_delivery/bundle_product_gpcr_adrb2",
                "artifact_count": 1,
                "bundle_validation_command_matches": True,
                "execution_enabled": False,
                "docking_results_emitted": False,
                "external_state_mutated": False,
            },
            "bundle_command_check": {
                "parsed_args": {
                    "rerun_command": "python3 tools/run_ligand_htvs_pipeline.py --out-prefix runs/product_gpcr_adrb2_after_approval"
                }
            },
            "planned_artifact_checks": [{"path": "runs/product_gpcr_adrb2_after_approval_summary.json"}],
        },
    )
    _write(
        runs_dir / "product_delivery_evidence_contract_current.json",
        {
            "summary": {
                "status": "product_delivery_evidence_contract_ready",
                "delivery_ready_claim_allowed": False,
                "execution_enabled": False,
                "docking_results_emitted": False,
                "external_state_mutated": False,
            }
        },
    )
    write_license_packets(runs_dir)
    _write(
        runs_dir / "independent_engine_roadmap_status_current.json",
        {
            "summary": {
                "status": "independent_engine_roadmap_closed",
                "phases": {
                    "E0": "closed",
                    "E1": "closed",
                    "E2": "closed",
                    "E3": "closed",
                    "E4": "closed",
                    "E5": "closed",
                },
                "scoring_ranking_contract_ready": True,
                "engine_dispatch_ready": True,
            }
        },
    )
    _write(
        runs_dir / "product_pilot_packet_contract_current.json",
        {
            "summary": {
                "status": "product_pilot_packet_preflight_ready",
                "pilot_delivery_ready": False,
                "execution_enabled": False,
                "docking_results_emitted": False,
                "external_state_mutated": False,
            }
        },
    )
    write_production_ai_checkpoint_fixture_packets(runs_dir)
    write_claim_expansion_gate_scaffolds(runs_dir)
    write_data_science_expansion_closure_packets(runs_dir)


def write_production_ai_checkpoint_fixture_packets(runs_dir: Path) -> None:
    _write(
        runs_dir / "residual_model_registry_current.json",
        {
            "summary": {
                "status": "residual_model_registry_ready",
                "default_residual_mode": "production_guarded",
                "production_promotion_allowed": True,
                "families": ["gpcr", "kinase", "ion_channel"],
            },
            "components": {
                "stage_router": {"output": "stage2_route_decision", "ready": True},
                "score_residual": {"mode": "production_guarded", "ready": True},
            },
        },
    )
    _write(
        runs_dir / "product_production_ai_checkpoint_readiness_current.json",
        {
            "summary": {
                "status": "product_production_ai_checkpoint_readiness_ready",
                "checkpoint_chain_ready": True,
                "production_guarded_residual_ready": True,
                "execution_enabled": False,
                "docking_results_emitted": False,
            }
        },
    )
    _write(
        runs_dir / "residual_production_checkpoint_preflight_current.json",
        {
            "summary": {
                "status": "residual_production_checkpoint_preflight_ready",
                "promotion_mode": "production_guarded",
                "preflight_green": True,
                "execution_enabled": False,
            }
        },
    )
    _write(
        runs_dir / "residual_production_training_data_contract_current.json",
        {
            "summary": {
                "status": "residual_production_training_data_contract_ready",
                "training_data_contract_ready": True,
                "gpu_return_receipt_ready": True,
            }
        },
    )


def write_claim_expansion_gate_scaffolds(runs_dir: Path) -> None:
    _write(
        runs_dir / "cameo_claim_boundary_expansion_scaffold_current.json",
        {
            "summary": {
                "status": "cameo_claim_boundary_scaffold_ready",
                "official_results_claim_allowed": False,
                "receiver_smoke_ready": True,
                "expansion_stage": "scaffold_ready",
            }
        },
    )
    _write(
        runs_dir / "ca2_claim_boundary_expansion_scaffold_current.json",
        {
            "summary": {
                "status": "ca2_claim_boundary_scaffold_ready",
                "packet_replacement_ready": True,
                "review_policy_closure_ready": True,
                "expansion_stage": "closure_ready",
            }
        },
    )
    _write(
        runs_dir / "pxr_claim_boundary_expansion_scaffold_current.json",
        {
            "summary": {
                "status": "pxr_claim_boundary_scaffold_ready",
                "blocked_row_count": 0,
                "ready_row_count": 14,
                "expansion_stage": "closure_ready",
            }
        },
    )
    _write(
        runs_dir / "transporter_claim_boundary_expansion_scaffold_current.json",
        {
            "summary": {
                "status": "transporter_claim_boundary_scaffold_ready",
                "direct_binding_kcal_claim_allowed": False,
                "binder_promotion_gate_ready": True,
                "curated_packet_ready": True,
                "expansion_stage": "closure_ready",
            }
        },
    )


def write_data_science_expansion_closure_packets(runs_dir: Path) -> None:
    _write(
        runs_dir / "gpcr_residual_proof_breadth_gate_current.json",
        {
            "summary": {
                "status": "gpcr_residual_proof_breadth_gate_ready",
                "gpcr_residual_proof_breadth_gate_ready": True,
                "effective_gpcr_breadth_count": 7,
                "pr_auc_regression_warning_count": 0,
            }
        },
    )
    _write(
        runs_dir / "idp_broader_promotion_resolution_current.json",
        {
            "summary": {
                "status": "idp_broader_promotion_resolution_ready",
                "wider_shadow_safe_lane_admitted": True,
                "bounded_lane_closure_ready": True,
                "broader_full_idp_promotion_blocked": True,
            }
        },
    )
    _write(
        runs_dir / "ca2_packet_replacement_readiness_current.json",
        {
            "summary": {
                "status": "ca2_packet_replacement_readiness_ready",
                "ready_row_count": 12,
                "blocked_row_count": 0,
            }
        },
    )
    _write(
        runs_dir / "pxr_packet_replacement_readiness_current.json",
        {
            "summary": {
                "status": "pxr_packet_replacement_readiness_ready",
                "ready_row_count": 14,
                "blocked_row_count": 0,
            }
        },
    )
    _write(
        runs_dir / "transporter_membrane_readiness_current.json",
        {
            "summary": {
                "status": "transporter_membrane_readiness_ready",
                "p0_open_count": 0,
                "curated_packet_ready": True,
            }
        },
    )
    _write(
        runs_dir / "accuracy_parity_scorecard_current.json",
        {
            "summary": {
                "status": "green",
                "pass_row_count": 5,
                "row_count": 5,
            }
        },
    )


def write_license_packets(runs_dir: Path) -> None:
    _write(
        runs_dir / "product_license_decision_gate_current.json",
        {
            "summary": {
                "status": "product_license_decision_gate_ready",
                "authorized_for_license_file_creation_review": True,
                "spdx_license_id": "ProprietaryRef-Betelgeuze",
                "license_text_source": "LICENSE",
                "copyright_holder": "JIHOON KANG",
                "effective_year": "2026",
            }
        },
    )
    _write(
        runs_dir / "product_license_file_creation_work_order_current.json",
        {
            "summary": {
                "status": "product_license_file_creation_work_order_ready",
                "license_review_manifest_ready": True,
                "spdx_license_id": "ProprietaryRef-Betelgeuze",
                "license_text_source": "LICENSE",
                "copyright_holder": "JIHOON KANG",
                "effective_year": "2026",
            }
        },
    )
    _write(
        runs_dir / "product_commercial_independence_gate_current.json",
        {
            "summary": {
                "status": "product_commercial_independence_gate_ready",
                "license_present": True,
                "commercial_independent_product_claim_allowed": True,
            }
        },
    )
    _write(
        runs_dir / "third_party_license_review_gate_current.json",
        {
            "summary": {
                "status": "third_party_license_review_gate_ready",
                "blocker_count": 0,
                "legal_advice_provided": False,
                "asset_modified": False,
                "external_state_mutated": False,
            }
        },
    )

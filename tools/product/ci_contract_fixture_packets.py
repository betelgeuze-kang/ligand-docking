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

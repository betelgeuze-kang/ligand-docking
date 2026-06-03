from __future__ import annotations

import json
from pathlib import Path

from tools import build_product_pilot_packet_contract as mod


def _readiness() -> dict:
    return {
        "summary": {
            "status": "product_handoff_ready",
            "target_id": "ADRB2",
            "family": "gpcr",
            "ligand_count": 1,
            "execution_approval_token_required": "APPROVE_PRODUCT_DOCKING_EXECUTION",
        }
    }


def _preflight() -> dict:
    return {
        "summary": {
            "status": "product_execution_preflight_ready",
            "approval_token_required": "APPROVE_PRODUCT_DOCKING_EXECUTION",
            "execution_enabled": False,
            "docking_results_emitted": False,
            "external_state_mutated": False,
        }
    }


def _bundle_contract(tmp_path: Path) -> dict:
    return {
        "summary": {
            "status": "product_bundle_contract_ready",
            "target_id": "ADRB2",
            "family": "gpcr",
            "ligand_count": 1,
            "expected_bundle_dir": str(tmp_path / "runs" / "local_delivery" / "bundle_product_gpcr_adrb2"),
            "bundle_assembled": False,
            "execution_enabled": False,
            "docking_results_emitted": False,
            "external_state_mutated": False,
        }
    }


def _delivery_evidence() -> dict:
    return {
        "summary": {
            "status": "product_delivery_evidence_contract_ready",
            "delivery_ready_claim_allowed": False,
            "execution_enabled": False,
            "docking_results_emitted": False,
            "external_state_mutated": False,
        }
    }


def test_build_product_pilot_packet_contract_tool_writes_outputs(tmp_path: Path) -> None:
    paths = {
        "readiness": tmp_path / "readiness.json",
        "preflight": tmp_path / "preflight.json",
        "bundle_contract": tmp_path / "bundle_contract.json",
        "delivery_evidence": tmp_path / "delivery_evidence.json",
    }
    paths["readiness"].write_text(json.dumps(_readiness()) + "\n", encoding="utf-8")
    paths["preflight"].write_text(json.dumps(_preflight()) + "\n", encoding="utf-8")
    paths["bundle_contract"].write_text(json.dumps(_bundle_contract(tmp_path)) + "\n", encoding="utf-8")
    paths["delivery_evidence"].write_text(json.dumps(_delivery_evidence()) + "\n", encoding="utf-8")
    out_json = tmp_path / "pilot_packet.json"
    out_csv = tmp_path / "pilot_packet.csv"
    out_md = tmp_path / "pilot_packet.md"

    mod.main(
        [
            "--product-readiness-json",
            str(paths["readiness"]),
            "--product-preflight-json",
            str(paths["preflight"]),
            "--product-bundle-contract-json",
            str(paths["bundle_contract"]),
            "--product-delivery-evidence-json",
            str(paths["delivery_evidence"]),
            "--bundle-validation-json",
            str(tmp_path / "missing_validation.json"),
            "--root",
            str(tmp_path),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ]
    )

    assert json.loads(out_json.read_text(encoding="utf-8"))["summary"]["status"] == "product_pilot_packet_preflight_ready"
    assert out_csv.read_text(encoding="utf-8").startswith("check,status,")
    assert "Product Pilot Packet Contract" in out_md.read_text(encoding="utf-8")

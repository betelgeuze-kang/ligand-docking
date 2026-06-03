from __future__ import annotations

from pathlib import Path

from betelgeuze_product.pilot_packet import build_product_pilot_packet_contract


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


def _bundle_contract(tmp_path: Path, *, assembled: bool = False) -> dict:
    bundle_dir = tmp_path / "runs" / "local_delivery" / "bundle_product_gpcr_adrb2"
    if assembled:
        bundle_dir.mkdir(parents=True)
    return {
        "summary": {
            "status": "product_bundle_contract_ready",
            "target_id": "ADRB2",
            "family": "gpcr",
            "ligand_count": 1,
            "expected_bundle_dir": str(bundle_dir),
            "bundle_assembled": assembled,
            "execution_enabled": False,
            "docking_results_emitted": False,
            "external_state_mutated": False,
        }
    }


def _delivery_evidence(*, claim_allowed: bool = False) -> dict:
    return {
        "summary": {
            "status": "product_delivery_evidence_contract_ready",
            "delivery_ready_claim_allowed": claim_allowed,
            "execution_enabled": False,
            "docking_results_emitted": False,
            "external_state_mutated": False,
        }
    }


def _validator(*, ok: bool = True) -> dict:
    return {
        "summary": {
            "overall_ok": ok,
            "delivery_ready_policy_ok": ok,
            "manifest_signature_ok": ok,
            "checksum": {"ok": ok},
        }
    }


def _top_level_validator(*, ok: bool = True) -> dict:
    return {
        "overall_ok": ok,
        "delivery_ready_policy_ok": ok,
        "manifest_signature_ok": ok,
        "checksum": {"ok": ok},
        "blocker_count": 0 if ok else 1,
    }


def test_product_pilot_packet_preflight_ready_without_assembly(tmp_path: Path) -> None:
    payload = build_product_pilot_packet_contract(
        product_readiness_packet=_readiness(),
        product_execution_preflight_packet=_preflight(),
        product_bundle_contract_packet=_bundle_contract(tmp_path),
        product_delivery_evidence_packet=_delivery_evidence(),
        root=tmp_path,
    )
    summary = payload["summary"]

    assert summary["status"] == "product_pilot_packet_preflight_ready"
    assert summary["pilot_delivery_ready"] is False
    assert summary["operator_approval_required"] is True
    assert summary["bundle_validation_passed"] is False
    assert summary["execution_enabled"] is False
    assert summary["external_state_mutated"] is False
    assert payload["blockers"] == []
    assert any(row["check"] == "bundle_finalization" and row["status"] == "pending" for row in payload["rows"])


def test_product_pilot_packet_ready_after_claim_and_validator_pass(tmp_path: Path) -> None:
    payload = build_product_pilot_packet_contract(
        product_readiness_packet=_readiness(),
        product_execution_preflight_packet=_preflight(),
        product_bundle_contract_packet=_bundle_contract(tmp_path, assembled=True),
        product_delivery_evidence_packet=_delivery_evidence(claim_allowed=True),
        bundle_validation_packet=_validator(),
        root=tmp_path,
    )

    assert payload["summary"]["status"] == "product_pilot_packet_ready"
    assert payload["summary"]["pilot_delivery_ready"] is True
    assert payload["summary"]["operator_approval_required"] is False
    assert payload["summary"]["bundle_validation_passed"] is True


def test_product_pilot_packet_accepts_top_level_validator_output(tmp_path: Path) -> None:
    payload = build_product_pilot_packet_contract(
        product_readiness_packet=_readiness(),
        product_execution_preflight_packet=_preflight(),
        product_bundle_contract_packet=_bundle_contract(tmp_path, assembled=True),
        product_delivery_evidence_packet=_delivery_evidence(claim_allowed=True),
        bundle_validation_packet=_top_level_validator(),
        root=tmp_path,
    )

    assert payload["summary"]["status"] == "product_pilot_packet_ready"
    assert payload["summary"]["bundle_validation_passed"] is True


def test_product_pilot_packet_blocks_claim_without_validator(tmp_path: Path) -> None:
    payload = build_product_pilot_packet_contract(
        product_readiness_packet=_readiness(),
        product_execution_preflight_packet=_preflight(),
        product_bundle_contract_packet=_bundle_contract(tmp_path, assembled=True),
        product_delivery_evidence_packet=_delivery_evidence(claim_allowed=True),
        root=tmp_path,
    )

    assert payload["summary"]["status"] == "blocked_product_pilot_packet_contract"
    assert any(blocker["code"] == "delivery_claim_without_final_bundle_validation" for blocker in payload["blockers"])

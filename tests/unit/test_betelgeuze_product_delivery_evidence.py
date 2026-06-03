from __future__ import annotations

from betelgeuze_product.delivery_evidence import build_product_delivery_evidence_contract


def _readiness(family: str = "gpcr") -> dict:
    return {"summary": {"status": "product_handoff_ready", "target_id": "ADRB2", "family": family, "ligand_count": 1}}


def _preflight() -> dict:
    return {"summary": {"status": "product_execution_preflight_ready"}}


def _bundle_contract(*, assembled: bool = False, validated: bool = False) -> dict:
    return {
        "summary": {
            "status": "product_bundle_contract_ready",
            "bundle_assembled": assembled,
            "bundle_validation_passed": validated,
            "execution_enabled": False,
            "docking_results_emitted": False,
            "external_state_mutated": False,
        }
    }


def _verdict(*, ready: bool = True) -> dict:
    return {
        "summary": {
            "delivery_ready": ready,
            "verdict": "delivery_ready" if ready else "internal_review",
            "p0_blocker_count": 0 if ready else 1,
            "hard_blocker_count": 0,
            "source_artifacts_all_fingerprinted": ready,
        }
    }


def _local_preflight() -> dict:
    return {"summary": {"overall_ok": True, "dry_run": False}}


def _environment() -> dict:
    return {"summary": {"requirements_lock_complete": True, "torch_blas_prefer_hipblaslt": "0", "requirements_lock_missing_count": 0}}


def _requirements() -> dict:
    return {
        "summary": {
            "missing_count": 0,
            "blocking_missing_count": 0,
            "loose_source_requirement_count": 0,
            "missing_input_file_count": 0,
            "incomplete_reason_count": 0,
        }
    }


def _engine() -> dict:
    return {"summary": {"provenance_ok": True, "existing_engine_reused": True}}


def _queue() -> dict:
    return {"summary": {"queue_clear": True, "blocked_count": 0}}


def _nightly() -> dict:
    return {"summary": {"status": "nightly_gate_green", "stage6_gate_failed": False}}


def _wetlab() -> dict:
    return {"summary": {"selected_allatom_wetlab_gate_pass": True, "selected_allatom_final_gate_pass": True, "hard_block_count": 0}}


def _build(**overrides: dict) -> dict:
    packets = {
        "product_readiness_packet": _readiness(),
        "product_execution_preflight_packet": _preflight(),
        "product_bundle_contract_packet": _bundle_contract(),
        "local_delivery_verdict_packet": _verdict(),
        "local_delivery_preflight_packet": _local_preflight(),
        "environment_manifest_packet": _environment(),
        "requirements_lock_packet": _requirements(),
        "engine_provenance_packet": _engine(),
        "commercialization_queue_packet": _queue(),
        "nightly_gate_packet": _nightly(),
        "wetlab_gate_packet": _wetlab(),
    }
    packets.update(overrides)
    return build_product_delivery_evidence_contract(**packets)


def test_product_delivery_evidence_contract_ready_but_claim_disallowed_before_bundle_validation() -> None:
    payload = _build()
    summary = payload["summary"]

    assert summary["status"] == "product_delivery_evidence_contract_ready"
    assert summary["evidence_pass_count"] == summary["evidence_check_count"]
    assert summary["delivery_ready_claim_allowed"] is False
    assert summary["bundle_assembled"] is False
    assert summary["bundle_validation_passed"] is False
    assert summary["execution_enabled"] is False
    assert summary["docking_results_emitted"] is False
    assert summary["external_state_mutated"] is False
    assert any(warning["code"] == "bundle_not_assembled_yet" for warning in payload["warnings"])


def test_product_delivery_evidence_contract_allows_claim_only_after_bundle_assembled_and_validated() -> None:
    payload = _build(product_bundle_contract_packet=_bundle_contract(assembled=True, validated=True))

    assert payload["summary"]["status"] == "product_delivery_evidence_contract_ready"
    assert payload["summary"]["delivery_ready_claim_allowed"] is True


def test_product_delivery_evidence_contract_blocks_bad_verdict_and_out_of_scope_family() -> None:
    payload = _build(product_readiness_packet=_readiness("transporter"), local_delivery_verdict_packet=_verdict(ready=False))

    assert payload["summary"]["status"] == "blocked_product_delivery_evidence_contract"
    codes = {blocker["code"] for blocker in payload["blockers"]}
    assert "restricted_product_family_not_ready" in codes
    assert "local_delivery_verdict_gate_not_ready" in codes

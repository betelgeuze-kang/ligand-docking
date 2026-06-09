from __future__ import annotations

from tools.product import build_residual_production_promotion_gate as mod


def _assist(*, allowed: bool = True) -> dict[str, object]:
    return {"summary": {"assist_promotion_allowed": allowed}}


def _sidecar(*, ready: bool = True) -> dict[str, object]:
    return {"summary": {"sidecar_ready": ready, "sidecar_written": ready}}


def _preflight(*, ready: bool = True) -> dict[str, object]:
    return {"summary": {"checkpoint_preflight_ready": ready, "ready_checkpoint_count": 1 if ready else 0}}


def _training(*, ready: bool = True) -> dict[str, object]:
    return {"summary": {"production_training_data_ready": ready, "primary_blocker": "none"}}


def _score(*, ready: bool = True) -> dict[str, object]:
    return {
        "summary": {
            "production_checkpoint_ready": ready,
            "missing_production_output_fields": [] if ready else ["delta_force"],
        }
    }


def _receipt(*, ready: bool = True) -> dict[str, object]:
    return {"summary": {"gpu_worker_return_receipt_ready": ready, "manifest_ok_row_count": 768 if ready else 0}}


def test_residual_production_promotion_gate_ready_when_all_checks_pass() -> None:
    payload = mod.build_residual_production_promotion_gate(
        assist_gate_packet=_assist(),
        sidecar_packet=_sidecar(),
        preflight_packet=_preflight(),
        training_contract_packet=_training(),
        score_model_packet=_score(),
        force_receipt_packet=_receipt(),
    )
    summary = payload["summary"]
    assert summary["status"] == "residual_production_promotion_gate_ready"
    assert summary["production_promotion_allowed"] is True
    assert summary["fail_check_count"] == 0


def test_residual_production_promotion_gate_blocks_when_assist_missing() -> None:
    payload = mod.build_residual_production_promotion_gate(
        assist_gate_packet=_assist(allowed=False),
        sidecar_packet=_sidecar(),
        preflight_packet=_preflight(),
        training_contract_packet=_training(),
        score_model_packet=_score(),
        force_receipt_packet=_receipt(),
    )
    summary = payload["summary"]
    assert summary["status"] == "blocked_residual_production_promotion_gate"
    assert summary["production_promotion_allowed"] is False
    assert summary["primary_blocker"] == "assist_promotion_prerequisite"


def test_residual_production_promotion_gate_reads_flat_score_model_summary() -> None:
    payload = mod.build_residual_production_promotion_gate(
        assist_gate_packet=_assist(),
        sidecar_packet=_sidecar(),
        preflight_packet=_preflight(),
        training_contract_packet=_training(),
        score_model_packet={"production_checkpoint_ready": True, "missing_production_output_fields": []},
        force_receipt_packet=_receipt(),
    )
    assert payload["summary"]["production_promotion_allowed"] is True

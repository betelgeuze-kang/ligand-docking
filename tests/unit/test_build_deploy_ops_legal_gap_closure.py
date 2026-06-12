from __future__ import annotations

from tools import build_deploy_ops_legal_gap_closure as mod


def _rollout_ready() -> dict:
    return {
        "summary": {
            "status": "product_rollout_execution_readiness_ready",
            "alert_smoke_ready": True,
            "authorized_for_separate_operator_execution": True,
            "blocker_count": 0,
            "rollout_executed": False,
            "external_state_mutated": False,
        }
    }


def _rollout_smoke_ready() -> dict:
    return {
        "summary": {
            "status": "product_rollout_execution_smoke_receipt_ready",
            "rollout_execution_smoke_receipt_ready": True,
            "rollout_executed": True,
            "external_state_mutated": True,
            "pager_provider_contacted": True,
            "ingress_certificate_verified_live": True,
        }
    }


def _license_review_ready() -> dict:
    return {
        "summary": {
            "status": "third_party_license_review_gate_ready",
            "legal_advice_provided": False,
        }
    }


def test_deploy_ops_legal_gap_closure_blocks_missing_actual_rollout_smoke(tmp_path, monkeypatch) -> None:
    license_path = tmp_path / "LICENSE"
    approved_path = tmp_path / "legal" / "proprietary-license-betelgeuze.txt"
    approved_path.parent.mkdir(parents=True)
    text = "Proprietary license text\n"
    license_path.write_text(text, encoding="utf-8")
    approved_path.write_text(text, encoding="utf-8")
    security = tmp_path / "api" / "security.py"
    config = tmp_path / "api" / "config.py"
    security.parent.mkdir(parents=True)
    security.write_text("hosted_tls_termination_not_verified\n", encoding="utf-8")
    config.write_text("product_api_tls_termination_operator_verified\n", encoding="utf-8")
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    monkeypatch.setattr(mod, "_read_text", lambda path: (tmp_path / path).read_text(encoding="utf-8") if (tmp_path / path).exists() else "")

    payload = mod.build_deploy_ops_legal_gap_closure(
        rollout_readiness_packet=_rollout_ready(),
        license_review_packet=_license_review_ready(),
        license_decision_packet={"summary": {"status": "product_license_decision_gate_ready"}},
    )
    summary = payload["summary"]
    assert summary["status"] == "blocked_deploy_ops_legal_gap_closure"
    assert summary["all_gaps_closed"] is False
    assert summary["open_gap_ids"] == ["DEP-ROLLOUT-SMOKE"]
    assert summary["current_primary_open_gap_id"] == "DEP-ROLLOUT-SMOKE"
    assert summary["rollout_execution_readiness_ready"] is True
    assert summary["rollout_smoke_receipt_ready"] is False
    assert summary["rollout_executed"] is False
    assert summary["legal_advice_provided"] is False


def test_deploy_ops_legal_gap_closure_complete_with_rollout_smoke_receipt(tmp_path, monkeypatch) -> None:
    license_path = tmp_path / "LICENSE"
    approved_path = tmp_path / "legal" / "proprietary-license-betelgeuze.txt"
    approved_path.parent.mkdir(parents=True)
    text = "Proprietary license text\n"
    license_path.write_text(text, encoding="utf-8")
    approved_path.write_text(text, encoding="utf-8")
    security = tmp_path / "api" / "security.py"
    config = tmp_path / "api" / "config.py"
    security.parent.mkdir(parents=True)
    security.write_text("hosted_tls_termination_not_verified\n", encoding="utf-8")
    config.write_text("product_api_tls_termination_operator_verified\n", encoding="utf-8")
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    monkeypatch.setattr(mod, "_read_text", lambda path: (tmp_path / path).read_text(encoding="utf-8") if (tmp_path / path).exists() else "")

    payload = mod.build_deploy_ops_legal_gap_closure(
        rollout_readiness_packet=_rollout_ready(),
        rollout_smoke_receipt_packet=_rollout_smoke_ready(),
        license_review_packet=_license_review_ready(),
        license_decision_packet={"summary": {"status": "product_license_decision_gate_ready"}},
    )
    summary = payload["summary"]
    assert summary["status"] == "deploy_ops_legal_gap_closure_complete"
    assert summary["all_gaps_closed"] is True
    assert summary["closed_gap_count"] == 6
    assert summary["rollout_executed"] is True
    assert summary["rollout_smoke_external_state_mutated"] is True
    assert summary["legal_advice_provided"] is False

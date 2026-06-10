from __future__ import annotations

from pathlib import Path

from tools.product import build_restricted_unattended_execution_readiness as mod


def test_build_restricted_unattended_execution_readiness_runtime_via_smoke(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    runs = tmp_path / "runs"
    runs.mkdir()
    (runs / "api_docking_dispatch_e2e_evidence_current.json").write_text(
        '{"summary": {"status": "api_docking_dispatch_e2e_ready", "wiring_ready": true, "evidence_mode": "live_job"}, "ledger_worker_state": "completed_fail_closed"}\n',
        encoding="utf-8",
    )
    (runs / "api_runner_profile_promotion_readiness_current.json").write_text(
        '{"summary": {"status": "api_runner_profile_promotion_ready"}}\n',
        encoding="utf-8",
    )
    (runs / "local_delivery_verdict_gate_current.json").write_text(
        '{"summary": {"delivery_ready": true, "verdict": "delivery_ready"}}\n',
        encoding="utf-8",
    )
    (runs / "architecture_validation_package_report_current.json").write_text(
        '{"summary": {"package_a_complete": true}}\n',
        encoding="utf-8",
    )
    (runs / "tier_alpha_adrb2_dispatch_smoke_current.json").write_text(
        '{"summary": {"status": "tier_alpha_adrb2_dispatch_smoke_pass", "api_validated_runner_enabled": true}, "ledger_worker_state": "completed_fail_closed", "simulation_sync_status": "completed"}\n',
        encoding="utf-8",
    )
    monkeypatch.delenv("API_VALIDATED_RUNNER_ENABLED", raising=False)

    payload = mod.build_restricted_unattended_execution_readiness()
    summary = payload["summary"]
    assert summary["restricted_unattended_execution_ready"] is True
    assert summary["restricted_unattended_execution_runtime_ready"] is True
    assert summary["tier_alpha_smoke_runtime_verified"] is True
    assert summary["status"] == "restricted_unattended_execution_runtime_ready"


def test_build_restricted_unattended_execution_readiness_wiring_only_without_smoke(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    runs = tmp_path / "runs"
    runs.mkdir()
    (runs / "api_docking_dispatch_e2e_evidence_current.json").write_text(
        '{"summary": {"status": "api_docking_dispatch_e2e_ready", "wiring_ready": true}, "ledger_worker_state": "completed_fail_closed"}\n',
        encoding="utf-8",
    )
    (runs / "api_runner_profile_promotion_readiness_current.json").write_text(
        '{"summary": {"status": "api_runner_profile_promotion_ready"}}\n',
        encoding="utf-8",
    )
    (runs / "local_delivery_verdict_gate_current.json").write_text(
        '{"summary": {"delivery_ready": true, "verdict": "delivery_ready"}}\n',
        encoding="utf-8",
    )
    (runs / "architecture_validation_package_report_current.json").write_text(
        '{"summary": {"package_a_complete": true}}\n',
        encoding="utf-8",
    )
    monkeypatch.delenv("API_VALIDATED_RUNNER_ENABLED", raising=False)

    payload = mod.build_restricted_unattended_execution_readiness()
    summary = payload["summary"]
    assert summary["restricted_unattended_execution_ready"] is True
    assert summary["restricted_unattended_execution_runtime_ready"] is False
    assert summary["status"] == "restricted_unattended_execution_wiring_ready"

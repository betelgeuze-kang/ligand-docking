from __future__ import annotations

from pathlib import Path

from tools.product import build_api_docking_dispatch_e2e_evidence as e2e_mod


def test_build_api_docking_dispatch_e2e_evidence_wiring_ready(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(e2e_mod, "ROOT", tmp_path)
    profiles = tmp_path / "config/api_validated_runner_profiles"
    profiles.mkdir(parents=True)
    (profiles / "ligand_htvs_pipeline_default.json").write_text('{"enabled": true}\n', encoding="utf-8")
    (tmp_path / "runs").mkdir()
    (tmp_path / "runs/api_runner_profile_promotion_readiness_current.json").write_text(
        '{"summary": {"status": "api_runner_profile_promotion_ready", "blocked_profile_count": 0}}\n',
        encoding="utf-8",
    )
    deploy = tmp_path / "deploy"
    deploy.mkdir()
    (deploy / "docker-compose.product.yml").write_text(
        "services:\n  api-server:\n    image: x\n  api-worker:\n    image: x\n  api-docking-dispatch:\n    image: x\n",
        encoding="utf-8",
    )
    (tmp_path / "config").mkdir(exist_ok=True)
    (tmp_path / "config/ligand_htvs_api_dispatch_smoke_v1.json").write_text("{}\n", encoding="utf-8")
    (tmp_path / "tools").mkdir()
    (tmp_path / "tools/run_api_docking_dispatch_worker.py").write_text("# dispatch\n", encoding="utf-8")
    (tmp_path / "tools/run_api_simulation_worker.py").write_text("# worker\n", encoding="utf-8")

    payload = e2e_mod.build_api_docking_dispatch_e2e_evidence()
    assert payload["summary"]["wiring_ready"] is True
    assert payload["ledger_worker_state"] == "completed_fail_closed"
    assert payload["simulation_sync_status"] == "completed"

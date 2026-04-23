from __future__ import annotations

import json
from pathlib import Path

from tools.monitor_cross_family_locked_decoy_shadow import _render


def test_render_cross_family_monitor(tmp_path: Path, monkeypatch) -> None:
    run_root = tmp_path / "runs/external_validation_blind_runs/external_validation_blind_runs_2026-03-25_r1"
    run_root.mkdir(parents=True)
    (run_root / "state.json").write_text(json.dumps({"protocol_id": "cross_family_locked_decoy_shadow_v1", "status": "running"}), encoding="utf-8")

    summary = tmp_path / "runs/external_validation_2026-03-25_r1_set1_core_blind_ion_trpv1_chembl20_full_summary.json"
    summary.parent.mkdir(parents=True, exist_ok=True)
    summary.write_text(json.dumps({"pass": True, "ranking_pr_auc": 0.9, "ranking_ef1": 4.0}), encoding="utf-8")

    progress = tmp_path / "runs/external_validation_2026-03-25_r1_set1_core_blind_kinase_core_full_p0_n10000_r1_stage2_traj_progress.json"
    progress.write_text(json.dumps({"processed_rows": 2500, "total_rows": 10000, "progress_ratio": 0.25}), encoding="utf-8")
    state = tmp_path / "runs/external_validation_2026-03-25_r1_set1_core_blind_kinase_core_full_state.json"
    state.write_text(json.dumps({"started_at": "2026-03-25T23:00:00", "current": {"status": "run_running"}}), encoding="utf-8")

    monkeypatch.setattr("tools.monitor_cross_family_locked_decoy_shadow.ROOT", tmp_path)
    monkeypatch.setattr("tools.monitor_cross_family_locked_decoy_shadow._proc_lines", lambda: ["run_ligand_stress_validation.py --profile-json x/trpv1_chembl20_crossfamshadow1.json"])

    text = _render(run_root)
    assert "CROSSFAM SHADOW" in text
    assert "trpv1_20" in text
    assert "PASS" in text
    assert "kin_core" in text
    assert "25.0%" in text
    assert "task trpv1_20" in text
    assert "actors 1 [stress]" in text
    assert "sets" in text
    assert "tasks" in text

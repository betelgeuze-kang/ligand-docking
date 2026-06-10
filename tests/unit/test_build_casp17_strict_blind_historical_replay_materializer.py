from __future__ import annotations

import json
from pathlib import Path

from tools.product import build_casp17_strict_blind_historical_replay_materializer as replay_mod


def test_build_strict_blind_historical_replay_materializes_slots(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(replay_mod, "ROOT", tmp_path)
    import tools.accounting.build_casp17_historical_benchmark_packet as hist_mod

    monkeypatch.setattr(hist_mod, "ROOT", tmp_path)
    metric_path = tmp_path / "casp17" / "casp17_win_tier_metric_surface_contract_current.json"
    metric_path.parent.mkdir(parents=True)
    metric_path.write_text(
        json.dumps(
            {
                "summary": {"ready_metric_row_count": 0, "strict_blind_slot_count": 0},
                "rows": [
                    {"slot_rank": 1, "metric_status": "awaiting_strict_blind_evidence_files"},
                    {"slot_rank": 2, "metric_status": "awaiting_strict_blind_evidence_files"},
                ],
            }
        )
        + "\n",
        encoding="utf-8",
    )

    payload = replay_mod.build_strict_blind_historical_replay(slot_count=2)
    summary = payload["summary"]
    assert summary["status"] == "strict_blind_historical_replay_ready"
    assert summary["slot_count"] == 2
    assert summary["pass_count"] == 2
    assert summary["metric_surface_sync"]["ready_metric_row_count"] == 2
    dropzone = summary["strict_blind_slot1_dropzone"]
    assert dropzone["installed"] is True
    assert dropzone["atom_count"] >= 20

    manifest = tmp_path / "runs" / "casp17_historical_benchmark_manifest_current.csv"
    assert manifest.exists()
    metric = json.loads(metric_path.read_text(encoding="utf-8"))
    assert metric["summary"]["ready_metric_row_count"] == 2

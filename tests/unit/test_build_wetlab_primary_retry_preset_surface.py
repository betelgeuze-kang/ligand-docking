from __future__ import annotations

import json
from pathlib import Path

from tools import build_wetlab_primary_retry_preset_surface as mod


def test_build_wetlab_primary_retry_preset_surface_classifies_retry_modes(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    base = tmp_path / "runs" / "wetlab_broad_screen_throughput"

    def write_summary(target_slug: str, shard_id: str, payload: dict) -> None:
        path = base / target_slug / shard_id
        path.mkdir(parents=True, exist_ok=True)
        (path / "throughput_run_summary.json").write_text(json.dumps(payload), encoding="utf-8")

    write_summary(
        "sars_cov_2_mpro",
        "01_of_20",
        {
            "failed_stage": "stage1_ligand_mapping",
            "service_result": {"status": "error", "error_code": "HTVS_MAPPING_FAILED", "failed_stage": "stage1_ligand_mapping"},
            "stages": {"stage1_ligand_mapping": {"pass": False}},
        },
    )
    write_summary(
        "t_cruzi_pde",
        "01_of_20",
        {
            "failed_stage": "stage6_operational_gate",
            "service_result": {"status": "error", "error_code": "HTVS_GATE_FAILED", "failed_stage": "stage6_operational_gate"},
            "stages": {
                "stage6_operational_gate": {
                    "pass": False,
                    "mean_min_distance_A": 4.8,
                    "failed_metrics": [{"metric": "mean_min_distance_A", "threshold": 2.5}],
                }
            },
        },
    )
    write_summary(
        "t_cruzi_pde",
        "02_of_20",
        {
            "failed_stage": "stage6_operational_gate",
            "service_result": {"status": "error", "error_code": "HTVS_GATE_FAILED", "failed_stage": "stage6_operational_gate"},
            "stages": {
                "stage6_operational_gate": {
                    "pass": False,
                    "mean_min_distance_A": 4.9,
                    "failed_metrics": [{"metric": "mean_min_distance_A", "threshold": 2.5}],
                }
            },
        },
    )
    write_summary(
        "alk2",
        "01_of_20",
        {
            "failed_stage": "stage6_operational_gate",
            "service_result": {"status": "error", "error_code": "HTVS_GATE_FAILED", "failed_stage": "stage6_operational_gate"},
            "stages": {
                "stage6_operational_gate": {
                    "pass": False,
                    "mean_min_distance_A": 4.3,
                    "failed_metrics": [{"metric": "mean_min_distance_A", "threshold": 2.5}],
                }
            },
        },
    )

    payload = mod.build_payload(
        {
            "rows": [
                {
                    "target_id": "SARS-CoV-2 Mpro",
                    "target_slug": "sars_cov_2_mpro",
                    "shard_id": "01_of_20",
                    "queue_status": "explicit_hold",
                    "notes": "auto_hold_from_primary_watcher_runtime_validation_only",
                },
                {
                    "target_id": "T. cruzi PDE",
                    "target_slug": "t_cruzi_pde",
                    "shard_id": "01_of_20",
                    "queue_status": "explicit_hold",
                    "notes": "auto_hold_from_primary_watcher_runtime_validation_only",
                },
                {
                    "target_id": "T. cruzi PDE",
                    "target_slug": "t_cruzi_pde",
                    "shard_id": "02_of_20",
                    "queue_status": "explicit_hold",
                    "notes": "auto_hold_from_primary_watcher_runtime_validation_only",
                },
                {
                    "target_id": "ALK2",
                    "target_slug": "alk2",
                    "shard_id": "01_of_20",
                    "queue_status": "explicit_hold",
                    "notes": "auto_hold_from_primary_watcher_runtime_validation_only",
                },
            ]
        },
        targets=["SARS-CoV-2 Mpro", "T. cruzi PDE", "ALK2"],
        guard_limit=2,
    )

    summary = payload["summary"]
    assert summary["status"] == "wetlab_primary_retry_preset_surface_ready"
    assert summary["target_count"] == 3
    assert summary["auto_hold_row_count"] == 4
    assert summary["stage1_mapping_failed_count"] == 1
    assert summary["stage6_distance_gate_failed_count"] == 3
    assert summary["guard_blocked_target_count"] == 1

    rows = {row["target_id"]: row for row in payload["rows"]}
    assert rows["SARS-CoV-2 Mpro"]["recommended_retry_mode"] == "mapping_fix_required"
    assert rows["SARS-CoV-2 Mpro"]["representative_stage1_mapping_failure_shard_id"] == "01_of_20"
    assert "Repair stage1 ligand mapping" in rows["SARS-CoV-2 Mpro"]["target_specific_next_step"]

    assert rows["T. cruzi PDE"]["recommended_retry_mode"] == "do_not_autoadvance"
    assert rows["T. cruzi PDE"]["consecutive_auto_hold_guard_recommendation"] == "guard_stop_target_now_2_ge_2"
    assert rows["T. cruzi PDE"]["representative_stage6_failure_shard_id"] == "02_of_20"

    assert rows["ALK2"]["recommended_retry_mode"] == "tuned_gate_candidate"
    assert rows["ALK2"]["consecutive_auto_hold_guard_recommendation"] == "allow_one_manual_retry_then_stop_at_2"

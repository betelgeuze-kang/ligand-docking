from __future__ import annotations

import json
from pathlib import Path

from tools import build_wetlab_hard_target_rescue_lane as mod


def _write_summary(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_build_wetlab_hard_target_rescue_lane_selects_ready_focus_and_blocks_preset_mismatch(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(mod, "ROOT", tmp_path)

    pde_summary = tmp_path / "runs" / "wetlab_broad_screen_throughput" / "t_cruzi_pde" / "20_of_20" / "throughput_run_summary.json"
    _write_summary(
        pde_summary,
        {
            "service_result": {"status": "error", "error_code": "HTVS_GATE_FAILED", "failed_stage": "stage6_operational_gate"},
            "stages": {"stage1_ligand_mapping": {"pass": True}},
            "traj_prod": {"requested_preset": "default", "resolved_preset": "default", "hinted_families": ["default"]},
        },
    )
    mpro_summary = tmp_path / "runs" / "wetlab_broad_screen_throughput" / "sars_cov_2_mpro" / "20_of_20" / "throughput_run_summary.json"
    _write_summary(
        mpro_summary,
        {
            "service_result": {"status": "error", "error_code": "HTVS_GATE_FAILED", "failed_stage": "stage6_operational_gate"},
            "stages": {"stage1_ligand_mapping": {"pass": True}},
            "traj_prod": {
                "requested_preset": "kinase_protease",
                "resolved_preset": "kinase_protease",
                "hinted_families": ["default"],
            },
        },
    )

    payload = mod.build_payload(
        {
            "rows": [
                {"target_id": "T. cruzi PDE", "shard_id": "20_of_20", "queue_status": "explicit_hold"},
                {"target_id": "SARS-CoV-2 Mpro", "shard_id": "20_of_20", "queue_status": "explicit_hold"},
            ]
        },
        {
            "rows": [
                {
                    "target_id": "T. cruzi PDE",
                    "shard_id": "19_of_20",
                    "failed_stage": "stage6_operational_gate",
                    "mean_min_distance_A": 4.8,
                    "distance_over_threshold_A": 2.3,
                    "summary_json": str(pde_summary),
                },
                {
                    "target_id": "T. cruzi PDE",
                    "shard_id": "20_of_20",
                    "failed_stage": "stage6_operational_gate",
                    "mean_min_distance_A": 5.04,
                    "distance_over_threshold_A": 2.54,
                    "summary_json": str(pde_summary),
                },
                {
                    "target_id": "SARS-CoV-2 Mpro",
                    "shard_id": "20_of_20",
                    "failed_stage": "stage6_operational_gate",
                    "mean_min_distance_A": 4.45,
                    "distance_over_threshold_A": 1.95,
                    "summary_json": str(mpro_summary),
                },
            ]
        },
        {
            "rows": [
                {"target_id": "T. cruzi PDE", "recent_consecutive_auto_hold_streak": 4, "total_auto_hold_count": 4},
                {"target_id": "SARS-CoV-2 Mpro", "recent_consecutive_auto_hold_streak": 5, "total_auto_hold_count": 5},
            ]
        },
        {
            "rows": [
                {"target_id": "T. cruzi PDE", "selected_command_kind": "throughput_preflight_tuned_gate51", "template_label": "gate51_branch_only_empirical"},
                {"target_id": "SARS-CoV-2 Mpro", "selected_command_kind": "throughput_preflight_tuned_gate45", "template_label": "guarded_gate45_candidate"},
            ]
        },
        min_auto_hold_streak=3,
        top_n_three_bead=32,
    )

    summary = payload["summary"]
    assert summary["candidate_target_count"] == 2
    assert summary["ready_target_count"] == 1
    assert summary["blocked_by_preset_mismatch_target_count"] == 1
    assert summary["focus_target_id"] == "T. cruzi PDE"
    assert summary["focus_shard_id"] == "20_of_20"
    assert summary["focus_ready_for_manual_retry"] is True
    assert summary["focus_top_n_three_bead_recommended"] is True

    rows = {row["target_id"]: row for row in payload["rows"]}
    assert rows["T. cruzi PDE"]["stage1_ok"] is True
    assert rows["T. cruzi PDE"]["stage1_ok_source"] == "stage1_ligand_mapping.pass"
    assert rows["T. cruzi PDE"]["rescue_candidate_shard_count"] == 2
    assert rows["T. cruzi PDE"]["rescue_candidate_shard_ids"] == "19_of_20;20_of_20"
    assert rows["T. cruzi PDE"]["rescue_base_command_kind"] == "throughput_preflight_tuned_gate51"
    assert rows["T. cruzi PDE"]["top_n_three_bead_recommended"] is True
    assert rows["T. cruzi PDE"]["ready_for_manual_retry"] is True

    assert rows["SARS-CoV-2 Mpro"]["preset_mismatch_hard_guard_active"] is True
    assert rows["SARS-CoV-2 Mpro"]["preset_mismatch_requested_preset"] == "kinase_protease"
    assert rows["SARS-CoV-2 Mpro"]["preset_mismatch_hinted_families"] == "default"
    assert rows["SARS-CoV-2 Mpro"]["ready_for_manual_retry"] is False


def test_build_wetlab_hard_target_rescue_lane_requires_stage1_ok_and_hold_streak(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(mod, "ROOT", tmp_path)

    summary_path = tmp_path / "runs" / "wetlab_broad_screen_throughput" / "cathepsin_k" / "04_of_20" / "throughput_run_summary.json"
    _write_summary(
        summary_path,
        {
            "service_result": {"status": "error", "error_code": "HTVS_GATE_FAILED", "failed_stage": "stage6_operational_gate"},
            "stages": {"stage1_ligand_mapping": {"pass": False}},
        },
    )

    payload = mod.build_payload(
        {"rows": [{"target_id": "Cathepsin K", "shard_id": "04_of_20", "queue_status": "explicit_hold"}]},
        {
            "rows": [
                {
                    "target_id": "Cathepsin K",
                    "shard_id": "04_of_20",
                    "failed_stage": "stage6_operational_gate",
                    "mean_min_distance_A": 4.41,
                    "summary_json": str(summary_path),
                }
            ]
        },
        {"rows": [{"target_id": "Cathepsin K", "recent_consecutive_auto_hold_streak": 2, "total_auto_hold_count": 2}]},
        {"rows": [{"target_id": "Cathepsin K", "selected_command_kind": "throughput_preflight_tuned_gate45"}]},
        min_auto_hold_streak=3,
    )

    assert payload["summary"]["candidate_target_count"] == 0
    assert payload["rows"] == []

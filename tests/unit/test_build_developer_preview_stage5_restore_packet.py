from __future__ import annotations

import csv
from pathlib import Path

from tools.product import build_developer_preview_stage5_restore_packet as mod


def _write_stage5_input_family(root: Path) -> None:
    csv_path = root / ".betelgeuze/developer_preview_clean_checkout_stage5_input_family_current.csv"
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path = (
        root
        / "runs/external_validation_blind_runs/demo/set1_core_blind/files/gpcr/demo_summary.json"
    )
    profile_path = root / "config/demo_profile.json"
    source_path = root / "runs/demo_stage3_scores.csv"
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    profile_path.parent.mkdir(parents=True, exist_ok=True)
    source_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text('{"summary": {"status": "ready"}}\n', encoding="utf-8")
    profile_path.write_text("{}\n", encoding="utf-8")
    source_path.write_text("target_id,score\nA,1.0\n", encoding="utf-8")
    fieldnames = [
        "set_id",
        "task_id",
        "task_key",
        "domain",
        "kind",
        "source_argument",
        "source_artifact_path",
        "source_artifact_present",
        "source_artifact_missing",
        "pipeline_summary_json",
        "pipeline_summary_present",
        "profile_json",
        "required_action",
        "operator_action_required",
        "execution_enabled",
        "external_state_mutated",
        "claim_promotion_allowed",
    ]
    rows = [
        {
            "set_id": "set1_core_blind",
            "task_id": "gpcr_core_full",
            "task_key": "demo_task",
            "domain": "gpcr",
            "kind": "ligand_stress",
            "source_argument": "--scores-csv",
            "source_artifact_path": "runs/demo_stage3_scores.csv",
            "source_artifact_present": "true",
            "source_artifact_missing": "false",
            "pipeline_summary_json": (
                "runs/external_validation_blind_runs/demo/set1_core_blind/files/gpcr/demo_summary.json"
            ),
            "pipeline_summary_present": "true",
            "profile_json": "config/demo_profile.json",
            "required_action": "restore",
            "operator_action_required": "false",
            "execution_enabled": "false",
            "external_state_mutated": "false",
            "claim_promotion_allowed": "false",
        },
        {
            "set_id": "set1_core_blind",
            "task_id": "gpcr_core_full",
            "task_key": "demo_task",
            "domain": "gpcr",
            "kind": "ligand_stress",
            "source_argument": "--labels-csv",
            "source_artifact_path": "runs/demo_hard_decoy_labels.csv",
            "source_artifact_present": "false",
            "source_artifact_missing": "true",
            "pipeline_summary_json": (
                "runs/external_validation_blind_runs/demo/set1_core_blind/files/gpcr/demo_summary.json"
            ),
            "pipeline_summary_present": "true",
            "profile_json": "config/demo_profile.json",
            "required_action": "restore",
            "operator_action_required": "true",
            "execution_enabled": "false",
            "external_state_mutated": "false",
            "claim_promotion_allowed": "false",
        },
        {
            "set_id": "set1_core_blind",
            "task_id": "gpcr_core_full",
            "task_key": "demo_task",
            "domain": "gpcr",
            "kind": "ligand_stress",
            "source_argument": "--split-csv",
            "source_artifact_path": "runs/demo_hard_decoy_split.csv",
            "source_artifact_present": "false",
            "source_artifact_missing": "true",
            "pipeline_summary_json": (
                "runs/external_validation_blind_runs/demo/set1_core_blind/files/gpcr/demo_summary.json"
            ),
            "pipeline_summary_present": "true",
            "profile_json": "config/demo_profile.json",
            "required_action": "restore",
            "operator_action_required": "true",
            "execution_enabled": "false",
            "external_state_mutated": "false",
            "claim_promotion_allowed": "false",
        },
        {
            "set_id": "set1_core_blind",
            "task_id": "gpcr_core_full",
            "task_key": "demo_task",
            "domain": "gpcr",
            "kind": "ligand_stress",
            "source_argument": "--expected-keys-csv",
            "source_artifact_path": "runs/demo_stage1_queue.csv",
            "source_artifact_present": "false",
            "source_artifact_missing": "true",
            "pipeline_summary_json": (
                "runs/external_validation_blind_runs/demo/set1_core_blind/files/gpcr/demo_summary.json"
            ),
            "pipeline_summary_present": "true",
            "profile_json": "config/demo_profile.json",
            "required_action": "restore",
            "operator_action_required": "true",
            "execution_enabled": "false",
            "external_state_mutated": "false",
            "claim_promotion_allowed": "false",
        },
    ]
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def test_stage5_restore_packet_blocks_missing_source_csvs(tmp_path: Path) -> None:
    _write_stage5_input_family(tmp_path)

    payload = mod.build_developer_preview_stage5_restore_packet(root=tmp_path)
    summary = payload["summary"]

    assert summary["status"] == "blocked_developer_preview_stage5_restore_packet"
    assert summary["developer_preview_stage5_restore_packet_ready"] is False
    assert summary["stage5_restore_ready"] is False
    assert summary["restore_ready"] is False
    assert summary["input_present"] is True
    assert summary["row_count"] == 4
    assert summary["total_rows"] == 4
    assert summary["task_count"] == 1
    assert summary["incomplete_task_count"] == 1
    assert summary["source_artifact_present_count"] == 1
    assert summary["missing_source_artifact_count"] == 3
    assert summary["missing_source_artifact_paths"] == [
        "runs/demo_hard_decoy_labels.csv",
        "runs/demo_hard_decoy_split.csv",
        "runs/demo_stage1_queue.csv",
    ]
    assert summary["pipeline_summary_present_count"] == 4
    assert summary["profile_present_count"] == 4
    assert summary["stage5_fail_closed_restore_receipt_ready"] is True
    assert summary["stage5_operator_restore_queue_ready"] is True
    assert summary["stage5_operator_restore_queue_row_count"] == 3
    assert summary["restore_queue_ready"] is True
    assert summary["restore_queue_ready_count"] == 3
    assert summary["operator_restore_sequence_ready"] is True
    assert summary["operator_restore_sequence_step_count"] == 4
    assert summary["operator_restore_sequence"][0].startswith(
        "Review rows where operator_action_required=true"
    )
    assert summary["operator_restore_sequence"][-1] == (
        "Rerun python3 tools/product/build_developer_preview_clean_checkout_benchmark_receipt.py "
        "--allow-blocked with the reviewed clean-checkout evidence."
    )
    assert summary["all_missing_rows_have_pipeline_summary"] is True
    assert summary["all_missing_rows_have_profile"] is True
    assert summary["stage5_restore_rebuild_command"] == (
        "python3 tools/product/build_developer_preview_stage5_restore_packet.py"
    )
    assert summary["clean_checkout_receipt_rebuild_command"] == (
        "python3 tools/product/build_developer_preview_clean_checkout_benchmark_receipt.py --allow-blocked"
    )
    assert summary["missing_source_artifact_count_by_argument"] == {
        "--labels-csv": 1,
        "--split-csv": 1,
        "--expected-keys-csv": 1,
    }
    assert summary["primary_missing_source_argument"] == "--labels-csv"
    assert (
        summary["primary_missing_source_artifact_path"]
        == "runs/demo_hard_decoy_labels.csv"
    )
    assert summary["primary_missing_pipeline_summary_json"] == (
        "runs/external_validation_blind_runs/demo/set1_core_blind/files/gpcr/demo_summary.json"
    )
    assert summary["primary_missing_pipeline_summary_present"] is True
    assert summary["primary_missing_profile_json"] == "config/demo_profile.json"
    assert summary["primary_missing_profile_present"] is True
    assert summary["primary_missing_restore_queue_ready"] is True
    assert summary["primary_missing_row_blocker"] == "runs/demo_hard_decoy_labels.csv:missing"
    assert "runs/demo_hard_decoy_labels.csv" in summary["primary_missing_restore_instruction"]
    assert "config/demo_profile.json" in summary["primary_missing_restore_instruction"]
    assert summary["blocker_count"] == 1
    assert summary["primary_blocker"] == "stage5_source_artifacts_missing:3"
    assert summary["execution_enabled"] is False
    assert summary["external_state_mutated"] is False
    assert summary["claim_promotion_allowed"] is False
    assert payload["rows"][0]["source_artifact_present"] is True
    assert payload["rows"][0]["operator_action_required"] is False
    assert payload["rows"][0]["row_blocker"] == ""
    assert payload["rows"][0]["restore_queue_ready"] is False
    assert payload["rows"][1]["task_source_required_count"] == 4
    assert payload["rows"][1]["task_source_missing_count"] == 3
    assert payload["rows"][1]["source_artifact_parent_dir"] == "runs"
    assert payload["rows"][1]["source_artifact_filename"] == "demo_hard_decoy_labels.csv"
    assert payload["rows"][1]["row_blocker"] == "runs/demo_hard_decoy_labels.csv:missing"
    assert payload["rows"][1]["restore_queue_ready"] is True
    assert "approved clean-checkout baseline" in payload["rows"][1][
        "operator_restore_instruction"
    ]
    rendered_md = mod._render_md(payload)
    assert "## Primary Restore Target" in rendered_md
    assert "- source_argument: `--labels-csv`" in rendered_md
    assert "- source_artifact_path: `runs/demo_hard_decoy_labels.csv`" in rendered_md
    assert (
        "- pipeline_summary_json: "
        "`runs/external_validation_blind_runs/demo/set1_core_blind/files/gpcr/demo_summary.json`"
        in rendered_md
    )
    assert "- profile_json: `config/demo_profile.json`" in rendered_md
    assert "- restore_queue_ready: `true`" in rendered_md


def test_stage5_restore_packet_fails_closed_when_input_family_missing(tmp_path: Path) -> None:
    payload = mod.build_developer_preview_stage5_restore_packet(root=tmp_path)
    summary = payload["summary"]

    assert summary["status"] == "blocked_developer_preview_stage5_restore_packet"
    assert summary["stage5_input_family_csv_present"] is False
    assert summary["input_present"] is False
    assert summary["row_count"] == 0
    assert summary["total_rows"] == 0
    assert summary["stage5_fail_closed_restore_receipt_ready"] is False
    assert summary["stage5_operator_restore_queue_ready"] is False
    assert summary["stage5_operator_restore_queue_row_count"] == 0
    assert summary["restore_queue_ready"] is False
    assert summary["restore_queue_ready_count"] == 0
    assert summary["operator_restore_sequence_ready"] is False
    assert summary["operator_restore_sequence_step_count"] == 4
    assert summary["blocker_count"] == 2
    assert summary["blockers"] == [
        ".betelgeuze/developer_preview_clean_checkout_stage5_input_family_current.csv:missing",
        "stage5_input_family_rows:missing",
    ]
    assert payload["rows"] == []

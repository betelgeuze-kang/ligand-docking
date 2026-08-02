from __future__ import annotations

import json
from pathlib import Path

from tools.product import build_competition_benchmark_custody_work_order as mod


def _write_json(path: Path, summary: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"summary": summary}, indent=2) + "\n", encoding="utf-8")
    return path


def test_competition_benchmark_custody_work_order_surfaces_receipt_and_raw_gaps(
    tmp_path: Path,
) -> None:
    casp16 = _write_json(
        tmp_path / "runs/casp16_ligand_source_manifest_current.json",
        {
            "suite_id": "casp16_ligand_pose_affinity",
            "local_source_manifest_csv_present": False,
            "local_source_manifest_csv": "data/competition_benchmarks/casp16_ligand/source_manifest.csv",
            "local_checksum_manifest_present": False,
            "local_checksum_manifest": "data/competition_benchmarks/casp16_ligand/checksums.sha256",
            "local_materialization_manifest_present": False,
            "local_materialization_manifest": "runs/casp16_ligand_materialization_manifest_current.json",
            "scorecard_json_present": False,
            "scorecard_json": "runs/casp16_ligand_scorecard_current.json",
            "raw_data_committed": False,
        },
    )
    bm5 = _write_json(
        tmp_path / "runs/bm5_capri_complex_source_manifest_current.json",
        {
            "suite_id": "bm5_capri_complex_benchmark",
            "capri_source_ready": False,
            "capri_score_set_source_manifest": "data/competition_benchmarks/capri_score_set/source_manifest.csv",
            "capri_score_set_checksum_manifest": "data/competition_benchmarks/capri_score_set/checksums.sha256",
            "capri_materialization_ready": False,
            "capri_score_set_materialization_manifest": "data/competition_benchmarks/capri_score_set/materialization_manifest.json",
            "capri_scorecard_ready": False,
            "capri_score_set_scorecard_json": "runs/capri_score_set_scorecard_current.json",
            "raw_data_committed": True,
            "raw_data_git_tracked_file_count": 2802,
            "raw_data_git_tracked_sample_paths": [
                "HADDOCK-ready/1A2K/1A2K_l_b-matched.pdb"
            ],
        },
    )
    bm5_untrack_preflight = _write_json(
        tmp_path / "runs/bm5_capri_raw_data_untrack_apply_preflight_current.json",
        {
            "status": "bm5_capri_raw_data_untrack_apply_preflight_ready",
            "preview_ready": True,
            "generated_untrack_candidate_manifest_path": (
                "runs/bm5_capri_raw_data_untrack_candidates_current.txt"
            ),
            "untrack_candidate_manifest_path": (
                "runs/bm5_capri_raw_data_untrack_candidates_current.txt"
            ),
            "reviewed_untrack_manifest_template_path": (
                "runs/bm5_capri_raw_data_reviewed_untrack_manifest_template_current.txt"
            ),
            "operator_reviewed_untrack_manifest_path": (
                "OPERATOR_REVIEWED_BM5_CAPRI_RAW_DATA_UNTRACK_PATHS.txt"
            ),
            "untrack_candidate_count": 2802,
            "custody_plan_raw_data_path_count": 2802,
            "untrack_candidates_match_custody_plan": True,
            "preview_command": (
                "python3 tools/apply_bm5_capri_raw_data_custody_plan.py --mode preview "
                "--untrack-candidates OPERATOR_REVIEWED_BM5_CAPRI_RAW_DATA_UNTRACK_PATHS.txt"
            ),
            "execute_command": (
                "python3 tools/apply_bm5_capri_raw_data_custody_plan.py --mode execute "
                "--untrack-candidates OPERATOR_REVIEWED_BM5_CAPRI_RAW_DATA_UNTRACK_PATHS.txt "
                "--approval-token APPROVE_BM5_CAPRI_RAW_DATA_UNTRACK"
            ),
            "approval_token_required": "APPROVE_BM5_CAPRI_RAW_DATA_UNTRACK",
            "candidate_manifest_required_for_execute": True,
            "candidate_manifest_operator_review_required": True,
            "preview_mutates_git_index": False,
            "execute_mutates_git_index": True,
            "execute_requires_approval_token": True,
            "execute_requires_operator_reviewed_manifest": True,
            "execute_deletes_files": False,
            "execute_mutates_external_state": False,
            "post_execute_verification_command": (
                "python3 tools/build_bm5_capri_raw_data_custody_plan.py --compute-sha256"
            ),
            "operator_review_handoff": (
                "Review runs/bm5_capri_raw_data_reviewed_untrack_manifest_template_current.txt "
                "before copying to OPERATOR_REVIEWED_BM5_CAPRI_RAW_DATA_UNTRACK_PATHS.txt."
            ),
            "next_required_step": "Review the preflight receipt before execute.",
        },
    )

    payload = mod.build_competition_benchmark_custody_work_order(
        casp16_ligand_manifest_json=casp16,
        bm5_capri_complex_manifest_json=bm5,
        bm5_capri_untrack_apply_preflight_json=bm5_untrack_preflight,
        root=tmp_path,
    )
    summary = payload["summary"]
    rows = {row["work_order_id"]: row for row in payload["rows"]}
    markdown = mod._render_md(payload)

    assert summary["status"] == "blocked_competition_benchmark_custody_work_order"
    assert summary["custody_work_order_ready"] is False
    assert summary["operator_action_required_count"] == 3
    assert summary["raw_data_custody_blocked_row_count"] == 1
    assert summary["missing_receipt_row_count"] == 2
    assert summary["raw_data_git_tracked_file_count"] == 2802
    assert summary["primary_work_order_id"] == "casp16_ligand_operator_receipts_missing"
    assert summary["primary_raw_data_work_order_id"] == "bm5_capri_raw_data_custody"
    assert summary["primary_raw_data_git_tracked_file_count"] == 2802
    assert summary["primary_raw_data_git_tracked_sample_paths"] == [
        "HADDOCK-ready/1A2K/1A2K_l_b-matched.pdb"
    ]
    assert summary["bm5_capri_raw_data_untrack_apply_preflight_status"] == (
        "bm5_capri_raw_data_untrack_apply_preflight_ready"
    )
    assert summary["bm5_capri_raw_data_untrack_apply_preflight_ready"] is True
    assert summary["bm5_capri_raw_data_untrack_apply_preflight_json"] == (
        "runs/bm5_capri_raw_data_untrack_apply_preflight_current.json"
    )
    assert summary[
        "bm5_capri_raw_data_untrack_apply_generated_candidate_manifest_path"
    ] == "runs/bm5_capri_raw_data_untrack_candidates_current.txt"
    assert summary[
        "bm5_capri_raw_data_untrack_apply_candidate_manifest_path"
    ] == "runs/bm5_capri_raw_data_untrack_candidates_current.txt"
    assert summary[
        "bm5_capri_raw_data_untrack_apply_reviewed_manifest_template_path"
    ] == "runs/bm5_capri_raw_data_reviewed_untrack_manifest_template_current.txt"
    assert summary[
        "bm5_capri_raw_data_untrack_apply_operator_reviewed_manifest_path"
    ] == "OPERATOR_REVIEWED_BM5_CAPRI_RAW_DATA_UNTRACK_PATHS.txt"
    assert summary["bm5_capri_raw_data_untrack_apply_untrack_candidate_count"] == 2802
    assert (
        summary["bm5_capri_raw_data_untrack_apply_custody_plan_raw_data_path_count"]
        == 2802
    )
    assert summary[
        "bm5_capri_raw_data_untrack_apply_candidates_match_custody_plan"
    ] is True
    assert (
        "bm5_capri_raw_data_reviewed_untrack_manifest_template_current.txt"
        in summary["bm5_capri_raw_data_untrack_apply_operator_review_handoff"]
    )
    assert summary["bm5_capri_raw_data_untrack_apply_approval_token_required"] == (
        "APPROVE_BM5_CAPRI_RAW_DATA_UNTRACK"
    )
    assert "--mode preview" in summary["bm5_capri_raw_data_untrack_apply_preview_command"]
    assert "--mode execute" in summary["bm5_capri_raw_data_untrack_apply_execute_command"]
    assert "OPERATOR_REVIEWED_BM5_CAPRI_RAW_DATA_UNTRACK_PATHS.txt" in summary[
        "bm5_capri_raw_data_untrack_apply_execute_command"
    ]
    assert summary[
        "bm5_capri_raw_data_untrack_apply_candidate_manifest_required_for_execute"
    ] is True
    assert summary[
        "bm5_capri_raw_data_untrack_apply_candidate_manifest_operator_review_required"
    ] is True
    assert summary["bm5_capri_raw_data_untrack_apply_preview_mutates_git_index"] is False
    assert summary["bm5_capri_raw_data_untrack_apply_execute_mutates_git_index"] is True
    assert summary[
        "bm5_capri_raw_data_untrack_apply_execute_requires_approval_token"
    ] is True
    assert summary[
        "bm5_capri_raw_data_untrack_apply_execute_requires_operator_reviewed_manifest"
    ] is True
    assert summary["bm5_capri_raw_data_untrack_apply_execute_deletes_files"] is False
    assert summary[
        "bm5_capri_raw_data_untrack_apply_execute_mutates_external_state"
    ] is False
    assert "BM5/CAPRI raw structures" in summary["primary_raw_data_required_action"]
    assert "tools/build_bm5_capri_raw_data_custody_plan.py" in summary[
        "primary_raw_data_verification_command"
    ]
    assert "--compute-sha256" in summary["primary_raw_data_verification_command"]
    assert summary["casp16_ligand_operator_input_schema_ready"] is True
    assert summary["casp16_ligand_source_manifest_required_columns"] == [
        "target_id",
        "source_url",
        "sha256",
    ]
    assert summary["casp16_ligand_scorecard_required_columns"] == [
        "target_id",
        "task_type",
        "metric_name",
        "metric_value",
        "result_source",
    ]
    assert summary["casp16_ligand_operator_source_manifest_template_csv"] == (
        "runs/casp16_ligand_operator_source_manifest_template_current.csv"
    )
    assert summary["casp16_ligand_operator_checksum_manifest_template"] == (
        "runs/casp16_ligand_operator_checksum_manifest_template_current.sha256"
    )
    assert summary["casp16_ligand_operator_scorecard_rows_template_csv"] == (
        "runs/casp16_ligand_operator_scorecard_rows_template_current.csv"
    )
    assert summary["casp16_ligand_operator_receipt_fill_in_md"] == (
        "runs/casp16_ligand_operator_receipt_fill_in_current.md"
    )
    assert summary["casp16_ligand_operator_templates_written"] is False
    assert "casp16_ligand_operator_source_manifest_template_current.csv" in summary[
        "casp16_ligand_operator_template_artifacts"
    ]
    assert rows["casp16_ligand_operator_receipts_missing"]["operator_input_schema"][
        "scorecard_allowed_metrics"
    ] == ["LDDT-PLI", "Kendall_tau"]
    assert rows["casp16_ligand_operator_receipts_missing"][
        "operator_source_manifest_template_csv"
    ] == "runs/casp16_ligand_operator_source_manifest_template_current.csv"
    assert rows["casp16_ligand_operator_receipts_missing"][
        "operator_checksum_manifest_template"
    ] == "runs/casp16_ligand_operator_checksum_manifest_template_current.sha256"
    assert rows["casp16_ligand_operator_receipts_missing"][
        "operator_scorecard_rows_template_csv"
    ] == "runs/casp16_ligand_operator_scorecard_rows_template_current.csv"
    assert rows["casp16_ligand_operator_receipts_missing"][
        "operator_receipt_fill_in_md"
    ] == "runs/casp16_ligand_operator_receipt_fill_in_current.md"
    assert rows["casp16_ligand_operator_receipts_missing"]["operator_input_schema"][
        "operator_source_manifest_template_csv"
    ] == "runs/casp16_ligand_operator_source_manifest_template_current.csv"
    assert rows["casp16_ligand_operator_receipts_missing"]["missing_receipt_count"] == 4
    assert "tools/build_casp16_ligand_materialization_manifest.py" in rows[
        "casp16_ligand_operator_receipts_missing"
    ]["verification_command"]
    assert "runs/casp16_ligand_materialization_manifest_current.json" in rows[
        "casp16_ligand_operator_receipts_missing"
    ]["verification_command"]
    assert "tools/build_casp16_ligand_scorecard.py" in rows[
        "casp16_ligand_operator_receipts_missing"
    ]["verification_command"]
    assert "--scorecard-rows-csv OPERATOR_REVIEWED_SCORECARD_ROWS_CSV" in rows[
        "casp16_ligand_operator_receipts_missing"
    ]["verification_command"]
    assert rows["capri_score_set_operator_receipts_missing"]["missing_receipt_count"] == 4
    assert rows["bm5_capri_raw_data_custody"]["raw_data_git_tracked_file_count"] == 2802
    assert rows["bm5_capri_raw_data_custody"]["raw_data_git_tracked_sample_paths"] == [
        "HADDOCK-ready/1A2K/1A2K_l_b-matched.pdb"
    ]
    assert rows["bm5_capri_raw_data_custody"][
        "raw_data_untrack_apply_preflight_ready"
    ] is True
    assert rows["bm5_capri_raw_data_custody"][
        "raw_data_untrack_apply_approval_token_required"
    ] == "APPROVE_BM5_CAPRI_RAW_DATA_UNTRACK"
    assert rows["bm5_capri_raw_data_custody"][
        "raw_data_untrack_apply_preflight_json"
    ] == "runs/bm5_capri_raw_data_untrack_apply_preflight_current.json"
    assert rows["bm5_capri_raw_data_custody"][
        "raw_data_untrack_apply_generated_candidate_manifest_path"
    ] == "runs/bm5_capri_raw_data_untrack_candidates_current.txt"
    assert rows["bm5_capri_raw_data_custody"][
        "raw_data_untrack_apply_reviewed_manifest_template_path"
    ] == "runs/bm5_capri_raw_data_reviewed_untrack_manifest_template_current.txt"
    assert rows["bm5_capri_raw_data_custody"][
        "raw_data_untrack_apply_untrack_candidate_count"
    ] == 2802
    assert rows["bm5_capri_raw_data_custody"][
        "raw_data_untrack_apply_candidates_match_custody_plan"
    ] is True
    assert "OPERATOR_REVIEWED_BM5_CAPRI_RAW_DATA_UNTRACK_PATHS.txt" in rows[
        "bm5_capri_raw_data_custody"
    ]["raw_data_untrack_apply_execute_command"]
    assert rows["bm5_capri_raw_data_custody"][
        "raw_data_untrack_apply_candidate_manifest_required_for_execute"
    ] is True
    assert rows["bm5_capri_raw_data_custody"][
        "raw_data_untrack_apply_candidate_manifest_operator_review_required"
    ] is True
    assert rows["bm5_capri_raw_data_custody"][
        "raw_data_untrack_apply_preview_mutates_git_index"
    ] is False
    assert rows["bm5_capri_raw_data_custody"][
        "raw_data_untrack_apply_execute_mutates_git_index"
    ] is True
    assert rows["bm5_capri_raw_data_custody"][
        "raw_data_untrack_apply_execute_requires_operator_reviewed_manifest"
    ] is True
    assert "OPERATOR_REVIEWED_BM5_CAPRI_RAW_DATA_UNTRACK_PATHS.txt" in markdown
    assert "bm5_capri_raw_data_reviewed_untrack_manifest_template_current.txt" in markdown
    assert "execute_mutates_git_index" in markdown
    assert "casp16_ligand_operator_source_manifest_template_current.csv" in markdown
    assert "tools/build_bm5_capri_raw_data_custody_plan.py" in rows[
        "bm5_capri_raw_data_custody"
    ]["verification_command"]
    assert "--compute-sha256" in rows["bm5_capri_raw_data_custody"][
        "verification_command"
    ]
    assert rows["bm5_capri_raw_data_custody"]["execution_enabled"] is False
    assert rows["bm5_capri_raw_data_custody"]["external_state_mutated"] is False


def test_competition_benchmark_custody_work_order_ready_when_no_gaps(tmp_path: Path) -> None:
    casp16 = _write_json(
        tmp_path / "runs/casp16_ligand_source_manifest_current.json",
        {
            "suite_id": "casp16_ligand_pose_affinity",
            "local_source_manifest_csv_present": True,
            "local_checksum_manifest_present": True,
            "local_materialization_manifest_present": True,
            "scorecard_json_present": True,
            "raw_data_committed": False,
        },
    )
    bm5 = _write_json(
        tmp_path / "runs/bm5_capri_complex_source_manifest_current.json",
        {
            "suite_id": "bm5_capri_complex_benchmark",
            "capri_source_ready": True,
            "capri_materialization_ready": True,
            "capri_scorecard_ready": True,
            "raw_data_committed": False,
        },
    )

    payload = mod.build_competition_benchmark_custody_work_order(
        casp16_ligand_manifest_json=casp16,
        bm5_capri_complex_manifest_json=bm5,
        root=tmp_path,
    )
    summary = payload["summary"]

    assert summary["status"] == "competition_benchmark_custody_work_order_ready"
    assert summary["custody_work_order_ready"] is True
    assert summary["operator_action_required_count"] == 0
    assert summary["primary_raw_data_work_order_id"] == ""
    assert summary["primary_raw_data_git_tracked_file_count"] == 0
    assert summary["primary_raw_data_git_tracked_sample_paths"] == []
    assert summary["bm5_capri_raw_data_untrack_apply_preflight_ready"] is False
    assert summary["casp16_ligand_operator_input_schema_ready"] is True
    assert summary["casp16_ligand_operator_templates_written"] is False
    assert payload["rows"] == []


def test_competition_benchmark_custody_work_order_cli_writes_outputs(tmp_path: Path) -> None:
    casp16 = _write_json(
        tmp_path / "runs/casp16_ligand_source_manifest_current.json",
        {"local_source_manifest_csv_present": True, "local_checksum_manifest_present": True, "local_materialization_manifest_present": True, "scorecard_json_present": True},
    )
    bm5 = _write_json(
        tmp_path / "runs/bm5_capri_complex_source_manifest_current.json",
        {"capri_source_ready": True, "capri_materialization_ready": True, "capri_scorecard_ready": True},
    )
    out_json = tmp_path / "runs/competition_benchmark_custody_work_order_current.json"
    out_csv = tmp_path / "runs/competition_benchmark_custody_work_order_current.csv"
    out_md = tmp_path / "runs/competition_benchmark_custody_work_order_current.md"

    assert mod.main(
        [
            "--casp16-ligand-manifest-json",
            str(casp16),
            "--bm5-capri-complex-manifest-json",
            str(bm5),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ]
    ) == 0

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["summary"]["packet_type"] == "competition_benchmark_custody_work_order"
    assert out_csv.read_text(encoding="utf-8").startswith("work_order_id,status,")
    assert "Competition Benchmark Custody Work Order" in out_md.read_text(encoding="utf-8")

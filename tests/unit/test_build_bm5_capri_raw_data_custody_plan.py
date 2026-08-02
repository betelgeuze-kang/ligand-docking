from __future__ import annotations

import json
import subprocess
from pathlib import Path

from tools.product import build_bm5_capri_raw_data_custody_plan as mod


def test_bm5_capri_raw_data_custody_plan_reports_clear_repo(tmp_path: Path) -> None:
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    bm5_dir = tmp_path / "data/public_benchmarks/protein_protein_docking_benchmark_v5"
    capri_dir = tmp_path / "data/competition_benchmarks/capri_score_set"
    bm5_dir.mkdir(parents=True)
    capri_dir.mkdir(parents=True)

    payload = mod.build_bm5_capri_raw_data_custody_plan(
        bm5_dataset_dir=bm5_dir,
        capri_score_set_dir=capri_dir,
        root=tmp_path,
    )
    summary = payload["summary"]

    assert summary["status"] == "bm5_capri_raw_data_custody_plan_ready"
    assert summary["custody_plan_ready"] is True
    assert summary["raw_data_custody_clear"] is True
    assert summary["raw_data_git_tracked_file_count"] == 0
    assert summary["raw_data_review_group_count"] == 0
    assert summary["raw_data_primary_review_group"] == ""
    assert summary["raw_data_primary_review_group_file_count"] == 0
    assert summary["approved_untrack_manifest_template"] == (
        "OPERATOR_REVIEWED_BM5_CAPRI_RAW_DATA_UNTRACK_PATHS.txt"
    )
    assert summary["approved_untrack_manifest_template_path"] == (
        "runs/bm5_capri_raw_data_reviewed_untrack_manifest_template_current.txt"
    )
    assert summary["approved_untrack_manifest_template_ready"] is False
    assert summary["review_group_manifest_path"] == (
        "runs/bm5_capri_raw_data_review_groups_current.csv"
    )
    assert summary["review_group_manifest_ready"] is False
    assert summary["checksum_manifest_ready"] is False
    assert summary["checksum_manifest_path"] == (
        "runs/bm5_capri_raw_data_custody_plan_current.sha256"
    )
    assert summary["untrack_candidate_manifest_ready"] is False
    assert summary["untrack_candidate_count"] == 0
    assert summary["operator_reviewed_untrack_manifest_required"] is False
    assert summary["operator_reviewed_untrack_manifest_path"] == (
        "OPERATOR_REVIEWED_BM5_CAPRI_RAW_DATA_UNTRACK_PATHS.txt"
    )
    assert summary["untrack_preview_mutates_git_index"] is False
    assert summary["untrack_execute_mutates_git_index"] is False
    assert summary["untrack_execute_requires_approval_token"] is False
    assert summary["untrack_execute_requires_operator_reviewed_manifest"] is False
    assert summary["untrack_execute_deletes_files"] is False
    assert summary["untrack_execute_mutates_external_state"] is False
    assert summary["materialization_manifest_ready"] is False
    assert summary["materialization_manifest_json_path"] == (
        "runs/bm5_capri_raw_data_materialization_manifest_current.json"
    )
    assert summary["execution_enabled"] is False
    assert summary["external_state_mutated"] is False
    assert payload["rows"] == []
    assert payload["review_group_rows"] == []


def test_bm5_capri_raw_data_custody_plan_inventories_tracked_raw_files(
    tmp_path: Path,
) -> None:
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    bm5_dir = tmp_path / "data/public_benchmarks/protein_protein_docking_benchmark_v5"
    capri_dir = tmp_path / "data/competition_benchmarks/capri_score_set"
    bm5_raw = bm5_dir / "structures-matched/tracked_bm5.pdb"
    capri_raw = capri_dir / "models/tracked_capri.cif"
    bm5_raw.parent.mkdir(parents=True)
    capri_raw.parent.mkdir(parents=True)
    bm5_raw.write_text("ATOM      1  N   GLY A   1      0.0 0.0 0.0\n", encoding="utf-8")
    capri_raw.write_text("data_capri\n", encoding="utf-8")
    subprocess.run(["git", "add", str(bm5_raw), str(capri_raw)], cwd=tmp_path, check=True, capture_output=True)

    payload = mod.build_bm5_capri_raw_data_custody_plan(
        bm5_dataset_dir=bm5_dir,
        capri_score_set_dir=capri_dir,
        external_custody_root="/external/custody",
        compute_sha256=True,
        root=tmp_path,
    )
    summary = payload["summary"]
    rows = {row["raw_data_scope"]: row for row in payload["rows"]}

    assert summary["status"] == "bm5_capri_raw_data_custody_plan_ready"
    assert summary["raw_data_custody_clear"] is False
    assert summary["raw_data_git_tracked_file_count"] == 2
    assert summary["bm5_raw_data_git_tracked_file_count"] == 1
    assert summary["capri_raw_data_git_tracked_file_count"] == 1
    assert summary["raw_data_review_group_count"] == 2
    assert summary["approved_untrack_command_template"] == (
        "git rm --cached --pathspec-from-file OPERATOR_REVIEWED_BM5_CAPRI_RAW_DATA_UNTRACK_PATHS.txt"
    )
    assert summary["approved_untrack_manifest_template_ready"] is True
    assert summary["review_group_manifest_ready"] is True
    assert summary["untrack_approval_token_required"] == (
        "APPROVE_BM5_CAPRI_RAW_DATA_UNTRACK"
    )
    assert summary["untrack_apply_preview_command"] == (
        "python3 tools/apply_bm5_capri_raw_data_custody_plan.py --mode preview "
        "--untrack-candidates OPERATOR_REVIEWED_BM5_CAPRI_RAW_DATA_UNTRACK_PATHS.txt"
    )
    assert summary["untrack_apply_execute_command"] == (
        "python3 tools/apply_bm5_capri_raw_data_custody_plan.py --mode execute "
        "--untrack-candidates OPERATOR_REVIEWED_BM5_CAPRI_RAW_DATA_UNTRACK_PATHS.txt "
        "--approval-token APPROVE_BM5_CAPRI_RAW_DATA_UNTRACK"
    )
    assert summary["sha256_computed"] is True
    assert summary["sha256_row_count"] == 2
    assert summary["checksum_manifest_ready"] is True
    assert summary["untrack_candidate_manifest_ready"] is True
    assert summary["untrack_candidate_count"] == 2
    assert summary["operator_reviewed_untrack_manifest_required"] is True
    assert summary["operator_reviewed_untrack_manifest_path"] == (
        "OPERATOR_REVIEWED_BM5_CAPRI_RAW_DATA_UNTRACK_PATHS.txt"
    )
    assert summary["untrack_preview_mutates_git_index"] is False
    assert summary["untrack_execute_mutates_git_index"] is True
    assert summary["untrack_execute_requires_approval_token"] is True
    assert summary["untrack_execute_requires_operator_reviewed_manifest"] is True
    assert summary["untrack_execute_deletes_files"] is False
    assert summary["untrack_execute_mutates_external_state"] is False
    assert summary["materialization_manifest_ready"] is True
    assert rows["bm5"]["git_tracked_path"].endswith("tracked_bm5.pdb")
    assert rows["bm5"]["proposed_external_path"].startswith("/external/custody/")
    assert len(rows["bm5"]["sha256"]) == 64
    assert rows["bm5"]["execution_enabled"] is False
    assert rows["capri_score_set"]["git_tracked_path"].endswith("tracked_capri.cif")
    review_groups = {
        (row["raw_data_scope"], row["review_group"]): row
        for row in payload["review_group_rows"]
    }
    assert review_groups[("bm5", "structures-matched")]["git_tracked_file_count"] == 1
    assert review_groups[("bm5", "structures-matched")]["file_suffixes"] == [".pdb"]
    assert review_groups[("capri_score_set", "models")]["git_tracked_file_count"] == 1
    assert review_groups[("capri_score_set", "models")]["sample_git_tracked_paths"][0].endswith(
        "tracked_capri.cif"
    )


def test_bm5_capri_raw_data_custody_plan_cli_writes_outputs(tmp_path: Path) -> None:
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    bm5_dir = tmp_path / "data/public_benchmarks/protein_protein_docking_benchmark_v5"
    capri_dir = tmp_path / "data/competition_benchmarks/capri_score_set"
    raw = bm5_dir / "tracked_raw.pdb"
    raw.parent.mkdir(parents=True)
    capri_dir.mkdir(parents=True)
    raw.write_text("ATOM\n", encoding="utf-8")
    subprocess.run(["git", "add", str(raw)], cwd=tmp_path, check=True, capture_output=True)
    out_json = tmp_path / "runs/bm5_capri_raw_data_custody_plan_current.json"
    out_csv = tmp_path / "runs/bm5_capri_raw_data_custody_plan_current.csv"
    out_md = tmp_path / "runs/bm5_capri_raw_data_custody_plan_current.md"
    out_checksums = tmp_path / "runs/bm5_capri_raw_data_custody_plan_current.sha256"
    out_untrack = tmp_path / "runs/bm5_capri_raw_data_untrack_candidates_current.txt"
    out_reviewed_template = (
        tmp_path / "runs/bm5_capri_raw_data_reviewed_untrack_manifest_template_current.txt"
    )
    out_review_groups = tmp_path / "runs/bm5_capri_raw_data_review_groups_current.csv"
    out_materialization_json = (
        tmp_path / "runs/bm5_capri_raw_data_materialization_manifest_current.json"
    )
    out_materialization_md = (
        tmp_path / "runs/bm5_capri_raw_data_materialization_manifest_current.md"
    )

    assert mod.main(
        [
            "--bm5-dataset-dir",
            str(bm5_dir),
            "--capri-score-set-dir",
            str(capri_dir),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
            "--out-checksums",
            str(out_checksums),
            "--out-untrack-candidates",
            str(out_untrack),
            "--out-approved-untrack-template",
            str(out_reviewed_template),
            "--out-review-group-csv",
            str(out_review_groups),
            "--out-materialization-json",
            str(out_materialization_json),
            "--out-materialization-md",
            str(out_materialization_md),
        ]
    ) == 0

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["summary"]["packet_type"] == "bm5_capri_raw_data_custody_plan"
    assert payload["summary"]["sha256_computed"] is False
    assert payload["summary"]["checksum_manifest_ready"] is False
    assert payload["summary"]["untrack_candidate_manifest_ready"] is True
    assert payload["summary"]["approved_untrack_manifest_template_ready"] is True
    assert payload["summary"]["operator_reviewed_untrack_manifest_required"] is True
    assert payload["summary"]["untrack_execute_mutates_git_index"] is True
    assert payload["summary"]["review_group_manifest_ready"] is True
    assert payload["summary"]["materialization_manifest_ready"] is False
    assert payload["summary"]["raw_data_review_group_count"] == 1
    assert out_csv.read_text(encoding="utf-8").startswith("raw_data_scope,git_tracked_path,")
    assert "BM5/CAPRI Raw-Data Custody Plan" in out_md.read_text(encoding="utf-8")
    assert "Review Groups" in out_md.read_text(encoding="utf-8")
    assert out_checksums.read_text(encoding="utf-8") == ""
    assert out_untrack.read_text(encoding="utf-8").endswith("tracked_raw.pdb\n")
    reviewed_template = out_reviewed_template.read_text(encoding="utf-8")
    assert "Operator review is required" in reviewed_template
    assert reviewed_template.endswith("tracked_raw.pdb\n")
    assert out_review_groups.read_text(encoding="utf-8").startswith(
        "raw_data_scope,review_group,git_tracked_file_count,"
    )
    materialization = json.loads(out_materialization_json.read_text(encoding="utf-8"))
    assert materialization["summary"]["packet_type"] == (
        "bm5_capri_raw_data_materialization_manifest"
    )
    assert materialization["summary"]["checksum_manifest_ready"] is False
    assert "BM5/CAPRI Raw-Data Materialization Manifest" in out_materialization_md.read_text(
        encoding="utf-8"
    )

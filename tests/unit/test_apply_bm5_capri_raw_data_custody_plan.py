from __future__ import annotations

import json
import subprocess
from pathlib import Path

from tools.product import apply_bm5_capri_raw_data_custody_plan as mod
from tools.product import build_bm5_capri_raw_data_custody_plan as plan_mod


def _tracked_raw_fixture(tmp_path: Path) -> tuple[Path, Path, Path]:
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    bm5_dir = tmp_path / "data/public_benchmarks/protein_protein_docking_benchmark_v5"
    capri_dir = tmp_path / "data/competition_benchmarks/capri_score_set"
    raw_path = bm5_dir / "structures-matched/tracked_bm5.pdb"
    raw_path.parent.mkdir(parents=True)
    capri_dir.mkdir(parents=True)
    raw_path.write_text("ATOM\n", encoding="utf-8")
    subprocess.run(["git", "add", str(raw_path)], cwd=tmp_path, check=True, capture_output=True)
    return bm5_dir, capri_dir, raw_path


def _write_plan_and_candidates(tmp_path: Path, bm5_dir: Path, capri_dir: Path) -> tuple[Path, Path]:
    payload = plan_mod.build_bm5_capri_raw_data_custody_plan(
        bm5_dataset_dir=bm5_dir,
        capri_score_set_dir=capri_dir,
        compute_sha256=True,
        root=tmp_path,
    )
    plan_path = tmp_path / "runs/bm5_capri_raw_data_custody_plan_current.json"
    candidates_path = tmp_path / "runs/bm5_capri_raw_data_untrack_candidates_current.txt"
    plan_path.parent.mkdir(parents=True)
    plan_path.write_text(json.dumps(payload), encoding="utf-8")
    candidates_path.write_text(
        "\n".join(row["git_tracked_path"] for row in payload["rows"]) + "\n",
        encoding="utf-8",
    )
    return plan_path, candidates_path


def _write_operator_reviewed_manifest(tmp_path: Path, candidates_path: Path) -> Path:
    reviewed_path = tmp_path / mod.DEFAULT_APPROVED_UNTRACK_MANIFEST
    reviewed_path.write_text(candidates_path.read_text(encoding="utf-8"), encoding="utf-8")
    return reviewed_path


def test_bm5_capri_raw_data_untrack_apply_preview_is_non_mutating(tmp_path: Path) -> None:
    bm5_dir, capri_dir, raw_path = _tracked_raw_fixture(tmp_path)
    plan_path, candidates_path = _write_plan_and_candidates(tmp_path, bm5_dir, capri_dir)

    payload = mod.build_bm5_capri_raw_data_untrack_apply(
        plan_json=plan_path,
        untrack_candidates=candidates_path,
        mode="preview",
        root=tmp_path,
    )
    summary = payload["summary"]

    assert summary["status"] == "bm5_capri_raw_data_untrack_apply_preflight_ready"
    assert summary["preview_ready"] is True
    assert summary["execution_enabled"] is False
    assert summary["local_git_index_mutated"] is False
    assert summary["file_delete_requested"] is False
    assert summary["external_state_mutated"] is False
    assert summary["untrack_candidates_match_custody_plan"] is True
    assert summary["tracked_candidate_count"] == 1
    assert summary["candidate_manifest_required_for_execute"] is True
    assert summary["candidate_manifest_operator_review_required"] is True
    assert summary["operator_reviewed_untrack_manifest_required"] is True
    assert summary["generated_untrack_candidate_manifest_path"] == (
        "runs/bm5_capri_raw_data_untrack_candidates_current.txt"
    )
    assert summary["reviewed_untrack_manifest_template_path"] == (
        "runs/bm5_capri_raw_data_reviewed_untrack_manifest_template_current.txt"
    )
    assert summary["reviewed_untrack_manifest_template_ready"] is True
    assert summary["operator_reviewed_untrack_manifest_path"] == (
        "OPERATOR_REVIEWED_BM5_CAPRI_RAW_DATA_UNTRACK_PATHS.txt"
    )
    assert summary["operator_reviewed_manifest_used"] is False
    assert summary["generated_untrack_candidate_manifest_used"] is True
    assert summary["reviewed_untrack_template_manifest_used"] is False
    assert (
        "Review runs/bm5_capri_raw_data_reviewed_untrack_manifest_template_current.txt"
        in summary["operator_review_handoff"]
    )
    assert summary["preview_mutates_git_index"] is False
    assert summary["execute_mutates_git_index"] is True
    assert summary["execute_would_mutate_git_index"] is False
    assert summary["execute_requires_approval_token"] is True
    assert summary["execute_requires_operator_reviewed_manifest"] is True
    assert summary["execute_deletes_files"] is False
    assert summary["execute_mutates_external_state"] is False
    assert summary["preview_command"] == (
        "python3 tools/apply_bm5_capri_raw_data_custody_plan.py --mode preview "
        "--untrack-candidates OPERATOR_REVIEWED_BM5_CAPRI_RAW_DATA_UNTRACK_PATHS.txt"
    )
    assert summary["execute_command"] == (
        "python3 tools/apply_bm5_capri_raw_data_custody_plan.py --mode execute "
        "--untrack-candidates OPERATOR_REVIEWED_BM5_CAPRI_RAW_DATA_UNTRACK_PATHS.txt "
        "--approval-token APPROVE_BM5_CAPRI_RAW_DATA_UNTRACK"
    )
    assert raw_path.exists()
    listed = subprocess.run(
        ["git", "ls-files", "--", str(raw_path.relative_to(tmp_path))],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    assert "tracked_bm5.pdb" in listed


def test_bm5_capri_raw_data_untrack_apply_execute_requires_approval_token(
    tmp_path: Path,
) -> None:
    bm5_dir, capri_dir, raw_path = _tracked_raw_fixture(tmp_path)
    plan_path, candidates_path = _write_plan_and_candidates(tmp_path, bm5_dir, capri_dir)
    reviewed_path = _write_operator_reviewed_manifest(tmp_path, candidates_path)

    payload = mod.build_bm5_capri_raw_data_untrack_apply(
        plan_json=plan_path,
        untrack_candidates=reviewed_path,
        mode="execute",
        approval_token="",
        root=tmp_path,
    )
    summary = payload["summary"]

    assert summary["status"] == "blocked_bm5_capri_raw_data_untrack_apply"
    assert "approval_token_missing_or_invalid" in summary["blockers"]
    assert summary["execution_enabled"] is False
    assert summary["local_git_index_mutated"] is False
    assert summary["execute_would_mutate_git_index"] is False
    assert summary["execute_requires_approval_token"] is True
    assert summary["execute_requires_operator_reviewed_manifest"] is True
    assert summary["operator_reviewed_manifest_used"] is True
    assert raw_path.exists()
    listed = subprocess.run(
        ["git", "ls-files", "--", str(raw_path.relative_to(tmp_path))],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    assert "tracked_bm5.pdb" in listed


def test_bm5_capri_raw_data_untrack_apply_execute_untracks_without_deleting(
    tmp_path: Path,
) -> None:
    bm5_dir, capri_dir, raw_path = _tracked_raw_fixture(tmp_path)
    plan_path, candidates_path = _write_plan_and_candidates(tmp_path, bm5_dir, capri_dir)
    reviewed_path = _write_operator_reviewed_manifest(tmp_path, candidates_path)

    payload = mod.build_bm5_capri_raw_data_untrack_apply(
        plan_json=plan_path,
        untrack_candidates=reviewed_path,
        mode="execute",
        approval_token=mod.UNTRACK_APPROVAL_TOKEN,
        root=tmp_path,
    )
    summary = payload["summary"]

    assert summary["status"] == "bm5_capri_raw_data_untrack_apply_executed"
    assert summary["execute_ready"] is True
    assert summary["execution_enabled"] is True
    assert summary["local_git_index_mutated"] is True
    assert summary["execute_would_mutate_git_index"] is True
    assert summary["execute_mutates_git_index"] is True
    assert summary["operator_reviewed_manifest_used"] is True
    assert summary["execute_deletes_files"] is False
    assert summary["file_delete_requested"] is False
    assert summary["external_state_mutated"] is False
    assert raw_path.exists()
    listed = subprocess.run(
        ["git", "ls-files", "--", str(raw_path.relative_to(tmp_path))],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    assert listed == ""


def test_bm5_capri_raw_data_untrack_apply_execute_rejects_generated_manifest(
    tmp_path: Path,
) -> None:
    bm5_dir, capri_dir, raw_path = _tracked_raw_fixture(tmp_path)
    plan_path, candidates_path = _write_plan_and_candidates(tmp_path, bm5_dir, capri_dir)

    payload = mod.build_bm5_capri_raw_data_untrack_apply(
        plan_json=plan_path,
        untrack_candidates=candidates_path,
        mode="execute",
        approval_token=mod.UNTRACK_APPROVAL_TOKEN,
        root=tmp_path,
    )
    summary = payload["summary"]

    assert summary["status"] == "blocked_bm5_capri_raw_data_untrack_apply"
    assert "operator_reviewed_untrack_manifest_not_used" in summary["blockers"]
    assert summary["operator_reviewed_manifest_used"] is False
    assert summary["generated_untrack_candidate_manifest_used"] is True
    assert summary["execute_would_mutate_git_index"] is False
    assert summary["local_git_index_mutated"] is False
    assert raw_path.exists()
    listed = subprocess.run(
        ["git", "ls-files", "--", str(raw_path.relative_to(tmp_path))],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    assert "tracked_bm5.pdb" in listed


def test_bm5_capri_raw_data_untrack_apply_rejects_paths_outside_allowed_roots(
    tmp_path: Path,
) -> None:
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    plan_path = tmp_path / "runs/bm5_capri_raw_data_custody_plan_current.json"
    candidates_path = tmp_path / "runs/bm5_capri_raw_data_untrack_candidates_current.txt"
    rogue = tmp_path / "README.pdb"
    rogue.write_text("ATOM\n", encoding="utf-8")
    subprocess.run(["git", "add", str(rogue)], cwd=tmp_path, check=True, capture_output=True)
    plan_path.parent.mkdir(parents=True)
    plan_path.write_text(
        json.dumps({"summary": {}, "rows": [{"git_tracked_path": "README.pdb"}]}),
        encoding="utf-8",
    )
    candidates_path.write_text("README.pdb\n", encoding="utf-8")

    payload = mod.build_bm5_capri_raw_data_untrack_apply(
        plan_json=plan_path,
        untrack_candidates=candidates_path,
        mode="preview",
        root=tmp_path,
    )

    assert payload["summary"]["status"] == "blocked_bm5_capri_raw_data_untrack_apply"
    assert payload["summary"]["path_outside_allowed_roots_count"] == 1
    assert "path_outside_allowed_roots:README.pdb" in payload["summary"]["blockers"]

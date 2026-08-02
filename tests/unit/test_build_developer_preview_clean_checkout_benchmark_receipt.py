from __future__ import annotations

import json
from pathlib import Path

from tools.product import build_developer_preview_clean_checkout_benchmark_receipt as mod


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _write_ready_sources(root: Path) -> tuple[Path, Path, Path]:
    ai_verify_log = root / ".betelgeuze/developer_preview_clean_checkout_ai_verify.log"
    ai_verify_log.parent.mkdir(parents=True, exist_ok=True)
    ai_verify_log.write_text("==> python syntax smoke\nverify ok (smoke)\n", encoding="utf-8")
    provenance = root / ".betelgeuze/developer_preview_clean_checkout_source_provenance.json"
    _write_json(
        provenance,
        {
            "summary": {
                "packet_type": "developer_preview_clean_checkout_source_provenance",
                "schema_version": "developer_preview_clean_checkout_source_provenance_v1",
                "source_repo_url_present": True,
                "source_repo_url_fingerprint": "abc123",
                "source_ref_requested": "codex/developer-preview",
                "source_ref_requested_present": True,
                "source_checked_out_ref": "HEAD",
                "source_remote_url_redacted": "sha256:abc123",
                "head_sha": "a" * 40,
                "tracked_file_count": 12,
                "git_status_porcelain_empty": True,
                "working_tree_clean": True,
                "dirty_path_count": 0,
                "execution_enabled": False,
                "external_state_mutated": False,
                "claim_promotion_allowed": False,
            }
        },
    )

    bundle_root = root / ".betelgeuze/developer_preview_external_baselines" / (
        "biorxiv_baseline_comparison_developer_preview_clean_checkout"
    )
    ranking_summary = bundle_root / "tasks/set1__gpcr/current_summary.json"
    _write_json(ranking_summary, {"metrics_unique": {"pr_auc": 1.0}})
    (bundle_root / "score_leaderboard.csv").parent.mkdir(parents=True, exist_ok=True)
    (bundle_root / "score_leaderboard.csv").write_text(
        "score_alias,score_col,task_count,wins_pr_auc\n"
        "composite_v7,binding_score_composite_v7,1,1\n",
        encoding="utf-8",
    )
    baseline_summary = bundle_root / "summary.json"
    _write_json(
        baseline_summary,
        {
            "bundle_root": str(bundle_root),
            "task_count": 1,
            "task_winner_count_current": 1,
            "task_winner_count_noncurrent": 0,
            "score_leaderboard": [
                {
                    "score_alias": "composite_v7",
                    "score_col": "binding_score_composite_v7",
                    "task_count": 1,
                    "wins_pr_auc": 1,
                }
            ],
            "tasks": [
                {
                    "set_id": "set1",
                    "task_id": "gpcr",
                    "current_score_col": "binding_score_composite_v7",
                    "score_rows": [
                        {
                            "score_col": "binding_score_composite_v7",
                            "ranking_summary_json": str(ranking_summary),
                        }
                    ],
                }
            ],
        },
    )
    return ai_verify_log, baseline_summary, provenance


def test_clean_checkout_benchmark_receipt_ready_after_review(tmp_path: Path) -> None:
    ai_verify_log, baseline_summary, provenance = _write_ready_sources(tmp_path)

    payload = mod.build_developer_preview_clean_checkout_benchmark_receipt(
        ai_verify_log=ai_verify_log,
        baseline_summary_json=baseline_summary,
        checkout_provenance_json=provenance,
        reviewed_receipt_attached=True,
        reviewer_id="operator-a",
        reviewed_at_utc="2026-07-03T00:00:00Z",
        root=tmp_path,
    )
    summary = payload["summary"]

    assert summary["status"] == "developer_preview_clean_checkout_benchmark_receipt_ready"
    assert summary["clean_checkout_benchmark_regenerated"] is True
    assert summary["ai_verify_passed"] is True
    assert summary["reviewed_receipt_attached"] is True
    assert summary["clean_checkout_provenance_ready"] is True
    assert summary["clean_checkout_source_repo_url_present"] is True
    assert summary["clean_checkout_source_ref_requested"] == "codex/developer-preview"
    assert summary["clean_checkout_source_ref_requested_present"] is True
    assert summary["clean_checkout_source_checked_out_ref"] == "HEAD"
    assert summary["clean_checkout_source_remote_url_redacted"] == "sha256:abc123"
    assert summary["clean_checkout_head_sha"] == "a" * 40
    assert summary["clean_checkout_tracked_file_count"] == 12
    assert summary["clean_checkout_working_tree_clean"] is True
    assert summary["blocker_count"] == 0
    assert summary["primary_blocker"] == ""
    assert summary["primary_required_action"] == ""
    assert summary["failed_count"] == 0
    assert summary["baseline_task_count"] == 1
    assert summary["claim_promotion_allowed"] is False
    assert summary["execution_enabled"] is False
    assert summary["external_state_mutated"] is False


def test_clean_checkout_benchmark_receipt_blocks_missing_sources(tmp_path: Path) -> None:
    payload = mod.build_developer_preview_clean_checkout_benchmark_receipt(root=tmp_path)
    summary = payload["summary"]
    blockers = ";".join(summary["blockers"])

    assert summary["status"] == "blocked_developer_preview_clean_checkout_benchmark_receipt"
    assert summary["clean_checkout_benchmark_regenerated"] is False
    assert summary["ai_verify_passed"] is False
    assert summary["reviewed_receipt_attached"] is False
    assert (
        summary["primary_blocker"]
        == ".betelgeuze/developer_preview_clean_checkout_ai_verify.log:missing"
    )
    assert summary["primary_required_action"].startswith("Run Gate A in a fresh checkout")
    assert summary["failed_count"] > 0
    assert "developer_preview_clean_checkout_ai_verify.log:missing" in blockers
    assert "summary.json:missing_or_invalid" in blockers
    assert "developer_preview_clean_checkout_source_provenance.json:missing_or_invalid" in blockers
    assert "checkout_source_repo_url_missing" in blockers
    assert "checkout_head_sha_missing" in blockers
    assert "checkout_tracked_file_count_zero" in blockers
    assert "reviewed_receipt_attached_not_true" in blockers
    assert "reviewer_id_missing" in blockers
    assert "reviewed_at_utc_missing" in blockers


def test_clean_checkout_benchmark_receipt_surfaces_baseline_source_blockers(
    tmp_path: Path,
) -> None:
    ai_verify_log = tmp_path / ".betelgeuze/developer_preview_clean_checkout_ai_verify.log"
    ai_verify_log.parent.mkdir(parents=True, exist_ok=True)
    ai_verify_log.write_text("verify ok (smoke)\n", encoding="utf-8")
    baseline_summary = (
        tmp_path
        / ".betelgeuze/developer_preview_external_baselines"
        / "biorxiv_baseline_comparison_developer_preview_clean_checkout"
        / "summary.json"
    )
    _write_json(
        baseline_summary,
        {
            "bundle_root": str(baseline_summary.parent),
            "task_count": 1,
            "task_winner_count_current": 0,
            "task_winner_count_noncurrent": 0,
            "task_source_error_count": 1,
            "blockers": [
                "pipeline_summary_json_missing:/tmp/missing_pipeline_summary.json",
            ],
            "score_leaderboard": [],
            "tasks": [
                {
                    "set_id": "set1_core_blind",
                    "task_id": "gpcr_core_full",
                    "current_score_col": "",
                    "score_rows": [],
                }
            ],
        },
    )

    payload = mod.build_developer_preview_clean_checkout_benchmark_receipt(
        ai_verify_log=ai_verify_log,
        baseline_summary_json=baseline_summary,
        reviewed_receipt_attached=False,
        root=tmp_path,
    )
    summary = payload["summary"]
    blockers = ";".join(summary["blockers"])

    assert summary["status"] == "blocked_developer_preview_clean_checkout_benchmark_receipt"
    assert summary["baseline_task_count"] == 1
    assert summary["baseline_task_source_error_count"] == 1
    assert summary["baseline_summary_blocker_count"] == 1
    assert "baseline_task_source_error_count_nonzero" in blockers
    assert "baseline_summary_blocker_count_nonzero" in blockers
    assert (
        "baseline_source_blocker=pipeline_summary_json_missing:/tmp/missing_pipeline_summary.json"
        in blockers
    )


def test_clean_checkout_benchmark_receipt_blocks_dirty_checkout_provenance(
    tmp_path: Path,
) -> None:
    ai_verify_log, baseline_summary, provenance = _write_ready_sources(tmp_path)
    _write_json(
        provenance,
        {
            "summary": {
                "source_repo_url_present": True,
                "source_repo_url_fingerprint": "abc123",
                "head_sha": "b" * 40,
                "tracked_file_count": 12,
                "git_status_porcelain_empty": False,
                "working_tree_clean": False,
                "dirty_path_count": 1,
            },
            "dirty_rows": [{"status_line": " M pyproject.toml"}],
        },
    )

    payload = mod.build_developer_preview_clean_checkout_benchmark_receipt(
        ai_verify_log=ai_verify_log,
        baseline_summary_json=baseline_summary,
        checkout_provenance_json=provenance,
        reviewed_receipt_attached=True,
        reviewer_id="operator-a",
        reviewed_at_utc="2026-07-03T00:00:00Z",
        root=tmp_path,
    )
    summary = payload["summary"]

    assert summary["status"] == "blocked_developer_preview_clean_checkout_benchmark_receipt"
    assert summary["clean_checkout_benchmark_regenerated"] is True
    assert summary["clean_checkout_provenance_ready"] is False
    assert summary["clean_checkout_working_tree_clean"] is False
    assert summary["clean_checkout_dirty_path_count"] == 1
    assert "checkout_worktree_dirty" in summary["blockers"]


def test_clean_checkout_benchmark_receipt_surfaces_stage5_input_family(
    tmp_path: Path,
) -> None:
    ai_verify_log = tmp_path / ".betelgeuze/developer_preview_clean_checkout_ai_verify.log"
    ai_verify_log.parent.mkdir(parents=True, exist_ok=True)
    ai_verify_log.write_text("verify ok (smoke)\n", encoding="utf-8")
    runs_dir = tmp_path / "runs"
    scores_csv = runs_dir / "dp_task_stage3_scores.csv"
    labels_csv = runs_dir / "dp_task_labels.csv"
    split_csv = runs_dir / "dp_task_split.csv"
    expected_keys_csv = runs_dir / "dp_task_expected_keys.csv"
    labels_csv.parent.mkdir(parents=True, exist_ok=True)
    labels_csv.write_text("ligand_id,label\n", encoding="utf-8")
    expected_keys_csv.write_text("ligand_id\n", encoding="utf-8")
    pipeline_summary = runs_dir / "dp_task_summary.json"
    _write_json(
        pipeline_summary,
        {
            "stages": {
                "stage5_ranking_eval": {
                    "cmd": [
                        "python3",
                        "tools/product/evaluate_ligand_ranking_metrics.py",
                        "--scores-csv",
                        str(scores_csv),
                        "--labels-csv",
                        str(labels_csv),
                        "--split-csv",
                        str(split_csv),
                        "--expected-keys-csv",
                        str(expected_keys_csv),
                        "--out-json",
                        str(runs_dir / "dp_task_ranking_summary.json"),
                    ],
                },
            },
        },
    )
    baseline_summary = (
        tmp_path
        / ".betelgeuze/developer_preview_external_baselines"
        / "biorxiv_baseline_comparison_developer_preview_clean_checkout"
        / "summary.json"
    )
    blocker = f"stage5_input_missing:--scores-csv:{scores_csv}"
    _write_json(
        baseline_summary,
        {
            "bundle_root": str(baseline_summary.parent),
            "task_count": 1,
            "task_winner_count_current": 0,
            "task_winner_count_noncurrent": 0,
            "task_source_error_count": 1,
            "blockers": [blocker],
            "task_source_errors": [
                {
                    "set_id": "set1_core_blind",
                    "task_id": "gpcr_core_full",
                    "domain": "gpcr",
                    "kind": "ligand_stress",
                    "profile_json": str(tmp_path / "config/profile.json"),
                    "pipeline_summary_json": str(pipeline_summary),
                    "pipeline_summary_resolution_source": "copied_files",
                    "source_error_type": "TaskSourceError",
                    "source_error": blocker,
                    "blocker": blocker,
                }
            ],
            "score_leaderboard": [],
            "tasks": [
                {
                    "set_id": "set1_core_blind",
                    "task_id": "gpcr_core_full",
                    "current_score_col": "",
                    "score_rows": [],
                }
            ],
        },
    )

    payload = mod.build_developer_preview_clean_checkout_benchmark_receipt(
        ai_verify_log=ai_verify_log,
        baseline_summary_json=baseline_summary,
        root=tmp_path,
    )
    summary = payload["summary"]
    family_rows = payload["stage5_input_family_rows"]
    missing_rows = [row for row in family_rows if row["source_artifact_missing"]]

    assert summary["stage5_required_argument_count"] == 4
    assert summary["stage5_input_family_row_count"] == 4
    assert summary["stage5_recovery_task_count"] == 1
    assert summary["stage5_complete_task_count"] == 0
    assert summary["stage5_incomplete_task_count"] == 1
    assert summary["stage5_missing_input_count"] == 2
    assert summary["stage5_missing_source_artifact_count"] == 2
    assert summary["stage5_input_family_ready"] is False
    assert summary["stage5_primary_task_key"] == "dp_task"
    assert summary["stage5_primary_source_argument"] == "--scores-csv"
    assert summary["stage5_primary_source_artifact_path"] == "runs/dp_task_stage3_scores.csv"
    assert summary["primary_blocker"] == f"baseline_source_blocker={blocker}"
    assert summary["primary_required_action"] == (
        "Restore or regenerate --scores-csv at runs/dp_task_stage3_scores.csv from the "
        "approved clean-checkout baseline, then rerun python3 "
        "tools/product/build_developer_preview_stage5_restore_packet.py and python3 "
        "tools/product/build_developer_preview_clean_checkout_benchmark_receipt.py --allow-blocked."
    )
    assert summary["next_required_step"] == summary["primary_required_action"]
    assert payload["stage5_task_family_rows"] == [
        {
            "task_key": "dp_task",
            "set_id": "set1_core_blind",
            "task_id": "gpcr_core_full",
            "domain": "gpcr",
            "kind": "ligand_stress",
            "profile_json": "config/profile.json",
            "pipeline_summary_json": "runs/dp_task_summary.json",
            "pipeline_summary_present": True,
            "required_stage5_arguments": [
                "--scores-csv",
                "--labels-csv",
                "--split-csv",
                "--expected-keys-csv",
            ],
            "required_stage5_argument_count": 4,
            "present_source_arguments": [
                "--expected-keys-csv",
                "--labels-csv",
            ],
            "missing_source_arguments": [
                "--scores-csv",
                "--split-csv",
            ],
            "missing_source_artifact_paths": [
                "runs/dp_task_stage3_scores.csv",
                "runs/dp_task_split.csv",
            ],
            "present_input_count": 2,
            "missing_input_count": 2,
            "stage5_input_family_complete": False,
            "operator_action_required": True,
            "required_action": (
                "Restore or regenerate the full scores/labels/split/expected-keys CSV family for this task."
            ),
            "execution_enabled": False,
            "external_state_mutated": False,
            "claim_promotion_allowed": False,
            "claim_boundary": mod.CLAIM_BOUNDARY,
        }
    ]
    assert {row["source_argument"] for row in missing_rows} == {
        "--scores-csv",
        "--split-csv",
    }
    assert all(row["execution_enabled"] is False for row in family_rows)
    assert all(row["claim_promotion_allowed"] is False for row in family_rows)
    assert payload["rows"][-1]["check"] == "stage5_input_family_recovery"
    assert payload["rows"][-1]["missing_input_count"] == 2
    assert payload["rows"][-1]["incomplete_task_count"] == 1


def test_clean_checkout_benchmark_receipt_cli_writes_outputs(tmp_path: Path) -> None:
    ai_verify_log, baseline_summary, provenance = _write_ready_sources(tmp_path)
    out_json = tmp_path / ".betelgeuze/developer_preview_clean_checkout_benchmark_receipt.json"
    out_md = tmp_path / ".betelgeuze/developer_preview_clean_checkout_benchmark_receipt.md"
    out_stage5_csv = (
        tmp_path / ".betelgeuze/developer_preview_clean_checkout_stage5_input_family_current.csv"
    )
    out_stage5_md = (
        tmp_path / ".betelgeuze/developer_preview_clean_checkout_stage5_input_family_current.md"
    )

    assert mod.main(
        [
            "--ai-verify-log",
            str(ai_verify_log),
            "--baseline-summary-json",
            str(baseline_summary),
            "--checkout-provenance-json",
            str(provenance),
            "--reviewed-receipt-attached",
            "--reviewer-id",
            "operator-a",
            "--reviewed-at-utc",
            "2026-07-03T00:00:00Z",
            "--out-json",
            str(out_json),
            "--out-md",
            str(out_md),
            "--out-stage5-input-family-csv",
            str(out_stage5_csv),
            "--out-stage5-input-family-md",
            str(out_stage5_md),
        ]
    ) == 0

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["summary"]["packet_type"] == "developer_preview_clean_checkout_benchmark_receipt"
    assert "Developer Preview Clean-Checkout Benchmark Receipt" in out_md.read_text(
        encoding="utf-8"
    )
    assert out_stage5_csv.read_text(encoding="utf-8").startswith("set_id,task_id,")
    assert "Developer Preview Clean-Checkout Stage5 Input Family" in out_stage5_md.read_text(
        encoding="utf-8"
    )
    assert "Task Family Checklist" in out_stage5_md.read_text(encoding="utf-8")


def test_clean_checkout_benchmark_receipt_cli_allow_blocked_writes_fail_closed_outputs(
    tmp_path: Path,
) -> None:
    out_json = tmp_path / ".betelgeuze/developer_preview_clean_checkout_benchmark_receipt.json"
    out_md = tmp_path / ".betelgeuze/developer_preview_clean_checkout_benchmark_receipt.md"
    out_stage5_csv = (
        tmp_path / ".betelgeuze/developer_preview_clean_checkout_stage5_input_family_current.csv"
    )
    out_stage5_md = (
        tmp_path / ".betelgeuze/developer_preview_clean_checkout_stage5_input_family_current.md"
    )

    assert mod.main(
        [
            "--ai-verify-log",
            str(tmp_path / ".betelgeuze/missing_ai_verify.log"),
            "--baseline-summary-json",
            str(tmp_path / ".betelgeuze/missing_baseline_summary.json"),
            "--allow-blocked",
            "--out-json",
            str(out_json),
            "--out-md",
            str(out_md),
            "--out-stage5-input-family-csv",
            str(out_stage5_csv),
            "--out-stage5-input-family-md",
            str(out_stage5_md),
        ]
    ) == 0

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["summary"]["status"] == "blocked_developer_preview_clean_checkout_benchmark_receipt"
    assert payload["summary"]["claim_promotion_allowed"] is False
    assert out_md.is_file()
    assert out_stage5_csv.is_file()
    assert out_stage5_md.is_file()

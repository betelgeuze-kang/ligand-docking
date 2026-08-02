from __future__ import annotations

import csv
import json
from pathlib import Path

from tools.product import build_competition_benchmark_rollup as mod


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _write_intake_csv(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(mod.INTAKE_COLUMNS))
        writer.writeheader()


def _write_rollup_inputs(
    root: Path,
    *,
    casp16_raw_count: int = 0,
    bm5_raw_count: int = 0,
) -> None:
    _write_intake_csv(root / "runs/cameo_official_results_operator_intake.csv")
    for rel_path, summary in {
        "runs/cameo_api_dependency_readiness_current.json": {
            "status": "cameo_api_dependency_ready"
        },
        "runs/cameo_receiver_smoke_contract_current.json": {
            "status": "cameo_receiver_smoke_ready"
        },
        "runs/cameo_format_validation_packet_current.json": {
            "status": "cameo_format_validation_ready"
        },
        "runs/cameo_model1_selection_packet_current.json": {
            "selection_status": "cameo_model1_selection_ready"
        },
        "runs/cameo_dry_run_handoff_packet_current.json": {
            "status": "cameo_handoff_dry_run_ready"
        },
        "runs/cameo_validation_readiness_gate_current.json": {
            "status": "cameo_validation_readiness_ready",
            "official_cameo_results_used": True,
        },
        "runs/cameo_official_results_intake_gate_current.json": {
            "status": "cameo_official_results_intake_ready",
            "official_result_intake_ready": True,
            "model1_official_result_ready": True,
            "accepted_official_result_count": 1,
            "rejected_official_result_count": 0,
            "blocker_count": 0,
            "native_local_accuracy_used": False,
            "external_state_mutated": False,
        },
    }.items():
        _write_json(root / rel_path, {"summary": summary})

    _write_json(
        root / "casp17/casp17_strict_blind_internal_prediction_source_gate_current.json",
        {"rows": [{"check_status": "pass"}]},
    )
    _write_json(
        root / "casp17/casp17_historical_winner_normalized_bands_current.json",
        {"rows": [{"band_status": "ready"}]},
    )
    _write_json(
        root / "runs/casp16_ligand_source_manifest_current.json",
        {
            "summary": {
                "status": "casp16_ligand_competition_credibility_ready",
                "source_manifest_ready": True,
                "materialization_ready": True,
                "scorecard_ready": True,
                "competition_credibility_ready": True,
                "raw_data_committed": casp16_raw_count > 0,
                "raw_data_git_tracked_file_count": casp16_raw_count,
                "pharma_pose_ligand_target_count": 233,
                "pharma_affinity_ligand_target_count": 140,
            }
        },
    )
    _write_json(
        root / "runs/bm5_capri_complex_source_manifest_current.json",
        {
            "summary": {
                "status": "bm5_capri_complex_competition_credibility_ready",
                "bm5_complex_benchmark_ready": True,
                "capri_score_set_ready": True,
                "competition_credibility_ready": True,
                "raw_data_committed": bm5_raw_count > 0,
                "raw_data_git_tracked_file_count": bm5_raw_count,
                "primary_metric": "dockq_acceptable_rate_proxy",
            }
        },
    )
    _write_json(
        root / "runs/competition_benchmark_custody_work_order_current.json",
        {
            "summary": {
                "status": "competition_benchmark_custody_work_order_ready"
                if not (casp16_raw_count or bm5_raw_count)
                else "blocked_competition_benchmark_custody_work_order",
                "custody_work_order_ready": not (casp16_raw_count or bm5_raw_count),
                "raw_data_custody_blocked_row_count": 1 if (casp16_raw_count or bm5_raw_count) else 0,
                "primary_raw_data_git_tracked_file_count": max(casp16_raw_count, bm5_raw_count),
                "primary_raw_data_required_action": "Move raw structures out of git-tracked storage.",
                "bm5_capri_raw_data_untrack_apply_preflight_json": (
                    "runs/bm5_capri_raw_data_untrack_apply_preflight_current.json"
                ),
                "bm5_capri_raw_data_untrack_apply_preflight_status": (
                    "bm5_capri_raw_data_untrack_apply_preflight_ready"
                ),
                "bm5_capri_raw_data_untrack_apply_preflight_ready": True,
                "bm5_capri_raw_data_untrack_apply_generated_candidate_manifest_path": (
                    "runs/bm5_capri_raw_data_untrack_candidates_current.txt"
                ),
                "bm5_capri_raw_data_untrack_apply_candidate_manifest_path": (
                    "runs/bm5_capri_raw_data_untrack_candidates_current.txt"
                ),
                "bm5_capri_raw_data_untrack_apply_reviewed_manifest_template_path": (
                    "runs/bm5_capri_raw_data_reviewed_untrack_manifest_template_current.txt"
                ),
                "bm5_capri_raw_data_untrack_apply_operator_reviewed_manifest_path": (
                    "OPERATOR_REVIEWED_BM5_CAPRI_RAW_DATA_UNTRACK_PATHS.txt"
                ),
                "bm5_capri_raw_data_untrack_apply_untrack_candidate_count": 2802,
                "bm5_capri_raw_data_untrack_apply_custody_plan_raw_data_path_count": 2802,
                "bm5_capri_raw_data_untrack_apply_candidates_match_custody_plan": True,
                "bm5_capri_raw_data_untrack_apply_preview_command": (
                    "python3 tools/apply_bm5_capri_raw_data_custody_plan.py --mode preview "
                    "--untrack-candidates OPERATOR_REVIEWED_BM5_CAPRI_RAW_DATA_UNTRACK_PATHS.txt"
                ),
                "bm5_capri_raw_data_untrack_apply_execute_command": (
                    "python3 tools/apply_bm5_capri_raw_data_custody_plan.py --mode execute "
                    "--untrack-candidates OPERATOR_REVIEWED_BM5_CAPRI_RAW_DATA_UNTRACK_PATHS.txt "
                    "--approval-token APPROVE_BM5_CAPRI_RAW_DATA_UNTRACK"
                ),
                "bm5_capri_raw_data_untrack_apply_approval_token_required": (
                    "APPROVE_BM5_CAPRI_RAW_DATA_UNTRACK"
                ),
                "bm5_capri_raw_data_untrack_apply_post_execute_verification_command": (
                    "python3 tools/build_bm5_capri_raw_data_custody_plan.py --compute-sha256"
                ),
                "bm5_capri_raw_data_untrack_apply_operator_review_handoff": (
                    "Review runs/bm5_capri_raw_data_reviewed_untrack_manifest_template_current.txt."
                ),
                "casp16_ligand_operator_source_manifest_template_csv": (
                    "runs/casp16_ligand_operator_source_manifest_template_current.csv"
                ),
                "casp16_ligand_operator_checksum_manifest_template": (
                    "runs/casp16_ligand_operator_checksum_manifest_template_current.sha256"
                ),
                "casp16_ligand_operator_scorecard_rows_template_csv": (
                    "runs/casp16_ligand_operator_scorecard_rows_template_current.csv"
                ),
                "casp16_ligand_operator_receipt_fill_in_md": (
                    "runs/casp16_ligand_operator_receipt_fill_in_current.md"
                ),
                "casp16_ligand_operator_template_artifacts": (
                    "runs/casp16_ligand_operator_source_manifest_template_current.csv;"
                    "runs/casp16_ligand_operator_checksum_manifest_template_current.sha256;"
                    "runs/casp16_ligand_operator_scorecard_rows_template_current.csv;"
                    "runs/casp16_ligand_operator_receipt_fill_in_current.md"
                ),
                "casp16_ligand_operator_templates_written": True,
            }
        },
    )
    _write_json(
        root / "runs/product_public_benchmark_contract_current.json",
        {
            "summary": {
                "status": "product_public_benchmark_contract_ready",
                "public_benchmark_validation_ready": True,
                "required_suite_count": 3,
                "ready_required_suite_count": 3,
                "blocked_suite_count": 0,
                "phase2_pdbbind_casf_pose_success_harness_ready": True,
                "phase2_posebusters_style_validity_checks_ready": True,
                "phase2_symmetry_aware_ligand_rmsd_ready": True,
                "phase2_dude_or_lit_pcba_enrichment_ready": True,
            }
        },
    )
    _write_json(
        root / "runs/refine_tier_public_benchmark_readiness_current.json",
        {
            "summary": {
                "status": "refine_tier_public_benchmark_readiness_ready",
                "claim_grade_public_benchmark_ready": False,
                "blockers": ["fit_and_holdout_splits_required"],
                "external_state_mutated": False,
            }
        },
    )
    _write_json(
        root / "runs/refine_tier_public_benchmark_work_order_apply_current.json",
        {
            "summary": {
                "status": "blocked_refine_tier_public_benchmark_work_order_apply",
                "apply_ready": False,
                "external_state_mutated": False,
            }
        },
    )


def test_competition_rollup_surfaces_github_raw_data_policy_blockers(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    _write_rollup_inputs(tmp_path, bm5_raw_count=2802)

    payload = mod.build_competition_benchmark_rollup()
    summary = payload["summary"]
    markdown = mod._render_status_markdown(payload)

    assert summary["status"] == "competition_benchmark_rollup_ready"
    assert summary["competition_benchmark_rollup_artifact_ready"] is True
    assert summary["competition_benchmark_rollup_ready"] is True
    assert summary["competition_credibility_evidence_ready"] is False
    assert summary["competition_credibility_evidence_blockers"] == [
        "bm5_capri_raw_data_committed_in_repo"
    ]
    assert summary["competition_credibility_evidence_blocker_count"] == 1
    assert summary["competition_credibility_evidence_primary_blocker"] == (
        "bm5_capri_raw_data_committed_in_repo"
    )
    assert summary["competition_benchmark_action_required"] is True
    assert summary["competition_benchmark_blockers"] == [
        "bm5_capri_raw_data_committed_in_repo",
        "package_b_claim_grade_public_benchmark_not_ready",
    ]
    assert summary["competition_benchmark_blocker_count"] == 2
    assert summary["blockers"] == summary["competition_benchmark_blockers"]
    assert summary["blocker_count"] == 2
    assert summary["primary_blocker"] == "bm5_capri_raw_data_committed_in_repo"
    assert summary["competition_benchmark_next_required_step"] == (
        "Move raw structures out of git-tracked storage."
    )
    assert summary["competition_credibility_only"] is True
    assert summary["raw_data_stored_in_repo"] is True
    assert summary["raw_data_free"] is False
    assert summary["github_raw_payloads_allowed"] is False
    assert summary["competition_ligand_commercial_claim_allowed"] is False
    assert summary["ligand_commercial_claim_unlocked"] is False
    assert summary["commercial_claim_unlocked"] is False
    assert summary["claim_promotion_allowed"] is False
    assert summary["execution_enabled"] is False
    assert summary["external_state_mutated"] is False
    assert summary["github_raw_data_policy_ready"] is False
    assert summary["github_raw_data_git_tracked_total_count"] == 2802
    assert summary["github_raw_data_policy_blockers"] == [
        "bm5_capri_raw_data_committed_in_repo"
    ]
    assert summary["github_raw_data_policy_blocker_count"] == 1
    assert "source manifests" in summary["github_raw_data_policy_required_action"]
    assert summary["github_safe_allowed_artifact_classes"] == [
        "source_manifests",
        "checksum_manifests",
        "materialization_manifests",
        "scorecard_builders",
        "scorecard_receipts",
        "claim_boundary_docs",
    ]
    assert summary["github_disallowed_artifact_classes"] == [
        "raw_benchmark_payloads",
        "raw_structure_archives",
        "official_archive_models_as_internal_predictions",
    ]
    assert summary["github_source_manifest_artifacts_allowed"] is True
    assert summary["github_checksum_manifest_artifacts_allowed"] is True
    assert summary["github_materialization_manifest_artifacts_allowed"] is True
    assert summary["github_scorecard_builder_artifacts_allowed"] is True
    assert summary["github_claim_boundary_docs_allowed"] is True
    assert summary["github_raw_benchmark_payloads_allowed"] is False
    assert (
        summary["github_official_archive_models_as_internal_predictions_allowed"]
        is False
    )
    assert "raw_benchmark_payloads" not in summary[
        "github_safe_allowed_artifact_classes"
    ]
    assert summary["github_raw_data_policy_untrack_preflight_ready"] is True
    assert summary["github_raw_data_policy_untrack_preflight_status"] == (
        "bm5_capri_raw_data_untrack_apply_preflight_ready"
    )
    assert summary["github_raw_data_policy_untrack_preflight_receipt"] == (
        "runs/bm5_capri_raw_data_untrack_apply_preflight_current.json"
    )
    assert summary[
        "github_raw_data_policy_untrack_generated_candidate_manifest_path"
    ] == "runs/bm5_capri_raw_data_untrack_candidates_current.txt"
    assert summary[
        "github_raw_data_policy_untrack_reviewed_manifest_template_path"
    ] == "runs/bm5_capri_raw_data_reviewed_untrack_manifest_template_current.txt"
    assert summary[
        "github_raw_data_policy_untrack_operator_reviewed_manifest_path"
    ] == "OPERATOR_REVIEWED_BM5_CAPRI_RAW_DATA_UNTRACK_PATHS.txt"
    assert summary["github_raw_data_policy_untrack_candidate_count"] == 2802
    assert summary["github_raw_data_policy_untrack_candidates_match_custody_plan"] is True
    assert summary["github_raw_data_policy_untrack_approval_token_required"] == (
        "APPROVE_BM5_CAPRI_RAW_DATA_UNTRACK"
    )
    assert "--mode preview" in summary["github_raw_data_policy_untrack_preview_command"]
    assert "OPERATOR_REVIEWED_BM5_CAPRI_RAW_DATA_UNTRACK_PATHS.txt" in summary[
        "github_raw_data_policy_untrack_execute_command"
    ]
    assert "bm5_capri_raw_data_committed_in_repo" in summary[
        "competition_credibility_extension_blockers"
    ]
    assert summary[
        "competition_benchmark_custody_work_order_bm5_capri_raw_data_untrack_apply_preflight_ready"
    ] is True
    assert summary[
        "competition_benchmark_custody_work_order_bm5_capri_raw_data_untrack_apply_reviewed_manifest_template_path"
    ] == "runs/bm5_capri_raw_data_reviewed_untrack_manifest_template_current.txt"
    assert summary[
        "competition_benchmark_custody_work_order_bm5_capri_raw_data_untrack_apply_candidates_match_custody_plan"
    ] is True
    assert summary[
        "competition_benchmark_custody_work_order_casp16_operator_templates_written"
    ] is True
    assert "casp16_ligand_operator_source_manifest_template_current.csv" in summary[
        "competition_benchmark_custody_work_order_casp16_operator_template_artifacts"
    ]
    assert "## GitHub Raw-Data Policy" in markdown
    assert "| Rollup artifact ready | `true` |" in markdown
    assert "| Competition credibility evidence ready | `false` |" in markdown
    assert "| Competition credibility evidence primary blocker | `bm5_capri_raw_data_committed_in_repo` |" in markdown
    assert "| Operator action required | `true` |" in markdown
    assert "| Raw data stored in repo | `true` |" in markdown
    assert "| Raw-data-free evidence | `false` |" in markdown
    assert "| Ready | `false` |" in markdown
    assert "source_manifests; checksum_manifests; materialization_manifests" in markdown
    assert "raw_benchmark_payloads; raw_structure_archives" in markdown
    assert "| Untrack preflight ready | `true` |" in markdown
    assert "bm5_capri_raw_data_reviewed_untrack_manifest_template_current.txt" in markdown
    assert "OPERATOR_REVIEWED_BM5_CAPRI_RAW_DATA_UNTRACK_PATHS.txt" in markdown
    assert "casp16_ligand_operator_source_manifest_template_current.csv" in markdown


def test_competition_rollup_marks_github_raw_data_policy_ready_when_manifest_only(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    _write_rollup_inputs(tmp_path)

    summary = mod.build_competition_benchmark_rollup()["summary"]

    assert summary["github_raw_data_policy_ready"] is True
    assert summary["raw_data_stored_in_repo"] is False
    assert summary["raw_data_free"] is True
    assert summary["github_raw_payloads_allowed"] is False
    assert summary["github_raw_benchmark_payloads_allowed"] is False
    assert "source_manifests" in summary["github_safe_allowed_artifact_classes"]
    assert "raw_benchmark_payloads" in summary["github_disallowed_artifact_classes"]
    assert "raw_benchmark_payloads" not in summary[
        "github_safe_allowed_artifact_classes"
    ]
    assert summary["github_raw_data_git_tracked_total_count"] == 0
    assert summary["github_raw_data_policy_blockers"] == []
    assert summary["competition_credibility_extension_ready"] is True
    assert summary["competition_credibility_evidence_ready"] is True
    assert summary["competition_credibility_evidence_blockers"] == []
    assert summary["competition_credibility_evidence_blocker_count"] == 0
    assert summary["competition_benchmark_rollup_ready"] is True
    assert summary["competition_benchmark_action_required"] is True
    assert summary["competition_benchmark_blockers"] == [
        "package_b_claim_grade_public_benchmark_not_ready"
    ]
    assert summary["blockers"] == summary["competition_benchmark_blockers"]
    assert summary["blocker_count"] == 1
    assert summary["primary_blocker"] == "package_b_claim_grade_public_benchmark_not_ready"
    assert summary["competition_benchmark_next_required_step"] == (
        "Complete Package B claim-grade public benchmark receipts before any ligand commercial claim."
    )

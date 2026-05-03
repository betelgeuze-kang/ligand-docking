from __future__ import annotations

import json
from pathlib import Path

from tools import build_gpcr_scaleup_regression_triage as mod


class _Args:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def test_triage_keeps_failed_scaleup_claim_blocked_and_candidates_comparison_only(tmp_path: Path) -> None:
    runs = tmp_path / "runs"
    _write_json(
        runs / "ligand_scaleup_benchmark_summary_current.json",
        {
            "claim_safe": False,
            "claim_safe_status": "regression_guardrail_failed",
            "primary_regression_task_id": "gpcr_core_full",
            "guardrail_fail_count": 3,
            "regression_diagnostics": {
                "primary_regression_task_id": "gpcr_core_full",
                "primary_regression_reason": "pass_to_fail_and_worst_pr_auc",
            },
            "guardrail_rows": [
                {"guardrail_id": "no_pass_to_fail", "pass": False},
                {"guardrail_id": "pr_auc_drop_max_0p02", "pass": False},
                {"guardrail_id": "slowest_domain_speedup_min_1p8x", "pass": None},
            ],
        },
    )
    _write_json(
        runs / "ligand_scaleup_suite_status_current.json",
        {"summary": {"suite_count": 3}, "suite_rows": [{"suite_id": "pilot_100k", "claim_safe_status": "regression_guardrail_failed"}]},
    )
    _write_json(
        runs / "gpcr_100k_failure_analysis_current.json",
        {
            "summary": {"status": "computed", "scaleup_positive_ranks": [1, 2, 16, 79, 106, 125]},
            "score_diagnostics": {
                "available": True,
                "existing_score_recovery_status": "no_existing_score_column_recovers_gate",
                "root_cause_tags": ["donor_prior_decoy_intrusion", "no_existing_score_column_recovers_gate"],
            },
        },
    )
    _write_json(
        runs / "external_validation_2026-05-02_gpcr_decoy_intrusion_apply_core_v1_set1_core_blind_gpcr_core_full_summary.json",
        {
            "pass": False,
            "profile_json": str(runs / "profiles" / "ligand_htvs_blind_gpcr_adrb2_v4_scorefix3_prod100k_core-decoy-intrusion-apply100k.json"),
            "aggregate": [{"ranking_pr_auc_mean": 0.24, "topk_hit_rate_mean": 0.05}],
            "failures": [
                {
                    "command": {
                        "cmd": [
                            "python3",
                            "tools/run_ligand_htvs_pipeline.py",
                            "--ranking-score-col",
                            "binding_score_composite_v7_residual_active",
                        ]
                    }
                }
            ],
        },
    )
    _write_json(
        runs / "external_validation_2026-04-30_gpcr_scaleup_100k_linear_c100_logit_candidate_v1_set1_core_blind_gpcr_core_full_summary.json",
        {
            "pass": False,
            "profile_json": str(runs / "profiles" / "ligand_htvs_blind_gpcr_adrb2_v4_scorefix3_prod100k_linear_c100_logit_candidate.json"),
            "aggregate": [{"ranking_pr_auc_mean": 0.23, "topk_hit_rate_mean": 0.05}],
        },
    )
    _write_json(
        runs / "external_validation_2026-04-30_gpcr_scaleup_100k_adrb2_pharmacophore_apply_v1_set1_core_blind_gpcr_core_full_summary.json",
        {
            "pass": True,
            "profile_json": str(runs / "profiles" / "ligand_htvs_blind_gpcr_adrb2_v4_scorefix3_prod100k_adrb2-pharmacophore-apply100k.json"),
            "aggregate": [{"ranking_pr_auc_mean": 1.0, "topk_hit_rate_mean": 0.3}],
        },
    )

    args = _Args(
        benchmark_summary_json="runs/ligand_scaleup_benchmark_summary_current.json",
        suite_status_json="runs/ligand_scaleup_suite_status_current.json",
        failure_analysis_json="runs/gpcr_100k_failure_analysis_current.json",
        candidate_glob="runs/external_validation_*gpcr*summary.json",
        out_json="runs/gpcr_scaleup_regression_triage_current.json",
        out_md="runs/gpcr_scaleup_regression_triage_current.md",
    )
    mod.ROOT = tmp_path

    payload = mod.build_payload(args)
    summary = payload["summary"]
    candidates = {row["candidate_id"]: row for row in payload["candidates"]}

    assert summary["claim_safe"] is False
    assert summary["claim_safe_status"] == "regression_guardrail_failed"
    assert summary["primary_blocker_task"] == "gpcr_core_full"
    assert summary["guardrail_fail_count"] == 3
    assert summary["candidate_count"] == 3
    assert summary["rejected_candidate_count"] == 2
    assert summary["comparison_only_candidate_count"] == 3
    assert "guarded/shadow diagnostics" in summary["recommended_next_action"]
    assert "delivery" not in summary["recommended_next_action"].lower()

    assert candidates["gpcr_core_decoy_intrusion_v1"]["claim_allowed"] is False
    assert candidates["gpcr_core_decoy_intrusion_v1"]["reject_evidence"] is True
    assert candidates["gpcr_core_decoy_intrusion_v1"]["score_column"] == "binding_score_composite_v7_residual_active"
    assert candidates["gpcr_core_linear_rescore_v1"]["reject_evidence"] is True
    assert candidates["gpcr_core_pharmacophore_v1"]["claim_allowed"] is False
    assert candidates["gpcr_core_pharmacophore_v1"]["reject_evidence"] is False


def test_cli_writes_json_and_markdown_packet(tmp_path: Path) -> None:
    runs = tmp_path / "runs"
    _write_json(
        runs / "ligand_scaleup_benchmark_summary_current.json",
        {
            "claim_safe": False,
            "claim_safe_status": "regression_guardrail_failed",
            "primary_regression_task_id": "gpcr_core_full",
            "guardrail_rows": [{"guardrail_id": "no_pass_to_fail", "pass": False}],
        },
    )
    _write_json(runs / "ligand_scaleup_suite_status_current.json", {"summary": {"suite_count": 3}})
    _write_json(
        runs / "external_validation_2026-05-02_gpcr_decoy_intrusion_apply_core_v1_set1_core_blind_gpcr_core_full_summary.json",
        {"pass": False, "profile_json": "profiles/core-decoy-intrusion-apply100k.json"},
    )

    args = _Args(
        benchmark_summary_json="runs/ligand_scaleup_benchmark_summary_current.json",
        suite_status_json="runs/ligand_scaleup_suite_status_current.json",
        failure_analysis_json="runs/gpcr_100k_failure_analysis_current.json",
        candidate_glob="runs/external_validation_*gpcr*summary.json",
        out_json="runs/gpcr_scaleup_regression_triage_current.json",
        out_md="runs/gpcr_scaleup_regression_triage_current.md",
    )
    mod.ROOT = tmp_path
    mod.write_outputs(args)

    payload = json.loads((runs / "gpcr_scaleup_regression_triage_current.json").read_text(encoding="utf-8"))
    md = (runs / "gpcr_scaleup_regression_triage_current.md").read_text(encoding="utf-8")
    assert payload["summary"]["claim_safe"] is False
    assert payload["summary"]["candidate_count"] == 1
    assert "GPCR Scale-up Regression Triage" in md
    assert "gpcr_core_decoy_intrusion_v1" in md


def test_triage_prefers_guarded_apply_over_shadow_for_same_candidate(tmp_path: Path) -> None:
    runs = tmp_path / "runs"
    _write_json(
        runs / "ligand_scaleup_benchmark_summary_current.json",
        {
            "claim_safe": False,
            "claim_safe_status": "regression_guardrail_failed",
            "primary_regression_task_id": "gpcr_core_full",
        },
    )
    _write_json(runs / "ligand_scaleup_suite_status_current.json", {"summary": {"suite_count": 3}})
    _write_json(
        runs / "external_validation_shadow_pharmacophore_v1_set1_core_blind_gpcr_core_full_summary.json",
        {
            "pass": False,
            "profile_json": "profiles/adrb2-pharmacophore100k.json",
            "aggregate": [{"ranking_pr_auc_mean": 0.39, "topk_hit_rate_mean": 0.15}],
        },
    )
    _write_json(
        runs / "external_validation_apply_pharmacophore_v1_set1_core_blind_gpcr_core_full_summary.json",
        {
            "pass": True,
            "profile_json": "profiles/adrb2-pharmacophore-apply100k.json",
            "aggregate": [{"ranking_pr_auc_mean": 1.0, "topk_hit_rate_mean": 0.30}],
        },
    )

    args = _Args(
        benchmark_summary_json="runs/ligand_scaleup_benchmark_summary_current.json",
        suite_status_json="runs/ligand_scaleup_suite_status_current.json",
        failure_analysis_json="runs/gpcr_100k_failure_analysis_current.json",
        candidate_glob="runs/external_validation_*gpcr*summary.json",
        out_json="runs/gpcr_scaleup_regression_triage_current.json",
        out_md="runs/gpcr_scaleup_regression_triage_current.md",
    )
    mod.ROOT = tmp_path

    payload = mod.build_payload(args)
    candidates = {row["candidate_id"]: row for row in payload["candidates"]}

    assert payload["summary"]["candidate_count"] == 1
    assert payload["summary"]["rejected_candidate_count"] == 0
    assert candidates["gpcr_core_pharmacophore_v1"]["mode"] == "guarded_apply"
    assert candidates["gpcr_core_pharmacophore_v1"]["pass"] is True
    assert candidates["gpcr_core_pharmacophore_v1"]["claim_allowed"] is False


def test_triage_classifies_failed_mismatch_contact_guarded_apply_as_reject_evidence(tmp_path: Path) -> None:
    runs = tmp_path / "runs"
    _write_json(
        runs / "ligand_scaleup_benchmark_summary_current.json",
        {
            "claim_safe": False,
            "claim_safe_status": "regression_guardrail_failed",
            "primary_regression_task_id": "gpcr_core_full",
        },
    )
    _write_json(runs / "ligand_scaleup_suite_status_current.json", {"summary": {"suite_count": 3}})
    _write_json(
        runs
        / "external_validation_2026-05-02_gpcr_core_mismatch_contact_rescore_apply_v1_set1_core_blind_gpcr_core_full_summary.json",
        {
            "pass": False,
            "profile_json": str(
                runs
                / "profiles"
                / "ligand_htvs_blind_gpcr_adrb2_v4_scorefix3_prod100k_mismatch-contact-apply100k.json"
            ),
            "aggregate": [{"ranking_pr_auc_mean": 0.39, "topk_hit_rate_mean": 0.15}],
        },
    )
    _write_json(
        runs
        / "external_validation_2026-05-02_gpcr_core_mismatch_contact_rescore_shadow_v1_set1_core_blind_gpcr_core_full_summary.json",
        {
            "pass": True,
            "profile_json": str(
                runs
                / "profiles"
                / "ligand_htvs_blind_gpcr_adrb2_v4_scorefix3_prod100k_mismatch-contact-shadow100k.json"
            ),
            "aggregate": [{"ranking_pr_auc_mean": 0.41, "topk_hit_rate_mean": 0.20}],
        },
    )

    args = _Args(
        benchmark_summary_json="runs/ligand_scaleup_benchmark_summary_current.json",
        suite_status_json="runs/ligand_scaleup_suite_status_current.json",
        failure_analysis_json="runs/gpcr_100k_failure_analysis_current.json",
        candidate_glob="runs/external_validation_*gpcr*summary.json",
        out_json="runs/gpcr_scaleup_regression_triage_current.json",
        out_md="runs/gpcr_scaleup_regression_triage_current.md",
    )
    mod.ROOT = tmp_path

    payload = mod.build_payload(args)
    candidates = {row["candidate_id"]: row for row in payload["candidates"]}

    assert payload["summary"]["candidate_count"] == 1
    assert payload["summary"]["rejected_candidate_count"] == 1
    assert payload["summary"]["comparison_only_candidate_count"] == 1
    assert "gpcr_core_mismatch_contact_rescore_v1" in candidates
    assert candidates["gpcr_core_mismatch_contact_rescore_v1"]["mode"] == "guarded_apply"
    assert candidates["gpcr_core_mismatch_contact_rescore_v1"]["pass"] is False
    assert candidates["gpcr_core_mismatch_contact_rescore_v1"]["claim_allowed"] is False
    assert candidates["gpcr_core_mismatch_contact_rescore_v1"]["reject_evidence"] is True


def test_triage_does_not_derive_candidate_version_from_base_profile_v4(tmp_path: Path) -> None:
    runs = tmp_path / "runs"
    _write_json(
        runs / "ligand_scaleup_benchmark_summary_current.json",
        {
            "claim_safe": False,
            "claim_safe_status": "regression_guardrail_failed",
            "primary_regression_task_id": "gpcr_core_full",
        },
    )
    _write_json(runs / "ligand_scaleup_suite_status_current.json", {"summary": {"suite_count": 3}})
    _write_json(
        runs
        / "external_validation_2026-05-02_mismatch_contact_apply_safesync_r3_set1_core_blind_gpcr_core_full_summary.json",
        {
            "pass": False,
            "profile_json": str(
                runs
                / "profiles"
                / "ligand_htvs_blind_gpcr_adrb2_v4_scorefix3_prod100k_mismatch-contact-apply-safesync100k.json"
            ),
            "aggregate": [{"ranking_pr_auc_mean": 0.3836, "topk_hit_rate_mean": 0.15}],
        },
    )
    _write_json(
        runs
        / "external_validation_2026-05-02_mismatch_contact_apply_safeio_r1_set1_core_blind_gpcr_core_full_summary.json",
        {
            "pass": False,
            "profile_json": str(
                runs
                / "profiles"
                / "ligand_htvs_blind_gpcr_adrb2_v4_scorefix3_prod100k_mismatch-contact-apply-safeio100k.json"
            ),
            "aggregate": [{"ranking_pr_auc_mean": 0.3936}],
        },
    )

    args = _Args(
        benchmark_summary_json="runs/ligand_scaleup_benchmark_summary_current.json",
        suite_status_json="runs/ligand_scaleup_suite_status_current.json",
        failure_analysis_json="runs/gpcr_100k_failure_analysis_current.json",
        candidate_glob="runs/external_validation_*gpcr*summary.json",
        out_json="runs/gpcr_scaleup_regression_triage_current.json",
        out_md="runs/gpcr_scaleup_regression_triage_current.md",
    )
    mod.ROOT = tmp_path

    payload = mod.build_payload(args)
    candidates = {row["candidate_id"]: row for row in payload["candidates"]}

    assert payload["summary"]["candidate_count"] == 1
    assert "gpcr_core_mismatch_contact_rescore_v1" in candidates
    assert "gpcr_core_mismatch_contact_rescore_v4" not in candidates
    assert candidates["gpcr_core_mismatch_contact_rescore_v1"]["metrics"]["topk_hit_rate"] == 0.15


def test_triage_keeps_fixed_reference_candidate_distinct_from_decoy_intrusion(tmp_path: Path) -> None:
    runs = tmp_path / "runs"
    _write_json(
        runs / "ligand_scaleup_benchmark_summary_current.json",
        {
            "claim_safe": False,
            "claim_safe_status": "regression_guardrail_failed",
            "primary_regression_task_id": "gpcr_core_full",
        },
    )
    _write_json(runs / "ligand_scaleup_suite_status_current.json", {"summary": {"suite_count": 3}})
    _write_json(
        runs / "external_validation_2026-05-02_gpcr_decoy_intrusion_apply_core_v2_set1_core_blind_gpcr_core_full_summary.json",
        {
            "pass": False,
            "profile_json": "profiles/core-decoy-intrusion-apply100k.json",
            "aggregate": [{"ranking_pr_auc_mean": 0.389, "topk_hit_rate_mean": 0.15}],
        },
    )
    _write_json(
        runs
        / "external_validation_2026-05-02_fixed_reference_decoy_intrusion_r1_set1_core_blind_gpcr_core_full_summary.json",
        {
            "pass": False,
            "profile_json": "profiles/ligand_htvs_blind_gpcr_adrb2_v4_scorefix3_prod100k_fixed-ref-decoy-intrusion100k.json",
            "aggregate": [{"ranking_pr_auc_mean": 0.0328, "topk_hit_rate_mean": 0.05}],
        },
    )

    args = _Args(
        benchmark_summary_json="runs/ligand_scaleup_benchmark_summary_current.json",
        suite_status_json="runs/ligand_scaleup_suite_status_current.json",
        failure_analysis_json="runs/gpcr_100k_failure_analysis_current.json",
        candidate_glob="runs/external_validation_*gpcr*summary.json",
        out_json="runs/gpcr_scaleup_regression_triage_current.json",
        out_md="runs/gpcr_scaleup_regression_triage_current.md",
    )
    mod.ROOT = tmp_path

    payload = mod.build_payload(args)
    candidates = {row["candidate_id"]: row for row in payload["candidates"]}

    assert payload["summary"]["candidate_count"] == 2
    assert candidates["gpcr_core_decoy_intrusion_v1"]["reject_evidence"] is True
    assert candidates["gpcr_core_fixed_reference_decoy_intrusion_v1"]["reject_evidence"] is True
    assert candidates["gpcr_core_fixed_reference_decoy_intrusion_v1"]["comparison_only"] is True


def test_triage_classifies_structure_support_rescore_as_comparison_only(tmp_path: Path) -> None:
    runs = tmp_path / "runs"
    _write_json(
        runs / "ligand_scaleup_benchmark_summary_current.json",
        {
            "claim_safe": False,
            "claim_safe_status": "regression_guardrail_failed",
            "primary_regression_task_id": "gpcr_core_full",
        },
    )
    _write_json(runs / "ligand_scaleup_suite_status_current.json", {"summary": {"suite_count": 3}})
    _write_json(
        runs
        / "profiles"
        / "ligand_htvs_blind_gpcr_adrb2_v4_scorefix3_prod100k_structure-support-rescore-rollout-r1.json",
        {"residual_prototype_mode": "apply"},
    )
    _write_json(
        runs / "external_validation_2026-05-03_r1_set1_core_blind_gpcr_core_full_summary.json",
        {
            "pass": False,
            "profile_json": str(
                runs
                / "profiles"
                / "ligand_htvs_blind_gpcr_adrb2_v4_scorefix3_prod100k_structure-support-rescore-rollout-r1.json"
            ),
            "aggregate": [{"ranking_pr_auc_mean": 0.5928, "topk_hit_rate_mean": 0.25}],
        },
    )

    args = _Args(
        benchmark_summary_json="runs/ligand_scaleup_benchmark_summary_current.json",
        suite_status_json="runs/ligand_scaleup_suite_status_current.json",
        failure_analysis_json="runs/gpcr_100k_failure_analysis_current.json",
        candidate_glob="runs/external_validation_*gpcr*summary.json",
        out_json="runs/gpcr_scaleup_regression_triage_current.json",
        out_md="runs/gpcr_scaleup_regression_triage_current.md",
    )
    mod.ROOT = tmp_path

    payload = mod.build_payload(args)
    candidates = {row["candidate_id"]: row for row in payload["candidates"]}

    assert payload["summary"]["candidate_count"] == 1
    assert candidates["gpcr_core_structure_support_rescore_v1"]["mode"] == "guarded_apply"
    assert candidates["gpcr_core_structure_support_rescore_v1"]["claim_allowed"] is False
    assert candidates["gpcr_core_structure_support_rescore_v1"]["reject_evidence"] is True
    assert candidates["gpcr_core_structure_support_rescore_v1"]["metrics"]["ranking_pr_auc"] == 0.5928
    assert candidates["gpcr_core_structure_support_rescore_v1"]["metrics"]["topk_hit_rate"] == 0.25

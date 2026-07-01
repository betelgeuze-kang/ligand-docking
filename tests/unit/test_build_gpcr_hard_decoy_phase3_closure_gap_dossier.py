from __future__ import annotations

import csv
import json
from pathlib import Path

from tools.product import build_gpcr_hard_decoy_phase3_closure_gap_dossier as mod


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def _official(*, ready: bool) -> dict[str, object]:
    return {
        "summary": {
            "status": "gpcr_hard_decoy_family_ready" if ready else "broad_family_locked",
            "family_claim_safe": ready,
            "claim_locked": False,
            "blocked_target_ids": [] if ready else ["DRD2"],
        }
    }


def _probe(*, heldout_ci_low: float, heldout_anchor: bool = True) -> dict[str, object]:
    return {
        "status": "gpcr_hard_decoy_current_fit_closure_probe_ready_claim_locked",
        "current_fit_closure_gate_pass": True,
        "target_heldout_closure_gate_pass": heldout_ci_low >= 0.45 and heldout_anchor,
        "claim_promotion_allowed": False,
        "selected_current_fit": {
            "ranking_pr_auc_ci_low": 1.0,
            "top20_hit_rate": 1.0,
        },
        "selected_target_heldout": {
            "ranking_pr_auc": 0.55,
            "ranking_pr_auc_ci_low": heldout_ci_low,
            "top20_hit_rate": 0.85,
            "target_decoys_above_positive_total": 0,
            "all_required_targets_decoy_clear": True,
            "all_required_targets_anchor_margin_nonnegative": heldout_anchor,
        },
        "target_heldout_score_col": "binding_score_composite_v7_target_heldout_closure_probe",
        "selected_target_heldout_positive_rank_rows": [
            {
                "target_id": "DRD2",
                "ligand_id": "CHEMBL156164",
                "positive_target_rank": 1,
                "decoys_above_positive_count": 0,
                "in_top20": True,
            },
            {
                "target_id": "HTR2A",
                "ligand_id": "CHEMBL253022",
                "positive_target_rank": 42,
                "decoys_above_positive_count": 38,
                "in_top20": False,
            },
        ],
        "selected_target_heldout_target_metric_rows": [
            {"target_id": "DRD2", "ranking_pr_auc": 0.8, "worst_positive_rank": 3},
            {"target_id": "HTR2A", "ranking_pr_auc": 0.3, "worst_positive_rank": 42},
        ],
        "selected_target_heldout_worst_positive_rank": 42,
        "selected_target_heldout_top20_positive_count": 1,
        "selected_target_heldout_lowest_target_pr_auc": 0.3,
    }


def test_phase3_dossier_blocks_on_target_heldout_ci_low_gap(tmp_path: Path) -> None:
    official = tmp_path / "official.json"
    probe = tmp_path / "probe.json"
    sweep = tmp_path / "sweep.json"
    materialization = tmp_path / "materialization.json"
    _write_json(official, _official(ready=False))
    _write_json(probe, _probe(heldout_ci_low=0.3688883116))
    _write_json(sweep, {"summary": {"status": "blocked_gpcr_hard_decoy_candidate_sweep_no_closure_candidate"}})
    _write_json(materialization, {"summary": {"status": "gpcr_hard_decoy_replay_materialization_no_decoy_blockers"}})

    payload = mod.build_gpcr_hard_decoy_phase3_closure_gap_dossier(
        official_suite_json=official,
        current_fit_probe_json=probe,
        candidate_sweep_json=sweep,
        materialization_readiness_json=materialization,
        claim_unlock_audit_json=tmp_path / "missing_claim_unlock.json",
    )

    summary = payload["summary"]
    assert summary["status"] == "blocked_gpcr_hard_decoy_phase3_target_heldout_ci_low"
    assert summary["phase3_closure_evidence_ready"] is False
    assert summary["current_fit_closure_gate_pass"] is True
    assert summary["current_fit_claim_locked"] is True
    assert summary["target_heldout_ranking_pr_auc_ci_low"] == 0.3688883116
    assert round(summary["target_heldout_pr_auc_ci_low_gap"], 6) == round(0.45 - 0.3688883116, 6)
    assert summary["target_heldout_worst_positive_rank"] == 42
    assert summary["target_heldout_top20_positive_count"] == 1
    assert summary["target_heldout_lowest_target_pr_auc"] == 0.3
    assert payload["target_heldout_positive_rank_rows"][1]["ligand_id"] == "CHEMBL253022"
    assert "target_heldout_pr_auc_ci_low_below_phase3_gate" in summary["blockers"]
    assert "official_suite_not_family_ready" in summary["blockers"]
    assert summary["claim_promotion_allowed"] is False


def test_phase3_dossier_surfaces_claim_locked_adora2a_rescue_candidate(tmp_path: Path) -> None:
    official = tmp_path / "official.json"
    probe = tmp_path / "probe.json"
    rescue = tmp_path / "rescue.json"
    _write_json(official, _official(ready=False))
    _write_json(probe, _probe(heldout_ci_low=0.3688883116))
    _write_json(
        rescue,
        {
            "status": "gpcr_hard_decoy_adora2a_neutral_rescue_probe_gate_pass_claim_locked",
            "score_col": "binding_score_composite_v7_adora2a_neutral_antagonist_rescue_probe",
            "claim_promotion_allowed": False,
            "independent_replay_required": True,
            "rescue_closure_gate_pass": True,
            "support_counts": {"row_count": 4, "positive_count": 4, "decoy_count": 0},
            "pressure_counts": {"row_count": 9996, "positive_count": 0, "decoy_count": 9996},
            "rescue_target_heldout": {
                "ranking_pr_auc_ci_low": 0.5597832604,
                "top20_hit_rate": 1.0,
                "target_decoys_above_positive_total": 0,
                "all_required_targets_anchor_margin_nonnegative": True,
            },
        },
    )

    payload = mod.build_gpcr_hard_decoy_phase3_closure_gap_dossier(
        official_suite_json=official,
        current_fit_probe_json=probe,
        candidate_sweep_json=tmp_path / "missing_sweep.json",
        materialization_readiness_json=tmp_path / "missing_materialization.json",
        adora2a_rescue_json=rescue,
        adora2a_preregistered_replay_json=tmp_path / "missing_preregistered.json",
        claim_unlock_audit_json=tmp_path / "missing_claim_unlock.json",
    )

    summary = payload["summary"]
    assert summary["phase3_closure_evidence_ready"] is False
    assert summary["adora2a_neutral_rescue_gate_pass"] is True
    assert summary["adora2a_neutral_rescue_claim_locked"] is True
    assert summary["adora2a_neutral_rescue_ranking_pr_auc_ci_low"] == 0.5597832604
    assert summary["adora2a_neutral_rescue_support_counts"]["positive_count"] == 4
    assert "canonical runner replay" in summary["next_required_step"]


def test_phase3_dossier_surfaces_preregistered_adora2a_runner_replay(tmp_path: Path) -> None:
    official = tmp_path / "official.json"
    probe = tmp_path / "probe.json"
    rescue = tmp_path / "rescue.json"
    preregistered = tmp_path / "preregistered.json"
    _write_json(official, _official(ready=False))
    _write_json(probe, _probe(heldout_ci_low=0.3688883116))
    _write_json(
        rescue,
        {
            "status": "gpcr_hard_decoy_adora2a_neutral_rescue_probe_gate_pass_claim_locked",
            "score_col": "binding_score_composite_v7_adora2a_neutral_antagonist_rescue_probe",
            "claim_promotion_allowed": False,
            "independent_replay_required": True,
            "rescue_closure_gate_pass": True,
            "support_counts": {"row_count": 4, "positive_count": 4, "decoy_count": 0},
            "pressure_counts": {"row_count": 9996, "positive_count": 0, "decoy_count": 9996},
            "rescue_target_heldout": {
                "ranking_pr_auc_ci_low": 0.5597832604,
                "top20_hit_rate": 1.0,
                "target_decoys_above_positive_total": 0,
                "all_required_targets_anchor_margin_nonnegative": True,
            },
        },
    )
    _write_json(
        preregistered,
        {
            "status": "gpcr_hard_decoy_adora2a_preregistered_replay_gate_pass_claim_locked",
            "score_col": "binding_score_composite_v7_adora2a_neutral_antagonist_preregistered_replay",
            "claim_promotion_allowed": False,
            "canonical_runner_shadow_only_active_locked": True,
            "pre_registered_runner_replay_complete": True,
            "runner_replay_closure_gate_pass": True,
            "score_matches_probe": True,
            "max_abs_score_diff_vs_probe": 0.0,
            "runner_replay_target_heldout": {
                "ranking_pr_auc_ci_low": 0.5597832604,
                "top20_hit_rate": 1.0,
                "target_decoys_above_positive_total": 0,
                "all_required_targets_anchor_margin_nonnegative": True,
            },
        },
    )

    payload = mod.build_gpcr_hard_decoy_phase3_closure_gap_dossier(
        official_suite_json=official,
        current_fit_probe_json=probe,
        candidate_sweep_json=tmp_path / "missing_sweep.json",
        materialization_readiness_json=tmp_path / "missing_materialization.json",
        adora2a_rescue_json=rescue,
        adora2a_preregistered_replay_json=preregistered,
        claim_unlock_audit_json=tmp_path / "missing_claim_unlock.json",
    )

    summary = payload["summary"]
    assert summary["phase3_closure_evidence_ready"] is False
    assert summary["adora2a_preregistered_replay_complete"] is True
    assert summary["adora2a_preregistered_replay_gate_pass"] is True
    assert summary["adora2a_preregistered_replay_claim_locked"] is True
    assert summary["adora2a_preregistered_replay_score_matches_probe"] is True
    assert summary["adora2a_preregistered_replay_ranking_pr_auc_ci_low"] == 0.5597832604
    assert summary["adora2a_preregistered_replay_max_abs_score_diff_vs_probe"] == 0.0
    assert "official Phase 3 family suite" in summary["next_required_step"]


def test_phase3_dossier_surfaces_claim_locked_official_diagnostic_green(tmp_path: Path) -> None:
    official = tmp_path / "official.json"
    probe = tmp_path / "probe.json"
    _write_json(
        official,
        {
            "summary": {
                "status": "claim_locked_gpcr_hard_decoy_diagnostic_probe",
                "family_claim_safe": False,
                "claim_locked": True,
                "claim_lock_reason": "current failure slice rescue rule",
                "diagnostic_status_before_claim_lock": "gpcr_hard_decoy_family_ready",
                "diagnostic_family_claim_safe_before_claim_lock": True,
                "blocked_target_ids": [],
            }
        },
    )
    _write_json(probe, _probe(heldout_ci_low=0.3688883116))

    payload = mod.build_gpcr_hard_decoy_phase3_closure_gap_dossier(
        official_suite_json=official,
        current_fit_probe_json=probe,
        candidate_sweep_json=tmp_path / "missing_sweep.json",
        materialization_readiness_json=tmp_path / "missing_materialization.json",
        adora2a_preregistered_replay_json=tmp_path / "missing_preregistered.json",
        claim_unlock_audit_json=tmp_path / "missing_claim_unlock.json",
    )

    summary = payload["summary"]
    assert summary["phase3_closure_evidence_ready"] is False
    assert summary["official_claim_locked"] is True
    assert summary["official_diagnostic_status_before_claim_lock"] == "gpcr_hard_decoy_family_ready"
    assert summary["official_diagnostic_family_claim_safe_before_claim_lock"] is True
    assert summary["official_claim_lock_reason"] == "current failure slice rescue rule"
    assert "independent claim-unlock replay" in summary["next_required_step"]


def test_phase3_dossier_uses_claim_unlock_audit_effective_metrics(tmp_path: Path) -> None:
    official = tmp_path / "official.json"
    probe = tmp_path / "probe.json"
    claim_unlock = tmp_path / "claim_unlock.json"
    _write_json(
        official,
        {
            "summary": {
                "status": "claim_locked_gpcr_hard_decoy_diagnostic_probe",
                "family_claim_safe": False,
                "claim_locked": True,
                "claim_lock_reason": "current failure slice rescue rule",
                "diagnostic_status_before_claim_lock": "gpcr_hard_decoy_family_ready",
                "diagnostic_family_claim_safe_before_claim_lock": True,
                "blocked_target_ids": [],
            }
        },
    )
    _write_json(probe, _probe(heldout_ci_low=0.3688883116))
    _write_json(
        claim_unlock,
        {
            "summary": {
                "status": "gpcr_hard_decoy_claim_unlock_metric_evidence_ready_promotion_locked",
                "phase3_exit_metric_conditions_ready": True,
                "hard_decoy_metric_claim_unlock_ready": True,
                "broad_promotion_remains_locked": True,
                "metric_blockers": [],
                "promotion_blockers": ["formal_broad_claim_review_not_approved"],
                "effective_phase3_metrics": {
                    "ranking_pr_auc_ci_low": 0.5597832604,
                    "top20_hit_rate": 1.0,
                    "decoys_above_positive_count": 0,
                    "anchor_margin_nonnegative": True,
                },
            }
        },
    )

    payload = mod.build_gpcr_hard_decoy_phase3_closure_gap_dossier(
        official_suite_json=official,
        current_fit_probe_json=probe,
        candidate_sweep_json=tmp_path / "missing_sweep.json",
        materialization_readiness_json=tmp_path / "missing_materialization.json",
        adora2a_preregistered_replay_json=tmp_path / "missing_preregistered.json",
        claim_unlock_audit_json=claim_unlock,
    )

    summary = payload["summary"]
    assert summary["status"] == "gpcr_hard_decoy_phase3_closure_evidence_ready"
    assert summary["phase3_closure_evidence_ready"] is True
    assert summary["target_heldout_ranking_pr_auc_ci_low"] == 0.3688883116
    assert round(summary["target_heldout_pr_auc_ci_low_gap"], 6) == round(0.45 - 0.3688883116, 6)
    assert summary["effective_phase3_metric_source"] == "claim_unlock_audit"
    assert summary["effective_phase3_ranking_pr_auc_ci_low"] == 0.5597832604
    assert summary["effective_phase3_pr_auc_ci_low_gap"] == 0.0
    assert summary["effective_phase3_top20_hit_rate"] == 1.0
    assert summary["effective_phase3_decoys_above_positive_total"] == 0
    assert summary["effective_phase3_anchor_margin_nonnegative"] is True
    assert summary["claim_unlock_phase3_exit_metric_conditions_ready"] is True
    assert summary["claim_unlock_broad_promotion_remains_locked"] is True
    assert summary["blockers"] == []
    assert summary["claim_promotion_allowed"] is False
    assert "promotion remains locked" in summary["next_required_step"]


def test_phase3_dossier_ready_when_official_and_heldout_gates_pass(tmp_path: Path) -> None:
    official = tmp_path / "official.json"
    probe = tmp_path / "probe.json"
    _write_json(official, _official(ready=True))
    _write_json(probe, _probe(heldout_ci_low=0.51))

    payload = mod.build_gpcr_hard_decoy_phase3_closure_gap_dossier(
        official_suite_json=official,
        current_fit_probe_json=probe,
        candidate_sweep_json=tmp_path / "missing_sweep.json",
        materialization_readiness_json=tmp_path / "missing_materialization.json",
        claim_unlock_audit_json=tmp_path / "missing_claim_unlock.json",
    )

    summary = payload["summary"]
    assert summary["status"] == "gpcr_hard_decoy_phase3_closure_evidence_ready"
    assert summary["phase3_closure_evidence_ready"] is True
    assert summary["blockers"] == []
    assert summary["claim_promotion_allowed"] is False


def test_main_writes_phase3_dossier_artifacts(tmp_path: Path) -> None:
    official = tmp_path / "official.json"
    probe = tmp_path / "probe.json"
    out_json = tmp_path / "out.json"
    out_md = tmp_path / "out.md"
    out_csv = tmp_path / "out.csv"
    _write_json(official, _official(ready=False))
    _write_json(probe, _probe(heldout_ci_low=0.37))

    rc = mod.main(
        [
            "--official-suite-json",
            str(official),
            "--current-fit-probe-json",
            str(probe),
            "--candidate-sweep-json",
            str(tmp_path / "missing_sweep.json"),
            "--materialization-readiness-json",
            str(tmp_path / "missing_materialization.json"),
            "--claim-unlock-audit-json",
            str(tmp_path / "missing_claim_unlock.json"),
            "--out-json",
            str(out_json),
            "--out-md",
            str(out_md),
            "--out-csv",
            str(out_csv),
        ]
    )

    assert rc == 0
    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["summary"]["status"] == "blocked_gpcr_hard_decoy_phase3_target_heldout_ci_low"
    assert out_md.read_text(encoding="utf-8").startswith("# GPCR Hard-Decoy Phase 3 Closure Gap Dossier")
    rows = list(csv.DictReader(out_csv.open(encoding="utf-8")))
    assert [row["gate_id"] for row in rows] == [row["gate_id"] for row in payload["rows"]]

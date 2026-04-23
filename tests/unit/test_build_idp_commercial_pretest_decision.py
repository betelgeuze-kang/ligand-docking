import json
import subprocess
import sys
from pathlib import Path

ROOT = Path("/home/betelgeuze/분자동역학")


def test_build_idp_commercial_pretest_decision_blocks_broader_promotion_when_tau_k18_fails(tmp_path: Path) -> None:
    holdout = tmp_path / "holdout.json"
    combined = tmp_path / "combined.json"
    corrected = tmp_path / "corrected.json"
    failure = tmp_path / "failure.json"
    packet = tmp_path / "packet.json"
    activation = tmp_path / "activation.json"
    holdout.write_text(
        json.dumps({"fold_count": 7, "baseline_pass_folds": 6, "corrected_pass_folds": 6, "combined_gate_pass": True}, ensure_ascii=False),
        encoding="utf-8",
    )
    combined.write_text(json.dumps({"pass": True}, ensure_ascii=False), encoding="utf-8")
    corrected.write_text(
        json.dumps(
            {
                "kalman_shadow": {
                    "feature_mask_name": "rg_sasa_only",
                    "would_change_state_count": 0,
                    "would_change_gate_count": 0,
                    "would_change_llps_flag_count": 0,
                    "would_change_aggregation_flag_count": 0,
                }
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    failure.write_text(
        json.dumps(
            {
                "summary": {
                    "failure_anchor_target": "tau_k18",
                    "blocker_reason": "tau_k18 corrected-path fragility remains the blocker for broader IDP promotion; Kalman shadow stayed telemetry-only and did not cause the failure.",
                    "do_not_infer": "Do not treat this as a Kalman-shadow regression.",
                }
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    packet.write_text(
        json.dumps({"summary": {"core_target_count": 4, "watchlist_target_count": 3, "default_feature_mask": "rg_sasa_only"}}, ensure_ascii=False),
        encoding="utf-8",
    )
    activation.write_text(json.dumps({"summary": {}}, ensure_ascii=False), encoding="utf-8")
    out_json = tmp_path / "out.json"
    out_md = tmp_path / "out.md"
    proc = subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools" / "build_idp_commercial_pretest_decision.py"),
            "--holdout-summary-json",
            str(holdout),
            "--combined-gate-json",
            str(combined),
            "--corrected-eval-json",
            str(corrected),
            "--failure-packet-json",
            str(failure),
            "--pretest-packet-json",
            str(packet),
            "--activation-result-json",
            str(activation),
            "--out-json",
            str(out_json),
            "--out-md",
            str(out_md),
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["summary"]["decision"] == "shadow_safe_retained_broader_promotion_blocked"
    assert payload["summary"]["status"] == "controlled_shadow_only_commercial_pretest_completed_shadow_safe"
    assert payload["summary"]["shadow_safe_retained"] is True
    assert payload["summary"]["broader_promotion_blocked"] is True
    assert payload["summary"]["blocking_target"] == "tau_k18"
    assert payload["summary"]["would_change_gate_count"] == 0


def test_build_idp_commercial_pretest_decision_prefers_activation_follow_up(tmp_path: Path) -> None:
    holdout = tmp_path / "holdout.json"
    combined = tmp_path / "combined.json"
    corrected = tmp_path / "corrected.json"
    failure = tmp_path / "failure.json"
    packet = tmp_path / "packet.json"
    diagnostic = tmp_path / "diagnostic.json"
    activation = tmp_path / "activation.json"
    holdout.write_text(
        json.dumps({"fold_count": 7, "baseline_pass_folds": 6, "corrected_pass_folds": 6, "combined_gate_pass": True}, ensure_ascii=False),
        encoding="utf-8",
    )
    combined.write_text(json.dumps({"pass": True}, ensure_ascii=False), encoding="utf-8")
    corrected.write_text(
        json.dumps(
            {"kalman_shadow": {"feature_mask_name": "rg_sasa_only", "would_change_state_count": 0, "would_change_gate_count": 0, "would_change_llps_flag_count": 0, "would_change_aggregation_flag_count": 0}},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    failure.write_text(json.dumps({"summary": {"failure_anchor_target": "tau_k18", "blocker_reason": "tau_k18 fragility"}}), encoding="utf-8")
    packet.write_text(json.dumps({"summary": {"core_target_count": 4, "watchlist_target_count": 3, "default_feature_mask": "rg_sasa_only"}}), encoding="utf-8")
    diagnostic.write_text(json.dumps({"summary": {"primary_observation": "short_tau_diagnostic_path_inactive_on_current_corrected_slice"}}), encoding="utf-8")
    activation.write_text(
        json.dumps(
            {
                "summary": {
                    "status": "activation_slice_completed_path_active",
                    "activation_rule_name": "short_tau_diag_r16_activation_v1",
                    "primary_observation": "short_tau_diagnostic_path_activated_on_focus_rows",
                    "focus_condition_count": 2,
                    "focus_condition_active_count": 2,
                    "activation_dominant_state_accuracy": 0.75,
                }
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    out_json = tmp_path / "out.json"
    out_md = tmp_path / "out.md"
    proc = subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools" / "build_idp_commercial_pretest_decision.py"),
            "--holdout-summary-json",
            str(holdout),
            "--combined-gate-json",
            str(combined),
            "--corrected-eval-json",
            str(corrected),
            "--failure-packet-json",
            str(failure),
            "--pretest-packet-json",
            str(packet),
            "--diagnostic-result-json",
            str(diagnostic),
            "--activation-result-json",
            str(activation),
            "--out-json",
            str(out_json),
            "--out-md",
            str(out_md),
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["summary"]["latest_activation_observation"] == "short_tau_diagnostic_path_activated_on_focus_rows"
    assert payload["summary"]["latest_activation_focus_condition_active_count"] == 2
    assert "bounded commercial-pretest rerun" in payload["summary"]["next_required_step"]


def test_build_idp_commercial_pretest_decision_prefers_validation_follow_up(tmp_path: Path) -> None:
    holdout = tmp_path / "holdout.json"
    combined = tmp_path / "combined.json"
    corrected = tmp_path / "corrected.json"
    failure = tmp_path / "failure.json"
    packet = tmp_path / "packet.json"
    diagnostic = tmp_path / "diagnostic.json"
    activation = tmp_path / "activation.json"
    validation = tmp_path / "validation.json"
    holdout.write_text(json.dumps({"fold_count": 7, "baseline_pass_folds": 6, "corrected_pass_folds": 6, "combined_gate_pass": True}), encoding="utf-8")
    combined.write_text(json.dumps({"pass": True}), encoding="utf-8")
    corrected.write_text(json.dumps({"kalman_shadow": {"feature_mask_name": "rg_sasa_only", "would_change_state_count": 0, "would_change_gate_count": 0, "would_change_llps_flag_count": 0, "would_change_aggregation_flag_count": 0}}), encoding="utf-8")
    failure.write_text(json.dumps({"summary": {"failure_anchor_target": "tau_k18", "blocker_reason": "tau_k18 fragility"}}), encoding="utf-8")
    packet.write_text(json.dumps({"summary": {"core_target_count": 4, "watchlist_target_count": 3, "default_feature_mask": "rg_sasa_only"}}), encoding="utf-8")
    diagnostic.write_text(json.dumps({"summary": {"primary_observation": "short_tau_diagnostic_path_inactive_on_current_corrected_slice"}}), encoding="utf-8")
    activation.write_text(json.dumps({"summary": {"status": "activation_slice_completed_path_active", "activation_rule_name": "short_tau_diag_r16_activation_v1", "primary_observation": "short_tau_diagnostic_path_activated_on_focus_rows", "focus_condition_count": 2, "focus_condition_active_count": 2, "activation_dominant_state_accuracy": 0.75}}), encoding="utf-8")
    validation.write_text(json.dumps({"summary": {"status": "bounded_commercial_pretest_completed_blocker_persists_activation_retained", "fold_count": 7, "corrected_pass_folds": 6, "tau_k18_corrected_gate_pass": False, "next_required_step": "Use the tau_k18 full-fold corrected failure slice to choose exactly one next corrected-path interpretation or calibration rule."}}), encoding="utf-8")
    out_json = tmp_path / "out.json"
    out_md = tmp_path / "out.md"
    proc = subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools" / "build_idp_commercial_pretest_decision.py"),
            "--holdout-summary-json", str(holdout),
            "--combined-gate-json", str(combined),
            "--corrected-eval-json", str(corrected),
            "--failure-packet-json", str(failure),
            "--pretest-packet-json", str(packet),
            "--diagnostic-result-json", str(diagnostic),
            "--activation-result-json", str(activation),
            "--validation-result-json", str(validation),
            "--out-json", str(out_json),
            "--out-md", str(out_md),
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["summary"]["latest_validation_status"] == "bounded_commercial_pretest_completed_blocker_persists_activation_retained"
    assert "full-fold corrected failure slice" in payload["summary"]["next_required_step"]


def test_build_idp_commercial_pretest_decision_requires_same_scope_or_new_anchor_when_clean_but_no_true_broader_roster(tmp_path: Path) -> None:
    holdout = tmp_path / "holdout.json"
    combined = tmp_path / "combined.json"
    corrected = tmp_path / "corrected.json"
    failure = tmp_path / "failure.json"
    packet = tmp_path / "packet.json"
    activation = tmp_path / "activation.json"
    validation = tmp_path / "validation.json"
    viability = tmp_path / "viability.json"
    processcheck = tmp_path / "processcheck.json"
    page4_promotion = tmp_path / "page4_promotion.json"
    holdout.write_text(json.dumps({"fold_count": 7, "baseline_pass_folds": 7, "corrected_pass_folds": 7, "combined_gate_pass": True}), encoding="utf-8")
    combined.write_text(json.dumps({"pass": True}), encoding="utf-8")
    corrected.write_text(json.dumps({"kalman_shadow": {"feature_mask_name": "rg_sasa_only", "would_change_state_count": 0, "would_change_gate_count": 0, "would_change_llps_flag_count": 0, "would_change_aggregation_flag_count": 0}}), encoding="utf-8")
    failure.write_text(json.dumps({"summary": {"failure_anchor_target": "tau_k18", "blocker_reason": "tau_k18 fragility"}}), encoding="utf-8")
    packet.write_text(json.dumps({"summary": {"core_target_count": 4, "watchlist_target_count": 3, "default_feature_mask": "rg_sasa_only"}}), encoding="utf-8")
    activation.write_text(json.dumps({"summary": {}}), encoding="utf-8")
    validation.write_text(json.dumps({"summary": {"status": "bounded_commercial_pretest_completed_activation_retained", "fold_count": 7, "corrected_pass_folds": 7, "tau_k18_corrected_gate_pass": True}}), encoding="utf-8")
    viability.write_text(json.dumps({"summary": {"additional_anchor_backed_target_count": 0, "provisional_only_target_count": 13}}), encoding="utf-8")
    processcheck.write_text(
        json.dumps(
            {
                "summary": {
                    "status": "same_scope_processcheck_completed_reproducibility_confirmed",
                    "fold_count": 7,
                    "corrected_pass_folds": 7,
                    "would_change_state_count": 0,
                    "would_change_gate_count": 0,
                }
            }
        ),
        encoding="utf-8",
    )
    page4_promotion.write_text(
        json.dumps({"summary": {"anchor_backed_candidate_ready_now": True}}, ensure_ascii=False),
        encoding="utf-8",
    )
    out_json = tmp_path / "out.json"
    out_md = tmp_path / "out.md"
    proc = subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools" / "build_idp_commercial_pretest_decision.py"),
            "--holdout-summary-json", str(holdout),
            "--combined-gate-json", str(combined),
            "--corrected-eval-json", str(corrected),
            "--failure-packet-json", str(failure),
            "--pretest-packet-json", str(packet),
            "--activation-result-json", str(activation),
            "--validation-result-json", str(validation),
            "--roster-viability-json", str(viability),
            "--same-scope-processcheck-result-json", str(processcheck),
            "--page4-promotion-review-json", str(page4_promotion),
            "--out-json", str(out_json),
            "--out-md", str(out_md),
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["summary"]["decision"] == "shadow_safe_retained_promotion_review_required"
    assert payload["summary"]["additional_anchor_backed_target_count"] == 0
    assert payload["summary"]["provisional_only_target_count"] == 13
    assert payload["summary"]["same_scope_reproducibility_confirmed"] is True
    assert payload["summary"]["page4_candidate_ready_now"] is True
    assert payload["summary"]["blocking_class"] == "page4_quantitative_anchor_replacement_required"
    assert payload["summary"]["next_anchor_curation_target"] == "page4_quantitative_anchor_replacement"
    assert "same-scope reproducibility" in payload["summary"]["next_required_step"]
    assert "page4 quantitative anchor replacement" in payload["summary"]["next_required_step"]


def test_build_idp_commercial_pretest_decision_reopens_broader_review_once_page4_counts_as_additional_anchor(tmp_path: Path) -> None:
    holdout = tmp_path / "holdout.json"
    combined = tmp_path / "combined.json"
    corrected = tmp_path / "corrected.json"
    failure = tmp_path / "failure.json"
    packet = tmp_path / "packet.json"
    validation = tmp_path / "validation.json"
    viability = tmp_path / "viability.json"
    processcheck = tmp_path / "processcheck.json"
    page4_promotion = tmp_path / "page4_promotion.json"
    holdout.write_text(json.dumps({"fold_count": 7, "baseline_pass_folds": 7, "corrected_pass_folds": 7, "combined_gate_pass": True}), encoding="utf-8")
    combined.write_text(json.dumps({"pass": True}), encoding="utf-8")
    corrected.write_text(json.dumps({"kalman_shadow": {"feature_mask_name": "rg_sasa_only", "would_change_state_count": 0, "would_change_gate_count": 0, "would_change_llps_flag_count": 0, "would_change_aggregation_flag_count": 0}}), encoding="utf-8")
    failure.write_text(json.dumps({"summary": {"failure_anchor_target": "tau_k18", "blocker_reason": "tau_k18 fragility"}}), encoding="utf-8")
    packet.write_text(json.dumps({"summary": {"core_target_count": 4, "watchlist_target_count": 3, "default_feature_mask": "rg_sasa_only"}}), encoding="utf-8")
    validation.write_text(json.dumps({"summary": {"status": "bounded_commercial_pretest_completed_activation_retained", "fold_count": 7, "corrected_pass_folds": 7, "tau_k18_corrected_gate_pass": True}}), encoding="utf-8")
    viability.write_text(json.dumps({"summary": {"additional_anchor_backed_target_count": 1, "provisional_only_target_count": 12}}), encoding="utf-8")
    processcheck.write_text(json.dumps({"summary": {"status": "same_scope_processcheck_completed_reproducibility_confirmed", "fold_count": 7, "corrected_pass_folds": 7, "would_change_state_count": 0, "would_change_gate_count": 0}}), encoding="utf-8")
    page4_promotion.write_text(json.dumps({"summary": {"anchor_backed_candidate_ready_now": True}}, ensure_ascii=False), encoding="utf-8")
    out_json = tmp_path / "out.json"
    out_md = tmp_path / "out.md"
    proc = subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools" / "build_idp_commercial_pretest_decision.py"),
            "--holdout-summary-json", str(holdout),
            "--combined-gate-json", str(combined),
            "--corrected-eval-json", str(corrected),
            "--failure-packet-json", str(failure),
            "--pretest-packet-json", str(packet),
            "--validation-result-json", str(validation),
            "--roster-viability-json", str(viability),
            "--same-scope-processcheck-result-json", str(processcheck),
            "--page4-promotion-review-json", str(page4_promotion),
            "--out-json", str(out_json),
            "--out-md", str(out_md),
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["summary"]["decision"] == "shadow_safe_retained_promotion_review_required"
    assert payload["summary"]["blocking_target"] == "broader_shadow_review"
    assert payload["summary"]["blocking_class"] == "bounded_review_required"
    assert payload["summary"]["next_anchor_curation_target"] == "broader_shadow_review"
    assert "broader-shadow review packet" in payload["summary"]["next_required_step"]

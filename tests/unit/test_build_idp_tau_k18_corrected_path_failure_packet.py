import json
import subprocess
import sys
from pathlib import Path

ROOT = Path("/home/betelgeuze/분자동역학")


def test_build_idp_tau_k18_corrected_path_failure_packet(tmp_path: Path) -> None:
    baseline_gate = tmp_path / "baseline_gate.json"
    corrected_gate = tmp_path / "corrected_gate.json"
    baseline_eval = tmp_path / "baseline_eval.json"
    corrected_eval = tmp_path / "corrected_eval.json"
    baseline_gate.write_text(
        json.dumps({"pass": True}, ensure_ascii=False),
        encoding="utf-8",
    )
    corrected_gate.write_text(
        json.dumps(
            {
                "pass": False,
                "utility_gate_pass": False,
                "physics_gate_pass": True,
                "classification_metrics": {
                    "dominant_state_accuracy": 0.375,
                    "branch_macro_f1": 0.3333,
                    "llps_flag_pr_auc": 0.0,
                    "aggregation_flag_pr_auc": 1.0,
                },
                "ranking_metrics": {
                    "compactness_rank_auc": 0.89,
                    "helicity_rank_auc": 1.0,
                    "condensation_rank_auc": 0.93,
                },
                "anchor_diagnostics": {
                    "rg_mean": {"median_normalized_error": 4.8},
                    "sasa_proxy_mean": {"median_normalized_error": 2.5},
                },
                "gate_context": {"effective_thresholds": {"min_dominant_state_accuracy": 0.7}},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    baseline_eval.write_text(
        json.dumps(
            {
                "targets": [
                    {
                        "condition_group": "base",
                        "true_dominant_state": "compact_disordered",
                        "dominant_state_label": "compact_disordered",
                        "pred_state": "compact_disordered",
                        "target_pass": True,
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    corrected_eval.write_text(
        json.dumps(
            {
                "targets": [
                    {
                        "condition_group": "base",
                        "true_dominant_state": "compact_disordered",
                        "dominant_state_label": "compact_disordered",
                        "pred_state": "helix_enriched",
                        "target_pass": False,
                        "would_have_changed_state": False,
                        "would_have_changed_gate": False,
                        "kf_shadow_dominant_state_label": "compact_disordered",
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    out_json = tmp_path / "out.json"
    out_csv = tmp_path / "out.csv"
    out_md = tmp_path / "out.md"
    proc = subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools" / "build_idp_tau_k18_corrected_path_failure_packet.py"),
            "--baseline-gate-json",
            str(baseline_gate),
            "--corrected-gate-json",
            str(corrected_gate),
            "--baseline-eval-json",
            str(baseline_eval),
            "--corrected-eval-json",
            str(corrected_eval),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["summary"]["status"] == "corrected_path_failure_packet_ready"
    assert payload["summary"]["shadow_safe_retained"] is True
    assert payload["summary"]["corrected_pass"] is False
    assert payload["summary"]["failure_anchor_target"] == "tau_k18"
    assert payload["summary"]["kalman_gate_change_count"] == 0
    assert "Kalman shadow" in payload["summary"]["blocker_reason"]


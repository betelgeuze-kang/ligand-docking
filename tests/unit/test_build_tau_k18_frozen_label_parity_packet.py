from __future__ import annotations

from tools import build_tau_k18_frozen_label_parity_packet as mod


def test_build_tau_k18_frozen_label_parity_packet() -> None:
    payload = mod.build_payload(
        {
            "summary": {
                "operator_scope_now": "controlled_shadow_only_commercial_pretest",
                "blocking_target": "tau_k18",
                "candidate_rule_name": "short_tau_ph_split_helix_gate_v1",
            }
        },
        frozen_labels_csv="runs/idp_3bead_holdout_v7_sb_rust_2026-03-19_r2_fold6_tau_k18_eval_corrected_targets.csv",
        out_prefix="runs/idp_tau_k18_stabilization_trial_commercial_pretest_seed123_phsplithelix_frozen_r1",
    )

    summary = payload["summary"]
    assert summary["packet_scope"] == "tau_k18_frozen_label_parity_rerun"
    assert summary["candidate_rule_name"] == "short_tau_ph_split_helix_gate_v1"
    assert "frozen-labels-csv" in summary["exact_command"]

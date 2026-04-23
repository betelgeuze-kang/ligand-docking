from __future__ import annotations

import json
from pathlib import Path

from tools.build_idp_3bead_holdout_cleanup_review_manifest import build_payload


def test_build_idp_3bead_holdout_cleanup_review_manifest(tmp_path: Path) -> None:
    runs = tmp_path / "runs"
    runs.mkdir()

    protected = "idp_3bead_holdout_v7_anchor_commercial_pretest_r1"
    referenced = "idp_3bead_holdout_v7_sb_rust_2026-03-20_r3_speedopt3"
    stale = "idp_3bead_holdout_v7_fastpair_2026-03-16_r1"

    (runs / f"{protected}_combined_gate_summary.json").write_text("{}", encoding="utf-8")
    (runs / f"{referenced}_fold1_alpha_eval_corrected_targets.csv").write_text("a,b\n", encoding="utf-8")
    (runs / f"{stale}_combined_gate_summary.json").write_text("{}", encoding="utf-8")
    (runs / "idp_tau_k18_feature_state_v1_shadow_current_summary.json").write_text(
        json.dumps({"source_csv": f"runs/{referenced}_fold1_alpha_eval_corrected_targets.csv"}),
        encoding="utf-8",
    )

    payload = build_payload(str(runs))
    rows = {row["prefix"]: row for row in payload["rows"]}

    assert payload["summary"]["status"] == "idp_3bead_holdout_cleanup_review_manifest_ready"
    assert rows[protected]["classification"] == "protected_current_lane"
    assert rows[protected]["recommended_disposition"] == "keep_in_active_root"
    assert rows[referenced]["classification"] == "review_hold_current_reference"
    assert rows[referenced]["current_reference_count"] == 1
    assert rows[stale]["recommended_disposition"] == "review_for_archive_after_prefix_signoff"

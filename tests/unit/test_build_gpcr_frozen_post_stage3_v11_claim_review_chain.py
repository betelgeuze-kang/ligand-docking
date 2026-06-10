from __future__ import annotations

import json
from pathlib import Path

from tools.gpcr_replay.build_gpcr_frozen_post_stage3_v11_claim_review_chain import build_packet


def test_post_stage3_chain_blocks_without_stage3_csv(tmp_path: Path) -> None:
    payload = build_packet(
        stage3_scores_csv=tmp_path / "missing_stage3.csv",
        generated_at_local="2026-06-07T19:20:00+09:00",
    )
    summary = payload["summary"]
    assert summary["status"] == "blocked_wait_stage3_scores_csv"
    assert summary["claim_promotion_allowed"] is False
    assert "stage3_scores_csv_missing" in summary["blockers"]


def test_post_stage3_chain_runs_review_steps_when_stage3_present(tmp_path: Path, monkeypatch) -> None:
    stage3 = tmp_path / "stage3_scores.csv"
    stage3.write_text("target,ligand_id\nT1,L1\n", encoding="utf-8")
    feature_json = tmp_path / "cache.json"
    review_json = tmp_path / "review.json"
    guarded_json = tmp_path / "guarded.json"

    def _fake_run(cmd: list[str]) -> None:
        if "build_gpcr_cationic_pose_distortion_frozen_feature_cache.py" in cmd[1]:
            out_json = Path(cmd[cmd.index("--out-json") + 1])
            out_json.write_text(
                json.dumps({"summary": {"status": "feature_cache_ready_for_shadow_replay_claim_locked", "feature_row_count": 2}}),
                encoding="utf-8",
            )
            return
        if "build_gpcr_guarded_100k_rerun_readiness.py" in cmd[1]:
            guarded_json.write_text(
                json.dumps({"summary": {"status": "blocked", "claim_review_eligible": False, "blockers": ["ci_low_blocked"]}}),
                encoding="utf-8",
            )

    def _fake_v11_chain(**kwargs: object) -> dict[str, object]:
        review_json.write_text(
            json.dumps({"summary": {"status": "blocked_frozen_shadow_review_claim_locked", "blockers": ["shadow_top20_has_no_positive"]}}),
            encoding="utf-8",
        )
        return {
            "summary": {
                "status": "blocked_frozen_shadow_review_claim_locked",
                "shadow_top20_positive_count": 0,
                "blockers": ["shadow_top20_has_no_positive"],
            }
        }

    monkeypatch.setattr(
        "tools.gpcr_replay.build_gpcr_frozen_post_stage3_v11_claim_review_chain._run",
        _fake_run,
    )
    monkeypatch.setattr(
        "tools.gpcr_replay.build_gpcr_frozen_v11_discriminator_replay_chain.build_packet",
        _fake_v11_chain,
    )

    payload = build_packet(
        stage3_scores_csv=stage3,
        feature_cache_csv=tmp_path / "cache.csv",
        feature_cache_json=feature_json,
        v11_review_json=review_json,
        guarded_readiness_json=guarded_json,
        generated_at_local="2026-06-07T19:20:00+09:00",
    )
    summary = payload["summary"]
    assert summary["feature_row_count"] == 2
    assert summary["claim_promotion_allowed"] is False
    assert summary["full_100k_claim_review_allowed"] is False
    assert "shadow_top20_has_no_positive" in summary["blockers"]

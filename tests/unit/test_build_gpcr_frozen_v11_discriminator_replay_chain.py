from __future__ import annotations

import json
from pathlib import Path

from tools.gpcr_replay.build_gpcr_frozen_v11_discriminator_replay_chain import build_packet


def test_frozen_v11_discriminator_chain_reads_nested_review_fields(tmp_path: Path, monkeypatch) -> None:
    input_cache = tmp_path / "input_cache.csv"
    input_cache.write_text(
        "target,ligand_id,base_score,basic_amine_count,cationic_center_basic_atom_count,"
        "ligand_h_donors,ligand_h_acceptors,ligand_rot_bonds,ligand_logp,"
        "atom_contact_fraction_le_2p8A,atom_contact_fraction_2p8_4p2A,"
        "cationic_center_contact_fraction_2p8_4p2A,cationic_center_contact_fraction_le_2p8A,"
        "cationic_center_contact_fraction_ge_4p2A,coarse_centroid_preservation_rmsd_A_mean,"
        "atom_anchor_mean_distance_A,label_free_penalty_pressure,label_free_support_pressure,"
        "false_valid_anchor_discriminator_pressure,weak_base_rescue_support_pressure,weak_base_rescue_gate\n"
        "CHEMBL217_DRD2_HUMAN,decoy,-2.0,0,1,1,2,3,1.0,0.1,0.5,0.5,0.1,0.1,1.0,3.5,1.0,0.0,0.5,0.0,0.0\n",
        encoding="utf-8",
    )

    def _fake_run(cmd: list[str]) -> None:
        if "recompute_gpcr_frozen_feature_cache_discriminator_pressures.py" in cmd[1]:
            refreshed = Path(cmd[cmd.index("--out-csv") + 1])
            out_json = Path(cmd[cmd.index("--out-json") + 1])
            refreshed.write_text(input_cache.read_text(encoding="utf-8"), encoding="utf-8")
            out_json.write_text(
                json.dumps(
                    {
                        "summary": {
                            "status": "discriminator_pressure_refresh_ready",
                            "false_valid_anchor_discriminator_row_count": 1,
                        }
                    }
                ),
                encoding="utf-8",
            )
            return
        if "replay_gpcr_residual_shadow_scores.py" in cmd[1]:
            replay_summary = Path(cmd[cmd.index("--out-summary-json") + 1])
            replay_summary.write_text(
                json.dumps({"summary": {"status": "ready_for_evaluation", "active_score_locked_to_base": True}}),
                encoding="utf-8",
            )
            Path(cmd[cmd.index("--out-scores-csv") + 1]).write_text("target,ligand_id\n", encoding="utf-8")
            return
        if "build_gpcr_cationic_weakbase_frozen_shadow_replay_review.py" in cmd[1]:
            review_json = Path(cmd[cmd.index("--out-json") + 1])
            review_json.write_text(
                json.dumps(
                    {
                        "summary": {
                            "status": "blocked_frozen_shadow_review_claim_locked",
                            "shadow_score_summary": {
                                "top20_positive_count": 0,
                                "target_positive_ranks": {
                                    "CHEMBL217_DRD2_HUMAN": [{"decoys_above_positive": 498}]
                                },
                            },
                            "blockers": ["shadow_top20_has_no_positive"],
                            "next_required_step": "wait for stage2",
                        }
                    }
                ),
                encoding="utf-8",
            )

    monkeypatch.setattr(
        "tools.gpcr_replay.build_gpcr_frozen_v11_discriminator_replay_chain._run",
        _fake_run,
    )

    payload = build_packet(
        input_cache_csv=input_cache,
        refreshed_cache_csv=tmp_path / "refreshed.csv",
        spec_json=tmp_path / "spec.json",
        replay_scores_csv=tmp_path / "replay_scores.csv",
        replay_summary_json=tmp_path / "replay_summary.json",
        review_json=tmp_path / "review.json",
        generated_at_local="2026-06-07T00:00:00+09:00",
    )
    summary = payload["summary"]
    assert summary["refresh_status"] == "discriminator_pressure_refresh_ready"
    assert summary["false_valid_anchor_discriminator_row_count"] == 1
    assert summary["shadow_top20_positive_count"] == 0
    assert summary["drd2_decoys_above_positive"] == 498
    assert summary["claim_promotion_allowed"] is False

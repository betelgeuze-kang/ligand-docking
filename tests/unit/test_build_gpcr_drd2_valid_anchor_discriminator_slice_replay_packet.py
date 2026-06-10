from __future__ import annotations

import json
from pathlib import Path

from tools.gpcr_replay.build_gpcr_drd2_valid_anchor_discriminator_slice_replay_packet import (
    SPEC_VARIANT,
    build_packet,
)


def test_valid_anchor_discriminator_packet_uses_v11_variant(tmp_path: Path, monkeypatch) -> None:
    rows_csv = tmp_path / "slice_rows.csv"
    rows_csv.write_text(
        "target,ligand_id,is_positive,base_score,label_free_penalty_pressure,label_free_support_pressure,"
        "false_valid_anchor_discriminator_pressure,weak_base_rescue_support_pressure,weak_base_rescue_gate,"
        "atom_anchor_mean_distance_A,atom_contact_fraction_2p8_4p2A,basic_amine_count,cationic_center_basic_atom_count,"
        "slice_label_text\n"
        "CHEMBL217_DRD2_HUMAN,decoy,False,-2.0,1.0,0.0,0.5,0.0,0.0,3.5,0.5,0,1,window_like_nonbasic\n"
        "CHEMBL217_DRD2_HUMAN,CHEMBL301265,True,-1.0,0.0,0.8,0.0,0.8,1.0,2.8,0.8,1,2,positive_repaired_anchor_window\n",
        encoding="utf-8",
    )

    def _fake_run(cmd: list[str]) -> None:
        return None

    monkeypatch.setattr(
        "tools.gpcr_replay.build_gpcr_drd2_valid_anchor_discriminator_slice_replay_packet._run",
        _fake_run,
    )

    payload = build_packet(
        slice_rows_csv=rows_csv,
        penalty_envelope_json=tmp_path / "penalty.json",
        slice_scores_csv=tmp_path / "scores.csv",
        spec_json=tmp_path / "spec.json",
        replay_scores_csv=tmp_path / "replay_scores.csv",
        replay_summary_json=tmp_path / "replay_summary.json",
        review_json=tmp_path / "review.json",
        rebuild_slice=False,
        generated_at_local="2026-06-07T00:00:00+09:00",
    )
    assert payload["summary"]["spec_variant"] == SPEC_VARIANT
    assert (tmp_path / "spec.json").exists()
    spec = json.loads((tmp_path / "spec.json").read_text(encoding="utf-8"))
    assert spec["prototype"]["tuning"]["variant"] == SPEC_VARIANT

from __future__ import annotations

import csv
import json
from pathlib import Path

from tools.gpcr_replay import build_gpcr_drd2_hard_decoy_penalty_envelope as penalty_mod
from tools.gpcr_replay.build_gpcr_drd2_hard_decoy_slice_packet import _candidate_pressures


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def test_window_like_nonbasic_pressure_is_nonzero_without_basic_amine() -> None:
    pressures = _candidate_pressures(
        {
            "basic_amine_count": 0,
            "cationic_center_basic_atom_count": 0,
            "atom_contact_fraction_2p8_4p2A": 0.75,
            "cationic_center_contact_fraction_2p8_4p2A": 0.0,
            "cationic_center_contact_fraction_ge_4p2A": 1.0,
        }
    )
    assert pressures["window_like_nonbasic_pressure"] > 0.0
    assert pressures["label_free_penalty_pressure"] >= pressures["window_like_nonbasic_pressure"]


def test_false_valid_anchor_discriminator_penalizes_geometry_only_basic() -> None:
    pressures = _candidate_pressures(
        {
            "basic_amine_count": 0,
            "cationic_center_basic_atom_count": 1,
            "atom_contact_fraction_2p8_4p2A": 1.0,
            "atom_contact_fraction_le_2p8A": 0.0,
            "cationic_center_contact_fraction_2p8_4p2A": 1.0,
            "cationic_center_contact_fraction_le_2p8A": 0.0,
            "coarse_centroid_preservation_rmsd_A_mean": 0.5,
        }
    )
    assert pressures["false_valid_anchor_discriminator_pressure"] > 0.0
    assert pressures["valid_anchor_support"] == 0.0
    assert pressures["label_free_support_pressure"] == 0.0


def test_penalty_envelope_can_clear_positive_when_window_like_pressure_present(tmp_path: Path) -> None:
    rows_csv = tmp_path / "slice_rows.csv"
    _write_csv(
        rows_csv,
        [
            {
                "ligand_id": "window_decoy",
                "is_positive": "False",
                "base_score": "-11.0",
                "label_free_penalty_pressure": "0.75",
                "label_free_support_pressure": "0.0",
                "slice_label_text": "window_like_nonbasic",
            },
            {
                "ligand_id": "CHEMBL301265",
                "is_positive": "True",
                "base_score": "-0.5",
                "label_free_penalty_pressure": "0.0",
                "label_free_support_pressure": "0.8",
                "slice_label_text": "positive_repaired_anchor_window",
            },
        ],
    )
    payload, _ = penalty_mod.build_envelope(
        rows_csv=rows_csv,
        grid="0,5,10,15,20",
        topk_threshold=1,
        bounded_weight_ceiling=20.0,
    )
    assert payload["summary"]["status"] == "slice_pairwise_green_diagnostic_only"
    assert payload["summary"]["bounded_best_positive_rank"] == 1


def test_repaired_slice_shadow_replay_packet_writes_summary(tmp_path: Path, monkeypatch) -> None:
    rows_csv = tmp_path / "slice_rows.csv"
    _write_csv(
        rows_csv,
        [
            {
                "target": "CHEMBL217_DRD2_HUMAN",
                "ligand_id": "decoy",
                "is_positive": "False",
                "base_score": "-2.0",
                "label_free_penalty_pressure": "2.0",
                "label_free_support_pressure": "0.0",
                "window_like_nonbasic_pressure": "0.0",
                "invalid_close_overanchor_pressure": "2.0",
                "hydrophobic_overcontact_pressure": "0.0",
                "multipolar_basic_pressure": "0.0",
                "cationic_mismatch_pressure": "0.0",
                "pose_distortion_pressure": "0.0",
                "pose_preservation_support": "0.0",
                "valid_anchor_support": "0.0",
                "compact_anchor_support": "0.0",
                "atom_anchor_mean_distance_A": "3.5",
                "atom_contact_fraction_2p8_4p2A": "0.5",
                "ligand_h_donors": "0",
                "ligand_h_acceptors": "0",
                "ligand_rot_bonds": "0",
                "ligand_logp": "0",
                "basic_amine_count": "0",
                "slice_label_text": "invalid_close_overanchor_no_basic",
            },
            {
                "target": "CHEMBL217_DRD2_HUMAN",
                "ligand_id": "CHEMBL301265",
                "is_positive": "True",
                "base_score": "-1.0",
                "label_free_penalty_pressure": "0.0",
                "label_free_support_pressure": "0.8",
                "window_like_nonbasic_pressure": "0.0",
                "invalid_close_overanchor_pressure": "0.0",
                "hydrophobic_overcontact_pressure": "0.0",
                "multipolar_basic_pressure": "0.0",
                "cationic_mismatch_pressure": "0.0",
                "pose_distortion_pressure": "0.0",
                "pose_preservation_support": "1.0",
                "valid_anchor_support": "0.8",
                "compact_anchor_support": "0.8",
                "atom_anchor_mean_distance_A": "2.8",
                "atom_contact_fraction_2p8_4p2A": "0.8",
                "ligand_h_donors": "1",
                "ligand_h_acceptors": "1",
                "ligand_rot_bonds": "2",
                "ligand_logp": "2.0",
                "basic_amine_count": "1",
                "slice_label_text": "positive_repaired_anchor_window",
            },
        ],
    )

    from tools.gpcr_replay import build_gpcr_drd2_repaired_slice_shadow_replay_packet as replay_mod

    calls: list[list[str]] = []

    def _fake_run(cmd: list[str]) -> None:
        calls.append(cmd)

    monkeypatch.setattr(replay_mod, "_run", _fake_run)

    out_json = tmp_path / "replay_packet.json"
    payload = replay_mod.build_packet(
        slice_rows_csv=rows_csv,
        penalty_envelope_json=tmp_path / "penalty.json",
        slice_scores_csv=tmp_path / "slice_scores.csv",
        spec_json=tmp_path / "spec.json",
        replay_scores_csv=tmp_path / "replay_scores.csv",
        replay_summary_json=tmp_path / "replay_summary.json",
        review_json=tmp_path / "review.json",
    )
    assert payload["summary"]["slice_row_count"] == 2
    assert any("build_gpcr_drd2_hard_decoy_penalty_envelope.py" in " ".join(cmd) for cmd in calls)
    assert out_json.parent.exists()


def test_stage2_launch_packet_reports_mount_stage2_absence(tmp_path: Path) -> None:
    mount_root = tmp_path / "mount"
    run_root = mount_root / "frozen_run"
    (run_root / "stage3_delivery").mkdir(parents=True)
    profile_json = tmp_path / "profile.json"
    profile_json.write_text("{}", encoding="utf-8")

    from tools.gpcr_replay.build_gpcr_frozen_stage2_regeneration_launch_packet import build_packet

    payload = build_packet(
        mount_root=str(mount_root),
        frozen_run_id="frozen_run",
        profile_json=str(profile_json),
        out_prefix=str(tmp_path / "out_prefix"),
        restoration_json=str(tmp_path / "missing_restoration.json"),
        replay_json=str(tmp_path / "missing_replay.json"),
        gap_json=str(tmp_path / "missing_gap.json"),
        generated_at_local="2026-06-07T00:00:00+09:00",
    )
    summary = payload["summary"]
    assert summary["launch_allowed"] is True
    assert summary["mount_stage2_npz_count"] == 0
    assert summary["mount_stage3_npz_count"] == 0
    assert "run_ligand_stress_validation.py" in summary["recommended_resume_command"]

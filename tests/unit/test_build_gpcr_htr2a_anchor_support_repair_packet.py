from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path

from tools import build_gpcr_htr2a_anchor_support_repair_packet as mod

ROOT = Path(__file__).resolve().parents[2]


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _row(
    *,
    ligand_id: str,
    base_score: float,
    shadow_score: float,
    basic_amine_count: int,
    support: float,
    penalty: float,
    pose_support: float,
    atom_le_2p8: float,
    cationic_2p8_4p2: float,
) -> dict[str, object]:
    return {
        "target": "CHEMBL224_HTR2A_HUMAN",
        "ligand_id": ligand_id,
        "base_score": base_score,
        "binding_score_composite_v7_residual_shadow": shadow_score,
        "effective_label_free_anchor_mode": "all_basic",
        "label_free_anchor_mode": "all_basic",
        "basic_amine_count": basic_amine_count,
        "repaired_ligand_frame_atom_count": 20,
        "label_free_support_pressure": support,
        "label_free_penalty_pressure": penalty,
        "pose_preservation_support": pose_support,
        "coarse_centroid_preservation_rmsd_A_mean": 1.0,
        "atom_anchor_min_distance_A": 2.4,
        "atom_contact_fraction_le_2p8A": atom_le_2p8,
        "atom_contact_fraction_2p8_4p2A": 0.0,
        "cationic_center_min_distance_A": 3.2,
        "cationic_center_contact_fraction_le_2p8A": 0.0,
        "cationic_center_contact_fraction_2p8_4p2A": cationic_2p8_4p2,
        "invalid_close_overanchor_pressure": 0.0,
        "hydrophobic_overcontact_pressure": 0.0,
        "multipolar_basic_pressure": 0.0,
        "cationic_mismatch_pressure": 0.0,
        "adaptive_selection_reason": "all_basic_anchor_gain_pose_preserved",
    }


def test_build_packet_flags_htr2a_anchor_signature_nonidentifiability(tmp_path: Path) -> None:
    pose_gap = tmp_path / "pose_gap.json"
    scores = tmp_path / "scores.csv"
    _write_json(
        pose_gap,
        {
            "summary": {"score_col": "binding_score_composite_v7_residual_shadow"},
            "target_summaries": [
                {
                    "target": "CHEMBL224_HTR2A_HUMAN",
                    "ligand_id": "CHEMBL83894",
                    "target_rank": 3,
                    "decoys_above_positive": 2,
                    "label_free_support_pressure": 0.0,
                    "pose_preservation_support": 0.4,
                    "blockers": [
                        "target_decoys_above_positive",
                        "positive_anchor_support_missing",
                        "positive_pose_preservation_borderline",
                    ],
                }
            ],
        },
    )
    _write_csv(
        scores,
        [
            _row(
                ligand_id="decoy_collision",
                base_score=-6.0,
                shadow_score=-6.0,
                basic_amine_count=3,
                support=0.0,
                penalty=0.0,
                pose_support=0.8,
                atom_le_2p8=1.0,
                cationic_2p8_4p2=1.0,
            ),
            _row(
                ligand_id="decoy_supported",
                base_score=-5.8,
                shadow_score=-5.8,
                basic_amine_count=1,
                support=0.1,
                penalty=0.0,
                pose_support=0.9,
                atom_le_2p8=0.7,
                cationic_2p8_4p2=1.0,
            ),
            _row(
                ligand_id="CHEMBL83894",
                base_score=-5.5,
                shadow_score=-5.5,
                basic_amine_count=3,
                support=0.0,
                penalty=0.0,
                pose_support=0.4,
                atom_le_2p8=1.0,
                cationic_2p8_4p2=1.0,
            ),
            _row(
                ligand_id="decoy_below",
                base_score=-4.0,
                shadow_score=-4.0,
                basic_amine_count=3,
                support=0.0,
                penalty=0.0,
                pose_support=0.3,
                atom_le_2p8=1.0,
                cationic_2p8_4p2=1.0,
            ),
        ],
    )

    payload, rows = mod.build_packet(
        pose_gap_json=pose_gap,
        scores_csv=scores,
        top_n_decoys=5,
        generated_at_local="2026-05-06T00:00:00+09:00",
    )

    summary = payload["summary"]
    assert summary["status"] == "blocked_htr2a_anchor_signature_nonidentifiable"
    assert summary["positive_target_rank"] == 3
    assert summary["decoys_above_positive_count"] == 2
    assert summary["base_score_locked_decoys_above_positive_count"] == 2
    assert summary["support_blind_decoys_above_positive_count"] == 1
    assert summary["pose_advantaged_decoys_above_positive_count"] == 2
    assert summary["exact_anchor_signature_decoys_above_positive_count"] == 1
    assert summary["generic_anchor_signature_decoys_above_positive_count"] == 1
    assert summary["positive_pose_support_deficit_to_gate"] == 0.09999999999999998
    assert summary["claim_promotion_allowed"] is False
    assert payload["claim_boundary"]["target_identity_feature_allowed"] is False
    assert payload["feature_contract"]["required_feature_family"] == (
        "target_portable_atom_typed_anchor_and_pose_support"
    )
    assert rows[-1]["row_role"] == "positive"
    assert rows[0]["exact_anchor_signature_matches_positive"] is True


def test_build_packet_cli_writes_outputs(tmp_path: Path) -> None:
    pose_gap = tmp_path / "pose_gap.json"
    scores = tmp_path / "scores.csv"
    out_json = tmp_path / "packet.json"
    out_csv = tmp_path / "packet.csv"
    out_md = tmp_path / "packet.md"
    _write_json(
        pose_gap,
        {
            "summary": {"score_col": "binding_score_composite_v7_residual_shadow"},
            "target_summaries": [
                {
                    "target": "CHEMBL224_HTR2A_HUMAN",
                    "ligand_id": "CHEMBL83894",
                    "blockers": ["positive_anchor_support_missing"],
                }
            ],
        },
    )
    _write_csv(
        scores,
        [
            _row(
                ligand_id="decoy_collision",
                base_score=-6.0,
                shadow_score=-6.0,
                basic_amine_count=3,
                support=0.0,
                penalty=0.0,
                pose_support=0.8,
                atom_le_2p8=1.0,
                cationic_2p8_4p2=1.0,
            ),
            _row(
                ligand_id="CHEMBL83894",
                base_score=-5.5,
                shadow_score=-5.5,
                basic_amine_count=3,
                support=0.0,
                penalty=0.0,
                pose_support=0.4,
                atom_le_2p8=1.0,
                cationic_2p8_4p2=1.0,
            ),
        ],
    )

    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools/build_gpcr_htr2a_anchor_support_repair_packet.py"),
            "--pose-gap-json",
            str(pose_gap),
            "--scores-csv",
            str(scores),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ],
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=True,
    )

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert result.returncode == 0
    assert payload["summary"]["next_action"] == "build_htr2a_atom_typed_anchor_probe"
    assert "GPCR HTR2A Anchor-Support Repair Packet" in out_md.read_text(encoding="utf-8")
    assert "exact_anchor_signature_matches_positive" in out_csv.read_text(encoding="utf-8")

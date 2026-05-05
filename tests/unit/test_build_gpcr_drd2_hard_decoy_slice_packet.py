from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path

from tools import build_gpcr_drd2_hard_decoy_slice_packet as mod

ROOT = Path(__file__).resolve().parents[2]


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        fieldnames: list[str] = []
        for row in rows:
            for key in row:
                if key not in fieldnames:
                    fieldnames.append(key)
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def test_build_packet_classifies_repaired_drd2_hard_decoy_slices(tmp_path: Path) -> None:
    repair_rows = tmp_path / "repair_rows.csv"
    atom_cache = tmp_path / "atom_cache.csv"
    cationic_cache = tmp_path / "cationic_cache.csv"
    _write_csv(
        repair_rows,
        [
            {
                "target": "CHEMBL217_DRD2_HUMAN",
                "ligand_id": "hydrophobic_decoy",
                "is_positive": "False",
                "score": "-12.0",
                "within_target_rank": "1",
                "ligand_smiles": "CCCCCCc1ccccc1",
                "ligand_h_donors": "0",
                "ligand_h_acceptors": "1",
                "ligand_rot_bonds": "5",
                "ligand_logp": "4.0",
                "allatom_basic_amine_atom_count": "0",
                "repaired_ligand_frame_atom_count": "18",
                "allatom_backmapping_coverage_ratio": "1.0",
            },
            {
                "target": "CHEMBL217_DRD2_HUMAN",
                "ligand_id": "multipolar_decoy",
                "is_positive": "False",
                "score": "-10.0",
                "within_target_rank": "2",
                "ligand_smiles": "NCCN(CCO)CCO",
                "ligand_h_donors": "3",
                "ligand_h_acceptors": "6",
                "ligand_rot_bonds": "8",
                "ligand_logp": "0.5",
                "allatom_basic_amine_atom_count": "1",
                "repaired_ligand_frame_atom_count": "12",
                "allatom_backmapping_coverage_ratio": "1.0",
            },
            {
                "target": "CHEMBL217_DRD2_HUMAN",
                "ligand_id": "valid_anchor_decoy",
                "is_positive": "False",
                "score": "-8.0",
                "within_target_rank": "3",
                "ligand_smiles": "CNCCc1ccccc1",
                "ligand_h_donors": "1",
                "ligand_h_acceptors": "2",
                "ligand_rot_bonds": "4",
                "ligand_logp": "2.0",
                "allatom_basic_amine_atom_count": "1",
                "repaired_ligand_frame_atom_count": "11",
                "allatom_backmapping_coverage_ratio": "1.0",
            },
            {
                "target": "CHEMBL217_DRD2_HUMAN",
                "ligand_id": "pose_distorted_decoy",
                "is_positive": "False",
                "score": "-7.0",
                "within_target_rank": "4",
                "ligand_smiles": "CNCCc1ccccc1",
                "ligand_h_donors": "1",
                "ligand_h_acceptors": "2",
                "ligand_rot_bonds": "4",
                "ligand_logp": "2.0",
                "allatom_basic_amine_atom_count": "1",
                "repaired_ligand_frame_atom_count": "11",
                "allatom_backmapping_coverage_ratio": "1.0",
                "coarse_centroid_preservation_rmsd_A_mean": "3.0",
            },
            {
                "target": "CHEMBL217_DRD2_HUMAN",
                "ligand_id": "CHEMBL301265",
                "is_positive": "True",
                "score": "-1.0",
                "within_target_rank": "4",
                "ligand_smiles": "CCCN[C@H]1CCc2nc(N)sc2C1",
                "ligand_h_donors": "2",
                "ligand_h_acceptors": "4",
                "ligand_rot_bonds": "3",
                "ligand_logp": "1.5",
                "allatom_basic_amine_atom_count": "2",
                "repaired_ligand_frame_atom_count": "14",
                "allatom_backmapping_coverage_ratio": "1.0",
            },
        ],
    )
    _write_csv(
        atom_cache,
        [
            {
                "target": "CHEMBL217_DRD2_HUMAN",
                "ligand_id": "hydrophobic_decoy",
                "class_a_atom_anchor_available": "1",
                "class_a_atom_anchor_mean_distance_A": "1.2",
                "class_a_atom_anchor_contact_fraction_le_2p8A": "1.0",
                "class_a_atom_anchor_contact_fraction_2p8_4p2A": "0.0",
            },
            {
                "target": "CHEMBL217_DRD2_HUMAN",
                "ligand_id": "multipolar_decoy",
                "class_a_atom_anchor_available": "1",
                "class_a_atom_anchor_mean_distance_A": "3.0",
                "class_a_atom_anchor_contact_fraction_le_2p8A": "0.4",
                "class_a_atom_anchor_contact_fraction_2p8_4p2A": "0.7",
            },
            {
                "target": "CHEMBL217_DRD2_HUMAN",
                "ligand_id": "valid_anchor_decoy",
                "class_a_atom_anchor_available": "1",
                "class_a_atom_anchor_mean_distance_A": "3.2",
                "class_a_atom_anchor_contact_fraction_le_2p8A": "0.1",
                "class_a_atom_anchor_contact_fraction_2p8_4p2A": "0.8",
            },
            {
                "target": "CHEMBL217_DRD2_HUMAN",
                "ligand_id": "CHEMBL301265",
                "class_a_atom_anchor_available": "1",
                "class_a_atom_anchor_mean_distance_A": "2.82",
                "class_a_atom_anchor_contact_fraction_le_2p8A": "0.19",
                "class_a_atom_anchor_contact_fraction_2p8_4p2A": "0.81",
            },
            {
                "target": "CHEMBL217_DRD2_HUMAN",
                "ligand_id": "pose_distorted_decoy",
                "class_a_atom_anchor_available": "1",
                "class_a_atom_anchor_mean_distance_A": "3.2",
                "class_a_atom_anchor_contact_fraction_le_2p8A": "0.1",
                "class_a_atom_anchor_contact_fraction_2p8_4p2A": "0.8",
            },
        ],
    )
    _write_csv(
        cationic_cache,
        [
            {
                "target": "CHEMBL217_DRD2_HUMAN",
                "ligand_id": "hydrophobic_decoy",
                "class_a_cationic_center_available": "0",
                "class_a_cationic_center_contact_fraction_le_2p8A": "",
                "class_a_cationic_center_contact_fraction_2p8_4p2A": "",
            },
            {
                "target": "CHEMBL217_DRD2_HUMAN",
                "ligand_id": "multipolar_decoy",
                "class_a_cationic_center_available": "1",
                "class_a_cationic_center_contact_fraction_le_2p8A": "0.0",
                "class_a_cationic_center_contact_fraction_2p8_4p2A": "0.7",
            },
            {
                "target": "CHEMBL217_DRD2_HUMAN",
                "ligand_id": "valid_anchor_decoy",
                "class_a_cationic_center_available": "1",
                "class_a_cationic_center_contact_fraction_le_2p8A": "0.1",
                "class_a_cationic_center_contact_fraction_2p8_4p2A": "0.8",
            },
            {
                "target": "CHEMBL217_DRD2_HUMAN",
                "ligand_id": "CHEMBL301265",
                "class_a_cationic_center_available": "1",
                "class_a_cationic_center_contact_fraction_le_2p8A": "0.0",
                "class_a_cationic_center_contact_fraction_2p8_4p2A": "1.0",
            },
            {
                "target": "CHEMBL217_DRD2_HUMAN",
                "ligand_id": "pose_distorted_decoy",
                "class_a_cationic_center_available": "1",
                "class_a_cationic_center_contact_fraction_le_2p8A": "0.1",
                "class_a_cationic_center_contact_fraction_2p8_4p2A": "0.8",
            },
        ],
    )

    payload, rows = mod.build_packet(
        repair_rows_csv=repair_rows,
        atom_cache_csv=atom_cache,
        cationic_cache_csv=cationic_cache,
        generated_at_local="2026-05-05T00:00:00+09:00",
    )

    summary = payload["summary"]
    assert summary["status"] == "hard_decoy_slice_packet_ready"
    assert summary["claim_promotion_allowed"] is False
    assert summary["scorer_apply_allowed"] is False
    assert summary["invalid_close_overanchor_no_basic_count"] == 1
    assert summary["hydrophobic_close_overanchor_count"] == 1
    assert summary["multipolar_basic_overanchor_count"] == 1
    assert summary["atom_window_basic_cationic_mismatch_count"] == 0
    assert summary["pose_distorted_valid_anchor_count"] == 1
    assert summary["valid_anchor_challenge_count"] == 1
    assert summary["max_rank_pressure_to_clear_positive"] == 11.001
    by_ligand = {row["ligand_id"]: row for row in rows}
    assert "hydrophobic_close_overanchor" in by_ligand["hydrophobic_decoy"]["slice_labels"]
    assert "multipolar_basic_overanchor" in by_ligand["multipolar_decoy"]["slice_labels"]
    assert "valid_anchor_challenge" in by_ligand["valid_anchor_decoy"]["slice_labels"]
    assert "pose_distorted_valid_anchor" in by_ligand["pose_distorted_decoy"]["slice_labels"]
    assert "valid_anchor_challenge" not in by_ligand["pose_distorted_decoy"]["slice_labels"]
    assert by_ligand["CHEMBL301265"]["slice_labels"] == ["positive_repaired_anchor_window"]
    assert by_ligand["hydrophobic_decoy"]["rank_pressure_to_clear_positive"] == 11.001
    assert by_ligand["valid_anchor_decoy"]["label_free_support_pressure"] > 0


def test_hard_decoy_slice_cli_writes_outputs(tmp_path: Path) -> None:
    repair_rows = tmp_path / "repair_rows.csv"
    atom_cache = tmp_path / "atom_cache.csv"
    cationic_cache = tmp_path / "cationic_cache.csv"
    _write_csv(
        repair_rows,
        [
            {
                "target": "CHEMBL217_DRD2_HUMAN",
                "ligand_id": "decoy",
                "is_positive": "False",
                "score": "-2.0",
                "ligand_h_donors": "0",
                "ligand_h_acceptors": "1",
                "ligand_rot_bonds": "3",
                "ligand_logp": "3.0",
                "allatom_basic_amine_atom_count": "0",
            },
            {
                "target": "CHEMBL217_DRD2_HUMAN",
                "ligand_id": "CHEMBL301265",
                "is_positive": "True",
                "score": "-1.0",
                "ligand_h_donors": "2",
                "ligand_h_acceptors": "4",
                "ligand_rot_bonds": "3",
                "ligand_logp": "1.5",
                "allatom_basic_amine_atom_count": "2",
            },
        ],
    )
    _write_csv(
        atom_cache,
        [
            {
                "target": "CHEMBL217_DRD2_HUMAN",
                "ligand_id": "decoy",
                "class_a_atom_anchor_available": "1",
                "class_a_atom_anchor_mean_distance_A": "1.1",
                "class_a_atom_anchor_contact_fraction_le_2p8A": "1.0",
                "class_a_atom_anchor_contact_fraction_2p8_4p2A": "0.0",
            },
            {
                "target": "CHEMBL217_DRD2_HUMAN",
                "ligand_id": "CHEMBL301265",
                "class_a_atom_anchor_available": "1",
                "class_a_atom_anchor_mean_distance_A": "2.9",
                "class_a_atom_anchor_contact_fraction_le_2p8A": "0.2",
                "class_a_atom_anchor_contact_fraction_2p8_4p2A": "0.8",
            },
        ],
    )
    _write_csv(
        cationic_cache,
        [
            {
                "target": "CHEMBL217_DRD2_HUMAN",
                "ligand_id": "decoy",
                "class_a_cationic_center_available": "0",
                "class_a_cationic_center_contact_fraction_le_2p8A": "",
                "class_a_cationic_center_contact_fraction_2p8_4p2A": "",
            },
            {
                "target": "CHEMBL217_DRD2_HUMAN",
                "ligand_id": "CHEMBL301265",
                "class_a_cationic_center_available": "1",
                "class_a_cationic_center_contact_fraction_le_2p8A": "0.0",
                "class_a_cationic_center_contact_fraction_2p8_4p2A": "1.0",
            },
        ],
    )
    out_json = tmp_path / "packet.json"
    out_csv = tmp_path / "packet.csv"
    out_md = tmp_path / "packet.md"

    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools/build_gpcr_drd2_hard_decoy_slice_packet.py"),
            "--repair-rows-csv",
            str(repair_rows),
            "--atom-cache-csv",
            str(atom_cache),
            "--cationic-cache-csv",
            str(cationic_cache),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ],
        check=True,
        cwd=ROOT,
        text=True,
        capture_output=True,
    )

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert result.returncode == 0
    assert payload["summary"]["status"] == "hard_decoy_slice_packet_ready"
    assert "GPCR DRD2 Hard-Decoy Slice Packet" in out_md.read_text(encoding="utf-8")
    assert "invalid_close_overanchor_no_basic" in out_csv.read_text(encoding="utf-8")

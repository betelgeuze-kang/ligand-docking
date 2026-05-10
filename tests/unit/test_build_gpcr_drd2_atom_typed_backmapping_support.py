from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path

import numpy as np

from tools import build_gpcr_drd2_atom_typed_backmapping_support as mod

ROOT = Path(__file__).resolve().parents[2]


def test_defaults_use_pseudo_allatom_repair_artifacts() -> None:
    assert mod.DEFAULT_STAGE3_CSV == "runs/gpcr_drd2_pseudo_allatom_repair_rows_current.csv"
    assert (
        mod.DEFAULT_ATOM_CACHE_CSV
        == "runs/gpcr_atom_window_anchor_feature_cache_drd2_pseudo_allatom_repair_current.csv"
    )
    assert mod.DEFAULT_LOCAL_MINIMIZATION_JSON == "runs/gpcr_drd2_local_minimization_survival_current.json"


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _pdb_atom(
    record: str,
    serial: int,
    atom_name: str,
    residue_name: str,
    chain: str,
    residue_seq: int,
    x: float,
    y: float,
    z: float,
    element: str,
) -> str:
    return (
        f"{record:<6}{serial:5d} {atom_name:<4s} {residue_name:>3s} {chain:1s}{residue_seq:4d}    "
        f"{x:8.3f}{y:8.3f}{z:8.3f}  1.00 20.00          {element:>2s}"
    )


def test_build_support_blocks_low_coverage_and_missing_minimization(tmp_path: Path) -> None:
    pos_npz = tmp_path / "pos.npz"
    decoy_npz = tmp_path / "decoy.npz"
    np.savez(
        pos_npz,
        ligand_frames=np.asarray(
            [
                [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0]],
                [[0.0, 0.0, 0.0], [1.2, 0.0, 0.0]],
                [[0.0, 0.0, 0.0], [1.4, 0.0, 0.0]],
            ],
            dtype=np.float32,
        ),
    )
    np.savez(
        decoy_npz,
        ligand_frames=np.asarray(
            [
                [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [2.0, 0.0, 0.0]],
                [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [2.0, 0.0, 0.0]],
            ],
            dtype=np.float32,
        ),
    )
    stage3 = tmp_path / "stage3.csv"
    ranking = tmp_path / "ranking.csv"
    atom_cache = tmp_path / "atom_cache.csv"
    _write_csv(
        stage3,
        [
            {
                "target": "CHEMBL217_DRD2_HUMAN",
                "ligand_id": "CHEMBL301265",
                "ligand_smiles": "CCCCN",
                "trajectory_npz": str(pos_npz),
                "backmapped_pdb": "",
            },
            {
                "target": "CHEMBL217_DRD2_HUMAN",
                "ligand_id": "D1",
                "ligand_smiles": "CCN",
                "trajectory_npz": str(decoy_npz),
                "backmapped_pdb": "decoy.pdb",
                "local_minimization_survival_fraction": "0.8",
            },
        ],
    )
    _write_csv(
        ranking,
        [
            {
                "target": "CHEMBL217_DRD2_HUMAN",
                "ligand_id": "D1",
                "is_binder": "0",
                "binding_score_composite_v7_residual_active": "-9.0",
            },
            {
                "target": "CHEMBL217_DRD2_HUMAN",
                "ligand_id": "CHEMBL301265",
                "is_binder": "1",
                "binding_score_composite_v7_residual_active": "-1.0",
            },
        ],
    )
    _write_csv(
        atom_cache,
        [
            {
                "target": "CHEMBL217_DRD2_HUMAN",
                "ligand_id": "CHEMBL301265",
                "class_a_atom_anchor_available": "1",
                "class_a_atom_anchor_template_residue": "ASP114A",
                "class_a_atom_anchor_min_distance_A": "3.4",
                "class_a_atom_anchor_mean_distance_A": "3.8",
                "class_a_atom_anchor_contact_fraction_le_2p8A": "0.0",
                "class_a_atom_anchor_contact_fraction_2p8_4p2A": "0.7",
            }
        ],
    )

    payload = mod.build_support(
        stage3_csv=stage3,
        ranking_rows_csv=ranking,
        atom_cache_csv=atom_cache,
        local_minimization_json=tmp_path / "missing_local_min.json",
        top_decoys=1,
        generated_at_local="2026-05-06T00:00:00+09:00",
    )
    summary = payload["summary"]
    positive = next(row for row in payload["rows"] if row["is_positive"])

    assert summary["status"] == "drd2_atom_typed_backmapping_blocked"
    assert summary["hard_decoy_rebuild_allowed"] is False
    assert summary["guarded_100k_rerun_allowed"] is False
    assert positive["backmapping_atom_coverage_ratio"] == 0.4
    assert positive["backmapping_atom_count_source"] == "ligand_frame_atom_count"
    assert positive["backmapping_coordinate_source"] == "trajectory_npz"
    assert "backmapping_atom_coverage_below_min" in positive["blockers"]
    assert "full_atom_typed_backmapping_missing" in positive["blockers"]
    assert "local_minimization_survival_missing" in positive["blockers"]
    assert positive["pose_preservation_rmsd_A_p90"] is not None
    assert positive["source_metric_provenance"]["backmapping_atom_coverage_ratio"]["coordinate_source"] == "trajectory_npz"


def test_build_support_prefers_backmapped_pdb_atom_count_and_records_provenance(tmp_path: Path) -> None:
    npz = tmp_path / "traj.npz"
    np.savez(
        npz,
        ligand_frames=np.asarray(
            [
                [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0]],
                [[0.0, 0.0, 0.0], [1.1, 0.0, 0.0]],
            ],
            dtype=np.float32,
        ),
    )
    pdb = tmp_path / "backmapped.pdb"
    pdb.write_text(
        "\n".join(
            [
                _pdb_atom("ATOM", 1, "CA", "ASP", "A", 114, 0.0, 0.0, 0.0, "C"),
                _pdb_atom("HETATM", 2, "C1", "LIG", "L", 1, 1.0, 0.0, 0.0, "C"),
                _pdb_atom("HETATM", 3, "C2", "LIG", "L", 1, 2.0, 0.0, 0.0, "C"),
                _pdb_atom("HETATM", 4, "C3", "LIG", "L", 1, 3.0, 0.0, 0.0, "C"),
                _pdb_atom("HETATM", 5, "C4", "LIG", "L", 1, 4.0, 0.0, 0.0, "C"),
                _pdb_atom("HETATM", 6, "N1", "LIG", "L", 1, 5.0, 0.0, 0.0, "N"),
                _pdb_atom("HETATM", 7, "H1", "LIG", "L", 1, 6.0, 0.0, 0.0, "H"),
                _pdb_atom("HETATM", 8, "O", "HOH", "A", 900, 9.0, 0.0, 0.0, "O"),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    stage3 = tmp_path / "stage3.csv"
    ranking = tmp_path / "ranking.csv"
    atom_cache = tmp_path / "atom_cache.csv"
    _write_csv(
        stage3,
        [
            {
                "target": "CHEMBL217_DRD2_HUMAN",
                "ligand_id": "CHEMBL301265",
                "ligand_smiles": "CCCCN",
                "trajectory_npz": str(npz),
                "backmapped_pdb": str(pdb),
                "source_three_bead_local_minimization_survival_fraction": "0.8",
            }
        ],
    )
    _write_csv(
        ranking,
        [
            {
                "target": "CHEMBL217_DRD2_HUMAN",
                "ligand_id": "CHEMBL301265",
                "is_binder": "1",
                "binding_score_composite_v7_residual_active": "-1.0",
            }
        ],
    )
    _write_csv(atom_cache, [{"target": "CHEMBL217_DRD2_HUMAN", "ligand_id": "CHEMBL301265"}])

    payload = mod.build_support(
        stage3_csv=stage3,
        ranking_rows_csv=ranking,
        atom_cache_csv=atom_cache,
        local_minimization_json=tmp_path / "missing_local_min.json",
        generated_at_local="2026-05-06T00:00:00+09:00",
    )
    summary = payload["summary"]
    positive = payload["rows"][0]

    assert summary["status"] == "drd2_atom_typed_backmapping_ready"
    assert summary["hard_decoy_rebuild_allowed"] is True
    assert positive["ligand_frame_atom_count"] == 2
    assert positive["backmapped_pdb_ligand_atom_count"] == 6
    assert positive["backmapped_pdb_ligand_heavy_atom_count"] == 5
    assert positive["backmapping_atom_coverage_ratio"] == 1.0
    assert positive["backmapping_atom_count_source"] == "backmapped_pdb_ligand_heavy_atom_count"
    assert positive["backmapping_coordinate_source"] == "backmapped_pdb"
    assert positive["local_minimization_survival_source_column"] == (
        "source_three_bead_local_minimization_survival_fraction"
    )
    assert positive["source_metric_provenance"]["local_minimization_survival_fraction"]["threshold_min"] == 0.55
    assert summary["positive_backmapping_atom_count_source"] == "backmapped_pdb_ligand_heavy_atom_count"
    assert summary["positive_source_metric_provenance"]["backmapping_atom_coverage_ratio"]["atom_count"] == 5


def test_build_support_blocks_low_local_minimization_survival(tmp_path: Path) -> None:
    npz = tmp_path / "traj.npz"
    np.savez(npz, ligand_frames=np.asarray([[[0.0, 0.0, 0.0]]], dtype=np.float32))
    pdb = tmp_path / "backmapped.pdb"
    pdb.write_text(
        _pdb_atom("HETATM", 1, "C1", "LIG", "L", 1, 0.0, 0.0, 0.0, "C") + "\n",
        encoding="utf-8",
    )
    stage3 = tmp_path / "stage3.csv"
    ranking = tmp_path / "ranking.csv"
    atom_cache = tmp_path / "atom_cache.csv"
    _write_csv(
        stage3,
        [
            {
                "target": "CHEMBL217_DRD2_HUMAN",
                "ligand_id": "CHEMBL301265",
                "ligand_smiles": "C",
                "trajectory_npz": str(npz),
                "backmapped_pdb": str(pdb),
                "local_minimization_survival_fraction": "0.2",
            }
        ],
    )
    _write_csv(
        ranking,
        [
            {
                "target": "CHEMBL217_DRD2_HUMAN",
                "ligand_id": "CHEMBL301265",
                "is_binder": "1",
                "binding_score_composite_v7_residual_active": "-1.0",
            }
        ],
    )
    _write_csv(atom_cache, [{"target": "CHEMBL217_DRD2_HUMAN", "ligand_id": "CHEMBL301265"}])

    payload = mod.build_support(
        stage3_csv=stage3,
        ranking_rows_csv=ranking,
        atom_cache_csv=atom_cache,
        local_minimization_json=tmp_path / "missing_local_min.json",
        generated_at_local="2026-05-06T00:00:00+09:00",
    )
    positive = payload["rows"][0]

    assert payload["summary"]["status"] == "drd2_atom_typed_backmapping_blocked"
    assert payload["summary"]["hard_decoy_rebuild_allowed"] is False
    assert positive["local_minimization_survival_gate_pass"] is False
    assert "local_minimization_survival_below_min" in positive["blockers"]


def test_build_support_records_bounded_local_minimization_but_keeps_gate_closed(tmp_path: Path) -> None:
    npz = tmp_path / "traj.npz"
    np.savez(npz, ligand_frames=np.asarray([[[0.0, 0.0, 0.0]]], dtype=np.float32))
    pdb = tmp_path / "backmapped.pdb"
    pdb.write_text(
        _pdb_atom("HETATM", 1, "C1", "LIG", "L", 1, 0.0, 0.0, 0.0, "C") + "\n",
        encoding="utf-8",
    )
    stage3 = tmp_path / "stage3.csv"
    ranking = tmp_path / "ranking.csv"
    atom_cache = tmp_path / "atom_cache.csv"
    local_min = tmp_path / "local_min.json"
    _write_csv(
        stage3,
        [
            {
                "target": "CHEMBL217_DRD2_HUMAN",
                "ligand_id": "CHEMBL301265",
                "ligand_smiles": "C",
                "trajectory_npz": str(npz),
                "backmapped_pdb": str(pdb),
            }
        ],
    )
    _write_csv(
        ranking,
        [
            {
                "target": "CHEMBL217_DRD2_HUMAN",
                "ligand_id": "CHEMBL301265",
                "is_binder": "1",
                "binding_score_composite_v7_residual_active": "-1.0",
            }
        ],
    )
    _write_csv(atom_cache, [{"target": "CHEMBL217_DRD2_HUMAN", "ligand_id": "CHEMBL301265"}])
    local_min.write_text(
        json.dumps(
            {
                "summary": {"hard_decoy_rebuild_evidence_allowed": False},
                "rows": [
                    {
                        "target": "CHEMBL217_DRD2_HUMAN",
                        "ligand_id": "CHEMBL301265",
                        "survival_fraction": 1.0,
                        "engine_kind": "openmm_custom_protein_ligand_bounded",
                        "survival_claim_scope": "bounded_custom_protein_ligand_not_full_forcefield",
                        "blockers": ["custom_force_minimizer_not_equivalent_to_full_protein_ligand_forcefield"],
                    }
                ],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    payload = mod.build_support(
        stage3_csv=stage3,
        ranking_rows_csv=ranking,
        atom_cache_csv=atom_cache,
        local_minimization_json=local_min,
        generated_at_local="2026-05-06T00:00:00+09:00",
    )
    positive = payload["rows"][0]

    assert payload["summary"]["status"] == "drd2_atom_typed_backmapping_blocked"
    assert positive["local_minimization_survival_fraction"] == 1.0
    assert positive["local_minimization_survival_engine_kind"] == "openmm_custom_protein_ligand_bounded"
    assert positive["local_minimization_survival_gate_pass"] is False
    assert "local_minimization_survival_not_claim_grade" in positive["blockers"]
    assert payload["summary"]["hard_decoy_rebuild_allowed"] is False


def test_cli_writes_support_artifacts(tmp_path: Path) -> None:
    npz = tmp_path / "traj.npz"
    np.savez(npz, ligand_frames=np.asarray([[[0.0, 0.0, 0.0]]], dtype=np.float32))
    stage3 = tmp_path / "stage3.csv"
    ranking = tmp_path / "ranking.csv"
    atom_cache = tmp_path / "atom_cache.csv"
    out_json = tmp_path / "support.json"
    out_csv = tmp_path / "support.csv"
    out_md = tmp_path / "support.md"
    _write_csv(
        stage3,
        [
            {
                "target": "CHEMBL217_DRD2_HUMAN",
                "ligand_id": "CHEMBL301265",
                "ligand_smiles": "C",
                "trajectory_npz": str(npz),
            }
        ],
    )
    _write_csv(
        ranking,
        [
            {
                "target": "CHEMBL217_DRD2_HUMAN",
                "ligand_id": "CHEMBL301265",
                "is_binder": "1",
                "binding_score_composite_v7_residual_active": "-1.0",
            }
        ],
    )
    _write_csv(atom_cache, [{"target": "CHEMBL217_DRD2_HUMAN", "ligand_id": "CHEMBL301265"}])

    subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools/build_gpcr_drd2_atom_typed_backmapping_support.py"),
            "--stage3-csv",
            str(stage3),
            "--ranking-rows-csv",
            str(ranking),
            "--atom-cache-csv",
            str(atom_cache),
            "--local-minimization-json",
            str(tmp_path / "missing_local_min.json"),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ],
        check=True,
        cwd=ROOT,
    )
    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["packet_type"] == "gpcr_drd2_atom_typed_backmapping_support"
    assert out_csv.exists()
    assert "GPCR DRD2 Atom-Typed Backmapping Support" in out_md.read_text(encoding="utf-8")

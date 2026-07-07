from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from tools.product.strict_ligand_mapping_queue import run

_TINY_PDB = """ATOM      1  N   GLY A   1       0.000   0.000   0.000  1.00 20.00           N
ATOM      2  CA  GLY A   1       1.458   0.000   0.000  1.00 20.00           C
ATOM      3  C   GLY A   1       2.028   1.410   0.000  1.00 20.00           C
END
"""


def _write_csv(path: Path, rows: list[dict[str, object]]) -> Path:
    pd.DataFrame(rows).to_csv(path, index=False)
    return path


def _bool_texts(series: pd.Series) -> set[str]:
    return {str(value).strip().lower() for value in series.tolist()}


def test_strict_ligand_mapping_queue_passes_with_explicit_geometry_and_pocket(tmp_path: Path) -> None:
    repo = Path(__file__).resolve().parents[2]
    ligand_csv = repo / "tests" / "fixtures" / "tiny_docking" / "ligands_explicit_beads.csv"
    native_pdb = tmp_path / "native.pdb"
    native_pdb.write_text("END\n", encoding="utf-8")
    native_csv = _write_csv(
        tmp_path / "targets.csv",
        [{"target": "TINY_KINASE", "native_pdb_path": str(native_pdb)}],
    )
    pocket_csv = _write_csv(
        tmp_path / "pockets.csv",
        [{"target": "TINY_KINASE", "pocket_x": 1.0, "pocket_y": 2.0, "pocket_z": 3.0}],
    )
    out_queue = tmp_path / "queue.csv"
    out_ligands = tmp_path / "ligands.json"
    out_summary = tmp_path / "summary.json"

    run(
        [
            "--targets",
            "TINY_KINASE",
            "--ligand-csv",
            str(ligand_csv),
            "--max-ligands",
            "2",
            "--replicas",
            "2",
            "--jobs-per-target",
            "2",
            "--target-native-csv",
            str(native_csv),
            "--target-pocket-csv",
            str(pocket_csv),
            "--require-native-path",
            "--production-strict-inputs",
            "--out-queue-csv",
            str(out_queue),
            "--out-ligand-json",
            str(out_ligands),
            "--out-summary-json",
            str(out_summary),
            "--out-summary-md",
            str(tmp_path / "summary.md"),
        ]
    )

    queue = pd.read_csv(out_queue)
    assert set(
        [
            "production_strict_inputs",
            "ligand_geometry_source",
            "ligand_conformer_status",
            "fallback_beads_used",
            "pocket_source",
            "native_structure_source",
            "science_input_risk_level",
            "science_input_blockers_json",
        ]
    ).issubset(queue.columns)
    assert _bool_texts(queue["production_strict_inputs"]) == {"true"}
    assert _bool_texts(queue["fallback_beads_used"]) == {"false"}
    assert set(queue["ligand_geometry_source"]) == {"explicit_bead_coords_json"}
    assert set(queue["pocket_source"]) == {"target_pocket_csv"}
    assert set(queue["native_structure_source"]) == {"target_native_csv"}
    summary = json.loads(out_summary.read_text(encoding="utf-8"))
    assert summary["production_input_provenance"]["pass"] is True
    report_path = Path(summary["artifacts"]["production_input_provenance_json"])
    assert report_path.exists()


def test_strict_ligand_mapping_queue_blocks_non_explicit_pocket(tmp_path: Path) -> None:
    ligand_csv = _write_csv(
        tmp_path / "ligands.csv",
        [{"ligand_id": "LIG_A", "smiles": "C", "is_binder": 1}],
    )
    native_pdb = tmp_path / "native.pdb"
    native_pdb.write_text(_TINY_PDB, encoding="utf-8")
    native_csv = _write_csv(
        tmp_path / "targets.csv",
        [{"target": "TINY_KINASE", "native_pdb_path": str(native_pdb)}],
    )
    out_summary = tmp_path / "summary.json"

    with pytest.raises(SystemExit) as exc:
        run(
            [
                "--targets",
                "TINY_KINASE",
                "--ligand-csv",
                str(ligand_csv),
                "--max-ligands",
                "1",
                "--replicas",
                "1",
                "--jobs-per-target",
                "1",
                "--target-native-csv",
                str(native_csv),
                "--require-native-path",
                "--production-strict-inputs",
                "--out-queue-csv",
                str(tmp_path / "queue.csv"),
                "--out-ligand-json",
                str(tmp_path / "ligands.json"),
                "--out-summary-json",
                str(out_summary),
                "--out-summary-md",
                str(tmp_path / "summary.md"),
            ]
        )

    assert "production_strict_inputs_failed" in str(exc.value)
    summary = json.loads(out_summary.read_text(encoding="utf-8"))
    assert summary["production_input_provenance"]["pass"] is False
    assert "pocket_source_not_explicit" in summary["production_input_provenance"]["unique_blockers"]

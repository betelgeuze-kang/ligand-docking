from __future__ import annotations

import csv
import json
from pathlib import Path

from betelgeuze_product.structure_report import build_product_structure_analysis_report
from tools import build_product_structure_analysis_report as tool


PDB_TEXT = """\
ATOM      1  N   GLY A   1      11.104  13.207  14.321  1.00 10.00           N
ATOM      2  CA  GLY A   1      12.104  13.207  14.321  1.00 10.00           C
HETATM    3  C1  LIG B 201      18.104  19.207  20.321  1.00 10.00           C
"""


def _target_csv(tmp_path: Path, structure_path: str) -> Path:
    csv_path = tmp_path / "targets.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["target", "native_pdb_path", "pdb_id", "pocket_x", "pocket_y", "pocket_z"])
        writer.writeheader()
        writer.writerow(
            {
                "target": "ADRB2_GPCR_BLIND",
                "native_pdb_path": structure_path,
                "pdb_id": "2RH1",
                "pocket_x": "1.0",
                "pocket_y": "2.0",
                "pocket_z": "3.0",
            }
        )
    return csv_path


def test_product_structure_analysis_report_reads_local_target_structure(tmp_path: Path) -> None:
    pdb_path = tmp_path / "adrb2.pdb"
    pdb_path.write_text(PDB_TEXT, encoding="utf-8")
    target_csv = _target_csv(tmp_path, str(pdb_path))

    payload = build_product_structure_analysis_report(
        target_native_csv=str(target_csv),
        target_key="ADRB2_GPCR_BLIND",
        target_id="ADRB2",
        family="gpcr",
        root=tmp_path,
    )

    summary = payload["summary"]
    assert summary["status"] == "product_structure_analysis_report_ready"
    assert summary["local_structure_parsed"] is True
    assert summary["atom_count"] == 3
    assert summary["ligand_like_residue_count"] == 1
    assert summary["execution_enabled"] is False
    assert summary["docking_results_emitted"] is False
    assert summary["external_state_mutated"] is False
    assert payload["blockers"] == []


def test_product_structure_analysis_report_blocks_missing_target_key(tmp_path: Path) -> None:
    target_csv = _target_csv(tmp_path, "missing.pdb")

    payload = build_product_structure_analysis_report(
        target_native_csv=str(target_csv),
        target_key="NOT_PRESENT",
        root=tmp_path,
    )

    assert payload["summary"]["status"] == "blocked_product_structure_analysis_report"
    assert any(blocker["code"] == "target_key_not_found" for blocker in payload["blockers"])


def test_product_structure_analysis_report_tool_writes_outputs(tmp_path: Path) -> None:
    pdb_path = tmp_path / "adrb2.pdb"
    pdb_path.write_text(PDB_TEXT, encoding="utf-8")
    target_csv = _target_csv(tmp_path, str(pdb_path))
    out_json = tmp_path / "report.json"
    out_csv = tmp_path / "report.csv"
    out_md = tmp_path / "report.md"

    tool.main(
        [
            "--target-native-csv",
            str(target_csv),
            "--target-key",
            "ADRB2_GPCR_BLIND",
            "--target-id",
            "ADRB2",
            "--family",
            "gpcr",
            "--root",
            str(tmp_path),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ]
    )

    assert json.loads(out_json.read_text(encoding="utf-8"))["summary"]["status"] == "product_structure_analysis_report_ready"
    assert out_csv.read_text(encoding="utf-8").startswith("check,status,")
    assert "Product Structure Analysis Report" in out_md.read_text(encoding="utf-8")

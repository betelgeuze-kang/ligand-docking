from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def test_build_ca2_binding_verification_sheet(tmp_path: Path) -> None:
    queue_csv = tmp_path / "runs" / "ca2_packet_replacement_verification_queue_current.csv"
    workbook_csv = tmp_path / "runs" / "ca2_packet_replacement_workbook_current.csv"
    _write_csv(
        queue_csv,
        [
            "priority_rank",
            "packet",
            "packet_step",
            "replacement_ligand_id",
            "replacement_is_binder",
            "replacement_source",
        ],
        [
            {
                "priority_rank": "1",
                "packet": "core",
                "packet_step": "core_binder_01",
                "replacement_ligand_id": "acetazolamide",
                "replacement_is_binder": "1",
                "replacement_source": "pubchem_name_resolve_pending::known_ca2_inhibitor_seed",
            }
        ],
    )
    _write_csv(
        workbook_csv,
        [
            "packet_step",
            "replacement_smiles",
            "replacement_scaffold",
            "replacement_pubchem_cid",
            "replacement_structure_resolution_url",
        ],
        [
            {
                "packet_step": "core_binder_01",
                "replacement_smiles": "CC(=O)NC1=NN=C(S1)S(=O)(=O)N",
                "replacement_scaffold": "c1nncs1",
                "replacement_pubchem_cid": "1986",
                "replacement_structure_resolution_url": "https://example.test/acetazolamide",
            }
        ],
    )
    out_json = tmp_path / "runs" / "sheet.json"
    out_csv = tmp_path / "runs" / "sheet.csv"
    out_md = tmp_path / "runs" / "sheet.md"
    subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools/build_packet_binding_verification_sheet.py"),
            "--family",
            "ca2",
            "--queue-csv",
            str(queue_csv),
            "--workbook-csv",
            str(workbook_csv),
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
    row = payload["sheet_rows"][0]
    assert row["replacement_ligand_id"] == "acetazolamide"
    assert row["replacement_pubchem_cid"] == "1986"
    assert row["verify_reference_binding_kcal_mol"] == ""
    assert payload["summary"]["binder_row_count"] == 1


def test_build_binding_verification_sheet_preserves_existing_verify_fields(tmp_path: Path) -> None:
    queue_csv = tmp_path / "runs" / "ca2_packet_replacement_verification_queue_current.csv"
    workbook_csv = tmp_path / "runs" / "ca2_packet_replacement_workbook_current.csv"
    out_json = tmp_path / "runs" / "sheet.json"
    out_csv = tmp_path / "runs" / "sheet.csv"
    out_md = tmp_path / "runs" / "sheet.md"
    _write_csv(
        queue_csv,
        [
            "priority_rank",
            "packet",
            "packet_step",
            "replacement_ligand_id",
            "replacement_is_binder",
            "replacement_source",
        ],
        [
            {
                "priority_rank": "1",
                "packet": "core",
                "packet_step": "core_binder_01",
                "replacement_ligand_id": "acetazolamide",
                "replacement_is_binder": "1",
                "replacement_source": "pubchem_name_resolve_pending::known_ca2_inhibitor_seed",
            }
        ],
    )
    _write_csv(
        workbook_csv,
        [
            "packet_step",
            "replacement_smiles",
            "replacement_scaffold",
            "replacement_pubchem_cid",
            "replacement_structure_resolution_url",
        ],
        [
            {
                "packet_step": "core_binder_01",
                "replacement_smiles": "CC(=O)NC1=NN=C(S1)S(=O)(=O)N",
                "replacement_scaffold": "c1nncs1",
                "replacement_pubchem_cid": "1986",
                "replacement_structure_resolution_url": "https://example.test/acetazolamide",
            }
        ],
    )
    _write_csv(
        out_csv,
        [
            "priority_rank",
            "packet",
            "packet_step",
            "replacement_ligand_id",
            "replacement_is_binder",
            "replacement_source",
            "replacement_smiles",
            "replacement_scaffold",
            "replacement_pubchem_cid",
            "replacement_structure_resolution_url",
            "verify_reference_binding_kcal_mol",
            "verify_provenance_source",
            "verify_source_url",
            "verification_status",
            "notes",
        ],
        [
            {
                "priority_rank": "1",
                "packet": "core",
                "packet_step": "core_binder_01",
                "replacement_ligand_id": "acetazolamide",
                "replacement_is_binder": "1",
                "replacement_source": "pubchem_name_resolve_pending::known_ca2_inhibitor_seed",
                "replacement_smiles": "CC(=O)NC1=NN=C(S1)S(=O)(=O)N",
                "replacement_scaffold": "c1nncs1",
                "replacement_pubchem_cid": "1986",
                "replacement_structure_resolution_url": "https://example.test/acetazolamide",
                "verify_reference_binding_kcal_mol": "-10.8060",
                "verify_provenance_source": "chembl_direct_binding::CHEMBL205::CHEMBL20::activity_47560",
                "verify_source_url": "https://www.ebi.ac.uk/chembl/document_report_card/CHEMBL1146805/",
                "verification_status": "verified_chembl_activity_pending_workbook_copy",
                "notes": "Keep existing verification evidence.",
            }
        ],
    )
    subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools/build_packet_binding_verification_sheet.py"),
            "--family",
            "ca2",
            "--queue-csv",
            str(queue_csv),
            "--workbook-csv",
            str(workbook_csv),
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
    row = payload["sheet_rows"][0]
    assert row["verify_reference_binding_kcal_mol"] == "-10.8060"
    assert row["verify_provenance_source"] == "chembl_direct_binding::CHEMBL205::CHEMBL20::activity_47560"
    assert row["verify_source_url"] == "https://www.ebi.ac.uk/chembl/document_report_card/CHEMBL1146805/"
    assert row["verification_status"] == "verified_chembl_activity_pending_workbook_copy"
    assert row["notes"] == "Keep existing verification evidence."

from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def test_promote_verified_binding_rows_to_workbook(tmp_path: Path) -> None:
    workbook_csv = tmp_path / "workbook.csv"
    sheet_csv = tmp_path / "sheet.csv"
    out_json = tmp_path / "promotion.json"
    out_csv = tmp_path / "promotion.csv"
    out_md = tmp_path / "promotion.md"
    _write_csv(
        workbook_csv,
        [
            {
                "packet": "core",
                "packet_step": "core_binder_01",
                "target": "CARBONIC_ANHYDRASE_2_ZN_BLIND",
                "current_ligand_id": "placeholder",
                "replacement_ligand_id": "acetazolamide",
                "replacement_reference_binding_kcal_mol": "",
                "replacement_is_binder": "1",
                "replacement_source": "pubchem_name_resolve_pending::known_ca2_inhibitor_seed",
                "replacement_role": "far_ood_eval",
                "replacement_smiles": "CC",
                "replacement_molecular_weight": "222.2",
                "replacement_logp": "-0.85",
                "replacement_h_donors": "2",
                "replacement_h_acceptors": "6",
                "replacement_rot_bonds": "2",
                "replacement_scaffold": "c1nncs1",
                "apply_reference_row": "yes",
                "apply_split_row": "yes",
                "apply_meta_row": "yes",
                "row_ready_for_apply": "no",
                "required_missing_fields": "replacement_reference_binding_kcal_mol",
                "notes": "pending",
                "resolved_query_name": "acetazolamide",
                "replacement_pubchem_cid": "1986",
                "replacement_structure_resolution_status": "pubchem_name_resolved",
                "replacement_structure_resolution_url": "https://example.test/1",
            }
        ],
    )
    _write_csv(
        sheet_csv,
        [
            {
                "priority_rank": "1",
                "packet": "core",
                "packet_step": "core_binder_01",
                "replacement_ligand_id": "acetazolamide",
                "replacement_is_binder": "1",
                "replacement_source": "pubchem_name_resolve_pending::known_ca2_inhibitor_seed",
                "replacement_smiles": "CC",
                "replacement_scaffold": "c1nncs1",
                "replacement_pubchem_cid": "1986",
                "replacement_structure_resolution_url": "https://example.test/1",
                "verify_reference_binding_kcal_mol": "-10.8060",
                "verify_provenance_source": "chembl_direct_binding::CHEMBL205::CHEMBL20::activity_47560",
                "verify_source_url": "https://www.ebi.ac.uk/chembl/document_report_card/CHEMBL1146805/",
                "verification_status": "verified_chembl_activity_pending_workbook_copy",
                "notes": "verified",
            }
        ],
    )
    subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools/promote_verified_binding_rows_to_workbook.py"),
            "--family",
            "ca2",
            "--workbook-csv",
            str(workbook_csv),
            "--sheet-csv",
            str(sheet_csv),
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
    promoted = json.loads(out_json.read_text(encoding="utf-8"))
    assert promoted["summary"]["promoted_row_count"] == 1
    saved_rows = list(csv.DictReader(workbook_csv.open("r", encoding="utf-8", newline="")))
    row = saved_rows[0]
    assert row["replacement_reference_binding_kcal_mol"] == "-10.8060"
    assert row["replacement_source"] == "chembl_direct_binding::CHEMBL205::CHEMBL20::activity_47560"
    assert row["row_ready_for_apply"] == "yes"

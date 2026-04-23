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


def test_apply_binding_verification_updates(tmp_path: Path) -> None:
    sheet_csv = tmp_path / "sheet.csv"
    sheet_json = tmp_path / "sheet.json"
    sheet_md = tmp_path / "sheet.md"
    updates_json = tmp_path / "updates.json"
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
                "replacement_smiles": "X",
                "replacement_scaffold": "Y",
                "replacement_pubchem_cid": "1986",
                "replacement_structure_resolution_url": "https://example.test/1",
                "verify_reference_binding_kcal_mol": "",
                "verify_provenance_source": "",
                "verify_source_url": "",
                "verification_status": "pending_binding_provenance_review",
                "notes": "Start with binder evidence and quantitative affinity.",
            }
        ],
    )
    updates_payload = {
        "summary": {"family": "ca2"},
        "rows": [
            {
                "packet_step": "core_binder_01",
                "verify_reference_binding_kcal_mol": "-10.8060",
                "verify_provenance_source": "chembl_activity::CHEMBL205::CHEMBL20::activity=47560",
                "verify_source_url": "https://www.ebi.ac.uk/chembl/api/data/activity/47560.json",
                "verification_status": "verified_chembl_activity_pending_workbook_copy",
                "evidence_note": "Human carbonic anhydrase II Ki 12.0 nM.",
            }
        ],
    }
    updates_json.write_text(json.dumps(updates_payload, indent=2), encoding="utf-8")
    subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools/apply_binding_verification_updates.py"),
            "--family",
            "ca2",
            "--sheet-csv",
            str(sheet_csv),
            "--sheet-json",
            str(sheet_json),
            "--sheet-md",
            str(sheet_md),
            "--updates-json",
            str(updates_json),
        ],
        check=True,
        cwd=ROOT,
    )
    saved = json.loads(sheet_json.read_text(encoding="utf-8"))
    row = saved["sheet_rows"][0]
    assert row["verify_reference_binding_kcal_mol"] == "-10.8060"
    assert row["verification_status"] == "verified_chembl_activity_pending_workbook_copy"
    assert "Ki 12.0 nM" in row["notes"]

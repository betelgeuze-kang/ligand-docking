from __future__ import annotations

import csv
import json
from pathlib import Path

from tools.apply_verified_binding_sources import main


def test_apply_verified_binding_sources_updates_matching_rows(tmp_path: Path, monkeypatch) -> None:
    sheet_csv = tmp_path / "sheet.csv"
    with sheet_csv.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=[
                "packet_step",
                "verify_reference_binding_kcal_mol",
                "verify_provenance_source",
                "verify_source_url",
                "verification_status",
                "notes",
            ],
        )
        writer.writeheader()
        writer.writerow(
            {
                "packet_step": "core_binder_01",
                "verify_reference_binding_kcal_mol": "",
                "verify_provenance_source": "",
                "verify_source_url": "",
                "verification_status": "pending",
                "notes": "old",
            }
        )
    spec_json = tmp_path / "spec.json"
    spec_json.write_text(
        json.dumps(
            {
                "verified_rows": [
                    {
                        "packet_step": "core_binder_01",
                        "verify_reference_binding_kcal_mol": "-10.8",
                        "verify_provenance_source": "chembl_activity::demo",
                        "verify_source_url": "https://example.org/activity",
                        "verification_status": "verified_binding_provenance",
                        "notes": "updated",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "sys.argv",
        [
            "apply_verified_binding_sources.py",
            "--family",
            "ca2",
            "--sheet-csv",
            str(sheet_csv),
            "--spec-json",
            str(spec_json),
        ],
    )
    main()
    with sheet_csv.open("r", encoding="utf-8", newline="") as fh:
        row = next(csv.DictReader(fh))
    assert row["verify_reference_binding_kcal_mol"] == "-10.8"
    assert row["verify_provenance_source"] == "chembl_activity::demo"
    assert row["verify_source_url"] == "https://example.org/activity"
    assert row["verification_status"] == "verified_binding_provenance"
    assert row["notes"] == "updated"


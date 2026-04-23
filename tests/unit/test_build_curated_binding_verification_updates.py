from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_build_curated_binding_verification_updates_ca2(tmp_path: Path) -> None:
    out_json = tmp_path / "ca2_updates.json"
    out_csv = tmp_path / "ca2_updates.csv"
    out_md = tmp_path / "ca2_updates.md"
    subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools/build_curated_binding_verification_updates.py"),
            "--family",
            "ca2",
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
    assert payload["summary"]["verified_row_count"] == 6
    rows = payload["rows"]
    assert rows[0]["packet_step"] == "core_binder_01"
    assert rows[0]["verify_reference_binding_kcal_mol"] == "-10.8060"
    assert "activity_47560" in rows[0]["verify_provenance_source"]
    assert rows[0]["verify_source_url"] == "https://www.ebi.ac.uk/chembl/document_report_card/CHEMBL1146805/"
    assert rows[3]["packet_step"] == "ood_binder_01"
    assert rows[3]["verify_reference_binding_kcal_mol"] == "-10.9764"
    assert "activity_110109" in rows[3]["verify_provenance_source"]
    assert rows[4]["packet_step"] == "ood_binder_02"
    assert rows[4]["verify_reference_binding_kcal_mol"] == "-11.6273"
    assert "activity_138028" in rows[4]["verify_provenance_source"]
    assert rows[5]["packet_step"] == "ood_binder_03"
    assert rows[5]["verify_reference_binding_kcal_mol"] == "-10.8060"
    assert "CHEMBL360356" in rows[5]["verify_provenance_source"]


def test_build_curated_binding_verification_updates_pxr(tmp_path: Path) -> None:
    out_json = tmp_path / "pxr_updates.json"
    out_csv = tmp_path / "pxr_updates.csv"
    out_md = tmp_path / "pxr_updates.md"
    subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools/build_curated_binding_verification_updates.py"),
            "--family",
            "pxr",
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
    assert payload["summary"]["verified_row_count"] == 8
    rows = payload["rows"]
    assert rows[2]["packet_step"] == "core_fit_binder_01"
    assert rows[2]["verify_reference_binding_kcal_mol"] == "-10.3255"
    assert "Ki_27.0_nM" in rows[2]["verify_provenance_source"]
    assert rows[4]["packet_step"] == "ood_eval_binder_02"
    assert rows[4]["verify_reference_binding_kcal_mol"] == "-6.8903"
    assert "EC50_8900.0_nM" in rows[4]["verify_provenance_source"]
    assert rows[5]["packet_step"] == "ood_eval_binder_01"
    assert rows[5]["verify_reference_binding_kcal_mol"] == "-6.1703"
    assert "AC50_30000.0_nM" in rows[5]["verify_provenance_source"]
    assert rows[6]["packet_step"] == "ood_eval_binder_03"
    assert rows[6]["verify_reference_binding_kcal_mol"] == "-6.1703"
    assert "activity_25188566" in rows[6]["verify_provenance_source"]
    assert rows[7]["packet_step"] == "ood_fit_binder_02"
    assert rows[7]["verify_reference_binding_kcal_mol"] == "-8.6719"
    assert "EC50_440.0_nM" in rows[7]["verify_provenance_source"]

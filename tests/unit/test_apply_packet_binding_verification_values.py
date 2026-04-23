from __future__ import annotations

import csv
from pathlib import Path

from tools.apply_packet_binding_verification_values import build_payload


def test_build_payload_updates_ca2_top_binders() -> None:
    rows = [
        {
            "priority_rank": "1",
            "packet_step": "core_binder_01",
            "replacement_ligand_id": "acetazolamide",
            "verify_reference_binding_kcal_mol": "",
            "verify_provenance_source": "",
            "verify_source_url": "",
            "verification_status": "pending_binding_provenance_review",
            "notes": "Start with binder evidence and quantitative affinity.",
        },
        {
            "priority_rank": "4",
            "packet_step": "core_non_binder_01",
            "replacement_ligand_id": "acetaminophen",
            "verify_reference_binding_kcal_mol": "",
            "verify_provenance_source": "",
            "verify_source_url": "",
            "verification_status": "pending_binding_provenance_review",
            "notes": "Use conservative non-binder evidence and keep provenance explicit.",
        },
    ]
    payload = build_payload(rows, "ca2")
    row = payload["sheet_rows"][0]
    assert row["verify_reference_binding_kcal_mol"] == "-10.8060"
    assert row["verification_status"] == "verified_chembl_binding"
    assert "CHEMBL205" in row["verify_provenance_source"]
    assert row["verify_source_url"].endswith("/CHEMBL1146805/")
    assert payload["summary"]["verified_row_count"] == 1


def test_build_payload_updates_pxr_core_binders() -> None:
    rows = [
        {
            "priority_rank": "1",
            "packet_step": "core_eval_binder_01",
            "replacement_ligand_id": "rifampicin",
            "verify_reference_binding_kcal_mol": "",
            "verify_provenance_source": "",
            "verify_source_url": "",
            "verification_status": "pending_binding_provenance_review",
            "notes": "Start with binder evidence and quantitative affinity.",
        },
        {
            "priority_rank": "3",
            "packet_step": "core_fit_binder_01",
            "replacement_ligand_id": "hyperforin",
            "verify_reference_binding_kcal_mol": "",
            "verify_provenance_source": "",
            "verify_source_url": "",
            "verification_status": "pending_binding_provenance_review",
            "notes": "Start with binder evidence and quantitative affinity.",
        },
    ]
    payload = build_payload(rows, "pxr")
    row0 = payload["sheet_rows"][0]
    row1 = payload["sheet_rows"][1]
    assert row0["verify_reference_binding_kcal_mol"] == "-9.1390"
    assert row0["verification_status"] == "verified_chembl_activity_proxy"
    assert "EC50_200.0_nM" in row0["verify_provenance_source"]
    assert row1["verify_reference_binding_kcal_mol"] == "-10.3255"
    assert row1["verification_status"] == "verified_chembl_binding"
    assert "Ki_27.0_nM" in row1["verify_provenance_source"]

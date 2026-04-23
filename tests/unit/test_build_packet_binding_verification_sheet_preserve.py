from __future__ import annotations

from tools.build_packet_binding_verification_sheet import build_payload


def test_build_payload_preserves_existing_verification_fields() -> None:
    queue_rows = [
        {
            "priority_rank": "1",
            "packet": "core",
            "packet_step": "core_binder_01",
            "replacement_ligand_id": "acetazolamide",
            "replacement_is_binder": "1",
            "replacement_source": "seed",
        }
    ]
    workbook_rows = [
        {
            "packet_step": "core_binder_01",
            "replacement_smiles": "CC",
            "replacement_scaffold": "C",
            "replacement_pubchem_cid": "123",
            "replacement_structure_resolution_url": "https://example.org/compound",
        }
    ]
    existing = {
        "core_binder_01": {
            "verify_reference_binding_kcal_mol": "-10.8",
            "verify_provenance_source": "chembl_activity::demo",
            "verify_source_url": "https://example.org/activity",
            "verification_status": "verified_binding_provenance",
            "notes": "verified",
        }
    }

    payload = build_payload(queue_rows, workbook_rows, "ca2", existing_verification=existing)
    row = payload["sheet_rows"][0]
    assert row["verify_reference_binding_kcal_mol"] == "-10.8"
    assert row["verify_provenance_source"] == "chembl_activity::demo"
    assert row["verify_source_url"] == "https://example.org/activity"
    assert row["verification_status"] == "verified_binding_provenance"
    assert row["notes"] == "verified"


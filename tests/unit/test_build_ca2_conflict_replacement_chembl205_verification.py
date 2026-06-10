from tools.accounting.build_ca2_conflict_replacement_chembl205_verification import (
    build_payload,
    verify_shortlist_row,
)


def test_verify_shortlist_row_direct_negative() -> None:
    def fake_fetch(url: str) -> dict[str, object]:
        assert "CHEMBL866" in url
        return {
            "activities": [
                {
                    "activity_comment": "Inhibition < 50% @ 10 uM and thus dose-reponse curve not measured",
                    "assay_chembl_id": "CHEMBL1909123",
                    "document_chembl_id": "CHEMBL1909046",
                }
            ]
        }

    row = verify_shortlist_row(
        {
            "packet_step": "core_non_binder_01",
            "primary_replacement_ligand_id": "mannitol",
            "alternate_replacement_ligand_id": "glycerol",
            "superseded_ligand": "acetaminophen",
        },
        fetch_json=fake_fetch,
        today_local="2026-06-07",
    )
    assert row["verification_status"] == "verified_direct_negative_evidence_review_only"
    assert row["selected_replacement_ligand_id"] == "mannitol"
    assert row["replacement_status"] == "verified_direct_negative_review_only"


def test_verify_shortlist_row_promotes_alternate_on_no_activity() -> None:
    calls: list[str] = []

    def fake_fetch(url: str) -> dict[str, object]:
        if "CHEMBL853" in url:
            calls.append("primary")
            return {"activities": []}
        if "CHEMBL866" in url:
            calls.append("alternate")
            return {
                "activities": [
                    {
                        "activity_comment": "Inhibition < 50% @ 10 uM and thus dose-reponse curve not measured",
                        "assay_chembl_id": "CHEMBL1909123",
                        "document_chembl_id": "CHEMBL1909046",
                    }
                ]
            }
        raise AssertionError(url)

    row = verify_shortlist_row(
        {
            "packet_step": "ood_non_binder_01",
            "primary_replacement_ligand_id": "sucrose",
            "alternate_replacement_ligand_id": "mannitol",
            "superseded_ligand": "aspirin",
        },
        fetch_json=fake_fetch,
        today_local="2026-06-07",
    )
    assert calls == ["primary", "alternate"]
    assert row["selected_replacement_ligand_id"] == "mannitol"
    assert row["rejected_primary"] == "sucrose"
    assert row["verification_status"] == "verified_direct_negative_evidence_review_only"


def test_verify_shortlist_row_promotes_fallback_after_primary_and_alternate_fail() -> None:
    calls: list[str] = []

    def fake_fetch(url: str) -> dict[str, object]:
        if "CHEMBL542" in url:
            calls.append("benzoic_acid")
            return {"activities": []}
        if "CHEMBL886" in url:
            calls.append("nicotinamide")
            return {"activities": []}
        if "CHEMBL866" in url:
            calls.append("mannitol")
            return {
                "activities": [
                    {
                        "activity_comment": "Inhibition < 50% @ 10 uM and thus dose-reponse curve not measured",
                        "assay_chembl_id": "CHEMBL1909123",
                        "document_chembl_id": "CHEMBL1909046",
                    }
                ]
            }
        raise AssertionError(url)

    row = verify_shortlist_row(
        {
            "packet_step": "ood_non_binder_02",
            "primary_replacement_ligand_id": "benzoic_acid",
            "alternate_replacement_ligand_id": "nicotinamide",
            "superseded_ligand": "ibuprofen",
        },
        fetch_json=fake_fetch,
        today_local="2026-06-07",
    )
    assert calls == ["benzoic_acid", "nicotinamide", "mannitol"]
    assert row["selected_replacement_ligand_id"] == "mannitol"
    assert row["verification_status"] == "verified_direct_negative_evidence_review_only"


def test_build_payload_counts_blocked_rows() -> None:
    payload = build_payload(
        {
            "rows": [
                {
                    "packet_step": "ood_non_binder_02",
                    "primary_replacement_ligand_id": "benzoic_acid",
                    "alternate_replacement_ligand_id": "nicotinamide",
                    "superseded_ligand": "ibuprofen",
                }
            ]
        },
        fetch_json=lambda url: {"activities": []},
        today_local="2026-06-07",
    )
    assert payload["summary"]["direct_negative_review_only_count"] == 0
    assert payload["rows"][0]["verification_status"] == "verified_no_chembl205_target_activity"

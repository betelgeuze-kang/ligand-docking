from __future__ import annotations

from urllib.parse import parse_qs, urlparse

from tools import build_pxr_public_evidence_overlay as mod


def test_build_pxr_public_evidence_overlay_autofills_gap_rows() -> None:
    def fake_fetch(url: str) -> dict[str, object]:
        params = parse_qs(urlparse(url).query)
        molecule_chembl_id = params["molecule_chembl_id"][0]
        assert params["target_chembl_id"][0] == "CHEMBL3401"
        if molecule_chembl_id in {"CHEMBL1140", "CHEMBL25"}:
            return {"activities": []}
        raise AssertionError(f"unexpected molecule_chembl_id: {molecule_chembl_id}")

    payload = mod.build_payload(
        [
            {
                "packet_step": "ood_eval_non_binder_01",
                "replacement_ligand_id": "nicotinamide",
                "replacement_is_binder": "0",
                "capture_status": "pending_capture",
            },
            {
                "packet_step": "ood_eval_non_binder_03",
                "replacement_ligand_id": "aspirin",
                "replacement_is_binder": "0",
                "capture_status": "pending_capture",
            },
        ],
        fetch_json=fake_fetch,
        today_local="2026-04-17",
    )

    summary = payload["summary"]
    assert summary["row_count"] == 2
    assert summary["gap_row_count"] == 2
    assert summary["pending_row_count"] == 0
    assert summary["source_linked_count"] == 2

    rows = {row["packet_step"]: row for row in payload["rows"]}
    nicotinamide = rows["ood_eval_non_binder_01"]
    assert nicotinamide["overlay_status"] == "captured_gap"
    assert nicotinamide["capture_status"] == "captured_gap"
    assert nicotinamide["supports_local_target_specific_human_pxr"] == "no"
    assert "returned 0 records" in nicotinamide["source_title"]
    assert "evidence gap" in nicotinamide["source_note"]
    assert nicotinamide["manual_promotion_blocker"] == "no_local_target_activity_curated"
    assert nicotinamide["commit_status"] == "confirmed_defer"


def test_build_pxr_public_evidence_overlay_marks_activity_conflicts() -> None:
    def fake_fetch(url: str) -> dict[str, object]:
        return {
            "activities": [
                {
                    "assay_chembl_id": "CHEMBL5291845",
                    "assay_description": "Antagonist activity at human NR1I2 in an in vitro cell free assay measured by time-resolved fluorescence resonance energy transfer method",
                    "document_chembl_id": "CHEMBL5291721",
                    "standard_type": "AC50",
                    "standard_relation": "=",
                    "standard_value": "23999.9",
                    "standard_units": "nM",
                },
                {
                    "assay_chembl_id": "CHEMBL5291844",
                    "assay_description": "Agonist activity at human NR1I2 in an in vitro cell free assay measured by time-resolved fluorescence resonance energy transfer method",
                    "document_chembl_id": "CHEMBL5291721",
                    "standard_type": "AC50",
                    "standard_relation": ">",
                    "standard_value": "30000.0",
                    "standard_units": "nM",
                }
            ]
        }

    payload = mod.build_payload(
        [
            {
                "packet_step": "core_eval_non_binder_01",
                "replacement_ligand_id": "acetaminophen",
                "replacement_is_binder": "0",
                "capture_status": "pending_capture",
            }
        ],
        fetch_json=fake_fetch,
        today_local="2026-04-17",
    )

    row = payload["rows"][0]
    assert row["overlay_status"] == "captured_conflict"
    assert row["supports_local_target_specific_human_pxr"] == "yes"
    assert row["capture_status"] == "captured_conflict"
    assert row["manual_promotion_blocker"] == "activity_proxy_conflicts_with_non_binder"
    assert "CHEMBL5291845" in row["source_note"]
    assert "Antagonist activity at human NR1I2" in row["source_note"]
    assert "Agonist activity at human NR1I2" in row["source_note"]
    assert "23999.9" in row["source_note"]
    assert ">30000.0" in row["source_note"]
    assert row["manual_next_required_action"] == "manual_curated_search_or_defer"


def test_build_pxr_public_evidence_overlay_refreshes_existing_conflict_rows() -> None:
    def fake_fetch(url: str) -> dict[str, object]:
        return {
            "activities": [
                {
                    "assay_chembl_id": "CHEMBL5291845",
                    "assay_description": "Antagonist activity at human NR1I2 in an in vitro cell free assay measured by time-resolved fluorescence resonance energy transfer method",
                    "document_chembl_id": "CHEMBL5291721",
                    "standard_type": "AC50",
                    "standard_relation": "=",
                    "standard_value": "23999.9",
                    "standard_units": "nM",
                }
            ]
        }

    payload = mod.build_payload(
        [
            {
                "packet_step": "core_eval_non_binder_01",
                "replacement_ligand_id": "acetaminophen",
                "replacement_is_binder": "0",
                "capture_status": "captured_conflict",
                "manual_promotion_blocker": "activity_proxy_conflicts_with_non_binder",
            }
        ],
        fetch_json=fake_fetch,
        today_local="2026-04-19",
    )

    assert payload["summary"]["row_count"] == 1
    row = payload["rows"][0]
    assert row["overlay_status"] == "captured_conflict"
    assert "Antagonist activity at human NR1I2" in row["source_note"]


def test_build_pxr_public_evidence_overlay_uses_literature_override_for_bexarotene() -> None:
    def fake_fetch(url: str) -> dict[str, object]:
        return {"activities": []}

    payload = mod.build_payload(
        [
            {
                "packet_step": "ood_fit_binder_01",
                "replacement_ligand_id": "bexarotene",
                "replacement_is_binder": "1",
                "capture_status": "captured_gap",
            }
        ],
        fetch_json=fake_fetch,
        today_local="2026-04-18",
    )

    row = payload["rows"][0]
    assert row["overlay_status"] == "captured_supportive"
    assert row["supports_local_target_specific_human_pxr"] == "yes"
    assert row["capture_status"] == "captured_supportive"
    assert "PMID 18544536" in row["source_title"]
    assert row["manual_promotion_blocker"] == "quantitative_binding_value_or_activity_proxy_missing"
    assert row["manual_next_required_action"] == "curate_quantitative_binding_value"


def test_build_pxr_public_evidence_overlay_prefers_pubchem_human_pxr_proxy_for_bexarotene() -> None:
    def fake_fetch(url: str) -> dict[str, object]:
        if "chembl" in url:
            return {"activities": []}
        if "pubchem" in url:
            return {
                "Table": {
                    "Columns": {
                        "Column": [
                            {"Name": "AID"},
                            {"Name": "Panel Member ID"},
                            {"Name": "SID"},
                            {"Name": "CID"},
                            {"Name": "Activity Outcome"},
                            {"Name": "Target Accession"},
                            {"Name": "Target GeneID"},
                            {"Name": "Activity Value [uM]"},
                            {"Name": "Activity Name"},
                            {"Name": "Assay Name"},
                            {"Name": "Assay Type"},
                            {"Name": "PubMed ID"},
                            {"Name": "RNAi"},
                        ]
                    },
                    "Row": [
                        {
                            "Cell": [
                                "1346982",
                                "",
                                "144212724",
                                "82146",
                                "Inconclusive",
                                "ADZ17384",
                                "8856",
                                "19.3312",
                                "Potency",
                                "Human pregnane X receptor (PXR) small molecule agonists, qHTS assay",
                                "Confirmatory",
                                "",
                                "",
                            ]
                        },
                        {
                            "Cell": [
                                "1346985",
                                "",
                                "144206219",
                                "82146",
                                "Inactive",
                                "ADZ17384",
                                "8856",
                                "",
                                "Potency",
                                "Human pregnane X receptor (PXR) activation by small molecules, qHTS assay",
                                "Confirmatory",
                                "",
                                "",
                            ]
                        },
                    ],
                }
            }
        raise AssertionError(f"unexpected url: {url}")

    payload = mod.build_payload(
        [
            {
                "packet_step": "ood_fit_binder_01",
                "replacement_ligand_id": "bexarotene",
                "replacement_is_binder": "1",
                "capture_status": "captured_supportive",
                "manual_promotion_blocker": "quantitative_binding_value_or_activity_proxy_missing",
            }
        ],
        fetch_json=fake_fetch,
        today_local="2026-04-19",
    )

    row = payload["rows"][0]
    assert row["overlay_status"] == "captured_supportive"
    assert row["supports_local_target_specific_human_pxr"] == "yes"
    assert "PubChem CID 82146" in row["source_title"]
    assert row["manual_assay_type_honesty"] == "activity_present_manual_confirmation_required"
    assert row["manual_promotion_blocker"] == "activity_present_manual_confirmation_required"
    assert row["manual_next_required_action"] == "manual_curated_search_or_defer"
    assert "AID 1346982" in row["source_note"]
    assert "19.3312 uM" in row["source_note"]


def test_build_pxr_public_evidence_overlay_uses_pubchem_conflict_for_caffeine() -> None:
    def fake_fetch(url: str) -> dict[str, object]:
        if "chembl" in url:
            return {"activities": []}
        if "pubchem" in url:
            return {
                "Table": {
                    "Columns": {
                        "Column": [
                            {"Name": "AID"},
                            {"Name": "Panel Member ID"},
                            {"Name": "SID"},
                            {"Name": "CID"},
                            {"Name": "Activity Outcome"},
                            {"Name": "Target Accession"},
                            {"Name": "Target GeneID"},
                            {"Name": "Activity Value [uM]"},
                            {"Name": "Activity Name"},
                            {"Name": "Assay Name"},
                            {"Name": "Assay Type"},
                            {"Name": "PubMed ID"},
                            {"Name": "RNAi"},
                        ]
                    },
                    "Row": [
                        {
                            "Cell": [
                                "1346982",
                                "",
                                "144208883",
                                "2519",
                                "Active",
                                "ADZ17384",
                                "8856",
                                "5.5148",
                                "Potency",
                                "Human pregnane X receptor (PXR) small molecule agonists, qHTS assay",
                                "Confirmatory",
                                "",
                                "",
                            ]
                        },
                        {
                            "Cell": [
                                "720659",
                                "",
                                "17389997",
                                "2519",
                                "Inactive",
                                "ADZ17384",
                                "8856",
                                "",
                                "Potency",
                                "qHTS assay for small molecule activators of the human pregnane X receptor (PXR) signaling pathway",
                                "Confirmatory",
                                "",
                                "",
                            ]
                        },
                    ],
                }
            }
        raise AssertionError(f"unexpected url: {url}")

    payload = mod.build_payload(
        [
            {
                "packet_step": "core_eval_non_binder_02",
                "replacement_ligand_id": "caffeine",
                "replacement_is_binder": "0",
                "capture_status": "captured_gap",
            }
        ],
        fetch_json=fake_fetch,
        today_local="2026-04-19",
    )

    row = payload["rows"][0]
    assert row["overlay_status"] == "captured_conflict"
    assert row["capture_status"] == "captured_conflict"
    assert row["supports_local_target_specific_human_pxr"] == "yes"
    assert row["manual_assay_type_honesty"] == "activity_proxy_conflicts_with_non_binder"
    assert row["manual_promotion_blocker"] == "activity_proxy_conflicts_with_non_binder"
    assert row["manual_next_required_action"] == "manual_curated_search_or_defer"
    assert "AID 1346982" in row["source_note"]
    assert "5.5148 uM" in row["source_note"]
    assert "720659" in row["source_note"]


def test_build_pxr_public_evidence_overlay_uses_inactive_only_pubchem_lane_for_nicotinamide() -> None:
    def fake_fetch(url: str) -> dict[str, object]:
        if "chembl" in url:
            return {"activities": []}
        if "pubchem" in url:
            return {
                "Table": {
                    "Columns": {
                        "Column": [
                            {"Name": "AID"},
                            {"Name": "Panel Member ID"},
                            {"Name": "SID"},
                            {"Name": "CID"},
                            {"Name": "Activity Outcome"},
                            {"Name": "Target Accession"},
                            {"Name": "Target GeneID"},
                            {"Name": "Activity Value [uM]"},
                            {"Name": "Activity Name"},
                            {"Name": "Assay Name"},
                            {"Name": "Assay Type"},
                            {"Name": "PubMed ID"},
                            {"Name": "RNAi"},
                        ]
                    },
                    "Row": [
                        {
                            "Cell": [
                                "1346982",
                                "",
                                "111",
                                "936",
                                "Inactive",
                                "ADZ17384",
                                "8856",
                                "12.4",
                                "Potency",
                                "Human pregnane X receptor (PXR) small molecule agonists, qHTS assay",
                                "Confirmatory",
                                "",
                                "",
                            ]
                        }
                    ],
                }
            }
        raise AssertionError(f"unexpected url: {url}")

    payload = mod.build_payload(
        [
            {
                "packet_step": "ood_eval_non_binder_01",
                "replacement_ligand_id": "nicotinamide",
                "replacement_is_binder": "0",
                "capture_status": "captured_gap",
                "manual_promotion_blocker": "no_local_target_activity_curated",
            }
        ],
        fetch_json=fake_fetch,
        today_local="2026-04-19",
    )

    row = payload["rows"][0]
    assert row["overlay_status"] == "captured_review_only"
    assert row["capture_status"] == "captured_review_only"
    assert row["manual_assay_type_honesty"] == "inactive_only_human_pxr_qhts_review_only"
    assert row["manual_promotion_blocker"] == "inactive_only_human_pxr_qhts_review_only"
    assert row["manual_next_required_action"] == "manual_negative_evidence_review"

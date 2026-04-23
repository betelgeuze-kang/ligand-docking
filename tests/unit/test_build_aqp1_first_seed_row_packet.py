from __future__ import annotations

from tools import build_aqp1_first_seed_row_packet as mod


def test_build_aqp1_first_seed_row_packet() -> None:
    payload = mod.build_payload(
        {
            "rows": [
                {
                    "packet_step": "core_binder_01",
                    "candidate_name": "bacopaside II",
                    "promotion_class": "seed_now",
                    "source_anchor": "PMID 27474162",
                    "source_url": "https://pubmed.ncbi.nlm.nih.gov/27474162/",
                    "evidence_signal": "AQP1 water-channel IC50 18 uM",
                    "promotion_blocker": "no_local_aqp1_binder_evidence_curated",
                }
            ]
        },
        {
            "workbook_rows": [
                {
                    "packet_step": "core_binder_01",
                    "replacement_ligand_id": "",
                    "replacement_reference_binding_kcal_mol": "",
                    "replacement_source": "",
                    "replacement_smiles": "",
                    "replacement_scaffold": "",
                }
            ]
        },
        {
            "rows": [
                {
                    "packet_step": "core_binder_01",
                    "candidate_name": "bacopaside II",
                }
            ]
        },
        {
            "rows": [
                {
                    "packet_step": "core_binder_01",
                    "source_anchor": "PMID 27474162",
                    "source_url": "https://pubmed.ncbi.nlm.nih.gov/27474162/",
                    "potency_or_signal": "AQP1 water-channel IC50 18 uM",
                }
            ]
        },
    )
    assert payload["summary"]["packet_step"] == "core_binder_01"
    assert payload["summary"]["candidate_name"] == "bacopaside II"
    assert payload["summary"]["ready_to_copy_field_count"] == 1
    assert payload["summary"]["blocked_field_count"] == 4
    rows = {row["field_name"]: row for row in payload["rows"]}
    assert rows["replacement_source"]["status"] == "ready_to_copy"
    assert rows["replacement_reference_binding_kcal_mol"]["status"] == "blocked_quantitative_binding_gap"


def test_build_aqp1_seed_row_packet_accepts_custom_packet_step() -> None:
    payload = mod.build_payload(
        {
            "rows": [
                {
                    "packet_step": "core_binder_02",
                    "candidate_name": "AqB013",
                    "promotion_class": "seed_now",
                    "source_anchor": "PMID 22427546",
                    "source_url": "https://pubmed.ncbi.nlm.nih.gov/22427546/",
                    "evidence_signal": "AQP1 functional flux block",
                    "promotion_blocker": "no_local_aqp1_binder_evidence_curated",
                }
            ]
        },
        {
            "workbook_rows": [
                {
                    "packet_step": "core_binder_02",
                    "replacement_ligand_id": "",
                    "replacement_reference_binding_kcal_mol": "",
                    "replacement_source": "",
                    "replacement_smiles": "",
                    "replacement_scaffold": "",
                }
            ]
        },
        {"rows": [{"packet_step": "core_binder_02", "candidate_name": "AqB013"}]},
        {"rows": []},
        packet_step="core_binder_02",
    )
    assert payload["summary"]["packet_step"] == "core_binder_02"
    assert payload["summary"]["candidate_name"] == "AqB013"
    rows = {row["field_name"]: row for row in payload["rows"]}
    assert rows["replacement_source"]["suggested_value"] == "https://pubmed.ncbi.nlm.nih.gov/22427546/"

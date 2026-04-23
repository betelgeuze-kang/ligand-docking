from __future__ import annotations

from tools import build_aqp1_packet_replacement_workbook as mod


def test_build_aqp1_packet_replacement_workbook() -> None:
    payload = mod.build_payload(
        {
            "queue_rows": [
                {
                    "packet": "core",
                    "packet_step": "core_binder_01",
                    "current_ligand_id": "aqp1_placeholder_binder_01",
                    "binder_label": "binder",
                    "current_role": "far_ood_eval",
                    "current_reference_binding_kcal_mol": "-8.0",
                    "current_source": "template_placeholder_needs_curation",
                    "current_smiles": "O",
                    "current_scaffold": "template_placeholder",
                    "placeholder_sources": "reference,meta",
                    "replacement_role": "far_ood_eval",
                }
            ]
        }
    )
    row = payload["workbook_rows"][0]
    assert payload["summary"]["workbook_row_count"] == 1
    assert row["replacement_is_binder"] == "1"
    assert "replacement_ligand_id" in row["required_missing_fields"]
    assert "replacement_role" not in row["required_missing_fields"]

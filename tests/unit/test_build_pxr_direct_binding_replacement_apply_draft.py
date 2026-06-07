from __future__ import annotations

import json
from pathlib import Path

from tools.product import build_pxr_direct_binding_replacement_apply_draft as mod


def _write(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_pxr_direct_binding_replacement_apply_draft_overlays_blocked_rows(
    tmp_path: Path,
) -> None:
    workbook_fieldnames = [
        "packet",
        "packet_step",
        "current_role",
        "current_ligand_id",
        "replacement_role",
        "replacement_ligand_id",
        "replacement_reference_binding_kcal_mol",
        "replacement_source",
        "replacement_smiles",
        "replacement_molecular_weight",
        "replacement_logp",
        "replacement_h_donors",
        "replacement_h_acceptors",
        "replacement_rot_bonds",
        "replacement_scaffold",
        "row_ready_for_apply",
        "required_missing_fields",
        "notes",
    ]
    workbook_rows = [
        {
            "packet": "core",
            "packet_step": "core_eval_non_binder_01",
            "current_role": "non_binder",
            "current_ligand_id": "acetaminophen",
            "row_ready_for_apply": "no",
            "required_missing_fields": "replacement_reference_binding_kcal_mol",
            "notes": "blocked placeholder",
        },
        {
            "packet": "core",
            "packet_step": "core_fit_binder_01",
            "current_role": "binder",
            "current_ligand_id": "hyperforin",
            "replacement_ligand_id": "hyperforin",
            "replacement_reference_binding_kcal_mol": "-10.3255",
            "row_ready_for_apply": "yes",
            "required_missing_fields": "",
        },
    ]
    candidate_packet = {
        "summary": {"replacement_candidate_packet_ready": True},
        "rows": [
            {
                "replacement_for_packet_step": "core_eval_non_binder_01",
                "replacement_ligand_id": "e_guggulsterone",
                "molecule_chembl_id": "CHEMBL402063",
                "reference_binding_kcal_mol": "-11.7595",
                "source": "chembl_direct_binding::CHEMBL3401::CHEMBL402063::activity_1610264",
                "planned_role": "non_binder",
            }
        ],
    }
    _write(
        tmp_path / "chembl_molecule_CHEMBL402063.json",
        {
            "molecule_properties": {
                "full_mwt": "312.45",
                "alogp": "5.12",
                "hbd": 1,
                "hba": 2,
                "rtb": 3,
            },
            "molecule_structures": {
                "canonical_smiles": "CC1CCC2C(C1)CCC3C2CCC4=CC(=O)CCC34C",
                "standard_inchi_key": "WXSPTSKQZQYNGW-UHFFFAOYSA-N",
            },
        },
    )

    payload = mod.build_payload(
        workbook_rows=workbook_rows,
        workbook_fieldnames=workbook_fieldnames,
        candidate_packet=candidate_packet,
        molecule_dir=tmp_path,
    )

    summary = payload["summary"]
    assert summary["status"] == "blocked_pxr_direct_binding_replacement_apply_draft"
    assert summary["draft_ready"] is False
    assert summary["blocked_row_count_before_draft"] == 1
    assert summary["direct_binding_overlay_row_count"] == 1
    assert summary["ready_for_apply_row_count_after_draft"] == 2
    assert summary["blocked_row_count_after_draft"] == 0
    assert summary["authoritative_replacement_fields_touched"] is False

    draft = payload["draft_rows"][0]
    assert draft["replacement_ligand_id"] == "e_guggulsterone"
    assert draft["replacement_reference_binding_kcal_mol"] == "-11.7595"
    assert draft["replacement_source"].startswith("chembl_direct_binding::CHEMBL3401")
    assert draft["replacement_smiles"].startswith("CC1")
    assert draft["replacement_scaffold"] == "WXSPTSKQZQYNGW-UHFFFAOYSA-N"
    assert draft["row_ready_for_apply"] == "yes"
    assert draft["required_missing_fields"] == ""
    assert draft["replacement_structure_resolution_status"] == "chembl_molecule_resolved"

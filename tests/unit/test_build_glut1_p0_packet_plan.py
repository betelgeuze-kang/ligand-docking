from __future__ import annotations

from tools.product import build_glut1_p0_packet_plan as mod


def test_build_glut1_p0_packet_plan_marks_target_meta_ready_from_4pyp_sequence() -> None:
    payload = mod.build_payload(
        reference_rows=[
            {"target": "GLUT1_TRANSPORT_BLIND", "ligand_id": "glut1_placeholder_binder_01", "source": "template_placeholder_needs_curation"},
        ],
        split_rows=[
            {"target": "GLUT1_TRANSPORT_BLIND", "ligand_id": "glut1_placeholder_binder_01", "role": "far_ood_eval"},
        ],
        meta_rows=[
            {"ligand_id": "glut1_placeholder_binder_01", "scaffold": "template_placeholder"},
        ],
        target_rows=[
            {
                "target": "GLUT1_TRANSPORT_BLIND",
                "native_pdb_path": "data/glut1.pdb",
                "pdb_id": "4PYP",
                "pocket_x": "0.0",
                "pocket_y": "0.0",
                "pocket_z": "0.0",
            }
        ],
        target_meta_rows=[
            {
                "target": "GLUT1_TRANSPORT_BLIND",
                "target_family": "MEMBRANE_TRANSPORT_GLUCOSE",
                "sequence": "MEEP",
                "pocket_fingerprint": "glut_transporter|central_cavity|state_sensitive|4pyp_seqres_chain_a",
            }
        ],
        profile_payload={"dry_run": True, "hard_decoy_fit_targets": "EGFR_KINASE"},
        workbook_payload={"workbook_rows": [{"packet_step": "core_binder_01", "row_ready_for_apply": "yes"}]},
    )

    rows = {row["step_id"]: row for row in payload["rows"]}
    assert rows["glut1_target_meta"]["status"] == "ready"
    assert rows["glut1_target_native"]["status"] == "todo"
    assert rows["glut1_ligand_reference"]["status"] == "todo"
    assert payload["summary"]["p0_open_count"] == 4
    assert payload["summary"]["ready_workbook_row_count"] == 1


def test_build_glut1_p0_packet_plan_blocks_placeholder_sequence() -> None:
    payload = mod.build_payload(
        reference_rows=[],
        split_rows=[],
        meta_rows=[],
        target_rows=[],
        target_meta_rows=[
            {
                "target": "GLUT1_TRANSPORT_BLIND",
                "target_family": "MEMBRANE_TRANSPORT_GLUCOSE",
                "sequence": "TEMPLATE_SEQ_GLUT1_P11166_OR_4PYP_REQUIRED",
                "pocket_fingerprint": "glut_transporter",
            }
        ],
        profile_payload={},
        workbook_payload={},
    )

    rows = {row["step_id"]: row for row in payload["rows"]}
    assert rows["glut1_target_meta"]["status"] == "todo"
    assert rows["glut1_target_meta"]["blocker"] == "sequence_placeholder"


def test_build_glut1_p0_packet_plan_counts_non_prefixed_replacement_meta_rows() -> None:
    payload = mod.build_payload(
        reference_rows=[
            {
                "target": "GLUT1_TRANSPORT_BLIND",
                "ligand_id": "cytochalasin_b",
                "source": "pubmed_direct_binding::PMID1716731",
            },
            {
                "target": "GLUT1_TRANSPORT_BLIND",
                "ligand_id": "glut1_placeholder_binder_02",
                "source": "template_placeholder_needs_curation",
            },
        ],
        split_rows=[
            {"target": "GLUT1_TRANSPORT_BLIND", "ligand_id": "cytochalasin_b", "role": "far_ood_eval"},
            {"target": "GLUT1_TRANSPORT_BLIND", "ligand_id": "glut1_placeholder_binder_02", "role": "far_ood_eval"},
        ],
        meta_rows=[
            {"ligand_id": "cytochalasin_b", "scaffold": "cytochalasin_macrocycle"},
            {"ligand_id": "glut1_placeholder_binder_02", "scaffold": "template_placeholder"},
        ],
        target_rows=[
            {
                "target": "GLUT1_TRANSPORT_BLIND",
                "native_pdb_path": "data/glut1.pdb",
                "pdb_id": "4PYP",
                "pocket_x": "1.0",
                "pocket_y": "2.0",
                "pocket_z": "3.0",
            }
        ],
        target_meta_rows=[
            {
                "target": "GLUT1_TRANSPORT_BLIND",
                "target_family": "MEMBRANE_TRANSPORT_GLUCOSE",
                "sequence": "MEEP",
                "pocket_fingerprint": "glut_transporter|central_cavity|state_sensitive|4pyp_seqres_chain_a",
            }
        ],
        profile_payload={"dry_run": True, "hard_decoy_fit_targets": "EGFR_KINASE"},
        workbook_payload={"workbook_rows": [{"packet_step": "core_binder_01", "row_ready_for_apply": "yes"}]},
    )

    rows = {row["step_id"]: row for row in payload["rows"]}
    assert rows["glut1_ligand_meta"]["status"] == "todo"
    assert "row_count=2" in rows["glut1_ligand_meta"]["detail"]
    assert "placeholder_rows=1" in rows["glut1_ligand_meta"]["detail"]

from __future__ import annotations

from tools.product import build_glut1_local_evidence_note as mod


def test_build_glut1_local_evidence_note_blocked() -> None:
    reference_rows = [
        {"target": "GLUT1_TRANSPORT_BLIND", "ligand_id": "glut1_placeholder_binder_01", "is_binder": "1", "source": "template_placeholder_needs_curation"},
        {"target": "GLUT1_TRANSPORT_BLIND", "ligand_id": "glut1_placeholder_nonbinder_01", "is_binder": "0", "source": "template_placeholder_needs_curation"},
    ]
    meta_rows = [
        {"ligand_id": "glut1_placeholder_binder_01", "scaffold": "template_placeholder"},
        {"ligand_id": "glut1_placeholder_nonbinder_01", "scaffold": "template_placeholder"},
    ]
    split_rows = [
        {"target": "GLUT1_TRANSPORT_BLIND", "ligand_id": "glut1_placeholder_binder_01", "role": "far_ood_eval"},
        {"target": "GLUT1_TRANSPORT_BLIND", "ligand_id": "glut1_placeholder_nonbinder_01", "role": "far_ood_eval"},
    ]
    profile_payload = {"hard_decoy_fit_targets": "EGFR_KINASE", "dry_run": True}
    target_rows = [{"target": "GLUT1_TRANSPORT_BLIND", "pdb_id": "4PYP"}]
    target_meta_rows = [{"target": "GLUT1_TRANSPORT_BLIND", "sequence": "TEMPLATE_SEQ_GLUT1_P11166_OR_4PYP_REQUIRED"}]
    manual_queue_payload = {"summary": {"review_only_negative_count": 1, "defer_binder_count": 1}}
    payload = mod.build_payload(
        reference_rows,
        meta_rows,
        split_rows,
        profile_payload,
        target_rows,
        target_meta_rows,
        manual_queue_payload,
    )
    assert payload["summary"]["endpoint_status"] == "draft_only_local_evidence_blocked"
    assert payload["summary"]["local_target_specific_binder_evidence_curated"] is False
    assert payload["summary"]["temporary_fit_donor_target"] == "EGFR_KINASE"

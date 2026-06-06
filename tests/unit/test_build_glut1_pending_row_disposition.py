from __future__ import annotations

from tools.product import build_glut1_pending_row_disposition as mod


def test_build_glut1_pending_row_disposition() -> None:
    payload = mod.build_payload(
        [
            {"packet_step": "core_binder_01", "replacement_ligand_id": "", "replacement_is_binder": "1", "required_missing_fields": "replacement_ligand_id"},
            {"packet_step": "core_non_binder_01", "replacement_ligand_id": "", "replacement_is_binder": "0", "required_missing_fields": "replacement_ligand_id"},
        ]
    )
    assert payload["summary"]["defer_rows"] == 1
    assert payload["summary"]["review_only_rows"] == 1


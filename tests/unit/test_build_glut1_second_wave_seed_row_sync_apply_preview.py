from __future__ import annotations

import json
from pathlib import Path

from tools.product import build_glut1_second_wave_seed_row_sync_apply_preview as mod


ROOT = Path(__file__).resolve().parents[2]


def test_build_glut1_second_wave_seed_row_sync_apply_preview_reads_current_artifacts() -> None:
    seed_fill_draft = json.loads((ROOT / "runs/glut1_second_wave_seed_row_fill_draft_current.json").read_text(encoding="utf-8"))
    workbook = json.loads((ROOT / "runs/glut1_packet_replacement_workbook_current.json").read_text(encoding="utf-8"))
    seed_packet = json.loads((ROOT / "runs/glut1_second_wave_seed_row_packet_current.json").read_text(encoding="utf-8"))

    row = mod.build_row(seed_fill_draft, workbook, seed_packet, "core_binder_01")
    summary = mod.build_summary(seed_fill_draft, row)

    assert summary["target_id"] == "GLUT1"
    assert summary["wave"] == "second"
    assert summary["safe_staged_field_count"] == 4
    assert summary["unresolved_field_count"] == 1
    assert summary["authoritative_apply_allowed"] is False
    assert row["unresolved_fields"] == "replacement_reference_binding_kcal_mol"
    assert row["staged_replacement_ligand_id"] == "cytochalasin_b"
    assert row["staged_replacement_source"].startswith("pubmed_direct_binding::PMID1716731")
    assert row["staged_replacement_smiles"]
    assert row["staged_replacement_scaffold"] == "cytochalasin_macrocycle"

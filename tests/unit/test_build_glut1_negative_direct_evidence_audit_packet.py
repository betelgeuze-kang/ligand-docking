from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from tools.product import build_glut1_negative_direct_evidence_audit_packet as mod


ROOT = Path(__file__).resolve().parents[2]


def test_build_glut1_negative_direct_evidence_audit_packet() -> None:
    payload = mod.build_payload(
        json.loads((ROOT / "runs/glut1_negative_review_handoff_packet_current.json").read_text(encoding="utf-8")),
        json.loads((ROOT / "runs/glut1_second_wave_source_confirmation_packet_current.json").read_text(encoding="utf-8")),
        json.loads((ROOT / "runs/glut1_external_evidence_seed_current.json").read_text(encoding="utf-8")),
        as_of_date="2026-05-11",
    )

    summary = payload["summary"]
    rows = payload["rows"]
    assert summary["target_id"] == "GLUT1"
    assert summary["negative_slot_count"] == 3
    assert summary["placeholder_negative_candidate_count"] == 3
    assert summary["candidate_named_negative_ligand_count"] == 0
    assert summary["source_context_primary_focus_ligand"] == "cytochalasin B"
    assert summary["source_context_positive_or_binder_candidate_count"] == 3
    assert summary["source_context_negative_evidence_row_count"] == 0
    assert summary["positive_direct_quantitative_binding_count"] == 1
    assert summary["positive_exact_target_pair_candidate_count"] == 2
    assert summary["positive_exact_target_pair_activity_record_count"] == 5
    assert summary["claim_safe_kcal_ready_count"] == 0
    assert summary["caution_signal_count"] == 2
    assert summary["direct_negative_quantitative_row_found_count"] == 0
    assert summary["authoritative_negative_apply_allowed_count"] == 0
    assert summary["audit_decision"] == "keep_placeholder_negative_slots_review_only_no_authoritative_negative_promotion"
    assert rows[0]["audit_route"] == "placeholder_negative_slot_check"
    assert rows[0]["result_count"] == 3
    assert rows[1]["audit_route"] == "positive_source_context_contrast"
    assert rows[1]["positive_exact_target_pair_activity_record_count"] == 5
    assert rows[2]["candidate_name"] == "forskolin,gossypol"


def test_build_glut1_negative_direct_evidence_audit_packet_cli(tmp_path: Path) -> None:
    out_json = tmp_path / "glut1_negative_direct_evidence_audit.json"
    out_csv = tmp_path / "glut1_negative_direct_evidence_audit.csv"
    out_md = tmp_path / "glut1_negative_direct_evidence_audit.md"

    subprocess.run(
        [
            sys.executable,
            "tools/product/build_glut1_negative_direct_evidence_audit_packet.py",
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ],
        cwd=ROOT,
        check=True,
    )

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["summary"]["packet_artifact"] == "runs/glut1_negative_direct_evidence_audit_packet_current.md"
    assert payload["summary"]["placeholder_negative_candidate_count"] == 3
    assert payload["summary"]["direct_negative_quantitative_row_found_count"] == 0
    assert out_csv.exists()
    assert out_md.exists()

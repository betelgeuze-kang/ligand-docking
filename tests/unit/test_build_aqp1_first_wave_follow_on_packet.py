from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from tools import build_aqp1_first_wave_follow_on_packet as mod


ROOT = Path(__file__).resolve().parents[2]


def test_build_aqp1_first_wave_follow_on_packet_build_payload_materializes_follow_on_rows() -> None:
    payload = mod.build_payload(
        json.loads((ROOT / "runs/transporter_seed_row_promotion_board_current.json").read_text()),
        json.loads((ROOT / "runs/aqp1_packet_replacement_workbook_current.json").read_text()),
        json.loads((ROOT / "runs/aqp1_manual_verdict_apply_draft_current.json").read_text()),
        json.loads((ROOT / "runs/aqp1_external_evidence_seed_current.json").read_text()),
        json.loads((ROOT / "runs/aqp1_manual_review_queue_current.json").read_text()),
        json.loads((ROOT / "runs/aqp1_quantitative_provenance_packet_current.json").read_text()),
    )

    summary = payload["summary"]
    rows = {row["packet_step"]: row for row in payload["rows"]}

    assert summary["status"] == "aqp1_first_wave_follow_on_packet_ready"
    assert summary["row_count"] == 2
    assert summary["follow_on_targets"] == "core_binder_02, core_binder_03"
    assert summary["primary_follow_on_target"] == "core_binder_02"
    assert summary["primary_focus_ligand"] == "AqB013"
    assert summary["candidate_names"] == "AqB013, AqB011"
    assert summary["source_anchors"] == "PMID 22427546, PMID 26467039"
    assert summary["exact_human_guardrail_ligand"] == "AqB013"

    assert rows["core_binder_02"]["priority_rank"] == 1
    assert rows["core_binder_02"]["focus_scope"] == "exact_human_activity_guardrail_follow_on"
    assert rows["core_binder_02"]["seed_packet_artifact"] == "runs/aqp1_first_seed_row_packet_core_binder_02_current.md"
    assert rows["core_binder_02"]["fill_draft_artifact"] == "runs/aqp1_seed_row_fill_draft_core_binder_02_current.md"
    assert rows["core_binder_02"]["sync_preview_artifact"] == "runs/aqp1_seed_row_sync_apply_preview_core_binder_02_current.md"
    assert rows["core_binder_02"]["seed_packet_next_required_step"].startswith("Use this packet")

    assert rows["core_binder_03"]["priority_rank"] == 2
    assert rows["core_binder_03"]["focus_scope"] == "follow_on_exact_source_scope"
    assert rows["core_binder_03"]["seed_packet_artifact"] == "runs/aqp1_first_seed_row_packet_core_binder_03_current.md"
    assert rows["core_binder_03"]["fill_draft_artifact"] == "runs/aqp1_seed_row_fill_draft_core_binder_03_current.md"
    assert rows["core_binder_03"]["sync_preview_artifact"] == "runs/aqp1_seed_row_sync_apply_preview_core_binder_03_current.md"
    assert rows["core_binder_03"]["sync_preview_next_required_step"].startswith(
        "This preview shows the exact non-authoritative synchronized row stage"
    )


def test_build_aqp1_first_wave_follow_on_packet_cli(tmp_path: Path) -> None:
    out_json = tmp_path / "aqp1_first_wave_follow_on_packet.json"
    out_csv = tmp_path / "aqp1_first_wave_follow_on_packet.csv"
    out_md = tmp_path / "aqp1_first_wave_follow_on_packet.md"

    subprocess.run(
        [
            sys.executable,
            "tools/build_aqp1_first_wave_follow_on_packet.py",
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
    assert payload["summary"]["status"] == "aqp1_first_wave_follow_on_packet_ready"
    assert payload["summary"]["row_count"] == 2
    assert payload["summary"]["candidate_names"] == "AqB013, AqB011"
    assert payload["rows"][0]["packet_step"] == "core_binder_02"
    assert payload["rows"][1]["packet_step"] == "core_binder_03"
    assert out_md.read_text(encoding="utf-8").startswith("# AQP1 First-Wave Follow-On Packet")

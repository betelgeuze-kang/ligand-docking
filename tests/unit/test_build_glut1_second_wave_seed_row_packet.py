from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from tools import build_glut1_second_wave_seed_row_packet as mod


ROOT = Path(__file__).resolve().parents[2]


def test_build_glut1_second_wave_seed_row_packet_reads_current_artifacts() -> None:
    payload = mod.build_payload(
        json.loads((ROOT / "runs/transporter_seed_row_promotion_board_current.json").read_text(encoding="utf-8")),
        json.loads((ROOT / "runs/glut1_packet_replacement_workbook_current.json").read_text(encoding="utf-8")),
        json.loads((ROOT / "runs/glut1_manual_verdict_apply_draft_current.json").read_text(encoding="utf-8")),
        json.loads((ROOT / "runs/glut1_second_wave_source_confirmation_packet_current.json").read_text(encoding="utf-8")),
    )

    summary = payload["summary"]
    assert summary["target_id"] == "GLUT1"
    assert summary["wave"] == "second"
    assert summary["packet_step"] == "core_binder_01"
    assert summary["candidate_name"] == "cytochalasin B"
    assert summary["promotion_class"] == "seed_after_aqp1"
    assert summary["source_anchor"] == "PMID 1716731"
    assert summary["direct_quantitative_binding_count"] == 1
    assert summary["exact_target_pair_activity_count"] == 2
    assert summary["structured_pair_absent_count"] == 1
    assert summary["blocked_field_count"] == 4
    assert summary["ready_to_copy_field_count"] == 1
    assert summary["authoritative_apply_allowed"] is False


def test_build_glut1_second_wave_seed_row_packet_cli(tmp_path: Path) -> None:
    out_json = tmp_path / "packet.json"
    out_csv = tmp_path / "packet.csv"
    out_md = tmp_path / "packet.md"

    subprocess.run(
        [
            sys.executable,
            "tools/build_glut1_second_wave_seed_row_packet.py",
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
    assert payload["summary"]["candidate_name"] == "cytochalasin B"
    assert payload["summary"]["promotion_class"] == "seed_after_aqp1"
    assert out_md.read_text(encoding="utf-8").startswith("# GLUT1 Second-Wave Seed Row Packet")

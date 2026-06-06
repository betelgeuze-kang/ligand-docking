from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from tools.product import build_aqp1_negative_slot_resolution_packet as mod


ROOT = Path(__file__).resolve().parents[2]


def test_build_aqp1_negative_slot_resolution_packet() -> None:
    payload = mod.build_payload(
        json.loads((ROOT / "runs/aqp1_negative_slot_closure_packet_current.json").read_text(encoding="utf-8")),
        json.loads((ROOT / "runs/aqp1_negative_source_exclusion_packet_current.json").read_text(encoding="utf-8")),
        json.loads((ROOT / "runs/aqp1_negative_evidence_acquisition_packet_current.json").read_text(encoding="utf-8")),
        json.loads((ROOT / "runs/aqp1_negative_evidence_confirmation_packet_current.json").read_text(encoding="utf-8")),
        as_of_date="2026-04-20",
    )

    summary = payload["summary"]
    rows = payload["rows"]
    assert summary["family"] == "aqp1"
    assert summary["row_count"] == 3
    assert summary["top_packet_step"] == "core_non_binder_01"
    assert summary["primary_anchor_pmid"] == "23123479"
    assert summary["acetazolamide_boundary_pmid"] == "40359885"
    assert summary["tetraethylammonium_exact_target_pair_absent_count"] == 1
    assert rows[0]["slot_resolution_role"] == "primary_exact_source_reinvestigation"
    assert rows[1]["slot_resolution_role"] == "acetazolamide_positive_boundary_exclusion"
    assert rows[1]["exclusion_candidate_name"] == "acetazolamide"
    assert rows[2]["slot_resolution_role"] == "tetraethylammonium_tool_reference_exclusion"
    assert rows[2]["exclusion_candidate_name"] == "tetraethylammonium"


def test_build_aqp1_negative_slot_resolution_packet_cli(tmp_path: Path) -> None:
    out_json = tmp_path / "aqp1_negative_slot_resolution.json"
    out_csv = tmp_path / "aqp1_negative_slot_resolution.csv"
    out_md = tmp_path / "aqp1_negative_slot_resolution.md"

    subprocess.run(
        [
            sys.executable,
            "tools/product/build_aqp1_negative_slot_resolution_packet.py",
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
    assert payload["summary"]["row_count"] == 3
    assert payload["summary"]["primary_anchor_pmid"] == "23123479"
    assert payload["summary"]["acetazolamide_boundary_pmid"] == "40359885"
    assert out_csv.exists()
    assert out_md.exists()

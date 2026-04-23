from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from tools import build_aqp1_negative_evidence_acquisition_packet as mod


ROOT = Path(__file__).resolve().parents[2]


def test_build_aqp1_negative_evidence_acquisition_packet() -> None:
    payload = mod.build_payload(
        json.loads((ROOT / "runs/aqp1_negative_slot_closure_packet_current.json").read_text(encoding="utf-8")),
        json.loads((ROOT / "runs/aqp1_negative_source_exclusion_packet_current.json").read_text(encoding="utf-8")),
        as_of_date="2026-04-20",
    )

    summary = payload["summary"]
    rows = payload["rows"]
    assert summary["family"] == "aqp1"
    assert summary["row_count"] == 3
    assert summary["primary_query_label"] == "pressure_induced_hemolysis_reinvestigation"
    assert summary["primary_anchor_pmid"] == "23123479"
    assert rows[0]["anchor_url"] == "https://pubmed.ncbi.nlm.nih.gov/23123479/"
    assert rows[1]["query_label"] == "acetazolamide_boundary_review"
    assert rows[2]["query_label"] == "tetraethylammonium_boundary_review"


def test_build_aqp1_negative_evidence_acquisition_packet_cli(tmp_path: Path) -> None:
    out_json = tmp_path / "aqp1_negative_evidence_acquisition.json"
    out_csv = tmp_path / "aqp1_negative_evidence_acquisition.csv"
    out_md = tmp_path / "aqp1_negative_evidence_acquisition.md"

    subprocess.run(
        [
            sys.executable,
            "tools/build_aqp1_negative_evidence_acquisition_packet.py",
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
    assert out_csv.exists()
    assert out_md.exists()

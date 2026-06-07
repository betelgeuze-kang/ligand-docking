from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from tools.product import build_aqp1_negative_frontier_resolution_packet as mod


ROOT = Path(__file__).resolve().parents[2]


def test_build_aqp1_negative_frontier_resolution_packet() -> None:
    payload = mod.build_payload(
        json.loads((ROOT / "runs/aqp1_negative_candidate_frontier_packet_current.json").read_text(encoding="utf-8")),
        json.loads((ROOT / "runs/aqp1_negative_evidence_confirmation_packet_current.json").read_text(encoding="utf-8")),
        as_of_date="2026-04-20",
    )

    summary = payload["summary"]
    rows = payload["rows"]

    assert summary["family"] == "aqp1"
    assert summary["row_count"] == 2
    assert summary["primary_frontier_candidate"] == "sodium nitroprusside"
    assert summary["solvent_fallback_candidate"] == "dimethyl sulfoxide"
    assert summary["indirect_context_row_count"] == 1
    assert summary["solvent_context_row_count"] == 1
    assert summary["exact_target_pair_absent_count"] == 2
    assert rows[0]["candidate_name"] == "sodium nitroprusside"
    assert rows[0]["frontier_resolution_role"] == "primary_indirect_aqp1_context_frontier_candidate"
    assert rows[0]["supporting_context_pmid"] == "27261598"
    assert rows[0]["activity_url"].endswith("molecule_chembl_id=CHEMBL136478&target_chembl_id=CHEMBL4523210&limit=10")
    assert rows[1]["candidate_name"] == "dimethyl sulfoxide"
    assert rows[1]["frontier_resolution_role"] == "solvent_context_fallback_frontier_candidate"
    assert rows[1]["supporting_context_pmid"] == ""
    assert rows[1]["activity_url"].endswith("molecule_chembl_id=CHEMBL504&target_chembl_id=CHEMBL4523210&limit=10")


def test_build_aqp1_negative_frontier_resolution_packet_cli(tmp_path: Path) -> None:
    out_json = tmp_path / "aqp1_negative_frontier_resolution.json"
    out_csv = tmp_path / "aqp1_negative_frontier_resolution.csv"
    out_md = tmp_path / "aqp1_negative_frontier_resolution.md"

    subprocess.run(
        [
            sys.executable,
            "tools/product/build_aqp1_negative_frontier_resolution_packet.py",
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
    assert payload["summary"]["row_count"] == 2
    assert payload["summary"]["primary_frontier_candidate"] == "sodium nitroprusside"
    assert payload["summary"]["solvent_fallback_candidate"] == "dimethyl sulfoxide"
    assert out_csv.exists()
    assert out_md.exists()

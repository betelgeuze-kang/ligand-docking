from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from tools.product import build_aqp1_negative_candidate_frontier_packet as mod


ROOT = Path(__file__).resolve().parents[2]


def test_build_aqp1_negative_candidate_frontier_packet() -> None:
    payload = mod.build_payload(
        json.loads((ROOT / "runs/aqp1_negative_evidence_confirmation_packet_current.json").read_text(encoding="utf-8")),
        json.loads((ROOT / "runs/aqp1_negative_source_exclusion_packet_current.json").read_text(encoding="utf-8")),
        as_of_date="2026-04-20",
    )

    summary = payload["summary"]
    rows = payload["rows"]

    assert summary["family"] == "aqp1"
    assert summary["row_count"] == 4
    assert summary["exact_source_tested_row_count"] == 4
    assert summary["exact_target_pair_absent_count"] == 4
    assert summary["frontier_candidate_count"] == 2
    assert summary["claim_safe_negative_candidate_count"] == 0
    assert summary["primary_frontier_candidate"] == "sodium nitroprusside"
    assert summary["primary_anchor_pmid"] == "23123479"
    assert rows[0]["candidate_name"] == "acetazolamide"
    assert rows[0]["molecule_chembl_id"] == "CHEMBL20"
    assert rows[0]["source_role"] == "positive_boundary_context_keep_excluded"
    assert rows[0]["exact_target_pair_activity_count"] == 0
    assert rows[1]["candidate_name"] == "tetraethylammonium"
    assert rows[1]["molecule_chembl_id"] == "CHEMBL9324"
    assert rows[2]["candidate_name"] == "sodium nitroprusside"
    assert rows[2]["molecule_chembl_id"] == "CHEMBL136478"
    assert rows[2]["source_role"] == "exact_source_tested_frontier_candidate"
    assert rows[2]["activity_url"].endswith("molecule_chembl_id=CHEMBL136478&target_chembl_id=CHEMBL4523210&limit=10")
    assert rows[3]["candidate_name"] == "dimethyl sulfoxide"
    assert rows[3]["molecule_chembl_id"] == "CHEMBL504"
    assert rows[3]["activity_url"].endswith("molecule_chembl_id=CHEMBL504&target_chembl_id=CHEMBL4523210&limit=10")


def test_build_aqp1_negative_candidate_frontier_packet_cli(tmp_path: Path) -> None:
    out_json = tmp_path / "aqp1_negative_candidate_frontier.json"
    out_csv = tmp_path / "aqp1_negative_candidate_frontier.csv"
    out_md = tmp_path / "aqp1_negative_candidate_frontier.md"

    subprocess.run(
        [
            sys.executable,
            "tools/product/build_aqp1_negative_candidate_frontier_packet.py",
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
    assert payload["summary"]["row_count"] == 4
    assert payload["summary"]["primary_frontier_candidate"] == "sodium nitroprusside"
    assert payload["summary"]["exact_target_pair_absent_count"] == 4
    assert out_csv.exists()
    assert out_md.exists()

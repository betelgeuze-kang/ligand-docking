from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from tools import build_aqp1_negative_primary_probe_packet as mod


ROOT = Path(__file__).resolve().parents[2]


def test_build_aqp1_negative_primary_probe_packet() -> None:
    payload = mod.build_payload(
        json.loads((ROOT / "runs/aqp1_negative_frontier_resolution_packet_current.json").read_text(encoding="utf-8")),
        json.loads((ROOT / "runs/aqp1_negative_evidence_confirmation_packet_current.json").read_text(encoding="utf-8")),
        as_of_date="2026-04-20",
    )

    summary = payload["summary"]
    rows = payload["rows"]

    assert summary["family"] == "aqp1"
    assert summary["row_count"] == 1
    assert summary["primary_probe_candidate"] == "sodium nitroprusside"
    assert summary["source_anchor_pmid"] == "23123479"
    assert summary["indirect_context_pmid"] == "27261598"
    assert summary["assay_context_pmid"] == "26685080"
    assert summary["exact_target_pair_absent_count"] == 1
    assert rows[0]["candidate_name"] == "sodium nitroprusside"
    assert rows[0]["probe_role"] == "primary_review_only_negative_probe_candidate"
    assert rows[0]["activity_url"].endswith("molecule_chembl_id=CHEMBL136478&target_chembl_id=CHEMBL4523210&limit=10")


def test_build_aqp1_negative_primary_probe_packet_cli(tmp_path: Path) -> None:
    out_json = tmp_path / "aqp1_negative_primary_probe.json"
    out_csv = tmp_path / "aqp1_negative_primary_probe.csv"
    out_md = tmp_path / "aqp1_negative_primary_probe.md"

    subprocess.run(
        [
            sys.executable,
            "tools/build_aqp1_negative_primary_probe_packet.py",
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
    assert payload["summary"]["row_count"] == 1
    assert payload["summary"]["primary_probe_candidate"] == "sodium nitroprusside"
    assert out_csv.exists()
    assert out_md.exists()

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from tools import build_aqp1_negative_direct_evidence_audit_packet as mod


ROOT = Path(__file__).resolve().parents[2]


def test_build_aqp1_negative_direct_evidence_audit_packet() -> None:
    payload = mod.build_payload(
        json.loads((ROOT / "runs/aqp1_negative_evidence_acquisition_packet_current.json").read_text(encoding="utf-8")),
        json.loads((ROOT / "runs/aqp1_negative_exact_source_outcome_packet_current.json").read_text(encoding="utf-8")),
        json.loads((ROOT / "runs/aqp1_negative_primary_probe_resolution_packet_current.json").read_text(encoding="utf-8")),
        json.loads((ROOT / "runs/aqp1_negative_source_exclusion_packet_current.json").read_text(encoding="utf-8")),
        as_of_date="2026-05-11",
    )

    summary = payload["summary"]
    rows = payload["rows"]
    assert summary["family"] == "aqp1"
    assert summary["primary_candidate"] == "sodium nitroprusside"
    assert summary["pubmed_exact_ligand_target_hit_count"] == 8
    assert summary["pubmed_pressure_hemolysis_hit_count"] == 1
    assert summary["chembl_exact_target_pair_activity_count"] == 0
    assert summary["direct_negative_quantitative_row_found_count"] == 0
    assert summary["authoritative_negative_apply_allowed_count"] == 0
    assert summary["no_direct_negative_source_row_count"] == 3
    assert summary["audit_decision"] == "keep_review_only_no_authoritative_negative_promotion"
    assert rows[0]["audit_route"] == "pubmed_exact_ligand_target_query"
    assert rows[0]["representative_pmids"].startswith("27261598,25338424,23123479")
    assert rows[1]["best_anchor_pmid"] == "23123479"
    assert rows[2]["audit_route"] == "chembl_exact_target_pair_query"
    assert rows[2]["result_count"] == 0


def test_build_aqp1_negative_direct_evidence_audit_packet_cli(tmp_path: Path) -> None:
    out_json = tmp_path / "aqp1_negative_direct_evidence_audit.json"
    out_csv = tmp_path / "aqp1_negative_direct_evidence_audit.csv"
    out_md = tmp_path / "aqp1_negative_direct_evidence_audit.md"

    subprocess.run(
        [
            sys.executable,
            "tools/build_aqp1_negative_direct_evidence_audit_packet.py",
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
    assert payload["summary"]["packet_artifact"] == "runs/aqp1_negative_direct_evidence_audit_packet_current.md"
    assert payload["summary"]["pubmed_exact_ligand_target_hit_count"] == 8
    assert payload["summary"]["direct_negative_quantitative_row_found_count"] == 0
    assert out_csv.exists()
    assert out_md.exists()

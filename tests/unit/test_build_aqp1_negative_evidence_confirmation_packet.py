from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from tools.product import build_aqp1_negative_evidence_confirmation_packet as mod


ROOT = Path(__file__).resolve().parents[2]


def test_build_aqp1_negative_evidence_confirmation_packet() -> None:
    payload = mod.build_payload(
        json.loads((ROOT / "runs/aqp1_negative_slot_closure_packet_current.json").read_text(encoding="utf-8")),
        json.loads((ROOT / "runs/aqp1_negative_source_exclusion_packet_current.json").read_text(encoding="utf-8")),
        json.loads((ROOT / "runs/aqp1_negative_evidence_acquisition_packet_current.json").read_text(encoding="utf-8")),
        json.loads((ROOT / "runs/aqp1_negative_exact_source_outcome_packet_current.json").read_text(encoding="utf-8")),
        as_of_date="2026-04-20",
    )

    summary = payload["summary"]
    rows = payload["rows"]
    assert summary["family"] == "aqp1"
    assert summary["row_count"] == 3
    assert summary["top_packet_step"] == "core_non_binder_01"
    assert summary["primary_anchor_pmid"] == "23123479"
    assert summary["boundary_positive_pmid"] == "40359885"
    assert summary["primary_anchor_outcome_row_count"] == 4
    assert summary["primary_anchor_almost_unaffected_candidate_count"] == 2
    assert summary["primary_anchor_small_inhibitor_signal_candidate"] == "dimethyl sulfoxide"
    assert summary["primary_anchor_direct_negative_quantitative_row_found_count"] == 0
    assert summary["primary_anchor_authoritative_negative_apply_allowed_count"] == 0
    assert summary["confirmation_decision"] == "keep_review_only_no_authoritative_negative_promotion"
    assert rows[0]["packet_step"] == "core_non_binder_01"
    assert rows[0]["primary_anchor_url"] == "https://pubmed.ncbi.nlm.nih.gov/23123479/"
    assert rows[0]["primary_anchor_source_endpoint"] == "hemolysis_at_200_mpa"
    assert rows[0]["primary_anchor_outcome_row_count"] == 4
    assert rows[0]["positive_boundary_url"] == "https://pubmed.ncbi.nlm.nih.gov/40359885/"


def test_build_aqp1_negative_evidence_confirmation_packet_cli(tmp_path: Path) -> None:
    out_json = tmp_path / "aqp1_negative_evidence_confirmation.json"
    out_csv = tmp_path / "aqp1_negative_evidence_confirmation.csv"
    out_md = tmp_path / "aqp1_negative_evidence_confirmation.md"

    subprocess.run(
        [
            sys.executable,
            "tools/product/build_aqp1_negative_evidence_confirmation_packet.py",
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
    assert payload["summary"]["primary_anchor_outcome_row_count"] == 4
    assert payload["summary"]["primary_anchor_almost_unaffected_candidate_count"] == 2
    assert payload["summary"]["boundary_positive_pmid"] == "40359885"
    assert out_csv.exists()
    assert out_md.exists()

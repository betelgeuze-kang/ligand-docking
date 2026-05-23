from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path

from tools import build_aqp1_negative_primary_functional_evidence as mod


ROOT = Path(__file__).resolve().parents[2]


def test_build_aqp1_negative_primary_functional_evidence_rows_are_apply_ready() -> None:
    payload = mod.build_payload(as_of_date="2026-05-13")

    summary = payload["summary"]
    rows = payload["rows"]
    assert summary["curation_ready"] is True
    assert summary["source_pmid"] == "23123479"
    assert summary["source_article_type"] == "primary_journal_article"
    assert summary["direct_negative_quantitative_row_found_count"] == 3
    assert summary["slot_cover_ready_count"] == 3
    assert summary["split_reference_meta_ready"] is True
    assert summary["authoritative_negative_apply_allowed_count"] == 3
    assert summary["negative_evidence_closure_allowed"] is True
    assert summary["claim_promotion_allowed"] is False
    assert [row["slot_queue_id"] for row in rows] == [
        "AQP1__core_non_binder_01",
        "AQP1__core_non_binder_02",
        "AQP1__core_non_binder_03",
    ]
    assert rows[0]["candidate_name"] == "sodium nitroprusside"
    assert rows[2]["candidate_name"] == "acetazolamide"
    assert all(row["negative_semantics"] == "no_transport_effect" for row in rows)
    assert all("review-only" not in row["primary_source"].lower() for row in rows)


def test_build_aqp1_negative_primary_functional_evidence_cli_writes_intake_csv(tmp_path: Path) -> None:
    out_json = tmp_path / "primary.json"
    out_csv = tmp_path / "primary.csv"
    out_md = tmp_path / "primary.md"
    intake_csv = tmp_path / "intake.csv"

    subprocess.run(
        [
            sys.executable,
            "tools/build_aqp1_negative_primary_functional_evidence.py",
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
            "--intake-csv",
            str(intake_csv),
        ],
        cwd=ROOT,
        check=True,
    )

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["summary"]["curation_ready"] is True
    with intake_csv.open("r", encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
    assert len(rows) == 3
    assert rows[0]["source_id"].startswith("PMID:23123479")
    assert out_csv.exists()
    assert out_md.read_text(encoding="utf-8").startswith("# AQP1 Negative Primary Functional Evidence")

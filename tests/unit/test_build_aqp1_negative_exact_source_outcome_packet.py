from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from tools.product import build_aqp1_negative_exact_source_outcome_packet as mod


ROOT = Path(__file__).resolve().parents[2]


def test_build_aqp1_negative_exact_source_outcome_packet() -> None:
    payload = mod.build_payload(as_of_date="2026-04-21")

    summary = payload["summary"]
    rows = payload["rows"]

    assert summary["family"] == "aqp1"
    assert summary["row_count"] == 4
    assert summary["source_assay_context"] == "human_erythrocyte_pressure_induced_hemolysis"
    assert summary["source_endpoint"] == "hemolysis_at_200_mpa"
    assert summary["almost_unaffected_candidate_count"] == 2
    assert summary["primary_negative_probe_candidate"] == "sodium nitroprusside"
    assert summary["small_inhibitor_signal_candidate"] == "dimethyl sulfoxide"
    assert summary["source_pmid"] == "23123479"
    assert summary["direct_negative_quantitative_row_found_count"] == 0
    assert summary["authoritative_negative_apply_allowed_count"] == 0
    assert rows[0]["candidate_name"] == "sodium nitroprusside"
    assert rows[0]["hemolysis_outcome"] == "almost_unaffected_at_200_mpa"
    assert rows[0]["outcome_direction"] == "unchanged"
    assert rows[0]["direct_transporter_specific_quantitative_negative_row_found"] is False
    assert rows[3]["candidate_name"] == "dimethyl sulfoxide"
    assert rows[3]["outcome_direction"] == "increased"
    assert rows[3]["aqp1_interpretation"] == "exact_source_small_inhibitor_signal_not_negative_candidate"


def test_build_aqp1_negative_exact_source_outcome_packet_cli(tmp_path: Path) -> None:
    out_json = tmp_path / "aqp1_negative_exact_source_outcome.json"
    out_csv = tmp_path / "aqp1_negative_exact_source_outcome.csv"
    out_md = tmp_path / "aqp1_negative_exact_source_outcome.md"

    subprocess.run(
        [
            sys.executable,
            "tools/product/build_aqp1_negative_exact_source_outcome_packet.py",
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
    assert payload["summary"]["almost_unaffected_candidate_count"] == 2
    assert payload["summary"]["primary_negative_probe_candidate"] == "sodium nitroprusside"
    assert payload["summary"]["small_inhibitor_signal_candidate"] == "dimethyl sulfoxide"
    assert payload["summary"]["direct_negative_quantitative_row_found_count"] == 0
    assert out_csv.exists()
    assert out_md.exists()

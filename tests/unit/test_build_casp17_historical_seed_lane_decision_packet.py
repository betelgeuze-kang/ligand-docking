from __future__ import annotations

import csv
import json
from pathlib import Path

from tools.casp17 import build_casp17_historical_seed_lane_decision_packet as mod


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def test_lane_decision_separates_strict_blind_from_retrospective_rows(tmp_path: Path) -> None:
    chronology_json = tmp_path / "chronology.json"
    lane_dir = tmp_path / "lane"
    out_json = tmp_path / "lane.json"
    out_csv = tmp_path / "lane.csv"
    out_md = tmp_path / "LANE.md"
    _write_json(
        chronology_json,
        {
            "rows": [
                {
                    "target_id": "HIST_BLIND",
                    "benchmark_id": "hist_blind",
                    "scope": "monomer",
                    "chronology_authority_status": "chronology_candidate_before_native_review",
                    "blockers": "",
                },
                {
                    "target_id": "HIST_POST",
                    "benchmark_id": "hist_post",
                    "scope": "monomer",
                    "chronology_authority_status": "post_native_prediction_chronology_blocked",
                    "blockers": "prediction_not_before_authoritative_native_date",
                },
                {
                    "target_id": "HIST_AUTHORITY",
                    "benchmark_id": "hist_authority",
                    "scope": "complex",
                    "chronology_authority_status": "operator_authoritative_chronology_evidence_required",
                    "blockers": "native_authority_not_pass",
                },
            ]
        },
    )

    args = mod.parse_args(
        [
            "--authoritative-chronology-json",
            str(chronology_json),
            "--lane-dir",
            str(lane_dir),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ]
    )
    payload = mod.build_payload(args)
    mod.write_outputs(args, payload)

    assert payload["summary"]["lane_decision_status"] == "partial_strict_blind_candidates_with_replacements_required"
    assert payload["summary"]["seed_row_count"] == 3
    assert payload["summary"]["strict_blind_eligible_count"] == 1
    assert payload["summary"]["retrospective_calibration_review_count"] == 1
    assert payload["summary"]["authority_or_replacement_required_count"] == 1
    assert payload["summary"]["competitive_proof_allowed_count"] == 0
    assert payload["summary"]["identity_intake_allowed_count"] == 0
    assert payload["summary"]["sidechain_native_benchmark_allowed_count"] == 0
    assert payload["summary"]["strict_blind_replacement_required_count"] == 3

    rows = {row["target_id"]: row for row in payload["rows"]}
    assert rows["HIST_BLIND"]["lane_decision_status"] == "strict_blind_candidate_review"
    assert rows["HIST_BLIND"]["strict_blind_eligible"] is True
    assert rows["HIST_POST"]["lane_decision_status"] == "retrospective_no_template_review_only"
    assert rows["HIST_POST"]["retrospective_calibration_review_allowed"] is True
    assert rows["HIST_POST"]["competitive_proof_allowed"] is False
    assert rows["HIST_AUTHORITY"]["lane_decision_status"] == "strict_blind_replacement_or_authority_required"
    assert "native_authority_not_pass" in rows["HIST_AUTHORITY"]["blockers"]

    written_rows = _read_csv(out_csv)
    assert len(written_rows) == 3
    assert (lane_dir / "02_hist_post" / "LANE_DECISION.md").exists()
    assert "Claim Boundary" in out_md.read_text(encoding="utf-8")


def test_lane_decision_reports_missing_input(tmp_path: Path) -> None:
    payload = mod.build_payload(
        mod.parse_args(
            [
                "--authoritative-chronology-json",
                str(tmp_path / "missing_chronology.json"),
                "--lane-dir",
                str(tmp_path / "lane"),
            ]
        )
    )

    assert payload["summary"]["lane_decision_status"] == "blocked_missing_input"
    assert "authoritative_chronology_json_missing" in payload["summary"]["input_blockers"]

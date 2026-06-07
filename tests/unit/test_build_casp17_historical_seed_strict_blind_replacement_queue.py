from __future__ import annotations

import csv
import json
from pathlib import Path

from tools.casp17 import build_casp17_historical_seed_strict_blind_replacement_queue as mod


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_csv(path: Path, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def test_strict_blind_replacement_queue_expands_lane_decision_to_scaffold_slots(tmp_path: Path) -> None:
    lane_json = tmp_path / "lane.json"
    scaffold_csv = tmp_path / "scaffold.csv"
    queue_dir = tmp_path / "queue"
    out_json = tmp_path / "queue.json"
    out_csv = tmp_path / "queue.csv"
    out_md = tmp_path / "QUEUE.md"
    _write_json(
        lane_json,
        {
            "summary": {
                "lane_decision_status": "strict_blind_replacement_required",
                "seed_row_count": 17,
                "strict_blind_eligible_count": 0,
                "retrospective_calibration_review_count": 10,
                "authority_or_replacement_required_count": 7,
                "competitive_proof_allowed_count": 0,
            }
        },
    )
    _write_csv(
        scaffold_csv,
        [
            {
                "row_rank": "1",
                "benchmark_id": "hist_REQUIRED_MONOMER_001",
                "target_id": "REQUIRED_MONOMER_001",
                "scope": "monomer",
                "metric_profile": "TM,GDT_TS,CA_lDDT",
            },
            {
                "row_rank": "2",
                "benchmark_id": "hist_REQUIRED_COMPLEX_001",
                "target_id": "REQUIRED_COMPLEX_001",
                "scope": "complex",
                "metric_profile": "TM,DockQ,IPS",
            },
        ],
        ["row_rank", "benchmark_id", "target_id", "scope", "metric_profile"],
    )

    args = mod.parse_args(
        [
            "--lane-decision-json",
            str(lane_json),
            "--benchmark-scaffold-csv",
            str(scaffold_csv),
            "--queue-dir",
            str(queue_dir),
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

    assert payload["summary"]["strict_blind_replacement_queue_status"] == "strict_blind_replacement_queue_open"
    assert payload["summary"]["scaffold_slot_count"] == 2
    assert payload["summary"]["monomer_slot_count"] == 1
    assert payload["summary"]["complex_slot_count"] == 1
    assert payload["summary"]["strict_blind_replacement_required_count"] == 2
    assert payload["summary"]["competitive_proof_allowed_slot_count"] == 0
    assert payload["summary"]["current_seed_count"] == 17
    assert payload["summary"]["current_seed_retrospective_count"] == 10
    assert payload["summary"]["current_seed_authority_required_count"] == 7
    assert payload["summary"]["requirement_field_count"] == 32

    rows = payload["rows"]
    assert rows[0]["required_benchmark_id"] == "hist_REQUIRED_MONOMER_001"
    assert rows[0]["requirement_field_count"] == 16
    assert "strict_blind_replacement_identity_required" in rows[0]["blockers"]

    requirements = _read_csv(queue_dir / "01_hist_required_monomer_001" / "strict_blind_replacement_requirements.csv")
    assert len(requirements) == 16
    by_field = {row["field_name"]: row for row in requirements}
    assert by_field["prediction_pdb"]["required_policy"] == "existing_coordinate_valid_pdb"
    assert by_field["prediction_generated_before_native_release"]["required_policy"] == "operator_confirmed_true"
    assert by_field["public_template_or_native_used_for_prediction"]["required_policy"] == "operator_confirmed_false"
    assert (queue_dir / "02_hist_required_complex_001" / "REPLACEMENT_REQUIREMENTS.md").exists()
    assert "Claim Boundary" in out_md.read_text(encoding="utf-8")


def test_strict_blind_replacement_queue_reports_missing_inputs(tmp_path: Path) -> None:
    payload = mod.build_payload(
        mod.parse_args(
            [
                "--lane-decision-json",
                str(tmp_path / "missing_lane.json"),
                "--benchmark-scaffold-csv",
                str(tmp_path / "missing_scaffold.csv"),
                "--queue-dir",
                str(tmp_path / "queue"),
            ]
        )
    )

    assert payload["summary"]["strict_blind_replacement_queue_status"] == "blocked_missing_input"
    assert "lane_decision_json_missing" in payload["summary"]["input_blockers"]
    assert "benchmark_scaffold_csv_missing" in payload["summary"]["input_blockers"]

from __future__ import annotations

import csv
import json
from pathlib import Path

from tools.casp17 import build_casp17_historical_seed_clearance_execution_board as mod


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def test_clearance_execution_board_ranks_no_leak_only_row_first(tmp_path: Path) -> None:
    fill_json = tmp_path / "fill.json"
    no_leak_json = tmp_path / "no_leak.json"
    ablation_json = tmp_path / "ablation.json"
    _write_json(
        fill_json,
        {
            "rows": [
                {
                    "row_rank": 1,
                    "target_id": "HIST_BBA5",
                    "benchmark_id": "hist_seed_bba5",
                    "scope": "monomer",
                    "field_candidate_csv": "casp17/fill/bba5.csv",
                    "operator_required_field_count": 10,
                    "proposed_field_count": 6,
                    "calibration_candidate_count": 6,
                    "ablation_candidate_count": 0,
                    "blocked_field_count": 1,
                },
                {
                    "row_rank": 2,
                    "target_id": "HIST_CHIGNOLIN",
                    "benchmark_id": "hist_seed_chignolin",
                    "scope": "monomer",
                    "field_candidate_csv": "casp17/fill/chignolin.csv",
                    "operator_required_field_count": 10,
                    "proposed_field_count": 7,
                    "calibration_candidate_count": 6,
                    "ablation_candidate_count": 1,
                    "blocked_field_count": 0,
                },
            ],
        },
    )
    _write_json(
        no_leak_json,
        {
            "rows": [
                {"target_id": "HIST_BBA5", "repair_csv": "casp17/no_leak/bba5.csv"},
                {"target_id": "HIST_CHIGNOLIN", "repair_csv": "casp17/no_leak/chignolin.csv"},
            ]
        },
    )
    _write_json(
        ablation_json,
        {
            "rows": [
                {"target_id": "HIST_BBA5", "repair_csv": "casp17/ablation/bba5.csv"},
                {"target_id": "HIST_CHIGNOLIN", "repair_csv": "casp17/ablation/chignolin.csv"},
            ]
        },
    )
    args = mod.parse_args(
        [
            "--fill-candidates-json",
            str(fill_json),
            "--no-leak-repair-json",
            str(no_leak_json),
            "--ablation-repair-json",
            str(ablation_json),
            "--board-dir",
            str(tmp_path / "board"),
            "--out-json",
            str(tmp_path / "board.json"),
            "--out-csv",
            str(tmp_path / "board.csv"),
            "--out-md",
            str(tmp_path / "board.md"),
        ]
    )

    payload = mod.build_payload(args)
    mod.write_outputs(args, payload)

    assert payload["summary"]["execution_board_status"] == "first_row_operator_no_leak_only"
    assert payload["summary"]["seed_row_count"] == 2
    assert payload["summary"]["operator_no_leak_only_row_count"] == 1
    assert payload["summary"]["ablation_repair_required_row_count"] == 1
    assert payload["summary"]["first_execution_target_id"] == "HIST_CHIGNOLIN"
    assert payload["summary"]["first_execution_status"] == "operator_no_leak_only"
    assert payload["rows"][0]["execution_rank"] == 1
    assert payload["rows"][0]["target_id"] == "HIST_CHIGNOLIN"
    assert payload["rows"][1]["execution_status"] == "ablation_repair_then_operator_no_leak"
    assert "real_ablation_layer_required" in payload["rows"][1]["blockers"]

    csv_rows = _read_csv(tmp_path / "board.csv")
    assert csv_rows[0]["target_id"] == "HIST_CHIGNOLIN"
    assert (tmp_path / "board" / "02_hist_chignolin" / "ACTION.md").exists()
    assert "first execution target: `HIST_CHIGNOLIN`" in (tmp_path / "board.md").read_text(encoding="utf-8")

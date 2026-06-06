from __future__ import annotations

import json
from pathlib import Path

from tools.casp17 import build_casp17_historical_winner_normalized_unlock_plan as mod


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _args(tmp_path: Path) -> list[str]:
    return [
        "--bands-json",
        str(tmp_path / "bands.json"),
        "--metric-surface-contract-json",
        str(tmp_path / "metric.json"),
        "--sidechain-native-benchmark-json",
        str(tmp_path / "sidechain.json"),
        "--source-request-closure-board-json",
        str(tmp_path / "source_request.json"),
        "--batch-closure-runway-json",
        str(tmp_path / "batch.json"),
        "--official-archive-baseline-json",
        str(tmp_path / "official.json"),
        "--out-json",
        str(tmp_path / "unlock.json"),
        "--out-csv",
        str(tmp_path / "unlock.csv"),
        "--out-md",
        str(tmp_path / "unlock.md"),
    ]


def _write_blocked_inputs(tmp_path: Path) -> None:
    _write_json(
        tmp_path / "bands.json",
        {
            "summary": {
                "historical_winner_normalized_bands_status": "blocked_strict_blind_metrics_missing",
                "band_count": 5,
                "top5_or_better_count": 0,
                "blocked_band_count": 5,
                "first_blocker": "strict_blind_historical_metric_surface_missing",
                "first_next_action": "score no-leak rows",
            }
        },
    )
    _write_json(
        tmp_path / "metric.json",
        {
            "summary": {
                "ready_slot_count": 0,
                "strict_blind_slot_count": 40,
                "ready_metric_row_count": 0,
                "metric_surface_row_count": 440,
                "next_action": "fill strict-blind evidence",
            }
        },
    )
    _write_json(
        tmp_path / "sidechain.json",
        {
            "summary": {
                "pass_count": 0,
                "benchmark_count": 40,
                "first_open_next_action": "place cleared prediction/native PDBs",
            }
        },
    )
    _write_json(
        tmp_path / "source_request.json",
        {
            "summary": {
                "ready_stage_count": 0,
                "blocked_stage_count": 9,
                "stage_count": 9,
                "first_blocker": "prediction_not_before_native",
                "next_action": "attach pre-native source",
            }
        },
    )
    _write_json(
        tmp_path / "batch.json",
        {
            "summary": {
                "ready_slot_count": 0,
                "blocked_slot_count": 40,
                "slot_count": 40,
                "first_blocker": "internal_prediction_source_gate",
                "first_next_action": "set internal source",
            }
        },
    )
    _write_json(
        tmp_path / "official.json",
        {"summary": {"baseline_candidate_count": 24, "competitive_proof_eligible_count": 0}},
    )


def test_winner_normalized_unlock_plan_orders_first_strict_blind_source_blocker(tmp_path: Path) -> None:
    _write_blocked_inputs(tmp_path)

    args = mod.parse_args(_args(tmp_path))
    payload = mod.build_payload(args)
    mod.write_outputs(args, payload)
    rows = {row["action_id"]: row for row in payload["rows"]}

    assert payload["summary"]["historical_winner_normalized_unlock_plan_status"] == (
        "awaiting_historical_winner_normalized_unlocks"
    )
    assert payload["summary"]["action_count"] == 6
    assert payload["summary"]["ready_action_count"] == 1
    assert payload["summary"]["blocked_action_count"] == 5
    assert payload["summary"]["first_blocked_action_id"] == "close_first_source_request"
    assert payload["summary"]["first_blocker"] == "prediction_not_before_native"
    assert rows["preserve_official_archive_as_baseline"]["action_status"] == "unlock_ready"
    assert rows["score_winner_normalized_bands"]["blocker"] == "strict_blind_historical_metric_surface_missing"
    assert (tmp_path / "unlock.md").is_file()


def test_winner_normalized_unlock_plan_ready_when_all_gates_closed(tmp_path: Path) -> None:
    _write_json(
        tmp_path / "bands.json",
        {
            "summary": {
                "historical_winner_normalized_bands_status": "historical_winner_normalized_bands_ready",
                "band_count": 5,
                "top5_or_better_count": 5,
                "blocked_band_count": 0,
            }
        },
    )
    _write_json(
        tmp_path / "metric.json",
        {"summary": {"ready_slot_count": 40, "strict_blind_slot_count": 40, "ready_metric_row_count": 440, "metric_surface_row_count": 440}},
    )
    _write_json(tmp_path / "sidechain.json", {"summary": {"pass_count": 40, "benchmark_count": 40}})
    _write_json(tmp_path / "source_request.json", {"summary": {"ready_stage_count": 9, "blocked_stage_count": 0, "stage_count": 9}})
    _write_json(tmp_path / "batch.json", {"summary": {"ready_slot_count": 40, "blocked_slot_count": 0, "slot_count": 40}})
    _write_json(tmp_path / "official.json", {"summary": {"baseline_candidate_count": 24, "competitive_proof_eligible_count": 0}})

    payload = mod.build_payload(mod.parse_args(_args(tmp_path)))

    assert payload["summary"]["historical_winner_normalized_unlock_plan_status"] == (
        "historical_winner_normalized_unlock_ready"
    )
    assert payload["summary"]["ready_action_count"] == 6
    assert payload["summary"]["blocked_action_count"] == 0
    assert {row["action_status"] for row in payload["rows"]} == {"unlock_ready"}


def test_winner_normalized_unlock_plan_blocks_missing_inputs(tmp_path: Path) -> None:
    payload = mod.build_payload(mod.parse_args(_args(tmp_path)))

    assert payload["summary"]["historical_winner_normalized_unlock_plan_status"] == "blocked_missing_inputs"
    assert "bands_json_missing" in payload["summary"]["input_blockers"]
    assert payload["rows"] == []

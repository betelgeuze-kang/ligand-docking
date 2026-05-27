from __future__ import annotations

import csv
import json
from pathlib import Path

from tools import apply_casp17_historical_seed_current_target_prefill as mod


FIELDS = ["benchmark_id", "target_id", "current_casp17_target", "notes"]


def _write_csv(path: Path, rows: list[dict[str, str]], fieldnames: list[str] = FIELDS) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _args(tmp_path: Path, operator_csv: Path, seed_csv: Path, current_json: Path, mode: str) -> list[str]:
    return [
        "--operator-clearance-csv",
        str(operator_csv),
        "--seed-manifest-csv",
        str(seed_csv),
        "--current-target-json",
        str(current_json),
        "--mode",
        mode,
        "--out-json",
        str(tmp_path / "prefill.json"),
        "--out-csv",
        str(tmp_path / "prefill.csv"),
        "--out-md",
        str(tmp_path / "PREFILL.md"),
    ]


def test_current_target_prefill_dry_run_does_not_mutate_operator_csv(tmp_path: Path) -> None:
    operator_csv = tmp_path / "operator.csv"
    seed_csv = tmp_path / "seed.csv"
    current_json = tmp_path / "current_targets.json"
    _write_csv(
        operator_csv,
        [
            {"benchmark_id": "hist_a", "target_id": "HIST_A", "current_casp17_target": "REQUIRED_FALSE_CONFIRMATION", "notes": ""},
            {"benchmark_id": "hist_b", "target_id": "HIST_B", "current_casp17_target": "false", "notes": ""},
            {"benchmark_id": "hist_bad", "target_id": "T1331", "current_casp17_target": "REQUIRED_FALSE_CONFIRMATION", "notes": ""},
        ],
    )
    _write_csv(
        seed_csv,
        [
            {"benchmark_id": "hist_a", "target_id": "HIST_A", "current_casp17_target": "false", "notes": ""},
            {"benchmark_id": "hist_b", "target_id": "HIST_B", "current_casp17_target": "false", "notes": ""},
            {"benchmark_id": "hist_bad", "target_id": "T1331", "current_casp17_target": "false", "notes": ""},
        ],
    )
    _write_json(current_json, {"rows": [{"target_id": "T1331"}]})

    args = mod.parse_args(_args(tmp_path, operator_csv, seed_csv, current_json, "dry_run"))
    payload = mod.build_payload(args)
    mod.write_outputs(args, payload)

    assert payload["summary"]["prefill_status"] == "blocked"
    assert payload["summary"]["ready_to_apply_count"] == 1
    assert payload["summary"]["already_safe_false_count"] == 1
    assert payload["summary"]["blocked_count"] == 1
    assert payload["summary"]["current_target_collision_count"] == 1
    assert _read_csv(operator_csv)[0]["current_casp17_target"] == "REQUIRED_FALSE_CONFIRMATION"


def test_current_target_prefill_apply_updates_only_safe_hist_rows(tmp_path: Path) -> None:
    operator_csv = tmp_path / "operator.csv"
    seed_csv = tmp_path / "seed.csv"
    current_json = tmp_path / "current_targets.json"
    _write_csv(
        operator_csv,
        [
            {"benchmark_id": "hist_a", "target_id": "HIST_A", "current_casp17_target": "REQUIRED_FALSE_CONFIRMATION", "notes": ""},
            {"benchmark_id": "hist_b", "target_id": "HIST_B", "current_casp17_target": "false", "notes": ""},
        ],
    )
    _write_csv(
        seed_csv,
        [
            {"benchmark_id": "hist_a", "target_id": "HIST_A", "current_casp17_target": "false", "notes": ""},
            {"benchmark_id": "hist_b", "target_id": "HIST_B", "current_casp17_target": "false", "notes": ""},
        ],
    )
    _write_json(current_json, {"rows": [{"target_id": "T1331"}]})

    args = mod.parse_args(_args(tmp_path, operator_csv, seed_csv, current_json, "apply"))
    payload = mod.build_payload(args)
    mod.write_outputs(args, payload)

    updated = _read_csv(operator_csv)
    assert payload["summary"]["prefill_status"] == "applied"
    assert payload["summary"]["applied_count"] == 1
    assert payload["summary"]["already_safe_false_count"] == 1
    assert payload["summary"]["remaining_open_current_target_count"] == 0
    assert [row["current_casp17_target"] for row in updated] == ["false", "false"]


def test_current_target_prefill_blocks_seed_manifest_without_false_value(tmp_path: Path) -> None:
    operator_csv = tmp_path / "operator.csv"
    seed_csv = tmp_path / "seed.csv"
    current_json = tmp_path / "current_targets.json"
    _write_csv(
        operator_csv,
        [
            {"benchmark_id": "hist_a", "target_id": "HIST_A", "current_casp17_target": "REQUIRED_FALSE_CONFIRMATION", "notes": ""},
        ],
    )
    _write_csv(
        seed_csv,
        [
            {"benchmark_id": "hist_a", "target_id": "HIST_A", "current_casp17_target": "", "notes": ""},
        ],
    )
    _write_json(current_json, {"rows": []})

    args = mod.parse_args(_args(tmp_path, operator_csv, seed_csv, current_json, "apply"))
    payload = mod.build_payload(args)

    assert payload["summary"]["prefill_status"] == "blocked"
    assert payload["summary"]["blocked_count"] == 1
    assert payload["rows"][0]["blockers"] == "seed_manifest_current_target_false_required"

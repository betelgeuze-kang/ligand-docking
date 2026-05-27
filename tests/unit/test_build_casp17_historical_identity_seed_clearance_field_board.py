from __future__ import annotations

import csv
import json
from pathlib import Path

from tools import build_casp17_historical_identity_seed_clearance_field_board as mod


FIELDS = [
    "seed_rank",
    "batch_slot",
    "benchmark_id",
    "target_id",
    "scope",
    "prediction_pdb",
    "native_pdb",
    "no_leak_evidence_ref",
    "leakage_clearance",
    "operator_clearance",
    "operator",
    "prediction_created_at",
    "native_release_date",
    "prediction_generated_before_native_release",
    "public_template_or_native_used_for_prediction",
    "other_team_model_used",
    "post_release_information_used",
    "current_casp17_target",
    "selected_model_rank",
    "best_model_rank",
    "selected_native_metric",
    "best_native_metric",
    "selected_score",
    "best_score",
    "ablation_manifest_ref",
    "notes",
]
MANIFEST_FIELDS = [
    "benchmark_id",
    "target_id",
    "scope",
    "split",
    "prediction_pdb",
    "native_pdb",
    "leakage_clearance",
    "prediction_method",
    "prediction_created_at",
    "native_release_date",
    "prediction_generated_before_native_release",
    "public_template_or_native_used_for_prediction",
    "other_team_model_used",
    "post_release_information_used",
    "current_casp17_target",
    "operator_clearance",
]


def _write_csv(path: Path, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _pdb(path: Path, x: float) -> str:
    path.write_text(f"ATOM      1  CA  ALA A   1      {x:6.3f}   0.000   0.000\n", encoding="utf-8")
    return str(path)


def _operator_row(tmp_path: Path, **overrides: str) -> dict[str, str]:
    pred = _pdb(tmp_path / "prediction.pdb", 0.0)
    native = _pdb(tmp_path / "native.pdb", 1.0)
    row = {
        "seed_rank": "1",
        "batch_slot": "1",
        "benchmark_id": "hist_seed_demo",
        "target_id": "HIST_DEMO",
        "scope": "monomer",
        "prediction_pdb": pred,
        "native_pdb": native,
        "no_leak_evidence_ref": "",
        "leakage_clearance": "REQUIRED_NO_LEAK_CLEARANCE",
        "operator_clearance": "REQUIRED_OPERATOR_CLEARANCE",
        "operator": "REQUIRED_OPERATOR_ID",
        "prediction_created_at": "YYYY-MM-DD",
        "native_release_date": "YYYY-MM-DD",
        "prediction_generated_before_native_release": "REQUIRED_TRUE_CONFIRMATION",
        "public_template_or_native_used_for_prediction": "REQUIRED_FALSE_CONFIRMATION",
        "other_team_model_used": "REQUIRED_FALSE_CONFIRMATION",
        "post_release_information_used": "REQUIRED_FALSE_CONFIRMATION",
        "current_casp17_target": "REQUIRED_FALSE_CONFIRMATION",
        "selected_model_rank": "REQUIRED_1_TO_5",
        "best_model_rank": "REQUIRED_1_TO_5",
        "selected_native_metric": "REQUIRED_NATIVE_METRIC",
        "best_native_metric": "REQUIRED_ORACLE_METRIC",
        "selected_score": "REQUIRED_INTERNAL_SCORE",
        "best_score": "REQUIRED_ORACLE_SCORE",
        "ablation_manifest_ref": "REQUIRED_ABLATION_MANIFEST_REF",
        "notes": "",
    }
    row.update(overrides)
    return row


def _manifest_row(row: dict[str, str]) -> dict[str, str]:
    return {
        "benchmark_id": row["benchmark_id"],
        "target_id": row["target_id"],
        "scope": row["scope"],
        "split": "historical_seed",
        "prediction_pdb": row["prediction_pdb"],
        "native_pdb": row["native_pdb"],
        "leakage_clearance": "",
        "prediction_method": "internal_physics_seed_inventory",
        "prediction_created_at": "",
        "native_release_date": "",
        "prediction_generated_before_native_release": "",
        "public_template_or_native_used_for_prediction": "",
        "other_team_model_used": "",
        "post_release_information_used": "",
        "current_casp17_target": "false",
        "operator_clearance": "",
    }


def _args(tmp_path: Path, operator_csv: Path, seed_csv: Path) -> list[str]:
    return [
        "--operator-clearance-csv",
        str(operator_csv),
        "--seed-manifest-csv",
        str(seed_csv),
        "--out-json",
        str(tmp_path / "board.json"),
        "--out-csv",
        str(tmp_path / "board.csv"),
        "--out-md",
        str(tmp_path / "BOARD.md"),
    ]


def test_seed_clearance_field_board_separates_core_pass_from_operator_fields(tmp_path: Path) -> None:
    row = _operator_row(tmp_path)
    operator_csv = tmp_path / "operator.csv"
    seed_csv = tmp_path / "seed.csv"
    _write_csv(operator_csv, [row], FIELDS)
    _write_csv(seed_csv, [_manifest_row(row)], MANIFEST_FIELDS)

    args = mod.parse_args(_args(tmp_path, operator_csv, seed_csv))
    payload = mod.build_payload(args)
    mod.write_outputs(args, payload)

    assert payload["summary"]["field_board_status"] == "operator_field_fill_required"
    assert payload["summary"]["core_file_pass_count"] == 1
    assert payload["summary"]["no_leak_open_field_count"] == 11
    assert payload["summary"]["calibration_open_field_count"] == 6
    assert payload["summary"]["ablation_open_field_count"] == 1
    assert payload["rows"][0]["field_board_status"] == "operator_field_fill_required"
    assert payload["rows"][0]["prediction_atom_count"] == 1
    assert payload["rows"][0]["first_open_field"] == "no_leak_evidence_ref"
    assert _read_json(tmp_path / "board.json")["summary"]["seed_row_count"] == 1


def test_seed_clearance_field_board_accepts_filled_seed_row(tmp_path: Path) -> None:
    evidence = tmp_path / "no_leak.md"
    ablation = tmp_path / "ablation.csv"
    evidence.write_text("local no leak evidence\n", encoding="utf-8")
    ablation.write_text("layer,path\n", encoding="utf-8")
    row = _operator_row(
        tmp_path,
        no_leak_evidence_ref=str(evidence),
        leakage_clearance="no_leak",
        operator_clearance="ready_for_row_fill",
        operator="codex",
        prediction_created_at="2026-02-19",
        native_release_date="2026-02-20",
        prediction_generated_before_native_release="true",
        public_template_or_native_used_for_prediction="false",
        other_team_model_used="false",
        post_release_information_used="false",
        current_casp17_target="false",
        selected_model_rank="1",
        best_model_rank="1",
        selected_native_metric="0.75",
        best_native_metric="0.80",
        selected_score="0.5",
        best_score="0.6",
        ablation_manifest_ref=str(ablation),
    )
    operator_csv = tmp_path / "operator.csv"
    seed_csv = tmp_path / "seed.csv"
    _write_csv(operator_csv, [row], FIELDS)
    _write_csv(seed_csv, [_manifest_row(row)], MANIFEST_FIELDS)

    args = mod.parse_args(_args(tmp_path, operator_csv, seed_csv))
    payload = mod.build_payload(args)

    assert payload["summary"]["field_board_status"] == "ready_for_cleared_seed_manifest"
    assert payload["summary"]["ready_for_cleared_seed_manifest_count"] == 1
    assert payload["summary"]["total_open_field_count"] == 0
    assert payload["rows"][0]["field_board_status"] == "ready_for_cleared_seed_manifest"


def test_seed_clearance_field_board_blocks_missing_core_file(tmp_path: Path) -> None:
    row = _operator_row(tmp_path, prediction_pdb=str(tmp_path / "missing_prediction.pdb"))
    operator_csv = tmp_path / "operator.csv"
    seed_csv = tmp_path / "seed.csv"
    _write_csv(operator_csv, [row], FIELDS)
    _write_csv(seed_csv, [_manifest_row(row)], MANIFEST_FIELDS)

    args = mod.parse_args(_args(tmp_path, operator_csv, seed_csv))
    payload = mod.build_payload(args)

    assert payload["summary"]["field_board_status"] == "blocked_core_files"
    assert payload["summary"]["blocked_core_file_count"] == 1
    assert payload["rows"][0]["core_file_status"] == "blocked_core_files"
    assert "prediction_pdb_missing" in payload["rows"][0]["open_fields"]

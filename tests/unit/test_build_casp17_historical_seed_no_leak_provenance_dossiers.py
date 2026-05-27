from __future__ import annotations

import csv
import json
from pathlib import Path

from tools import build_casp17_historical_seed_no_leak_provenance_dossiers as mod


FIELDS = [
    "seed_rank",
    "batch_slot",
    "benchmark_id",
    "target_id",
    "scope",
    "prediction_pdb",
    "native_pdb",
    "prediction_method",
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
]


def _write_csv(path: Path, rows: list[dict[str, str]], fieldnames: list[str] = FIELDS) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _pdb(path: Path) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "ATOM      1  CA  ALA A   1       0.000   0.000   0.000  1.00 20.00           C\n",
        encoding="utf-8",
    )
    return str(path)


def _base_row(tmp_path: Path) -> dict[str, str]:
    return {
        "seed_rank": "1",
        "batch_slot": "1",
        "benchmark_id": "hist_seed_bba5",
        "target_id": "HIST_BBA5",
        "scope": "monomer",
        "prediction_pdb": _pdb(tmp_path / "nightly" / "2026-02-19-run" / "prediction.pdb"),
        "native_pdb": _pdb(tmp_path / "native" / "bba5.pdb"),
        "prediction_method": "internal_physics_seed_inventory",
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
        "current_casp17_target": "false",
    }


def _args(tmp_path: Path, operator_csv: Path, seed_csv: Path) -> list[str]:
    return [
        "--operator-clearance-csv",
        str(operator_csv),
        "--seed-manifest-csv",
        str(seed_csv),
        "--dossier-dir",
        str(tmp_path / "dossiers"),
        "--out-json",
        str(tmp_path / "dossiers.json"),
        "--out-csv",
        str(tmp_path / "dossiers.csv"),
        "--out-md",
        str(tmp_path / "DOSSIERS.md"),
    ]


def test_no_leak_dossier_surfaces_operator_required_fields_without_clearing(tmp_path: Path) -> None:
    row = _base_row(tmp_path)
    operator_csv = tmp_path / "operator.csv"
    seed_csv = tmp_path / "seed.csv"
    _write_csv(operator_csv, [row])
    _write_csv(seed_csv, [row])

    args = mod.parse_args(_args(tmp_path, operator_csv, seed_csv))
    payload = mod.build_payload(args)
    mod.write_outputs(args, payload)

    assert payload["summary"]["no_leak_dossier_status"] == "operator_provenance_review_required"
    assert payload["summary"]["seed_row_count"] == 1
    assert payload["summary"]["dossier_count"] == 1
    assert payload["summary"]["core_input_pass_count"] == 1
    assert payload["summary"]["current_target_prefilled_false_count"] == 1
    assert payload["summary"]["ready_for_no_leak_clearance_count"] == 0
    assert payload["summary"]["operator_required_open_field_count"] == 10
    assert payload["summary"]["chronology_evidence_gap_count"] == 1
    assert payload["summary"]["negative_leakage_control_gap_count"] == 1
    assert payload["rows"][0]["dossier_status"] == "operator_provenance_review_required"
    assert payload["rows"][0]["current_target_safety_status"] == "prefilled_false_hist_prefix"
    assert payload["rows"][0]["prediction_path_date"] == "2026-02-19"
    assert "operator_no_leak_fields_required" in payload["rows"][0]["blockers"]
    assert "operator_chronology_evidence_required" in payload["rows"][0]["blockers"]
    assert "operator_negative_leakage_control_required" in payload["rows"][0]["blockers"]

    dossier_path = Path(payload["rows"][0]["dossier_md"])
    if not dossier_path.is_absolute():
        dossier_path = mod.ROOT / dossier_path
    assert dossier_path.exists()
    assert "do not clear leakage provenance" in json.loads((tmp_path / "dossiers.json").read_text(encoding="utf-8"))["summary"]["claim_boundary"]


def test_no_leak_dossier_blocks_current_target_risk(tmp_path: Path) -> None:
    row = _base_row(tmp_path)
    row["target_id"] = "H1354"
    row["current_casp17_target"] = "true"
    operator_csv = tmp_path / "operator.csv"
    seed_csv = tmp_path / "seed.csv"
    _write_csv(operator_csv, [row])
    _write_csv(seed_csv, [row])

    payload = mod.build_payload(mod.parse_args(_args(tmp_path, operator_csv, seed_csv)))

    assert payload["summary"]["no_leak_dossier_status"] == "blocked_current_target_risk"
    assert payload["summary"]["blocked_current_target_risk_count"] == 1
    assert payload["rows"][0]["dossier_status"] == "blocked_current_target_risk"
    assert "current_target_or_identity_risk_requires_operator_review" in payload["rows"][0]["blockers"]


def test_no_leak_dossier_blocks_missing_core_inputs(tmp_path: Path) -> None:
    row = _base_row(tmp_path)
    row["prediction_pdb"] = str(tmp_path / "missing.pdb")
    operator_csv = tmp_path / "operator.csv"
    seed_csv = tmp_path / "seed.csv"
    _write_csv(operator_csv, [row])
    _write_csv(seed_csv, [row])

    payload = mod.build_payload(mod.parse_args(_args(tmp_path, operator_csv, seed_csv)))

    assert payload["summary"]["no_leak_dossier_status"] == "blocked_core_provenance_inputs"
    assert payload["summary"]["blocked_core_provenance_input_count"] == 1
    assert payload["rows"][0]["dossier_status"] == "blocked_core_provenance_inputs"
    assert "prediction_pdb_missing_or_invalid" in payload["rows"][0]["blockers"]

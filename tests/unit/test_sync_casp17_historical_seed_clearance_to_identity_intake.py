from __future__ import annotations

import csv
import json
from pathlib import Path

from tools import sync_casp17_historical_seed_clearance_to_identity_intake as mod


SEED_FIELDS = [
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
INTAKE_FIELDS = [
    "dropzone_id",
    "operator_priority",
    "row_rank",
    "scope",
    "current_benchmark_id",
    "current_target_id",
    "proposed_benchmark_id",
    "proposed_target_id",
    "evidence_ref",
    "operator_clearance",
]


def _write_csv(path: Path, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _intake(scope: str = "monomer") -> dict[str, str]:
    suffix = "MONOMER_001" if scope == "monomer" else "COMPLEX_001"
    return {
        "dropzone_id": f"priority_001_REQUIRED_{suffix}",
        "operator_priority": "1",
        "row_rank": "1",
        "scope": scope,
        "current_benchmark_id": f"hist_REQUIRED_{suffix}",
        "current_target_id": f"REQUIRED_{suffix}",
        "proposed_benchmark_id": "",
        "proposed_target_id": "",
        "evidence_ref": "",
        "operator_clearance": "",
    }


def _seed(tmp_path: Path, scope: str = "monomer", **overrides: str) -> dict[str, str]:
    prediction = tmp_path / f"{scope}_prediction.pdb"
    native = tmp_path / f"{scope}_native.pdb"
    prediction.write_text("ATOM      1  CA  ALA A   1       0.000   0.000   0.000\n", encoding="utf-8")
    native.write_text("ATOM      1  CA  ALA A   1       1.000   0.000   0.000\n", encoding="utf-8")
    row = {
        "benchmark_id": f"hist_{scope}_001",
        "target_id": f"{scope.upper()}_001",
        "scope": scope,
        "split": "historical_seed_cleared",
        "prediction_pdb": str(prediction),
        "native_pdb": str(native),
        "leakage_clearance": "no_leak",
        "prediction_method": "internal_physics_historical_fixture",
        "prediction_created_at": "2024-01-01",
        "native_release_date": "2024-02-01",
        "prediction_generated_before_native_release": "true",
        "public_template_or_native_used_for_prediction": "false",
        "other_team_model_used": "false",
        "post_release_information_used": "false",
        "current_casp17_target": "false",
        "operator_clearance": "ready_for_row_fill",
    }
    row.update(overrides)
    return row


def _args(tmp_path: Path, seed_csv: Path, intake_csv: Path, *extra: str) -> list[str]:
    return [
        "--cleared-seed-manifest-csv",
        str(seed_csv),
        "--identity-intake-csv",
        str(intake_csv),
        "--out-json",
        str(tmp_path / "sync.json"),
        "--out-csv",
        str(tmp_path / "sync.csv"),
        "--out-md",
        str(tmp_path / "SYNC.md"),
        *extra,
    ]


def test_seed_clearance_sync_waits_on_empty_cleared_manifest(tmp_path: Path) -> None:
    seed_csv = tmp_path / "seed.csv"
    intake_csv = tmp_path / "intake.csv"
    _write_csv(seed_csv, [], SEED_FIELDS)
    _write_csv(intake_csv, [_intake()], INTAKE_FIELDS)

    args = mod.parse_args(_args(tmp_path, seed_csv, intake_csv))
    payload = mod.build_payload(args)
    mod.write_outputs(args, payload)

    assert payload["summary"]["seed_to_identity_sync_status"] == "waiting_on_cleared_seed_manifest"
    assert payload["summary"]["ready_to_sync_count"] == 0
    assert payload["summary"]["waiting_intake_count"] == 1
    assert _read_csv(tmp_path / "sync.csv")[0]["sync_status"] == "waiting_on_cleared_seed"
    assert _read_json(tmp_path / "sync.json")["summary"]["intake_row_count"] == 1


def test_seed_clearance_sync_previews_matching_scope_seed(tmp_path: Path) -> None:
    seed_csv = tmp_path / "seed.csv"
    intake_csv = tmp_path / "intake.csv"
    _write_csv(seed_csv, [_seed(tmp_path)], SEED_FIELDS)
    _write_csv(intake_csv, [_intake()], INTAKE_FIELDS)

    args = mod.parse_args(_args(tmp_path, seed_csv, intake_csv))
    payload = mod.build_payload(args)

    row = payload["rows"][0]
    assert payload["summary"]["seed_to_identity_sync_status"] == "ready_to_sync"
    assert payload["summary"]["ready_to_sync_count"] == 1
    assert row["seed_benchmark_id"] == "hist_monomer_001"
    assert row["seed_target_id"] == "MONOMER_001"
    assert row["evidence_ref"].endswith("seed.csv")
    assert row["operator_clearance"] == "ready_for_row_fill"


def test_seed_clearance_sync_apply_updates_identity_intake(tmp_path: Path) -> None:
    seed_csv = tmp_path / "seed.csv"
    intake_csv = tmp_path / "intake.csv"
    _write_csv(seed_csv, [_seed(tmp_path)], SEED_FIELDS)
    _write_csv(intake_csv, [_intake()], INTAKE_FIELDS)

    args = mod.parse_args(_args(tmp_path, seed_csv, intake_csv, "--apply"))
    payload = mod.build_payload(args)
    mod.write_outputs(args, payload)

    assert payload["summary"]["seed_to_identity_sync_status"] == "applied"
    assert payload["summary"]["applied_count"] == 1
    updated = _read_csv(intake_csv)[0]
    assert updated["proposed_benchmark_id"] == "hist_monomer_001"
    assert updated["proposed_target_id"] == "MONOMER_001"
    assert updated["operator_clearance"] == "ready_for_row_fill"


def test_seed_clearance_sync_rejects_current_target_seed(tmp_path: Path) -> None:
    seed_csv = tmp_path / "seed.csv"
    intake_csv = tmp_path / "intake.csv"
    _write_csv(seed_csv, [_seed(tmp_path, current_casp17_target="true")], SEED_FIELDS)
    _write_csv(intake_csv, [_intake()], INTAKE_FIELDS)

    args = mod.parse_args(_args(tmp_path, seed_csv, intake_csv))
    payload = mod.build_payload(args)

    assert payload["summary"]["seed_to_identity_sync_status"] == "blocked_seed_rows"
    assert payload["summary"]["rejected_seed_row_count"] == 1
    assert "current_casp17_target_not_false" in payload["rejected_seed_rows"][0]["blockers"]
    assert payload["rows"][0]["sync_status"] == "waiting_on_cleared_seed"

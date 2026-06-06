import csv
import json
from pathlib import Path

from tools.casp17 import build_casp17_competitive_floor_target_identity_clearance_intake_staging_plan as mod


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_csv(path: Path, rows: list[dict[str, str]], fieldnames: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    names = fieldnames or list(rows[0])
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=names, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _intake_row(dropzone_id: str, scope: str, priority: str) -> dict[str, str]:
    return {
        "dropzone_id": dropzone_id,
        "operator_priority": priority,
        "row_rank": priority,
        "scope": scope,
        "current_benchmark_id": f"hist_REQUIRED_{scope.upper()}_{priority}",
        "current_target_id": f"REQUIRED_{scope.upper()}_{priority}",
        "proposed_benchmark_id": "",
        "proposed_target_id": "",
        "evidence_ref": "",
        "operator_clearance": "",
        "identity_status": "awaiting_identity",
        "missing_field_count": "4",
        "blockers": "proposed_benchmark_id_required,proposed_target_id_required",
        "file_actions_unlocked": "0",
        "readiness_gate_status": "awaiting_identity",
        "apply_identity_command": "python3 tools/run_casp17_competitive_floor_identity_unlock_round.py --apply-identity",
        "verify_command": "python3 tools/build_casp17_competitive_floor_execution_board.py",
        "next_action": "fill proposed_benchmark_id",
    }


def _manifest_row(target_id: str = "H9001", scope: str = "complex") -> dict[str, str]:
    return {
        "benchmark_id": f"hist_{target_id}_clearance_candidate",
        "target_id": target_id,
        "scope": scope,
        "split": "historical_candidate",
        "prediction_pdb": "runs/prediction.pdb",
        "native_pdb": "runs/native.pdb",
        "leakage_clearance": "no_leak",
        "prediction_method": "internal_prediction",
        "prediction_created_at": "2026-01-01",
        "native_release_date": "2026-02-01",
        "prediction_generated_before_native_release": "true",
        "public_template_or_native_used_for_prediction": "false",
        "other_team_model_used": "false",
        "post_release_information_used": "false",
        "current_casp17_target": "false",
        "operator_clearance": "cleared",
    }


def _args(
    tmp_path: Path,
    manifest_csv: Path,
    promotion_json: Path,
    intake_csv: Path,
    current_csv: Path,
) -> list[str]:
    return [
        "--promoted-manifest-csv",
        str(manifest_csv),
        "--promotion-plan-json",
        str(promotion_json),
        "--identity-intake-csv",
        str(intake_csv),
        "--current-target-csv",
        str(current_csv),
        "--out-candidate-intake-csv",
        str(tmp_path / "candidate_intake.csv"),
        "--out-json",
        str(tmp_path / "staging.json"),
        "--out-csv",
        str(tmp_path / "staging.csv"),
        "--out-md",
        str(tmp_path / "STAGING.md"),
    ]


def test_intake_staging_plan_maps_promoted_complex_to_open_complex_slot(tmp_path):
    manifest_csv = tmp_path / "promoted.csv"
    promotion_json = tmp_path / "promotion.json"
    intake_csv = tmp_path / "intake.csv"
    current_csv = tmp_path / "current.csv"
    _write_csv(manifest_csv, [_manifest_row()])
    _write_json(promotion_json, {"summary": {"clearance_promotion_status": "ready_for_operator_manifest_import"}})
    _write_csv(
        intake_csv,
        [
            _intake_row("priority_001_REQUIRED_MONOMER_001", "monomer", "1"),
            _intake_row("priority_011_REQUIRED_COMPLEX_001", "complex", "11"),
        ],
    )
    _write_csv(current_csv, [{"target_id": "T1331"}])

    args = mod.parse_args(_args(tmp_path, manifest_csv, promotion_json, intake_csv, current_csv))
    payload = mod.build_payload(args)
    mod.write_outputs(args, payload)

    assert payload["summary"]["clearance_intake_staging_status"] == "ready_for_operator_intake_review"
    assert payload["summary"]["staged_identity_count"] == 1
    assert payload["summary"]["blocked_assignment_count"] == 0
    assert payload["rows"][0]["dropzone_id"] == "priority_011_REQUIRED_COMPLEX_001"
    assert payload["rows"][0]["staging_status"] == "staged_for_operator_review"
    candidate_rows = {row["dropzone_id"]: row for row in _read_csv(tmp_path / "candidate_intake.csv")}
    assert candidate_rows["priority_011_REQUIRED_COMPLEX_001"]["proposed_target_id"] == "H9001"
    assert candidate_rows["priority_011_REQUIRED_COMPLEX_001"]["proposed_benchmark_id"] == "hist_H9001_clearance_candidate"
    assert "#H9001" in candidate_rows["priority_011_REQUIRED_COMPLEX_001"]["evidence_ref"]
    assert (tmp_path / "STAGING.md").is_file()


def test_intake_staging_plan_rejects_current_casp17_promoted_target(tmp_path):
    manifest_csv = tmp_path / "promoted.csv"
    promotion_json = tmp_path / "promotion.json"
    intake_csv = tmp_path / "intake.csv"
    current_csv = tmp_path / "current.csv"
    _write_csv(manifest_csv, [_manifest_row(target_id="H9001")])
    _write_json(promotion_json, {"summary": {"clearance_promotion_status": "ready_for_operator_manifest_import"}})
    _write_csv(intake_csv, [_intake_row("priority_011_REQUIRED_COMPLEX_001", "complex", "11")])
    _write_csv(current_csv, [{"target_id": "H9001"}])

    args = mod.parse_args(_args(tmp_path, manifest_csv, promotion_json, intake_csv, current_csv))
    payload = mod.build_payload(args)

    assert payload["summary"]["clearance_intake_staging_status"] == "blocked_assignments"
    assert payload["summary"]["staged_identity_count"] == 0
    assert payload["summary"]["blocked_assignment_count"] == 1
    assert payload["rows"][0]["staging_status"] == "blocked_manifest_row"
    assert "current_casp17_target_not_allowed" in payload["rows"][0]["blockers"]


def test_intake_staging_plan_waits_when_promoted_manifest_is_header_only(tmp_path):
    manifest_csv = tmp_path / "promoted.csv"
    promotion_json = tmp_path / "promotion.json"
    intake_csv = tmp_path / "intake.csv"
    current_csv = tmp_path / "current.csv"
    _write_csv(manifest_csv, [], fieldnames=mod.MANIFEST_COLUMNS)
    _write_json(promotion_json, {"summary": {"clearance_promotion_status": "blocked_by_audit"}})
    _write_csv(intake_csv, [_intake_row("priority_011_REQUIRED_COMPLEX_001", "complex", "11")])
    _write_csv(current_csv, [{"target_id": "T1331"}])

    args = mod.parse_args(_args(tmp_path, manifest_csv, promotion_json, intake_csv, current_csv))
    payload = mod.build_payload(args)

    assert payload["summary"]["clearance_intake_staging_status"] == "waiting_on_promoted_manifest"
    assert payload["summary"]["promoted_manifest_row_count"] == 0
    assert payload["summary"]["staged_identity_count"] == 0
    assert payload["summary"]["candidate_intake_row_count"] == 1

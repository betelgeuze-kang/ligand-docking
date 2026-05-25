import csv
import json
from pathlib import Path

from tools import sync_casp17_competitive_floor_target_identity_clearance_manifest_stub as mod


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


def _ready_provenance(target_id: str = "H1001") -> dict[str, str]:
    return {
        "benchmark_id": f"hist_{target_id}_clearance_candidate",
        "target_id": target_id,
        "scope": "complex",
        "split": "historical_candidate",
        "leakage_clearance": "no_leak",
        "prediction_method": "internal_prediction_from_clearance_queue",
        "prediction_created_at": "2026-01-01",
        "native_release_date": "2026-02-01",
        "prediction_generated_before_native_release": "true",
        "public_template_or_native_used_for_prediction": "false",
        "other_team_model_used": "false",
        "post_release_information_used": "false",
        "current_casp17_target": "false",
        "operator_clearance": "cleared",
        "operator": "operator-a",
        "evidence_ref": "local/no_leak/H1001.md",
        "notes": "reviewed",
    }


def _placeholder_manifest(target_id: str = "H1001") -> dict[str, str]:
    return {
        "benchmark_id": f"hist_{target_id}_clearance_candidate",
        "target_id": target_id,
        "scope": "complex",
        "split": "historical_candidate",
        "prediction_pdb": "runs/prediction.pdb",
        "native_pdb": "native/H1001_native.pdb",
        "leakage_clearance": "REQUIRED_NO_LEAK_CLEARANCE",
        "prediction_method": "internal_prediction_from_clearance_queue",
        "prediction_created_at": "YYYY-MM-DD",
        "native_release_date": "YYYY-MM-DD",
        "prediction_generated_before_native_release": "REQUIRED_TRUE_CONFIRMATION",
        "public_template_or_native_used_for_prediction": "REQUIRED_FALSE_CONFIRMATION",
        "other_team_model_used": "REQUIRED_FALSE_CONFIRMATION",
        "post_release_information_used": "REQUIRED_FALSE_CONFIRMATION",
        "current_casp17_target": "REQUIRED_FALSE_CONFIRMATION",
        "operator_clearance": "REQUIRED_OPERATOR_CLEARANCE",
    }


def _blocked_provenance(target_id: str = "H1001") -> dict[str, str]:
    row = _ready_provenance(target_id)
    row["leakage_clearance"] = "REQUIRED_NO_LEAK_CLEARANCE"
    row["prediction_created_at"] = "YYYY-MM-DD"
    return row


def _workorder_json(tmp_path: Path, provenance_csv: Path, manifest_csv: Path) -> Path:
    path = tmp_path / "workorder.json"
    _write_json(
        path,
        {
            "summary": {"clearance_workorder_status": "awaiting_native_or_provenance"},
            "rows": [
                {
                    "target_id": "H1001",
                    "provenance_template_csv": str(provenance_csv),
                    "manifest_stub_csv": str(manifest_csv),
                }
            ],
        },
    )
    return path


def _args(tmp_path: Path, workorder_json: Path, *extra: str) -> list[str]:
    return [
        "--workorder-json",
        str(workorder_json),
        "--out-json",
        str(tmp_path / "sync.json"),
        "--out-csv",
        str(tmp_path / "sync.csv"),
        "--out-md",
        str(tmp_path / "SYNC.md"),
        *extra,
    ]


def test_manifest_sync_reports_ready_to_sync_without_mutating_by_default(tmp_path):
    provenance_csv = tmp_path / "provenance_template.csv"
    manifest_csv = tmp_path / "manifest_stub.csv"
    _write_csv(provenance_csv, [_ready_provenance()])
    _write_csv(manifest_csv, [_placeholder_manifest()])
    workorder_json = _workorder_json(tmp_path, provenance_csv, manifest_csv)
    args = mod.parse_args(_args(tmp_path, workorder_json))

    payload = mod.build_payload(args)
    mod.write_outputs(args, payload)

    assert payload["summary"]["clearance_manifest_sync_status"] == "ready_to_sync"
    assert payload["summary"]["ready_to_sync_count"] == 1
    assert payload["summary"]["changed_field_count"] > 0
    assert payload["summary"]["applied_field_count"] == 0
    assert _read_csv(manifest_csv)[0]["operator_clearance"] == "REQUIRED_OPERATOR_CLEARANCE"
    assert _read_csv(tmp_path / "sync.csv")[0]["sync_status"] == "ready_to_sync"
    assert (tmp_path / "SYNC.md").is_file()


def test_manifest_sync_apply_copies_cleared_provenance_fields(tmp_path):
    provenance_csv = tmp_path / "provenance_template.csv"
    manifest_csv = tmp_path / "manifest_stub.csv"
    _write_csv(provenance_csv, [_ready_provenance()])
    _write_csv(manifest_csv, [_placeholder_manifest()])
    workorder_json = _workorder_json(tmp_path, provenance_csv, manifest_csv)
    args = mod.parse_args(_args(tmp_path, workorder_json, "--apply"))

    payload = mod.build_payload(args)
    mod.write_outputs(args, payload)

    assert payload["summary"]["clearance_manifest_sync_status"] == "synced"
    assert payload["summary"]["synced_count"] == 1
    assert payload["summary"]["applied_field_count"] > 0
    manifest = _read_csv(manifest_csv)[0]
    assert manifest["operator_clearance"] == "cleared"
    assert manifest["leakage_clearance"] == "no_leak"
    assert manifest["prediction_pdb"] == "runs/prediction.pdb"
    assert manifest["native_pdb"] == "native/H1001_native.pdb"


def test_manifest_sync_waits_for_blocked_provenance(tmp_path):
    provenance_csv = tmp_path / "provenance_template.csv"
    manifest_csv = tmp_path / "manifest_stub.csv"
    _write_csv(provenance_csv, [_blocked_provenance()])
    _write_csv(manifest_csv, [_placeholder_manifest()])
    workorder_json = _workorder_json(tmp_path, provenance_csv, manifest_csv)
    args = mod.parse_args(_args(tmp_path, workorder_json, "--apply"))

    payload = mod.build_payload(args)

    assert payload["summary"]["clearance_manifest_sync_status"] == "awaiting_provenance"
    assert payload["summary"]["awaiting_provenance_count"] == 1
    assert payload["summary"]["applied_field_count"] == 0
    assert "leakage_clearance_required" in payload["rows"][0]["blockers"]

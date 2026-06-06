import csv
import json
from pathlib import Path

from tools.casp17 import build_casp17_competitive_floor_target_identity_clearance_promotion_plan as mod


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


def _valid_manifest_row(tmp_path: Path, target_id: str = "H1001") -> dict[str, str]:
    prediction = tmp_path / "prediction.pdb"
    native = tmp_path / "native.pdb"
    prediction.write_text("ATOM      1  CA  ALA A   1       0.000   0.000   0.000  1.00 20.00           C\n")
    native.write_text("ATOM      1  CA  ALA A   1       1.000   0.000   0.000  1.00 20.00           C\n")
    return {
        "benchmark_id": f"hist_{target_id}_clearance_candidate",
        "target_id": target_id,
        "scope": "complex",
        "split": "historical_candidate",
        "prediction_pdb": str(prediction),
        "native_pdb": str(native),
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


def test_build_promotion_plan_promotes_only_audit_pass_rows(tmp_path):
    manifest_stub = tmp_path / "H1001_manifest_stub.csv"
    _write_csv(manifest_stub, [_valid_manifest_row(tmp_path)])
    audit_json = tmp_path / "audit.json"
    current_target_csv = tmp_path / "current_targets.csv"
    out_manifest_csv = tmp_path / "promoted_manifest.csv"
    _write_csv(current_target_csv, [{"target_id": "T9999"}])
    _write_json(
        audit_json,
        {
            "summary": {"clearance_workorder_audit_status": "partial", "audit_pass_count": 1},
            "rows": [
                {"target_id": "H1001", "audit_status": "pass", "manifest_stub_csv": str(manifest_stub)},
                {
                    "target_id": "H1002",
                    "audit_status": "blocked",
                    "manifest_stub_csv": str(tmp_path / "H1002_manifest_stub.csv"),
                    "blockers": "native_pdb_missing",
                },
            ],
        },
    )

    args = mod.parse_args(
        [
            "--audit-json",
            str(audit_json),
            "--current-target-csv",
            str(current_target_csv),
            "--out-manifest-csv",
            str(out_manifest_csv),
            "--out-json",
            str(tmp_path / "plan.json"),
            "--out-csv",
            str(tmp_path / "plan.csv"),
            "--out-md",
            str(tmp_path / "plan.md"),
        ]
    )
    payload = mod.build_payload(args)

    assert payload["summary"]["clearance_promotion_status"] == "partial_ready_for_operator_manifest_import"
    assert payload["summary"]["promoted_manifest_count"] == 1
    assert payload["summary"]["blocked_count"] == 1
    assert payload["summary"]["audit_pass_count"] == 1
    by_target = {row["target_id"]: row for row in payload["rows"]}
    assert by_target["H1001"]["promotion_status"] == "ready_for_operator_manifest_import"
    assert by_target["H1002"]["promotion_status"] == "blocked_by_audit"
    promoted = _read_csv(out_manifest_csv)
    assert [row["target_id"] for row in promoted] == ["H1001"]


def test_build_promotion_plan_rejects_current_casp17_target(tmp_path):
    manifest_stub = tmp_path / "H1001_manifest_stub.csv"
    _write_csv(manifest_stub, [_valid_manifest_row(tmp_path)])
    audit_json = tmp_path / "audit.json"
    current_target_csv = tmp_path / "current_targets.csv"
    out_manifest_csv = tmp_path / "promoted_manifest.csv"
    _write_csv(current_target_csv, [{"target_id": "H1001"}])
    _write_json(
        audit_json,
        {
            "summary": {"clearance_workorder_audit_status": "pass", "audit_pass_count": 1},
            "rows": [{"target_id": "H1001", "audit_status": "pass", "manifest_stub_csv": str(manifest_stub)}],
        },
    )

    args = mod.parse_args(
        [
            "--audit-json",
            str(audit_json),
            "--current-target-csv",
            str(current_target_csv),
            "--out-manifest-csv",
            str(out_manifest_csv),
            "--out-json",
            str(tmp_path / "plan.json"),
            "--out-csv",
            str(tmp_path / "plan.csv"),
            "--out-md",
            str(tmp_path / "plan.md"),
        ]
    )
    payload = mod.build_payload(args)

    assert payload["summary"]["clearance_promotion_status"] == "blocked_manifest_stub"
    assert payload["summary"]["promoted_manifest_count"] == 0
    assert payload["summary"]["blocked_count"] == 1
    assert "current_casp17_target_not_allowed" in payload["rows"][0]["blockers"]
    assert _read_csv(out_manifest_csv) == []

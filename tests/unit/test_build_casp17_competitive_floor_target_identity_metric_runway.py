import json
from pathlib import Path

from tools.casp17 import build_casp17_competitive_floor_target_identity_metric_runway as mod


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _touch(path: Path, text: str = "artifact\n") -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return str(path)


def _workorder(tmp_path: Path, target_id: str, native_present: bool) -> dict:
    folder = tmp_path / "workorders" / target_id
    native_path = folder / "native" / f"{target_id}_native.pdb"
    row = {
        "target_id": target_id,
        "target_name": f"{target_id} complex",
        "scope": "complex",
        "workorder_folder": str(folder),
        "readme_path": _touch(folder / "README.md"),
        "prediction_pdb": _touch(tmp_path / "predictions" / f"{target_id}.pdb", "ATOM prediction\n"),
        "ts_prediction_pdb": _touch(tmp_path / "predictions" / f"{target_id}TS.pdb", "ATOM ts\n"),
        "native_dropzone_pdb": str(native_path),
        "provenance_template_csv": _touch(folder / "provenance_template.csv"),
        "manifest_stub_csv": _touch(folder / "manifest_stub.csv"),
    }
    if native_present:
        _touch(native_path, "ATOM native\n")
    return row


def _audit(target_id: str, status: str) -> dict:
    if status == "pass":
        return {
            "target_id": target_id,
            "audit_status": "pass",
            "provenance_status": "ready",
            "evidence_ref_status": "verified",
            "identity_discovery_blocker_status": "cleared",
            "blockers": "",
        }
    return {
        "target_id": target_id,
        "audit_status": "blocked",
        "provenance_status": "blocked",
        "evidence_ref_status": "missing",
        "identity_discovery_blocker_status": "blocked",
        "blockers": (
            "native_pdb_missing,identity_discovery_no_leak_clearance_required,"
            "operator_required,evidence_ref_required,leakage_clearance_required,operator_clearance_required"
        ),
    }


def test_competitive_floor_target_identity_metric_runway_blocks_until_native_provenance(
    tmp_path: Path,
) -> None:
    workorder_json = tmp_path / "workorders.json"
    audit_json = tmp_path / "audit.json"
    native_json = tmp_path / "native_candidates.json"
    out_dir = tmp_path / "runway"
    blocked = _workorder(tmp_path, "H1319", native_present=False)
    ready = _workorder(tmp_path, "H2324", native_present=True)
    _write_json(
        workorder_json,
        {
            "summary": {"clearance_workorder_status": "awaiting_native_or_provenance"},
            "rows": [blocked, ready],
        },
    )
    _write_json(
        audit_json,
        {
            "summary": {"clearance_workorder_audit_status": "blocked"},
            "rows": [_audit("H1319", "blocked"), _audit("H2324", "pass")],
        },
    )
    _write_json(
        native_json,
        {
            "summary": {"native_candidate_packet_status": "review_required"},
            "rows": [
                {
                    "target_id": "H1319",
                    "candidate_status": "blocked_current_target_collision",
                    "pdb_id": "8UFN",
                    "blockers": "current_target_name_collision",
                },
                {
                    "target_id": "H2324",
                    "candidate_status": "operator_review_required",
                    "pdb_id": "9XYZ",
                    "blockers": "",
                },
            ],
        },
    )

    args = mod.parse_args(
        [
            "--clearance-workorder-json",
            str(workorder_json),
            "--clearance-workorder-audit-json",
            str(audit_json),
            "--native-candidate-packet-json",
            str(native_json),
            "--out-dir",
            str(out_dir),
            "--out-json",
            str(tmp_path / "runway.json"),
            "--out-csv",
            str(tmp_path / "runway.csv"),
            "--out-md",
            str(tmp_path / "RUNWAY.md"),
            "--out-html",
            str(tmp_path / "runway.html"),
        ]
    )
    payload = mod.build_payload(args)
    mod.write_outputs(args, payload)

    summary = payload["summary"]
    rows = {row["target_id"]: row for row in payload["rows"]}
    assert summary["metric_runway_status"] == (
        "casp17_competitive_floor_target_identity_metric_runway_blocked_awaiting_native_provenance"
    )
    assert summary["target_count"] == 2
    assert summary["target_ready_count"] == 1
    assert summary["target_blocked_count"] == 1
    assert summary["metric_requirement_count"] == 18
    assert summary["prediction_present_count"] == 2
    assert summary["native_present_count"] == 1
    assert summary["provenance_ready_count"] == 1
    assert summary["evidence_ref_ready_count"] == 1
    assert summary["native_candidate_count"] == 2
    assert summary["native_candidate_blocked_count"] == 1
    assert rows["H1319"]["runway_status"] == "blocked_awaiting_native_provenance"
    assert "native_pdb_missing" in rows["H1319"]["blockers"]
    assert "native_candidate_blocked_review_required" in rows["H1319"]["blockers"]
    assert rows["H2324"]["runway_status"] == "ready_for_metric_after_native_provenance"
    assert rows["H2324"]["metric_requirement_count"] == 9
    assert (out_dir / "H2324_H2324_complex" / "metric_requirements.csv").is_file()
    assert (out_dir / "H2324_H2324_complex" / "METRIC_RUNWAY.md").is_file()
    assert "AUTHOR " not in (tmp_path / "runway.json").read_text(encoding="utf-8")


def test_competitive_floor_target_identity_metric_runway_blocks_missing_workorder_files(
    tmp_path: Path,
) -> None:
    workorder_json = tmp_path / "workorders.json"
    audit_json = tmp_path / "audit.json"
    native_json = tmp_path / "native_candidates.json"
    row = _workorder(tmp_path, "T9999", native_present=False)
    Path(row["prediction_pdb"]).unlink()
    _write_json(workorder_json, {"rows": [row]})
    _write_json(audit_json, {"rows": [_audit("T9999", "blocked")]})
    _write_json(native_json, {"rows": []})
    args = mod.parse_args(
        [
            "--clearance-workorder-json",
            str(workorder_json),
            "--clearance-workorder-audit-json",
            str(audit_json),
            "--native-candidate-packet-json",
            str(native_json),
            "--out-dir",
            str(tmp_path / "runway"),
        ]
    )
    payload = mod.build_payload(args)

    assert payload["summary"]["target_blocked_count"] == 1
    blockers = payload["rows"][0]["blockers"]
    assert "prediction_pdb_missing" in blockers
    assert "native_pdb_missing" in blockers
    assert "native_candidate_packet_missing" in blockers

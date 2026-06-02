import json
from pathlib import Path

from tools import build_casp17_strict_blind_source_request_operator_fill_batch_kit as kit
from tools import build_casp17_strict_blind_source_request_operator_fill_batch_kit_completion_audit as audit


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _row(request_index: int, field_order: int, field_key: str, ready: bool = False, replacement: bool = False) -> dict:
    request_id = f"source_request_{request_index:03d}"
    target_id = f"HIST_TARGET_{request_index:03d}"
    fill_status = "field_ready_for_fulfillment_gate" if ready else "awaiting_operator_value"
    first_blocker = "" if ready else "operator_value_missing"
    if replacement:
        fill_status = "blocked_candidate_replacement_required"
        first_blocker = "candidate_replacement_required"
    return {
        "fill_id": f"source_request_operator_fill_{request_index:03d}_{field_order:03d}",
        "request_id": request_id,
        "candidate_target_id": target_id,
        "candidate_scope": "monomer",
        "request_kind": "candidate_replacement_required" if replacement else "pre_native_prediction_source_required",
        "field_key": field_key,
        "operator_template_csv": f"casp17/strict_blind/source_request_{request_index:03d}/operator_source_values_template.csv",
        "operator_value": f"value_{field_key}" if ready else "",
        "operator_evidence_ref": f"evidence/{request_id}/{field_key}.md" if ready else "",
        "value_status": "value_present" if ready else "operator_value_missing",
        "evidence_status": "evidence_present" if ready else "evidence_required_missing",
        "fill_status": fill_status,
        "first_blocker": first_blocker,
        "next_action": "rerun fulfillment gate" if ready else f"fill operator_value for {field_key}",
    }


def _build_kit(tmp_path: Path) -> Path:
    worklist_json = tmp_path / "worklist.json"
    kit_json = tmp_path / "kit.json"
    _write_json(
        worklist_json,
        {
            "summary": {
                "source_request_operator_fill_worklist_status": "awaiting_source_request_operator_values"
            },
            "rows": [
                _row(1, 1, "source_id"),
                _row(1, 2, "prediction_pdb"),
                _row(2, 1, "source_id", replacement=True),
                _row(2, 2, "prediction_pdb", replacement=True),
            ],
        },
    )
    args = kit.parse_args(
        [
            "--worklist-json",
            str(worklist_json),
            "--out-dir",
            str(tmp_path / "batch"),
            "--out-json",
            str(kit_json),
            "--out-csv",
            str(tmp_path / "kit.csv"),
            "--out-md",
            str(tmp_path / "KIT.md"),
        ]
    )
    kit.write_outputs(args, kit.build_payload(args))
    return kit_json


def test_source_request_batch_kit_completion_audit_passes_file_surface(tmp_path: Path) -> None:
    kit_json = _build_kit(tmp_path)
    args = audit.parse_args(
        [
            "--batch-kit-json",
            str(kit_json),
            "--out-json",
            str(tmp_path / "audit.json"),
            "--out-csv",
            str(tmp_path / "audit.csv"),
            "--out-md",
            str(tmp_path / "AUDIT.md"),
        ]
    )
    payload = audit.build_payload(args)
    audit.write_outputs(args, payload)

    summary = payload["summary"]
    assert summary["strict_blind_source_request_operator_fill_batch_kit_completion_audit_status"] == (
        "casp17_strict_blind_source_request_operator_fill_batch_kit_completion_audit_pass"
    )
    assert summary["batch_kit_status"] == "strict_blind_source_request_operator_fill_batch_kit_ready_for_operator_fill"
    assert summary["worklist_status"] == "awaiting_source_request_operator_values"
    assert summary["request_count"] == 2
    assert summary["request_pass_count"] == 2
    assert summary["request_blocked_count"] == 0
    assert summary["root_file_present_count"] == 4
    assert summary["root_file_required_count"] == 4
    assert summary["field_count"] == 4
    assert summary["batch_csv_row_count"] == 4
    assert summary["request_summary_csv_row_count"] == 2
    assert summary["per_request_csv_row_count"] == 4
    assert summary["request_folder_present_count"] == 2
    assert summary["request_readme_present_count"] == 2
    assert summary["request_operator_fill_csv_present_count"] == 2
    assert summary["request_summary_csv_match_count"] == 2
    assert summary["request_row_mismatch_count"] == 0
    assert summary["operator_value_missing_count"] == 4
    assert summary["operator_evidence_missing_count"] == 4
    assert summary["candidate_replacement_field_count"] == 2
    assert summary["coordinate_copy_count"] == 0
    assert summary["proof_marker_count"] == 0
    assert summary["author_marker_count"] == 0
    assert (tmp_path / "AUDIT.md").is_file()


def test_source_request_batch_kit_completion_audit_blocks_request_csv_mismatch(tmp_path: Path) -> None:
    kit_json = _build_kit(tmp_path)
    kit_payload = json.loads(kit_json.read_text(encoding="utf-8"))
    first_csv = Path(kit_payload["request_rows"][0]["request_operator_fill_csv"])
    first_csv.write_text("request_id\nwrong_request\n", encoding="utf-8")

    payload = audit.build_payload(audit.parse_args(["--batch-kit-json", str(kit_json)]))

    assert payload["summary"]["strict_blind_source_request_operator_fill_batch_kit_completion_audit_status"] == (
        "blocked_strict_blind_source_request_operator_fill_batch_kit_completion_audit"
    )
    assert payload["summary"]["request_blocked_count"] == 1
    assert "request_operator_fill_csv_row_mismatch" in payload["rows"][0]["blockers"]


def test_source_request_batch_kit_completion_audit_blocks_missing_input(tmp_path: Path) -> None:
    payload = audit.build_payload(audit.parse_args(["--batch-kit-json", str(tmp_path / "missing_kit.json")]))

    assert payload["summary"]["strict_blind_source_request_operator_fill_batch_kit_completion_audit_status"] == (
        "blocked_strict_blind_source_request_operator_fill_batch_kit_missing"
    )
    assert payload["summary"]["request_count"] == 0

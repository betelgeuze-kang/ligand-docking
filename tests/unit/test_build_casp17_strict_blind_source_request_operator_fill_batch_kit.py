import json
from pathlib import Path

from tools.casp17 import build_casp17_strict_blind_source_request_operator_fill_batch_kit as mod


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _row(request_index: int, field_order: int, field_key: str, ready: bool = False, replacement: bool = False) -> dict:
    request_id = f"source_request_{request_index:03d}"
    target_id = f"HIST_TARGET_{request_index:03d}"
    value = f"value_{field_key}" if ready else ""
    evidence = f"evidence/{request_id}/{field_key}.md" if ready else ""
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
        "operator_value": value,
        "operator_evidence_ref": evidence,
        "value_status": "value_present" if ready else "operator_value_missing",
        "evidence_status": "evidence_present" if ready else "evidence_required_missing",
        "fill_status": fill_status,
        "first_blocker": first_blocker,
        "next_action": "rerun fulfillment gate" if ready else f"fill operator_value for {field_key}",
    }


def test_source_request_batch_kit_collects_all_requests(tmp_path: Path) -> None:
    worklist_json = tmp_path / "worklist.json"
    _write_json(
        worklist_json,
        {
            "summary": {
                "source_request_operator_fill_worklist_status": "awaiting_source_request_operator_values"
            },
            "rows": [
                _row(1, 1, "source_id"),
                _row(1, 2, "prediction_pdb"),
                _row(2, 1, "source_id"),
                _row(2, 2, "prediction_pdb", ready=True),
                _row(3, 1, "source_id", replacement=True),
            ],
        },
    )
    args = mod.parse_args(
        [
            "--worklist-json",
            str(worklist_json),
            "--out-dir",
            str(tmp_path / "batch"),
            "--out-json",
            str(tmp_path / "batch.json"),
            "--out-csv",
            str(tmp_path / "batch.csv"),
            "--out-md",
            str(tmp_path / "BATCH.md"),
        ]
    )
    payload = mod.build_payload(args)
    mod.write_outputs(args, payload)

    summary = payload["summary"]
    assert summary["strict_blind_source_request_operator_fill_batch_kit_status"] == (
        "strict_blind_source_request_operator_fill_batch_kit_ready_for_operator_fill"
    )
    assert summary["request_count"] == 3
    assert summary["ready_request_count"] == 0
    assert summary["blocked_request_count"] == 3
    assert summary["field_count"] == 5
    assert summary["field_ready_count"] == 1
    assert summary["field_blocked_count"] == 4
    assert summary["operator_value_missing_count"] == 4
    assert summary["operator_evidence_missing_count"] == 4
    assert summary["candidate_replacement_field_count"] == 1
    assert summary["source_template_count"] == 3
    assert summary["source_request_folder_count"] == 3
    assert summary["first_request_id"] == "source_request_001"
    assert summary["first_field_key"] == "source_id"
    assert summary["first_blocker"] == "operator_value_missing"
    assert len(payload["request_rows"]) == 3
    assert (tmp_path / "batch" / "operator_fill_intake_batch.csv").is_file()
    assert (tmp_path / "batch" / "request_summary.csv").is_file()
    assert (tmp_path / "batch" / "01_source_request_001_HIST_TARGET_001" / "README.md").is_file()
    assert (tmp_path / "BATCH.md").is_file()


def test_source_request_batch_kit_complete_when_all_rows_ready(tmp_path: Path) -> None:
    worklist_json = tmp_path / "worklist.json"
    _write_json(
        worklist_json,
        {
            "summary": {
                "source_request_operator_fill_worklist_status": "source_request_operator_fill_worklist_ready"
            },
            "rows": [_row(1, 1, "source_id", ready=True)],
        },
    )
    payload = mod.build_payload(mod.parse_args(["--worklist-json", str(worklist_json)]))

    assert payload["summary"]["strict_blind_source_request_operator_fill_batch_kit_status"] == (
        "strict_blind_source_request_operator_fill_batch_kit_complete"
    )
    assert payload["summary"]["ready_request_count"] == 1
    assert payload["summary"]["blocked_request_count"] == 0


def test_source_request_batch_kit_blocks_missing_worklist(tmp_path: Path) -> None:
    payload = mod.build_payload(mod.parse_args(["--worklist-json", str(tmp_path / "missing.json")]))

    assert payload["summary"]["strict_blind_source_request_operator_fill_batch_kit_status"] == (
        "blocked_strict_blind_source_request_operator_fill_worklist_missing"
    )
    assert payload["summary"]["field_count"] == 0

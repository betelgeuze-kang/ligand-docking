import csv
import json
from pathlib import Path

from tools.casp17 import build_casp17_strict_blind_source_request_operator_fill_worklist_completion_audit as mod


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _request(tmp_path: Path, request_id: str, target_id: str, fields: list[str]) -> dict:
    folder = tmp_path / "requests" / request_id
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "SOURCE_REQUEST.md").write_text(f"# {request_id}\n", encoding="utf-8")
    _write_csv(
        folder / "operator_source_values_template.csv",
        [
            {
                "field_key": field,
                "operator_value": "",
                "operator_evidence_ref": "",
                "required_format": "",
                "source_request_note": "",
            }
            for field in fields
        ],
    )
    return {
        "request_id": request_id,
        "candidate_target_id": target_id,
        "candidate_scope": "monomer",
        "request_kind": "pre_native_prediction_source_required",
        "request_folder": str(folder),
        "operator_template_csv": str(folder / "operator_source_values_template.csv"),
        "required_operator_fields": ",".join(fields),
    }


def _worklist_rows(request: dict, fields: list[str]) -> list[dict]:
    rows = []
    for field in fields:
        rows.append(
            {
                "fill_id": f"{request['request_id']}_{field}",
                "request_id": request["request_id"],
                "candidate_target_id": request["candidate_target_id"],
                "candidate_scope": request["candidate_scope"],
                "request_kind": request["request_kind"],
                "field_key": field,
                "operator_template_csv": request["operator_template_csv"],
                "operator_value": "",
                "operator_evidence_ref": "",
                "value_status": "operator_value_missing",
                "evidence_status": "evidence_required_missing" if field != "prediction_pdb_dropzone" else "evidence_not_required",
                "fill_status": "awaiting_operator_value",
                "first_blocker": "operator_value_missing",
                "next_action": f"fill operator_value for {field}",
            }
        )
    return rows


def _payloads(tmp_path: Path) -> tuple[Path, Path, list[dict], list[dict]]:
    request_one = _request(tmp_path, "source_request_001", "HIST_BBA5", ["source_id", "prediction_pdb"])
    request_two = _request(
        tmp_path,
        "source_request_002",
        "HIST_CHIGNOLIN",
        ["source_id", "prediction_pdb_dropzone", "operator_clearance"],
    )
    requests = [request_one, request_two]
    worklist_rows = _worklist_rows(request_one, ["source_id", "prediction_pdb"]) + _worklist_rows(
        request_two,
        ["source_id", "prediction_pdb_dropzone", "operator_clearance"],
    )
    source_request_json = tmp_path / "source_requests.json"
    worklist_json = tmp_path / "worklist.json"
    _write_json(
        source_request_json,
        {
            "summary": {
                "source_request_packet_status": "awaiting_pre_native_source_or_candidate_replacement",
                "request_count": len(requests),
            },
            "rows": requests,
        },
    )
    _write_json(
        worklist_json,
        {
            "summary": {
                "source_request_operator_fill_worklist_status": "awaiting_source_request_operator_values",
                "field_action_count": len(worklist_rows),
            },
            "rows": worklist_rows,
        },
    )
    return source_request_json, worklist_json, requests, worklist_rows


def test_source_request_operator_fill_worklist_completion_audit_passes_file_surface(tmp_path: Path) -> None:
    source_request_json, worklist_json, _, _ = _payloads(tmp_path)
    args = mod.parse_args(
        [
            "--source-request-packet-json",
            str(source_request_json),
            "--operator-fill-worklist-json",
            str(worklist_json),
            "--out-json",
            str(tmp_path / "audit.json"),
            "--out-csv",
            str(tmp_path / "audit.csv"),
            "--out-md",
            str(tmp_path / "AUDIT.md"),
        ]
    )
    payload = mod.build_payload(args)
    mod.write_outputs(args, payload)

    summary = payload["summary"]
    assert summary["source_request_operator_fill_worklist_completion_audit_status"] == (
        "casp17_strict_blind_source_request_operator_fill_worklist_completion_audit_pass"
    )
    assert summary["request_count"] == 2
    assert summary["request_pass_count"] == 2
    assert summary["request_blocked_count"] == 0
    assert summary["expected_field_count"] == 5
    assert summary["template_csv_row_count"] == 5
    assert summary["worklist_row_count"] == 5
    assert summary["field_row_mismatch_count"] == 0
    assert summary["operator_value_missing_count"] == 5
    assert summary["operator_evidence_missing_count"] == 4
    assert summary["request_folder_present_count"] == 2
    assert summary["source_request_md_present_count"] == 2
    assert summary["operator_template_csv_present_count"] == 2
    assert summary["coordinate_copy_count"] == 0
    assert {row["audit_status"] for row in payload["rows"]} == {"pass"}
    assert (tmp_path / "audit.json").is_file()
    assert (tmp_path / "AUDIT.md").is_file()


def test_source_request_operator_fill_worklist_completion_audit_blocks_mismatch_and_coordinate_copy(
    tmp_path: Path,
) -> None:
    source_request_json, worklist_json, requests, _ = _payloads(tmp_path)
    first_template = Path(requests[0]["operator_template_csv"])
    _write_csv(
        first_template,
        [
            {
                "field_key": "source_id",
                "operator_value": "",
                "operator_evidence_ref": "",
                "required_format": "",
                "source_request_note": "",
            }
        ],
    )
    (Path(requests[0]["request_folder"]) / "copied_prediction.pdb").write_text("ATOM copied\n", encoding="utf-8")

    args = mod.parse_args(
        [
            "--source-request-packet-json",
            str(source_request_json),
            "--operator-fill-worklist-json",
            str(worklist_json),
        ]
    )
    payload = mod.build_payload(args)

    summary = payload["summary"]
    assert summary["source_request_operator_fill_worklist_completion_audit_status"] == (
        "casp17_strict_blind_source_request_operator_fill_worklist_completion_audit_blocked"
    )
    assert summary["request_blocked_count"] == 1
    assert summary["field_row_mismatch_count"] == 1
    assert summary["coordinate_copy_count"] == 1
    blockers = payload["rows"][0]["blockers"]
    assert "operator_template_csv_row_count_mismatch" in blockers
    assert "operator_template_missing_required_fields" in blockers
    assert "request_coordinate_copy_present" in blockers

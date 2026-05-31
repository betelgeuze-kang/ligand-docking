import csv
import json
from pathlib import Path

from tools import build_casp17_strict_blind_source_gate_operator_packet as mod


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_operator_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=mod.OPERATOR_COLUMNS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _field_board_payload(dropzone: str = "dropzone/replacement_prediction.pdb") -> dict:
    rows = [
        ("source_id", "manifest_value", "", "manifest.csv", "internal_source_id_missing_or_external"),
        ("prediction_pdb", "file", "", "manifest.csv", "prediction_pdb_missing,prediction_pdb_not_found"),
        ("prediction_pdb_dropzone", "file", dropzone, dropzone, "dropzone_prediction_pdb_missing"),
        ("prediction_created_at", "manifest_value", "", "manifest.csv", "prediction_created_at_missing_or_invalid"),
        ("native_release_date", "manifest_value", "", "manifest.csv", "native_release_date_missing_or_invalid"),
        (
            "prediction_created_at/native_release_date",
            "manifest_value",
            "/",
            "manifest.csv",
            "prediction_not_before_native",
        ),
        ("native_authority_ref", "manifest_value", "", "manifest.csv", "native_authority_ref_missing"),
        ("creation_evidence_ref", "manifest_value", "", "manifest.csv", "creation_evidence_ref_missing"),
        ("no_leak_evidence_ref", "manifest_value", "", "manifest.csv", "no_leak_evidence_ref_missing"),
        ("method_summary", "manifest_value", "", "manifest.csv", "method_summary_missing"),
        ("operator_clearance", "manifest_value", "", "manifest.csv", "operator_clearance_missing"),
    ]
    return {
        "summary": {
            "source_gate_field_board_status": "awaiting_source_gate_field_fills",
            "required_benchmark_id": "hist_REQUIRED_MONOMER_001",
            "required_target_id": "REQUIRED_MONOMER_001",
            "required_scope": "monomer",
            "manifest_csv": "manifest.csv",
        },
        "rows": [
            {
                "field_key": field_key,
                "fill_kind": fill_kind,
                "current_value": current_value,
                "destination": destination,
                "affected_check_ids": field_key,
                "blockers": blockers,
                "next_action": f"fill {field_key}",
            }
            for field_key, fill_kind, current_value, destination, blockers in rows
        ],
    }


def test_operator_packet_builds_blank_operator_surface_and_patch_preview(tmp_path):
    field_board_json = tmp_path / "field_board.json"
    _write_json(field_board_json, _field_board_payload())

    args = mod.parse_args(
        [
            "--field-board-json",
            str(field_board_json),
            "--packet-dir",
            str(tmp_path / "operator_packet"),
            "--out-json",
            str(tmp_path / "packet.json"),
            "--out-csv",
            str(tmp_path / "packet.csv"),
            "--out-md",
            str(tmp_path / "PACKET.md"),
        ]
    )
    payload = mod.build_payload(args)
    mod.write_outputs(args, payload)

    summary = payload["summary"]
    assert summary["source_gate_operator_packet_status"] == "awaiting_source_gate_operator_values"
    assert summary["field_action_count"] == 11
    assert summary["operator_ready_count"] == 0
    assert summary["operator_awaiting_count"] == 11
    assert summary["manifest_patch_count"] == 9
    assert summary["file_copy_count"] == 1
    assert summary["derived_check_count"] == 1
    assert summary["first_field_key"] == "source_id"
    assert summary["first_operator_status"] == "awaiting_operator_value"
    assert (tmp_path / "operator_packet" / "hist_REQUIRED_MONOMER_001" / "source_gate_operator_values.csv").is_file()
    assert (
        tmp_path
        / "operator_packet"
        / "hist_REQUIRED_MONOMER_001"
        / "source_gate_manifest_patch_preview.csv"
    ).is_file()


def test_operator_packet_preserves_existing_values_and_marks_ready_rows(tmp_path):
    prediction = tmp_path / "prediction.pdb"
    prediction.write_text("ATOM      1  CA  ALA A   1       0.000   0.000   0.000  1.00 10.00           C\n")
    dropzone = tmp_path / "dropzone" / "replacement_prediction.pdb"
    dropzone.parent.mkdir(parents=True)
    dropzone.write_text(prediction.read_text(encoding="utf-8"), encoding="utf-8")
    field_board_json = tmp_path / "field_board.json"
    _write_json(field_board_json, _field_board_payload(str(dropzone)))

    operator_csv = tmp_path / "operator_packet" / "hist_REQUIRED_MONOMER_001" / "source_gate_operator_values.csv"
    values = {
        "source_id": "internal_fold_run_001",
        "prediction_pdb": str(prediction),
        "prediction_pdb_dropzone": str(dropzone),
        "prediction_created_at": "2026-01-02",
        "native_release_date": "2026-02-02",
        "prediction_created_at/native_release_date": "",
        "native_authority_ref": "evidence/native.md",
        "creation_evidence_ref": "evidence/creation.md",
        "no_leak_evidence_ref": "evidence/no_leak.md",
        "method_summary": "internal pre-native run",
        "operator_clearance": "approved",
    }
    _write_operator_csv(
        operator_csv,
        [
            {
                "field_key": field_key,
                "fill_kind": "",
                "operator_value": value,
                "operator_evidence_ref": "operator-note",
                "required_format": "",
                "current_value": "",
                "destination": "",
                "blocked_checks": "",
                "operator_status": "",
                "next_action": "",
            }
            for field_key, value in values.items()
        ],
    )

    args = mod.parse_args(
        [
            "--field-board-json",
            str(field_board_json),
            "--packet-dir",
            str(tmp_path / "operator_packet"),
            "--out-json",
            str(tmp_path / "packet.json"),
            "--out-csv",
            str(tmp_path / "packet.csv"),
        ]
    )
    payload = mod.build_payload(args)

    by_field = {row["field_key"]: row for row in payload["operator_rows"]}
    assert payload["summary"]["source_gate_operator_packet_status"] == (
        "source_gate_operator_packet_ready_for_review"
    )
    assert payload["summary"]["operator_ready_count"] == 11
    assert payload["summary"]["patch_ready_count"] == 11
    assert by_field["prediction_pdb"]["operator_value"] == str(prediction)
    assert by_field["prediction_created_at/native_release_date"]["operator_status"] == "ready"


def test_operator_packet_blocks_missing_field_board_json(tmp_path):
    args = mod.parse_args(["--field-board-json", str(tmp_path / "missing_field_board.json")])
    payload = mod.build_payload(args)

    assert payload["summary"]["source_gate_operator_packet_status"] == "blocked_missing_inputs"
    assert "source_gate_field_board_json_missing" in payload["summary"]["input_blockers"]
    assert payload["operator_rows"] == []

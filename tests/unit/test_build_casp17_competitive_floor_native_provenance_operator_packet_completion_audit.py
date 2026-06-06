import csv
import json
from pathlib import Path

from tools.casp17 import build_casp17_competitive_floor_native_provenance_operator_packet_completion_audit as mod


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _touch(path: Path, text: str = "artifact\n") -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return str(path)


def _write_actions_csv(path: Path) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = [
        ("native_dropzone", "native_pdb"),
        ("no_leak_evidence", "evidence_ref"),
        ("provenance_fields", "provenance_template_required_fields"),
        ("manifest_stub_sync", "manifest_stub_fields"),
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "action_rank",
                "lane",
                "required_field",
                "required_artifact",
                "action_status",
                "blockers",
                "recommended_action",
                "unlocks",
                "verification_command",
            ],
            lineterminator="\n",
        )
        writer.writeheader()
        for index, (lane, field) in enumerate(rows, start=1):
            writer.writerow(
                {
                    "action_rank": index,
                    "lane": lane,
                    "required_field": field,
                    "required_artifact": f"{field}.csv",
                    "action_status": "open",
                    "blockers": "operator_required",
                    "recommended_action": "fill value",
                    "unlocks": "metric_runway",
                    "verification_command": "python3 tools/run_cycle.py",
                }
            )
    return str(path)


def _write_native_candidates_csv(path: Path, count: int) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "pdb_id",
                "candidate_status",
                "blockers",
                "download_url",
                "initial_release_date",
                "experimental_method",
                "resolution_combined",
                "struct_title",
                "native_source_pdb_suggestion",
                "next_action",
            ],
            lineterminator="\n",
        )
        writer.writeheader()
        for index in range(count):
            writer.writerow(
                {
                    "pdb_id": f"{index + 1}ABC",
                    "candidate_status": "blocked_current_target_collision",
                    "blockers": "operator_review_required",
                    "download_url": "https://files.rcsb.org/download/1ABC.pdb",
                    "initial_release_date": "2020-01-01",
                    "experimental_method": "X-RAY DIFFRACTION",
                    "resolution_combined": "2.0",
                    "struct_title": "candidate",
                    "native_source_pdb_suggestion": "",
                    "next_action": "review candidate",
                }
            )
    return str(path)


def _packet_row(tmp_path: Path, target_id: str, native_candidate_count: int) -> dict:
    packet_folder = tmp_path / "packet" / f"{target_id}_{target_id}_complex"
    workorder = tmp_path / "workorders" / target_id
    runway = tmp_path / "runway" / target_id
    _touch(packet_folder / "README.md")
    _write_json(packet_folder / "operator_packet_manifest.json", {"summary": {"target_id": target_id}})
    _touch(workorder / "README.md")
    _touch(workorder / "provenance_template.csv")
    _touch(workorder / "manifest_stub.csv")
    _touch(runway / "METRIC_RUNWAY.md")
    return {
        "target_id": target_id,
        "target_name": f"{target_id} complex",
        "operator_packet_status": "open_actions",
        "packet_folder": str(packet_folder),
        "packet_readme": str(packet_folder / "README.md"),
        "packet_manifest": str(packet_folder / "operator_packet_manifest.json"),
        "actions_csv": _write_actions_csv(packet_folder / "actions.csv"),
        "native_candidates_csv": _write_native_candidates_csv(packet_folder / "native_candidates.csv", native_candidate_count),
        "action_count": 4,
        "native_action_count": 1,
        "evidence_action_count": 1,
        "provenance_action_count": 1,
        "manifest_action_count": 1,
        "metric_requirement_count": 9,
        "metric_runway_md": str(runway / "METRIC_RUNWAY.md"),
        "workorder_folder": str(workorder),
        "workorder_readme": str(workorder / "README.md"),
        "prediction_pdb": _touch(tmp_path / "predictions" / f"{target_id}.pdb", "ATOM prediction\n"),
        "ts_prediction_pdb": _touch(tmp_path / "predictions" / f"{target_id}TS.pdb", "ATOM ts\n"),
        "native_dropzone_pdb": str(workorder / "native" / f"{target_id}_native.pdb"),
        "provenance_template_csv": str(workorder / "provenance_template.csv"),
        "manifest_stub_csv": str(workorder / "manifest_stub.csv"),
        "native_candidate_count": native_candidate_count,
        "competitive_proof_eligible": "false",
        "author_serialized": "false",
    }


def test_operator_packet_completion_audit_passes_complete_packet(tmp_path: Path) -> None:
    packet_json = tmp_path / "packet.json"
    rows = [_packet_row(tmp_path, "H1319", 2), _packet_row(tmp_path, "H2324", 1)]
    _write_json(
        packet_json,
        {
            "summary": {
                "operator_packet_status": (
                    "casp17_competitive_floor_native_provenance_operator_packet_open_actions"
                ),
                "out_dir": str(tmp_path / "packet"),
            },
            "rows": rows,
        },
    )
    args = mod.parse_args(
        [
            "--operator-packet-json",
            str(packet_json),
            "--out-json",
            str(tmp_path / "audit.json"),
            "--out-csv",
            str(tmp_path / "audit.csv"),
            "--out-md",
            str(tmp_path / "AUDIT.md"),
            "--out-html",
            str(tmp_path / "audit.html"),
        ]
    )
    payload = mod.build_payload(args)
    mod.write_outputs(args, payload)

    summary = payload["summary"]
    assert summary["operator_packet_completion_audit_status"] == (
        "casp17_competitive_floor_native_provenance_operator_packet_completion_audit_pass"
    )
    assert summary["target_pass_count"] == 2
    assert summary["target_blocked_count"] == 0
    assert summary["packet_folder_present_count"] == 2
    assert summary["packet_readme_present_count"] == 2
    assert summary["packet_manifest_present_count"] == 2
    assert summary["actions_csv_present_count"] == 2
    assert summary["native_candidates_csv_present_count"] == 2
    assert summary["action_expected_row_count"] == 8
    assert summary["action_csv_row_count"] == 8
    assert summary["action_csv_mismatch_count"] == 0
    assert summary["native_candidate_expected_row_count"] == 3
    assert summary["native_candidate_csv_row_count"] == 3
    assert summary["native_candidate_csv_mismatch_count"] == 0
    assert summary["native_action_csv_count"] == 2
    assert summary["evidence_action_csv_count"] == 2
    assert summary["provenance_action_csv_count"] == 2
    assert summary["manifest_action_csv_count"] == 2
    assert summary["prediction_present_count"] == 2
    assert summary["ts_prediction_present_count"] == 2
    assert summary["native_dropzone_path_present_count"] == 2
    assert summary["native_file_present_count"] == 0
    assert summary["packet_coordinate_copy_count"] == 0
    assert summary["out_dir_coordinate_copy_count"] == 0
    assert summary["competitive_proof_eligible_count"] == 0
    assert summary["author_serialized_count"] == 0
    assert {row["audit_status"] for row in payload["rows"]} == {"pass"}
    assert (tmp_path / "AUDIT.md").is_file()
    assert ("AUTHOR" + " ") not in (tmp_path / "audit.json").read_text(encoding="utf-8")


def test_operator_packet_completion_audit_blocks_missing_actions_and_copied_coordinates(
    tmp_path: Path,
) -> None:
    row = _packet_row(tmp_path, "T9999", 1)
    Path(row["actions_csv"]).unlink()
    _touch(Path(row["packet_folder"]) / "copied_native.pdb", "ATOM copied\n")
    packet_json = tmp_path / "packet.json"
    _write_json(
        packet_json,
        {
            "summary": {
                "operator_packet_status": (
                    "casp17_competitive_floor_native_provenance_operator_packet_open_actions"
                ),
                "out_dir": str(tmp_path / "packet"),
            },
            "rows": [row],
        },
    )
    args = mod.parse_args(["--operator-packet-json", str(packet_json)])
    payload = mod.build_payload(args)

    assert payload["summary"]["operator_packet_completion_audit_status"] == (
        "casp17_competitive_floor_native_provenance_operator_packet_completion_audit_blocked"
    )
    assert payload["summary"]["target_blocked_count"] == 1
    assert payload["summary"]["action_csv_mismatch_count"] == 1
    assert payload["summary"]["packet_coordinate_copy_count"] == 1
    assert payload["summary"]["out_dir_coordinate_copy_count"] == 1
    blockers = payload["rows"][0]["blockers"]
    assert "actions_csv_missing" in blockers
    assert "action_csv_row_count_mismatch" in blockers
    assert "packet_coordinate_copy_present" in blockers

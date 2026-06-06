import json
from pathlib import Path

from tools.casp17 import build_casp17_competitive_floor_native_provenance_operator_packet as mod


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _touch(path: Path, text: str = "artifact\n") -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return str(path)


def _actions(tmp_path: Path, target_id: str) -> list[dict]:
    folder = tmp_path / "workorders" / target_id
    native = folder / "native" / f"{target_id}_native.pdb"
    provenance = folder / "provenance_template.csv"
    manifest = folder / "manifest_stub.csv"
    _touch(provenance)
    _touch(manifest)
    lanes = [
        ("native_dropzone", "native_pdb", native, "place native"),
        ("no_leak_evidence", "evidence_ref", provenance, "write evidence ref"),
        ("provenance_fields", "provenance_template_required_fields", provenance, "fill provenance"),
        ("manifest_stub_sync", "manifest_stub_fields", manifest, "sync manifest"),
    ]
    return [
        {
            "action_rank": index,
            "target_id": target_id,
            "lane": lane,
            "required_field": field,
            "required_artifact": str(artifact),
            "action_status": "open",
            "blockers": "native_pdb_missing" if lane == "native_dropzone" else "operator_clearance_required",
            "recommended_action": action,
            "unlocks": "metric_runway",
            "verification_command": "python3 tools/run_cycle.py",
        }
        for index, (lane, field, artifact, action) in enumerate(lanes, start=1)
    ]


def _runway(tmp_path: Path, target_id: str) -> dict:
    folder = tmp_path / "workorders" / target_id
    runway = tmp_path / "runway" / target_id
    _touch(runway / "METRIC_RUNWAY.md")
    return {
        "target_id": target_id,
        "target_name": f"{target_id} complex",
        "runway_status": "blocked_awaiting_native_provenance",
        "metric_requirement_count": 9,
        "required_metric_names": "GDT_TS|lDDT|TM-score|RMSD|GDT_HA|MolProbity|DockQ|ICS|IPS",
        "metric_runway_md": str(runway / "METRIC_RUNWAY.md"),
        "prediction_pdb": _touch(tmp_path / "predictions" / f"{target_id}.pdb", "ATOM prediction\n"),
        "ts_prediction_pdb": _touch(tmp_path / "predictions" / f"{target_id}TS.pdb", "ATOM ts\n"),
        "native_dropzone_pdb": str(folder / "native" / f"{target_id}_native.pdb"),
        "provenance_template_csv": str(folder / "provenance_template.csv"),
        "manifest_stub_csv": str(folder / "manifest_stub.csv"),
        "prediction_status": "present",
        "native_status": "missing",
        "provenance_status": "blocked",
        "evidence_ref_status": "missing",
        "blockers": "native_pdb_missing,operator_clearance_required",
    }


def _workorder(tmp_path: Path, target_id: str) -> dict:
    folder = tmp_path / "workorders" / target_id
    _touch(folder / "README.md")
    return {
        "target_id": target_id,
        "target_name": f"{target_id} complex",
        "workorder_folder": str(folder),
        "readme_path": str(folder / "README.md"),
        "prediction_pdb": str(tmp_path / "predictions" / f"{target_id}.pdb"),
        "ts_prediction_pdb": str(tmp_path / "predictions" / f"{target_id}TS.pdb"),
        "native_dropzone_pdb": str(folder / "native" / f"{target_id}_native.pdb"),
        "provenance_template_csv": str(folder / "provenance_template.csv"),
        "manifest_stub_csv": str(folder / "manifest_stub.csv"),
    }


def test_native_provenance_operator_packet_groups_target_actions(tmp_path: Path) -> None:
    action_json = tmp_path / "actions.json"
    runway_json = tmp_path / "runway.json"
    workorder_json = tmp_path / "workorders.json"
    native_json = tmp_path / "natives.json"
    out_dir = tmp_path / "packet"
    action_rows = _actions(tmp_path, "H1319") + _actions(tmp_path, "H2324")
    _write_json(action_json, {"summary": {"action_board_status": "open_actions"}, "rows": action_rows})
    _write_json(
        runway_json,
        {
            "summary": {"metric_runway_status": "blocked_awaiting_native_provenance"},
            "rows": [_runway(tmp_path, "H1319"), _runway(tmp_path, "H2324")],
        },
    )
    _write_json(
        workorder_json,
        {
            "summary": {"clearance_workorder_status": "awaiting_native_or_provenance"},
            "rows": [_workorder(tmp_path, "H1319"), _workorder(tmp_path, "H2324")],
        },
    )
    _write_json(
        native_json,
        {
            "summary": {"native_candidate_packet_status": "review_required"},
            "rows": [
                {
                    "target_id": "H1319",
                    "pdb_id": "8UFN",
                    "candidate_status": "blocked_current_target_collision",
                    "blockers": "current_target_name_collision",
                },
                {
                    "target_id": "H2324",
                    "pdb_id": "",
                    "candidate_status": "no_rcsb_candidate_found",
                    "blockers": "rcsb_candidate_missing",
                },
            ],
        },
    )

    args = mod.parse_args(
        [
            "--action-board-json",
            str(action_json),
            "--metric-runway-json",
            str(runway_json),
            "--workorder-json",
            str(workorder_json),
            "--native-candidate-packet-json",
            str(native_json),
            "--out-dir",
            str(out_dir),
            "--out-json",
            str(tmp_path / "packet.json"),
            "--out-csv",
            str(tmp_path / "packet.csv"),
            "--out-md",
            str(tmp_path / "PACKET.md"),
            "--out-html",
            str(tmp_path / "packet.html"),
        ]
    )
    payload = mod.build_payload(args)
    mod.write_outputs(args, payload)

    summary = payload["summary"]
    rows = {row["target_id"]: row for row in payload["rows"]}
    assert summary["operator_packet_status"] == (
        "casp17_competitive_floor_native_provenance_operator_packet_open_actions"
    )
    assert summary["target_count"] == 2
    assert summary["target_open_count"] == 2
    assert summary["action_count"] == 8
    assert summary["open_action_count"] == 8
    assert summary["native_action_count"] == 2
    assert summary["evidence_action_count"] == 2
    assert summary["provenance_action_count"] == 2
    assert summary["manifest_action_count"] == 2
    assert summary["metric_requirement_count"] == 18
    assert summary["prediction_present_count"] == 2
    assert summary["native_present_count"] == 0
    assert summary["native_candidate_blocked_count"] == 1
    assert summary["native_candidate_no_candidate_count"] == 1
    assert rows["H1319"]["native_candidate_blocked_count"] == 1
    assert rows["H2324"]["native_candidate_no_candidate_count"] == 1
    assert "native_pdb_missing" in rows["H1319"]["blockers"]
    assert (out_dir / "H1319_H1319_complex" / "actions.csv").is_file()
    assert (out_dir / "H1319_H1319_complex" / "native_candidates.csv").is_file()
    assert (out_dir / "H1319_H1319_complex" / "README.md").is_file()
    assert not list(out_dir.rglob("*.pdb"))
    assert "AUTHOR " not in (tmp_path / "packet.json").read_text(encoding="utf-8")


def test_native_provenance_operator_packet_blocks_missing_prediction_and_native_candidates(
    tmp_path: Path,
) -> None:
    action_json = tmp_path / "actions.json"
    runway_json = tmp_path / "runway.json"
    workorder_json = tmp_path / "workorders.json"
    native_json = tmp_path / "natives.json"
    target_id = "T9999"
    action_rows = _actions(tmp_path, target_id)
    runway = _runway(tmp_path, target_id)
    Path(runway["prediction_pdb"]).unlink()
    _write_json(action_json, {"rows": action_rows})
    _write_json(runway_json, {"rows": [runway]})
    _write_json(workorder_json, {"rows": [_workorder(tmp_path, target_id)]})
    _write_json(native_json, {"rows": []})
    args = mod.parse_args(
        [
            "--action-board-json",
            str(action_json),
            "--metric-runway-json",
            str(runway_json),
            "--workorder-json",
            str(workorder_json),
            "--native-candidate-packet-json",
            str(native_json),
            "--out-dir",
            str(tmp_path / "packet"),
        ]
    )
    payload = mod.build_payload(args)

    assert payload["summary"]["target_open_count"] == 1
    blockers = payload["rows"][0]["blockers"]
    assert "prediction_pdb_missing" in blockers
    assert "native_candidate_packet_missing" in blockers

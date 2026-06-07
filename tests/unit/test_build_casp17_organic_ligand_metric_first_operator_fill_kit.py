import json
from pathlib import Path

from tools.casp17 import build_casp17_organic_ligand_metric_first_operator_fill_kit as mod


FIELDS = [
    "direct_native_or_source_authority",
    "no_leak_provenance",
    "prediction_chronology",
    "ligand_pose_reference",
    "strict_blind_slot_mapping",
]


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _worklist_payload(*, ready: bool = False) -> dict:
    rows = []
    for candidate_rank in range(1, 3):
        candidate_id = f"organic_ligand_slot_candidate_{candidate_rank:03d}"
        ligand_id = f"ligand_{candidate_rank:03d}"
        for field_order, field_key in enumerate(FIELDS, start=1):
            rows.append(
                {
                    "fill_id": f"organic_ligand_metric_operator_fill_{len(rows) + 1:03d}",
                    "candidate_rank": candidate_rank,
                    "candidate_id": candidate_id,
                    "target_id": f"HIST_COMPLEX_{candidate_rank:02d}",
                    "ligand_id": ligand_id,
                    "field_order": field_order,
                    "field_key": field_key,
                    "required_operator_value_format": "operator reviewed evidence",
                    "source_operator_template_csv": f"intake/{ligand_id}/operator_evidence_template.csv",
                    "source_evidence_stub_md": f"intake/{ligand_id}/{field_key}.md",
                    "linked_action_md": f"actions/{candidate_id}/{field_key}/ACTION.md",
                    "operator_value": "reviewed_value" if ready else "",
                    "operator_evidence_ref": "evidence.md" if ready else "",
                    "operator_clearance": "approved" if ready else "",
                    "operator_id": "operator_001" if ready else "",
                    "value_status": "value_present" if ready else "operator_value_missing",
                    "evidence_ref_status": (
                        "evidence_ref_present" if ready else "operator_evidence_ref_missing"
                    ),
                    "clearance_status": "clearance_present" if ready else "operator_clearance_missing",
                    "operator_id_status": "operator_id_present" if ready else "operator_id_missing",
                    "fill_status": mod.READY_STATUS if ready else "awaiting_operator_value",
                    "first_blocker": "" if ready else "operator_value_missing",
                    "next_action": f"fill operator_value for {field_key}",
                }
            )
    return {
        "summary": {
            "organic_ligand_metric_operator_fill_worklist_status": (
                "organic_ligand_metric_operator_fill_complete"
                if ready
                else "awaiting_organic_ligand_metric_operator_fill_values"
            )
        },
        "rows": rows,
    }


def _args(tmp_path: Path, worklist_json: Path) -> list[str]:
    return [
        "--worklist-json",
        str(worklist_json),
        "--out-dir",
        str(tmp_path / "kit"),
        "--out-json",
        str(tmp_path / "kit.json"),
        "--out-csv",
        str(tmp_path / "kit.csv"),
        "--out-md",
        str(tmp_path / "KIT.md"),
    ]


def test_first_operator_fill_kit_focuses_first_blocked_candidate(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    worklist_json = tmp_path / "worklist.json"
    _write_json(worklist_json, _worklist_payload(ready=False))

    args = mod.parse_args(_args(tmp_path, worklist_json))
    payload = mod.build_payload(args)
    mod.write_outputs(args, payload)
    summary = payload["summary"]

    assert summary["organic_ligand_metric_first_operator_fill_kit_status"] == (
        "organic_ligand_metric_first_operator_fill_kit_ready_for_operator_fill"
    )
    assert summary["candidate_id"] == "organic_ligand_slot_candidate_001"
    assert summary["target_id"] == "HIST_COMPLEX_01"
    assert summary["ligand_id"] == "ligand_001"
    assert summary["field_count"] == 5
    assert summary["field_ready_count"] == 0
    assert summary["field_blocked_count"] == 5
    assert summary["operator_value_missing_count"] == 5
    assert summary["operator_evidence_ref_missing_count"] == 5
    assert summary["operator_clearance_missing_count"] == 5
    assert summary["operator_id_missing_count"] == 5
    assert summary["source_template_count"] == 1
    assert summary["source_stub_count"] == 5
    assert summary["linked_action_count"] == 5
    assert summary["first_field_key"] == "direct_native_or_source_authority"
    assert summary["first_blocker"] == "operator_value_missing"
    assert len(payload["rows"]) == 5
    assert (tmp_path / "KIT.md").is_file()
    kit_folder = tmp_path / summary["kit_folder"]
    assert (kit_folder / "README.md").is_file()
    assert (kit_folder / "operator_fill_template.csv").is_file()
    assert (kit_folder / "field_actions.csv").is_file()
    assert (kit_folder / "RERUN_COMMANDS.md").is_file()
    assert (kit_folder / "kit_manifest.json").is_file()


def test_first_operator_fill_kit_can_report_complete_candidate(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    worklist_json = tmp_path / "worklist.json"
    _write_json(worklist_json, _worklist_payload(ready=True))

    payload = mod.build_payload(mod.parse_args(_args(tmp_path, worklist_json)))

    assert payload["summary"]["organic_ligand_metric_first_operator_fill_kit_status"] == (
        "organic_ligand_metric_first_operator_fill_kit_complete"
    )
    assert payload["summary"]["field_ready_count"] == 5
    assert payload["summary"]["field_blocked_count"] == 0
    assert payload["summary"]["operator_value_missing_count"] == 0
    assert {row["fill_status"] for row in payload["rows"]} == {mod.READY_STATUS}


def test_first_operator_fill_kit_reports_missing_worklist(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(mod, "ROOT", tmp_path)

    payload = mod.build_payload(
        mod.parse_args(_args(tmp_path, tmp_path / "missing_worklist.json"))
    )

    assert payload["summary"]["organic_ligand_metric_first_operator_fill_kit_status"] == (
        "blocked_organic_ligand_metric_operator_fill_worklist_missing"
    )
    assert payload["summary"]["field_count"] == 0
    assert payload["rows"] == []

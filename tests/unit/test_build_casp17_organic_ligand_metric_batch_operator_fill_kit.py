import json
from pathlib import Path

from tools.casp17 import build_casp17_organic_ligand_metric_batch_operator_fill_kit as mod


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _row(candidate_rank: int, field_order: int, field_key: str, ready: bool = False) -> dict:
    candidate_id = f"organic_ligand_slot_candidate_{candidate_rank:03d}"
    ligand_id = f"ligand_{candidate_rank:03d}"
    value = f"value_{field_key}" if ready else ""
    evidence = f"evidence/{field_key}.md" if ready else ""
    clearance = "operator_confirmed_no_leak" if ready else ""
    operator = "operator_a" if ready else ""
    return {
        "fill_id": f"organic_ligand_metric_operator_fill_{candidate_rank}{field_order}",
        "candidate_rank": candidate_rank,
        "candidate_id": candidate_id,
        "target_id": f"HIST_COMPLEX_{candidate_rank:02d}",
        "ligand_id": ligand_id,
        "field_order": field_order,
        "field_key": field_key,
        "required_operator_value_format": "operator value",
        "source_operator_template_csv": f"casp17/intake/{ligand_id}/operator_evidence_template.csv",
        "source_evidence_stub_md": f"casp17/intake/{ligand_id}/field_evidence/{field_key}.md",
        "linked_action_md": f"casp17/actions/{ligand_id}/{field_key}/ACTION.md",
        "operator_value": value,
        "operator_evidence_ref": evidence,
        "operator_clearance": clearance,
        "operator_id": operator,
        "value_status": "value_present" if ready else "operator_value_missing",
        "evidence_ref_status": "evidence_ref_present" if ready else "operator_evidence_ref_missing",
        "clearance_status": "clearance_present" if ready else "operator_clearance_missing",
        "operator_id_status": "operator_id_present" if ready else "operator_id_missing",
        "fill_status": "field_ready_for_review_gate" if ready else "awaiting_operator_value",
        "first_blocker": "" if ready else "operator_value_missing",
        "next_action": "rerun review gate" if ready else f"fill operator_value for {field_key}",
    }


def test_batch_operator_fill_kit_collects_all_candidates(tmp_path: Path) -> None:
    worklist_json = tmp_path / "worklist.json"
    _write_json(
        worklist_json,
        {
            "summary": {
                "organic_ligand_metric_operator_fill_worklist_status": (
                    "awaiting_organic_ligand_metric_operator_fill_values"
                )
            },
            "rows": [
                _row(1, 1, "direct_native_or_source_authority"),
                _row(1, 2, "no_leak_provenance"),
                _row(2, 1, "direct_native_or_source_authority"),
                _row(2, 2, "no_leak_provenance", ready=True),
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
    assert summary["organic_ligand_metric_batch_operator_fill_kit_status"] == (
        "organic_ligand_metric_batch_operator_fill_kit_ready_for_operator_fill"
    )
    assert summary["candidate_count"] == 2
    assert summary["ready_candidate_count"] == 0
    assert summary["blocked_candidate_count"] == 2
    assert summary["field_count"] == 4
    assert summary["field_ready_count"] == 1
    assert summary["field_blocked_count"] == 3
    assert summary["operator_value_missing_count"] == 3
    assert summary["source_template_count"] == 2
    assert summary["source_stub_count"] == 4
    assert summary["linked_action_count"] == 4
    assert summary["first_candidate_id"] == "organic_ligand_slot_candidate_001"
    assert summary["first_field_key"] == "direct_native_or_source_authority"
    assert len(payload["candidate_rows"]) == 2
    assert (tmp_path / "batch" / "operator_fill_intake_batch.csv").is_file()
    assert (tmp_path / "batch" / "candidate_summary.csv").is_file()
    assert (tmp_path / "batch" / "01_ligand_001" / "README.md").is_file()
    assert (tmp_path / "BATCH.md").is_file()


def test_batch_operator_fill_kit_complete_when_all_rows_ready(tmp_path: Path) -> None:
    worklist_json = tmp_path / "worklist.json"
    _write_json(
        worklist_json,
        {
            "summary": {
                "organic_ligand_metric_operator_fill_worklist_status": (
                    "organic_ligand_metric_operator_fill_complete"
                )
            },
            "rows": [_row(1, 1, "direct_native_or_source_authority", ready=True)],
        },
    )
    payload = mod.build_payload(mod.parse_args(["--worklist-json", str(worklist_json)]))

    assert payload["summary"]["organic_ligand_metric_batch_operator_fill_kit_status"] == (
        "organic_ligand_metric_batch_operator_fill_kit_complete"
    )
    assert payload["summary"]["ready_candidate_count"] == 1
    assert payload["summary"]["blocked_candidate_count"] == 0


def test_batch_operator_fill_kit_blocks_missing_worklist(tmp_path: Path) -> None:
    payload = mod.build_payload(mod.parse_args(["--worklist-json", str(tmp_path / "missing.json")]))

    assert payload["summary"]["organic_ligand_metric_batch_operator_fill_kit_status"] == (
        "blocked_organic_ligand_metric_operator_fill_worklist_missing"
    )
    assert payload["summary"]["field_count"] == 0

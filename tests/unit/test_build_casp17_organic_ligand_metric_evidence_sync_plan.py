import json
from pathlib import Path

from tools import build_casp17_organic_ligand_metric_evidence_sync_plan as mod


FIELDS = [
    "direct_native_or_source_authority",
    "no_leak_provenance",
    "chronology_clearance",
    "ligand_pose_metric_inputs",
    "strict_blind_slot_mapping",
]


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _review_payload(tmp_path: Path, *, ready: bool) -> dict:
    rows = []
    gate_status = (
        mod.READY_GATE_STATUS
        if ready
        else "awaiting_organic_ligand_metric_evidence_review"
    )
    field_status = mod.READY_REVIEW_STATUS if ready else "blocked"
    for candidate_index in range(1, 3):
        candidate_id = f"organic_ligand_slot_candidate_{candidate_index:03d}"
        for field_order, field_key in enumerate(FIELDS, start=1):
            action_md = tmp_path / "actions" / candidate_id / field_key / "ACTION.md"
            action_md.parent.mkdir(parents=True, exist_ok=True)
            action_md.write_text("# linked action\n", encoding="utf-8")
            rows.append(
                {
                    "candidate_rank": candidate_index,
                    "candidate_id": candidate_id,
                    "target_id": f"T30{candidate_index:02d}",
                    "ligand_id": f"LIG{candidate_index:03d}",
                    "field_order": field_order,
                    "field_key": field_key,
                    "review_gate_status": field_status,
                    "template_operator_value": (
                        f"{field_key}_value" if ready else ""
                    ),
                    "template_operator_evidence_ref": (
                        f"evidence/{candidate_id}/{field_key}.md" if ready else ""
                    ),
                    "template_operator_clearance": "approved" if ready else "",
                    "template_operator_id": "operator-001" if ready else "",
                    "linked_action_md": str(action_md),
                    "first_blocker": (
                        "" if ready else "template_operator_value_missing"
                    ),
                    "next_action": (
                        f"sync reviewed {field_key}"
                        if ready
                        else f"fill operator_value for {field_key} in operator_evidence_template.csv"
                    ),
                }
            )
    return {
        "summary": {
            "organic_ligand_metric_evidence_review_gate_status": gate_status,
            "candidate_count": 2,
            "field_count": 10,
        },
        "rows": rows,
    }


def _run(tmp_path: Path, review_gate_json: Path) -> dict:
    args = mod.parse_args(
        [
            "--review-gate-json",
            str(review_gate_json),
            "--out-dir",
            str(tmp_path / "sync_plan"),
            "--out-json",
            str(tmp_path / "sync_plan.json"),
            "--out-csv",
            str(tmp_path / "sync_plan.csv"),
            "--out-md",
            str(tmp_path / "SYNC_PLAN.md"),
        ]
    )
    payload = mod.build_payload(args)
    mod.write_outputs(args, payload)
    return payload


def test_sync_plan_blocks_until_review_gate_is_ready(tmp_path):
    review_gate_json = tmp_path / "review_gate.json"
    _write_json(review_gate_json, _review_payload(tmp_path, ready=False))

    payload = _run(tmp_path, review_gate_json)
    summary = payload["summary"]

    assert summary["organic_ligand_metric_evidence_sync_plan_status"] == (
        "awaiting_organic_ligand_metric_evidence_review"
    )
    assert summary["candidate_count"] == 2
    assert summary["ready_candidate_count"] == 0
    assert summary["blocked_candidate_count"] == 2
    assert summary["action_count"] == 10
    assert summary["ready_action_count"] == 0
    assert summary["blocked_action_count"] == 10
    assert summary["destination_action_present_count"] == 10
    assert summary["destination_action_missing_count"] == 0
    assert summary["source_value_missing_count"] == 10
    assert summary["source_evidence_ref_missing_count"] == 10
    assert summary["source_clearance_missing_count"] == 10
    assert summary["source_operator_id_missing_count"] == 10
    assert summary["first_blocked_candidate_id"] == "organic_ligand_slot_candidate_001"
    assert summary["first_blocked_field_key"] == "direct_native_or_source_authority"
    assert summary["first_blocker"] == "template_operator_value_missing"
    assert payload["rows"][0]["action_status"] == "blocked_review_gate_not_ready"
    assert (tmp_path / "SYNC_PLAN.md").is_file()
    assert (tmp_path / "sync_plan.csv").is_file()
    assert (
        tmp_path
        / "sync_plan"
        / "01_organic_ligand_slot_candidate_001"
        / "SYNC.md"
    ).is_file()


def test_sync_plan_marks_ready_rows_when_reviewed_sources_are_present(tmp_path):
    review_gate_json = tmp_path / "review_gate.json"
    _write_json(review_gate_json, _review_payload(tmp_path, ready=True))

    payload = _run(tmp_path, review_gate_json)
    summary = payload["summary"]

    assert summary["organic_ligand_metric_evidence_sync_plan_status"] == (
        "organic_ligand_metric_evidence_sync_ready_dry_run"
    )
    assert summary["candidate_count"] == 2
    assert summary["ready_candidate_count"] == 2
    assert summary["blocked_candidate_count"] == 0
    assert summary["action_count"] == 10
    assert summary["ready_action_count"] == 10
    assert summary["blocked_action_count"] == 0
    assert summary["destination_action_present_count"] == 10
    assert summary["source_value_missing_count"] == 0
    assert summary["source_evidence_ref_missing_count"] == 0
    assert summary["source_clearance_missing_count"] == 0
    assert summary["source_operator_id_missing_count"] == 0
    assert {row["action_status"] for row in payload["rows"]} == {"ready_to_sync"}


def test_sync_plan_reports_missing_review_gate(tmp_path):
    review_gate_json = tmp_path / "missing_review_gate.json"

    payload = _run(tmp_path, review_gate_json)
    summary = payload["summary"]

    assert summary["organic_ligand_metric_evidence_sync_plan_status"] == (
        "blocked_organic_ligand_metric_evidence_review_gate_missing"
    )
    assert summary["candidate_count"] == 0
    assert summary["action_count"] == 0
    assert payload["rows"] == []
    assert (tmp_path / "SYNC_PLAN.md").is_file()

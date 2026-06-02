import json
from pathlib import Path

from tools import build_casp17_organic_ligand_metric_operator_fill_worklist as mod


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


def _review_gate_payload(tmp_path: Path, *, ready: bool) -> dict:
    rows = []
    for candidate_rank in range(1, 3):
        candidate_id = f"organic_ligand_slot_candidate_{candidate_rank:03d}"
        ligand_id = f"ligand_{candidate_rank:03d}"
        packet = tmp_path / "intake" / f"{candidate_rank:02d}_{ligand_id}"
        template_csv = packet / "operator_evidence_template.csv"
        for field_order, field_key in enumerate(FIELDS, start=1):
            stub_md = packet / "field_evidence" / f"{field_key}.md"
            action_md = tmp_path / "actions" / candidate_id / field_key / "ACTION.md"
            rows.append(
                {
                    "candidate_rank": candidate_rank,
                    "candidate_id": candidate_id,
                    "target_id": f"HIST_COMPLEX_{candidate_rank:02d}",
                    "ligand_id": ligand_id,
                    "field_order": field_order,
                    "field_key": field_key,
                    "required_operator_value_format": "operator reviewed evidence",
                    "operator_template_csv": str(template_csv),
                    "evidence_stub_md": str(stub_md),
                    "linked_action_md": str(action_md),
                    "template_operator_value": "reviewed_value" if ready else "",
                    "template_operator_evidence_ref": "evidence.md" if ready else "",
                    "template_operator_clearance": "approved" if ready else "",
                    "template_operator_id": "operator_001" if ready else "",
                    "review_gate_status": (
                        mod.READY_REVIEW_STATUS if ready else "blocked"
                    ),
                    "first_blocker": (
                        "" if ready else "template_operator_value_missing"
                    ),
                }
            )
    return {
        "summary": {
            "organic_ligand_metric_evidence_review_gate_status": (
                "organic_ligand_metric_evidence_review_ready"
                if ready
                else "awaiting_organic_ligand_metric_evidence_review"
            )
        },
        "rows": rows,
    }


def _args(tmp_path: Path, review_gate_json: Path) -> list[str]:
    return [
        "--review-gate-json",
        str(review_gate_json),
        "--out-dir",
        str(tmp_path / "worklist"),
        "--out-json",
        str(tmp_path / "worklist.json"),
        "--out-csv",
        str(tmp_path / "worklist.csv"),
        "--out-md",
        str(tmp_path / "WORKLIST.md"),
    ]


def test_operator_fill_worklist_blocks_blank_review_gate_rows(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    review_gate_json = tmp_path / "review_gate.json"
    _write_json(review_gate_json, _review_gate_payload(tmp_path, ready=False))

    args = mod.parse_args(_args(tmp_path, review_gate_json))
    payload = mod.build_payload(args)
    mod.write_outputs(args, payload)

    summary = payload["summary"]
    assert summary["organic_ligand_metric_operator_fill_worklist_status"] == (
        "awaiting_organic_ligand_metric_operator_fill_values"
    )
    assert summary["candidate_count"] == 2
    assert summary["ready_candidate_count"] == 0
    assert summary["blocked_candidate_count"] == 2
    assert summary["field_action_count"] == 10
    assert summary["field_ready_count"] == 0
    assert summary["field_blocked_count"] == 10
    assert summary["operator_value_missing_count"] == 10
    assert summary["operator_evidence_ref_missing_count"] == 10
    assert summary["operator_clearance_missing_count"] == 10
    assert summary["operator_id_missing_count"] == 10
    assert summary["operator_template_count"] == 2
    assert summary["evidence_stub_count"] == 10
    assert summary["linked_action_count"] == 10
    assert summary["candidate_fill_folder_count"] == 2
    assert summary["first_candidate_id"] == "organic_ligand_slot_candidate_001"
    assert summary["first_field_key"] == "direct_native_or_source_authority"
    assert summary["first_blocker"] == "operator_value_missing"
    assert payload["rows"][0]["fill_status"] == "awaiting_operator_value"
    assert (tmp_path / "WORKLIST.md").is_file()
    assert (tmp_path / "worklist.csv").is_file()
    assert (tmp_path / "worklist/01_ligand_001/OPERATOR_FILL.md").is_file()


def test_operator_fill_worklist_completes_when_review_rows_are_ready(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    review_gate_json = tmp_path / "review_gate.json"
    _write_json(review_gate_json, _review_gate_payload(tmp_path, ready=True))

    payload = mod.build_payload(mod.parse_args(_args(tmp_path, review_gate_json)))

    assert payload["summary"]["organic_ligand_metric_operator_fill_worklist_status"] == (
        "organic_ligand_metric_operator_fill_complete"
    )
    assert payload["summary"]["ready_candidate_count"] == 2
    assert payload["summary"]["field_ready_count"] == 10
    assert payload["summary"]["field_blocked_count"] == 0
    assert payload["summary"]["operator_value_missing_count"] == 0
    assert {row["fill_status"] for row in payload["rows"]} == {"field_ready_for_review_gate"}


def test_operator_fill_worklist_reports_missing_review_gate(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(mod, "ROOT", tmp_path)

    payload = mod.build_payload(
        mod.parse_args(_args(tmp_path, tmp_path / "missing_review_gate.json"))
    )

    assert payload["summary"]["organic_ligand_metric_operator_fill_worklist_status"] == (
        "blocked_organic_ligand_metric_evidence_review_gate_missing"
    )
    assert payload["summary"]["field_action_count"] == 0
    assert payload["rows"] == []

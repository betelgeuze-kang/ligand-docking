from __future__ import annotations

import csv
import json
from pathlib import Path

from tools.casp17 import build_casp17_organic_ligand_metric_evidence_review_gate as mod


FIELDS = [
    "direct_native_or_source_authority",
    "no_leak_provenance",
    "prediction_chronology",
    "ligand_pose_reference",
    "strict_blind_slot_mapping",
]


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "field_key",
                "operator_value",
                "operator_evidence_ref",
                "operator_clearance",
                "operator_id",
                "required_operator_value_format",
                "evidence_stub_md",
                "linked_action_md",
                "notes",
            ],
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)


def _write_stub(path: Path, *, ready: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    value = "reviewed_value" if ready else "``"
    evidence = "evidence.md" if ready else "``"
    clearance = "approved" if ready else "``"
    operator = "operator_001" if ready else "``"
    path.write_text(
        "\n".join(
            [
                "# Evidence Stub",
                "",
                "## Operator Evidence",
                "",
                f"- operator_value: `{value}`" if ready else "- operator_value: ``",
                f"- operator_evidence_ref: `{evidence}`" if ready else "- operator_evidence_ref: ``",
                f"- operator_clearance: `{clearance}`" if ready else "- operator_clearance: ``",
                f"- operator_id: `{operator}`" if ready else "- operator_id: ``",
                "",
            ]
        ),
        encoding="utf-8",
    )


def _write_intake(tmp_path: Path, *, ready: bool = False) -> Path:
    rows = []
    for rank, candidate_id in enumerate(["organic_ligand_slot_candidate_001", "organic_ligand_slot_candidate_002"], start=1):
        ligand_id = f"ligand_{rank:03d}"
        packet = tmp_path / "packets" / f"{rank:02d}_{ligand_id}"
        template = packet / "operator_evidence_template.csv"
        template_rows = []
        for field_order, field_key in enumerate(FIELDS, start=1):
            stub = packet / "field_evidence" / f"{field_key}.md"
            _write_stub(stub, ready=ready)
            template_rows.append(
                {
                    "field_key": field_key,
                    "operator_value": "reviewed_value" if ready else "",
                    "operator_evidence_ref": "evidence.md" if ready else "",
                    "operator_clearance": "approved" if ready else "",
                    "operator_id": "operator_001" if ready else "",
                    "required_operator_value_format": "operator reviewed evidence",
                    "evidence_stub_md": str(stub),
                    "linked_action_md": f"actions/{candidate_id}/{field_key}/ACTION.md",
                    "notes": "",
                }
            )
            rows.append(
                {
                    "candidate_rank": rank,
                    "candidate_id": candidate_id,
                    "target_id": f"HIST_COMPLEX_{rank:02d}",
                    "ligand_id": ligand_id,
                    "field_order": field_order,
                    "field_key": field_key,
                    "evidence_request_kind": "operator_evidence",
                    "required_operator_value_format": "operator reviewed evidence",
                    "operator_template_csv": str(template),
                    "evidence_stub_md": str(stub),
                    "linked_action_md": f"actions/{candidate_id}/{field_key}/ACTION.md",
                }
            )
        _write_csv(template, template_rows)
    intake = tmp_path / "intake.json"
    _write_json(
        intake,
        {
            "summary": {
                "organic_ligand_metric_evidence_intake_status": (
                    "awaiting_organic_ligand_metric_evidence_intake"
                )
            },
            "rows": rows,
        },
    )
    return intake


def _args(tmp_path: Path, intake: Path) -> list[str]:
    return [
        "--evidence-intake-json",
        str(intake),
        "--out-dir",
        str(tmp_path / "review"),
        "--out-json",
        str(tmp_path / "review.json"),
        "--out-csv",
        str(tmp_path / "review.csv"),
        "--out-md",
        str(tmp_path / "REVIEW.md"),
    ]


def test_organic_ligand_metric_evidence_review_gate_blocks_blank_templates_and_stubs(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    intake = _write_intake(tmp_path, ready=False)
    args = mod.parse_args(_args(tmp_path, intake))

    payload = mod.build_payload(args)
    mod.write_outputs(args, payload)

    summary = payload["summary"]
    assert summary["organic_ligand_metric_evidence_review_gate_status"] == (
        "awaiting_organic_ligand_metric_evidence_review"
    )
    assert summary["candidate_count"] == 2
    assert summary["ready_candidate_count"] == 0
    assert summary["blocked_candidate_count"] == 2
    assert summary["field_count"] == 10
    assert summary["ready_field_count"] == 0
    assert summary["blocked_field_count"] == 10
    assert summary["template_operator_value_missing_count"] == 10
    assert summary["template_operator_evidence_ref_missing_count"] == 10
    assert summary["template_operator_clearance_missing_count"] == 10
    assert summary["template_operator_id_missing_count"] == 10
    assert summary["stub_present_count"] == 10
    assert summary["stub_missing_count"] == 0
    assert summary["stub_evidence_missing_count"] == 10
    assert summary["policy_pass_count"] == 0
    assert summary["policy_blocked_count"] == 10
    assert summary["first_blocked_field_key"] == "direct_native_or_source_authority"
    assert summary["first_blocker"] == "template_operator_value_missing"
    assert payload["rows"][0]["stub_status"] == "stub_present"
    assert payload["rows"][0]["review_gate_status"] == "blocked"
    assert (tmp_path / "review.json").is_file()
    assert (tmp_path / "review.csv").is_file()
    assert (tmp_path / "REVIEW.md").is_file()
    assert (tmp_path / "review/01_ligand_001/REVIEW.md").is_file()


def test_organic_ligand_metric_evidence_review_gate_ready_when_values_present(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    intake = _write_intake(tmp_path, ready=True)

    payload = mod.build_payload(mod.parse_args(_args(tmp_path, intake)))

    assert payload["summary"]["organic_ligand_metric_evidence_review_gate_status"] == (
        "organic_ligand_metric_evidence_review_ready"
    )
    assert payload["summary"]["ready_candidate_count"] == 2
    assert payload["summary"]["ready_field_count"] == 10
    assert payload["summary"]["blocked_field_count"] == 0
    assert {row["review_gate_status"] for row in payload["rows"]} == {
        "field_ready_for_organic_ligand_metric_review"
    }


def test_organic_ligand_metric_evidence_review_gate_blocks_missing_intake(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(mod, "ROOT", tmp_path)

    payload = mod.build_payload(
        mod.parse_args(_args(tmp_path, tmp_path / "missing_intake.json"))
    )

    assert payload["summary"]["organic_ligand_metric_evidence_review_gate_status"] == (
        "blocked_organic_ligand_metric_evidence_intake_missing"
    )
    assert payload["summary"]["field_count"] == 0
    assert payload["rows"] == []

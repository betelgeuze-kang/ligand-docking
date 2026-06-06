from __future__ import annotations

import csv
import json
from pathlib import Path

from tools.casp17 import build_casp17_historical_seed_first_clearance_no_leak_gate as mod


INTAKE_COLUMNS = [
    "field_name",
    "current_value",
    "required_value_policy",
    "weak_local_hint",
    "weak_local_hint_source",
    "evidence_ref",
    "operator_value",
    "operator_clearance",
    "notes",
]

POLICIES = [
    ("no_leak_evidence_ref", "independent_no_leak_evidence_ref_required", "evidence/no-leak.md"),
    ("leakage_clearance", "clear", "clear"),
    ("operator_clearance", "operator_cleared", "operator_cleared"),
    ("operator", "operator_id", "tester"),
    ("prediction_created_at", "iso_date", "2025-01-01"),
    ("native_release_date", "authoritative_release_iso_date", "2025-02-01"),
    ("prediction_generated_before_native_release", "true", "true"),
    ("public_template_or_native_used_for_prediction", "false", "false"),
    ("other_team_model_used", "false", "false"),
    ("post_release_information_used", "false", "false"),
]


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_intake(path: Path, *, filled: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=INTAKE_COLUMNS, lineterminator="\n")
        writer.writeheader()
        for field_name, policy, valid_value in POLICIES:
            writer.writerow(
                {
                    "field_name": field_name,
                    "current_value": "",
                    "required_value_policy": policy,
                    "weak_local_hint": "2025-01-01" if field_name == "prediction_created_at" else "",
                    "weak_local_hint_source": (
                        "prediction_path_date" if field_name == "prediction_created_at" else ""
                    ),
                    "evidence_ref": "casp17/no_leak_dossier.md",
                    "operator_value": valid_value if filled else "",
                    "operator_clearance": "clear" if filled else "",
                    "notes": "operator-only no-leak provenance",
                }
            )


def _write_kit(path: Path, intake: Path, *, status: str = "operator_no_leak_intake_ready") -> None:
    _write_json(
        path,
        {
            "summary": {
                "first_clearance_kit_status": status,
                "target_id": "HIST_CHIGNOLIN",
                "benchmark_id": "hist_seed_chignolin",
                "no_leak_operator_intake_csv": str(intake),
                "promotion_preview_csv": str(intake.parent / "promotion_preview.csv"),
            }
        },
    )


def _args(tmp_path: Path, kit: Path) -> list[str]:
    return [
        "--first-clearance-kit-json",
        str(kit),
        "--out-json",
        str(tmp_path / "gate.json"),
        "--out-csv",
        str(tmp_path / "gate.csv"),
        "--out-md",
        str(tmp_path / "GATE.md"),
    ]


def test_no_leak_gate_blocks_blank_operator_intake(tmp_path: Path) -> None:
    intake = tmp_path / "kit" / "no_leak_operator_intake.csv"
    kit = tmp_path / "first_clearance_kit.json"
    _write_intake(intake, filled=False)
    _write_kit(kit, intake)

    args = mod.parse_args(_args(tmp_path, kit))
    payload = mod.build_payload(args)
    mod.write_outputs(args, payload)

    summary = payload["summary"]
    assert summary["first_clearance_no_leak_gate_status"] == "awaiting_operator_no_leak_values"
    assert summary["field_count"] == 10
    assert summary["ready_field_count"] == 0
    assert summary["blocked_field_count"] == 10
    assert summary["operator_value_missing_count"] == 10
    assert summary["operator_clearance_missing_count"] == 10
    assert summary["policy_blocked_count"] == 10
    assert summary["weak_hint_count"] == 1
    assert summary["first_blocked_field"] == "no_leak_evidence_ref"
    assert summary["first_blocker"] == "operator_value_missing"
    assert payload["rows"][0]["field_gate_status"] == "awaiting_operator_input"
    assert (tmp_path / "gate.csv").is_file()
    assert "Claim Boundary" in (tmp_path / "GATE.md").read_text(encoding="utf-8")


def test_no_leak_gate_marks_policy_shaped_operator_intake_ready(tmp_path: Path) -> None:
    intake = tmp_path / "kit" / "no_leak_operator_intake.csv"
    kit = tmp_path / "first_clearance_kit.json"
    _write_intake(intake, filled=True)
    _write_kit(kit, intake)

    payload = mod.build_payload(mod.parse_args(_args(tmp_path, kit)))

    summary = payload["summary"]
    assert summary["first_clearance_no_leak_gate_status"] == "first_clearance_no_leak_ready_for_promotion_review"
    assert summary["ready_field_count"] == 10
    assert summary["blocked_field_count"] == 0
    assert summary["operator_value_present_count"] == 10
    assert summary["operator_clearance_present_count"] == 10
    assert summary["policy_pass_count"] == 10
    assert summary["policy_blocked_count"] == 0
    assert summary["first_blocked_field"] == ""
    assert summary["first_blocker"] == ""
    assert {row["field_gate_status"] for row in payload["rows"]} == {"ready_for_no_leak_review"}


def test_no_leak_gate_blocks_missing_kit(tmp_path: Path) -> None:
    args = mod.parse_args(_args(tmp_path, tmp_path / "missing_kit.json"))
    payload = mod.build_payload(args)

    assert payload["summary"]["first_clearance_no_leak_gate_status"] == "blocked_first_clearance_kit_missing"
    assert payload["summary"]["field_count"] == 0
    assert payload["rows"] == []

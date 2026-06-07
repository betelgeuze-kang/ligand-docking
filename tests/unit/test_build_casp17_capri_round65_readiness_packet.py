from __future__ import annotations

import csv
import json
from pathlib import Path

from tools.casp17 import build_casp17_capri_round65_readiness_packet as mod


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def test_capri_round65_packet_blocks_until_registration_and_builds_target_folders(tmp_path: Path) -> None:
    args = mod.parse_args(
        [
            "--as-of-date",
            "2026-05-31",
            "--target-dir",
            str(tmp_path / "targets"),
            "--registration-csv",
            str(tmp_path / "registration.csv"),
            "--out-json",
            str(tmp_path / "packet.json"),
            "--out-csv",
            str(tmp_path / "targets.csv"),
            "--out-md",
            str(tmp_path / "README.md"),
        ]
    )

    payload = mod.build_payload(args)
    mod.write_outputs(args, payload)

    assert payload["summary"]["capri_readiness_status"] == "blocked_registration_role_selection"
    assert payload["summary"]["round_status"] == "Active"
    assert payload["summary"]["registration_end"] == "2026-06-01 midnight"
    assert payload["summary"]["registration_days_remaining"] == 1
    assert payload["summary"]["registration_required_field_count"] == 4
    assert payload["summary"]["registration_ready_field_count"] == 0
    assert payload["summary"]["target_count"] == 13
    assert payload["summary"]["active_target_count"] == 11
    assert payload["summary"]["scorer_priority_target_count"] == 4
    assert payload["summary"]["predictor_priority_target_count"] == 7
    assert payload["summary"]["blocked_target_count"] == 11
    assert payload["rows"][3]["capri_target_id"] == "T330"
    assert payload["rows"][3]["recommended_role"] == "scorer"
    assert payload["rows"][8]["capri_target_id"] == "T335"
    assert payload["rows"][8]["recommended_role"] == "predictor_then_scorer"

    registration_rows = _read_csv(tmp_path / "registration.csv")
    assert [row["field"] for row in registration_rows] == [
        "casp_team_id",
        "capri_registration_confirmed",
        "selected_role",
        "submitter_contact",
    ]
    target_action = tmp_path / "targets" / "T330_T2313" / "ACTION.md"
    assert target_action.exists()
    assert "scoring closes on registration-deadline day" in target_action.read_text(encoding="utf-8")
    assert "Registration Gate" in (tmp_path / "README.md").read_text(encoding="utf-8")


def test_capri_round65_packet_moves_to_format_preflight_after_operator_registration(tmp_path: Path) -> None:
    registration_csv = tmp_path / "registration.csv"
    with registration_csv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=mod.REGISTRATION_COLUMNS)
        writer.writeheader()
        for field, _notes in mod.REGISTRATION_FIELDS:
            writer.writerow(
                {
                    "field": field,
                    "value": "both" if field == "selected_role" else "provided",
                    "evidence_ref": f"evidence/{field}.md",
                    "operator_clearance": "operator_cleared",
                    "notes": "",
                }
            )

    args = mod.parse_args(
        [
            "--as-of-date",
            "2026-05-31",
            "--target-dir",
            str(tmp_path / "targets"),
            "--registration-csv",
            str(registration_csv),
            "--out-json",
            str(tmp_path / "packet.json"),
            "--out-csv",
            str(tmp_path / "targets.csv"),
            "--out-md",
            str(tmp_path / "README.md"),
        ]
    )

    payload = mod.build_payload(args)
    mod.write_outputs(args, payload)

    assert payload["summary"]["capri_readiness_status"] == "format_preflight_required"
    assert payload["summary"]["registration_gate_status"] == "ready"
    assert payload["summary"]["registration_ready_field_count"] == 4
    assert payload["summary"]["blocked_target_count"] == 0
    assert payload["summary"]["format_preflight_target_count"] == 11
    written = json.loads((tmp_path / "packet.json").read_text(encoding="utf-8"))
    assert written["summary"]["source_format"] == mod.SOURCE_FORMAT

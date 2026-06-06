from __future__ import annotations

import csv
import json
from pathlib import Path

from tools.casp17 import build_casp17_competitive_floor_target_identity_clearance_replacement_decision_bundle as mod


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _args(tmp_path: Path) -> list[str]:
    return [
        "--duplicate-resolution-json",
        str(tmp_path / "duplicate_resolution.json"),
        "--out-dir",
        str(tmp_path / "decisions"),
        "--out-json",
        str(tmp_path / "decision_bundle.json"),
        "--out-csv",
        str(tmp_path / "decision_bundle.csv"),
        "--out-md",
        str(tmp_path / "DECISION_BUNDLE.md"),
    ]


def _duplicate_row(replace_id: str, candidate_id: str) -> dict[str, str]:
    return {
        "replace_target_id": replace_id,
        "replace_target_name": f"Blocked {replace_id}",
        "candidate_rank": "1",
        "candidate_target_id": candidate_id,
        "candidate_target_name": f"Candidate {candidate_id}",
        "queue_candidate_status": "candidate_ready_for_operator_clearance",
        "source_repair_status": "source_ready",
        "resolution_status": "blocked_duplicate_candidate_assignment",
        "safe_unique_ready_candidate": "false",
        "duplicate_candidate": "true",
        "duplicate_candidate_for_replace_target_ids": "H1001",
        "blockers": "duplicate_candidate_target_id",
    }


def _blocked_row(replace_id: str, candidate_id: str) -> dict[str, str]:
    return {
        "replace_target_id": replace_id,
        "replace_target_name": f"Blocked {replace_id}",
        "candidate_rank": "2",
        "candidate_target_id": candidate_id,
        "candidate_target_name": f"Candidate {candidate_id}",
        "queue_candidate_status": "blocked_current_target_collision",
        "source_repair_status": "blocked_current_target_collision",
        "resolution_status": "blocked_current_target_collision",
        "safe_unique_ready_candidate": "false",
        "duplicate_candidate": "false",
        "blockers": "current_target_name_collision",
    }


def _safe_unique_row(replace_id: str, candidate_id: str) -> dict[str, str]:
    return {
        "replace_target_id": replace_id,
        "replace_target_name": f"Blocked {replace_id}",
        "candidate_rank": "2",
        "candidate_target_id": candidate_id,
        "candidate_target_name": f"Candidate {candidate_id}",
        "queue_candidate_status": "candidate_ready_for_operator_clearance",
        "source_repair_status": "source_ready",
        "resolution_status": "safe_unique_ready_candidate",
        "safe_unique_ready_candidate": "true",
        "duplicate_candidate": "false",
        "blockers": "",
    }


def test_decision_bundle_materializes_open_operator_templates(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    _write_json(
        tmp_path / "duplicate_resolution.json",
        {"rows": [_duplicate_row("H1002", "H2001"), _blocked_row("H1002", "H2003")]},
    )
    args = mod.parse_args(_args(tmp_path))

    payload = mod.build_payload(args)
    mod.write_outputs(args, payload)

    assert payload["summary"]["decision_bundle_status"] == "open_operator_decision"
    assert payload["summary"]["decision_target_count"] == 1
    assert payload["summary"]["open_decision_count"] == 1
    assert payload["summary"]["new_unique_template_count"] == 1
    assert payload["summary"]["duplicate_exception_template_count"] == 1
    row = payload["rows"][0]
    assert row["decision_status"] == "open_operator_decision"
    assert row["duplicate_candidate_ids"] == "H2001"
    assert row["next_action"] == mod.OPEN_DECISION_ACTION
    assert Path(row["decision_md"]).is_file()
    new_unique = _read_csv(Path(row["new_unique_candidate_intake_csv"]))
    assert new_unique[0]["proposed_candidate_target_id"] == "REQUIRED_NEW_CLOSED_PROTEIN_TARGET_ID"
    duplicate_exception = _read_csv(Path(row["duplicate_reuse_exception_csv"]))
    assert duplicate_exception[0]["duplicate_candidate_target_id"] == "H2001"
    assert (tmp_path / "DECISION_BUNDLE.md").is_file()


def test_decision_bundle_marks_ready_when_safe_unique_candidate_exists(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    _write_json(
        tmp_path / "duplicate_resolution.json",
        {"rows": [_duplicate_row("H1002", "H2001"), _safe_unique_row("H1002", "H2002")]},
    )
    args = mod.parse_args(_args(tmp_path))

    payload = mod.build_payload(args)

    assert payload["summary"]["decision_bundle_status"] == "ready_for_unique_replacement_workorder"
    assert payload["summary"]["ready_decision_count"] == 1
    assert payload["summary"]["safe_unique_ready_candidate_count"] == 1
    assert payload["rows"][0]["decision_status"] == "ready_for_unique_replacement_workorder"
    assert payload["rows"][0]["safe_unique_candidate_ids"] == "H2002"

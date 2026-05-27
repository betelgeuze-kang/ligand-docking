from __future__ import annotations

import csv
import json
from pathlib import Path

from tools import build_casp17_competitive_floor_target_identity_clearance_replacement_decision_preflight as mod


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _args(tmp_path: Path) -> list[str]:
    return [
        "--decision-bundle-json",
        str(tmp_path / "decision_bundle.json"),
        "--out-json",
        str(tmp_path / "preflight.json"),
        "--out-csv",
        str(tmp_path / "preflight.csv"),
        "--out-md",
        str(tmp_path / "PREFLIGHT.md"),
    ]


def _decision_row(tmp_path: Path) -> dict[str, str]:
    folder = tmp_path / "decision"
    return {
        "replace_target_id": "H1002",
        "replace_target_name": "Blocked target",
        "decision_status": "open_operator_decision",
        "decision_folder": str(folder),
        "new_unique_candidate_intake_csv": str(folder / "new_unique_candidate_intake.csv"),
        "duplicate_reuse_exception_csv": str(folder / "duplicate_reuse_exception.csv"),
        "decision_md": str(folder / "DECISION.md"),
    }


def _write_placeholder_decision_files(row: dict[str, str]) -> None:
    _write_csv(
        Path(row["new_unique_candidate_intake_csv"]),
        [
            {
                "proposed_candidate_target_id": "REQUIRED_NEW_CLOSED_PROTEIN_TARGET_ID",
                "proposed_candidate_name": "REQUIRED_TARGET_NAME",
                "closed_protein_target": "REQUIRED_TRUE_CONFIRMATION",
                "current_target_collision_checked": "REQUIRED_TRUE_CONFIRMATION",
                "cancellation_checked": "REQUIRED_TRUE_CONFIRMATION",
                "local_prediction_pdb": "REQUIRED_LOCAL_PREDICTION_PDB",
                "raw_validation_json": "REQUIRED_RAW_VALIDATION_JSON",
                "scorecard_json": "REQUIRED_INTERNAL_SCORECARD_JSON",
                "no_leak_evidence_ref": "REQUIRED_NO_LEAK_EVIDENCE_REF",
                "operator_clearance": "REQUIRED_OPERATOR_CLEARANCE",
                "operator": "REQUIRED_OPERATOR_ID",
            }
        ],
    )
    _write_csv(
        Path(row["duplicate_reuse_exception_csv"]),
        [
            {
                "duplicate_candidate_target_id": "H2001",
                "allow_duplicate_reuse": "REQUIRED_FALSE_UNLESS_EXPLICITLY_APPROVED",
                "no_leak_evidence_ref": "REQUIRED_NO_LEAK_EVIDENCE_REF",
                "operator_clearance": "REQUIRED_OPERATOR_CLEARANCE",
                "operator": "REQUIRED_OPERATOR_ID",
                "approval_date": "YYYY-MM-DD",
                "rationale": "REQUIRED_RATIONALE",
            }
        ],
    )


def test_decision_preflight_awaits_placeholder_operator_input(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    row = _decision_row(tmp_path)
    _write_placeholder_decision_files(row)
    _write_json(tmp_path / "decision_bundle.json", {"summary": {"decision_bundle_status": "open_operator_decision"}, "rows": [row]})
    args = mod.parse_args(_args(tmp_path))

    payload = mod.build_payload(args)
    mod.write_outputs(args, payload)

    assert payload["summary"]["decision_preflight_status"] == "awaiting_operator_decision"
    assert payload["summary"]["awaiting_operator_decision_count"] == 1
    assert payload["summary"]["ready_new_unique_count"] == 0
    assert payload["summary"]["ready_duplicate_exception_count"] == 0
    assert payload["rows"][0]["new_unique_status"] == "awaiting_operator_input"
    assert "proposed_candidate_target_id_required" in payload["rows"][0]["new_unique_blockers"]
    assert payload["rows"][0]["duplicate_exception_status"] == "awaiting_operator_input"
    assert "allow_duplicate_reuse_required" in payload["rows"][0]["duplicate_exception_blockers"]
    assert (tmp_path / "PREFLIGHT.md").is_file()


def test_decision_preflight_accepts_filled_new_unique_candidate(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    row = _decision_row(tmp_path)
    prediction = tmp_path / "H2002_model_1.pdb"
    raw_validation = tmp_path / "H2002_raw.json"
    scorecard = tmp_path / "H2002_scorecard.json"
    prediction.write_text("ATOM      1  CA  ALA A   1       0.000   1.000   2.000  1.00 70.00           C  \n", encoding="utf-8")
    raw_validation.write_text("{}", encoding="utf-8")
    scorecard.write_text("{}", encoding="utf-8")
    _write_csv(
        Path(row["new_unique_candidate_intake_csv"]),
        [
            {
                "proposed_candidate_target_id": "H2002",
                "proposed_candidate_name": "Candidate H2002",
                "closed_protein_target": "true",
                "current_target_collision_checked": "true",
                "cancellation_checked": "true",
                "local_prediction_pdb": str(prediction),
                "raw_validation_json": str(raw_validation),
                "scorecard_json": str(scorecard),
                "no_leak_evidence_ref": "operator-note-1",
                "operator_clearance": "clear",
                "operator": "tester",
            }
        ],
    )
    _write_csv(
        Path(row["duplicate_reuse_exception_csv"]),
        [
            {
                "duplicate_candidate_target_id": "H2001",
                "allow_duplicate_reuse": "false",
                "no_leak_evidence_ref": "REQUIRED_NO_LEAK_EVIDENCE_REF",
                "operator_clearance": "REQUIRED_OPERATOR_CLEARANCE",
                "operator": "REQUIRED_OPERATOR_ID",
                "approval_date": "YYYY-MM-DD",
                "rationale": "REQUIRED_RATIONALE",
            }
        ],
    )
    _write_json(tmp_path / "decision_bundle.json", {"summary": {"decision_bundle_status": "open_operator_decision"}, "rows": [row]})
    args = mod.parse_args(_args(tmp_path))

    payload = mod.build_payload(args)

    assert payload["summary"]["decision_preflight_status"] == "ready"
    assert payload["summary"]["ready_new_unique_count"] == 1
    assert payload["rows"][0]["preflight_status"] == "ready_new_unique_candidate"
    assert payload["rows"][0]["ready_branch"] == "new_unique"
    assert payload["rows"][0]["new_unique_blockers"] == ""


def test_decision_preflight_accepts_explicit_duplicate_exception(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    row = _decision_row(tmp_path)
    _write_placeholder_decision_files(row)
    _write_csv(
        Path(row["duplicate_reuse_exception_csv"]),
        [
            {
                "duplicate_candidate_target_id": "H2001",
                "allow_duplicate_reuse": "true",
                "no_leak_evidence_ref": "operator-note-2",
                "operator_clearance": "clear",
                "operator": "tester",
                "approval_date": "2026-05-28",
                "rationale": "single candidate is intentionally reused for paired antibody-complex replay rows",
            }
        ],
    )
    _write_json(tmp_path / "decision_bundle.json", {"summary": {"decision_bundle_status": "open_operator_decision"}, "rows": [row]})
    args = mod.parse_args(_args(tmp_path))

    payload = mod.build_payload(args)

    assert payload["summary"]["decision_preflight_status"] == "ready"
    assert payload["summary"]["ready_duplicate_exception_count"] == 1
    assert payload["rows"][0]["preflight_status"] == "ready_duplicate_reuse_exception"
    assert payload["rows"][0]["ready_branch"] == "duplicate_reuse_exception"
    assert payload["rows"][0]["duplicate_exception_blockers"] == ""

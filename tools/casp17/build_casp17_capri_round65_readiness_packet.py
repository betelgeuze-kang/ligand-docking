#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]

DEFAULT_OUT_JSON = "casp17/capri_round65/capri_round65_readiness_current.json"
DEFAULT_OUT_CSV = "casp17/capri_round65/capri_round65_target_worklist_current.csv"
DEFAULT_OUT_MD = "casp17/capri_round65/README.md"
DEFAULT_TARGET_DIR = "casp17/capri_round65/targets"
DEFAULT_REGISTRATION_CSV = "casp17/capri_round65/registration/operator_registration_status.csv"

SOURCE_ROUND = "https://www.ebi.ac.uk/pdbe/complex-pred/capri/round/65/"
SOURCE_MAIN = "https://www.ebi.ac.uk/pdbe/complex-pred/capri/"
SOURCE_FORMAT = "https://www.ebi.ac.uk/pdbe/complex-pred/capri/capri-format/"
SOURCE_CASP_CAPRI = "https://www.ebi.ac.uk/pdbe/complex-pred/capri/casp-capri/"

REGISTRATION_FIELDS = [
    ("casp_team_id", "12-digit CASP Team ID for joint CASP-CAPRI predictor/server participation"),
    ("capri_registration_confirmed", "true after CAPRI Round 65 registration is confirmed"),
    ("selected_role", "predictor_server, scorer, or both"),
    ("submitter_contact", "operator/account owner contact for upload and confirmation receipts"),
]

TARGETS = [
    {
        "capri_target_id": "T327",
        "casp_target_id": "H1311",
        "status": "Closed",
        "prediction_start": "2026-04-29 22:23",
        "prediction_server_end": "2026-05-02 17:00",
        "prediction_human_end": "2026-05-13 17:00",
        "scoring_start": "2026-05-14 09:00",
        "scoring_end": "2026-05-18 23:59",
        "recommended_role": "closed",
        "action": "closed; preserve only as schedule context",
    },
    {
        "capri_target_id": "T328",
        "casp_target_id": "H2324",
        "status": "Closed",
        "prediction_start": "2026-05-07 17:30",
        "prediction_server_end": "2026-05-10 17:00",
        "prediction_human_end": "2026-05-21 17:00",
        "scoring_start": "2026-05-22 09:00",
        "scoring_end": "2026-05-26 23:59",
        "recommended_role": "closed",
        "action": "closed; preserve only as schedule context",
    },
    {
        "capri_target_id": "T329",
        "casp_target_id": "H2312",
        "status": "Scoring challenge",
        "prediction_start": "2026-05-13 17:30",
        "prediction_server_end": "2026-05-16 17:00",
        "prediction_human_end": "2026-05-27 17:00",
        "scoring_start": "2026-05-28 09:00",
        "scoring_end": "2026-05-31 23:59",
        "recommended_role": "scorer",
        "action": "emergency scorer preflight if registered and scoring files are available",
    },
    {
        "capri_target_id": "T330",
        "casp_target_id": "T2313",
        "status": "Scoring challenge",
        "prediction_start": "2026-05-14 17:30",
        "prediction_server_end": "2026-05-17 17:00",
        "prediction_human_end": "2026-05-28 17:00",
        "scoring_start": "2026-05-29 09:00",
        "scoring_end": "2026-06-01 23:59",
        "recommended_role": "scorer",
        "action": "scorer preflight now; scoring closes on registration-deadline day",
    },
    {
        "capri_target_id": "T331",
        "casp_target_id": "H2338",
        "status": "Scoring challenge",
        "prediction_start": "2026-05-14 17:30",
        "prediction_server_end": "2026-05-17 17:00",
        "prediction_human_end": "2026-05-29 17:00",
        "scoring_start": "2026-05-30 09:00",
        "scoring_end": "2026-06-01 23:59",
        "recommended_role": "scorer",
        "action": "scorer preflight now; scoring closes on registration-deadline day",
    },
    {
        "capri_target_id": "T332",
        "casp_target_id": "H2339",
        "status": "Prediction (human only)",
        "prediction_start": "2026-05-15 17:30",
        "prediction_server_end": "2026-05-18 17:00",
        "prediction_human_end": "2026-05-30 17:00",
        "scoring_start": "2026-06-01 09:00",
        "scoring_end": "2026-06-05 23:59",
        "recommended_role": "scorer",
        "action": "prediction closed; scoring starts on registration-deadline day",
    },
    {
        "capri_target_id": "T333",
        "casp_target_id": "H2319",
        "status": "Prediction (human only)",
        "prediction_start": "2026-05-19 17:30",
        "prediction_server_end": "2026-05-22 17:00",
        "prediction_human_end": "2026-06-02 17:00",
        "scoring_start": "2026-06-03 09:00",
        "scoring_end": "2026-06-06 23:59",
        "recommended_role": "predictor_then_scorer",
        "action": "predictor if CASP ID is ready, then prepare scorer lane",
    },
    {
        "capri_target_id": "T334",
        "casp_target_id": "H2321",
        "status": "Prediction (human only)",
        "prediction_start": "2026-05-20 17:30",
        "prediction_server_end": "2026-05-23 17:00",
        "prediction_human_end": "2026-06-03 17:00",
        "scoring_start": "2026-06-04 09:00",
        "scoring_end": "2026-06-08 23:59",
        "recommended_role": "predictor_then_scorer",
        "action": "predictor if CASP ID is ready, then prepare scorer lane",
    },
    {
        "capri_target_id": "T335",
        "casp_target_id": "H2335",
        "status": "Prediction challenge",
        "prediction_start": "2026-05-27 17:30",
        "prediction_server_end": "2026-05-30 17:00",
        "prediction_human_end": "2026-06-10 17:00",
        "scoring_start": "2026-06-11 09:00",
        "scoring_end": "2026-06-15 23:59",
        "recommended_role": "predictor_then_scorer",
        "action": "human predictor priority, then scorer",
    },
    {
        "capri_target_id": "T336",
        "casp_target_id": "H2340",
        "status": "Upcoming",
        "prediction_start": "2026-06-01 17:30",
        "prediction_server_end": "2026-06-04 17:00",
        "prediction_human_end": "2026-06-15 17:00",
        "scoring_start": "2026-06-16 09:00",
        "scoring_end": "2026-06-20 23:59",
        "recommended_role": "predictor_then_scorer",
        "action": "predictor/server priority when target opens",
    },
    {
        "capri_target_id": "T337",
        "casp_target_id": "H2343",
        "status": "Upcoming",
        "prediction_start": "2026-06-01 17:30",
        "prediction_server_end": "2026-06-04 17:00",
        "prediction_human_end": "2026-06-15 17:00",
        "scoring_start": "2026-06-16 09:00",
        "scoring_end": "2026-06-20 23:59",
        "recommended_role": "predictor_then_scorer",
        "action": "predictor/server priority when target opens",
    },
    {
        "capri_target_id": "T338",
        "casp_target_id": "T2342",
        "status": "Upcoming",
        "prediction_start": "2026-06-02 17:30",
        "prediction_server_end": "2026-06-05 17:00",
        "prediction_human_end": "2026-06-16 17:00",
        "scoring_start": "2026-06-17 09:00",
        "scoring_end": "2026-06-21 23:59",
        "recommended_role": "predictor_then_scorer",
        "action": "predictor/server watch",
    },
    {
        "capri_target_id": "T339",
        "casp_target_id": "H2344",
        "status": "Upcoming",
        "prediction_start": "2026-06-03 17:30",
        "prediction_server_end": "2026-06-06 17:00",
        "prediction_human_end": "2026-06-17 17:00",
        "scoring_start": "2026-06-18 09:00",
        "scoring_end": "2026-06-22 23:59",
        "recommended_role": "predictor_then_scorer",
        "action": "predictor/server watch",
    },
]

TARGET_COLUMNS = [
    "capri_target_id",
    "casp_target_id",
    "status",
    "prediction_start",
    "prediction_server_end",
    "prediction_human_end",
    "scoring_start",
    "scoring_end",
    "recommended_role",
    "readiness_status",
    "target_folder",
    "action",
    "blockers",
]

REGISTRATION_COLUMNS = ["field", "value", "evidence_ref", "operator_clearance", "notes"]

CLAIM_BOUNDARY = (
    "Local CAPRI Round 65 readiness packet only. It records official schedule and format gates, creates "
    "operator registration/role/preflight worklists, and does not register, download restricted target files, "
    "submit models, claim CAPRI/CASP scoring performance, or override online CAPRI validation."
)


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _artifact(path_like: str | Path) -> str:
    path = _resolve(path_like).resolve()
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _read_csv(path_like: str | Path) -> list[dict[str, str]]:
    path = _resolve(path_like)
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_csv(path_like: str | Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _date(value: str) -> dt.date:
    return dt.date.fromisoformat(value[:10])


def _registration_template(existing_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    existing = {_text(row.get("field")): row for row in existing_rows}
    rows: list[dict[str, str]] = []
    for field, notes in REGISTRATION_FIELDS:
        old = existing.get(field, {})
        rows.append(
            {
                "field": field,
                "value": _text(old.get("value")),
                "evidence_ref": _text(old.get("evidence_ref")),
                "operator_clearance": _text(old.get("operator_clearance")),
                "notes": notes,
            }
        )
    return rows


def _ready_registration_fields(rows: list[dict[str, str]]) -> int:
    count = 0
    for row in rows:
        value = _text(row.get("value"))
        evidence = _text(row.get("evidence_ref"))
        clearance = _text(row.get("operator_clearance")).lower()
        if value and evidence and clearance in {"true", "yes", "cleared", "operator_cleared"}:
            count += 1
    return count


def _target_folder_name(target: dict[str, str]) -> str:
    return f"{target['capri_target_id']}_{target['casp_target_id']}"


def _target_readiness(target: dict[str, str], registration_ready: bool) -> tuple[str, str]:
    blockers = ["operator_registration_required", "role_selection_required", "capri_template_required"]
    if target["recommended_role"] == "closed":
        return "closed_context", "closed_target"
    if registration_ready:
        blockers = ["capri_template_required", "online_validation_required"]
        return "format_preflight_required", ",".join(blockers)
    return "blocked_registration_role_selection", ",".join(blockers)


def _target_rows(target_dir: str | Path, registration_ready: bool) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for target in TARGETS:
        folder = _resolve(target_dir) / _target_folder_name(target)
        readiness, blockers = _target_readiness(target, registration_ready)
        row = dict(target)
        row.update(
            {
                "readiness_status": readiness,
                "target_folder": _artifact(folder),
                "blockers": blockers,
            }
        )
        rows.append(row)
    return rows


def _write_target_folders(rows: list[dict[str, Any]]) -> None:
    for row in rows:
        folder = _resolve(row["target_folder"])
        folder.mkdir(parents=True, exist_ok=True)
        action_lines = [
            f"# CAPRI Round 65 {row['capri_target_id']} / {row['casp_target_id']}",
            "",
            f"- status: `{row['status']}`",
            f"- recommended role: `{row['recommended_role']}`",
            f"- readiness: `{row['readiness_status']}`",
            f"- prediction: `{row['prediction_start']}` to `{row['prediction_human_end']}`",
            f"- scoring: `{row['scoring_start']}` to `{row['scoring_end']}`",
            f"- action: {row['action']}",
            f"- blockers: `{row['blockers']}`",
            "",
            "## Preflight",
            "",
            "- confirm registration and role",
            "- fetch the target-specific CAPRI template",
            "- validate HEADER, MODEL numbering, TER/ENDMDL/END records, chain IDs, and residue numbering",
            "- run CAPRI online validation before submission",
            "",
        ]
        (folder / "ACTION.md").write_text("\n".join(action_lines), encoding="utf-8")
        _write_csv(
            folder / "role_preflight.csv",
            [
                {
                    "gate": "registration",
                    "status": "blocked" if "registration" in row["blockers"] else "ready",
                    "required_evidence": "CASP ID and CAPRI registration confirmation",
                },
                {
                    "gate": "format_template",
                    "status": "blocked",
                    "required_evidence": "target-specific CAPRI template",
                },
                {
                    "gate": "online_validation",
                    "status": "blocked",
                    "required_evidence": "CAPRI online validator acceptance",
                },
            ],
            ["gate", "status", "required_evidence"],
        )


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    as_of_date = _date(args.as_of_date)
    registration_rows = _registration_template(_read_csv(args.registration_csv))
    ready_registration_field_count = _ready_registration_fields(registration_rows)
    registration_ready = ready_registration_field_count == len(REGISTRATION_FIELDS)
    rows = _target_rows(args.target_dir, registration_ready)
    active_rows = [row for row in rows if row["recommended_role"] != "closed"]
    blocked_rows = [row for row in rows if row["readiness_status"].startswith("blocked")]
    preflight_rows = [row for row in rows if row["readiness_status"] == "format_preflight_required"]
    scorer_rows = [row for row in rows if row["recommended_role"] == "scorer"]
    predictor_rows = [row for row in rows if "predictor" in row["recommended_role"]]
    registration_deadline = dt.date(2026, 6, 1)
    days_to_registration_deadline = (registration_deadline - as_of_date).days
    if not registration_ready:
        status = "blocked_registration_role_selection"
        first_action = "confirm CASP ID, CAPRI registration, selected role, and submitter contact"
    elif preflight_rows:
        status = "format_preflight_required"
        first_action = "fetch CAPRI target templates and run format/online validation"
    else:
        status = "ready_for_submission_review"
        first_action = "operator review before any CAPRI upload"
    summary = {
        "packet_type": "capri_round65_readiness",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "as_of_date": args.as_of_date,
        "round_status": "Active",
        "registration_start": "2026-04-10 11:14",
        "registration_end": "2026-06-01 midnight",
        "registration_deadline_source": SOURCE_MAIN,
        "registration_days_remaining": days_to_registration_deadline,
        "registration_urgency": "immediate" if days_to_registration_deadline <= 1 else "open",
        "capri_readiness_status": status,
        "registration_gate_status": "ready" if registration_ready else "operator_input_required",
        "registration_required_field_count": len(REGISTRATION_FIELDS),
        "registration_ready_field_count": ready_registration_field_count,
        "role_selection_status": "ready" if registration_ready else "operator_input_required",
        "format_preflight_status": "required",
        "target_count": len(rows),
        "active_target_count": len(active_rows),
        "closed_target_count": len(rows) - len(active_rows),
        "scorer_priority_target_count": len(scorer_rows),
        "predictor_priority_target_count": len(predictor_rows),
        "blocked_target_count": len(blocked_rows),
        "format_preflight_target_count": len(preflight_rows),
        "target_folder_count": len(rows),
        "first_open_target_id": next((row["capri_target_id"] for row in active_rows), ""),
        "first_next_action": first_action,
        "source_round": SOURCE_ROUND,
        "source_main": SOURCE_MAIN,
        "source_format": SOURCE_FORMAT,
        "source_casp_capri": SOURCE_CASP_CAPRI,
        "claim_boundary": CLAIM_BOUNDARY,
    }
    return {"summary": summary, "rows": rows, "registration_rows": registration_rows}


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CAPRI Round 65 Readiness Packet",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- official source checked: `{summary['as_of_date']}`",
        f"- source round: {summary['source_round']}",
        f"- source active-round registration: {summary['source_main']}",
        f"- status: `{summary['capri_readiness_status']}`",
        f"- registration: `{summary['registration_gate_status']}` ready fields `{summary['registration_ready_field_count']}/{summary['registration_required_field_count']}`",
        f"- registration window: `{summary['registration_start']}` to `{summary['registration_end']}`",
        f"- registration days remaining: `{summary['registration_days_remaining']}` urgency `{summary['registration_urgency']}`",
        f"- targets active/closed/total: `{summary['active_target_count']}/{summary['closed_target_count']}/{summary['target_count']}`",
        f"- scorer/predictor priority targets: `{summary['scorer_priority_target_count']}/{summary['predictor_priority_target_count']}`",
        f"- next action: {summary['first_next_action']}",
        "",
        "## Position",
        "",
        "CAPRI Round 65 is worth entering if CASP ID and CAPRI registration can be confirmed immediately. "
        "It is the 7th joint CASP-CAPRI Assembly Prediction challenge in the CASP17 season, and it maps "
        "directly to the CASP17 immune, nucleic-acid-complex, difficult-complex, and scoring/model-selection lanes.",
        "",
        "## Registration Gate",
        "",
        "| field | value | evidence | clearance | notes |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in payload["registration_rows"]:
        lines.append(
            f"| `{row['field']}` | `{row['value'] or '-'}` | `{row['evidence_ref'] or '-'}` | "
            f"`{row['operator_clearance'] or '-'}` | {row['notes']} |"
        )
    lines.extend(
        [
            "",
            "## Target Worklist",
            "",
            "| CAPRI | CASP | status | role | readiness | prediction human end | scoring end | folder | action |",
            "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for row in payload["rows"]:
        lines.append(
            f"| `{row['capri_target_id']}` | `{row['casp_target_id']}` | `{row['status']}` | "
            f"`{row['recommended_role']}` | `{row['readiness_status']}` | `{row['prediction_human_end']}` | "
            f"`{row['scoring_end']}` | `{row['target_folder']}` | {row['action']} |"
        )
    lines.extend(
        [
            "",
            "## Format Preflight",
            "",
            "- Use the target-specific CAPRI template.",
            "- Submit only PDB format files.",
            "- Put the CAPRI target number in the first line as a HEADER record.",
            "- Keep MODEL records numbered and ordered correctly.",
            "- End chains with TER, models with ENDMDL, and each submission with END.",
            "- Preserve chain IDs and residue numbering from the template.",
            "- Add PARENT records where templates are used; preserve MassiveFold REMARK provenance if applicable.",
            "- Run the CAPRI online validator before treating any upload as ready.",
            "",
            "## Claim Boundary",
            "",
            str(summary["claim_boundary"]),
            "",
        ]
    )
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def write_outputs(args: argparse.Namespace, payload: dict[str, Any]) -> None:
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"], TARGET_COLUMNS)
    _write_csv(args.registration_csv, payload["registration_rows"], REGISTRATION_COLUMNS)
    _write_target_folders(payload["rows"])
    _write_md(args.out_md, payload)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build CASP17 CAPRI Round 65 readiness packet.")
    parser.add_argument("--as-of-date", default=dt.date.today().isoformat())
    parser.add_argument("--target-dir", default=DEFAULT_TARGET_DIR)
    parser.add_argument("--registration-csv", default=DEFAULT_REGISTRATION_CSV)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_payload(args)
    write_outputs(args, payload)


if __name__ == "__main__":
    main()

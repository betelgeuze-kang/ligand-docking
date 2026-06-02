#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]

DEFAULT_DECISION_KIT_JSON = "casp17/casp17_current_upload_operator_decision_kit_current.json"
DEFAULT_OUT_JSON = "casp17/casp17_current_upload_operator_decision_kit_completion_audit_current.json"
DEFAULT_OUT_CSV = "casp17/casp17_current_upload_operator_decision_kit_completion_audit_current.csv"
DEFAULT_OUT_MD = "casp17/CASP17_CURRENT_UPLOAD_OPERATOR_DECISION_KIT_COMPLETION_AUDIT.md"

ROW_COLUMNS = [
    "queue_rank",
    "target_id",
    "audit_status",
    "urgency",
    "review_status",
    "decision_status",
    "decision_packet_folder",
    "decision_folder_present",
    "decision_md_present",
    "operator_decision_row_csv_present",
    "operator_decision_row_csv_rows",
    "target_summary_csv_match",
    "operator_decision_missing",
    "invalid_operator_decision",
    "author_serialization_missing",
    "final_upload_filename_missing",
    "coordinate_copy_count",
    "proof_marker_count",
    "portal_submit_marker_count",
    "blockers",
    "next_action",
]

CLAIM_BOUNDARY = (
    "CASP17 current upload operator decision kit completion audit only. It verifies root kit files, "
    "per-target decision folders, DECISION.md files, per-target operator-decision CSV rows, target "
    "summary consistency, and no-coordinate/no-proof/no-portal-submit hygiene. It does not enter "
    "operator decisions, serialize a CASP author code, upload to CASP, compute native accuracy, or "
    "mark strict-blind competitive proof."
)


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _artifact(path_like: Any) -> str:
    if path_like is None or not str(path_like).strip():
        return ""
    path = _resolve(path_like).resolve()
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _int(value: Any) -> int:
    try:
        return int(float(_text(value)))
    except (TypeError, ValueError):
        return 0


def _read_json(path_like: str | Path) -> dict[str, Any]:
    path = _resolve(path_like)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _summary(payload: dict[str, Any]) -> dict[str, Any]:
    summary = payload.get("summary")
    return summary if isinstance(summary, dict) else {}


def _rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = payload.get("rows")
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def _read_csv_rows(path_like: str | Path) -> list[dict[str, str]]:
    path = _resolve(path_like)
    if not path.exists() or not path.is_file():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_csv(path_like: str | Path, rows: list[dict[str, Any]]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=ROW_COLUMNS, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _is_file(path_like: str | Path) -> bool:
    return bool(_text(path_like)) and _resolve(path_like).is_file()


def _is_dir(path_like: str | Path) -> bool:
    return bool(_text(path_like)) and _resolve(path_like).is_dir()


def _coordinate_file_count(path_like: str | Path) -> int:
    path = _resolve(path_like)
    if not path.exists():
        return 0
    return sum(1 for item in path.rglob("*") if item.is_file() and item.suffix.lower() in {".pdb", ".cif"})


def _truthy_marker_count(rows: list[dict[str, Any]], keys: set[str]) -> int:
    count = 0
    for row in rows:
        for key in keys:
            value = _text(row.get(key)).lower()
            if value and value not in {"false", "0", "no", "none", "not_applicable"}:
                count += 1
    return count


def _target_summary_by_target(path_like: str | Path) -> dict[str, dict[str, str]]:
    return {_text(row.get("target_id")).upper(): row for row in _read_csv_rows(path_like)}


def _audit_row(
    row: dict[str, Any],
    *,
    target_summary_by_target: dict[str, dict[str, str]],
    global_blockers: list[str],
) -> dict[str, Any]:
    target_id = _text(row.get("target_id")).upper()
    folder = _text(row.get("decision_packet_folder"))
    decision_md = _text(row.get("decision_md")) or _artifact(_resolve(folder) / "DECISION.md")
    row_csv = _artifact(_resolve(folder) / "operator_decision_row.csv") if folder else ""
    csv_rows = _read_csv_rows(row_csv) if _is_file(row_csv) else []
    blockers = list(global_blockers)
    if not _is_dir(folder):
        blockers.append("decision_folder_missing")
    if not _is_file(decision_md):
        blockers.append("decision_md_missing")
    if not _is_file(row_csv):
        blockers.append("operator_decision_row_csv_missing")
    if len(csv_rows) != 1:
        blockers.append("operator_decision_row_csv_count_mismatch")
    if csv_rows and _text(csv_rows[0].get("target_id")).upper() != target_id:
        blockers.append("operator_decision_row_csv_target_mismatch")
    summary_row = target_summary_by_target.get(target_id, {})
    target_summary_match = int(
        bool(summary_row)
        and _text(summary_row.get("decision_packet_folder")) == _artifact(folder)
        and _text(summary_row.get("decision_md")) == _artifact(decision_md)
    )
    if not target_summary_match:
        blockers.append("target_summary_csv_mismatch")
    coordinate_count = _coordinate_file_count(folder)
    if coordinate_count:
        blockers.append("decision_coordinate_copy_present")
    proof_marker_count = _truthy_marker_count(csv_rows + [row], {"competitive_proof_eligible", "proof_eligible"})
    if proof_marker_count:
        blockers.append("competitive_proof_marker_present")
    portal_submit_marker_count = _truthy_marker_count(csv_rows + [row], {"portal_submitted", "submitted_to_casp"})
    if portal_submit_marker_count:
        blockers.append("portal_submit_marker_present")
    decision = _text(row.get("operator_decision")).lower()
    invalid_decision = int(bool(decision) and decision not in {"approve", "hold", "reject"})
    author_missing = int(_text(row.get("author_serialization_status")).lower() != "author_serialized")
    final_missing = int(decision == "approve" and not _text(row.get("final_upload_filename")))
    blockers = list(dict.fromkeys(blockers))
    first_blocker = blockers[0] if blockers else ""
    return {
        "queue_rank": _int(row.get("queue_rank")),
        "target_id": target_id,
        "audit_status": "pass" if not blockers else "blocked",
        "urgency": _text(row.get("urgency")),
        "review_status": _text(row.get("review_status")),
        "decision_status": _text(row.get("decision_status")),
        "decision_packet_folder": _artifact(folder),
        "decision_folder_present": int(_is_dir(folder)),
        "decision_md_present": int(_is_file(decision_md)),
        "operator_decision_row_csv_present": int(_is_file(row_csv)),
        "operator_decision_row_csv_rows": len(csv_rows),
        "target_summary_csv_match": target_summary_match,
        "operator_decision_missing": int(not decision),
        "invalid_operator_decision": invalid_decision,
        "author_serialization_missing": author_missing,
        "final_upload_filename_missing": final_missing,
        "coordinate_copy_count": coordinate_count,
        "proof_marker_count": proof_marker_count,
        "portal_submit_marker_count": portal_submit_marker_count,
        "blockers": ",".join(blockers),
        "next_action": (
            f"repair {first_blocker} for {target_id}"
            if first_blocker
            else _text(row.get("next_action"))
            or "fill operator decision and rerun current upload operator decision kit"
        ),
    }


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    kit_path = _resolve(args.decision_kit_json)
    kit_payload = _read_json(args.decision_kit_json)
    kit_summary = _summary(kit_payload)
    kit_rows = _rows(kit_payload) if kit_path.exists() else []
    kit_dir = _text(kit_summary.get("decision_kit_dir"))
    intake_csv = _text(kit_summary.get("operator_decision_intake_csv")) or str(
        _resolve(kit_dir) / "operator_decision_intake.csv"
    )
    target_summary_csv = _text(kit_summary.get("target_summary_csv")) or str(_resolve(kit_dir) / "target_summary.csv")
    rerun_commands_md = _text(kit_summary.get("rerun_commands_md")) or str(_resolve(kit_dir) / "RERUN_COMMANDS.md")
    batch_manifest_json = _text(kit_summary.get("batch_manifest_json")) or str(
        _resolve(kit_dir) / "batch_manifest.json"
    )
    global_blockers: list[str] = []
    if not kit_path.exists():
        global_blockers.append("decision_kit_json_missing")
    if not _is_dir(kit_dir):
        global_blockers.append("decision_kit_dir_missing")
    root_files = [
        ("operator_decision_intake_csv_missing", intake_csv),
        ("target_summary_csv_missing", target_summary_csv),
        ("rerun_commands_md_missing", rerun_commands_md),
        ("batch_manifest_json_missing", batch_manifest_json),
    ]
    for blocker, path_like in root_files:
        if not _is_file(path_like):
            global_blockers.append(blocker)
    intake_rows = _read_csv_rows(intake_csv) if _is_file(intake_csv) else []
    target_summary_rows = _read_csv_rows(target_summary_csv) if _is_file(target_summary_csv) else []
    manifest_payload = _read_json(batch_manifest_json) if _is_file(batch_manifest_json) else {}
    manifest_summary = _summary(manifest_payload)
    expected = _int(kit_summary.get("review_target_count"))
    if len(kit_rows) != expected:
        global_blockers.append("kit_json_row_count_mismatch")
    if len(intake_rows) != expected:
        global_blockers.append("operator_decision_intake_csv_row_count_mismatch")
    if len(target_summary_rows) != expected:
        global_blockers.append("target_summary_csv_row_count_mismatch")
    if not manifest_payload:
        global_blockers.append("batch_manifest_unreadable")
    if manifest_summary and _int(manifest_summary.get("review_target_count")) != expected:
        global_blockers.append("batch_manifest_review_target_count_mismatch")
    target_summary_map = _target_summary_by_target(target_summary_csv)
    rows = [
        _audit_row(row, target_summary_by_target=target_summary_map, global_blockers=global_blockers)
        for row in kit_rows
    ]
    blocked = [row for row in rows if row["audit_status"] != "pass"]
    first = blocked[0] if blocked else (rows[0] if rows else {})
    root_present = sum(1 for _, path_like in root_files if _is_file(path_like))
    root_required = len(root_files)
    status = (
        "blocked_current_upload_operator_decision_kit_missing"
        if not kit_path.exists()
        else (
            "casp17_current_upload_operator_decision_kit_completion_audit_pass"
            if rows and not blocked
            else "blocked_current_upload_operator_decision_kit_completion_audit"
        )
    )
    summary = {
        "packet_type": "casp17_current_upload_operator_decision_kit_completion_audit",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "current_upload_operator_decision_kit_completion_audit_status": status,
        "decision_kit_status": _text(kit_summary.get("current_upload_operator_decision_kit_status")),
        "review_packet_status": _text(kit_summary.get("review_packet_status")),
        "review_target_count": expected,
        "target_pass_count": len(rows) - len(blocked),
        "target_blocked_count": len(blocked),
        "root_file_present_count": root_present,
        "root_file_required_count": root_required,
        "intake_csv_row_count": len(intake_rows),
        "target_summary_csv_row_count": len(target_summary_rows),
        "per_target_csv_row_count": sum(_int(row.get("operator_decision_row_csv_rows")) for row in rows),
        "decision_folder_present_count": sum(_int(row.get("decision_folder_present")) for row in rows),
        "decision_md_present_count": sum(_int(row.get("decision_md_present")) for row in rows),
        "operator_decision_row_csv_present_count": sum(
            _int(row.get("operator_decision_row_csv_present")) for row in rows
        ),
        "target_summary_csv_match_count": sum(_int(row.get("target_summary_csv_match")) for row in rows),
        "operator_decision_missing_count": sum(_int(row.get("operator_decision_missing")) for row in rows),
        "invalid_operator_decision_count": sum(_int(row.get("invalid_operator_decision")) for row in rows),
        "author_serialization_missing_count": sum(_int(row.get("author_serialization_missing")) for row in rows),
        "final_upload_filename_missing_count": sum(_int(row.get("final_upload_filename_missing")) for row in rows),
        "coordinate_copy_count": sum(_int(row.get("coordinate_copy_count")) for row in rows),
        "proof_marker_count": sum(_int(row.get("proof_marker_count")) for row in rows),
        "portal_submit_marker_count": sum(_int(row.get("portal_submit_marker_count")) for row in rows),
        "first_blocked_target_id": _text(first.get("target_id")) if blocked else "",
        "first_blocker": _text(first.get("blockers")).split(",")[0] if blocked and _text(first.get("blockers")) else "",
        "next_action": (
            "fill approve/hold/reject operator decisions, serialize runtime CASP author code for approved rows, "
            "then rerun current upload operator decision kit"
        ),
        "claim_boundary": CLAIM_BOUNDARY,
    }
    return {"summary": summary, "rows": rows}


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Current Upload Operator Decision Kit Completion Audit",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- status: `{summary['current_upload_operator_decision_kit_completion_audit_status']}`",
        f"- decision/review packet: `{summary['decision_kit_status'] or '-'}` `{summary['review_packet_status'] or '-'}`",
        f"- targets pass/blocked/total: `{summary['target_pass_count']}/{summary['target_blocked_count']}/{summary['review_target_count']}`",
        f"- root files: `{summary['root_file_present_count']}/{summary['root_file_required_count']}`",
        f"- rows intake/summary/per-target: `{summary['intake_csv_row_count']}/{summary['target_summary_csv_row_count']}/{summary['per_target_csv_row_count']}`",
        f"- folders/md/csv/summary-match: `{summary['decision_folder_present_count']}/{summary['decision_md_present_count']}/{summary['operator_decision_row_csv_present_count']}/{summary['target_summary_csv_match_count']}`",
        f"- missing decision/invalid/author/final-name: `{summary['operator_decision_missing_count']}/{summary['invalid_operator_decision_count']}/{summary['author_serialization_missing_count']}/{summary['final_upload_filename_missing_count']}`",
        f"- hygiene coordinate/proof/portal-submit: `{summary['coordinate_copy_count']}/{summary['proof_marker_count']}/{summary['portal_submit_marker_count']}`",
        f"- first blocked: `{summary['first_blocked_target_id'] or '-'}` `{summary['first_blocker'] or '-'}`",
        "",
        "## Claim Boundary",
        "",
        CLAIM_BOUNDARY,
        "",
    ]
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def write_outputs(args: argparse.Namespace, payload: dict[str, Any]) -> None:
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"])
    _write_md(args.out_md, payload)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit CASP17 current upload operator decision kit completion.")
    parser.add_argument("--decision-kit-json", default=DEFAULT_DECISION_KIT_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    write_outputs(args, build_payload(args))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

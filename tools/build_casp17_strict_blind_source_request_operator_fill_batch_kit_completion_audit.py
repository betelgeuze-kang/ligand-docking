#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]

DEFAULT_BATCH_KIT_JSON = "casp17/casp17_strict_blind_source_request_operator_fill_batch_kit_current.json"
DEFAULT_OUT_JSON = "casp17/casp17_strict_blind_source_request_operator_fill_batch_kit_completion_audit_current.json"
DEFAULT_OUT_CSV = "casp17/casp17_strict_blind_source_request_operator_fill_batch_kit_completion_audit_current.csv"
DEFAULT_OUT_MD = "casp17/CASP17_STRICT_BLIND_SOURCE_REQUEST_OPERATOR_FILL_BATCH_KIT_COMPLETION_AUDIT.md"

ROW_COLUMNS = [
    "request_index",
    "request_id",
    "candidate_target_id",
    "candidate_scope",
    "request_kind",
    "audit_status",
    "request_batch_folder",
    "request_folder_present",
    "request_readme_present",
    "request_operator_fill_csv_present",
    "expected_field_count",
    "request_operator_fill_csv_rows",
    "request_row_mismatch",
    "request_summary_csv_match",
    "operator_value_missing_count",
    "operator_evidence_missing_count",
    "candidate_replacement_field_count",
    "coordinate_copy_count",
    "proof_marker_count",
    "author_marker_count",
    "blockers",
    "next_action",
]

CLAIM_BOUNDARY = (
    "CASP17 strict-blind source-request operator-fill batch kit completion audit only. It verifies "
    "the batch intake files, request folders, per-request CSV row counts, request-summary consistency, "
    "no-coordinate-copy hygiene, and proof/author boundary markers. It reports missing operator values "
    "and evidence refs but does not fill them, approve no-leak provenance, copy coordinates, compute "
    "CASP metrics, serialize a CASP author code, push remotes, or submit to CASP."
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


def _rows(payload: dict[str, Any], key: str = "rows") -> list[dict[str, Any]]:
    rows = payload.get(key)
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


def _boundary_marker_count(rows: list[dict[str, Any]], key: str) -> int:
    count = 0
    for row in rows:
        value = _text(row.get(key)).lower()
        if value and value not in {"false", "0", "no", "none", "not_applicable"}:
            count += 1
    return count


def _rows_by_request(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        request_id = _text(row.get("request_id"))
        if request_id:
            grouped.setdefault(request_id, []).append(row)
    return grouped


def _request_summary_by_id(path_like: str | Path) -> dict[str, dict[str, str]]:
    return {_text(row.get("request_id")): row for row in _read_csv_rows(path_like) if _text(row.get("request_id"))}


def _audit_request(
    request: dict[str, Any],
    *,
    kit_rows_by_request: dict[str, list[dict[str, Any]]],
    request_summary_csv_by_id: dict[str, dict[str, str]],
    global_blockers: list[str],
) -> dict[str, Any]:
    request_id = _text(request.get("request_id"))
    folder = _text(request.get("request_batch_folder"))
    csv_path = _text(request.get("request_operator_fill_csv")) or str(_resolve(folder) / "operator_fill_rows.csv")
    readme_path = _text(request.get("request_readme")) or str(_resolve(folder) / "README.md")
    expected = _int(request.get("field_count"))
    request_rows = kit_rows_by_request.get(request_id, [])
    csv_rows = _read_csv_rows(csv_path) if _is_file(csv_path) else []
    blockers = list(global_blockers)
    if not _is_dir(folder):
        blockers.append("request_batch_folder_missing")
    if not _is_file(readme_path):
        blockers.append("request_readme_missing")
    if not _is_file(csv_path):
        blockers.append("request_operator_fill_csv_missing")
    if len(request_rows) != expected:
        blockers.append("kit_request_row_count_mismatch")
    if len(csv_rows) != expected:
        blockers.append("request_operator_fill_csv_row_mismatch")
    if any(_text(row.get("request_id")) != request_id for row in csv_rows):
        blockers.append("request_operator_fill_csv_request_id_mismatch")
    summary_row = request_summary_csv_by_id.get(request_id, {})
    summary_match = int(
        bool(summary_row)
        and _int(summary_row.get("field_count")) == expected
        and _text(summary_row.get("request_batch_folder")) == _artifact(folder)
        and _text(summary_row.get("request_operator_fill_csv")) == _artifact(csv_path)
    )
    if not summary_match:
        blockers.append("request_summary_csv_mismatch")
    coordinate_count = _coordinate_file_count(folder)
    if coordinate_count:
        blockers.append("request_coordinate_copy_present")
    proof_marker_count = _boundary_marker_count(request_rows + csv_rows, "competitive_proof_eligible")
    author_marker_count = _boundary_marker_count(request_rows + csv_rows, "author_serialized")
    if proof_marker_count:
        blockers.append("competitive_proof_marker_present")
    if author_marker_count:
        blockers.append("author_marker_present")
    blockers = list(dict.fromkeys(blockers))
    first_blocker = blockers[0] if blockers else ""
    operator_value_missing = sum(1 for row in request_rows if _text(row.get("value_status")) != "value_present")
    operator_evidence_missing = sum(
        1 for row in request_rows if _text(row.get("evidence_status")) == "evidence_required_missing"
    )
    candidate_replacement = sum(
        1 for row in request_rows if _text(row.get("fill_status")) == "blocked_candidate_replacement_required"
    )
    return {
        "request_index": _int(request.get("request_index")),
        "request_id": request_id,
        "candidate_target_id": _text(request.get("candidate_target_id")),
        "candidate_scope": _text(request.get("candidate_scope")),
        "request_kind": _text(request.get("request_kind")),
        "audit_status": "pass" if not blockers else "blocked",
        "request_batch_folder": _artifact(folder),
        "request_folder_present": int(_is_dir(folder)),
        "request_readme_present": int(_is_file(readme_path)),
        "request_operator_fill_csv_present": int(_is_file(csv_path)),
        "expected_field_count": expected,
        "request_operator_fill_csv_rows": len(csv_rows),
        "request_row_mismatch": 0 if len(request_rows) == expected and len(csv_rows) == expected else 1,
        "request_summary_csv_match": summary_match,
        "operator_value_missing_count": operator_value_missing,
        "operator_evidence_missing_count": operator_evidence_missing,
        "candidate_replacement_field_count": candidate_replacement,
        "coordinate_copy_count": coordinate_count,
        "proof_marker_count": proof_marker_count,
        "author_marker_count": author_marker_count,
        "blockers": ",".join(blockers),
        "next_action": (
            f"repair {first_blocker} for {request_id}"
            if first_blocker
            else "fill operator values/evidence refs and rerun source-request fulfillment"
        ),
    }


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    kit_path = _resolve(args.batch_kit_json)
    kit_payload = _read_json(args.batch_kit_json)
    kit_summary = _summary(kit_payload)
    kit_rows = _rows(kit_payload)
    request_rows = _rows(kit_payload, "request_rows")
    batch_folder = _text(kit_summary.get("batch_folder"))
    batch_csv = _text(kit_summary.get("operator_fill_intake_batch_csv")) or str(
        _resolve(batch_folder) / "operator_fill_intake_batch.csv"
    )
    request_summary_csv = _text(kit_summary.get("request_summary_csv")) or str(
        _resolve(batch_folder) / "request_summary.csv"
    )
    rerun_commands_md = _text(kit_summary.get("rerun_commands_md")) or str(_resolve(batch_folder) / "RERUN_COMMANDS.md")
    batch_manifest_json = _text(kit_summary.get("batch_manifest_json")) or str(
        _resolve(batch_folder) / "batch_manifest.json"
    )
    global_blockers: list[str] = []
    if not kit_path.exists():
        global_blockers.append("batch_kit_json_missing")
    if not _is_dir(batch_folder):
        global_blockers.append("batch_folder_missing")
    root_files = [
        ("operator_fill_intake_batch_csv_missing", batch_csv),
        ("request_summary_csv_missing", request_summary_csv),
        ("rerun_commands_md_missing", rerun_commands_md),
        ("batch_manifest_json_missing", batch_manifest_json),
    ]
    for blocker, path_like in root_files:
        if not _is_file(path_like):
            global_blockers.append(blocker)
    batch_csv_rows = _read_csv_rows(batch_csv) if _is_file(batch_csv) else []
    request_summary_csv_rows = _read_csv_rows(request_summary_csv) if _is_file(request_summary_csv) else []
    manifest_payload = _read_json(batch_manifest_json) if _is_file(batch_manifest_json) else {}
    manifest_summary = _summary(manifest_payload)
    field_count = _int(kit_summary.get("field_count"))
    request_count = _int(kit_summary.get("request_count"))
    if len(batch_csv_rows) != field_count:
        global_blockers.append("batch_csv_row_count_mismatch")
    if len(kit_rows) != field_count:
        global_blockers.append("kit_json_field_row_count_mismatch")
    if len(request_summary_csv_rows) != request_count:
        global_blockers.append("request_summary_csv_row_count_mismatch")
    if len(request_rows) != request_count:
        global_blockers.append("kit_json_request_row_count_mismatch")
    if not manifest_payload:
        global_blockers.append("batch_manifest_unreadable")
    if manifest_summary and _int(manifest_summary.get("field_count")) != field_count:
        global_blockers.append("batch_manifest_field_count_mismatch")
    if manifest_summary and _int(manifest_summary.get("request_count")) != request_count:
        global_blockers.append("batch_manifest_request_count_mismatch")
    root_coordinate_count = _coordinate_file_count(batch_folder)
    if root_coordinate_count:
        global_blockers.append("batch_folder_coordinate_copy_present")
    kit_rows_by_request = _rows_by_request(kit_rows)
    request_summary_map = _request_summary_by_id(request_summary_csv)
    rows = [
        _audit_request(
            request,
            kit_rows_by_request=kit_rows_by_request,
            request_summary_csv_by_id=request_summary_map,
            global_blockers=global_blockers,
        )
        for request in request_rows
    ]
    blocked_rows = [row for row in rows if row["audit_status"] != "pass"]
    status = (
        "blocked_strict_blind_source_request_operator_fill_batch_kit_missing"
        if not kit_path.exists()
        else (
            "casp17_strict_blind_source_request_operator_fill_batch_kit_completion_audit_pass"
            if rows and not blocked_rows
            else "blocked_strict_blind_source_request_operator_fill_batch_kit_completion_audit"
        )
    )
    first = blocked_rows[0] if blocked_rows else {}
    root_present = sum(1 for _, path_like in root_files if _is_file(path_like))
    per_request_csv_rows = sum(_int(row.get("request_operator_fill_csv_rows")) for row in rows)
    summary = {
        "packet_type": "casp17_strict_blind_source_request_operator_fill_batch_kit_completion_audit",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "strict_blind_source_request_operator_fill_batch_kit_completion_audit_status": status,
        "batch_kit_json": _artifact(args.batch_kit_json),
        "batch_kit_status": _text(kit_summary.get("strict_blind_source_request_operator_fill_batch_kit_status")),
        "worklist_status": _text(kit_summary.get("worklist_status")),
        "batch_folder": _artifact(batch_folder),
        "request_count": request_count,
        "request_pass_count": len(rows) - len(blocked_rows),
        "request_blocked_count": len(blocked_rows),
        "root_file_present_count": root_present,
        "root_file_required_count": len(root_files),
        "field_count": field_count,
        "batch_csv_row_count": len(batch_csv_rows),
        "request_summary_csv_row_count": len(request_summary_csv_rows),
        "per_request_csv_row_count": per_request_csv_rows,
        "request_folder_present_count": sum(_int(row.get("request_folder_present")) for row in rows),
        "request_readme_present_count": sum(_int(row.get("request_readme_present")) for row in rows),
        "request_operator_fill_csv_present_count": sum(
            _int(row.get("request_operator_fill_csv_present")) for row in rows
        ),
        "request_summary_csv_match_count": sum(_int(row.get("request_summary_csv_match")) for row in rows),
        "request_row_mismatch_count": sum(_int(row.get("request_row_mismatch")) for row in rows),
        "operator_value_missing_count": sum(_int(row.get("operator_value_missing_count")) for row in rows),
        "operator_evidence_missing_count": sum(_int(row.get("operator_evidence_missing_count")) for row in rows),
        "candidate_replacement_field_count": sum(
            _int(row.get("candidate_replacement_field_count")) for row in rows
        ),
        "coordinate_copy_count": root_coordinate_count + sum(_int(row.get("coordinate_copy_count")) for row in rows),
        "proof_marker_count": sum(_int(row.get("proof_marker_count")) for row in rows),
        "author_marker_count": sum(_int(row.get("author_marker_count")) for row in rows),
        "first_blocked_request_id": _text(first.get("request_id")) if blocked_rows else "",
        "first_blocked_target_id": _text(first.get("candidate_target_id")) if blocked_rows else "",
        "first_blocker": _text(first.get("blockers")).split(",")[0] if blocked_rows and _text(first.get("blockers")) else "",
        "next_action": "fill operator values/evidence refs and rerun source-request fulfillment, sync, and closure",
        "claim_boundary": CLAIM_BOUNDARY,
    }
    return {"summary": summary, "rows": rows}


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Strict-Blind Source Request Operator Fill Batch Kit Completion Audit",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- status: `{summary['strict_blind_source_request_operator_fill_batch_kit_completion_audit_status']}`",
        f"- batch/worklist: `{summary['batch_kit_status'] or '-'}` `{summary['worklist_status'] or '-'}`",
        f"- requests pass/blocked/total: `{summary['request_pass_count']}/{summary['request_blocked_count']}/{summary['request_count']}`",
        f"- root files: `{summary['root_file_present_count']}/{summary['root_file_required_count']}`",
        f"- fields expected/batch/per-request: `{summary['field_count']}/{summary['batch_csv_row_count']}/{summary['per_request_csv_row_count']}`",
        f"- request summary rows/matches: `{summary['request_summary_csv_row_count']}/{summary['request_summary_csv_match_count']}`",
        f"- request folder/readme/csv: `{summary['request_folder_present_count']}/{summary['request_readme_present_count']}/{summary['request_operator_fill_csv_present_count']}`",
        f"- row mismatch: `{summary['request_row_mismatch_count']}`",
        f"- missing value/evidence/candidate-replacement: `{summary['operator_value_missing_count']}/{summary['operator_evidence_missing_count']}/{summary['candidate_replacement_field_count']}`",
        f"- hygiene coordinate/proof/author: `{summary['coordinate_copy_count']}/{summary['proof_marker_count']}/{summary['author_marker_count']}`",
        f"- first blocked: `{summary['first_blocked_request_id'] or '-'}` `{summary['first_blocker'] or '-'}`",
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
    parser = argparse.ArgumentParser(
        description="Audit CASP17 strict-blind source request operator fill batch kit completion."
    )
    parser.add_argument("--batch-kit-json", default=DEFAULT_BATCH_KIT_JSON)
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

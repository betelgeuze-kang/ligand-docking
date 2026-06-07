#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
from pathlib import Path
from typing import Any

from tools.casp17 import build_casp17_competitive_floor_batch_native_provenance_operator_fill_preflight as preflight


ROOT = Path(__file__).resolve().parents[2]

DEFAULT_PREFLIGHT_JSON = (
    "casp17/casp17_competitive_floor_batch_native_provenance_operator_fill_preflight_current.json"
)
DEFAULT_OUT_JSON = (
    "casp17/casp17_competitive_floor_batch_native_provenance_operator_fill_preflight_completion_audit_current.json"
)
DEFAULT_OUT_CSV = (
    "casp17/casp17_competitive_floor_batch_native_provenance_operator_fill_preflight_completion_audit_current.csv"
)
DEFAULT_OUT_MD = (
    "casp17/CASP17_COMPETITIVE_FLOOR_BATCH_NATIVE_PROVENANCE_OPERATOR_FILL_PREFLIGHT_COMPLETION_AUDIT.md"
)

ROW_COLUMNS = [
    "target_id",
    "target_name",
    "audit_status",
    "target_preflight_folder",
    "folder_present",
    "readme_present",
    "operator_fill_template_present",
    "field_policy_present",
    "operator_template_expected_rows",
    "operator_template_csv_rows",
    "operator_template_row_mismatch",
    "field_policy_expected_rows",
    "field_policy_csv_rows",
    "field_policy_row_mismatch",
    "coordinate_copy_count",
    "competitive_proof_eligible",
    "author_serialized",
    "blockers",
]
CLAIM_BOUNDARY = (
    "CASP17 competitive-floor batch native/provenance operator-fill preflight completion audit only. "
    "It verifies target-named preflight folders, operator-fill templates, field policy rows, manifest "
    "presence, no-coordinate-copy hygiene, and proof boundary flags. It does not fill values, fetch "
    "native structures, clear no-leak provenance, compute native accuracy, serialize a CASP author code, "
    "or submit to CASP."
)


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _artifact(path_like: str | Path) -> str:
    text = str(path_like or "").strip()
    if not text:
        return ""
    path = _resolve(text).resolve()
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


def _read_csv(path_like: str | Path) -> tuple[list[str], list[dict[str, str]]]:
    path = _resolve(path_like)
    if not path.exists():
        return [], []
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), [dict(row) for row in reader]


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


def _present_file(path_like: str | Path) -> int:
    return 1 if _resolve(path_like).is_file() else 0


def _present_dir(path_like: str | Path) -> int:
    return 1 if _resolve(path_like).is_dir() else 0


def _coordinate_file_count(path_like: str | Path) -> int:
    path = _resolve(path_like)
    if not path.exists():
        return 0
    return sum(1 for item in path.rglob("*") if item.is_file() and item.suffix.lower() in {".pdb", ".cif"})


def _missing_columns(fieldnames: list[str], expected: list[str]) -> list[str]:
    return [column for column in expected if column not in fieldnames]


def _row_blockers(
    *,
    source: dict[str, Any],
    global_blockers: list[str],
) -> dict[str, Any]:
    target_id = _text(source.get("target_id")).upper()
    folder = _text(source.get("target_preflight_folder"))
    template_csv = _text(source.get("operator_fill_template_csv"))
    policy_csv = _text(source.get("field_policy_csv"))
    expected_policy_rows = _int(source.get("open_action_count"))
    blockers = list(global_blockers)

    folder_present = _present_dir(folder)
    readme_present = _present_file(_resolve(folder) / "README.md")
    template_present = _present_file(template_csv)
    policy_present = _present_file(policy_csv)
    template_fields, template_rows = _read_csv(template_csv)
    policy_fields, policy_rows = _read_csv(policy_csv)

    if not folder_present:
        blockers.append("target_preflight_folder_missing")
    if not readme_present:
        blockers.append("target_preflight_readme_missing")
    if not template_present:
        blockers.append("operator_fill_template_missing")
    if not policy_present:
        blockers.append("field_policy_missing")
    if template_present and _missing_columns(template_fields, preflight.INTAKE_COLUMNS):
        blockers.append("operator_fill_template_column_mismatch")
    if policy_present and _missing_columns(policy_fields, preflight.FIELD_POLICY_COLUMNS):
        blockers.append("field_policy_column_mismatch")
    if len(template_rows) != 1:
        blockers.append("operator_fill_template_row_mismatch")
    if template_rows and _text(template_rows[0].get("target_id")).upper() != target_id:
        blockers.append("operator_fill_template_target_id_mismatch")
    if len(policy_rows) != expected_policy_rows:
        blockers.append("field_policy_row_mismatch")
    if any(_text(row.get("target_id")).upper() != target_id for row in policy_rows):
        blockers.append("field_policy_target_id_mismatch")

    coordinate_count = _coordinate_file_count(folder)
    if coordinate_count:
        blockers.append("target_preflight_coordinate_copy_present")
    if _text(source.get("competitive_proof_eligible")).lower() != "false":
        blockers.append("competitive_proof_boundary_not_false")
    if _text(source.get("author_serialized")).lower() != "false":
        blockers.append("author_boundary_not_false")

    blockers = list(dict.fromkeys(blockers))
    return {
        "target_id": target_id,
        "target_name": _text(source.get("target_name")),
        "audit_status": "pass" if not blockers else "blocked",
        "target_preflight_folder": _artifact(folder),
        "folder_present": folder_present,
        "readme_present": readme_present,
        "operator_fill_template_present": template_present,
        "field_policy_present": policy_present,
        "operator_template_expected_rows": 1,
        "operator_template_csv_rows": len(template_rows),
        "operator_template_row_mismatch": 0 if len(template_rows) == 1 else 1,
        "field_policy_expected_rows": expected_policy_rows,
        "field_policy_csv_rows": len(policy_rows),
        "field_policy_row_mismatch": 0 if len(policy_rows) == expected_policy_rows else 1,
        "coordinate_copy_count": coordinate_count,
        "competitive_proof_eligible": "false",
        "author_serialized": "false",
        "blockers": ",".join(blockers),
    }


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    preflight_payload = _read_json(args.preflight_json)
    preflight_summary = _summary(preflight_payload)
    source_rows = _rows(preflight_payload)
    out_dir = _text(preflight_summary.get("out_dir"))
    global_blockers: list[str] = []
    if not _resolve(args.preflight_json).exists():
        global_blockers.append("operator_fill_preflight_json_missing")
    preflight_status = _text(preflight_summary.get("batch_native_provenance_operator_fill_preflight_status"))
    if preflight_status != "casp17_competitive_floor_batch_native_provenance_operator_fill_preflight_ready_for_operator_fill":
        global_blockers.append("operator_fill_preflight_not_ready")
    if not out_dir:
        global_blockers.append("operator_fill_preflight_out_dir_missing")
    else:
        if not _present_dir(out_dir):
            global_blockers.append("operator_fill_preflight_out_dir_missing")
        if not _present_file(_resolve(out_dir) / "manifest.json"):
            global_blockers.append("operator_fill_preflight_manifest_missing")
    if _int(preflight_summary.get("target_count")) != len(source_rows):
        global_blockers.append("operator_fill_preflight_target_count_mismatch")

    rows = [_row_blockers(source=row, global_blockers=global_blockers) for row in source_rows]
    blocked_rows = [row for row in rows if row["audit_status"] != "pass"]
    coordinate_count = _coordinate_file_count(out_dir) if out_dir else 0
    status = "casp17_competitive_floor_batch_native_provenance_operator_fill_preflight_completion_audit_pass"
    if blocked_rows or global_blockers or not rows:
        status = "casp17_competitive_floor_batch_native_provenance_operator_fill_preflight_completion_audit_blocked"
    first_blocked = blocked_rows[0] if blocked_rows else {}
    summary = {
        "packet_type": "casp17_competitive_floor_batch_native_provenance_operator_fill_preflight_completion_audit",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "batch_native_provenance_operator_fill_preflight_completion_audit_status": status,
        "operator_fill_preflight_json": _artifact(args.preflight_json),
        "operator_fill_preflight_status": preflight_status,
        "operator_fill_preflight_out_dir": _artifact(out_dir),
        "root_manifest_present": _present_file(_resolve(out_dir) / "manifest.json") if out_dir else 0,
        "target_count": len(rows),
        "target_pass_count": len(rows) - len(blocked_rows),
        "target_blocked_count": len(blocked_rows),
        "target_folder_count": sum(_int(row.get("folder_present")) for row in rows),
        "target_readme_count": sum(_int(row.get("readme_present")) for row in rows),
        "target_operator_template_file_count": sum(_int(row.get("operator_fill_template_present")) for row in rows),
        "target_field_policy_file_count": sum(_int(row.get("field_policy_present")) for row in rows),
        "operator_template_expected_rows": sum(_int(row.get("operator_template_expected_rows")) for row in rows),
        "operator_template_csv_rows": sum(_int(row.get("operator_template_csv_rows")) for row in rows),
        "operator_template_row_mismatch_count": sum(_int(row.get("operator_template_row_mismatch")) for row in rows),
        "field_policy_expected_rows": sum(_int(row.get("field_policy_expected_rows")) for row in rows),
        "field_policy_csv_rows": sum(_int(row.get("field_policy_csv_rows")) for row in rows),
        "field_policy_row_mismatch_count": sum(_int(row.get("field_policy_row_mismatch")) for row in rows),
        "coordinate_copy_count": coordinate_count,
        "target_coordinate_copy_count": sum(_int(row.get("coordinate_copy_count")) for row in rows),
        "competitive_proof_eligible_count": 0,
        "author_serialized_count": 0,
        "first_blocked_target_id": _text(first_blocked.get("target_id")),
        "first_blocker": _text(first_blocked.get("blockers")).split(",")[0] if first_blocked else "",
        "next_action": "Fill the target operator templates or batch intake CSV, then rerun the value gate.",
        "claim_boundary": CLAIM_BOUNDARY,
    }
    return {"summary": summary, "rows": rows}


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Competitive Floor Batch Native/Provenance Operator Fill Preflight Completion Audit",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- status: `{summary['batch_native_provenance_operator_fill_preflight_completion_audit_status']}`",
        f"- targets pass/blocked/total: `{summary['target_pass_count']}/{summary['target_blocked_count']}/{summary['target_count']}`",
        f"- target files folder/readme/template/policy: `{summary['target_folder_count']}/{summary['target_readme_count']}/{summary['target_operator_template_file_count']}/{summary['target_field_policy_file_count']}`",
        f"- operator template expected/csv/mismatch: `{summary['operator_template_expected_rows']}/{summary['operator_template_csv_rows']}/{summary['operator_template_row_mismatch_count']}`",
        f"- field policy expected/csv/mismatch: `{summary['field_policy_expected_rows']}/{summary['field_policy_csv_rows']}/{summary['field_policy_row_mismatch_count']}`",
        f"- coordinate copies preflight/target: `{summary['coordinate_copy_count']}/{summary['target_coordinate_copy_count']}`",
        f"- proof/author: `{summary['competitive_proof_eligible_count']}/{summary['author_serialized_count']}`",
        f"- first blocked: `{summary['first_blocked_target_id'] or '-'}` `{summary['first_blocker'] or '-'}`",
        "",
        "## Targets",
        "",
        "| target | status | template rows | policy rows | blockers |",
        "| --- | --- | ---: | ---: | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['target_id']}` | `{row['audit_status']}` | `{row['operator_template_csv_rows']}` | "
            f"`{row['field_policy_csv_rows']}` | `{row['blockers'] or '-'}` |"
        )
    lines.extend(["", "## Claim Boundary", "", CLAIM_BOUNDARY, ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def write_outputs(args: argparse.Namespace, payload: dict[str, Any]) -> None:
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"])
    _write_md(args.out_md, payload)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audit CASP17 batch native/provenance operator-fill preflight packet completion."
    )
    parser.add_argument("--preflight-json", default=DEFAULT_PREFLIGHT_JSON)
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

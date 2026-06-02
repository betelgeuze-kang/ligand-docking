#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]

DEFAULT_BATCH_KIT_JSON = "casp17/casp17_organic_ligand_metric_batch_operator_fill_kit_current.json"
DEFAULT_OUT_JSON = (
    "casp17/casp17_organic_ligand_metric_batch_operator_fill_kit_completion_audit_current.json"
)
DEFAULT_OUT_CSV = (
    "casp17/casp17_organic_ligand_metric_batch_operator_fill_kit_completion_audit_current.csv"
)
DEFAULT_OUT_MD = "casp17/CASP17_ORGANIC_LIGAND_METRIC_BATCH_OPERATOR_FILL_KIT_COMPLETION_AUDIT.md"

ROW_COLUMNS = [
    "candidate_id",
    "target_id",
    "ligand_id",
    "audit_status",
    "candidate_folder",
    "candidate_readme_present",
    "candidate_operator_fill_csv_present",
    "expected_field_count",
    "candidate_operator_fill_csv_rows",
    "candidate_row_mismatch",
    "candidate_summary_csv_match",
    "coordinate_copy_count",
    "proof_marker_count",
    "author_marker_count",
    "blockers",
]

CLAIM_BOUNDARY = (
    "CASP17 organic ligand metric batch operator-fill kit completion audit only. It verifies the "
    "batch intake files, candidate folders, per-candidate CSV row counts, manifest consistency, "
    "no-coordinate-copy hygiene, and proof boundary markers. It does not fill operator values, approve "
    "no-leak provenance, compute LDDT-PLI or BiSyRMSD, serialize a CASP author code, or submit to CASP."
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
    if not path.exists():
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
        if value and value not in {"false", "0", "no"}:
            count += 1
    return count


def _rows_by_candidate(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        candidate_id = _text(row.get("candidate_id"))
        if candidate_id:
            grouped.setdefault(candidate_id, []).append(row)
    return grouped


def _audit_candidate(
    candidate: dict[str, Any],
    *,
    kit_rows_by_candidate: dict[str, list[dict[str, Any]]],
    candidate_summary_csv_by_id: dict[str, dict[str, str]],
    global_blockers: list[str],
) -> dict[str, Any]:
    candidate_id = _text(candidate.get("candidate_id"))
    folder = _text(candidate.get("candidate_folder"))
    csv_path = _text(candidate.get("candidate_operator_fill_csv")) or str(_resolve(folder) / "operator_fill_rows.csv")
    readme_path = _text(candidate.get("candidate_readme")) or str(_resolve(folder) / "README.md")
    expected = _int(candidate.get("field_count"))
    candidate_rows = kit_rows_by_candidate.get(candidate_id, [])
    csv_rows = _read_csv_rows(csv_path) if _is_file(csv_path) else []
    blockers = list(global_blockers)
    folder_present = _is_dir(folder)
    readme_present = _is_file(readme_path)
    csv_present = _is_file(csv_path)
    if not folder_present:
        blockers.append("candidate_folder_missing")
    if not readme_present:
        blockers.append("candidate_readme_missing")
    if not csv_present:
        blockers.append("candidate_operator_fill_csv_missing")
    if len(candidate_rows) != expected:
        blockers.append("kit_candidate_row_count_mismatch")
    if len(csv_rows) != expected:
        blockers.append("candidate_operator_fill_csv_row_mismatch")
    if any(_text(row.get("candidate_id")) != candidate_id for row in csv_rows):
        blockers.append("candidate_operator_fill_csv_candidate_id_mismatch")
    summary_csv_row = candidate_summary_csv_by_id.get(candidate_id, {})
    candidate_summary_csv_match = int(
        bool(summary_csv_row)
        and _int(summary_csv_row.get("field_count")) == expected
        and _text(summary_csv_row.get("candidate_folder")) == _artifact(folder)
    )
    if not candidate_summary_csv_match:
        blockers.append("candidate_summary_csv_mismatch")
    coordinate_count = _coordinate_file_count(folder)
    if coordinate_count:
        blockers.append("candidate_coordinate_copy_present")
    proof_marker_count = _boundary_marker_count(candidate_rows + csv_rows, "competitive_proof_eligible")
    author_marker_count = _boundary_marker_count(candidate_rows + csv_rows, "author_serialized")
    if proof_marker_count:
        blockers.append("competitive_proof_marker_present")
    if author_marker_count:
        blockers.append("author_marker_present")
    blockers = list(dict.fromkeys(blockers))
    return {
        "candidate_id": candidate_id,
        "target_id": _text(candidate.get("target_id")),
        "ligand_id": _text(candidate.get("ligand_id")),
        "audit_status": "pass" if not blockers else "blocked",
        "candidate_folder": _artifact(folder),
        "candidate_readme_present": int(readme_present),
        "candidate_operator_fill_csv_present": int(csv_present),
        "expected_field_count": expected,
        "candidate_operator_fill_csv_rows": len(csv_rows),
        "candidate_row_mismatch": 0 if len(candidate_rows) == expected and len(csv_rows) == expected else 1,
        "candidate_summary_csv_match": candidate_summary_csv_match,
        "coordinate_copy_count": coordinate_count,
        "proof_marker_count": proof_marker_count,
        "author_marker_count": author_marker_count,
        "blockers": ",".join(blockers),
    }


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    kit_path = _resolve(args.batch_kit_json)
    kit_payload = _read_json(args.batch_kit_json)
    kit_summary = _summary(kit_payload)
    kit_rows = _rows(kit_payload)
    candidate_rows = _rows(kit_payload, "candidate_rows")
    batch_folder = _text(kit_summary.get("batch_folder"))
    batch_csv = _text(kit_summary.get("operator_fill_intake_batch_csv")) or str(
        _resolve(batch_folder) / "operator_fill_intake_batch.csv"
    )
    candidate_summary_csv = _text(kit_summary.get("candidate_summary_csv")) or str(
        _resolve(batch_folder) / "candidate_summary.csv"
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
        ("candidate_summary_csv_missing", candidate_summary_csv),
        ("rerun_commands_md_missing", rerun_commands_md),
        ("batch_manifest_json_missing", batch_manifest_json),
    ]
    for blocker, path_like in root_files:
        if not _is_file(path_like):
            global_blockers.append(blocker)
    batch_csv_rows = _read_csv_rows(batch_csv) if _is_file(batch_csv) else []
    candidate_summary_csv_rows = _read_csv_rows(candidate_summary_csv) if _is_file(candidate_summary_csv) else []
    candidate_summary_csv_by_id = {
        _text(row.get("candidate_id")): row for row in candidate_summary_csv_rows if _text(row.get("candidate_id"))
    }
    manifest_payload = _read_json(batch_manifest_json) if _is_file(batch_manifest_json) else {}
    manifest_summary = _summary(manifest_payload)
    if len(batch_csv_rows) != _int(kit_summary.get("field_count")):
        global_blockers.append("batch_csv_row_count_mismatch")
    if len(kit_rows) != _int(kit_summary.get("field_count")):
        global_blockers.append("kit_json_field_row_count_mismatch")
    if len(candidate_summary_csv_rows) != _int(kit_summary.get("candidate_count")):
        global_blockers.append("candidate_summary_csv_row_count_mismatch")
    if len(candidate_rows) != _int(kit_summary.get("candidate_count")):
        global_blockers.append("kit_json_candidate_row_count_mismatch")
    if manifest_summary and _int(manifest_summary.get("field_count")) != _int(kit_summary.get("field_count")):
        global_blockers.append("batch_manifest_field_count_mismatch")
    if manifest_summary and _int(manifest_summary.get("candidate_count")) != _int(kit_summary.get("candidate_count")):
        global_blockers.append("batch_manifest_candidate_count_mismatch")
    if not manifest_payload:
        global_blockers.append("batch_manifest_unreadable")
    root_coordinate_count = _coordinate_file_count(batch_folder)
    kit_rows_by_candidate = _rows_by_candidate(kit_rows)
    rows = [
        _audit_candidate(
            candidate,
            kit_rows_by_candidate=kit_rows_by_candidate,
            candidate_summary_csv_by_id=candidate_summary_csv_by_id,
            global_blockers=global_blockers,
        )
        for candidate in candidate_rows
    ]
    blocked_rows = [row for row in rows if row["audit_status"] != "pass"]
    per_candidate_csv_row_count = sum(_int(row.get("candidate_operator_fill_csv_rows")) for row in rows)
    candidate_row_mismatch_count = sum(_int(row.get("candidate_row_mismatch")) for row in rows)
    proof_marker_count = sum(_int(row.get("proof_marker_count")) for row in rows)
    author_marker_count = sum(_int(row.get("author_marker_count")) for row in rows)
    status = "casp17_organic_ligand_metric_batch_operator_fill_kit_completion_audit_pass"
    if blocked_rows or global_blockers or root_coordinate_count or not rows:
        status = "casp17_organic_ligand_metric_batch_operator_fill_kit_completion_audit_blocked"
    first = blocked_rows[0] if blocked_rows else {}
    summary = {
        "packet_type": "casp17_organic_ligand_metric_batch_operator_fill_kit_completion_audit",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "organic_ligand_metric_batch_operator_fill_kit_completion_audit_status": status,
        "batch_kit_json": _artifact(args.batch_kit_json),
        "batch_kit_status": _text(kit_summary.get("organic_ligand_metric_batch_operator_fill_kit_status")),
        "batch_folder": _artifact(batch_folder),
        "candidate_count": len(rows),
        "candidate_pass_count": len(rows) - len(blocked_rows),
        "candidate_blocked_count": len(blocked_rows),
        "field_count": _int(kit_summary.get("field_count")),
        "batch_csv_row_count": len(batch_csv_rows),
        "per_candidate_csv_row_count": per_candidate_csv_row_count,
        "candidate_row_mismatch_count": candidate_row_mismatch_count,
        "candidate_summary_csv_row_count": len(candidate_summary_csv_rows),
        "root_file_present_count": sum(1 for _blocker, path_like in root_files if _is_file(path_like)),
        "root_file_required_count": len(root_files),
        "batch_manifest_present_count": int(_is_file(batch_manifest_json)),
        "candidate_folder_present_count": sum(1 for row in rows if _is_dir(row.get("candidate_folder", ""))),
        "candidate_readme_present_count": sum(_int(row.get("candidate_readme_present")) for row in rows),
        "candidate_operator_fill_csv_present_count": sum(
            _int(row.get("candidate_operator_fill_csv_present")) for row in rows
        ),
        "coordinate_copy_count": root_coordinate_count,
        "proof_marker_count": proof_marker_count,
        "author_marker_count": author_marker_count,
        "first_blocked_candidate_id": _text(first.get("candidate_id")),
        "first_blocker": _text(first.get("blockers")).split(",", 1)[0] if _text(first.get("blockers")) else "",
        "next_action": (
            "repair the blocked batch operator fill kit files, then rerun this completion audit"
            if blocked_rows or global_blockers
            else "fill operator values in the batch intake CSV, then rerun review and sync gates"
        ),
        "claim_boundary": CLAIM_BOUNDARY,
    }
    return {"summary": summary, "rows": rows}


def _packet_row(payload: dict[str, Any]) -> dict[str, Any]:
    summary = payload["summary"]
    return {
        "status": summary["organic_ligand_metric_batch_operator_fill_kit_completion_audit_status"],
        "batch_kit_status": summary["batch_kit_status"],
        "candidate_pass_count": summary["candidate_pass_count"],
        "candidate_blocked_count": summary["candidate_blocked_count"],
        "candidate_count": summary["candidate_count"],
        "field_count": summary["field_count"],
        "batch_csv_row_count": summary["batch_csv_row_count"],
        "per_candidate_csv_row_count": summary["per_candidate_csv_row_count"],
        "candidate_row_mismatch_count": summary["candidate_row_mismatch_count"],
        "coordinate_copy_count": summary["coordinate_copy_count"],
        "proof_marker_count": summary["proof_marker_count"],
        "author_marker_count": summary["author_marker_count"],
        "first_blocked_candidate_id": summary["first_blocked_candidate_id"],
        "first_blocker": summary["first_blocker"],
        "next_action": summary["next_action"],
    }


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Organic Ligand Metric Batch Operator Fill Kit Completion Audit",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- status: `{summary['organic_ligand_metric_batch_operator_fill_kit_completion_audit_status']}`",
        f"- batch kit: `{summary['batch_kit_status'] or '-'}`",
        f"- candidates pass/blocked/total: `{summary['candidate_pass_count']}/{summary['candidate_blocked_count']}/{summary['candidate_count']}`",
        f"- fields expected/batch/per-candidate: `{summary['field_count']}/{summary['batch_csv_row_count']}/{summary['per_candidate_csv_row_count']}`",
        f"- root files present/required: `{summary['root_file_present_count']}/{summary['root_file_required_count']}`",
        f"- candidate folder/readme/csv: `{summary['candidate_folder_present_count']}/{summary['candidate_readme_present_count']}/{summary['candidate_operator_fill_csv_present_count']}`",
        f"- mismatches/coordinate/proof/author: `{summary['candidate_row_mismatch_count']}/{summary['coordinate_copy_count']}/{summary['proof_marker_count']}/{summary['author_marker_count']}`",
        f"- first blocked: `{summary['first_blocked_candidate_id'] or '-'}` `{summary['first_blocker'] or '-'}`",
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
        description="Audit CASP17 organic ligand metric batch operator fill kit completion."
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

#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]

DEFAULT_DROPZONES_JSON = "casp17/casp17_historical_seed_strict_blind_replacement_evidence_dropzones_current.json"
DEFAULT_AUDIT_DIR = "casp17/historical_seed_strict_blind_replacement_evidence_quality_audit"
DEFAULT_OUT_JSON = "casp17/casp17_historical_seed_strict_blind_replacement_evidence_quality_audit_current.json"
DEFAULT_OUT_CSV = "casp17/casp17_historical_seed_strict_blind_replacement_evidence_quality_audit_current.csv"
DEFAULT_OUT_MD = "casp17/CASP17_HISTORICAL_SEED_STRICT_BLIND_REPLACEMENT_EVIDENCE_QUALITY_AUDIT.md"

FILE_TYPES = {
    "prediction_pdb": "pdb",
    "native_pdb": "pdb",
    "native_authority_ref": "text",
    "no_leak_evidence_ref": "text",
    "ablation_manifest_ref": "json",
    "calibration_values_ref": "json",
}
PDB_FIELDS = {"prediction_pdb", "native_pdb"}
ROW_COLUMNS = [
    "queue_rank",
    "required_benchmark_id",
    "required_target_id",
    "scope",
    "quality_status",
    "ready_for_quality_review",
    "file_required_count",
    "file_present_count",
    "file_missing_count",
    "pdb_valid_count",
    "pdb_invalid_count",
    "supporting_valid_count",
    "supporting_invalid_count",
    "prediction_status",
    "native_status",
    "prediction_atom_count",
    "native_atom_count",
    "prediction_ca_count",
    "native_ca_count",
    "prediction_sha256",
    "native_sha256",
    "prediction_native_relation",
    "quality_md",
    "blockers",
    "next_action",
]
CLAIM_BOUNDARY = (
    "Local CASP17 strict-blind replacement evidence quality audit only. It validates whether dropzone evidence "
    "files are present, readable, structurally plausible, and prediction/native PDBs are distinct. It does not "
    "approve no-leak provenance, select replacement targets, import values into intake CSVs, compute CASP metrics, "
    "or submit to CASP."
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


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _read_csv(path_like: str | Path) -> tuple[list[dict[str, str]], list[str]]:
    path = _resolve(path_like)
    if not path.exists():
        return [], [f"{path.name}_missing"]
    if not path.is_file():
        return [], [f"{path.name}_not_file"]
    try:
        with path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            rows = [dict(row) for row in reader]
    except OSError:
        return [], [f"{path.name}_unreadable"]
    blockers: list[str] = []
    if not rows:
        blockers.append(f"{path.name}_empty")
    return rows, blockers


def _write_csv(path_like: str | Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _safe_name(value: str) -> str:
    return "".join(ch.lower() if ch.isalnum() else "_" for ch in value).strip("_") or "unknown"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _pdb_stats(path: Path) -> dict[str, Any]:
    stats = {
        "status": "valid_pdb",
        "atom_count": 0,
        "ca_count": 0,
        "coordinate_error_count": 0,
        "sha256": "",
        "blocker": "",
    }
    try:
        stats["sha256"] = _sha256(path)
        with path.open("r", encoding="utf-8", errors="ignore") as handle:
            for line in handle:
                if not line.startswith("ATOM"):
                    continue
                stats["atom_count"] += 1
                if line[12:16].strip() == "CA":
                    stats["ca_count"] += 1
                try:
                    float(line[30:38])
                    float(line[38:46])
                    float(line[46:54])
                except ValueError:
                    parts = line.split()
                    try:
                        float(parts[6])
                        float(parts[7])
                        float(parts[8])
                    except (IndexError, ValueError):
                        stats["coordinate_error_count"] += 1
    except OSError:
        stats.update({"status": "invalid_pdb", "blocker": "pdb_unreadable"})
        return stats
    if stats["atom_count"] <= 0:
        stats.update({"status": "invalid_pdb", "blocker": "pdb_has_no_protein_atoms"})
    elif stats["coordinate_error_count"] > 0:
        stats.update({"status": "invalid_pdb", "blocker": "pdb_coordinate_parse_error"})
    return stats


def _supporting_status(path: Path, file_type: str) -> tuple[str, str, str]:
    try:
        if file_type == "json":
            payload = json.loads(path.read_text(encoding="utf-8"))
            if payload in ({}, []):
                return "invalid_supporting_file", "json_payload_empty", _sha256(path)
            return "valid_supporting_file", "", _sha256(path)
        text = path.read_text(encoding="utf-8", errors="replace").strip()
    except (OSError, json.JSONDecodeError):
        return "invalid_supporting_file", f"{file_type}_unreadable_or_invalid", ""
    if not text:
        return "invalid_supporting_file", f"{file_type}_empty", _sha256(path)
    upper = text.upper()
    if "REQUIRED_" in upper or "TODO" in upper:
        return "invalid_supporting_file", f"{file_type}_placeholder_content", _sha256(path)
    return "valid_supporting_file", "", _sha256(path)


def _file_audit(patch: dict[str, str]) -> dict[str, Any]:
    field_name = _text(patch.get("field_name"))
    path_text = _text(patch.get("source_path")) or _text(patch.get("recommended_value"))
    file_type = FILE_TYPES.get(field_name, "unknown")
    row = {
        "field_name": field_name,
        "file_type": file_type,
        "source_path": path_text,
        "status": "",
        "atom_count": 0,
        "ca_count": 0,
        "sha256": "",
        "blocker": "",
    }
    if not path_text:
        row.update({"status": "missing", "blocker": "source_path_missing"})
        return row
    path = _resolve(path_text)
    if not path.exists():
        row.update({"status": "missing", "blocker": "file_missing"})
        return row
    if not path.is_file():
        row.update({"status": "invalid_supporting_file", "blocker": "path_not_file"})
        return row
    if file_type == "pdb":
        stats = _pdb_stats(path)
        row.update(
            {
                "status": stats["status"],
                "atom_count": stats["atom_count"],
                "ca_count": stats["ca_count"],
                "sha256": stats["sha256"],
                "blocker": stats["blocker"],
            }
        )
        return row
    status, blocker, digest = _supporting_status(path, file_type)
    row.update({"status": status, "sha256": digest, "blocker": blocker})
    return row


def _file_patches(dropzone_row: dict[str, Any]) -> tuple[list[dict[str, str]], list[str]]:
    patch_csv = _text(dropzone_row.get("patch_preview_csv"))
    patch_rows, blockers = _read_csv(patch_csv)
    if blockers:
        return [], blockers
    return [
        row
        for row in patch_rows
        if _text(row.get("field_kind")) == "file" and _text(row.get("field_name")) in FILE_TYPES
    ], []


def _quality_row(dropzone_row: dict[str, Any], audit_dir: str | Path) -> dict[str, Any]:
    patches, patch_blockers = _file_patches(dropzone_row)
    audits = [_file_audit(patch) for patch in patches]
    by_field = {audit["field_name"]: audit for audit in audits}
    missing_expected = sorted(set(FILE_TYPES) - set(by_field))
    blockers = list(patch_blockers)
    blockers.extend(f"{field}:patch_missing" for field in missing_expected)
    blockers.extend(f"{audit['field_name']}:{audit['blocker']}" for audit in audits if audit["blocker"])

    prediction = by_field.get("prediction_pdb", {})
    native = by_field.get("native_pdb", {})
    relation = "waiting_on_pdb_pair"
    if prediction.get("status") == "valid_pdb" and native.get("status") == "valid_pdb":
        if _text(prediction.get("sha256")) == _text(native.get("sha256")):
            relation = "identical_sha256_blocked"
            blockers.append("prediction_native_identical_file")
        else:
            relation = "distinct_sha256_pass"

    file_required = len(FILE_TYPES)
    file_present = sum(1 for audit in audits if audit["status"] != "missing")
    file_missing = file_required - file_present
    pdb_valid = sum(1 for audit in audits if audit["file_type"] == "pdb" and audit["status"] == "valid_pdb")
    pdb_invalid = sum(1 for audit in audits if audit["file_type"] == "pdb" and audit["status"] not in {"valid_pdb", "missing"})
    supporting_valid = sum(1 for audit in audits if audit["file_type"] != "pdb" and audit["status"] == "valid_supporting_file")
    supporting_invalid = sum(
        1 for audit in audits if audit["file_type"] != "pdb" and audit["status"] not in {"valid_supporting_file", "missing"}
    )
    if file_missing:
        status = "awaiting_evidence_files"
        next_action = "place all six strict-blind evidence files in the dropzone and rerun dropzones/quality audit"
    elif blockers:
        status = "blocked_evidence_quality"
        next_action = "repair invalid evidence files before import or promotion"
    else:
        status = "ready_for_operator_quality_review"
        next_action = "review evidence hashes, then run import gate and operator value gate"

    queue_rank = _int(dropzone_row.get("queue_rank"))
    benchmark_id = _text(dropzone_row.get("required_benchmark_id"))
    md = _resolve(audit_dir) / f"{queue_rank:02d}_{_safe_name(benchmark_id)}" / "QUALITY_AUDIT.md"
    row = {
        "queue_rank": queue_rank,
        "required_benchmark_id": benchmark_id,
        "required_target_id": _text(dropzone_row.get("required_target_id")),
        "scope": _text(dropzone_row.get("scope")),
        "quality_status": status,
        "ready_for_quality_review": "true" if status == "ready_for_operator_quality_review" else "false",
        "file_required_count": file_required,
        "file_present_count": file_present,
        "file_missing_count": file_missing,
        "pdb_valid_count": pdb_valid,
        "pdb_invalid_count": pdb_invalid,
        "supporting_valid_count": supporting_valid,
        "supporting_invalid_count": supporting_invalid,
        "prediction_status": _text(prediction.get("status")),
        "native_status": _text(native.get("status")),
        "prediction_atom_count": _int(prediction.get("atom_count")),
        "native_atom_count": _int(native.get("atom_count")),
        "prediction_ca_count": _int(prediction.get("ca_count")),
        "native_ca_count": _int(native.get("ca_count")),
        "prediction_sha256": _text(prediction.get("sha256")),
        "native_sha256": _text(native.get("sha256")),
        "prediction_native_relation": relation,
        "quality_md": _artifact(md),
        "blockers": ",".join(blockers),
        "next_action": next_action,
    }
    _write_row_md(md, row, audits)
    return row


def _write_row_md(path: Path, row: dict[str, Any], audits: list[dict[str, Any]]) -> None:
    lines = [
        f"# {row['required_benchmark_id']} Evidence Quality Audit",
        "",
        f"- status: `{row['quality_status']}`",
        f"- ready_for_quality_review: `{row['ready_for_quality_review']}`",
        f"- required target: `{row['required_target_id']}`",
        f"- scope: `{row['scope']}`",
        f"- files present/missing/required: `{row['file_present_count']}/{row['file_missing_count']}/{row['file_required_count']}`",
        f"- pdb valid/invalid: `{row['pdb_valid_count']}/{row['pdb_invalid_count']}`",
        f"- supporting valid/invalid: `{row['supporting_valid_count']}/{row['supporting_invalid_count']}`",
        f"- prediction/native relation: `{row['prediction_native_relation']}`",
        f"- blockers: `{row['blockers'] or '-'}`",
        f"- next action: {row['next_action'] or '-'}",
        "",
        "## File Audits",
        "",
        "| field | type | status | atoms | CA | sha256 | blocker | path |",
        "| --- | --- | --- | ---: | ---: | --- | --- | --- |",
    ]
    for audit in audits:
        digest = _text(audit.get("sha256"))
        lines.append(
            f"| `{audit['field_name']}` | `{audit['file_type']}` | `{audit['status']}` | "
            f"{audit['atom_count']} | {audit['ca_count']} | `{digest[:12] if digest else '-'}` | "
            f"`{audit['blocker'] or '-'}` | `{audit['source_path']}` |"
        )
    lines.extend(["", "## Claim Boundary", "", CLAIM_BOUNDARY, ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    dropzones_payload = _read_json(args.dropzones_json)
    dropzone_rows = _rows(dropzones_payload)
    input_blockers: list[str] = []
    if not _resolve(args.dropzones_json).exists():
        input_blockers.append("strict_blind_replacement_evidence_dropzones_json_missing")
    rows = [_quality_row(row, args.audit_dir) for row in dropzone_rows]
    summary = _build_summary(args, rows, input_blockers, dropzones_payload)
    return {"summary": summary, "rows": rows}


def _build_summary(
    args: argparse.Namespace,
    rows: list[dict[str, Any]],
    input_blockers: list[str],
    dropzones_payload: dict[str, Any],
) -> dict[str, Any]:
    by_status: dict[str, int] = defaultdict(int)
    for row in rows:
        by_status[_text(row.get("quality_status"))] += 1
    first_open = next((row for row in rows if row.get("quality_status") != "ready_for_operator_quality_review"), {})
    summary = {
        "packet_type": "casp17_historical_seed_strict_blind_replacement_evidence_quality_audit",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "strict_blind_replacement_evidence_quality_audit_status": _overall_status(rows, input_blockers),
        "dropzones_json": _artifact(args.dropzones_json),
        "audit_dir": _artifact(args.audit_dir),
        "dropzone_status": _text(_summary(dropzones_payload).get("strict_blind_replacement_evidence_dropzones_status")),
        "slot_count": len(rows),
        "ready_for_quality_review_count": by_status["ready_for_operator_quality_review"],
        "awaiting_evidence_files_count": by_status["awaiting_evidence_files"],
        "blocked_evidence_quality_count": by_status["blocked_evidence_quality"],
        "file_required_count": sum(_int(row.get("file_required_count")) for row in rows),
        "file_present_count": sum(_int(row.get("file_present_count")) for row in rows),
        "file_missing_count": sum(_int(row.get("file_missing_count")) for row in rows),
        "pdb_valid_slot_count": sum(1 for row in rows if _int(row.get("pdb_valid_count")) == 2),
        "pdb_invalid_slot_count": sum(1 for row in rows if _int(row.get("pdb_invalid_count")) > 0),
        "supporting_valid_slot_count": sum(1 for row in rows if _int(row.get("supporting_valid_count")) == 4),
        "supporting_invalid_slot_count": sum(1 for row in rows if _int(row.get("supporting_invalid_count")) > 0),
        "prediction_native_distinct_count": sum(
            1 for row in rows if row.get("prediction_native_relation") == "distinct_sha256_pass"
        ),
        "prediction_native_identical_count": sum(
            1 for row in rows if row.get("prediction_native_relation") == "identical_sha256_blocked"
        ),
        "first_open_benchmark_id": _text(first_open.get("required_benchmark_id")),
        "first_open_status": _text(first_open.get("quality_status")),
        "first_next_action": _text(first_open.get("next_action")) or "provide strict-blind evidence quality inputs",
        "input_blockers": ",".join(input_blockers),
        "claim_boundary": CLAIM_BOUNDARY,
    }
    return summary


def _overall_status(rows: list[dict[str, Any]], input_blockers: list[str]) -> str:
    if input_blockers:
        return "blocked_missing_input"
    if not rows:
        return "blocked_missing_dropzone_rows"
    if all(row.get("quality_status") == "ready_for_operator_quality_review" for row in rows):
        return "strict_blind_evidence_quality_ready_for_operator_review"
    if any(row.get("quality_status") == "blocked_evidence_quality" for row in rows):
        return "blocked_evidence_quality"
    return "awaiting_strict_blind_evidence_quality_files"


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Historical Seed Strict-Blind Replacement Evidence Quality Audit",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- status: `{summary['strict_blind_replacement_evidence_quality_audit_status']}`",
        f"- slots ready/awaiting/blocked/total: `{summary['ready_for_quality_review_count']}/{summary['awaiting_evidence_files_count']}/{summary['blocked_evidence_quality_count']}/{summary['slot_count']}`",
        f"- files present/missing/required: `{summary['file_present_count']}/{summary['file_missing_count']}/{summary['file_required_count']}`",
        f"- pdb valid/invalid slots: `{summary['pdb_valid_slot_count']}/{summary['pdb_invalid_slot_count']}`",
        f"- supporting valid/invalid slots: `{summary['supporting_valid_slot_count']}/{summary['supporting_invalid_slot_count']}`",
        f"- prediction/native distinct/identical: `{summary['prediction_native_distinct_count']}/{summary['prediction_native_identical_count']}`",
        f"- first open: `{summary['first_open_benchmark_id'] or '-'}` `{summary['first_open_status'] or '-'}`",
        f"- next action: {summary['first_next_action'] or '-'}",
        "",
        "## Quality Rows",
        "",
        "| rank | benchmark | scope | status | files present/missing | pdb valid/invalid | supporting valid/invalid | relation | blockers |",
        "| ---: | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| {row['queue_rank']} | `{row['required_benchmark_id']}` | `{row['scope']}` | "
            f"`{row['quality_status']}` | {row['file_present_count']}/{row['file_missing_count']} | "
            f"{row['pdb_valid_count']}/{row['pdb_invalid_count']} | "
            f"{row['supporting_valid_count']}/{row['supporting_invalid_count']} | "
            f"`{row['prediction_native_relation']}` | `{row['blockers'] or '-'}` |"
        )
    if not payload["rows"]:
        lines.append("| - | - | - | `blocked_missing_dropzone_rows` | 0/0 | 0/0 | 0/0 | - | provide inputs |")
    lines.extend(["", "## Claim Boundary", "", str(summary["claim_boundary"]), ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def write_outputs(args: argparse.Namespace, payload: dict[str, Any]) -> None:
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"], ROW_COLUMNS)
    _write_md(args.out_md, payload)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit CASP17 strict-blind replacement evidence file quality.")
    parser.add_argument("--dropzones-json", default=DEFAULT_DROPZONES_JSON)
    parser.add_argument("--audit-dir", default=DEFAULT_AUDIT_DIR)
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

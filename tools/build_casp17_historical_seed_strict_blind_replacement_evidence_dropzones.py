#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]

DEFAULT_INTAKE_JSON = "casp17/casp17_historical_seed_strict_blind_replacement_intake_current.json"
DEFAULT_DROPZONE_DIR = "casp17/historical_seed_strict_blind_replacement_evidence_dropzones"
DEFAULT_OUT_JSON = "casp17/casp17_historical_seed_strict_blind_replacement_evidence_dropzones_current.json"
DEFAULT_OUT_CSV = "casp17/casp17_historical_seed_strict_blind_replacement_evidence_dropzones_current.csv"
DEFAULT_OUT_MD = "casp17/CASP17_HISTORICAL_SEED_STRICT_BLIND_REPLACEMENT_EVIDENCE_DROPZONES.md"

FILE_REQUIREMENTS = [
    ("prediction_pdb", "prediction", "replacement_prediction.pdb", "valid local prediction PDB"),
    ("native_pdb", "native", "replacement_native.pdb", "authoritative local native PDB"),
    ("native_authority_ref", "authority", "native_authority.md", "native authority/source reference"),
    ("no_leak_evidence_ref", "no_leak", "no_leak_evidence.md", "independent no-leak evidence"),
    ("ablation_manifest_ref", "ablation", "ablation_manifest.json", "same-run ablation manifest"),
    ("calibration_values_ref", "calibration", "calibration_values.json", "calibration value ledger"),
]
OPERATOR_VALUE_FIELDS = [
    "replacement_target_id",
    "replacement_benchmark_id",
    "target_identity_non_current_historical",
    "prediction_created_at",
    "native_release_date",
    "prediction_generated_before_native_release",
    "public_template_or_native_used_for_prediction",
    "other_team_model_used",
    "post_release_information_used",
    "operator_clearance",
]
ROW_COLUMNS = [
    "queue_rank",
    "required_benchmark_id",
    "required_target_id",
    "scope",
    "metric_profile",
    "dropzone_status",
    "dropzone_folder",
    "file_required_count",
    "file_present_count",
    "file_missing_count",
    "operator_value_required_count",
    "patch_preview_csv",
    "dropzone_md",
    "next_action",
    "blockers",
]
PATCH_COLUMNS = [
    "queue_rank",
    "required_benchmark_id",
    "field_name",
    "field_kind",
    "recommended_value",
    "source_status",
    "source_path",
    "destination_intake_csv",
    "operator_action",
    "notes",
]
CLAIM_BOUNDARY = (
    "Local CASP17 historical strict-blind replacement evidence dropzones only. It creates per-slot folders and "
    "patch previews for the files and operator values needed by the strict-blind replacement intake. It does not "
    "select replacement targets, create evidence, approve no-leak provenance, mutate intake CSVs, compute CASP "
    "metrics, or submit to CASP."
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


def _write_csv(path_like: str | Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _safe_name(value: str) -> str:
    return "".join(ch.lower() if ch.isalnum() else "_" for ch in value).strip("_") or "unknown"


def _dropzone_folder(dropzone_dir: str | Path, intake_row: dict[str, Any]) -> Path:
    queue_rank = _int(intake_row.get("queue_rank"))
    benchmark_id = _text(intake_row.get("required_benchmark_id"))
    return _resolve(dropzone_dir) / f"{queue_rank:02d}_{_safe_name(benchmark_id)}"


def _ensure_dropzone_dirs(folder: Path) -> None:
    for _, subdir, _, _ in FILE_REQUIREMENTS:
        (folder / subdir).mkdir(parents=True, exist_ok=True)


def _patch_rows(intake_row: dict[str, Any], folder: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    destination_intake = _text(intake_row.get("intake_csv"))
    for field_name, subdir, filename, note in FILE_REQUIREMENTS:
        source_path = folder / subdir / filename
        source_present = source_path.is_file()
        rows.append(
            {
                "queue_rank": _int(intake_row.get("queue_rank")),
                "required_benchmark_id": _text(intake_row.get("required_benchmark_id")),
                "field_name": field_name,
                "field_kind": "file",
                "recommended_value": _artifact(source_path) if source_present else "",
                "source_status": "present" if source_present else "missing",
                "source_path": _artifact(source_path),
                "destination_intake_csv": destination_intake,
                "operator_action": (
                    "review and copy recommended_value into replacement_candidate_intake.csv"
                    if source_present
                    else f"place {note} at source_path"
                ),
                "notes": note,
            }
        )
    for field_name in OPERATOR_VALUE_FIELDS:
        rows.append(
            {
                "queue_rank": _int(intake_row.get("queue_rank")),
                "required_benchmark_id": _text(intake_row.get("required_benchmark_id")),
                "field_name": field_name,
                "field_kind": "operator_value",
                "recommended_value": "",
                "source_status": "operator_required",
                "source_path": "",
                "destination_intake_csv": destination_intake,
                "operator_action": "fill and clear this value in replacement_candidate_intake.csv",
                "notes": "required non-file strict-blind intake value",
            }
        )
    return rows


def _write_dropzone_md(path: Path, row: dict[str, Any], patches: list[dict[str, Any]]) -> None:
    lines = [
        f"# {row['required_benchmark_id']} Strict-Blind Evidence Dropzone",
        "",
        f"- status: `{row['dropzone_status']}`",
        f"- required target: `{row['required_target_id']}`",
        f"- scope: `{row['scope']}`",
        f"- files present/missing/required: `{row['file_present_count']}/{row['file_missing_count']}/{row['file_required_count']}`",
        f"- operator values required: `{row['operator_value_required_count']}`",
        f"- patch preview: `{row['patch_preview_csv']}`",
        f"- blockers: `{row['blockers'] or '-'}`",
        f"- next action: {row['next_action'] or '-'}",
        "",
        "## Expected Evidence Files",
        "",
        "| field | path | status |",
        "| --- | --- | --- |",
    ]
    for patch in patches:
        if patch["field_kind"] != "file":
            continue
        lines.append(f"| `{patch['field_name']}` | `{patch['source_path']}` | `{patch['source_status']}` |")
    lines.extend(["", "## Claim Boundary", "", CLAIM_BOUNDARY, ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def _build_row(intake_row: dict[str, Any], dropzone_dir: str | Path) -> dict[str, Any]:
    folder = _dropzone_folder(dropzone_dir, intake_row)
    _ensure_dropzone_dirs(folder)
    patches = _patch_rows(intake_row, folder)
    patch_preview_csv = folder / "replacement_intake_patch_preview.csv"
    dropzone_md = folder / "EVIDENCE_DROPZONE.md"
    _write_csv(patch_preview_csv, patches, PATCH_COLUMNS)
    present = sum(1 for patch in patches if patch["field_kind"] == "file" and patch["source_status"] == "present")
    missing = len(FILE_REQUIREMENTS) - present
    status = "ready_for_intake_patch_review" if missing == 0 else "awaiting_strict_blind_evidence_files"
    blockers = []
    if missing:
        blockers.append(f"missing_files:{missing}")
    blockers.append(f"operator_values_required:{len(OPERATOR_VALUE_FIELDS)}")
    row = {
        "queue_rank": _int(intake_row.get("queue_rank")),
        "required_benchmark_id": _text(intake_row.get("required_benchmark_id")),
        "required_target_id": _text(intake_row.get("required_target_id")),
        "scope": _text(intake_row.get("scope")),
        "metric_profile": _text(intake_row.get("metric_profile")),
        "dropzone_status": status,
        "dropzone_folder": _artifact(folder),
        "file_required_count": len(FILE_REQUIREMENTS),
        "file_present_count": present,
        "file_missing_count": missing,
        "operator_value_required_count": len(OPERATOR_VALUE_FIELDS),
        "patch_preview_csv": _artifact(patch_preview_csv),
        "dropzone_md": _artifact(dropzone_md),
        "next_action": (
            "review patch preview and copy cleared values into replacement_candidate_intake.csv"
            if missing == 0
            else "place strict-blind evidence files in this dropzone, then rerun dropzone and intake preflight"
        ),
        "blockers": ",".join(blockers),
    }
    _write_dropzone_md(dropzone_md, row, patches)
    return row


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    intake_payload = _read_json(args.intake_json)
    intake_summary = _summary(intake_payload)
    intake_rows = _rows(intake_payload)
    rows = [_build_row(row, args.dropzone_dir) for row in intake_rows]
    input_blockers: list[str] = []
    if not _resolve(args.intake_json).exists():
        input_blockers.append("strict_blind_replacement_intake_json_missing")
    ready = sum(1 for row in rows if row.get("dropzone_status") == "ready_for_intake_patch_review")
    awaiting = len(rows) - ready
    file_required = sum(_int(row.get("file_required_count")) for row in rows)
    file_present = sum(_int(row.get("file_present_count")) for row in rows)
    file_missing = sum(_int(row.get("file_missing_count")) for row in rows)
    operator_required = sum(_int(row.get("operator_value_required_count")) for row in rows)
    if input_blockers:
        status = "blocked_missing_input"
    elif not rows:
        status = "blocked_missing_intake_rows"
    elif ready == len(rows):
        status = "strict_blind_evidence_files_ready_for_intake_patch"
    else:
        status = "awaiting_strict_blind_evidence_files"
    first_open = next((row for row in rows if row.get("dropzone_status") != "ready_for_intake_patch_review"), {})
    summary = {
        "packet_type": "casp17_historical_seed_strict_blind_replacement_evidence_dropzones",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "strict_blind_replacement_evidence_dropzone_status": status,
        "intake_json": _artifact(args.intake_json),
        "intake_status": _text(intake_summary.get("strict_blind_replacement_intake_status")),
        "dropzone_dir": _artifact(args.dropzone_dir),
        "dropzone_count": len(rows),
        "ready_for_intake_patch_count": ready,
        "awaiting_file_count": awaiting,
        "file_required_count": file_required,
        "file_present_count": file_present,
        "file_missing_count": file_missing,
        "operator_value_required_count": operator_required,
        "patch_preview_count": len(rows),
        "first_open_benchmark_id": _text(first_open.get("required_benchmark_id")),
        "first_next_action": _text(first_open.get("next_action")) or "provide strict-blind replacement intake rows",
        "input_blockers": ",".join(input_blockers),
        "claim_boundary": CLAIM_BOUNDARY,
    }
    return {"summary": summary, "rows": rows}


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Historical Seed Strict-Blind Replacement Evidence Dropzones",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- status: `{summary['strict_blind_replacement_evidence_dropzone_status']}`",
        f"- intake status: `{summary['intake_status'] or '-'}`",
        f"- dropzones ready/awaiting/total: `{summary['ready_for_intake_patch_count']}/{summary['awaiting_file_count']}/{summary['dropzone_count']}`",
        f"- evidence files present/missing/required: `{summary['file_present_count']}/{summary['file_missing_count']}/{summary['file_required_count']}`",
        f"- operator values required: `{summary['operator_value_required_count']}`",
        f"- patch previews: `{summary['patch_preview_count']}`",
        f"- first open: `{summary['first_open_benchmark_id'] or '-'}`",
        f"- next action: {summary['first_next_action'] or '-'}",
        "",
        "## Dropzones",
        "",
        "| rank | benchmark | scope | status | files present | files missing | folder |",
        "| ---: | --- | --- | --- | ---: | ---: | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| {row['queue_rank']} | `{row['required_benchmark_id']}` | `{row['scope']}` | "
            f"`{row['dropzone_status']}` | {row['file_present_count']} | {row['file_missing_count']} | "
            f"`{row['dropzone_folder']}` |"
        )
    if not payload["rows"]:
        lines.append("| - | - | - | `blocked_missing_intake_rows` | 0 | 0 | - |")
    lines.extend(["", "## Claim Boundary", "", str(summary["claim_boundary"]), ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def write_outputs(args: argparse.Namespace, payload: dict[str, Any]) -> None:
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"], ROW_COLUMNS)
    _write_md(args.out_md, payload)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build CASP17 strict-blind replacement evidence dropzones.")
    parser.add_argument("--intake-json", default=DEFAULT_INTAKE_JSON)
    parser.add_argument("--dropzone-dir", default=DEFAULT_DROPZONE_DIR)
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

#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]

DEFAULT_DROPZONES_JSON = "casp17/casp17_historical_seed_strict_blind_replacement_evidence_dropzones_current.json"
DEFAULT_QUALITY_JSON = "casp17/casp17_historical_seed_strict_blind_replacement_evidence_quality_audit_current.json"
DEFAULT_OUT_JSON = "casp17/casp17_historical_seed_strict_blind_replacement_evidence_action_board_current.json"
DEFAULT_OUT_CSV = "casp17/casp17_historical_seed_strict_blind_replacement_evidence_action_board_current.csv"
DEFAULT_OUT_MD = "casp17/CASP17_HISTORICAL_SEED_STRICT_BLIND_REPLACEMENT_EVIDENCE_ACTION_BOARD.md"

FILE_FIELDS = {
    "prediction_pdb": "prediction",
    "native_pdb": "native",
    "native_authority_ref": "authority",
    "no_leak_evidence_ref": "no_leak",
    "ablation_manifest_ref": "ablation",
    "calibration_values_ref": "calibration",
}
ROW_COLUMNS = [
    "action_id",
    "queue_rank",
    "required_benchmark_id",
    "required_target_id",
    "scope",
    "field_name",
    "evidence_class",
    "action_status",
    "source_status",
    "source_path",
    "expected_filename",
    "dropzone_folder",
    "patch_preview_csv",
    "quality_status",
    "quality_blocker",
    "verify_command",
    "next_action",
]
CLAIM_BOUNDARY = (
    "Local CASP17 strict-blind replacement evidence action board only. It expands dropzone patch previews into "
    "file-level placement actions for the six strict-blind evidence files per slot. It does not create evidence, "
    "select replacement targets, approve no-leak provenance, mutate intake CSVs, compute CASP metrics, or submit "
    "to CASP."
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


def _read_csv(path_like: str | Path) -> tuple[list[dict[str, str]], list[str]]:
    if not _text(path_like):
        return [], ["patch_preview_csv_missing"]
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
    if not rows:
        return [], [f"{path.name}_empty"]
    return rows, []


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


def _quality_by_benchmark(quality_rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {_text(row.get("required_benchmark_id")): row for row in quality_rows}


def _field_quality_blocker(quality_row: dict[str, Any], field_name: str) -> str:
    blockers = _text(quality_row.get("blockers"))
    for blocker in [part.strip() for part in blockers.split(",") if part.strip()]:
        if blocker.startswith(f"{field_name}:"):
            return blocker.split(":", 1)[1]
    return ""


def _status_for(patch: dict[str, str], quality_row: dict[str, Any]) -> tuple[str, str]:
    source_path = _text(patch.get("source_path")) or _text(patch.get("recommended_value"))
    source_status = _text(patch.get("source_status"))
    field_name = _text(patch.get("field_name"))
    quality_blocker = _field_quality_blocker(quality_row, field_name)
    if source_status != "present" or not source_path or not _resolve(source_path).is_file():
        return "open_missing_file", quality_blocker or "file_missing"
    if quality_blocker:
        return "blocked_quality_review", quality_blocker
    return "ready_for_quality_audit", ""


def _expected_filename(source_path: str) -> str:
    return Path(source_path).name if source_path else ""


def _action_rows(dropzones: list[dict[str, Any]], quality_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    quality = _quality_by_benchmark(quality_rows)
    rows: list[dict[str, Any]] = []
    action_index = 1
    for dropzone in dropzones:
        patch_csv = _text(dropzone.get("patch_preview_csv"))
        patches, blockers = _read_csv(patch_csv)
        if blockers:
            rows.append(_blocked_patch_action(action_index, dropzone, patch_csv, blockers))
            action_index += 1
            continue
        for patch in patches:
            field_name = _text(patch.get("field_name"))
            if _text(patch.get("field_kind")) != "file" or field_name not in FILE_FIELDS:
                continue
            benchmark_id = _text(dropzone.get("required_benchmark_id")) or _text(patch.get("required_benchmark_id"))
            quality_row = quality.get(benchmark_id, {})
            status, quality_blocker = _status_for(patch, quality_row)
            source_path = _text(patch.get("source_path")) or _text(patch.get("recommended_value"))
            rows.append(
                {
                    "action_id": f"strict_blind_evidence_{action_index:03d}",
                    "queue_rank": _int(dropzone.get("queue_rank") or patch.get("queue_rank")),
                    "required_benchmark_id": benchmark_id,
                    "required_target_id": _text(dropzone.get("required_target_id")),
                    "scope": _text(dropzone.get("scope")),
                    "field_name": field_name,
                    "evidence_class": FILE_FIELDS[field_name],
                    "action_status": status,
                    "source_status": _text(patch.get("source_status")),
                    "source_path": _artifact(source_path) if source_path else "",
                    "expected_filename": _expected_filename(source_path),
                    "dropzone_folder": _text(dropzone.get("dropzone_folder")),
                    "patch_preview_csv": patch_csv,
                    "quality_status": _text(quality_row.get("quality_status")),
                    "quality_blocker": quality_blocker,
                    "verify_command": (
                        "python3 tools/build_casp17_historical_seed_strict_blind_replacement_evidence_quality_audit.py"
                    ),
                    "next_action": _next_action(status, field_name, source_path),
                }
            )
            action_index += 1
    return rows


def _blocked_patch_action(
    action_index: int,
    dropzone: dict[str, Any],
    patch_csv: str,
    blockers: list[str],
) -> dict[str, Any]:
    return {
        "action_id": f"strict_blind_evidence_{action_index:03d}",
        "queue_rank": _int(dropzone.get("queue_rank")),
        "required_benchmark_id": _text(dropzone.get("required_benchmark_id")),
        "required_target_id": _text(dropzone.get("required_target_id")),
        "scope": _text(dropzone.get("scope")),
        "field_name": "",
        "evidence_class": "",
        "action_status": "blocked_patch_preview",
        "source_status": "blocked",
        "source_path": "",
        "expected_filename": "",
        "dropzone_folder": _text(dropzone.get("dropzone_folder")),
        "patch_preview_csv": patch_csv,
        "quality_status": "",
        "quality_blocker": ",".join(blockers),
        "verify_command": "python3 tools/build_casp17_historical_seed_strict_blind_replacement_evidence_dropzones.py",
        "next_action": "repair or regenerate the strict-blind dropzone patch preview",
    }


def _next_action(status: str, field_name: str, source_path: str) -> str:
    if status == "open_missing_file":
        return f"place {field_name} evidence at {source_path}"
    if status == "blocked_quality_review":
        return f"repair {field_name} evidence and rerun quality audit"
    if status == "ready_for_quality_audit":
        return "rerun quality audit, then evidence import gate"
    return "repair strict-blind evidence action source"


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    dropzones_payload = _read_json(args.dropzones_json)
    quality_payload = _read_json(args.quality_json)
    input_blockers: list[str] = []
    if not _resolve(args.dropzones_json).exists():
        input_blockers.append("strict_blind_replacement_evidence_dropzones_json_missing")
    if not _resolve(args.quality_json).exists():
        input_blockers.append("strict_blind_replacement_evidence_quality_audit_json_missing")
    rows = _action_rows(_rows(dropzones_payload), _rows(quality_payload))
    summary = _build_summary(args, rows, input_blockers, dropzones_payload, quality_payload)
    return {"summary": summary, "rows": rows}


def _build_summary(
    args: argparse.Namespace,
    rows: list[dict[str, Any]],
    input_blockers: list[str],
    dropzones_payload: dict[str, Any],
    quality_payload: dict[str, Any],
) -> dict[str, Any]:
    first_open = next((row for row in rows if row.get("action_status") != "ready_for_quality_audit"), {})
    by_field = {
        field: sum(1 for row in rows if row.get("field_name") == field and row.get("action_status") == "open_missing_file")
        for field in FILE_FIELDS
    }
    ready = sum(1 for row in rows if row.get("action_status") == "ready_for_quality_audit")
    open_missing = sum(1 for row in rows if row.get("action_status") == "open_missing_file")
    blocked = sum(1 for row in rows if _text(row.get("action_status")).startswith("blocked"))
    summary = {
        "packet_type": "casp17_historical_seed_strict_blind_replacement_evidence_action_board",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "strict_blind_replacement_evidence_action_board_status": _overall_status(rows, input_blockers),
        "dropzones_json": _artifact(args.dropzones_json),
        "quality_json": _artifact(args.quality_json),
        "dropzone_status": _text(_summary(dropzones_payload).get("strict_blind_replacement_evidence_dropzone_status")),
        "quality_status": _text(
            _summary(quality_payload).get("strict_blind_replacement_evidence_quality_audit_status")
        ),
        "action_count": len(rows),
        "ready_for_quality_audit_count": ready,
        "open_missing_file_count": open_missing,
        "blocked_count": blocked,
        "prediction_pdb_missing_count": by_field["prediction_pdb"],
        "native_pdb_missing_count": by_field["native_pdb"],
        "native_authority_missing_count": by_field["native_authority_ref"],
        "no_leak_evidence_missing_count": by_field["no_leak_evidence_ref"],
        "ablation_manifest_missing_count": by_field["ablation_manifest_ref"],
        "calibration_values_missing_count": by_field["calibration_values_ref"],
        "first_open_action_id": _text(first_open.get("action_id")),
        "first_open_benchmark_id": _text(first_open.get("required_benchmark_id")),
        "first_open_field": _text(first_open.get("field_name")),
        "first_open_source_path": _text(first_open.get("source_path")),
        "first_next_action": _text(first_open.get("next_action")) or "provide strict-blind evidence action inputs",
        "input_blockers": ",".join(input_blockers),
        "claim_boundary": CLAIM_BOUNDARY,
    }
    return summary


def _overall_status(rows: list[dict[str, Any]], input_blockers: list[str]) -> str:
    if input_blockers:
        return "blocked_missing_input"
    if not rows:
        return "blocked_missing_evidence_actions"
    if any(_text(row.get("action_status")).startswith("blocked") for row in rows):
        return "blocked_evidence_action_review"
    if any(row.get("action_status") == "open_missing_file" for row in rows):
        return "awaiting_strict_blind_evidence_actions"
    return "strict_blind_evidence_actions_ready_for_quality_audit"


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Historical Seed Strict-Blind Replacement Evidence Action Board",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- status: `{summary['strict_blind_replacement_evidence_action_board_status']}`",
        f"- actions ready/open/blocked/total: `{summary['ready_for_quality_audit_count']}/{summary['open_missing_file_count']}/{summary['blocked_count']}/{summary['action_count']}`",
        f"- missing prediction/native/authority/no-leak/ablation/calibration: `{summary['prediction_pdb_missing_count']}/{summary['native_pdb_missing_count']}/{summary['native_authority_missing_count']}/{summary['no_leak_evidence_missing_count']}/{summary['ablation_manifest_missing_count']}/{summary['calibration_values_missing_count']}`",
        f"- first open: `{summary['first_open_action_id'] or '-'}` `{summary['first_open_benchmark_id'] or '-'}` `{summary['first_open_field'] or '-'}`",
        f"- first source path: `{summary['first_open_source_path'] or '-'}`",
        f"- next action: {summary['first_next_action'] or '-'}",
        "",
        "## Open Actions",
        "",
        "| action | benchmark | scope | field | status | source path | next action |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    open_rows = [row for row in payload["rows"] if row.get("action_status") != "ready_for_quality_audit"]
    for row in open_rows[:80]:
        lines.append(
            f"| `{row['action_id']}` | `{row['required_benchmark_id']}` | `{row['scope']}` | "
            f"`{row['field_name'] or '-'}` | `{row['action_status']}` | `{row['source_path'] or '-'}` | "
            f"{row['next_action']} |"
        )
    if len(open_rows) > 80:
        lines.append(f"| ... | ... | ... | ... | ... | ... | `{len(open_rows) - 80} more actions in CSV` |")
    if not open_rows:
        lines.append("| - | - | - | - | `ready_for_quality_audit` | - | rerun quality audit |")
    lines.extend(["", "## Claim Boundary", "", str(summary["claim_boundary"]), ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def write_outputs(args: argparse.Namespace, payload: dict[str, Any]) -> None:
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"], ROW_COLUMNS)
    _write_md(args.out_md, payload)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build CASP17 strict-blind evidence file action board.")
    parser.add_argument("--dropzones-json", default=DEFAULT_DROPZONES_JSON)
    parser.add_argument("--quality-json", default=DEFAULT_QUALITY_JSON)
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

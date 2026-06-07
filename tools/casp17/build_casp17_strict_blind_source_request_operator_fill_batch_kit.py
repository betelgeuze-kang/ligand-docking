#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
from collections import defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]

DEFAULT_WORKLIST_JSON = "casp17/casp17_strict_blind_source_request_operator_fill_worklist_current.json"
DEFAULT_OUT_DIR = "casp17/strict_blind_source_request_operator_fill_batch_kit"
DEFAULT_OUT_JSON = "casp17/casp17_strict_blind_source_request_operator_fill_batch_kit_current.json"
DEFAULT_OUT_CSV = "casp17/casp17_strict_blind_source_request_operator_fill_batch_kit_current.csv"
DEFAULT_OUT_MD = "casp17/CASP17_STRICT_BLIND_SOURCE_REQUEST_OPERATOR_FILL_BATCH_KIT.md"

READY_STATUS = "field_ready_for_fulfillment_gate"
RERUN_COMMANDS = [
    "python3 tools/casp17/build_casp17_strict_blind_source_request_fulfillment_gate.py",
    "python3 tools/casp17/build_casp17_strict_blind_source_request_operator_fill_worklist.py",
    "python3 tools/casp17/build_casp17_strict_blind_source_request_operator_fill_worklist_completion_audit.py",
    "python3 tools/casp17/build_casp17_strict_blind_source_request_operator_fill_batch_kit.py",
    "python3 tools/casp17/build_casp17_strict_blind_source_request_operator_fill_batch_kit_completion_audit.py",
    "python3 tools/casp17/build_casp17_strict_blind_source_request_operator_sync_plan.py",
    "python3 tools/casp17/build_casp17_strict_blind_source_request_closure_board.py",
    "python3 tools/build_casp17_workbench_index.py",
]

FIELD_COLUMNS = [
    "fill_id",
    "request_index",
    "request_id",
    "candidate_target_id",
    "candidate_scope",
    "request_kind",
    "field_order",
    "field_key",
    "operator_template_csv",
    "operator_value",
    "operator_evidence_ref",
    "operator_notes",
    "value_status",
    "evidence_status",
    "fill_status",
    "first_blocker",
    "next_action",
]
SUMMARY_COLUMNS = [
    "request_index",
    "request_id",
    "candidate_target_id",
    "candidate_scope",
    "request_kind",
    "field_count",
    "field_ready_count",
    "field_blocked_count",
    "operator_value_missing_count",
    "operator_evidence_missing_count",
    "candidate_replacement_field_count",
    "source_template_count",
    "source_template_csv",
    "source_request_folder",
    "request_batch_folder",
    "request_operator_fill_csv",
    "request_readme",
    "first_field_key",
    "first_blocker",
    "first_next_action",
]
ROW_COLUMNS = [
    "batch_status",
    "worklist_status",
    "batch_folder",
    "operator_fill_intake_batch_csv",
    "request_summary_csv",
    "rerun_commands_md",
    "batch_manifest_json",
    "request_count",
    "ready_request_count",
    "blocked_request_count",
    "field_count",
    "field_ready_count",
    "field_blocked_count",
    "operator_value_missing_count",
    "operator_evidence_missing_count",
    "candidate_replacement_field_count",
    "source_template_count",
    "source_request_folder_count",
    "first_request_id",
    "first_target_id",
    "first_field_key",
    "first_blocker",
    "next_action",
]

CLAIM_BOUNDARY = (
    "Local CASP17 strict-blind source-request operator-fill batch kit only. It consolidates the "
    "existing source-request operator-fill worklist into one batch intake CSV plus request packets. "
    "It does not mutate source templates, fill values, approve no-leak provenance, copy coordinates, "
    "compute CASP metrics, mark competitive proof, serialize a CASP author code, push remotes, or "
    "submit to CASP."
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


def _safe_slug(value: str) -> str:
    slug = "".join(ch if ch.isalnum() or ch in {"_", "-"} else "_" for ch in value).strip("_")
    return slug[:140] or "source_request"


def _source_request_folder(row: dict[str, Any]) -> str:
    template = _text(row.get("operator_template_csv"))
    return _artifact(_resolve(template).parent) if template else ""


def _request_sort_key(row: dict[str, Any]) -> tuple[int, str]:
    request_id = _text(row.get("request_id"))
    digits = "".join(ch for ch in request_id if ch.isdigit())
    return (_int(digits), request_id)


def _rows_by_request(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[_text(row.get("request_id"))].append(row)
    return dict(sorted(grouped.items(), key=lambda item: _request_sort_key(item[1][0] if item[1] else {})))


def _field_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    request_order: dict[str, int] = {}
    normalized: list[dict[str, Any]] = []
    for row in sorted(rows, key=lambda item: (_request_sort_key(item), _text(item.get("fill_id")))):
        request_id = _text(row.get("request_id"))
        if request_id not in request_order:
            request_order[request_id] = len(request_order) + 1
        normalized.append(
            {
                "fill_id": _text(row.get("fill_id")),
                "request_index": request_order[request_id],
                "request_id": request_id,
                "candidate_target_id": _text(row.get("candidate_target_id")),
                "candidate_scope": _text(row.get("candidate_scope")),
                "request_kind": _text(row.get("request_kind")),
                "field_order": len([existing for existing in normalized if existing["request_id"] == request_id]) + 1,
                "field_key": _text(row.get("field_key")),
                "operator_template_csv": _text(row.get("operator_template_csv")),
                "operator_value": _text(row.get("operator_value")),
                "operator_evidence_ref": _text(row.get("operator_evidence_ref")),
                "operator_notes": "",
                "value_status": _text(row.get("value_status")),
                "evidence_status": _text(row.get("evidence_status")),
                "fill_status": _text(row.get("fill_status")),
                "first_blocker": _text(row.get("first_blocker")),
                "next_action": _text(row.get("next_action")),
            }
        )
    return normalized


def _request_folder_name(index: int, rows: list[dict[str, Any]]) -> str:
    first = rows[0] if rows else {}
    target = _safe_slug(_text(first.get("candidate_target_id")) or _text(first.get("request_id")))
    request_id = _safe_slug(_text(first.get("request_id")))
    return f"{index:02d}_{request_id}_{target}"


def _request_summary_rows(rows: list[dict[str, Any]], out_dir: str | Path) -> list[dict[str, Any]]:
    summaries: list[dict[str, Any]] = []
    for request_index, (request_id, request_rows) in enumerate(_rows_by_request(rows).items(), start=1):
        ordered = sorted(request_rows, key=lambda row: _int(row.get("field_order")))
        blocked = [row for row in ordered if row["fill_status"] != READY_STATUS]
        first = blocked[0] if blocked else (ordered[0] if ordered else {})
        source_templates = {row["operator_template_csv"] for row in ordered if row["operator_template_csv"]}
        source_request_folders = {_source_request_folder(row) for row in ordered if _source_request_folder(row)}
        request_folder = _artifact(_resolve(out_dir) / _request_folder_name(request_index, ordered))
        summaries.append(
            {
                "request_index": request_index,
                "request_id": request_id,
                "candidate_target_id": _text(first.get("candidate_target_id")),
                "candidate_scope": _text(first.get("candidate_scope")),
                "request_kind": _text(first.get("request_kind")),
                "field_count": len(ordered),
                "field_ready_count": sum(1 for row in ordered if row["fill_status"] == READY_STATUS),
                "field_blocked_count": sum(1 for row in ordered if row["fill_status"] != READY_STATUS),
                "operator_value_missing_count": sum(1 for row in ordered if row["value_status"] != "value_present"),
                "operator_evidence_missing_count": sum(
                    1 for row in ordered if row["evidence_status"] == "evidence_required_missing"
                ),
                "candidate_replacement_field_count": sum(
                    1 for row in ordered if row["fill_status"] == "blocked_candidate_replacement_required"
                ),
                "source_template_count": len(source_templates),
                "source_template_csv": sorted(source_templates)[0] if source_templates else "",
                "source_request_folder": sorted(source_request_folders)[0] if source_request_folders else "",
                "request_batch_folder": request_folder,
                "request_operator_fill_csv": _artifact(_resolve(request_folder) / "operator_fill_rows.csv"),
                "request_readme": _artifact(_resolve(request_folder) / "README.md"),
                "first_field_key": _text(first.get("field_key")),
                "first_blocker": _text(first.get("first_blocker")),
                "first_next_action": _text(first.get("next_action")),
            }
        )
    return summaries


def _status(input_missing: bool, rows: list[dict[str, Any]], request_rows: list[dict[str, Any]]) -> str:
    if input_missing:
        return "blocked_strict_blind_source_request_operator_fill_worklist_missing"
    if not rows:
        return "blocked_strict_blind_source_request_operator_fill_batch_rows_missing"
    if any(row["field_blocked_count"] for row in request_rows):
        return "strict_blind_source_request_operator_fill_batch_kit_ready_for_operator_fill"
    return "strict_blind_source_request_operator_fill_batch_kit_complete"


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    worklist_path = _resolve(args.worklist_json)
    worklist_payload = _read_json(worklist_path)
    worklist_summary = _summary(worklist_payload)
    rows = _field_rows(_rows(worklist_payload)) if worklist_path.exists() else []
    request_rows = _request_summary_rows(rows, args.out_dir)
    blocked_requests = [row for row in request_rows if _int(row.get("field_blocked_count"))]
    blocked_fields = [row for row in rows if row["fill_status"] != READY_STATUS]
    source_templates = {row["operator_template_csv"] for row in rows if row["operator_template_csv"]}
    source_request_folders = {_source_request_folder(row) for row in rows if _source_request_folder(row)}
    first = blocked_fields[0] if blocked_fields else (rows[0] if rows else {})
    batch_status = _status(not worklist_path.exists(), rows, request_rows)
    summary = {
        "packet_type": "casp17_strict_blind_source_request_operator_fill_batch_kit",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "strict_blind_source_request_operator_fill_batch_kit_status": batch_status,
        "batch_status": batch_status,
        "worklist_json": _artifact(args.worklist_json),
        "worklist_status": _text(worklist_summary.get("source_request_operator_fill_worklist_status")),
        "batch_folder": _artifact(args.out_dir),
        "operator_fill_intake_batch_csv": _artifact(_resolve(args.out_dir) / "operator_fill_intake_batch.csv"),
        "request_summary_csv": _artifact(_resolve(args.out_dir) / "request_summary.csv"),
        "rerun_commands_md": _artifact(_resolve(args.out_dir) / "RERUN_COMMANDS.md"),
        "batch_manifest_json": _artifact(_resolve(args.out_dir) / "batch_manifest.json"),
        "request_count": len(request_rows),
        "ready_request_count": len(request_rows) - len(blocked_requests),
        "blocked_request_count": len(blocked_requests),
        "field_count": len(rows),
        "field_ready_count": sum(1 for row in rows if row["fill_status"] == READY_STATUS),
        "field_blocked_count": len(blocked_fields),
        "operator_value_missing_count": sum(1 for row in rows if row["value_status"] != "value_present"),
        "operator_evidence_missing_count": sum(
            1 for row in rows if row["evidence_status"] == "evidence_required_missing"
        ),
        "candidate_replacement_field_count": sum(
            1 for row in rows if row["fill_status"] == "blocked_candidate_replacement_required"
        ),
        "source_template_count": len(source_templates),
        "source_request_folder_count": len(source_request_folders),
        "first_request_id": _text(first.get("request_id")),
        "first_target_id": _text(first.get("candidate_target_id")),
        "first_field_key": _text(first.get("field_key")),
        "first_blocker": _text(first.get("first_blocker")),
        "first_next_action": _text(first.get("next_action")),
        "next_action": _text(first.get("next_action"))
        or "fill the batch CSV and source templates, then rerun the listed commands",
        "claim_boundary": CLAIM_BOUNDARY,
    }
    return {
        "summary": summary,
        "rows": rows,
        "request_rows": request_rows,
        "rerun_commands": RERUN_COMMANDS,
    }


def _packet_row(payload: dict[str, Any]) -> dict[str, Any]:
    summary = payload["summary"]
    return {column: summary.get(column, "") for column in ROW_COLUMNS}


def _write_batch_folder(args: argparse.Namespace, payload: dict[str, Any]) -> None:
    root = _resolve(args.out_dir)
    root.mkdir(parents=True, exist_ok=True)
    _write_csv(root / "operator_fill_intake_batch.csv", payload["rows"], FIELD_COLUMNS)
    _write_csv(root / "request_summary.csv", payload["request_rows"], SUMMARY_COLUMNS)
    _write_json(
        root / "batch_manifest.json",
        {
            "summary": payload["summary"],
            "claim_boundary": CLAIM_BOUNDARY,
            "rerun_commands": payload["rerun_commands"],
            "request_rows": payload["request_rows"],
        },
    )
    (root / "RERUN_COMMANDS.md").write_text(
        "\n".join(["# Rerun Commands", "", *[f"- `{command}`" for command in payload["rerun_commands"]], ""]),
        encoding="utf-8",
    )
    rows_by_request = _rows_by_request(payload["rows"])
    folder_by_request = {row["request_id"]: row["request_batch_folder"] for row in payload["request_rows"]}
    for request_id, rows in rows_by_request.items():
        folder = _resolve(folder_by_request.get(request_id, ""))
        folder.mkdir(parents=True, exist_ok=True)
        _write_csv(folder / "operator_fill_rows.csv", rows, FIELD_COLUMNS)
        first = next((row for row in rows if row["fill_status"] != READY_STATUS), rows[0] if rows else {})
        lines = [
            f"# {request_id} Strict-Blind Source Request Fill",
            "",
            f"- target: `{first.get('candidate_target_id', '') or '-'}`",
            f"- scope: `{first.get('candidate_scope', '') or '-'}`",
            f"- request kind: `{first.get('request_kind', '') or '-'}`",
            f"- fields ready/blocked/total: `{sum(1 for row in rows if row['fill_status'] == READY_STATUS)}/{sum(1 for row in rows if row['fill_status'] != READY_STATUS)}/{len(rows)}`",
            f"- missing value/evidence: `{sum(1 for row in rows if row['value_status'] != 'value_present')}/{sum(1 for row in rows if row['evidence_status'] == 'evidence_required_missing')}`",
            f"- first field: `{first.get('field_key', '') or '-'}` `{first.get('first_blocker', '') or '-'}`",
            "",
            "## Fields",
            "",
            "| field | status | value | evidence | source template |",
            "| --- | --- | --- | --- | --- |",
        ]
        for row in rows:
            lines.append(
                f"| `{row['field_key']}` | `{row['fill_status']}` | `{row['value_status']}` | "
                f"`{row['evidence_status']}` | `{row['operator_template_csv'] or '-'}` |"
            )
        lines.extend(["", "## Claim Boundary", "", CLAIM_BOUNDARY, ""])
        (folder / "README.md").write_text("\n".join(lines), encoding="utf-8")


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Strict-Blind Source Request Operator Fill Batch Kit",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- status: `{summary['strict_blind_source_request_operator_fill_batch_kit_status']}`",
        f"- worklist: `{summary['worklist_status'] or '-'}`",
        f"- requests ready/blocked/total: `{summary['ready_request_count']}/{summary['blocked_request_count']}/{summary['request_count']}`",
        f"- fields ready/blocked/total: `{summary['field_ready_count']}/{summary['field_blocked_count']}/{summary['field_count']}`",
        f"- missing value/evidence: `{summary['operator_value_missing_count']}/{summary['operator_evidence_missing_count']}`",
        f"- candidate-replacement fields: `{summary['candidate_replacement_field_count']}`",
        f"- sources template/folder: `{summary['source_template_count']}/{summary['source_request_folder_count']}`",
        f"- first: `{summary['first_request_id'] or '-'}` `{summary['first_target_id'] or '-'}` `{summary['first_field_key'] or '-'}` `{summary['first_blocker'] or '-'}`",
        "",
        "## Kit Files",
        "",
        f"- batch intake: `{summary['operator_fill_intake_batch_csv']}`",
        f"- request summary: `{summary['request_summary_csv']}`",
        f"- rerun commands: `{summary['rerun_commands_md']}`",
        f"- manifest: `{summary['batch_manifest_json']}`",
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
    _write_batch_folder(args, payload)
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, [_packet_row(payload)], ROW_COLUMNS)
    _write_md(args.out_md, payload)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build CASP17 strict-blind source request operator fill batch kit.")
    parser.add_argument("--worklist-json", default=DEFAULT_WORKLIST_JSON)
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
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

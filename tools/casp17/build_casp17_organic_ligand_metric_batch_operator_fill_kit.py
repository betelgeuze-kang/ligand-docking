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

DEFAULT_WORKLIST_JSON = "casp17/casp17_organic_ligand_metric_operator_fill_worklist_current.json"
DEFAULT_OUT_DIR = "casp17/organic_ligand_metric_batch_operator_fill_kit"
DEFAULT_OUT_JSON = "casp17/casp17_organic_ligand_metric_batch_operator_fill_kit_current.json"
DEFAULT_OUT_CSV = "casp17/casp17_organic_ligand_metric_batch_operator_fill_kit_current.csv"
DEFAULT_OUT_MD = "casp17/CASP17_ORGANIC_LIGAND_METRIC_BATCH_OPERATOR_FILL_KIT.md"

READY_STATUS = "field_ready_for_review_gate"
RERUN_COMMANDS = [
    "python3 tools/casp17/build_casp17_organic_ligand_metric_evidence_review_gate.py",
    "python3 tools/casp17/build_casp17_organic_ligand_metric_operator_fill_worklist.py",
    "python3 tools/build_casp17_organic_ligand_metric_batch_operator_fill_kit.py",
    "python3 tools/casp17/build_casp17_organic_ligand_metric_first_operator_fill_kit.py",
    "python3 tools/casp17/build_casp17_organic_ligand_metric_evidence_sync_plan.py",
    "python3 tools/build_casp17_workbench_index.py",
]

FIELD_COLUMNS = [
    "fill_id",
    "candidate_rank",
    "candidate_id",
    "target_id",
    "ligand_id",
    "field_order",
    "field_key",
    "required_operator_value_format",
    "source_operator_template_csv",
    "source_evidence_stub_md",
    "linked_action_md",
    "operator_value",
    "operator_evidence_ref",
    "operator_clearance",
    "operator_id",
    "value_status",
    "evidence_ref_status",
    "clearance_status",
    "operator_id_status",
    "fill_status",
    "first_blocker",
    "next_action",
]
SUMMARY_COLUMNS = [
    "candidate_id",
    "target_id",
    "ligand_id",
    "field_count",
    "field_ready_count",
    "field_blocked_count",
    "operator_value_missing_count",
    "operator_evidence_ref_missing_count",
    "operator_clearance_missing_count",
    "operator_id_missing_count",
    "source_template_count",
    "source_stub_count",
    "linked_action_count",
    "candidate_folder",
    "candidate_operator_fill_csv",
    "candidate_readme",
    "first_field_key",
    "first_blocker",
    "first_next_action",
]
ROW_COLUMNS = [
    "batch_status",
    "batch_folder",
    "operator_fill_intake_batch_csv",
    "candidate_summary_csv",
    "rerun_commands_md",
    "batch_manifest_json",
    "candidate_count",
    "ready_candidate_count",
    "blocked_candidate_count",
    "field_count",
    "field_ready_count",
    "field_blocked_count",
    "operator_value_missing_count",
    "operator_evidence_ref_missing_count",
    "operator_clearance_missing_count",
    "operator_id_missing_count",
    "source_template_count",
    "source_stub_count",
    "linked_action_count",
    "first_candidate_id",
    "first_field_key",
    "first_blocker",
    "next_action",
]

CLAIM_BOUNDARY = (
    "Local CASP17 organic ligand metric batch operator-fill kit only. It consolidates the existing "
    "organic ligand operator-fill worklist into one batch intake CSV plus candidate packets. It does "
    "not mutate evidence templates, fill values, approve no-leak provenance, compute LDDT-PLI or "
    "BiSyRMSD, mark competitive proof, serialize a CASP author code, or submit to CASP."
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


def _safe_slug(value: str) -> str:
    slug = "".join(ch if ch.isalnum() or ch in {"_", "-"} else "_" for ch in value).strip("_")
    return slug[:140] or "organic_ligand_candidate"


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


def _field_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {column: _text(row.get(column)) for column in FIELD_COLUMNS}
        for row in sorted(rows, key=lambda row: (_int(row.get("candidate_rank")), _int(row.get("field_order"))))
    ]


def _candidate_summary_rows(rows: list[dict[str, Any]], out_dir: str | Path) -> list[dict[str, Any]]:
    rows_by_candidate: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        rows_by_candidate[_text(row.get("candidate_id"))].append(row)
    summaries: list[dict[str, Any]] = []
    for index, (candidate_id, candidate_rows) in enumerate(rows_by_candidate.items(), start=1):
        ordered = _field_rows(candidate_rows)
        blocked = [row for row in ordered if row["fill_status"] != READY_STATUS]
        first = blocked[0] if blocked else (ordered[0] if ordered else {})
        ligand_id = _text(first.get("ligand_id")) or candidate_id
        folder = _artifact(_resolve(out_dir) / f"{index:02d}_{_safe_slug(ligand_id)}")
        summaries.append(
            {
                "candidate_id": candidate_id,
                "target_id": _text(first.get("target_id")),
                "ligand_id": ligand_id,
                "field_count": len(ordered),
                "field_ready_count": sum(1 for row in ordered if row["fill_status"] == READY_STATUS),
                "field_blocked_count": sum(1 for row in ordered if row["fill_status"] != READY_STATUS),
                "operator_value_missing_count": sum(1 for row in ordered if row["value_status"] != "value_present"),
                "operator_evidence_ref_missing_count": sum(
                    1 for row in ordered if row["evidence_ref_status"] != "evidence_ref_present"
                ),
                "operator_clearance_missing_count": sum(
                    1 for row in ordered if row["clearance_status"] != "clearance_present"
                ),
                "operator_id_missing_count": sum(1 for row in ordered if row["operator_id_status"] != "operator_id_present"),
                "source_template_count": len({row["source_operator_template_csv"] for row in ordered if row["source_operator_template_csv"]}),
                "source_stub_count": len({row["source_evidence_stub_md"] for row in ordered if row["source_evidence_stub_md"]}),
                "linked_action_count": len({row["linked_action_md"] for row in ordered if row["linked_action_md"]}),
                "candidate_folder": folder,
                "candidate_operator_fill_csv": _artifact(_resolve(folder) / "operator_fill_rows.csv"),
                "candidate_readme": _artifact(_resolve(folder) / "README.md"),
                "first_field_key": _text(first.get("field_key")),
                "first_blocker": _text(first.get("first_blocker")),
                "first_next_action": _text(first.get("next_action")),
            }
        )
    return summaries


def _status(input_missing: bool, rows: list[dict[str, Any]], candidate_rows: list[dict[str, Any]]) -> str:
    if input_missing:
        return "blocked_organic_ligand_metric_operator_fill_worklist_missing"
    if not rows:
        return "blocked_organic_ligand_metric_batch_operator_fill_rows_missing"
    if any(row["field_blocked_count"] for row in candidate_rows):
        return "organic_ligand_metric_batch_operator_fill_kit_ready_for_operator_fill"
    return "organic_ligand_metric_batch_operator_fill_kit_complete"


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    worklist_path = _resolve(args.worklist_json)
    worklist_payload = _read_json(worklist_path)
    worklist_summary = _summary(worklist_payload)
    rows = _field_rows(_rows(worklist_payload)) if worklist_path.exists() else []
    candidate_rows = _candidate_summary_rows(rows, args.out_dir)
    blocked_candidates = [row for row in candidate_rows if _int(row.get("field_blocked_count"))]
    blocked_fields = [row for row in rows if row["fill_status"] != READY_STATUS]
    first = blocked_fields[0] if blocked_fields else (rows[0] if rows else {})
    summary = {
        "packet_type": "casp17_organic_ligand_metric_batch_operator_fill_kit",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "organic_ligand_metric_batch_operator_fill_kit_status": _status(
            not worklist_path.exists(), rows, candidate_rows
        ),
        "worklist_json": _artifact(args.worklist_json),
        "worklist_status": _text(worklist_summary.get("organic_ligand_metric_operator_fill_worklist_status")),
        "batch_folder": _artifact(args.out_dir),
        "operator_fill_intake_batch_csv": _artifact(_resolve(args.out_dir) / "operator_fill_intake_batch.csv"),
        "candidate_summary_csv": _artifact(_resolve(args.out_dir) / "candidate_summary.csv"),
        "rerun_commands_md": _artifact(_resolve(args.out_dir) / "RERUN_COMMANDS.md"),
        "batch_manifest_json": _artifact(_resolve(args.out_dir) / "batch_manifest.json"),
        "candidate_count": len(candidate_rows),
        "ready_candidate_count": len(candidate_rows) - len(blocked_candidates),
        "blocked_candidate_count": len(blocked_candidates),
        "field_count": len(rows),
        "field_ready_count": sum(1 for row in rows if row["fill_status"] == READY_STATUS),
        "field_blocked_count": len(blocked_fields),
        "operator_value_missing_count": sum(1 for row in rows if row["value_status"] != "value_present"),
        "operator_evidence_ref_missing_count": sum(
            1 for row in rows if row["evidence_ref_status"] != "evidence_ref_present"
        ),
        "operator_clearance_missing_count": sum(1 for row in rows if row["clearance_status"] != "clearance_present"),
        "operator_id_missing_count": sum(1 for row in rows if row["operator_id_status"] != "operator_id_present"),
        "source_template_count": len({row["source_operator_template_csv"] for row in rows if row["source_operator_template_csv"]}),
        "source_stub_count": len({row["source_evidence_stub_md"] for row in rows if row["source_evidence_stub_md"]}),
        "linked_action_count": len({row["linked_action_md"] for row in rows if row["linked_action_md"]}),
        "first_candidate_id": _text(first.get("candidate_id")),
        "first_field_key": _text(first.get("field_key")),
        "first_blocker": _text(first.get("first_blocker")),
        "first_next_action": _text(first.get("next_action")),
        "next_action": _text(first.get("next_action"))
        or "fill the batch operator intake CSV, then rerun the listed commands",
        "claim_boundary": CLAIM_BOUNDARY,
    }
    return {
        "summary": summary,
        "rows": rows,
        "candidate_rows": candidate_rows,
        "rerun_commands": RERUN_COMMANDS,
    }


def _packet_row(payload: dict[str, Any]) -> dict[str, Any]:
    summary = payload["summary"]
    return {column: summary.get(column, "") for column in ROW_COLUMNS}


def _write_batch_folder(args: argparse.Namespace, payload: dict[str, Any]) -> None:
    root = _resolve(args.out_dir)
    root.mkdir(parents=True, exist_ok=True)
    _write_csv(root / "operator_fill_intake_batch.csv", payload["rows"], FIELD_COLUMNS)
    _write_csv(root / "candidate_summary.csv", payload["candidate_rows"], SUMMARY_COLUMNS)
    _write_json(
        root / "batch_manifest.json",
        {
            "summary": payload["summary"],
            "claim_boundary": CLAIM_BOUNDARY,
            "rerun_commands": payload["rerun_commands"],
            "candidate_rows": payload["candidate_rows"],
        },
    )
    (root / "RERUN_COMMANDS.md").write_text(
        "\n".join(["# Rerun Commands", "", *[f"- `{command}`" for command in payload["rerun_commands"]], ""]),
        encoding="utf-8",
    )
    rows_by_candidate: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in payload["rows"]:
        rows_by_candidate[row["candidate_id"]].append(row)
    folder_by_candidate = {row["candidate_id"]: row["candidate_folder"] for row in payload["candidate_rows"]}
    for candidate_id, rows in rows_by_candidate.items():
        folder = _resolve(folder_by_candidate.get(candidate_id, ""))
        folder.mkdir(parents=True, exist_ok=True)
        _write_csv(folder / "operator_fill_rows.csv", rows, FIELD_COLUMNS)
        first = next((row for row in rows if row["fill_status"] != READY_STATUS), rows[0] if rows else {})
        lines = [
            f"# {candidate_id} Batch Operator Fill",
            "",
            f"- target: `{first.get('target_id', '') or '-'}`",
            f"- ligand: `{first.get('ligand_id', '') or '-'}`",
            f"- fields ready/blocked/total: `{sum(1 for row in rows if row['fill_status'] == READY_STATUS)}/{sum(1 for row in rows if row['fill_status'] != READY_STATUS)}/{len(rows)}`",
            f"- first field: `{first.get('field_key', '') or '-'}` `{first.get('first_blocker', '') or '-'}`",
            "",
            "## Fields",
            "",
            "| field | status | source template | evidence stub |",
            "| --- | --- | --- | --- |",
        ]
        for row in rows:
            lines.append(
                f"| `{row['field_key']}` | `{row['fill_status']}` | "
                f"`{row['source_operator_template_csv'] or '-'}` | `{row['source_evidence_stub_md'] or '-'}` |"
            )
        lines.extend(["", "## Claim Boundary", "", CLAIM_BOUNDARY, ""])
        (folder / "README.md").write_text("\n".join(lines), encoding="utf-8")


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Organic Ligand Metric Batch Operator Fill Kit",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- status: `{summary['organic_ligand_metric_batch_operator_fill_kit_status']}`",
        f"- worklist: `{summary['worklist_status'] or '-'}`",
        f"- candidates ready/blocked/total: `{summary['ready_candidate_count']}/{summary['blocked_candidate_count']}/{summary['candidate_count']}`",
        f"- fields ready/blocked/total: `{summary['field_ready_count']}/{summary['field_blocked_count']}/{summary['field_count']}`",
        f"- missing value/evidence/clearance/operator: `{summary['operator_value_missing_count']}/{summary['operator_evidence_ref_missing_count']}/{summary['operator_clearance_missing_count']}/{summary['operator_id_missing_count']}`",
        f"- sources template/stub/action: `{summary['source_template_count']}/{summary['source_stub_count']}/{summary['linked_action_count']}`",
        f"- first: `{summary['first_candidate_id'] or '-'}` `{summary['first_field_key'] or '-'}` `{summary['first_blocker'] or '-'}`",
        "",
        "## Kit Files",
        "",
        f"- batch intake: `{summary['operator_fill_intake_batch_csv']}`",
        f"- candidate summary: `{summary['candidate_summary_csv']}`",
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
    parser = argparse.ArgumentParser(description="Build CASP17 organic ligand metric batch operator fill kit.")
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

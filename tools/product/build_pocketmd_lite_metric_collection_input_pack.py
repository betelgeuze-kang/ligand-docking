#!/usr/bin/env python3
"""Build the PocketMD Lite metric collection input pack.

Read-only: this joins the remaining evidence queue with the recovery manifest
so the next local-min/H-bond/clash-relief collector has one concrete input CSV.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]

DEFAULT_QUEUE_JSON = "runs/pocketmd_lite_remaining_evidence_queue_current.json"
DEFAULT_RECOVERY_JSON = "runs/pocketmd_lite_evidence_recovery_manifest_current.json"
DEFAULT_OUT_JSON = "runs/pocketmd_lite_metric_collection_input_pack_current.json"
DEFAULT_OUT_MD = "runs/pocketmd_lite_metric_collection_input_pack_current.md"
DEFAULT_OUT_CSV = "runs/pocketmd_lite_metric_collection_input_pack_current.csv"

PACKET_TYPE = "pocketmd_lite_metric_collection_input_pack"
SCHEMA_VERSION = "pocketmd_lite_metric_collection_input_pack_v1"

CLAIM_BOUNDARY = (
    "PocketMD Lite metric collection input pack only; it selects local trajectory/protein/ligand-smiles inputs for "
    "claim-grade local-min, H-bond, and clash-relief metric collection. It does not run local-min, compute "
    "H-bonds, copy restore candidates, promote claims, or mutate external state."
)

_READ_ONLY_FLAGS = {
    "execution_enabled": False,
    "external_state_mutated": False,
    "refinement_execution_enabled": False,
    "claim_promotion_allowed": False,
}

_CSV_COLUMNS = [
    "entry_id",
    "target",
    "ligand_id",
    "required_collection_metrics",
    "selected_trajectory_npz",
    "selected_trajectory_source",
    "selected_trajectory_readable",
    "selected_trajectory_claim_grade_metric_fields_present",
    "protein_structure_source_path",
    "protein_structure_source_path_available",
    "ligand_smiles",
    "ligand_smiles_present",
    "collection_input_ready",
    "claim_grade_metrics_already_present",
    "recommended_next_local_action",
    "blockers",
    "execution_enabled",
    "external_state_mutated",
    "refinement_execution_enabled",
    "claim_promotion_allowed",
]


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _display(path_like: str | Path) -> str:
    text = _text(path_like)
    if not text:
        return ""
    path = Path(text)
    if path.is_absolute():
        try:
            return str(path.relative_to(ROOT))
        except ValueError:
            return str(path)
    return text


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _read_json(path_like: str | Path) -> dict[str, Any]:
    path = _resolve(path_like)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _by_entry(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        _text(row.get("entry_id")): row
        for row in payload.get("rows", []) or []
        if isinstance(row, dict) and _text(row.get("entry_id"))
    }


def _first_path(value: Any) -> str:
    return next((part for part in _text(value).split(";") if part), "")


def _select_trajectory(queue_row: dict[str, Any], recovery_row: dict[str, Any]) -> tuple[str, str, bool, bool]:
    exact_status = _text(recovery_row.get("exact_npz_status"))
    if exact_status and exact_status != "missing":
        return (
            _text(recovery_row.get("trajectory_npz")),
            "exact_current",
            exact_status not in {"missing", "unreadable", "not_requested"},
            bool(recovery_row.get("exact_npz_claim_grade_metric_source_ready") is True),
        )
    restore = _first_path(recovery_row.get("exact_basename_restore_npz_paths"))
    if restore:
        return (
            restore,
            "exact_basename_restore_candidate",
            int(recovery_row.get("exact_basename_restore_readable_count") or 0) > 0,
            int(recovery_row.get("exact_basename_restore_claim_grade_metric_field_count") or 0) > 0,
        )
    alternate = _first_path(queue_row.get("alternate_trajectory_npz_candidates"))
    if alternate:
        return (
            alternate,
            "alternate_same_basename_candidate",
            int(queue_row.get("alternate_trajectory_npz_candidate_count") or 0) > 0,
            False,
        )
    return (_text(queue_row.get("trajectory_npz")), "missing_exact_current", False, False)


def _row_action(row: dict[str, Any]) -> str:
    if row["claim_grade_metrics_already_present"]:
        return "extract_existing_claim_grade_metrics_into_candidate_csv"
    if row["collection_input_ready"]:
        return "run_pocketmd_lite_local_min_hbond_clash_relief_collector_for_selected_input"
    return "restore_or_regenerate_missing_collection_inputs"


def build_pocketmd_lite_metric_collection_input_pack(
    *,
    queue_json: str | Path = DEFAULT_QUEUE_JSON,
    recovery_json: str | Path = DEFAULT_RECOVERY_JSON,
) -> dict[str, Any]:
    queue_path = _resolve(queue_json)
    recovery_path = _resolve(recovery_json)
    queue = _read_json(queue_path)
    recovery = _read_json(recovery_path)
    recovery_rows = _by_entry(recovery)
    rows: list[dict[str, Any]] = []
    for queue_row in queue.get("rows", []) or []:
        if not isinstance(queue_row, dict) or not _text(queue_row.get("missing_metrics")):
            continue
        entry_id = _text(queue_row.get("entry_id"))
        recovery_row = recovery_rows.get(entry_id, {})
        selected_npz, source, readable, metric_fields_present = _select_trajectory(queue_row, recovery_row)
        protein_ok = bool(queue_row.get("protein_structure_source_path_available") is True)
        ligand_ok = bool(queue_row.get("ligand_smiles_present") is True)
        collection_ready = bool(selected_npz and readable and protein_ok and ligand_ok)
        blockers: list[str] = []
        if not selected_npz or not readable:
            blockers.append("selected_trajectory_npz_unavailable")
        if not protein_ok:
            blockers.append("protein_structure_source_path_unavailable")
        if not ligand_ok:
            blockers.append("ligand_smiles_missing")
        row = {
            "entry_id": entry_id,
            "target": _text(queue_row.get("target")),
            "ligand_id": _text(queue_row.get("ligand_id")),
            "required_collection_metrics": _text(queue_row.get("missing_metrics")),
            "selected_trajectory_npz": _display(selected_npz),
            "selected_trajectory_source": source,
            "selected_trajectory_readable": readable,
            "selected_trajectory_claim_grade_metric_fields_present": metric_fields_present,
            "protein_structure_source_path": _display(queue_row.get("protein_structure_source_path")),
            "protein_structure_source_path_available": protein_ok,
            "ligand_smiles": _text(queue_row.get("ligand_smiles")),
            "ligand_smiles_present": ligand_ok,
            "collection_input_ready": collection_ready,
            "claim_grade_metrics_already_present": metric_fields_present,
            "blockers": blockers,
            **_READ_ONLY_FLAGS,
        }
        row["recommended_next_local_action"] = _row_action(row)
        rows.append(row)

    ready_count = sum(1 for row in rows if row["collection_input_ready"])
    existing_metric_count = sum(1 for row in rows if row["claim_grade_metrics_already_present"])
    status = (
        "pocketmd_lite_metric_collection_input_pack_ready"
        if rows and ready_count == len(rows)
        else "blocked_pocketmd_lite_metric_collection_input_pack"
    )
    summary = {
        "packet_type": PACKET_TYPE,
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "collection_input_pack_ready": status == "pocketmd_lite_metric_collection_input_pack_ready",
        "queue_json": _display(queue_path),
        "recovery_json": _display(recovery_path),
        "candidate_count": len(rows),
        "collection_input_ready_count": ready_count,
        "claim_grade_metric_field_candidate_count": existing_metric_count,
        "selected_exact_basename_restore_count": sum(
            1 for row in rows if row["selected_trajectory_source"] == "exact_basename_restore_candidate"
        ),
        "next_required_step": (
            "Run the PocketMD Lite local-min/H-bond/clash-relief collector over this input CSV, then fill candidate metrics and rerun the report."
            if ready_count == len(rows) and rows
            else "Restore or regenerate missing collection inputs, then rebuild this input pack."
        ),
        "claim_boundary": CLAIM_BOUNDARY,
        **_READ_ONLY_FLAGS,
    }
    return {
        "packet_type": PACKET_TYPE,
        "schema_version": SCHEMA_VERSION,
        "summary": summary,
        "rows": rows,
        "claim_boundary": CLAIM_BOUNDARY,
    }


def _fmt(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, list):
        return ";".join(str(item) for item in value)
    return str(value)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=_CSV_COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow({column: _fmt(row.get(column)) for column in _CSV_COLUMNS})


def _render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# PocketMD Lite Metric Collection Input Pack",
        "",
        f"- status: `{summary['status']}`",
        f"- collection_input_ready_count: `{summary['collection_input_ready_count']}` / `{summary['candidate_count']}`",
        f"- selected_exact_basename_restore_count: `{summary['selected_exact_basename_restore_count']}`",
        f"- claim_grade_metric_field_candidate_count: `{summary['claim_grade_metric_field_candidate_count']}`",
        "",
        "| entry | input ready | trajectory source | metrics | action |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            "| `{entry}` | `{ready}` | `{source}` | `{metrics}` | `{action}` |".format(
                entry=row["entry_id"],
                ready=str(row["collection_input_ready"]).lower(),
                source=row["selected_trajectory_source"],
                metrics=row["required_collection_metrics"],
                action=row["recommended_next_local_action"],
            )
        )
    lines.extend(["", "## Claim Boundary", "", CLAIM_BOUNDARY, ""])
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build the PocketMD Lite metric collection input pack.")
    parser.add_argument("--queue-json", default=DEFAULT_QUEUE_JSON)
    parser.add_argument("--recovery-json", default=DEFAULT_RECOVERY_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    args = parser.parse_args(argv)

    payload = build_pocketmd_lite_metric_collection_input_pack(
        queue_json=args.queue_json,
        recovery_json=args.recovery_json,
    )
    out_json = _resolve(args.out_json)
    out_md = _resolve(args.out_md)
    out_csv = _resolve(args.out_csv)
    _write_json(out_json, payload)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text(_render_markdown(payload), encoding="utf-8")
    _write_csv(out_csv, payload["rows"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]
RUNS = Path("runs")

DEFAULT_HANDOFF_JSON = RUNS / "residual_force_gpu_worker_handoff_package_current.json"
DEFAULT_MANIFEST_TEMPLATE_CSV = RUNS / "residual_force_gpu_worker_return_manifest_template_current.csv"
DEFAULT_SUMMARY_TEMPLATE_JSON = RUNS / "residual_force_trajectory_regeneration_current_summary_template.json"
DEFAULT_QUEUE_CSV = RUNS / "residual_force_trajectory_regeneration_queue_current.csv"
DEFAULT_OUT_JSON = RUNS / "residual_force_gpu_worker_preflight_checklist_current.json"
DEFAULT_OUT_CSV = RUNS / "residual_force_gpu_worker_preflight_checklist_current.csv"
DEFAULT_OUT_MD = RUNS / "residual_force_gpu_worker_preflight_checklist_current.md"

MANIFEST_OK_STATUS_VALUES = ("ok", "ok_npz_bundle", "ok_regenerated_npz", "ok_full_regeneration")
MANIFEST_FAILED_STATUS_VALUES = ("failed", "error", "missing", "aborted", "skipped")
OPERATOR_VERIFICATION_TRUTHY = ("true", "yes", "1", "ok", "verified")
OPERATOR_VERIFICATION_FALSEY = ("false", "no", "0", "missing", "failed", "not_found")

MANIFEST_COLUMN_GUIDE: list[dict[str, str]] = [
    {
        "column_name": "status",
        "required": "yes",
        "operator_fill": "ok | ok_npz_bundle | ok_regenerated_npz | ok_full_regeneration | failed | error | missing | aborted | skipped",
        "acceptance": "768 rows must use an ok_* status; zero failed/missing/placeholder rows",
        "notes": "Replace OPERATOR_FILL_OK_OR_FAILED with final worker status per row",
    },
    {
        "column_name": "queue_id",
        "required": "yes",
        "operator_fill": "do not edit",
        "acceptance": "must match template identity exactly for all 768 rows",
        "notes": "Primary queue identity key; receipt validates coverage",
    },
    {
        "column_name": "source_queue_id",
        "required": "yes",
        "operator_fill": "do not edit",
        "acceptance": "must equal queue_id unless handoff documents alias mapping",
        "notes": "Identity lock column from prefilled template",
    },
    {
        "column_name": "regeneration_queue_id",
        "required": "yes",
        "operator_fill": "do not edit",
        "acceptance": "must equal queue_id for identity-locked return manifest",
        "notes": "Used by return receipt queue manifest identity coverage",
    },
    {
        "column_name": "expected_regenerated_trajectory_npz",
        "required": "yes",
        "operator_fill": "do not edit",
        "acceptance": "must match full regeneration out-root path plan",
        "notes": "Expected NPZ destination under runs/residual_force_trajectory_regeneration_current/",
    },
    {
        "column_name": "queue_row_fingerprint",
        "required": "yes",
        "operator_fill": "do not edit",
        "acceptance": "sha256 fingerprint must match prepared queue row",
        "notes": "Tamper detection for returned manifest rows",
    },
    {
        "column_name": "generated_npz",
        "required": "yes",
        "operator_fill": "path written by worker OR same as expected when ok",
        "acceptance": "file must exist on worker before return; local receipt checks existence after transfer",
        "notes": "Primary NPZ path column for operator verification",
    },
    {
        "column_name": "target",
        "required": "yes",
        "operator_fill": "do not edit",
        "acceptance": "matches queue CSV target column",
        "notes": "Diagnostic only; do not mutate",
    },
    {
        "column_name": "ligand_id",
        "required": "yes",
        "operator_fill": "do not edit",
        "acceptance": "matches queue CSV ligand_id column",
        "notes": "Diagnostic only; do not mutate",
    },
    {
        "column_name": "replica_idx",
        "required": "no",
        "operator_fill": "do not edit",
        "acceptance": "matches queue CSV when present",
        "notes": "Optional replica index",
    },
    {
        "column_name": "simulation_seed",
        "required": "no",
        "operator_fill": "do not edit",
        "acceptance": "matches queue CSV when present",
        "notes": "Optional seed",
    },
    {
        "column_name": "native_pdb_path",
        "required": "yes",
        "operator_fill": "do not edit",
        "acceptance": "native PDB must exist on worker before run",
        "notes": "Preflight: verify data/native/*.pdb present",
    },
    {
        "column_name": "failure_reason",
        "required": "conditional",
        "operator_fill": "empty for ok rows; concise error for failed rows",
        "acceptance": "empty when status is ok_*",
        "notes": "Required when status is failed/error/missing/aborted/skipped",
    },
    {
        "column_name": "operator_verified_npz_exists",
        "required": "yes",
        "operator_fill": "true | false",
        "acceptance": "true for every ok row after ls/stat on generated_npz",
        "notes": "Replace OPERATOR_FILL_TRUE_OR_FALSE; receipt counts truthy values",
    },
    {
        "column_name": "operator_notes",
        "required": "no",
        "operator_fill": "free text",
        "acceptance": "optional worker notes; include run id or shard if useful",
        "notes": "Not validated by receipt beyond presence",
    },
]

SUMMARY_FIELD_GUIDE: list[dict[str, str]] = [
    {
        "column_name": "queue_rows",
        "required": "yes",
        "operator_fill": "768",
        "acceptance": "must equal prepared queue row count",
        "notes": "From runs/residual_force_trajectory_regeneration_queue_current.csv",
    },
    {
        "column_name": "processed_rows",
        "required": "yes",
        "operator_fill": ">=768",
        "acceptance": "processed_rows >= queue_rows",
        "notes": "Worker fill after full regeneration",
    },
    {
        "column_name": "ok_rows",
        "required": "yes",
        "operator_fill": "768",
        "acceptance": "ok_rows >= queue_rows; failed_rows=0",
        "notes": "All jobs must succeed for production promotion",
    },
    {
        "column_name": "failed_rows",
        "required": "yes",
        "operator_fill": "0",
        "acceptance": "must be exactly 0 for receipt pass",
        "notes": "Any non-zero value blocks gpu_worker_return_receipt_ready",
    },
    {
        "column_name": "aborted_early",
        "required": "yes",
        "operator_fill": "false",
        "acceptance": "must be false",
        "notes": "Early abort blocks promotion ladder",
    },
    {
        "column_name": "out_manifest_csv",
        "required": "yes",
        "operator_fill": "runs/residual_force_trajectory_regeneration_current_manifest.csv",
        "acceptance": "must bind to returned manifest path",
        "notes": "Receipt checks summary/manifest path binding",
    },
    {
        "column_name": "out_summary_json",
        "required": "yes",
        "operator_fill": "runs/residual_force_trajectory_regeneration_current_summary.json",
        "acceptance": "must bind to this summary file",
        "notes": "Write from summary template skeleton",
    },
    {
        "column_name": "backend_counts.rust_hip_rollout",
        "required": "yes",
        "operator_fill": "768 or worker-reported ok count",
        "acceptance": "production path must show rust_hip backend, not cpu fallback",
        "notes": "CPU/pytorch markers block production promotion",
    },
]

PREFLIGHT_STEPS: list[dict[str, str]] = [
    {
        "step_id": "rocm_visible",
        "phase": "worker_preflight",
        "command": "python3 tools/build_rocm_environment_manifest.py",
        "acceptance": "manifest_ready=true; visible_device_count>0; torch_rocm_ready=true",
    },
    {
        "step_id": "tiny_pilot",
        "phase": "worker_execution",
        "command": "see handoff run_tiny_npz_pilot step",
        "acceptance": "pilot ok_rows>=1; aborted_early=false",
    },
    {
        "step_id": "full_regeneration",
        "phase": "worker_execution",
        "command": "see handoff run_full_regeneration_queue step",
        "acceptance": "summary ok_rows=768; failed_rows=0",
    },
    {
        "step_id": "manifest_return",
        "phase": "return_bundle",
        "command": "fill manifest template CSV; verify every generated_npz exists",
        "acceptance": "768 ok rows; operator_verified_npz_exists=true for each ok row",
    },
    {
        "step_id": "local_receipt",
        "phase": "local_acceptance",
        "command": "python3 tools/build_residual_force_gpu_worker_return_receipt.py",
        "acceptance": "gpu_worker_return_receipt_ready=true",
    },
]

CLAIM_BOUNDARY = (
    "Residual force GPU worker preflight checklist only; documents manifest/summary column rules "
    "and worker preflight steps. It does not run GPU jobs or mutate external state."
)


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _read_json(path_like: str | Path) -> dict[str, Any]:
    path = _resolve(path_like)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _text(value: Any) -> str:
    return str(value or "").strip()


def _csv_row_count(path_like: str | Path) -> int:
    path = _resolve(path_like)
    if not path.exists():
        return 0
    try:
        with path.open("r", encoding="utf-8", newline="") as fh:
            return max(sum(1 for _ in fh) - 1, 0)
    except OSError:
        return 0


def _manifest_columns(path_like: str | Path) -> list[str]:
    path = _resolve(path_like)
    if not path.exists():
        return []
    try:
        with path.open("r", encoding="utf-8", newline="") as fh:
            reader = csv.reader(fh)
            header = next(reader, [])
            return [col.strip() for col in header if col.strip()]
    except OSError:
        return []


def build_payload(
    *,
    handoff_packet: dict[str, Any],
    manifest_template_csv: str,
    summary_template_json: str,
    queue_csv: str,
) -> dict[str, Any]:
    handoff_summary = handoff_packet.get("summary") if isinstance(handoff_packet.get("summary"), dict) else {}
    manifest_columns = _manifest_columns(manifest_template_csv)
    queue_rows = _csv_row_count(queue_csv)
    template_rows = _csv_row_count(manifest_template_csv)
    column_guide = [dict(row) for row in MANIFEST_COLUMN_GUIDE]
    for column in manifest_columns:
        if not any(row["column_name"] == column for row in column_guide):
            column_guide.append(
                {
                    "column_name": column,
                    "required": "unknown",
                    "operator_fill": "see handoff package",
                    "acceptance": "preserve template identity columns",
                    "notes": "Extra column detected in manifest template",
                }
            )
    checklist_rows = column_guide + [{**row, "artifact": "summary_json"} for row in SUMMARY_FIELD_GUIDE]
    for step in PREFLIGHT_STEPS:
        if step["step_id"] == "full_regeneration":
            step = dict(step)
            step["command"] = _text(handoff_summary.get("full_regeneration_command")) or step["command"]
        if step["step_id"] == "tiny_pilot":
            for row in handoff_packet.get("rows", []) or []:
                if isinstance(row, dict) and _text(row.get("step_id")) == "run_tiny_npz_pilot":
                    step = dict(step)
                    step["command"] = _text(row.get("command"))
                    break
    schema_ready = bool(manifest_columns) and template_rows == queue_rows and queue_rows > 0
    summary = {
        "packet_type": "residual_force_gpu_worker_preflight_checklist",
        "status": (
            "residual_force_gpu_worker_preflight_checklist_ready"
            if schema_ready
            else "blocked_residual_force_gpu_worker_preflight_checklist"
        ),
        "claim_boundary": CLAIM_BOUNDARY,
        "queue_row_count": queue_rows,
        "manifest_template_row_count": template_rows,
        "manifest_template_column_count": len(manifest_columns),
        "manifest_template_columns": manifest_columns,
        "manifest_ok_status_values": list(MANIFEST_OK_STATUS_VALUES),
        "manifest_failed_status_values": list(MANIFEST_FAILED_STATUS_VALUES),
        "operator_verification_truthy_values": list(OPERATOR_VERIFICATION_TRUTHY),
        "handoff_json": str(DEFAULT_HANDOFF_JSON),
        "manifest_template_csv": manifest_template_csv,
        "summary_template_json": summary_template_json,
        "queue_csv": queue_csv,
        "full_regeneration_command": _text(handoff_summary.get("full_regeneration_command")),
        "next_required_step": (
            "Run worker preflight steps, fill manifest columns per guide, return summary+manifest, "
            "then python3 tools/build_residual_force_gpu_worker_return_receipt.py."
            if schema_ready
            else "Regenerate GPU handoff package and manifest template before using preflight checklist."
        ),
    }
    return {
        "summary": summary,
        "manifest_column_guide": column_guide,
        "summary_field_guide": SUMMARY_FIELD_GUIDE,
        "preflight_steps": PREFLIGHT_STEPS,
        "checklist_rows": checklist_rows,
    }


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# Residual Force GPU Worker Preflight Checklist",
        "",
        f"- status: `{summary['status']}`",
        f"- queue_row_count: `{summary['queue_row_count']}`",
        f"- manifest_template_row_count: `{summary['manifest_template_row_count']}`",
        "",
        "## Manifest Column Guide",
        "",
        "| column | required | operator_fill | acceptance |",
        "| --- | --- | --- | --- |",
    ]
    for row in payload["manifest_column_guide"]:
        lines.append(
            f"| `{row['column_name']}` | {row['required']} | {row['operator_fill']} | {row['acceptance']} |"
        )
    lines.extend(
        [
            "",
            "## Summary JSON Fields",
            "",
            "| field | required | operator_fill | acceptance |",
            "| --- | --- | --- | --- |",
        ]
    )
    for row in payload["summary_field_guide"]:
        lines.append(
            f"| `{row['column_name']}` | {row['required']} | {row['operator_fill']} | {row['acceptance']} |"
        )
    lines.extend(
        [
            "",
            "## Preflight Steps",
            "",
            "| step_id | phase | command | acceptance |",
            "| --- | --- | --- | --- |",
        ]
    )
    for row in payload["preflight_steps"]:
        cmd = row["command"].replace("|", "\\|")
        lines.append(f"| `{row['step_id']}` | {row['phase']} | `{cmd}` | {row['acceptance']} |")
    lines.extend(["", "## Next Step", "", f"- {summary['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build GPU worker preflight checklist with manifest column guide.")
    parser.add_argument("--handoff-json", default=str(DEFAULT_HANDOFF_JSON))
    parser.add_argument("--manifest-template-csv", default=str(DEFAULT_MANIFEST_TEMPLATE_CSV))
    parser.add_argument("--summary-template-json", default=str(DEFAULT_SUMMARY_TEMPLATE_JSON))
    parser.add_argument("--queue-csv", default=str(DEFAULT_QUEUE_CSV))
    parser.add_argument("--out-json", default=str(DEFAULT_OUT_JSON))
    parser.add_argument("--out-csv", default=str(DEFAULT_OUT_CSV))
    parser.add_argument("--out-md", default=str(DEFAULT_OUT_MD))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        handoff_packet=_read_json(args.handoff_json),
        manifest_template_csv=args.manifest_template_csv,
        summary_template_json=args.summary_template_json,
        queue_csv=args.queue_csv,
    )
    _write_json(args.out_json, payload)
    write_csv_rows(_resolve(args.out_csv), payload["checklist_rows"])
    _write_markdown(_resolve(args.out_md), payload)
    print(json.dumps(payload["summary"], indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

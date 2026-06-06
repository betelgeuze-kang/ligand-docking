#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REGENERATION_QUEUE_JSON = "runs/residual_force_trajectory_regeneration_queue_current.json"
DEFAULT_OUT_JSON = "runs/residual_force_gpu_worker_return_summary_template_current.json"
DEFAULT_OUT_CSV = "runs/residual_force_gpu_worker_return_summary_template_current.csv"
DEFAULT_OUT_MD = "runs/residual_force_gpu_worker_return_summary_template_current.md"
DEFAULT_OUT_TEMPLATE_PAYLOAD_JSON = "runs/residual_force_trajectory_regeneration_current_summary_template.json"
DEFAULT_ACTUAL_SUMMARY_RETURN_PATH = "runs/residual_force_trajectory_regeneration_current_summary.json"
DEFAULT_ACTUAL_MANIFEST_RETURN_PATH = "runs/residual_force_trajectory_regeneration_current_manifest.csv"

REQUIRED_SUMMARY_FIELDS = (
    "queue_rows",
    "processed_rows",
    "ok_rows",
    "failed_rows",
    "aborted_early",
    "out_manifest_csv",
    "out_summary_json",
    "prod_mode",
    "require_rust_hip",
    "backend_counts",
)
REQUIRED_BACKEND_PROVENANCE_FIELDS = (
    "prod_mode",
    "require_rust_hip",
    "backend_counts",
)

CLAIM_BOUNDARY = (
    "Residual force GPU worker return summary template only; defines the required completion fields and acceptance "
    "rules for an operator-returned full-regeneration summary JSON. It does not run docking, regenerate trajectories, "
    "derive force labels, train models, create checkpoints, promote production mode, upload, submit, email, delete, "
    "or mutate external state."
)


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _read_json_if_present(path_like: str | Path) -> dict[str, Any]:
    path = _resolve(path_like)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _summary(packet: dict[str, Any]) -> dict[str, Any]:
    summary = packet.get("summary")
    if isinstance(summary, dict):
        return summary
    return packet if isinstance(packet, dict) else {}


def _rows(packet: dict[str, Any]) -> list[dict[str, Any]]:
    rows = packet.get("rows")
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def _int(value: Any) -> int:
    try:
        return int(float(str(value).strip()))
    except (TypeError, ValueError):
        return 0


def _text(value: Any) -> str:
    return str(value or "").strip()


def _queue_row_count(packet: dict[str, Any]) -> int:
    summary = _summary(packet)
    for key in ("queue_rows", "queue_row_count", "expected_queue_rows"):
        count = _int(summary.get(key))
        if count > 0:
            return count
    return len(_rows(packet))


def _field_row(
    field: str,
    expected_queue_rows: int,
    actual_manifest_return_path: str,
    actual_summary_return_path: str,
) -> dict[str, Any]:
    requirements = {
        "queue_rows": f"must equal prepared queue row count {expected_queue_rows}",
        "processed_rows": f"must be >= prepared queue row count {expected_queue_rows}",
        "ok_rows": f"must be >= prepared queue row count {expected_queue_rows}",
        "failed_rows": "must equal 0",
        "aborted_early": "must be false",
        "out_manifest_csv": "must point to the completed manifest CSV returned with this summary",
        "out_summary_json": "must point to the completed summary JSON returned to this receipt",
        "prod_mode": "must be true for production GPU-return acceptance",
        "require_rust_hip": "must be true so CPU diagnostic/fallback runs cannot satisfy production force-label evidence",
        "backend_counts": f"must count production GPU backend rows, with rust_hip* rows >= {expected_queue_rows} and CPU/fallback rows = 0",
    }
    placeholders = {
        "queue_rows": expected_queue_rows,
        "processed_rows": "GPU_WORKER_FILL_PROCESSED_ROWS",
        "ok_rows": "GPU_WORKER_FILL_OK_ROWS",
        "failed_rows": "GPU_WORKER_FILL_FAILED_ROWS",
        "aborted_early": "GPU_WORKER_FILL_FALSE",
        "out_manifest_csv": actual_manifest_return_path,
        "out_summary_json": actual_summary_return_path,
        "prod_mode": True,
        "require_rust_hip": True,
        "backend_counts": {"rust_hip_rollout": "GPU_WORKER_FILL_OK_ROWS"},
    }
    return {
        "field": field,
        "required": requirements[field],
        "template_value": placeholders[field],
        "operator_action_required": field != "queue_rows",
        "execution_enabled": False,
        "external_state_mutated": False,
    }


def build_residual_force_gpu_worker_return_summary_template(
    *,
    regeneration_queue_packet: dict[str, Any],
    regeneration_queue_path: str = DEFAULT_REGENERATION_QUEUE_JSON,
    actual_summary_return_path: str = DEFAULT_ACTUAL_SUMMARY_RETURN_PATH,
    actual_manifest_return_path: str = DEFAULT_ACTUAL_MANIFEST_RETURN_PATH,
) -> dict[str, Any]:
    queue = _summary(regeneration_queue_packet)
    queue_ready = queue.get("regeneration_queue_execution_ready") is True
    expected_queue_rows = _queue_row_count(regeneration_queue_packet)
    template_payload = {
        "queue_rows": expected_queue_rows,
        "processed_rows": "GPU_WORKER_FILL_PROCESSED_ROWS",
        "ok_rows": "GPU_WORKER_FILL_OK_ROWS",
        "failed_rows": "GPU_WORKER_FILL_FAILED_ROWS",
        "aborted_early": False,
        "out_manifest_csv": actual_manifest_return_path,
        "out_summary_json": actual_summary_return_path,
        "prod_mode": True,
        "require_rust_hip": True,
        "backend_counts": {"rust_hip_rollout": "GPU_WORKER_FILL_OK_ROWS"},
        "operator_notes": "GPU_WORKER_FILL_RUN_NOTES",
    }
    template_ready = bool(queue_ready and expected_queue_rows > 0)
    blockers: list[str] = []
    if not queue_ready:
        blockers.append("regeneration_queue_execution_ready")
    if expected_queue_rows <= 0:
        blockers.append("expected_queue_rows")

    rows = [
        _field_row(field, expected_queue_rows, actual_manifest_return_path, actual_summary_return_path)
        for field in REQUIRED_SUMMARY_FIELDS
    ]
    summary = {
        "packet_type": "residual_force_gpu_worker_return_summary_template",
        "status": (
            "residual_force_gpu_worker_return_summary_template_ready"
            if template_ready
            else "blocked_residual_force_gpu_worker_return_summary_template"
        ),
        "return_summary_template_ready": template_ready,
        "blocker_count": len(blockers),
        "blockers": blockers,
        "regeneration_queue_artifact": regeneration_queue_path,
        "expected_queue_rows": expected_queue_rows,
        "required_summary_fields": list(REQUIRED_SUMMARY_FIELDS),
        "required_backend_provenance_fields": list(REQUIRED_BACKEND_PROVENANCE_FIELDS),
        "required_completion_rule": (
            "queue_rows equals expected_queue_rows; processed_rows>=expected_queue_rows; "
            "ok_rows>=expected_queue_rows; failed_rows=0; aborted_early=false; "
            "out_manifest_csv points to the returned manifest CSV; "
            "out_summary_json points to the returned summary JSON"
        ),
        "backend_provenance_completion_rule": (
            "prod_mode=true; require_rust_hip=true; backend_counts has rust_hip* rows >= expected_queue_rows "
            "and no CPU/PyTorch fallback rows"
        ),
        "backend_provenance_template_ready": True,
        "actual_summary_return_path": actual_summary_return_path,
        "actual_manifest_return_path": actual_manifest_return_path,
        "template_payload_json": DEFAULT_OUT_TEMPLATE_PAYLOAD_JSON,
        "template_payload": template_payload,
        "template_field_count": len(REQUIRED_SUMMARY_FIELDS),
        "execution_enabled": False,
        "full_regeneration_executed": False,
        "force_labels_created": False,
        "training_executed": False,
        "checkpoint_created": False,
        "model_promoted": False,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "Use this template as the GPU worker's summary contract and return the actual summary JSON after the full run."
            if template_ready
            else "Repair the regeneration queue before creating a full-regeneration summary return template."
        ),
    }
    return {"summary": summary, "rows": rows}


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_template_payload_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    template_payload = _summary(payload).get("template_payload")
    output = template_payload if isinstance(template_payload, dict) else {}
    path.write_text(json.dumps(output, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    s = payload["summary"]
    lines = [
        "# Residual Force GPU Worker Return Summary Template",
        "",
        f"- status: `{s['status']}`",
        f"- return_summary_template_ready: `{s['return_summary_template_ready']}`",
        f"- expected_queue_rows: `{s['expected_queue_rows']}`",
        f"- actual_summary_return_path: `{s['actual_summary_return_path']}`",
        f"- actual_manifest_return_path: `{s['actual_manifest_return_path']}`",
        f"- template_payload_json: `{s['template_payload_json']}`",
        f"- required_completion_rule: `{s['required_completion_rule']}`",
        f"- backend_provenance_completion_rule: `{s['backend_provenance_completion_rule']}`",
        f"- blockers: `{','.join(s['blockers'])}`",
        "",
        "## Required Fields",
        "",
        "| field | required | template value |",
        "| --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(f"| `{row['field']}` | `{row['required']}` | `{row['template_value']}` |")
    lines.extend(
        [
            "",
            "## Template Payload",
            "",
            "```json",
            json.dumps(s["template_payload"], indent=2, ensure_ascii=False, sort_keys=True),
            "```",
            "",
            "## Claim Boundary",
            "",
            s["claim_boundary"],
            "",
            "## Next Step",
            "",
            f"- {s['next_required_step']}",
            "",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build residual force GPU worker return summary template.")
    parser.add_argument("--regeneration-queue-json", default=DEFAULT_REGENERATION_QUEUE_JSON)
    parser.add_argument("--actual-summary-return-path", default=DEFAULT_ACTUAL_SUMMARY_RETURN_PATH)
    parser.add_argument("--actual-manifest-return-path", default=DEFAULT_ACTUAL_MANIFEST_RETURN_PATH)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    parser.add_argument("--out-template-payload-json", default=DEFAULT_OUT_TEMPLATE_PAYLOAD_JSON)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_residual_force_gpu_worker_return_summary_template(
        regeneration_queue_packet=_read_json_if_present(args.regeneration_queue_json),
        regeneration_queue_path=args.regeneration_queue_json,
        actual_summary_return_path=args.actual_summary_return_path,
        actual_manifest_return_path=args.actual_manifest_return_path,
    )
    _write_json(args.out_json, payload)
    write_csv_rows(_resolve(args.out_csv), payload["rows"])
    _write_template_payload_json(args.out_template_payload_json, payload)
    _write_md(args.out_md, payload)


if __name__ == "__main__":
    main()

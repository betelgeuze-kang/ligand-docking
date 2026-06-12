#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT_JSON = "runs/product_operator_parallel_refresh_chain_current.json"
DEFAULT_OUT_MD = "runs/product_operator_parallel_refresh_chain_current.md"

REFRESH_STEPS = [
    ("aqp1_live_supplement_blank", "tools/build_aqp1_direct_binding_live_supplement_blank.py"),
    ("aqp1_operator_worksheet", "tools/build_aqp1_direct_binding_external_evidence_operator_worksheet.py"),
    ("transporter_negative_control_worksheet", "tools/build_transporter_negative_control_operator_worksheet.py"),
    ("gpu_worker_preflight_checklist", "tools/build_residual_force_gpu_worker_preflight_checklist.py"),
    ("rocm_environment_manifest", "tools/build_rocm_environment_manifest.py"),
    ("residual_force_execution_probe", "tools/build_residual_force_trajectory_regeneration_execution_probe.py"),
    ("scope_optional_lane_refresh", "tools/product/build_product_scope_optional_lane_refresh_chain.py"),
]

STEP_ARTIFACTS = {
    "aqp1_live_supplement_blank": "runs/aqp1_direct_binding_live_supplement_blank_current.json",
    "transporter_negative_control_worksheet": "runs/transporter_negative_control_operator_worksheet_current.json",
    "gpu_worker_preflight_checklist": "runs/residual_force_gpu_worker_preflight_checklist_current.json",
}


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


def _run_step(step_id: str, command: str) -> dict[str, Any]:
    proc = subprocess.run([sys.executable, command], cwd=ROOT, capture_output=True, text=True)
    artifact = STEP_ARTIFACTS.get(step_id, "")
    artifact_payload = _read_json(artifact) if artifact else {}
    summary = artifact_payload.get("summary", {}) if isinstance(artifact_payload.get("summary"), dict) else {}
    return {
        "step_id": step_id,
        "command": command,
        "returncode": proc.returncode,
        "ok": proc.returncode == 0,
        "artifact": artifact,
        "artifact_status": summary.get("status", ""),
        "stdout_tail": "\n".join(proc.stdout.splitlines()[-5:]),
        "stderr_tail": "\n".join(proc.stderr.splitlines()[-5:]),
    }


def build_payload(*, execute: bool) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for step_id, command in REFRESH_STEPS:
        if execute:
            rows.append(_run_step(step_id, command))
        else:
            rows.append({"step_id": step_id, "command": command, "execution_enabled": False})
    aqp1 = _read_json(STEP_ARTIFACTS["aqp1_live_supplement_blank"])
    neg = _read_json(STEP_ARTIFACTS["transporter_negative_control_worksheet"])
    gpu = _read_json(STEP_ARTIFACTS["gpu_worker_preflight_checklist"])
    full_summary = _read_json("runs/residual_force_trajectory_regeneration_current_summary.json")
    aqp1_summary = aqp1.get("summary", {}) if isinstance(aqp1.get("summary"), dict) else {}
    neg_summary = neg.get("summary", {}) if isinstance(neg.get("summary"), dict) else {}
    gpu_summary = gpu.get("summary", {}) if isinstance(gpu.get("summary"), dict) else {}
    full_ok_rows = int((full_summary.get("ok_rows") or 0))
    ready = all(row.get("ok", row.get("execution_enabled") is False) for row in rows if execute)
    summary = {
        "packet_type": "product_operator_parallel_refresh_chain",
        "status": "product_operator_parallel_refresh_chain_ready" if ready else "blocked_product_operator_parallel_refresh_chain",
        "generated_at": dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).isoformat(),
        "execution_enabled": execute,
        "step_count": len(rows),
        "aqp1_blank_pending_field_count": aqp1_summary.get("operator_fill_pending_field_count"),
        "negative_control_pending_field_count": neg_summary.get("operator_fill_pending_field_count"),
        "gpu_preflight_queue_rows": gpu_summary.get("queue_row_count"),
        "gpu_full_regeneration_ok_rows": full_ok_rows,
        "operator_evidence_blocker": "exact_direct_binding_and_negative_quantitative_values_require_primary_source_review",
        "next_required_step": (
            "Complete operator CSV fills (AQP1 direct Kd/Ki + 6 negative kcal with primary sources), then rerun "
            "tools/product/build_aqp1_direct_binding_external_evidence_one_shot_chain.py and "
            "tools/product/build_product_scope_optional_lane_refresh_chain.py."
            if full_ok_rows >= 768
            else (
                "Complete operator CSV fills (AQP1 direct Kd/Ki + 6 negative kcal), wait for gpu full regeneration, "
                "then run tools/build_product_gpu_return_post_regeneration_chain.py --execute."
            )
        ),
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# Product Operator Parallel Refresh Chain",
        "",
        f"- status: `{summary['status']}`",
        f"- aqp1_blank_pending_field_count: `{summary.get('aqp1_blank_pending_field_count')}`",
        f"- negative_control_pending_field_count: `{summary.get('negative_control_pending_field_count')}`",
        f"- gpu_full_regeneration_ok_rows: `{summary.get('gpu_full_regeneration_ok_rows')}`",
        "",
        "## Steps",
        "",
    ]
    for row in payload["rows"]:
        lines.append(f"- `{row['step_id']}`: ok={row.get('ok', 'dry-run')}")
    lines.extend(["", "## Next Step", "", f"- {summary['next_required_step']}", ""])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run operator artifact refresh steps in parallel prep chain.")
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    parser.add_argument("--execute", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(execute=bool(args.execute))
    _write_json(args.out_json, payload)
    _write_markdown(_resolve(args.out_md), payload)
    print(json.dumps(payload["summary"], indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

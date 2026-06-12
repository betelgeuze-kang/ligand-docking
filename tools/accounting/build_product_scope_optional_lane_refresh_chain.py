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
DEFAULT_OUT_JSON = "runs/product_scope_optional_lane_refresh_chain_current.json"
DEFAULT_OUT_MD = "runs/product_scope_optional_lane_refresh_chain_current.md"

REFRESH_STEPS = [
    ("transporter_manual_review_intake_template", "tools/build_transporter_manual_review_intake_template.py"),
    ("product_scope_breadth_closure_checklist", "tools/build_product_scope_breadth_closure_checklist.py"),
    ("transporter_aqp1_external_evidence_refresh_chain", "tools/product/build_transporter_aqp1_external_evidence_refresh_chain.py"),
    ("product_scope_breadth_contract", "tools/build_product_scope_breadth_contract.py"),
    ("product_ai_architecture_gap_closure", "tools/build_product_ai_architecture_gap_closure.py"),
    ("product_ai_architecture_execution_backlog", "tools/build_product_ai_architecture_execution_backlog.py"),
    ("product_goal_completion_audit", "tools/build_product_goal_completion_audit.py"),
]

CLAIM_BOUNDARY = (
    "Product scope optional-lane refresh chain only; it rebuilds transporter manual review, scope breadth, "
    "AQP1 evidence, AI backlog, and goal audit artifacts for deferred scope promotion work. It does not fabricate "
    "claim-safe evidence, authoritatively apply rows, run docking, upload, or mutate external state."
)


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else (ROOT / path).resolve()


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
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _run(cmd: list[str]) -> None:
    subprocess.run(cmd, cwd=str(ROOT), check=True)


def build_packet(*, generated_at_local: str | None = None) -> dict[str, Any]:
    lanes: dict[str, dict[str, Any]] = {}
    blockers: list[str] = []
    for lane, script in REFRESH_STEPS:
        _run([sys.executable, script])
        artifact = f"runs/{lane}_current.json"
        if lane == "transporter_aqp1_external_evidence_refresh_chain":
            artifact = "runs/transporter_aqp1_external_evidence_refresh_chain_current.json"
        elif lane == "product_goal_completion_audit":
            artifact = "runs/product_goal_completion_audit_current.json"
        payload = _read_json(artifact)
        summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else payload
        lanes[lane] = {
            "lane": lane,
            "status": str(summary.get("status") or "").strip(),
            "artifact": str(_resolve(artifact)),
            "summary": summary,
        }
        for item in summary.get("blockers") or []:
            blockers.append(f"{lane}:{item}")

    audit = lanes.get("product_goal_completion_audit", {}).get("summary", {})
    backlog = lanes.get("product_ai_architecture_execution_backlog", {}).get("summary", {})
    status = (
        "product_scope_optional_lane_refresh_chain_ready"
        if not blockers and _bool(audit.get("product_ai_optional_lane_ready"))
        else "product_scope_optional_lane_refresh_chain_refreshed_with_blockers"
    )
    summary = {
        "packet_type": "product_scope_optional_lane_refresh_chain",
        "status": status,
        "generated_at_local": generated_at_local or dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "claim_boundary": CLAIM_BOUNDARY,
        "blockers": blockers,
        "product_ai_optional_lane_ready": _bool(audit.get("product_ai_optional_lane_ready")),
        "product_ai_scope_deferred_work_item_count": int(backlog.get("scope_deferred_work_item_count") or 0),
        "goal_complete": _bool(audit.get("goal_complete")),
        "next_required_step": (
            "Optional scope lane refreshed; continue operator evidence curation for deferred transporter/general-platform items."
            if blockers or not _bool(audit.get("product_ai_optional_lane_ready"))
            else "Optional scope lane and goal audit are aligned; no deferred-scope blockers remain."
        ),
    }
    return {"summary": summary, "lanes": lanes}


def _bool(value: Any) -> bool:
    return bool(value is True)


def _write_markdown(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    summary = payload["summary"]
    lines = [
        "# Product Scope Optional Lane Refresh Chain",
        "",
        f"- status: `{summary['status']}`",
        f"- product_ai_optional_lane_ready: `{summary['product_ai_optional_lane_ready']}`",
        f"- scope_deferred_work_item_count: `{summary['product_ai_scope_deferred_work_item_count']}`",
        f"- goal_complete: `{summary['goal_complete']}`",
        "",
        summary["claim_boundary"],
        "",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Refresh deferred scope optional lane artifacts.")
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_packet()
    _write_json(args.out_json, payload)
    _write_markdown(args.out_md, payload)
    print(json.dumps(payload["summary"], indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

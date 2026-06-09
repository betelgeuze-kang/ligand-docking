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
DEFAULT_OUT_JSON = "runs/goal_product_status_refresh_chain_current.json"
DEFAULT_OUT_MD = "runs/goal_product_status_refresh_chain_current.md"

REFRESH_STEPS = [
    ("product_release_operations_dossier", "tools/build_product_release_operations_dossier.py"),
    ("product_architecture_contract", "tools/build_product_architecture_contract.py"),
    ("product_ai_architecture_execution_backlog", "tools/build_product_ai_architecture_execution_backlog.py"),
    ("goal_readiness_rollup", "tools/build_goal_readiness_rollup.py"),
    ("goal_operator_action_board", "tools/build_goal_operator_action_board.py"),
    ("goal_release_decision_gate", "tools/build_goal_release_decision_gate.py"),
    ("product_goal_completion_audit", "tools/build_product_goal_completion_audit.py"),
]

ARTIFACTS = {
    "product_release_operations_dossier": "runs/product_release_operations_dossier_current.json",
    "product_architecture_contract": "runs/product_architecture_contract_current.json",
    "product_ai_architecture_execution_backlog": "runs/product_ai_architecture_execution_backlog_current.json",
    "goal_readiness_rollup": "runs/goal_readiness_rollup_current.json",
    "goal_operator_action_board": "runs/goal_operator_action_board_current.json",
    "goal_release_decision_gate": "runs/goal_release_decision_gate_current.json",
    "product_goal_completion_audit": "runs/product_goal_completion_audit_current.json",
}

CLAIM_BOUNDARY = (
    "Goal product status refresh chain only; it rebuilds local product operations, architecture, AI backlog, "
    "goal rollup, release gate, and completion audit artifacts from existing evidence. It does not run docking, "
    "delete data, submit CAMEO predictions, send email, upload, commit, push, or mutate external state."
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


def _lane(name: str, path_like: str | Path) -> dict[str, Any]:
    payload = _read_json(path_like)
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else payload
    return {
        "lane": name,
        "status": str(summary.get("status") or "").strip(),
        "artifact": str(_resolve(path_like)),
        "summary": summary,
    }


def build_packet(*, generated_at_local: str | None = None) -> dict[str, Any]:
    from betelgeuze_product.cli import build_all_status as build_product_cli_all_status

    lanes: dict[str, dict[str, Any]] = {}
    for lane_id, script in REFRESH_STEPS:
        _run([sys.executable, script])
        lanes[lane_id] = _lane(lane_id, ARTIFACTS[lane_id])

    product_cli = build_product_cli_all_status(root=ROOT)
    rollup = lanes["goal_readiness_rollup"]["summary"]
    release_gate = lanes["goal_release_decision_gate"]["summary"]
    operations = lanes["product_release_operations_dossier"]["summary"]

    blockers: list[str] = []
    if not bool(product_cli.get("core_product_cli_status_set_ready") is True):
        blockers.append("goal_refresh:core_product_cli_status_set_not_ready")
    if str(rollup.get("status") or "").startswith("blocked_"):
        blockers.append("goal_refresh:goal_readiness_rollup_blocked")
    if not bool(release_gate.get("release_allowed") is True):
        blockers.append("goal_refresh:goal_release_decision_not_allowed")

    status = (
        "goal_product_status_refresh_chain_ready"
        if not blockers
        else "goal_product_status_refresh_chain_refreshed_with_blockers"
    )

    summary = {
        "packet_type": "goal_product_status_refresh_chain",
        "status": status,
        "generated_at_local": generated_at_local or dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "claim_boundary": CLAIM_BOUNDARY,
        "blockers": blockers,
        "product_cli_status_set_status": str(product_cli.get("status") or ""),
        "core_product_cli_status_set_ready": bool(product_cli.get("core_product_cli_status_set_ready") is True),
        "product_cli_delivery_ready_claim_allowed": bool(product_cli.get("delivery_ready_claim_allowed") is True),
        "product_cli_bundle_validation_passed": bool(product_cli.get("bundle_validation_passed") is True),
        "product_cli_pilot_delivery_ready": bool(product_cli.get("pilot_delivery_ready") is True),
        "goal_readiness_rollup_status": str(rollup.get("status") or ""),
        "goal_release_decision_gate_status": str(release_gate.get("status") or ""),
        "goal_release_allowed": bool(release_gate.get("release_allowed") is True),
        "operations_blocked_stage_count": int(operations.get("blocked_stage_count") or 0),
        "next_required_step": (
            "Product CLI, goal rollup, and release gate refreshed from current local delivery evidence."
            if not blockers
            else "Refresh completed; resolve remaining optional or scope-deferred blockers without threshold relaxation."
        ),
    }
    return {"summary": summary, "lanes": lanes}


def _write_markdown(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    summary = payload["summary"]
    lines = [
        "# Goal Product Status Refresh Chain",
        "",
        f"- status: `{summary['status']}`",
        f"- core_product_cli_status_set_ready: `{summary['core_product_cli_status_set_ready']}`",
        f"- goal_readiness_rollup_status: `{summary['goal_readiness_rollup_status']}`",
        f"- goal_release_allowed: `{summary['goal_release_allowed']}`",
        f"- blockers: `{';'.join(summary.get('blockers') or []) or 'none'}`",
        "",
        "## Lanes",
        "",
    ]
    for lane_id, lane in payload.get("lanes", {}).items():
        lines.append(f"- {lane_id}: `{lane.get('status')}`")
    lines.extend(["", "## Claim Boundary", "", summary["claim_boundary"], "", "## Next Step", "", f"- {summary['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Refresh product CLI, goal rollup, and release gate artifacts.")
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

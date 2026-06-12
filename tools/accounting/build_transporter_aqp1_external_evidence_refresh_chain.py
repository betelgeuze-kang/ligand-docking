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
DEFAULT_OUT_JSON = "runs/transporter_aqp1_external_evidence_refresh_chain_current.json"
DEFAULT_OUT_MD = "runs/transporter_aqp1_external_evidence_refresh_chain_current.md"

REFRESH_STEPS = [
    ("aqp1_external_evidence_operator_fill_guide", "tools/build_aqp1_direct_binding_external_evidence_operator_fill_guide.py"),
    ("aqp1_external_evidence_supplement_example", "tools/build_aqp1_direct_binding_external_evidence_supplement_example.py"),
    ("aqp1_external_evidence_intake", "tools/build_aqp1_direct_binding_external_evidence_intake.py"),
    ("aqp1_external_evidence_operator_worksheet", "tools/build_aqp1_direct_binding_external_evidence_operator_worksheet.py"),
    ("aqp1_ready_workbook_apply", "tools/apply_aqp1_ready_workbook_rows.py"),
    ("transporter_p0_closure_packet", "tools/build_transporter_p0_closure_packet.py"),
    ("transporter_blocker_capture_sheet", "tools/product/build_transporter_blocker_capture_sheet.py"),
    ("transporter_binder_promotion_gate", "tools/build_transporter_binder_promotion_gate.py"),
    ("transporter_donor_policy_reopen_checklist", "tools/product/build_transporter_donor_policy_reopen_checklist.py"),
    ("product_scope_breadth_contract", "tools/build_product_scope_breadth_contract.py"),
    ("product_ai_architecture_execution_backlog", "tools/build_product_ai_architecture_execution_backlog.py"),
]

ARTIFACTS = {
    "aqp1_external_evidence_supplement_example": "runs/aqp1_direct_binding_external_evidence_supplement_example_current.json",
    "aqp1_external_evidence_intake": "runs/aqp1_direct_binding_external_evidence_intake_current.json",
    "aqp1_external_evidence_operator_worksheet": "runs/aqp1_direct_binding_external_evidence_operator_worksheet_current.json",
    "aqp1_external_evidence_operator_fill_guide": "runs/aqp1_direct_binding_external_evidence_operator_fill_guide_current.json",
    "aqp1_ready_workbook_apply": "runs/aqp1_ready_workbook_apply_current.json",
    "transporter_p0_closure_packet": "runs/transporter_p0_closure_packet_current.json",
    "transporter_blocker_capture_sheet": "runs/transporter_blocker_capture_sheet_current.json",
    "transporter_binder_promotion_gate": "runs/transporter_binder_promotion_gate_current.json",
    "transporter_donor_policy_reopen_checklist": "runs/transporter_donor_policy_reopen_checklist_current.json",
    "product_scope_breadth_contract": "runs/product_scope_breadth_contract_current.json",
    "product_ai_architecture_execution_backlog": "runs/product_ai_architecture_execution_backlog_current.json",
}

CLAIM_BOUNDARY = (
    "Transporter AQP1 external evidence refresh chain only; it rebuilds local AQP1 intake templates, "
    "workbook apply receipts, transporter P0 closure, scope breadth, and AI backlog artifacts. "
    "It does not fabricate claim-safe direct-binding kcal values, mutate external databases, run docking, "
    "delete data, upload, submit, email, or mutate external state."
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


def _claim_safe_approved_count(intake_summary: dict[str, Any]) -> int:
    return int(
        intake_summary.get("claim_safe_approved_count")
        or intake_summary.get("claim_safe_approved_row_count")
        or 0
    )


def build_packet(*, generated_at_local: str | None = None) -> dict[str, Any]:
    lanes: dict[str, dict[str, Any]] = {}
    for lane_id, script in REFRESH_STEPS:
        _run([sys.executable, script])
        lanes[lane_id] = _lane(lane_id, ARTIFACTS[lane_id])

    intake = lanes["aqp1_external_evidence_intake"]["summary"]
    p0 = lanes["transporter_p0_closure_packet"]["summary"]
    scope = lanes["product_scope_breadth_contract"]["summary"]
    backlog = lanes["product_ai_architecture_execution_backlog"]["summary"]

    blockers: list[str] = []
    claim_safe_approved_count = _claim_safe_approved_count(intake)
    if claim_safe_approved_count == 0:
        blockers.append("transporter_refresh:aqp1_claim_safe_external_evidence_pending")
    if int(p0.get("aqp1_core_p0_open_count") or 0) > 0:
        blockers.append("transporter_refresh:aqp1_core_p0_open")
    if str(scope.get("status") or "").startswith("blocked_"):
        blockers.append("transporter_refresh:product_scope_breadth_blocked")

    status = (
        "transporter_aqp1_external_evidence_refresh_chain_ready"
        if not blockers
        else "transporter_aqp1_external_evidence_refresh_chain_refreshed_with_blockers"
    )

    summary = {
        "packet_type": "transporter_aqp1_external_evidence_refresh_chain",
        "status": status,
        "generated_at_local": generated_at_local or dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "claim_boundary": CLAIM_BOUNDARY,
        "blockers": blockers,
        "aqp1_claim_safe_approved_count": claim_safe_approved_count,
        "aqp1_claim_safe_approved_row_count": claim_safe_approved_count,
        "aqp1_core_p0_open_count": int(p0.get("aqp1_core_p0_open_count") or 0),
        "scope_breadth_status": str(scope.get("status") or ""),
        "scope_deferred_work_item_count": int(backlog.get("scope_deferred_work_item_count") or 0),
        "release_blocking_work_item_count": int(backlog.get("release_blocking_work_item_count") or 0),
        "next_required_step": (
            "Fill AQP1 direct-binding external evidence intake with exact claim-safe kcal rows, rerun apply, "
            "then rerun this chain before transporter scope promotion."
            if blockers
            else "Transporter AQP1 evidence tooling and scope breadth artifacts refreshed."
        ),
    }
    return {"summary": summary, "lanes": lanes}


def _write_markdown(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    summary = payload["summary"]
    lines = [
        "# Transporter AQP1 External Evidence Refresh Chain",
        "",
        f"- status: `{summary['status']}`",
        f"- aqp1_claim_safe_approved_row_count: `{summary['aqp1_claim_safe_approved_row_count']}`",
        f"- aqp1_core_p0_open_count: `{summary['aqp1_core_p0_open_count']}`",
        f"- scope_breadth_status: `{summary['scope_breadth_status']}`",
        f"- blockers: `{';'.join(summary.get('blockers') or []) or 'none'}`",
        "",
        "## Claim Boundary",
        "",
        summary["claim_boundary"],
        "",
        "## Next Step",
        "",
        f"- {summary['next_required_step']}",
        "",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Refresh AQP1 transporter external evidence tooling artifacts.")
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

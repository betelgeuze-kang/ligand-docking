#!/usr/bin/env python3
"""Aggregate R8/R9 full-commercial evidence receipt blockers into one gate."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SCOPE_RECEIPT_JSON = "runs/product_scope_breadth_evidence_receipt_current.json"
DEFAULT_ENGINE_RECEIPT_JSON = "runs/engine_refinement_claim_evidence_receipt_current.json"
DEFAULT_GOAL_AUDIT_JSON = "runs/product_goal_completion_audit_current.json"
DEFAULT_BOTTLENECK_BRIEFING_JSON = "runs/goal_bottleneck_briefing_current.json"
DEFAULT_OUT_JSON = "runs/product_full_commercial_blocker_evidence_matrix_current.json"
DEFAULT_OUT_CSV = "runs/product_full_commercial_blocker_evidence_matrix_current.csv"
DEFAULT_OUT_MD = "runs/product_full_commercial_blocker_evidence_matrix_current.md"

EXPECTED_RELEASE_BLOCKER_IDS = [
    "R8_full_scope_claim_closure",
    "R9_engine_refinement_claim_promotion",
]

CLAIM_BOUNDARY = (
    "Product full-commercial blocker evidence matrix only; it aggregates existing local R8/R9 receipt "
    "artifacts into one operator acceptance surface. It does not fill evidence, approve tokens, run docking, "
    "run external tools, promote claims, upload, email, delete, commit, push, or mutate external state."
)


def _resolve(path_like: str | Path, *, root: Path = ROOT) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else root / path


def _read_json(path_like: str | Path, *, root: Path = ROOT) -> tuple[dict[str, Any], bool]:
    path = _resolve(path_like, root=root)
    if not path.is_file():
        return {}, False
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}, True
    return (payload if isinstance(payload, dict) else {}), True


def _write_json(path_like: str | Path, payload: dict[str, Any], *, root: Path = ROOT) -> None:
    path = _resolve(path_like, root=root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _summary(packet: dict[str, Any]) -> dict[str, Any]:
    summary = packet.get("summary")
    if isinstance(summary, dict):
        return summary
    if packet.get("status"):
        return packet
    return {}


def _rows(packet: dict[str, Any]) -> list[dict[str, Any]]:
    rows = packet.get("rows")
    return [dict(row) for row in (rows or []) if isinstance(row, dict)]


def _text(value: Any) -> str:
    return str(value or "").strip()


def _bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return _text(value).lower() in {"1", "true", "yes", "y"}


def _int(value: Any, default: int = 0) -> int:
    try:
        return int(float(_text(value)))
    except (TypeError, ValueError):
        return default


def _goal_release_blocker_ids(goal_audit_packet: dict[str, Any]) -> list[str]:
    ids: list[str] = []
    for row in _rows(goal_audit_packet):
        row_id = _text(row.get("requirement_id") or row.get("id") or row.get("check_id"))
        if row.get("release_blocker") is True and row_id:
            ids.append(row_id)
    return ids


def _bottleneck_ids(bottleneck_packet: dict[str, Any]) -> list[str]:
    ids: list[str] = []
    for row in _rows(bottleneck_packet):
        row_id = _text(row.get("bottleneck_id") or row.get("id"))
        if row_id:
            ids.append(row_id)
    return ids


def _receipt_matrix_rows(
    *,
    release_blocker_id: str,
    evidence_domain: str,
    receipt_json_path: str,
    receipt_packet: dict[str, Any],
    receipt_present: bool,
    blocker_id_key: str,
    receipt_ready_key: str,
    receipt_csv_key: str,
    approval_token: str,
    post_return_acceptance_artifact: str,
    next_required_step: str,
) -> list[dict[str, Any]]:
    summary = _summary(receipt_packet)
    receipt_rows = _rows(receipt_packet)
    if not receipt_rows:
        return [
            {
                "release_blocker_id": release_blocker_id,
                "evidence_domain": evidence_domain,
                "receipt_json": receipt_json_path,
                "receipt_present": receipt_present,
                "receipt_status": _text(summary.get("status")) or "missing",
                "receipt_ready_key": receipt_ready_key,
                "receipt_ready": bool(summary.get(receipt_ready_key) is True),
                "receipt_csv": _text(summary.get(receipt_csv_key)),
                "approval_token_required": approval_token,
                "evidence_row_id": "",
                "evidence_artifact": "",
                "evidence_artifact_present": False,
                "expected_evidence_status": "",
                "observed_evidence_status": "missing",
                "claim_ready": False,
                "row_status": "blocked",
                "row_blockers": "receipt_rows_missing",
                "post_return_acceptance_artifact": post_return_acceptance_artifact,
                "next_required_step": next_required_step,
                "external_state_mutated": False,
            }
        ]

    rows: list[dict[str, Any]] = []
    for row in receipt_rows:
        row_status = _text(row.get("row_status")) or "blocked"
        rows.append(
            {
                "release_blocker_id": release_blocker_id,
                "evidence_domain": evidence_domain,
                "receipt_json": receipt_json_path,
                "receipt_present": receipt_present,
                "receipt_status": _text(summary.get("status")) or "missing",
                "receipt_ready_key": receipt_ready_key,
                "receipt_ready": bool(summary.get(receipt_ready_key) is True),
                "receipt_csv": _text(summary.get(receipt_csv_key)),
                "approval_token_required": approval_token,
                "evidence_row_id": _text(row.get(blocker_id_key)),
                "evidence_artifact": _text(row.get("evidence_artifact")),
                "evidence_artifact_present": bool(row.get("evidence_artifact_present") is True),
                "expected_evidence_status": _text(row.get("expected_evidence_status")),
                "observed_evidence_status": _text(row.get("observed_evidence_status")) or "missing",
                "claim_ready": _bool(row.get("claim_ready")),
                "row_status": row_status,
                "row_blockers": _text(row.get("blockers")),
                "post_return_acceptance_artifact": post_return_acceptance_artifact,
                "next_required_step": next_required_step,
                "external_state_mutated": False,
            }
        )
    return rows


def build_product_full_commercial_blocker_evidence_matrix(
    *,
    scope_receipt_json: str | Path = DEFAULT_SCOPE_RECEIPT_JSON,
    engine_receipt_json: str | Path = DEFAULT_ENGINE_RECEIPT_JSON,
    goal_audit_json: str | Path = DEFAULT_GOAL_AUDIT_JSON,
    bottleneck_briefing_json: str | Path = DEFAULT_BOTTLENECK_BRIEFING_JSON,
    root: str | Path = ROOT,
) -> dict[str, Any]:
    root_path = Path(root)
    scope_packet, scope_present = _read_json(scope_receipt_json, root=root_path)
    engine_packet, engine_present = _read_json(engine_receipt_json, root=root_path)
    goal_packet, goal_present = _read_json(goal_audit_json, root=root_path)
    bottleneck_packet, bottleneck_present = _read_json(bottleneck_briefing_json, root=root_path)

    return build_product_full_commercial_blocker_evidence_matrix_from_packets(
        scope_packet=scope_packet,
        scope_present=scope_present,
        engine_packet=engine_packet,
        engine_present=engine_present,
        goal_packet=goal_packet,
        goal_present=goal_present,
        bottleneck_packet=bottleneck_packet,
        bottleneck_present=bottleneck_present,
        scope_receipt_json=scope_receipt_json,
        engine_receipt_json=engine_receipt_json,
        goal_audit_json=goal_audit_json,
        bottleneck_briefing_json=bottleneck_briefing_json,
    )


def build_product_full_commercial_blocker_evidence_matrix_from_packets(
    *,
    scope_packet: dict[str, Any],
    scope_present: bool,
    engine_packet: dict[str, Any],
    engine_present: bool,
    goal_packet: dict[str, Any],
    goal_present: bool,
    bottleneck_packet: dict[str, Any],
    bottleneck_present: bool,
    scope_receipt_json: str | Path = DEFAULT_SCOPE_RECEIPT_JSON,
    engine_receipt_json: str | Path = DEFAULT_ENGINE_RECEIPT_JSON,
    goal_audit_json: str | Path = DEFAULT_GOAL_AUDIT_JSON,
    bottleneck_briefing_json: str | Path = DEFAULT_BOTTLENECK_BRIEFING_JSON,
) -> dict[str, Any]:
    scope_summary = _summary(scope_packet)
    engine_summary = _summary(engine_packet)
    goal_summary = _summary(goal_packet)
    bottleneck_summary = _summary(bottleneck_packet)

    rows = []
    rows.extend(
        _receipt_matrix_rows(
            release_blocker_id="R8_full_scope_claim_closure",
            evidence_domain="full_commercial_scope",
            receipt_json_path=str(scope_receipt_json),
            receipt_packet=scope_packet,
            receipt_present=scope_present,
            blocker_id_key="scope_blocker_id",
            receipt_ready_key="full_scope_evidence_receipt_ready",
            receipt_csv_key="receipt_csv",
            approval_token=_text(scope_summary.get("approval_token_required"))
            or "APPROVE_PRODUCT_SCOPE_BREADTH_EVIDENCE_RECEIPT",
            post_return_acceptance_artifact=str(scope_receipt_json),
            next_required_step=_text(scope_summary.get("next_required_step")),
        )
    )
    rows.extend(
        _receipt_matrix_rows(
            release_blocker_id="R9_engine_refinement_claim_promotion",
            evidence_domain="full_commercial_science_claim",
            receipt_json_path=str(engine_receipt_json),
            receipt_packet=engine_packet,
            receipt_present=engine_present,
            blocker_id_key="blocker_id",
            receipt_ready_key="claim_promotion_evidence_receipt_ready",
            receipt_csv_key="receipt_csv",
            approval_token=_text(engine_summary.get("approval_token_required"))
            or "APPROVE_ENGINE_REFINEMENT_CLAIM_EVIDENCE_RECEIPT",
            post_return_acceptance_artifact=str(engine_receipt_json),
            next_required_step=_text(engine_summary.get("next_required_step")),
        )
    )

    goal_release_ids = _goal_release_blocker_ids(goal_packet)
    bottleneck_ids = _bottleneck_ids(bottleneck_packet)
    missing_goal_release_ids = [item for item in EXPECTED_RELEASE_BLOCKER_IDS if item not in goal_release_ids]
    missing_bottleneck_ids = [item for item in EXPECTED_RELEASE_BLOCKER_IDS if item not in bottleneck_ids]
    blocked_rows = [row for row in rows if row["row_status"] != "pass"]
    ready_receipts = [
        row["release_blocker_id"]
        for row in rows
        if row["receipt_ready"]
    ]
    ready_receipt_ids = sorted(set(ready_receipts))
    required_tokens = sorted({_text(row.get("approval_token_required")) for row in rows if _text(row.get("approval_token_required"))})

    blockers: list[str] = []
    if not scope_present:
        blockers.append("scope_receipt_missing")
    if not engine_present:
        blockers.append("engine_refinement_receipt_missing")
    if not goal_present:
        blockers.append("goal_completion_audit_missing")
    if not bottleneck_present:
        blockers.append("goal_bottleneck_briefing_missing")
    if missing_goal_release_ids:
        blockers.append("goal_audit_missing_expected_release_blockers:" + ",".join(missing_goal_release_ids))
    if missing_bottleneck_ids:
        blockers.append("bottleneck_briefing_missing_expected_release_blockers:" + ",".join(missing_bottleneck_ids))
    if blocked_rows:
        blockers.append("blocked_evidence_matrix_rows_present")
    if set(ready_receipt_ids) != set(EXPECTED_RELEASE_BLOCKER_IDS):
        blockers.append("full_commercial_receipts_not_ready")

    ready = not blockers
    first_blocked = blocked_rows[0] if blocked_rows else {}
    summary = {
        "packet_type": "product_full_commercial_blocker_evidence_matrix",
        "status": (
            "product_full_commercial_blocker_evidence_matrix_ready"
            if ready
            else "blocked_product_full_commercial_blocker_evidence_matrix"
        ),
        "full_commercial_blocker_evidence_matrix_ready": ready,
        "full_commercial_evidence_receipts_ready": set(ready_receipt_ids) == set(EXPECTED_RELEASE_BLOCKER_IDS),
        "expected_release_blocker_ids": list(EXPECTED_RELEASE_BLOCKER_IDS),
        "expected_release_blocker_count": len(EXPECTED_RELEASE_BLOCKER_IDS),
        "goal_audit_json": str(goal_audit_json),
        "goal_audit_present": goal_present,
        "goal_audit_status": _text(goal_summary.get("status")),
        "goal_complete": bool(goal_summary.get("goal_complete") is True),
        "goal_audit_release_blocker_ids": goal_release_ids,
        "missing_goal_audit_release_blocker_ids": missing_goal_release_ids,
        "bottleneck_briefing_json": str(bottleneck_briefing_json),
        "bottleneck_briefing_present": bottleneck_present,
        "bottleneck_briefing_status": _text(bottleneck_summary.get("status")),
        "bottleneck_release_blocker_ids": bottleneck_ids,
        "missing_bottleneck_release_blocker_ids": missing_bottleneck_ids,
        "release_blocker_visibility_ready": not missing_goal_release_ids and not missing_bottleneck_ids,
        "scope_receipt_json": str(scope_receipt_json),
        "scope_receipt_present": scope_present,
        "scope_receipt_status": _text(scope_summary.get("status")) or "missing",
        "scope_receipt_ready": bool(scope_summary.get("full_scope_evidence_receipt_ready") is True),
        "scope_receipt_blocked_row_count": _int(scope_summary.get("blocked_row_count")),
        "scope_receipt_first_blocked_scope_blocker_id": _text(
            scope_summary.get("first_blocked_scope_blocker_id")
        ),
        "scope_receipt_most_common_row_blocker": _text(scope_summary.get("most_common_row_blocker")),
        "engine_receipt_json": str(engine_receipt_json),
        "engine_receipt_present": engine_present,
        "engine_receipt_status": _text(engine_summary.get("status")) or "missing",
        "engine_receipt_ready": bool(engine_summary.get("claim_promotion_evidence_receipt_ready") is True),
        "engine_receipt_blocked_row_count": _int(engine_summary.get("blocked_row_count")),
        "engine_receipt_first_blocked_blocker_id": _text(engine_summary.get("first_blocked_blocker_id")),
        "engine_receipt_most_common_row_blocker": _text(engine_summary.get("most_common_row_blocker")),
        "matrix_row_count": len(rows),
        "pass_matrix_row_count": len(rows) - len(blocked_rows),
        "blocked_matrix_row_count": len(blocked_rows),
        "ready_receipt_count": len(ready_receipt_ids),
        "blocked_receipt_count": len(EXPECTED_RELEASE_BLOCKER_IDS) - len(ready_receipt_ids),
        "approval_token_count": len(required_tokens),
        "approval_tokens_required": required_tokens,
        "first_blocked_release_blocker_id": _text(first_blocked.get("release_blocker_id")),
        "first_blocked_evidence_row_id": _text(first_blocked.get("evidence_row_id")),
        "first_blocked_evidence_artifact": _text(first_blocked.get("evidence_artifact")),
        "first_blocked_expected_evidence_status": _text(first_blocked.get("expected_evidence_status")),
        "first_blocked_observed_evidence_status": _text(first_blocked.get("observed_evidence_status")),
        "first_blocked_row_blockers": _text(first_blocked.get("row_blockers")),
        "first_blocked_receipt_json": _text(first_blocked.get("receipt_json")),
        "first_blocked_acceptance_artifact": _text(first_blocked.get("post_return_acceptance_artifact")),
        "first_blocked_next_required_step": _text(first_blocked.get("next_required_step")),
        "blocker_count": len(blockers),
        "blockers": blockers,
        "claim_boundary": CLAIM_BOUNDARY,
        "execution_enabled": False,
        "external_state_mutated": False,
        "next_required_step": (
            "R8/R9 full-commercial evidence receipts are locally verified; rerun product goal completion, "
            "commercial handoff, release source-of-truth, and release decision gates."
            if ready
            else "Fill the R8/R9 receipt CSVs with reviewed local evidence artifacts and approval tokens, then rerun the two receipt gates and this matrix."
        ),
    }
    return {"summary": summary, "rows": rows, "blockers": blockers}


def _write_markdown(path_like: str | Path, payload: dict[str, Any], *, root: Path = ROOT) -> None:
    path = _resolve(path_like, root=root)
    summary = payload["summary"]
    lines = [
        "# Product Full Commercial Blocker Evidence Matrix",
        "",
        f"- status: `{summary['status']}`",
        f"- full_commercial_blocker_evidence_matrix_ready: `{summary['full_commercial_blocker_evidence_matrix_ready']}`",
        f"- release_blocker_visibility_ready: `{summary['release_blocker_visibility_ready']}`",
        f"- matrix rows pass/total: `{summary['pass_matrix_row_count']}/{summary['matrix_row_count']}`",
        f"- blocked_matrix_row_count: `{summary['blocked_matrix_row_count']}`",
        f"- first_blocked_release_blocker_id: `{summary['first_blocked_release_blocker_id']}`",
        f"- first_blocked_evidence_row_id: `{summary['first_blocked_evidence_row_id']}`",
        f"- first_blocked_row_blockers: `{summary['first_blocked_row_blockers']}`",
        f"- scope_receipt_most_common_row_blocker: `{summary['scope_receipt_most_common_row_blocker']}`",
        f"- engine_receipt_most_common_row_blocker: `{summary['engine_receipt_most_common_row_blocker']}`",
        f"- approval_tokens_required: `{';'.join(summary['approval_tokens_required'])}`",
        "",
        "## Blockers",
    ]
    lines.extend(f"- `{blocker}`" for blocker in summary["blockers"])
    if not summary["blockers"]:
        lines.append("- none")
    lines.extend(
        [
            "",
            "## Rows",
            "",
            "| release blocker | evidence row | status | observed evidence | blockers |",
            "| --- | --- | --- | --- | --- |",
        ]
    )
    for row in payload["rows"]:
        lines.append(
            f"| `{row['release_blocker_id']}` | `{row['evidence_row_id']}` | `{row['row_status']}` | "
            f"`{row['observed_evidence_status']}` | `{row['row_blockers']}` |"
        )
    lines.extend(["", "## Claim Boundary", "", summary["claim_boundary"], ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Build the product full-commercial blocker evidence matrix.")
    parser.add_argument("--scope-receipt-json", default=DEFAULT_SCOPE_RECEIPT_JSON)
    parser.add_argument("--engine-receipt-json", default=DEFAULT_ENGINE_RECEIPT_JSON)
    parser.add_argument("--goal-audit-json", default=DEFAULT_GOAL_AUDIT_JSON)
    parser.add_argument("--bottleneck-briefing-json", default=DEFAULT_BOTTLENECK_BRIEFING_JSON)
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    args = parser.parse_args(argv)
    root = Path(args.root)
    payload = build_product_full_commercial_blocker_evidence_matrix(
        scope_receipt_json=args.scope_receipt_json,
        engine_receipt_json=args.engine_receipt_json,
        goal_audit_json=args.goal_audit_json,
        bottleneck_briefing_json=args.bottleneck_briefing_json,
        root=root,
    )
    _write_json(args.out_json, payload, root=root)
    write_csv_rows(_resolve(args.out_csv, root=root), payload["rows"])
    _write_markdown(args.out_md, payload, root=root)
    print(json.dumps(payload["summary"], indent=2, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()

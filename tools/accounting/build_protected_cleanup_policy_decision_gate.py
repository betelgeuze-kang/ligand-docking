#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows
from tools.cleanup.build_protected_cleanup_payload_review import DEFAULT_OUT_JSON as DEFAULT_PROTECTED_REVIEW_JSON
from tools.build_protected_ligand_heavy_payload_deep_review import DEFAULT_OUT_JSON as DEFAULT_PROTECTED_LIGAND_HEAVY_DEEP_REVIEW_JSON

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OPERATOR_POLICY_CSV = "runs/protected_cleanup_policy_decision_intake.csv"
DEFAULT_TEMPLATE_CSV = "runs/protected_cleanup_policy_decision_template_current.csv"
DEFAULT_OUT_JSON = "runs/protected_cleanup_policy_decision_gate_current.json"
DEFAULT_OUT_CSV = "runs/protected_cleanup_policy_decision_gate_current.csv"
DEFAULT_OUT_MD = "runs/protected_cleanup_policy_decision_gate_current.md"

KEEP_DECISION = "keep_protected"
REQUEST_POLICY_CHANGE_DECISION = "request_policy_change"
DEFER_DECISION = "defer"
VALID_DECISIONS = {KEEP_DECISION, REQUEST_POLICY_CHANGE_DECISION, DEFER_DECISION}

CLAIM_BOUNDARY = (
    "Protected cleanup policy decision gate only; it validates operator policy decisions for protected cleanup rows. "
    "It does not promote protected rows to deletion approval, delete, move, archive, externalize, upload, commit, push, "
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


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _read_csv_rows(path_like: str | Path) -> list[dict[str, str]]:
    path = _resolve(path_like)
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _summary(packet: dict[str, Any]) -> dict[str, Any]:
    summary = packet.get("summary")
    return summary if isinstance(summary, dict) else {}


def _rows(packet: dict[str, Any]) -> list[dict[str, Any]]:
    return [row for row in packet.get("rows", []) or [] if isinstance(row, dict)]


def _text(value: Any) -> str:
    return str(value or "").strip()


def _float(value: Any) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _key(row: dict[str, Any]) -> str:
    return _text(row.get("path"))


def _deep_review_rows_by_protected_path(deep_review_packet: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    rows_by_path: dict[str, list[dict[str, Any]]] = {}
    for row in _rows(deep_review_packet):
        key = _text(row.get("protected_path"))
        if not key:
            continue
        rows_by_path.setdefault(key, []).append(row)
    return rows_by_path


def _deep_review_context(row: dict[str, Any], rows_by_path: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    child_rows = rows_by_path.get(_text(row.get("path")), [])
    payload_rows = [child for child in child_rows if _text(child.get("child_role")) == "known_payload_child"]
    sibling_rows = [child for child in child_rows if _text(child.get("child_role")) == "preservation_sibling"]
    return {
        "known_payload_child_count": len(payload_rows),
        "known_payload_child_size_gb": round(sum(_float(child.get("size_gb")) for child in payload_rows), 3),
        "preservation_sibling_count": len(sibling_rows),
        "largest_known_payload_child_size_gb": max((_float(child.get("size_gb")) for child in payload_rows), default=0.0),
    }


def _write_template(path_like: str | Path, protected_rows: list[dict[str, Any]], deep_review_packet: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    deep_rows_by_path = _deep_review_rows_by_protected_path(deep_review_packet)
    fieldnames = [
        "path",
        "known_payload_size_gb",
        "known_payload_child_count",
        "known_payload_child_size_gb",
        "preservation_sibling_count",
        "largest_known_payload_child_size_gb",
        "source_dry_run_status",
        "current_policy_action",
        "valid_operator_policy_decisions",
        "operator_policy_decision",
        "operator_note",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for row in protected_rows:
            context = _deep_review_context(row, deep_rows_by_path)
            writer.writerow(
                {
                    "path": _text(row.get("path")),
                    "known_payload_size_gb": _float(row.get("known_payload_size_gb")),
                    "known_payload_child_count": context["known_payload_child_count"],
                    "known_payload_child_size_gb": context["known_payload_child_size_gb"],
                    "preservation_sibling_count": context["preservation_sibling_count"],
                    "largest_known_payload_child_size_gb": context["largest_known_payload_child_size_gb"],
                    "source_dry_run_status": _text(row.get("source_dry_run_status")),
                    "current_policy_action": _text(row.get("current_policy_action")) or KEEP_DECISION,
                    "valid_operator_policy_decisions": "|".join(sorted(VALID_DECISIONS)),
                    "operator_policy_decision": "",
                    "operator_note": "",
                }
            )


def build_protected_cleanup_policy_decision_gate(
    *,
    protected_review_packet: dict[str, Any],
    operator_policy_rows: list[dict[str, Any]],
    protected_ligand_heavy_deep_review_packet: dict[str, Any] | None = None,
    protected_review_json: str = DEFAULT_PROTECTED_REVIEW_JSON,
    protected_ligand_heavy_deep_review_json: str = DEFAULT_PROTECTED_LIGAND_HEAVY_DEEP_REVIEW_JSON,
    operator_policy_csv: str = DEFAULT_OPERATOR_POLICY_CSV,
    template_csv: str = DEFAULT_TEMPLATE_CSV,
    operator_policy_csv_present: bool = True,
) -> dict[str, Any]:
    review = _summary(protected_review_packet)
    deep_review_packet = protected_ligand_heavy_deep_review_packet or {}
    deep_review = _summary(deep_review_packet)
    deep_rows_by_path = _deep_review_rows_by_protected_path(deep_review_packet)
    protected_rows = _rows(protected_review_packet)
    blockers: list[str] = []
    if review.get("status") != "protected_cleanup_payload_review_ready":
        blockers.append("protected_cleanup_payload_review_not_ready")
    if not operator_policy_csv_present:
        blockers.append("operator_policy_csv_missing")

    decisions_by_path: dict[str, dict[str, Any]] = {}
    duplicate_decision_count = 0
    for row in operator_policy_rows:
        key = _key(row)
        if key in decisions_by_path:
            duplicate_decision_count += 1
        decisions_by_path[key] = row
    if duplicate_decision_count:
        blockers.append("duplicate_operator_policy_rows")
    protected_keys = {_key(row) for row in protected_rows}
    unknown_decision_count = sum(1 for key in decisions_by_path if key not in protected_keys)
    if unknown_decision_count:
        blockers.append("operator_policy_row_not_in_protected_review")

    rows: list[dict[str, Any]] = []
    for protected_row in protected_rows:
        deep_context = _deep_review_context(protected_row, deep_rows_by_path)
        decision_row = decisions_by_path.get(_key(protected_row), {})
        decision = _text(decision_row.get("operator_policy_decision") or decision_row.get("operator_decision")).lower()
        row_blockers: list[str] = []
        if not decision_row:
            gate_status = "awaiting_operator_policy_decision"
            row_blockers.append("operator_policy_decision_missing")
        elif decision not in VALID_DECISIONS:
            gate_status = "blocked_invalid_policy_decision"
            row_blockers.append("operator_policy_decision_invalid")
        elif decision == KEEP_DECISION:
            gate_status = "resolved_keep_protected"
        elif decision == REQUEST_POLICY_CHANGE_DECISION:
            gate_status = "policy_change_requested"
        else:
            gate_status = "deferred_by_operator"

        if _text(decision_row.get("operator_approval_token") or decision_row.get("approval_token")):
            row_blockers.append("approval_token_not_allowed_for_policy_decision")
            gate_status = "blocked_approval_token_attempted"
        if row_blockers:
            blockers.extend(row_blockers)
        rows.append(
            {
                "path": _text(protected_row.get("path")),
                "surface_path": _text(protected_row.get("surface_path")),
                "source_dry_run_status": _text(protected_row.get("source_dry_run_status")),
                "source_dry_run_reason": _text(protected_row.get("source_dry_run_reason")),
                "known_payload_size_gb": round(_float(protected_row.get("known_payload_size_gb")), 3),
                "known_payload_child_count": deep_context["known_payload_child_count"],
                "known_payload_child_size_gb": deep_context["known_payload_child_size_gb"],
                "preservation_sibling_count": deep_context["preservation_sibling_count"],
                "largest_known_payload_child_size_gb": deep_context["largest_known_payload_child_size_gb"],
                "current_policy_action": _text(protected_row.get("current_policy_action")) or KEEP_DECISION,
                "operator_policy_decision": decision,
                "policy_gate_status": gate_status,
                "blockers": ",".join(row_blockers),
                "approval_promoted": False,
                "delete_enabled": False,
                "delete_executed": False,
                "external_state_mutated": False,
            }
        )

    awaiting_rows = [row for row in rows if row["policy_gate_status"] == "awaiting_operator_policy_decision"]
    keep_rows = [row for row in rows if row["policy_gate_status"] == "resolved_keep_protected"]
    requested_rows = [row for row in rows if row["policy_gate_status"] == "policy_change_requested"]
    deferred_rows = [row for row in rows if row["policy_gate_status"] == "deferred_by_operator"]
    blocked_rows = [row for row in rows if row["blockers"]]
    no_protected_rows_remaining = not protected_rows and not blockers
    policy_resolved = no_protected_rows_remaining or (bool(rows) and len(keep_rows) == len(rows) and not blockers)
    status = "protected_cleanup_policy_decision_gate_ready" if policy_resolved else "blocked_protected_cleanup_policy_decision_gate"
    summary = {
        "packet_type": "protected_cleanup_policy_decision_gate",
        "status": status,
        "source_protected_review_json": protected_review_json,
        "source_protected_review_status": _text(review.get("status")),
        "source_protected_ligand_heavy_deep_review_json": protected_ligand_heavy_deep_review_json,
        "protected_ligand_heavy_deep_review_status": _text(deep_review.get("status")),
        "known_payload_child_count": sum(int(row["known_payload_child_count"]) for row in rows),
        "known_payload_child_size_gb": round(sum(_float(row.get("known_payload_child_size_gb")) for row in rows), 3),
        "preservation_sibling_count": sum(int(row["preservation_sibling_count"]) for row in rows),
        "largest_known_payload_child_size_gb": max((_float(row.get("largest_known_payload_child_size_gb")) for row in rows), default=0.0),
        "policy_change_required_for_deletion_count": int(deep_review.get("policy_change_required_for_deletion_count") or 0),
        "operator_policy_csv": operator_policy_csv,
        "operator_policy_csv_present": bool(operator_policy_csv_present),
        "operator_template_csv": template_csv,
        "protected_payload_row_count": len(rows),
        "protected_payload_size_gb": round(sum(_float(row.get("known_payload_size_gb")) for row in rows), 3),
        "policy_resolved": policy_resolved,
        "resolved_keep_protected_row_count": len(keep_rows),
        "policy_change_requested_row_count": len(requested_rows),
        "deferred_row_count": len(deferred_rows),
        "awaiting_policy_decision_row_count": len(awaiting_rows),
        "blocked_row_count": len(blocked_rows),
        "unknown_operator_policy_row_count": unknown_decision_count,
        "duplicate_operator_policy_row_count": duplicate_decision_count,
        "blocker_count": len(blockers),
        "blockers": sorted(set(blockers)),
        "approval_promoted": False,
        "delete_enabled": False,
        "delete_executed": False,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "No protected cleanup payload rows remain after refresh."
            if no_protected_rows_remaining
            else "Protected cleanup policy is resolved by explicit keep decisions."
            if policy_resolved
            else f"Fill `{template_csv}` into `{operator_policy_csv}` with keep_protected, request_policy_change, or defer decisions."
        ),
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    s = payload["summary"]
    lines = [
        "# Protected Cleanup Policy Decision Gate",
        "",
        f"- status: `{s['status']}`",
        f"- protected_ligand_heavy_deep_review_status: `{s['protected_ligand_heavy_deep_review_status']}`",
        f"- operator_policy_csv_present: `{s['operator_policy_csv_present']}`",
        f"- protected_payload_row_count: `{s['protected_payload_row_count']}`",
        f"- protected_payload_size_gb: `{s['protected_payload_size_gb']}`",
        f"- known_payload_child_count: `{s['known_payload_child_count']}`",
        f"- known_payload_child_size_gb: `{s['known_payload_child_size_gb']}`",
        f"- preservation_sibling_count: `{s['preservation_sibling_count']}`",
        f"- policy_resolved: `{s['policy_resolved']}`",
        f"- resolved_keep_protected_row_count: `{s['resolved_keep_protected_row_count']}`",
        f"- policy_change_requested_row_count: `{s['policy_change_requested_row_count']}`",
        f"- awaiting_policy_decision_row_count: `{s['awaiting_policy_decision_row_count']}`",
        f"- blocked_row_count: `{s['blocked_row_count']}`",
        f"- delete_enabled: `{s['delete_enabled']}`",
        f"- delete_executed: `{s['delete_executed']}`",
        f"- external_state_mutated: `{s['external_state_mutated']}`",
        "",
        "## Rows",
        "",
        "| gate_status | decision | size_gb | child_payload_gb | child_count | siblings | dry_run_status | path | blockers |",
        "| --- | --- | ---: | ---: | ---: | ---: | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['policy_gate_status']}` | `{row['operator_policy_decision']}` | `{row['known_payload_size_gb']}` | "
            f"`{row['known_payload_child_size_gb']}` | `{row['known_payload_child_count']}` | "
            f"`{row['preservation_sibling_count']}` | `{row['source_dry_run_status']}` | `{row['path']}` | `{row['blockers']}` |"
        )
    lines.extend(["", "## Claim Boundary", "", s["claim_boundary"], "", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate protected cleanup policy decisions without promoting deletion.")
    parser.add_argument("--protected-review-json", default=DEFAULT_PROTECTED_REVIEW_JSON)
    parser.add_argument("--protected-ligand-heavy-deep-review-json", default=DEFAULT_PROTECTED_LIGAND_HEAVY_DEEP_REVIEW_JSON)
    parser.add_argument("--operator-policy-csv", default=DEFAULT_OPERATOR_POLICY_CSV)
    parser.add_argument("--template-csv", default=DEFAULT_TEMPLATE_CSV)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    protected_review = _read_json_if_present(args.protected_review_json)
    protected_ligand_heavy_deep_review = _read_json_if_present(args.protected_ligand_heavy_deep_review_json)
    operator_csv_path = _resolve(args.operator_policy_csv)
    payload = build_protected_cleanup_policy_decision_gate(
        protected_review_packet=protected_review,
        protected_ligand_heavy_deep_review_packet=protected_ligand_heavy_deep_review,
        operator_policy_rows=_read_csv_rows(args.operator_policy_csv),
        protected_review_json=args.protected_review_json,
        protected_ligand_heavy_deep_review_json=args.protected_ligand_heavy_deep_review_json,
        operator_policy_csv=args.operator_policy_csv,
        template_csv=args.template_csv,
        operator_policy_csv_present=operator_csv_path.exists(),
    )
    _write_template(args.template_csv, _rows(protected_review), protected_ligand_heavy_deep_review)
    _write_json(args.out_json, payload)
    write_csv_rows(_resolve(args.out_csv), payload["rows"])
    _write_markdown(args.out_md, payload)


if __name__ == "__main__":
    main()

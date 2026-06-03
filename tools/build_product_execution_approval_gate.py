#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

from betelgeuze_product.work_order import EXECUTION_APPROVAL_TOKEN
from tools.builder_table_utils import write_csv_rows
from tools.build_product_execution_preflight import DEFAULT_OUT_JSON as DEFAULT_PRODUCT_PREFLIGHT_JSON
from tools.build_product_execution_work_order import DEFAULT_OUT_JSON as DEFAULT_PRODUCT_WORK_ORDER_JSON

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OPERATOR_APPROVAL_CSV = "runs/product_execution_operator_approval_intake.csv"
DEFAULT_TEMPLATE_CSV = "runs/product_execution_operator_approval_template_current.csv"
DEFAULT_OUT_JSON = "runs/product_execution_approval_gate_current.json"
DEFAULT_OUT_CSV = "runs/product_execution_approval_gate_current.csv"
DEFAULT_OUT_MD = "runs/product_execution_approval_gate_current.md"

CLAIM_BOUNDARY = (
    "Product execution approval gate only; it validates operator approval-token intake against the product execution "
    "preflight and work order. It does not run docking, assemble bundles, emit scientific results, upload, commit, "
    "push, or mutate external state."
)

APPROVE_DECISION = "approve"
SKIP_DECISION = "skip"
VALID_DECISIONS = {APPROVE_DECISION, SKIP_DECISION}


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


def _summary(packet: dict[str, Any]) -> dict[str, Any]:
    summary = packet.get("summary")
    return summary if isinstance(summary, dict) else {}


def _rows(packet: dict[str, Any]) -> list[dict[str, Any]]:
    return [row for row in packet.get("rows", []) or [] if isinstance(row, dict)]


def _text(value: Any) -> str:
    return str(value or "").strip()


def _bool(value: Any) -> bool:
    return bool(value is True)


def _read_csv_rows(path_like: str | Path) -> list[dict[str, str]]:
    path = _resolve(path_like)
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _identity(row: dict[str, Any]) -> tuple[str, str, str]:
    return (_text(row.get("target_id")), _text(row.get("family")), _text(row.get("bundle_tag")))


def _approval_target(preflight: dict[str, Any], work_order: dict[str, Any]) -> dict[str, Any]:
    preflight_summary = _summary(preflight)
    work_summary = _summary(work_order)
    return {
        "target_id": _text(preflight_summary.get("target_id") or work_summary.get("target_id")),
        "family": _text(preflight_summary.get("family") or work_summary.get("family")),
        "bundle_tag": _text(work_summary.get("bundle_tag")),
        "approval_token_required": _text(preflight_summary.get("approval_token_required") or work_summary.get("approval_token_required")),
        "execution_command_present": bool(_text((work_order.get("commands") or {}).get("execution_command") if isinstance(work_order.get("commands"), dict) else "")),
        "bundle_command_present": bool((work_order.get("commands") or {}).get("bundle_command") if isinstance(work_order.get("commands"), dict) else False),
        "bundle_validation_command_present": bool(_text((work_order.get("commands") or {}).get("bundle_validation_command") if isinstance(work_order.get("commands"), dict) else "")),
    }


def _write_template(path_like: str | Path, target: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "target_id",
        "family",
        "bundle_tag",
        "approval_token_required",
        "operator_decision",
        "operator_approval_token",
        "operator_note",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerow(
            {
                "target_id": _text(target.get("target_id")),
                "family": _text(target.get("family")),
                "bundle_tag": _text(target.get("bundle_tag")),
                "approval_token_required": _text(target.get("approval_token_required")),
                "operator_decision": "",
                "operator_approval_token": "",
                "operator_note": "",
            }
        )


def build_product_execution_approval_gate(
    *,
    product_execution_preflight_packet: dict[str, Any],
    product_execution_work_order_packet: dict[str, Any],
    operator_approval_rows: list[dict[str, Any]],
    product_execution_preflight_json: str = DEFAULT_PRODUCT_PREFLIGHT_JSON,
    product_execution_work_order_json: str = DEFAULT_PRODUCT_WORK_ORDER_JSON,
    operator_approval_csv: str = DEFAULT_OPERATOR_APPROVAL_CSV,
    template_csv: str = DEFAULT_TEMPLATE_CSV,
    operator_approval_csv_present: bool = True,
) -> dict[str, Any]:
    preflight = _summary(product_execution_preflight_packet)
    work_order = _summary(product_execution_work_order_packet)
    target = _approval_target(product_execution_preflight_packet, product_execution_work_order_packet)
    blockers: list[str] = []
    if preflight.get("status") != "product_execution_preflight_ready":
        blockers.append("product_execution_preflight_not_ready")
    if work_order.get("status") != "product_execution_work_order_ready":
        blockers.append("product_execution_work_order_not_ready")
    if preflight.get("execution_enabled") is not False or work_order.get("execution_enabled") is not False:
        blockers.append("source_execution_flag_invalid")
    if preflight.get("docking_results_emitted") is not False or work_order.get("docking_results_emitted") is not False:
        blockers.append("source_results_flag_invalid")
    if preflight.get("external_state_mutated") is not False or work_order.get("external_state_mutated") is not False:
        blockers.append("source_external_state_flag_invalid")
    if target["approval_token_required"] != EXECUTION_APPROVAL_TOKEN:
        blockers.append("approval_token_required_invalid")
    if not target["execution_command_present"]:
        blockers.append("execution_command_missing")
    if not target["bundle_command_present"]:
        blockers.append("bundle_command_missing")
    if not target["bundle_validation_command_present"]:
        blockers.append("bundle_validation_command_missing")

    if not operator_approval_csv_present:
        blockers.append("operator_approval_csv_missing")

    target_key = _identity(target)
    matched_rows = [row for row in operator_approval_rows if _identity(row) == target_key]
    unknown_rows = [row for row in operator_approval_rows if _identity(row) != target_key]
    if len(matched_rows) > 1:
        blockers.append("duplicate_operator_approval_rows")
    if unknown_rows:
        blockers.append("operator_approval_row_not_in_product_target")

    approval_row = matched_rows[0] if matched_rows else {}
    decision = _text(approval_row.get("operator_decision")).lower()
    operator_token = _text(approval_row.get("operator_approval_token") or approval_row.get("approval_token"))
    row_blockers: list[str] = []
    if not approval_row:
        row_blockers.append("operator_decision_missing")
        gate_status = "awaiting_operator_approval"
    elif decision not in VALID_DECISIONS:
        row_blockers.append("operator_decision_invalid")
        gate_status = "blocked_before_execution"
    elif decision == SKIP_DECISION:
        gate_status = "skipped_by_operator"
    elif operator_token != target["approval_token_required"]:
        row_blockers.append("operator_approval_token_mismatch")
        gate_status = "blocked_before_execution"
    else:
        gate_status = "authorized_for_operator_execution"
    blockers.extend(row_blockers)

    row = {
        "target_id": target["target_id"],
        "family": target["family"],
        "bundle_tag": target["bundle_tag"],
        "approval_gate_status": gate_status,
        "operator_decision": decision,
        "approval_token_required": target["approval_token_required"],
        "operator_approval_token_present": bool(operator_token),
        "execution_command_present": target["execution_command_present"],
        "bundle_command_present": target["bundle_command_present"],
        "bundle_validation_command_present": target["bundle_validation_command_present"],
        "blockers": ",".join(row_blockers),
        "execution_enabled": False,
        "docking_results_emitted": False,
        "bundle_assembled": False,
        "external_state_mutated": False,
    }
    authorized = gate_status == "authorized_for_operator_execution" and not blockers
    skipped = gate_status == "skipped_by_operator" and not row_blockers
    status = "product_execution_operator_approval_gate_ready" if authorized else "blocked_product_execution_operator_approval_gate"
    summary = {
        "packet_type": "product_execution_operator_approval_gate",
        "status": status,
        "source_product_execution_preflight_json": product_execution_preflight_json,
        "source_product_execution_preflight_status": _text(preflight.get("status")),
        "source_product_execution_work_order_json": product_execution_work_order_json,
        "source_product_execution_work_order_status": _text(work_order.get("status")),
        "operator_approval_csv": operator_approval_csv,
        "operator_approval_csv_present": bool(operator_approval_csv_present),
        "operator_template_csv": template_csv,
        "target_id": target["target_id"],
        "family": target["family"],
        "bundle_tag": target["bundle_tag"],
        "authorized_for_execution": bool(authorized),
        "authorized_row_count": 1 if authorized else 0,
        "awaiting_operator_approval_row_count": 1 if gate_status == "awaiting_operator_approval" else 0,
        "skipped_row_count": 1 if skipped else 0,
        "blocked_row_count": 1 if row_blockers or blockers else 0,
        "unknown_operator_approval_row_count": len(unknown_rows),
        "approval_token_required": target["approval_token_required"],
        "blocker_count": len(blockers),
        "blockers": sorted(set(blockers)),
        "execution_enabled": False,
        "docking_results_emitted": False,
        "bundle_assembled": False,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "Run the product execution command only through the separate operator-approved execution path."
            if authorized
            else f"Fill `{template_csv}` into `{operator_approval_csv}` with an exact decision and approval token."
        ),
    }
    return {"summary": summary, "rows": [row]}


def _write_markdown(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    s = payload["summary"]
    lines = [
        "# Product Execution Operator Approval Gate",
        "",
        f"- status: `{s['status']}`",
        f"- target_id: `{s['target_id']}`",
        f"- family: `{s['family']}`",
        f"- bundle_tag: `{s['bundle_tag']}`",
        f"- operator_approval_csv_present: `{s['operator_approval_csv_present']}`",
        f"- authorized_for_execution: `{s['authorized_for_execution']}`",
        f"- authorized_row_count: `{s['authorized_row_count']}`",
        f"- awaiting_operator_approval_row_count: `{s['awaiting_operator_approval_row_count']}`",
        f"- skipped_row_count: `{s['skipped_row_count']}`",
        f"- blocked_row_count: `{s['blocked_row_count']}`",
        f"- approval_token_required: `{s['approval_token_required']}`",
        f"- execution_enabled: `{s['execution_enabled']}`",
        f"- docking_results_emitted: `{s['docking_results_emitted']}`",
        f"- bundle_assembled: `{s['bundle_assembled']}`",
        f"- external_state_mutated: `{s['external_state_mutated']}`",
        "",
        "## Rows",
        "",
        "| gate_status | target | family | bundle | decision | token_present | blockers |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['approval_gate_status']}` | `{row['target_id']}` | `{row['family']}` | "
            f"`{row['bundle_tag']}` | `{row['operator_decision']}` | "
            f"`{row['operator_approval_token_present']}` | `{row['blockers']}` |"
        )
    lines.extend(["", "## Blockers", ""])
    if s["blockers"]:
        lines.extend(f"- `{blocker}`" for blocker in s["blockers"])
    else:
        lines.append("- none")
    lines.extend(["", "## Claim Boundary", "", s["claim_boundary"], "", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate product operator approval tokens without running product execution.")
    parser.add_argument("--product-execution-preflight-json", default=DEFAULT_PRODUCT_PREFLIGHT_JSON)
    parser.add_argument("--product-execution-work-order-json", default=DEFAULT_PRODUCT_WORK_ORDER_JSON)
    parser.add_argument("--operator-approval-csv", default=DEFAULT_OPERATOR_APPROVAL_CSV)
    parser.add_argument("--template-csv", default=DEFAULT_TEMPLATE_CSV)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    preflight_packet = _read_json_if_present(args.product_execution_preflight_json)
    work_order_packet = _read_json_if_present(args.product_execution_work_order_json)
    target = _approval_target(preflight_packet, work_order_packet)
    _write_template(args.template_csv, target)
    operator_path = _resolve(args.operator_approval_csv)
    payload = build_product_execution_approval_gate(
        product_execution_preflight_packet=preflight_packet,
        product_execution_work_order_packet=work_order_packet,
        operator_approval_rows=_read_csv_rows(args.operator_approval_csv),
        product_execution_preflight_json=args.product_execution_preflight_json,
        product_execution_work_order_json=args.product_execution_work_order_json,
        operator_approval_csv=args.operator_approval_csv,
        template_csv=args.template_csv,
        operator_approval_csv_present=operator_path.exists(),
    )
    _write_json(args.out_json, payload)
    write_csv_rows(_resolve(args.out_csv), payload["rows"])
    _write_markdown(args.out_md, payload)


if __name__ == "__main__":
    main()

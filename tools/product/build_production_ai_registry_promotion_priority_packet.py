#!/usr/bin/env python3
"""Prioritize operator work for production AI registry promotion."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows
from tools.product.build_production_ai_registry_promotion_operator_receipt import (
    APPROVAL_TOKEN,
    GUARDED_MODES,
)

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OPERATOR_RECEIPT_JSON = "runs/production_ai_registry_promotion_operator_receipt_current.json"
DEFAULT_OPERATOR_RECEIPT_CSV = "config/production_ai_registry_promotion_operator_receipt_current.csv"
DEFAULT_REGISTRY_JSON = "runs/residual_model_registry_current.json"
DEFAULT_CHECKPOINT_READINESS_JSON = "runs/product_production_ai_checkpoint_readiness_current.json"
DEFAULT_PROMOTION_WORKBENCH_JSON = "runs/product_production_ai_promotion_workbench_current.json"
DEFAULT_OUT_JSON = "runs/production_ai_registry_promotion_priority_packet_current.json"
DEFAULT_OUT_CSV = "runs/production_ai_registry_promotion_priority_packet_current.csv"
DEFAULT_OUT_MD = "runs/production_ai_registry_promotion_priority_packet_current.md"

REQUIRED_GATES = [
    "trained_model_checkpoint_count_positive",
    "default_residual_mode_guarded",
    "production_promotion_allowed",
    "customer_facing_mutation_flags",
]

CUSTOMER_FACING_FLAG_FIELDS = [
    "customer_facing_auto_correction_allowed",
    "customer_facing_score_mutation_allowed",
    "customer_facing_ranking_mutation_allowed",
]

CLAIM_BOUNDARY = (
    "Production AI registry promotion priority packet only; it orders existing local registry, "
    "checkpoint-readiness, promotion-workbench, and operator-receipt artifacts into operator-facing "
    "promotion gates. It does not edit the registry, create checkpoints, enable customer-facing mutation, "
    "promote models, run GPU jobs, deploy, upload, email, delete, commit, push, or mutate external state."
)


def _resolve(path_like: str | Path, *, root: Path = ROOT) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else root / path


def _display_path(path: str | Path, *, root: Path = ROOT) -> str:
    resolved = _resolve(path, root=root)
    try:
        return str(resolved.relative_to(root))
    except ValueError:
        return str(resolved)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _int(value: Any, default: int = 0) -> int:
    try:
        return int(float(_text(value)))
    except (TypeError, ValueError):
        return default


def _read_json(path_like: str | Path, *, root: Path = ROOT) -> tuple[dict[str, Any], bool]:
    path = _resolve(path_like, root=root)
    if not path.is_file():
        return {}, False
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}, True
    return (payload if isinstance(payload, dict) else {}), True


def _summary(packet: dict[str, Any]) -> dict[str, Any]:
    summary = packet.get("summary")
    if isinstance(summary, dict):
        return summary
    return packet if isinstance(packet, dict) and packet.get("status") else {}


def _artifact_present(path_like: str | Path, *, root: Path = ROOT) -> bool:
    return _resolve(path_like, root=root).is_file()


def _customer_facing_flags_ready(summary: dict[str, Any]) -> bool:
    return all(summary.get(field) is True for field in CUSTOMER_FACING_FLAG_FIELDS)


def _reported_missing_gates(summary: dict[str, Any]) -> list[str]:
    gates = summary.get("registry_promotion_missing_gate_ids")
    if not isinstance(gates, list):
        return []
    return [str(gate) for gate in gates if str(gate)]


def _gate_row(
    gate_id: str,
    *,
    priority: int,
    gate_satisfied: bool,
    bucket: str,
    prerequisite_gate_id: str,
    observed_value: str,
    required_input: str,
    acceptance_artifact: str,
    verification_command: str,
    next_operator_step: str,
    registry_summary: dict[str, Any],
    checkpoint_summary: dict[str, Any],
    workbench_summary: dict[str, Any],
    receipt_summary: dict[str, Any],
) -> dict[str, Any]:
    checkpoint_missing = _reported_missing_gates(checkpoint_summary)
    workbench_missing = _reported_missing_gates(workbench_summary)
    return {
        "priority": priority,
        "gate_id": gate_id,
        "priority_bucket": "gate_satisfied" if gate_satisfied else bucket,
        "gate_satisfied": gate_satisfied,
        "operator_input_required": not gate_satisfied,
        "prerequisite_gate_id": prerequisite_gate_id,
        "observed_value": observed_value,
        "required_input": required_input,
        "acceptance_artifact": acceptance_artifact,
        "verification_command": verification_command,
        "next_operator_step": next_operator_step,
        "approval_token_required": APPROVAL_TOKEN,
        "operator_receipt_status": _text(receipt_summary.get("status")),
        "operator_receipt_ready": bool(receipt_summary.get("operator_receipt_ready") is True),
        "operator_receipt_first_blocked_row_blocker": _text(
            receipt_summary.get("first_blocked_row_blocker")
        ),
        "reported_missing_by_checkpoint_readiness": gate_id in checkpoint_missing,
        "reported_missing_by_promotion_workbench": gate_id in workbench_missing,
        "observed_registry_default_residual_mode": _text(
            registry_summary.get("default_residual_mode")
        ),
        "observed_registry_trained_model_checkpoint_count": _int(
            registry_summary.get("trained_model_checkpoint_count")
        ),
        "observed_registry_production_promotion_allowed": bool(
            registry_summary.get("production_promotion_allowed") is True
        ),
        "observed_registry_customer_facing_mutation_flags_ready": _customer_facing_flags_ready(
            registry_summary
        ),
        "observed_checkpoint_registry_promotion_currently_satisfied": bool(
            checkpoint_summary.get("registry_promotion_currently_satisfied") is True
        ),
        "model_promoted": False,
        "customer_facing_mutation_enabled": False,
        "external_state_mutated": False,
    }


def _build_rows(
    *,
    registry_summary: dict[str, Any],
    checkpoint_summary: dict[str, Any],
    workbench_summary: dict[str, Any],
    receipt_summary: dict[str, Any],
) -> list[dict[str, Any]]:
    checkpoint_count = _int(registry_summary.get("trained_model_checkpoint_count"))
    default_mode = _text(registry_summary.get("default_residual_mode"))
    production_promotion_allowed = bool(registry_summary.get("production_promotion_allowed") is True)
    customer_flags_ready = _customer_facing_flags_ready(registry_summary)
    checkpoint_gate = checkpoint_count > 0
    guarded_mode_gate = default_mode in GUARDED_MODES
    production_gate = production_promotion_allowed
    customer_flags_gate = customer_flags_ready

    return [
        _gate_row(
            "trained_model_checkpoint_count_positive",
            priority=1,
            gate_satisfied=checkpoint_gate,
            bucket="trained_checkpoint_registration_required",
            prerequisite_gate_id="",
            observed_value=f"trained_model_checkpoint_count={checkpoint_count}",
            required_input=(
                "Register a trained production residual checkpoint that passes checkpoint preflight in "
                "runs/residual_model_registry_current.json."
            ),
            acceptance_artifact=DEFAULT_REGISTRY_JSON,
            verification_command=(
                "python3 tools/build_residual_model_registry.py; "
                "python3 tools/build_product_production_ai_checkpoint_readiness.py; "
                "python3 tools/build_product_production_ai_promotion_workbench.py; "
                "python3 tools/build_production_ai_registry_promotion_operator_receipt.py"
            ),
            next_operator_step=(
                "Return or register a trained checkpoint, rerun residual registry and checkpoint-readiness gates, "
                "then rebuild the operator receipt."
            ),
            registry_summary=registry_summary,
            checkpoint_summary=checkpoint_summary,
            workbench_summary=workbench_summary,
            receipt_summary=receipt_summary,
        ),
        _gate_row(
            "default_residual_mode_guarded",
            priority=2,
            gate_satisfied=guarded_mode_gate,
            bucket=(
                "blocked_until_trained_checkpoint_registered"
                if not checkpoint_gate
                else "guarded_residual_mode_selection_required"
            ),
            prerequisite_gate_id="trained_model_checkpoint_count_positive",
            observed_value=f"default_residual_mode={default_mode}",
            required_input="Set the registry default residual mode to assist, production, or production_guarded.",
            acceptance_artifact=DEFAULT_REGISTRY_JSON,
            verification_command=(
                "python3 tools/build_residual_model_registry.py; "
                "python3 tools/build_product_production_ai_checkpoint_readiness.py"
            ),
            next_operator_step=(
                "Keep shadow mode until a trained checkpoint is registered; then select a guarded residual mode "
                "and rerun registry readiness."
            ),
            registry_summary=registry_summary,
            checkpoint_summary=checkpoint_summary,
            workbench_summary=workbench_summary,
            receipt_summary=receipt_summary,
        ),
        _gate_row(
            "production_promotion_allowed",
            priority=3,
            gate_satisfied=production_gate,
            bucket=(
                "blocked_until_guarded_registry_ready"
                if not (checkpoint_gate and guarded_mode_gate)
                else "production_promotion_policy_review_required"
            ),
            prerequisite_gate_id="default_residual_mode_guarded",
            observed_value=f"production_promotion_allowed={production_promotion_allowed}",
            required_input="Approve guarded registry promotion policy after checkpoint and mode gates are ready.",
            acceptance_artifact=DEFAULT_CHECKPOINT_READINESS_JSON,
            verification_command=(
                "python3 tools/build_product_production_ai_checkpoint_readiness.py; "
                "python3 tools/build_product_production_ai_promotion_workbench.py"
            ),
            next_operator_step=(
                "Do not promote until checkpoint count and guarded mode are ready; then review production "
                "promotion policy and rerun checkpoint readiness."
            ),
            registry_summary=registry_summary,
            checkpoint_summary=checkpoint_summary,
            workbench_summary=workbench_summary,
            receipt_summary=receipt_summary,
        ),
        _gate_row(
            "customer_facing_mutation_flags",
            priority=4,
            gate_satisfied=customer_flags_gate,
            bucket=(
                "blocked_until_production_promotion_allowed"
                if not production_gate
                else "customer_facing_mutation_policy_review_required"
            ),
            prerequisite_gate_id="production_promotion_allowed",
            observed_value=(
                "customer_facing_auto_correction_allowed="
                f"{bool(registry_summary.get('customer_facing_auto_correction_allowed') is True)};"
                "customer_facing_score_mutation_allowed="
                f"{bool(registry_summary.get('customer_facing_score_mutation_allowed') is True)};"
                "customer_facing_ranking_mutation_allowed="
                f"{bool(registry_summary.get('customer_facing_ranking_mutation_allowed') is True)}"
            ),
            required_input=(
                "Review and set guarded customer-facing auto-correction, score-mutation, and ranking-mutation "
                "policy flags."
            ),
            acceptance_artifact=DEFAULT_OPERATOR_RECEIPT_JSON,
            verification_command=(
                "python3 tools/build_product_production_ai_promotion_workbench.py; "
                "python3 tools/build_production_ai_registry_promotion_operator_receipt.py"
            ),
            next_operator_step=(
                "Keep customer-facing mutation disabled until promotion policy is allowed; then fill the operator "
                "receipt with reviewed mutation policy flags."
            ),
            registry_summary=registry_summary,
            checkpoint_summary=checkpoint_summary,
            workbench_summary=workbench_summary,
            receipt_summary=receipt_summary,
        ),
    ]


def build_production_ai_registry_promotion_priority_packet(
    *,
    operator_receipt_json: str | Path = DEFAULT_OPERATOR_RECEIPT_JSON,
    operator_receipt_csv: str | Path = DEFAULT_OPERATOR_RECEIPT_CSV,
    registry_json: str | Path = DEFAULT_REGISTRY_JSON,
    checkpoint_readiness_json: str | Path = DEFAULT_CHECKPOINT_READINESS_JSON,
    promotion_workbench_json: str | Path = DEFAULT_PROMOTION_WORKBENCH_JSON,
    root: str | Path = ROOT,
) -> dict[str, Any]:
    root_path = Path(root)
    receipt_packet, receipt_present = _read_json(operator_receipt_json, root=root_path)
    registry_packet, registry_present = _read_json(registry_json, root=root_path)
    checkpoint_packet, checkpoint_present = _read_json(checkpoint_readiness_json, root=root_path)
    workbench_packet, workbench_present = _read_json(promotion_workbench_json, root=root_path)
    receipt_csv_present = _artifact_present(operator_receipt_csv, root=root_path)
    receipt_summary = _summary(receipt_packet)
    registry_summary = _summary(registry_packet)
    checkpoint_summary = _summary(checkpoint_packet)
    workbench_summary = _summary(workbench_packet)

    rows = _build_rows(
        registry_summary=registry_summary,
        checkpoint_summary=checkpoint_summary,
        workbench_summary=workbench_summary,
        receipt_summary=receipt_summary,
    )
    operator_required_rows = [row for row in rows if row["operator_input_required"]]
    top_row = operator_required_rows[0] if operator_required_rows else (rows[0] if rows else {})
    source_blockers: list[str] = []
    if not receipt_present:
        source_blockers.append("operator_receipt_artifact_missing")
    if not receipt_csv_present:
        source_blockers.append("operator_receipt_csv_missing")
    if not registry_present:
        source_blockers.append("residual_registry_artifact_missing")
    if not checkpoint_present:
        source_blockers.append("checkpoint_readiness_artifact_missing")
    if not workbench_present:
        source_blockers.append("promotion_workbench_artifact_missing")
    priority_packet_ready = not source_blockers
    blockers = list(source_blockers)
    if operator_required_rows:
        blockers.append("registry_promotion_operator_priority_items_pending")
    ready = priority_packet_ready and not operator_required_rows
    missing_gate_ids = [row["gate_id"] for row in rows if not row["gate_satisfied"]]

    summary = {
        "packet_type": "production_ai_registry_promotion_priority_packet",
        "status": (
            "production_ai_registry_promotion_priority_packet_ready"
            if ready
            else "blocked_production_ai_registry_promotion_priority_packet"
        ),
        "priority_packet_ready": priority_packet_ready,
        "registry_promotion_ready": ready,
        "operator_receipt_ready": bool(receipt_summary.get("operator_receipt_ready") is True),
        "operator_receipt_status": _text(receipt_summary.get("status")),
        "priority_item_count": len(rows),
        "operator_input_required_count": len(operator_required_rows),
        "blocked_priority_item_count": len(operator_required_rows),
        "required_gate_count": len(REQUIRED_GATES),
        "registry_promotion_missing_gate_ids": missing_gate_ids,
        "registry_promotion_missing_gate_count": len(missing_gate_ids),
        "observed_checkpoint_registry_promotion_missing_gate_ids": _reported_missing_gates(
            checkpoint_summary
        ),
        "observed_workbench_registry_promotion_missing_gate_ids": _reported_missing_gates(
            workbench_summary
        ),
        "top_gate_id": _text(top_row.get("gate_id")),
        "top_priority_bucket": _text(top_row.get("priority_bucket")),
        "top_required_input": _text(top_row.get("required_input")),
        "top_acceptance_artifact": _text(top_row.get("acceptance_artifact")),
        "top_verification_command": _text(top_row.get("verification_command")),
        "top_next_operator_step": _text(top_row.get("next_operator_step")),
        "operator_receipt_csv": _display_path(operator_receipt_csv, root=root_path),
        "operator_receipt_csv_present": receipt_csv_present,
        "operator_receipt_artifact": _display_path(operator_receipt_json, root=root_path),
        "operator_receipt_artifact_present": receipt_present,
        "residual_registry_artifact": _display_path(registry_json, root=root_path),
        "residual_registry_artifact_present": registry_present,
        "checkpoint_readiness_artifact": _display_path(checkpoint_readiness_json, root=root_path),
        "checkpoint_readiness_artifact_present": checkpoint_present,
        "promotion_workbench_artifact": _display_path(promotion_workbench_json, root=root_path),
        "promotion_workbench_artifact_present": workbench_present,
        "observed_registry_default_residual_mode": _text(
            registry_summary.get("default_residual_mode")
        ),
        "observed_registry_trained_model_checkpoint_count": _int(
            registry_summary.get("trained_model_checkpoint_count")
        ),
        "observed_registry_production_promotion_allowed": bool(
            registry_summary.get("production_promotion_allowed") is True
        ),
        "observed_registry_customer_facing_mutation_flags_ready": _customer_facing_flags_ready(
            registry_summary
        ),
        "observed_checkpoint_registry_promotion_currently_satisfied": bool(
            checkpoint_summary.get("registry_promotion_currently_satisfied") is True
        ),
        "approval_token_required": APPROVAL_TOKEN,
        "approval_token_count": 1,
        "blocker_count": len(blockers),
        "blockers": blockers,
        "source_artifacts": [
            str(operator_receipt_json),
            str(operator_receipt_csv),
            str(registry_json),
            str(checkpoint_readiness_json),
            str(promotion_workbench_json),
        ],
        "registry_edited_by_this_tool": False,
        "checkpoint_created_by_this_tool": False,
        "execution_enabled": False,
        "docking_results_emitted": False,
        "model_promoted": False,
        "customer_facing_mutation_enabled": False,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "Production AI registry promotion priority rows are verified; rerun operator receipt, goal audit, "
            "commercial readiness handoff, and release source-of-truth gates."
            if ready
            else "Resolve the top production AI registry promotion gate first, then refill the guarded operator receipt and rerun promotion readiness."
        ),
    }
    return {"summary": summary, "rows": rows}


def _write_json(path_like: str | Path, payload: dict[str, Any], *, root: Path = ROOT) -> None:
    path = _resolve(path_like, root=root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_markdown(path_like: str | Path, payload: dict[str, Any], *, root: Path = ROOT) -> None:
    path = _resolve(path_like, root=root)
    summary = payload["summary"]
    lines = [
        "# Production AI Registry Promotion Priority Packet",
        "",
        f"- status: `{summary['status']}`",
        f"- priority_packet_ready: `{summary['priority_packet_ready']}`",
        f"- registry_promotion_ready: `{summary['registry_promotion_ready']}`",
        f"- priority_item_count: `{summary['priority_item_count']}`",
        f"- operator_input_required_count: `{summary['operator_input_required_count']}`",
        f"- top_gate_id: `{summary['top_gate_id']}`",
        f"- top_priority_bucket: `{summary['top_priority_bucket']}`",
        f"- observed_registry_default_residual_mode: `{summary['observed_registry_default_residual_mode']}`",
        f"- observed_registry_trained_model_checkpoint_count: `{summary['observed_registry_trained_model_checkpoint_count']}`",
        f"- approval_token_required: `{summary['approval_token_required']}`",
        "",
        "## Rows",
        "",
        "| priority | gate | bucket | observed | next step |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['priority']}` | `{row['gate_id']}` | `{row['priority_bucket']}` | "
            f"`{row['observed_value']}` | `{row['next_operator_step']}` |"
        )
    lines.extend(["", "## Claim Boundary", "", summary["claim_boundary"], ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Build production AI registry promotion priority packet.")
    parser.add_argument("--operator-receipt-json", default=DEFAULT_OPERATOR_RECEIPT_JSON)
    parser.add_argument("--operator-receipt-csv", default=DEFAULT_OPERATOR_RECEIPT_CSV)
    parser.add_argument("--registry-json", default=DEFAULT_REGISTRY_JSON)
    parser.add_argument("--checkpoint-readiness-json", default=DEFAULT_CHECKPOINT_READINESS_JSON)
    parser.add_argument("--promotion-workbench-json", default=DEFAULT_PROMOTION_WORKBENCH_JSON)
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    args = parser.parse_args(argv)
    root = Path(args.root)
    payload = build_production_ai_registry_promotion_priority_packet(
        operator_receipt_json=args.operator_receipt_json,
        operator_receipt_csv=args.operator_receipt_csv,
        registry_json=args.registry_json,
        checkpoint_readiness_json=args.checkpoint_readiness_json,
        promotion_workbench_json=args.promotion_workbench_json,
        root=root,
    )
    _write_json(args.out_json, payload, root=root)
    write_csv_rows(_resolve(args.out_csv, root=root), payload["rows"])
    _write_markdown(args.out_md, payload, root=root)
    print(json.dumps(payload["summary"], indent=2, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()

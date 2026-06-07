from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from betelgeuze_product.runtime_paths import repo_root

ROOT = repo_root()

ARTIFACTS = {
    "operations-surface": "runs/cleanup_operations_surface_contract_current.json",
    "snapshot-preflight": "runs/cleanup_snapshot_preflight_current.json",
    "snapshot-artifacts": "runs/cleanup_snapshot_artifacts_current.json",
    "approval-dossier": "runs/cleanup_execution_approval_dossier_current.json",
    "payload-lock": "runs/cleanup_payload_manifest_lock_current.json",
    "approval-gate": "runs/cleanup_execution_approval_gate_current.json",
    "postcheck": "runs/cleanup_postcheck_contract_current.json",
    "completion": "runs/cleanup_completion_gate_current.json",
    "large-drilldown": "runs/large_cleanup_surface_drilldown_current.json",
    "protected-review": "runs/protected_cleanup_payload_review_current.json",
    "protected-ligand-heavy-review": "runs/protected_ligand_heavy_payload_deep_review_current.json",
    "protected-policy": "runs/protected_cleanup_policy_decision_gate_current.json",
    "transition-work-order": "runs/transition_cleanup_work_order_current.json",
    "transition-preflight": "runs/transition_cleanup_execution_preflight_current.json",
    "ligand-heavy-work-order": "runs/ligand_heavy_cleanup_work_order_current.json",
    "ligand-heavy-preflight": "runs/ligand_heavy_cleanup_execution_preflight_current.json",
}

CLAIM_BOUNDARY = (
    "Betelgeuze cleanup CLI only; it reads local cleanup approval, payload, protected-policy, and completion artifacts "
    "and prints status JSON. It does not approve cleanup, delete, move, archive, externalize, upload, commit, push, "
    "or mutate external state."
)


def _resolve(root: str | Path, path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else Path(root).resolve() / path


def _read_json_object(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _summary(packet: dict[str, Any]) -> dict[str, Any]:
    summary = packet.get("summary")
    return summary if isinstance(summary, dict) else {}


def _rows(packet: dict[str, Any]) -> list[dict[str, Any]]:
    return [row for row in packet.get("rows", []) or [] if isinstance(row, dict)]


def _blockers(packet: dict[str, Any]) -> list[dict[str, Any]]:
    return [row for row in packet.get("blockers", []) or [] if isinstance(row, dict)]


def _count(summary: dict[str, Any], packet: dict[str, Any], keys: tuple[str, ...], fallback: int = 0) -> int:
    for key in keys:
        try:
            value = int(summary.get(key) or 0)
        except (TypeError, ValueError):
            value = 0
        if value:
            return value
    return fallback


def _blocker_count(summary: dict[str, Any], packet: dict[str, Any]) -> int:
    return _count(
        summary,
        packet,
        (
            "blocker_count",
            "blocked_stage_count",
            "blocked_row_count",
            "blocked_approval_row_count",
        ),
        fallback=len(_blockers(packet)),
    )


def _approval_required_count(summary: dict[str, Any]) -> int:
    return _count(
        summary,
        {},
        (
            "approval_required_count",
            "approval_required_item_count",
            "approval_required_stage_count",
            "awaiting_operator_approval_row_count",
            "awaiting_policy_decision_row_count",
        ),
    )


def _float_value(value: Any) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _approval_tokens_from_value(value: Any) -> list[str]:
    if isinstance(value, list):
        tokens: list[str] = []
        for token in value:
            tokens.extend(_approval_tokens_from_value(token))
        return tokens
    normalized = str(value or "").replace(",", ";")
    return [token.strip() for token in normalized.split(";") if token.strip()]


def _approval_tokens_from_status(payload: dict[str, Any]) -> set[str]:
    tokens: set[str] = set()
    for key in ("approval_tokens_required", "approval_token_required"):
        tokens.update(_approval_tokens_from_value(payload.get(key)))
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    for key in ("approval_tokens_required", "approval_token_required"):
        tokens.update(_approval_tokens_from_value(summary.get(key)))
    rows = summary.get("rows") if isinstance(summary.get("rows"), list) else []
    for row in rows:
        if isinstance(row, dict):
            tokens.update(_approval_tokens_from_value(row.get("approval_token_required")))
    return tokens


def build_cli_status(command: str, *, root: str | Path = ROOT) -> dict[str, Any]:
    artifact_rel = ARTIFACTS[command]
    artifact = _resolve(root, artifact_rel)
    packet = _read_json_object(artifact)
    summary = _summary(packet)
    approval_tokens = sorted({token for row in _rows(packet) for token in _approval_tokens_from_value(row.get("approval_token_required"))})
    if not summary:
        return {
            "packet_type": "cleanup_cli_status",
            "command": command,
            "status": f"missing_cleanup_{command.replace('-', '_')}_artifact",
            "artifact_path": artifact_rel,
            "artifact_present": artifact.exists(),
            "row_count": 0,
            "blocker_count": 1,
            "approval_required_count": 0,
            "approval_token_count": 0,
            "approval_tokens_required": [],
            "summary": {},
            "execution_enabled": False,
            "delete_enabled": False,
            "delete_executed": False,
            "archive_executed": False,
            "externalize_executed": False,
            "external_state_mutated": False,
            "claim_boundary": CLAIM_BOUNDARY,
        }
    return {
        "packet_type": "cleanup_cli_status",
        "command": command,
        "status": str(summary.get("status") or "unknown"),
        "artifact_path": artifact_rel,
        "artifact_present": True,
        "row_count": len(_rows(packet)),
        "blocker_count": _blocker_count(summary, packet),
        "approval_required_count": _approval_required_count(summary),
        "approval_token_count": len(approval_tokens),
        "approval_tokens_required": approval_tokens,
        "summary": summary,
        "execution_enabled": False,
        "delete_enabled": False,
        "delete_executed": False,
        "archive_executed": False,
        "externalize_executed": False,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
    }


def build_all_status(*, root: str | Path = ROOT) -> dict[str, Any]:
    statuses = {command: build_cli_status(command, root=root) for command in ARTIFACTS}
    blocked_or_missing = [
        command
        for command, payload in statuses.items()
        if str(payload.get("status", "")).startswith(("blocked_", "missing_"))
    ]
    approval_required = [command for command, payload in statuses.items() if int(payload.get("approval_required_count") or 0) > 0]
    approval_tokens = sorted({token for payload in statuses.values() for token in _approval_tokens_from_status(payload)})
    approval_gate = statuses.get("approval-gate", {}).get("summary", {})
    postcheck = statuses.get("postcheck", {}).get("summary", {})
    protected_policy = statuses.get("protected-policy", {}).get("summary", {})
    if not isinstance(approval_gate, dict):
        approval_gate = {}
    if not isinstance(postcheck, dict):
        postcheck = {}
    if not isinstance(protected_policy, dict):
        protected_policy = {}
    return {
        "packet_type": "cleanup_cli_status_set",
        "status": "blocked_cleanup_cli_status_set" if blocked_or_missing else "cleanup_cli_status_set_ready",
        "command_count": len(statuses),
        "blocked_or_missing_command_count": len(blocked_or_missing),
        "blocked_or_missing_commands": blocked_or_missing,
        "approval_required_command_count": len(approval_required),
        "approval_required_commands": approval_required,
        "approval_token_count": len(approval_tokens),
        "approval_tokens_required": approval_tokens,
        "authorized_row_count": int(approval_gate.get("authorized_row_count") or 0),
        "awaiting_operator_approval_row_count": int(approval_gate.get("awaiting_operator_approval_row_count") or 0),
        "approval_reclaim_size_gb": _float_value(
            approval_gate.get("total_reclaim_size_gb") or approval_gate.get("approval_reclaim_size_gb")
        ),
        "authorized_reclaim_size_gb": _float_value(approval_gate.get("authorized_reclaim_size_gb")),
        "postcheck_contract_ready": bool(postcheck.get("postcheck_contract_ready") is True),
        "postcheck_row_count": int(postcheck.get("row_count") or 0),
        "postcheck_blocked_row_count": int(postcheck.get("blocked_row_count") or 0),
        "postcheck_global_refresh_command_count": int(postcheck.get("global_refresh_command_count") or 0),
        "protected_payload_size_gb": _float_value(protected_policy.get("protected_payload_size_gb")),
        "protected_policy_change_required_count": int(
            protected_policy.get("policy_change_required_count")
            or protected_policy.get("policy_change_required_for_deletion_count")
            or 0
        ),
        "protected_policy_resolved": bool(protected_policy.get("policy_resolved") is True),
        "statuses": statuses,
        "execution_enabled": False,
        "delete_enabled": False,
        "delete_executed": False,
        "archive_executed": False,
        "externalize_executed": False,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Read local Betelgeuze cleanup status artifacts as JSON.")
    parser.add_argument(
        "command",
        choices=[*ARTIFACTS.keys(), "all"],
        help="Cleanup status surface to read.",
    )
    parser.add_argument("--root", default=str(ROOT), help="Repository root containing the runs/ artifacts.")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON output.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    payload = build_all_status(root=args.root) if args.command == "all" else build_cli_status(args.command, root=args.root)
    json.dump(payload, sys.stdout, ensure_ascii=False, indent=2 if args.pretty else None, sort_keys=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

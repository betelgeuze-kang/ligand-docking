#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows
from tools.build_protected_cleanup_policy_decision_gate import DEFAULT_OUT_JSON as DEFAULT_PROTECTED_POLICY_GATE_JSON

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_TRANSITION_PREFLIGHT_JSON = "runs/transition_cleanup_execution_preflight_current.json"
DEFAULT_SNAPSHOT_PREFLIGHT_JSON = "runs/cleanup_snapshot_preflight_current.json"
DEFAULT_SNAPSHOT_ARTIFACTS_JSON = "runs/cleanup_snapshot_artifacts_current.json"
DEFAULT_LIGAND_PREFLIGHT_JSON = "runs/ligand_heavy_cleanup_execution_preflight_current.json"
DEFAULT_PROTECTED_REVIEW_JSON = "runs/protected_cleanup_payload_review_current.json"
DEFAULT_PROTECTED_POLICY_JSON = DEFAULT_PROTECTED_POLICY_GATE_JSON
DEFAULT_OUT_JSON = "runs/cleanup_execution_approval_dossier_current.json"
DEFAULT_OUT_CSV = "runs/cleanup_execution_approval_dossier_current.csv"
DEFAULT_OUT_MD = "runs/cleanup_execution_approval_dossier_current.md"

CLAIM_BOUNDARY = (
    "Cleanup execution approval dossier only; it consolidates approval-ready cleanup rows, snapshot evidence, "
    "ligand-heavy stale payload candidates, and protected-not-promoted rows. It does not delete, move, archive, "
    "externalize, upload, commit, push, or mutate external state."
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


def _summary(packet: dict[str, Any]) -> dict[str, Any]:
    summary = packet.get("summary")
    return summary if isinstance(summary, dict) else {}


def _rows(packet: dict[str, Any]) -> list[dict[str, Any]]:
    return [row for row in packet.get("rows", []) or [] if isinstance(row, dict)]


def _text(value: Any) -> str:
    return str(value or "").strip()


def _int(value: Any) -> int:
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0


def _float(value: Any) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _key(row: dict[str, Any]) -> tuple[str, str, str]:
    return (_text(row.get("lane")), _text(row.get("recommended_action")), _text(row.get("path")))


def _source_status_blockers(
    *,
    transition: dict[str, Any],
    snapshot_preflight: dict[str, Any],
    snapshot_artifacts: dict[str, Any],
    ligand: dict[str, Any],
    protected: dict[str, Any],
) -> list[str]:
    checks = [
        (_summary(transition).get("status"), "transition_cleanup_execution_preflight_ready", "transition_preflight_not_ready"),
        (_summary(snapshot_preflight).get("status"), "cleanup_snapshot_preflight_ready", "snapshot_preflight_not_ready"),
        (_summary(snapshot_artifacts).get("status"), "cleanup_snapshot_artifacts_ready", "snapshot_artifacts_not_ready"),
        (_summary(ligand).get("status"), "ligand_heavy_cleanup_execution_preflight_ready", "ligand_cleanup_preflight_not_ready"),
        (_summary(protected).get("status"), "protected_cleanup_payload_review_ready", "protected_cleanup_review_not_ready"),
    ]
    return [code for observed, required, code in checks if observed != required]


def build_cleanup_execution_approval_dossier(
    *,
    transition_preflight_packet: dict[str, Any],
    cleanup_snapshot_preflight_packet: dict[str, Any],
    cleanup_snapshot_artifacts_packet: dict[str, Any],
    ligand_cleanup_preflight_packet: dict[str, Any],
    protected_cleanup_review_packet: dict[str, Any],
    protected_cleanup_policy_packet: dict[str, Any] | None = None,
    transition_preflight_path: str = DEFAULT_TRANSITION_PREFLIGHT_JSON,
    cleanup_snapshot_preflight_path: str = DEFAULT_SNAPSHOT_PREFLIGHT_JSON,
    cleanup_snapshot_artifacts_path: str = DEFAULT_SNAPSHOT_ARTIFACTS_JSON,
    ligand_cleanup_preflight_path: str = DEFAULT_LIGAND_PREFLIGHT_JSON,
    protected_cleanup_review_path: str = DEFAULT_PROTECTED_REVIEW_JSON,
    protected_cleanup_policy_path: str = DEFAULT_PROTECTED_POLICY_JSON,
) -> dict[str, Any]:
    blockers = _source_status_blockers(
        transition=transition_preflight_packet,
        snapshot_preflight=cleanup_snapshot_preflight_packet,
        snapshot_artifacts=cleanup_snapshot_artifacts_packet,
        ligand=ligand_cleanup_preflight_packet,
        protected=protected_cleanup_review_packet,
    )
    snapshot_preflight_by_key = {_key(row): row for row in _rows(cleanup_snapshot_preflight_packet)}
    snapshot_artifact_by_key = {_key(row): row for row in _rows(cleanup_snapshot_artifacts_packet)}
    protected_cleanup_policy_packet = protected_cleanup_policy_packet or {}
    protected_policy_by_path = {
        _text(row.get("path")): row for row in _rows(protected_cleanup_policy_packet) if _text(row.get("path"))
    }

    rows: list[dict[str, Any]] = []
    for source_row in _rows(transition_preflight_packet):
        if _text(source_row.get("work_order_status")) != "approval_gated":
            continue
        key = _key(source_row)
        snapshot_preflight = snapshot_preflight_by_key.get(key, {})
        snapshot_artifact = snapshot_artifact_by_key.get(key, {})
        action = _text(source_row.get("recommended_action"))
        row_blockers: list[str] = []
        if _text(source_row.get("preflight_status")) != "pass":
            row_blockers.append("transition_row_preflight_not_pass")
        if bool(snapshot_preflight.get("snapshot_required") is True):
            if snapshot_preflight.get("snapshot_present") is not True:
                row_blockers.append("required_snapshot_missing")
            if _text(snapshot_artifact.get("snapshot_status")) != "cleanup_snapshot_artifact_ready":
                row_blockers.append("snapshot_artifact_not_ready")
        if row_blockers:
            blockers.extend(row_blockers)
        rows.append(
            {
                "lane": _text(source_row.get("lane")),
                "operation_class": "transition_cleanup",
                "recommended_action": action,
                "path": _text(source_row.get("path")),
                "approval_status": "approval_required" if not row_blockers else "blocked_before_approval",
                "approval_token_required": _text(source_row.get("approval_token")),
                "size_gb": round(_float(source_row.get("size_gb")), 3),
                "candidate_count": 1,
                "preflight_status": _text(source_row.get("preflight_status")),
                "snapshot_required": bool(snapshot_preflight.get("snapshot_required") is True),
                "snapshot_present": bool(snapshot_preflight.get("snapshot_present") is True),
                "snapshot_artifact": _text(snapshot_preflight.get("snapshot_artifact") or snapshot_artifact.get("snapshot_artifact")),
                "snapshot_fingerprint_sha256": _text(snapshot_artifact.get("metadata_fingerprint_sha256")),
                "snapshot_entry_count": _int(snapshot_artifact.get("entry_count")),
                "snapshot_file_count": _int(snapshot_artifact.get("file_count")),
                "snapshot_listing_truncated": bool(snapshot_artifact.get("listing_truncated") is True),
                "postcheck": _text(snapshot_preflight.get("postcheck")),
                "blockers": ",".join(row_blockers),
                "protected_policy_change_required": False,
                "approval_promoted": True,
                "execution_enabled": False,
                "delete_executed": False,
                "external_state_mutated": False,
            }
        )

    ligand_summary = _summary(ligand_cleanup_preflight_packet)
    ligand_blockers: list[str] = []
    if _text(ligand_summary.get("status")) != "ligand_heavy_cleanup_execution_preflight_ready":
        ligand_blockers.append("ligand_cleanup_preflight_not_ready")
    if _int(ligand_summary.get("existing_candidate_count")) <= 0:
        ligand_blockers.append("ligand_existing_candidates_missing")
    if ligand_blockers:
        blockers.extend(ligand_blockers)
    rows.append(
        {
            "lane": "ligand_heavy_cleanup",
            "operation_class": "ligand_heavy_stale_payload_delete",
            "recommended_action": "delete_stale_stage2_trajectory_payloads_after_approval",
            "path": ligand_cleanup_preflight_path,
            "approval_status": "approval_required" if not ligand_blockers else "blocked_before_approval",
            "approval_token_required": _text(ligand_summary.get("approval_token_required")),
            "size_gb": round(_float(ligand_summary.get("candidate_size_gb")), 3),
            "candidate_count": _int(ligand_summary.get("existing_candidate_count") or ligand_summary.get("candidate_count")),
            "preflight_status": _text(ligand_summary.get("status")),
            "snapshot_required": False,
            "snapshot_present": False,
            "snapshot_artifact": "",
            "snapshot_fingerprint_sha256": "",
            "snapshot_entry_count": 0,
            "snapshot_file_count": 0,
            "snapshot_listing_truncated": False,
            "postcheck": "rerun ligand-heavy cleanup dry-run and release gates after approved deletion",
            "blockers": ",".join(ligand_blockers),
            "protected_policy_change_required": False,
            "approval_promoted": True,
            "execution_enabled": False,
            "delete_executed": False,
            "external_state_mutated": False,
        }
    )

    for protected_row in _rows(protected_cleanup_review_packet):
        protected_path = _text(protected_row.get("path"))
        policy_row = protected_policy_by_path.get(protected_path, {})
        policy_status = _text(policy_row.get("policy_gate_status"))
        policy_change_requested = policy_status == "policy_change_requested"
        approval_status = "approval_required" if policy_change_requested else "policy_blocked_not_promoted"
        rows.append(
            {
                "lane": "protected_cleanup",
                "operation_class": (
                    "protected_ligand_heavy_policy_change_delete"
                    if policy_change_requested
                    else "protected_not_promoted"
                ),
                "recommended_action": (
                    "delete_policy_changed_protected_ligand_heavy_payload"
                    if policy_change_requested
                    else "keep_protected_until_explicit_policy_change"
                ),
                "path": protected_path,
                "approval_status": approval_status,
                "approval_token_required": (
                    _text(ligand_summary.get("approval_token_required"))
                    if policy_change_requested
                    else ""
                ),
                "size_gb": round(_float(protected_row.get("known_payload_size_gb")), 3),
                "candidate_count": _int(protected_row.get("known_payload_count")),
                "preflight_status": _text(protected_row.get("source_dry_run_status")),
                "snapshot_required": False,
                "snapshot_present": False,
                "snapshot_artifact": "",
                "snapshot_fingerprint_sha256": "",
                "snapshot_entry_count": 0,
                "snapshot_file_count": 0,
                "snapshot_listing_truncated": False,
                "postcheck": (
                    "rerun ligand-heavy cleanup dry-run and verify protected path no longer exists after approved policy-change deletion"
                    if policy_change_requested
                    else "do not promote to deletion unless cleanup policy is explicitly changed"
                ),
                "blockers": "",
                "protected_policy_change_required": bool(protected_row.get("policy_change_required_for_deletion") is True),
                "approval_promoted": policy_change_requested,
                "execution_enabled": False,
                "delete_executed": False,
                "external_state_mutated": False,
            }
        )

    approval_rows = [row for row in rows if row["approval_status"] == "approval_required"]
    protected_rows = [row for row in rows if row["approval_status"] == "policy_blocked_not_promoted"]
    protected_policy_change_promoted_rows = [
        row for row in rows if row["operation_class"] == "protected_ligand_heavy_policy_change_delete"
    ]
    blocked_rows = [row for row in rows if row["approval_status"] == "blocked_before_approval"]
    tokens = sorted({_text(row.get("approval_token_required")) for row in approval_rows if _text(row.get("approval_token_required"))})
    status = "cleanup_execution_approval_dossier_ready" if not blockers and approval_rows else "blocked_cleanup_execution_approval_dossier"
    summary = {
        "packet_type": "cleanup_execution_approval_dossier",
        "status": status,
        "source_transition_preflight_json": transition_preflight_path,
        "source_cleanup_snapshot_preflight_json": cleanup_snapshot_preflight_path,
        "source_cleanup_snapshot_artifacts_json": cleanup_snapshot_artifacts_path,
        "source_ligand_cleanup_preflight_json": ligand_cleanup_preflight_path,
        "source_protected_cleanup_review_json": protected_cleanup_review_path,
        "source_protected_cleanup_policy_json": protected_cleanup_policy_path,
        "approval_row_count": len(approval_rows),
        "blocked_approval_row_count": len(blocked_rows),
        "protected_not_promoted_row_count": len(protected_rows),
        "protected_policy_change_promoted_row_count": len(protected_policy_change_promoted_rows),
        "snapshot_backed_approval_row_count": sum(1 for row in approval_rows if row["snapshot_required"] and row["snapshot_present"]),
        "approval_token_count": len(tokens),
        "approval_tokens_required": ",".join(tokens),
        "approval_reclaim_size_gb": round(sum(_float(row.get("size_gb")) for row in approval_rows), 3),
        "protected_payload_size_gb": round(sum(_float(row.get("size_gb")) for row in protected_rows), 3),
        "protected_policy_change_promoted_size_gb": round(
            sum(_float(row.get("size_gb")) for row in protected_policy_change_promoted_rows), 3
        ),
        "snapshot_artifact_count": _int(_summary(cleanup_snapshot_artifacts_packet).get("snapshot_artifact_count")),
        "snapshot_ready_count": _int(_summary(cleanup_snapshot_artifacts_packet).get("snapshot_ready_count")),
        "snapshot_listing_truncated_count": _int(_summary(cleanup_snapshot_artifacts_packet).get("listing_truncated_count")),
        "snapshot_total_entry_count": _int(_summary(cleanup_snapshot_artifacts_packet).get("total_entry_count")),
        "snapshot_total_file_count": _int(_summary(cleanup_snapshot_artifacts_packet).get("total_file_count")),
        "snapshot_set_fingerprint_sha256": _text(_summary(cleanup_snapshot_artifacts_packet).get("snapshot_set_fingerprint_sha256")),
        "snapshot_fingerprint_count": sum(1 for row in approval_rows if _text(row.get("snapshot_fingerprint_sha256"))),
        "snapshot_truncated_approval_row_count": sum(1 for row in approval_rows if row.get("snapshot_listing_truncated") is True),
        "ligand_heavy_candidate_count": _int(ligand_summary.get("existing_candidate_count") or ligand_summary.get("candidate_count")),
        "blocker_count": len(blockers),
        "blockers": sorted(set(blockers)),
        "execution_enabled": False,
        "delete_executed": False,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "Review this dossier and provide only the row-specific approval tokens that should be executed."
            if status == "cleanup_execution_approval_dossier_ready"
            else "Repair source preflights, snapshot evidence, or blocked approval rows before requesting cleanup execution approval."
        ),
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    s = payload["summary"]
    lines = [
        "# Cleanup Execution Approval Dossier",
        "",
        f"- status: `{s['status']}`",
        f"- approval_row_count: `{s['approval_row_count']}`",
        f"- blocked_approval_row_count: `{s['blocked_approval_row_count']}`",
        f"- protected_not_promoted_row_count: `{s['protected_not_promoted_row_count']}`",
        f"- protected_policy_change_promoted_row_count: `{s['protected_policy_change_promoted_row_count']}`",
        f"- snapshot_backed_approval_row_count: `{s['snapshot_backed_approval_row_count']}`",
        f"- snapshot_artifact_count: `{s['snapshot_artifact_count']}`",
        f"- snapshot_ready_count: `{s['snapshot_ready_count']}`",
        f"- snapshot_listing_truncated_count: `{s['snapshot_listing_truncated_count']}`",
        f"- snapshot_total_entry_count: `{s['snapshot_total_entry_count']}`",
        f"- snapshot_set_fingerprint_sha256: `{s['snapshot_set_fingerprint_sha256']}`",
        f"- approval_reclaim_size_gb: `{s['approval_reclaim_size_gb']}`",
        f"- protected_payload_size_gb: `{s['protected_payload_size_gb']}`",
        f"- protected_policy_change_promoted_size_gb: `{s['protected_policy_change_promoted_size_gb']}`",
        f"- approval_tokens_required: `{s['approval_tokens_required']}`",
        f"- execution_enabled: `{s['execution_enabled']}`",
        f"- delete_executed: `{s['delete_executed']}`",
        f"- external_state_mutated: `{s['external_state_mutated']}`",
        "",
        "## Rows",
        "",
        "| approval_status | lane | action | size_gb | candidates | token | snapshot | snapshot_entries | truncated | path |",
        "| --- | --- | --- | ---: | ---: | --- | --- | ---: | --- | --- |",
    ]
    for row in payload["rows"]:
        snapshot = row["snapshot_fingerprint_sha256"][:12] if row["snapshot_fingerprint_sha256"] else ""
        lines.append(
            f"| `{row['approval_status']}` | `{row['lane']}` | `{row['recommended_action']}` | "
            f"`{row['size_gb']}` | `{row['candidate_count']}` | `{row['approval_token_required']}` | "
            f"`{snapshot}` | `{row['snapshot_entry_count']}` | `{row['snapshot_listing_truncated']}` | `{row['path']}` |"
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
    parser = argparse.ArgumentParser(description="Build cleanup execution approval dossier without executing cleanup.")
    parser.add_argument("--transition-preflight-json", default=DEFAULT_TRANSITION_PREFLIGHT_JSON)
    parser.add_argument("--cleanup-snapshot-preflight-json", default=DEFAULT_SNAPSHOT_PREFLIGHT_JSON)
    parser.add_argument("--cleanup-snapshot-artifacts-json", default=DEFAULT_SNAPSHOT_ARTIFACTS_JSON)
    parser.add_argument("--ligand-cleanup-preflight-json", default=DEFAULT_LIGAND_PREFLIGHT_JSON)
    parser.add_argument("--protected-cleanup-review-json", default=DEFAULT_PROTECTED_REVIEW_JSON)
    parser.add_argument("--protected-cleanup-policy-json", default=DEFAULT_PROTECTED_POLICY_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_cleanup_execution_approval_dossier(
        transition_preflight_packet=_read_json_if_present(args.transition_preflight_json),
        cleanup_snapshot_preflight_packet=_read_json_if_present(args.cleanup_snapshot_preflight_json),
        cleanup_snapshot_artifacts_packet=_read_json_if_present(args.cleanup_snapshot_artifacts_json),
        ligand_cleanup_preflight_packet=_read_json_if_present(args.ligand_cleanup_preflight_json),
        protected_cleanup_review_packet=_read_json_if_present(args.protected_cleanup_review_json),
        protected_cleanup_policy_packet=_read_json_if_present(args.protected_cleanup_policy_json),
        transition_preflight_path=args.transition_preflight_json,
        cleanup_snapshot_preflight_path=args.cleanup_snapshot_preflight_json,
        cleanup_snapshot_artifacts_path=args.cleanup_snapshot_artifacts_json,
        ligand_cleanup_preflight_path=args.ligand_cleanup_preflight_json,
        protected_cleanup_review_path=args.protected_cleanup_review_json,
        protected_cleanup_policy_path=args.protected_cleanup_policy_json,
    )
    _write_json(args.out_json, payload)
    write_csv_rows(_resolve(args.out_csv), payload["rows"])
    _write_markdown(args.out_md, payload)


if __name__ == "__main__":
    main()

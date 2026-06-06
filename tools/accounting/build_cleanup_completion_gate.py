#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows
from tools.build_cleanup_execution_approval_gate import DEFAULT_OUT_JSON as DEFAULT_APPROVAL_GATE_JSON
from tools.build_cleanup_execution_completion_evidence import DEFAULT_OUT_JSON as DEFAULT_COMPLETION_EVIDENCE_JSON
from tools.build_ligand_heavy_cleanup_execution_preflight import DEFAULT_OUT_JSON as DEFAULT_LIGAND_PREFLIGHT_JSON
from tools.build_cleanup_postcheck_contract import DEFAULT_OUT_JSON as DEFAULT_POSTCHECK_CONTRACT_JSON
from tools.build_protected_cleanup_policy_decision_gate import DEFAULT_OUT_JSON as DEFAULT_PROTECTED_POLICY_GATE_JSON
from tools.cleanup.build_transition_cleanup_execution_preflight import DEFAULT_OUT_JSON as DEFAULT_TRANSITION_PREFLIGHT_JSON

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT_JSON = "runs/cleanup_completion_gate_current.json"
DEFAULT_OUT_CSV = "runs/cleanup_completion_gate_current.csv"
DEFAULT_OUT_MD = "runs/cleanup_completion_gate_current.md"

CLAIM_BOUNDARY = (
    "Cleanup completion gate only; it audits cleanup authorization, row-specific postcheck readiness, transition cleanup "
    "completion, ligand-heavy cleanup completion, and protected-policy resolution from existing local artifacts. It does "
    "not execute cleanup, delete, move, archive, externalize, upload, commit, push, or mutate external state."
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


def _row(
    *,
    stage: str,
    status: str,
    source_status: str,
    source_artifact: str,
    observed: str,
    required: str,
    reason: str,
) -> dict[str, Any]:
    return {
        "stage": stage,
        "status": status,
        "source_status": source_status,
        "observed": observed,
        "required": required,
        "source_artifact": source_artifact,
        "reason": reason,
        "execution_enabled": False,
        "delete_executed": False,
        "external_state_mutated": False,
    }


def build_cleanup_completion_gate(
    *,
    approval_gate_packet: dict[str, Any],
    postcheck_contract_packet: dict[str, Any],
    transition_cleanup_packet: dict[str, Any],
    ligand_cleanup_packet: dict[str, Any],
    protected_policy_gate_packet: dict[str, Any],
    completion_evidence_packet: dict[str, Any] | None = None,
    approval_gate_path: str = DEFAULT_APPROVAL_GATE_JSON,
    postcheck_contract_path: str = DEFAULT_POSTCHECK_CONTRACT_JSON,
    transition_cleanup_path: str = DEFAULT_TRANSITION_PREFLIGHT_JSON,
    ligand_cleanup_path: str = DEFAULT_LIGAND_PREFLIGHT_JSON,
    protected_policy_gate_path: str = DEFAULT_PROTECTED_POLICY_GATE_JSON,
    completion_evidence_path: str = DEFAULT_COMPLETION_EVIDENCE_JSON,
) -> dict[str, Any]:
    approval = _summary(approval_gate_packet)
    postcheck = _summary(postcheck_contract_packet or {})
    transition = _summary(transition_cleanup_packet)
    ligand = _summary(ligand_cleanup_packet)
    protected = _summary(protected_policy_gate_packet)
    completion_evidence = _summary(completion_evidence_packet or {})
    completion_evidence_ready = (
        _text(completion_evidence.get("status")) == "cleanup_execution_completion_evidence_ready"
        and bool(completion_evidence.get("completion_evidence_ready") is True)
        and _int(completion_evidence.get("blocked_row_count")) == 0
    )

    approval_ready = (
        _text(approval.get("status")) == "cleanup_execution_operator_approval_gate_ready"
        and _int(approval.get("awaiting_operator_approval_row_count")) == 0
        and _int(approval.get("blocked_row_count")) == 0
    )
    postcheck_ready = (
        _text(postcheck.get("status")) == "cleanup_postcheck_contract_ready"
        and bool(postcheck.get("postcheck_contract_ready") is True)
        and _int(postcheck.get("blocked_row_count")) == 0
        and _int(postcheck.get("row_count")) > 0
        and _int(postcheck.get("global_refresh_command_count")) > 0
    )
    transition_complete = (
        _text(transition.get("status")) == "transition_cleanup_execution_complete"
        and bool(transition.get("external_state_mutated") is True)
    ) or (completion_evidence_ready and bool(completion_evidence.get("transition_cleanup_complete") is True))
    ligand_complete = (
        _text(ligand.get("status")) == "ligand_heavy_cleanup_execution_complete"
        and bool(ligand.get("delete_executed") is True)
    ) or (completion_evidence_ready and bool(completion_evidence.get("ligand_heavy_cleanup_complete") is True))
    protected_resolved = (
        _text(protected.get("status")) == "protected_cleanup_policy_decision_gate_ready"
        and bool(protected.get("policy_resolved") is True)
        and _int(protected.get("awaiting_policy_decision_row_count")) == 0
        and _int(protected.get("blocked_row_count")) == 0
        and _int(protected.get("policy_change_requested_row_count")) == 0
    )

    rows = [
        _row(
            stage="cleanup_execution_authorization",
            status="ready" if approval_ready else "approval_required",
            source_status=_text(approval.get("status")) or "missing",
            source_artifact=approval_gate_path,
            observed=(
                f"authorized_row_count={_int(approval.get('authorized_row_count'))};"
                f"awaiting={_int(approval.get('awaiting_operator_approval_row_count'))};"
                f"blocked={_int(approval.get('blocked_row_count'))}"
            ),
            required="cleanup_execution_operator_approval_gate_ready;awaiting=0;blocked=0",
            reason="Cleanup execution cannot complete until row-specific operator decisions are resolved.",
        ),
        _row(
            stage="cleanup_postcheck_contract",
            status="ready" if postcheck_ready else "blocked",
            source_status=_text(postcheck.get("status")) or "missing",
            source_artifact=postcheck_contract_path,
            observed=(
                f"ready={bool(postcheck.get('postcheck_contract_ready') is True)};"
                f"rows={_int(postcheck.get('row_count'))};"
                f"blocked={_int(postcheck.get('blocked_row_count'))};"
                f"global_refresh_commands={_int(postcheck.get('global_refresh_command_count'))}"
            ),
            required="cleanup_postcheck_contract_ready;row_count>0;blocked=0;global_refresh_commands>0",
            reason="Cleanup completion must name the row-specific postcheck evidence and global refresh sequence before completion can be claimed.",
        ),
        _row(
            stage="transition_cleanup_completion",
            status="ready" if transition_complete else "blocked",
            source_status=(
                _text(completion_evidence.get("status"))
                if completion_evidence_ready and bool(completion_evidence.get("transition_cleanup_complete") is True)
                else _text(transition.get("status")) or "missing"
            ),
            source_artifact=(
                completion_evidence_path
                if completion_evidence_ready and bool(completion_evidence.get("transition_cleanup_complete") is True)
                else transition_cleanup_path
            ),
            observed=(
                f"completion_evidence_ready={completion_evidence_ready};external_state_mutated={bool(completion_evidence.get('external_state_mutated') is True)}"
                if completion_evidence_ready and bool(completion_evidence.get("transition_cleanup_complete") is True)
                else f"external_state_mutated={bool(transition.get('external_state_mutated') is True)}"
            ),
            required="transition_cleanup_execution_complete;external_state_mutated=true",
            reason="CASP17/transition cleanup must have explicit completion evidence after approved archive/externalize/delete work.",
        ),
        _row(
            stage="ligand_heavy_cleanup_completion",
            status="ready" if ligand_complete else "blocked",
            source_status=(
                _text(completion_evidence.get("status"))
                if completion_evidence_ready and bool(completion_evidence.get("ligand_heavy_cleanup_complete") is True)
                else _text(ligand.get("status")) or "missing"
            ),
            source_artifact=(
                completion_evidence_path
                if completion_evidence_ready and bool(completion_evidence.get("ligand_heavy_cleanup_complete") is True)
                else ligand_cleanup_path
            ),
            observed=(
                f"completion_evidence_ready={completion_evidence_ready};deleted_count={_int(completion_evidence.get('ligand_deleted_count'))};deleted_bytes={_int(completion_evidence.get('ligand_deleted_bytes'))}"
                if completion_evidence_ready and bool(completion_evidence.get("ligand_heavy_cleanup_complete") is True)
                else f"delete_executed={bool(ligand.get('delete_executed') is True)};candidate_size_gb={round(_float(ligand.get('candidate_size_gb')), 3)}"
            ),
            required="ligand_heavy_cleanup_execution_complete;delete_executed=true",
            reason="Stale ligand-heavy trajectory payload cleanup must have explicit post-execution evidence.",
        ),
        _row(
            stage="protected_cleanup_policy_resolution",
            status="ready" if protected_resolved else "policy_decision_required",
            source_status=_text(protected.get("status")) or "missing",
            source_artifact=protected_policy_gate_path,
            observed=(
                f"policy_resolved={bool(protected.get('policy_resolved') is True)};"
                f"awaiting={_int(protected.get('awaiting_policy_decision_row_count'))};"
                f"blocked={_int(protected.get('blocked_row_count'))}"
            ),
            required="protected_cleanup_policy_decision_gate_ready;policy_resolved=true",
            reason="Protected heavy payload rows must be explicitly kept or handled through a separate policy-change path.",
        ),
    ]

    blocked_stage_count = sum(1 for row in rows if row["status"] in {"blocked", "approval_required", "policy_decision_required"})
    cleanup_complete = approval_ready and transition_complete and ligand_complete and protected_resolved
    cleanup_complete = cleanup_complete and postcheck_ready
    summary = {
        "packet_type": "cleanup_completion_gate",
        "status": "cleanup_completion_gate_ready" if cleanup_complete else "blocked_cleanup_completion_gate",
        "cleanup_complete": cleanup_complete,
        "stage_count": len(rows),
        "blocked_stage_count": blocked_stage_count,
        "approval_ready": approval_ready,
        "approval_authorized_row_count": _int(approval.get("authorized_row_count")),
        "approval_awaiting_operator_approval_row_count": _int(approval.get("awaiting_operator_approval_row_count")),
        "approval_blocked_row_count": _int(approval.get("blocked_row_count")),
        "postcheck_contract_ready": postcheck_ready,
        "postcheck_row_count": _int(postcheck.get("row_count")),
        "postcheck_blocked_row_count": _int(postcheck.get("blocked_row_count")),
        "postcheck_global_refresh_command_count": _int(postcheck.get("global_refresh_command_count")),
        "completion_evidence_ready": completion_evidence_ready,
        "completion_evidence_status": _text(completion_evidence.get("status")),
        "completion_evidence_blocked_row_count": _int(completion_evidence.get("blocked_row_count")),
        "transition_cleanup_complete": transition_complete,
        "transition_approval_gated_reclaim_size_gb": round(_float(transition.get("approval_gated_reclaim_size_gb")), 3),
        "ligand_heavy_cleanup_complete": ligand_complete,
        "ligand_heavy_candidate_size_gb": round(_float(ligand.get("candidate_size_gb")), 3),
        "protected_policy_resolved": protected_resolved,
        "authorized_reclaim_size_gb": round(_float(approval.get("authorized_reclaim_size_gb")), 3),
        "total_reclaim_size_gb": round(_float(approval.get("total_reclaim_size_gb")), 3),
        "protected_payload_size_gb": round(_float(protected.get("protected_payload_size_gb") or approval.get("protected_payload_size_gb")), 3),
        "execution_enabled": False,
        "delete_executed": False,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "Cleanup completion evidence is clear."
            if cleanup_complete
            else "Resolve cleanup approval decisions, execute only approved cleanup rows, and refresh post-execution completion evidence."
        ),
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    s = payload["summary"]
    lines = [
        "# Cleanup Completion Gate",
        "",
        f"- status: `{s['status']}`",
        f"- cleanup_complete: `{s['cleanup_complete']}`",
        f"- blocked_stage_count: `{s['blocked_stage_count']}`",
        f"- approval_ready: `{s['approval_ready']}`",
        f"- approval_authorized_row_count: `{s['approval_authorized_row_count']}`",
        f"- approval_awaiting_operator_approval_row_count: `{s['approval_awaiting_operator_approval_row_count']}`",
        f"- approval_blocked_row_count: `{s['approval_blocked_row_count']}`",
        f"- postcheck_contract_ready: `{s['postcheck_contract_ready']}`",
        f"- postcheck_row_count: `{s['postcheck_row_count']}`",
        f"- postcheck_blocked_row_count: `{s['postcheck_blocked_row_count']}`",
        f"- postcheck_global_refresh_command_count: `{s['postcheck_global_refresh_command_count']}`",
        f"- completion_evidence_ready: `{s['completion_evidence_ready']}`",
        f"- completion_evidence_status: `{s['completion_evidence_status']}`",
        f"- completion_evidence_blocked_row_count: `{s['completion_evidence_blocked_row_count']}`",
        f"- transition_cleanup_complete: `{s['transition_cleanup_complete']}`",
        f"- transition_approval_gated_reclaim_size_gb: `{s['transition_approval_gated_reclaim_size_gb']}`",
        f"- ligand_heavy_cleanup_complete: `{s['ligand_heavy_cleanup_complete']}`",
        f"- ligand_heavy_candidate_size_gb: `{s['ligand_heavy_candidate_size_gb']}`",
        f"- protected_policy_resolved: `{s['protected_policy_resolved']}`",
        f"- authorized_reclaim_size_gb: `{s['authorized_reclaim_size_gb']}`",
        f"- total_reclaim_size_gb: `{s['total_reclaim_size_gb']}`",
        f"- protected_payload_size_gb: `{s['protected_payload_size_gb']}`",
        f"- delete_executed: `{s['delete_executed']}`",
        f"- external_state_mutated: `{s['external_state_mutated']}`",
        "",
        "## Stages",
        "",
        "| stage | status | source_status | observed | required | source |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['stage']}` | `{row['status']}` | `{row['source_status']}` | "
            f"`{row['observed']}` | `{row['required']}` | `{row['source_artifact']}` |"
        )
    lines.extend(["", "## Claim Boundary", "", s["claim_boundary"], "", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a cleanup completion gate without executing cleanup.")
    parser.add_argument("--approval-gate-json", default=DEFAULT_APPROVAL_GATE_JSON)
    parser.add_argument("--postcheck-contract-json", default=DEFAULT_POSTCHECK_CONTRACT_JSON)
    parser.add_argument("--transition-cleanup-json", default=DEFAULT_TRANSITION_PREFLIGHT_JSON)
    parser.add_argument("--ligand-cleanup-json", default=DEFAULT_LIGAND_PREFLIGHT_JSON)
    parser.add_argument("--protected-policy-gate-json", default=DEFAULT_PROTECTED_POLICY_GATE_JSON)
    parser.add_argument("--completion-evidence-json", default=DEFAULT_COMPLETION_EVIDENCE_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_cleanup_completion_gate(
        approval_gate_packet=_read_json_if_present(args.approval_gate_json),
        postcheck_contract_packet=_read_json_if_present(args.postcheck_contract_json),
        transition_cleanup_packet=_read_json_if_present(args.transition_cleanup_json),
        ligand_cleanup_packet=_read_json_if_present(args.ligand_cleanup_json),
        protected_policy_gate_packet=_read_json_if_present(args.protected_policy_gate_json),
        completion_evidence_packet=_read_json_if_present(args.completion_evidence_json),
        approval_gate_path=args.approval_gate_json,
        postcheck_contract_path=args.postcheck_contract_json,
        transition_cleanup_path=args.transition_cleanup_json,
        ligand_cleanup_path=args.ligand_cleanup_json,
        protected_policy_gate_path=args.protected_policy_gate_json,
        completion_evidence_path=args.completion_evidence_json,
    )
    _write_json(args.out_json, payload)
    write_csv_rows(_resolve(args.out_csv), payload["rows"])
    _write_markdown(args.out_md, payload)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import build_casp17_competitive_floor_target_identity_clearance_intake_staging_plan as intake_staging
from tools import build_casp17_competitive_floor_target_identity_clearance_action_board as action_board
from tools import build_casp17_competitive_floor_target_identity_clearance_action_bundle as action_bundle
from tools import build_casp17_competitive_floor_target_identity_clearance_operator_intake as operator_intake
from tools import build_casp17_competitive_floor_target_identity_clearance_promotion_plan as promotion_plan
from tools import build_casp17_competitive_floor_target_identity_clearance_workorder_audit as workorder_audit
from tools import build_casp17_workbench_index as workbench_index
from tools import sync_casp17_competitive_floor_target_identity_clearance_candidate_intake as candidate_intake_sync
from tools import sync_casp17_competitive_floor_target_identity_clearance_manifest_stub as manifest_sync


DEFAULT_WORKORDER_JSON = "casp17/casp17_competitive_floor_target_identity_clearance_workorder_current.json"
DEFAULT_OPERATOR_INTAKE_CSV = "casp17/casp17_competitive_floor_target_identity_clearance_operator_intake_current.csv"
DEFAULT_OPERATOR_INTAKE_JSON = "casp17/casp17_competitive_floor_target_identity_clearance_operator_intake_current.json"
DEFAULT_OPERATOR_INTAKE_REPORT_CSV = (
    "casp17/casp17_competitive_floor_target_identity_clearance_operator_intake_report_current.csv"
)
DEFAULT_OPERATOR_INTAKE_MD = "casp17/COMPETITIVE_FLOOR_TARGET_IDENTITY_CLEARANCE_OPERATOR_INTAKE.md"
DEFAULT_MANIFEST_SYNC_JSON = "casp17/casp17_competitive_floor_target_identity_clearance_manifest_sync_current.json"
DEFAULT_MANIFEST_SYNC_CSV = "casp17/casp17_competitive_floor_target_identity_clearance_manifest_sync_current.csv"
DEFAULT_MANIFEST_SYNC_MD = "casp17/COMPETITIVE_FLOOR_TARGET_IDENTITY_CLEARANCE_MANIFEST_SYNC.md"
DEFAULT_AUDIT_JSON = "casp17/casp17_competitive_floor_target_identity_clearance_workorder_audit_current.json"
DEFAULT_AUDIT_CSV = "casp17/casp17_competitive_floor_target_identity_clearance_workorder_audit_current.csv"
DEFAULT_AUDIT_MD = "casp17/COMPETITIVE_FLOOR_TARGET_IDENTITY_CLEARANCE_WORKORDER_AUDIT.md"
DEFAULT_ACTION_BOARD_JSON = "casp17/casp17_competitive_floor_target_identity_clearance_action_board_current.json"
DEFAULT_ACTION_BOARD_CSV = "casp17/casp17_competitive_floor_target_identity_clearance_action_board_current.csv"
DEFAULT_ACTION_BOARD_MD = "casp17/COMPETITIVE_FLOOR_TARGET_IDENTITY_CLEARANCE_ACTION_BOARD.md"
DEFAULT_ACTION_BUNDLE_DIR = "casp17/competitive_floor_target_identity_clearance_action_bundle"
DEFAULT_ACTION_BUNDLE_JSON = "casp17/casp17_competitive_floor_target_identity_clearance_action_bundle_current.json"
DEFAULT_ACTION_BUNDLE_CSV = "casp17/casp17_competitive_floor_target_identity_clearance_action_bundle_current.csv"
DEFAULT_ACTION_BUNDLE_MD = "casp17/COMPETITIVE_FLOOR_TARGET_IDENTITY_CLEARANCE_ACTION_BUNDLE.md"
DEFAULT_CURRENT_TARGET_CSV = "casp17/casp17_target_model_folders_current.csv"
DEFAULT_PROMOTED_MANIFEST_CSV = (
    "casp17/casp17_competitive_floor_target_identity_clearance_promoted_manifest_candidate_current.csv"
)
DEFAULT_PROMOTION_JSON = "casp17/casp17_competitive_floor_target_identity_clearance_promotion_plan_current.json"
DEFAULT_PROMOTION_CSV = "casp17/casp17_competitive_floor_target_identity_clearance_promotion_plan_current.csv"
DEFAULT_PROMOTION_MD = "casp17/COMPETITIVE_FLOOR_TARGET_IDENTITY_CLEARANCE_PROMOTION_PLAN.md"
DEFAULT_IDENTITY_INTAKE_CSV = "casp17/casp17_competitive_floor_identity_intake_bundle_current.csv"
DEFAULT_CANDIDATE_INTAKE_CSV = (
    "casp17/casp17_competitive_floor_identity_intake_bundle_candidate_from_clearance_current.csv"
)
DEFAULT_CANDIDATE_INTAKE_SYNC_JSON = (
    "casp17/casp17_competitive_floor_target_identity_clearance_candidate_intake_sync_current.json"
)
DEFAULT_CANDIDATE_INTAKE_SYNC_CSV = (
    "casp17/casp17_competitive_floor_target_identity_clearance_candidate_intake_sync_current.csv"
)
DEFAULT_CANDIDATE_INTAKE_SYNC_MD = "casp17/COMPETITIVE_FLOOR_TARGET_IDENTITY_CLEARANCE_CANDIDATE_INTAKE_SYNC.md"
DEFAULT_INTAKE_STAGING_JSON = (
    "casp17/casp17_competitive_floor_target_identity_clearance_intake_staging_plan_current.json"
)
DEFAULT_INTAKE_STAGING_CSV = (
    "casp17/casp17_competitive_floor_target_identity_clearance_intake_staging_plan_current.csv"
)
DEFAULT_INTAKE_STAGING_MD = "casp17/COMPETITIVE_FLOOR_TARGET_IDENTITY_CLEARANCE_INTAKE_STAGING_PLAN.md"
DEFAULT_WORKBENCH_JSON = "casp17/casp17_workbench_index_current.json"
DEFAULT_WORKBENCH_CSV = "casp17/casp17_workbench_index_current.csv"
DEFAULT_WORKBENCH_MD = "casp17/WORKBENCH.md"
DEFAULT_OUT_JSON = "casp17/casp17_competitive_floor_target_identity_clearance_cycle_current.json"
DEFAULT_OUT_CSV = "casp17/casp17_competitive_floor_target_identity_clearance_cycle_current.csv"
DEFAULT_OUT_MD = "casp17/COMPETITIVE_FLOOR_TARGET_IDENTITY_CLEARANCE_CYCLE.md"

CYCLE_COLUMNS = [
    "stage",
    "status",
    "path",
    "ready_count",
    "awaiting_count",
    "blocked_count",
    "total_count",
    "next_action",
]
READY_STATUSES = {
    "pass",
    "ready",
    "ready_for_operator_intake_review",
    "ready_for_operator_manifest_import",
    "ready_for_operator_fill",
    "ready_for_manifest_sync_apply",
    "synced",
    "applied",
}
CLAIM_BOUNDARY = (
    "Local CASP17 competitive-floor target identity clearance cycle only. It chains operator intake validation, "
    "manifest-stub sync, workorder audit, action-board expansion, action-bundle materialization, audited manifest promotion, "
    "clearance-to-intake staging, and workbench refresh. "
    "It does not rebuild "
    "workorders, fetch native structures, clear no-leak provenance, choose targets, score native accuracy, run "
    "predictors, mutate live identity intake files, or submit to CASP. Native/provenance workorders are modified "
    "only when --apply-operator-intake is explicitly provided; manifest stubs are modified only when "
    "--apply-manifest-sync is explicitly provided; live identity intake is modified only when "
    "--apply-candidate-intake is explicitly provided."
)


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _artifact(path_like: str | Path) -> str:
    path = _resolve(path_like).resolve()
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _int(value: Any) -> int:
    try:
        return int(float(str(value).strip()))
    except (TypeError, ValueError):
        return 0


def _summary(payload: dict[str, Any]) -> dict[str, Any]:
    summary = payload.get("summary")
    return summary if isinstance(summary, dict) else {}


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_csv(path_like: str | Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _stage_row(
    stage: str,
    status: str,
    path_like: str | Path,
    *,
    ready: int,
    awaiting: int,
    blocked: int,
    total: int,
    next_action: str,
) -> dict[str, Any]:
    return {
        "stage": stage,
        "status": status or "missing",
        "path": _artifact(path_like),
        "ready_count": ready,
        "awaiting_count": awaiting,
        "blocked_count": blocked,
        "total_count": total,
        "next_action": next_action,
    }


def _run_operator_intake(args: argparse.Namespace) -> dict[str, Any]:
    argv = [
        "--workorder-json",
        args.workorder_json,
        "--intake-csv",
        args.operator_intake_csv,
        "--out-json",
        args.operator_intake_json,
        "--out-csv",
        args.operator_intake_report_csv,
        "--out-md",
        args.operator_intake_md,
    ]
    if args.apply_operator_intake:
        argv.append("--apply")
    intake_args = operator_intake.parse_args(argv)
    payload = operator_intake.build_payload(intake_args)
    operator_intake.write_outputs(intake_args, payload)
    return payload


def _run_manifest_sync(args: argparse.Namespace) -> dict[str, Any]:
    argv = [
        "--workorder-json",
        args.workorder_json,
        "--out-json",
        args.manifest_sync_json,
        "--out-csv",
        args.manifest_sync_csv,
        "--out-md",
        args.manifest_sync_md,
    ]
    if args.apply_manifest_sync:
        argv.append("--apply")
    sync_args = manifest_sync.parse_args(argv)
    payload = manifest_sync.build_payload(sync_args)
    manifest_sync.write_outputs(sync_args, payload)
    return payload


def _run_workorder_audit(args: argparse.Namespace) -> dict[str, Any]:
    audit_args = workorder_audit.parse_args(
        [
            "--workorder-json",
            args.workorder_json,
            "--out-json",
            args.audit_json,
            "--out-csv",
            args.audit_csv,
            "--out-md",
            args.audit_md,
        ]
    )
    payload = workorder_audit.build_payload(audit_args)
    workorder_audit.write_outputs(audit_args, payload)
    return payload


def _run_action_board(args: argparse.Namespace) -> dict[str, Any]:
    action_args = action_board.parse_args(
        [
            "--audit-json",
            args.audit_json,
            "--out-json",
            args.action_board_json,
            "--out-csv",
            args.action_board_csv,
            "--out-md",
            args.action_board_md,
        ]
    )
    payload = action_board.build_payload(action_args)
    action_board.write_outputs(action_args, payload)
    return payload


def _run_action_bundle(args: argparse.Namespace) -> dict[str, Any]:
    bundle_args = action_bundle.parse_args(
        [
            "--action-board-json",
            args.action_board_json,
            "--out-dir",
            args.action_bundle_dir,
            "--out-json",
            args.action_bundle_json,
            "--out-csv",
            args.action_bundle_csv,
            "--out-md",
            args.action_bundle_md,
        ]
    )
    payload = action_bundle.build_payload(bundle_args)
    action_bundle.write_outputs(bundle_args, payload)
    return payload


def _run_promotion_plan(args: argparse.Namespace) -> dict[str, Any]:
    promotion_args = promotion_plan.parse_args(
        [
            "--audit-json",
            args.audit_json,
            "--current-target-csv",
            args.current_target_csv,
            "--out-manifest-csv",
            args.promoted_manifest_csv,
            "--out-json",
            args.promotion_json,
            "--out-csv",
            args.promotion_csv,
            "--out-md",
            args.promotion_md,
        ]
    )
    payload = promotion_plan.build_payload(promotion_args)
    promotion_plan.write_outputs(promotion_args, payload)
    return payload


def _run_intake_staging(args: argparse.Namespace) -> dict[str, Any]:
    staging_args = intake_staging.parse_args(
        [
            "--promoted-manifest-csv",
            args.promoted_manifest_csv,
            "--promotion-plan-json",
            args.promotion_json,
            "--identity-intake-csv",
            args.identity_intake_csv,
            "--current-target-csv",
            args.current_target_csv,
            "--out-candidate-intake-csv",
            args.candidate_intake_csv,
            "--out-json",
            args.intake_staging_json,
            "--out-csv",
            args.intake_staging_csv,
            "--out-md",
            args.intake_staging_md,
        ]
    )
    payload = intake_staging.build_payload(staging_args)
    intake_staging.write_outputs(staging_args, payload)
    return payload


def _run_candidate_intake_sync(args: argparse.Namespace) -> dict[str, Any]:
    argv = [
        "--candidate-intake-csv",
        args.candidate_intake_csv,
        "--live-intake-csv",
        args.identity_intake_csv,
        "--current-target-csv",
        args.current_target_csv,
        "--out-json",
        args.candidate_intake_sync_json,
        "--out-csv",
        args.candidate_intake_sync_csv,
        "--out-md",
        args.candidate_intake_sync_md,
    ]
    if args.apply_candidate_intake:
        argv.append("--apply")
    sync_args = candidate_intake_sync.parse_args(argv)
    payload = candidate_intake_sync.build_payload(sync_args)
    candidate_intake_sync.write_outputs(sync_args, payload)
    return payload


def _run_workbench(args: argparse.Namespace) -> dict[str, Any]:
    workbench_args = workbench_index.parse_args(
        [
            "--competitive-target-identity-clearance-operator-intake-json",
            args.operator_intake_json,
            "--competitive-target-identity-clearance-manifest-sync-json",
            args.manifest_sync_json,
            "--competitive-target-identity-clearance-workorder-audit-json",
            args.audit_json,
            "--competitive-target-identity-clearance-action-board-json",
            args.action_board_json,
            "--competitive-target-identity-clearance-action-bundle-json",
            args.action_bundle_json,
            "--competitive-target-identity-clearance-promotion-plan-json",
            args.promotion_json,
            "--competitive-target-identity-clearance-intake-staging-json",
            args.intake_staging_json,
            "--competitive-target-identity-clearance-candidate-intake-sync-json",
            args.candidate_intake_sync_json,
            "--competitive-target-identity-clearance-cycle-json",
            args.out_json,
            "--out-json",
            args.workbench_json,
            "--out-csv",
            args.workbench_csv,
            "--out-md",
            args.workbench_md,
        ]
    )
    payload = workbench_index.build_payload(workbench_args)
    workbench_index._write_json(workbench_args.out_json, payload)
    workbench_index._write_csv(workbench_args.out_csv, payload["rows"])
    workbench_index._write_md(workbench_args.out_md, payload)
    return payload


def _cycle_status(args: argparse.Namespace, summaries: dict[str, dict[str, Any]]) -> str:
    operator_summary = summaries["operator_intake"]
    sync_summary = summaries["manifest_sync"]
    audit_summary = summaries["audit"]
    promotion_summary = summaries["promotion"]
    staging_summary = summaries["intake_staging"]
    candidate_sync_summary = summaries["candidate_intake_sync"]
    if _int(operator_summary.get("ready_to_apply_count")) and not args.apply_operator_intake:
        return "ready_for_operator_intake_apply"
    if _int(operator_summary.get("awaiting_input_count")):
        return "awaiting_operator_intake"
    if _int(operator_summary.get("blocked_count")):
        return "blocked_operator_intake"
    if _int(sync_summary.get("ready_to_sync_count")) and not args.apply_manifest_sync:
        return "ready_for_manifest_sync_apply"
    if _int(sync_summary.get("awaiting_provenance_count")):
        return "awaiting_provenance"
    if _int(sync_summary.get("blocked_count")):
        return "blocked_manifest_sync"
    if _int(audit_summary.get("audit_blocked_count")):
        return "awaiting_clearance_audit"
    if _int(staging_summary.get("staged_identity_count")):
        if _int(candidate_sync_summary.get("ready_to_apply_count")) and not args.apply_candidate_intake:
            return "ready_for_candidate_intake_apply"
        if _int(candidate_sync_summary.get("applied_row_count")):
            return "candidate_intake_applied"
        return "ready_for_operator_intake_review"
    if _int(candidate_sync_summary.get("blocked_count")):
        return "blocked_candidate_intake_sync"
    if _text(promotion_summary.get("clearance_promotion_status")) == "blocked_by_audit":
        return "blocked_by_audit"
    if _text(staging_summary.get("clearance_intake_staging_status")) == "waiting_on_promoted_manifest":
        return "waiting_on_promoted_manifest"
    return (
        _text(staging_summary.get("clearance_intake_staging_status"))
        or _text(promotion_summary.get("clearance_promotion_status"))
        or _text(audit_summary.get("clearance_workorder_audit_status"))
        or _text(sync_summary.get("clearance_manifest_sync_status"))
        or "missing"
    )


def _first_next_action(args: argparse.Namespace, summaries: dict[str, dict[str, Any]]) -> str:
    operator_summary = summaries["operator_intake"]
    if _int(operator_summary.get("ready_to_apply_count")) and not args.apply_operator_intake:
        return "review operator intake report, then rerun this cycle with --apply-operator-intake"
    if _int(operator_summary.get("awaiting_input_count")) or _int(operator_summary.get("blocked_count")):
        return _text(operator_summary.get("first_open_next_action"))
    sync_summary = summaries["manifest_sync"]
    if _int(sync_summary.get("ready_to_sync_count")) and not args.apply_manifest_sync:
        return "review manifest sync rows, then rerun this cycle with --apply-manifest-sync"
    if _int(sync_summary.get("awaiting_provenance_count")):
        action_summary = summaries.get("action_board", {})
        bundle_summary = summaries.get("action_bundle", {})
        return (
            _text(bundle_summary.get("first_open_action_md"))
            or _text(action_summary.get("first_open_next_action"))
            or _text(sync_summary.get("first_open_next_action"))
        )
    audit_summary = summaries["audit"]
    if _int(audit_summary.get("audit_blocked_count")):
        return _text(audit_summary.get("first_blocked_next_action"))
    staging_summary = summaries["intake_staging"]
    if _int(staging_summary.get("staged_identity_count")):
        if _int(summaries["candidate_intake_sync"].get("ready_to_apply_count")) and not args.apply_candidate_intake:
            return "review candidate intake sync rows, then rerun this cycle with --apply-candidate-intake"
        if _int(summaries["candidate_intake_sync"].get("applied_row_count")):
            return "rerun identity intake sync and identity cycle"
        return "review the candidate intake CSV before copying rows into the live identity intake bundle"
    return (
        _text(staging_summary.get("first_open_next_action"))
        or _text(summaries["promotion"].get("first_open_next_action"))
        or "review target identity clearance cycle outputs"
    )


def _build_cycle_payload(
    args: argparse.Namespace,
    payloads: dict[str, dict[str, Any]],
    *,
    workbench_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    summaries = {name: _summary(payload) for name, payload in payloads.items()}
    workbench_summary = _summary(workbench_payload or {})
    rows = [
        _stage_row(
            "operator_intake",
            _text(summaries["operator_intake"].get("operator_intake_status")),
            args.operator_intake_json,
            ready=_int(summaries["operator_intake"].get("ready_to_apply_count"))
            + _int(summaries["operator_intake"].get("applied_count")),
            awaiting=_int(summaries["operator_intake"].get("awaiting_input_count")),
            blocked=_int(summaries["operator_intake"].get("blocked_count")),
            total=_int(summaries["operator_intake"].get("row_count")),
            next_action=_text(summaries["operator_intake"].get("first_open_next_action")),
        ),
        _stage_row(
            "manifest_sync",
            _text(summaries["manifest_sync"].get("clearance_manifest_sync_status")),
            args.manifest_sync_json,
            ready=_int(summaries["manifest_sync"].get("ready_to_sync_count"))
            + _int(summaries["manifest_sync"].get("synced_count")),
            awaiting=_int(summaries["manifest_sync"].get("awaiting_provenance_count")),
            blocked=_int(summaries["manifest_sync"].get("blocked_count")),
            total=_int(summaries["manifest_sync"].get("sync_row_count")),
            next_action=_text(summaries["manifest_sync"].get("first_open_next_action")),
        ),
        _stage_row(
            "workorder_audit",
            _text(summaries["audit"].get("clearance_workorder_audit_status")),
            args.audit_json,
            ready=_int(summaries["audit"].get("audit_pass_count")),
            awaiting=0,
            blocked=_int(summaries["audit"].get("audit_blocked_count")),
            total=_int(summaries["audit"].get("audit_target_count")),
            next_action=_text(summaries["audit"].get("first_blocked_next_action")),
        ),
        _stage_row(
            "action_board",
            _text(summaries["action_board"].get("action_board_status")),
            args.action_board_json,
            ready=0,
            awaiting=0,
            blocked=_int(summaries["action_board"].get("open_action_count")),
            total=_int(summaries["action_board"].get("action_count")),
            next_action=_text(summaries["action_board"].get("first_open_next_action")),
        ),
        _stage_row(
            "action_bundle",
            _text(summaries["action_bundle"].get("action_bundle_status")),
            args.action_bundle_json,
            ready=max(
                0,
                _int(summaries["action_bundle"].get("action_count"))
                - _int(summaries["action_bundle"].get("open_action_count")),
            ),
            awaiting=0,
            blocked=_int(summaries["action_bundle"].get("open_action_count")),
            total=_int(summaries["action_bundle"].get("action_count")),
            next_action=_text(summaries["action_bundle"].get("first_open_action_md")),
        ),
        _stage_row(
            "promotion_plan",
            _text(summaries["promotion"].get("clearance_promotion_status")),
            args.promotion_json,
            ready=_int(summaries["promotion"].get("ready_for_operator_manifest_import_count")),
            awaiting=0,
            blocked=_int(summaries["promotion"].get("blocked_count")),
            total=_int(summaries["promotion"].get("promotion_row_count")),
            next_action=_text(summaries["promotion"].get("first_open_next_action")),
        ),
        _stage_row(
            "intake_staging",
            _text(summaries["intake_staging"].get("clearance_intake_staging_status")),
            args.intake_staging_json,
            ready=_int(summaries["intake_staging"].get("staged_identity_count")),
            awaiting=max(
                0,
                _int(summaries["intake_staging"].get("promoted_manifest_row_count"))
                - _int(summaries["intake_staging"].get("staged_identity_count"))
                - _int(summaries["intake_staging"].get("blocked_assignment_count")),
            ),
            blocked=_int(summaries["intake_staging"].get("blocked_assignment_count")),
            total=_int(summaries["intake_staging"].get("promoted_manifest_row_count")),
            next_action=_text(summaries["intake_staging"].get("first_open_next_action")),
        ),
        _stage_row(
            "candidate_intake_sync",
            _text(summaries["candidate_intake_sync"].get("candidate_intake_sync_status")),
            args.candidate_intake_sync_json,
            ready=_int(summaries["candidate_intake_sync"].get("ready_to_apply_count"))
            + _int(summaries["candidate_intake_sync"].get("applied_row_count")),
            awaiting=_int(summaries["candidate_intake_sync"].get("waiting_on_staged_identity_count")),
            blocked=_int(summaries["candidate_intake_sync"].get("blocked_count")),
            total=_int(summaries["candidate_intake_sync"].get("sync_row_count")),
            next_action=_text(summaries["candidate_intake_sync"].get("first_open_next_action")),
        ),
    ]
    if workbench_payload is not None:
        rows.append(
            _stage_row(
                "workbench",
                _text(workbench_summary.get("workbench_status")),
                args.workbench_json,
                ready=_int(workbench_summary.get("target_model_ready_count")),
                awaiting=0,
                blocked=max(
                    0,
                    _int(workbench_summary.get("target_model_count"))
                    - _int(workbench_summary.get("target_model_ready_count")),
                ),
                total=_int(workbench_summary.get("target_model_count")),
                next_action=_text(workbench_summary.get("first_operator_fill_action")),
            )
        )
    ready_stage_count = sum(1 for row in rows if _text(row.get("status")) in READY_STATUSES)
    summary = {
        "packet_type": "casp17_competitive_floor_target_identity_clearance_cycle",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "clearance_cycle_status": _cycle_status(args, summaries),
        "apply_operator_intake": bool(args.apply_operator_intake),
        "apply_manifest_sync": bool(args.apply_manifest_sync),
        "apply_candidate_intake": bool(args.apply_candidate_intake),
        "stage_count": len(rows),
        "ready_stage_count": ready_stage_count,
        "blocked_stage_count": len(rows) - ready_stage_count,
        "operator_intake_status": _text(summaries["operator_intake"].get("operator_intake_status")),
        "operator_intake_ready_to_apply_count": _int(summaries["operator_intake"].get("ready_to_apply_count")),
        "operator_intake_awaiting_input_count": _int(summaries["operator_intake"].get("awaiting_input_count")),
        "operator_intake_blocked_count": _int(summaries["operator_intake"].get("blocked_count")),
        "operator_intake_applied_count": _int(summaries["operator_intake"].get("applied_count")),
        "operator_intake_native_copied_count": _int(summaries["operator_intake"].get("native_copied_count")),
        "operator_intake_provenance_patched_count": _int(
            summaries["operator_intake"].get("provenance_patched_count")
        ),
        "manifest_sync_status": _text(summaries["manifest_sync"].get("clearance_manifest_sync_status")),
        "manifest_sync_ready_to_sync_count": _int(summaries["manifest_sync"].get("ready_to_sync_count")),
        "manifest_sync_awaiting_provenance_count": _int(summaries["manifest_sync"].get("awaiting_provenance_count")),
        "manifest_sync_synced_count": _int(summaries["manifest_sync"].get("synced_count")),
        "manifest_sync_applied_field_count": _int(summaries["manifest_sync"].get("applied_field_count")),
        "audit_status": _text(summaries["audit"].get("clearance_workorder_audit_status")),
        "audit_pass_count": _int(summaries["audit"].get("audit_pass_count")),
        "audit_blocked_count": _int(summaries["audit"].get("audit_blocked_count")),
        "action_board_status": _text(summaries["action_board"].get("action_board_status")),
        "action_board_action_count": _int(summaries["action_board"].get("action_count")),
        "action_board_open_action_count": _int(summaries["action_board"].get("open_action_count")),
        "action_bundle_status": _text(summaries["action_bundle"].get("action_bundle_status")),
        "action_bundle_action_count": _int(summaries["action_bundle"].get("action_count")),
        "action_bundle_open_action_count": _int(summaries["action_bundle"].get("open_action_count")),
        "action_bundle_file_count": _int(summaries["action_bundle"].get("bundle_file_count")),
        "action_bundle_folder_count": _int(summaries["action_bundle"].get("action_folder_count")),
        "promotion_status": _text(summaries["promotion"].get("clearance_promotion_status")),
        "promoted_manifest_count": _int(summaries["promotion"].get("promoted_manifest_count")),
        "promotion_blocked_count": _int(summaries["promotion"].get("blocked_count")),
        "intake_staging_status": _text(summaries["intake_staging"].get("clearance_intake_staging_status")),
        "staged_identity_count": _int(summaries["intake_staging"].get("staged_identity_count")),
        "staging_blocked_count": _int(summaries["intake_staging"].get("blocked_assignment_count")),
        "candidate_intake_sync_status": _text(
            summaries["candidate_intake_sync"].get("candidate_intake_sync_status")
        ),
        "candidate_intake_ready_to_apply_count": _int(
            summaries["candidate_intake_sync"].get("ready_to_apply_count")
        ),
        "candidate_intake_waiting_count": _int(
            summaries["candidate_intake_sync"].get("waiting_on_staged_identity_count")
        ),
        "candidate_intake_applied_count": _int(summaries["candidate_intake_sync"].get("applied_row_count")),
        "workbench_status": _text(workbench_summary.get("workbench_status")),
        "first_next_action": _first_next_action(args, summaries),
        "claim_boundary": CLAIM_BOUNDARY,
    }
    return {"summary": summary, "rows": rows}


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Competitive-Floor Target Identity Clearance Cycle",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- clearance_cycle_status: `{summary['clearance_cycle_status']}`",
        f"- apply_operator_intake/apply_manifest_sync/apply_candidate_intake: `{summary['apply_operator_intake']}/{summary['apply_manifest_sync']}/{summary['apply_candidate_intake']}`",
        f"- stages ready/blocked/total: `{summary['ready_stage_count']}/{summary['blocked_stage_count']}/{summary['stage_count']}`",
        f"- operator intake: `{summary['operator_intake_status']}` ready/awaiting/blocked/applied `{summary['operator_intake_ready_to_apply_count']}/{summary['operator_intake_awaiting_input_count']}/{summary['operator_intake_blocked_count']}/{summary['operator_intake_applied_count']}` native/provenance applied `{summary['operator_intake_native_copied_count']}/{summary['operator_intake_provenance_patched_count']}`",
        f"- manifest sync: `{summary['manifest_sync_status']}` ready/awaiting/synced/applied `{summary['manifest_sync_ready_to_sync_count']}/{summary['manifest_sync_awaiting_provenance_count']}/{summary['manifest_sync_synced_count']}/{summary['manifest_sync_applied_field_count']}`",
        f"- audit: `{summary['audit_status']}` pass/blocked `{summary['audit_pass_count']}/{summary['audit_blocked_count']}`",
        f"- action board: `{summary['action_board_status']}` actions/open `{summary['action_board_action_count']}/{summary['action_board_open_action_count']}`",
        f"- action bundle: `{summary['action_bundle_status']}` actions/open/files/folders `{summary['action_bundle_action_count']}/{summary['action_bundle_open_action_count']}/{summary['action_bundle_file_count']}/{summary['action_bundle_folder_count']}`",
        f"- promotion: `{summary['promotion_status']}` promoted/blocked `{summary['promoted_manifest_count']}/{summary['promotion_blocked_count']}`",
        f"- intake staging: `{summary['intake_staging_status']}` staged/blocked `{summary['staged_identity_count']}/{summary['staging_blocked_count']}`",
        f"- candidate intake sync: `{summary['candidate_intake_sync_status']}` ready/waiting/applied `{summary['candidate_intake_ready_to_apply_count']}/{summary['candidate_intake_waiting_count']}/{summary['candidate_intake_applied_count']}`",
        f"- workbench: `{summary['workbench_status'] or '-'}`",
        f"- first next action: {summary['first_next_action'] or '-'}",
        "",
        "## Cycle Stages",
        "",
        "| stage | status | ready | awaiting | blocked | total | path | next action |",
        "| --- | --- | ---: | ---: | ---: | ---: | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['stage']}` | `{row['status']}` | {row['ready_count']} | {row['awaiting_count']} | "
            f"{row['blocked_count']} | {row['total_count']} | `{row['path']}` | {row['next_action'] or '-'} |"
        )
    if not payload["rows"]:
        lines.append("| - | `missing` | 0 | 0 | 0 | 0 | - | rerun clearance cycle |")
    lines.extend(["", "## Claim Boundary", "", str(summary["claim_boundary"]), ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def write_outputs(args: argparse.Namespace, payload: dict[str, Any]) -> None:
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"], CYCLE_COLUMNS)
    _write_md(args.out_md, payload)


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    payloads = {
        "operator_intake": _run_operator_intake(args),
        "manifest_sync": _run_manifest_sync(args),
        "audit": _run_workorder_audit(args),
        "action_board": _run_action_board(args),
        "action_bundle": _run_action_bundle(args),
        "promotion": _run_promotion_plan(args),
        "intake_staging": _run_intake_staging(args),
        "candidate_intake_sync": _run_candidate_intake_sync(args),
    }
    payload = _build_cycle_payload(args, payloads)
    write_outputs(args, payload)
    workbench_payload = _run_workbench(args)
    final_payload = _build_cycle_payload(args, payloads, workbench_payload=workbench_payload)
    write_outputs(args, final_payload)
    _run_workbench(args)
    return final_payload


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run CASP17 target identity clearance downstream cycle.")
    parser.add_argument("--workorder-json", default=DEFAULT_WORKORDER_JSON)
    parser.add_argument("--operator-intake-csv", default=DEFAULT_OPERATOR_INTAKE_CSV)
    parser.add_argument("--operator-intake-json", default=DEFAULT_OPERATOR_INTAKE_JSON)
    parser.add_argument("--operator-intake-report-csv", default=DEFAULT_OPERATOR_INTAKE_REPORT_CSV)
    parser.add_argument("--operator-intake-md", default=DEFAULT_OPERATOR_INTAKE_MD)
    parser.add_argument("--manifest-sync-json", default=DEFAULT_MANIFEST_SYNC_JSON)
    parser.add_argument("--manifest-sync-csv", default=DEFAULT_MANIFEST_SYNC_CSV)
    parser.add_argument("--manifest-sync-md", default=DEFAULT_MANIFEST_SYNC_MD)
    parser.add_argument("--audit-json", default=DEFAULT_AUDIT_JSON)
    parser.add_argument("--audit-csv", default=DEFAULT_AUDIT_CSV)
    parser.add_argument("--audit-md", default=DEFAULT_AUDIT_MD)
    parser.add_argument("--action-board-json", default=DEFAULT_ACTION_BOARD_JSON)
    parser.add_argument("--action-board-csv", default=DEFAULT_ACTION_BOARD_CSV)
    parser.add_argument("--action-board-md", default=DEFAULT_ACTION_BOARD_MD)
    parser.add_argument("--action-bundle-dir", default=DEFAULT_ACTION_BUNDLE_DIR)
    parser.add_argument("--action-bundle-json", default=DEFAULT_ACTION_BUNDLE_JSON)
    parser.add_argument("--action-bundle-csv", default=DEFAULT_ACTION_BUNDLE_CSV)
    parser.add_argument("--action-bundle-md", default=DEFAULT_ACTION_BUNDLE_MD)
    parser.add_argument("--current-target-csv", default=DEFAULT_CURRENT_TARGET_CSV)
    parser.add_argument("--promoted-manifest-csv", default=DEFAULT_PROMOTED_MANIFEST_CSV)
    parser.add_argument("--promotion-json", default=DEFAULT_PROMOTION_JSON)
    parser.add_argument("--promotion-csv", default=DEFAULT_PROMOTION_CSV)
    parser.add_argument("--promotion-md", default=DEFAULT_PROMOTION_MD)
    parser.add_argument("--identity-intake-csv", default=DEFAULT_IDENTITY_INTAKE_CSV)
    parser.add_argument("--candidate-intake-csv", default=DEFAULT_CANDIDATE_INTAKE_CSV)
    parser.add_argument("--candidate-intake-sync-json", default=DEFAULT_CANDIDATE_INTAKE_SYNC_JSON)
    parser.add_argument("--candidate-intake-sync-csv", default=DEFAULT_CANDIDATE_INTAKE_SYNC_CSV)
    parser.add_argument("--candidate-intake-sync-md", default=DEFAULT_CANDIDATE_INTAKE_SYNC_MD)
    parser.add_argument("--intake-staging-json", default=DEFAULT_INTAKE_STAGING_JSON)
    parser.add_argument("--intake-staging-csv", default=DEFAULT_INTAKE_STAGING_CSV)
    parser.add_argument("--intake-staging-md", default=DEFAULT_INTAKE_STAGING_MD)
    parser.add_argument("--workbench-json", default=DEFAULT_WORKBENCH_JSON)
    parser.add_argument("--workbench-csv", default=DEFAULT_WORKBENCH_CSV)
    parser.add_argument("--workbench-md", default=DEFAULT_WORKBENCH_MD)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    parser.add_argument("--apply-operator-intake", action="store_true")
    parser.add_argument("--apply-manifest-sync", action="store_true")
    parser.add_argument("--apply-candidate-intake", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_payload(args)
    write_outputs(args, payload)


if __name__ == "__main__":
    main()

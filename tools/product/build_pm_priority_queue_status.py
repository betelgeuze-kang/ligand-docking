#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT_JSON = ".betelgeuze/pm_priority_queue_status_current.json"
DEFAULT_OUT_CSV = ".betelgeuze/pm_priority_queue_status_current.csv"
DEFAULT_OUT_MD = ".betelgeuze/pm_priority_queue_status_current.md"

DEFAULT_GITHUB_OPEN_PRS_JSON = ".betelgeuze/github_open_prs_current.json"
DEFAULT_RELEASE_SOURCE_JSON = "runs/product_release_source_of_truth_gate_current.json"
DEFAULT_RELEASE_SOURCE_RECALC_JSON = ".betelgeuze/tmp_product_release_source_of_truth_gate_now.json"
DEFAULT_F2G_F2H_PREFLIGHT_JSON = ".betelgeuze/f2g_f2h_surface_preflight.local.json"
DEFAULT_F2G_F2H_RECOVERY_JSON = ".betelgeuze/f2g_f2h_authoritative_surface_recovery_packet.local.json"
DEFAULT_DEVELOPER_PREVIEW_REGISTER_MD = "docs/developer_preview_final_gate_action_register.md"
DEFAULT_DEVELOPER_PREVIEW_AUDIT_JSON = "runs/developer_preview_final_gate_audit_current.json"
DEFAULT_EXTERNAL_BENCHMARK_JSON = ".betelgeuze/external_benchmark_receipt_queue_batch_update.json"
DEFAULT_PUBLIC_BENCHMARK_AUDIT_JSON = "runs/public_benchmark_external_receipts_audit_current.json"
DEFAULT_PUBLIC_BENCHMARK_ATTACH_PACKET_JSON = "runs/public_benchmark_receipt_attach_packet_current.json"
DEFAULT_CUSTOMER_SHADOW_JSON = "runs/customer_shadow_evidence_status_current.json"
DEFAULT_GPU_HIP_PLAN_MD = "docs/gpu_hip_parity_after_cpu_plan.md"
DEFAULT_GPU_RETURN_INTAKE_JSON = "runs/product_production_ai_gpu_return_intake_current.json"
DEFAULT_ROCM_ENV_JSON = "runs/rocm_environment_manifest_current.json"
DEFAULT_ROCM_BENCHMARK_JSON = "runs/product_end_to_end_rocm_benchmark_current.json"
DEFAULT_ENTERPRISE_ON_PREM_JSON = "runs/enterprise_on_prem_readiness_gate_current.json"

DP_GATE_IDS = {
    "benchmark_results_clean_checkout_regenerated",
    "silent_import_loss_zero",
    "selected_medium_models_pass_or_approved_review",
    "large_models_crash_oom_free",
    "linux_windows_reproducibility_confirmed",
    "new_user_core_workflow_observation_passed",
}
EXTERNAL_TRACK_IDS = {
    "hardest_external_10case",
    "korean_public_structures",
    "peer_spd_hinge",
    "tpu_hffb",
}

CLAIM_BOUNDARY = (
    "PM priority queue status rollup only; aggregates local status packets and optional locally captured GitHub PR "
    "state for the pasted PM queue. It does not call GitHub, close/rebase PRs, run solvers, regenerate protected "
    "evidence, submit benchmarks, ingest customer raw data, promote G1, or mutate external state."
)


def _resolve(path_like: str | Path, *, root: Path = ROOT) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else root / path


def _read_json(path_like: str | Path, *, root: Path = ROOT) -> Any:
    path = _resolve(path_like, root=root)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _summary(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {}
    summary = payload.get("summary")
    return summary if isinstance(summary, dict) else payload


def _text(value: Any) -> str:
    return str(value or "").strip()


def _int(value: Any) -> int:
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0


def _write_json(path_like: str | Path, payload: dict[str, Any], *, root: Path = ROOT) -> None:
    path = _resolve(path_like, root=root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _read_text(path_like: str | Path, *, root: Path = ROOT) -> str:
    path = _resolve(path_like, root=root)
    if not path.exists():
        return ""
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def _row(
    item_id: str,
    title: str,
    status: str,
    ready: bool,
    evidence: str,
    blocker: str,
    next_action: str,
) -> dict[str, Any]:
    return {
        "item_id": item_id,
        "title": title,
        "status": status,
        "ready": ready,
        "evidence": evidence,
        "blocker": "" if ready else blocker,
        "next_action": next_action,
        "claim_promotion_allowed": False,
        "execution_enabled": False,
        "external_state_mutated": False,
    }


def _github_pr_row(open_prs_payload: Any) -> dict[str, Any]:
    if open_prs_payload is None:
        return _row(
            "0",
            "stale PR cleanup",
            "unknown_github_open_pr_state",
            False,
            "github_open_prs_json_missing",
            "github_open_pr_state_not_captured",
            "Run gh pr list --state open --json number,title,url > .betelgeuze/github_open_prs_current.json, then rebuild this rollup.",
        )
    open_prs = open_prs_payload if isinstance(open_prs_payload, list) else []
    open_count = len(open_prs)
    return _row(
        "0",
        "stale PR cleanup",
        "closed_no_open_prs" if open_count == 0 else "blocked_open_prs_present",
        open_count == 0,
        f"open_pr_count={open_count}",
        "open_prs_present",
        "Inspect any listed open PRs and close/rebase with clear CI action.",
    )


def _readiness_row(release_payload: Any, recalc_payload: Any) -> dict[str, Any]:
    release = _summary(release_payload)
    recalc = _summary(recalc_payload)
    release_status = _text(release.get("status"))
    recalc_status = _text(recalc.get("status"))
    release_blockers = _int(release.get("blocker_count"))
    recalc_blockers = _int(recalc.get("blocker_count"))
    release_stale = _int(release.get("stale_artifact_count"))
    recalc_stale = _int(recalc.get("stale_artifact_count"))
    release_ready = release_status == "product_release_source_of_truth_gate_ready"
    recalc_ready = recalc_status == "product_release_source_of_truth_gate_ready"
    evidence = (
        f"stored_status={release_status or 'missing'};stored_blockers={release_blockers};"
        f"stored_stale={release_stale};recalc_status={recalc_status or 'missing'};"
        f"recalc_blockers={recalc_blockers};recalc_stale={recalc_stale}"
    )
    captured = bool(release_status and recalc_status)
    documented_blocked = captured and release_status.startswith("blocked_") and recalc_status.startswith("blocked_")
    synced_ready = captured and release_ready and recalc_ready and release_blockers == 0 and recalc_blockers == 0
    refresh_mismatch = captured and not synced_ready and not documented_blocked
    return _row(
        "1",
        "readiness snapshot/doc sync",
        (
            "source_of_truth_refresh_synced"
            if synced_ready
            else (
                "documented_blocked_no_promotion"
                if documented_blocked
                else (
                    "blocked_readiness_refresh_mismatch"
                    if refresh_mismatch
                    else "blocked_readiness_sync_evidence_missing"
                )
            )
        ),
        synced_ready or documented_blocked,
        evidence,
        "readiness_snapshot_recalc_mismatch" if refresh_mismatch else "readiness_snapshot_or_recalc_evidence_missing",
        (
            "Source-of-truth stored and recalc snapshots agree; downstream claim gates still control promotion."
            if synced_ready
            else "Keep readiness non-promoting; refresh protected evidence only after explicit approval."
        ),
    )


def _recovery_evidence(recovery_payload: Any) -> str:
    recovery = _summary(recovery_payload)
    rows = recovery_payload.get("rows") if isinstance(recovery_payload, dict) else []
    failing_rows = [
        row for row in rows if isinstance(row, dict) and _text(row.get("status")) != "pass"
    ] if isinstance(rows, list) else []
    primary = failing_rows[0] if failing_rows else {}
    return (
        f"recovery_status={_text(recovery.get('status')) or 'missing'};"
        f"recovery_required={bool(recovery.get('recovery_required') is True)};"
        f"blocked_recovery_items={_int(recovery.get('blocked_recovery_item_count'))};"
        f"primary_recovery_item={_text(primary.get('recovery_item_id')) or 'none'};"
        f"primary_required_surface={_text(primary.get('required_surface')) or 'none'}"
    )


def _recovery_action(recovery_payload: Any, fallback: str) -> str:
    rows = recovery_payload.get("rows") if isinstance(recovery_payload, dict) else []
    failing_rows = [
        row for row in rows if isinstance(row, dict) and _text(row.get("status")) != "pass"
    ] if isinstance(rows, list) else []
    primary = failing_rows[0] if failing_rows else {}
    return _text(primary.get("operator_action")) or fallback


def _f2g_row(f2_payload: Any, recovery_payload: Any = None) -> dict[str, Any]:
    summary = _summary(f2_payload)
    status = _text(summary.get("status"))
    blockers = summary.get("blockers") if isinstance(summary.get("blockers"), list) else []
    ready = status == "f2g_f2h_surface_preflight_ready" and bool(summary.get("f2g_audit_ready") is True)
    recovery_evidence = _recovery_evidence(recovery_payload)
    return _row(
        "2",
        "F2g support/elastic-link audit",
        "ready_for_f2g_audit" if ready else status or "blocked_f2g_preflight_missing",
        ready,
        f"status={status or 'missing'};blockers={','.join(map(str, blockers))};{recovery_evidence}",
        "f2g_authoritative_surfaces_missing",
        _recovery_action(
            recovery_payload or {},
            "Restore real-MGT, near-null, support/elastic-link, and assembled tangent inputs before running F2g.",
        ),
    )


def _f2h_row(f2_payload: Any, recovery_payload: Any = None) -> dict[str, Any]:
    summary = _summary(f2_payload)
    allowed = bool(summary.get("f2h_continuation_allowed") is True)
    f2g_ready = bool(summary.get("f2g_audit_ready") is True)
    recovery_evidence = _recovery_evidence(recovery_payload)
    return _row(
        "3",
        "F2h lightweight continuation",
        "ready_for_f2h_continuation" if allowed else "blocked_until_f2g_audit",
        allowed,
        f"f2g_audit_ready={f2g_ready};f2h_continuation_allowed={allowed};{recovery_evidence}",
        "f2h_blocked_until_f2g_audit",
        _recovery_action(
            recovery_payload or {},
            "Do not run continuation until the F2g local audit exists and prerequisite surfaces are present.",
        ),
    )


def _developer_preview_row(register_text: str, audit_payload: Any) -> dict[str, Any]:
    audit = _summary(audit_payload)
    audit_status = _text(audit.get("status"))
    if audit_status:
        clean_ready = bool(audit.get("developer_preview_clean_baseline_ready") is True)
        ready_count = _int(audit.get("ready_gate_count"))
        gate_count = _int(audit.get("gate_count")) or len(DP_GATE_IDS)
        blocked_count = _int(audit.get("blocked_gate_count"))
        missing_receipts = _int(audit.get("missing_receipt_count"))
        work_order_rows = _int(audit.get("receipt_work_order_row_count"))
        work_order_primary = _text(audit.get("receipt_work_order_primary_gate_id"))
        primary_blocker = _text(audit.get("primary_blocker_id") or audit.get("primary_blocker"))
        return _row(
            "4",
            "Developer Preview baseline clean",
            "developer_preview_final_gates_ready" if clean_ready else "blocked_developer_preview_final_gates",
            clean_ready,
            (
                f"status={audit_status};ready_gates={ready_count}/{gate_count};"
                f"blocked_gates={blocked_count};missing_receipts={missing_receipts};"
                f"receipt_work_order_rows={work_order_rows};"
                f"receipt_work_order_primary={work_order_primary or 'none'};"
                f"primary_blocker={primary_blocker or 'none'}"
            ),
            primary_blocker or "developer_preview_final_gate_receipts_missing",
            _text(audit.get("next_required_step"))
            or "Run the six DP gate commands in a clean checkout and attach reviewed receipts before promotion.",
        )

    present_ids = {gate_id for gate_id in DP_GATE_IDS if gate_id in register_text}
    ready = present_ids == DP_GATE_IDS
    return _row(
        "4",
        "Developer Preview baseline clean",
        "action_register_ready_gates_blocked" if ready else "blocked_dp_register_incomplete",
        ready,
        f"listed_gate_count={len(present_ids)};required_gate_count={len(DP_GATE_IDS)}",
        "developer_preview_final_gate_register_incomplete",
        "Run the six DP gate commands in a clean checkout and attach reviewed receipts before promotion.",
    )


def _external_benchmark_row(payload: Any, audit_payload: Any = None, attach_payload: Any = None) -> dict[str, Any]:
    data = payload if isinstance(payload, dict) else {}
    rows = data.get("rows") if isinstance(data.get("rows"), list) else []
    ids = {str(row.get("work_item_id")) for row in rows if isinstance(row, dict)}
    missing_status_count = sum(
        1
        for row in rows
        if isinstance(row, dict)
        and (_text(row.get("current_receipt_status")) != "missing_not_attached" or bool(_text(row.get("receipt_url"))))
    )
    queue_ready = ids == EXTERNAL_TRACK_IDS and missing_status_count == 0
    audit = _summary(audit_payload)
    attach = _summary(attach_payload)
    audit_status = _text(audit.get("status"))
    attach_status = _text(attach.get("status"))
    audit_ready = bool(audit.get("external_benchmark_receipts_ready") is True)
    attach_ready = bool(attach.get("receipt_attach_packet_ready") is True)
    field_work_order_rows = _int(attach.get("field_work_order_row_count"))
    field_work_order_primary = _text(
        attach.get("field_work_order_primary_lane_id") or attach.get("field_work_order_primary_field_name")
    )
    field_work_order_primary_field = _text(attach.get("field_work_order_primary_field_name"))
    field_work_order_primary_required_action = _text(
        attach.get("field_work_order_primary_required_action")
    )
    primary_blocker = _text(
        attach.get("primary_blocker_id")
        or audit.get("primary_blocker_id")
        or attach.get("primary_blocker")
        or audit.get("primary_blocker")
    )
    canonical_present = bool(audit_status or attach_status)
    ready = (audit_ready and attach_ready) if canonical_present else queue_ready
    evidence = (
        f"queue_track_count={len(ids)};queue_unexpected_attached_or_pass_count={missing_status_count};"
        f"audit_status={audit_status or 'missing'};attach_status={attach_status or 'missing'};"
        f"audit_ready={audit_ready};attach_ready={attach_ready};"
        f"field_work_order_rows={field_work_order_rows};"
        f"field_work_order_primary={field_work_order_primary or 'none'};"
        f"field_work_order_primary_field={field_work_order_primary_field or 'none'}"
    )
    return _row(
        "5",
        "external benchmark receipts",
        (
            "external_benchmark_receipts_ready"
            if ready
            else (
                "blocked_public_benchmark_receipt_attach_packet"
                if canonical_present
                else "blocked_external_benchmark_queue_incomplete"
            )
        ),
        ready,
        evidence,
        primary_blocker or "external_benchmark_receipt_queue_incomplete",
        field_work_order_primary_required_action
        or _text(attach.get("next_required_step") or audit.get("next_required_step"))
        or "Create/confirm operator queue rows and attach receipt URLs only after real closure evidence exists.",
    )


def _customer_shadow_row(payload: Any) -> dict[str, Any]:
    summary = _summary(payload)
    status = _text(summary.get("status"))
    schema_ready = bool(summary.get("customer_shadow_intake_schema_ready") is True)
    completed = _int(summary.get("completed_customer_shadow_case_count"))
    required = _int(summary.get("required_completed_customer_shadow_case_count")) or 3
    minimum_met = bool(summary.get("customer_shadow_minimum_met") is True) or completed >= required
    work_order_rows = _int(summary.get("customer_shadow_work_order_row_count"))
    work_order_primary = _text(summary.get("customer_shadow_work_order_primary_case_slot_id"))
    work_order_action = _text(summary.get("customer_shadow_work_order_primary_required_action"))
    ready = bool(status == "customer_shadow_evidence_status_ready" and schema_ready and minimum_met)
    return _row(
        "6",
        "customer shadow intake",
        "customer_shadow_minimum_ready"
        if ready
        else ("schema_ready_cases_missing" if schema_ready else "blocked_customer_shadow_schema_missing"),
        ready,
        (
            f"status={status or 'missing'};schema_ready={schema_ready};"
            f"completed={completed};required={required};minimum_met={minimum_met};"
            f"work_order_rows={work_order_rows};work_order_primary={work_order_primary or 'none'}"
        ),
        "customer_shadow_completed_cases_missing" if schema_ready else "customer_shadow_schema_missing",
        (
            "Customer shadow minimum is ready; keep paid-pilot wording blocked until release gates agree."
            if ready
            else (
                work_order_action
                or "Collect three real reviewed customer-shadow metadata rows without storing private raw data."
            )
        ),
    )


def _gpu_hip_row(plan_text: str, intake_payload: Any, rocm_payload: Any, benchmark_payload: Any) -> dict[str, Any]:
    intake = _summary(intake_payload)
    rocm = _summary(rocm_payload)
    benchmark = _summary(benchmark_payload)
    plan_ready = "GPU/HIP is a performance" in plan_text and "not solver-truth" in plan_text
    rocm_ready = _text(rocm.get("status")) == "rocm_environment_manifest_ready"
    benchmark_ready = _text(benchmark.get("status")) == "product_end_to_end_rocm_benchmark_ready"
    intake_status = _text(intake.get("status"))
    ready = plan_ready and rocm_ready and benchmark_ready and intake_status.startswith("blocked_")
    return _row(
        "7",
        "GPU/HIP after CPU parity",
        "plan_ready_product_intake_blocked" if ready else "blocked_gpu_hip_policy_evidence_missing",
        ready,
        f"plan_ready={plan_ready};rocm_ready={rocm_ready};benchmark_ready={benchmark_ready};gpu_return_intake={intake_status or 'missing'}",
        "gpu_hip_policy_or_intake_evidence_missing",
        "Keep GPU/HIP non-promoting until CPU closure, device residency, residual parity, full return, and post-validation close.",
    )


def _enterprise_on_prem_row(payload: Any) -> dict[str, Any]:
    summary = _summary(payload)
    status = _text(summary.get("status"))
    ready = bool(summary.get("enterprise_on_prem_ready") is True)
    ready_controls = _int(summary.get("ready_control_count"))
    control_count = _int(summary.get("control_count"))
    blocked_controls = _int(summary.get("blocked_control_count"))
    primary_blocker = _text(summary.get("primary_blocker_id") or summary.get("primary_blocker"))
    return _row(
        "8",
        "enterprise/on-prem platform",
        status or "blocked_enterprise_on_prem_readiness_gate_missing",
        ready,
        (
            f"status={status or 'missing'};ready_controls={ready_controls}/{control_count};"
            f"blocked_controls={blocked_controls};primary_blocker={primary_blocker or 'none'};"
            f"oidc_rbac_ready={bool(summary.get('oidc_rbac_ready') is True)};"
            f"object_storage_ready={bool(summary.get('object_storage_ready') is True)};"
            f"gpu_scheduler_ready={bool(summary.get('gpu_scheduler_ready') is True)};"
            f"support_bundle_recovery_drill_ready={bool(summary.get('support_bundle_recovery_drill_ready') is True)}"
        ),
        primary_blocker or "enterprise_on_prem_readiness_gate_missing",
        _text(summary.get("next_required_step"))
        or "Build runs/enterprise_on_prem_readiness_gate_current.json and clear OIDC/RBAC, object storage, GPU scheduler, tracing, and support-bundle blockers.",
    )


def build_pm_priority_queue_status(
    *,
    root: Path = ROOT,
    github_open_prs_json: str = DEFAULT_GITHUB_OPEN_PRS_JSON,
    release_source_json: str = DEFAULT_RELEASE_SOURCE_JSON,
    release_source_recalc_json: str = DEFAULT_RELEASE_SOURCE_RECALC_JSON,
    f2g_f2h_preflight_json: str = DEFAULT_F2G_F2H_PREFLIGHT_JSON,
    f2g_f2h_recovery_json: str = DEFAULT_F2G_F2H_RECOVERY_JSON,
    developer_preview_register_md: str = DEFAULT_DEVELOPER_PREVIEW_REGISTER_MD,
    developer_preview_audit_json: str = DEFAULT_DEVELOPER_PREVIEW_AUDIT_JSON,
    external_benchmark_json: str = DEFAULT_EXTERNAL_BENCHMARK_JSON,
    public_benchmark_audit_json: str = DEFAULT_PUBLIC_BENCHMARK_AUDIT_JSON,
    public_benchmark_attach_packet_json: str = DEFAULT_PUBLIC_BENCHMARK_ATTACH_PACKET_JSON,
    customer_shadow_json: str = DEFAULT_CUSTOMER_SHADOW_JSON,
    gpu_hip_plan_md: str = DEFAULT_GPU_HIP_PLAN_MD,
    gpu_return_intake_json: str = DEFAULT_GPU_RETURN_INTAKE_JSON,
    rocm_env_json: str = DEFAULT_ROCM_ENV_JSON,
    rocm_benchmark_json: str = DEFAULT_ROCM_BENCHMARK_JSON,
    enterprise_on_prem_json: str = DEFAULT_ENTERPRISE_ON_PREM_JSON,
) -> dict[str, Any]:
    root = Path(root)
    f2_payload = _read_json(f2g_f2h_preflight_json, root=root)
    f2_recovery_payload = _read_json(f2g_f2h_recovery_json, root=root)
    rows = [
        _github_pr_row(_read_json(github_open_prs_json, root=root)),
        _readiness_row(
            _read_json(release_source_json, root=root),
            _read_json(release_source_recalc_json, root=root),
        ),
        _f2g_row(f2_payload, f2_recovery_payload),
        _f2h_row(f2_payload, f2_recovery_payload),
        _developer_preview_row(
            _read_text(developer_preview_register_md, root=root),
            _read_json(developer_preview_audit_json, root=root),
        ),
        _external_benchmark_row(
            _read_json(external_benchmark_json, root=root),
            _read_json(public_benchmark_audit_json, root=root),
            _read_json(public_benchmark_attach_packet_json, root=root),
        ),
        _customer_shadow_row(_read_json(customer_shadow_json, root=root)),
        _gpu_hip_row(
            _read_text(gpu_hip_plan_md, root=root),
            _read_json(gpu_return_intake_json, root=root),
            _read_json(rocm_env_json, root=root),
            _read_json(rocm_benchmark_json, root=root),
        ),
        _enterprise_on_prem_row(_read_json(enterprise_on_prem_json, root=root)),
    ]
    ready_count = sum(1 for row in rows if row["ready"])
    blocker_count = len(rows) - ready_count
    technical_blockers = [row["blocker"] for row in rows if row["item_id"] in {"2", "3"} and row["blocker"]]
    first_blocked_row = next((row for row in rows if not row["ready"]), {})
    first_blocked_item_id = _text(first_blocked_row.get("item_id"))
    first_blocked_title = _text(first_blocked_row.get("title"))
    first_blocked_status = _text(first_blocked_row.get("status"))
    first_blocked_blocker = _text(first_blocked_row.get("blocker"))
    first_blocked_next_action = _text(first_blocked_row.get("next_action"))
    summary = {
        "packet_type": "pm_priority_queue_status",
        "status": "pm_priority_queue_complete" if blocker_count == 0 else "blocked_pm_priority_queue",
        "item_count": len(rows),
        "ready_item_count": ready_count,
        "blocked_item_count": blocker_count,
        "first_blocked_item_id": first_blocked_item_id,
        "first_blocked_title": first_blocked_title,
        "first_blocked_status": first_blocked_status,
        "first_blocked_blocker": first_blocked_blocker,
        "first_blocked_next_action": first_blocked_next_action,
        "technical_blockers": technical_blockers,
        "f2g_blocked": any(row["item_id"] == "2" and not row["ready"] for row in rows),
        "f2h_blocked": any(row["item_id"] == "3" and not row["ready"] for row in rows),
        "release_ready_promotion_allowed": False,
        "paid_pilot_ready_promotion_allowed": False,
        "solver_product_ready_promotion_allowed": False,
        "g1_promotion_allowed": False,
        "external_state_mutated": False,
        "execution_enabled": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": first_blocked_next_action or "No queue blockers remain.",
    }
    return {"summary": summary, "rows": rows}


def _write_md(path_like: str | Path, payload: dict[str, Any], *, root: Path = ROOT) -> None:
    path = _resolve(path_like, root=root)
    summary = payload["summary"]
    lines = [
        "# PM Priority Queue Status",
        "",
        f"- status: `{summary['status']}`",
        f"- ready_item_count: `{summary['ready_item_count']}`",
        f"- blocked_item_count: `{summary['blocked_item_count']}`",
        f"- first_blocked_item_id: `{summary['first_blocked_item_id']}`",
        f"- first_blocked_blocker: `{summary['first_blocked_blocker']}`",
        f"- first_blocked_next_action: `{summary['first_blocked_next_action']}`",
        f"- g1_promotion_allowed: `{summary['g1_promotion_allowed']}`",
        "",
        "| item | status | ready | blocker | next action |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['item_id']}` | `{row['status']}` | `{row['ready']}` | `{row['blocker'] or '-'}` | {row['next_action']} |"
        )
    lines.extend(["", "## Claim Boundary", "", summary["claim_boundary"], ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build machine-readable PM priority queue status.")
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument("--github-open-prs-json", default=DEFAULT_GITHUB_OPEN_PRS_JSON)
    parser.add_argument("--release-source-json", default=DEFAULT_RELEASE_SOURCE_JSON)
    parser.add_argument("--release-source-recalc-json", default=DEFAULT_RELEASE_SOURCE_RECALC_JSON)
    parser.add_argument("--f2g-f2h-preflight-json", default=DEFAULT_F2G_F2H_PREFLIGHT_JSON)
    parser.add_argument("--f2g-f2h-recovery-json", default=DEFAULT_F2G_F2H_RECOVERY_JSON)
    parser.add_argument("--developer-preview-register-md", default=DEFAULT_DEVELOPER_PREVIEW_REGISTER_MD)
    parser.add_argument("--developer-preview-audit-json", default=DEFAULT_DEVELOPER_PREVIEW_AUDIT_JSON)
    parser.add_argument("--external-benchmark-json", default=DEFAULT_EXTERNAL_BENCHMARK_JSON)
    parser.add_argument("--public-benchmark-audit-json", default=DEFAULT_PUBLIC_BENCHMARK_AUDIT_JSON)
    parser.add_argument(
        "--public-benchmark-attach-packet-json",
        default=DEFAULT_PUBLIC_BENCHMARK_ATTACH_PACKET_JSON,
    )
    parser.add_argument("--customer-shadow-json", default=DEFAULT_CUSTOMER_SHADOW_JSON)
    parser.add_argument("--gpu-hip-plan-md", default=DEFAULT_GPU_HIP_PLAN_MD)
    parser.add_argument("--gpu-return-intake-json", default=DEFAULT_GPU_RETURN_INTAKE_JSON)
    parser.add_argument("--rocm-env-json", default=DEFAULT_ROCM_ENV_JSON)
    parser.add_argument("--rocm-benchmark-json", default=DEFAULT_ROCM_BENCHMARK_JSON)
    parser.add_argument("--enterprise-on-prem-json", default=DEFAULT_ENTERPRISE_ON_PREM_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    root = Path(args.root)
    payload = build_pm_priority_queue_status(
        root=root,
        github_open_prs_json=args.github_open_prs_json,
        release_source_json=args.release_source_json,
        release_source_recalc_json=args.release_source_recalc_json,
        f2g_f2h_preflight_json=args.f2g_f2h_preflight_json,
        f2g_f2h_recovery_json=args.f2g_f2h_recovery_json,
        developer_preview_register_md=args.developer_preview_register_md,
        developer_preview_audit_json=args.developer_preview_audit_json,
        external_benchmark_json=args.external_benchmark_json,
        public_benchmark_audit_json=args.public_benchmark_audit_json,
        public_benchmark_attach_packet_json=args.public_benchmark_attach_packet_json,
        customer_shadow_json=args.customer_shadow_json,
        gpu_hip_plan_md=args.gpu_hip_plan_md,
        gpu_return_intake_json=args.gpu_return_intake_json,
        rocm_env_json=args.rocm_env_json,
        rocm_benchmark_json=args.rocm_benchmark_json,
        enterprise_on_prem_json=args.enterprise_on_prem_json,
    )
    _write_json(args.out_json, payload, root=root)
    write_csv_rows(_resolve(args.out_csv, root=root), payload["rows"])
    _write_md(args.out_md, payload, root=root)
    print(json.dumps(payload["summary"], indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

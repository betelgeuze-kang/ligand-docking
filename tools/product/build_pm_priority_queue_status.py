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
DEFAULT_DEVELOPER_PREVIEW_REGISTER_MD = "docs/developer_preview_final_gate_action_register.md"
DEFAULT_EXTERNAL_BENCHMARK_JSON = ".betelgeuze/external_benchmark_receipt_queue_batch_update.json"
DEFAULT_CUSTOMER_SHADOW_JSON = ".betelgeuze/customer_shadow_evidence_status_current.json"
DEFAULT_GPU_HIP_PLAN_MD = "docs/gpu_hip_parity_after_cpu_plan.md"
DEFAULT_GPU_RETURN_INTAKE_JSON = "runs/product_production_ai_gpu_return_intake_current.json"
DEFAULT_ROCM_ENV_JSON = "runs/rocm_environment_manifest_current.json"
DEFAULT_ROCM_BENCHMARK_JSON = "runs/product_end_to_end_rocm_benchmark_current.json"

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
    evidence = (
        f"stored_status={release_status or 'missing'};stored_blockers={release_blockers};"
        f"recalc_status={recalc_status or 'missing'};recalc_blockers={recalc_blockers}"
    )
    captured = bool(release_status and recalc_status)
    documented_blocked = captured and release_status.startswith("blocked_") and recalc_status.startswith("blocked_")
    return _row(
        "1",
        "readiness snapshot/doc sync",
        "documented_blocked_no_promotion" if documented_blocked else "blocked_readiness_sync_evidence_missing",
        documented_blocked,
        evidence,
        "readiness_snapshot_or_recalc_evidence_missing",
        "Keep readiness non-promoting; refresh protected evidence only after explicit approval.",
    )


def _f2g_row(f2_payload: Any) -> dict[str, Any]:
    summary = _summary(f2_payload)
    status = _text(summary.get("status"))
    blockers = summary.get("blockers") if isinstance(summary.get("blockers"), list) else []
    ready = status == "f2g_f2h_surface_preflight_ready" and bool(summary.get("f2g_audit_ready") is True)
    return _row(
        "2",
        "F2g support/elastic-link audit",
        "ready_for_f2g_audit" if ready else status or "blocked_f2g_preflight_missing",
        ready,
        f"status={status or 'missing'};blockers={','.join(map(str, blockers))}",
        "f2g_authoritative_surfaces_missing",
        "Restore real-MGT, near-null, support/elastic-link, and assembled tangent inputs before running F2g.",
    )


def _f2h_row(f2_payload: Any) -> dict[str, Any]:
    summary = _summary(f2_payload)
    allowed = bool(summary.get("f2h_continuation_allowed") is True)
    f2g_ready = bool(summary.get("f2g_audit_ready") is True)
    return _row(
        "3",
        "F2h lightweight continuation",
        "ready_for_f2h_continuation" if allowed else "blocked_until_f2g_audit",
        allowed,
        f"f2g_audit_ready={f2g_ready};f2h_continuation_allowed={allowed}",
        "f2h_blocked_until_f2g_audit",
        "Do not run continuation until the F2g local audit exists and prerequisite surfaces are present.",
    )


def _developer_preview_row(register_text: str) -> dict[str, Any]:
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


def _external_benchmark_row(payload: Any) -> dict[str, Any]:
    data = payload if isinstance(payload, dict) else {}
    rows = data.get("rows") if isinstance(data.get("rows"), list) else []
    ids = {str(row.get("work_item_id")) for row in rows if isinstance(row, dict)}
    missing_status_count = sum(
        1
        for row in rows
        if isinstance(row, dict)
        and (_text(row.get("current_receipt_status")) != "missing_not_attached" or bool(_text(row.get("receipt_url"))))
    )
    ready = ids == EXTERNAL_TRACK_IDS and missing_status_count == 0
    return _row(
        "5",
        "external benchmark receipts",
        "workflow_ready_receipts_missing" if ready else "blocked_external_benchmark_queue_incomplete",
        ready,
        f"track_count={len(ids)};unexpected_attached_or_pass_count={missing_status_count}",
        "external_benchmark_receipt_queue_incomplete",
        "Create/confirm operator queue rows and attach receipt URLs only after real closure evidence exists.",
    )


def _customer_shadow_row(payload: Any) -> dict[str, Any]:
    summary = _summary(payload)
    schema_ready = bool(summary.get("customer_shadow_intake_schema_ready") is True)
    completed = _int(summary.get("completed_customer_shadow_case_count"))
    required = _int(summary.get("required_completed_customer_shadow_case_count")) or 3
    return _row(
        "6",
        "customer shadow intake",
        "schema_ready_cases_missing" if schema_ready else "blocked_customer_shadow_schema_missing",
        schema_ready,
        f"schema_ready={schema_ready};completed={completed};required={required}",
        "customer_shadow_completed_cases_missing",
        "Collect three real reviewed customer-shadow metadata rows without storing private raw data.",
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


def build_pm_priority_queue_status(
    *,
    root: Path = ROOT,
    github_open_prs_json: str = DEFAULT_GITHUB_OPEN_PRS_JSON,
    release_source_json: str = DEFAULT_RELEASE_SOURCE_JSON,
    release_source_recalc_json: str = DEFAULT_RELEASE_SOURCE_RECALC_JSON,
    f2g_f2h_preflight_json: str = DEFAULT_F2G_F2H_PREFLIGHT_JSON,
    developer_preview_register_md: str = DEFAULT_DEVELOPER_PREVIEW_REGISTER_MD,
    external_benchmark_json: str = DEFAULT_EXTERNAL_BENCHMARK_JSON,
    customer_shadow_json: str = DEFAULT_CUSTOMER_SHADOW_JSON,
    gpu_hip_plan_md: str = DEFAULT_GPU_HIP_PLAN_MD,
    gpu_return_intake_json: str = DEFAULT_GPU_RETURN_INTAKE_JSON,
    rocm_env_json: str = DEFAULT_ROCM_ENV_JSON,
    rocm_benchmark_json: str = DEFAULT_ROCM_BENCHMARK_JSON,
) -> dict[str, Any]:
    root = Path(root)
    f2_payload = _read_json(f2g_f2h_preflight_json, root=root)
    rows = [
        _github_pr_row(_read_json(github_open_prs_json, root=root)),
        _readiness_row(
            _read_json(release_source_json, root=root),
            _read_json(release_source_recalc_json, root=root),
        ),
        _f2g_row(f2_payload),
        _f2h_row(f2_payload),
        _developer_preview_row(_read_text(developer_preview_register_md, root=root)),
        _external_benchmark_row(_read_json(external_benchmark_json, root=root)),
        _customer_shadow_row(_read_json(customer_shadow_json, root=root)),
        _gpu_hip_row(
            _read_text(gpu_hip_plan_md, root=root),
            _read_json(gpu_return_intake_json, root=root),
            _read_json(rocm_env_json, root=root),
            _read_json(rocm_benchmark_json, root=root),
        ),
    ]
    ready_count = sum(1 for row in rows if row["ready"])
    blocker_count = len(rows) - ready_count
    technical_blockers = [row["blocker"] for row in rows if row["item_id"] in {"2", "3"} and row["blocker"]]
    summary = {
        "packet_type": "pm_priority_queue_status",
        "status": "pm_priority_queue_complete" if blocker_count == 0 else "blocked_pm_priority_queue",
        "item_count": len(rows),
        "ready_item_count": ready_count,
        "blocked_item_count": blocker_count,
        "first_blocked_item_id": next((row["item_id"] for row in rows if not row["ready"]), ""),
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
        "next_required_step": next((row["next_action"] for row in rows if not row["ready"]), "No queue blockers remain."),
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
    parser.add_argument("--developer-preview-register-md", default=DEFAULT_DEVELOPER_PREVIEW_REGISTER_MD)
    parser.add_argument("--external-benchmark-json", default=DEFAULT_EXTERNAL_BENCHMARK_JSON)
    parser.add_argument("--customer-shadow-json", default=DEFAULT_CUSTOMER_SHADOW_JSON)
    parser.add_argument("--gpu-hip-plan-md", default=DEFAULT_GPU_HIP_PLAN_MD)
    parser.add_argument("--gpu-return-intake-json", default=DEFAULT_GPU_RETURN_INTAKE_JSON)
    parser.add_argument("--rocm-env-json", default=DEFAULT_ROCM_ENV_JSON)
    parser.add_argument("--rocm-benchmark-json", default=DEFAULT_ROCM_BENCHMARK_JSON)
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
        developer_preview_register_md=args.developer_preview_register_md,
        external_benchmark_json=args.external_benchmark_json,
        customer_shadow_json=args.customer_shadow_json,
        gpu_hip_plan_md=args.gpu_hip_plan_md,
        gpu_return_intake_json=args.gpu_return_intake_json,
        rocm_env_json=args.rocm_env_json,
        rocm_benchmark_json=args.rocm_benchmark_json,
    )
    _write_json(args.out_json, payload, root=root)
    write_csv_rows(_resolve(args.out_csv, root=root), payload["rows"])
    _write_md(args.out_md, payload, root=root)
    print(json.dumps(payload["summary"], indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

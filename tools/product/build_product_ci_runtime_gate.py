#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import datetime, timezone, timedelta
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT_JSON = "runs/product_ci_runtime_gate_current.json"
DEFAULT_OUT_MD = "runs/product_ci_runtime_gate_current.md"
DEFAULT_PRODUCT_IMAGE_PREFLIGHT_JSON = "runs/product_image_smoke_preflight_current.json"

CLAIM_BOUNDARY = (
    "Product CI runtime gate only; records observed GitHub Actions run status and local ROCm product "
    "image preflight evidence. It does not dispatch workflows, mutate billing, change branch protection, "
    "deploy, publish, upload, or delete files."
)

BILLING_BLOCKER_CODE = "github_actions_billing_or_spending_limit"


def _resolve(root: Path, path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else root / path


def _read_json(root: Path, path_like: str | Path) -> dict[str, Any]:
    path = _resolve(root, path_like)
    if not path.exists() or not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(ROOT, path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_markdown(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(ROOT, path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    s = payload["summary"]
    lines = [
        "# Product CI Runtime Gate",
        "",
        f"- status: `{s['status']}`",
        f"- remote_product_ci_green: `{s['remote_product_ci_green']}`",
        f"- github_actions_started: `{s['github_actions_started']}`",
        f"- external_blocker: `{s['external_blocker']}`",
        f"- blocker_code: `{s['blocker_code']}`",
        f"- product_api_worker_conclusion: `{s['product_api_worker_conclusion']}`",
        f"- product_image_smoke_conclusion: `{s['product_image_smoke_conclusion']}`",
        f"- latest_github_actions_record_kst_date: `{s['latest_github_actions_record_kst_date']}`",
        f"- local_rocm_clean_container_ready: `{s['local_rocm_clean_container_ready']}`",
        f"- workflow_dispatch_executed: `{s['workflow_dispatch_executed']}`",
        f"- external_state_mutated: `{s['external_state_mutated']}`",
        "",
        "## Runs",
        "",
    ]
    for row in payload["rows"]:
        lines.extend(
            [
                f"### {row['workflow']}",
                "",
                f"- run_id: `{row['run_id']}`",
                f"- created_at_utc: `{row['created_at_utc']}`",
                f"- created_at_kst_date: `{row['created_at_kst_date']}`",
                f"- conclusion: `{row['conclusion']}`",
                f"- job_started: `{row['job_started']}`",
                f"- url: {row['url'] or 'n/a'}",
                f"- release_blocker: `{row['release_blocker']}`",
                "",
            ]
        )
    lines.extend(["## Blockers", ""])
    blockers = payload.get("blockers") or []
    lines.extend(f"- `{row['code']}`" for row in blockers) if blockers else lines.append("- none")
    lines.extend(["", "## Next Steps", ""])
    lines.extend(f"- {step}" for step in s["next_required_steps"])
    lines.extend(["", "## Claim Boundary", "", s["claim_boundary"], ""])
    path.write_text("\n".join(lines), encoding="utf-8")


def _is_truthy_text(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "y", "started"}


def _billing_blocked(*messages: str) -> bool:
    joined = " ".join(message.lower() for message in messages if message)
    return "payments have failed" in joined or "spending limit" in joined or "billing" in joined


def _kst_date_from_utc(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return ""
    return parsed.astimezone(timezone(timedelta(hours=9))).date().isoformat()


def _summary(packet: dict[str, Any]) -> dict[str, Any]:
    summary = packet.get("summary")
    return summary if isinstance(summary, dict) else {}


def _workflow_row(
    *,
    workflow: str,
    run_id: str,
    url: str,
    conclusion: str,
    job_started: bool,
    annotation: str,
    created_at_utc: str = "",
    updated_at_utc: str = "",
) -> dict[str, Any]:
    green = conclusion == "success" and job_started
    return {
        "workflow": workflow,
        "run_id": run_id,
        "url": url,
        "conclusion": conclusion,
        "job_started": job_started,
        "annotation": annotation,
        "created_at_utc": created_at_utc,
        "updated_at_utc": updated_at_utc,
        "created_at_kst_date": _kst_date_from_utc(created_at_utc),
        "green": green,
        "release_blocker": not green,
        "external_state_mutated": False,
    }


def build_product_ci_runtime_gate(
    *,
    root: str | Path = ROOT,
    product_image_preflight_json: str | Path = DEFAULT_PRODUCT_IMAGE_PREFLIGHT_JSON,
    product_api_worker_run_id: str = "",
    product_api_worker_url: str = "",
    product_api_worker_conclusion: str = "",
    product_api_worker_job_started: bool = False,
    product_api_worker_annotation: str = "",
    product_api_worker_created_at_utc: str = "",
    product_api_worker_updated_at_utc: str = "",
    product_image_smoke_run_id: str = "",
    product_image_smoke_url: str = "",
    product_image_smoke_conclusion: str = "",
    product_image_smoke_job_started: bool = False,
    product_image_smoke_annotation: str = "",
    product_image_smoke_created_at_utc: str = "",
    product_image_smoke_updated_at_utc: str = "",
) -> dict[str, Any]:
    root_path = Path(root)
    preflight_summary = _summary(_read_json(root_path, product_image_preflight_json))
    local_rocm_clean_container_ready = bool(
        preflight_summary.get("status") == "product_image_smoke_preflight_ready"
        and preflight_summary.get("clean_container_smoke_ready") is True
        and preflight_summary.get("receipt_status") == "product_image_smoke_ready"
        and preflight_summary.get("receipt_mode") == "rocm-runtime"
        and preflight_summary.get("container_runtime_receipt_ready") is True
        and preflight_summary.get("container_runtime_rust_hip_backend_enabled") is True
        and preflight_summary.get("product_runner_smoke_ready") is True
    )
    rows = [
        _workflow_row(
            workflow="product-api-worker",
            run_id=product_api_worker_run_id,
            url=product_api_worker_url,
            conclusion=product_api_worker_conclusion,
            job_started=product_api_worker_job_started,
            annotation=product_api_worker_annotation,
            created_at_utc=product_api_worker_created_at_utc,
            updated_at_utc=product_api_worker_updated_at_utc,
        ),
        _workflow_row(
            workflow="product-image-smoke",
            run_id=product_image_smoke_run_id,
            url=product_image_smoke_url,
            conclusion=product_image_smoke_conclusion,
            job_started=product_image_smoke_job_started,
            annotation=product_image_smoke_annotation,
            created_at_utc=product_image_smoke_created_at_utc,
            updated_at_utc=product_image_smoke_updated_at_utc,
        ),
    ]
    observed_dates = sorted({row["created_at_kst_date"] for row in rows if row["created_at_kst_date"]})
    billing_blocked = _billing_blocked(product_api_worker_annotation, product_image_smoke_annotation)
    remote_product_ci_green = all(row["green"] for row in rows)
    github_actions_started = all(row["job_started"] for row in rows)
    runtime_gate_ready = bool(remote_product_ci_green and local_rocm_clean_container_ready)
    blockers: list[dict[str, str]] = []
    if billing_blocked:
        blockers.append({"code": BILLING_BLOCKER_CODE})
    if not local_rocm_clean_container_ready:
        blockers.append({"code": "local_rocm_clean_container_evidence_missing"})
    for row in rows:
        if not row["green"]:
            blockers.append({"code": f"{row['workflow']}_not_green"})
    status = "product_ci_runtime_gate_ready" if runtime_gate_ready else "blocked_product_ci_runtime_gate"
    next_required_steps = (
        [
            "Owner resolves GitHub Billing & plans payment/spending-limit status.",
            "After billing is restored, rerun: gh workflow run product-api-worker.yml",
            "Rerun hosted build smoke: gh workflow run product-image-smoke.yml -f verify_mode=build",
            "On a self-hosted ROCm runner, rerun: gh workflow run product-image-smoke.yml -f verify_mode=rocm-runtime",
        ]
        if billing_blocked
        else (
            ["Remote product CI is green; attach this gate to the product evidence bundle."]
            if runtime_gate_ready
            else [
                "Rerun product-api-worker and product-image-smoke workflows, then rebuild this gate from observed green runs.",
            ]
        )
    )
    summary = {
        "packet_type": "product_ci_runtime_gate",
        "status": status,
        "runtime_gate_ready": runtime_gate_ready,
        "remote_product_ci_green": remote_product_ci_green,
        "github_actions_started": github_actions_started,
        "external_blocker": billing_blocked,
        "blocker_code": BILLING_BLOCKER_CODE if billing_blocked else "",
        "product_api_worker_run_id": product_api_worker_run_id,
        "product_api_worker_url": product_api_worker_url,
        "product_api_worker_conclusion": product_api_worker_conclusion,
        "product_api_worker_job_started": product_api_worker_job_started,
        "product_api_worker_created_at_utc": product_api_worker_created_at_utc,
        "product_api_worker_created_at_kst_date": _kst_date_from_utc(product_api_worker_created_at_utc),
        "product_image_smoke_run_id": product_image_smoke_run_id,
        "product_image_smoke_url": product_image_smoke_url,
        "product_image_smoke_conclusion": product_image_smoke_conclusion,
        "product_image_smoke_job_started": product_image_smoke_job_started,
        "product_image_smoke_created_at_utc": product_image_smoke_created_at_utc,
        "product_image_smoke_created_at_kst_date": _kst_date_from_utc(product_image_smoke_created_at_utc),
        "latest_github_actions_record_kst_date": observed_dates[-1] if observed_dates else "",
        "github_actions_record_dates_kst": observed_dates,
        "product_image_preflight_json": str(product_image_preflight_json),
        "local_rocm_clean_container_ready": local_rocm_clean_container_ready,
        "local_product_image_preflight_status": str(preflight_summary.get("status") or ""),
        "local_product_image_receipt_mode": str(preflight_summary.get("receipt_mode") or ""),
        "local_product_image_receipt_status": str(preflight_summary.get("receipt_status") or ""),
        "workflow_dispatch_executed": False,
        "billing_mutated": False,
        "branch_protection_mutated": False,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_steps": next_required_steps,
    }
    return {"summary": summary, "rows": rows, "blockers": blockers}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build product CI runtime gate evidence.")
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    parser.add_argument("--product-image-preflight-json", default=DEFAULT_PRODUCT_IMAGE_PREFLIGHT_JSON)
    parser.add_argument("--product-api-worker-run-id", default="")
    parser.add_argument("--product-api-worker-url", default="")
    parser.add_argument("--product-api-worker-conclusion", default="")
    parser.add_argument("--product-api-worker-job-started", default="false")
    parser.add_argument("--product-api-worker-annotation", default="")
    parser.add_argument("--product-api-worker-created-at-utc", default="")
    parser.add_argument("--product-api-worker-updated-at-utc", default="")
    parser.add_argument("--product-image-smoke-run-id", default="")
    parser.add_argument("--product-image-smoke-url", default="")
    parser.add_argument("--product-image-smoke-conclusion", default="")
    parser.add_argument("--product-image-smoke-job-started", default="false")
    parser.add_argument("--product-image-smoke-annotation", default="")
    parser.add_argument("--product-image-smoke-created-at-utc", default="")
    parser.add_argument("--product-image-smoke-updated-at-utc", default="")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    payload = build_product_ci_runtime_gate(
        product_image_preflight_json=args.product_image_preflight_json,
        product_api_worker_run_id=args.product_api_worker_run_id,
        product_api_worker_url=args.product_api_worker_url,
        product_api_worker_conclusion=args.product_api_worker_conclusion,
        product_api_worker_job_started=_is_truthy_text(args.product_api_worker_job_started),
        product_api_worker_annotation=args.product_api_worker_annotation,
        product_api_worker_created_at_utc=args.product_api_worker_created_at_utc,
        product_api_worker_updated_at_utc=args.product_api_worker_updated_at_utc,
        product_image_smoke_run_id=args.product_image_smoke_run_id,
        product_image_smoke_url=args.product_image_smoke_url,
        product_image_smoke_conclusion=args.product_image_smoke_conclusion,
        product_image_smoke_job_started=_is_truthy_text(args.product_image_smoke_job_started),
        product_image_smoke_annotation=args.product_image_smoke_annotation,
        product_image_smoke_created_at_utc=args.product_image_smoke_created_at_utc,
        product_image_smoke_updated_at_utc=args.product_image_smoke_updated_at_utc,
    )
    _write_json(args.out_json, payload)
    _write_markdown(args.out_md, payload)
    print(json.dumps({"status": payload["summary"]["status"], "out_json": args.out_json}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

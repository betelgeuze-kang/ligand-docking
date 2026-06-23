#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT_JSON = "runs/release_ci_remote_green_receipt_current.json"
DEFAULT_OUT_MD = "runs/release_ci_remote_green_receipt_current.md"
DEFAULT_WORKFLOW_YML = ".github/workflows/product-image-smoke.yml"

CLAIM_BOUNDARY = (
    "Release CI remote-green receipt only evaluates read-only GitHub/API evidence supplied as JSON files plus "
    "the local product-image workflow source contract. It does not register runners, dispatch workflows, change "
    "branch protection, edit required checks, create tags, upload artifacts, deploy, publish, or mutate external state."
)

REQUIRED_MAIN_CHECKS = (
    "product-image-build-smoke",
    "product-image-rocm-runtime-smoke",
)


def _resolve(root: Path, path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else root / path


def _read_json(root: Path, path_like: str | Path | None) -> Any:
    if not path_like:
        return {}
    path = _resolve(root, path_like)
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _read_text(root: Path, path_like: str | Path | None) -> str:
    if not path_like:
        return ""
    path = _resolve(root, path_like)
    if not path.is_file():
        return ""
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(ROOT, path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_markdown(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(ROOT, path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    summary = payload["summary"]
    lines = [
        "# Release CI Remote Green Receipt",
        "",
        f"- status: `{summary['status']}`",
        f"- linux_self_hosted_runner_ready: `{summary['linux_self_hosted_runner_ready']}`",
        f"- rocm_self_hosted_runner_ready: `{summary['rocm_self_hosted_runner_ready']}`",
        f"- main_required_checks_ready: `{summary['main_required_checks_ready']}`",
        f"- workflow_source_contract_ready: `{summary['workflow_source_contract_ready']}`",
        f"- weekly_rocm_schedule_green: `{summary['weekly_rocm_schedule_green']}`",
        f"- failure_artifacts_preserved: `{summary['failure_artifacts_preserved']}`",
        f"- release_tag_rocm_gate_green: `{summary['release_tag_rocm_gate_green']}`",
        f"- blocker_count: `{summary['blocker_count']}`",
        "",
        "## Blockers",
        "",
    ]
    blockers = payload.get("blockers") or []
    lines.extend(f"- `{row['code']}`" for row in blockers) if blockers else lines.append("- none")
    lines.extend(["", "## Claim Boundary", "", summary["claim_boundary"], ""])
    path.write_text("\n".join(lines), encoding="utf-8")


def _as_list(payload: Any, key: str) -> list[Any]:
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict) and isinstance(payload.get(key), list):
        return list(payload[key])
    return []


def _labels(runner: dict[str, Any]) -> set[str]:
    labels = runner.get("labels") or []
    values = set()
    for label in labels if isinstance(labels, list) else []:
        if isinstance(label, dict):
            name = str(label.get("name") or "")
        else:
            name = str(label or "")
        if name:
            values.add(name.lower())
    return values


def _runner_ready(runners_payload: Any, required_labels: set[str]) -> tuple[bool, list[str]]:
    runner_names: list[str] = []
    for runner in _as_list(runners_payload, "runners"):
        if not isinstance(runner, dict):
            continue
        labels = _labels(runner)
        status = str(runner.get("status") or "").lower()
        if status == "online" and required_labels.issubset(labels):
            runner_names.append(str(runner.get("name") or runner.get("id") or "unnamed-runner"))
    return bool(runner_names), runner_names


def _required_checks(required_checks_payload: Any, branch_payload: Any) -> set[str]:
    checks: set[str] = set()
    contexts = []
    if isinstance(required_checks_payload, dict):
        contexts = list(required_checks_payload.get("contexts") or [])
        checks.update(str(row.get("context") or "") for row in required_checks_payload.get("checks") or [] if isinstance(row, dict))
    if isinstance(branch_payload, dict):
        protection = branch_payload.get("protection") if isinstance(branch_payload.get("protection"), dict) else {}
        required = protection.get("required_status_checks") if isinstance(protection.get("required_status_checks"), dict) else {}
        contexts.extend(required.get("contexts") or [])
        checks.update(str(row.get("context") or "") for row in required.get("checks") or [] if isinstance(row, dict))
    checks.update(str(context) for context in contexts if str(context))
    return {check for check in checks if check}


def _run_matches_rocm_success(run: dict[str, Any], *, event: str | None = None, tag_prefixes: tuple[str, ...] = ()) -> bool:
    if event and str(run.get("event") or "") != event:
        return False
    if tag_prefixes:
        ref = str(run.get("head_branch") or run.get("ref") or run.get("display_title") or "")
        if ref.startswith("refs/tags/"):
            ref = ref.removeprefix("refs/tags/")
        if not ref.startswith(tag_prefixes):
            return False
    name_text = " ".join(
        str(run.get(key) or "")
        for key in ("name", "display_title", "workflow_name", "path")
    ).lower()
    product_image_workflow = "product-image" in name_text or "product image" in name_text
    rocm_runtime_scope = "rocm" in name_text and "runtime" in name_text
    return (
        str(run.get("status") or "").lower() == "completed"
        and str(run.get("conclusion") or "").lower() == "success"
        and product_image_workflow
        and rocm_runtime_scope
    )


def _successful_rocm_run(runs_payload: Any, *, event: str | None = None, tag_prefixes: tuple[str, ...] = ()) -> tuple[bool, str]:
    for run in _as_list(runs_payload, "workflow_runs"):
        if isinstance(run, dict) and _run_matches_rocm_success(run, event=event, tag_prefixes=tag_prefixes):
            return True, str(run.get("html_url") or run.get("id") or "")
    return False, ""


def _failure_artifacts_ready(failed_run_artifacts_payload: Any) -> tuple[bool, list[str]]:
    active_names = [
        str(artifact.get("name") or "")
        for artifact in _as_list(failed_run_artifacts_payload, "artifacts")
        if isinstance(artifact, dict) and artifact.get("expired") is not True
    ]
    lowered = " ".join(active_names).lower()
    has_smoke_bundle = "product-image" in lowered and "smoke" in lowered
    has_receipt_or_runtime = "receipt" in lowered or "runtime" in lowered
    has_log_or_runtime = "log" in lowered or "runtime" in lowered
    ready = bool(active_names) and has_smoke_bundle and has_receipt_or_runtime and has_log_or_runtime
    return ready, active_names


def _workflow_source_contract(workflow_text: str, *, workflow_path: str) -> tuple[bool, dict[str, Any]]:
    text = str(workflow_text or "")
    checks = {
        "workflow_path": str(workflow_path or ""),
        "workflow_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest() if text else "",
        "workflow_present": bool(text.strip()),
        "build_job_present": "product-image-build-smoke:" in text,
        "build_self_hosted_linux_default": '"self-hosted","linux"' in text or "self-hosted, linux" in text,
        "rocm_runtime_job_present": "product-image-rocm-runtime-smoke:" in text,
        "rocm_runner_labels": "runs-on: [self-hosted, linux, rocm]" in text,
        "weekly_schedule": "schedule:" in text and "cron:" in text,
        "release_tag_triggers": "refs/tags/v" in text and "refs/tags/product-" in text,
        "workflow_tag_filters": "tags:" in text and "v*" in text and "product-*" in text,
        "artifact_upload_action": "actions/upload-artifact@v4" in text,
        "artifact_upload_always": "if: always()" in text,
        "receipt_artifact_path": "runs/product_image_smoke_receipt_current.json" in text,
        "build_log_artifact_path": "runs/product_image_build_smoke.log" in text,
        "rocm_log_artifact_path": "runs/product_image_rocm_runtime_smoke.log" in text,
        "rocm_runner_artifacts_path": "runs/product_image_smoke_runner_artifacts/**" in text,
    }
    pass_values = [value for key, value in checks.items() if key not in {"workflow_path", "workflow_sha256"}]
    return all(bool(value) for value in pass_values), checks


def _row(check_id: str, passed: bool, observed: Any, required: str, source: str) -> dict[str, Any]:
    return {
        "check_id": check_id,
        "passed": bool(passed),
        "observed": observed,
        "required": required,
        "source": source,
        "external_state_mutated": False,
        "release_blocker": not passed,
    }


def build_release_ci_remote_green_receipt(
    *,
    root: str | Path = ROOT,
    runner_inventory_json: str | Path | None = "",
    branch_json: str | Path | None = "",
    required_checks_json: str | Path | None = "",
    schedule_runs_json: str | Path | None = "",
    failed_run_artifacts_json: str | Path | None = "",
    release_tag_runs_json: str | Path | None = "",
    workflow_yml: str | Path | None = DEFAULT_WORKFLOW_YML,
) -> dict[str, Any]:
    root_path = Path(root)
    runners_payload = _read_json(root_path, runner_inventory_json)
    branch_payload = _read_json(root_path, branch_json)
    required_checks_payload = _read_json(root_path, required_checks_json)
    schedule_runs_payload = _read_json(root_path, schedule_runs_json)
    failed_artifacts_payload = _read_json(root_path, failed_run_artifacts_json)
    release_tag_runs_payload = _read_json(root_path, release_tag_runs_json)
    workflow_text = _read_text(root_path, workflow_yml)

    linux_ready, linux_runners = _runner_ready(runners_payload, {"self-hosted", "linux"})
    rocm_ready, rocm_runners = _runner_ready(runners_payload, {"self-hosted", "linux", "rocm"})
    branch_protected = bool(isinstance(branch_payload, dict) and branch_payload.get("protected") is True)
    checks = _required_checks(required_checks_payload, branch_payload)
    missing_checks = [check for check in REQUIRED_MAIN_CHECKS if not any(check in observed for observed in checks)]
    main_required_checks_ready = bool(branch_protected and not missing_checks)
    weekly_rocm_schedule_green, weekly_url = _successful_rocm_run(schedule_runs_payload, event="schedule")
    failure_artifacts_preserved, artifact_names = _failure_artifacts_ready(failed_artifacts_payload)
    release_tag_rocm_gate_green, tag_url = _successful_rocm_run(
        release_tag_runs_payload,
        event="push",
        tag_prefixes=("v", "product-"),
    )
    workflow_contract_ready, workflow_contract_observed = _workflow_source_contract(
        workflow_text,
        workflow_path=str(workflow_yml or ""),
    )

    rows = [
        _row("linux_self_hosted_runner_registered", linux_ready, linux_runners, "online runner with self-hosted+linux labels", str(runner_inventory_json or "")),
        _row("rocm_self_hosted_runner_registered", rocm_ready, rocm_runners, "online runner with self-hosted+linux+rocm labels", str(runner_inventory_json or "")),
        _row("main_branch_required_checks_configured", main_required_checks_ready, {"protected": branch_protected, "checks": sorted(checks), "missing_checks": missing_checks}, f"main protected and required checks include {', '.join(REQUIRED_MAIN_CHECKS)}", f"{branch_json};{required_checks_json}"),
        _row("product_image_workflow_source_contract_configured", workflow_contract_ready, workflow_contract_observed, "workflow source contains build/runtime jobs, weekly schedule, tag runtime gate, and always-uploaded receipt/log artifacts", str(workflow_yml or "")),
        _row("weekly_rocm_runtime_schedule_green", weekly_rocm_schedule_green, weekly_url, "at least one completed successful schedule run for ROCm runtime smoke", str(schedule_runs_json or "")),
        _row("failed_run_artifacts_preserved", failure_artifacts_preserved, artifact_names, "failed workflow run exposes smoke log/receipt/runtime artifacts", str(failed_run_artifacts_json or "")),
        _row("release_tag_rocm_runtime_gate_green", release_tag_rocm_gate_green, tag_url, "at least one successful v* or product-* tag push ROCm runtime run", str(release_tag_runs_json or "")),
    ]
    blockers = [{"code": row["check_id"], "source": row["source"], "observed": row["observed"]} for row in rows if not row["passed"]]
    summary = {
        "packet_type": "release_ci_remote_green_receipt",
        "schema_version": "release_ci_remote_green_receipt_v1",
        "status": "release_ci_remote_green_ready" if not blockers else "blocked_release_ci_remote_green",
        "pass": not blockers,
        "blocker_count": len(blockers),
        "linux_self_hosted_runner_ready": linux_ready,
        "rocm_self_hosted_runner_ready": rocm_ready,
        "main_required_checks_ready": main_required_checks_ready,
        "workflow_source_contract_ready": workflow_contract_ready,
        "weekly_rocm_schedule_green": weekly_rocm_schedule_green,
        "failure_artifacts_preserved": failure_artifacts_preserved,
        "release_tag_rocm_gate_green": release_tag_rocm_gate_green,
        "required_main_checks": list(REQUIRED_MAIN_CHECKS),
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "No local action required for this receipt; remote Release CI evidence is green."
            if not blockers
            else "Resolve blocked rows in GitHub runner/settings/workflow evidence, then rebuild this receipt from fresh read-only JSON."
        ),
    }
    return {"summary": summary, "rows": rows, "blockers": blockers}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build read-only release CI remote-green receipt.")
    parser.add_argument("--runner-inventory-json", default="")
    parser.add_argument("--branch-json", default="")
    parser.add_argument("--required-checks-json", default="")
    parser.add_argument("--schedule-runs-json", default="")
    parser.add_argument("--failed-run-artifacts-json", default="")
    parser.add_argument("--release-tag-runs-json", default="")
    parser.add_argument("--workflow-yml", default=DEFAULT_WORKFLOW_YML)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    args = parser.parse_args(argv)
    payload = build_release_ci_remote_green_receipt(
        runner_inventory_json=args.runner_inventory_json,
        branch_json=args.branch_json,
        required_checks_json=args.required_checks_json,
        schedule_runs_json=args.schedule_runs_json,
        failed_run_artifacts_json=args.failed_run_artifacts_json,
        release_tag_runs_json=args.release_tag_runs_json,
        workflow_yml=args.workflow_yml,
    )
    _write_json(args.out_json, payload)
    _write_markdown(args.out_md, payload)
    return 0 if payload["summary"]["pass"] else 2


if __name__ == "__main__":
    raise SystemExit(main())

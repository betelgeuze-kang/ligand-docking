#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
RUNS = ROOT / "runs"

DEFAULT_OUT_JSON = RUNS / "local_delivery_preflight_current.json"
DEFAULT_OUT_MD = RUNS / "local_delivery_preflight_current.md"
DEFAULT_LOCAL_CI_OUT_JSON = RUNS / "local_ci_tests_summary.json"
DEFAULT_REQUIREMENTS_LOCK_OUT_JSON = RUNS / "local_delivery_requirements_lock_current.json"
DEFAULT_REQUIREMENTS_LOCK_OUT_MD = RUNS / "local_delivery_requirements_lock_current.md"
DEFAULT_REQUIREMENTS_LOCK_OUT_TXT = RUNS / "local_delivery_requirements_lock_current.txt"
DEFAULT_ENGINE_PROVENANCE_OUT_JSON = RUNS / "local_delivery_engine_provenance_current.json"
DEFAULT_ENGINE_PROVENANCE_OUT_MD = RUNS / "local_delivery_engine_provenance_current.md"
DEFAULT_ENVIRONMENT_OUT_JSON = RUNS / "local_delivery_environment_manifest_current.json"
DEFAULT_ENVIRONMENT_OUT_MD = RUNS / "local_delivery_environment_manifest_current.md"
DEFAULT_QUEUE_OUT_JSON = RUNS / "local_engine_commercialization_queue_current.json"
DEFAULT_QUEUE_OUT_CSV = RUNS / "local_engine_commercialization_queue_current.csv"
DEFAULT_QUEUE_OUT_MD = RUNS / "local_engine_commercialization_queue_current.md"
DEFAULT_REPORT_OUT_MD = ROOT / "commercialization_status_report.md"
DEFAULT_VERDICT_GATE_OUT_JSON = RUNS / "local_delivery_verdict_gate_current.json"
DEFAULT_VERDICT_GATE_OUT_MD = RUNS / "local_delivery_verdict_gate_current.md"
DEFAULT_CLAIM_SCOPE = "kinase,gpcr,ion_channel"
DEFAULT_ENVIRONMENT_STEP_ENV = {"TORCH_BLAS_PREFER_HIPBLASLT": "0"}


def _script(name: str) -> str:
    return str(ROOT / "tools" / name)


def _sanitize_label(value: str) -> str:
    cleaned = "".join(ch if (ch.isalnum() or ch in {"-", "_"}) else "_" for ch in str(value).strip())
    return cleaned.strip("_") or "local_delivery_preflight_current"


def _split_args(value: str) -> list[str]:
    return shlex.split(str(value).strip()) if str(value).strip() else []


def _environment_step_env() -> dict[str, str]:
    env = dict(DEFAULT_ENVIRONMENT_STEP_ENV)
    for key in env:
        if os.environ.get(key):
            env[key] = str(os.environ[key])
    return env


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = Path(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _read_json_object(path_like: str | Path) -> dict[str, Any]:
    path = Path(path_like)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _read_json_status(path_like: str | Path) -> tuple[dict[str, Any], str]:
    path = Path(path_like)
    if not path.exists():
        return {}, "missing"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}, "invalid"
    if not isinstance(payload, dict):
        return {}, "invalid"
    return payload, "present"


def _summaryish(payload: dict[str, Any]) -> dict[str, Any]:
    summary = payload.get("summary")
    merged = dict(payload or {})
    if isinstance(summary, dict):
        merged.update(summary)
    return merged


def _boolish(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and value in {0, 1}:
        return bool(value)
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "yes", "y", "1", "pass", "passed", "ok", "green", "complete"}:
            return True
        if lowered in {"false", "no", "n", "0", "fail", "failed", "red", "blocked", "incomplete"}:
            return False
    return None


def _first_bool(data: dict[str, Any], keys: list[str]) -> bool | None:
    for key in keys:
        if key in data:
            parsed = _boolish(data.get(key))
            if parsed is not None:
                return parsed
    return None


def _as_list(value: Any) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def _accuracy_gate_artifact(label: str) -> str:
    return f"runs/accuracy_gate_{label}.json"


def _accuracy_gate_check_summary(path_like: str | Path, *, dry_run: bool = False) -> dict[str, Any]:
    read_path = Path(path_like)
    if not read_path.is_absolute():
        read_path = ROOT / read_path
    if dry_run:
        return {
            "checked": False,
            "present": False,
            "valid": None,
            "pass": None,
            "status": "dry_run",
            "artifact": str(path_like),
            "failed_metric_count": 0,
            "failed_metrics": [],
            "failed_targets": [],
            "primary_failed_metric": {},
            "reason": "Dry run did not inspect the accuracy gate artifact.",
            "action_required": False,
            "next_required_step": "Dry run only. Re-run without `--dry-run` to validate the accuracy gate artifact.",
        }

    payload, status = _read_json_status(read_path)
    if status == "missing":
        return {
            "checked": True,
            "present": False,
            "valid": False,
            "pass": False,
            "status": "missing",
            "artifact": str(path_like),
            "failed_metric_count": 0,
            "failed_metrics": [],
            "failed_targets": [],
            "primary_failed_metric": {},
            "reason": f"Accuracy gate artifact `{path_like}` is missing.",
            "action_required": True,
            "next_required_step": "Run the accuracy gate and regenerate the local-delivery preflight before any delivery-ready verdict.",
        }
    if status == "invalid":
        return {
            "checked": True,
            "present": True,
            "valid": False,
            "pass": False,
            "status": "invalid",
            "artifact": str(path_like),
            "failed_metric_count": 0,
            "failed_metrics": [],
            "failed_targets": [],
            "primary_failed_metric": {},
            "reason": f"Accuracy gate artifact `{path_like}` is not a valid JSON object.",
            "action_required": True,
            "next_required_step": "Regenerate the accuracy gate artifact; do not treat an invalid artifact as passing.",
        }

    data = _summaryish(payload)
    failed_metrics = [row for row in _as_list(data.get("failed_metrics")) if isinstance(row, dict)]
    failed_targets = [str(value) for value in _as_list(data.get("failed_targets"))]
    explicit_pass = _first_bool(data, ["pass", "accuracy_gate_pass", "gate_pass", "overall_ok", "passed"])
    gate_pass = bool(explicit_pass is True and not failed_metrics)
    primary_failed_metric = dict(failed_metrics[0]) if failed_metrics else {}
    if gate_pass:
        reason = "Accuracy gate artifact reports pass=true with no failed metrics."
        next_required_step = "Accuracy gate is green; continue with the remaining local-delivery gates."
    else:
        metric = str(primary_failed_metric.get("metric") or "unknown_metric")
        target = str(primary_failed_metric.get("target") or "all")
        value = primary_failed_metric.get("value", "")
        threshold = primary_failed_metric.get("threshold", "")
        operator = str(primary_failed_metric.get("operator") or "")
        reason = (
            "Accuracy gate is not green"
            f": metric={metric}, target={target}, value={value}, threshold={threshold}, operator={operator}."
        )
        next_required_step = str(
            data.get("next_required_step")
            or "Fix the failing accuracy metric(s), rerun the accuracy gate, and only proceed after it reports pass=true."
        )
    return {
        "checked": True,
        "present": True,
        "valid": True,
        "pass": gate_pass,
        "status": "pass" if gate_pass else "fail",
        "artifact": str(path_like),
        "failed_metric_count": len(failed_metrics),
        "failed_metrics": failed_metrics,
        "failed_targets": failed_targets,
        "primary_failed_metric": primary_failed_metric,
        "reason": reason,
        "action_required": not gate_pass,
        "next_required_step": next_required_step,
    }


def _artifact_diagnostic(path_like: str | Path) -> dict[str, Any]:
    path = Path(path_like)
    exists = path.exists()
    size_bytes = path.stat().st_size if exists else 0
    return {
        "path": str(path_like),
        "present": exists,
        "size_bytes": size_bytes,
        "nonempty": bool(exists and size_bytes > 0),
    }


def _step_artifact_diagnostics(steps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for step in steps:
        for artifact in step.get("expected_artifacts", []) or []:
            row = _artifact_diagnostic(artifact)
            row["step_label"] = str(step.get("label", ""))
            rows.append(row)
    return rows


def _verdict_gate_fingerprint_check_summary(verdict_gate_payload: dict[str, Any]) -> dict[str, Any]:
    source_artifacts = verdict_gate_payload.get("source_artifacts")
    artifact_count = 0
    missing_count = 0
    invalid_count = 0
    fingerprinted_count = 0
    if isinstance(source_artifacts, list):
        artifact_count = len(source_artifacts)
        for row in source_artifacts:
            if not isinstance(row, dict):
                invalid_count += 1
                continue
            present = bool(row.get("present", False))
            required = bool(row.get("required", False))
            sha256 = str(row.get("sha256", "")).strip()
            try:
                size_bytes = int(row.get("size_bytes", 0) or 0)
            except (TypeError, ValueError):
                size_bytes = 0
            if required and not present:
                missing_count += 1
            if present and sha256 and size_bytes > 0:
                fingerprinted_count += 1
            elif present:
                invalid_count += 1
    all_fingerprinted = None
    if artifact_count:
        all_fingerprinted = bool(missing_count == 0 and invalid_count == 0)
    return {
        "checked": False,
        "ok": None,
        "status": "pending_bundle_check",
        "reason": (
            "Persisted-vs-fresh source artifact fingerprint comparison is performed by "
            "tools/build_local_delivery_bundle.py when the bundle manifest is built."
        ),
        "comparison_performed": False,
        "required_for_delivery_ready_verdict": True,
        "source_artifact_count": artifact_count,
        "source_artifact_missing_count": missing_count,
        "source_artifact_invalid_count": invalid_count,
        "source_artifact_fingerprinted_count": fingerprinted_count,
        "source_artifacts_all_fingerprinted": all_fingerprinted,
    }


def _expected_artifacts_nonempty(step: dict[str, Any] | None, *, newer_than: str | Path | None = None) -> bool:
    if not step:
        return False
    expected_artifacts = step.get("expected_artifacts", []) or []
    if not expected_artifacts:
        return False
    reference_mtime_ns = None
    if newer_than is not None:
        reference = Path(newer_than)
        if not reference.exists():
            return False
        reference_mtime_ns = reference.stat().st_mtime_ns
    for path_like in expected_artifacts:
        path = Path(path_like)
        if not _artifact_diagnostic(path).get("nonempty", False):
            return False
        if reference_mtime_ns is not None and path.stat().st_mtime_ns < reference_mtime_ns:
            return False
    return True


def _verdict_gate_execution_ok(
    step: dict[str, Any] | None,
    verdict_gate_summary: dict[str, Any],
    fingerprint_check: dict[str, Any],
    *,
    preflight_json: str | Path,
) -> bool:
    if not step:
        return False
    if bool(step.get("ok", False)):
        return _expected_artifacts_nonempty(step, newer_than=preflight_json)

    # The verdict gate exits non-zero for a valid blocked verdict. Preflight should
    # treat that as generated evidence, not as proof that preflight itself failed.
    try:
        returncode = int(step.get("returncode", 0) or 0)
    except (TypeError, ValueError):
        returncode = 0
    verdict = str(verdict_gate_summary.get("verdict", "")).strip().lower()
    blocked_verdict = returncode == 2 and verdict == "blocked"
    source_artifacts_ready = fingerprint_check.get("source_artifacts_all_fingerprinted") is True
    return bool(
        blocked_verdict
        and source_artifacts_ready
        and _expected_artifacts_nonempty(step, newer_than=preflight_json)
    )


def _preview(values: list[Any], *, limit: int = 5) -> str:
    shown = [str(value) for value in values[:limit]]
    if len(values) > limit:
        shown.append("...")
    return ", ".join(shown)


def _requirements_lock_summary(path_like: str | Path, *, dry_run: bool = False) -> dict[str, Any]:
    if dry_run:
        return {
            "checked": False,
            "present": False,
            "complete": None,
            "status": "dry_run",
            "reason": "Dry run did not inspect requirements lock contents.",
            "missing_package_install_targets": [],
            "loose_source_requirements": [],
            "unpinned_pin_suggestions": [],
            "action_required": False,
            "next_required_step": "Dry run only. Re-run without `--dry-run` to validate dependency completeness.",
        }

    path = Path(path_like)
    payload = _read_json_object(path)
    summary = payload.get("summary") if isinstance(payload, dict) else {}
    summary = summary if isinstance(summary, dict) else {}
    present = bool(path.exists() and payload)

    def _summary_int(key: str) -> int:
        try:
            return int(summary.get(key, 0) or 0)
        except (TypeError, ValueError):
            return 0

    missing_count = _summary_int("missing_count")
    loose_source_count = _summary_int("loose_source_requirement_count")
    missing_input_count = _summary_int("missing_input_file_count")
    optional_missing_count = _summary_int("optional_missing_count")
    missing_targets = [str(value) for value in _as_list(summary.get("missing_package_install_targets"))]
    optional_deferred_targets = [
        str(value) for value in _as_list(summary.get("optional_deferred_install_targets"))
    ]
    loose_sources = [str(value) for value in _as_list(summary.get("loose_source_requirements"))]
    pin_suggestions = [row for row in _as_list(summary.get("unpinned_pin_suggestions")) if isinstance(row, dict)]
    if not missing_targets:
        missing_targets = [
            str(row.get("display_name") or row.get("name") or row.get("normalized_name"))
            for row in _as_list(payload.get("missing_packages"))
            if isinstance(row, dict) and str(row.get("display_name") or row.get("name") or row.get("normalized_name")).strip()
        ]
    if not loose_sources:
        loose_sources = [
            str(row.get("raw") or row.get("requirement"))
            for row in _as_list(payload.get("loose_source_requirements"))
            if isinstance(row, dict)
            and str(row.get("raw") or row.get("requirement")).strip()
            and not str(row.get("raw") or row.get("requirement")).strip().startswith("#")
        ]
    if not pin_suggestions:
        pin_suggestions = [
            {
                "current_requirement": str(row.get("raw") or row.get("requirement") or ""),
                "installed_version": str(row.get("installed_version") or ""),
                "suggested_requirement": (
                    f"{row.get('display_name') or row.get('name')}=={row.get('installed_version')}"
                    if row.get("installed_version") and (row.get("display_name") or row.get("name"))
                    else ""
                ),
                "source": f"{row.get('source_file_relative', '')}:{row.get('line_number', '')}",
            }
            for row in _as_list(payload.get("unpinned_requirements"))
            if isinstance(row, dict)
        ]
    explicit_complete = summary.get("requirements_lock_complete")
    if isinstance(explicit_complete, bool):
        complete = bool(present and explicit_complete)
    else:
        complete = bool(present and missing_count == 0 and loose_source_count == 0 and missing_input_count == 0)
    action_parts = []
    if missing_targets:
        action_parts.append(f"install or remove missing packages: {_preview(missing_targets)}")
    elif missing_count:
        action_parts.append(f"resolve {missing_count} missing package(s)")
    if loose_sources:
        action_parts.append(f"replace loose/source requirements with package pins: {_preview(loose_sources)}")
    elif loose_source_count:
        action_parts.append(f"resolve {loose_source_count} loose/source requirement(s)")
    if missing_input_count:
        action_parts.append("restore or remove missing requirement input files")
    if not present:
        next_required_step = "Build the requirements lock before issuing any delivery-ready verdict."
    elif action_parts:
        next_required_step = "; ".join(action_parts) + ". Then rebuild the requirements lock and rerun preflight."
    else:
        next_required_step = str(
            summary.get("next_required_step")
            or "Requirements lock is complete; use pin suggestions for requirement-file hygiene if needed."
        )
    return {
        "checked": True,
        "present": present,
        "complete": complete,
        "status": "complete" if complete else ("incomplete" if present else "missing"),
        "status_line": str(summary.get("status_line", "")),
        "missing_count": missing_count,
        "optional_missing_count": optional_missing_count,
        "loose_source_requirement_count": loose_source_count,
        "missing_input_file_count": missing_input_count,
        "unpinned_count": _summary_int("unpinned_count"),
        "missing_package_install_targets": missing_targets,
        "optional_deferred_install_targets": optional_deferred_targets,
        "optional_profiles": dict(summary.get("optional_profiles", {}) or {}),
        "loose_source_requirements": loose_sources,
        "unpinned_pin_suggestions": pin_suggestions,
        "action_required": not complete,
        "next_required_step": next_required_step,
    }


def _write_markdown(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = Path(path_like)
    summary = payload["summary"]
    fingerprint_check = summary.get("verdict_gate_fingerprint_check", {})
    requirements_lock_check = summary.get("requirements_lock_check", {})
    accuracy_gate_check = summary.get("accuracy_gate_check", {})
    lines = [
        "# Local Delivery Preflight",
        "",
        f"- overall_ok: `{summary['overall_ok']}`",
        f"- dry_run: `{summary['dry_run']}`",
        f"- step_count: `{summary['step_count']}`",
        f"- ok_count: `{summary['ok_count']}`",
        f"- failed_count: `{summary['failed_count']}`",
        f"- skipped_count: `{summary['skipped_count']}`",
        f"- first_failed_step: `{summary['first_failed_step'] or '-'}`",
        f"- preflight_label: `{summary['preflight_label']}`",
        f"- accuracy_gate_artifact: `{summary['accuracy_gate_artifact']}`",
        f"- accuracy_gate_check_status: `{accuracy_gate_check.get('status', '-')}`",
        f"- accuracy_gate_check_pass: `{accuracy_gate_check.get('pass', None)}`",
        f"- accuracy_gate_failed_metric_count: `{accuracy_gate_check.get('failed_metric_count', 0)}`",
        f"- accuracy_gate_reason: {accuracy_gate_check.get('reason', '-')}",
        f"- accuracy_gate_next_required_step: {accuracy_gate_check.get('next_required_step', '-')}",
        f"- local_ci_summary_json: `{summary['local_ci_summary_json']}`",
        f"- requirements_lock_json: `{summary['requirements_lock_json']}`",
        f"- requirements_lock_md: `{summary['requirements_lock_md']}`",
        f"- requirements_lock_txt: `{summary['requirements_lock_txt']}`",
        f"- requirements_lock_check_status: `{requirements_lock_check.get('status', '-')}`",
        f"- requirements_lock_check_complete: `{requirements_lock_check.get('complete', None)}`",
        f"- requirements_lock_missing_package_install_targets: `{', '.join(requirements_lock_check.get('missing_package_install_targets', []) or []) or '-'}`",
        f"- requirements_lock_optional_deferred_install_targets: `{', '.join(requirements_lock_check.get('optional_deferred_install_targets', []) or []) or '-'}`",
        f"- requirements_lock_loose_source_requirements: `{', '.join(requirements_lock_check.get('loose_source_requirements', []) or []) or '-'}`",
        f"- requirements_lock_next_required_step: {requirements_lock_check.get('next_required_step', '-')}",
        f"- engine_provenance_json: `{summary['engine_provenance_json']}`",
        f"- engine_provenance_md: `{summary['engine_provenance_md']}`",
        f"- engine_provenance_ok: `{summary['engine_provenance_ok']}`",
        f"- environment_manifest_json: `{summary['environment_manifest_json']}`",
        f"- environment_manifest_md: `{summary['environment_manifest_md']}`",
        f"- commercialization_queue_json: `{summary['commercialization_queue_json']}`",
        f"- commercialization_queue_md: `{summary['commercialization_queue_md']}`",
        f"- commercialization_status_report_md: `{summary['commercialization_status_report_md']}`",
        f"- verdict_gate_json: `{summary['verdict_gate_json']}`",
        f"- verdict_gate_md: `{summary['verdict_gate_md']}`",
        f"- verdict_gate_delivery_ready: `{summary['verdict_gate_delivery_ready']}`",
        f"- verdict_gate_p0_blocker_count: `{summary['verdict_gate_p0_blocker_count']}`",
        f"- verdict_gate_pending: `{summary['verdict_gate_pending']}`",
        f"- verdict_gate_execution_ok: `{summary['verdict_gate_execution_ok']}`",
        f"- verdict_gate_required_ok: `{summary['verdict_gate_required_ok']}`",
        f"- verdict_gate_fingerprint_check_status: `{fingerprint_check.get('status', '-')}`",
        f"- verdict_gate_fingerprint_check_reason: `{fingerprint_check.get('reason', '-')}`",
        f"- verdict_gate_fingerprint_check_comparison_performed: `{fingerprint_check.get('comparison_performed', False)}`",
        f"- verdict_gate_source_artifact_count: `{fingerprint_check.get('source_artifact_count', 0)}`",
        f"- expected_artifact_count: `{summary['expected_artifact_count']}`",
        f"- present_expected_artifact_count: `{summary['present_expected_artifact_count']}`",
        f"- missing_expected_artifact_count: `{summary['missing_expected_artifact_count']}`",
        f"- next_required_step: {summary['next_required_step']}",
        "",
        "## Step Results",
        "",
        "| label | ok | returncode | dry_run | env_overrides |",
        "| --- | --- | ---: | --- | --- |",
    ]
    for step in payload["steps"]:
        env_overrides = ", ".join(f"{key}={value}" for key, value in sorted((step.get("env") or {}).items())) or "-"
        lines.append(
            f"| `{step['label']}` | `{step['ok']}` | {step['returncode']} | `{step['dry_run']}` | `{env_overrides}` |"
        )
    artifact_rows = payload.get("artifact_diagnostics", []) or []
    if artifact_rows:
        lines.extend(
            [
                "",
                "## Expected Artifact Diagnostics",
                "",
                "| step | artifact | present | size_bytes |",
                "| --- | --- | --- | ---: |",
            ]
        )
        for row in artifact_rows:
            lines.append(
                f"| `{row['step_label']}` | `{row['path']}` | `{row['present']}` | {row['size_bytes']} |"
            )
    pin_suggestions = [
        row for row in (requirements_lock_check.get("unpinned_pin_suggestions", []) or []) if isinstance(row, dict)
    ]
    if pin_suggestions:
        lines.extend(
            [
                "",
                "## Requirements Pin Suggestions",
                "",
                "| requirement | installed_version | suggested_requirement | source |",
                "| --- | --- | --- | --- |",
            ]
        )
        for row in pin_suggestions:
            lines.append(
                f"| `{row.get('current_requirement', '')}` | `{row.get('installed_version', '') or '-'}` | "
                f"`{row.get('suggested_requirement', '') or '-'}` | `{row.get('source', '')}` |"
            )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run the standard local-delivery preflight: accuracy gate, local CI smoke, family refresh, "
            "engine queue rebuild, and commercialization report rebuild."
        )
    )
    parser.add_argument("--preflight-label", default="local_delivery_preflight_current")
    parser.add_argument("--preflight-args", default="")
    parser.add_argument("--local-ci-args", default="")
    parser.add_argument("--requirements-lock-args", default="")
    parser.add_argument("--engine-provenance-args", default="")
    parser.add_argument("--environment-manifest-args", default="")
    parser.add_argument("--verdict-gate-args", default="")
    parser.add_argument("--claim-scope", default=DEFAULT_CLAIM_SCOPE)
    parser.add_argument("--fail-fast", action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument("--skip-accuracy-gate", action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument("--skip-local-ci", action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument("--skip-requirements-lock", action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument("--skip-engine-provenance", action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument("--skip-environment-manifest", action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument("--skip-refresh", action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument("--skip-queue", action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument("--skip-report", action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument("--skip-verdict-gate", action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument("--out-json", default=str(DEFAULT_OUT_JSON))
    parser.add_argument("--out-md", default=str(DEFAULT_OUT_MD))
    parser.add_argument("--local-ci-out-json", default=str(DEFAULT_LOCAL_CI_OUT_JSON))
    parser.add_argument("--requirements-lock-out-json", default=str(DEFAULT_REQUIREMENTS_LOCK_OUT_JSON))
    parser.add_argument("--requirements-lock-out-md", default=str(DEFAULT_REQUIREMENTS_LOCK_OUT_MD))
    parser.add_argument("--requirements-lock-out-txt", default=str(DEFAULT_REQUIREMENTS_LOCK_OUT_TXT))
    parser.add_argument("--engine-provenance-out-json", default=str(DEFAULT_ENGINE_PROVENANCE_OUT_JSON))
    parser.add_argument("--engine-provenance-out-md", default=str(DEFAULT_ENGINE_PROVENANCE_OUT_MD))
    parser.add_argument("--environment-out-json", default=str(DEFAULT_ENVIRONMENT_OUT_JSON))
    parser.add_argument("--environment-out-md", default=str(DEFAULT_ENVIRONMENT_OUT_MD))
    parser.add_argument("--queue-out-json", default=str(DEFAULT_QUEUE_OUT_JSON))
    parser.add_argument("--queue-out-csv", default=str(DEFAULT_QUEUE_OUT_CSV))
    parser.add_argument("--queue-out-md", default=str(DEFAULT_QUEUE_OUT_MD))
    parser.add_argument("--report-out-md", default=str(DEFAULT_REPORT_OUT_MD))
    parser.add_argument("--verdict-gate-out-json", default=str(DEFAULT_VERDICT_GATE_OUT_JSON))
    parser.add_argument("--verdict-gate-out-md", default=str(DEFAULT_VERDICT_GATE_OUT_MD))
    parser.add_argument("--dry-run", action=argparse.BooleanOptionalAction, default=False)
    return parser


def build_run_plan(args: argparse.Namespace) -> list[dict[str, Any]]:
    label = _sanitize_label(args.preflight_label)
    plan: list[dict[str, Any]] = []
    if not bool(args.skip_accuracy_gate):
        plan.append(
            {
                "label": "accuracy_gate",
                "cmd": [
                    sys.executable,
                    _script("run_preflight_gate.py"),
                    *_split_args(args.preflight_args),
                    "--label",
                    label,
                ],
                "expected_artifacts": [f"runs/accuracy_gate_{label}.json"],
            }
        )
    if not bool(args.skip_local_ci):
        plan.append(
            {
                "label": "local_ci",
                "cmd": [
                    sys.executable,
                    _script("run_local_ci_tests.py"),
                    *_split_args(args.local_ci_args),
                    "--out-json",
                    str(args.local_ci_out_json),
                ],
                "expected_artifacts": [str(args.local_ci_out_json)],
            }
        )
    if not bool(args.skip_requirements_lock):
        plan.append(
            {
                "label": "requirements_lock",
                "cmd": [
                    sys.executable,
                    _script("build_local_delivery_requirements_lock.py"),
                    *_split_args(args.requirements_lock_args),
                    "--out-json",
                    str(args.requirements_lock_out_json),
                    "--out-md",
                    str(args.requirements_lock_out_md),
                    "--out-txt",
                    str(args.requirements_lock_out_txt),
                ],
                "expected_artifacts": [
                    str(args.requirements_lock_out_json),
                    str(args.requirements_lock_out_md),
                    str(args.requirements_lock_out_txt),
                ],
            }
        )
    if not bool(args.skip_environment_manifest):
        plan.append(
            {
                "label": "environment_manifest",
                "cmd": [
                    sys.executable,
                    _script("build_local_delivery_environment_manifest.py"),
                    *_split_args(args.environment_manifest_args),
                    "--manifest-label",
                    label,
                    "--out-json",
                    str(args.environment_out_json),
                    "--out-md",
                    str(args.environment_out_md),
                    "--requirements-lock-json",
                    str(args.requirements_lock_out_json),
                    "--requirements-lock-md",
                    str(args.requirements_lock_out_md),
                    "--requirements-lock-txt",
                    str(args.requirements_lock_out_txt),
                ],
                "env": _environment_step_env(),
                "expected_artifacts": [str(args.environment_out_json), str(args.environment_out_md)],
            }
        )
    if not bool(args.skip_engine_provenance):
        plan.append(
            {
                "label": "engine_provenance",
                "cmd": [
                    sys.executable,
                    _script("build_local_delivery_engine_provenance.py"),
                    *_split_args(args.engine_provenance_args),
                    "--out-json",
                    str(args.engine_provenance_out_json),
                    "--out-md",
                    str(args.engine_provenance_out_md),
                ],
                "expected_artifacts": [str(args.engine_provenance_out_json), str(args.engine_provenance_out_md)],
            }
        )
    if not bool(args.skip_refresh):
        plan.append(
            {
                "label": "family_refresh",
                "cmd": [sys.executable, _script("run_family_expansion_refresh.py")],
                "expected_artifacts": [],
            }
        )
    if not bool(args.skip_queue):
        plan.append(
            {
                "label": "engine_queue",
                "cmd": [
                    sys.executable,
                    _script("build_local_engine_commercialization_queue.py"),
                    "--out-json",
                    str(args.queue_out_json),
                    "--out-csv",
                    str(args.queue_out_csv),
                    "--out-md",
                    str(args.queue_out_md),
                ],
                "expected_artifacts": [str(args.queue_out_json), str(args.queue_out_csv), str(args.queue_out_md)],
            }
        )
    if not bool(args.skip_report):
        plan.append(
            {
                "label": "commercialization_report",
                "cmd": [
                    sys.executable,
                    _script("build_commercialization_status_report.py"),
                    "--local-engine-queue-json",
                    str(args.queue_out_json),
                    "--out-md",
                    str(args.report_out_md),
                ],
                "expected_artifacts": [str(args.report_out_md)],
            }
        )
    if not bool(args.skip_verdict_gate):
        plan.append(
            {
                "label": "verdict_gate",
                "cmd": [
                    sys.executable,
                    _script("build_local_delivery_verdict_gate.py"),
                    *_split_args(args.verdict_gate_args),
                    "--claim-scope",
                    str(args.claim_scope),
                    "--preflight-json",
                    str(args.out_json),
                    "--accuracy-gate-json",
                    _accuracy_gate_artifact(label),
                    "--requirements-lock-json",
                    str(args.requirements_lock_out_json),
                    "--environment-manifest-json",
                    str(args.environment_out_json),
                    "--engine-provenance-json",
                    str(args.engine_provenance_out_json),
                    "--commercialization-queue-json",
                    str(args.queue_out_json),
                    "--status-report-md",
                    str(args.report_out_md),
                    "--out-json",
                    str(args.verdict_gate_out_json),
                    "--out-md",
                    str(args.verdict_gate_out_md),
                ],
                "expected_artifacts": [str(args.verdict_gate_out_json), str(args.verdict_gate_out_md)],
            }
        )
    return plan


def _run_step(
    label: str,
    cmd: list[str],
    dry_run: bool = False,
    env: dict[str, str] | None = None,
    expected_artifacts: list[str] | None = None,
) -> dict[str, Any]:
    env_overrides = dict(env or {})
    expected_artifacts = list(expected_artifacts or [])
    if dry_run:
        return {
            "label": label,
            "cmd": list(cmd),
            "env": env_overrides,
            "expected_artifacts": expected_artifacts,
            "returncode": 0,
            "ok": True,
            "dry_run": True,
            "stdout_tail": "",
            "stderr_tail": "",
        }
    step_env = os.environ.copy()
    step_env.update(env_overrides)
    proc = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True, env=step_env)
    return {
        "label": label,
        "cmd": list(cmd),
        "env": env_overrides,
        "expected_artifacts": expected_artifacts,
        "returncode": int(proc.returncode),
        "ok": bool(proc.returncode == 0),
        "dry_run": False,
        "stdout_tail": "\n".join((proc.stdout or "").splitlines()[-80:]),
        "stderr_tail": "\n".join((proc.stderr or "").splitlines()[-80:]),
    }


def build_payload(
    args: argparse.Namespace,
    steps: list[dict[str, Any]],
    *,
    verdict_gate_pending: bool = False,
) -> dict[str, Any]:
    label = _sanitize_label(args.preflight_label)
    accuracy_gate_artifact = _accuracy_gate_artifact(label)
    accuracy_gate_check = _accuracy_gate_check_summary(accuracy_gate_artifact, dry_run=bool(args.dry_run))
    engine_provenance_payload = {} if bool(args.dry_run) else _read_json_object(args.engine_provenance_out_json)
    engine_provenance_summary = engine_provenance_payload.get("summary")
    engine_provenance_summary = engine_provenance_summary if isinstance(engine_provenance_summary, dict) else {}
    verdict_gate_payload = {} if bool(args.dry_run) else _read_json_object(args.verdict_gate_out_json)
    verdict_gate_summary = verdict_gate_payload.get("summary")
    verdict_gate_summary = verdict_gate_summary if isinstance(verdict_gate_summary, dict) else {}
    verdict_gate_fingerprint_check = _verdict_gate_fingerprint_check_summary(verdict_gate_payload)
    requirements_lock_check = _requirements_lock_summary(args.requirements_lock_out_json, dry_run=bool(args.dry_run))
    engine_provenance_ok: bool | None
    if engine_provenance_summary:
        engine_provenance_ok = bool(
            engine_provenance_summary.get(
                "existing_engine_reused",
                engine_provenance_summary.get("provenance_ok", False),
            )
        )
    else:
        engine_provenance_ok = None if bool(args.dry_run) else False
    skipped_count = sum(1 for step in steps if bool(step.get("dry_run", False)))
    verdict_gate_step = next((step for step in steps if str(step.get("label", "")) == "verdict_gate"), None)
    verdict_gate_delivery_ready = (
        None if bool(args.dry_run) and not verdict_gate_summary else bool(verdict_gate_summary.get("delivery_ready", False))
    )
    verdict_gate_execution_ok = _verdict_gate_execution_ok(
        verdict_gate_step,
        verdict_gate_summary,
        verdict_gate_fingerprint_check,
        preflight_json=args.out_json,
    )
    verdict_gate_pending = bool(verdict_gate_pending and not args.dry_run and verdict_gate_step is None)
    verdict_gate_required_ok = bool(args.dry_run) or verdict_gate_execution_ok or verdict_gate_pending
    raw_failed = [
        step
        for step in steps
        if not bool(step.get("ok", False))
        and not (str(step.get("label", "")) == "verdict_gate" and verdict_gate_execution_ok)
    ]
    ok_count = sum(
        1
        for step in steps
        if bool(step.get("ok", False))
        or (str(step.get("label", "")) == "verdict_gate" and verdict_gate_execution_ok)
    )
    synthetic_failed: list[dict[str, Any]] = []
    if (
        not bool(args.dry_run)
        and accuracy_gate_check.get("action_required")
        and not any(str(step.get("label", "")) == "accuracy_gate" for step in raw_failed)
    ):
        synthetic_failed.append(
            {
                "label": "accuracy_gate_check",
                "cmd": [],
                "returncode": 2,
                "ok": False,
                "dry_run": False,
                "stdout_tail": "",
                "stderr_tail": str(accuracy_gate_check.get("reason", "")),
            }
        )
    if (
        not bool(args.dry_run)
        and requirements_lock_check.get("action_required")
        and not any(str(step.get("label", "")) == "requirements_lock" for step in raw_failed)
    ):
        synthetic_failed.append(
            {
                "label": "requirements_lock_completeness",
                "cmd": [],
                "returncode": 2,
                "ok": False,
                "dry_run": False,
                "stdout_tail": "",
                "stderr_tail": str(requirements_lock_check.get("next_required_step", "")),
            }
        )
    if (
        not bool(args.dry_run)
        and not verdict_gate_required_ok
        and not any(str(step.get("label", "")) == "verdict_gate" for step in raw_failed)
    ):
        synthetic_failed.append(
            {
                "label": "verdict_gate",
                "cmd": [],
                "returncode": 2,
                "ok": False,
                "dry_run": False,
                "stdout_tail": "",
                "stderr_tail": "verdict gate missing, skipped, or did not produce an auditable verdict artifact",
            }
        )
    failed = [*raw_failed, *synthetic_failed]
    first_failed = str(failed[0]["label"]) if failed else ""
    overall_ok = not failed
    artifact_diagnostics = [] if bool(args.dry_run) else _step_artifact_diagnostics(steps)
    expected_artifact_count = len(artifact_diagnostics)
    present_expected_artifact_count = sum(1 for row in artifact_diagnostics if bool(row.get("nonempty", False)))
    missing_expected_artifact_count = expected_artifact_count - present_expected_artifact_count
    if bool(args.dry_run):
        next_required_step = (
            "Dry run only. Execute the same command without `--dry-run`, then use the refreshed queue/report "
            "artifacts as the delivery preflight record."
        )
    elif verdict_gate_pending:
        next_required_step = (
            "Prerequisite preflight evidence is green; continue to the verdict gate step and record the blocked or "
            "delivery-ready verdict separately."
        )
    elif overall_ok and verdict_gate_delivery_ready is False and int(verdict_gate_summary.get("p0_blocker_count", 0) or 0) > 0:
        next_required_step = (
            "Preflight evidence is green; inspect the verdict gate P0 blockers before any delivery-ready wording."
        )
    elif overall_ok:
        next_required_step = (
            "Proceed with the scoped local delivery run, then refresh the same reporting surfaces again before "
            "assembling the result bundle."
        )
    else:
        lock_next = str(requirements_lock_check.get("next_required_step", ""))
        accuracy_next = str(accuracy_gate_check.get("next_required_step", ""))
        if first_failed == "accuracy_gate_check" and accuracy_next:
            next_required_step = accuracy_next
        elif first_failed == "requirements_lock_completeness" and lock_next:
            next_required_step = lock_next
        else:
            next_required_step = (
                f"Inspect `{first_failed}` before issuing any delivery-ready verdict; do not use stale queue/report "
                "artifacts as a substitute for a green preflight."
            )
    summary = {
        "overall_ok": overall_ok,
        "dry_run": bool(args.dry_run),
        "step_count": len(steps),
        "ok_count": ok_count,
        "failed_count": len(failed),
        "skipped_count": skipped_count,
        "first_failed_step": first_failed,
        "preflight_label": label,
        "accuracy_gate_artifact": accuracy_gate_artifact,
        "accuracy_gate_check": accuracy_gate_check,
        "local_ci_summary_json": str(args.local_ci_out_json),
        "requirements_lock_json": str(args.requirements_lock_out_json),
        "requirements_lock_md": str(args.requirements_lock_out_md),
        "requirements_lock_txt": str(args.requirements_lock_out_txt),
        "requirements_lock_check": requirements_lock_check,
        "requirements_lock_complete": requirements_lock_check.get("complete"),
        "requirements_lock_missing_package_install_targets": requirements_lock_check.get(
            "missing_package_install_targets", []
        ),
        "requirements_lock_optional_deferred_install_targets": requirements_lock_check.get(
            "optional_deferred_install_targets", []
        ),
        "requirements_lock_loose_source_requirements": requirements_lock_check.get("loose_source_requirements", []),
        "engine_provenance_json": str(args.engine_provenance_out_json),
        "engine_provenance_md": str(args.engine_provenance_out_md),
        "engine_provenance_ok": engine_provenance_ok,
        "engine_provenance_status_line": str(engine_provenance_summary.get("status_line", "")),
        "environment_manifest_json": str(args.environment_out_json),
        "environment_manifest_md": str(args.environment_out_md),
        "commercialization_queue_json": str(args.queue_out_json),
        "commercialization_queue_md": str(args.queue_out_md),
        "commercialization_status_report_md": str(args.report_out_md),
        "verdict_gate_json": str(args.verdict_gate_out_json),
        "verdict_gate_md": str(args.verdict_gate_out_md),
        "verdict_gate_delivery_ready": verdict_gate_delivery_ready,
        "verdict_gate_p0_blocker_count": int(verdict_gate_summary.get("p0_blocker_count", 0) or 0),
        "verdict_gate_pending": verdict_gate_pending,
        "verdict_gate_execution_ok": verdict_gate_execution_ok,
        "verdict_gate_required_ok": verdict_gate_required_ok,
        "verdict_gate_status_line": str(verdict_gate_summary.get("status_line", "")),
        "verdict_gate_fingerprint_check": verdict_gate_fingerprint_check,
        "expected_artifact_count": expected_artifact_count,
        "present_expected_artifact_count": present_expected_artifact_count,
        "missing_expected_artifact_count": missing_expected_artifact_count,
        "next_required_step": next_required_step,
    }
    return {"summary": summary, "steps": steps, "artifact_diagnostics": artifact_diagnostics}


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    steps: list[dict[str, Any]] = []
    for item in build_run_plan(args):
        if item["label"] == "verdict_gate" and not bool(args.dry_run):
            provisional = build_payload(args, steps, verdict_gate_pending=True)
            _write_json(args.out_json, provisional)
            _write_markdown(args.out_md, provisional)
        step = _run_step(
            item["label"],
            item["cmd"],
            dry_run=bool(args.dry_run),
            env=item.get("env"),
            expected_artifacts=item.get("expected_artifacts"),
        )
        steps.append(step)
        if bool(args.fail_fast) and not bool(step.get("ok", False)):
            break

    payload = build_payload(args, steps)
    _write_json(args.out_json, payload)
    _write_markdown(args.out_md, payload)
    print(json.dumps(payload["summary"], indent=2, ensure_ascii=False))
    if not payload["summary"]["overall_ok"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()

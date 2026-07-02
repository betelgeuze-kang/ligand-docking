#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]

DEFAULT_LIGAND_SOURCE_JSON = "runs/ligand_scaleup_benchmark_summary_current.json"
DEFAULT_ROCM_SOURCE_JSON = "runs/product_end_to_end_rocm_benchmark_current.json"
DEFAULT_LIGAND_OUT_JSON = ".betelgeuze/developer_preview_large_model_oom_guard.json"
DEFAULT_ROCM_OUT_JSON = ".betelgeuze/developer_preview_rocm_large_model_guard.json"
DEFAULT_LIGAND_OUT_MD = ".betelgeuze/developer_preview_large_model_oom_guard.md"
DEFAULT_ROCM_OUT_MD = ".betelgeuze/developer_preview_rocm_large_model_guard.md"

PACKET_TYPE = "developer_preview_large_model_oom_guard_receipt"
SCHEMA_VERSION = "developer_preview_large_model_oom_guard_receipt_v1"

CLAIM_BOUNDARY = (
    "Developer Preview large-model crash/OOM receipt only; it reads existing local benchmark summaries and "
    "fails closed when required local evidence, readiness fields, or explicit crash/OOM/failure counters do "
    "not satisfy the Gate D contract. It does not run benchmarks, execute docking, approve science or "
    "performance claims, promote paid-pilot wording, upload, email, deploy, commit, push, or mutate external "
    "state."
)

VALID_GUARD_KINDS = {"ligand-scaleup", "rocm"}
READY_STATUS_BY_KIND = {
    "ligand-scaleup": "developer_preview_large_model_oom_guard_ready",
    "rocm": "developer_preview_rocm_large_model_guard_ready",
}
BLOCKED_STATUS_BY_KIND = {
    "ligand-scaleup": "blocked_developer_preview_large_model_oom_guard",
    "rocm": "blocked_developer_preview_rocm_large_model_guard",
}
COUNT_KEY_CATEGORIES = {
    "crash_count": "crash",
    "crashes": "crash",
    "oom_count": "oom",
    "out_of_memory_count": "oom",
    "out_of_memory_events": "oom",
    "failed_count": "failure",
    "failed_jobs": "failure",
    "failure_count": "failure",
    "error_count": "failure",
    "exception_count": "failure",
}


def _resolve(path_like: str | Path, *, root: Path = ROOT) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else root / path


def _display(path_like: str | Path, *, root: Path = ROOT) -> str:
    path = Path(path_like)
    if path.is_absolute():
        try:
            return str(path.relative_to(root))
        except ValueError:
            return str(path)
    return str(path_like)


def _load_json(path_like: str | Path, *, root: Path = ROOT) -> tuple[bool, dict[str, Any]]:
    path = _resolve(path_like, root=root)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return path.is_file(), {}
    return path.is_file(), payload if isinstance(payload, dict) else {}


def _summary(payload: dict[str, Any]) -> dict[str, Any]:
    summary = payload.get("summary")
    return summary if isinstance(summary, dict) else payload


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


def _bool_true(value: Any) -> bool:
    return value is True


def _counter_value(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, str) and value.strip():
        try:
            return int(float(value.strip()))
        except ValueError:
            return None
    return None


def _iter_counter_fields(node: Any, *, prefix: str = "") -> list[dict[str, Any]]:
    fields: list[dict[str, Any]] = []
    if isinstance(node, dict):
        for key, value in node.items():
            key_text = str(key)
            normalized = key_text.lower()
            category = COUNT_KEY_CATEGORIES.get(normalized)
            if category is None and normalized.endswith("_count"):
                if "crash" in normalized:
                    category = "crash"
                elif "oom" in normalized or "out_of_memory" in normalized:
                    category = "oom"
            value_int = _counter_value(value)
            if category and value_int is not None:
                fields.append(
                    {
                        "path": f"{prefix}.{key_text}" if prefix else key_text,
                        "category": category,
                        "value": value_int,
                    }
                )
            if isinstance(value, (dict, list)):
                child_prefix = f"{prefix}.{key_text}" if prefix else key_text
                fields.extend(_iter_counter_fields(value, prefix=child_prefix))
    elif isinstance(node, list):
        for index, item in enumerate(node):
            child_prefix = f"{prefix}[{index}]" if prefix else f"[{index}]"
            fields.extend(_iter_counter_fields(item, prefix=child_prefix))
    return fields


def _coverage_missing_artifact_count(summary: dict[str, Any]) -> int:
    kpi = summary.get("kpi_summary")
    coverage = kpi.get("coverage_summary") if isinstance(kpi, dict) else {}
    return _int(coverage.get("missing_artifact_count") if isinstance(coverage, dict) else 0)


def _ligand_readiness(summary: dict[str, Any], *, source_label: str) -> tuple[bool, list[str], dict[str, Any]]:
    missing_artifact_count = _coverage_missing_artifact_count(summary)
    checks = {
        "benchmark_stage": _text(summary.get("benchmark_stage")),
        "baseline_artifact_ready": _bool_true(summary.get("baseline_artifact_ready")),
        "candidate_artifact_ready": _bool_true(summary.get("candidate_artifact_ready")),
        "comparison_artifact_ready": _bool_true(summary.get("comparison_artifact_ready")),
        "missing_artifact_count": missing_artifact_count,
    }
    blockers: list[str] = []
    if checks["benchmark_stage"] != "post_run_comparison":
        blockers.append(f"{source_label}:benchmark_stage_not_post_run_comparison")
    for field in ("baseline_artifact_ready", "candidate_artifact_ready", "comparison_artifact_ready"):
        if checks[field] is not True:
            blockers.append(f"{source_label}:{field}_not_true")
    if missing_artifact_count != 0:
        blockers.append(f"{source_label}:missing_artifact_count_nonzero")
    return not blockers, blockers, checks


def _rocm_readiness(summary: dict[str, Any], *, source_label: str) -> tuple[bool, list[str], dict[str, Any]]:
    checks = {
        "status": _text(summary.get("status")),
        "benchmark_ready": _bool_true(summary.get("benchmark_ready")),
        "actual_end_to_end_run_evidence_ready": _bool_true(
            summary.get("actual_end_to_end_run_evidence_ready")
        ),
        "run_pass": _bool_true(summary.get("run_pass")),
        "rocm_end_to_end_throughput_ready": _bool_true(summary.get("rocm_end_to_end_throughput_ready")),
        "rocm_hip_rust_runtime_ready": _bool_true(summary.get("rocm_hip_rust_runtime_ready")),
        "failed_jobs": _int(summary.get("failed_jobs")),
        "failure_rate": _float(summary.get("failure_rate")),
        "processed_jobs": _int(summary.get("processed_jobs")),
        "rocm_visible_device_count": _int(summary.get("rocm_visible_device_count")),
    }
    blockers: list[str] = []
    if checks["status"] != "product_end_to_end_rocm_benchmark_ready":
        blockers.append(f"{source_label}:status_not_ready")
    for field in (
        "benchmark_ready",
        "actual_end_to_end_run_evidence_ready",
        "run_pass",
        "rocm_end_to_end_throughput_ready",
        "rocm_hip_rust_runtime_ready",
    ):
        if checks[field] is not True:
            blockers.append(f"{source_label}:{field}_not_true")
    if checks["failed_jobs"] != 0:
        blockers.append(f"{source_label}:failed_jobs_nonzero")
    if checks["failure_rate"] != 0.0:
        blockers.append(f"{source_label}:failure_rate_nonzero")
    if checks["processed_jobs"] <= 0:
        blockers.append(f"{source_label}:processed_jobs_zero")
    if checks["rocm_visible_device_count"] <= 0:
        blockers.append(f"{source_label}:rocm_visible_device_count_zero")
    return not blockers, blockers, checks


def _source_readiness(
    guard_kind: str,
    summary: dict[str, Any],
    *,
    source_label: str,
) -> tuple[bool, list[str], dict[str, Any]]:
    if guard_kind == "ligand-scaleup":
        return _ligand_readiness(summary, source_label=source_label)
    if guard_kind == "rocm":
        return _rocm_readiness(summary, source_label=source_label)
    return False, [f"guard_kind={guard_kind}:unsupported"], {}


def _counter_totals(counter_fields: list[dict[str, Any]]) -> dict[str, int]:
    totals = {"crash": 0, "oom": 0, "failure": 0}
    for field in counter_fields:
        category = str(field.get("category", ""))
        if category in totals:
            totals[category] += _int(field.get("value"))
    return totals


def build_developer_preview_large_model_oom_guard_receipt(
    *,
    guard_kind: str = "ligand-scaleup",
    source_json: str | Path | None = None,
    root: Path = ROOT,
) -> dict[str, Any]:
    if guard_kind not in VALID_GUARD_KINDS:
        source_json = source_json or DEFAULT_LIGAND_SOURCE_JSON
        source_label = _display(source_json, root=root)
        summary: dict[str, Any] = {}
        source_present = False
        source_payload: dict[str, Any] = {}
        source_ready = False
        source_blockers = [f"guard_kind={guard_kind}:unsupported"]
        source_checks: dict[str, Any] = {}
    else:
        source_json = source_json or (
            DEFAULT_ROCM_SOURCE_JSON if guard_kind == "rocm" else DEFAULT_LIGAND_SOURCE_JSON
        )
        source_label = _display(source_json, root=root)
        source_present, source_payload = _load_json(source_json, root=root)
        summary = _summary(source_payload)
        source_ready, source_blockers, source_checks = _source_readiness(
            guard_kind,
            summary,
            source_label=source_label,
        )
        if not source_present:
            source_blockers.insert(0, f"{source_label}:missing")
        elif not summary:
            source_blockers.insert(0, f"{source_label}:invalid_or_empty")
        source_ready = bool(source_present and summary and source_ready)

    counter_fields = _iter_counter_fields(summary)
    totals = _counter_totals(counter_fields)
    nonzero_counter_fields = [field for field in counter_fields if _int(field.get("value")) != 0]
    counter_blockers = [
        f"{source_label}:{field['path']}_nonzero={field['value']}" for field in nonzero_counter_fields
    ]
    crash_count = totals["crash"]
    oom_count = totals["oom"]
    failure_signal_count = totals["failure"]
    crash_oom_counter_free = crash_count == 0 and oom_count == 0 and failure_signal_count == 0

    blockers = source_blockers + counter_blockers
    ready = bool(source_ready and crash_oom_counter_free and not blockers)
    status = READY_STATUS_BY_KIND.get(guard_kind, READY_STATUS_BY_KIND["ligand-scaleup"]) if ready else (
        BLOCKED_STATUS_BY_KIND.get(guard_kind, BLOCKED_STATUS_BY_KIND["ligand-scaleup"])
    )

    rows = [
        {
            "check": "source_readiness",
            "status": "pass" if source_ready else "blocked",
            "source_json": source_label,
            "observed": "; ".join(f"{key}={value}" for key, value in source_checks.items()),
            "required": "approved local large-model source summary satisfies the selected guard contract",
            "blockers": source_blockers,
        },
        {
            "check": "explicit_crash_oom_failure_counters",
            "status": "pass" if crash_oom_counter_free else "blocked",
            "source_json": source_label,
            "observed": (
                f"crash_count={crash_count}; oom_count={oom_count}; "
                f"failure_signal_count={failure_signal_count}"
            ),
            "required": "crash_count=0, oom_count=0, and explicit failure counters=0",
            "blockers": counter_blockers,
        },
        {
            "check": "claim_boundary",
            "status": "pass",
            "source_json": source_label,
            "observed": "claim_promotion_allowed=false; execution_enabled=false; external_state_mutated=false",
            "required": "receipt remains a Developer Preview gate artifact only",
            "blockers": [],
        },
    ]
    summary_out = {
        "packet_type": PACKET_TYPE,
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "guard_kind": guard_kind,
        "source_json": source_label,
        "source_present": source_present,
        "source_status": _text(summary.get("status") or summary.get("benchmark_stage")),
        "source_summary_ready": source_ready,
        "source_claim_safe": summary.get("claim_safe") is True,
        "source_claim_safe_status": _text(summary.get("claim_safe_status")),
        "regression_guardrail_passed": summary.get("claim_safe") is True,
        "performance_regression_claim_allowed": False,
        "crash_oom_free": ready,
        "crash_count": crash_count,
        "oom_count": oom_count,
        "failure_signal_count": failure_signal_count,
        "explicit_counter_field_count": len(counter_fields),
        "nonzero_counter_field_count": len(nonzero_counter_fields),
        "blocker_count": len(blockers),
        "blockers": blockers,
        "claim_promotion_allowed": False,
        "execution_enabled": False,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": "Attach this receipt to the Developer Preview final gate audit."
        if ready
        else "Refresh the selected local large-model source summary and rebuild this fail-closed Gate D receipt.",
    }
    return {"summary": summary_out, "rows": rows}


def _write_json(path_like: str | Path, payload: dict[str, Any], *, root: Path = ROOT) -> None:
    path = _resolve(path_like, root=root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _render_md(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# Developer Preview Large Model OOM Guard Receipt",
        "",
        f"- status: `{summary['status']}`",
        f"- guard_kind: `{summary['guard_kind']}`",
        f"- source_json: `{summary['source_json']}`",
        f"- crash_oom_free: `{summary['crash_oom_free']}`",
        f"- crash_count: `{summary['crash_count']}`",
        f"- oom_count: `{summary['oom_count']}`",
        f"- failure_signal_count: `{summary['failure_signal_count']}`",
        f"- blocker_count: `{summary['blocker_count']}`",
        "",
        "| check | status | observed | blockers |",
        "| --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        blockers = ";".join(str(item) for item in row.get("blockers", [])) or "-"
        lines.append(f"| `{row['check']}` | `{row['status']}` | `{row['observed']}` | `{blockers}` |")
    lines.extend(["", CLAIM_BOUNDARY, ""])
    return "\n".join(lines)


def _write_text(path_like: str | Path, text: str, *, root: Path = ROOT) -> None:
    path = _resolve(path_like, root=root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _default_out_json(guard_kind: str) -> str:
    return DEFAULT_ROCM_OUT_JSON if guard_kind == "rocm" else DEFAULT_LIGAND_OUT_JSON


def _default_out_md(guard_kind: str) -> str:
    return DEFAULT_ROCM_OUT_MD if guard_kind == "rocm" else DEFAULT_LIGAND_OUT_MD


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build Developer Preview large-model crash/OOM receipt.")
    parser.add_argument("--guard-kind", choices=sorted(VALID_GUARD_KINDS), default="ligand-scaleup")
    parser.add_argument("--source-json")
    parser.add_argument("--out-json")
    parser.add_argument("--out-md")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    payload = build_developer_preview_large_model_oom_guard_receipt(
        guard_kind=args.guard_kind,
        source_json=args.source_json,
    )
    out_json = args.out_json or _default_out_json(args.guard_kind)
    out_md = args.out_md or _default_out_md(args.guard_kind)
    _write_json(out_json, payload)
    _write_text(out_md, _render_md(payload))
    return 0 if payload["summary"]["status"] == READY_STATUS_BY_KIND[args.guard_kind] else 1


if __name__ == "__main__":
    raise SystemExit(main())

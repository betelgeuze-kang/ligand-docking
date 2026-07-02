#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]

DEFAULT_REGISTER_MD = "docs/developer_preview_final_gate_action_register.md"
DEFAULT_OUT_JSON = "runs/developer_preview_final_gate_audit_current.json"
DEFAULT_OUT_CSV = "runs/developer_preview_final_gate_audit_current.csv"
DEFAULT_OUT_MD = "runs/developer_preview_final_gate_audit_current.md"

PACKET_TYPE = "developer_preview_final_gate_audit"
SCHEMA_VERSION = "developer_preview_final_gate_audit_v1"

CLAIM_BOUNDARY = (
    "Developer Preview final gate audit only; it reads local reviewed receipt artifacts for the six "
    "Developer Preview gates and fails closed when receipts are missing or incomplete. It does not run "
    "clean checkouts, execute benchmarks, run Vina/GNINA, approve reviews, promote paid-pilot wording, "
    "upload, email, deploy, or mutate external state."
)

CSV_FIELDS = [
    "priority",
    "gate_id",
    "status",
    "ready",
    "receipt_artifacts",
    "present_receipt_count",
    "required_receipt_count",
    "primary_metric",
    "secondary_metric",
    "blocker",
    "next_required_step",
    "execution_enabled",
    "external_state_mutated",
    "claim_promotion_allowed",
]


GATE_SPECS: list[dict[str, Any]] = [
    {
        "priority": "A",
        "gate_id": "benchmark_results_clean_checkout_regenerated",
        "receipt_artifacts": [
            {
                "path": ".betelgeuze/developer_preview_clean_checkout_benchmark_receipt.json",
                "required_status": "developer_preview_clean_checkout_benchmark_receipt_ready",
                "required_true_fields": [
                    "clean_checkout_benchmark_regenerated",
                    "ai_verify_passed",
                    "reviewed_receipt_attached",
                ],
                "required_zero_fields": ["blocker_count", "failed_count"],
            }
        ],
        "missing_blocker": "clean_checkout_benchmark_receipt_missing",
        "next_required_step": (
            "Run the clean-checkout benchmark regeneration command from the action register and attach "
            "a reviewed receipt at .betelgeuze/developer_preview_clean_checkout_benchmark_receipt.json."
        ),
    },
    {
        "priority": "B",
        "gate_id": "silent_import_loss_zero",
        "receipt_artifacts": [
            {
                "path": ".betelgeuze/developer_preview_silent_import_loss_receipt.json",
                "required_status": "developer_preview_silent_import_loss_receipt_ready",
                "required_true_fields": [
                    "import_cli_tests_passed",
                    "capability_matrix_checked",
                    "silent_import_loss_zero",
                ],
                "required_zero_fields": [
                    "blocker_count",
                    "missing_required_surface_count",
                    "unimportable_required_surface_count",
                ],
            }
        ],
        "missing_blocker": "silent_import_loss_receipt_missing",
        "next_required_step": (
            "Run the DP import/CLI tests plus capability matrix check and attach a receipt proving zero "
            "required import loss."
        ),
    },
    {
        "priority": "C",
        "gate_id": "selected_medium_models_pass_or_approved_review",
        "receipt_artifacts": [
            {
                "path": ".betelgeuze/developer_preview_medium_pose_sampling_readiness.json",
                "required_status": "product_pose_sampling_readiness_ready",
                "required_true_fields": ["pose_sampling_readiness_ready"],
                "required_zero_fields": ["blocker_count"],
            },
            {
                "path": ".betelgeuze/developer_preview_medium_backmapping_smoke.json",
                "required_status": "backmapping_scoring_batch_smoke_benchmark_ready",
                "required_true_fields": ["benchmark_ready"],
                "required_zero_fields": ["blocker_count", "failed_count"],
            },
        ],
        "review_artifact": {
            "path": ".betelgeuze/developer_preview_medium_model_operator_review.json",
            "required_status": "developer_preview_medium_model_operator_review_approved",
            "required_true_fields": ["approved_review"],
            "required_zero_fields": ["blocker_count"],
        },
        "missing_blocker": "selected_medium_model_receipts_or_review_missing",
        "next_required_step": (
            "Run the frozen selected-medium-model pose/backmapping smoke receipts, or attach an approved "
            "operator review explaining each failed medium model."
        ),
    },
    {
        "priority": "D",
        "gate_id": "large_models_crash_oom_free",
        "receipt_artifacts": [
            {
                "path": ".betelgeuze/developer_preview_large_model_oom_guard.json",
                "required_status": "developer_preview_large_model_oom_guard_ready",
                "required_true_fields": ["crash_oom_free"],
                "required_zero_fields": ["blocker_count", "crash_count", "oom_count"],
            },
            {
                "path": ".betelgeuze/developer_preview_rocm_large_model_guard.json",
                "required_status": "developer_preview_rocm_large_model_guard_ready",
                "required_true_fields": ["crash_oom_free"],
                "required_zero_fields": ["blocker_count", "crash_count", "oom_count"],
            },
        ],
        "missing_blocker": "large_model_crash_oom_receipts_missing",
        "next_required_step": (
            "Run the large-model crash/OOM guard on the approved local hardware/profile and attach "
            "reviewed receipts with explicit crash_count=0 and oom_count=0."
        ),
    },
    {
        "priority": "E",
        "gate_id": "linux_windows_reproducibility_confirmed",
        "receipt_artifacts": [
            {
                "path": ".betelgeuze/developer_preview_linux_reproducibility_receipt.json",
                "required_status": "developer_preview_platform_reproducibility_receipt_ready",
                "required_true_fields": ["command_set_passed", "linux_receipt"],
                "required_zero_fields": ["blocker_count"],
            },
            {
                "path": ".betelgeuze/developer_preview_windows_reproducibility_receipt.json",
                "required_status": "developer_preview_platform_reproducibility_receipt_ready",
                "required_true_fields": ["command_set_passed", "windows_receipt"],
                "required_zero_fields": ["blocker_count"],
            },
        ],
        "missing_blocker": "linux_windows_reproducibility_receipts_missing",
        "next_required_step": (
            "Attach matching Linux and Windows command-set receipts with Python/dependency inputs and "
            "expected skips recorded."
        ),
    },
    {
        "priority": "F",
        "gate_id": "new_user_core_workflow_observation_passed",
        "receipt_artifacts": [
            {
                "path": ".betelgeuze/developer_preview_new_user_execution_work_order.json",
                "required_status": "product_execution_work_order_ready",
                "required_true_fields": ["profile_command_generated"],
                "required_zero_fields": ["blocker_count"],
            },
            {
                "path": ".betelgeuze/developer_preview_new_user_execution_preflight.json",
                "required_status": "product_execution_preflight_ready",
                "required_true_fields": ["validated_without_execution"],
                "required_zero_fields": ["blocker_count", "unknown_arg_count"],
            },
            {
                "path": ".betelgeuze/developer_preview_new_user_observation_receipt.json",
                "required_status": "developer_preview_new_user_observation_receipt_ready",
                "required_true_fields": ["observer_signoff", "anonymized_notes_only"],
                "required_zero_fields": ["blocker_count", "hidden_state_blocker_count"],
            },
        ],
        "missing_blocker": "new_user_workflow_observation_receipts_missing",
        "next_required_step": (
            "Run the new-user work-order/preflight path and attach an observer signoff receipt with only "
            "derived/anonymized metadata."
        ),
    },
]


def _resolve(path_like: str | Path, *, root: Path = ROOT) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else root / path


def _display(path_like: str | Path, *, root: Path = ROOT) -> str:
    path = Path(str(path_like))
    if path.is_absolute():
        try:
            return str(path.relative_to(root))
        except ValueError:
            return str(path)
    return str(path_like)


def _read_json(path_like: str | Path, *, root: Path = ROOT) -> dict[str, Any]:
    path = _resolve(path_like, root=root)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _read_text(path_like: str | Path, *, root: Path = ROOT) -> str:
    path = _resolve(path_like, root=root)
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def _summary(payload: dict[str, Any]) -> dict[str, Any]:
    summary = payload.get("summary")
    return summary if isinstance(summary, dict) else payload


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _int(value: Any) -> int:
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0


def _bool_true(value: Any) -> bool:
    return value is True


def _metric(label: str, value: Any) -> str:
    rendered = "true" if value is True else "false" if value is False else _text(value)
    return f"{label}={rendered}" if rendered else ""


def _join_metrics(*parts: str) -> str:
    return "; ".join(part for part in parts if part)


def _artifact_check(artifact: dict[str, Any], *, root: Path) -> dict[str, Any]:
    artifact_path = artifact["path"]
    path = _resolve(artifact_path, root=root)
    present = path.is_file()
    summary = _summary(_read_json(artifact_path, root=root)) if present else {}
    status = _text(summary.get("status"))
    expected_status = _text(artifact.get("required_status"))
    status_ok = bool(status and status == expected_status)
    missing_true_fields = [
        field for field in artifact.get("required_true_fields", []) if not _bool_true(summary.get(field))
    ]
    nonzero_fields = [
        field for field in artifact.get("required_zero_fields", []) if _int(summary.get(field)) != 0
    ]
    ready = present and status_ok and not missing_true_fields and not nonzero_fields
    blockers: list[str] = []
    if not present:
        blockers.append(f"{artifact_path}:missing")
    elif not status_ok:
        blockers.append(f"{artifact_path}:status={status or 'missing'}")
    blockers.extend(f"{artifact_path}:{field}_not_true" for field in missing_true_fields)
    blockers.extend(f"{artifact_path}:{field}_nonzero" for field in nonzero_fields)
    return {
        "path": artifact_path,
        "present": present,
        "ready": ready,
        "status": status,
        "blockers": blockers,
    }


def _gate_row(spec: dict[str, Any], *, root: Path) -> dict[str, Any]:
    checks = [_artifact_check(artifact, root=root) for artifact in spec["receipt_artifacts"]]
    required_ready = all(check["ready"] for check in checks)
    review_spec = spec.get("review_artifact")
    review_check = _artifact_check(review_spec, root=root) if isinstance(review_spec, dict) else None
    review_ready = bool(review_check and review_check["ready"])
    ready = required_ready or review_ready
    blockers = [
        blocker
        for check in checks
        for blocker in check["blockers"]
        if not review_ready
    ]
    if review_check and not required_ready and not review_ready:
        blockers.extend(review_check["blockers"])
    if not blockers and not ready:
        blockers = [spec["missing_blocker"]]
    present_count = sum(1 for check in checks if check["present"])
    required_count = len(checks)
    if review_check and review_check["present"]:
        present_count += 1
    receipt_paths = [check["path"] for check in checks]
    if review_check:
        receipt_paths.append(review_check["path"])
    return {
        "priority": spec["priority"],
        "gate_id": spec["gate_id"],
        "status": "developer_preview_gate_ready" if ready else "blocked_developer_preview_gate",
        "ready": ready,
        "receipt_artifacts": ";".join(receipt_paths),
        "present_receipt_count": present_count,
        "required_receipt_count": required_count,
        "primary_metric": _join_metrics(
            _metric("required_ready", required_ready),
            _metric("review_ready", review_ready),
        ),
        "secondary_metric": _join_metrics(
            _metric("present_receipts", present_count),
            _metric("required_receipts", required_count),
        ),
        "blocker": "" if ready else (blockers[0] if blockers else spec["missing_blocker"]),
        "blockers": blockers,
        "next_required_step": spec["next_required_step"],
        "execution_enabled": False,
        "external_state_mutated": False,
        "claim_promotion_allowed": False,
        "claim_boundary": CLAIM_BOUNDARY,
    }


def build_developer_preview_final_gate_audit(
    *,
    register_md: str | Path = DEFAULT_REGISTER_MD,
    root: Path = ROOT,
) -> dict[str, Any]:
    register_text = _read_text(register_md, root=root)
    materialized_gate_ids = {spec["gate_id"] for spec in GATE_SPECS if spec["gate_id"] in register_text}
    rows = [_gate_row(spec, root=root) for spec in GATE_SPECS]
    ready_rows = [row for row in rows if row["ready"]]
    blocked_rows = [row for row in rows if not row["ready"]]
    missing_receipt_count = sum(
        max(0, int(row["required_receipt_count"]) - int(row["present_receipt_count"]))
        for row in rows
        if not row["ready"]
    )
    clean_ready = len(ready_rows) == len(rows)
    summary = {
        "packet_type": PACKET_TYPE,
        "schema_version": SCHEMA_VERSION,
        "status": "developer_preview_final_gate_audit_ready"
        if clean_ready
        else "blocked_developer_preview_final_gate_audit",
        "developer_preview_clean_baseline_ready": clean_ready,
        "claim_promotion_allowed": False,
        "gate_count": len(rows),
        "ready_gate_count": len(ready_rows),
        "blocked_gate_count": len(blocked_rows),
        "missing_receipt_count": missing_receipt_count,
        "register_gate_id_count": len(materialized_gate_ids),
        "register_gate_ids_complete": materialized_gate_ids == {spec["gate_id"] for spec in GATE_SPECS},
        "primary_blocker_id": blocked_rows[0]["gate_id"] if blocked_rows else "",
        "primary_blocker": blocked_rows[0]["blocker"] if blocked_rows else "",
        "blockers": [f"{row['gate_id']}:{row['blocker']}" for row in blocked_rows],
        "execution_enabled": False,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": blocked_rows[0]["next_required_step"]
        if blocked_rows
        else "Developer Preview final gates are ready for operator review.",
    }
    return {"summary": summary, "rows": rows}


def _write_json(path_like: str | Path, payload: dict[str, Any], *, root: Path = ROOT) -> None:
    path = _resolve(path_like, root=root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _csv_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, list):
        return ";".join(_text(item) for item in value if _text(item))
    return _text(value)


def _write_csv(path_like: str | Path, rows: list[dict[str, Any]], *, root: Path = ROOT) -> None:
    path = _resolve(path_like, root=root)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: _csv_value(row.get(field)) for field in CSV_FIELDS})


def _render_md(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# Developer Preview Final Gate Audit",
        "",
        f"- status: `{summary['status']}`",
        f"- developer_preview_clean_baseline_ready: `{summary['developer_preview_clean_baseline_ready']}`",
        f"- ready_gate_count: `{summary['ready_gate_count']}` / `{summary['gate_count']}`",
        f"- missing_receipt_count: `{summary['missing_receipt_count']}`",
        f"- primary_blocker_id: `{summary['primary_blocker_id']}`",
        "",
        "| priority | gate | status | receipts | blocker |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['priority']}` | `{row['gate_id']}` | `{row['status']}` | "
            f"`{row['present_receipt_count']}/{row['required_receipt_count']}` | `{row['blocker']}` |"
        )
    lines.extend(["", CLAIM_BOUNDARY, ""])
    return "\n".join(lines)


def _write_text(path_like: str | Path, text: str, *, root: Path = ROOT) -> None:
    path = _resolve(path_like, root=root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build Developer Preview final gate audit.")
    parser.add_argument("--register-md", default=DEFAULT_REGISTER_MD)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    payload = build_developer_preview_final_gate_audit(register_md=args.register_md)
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"])
    _write_text(args.out_md, _render_md(payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

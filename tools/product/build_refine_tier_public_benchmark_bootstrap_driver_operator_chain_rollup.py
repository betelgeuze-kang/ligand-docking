#!/usr/bin/env python3
"""Read-only rollup for the R9 bootstrap-driver operator closure chain."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows
from tools.product.build_refine_tier_public_benchmark_bootstrap_driver_operator_attestation_merge_preview import (
    DEFAULT_OUT_JSON as DEFAULT_MERGE_PREVIEW_JSON,
)
from tools.product.build_refine_tier_public_benchmark_bootstrap_driver_operator_attestation_template import (
    DEFAULT_OUT_JSON as DEFAULT_ATTESTATION_JSON,
)
from tools.product.build_refine_tier_public_benchmark_bootstrap_driver_operator_field_triage import (
    DEFAULT_OUT_JSON as DEFAULT_FIELD_TRIAGE_JSON,
)
from tools.product.build_refine_tier_public_benchmark_bootstrap_driver_operator_machine_prefill_template import (
    DEFAULT_OUT_JSON as DEFAULT_PREFILL_JSON,
)
from tools.product.build_refine_tier_public_benchmark_bootstrap_driver_operator_staging_apply import (
    DEFAULT_OUT_JSON as DEFAULT_STAGING_APPLY_JSON,
)
from tools.product.build_refine_tier_public_benchmark_statistical_support_metric_source_payload_operator_receipt import (
    APPROVAL_TOKEN,
)

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT_JSON = "config/refine_tier_public_benchmark_bootstrap_driver_operator_chain_rollup_current.json"
DEFAULT_OUT_CSV = "config/refine_tier_public_benchmark_bootstrap_driver_operator_chain_rollup_current.csv"
DEFAULT_OUT_MD = "docs/refine_tier_public_benchmark_bootstrap_driver_operator_chain_rollup_current.md"

CLAIM_BOUNDARY = (
    "R9 bootstrap-driver operator chain rollup only summarizes the read-only staging, triage, "
    "prefill, attestation, and merge-preview packets. It does not edit worksheets, mark approvals, "
    "write metric payload JSON, copy canonical receipts, promote canonical intake, change production "
    "scoring, run docking/MD, download, upload, email, delete, commit, push, or mutate external state."
)


def _resolve(path_like: str | Path, *, root: Path = ROOT) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else root / path


def _display(path_like: str | Path, *, root: Path = ROOT) -> str:
    path = _resolve(path_like, root=root)
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return _text(value).lower() in {"1", "true", "yes", "y"}


def _int(value: Any) -> int:
    try:
        return int(float(_text(value)))
    except (TypeError, ValueError):
        return 0


def _read_json(path_like: str | Path, *, root: Path) -> tuple[dict[str, Any], bool]:
    path = _resolve(path_like, root=root)
    if not path.is_file():
        return {}, False
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}, True
    return payload if isinstance(payload, dict) else {}, True


def _summary(payload: dict[str, Any]) -> dict[str, Any]:
    summary = payload.get("summary")
    return summary if isinstance(summary, dict) else {}


def _stage_row(stage_id: str, artifact: str | Path, summary: dict[str, Any], present: bool, *, root: Path) -> dict[str, Any]:
    status = _text(summary.get("status")) if summary else ""
    stage_ready = not status.startswith("blocked_") and bool(status)
    if stage_id == "field_triage":
        stage_ready = stage_ready and _int(summary.get("machine_gap_pending_field_count")) == 0
    elif stage_id == "machine_prefill":
        stage_ready = stage_ready and _int(summary.get("machine_remaining_field_count")) == 0
    elif stage_id == "operator_attestation_template":
        stage_ready = stage_ready and _int(summary.get("prefill_row_fingerprint_count")) > 0
    elif stage_id == "attestation_merge_preview":
        stage_ready = _bool(summary.get("attestation_merge_ready"))
    elif stage_id == "staging_apply_preview":
        stage_ready = present and bool(status)
    return {
        "stage_id": stage_id,
        "artifact": _display(artifact, root=root),
        "artifact_present": present,
        "status": status or "missing",
        "stage_surface_ready": stage_ready,
        "row_count": _int(
            summary.get("worksheet_row_count")
            or summary.get("row_count")
            or summary.get("prefill_row_count")
            or summary.get("attestation_row_count")
            or summary.get("merge_preview_row_count")
        ),
        "pass_row_count": _int(
            summary.get("pass_row_count")
            or summary.get("attestation_pass_row_count")
            or summary.get("merge_preview_pass_row_count")
        ),
        "blocked_row_count": _int(
            summary.get("blocked_row_count")
            or summary.get("attestation_blocked_row_count")
            or summary.get("merge_preview_blocked_row_count")
        ),
        "manual_pending_field_count": _int(summary.get("operator_manual_pending_field_count")),
        "operator_only_pending_field_count": _int(summary.get("operator_only_pending_field_count")),
        "machine_supported_field_count": _int(
            summary.get("machine_supported_pending_field_count")
            or summary.get("machine_supported_prefilled_field_count")
            or summary.get("machine_prefilled_field_count")
        ),
        "machine_gap_field_count": _int(summary.get("machine_gap_pending_field_count")),
        "prefill_fingerprint_verified_count": _int(summary.get("prefill_row_fingerprint_verified_count")),
        "prefill_fingerprint_mismatch_count": _int(summary.get("prefill_row_fingerprint_mismatch_count")),
        "merged_candidate_row_count": _int(summary.get("merged_candidate_row_count")),
        "most_common_row_blocker": _text(summary.get("most_common_row_blocker")),
        "blocker_count": _int(summary.get("blocker_count")),
        "blockers": ";".join(summary.get("blockers", [])) if isinstance(summary.get("blockers"), list) else _text(summary.get("blockers")),
        "payload_write_allowed": _bool(summary.get("payload_write_allowed")),
        "canonical_receipt_write_allowed": _bool(summary.get("canonical_receipt_write_allowed")),
        "claim_promotion_allowed": _bool(summary.get("claim_promotion_allowed")),
        "external_state_mutated": _bool(summary.get("external_state_mutated")),
    }


def build_refine_tier_public_benchmark_bootstrap_driver_operator_chain_rollup(
    *,
    staging_apply_json: str | Path = DEFAULT_STAGING_APPLY_JSON,
    field_triage_json: str | Path = DEFAULT_FIELD_TRIAGE_JSON,
    machine_prefill_json: str | Path = DEFAULT_PREFILL_JSON,
    attestation_json: str | Path = DEFAULT_ATTESTATION_JSON,
    merge_preview_json: str | Path = DEFAULT_MERGE_PREVIEW_JSON,
    root: str | Path = ROOT,
) -> dict[str, Any]:
    root_path = Path(root)
    specs = [
        ("staging_apply_preview", staging_apply_json),
        ("field_triage", field_triage_json),
        ("machine_prefill", machine_prefill_json),
        ("operator_attestation_template", attestation_json),
        ("attestation_merge_preview", merge_preview_json),
    ]
    rows: list[dict[str, Any]] = []
    summaries: dict[str, dict[str, Any]] = {}
    present_by_stage: dict[str, bool] = {}
    for stage_id, artifact in specs:
        payload, present = _read_json(artifact, root=root_path)
        summary = _summary(payload)
        summaries[stage_id] = summary
        present_by_stage[stage_id] = present
        rows.append(_stage_row(stage_id, artifact, summary, present, root=root_path))

    missing_stages = [row["stage_id"] for row in rows if row["artifact_present"] is not True]
    surface_ready = bool(not missing_stages and all(row["stage_surface_ready"] for row in rows[:-1]))
    merge = summaries["attestation_merge_preview"]
    operator_chain_closure_ready = bool(
        surface_ready
        and _bool(merge.get("attestation_merge_ready"))
        and _int(merge.get("merge_preview_pass_row_count")) == _int(merge.get("prefill_row_count"))
        and _int(merge.get("merged_candidate_row_count")) == _int(merge.get("prefill_row_count"))
        and _int(merge.get("prefill_row_count")) > 0
    )

    blockers: list[str] = []
    if missing_stages:
        blockers.append("operator_chain_artifacts_missing")
    if _int(summaries["field_triage"].get("machine_gap_pending_field_count")):
        blockers.append("machine_supported_field_evidence_gap_present")
    if _int(summaries["machine_prefill"].get("machine_remaining_field_count")):
        blockers.append("machine_supported_prefill_incomplete")
    attestation = summaries["operator_attestation_template"]
    if _int(attestation.get("attestation_blocked_row_count")):
        blockers.append("operator_attestation_rows_blocked")
    if _int(merge.get("merge_preview_blocked_row_count")):
        blockers.append("attestation_merge_rows_blocked")
    if _int(merge.get("prefill_row_fingerprint_mismatch_count")):
        blockers.append("prefill_row_fingerprint_mismatch_present")
    if not operator_chain_closure_ready:
        blockers.append("operator_chain_closure_not_ready")

    summary = {
        "packet_type": "refine_tier_public_benchmark_bootstrap_driver_operator_chain_rollup",
        "status": (
            "refine_tier_public_benchmark_bootstrap_driver_operator_chain_rollup_ready"
            if operator_chain_closure_ready
            else "blocked_refine_tier_public_benchmark_bootstrap_driver_operator_chain_rollup"
        ),
        "stage_count": len(rows),
        "stage_artifact_present_count": sum(1 for row in rows if row["artifact_present"] is True),
        "stage_surface_ready_count": sum(1 for row in rows if row["stage_surface_ready"] is True),
        "operator_chain_surface_ready": surface_ready,
        "operator_chain_closure_ready": operator_chain_closure_ready,
        "source_staging_operator_manual_pending_field_count": _int(
            summaries["staging_apply_preview"].get("operator_manual_pending_field_count")
        ),
        "machine_supported_pending_field_count": _int(
            summaries["field_triage"].get("machine_supported_pending_field_count")
        ),
        "machine_supported_prefilled_field_count": _int(
            summaries["machine_prefill"].get("machine_supported_prefilled_field_count")
        ),
        "operator_only_pending_field_count": _int(attestation.get("operator_only_pending_field_count")),
        "machine_gap_pending_field_count": _int(
            summaries["field_triage"].get("machine_gap_pending_field_count")
        ),
        "attestation_row_count": _int(attestation.get("attestation_row_count")),
        "attestation_blocked_row_count": _int(attestation.get("attestation_blocked_row_count")),
        "attestation_merge_ready": _bool(merge.get("attestation_merge_ready")),
        "merge_preview_pass_row_count": _int(merge.get("merge_preview_pass_row_count")),
        "merge_preview_blocked_row_count": _int(merge.get("merge_preview_blocked_row_count")),
        "prefill_row_fingerprint_verified_count": _int(merge.get("prefill_row_fingerprint_verified_count")),
        "prefill_row_fingerprint_mismatch_count": _int(merge.get("prefill_row_fingerprint_mismatch_count")),
        "merged_candidate_row_count": _int(merge.get("merged_candidate_row_count")),
        "final_blocker_stage_id": (
            "attestation_merge_preview"
            if _int(merge.get("merge_preview_blocked_row_count"))
            else "operator_attestation_template"
            if _int(attestation.get("attestation_blocked_row_count"))
            else ""
        ),
        "final_blocker": _text(merge.get("most_common_row_blocker"))
        or _text(attestation.get("most_common_row_blocker")),
        "approval_token_required": APPROVAL_TOKEN,
        "payload_write_allowed": False,
        "canonical_receipt_write_allowed": False,
        "canonical_intake_promotion_allowed": False,
        "claim_promotion_allowed": False,
        "production_score_mutation_allowed": False,
        "external_state_mutated": False,
        "blocker_count": len(blockers),
        "blockers": blockers,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "Fill the operator-only attestation rows, rerun attestation merge preview, then rerun staging apply "
            "against the merged candidate worksheet before any payload or canonical receipt write."
            if not operator_chain_closure_ready
            else "Operator chain closure candidate is ready for staging apply preview; writes remain disabled in this rollup."
        ),
    }
    return {"summary": summary, "rows": rows}


def _write_json(path_like: str | Path, payload: dict[str, Any], *, root: Path) -> None:
    path = _resolve(path_like, root=root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_md(path_like: str | Path, payload: dict[str, Any], *, root: Path) -> None:
    path = _resolve(path_like, root=root)
    s = payload["summary"]
    lines = [
        "# R9 Bootstrap Driver Operator Chain Rollup",
        "",
        f"- status: `{s['status']}`",
        f"- operator_chain_surface_ready: `{s['operator_chain_surface_ready']}`",
        f"- operator_chain_closure_ready: `{s['operator_chain_closure_ready']}`",
        f"- source_staging_operator_manual_pending_field_count: `{s['source_staging_operator_manual_pending_field_count']}`",
        f"- machine_supported_prefilled_field_count: `{s['machine_supported_prefilled_field_count']}`",
        f"- operator_only_pending_field_count: `{s['operator_only_pending_field_count']}`",
        f"- prefill_row_fingerprint_verified_count: `{s['prefill_row_fingerprint_verified_count']}`",
        f"- prefill_row_fingerprint_mismatch_count: `{s['prefill_row_fingerprint_mismatch_count']}`",
        f"- merged_candidate_row_count: `{s['merged_candidate_row_count']}`",
        f"- final_blocker_stage_id: `{s['final_blocker_stage_id']}`",
        f"- final_blocker: `{s['final_blocker']}`",
        f"- claim_promotion_allowed: `{s['claim_promotion_allowed']}`",
        "",
        "## Stages",
        "",
        "| stage | present | surface ready | status | rows | pass | blocked | blocker |",
        "| --- | --- | --- | --- | ---: | ---: | ---: | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['stage_id']}` | `{row['artifact_present']}` | `{row['stage_surface_ready']}` | "
            f"`{row['status']}` | `{row['row_count']}` | `{row['pass_row_count']}` | "
            f"`{row['blocked_row_count']}` | `{row['most_common_row_blocker']}` |"
        )
    lines.extend(["", "## Claim Boundary", "", s["claim_boundary"], "", "## Next Step", "", s["next_required_step"], ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build R9 bootstrap-driver operator chain rollup.")
    parser.add_argument("--staging-apply-json", default=DEFAULT_STAGING_APPLY_JSON)
    parser.add_argument("--field-triage-json", default=DEFAULT_FIELD_TRIAGE_JSON)
    parser.add_argument("--machine-prefill-json", default=DEFAULT_PREFILL_JSON)
    parser.add_argument("--attestation-json", default=DEFAULT_ATTESTATION_JSON)
    parser.add_argument("--merge-preview-json", default=DEFAULT_MERGE_PREVIEW_JSON)
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> dict[str, Any]:
    args = parse_args(argv)
    root = Path(args.root)
    payload = build_refine_tier_public_benchmark_bootstrap_driver_operator_chain_rollup(
        staging_apply_json=args.staging_apply_json,
        field_triage_json=args.field_triage_json,
        machine_prefill_json=args.machine_prefill_json,
        attestation_json=args.attestation_json,
        merge_preview_json=args.merge_preview_json,
        root=root,
    )
    _write_json(args.out_json, payload, root=root)
    write_csv_rows(_resolve(args.out_csv, root=root), payload["rows"])
    _write_md(args.out_md, payload, root=root)
    print(json.dumps(payload["summary"], indent=2, ensure_ascii=False, sort_keys=True))
    return payload


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]

DEFAULT_MATERIALIZATION_JSON = "runs/pdbbind_casf_pose_affinity_materialization_manifest_current.json"
DEFAULT_RESULTS_JSON = "runs/pdbbind_casf_pose_affinity_results_current.json"
DEFAULT_PHASE2_AUDIT_JSON = "runs/public_benchmark_phase2_harness_audit_current.json"
DEFAULT_PROVENANCE_JSON = "runs/pdbbind_casf_pose_affinity_result_provenance_current.json"
DEFAULT_SCORECARD_JSON = "runs/pdbbind_casf_pose_affinity_scorecard_current.json"
DEFAULT_RECEIPT_JSON = (
    "runs/refine_tier_public_benchmark_statistical_support_metric_source_payload_operator_receipt_current.json"
)
DEFAULT_RECEIPT_CSV = (
    "config/refine_tier_public_benchmark_statistical_support_metric_source_payload_operator_receipt_current.csv"
)
DEFAULT_BENCHMARK_LEDGER_JSON = "runs/benchmark_ledger_current.json"
DEFAULT_VINA_GNINA_WORK_ORDER_JSON = "runs/public_benchmark_vina_gnina_comparison_work_order_current.json"
DEFAULT_OUT_JSON = "runs/public_benchmark_external_receipts_audit_current.json"
DEFAULT_OUT_CSV = "runs/public_benchmark_external_receipts_audit_current.csv"
DEFAULT_OUT_MD = "runs/public_benchmark_external_receipts_audit_current.md"

PACKET_TYPE = "public_benchmark_external_receipts_audit"
SCHEMA_VERSION = "public_benchmark_external_receipts_audit_v1"

CLAIM_BOUNDARY = (
    "Public benchmark external receipts audit only; it reads local CASF/PDBBind, Phase 2 harness, "
    "operator receipt, provenance, scorecard, and benchmark-ledger artifacts. It does not download datasets, "
    "run docking, run Vina/GNINA, compute new benchmark metrics, approve receipt rows, promote claims, "
    "upload, email, deploy, or mutate external state."
)

STEP_IDS = (
    "casf_pdbbind_default_manifest",
    "subset_dry_run",
    "pose_rmsd_2a_5a",
    "posebusters_validity",
    "vina_gnina_same_input_comparison",
    "benchmark_receipt_attach",
    "benchmark_ledger_review",
)

CSV_FIELDS = [
    "step_id",
    "status",
    "ready",
    "evidence_artifact",
    "primary_metric",
    "secondary_metric",
    "blocker",
    "next_required_step",
    "execution_enabled",
    "external_state_mutated",
    "claim_promotion_allowed",
]


def _resolve(path_like: str | Path, *, root: Path = ROOT) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else root / path


def _display(path_like: str | Path, *, root: Path = ROOT) -> str:
    text = _text(path_like)
    if not text:
        return ""
    path = Path(text)
    if path.is_absolute():
        try:
            return str(path.relative_to(root))
        except ValueError:
            return str(path)
    return text


def _read_json(path_like: str | Path, *, root: Path = ROOT) -> dict[str, Any]:
    path = _resolve(path_like, root=root)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _summary(payload: dict[str, Any]) -> dict[str, Any]:
    summary = payload.get("summary")
    return summary if isinstance(summary, dict) else {}


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _int(value: Any) -> int:
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0


def _float(value: Any) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed


def _bool_true(value: Any) -> bool:
    return value is True


def _file_exists(path_like: str | Path, *, root: Path = ROOT) -> bool:
    return _resolve(path_like, root=root).is_file()


def _csv_row_count(path_like: str | Path, *, root: Path = ROOT) -> int:
    path = _resolve(path_like, root=root)
    if not path.is_file():
        return 0
    with path.open(newline="", encoding="utf-8") as handle:
        return sum(1 for _ in csv.DictReader(handle))


def _metric(label: str, value: Any) -> str:
    if isinstance(value, bool):
        rendered = "true" if value else "false"
    elif isinstance(value, float):
        rendered = f"{value:.4g}"
    else:
        rendered = _text(value)
    return f"{label}={rendered}" if rendered else ""


def _join_metrics(*parts: str) -> str:
    return "; ".join(part for part in parts if part)


def _step(
    *,
    step_id: str,
    ready: bool,
    evidence_artifact: str | Path,
    primary_metric: str,
    secondary_metric: str,
    blocker: str = "",
    next_required_step: str = "",
    root: Path = ROOT,
) -> dict[str, Any]:
    return {
        "step_id": step_id,
        "status": "ready" if ready else "blocked",
        "ready": ready,
        "evidence_artifact": _display(evidence_artifact, root=root),
        "primary_metric": primary_metric,
        "secondary_metric": secondary_metric,
        "blocker": blocker,
        "next_required_step": next_required_step,
        "execution_enabled": False,
        "external_state_mutated": False,
        "claim_promotion_allowed": False,
        "claim_boundary": CLAIM_BOUNDARY,
    }


def build_public_benchmark_external_receipts_audit(
    *,
    materialization_json: str | Path = DEFAULT_MATERIALIZATION_JSON,
    results_json: str | Path = DEFAULT_RESULTS_JSON,
    phase2_audit_json: str | Path = DEFAULT_PHASE2_AUDIT_JSON,
    provenance_json: str | Path = DEFAULT_PROVENANCE_JSON,
    scorecard_json: str | Path = DEFAULT_SCORECARD_JSON,
    receipt_json: str | Path = DEFAULT_RECEIPT_JSON,
    receipt_csv: str | Path = DEFAULT_RECEIPT_CSV,
    benchmark_ledger_json: str | Path = DEFAULT_BENCHMARK_LEDGER_JSON,
    vina_gnina_work_order_json: str | Path = DEFAULT_VINA_GNINA_WORK_ORDER_JSON,
    root: Path = ROOT,
) -> dict[str, Any]:
    materialization = _summary(_read_json(materialization_json, root=root))
    results = _summary(_read_json(results_json, root=root))
    phase2 = _summary(_read_json(phase2_audit_json, root=root))
    provenance = _summary(_read_json(provenance_json, root=root))
    scorecard = _summary(_read_json(scorecard_json, root=root))
    receipt = _summary(_read_json(receipt_json, root=root))
    ledger = _summary(_read_json(benchmark_ledger_json, root=root))
    vina_gnina_work_order = _summary(_read_json(vina_gnina_work_order_json, root=root))

    manifest_ready = (
        _file_exists(materialization_json, root=root)
        and _text(materialization.get("status")) == "public_benchmark_materialization_ready"
        and _text(materialization.get("operator_input_artifacts"))
        and _text(materialization.get("operator_output_artifacts"))
    )
    subset_ready = (
        _file_exists(results_json, root=root)
        and _text(results.get("status")) == "pdbbind_casf_pose_affinity_results_ready"
        and _int(results.get("pose_count")) > 0
        and _int(results.get("replay_pose_count")) > 0
        and bool(_text(results.get("subset_identity_sha256")))
        and not _bool_true(results.get("download_executed"))
        and not _bool_true(results.get("prediction_generation_enabled"))
    )
    top5_best = _float(results.get("top5_best_mean_rmsd_A"))
    pose_rmsd_ready = (
        subset_ready
        and _bool_true(results.get("symmetry_aware_ligand_rmsd_ready"))
        and _float(results.get("pose_success_rmsd_threshold_A")) == 2.0
        and _float(results.get("top1_mean_rmsd_A")) is not None
        and top5_best is not None
        and top5_best <= 5.0
    )
    posebusters_ready = (
        subset_ready
        and _bool_true(results.get("posebusters_style_validity_checks_ready"))
        and _int(results.get("posebusters_assessed_pose_count")) == _int(results.get("pose_count"))
    )
    comparison_ready = (
        subset_ready
        and _bool_true(results.get("vina_gnina_comparison_adapter_contract_ready"))
        and _bool_true(results.get("vina_gnina_comparison_adapter_score_evidence_ready"))
        and _bool_true(results.get("comparison_adapter_same_input_row_count_match"))
    )
    receipt_row_count = _int(receipt.get("row_count")) or _csv_row_count(receipt_csv, root=root)
    receipt_ready = (
        _file_exists(receipt_json, root=root)
        and _file_exists(receipt_csv, root=root)
        and _bool_true(receipt.get("claim_promotion_allowed"))
        and _int(receipt.get("blocked_row_count")) == 0
        and receipt_row_count > 0
    )
    ledger_ready = (
        _file_exists(benchmark_ledger_json, root=root)
        and _int(ledger.get("entry_count")) > 0
        and _int(ledger.get("external_safe_count")) > 0
    )
    vina_gnina_work_order_ready = (
        _file_exists(vina_gnina_work_order_json, root=root)
        and _bool_true(vina_gnina_work_order.get("work_order_ready"))
        and _bool_true(vina_gnina_work_order.get("same_input_score_template_ready"))
    )
    vina_gnina_next_step = _text(vina_gnina_work_order.get("next_required_step")) or (
        "Build the Vina/GNINA same-input score work order, fill the operator score template, then rerun "
        "the adapter."
    )

    rows = [
        _step(
            step_id="casf_pdbbind_default_manifest",
            ready=bool(manifest_ready),
            evidence_artifact=materialization_json,
            primary_metric=_join_metrics(
                _metric("manifest_status", materialization.get("status")),
                _metric("input_present", bool(_text(materialization.get("operator_input_artifacts")))),
            ),
            secondary_metric=_join_metrics(
                _metric("output_present", bool(_text(materialization.get("operator_output_artifacts")))),
                _metric("external_state_mutated", False),
            ),
            blocker="" if manifest_ready else "casf_pdbbind_materialization_manifest_missing_or_blocked",
            next_required_step="Build the local CASF/PDBBind materialization manifest.",
            root=root,
        ),
        _step(
            step_id="subset_dry_run",
            ready=bool(subset_ready),
            evidence_artifact=results_json,
            primary_metric=_join_metrics(
                _metric("pose_count", _int(results.get("pose_count"))),
                _metric("replay_pose_count", _int(results.get("replay_pose_count"))),
            ),
            secondary_metric=_join_metrics(
                _metric("subset_identity_sha256", bool(_text(results.get("subset_identity_sha256")))),
                _metric("download_executed", _bool_true(results.get("download_executed"))),
            ),
            blocker="" if subset_ready else "casf_pdbbind_subset_dry_run_missing_or_not_replay_only",
            next_required_step="Run the local PDBBind/CASF subset replay without downloads or prediction generation.",
            root=root,
        ),
        _step(
            step_id="pose_rmsd_2a_5a",
            ready=bool(pose_rmsd_ready),
            evidence_artifact=results_json,
            primary_metric=_join_metrics(
                _metric("threshold_a", results.get("pose_success_rmsd_threshold_A")),
                _metric("pose_success_rate", results.get("pose_success_rate")),
                _metric("top5_best_mean_rmsd_a", results.get("top5_best_mean_rmsd_A")),
            ),
            secondary_metric=_join_metrics(
                _metric("top1_pose_success_rate", results.get("top1_pose_success_rate")),
                _metric("top5_pose_success_rate", results.get("top5_pose_success_rate")),
            ),
            blocker="" if pose_rmsd_ready else "pose_rmsd_2a_5a_metrics_missing_or_above_threshold",
            next_required_step="Generate symmetry-aware pose RMSD 2A/5A evidence on the local subset.",
            root=root,
        ),
        _step(
            step_id="posebusters_validity",
            ready=bool(posebusters_ready),
            evidence_artifact=results_json,
            primary_metric=_join_metrics(
                _metric("posebusters_valid_rate", results.get("posebusters_valid_rate")),
                _metric("assessed", _int(results.get("posebusters_assessed_pose_count"))),
            ),
            secondary_metric=_metric("claim_boundary", "posebusters_style_not_official_posebusters"),
            blocker="" if posebusters_ready else "posebusters_style_validity_missing_or_incomplete",
            next_required_step="Attach PoseBusters-style validity checks for every subset pose.",
            root=root,
        ),
        _step(
            step_id="vina_gnina_same_input_comparison",
            ready=bool(comparison_ready),
            evidence_artifact=results_json,
            primary_metric=_join_metrics(
                _metric("contract_ready", _bool_true(results.get("vina_gnina_comparison_adapter_contract_ready"))),
                _metric("score_evidence_ready", _bool_true(results.get("vina_gnina_comparison_adapter_score_evidence_ready"))),
            ),
            secondary_metric=_join_metrics(
                _metric("same_input_rows", _bool_true(results.get("comparison_adapter_same_input_row_count_match"))),
                _metric("work_order_ready", vina_gnina_work_order_ready),
                _metric("status", results.get("vina_gnina_comparison_adapter_status")),
            ),
            blocker="" if comparison_ready else "vina_gnina_same_input_score_evidence_missing",
            next_required_step=vina_gnina_next_step,
            root=root,
        ),
        _step(
            step_id="benchmark_receipt_attach",
            ready=bool(receipt_ready),
            evidence_artifact=receipt_json,
            primary_metric=_join_metrics(
                _metric("receipt_rows", receipt_row_count),
                _metric("blocked_rows", _int(receipt.get("blocked_row_count"))),
            ),
            secondary_metric=_join_metrics(
                _metric("manual_fields_pending", _int(receipt.get("receipt_manual_field_pending_count"))),
                _metric("approval_tokens_pending", _int(receipt.get("receipt_approval_token_pending_count"))),
            ),
            blocker="" if receipt_ready else "benchmark_metric_source_receipt_rows_unapproved",
            next_required_step=(
                "Fill reviewed metric values, methods, artifact review fields, license flags, and approval token "
                "for the benchmark metric-source receipt rows."
            ),
            root=root,
        ),
        _step(
            step_id="benchmark_ledger_review",
            ready=bool(ledger_ready),
            evidence_artifact=benchmark_ledger_json,
            primary_metric=_join_metrics(
                _metric("entries", _int(ledger.get("entry_count"))),
                _metric("external_safe", _int(ledger.get("external_safe_count"))),
            ),
            secondary_metric=_join_metrics(
                _metric("locked_or_reject", _int(ledger.get("locked_or_reject_count"))),
                _metric("schema", ledger.get("schema_version")),
            ),
            blocker="" if ledger_ready else "benchmark_ledger_missing_or_empty",
            next_required_step="Build and review the benchmark claim ledger before external wording.",
            root=root,
        ),
    ]

    ready_rows = [row for row in rows if row["ready"]]
    blocked_rows = [row for row in rows if not row["ready"]]
    blockers = [f"{row['step_id']}:{row['blocker']}" for row in blocked_rows]
    external_ready = len(ready_rows) == len(rows)
    summary = {
        "packet_type": PACKET_TYPE,
        "schema_version": SCHEMA_VERSION,
        "status": (
            "public_benchmark_external_receipts_audit_ready"
            if external_ready
            else "blocked_public_benchmark_external_receipts_audit"
        ),
        "external_benchmark_receipts_ready": external_ready,
        "claim_promotion_allowed": False,
        "step_count": len(rows),
        "ready_step_count": len(ready_rows),
        "blocked_step_count": len(blocked_rows),
        "blocker_count": len(blockers),
        "blockers": blockers,
        "primary_blocker_id": blocked_rows[0]["step_id"] if blocked_rows else "",
        "primary_blocker": blocked_rows[0]["blocker"] if blocked_rows else "",
        "primary_blocker_next_required_step": blocked_rows[0]["next_required_step"] if blocked_rows else "",
        "materialization_manifest_ready": bool(manifest_ready),
        "subset_dry_run_ready": bool(subset_ready),
        "pose_rmsd_2a_5a_ready": bool(pose_rmsd_ready),
        "posebusters_validity_ready": bool(posebusters_ready),
        "vina_gnina_same_input_comparison_ready": bool(comparison_ready),
        "benchmark_receipt_attach_ready": bool(receipt_ready),
        "benchmark_ledger_review_ready": bool(ledger_ready),
        "vina_gnina_comparison_work_order_ready": bool(vina_gnina_work_order_ready),
        "vina_gnina_comparison_work_order_status": _text(vina_gnina_work_order.get("status")),
        "vina_gnina_score_template_csv": _text(vina_gnina_work_order.get("score_template_csv")),
        "vina_gnina_score_value_pending_count": _int(vina_gnina_work_order.get("score_value_pending_count")),
        "vina_gnina_adapter_command_after_fill": _text(vina_gnina_work_order.get("adapter_command_after_fill")),
        "pose_count": _int(results.get("pose_count")),
        "pose_success_rate": results.get("pose_success_rate"),
        "top1_pose_success_rate": results.get("top1_pose_success_rate"),
        "top5_pose_success_rate": results.get("top5_pose_success_rate"),
        "posebusters_valid_rate": results.get("posebusters_valid_rate"),
        "vina_gnina_comparison_adapter_contract_ready": _bool_true(
            results.get("vina_gnina_comparison_adapter_contract_ready")
        ),
        "vina_gnina_comparison_adapter_score_evidence_ready": _bool_true(
            results.get("vina_gnina_comparison_adapter_score_evidence_ready")
        ),
        "comparison_adapter_same_input_row_count_match": _bool_true(
            results.get("comparison_adapter_same_input_row_count_match")
        ),
        "receipt_row_count": receipt_row_count,
        "receipt_blocked_row_count": _int(receipt.get("blocked_row_count")),
        "receipt_manual_field_pending_count": _int(receipt.get("receipt_manual_field_pending_count")),
        "receipt_approval_token_pending_count": _int(receipt.get("receipt_approval_token_pending_count")),
        "phase2_harness_audit_status": _text(phase2.get("status")),
        "phase2_harness_ready": _bool_true(phase2.get("phase2_harness_audit_ready")),
        "provenance_status": _text(provenance.get("status")),
        "scorecard_status": _text(scorecard.get("status")),
        "benchmark_ledger_entry_count": _int(ledger.get("entry_count")),
        "benchmark_ledger_external_safe_count": _int(ledger.get("external_safe_count")),
        "execution_enabled": False,
        "external_state_mutated": False,
        "docking_results_emitted": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            blocked_rows[0]["next_required_step"]
            if blocked_rows
            else "External benchmark receipts audit is ready for operator review."
        ),
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
        "# Public Benchmark External Receipts Audit",
        "",
        f"- status: `{summary['status']}`",
        f"- external_benchmark_receipts_ready: `{summary['external_benchmark_receipts_ready']}`",
        f"- ready_step_count: `{summary['ready_step_count']}` / `{summary['step_count']}`",
        f"- blocker_count: `{summary['blocker_count']}`",
        f"- primary_blocker_id: `{summary['primary_blocker_id']}`",
        "",
        "| step | status | primary metric | blocker |",
        "| --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['step_id']}` | `{row['status']}` | {row['primary_metric']} | `{row['blocker']}` |"
        )
    lines.extend(["", CLAIM_BOUNDARY, ""])
    return "\n".join(lines)


def _write_text(path_like: str | Path, text: str, *, root: Path = ROOT) -> None:
    path = _resolve(path_like, root=root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build public benchmark external receipts audit.")
    parser.add_argument("--materialization-json", default=DEFAULT_MATERIALIZATION_JSON)
    parser.add_argument("--results-json", default=DEFAULT_RESULTS_JSON)
    parser.add_argument("--phase2-audit-json", default=DEFAULT_PHASE2_AUDIT_JSON)
    parser.add_argument("--provenance-json", default=DEFAULT_PROVENANCE_JSON)
    parser.add_argument("--scorecard-json", default=DEFAULT_SCORECARD_JSON)
    parser.add_argument("--receipt-json", default=DEFAULT_RECEIPT_JSON)
    parser.add_argument("--receipt-csv", default=DEFAULT_RECEIPT_CSV)
    parser.add_argument("--benchmark-ledger-json", default=DEFAULT_BENCHMARK_LEDGER_JSON)
    parser.add_argument("--vina-gnina-work-order-json", default=DEFAULT_VINA_GNINA_WORK_ORDER_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    payload = build_public_benchmark_external_receipts_audit(
        materialization_json=args.materialization_json,
        results_json=args.results_json,
        phase2_audit_json=args.phase2_audit_json,
        provenance_json=args.provenance_json,
        scorecard_json=args.scorecard_json,
        receipt_json=args.receipt_json,
        receipt_csv=args.receipt_csv,
        benchmark_ledger_json=args.benchmark_ledger_json,
        vina_gnina_work_order_json=args.vina_gnina_work_order_json,
    )
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"])
    _write_text(args.out_md, _render_md(payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

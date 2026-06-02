#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]

DEFAULT_MODEL_SELECTION_LEDGER_JSON = "casp17/casp17_massivefold_model_selection_ledger_current.json"
DEFAULT_RISK_QUEUE_JSON = "casp17/casp17_massivefold_model1_risk_queue_current.json"
DEFAULT_CRITICAL_RERANK_SCORE_LEDGER_JSON = "casp17/casp17_massivefold_critical_rerank_score_ledger_current.json"
DEFAULT_BASELINE_COMBINED_SELECTOR_JSON = (
    "casp17/casp17_official_archive_first_baseline_model1_gap_combined_selector_ledger_current.json"
)
DEFAULT_OUT_DIR = "casp17/massivefold_model1_combined_selector_overlay"
DEFAULT_OUT_JSON = "casp17/casp17_massivefold_model1_combined_selector_overlay_current.json"
DEFAULT_OUT_CSV = "casp17/casp17_massivefold_model1_combined_selector_overlay_current.csv"
DEFAULT_OUT_MD = "casp17/CASP17_MASSIVEFOLD_MODEL1_COMBINED_SELECTOR_OVERLAY.md"

CLAIM_BOUNDARY = (
    "CASP17 MassiveFold model1 combined selector overlay only. It applies a baseline-calibrated "
    "no-native model-selection policy to external MassiveFold model1/top5 ledgers. It is not native "
    "accuracy, internal prediction proof, a CASP submission, or permission to submit without operator approval."
)
EXTERNAL_ONLY_POLICY = "external_no_native_massivefold_model1_selector_overlay_only"
INTERNAL_PREDICTION_POLICY = "do_not_mark_as_internal_prediction"
SUBMISSION_POLICY = "do_not_submit_without_rule_check_and_operator_approval"
RULE_ID = "baseline_calibrated_no_native_massivefold_selector_overlay_v1"

ROW_COLUMNS = [
    "overlay_rank",
    "overlay_status",
    "target_group",
    "target_id",
    "target_family",
    "current_ledger_decision",
    "freeze_decision_class",
    "model1_freeze_state",
    "overlay_decision",
    "overlay_action",
    "overlay_reason",
    "selected_model_filename",
    "model1_filename",
    "probe_result",
    "probe_margin",
    "confidence_gap",
    "top5_score_spread",
    "mean_diversity_to_model1_rmsd",
    "max_geometry_outlier_score",
    "max_low_conf_atom_fraction",
    "min_nearest_top5_rmsd",
    "risk_tier",
    "risk_band",
    "risk_score",
    "low_margin",
    "baseline_capture_rate",
    "baseline_non_capture_rate",
    "review_md",
    "blockers",
    "external_only_policy",
    "internal_prediction_policy",
    "submission_policy",
    "claim_boundary",
    "rule_id",
]


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _artifact(path_like: str | Path) -> str:
    if not str(path_like).strip():
        return ""
    path = _resolve(path_like).resolve()
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _float(value: Any) -> float:
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return 0.0


def _bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def _read_json(path_like: str | Path) -> dict[str, Any]:
    path = _resolve(path_like)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _summary(payload: dict[str, Any]) -> dict[str, Any]:
    summary = payload.get("summary")
    return summary if isinstance(summary, dict) else {}


def _rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = payload.get("rows")
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_csv(path_like: str | Path, rows: list[dict[str, Any]]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=ROW_COLUMNS, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _by_target(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {_text(row.get("target_id")).upper(): row for row in rows if _text(row.get("target_id"))}


def _has_review_risk(row: dict[str, Any], risk_row: dict[str, Any]) -> bool:
    return (
        _bool(risk_row.get("low_margin"))
        or _float(row.get("max_geometry_outlier_score")) >= 5.0
        or _float(row.get("max_low_conf_atom_fraction")) >= 0.10
        or _float(row.get("mean_diversity_to_model1_rmsd")) >= 45.0
        or _float(row.get("confidence_gap")) <= 0.50
    )


def _overlay_decision(row: dict[str, Any], risk_row: dict[str, Any]) -> tuple[str, str, str]:
    ledger_decision = _text(row.get("ledger_decision"))
    probe_result = _text(row.get("probe_result"))
    freeze_class = _text(row.get("freeze_decision_class"))
    probe_margin = _float(row.get("probe_margin"))
    target_group = _text(row.get("target_group"))
    if ledger_decision == "external_model1_blocked_manual_review" or probe_result == "probe_fail_model1_displaced":
        return (
            "selector_blocked_manual_review",
            "do_not_freeze_model1_external_only",
            "existing probe displaced model1 or freeze ledger is manual-review blocked",
        )
    if probe_result == "probe_pass_model1_retained":
        if probe_margin >= 0.50 and freeze_class == "conditional_freeze_ready":
            return (
                "baseline_calibrated_freeze_ready",
                "carry_model1_as_external_only_freeze_ready",
                "probe margin clears baseline-calibrated conservative threshold",
            )
        if target_group == "protein_complex":
            return (
                "selector_hold_interface_review",
                "keep_model1_hold_until_interface_review",
                "protein/complex model1 retained but probe margin or watch class is too weak for freeze",
            )
        return (
            "selector_hold_weak_probe_margin",
            "repeat_or_extend_top5_probe_before_freeze",
            "probe retained model1 but margin is below baseline-calibrated conservative threshold",
        )
    if ledger_decision == "external_model1_review_only_unfrozen":
        if _has_review_risk(row, risk_row):
            return (
                "selector_probe_required",
                "run_targeted_no_native_probe_before_freeze",
                "review-only target has low-margin, diversity, geometry, or low-confidence risk",
            )
        return (
            "selector_review_only_watch",
            "keep_external_review_only_until_target_priority_changes",
            "review-only target lacks immediate high-risk flags but is not probe-gated",
        )
    return (
        "selector_hold_unknown_state",
        "manual_review_selector_state",
        "ledger state is not covered by baseline-calibrated overlay rules",
    )


def _rank_key(row: dict[str, Any]) -> tuple[int, str]:
    priority = {
        "selector_blocked_manual_review": 1,
        "selector_hold_interface_review": 2,
        "selector_hold_weak_probe_margin": 3,
        "selector_probe_required": 4,
        "baseline_calibrated_freeze_ready": 5,
        "selector_review_only_watch": 6,
        "selector_hold_unknown_state": 7,
    }.get(row["overlay_decision"], 9)
    return (priority, row["target_id"])


def _review_dir_name(row: dict[str, Any]) -> str:
    return f"{int(row['overlay_rank']):02d}_{row['target_group']}_{row['target_id'].lower()}"


def _write_review(path: Path, row: dict[str, Any]) -> None:
    lines = [
        f"# {row['target_id']} MassiveFold combined selector overlay",
        "",
        f"- overlay decision: `{row['overlay_decision']}`",
        f"- action: `{row['overlay_action']}`",
        f"- reason: `{row['overlay_reason']}`",
        f"- current ledger: `{row['current_ledger_decision']}` `{row['freeze_decision_class']}`",
        f"- probe: `{row['probe_result'] or '-'}` margin `{row['probe_margin'] or '-'}`",
        f"- risk tier/band/score: `{row['risk_tier'] or '-'}` `{row['risk_band'] or '-'}` `{row['risk_score'] or '-'}`",
        f"- baseline capture/non-capture: `{row['baseline_capture_rate']}` `{row['baseline_non_capture_rate']}`",
        "",
        "## Claim Boundary",
        "",
        CLAIM_BOUNDARY,
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    ledger_payload = _read_json(args.model_selection_ledger_json)
    risk_payload = _read_json(args.risk_queue_json)
    critical_payload = _read_json(args.critical_rerank_score_ledger_json)
    baseline_payload = _read_json(args.baseline_combined_selector_json)
    ledger_summary = _summary(ledger_payload)
    risk_summary = _summary(risk_payload)
    critical_summary = _summary(critical_payload)
    baseline_summary = _summary(baseline_payload)
    risk_by_target = _by_target(_rows(risk_payload))
    critical_by_target = _by_target(_rows(critical_payload))
    baseline_capture = _text(baseline_summary.get("baseline_capture_rate")) or "0.000"
    baseline_non_capture = _text(baseline_summary.get("baseline_non_capture_rate")) or "0.000"

    rows: list[dict[str, Any]] = []
    out_dir = _resolve(args.out_dir)
    for ledger_row in _rows(ledger_payload):
        target_id = _text(ledger_row.get("target_id")).upper()
        risk_row = risk_by_target.get(target_id, {})
        critical_row = critical_by_target.get(target_id, {})
        decision, action, reason = _overlay_decision(ledger_row, risk_row)
        blockers = _text(ledger_row.get("blockers"))
        row = {
            "overlay_rank": 0,
            "overlay_status": "ready_external_no_native_selector_overlay" if not blockers else "blocked_selector_overlay",
            "target_group": _text(ledger_row.get("target_group")),
            "target_id": target_id,
            "target_family": _text(ledger_row.get("target_family")),
            "current_ledger_decision": _text(ledger_row.get("ledger_decision")),
            "freeze_decision_class": _text(ledger_row.get("freeze_decision_class")),
            "model1_freeze_state": _text(ledger_row.get("model1_freeze_state")),
            "overlay_decision": decision,
            "overlay_action": action,
            "overlay_reason": reason,
            "selected_model_filename": _text(ledger_row.get("selected_model_filename")),
            "model1_filename": _text(ledger_row.get("model1_filename")),
            "probe_result": _text(ledger_row.get("probe_result")),
            "probe_margin": _text(ledger_row.get("probe_margin")),
            "confidence_gap": _text(ledger_row.get("confidence_gap")),
            "top5_score_spread": _text(ledger_row.get("top5_score_spread")),
            "mean_diversity_to_model1_rmsd": _text(ledger_row.get("mean_diversity_to_model1_rmsd")),
            "max_geometry_outlier_score": _text(ledger_row.get("max_geometry_outlier_score")),
            "max_low_conf_atom_fraction": _text(ledger_row.get("max_low_conf_atom_fraction")),
            "min_nearest_top5_rmsd": _text(ledger_row.get("min_nearest_top5_rmsd")),
            "risk_tier": _text(risk_row.get("risk_tier")),
            "risk_band": _text(critical_row.get("risk_band")),
            "risk_score": _text(critical_row.get("risk_score")),
            "low_margin": str(_bool(risk_row.get("low_margin"))),
            "baseline_capture_rate": baseline_capture,
            "baseline_non_capture_rate": baseline_non_capture,
            "review_md": "",
            "blockers": blockers,
            "external_only_policy": EXTERNAL_ONLY_POLICY,
            "internal_prediction_policy": INTERNAL_PREDICTION_POLICY,
            "submission_policy": SUBMISSION_POLICY,
            "claim_boundary": CLAIM_BOUNDARY,
            "rule_id": RULE_ID,
        }
        rows.append(row)

    rows.sort(key=_rank_key)
    for rank, row in enumerate(rows, start=1):
        row["overlay_rank"] = rank
        review = out_dir / _review_dir_name(row) / "SELECTOR_OVERLAY.md"
        row["review_md"] = _artifact(review)
        _write_review(review, row)

    ready_rows = [row for row in rows if row["overlay_status"] == "ready_external_no_native_selector_overlay"]
    decision_counts = {
        "freeze_ready": sum(1 for row in ready_rows if row["overlay_decision"] == "baseline_calibrated_freeze_ready"),
        "manual_blocked": sum(1 for row in ready_rows if row["overlay_decision"] == "selector_blocked_manual_review"),
        "interface_hold": sum(1 for row in ready_rows if row["overlay_decision"] == "selector_hold_interface_review"),
        "weak_probe_hold": sum(1 for row in ready_rows if row["overlay_decision"] == "selector_hold_weak_probe_margin"),
        "probe_required": sum(1 for row in ready_rows if row["overlay_decision"] == "selector_probe_required"),
        "review_watch": sum(1 for row in ready_rows if row["overlay_decision"] == "selector_review_only_watch"),
        "unknown_hold": sum(1 for row in ready_rows if row["overlay_decision"] == "selector_hold_unknown_state"),
    }
    first = rows[0] if rows else {}
    first_freeze = next((row for row in rows if row["overlay_decision"] == "baseline_calibrated_freeze_ready"), {})
    status = (
        "massivefold_model1_combined_selector_overlay_ready_external_only"
        if rows and len(ready_rows) == len(rows)
        else "massivefold_model1_combined_selector_overlay_blocked"
    )
    summary = {
        "packet_type": "casp17_massivefold_model1_combined_selector_overlay",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "massivefold_model1_combined_selector_overlay_status": status,
        "model_selection_ledger_json": _artifact(args.model_selection_ledger_json),
        "model_selection_ledger_status": _text(ledger_summary.get("massivefold_model_selection_ledger_status")),
        "risk_queue_json": _artifact(args.risk_queue_json),
        "risk_queue_status": _text(risk_summary.get("massivefold_model1_risk_queue_status")),
        "critical_rerank_score_ledger_json": _artifact(args.critical_rerank_score_ledger_json),
        "critical_rerank_score_ledger_status": _text(
            critical_summary.get("massivefold_critical_rerank_score_ledger_status")
        ),
        "baseline_combined_selector_json": _artifact(args.baseline_combined_selector_json),
        "baseline_combined_selector_status": _text(
            baseline_summary.get("official_archive_first_baseline_model1_gap_combined_selector_ledger_status")
        ),
        "baseline_capture_rate": baseline_capture,
        "baseline_non_capture_rate": baseline_non_capture,
        "overlay_count": len(rows),
        "overlay_ready_count": len(ready_rows),
        "overlay_blocked_count": len(rows) - len(ready_rows),
        "freeze_ready_overlay_count": decision_counts["freeze_ready"],
        "manual_blocked_overlay_count": decision_counts["manual_blocked"],
        "interface_hold_overlay_count": decision_counts["interface_hold"],
        "weak_probe_hold_overlay_count": decision_counts["weak_probe_hold"],
        "probe_required_overlay_count": decision_counts["probe_required"],
        "review_watch_overlay_count": decision_counts["review_watch"],
        "unknown_hold_overlay_count": decision_counts["unknown_hold"],
        "not_freeze_ready_overlay_count": len(ready_rows) - decision_counts["freeze_ready"],
        "rna_hybrid_overlay_count": sum(1 for row in ready_rows if row["target_group"] == "rna_hybrid"),
        "protein_complex_overlay_count": sum(1 for row in ready_rows if row["target_group"] == "protein_complex"),
        "first_overlay_target_id": _text(first.get("target_id")),
        "first_overlay_decision": _text(first.get("overlay_decision")),
        "first_overlay_action": _text(first.get("overlay_action")),
        "first_freeze_ready_target_id": _text(first_freeze.get("target_id")),
        "first_freeze_ready_action": _text(first_freeze.get("overlay_action")),
        "overlay_csv": _artifact(args.out_csv),
        "overlay_dir": _artifact(args.out_dir),
        "external_only_policy": EXTERNAL_ONLY_POLICY,
        "internal_prediction_policy": INTERNAL_PREDICTION_POLICY,
        "submission_policy": SUBMISSION_POLICY,
        "competitive_proof_eligible": False,
        "next_action": (
            "run targeted no-native probes for overlay probe-required targets and keep strict-blind proof separate"
            if status == "massivefold_model1_combined_selector_overlay_ready_external_only"
            else "repair blocked MassiveFold selector overlay rows before freeze review"
        ),
        "claim_boundary": CLAIM_BOUNDARY,
        "rule_id": RULE_ID,
    }
    return {"summary": summary, "rows": rows}


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 MassiveFold Model1 Combined Selector Overlay",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- status: `{summary['massivefold_model1_combined_selector_overlay_status']}`",
        f"- overlay ready/blocked/total: `{summary['overlay_ready_count']}/{summary['overlay_blocked_count']}/{summary['overlay_count']}`",
        f"- baseline capture/non-capture: `{summary['baseline_capture_rate']}` `{summary['baseline_non_capture_rate']}`",
        f"- freeze-ready/not-freeze-ready: `{summary['freeze_ready_overlay_count']}/{summary['not_freeze_ready_overlay_count']}`",
        f"- manual/interface/weak-probe/probe-required/review-watch/unknown: `{summary['manual_blocked_overlay_count']}/{summary['interface_hold_overlay_count']}/{summary['weak_probe_hold_overlay_count']}/{summary['probe_required_overlay_count']}/{summary['review_watch_overlay_count']}/{summary['unknown_hold_overlay_count']}`",
        f"- RNA/protein-complex overlays: `{summary['rna_hybrid_overlay_count']}/{summary['protein_complex_overlay_count']}`",
        f"- first overlay: `{summary['first_overlay_target_id'] or '-'}` `{summary['first_overlay_decision'] or '-'}` `{summary['first_overlay_action'] or '-'}`",
        f"- first freeze-ready: `{summary['first_freeze_ready_target_id'] or '-'}` `{summary['first_freeze_ready_action'] or '-'}`",
        f"- proof eligible: `{summary['competitive_proof_eligible']}` policy `{summary['internal_prediction_policy']}`",
        f"- next action: {summary['next_action']}",
        "",
        "## Overlay Worklist",
        "",
        "| rank | target | group | decision | action | probe | margin | risk | review |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['overlay_rank']}` | `{row['target_id']}` | `{row['target_group']}` | "
            f"`{row['overlay_decision']}` | `{row['overlay_action']}` | `{row['probe_result'] or '-'}` | "
            f"`{row['probe_margin'] or '-'}` | `{row['risk_tier'] or row['risk_band'] or '-'}` | `{row['review_md']}` |"
        )
    lines.extend(["", "## Claim Boundary", "", CLAIM_BOUNDARY])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_outputs(args: argparse.Namespace, payload: dict[str, Any]) -> None:
    _resolve(args.out_dir).mkdir(parents=True, exist_ok=True)
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"])
    _write_md(args.out_md, payload)
    _write_json(_resolve(args.out_dir) / "selector_overlay.json", payload)
    _write_csv(_resolve(args.out_dir) / "selector_overlay.csv", payload["rows"])


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a baseline-calibrated MassiveFold model1 selector overlay.")
    parser.add_argument("--model-selection-ledger-json", default=DEFAULT_MODEL_SELECTION_LEDGER_JSON)
    parser.add_argument("--risk-queue-json", default=DEFAULT_RISK_QUEUE_JSON)
    parser.add_argument("--critical-rerank-score-ledger-json", default=DEFAULT_CRITICAL_RERANK_SCORE_LEDGER_JSON)
    parser.add_argument("--baseline-combined-selector-json", default=DEFAULT_BASELINE_COMBINED_SELECTOR_JSON)
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    payload = build_payload(args)
    write_outputs(args, payload)
    print(
        json.dumps(
            {
                "status": payload["summary"]["massivefold_model1_combined_selector_overlay_status"],
                "ready": payload["summary"]["overlay_ready_count"],
                "freeze_ready": payload["summary"]["freeze_ready_overlay_count"],
                "not_freeze_ready": payload["summary"]["not_freeze_ready_overlay_count"],
                "first": payload["summary"]["first_overlay_target_id"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

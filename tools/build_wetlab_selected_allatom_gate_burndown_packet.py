#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[1]

DEFAULT_WETLAB_DASHBOARD_JSON = "runs/wetlab_master_handoff_dashboard_current.json"
DEFAULT_WETLAB_FINAL_JSON = "runs/wetlab_final_campaign_summary_current.json"
DEFAULT_OUT_JSON = "runs/wetlab_selected_allatom_gate_burndown_packet_current.json"
DEFAULT_OUT_CSV = "runs/wetlab_selected_allatom_gate_burndown_packet_current.csv"
DEFAULT_OUT_MD = "runs/wetlab_selected_allatom_gate_burndown_packet_current.md"
TCRUZI_PDE_ALLATOM_REVIEW_ARTIFACTS = {
    "runs/wetlab_tcruzi_pde_allatom_review_packet_current.md",
    "runs/wetlab_tcruzi_pde_allatom_review_packet_current.json",
}


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    if path.is_absolute():
        return path
    cwd_path = (Path.cwd() / path).resolve()
    if cwd_path.exists():
        return cwd_path
    return (ROOT / path).resolve()


def _load_json(path_like: str | Path) -> dict[str, Any]:
    with _resolve(path_like).open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _summaryish(payload: dict[str, Any]) -> dict[str, Any]:
    summary = dict(payload.get("summary", {}) or {})
    if summary:
        merged = dict(payload)
        merged.update(summary)
        return merged
    return dict(payload or {})


def _text(value: Any) -> str:
    return str(value or "").strip()


def _int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _fmt_float(value: Any, digits: int = 3) -> str:
    parsed = _float(value)
    if parsed is None:
        return "-"
    return f"{parsed:.{digits}f}"


def _bool_or_none(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if value is None:
        return None
    text = str(value).strip().lower()
    if text in {"true", "1", "yes", "pass", "passed"}:
        return True
    if text in {"false", "0", "no", "fail", "failed"}:
        return False
    return None


def _canonical_artifact(path_like: str) -> str:
    return path_like.replace("\\", "/").lstrip("./")


def _review_json_for_focus(focus_artifact: str) -> Path | None:
    artifact = _canonical_artifact(focus_artifact)
    if artifact not in TCRUZI_PDE_ALLATOM_REVIEW_ARTIFACTS:
        return None
    json_artifact = artifact[:-3] + ".json" if artifact.endswith(".md") else artifact
    path = _resolve(json_artifact)
    return path if path.exists() else None


def _review_metric_override(
    focus_artifact: str,
    selected_allatom_review_payload: dict[str, Any] | None,
) -> dict[str, str] | None:
    if _canonical_artifact(focus_artifact) not in TCRUZI_PDE_ALLATOM_REVIEW_ARTIFACTS:
        return None
    if not selected_allatom_review_payload:
        return None

    review = _summaryish(selected_allatom_review_payload)
    value_num = _float(review.get("best_mean_min_distance_A"))
    thresholds = review.get("wetlab_gate_thresholds") if isinstance(review.get("wetlab_gate_thresholds"), dict) else {}
    threshold_num = _float(review.get("selected_threshold_A"))
    if threshold_num is None:
        threshold_num = _float(thresholds.get("selected_threshold_A") or thresholds.get("strict_threshold_A"))
    if value_num is None or threshold_num is None:
        return None

    return {
        "metric": "mean_min_distance_A",
        "value": _fmt_float(value_num),
        "threshold": _fmt_float(threshold_num),
        "delta": _fmt_float(value_num - threshold_num),
        "source_artifact": "runs/wetlab_tcruzi_pde_allatom_review_packet_current.json",
        "source_kind": "selected_allatom_review_packet_summary",
        "refresh_reason": "review_packet_best_mean_min_distance_A_supersedes_stale_final_campaign_selected_allatom_value",
    }


def _operational_bucket(code: str, category: str, severity: str) -> str:
    if code == "recompute_mean_min_distance_A":
        return "geometry_hard_block"
    if code == "recompute_claim_gate_required_unavailable":
        return "claim_gate_metric_missing"
    if category == "claim_equivalence":
        return "claim_equivalence_block"
    if severity == "soft":
        return "expensive_lane_hold"
    return "general_gate_followup"


def _gate_dependency(category: str, severity: str) -> str:
    if severity == "hard":
        return "must_clear_before_claim_or_expensive_lane"
    if category == "claim_equivalence":
        return "blocked_until_translation_hard_gate_clears"
    return "keep_parked_until_hard_gate_clears"


def _next_required_action(code: str, action: str) -> str:
    if code == "recompute_mean_min_distance_A":
        return (
            "Re-minimize the selected all-atom pose, rerun short replicated MD, and refresh the strict 2.5A geometry gate before any stronger-physics escalation."
        )
    if code == "recompute_claim_gate_required_unavailable":
        return (
            "Materialize the missing claim_gate_required_unavailable field on the selected all-atom focus and rerun the translation/commercial hard gate."
        )
    if code == "produce_claim_equivalence_packet":
        return (
            "Assemble the neglected-disease claim/equivalence packet and attach it to the selected all-atom focus after the geometry hard block is cleared."
        )
    if code == "resolve_claim_equivalence_gate":
        return (
            "Re-evaluate the claim/equivalence gate after the packet is attached; do not mark the lane final-wetlab-ready until this gate explicitly resolves."
        )
    if code == "defer_expensive_lane":
        return (
            "Keep explicit-water rescoring and seed-replicated short MD parked until geometry and claim-gate blockers are both resolved."
        )
    return f"Resolve `{action or code or 'selected_allatom_gate_action'}` before reopening the selected all-atom lane."


def build_payload(
    wetlab_dashboard_payload: dict[str, Any],
    wetlab_final_payload: dict[str, Any],
    selected_allatom_review_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    dashboard = _summaryish(wetlab_dashboard_payload)
    final_summary = _summaryish(wetlab_final_payload)

    action_rows = list(
        dashboard.get("selected_allatom_action_recipe_rows")
        or final_summary.get("selected_allatom_action_recipe_rows")
        or []
    )
    target_id = _text(dashboard.get("selected_allatom_target_id")) or _text(final_summary.get("selected_allatom_target_id"))
    focus_artifact = _text(dashboard.get("selected_allatom_focus_artifact")) or "runs/wetlab_tcruzi_pde_allatom_review_packet_current.md"
    selected_command_kind = _text(dashboard.get("selected_allatom_selected_command_kind")) or _text(
        final_summary.get("selected_allatom_selected_command_kind")
    )
    selected_threshold_A = _text(dashboard.get("selected_allatom_selected_threshold_A")) or _text(
        final_summary.get("selected_allatom_selected_threshold_A")
    )
    best_mean_min_distance_A = _text(final_summary.get("selected_allatom_best_mean_min_distance_A"))
    wetlab_gate_pass = bool(dashboard.get("selected_allatom_wetlab_gate_pass", False))
    final_gate_pass = bool(dashboard.get("selected_allatom_final_gate_pass", False))
    claim_gate_available = bool(dashboard.get("selected_allatom_claim_gate_available", False))
    claim_ready_for_allatom = bool(dashboard.get("selected_allatom_claim_ready_for_allatom", False))
    actionability_status = _text(final_summary.get("selected_allatom_effective_actionability_status")) or _text(
        dashboard.get("selected_allatom_actionability_status")
    )
    primary_blocking_domain = _text(final_summary.get("selected_allatom_effective_primary_blocking_domain"))
    claim_requirement_reason = _text(
        final_summary.get("selected_allatom_effective_actionability_claim_requirement_reason")
    ) or _text(dashboard.get("selected_allatom_actionability_claim_requirement_reason"))
    action_recipe_rollup_text = _text(dashboard.get("selected_allatom_action_recipe_rollup_text")) or _text(
        final_summary.get("selected_allatom_action_recipe_rollup_text")
    )
    promoted_candidate_count = _int(final_summary.get("selected_allatom_promoted_candidate_count"))
    strict_candidate_count = _int(final_summary.get("selected_allatom_under_2p5_candidate_count"))
    near_candidate_count = _int(final_summary.get("selected_allatom_near_candidate_count"))
    metric_override = _review_metric_override(focus_artifact, selected_allatom_review_payload)

    rows: list[dict[str, Any]] = []
    for rank, action_row in enumerate(action_rows, start=1):
        code = _text(action_row.get("code")) or _text(action_row.get("calc_action"))
        severity = _text(action_row.get("severity"))
        category = _text(action_row.get("category"))
        value = _text(action_row.get("value"))
        threshold = _text(action_row.get("threshold"))
        value_num = _float(value)
        threshold_num = _float(threshold)
        delta_text = (
            _fmt_float(value_num - threshold_num)
            if value_num is not None and threshold_num is not None
            else "-"
        )
        rows.append(
            {
                "burndown_rank": rank,
                "severity": severity,
                "category": category,
                "operational_bucket": _operational_bucket(code, category, severity),
                "action": _text(action_row.get("action")),
                "calc_action": _text(action_row.get("calc_action")),
                "status": _text(action_row.get("status")),
                "code": code,
                "metric": _text(action_row.get("metric")),
                "value": value,
                "threshold": threshold,
                "delta": delta_text,
                "gate_dependency": _gate_dependency(category, severity),
                "reason": _text(action_row.get("reason")),
                "next_required_action": _next_required_action(code, _text(action_row.get("action"))),
            }
        )

    if metric_override:
        best_mean_min_distance_A = metric_override["value"]
        selected_threshold_A = metric_override["threshold"]
        for row in rows:
            if row["code"] == "recompute_mean_min_distance_A":
                row["metric"] = metric_override["metric"]
                row["value"] = metric_override["value"]
                row["threshold"] = metric_override["threshold"]
                row["delta"] = metric_override["delta"]
                row["reason"] = (
                    f"mean_min_distance_A={metric_override['value']} threshold={metric_override['threshold']} "
                    f"from {metric_override['source_artifact']}"
                )
                break

        review = _summaryish(selected_allatom_review_payload or {})
        review_wetlab_gate_pass = _bool_or_none(review.get("wetlab_gate_pass"))
        review_final_gate_pass = _bool_or_none(review.get("wetlab_final_gate_pass"))
        review_claim_gate_available = _bool_or_none(review.get("claim_gate_available"))
        if review_wetlab_gate_pass is not None:
            wetlab_gate_pass = wetlab_gate_pass and review_wetlab_gate_pass
        if review_claim_gate_available is False:
            claim_gate_available = False
            final_gate_pass = False
        elif review_claim_gate_available is not None:
            claim_gate_available = claim_gate_available and review_claim_gate_available
        if review_final_gate_pass is not None:
            final_gate_pass = final_gate_pass and review_final_gate_pass

    hard_block_count = sum(1 for row in rows if row["severity"] == "hard")
    semi_hard_block_count = sum(1 for row in rows if row["severity"] == "semi_hard")
    soft_deferred_count = sum(1 for row in rows if row["severity"] == "soft")
    missing_metric_count = sum(1 for row in rows if row["status"] == "missing")
    primary_row = rows[0] if rows else {}

    primary_metric = _text(primary_row.get("metric")) or "mean_min_distance_A"
    primary_value = _text(primary_row.get("value")) or best_mean_min_distance_A
    primary_threshold = _text(primary_row.get("threshold")) or selected_threshold_A
    primary_delta = _text(primary_row.get("delta"))

    summary = {
        "packet_ready": True,
        "packet_artifact": "runs/wetlab_selected_allatom_gate_burndown_packet_current.md",
        "selected_allatom_target_id": target_id,
        "selected_allatom_focus_artifact": focus_artifact,
        "selected_allatom_selected_command_kind": selected_command_kind,
        "selected_allatom_selected_threshold_A": selected_threshold_A,
        "selected_allatom_best_mean_min_distance_A": best_mean_min_distance_A,
        "selected_allatom_metric_source_artifact": (
            metric_override["source_artifact"] if metric_override else "runs/wetlab_final_campaign_summary_current.json"
        ),
        "selected_allatom_metric_source_kind": (
            metric_override["source_kind"] if metric_override else "final_campaign_summary_selected_allatom"
        ),
        "selected_allatom_metric_refresh_reason": (
            metric_override["refresh_reason"] if metric_override else "default_final_campaign_summary_source"
        ),
        "selected_allatom_wetlab_gate_pass": wetlab_gate_pass,
        "selected_allatom_final_gate_pass": final_gate_pass,
        "selected_allatom_claim_gate_available": claim_gate_available,
        "selected_allatom_claim_ready_for_allatom": claim_ready_for_allatom,
        "selected_allatom_actionability_status": actionability_status,
        "selected_allatom_primary_blocking_domain": primary_blocking_domain,
        "selected_allatom_claim_requirement_reason": claim_requirement_reason,
        "row_count": len(rows),
        "hard_block_count": hard_block_count,
        "semi_hard_block_count": semi_hard_block_count,
        "soft_deferred_count": soft_deferred_count,
        "missing_metric_count": missing_metric_count,
        "promoted_candidate_count": promoted_candidate_count,
        "strict_candidate_count": strict_candidate_count,
        "near_candidate_count": near_candidate_count,
        "primary_burndown_code": _text(primary_row.get("code")),
        "primary_burndown_action": _text(primary_row.get("action")),
        "primary_burndown_metric": primary_metric,
        "primary_burndown_value": primary_value,
        "primary_burndown_threshold": primary_threshold,
        "primary_burndown_delta": primary_delta,
        "next_required_step": (
            f"Start with `{_text(primary_row.get('code')) or 'recompute_mean_min_distance_A'}` on `{target_id or 'selected_allatom'}`: "
            f"`{primary_metric}` sits at `{primary_value or '-'}` versus `{primary_threshold or '-'}` (delta `{primary_delta or '-'}`), "
            "then recompute the missing claim-gate field, and only after the hard block clears move on to claim/equivalence packet production while keeping expensive lanes deferred."
        ),
        "action_recipe_rollup_text": action_recipe_rollup_text,
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# Wetlab Selected All-Atom Gate Burndown Packet",
        "",
        f"- selected_allatom_target_id: `{summary['selected_allatom_target_id']}`",
        f"- selected_allatom_focus_artifact: `{summary['selected_allatom_focus_artifact']}`",
        f"- selected_allatom_selected_command_kind: `{summary['selected_allatom_selected_command_kind']}`",
        f"- selected_allatom_selected_threshold_A: `{summary['selected_allatom_selected_threshold_A']}`",
        f"- selected_allatom_best_mean_min_distance_A: `{summary['selected_allatom_best_mean_min_distance_A']}`",
        f"- selected_allatom_metric_source_artifact: `{summary['selected_allatom_metric_source_artifact']}`",
        f"- selected_allatom_metric_source_kind: `{summary['selected_allatom_metric_source_kind']}`",
        f"- selected_allatom_metric_refresh_reason: `{summary['selected_allatom_metric_refresh_reason']}`",
        f"- selected_allatom_wetlab_gate_pass: `{summary['selected_allatom_wetlab_gate_pass']}`",
        f"- selected_allatom_final_gate_pass: `{summary['selected_allatom_final_gate_pass']}`",
        f"- selected_allatom_claim_gate_available: `{summary['selected_allatom_claim_gate_available']}`",
        f"- selected_allatom_claim_ready_for_allatom: `{summary['selected_allatom_claim_ready_for_allatom']}`",
        f"- selected_allatom_actionability_status: `{summary['selected_allatom_actionability_status']}`",
        f"- selected_allatom_primary_blocking_domain: `{summary['selected_allatom_primary_blocking_domain']}`",
        f"- row_count: `{summary['row_count']}`",
        f"- hard_block_count: `{summary['hard_block_count']}`",
        f"- semi_hard_block_count: `{summary['semi_hard_block_count']}`",
        f"- soft_deferred_count: `{summary['soft_deferred_count']}`",
        f"- missing_metric_count: `{summary['missing_metric_count']}`",
        f"- primary_burndown_code: `{summary['primary_burndown_code']}`",
        f"- primary_burndown_metric: `{summary['primary_burndown_metric']}`",
        f"- primary_burndown_delta: `{summary['primary_burndown_delta']}`",
        "",
        "## Next Step",
        "",
        f"- {summary['next_required_step']}",
        "",
        "## Burndown Queue",
        "",
        "| rank | severity | bucket | code | status | metric | value | threshold | delta |",
        "| ---: | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| {row['burndown_rank']} | `{row['severity']}` | `{row['operational_bucket']}` | `{row['code']}` | "
            f"`{row['status']}` | `{row['metric'] or '-'}` | `{row['value'] or '-'}` | `{row['threshold'] or '-'}` | `{row['delta']}` |"
        )
    lines.extend(["", "## Action Recipe Rollup", "", f"- {summary['action_recipe_rollup_text'] or '-'}", "", "## Execution Notes", ""])
    for row in payload["rows"]:
        lines.append(f"- `{row['code']}`: {row['next_required_action']}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the wetlab selected all-atom gate burndown packet.")
    parser.add_argument("--wetlab-dashboard-json", default=DEFAULT_WETLAB_DASHBOARD_JSON)
    parser.add_argument("--wetlab-final-json", default=DEFAULT_WETLAB_FINAL_JSON)
    parser.add_argument("--selected-allatom-review-json", default="")
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    wetlab_dashboard_payload = _load_json(args.wetlab_dashboard_json)
    wetlab_final_payload = _load_json(args.wetlab_final_json)
    dashboard = _summaryish(wetlab_dashboard_payload)
    final_summary = _summaryish(wetlab_final_payload)
    focus_artifact = _text(dashboard.get("selected_allatom_focus_artifact")) or _text(
        final_summary.get("selected_allatom_focus_artifact")
    )
    review_json = _resolve(args.selected_allatom_review_json) if args.selected_allatom_review_json else _review_json_for_focus(focus_artifact)
    selected_allatom_review_payload = _load_json(review_json) if review_json else None
    payload = build_payload(
        wetlab_dashboard_payload=wetlab_dashboard_payload,
        wetlab_final_payload=wetlab_final_payload,
        selected_allatom_review_payload=selected_allatom_review_payload,
    )
    out_json = _resolve(args.out_json)
    out_csv = _resolve(args.out_csv)
    out_md = _resolve(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    write_csv_rows(out_csv, payload["rows"])
    _write_markdown(out_md, payload)


if __name__ == "__main__":
    main()

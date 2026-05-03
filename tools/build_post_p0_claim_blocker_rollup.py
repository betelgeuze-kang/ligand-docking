#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

DEFAULT_GPCR_CI_LOW_JSON = "runs/gpcr_ci_low_recovery_packet_current.json"
DEFAULT_GPCR_POSITIVE_COVERAGE_JSON = "runs/gpcr_positive_coverage_freeze_packet_current.json"
DEFAULT_GPCR_GUARDED_100K_READINESS_JSON = "runs/gpcr_guarded_100k_rerun_readiness_current.json"
DEFAULT_PDE_TRANSLATION_JSON = "runs/wetlab_tcruzi_pde_translation_quality_packet_current.json"
DEFAULT_TRANSPORTER_BLOCKER_JSON = "runs/transporter_authoritative_apply_blocker_decomposition_current.json"
DEFAULT_CA2_READINESS_JSON = "runs/ca2_packet_replacement_readiness_current.json"
DEFAULT_PXR_READINESS_JSON = "runs/pxr_packet_fill_readiness_current.json"
DEFAULT_IDP_PROMOTION_JSON = "runs/idp_broader_promotion_resolution_current.json"
DEFAULT_OUT_JSON = "runs/post_p0_claim_blocker_rollup_current.json"
DEFAULT_OUT_MD = "runs/post_p0_claim_blocker_rollup_current.md"


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    if path.is_absolute():
        return path
    return (ROOT / path).resolve()


def _read_json(path_like: str | Path) -> dict[str, Any]:
    path = _resolve(path_like)
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as fh:
        payload = json.load(fh)
    return payload if isinstance(payload, dict) else {}


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _text(value: Any) -> str:
    return str(value or "").strip()


def _int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _float(value: Any) -> float | None:
    try:
        if value in {None, ""}:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _status(claim_promotion_allowed: bool, blocker_count: int) -> str:
    if claim_promotion_allowed:
        return "ready_for_claim_review"
    if blocker_count > 0:
        return "blocked"
    return "internal_review"


def _gpcr_row(
    payload: dict[str, Any],
    coverage_payload: dict[str, Any] | None = None,
    guarded_readiness_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    summary = dict(payload.get("summary", {}) or {})
    rank = dict(payload.get("rank_diagnostics", {}) or {})
    coverage = dict(payload.get("claim_coverage_requirement", {}) or {})
    coverage_summary = dict((coverage_payload or {}).get("summary", {}) or {})
    readiness_summary = dict((guarded_readiness_payload or {}).get("summary", {}) or {})
    ci_policy = dict(coverage.get("ci_low_policy", {}) or {})
    frozen_coverage = bool(coverage_summary.get("frozen", False))
    gap = (
        0
        if frozen_coverage
        else _int(coverage_summary.get("minimum_non_leaky_positive_additions", coverage.get("positive_coverage_gap")))
    )
    ci_low_blocker = bool(summary.get("ci_low_blocker", False))
    readiness_blockers = readiness_summary.get("blockers", [])
    if not isinstance(readiness_blockers, list):
        readiness_blockers = []
    launch_blockers = readiness_summary.get("launch_blockers", [])
    if not isinstance(launch_blockers, list):
        launch_blockers = []
    readiness_blocker_count = _int(readiness_summary.get("blocker_count"))
    blocker_count = max(int(ci_low_blocker) + int(gap > 0), readiness_blocker_count)
    readiness_ready = bool(readiness_summary.get("launch_eligible", readiness_summary.get("eligible", False)))
    claim_review_ready = bool(readiness_summary.get("claim_review_eligible", readiness_summary.get("eligible", False)))
    return {
        "priority_rank": 0,
        "lane_id": "gpcr_scaleup_ci_low",
        "claim_scope": "gpcr_scaleup_recovery",
        "status": _status(False, blocker_count),
        "claim_promotion_allowed": False,
        "comparison_only": True,
        "primary_blocker": (
            "guarded_100k_launch_blocked"
            if guarded_readiness_payload and not readiness_ready
            else "guarded_100k_claim_review_blocked"
            if guarded_readiness_payload and readiness_ready and not claim_review_ready
            else "ranking_pr_auc_ci_low_positive_coverage"
        ),
        "blocker_count": blocker_count,
        "primary_metric": "ranking_pr_auc_ci_low",
        "metric_value": _float(summary.get("ranking_pr_auc_ci_low")),
        "metric_threshold": _float(summary.get("threshold")),
        "positive_count": _int(summary.get("ranking_positive_count")),
        "positive_coverage_gap": gap,
        "top20_hit_rate": _float(summary.get("ranking_topk_hit_rate")),
        "top20_ceiling": _float(rank.get("top20_hit_rate_max_possible")),
        "top20_missing_positives": ", ".join(
            _text(row.get("ligand_id")) for row in rank.get("top20_missing_positives", []) if isinstance(row, dict)
        ),
        "next_required_step": _text(readiness_summary.get("next_required_step"))
        or "; ".join(coverage.get("required_next_evidence", []) or [])
        or _text(coverage_summary.get("next_required_step"))
        or "Keep claim_promotion_allowed=false until CI-low, positive coverage, and family-held-out gates clear.",
        "source_artifact": DEFAULT_GPCR_CI_LOW_JSON,
        "coverage_source_artifact": DEFAULT_GPCR_POSITIVE_COVERAGE_JSON if coverage_payload else "",
        "guarded_100k_readiness_source_artifact": (
            DEFAULT_GPCR_GUARDED_100K_READINESS_JSON if guarded_readiness_payload else ""
        ),
        "guarded_100k_rerun_ready": readiness_ready,
        "guarded_100k_claim_review_ready": claim_review_ready,
        "guarded_100k_launch_blockers": ", ".join(_text(row) for row in launch_blockers),
        "guarded_100k_blockers": ", ".join(_text(row) for row in readiness_blockers),
        "full_100k_guarded_rerun_eligible": readiness_ready,
        "claim_policy": "do_not_promote_recovery_band_signal",
        "policy_status": _text(ci_policy.get("status")) or "blocked",
    }


def _pde_row(payload: dict[str, Any]) -> dict[str, Any]:
    summary = dict(payload.get("summary", {}) or {})
    missing_count = _int(summary.get("measurement_gap_count", summary.get("missing_evidence_count", 0)))
    failed_count = _int(summary.get("failed_evidence_count"))
    claim_allowed = bool(summary.get("claim_promotion_allowed", False))
    return {
        "priority_rank": 1,
        "lane_id": "pde_translation_quality",
        "claim_scope": _text(summary.get("claim_scope")) or "post_p0_quality_followup_only",
        "status": _status(claim_allowed, failed_count + missing_count),
        "claim_promotion_allowed": claim_allowed,
        "comparison_only": False,
        "primary_blocker": _text(summary.get("primary_blocker")) or "translation_quality_evidence",
        "blocker_count": failed_count + missing_count,
        "primary_metric": "translation_gate_focus_score",
        "metric_value": _float(summary.get("translation_gate_focus_score")),
        "metric_threshold": None,
        "positive_count": None,
        "positive_coverage_gap": None,
        "top20_hit_rate": None,
        "top20_ceiling": None,
        "top20_missing_positives": "",
        "next_required_step": _text(summary.get("next_required_step")),
        "source_artifact": DEFAULT_PDE_TRANSLATION_JSON,
        "claim_policy": "do_not_expand_broad_translation_claim_until_quality_closed",
        "policy_status": _text(summary.get("claim_policy_status")) or "blocked_post_p0_quality_followup",
    }


def _transporter_row(payload: dict[str, Any]) -> dict[str, Any]:
    summary = dict(payload.get("summary", {}) or {})
    blocker_count = _int(summary.get("blocker_count", summary.get("hard_blocker_count", 0)))
    ready = bool(summary.get("authoritative_apply_ready", False))
    return {
        "priority_rank": 2,
        "lane_id": "transporter_aqp1_glut1_evidence",
        "claim_scope": "transporter_review_only",
        "status": _status(ready, blocker_count),
        "claim_promotion_allowed": False,
        "comparison_only": False,
        "primary_blocker": _text(summary.get("top_blocker_id")) or "transporter_authoritative_apply_blocked",
        "blocker_count": blocker_count,
        "primary_metric": "hard_blocker_count",
        "metric_value": _float(summary.get("hard_blocker_count")),
        "metric_threshold": 0.0,
        "positive_count": None,
        "positive_coverage_gap": None,
        "top20_hit_rate": None,
        "top20_ceiling": None,
        "top20_missing_positives": "",
        "next_required_step": _text(summary.get("next_required_step")),
        "source_artifact": DEFAULT_TRANSPORTER_BLOCKER_JSON,
        "claim_policy": "keep_aqp1_glut1_outside_delivery_claim",
        "policy_status": "blocked_review_only",
    }


def _ca2_row(payload: dict[str, Any]) -> dict[str, Any]:
    summary = dict(payload.get("summary", {}) or {})
    blocked_count = _int(summary.get("blocked_row_count"))
    ready_count = _int(summary.get("ready_row_count"))
    return {
        "priority_rank": 3,
        "lane_id": "ca2_packet_replacement",
        "claim_scope": "ca2_prep_only",
        "status": _status(False, blocked_count),
        "claim_promotion_allowed": False,
        "comparison_only": False,
        "primary_blocker": _text(summary.get("most_common_missing_field")) or "ca2_replacement_workbook_blocked",
        "blocker_count": blocked_count,
        "primary_metric": "ready_row_count",
        "metric_value": float(ready_count),
        "metric_threshold": _float(summary.get("workbook_row_count")),
        "positive_count": None,
        "positive_coverage_gap": None,
        "top20_hit_rate": None,
        "top20_ceiling": None,
        "top20_missing_positives": "",
        "next_required_step": _text(summary.get("next_required_step")),
        "source_artifact": DEFAULT_CA2_READINESS_JSON,
        "claim_policy": "prep_only_until_replacement_reference_binding_closed",
        "policy_status": "blocked_prep_only",
    }


def _pxr_row(payload: dict[str, Any]) -> dict[str, Any]:
    summary = dict(payload.get("summary", {}) or {})
    blocked_count = _int(summary.get("blocked_row_count"))
    ready_count = _int(summary.get("ready_for_apply_row_count"))
    return {
        "priority_rank": 4,
        "lane_id": "pxr_packet_fill",
        "claim_scope": "pxr_partial_authoritative_prep_only",
        "status": _status(False, blocked_count),
        "claim_promotion_allowed": False,
        "comparison_only": False,
        "primary_blocker": _text(summary.get("most_common_missing_field")) or "pxr_packet_fill_blocked",
        "blocker_count": blocked_count,
        "primary_metric": "ready_for_apply_row_count",
        "metric_value": float(ready_count),
        "metric_threshold": _float(summary.get("queue_row_count")),
        "positive_count": None,
        "positive_coverage_gap": None,
        "top20_hit_rate": None,
        "top20_ceiling": None,
        "top20_missing_positives": "",
        "next_required_step": _text(summary.get("next_required_step")),
        "source_artifact": DEFAULT_PXR_READINESS_JSON,
        "claim_policy": "prep_only_until_quantitative_provenance_closed",
        "policy_status": "blocked_partial_authoritative",
    }


def _idp_row(payload: dict[str, Any]) -> dict[str, Any]:
    summary = dict(payload.get("summary", {}) or {})
    blocked = bool(summary.get("broader_promotion_blocked", True))
    return {
        "priority_rank": 5,
        "lane_id": "idp_broader_promotion",
        "claim_scope": _text(summary.get("operator_scope_now")) or "one_wider_shadow_safe_lane_only",
        "status": "blocked" if blocked else "internal_review",
        "claim_promotion_allowed": False,
        "comparison_only": True,
        "primary_blocker": _text(summary.get("blocking_target")) or "broader_full_idp_promotion",
        "blocker_count": int(blocked),
        "primary_metric": "broader_promotion_blocked",
        "metric_value": float(int(blocked)),
        "metric_threshold": 0.0,
        "positive_count": None,
        "positive_coverage_gap": None,
        "top20_hit_rate": None,
        "top20_ceiling": None,
        "top20_missing_positives": "",
        "next_required_step": _text(summary.get("next_required_step")),
        "source_artifact": DEFAULT_IDP_PROMOTION_JSON,
        "claim_policy": "bounded_shadow_lane_only_not_commercialized",
        "policy_status": _text(summary.get("status")) or "broader_promotion_blocked",
    }


def build_payload(
    gpcr_ci_low: dict[str, Any],
    pde_translation: dict[str, Any],
    transporter_blocker: dict[str, Any],
    ca2_readiness: dict[str, Any],
    pxr_readiness: dict[str, Any],
    idp_promotion: dict[str, Any],
    gpcr_positive_coverage: dict[str, Any] | None = None,
    gpcr_guarded_100k_readiness: dict[str, Any] | None = None,
) -> dict[str, Any]:
    rows = [
        _gpcr_row(gpcr_ci_low, gpcr_positive_coverage, gpcr_guarded_100k_readiness),
        _pde_row(pde_translation),
        _transporter_row(transporter_blocker),
        _ca2_row(ca2_readiness),
        _pxr_row(pxr_readiness),
        _idp_row(idp_promotion),
    ]
    blocked_rows = [row for row in rows if row["claim_promotion_allowed"] is not True]
    summary = {
        "status": "post_p0_claim_blocker_rollup_ready",
        "delivery_claim_unchanged": True,
        "current_delivery_claim_scope": "restricted_kinase_ion_channel_gpcr",
        "lane_count": len(rows),
        "blocked_lane_count": len(blocked_rows),
        "claim_promotion_allowed_lane_count": sum(1 for row in rows if row["claim_promotion_allowed"]),
        "top_priority_lane_id": rows[0]["lane_id"],
        "top_priority_primary_blocker": rows[0]["primary_blocker"],
        "top_priority_next_required_step": rows[0]["next_required_step"],
        "next_required_step": (
            "Launch/refresh GPCR guarded 100k evidence first, then PDE translation quality, then transporter, "
            "CA2, PXR, and IDP evidence boundaries without widening the delivery claim."
        ),
    }
    return {"summary": summary, "rows": rows}


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# Post-P0 Claim Blocker Rollup",
        "",
        f"- delivery_claim_unchanged: `{summary['delivery_claim_unchanged']}`",
        f"- current_delivery_claim_scope: `{summary['current_delivery_claim_scope']}`",
        f"- blocked_lane_count: `{summary['blocked_lane_count']}`",
        f"- top_priority_lane_id: `{summary['top_priority_lane_id']}`",
        f"- top_priority_primary_blocker: `{summary['top_priority_primary_blocker']}`",
        "",
        "## Next Step",
        "",
        f"- {summary['next_required_step']}",
        "",
        "## Lanes",
        "",
        "| priority | lane_id | status | claim_promotion_allowed | primary_blocker | source_artifact | next_required_step |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            "| {priority} | `{lane_id}` | `{status}` | `{allowed}` | `{blocker}` | `{artifact}` | {next_step} |".format(
                priority=row["priority_rank"],
                lane_id=row["lane_id"],
                status=row["status"],
                allowed=str(row["claim_promotion_allowed"]).lower(),
                blocker=row["primary_blocker"],
                artifact=row["source_artifact"],
                next_step=row["next_required_step"],
            )
        )
    lines.append("")
    return "\n".join(lines)


def write_outputs(args: argparse.Namespace) -> dict[str, Any]:
    payload = build_payload(
        gpcr_ci_low=_read_json(args.gpcr_ci_low_json),
        gpcr_positive_coverage=_read_json(args.gpcr_positive_coverage_json),
        gpcr_guarded_100k_readiness=_read_json(args.gpcr_guarded_100k_readiness_json),
        pde_translation=_read_json(args.pde_translation_json),
        transporter_blocker=_read_json(args.transporter_blocker_json),
        ca2_readiness=_read_json(args.ca2_readiness_json),
        pxr_readiness=_read_json(args.pxr_readiness_json),
        idp_promotion=_read_json(args.idp_promotion_json),
    )
    _write_json(args.out_json, payload)
    out_md = _resolve(args.out_md)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text(render_markdown(payload), encoding="utf-8")
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a post-P0 blocker rollup without widening claim scope.")
    parser.add_argument("--gpcr-ci-low-json", default=DEFAULT_GPCR_CI_LOW_JSON)
    parser.add_argument("--gpcr-positive-coverage-json", default=DEFAULT_GPCR_POSITIVE_COVERAGE_JSON)
    parser.add_argument("--gpcr-guarded-100k-readiness-json", default=DEFAULT_GPCR_GUARDED_100K_READINESS_JSON)
    parser.add_argument("--pde-translation-json", default=DEFAULT_PDE_TRANSLATION_JSON)
    parser.add_argument("--transporter-blocker-json", default=DEFAULT_TRANSPORTER_BLOCKER_JSON)
    parser.add_argument("--ca2-readiness-json", default=DEFAULT_CA2_READINESS_JSON)
    parser.add_argument("--pxr-readiness-json", default=DEFAULT_PXR_READINESS_JSON)
    parser.add_argument("--idp-promotion-json", default=DEFAULT_IDP_PROMOTION_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    write_outputs(parse_args())


if __name__ == "__main__":
    main()

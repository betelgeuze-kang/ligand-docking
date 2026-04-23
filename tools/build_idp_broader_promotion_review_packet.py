#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows
from tools.operator_surface_contracts import (
    IDP_BLOCKED_SCOPE_BROADER_FULL_PROMOTION,
    IDP_SAFE_SCOPE_CONTROLLED_PRETEST,
    IDP_SAFE_SCOPE_ONE_WIDER_SHADOW_SAFE_LANE,
)

ROOT = Path(__file__).resolve().parents[1]

DEFAULT_BROADER_RESULT_JSON = "runs/idp_broader_shadow_result_current.json"
DEFAULT_BROADER_DECISION_JSON = "runs/idp_broader_shadow_decision_current.json"
DEFAULT_OUT_JSON = "runs/idp_broader_promotion_review_packet_current.json"
DEFAULT_OUT_CSV = "runs/idp_broader_promotion_review_packet_current.csv"
DEFAULT_OUT_MD = "runs/idp_broader_promotion_review_packet_current.md"


def _resolve(path_like: str) -> Path:
    path = Path(path_like)
    if path.is_absolute():
        return path
    cwd_path = (Path.cwd() / path).resolve()
    if cwd_path.exists():
        return cwd_path
    return (ROOT / path).resolve()


def _load_json(path_like: str) -> dict[str, Any]:
    with _resolve(path_like).open("r", encoding="utf-8") as fh:
        return json.load(fh)


def build_payload(
    broader_result: dict[str, Any],
    broader_decision: dict[str, Any],
) -> dict[str, Any]:
    result_s = dict((broader_result.get("summary") if isinstance(broader_result.get("summary"), dict) else {}) or {})
    decision_s = dict((broader_decision.get("summary") if isinstance(broader_decision.get("summary"), dict) else {}) or {})

    wider_lane_candidate = (
        bool(result_s.get("true_broader_shadow_passed", False))
        and bool(result_s.get("shadow_safe_retained", False))
        and bool(result_s.get("combined_gate_pass", False))
        and int(result_s.get("fold_count", 0) or 0) == int(result_s.get("corrected_pass_folds", 0) or 0)
        and bool(result_s.get("page4_fold_pass", False))
        and bool(result_s.get("tau_k18_fold_pass", False))
    )

    rows = [
        {
            "review_item": "lane_admission",
            "status": "accept_with_guardrails" if wider_lane_candidate else "keep_blocked",
            "current_signal": (
                f"broader_shadow_passed={result_s.get('true_broader_shadow_passed', False)}; "
                f"shadow_safe_retained={result_s.get('shadow_safe_retained', False)}; "
                f"combined_gate_pass={result_s.get('combined_gate_pass', False)}"
            ),
            "recommended_resolution": (
                f"Admit exactly one `{IDP_SAFE_SCOPE_ONE_WIDER_SHADOW_SAFE_LANE}` scope beyond the bounded commercial-pretest lane."
                if wider_lane_candidate
                else "Keep the wider lane blocked until the broader shadow pass is fully clean."
            ),
        },
        {
            "review_item": "frozen_roster",
            "status": "accept_with_guardrails" if wider_lane_candidate else "review_now",
            "current_signal": (
                f"validated_current_target_count={result_s.get('validated_current_target_count', 0)}; "
                f"additional_anchor_backed_target_count={result_s.get('additional_anchor_backed_target_count', 0)}; "
                f"page4_fold_pass={result_s.get('page4_fold_pass', False)}"
            ),
            "recommended_resolution": "Freeze the wider lane to the validated 7-target scaffold plus PAGE4 only.",
        },
        {
            "review_item": "guardrail_freeze",
            "status": "keep_frozen",
            "current_signal": "feature_state_smoothing_only; no_coordinate_correction; no_ranking_override; no_gate_override",
            "recommended_resolution": "Keep the exact no-override guardrails unchanged for the admitted wider lane.",
        },
        {
            "review_item": "commercialization_boundary",
            "status": "keep_blocked",
            "current_signal": (
                f"blocking_target={decision_s.get('blocking_target', 'promotion_review')}; "
                f"blocked_scope={IDP_BLOCKED_SCOPE_BROADER_FULL_PROMOTION}"
            ),
            "recommended_resolution": (
                "Do not treat the admitted wider lane as automatic commercialization or unrestricted broader-full promotion."
            ),
        },
    ]

    summary = {
        "status": (
            "broader_promotion_review_packet_ready_wider_lane_candidate"
            if wider_lane_candidate
            else "broader_promotion_review_packet_attention_required"
        ),
        "operator_scope_now": str(decision_s.get("operator_scope_now", "")).strip() or IDP_SAFE_SCOPE_CONTROLLED_PRETEST,
        "candidate_scope_next": IDP_SAFE_SCOPE_ONE_WIDER_SHADOW_SAFE_LANE,
        "blocked_scope": IDP_BLOCKED_SCOPE_BROADER_FULL_PROMOTION,
        "shadow_safe_retained": bool(result_s.get("shadow_safe_retained", False)),
        "broader_shadow_passed": bool(result_s.get("true_broader_shadow_passed", False)),
        "review_item_count": len(rows),
        "recommended_accept_with_guardrails_count": sum(1 for row in rows if row["status"] == "accept_with_guardrails"),
        "wider_lane_candidate_ready": wider_lane_candidate,
        "frozen_total_target_count": int(result_s.get("validated_current_target_count", 0) or 0)
        + int(result_s.get("additional_anchor_backed_target_count", 0) or 0),
        "next_required_step": (
            f"Resolve this promotion review by admitting exactly one `{IDP_SAFE_SCOPE_ONE_WIDER_SHADOW_SAFE_LANE}` scope frozen to the validated 7-target scaffold plus PAGE4, while keeping `{IDP_BLOCKED_SCOPE_BROADER_FULL_PROMOTION}` blocked."
            if wider_lane_candidate
            else "Keep broader promotion blocked and resolve the remaining broader-shadow cleanliness issues before admitting any wider lane."
        ),
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# IDP Broader Promotion Review Packet",
        "",
        f"- status: `{s['status']}`",
        f"- operator_scope_now: `{s['operator_scope_now']}`",
        f"- candidate_scope_next: `{s['candidate_scope_next']}`",
        f"- blocked_scope: `{s['blocked_scope']}`",
        f"- shadow_safe_retained: `{s['shadow_safe_retained']}`",
        f"- broader_shadow_passed: `{s['broader_shadow_passed']}`",
        f"- review_item_count: `{s['review_item_count']}`",
        f"- recommended_accept_with_guardrails_count: `{s['recommended_accept_with_guardrails_count']}`",
        f"- wider_lane_candidate_ready: `{s['wider_lane_candidate_ready']}`",
        f"- frozen_total_target_count: `{s['frozen_total_target_count']}`",
        "",
        "## Review Items",
        "",
        "| review_item | status | current_signal | recommended_resolution |",
        "| --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['review_item']}` | `{row['status']}` | `{row['current_signal']}` | {row['recommended_resolution']} |"
        )
    lines.extend(["", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the IDP broader promotion review packet after a completed broader shadow pass.")
    parser.add_argument("--broader-result-json", default=DEFAULT_BROADER_RESULT_JSON)
    parser.add_argument("--broader-decision-json", default=DEFAULT_BROADER_DECISION_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        _load_json(args.broader_result_json),
        _load_json(args.broader_decision_json),
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

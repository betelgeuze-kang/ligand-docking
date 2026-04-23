#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.operator_surface_contracts import (
    IDP_BLOCKED_SCOPE_BROADER_FULL_PROMOTION,
    IDP_SAFE_SCOPE_ONE_WIDER_SHADOW_SAFE_LANE,
)

ROOT = Path(__file__).resolve().parents[1]

DEFAULT_REVIEW_PACKET_JSON = "runs/idp_broader_promotion_review_packet_current.json"
DEFAULT_BROADER_RESULT_JSON = "runs/idp_broader_shadow_result_current.json"
DEFAULT_OUT_JSON = "runs/idp_broader_promotion_resolution_current.json"
DEFAULT_OUT_MD = "runs/idp_broader_promotion_resolution_current.md"


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
    review_packet: dict[str, Any],
    broader_result: dict[str, Any],
) -> dict[str, Any]:
    review_s = dict((review_packet.get("summary") if isinstance(review_packet.get("summary"), dict) else {}) or {})
    result_s = dict((broader_result.get("summary") if isinstance(broader_result.get("summary"), dict) else {}) or {})

    wider_lane_admitted = bool(review_s.get("wider_lane_candidate_ready", False))

    if wider_lane_admitted:
        decision = "one_wider_shadow_safe_lane_admitted"
        status = "one_wider_shadow_safe_lane_admitted_not_commercialized"
        blocking_target = "commercialization_boundary"
        blocking_class = "bounded_wider_lane_only"
        blocker_reason = (
            "The completed first broader shadow-only IDP pass justifies admitting exactly one wider shadow-safe lane frozen to the validated 7-target scaffold plus PAGE4. "
            f"`{IDP_BLOCKED_SCOPE_BROADER_FULL_PROMOTION}` remains blocked because this is a bounded shadow-safe expansion, not unrestricted broader promotion or automatic commercialization."
        )
        next_required_step = (
            f"Run only the admitted `{IDP_SAFE_SCOPE_ONE_WIDER_SHADOW_SAFE_LANE}` scope frozen to the validated 7-target scaffold plus PAGE4, keep the same no-override guardrails, and do not widen the roster or claim commercialization beyond that bounded lane."
        )
    else:
        decision = "keep_one_wider_shadow_safe_lane_blocked"
        status = "one_wider_shadow_safe_lane_attention_required"
        blocking_target = "promotion_review"
        blocking_class = "explicit_promotion_decision_required"
        blocker_reason = "The broader shadow result is not yet clean enough to admit a wider shadow-safe lane."
        next_required_step = "Keep broader promotion blocked and resolve promotion review attention items before admitting any wider lane."

    summary = {
        "decision": decision,
        "status": status,
        "operator_scope_now": IDP_SAFE_SCOPE_ONE_WIDER_SHADOW_SAFE_LANE if wider_lane_admitted else str(review_s.get("operator_scope_now", "")).strip(),
        "blocked_scope": IDP_BLOCKED_SCOPE_BROADER_FULL_PROMOTION,
        "shadow_safe_retained": bool(result_s.get("shadow_safe_retained", False)),
        "broader_promotion_blocked": True,
        "wider_shadow_safe_lane_admitted": wider_lane_admitted,
        "frozen_validated_current_target_count": int(result_s.get("validated_current_target_count", 0) or 0),
        "frozen_additional_anchor_backed_target_count": int(result_s.get("additional_anchor_backed_target_count", 0) or 0),
        "frozen_total_target_count": int(review_s.get("frozen_total_target_count", 0) or 0),
        "page4_fold_pass": bool(result_s.get("page4_fold_pass", False)),
        "tau_k18_fold_pass": bool(result_s.get("tau_k18_fold_pass", False)),
        "blocking_target": blocking_target,
        "blocking_class": blocking_class,
        "blocker_reason": blocker_reason,
        "next_required_step": next_required_step,
    }
    return {"summary": summary}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# IDP Broader Promotion Resolution",
        "",
        f"- decision: `{s['decision']}`",
        f"- status: `{s['status']}`",
        f"- operator_scope_now: `{s['operator_scope_now']}`",
        f"- blocked_scope: `{s['blocked_scope']}`",
        f"- shadow_safe_retained: `{s['shadow_safe_retained']}`",
        f"- broader_promotion_blocked: `{s['broader_promotion_blocked']}`",
        f"- wider_shadow_safe_lane_admitted: `{s['wider_shadow_safe_lane_admitted']}`",
        f"- frozen_validated_current_target_count: `{s['frozen_validated_current_target_count']}`",
        f"- frozen_additional_anchor_backed_target_count: `{s['frozen_additional_anchor_backed_target_count']}`",
        f"- frozen_total_target_count: `{s['frozen_total_target_count']}`",
        f"- page4_fold_pass: `{s['page4_fold_pass']}`",
        f"- tau_k18_fold_pass: `{s['tau_k18_fold_pass']}`",
        f"- blocking_target: `{s['blocking_target']}`",
        f"- blocking_class: `{s['blocking_class']}`",
        "",
        s["blocker_reason"],
        "",
        "## Next Step",
        "",
        f"- {s['next_required_step']}",
        "",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Resolve the IDP broader promotion review into a bounded wider-lane decision.")
    parser.add_argument("--review-packet-json", default=DEFAULT_REVIEW_PACKET_JSON)
    parser.add_argument("--broader-result-json", default=DEFAULT_BROADER_RESULT_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        _load_json(args.review_packet_json),
        _load_json(args.broader_result_json),
    )
    out_json = _resolve(args.out_json)
    out_md = _resolve(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    _write_markdown(out_md, payload)


if __name__ == "__main__":
    main()

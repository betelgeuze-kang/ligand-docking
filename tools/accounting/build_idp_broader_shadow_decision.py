#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.operator_surface_contracts import IDP_SAFE_SCOPE_CONTROLLED_PRETEST

ROOT = Path(__file__).resolve().parents[1]

DEFAULT_BROADER_RESULT_JSON = "runs/idp_broader_shadow_result_current.json"
DEFAULT_COMMERCIAL_PRETEST_DECISION_JSON = "runs/idp_commercial_pretest_decision_current.json"
DEFAULT_OUT_JSON = "runs/idp_broader_shadow_decision_current.json"
DEFAULT_OUT_MD = "runs/idp_broader_shadow_decision_current.md"


def _resolve(path_like: str) -> Path:
    path = Path(path_like)
    if path.is_absolute():
        return path
    cwd_path = (Path.cwd() / path).resolve()
    if cwd_path.exists():
        return cwd_path
    return (ROOT / path).resolve()


def _read_json(path_like: str) -> dict[str, Any]:
    with _resolve(path_like).open("r", encoding="utf-8") as fh:
        return json.load(fh)


def build_payload(
    broader_result: dict[str, Any],
    commercial_pretest_decision: dict[str, Any],
) -> dict[str, Any]:
    result_s = dict((broader_result.get("summary") if isinstance(broader_result.get("summary"), dict) else {}) or {})
    pretest_s = dict((commercial_pretest_decision.get("summary") if isinstance(commercial_pretest_decision.get("summary"), dict) else {}) or {})

    passed_clean = (
        bool(result_s.get("true_broader_shadow_passed", False))
        and bool(result_s.get("shadow_safe_retained", False))
        and bool(result_s.get("combined_gate_pass", False))
        and int(result_s.get("fold_count", 0) or 0) == int(result_s.get("corrected_pass_folds", 0) or 0)
    )

    if passed_clean:
        decision = "broader_shadow_passed_promotion_review_reopen"
        status = "controlled_shadow_only_commercial_pretest_broader_shadow_completed"
        blocker_reason = (
            "The first true broader shadow-only IDP rerun with PAGE4 passed cleanly across 8/8 folds with zero state/gate drift on the validated current targets. "
            "broader_full_idp_promotion remains blocked until an explicit promotion review decides whether to widen the allowed shadow-safe lane beyond the bounded commercial-pretest set."
        )
        next_required_step = (
            "Keep broader_full_idp_promotion blocked, reopen promotion review using the completed broader-shadow result, and decide explicitly whether to admit one wider shadow-safe lane beyond the bounded commercial-pretest set; do not treat this broader shadow pass as automatic commercialization or unrestricted broader promotion."
        )
    else:
        decision = "broader_shadow_attention_required_keep_promotion_blocked"
        status = "controlled_shadow_only_commercial_pretest_broader_shadow_attention_required"
        blocker_reason = (
            "The first broader shadow-only rerun completed, but the result is not clean enough to reopen promotion review without attention."
        )
        next_required_step = (
            "Keep broader_full_idp_promotion blocked and inspect the broader-shadow result before any promotion review."
        )

    summary = {
        "decision": decision,
        "status": status,
        "operator_scope_now": str(pretest_s.get("operator_scope_now", "")).strip() or IDP_SAFE_SCOPE_CONTROLLED_PRETEST,
        "shadow_safe_retained": bool(result_s.get("shadow_safe_retained", False)),
        "broader_promotion_blocked": True,
        "broader_shadow_completed": bool(result_s.get("true_broader_shadow_completed", False)),
        "broader_shadow_passed": bool(result_s.get("true_broader_shadow_passed", False)),
        "validated_current_target_count": int(result_s.get("validated_current_target_count", 0) or 0),
        "additional_anchor_backed_target_count": int(result_s.get("additional_anchor_backed_target_count", 0) or 0),
        "fold_count": int(result_s.get("fold_count", 0) or 0),
        "corrected_pass_folds": int(result_s.get("corrected_pass_folds", 0) or 0),
        "combined_gate_pass": bool(result_s.get("combined_gate_pass", False)),
        "page4_fold_pass": bool(result_s.get("page4_fold_pass", False)),
        "tau_k18_fold_pass": bool(result_s.get("tau_k18_fold_pass", False)),
        "blocking_target": "promotion_review",
        "blocking_class": "explicit_promotion_decision_required",
        "blocker_reason": blocker_reason,
        "decision_reason": blocker_reason,
        "default_feature_mask": str(pretest_s.get("default_feature_mask", "")).strip(),
        "next_required_step": next_required_step,
    }
    return {"summary": summary}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# IDP Broader Shadow Decision",
        "",
        f"- decision: `{s['decision']}`",
        f"- status: `{s['status']}`",
        f"- operator_scope_now: `{s['operator_scope_now']}`",
        f"- shadow_safe_retained: `{s['shadow_safe_retained']}`",
        f"- broader_promotion_blocked: `{s['broader_promotion_blocked']}`",
        f"- broader_shadow_completed: `{s['broader_shadow_completed']}`",
        f"- broader_shadow_passed: `{s['broader_shadow_passed']}`",
        f"- validated_current_target_count: `{s['validated_current_target_count']}`",
        f"- additional_anchor_backed_target_count: `{s['additional_anchor_backed_target_count']}`",
        f"- fold_count: `{s['fold_count']}`",
        f"- corrected_pass_folds: `{s['corrected_pass_folds']}`",
        f"- combined_gate_pass: `{s['combined_gate_pass']}`",
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
    ap = argparse.ArgumentParser(description="Build the IDP broader-shadow decision artifact.")
    ap.add_argument("--broader-result-json", default=DEFAULT_BROADER_RESULT_JSON)
    ap.add_argument("--commercial-pretest-decision-json", default=DEFAULT_COMMERCIAL_PRETEST_DECISION_JSON)
    ap.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    ap.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return ap.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        _read_json(args.broader_result_json),
        _read_json(args.commercial_pretest_decision_json),
    )
    out_json = _resolve(args.out_json)
    out_md = _resolve(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    _write_markdown(out_md, payload)


if __name__ == "__main__":
    main()

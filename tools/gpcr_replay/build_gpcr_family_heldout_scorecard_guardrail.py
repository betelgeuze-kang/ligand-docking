#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]

DEFAULT_SCORECARD_JSON = "runs/gpcr_family_heldout_scorecard_current.json"
DEFAULT_OUT_JSON = "runs/gpcr_family_heldout_scorecard_guardrail_current.json"
DEFAULT_OUT_MD = "runs/gpcr_family_heldout_scorecard_guardrail_current.md"


def _resolve(path_like: str | Path | None) -> Path | None:
    if path_like is None or str(path_like).strip() == "":
        return None
    path = Path(path_like)
    return path.resolve() if path.is_absolute() else (ROOT / path).resolve()


def _read_json(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _text(value: Any) -> str:
    return str(value or "").strip()


def _has_blocking_warnings(scorecard: dict[str, Any]) -> bool:
    return bool(_blocking_warning_reasons(scorecard))


def _blocking_warning_reasons(scorecard: dict[str, Any]) -> list[str]:
    warnings = scorecard.get("warnings", [])
    if not isinstance(warnings, list):
        return []
    blocking_reasons = {
        "duplicate_row_identity",
        "insufficient_distinct_gpcr_positive_targets",
        "insufficient_gpcr_positive_count",
        "missing_required_family",
        "missing_artifact",
        "missing_or_non_finite_scores",
        "single_class_labels",
        "target_specific_adrb2_bias_risk",
    }
    reasons: list[str] = []
    for row in warnings:
        if not isinstance(row, dict):
            continue
        reason = _text(row.get("reason"))
        severity = _text(row.get("severity")).lower()
        if reason and (reason in blocking_reasons or severity == "blocking"):
            reasons.append(reason)
    return sorted(set(reasons))


def _gpcr_family_present(scorecard: dict[str, Any]) -> bool:
    families = scorecard.get("families")
    return isinstance(families, dict) and "gpcr" in {str(key).lower() for key in families}


def build_guardrail(scorecard_json: str | Path | None = DEFAULT_SCORECARD_JSON) -> dict[str, Any]:
    scorecard_path = _resolve(scorecard_json)
    scorecard = _read_json(scorecard_path)
    summary = scorecard.get("summary") if isinstance(scorecard.get("summary"), dict) else {}
    scorecard_available = bool(scorecard)
    gpcr_present = _gpcr_family_present(scorecard)
    status = _text(summary.get("scorecard_level_status"))
    acceptance = summary.get("acceptance_overall_pass")
    blocking_warning_reasons = _blocking_warning_reasons(scorecard)
    blocking_warnings = bool(blocking_warning_reasons)
    green = (
        scorecard_available
        and gpcr_present
        and status == "pass"
        and acceptance is not False
        and not blocking_warnings
    )
    blockers: list[str] = []
    if not scorecard_available:
        blockers.append("scorecard_missing")
    if scorecard_available and not gpcr_present:
        blockers.append("gpcr_family_missing")
    if scorecard_available and status != "pass":
        blockers.append("scorecard_level_status_not_pass")
    if scorecard_available and acceptance is False:
        blockers.append("acceptance_overall_pass_false")
    if blocking_warnings:
        blockers.append("blocking_scorecard_warnings_present")

    return {
        "packet_type": "gpcr_family_heldout_scorecard_guardrail",
        "source_artifact": str(scorecard_path) if scorecard_path else None,
        "summary": {
            "status": "green" if green else "blocked",
            "scorecard_available": scorecard_available,
            "gpcr_family_present": gpcr_present,
            "scorecard_level_status": status or None,
            "acceptance_overall_pass": acceptance,
            "blocking_warning_present": blocking_warnings,
            "blocking_warning_reasons": blocking_warning_reasons,
            "blocker_count": len(blockers),
            "blockers": blockers,
            "router_claim_allowed": False,
            "platform_claim_allowed": False,
            "claim_promotion_allowed": False,
            "next_required_step": (
                "Family-held-out scorecard is green; still require full 100k CI-low/coverage gate before claim review."
                if green
                else "Build a non-leaky GPCR family-held-out scorecard with required family gpcr and no blocking warnings before router/platform claim review."
            ),
        },
        "claim_boundary": {
            "router_platform_claim_forbidden_until_green": True,
            "scorecard_alone_does_not_make_claim_safe": True,
            "requires_full_100k_gate_too": True,
            "threshold_relaxation_allowed": False,
            "fake_pass_allowed": False,
        },
    }


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    return "\n".join(
        [
            "# GPCR Family-Held-Out Scorecard Guardrail",
            "",
            f"- status: `{summary['status']}`",
            f"- scorecard_available: `{str(summary['scorecard_available']).lower()}`",
            f"- gpcr_family_present: `{str(summary['gpcr_family_present']).lower()}`",
            f"- claim_promotion_allowed: `{str(summary['claim_promotion_allowed']).lower()}`",
            f"- router_claim_allowed: `{str(summary['router_claim_allowed']).lower()}`",
            f"- platform_claim_allowed: `{str(summary['platform_claim_allowed']).lower()}`",
            f"- blockers: `{', '.join(summary['blockers'])}`",
            "",
            "## Next Step",
            "",
            f"- {summary['next_required_step']}",
            "",
        ]
    )


def write_outputs(*, scorecard_json: str | Path | None, out_json: str | Path, out_md: str | Path) -> dict[str, Any]:
    payload = build_guardrail(scorecard_json)
    out_json_path = _resolve(out_json)
    out_md_path = _resolve(out_md)
    assert out_json_path is not None
    assert out_md_path is not None
    _write_json(out_json_path, payload)
    out_md_path.parent.mkdir(parents=True, exist_ok=True)
    out_md_path.write_text(render_markdown(payload), encoding="utf-8")
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build GPCR family-held-out scorecard guardrail packet.")
    parser.add_argument("--scorecard-json", default=DEFAULT_SCORECARD_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    write_outputs(scorecard_json=args.scorecard_json, out_json=args.out_json, out_md=args.out_md)


if __name__ == "__main__":
    main()

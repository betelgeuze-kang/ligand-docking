#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]

DEFAULT_POSITIVE_JSON = "runs/gpcr_positive_coverage_freeze_packet_current.json"
DEFAULT_SCOREABILITY_JSON = "runs/gpcr_frozen_candidate_scoreability_current.json"
DEFAULT_FAMILY_HELDOUT_JSON = "runs/gpcr_family_heldout_scorecard_guardrail_current.json"
DEFAULT_CI_LOW_JSON = "runs/gpcr_ci_low_recovery_packet_current.json"
DEFAULT_TRIAGE_JSON = "runs/gpcr_scaleup_regression_triage_current.json"
DEFAULT_LEAKAGE_AUDIT_JSON = "runs/gpcr_guarded_100k_leakage_audit_current.json"
DEFAULT_OUT_JSON = "runs/gpcr_guarded_100k_rerun_readiness_current.json"
DEFAULT_OUT_MD = "runs/gpcr_guarded_100k_rerun_readiness_current.md"

MIN_FROZEN_POSITIVE_COUNT = 9
MIN_NEW_NON_ADRB2_POSITIVE_COUNT = 3
MIN_DISTINCT_POSITIVE_GPCR_TARGET_COUNT = 2
MIN_RANKING_PR_AUC_CI_LOW = 0.45
MIN_TOP20_HIT_RATE = 0.20
MIN_TOP20_CEILING = 0.45


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


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return _text(value).lower() in {"1", "true", "yes", "y", "pass", "passed", "green", "eligible", "frozen"}


def _as_int(value: Any) -> int | None:
    try:
        if value is None or str(value).strip() == "":
            return None
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _as_float(value: Any) -> float | None:
    try:
        if value is None or str(value).strip() == "":
            return None
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if out == out else None


def _source_available(payload: dict[str, Any]) -> bool:
    return bool(payload)


def _positive_gate(payload: dict[str, Any]) -> dict[str, Any]:
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    positive_count = _as_int(payload.get("positive_count"))
    if positive_count is None:
        positive_count = _as_int(summary.get("positive_count"))
    new_non_adrb2_positive_count = _as_int(payload.get("new_non_adrb2_positive_count"))
    if new_non_adrb2_positive_count is None:
        new_non_adrb2_positive_count = _as_int(summary.get("new_non_adrb2_positive_count"))
    distinct_positive_gpcr_target_count = _as_int(payload.get("distinct_positive_gpcr_target_count"))
    if distinct_positive_gpcr_target_count is None:
        distinct_positive_gpcr_target_count = _as_int(summary.get("distinct_positive_gpcr_target_count"))
    leakage_audit_pass = _as_bool(payload.get("leakage_audit_pass")) or _as_bool(summary.get("leakage_audit_pass"))
    frozen = (
        _as_bool(payload.get("frozen"))
        and _text(payload.get("status") or summary.get("status")).lower() == "frozen"
    ) or _as_bool(summary.get("frozen"))
    green = (
        _source_available(payload)
        and frozen
        and positive_count is not None
        and positive_count >= MIN_FROZEN_POSITIVE_COUNT
        and new_non_adrb2_positive_count is not None
        and new_non_adrb2_positive_count >= MIN_NEW_NON_ADRB2_POSITIVE_COUNT
        and distinct_positive_gpcr_target_count is not None
        and distinct_positive_gpcr_target_count >= MIN_DISTINCT_POSITIVE_GPCR_TARGET_COUNT
        and leakage_audit_pass
    )
    blockers: list[str] = []
    if not _source_available(payload):
        blockers.append("positive_coverage_packet_missing")
    if positive_count is None or positive_count < MIN_FROZEN_POSITIVE_COUNT:
        blockers.append("positive_count_below_9")
    if new_non_adrb2_positive_count is None or new_non_adrb2_positive_count < MIN_NEW_NON_ADRB2_POSITIVE_COUNT:
        blockers.append("new_non_adrb2_positive_count_below_3")
    if (
        distinct_positive_gpcr_target_count is None
        or distinct_positive_gpcr_target_count < MIN_DISTINCT_POSITIVE_GPCR_TARGET_COUNT
    ):
        blockers.append("distinct_positive_gpcr_target_count_below_2")
    if not leakage_audit_pass:
        blockers.append("leakage_audit_not_passed")
    if not frozen:
        blockers.append("positive_coverage_not_frozen")
    return {
        "status": "green" if green else "blocked",
        "positive_count": positive_count,
        "minimum_positive_count": MIN_FROZEN_POSITIVE_COUNT,
        "new_non_adrb2_positive_count": new_non_adrb2_positive_count,
        "minimum_new_non_adrb2_positive_count": MIN_NEW_NON_ADRB2_POSITIVE_COUNT,
        "distinct_positive_gpcr_target_count": distinct_positive_gpcr_target_count,
        "minimum_distinct_positive_gpcr_target_count": MIN_DISTINCT_POSITIVE_GPCR_TARGET_COUNT,
        "leakage_audit_pass": bool(leakage_audit_pass),
        "frozen": bool(frozen),
        "blockers": blockers,
    }


def _family_gate(payload: dict[str, Any]) -> dict[str, Any]:
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    status = _text(summary.get("status")).lower()
    blockers = summary.get("blockers") if isinstance(summary.get("blockers"), list) else []
    green = _source_available(payload) and status == "green" and not blockers
    out_blockers: list[str] = []
    if not _source_available(payload):
        out_blockers.append("family_heldout_packet_missing")
    if status != "green" or blockers:
        out_blockers.append("family_heldout_not_green")
    return {
        "status": "green" if green else "blocked",
        "scorecard_status": status or None,
        "source_blockers": blockers,
        "blockers": out_blockers,
    }


def _scoreability_gate(payload: dict[str, Any]) -> dict[str, Any]:
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    blockers = summary.get("blockers") if isinstance(summary.get("blockers"), list) else []
    green = _source_available(payload) and (
        summary.get("pass") is True or _text(summary.get("status")).lower() == "pass"
    ) and not blockers
    out_blockers: list[str] = []
    if not _source_available(payload):
        out_blockers.append("frozen_candidate_scoreability_packet_missing")
    if _source_available(payload) and not green:
        out_blockers.append("frozen_candidate_scoreability_not_pass")
    return {
        "status": "green" if green else "blocked",
        "source_status": _text(summary.get("status")) or None,
        "source_blockers": blockers,
        "blockers": out_blockers,
    }


def _ci_gate(payload: dict[str, Any]) -> dict[str, Any]:
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    requirement = (
        payload.get("claim_coverage_requirement")
        if isinstance(payload.get("claim_coverage_requirement"), dict)
        else {}
    )
    policy = requirement.get("ci_low_policy") if isinstance(requirement.get("ci_low_policy"), dict) else {}
    observed = _as_float(policy.get("observed"))
    if observed is None:
        observed = _as_float(summary.get("ranking_pr_auc_ci_low"))
    threshold = _as_float(policy.get("threshold"))
    if threshold is None:
        threshold = _as_float(summary.get("threshold")) or MIN_RANKING_PR_AUC_CI_LOW
    ci_low_blocker = _as_bool(summary.get("ci_low_blocker")) or _text(policy.get("status")).lower() == "blocked"
    green = _source_available(payload) and observed is not None and observed >= threshold and not ci_low_blocker
    blockers: list[str] = []
    if not _source_available(payload):
        blockers.append("ci_low_packet_missing")
    if observed is None or observed < threshold or ci_low_blocker:
        blockers.append("ci_low_below_threshold")
    return {
        "status": "green" if green else "blocked",
        "metric": "ranking_pr_auc_ci_low",
        "observed": observed,
        "threshold": threshold,
        "ci_low_blocker": bool(ci_low_blocker),
        "blockers": blockers,
    }


def _failed_metric_threshold(payload: dict[str, Any], metric: str, default: float) -> float:
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    rows = summary.get("failed_metrics") if isinstance(summary.get("failed_metrics"), list) else []
    for row in rows:
        if not isinstance(row, dict):
            continue
        if _text(row.get("metric")) == metric:
            threshold = _as_float(row.get("threshold"))
            if threshold is not None:
                return threshold
    return default


def _top20_gate(ci_payload: dict[str, Any], triage_payload: dict[str, Any]) -> dict[str, Any]:
    summary = ci_payload.get("summary") if isinstance(ci_payload.get("summary"), dict) else {}
    requirement = (
        ci_payload.get("claim_coverage_requirement")
        if isinstance(ci_payload.get("claim_coverage_requirement"), dict)
        else {}
    )
    rank = ci_payload.get("rank_diagnostics") if isinstance(ci_payload.get("rank_diagnostics"), dict) else {}
    observed_hit_rate = _as_float(summary.get("ranking_topk_hit_rate"))
    observed_ceiling = _as_float(requirement.get("top20_ceiling_observed"))
    if observed_ceiling is None:
        observed_ceiling = _as_float(rank.get("top20_hit_rate_max_possible"))
    hit_rate_threshold = _failed_metric_threshold(ci_payload, "topk_hit_rate@20", MIN_TOP20_HIT_RATE)
    ceiling_threshold = _as_float(requirement.get("top20_ceiling_threshold")) or MIN_TOP20_CEILING

    top20_guardrails = []
    rows = triage_payload.get("guardrail_rows") if isinstance(triage_payload.get("guardrail_rows"), list) else []
    for row in rows:
        if not isinstance(row, dict):
            continue
        row_text = " ".join([_text(row.get("guardrail_id")), _text(row.get("metric"))]).lower()
        if "top20" in row_text:
            top20_guardrails.append(row)
    top20_guardrails_green = bool(top20_guardrails) and all(row.get("pass") is True for row in top20_guardrails)
    green = (
        _source_available(ci_payload)
        and observed_hit_rate is not None
        and observed_hit_rate >= hit_rate_threshold
        and observed_ceiling is not None
        and observed_ceiling >= ceiling_threshold
    )
    blockers: list[str] = []
    if not _source_available(ci_payload):
        blockers.append("top20_inputs_missing")
    if (
        observed_hit_rate is None
        or observed_hit_rate < hit_rate_threshold
        or observed_ceiling is None
        or observed_ceiling < ceiling_threshold
    ):
        blockers.append("top20_stability_not_green")
    return {
        "status": "green" if green else "blocked",
        "top20_hit_rate_observed": observed_hit_rate,
        "top20_hit_rate_threshold": hit_rate_threshold,
        "top20_ceiling_observed": observed_ceiling,
        "top20_ceiling_threshold": ceiling_threshold,
        "top20_guardrail_rows": top20_guardrails,
        "top20_guardrails_green": top20_guardrails_green if top20_guardrails else None,
        "blockers": blockers,
    }


def _triage_gate(payload: dict[str, Any], leakage_payload: dict[str, Any] | None = None) -> dict[str, Any]:
    leakage_payload = leakage_payload or {}
    if _source_available(leakage_payload):
        failed_rules = leakage_payload.get("failed_rules") if isinstance(leakage_payload.get("failed_rules"), list) else []
        leakage_pass = leakage_payload.get("pass") is True and not failed_rules
        blockers: list[str] = []
        if not leakage_pass:
            blockers.append("leakage_triage_not_green")
        return {
            "status": "green" if leakage_pass else "blocked",
            "claim_safe": None,
            "claim_safe_status": None,
            "guardrail_fail_count": None,
            "all_guardrail_rows_pass": None,
            "leakage_audit_pass": leakage_payload.get("pass"),
            "failed_rules": failed_rules,
            "blockers": blockers,
        }

    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    rows = payload.get("guardrail_rows") if isinstance(payload.get("guardrail_rows"), list) else []
    all_rows_pass = bool(rows) and all(isinstance(row, dict) and row.get("pass") is True for row in rows)
    guardrail_fail_count = _as_int(summary.get("guardrail_fail_count"))
    claim_safe = summary.get("claim_safe") is True
    status_text = _text(summary.get("claim_safe_status")).lower()
    green = (
        _source_available(payload)
        and claim_safe
        and (guardrail_fail_count == 0 or guardrail_fail_count is None)
        and all_rows_pass
        and status_text not in {"regression_guardrail_failed", "blocked", "failed"}
    )
    blockers: list[str] = []
    if not _source_available(payload):
        blockers.append("triage_packet_missing")
    if not green:
        blockers.append("leakage_triage_not_green")
    return {
        "status": "green" if green else "blocked",
        "claim_safe": summary.get("claim_safe"),
        "claim_safe_status": summary.get("claim_safe_status"),
        "guardrail_fail_count": guardrail_fail_count,
        "all_guardrail_rows_pass": all_rows_pass,
        "blockers": blockers,
    }


def _collect_blockers(gates: dict[str, dict[str, Any]]) -> list[str]:
    blockers: list[str] = []
    for gate in gates.values():
        gate_blockers = gate.get("blockers")
        if not isinstance(gate_blockers, list):
            continue
        for blocker in gate_blockers:
            text = _text(blocker)
            if text and text not in blockers:
                blockers.append(text)
    return blockers


def build_packet(
    *,
    positive_json: str | Path | None = DEFAULT_POSITIVE_JSON,
    scoreability_json: str | Path | None = DEFAULT_SCOREABILITY_JSON,
    family_heldout_json: str | Path | None = DEFAULT_FAMILY_HELDOUT_JSON,
    ci_low_json: str | Path | None = DEFAULT_CI_LOW_JSON,
    triage_json: str | Path | None = DEFAULT_TRIAGE_JSON,
    leakage_audit_json: str | Path | None = DEFAULT_LEAKAGE_AUDIT_JSON,
    generated_at_local: str | None = None,
) -> dict[str, Any]:
    positive_path = _resolve(positive_json)
    scoreability_path = _resolve(scoreability_json)
    family_path = _resolve(family_heldout_json)
    ci_path = _resolve(ci_low_json)
    triage_path = _resolve(triage_json)
    leakage_path = _resolve(leakage_audit_json)
    positive_payload = _read_json(positive_path)
    scoreability_payload = _read_json(scoreability_path)
    family_payload = _read_json(family_path)
    ci_payload = _read_json(ci_path)
    triage_payload = _read_json(triage_path)
    leakage_payload = _read_json(leakage_path)

    gates = {
        "positive_coverage": _positive_gate(positive_payload),
        "frozen_candidate_scoreability": _scoreability_gate(scoreability_payload),
        "family_heldout": _family_gate(family_payload),
        "ci_low": _ci_gate(ci_payload),
        "top20_stability": _top20_gate(ci_payload, triage_payload),
        "leakage_triage": _triage_gate(triage_payload, leakage_payload),
    }
    launch_gates = {
        "positive_coverage": gates["positive_coverage"],
        "frozen_candidate_scoreability": gates["frozen_candidate_scoreability"],
    }
    launch_eligible = all(gate.get("status") == "green" for gate in launch_gates.values())
    eligible = all(gate.get("status") == "green" for gate in gates.values())
    launch_blockers = _collect_blockers(launch_gates)
    blockers = _collect_blockers(gates)
    positive_green = gates["positive_coverage"].get("status") == "green"
    scoreability_green = gates["frozen_candidate_scoreability"].get("status") == "green"
    ci_summary = ci_payload.get("summary") if isinstance(ci_payload.get("summary"), dict) else {}
    rerun_evidence_available = _source_available(ci_payload) and _as_int(ci_summary.get("ranking_positive_count")) is not None
    if eligible:
        next_required_step = (
            "Inputs are green for a guarded 100k rerun; keep promotion flags false pending rerun execution and review."
        )
    elif launch_eligible and rerun_evidence_available:
        next_required_step = (
            "Do not relaunch the same guarded packet as claim evidence; resolve rerun claim-review blockers: "
            + ", ".join(blockers)
            + "."
        )
    elif launch_eligible:
        next_required_step = "Launch a guarded 100k rerun candidate, then resolve claim-review blockers from the rerun evidence."
    elif positive_green and not scoreability_green:
        next_required_step = "Build frozen-candidate scorer/native/profile support before launching a full guarded GPCR 100k rerun."
    else:
        next_required_step = "Resolve positive coverage freeze/leakage blockers before launching a full guarded GPCR 100k rerun."

    return {
        "packet_type": "gpcr_guarded_100k_rerun_readiness",
        "generated_at_local": generated_at_local or dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "input_artifacts": {
            "positive_json": str(positive_path) if positive_path else None,
            "scoreability_json": str(scoreability_path) if scoreability_path else None,
            "family_heldout_json": str(family_path) if family_path else None,
            "ci_low_json": str(ci_path) if ci_path else None,
            "triage_json": str(triage_path) if triage_path else None,
            "leakage_audit_json": str(leakage_path) if leakage_path else None,
        },
        "summary": {
            "eligible": bool(eligible),
            "status": "eligible" if eligible else "blocked",
            "launch_eligible": bool(launch_eligible),
            "launch_status": "eligible" if launch_eligible else "blocked",
            "launch_blocker_count": len(launch_blockers),
            "launch_blockers": launch_blockers,
            "claim_review_eligible": bool(eligible),
            "blocker_count": len(blockers),
            "blockers": blockers,
            "claim_promotion_allowed": False,
            "router_claim_allowed": False,
            "platform_claim_allowed": False,
            "next_required_step": next_required_step,
        },
        "gates": gates,
        "claim_boundary": {
            "readiness_packet_is_not_claim_authorization": True,
            "claim_promotion_allowed": False,
            "router_claim_allowed": False,
            "platform_claim_allowed": False,
            "threshold_relaxation_allowed": False,
            "fake_pass_allowed": False,
            "conservative_missing_input_policy": "block",
        },
    }


def _fmt(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    gates = payload["gates"]
    lines = [
        "# GPCR Guarded 100k Rerun Readiness",
        "",
        f"- eligible: `{_fmt(summary.get('eligible'))}`",
        f"- status: `{_fmt(summary.get('status'))}`",
        f"- blocker_count: `{_fmt(summary.get('blocker_count'))}`",
        f"- blockers: `{', '.join(summary.get('blockers', []))}`",
        f"- claim_promotion_allowed: `{_fmt(summary.get('claim_promotion_allowed'))}`",
        f"- router_claim_allowed: `{_fmt(summary.get('router_claim_allowed'))}`",
        f"- platform_claim_allowed: `{_fmt(summary.get('platform_claim_allowed'))}`",
        "",
        "## Gate Table",
        "",
        "| gate | status | blockers |",
        "| --- | --- | --- |",
    ]
    for name, gate in gates.items():
        blockers = gate.get("blockers") if isinstance(gate.get("blockers"), list) else []
        lines.append(f"| {name} | {_fmt(gate.get('status'))} | {', '.join(blockers)} |")
    lines.extend(
        [
            "",
            "## Next Step",
            "",
            f"- {summary.get('next_required_step')}",
            "",
        ]
    )
    return "\n".join(lines)


def write_outputs(
    *,
    positive_json: str | Path | None,
    scoreability_json: str | Path | None,
    family_heldout_json: str | Path | None,
    ci_low_json: str | Path | None,
    triage_json: str | Path | None,
    leakage_audit_json: str | Path | None,
    out_json: str | Path,
    out_md: str | Path,
) -> dict[str, Any]:
    payload = build_packet(
        positive_json=positive_json,
        scoreability_json=scoreability_json,
        family_heldout_json=family_heldout_json,
        ci_low_json=ci_low_json,
        triage_json=triage_json,
        leakage_audit_json=leakage_audit_json,
    )
    out_json_path = _resolve(out_json)
    out_md_path = _resolve(out_md)
    assert out_json_path is not None
    assert out_md_path is not None
    _write_json(out_json_path, payload)
    out_md_path.parent.mkdir(parents=True, exist_ok=True)
    out_md_path.write_text(render_markdown(payload), encoding="utf-8")
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build GPCR guarded 100k rerun readiness packet.")
    parser.add_argument("--positive-json", default=DEFAULT_POSITIVE_JSON)
    parser.add_argument("--scoreability-json", default=DEFAULT_SCOREABILITY_JSON)
    parser.add_argument("--family-heldout-json", default=DEFAULT_FAMILY_HELDOUT_JSON)
    parser.add_argument("--ci-low-json", default=DEFAULT_CI_LOW_JSON)
    parser.add_argument("--triage-json", default=DEFAULT_TRIAGE_JSON)
    parser.add_argument("--leakage-audit-json", default=DEFAULT_LEAKAGE_AUDIT_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    write_outputs(
        positive_json=args.positive_json,
        scoreability_json=args.scoreability_json,
        family_heldout_json=args.family_heldout_json,
        ci_low_json=args.ci_low_json,
        triage_json=args.triage_json,
        leakage_audit_json=args.leakage_audit_json,
        out_json=args.out_json,
        out_md=args.out_md,
    )


if __name__ == "__main__":
    main()

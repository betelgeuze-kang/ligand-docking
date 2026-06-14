#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
from typing import Any

from tools.gpcr_replay.build_gpcr_active_scorer_promotion_decision_packet import (
    scorecard_metric_ready_under_claim_lock,
)

ROOT = Path(__file__).resolve().parents[2]

DEFAULT_ACCURACY_SCORECARD_JSON = "runs/accuracy_parity_scorecard_current.json"
DEFAULT_FAMILY_HELDOUT_GUARDRAIL_JSON = "runs/gpcr_family_heldout_scorecard_guardrail_current.json"
DEFAULT_GUARDED_100K_READINESS_JSON = "runs/gpcr_guarded_100k_rerun_readiness_current.json"
DEFAULT_ACTIVE_SCORER_DECISION_JSON = "runs/gpcr_active_scorer_promotion_decision_packet_current.json"
DEFAULT_BROAD_CLAIM_REVIEW_RECEIPT_JSON = "runs/gpcr_broad_claim_review_receipt_current.json"
DEFAULT_OUT_JSON = "runs/gpcr_broad_claim_scope_readiness_current.json"
DEFAULT_OUT_MD = "runs/gpcr_broad_claim_scope_readiness_current.md"

CLAIM_BOUNDARY = (
    "GPCR broad claim-scope readiness packet only; it separates target-held-out/guarded-100k "
    "input readiness from formal broad-claim review and scorer/router promotion approval. It does not "
    "promote claims, mutate router defaults, enable scorer application, run docking, upload, email, commit, "
    "push, or mutate external state."
)


def _resolve(path_like: str | Path | None) -> Path | None:
    if path_like is None or str(path_like).strip() == "":
        return None
    path = Path(path_like)
    return path.resolve() if path.is_absolute() else (ROOT / path).resolve()


def _read_json(path_like: str | Path | None) -> dict[str, Any]:
    path = _resolve(path_like)
    if path is None or not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    assert path is not None
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _summary(packet: dict[str, Any]) -> dict[str, Any]:
    summary = packet.get("summary")
    return summary if isinstance(summary, dict) else packet


def _text(value: Any) -> str:
    return str(value or "").strip()


def _bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return _text(value).lower() in {"1", "true", "yes", "y", "pass", "passed", "green", "eligible"}


def _int(value: Any) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def build_packet(
    *,
    accuracy_scorecard_json: str | Path = DEFAULT_ACCURACY_SCORECARD_JSON,
    family_heldout_guardrail_json: str | Path = DEFAULT_FAMILY_HELDOUT_GUARDRAIL_JSON,
    guarded_100k_readiness_json: str | Path = DEFAULT_GUARDED_100K_READINESS_JSON,
    active_scorer_decision_json: str | Path = DEFAULT_ACTIVE_SCORER_DECISION_JSON,
    broad_claim_review_receipt_json: str | Path = DEFAULT_BROAD_CLAIM_REVIEW_RECEIPT_JSON,
    generated_at_local: str | None = None,
) -> dict[str, Any]:
    accuracy_packet = _read_json(accuracy_scorecard_json)
    scorecard_readiness = scorecard_metric_ready_under_claim_lock(accuracy_packet)
    heldout = _summary(_read_json(family_heldout_guardrail_json))
    guarded = _summary(_read_json(guarded_100k_readiness_json))
    active = _summary(_read_json(active_scorer_decision_json))
    broad_review_receipt = _summary(_read_json(broad_claim_review_receipt_json))

    heldout_ready = (
        _text(heldout.get("status")).lower() == "green"
        and _int(heldout.get("blocker_count")) == 0
        and heldout.get("claim_promotion_allowed") is False
        and heldout.get("router_claim_allowed") is False
        and heldout.get("platform_claim_allowed") is False
    )
    guarded_inputs_ready = (
        _text(guarded.get("status")).lower() in {"eligible", "green"}
        and guarded.get("claim_review_eligible") is True
        and _int(guarded.get("blocker_count")) == 0
        and guarded.get("claim_promotion_allowed") is False
        and guarded.get("router_claim_allowed") is False
        and guarded.get("platform_claim_allowed") is False
    )
    target_heldout_input_ready = heldout_ready and guarded_inputs_ready
    active_scorer_recorded = bool(active)
    active_scorer_gate_ready = bool(
        active.get("active_scorer_apply_allowed") is True
        and active.get("scorer_apply_allowed") is True
    )
    broad_claim_review_receipt_ready = broad_review_receipt.get("broad_claim_review_receipt_ready") is True
    target_heldout_broad_scope_review_approved = bool(
        target_heldout_input_ready
        and broad_review_receipt.get("target_heldout_broad_scope_review_approved") is True
    )
    scorer_router_promotion_gate_receipt_approved = (
        broad_review_receipt.get("scorer_router_promotion_gate_approved") is True
    )
    scorer_router_gate_ready = bool(
        active_scorer_gate_ready and scorer_router_promotion_gate_receipt_approved
    )

    blockers: list[str] = []
    if not scorecard_readiness["metric_ready"]:
        blockers.append("accuracy_metric_not_ready")
    if not heldout_ready:
        blockers.append("target_heldout_family_guardrail_not_green")
    if not guarded_inputs_ready:
        blockers.append("guarded_100k_claim_review_inputs_not_ready")
    if target_heldout_input_ready and not target_heldout_broad_scope_review_approved:
        blockers.append("formal_broad_claim_review_not_approved")
    if not scorer_router_gate_ready:
        blockers.append("scorer_router_promotion_gate_not_approved")

    claim_promotion_allowed = False
    router_claim_allowed = False
    platform_claim_allowed = False
    status = "blocked_gpcr_broad_claim_scope_readiness"
    if not blockers and scorer_router_gate_ready:
        status = "gpcr_broad_claim_scope_ready"
        claim_promotion_allowed = True
        router_claim_allowed = True
        platform_claim_allowed = True

    summary = {
        "packet_type": "gpcr_broad_claim_scope_readiness",
        "generated_at_local": generated_at_local or dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "status": status,
        "target_heldout_family_guardrail_ready": heldout_ready,
        "guarded_100k_claim_review_inputs_ready": guarded_inputs_ready,
        "target_heldout_broad_scope_review_input_ready": target_heldout_input_ready,
        "target_heldout_broad_scope_review_approved": target_heldout_broad_scope_review_approved,
        "formal_broad_claim_review_blocked": target_heldout_input_ready
        and not target_heldout_broad_scope_review_approved,
        "broad_claim_review_receipt_status": _text(broad_review_receipt.get("status")),
        "broad_claim_review_receipt_ready": broad_claim_review_receipt_ready,
        "broad_claim_review_receipt_row_count": _int(broad_review_receipt.get("receipt_row_count")),
        "broad_claim_review_receipt_pass_row_count": _int(broad_review_receipt.get("pass_row_count")),
        "broad_claim_review_receipt_blocked_row_count": _int(broad_review_receipt.get("blocked_row_count")),
        "broad_claim_review_receipt_operator_review_surface_ready_count": _int(
            broad_review_receipt.get("operator_review_surface_ready_count")
        ),
        "broad_claim_review_receipt_operator_review_surface_blocked_count": _int(
            broad_review_receipt.get("operator_review_surface_blocked_count")
        ),
        "broad_claim_review_receipt_evidence_artifact_present_count": _int(
            broad_review_receipt.get("evidence_artifact_present_count")
        ),
        "broad_claim_review_receipt_evidence_status_contract_present_count": _int(
            broad_review_receipt.get("evidence_status_contract_present_count")
        ),
        "broad_claim_review_receipt_expected_true_fields_present_count": _int(
            broad_review_receipt.get("expected_true_fields_present_count")
        ),
        "broad_claim_review_receipt_external_engine_calls_zero_count": _int(
            broad_review_receipt.get("external_engine_calls_zero_count")
        ),
        "broad_claim_review_receipt_manual_field_pending_count": _int(
            broad_review_receipt.get("receipt_manual_field_pending_count")
        ),
        "broad_claim_review_receipt_first_blocked_review_id": _text(
            broad_review_receipt.get("first_blocked_review_id")
        ),
        "broad_claim_review_receipt_approval_token_required": _text(
            broad_review_receipt.get("approval_token_required")
        ),
        "active_scorer_decision_recorded": active_scorer_recorded,
        "active_scorer_gate_ready": active_scorer_gate_ready,
        "scorer_router_promotion_gate_receipt_approved": scorer_router_promotion_gate_receipt_approved,
        "scorer_router_promotion_gate_ready": scorer_router_gate_ready,
        "scorer_router_promotion_gate_blocked": not scorer_router_gate_ready,
        "accuracy_parity_metric_ready": bool(scorecard_readiness["metric_ready"]),
        "accuracy_parity_metric_blockers": scorecard_readiness["metric_blockers"],
        "accuracy_parity_claim_scope_lock_only": bool(scorecard_readiness["claim_scope_lock_only"]),
        "accuracy_parity_ligand_ranking_status": scorecard_readiness["ligand_ranking_status"],
        "accuracy_parity_ligand_ranking_blockers": scorecard_readiness["ligand_ranking_blockers"],
        "heldout_guardrail_status": _text(heldout.get("status")),
        "guarded_100k_readiness_status": _text(guarded.get("status")),
        "active_scorer_decision_status": _text(active.get("status")),
        "active_scorer_source_blockers": active.get("blockers") if isinstance(active.get("blockers"), list) else [],
        "promotion_scope": _text(active.get("promotion_scope")) or "guarded_operational_gpcr_ranking_only",
        "claim_promotion_allowed": claim_promotion_allowed,
        "router_claim_allowed": router_claim_allowed,
        "platform_claim_allowed": platform_claim_allowed,
        "blocker_count": len(blockers),
        "blockers": sorted(blockers),
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "Target-held-out and guarded-100k inputs are green; fill the broad-claim review receipt and "
            "scorer/router promotion evidence before any broad GPCR or Schrodinger-class claim."
            if target_heldout_input_ready
            else "Repair target-held-out family guardrail and guarded-100k claim-review inputs before broad claim review."
        ),
    }
    return {"summary": summary}


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    blockers = summary.get("blockers") if isinstance(summary.get("blockers"), list) else []
    return "\n".join(
        [
            "# GPCR Broad Claim-Scope Readiness",
            "",
            f"- status: `{summary['status']}`",
            f"- target_heldout_broad_scope_review_input_ready: `{summary['target_heldout_broad_scope_review_input_ready']}`",
            f"- target_heldout_broad_scope_review_approved: `{summary['target_heldout_broad_scope_review_approved']}`",
            f"- scorer_router_promotion_gate_ready: `{summary['scorer_router_promotion_gate_ready']}`",
            f"- accuracy_parity_metric_ready: `{summary['accuracy_parity_metric_ready']}`",
            f"- accuracy_parity_claim_scope_lock_only: `{summary['accuracy_parity_claim_scope_lock_only']}`",
            f"- claim_promotion_allowed: `{summary['claim_promotion_allowed']}`",
            f"- router_claim_allowed: `{summary['router_claim_allowed']}`",
            f"- platform_claim_allowed: `{summary['platform_claim_allowed']}`",
            f"- blockers: `{', '.join(blockers) or 'none'}`",
            "",
            "## Next Step",
            "",
            f"- {summary['next_required_step']}",
            "",
        ]
    )


def write_outputs(
    *,
    accuracy_scorecard_json: str | Path,
    family_heldout_guardrail_json: str | Path,
    guarded_100k_readiness_json: str | Path,
    active_scorer_decision_json: str | Path,
    broad_claim_review_receipt_json: str | Path,
    out_json: str | Path,
    out_md: str | Path,
) -> dict[str, Any]:
    payload = build_packet(
        accuracy_scorecard_json=accuracy_scorecard_json,
        family_heldout_guardrail_json=family_heldout_guardrail_json,
        guarded_100k_readiness_json=guarded_100k_readiness_json,
        active_scorer_decision_json=active_scorer_decision_json,
        broad_claim_review_receipt_json=broad_claim_review_receipt_json,
    )
    _write_json(out_json, payload)
    out_md_path = _resolve(out_md)
    assert out_md_path is not None
    out_md_path.parent.mkdir(parents=True, exist_ok=True)
    out_md_path.write_text(render_markdown(payload), encoding="utf-8")
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build GPCR broad claim-scope readiness packet.")
    parser.add_argument("--accuracy-scorecard-json", default=DEFAULT_ACCURACY_SCORECARD_JSON)
    parser.add_argument("--family-heldout-guardrail-json", default=DEFAULT_FAMILY_HELDOUT_GUARDRAIL_JSON)
    parser.add_argument("--guarded-100k-readiness-json", default=DEFAULT_GUARDED_100K_READINESS_JSON)
    parser.add_argument("--active-scorer-decision-json", default=DEFAULT_ACTIVE_SCORER_DECISION_JSON)
    parser.add_argument("--broad-claim-review-receipt-json", default=DEFAULT_BROAD_CLAIM_REVIEW_RECEIPT_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = write_outputs(
        accuracy_scorecard_json=args.accuracy_scorecard_json,
        family_heldout_guardrail_json=args.family_heldout_guardrail_json,
        guarded_100k_readiness_json=args.guarded_100k_readiness_json,
        active_scorer_decision_json=args.active_scorer_decision_json,
        broad_claim_review_receipt_json=args.broad_claim_review_receipt_json,
        out_json=args.out_json,
        out_md=args.out_md,
    )
    print(json.dumps(payload["summary"], indent=2, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()

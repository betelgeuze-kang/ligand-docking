#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_BREADTH_JSON = "runs/gpcr_residual_proof_breadth_gate_current.json"
DEFAULT_CI_LOW_JSON = "runs/gpcr_ci_low_recovery_packet_current.json"
DEFAULT_OPRM1_JSON = "runs/gpcr_oprm1_life_science_evidence_packet_current.json"
DEFAULT_OUT_JSON = "runs/gpcr_conditional_prior_promotion_gate_current.json"
DEFAULT_OUT_CSV = "runs/gpcr_conditional_prior_promotion_gate_current.csv"
DEFAULT_OUT_MD = "runs/gpcr_conditional_prior_promotion_gate_current.md"

CI_LOW_THRESHOLD = 0.45
CLAIM_BOUNDARY = (
    "GPCR conditional prior promotion gate only; it audits breadth accounting, CI-low recovery, OPRM1 collapse "
    "evidence, and conditional prior scaffold wiring while keeping claim_promotion_allowed=false. It does not run "
    "docking, relax thresholds, promote assist/production mode, or mutate external state."
)


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _read_json_if_present(path_like: str | Path) -> dict[str, Any]:
    path = _resolve(path_like)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _read_text(path_like: str | Path) -> str:
    path = _resolve(path_like)
    return path.read_text(encoding="utf-8") if path.exists() else ""


def _summary(packet: dict[str, Any]) -> dict[str, Any]:
    summary = packet.get("summary")
    return summary if isinstance(summary, dict) else {}


def _text(value: Any) -> str:
    return str(value or "").strip()


def _float(value: Any) -> float | None:
    try:
        if value in {None, ""}:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _bool(value: Any) -> bool:
    return value is True


def _int(value: Any) -> int:
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0


def build_gpcr_conditional_prior_promotion_gate(
    *,
    breadth_packet: dict[str, Any] | None = None,
    ci_low_packet: dict[str, Any] | None = None,
    oprm1_packet: dict[str, Any] | None = None,
) -> dict[str, Any]:
    breadth = _summary(breadth_packet or _read_json_if_present(DEFAULT_BREADTH_JSON))
    ci_low = _summary(ci_low_packet or _read_json_if_present(DEFAULT_CI_LOW_JSON))
    oprm1 = _summary(oprm1_packet or _read_json_if_present(DEFAULT_OPRM1_JSON))
    backmapping = _read_text("tools/run_ligand_backmapping_scoring.py")
    prototype_spec = _read_text("tools/accounting/build_gpcr_residual_prototype_spec.py")

    breadth_gate_ready = _bool(breadth.get("gpcr_residual_proof_breadth_gate_ready")) or _text(breadth.get("status")) == "gpcr_residual_proof_breadth_gate_ready"
    ci_low_value = _float(ci_low.get("ranking_pr_auc_ci_low"))
    ci_low_blocker = ci_low_value is None or ci_low_value < CI_LOW_THRESHOLD
    oprm1_collapse = _bool(oprm1.get("pose_collapse_blocker")) or _int(oprm1.get("blocked_positive_count")) > 0
    conditional_prior_scaffold = (
        "gpcr_acidic_anchor_overcontact_prior_gate" in backmapping
        and "gpcr_core_acidic_anchor_overcontact_prior_gate_v4" in prototype_spec
        and ("conditional_prior" in prototype_spec.lower() or "acidic_anchor_overcontact" in prototype_spec)
    )
    promotion_boundary_ready = breadth_gate_ready and conditional_prior_scaffold
    claim_promotion_allowed = False
    blockers: list[str] = []
    if ci_low_blocker:
        blockers.append("ranking_pr_auc_ci_low_below_threshold")
    if oprm1_collapse:
        blockers.append("oprm1_pose_collapse_unresolved")
    if not breadth_gate_ready:
        blockers.append("gpcr_residual_proof_breadth_gate_not_ready")
    if not conditional_prior_scaffold:
        blockers.append("conditional_prior_scaffold_missing")

    row = {
        "lane_id": "gpcr_broad_family",
        "accounting_status": "green" if breadth_gate_ready else "blocked",
        "claim_promotion_status": "blocked" if blockers else "boundary_ready",
        "claim_promotion_allowed": claim_promotion_allowed,
        "comparison_only": True,
        "ranking_pr_auc_ci_low": ci_low_value,
        "ci_low_threshold": CI_LOW_THRESHOLD,
        "ci_low_blocker": ci_low_blocker,
        "oprm1_pose_collapse_blocker": oprm1_collapse,
        "breadth_gate_ready": breadth_gate_ready,
        "conditional_prior_scaffold_ready": conditional_prior_scaffold,
        "promotion_boundary_ready": promotion_boundary_ready,
        "gap_closed": promotion_boundary_ready,
        "blockers": ",".join(blockers),
        "next_required_step": (
            "Keep claim_promotion_allowed=false; continue OPRM1 pose/anchor evidence and conditional prior gating "
            "before any broad-family claim review."
            if blockers
            else "Promotion boundary scaffold is ready; claim promotion remains intentionally blocked."
        ),
    }
    summary = {
        "packet_type": "gpcr_conditional_prior_promotion_gate",
        "status": "gpcr_conditional_prior_promotion_gate_ready" if promotion_boundary_ready else "blocked_gpcr_conditional_prior_promotion_gate",
        "promotion_boundary_ready": promotion_boundary_ready,
        "accounting_closed": breadth_gate_ready,
        "claim_promotion_allowed": claim_promotion_allowed,
        "comparison_only": True,
        "ci_low_blocker": ci_low_blocker,
        "oprm1_collapse_blocker": oprm1_collapse,
        "blocker_count": len(blockers),
        "blockers": blockers,
        "execution_enabled": False,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": row["next_required_step"],
    }
    return {"summary": summary, "rows": [row]}


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_markdown(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    s = payload["summary"]
    lines = [
        "# GPCR Conditional Prior Promotion Gate",
        "",
        f"- status: `{s['status']}`",
        f"- promotion_boundary_ready: `{s['promotion_boundary_ready']}`",
        f"- claim_promotion_allowed: `{s['claim_promotion_allowed']}`",
        f"- blockers: `{', '.join(s['blockers']) or 'none'}`",
        "",
        "## Claim Boundary",
        "",
        s["claim_boundary"],
        "",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Build GPCR conditional prior promotion gate.")
    parser.add_argument("--breadth-json", default=DEFAULT_BREADTH_JSON)
    parser.add_argument("--ci-low-json", default=DEFAULT_CI_LOW_JSON)
    parser.add_argument("--oprm1-json", default=DEFAULT_OPRM1_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    args = parser.parse_args(argv)
    payload = build_gpcr_conditional_prior_promotion_gate(
        breadth_packet=_read_json_if_present(args.breadth_json),
        ci_low_packet=_read_json_if_present(args.ci_low_json),
        oprm1_packet=_read_json_if_present(args.oprm1_json),
    )
    _write_json(args.out_json, payload)
    write_csv_rows(_resolve(args.out_csv), payload["rows"])
    _write_markdown(args.out_md, payload)


if __name__ == "__main__":
    main()

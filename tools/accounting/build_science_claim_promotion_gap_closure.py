#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.accounting.build_gpcr_conditional_prior_promotion_gate import build_gpcr_conditional_prior_promotion_gate
from tools.product.build_transporter_claim_promotion_boundary import build_transporter_claim_promotion_boundary
from tools.wetlab.build_wetlab_openmm_claim_promotion_boundary import build_wetlab_openmm_claim_promotion_boundary
from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT_JSON = "runs/science_claim_promotion_gap_closure_current.json"
DEFAULT_OUT_CSV = "runs/science_claim_promotion_gap_closure_current.csv"
DEFAULT_OUT_MD = "runs/science_claim_promotion_gap_closure_current.md"

CLAIM_BOUNDARY = (
    "Science claim promotion gap closure status only; it tracks accounting closure versus real claim promotion "
    "boundaries for GPCR, transporter, CA2/PXR, wetlab, and OpenMM lanes. It does not promote claims, run "
    "docking, or mutate external state."
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


def _summary(packet: dict[str, Any]) -> dict[str, Any]:
    summary = packet.get("summary")
    return summary if isinstance(summary, dict) else {}


def _int(value: Any) -> int:
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0


def _row(
    gap_id: str,
    area: str,
    accounting_status: str,
    claim_status: str,
    status: str,
    evidence: str,
    observed: str,
    next_action: str,
    *,
    claim_promotion_allowed: bool = False,
) -> dict[str, Any]:
    return {
        "gap_id": gap_id,
        "area": area,
        "accounting_status": accounting_status,
        "claim_promotion_status": claim_status,
        "status": status,
        "evidence": evidence,
        "observed": observed,
        "next_action": next_action,
        "claim_promotion_allowed": claim_promotion_allowed,
        "release_blocker": status != "closed",
        "execution_enabled": False,
        "external_state_mutated": False,
    }


def build_science_claim_promotion_gap_closure(
    *,
    gpcr_gate_packet: dict[str, Any] | None = None,
    transporter_boundary_packet: dict[str, Any] | None = None,
    ca2_readiness_packet: dict[str, Any] | None = None,
    pxr_readiness_packet: dict[str, Any] | None = None,
    wetlab_openmm_boundary_packet: dict[str, Any] | None = None,
    gpcr_breadth_packet: dict[str, Any] | None = None,
) -> dict[str, Any]:
    gpcr_gate = gpcr_gate_packet or build_gpcr_conditional_prior_promotion_gate(
        breadth_packet=gpcr_breadth_packet or _read_json_if_present("runs/gpcr_residual_proof_breadth_gate_current.json")
    )
    transporter = transporter_boundary_packet or build_transporter_claim_promotion_boundary()
    wetlab_openmm = wetlab_openmm_boundary_packet or build_wetlab_openmm_claim_promotion_boundary()
    ca2 = _summary(ca2_readiness_packet or _read_json_if_present("runs/ca2_packet_replacement_readiness_current.json"))
    pxr = _summary(pxr_readiness_packet or _read_json_if_present("runs/pxr_packet_replacement_readiness_current.json"))

    gpcr_summary = _summary(gpcr_gate)
    transporter_summary = _summary(transporter)
    wetlab_openmm_summary = _summary(wetlab_openmm)

    gpcr_closed = bool(gpcr_summary.get("promotion_boundary_ready"))
    transporter_closed = bool(transporter_summary.get("promotion_boundary_ready"))
    ca2_closed = _int(ca2.get("blocked_row_count")) == 0 or _int(ca2.get("ready_row_count")) >= _int(ca2.get("workbook_row_count", 1))
    pxr_closed = _int(pxr.get("blocked_row_count")) == 0 or _int(pxr.get("ready_row_count")) >= 8
    ca2_pxr_closed = ca2_closed and pxr_closed
    wetlab_closed = bool(wetlab_openmm_summary.get("wetlab_lane_closed"))
    openmm_closed = bool(wetlab_openmm_summary.get("openmm_2bead_lane_closed"))
    gpcr_blockers = [str(item) for item in (gpcr_summary.get("blockers") or []) if str(item)]
    if gpcr_closed:
        gpcr_claim_status = "boundary_ready_comparison_only"
        gpcr_next_action = "Maintain claim_promotion_allowed=false until a separate broad-family claim review is approved."
    elif "ranking_pr_auc_ci_low_below_threshold" in gpcr_blockers and "oprm1_pose_collapse_unresolved" in gpcr_blockers:
        gpcr_claim_status = "blocked_ci_low_oprm1"
        gpcr_next_action = (
            "Maintain conditional prior gate and keep broad-family claim promotion blocked until CI-low and "
            "OPRM1 gates clear."
        )
    elif "oprm1_pose_collapse_unresolved" in gpcr_blockers:
        gpcr_claim_status = "blocked_oprm1_pose_collapse"
        gpcr_next_action = (
            "CI-low evidence is green in the tracked rank-rescue lane; keep broad-family claim promotion blocked "
            "until OPRM1 pose-collapse evidence clears."
        )
    else:
        gpcr_claim_status = "blocked_boundary_evidence"
        gpcr_next_action = "Close the listed GPCR boundary blockers before any broad-family claim review."

    rows = [
        _row(
            "SCI-GPCR",
            "GPCR broad family",
            "green" if gpcr_summary.get("accounting_closed") else "fixture_or_blocked",
            gpcr_claim_status,
            "closed" if gpcr_closed else "open",
            "runs/gpcr_conditional_prior_promotion_gate_current.json",
            (
                f"promotion_boundary_ready={gpcr_summary.get('promotion_boundary_ready')}; "
                f"claim_promotion_allowed=false; blockers={','.join(gpcr_blockers) or 'none'}"
            ),
            gpcr_next_action,
        ),
        _row(
            "SCI-TRANS",
            "Transporter AQP1/GLUT1",
            "green" if transporter_summary.get("accounting_closed") else "placeholder_or_blocked",
            "functional_surrogate_only",
            "closed" if transporter_closed else "open",
            "runs/transporter_claim_promotion_boundary_current.json",
            f"direct_binding_kcal_claim_allowed=false; promotion_boundary_ready={transporter_summary.get('promotion_boundary_ready')}",
            "Keep direct binding kcal out-of-claim; operator-fill AQP1 negative intake when primary evidence exists.",
        ),
        _row(
            "SCI-CA2-PXR",
            "CA2/PXR packet replacement",
            "green" if ca2_pxr_closed else "readiness_fixture_or_blocked",
            "review_only_until_workbook_applied",
            "closed" if ca2_pxr_closed else "open",
            "runs/ca2_packet_replacement_readiness_current.json; runs/pxr_packet_replacement_readiness_current.json",
            f"ca2_blocked_rows={ca2.get('blocked_row_count')}; pxr_blocked_rows={pxr.get('blocked_row_count')}",
            "Apply replacement_* triple-edit workbook rows with curated quantitative provenance.",
        ),
        _row(
            "SCI-WETLAB",
            "Wetlab prospective translation",
            "green" if wetlab_closed else "simulation_blocked",
            "simulation_packet_only",
            "closed" if wetlab_closed else "open",
            "runs/wetlab_openmm_claim_promotion_boundary_current.json",
            f"wetlab_assay_count=0; wetlab_proven_hit_out_of_claim=true",
            "Keep wetlab-proven hits out-of-claim while simulation packet quality stays green.",
        ),
        _row(
            "SCI-OPENMM",
            "OpenMM restricted vs full physics",
            "green" if openmm_closed else "parity_or_openmm_blocked",
            "restricted_2bead_only",
            "closed" if openmm_closed else "open",
            "runs/wetlab_openmm_claim_promotion_boundary_current.json; runs/accuracy_parity_scorecard_current.json",
            f"openmm_2bead_lane_closed={wetlab_openmm_summary.get('openmm_2bead_lane_closed')}; full_all_atom_implemented=false",
            "Maintain restricted 2-bead OpenMM lane; full all-atom/MM-GBSA/FEP+ remain unimplemented.",
        ),
    ]
    closed_rows = [row for row in rows if row["status"] == "closed"]
    open_rows = [row for row in rows if row["status"] != "closed"]
    first_open = open_rows[0] if open_rows else None
    summary = {
        "packet_type": "science_claim_promotion_gap_closure",
        "status": "science_claim_promotion_gap_closure_complete" if not open_rows else "blocked_science_claim_promotion_gap_closure",
        "all_gaps_closed": not open_rows,
        "gap_count": len(rows),
        "closed_gap_count": len(closed_rows),
        "open_gap_count": len(open_rows),
        "closed_gap_ids": [row["gap_id"] for row in closed_rows],
        "open_gap_ids": [row["gap_id"] for row in open_rows],
        "current_primary_open_gap_id": first_open["gap_id"] if first_open else "none",
        "current_next_action": first_open["next_action"] if first_open else "All science claim promotion boundary gaps are closed.",
        "claim_promotion_allowed": False,
        "execution_enabled": False,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
    }
    return {"summary": summary, "rows": rows}


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_markdown(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    s = payload["summary"]
    lines = [
        "# Science Claim Promotion Gap Closure",
        "",
        f"- status: `{s['status']}`",
        f"- all_gaps_closed: `{s['all_gaps_closed']}`",
        f"- closed_gap_count: `{s['closed_gap_count']}` / `{s['gap_count']}`",
        f"- claim_promotion_allowed: `{s['claim_promotion_allowed']}`",
        "",
        "## Gaps",
        "",
        "| gap_id | status | area | accounting | claim |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['gap_id']}` | `{row['status']}` | {row['area']} | `{row['accounting_status']}` | `{row['claim_promotion_status']}` |"
        )
    lines.extend(["", "## Claim Boundary", "", s["claim_boundary"], ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Build science claim promotion gap closure status.")
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    args = parser.parse_args(argv)
    payload = build_science_claim_promotion_gap_closure()
    _write_json(args.out_json, payload)
    write_csv_rows(_resolve(args.out_csv), payload["rows"])
    _write_markdown(args.out_md, payload)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

from tools.operator_surface_contracts import (
    GPCR_OPERATOR_STATUS_READY_ENDPOINT_ONLY,
    GPCR_SAFE_SCOPE_ENDPOINT_ONLY,
    IDP_BLOCKED_SCOPE_BROADER_FULL_PROMOTION,
    IDP_OPERATOR_STATUS_ONE_WIDER_SHADOW_SAFE_LANE_ONLY,
    IDP_OPERATOR_STATUS_SUBSET_SAFE_CONTROLLED_PRETEST_READY,
    IDP_SAFE_SCOPE_CONTROLLED_PRETEST,
    IDP_SAFE_SCOPE_LEGACY_SUBSET_ONLY,
    IDP_SAFE_SCOPE_ONE_WIDER_SHADOW_SAFE_LANE,
    PARTIAL_AUTHORITATIVE_OPERATOR_STATUS,
    PARTIAL_AUTHORITATIVE_SAFE_SCOPE,
    TRANSPORTER_SAFE_SCOPE_MANUAL_REVIEW_ONLY_DRAFT_PACKETS,
    TRANSPORTER_OPERATOR_STATUS_SEED_ROW_BLOCKER_CLOSURE_ONLY,
    TRANSPORTER_SAFE_SCOPE_SEED_ROW_BLOCKER_CLOSURE,
)
from tools.product.transporter_phase_helpers import infer_transporter_phase

ROOT = Path(__file__).resolve().parents[1]

DEFAULT_PRETEST_READINESS_JSON = "runs/pretest_execution_readiness_current.json"
DEFAULT_GPCR_HANDOFF_JSON = "runs/gpcr_handoff_bundle_current.json"
DEFAULT_IDP_SCOPE_JSON = "runs/idp_pretest_scope_note_current.json"
DEFAULT_IDP_BLOCKER_JSON = "runs/idp_broader_promotion_blocker_note_current.json"
DEFAULT_IDP_COMMERCIAL_PRETEST_JSON = "runs/idp_commercial_pretest_packet_current.json"
DEFAULT_IDP_COMMERCIAL_PRETEST_DECISION_JSON = "runs/idp_commercial_pretest_decision_current.json"
DEFAULT_IDP_BROADER_SHADOW_DECISION_JSON = "runs/idp_broader_shadow_decision_current.json"
DEFAULT_IDP_BROADER_PROMOTION_RESOLUTION_JSON = "runs/idp_broader_promotion_resolution_current.json"
DEFAULT_CA2_READINESS_JSON = "runs/ca2_packet_replacement_readiness_current.json"
DEFAULT_PXR_POLICY_JSON = "runs/pxr_pending_policy_note_current.json"
DEFAULT_TRANSPORTER_DASHBOARD_JSON = "runs/transporter_manual_review_dashboard_current.json"
DEFAULT_OUT_JSON = "runs/pretest_handoff_bundle_current.json"
DEFAULT_OUT_CSV = "runs/pretest_handoff_bundle_current.csv"
DEFAULT_OUT_MD = "runs/pretest_handoff_bundle_current.md"


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


def _maybe_load_json(path_like: str) -> dict[str, Any]:
    path = _resolve(path_like)
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def build_payload(
    pretest_readiness: dict[str, Any],
    gpcr_handoff: dict[str, Any],
    idp_scope: dict[str, Any],
    idp_blocker: dict[str, Any],
    idp_commercial_pretest: dict[str, Any],
    idp_broader_shadow_decision: dict[str, Any] | None,
    ca2_readiness: dict[str, Any],
    pxr_policy: dict[str, Any],
    transporter_dashboard: dict[str, Any],
    idp_commercial_pretest_decision: dict[str, Any] | None = None,
    idp_broader_promotion_resolution: dict[str, Any] | None = None,
) -> dict[str, Any]:
    readiness_summary = dict(pretest_readiness.get("summary", {}) or {})
    readiness_rows = {
        str(row.get("family", "")).strip(): dict(row)
        for row in pretest_readiness.get("rows", []) or []
        if str(row.get("family", "")).strip()
    }
    gpcr = dict(gpcr_handoff.get("summary", {}) or {})
    idp_s = dict(idp_scope.get("summary", {}) or {})
    idp_b = dict(idp_blocker.get("summary", {}) or {})
    idp_p = dict(idp_commercial_pretest.get("summary", {}) or {})
    idp_bd = dict((idp_broader_shadow_decision or {}).get("summary", {}) or {})
    idp_pr = dict((idp_broader_promotion_resolution or {}).get("summary", {}) or {})
    idp_pd = dict((idp_commercial_pretest_decision or {}).get("summary", {}) or {})
    ca2 = dict(ca2_readiness.get("summary", {}) or {})
    pxr = dict(pxr_policy.get("summary", {}) or {})
    transporter = dict(transporter_dashboard.get("summary", {}) or {})
    transporter_seed_rows = int(transporter.get("binder_seed_row_count", 0) or 0)
    transporter_pending = int(transporter.get("binder_pending_manual_verdict_count", 0) or 0)
    transporter_phase = infer_transporter_phase(transporter)
    transporter_next_step = (
        "Use AQP1 first for transporter seed-row promotion, keep GLUT1 staged behind it, and do not reopen donor policy until at least one transporter ligand packet is no longer placeholder-driven."
        if transporter_phase == "seed_row_blocker_closure"
        else str(transporter.get("next_required_step", ""))
    )
    transporter_note = (
        "Use AQP1 first-wave and GLUT1 second-wave packets only as seed-row promotion and blocker-closure surfaces; do not reopen donor policy yet."
        if transporter_phase == "seed_row_blocker_closure"
        else "Use AQP1 first-wave and GLUT1 second-wave packets only as manual-review surfaces; do not reopen donor policy yet."
    )

    rows = [
        {
            "family": "gpcr",
            "safe_scope_now": str(gpcr.get("safe_now", "")) or GPCR_SAFE_SCOPE_ENDPOINT_ONLY,
            "blocked_scope": str(gpcr.get("blocked_now", "")),
            "operator_status": GPCR_OPERATOR_STATUS_READY_ENDPOINT_ONLY,
            "next_safe_experiment": "locked-decoy variant only",
            "primary_handoff_note": "Use the apply-safe endpoint only; keep router promotion blocked.",
            "source_artifact": "runs/gpcr_handoff_bundle_current.md",
        },
        {
            "family": "idp",
            "safe_scope_now": IDP_SAFE_SCOPE_ONE_WIDER_SHADOW_SAFE_LANE if idp_pr else IDP_SAFE_SCOPE_CONTROLLED_PRETEST,
            "blocked_scope": str(idp_s.get("blocked_now", "")) or IDP_BLOCKED_SCOPE_BROADER_FULL_PROMOTION,
            "operator_status": IDP_OPERATOR_STATUS_ONE_WIDER_SHADOW_SAFE_LANE_ONLY if idp_pr else IDP_OPERATOR_STATUS_SUBSET_SAFE_CONTROLLED_PRETEST_READY,
            "next_safe_experiment": (
                str(idp_pr.get("next_required_step", "")).strip()
                or
                str(idp_bd.get("next_required_step", "")).strip()
                or
                str(idp_pd.get("next_required_step", "")).strip()
                or str(idp_p.get("next_required_step", "")).strip()
                or str(idp_s.get("next_safe_experiment", "")).strip()
            ),
            "primary_handoff_note": (
                str(idp_pr.get("blocker_reason", "")).strip()
                or
                str(idp_bd.get("blocker_reason", "")).strip()
                or str(idp_pd.get("blocker_reason", "")).strip()
                or str(idp_b.get("blocker_reason", ""))
            ),
            "source_artifact": (
                "runs/idp_broader_promotion_resolution_current.md"
                if idp_pr
                else
                "runs/idp_broader_shadow_decision_current.md"
                if idp_bd
                else "runs/idp_commercial_pretest_decision_current.md"
                if idp_pd
                else "runs/idp_commercial_pretest_packet_current.md"
            ),
        },
        {
            "family": "non_kinase_enzyme_ca2",
            "safe_scope_now": PARTIAL_AUTHORITATIVE_SAFE_SCOPE,
            "blocked_scope": "remaining_negative_like_rows",
            "operator_status": PARTIAL_AUTHORITATIVE_OPERATOR_STATUS,
            "next_safe_experiment": str(ca2.get("next_required_step", "")),
            "primary_handoff_note": "Only the ready binder tranche is authoritative-ready; the remaining rows still need review-only negative closure.",
            "source_artifact": "runs/ca2_packet_replacement_readiness_current.md",
        },
        {
            "family": "nuclear_receptor_pxr",
            "safe_scope_now": PARTIAL_AUTHORITATIVE_SAFE_SCOPE,
            "blocked_scope": "remaining_unresolved_pending_rows",
            "operator_status": PARTIAL_AUTHORITATIVE_OPERATOR_STATUS,
            "next_safe_experiment": str(pxr.get("next_required_step", "")),
            "primary_handoff_note": str(pxr.get("policy_line", "")),
            "source_artifact": "runs/pxr_pending_policy_note_current.md",
        },
        {
            "family": "transporter",
            "safe_scope_now": (
                TRANSPORTER_SAFE_SCOPE_SEED_ROW_BLOCKER_CLOSURE
                if transporter_phase == "seed_row_blocker_closure"
                else TRANSPORTER_SAFE_SCOPE_MANUAL_REVIEW_ONLY_DRAFT_PACKETS
            ),
            "blocked_scope": "authoritative_apply_and_donor_reopen",
            "operator_status": (
                TRANSPORTER_OPERATOR_STATUS_SEED_ROW_BLOCKER_CLOSURE_ONLY
                if transporter_phase == "seed_row_blocker_closure"
                else "blocked_manual_review_only"
            ),
            "next_safe_experiment": transporter_next_step,
            "primary_handoff_note": transporter_note,
            "source_artifact": "runs/transporter_operator_console_current.md",
        },
    ]

    summary = {
        "bundle_family_count": len(rows),
        "pretest_ready_count": readiness_summary.get("pretest_ready_count", 0),
        "partial_pretest_ready_count": readiness_summary.get("partial_pretest_ready_count", 0),
        "blocked_pretest_count": readiness_summary.get("blocked_pretest_count", 0),
        "core_commercial_lane_score": readiness_summary.get("core_commercial_lane_score", ""),
        "all_category_expansion_score": readiness_summary.get("all_category_expansion_score", ""),
        "gpcr_ready_endpoint_only": bool(gpcr.get("safe_now")),
        "idp_subset_only": idp_s.get("allowed_now", "") == IDP_SAFE_SCOPE_LEGACY_SUBSET_ONLY,
        "idp_commercial_pretest_ready": bool(idp_p),
        "idp_wider_shadow_safe_lane_admitted": bool(idp_pr.get("wider_shadow_safe_lane_admitted", False)),
        "idp_broader_shadow_passed": bool(idp_bd.get("broader_shadow_passed", False)),
        "ca2_ready_rows": ca2.get("ready_row_count", 0),
        "pxr_review_only_rows": len(pxr.get("review_only_rows", []) or []),
        "transporter_binder_pending_manual_verdict_count": transporter_pending,
        "transporter_seed_row_count": transporter_seed_rows,
        "next_required_step": (
            "Use this bundle as the cross-family operator handoff before any new tests. Stay inside each family's safe scope, treat IDP as admitted only for the frozen one-wider shadow-safe lane, keep broader_full_idp_promotion blocked, treat CA2/PXR as evidence-closure lanes, and keep transporter in seed-row blocker-closure mode."
            if idp_pr and transporter_phase == "seed_row_blocker_closure"
            else "Use this bundle as the cross-family operator handoff before any new tests. Stay inside each family's safe scope, treat IDP as admitted only for the frozen one-wider shadow-safe lane, keep broader_full_idp_promotion blocked, treat CA2/PXR as evidence-closure lanes, and keep transporter out of broad execution lanes."
            if idp_pr
            else
            "Use this bundle as the cross-family operator handoff before any new tests. Stay inside each family's safe scope and treat CA2/PXR as evidence-closure lanes while transporter stays in seed-row blocker-closure mode, not broad execution lanes."
            if transporter_phase == "seed_row_blocker_closure"
            else "Use this bundle as the cross-family operator handoff before any new tests. Stay inside each family's safe scope and treat CA2/PXR/transporter as evidence-closure lanes, not broad execution lanes."
        ),
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# Pretest Handoff Bundle",
        "",
        f"- bundle_family_count: `{s['bundle_family_count']}`",
        f"- pretest_ready_count: `{s['pretest_ready_count']}`",
        f"- partial_pretest_ready_count: `{s['partial_pretest_ready_count']}`",
        f"- blocked_pretest_count: `{s['blocked_pretest_count']}`",
        f"- core_commercial_lane_score: `{s['core_commercial_lane_score']}`",
        f"- all_category_expansion_score: `{s['all_category_expansion_score']}`",
        f"- gpcr_ready_endpoint_only: `{s['gpcr_ready_endpoint_only']}`",
        f"- idp_subset_only: `{s['idp_subset_only']}`",
        f"- idp_commercial_pretest_ready: `{s['idp_commercial_pretest_ready']}`",
        f"- ca2_ready_rows: `{s['ca2_ready_rows']}`",
        f"- pxr_review_only_rows: `{s['pxr_review_only_rows']}`",
        f"- transporter_binder_pending_manual_verdict_count: `{s['transporter_binder_pending_manual_verdict_count']}`",
        f"- transporter_seed_row_count: `{s['transporter_seed_row_count']}`",
        "",
        "## Next Step",
        "",
        f"- {s['next_required_step']}",
        "",
        "## Family Handoff",
        "",
        "| family | safe_scope_now | blocked_scope | operator_status | next_safe_experiment | primary_handoff_note | source_artifact |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['family']}` | `{row['safe_scope_now']}` | `{row['blocked_scope']}` | `{row['operator_status']}` | {row['next_safe_experiment']} | {row['primary_handoff_note']} | `{row['source_artifact']}` |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a cross-family pretest handoff bundle from current per-family artifacts.")
    parser.add_argument("--pretest-readiness-json", default=DEFAULT_PRETEST_READINESS_JSON)
    parser.add_argument("--gpcr-handoff-json", default=DEFAULT_GPCR_HANDOFF_JSON)
    parser.add_argument("--idp-scope-json", default=DEFAULT_IDP_SCOPE_JSON)
    parser.add_argument("--idp-blocker-json", default=DEFAULT_IDP_BLOCKER_JSON)
    parser.add_argument("--idp-commercial-pretest-json", default=DEFAULT_IDP_COMMERCIAL_PRETEST_JSON)
    parser.add_argument("--idp-broader-shadow-decision-json", default=DEFAULT_IDP_BROADER_SHADOW_DECISION_JSON)
    parser.add_argument("--idp-broader-promotion-resolution-json", default=DEFAULT_IDP_BROADER_PROMOTION_RESOLUTION_JSON)
    parser.add_argument("--idp-commercial-pretest-decision-json", default=DEFAULT_IDP_COMMERCIAL_PRETEST_DECISION_JSON)
    parser.add_argument("--ca2-readiness-json", default=DEFAULT_CA2_READINESS_JSON)
    parser.add_argument("--pxr-policy-json", default=DEFAULT_PXR_POLICY_JSON)
    parser.add_argument("--transporter-dashboard-json", default=DEFAULT_TRANSPORTER_DASHBOARD_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        _load_json(args.pretest_readiness_json),
        _load_json(args.gpcr_handoff_json),
        _load_json(args.idp_scope_json),
        _load_json(args.idp_blocker_json),
        _load_json(args.idp_commercial_pretest_json),
        _maybe_load_json(args.idp_broader_shadow_decision_json),
        _load_json(args.ca2_readiness_json),
        _load_json(args.pxr_policy_json),
        _load_json(args.transporter_dashboard_json),
        _maybe_load_json(args.idp_commercial_pretest_decision_json),
        _maybe_load_json(args.idp_broader_promotion_resolution_json),
    )
    out_json = _resolve(args.out_json)
    out_csv = _resolve(args.out_csv)
    out_md = _resolve(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    _write_csv(out_csv, payload["rows"])
    _write_markdown(out_md, payload)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

from tools.operator_surface_contracts import (
    GPCR_SAFE_SCOPE_ENDPOINT_ONLY,
    IDP_SAFE_SCOPE_CONTROLLED_PRETEST,
    IDP_SAFE_SCOPE_ONE_WIDER_SHADOW_SAFE_LANE,
    MEASURED_NOOP_SAFE_SCOPE,
    PARTIAL_AUTHORITATIVE_SAFE_SCOPE,
    TRANSPORTER_SAFE_SCOPE_SEED_ROW_BLOCKER_CLOSURE,
)
from tools.product.transporter_phase_helpers import infer_transporter_phase

ROOT = Path(__file__).resolve().parents[2]

DEFAULT_COMMERCIALIZATION_JSON = "runs/commercialization_readiness_current.json"
DEFAULT_CROSSFAMILY_JSON = "runs/cross_family_residual_shadow_layer_current.json"
DEFAULT_GPCR_ENDPOINT_JSON = "runs/gpcr_apply_safe_endpoint_current.json"
DEFAULT_IDP_SUBSET_DECISION_JSON = "runs/idp_feature_state_subset_decision_current.json"
DEFAULT_IDP_COMMERCIAL_PRETEST_JSON = "runs/idp_commercial_pretest_packet_current.json"
DEFAULT_IDP_COMMERCIAL_PRETEST_DECISION_JSON = "runs/idp_commercial_pretest_decision_current.json"
DEFAULT_IDP_BROADER_SHADOW_DECISION_JSON = "runs/idp_broader_shadow_decision_current.json"
DEFAULT_IDP_BROADER_PROMOTION_RESOLUTION_JSON = "runs/idp_broader_promotion_resolution_current.json"
DEFAULT_IDP_ONE_WIDER_REPEATABILITY_PACKET_JSON = "runs/idp_one_wider_shadow_repeatability_packet_current.json"
DEFAULT_IDP_ONE_WIDER_REPEATABILITY_RESULT_JSON = "runs/idp_one_wider_shadow_repeatability_result_current.json"
DEFAULT_CA2_READINESS_JSON = "runs/ca2_packet_replacement_readiness_current.json"
DEFAULT_PXR_READINESS_JSON = "runs/pxr_packet_fill_readiness_current.json"
DEFAULT_TRANSPORTER_DASHBOARD_JSON = "runs/transporter_manual_review_dashboard_current.json"
DEFAULT_TRANSPORTER_SEED_ROW_BOARD_JSON = "runs/transporter_seed_row_promotion_board_current.json"
DEFAULT_OUT_JSON = "runs/pretest_execution_readiness_current.json"
DEFAULT_OUT_CSV = "runs/pretest_execution_readiness_current.csv"
DEFAULT_OUT_MD = "runs/pretest_execution_readiness_current.md"


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


def _score_by_family(commercialization_payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(row.get("family", "")).strip(): dict(row)
        for row in commercialization_payload.get("rows", []) or []
        if str(row.get("family", "")).strip()
    }


def build_payload(
    commercialization_payload: dict[str, Any],
    crossfamily_payload: dict[str, Any],
    gpcr_endpoint_payload: dict[str, Any],
    idp_subset_payload: dict[str, Any],
    idp_commercial_pretest_payload: dict[str, Any],
    ca2_readiness_payload: dict[str, Any],
    pxr_readiness_payload: dict[str, Any],
    transporter_dashboard_payload: dict[str, Any],
    transporter_seed_row_board_payload: dict[str, Any],
    idp_commercial_pretest_decision_payload: dict[str, Any] | None = None,
    idp_broader_shadow_decision_payload: dict[str, Any] | None = None,
    idp_broader_promotion_resolution_payload: dict[str, Any] | None = None,
    idp_one_wider_repeatability_packet_payload: dict[str, Any] | None = None,
    idp_one_wider_repeatability_result_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    family_scores = _score_by_family(commercialization_payload)
    crossfamily_rows = {
        str(row.get("family", "")).strip(): dict(row)
        for row in crossfamily_payload.get("rows", []) or []
        if str(row.get("family", "")).strip()
    }

    gpcr_summary = dict(gpcr_endpoint_payload.get("summary", {}) or {})
    idp_summary = dict(idp_subset_payload.get("summary", {}) or {})
    idp_pretest_summary = dict(idp_commercial_pretest_payload.get("summary", {}) or {})
    idp_pretest_decision_summary = dict((idp_commercial_pretest_decision_payload or {}).get("summary", {}) or {})
    idp_broader_decision_summary = dict((idp_broader_shadow_decision_payload or {}).get("summary", {}) or {})
    idp_broader_promotion_resolution_summary = dict((idp_broader_promotion_resolution_payload or {}).get("summary", {}) or {})
    idp_one_wider_repeatability_packet_summary = dict((idp_one_wider_repeatability_packet_payload or {}).get("summary", {}) or {})
    idp_one_wider_repeatability_result_summary = dict((idp_one_wider_repeatability_result_payload or {}).get("summary", {}) or {})
    idp_effective_decision = idp_broader_promotion_resolution_summary or idp_broader_decision_summary or idp_pretest_decision_summary
    idp_repeatability_summary = idp_one_wider_repeatability_result_summary or idp_one_wider_repeatability_packet_summary
    idp_additional_anchor_backed_target_count = int(idp_pretest_decision_summary.get("additional_anchor_backed_target_count", 0) or 0)
    idp_same_scope_reproducibility_confirmed = bool(idp_pretest_decision_summary.get("same_scope_reproducibility_confirmed", False))
    idp_page4_candidate_ready_now = bool(idp_pretest_decision_summary.get("page4_candidate_ready_now", False))
    ca2_summary = dict(ca2_readiness_payload.get("summary", {}) or {})
    pxr_summary = dict(pxr_readiness_payload.get("summary", {}) or {})
    transporter_summary = dict(transporter_dashboard_payload.get("summary", {}) or {})
    transporter_seed_summary = dict(transporter_seed_row_board_payload.get("summary", {}) or {})
    transporter_seed_rows = int(transporter_summary.get("binder_seed_row_count", 0) or 0)
    transporter_placeholder_rows = int(transporter_summary.get("placeholder_row_count_total", 0) or 0)
    transporter_phase = infer_transporter_phase(transporter_summary)
    transporter_next_step = (
        "Keep transporter family in draft/manual-review mode. Start with AQP1 seed-row promotion surfaces, keep GLUT1 staged behind it, and do not revisit family-level donor policy until at least one transporter ligand packet is no longer placeholder-driven."
        if transporter_phase == "seed_row_blocker_closure"
        else str(transporter_summary.get("next_required_step", ""))
    )

    rows = [
        {
            "family": "gpcr",
            "commercialization_score": family_scores.get("gpcr", {}).get("score", ""),
            "current_state": crossfamily_rows.get("gpcr", {}).get("current_state", ""),
            "runtime_scope_now": GPCR_SAFE_SCOPE_ENDPOINT_ONLY,
            "pretest_ready": "yes",
            "claim_safe_test_ready": "yes",
            "router_ready": "no",
            "primary_blocker": "100k_router_still_blocked",
            "next_required_step": gpcr_summary.get("next_required_step", ""),
        },
        {
            "family": "ion_channel",
            "commercialization_score": family_scores.get("ion_channel", {}).get("score", ""),
            "current_state": crossfamily_rows.get("ion_channel", {}).get("current_state", ""),
            "runtime_scope_now": MEASURED_NOOP_SAFE_SCOPE,
            "pretest_ready": "yes",
            "claim_safe_test_ready": "yes",
            "router_ready": "n/a",
            "primary_blocker": "",
            "next_required_step": crossfamily_rows.get("ion_channel", {}).get("next_required_step", ""),
        },
        {
            "family": "kinase",
            "commercialization_score": family_scores.get("kinase", {}).get("score", ""),
            "current_state": crossfamily_rows.get("kinase", {}).get("current_state", ""),
            "runtime_scope_now": MEASURED_NOOP_SAFE_SCOPE,
            "pretest_ready": "yes",
            "claim_safe_test_ready": "yes",
            "router_ready": "n/a",
            "primary_blocker": "",
            "next_required_step": crossfamily_rows.get("kinase", {}).get("next_required_step", ""),
        },
        {
            "family": "idp",
            "commercialization_score": family_scores.get("idp", {}).get("score", ""),
            "current_state": str(idp_effective_decision.get("status", "")).strip() or crossfamily_rows.get("idp", {}).get("current_state", ""),
            "runtime_scope_now": (
                IDP_SAFE_SCOPE_ONE_WIDER_SHADOW_SAFE_LANE
                if idp_broader_promotion_resolution_summary
                else
                IDP_SAFE_SCOPE_CONTROLLED_PRETEST
                if idp_pretest_summary or idp_effective_decision
                else "literature_anchor_subset_rg_sasa_only"
            ),
            "pretest_ready": "yes",
            "claim_safe_test_ready": "wider_shadow_safe_lane_only" if idp_broader_promotion_resolution_summary else "controlled_shadow_only" if idp_pretest_summary or idp_effective_decision else "subset_only",
            "router_ready": "n/a",
            "primary_blocker": (
                "repeatability_confirmation_required"
                if idp_repeatability_summary and str(idp_one_wider_repeatability_result_summary.get("status", "")).strip() != "one_wider_shadow_repeatability_confirmed"
                else str(idp_effective_decision.get("blocking_class", "")).strip() or "broader_full_idp_promotion_blocked"
            ),
            "next_required_step": (
                str(idp_repeatability_summary.get("next_required_step", "")).strip()
                or str(idp_effective_decision.get("next_required_step", "")).strip()
                or idp_pretest_summary.get("next_required_step", "")
                or idp_summary.get("next_required_step", "")
            ),
        },
        {
            "family": "non_kinase_enzyme_ca2",
            "commercialization_score": family_scores.get("non_kinase_enzyme_ca2", {}).get("score", ""),
            "current_state": crossfamily_rows.get("non_kinase_enzyme_ca2", {}).get("current_state", ""),
            "runtime_scope_now": PARTIAL_AUTHORITATIVE_SAFE_SCOPE,
            "pretest_ready": "partial",
            "claim_safe_test_ready": "no",
            "router_ready": "n/a",
            "primary_blocker": ca2_summary.get("most_common_missing_field", ""),
            "next_required_step": ca2_summary.get("next_required_step", ""),
        },
        {
            "family": "nuclear_receptor_pxr",
            "commercialization_score": family_scores.get("nuclear_receptor_pxr", {}).get("score", ""),
            "current_state": crossfamily_rows.get("nuclear_receptor_pxr", {}).get("current_state", ""),
            "runtime_scope_now": PARTIAL_AUTHORITATIVE_SAFE_SCOPE,
            "pretest_ready": "partial",
            "claim_safe_test_ready": "no",
            "router_ready": "n/a",
            "primary_blocker": pxr_summary.get("most_common_missing_field", ""),
            "next_required_step": pxr_summary.get("next_required_step", ""),
        },
        {
            "family": "transporter",
            "commercialization_score": family_scores.get("transporter", {}).get("score", ""),
            "current_state": crossfamily_rows.get("transporter", {}).get("current_state", ""),
            "runtime_scope_now": TRANSPORTER_SAFE_SCOPE_SEED_ROW_BLOCKER_CLOSURE,
            "pretest_ready": "no",
            "claim_safe_test_ready": "no",
            "router_ready": "n/a",
            "primary_blocker": transporter_seed_summary.get("top_blocker_id", "") or "local_evidence_and_donor_policy_blocked",
            "next_required_step": transporter_seed_summary.get("next_required_step", "") or transporter_next_step,
        },
    ]

    summary = {
        "family_count": len(rows),
        "pretest_ready_count": sum(1 for row in rows if row["pretest_ready"] == "yes"),
        "partial_pretest_ready_count": sum(1 for row in rows if row["pretest_ready"] == "partial"),
        "blocked_pretest_count": sum(1 for row in rows if row["pretest_ready"] == "no"),
        "claim_safe_test_ready_count": sum(1 for row in rows if row["claim_safe_test_ready"] == "yes"),
        "subset_only_count": sum(1 for row in rows if row["claim_safe_test_ready"] == "subset_only"),
        "controlled_shadow_only_count": sum(1 for row in rows if row["claim_safe_test_ready"] == "controlled_shadow_only"),
        "wider_shadow_safe_lane_only_count": sum(1 for row in rows if row["claim_safe_test_ready"] == "wider_shadow_safe_lane_only"),
        "transporter_seed_row_count": transporter_seed_rows,
        "transporter_placeholder_row_count": transporter_placeholder_rows,
        "all_category_expansion_score": commercialization_payload.get("summary", {}).get("all_category_expansion_score", ""),
        "core_commercial_lane_score": commercialization_payload.get("summary", {}).get("core_commercial_lane_score", ""),
        "next_required_step": (
            "Run only the families marked pretest-ready within their allowed scope. Launch or monitor the bounded IDP one-wider shadow repeatability rerun on the frozen validated-7-plus-PAGE4 roster, keep broader_full_idp_promotion blocked, and do not widen the roster or claim commercialization beyond that bounded lane; keep CA2/PXR in partial-authoritative preparation mode; keep transporter in seed-row blocker-closure mode until packet evidence, placeholder rows, and donor policy blockers reduce."
            if idp_broader_promotion_resolution_summary and idp_repeatability_summary and transporter_phase == "seed_row_blocker_closure"
            else "Run only the families marked pretest-ready within their allowed scope. Launch or monitor the bounded IDP one-wider shadow repeatability rerun on the frozen validated-7-plus-PAGE4 roster, keep broader_full_idp_promotion blocked, and do not widen the roster or claim commercialization beyond that bounded lane; keep CA2/PXR in partial-authoritative preparation mode; keep transporter in manual-review mode until packet evidence and donor policy mature."
            if idp_broader_promotion_resolution_summary and idp_repeatability_summary
            else
            "Run only the families marked pretest-ready within their allowed scope. Retain IDP on the newly admitted one-wider shadow-safe lane frozen to the validated 7-target scaffold plus PAGE4, keep broader_full_idp_promotion blocked, and do not widen the roster or claim commercialization beyond that bounded lane; keep CA2/PXR in partial-authoritative preparation mode; keep transporter in seed-row blocker-closure mode until packet evidence, placeholder rows, and donor policy blockers reduce."
            if idp_broader_promotion_resolution_summary and transporter_phase == "seed_row_blocker_closure"
            else "Run only the families marked pretest-ready within their allowed scope. Retain IDP on the newly admitted one-wider shadow-safe lane frozen to the validated 7-target scaffold plus PAGE4, keep broader_full_idp_promotion blocked, and do not widen the roster or claim commercialization beyond that bounded lane; keep CA2/PXR in partial-authoritative preparation mode; keep transporter in manual-review mode until packet evidence and donor policy mature."
            if idp_broader_promotion_resolution_summary
            else
            "Run only the families marked pretest-ready within their allowed scope. Retain IDP on the controlled shadow-only commercial-pretest lane, record that the first broader shadow-only rerun passed cleanly, keep broader promotion blocked, and reopen only the explicit promotion review rather than auto-widening the lane; keep CA2/PXR in partial-authoritative preparation mode; keep transporter in seed-row blocker-closure mode until packet evidence, placeholder rows, and donor policy blockers reduce."
            if idp_broader_decision_summary and transporter_phase == "seed_row_blocker_closure"
            else "Run only the families marked pretest-ready within their allowed scope. Retain IDP on the controlled shadow-only commercial-pretest lane, record that the first broader shadow-only rerun passed cleanly, keep broader promotion blocked, and reopen only the explicit promotion review rather than auto-widening the lane; keep CA2/PXR in partial-authoritative preparation mode; keep transporter in manual-review mode until packet evidence and donor policy mature."
            if idp_broader_decision_summary
            else
            "Run only the families marked pretest-ready within their allowed scope. Retain IDP on the controlled shadow-only commercial-pretest lane, keep broader promotion blocked, treat same-scope reproducibility as confirmed, and move the next IDP improvement to page4 quantitative anchor replacement before any true broader rerun; keep CA2/PXR in partial-authoritative preparation mode; keep transporter in seed-row blocker-closure mode until packet evidence, placeholder rows, and donor policy blockers reduce."
            if idp_pretest_decision_summary and idp_same_scope_reproducibility_confirmed and idp_additional_anchor_backed_target_count == 0 and idp_page4_candidate_ready_now and transporter_phase == "seed_row_blocker_closure"
            else "Run only the families marked pretest-ready within their allowed scope. Retain IDP on the controlled shadow-only commercial-pretest lane, keep broader promotion blocked, treat same-scope reproducibility as confirmed, and move the next IDP improvement to page4 quantitative anchor replacement before any true broader rerun; keep CA2/PXR in partial-authoritative preparation mode; keep transporter in manual-review mode until packet evidence and donor policy mature."
            if idp_pretest_decision_summary and idp_same_scope_reproducibility_confirmed and idp_additional_anchor_backed_target_count == 0 and idp_page4_candidate_ready_now
            else "Run only the families marked pretest-ready within their allowed scope. Retain IDP on the controlled shadow-only commercial-pretest lane, keep broader promotion blocked, treat same-scope reproducibility as confirmed, and move the next IDP improvement to page4 manual-confirmation console before any true broader rerun; keep CA2/PXR in partial-authoritative preparation mode; keep transporter in seed-row blocker-closure mode until packet evidence, placeholder rows, and donor policy blockers reduce."
            if idp_pretest_decision_summary and idp_same_scope_reproducibility_confirmed and idp_additional_anchor_backed_target_count == 0 and transporter_phase == "seed_row_blocker_closure"
            else "Run only the families marked pretest-ready within their allowed scope. Retain IDP on the controlled shadow-only commercial-pretest lane, keep broader promotion blocked, treat same-scope reproducibility as confirmed, and move the next IDP improvement to page4 manual-confirmation console before any true broader rerun; keep CA2/PXR in partial-authoritative preparation mode; keep transporter in manual-review mode until packet evidence and donor policy mature."
            if idp_pretest_decision_summary and idp_same_scope_reproducibility_confirmed and idp_additional_anchor_backed_target_count == 0
            else "Run only the families marked pretest-ready within their allowed scope. Retain IDP on the controlled shadow-only commercial-pretest lane, keep broader promotion blocked, and do not call the next IDP run broader yet; either approve one same-scope process check on the validated 7-target literature-anchor subset or curate at least one additional anchor-backed target first; keep CA2/PXR in partial-authoritative preparation mode; keep transporter in seed-row blocker-closure mode until packet evidence, placeholder rows, and donor policy blockers reduce."
            if idp_pretest_decision_summary and idp_additional_anchor_backed_target_count == 0 and transporter_phase == "seed_row_blocker_closure"
            else "Run only the families marked pretest-ready within their allowed scope. Retain IDP on the controlled shadow-only commercial-pretest lane, keep broader promotion blocked, and do not call the next IDP run broader yet; either approve one same-scope process check on the validated 7-target literature-anchor subset or curate at least one additional anchor-backed target first; keep CA2/PXR in partial-authoritative preparation mode; keep transporter in manual-review mode until packet evidence and donor policy mature."
            if idp_pretest_decision_summary and idp_additional_anchor_backed_target_count == 0
            else "Run only the families marked pretest-ready within their allowed scope. Retain IDP on the controlled shadow-only commercial-pretest lane, keep broader promotion blocked, use the broader-shadow review step to freeze policy/roster/guardrails, and only then consider one broader full-IDP shadow rerun; keep CA2/PXR in partial-authoritative preparation mode; keep transporter in seed-row blocker-closure mode until packet evidence, placeholder rows, and donor policy blockers reduce."
            if transporter_phase == "seed_row_blocker_closure"
            else "Run only the families marked pretest-ready within their allowed scope. Retain IDP on the controlled shadow-only commercial-pretest lane, keep broader promotion blocked, use the broader-shadow review step to freeze policy/roster/guardrails, and only then consider one broader full-IDP shadow rerun; keep CA2/PXR in partial-authoritative preparation mode; keep transporter in manual-review mode until packet evidence and donor policy mature."
        ),
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# Pretest Execution Readiness",
        "",
        f"- family_count: `{s['family_count']}`",
        f"- pretest_ready_count: `{s['pretest_ready_count']}`",
        f"- partial_pretest_ready_count: `{s['partial_pretest_ready_count']}`",
        f"- blocked_pretest_count: `{s['blocked_pretest_count']}`",
        f"- claim_safe_test_ready_count: `{s['claim_safe_test_ready_count']}`",
        f"- subset_only_count: `{s['subset_only_count']}`",
        f"- controlled_shadow_only_count: `{s['controlled_shadow_only_count']}`",
        f"- transporter_seed_row_count: `{s['transporter_seed_row_count']}`",
        f"- transporter_placeholder_row_count: `{s['transporter_placeholder_row_count']}`",
        f"- core_commercial_lane_score: `{s['core_commercial_lane_score']}`",
        f"- all_category_expansion_score: `{s['all_category_expansion_score']}`",
        "",
        "## Next Step",
        "",
        f"- {s['next_required_step']}",
        "",
        "## Family Matrix",
        "",
        "| family | commercialization_score | current_state | runtime_scope_now | pretest_ready | claim_safe_test_ready | router_ready | primary_blocker | next_required_step |",
        "| --- | ---: | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['family']}` | {row['commercialization_score']} | `{row['current_state']}` | `{row['runtime_scope_now']}` | `{row['pretest_ready']}` | `{row['claim_safe_test_ready']}` | `{row['router_ready']}` | `{row['primary_blocker']}` | {row['next_required_step']} |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a cross-family pretest execution readiness board.")
    parser.add_argument("--commercialization-json", default=DEFAULT_COMMERCIALIZATION_JSON)
    parser.add_argument("--crossfamily-json", default=DEFAULT_CROSSFAMILY_JSON)
    parser.add_argument("--gpcr-endpoint-json", default=DEFAULT_GPCR_ENDPOINT_JSON)
    parser.add_argument("--idp-subset-decision-json", default=DEFAULT_IDP_SUBSET_DECISION_JSON)
    parser.add_argument("--idp-commercial-pretest-json", default=DEFAULT_IDP_COMMERCIAL_PRETEST_JSON)
    parser.add_argument("--idp-commercial-pretest-decision-json", default=DEFAULT_IDP_COMMERCIAL_PRETEST_DECISION_JSON)
    parser.add_argument("--idp-broader-shadow-decision-json", default=DEFAULT_IDP_BROADER_SHADOW_DECISION_JSON)
    parser.add_argument("--idp-broader-promotion-resolution-json", default=DEFAULT_IDP_BROADER_PROMOTION_RESOLUTION_JSON)
    parser.add_argument("--idp-one-wider-repeatability-packet-json", default=DEFAULT_IDP_ONE_WIDER_REPEATABILITY_PACKET_JSON)
    parser.add_argument("--idp-one-wider-repeatability-result-json", default=DEFAULT_IDP_ONE_WIDER_REPEATABILITY_RESULT_JSON)
    parser.add_argument("--ca2-readiness-json", default=DEFAULT_CA2_READINESS_JSON)
    parser.add_argument("--pxr-readiness-json", default=DEFAULT_PXR_READINESS_JSON)
    parser.add_argument("--transporter-dashboard-json", default=DEFAULT_TRANSPORTER_DASHBOARD_JSON)
    parser.add_argument("--transporter-seed-row-board-json", default=DEFAULT_TRANSPORTER_SEED_ROW_BOARD_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        _load_json(args.commercialization_json),
        _load_json(args.crossfamily_json),
        _load_json(args.gpcr_endpoint_json),
        _load_json(args.idp_subset_decision_json),
        _load_json(args.idp_commercial_pretest_json),
        _load_json(args.ca2_readiness_json),
        _load_json(args.pxr_readiness_json),
        _load_json(args.transporter_dashboard_json),
        _load_json(args.transporter_seed_row_board_json),
        _maybe_load_json(args.idp_commercial_pretest_decision_json),
        _maybe_load_json(args.idp_broader_shadow_decision_json),
        _maybe_load_json(args.idp_broader_promotion_resolution_json),
        _maybe_load_json(args.idp_one_wider_repeatability_packet_json),
        _maybe_load_json(args.idp_one_wider_repeatability_result_json),
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

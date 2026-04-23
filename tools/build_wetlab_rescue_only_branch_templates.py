#!/usr/bin/env python3
from __future__ import annotations

import argparse
from typing import Any

from tools.wetlab_target_render_utils import maybe_load_json, write_artifact

DEFAULT_TCRUZI_PDE_RESCUE_ONLY_BRANCH_SUMMARY_JSON = "runs/wetlab_tcruzi_pde_rescue_only_branch_summary_current.json"
DEFAULT_TCRUZI_PDE_PROMOTED_TOP4_REVIEW_PACKET_JSON = "runs/wetlab_tcruzi_pde_promoted_top4_review_packet_current.json"
DEFAULT_CATHEPSIN_K_TUNED_BRANCH_SUMMARY_JSON = "runs/wetlab_cathepsin_k_tuned_branch_summary_current.json"
DEFAULT_CATHEPSIN_K_TUNED_OPERATOR_PACKET_JSON = "runs/wetlab_cathepsin_k_tuned_operator_packet_current.json"
DEFAULT_DENGUE_REVIEW_BRANCH_SUMMARY_JSON = "runs/wetlab_dengue_ns2b_ns3_protease_review_branch_summary_current.json"
DEFAULT_DENGUE_OPERATOR_PACKET_JSON = "runs/wetlab_dengue_ns2b_ns3_protease_operator_packet_current.json"
DEFAULT_TCRUZI_PDE_RESCUE_OPERATOR_PACKET_MD = "runs/wetlab_tcruzi_pde_rescue_operator_packet_current.md"
DEFAULT_OUT_MD = "runs/wetlab_rescue_only_branch_templates_current.md"


def _summary(payload: dict[str, Any] | None) -> dict[str, Any]:
    return dict((payload or {}).get("summary", {}) or {})


def _text(*values: Any, default: str = "") -> str:
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return default


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value in {"", None}:
            return default
        return float(value)
    except Exception:
        return default


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        if value in {"", None}:
            return default
        return int(value)
    except Exception:
        return default


def _safe_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if value in {"", None}:
        return None
    if isinstance(value, (int, float)):
        return bool(value)
    text = str(value).strip().lower()
    if text in {"1", "true", "t", "yes", "y", "ready", "pass", "passed"}:
        return True
    if text in {"0", "false", "f", "no", "n", "fail", "failed"}:
        return False
    return None


def _resolve_bool_value(payload: dict[str, Any], *keys: str, default: bool = False) -> bool:
    for key in keys:
        value = _safe_bool(payload.get(key))
        if value is not None:
            return value
    return default


def _is_branch_summary_ready(summary: dict[str, Any]) -> bool:
    return _text(summary.get("status")).endswith("_branch_summary_ready")


def _materialize_target_entry(
    *,
    branch_summary_payload: dict[str, Any] | None,
    promoted_top4_review_packet_payload: dict[str, Any] | None,
    template_label: str,
    surface_label: str,
    review_unit_label: str,
    source_surface: str,
    branch_summary_artifact: str,
    review_packet_artifact: str,
    rescue_operator_packet_artifact: str = "",
) -> tuple[dict[str, Any], dict[str, Any]] | None:
    branch_summary = _summary(branch_summary_payload)
    packet_summary = _summary(promoted_top4_review_packet_payload)
    if not _is_branch_summary_ready(branch_summary):
        return None

    row = {
        "row_kind": "rescue_only_branch_template",
        "template_label": template_label,
        "target_id": _text(branch_summary.get("target_id"), packet_summary.get("target_id")),
        "surface_label": surface_label,
        "branch_label": _text(branch_summary.get("branch_label")),
        "selected_command_kind": _text(branch_summary.get("selected_command_kind")),
        "selected_threshold_A": round(_safe_float(branch_summary.get("selected_threshold_A"), 2.5), 3),
        "promoted_candidate_count": _safe_int(branch_summary.get("promoted_candidate_count")),
        "under_2p5_candidate_count": _safe_int(branch_summary.get("under_2p5_candidate_count")),
        "near_candidate_count": _safe_int(branch_summary.get("near_candidate_count")),
        "best_ligand_id": _text(branch_summary.get("best_ligand_id"), packet_summary.get("best_ligand_id")),
        "best_mean_min_distance_A": round(
            _safe_float(
                branch_summary.get("best_mean_min_distance_A"),
                _safe_float(packet_summary.get("best_mean_min_distance_A"), 0.0),
            ),
            3,
        ),
        "branch_ready_for_operator_review": _resolve_bool_value(
            branch_summary,
            "branch_ready_for_operator_review",
            "review_packet_ready_for_operator_review",
            "review_packet_ready",
            "promoted_top4_packet_ready",
            default=_is_branch_summary_ready(branch_summary),
        ),
        "branch_ready_for_final_wetlab": _resolve_bool_value(
            branch_summary,
            "branch_ready_for_final_wetlab",
            "review_packet_final_gate_pass",
            "wetlab_final_gate_pass",
            default=False,
        ),
        "review_packet_final_gate_pass": _resolve_bool_value(
            branch_summary,
            "review_packet_final_gate_pass",
            default=_resolve_bool_value(packet_summary, "wetlab_final_gate_pass", default=False),
        ),
        "claim_gate_available": _resolve_bool_value(
            branch_summary,
            "review_packet_claim_gate_available",
            "claim_gate_available",
            default=_resolve_bool_value(packet_summary, "claim_gate_available", default=False),
        ),
        "claim_ready_for_allatom": _resolve_bool_value(
            branch_summary,
            "review_packet_claim_ready_for_allatom",
            "claim_ready_for_allatom",
            default=_resolve_bool_value(packet_summary, "claim_ready_for_allatom", default=False),
        ),
        "default_lane_reopen_allowed": bool(branch_summary.get("default_lane_reopen_allowed", False)),
        "branch_to_rescue_only": bool(branch_summary.get("branch_to_rescue_only", False)),
        "review_unit_label": review_unit_label,
        "source_surface": source_surface,
        "next_required_step": _text(branch_summary.get("next_required_step"), packet_summary.get("next_required_step")),
    }
    artifacts = {
        "target_id": row["target_id"],
        "template_label": template_label,
        "surface_label": surface_label,
        "branch_summary_artifact": branch_summary_artifact,
        "review_packet_artifact": review_packet_artifact,
    }
    if rescue_operator_packet_artifact:
        artifacts["rescue_operator_packet_artifact"] = rescue_operator_packet_artifact
    return row, artifacts


def build_payload(
    tcruzi_pde_rescue_only_branch_summary_payload: dict[str, Any] | None,
    tcruzi_pde_promoted_top4_review_packet_payload: dict[str, Any] | None = None,
    additional_rescue_only_branch_target_entries: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    target_artifacts: list[dict[str, Any]] = []

    focus_entry = _materialize_target_entry(
        branch_summary_payload=tcruzi_pde_rescue_only_branch_summary_payload,
        promoted_top4_review_packet_payload=tcruzi_pde_promoted_top4_review_packet_payload,
        template_label="three_bead_rescue_only_branch",
        surface_label="pde_rescue_only_branch",
        review_unit_label="promoted_top4_three_bead_rescue_review",
        source_surface="tcruzi_pde_rescue_only_branch_summary",
        branch_summary_artifact="runs/wetlab_tcruzi_pde_rescue_only_branch_summary_current.md",
        review_packet_artifact="runs/wetlab_tcruzi_pde_promoted_top4_review_packet_current.md",
        rescue_operator_packet_artifact=DEFAULT_TCRUZI_PDE_RESCUE_OPERATOR_PACKET_MD,
    )
    if focus_entry:
        focus_row, focus_artifacts = focus_entry
        rows.append(focus_row)
        target_artifacts.append(focus_artifacts)

    for target_entry in additional_rescue_only_branch_target_entries or []:
        extra_entry = _materialize_target_entry(
            branch_summary_payload=target_entry.get("branch_summary_payload"),
            promoted_top4_review_packet_payload=target_entry.get("promoted_top4_review_packet_payload"),
            template_label=_text(target_entry.get("template_label"), "three_bead_rescue_only_branch"),
            surface_label=_text(
                target_entry.get("surface_label"),
                _text((_summary(target_entry.get("branch_summary_payload"))).get("branch_label"), "rescue_only_branch"),
            ),
            review_unit_label=_text(target_entry.get("review_unit_label"), "promoted_top4_three_bead_rescue_review"),
            source_surface=_text(
                target_entry.get("source_surface"),
                _text((_summary(target_entry.get("branch_summary_payload"))).get("branch_label"), "rescue_only_branch_summary"),
            ),
            branch_summary_artifact=_text(target_entry.get("branch_summary_artifact")),
            review_packet_artifact=_text(
                target_entry.get("review_packet_artifact"),
                target_entry.get("promoted_top4_review_packet_artifact"),
            ),
            rescue_operator_packet_artifact=_text(target_entry.get("rescue_operator_packet_artifact")),
        )
        if not extra_entry:
            continue
        extra_row, extra_artifacts = extra_entry
        rows.append(extra_row)
        target_artifacts.append(extra_artifacts)

    focus_row = rows[0] if rows else {}
    additional_rows = rows[1:] if len(rows) > 1 else []
    next_required_step = _text(focus_row.get("next_required_step"), additional_rows[0].get("next_required_step") if additional_rows else "")
    return {
        "summary": {
            "status": "wetlab_rescue_only_branch_templates_ready" if rows else "wetlab_rescue_only_branch_templates_empty",
            "template_target_count": len(rows),
            "additional_rescue_only_branch_target_count": len(additional_rows),
            "focus_target_id": _text(focus_row.get("target_id")),
            "focus_template_label": _text(focus_row.get("template_label")),
            "focus_surface_label": _text(focus_row.get("surface_label")),
            "focus_selected_command_kind": _text(focus_row.get("selected_command_kind")),
            "focus_selected_threshold_A": round(_safe_float(focus_row.get("selected_threshold_A")), 3),
            "focus_promoted_candidate_count": _safe_int(focus_row.get("promoted_candidate_count")),
            "focus_under_2p5_candidate_count": _safe_int(focus_row.get("under_2p5_candidate_count")),
            "focus_branch_ready_for_operator_review": bool(focus_row.get("branch_ready_for_operator_review", False)),
            "focus_branch_ready_for_final_wetlab": bool(focus_row.get("branch_ready_for_final_wetlab", False)),
            "focus_review_packet_final_gate_pass": bool(focus_row.get("review_packet_final_gate_pass", False)),
            "focus_claim_gate_available": bool(focus_row.get("claim_gate_available", False)),
            "focus_claim_ready_for_allatom": bool(focus_row.get("claim_ready_for_allatom", False)),
            "first_additional_rescue_only_branch_target": _text(additional_rows[0].get("target_id")) if additional_rows else "",
            "next_required_step": next_required_step,
        },
        "structured": {
            "tcruzi_pde_rescue_only_branch_summary_artifact": "runs/wetlab_tcruzi_pde_rescue_only_branch_summary_current.md",
            "tcruzi_pde_promoted_top4_review_packet_artifact": "runs/wetlab_tcruzi_pde_promoted_top4_review_packet_current.md",
            "tcruzi_pde_rescue_operator_packet_artifact": DEFAULT_TCRUZI_PDE_RESCUE_OPERATOR_PACKET_MD,
            "additional_rescue_only_branch_target_artifacts": target_artifacts[1:] if len(target_artifacts) > 1 else [],
        },
        "rows": rows,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build generic rescue-only branch templates.")
    parser.add_argument("--tcruzi-pde-rescue-only-branch-summary-json", default=DEFAULT_TCRUZI_PDE_RESCUE_ONLY_BRANCH_SUMMARY_JSON)
    parser.add_argument("--tcruzi-pde-promoted-top4-review-packet-json", default=DEFAULT_TCRUZI_PDE_PROMOTED_TOP4_REVIEW_PACKET_JSON)
    parser.add_argument("--cathepsin-k-tuned-branch-summary-json", default=DEFAULT_CATHEPSIN_K_TUNED_BRANCH_SUMMARY_JSON)
    parser.add_argument("--cathepsin-k-tuned-operator-packet-json", default=DEFAULT_CATHEPSIN_K_TUNED_OPERATOR_PACKET_JSON)
    parser.add_argument("--dengue-review-branch-summary-json", default=DEFAULT_DENGUE_REVIEW_BRANCH_SUMMARY_JSON)
    parser.add_argument("--dengue-operator-packet-json", default=DEFAULT_DENGUE_OPERATOR_PACKET_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        maybe_load_json(args.tcruzi_pde_rescue_only_branch_summary_json),
        maybe_load_json(args.tcruzi_pde_promoted_top4_review_packet_json),
        additional_rescue_only_branch_target_entries=[
            {
                "branch_summary_payload": maybe_load_json(args.cathepsin_k_tuned_branch_summary_json),
                "promoted_top4_review_packet_payload": maybe_load_json(args.cathepsin_k_tuned_operator_packet_json),
                "template_label": "guarded_tuned_branch_promote",
                "surface_label": "cathepsin_k_tuned_branch",
                "review_unit_label": "tuned branch operator packet",
                "source_surface": "cathepsin_k_tuned_branch_summary",
                "branch_summary_artifact": "runs/wetlab_cathepsin_k_tuned_branch_summary_current.md",
                "review_packet_artifact": "runs/wetlab_cathepsin_k_tuned_operator_packet_current.md",
                "rescue_operator_packet_artifact": "runs/wetlab_cathepsin_k_tuned_operator_packet_current.md",
            },
            {
                "branch_summary_payload": maybe_load_json(args.dengue_review_branch_summary_json),
                "promoted_top4_review_packet_payload": maybe_load_json(args.dengue_operator_packet_json),
                "template_label": "guarded_stage6_review_branch",
                "surface_label": "dengue_ns2b_ns3_review_branch",
                "review_unit_label": "guarded stage6 operator packet",
                "source_surface": "dengue_ns2b_ns3_protease_review_branch_summary",
                "branch_summary_artifact": "runs/wetlab_dengue_ns2b_ns3_protease_review_branch_summary_current.md",
                "review_packet_artifact": "runs/wetlab_dengue_ns2b_ns3_protease_operator_packet_current.md",
                "rescue_operator_packet_artifact": "runs/wetlab_dengue_ns2b_ns3_protease_operator_packet_current.md",
            },
        ],
    )
    write_artifact(args.out_md, "Wet-Lab Rescue-Only Branch Templates", payload)


if __name__ == "__main__":
    main()

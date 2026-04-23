#!/usr/bin/env python3
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from tools.wetlab_target_render_utils import load_json, write_artifact


ReviewPacketBuilder = Callable[[dict[str, Any], dict[str, Any] | None], dict[str, Any]]


@dataclass(frozen=True)
class RescueOnlyBranchTemplate:
    branch_key: str
    target_id: str
    branch_label: str
    review_unit_label: str
    review_surface_artifact: str
    review_surface_title: str
    review_packet_artifact: str
    review_packet_title: str
    branch_runner_artifact: str
    branch_runner_title: str
    branch_summary_artifact: str
    branch_summary_title: str
    operator_packet_artifact: str = ""
    operator_packet_title: str = ""
    operator_packet_step_id: str = "rescue_operator_packet"
    operator_packet_structured_key: str = "rescue_operator_packet_artifact"
    review_surface_step_id: str = "rescue_review_surface"
    review_packet_step_id: str = "review_packet"
    review_packet_signal_suffix: str = "review rows"
    review_surface_structured_key: str = "rescue_review_surface_artifact"
    review_packet_structured_key: str = "review_packet_artifact"
    branch_runner_structured_key: str = "branch_runner_artifact"
    three_bead_slice_artifact: str = "runs/wetlab_rescue_three_bead_slice_current.md"
    three_bead_slice_step_id: str = "three_bead_slice"
    three_bead_slice_structured_key: str = "rescue_three_bead_slice_artifact"
    generic_runner_artifact: str = "runs/wetlab_hard_target_rescue_runner_current.md"
    generic_runner_structured_key: str = "generic_hard_target_rescue_runner_artifact"
    default_selected_command_kind: str = "three_bead_rescue_local_refine"
    default_selected_threshold_a: float = 2.5
    runner_branch_state: str = "adopted_from_generic_rescue_lane"
    default_execution_mode: str = "adopted_from_generic_rescue_lane"
    operator_packet_ready_status: str = ""
    review_packet_ready_alias: str = ""
    review_packet_candidate_count_alias: str = ""
    strict_candidate_count_alias: str = ""
    ready_branch_state: str = "review_packet_ready_default_lane_closed"
    pending_branch_state: str = "review_pending_default_lane_closed"

    @property
    def runner_status(self) -> str:
        return f"wetlab_{self.branch_key}_rescue_only_branch_runner_ready"

    @property
    def summary_status(self) -> str:
        return f"wetlab_{self.branch_key}_rescue_only_branch_summary_ready"

    @property
    def step_row_kind(self) -> str:
        return f"{self.branch_key}_rescue_only_branch_step"

    @property
    def runner_row_kind(self) -> str:
        return f"{self.branch_key}_rescue_only_branch_runner"

    def next_required_step(self, target_id: str = "") -> str:
        target_name = _text(target_id, self.target_id)
        return (
            f"Operate {target_name} through the dedicated rescue-only branch, keep the default lane closed, "
            f"and use the {self.review_unit_label} as the review unit before any reopen decision."
        )

    def pending_next_required_step(self, target_id: str = "") -> str:
        target_name = _text(target_id, self.target_id)
        return (
            f"Keep the {target_name} default lane closed and use the {self.review_unit_label} as the operator "
            f"review unit before any rescue-only branch or reopen decision."
        )


TCRUZI_PDE_RESCUE_ONLY_BRANCH_TEMPLATE = RescueOnlyBranchTemplate(
    branch_key="tcruzi_pde",
    target_id="T. cruzi PDE",
    branch_label="tcruzi_pde_rescue_only_branch",
    review_unit_label="promoted top-4 packet",
    review_surface_artifact="runs/wetlab_tcruzi_pde_rescue_review_surface_current.md",
    review_surface_title="Wet-Lab T. cruzi PDE Rescue Review Surface",
    review_packet_artifact="runs/wetlab_tcruzi_pde_promoted_top4_review_packet_current.md",
    review_packet_title="Wet-Lab T. cruzi PDE Promoted Top-4 Review Packet",
    operator_packet_artifact="runs/wetlab_tcruzi_pde_rescue_operator_packet_current.md",
    operator_packet_title="Wet-Lab T. cruzi PDE Rescue Operator Packet",
    branch_runner_artifact="runs/wetlab_tcruzi_pde_rescue_only_branch_runner_current.md",
    branch_runner_title="Wet-Lab T. cruzi PDE Rescue-Only Branch Runner",
    branch_summary_artifact="runs/wetlab_tcruzi_pde_rescue_only_branch_summary_current.md",
    branch_summary_title="Wet-Lab T. cruzi PDE Rescue-Only Branch Summary",
    review_packet_step_id="promoted_top4_review_packet",
    review_packet_signal_suffix="promoted",
    review_packet_structured_key="promoted_top4_review_packet_artifact",
    branch_runner_structured_key="rescue_only_branch_runner_artifact",
    review_packet_ready_alias="promoted_top4_packet_ready",
    review_packet_candidate_count_alias="promoted_candidate_count",
    strict_candidate_count_alias="under_2p5_candidate_count",
    ready_branch_state="promoted_top4_packet_ready_default_lane_closed",
    pending_branch_state="review_pending_default_lane_closed",
)


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


def _resolve_bool_value(payload: dict[str, Any], *keys: str, default: bool = False) -> tuple[bool, str]:
    for key in keys:
        value = _safe_bool(payload.get(key))
        if value is not None:
            return value, key
    return default, "default"


def _resolve_optional_bool_value(payload: dict[str, Any], *keys: str) -> tuple[bool | None, str]:
    for key in keys:
        value = _safe_bool(payload.get(key))
        if value is not None:
            return value, key
    return None, "missing"


def _review_ready_only_source(review_ready_source: str) -> str:
    if review_ready_source and review_ready_source != "default":
        return f"review_ready_only.{review_ready_source}"
    return "missing_explicit_gate"


def _source_is_review_ready_only_fallback(source: str) -> bool:
    return source.startswith("review_ready_only.") or source == "missing_explicit_gate"


def _gate_semantics(source: str, *, reported: bool) -> str:
    if source == "derived_from_explicit_wetlab_gate_pass":
        return "derived_from_explicit_wetlab_gate"
    if reported:
        return "explicit_gate_reported"
    if _source_is_review_ready_only_fallback(source):
        return "review_ready_only_blocked_pending_explicit_gate"
    return "blocked_pending_explicit_gate"


def _packet_gate_state(packet: dict[str, Any]) -> dict[str, Any]:
    operator_ready, operator_ready_source = _resolve_bool_value(
        packet,
        "packet_ready_for_operator_review",
        "review_packet_ready",
        "packet_ready",
    )
    explicit_wetlab_gate_pass, explicit_wetlab_gate_source = _resolve_optional_bool_value(packet, "wetlab_gate_pass")
    if explicit_wetlab_gate_pass is None:
        wetlab_gate_pass = False
        wetlab_gate_source = _review_ready_only_source(operator_ready_source)
        wetlab_gate_reported = False
    else:
        wetlab_gate_pass = explicit_wetlab_gate_pass
        wetlab_gate_source = explicit_wetlab_gate_source
        wetlab_gate_reported = True

    explicit_final_gate_pass, explicit_final_gate_source = _resolve_optional_bool_value(packet, "wetlab_final_gate_pass")
    if explicit_final_gate_pass is not None:
        wetlab_final_gate_pass = explicit_final_gate_pass
        wetlab_final_gate_source = explicit_final_gate_source
        wetlab_final_gate_reported = True
    elif explicit_wetlab_gate_pass is not None:
        wetlab_final_gate_pass = explicit_wetlab_gate_pass
        wetlab_final_gate_source = "derived_from_explicit_wetlab_gate_pass"
        wetlab_final_gate_reported = False
    else:
        wetlab_final_gate_pass = False
        wetlab_final_gate_source = _review_ready_only_source(operator_ready_source)
        wetlab_final_gate_reported = False

    claim_gate_available, claim_gate_source = _resolve_bool_value(
        packet,
        "claim_gate_available",
        default=False,
    )
    claim_ready_for_allatom, claim_ready_source = _resolve_bool_value(
        packet,
        "claim_ready_for_allatom",
        default=False,
    )
    return {
        "packet_ready_for_operator_review": operator_ready,
        "packet_ready_for_operator_review_source": operator_ready_source,
        "wetlab_gate_pass": wetlab_gate_pass,
        "wetlab_gate_source": wetlab_gate_source,
        "wetlab_gate_reported": wetlab_gate_reported,
        "wetlab_gate_semantics": _gate_semantics(wetlab_gate_source, reported=wetlab_gate_reported),
        "wetlab_final_gate_pass": wetlab_final_gate_pass,
        "wetlab_final_gate_source": wetlab_final_gate_source,
        "wetlab_final_gate_reported": wetlab_final_gate_reported,
        "wetlab_final_gate_semantics": _gate_semantics(
            wetlab_final_gate_source,
            reported=wetlab_final_gate_reported,
        ),
        "claim_gate_available": claim_gate_available,
        "claim_gate_source": claim_gate_source,
        "claim_ready_for_allatom": claim_ready_for_allatom,
        "claim_ready_source": claim_ready_source,
    }


def _review_packet_ready(packet: dict[str, Any]) -> bool:
    return _packet_gate_state(packet)["packet_ready_for_operator_review"]


def _review_packet_candidate_count(packet: dict[str, Any]) -> int:
    return _safe_int(packet.get("review_packet_candidate_count"), _safe_int(packet.get("promoted_candidate_count")))


def _strict_candidate_count(packet: dict[str, Any]) -> int:
    return _safe_int(packet.get("strict_candidate_count"), _safe_int(packet.get("under_2p5_candidate_count")))


def _operator_packet_ready(packet: dict[str, Any], template: RescueOnlyBranchTemplate) -> bool:
    gate_state = _packet_gate_state(packet)
    if gate_state["packet_ready_for_operator_review"]:
        return True
    status = _text(packet.get("status"))
    if template.operator_packet_ready_status and status == template.operator_packet_ready_status:
        return True
    if status.endswith("_rescue_operator_packet_ready"):
        return True
    return bool(packet.get("packet_ready", False))


def _branch_next_required_step(
    template: RescueOnlyBranchTemplate,
    target_id: str,
    *,
    branch_to_rescue_only: bool,
    review_packet_ready: bool,
    wetlab_final_gate_pass: bool,
    wetlab_final_gate_source: str,
) -> str:
    if not (branch_to_rescue_only and review_packet_ready):
        return template.pending_next_required_step(target_id)
    base = template.next_required_step(target_id)
    if wetlab_final_gate_pass:
        if _source_is_review_ready_only_fallback(wetlab_final_gate_source):
            return (
                f"{base} Final wetlab readiness is currently inferred from legacy packet readiness, "
                "so keep the handoff review-only until the explicit all-atom gate is refreshed."
            )
        if wetlab_final_gate_source == "derived_from_explicit_wetlab_gate_pass":
            return (
                f"{base} Final wetlab readiness currently derives from the explicit wetlab gate rather than a "
                "dedicated final-gate field, so keep the handoff review-only until the explicit final gate is refreshed."
            )
        return f"{base} Final wetlab gate currently passes, but keep the handoff review-only until operator confirmation."
    return f"{base} Treat the branch as operator-review only until the explicit final wetlab gate passes."


def _decorate_review_metrics(
    summary: dict[str, Any],
    template: RescueOnlyBranchTemplate,
    *,
    review_packet_ready: bool,
    review_packet_candidate_count: int,
    strict_candidate_count: int,
    near_candidate_count: int,
) -> None:
    summary["review_packet_ready"] = review_packet_ready
    summary["review_packet_candidate_count"] = review_packet_candidate_count
    summary["strict_candidate_count"] = strict_candidate_count
    summary["near_candidate_count"] = near_candidate_count
    if template.review_packet_ready_alias:
        summary[template.review_packet_ready_alias] = review_packet_ready
    if template.review_packet_candidate_count_alias:
        summary[template.review_packet_candidate_count_alias] = review_packet_candidate_count
    if template.strict_candidate_count_alias:
        summary[template.strict_candidate_count_alias] = strict_candidate_count


def _require_target_focus(template: RescueOnlyBranchTemplate, target_id: str) -> str:
    resolved_target = _text(target_id, template.target_id)
    expected_target = _text(template.target_id)
    if expected_target and resolved_target and resolved_target != expected_target:
        raise SystemExit(f"current rescue evidence does not focus {expected_target}: {resolved_target or 'missing'}")
    return resolved_target


def build_rescue_only_branch_runner_payload(
    template: RescueOnlyBranchTemplate,
    review_packet_payload: dict[str, Any],
    hard_target_rescue_runner_payload: dict[str, Any],
    three_bead_slice_payload: dict[str, Any],
) -> dict[str, Any]:
    packet = _summary(review_packet_payload)
    runner = _summary(hard_target_rescue_runner_payload)
    slice_summary = _summary(three_bead_slice_payload)
    packet_gate = _packet_gate_state(packet)

    target_id = _require_target_focus(
        template,
        _text(packet.get("target_id"), runner.get("target_id"), slice_summary.get("target_id"), template.target_id),
    )
    shard_id = _text(packet.get("shard_id"), runner.get("shard_id"), slice_summary.get("shard_id"))
    review_packet_ready = packet_gate["packet_ready_for_operator_review"]
    branch_to_rescue_only = bool(packet.get("branch_to_rescue_only", review_packet_ready))
    review_packet_candidate_count = _review_packet_candidate_count(packet)
    strict_candidate_count = _strict_candidate_count(packet)
    near_candidate_count = _safe_int(packet.get("near_candidate_count"))

    summary = {
        "status": template.runner_status,
        "target_id": target_id,
        "shard_id": shard_id,
        "branch_label": template.branch_label,
        "branch_state": (
            template.runner_branch_state
            if branch_to_rescue_only and review_packet_ready
            else template.pending_branch_state
        ),
        "default_lane_reopen_allowed": False,
        "branch_to_rescue_only": branch_to_rescue_only,
        "review_unit_label": template.review_unit_label,
        "selected_command_kind": _text(
            packet.get("selected_command_kind"),
            slice_summary.get("selected_command_kind"),
            template.default_selected_command_kind,
        ),
        "source_runner_status": _text(runner.get("status")),
        "source_slice_status": _text(slice_summary.get("status")),
        "execution_mode": _text(slice_summary.get("execution_mode"), template.default_execution_mode),
        "scoring_status": _text(slice_summary.get("scoring_status")),
        "review_packet_ready_for_operator_review": review_packet_ready,
        "review_packet_ready_source": packet_gate["packet_ready_for_operator_review_source"],
        "review_packet_wetlab_gate_pass": packet_gate["wetlab_gate_pass"],
        "review_packet_wetlab_gate_source": packet_gate["wetlab_gate_source"],
        "review_packet_wetlab_gate_reported": packet_gate["wetlab_gate_reported"],
        "review_packet_wetlab_gate_semantics": packet_gate["wetlab_gate_semantics"],
        "review_packet_wetlab_gate_legacy_fallback": _source_is_review_ready_only_fallback(packet_gate["wetlab_gate_source"]),
        "review_packet_final_gate_pass": packet_gate["wetlab_final_gate_pass"],
        "review_packet_final_gate_source": packet_gate["wetlab_final_gate_source"],
        "review_packet_final_gate_reported": packet_gate["wetlab_final_gate_reported"],
        "review_packet_final_gate_semantics": packet_gate["wetlab_final_gate_semantics"],
        "review_packet_final_gate_legacy_fallback": _source_is_review_ready_only_fallback(
            packet_gate["wetlab_final_gate_source"]
        ),
        "review_packet_claim_gate_available": packet_gate["claim_gate_available"],
        "review_packet_claim_gate_source": packet_gate["claim_gate_source"],
        "review_packet_claim_ready_for_allatom": packet_gate["claim_ready_for_allatom"],
        "review_packet_claim_ready_source": packet_gate["claim_ready_source"],
        "branch_ready_for_operator_review": branch_to_rescue_only and review_packet_ready,
        "branch_ready_for_final_wetlab": branch_to_rescue_only and packet_gate["wetlab_final_gate_pass"],
        "next_required_step": _branch_next_required_step(
            template,
            target_id,
            branch_to_rescue_only=branch_to_rescue_only,
            review_packet_ready=review_packet_ready,
            wetlab_final_gate_pass=packet_gate["wetlab_final_gate_pass"],
            wetlab_final_gate_source=packet_gate["wetlab_final_gate_source"],
        ),
    }
    _decorate_review_metrics(
        summary,
        template,
        review_packet_ready=review_packet_ready,
        review_packet_candidate_count=review_packet_candidate_count,
        strict_candidate_count=strict_candidate_count,
        near_candidate_count=near_candidate_count,
    )

    return {
        "summary": summary,
        "structured": {
            template.generic_runner_structured_key: template.generic_runner_artifact,
            template.review_surface_structured_key: template.review_surface_artifact,
            template.review_packet_structured_key: template.review_packet_artifact,
            **(
                {template.operator_packet_structured_key: template.operator_packet_artifact}
                if template.operator_packet_artifact
                else {}
            ),
            template.three_bead_slice_structured_key: template.three_bead_slice_artifact,
        },
        "rows": [
            {
                "row_kind": template.runner_row_kind,
                "target_id": target_id,
                "shard_id": shard_id,
                "selected_command_kind": _text(packet.get("selected_command_kind")),
                "generic_runner_status": _text(runner.get("status")),
                "three_bead_slice_status": _text(slice_summary.get("status")),
                "execution_mode": _text(slice_summary.get("execution_mode")),
                "scoring_status": _text(slice_summary.get("scoring_status")),
            }
        ],
    }


def build_rescue_only_branch_summary_payload(
    template: RescueOnlyBranchTemplate,
    review_surface_payload: dict[str, Any],
    review_packet_payload: dict[str, Any],
    branch_runner_payload: dict[str, Any],
    three_bead_slice_payload: dict[str, Any] | None = None,
    operator_packet_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    review = _summary(review_surface_payload)
    packet = _summary(review_packet_payload)
    runner = _summary(branch_runner_payload)
    slice_summary = _summary(three_bead_slice_payload)
    operator_packet = _summary(operator_packet_payload)
    packet_gate = _packet_gate_state(packet)
    operator_gate = _packet_gate_state(operator_packet) if operator_packet else {}

    target_id = _require_target_focus(
        template,
        _text(packet.get("target_id"), runner.get("target_id"), review.get("target_id"), template.target_id),
    )
    shard_id = _text(packet.get("shard_id"), runner.get("shard_id"), review.get("shard_id"))
    review_packet_ready = packet_gate["packet_ready_for_operator_review"]
    branch_to_rescue_only = bool(
        packet.get("branch_to_rescue_only", review.get("branch_to_rescue_only", runner.get("branch_to_rescue_only", True)))
    )
    review_packet_candidate_count = _review_packet_candidate_count(packet)
    strict_candidate_count = _strict_candidate_count(packet)
    near_candidate_count = _safe_int(packet.get("near_candidate_count"))
    branch_state = (
        template.ready_branch_state
        if review_packet_ready and branch_to_rescue_only
        else template.pending_branch_state
    )

    rows = [
        {
            "row_kind": template.step_row_kind,
            "step_id": template.review_surface_step_id,
            "status": _text(review.get("status")),
            "artifact": template.review_surface_artifact,
            "signal": _text(review.get("decision")),
        },
        {
            "row_kind": template.step_row_kind,
            "step_id": template.review_packet_step_id,
            "status": _text(packet.get("status")),
            "artifact": template.review_packet_artifact,
            "signal": (
                f"{review_packet_candidate_count} {template.review_packet_signal_suffix}; "
                f"operator_review={'yes' if review_packet_ready else 'no'}; "
                f"final_gate={'yes' if packet_gate['wetlab_final_gate_pass'] else 'no'}"
            ),
            "packet_ready_for_operator_review": review_packet_ready,
            "wetlab_gate_pass": packet_gate["wetlab_gate_pass"],
            "wetlab_final_gate_pass": packet_gate["wetlab_final_gate_pass"],
            "claim_gate_available": packet_gate["claim_gate_available"],
            "claim_ready_for_allatom": packet_gate["claim_ready_for_allatom"],
        },
    ]
    if operator_packet and template.operator_packet_artifact:
        rows.append(
            {
                "row_kind": template.step_row_kind,
                "step_id": template.operator_packet_step_id,
                "status": _text(operator_packet.get("status")),
                "artifact": template.operator_packet_artifact,
                "signal": _text(
                    operator_packet.get("packet_scope"),
                    f"{_safe_int(operator_packet.get('promoted_candidate_count'))} promoted",
                ),
                "packet_ready_for_operator_review": operator_gate.get("packet_ready_for_operator_review", False),
                "wetlab_gate_pass": operator_gate.get("wetlab_gate_pass", False),
                "wetlab_final_gate_pass": operator_gate.get("wetlab_final_gate_pass", False),
                "claim_gate_available": operator_gate.get("claim_gate_available", False),
                "claim_ready_for_allatom": operator_gate.get("claim_ready_for_allatom", False),
            }
        )
    rows.extend(
        [
            {
                "row_kind": template.step_row_kind,
                "step_id": "rescue_only_branch_runner",
                "status": _text(runner.get("status")),
                "artifact": template.branch_runner_artifact,
                "signal": _text(runner.get("branch_state"), runner.get("execution_mode")),
            },
            {
                "row_kind": template.step_row_kind,
                "step_id": template.three_bead_slice_step_id,
                "status": _text(slice_summary.get("status")),
                "artifact": template.three_bead_slice_artifact,
                "signal": _text(slice_summary.get("scoring_status"), slice_summary.get("execution_mode")),
            },
        ]
    )

    summary = {
        "status": template.summary_status,
        "target_id": target_id,
        "shard_id": shard_id,
        "branch_label": template.branch_label,
        "branch_state": branch_state,
        "default_lane_reopen_allowed": False,
        "branch_to_rescue_only": branch_to_rescue_only,
        "review_unit_label": template.review_unit_label,
        "selected_command_kind": _text(
            packet.get("selected_command_kind"),
            runner.get("selected_command_kind"),
            review.get("selected_command_kind"),
            template.default_selected_command_kind,
        ),
        "selected_threshold_A": _safe_float(
            packet.get("strict_threshold_A"),
            _safe_float(review.get("selected_threshold_A"), template.default_selected_threshold_a),
        ),
        "best_ligand_id": _text(packet.get("best_ligand_id")),
        "best_compound_name": _text(packet.get("best_compound_name"), packet.get("best_ligand_id")),
        "best_compound_name_human_readable": _text(packet.get("best_compound_name_human_readable")),
        "best_compound_name_resolution": _text(packet.get("best_compound_name_resolution"), default="unresolved"),
        "best_mean_min_distance_A": _safe_float(packet.get("best_mean_min_distance_A")),
        "runner_status": _text(runner.get("status")),
        "three_bead_scoring_status": _text(slice_summary.get("scoring_status")),
        "execution_mode": _text(runner.get("execution_mode"), slice_summary.get("execution_mode"), template.default_execution_mode),
        "review_packet_ready_for_operator_review": review_packet_ready,
        "review_packet_ready_source": packet_gate["packet_ready_for_operator_review_source"],
        "review_packet_wetlab_gate_pass": packet_gate["wetlab_gate_pass"],
        "review_packet_wetlab_gate_source": packet_gate["wetlab_gate_source"],
        "review_packet_wetlab_gate_reported": packet_gate["wetlab_gate_reported"],
        "review_packet_wetlab_gate_semantics": packet_gate["wetlab_gate_semantics"],
        "review_packet_wetlab_gate_legacy_fallback": _source_is_review_ready_only_fallback(packet_gate["wetlab_gate_source"]),
        "review_packet_final_gate_pass": packet_gate["wetlab_final_gate_pass"],
        "review_packet_final_gate_source": packet_gate["wetlab_final_gate_source"],
        "review_packet_final_gate_reported": packet_gate["wetlab_final_gate_reported"],
        "review_packet_final_gate_semantics": packet_gate["wetlab_final_gate_semantics"],
        "review_packet_final_gate_legacy_fallback": _source_is_review_ready_only_fallback(
            packet_gate["wetlab_final_gate_source"]
        ),
        "review_packet_claim_gate_available": packet_gate["claim_gate_available"],
        "review_packet_claim_gate_source": packet_gate["claim_gate_source"],
        "review_packet_claim_ready_for_allatom": packet_gate["claim_ready_for_allatom"],
        "review_packet_claim_ready_source": packet_gate["claim_ready_source"],
        "branch_ready_for_operator_review": branch_to_rescue_only and review_packet_ready,
        "branch_ready_for_final_wetlab": branch_to_rescue_only and packet_gate["wetlab_final_gate_pass"],
        "next_required_step": _branch_next_required_step(
            template,
            target_id,
            branch_to_rescue_only=branch_to_rescue_only,
            review_packet_ready=review_packet_ready,
            wetlab_final_gate_pass=packet_gate["wetlab_final_gate_pass"],
            wetlab_final_gate_source=packet_gate["wetlab_final_gate_source"],
        ),
    }
    if operator_packet and template.operator_packet_artifact:
        summary["operator_packet_ready"] = _operator_packet_ready(operator_packet, template)
        summary["operator_packet_ready_for_operator_review"] = operator_gate.get("packet_ready_for_operator_review", False)
        summary["operator_packet_ready_source"] = operator_gate.get("packet_ready_for_operator_review_source", "default")
        summary["operator_packet_wetlab_gate_pass"] = operator_gate.get("wetlab_gate_pass", False)
        summary["operator_packet_wetlab_gate_source"] = operator_gate.get("wetlab_gate_source", "default")
        summary["operator_packet_wetlab_gate_reported"] = operator_gate.get("wetlab_gate_reported", False)
        summary["operator_packet_wetlab_gate_semantics"] = operator_gate.get(
            "wetlab_gate_semantics",
            _gate_semantics(summary["operator_packet_wetlab_gate_source"], reported=False),
        )
        summary["operator_packet_final_gate_pass"] = operator_gate.get("wetlab_final_gate_pass", False)
        summary["operator_packet_final_gate_source"] = operator_gate.get("wetlab_final_gate_source", "default")
        summary["operator_packet_final_gate_reported"] = operator_gate.get("wetlab_final_gate_reported", False)
        summary["operator_packet_final_gate_semantics"] = operator_gate.get(
            "wetlab_final_gate_semantics",
            _gate_semantics(summary["operator_packet_final_gate_source"], reported=False),
        )
        summary["operator_packet_claim_gate_available"] = operator_gate.get("claim_gate_available", False)
        summary["operator_packet_claim_ready_for_allatom"] = operator_gate.get("claim_ready_for_allatom", False)
        summary["operator_packet_scope"] = _text(operator_packet.get("packet_scope"))
    _decorate_review_metrics(
        summary,
        template,
        review_packet_ready=review_packet_ready,
        review_packet_candidate_count=review_packet_candidate_count,
        strict_candidate_count=strict_candidate_count,
        near_candidate_count=near_candidate_count,
    )

    return {
        "summary": summary,
        "structured": {
            template.review_surface_structured_key: template.review_surface_artifact,
            template.review_packet_structured_key: template.review_packet_artifact,
            **(
                {template.operator_packet_structured_key: template.operator_packet_artifact}
                if template.operator_packet_artifact
                else {}
            ),
            template.branch_runner_structured_key: template.branch_runner_artifact,
            template.three_bead_slice_structured_key: template.three_bead_slice_artifact,
        },
        "rows": rows,
    }


def materialize_rescue_only_branch(
    template: RescueOnlyBranchTemplate,
    review_surface_payload: dict[str, Any],
    hard_target_rescue_runner_payload: dict[str, Any],
    three_bead_slice_payload: dict[str, Any],
    *,
    review_packet_builder: ReviewPacketBuilder,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    review_packet_payload = review_packet_builder(review_surface_payload, three_bead_slice_payload)
    branch_runner_payload = build_rescue_only_branch_runner_payload(
        template,
        review_packet_payload,
        hard_target_rescue_runner_payload,
        three_bead_slice_payload,
    )
    branch_summary_payload = build_rescue_only_branch_summary_payload(
        template,
        review_surface_payload,
        review_packet_payload,
        branch_runner_payload,
        three_bead_slice_payload,
    )
    return review_packet_payload, branch_runner_payload, branch_summary_payload


def run_rescue_only_branch(
    *,
    template: RescueOnlyBranchTemplate,
    review_packet_builder: ReviewPacketBuilder,
    review_surface_json: str,
    hard_target_rescue_runner_json: str,
    three_bead_slice_json: str,
    review_packet_md: str,
    branch_summary_md: str,
    out_md: str,
) -> dict[str, Any]:
    review_surface_payload = load_json(review_surface_json)
    hard_target_rescue_runner_payload = load_json(hard_target_rescue_runner_json)
    three_bead_slice_payload = load_json(three_bead_slice_json)

    review_packet_payload, branch_runner_payload, branch_summary_payload = materialize_rescue_only_branch(
        template,
        review_surface_payload,
        hard_target_rescue_runner_payload,
        three_bead_slice_payload,
        review_packet_builder=review_packet_builder,
    )

    write_artifact(review_packet_md, template.review_packet_title, review_packet_payload)
    write_artifact(out_md, template.branch_runner_title, branch_runner_payload)
    write_artifact(branch_summary_md, template.branch_summary_title, branch_summary_payload)
    return branch_runner_payload

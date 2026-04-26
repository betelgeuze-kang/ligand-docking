#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[1]

DEFAULT_BURNDOWN_JSON = "runs/wetlab_selected_allatom_gate_burndown_packet_current.json"
DEFAULT_REVIEW_JSON = "runs/wetlab_tcruzi_pde_allatom_review_packet_current.json"
DEFAULT_RESCUE_LANE_JSON = "runs/wetlab_tcruzi_pde_allatom_rescue_lane_current.json"
DEFAULT_OUT_JSON = "runs/wetlab_selected_allatom_repair_packet_current.json"
DEFAULT_OUT_CSV = "runs/wetlab_selected_allatom_repair_packet_current.csv"
DEFAULT_OUT_MD = "runs/wetlab_selected_allatom_repair_packet_current.md"
HARD_GATE_REPAIR_COMMAND = (
    "python3 tools/run_wetlab_tcruzi_pde_allatom_rescue.py "
    "--top-k 8 --filter-mode strict_then_near_fill --execute"
)
CLAIM_INPUT_BUILD_COMMAND = (
    "python3 tools/build_claim_inputs_from_openmm_manifest.py "
    "--manifest-csv <openmm_manifest.csv> --targets \"T. cruzi PDE\""
)
CLAIM_READINESS_COMMAND = (
    "python3 tools/run_allatom_claim_readiness.py "
    "--strict-summary-json <strict_summary.json> "
    "--accuracy-external-csv <accuracy_external.csv> "
    "--kinetics-input-csv <kinetics.csv> "
    "--thermo-input-csv <thermo.csv> "
    "--experiment-input-csv <experiment.csv> "
    "--enforce-complete-claim "
    "--out-json <claim_summary.json> --gate-out-json <gate.json>"
)
CLAIM_ATTACHED_REVIEW_COMMAND = (
    "python3 tools/build_wetlab_tcruzi_pde_allatom_review_packet.py "
    "--claim-readiness-json <claim_summary.json> --equivalence-gate-json <gate.json>"
)


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    if path.is_absolute():
        return path
    cwd_path = (Path.cwd() / path).resolve()
    if cwd_path.exists():
        return cwd_path
    return (ROOT / path).resolve()


def _load_json(path_like: str | Path) -> dict[str, Any]:
    with _resolve(path_like).open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _summary(payload: dict[str, Any]) -> dict[str, Any]:
    return dict(payload.get("summary", {}) or {})


def _text(value: Any, default: str = "") -> str:
    text = str(value or "").strip()
    return text or default


def _safe_float(value: Any) -> float | None:
    try:
        if value in {"", None, "missing"}:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _fmt_float(value: Any, digits: int = 3) -> str:
    parsed = _safe_float(value)
    if parsed is None:
        return "-"
    return f"{parsed:.{digits}f}"


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        if value in {"", None}:
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def _burndown_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    return [dict(row or {}) for row in (payload.get("rows", []) or [])]


def _first_row(rows: list[dict[str, Any]], code: str) -> dict[str, Any]:
    for row in rows:
        if _text(row.get("code")) == code:
            return dict(row)
    return {}


def _repair_phase(row: dict[str, Any]) -> str:
    code = _text(row.get("code"))
    severity = _text(row.get("severity"))
    category = _text(row.get("category"))
    if code == "defer_expensive_lane" or severity == "soft":
        return "deferred"
    if category == "claim_equivalence" or code in {"produce_claim_equivalence_packet", "resolve_claim_equivalence_gate"}:
        return "after_hard_gate"
    return "hard_gate_repair"


def _operator_action(row: dict[str, Any]) -> str:
    code = _text(row.get("code"))
    if code == "recompute_mean_min_distance_A":
        return "repair_pose_geometry_and_recompute_gate"
    if code == "recompute_claim_gate_required_unavailable":
        return "materialize_missing_claim_gate_metric"
    if code == "produce_claim_equivalence_packet":
        return "produce_claim_equivalence_packet_after_hard_gate"
    if code == "resolve_claim_equivalence_gate":
        return "resolve_claim_equivalence_gate_after_hard_gate"
    if code == "defer_expensive_lane":
        return "keep_expensive_lane_deferred"
    return _text(row.get("action"), default=code or "repair_selected_allatom_gate")


def _operator_instruction(row: dict[str, Any], *, target_id: str, recommended_lane_reason: str) -> str:
    code = _text(row.get("code"))
    if code == "recompute_mean_min_distance_A":
        return (
            f"Repair `{target_id}` selected all-atom pose geometry, rerun the pseudo-all-atom rescue scoring, "
            "and recompute `mean_min_distance_A` against the unchanged 2.500A strict gate."
        )
    if code == "recompute_claim_gate_required_unavailable":
        return (
            "Materialize the missing `claim_gate_required_unavailable` field from the selected all-atom focus, "
            "then rerun the commercial/final wetlab gate without changing pass state by hand."
        )
    if code == "produce_claim_equivalence_packet":
        return "Only after the hard gate clears, produce and attach the neglected-disease claim/equivalence packet."
    if code == "resolve_claim_equivalence_gate":
        return "Only after the claim/equivalence packet exists, rerun that gate and require explicit resolution before final wetlab readiness."
    if code == "defer_expensive_lane":
        return recommended_lane_reason or "Keep explicit-water rescoring and other expensive lanes deferred until hard gate repair succeeds."
    return _text(row.get("next_required_action"), default="Complete this repair row without pass override or threshold relaxation.")


def _repair_row(
    row: dict[str, Any],
    *,
    rank: int,
    target_id: str,
    recommended_lane_reason: str,
) -> dict[str, Any]:
    value = _text(row.get("value"))
    threshold = _text(row.get("threshold"))
    delta = _text(row.get("delta"))
    if not delta or delta == "-":
        value_num = _safe_float(value)
        threshold_num = _safe_float(threshold)
        if value_num is not None and threshold_num is not None:
            delta = _fmt_float(value_num - threshold_num)
        else:
            delta = "-"
    return {
        "repair_rank": rank,
        "execution_phase": _repair_phase(row),
        "severity": _text(row.get("severity")),
        "category": _text(row.get("category")),
        "repair_code": _text(row.get("code")),
        "operator_action": _operator_action(row),
        "source_status": _text(row.get("status")),
        "metric": _text(row.get("metric")),
        "value": value,
        "threshold": threshold,
        "delta": delta,
        "threshold_change_allowed": False,
        "manual_pass_promotion_allowed": False,
        "selected_allatom_pass_override_allowed": False,
        "delivery_ready_override_allowed": False,
        "reason": _text(row.get("reason")),
        "operator_instruction": _operator_instruction(
            row,
            target_id=target_id,
            recommended_lane_reason=recommended_lane_reason,
        ),
    }


def _command_plan(*, target_id: str, focus_artifact: str) -> list[dict[str, str]]:
    target_slug = "tcruzi_pde" if "cruzi" in target_id.lower() and "pde" in target_id.lower() else "selected_allatom"
    if target_slug == "tcruzi_pde":
        return [
            {
                "phase": "rescue_only_branch_build",
                "command": "python3 tools/run_wetlab_tcruzi_pde_rescue_only_branch.py",
                "purpose": "materialize the dedicated T. cruzi PDE rescue-only branch before selected all-atom repair",
                "manual_pass_promotion_allowed": "false",
            },
            {
                "phase": "rescue_only_branch_summary",
                "command": "python3 tools/build_wetlab_tcruzi_pde_rescue_only_branch_summary.py",
                "purpose": "refresh rescue-only branch summary inputs for the all-atom rescue lane",
                "manual_pass_promotion_allowed": "false",
            },
            {
                "phase": "allatom_rescue_lane_build",
                "command": "python3 tools/build_wetlab_tcruzi_pde_allatom_rescue_lane.py",
                "purpose": "build the pseudo-all-atom rescue lane from rescue-only branch inputs",
                "manual_pass_promotion_allowed": "false",
            },
            {
                "phase": "hard_gate_repair",
                "command": HARD_GATE_REPAIR_COMMAND,
                "purpose": "execute strict-then-near pseudo-all-atom rescue and recompute the unchanged hard gate",
                "manual_pass_promotion_allowed": "false",
            },
            {
                "phase": "hard_gate_review_refresh",
                "command": "python3 tools/build_wetlab_tcruzi_pde_allatom_review_packet.py",
                "purpose": f"rebuild selected all-atom review artifact `{focus_artifact}` from the hard-gate repair run",
                "manual_pass_promotion_allowed": "false",
            },
            {
                "phase": "claim_inputs_build_after_hard_gate",
                "command": CLAIM_INPUT_BUILD_COMMAND,
                "purpose": (
                    "after hard-gate closure, derive kinetics/thermo/experiment claim inputs from real OpenMM outputs; "
                    "placeholder or missing inputs remain blocked"
                ),
                "required_inputs": "<openmm_manifest.csv>",
                "blocked_if_missing": "true",
                "manual_pass_promotion_allowed": "false",
            },
            {
                "phase": "claim_readiness_after_hard_gate",
                "command": CLAIM_READINESS_COMMAND,
                "purpose": (
                    "after claim inputs exist, evaluate all-atom claim readiness and write both claim summary and gate JSON; "
                    "incomplete claim data remains blocked"
                ),
                "required_inputs": (
                    "<strict_summary.json>, <accuracy_external.csv>, <kinetics.csv>, "
                    "<thermo.csv>, <experiment.csv>"
                ),
                "blocked_if_missing": "true",
                "manual_pass_promotion_allowed": "false",
            },
            {
                "phase": "claim_attached_review_refresh",
                "command": CLAIM_ATTACHED_REVIEW_COMMAND,
                "purpose": (
                    "rebuild the selected all-atom review with explicit claim/equivalence evidence attached "
                    "before downstream final/queue/verdict refresh"
                ),
                "required_inputs": "<claim_summary.json>, <gate.json>",
                "blocked_if_missing": "true",
                "manual_pass_promotion_allowed": "false",
            },
            {
                "phase": "final_campaign_refresh",
                "command": "python3 tools/build_wetlab_final_campaign_summary.py",
                "purpose": "refresh the final campaign summary from the rebuilt selected all-atom state",
                "manual_pass_promotion_allowed": "false",
            },
            {
                "phase": "dashboard_refresh",
                "command": "python3 tools/build_wetlab_master_handoff_dashboard.py",
                "purpose": "refresh the master wetlab dashboard after final campaign summary rebuild",
                "manual_pass_promotion_allowed": "false",
            },
            {
                "phase": "burndown_refresh",
                "command": "python3 tools/build_wetlab_selected_allatom_gate_burndown_packet.py",
                "purpose": "refresh hard_block_count, missing_metric_count, and primary_burndown_code",
                "manual_pass_promotion_allowed": "false",
            },
            {
                "phase": "commercialization_queue_refresh",
                "command": "python3 tools/build_local_engine_commercialization_queue.py",
                "purpose": "refresh commercialization queue state from the repaired wetlab selected-allatom artifacts",
                "manual_pass_promotion_allowed": "false",
            },
            {
                "phase": "commercialization_status_refresh",
                "command": "python3 tools/build_commercialization_status_report.py",
                "purpose": "refresh commercialization status report without overriding any wetlab gate result",
                "manual_pass_promotion_allowed": "false",
            },
            {
                "phase": "delivery_verdict_refresh",
                "command": "python3 tools/build_local_delivery_verdict_gate.py",
                "purpose": "refresh the conservative local-delivery verdict gate after queue/status rebuilds",
                "manual_pass_promotion_allowed": "false",
            },
            {
                "phase": "closure_acceptance_check",
                "command": "confirm delivery_ready=true only from regenerated verdict outputs",
                "purpose": "accept closure only when regenerated verdict artifacts report no P0 blockers; do not infer pass from this repair packet",
                "manual_pass_promotion_allowed": "false",
            },
        ]
    return [
        {
            "phase": "hard_gate_repair",
            "command": "rerun selected all-atom pose repair and scoring lane",
            "purpose": "refresh mean_min_distance_A without relaxing the strict gate",
            "manual_pass_promotion_allowed": "false",
        }
    ]


def _hard_gate_command(command_plan: list[dict[str, str]]) -> str:
    for item in command_plan:
        if item.get("phase") == "hard_gate_repair":
            return _text(item.get("command"))
    return command_plan[0]["command"] if command_plan else ""


def build_payload(
    burndown_payload: dict[str, Any],
    review_payload: dict[str, Any],
    rescue_lane_payload: dict[str, Any],
) -> dict[str, Any]:
    burndown_summary = _summary(burndown_payload)
    review_summary = _summary(review_payload)
    rescue_summary = _summary(rescue_lane_payload)
    burndown_rows = _burndown_rows(burndown_payload)

    target_id = _text(burndown_summary.get("selected_allatom_target_id")) or _text(review_summary.get("target_id"))
    focus_artifact = _text(
        burndown_summary.get("selected_allatom_focus_artifact"),
        default="runs/wetlab_tcruzi_pde_allatom_review_packet_current.md",
    )
    primary_code = _text(burndown_summary.get("primary_burndown_code"), default="recompute_mean_min_distance_A")
    primary_row = _first_row(burndown_rows, primary_code) or (burndown_rows[0] if burndown_rows else {})
    primary_metric = _text(burndown_summary.get("primary_burndown_metric")) or _text(primary_row.get("metric"))
    primary_value = _text(burndown_summary.get("primary_burndown_value")) or _text(primary_row.get("value"))
    primary_threshold = _text(burndown_summary.get("primary_burndown_threshold")) or _text(primary_row.get("threshold"))
    primary_delta = _text(burndown_summary.get("primary_burndown_delta")) or _text(primary_row.get("delta"))
    if not primary_delta or primary_delta == "-":
        value_num = _safe_float(primary_value)
        threshold_num = _safe_float(primary_threshold)
        primary_delta = _fmt_float(value_num - threshold_num) if value_num is not None and threshold_num is not None else "-"

    recommended_lane = _text(review_summary.get("recommended_next_expensive_lane")) or _text(
        rescue_summary.get("recommended_next_expensive_lane")
    )
    recommended_lane_reason = _text(review_summary.get("recommended_next_expensive_lane_reason")) or _text(
        rescue_summary.get("recommended_next_expensive_lane_reason")
    )
    rows = [
        _repair_row(
            row,
            rank=idx,
            target_id=target_id or "selected all-atom focus",
            recommended_lane_reason=recommended_lane_reason,
        )
        for idx, row in enumerate(burndown_rows, start=1)
    ]
    hard_block_count = _safe_int(
        burndown_summary.get("hard_block_count"),
        sum(1 for row in rows if row["severity"] == "hard"),
    )
    missing_metric_count = _safe_int(
        burndown_summary.get("missing_metric_count"),
        sum(1 for row in rows if row["source_status"] == "missing"),
    )
    command_plan = _command_plan(target_id=target_id, focus_artifact=focus_artifact)
    recommended_command = _hard_gate_command(command_plan)
    hard_codes = [row["repair_code"] for row in rows if row["execution_phase"] == "hard_gate_repair"]
    after_hard_codes = [row["repair_code"] for row in rows if row["execution_phase"] == "after_hard_gate"]
    deferred_codes = [row["repair_code"] for row in rows if row["execution_phase"] == "deferred"]

    summary = {
        "repair_ready": bool(rows),
        "packet_artifact": DEFAULT_OUT_MD,
        "target_id": target_id,
        "selected_allatom_focus_artifact": focus_artifact,
        "supporting_packet_only": True,
        "repair_only_packet": True,
        "threshold_relaxation_allowed": False,
        "manual_pass_promotion_allowed": False,
        "delivery_ready_override_allowed": False,
        "selected_allatom_pass_override_allowed": False,
        "selected_allatom_wetlab_gate_pass": bool(burndown_summary.get("selected_allatom_wetlab_gate_pass", False)),
        "selected_allatom_final_gate_pass": bool(burndown_summary.get("selected_allatom_final_gate_pass", False)),
        "review_packet_wetlab_gate_pass": bool(review_summary.get("wetlab_gate_pass", False)),
        "review_packet_wetlab_final_gate_pass": bool(review_summary.get("wetlab_final_gate_pass", False)),
        "hard_block_count": hard_block_count,
        "missing_metric_count": missing_metric_count,
        "primary_repair_code": primary_code,
        "primary_metric": primary_metric,
        "primary_value": primary_value,
        "primary_threshold": primary_threshold,
        "primary_delta": primary_delta,
        "recommended_command": recommended_command,
        "command_plan": command_plan,
        "closure_plan": command_plan,
        "claim_equivalence_required_inputs": ["<claim_summary.json>", "<gate.json>"],
        "claim_equivalence_missing_inputs_pass": False,
        "claim_equivalence_plan_phases": [
            "claim_inputs_build_after_hard_gate",
            "claim_readiness_after_hard_gate",
            "claim_attached_review_refresh",
        ],
        "hard_gate_acceptance_metric": primary_metric or "mean_min_distance_A",
        "hard_gate_acceptance_operator": "<=",
        "hard_gate_acceptance_threshold": primary_threshold or "2.500",
        "hard_gate_acceptance_scope": "promoted selected all-atom review rows",
        "hard_gate_acceptance_manual_override_allowed": False,
        "closure_acceptance_requires": [
            "selected_allatom_wetlab_gate_pass=true",
            "selected_allatom_final_gate_pass=true",
            "hard_block_count=0",
            "semi_hard_block_count=0",
            "missing_metric_count=0",
            "commercialization_queue_clear=true",
            "delivery_ready=true",
            "p0_blocker_count=0",
        ],
        "hard_gate_repair_codes": hard_codes,
        "after_hard_gate_codes": after_hard_codes,
        "deferred_codes": deferred_codes,
        "recommended_next_expensive_lane": recommended_lane,
        "recommended_next_expensive_lane_reason": recommended_lane_reason,
        "claim_equivalence_after_hard_gate": bool(after_hard_codes),
        "expensive_lane_deferred": recommended_lane == "defer_expensive_lane" or "defer_expensive_lane" in deferred_codes,
        "source_burndown_packet": DEFAULT_BURNDOWN_JSON,
        "source_review_packet": DEFAULT_REVIEW_JSON,
        "source_rescue_lane_packet": DEFAULT_RESCUE_LANE_JSON,
        "next_required_step": (
            f"Execute repair `{primary_code}` for `{target_id or 'selected_allatom'}` with `{primary_metric}` currently "
            f"`{primary_value or '-'}` versus unchanged threshold `{primary_threshold or '-'}` (delta `{primary_delta or '-'}`); "
            "then recompute `claim_gate_required_unavailable`. Run claim/equivalence only after hard gate closure with "
            "`<claim_summary.json>` and `<gate.json>`; missing inputs stay blocked, not pass. Keep the expensive lane deferred."
        ),
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# Wetlab Selected All-Atom Repair Packet",
        "",
        f"- repair_ready: `{summary['repair_ready']}`",
        f"- supporting_packet_only: `{summary['supporting_packet_only']}`",
        f"- repair_only_packet: `{summary['repair_only_packet']}`",
        f"- delivery_ready_override_allowed: `{summary['delivery_ready_override_allowed']}`",
        f"- selected_allatom_pass_override_allowed: `{summary['selected_allatom_pass_override_allowed']}`",
        f"- threshold_relaxation_allowed: `{summary['threshold_relaxation_allowed']}`",
        f"- target_id: `{summary['target_id']}`",
        f"- selected_allatom_focus_artifact: `{summary['selected_allatom_focus_artifact']}`",
        f"- hard_block_count: `{summary['hard_block_count']}`",
        f"- missing_metric_count: `{summary['missing_metric_count']}`",
        f"- primary_repair_code: `{summary['primary_repair_code']}`",
        f"- primary_metric: `{summary['primary_metric']}`",
        f"- primary_value: `{summary['primary_value']}`",
        f"- primary_threshold: `{summary['primary_threshold']}`",
        f"- primary_delta: `{summary['primary_delta']}`",
        f"- recommended_command: `{summary['recommended_command']}`",
        f"- hard_gate_acceptance: `{summary['hard_gate_acceptance_metric']} {summary['hard_gate_acceptance_operator']} {summary['hard_gate_acceptance_threshold']}`",
        f"- hard_gate_acceptance_scope: `{summary['hard_gate_acceptance_scope']}`",
        f"- claim_equivalence_required_inputs: `{', '.join(summary['claim_equivalence_required_inputs'])}`",
        f"- claim_equivalence_missing_inputs_pass: `{summary['claim_equivalence_missing_inputs_pass']}`",
        "",
        "## Next Required Step",
        "",
        summary["next_required_step"],
        "",
        "## Command Plan",
        "",
    ]
    for item in summary["command_plan"]:
        suffix = ""
        if item.get("required_inputs"):
            suffix = f" Required inputs: `{item['required_inputs']}`."
        if item.get("blocked_if_missing") == "true":
            suffix += " Missing inputs remain blocked, not pass."
        lines.append(f"- `{item['phase']}`: `{item['command']}` - {item['purpose']}{suffix}")
    lines.extend(
        [
            "",
            "## Repair Rows",
            "",
            "| rank | phase | severity | repair_code | action | status | metric | value | threshold | delta |",
            "| ---: | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for row in payload["rows"]:
        lines.append(
            f"| {row['repair_rank']} | `{row['execution_phase']}` | `{row['severity']}` | `{row['repair_code']}` | "
            f"`{row['operator_action']}` | `{row['source_status']}` | `{row['metric'] or '-'}` | "
            f"`{row['value'] or '-'}` | `{row['threshold'] or '-'}` | `{row['delta']}` |"
        )
    lines.extend(["", "## Operator Instructions", ""])
    for row in payload["rows"]:
        lines.append(f"- `{row['repair_code']}`: {row['operator_instruction']}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the wetlab selected all-atom repair packet.")
    parser.add_argument("--burndown-json", default=DEFAULT_BURNDOWN_JSON)
    parser.add_argument("--review-json", default=DEFAULT_REVIEW_JSON)
    parser.add_argument("--rescue-lane-json", default=DEFAULT_RESCUE_LANE_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        burndown_payload=_load_json(args.burndown_json),
        review_payload=_load_json(args.review_json),
        rescue_lane_payload=_load_json(args.rescue_lane_json),
    )
    out_json = _resolve(args.out_json)
    out_csv = _resolve(args.out_csv)
    out_md = _resolve(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    write_csv_rows(out_csv, payload["rows"])
    _write_markdown(out_md, payload)


if __name__ == "__main__":
    main()

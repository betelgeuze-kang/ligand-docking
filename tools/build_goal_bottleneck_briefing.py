#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows
from tools.build_goal_operator_action_board import DEFAULT_OUT_JSON as DEFAULT_ACTION_BOARD_JSON
from tools.build_goal_operator_intake_kit import DEFAULT_OUT_JSON as DEFAULT_INTAKE_KIT_JSON
from tools.build_goal_release_burndown_work_order import DEFAULT_OUT_JSON as DEFAULT_BURNDOWN_JSON
from tools.build_goal_release_decision_gate import DEFAULT_OUT_JSON as DEFAULT_RELEASE_GATE_JSON

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PUBLIC_BENCHMARK_WORK_ORDER_JSON = "runs/product_public_benchmark_work_order_current.json"
DEFAULT_OUT_JSON = "runs/goal_bottleneck_briefing_current.json"
DEFAULT_OUT_CSV = "runs/goal_bottleneck_briefing_current.csv"
DEFAULT_OUT_MD = "runs/goal_bottleneck_briefing_current.md"

CLAIM_BOUNDARY = (
    "Goal bottleneck briefing only; it consolidates release blockers, burndown phases, operator intake templates, "
    "approval tokens, required inputs, and cleanup sizes from existing local artifacts. It does not approve tokens, "
    "fill intake files, run docking, install packages, submit CAMEO predictions, register servers, send email, delete, "
    "archive, externalize, upload, commit, push, or mutate external state."
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


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _summary(packet: dict[str, Any]) -> dict[str, Any]:
    summary = packet.get("summary")
    return summary if isinstance(summary, dict) else {}


def _rows(packet: dict[str, Any]) -> list[dict[str, Any]]:
    rows = packet.get("rows")
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def _text(value: Any) -> str:
    return str(value or "").strip()


def _int(value: Any) -> int:
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0


def _float(value: Any) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _split_semicolon(value: Any) -> list[str]:
    return [part.strip() for part in _text(value).split(";") if part.strip()]


def _unique(values: list[Any]) -> list[str]:
    output: list[str] = []
    seen: set[str] = set()
    for value in values:
        for part in _split_semicolon(value):
            if part in seen:
                continue
            seen.add(part)
            output.append(part)
    return output


def _join(values: list[Any]) -> str:
    return ";".join(_unique(values))


def _matches_release_checks(burndown_row: dict[str, Any], intake_row: dict[str, Any]) -> bool:
    burndown_checks = set(_split_semicolon(burndown_row.get("release_checks") or burndown_row.get("release_check")))
    intake_checks = set(_split_semicolon(intake_row.get("release_checks")))
    return bool(burndown_checks and intake_checks and burndown_checks & intake_checks)


def _matches_action(burndown_row: dict[str, Any], action_row: dict[str, Any], intake_rows: list[dict[str, Any]]) -> bool:
    action_artifacts = set(_split_semicolon(action_row.get("artifact_path")))
    source_artifacts = set(_split_semicolon(burndown_row.get("source_artifact")))
    if action_artifacts and source_artifacts and action_artifacts & source_artifacts:
        return True
    action_type = _text(action_row.get("action_type"))
    if not action_type:
        return False
    for intake in intake_rows:
        if not _matches_release_checks(burndown_row, intake):
            continue
        if action_type in set(_split_semicolon(intake.get("action_types"))):
            return True
    return False


def _filter_current_intake_rows(burndown_row: dict[str, Any], intake_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if _text(burndown_row.get("burndown_status")).startswith("blocked_until_"):
        return []
    burndown_tokens = set(_split_semicolon(burndown_row.get("approval_token_required")))
    intake_rows = [row for row in intake_rows if _text(row.get("kit_status")) != "not_surfaced"]
    if not burndown_tokens:
        return intake_rows
    filtered: list[dict[str, Any]] = []
    for row in intake_rows:
        intake_tokens = set(_split_semicolon(row.get("approval_token_required")))
        if not intake_tokens or burndown_tokens & intake_tokens:
            filtered.append(row)
    return filtered


def _bottleneck_kind(row: dict[str, Any]) -> str:
    status = _text(row.get("burndown_status"))
    if status == "official_results_required":
        return "official_cameo_results_missing"
    if status == "policy_decision_required":
        return "protected_payload_policy_decision"
    if status == "approval_required":
        return "operator_approval_required"
    if status == "operator_action_required":
        return "operator_action_board_not_clear"
    if status == "blocked_until_prior_phases_clear":
        return "dependent_refresh_after_prior_phases"
    if status == "operator_input_required":
        return "operator_input_required"
    return status or "unknown"


def _mutation_flags() -> dict[str, bool]:
    return {
        "execution_enabled": False,
        "action_executed": False,
        "delete_executed": False,
        "archive_executed": False,
        "externalize_executed": False,
        "upload_executed": False,
        "docking_results_emitted": False,
        "prediction_generation_enabled": False,
        "server_registration_mutated": False,
        "outbound_email_enabled": False,
        "external_state_mutated": False,
    }


def build_goal_bottleneck_briefing(
    *,
    release_gate_packet: dict[str, Any],
    burndown_packet: dict[str, Any],
    action_board_packet: dict[str, Any],
    intake_kit_packet: dict[str, Any],
    public_benchmark_work_order_packet: dict[str, Any] | None = None,
    release_gate_path: str = DEFAULT_RELEASE_GATE_JSON,
    burndown_path: str = DEFAULT_BURNDOWN_JSON,
    action_board_path: str = DEFAULT_ACTION_BOARD_JSON,
    intake_kit_path: str = DEFAULT_INTAKE_KIT_JSON,
    public_benchmark_work_order_path: str = DEFAULT_PUBLIC_BENCHMARK_WORK_ORDER_JSON,
) -> dict[str, Any]:
    release = _summary(release_gate_packet)
    burndown = _summary(burndown_packet)
    actions = _summary(action_board_packet)
    intake = _summary(intake_kit_packet)
    public_benchmark_work_order = _summary(public_benchmark_work_order_packet or {})
    burndown_rows = _rows(burndown_packet)
    action_rows = _rows(action_board_packet)
    intake_rows = _rows(intake_kit_packet)
    rows: list[dict[str, Any]] = []

    for burndown_row in sorted(burndown_rows, key=lambda row: _int(row.get("sequence"))):
        matched_intake = _filter_current_intake_rows(
            burndown_row,
            [row for row in intake_rows if _matches_release_checks(burndown_row, row)],
        )
        matched_actions = (
            []
            if _text(burndown_row.get("burndown_status")).startswith("blocked_until_")
            else [row for row in action_rows if _matches_action(burndown_row, row, matched_intake)]
        )
        approval_tokens = _unique(
            [burndown_row.get("approval_token_required")]
            + [row.get("approval_token_required") for row in matched_intake]
            + [row.get("approval_token") for row in matched_actions]
        )
        required_inputs = _unique(
            [row.get("required_input") for row in matched_actions]
            + [row.get("intake_path") for row in matched_intake if row.get("operator_input_required")]
        )
        source_artifacts = _unique(
            [burndown_row.get("source_artifact")]
            + [row.get("source_artifacts") for row in matched_intake]
            + [row.get("artifact_path") for row in matched_actions]
        )
        public_benchmark_blocked = _text(burndown_row.get("burndown_status")) == "blocked_until_public_benchmark_validation"
        if public_benchmark_blocked and public_benchmark_work_order_path not in source_artifacts:
            source_artifacts.append(public_benchmark_work_order_path)
        size_gb = round(sum(_float(row.get("size_gb")) for row in matched_actions), 3)
        if not size_gb:
            size_gb = round(_float(burndown_row.get("size_gb")), 3)
        row = {
            "bottleneck_id": f"P{_int(burndown_row.get('sequence')):02d}_{_text(burndown_row.get('phase')) or 'unknown'}",
            "sequence": _int(burndown_row.get("sequence")),
            "phase": _text(burndown_row.get("phase")),
            "lane_id": _text(burndown_row.get("lane_id")),
            "bottleneck_kind": _bottleneck_kind(burndown_row),
            "burndown_status": _text(burndown_row.get("burndown_status")),
            "release_checks": _text(burndown_row.get("release_checks") or burndown_row.get("release_check")),
            "release_observed": _text(burndown_row.get("release_observed")),
            "release_required": _text(burndown_row.get("release_required")),
            "release_check_count": _int(burndown_row.get("release_check_count")),
            "requires_operator_action": bool(burndown_row.get("requires_operator_action") is True),
            "approval_token_required": ";".join(approval_tokens),
            "approval_token_count": len(approval_tokens),
            "required_inputs": ";".join(required_inputs),
            "required_input_count": len(required_inputs),
            "operator_intake_entries": _join([row.get("kit_entry_id") for row in matched_intake]),
            "operator_intake_statuses": _join([row.get("kit_status") for row in matched_intake]),
            "operator_action_types": _join([row.get("action_type") for row in matched_actions]),
            "operator_action_statuses": _join([row.get("status") for row in matched_actions]),
            "operator_action_reasons": _join([row.get("reason") for row in matched_actions]),
            "operator_action_count": len(matched_actions),
            "source_artifacts": ";".join(source_artifacts),
            "source_artifact_count": len(source_artifacts),
            "command": _text(burndown_row.get("command")),
            "recommended_action": _text(burndown_row.get("recommended_action")),
            "public_benchmark_work_order_json": (public_benchmark_work_order_path if public_benchmark_blocked else ""),
            "public_benchmark_open_suite_count": (
                _int(public_benchmark_work_order.get("open_suite_count")) if public_benchmark_blocked else 0
            ),
            "public_benchmark_materialization_required_suite_count": (
                _int(public_benchmark_work_order.get("materialization_required_suite_count"))
                if public_benchmark_blocked
                else 0
            ),
            "public_benchmark_scorecard_required_suite_count": (
                _int(public_benchmark_work_order.get("scorecard_required_suite_count")) if public_benchmark_blocked else 0
            ),
            "size_gb": size_gb,
            **_mutation_flags(),
        }
        rows.append(row)

    status_counts: dict[str, int] = {}
    kind_counts: dict[str, int] = {}
    for row in rows:
        status_counts[row["burndown_status"]] = status_counts.get(row["burndown_status"], 0) + 1
        kind_counts[row["bottleneck_kind"]] = kind_counts.get(row["bottleneck_kind"], 0) + 1
    approval_tokens = _unique([row.get("approval_token_required") for row in rows])
    primary = rows[0] if rows else {}
    cleanup_objective_ready = bool(release.get("cleanup_objective_ready") is True) or bool(
        release.get("cleanup_completion_complete") is True
    )
    cleanup_transition_size_gb = 0.0 if cleanup_objective_ready else round(
        _float(release.get("cleanup_completion_transition_approval_gated_reclaim_size_gb")), 3
    )
    cleanup_ligand_size_gb = 0.0 if cleanup_objective_ready else round(
        _float(release.get("cleanup_completion_ligand_heavy_candidate_size_gb")), 3
    )
    summary = {
        "packet_type": "goal_bottleneck_briefing",
        "status": "goal_bottleneck_briefing_ready" if rows else "blocked_goal_bottleneck_briefing",
        "release_allowed": bool(release.get("release_allowed") is True),
        "source_release_gate_status": _text(release.get("status")),
        "source_release_blocker_count": _int(release.get("blocker_count")),
        "source_release_check_count": _int(release.get("check_count")),
        "source_burndown_status": _text(burndown.get("status")),
        "source_action_board_status": _text(actions.get("status")),
        "source_intake_kit_status": _text(intake.get("status")),
        "bottleneck_count": len(rows),
        "operator_action_required_bottleneck_count": sum(1 for row in rows if row["requires_operator_action"]),
        "approval_required_bottleneck_count": status_counts.get("approval_required", 0),
        "official_results_required_bottleneck_count": status_counts.get("official_results_required", 0),
        "policy_decision_required_bottleneck_count": status_counts.get("policy_decision_required", 0),
        "blocked_until_prior_phases_clear_count": status_counts.get("blocked_until_prior_phases_clear", 0),
        "approval_token_count": len(approval_tokens),
        "approval_tokens_required": approval_tokens,
        "approval_reclaim_size_gb": round(_float(actions.get("approval_reclaim_size_gb") or burndown.get("approval_reclaim_size_gb")), 3),
        "cleanup_transition_approval_gated_reclaim_size_gb": cleanup_transition_size_gb,
        "cleanup_ligand_heavy_candidate_size_gb": cleanup_ligand_size_gb,
        "protected_cleanup_payload_size_gb": round(_float(release.get("protected_cleanup_payload_size_gb")), 3),
        "operator_intake_kit_release_burndown_linked_entry_count": _int(
            intake.get("release_burndown_linked_entry_count")
        ),
        "public_benchmark_work_order_status": _text(public_benchmark_work_order.get("status")),
        "public_benchmark_work_order_json": public_benchmark_work_order_path,
        "public_benchmark_open_suite_count": _int(public_benchmark_work_order.get("open_suite_count")),
        "public_benchmark_materialization_required_suite_count": _int(
            public_benchmark_work_order.get("materialization_required_suite_count")
        ),
        "public_benchmark_scorecard_required_suite_count": _int(
            public_benchmark_work_order.get("scorecard_required_suite_count")
        ),
        "primary_bottleneck_sequence": _int(primary.get("sequence")),
        "primary_bottleneck_kind": _text(primary.get("bottleneck_kind")),
        "primary_bottleneck_phase": _text(primary.get("phase")),
        "source_release_gate_json": release_gate_path,
        "source_burndown_json": burndown_path,
        "source_action_board_json": action_board_path,
        "source_intake_kit_json": intake_kit_path,
        "status_counts": status_counts,
        "kind_counts": kind_counts,
        **_mutation_flags(),
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            (
                "Resolve bottlenecks in sequence: product benchmark scorecards/license, optional CAMEO live evidence, then refresh release evidence."
                if cleanup_objective_ready
                else "Resolve bottlenecks in sequence: product benchmark scorecards/license, optional CAMEO live evidence, cleanup approvals/policy, then refresh release evidence."
            )
        ),
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    s = payload["summary"]
    lines = [
        "# Goal Bottleneck Briefing",
        "",
        f"- status: `{s['status']}`",
        f"- release_allowed: `{s['release_allowed']}`",
        f"- source_release_blocker_count: `{s['source_release_blocker_count']}`",
        f"- bottleneck_count: `{s['bottleneck_count']}`",
        f"- approval_required_bottleneck_count: `{s['approval_required_bottleneck_count']}`",
        f"- official_results_required_bottleneck_count: `{s['official_results_required_bottleneck_count']}`",
        f"- policy_decision_required_bottleneck_count: `{s['policy_decision_required_bottleneck_count']}`",
        f"- approval_reclaim_size_gb: `{s['approval_reclaim_size_gb']}`",
        f"- cleanup_transition_approval_gated_reclaim_size_gb: `{s['cleanup_transition_approval_gated_reclaim_size_gb']}`",
        f"- cleanup_ligand_heavy_candidate_size_gb: `{s['cleanup_ligand_heavy_candidate_size_gb']}`",
        f"- protected_cleanup_payload_size_gb: `{s['protected_cleanup_payload_size_gb']}`",
        f"- approval_tokens_required: `{';'.join(s['approval_tokens_required'])}`",
        f"- public_benchmark_work_order_status: `{s['public_benchmark_work_order_status']}`",
        f"- public_benchmark_open_suite_count: `{s['public_benchmark_open_suite_count']}`",
        f"- public_benchmark_materialization_required_suite_count: `{s['public_benchmark_materialization_required_suite_count']}`",
        f"- public_benchmark_scorecard_required_suite_count: `{s['public_benchmark_scorecard_required_suite_count']}`",
        "",
        "## Bottlenecks",
        "",
        "| seq | phase | kind | status | tokens | inputs | size_gb | action |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['sequence']}` | `{row['phase']}` | `{row['bottleneck_kind']}` | "
            f"`{row['burndown_status']}` | `{row['approval_token_required']}` | "
            f"`{row['required_inputs']}` | `{row['size_gb']}` | {row['recommended_action']} |"
        )
    lines.extend(["", "## Claim Boundary", "", s["claim_boundary"], "", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a read-only briefing of current full-goal release bottlenecks.")
    parser.add_argument("--release-gate-json", default=DEFAULT_RELEASE_GATE_JSON)
    parser.add_argument("--burndown-json", default=DEFAULT_BURNDOWN_JSON)
    parser.add_argument("--action-board-json", default=DEFAULT_ACTION_BOARD_JSON)
    parser.add_argument("--intake-kit-json", default=DEFAULT_INTAKE_KIT_JSON)
    parser.add_argument("--public-benchmark-work-order-json", default=DEFAULT_PUBLIC_BENCHMARK_WORK_ORDER_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_goal_bottleneck_briefing(
        release_gate_packet=_read_json_if_present(args.release_gate_json),
        burndown_packet=_read_json_if_present(args.burndown_json),
        action_board_packet=_read_json_if_present(args.action_board_json),
        intake_kit_packet=_read_json_if_present(args.intake_kit_json),
        public_benchmark_work_order_packet=_read_json_if_present(args.public_benchmark_work_order_json),
        release_gate_path=args.release_gate_json,
        burndown_path=args.burndown_json,
        action_board_path=args.action_board_json,
        intake_kit_path=args.intake_kit_json,
        public_benchmark_work_order_path=args.public_benchmark_work_order_json,
    )
    _write_json(args.out_json, payload)
    write_csv_rows(_resolve(args.out_csv), payload["rows"])
    _write_markdown(args.out_md, payload)


if __name__ == "__main__":
    main()

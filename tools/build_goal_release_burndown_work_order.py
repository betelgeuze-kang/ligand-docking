#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RELEASE_GATE_JSON = "runs/goal_release_decision_gate_current.json"
DEFAULT_OPERATOR_ACTION_BOARD_JSON = "runs/goal_operator_action_board_current.json"
DEFAULT_PRODUCT_PREFLIGHT_JSON = "runs/product_execution_preflight_current.json"
DEFAULT_PRODUCT_GATE_REPAIR_JSON = "runs/product_operational_gate_repair_work_order_current.json"
DEFAULT_PRODUCT_WORK_ORDER_JSON = "runs/product_execution_work_order_current.json"
DEFAULT_PRODUCT_PILOT_JSON = "runs/product_pilot_packet_contract_current.json"
DEFAULT_PUBLIC_BENCHMARK_WORK_ORDER_JSON = "runs/product_public_benchmark_work_order_current.json"
DEFAULT_CAMEO_VALIDATION_REPAIR_JSON = "runs/cameo_validation_repair_work_order_current.json"
DEFAULT_CAMEO_RUNTIME_REPAIR_JSON = "runs/cameo_runtime_repair_work_order_current.json"
DEFAULT_CAMEO_CAPABILITY_JSON = "runs/cameo_capability_preflight_current.json"
DEFAULT_TRANSITION_CLEANUP_WORK_ORDER_JSON = "runs/transition_cleanup_work_order_current.json"
DEFAULT_LIGAND_CLEANUP_WORK_ORDER_JSON = "runs/ligand_heavy_cleanup_work_order_current.json"
DEFAULT_PROTECTED_CLEANUP_REVIEW_JSON = "runs/protected_cleanup_payload_review_current.json"
DEFAULT_CLEANUP_POSTCHECK_CONTRACT_JSON = "runs/cleanup_postcheck_contract_current.json"
DEFAULT_OUT_JSON = "runs/goal_release_burndown_work_order_current.json"
DEFAULT_OUT_CSV = "runs/goal_release_burndown_work_order_current.csv"
DEFAULT_OUT_MD = "runs/goal_release_burndown_work_order_current.md"

CLAIM_BOUNDARY = (
    "Goal release burndown work order only; it maps release gate blockers to existing operator-reviewed artifacts, "
    "approval tokens, and local refresh commands. It does not run docking, rebuild CAMEO artifacts, install packages, "
    "register a CAMEO server, submit predictions, send email, delete, archive, externalize, upload, commit, push, or "
    "mutate external state."
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
    return [row for row in packet.get("rows", []) or [] if isinstance(row, dict)]


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


def _first_command(packet: dict[str, Any], step: str = "") -> str:
    for row in _rows(packet):
        if step and _text(row.get("step")) != step:
            continue
        command = _text(row.get("command"))
        if command:
            return command
    return ""


def _first_approval_token(*packets: dict[str, Any]) -> str:
    for packet in packets:
        summary = _summary(packet)
        token = _text(summary.get("approval_token_required") or summary.get("registration_approval_token_required"))
        if token:
            return token
        for row in _rows(packet):
            token = _text(row.get("approval_token_required") or row.get("approval_token"))
            if token:
                return token
    return ""


def _join_tokens(*tokens: str) -> str:
    seen: set[str] = set()
    ordered: list[str] = []
    for token_group in tokens:
        for token in _split_tokens(token_group):
            if token not in seen:
                seen.add(token)
                ordered.append(token)
    return ";".join(ordered)


def _split_tokens(token_group: str) -> list[str]:
    return [token.strip() for token in _text(token_group).split(";") if token.strip()]


def _operator_action_token(packet: dict[str, Any], *, lane_id: str = "", action_type: str = "") -> str:
    for row in _rows(packet):
        if lane_id and _text(row.get("lane_id")) != lane_id:
            continue
        if action_type and _text(row.get("action_type")) != action_type:
            continue
        token = _text(row.get("approval_token_required") or row.get("approval_token"))
        if token:
            return token
    return ""


def _operator_action_artifact(packet: dict[str, Any], *, lane_id: str = "", action_type: str = "") -> str:
    for row in _rows(packet):
        if lane_id and _text(row.get("lane_id")) != lane_id:
            continue
        if action_type and _text(row.get("action_type")) != action_type:
            continue
        artifact = _text(row.get("artifact_path"))
        if artifact:
            return artifact
    return ""


def _row(
    *,
    sequence: int,
    phase: str,
    lane_id: str,
    release_check: str,
    release_observed: str,
    release_required: str,
    burndown_status: str,
    source_artifact: str,
    approval_token_required: str = "",
    recommended_action: str = "",
    command: str = "",
    reason: str = "",
) -> dict[str, Any]:
    return {
        "sequence": sequence,
        "phase": phase,
        "lane_id": lane_id,
        "release_check": release_check,
        "release_check_count": 1,
        "release_observed": release_observed,
        "release_required": release_required,
        "burndown_status": burndown_status,
        "source_artifact": source_artifact,
        "approval_token_required": approval_token_required,
        "recommended_action": recommended_action,
        "command": command,
        "reason": reason,
        "requires_operator_action": True,
        "execution_enabled": False,
        "action_executed": False,
        "delete_executed": False,
        "outbound_email_enabled": False,
        "external_state_mutated": False,
    }


def _merge_burndown_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    by_key: dict[tuple[str, str, str, str, str, str], dict[str, Any]] = {}
    for row in rows:
        key = (
            _text(row.get("phase")),
            _text(row.get("lane_id")),
            _text(row.get("burndown_status")),
            _text(row.get("approval_token_required")),
            _text(row.get("command")),
            _text(row.get("source_artifact")),
        )
        current = by_key.get(key)
        if current is None:
            clone = dict(row)
            clone["release_checks"] = _text(row.get("release_check"))
            check = _text(row.get("release_check"))
            clone["release_observed"] = f"{check}={_text(row.get('release_observed'))}" if check else _text(row.get("release_observed"))
            clone["release_required"] = f"{check}={_text(row.get('release_required'))}" if check else _text(row.get("release_required"))
            clone["reason"] = f"{check}: {_text(row.get('reason'))}" if check else _text(row.get("reason"))
            by_key[key] = clone
            merged.append(clone)
            continue
        check = _text(row.get("release_check"))
        current["release_check_count"] = _int(current.get("release_check_count")) + 1
        current["release_checks"] = ";".join(part for part in (_text(current.get("release_checks")), check) if part)
        current["release_check"] = current["release_checks"]
        current["release_observed"] = "; ".join(
            part
            for part in (
                _text(current.get("release_observed")),
                f"{check}={_text(row.get('release_observed'))}",
            )
            if part
        )
        current["release_required"] = "; ".join(
            part
            for part in (
                _text(current.get("release_required")),
                f"{check}={_text(row.get('release_required'))}",
            )
            if part
        )
        current["reason"] = "; ".join(
            part
            for part in (
                _text(current.get("reason")),
                f"{check}: {_text(row.get('reason'))}",
            )
            if part
        )
    for sequence, row in enumerate(merged, start=1):
        row["sequence"] = sequence
    return merged


def _next_required_step(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "Release burndown is clear; refresh the release decision gate before any completion claim."

    items: list[str] = []

    def add(item: str) -> None:
        if item not in items:
            items.append(item)

    for row in rows:
        phase = _text(row.get("phase"))
        status = _text(row.get("burndown_status"))
        token = _text(row.get("approval_token_required"))
        if phase == "P1_product_execution_and_bundle_validation":
            add("P1 product execution/bundle validation")
        elif phase == "P1_product_commercial_independence":
            add("P1 commercial license/independence")
        elif phase == "P2_cameo_official_validation_and_registration":
            if status == "official_results_required":
                add("P2 official CAMEO evidence")
            if "APPROVE_API_DEPENDENCY_INSTALL" in token:
                add("P2 CAMEO runtime repair")
            elif token:
                add("P2 CAMEO registration/email approval")
        elif phase == "P3_cleanup_execution_or_policy_resolution":
            add("P3 cleanup completion/policy/postcheck")
        elif phase == "P4_refresh_release_evidence":
            add("P4 release evidence refresh")

    if "P4 release evidence refresh" in items:
        return f"Burn down {', '.join(items)}."
    return f"Burn down {', '.join(items)}, then refresh release evidence."


def _product_burndown_row(
    *,
    sequence: int,
    release_row: dict[str, Any],
    product_preflight: dict[str, Any],
    product_gate_repair: dict[str, Any],
    product_work_order: dict[str, Any],
    product_pilot_packet: dict[str, Any],
    product_preflight_path: str,
    product_gate_repair_path: str,
    product_work_order_path: str,
    product_pilot_path: str,
    public_benchmark_work_order_path: str,
) -> dict[str, Any]:
    preflight = _summary(product_preflight)
    pilot = _summary(product_pilot_packet)
    preflight_status = _text(preflight.get("status"))
    preflight_ready = (not preflight_status) or preflight_status == "product_execution_preflight_ready"
    pilot_delivery_ready = bool(pilot.get("pilot_delivery_ready") is True)
    token = _first_approval_token(product_work_order) if preflight_ready else ""
    preflight_gate_status = _text(preflight.get("operational_gate_feasibility_status"))
    preflight_blocker_count = _int(preflight.get("blocker_count"))
    gate_repair = _summary(product_gate_repair)
    gate_repair_required = bool(gate_repair.get("repair_required") is True)
    additional_eval_needed = _int(gate_repair.get("additional_eval_unique_keys_needed"))
    additional_negative_needed = _int(gate_repair.get("additional_negative_keys_needed"))
    required_negative_at_gate_min = _int(gate_repair.get("required_negative_keys_at_gate_min"))
    gate_min_eval = _int(gate_repair.get("gate_min_eval_unique_keys"))
    source_artifact = f"{product_work_order_path};{product_pilot_path}"
    burndown_status = "approval_required"
    recommended_action = "Review and approve product execution, then assemble and validate the product local-delivery bundle before refreshing pilot evidence."
    command = _first_command(product_work_order, "execution") or _first_command(product_work_order)
    reason = _text(release_row.get("reason"))
    if (
        preflight_ready
        and pilot_delivery_ready
        and _text(release_row.get("check")) == "product_architecture_release_ready"
    ):
        token = ""
        burndown_status = "blocked_until_public_benchmark_validation"
        recommended_action = (
            "Product docking execution, bundle assembly, and pilot delivery evidence are ready; run and attach the "
            "required public benchmark scorecards before treating the architecture contract as release-ready."
        )
        command = (
            "python3 tools/build_product_public_benchmark_work_order.py && "
            "python3 tools/build_product_public_benchmark_contract.py && "
            "python3 tools/build_product_architecture_contract.py && python3 tools/build_goal_release_decision_gate.py && "
            "python3 tools/build_goal_release_burndown_work_order.py"
        )
        source_artifact = f"{source_artifact};{public_benchmark_work_order_path}"
        reason = f"{reason}; product_pilot_delivery_ready=True, product_execution_no_longer_blocks_this_check=True"
    if not preflight_ready:
        source_artifact = f"{product_preflight_path};{product_gate_repair_path};{source_artifact}" if gate_repair else f"{product_preflight_path};{source_artifact}"
        burndown_status = "operator_action_required"
        recommended_action = (
            (
                f"Repair the product operational eval panel to at least {gate_min_eval} unique eval keys with at least "
                f"{required_negative_at_gate_min} negative/decoy keys ({additional_eval_needed} total eval additions, "
                f"{additional_negative_needed} more negative/decoy keys), then rebuild preflight, approval gate, product "
                "release dossier, and goal burndown."
            )
            if gate_repair_required
            else (
                "Repair product execution preflight before approval: align operational gate thresholds with the eval split "
                "or switch to a validation dataset that can satisfy the configured gate; then rebuild preflight, approval gate, "
                "product release dossier, and goal burndown."
            )
        )
        command = (
            "python3 tools/build_product_execution_preflight.py && "
            "python3 tools/build_product_operational_gate_repair_work_order.py && "
            "python3 tools/build_product_execution_approval_gate.py && python3 tools/build_product_release_operations_dossier.py && "
            "python3 tools/build_goal_release_decision_gate.py && python3 tools/build_goal_release_burndown_work_order.py"
        )
        reason = (
            f"{reason}; product_execution_preflight_status={preflight_status or 'missing'}, "
            f"preflight_blocker_count={preflight_blocker_count}, "
            f"operational_gate_feasibility_status={preflight_gate_status or 'not_checked'}, "
            f"gate_repair_required={gate_repair_required}, additional_eval_unique_keys_needed={additional_eval_needed}, "
            f"additional_negative_keys_needed={additional_negative_needed}"
        )
    return _row(
        sequence=sequence,
        phase="P1_product_execution_and_bundle_validation",
        lane_id=_text(release_row.get("lane_id")),
        release_check=_text(release_row.get("check")),
        release_observed=_text(release_row.get("observed")),
        release_required=_text(release_row.get("required")),
        burndown_status=burndown_status,
        source_artifact=source_artifact,
        approval_token_required=token,
        recommended_action=recommended_action,
        command=command,
        reason=reason,
    )


def _product_independence_burndown_row(
    *,
    sequence: int,
    release_row: dict[str, Any],
    operator_action_board: dict[str, Any],
    operator_action_board_path: str,
) -> dict[str, Any]:
    artifact = _text(release_row.get("artifact_path")) or "runs/product_commercial_independence_gate_current.json"
    token = _operator_action_token(
        operator_action_board,
        lane_id="commercial_product_license",
        action_type="fill_product_license_decision",
    )
    return _row(
        sequence=sequence,
        phase="P1_product_commercial_independence",
        lane_id=_text(release_row.get("lane_id")),
        release_check=_text(release_row.get("check")),
        release_observed=_text(release_row.get("observed")),
        release_required=_text(release_row.get("required")),
        burndown_status="approval_required" if token else "implementation_required",
        source_artifact=f"{artifact};{operator_action_board_path}" if token else artifact,
        approval_token_required=token,
        recommended_action=(
            "Fill the product license decision operator intake with the exact approval token, SPDX/source, holder, "
            "and year before any LICENSE file creation review; then rebuild the license, commercial-independence, "
            "product release, and goal release gates."
            if token
            else "Resolve commercial-independence blockers: add license evidence, pin core runtime dependencies, "
            "move external API SDKs out of requirements.txt, then rebuild the commercial-independence and release gates."
        ),
        command=(
            "python3 tools/build_product_license_decision_gate.py && python3 tools/build_product_commercial_independence_gate.py && "
            "python3 tools/build_product_release_operations_dossier.py && python3 tools/build_goal_release_decision_gate.py && "
            "python3 tools/build_goal_release_burndown_work_order.py"
            if token
            else "python3 tools/build_product_commercial_independence_gate.py && python3 tools/build_goal_release_decision_gate.py && python3 tools/build_goal_release_burndown_work_order.py"
        ),
        reason=_text(release_row.get("reason")),
    )


def _cameo_burndown_row(
    *,
    sequence: int,
    release_row: dict[str, Any],
    validation_repair: dict[str, Any],
    runtime_repair: dict[str, Any],
    capability: dict[str, Any],
    validation_repair_path: str,
    runtime_repair_path: str,
    capability_path: str,
    operator_action_board: dict[str, Any],
    operator_action_board_path: str,
) -> dict[str, Any]:
    check = _text(release_row.get("check"))
    if check == "cameo_public_registration_allowed":
        operator_actions = _summary(operator_action_board)
        receiver_status = _text(operator_actions.get("cameo_cli_receiver_smoke_status"))
        api_install_required = bool(operator_actions.get("cameo_cli_api_install_approval_required") is True)
        runtime_repair_required = api_install_required or bool(receiver_status and receiver_status != "cameo_receiver_smoke_ready")
        capability_summary = _summary(capability)
        if runtime_repair_required:
            token = _first_approval_token(runtime_repair)
            command = _first_command(runtime_repair, "install_or_activate_api_dependency_profile") or _first_command(runtime_repair)
            action = (
                "Repair API dependency and receiver smoke first; only after validation evidence is ready, review "
                "CAMEO registration and outbound-email approval tokens."
            )
        else:
            token = _join_tokens(
                _text(capability_summary.get("registration_approval_token_required")),
                _text(capability_summary.get("outbound_email_approval_token_required")),
            )
            command = ""
            action = "Review CAMEO registration and outbound-email approval only after official validation evidence is ready."
        status = "approval_required"
        source_artifact = f"{validation_repair_path};{runtime_repair_path};{capability_path}"
    elif check == "official_cameo_results_used":
        token = ""
        command = (
            "python3 tools/build_cameo_official_results_intake_gate.py && "
            "python3 tools/build_cameo_performance_scorecard.py --results-csv runs/cameo_official_results_operator_intake.csv && "
            "python3 tools/build_cameo_validation_readiness_gate.py"
        )
        action = (
            "Fill official CAMEO assessment rows, validate the official-results intake gate, rebuild the performance "
            "scorecard with official metrics, then refresh CAMEO validation readiness."
        )
        status = "official_results_required"
        source_artifact = (
            _operator_action_artifact(
                operator_action_board,
                lane_id="cameo_validation",
                action_type="fill_cameo_official_results_intake",
            )
            or f"{validation_repair_path};{operator_action_board_path}"
        )
    else:
        token = ""
        command = (
            "python3 tools/build_cameo_official_results_intake_gate.py && "
            "python3 tools/build_cameo_performance_scorecard.py --results-csv runs/cameo_official_results_operator_intake.csv && "
            "python3 tools/build_cameo_validation_readiness_gate.py"
        )
        action = (
            "Current local CAMEO selection/format/handoff stages are ready; attach official CAMEO result rows and "
            "refresh the performance/readiness artifacts before claiming architecture validation."
        )
        status = "official_results_required"
        source_artifact = (
            _operator_action_artifact(
                operator_action_board,
                lane_id="cameo_validation",
                action_type="fill_cameo_official_results_intake",
            )
            or f"{validation_repair_path};{operator_action_board_path}"
        )
    return _row(
        sequence=sequence,
        phase="P2_cameo_official_validation_and_registration",
        lane_id=_text(release_row.get("lane_id")),
        release_check=check,
        release_observed=_text(release_row.get("observed")),
        release_required=_text(release_row.get("required")),
        burndown_status=status,
        source_artifact=source_artifact,
        approval_token_required=token,
        recommended_action=action,
        command=command,
        reason=_text(release_row.get("reason")),
    )


def _cleanup_burndown_row(
    *,
    sequence: int,
    release_row: dict[str, Any],
    operator_action_board: dict[str, Any],
    transition_cleanup: dict[str, Any],
    ligand_cleanup: dict[str, Any],
    protected_cleanup: dict[str, Any],
    cleanup_postcheck: dict[str, Any],
    operator_action_board_path: str,
    transition_cleanup_path: str,
    ligand_cleanup_path: str,
    protected_cleanup_path: str,
    cleanup_postcheck_path: str,
) -> dict[str, Any]:
    check = _text(release_row.get("check"))
    if check == "transition_cleanup_complete":
        token = _first_approval_token(transition_cleanup)
        source = transition_cleanup_path
        command = ""
        action = "Review row-specific transition cleanup approvals, snapshot payloads, then execute only the approved archive/externalize/delete rows."
        status = "approval_required"
    elif check == "ligand_heavy_cleanup_complete":
        token = _first_approval_token(ligand_cleanup)
        source = ligand_cleanup_path
        command = _first_command(ligand_cleanup, "execute_after_approval")
        action = "Review stale ligand-heavy trajectory payload candidates, then execute the cleanup command only after explicit approval."
        status = "approval_required"
    elif check == "protected_cleanup_policy_resolved":
        token = ""
        source = protected_cleanup_path
        command = ""
        action = "Keep protected payload rows out of deletion or record an explicit cleanup-policy change before promoting them."
        status = "policy_decision_required"
    elif check == "cleanup_postcheck_contract_ready":
        token = ""
        source = cleanup_postcheck_path
        command = (
            "python3 tools/build_cleanup_postcheck_contract.py && "
            "python3 tools/build_cleanup_operations_surface_contract.py && "
            "python3 tools/build_goal_readiness_rollup.py && "
            "python3 tools/build_goal_operator_action_board.py && "
            "python3 tools/build_goal_release_decision_gate.py && "
            "python3 tools/build_goal_release_burndown_work_order.py"
        )
        action = "Refresh the cleanup postcheck contract and goal-level release evidence before any cleanup completion claim."
        status = "postcheck_required"
    else:
        token = ""
        source = operator_action_board_path
        command = ""
        action = "Clear all priority operator action board rows before release; product, CAMEO, and cleanup actions remain open."
        status = "operator_action_required"
    return _row(
        sequence=sequence,
        phase="P3_cleanup_execution_or_policy_resolution",
        lane_id=_text(release_row.get("lane_id")),
        release_check=check,
        release_observed=_text(release_row.get("observed")),
        release_required=_text(release_row.get("required")),
        burndown_status=status,
        source_artifact=source,
        approval_token_required=token,
        recommended_action=action,
        command=command,
        reason=_text(release_row.get("reason")),
    )


def _goal_burndown_row(
    *,
    sequence: int,
    release_row: dict[str, Any],
    release_gate_path: str,
    operator_action_board_path: str,
) -> dict[str, Any]:
    if _text(release_row.get("check")) == "goal_api_surface_contract_ready":
        return _row(
            sequence=sequence,
            phase="P4_refresh_release_evidence",
            lane_id=_text(release_row.get("lane_id")),
            release_check=_text(release_row.get("check")),
            release_observed=_text(release_row.get("observed")),
            release_required=_text(release_row.get("required")),
            burndown_status="api_contract_refresh_required",
            source_artifact=f"{release_gate_path};runs/goal_api_surface_contract_current.json",
            recommended_action="Refresh the static goal API surface contract, then rebuild the release gate and burndown work order.",
            command="python3 tools/build_goal_api_surface_contract.py && python3 tools/build_goal_release_decision_gate.py && python3 tools/build_goal_release_burndown_work_order.py",
            reason=_text(release_row.get("reason")),
        )
    return _row(
        sequence=sequence,
        phase="P4_refresh_release_evidence",
        lane_id=_text(release_row.get("lane_id")),
        release_check=_text(release_row.get("check")),
        release_observed=_text(release_row.get("observed")),
        release_required=_text(release_row.get("required")),
        burndown_status="blocked_until_prior_phases_clear",
        source_artifact=f"{release_gate_path};{operator_action_board_path}",
        recommended_action="After prior blocking phases are cleared, refresh goal rollup, action board, release gate, and this burndown work order.",
        command="python3 tools/build_goal_readiness_rollup.py && python3 tools/build_goal_operator_action_board.py && python3 tools/build_goal_release_decision_gate.py && python3 tools/build_goal_release_burndown_work_order.py",
        reason=_text(release_row.get("reason")),
    )


def build_goal_release_burndown_work_order(
    *,
    release_gate_packet: dict[str, Any],
    operator_action_board_packet: dict[str, Any],
    product_work_order_packet: dict[str, Any],
    product_pilot_packet: dict[str, Any],
    cameo_validation_repair_packet: dict[str, Any],
    cameo_runtime_repair_packet: dict[str, Any],
    cameo_capability_packet: dict[str, Any],
    transition_cleanup_work_order_packet: dict[str, Any],
    ligand_cleanup_work_order_packet: dict[str, Any],
    protected_cleanup_review_packet: dict[str, Any],
    cleanup_postcheck_contract_packet: dict[str, Any] | None = None,
    product_preflight_packet: dict[str, Any] | None = None,
    product_gate_repair_packet: dict[str, Any] | None = None,
    release_gate_path: str = DEFAULT_RELEASE_GATE_JSON,
    operator_action_board_path: str = DEFAULT_OPERATOR_ACTION_BOARD_JSON,
    product_preflight_path: str = DEFAULT_PRODUCT_PREFLIGHT_JSON,
    product_gate_repair_path: str = DEFAULT_PRODUCT_GATE_REPAIR_JSON,
    product_work_order_path: str = DEFAULT_PRODUCT_WORK_ORDER_JSON,
    product_pilot_path: str = DEFAULT_PRODUCT_PILOT_JSON,
    public_benchmark_work_order_path: str = DEFAULT_PUBLIC_BENCHMARK_WORK_ORDER_JSON,
    cameo_validation_repair_path: str = DEFAULT_CAMEO_VALIDATION_REPAIR_JSON,
    cameo_runtime_repair_path: str = DEFAULT_CAMEO_RUNTIME_REPAIR_JSON,
    cameo_capability_path: str = DEFAULT_CAMEO_CAPABILITY_JSON,
    transition_cleanup_work_order_path: str = DEFAULT_TRANSITION_CLEANUP_WORK_ORDER_JSON,
    ligand_cleanup_work_order_path: str = DEFAULT_LIGAND_CLEANUP_WORK_ORDER_JSON,
    protected_cleanup_review_path: str = DEFAULT_PROTECTED_CLEANUP_REVIEW_JSON,
    cleanup_postcheck_contract_path: str = DEFAULT_CLEANUP_POSTCHECK_CONTRACT_JSON,
) -> dict[str, Any]:
    release_summary = _summary(release_gate_packet)
    rows: list[dict[str, Any]] = []
    blockers = [row for row in _rows(release_gate_packet) if row.get("release_blocker") is True]

    for sequence, release_row in enumerate(blockers, start=1):
        lane = _text(release_row.get("lane_id"))
        if lane == "commercial_product_release":
            if _text(release_row.get("check")) == "commercial_independence_gate_ready":
                rows.append(
                    _product_independence_burndown_row(
                        sequence=sequence,
                        release_row=release_row,
                        operator_action_board=operator_action_board_packet,
                        operator_action_board_path=operator_action_board_path,
                    )
                )
            else:
                rows.append(
                    _product_burndown_row(
                        sequence=sequence,
                        release_row=release_row,
                        product_preflight=product_preflight_packet or {},
                        product_gate_repair=product_gate_repair_packet or {},
                        product_work_order=product_work_order_packet,
                        product_pilot_packet=product_pilot_packet,
                        product_preflight_path=product_preflight_path,
                        product_gate_repair_path=product_gate_repair_path,
                        product_work_order_path=product_work_order_path,
                        product_pilot_path=product_pilot_path,
                        public_benchmark_work_order_path=public_benchmark_work_order_path,
                    )
                )
        elif lane == "cameo_architecture_validation":
            rows.append(
                _cameo_burndown_row(
                    sequence=sequence,
                    release_row=release_row,
                    validation_repair=cameo_validation_repair_packet,
                    runtime_repair=cameo_runtime_repair_packet,
                    capability=cameo_capability_packet,
                    validation_repair_path=cameo_validation_repair_path,
                    runtime_repair_path=cameo_runtime_repair_path,
                    capability_path=cameo_capability_path,
                    operator_action_board=operator_action_board_packet,
                    operator_action_board_path=operator_action_board_path,
                )
            )
        elif lane == "cleanup_release":
            rows.append(
                _cleanup_burndown_row(
                    sequence=sequence,
                    release_row=release_row,
                    operator_action_board=operator_action_board_packet,
                    transition_cleanup=transition_cleanup_work_order_packet,
                    ligand_cleanup=ligand_cleanup_work_order_packet,
                    protected_cleanup=protected_cleanup_review_packet,
                    cleanup_postcheck=cleanup_postcheck_contract_packet or {},
                    operator_action_board_path=operator_action_board_path,
                    transition_cleanup_path=transition_cleanup_work_order_path,
                    ligand_cleanup_path=ligand_cleanup_work_order_path,
                    protected_cleanup_path=protected_cleanup_review_path,
                    cleanup_postcheck_path=cleanup_postcheck_contract_path,
                )
            )
        else:
            rows.append(
                _goal_burndown_row(
                    sequence=sequence,
                    release_row=release_row,
                    release_gate_path=release_gate_path,
                    operator_action_board_path=operator_action_board_path,
                )
            )

    raw_row_count = len(rows)
    rows = _merge_burndown_rows(rows)
    approval_tokens = sorted(
        {
            token
            for row in rows
            for token in _split_tokens(_text(row.get("approval_token_required")))
        }
    )
    operator_actions = _summary(operator_action_board_packet)
    burndown_operator_input_required_work_item_count = sum(
        1 for row in rows if row.get("burndown_status") == "operator_input_required"
    )
    intake_current_action_required_count = _int(operator_actions.get("goal_operator_intake_kit_current_action_required_count"))
    summary = {
        "packet_type": "goal_release_burndown_work_order",
        "status": "goal_release_burndown_clear" if not rows else "goal_release_burndown_work_order_ready",
        "source_release_gate_status": _text(release_summary.get("status")),
        "source_release_allowed": bool(release_summary.get("release_allowed") is True),
        "source_release_blocker_count": _int(release_summary.get("blocker_count")),
        "release_blocker_check_count": raw_row_count,
        "work_item_count": len(rows),
        "approval_required_item_count": sum(1 for row in rows if _text(row.get("approval_token_required"))),
        "operator_input_required_item_count": intake_current_action_required_count
        or burndown_operator_input_required_work_item_count,
        "burndown_operator_input_required_work_item_count": burndown_operator_input_required_work_item_count,
        "official_results_required_item_count": sum(1 for row in rows if row.get("burndown_status") == "official_results_required"),
        "policy_decision_required_item_count": sum(1 for row in rows if row.get("burndown_status") == "policy_decision_required"),
        "postcheck_required_item_count": sum(1 for row in rows if row.get("burndown_status") == "postcheck_required"),
        "approval_tokens_required": approval_tokens,
        "approval_token_count": len(approval_tokens),
        "operator_action_count": _int(operator_actions.get("action_count")),
        "goal_operator_intake_kit_status": _text(operator_actions.get("goal_operator_intake_kit_status")),
        "goal_operator_intake_kit_json": _text(operator_actions.get("goal_operator_intake_kit_json")),
        "goal_operator_intake_kit_operator_input_required_count": _int(
            operator_actions.get("goal_operator_intake_kit_operator_input_required_count")
        ),
        "goal_operator_intake_kit_release_burndown_linked_entry_count": _int(
            operator_actions.get("goal_operator_intake_kit_release_burndown_linked_entry_count")
        ),
        "goal_operator_intake_kit_current_action_required_count": intake_current_action_required_count,
        "goal_operator_intake_kit_deferred_operator_input_count": _int(
            operator_actions.get("goal_operator_intake_kit_deferred_operator_input_count")
        ),
        "goal_operator_intake_kit_approval_token_count": _int(
            operator_actions.get("goal_operator_intake_kit_approval_token_count")
        ),
        "goal_operator_intake_kit_current_action_approval_token_count": _int(
            operator_actions.get("goal_operator_intake_kit_current_action_approval_token_count")
        ),
        "goal_operator_intake_kit_current_action_approval_tokens": operator_actions.get(
            "goal_operator_intake_kit_current_action_approval_tokens"
        )
        or [],
        "approval_reclaim_size_gb": round(_float(operator_actions.get("approval_reclaim_size_gb")), 3),
        "product_cli_status_set_status": _text(operator_actions.get("product_cli_status_set_status")),
        "product_cli_approval_token_count": _int(operator_actions.get("product_cli_approval_token_count")),
        "product_cli_operations_blocked_stage_count": _int(operator_actions.get("product_cli_operations_blocked_stage_count")),
        "product_cli_operational_quality_ready": bool(operator_actions.get("product_cli_operational_quality_ready") is True),
        "product_operational_quality_ready": bool(
            operator_actions.get("product_cli_operational_quality_ready") is True
            or operator_actions.get("product_release_operations_operational_quality_ready") is True
        ),
        "product_operational_quality_status": _text(
            operator_actions.get("product_release_operations_source_operational_quality_status")
        ),
        "product_operational_quality_blocker_count": _int(
            operator_actions.get("product_release_operations_operational_quality_blocker_count")
        ),
        "product_cli_authorized_for_execution": bool(operator_actions.get("product_cli_authorized_for_execution") is True),
        "product_cli_bundle_validation_passed": bool(operator_actions.get("product_cli_bundle_validation_passed") is True),
        "product_cli_delivery_ready_claim_allowed": bool(operator_actions.get("product_cli_delivery_ready_claim_allowed") is True),
        "product_gate_repair_status": _text(_summary(product_gate_repair_packet or {}).get("status")),
        "product_gate_repair_required": bool(_summary(product_gate_repair_packet or {}).get("repair_required") is True),
        "product_gate_repair_additional_eval_unique_keys_needed": _int(
            _summary(product_gate_repair_packet or {}).get("additional_eval_unique_keys_needed")
        ),
        "product_gate_repair_additional_negative_keys_needed": _int(
            _summary(product_gate_repair_packet or {}).get("additional_negative_keys_needed")
        ),
        "cameo_cli_status_set_status": _text(operator_actions.get("cameo_cli_status_set_status")),
        "cameo_cli_approval_token_count": _int(operator_actions.get("cameo_cli_approval_token_count")),
        "cameo_cli_official_result_required": bool(operator_actions.get("cameo_cli_official_result_required") is True),
        "cameo_cli_evidence_integrity_ready": bool(operator_actions.get("cameo_cli_evidence_integrity_ready") is True),
        "cameo_evidence_integrity_ready": bool(
            operator_actions.get("cameo_cli_evidence_integrity_ready") is True
            or operator_actions.get("cameo_validation_operations_evidence_integrity_ready") is True
        ),
        "cameo_evidence_integrity_status": _text(
            operator_actions.get("cameo_validation_operations_evidence_integrity_status")
        ),
        "cameo_evidence_integrity_blocker_count": _int(
            operator_actions.get("cameo_validation_operations_evidence_integrity_blocker_count")
        ),
        "cameo_official_results_pending_honest": bool(
            operator_actions.get("cameo_cli_official_results_pending_honest") is True
            or operator_actions.get("cameo_validation_operations_official_results_pending_honest") is True
        ),
        "cameo_no_local_native_accuracy_substitution": bool(
            operator_actions.get("cameo_cli_no_local_native_accuracy_substitution") is True
            or operator_actions.get("cameo_validation_operations_no_local_native_accuracy_substitution") is True
        ),
        "cameo_cli_api_install_approval_required": bool(operator_actions.get("cameo_cli_api_install_approval_required") is True),
        "cameo_cli_receiver_smoke_status": _text(operator_actions.get("cameo_cli_receiver_smoke_status")),
        "cleanup_cli_status_set_status": _text(operator_actions.get("cleanup_cli_status_set_status")),
        "cleanup_cli_approval_token_count": _int(operator_actions.get("cleanup_cli_approval_token_count")),
        "cleanup_cli_approval_reclaim_size_gb": round(_float(operator_actions.get("cleanup_cli_approval_reclaim_size_gb")), 3),
        "cleanup_cli_postcheck_contract_ready": bool(operator_actions.get("cleanup_cli_postcheck_contract_ready") is True),
        "cleanup_cli_protected_payload_size_gb": round(_float(operator_actions.get("cleanup_cli_protected_payload_size_gb")), 3),
        "cleanup_cli_protected_policy_change_required_count": _int(
            operator_actions.get("cleanup_cli_protected_policy_change_required_count")
        ),
        "protected_cleanup_payload_size_gb": round(_float(_summary(protected_cleanup_review_packet).get("protected_payload_size_gb")), 3),
        "cleanup_postcheck_contract_status": _text(_summary(cleanup_postcheck_contract_packet or {}).get("status")),
        "cleanup_postcheck_contract_ready": bool(_summary(cleanup_postcheck_contract_packet or {}).get("postcheck_contract_ready") is True),
        "cleanup_postcheck_row_count": _int(_summary(cleanup_postcheck_contract_packet or {}).get("row_count")),
        "cleanup_postcheck_blocked_row_count": _int(_summary(cleanup_postcheck_contract_packet or {}).get("blocked_row_count")),
        "execution_enabled": False,
        "action_executed": False,
        "delete_executed": False,
        "outbound_email_enabled": False,
        "server_registration_mutated": False,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": _next_required_step(rows),
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    s = payload["summary"]
    lines = [
        "# Goal Release Burndown Work Order",
        "",
        f"- status: `{s['status']}`",
        f"- source_release_gate_status: `{s['source_release_gate_status']}`",
        f"- source_release_allowed: `{s['source_release_allowed']}`",
        f"- source_release_blocker_count: `{s['source_release_blocker_count']}`",
        f"- work_item_count: `{s['work_item_count']}`",
        f"- approval_required_item_count: `{s['approval_required_item_count']}`",
        f"- operator_input_required_item_count: `{s['operator_input_required_item_count']}`",
        f"- burndown_operator_input_required_work_item_count: `{s['burndown_operator_input_required_work_item_count']}`",
        f"- goal_operator_intake_kit_status: `{s['goal_operator_intake_kit_status']}`",
        f"- goal_operator_intake_kit_release_burndown_linked_entry_count: `{s['goal_operator_intake_kit_release_burndown_linked_entry_count']}`",
        f"- goal_operator_intake_kit_current_action_required_count: `{s['goal_operator_intake_kit_current_action_required_count']}`",
        f"- goal_operator_intake_kit_deferred_operator_input_count: `{s['goal_operator_intake_kit_deferred_operator_input_count']}`",
        f"- goal_operator_intake_kit_current_action_approval_token_count: `{s['goal_operator_intake_kit_current_action_approval_token_count']}`",
        f"- official_results_required_item_count: `{s['official_results_required_item_count']}`",
        f"- policy_decision_required_item_count: `{s['policy_decision_required_item_count']}`",
        f"- postcheck_required_item_count: `{s['postcheck_required_item_count']}`",
        f"- approval_tokens_required: `{','.join(s['approval_tokens_required'])}`",
        f"- product_cli_status_set_status: `{s['product_cli_status_set_status']}`",
        f"- product_cli_approval_token_count: `{s['product_cli_approval_token_count']}`",
        f"- product_cli_operations_blocked_stage_count: `{s['product_cli_operations_blocked_stage_count']}`",
        f"- product_operational_quality_status: `{s['product_operational_quality_status']}`",
        f"- product_operational_quality_ready: `{s['product_operational_quality_ready']}`",
        f"- product_operational_quality_blocker_count: `{s['product_operational_quality_blocker_count']}`",
        f"- cameo_cli_status_set_status: `{s['cameo_cli_status_set_status']}`",
        f"- cameo_cli_approval_token_count: `{s['cameo_cli_approval_token_count']}`",
        f"- cameo_cli_official_result_required: `{s['cameo_cli_official_result_required']}`",
        f"- cameo_evidence_integrity_status: `{s['cameo_evidence_integrity_status']}`",
        f"- cameo_evidence_integrity_ready: `{s['cameo_evidence_integrity_ready']}`",
        f"- cameo_evidence_integrity_blocker_count: `{s['cameo_evidence_integrity_blocker_count']}`",
        f"- cameo_official_results_pending_honest: `{s['cameo_official_results_pending_honest']}`",
        f"- cameo_no_local_native_accuracy_substitution: `{s['cameo_no_local_native_accuracy_substitution']}`",
        f"- cleanup_cli_status_set_status: `{s['cleanup_cli_status_set_status']}`",
        f"- cleanup_cli_approval_token_count: `{s['cleanup_cli_approval_token_count']}`",
        f"- cleanup_cli_approval_reclaim_size_gb: `{s['cleanup_cli_approval_reclaim_size_gb']}`",
        f"- execution_enabled: `{s['execution_enabled']}`",
        f"- action_executed: `{s['action_executed']}`",
        f"- delete_executed: `{s['delete_executed']}`",
        f"- outbound_email_enabled: `{s['outbound_email_enabled']}`",
        f"- external_state_mutated: `{s['external_state_mutated']}`",
        "",
        "## Work Items",
        "",
        "| seq | phase | lane | check | status | approval | artifact | action |",
        "| ---: | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['sequence']}` | `{row['phase']}` | `{row['lane_id']}` | `{row['release_check']}` | "
            f"`{row['burndown_status']}` | `{row['approval_token_required']}` | `{row['source_artifact']}` | {row['recommended_action']} |"
        )
    lines.extend(["", "## Claim Boundary", "", s["claim_boundary"], "", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a release blocker burndown work order from current local artifacts.")
    parser.add_argument("--release-gate-json", default=DEFAULT_RELEASE_GATE_JSON)
    parser.add_argument("--operator-action-board-json", default=DEFAULT_OPERATOR_ACTION_BOARD_JSON)
    parser.add_argument("--product-preflight-json", default=DEFAULT_PRODUCT_PREFLIGHT_JSON)
    parser.add_argument("--product-gate-repair-json", default=DEFAULT_PRODUCT_GATE_REPAIR_JSON)
    parser.add_argument("--product-work-order-json", default=DEFAULT_PRODUCT_WORK_ORDER_JSON)
    parser.add_argument("--product-pilot-json", default=DEFAULT_PRODUCT_PILOT_JSON)
    parser.add_argument("--public-benchmark-work-order-json", default=DEFAULT_PUBLIC_BENCHMARK_WORK_ORDER_JSON)
    parser.add_argument("--cameo-validation-repair-json", default=DEFAULT_CAMEO_VALIDATION_REPAIR_JSON)
    parser.add_argument("--cameo-runtime-repair-json", default=DEFAULT_CAMEO_RUNTIME_REPAIR_JSON)
    parser.add_argument("--cameo-capability-json", default=DEFAULT_CAMEO_CAPABILITY_JSON)
    parser.add_argument("--transition-cleanup-work-order-json", default=DEFAULT_TRANSITION_CLEANUP_WORK_ORDER_JSON)
    parser.add_argument("--ligand-cleanup-work-order-json", default=DEFAULT_LIGAND_CLEANUP_WORK_ORDER_JSON)
    parser.add_argument("--protected-cleanup-review-json", default=DEFAULT_PROTECTED_CLEANUP_REVIEW_JSON)
    parser.add_argument("--cleanup-postcheck-contract-json", default=DEFAULT_CLEANUP_POSTCHECK_CONTRACT_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_goal_release_burndown_work_order(
        release_gate_packet=_read_json_if_present(args.release_gate_json),
        operator_action_board_packet=_read_json_if_present(args.operator_action_board_json),
        product_work_order_packet=_read_json_if_present(args.product_work_order_json),
        product_pilot_packet=_read_json_if_present(args.product_pilot_json),
        cameo_validation_repair_packet=_read_json_if_present(args.cameo_validation_repair_json),
        cameo_runtime_repair_packet=_read_json_if_present(args.cameo_runtime_repair_json),
        cameo_capability_packet=_read_json_if_present(args.cameo_capability_json),
        transition_cleanup_work_order_packet=_read_json_if_present(args.transition_cleanup_work_order_json),
        ligand_cleanup_work_order_packet=_read_json_if_present(args.ligand_cleanup_work_order_json),
        protected_cleanup_review_packet=_read_json_if_present(args.protected_cleanup_review_json),
        cleanup_postcheck_contract_packet=_read_json_if_present(args.cleanup_postcheck_contract_json),
        product_preflight_packet=_read_json_if_present(args.product_preflight_json),
        product_gate_repair_packet=_read_json_if_present(args.product_gate_repair_json),
        release_gate_path=args.release_gate_json,
        operator_action_board_path=args.operator_action_board_json,
        product_preflight_path=args.product_preflight_json,
        product_gate_repair_path=args.product_gate_repair_json,
        product_work_order_path=args.product_work_order_json,
        product_pilot_path=args.product_pilot_json,
        public_benchmark_work_order_path=args.public_benchmark_work_order_json,
        cameo_validation_repair_path=args.cameo_validation_repair_json,
        cameo_runtime_repair_path=args.cameo_runtime_repair_json,
        cameo_capability_path=args.cameo_capability_json,
        transition_cleanup_work_order_path=args.transition_cleanup_work_order_json,
        ligand_cleanup_work_order_path=args.ligand_cleanup_work_order_json,
        protected_cleanup_review_path=args.protected_cleanup_review_json,
        cleanup_postcheck_contract_path=args.cleanup_postcheck_contract_json,
    )
    _write_json(args.out_json, payload)
    write_csv_rows(_resolve(args.out_csv), payload["rows"])
    _write_markdown(args.out_md, payload)


if __name__ == "__main__":
    main()

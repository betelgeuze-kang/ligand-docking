from __future__ import annotations

from typing import Any

EXECUTION_APPROVAL_TOKEN = "APPROVE_PRODUCT_DOCKING_EXECUTION"
CLAIM_BOUNDARY = (
    "Product execution work order only; it records commands and required artifacts for an operator-reviewed run. "
    "It does not execute docking, assemble a bundle, emit scientific results, or mutate external state."
)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _as_list(value: Any) -> list[str]:
    if not value:
        return []
    if isinstance(value, list):
        return [_text(item) for item in value if _text(item)]
    return [_text(value)] if _text(value) else []


def _blocker(code: str, reason: str) -> dict[str, str]:
    return {"code": code, "severity": "hard", "reason": reason}


def build_product_execution_work_order(
    readiness_packet: dict[str, Any],
    *,
    run_command: str = "",
    config_paths: list[str] | None = None,
    planned_artifact_paths: list[str] | None = None,
    command_generation: dict[str, Any] | None = None,
    bundle_tag: str = "",
    out_dir: str = "runs/local_delivery",
) -> dict[str, Any]:
    readiness_summary = readiness_packet.get("summary") if isinstance(readiness_packet.get("summary"), dict) else {}
    target_id = _text(readiness_summary.get("target_id"))
    family = _text(readiness_summary.get("family"))
    ligand_count = int(readiness_summary.get("ligand_count") or 0)
    config_paths = _as_list(config_paths)
    planned_artifact_paths = _as_list(planned_artifact_paths)
    run_command = _text(run_command)
    command_generation = command_generation if isinstance(command_generation, dict) else {}
    if not run_command and _text(command_generation.get("command")):
        run_command = _text(command_generation.get("command"))
    bundle_tag = _text(bundle_tag) or f"product_{family}_{target_id}".strip("_")

    blockers: list[dict[str, str]] = []
    if readiness_summary.get("status") != "product_handoff_ready":
        blockers.append(_blocker("product_readiness_not_ready", "Product readiness gate must be product_handoff_ready before execution work order."))
    if readiness_summary.get("execution_enabled") is not False:
        blockers.append(_blocker("readiness_execution_flag_invalid", "Readiness gate must keep execution_enabled=false until explicit approval."))
    if not run_command:
        blockers.append(_blocker("run_command_missing", "Operator-reviewed run_command is required before execution approval."))
    if not config_paths:
        blockers.append(_blocker("config_paths_missing", "At least one exact config/profile path is required for a reproducible work order."))
    if command_generation:
        if command_generation.get("parser_valid") is not True:
            blockers.append(_blocker("profile_command_generation_invalid", "Profile-generated execution command did not validate against the HTVS parser."))
        if command_generation.get("unsupported_profile_keys"):
            blockers.append(_blocker("profile_command_generation_incomplete", "Profile contains keys that could not be mapped to HTVS CLI arguments."))

    request_summary = f"{target_id} {family} ligand docking request; ligands={ligand_count}".strip()
    delivery_scope = f"restricted local delivery: {family}"
    claim_scope = family
    verdict = "Internal-review execution work order only; not a completed delivery bundle."
    rerun_command = run_command or "OPERATOR_FILL_RUN_COMMAND"
    artifact_args = planned_artifact_paths or ["OPERATOR_FILL_RESULT_ARTIFACT_PATH_AFTER_RUN"]
    bundle_command_parts = [
        "python3",
        "tools/build_local_delivery_bundle.py",
        "--bundle-tag",
        bundle_tag,
        "--out-dir",
        out_dir,
        "--request-summary",
        request_summary,
        "--delivery-scope",
        delivery_scope,
        "--claim-scope",
        claim_scope,
        "--verdict",
        verdict,
        "--rerun-command",
        rerun_command,
    ]
    for config_path in config_paths:
        bundle_command_parts.extend(["--config-path", config_path])
    for artifact_path in artifact_args:
        bundle_command_parts.extend(["--artifact-path", artifact_path])

    status = "product_execution_work_order_ready" if not blockers else "blocked_product_execution_work_order"
    summary = {
        "packet_type": "product_execution_work_order",
        "status": status,
        "target_id": target_id,
        "family": family,
        "ligand_count": ligand_count,
        "blocker_count": len(blockers),
        "execution_enabled": False,
        "docking_results_emitted": False,
        "bundle_assembled": False,
        "external_state_mutated": False,
        "approval_token_required": EXECUTION_APPROVAL_TOKEN,
        "bundle_tag": bundle_tag,
        "profile_command_generated": bool(command_generation),
        "profile_command_rendered_count": int(command_generation.get("rendered_count") or 0),
        "profile_command_unsupported_count": len(command_generation.get("unsupported_profile_keys") or []),
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            f"Review this work order, provide `{EXECUTION_APPROVAL_TOKEN}`, rerun the approval gate, then run the execution command only if the gate is ready."
            if status == "product_execution_work_order_ready"
            else "Fill missing command/config fields or repair readiness blockers before execution approval."
        ),
    }
    commands = {
        "preflight_command": "python3 tools/run_local_delivery_preflight.py",
        "approval_gate_command": "python3 tools/build_product_execution_approval_gate.py",
        "execution_command": rerun_command,
        "bundle_command": bundle_command_parts,
        "bundle_validation_command": f"python3 tools/validate_local_delivery_bundle.py --bundle-dir {out_dir}/bundle_{bundle_tag}",
    }
    rows = [
        {"step": "preflight", "command": commands["preflight_command"], "required_before_execution": True},
        {"step": "approval_gate", "command": commands["approval_gate_command"], "required_before_execution": True},
        {"step": "execution", "command": commands["execution_command"], "required_before_execution": True},
        {"step": "bundle", "command": " ".join(commands["bundle_command"]), "required_before_execution": False},
        {"step": "validate_bundle", "command": commands["bundle_validation_command"], "required_before_execution": False},
    ]
    return {
        "summary": summary,
        "blockers": blockers,
        "commands": commands,
        "command_generation": command_generation,
        "rows": rows,
    }

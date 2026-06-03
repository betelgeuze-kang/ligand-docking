#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows
from tools.build_cameo_official_results_intake_gate import (
    DEFAULT_OUT_JSON as DEFAULT_CAMEO_OFFICIAL_RESULTS_GATE_JSON,
    DEFAULT_RESULTS_CSV as DEFAULT_CAMEO_OFFICIAL_RESULTS_INTAKE_CSV,
    DEFAULT_TEMPLATE_CSV as DEFAULT_CAMEO_OFFICIAL_RESULTS_TEMPLATE_CSV,
)
from tools.build_cameo_public_registration_approval_gate import (
    DEFAULT_OPERATOR_APPROVAL_CSV as DEFAULT_CAMEO_REGISTRATION_INTAKE_CSV,
    DEFAULT_OUT_JSON as DEFAULT_CAMEO_REGISTRATION_GATE_JSON,
    DEFAULT_TEMPLATE_CSV as DEFAULT_CAMEO_REGISTRATION_TEMPLATE_CSV,
    OUTBOUND_EMAIL_APPROVAL_TOKEN,
    REGISTRATION_APPROVAL_TOKEN,
)
from tools.build_cleanup_execution_approval_gate import (
    DEFAULT_OPERATOR_APPROVAL_CSV as DEFAULT_CLEANUP_APPROVAL_INTAKE_CSV,
    DEFAULT_OUT_JSON as DEFAULT_CLEANUP_APPROVAL_GATE_JSON,
    DEFAULT_TEMPLATE_CSV as DEFAULT_CLEANUP_APPROVAL_TEMPLATE_CSV,
)
from tools.build_goal_operator_action_board import DEFAULT_OUT_JSON as DEFAULT_ACTION_BOARD_JSON
from tools.build_goal_api_surface_contract import DEFAULT_OUT_JSON as DEFAULT_GOAL_API_SURFACE_CONTRACT_JSON
from tools.build_goal_release_burndown_work_order import DEFAULT_OUT_JSON as DEFAULT_RELEASE_BURNDOWN_JSON
from tools.build_product_execution_approval_gate import (
    DEFAULT_OPERATOR_APPROVAL_CSV as DEFAULT_PRODUCT_EXECUTION_INTAKE_CSV,
    DEFAULT_OUT_JSON as DEFAULT_PRODUCT_EXECUTION_GATE_JSON,
    DEFAULT_TEMPLATE_CSV as DEFAULT_PRODUCT_EXECUTION_TEMPLATE_CSV,
)
from tools.build_product_commercial_independence_gate import DEFAULT_OUT_JSON as DEFAULT_PRODUCT_COMMERCIAL_INDEPENDENCE_JSON
from tools.build_product_license_decision_gate import (
    DEFAULT_OPERATOR_INTAKE_CSV as DEFAULT_PRODUCT_LICENSE_INTAKE_CSV,
    DEFAULT_OUT_JSON as DEFAULT_PRODUCT_LICENSE_GATE_JSON,
    DEFAULT_TEMPLATE_CSV as DEFAULT_PRODUCT_LICENSE_TEMPLATE_CSV,
)
from tools.build_protected_cleanup_policy_decision_gate import (
    DEFAULT_OPERATOR_POLICY_CSV as DEFAULT_PROTECTED_POLICY_INTAKE_CSV,
    DEFAULT_OUT_JSON as DEFAULT_PROTECTED_POLICY_GATE_JSON,
    DEFAULT_TEMPLATE_CSV as DEFAULT_PROTECTED_POLICY_TEMPLATE_CSV,
)

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT_DIR = "runs/goal_operator_intake_kit_current"
DEFAULT_OUT_JSON = f"{DEFAULT_OUT_DIR}/manifest.json"
DEFAULT_OUT_CSV = f"{DEFAULT_OUT_DIR}/manifest.csv"
DEFAULT_OUT_MD = f"{DEFAULT_OUT_DIR}/README.md"

CLAIM_BOUNDARY = (
    "Goal operator intake kit only; it consolidates existing operator templates, expected intake paths, approval tokens, "
    "read-only goal API contract status, and official-result/policy-decision requirements into a local review manifest. "
    "It copies template CSVs only. It does "
    "not fill operator intake, approve tokens, run docking, install packages, register CAMEO, send email, delete, archive, "
    "externalize, upload, commit, push, or mutate external state."
)


CATALOG: list[dict[str, Any]] = [
    {
        "kit_entry_id": "cameo_official_results",
        "lane_id": "cameo_validation",
        "action_types": ["fill_cameo_official_results_intake"],
        "input_kind": "official_results_intake",
        "source_gate_json": DEFAULT_CAMEO_OFFICIAL_RESULTS_GATE_JSON,
        "template_path": DEFAULT_CAMEO_OFFICIAL_RESULTS_TEMPLATE_CSV,
        "intake_path": DEFAULT_CAMEO_OFFICIAL_RESULTS_INTAKE_CSV,
        "official_result_required": True,
        "release_checks": "official_cameo_validation_evidence_ready;official_cameo_results_used",
        "recommended_action": "Fill the intake CSV from official CAMEO assessment output only.",
    },
    {
        "kit_entry_id": "cameo_api_dependency_install",
        "lane_id": "cameo_validation",
        "action_types": ["repair_cameo_receiver_runtime_smoke"],
        "input_kind": "approval_token",
        "source_gate_json": "",
        "template_path": "",
        "intake_path": "",
        "template_required": False,
        "approval_token_required": "APPROVE_API_DEPENDENCY_INSTALL",
        "release_checks": "cameo_public_registration_allowed",
        "recommended_action": "Approve dependency installation separately, then rerun the CAMEO receiver smoke gates.",
    },
    {
        "kit_entry_id": "cameo_public_registration",
        "lane_id": "cameo_validation",
        "action_types": ["fill_cameo_public_registration_approval"],
        "input_kind": "registration_approval_intake",
        "source_gate_json": DEFAULT_CAMEO_REGISTRATION_GATE_JSON,
        "template_path": DEFAULT_CAMEO_REGISTRATION_TEMPLATE_CSV,
        "intake_path": DEFAULT_CAMEO_REGISTRATION_INTAKE_CSV,
        "approval_token_required": f"{REGISTRATION_APPROVAL_TOKEN};{OUTBOUND_EMAIL_APPROVAL_TOKEN}",
        "release_checks": "cameo_public_registration_allowed",
        "recommended_action": "Fill registration/email metadata only after official validation and receiver smoke are ready.",
    },
    {
        "kit_entry_id": "product_execution",
        "lane_id": "commercial_product_execution",
        "action_types": ["review_product_execution_approval"],
        "input_kind": "approval_intake",
        "source_gate_json": DEFAULT_PRODUCT_EXECUTION_GATE_JSON,
        "template_path": DEFAULT_PRODUCT_EXECUTION_TEMPLATE_CSV,
        "intake_path": DEFAULT_PRODUCT_EXECUTION_INTAKE_CSV,
        "approval_token_required": "APPROVE_PRODUCT_DOCKING_EXECUTION",
        "release_checks": "product_architecture_release_ready;pilot_delivery_ready;bundle_validation_passed;delivery_ready_claim_allowed",
        "recommended_action": "Review product execution target and token intake before any docking run.",
    },
    {
        "kit_entry_id": "product_license_decision",
        "lane_id": "commercial_product_license",
        "action_types": ["fill_product_license_decision", "review_product_license_options"],
        "input_kind": "license_decision_intake",
        "source_gate_json": DEFAULT_PRODUCT_LICENSE_GATE_JSON,
        "template_path": DEFAULT_PRODUCT_LICENSE_TEMPLATE_CSV,
        "intake_path": DEFAULT_PRODUCT_LICENSE_INTAKE_CSV,
        "related_source_json": DEFAULT_PRODUCT_COMMERCIAL_INDEPENDENCE_JSON,
        "approval_token_required": "APPROVE_PRODUCT_LICENSE_FILE_CREATION",
        "release_checks": "commercial_independence_gate_ready",
        "recommended_action": "Choose a license path and fill the decision CSV before any LICENSE file creation review.",
    },
    {
        "kit_entry_id": "cleanup_execution_approval",
        "lane_id": "transition_cleanup",
        "action_types": ["review_cleanup_approval_token", "review_ligand_heavy_cleanup_approval"],
        "input_kind": "cleanup_approval_intake",
        "source_gate_json": DEFAULT_CLEANUP_APPROVAL_GATE_JSON,
        "template_path": DEFAULT_CLEANUP_APPROVAL_TEMPLATE_CSV,
        "intake_path": DEFAULT_CLEANUP_APPROVAL_INTAKE_CSV,
        "release_checks": "transition_cleanup_complete;ligand_heavy_cleanup_complete",
        "recommended_action": "Review snapshot-backed cleanup rows and fill approval decisions before any cleanup execution.",
    },
    {
        "kit_entry_id": "protected_cleanup_policy",
        "lane_id": "ligand_heavy_cleanup",
        "action_types": ["review_protected_ligand_heavy_policy"],
        "input_kind": "policy_decision_intake",
        "source_gate_json": DEFAULT_PROTECTED_POLICY_GATE_JSON,
        "template_path": DEFAULT_PROTECTED_POLICY_TEMPLATE_CSV,
        "intake_path": DEFAULT_PROTECTED_POLICY_INTAKE_CSV,
        "policy_decision_required": True,
        "release_checks": "protected_cleanup_policy_resolved",
        "recommended_action": "Decide whether protected payload rows remain protected or require explicit policy-change review.",
    },
    {
        "kit_entry_id": "goal_api_status_surface",
        "lane_id": "goal_status_surface",
        "action_types": [],
        "input_kind": "read_only_api_contract_review",
        "source_gate_json": DEFAULT_GOAL_API_SURFACE_CONTRACT_JSON,
        "template_path": "",
        "intake_path": "",
        "template_required": False,
        "api_endpoints": "/goal/status;/goal/api-contract",
        "recommended_action": "Review the read-only /goal status and API contract surfaces before operator handoff.",
    },
]


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


def _display_path(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def _bool(value: Any) -> bool:
    return bool(value is True)


def _int(value: Any) -> int:
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0


def _split_artifacts(value: Any) -> list[str]:
    return [part.strip() for part in _text(value).split(";") if part.strip()]


def _unique_text(values: list[Any]) -> str:
    parts: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = _text(value)
        if not text or text in seen:
            continue
        seen.add(text)
        parts.append(text)
    return ";".join(parts)


def _token_set(value: Any) -> set[str]:
    return {part.strip() for part in _text(value).split(";") if part.strip()}


def _source_status(source_packets: dict[str, dict[str, Any]], source_gate_json: str) -> str:
    if not source_gate_json:
        return ""
    return _text(_summary(source_packets.get(source_gate_json, {})).get("status"))


def _matching_actions(actions: list[dict[str, Any]], entry: dict[str, Any]) -> list[dict[str, Any]]:
    action_types = set(entry.get("action_types") or [])
    lane_id = _text(entry.get("lane_id"))
    matched: list[dict[str, Any]] = []
    for action in actions:
        action_type = _text(action.get("action_type"))
        if action_type not in action_types:
            continue
        if lane_id and _text(action.get("lane_id")) not in {lane_id, "ligand_heavy_cleanup"} and entry["kit_entry_id"] != "cleanup_execution_approval":
            continue
        matched.append(action)
    return matched


def _matching_burndown_rows(burndown_rows: list[dict[str, Any]], entry: dict[str, Any]) -> list[dict[str, Any]]:
    release_checks = {part for part in _text(entry.get("release_checks")).split(";") if part}
    if not release_checks:
        return []
    matched: list[dict[str, Any]] = []
    for row in burndown_rows:
        row_checks = {part for part in _text(row.get("release_checks") or row.get("release_check")).split(";") if part}
        if release_checks & row_checks:
            matched.append(row)
    return matched


def _entry_obsolete_for_current_burndown(entry: dict[str, Any], matched_burndown: list[dict[str, Any]]) -> bool:
    entry_tokens = _token_set(entry.get("approval_token_required"))
    if not entry_tokens or not matched_burndown:
        return False
    current_tokens: set[str] = set()
    for row in matched_burndown:
        current_tokens.update(_token_set(row.get("approval_token_required")))
    return bool(current_tokens and not (entry_tokens & current_tokens))


def _entry_status(matched_actions: list[dict[str, Any]], source_status: str, entry: dict[str, Any]) -> str:
    if matched_actions:
        statuses = {_text(action.get("status")) for action in matched_actions}
        if "approval_required" in statuses:
            return "approval_required"
        if "policy_decision_required" in statuses:
            return "policy_decision_required"
        if "required" in statuses:
            return "operator_input_required"
        if "blocked" in statuses:
            return "blocked"
        if "available" in statuses:
            return "available"
    if source_status.startswith("blocked"):
        if _bool(entry.get("policy_decision_required")):
            return "policy_decision_required"
        if _bool(entry.get("official_result_required")):
            return "operator_input_required"
        if _text(entry.get("approval_token_required")):
            return "approval_required"
        return "blocked"
    if source_status.endswith("_ready") or source_status.endswith("_clear"):
        return "ready"
    return "not_surfaced"


def _copy_template(template_path: str, out_dir: Path) -> tuple[str, bool]:
    if not template_path:
        return "", False
    source = _resolve(template_path)
    destination = out_dir / "templates" / source.name
    if not source.exists():
        return _display_path(destination), False
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)
    return _display_path(destination), True


def build_goal_operator_intake_kit(
    *,
    action_board_packet: dict[str, Any],
    release_burndown_packet: dict[str, Any] | None = None,
    source_packets: dict[str, dict[str, Any]] | None = None,
    out_dir: str | Path = DEFAULT_OUT_DIR,
    copy_templates: bool = False,
) -> dict[str, Any]:
    source_packets = source_packets or {}
    out_dir_path = _resolve(out_dir)
    actions = _rows(action_board_packet)
    burndown_rows = _rows(release_burndown_packet or {})
    rows: list[dict[str, Any]] = []
    for entry in CATALOG:
        template_path = _text(entry.get("template_path"))
        template_required = entry.get("template_required") is not False
        matched = _matching_actions(actions, entry)
        matched_burndown = _matching_burndown_rows(burndown_rows, entry)
        if _entry_obsolete_for_current_burndown(entry, matched_burndown):
            matched = []
            matched_burndown = []
        source_gate_json = _text(entry.get("source_gate_json"))
        source_status = _source_status(source_packets, source_gate_json)
        related_source_json = _text(entry.get("related_source_json"))
        related_source_status = _source_status(source_packets, related_source_json)
        copied_template_path = ""
        copied = False
        if copy_templates:
            copied_template_path, copied = _copy_template(template_path, out_dir_path)
        elif template_path:
            copied_template_path = _display_path(out_dir_path / "templates" / Path(template_path).name)
        template_present = bool(template_path and _resolve(template_path).exists())
        intake_path = _text(entry.get("intake_path"))
        kit_status = _entry_status(matched, source_status, entry)
        tokens = (
            ""
            if kit_status == "not_surfaced"
            else _unique_text(
                [_text(entry.get("approval_token_required"))]
                + [action.get("approval_token") or action.get("approval_token_required") for action in matched]
            )
        )
        row = {
            "kit_entry_id": _text(entry.get("kit_entry_id")),
            "lane_id": _text(entry.get("lane_id")),
            "action_types": ";".join(entry.get("action_types") or []),
            "input_kind": _text(entry.get("input_kind")),
            "kit_status": kit_status,
            "current_action_surfaced": bool(matched),
            "source_gate_json": source_gate_json,
            "source_gate_status": source_status,
            "related_source_json": related_source_json,
            "related_source_status": related_source_status,
            "source_action_count": len(matched),
            "source_action_statuses": _unique_text([action.get("status") for action in matched]),
            "source_artifacts": _unique_text([artifact for action in matched for artifact in _split_artifacts(action.get("artifact_path"))]),
            "release_checks": _text(entry.get("release_checks")),
            "release_burndown_surfaced": bool(matched_burndown),
            "release_sequence": _unique_text([row.get("sequence") for row in matched_burndown]),
            "release_phase": _unique_text([row.get("phase") for row in matched_burndown]),
            "release_burndown_status": _unique_text([row.get("burndown_status") for row in matched_burndown]),
            "release_source_artifacts": _unique_text(
                [artifact for row in matched_burndown for artifact in _split_artifacts(row.get("source_artifact"))]
            ),
            "release_recommended_action": _unique_text([row.get("recommended_action") for row in matched_burndown]),
            "template_required": template_required,
            "template_path": template_path,
            "template_present": template_present,
            "kit_template_path": copied_template_path,
            "kit_template_copied": copied,
            "intake_path": intake_path,
            "intake_present": bool(intake_path and _resolve(intake_path).exists()),
            "api_endpoints": _text(entry.get("api_endpoints")),
            "approval_token_required": tokens,
            "official_result_required": _bool(entry.get("official_result_required")),
            "policy_decision_required": _bool(entry.get("policy_decision_required")),
            "operator_input_required": False,
            "operator_input_required_now": False,
            "recommended_action": _text(entry.get("recommended_action")),
            "action_executed": False,
            "delete_executed": False,
            "outbound_email_enabled": False,
            "external_state_mutated": False,
        }
        row["operator_input_required"] = row["kit_status"] in {
            "operator_input_required",
            "approval_required",
            "policy_decision_required",
            "blocked",
        }
        row["operator_input_required_now"] = bool(row["operator_input_required"] and row["current_action_surfaced"])
        rows.append(row)

    goal_api_surface = _summary(source_packets.get(DEFAULT_GOAL_API_SURFACE_CONTRACT_JSON, {}))
    product_commercial = _summary(source_packets.get(DEFAULT_PRODUCT_COMMERCIAL_INDEPENDENCE_JSON, {}))
    template_rows = [row for row in rows if row["template_required"]]
    missing_template_rows = [row for row in template_rows if not row["template_present"]]
    copied_template_rows = [row for row in template_rows if row["kit_template_copied"]]
    approval_tokens = sorted(
        {
            token
            for row in rows
            for token in _text(row.get("approval_token_required")).split(";")
            if token
        }
    )
    current_action_approval_tokens = sorted(
        {
            token
            for action in actions
            for token in _text(action.get("approval_token") or action.get("approval_token_required")).split(";")
            if token
        }
    )
    summary = {
        "packet_type": "goal_operator_intake_kit",
        "status": "goal_operator_intake_kit_ready" if not missing_template_rows else "blocked_goal_operator_intake_kit",
        "kit_dir": _display_path(out_dir_path),
        "manifest_json": DEFAULT_OUT_JSON if _resolve(DEFAULT_OUT_JSON).parent == out_dir_path else "",
        "entry_count": len(rows),
        "source_action_count": len(actions),
        "release_burndown_source_row_count": len(burndown_rows),
        "release_burndown_linked_entry_count": sum(1 for row in rows if row["release_burndown_surfaced"]),
        "operator_input_required_count": sum(1 for row in rows if row["operator_input_required"]),
        "current_action_required_count": sum(1 for row in rows if row["operator_input_required_now"]),
        "deferred_operator_input_count": sum(
            1 for row in rows if row["operator_input_required"] and not row["operator_input_required_now"]
        ),
        "approval_required_count": sum(1 for row in rows if row["kit_status"] == "approval_required"),
        "official_results_required_count": sum(1 for row in rows if row["official_result_required"]),
        "policy_decision_required_count": sum(1 for row in rows if row["policy_decision_required"]),
        "template_required_count": len(template_rows),
        "template_present_count": len(template_rows) - len(missing_template_rows),
        "template_missing_count": len(missing_template_rows),
        "template_copied_count": len(copied_template_rows),
        "all_required_templates_present": not missing_template_rows,
        "approval_token_count": len(approval_tokens),
        "approval_tokens": approval_tokens,
        "current_action_approval_token_count": len(current_action_approval_tokens),
        "current_action_approval_tokens": current_action_approval_tokens,
        "product_commercial_independence_status": _text(product_commercial.get("status")),
        "product_commercial_independent_claim_allowed": bool(
            product_commercial.get("commercial_independent_product_claim_allowed") is True
        ),
        "product_commercial_independence_blocker_count": _int(product_commercial.get("blocker_count")),
        "product_commercial_independence_license_present": bool(product_commercial.get("license_present") is True),
        "product_commercial_independence_check_count": _int(product_commercial.get("check_count")),
        "goal_api_surface_contract_status": _text(goal_api_surface.get("status")),
        "goal_api_surface_ready": bool(goal_api_surface.get("surface_ready") is True),
        "goal_api_surface_check_count": _int(goal_api_surface.get("check_count")),
        "goal_api_surface_blocker_count": _int(goal_api_surface.get("blocker_count")),
        "goal_api_surface_missing_endpoint_count": _int(goal_api_surface.get("missing_endpoint_count")),
        "goal_api_surface_missing_status_key_count": _int(goal_api_surface.get("missing_status_key_count")),
        "goal_api_surface_contract_json": DEFAULT_GOAL_API_SURFACE_CONTRACT_JSON,
        "goal_api_status_endpoint": "/goal/status",
        "goal_api_contract_endpoint": "/goal/api-contract",
        "action_executed": False,
        "delete_executed": False,
        "outbound_email_enabled": False,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": "Use the kit templates to prepare operator intake CSVs; approval-gated actions remain disabled until explicit tokens are provided.",
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    s = payload["summary"]
    lines = [
        "# Goal Operator Intake Kit",
        "",
        f"- status: `{s['status']}`",
        f"- entry_count: `{s['entry_count']}`",
        f"- release_burndown_linked_entry_count: `{s['release_burndown_linked_entry_count']}`",
        f"- operator_input_required_count: `{s['operator_input_required_count']}`",
        f"- current_action_required_count: `{s['current_action_required_count']}`",
        f"- deferred_operator_input_count: `{s['deferred_operator_input_count']}`",
        f"- approval_required_count: `{s['approval_required_count']}`",
        f"- official_results_required_count: `{s['official_results_required_count']}`",
        f"- policy_decision_required_count: `{s['policy_decision_required_count']}`",
        f"- template_present_count: `{s['template_present_count']}` / `{s['template_required_count']}`",
        f"- approval_tokens: `{';'.join(s['approval_tokens'])}`",
        f"- current_action_approval_tokens: `{';'.join(s['current_action_approval_tokens'])}`",
        f"- product_commercial_independence_status: `{s['product_commercial_independence_status']}`",
        f"- product_commercial_independence_license_present: `{s['product_commercial_independence_license_present']}`",
        f"- goal_api_surface_contract_status: `{s['goal_api_surface_contract_status']}`",
        f"- goal_api_surface_ready: `{s['goal_api_surface_ready']}`",
        f"- goal_api_status_endpoint: `{s['goal_api_status_endpoint']}`",
        f"- goal_api_contract_endpoint: `{s['goal_api_contract_endpoint']}`",
        "",
        "## Entries",
        "",
        "| entry | status | release sequence | release phase | template | intake | related source | endpoint | token |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['kit_entry_id']}` | `{row['kit_status']}` | `{row['release_sequence']}` | "
            f"`{row['release_phase']}` | `{row['kit_template_path'] or row['template_path']}` | "
            f"`{row['intake_path']}` | `{row['related_source_status']}` | `{row['api_endpoints']}` | "
            f"`{row['approval_token_required']}` |"
        )
    lines.extend(["", "## Claim Boundary", "", s["claim_boundary"], "", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a read-only goal operator intake kit from existing templates and action boards.")
    parser.add_argument("--action-board-json", default=DEFAULT_ACTION_BOARD_JSON)
    parser.add_argument("--release-burndown-json", default=DEFAULT_RELEASE_BURNDOWN_JSON)
    parser.add_argument("--cameo-official-results-gate-json", default=DEFAULT_CAMEO_OFFICIAL_RESULTS_GATE_JSON)
    parser.add_argument("--cameo-registration-gate-json", default=DEFAULT_CAMEO_REGISTRATION_GATE_JSON)
    parser.add_argument("--product-execution-gate-json", default=DEFAULT_PRODUCT_EXECUTION_GATE_JSON)
    parser.add_argument("--product-commercial-independence-json", default=DEFAULT_PRODUCT_COMMERCIAL_INDEPENDENCE_JSON)
    parser.add_argument("--product-license-gate-json", default=DEFAULT_PRODUCT_LICENSE_GATE_JSON)
    parser.add_argument("--cleanup-approval-gate-json", default=DEFAULT_CLEANUP_APPROVAL_GATE_JSON)
    parser.add_argument("--protected-policy-gate-json", default=DEFAULT_PROTECTED_POLICY_GATE_JSON)
    parser.add_argument("--goal-api-surface-contract-json", default=DEFAULT_GOAL_API_SURFACE_CONTRACT_JSON)
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    source_packets = {
        DEFAULT_CAMEO_OFFICIAL_RESULTS_GATE_JSON: _read_json_if_present(args.cameo_official_results_gate_json),
        DEFAULT_CAMEO_REGISTRATION_GATE_JSON: _read_json_if_present(args.cameo_registration_gate_json),
        DEFAULT_PRODUCT_EXECUTION_GATE_JSON: _read_json_if_present(args.product_execution_gate_json),
        DEFAULT_PRODUCT_COMMERCIAL_INDEPENDENCE_JSON: _read_json_if_present(args.product_commercial_independence_json),
        DEFAULT_PRODUCT_LICENSE_GATE_JSON: _read_json_if_present(args.product_license_gate_json),
        DEFAULT_CLEANUP_APPROVAL_GATE_JSON: _read_json_if_present(args.cleanup_approval_gate_json),
        DEFAULT_PROTECTED_POLICY_GATE_JSON: _read_json_if_present(args.protected_policy_gate_json),
        DEFAULT_GOAL_API_SURFACE_CONTRACT_JSON: _read_json_if_present(args.goal_api_surface_contract_json),
    }
    payload = build_goal_operator_intake_kit(
        action_board_packet=_read_json_if_present(args.action_board_json),
        release_burndown_packet=_read_json_if_present(args.release_burndown_json),
        source_packets=source_packets,
        out_dir=args.out_dir,
        copy_templates=True,
    )
    _write_json(args.out_json, payload)
    write_csv_rows(_resolve(args.out_csv), payload["rows"])
    _write_markdown(args.out_md, payload)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]

DEFAULT_WORK_ORDER_JSON = ".betelgeuze/developer_preview_new_user_execution_work_order.json"
DEFAULT_PREFLIGHT_JSON = ".betelgeuze/developer_preview_new_user_execution_preflight.json"
DEFAULT_RUNBOOK_MD = "docs/developer_preview_core_workflow_quickstart.md"
DEFAULT_OUT_JSON = ".betelgeuze/developer_preview_new_user_observation_receipt.json"
DEFAULT_OUT_MD = ".betelgeuze/developer_preview_new_user_observation_receipt.md"
DEFAULT_OUT_CHECKLIST_CSV = (
    ".betelgeuze/developer_preview_new_user_observation_checklist.csv"
)
DEFAULT_OUT_CHECKLIST_MD = (
    ".betelgeuze/developer_preview_new_user_observation_checklist.md"
)
DEFAULT_OBSERVATION_INPUT_JSON = (
    ".betelgeuze/developer_preview_new_user_observation_input.json"
)
DEFAULT_OUT_OBSERVATION_INPUT_TEMPLATE_JSON = (
    ".betelgeuze/developer_preview_new_user_observation_input_template.json"
)

PACKET_TYPE = "developer_preview_new_user_observation_receipt"
SCHEMA_VERSION = "developer_preview_new_user_observation_receipt_v1"
OBSERVATION_INPUT_PACKET_TYPE = "developer_preview_new_user_observation_input"
OBSERVATION_INPUT_SCHEMA_VERSION = "developer_preview_new_user_observation_input_v1"
OBSERVATION_REVIEW_REQUIRED_FIELD_IDS = [
    "observer_id_present",
    "observed_at_utc_present",
    "observer_signoff",
    "anonymized_notes_only",
    "anonymized_summary_present",
    "hidden_state_blockers_absent",
    "raw_customer_data_not_stored_in_repo",
    "customer_retained_raw_data",
]
RUNBOOK_REQUIRED_TOKENS = [
    "git clone <repo-url> betelgeuze-developer-preview",
    "python3 -m venv .venv",
    ". .venv/bin/activate",
    "py -3 -m venv .venv",
    ". .venv/Scripts/activate",
    "python -m pip install -r requirements.txt -r requirements-dev.txt",
    "scripts/ai-verify.sh",
    "tools/run_external_validation_baselines.py",
    "tools/product/build_developer_preview_clean_checkout_benchmark_receipt.py",
    "tools/product/build_developer_preview_platform_reproducibility_receipt.py",
    "tools/build_product_execution_work_order.py",
    "tools/build_product_execution_preflight.py",
    "tools/product/build_developer_preview_new_user_observation_receipt.py",
    "tools/product/build_developer_preview_final_gate_audit.py",
    "tools/product/build_developer_preview_stage5_restore_packet.py",
    "stage5-recovery",
    "pwsh -File runs/developer_preview_external_operator_command_pack_current.ps1 -Target windows-repro",
    "runs/developer_preview_stage5_restore_packet_current.json",
    ".betelgeuze/developer_preview_clean_checkout_ai_verify.log",
    ".betelgeuze/developer_preview_external_baselines/biorxiv_baseline_comparison_developer_preview_clean_checkout/summary.json",
    ".betelgeuze/developer_preview_clean_checkout_benchmark_receipt.json",
    ".betelgeuze/developer_preview_linux_ai_verify.log",
    ".betelgeuze/developer_preview_linux_reproducibility_pytest.xml",
    ".betelgeuze/developer_preview_linux_reproducibility_receipt.json",
    ".betelgeuze/developer_preview_windows_ai_verify.log",
    ".betelgeuze/developer_preview_windows_reproducibility_pytest.xml",
    ".betelgeuze/developer_preview_windows_reproducibility_receipt.json",
    ".betelgeuze/developer_preview_new_user_execution_work_order.json",
    ".betelgeuze/developer_preview_new_user_execution_preflight.json",
    ".betelgeuze/developer_preview_new_user_observation_input_template.json",
    ".betelgeuze/developer_preview_new_user_observation_input.json",
    "`new-user-final` requires `.betelgeuze/developer_preview_new_user_observation_input.json`",
    "observation_input_contract_ready",
    "observation_input_packet_type_valid",
    "observation_input_schema_version_valid",
    "observation_input_policy_ready",
    "raw_customer_data_allowed",
    "stores_private_notes",
    ".betelgeuze/developer_preview_new_user_observation_checklist.csv",
    ".betelgeuze/developer_preview_new_user_observation_checklist.md",
    ".betelgeuze/developer_preview_new_user_observation_receipt.json",
    "runs/developer_preview_final_gate_audit_current.json",
    "--out-checklist-csv",
    "--out-checklist-md",
    "--observation-input-json",
    "--out-observation-input-template-json",
    "--observer-signoff",
    "--anonymized-notes-only",
    "--raw-customer-data-not-stored-in-repo",
    "--customer-retained-raw-data",
    "--allow-blocked",
    "blocked_developer_preview_new_user_observation_receipt",
    "hidden local state",
    "raw customer data stays outside this repository",
]
CORE_WORKFLOW_RECEIPT_PATH_TOKENS = [
    ".betelgeuze/developer_preview_new_user_execution_work_order.json",
    ".betelgeuze/developer_preview_new_user_execution_preflight.json",
    ".betelgeuze/developer_preview_new_user_observation_receipt.json",
]
CORE_WORKFLOW_COMMAND_TOKENS = [
    "tools/build_product_execution_work_order.py",
    "tools/build_product_execution_preflight.py",
    "tools/product/build_developer_preview_new_user_observation_receipt.py",
]
DEVELOPER_PREVIEW_EXIT_RECEIPT_PATH_TOKENS = [
    ".betelgeuze/developer_preview_clean_checkout_benchmark_receipt.json",
    ".betelgeuze/developer_preview_linux_reproducibility_receipt.json",
    ".betelgeuze/developer_preview_windows_reproducibility_receipt.json",
    ".betelgeuze/developer_preview_new_user_observation_receipt.json",
    "runs/developer_preview_final_gate_audit_current.json",
]
OBSERVATION_CHECKLIST_PATH_TOKENS = [
    ".betelgeuze/developer_preview_new_user_observation_input_template.json",
    ".betelgeuze/developer_preview_new_user_observation_input.json",
    ".betelgeuze/developer_preview_new_user_observation_checklist.csv",
    ".betelgeuze/developer_preview_new_user_observation_checklist.md",
]
DEVELOPER_PREVIEW_EXIT_COMMAND_TOKENS = [
    "tools/product/build_developer_preview_clean_checkout_benchmark_receipt.py",
    "tools/product/build_developer_preview_platform_reproducibility_receipt.py",
    "tools/product/build_developer_preview_new_user_observation_receipt.py",
    "tools/product/build_developer_preview_final_gate_audit.py",
]
BOOTSTRAP_COMMAND_TOKENS = [
    "git clone <repo-url> betelgeuze-developer-preview",
    "python -m pip install -r requirements.txt -r requirements-dev.txt",
]
LINUX_BOOTSTRAP_COMMAND_TOKENS = [
    "python3 -m venv .venv",
    ". .venv/bin/activate",
]
WINDOWS_BOOTSTRAP_COMMAND_TOKENS = [
    "py -3 -m venv .venv",
    ". .venv/Scripts/activate",
]

CLAIM_BOUNDARY = (
    "Developer Preview new-user observation receipt only; it records derived/anonymized operator review "
    "metadata for a local core-workflow observation. It does not execute workflows, collect raw customer "
    "data, store private notes, approve paid-pilot wording, upload, email, deploy, commit, push, or mutate "
    "external state."
)


def _resolve(path_like: str | Path, *, root: Path = ROOT) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else root / path


def _display(path_like: str | Path, *, root: Path = ROOT) -> str:
    path = Path(path_like)
    if path.is_absolute():
        try:
            return str(path.relative_to(root))
        except ValueError:
            return str(path)
    return str(path_like)


def _read_json(path_like: str | Path, *, root: Path = ROOT) -> dict[str, Any]:
    path = _resolve(path_like, root=root)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _read_text(path_like: str | Path, *, root: Path = ROOT) -> str:
    path = _resolve(path_like, root=root)
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def _summary(payload: dict[str, Any]) -> dict[str, Any]:
    summary = payload.get("summary")
    return summary if isinstance(summary, dict) else payload


def _text(value: Any) -> str:
    return str(value or "").strip()


def _bool_true(value: Any) -> bool:
    return value is True


def _int(value: Any) -> int:
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0


def _split_hidden_blockers(values: list[str] | None) -> list[str]:
    blockers: list[str] = []
    for value in values or []:
        text = _text(value)
        if text:
            blockers.append(text)
    return blockers


def _string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [_text(item) for item in value if _text(item)]
    text = _text(value)
    return [text] if text else []


def _observation_input_template_payload() -> dict[str, Any]:
    return {
        "packet_type": OBSERVATION_INPUT_PACKET_TYPE,
        "schema_version": OBSERVATION_INPUT_SCHEMA_VERSION,
        "observer_id": "",
        "observed_at_utc": "",
        "anonymized_summary": "",
        "observer_signoff": False,
        "anonymized_notes_only": False,
        "raw_customer_data_not_stored_in_repo": False,
        "customer_retained_raw_data": False,
        "hidden_state_blockers": [],
        "raw_customer_data_allowed": False,
        "stores_private_notes": False,
        "instructions": [
            "Copy this file to .betelgeuze/developer_preview_new_user_observation_input.json.",
            "Fill only derived/anonymized operator metadata.",
            "Keep raw customer data and private notes outside this repository.",
            "Leave hidden_state_blockers empty only when no undocumented local state was required.",
        ],
        "claim_boundary": CLAIM_BOUNDARY,
    }


def _template_row(
    *,
    field_id: str,
    label: str,
    ready: bool,
    observed: str,
    blocker: str,
    required_action: str,
) -> dict[str, Any]:
    return {
        "field_id": field_id,
        "label": label,
        "status": "pass" if ready else "blocked",
        "ready": ready,
        "observed": observed,
        "blocker": "" if ready else blocker,
        "required_action": "" if ready else required_action,
        "raw_customer_data_allowed": False,
        "stores_private_notes": False,
        "operator_action_required": not ready,
        "execution_enabled": False,
        "external_state_mutated": False,
        "claim_promotion_allowed": False,
        "claim_boundary": CLAIM_BOUNDARY,
    }


def _observation_review_template_rows(
    *,
    reviewer_present: bool,
    observed_at_present: bool,
    observer_signoff: bool,
    anonymized_notes_only: bool,
    anonymized_summary_present: bool,
    hidden_state_blocker_count: int,
    raw_customer_data_not_stored_in_repo: bool,
    customer_retained_raw_data: bool,
) -> list[dict[str, Any]]:
    return [
        _template_row(
            field_id="observer_id_present",
            label="Observer ID recorded as derived operator metadata",
            ready=reviewer_present,
            observed="present" if reviewer_present else "missing",
            blocker="observer_id_missing",
            required_action="Record a non-secret observer id in the reviewed receipt.",
        ),
        _template_row(
            field_id="observed_at_utc_present",
            label="Observation timestamp recorded in UTC",
            ready=observed_at_present,
            observed="present" if observed_at_present else "missing",
            blocker="observed_at_utc_missing",
            required_action="Record the observed_at_utc timestamp for the session.",
        ),
        _template_row(
            field_id="observer_signoff",
            label="Observer explicitly signed off",
            ready=observer_signoff,
            observed="true" if observer_signoff else "false",
            blocker="observer_signoff_missing",
            required_action="Attach explicit observer signoff for the observed workflow.",
        ),
        _template_row(
            field_id="anonymized_notes_only",
            label="Only anonymized notes are stored",
            ready=anonymized_notes_only,
            observed="true" if anonymized_notes_only else "false",
            blocker="anonymized_notes_only_not_true",
            required_action="Confirm stored notes contain only anonymized/derived metadata.",
        ),
        _template_row(
            field_id="anonymized_summary_present",
            label="Anonymized workflow summary present",
            ready=anonymized_summary_present,
            observed="present" if anonymized_summary_present else "missing",
            blocker="anonymized_summary_missing",
            required_action="Add a derived, anonymized summary of the observed workflow.",
        ),
        _template_row(
            field_id="hidden_state_blockers_absent",
            label="No hidden local state was required",
            ready=hidden_state_blocker_count == 0,
            observed=f"hidden_state_blocker_count={hidden_state_blocker_count}",
            blocker="hidden_state_blockers_present",
            required_action="Resolve or document hidden local-state dependencies before signoff.",
        ),
        _template_row(
            field_id="raw_customer_data_not_stored_in_repo",
            label="Raw customer data is not stored in the repo",
            ready=raw_customer_data_not_stored_in_repo,
            observed="true" if raw_customer_data_not_stored_in_repo else "unverified",
            blocker="raw_customer_data_not_confirmed_outside_repo",
            required_action=(
                "Confirm raw customer data stayed outside the repository and store only "
                "derived/anonymized metadata."
            ),
        ),
        _template_row(
            field_id="customer_retained_raw_data",
            label="Raw data remains customer-retained",
            ready=customer_retained_raw_data,
            observed="true" if customer_retained_raw_data else "unverified",
            blocker="customer_retained_raw_data_not_true",
            required_action="Confirm raw data remained customer-retained during the observation.",
        ),
    ]


def build_developer_preview_new_user_observation_receipt(
    *,
    work_order_json: str | Path = DEFAULT_WORK_ORDER_JSON,
    preflight_json: str | Path = DEFAULT_PREFLIGHT_JSON,
    runbook_md: str | Path = DEFAULT_RUNBOOK_MD,
    observation_input_json: str | Path = "",
    observer_id: str = "",
    observed_at_utc: str = "",
    anonymized_summary: str = "",
    observer_signoff: bool = False,
    anonymized_notes_only: bool = False,
    raw_customer_data_not_stored_in_repo: bool = False,
    customer_retained_raw_data: bool = False,
    hidden_state_blockers: list[str] | None = None,
    root: Path = ROOT,
) -> dict[str, Any]:
    work_order = _summary(_read_json(work_order_json, root=root))
    preflight = _summary(_read_json(preflight_json, root=root))
    runbook_text = _read_text(runbook_md, root=root)
    observation_input_path = _resolve(observation_input_json, root=root) if observation_input_json else None
    observation_input_present = bool(
        observation_input_path and observation_input_path.exists() and observation_input_path.is_file()
    )
    observation_input = (
        _summary(_read_json(observation_input_json, root=root))
        if observation_input_json
        else {}
    )
    observation_input_packet_type = _text(observation_input.get("packet_type"))
    observation_input_schema_version = _text(observation_input.get("schema_version"))
    observation_input_packet_type_valid = bool(
        not observation_input_json
        or (
            observation_input_present
            and observation_input_packet_type == OBSERVATION_INPUT_PACKET_TYPE
        )
    )
    observation_input_schema_version_valid = bool(
        not observation_input_json
        or (
            observation_input_present
            and observation_input_schema_version == OBSERVATION_INPUT_SCHEMA_VERSION
        )
    )
    observation_input_raw_customer_data_allowed = _bool_true(
        observation_input.get("raw_customer_data_allowed")
    )
    observation_input_stores_private_notes = _bool_true(
        observation_input.get("stores_private_notes")
    )
    observation_input_policy_ready = bool(
        not observation_input_raw_customer_data_allowed
        and not observation_input_stores_private_notes
    )
    observation_input_contract_ready = bool(
        not observation_input_json
        or (
            observation_input_present
            and observation_input_packet_type_valid
            and observation_input_schema_version_valid
            and observation_input_policy_ready
        )
    )
    observer_id = _text(observer_id) or _text(observation_input.get("observer_id"))
    observed_at_utc = _text(observed_at_utc) or _text(
        observation_input.get("observed_at_utc")
    )
    anonymized_summary = _text(anonymized_summary) or _text(
        observation_input.get("anonymized_summary")
    )
    observer_signoff = bool(
        observer_signoff or _bool_true(observation_input.get("observer_signoff"))
    )
    anonymized_notes_only = bool(
        anonymized_notes_only
        or _bool_true(observation_input.get("anonymized_notes_only"))
    )
    raw_customer_data_not_stored_in_repo = bool(
        raw_customer_data_not_stored_in_repo
        or _bool_true(observation_input.get("raw_customer_data_not_stored_in_repo"))
    )
    customer_retained_raw_data = bool(
        customer_retained_raw_data
        or _bool_true(observation_input.get("customer_retained_raw_data"))
    )
    hidden_blockers = _split_hidden_blockers(
        [
            *list(hidden_state_blockers or []),
            *_string_list(observation_input.get("hidden_state_blockers")),
        ]
    )

    runbook_present = bool(runbook_text)
    missing_runbook_tokens = [
        token for token in RUNBOOK_REQUIRED_TOKENS if token not in runbook_text
    ]
    runbook_ready = runbook_present and not missing_runbook_tokens
    work_order_ready = (
        work_order.get("status") == "product_execution_work_order_ready"
        and _bool_true(work_order.get("profile_command_generated"))
        and _int(work_order.get("blocker_count")) == 0
    )
    preflight_ready = (
        preflight.get("status") == "product_execution_preflight_ready"
        and _bool_true(preflight.get("validated_without_execution"))
        and _int(preflight.get("blocker_count")) == 0
        and _int(preflight.get("unknown_arg_count")) == 0
    )
    reviewer_present = bool(_text(observer_id))
    observed_at_present = bool(_text(observed_at_utc))
    anonymized_summary_present = bool(_text(anonymized_summary))
    hidden_state_blocker_count = len(hidden_blockers)
    observation_review_template_rows = _observation_review_template_rows(
        reviewer_present=reviewer_present,
        observed_at_present=observed_at_present,
        observer_signoff=observer_signoff,
        anonymized_notes_only=anonymized_notes_only,
        anonymized_summary_present=anonymized_summary_present,
        hidden_state_blocker_count=hidden_state_blocker_count,
        raw_customer_data_not_stored_in_repo=raw_customer_data_not_stored_in_repo,
        customer_retained_raw_data=customer_retained_raw_data,
    )
    observation_review_blocked_rows = [
        row for row in observation_review_template_rows if not row["ready"]
    ]
    observation_review_primary_row = (
        observation_review_blocked_rows[0] if observation_review_blocked_rows else {}
    )

    blockers: list[str] = []
    if not work_order:
        blockers.append(f"{_display(work_order_json, root=root)}:missing")
    elif not work_order_ready:
        blockers.append(f"{_display(work_order_json, root=root)}:work_order_not_ready")
    if not preflight:
        blockers.append(f"{_display(preflight_json, root=root)}:missing")
    elif not preflight_ready:
        blockers.append(f"{_display(preflight_json, root=root)}:preflight_not_ready")
    if observation_input_json and not observation_input_present:
        blockers.append(f"{_display(observation_input_json, root=root)}:missing")
    if observation_input_present and not observation_input_packet_type_valid:
        blockers.append(
            f"{_display(observation_input_json, root=root)}:invalid_packet_type"
        )
    if observation_input_present and not observation_input_schema_version_valid:
        blockers.append(
            f"{_display(observation_input_json, root=root)}:invalid_schema_version"
        )
    if observation_input_present and observation_input_raw_customer_data_allowed:
        blockers.append(
            f"{_display(observation_input_json, root=root)}:raw_customer_data_allowed_true"
        )
    if observation_input_present and observation_input_stores_private_notes:
        blockers.append(
            f"{_display(observation_input_json, root=root)}:stores_private_notes_true"
        )
    if not runbook_present:
        blockers.append(f"{_display(runbook_md, root=root)}:missing")
    elif missing_runbook_tokens:
        blockers.append(
            f"{_display(runbook_md, root=root)}:missing_required_tokens"
        )
    if not reviewer_present:
        blockers.append("observer_id_missing")
    if not observed_at_present:
        blockers.append("observed_at_utc_missing")
    if not observer_signoff:
        blockers.append("observer_signoff_missing")
    if not anonymized_notes_only:
        blockers.append("anonymized_notes_only_not_true")
    if not anonymized_summary_present:
        blockers.append("anonymized_summary_missing")
    if hidden_state_blocker_count:
        blockers.append("hidden_state_blockers_present")
    if not raw_customer_data_not_stored_in_repo:
        blockers.append("raw_customer_data_not_confirmed_outside_repo")
    if not customer_retained_raw_data:
        blockers.append("customer_retained_raw_data_not_true")

    ready = (
        runbook_ready
        and work_order_ready
        and preflight_ready
        and observation_input_contract_ready
        and reviewer_present
        and observed_at_present
        and observer_signoff
        and anonymized_notes_only
        and anonymized_summary_present
        and hidden_state_blocker_count == 0
        and raw_customer_data_not_stored_in_repo
        and customer_retained_raw_data
    )

    rows = [
        {
            "check": "runbook",
            "status": "pass" if runbook_ready else "blocked",
            "artifact_path": _display(runbook_md, root=root),
            "runbook_present": runbook_present,
            "missing_required_token_count": len(missing_runbook_tokens),
            "missing_required_tokens": missing_runbook_tokens,
            "blockers": [
                blocker
                for blocker in blockers
                if _display(runbook_md, root=root) in blocker
            ],
        },
        {
            "check": "work_order",
            "status": "pass" if work_order_ready else "blocked",
            "artifact_path": _display(work_order_json, root=root),
            "source_status": _text(work_order.get("status")),
            "blockers": [blocker for blocker in blockers if _display(work_order_json, root=root) in blocker],
        },
        {
            "check": "preflight",
            "status": "pass" if preflight_ready else "blocked",
            "artifact_path": _display(preflight_json, root=root),
            "source_status": _text(preflight.get("status")),
            "blockers": [blocker for blocker in blockers if _display(preflight_json, root=root) in blocker],
        },
        {
            "check": "observation_input",
            "status": "pass" if observation_input_contract_ready else "blocked",
            "artifact_path": _display(observation_input_json, root=root)
            if observation_input_json
            else "",
            "source_status": _text(observation_input.get("schema_version")),
            "packet_type": observation_input_packet_type,
            "packet_type_valid": observation_input_packet_type_valid,
            "schema_version_valid": observation_input_schema_version_valid,
            "raw_customer_data_allowed": observation_input_raw_customer_data_allowed,
            "stores_private_notes": observation_input_stores_private_notes,
            "observation_input_contract_ready": observation_input_contract_ready,
            "blockers": [
                blocker
                for blocker in blockers
                if observation_input_json
                and _display(observation_input_json, root=root) in blocker
            ],
        },
        {
            "check": "observer_review",
            "status": "pass" if ready else "blocked",
            "observer_id_present": reviewer_present,
            "observed_at_utc_present": observed_at_present,
            "observer_signoff": observer_signoff,
            "anonymized_notes_only": anonymized_notes_only,
            "raw_customer_data_not_stored_in_repo": raw_customer_data_not_stored_in_repo,
            "customer_retained_raw_data": customer_retained_raw_data,
            "hidden_state_blocker_count": hidden_state_blocker_count,
            "blockers": [
                blocker
                for blocker in blockers
                if blocker not in {
                    f"{_display(work_order_json, root=root)}:missing",
                    f"{_display(work_order_json, root=root)}:work_order_not_ready",
                    f"{_display(preflight_json, root=root)}:missing",
                    f"{_display(preflight_json, root=root)}:preflight_not_ready",
                    f"{_display(observation_input_json, root=root)}:missing",
                    f"{_display(runbook_md, root=root)}:missing",
                    f"{_display(runbook_md, root=root)}:missing_required_tokens",
                }
            ],
        },
    ]
    primary_blocker = blockers[0] if blockers else ""
    if ready:
        primary_required_action = ""
    else:
        primary_required_action = _text(
            observation_review_primary_row.get("required_action")
        ) or (
            "Run an observed new-user workflow session, keep raw data outside the repo, and rebuild this "
            "receipt with observer signoff plus anonymized notes only."
        )
    new_user_draft_fail_closed_ready = bool(
        not ready
        and runbook_ready
        and work_order_ready
        and preflight_ready
        and hidden_state_blocker_count == 0
    )
    summary = {
        "packet_type": PACKET_TYPE,
        "schema_version": SCHEMA_VERSION,
        "status": "developer_preview_new_user_observation_receipt_ready"
        if ready
        else "blocked_developer_preview_new_user_observation_receipt",
        "new_user_observation_ready": ready,
        "observation_ready": ready,
        "new_user_draft_fail_closed_ready": new_user_draft_fail_closed_ready,
        "observer_signoff": observer_signoff,
        "anonymized_notes_only": anonymized_notes_only,
        "blocker_count": len(blockers),
        "primary_blocker": primary_blocker,
        "primary_required_action": primary_required_action,
        "blockers": blockers,
        "hidden_state_blocker_count": hidden_state_blocker_count,
        "hidden_state_blockers": hidden_blockers,
        "observation_input_json": _display(observation_input_json, root=root)
        if observation_input_json
        else "",
        "observation_input_json_present": observation_input_present,
        "observation_input_packet_type": observation_input_packet_type,
        "observation_input_packet_type_valid": observation_input_packet_type_valid,
        "observation_input_schema_version": observation_input_schema_version,
        "observation_input_schema_version_valid": observation_input_schema_version_valid,
        "observation_input_template_schema_version": OBSERVATION_INPUT_SCHEMA_VERSION,
        "observation_input_template_json": DEFAULT_OUT_OBSERVATION_INPUT_TEMPLATE_JSON,
        "new_user_final_observation_input_json": DEFAULT_OBSERVATION_INPUT_JSON,
        "new_user_final_required_input_artifact": DEFAULT_OBSERVATION_INPUT_JSON,
        "new_user_final_command_target": "new-user-final",
        "new_user_draft_command_target": "new-user-draft",
        "new_user_observation_template_next_action": (
            "Copy the generated observation input template to "
            f"{DEFAULT_OBSERVATION_INPUT_JSON}, fill only derived/anonymized "
            "observer metadata, then run the new-user-final command-pack target."
        ),
        "observation_input_contract_ready": observation_input_contract_ready,
        "observation_input_raw_customer_data_allowed": observation_input_raw_customer_data_allowed,
        "observation_input_stores_private_notes": observation_input_stores_private_notes,
        "observation_input_policy_ready": observation_input_policy_ready,
        "runbook_path": _display(runbook_md, root=root),
        "runbook_ready": runbook_ready,
        "runbook_required_tokens": list(RUNBOOK_REQUIRED_TOKENS),
        "runbook_required_token_count": len(RUNBOOK_REQUIRED_TOKENS),
        "runbook_missing_required_tokens": missing_runbook_tokens,
        "runbook_missing_required_token_count": len(missing_runbook_tokens),
        "core_workflow_receipt_path_documented": all(
            token not in missing_runbook_tokens
            for token in CORE_WORKFLOW_RECEIPT_PATH_TOKENS
        ),
        "core_workflow_command_set_documented": all(
            token not in missing_runbook_tokens
            for token in CORE_WORKFLOW_COMMAND_TOKENS
        ),
        "developer_preview_exit_receipt_path_documented": all(
            token not in missing_runbook_tokens
            for token in DEVELOPER_PREVIEW_EXIT_RECEIPT_PATH_TOKENS
        ),
        "developer_preview_exit_command_set_documented": all(
            token not in missing_runbook_tokens
            for token in DEVELOPER_PREVIEW_EXIT_COMMAND_TOKENS
        ),
        "observation_checklist_path_documented": all(
            token not in missing_runbook_tokens
            for token in OBSERVATION_CHECKLIST_PATH_TOKENS
        ),
        "clean_checkout_bootstrap_documented": all(
            token not in missing_runbook_tokens for token in BOOTSTRAP_COMMAND_TOKENS
        ),
        "linux_bootstrap_command_set_documented": all(
            token not in missing_runbook_tokens for token in LINUX_BOOTSTRAP_COMMAND_TOKENS
        ),
        "windows_bootstrap_command_set_documented": all(
            token not in missing_runbook_tokens for token in WINDOWS_BOOTSTRAP_COMMAND_TOKENS
        ),
        "clean_checkout_receipt_path_documented": (
            ".betelgeuze/developer_preview_clean_checkout_benchmark_receipt.json"
            not in missing_runbook_tokens
        ),
        "platform_reproducibility_receipt_paths_documented": all(
            token not in missing_runbook_tokens
            for token in (
                ".betelgeuze/developer_preview_linux_reproducibility_receipt.json",
                ".betelgeuze/developer_preview_windows_reproducibility_receipt.json",
            )
        ),
        "observation_review_required_field_ids": list(
            OBSERVATION_REVIEW_REQUIRED_FIELD_IDS
        ),
        "observation_review_required_field_count": len(
            OBSERVATION_REVIEW_REQUIRED_FIELD_IDS
        ),
        "observation_review_ready_field_count": (
            len(observation_review_template_rows) - len(observation_review_blocked_rows)
        ),
        "observation_review_blocked_field_count": len(observation_review_blocked_rows),
        "observation_review_primary_field_id": _text(
            observation_review_primary_row.get("field_id")
        ),
        "observation_review_primary_blocker": _text(
            observation_review_primary_row.get("blocker")
        ),
        "observation_review_primary_required_action": _text(
            observation_review_primary_row.get("required_action")
        ),
        "work_order_ready": work_order_ready,
        "preflight_ready": preflight_ready,
        "observer_id_present": reviewer_present,
        "observed_at_utc_present": observed_at_present,
        "anonymized_summary_present": anonymized_summary_present,
        "raw_customer_data_not_stored_in_repo": raw_customer_data_not_stored_in_repo,
        "raw_customer_data_storage_unverified": not raw_customer_data_not_stored_in_repo,
        "raw_customer_data_stored_in_repo": False,
        "customer_retained_raw_data": customer_retained_raw_data,
        "execution_enabled": False,
        "external_state_mutated": False,
        "claim_promotion_allowed": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": "Attach this observation receipt to the Developer Preview final gate audit."
        if ready
        else primary_required_action,
    }
    return {
        "summary": summary,
        "rows": rows,
        "observation_review_template_rows": observation_review_template_rows,
    }


def _write_json(path_like: str | Path, payload: dict[str, Any], *, root: Path = ROOT) -> None:
    path = _resolve(path_like, root=root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _render_md(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# Developer Preview New-User Observation Receipt",
        "",
        f"- status: `{summary['status']}`",
        f"- runbook_ready: `{summary['runbook_ready']}`",
        f"- runbook_missing_required_token_count: `{summary['runbook_missing_required_token_count']}`",
        f"- observation_input_json: `{summary['observation_input_json']}`",
        f"- observation_input_json_present: `{summary['observation_input_json_present']}`",
        f"- observation_input_template_json: `{summary['observation_input_template_json']}`",
        f"- new_user_final_required_input_artifact: `{summary['new_user_final_required_input_artifact']}`",
        f"- new_user_observation_template_next_action: {summary['new_user_observation_template_next_action']}",
        f"- observation_input_contract_ready: `{summary['observation_input_contract_ready']}`",
        f"- observation_input_packet_type_valid: `{summary['observation_input_packet_type_valid']}`",
        f"- observation_input_schema_version_valid: `{summary['observation_input_schema_version_valid']}`",
        f"- observation_input_policy_ready: `{summary['observation_input_policy_ready']}`",
        f"- observation_input_template_schema_version: `{summary['observation_input_template_schema_version']}`",
        f"- observation_checklist_path_documented: `{summary['observation_checklist_path_documented']}`",
        f"- observer_signoff: `{summary['observer_signoff']}`",
        f"- anonymized_notes_only: `{summary['anonymized_notes_only']}`",
        f"- raw_customer_data_not_stored_in_repo: `{summary['raw_customer_data_not_stored_in_repo']}`",
        f"- customer_retained_raw_data: `{summary['customer_retained_raw_data']}`",
        f"- blocker_count: `{summary['blocker_count']}`",
        f"- primary_blocker: `{summary['primary_blocker'] or '-'}`",
        f"- primary_required_action: {summary['primary_required_action'] or '-'}",
        f"- hidden_state_blocker_count: `{summary['hidden_state_blocker_count']}`",
        f"- observation_review_blocked_field_count: `{summary['observation_review_blocked_field_count']}`",
        f"- raw_customer_data_stored_in_repo: `{summary['raw_customer_data_stored_in_repo']}`",
        "",
        "| check | status | blockers |",
        "| --- | --- | --- |",
    ]
    for row in payload["rows"]:
        blockers = ";".join(str(item) for item in row.get("blockers", [])) or "-"
        lines.append(f"| `{row['check']}` | `{row['status']}` | `{blockers}` |")
    lines.extend(
        [
            "",
            "## Observation Review Template",
            "",
            "| field | status | observed | blocker | action |",
            "| --- | --- | --- | --- | --- |",
        ]
    )
    for row in payload.get("observation_review_template_rows", []):
        lines.append(
            f"| `{row['field_id']}` | `{row['status']}` | `{row['observed']}` | "
            f"`{row['blocker'] or '-'}` | {row['required_action'] or '-'} |"
        )
    lines.extend(["", CLAIM_BOUNDARY, ""])
    return "\n".join(lines)


def _write_text(path_like: str | Path, text: str, *, root: Path = ROOT) -> None:
    path = _resolve(path_like, root=root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_checklist_csv(
    path_like: str | Path,
    payload: dict[str, Any],
    *,
    root: Path = ROOT,
) -> None:
    path = _resolve(path_like, root=root)
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "field_id",
        "label",
        "status",
        "ready",
        "observed",
        "blocker",
        "required_action",
        "raw_customer_data_allowed",
        "stores_private_notes",
        "operator_action_required",
    ]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in payload.get("observation_review_template_rows", []):
            writer.writerow({key: row.get(key, "") for key in fieldnames})


def _render_checklist_md(payload: dict[str, Any]) -> str:
    lines = [
        "# Developer Preview New-User Observation Checklist",
        "",
        "Record only derived/anonymized operator metadata here. Raw customer data and private notes stay outside this repository.",
        "",
        "| field | status | observed | blocker | action |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in payload.get("observation_review_template_rows", []):
        lines.append(
            f"| `{row['field_id']}` | `{row['status']}` | `{row['observed']}` | "
            f"`{row['blocker'] or '-'}` | {row['required_action'] or '-'} |"
        )
    lines.extend(["", CLAIM_BOUNDARY, ""])
    return "\n".join(lines)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build a Developer Preview new-user observation receipt.")
    parser.add_argument("--work-order-json", default=DEFAULT_WORK_ORDER_JSON)
    parser.add_argument("--preflight-json", default=DEFAULT_PREFLIGHT_JSON)
    parser.add_argument("--runbook-md", default=DEFAULT_RUNBOOK_MD)
    parser.add_argument("--observation-input-json", default="")
    parser.add_argument("--observer-id", default="")
    parser.add_argument("--observed-at-utc", default="")
    parser.add_argument("--anonymized-summary", default="")
    parser.add_argument("--observer-signoff", action="store_true")
    parser.add_argument("--anonymized-notes-only", action="store_true")
    parser.add_argument("--raw-customer-data-not-stored-in-repo", action="store_true")
    parser.add_argument("--customer-retained-raw-data", action="store_true")
    parser.add_argument("--hidden-state-blocker", action="append", default=[])
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    parser.add_argument("--out-checklist-csv", default=DEFAULT_OUT_CHECKLIST_CSV)
    parser.add_argument("--out-checklist-md", default=DEFAULT_OUT_CHECKLIST_MD)
    parser.add_argument(
        "--out-observation-input-template-json",
        default=DEFAULT_OUT_OBSERVATION_INPUT_TEMPLATE_JSON,
    )
    parser.add_argument(
        "--allow-blocked",
        action="store_true",
        help="Write a fail-closed blocked receipt and return success so the operator can continue rebuilding the final audit.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    payload = build_developer_preview_new_user_observation_receipt(
        work_order_json=args.work_order_json,
        preflight_json=args.preflight_json,
        runbook_md=args.runbook_md,
        observation_input_json=args.observation_input_json,
        observer_id=args.observer_id,
        observed_at_utc=args.observed_at_utc,
        anonymized_summary=args.anonymized_summary,
        observer_signoff=args.observer_signoff,
        anonymized_notes_only=args.anonymized_notes_only,
        raw_customer_data_not_stored_in_repo=args.raw_customer_data_not_stored_in_repo,
        customer_retained_raw_data=args.customer_retained_raw_data,
        hidden_state_blockers=list(args.hidden_state_blocker or []),
    )
    payload["summary"]["observation_input_template_json"] = _display(
        args.out_observation_input_template_json
    )
    _write_json(args.out_json, payload)
    _write_text(args.out_md, _render_md(payload))
    _write_checklist_csv(args.out_checklist_csv, payload)
    _write_text(args.out_checklist_md, _render_checklist_md(payload))
    _write_json(args.out_observation_input_template_json, _observation_input_template_payload())
    if payload["summary"]["status"] == "developer_preview_new_user_observation_receipt_ready":
        return 0
    return 0 if args.allow_blocked else 1


if __name__ == "__main__":
    raise SystemExit(main())

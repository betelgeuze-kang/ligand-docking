#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]

DEFAULT_REGISTER_MD = "docs/developer_preview_final_gate_action_register.md"
DEFAULT_OUT_JSON = "runs/developer_preview_final_gate_audit_current.json"
DEFAULT_OUT_CSV = "runs/developer_preview_final_gate_audit_current.csv"
DEFAULT_OUT_MD = "runs/developer_preview_final_gate_audit_current.md"
DEFAULT_OUT_OPERATOR_WORK_ORDER_JSON = (
    "runs/developer_preview_external_operator_work_order_current.json"
)
DEFAULT_OUT_OPERATOR_WORK_ORDER_CSV = (
    "runs/developer_preview_external_operator_work_order_current.csv"
)
DEFAULT_OUT_OPERATOR_WORK_ORDER_MD = (
    "runs/developer_preview_external_operator_work_order_current.md"
)
DEFAULT_OUT_OPERATOR_COMMAND_PACK_JSON = (
    "runs/developer_preview_external_operator_command_pack_current.json"
)
DEFAULT_OUT_OPERATOR_COMMAND_PACK_SH = (
    "runs/developer_preview_external_operator_command_pack_current.sh"
)
DEFAULT_OUT_OPERATOR_COMMAND_PACK_PS1 = (
    "runs/developer_preview_external_operator_command_pack_current.ps1"
)
DEFAULT_OUT_OPERATOR_COMMAND_PACK_MD = (
    "runs/developer_preview_external_operator_command_pack_current.md"
)
DEFAULT_CORE_WORKFLOW_RUNBOOK_MD = "docs/developer_preview_core_workflow_quickstart.md"
DEFAULT_STAGE5_INPUT_FAMILY_CSV = (
    ".betelgeuze/developer_preview_clean_checkout_stage5_input_family_current.csv"
)
DEFAULT_STAGE5_INPUT_FAMILY_MD = (
    ".betelgeuze/developer_preview_clean_checkout_stage5_input_family_current.md"
)
DEFAULT_CLEAN_CHECKOUT_SOURCE_PROVENANCE_JSON = (
    ".betelgeuze/developer_preview_clean_checkout_source_provenance.json"
)
DEFAULT_STAGE5_RESTORE_PACKET_JSON = (
    "runs/developer_preview_stage5_restore_packet_current.json"
)
DEFAULT_STAGE5_RESTORE_PACKET_CSV = (
    "runs/developer_preview_stage5_restore_packet_current.csv"
)
DEFAULT_STAGE5_RESTORE_PACKET_MD = (
    "runs/developer_preview_stage5_restore_packet_current.md"
)
DEFAULT_NEW_USER_OBSERVATION_INPUT_TEMPLATE_JSON = (
    ".betelgeuze/developer_preview_new_user_observation_input_template.json"
)
DEFAULT_NEW_USER_OBSERVATION_INPUT_JSON = (
    ".betelgeuze/developer_preview_new_user_observation_input.json"
)
DEFAULT_NEW_USER_OBSERVATION_RECEIPT_JSON = (
    ".betelgeuze/developer_preview_new_user_observation_receipt.json"
)
DEFAULT_NEW_USER_OBSERVATION_CHECKLIST_CSV = (
    ".betelgeuze/developer_preview_new_user_observation_checklist.csv"
)
DEFAULT_NEW_USER_OBSERVATION_CHECKLIST_MD = (
    ".betelgeuze/developer_preview_new_user_observation_checklist.md"
)

PACKET_TYPE = "developer_preview_final_gate_audit"
SCHEMA_VERSION = "developer_preview_final_gate_audit_v1"
OPERATOR_WORK_ORDER_PACKET_TYPE = "developer_preview_external_operator_work_order"
OPERATOR_WORK_ORDER_SCHEMA_VERSION = "developer_preview_external_operator_work_order_v1"
OPERATOR_COMMAND_PACK_PACKET_TYPE = "developer_preview_external_operator_command_pack"
OPERATOR_COMMAND_PACK_SCHEMA_VERSION = "developer_preview_external_operator_command_pack_v1"

CLAIM_BOUNDARY = (
    "Developer Preview final gate audit only; it reads local reviewed receipt artifacts for the six "
    "Developer Preview gates and fails closed when receipts are missing or incomplete. It does not run "
    "clean checkouts, execute benchmarks, run Vina/GNINA, approve reviews, promote paid-pilot wording, "
    "upload, email, deploy, or mutate external state."
)

STAGE5_REQUIRED_ARGUMENTS = [
    "--scores-csv",
    "--labels-csv",
    "--split-csv",
    "--expected-keys-csv",
]

REGISTER_FAIL_CLOSED_REQUIRED_TOKENS = [
    "tools/product/build_developer_preview_clean_checkout_benchmark_receipt.py",
    "bash runs/developer_preview_external_operator_command_pack_current.sh clean-checkout",
    "DEVELOPER_PREVIEW_REPO_URL",
    "write_clean_checkout_source_provenance",
    "--checkout-provenance-json .betelgeuze/developer_preview_clean_checkout_source_provenance.json",
    "clean_checkout_provenance_ready",
    "clean_checkout_source_repo_url_present",
    "clean_checkout_working_tree_clean",
    "stage5_input_family_ready",
    "clean_checkout_dirty_path_count",
    "stage5_missing_source_artifact_count",
    "stage5_incomplete_task_count",
    "tools/product/build_developer_preview_platform_reproducibility_receipt.py --platform linux",
    "tools/product/build_developer_preview_platform_reproducibility_receipt.py --platform windows",
    "shell_platform_guard_accepts_git_bash_windows",
    "tools/product/build_developer_preview_new_user_observation_receipt.py",
    "--allow-blocked --out-json .betelgeuze/developer_preview_clean_checkout_benchmark_receipt.json",
    "stage5-recovery",
    "tools/product/build_developer_preview_stage5_restore_packet.py",
    "runs/developer_preview_stage5_restore_packet_current.json",
    "--ai-verify-log .betelgeuze/developer_preview_linux_ai_verify.log",
    "--pytest-junit-xml .betelgeuze/developer_preview_linux_reproducibility_pytest.xml",
    "--platform linux --ai-verify-log .betelgeuze/developer_preview_linux_ai_verify.log --pytest-junit-xml .betelgeuze/developer_preview_linux_reproducibility_pytest.xml --allow-blocked --out-json .betelgeuze/developer_preview_linux_reproducibility_receipt.json",
    "--ai-verify-log .betelgeuze/developer_preview_windows_ai_verify.log",
    "--pytest-junit-xml .betelgeuze/developer_preview_windows_reproducibility_pytest.xml",
    "--platform windows --ai-verify-log .betelgeuze/developer_preview_windows_ai_verify.log --pytest-junit-xml .betelgeuze/developer_preview_windows_reproducibility_pytest.xml --allow-blocked --out-json .betelgeuze/developer_preview_windows_reproducibility_receipt.json",
    "--observation-input-json .betelgeuze/developer_preview_new_user_observation_input.json",
    "--out-observation-input-template-json .betelgeuze/developer_preview_new_user_observation_input_template.json",
    "--out-checklist-csv .betelgeuze/developer_preview_new_user_observation_checklist.csv",
    "--out-checklist-md .betelgeuze/developer_preview_new_user_observation_checklist.md",
]

EXTERNAL_OPERATOR_WORK_ORDER_SPECS = [
    {
        "operator_flow_id": "clean_checkout_benchmark_receipt",
        "gate_id": "benchmark_results_clean_checkout_regenerated",
        "label": "Clean checkout benchmark receipt",
        "required_platform": "fresh local clone",
        "runbook_section": "Gate A: Clean Checkout Benchmark Receipt",
        "primary_receipt_artifact": ".betelgeuze/developer_preview_clean_checkout_benchmark_receipt.json",
        "required_receipt_artifacts": [
            ".betelgeuze/developer_preview_clean_checkout_benchmark_receipt.json",
        ],
        "supporting_artifacts": [
            DEFAULT_CLEAN_CHECKOUT_SOURCE_PROVENANCE_JSON,
            ".betelgeuze/developer_preview_clean_checkout_ai_verify.log",
            (
                ".betelgeuze/developer_preview_external_baselines/"
                "biorxiv_baseline_comparison_developer_preview_clean_checkout/summary.json"
            ),
            DEFAULT_STAGE5_INPUT_FAMILY_CSV,
            DEFAULT_STAGE5_INPUT_FAMILY_MD,
        ],
        "fail_closed_command_token": (
            "tools/product/build_developer_preview_clean_checkout_benchmark_receipt.py "
            "--allow-blocked"
        ),
        "required_action": (
            "Run Gate A from a fresh clone, keep the ai-verify log and baseline summary, "
            "then rebuild the reviewed clean-checkout benchmark receipt."
        ),
    },
    {
        "operator_flow_id": "linux_reproducibility_receipt",
        "gate_id": "linux_windows_reproducibility_confirmed",
        "label": "Linux reproducibility receipt",
        "required_platform": "Linux checkout",
        "runbook_section": "Gate E: Linux Reproducibility Receipt",
        "primary_receipt_artifact": ".betelgeuze/developer_preview_linux_reproducibility_receipt.json",
        "required_receipt_artifacts": [
            ".betelgeuze/developer_preview_linux_reproducibility_receipt.json",
        ],
        "supporting_artifacts": [
            ".betelgeuze/developer_preview_linux_ai_verify.log",
            ".betelgeuze/developer_preview_linux_reproducibility_pytest.xml",
        ],
        "fail_closed_command_token": (
            "tools/product/build_developer_preview_platform_reproducibility_receipt.py "
            "--platform linux --allow-blocked"
        ),
        "required_action": (
            "Run the documented Linux command set and rebuild the platform receipt with "
            "captured ai-verify and pytest evidence."
        ),
    },
    {
        "operator_flow_id": "windows_reproducibility_receipt",
        "gate_id": "linux_windows_reproducibility_confirmed",
        "label": "Windows reproducibility receipt",
        "required_platform": "Windows checkout",
        "runbook_section": "Gate E: Windows Reproducibility Receipt",
        "primary_receipt_artifact": ".betelgeuze/developer_preview_windows_reproducibility_receipt.json",
        "required_receipt_artifacts": [
            ".betelgeuze/developer_preview_windows_reproducibility_receipt.json",
        ],
        "supporting_artifacts": [
            ".betelgeuze/developer_preview_windows_ai_verify.log",
            ".betelgeuze/developer_preview_windows_reproducibility_pytest.xml",
        ],
        "fail_closed_command_token": (
            "tools/product/build_developer_preview_platform_reproducibility_receipt.py "
            "--platform windows --allow-blocked"
        ),
        "required_action": (
            "Run the same documented command set on Windows and rebuild the Windows receipt; "
            "do not copy a Linux receipt into the Windows slot."
        ),
    },
    {
        "operator_flow_id": "new_user_observation_receipt",
        "gate_id": "new_user_core_workflow_observation_passed",
        "label": "New-user workflow observation receipt",
        "required_platform": "observed local user session",
        "runbook_section": "Gate F: New-User Observation Receipt",
        "primary_receipt_artifact": ".betelgeuze/developer_preview_new_user_observation_receipt.json",
        "required_receipt_artifacts": [
            ".betelgeuze/developer_preview_new_user_execution_work_order.json",
            ".betelgeuze/developer_preview_new_user_execution_preflight.json",
            ".betelgeuze/developer_preview_new_user_observation_receipt.json",
        ],
        "supporting_artifacts": [
            DEFAULT_CORE_WORKFLOW_RUNBOOK_MD,
            DEFAULT_NEW_USER_OBSERVATION_INPUT_TEMPLATE_JSON,
            DEFAULT_NEW_USER_OBSERVATION_INPUT_JSON,
        ],
        "fail_closed_command_token": (
            "tools/product/build_developer_preview_new_user_observation_receipt.py "
            "--allow-blocked"
        ),
        "required_action": (
            "Run the work-order and preflight path with a new technical user, then rebuild "
            "the observation receipt with anonymized observer signoff only."
        ),
    },
]

CSV_FIELDS = [
    "priority",
    "gate_id",
    "status",
    "ready",
    "receipt_artifacts",
    "present_receipt_count",
    "required_receipt_count",
    "primary_metric",
    "secondary_metric",
    "blocker",
    "next_required_step",
    "execution_enabled",
    "external_state_mutated",
    "claim_promotion_allowed",
]

OPERATOR_WORK_ORDER_CSV_FIELDS = [
    "operator_flow_id",
    "gate_id",
    "label",
    "status",
    "ready",
    "required_platform",
    "runbook_path",
    "runbook_section",
    "action_register_path",
    "primary_receipt_artifact",
    "required_receipt_artifacts",
    "supporting_artifacts",
    "present_receipt_count",
    "required_receipt_count",
    "primary_receipt_status",
    "primary_receipt_present",
    "fail_closed_command_token",
    "blocker",
    "receipt_blockers",
    "receipt_blocker_count",
    "source_blocker_count",
    "required_action",
    "next_required_step",
    "operator_action_required",
    "execution_enabled",
    "external_state_mutated",
    "claim_promotion_allowed",
]


def _command_row(
    *,
    target: str,
    operator_flow_id: str,
    label: str,
    required_platform: str,
    receipt_artifacts: list[str],
    commands: list[str],
    required_env_vars: list[str] | None = None,
    required_input_artifacts: list[str] | None = None,
    platform_guard: str = "",
) -> dict[str, Any]:
    env_vars = list(required_env_vars or [])
    input_artifacts = list(required_input_artifacts or [])
    export_command = "export_artifacts " + " ".join(
        [f'"{target}"', *(f'"{artifact}"' for artifact in receipt_artifacts)]
    )
    commands_with_export = [*commands, export_command]
    return {
        "target": target,
        "operator_flow_id": operator_flow_id,
        "label": label,
        "required_platform": required_platform,
        "platform_guard": platform_guard,
        "receipt_artifacts": receipt_artifacts,
        "required_input_artifacts": input_artifacts,
        "required_input_artifact_count": len(input_artifacts),
        "required_env_vars": env_vars,
        "required_env_var_count": len(env_vars),
        "commands": commands_with_export,
        "command_count": len(commands_with_export),
        "optional_export_env_var": "DEVELOPER_PREVIEW_EXPORT_DIR",
        "execution_enabled": False,
        "external_state_mutated": False,
        "claim_promotion_allowed": False,
        "claim_boundary": CLAIM_BOUNDARY,
    }


def _external_operator_command_rows() -> list[dict[str, Any]]:
    return [
        _command_row(
            target="clean-checkout",
            operator_flow_id="clean_checkout_benchmark_receipt",
            label="Clean checkout benchmark receipt",
            required_platform="fresh local clone",
            receipt_artifacts=[
                DEFAULT_CLEAN_CHECKOUT_SOURCE_PROVENANCE_JSON,
                ".betelgeuze/developer_preview_clean_checkout_ai_verify.log",
                (
                    ".betelgeuze/developer_preview_external_baselines/"
                    "biorxiv_baseline_comparison_developer_preview_clean_checkout/summary.json"
                ),
                ".betelgeuze/developer_preview_external_baselines/developer_preview_clean_checkout_status.txt",
                ".betelgeuze/developer_preview_clean_checkout_benchmark_receipt.json",
                DEFAULT_STAGE5_INPUT_FAMILY_CSV,
                DEFAULT_STAGE5_INPUT_FAMILY_MD,
            ],
            required_env_vars=[
                "DEVELOPER_PREVIEW_REPO_URL",
                "DEVELOPER_PREVIEW_REVIEWER_ID",
                "DEVELOPER_PREVIEW_REVIEWED_AT_UTC",
            ],
            commands=[
                (
                    'workdir="$(resolve_clean_checkout_workdir)" '
                    '&& git clone --no-hardlinks "${DEVELOPER_PREVIEW_REPO_URL}" "$workdir" '
                    '&& cd "$workdir"'
                ),
                (
                    'if [[ -n "${DEVELOPER_PREVIEW_REF:-}" ]]; then '
                    'git fetch origin "${DEVELOPER_PREVIEW_REF}" '
                    '&& git checkout --detach FETCH_HEAD; fi'
                ),
                '"${PYTHON_BIN}" -m venv .venv',
                ". .venv/bin/activate",
                "python -m pip install --upgrade pip",
                "python -m pip install -r requirements.txt -r requirements-dev.txt",
                "mkdir -p .betelgeuze",
                f"write_clean_checkout_source_provenance {DEFAULT_CLEAN_CHECKOUT_SOURCE_PROVENANCE_JSON}",
                (
                    "bash -o pipefail -c "
                    "'./scripts/ai-verify.sh | tee .betelgeuze/developer_preview_clean_checkout_ai_verify.log'"
                ),
                (
                    "baseline_status=.betelgeuze/developer_preview_external_baselines/"
                    "developer_preview_clean_checkout_status.txt; "
                    "mkdir -p \"$(dirname \"$baseline_status\")\"; "
                    "set +e; "
                    "python tools/run_external_validation_baselines.py "
                    "--spec-json config/external_validation_baselines_v1.json "
                    "--current-meta-json runs/biorxiv_external_validation_package_current.json "
                    "--out-root .betelgeuze/developer_preview_external_baselines "
                    "--label developer_preview_clean_checkout --no-rerun-current --require-tasks; "
                    "baseline_rc=$?; set -e; "
                    "printf 'run_external_validation_baselines_exit_code=%s\\n' \"$baseline_rc\" "
                    "> \"$baseline_status\""
                ),
                (
                    "python tools/product/build_developer_preview_clean_checkout_benchmark_receipt.py "
                    "--ai-verify-log .betelgeuze/developer_preview_clean_checkout_ai_verify.log "
                    "--baseline-summary-json "
                    ".betelgeuze/developer_preview_external_baselines/"
                    "biorxiv_baseline_comparison_developer_preview_clean_checkout/summary.json "
                    f"--checkout-provenance-json {DEFAULT_CLEAN_CHECKOUT_SOURCE_PROVENANCE_JSON} "
                    "--reviewed-receipt-attached "
                    '--reviewer-id "${DEVELOPER_PREVIEW_REVIEWER_ID}" '
                    '--reviewed-at-utc "${DEVELOPER_PREVIEW_REVIEWED_AT_UTC}" '
                    "--allow-blocked "
                    "--out-json .betelgeuze/developer_preview_clean_checkout_benchmark_receipt.json "
                    "--out-md .betelgeuze/developer_preview_clean_checkout_benchmark_receipt.md "
                    f"--out-stage5-input-family-csv {DEFAULT_STAGE5_INPUT_FAMILY_CSV} "
                    f"--out-stage5-input-family-md {DEFAULT_STAGE5_INPUT_FAMILY_MD}"
                ),
            ],
        ),
        _command_row(
            target="stage5-recovery",
            operator_flow_id="clean_checkout_stage5_source_recovery",
            label="Clean checkout stage5 source recovery handoff",
            required_platform="current checkout",
            receipt_artifacts=[
                ".betelgeuze/developer_preview_clean_checkout_benchmark_receipt.json",
                DEFAULT_STAGE5_INPUT_FAMILY_CSV,
                DEFAULT_STAGE5_INPUT_FAMILY_MD,
                DEFAULT_OUT_JSON,
                DEFAULT_OUT_MD,
                DEFAULT_OUT_OPERATOR_WORK_ORDER_JSON,
                DEFAULT_OUT_OPERATOR_WORK_ORDER_CSV,
                DEFAULT_OUT_OPERATOR_WORK_ORDER_MD,
                DEFAULT_STAGE5_RESTORE_PACKET_JSON,
                DEFAULT_STAGE5_RESTORE_PACKET_CSV,
                DEFAULT_STAGE5_RESTORE_PACKET_MD,
            ],
            required_input_artifacts=[
                ".betelgeuze/developer_preview_clean_checkout_benchmark_receipt.json",
                DEFAULT_STAGE5_INPUT_FAMILY_CSV,
                DEFAULT_STAGE5_INPUT_FAMILY_MD,
            ],
            commands=[
                (
                    '"${PYTHON_BIN}" tools/product/build_developer_preview_stage5_restore_packet.py '
                    f"--stage5-input-family-csv {DEFAULT_STAGE5_INPUT_FAMILY_CSV} "
                    f"--out-json {DEFAULT_STAGE5_RESTORE_PACKET_JSON} "
                    f"--out-csv {DEFAULT_STAGE5_RESTORE_PACKET_CSV} "
                    f"--out-md {DEFAULT_STAGE5_RESTORE_PACKET_MD}"
                ),
                (
                    '"${PYTHON_BIN}" tools/product/build_developer_preview_final_gate_audit.py '
                    f"--out-json {DEFAULT_OUT_JSON} "
                    f"--out-csv {DEFAULT_OUT_CSV} "
                    f"--out-md {DEFAULT_OUT_MD} "
                    f"--out-operator-work-order-json {DEFAULT_OUT_OPERATOR_WORK_ORDER_JSON} "
                    f"--out-operator-work-order-csv {DEFAULT_OUT_OPERATOR_WORK_ORDER_CSV} "
                    f"--out-operator-work-order-md {DEFAULT_OUT_OPERATOR_WORK_ORDER_MD} "
                    f"--out-operator-command-pack-json {DEFAULT_OUT_OPERATOR_COMMAND_PACK_JSON} "
                    f"--out-operator-command-pack-sh {DEFAULT_OUT_OPERATOR_COMMAND_PACK_SH} "
                    f"--out-operator-command-pack-ps1 {DEFAULT_OUT_OPERATOR_COMMAND_PACK_PS1} "
                    f"--out-operator-command-pack-md {DEFAULT_OUT_OPERATOR_COMMAND_PACK_MD}"
                ),
            ],
        ),
        _command_row(
            target="linux-repro",
            operator_flow_id="linux_reproducibility_receipt",
            label="Linux reproducibility receipt",
            required_platform="Linux checkout",
            platform_guard="linux",
            receipt_artifacts=[
                ".betelgeuze/developer_preview_linux_ai_verify.log",
                ".betelgeuze/developer_preview_linux_reproducibility_pytest.xml",
                ".betelgeuze/developer_preview_linux_reproducibility_receipt.json",
            ],
            commands=[
                "mkdir -p .betelgeuze",
                (
                    "bash -o pipefail -c "
                    "'./scripts/ai-verify.sh | tee .betelgeuze/developer_preview_linux_ai_verify.log'"
                ),
                (
                    '"${PYTHON_BIN}" -m pytest -q '
                    "tests/unit/test_betelgeuze_product_readiness.py "
                    "tests/unit/test_betelgeuze_product_cli.py "
                    "tests/unit/test_betelgeuze_cameo_cli.py "
                    "tests/unit/test_betelgeuze_cleanup_cli.py "
                    "--junitxml .betelgeuze/developer_preview_linux_reproducibility_pytest.xml"
                ),
                (
                    '"${PYTHON_BIN}" tools/product/build_developer_preview_platform_reproducibility_receipt.py '
                    "--platform linux "
                    "--ai-verify-log .betelgeuze/developer_preview_linux_ai_verify.log "
                    "--pytest-junit-xml .betelgeuze/developer_preview_linux_reproducibility_pytest.xml "
                    "--allow-blocked "
                    "--out-json .betelgeuze/developer_preview_linux_reproducibility_receipt.json "
                    "--out-md .betelgeuze/developer_preview_linux_reproducibility_receipt.md"
                ),
            ],
        ),
        _command_row(
            target="windows-repro",
            operator_flow_id="windows_reproducibility_receipt",
            label="Windows reproducibility receipt",
            required_platform="Windows checkout",
            platform_guard="windows",
            receipt_artifacts=[
                ".betelgeuze/developer_preview_windows_ai_verify.log",
                ".betelgeuze/developer_preview_windows_reproducibility_pytest.xml",
                ".betelgeuze/developer_preview_windows_reproducibility_receipt.json",
            ],
            commands=[
                "mkdir -p .betelgeuze",
                (
                    "bash -o pipefail -c "
                    "'./scripts/ai-verify.sh | tee .betelgeuze/developer_preview_windows_ai_verify.log'"
                ),
                (
                    '"${PYTHON_BIN}" -m pytest -q '
                    "tests/unit/test_betelgeuze_product_readiness.py "
                    "tests/unit/test_betelgeuze_product_cli.py "
                    "tests/unit/test_betelgeuze_cameo_cli.py "
                    "tests/unit/test_betelgeuze_cleanup_cli.py "
                    "--junitxml .betelgeuze/developer_preview_windows_reproducibility_pytest.xml"
                ),
                (
                    '"${PYTHON_BIN}" tools/product/build_developer_preview_platform_reproducibility_receipt.py '
                    "--platform windows "
                    "--ai-verify-log .betelgeuze/developer_preview_windows_ai_verify.log "
                    "--pytest-junit-xml .betelgeuze/developer_preview_windows_reproducibility_pytest.xml "
                    "--allow-blocked "
                    "--out-json .betelgeuze/developer_preview_windows_reproducibility_receipt.json "
                    "--out-md .betelgeuze/developer_preview_windows_reproducibility_receipt.md"
                ),
            ],
        ),
        _command_row(
            target="new-user-draft",
            operator_flow_id="new_user_observation_receipt",
            label="New-user observation draft receipt",
            required_platform="observed local user session",
            receipt_artifacts=[
                ".betelgeuze/developer_preview_new_user_execution_work_order.json",
                ".betelgeuze/developer_preview_new_user_execution_preflight.json",
                DEFAULT_NEW_USER_OBSERVATION_INPUT_TEMPLATE_JSON,
                DEFAULT_NEW_USER_OBSERVATION_INPUT_JSON,
                ".betelgeuze/developer_preview_new_user_observation_receipt.json",
                ".betelgeuze/developer_preview_new_user_observation_checklist.csv",
                ".betelgeuze/developer_preview_new_user_observation_checklist.md",
            ],
            commands=[
                "mkdir -p .betelgeuze",
                (
                    '"${PYTHON_BIN}" tools/build_product_execution_work_order.py '
                    "--out-json .betelgeuze/developer_preview_new_user_execution_work_order.json "
                    "--out-csv .betelgeuze/developer_preview_new_user_execution_work_order.csv "
                    "--out-md .betelgeuze/developer_preview_new_user_execution_work_order.md"
                ),
                (
                    '"${PYTHON_BIN}" tools/build_product_execution_preflight.py '
                    "--work-order-json .betelgeuze/developer_preview_new_user_execution_work_order.json "
                    "--out-json .betelgeuze/developer_preview_new_user_execution_preflight.json "
                    "--out-csv .betelgeuze/developer_preview_new_user_execution_preflight.csv "
                    "--out-md .betelgeuze/developer_preview_new_user_execution_preflight.md"
                ),
                (
                    '"${PYTHON_BIN}" tools/product/build_developer_preview_new_user_observation_receipt.py '
                    "--work-order-json .betelgeuze/developer_preview_new_user_execution_work_order.json "
                    "--preflight-json .betelgeuze/developer_preview_new_user_execution_preflight.json "
                    "--runbook-md docs/developer_preview_core_workflow_quickstart.md "
                    "--allow-blocked "
                    "--out-json .betelgeuze/developer_preview_new_user_observation_receipt.json "
                    "--out-md .betelgeuze/developer_preview_new_user_observation_receipt.md "
                    "--out-checklist-csv .betelgeuze/developer_preview_new_user_observation_checklist.csv "
                    "--out-checklist-md .betelgeuze/developer_preview_new_user_observation_checklist.md "
                    f"--out-observation-input-template-json {DEFAULT_NEW_USER_OBSERVATION_INPUT_TEMPLATE_JSON}"
                ),
                (
                    f"if [[ ! -f {DEFAULT_NEW_USER_OBSERVATION_INPUT_JSON} ]]; then "
                    f"cp {DEFAULT_NEW_USER_OBSERVATION_INPUT_TEMPLATE_JSON} "
                    f"{DEFAULT_NEW_USER_OBSERVATION_INPUT_JSON}; fi"
                ),
            ],
        ),
        _command_row(
            target="new-user-final",
            operator_flow_id="new_user_observation_receipt",
            label="New-user observation reviewed receipt",
            required_platform="observed local user session",
            receipt_artifacts=[
                ".betelgeuze/developer_preview_new_user_observation_receipt.json",
                ".betelgeuze/developer_preview_new_user_observation_checklist.csv",
                ".betelgeuze/developer_preview_new_user_observation_checklist.md",
                DEFAULT_NEW_USER_OBSERVATION_INPUT_TEMPLATE_JSON,
                DEFAULT_NEW_USER_OBSERVATION_INPUT_JSON,
            ],
            required_input_artifacts=[
                ".betelgeuze/developer_preview_new_user_execution_work_order.json",
                ".betelgeuze/developer_preview_new_user_execution_preflight.json",
                DEFAULT_NEW_USER_OBSERVATION_INPUT_JSON,
            ],
            commands=[
                (
                    '"${PYTHON_BIN}" tools/product/build_developer_preview_new_user_observation_receipt.py '
                    "--work-order-json .betelgeuze/developer_preview_new_user_execution_work_order.json "
                    "--preflight-json .betelgeuze/developer_preview_new_user_execution_preflight.json "
                    "--runbook-md docs/developer_preview_core_workflow_quickstart.md "
                    f"--observation-input-json {DEFAULT_NEW_USER_OBSERVATION_INPUT_JSON} "
                    "--allow-blocked "
                    "--out-json .betelgeuze/developer_preview_new_user_observation_receipt.json "
                    "--out-md .betelgeuze/developer_preview_new_user_observation_receipt.md "
                    "--out-checklist-csv .betelgeuze/developer_preview_new_user_observation_checklist.csv "
                    "--out-checklist-md .betelgeuze/developer_preview_new_user_observation_checklist.md "
                    f"--out-observation-input-template-json {DEFAULT_NEW_USER_OBSERVATION_INPUT_TEMPLATE_JSON}"
                ),
            ],
        ),
        _command_row(
            target="final-gate",
            operator_flow_id="final_gate_audit",
            label="Developer Preview final gate audit",
            required_platform="current checkout",
            receipt_artifacts=[
                DEFAULT_OUT_JSON,
                DEFAULT_OUT_OPERATOR_WORK_ORDER_JSON,
                DEFAULT_OUT_OPERATOR_COMMAND_PACK_JSON,
            ],
            commands=[
                (
                    '"${PYTHON_BIN}" tools/product/build_developer_preview_final_gate_audit.py '
                    f"--out-json {DEFAULT_OUT_JSON} "
                    f"--out-csv {DEFAULT_OUT_CSV} "
                    f"--out-md {DEFAULT_OUT_MD} "
                    f"--out-operator-work-order-json {DEFAULT_OUT_OPERATOR_WORK_ORDER_JSON} "
                    f"--out-operator-work-order-csv {DEFAULT_OUT_OPERATOR_WORK_ORDER_CSV} "
                    f"--out-operator-work-order-md {DEFAULT_OUT_OPERATOR_WORK_ORDER_MD} "
                    f"--out-operator-command-pack-json {DEFAULT_OUT_OPERATOR_COMMAND_PACK_JSON} "
                    f"--out-operator-command-pack-sh {DEFAULT_OUT_OPERATOR_COMMAND_PACK_SH} "
                    f"--out-operator-command-pack-ps1 {DEFAULT_OUT_OPERATOR_COMMAND_PACK_PS1} "
                    f"--out-operator-command-pack-md {DEFAULT_OUT_OPERATOR_COMMAND_PACK_MD}"
                ),
            ],
        ),
    ]


def _target_for_operator_flow(row: dict[str, Any]) -> str:
    flow_id = _text(row.get("operator_flow_id"))
    if flow_id == "clean_checkout_benchmark_receipt":
        return "clean-checkout"
    if flow_id == "linux_reproducibility_receipt":
        return "linux-repro"
    if flow_id == "windows_reproducibility_receipt":
        return "windows-repro"
    if flow_id == "new_user_observation_receipt":
        input_paths = {
            _text(path) for path in row.get("required_receipt_artifacts", []) if _text(path)
        }
        present_paths = {
            _text(check_path)
            for check_path in row.get("present_receipt_artifacts", [])
            if _text(check_path)
        }
        prerequisites = {
            ".betelgeuze/developer_preview_new_user_execution_work_order.json",
            ".betelgeuze/developer_preview_new_user_execution_preflight.json",
        }
        if prerequisites.issubset(input_paths) and prerequisites.issubset(present_paths):
            return "new-user-final"
        return "new-user-draft"
    return ""


def _command_for_target(target: str) -> str:
    if not target:
        return ""
    if target == "windows-repro":
        return f"pwsh -File {DEFAULT_OUT_OPERATOR_COMMAND_PACK_PS1} -Target windows-repro"
    return f"bash {DEFAULT_OUT_OPERATOR_COMMAND_PACK_SH} {target}"


GATE_SPECS: list[dict[str, Any]] = [
    {
        "priority": "A",
        "gate_id": "benchmark_results_clean_checkout_regenerated",
        "receipt_artifacts": [
            {
                "path": ".betelgeuze/developer_preview_clean_checkout_benchmark_receipt.json",
                "required_status": "developer_preview_clean_checkout_benchmark_receipt_ready",
                "required_true_fields": [
                    "clean_checkout_benchmark_regenerated",
                    "clean_checkout_provenance_ready",
                    "clean_checkout_source_repo_url_present",
                    "clean_checkout_working_tree_clean",
                    "ai_verify_passed",
                    "reviewed_receipt_attached",
                    "stage5_input_family_ready",
                ],
                "required_zero_fields": [
                    "blocker_count",
                    "failed_count",
                    "clean_checkout_dirty_path_count",
                    "stage5_missing_source_artifact_count",
                    "stage5_incomplete_task_count",
                ],
            }
        ],
        "missing_blocker": "clean_checkout_benchmark_receipt_missing",
        "next_required_step": (
            "Run the clean-checkout benchmark regeneration command from the action register and attach "
            "a reviewed receipt at .betelgeuze/developer_preview_clean_checkout_benchmark_receipt.json."
        ),
    },
    {
        "priority": "B",
        "gate_id": "silent_import_loss_zero",
        "receipt_artifacts": [
            {
                "path": ".betelgeuze/developer_preview_silent_import_loss_receipt.json",
                "required_status": "developer_preview_silent_import_loss_receipt_ready",
                "required_true_fields": [
                    "import_cli_tests_passed",
                    "capability_matrix_checked",
                    "silent_import_loss_zero",
                ],
                "required_zero_fields": [
                    "blocker_count",
                    "missing_required_surface_count",
                    "unimportable_required_surface_count",
                ],
            }
        ],
        "missing_blocker": "silent_import_loss_receipt_missing",
        "next_required_step": (
            "Run the DP import/CLI tests plus capability matrix check and attach a receipt proving zero "
            "required import loss."
        ),
    },
    {
        "priority": "C",
        "gate_id": "selected_medium_models_pass_or_approved_review",
        "receipt_artifacts": [
            {
                "path": ".betelgeuze/developer_preview_medium_pose_sampling_readiness.json",
                "required_status": "product_pose_sampling_readiness_ready",
                "required_true_fields": ["pose_sampling_readiness_ready"],
                "required_zero_fields": ["blocker_count"],
            },
            {
                "path": ".betelgeuze/developer_preview_medium_backmapping_smoke.json",
                "required_status": "backmapping_scoring_batch_smoke_benchmark_ready",
                "required_true_fields": ["benchmark_ready"],
                "required_zero_fields": ["blocker_count", "failed_count"],
            },
        ],
        "review_artifact": {
            "path": ".betelgeuze/developer_preview_medium_model_operator_review.json",
            "required_status": "developer_preview_medium_model_operator_review_approved",
            "required_true_fields": ["approved_review"],
            "required_zero_fields": ["blocker_count"],
        },
        "missing_blocker": "selected_medium_model_receipts_or_review_missing",
        "next_required_step": (
            "Run the frozen selected-medium-model pose/backmapping smoke receipts, or attach an approved "
            "operator review explaining each failed medium model."
        ),
    },
    {
        "priority": "D",
        "gate_id": "large_models_crash_oom_free",
        "receipt_artifacts": [
            {
                "path": ".betelgeuze/developer_preview_large_model_oom_guard.json",
                "required_status": "developer_preview_large_model_oom_guard_ready",
                "required_true_fields": ["crash_oom_free"],
                "required_zero_fields": ["blocker_count", "crash_count", "oom_count"],
            },
            {
                "path": ".betelgeuze/developer_preview_rocm_large_model_guard.json",
                "required_status": "developer_preview_rocm_large_model_guard_ready",
                "required_true_fields": ["crash_oom_free"],
                "required_zero_fields": ["blocker_count", "crash_count", "oom_count"],
            },
        ],
        "missing_blocker": "large_model_crash_oom_receipts_missing",
        "next_required_step": (
            "Run the large-model crash/OOM guard on the approved local hardware/profile and attach "
            "reviewed receipts with explicit crash_count=0 and oom_count=0."
        ),
    },
    {
        "priority": "E",
        "gate_id": "linux_windows_reproducibility_confirmed",
        "receipt_artifacts": [
            {
                "path": ".betelgeuze/developer_preview_linux_reproducibility_receipt.json",
                "required_status": "developer_preview_platform_reproducibility_receipt_ready",
                "required_true_fields": ["command_set_passed", "linux_receipt"],
                "required_zero_fields": ["blocker_count"],
            },
            {
                "path": ".betelgeuze/developer_preview_windows_reproducibility_receipt.json",
                "required_status": "developer_preview_platform_reproducibility_receipt_ready",
                "required_true_fields": ["command_set_passed", "windows_receipt"],
                "required_zero_fields": ["blocker_count"],
            },
        ],
        "missing_blocker": "linux_windows_reproducibility_receipts_missing",
        "next_required_step": (
            "Attach matching Linux and Windows command-set receipts with Python/dependency inputs and "
            "expected skips recorded."
        ),
    },
    {
        "priority": "F",
        "gate_id": "new_user_core_workflow_observation_passed",
        "receipt_artifacts": [
            {
                "path": ".betelgeuze/developer_preview_new_user_execution_work_order.json",
                "required_status": "product_execution_work_order_ready",
                "required_true_fields": ["profile_command_generated"],
                "required_zero_fields": ["blocker_count"],
            },
            {
                "path": ".betelgeuze/developer_preview_new_user_execution_preflight.json",
                "required_status": "product_execution_preflight_ready",
                "required_true_fields": ["validated_without_execution"],
                "required_zero_fields": ["blocker_count", "unknown_arg_count"],
            },
            {
                "path": ".betelgeuze/developer_preview_new_user_observation_receipt.json",
                "required_status": "developer_preview_new_user_observation_receipt_ready",
                "required_true_fields": [
                    "runbook_ready",
                    "core_workflow_receipt_path_documented",
                    "core_workflow_command_set_documented",
                    "observation_checklist_path_documented",
                    "developer_preview_exit_receipt_path_documented",
                    "developer_preview_exit_command_set_documented",
                    "clean_checkout_bootstrap_documented",
                    "linux_bootstrap_command_set_documented",
                    "windows_bootstrap_command_set_documented",
                    "clean_checkout_receipt_path_documented",
                    "platform_reproducibility_receipt_paths_documented",
                    "observer_signoff",
                    "anonymized_notes_only",
                    "raw_customer_data_not_stored_in_repo",
                    "customer_retained_raw_data",
                ],
                "required_zero_fields": ["blocker_count", "hidden_state_blocker_count"],
            },
        ],
        "missing_blocker": "new_user_workflow_observation_receipts_missing",
        "next_required_step": (
            "Run the new-user work-order/preflight path and attach an observer signoff receipt with only "
            "derived/anonymized metadata."
        ),
    },
]


def _resolve(path_like: str | Path, *, root: Path = ROOT) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else root / path


def _display(path_like: str | Path, *, root: Path = ROOT) -> str:
    path = Path(str(path_like))
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


def _stage5_restore_packet_state(*, root: Path = ROOT) -> dict[str, Any]:
    path = _resolve(DEFAULT_STAGE5_RESTORE_PACKET_JSON, root=root)
    present = path.is_file()
    payload = _read_json(DEFAULT_STAGE5_RESTORE_PACKET_JSON, root=root) if present else {}
    summary = _summary(payload) if present else {}
    status = _text(summary.get("status"))
    ready = status == "developer_preview_stage5_restore_packet_ready"
    missing_source_artifact_count = _int(summary.get("missing_source_artifact_count"))
    fail_closed_restore_receipt_ready = _bool_true(
        summary.get("stage5_fail_closed_restore_receipt_ready")
    )
    return {
        "json_path": DEFAULT_STAGE5_RESTORE_PACKET_JSON,
        "present": present,
        "status": status,
        "ready": ready,
        "fail_closed_restore_receipt_ready": fail_closed_restore_receipt_ready,
        "operator_restore_queue_ready": _bool_true(
            summary.get("stage5_operator_restore_queue_ready")
        ),
        "operator_restore_queue_row_count": _int(
            summary.get("stage5_operator_restore_queue_row_count")
        ),
        "missing_source_artifact_count": missing_source_artifact_count,
        "primary_blocker": _text(summary.get("primary_blocker")),
        "primary_missing_source_argument": _text(
            summary.get("primary_missing_source_argument")
        ),
        "primary_missing_source_artifact_path": _text(
            summary.get("primary_missing_source_artifact_path")
        ),
        "primary_missing_pipeline_summary_json": _text(
            summary.get("primary_missing_pipeline_summary_json")
        ),
        "primary_missing_pipeline_summary_present": _bool_true(
            summary.get("primary_missing_pipeline_summary_present")
        ),
        "primary_missing_profile_json": _text(summary.get("primary_missing_profile_json")),
        "primary_missing_profile_present": _bool_true(
            summary.get("primary_missing_profile_present")
        ),
        "primary_missing_restore_queue_ready": _bool_true(
            summary.get("primary_missing_restore_queue_ready")
        ),
        "primary_missing_restore_instruction": _text(
            summary.get("primary_missing_restore_instruction")
        ),
        "next_required_step": _text(summary.get("next_required_step")),
        "operator_action_required": bool(present and missing_source_artifact_count and not ready),
    }


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _int(value: Any) -> int:
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0


def _bool_true(value: Any) -> bool:
    return value is True


def _metric(label: str, value: Any) -> str:
    rendered = "true" if value is True else "false" if value is False else _text(value)
    return f"{label}={rendered}" if rendered else ""


def _join_metrics(*parts: str) -> str:
    return "; ".join(part for part in parts if part)


def _split_receipt_blocker(blocker: str) -> tuple[str, str]:
    text = _text(blocker)
    if ":source_blocker=" in text:
        artifact, detail = text.split(":source_blocker=", 1)
        return artifact, detail
    if ":" in text:
        artifact, detail = text.split(":", 1)
        return artifact, detail
    return "", text


def _source_blocker_parts(detail: str, *, root: Path = ROOT) -> dict[str, Any]:
    blocker_detail = _text(detail)
    source_label = ""
    blocker_expression = blocker_detail
    for prefix in ("baseline_source_blocker=", "source_blocker="):
        if blocker_expression.startswith(prefix):
            source_label = prefix.removesuffix("=")
            blocker_expression = blocker_expression[len(prefix) :]
            break

    blocker_id = blocker_expression
    source_argument = ""
    source_artifact_path = ""
    if blocker_expression.endswith(":missing"):
        blocker_id = "missing_source_artifact"
        source_artifact_path = blocker_expression.removesuffix(":missing")
    elif ":" in blocker_expression:
        parts = blocker_expression.split(":", 2)
        blocker_id = parts[0]
        if len(parts) > 1 and parts[1].startswith("--"):
            source_argument = parts[1]
            source_artifact_path = parts[2] if len(parts) > 2 else ""
        elif len(parts) > 1:
            source_artifact_path = ":".join(parts[1:])

    return {
        "source_label": source_label,
        "blocker_id": blocker_id,
        "source_argument": source_argument,
        "source_artifact_path": _display(source_artifact_path, root=root)
        if source_artifact_path
        else "",
        "source_artifact_present": _resolve(source_artifact_path, root=root).is_file()
        if source_artifact_path
        else False,
    }


def _stage5_task_key(source_artifact_path: str) -> str:
    if not source_artifact_path:
        return ""
    stem = Path(source_artifact_path).stem
    for suffix in ("_stage4_calibration_scores", "_stage3_scores"):
        if stem.endswith(suffix):
            return stem[: -len(suffix)]
    return stem


def _blocker_required_action(detail: str) -> str:
    if "stage5_input_missing" in detail:
        return (
            "Restore or regenerate the missing clean-checkout stage5 input CSVs "
            "(scores, labels, split, and expected-key queue), then rebuild the baseline receipt."
        )
    if "pipeline_summary_json_missing" in detail:
        return (
            "Restore the packaged pipeline summary copy or rerun the clean-checkout benchmark "
            "regeneration before rebuilding the baseline receipt."
        )
    if detail == "missing":
        return "Create or attach the required receipt artifact."
    if detail.startswith("status="):
        return "Rebuild the receipt after clearing its source blockers."
    if detail.endswith("_not_true"):
        return f"Provide evidence so {detail[:-9]} is true."
    if detail.endswith("_nonzero"):
        return f"Clear the underlying blockers so {detail[:-8]} is zero."
    if detail.endswith(":missing") or detail.endswith("_missing"):
        return "Attach the missing source evidence required by the receipt."
    if "missing_or_invalid" in detail:
        return "Attach a valid source artifact for the receipt."
    if "platform_mismatch" in detail:
        return "Run this receipt on the expected platform or attach an approved platform receipt."
    return "Resolve this receipt blocker and rebuild the Developer Preview audit."


def _receipt_requirement_index() -> dict[str, dict[str, Any]]:
    requirements: dict[str, dict[str, Any]] = {}
    for gate_spec in GATE_SPECS:
        artifacts = [("required", item) for item in gate_spec["receipt_artifacts"]]
        if isinstance(gate_spec.get("review_artifact"), dict):
            artifacts.append(("review", gate_spec["review_artifact"]))
        for receipt_kind, artifact in artifacts:
            requirements[_text(artifact.get("path"))] = {
                "receipt_kind": receipt_kind,
                "required_receipt_status": _text(artifact.get("required_status")),
                "required_true_fields": list(artifact.get("required_true_fields", [])),
                "required_zero_fields": list(artifact.get("required_zero_fields", [])),
            }
    return requirements


def _receipt_artifact_index() -> dict[str, dict[str, Any]]:
    artifacts: dict[str, dict[str, Any]] = {}
    for gate_spec in GATE_SPECS:
        for artifact in gate_spec["receipt_artifacts"]:
            artifacts[_text(artifact.get("path"))] = artifact
        if isinstance(gate_spec.get("review_artifact"), dict):
            review_artifact = gate_spec["review_artifact"]
            artifacts[_text(review_artifact.get("path"))] = review_artifact
    return artifacts


def _receipt_work_order_rows(
    rows: list[dict[str, Any]],
    *,
    root: Path = ROOT,
) -> list[dict[str, Any]]:
    receipt_requirements = _receipt_requirement_index()
    work_rows: list[dict[str, Any]] = []
    for row in rows:
        if row["ready"]:
            continue
        for blocker in row["receipt_blockers"]:
            artifact, detail = _split_receipt_blocker(blocker)
            requirement = receipt_requirements.get(artifact, {})
            required_true_fields = list(requirement.get("required_true_fields", []))
            required_zero_fields = list(requirement.get("required_zero_fields", []))
            blocker_scope = "receipt_source" if ":source_blocker=" in blocker else "receipt_contract"
            source_parts = (
                _source_blocker_parts(detail, root=root)
                if blocker_scope == "receipt_source"
                else {}
            )
            work_rows.append(
                {
                    "priority": row["priority"],
                    "gate_id": row["gate_id"],
                    "receipt_artifact": artifact,
                    "receipt_kind": requirement.get("receipt_kind", ""),
                    "blocker_scope": blocker_scope,
                    "required_receipt_status": requirement.get("required_receipt_status", ""),
                    "required_true_fields": required_true_fields,
                    "required_zero_fields": required_zero_fields,
                    "required_true_field_count": len(required_true_fields),
                    "required_zero_field_count": len(required_zero_fields),
                    "blocker": blocker,
                    "blocker_detail": detail,
                    "source_label": source_parts.get("source_label", ""),
                    "blocker_id": source_parts.get("blocker_id", ""),
                    "source_argument": source_parts.get("source_argument", ""),
                    "source_artifact_path": source_parts.get("source_artifact_path", ""),
                    "source_artifact_present": source_parts.get(
                        "source_artifact_present",
                        False,
                    ),
                    "required_action": _blocker_required_action(detail),
                    "next_required_step": row["next_required_step"],
                    "execution_enabled": False,
                    "external_state_mutated": False,
                    "claim_promotion_allowed": False,
                    "claim_boundary": CLAIM_BOUNDARY,
                }
            )
    return work_rows


def _stage5_recovery_rows(
    receipt_work_order_rows: list[dict[str, Any]],
    *,
    gate_rows: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()

    def append_row(row: dict[str, Any]) -> None:
        key = (
            _text(row.get("receipt_artifact")),
            _text(row.get("source_argument")),
            _text(row.get("source_artifact_path")),
        )
        if key in seen:
            return
        seen.add(key)
        rows.append(row)

    for gate_row in gate_rows or []:
        for family_row in gate_row.get("stage5_input_family_rows", []):
            if not isinstance(family_row, dict):
                continue
            if not (
                _bool_true(family_row.get("source_artifact_missing"))
                or _bool_true(family_row.get("operator_action_required"))
            ):
                continue
            source_path = _text(family_row.get("source_artifact_path"))
            source_argument = _text(family_row.get("source_argument"))
            if not source_path and not source_argument:
                continue
            append_row(
                {
                    "priority": _text(family_row.get("priority"))
                    or _text(gate_row.get("priority")),
                    "gate_id": _text(family_row.get("gate_id"))
                    or _text(gate_row.get("gate_id")),
                    "receipt_artifact": _text(family_row.get("receipt_artifact")),
                    "receipt_kind": _text(family_row.get("receipt_kind")) or "required",
                    "blocker_detail": f"stage5_input_missing:{source_argument}:{source_path}",
                    "source_label": "stage5_input_family",
                    "blocker_id": "stage5_input_missing",
                    "source_argument": source_argument,
                    "source_artifact_path": source_path,
                    "source_artifact_present": _bool_true(
                        family_row.get("source_artifact_present")
                    ),
                    "task_key": _text(family_row.get("task_key"))
                    or _stage5_task_key(source_path),
                    "required_stage5_arguments": list(STAGE5_REQUIRED_ARGUMENTS),
                    "required_stage5_argument_count": len(STAGE5_REQUIRED_ARGUMENTS),
                    "required_action": (
                        "Restore or regenerate this stage5 input family from the clean-checkout "
                        "baseline run, then rebuild the clean-checkout benchmark receipt."
                    ),
                    "operator_action_required": True,
                    "execution_enabled": False,
                    "external_state_mutated": False,
                    "claim_promotion_allowed": False,
                    "claim_boundary": CLAIM_BOUNDARY,
                }
            )

    for row in receipt_work_order_rows:
        if row.get("blocker_scope") != "receipt_source":
            continue
        if row.get("blocker_id") != "stage5_input_missing":
            continue
        source_path = _text(row.get("source_artifact_path"))
        append_row(
            {
                "priority": _text(row.get("priority")),
                "gate_id": _text(row.get("gate_id")),
                "receipt_artifact": _text(row.get("receipt_artifact")),
                "receipt_kind": _text(row.get("receipt_kind")),
                "blocker_detail": _text(row.get("blocker_detail")),
                "source_label": _text(row.get("source_label")),
                "blocker_id": _text(row.get("blocker_id")),
                "source_argument": _text(row.get("source_argument")),
                "source_artifact_path": source_path,
                "source_artifact_present": _bool_true(row.get("source_artifact_present")),
                "task_key": _stage5_task_key(source_path),
                "required_stage5_arguments": list(STAGE5_REQUIRED_ARGUMENTS),
                "required_stage5_argument_count": len(STAGE5_REQUIRED_ARGUMENTS),
                "required_action": (
                    "Restore or regenerate this stage5 input family from the clean-checkout "
                    "baseline run, then rebuild the clean-checkout benchmark receipt."
                ),
                "operator_action_required": True,
                "execution_enabled": False,
                "external_state_mutated": False,
                "claim_promotion_allowed": False,
                "claim_boundary": CLAIM_BOUNDARY,
            }
        )
    return rows


def _artifact_check(artifact: dict[str, Any], *, root: Path) -> dict[str, Any]:
    artifact_path = artifact["path"]
    path = _resolve(artifact_path, root=root)
    present = path.is_file()
    payload = _read_json(artifact_path, root=root) if present else {}
    summary = _summary(payload) if present else {}
    stage5_input_family_rows = (
        payload.get("stage5_input_family_rows")
        if isinstance(payload.get("stage5_input_family_rows"), list)
        else []
    )
    status = _text(summary.get("status"))
    expected_status = _text(artifact.get("required_status"))
    status_ok = bool(status and status == expected_status)
    missing_true_fields = (
        [field for field in artifact.get("required_true_fields", []) if not _bool_true(summary.get(field))]
        if present
        else []
    )
    nonzero_fields = (
        [field for field in artifact.get("required_zero_fields", []) if _int(summary.get(field)) != 0]
        if present
        else []
    )
    ready = present and status_ok and not missing_true_fields and not nonzero_fields
    blockers: list[str] = []
    if not present:
        blockers.append(f"{artifact_path}:missing")
    elif not status_ok:
        blockers.append(f"{artifact_path}:status={status or 'missing'}")
    blockers.extend(f"{artifact_path}:{field}_not_true" for field in missing_true_fields)
    blockers.extend(f"{artifact_path}:{field}_nonzero" for field in nonzero_fields)
    source_blockers = [
        _text(blocker)
        for blocker in summary.get("blockers", [])
        if _text(blocker)
    ]
    detailed_blockers = [
        *blockers,
        *[f"{artifact_path}:source_blocker={blocker}" for blocker in source_blockers],
    ]
    return {
        "path": artifact_path,
        "present": present,
        "ready": ready,
        "status": status,
        "blockers": blockers,
        "detailed_blockers": detailed_blockers,
        "source_blockers": source_blockers,
        "stage5_input_family_rows": [
            row for row in stage5_input_family_rows if isinstance(row, dict)
        ],
    }


def _gate_row(spec: dict[str, Any], *, root: Path) -> dict[str, Any]:
    checks = [_artifact_check(artifact, root=root) for artifact in spec["receipt_artifacts"]]
    required_ready = all(check["ready"] for check in checks)
    review_spec = spec.get("review_artifact")
    review_check = _artifact_check(review_spec, root=root) if isinstance(review_spec, dict) else None
    review_ready = bool(review_check and review_check["ready"])
    ready = required_ready or review_ready
    blockers = [
        blocker
        for check in checks
        for blocker in check["blockers"]
        if not review_ready
    ]
    detailed_blockers = [
        blocker
        for check in checks
        for blocker in check["detailed_blockers"]
        if not review_ready
    ]
    if review_check and not required_ready and not review_ready:
        blockers.extend(review_check["blockers"])
        detailed_blockers.extend(review_check["detailed_blockers"])
    if not blockers and not ready:
        blockers = [spec["missing_blocker"]]
    if not detailed_blockers and not ready:
        detailed_blockers = list(blockers)
    present_count = sum(1 for check in checks if check["present"])
    present_blocked_receipt_count = sum(
        1 for check in checks if check["present"] and not check["ready"]
    )
    required_count = len(checks)
    if review_check and review_check["present"]:
        present_count += 1
    if review_check and review_check["present"] and not review_check["ready"]:
        present_blocked_receipt_count += 1
    receipt_paths = [check["path"] for check in checks]
    if review_check:
        receipt_paths.append(review_check["path"])
    stage5_input_family_rows: list[dict[str, Any]] = []
    for check in checks:
        for family_row in check.get("stage5_input_family_rows", []):
            enriched_row = dict(family_row)
            enriched_row["priority"] = spec["priority"]
            enriched_row["gate_id"] = spec["gate_id"]
            enriched_row["receipt_artifact"] = check["path"]
            enriched_row["receipt_kind"] = "required"
            stage5_input_family_rows.append(enriched_row)
    return {
        "priority": spec["priority"],
        "gate_id": spec["gate_id"],
        "status": "developer_preview_gate_ready" if ready else "blocked_developer_preview_gate",
        "ready": ready,
        "receipt_artifacts": ";".join(receipt_paths),
        "present_receipt_count": present_count,
        "required_receipt_count": required_count,
        "primary_metric": _join_metrics(
            _metric("required_ready", required_ready),
            _metric("review_ready", review_ready),
        ),
        "secondary_metric": _join_metrics(
            _metric("present_receipts", present_count),
            _metric("required_receipts", required_count),
        ),
        "blocker": "" if ready else (blockers[0] if blockers else spec["missing_blocker"]),
        "blockers": blockers,
        "receipt_blocker_count": len(detailed_blockers),
        "receipt_blockers": detailed_blockers,
        "present_blocked_receipt_count": present_blocked_receipt_count,
        "stage5_input_family_rows": stage5_input_family_rows,
        "next_required_step": spec["next_required_step"],
        "execution_enabled": False,
        "external_state_mutated": False,
        "claim_promotion_allowed": False,
        "claim_boundary": CLAIM_BOUNDARY,
    }


def _external_operator_work_order_rows(*, root: Path = ROOT) -> list[dict[str, Any]]:
    artifact_index = _receipt_artifact_index()
    rows: list[dict[str, Any]] = []
    for spec in EXTERNAL_OPERATOR_WORK_ORDER_SPECS:
        required_paths = [
            _text(path) for path in spec["required_receipt_artifacts"] if _text(path)
        ]
        checks = [
            _artifact_check(artifact_index[path], root=root)
            for path in required_paths
            if path in artifact_index
        ]
        ready = bool(checks and all(check["ready"] for check in checks))
        present_count = sum(1 for check in checks if check["present"])
        detailed_blockers = [
            blocker for check in checks for blocker in check["detailed_blockers"]
        ]
        source_blocker_count = sum(len(check["source_blockers"]) for check in checks)
        primary_path = _text(spec.get("primary_receipt_artifact"))
        primary_check = next(
            (check for check in checks if check["path"] == primary_path),
            checks[0] if checks else {},
        )
        primary_blocker = ""
        if not ready:
            primary_blocker = (
                next(
                    (
                        blocker
                        for blocker in detailed_blockers
                        if blocker.startswith(f"{primary_path}:")
                    ),
                    "",
                )
                or (detailed_blockers[0] if detailed_blockers else "receipt_artifact_missing")
            )
        rows.append(
            {
                "operator_flow_id": spec["operator_flow_id"],
                "gate_id": spec["gate_id"],
                "label": spec["label"],
                "status": "developer_preview_operator_flow_ready"
                if ready
                else "blocked_developer_preview_operator_flow",
                "ready": ready,
                "required_platform": spec["required_platform"],
                "runbook_path": DEFAULT_CORE_WORKFLOW_RUNBOOK_MD,
                "runbook_section": spec["runbook_section"],
                "action_register_path": DEFAULT_REGISTER_MD,
                "primary_receipt_artifact": primary_path,
                "required_receipt_artifacts": required_paths,
                "present_receipt_artifacts": [
                    check["path"] for check in checks if check.get("present")
                ],
                "supporting_artifacts": list(spec.get("supporting_artifacts", [])),
                "present_receipt_count": present_count,
                "required_receipt_count": len(required_paths),
                "primary_receipt_status": _text(primary_check.get("status")),
                "primary_receipt_present": bool(primary_check.get("present")),
                "fail_closed_command_token": spec["fail_closed_command_token"],
                "blocker": "" if ready else primary_blocker,
                "receipt_blockers": detailed_blockers,
                "receipt_blocker_count": len(detailed_blockers),
                "source_blocker_count": source_blocker_count,
                "required_action": "" if ready else spec["required_action"],
                "next_required_step": (
                    "Attach the ready receipt to the Developer Preview final gate audit."
                    if ready
                    else spec["required_action"]
                ),
                "operator_action_required": not ready,
                "execution_enabled": False,
                "external_state_mutated": False,
                "claim_promotion_allowed": False,
                "claim_boundary": CLAIM_BOUNDARY,
            }
        )
    return rows


def build_developer_preview_final_gate_audit(
    *,
    register_md: str | Path = DEFAULT_REGISTER_MD,
    root: Path = ROOT,
) -> dict[str, Any]:
    register_text = _read_text(register_md, root=root)
    materialized_gate_ids = {spec["gate_id"] for spec in GATE_SPECS if spec["gate_id"] in register_text}
    missing_register_fail_closed_tokens = [
        token for token in REGISTER_FAIL_CLOSED_REQUIRED_TOKENS if token not in register_text
    ]
    register_fail_closed_command_contract_ready = bool(
        register_text and not missing_register_fail_closed_tokens
    )
    rows = [_gate_row(spec, root=root) for spec in GATE_SPECS]
    ready_rows = [row for row in rows if row["ready"]]
    blocked_rows = [row for row in rows if not row["ready"]]
    missing_receipt_count = sum(
        max(0, int(row["required_receipt_count"]) - int(row["present_receipt_count"]))
        for row in rows
        if not row["ready"]
    )
    receipt_blockers = [
        blocker
        for row in blocked_rows
        for blocker in row["receipt_blockers"]
    ]
    receipt_work_order_rows = _receipt_work_order_rows(rows, root=root)
    receipt_source_blocker_rows = [
        row for row in receipt_work_order_rows if row.get("blocker_scope") == "receipt_source"
    ]
    stage5_recovery_rows = _stage5_recovery_rows(receipt_work_order_rows, gate_rows=rows)
    external_operator_work_order_rows = _external_operator_work_order_rows(root=root)
    blocked_external_operator_work_order_rows = [
        row for row in external_operator_work_order_rows if not row["ready"]
    ]
    missing_stage5_recovery_rows = [
        row for row in stage5_recovery_rows if not row["source_artifact_present"]
    ]
    stage5_input_family_csv_present = _resolve(
        DEFAULT_STAGE5_INPUT_FAMILY_CSV,
        root=root,
    ).is_file()
    stage5_input_family_md_present = _resolve(
        DEFAULT_STAGE5_INPUT_FAMILY_MD,
        root=root,
    ).is_file()
    stage5_recovery_operator_work_order_materialized = bool(
        stage5_recovery_rows
        and stage5_input_family_csv_present
        and stage5_input_family_md_present
    )
    stage5_restore_packet_state = _stage5_restore_packet_state(root=root)
    new_user_observation_receipt_summary = _summary(
        _read_json(DEFAULT_NEW_USER_OBSERVATION_RECEIPT_JSON, root=root)
    )
    command_pack_rows = _external_operator_command_rows()
    command_pack_rows_by_target = {row["target"]: row for row in command_pack_rows}
    next_operator_command_pack_target = (
        _target_for_operator_flow(blocked_external_operator_work_order_rows[0])
        if blocked_external_operator_work_order_rows
        else ""
    )
    if (
        next_operator_command_pack_target == "clean-checkout"
        and stage5_recovery_rows
        and stage5_recovery_operator_work_order_materialized
    ):
        next_operator_command_pack_target = "stage5-recovery"
    next_operator_command_pack_row = command_pack_rows_by_target.get(
        next_operator_command_pack_target,
        {},
    )
    next_operator_command_pack_command = _command_for_target(
        next_operator_command_pack_target
    )
    present_blocked_receipt_count = sum(
        int(row["present_blocked_receipt_count"])
        for row in blocked_rows
    )
    clean_ready = bool(
        len(ready_rows) == len(rows)
        and materialized_gate_ids == {spec["gate_id"] for spec in GATE_SPECS}
        and register_fail_closed_command_contract_ready
    )
    rows_by_gate_id = {row["gate_id"]: row for row in rows}
    clean_checkout_ready = bool(
        rows_by_gate_id.get("benchmark_results_clean_checkout_regenerated", {}).get("ready")
        is True
    )
    linux_windows_reproducibility_ready = bool(
        rows_by_gate_id.get("linux_windows_reproducibility_confirmed", {}).get("ready")
        is True
    )
    new_user_observation_ready = bool(
        rows_by_gate_id.get("new_user_core_workflow_observation_passed", {}).get("ready")
        is True
    )
    register_contract_blockers = [
        f"developer_preview_action_register:missing_fail_closed_token:{token}"
        for token in missing_register_fail_closed_tokens
    ]
    stage5_next_required_step = (
        _text(stage5_restore_packet_state["primary_missing_restore_instruction"])
        or _text(stage5_restore_packet_state["next_required_step"])
    )
    if next_operator_command_pack_target == "stage5-recovery" and stage5_next_required_step:
        next_required_step = stage5_next_required_step
    elif blocked_rows:
        next_required_step = blocked_rows[0]["next_required_step"]
    elif register_contract_blockers:
        next_required_step = (
            "Repair the Developer Preview action register so clean checkout, platform, "
            "and new-user receipt commands write fail-closed outputs with --allow-blocked."
        )
    else:
        next_required_step = "Developer Preview final gates are ready for operator review."
    blockers = [
        *[f"{row['gate_id']}:{row['blocker']}" for row in blocked_rows],
        *register_contract_blockers,
    ]
    primary_blocker_detail = (
        blocked_rows[0]["blocker"]
        if blocked_rows
        else (register_contract_blockers[0] if register_contract_blockers else "")
    )
    summary = {
        "packet_type": PACKET_TYPE,
        "schema_version": SCHEMA_VERSION,
        "status": "developer_preview_final_gate_audit_ready"
        if clean_ready
        else "blocked_developer_preview_final_gate_audit",
        "developer_preview_clean_baseline_ready": clean_ready,
        "developer_preview_exit_ready": clean_ready,
        "clean_checkout_ready": clean_checkout_ready,
        "linux_windows_reproducibility_ready": linux_windows_reproducibility_ready,
        "windows_reproducibility_ready": linux_windows_reproducibility_ready,
        "new_user_observation_ready": new_user_observation_ready,
        "claim_promotion_allowed": False,
        "gate_count": len(rows),
        "ready_gate_count": len(ready_rows),
        "blocked_gate_count": len(blocked_rows),
        "missing_receipt_count": missing_receipt_count,
        "present_blocked_receipt_count": present_blocked_receipt_count,
        "receipt_blocker_count": len(receipt_blockers),
        "receipt_blockers": receipt_blockers,
        "receipt_work_order_ready": not receipt_work_order_rows,
        "receipt_work_order_row_count": len(receipt_work_order_rows),
        "receipt_work_order_blocked_gate_count": len(
            {row["gate_id"] for row in receipt_work_order_rows}
        ),
        "receipt_work_order_primary_gate_id": receipt_work_order_rows[0]["gate_id"]
        if receipt_work_order_rows
        else "",
        "receipt_work_order_primary_receipt_artifact": receipt_work_order_rows[0]["receipt_artifact"]
        if receipt_work_order_rows
        else "",
        "receipt_work_order_primary_blocker": receipt_work_order_rows[0]["blocker_detail"]
        if receipt_work_order_rows
        else "",
        "receipt_work_order_primary_required_receipt_status": (
            receipt_work_order_rows[0]["required_receipt_status"] if receipt_work_order_rows else ""
        ),
        "receipt_work_order_primary_required_true_fields": (
            receipt_work_order_rows[0]["required_true_fields"] if receipt_work_order_rows else []
        ),
        "receipt_work_order_primary_required_zero_fields": (
            receipt_work_order_rows[0]["required_zero_fields"] if receipt_work_order_rows else []
        ),
        "receipt_work_order_source_blocker_count": len(receipt_source_blocker_rows),
        "receipt_work_order_primary_source_blocker_gate_id": (
            receipt_source_blocker_rows[0]["gate_id"] if receipt_source_blocker_rows else ""
        ),
        "receipt_work_order_primary_source_blocker_receipt_artifact": (
            receipt_source_blocker_rows[0]["receipt_artifact"] if receipt_source_blocker_rows else ""
        ),
        "receipt_work_order_primary_source_blocker": (
            receipt_source_blocker_rows[0]["blocker_detail"] if receipt_source_blocker_rows else ""
        ),
        "receipt_work_order_primary_source_blocker_required_action": (
            receipt_source_blocker_rows[0]["required_action"] if receipt_source_blocker_rows else ""
        ),
        "stage5_recovery_work_order_ready": not stage5_recovery_rows,
        "stage5_recovery_operator_work_order_ready": bool(
            not stage5_recovery_rows or stage5_recovery_operator_work_order_materialized
        ),
        "stage5_recovery_operator_work_order_materialized": (
            stage5_recovery_operator_work_order_materialized
        ),
        "stage5_input_family_csv_path": DEFAULT_STAGE5_INPUT_FAMILY_CSV,
        "stage5_input_family_md_path": DEFAULT_STAGE5_INPUT_FAMILY_MD,
        "stage5_input_family_csv_present": stage5_input_family_csv_present,
        "stage5_input_family_md_present": stage5_input_family_md_present,
        "stage5_recovery_row_count": len(stage5_recovery_rows),
        "stage5_missing_source_artifact_count": len(missing_stage5_recovery_rows),
        "stage5_required_argument_count": len(STAGE5_REQUIRED_ARGUMENTS),
        "stage5_primary_task_key": (
            stage5_recovery_rows[0]["task_key"] if stage5_recovery_rows else ""
        ),
        "stage5_primary_source_argument": (
            stage5_recovery_rows[0]["source_argument"] if stage5_recovery_rows else ""
        ),
        "stage5_primary_source_artifact_path": (
            stage5_recovery_rows[0]["source_artifact_path"] if stage5_recovery_rows else ""
        ),
        "stage5_restore_packet_json_path": stage5_restore_packet_state["json_path"],
        "stage5_restore_packet_json_present": stage5_restore_packet_state["present"],
        "stage5_restore_packet_status": stage5_restore_packet_state["status"],
        "stage5_restore_packet_ready": stage5_restore_packet_state["ready"],
        "stage5_restore_packet_fail_closed_restore_receipt_ready": stage5_restore_packet_state[
            "fail_closed_restore_receipt_ready"
        ],
        "stage5_restore_packet_operator_restore_queue_ready": stage5_restore_packet_state[
            "operator_restore_queue_ready"
        ],
        "stage5_restore_packet_operator_restore_queue_row_count": stage5_restore_packet_state[
            "operator_restore_queue_row_count"
        ],
        "stage5_restore_packet_missing_source_artifact_count": stage5_restore_packet_state[
            "missing_source_artifact_count"
        ],
        "stage5_restore_packet_primary_blocker": stage5_restore_packet_state[
            "primary_blocker"
        ],
        "stage5_restore_packet_primary_missing_source_argument": (
            stage5_restore_packet_state["primary_missing_source_argument"]
        ),
        "stage5_restore_packet_primary_missing_source_artifact_path": (
            stage5_restore_packet_state["primary_missing_source_artifact_path"]
        ),
        "stage5_restore_packet_primary_missing_pipeline_summary_json": (
            stage5_restore_packet_state["primary_missing_pipeline_summary_json"]
        ),
        "stage5_restore_packet_primary_missing_pipeline_summary_present": (
            stage5_restore_packet_state["primary_missing_pipeline_summary_present"]
        ),
        "stage5_restore_packet_primary_missing_profile_json": (
            stage5_restore_packet_state["primary_missing_profile_json"]
        ),
        "stage5_restore_packet_primary_missing_profile_present": (
            stage5_restore_packet_state["primary_missing_profile_present"]
        ),
        "stage5_restore_packet_primary_missing_restore_queue_ready": (
            stage5_restore_packet_state["primary_missing_restore_queue_ready"]
        ),
        "stage5_restore_packet_primary_missing_restore_instruction": (
            stage5_restore_packet_state["primary_missing_restore_instruction"]
        ),
        "stage5_restore_packet_next_required_step": stage5_restore_packet_state[
            "next_required_step"
        ],
        "stage5_restore_packet_operator_action_required": stage5_restore_packet_state[
            "operator_action_required"
        ],
        "external_operator_work_order_json_path": DEFAULT_OUT_OPERATOR_WORK_ORDER_JSON,
        "external_operator_work_order_csv_path": DEFAULT_OUT_OPERATOR_WORK_ORDER_CSV,
        "external_operator_work_order_md_path": DEFAULT_OUT_OPERATOR_WORK_ORDER_MD,
        "external_operator_command_pack_json_path": DEFAULT_OUT_OPERATOR_COMMAND_PACK_JSON,
        "external_operator_command_pack_sh_path": DEFAULT_OUT_OPERATOR_COMMAND_PACK_SH,
        "external_operator_command_pack_md_path": DEFAULT_OUT_OPERATOR_COMMAND_PACK_MD,
        "external_operator_command_pack_target_count": len(command_pack_rows),
        "next_operator_command_pack_target": next_operator_command_pack_target,
        "next_operator_command_pack_command": next_operator_command_pack_command,
        "next_operator_command_pack_required_platform": _text(
            next_operator_command_pack_row.get("required_platform")
        ),
        "next_operator_command_pack_required_env_vars": list(
            next_operator_command_pack_row.get("required_env_vars", [])
        ),
        "next_operator_command_pack_required_input_artifacts": list(
            next_operator_command_pack_row.get("required_input_artifacts", [])
        ),
        "next_operator_command_pack_receipt_artifacts": list(
            next_operator_command_pack_row.get("receipt_artifacts", [])
        ),
        "external_operator_work_order_ready": not blocked_external_operator_work_order_rows,
        "external_operator_work_order_row_count": len(external_operator_work_order_rows),
        "external_operator_work_order_blocked_row_count": len(
            blocked_external_operator_work_order_rows
        ),
        "external_operator_work_order_primary_flow_id": (
            blocked_external_operator_work_order_rows[0]["operator_flow_id"]
            if blocked_external_operator_work_order_rows
            else ""
        ),
        "external_operator_work_order_primary_gate_id": (
            blocked_external_operator_work_order_rows[0]["gate_id"]
            if blocked_external_operator_work_order_rows
            else ""
        ),
        "external_operator_work_order_primary_receipt_artifact": (
            blocked_external_operator_work_order_rows[0]["primary_receipt_artifact"]
            if blocked_external_operator_work_order_rows
            else ""
        ),
        "external_operator_work_order_primary_blocker": (
            blocked_external_operator_work_order_rows[0]["blocker"]
            if blocked_external_operator_work_order_rows
            else ""
        ),
        "external_operator_work_order_primary_required_action": (
            blocked_external_operator_work_order_rows[0]["required_action"]
            if blocked_external_operator_work_order_rows
            else ""
        ),
        "clean_checkout_operator_work_order_ready": next(
            (
                bool(row["ready"])
                for row in external_operator_work_order_rows
                if row["operator_flow_id"] == "clean_checkout_benchmark_receipt"
            ),
            False,
        ),
        "linux_reproducibility_operator_work_order_ready": next(
            (
                bool(row["ready"])
                for row in external_operator_work_order_rows
                if row["operator_flow_id"] == "linux_reproducibility_receipt"
            ),
            False,
        ),
        "windows_reproducibility_operator_work_order_ready": next(
            (
                bool(row["ready"])
                for row in external_operator_work_order_rows
                if row["operator_flow_id"] == "windows_reproducibility_receipt"
            ),
            False,
        ),
        "new_user_observation_operator_work_order_ready": next(
            (
                bool(row["ready"])
                for row in external_operator_work_order_rows
                if row["operator_flow_id"] == "new_user_observation_receipt"
            ),
            False,
        ),
        "new_user_observation_draft_fail_closed_ready": _bool_true(
            new_user_observation_receipt_summary.get("new_user_draft_fail_closed_ready")
        ),
        "new_user_observation_input_json": DEFAULT_NEW_USER_OBSERVATION_INPUT_JSON,
        "new_user_observation_input_template_json": (
            DEFAULT_NEW_USER_OBSERVATION_INPUT_TEMPLATE_JSON
        ),
        "new_user_observation_input_json_present": _bool_true(
            new_user_observation_receipt_summary.get("observation_input_json_present")
        ),
        "new_user_observation_input_contract_ready": _bool_true(
            new_user_observation_receipt_summary.get("observation_input_contract_ready")
        ),
        "new_user_observation_input_policy_ready": _bool_true(
            new_user_observation_receipt_summary.get("observation_input_policy_ready")
        ),
        "new_user_observation_checklist_csv": DEFAULT_NEW_USER_OBSERVATION_CHECKLIST_CSV,
        "new_user_observation_checklist_md": DEFAULT_NEW_USER_OBSERVATION_CHECKLIST_MD,
        "new_user_observation_checklist_path_documented": _bool_true(
            new_user_observation_receipt_summary.get("observation_checklist_path_documented")
        ),
        "new_user_observation_template_next_action": _text(
            new_user_observation_receipt_summary.get(
                "new_user_observation_template_next_action"
            )
        ),
        "new_user_observation_primary_required_action": _text(
            new_user_observation_receipt_summary.get("primary_required_action")
        ),
        "register_gate_id_count": len(materialized_gate_ids),
        "register_gate_ids_complete": materialized_gate_ids == {spec["gate_id"] for spec in GATE_SPECS},
        "register_fail_closed_command_contract_ready": register_fail_closed_command_contract_ready,
        "register_fail_closed_required_token_count": len(REGISTER_FAIL_CLOSED_REQUIRED_TOKENS),
        "register_fail_closed_required_tokens": list(REGISTER_FAIL_CLOSED_REQUIRED_TOKENS),
        "register_fail_closed_missing_token_count": len(missing_register_fail_closed_tokens),
        "register_fail_closed_missing_tokens": missing_register_fail_closed_tokens,
        "register_contract_blocker_count": len(register_contract_blockers),
        "register_contract_blockers": register_contract_blockers,
        "primary_blocker_id": (
            blocked_rows[0]["gate_id"]
            if blocked_rows
            else (
                "developer_preview_action_register_fail_closed_contract"
                if register_contract_blockers
                else ""
            )
        ),
        "blocker_count": len(blockers),
        "blockers": blockers,
        "primary_blocker": blockers[0] if blockers else "",
        "primary_blocker_detail": primary_blocker_detail,
        "execution_enabled": False,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": next_required_step,
    }
    return {
        "summary": summary,
        "rows": rows,
        "receipt_work_order_rows": receipt_work_order_rows,
        "stage5_recovery_rows": stage5_recovery_rows,
        "external_operator_work_order_rows": external_operator_work_order_rows,
    }


def _write_json(path_like: str | Path, payload: dict[str, Any], *, root: Path = ROOT) -> None:
    path = _resolve(path_like, root=root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _csv_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, list):
        return ";".join(_text(item) for item in value if _text(item))
    return _text(value)


def _write_csv(
    path_like: str | Path,
    rows: list[dict[str, Any]],
    *,
    fields: list[str] = CSV_FIELDS,
    root: Path = ROOT,
) -> None:
    path = _resolve(path_like, root=root)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: _csv_value(row.get(field)) for field in fields})


def build_developer_preview_external_operator_work_order(
    audit_payload: dict[str, Any],
) -> dict[str, Any]:
    audit_summary = audit_payload.get("summary", {})
    rows = [
        row
        for row in audit_payload.get("external_operator_work_order_rows", [])
        if isinstance(row, dict)
    ]
    blocked_rows = [row for row in rows if not row.get("ready")]
    expected_flow_count = len(EXTERNAL_OPERATOR_WORK_ORDER_SPECS)
    materialized = len(rows) == expected_flow_count
    summary = {
        "packet_type": OPERATOR_WORK_ORDER_PACKET_TYPE,
        "schema_version": OPERATOR_WORK_ORDER_SCHEMA_VERSION,
        "status": "developer_preview_external_operator_work_order_ready"
        if materialized
        else "blocked_developer_preview_external_operator_work_order",
        "operator_work_order_materialized": materialized,
        "operator_flow_ready": bool(materialized and not blocked_rows),
        "expected_operator_flow_count": expected_flow_count,
        "operator_flow_count": len(rows),
        "blocked_operator_flow_count": len(blocked_rows),
        "primary_flow_id": (
            _text(blocked_rows[0].get("operator_flow_id")) if blocked_rows else ""
        ),
        "primary_gate_id": _text(blocked_rows[0].get("gate_id")) if blocked_rows else "",
        "primary_receipt_artifact": (
            _text(blocked_rows[0].get("primary_receipt_artifact")) if blocked_rows else ""
        ),
        "primary_blocker": _text(blocked_rows[0].get("blocker")) if blocked_rows else "",
        "primary_required_action": (
            _text(blocked_rows[0].get("required_action")) if blocked_rows else ""
        ),
        "final_gate_audit_path": DEFAULT_OUT_JSON,
        "final_gate_audit_status": _text(audit_summary.get("status")),
        "developer_preview_clean_baseline_ready": _bool_true(
            audit_summary.get("developer_preview_clean_baseline_ready")
        ),
        "runbook_path": DEFAULT_CORE_WORKFLOW_RUNBOOK_MD,
        "action_register_path": DEFAULT_REGISTER_MD,
        "execution_enabled": False,
        "external_state_mutated": False,
        "claim_promotion_allowed": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            _text(blocked_rows[0].get("required_action"))
            if blocked_rows
            else "All external operator receipt flows are ready for final gate review."
        ),
    }
    return {"summary": summary, "rows": rows}


def build_developer_preview_external_operator_command_pack(
    audit_payload: dict[str, Any],
) -> dict[str, Any]:
    audit_summary = audit_payload.get("summary", {})
    rows = _external_operator_command_rows()
    recommended_next_target = _text(audit_summary.get("next_operator_command_pack_target"))
    stage5_recovery_action = _text(
        audit_summary.get("stage5_restore_packet_primary_missing_restore_instruction")
    ) or _text(audit_summary.get("stage5_restore_packet_next_required_step"))
    recommended_next_action = (
        stage5_recovery_action
        if recommended_next_target == "stage5-recovery" and stage5_recovery_action
        else _text(audit_summary.get("next_required_step"))
    )
    summary = {
        "packet_type": OPERATOR_COMMAND_PACK_PACKET_TYPE,
        "schema_version": OPERATOR_COMMAND_PACK_SCHEMA_VERSION,
        "status": "developer_preview_external_operator_command_pack_ready",
        "command_pack_ready": True,
        "command_pack_materialized": True,
        "blocker_count": 0,
        "blockers": [],
        "primary_blocker": "",
        "target_count": len(rows),
        "command_count": sum(_int(row.get("command_count")) for row in rows),
        "required_env_var_count": sum(
            _int(row.get("required_env_var_count")) for row in rows
        ),
        "required_input_artifact_count": sum(
            _int(row.get("required_input_artifact_count")) for row in rows
        ),
        "platform_guard_count": sum(
            1 for row in rows if _text(row.get("platform_guard"))
        ),
        "targets": [row["target"] for row in rows],
        "shell_script_path": DEFAULT_OUT_OPERATOR_COMMAND_PACK_SH,
        "powershell_script_path": DEFAULT_OUT_OPERATOR_COMMAND_PACK_PS1,
        "powershell_targets": ["windows-repro", "final-gate"],
        "powershell_target_count": 2,
        "powershell_scope": (
            "PowerShell command pack intentionally supports only windows-repro and final-gate. "
            "Use the shell command pack for clean-checkout, stage5-recovery, linux-repro, and new-user observation targets."
        ),
        "windows_repro_powershell_command_pack_ready": True,
        "shell_platform_guard_normalizes_observed_platform": True,
        "shell_platform_guard_accepts_git_bash_windows": True,
        "clean_checkout_default_workdir_pattern": (
            "${RUNNER_TEMP:-${TMPDIR:-/tmp}}/betelgeuze-developer-preview-<UTC timestamp>"
        ),
        "clean_checkout_existing_workdir_fail_closed": True,
        "markdown_path": DEFAULT_OUT_OPERATOR_COMMAND_PACK_MD,
        "optional_export_env_var": "DEVELOPER_PREVIEW_EXPORT_DIR",
        "optional_clean_checkout_ref_env_var": "DEVELOPER_PREVIEW_REF",
        "operator_must_explicitly_run_target": True,
        "human_review_required_before_external_operator_run": True,
        "generated_scripts_non_executable_by_default": True,
        "clean_checkout_ref_checkout_supported": True,
        "optional_export_behavior": (
            "When DEVELOPER_PREVIEW_EXPORT_DIR is set, each target copies generated "
            "receipt artifacts into ${DEVELOPER_PREVIEW_EXPORT_DIR}/<target>/ after "
            "the fail-closed receipt step. Relative export paths are resolved from "
            "the directory where the command pack was invoked."
        ),
        "recommended_next_target": recommended_next_target,
        "recommended_next_command": _text(
            audit_summary.get("next_operator_command_pack_command")
        ),
        "recommended_next_action": recommended_next_action,
        "recommended_next_required_platform": _text(
            audit_summary.get("next_operator_command_pack_required_platform")
        ),
        "recommended_next_required_env_vars": list(
            audit_summary.get("next_operator_command_pack_required_env_vars") or []
        ),
        "recommended_next_required_input_artifacts": list(
            audit_summary.get("next_operator_command_pack_required_input_artifacts") or []
        ),
        "recommended_stage5_restore_packet_path": _text(
            audit_summary.get("stage5_restore_packet_json_path")
        ),
        "recommended_stage5_restore_packet_status": _text(
            audit_summary.get("stage5_restore_packet_status")
        ),
        "recommended_stage5_restore_packet_missing_source_artifact_count": _int(
            audit_summary.get("stage5_restore_packet_missing_source_artifact_count")
        ),
        "recommended_stage5_restore_packet_primary_missing_source_argument": _text(
            audit_summary.get("stage5_restore_packet_primary_missing_source_argument")
        ),
        "recommended_stage5_restore_packet_primary_missing_source_artifact_path": _text(
            audit_summary.get("stage5_restore_packet_primary_missing_source_artifact_path")
        ),
        "recommended_stage5_restore_packet_primary_missing_pipeline_summary_json": _text(
            audit_summary.get(
                "stage5_restore_packet_primary_missing_pipeline_summary_json"
            )
        ),
        "recommended_stage5_restore_packet_primary_missing_pipeline_summary_present": (
            _bool_true(
                audit_summary.get(
                    "stage5_restore_packet_primary_missing_pipeline_summary_present"
                )
            )
        ),
        "recommended_stage5_restore_packet_primary_missing_profile_json": _text(
            audit_summary.get("stage5_restore_packet_primary_missing_profile_json")
        ),
        "recommended_stage5_restore_packet_primary_missing_profile_present": _bool_true(
            audit_summary.get(
                "stage5_restore_packet_primary_missing_profile_present"
            )
        ),
        "recommended_stage5_restore_packet_primary_missing_restore_queue_ready": _bool_true(
            audit_summary.get(
                "stage5_restore_packet_primary_missing_restore_queue_ready"
            )
        ),
        "recommended_stage5_restore_packet_primary_missing_restore_instruction": _text(
            audit_summary.get("stage5_restore_packet_primary_missing_restore_instruction")
        ),
        "final_gate_audit_path": DEFAULT_OUT_JSON,
        "final_gate_audit_status": _text(audit_summary.get("status")),
        "developer_preview_clean_baseline_ready": _bool_true(
            audit_summary.get("developer_preview_clean_baseline_ready")
        ),
        "runbook_path": DEFAULT_CORE_WORKFLOW_RUNBOOK_MD,
        "action_register_path": DEFAULT_REGISTER_MD,
        "execution_enabled": False,
        "external_state_mutated": False,
        "claim_promotion_allowed": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "Run one command-pack target on the required platform, then rebuild the final gate audit."
        ),
    }
    return {"summary": summary, "rows": rows}


def _render_md(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# Developer Preview Final Gate Audit",
        "",
        f"- status: `{summary['status']}`",
        f"- developer_preview_clean_baseline_ready: `{summary['developer_preview_clean_baseline_ready']}`",
        f"- developer_preview_exit_ready: `{summary['developer_preview_exit_ready']}`",
        f"- clean_checkout_ready: `{summary['clean_checkout_ready']}`",
        f"- windows_reproducibility_ready: `{summary['windows_reproducibility_ready']}`",
        f"- new_user_observation_ready: `{summary['new_user_observation_ready']}`",
        f"- ready_gate_count: `{summary['ready_gate_count']}` / `{summary['gate_count']}`",
        f"- missing_receipt_count: `{summary['missing_receipt_count']}`",
        f"- present_blocked_receipt_count: `{summary['present_blocked_receipt_count']}`",
        f"- receipt_blocker_count: `{summary['receipt_blocker_count']}`",
        f"- blocker_count: `{summary['blocker_count']}`",
        f"- receipt_work_order_row_count: `{summary['receipt_work_order_row_count']}`",
        f"- receipt_work_order_source_blocker_count: `{summary['receipt_work_order_source_blocker_count']}`",
        f"- stage5_recovery_row_count: `{summary['stage5_recovery_row_count']}`",
        f"- stage5_missing_source_artifact_count: `{summary['stage5_missing_source_artifact_count']}`",
        f"- stage5_recovery_operator_work_order_ready: `{summary['stage5_recovery_operator_work_order_ready']}`",
        f"- stage5_input_family_csv_present: `{summary['stage5_input_family_csv_present']}`",
        f"- stage5_input_family_md_present: `{summary['stage5_input_family_md_present']}`",
        f"- stage5_restore_packet_status: `{summary['stage5_restore_packet_status'] or '-'}`",
        f"- stage5_restore_packet_missing_source_artifact_count: `{summary['stage5_restore_packet_missing_source_artifact_count']}`",
        f"- stage5_restore_packet_primary_missing_source_artifact_path: `{summary['stage5_restore_packet_primary_missing_source_artifact_path'] or '-'}`",
        f"- stage5_restore_packet_operator_action_required: `{summary['stage5_restore_packet_operator_action_required']}`",
        f"- external_operator_work_order_ready: `{summary['external_operator_work_order_ready']}`",
        f"- external_operator_work_order_blocked_row_count: `{summary['external_operator_work_order_blocked_row_count']}`",
        f"- external_operator_command_pack_target_count: `{summary['external_operator_command_pack_target_count']}`",
        f"- next_operator_command_pack_target: `{summary['next_operator_command_pack_target'] or '-'}`",
        f"- next_operator_command_pack_command: `{summary['next_operator_command_pack_command'] or '-'}`",
        f"- clean_checkout_operator_work_order_ready: `{summary['clean_checkout_operator_work_order_ready']}`",
        f"- windows_reproducibility_operator_work_order_ready: `{summary['windows_reproducibility_operator_work_order_ready']}`",
        f"- new_user_observation_operator_work_order_ready: `{summary['new_user_observation_operator_work_order_ready']}`",
        f"- register_gate_ids_complete: `{summary['register_gate_ids_complete']}`",
        f"- register_fail_closed_command_contract_ready: `{summary['register_fail_closed_command_contract_ready']}`",
        f"- register_fail_closed_missing_token_count: `{summary['register_fail_closed_missing_token_count']}`",
        f"- primary_blocker_id: `{summary['primary_blocker_id']}`",
        f"- primary_blocker: `{summary['primary_blocker'] or '-'}`",
        f"- primary_blocker_detail: `{summary['primary_blocker_detail'] or '-'}`",
        f"- primary_source_blocker: `{summary['receipt_work_order_primary_source_blocker']}`",
        "",
        "| priority | gate | status | receipts | blocker |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['priority']}` | `{row['gate_id']}` | `{row['status']}` | "
            f"`{row['present_receipt_count']}/{row['required_receipt_count']}` | `{row['blocker']}` |"
        )
    lines.extend(
        [
            "",
            "## Receipt Work Order",
            "",
            "| gate | receipt | expected status | required fields | blocker | action |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
    )
    for row in payload.get("receipt_work_order_rows", []):
        required_fields = _join_metrics(
            _metric("true", row["required_true_field_count"]),
            _metric("zero", row["required_zero_field_count"]),
        )
        lines.append(
            f"| `{row['gate_id']}` | `{row['receipt_artifact']}` | "
            f"`{row['required_receipt_status']}` | `{required_fields}` | "
            f"`{row['blocker_detail']}` | {row['required_action']} |"
        )
    lines.extend(
        [
            "",
            "## External Operator Work Order",
            "",
            "| flow | platform | receipt | status | blocker | action |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
    )
    for row in payload.get("external_operator_work_order_rows", []):
        action = row["required_action"] or "Ready receipt can be attached to the final gate audit."
        lines.append(
            f"| `{row['operator_flow_id']}` | `{row['required_platform']}` | "
            f"`{row['primary_receipt_artifact']}` | `{row['status']}` | "
            f"`{row['blocker'] or '-'}` | {action} |"
        )
    lines.extend(
        [
            "",
            "## Stage5 Source Recovery",
            "",
            "| gate | task | source argument | source artifact | present | action |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
    )
    for row in payload.get("stage5_recovery_rows", []):
        lines.append(
            f"| `{row['gate_id']}` | `{row['task_key']}` | `{row['source_argument']}` | "
            f"`{row['source_artifact_path']}` | `{row['source_artifact_present']}` | "
            f"{row['required_action']} |"
        )
    lines.extend(["", CLAIM_BOUNDARY, ""])
    return "\n".join(lines)


def _render_operator_work_order_md(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# Developer Preview External Operator Work Order",
        "",
        f"- status: `{summary['status']}`",
        f"- operator_work_order_materialized: `{summary['operator_work_order_materialized']}`",
        f"- operator_flow_ready: `{summary['operator_flow_ready']}`",
        f"- operator_flow_count: `{summary['operator_flow_count']}`",
        f"- blocked_operator_flow_count: `{summary['blocked_operator_flow_count']}`",
        f"- primary_flow_id: `{summary['primary_flow_id']}`",
        f"- primary_receipt_artifact: `{summary['primary_receipt_artifact']}`",
        f"- primary_blocker: `{summary['primary_blocker']}`",
        f"- final_gate_audit_status: `{summary['final_gate_audit_status']}`",
        "",
        "| flow | label | platform | runbook section | receipt | status | blocker | action |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload.get("rows", []):
        action = row["required_action"] or "Ready receipt can be attached to the final gate audit."
        lines.append(
            f"| `{row['operator_flow_id']}` | {row['label']} | "
            f"`{row['required_platform']}` | `{row['runbook_section']}` | "
            f"`{row['primary_receipt_artifact']}` | `{row['status']}` | "
            f"`{row['blocker'] or '-'}` | {action} |"
        )
    lines.extend(["", CLAIM_BOUNDARY, ""])
    return "\n".join(lines)


def _render_operator_command_pack_sh(payload: dict[str, Any]) -> str:
    targets = " ".join(row["target"] for row in payload.get("rows", []))
    lines = [
        "#!/usr/bin/env bash",
        "set -euo pipefail",
        "",
        "# Developer Preview external operator command pack.",
        "# Runs only the target passed as the first argument.",
        "# It writes local receipts/logs under .betelgeuze/ or runs/ and does not mutate external state.",
        "# Optional: set DEVELOPER_PREVIEW_EXPORT_DIR to copy generated receipts out of clean checkouts.",
        "",
        "require_env() {",
        "  local name=\"$1\"",
        "  if [[ -z \"${!name:-}\" ]]; then",
        "    echo \"missing required environment variable: ${name}\" >&2",
        "    exit 3",
        "  fi",
        "}",
        "",
        "detect_python() {",
        "  if [[ -n \"${DEVELOPER_PREVIEW_PYTHON:-}\" ]]; then",
        "    printf '%s\\n' \"${DEVELOPER_PREVIEW_PYTHON}\"",
        "    return",
        "  fi",
        "  if command -v python3 >/dev/null 2>&1; then",
        "    printf '%s\\n' python3",
        "    return",
        "  fi",
        "  if command -v python >/dev/null 2>&1; then",
        "    printf '%s\\n' python",
        "    return",
        "  fi",
        "  echo \"missing Python interpreter; set DEVELOPER_PREVIEW_PYTHON\" >&2",
        "  exit 6",
        "}",
        "",
        "require_file() {",
        "  local path=\"$1\"",
        "  if [[ ! -f \"$path\" ]]; then",
        "    echo \"missing required input artifact for target ${target}: ${path}\" >&2",
        "    echo \"run the prerequisite command-pack target first when applicable\" >&2",
        "    exit 5",
        "  fi",
        "}",
        "",
        "require_platform() {",
        "  local expected=\"$1\"",
        "  local observed_raw observed",
        "  observed_raw=\"$(${PYTHON_BIN} -c 'import platform; print(platform.system().lower())')\"",
        "  case \"${observed_raw}\" in",
        "    linux*) observed=\"linux\" ;;",
        "    windows*|win32*|cygwin*|cygwin_nt*|msys*|mingw*) observed=\"windows\" ;;",
        "    *) observed=\"${observed_raw}\" ;;",
        "  esac",
        "  case \"${expected}:${observed}\" in",
        "    linux:linux|windows:windows) ;;",
        "    *)",
        "      echo \"target ${target} requires ${expected}; observed ${observed_raw}\" >&2",
        "      exit 4",
        "      ;;",
        "  esac",
        "}",
        "",
        "resolve_clean_checkout_workdir() {",
        "  local configured=\"${DEVELOPER_PREVIEW_WORKDIR:-}\"",
        "  local resolved",
        "  if [[ -n \"${configured}\" ]]; then",
        "    resolved=\"${configured}\"",
        "  else",
        "    resolved=\"${RUNNER_TEMP:-${TMPDIR:-/tmp}}/betelgeuze-developer-preview-$(date -u +%Y%m%dT%H%M%SZ)\"",
        "  fi",
        "  if [[ -e \"${resolved}\" ]]; then",
        "    echo \"clean checkout workdir already exists: ${resolved}\" >&2",
        "    echo \"set DEVELOPER_PREVIEW_WORKDIR to a new path or remove the old clone outside this script\" >&2",
        "    exit 7",
        "  fi",
        "  printf '%s\\n' \"${resolved}\"",
        "}",
        "",
        "write_clean_checkout_source_provenance() {",
        "  local path=\"$1\"",
        "  mkdir -p \"$(dirname \"$path\")\"",
        "  \"${PYTHON_BIN}\" - \"$path\" <<'PY'",
        "import hashlib",
        "import json",
        "import os",
        "import subprocess",
        "import sys",
        "",
        "def run(args):",
        "    result = subprocess.run(args, check=False, capture_output=True, text=True)",
        "    return result.stdout.strip(), result.returncode",
        "",
        "path = sys.argv[1]",
        "repo_url = os.environ.get('DEVELOPER_PREVIEW_REPO_URL', '').strip()",
        "requested_ref = os.environ.get('DEVELOPER_PREVIEW_REF', '').strip()",
        "head_sha, _ = run(['git', 'rev-parse', 'HEAD'])",
        "checked_out_ref, _ = run(['git', 'rev-parse', '--abbrev-ref', 'HEAD'])",
        "status_text, _ = run(['git', 'status', '--porcelain'])",
        "tracked_text, _ = run(['git', 'ls-files'])",
        "dirty_lines = [line for line in status_text.splitlines() if line.strip()]",
        "payload = {",
        "    'summary': {",
        "        'packet_type': 'developer_preview_clean_checkout_source_provenance',",
        "        'schema_version': 'developer_preview_clean_checkout_source_provenance_v1',",
        "        'source_repo_url_present': bool(repo_url),",
        "        'source_repo_url_fingerprint': hashlib.sha256(repo_url.encode('utf-8')).hexdigest() if repo_url else '',",
        "        'source_ref_requested': requested_ref,",
        "        'source_ref_requested_present': bool(requested_ref),",
        "        'source_checked_out_ref': checked_out_ref,",
        "        'source_remote_url_redacted': 'sha256:' + hashlib.sha256(repo_url.encode('utf-8')).hexdigest() if repo_url else '',",
        "        'head_sha': head_sha,",
        "        'tracked_file_count': len([line for line in tracked_text.splitlines() if line.strip()]),",
        "        'git_status_porcelain_empty': not dirty_lines,",
        "        'working_tree_clean': not dirty_lines,",
        "        'dirty_path_count': len(dirty_lines),",
        "        'execution_enabled': False,",
        "        'external_state_mutated': False,",
        "        'claim_promotion_allowed': False,",
        "    },",
        "    'dirty_rows': [{'status_line': line} for line in dirty_lines[:50]],",
        "}",
        "with open(path, 'w', encoding='utf-8') as handle:",
        "    json.dump(payload, handle, indent=2, sort_keys=True)",
        "    handle.write('\\n')",
        "PY",
        "}",
        "",
        "COMMAND_PACK_ROOT=\"$(pwd)\"",
        "EXPORT_DIR=\"${DEVELOPER_PREVIEW_EXPORT_DIR:-}\"",
        "if [[ -n \"${EXPORT_DIR}\" && \"${EXPORT_DIR}\" != /* ]]; then",
        "  EXPORT_DIR=\"${COMMAND_PACK_ROOT}/${EXPORT_DIR}\"",
        "fi",
        "",
        "export_artifacts() {",
        "  local target_name=\"$1\"",
        "  shift",
        "  if [[ -z \"${EXPORT_DIR}\" ]]; then",
        "    echo \"target ${target_name} receipts remain under $(pwd)/.betelgeuze or $(pwd)/runs\" >&2",
        "    return 0",
        "  fi",
        "  local target_dir=\"${EXPORT_DIR}/${target_name}\"",
        "  mkdir -p \"${target_dir}\"",
        "  local artifact",
        "  for artifact in \"$@\"; do",
        "    if [[ -e \"${artifact}\" ]]; then",
        "      mkdir -p \"${target_dir}/$(dirname \"${artifact}\")\"",
        "      cp -R \"${artifact}\" \"${target_dir}/${artifact}\"",
        "    else",
        "      echo \"receipt artifact missing for ${target_name}: ${artifact}\" >&2",
        "    fi",
        "  done",
        "  echo \"exported target ${target_name} artifacts to ${target_dir}\" >&2",
        "}",
        "",
        "PYTHON_BIN=\"$(detect_python)\"",
        "",
        "target=\"${1:-}\"",
        "case \"$target\" in",
    ]
    for row in payload.get("rows", []):
        lines.extend(
            [
                f"  {row['target']})",
                f"    # {row['label']} ({row['required_platform']})",
            ]
        )
        if _text(row.get("platform_guard")):
            lines.append(f"    require_platform {_text(row['platform_guard'])}")
        for env_var in row.get("required_env_vars", []):
            lines.append(f"    require_env {_text(env_var)}")
        for artifact in row.get("required_input_artifacts", []):
            lines.append(f"    require_file {_text(artifact)}")
        for command in row["commands"]:
            lines.append(f"    {command}")
        lines.extend(["    ;;", ""])
    lines.extend(
        [
            "  *)",
            f"    echo \"usage: $0 {{{targets.replace(' ', '|')}}}\" >&2",
            "    exit 2",
            "    ;;",
            "esac",
            "",
        ]
    )
    return "\n".join(lines)


def _ps_single_quote(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _ps_array(values: list[str]) -> str:
    return "@(" + ", ".join(_ps_single_quote(value) for value in values) + ")"


def _render_operator_command_pack_ps1(payload: dict[str, Any]) -> str:
    rows = {
        _text(row.get("target")): row
        for row in payload.get("rows", [])
        if isinstance(row, dict)
    }
    windows_artifacts = [
        _text(item)
        for item in rows.get("windows-repro", {}).get("receipt_artifacts", [])
        if _text(item)
    ]
    final_artifacts = [
        _text(item)
        for item in rows.get("final-gate", {}).get("receipt_artifacts", [])
        if _text(item)
    ]
    pytest_targets = [
        "tests/unit/test_betelgeuze_product_readiness.py",
        "tests/unit/test_betelgeuze_product_cli.py",
        "tests/unit/test_betelgeuze_cameo_cli.py",
        "tests/unit/test_betelgeuze_cleanup_cli.py",
    ]
    final_gate_args = [
        "tools/product/build_developer_preview_final_gate_audit.py",
        "--out-json",
        DEFAULT_OUT_JSON,
        "--out-csv",
        DEFAULT_OUT_CSV,
        "--out-md",
        DEFAULT_OUT_MD,
        "--out-operator-work-order-json",
        DEFAULT_OUT_OPERATOR_WORK_ORDER_JSON,
        "--out-operator-work-order-csv",
        DEFAULT_OUT_OPERATOR_WORK_ORDER_CSV,
        "--out-operator-work-order-md",
        DEFAULT_OUT_OPERATOR_WORK_ORDER_MD,
        "--out-operator-command-pack-json",
        DEFAULT_OUT_OPERATOR_COMMAND_PACK_JSON,
        "--out-operator-command-pack-sh",
        DEFAULT_OUT_OPERATOR_COMMAND_PACK_SH,
        "--out-operator-command-pack-ps1",
        DEFAULT_OUT_OPERATOR_COMMAND_PACK_PS1,
        "--out-operator-command-pack-md",
        DEFAULT_OUT_OPERATOR_COMMAND_PACK_MD,
    ]
    return "\n".join(
        [
            "param(",
            "  [Parameter(Mandatory=$true)]",
            "  [ValidateSet('windows-repro','final-gate')]",
            "  [string]$Target",
            ")",
            "$ErrorActionPreference = 'Stop'",
            "",
            "# Developer Preview external operator PowerShell command pack.",
            "# Supports Windows reproducibility and final-gate receipt refresh targets.",
            "# Use the shell command pack for clean-checkout, linux-repro, and new-user observation targets.",
            "",
            "function Detect-Python {",
            "  if ($env:DEVELOPER_PREVIEW_PYTHON) { return $env:DEVELOPER_PREVIEW_PYTHON }",
            "  $python = Get-Command python -ErrorAction SilentlyContinue",
            "  if ($python) { return $python.Source }",
            "  $py = Get-Command py -ErrorAction SilentlyContinue",
            "  if ($py) { return $py.Source }",
            "  throw 'missing Python interpreter; set DEVELOPER_PREVIEW_PYTHON'",
            "}",
            "",
            "function Require-Platform([string]$Expected) {",
            "  $observed = & $PythonBin -c 'import platform; print(platform.system().lower())'",
            "  if ($Expected -eq 'windows' -and $observed -ne 'windows') {",
            "    throw \"target $Target requires windows; observed $observed\"",
            "  }",
            "}",
            "",
            "function Invoke-Checked([string]$Command, [string[]]$Arguments) {",
            "  & $Command @Arguments",
            "  if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }",
            "}",
            "",
            "function Export-Artifacts([string]$TargetName, [string[]]$Artifacts) {",
            "  $exportDir = $env:DEVELOPER_PREVIEW_EXPORT_DIR",
            "  if ([string]::IsNullOrWhiteSpace($exportDir)) {",
            "    Write-Host \"target $TargetName receipts remain under $(Get-Location)\"",
            "    return",
            "  }",
            "  if (-not [System.IO.Path]::IsPathRooted($exportDir)) {",
            "    $exportDir = Join-Path (Get-Location) $exportDir",
            "  }",
            "  $targetDir = Join-Path $exportDir $TargetName",
            "  New-Item -ItemType Directory -Force -Path $targetDir | Out-Null",
            "  foreach ($artifact in $Artifacts) {",
            "    if (Test-Path $artifact) {",
            "      $dest = Join-Path $targetDir $artifact",
            "      $destParent = Split-Path -Parent $dest",
            "      if ($destParent) { New-Item -ItemType Directory -Force -Path $destParent | Out-Null }",
            "      Copy-Item -Recurse -Force -Path $artifact -Destination $dest",
            "    } else {",
            "      Write-Warning \"receipt artifact missing for $TargetName: $artifact\"",
            "    }",
            "  }",
            "}",
            "",
            "$PythonBin = Detect-Python",
            "",
            "switch ($Target) {",
            "  'windows-repro' {",
            "    Require-Platform 'windows'",
            "    if (-not (Get-Command bash -ErrorAction SilentlyContinue)) {",
            "      throw 'missing bash; install Git for Windows or set up a shell that can run ./scripts/ai-verify.sh'",
            "    }",
            "    New-Item -ItemType Directory -Force -Path '.betelgeuze' | Out-Null",
            "    Invoke-Checked 'bash' @('-o','pipefail','-c','./scripts/ai-verify.sh | tee .betelgeuze/developer_preview_windows_ai_verify.log')",
            "    $pytestArgs = @('-m','pytest','-q') + "
            + _ps_array(pytest_targets)
            + " + @('--junitxml','.betelgeuze/developer_preview_windows_reproducibility_pytest.xml')",
            "    Invoke-Checked $PythonBin $pytestArgs",
            "    $receiptArgs = @(",
            "      'tools/product/build_developer_preview_platform_reproducibility_receipt.py',",
            "      '--platform','windows',",
            "      '--ai-verify-log','.betelgeuze/developer_preview_windows_ai_verify.log',",
            "      '--pytest-junit-xml','.betelgeuze/developer_preview_windows_reproducibility_pytest.xml',",
            "      '--allow-blocked',",
            "      '--out-json','.betelgeuze/developer_preview_windows_reproducibility_receipt.json',",
            "      '--out-md','.betelgeuze/developer_preview_windows_reproducibility_receipt.md'",
            "    )",
            "    Invoke-Checked $PythonBin $receiptArgs",
            "    Export-Artifacts 'windows-repro' " + _ps_array(windows_artifacts),
            "  }",
            "  'final-gate' {",
            "    $finalArgs = " + _ps_array(final_gate_args),
            "    Invoke-Checked $PythonBin $finalArgs",
            "    Export-Artifacts 'final-gate' " + _ps_array(final_artifacts),
            "  }",
            "}",
            "",
        ]
    )


def _render_operator_command_pack_md(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# Developer Preview External Operator Command Pack",
        "",
        f"- status: `{summary['status']}`",
        f"- target_count: `{summary['target_count']}`",
        f"- command_count: `{summary['command_count']}`",
        f"- required_env_var_count: `{summary['required_env_var_count']}`",
        f"- required_input_artifact_count: `{summary['required_input_artifact_count']}`",
        f"- platform_guard_count: `{summary['platform_guard_count']}`",
        f"- optional_export_env_var: `{summary['optional_export_env_var']}`",
        f"- powershell_script_path: `{summary['powershell_script_path']}`",
        f"- powershell_targets: `{_csv_value(summary['powershell_targets'])}`",
        f"- powershell_scope: `{summary['powershell_scope']}`",
        f"- shell_platform_guard_normalizes_observed_platform: `{summary['shell_platform_guard_normalizes_observed_platform']}`",
        f"- shell_platform_guard_accepts_git_bash_windows: `{summary['shell_platform_guard_accepts_git_bash_windows']}`",
        f"- clean_checkout_default_workdir_pattern: `{summary['clean_checkout_default_workdir_pattern']}`",
        f"- clean_checkout_existing_workdir_fail_closed: `{summary['clean_checkout_existing_workdir_fail_closed']}`",
        f"- optional_clean_checkout_ref_env_var: `{summary['optional_clean_checkout_ref_env_var']}`",
        f"- clean_checkout_ref_checkout_supported: `{summary['clean_checkout_ref_checkout_supported']}`",
        f"- recommended_next_target: `{summary['recommended_next_target'] or '-'}`",
        f"- recommended_next_command: `{summary['recommended_next_command'] or '-'}`",
        f"- recommended_next_action: `{summary['recommended_next_action'] or '-'}`",
        f"- recommended_stage5_restore_packet_status: `{summary['recommended_stage5_restore_packet_status'] or '-'}`",
        f"- recommended_stage5_restore_packet_missing_source_artifact_count: `{summary['recommended_stage5_restore_packet_missing_source_artifact_count']}`",
        f"- recommended_stage5_restore_packet_primary_missing_source_argument: `{summary['recommended_stage5_restore_packet_primary_missing_source_argument'] or '-'}`",
        f"- recommended_stage5_restore_packet_primary_missing_source_artifact_path: `{summary['recommended_stage5_restore_packet_primary_missing_source_artifact_path'] or '-'}`",
        f"- recommended_stage5_restore_packet_primary_missing_pipeline_summary_json: `{summary['recommended_stage5_restore_packet_primary_missing_pipeline_summary_json'] or '-'}`",
        f"- recommended_stage5_restore_packet_primary_missing_pipeline_summary_present: `{summary['recommended_stage5_restore_packet_primary_missing_pipeline_summary_present']}`",
        f"- recommended_stage5_restore_packet_primary_missing_profile_json: `{summary['recommended_stage5_restore_packet_primary_missing_profile_json'] or '-'}`",
        f"- recommended_stage5_restore_packet_primary_missing_profile_present: `{summary['recommended_stage5_restore_packet_primary_missing_profile_present']}`",
        f"- recommended_stage5_restore_packet_primary_missing_restore_queue_ready: `{summary['recommended_stage5_restore_packet_primary_missing_restore_queue_ready']}`",
        f"- final_gate_audit_status: `{summary['final_gate_audit_status']}`",
        "",
        summary["optional_export_behavior"],
        "",
        "The `clean-checkout` target creates a timestamped fresh clone under "
        "`${RUNNER_TEMP:-${TMPDIR:-/tmp}}` by default. "
        "When `DEVELOPER_PREVIEW_WORKDIR` is set, the path must not already exist; "
        "an existing path fails closed so hidden local state is not mixed into the receipt.",
        "Set `DEVELOPER_PREVIEW_REF` to pin `clean-checkout` to a reviewed branch, tag, "
        "or commit; the target fetches that ref, checks out `FETCH_HEAD` detached, "
        "and records the requested ref in checkout provenance.",
        "The `stage5-recovery` target is a read-only handoff helper: run it after a "
        "blocked clean-checkout receipt has emitted the stage5 input-family CSV/MD to "
        "refresh the final gate audit, build the stage5 restore packet, and export both "
        "the recovery work order and restore packet.",
        "",
        summary["powershell_scope"],
        "",
        "Run one target from the generated shell script:",
        "",
        "```bash",
        f"bash {summary['shell_script_path']} <target>",
        "```",
        "",
        "Run the Windows reproducibility target from PowerShell:",
        "",
        "```powershell",
        f"pwsh -File {summary['powershell_script_path']} -Target windows-repro",
        "```",
        "",
    ]
    for row in payload.get("rows", []):
        lines.extend(
            [
                f"## {row['target']}",
                "",
                f"- label: `{row['label']}`",
                f"- platform: `{row['required_platform']}`",
                f"- platform_guard: `{row['platform_guard'] or '-'}`",
                f"- required_env_vars: `{_csv_value(row['required_env_vars']) or '-'}`",
                f"- required_inputs: `{_csv_value(row['required_input_artifacts']) or '-'}`",
                f"- receipts: `{_csv_value(row['receipt_artifacts'])}`",
                f"- optional_export_env_var: `{row['optional_export_env_var']}`",
                "",
                "```bash",
            ]
        )
        lines.extend(row["commands"])
        lines.extend(["```", ""])
    lines.extend([CLAIM_BOUNDARY, ""])
    return "\n".join(lines)


def _write_text(path_like: str | Path, text: str, *, root: Path = ROOT) -> None:
    path = _resolve(path_like, root=root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build Developer Preview final gate audit.")
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument("--register-md", default=DEFAULT_REGISTER_MD)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    parser.add_argument(
        "--out-operator-work-order-json",
        default=DEFAULT_OUT_OPERATOR_WORK_ORDER_JSON,
    )
    parser.add_argument(
        "--out-operator-work-order-csv",
        default=DEFAULT_OUT_OPERATOR_WORK_ORDER_CSV,
    )
    parser.add_argument(
        "--out-operator-work-order-md",
        default=DEFAULT_OUT_OPERATOR_WORK_ORDER_MD,
    )
    parser.add_argument(
        "--out-operator-command-pack-json",
        default=DEFAULT_OUT_OPERATOR_COMMAND_PACK_JSON,
    )
    parser.add_argument(
        "--out-operator-command-pack-sh",
        default=DEFAULT_OUT_OPERATOR_COMMAND_PACK_SH,
    )
    parser.add_argument(
        "--out-operator-command-pack-ps1",
        default=DEFAULT_OUT_OPERATOR_COMMAND_PACK_PS1,
    )
    parser.add_argument(
        "--out-operator-command-pack-md",
        default=DEFAULT_OUT_OPERATOR_COMMAND_PACK_MD,
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    root = Path(args.root)
    payload = build_developer_preview_final_gate_audit(register_md=args.register_md, root=root)
    operator_work_order_payload = build_developer_preview_external_operator_work_order(payload)
    operator_command_pack_payload = build_developer_preview_external_operator_command_pack(payload)
    _write_json(args.out_json, payload, root=root)
    _write_csv(args.out_csv, payload["rows"], root=root)
    _write_text(args.out_md, _render_md(payload), root=root)
    _write_json(args.out_operator_work_order_json, operator_work_order_payload, root=root)
    _write_csv(
        args.out_operator_work_order_csv,
        operator_work_order_payload["rows"],
        fields=OPERATOR_WORK_ORDER_CSV_FIELDS,
        root=root,
    )
    _write_text(
        args.out_operator_work_order_md,
        _render_operator_work_order_md(operator_work_order_payload),
        root=root,
    )
    _write_json(args.out_operator_command_pack_json, operator_command_pack_payload, root=root)
    _write_text(
        args.out_operator_command_pack_sh,
        _render_operator_command_pack_sh(operator_command_pack_payload),
        root=root,
    )
    _write_text(
        args.out_operator_command_pack_ps1,
        _render_operator_command_pack_ps1(operator_command_pack_payload),
        root=root,
    )
    _write_text(
        args.out_operator_command_pack_md,
        _render_operator_command_pack_md(operator_command_pack_payload),
        root=root,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

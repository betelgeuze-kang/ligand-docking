#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT_JSON = "runs/product_image_smoke_preflight_current.json"
DEFAULT_OUT_MD = "runs/product_image_smoke_preflight_current.md"
DEFAULT_OUT_RUNNER_HYGIENE_WORK_ORDER_JSON = (
    "runs/product_image_smoke_runner_hygiene_work_order_current.json"
)
DEFAULT_OUT_RUNNER_HYGIENE_WORK_ORDER_CSV = (
    "runs/product_image_smoke_runner_hygiene_work_order_current.csv"
)
DEFAULT_OUT_RUNNER_HYGIENE_WORK_ORDER_MD = (
    "runs/product_image_smoke_runner_hygiene_work_order_current.md"
)
DEFAULT_OUT_RUNNER_HYGIENE_COMMAND_PACK_JSON = (
    "runs/product_image_smoke_runner_hygiene_command_pack_current.json"
)
DEFAULT_OUT_RUNNER_HYGIENE_COMMAND_PACK_SH = (
    "runs/product_image_smoke_runner_hygiene_command_pack_current.sh"
)
DEFAULT_OUT_RUNNER_HYGIENE_COMMAND_PACK_MD = (
    "runs/product_image_smoke_runner_hygiene_command_pack_current.md"
)
DEFAULT_RECEIPT_JSON = "runs/product_image_smoke_receipt_current.json"
RUNNER_HYGIENE_SCHEMA_VERSION = "product_image_runner_hygiene_v1"
RUNNER_HYGIENE_WORK_ORDER_SCHEMA_VERSION = "product_image_smoke_runner_hygiene_work_order_v1"
RUNNER_HYGIENE_COMMAND_PACK_SCHEMA_VERSION = "product_image_smoke_runner_hygiene_command_pack_v1"
WORKFLOW_SOURCES = {
    ".github/workflows/product-api-worker.yml",
    ".github/workflows/product-image-smoke.yml",
}
PRODUCT_IMAGE_SMOKE_PR_TRIGGER_REQUIRED_PATHS = (
    "deploy/verify_product_image.sh",
    "scripts/normalize_product_image_smoke_artifact_ownership.sh",
    "tools/product/build_product_image_smoke_preflight.py",
    "tools/build_product_image_smoke_preflight.py",
    "tests/unit/test_build_product_image_smoke_preflight.py",
)

RUNNER_HYGIENE_WORK_ORDER_FIELDS = [
    "blocker_id",
    "status",
    "expected_receipt_field",
    "expected_value",
    "observed_value",
    "required_action",
    "verification_command",
    "receipt_json",
    "execution_enabled",
    "external_state_mutated",
]

RUNNER_HYGIENE_BLOCKER_FIELD_MAP = {
    "workspace_smoke_artifact_current_cleanup_not_ready": (
        "workspace_smoke_artifact_current_cleanup_ready",
        True,
    ),
    "workspace_smoke_artifact_current_owner_not_normalized": (
        "workspace_smoke_artifact_current_owner_ready",
        True,
    ),
    "workspace_smoke_artifact_current_not_writable": (
        "workspace_smoke_artifact_current_writable_ready",
        True,
    ),
    "workspace_smoke_artifact_current_permission_error": (
        "workspace_smoke_artifact_current_permission_error",
        "",
    ),
    "receipt_runner_hygiene_schema_missing": (
        "receipt_runner_hygiene_schema_version",
        RUNNER_HYGIENE_SCHEMA_VERSION,
    ),
    "receipt_runner_smoke_dir_inside_workspace": (
        "receipt_runner_smoke_dir_outside_workspace",
        True,
    ),
    "receipt_container_output_uid_gid_not_pinned": (
        "receipt_container_output_uid_gid_pinned",
        True,
    ),
    "receipt_container_output_uid_gid_not_host": (
        "receipt_container_output_uid_gid_matches_host",
        True,
    ),
    "receipt_container_output_uid_gid_root": (
        "receipt_container_output_uid_gid_non_root",
        True,
    ),
    "receipt_workspace_runner_smoke_dir_cleanup_not_ready": (
        "receipt_workspace_runner_smoke_dir_cleanup_ready",
        True,
    ),
    "receipt_runner_smoke_dir_still_exists_after_cleanup": (
        "receipt_workspace_runner_smoke_dir_exists_after_cleanup",
        False,
    ),
}

CLAIM_BOUNDARY = (
    "Product image smoke preflight only; checks local Docker availability and verifies that the product image "
    "smoke script/workflow fail closed and expose Docker-host preparation plus ROCm-runtime runner validation "
    "commands. It does not build images, run containers, run docking, mutate Docker state, upload, deploy, "
    "submit, email, or delete files."
)


def _runner_hygiene_command_row(
    *,
    target: str,
    label: str,
    required_platform: str,
    commands: list[str],
    writes_artifacts: list[str],
    platform_guard: str = "",
) -> dict[str, Any]:
    return {
        "target": target,
        "label": label,
        "required_platform": required_platform,
        "platform_guard": platform_guard,
        "commands": commands,
        "command_count": len(commands),
        "writes_artifacts": writes_artifacts,
        "execution_enabled": False,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
    }


def build_product_image_smoke_runner_hygiene_command_pack(
    preflight_payload: dict[str, Any],
    work_order_payload: dict[str, Any],
) -> dict[str, Any]:
    preflight_summary = preflight_payload.get("summary", {})
    work_order_summary = work_order_payload.get("summary", {})
    runner_temp_dir = "${RUNNER_TEMP:-/tmp}/product_image_smoke_runner_artifacts"
    rows = [
        _runner_hygiene_command_row(
            target="normalize-artifacts",
            label="Normalize existing product image smoke artifact ownership",
            required_platform="self-hosted Linux runner workspace",
            platform_guard="linux",
            commands=[
                (
                    "bash scripts/normalize_product_image_smoke_artifact_ownership.sh "
                    "--log-path runs/product_image_build_smoke.log"
                ),
                (
                    "bash scripts/normalize_product_image_smoke_artifact_ownership.sh "
                    "--log-path runs/product_image_rocm_runtime_smoke.log"
                ),
            ],
            writes_artifacts=[
                "runs/product_image_smoke_receipt_current.json",
                "runs/product_image_build_smoke.log",
                "runs/product_image_rocm_runtime_smoke.log",
                runner_temp_dir,
            ],
        ),
        _runner_hygiene_command_row(
            target="rocm-runtime-refresh",
            label="Refresh ROCm runtime smoke receipt with runner hygiene schema",
            required_platform="self-hosted Linux ROCm runner",
            platform_guard="linux",
            commands=[
                "mkdir -p \"${RUNNER_TEMP:-/tmp}/product_image_smoke_runner_artifacts\"",
                (
                    "mkdir -p runs && set +e; "
                    "PRODUCT_IMAGE_VERIFY_MODE=rocm-runtime "
                    "PRODUCT_IMAGE_RUNNER_SMOKE_DIR=\"${RUNNER_TEMP:-/tmp}/product_image_smoke_runner_artifacts\" "
                    "PRODUCT_IMAGE_CONTAINER_UID_GID=\"$(id -u):$(id -g)\" "
                    "bash deploy/verify_product_image.sh 2>&1 | tee runs/product_image_rocm_runtime_smoke.log; "
                    "rc=\"${PIPESTATUS[0]}\"; set -e; "
                    "bash scripts/normalize_product_image_smoke_artifact_ownership.sh "
                    "--log-path runs/product_image_rocm_runtime_smoke.log; "
                    "exit \"${rc}\""
                ),
            ],
            writes_artifacts=[
                "runs/product_image_smoke_receipt_current.json",
                "runs/product_image_rocm_runtime_smoke.log",
                runner_temp_dir,
            ],
        ),
        _runner_hygiene_command_row(
            target="preflight-rebuild",
            label="Rebuild product image smoke preflight and hygiene artifacts",
            required_platform="repository checkout after receipt refresh",
            commands=[
                (
                    "python3 tools/build_product_image_smoke_preflight.py "
                    f"--out-json {DEFAULT_OUT_JSON} "
                    f"--out-md {DEFAULT_OUT_MD} "
                    f"--out-runner-hygiene-work-order-json {DEFAULT_OUT_RUNNER_HYGIENE_WORK_ORDER_JSON} "
                    f"--out-runner-hygiene-work-order-csv {DEFAULT_OUT_RUNNER_HYGIENE_WORK_ORDER_CSV} "
                    f"--out-runner-hygiene-work-order-md {DEFAULT_OUT_RUNNER_HYGIENE_WORK_ORDER_MD} "
                    f"--out-runner-hygiene-command-pack-json {DEFAULT_OUT_RUNNER_HYGIENE_COMMAND_PACK_JSON} "
                    f"--out-runner-hygiene-command-pack-sh {DEFAULT_OUT_RUNNER_HYGIENE_COMMAND_PACK_SH} "
                    f"--out-runner-hygiene-command-pack-md {DEFAULT_OUT_RUNNER_HYGIENE_COMMAND_PACK_MD}"
                ),
            ],
            writes_artifacts=[
                DEFAULT_OUT_JSON,
                DEFAULT_OUT_RUNNER_HYGIENE_WORK_ORDER_JSON,
                DEFAULT_OUT_RUNNER_HYGIENE_COMMAND_PACK_JSON,
            ],
        ),
    ]
    summary = {
        "packet_type": "product_image_smoke_runner_hygiene_command_pack",
        "schema_version": RUNNER_HYGIENE_COMMAND_PACK_SCHEMA_VERSION,
        "status": "product_image_smoke_runner_hygiene_command_pack_ready",
        "command_pack_materialized": True,
        "target_count": len(rows),
        "command_count": sum(int(row["command_count"]) for row in rows),
        "targets": [row["target"] for row in rows],
        "runner_hygiene_ready": bool(work_order_summary.get("runner_hygiene_ready") is True),
        "refresh_required": bool(work_order_summary.get("refresh_required") is True),
        "primary_blocker": str(work_order_summary.get("primary_blocker") or ""),
        "receipt_json": str(work_order_summary.get("receipt_json") or DEFAULT_RECEIPT_JSON),
        "preflight_status": str(preflight_summary.get("status") or ""),
        "required_runner_hygiene_schema_version": RUNNER_HYGIENE_SCHEMA_VERSION,
        "shell_script_path": DEFAULT_OUT_RUNNER_HYGIENE_COMMAND_PACK_SH,
        "markdown_path": DEFAULT_OUT_RUNNER_HYGIENE_COMMAND_PACK_MD,
        "execution_enabled": False,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "Run rocm-runtime-refresh on the self-hosted ROCm runner, then run preflight-rebuild."
            if work_order_summary.get("refresh_required") is True
            else "Runner hygiene receipt is ready; command pack is available for future refreshes."
        ),
    }
    return {"summary": summary, "rows": rows}


def _resolve(root: Path, path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else root / path


def _read_text(root: Path, path_like: str | Path) -> str:
    path = _resolve(root, path_like)
    if not path.exists() or not path.is_file():
        return ""
    return path.read_text(encoding="utf-8")


def _read_json(root: Path, path_like: str | Path) -> dict[str, Any]:
    path = _resolve(root, path_like)
    if not path.exists() or not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _display_path(root: Path, path: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def _workspace_smoke_artifact_state(root: Path) -> dict[str, Any]:
    path = root / "runs" / "product_image_smoke_runner_artifacts"
    host_uid = os.getuid()
    host_gid = os.getgid()
    exists = path.exists()
    checked_path_count = 0
    bad_owner_path = ""
    not_writable_path = ""
    permission_error = ""

    def inspect(candidate: Path) -> None:
        nonlocal checked_path_count, bad_owner_path, not_writable_path, permission_error
        try:
            stat_result = candidate.stat()
        except OSError as exc:
            if not permission_error:
                permission_error = f"{_display_path(root, candidate)}: {exc.__class__.__name__}"
            return
        checked_path_count += 1
        if not bad_owner_path and (
            stat_result.st_uid != host_uid or stat_result.st_gid != host_gid
        ):
            bad_owner_path = _display_path(root, candidate)
        if not not_writable_path and not os.access(candidate, os.W_OK):
            not_writable_path = _display_path(root, candidate)

    if exists:
        inspect(path)
        if path.is_dir():
            def record_walk_error(exc: OSError) -> None:
                nonlocal permission_error
                if not permission_error:
                    filename = exc.filename or str(path)
                    permission_error = f"{_display_path(root, Path(filename))}: {exc.__class__.__name__}"

            for dirpath, dirnames, filenames in os.walk(
                path,
                topdown=True,
                onerror=record_walk_error,
            ):
                dir_path = Path(dirpath)
                inspect(dir_path)
                for name in [*dirnames, *filenames]:
                    inspect(dir_path / name)
                if bad_owner_path and not_writable_path:
                    dirnames[:] = []

    owner_ready = bool(not exists or (not bad_owner_path and not permission_error))
    writable_ready = bool(not exists or (not not_writable_path and not permission_error))
    cleanup_ready = bool(owner_ready and writable_ready)
    required_action = (
        "Run bash scripts/normalize_product_image_smoke_artifact_ownership.sh "
        "--log-path runs/product_image_rocm_runtime_smoke.log on the self-hosted runner, "
        "or repair ownership with sudo chown -R \"$(id -u):$(id -g)\" "
        "runs/product_image_smoke_runner_artifacts before treating product CI as verified."
        if not cleanup_ready
        else ""
    )
    return {
        "workspace_smoke_artifact_current_path": _display_path(root, path),
        "workspace_smoke_artifact_current_present": exists,
        "workspace_smoke_artifact_current_checked_path_count": checked_path_count,
        "workspace_smoke_artifact_current_expected_uid_gid": f"{host_uid}:{host_gid}",
        "workspace_smoke_artifact_current_owner_ready": owner_ready,
        "workspace_smoke_artifact_current_writable_ready": writable_ready,
        "workspace_smoke_artifact_current_cleanup_ready": cleanup_ready,
        "workspace_smoke_artifact_current_bad_owner_path": bad_owner_path,
        "workspace_smoke_artifact_current_not_writable_path": not_writable_path,
        "workspace_smoke_artifact_current_permission_error": permission_error,
        "workspace_smoke_artifact_current_required_action": required_action,
        "workspace_smoke_artifact_current_verification_command": (
            "bash scripts/normalize_product_image_smoke_artifact_ownership.sh "
            "--log-path runs/product_image_rocm_runtime_smoke.log"
        ),
    }


def _int_value(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _requirement_lines(text: str) -> set[str]:
    return {
        line.strip()
        for line in text.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }


def _docker_daemon_reachable(docker_cli: str) -> bool:
    if not docker_cli:
        return False
    try:
        result = subprocess.run(
            [docker_cli, "info"],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return result.returncode == 0


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(ROOT, path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_markdown(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(ROOT, path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    s = payload["summary"]
    lines = [
        "# Product Image Smoke Preflight",
        "",
        f"- status: `{s['status']}`",
        f"- docker_cli_present: `{s['docker_cli_present']}`",
        f"- docker_daemon_reachable: `{s['docker_daemon_reachable']}`",
        f"- script_contract_ready: `{s['script_contract_ready']}`",
        f"- workflow_contract_ready: `{s['workflow_contract_ready']}`",
        f"- runner_smoke_dir_contract_ready: `{s['runner_smoke_dir_contract_ready']}`",
        f"- workflow_workspace_artifact_recovery_ready: `{s['workflow_workspace_artifact_recovery_ready']}`",
        f"- workspace_smoke_artifact_current_cleanup_ready: `{s['workspace_smoke_artifact_current_cleanup_ready']}`",
        f"- workspace_smoke_artifact_current_blocker_count: `{s['workspace_smoke_artifact_current_blocker_count']}`",
        f"- workspace_smoke_artifact_current_bad_owner_path: `{s['workspace_smoke_artifact_current_bad_owner_path']}`",
        f"- workspace_smoke_artifact_current_not_writable_path: `{s['workspace_smoke_artifact_current_not_writable_path']}`",
        f"- clean_container_smoke_ready: `{s['clean_container_smoke_ready']}`",
        f"- receipt_present: `{s['receipt_present']}`",
        f"- receipt_mode: `{s['receipt_mode']}`",
        f"- receipt_runner_hygiene_schema_version: `{s['receipt_runner_hygiene_schema_version']}`",
        f"- receipt_runner_smoke_dir_outside_workspace: `{s['receipt_runner_smoke_dir_outside_workspace']}`",
        f"- receipt_container_output_uid_gid_pinned: `{s['receipt_container_output_uid_gid_pinned']}`",
        f"- receipt_container_output_uid_gid_matches_host: `{s['receipt_container_output_uid_gid_matches_host']}`",
        f"- receipt_container_output_uid_gid_non_root: `{s['receipt_container_output_uid_gid_non_root']}`",
        f"- receipt_workspace_runner_smoke_dir_exists_after_cleanup: `{s['receipt_workspace_runner_smoke_dir_exists_after_cleanup']}`",
        f"- receipt_runner_hygiene_ready: `{s['receipt_runner_hygiene_ready']}`",
        f"- receipt_runner_hygiene_blocker_count: `{s['receipt_runner_hygiene_blocker_count']}`",
        f"- receipt_runner_hygiene_refresh_required: `{s['receipt_runner_hygiene_refresh_required']}`",
        f"- receipt_runner_hygiene_required_action: `{s['receipt_runner_hygiene_required_action']}`",
        f"- receipt_runner_hygiene_verification_command: `{s['receipt_runner_hygiene_verification_command']}`",
        f"- container_runtime_receipt_ready: `{s['container_runtime_receipt_ready']}`",
        f"- container_runtime_visible_device_count: `{s['container_runtime_visible_device_count']}`",
        f"- container_runtime_rust_hip_backend_enabled: `{s['container_runtime_rust_hip_backend_enabled']}`",
        f"- runtime_neighbor_release_scaling_ready: `{s['runtime_neighbor_release_scaling_ready']}`",
        f"- runtime_neighbor_release_atom_counts_ready: `{s['runtime_neighbor_release_atom_counts_ready']}`",
        f"- docker_host_setup_command: `{s['docker_host_setup_command']}`",
        f"- docker_cmd_override_example: `{s['docker_cmd_override_example']}`",
        f"- product_runner_smoke_ready: `{s['product_runner_smoke_ready']}`",
        f"- rocm_runtime_runner_smoke_command: `{s['rocm_runtime_runner_smoke_command']}`",
        "",
        "## Blockers",
        "",
    ]
    blockers = payload.get("blockers") or []
    lines.extend(f"- `{row['code']}`" for row in blockers) if blockers else lines.append("- none")
    lines.extend(["", "## Claim Boundary", "", s["claim_boundary"], "", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.write_text("\n".join(lines), encoding="utf-8")


def _csv_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, list):
        return ";".join(str(item) for item in value)
    return "" if value is None else str(value)


def _write_csv(path_like: str | Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path = _resolve(ROOT, path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: _csv_value(row.get(field)) for field in fields})


def _contract_row(check_id: str, passed: bool, observed: str, required: str, source: str) -> dict[str, Any]:
    return {
        "check_id": check_id,
        "passed": passed,
        "observed": observed,
        "required": required,
        "source": source,
        "release_blocker": not passed,
        "execution_enabled": False,
        "external_state_mutated": False,
    }


def build_product_image_smoke_runner_hygiene_work_order(
    preflight_payload: dict[str, Any],
) -> dict[str, Any]:
    summary = preflight_payload.get("summary", {})
    workspace_blockers = [
        str(blocker)
        for blocker in summary.get("workspace_smoke_artifact_current_blockers", [])
        if str(blocker)
    ]
    receipt_blockers = [
        str(blocker)
        for blocker in summary.get("receipt_runner_hygiene_blockers", [])
        if str(blocker)
    ]
    blockers = workspace_blockers + receipt_blockers
    workspace_verification_command = str(
        summary.get("workspace_smoke_artifact_current_verification_command") or ""
    )
    workspace_required_action = str(
        summary.get("workspace_smoke_artifact_current_required_action") or ""
    )
    verification_command = str(summary.get("receipt_runner_hygiene_verification_command") or "")
    required_action = str(summary.get("receipt_runner_hygiene_required_action") or "")
    receipt_json = str(summary.get("receipt_json") or DEFAULT_RECEIPT_JSON)
    rows: list[dict[str, Any]] = []
    for blocker in blockers:
        expected_field, expected_value = RUNNER_HYGIENE_BLOCKER_FIELD_MAP.get(
            blocker,
            ("", ""),
        )
        row_required_action = (
            workspace_required_action if blocker.startswith("workspace_") else required_action
        )
        row_verification_command = (
            workspace_verification_command
            if blocker.startswith("workspace_")
            else verification_command
        )
        rows.append(
            {
                "blocker_id": blocker,
                "status": "operator_action_required",
                "expected_receipt_field": expected_field,
                "expected_value": expected_value,
                "observed_value": summary.get(expected_field) if expected_field else "",
                "required_action": row_required_action,
                "verification_command": row_verification_command,
                "receipt_json": receipt_json,
                "execution_enabled": False,
                "external_state_mutated": False,
            }
        )
    if not rows:
        rows.append(
            {
                "blocker_id": "none",
                "status": "runner_hygiene_receipt_ready",
                "expected_receipt_field": "receipt_runner_hygiene_ready",
                "expected_value": True,
                "observed_value": summary.get("receipt_runner_hygiene_ready") is True,
                "required_action": "",
                "verification_command": verification_command,
                "receipt_json": receipt_json,
                "execution_enabled": False,
                "external_state_mutated": False,
            }
        )

    refresh_required = bool(summary.get("receipt_runner_hygiene_refresh_required") is True)
    workspace_cleanup_required = bool(
        summary.get("workspace_smoke_artifact_current_cleanup_ready") is not True
    )
    work_order_summary = {
        "packet_type": "product_image_smoke_runner_hygiene_work_order",
        "schema_version": RUNNER_HYGIENE_WORK_ORDER_SCHEMA_VERSION,
        "status": "product_image_smoke_runner_hygiene_work_order_ready",
        "work_order_ready": True,
        "runner_hygiene_ready": bool(summary.get("receipt_runner_hygiene_ready") is True),
        "refresh_required": bool(refresh_required or workspace_cleanup_required),
        "receipt_hygiene_refresh_required": refresh_required,
        "workspace_cleanup_required": workspace_cleanup_required,
        "blocker_count": len(blockers),
        "blockers": blockers,
        "workspace_blocker_count": len(workspace_blockers),
        "workspace_blockers": workspace_blockers,
        "receipt_blocker_count": len(receipt_blockers),
        "receipt_blockers": receipt_blockers,
        "primary_blocker": blockers[0] if blockers else "",
        "receipt_json": receipt_json,
        "preflight_status": str(summary.get("status") or ""),
        "preflight_artifact": DEFAULT_OUT_JSON,
        "required_runner_hygiene_schema_version": RUNNER_HYGIENE_SCHEMA_VERSION,
        "receipt_runner_hygiene_schema_version": str(
            summary.get("receipt_runner_hygiene_schema_version") or ""
        ),
        "receipt_runner_smoke_dir": str(summary.get("receipt_runner_smoke_dir") or ""),
        "receipt_runner_smoke_dir_outside_workspace": bool(
            summary.get("receipt_runner_smoke_dir_outside_workspace") is True
        ),
        "receipt_host_uid_gid": str(summary.get("receipt_host_uid_gid") or ""),
        "receipt_container_uid_gid": str(summary.get("receipt_container_uid_gid") or ""),
        "receipt_container_output_uid_gid_pinned": bool(
            summary.get("receipt_container_output_uid_gid_pinned") is True
        ),
        "receipt_container_output_uid_gid_matches_host": bool(
            summary.get("receipt_container_output_uid_gid_matches_host") is True
        ),
        "receipt_container_output_uid_gid_non_root": bool(
            summary.get("receipt_container_output_uid_gid_non_root") is True
        ),
        "receipt_workspace_runner_smoke_dir_cleanup_ready": bool(
            summary.get("receipt_workspace_runner_smoke_dir_cleanup_ready") is True
        ),
        "receipt_workspace_runner_smoke_dir_exists_after_cleanup": bool(
            summary.get("receipt_workspace_runner_smoke_dir_exists_after_cleanup") is True
        ),
        "workspace_smoke_artifact_current_path": str(
            summary.get("workspace_smoke_artifact_current_path") or ""
        ),
        "workspace_smoke_artifact_current_cleanup_ready": bool(
            summary.get("workspace_smoke_artifact_current_cleanup_ready") is True
        ),
        "workspace_smoke_artifact_current_bad_owner_path": str(
            summary.get("workspace_smoke_artifact_current_bad_owner_path") or ""
        ),
        "workspace_smoke_artifact_current_not_writable_path": str(
            summary.get("workspace_smoke_artifact_current_not_writable_path") or ""
        ),
        "workspace_smoke_artifact_current_required_action": str(
            summary.get("workspace_smoke_artifact_current_required_action") or ""
        ),
        "workspace_smoke_artifact_current_verification_command": (
            workspace_verification_command
        ),
        "verification_command": verification_command,
        "required_action": workspace_required_action if workspace_blockers else required_action,
        "execution_enabled": False,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            workspace_required_action
            if workspace_blockers
            else required_action
            if refresh_required
            else "Runner hygiene receipt is ready; no refresh work order action is required."
        ),
    }
    return {"summary": work_order_summary, "rows": rows}


def _write_runner_hygiene_work_order_markdown(
    path_like: str | Path,
    payload: dict[str, Any],
) -> None:
    path = _resolve(ROOT, path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    summary = payload["summary"]
    lines = [
        "# Product Image Smoke Runner Hygiene Work Order",
        "",
        f"- status: `{summary['status']}`",
        f"- runner_hygiene_ready: `{summary['runner_hygiene_ready']}`",
        f"- refresh_required: `{summary['refresh_required']}`",
        f"- blocker_count: `{summary['blocker_count']}`",
        f"- primary_blocker: `{summary['primary_blocker']}`",
        f"- receipt_json: `{summary['receipt_json']}`",
        f"- verification_command: `{summary['verification_command']}`",
        "",
        "| blocker | expected field | expected | observed | action |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in payload.get("rows", []):
        lines.append(
            f"| `{row['blocker_id']}` | `{row['expected_receipt_field']}` | "
            f"`{_csv_value(row['expected_value'])}` | `{_csv_value(row['observed_value'])}` | "
            f"{row['required_action'] or 'No action required.'} |"
        )
    lines.extend(["", CLAIM_BOUNDARY, ""])
    path.write_text("\n".join(lines), encoding="utf-8")


def _render_runner_hygiene_command_pack_sh(payload: dict[str, Any]) -> str:
    targets = " ".join(row["target"] for row in payload.get("rows", []))
    lines = [
        "#!/usr/bin/env bash",
        "set -euo pipefail",
        "",
        "# Product image smoke runner hygiene command pack.",
        "# Runs only the target passed as the first argument.",
        "# Intended for self-hosted Linux/ROCm runners; it writes local receipts/logs only.",
        "",
        "require_platform() {",
        "  local expected=\"$1\"",
        "  local observed",
        "  observed=\"$(python3 -c 'import platform; print(platform.system().lower())')\"",
        "  case \"${expected}:${observed}\" in",
        "    linux:linux) ;;",
        "    *)",
        "      echo \"target ${target} requires ${expected}; observed ${observed}\" >&2",
        "      exit 4",
        "      ;;",
        "  esac",
        "}",
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
        platform_guard = str(row.get("platform_guard") or "").strip()
        if platform_guard:
            lines.append(f"    require_platform {platform_guard}")
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


def _write_runner_hygiene_command_pack_text_outputs(
    *,
    shell_path_like: str | Path,
    markdown_path_like: str | Path,
    payload: dict[str, Any],
) -> None:
    shell_path = _resolve(ROOT, shell_path_like)
    shell_path.parent.mkdir(parents=True, exist_ok=True)
    shell_path.write_text(_render_runner_hygiene_command_pack_sh(payload), encoding="utf-8")
    markdown_path = _resolve(ROOT, markdown_path_like)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    summary = payload["summary"]
    lines = [
        "# Product Image Smoke Runner Hygiene Command Pack",
        "",
        f"- status: `{summary['status']}`",
        f"- runner_hygiene_ready: `{summary['runner_hygiene_ready']}`",
        f"- refresh_required: `{summary['refresh_required']}`",
        f"- target_count: `{summary['target_count']}`",
        f"- primary_blocker: `{summary['primary_blocker']}`",
        "",
        "```bash",
        f"bash {summary['shell_script_path']} <target>",
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
                f"- writes: `{_csv_value(row['writes_artifacts'])}`",
                "",
                "```bash",
            ]
        )
        lines.extend(row["commands"])
        lines.extend(["```", ""])
    lines.extend([CLAIM_BOUNDARY, ""])
    markdown_path.write_text("\n".join(lines), encoding="utf-8")


def _workflow_event_block(workflow: str, event_name: str) -> str:
    header = f"  {event_name}:"
    lines: list[str] = []
    in_block = False
    for line in workflow.splitlines():
        if line == header:
            in_block = True
            lines.append(line)
            continue
        if not in_block:
            continue
        if line.startswith("  ") and not line.startswith("    ") and line.strip():
            break
        lines.append(line)
    return "\n".join(lines)


def _workflow_step_before_checkout(
    workflow: str,
    step_name: str,
    *,
    minimum_count: int,
) -> bool:
    lines = workflow.splitlines()
    step_positions = [
        index for index, line in enumerate(lines) if f"name: {step_name}" in line
    ]
    checkout_positions = [
        index for index, line in enumerate(lines) if "actions/checkout@v5" in line
    ]
    if len(step_positions) < minimum_count or len(checkout_positions) < minimum_count:
        return False
    return all(
        step_positions[index] < checkout_positions[index]
        for index in range(minimum_count)
    )


def _workflow_checkout_clean_false_ready(workflow: str, *, minimum_count: int) -> bool:
    lines = workflow.splitlines()
    checkout_positions = [
        index for index, line in enumerate(lines) if "actions/checkout@v5" in line
    ]
    if len(checkout_positions) < minimum_count:
        return False
    for checkout_index in checkout_positions[:minimum_count]:
        checkout_window = "\n".join(lines[checkout_index : checkout_index + 6])
        if "clean: false" not in checkout_window:
            return False
    return True


def _workflow_workspace_recovery_shell_syntax_ready(
    workflow: str,
    *,
    minimum_count: int,
) -> bool:
    recovery_function_to_runs_dir_check = "\n".join(
        [
            '          repair_path() {',
            '            local path="$1"',
            '            if [[ -e "${path}" ]]; then',
            '              chown -R "$(id -u):$(id -g)" "${path}" 2>/dev/null || sudo -n chown -R "$(id -u):$(id -g)" "${path}" 2>/dev/null || true',
            '              chmod -R u+rwX "${path}" 2>/dev/null || sudo -n chmod -R u+rwX "${path}" 2>/dev/null || true',
            '            fi',
            '          }',
            '          if [[ -e "${runs_dir}" ]]; then',
        ]
    )
    return workflow.count(recovery_function_to_runs_dir_check) >= minimum_count


def build_product_image_smoke_preflight(
    *,
    root: str | Path = ROOT,
    docker_cli_path: str | None = None,
    docker_daemon_ready: bool | None = None,
    receipt_json: str | Path = DEFAULT_RECEIPT_JSON,
) -> dict[str, Any]:
    root_path = Path(root)
    workspace_artifact_state = _workspace_smoke_artifact_state(root_path)
    workspace_artifact_cleanup_ready = bool(
        workspace_artifact_state.get("workspace_smoke_artifact_current_cleanup_ready")
        is True
    )
    workspace_artifact_blockers: list[str] = []
    if not workspace_artifact_cleanup_ready:
        workspace_artifact_blockers.append(
            "workspace_smoke_artifact_current_cleanup_not_ready"
        )
        if workspace_artifact_state.get("workspace_smoke_artifact_current_bad_owner_path"):
            workspace_artifact_blockers.append(
                "workspace_smoke_artifact_current_owner_not_normalized"
            )
        if workspace_artifact_state.get("workspace_smoke_artifact_current_not_writable_path"):
            workspace_artifact_blockers.append(
                "workspace_smoke_artifact_current_not_writable"
            )
        if workspace_artifact_state.get("workspace_smoke_artifact_current_permission_error"):
            workspace_artifact_blockers.append(
                "workspace_smoke_artifact_current_permission_error"
            )
    docker_cli = docker_cli_path if docker_cli_path is not None else shutil.which("docker")
    docker_cli_present = bool(docker_cli)
    if docker_daemon_ready is None:
        docker_daemon_ready = (
            docker_cli_present
            if docker_cli_path is not None
            else _docker_daemon_reachable(str(docker_cli or ""))
        )
    verify_script = _read_text(root_path, "deploy/verify_product_image.sh")
    host_setup_script = _read_text(root_path, "scripts/prepare_product_docker_host.sh")
    workflow = _read_text(root_path, ".github/workflows/product-image-smoke.yml")
    api_worker_workflow = _read_text(root_path, ".github/workflows/product-api-worker.yml")
    ownership_script = _read_text(root_path, "scripts/normalize_product_image_smoke_artifact_ownership.sh")
    dockerfile = _read_text(root_path, "Dockerfile.product")
    base_requirements = _read_text(root_path, "requirements-base.txt")
    default_requirements = _read_text(root_path, "requirements.txt")
    rocm_requirements = _read_text(root_path, "requirements-rocm.txt")
    product_rocm_requirements = _read_text(root_path, "requirements-product-rocm.txt")
    receipt = _read_json(root_path, receipt_json)
    base_requirement_lines = _requirement_lines(base_requirements)
    default_requirement_lines = _requirement_lines(default_requirements)
    rocm_requirement_lines = _requirement_lines(rocm_requirements)
    product_rocm_requirement_lines = _requirement_lines(product_rocm_requirements)
    product_rocm_preserves_base_torch = bool(
        "-r requirements-base.txt" in product_rocm_requirement_lines
        and "-r requirements-rocm.txt" not in product_rocm_requirement_lines
        and "-r requirements.txt" not in product_rocm_requirement_lines
        and "torch==2.6.0" not in product_rocm_requirement_lines
        and "-r requirements-base.txt" in rocm_requirement_lines
        and "-r requirements.txt" not in rocm_requirement_lines
        and "torch==2.6.0+rocm6.1" in rocm_requirement_lines
        and "torch==2.6.0" not in rocm_requirement_lines
        and "-r requirements-base.txt" in default_requirement_lines
        and "torch==2.6.0" in default_requirement_lines
        and base_requirement_lines
        and "torch==2.6.0" not in base_requirement_lines
        and "requirements-base.txt" in dockerfile
    )
    product_image_smoke_pr_trigger_block = _workflow_event_block(workflow, "pull_request")
    missing_product_image_smoke_pr_trigger_paths = [
        path
        for path in PRODUCT_IMAGE_SMOKE_PR_TRIGGER_REQUIRED_PATHS
        if f"- {path}" not in product_image_smoke_pr_trigger_block
    ]
    product_workflow_pre_checkout_recovery_ready = _workflow_step_before_checkout(
        workflow,
        "Recover stale product image smoke workspace artifacts",
        minimum_count=2,
    )
    product_workflow_checkout_clean_false_ready = _workflow_checkout_clean_false_ready(
        workflow,
        minimum_count=2,
    )
    product_workflow_recovery_shell_syntax_ready = (
        _workflow_workspace_recovery_shell_syntax_ready(
            workflow,
            minimum_count=2,
        )
    )
    api_worker_pre_checkout_recovery_ready = _workflow_step_before_checkout(
        api_worker_workflow,
        "Recover stale product image smoke workspace artifacts",
        minimum_count=1,
    )
    api_worker_checkout_clean_false_ready = _workflow_checkout_clean_false_ready(
        api_worker_workflow,
        minimum_count=1,
    )
    api_worker_recovery_shell_syntax_ready = (
        _workflow_workspace_recovery_shell_syntax_ready(
            api_worker_workflow,
            minimum_count=1,
        )
    )

    rows = [
        _contract_row(
            "docker_missing_fail_closed",
            "docker_cli_missing" in verify_script
            and "docker_daemon_unreachable" in verify_script
            and "exit 2" in verify_script
            and "not mark missing Docker as green" in verify_script,
            "docker_cli_missing guarded" if "docker_cli_missing" in verify_script else "missing",
            "missing Docker or inaccessible daemon exits nonzero and is not treated as green",
            "deploy/verify_product_image.sh",
        ),
        _contract_row(
            "docker_cmd_override_declared",
            "DOCKER_CMD" in verify_script
            and "DOCKER_BIN" in verify_script
            and "docker_cmd" in verify_script,
            "DOCKER_CMD override present" if "DOCKER_CMD" in verify_script else "missing",
            "operator can run the smoke with a Docker-compatible command such as sudo docker",
            "deploy/verify_product_image.sh",
        ),
        _contract_row(
            "fail_closed_receipt_written_on_early_exit",
            "write_blocked_receipt" in verify_script
            and "on_exit_write_blocked_receipt" in verify_script
            and "cleanup_and_on_exit_write_blocked_receipt" in verify_script
            and "trap cleanup_and_on_exit_write_blocked_receipt EXIT" in verify_script
            and "receipt_failure_stage" in verify_script
            and "docker_cli_missing" in verify_script
            and "docker_daemon_unreachable" in verify_script
            and "host_python_missing" in verify_script
            and "docker_buildx_missing" in verify_script
            and "rocm_device_nodes_missing" in verify_script
            and "repair_receipt_path" in verify_script
            and "clear_stale_receipt" in verify_script
            and "receipt_path_cleanup_failed" in verify_script
            and 'repair_path_ownership "${RECEIPT_JSON}"' in verify_script
            and "chmod -R u+rwX" in verify_script,
            "blocked receipt helper present" if "write_blocked_receipt" in verify_script else "missing",
            "verify script repairs stale receipt ownership, clears stale receipts, and writes fail-closed receipts for early validation failures and unexpected ERR exits",
            "deploy/verify_product_image.sh",
        ),
        _contract_row(
            "exit_trap_runner_artifact_ownership_normalization_declared",
            "normalize_runner_artifacts_on_exit" in verify_script
            and "cleanup_and_on_exit_write_blocked_receipt" in verify_script
            and "trap cleanup_and_on_exit_write_blocked_receipt EXIT" in verify_script
            and 'repair_path_ownership "${WORKSPACE_RUNNER_SMOKE_DIR}"' in verify_script
            and 'repair_path_ownership "${RUNNER_SMOKE_DIR}"' in verify_script
            and 'repair_path_ownership "$(dirname "${RECEIPT_JSON}")"' in verify_script
            and 'repair_path_ownership "${RECEIPT_JSON}"' in verify_script,
            "exit trap normalizes smoke artifact ownership"
            if "normalize_runner_artifacts_on_exit" in verify_script
            else "missing",
            "verify script normalizes receipt, runner-temp smoke artifacts, and stale workspace smoke artifacts during the EXIT trap even after failed Docker/container steps",
            "deploy/verify_product_image.sh",
        ),
        _contract_row(
            "runner_smoke_dir_ownership_guard_declared",
            "DEFAULT_RUNNER_SMOKE_DIR" in verify_script
            and "${RUNNER_TEMP:-/tmp}/product_image_smoke_runner_artifacts" in verify_script
            and "PRODUCT_IMAGE_RUNNER_SMOKE_DIR" in verify_script
            and "PRODUCT_IMAGE_CONTAINER_UID_GID" in verify_script
            and "HOST_UID_GID" in verify_script
            and "CONTAINER_UID_GID" in verify_script
            and "CONTAINER_OUTPUT_UID_GID_PINNED" in verify_script
            and "CONTAINER_OUTPUT_UID_GID_MATCHES_HOST" in verify_script
            and "CONTAINER_OUTPUT_UID_GID_NON_ROOT" in verify_script
            and "container_uid_gid_invalid" in verify_script
            and "container_uid_gid_not_host" in verify_script
            and "container_uid_gid_root" in verify_script
            and "DOCKER_SMOKE_RUN_ARGS" in verify_script
            and "--user" in verify_script
            and "reset_runner_smoke_dir" in verify_script
            and "runner_smoke_dir_cleanup_failed" in verify_script,
            "runner temp dir and host UID/GID guard present"
            if "DOCKER_SMOKE_RUN_ARGS" in verify_script
            else "missing",
            "rocm-runtime smoke writes bind-mounted artifacts outside the GitHub workspace by default and uses the non-root host UID/GID for container outputs",
            "deploy/verify_product_image.sh",
        ),
        _contract_row(
            "runner_smoke_dir_workspace_fail_closed_declared",
            "WORKSPACE_RUNNER_SMOKE_DIR" in verify_script
            and "PRODUCT_IMAGE_WORKSPACE_RUNNER_SMOKE_DIR" in verify_script
            and "RUNNER_SMOKE_DIR_OUTSIDE_WORKSPACE" in verify_script
            and "recover_workspace_smoke_dir" in verify_script
            and "workspace_smoke_dir_cleanup_failed" in verify_script
            and "runner_smoke_dir_inside_workspace" in verify_script
            and "runner_smoke_dir_outside_workspace" in verify_script
            and "workspace_runner_smoke_dir_cleanup_ready" in verify_script
            and "PRODUCT_IMAGE_OWNERSHIP_REPAIR_IMAGE" in verify_script
            and "busybox:1.36.1" in verify_script
            and "needs_ownership_repair" in verify_script
            and "docker_repair_ownership" in verify_script
            and "run --rm" in verify_script
            and "/repair-root" in verify_script,
            "workspace artifact root fail-closed guard present"
            if "runner_smoke_dir_inside_workspace" in verify_script
            else "missing",
            "product image smoke artifacts are blocked from the checkout workspace and stale workspace artifacts are cleaned or Docker-repaired before Docker runs",
            "deploy/verify_product_image.sh",
        ),
        _contract_row(
            "post_smoke_ownership_script_declared",
            "normalize_product_image_smoke_artifact_ownership.sh" in ownership_script
            and "GITHUB_WORKSPACE" in ownership_script
            and "RUNNER_TEMP" in ownership_script
            and "product_image_smoke_receipt_current.json" in ownership_script
            and "WORKSPACE_SMOKE_DIR" in ownership_script
            and "product_image_smoke_runner_artifacts" in ownership_script
            and "verify_ownership" in ownership_script
            and "product_image_smoke_artifact_ownership_not_normalized" in ownership_script
            and "product_image_smoke_artifact_not_writable" in ownership_script
            and "chown \"${HOST_UID_GID}\" \"${RUNS_DIR}\"" in ownership_script
            and "chown -R \"${HOST_UID_GID}\" \"${path}\"" in ownership_script
            and "chmod u+rwx \"${RUNS_DIR}\"" in ownership_script
            and "chmod -R u+rwX \"${path}\"" in ownership_script
            and "PRODUCT_IMAGE_OWNERSHIP_REPAIR_DOCKER_CMD" in ownership_script
            and "PRODUCT_IMAGE_OWNERSHIP_REPAIR_IMAGE" in ownership_script
            and "busybox:1.36.1" in ownership_script
            and "needs_ownership_repair" in ownership_script
            and "docker_repair_ownership" in ownership_script
            and "run --rm" in ownership_script
            and "/repair-root" in ownership_script,
            "post-smoke ownership script present"
            if "normalize_product_image_smoke_artifact_ownership.sh" in ownership_script
            else "missing",
            "post-checkout ownership normalization script repairs runs, receipt, log, and runner-temp smoke artifact ownership and write bits, including Docker bind-mount fallback repair",
            "scripts/normalize_product_image_smoke_artifact_ownership.sh",
        ),
        _contract_row(
            "docker_buildkit_and_runner_cleanup_declared",
            "DOCKER_BUILDKIT" in verify_script
            and "PRODUCT_IMAGE_REQUIRE_BUILDX" in verify_script
            and "docker_buildx_missing" in verify_script
            and "PRODUCT_IMAGE_PRUNE_BEFORE_BUILD" in verify_script
            and "container prune -f" in verify_script
            and "image prune -f" in verify_script
            and "build --progress=plain" in verify_script,
            "BuildKit and opt-in Docker cleanup present"
            if "PRODUCT_IMAGE_PRUNE_BEFORE_BUILD" in verify_script
            else "missing",
            "self-hosted Docker smoke uses BuildKit and can prune stale containers/dangling images before build",
            "deploy/verify_product_image.sh",
        ),
        _contract_row(
            "smoke_containers_disable_auth_preflight",
            "DOCKER_RUN_ARGS=(--rm -e PRODUCT_API_AUTH_REQUIRED=0)" in verify_script
            and "PRODUCT_API_AUTH_REQUIRED=0" in verify_script,
            "smoke run args disable auth"
            if "DOCKER_RUN_ARGS=(--rm -e PRODUCT_API_AUTH_REQUIRED=0)" in verify_script
            else "missing",
            "ephemeral smoke containers pass PRODUCT_API_AUTH_REQUIRED=0 so importing api.main "
            "is not blocked by the hardened startup auth preflight (Dockerfile default stays 1)",
            "deploy/verify_product_image.sh",
        ),
        _contract_row(
            "docker_host_setup_script_declared",
            "docker.io" in host_setup_script
            and "systemctl enable --now docker" in host_setup_script
            and "PRODUCT_IMAGE_VERIFY_MODE=rocm-runtime" in host_setup_script
            and "/dev/kfd" in host_setup_script
            and "/dev/dri" in host_setup_script,
            "Docker host setup helper present" if "docker.io" in host_setup_script else "missing",
            "host helper installs/starts Docker, checks ROCm device nodes, and prints rocm-runtime smoke command",
            "scripts/prepare_product_docker_host.sh",
        ),
        _contract_row(
            "verify_modes_declared",
            "build|rocm-runtime" in verify_script and "PRODUCT_IMAGE_VERIFY_MODE" in verify_script,
            "build|rocm-runtime" if "build|rocm-runtime" in verify_script else "missing",
            "build and rocm-runtime modes",
            "deploy/verify_product_image.sh",
        ),
        _contract_row(
            "rocm_device_nodes_required",
            "/dev/kfd" in verify_script and "/dev/dri" in verify_script and "--device=/dev/kfd" in verify_script,
            "device args present" if "--device=/dev/kfd" in verify_script else "missing",
            "rocm-runtime mode passes /dev/kfd and /dev/dri",
            "deploy/verify_product_image.sh",
        ),
        _contract_row(
            "rocm_torch_visibility_required",
            "torch.cuda.is_available()" in verify_script and "torch.cuda.device_count() > 0" in verify_script,
            "torch visibility assert present" if "torch.cuda.device_count() > 0" in verify_script else "missing",
            "container asserts torch ROCm visible device count > 0",
            "deploy/verify_product_image.sh",
        ),
        _contract_row(
            "container_runtime_proof_required",
            "rocm_container_runtime_proof.json" in verify_script
            and "rocm_container_runtime_proof_v1" in verify_script
            and "probe_rust_hip_backend" in verify_script
            and "rust_hip_backend_enabled" in verify_script,
            "container runtime proof writer present"
            if "rocm_container_runtime_proof.json" in verify_script
            else "missing",
            "rocm-runtime mode writes in-container ROCm/HIP/Rust proof JSON",
            "deploy/verify_product_image.sh",
        ),
        _contract_row(
            "real_validated_runner_smoke_required",
            "run_tier_alpha_adrb2_dispatch_smoke.py" in verify_script
            and "API_VALIDATED_RUNNER_ENABLED=1" in verify_script
            and "tier_alpha_adrb2_dispatch_smoke.json" in verify_script,
            "tier alpha runner smoke present" if "run_tier_alpha_adrb2_dispatch_smoke.py" in verify_script else "missing",
            "rocm-runtime mode runs real validated runner dispatch smoke",
            "deploy/verify_product_image.sh",
        ),
        _contract_row(
            "backmapping_claim_metadata_smoke_required",
            "tools/run_ligand_backmapping_scoring.py" in verify_script
            and "backmapping_summary.json" in verify_script
            and "hbond_evidence_v1" in verify_script
            and "ligand_topology_validity_v1" in verify_script
            and "product_runner_claim_metadata_ready" in verify_script,
            "backmapping claim metadata smoke present"
            if "product_runner_claim_metadata_ready" in verify_script
            else "missing",
            "rocm-runtime mode runs backmapping scoring smoke and records H-bond/ONSPS/ligand topology schema claim metadata",
            "deploy/verify_product_image.sh",
        ),
        _contract_row(
            "rocm_runtime_receipt_written",
            "PRODUCT_IMAGE_SMOKE_RECEIPT_JSON" in verify_script
            and "product_runner_smoke_ready" in verify_script
            and "clean_container_smoke_ready" in verify_script,
            "receipt writer present" if "PRODUCT_IMAGE_SMOKE_RECEIPT_JSON" in verify_script else "missing",
            "successful smoke writes a receipt that distinguishes build from rocm-runtime",
            "deploy/verify_product_image.sh",
        ),
        _contract_row(
            "build_mode_receipt_not_product_claim_ready",
            "product_image_build_smoke_ready" in verify_script
            and "blocked_product_image_rocm_runtime_smoke" in verify_script
            and "receipt_ready" in verify_script,
            "mode-specific receipt status present"
            if "product_image_build_smoke_ready" in verify_script
            else "missing",
            "build-only receipt must not use product_image_smoke_ready claim status",
            "deploy/verify_product_image.sh",
        ),
        _contract_row(
            "workflow_build_mode_declared",
            "PRODUCT_IMAGE_VERIFY_MODE: build" in workflow
            and "docker/setup-buildx-action@v3" in workflow
            and 'DOCKER_BUILDKIT: "1"' in workflow
            and 'PRODUCT_IMAGE_REQUIRE_BUILDX: "1"' in workflow
            and 'PRODUCT_IMAGE_PRUNE_BEFORE_BUILD: "1"' in workflow,
            "build mode in workflow" if "PRODUCT_IMAGE_VERIFY_MODE: build" in workflow else "missing",
            "self-hosted CI uses build contract mode explicitly with BuildKit and stale Docker cleanup",
            ".github/workflows/product-image-smoke.yml",
        ),
        _contract_row(
            "workflow_pre_checkout_workspace_artifact_recovery_declared",
            "Recover stale product image smoke workspace artifacts" in workflow
            and "runs_dir=" in workflow
            and "product_image_smoke_runner_artifacts" in workflow
            and workflow.count("receipt_path=") >= 2
            and workflow.count("build_log_path=") >= 2
            and workflow.count("rocm_log_path=") >= 2
            and workflow.count("repair_path()") >= 2
            and workflow.count('chown "$(id -u):$(id -g)" "${runs_dir}"') >= 2
            and workflow.count('chmod u+rwx "${runs_dir}"') >= 2
            and "sudo -n chown -R" in workflow
            and "sudo -n chmod -R u+rwX" in workflow
            and workflow.count('repair_path "${receipt_path}"') >= 2
            and workflow.count('repair_path "${build_log_path}"') >= 2
            and workflow.count('repair_path "${rocm_log_path}"') >= 2
            and workflow.count('if ! rm -rf "${smoke_dir}"; then') >= 2
            and workflow.count("product_image_smoke_workspace_cleanup_failed") >= 2
            and workflow.count("continuing so verify_product_image.sh can emit a fail-closed receipt") >= 2
            and product_workflow_pre_checkout_recovery_ready
            and product_workflow_checkout_clean_false_ready
            and product_workflow_recovery_shell_syntax_ready,
            "pre-checkout product smoke artifact recovery present"
            if (
                product_workflow_pre_checkout_recovery_ready
                and product_workflow_recovery_shell_syntax_ready
            )
            else "missing",
            "self-hosted jobs attempt stale runs directory and smoke artifact recovery before checkout, disable checkout's broad workspace clean, and continue to the verify script so cleanup failures still emit fail-closed receipts",
            ".github/workflows/product-image-smoke.yml",
        ),
        _contract_row(
            "workflow_runner_temp_artifact_root_declared",
            workflow.count("PRODUCT_IMAGE_RUNNER_SMOKE_DIR: ${{ runner.temp }}/product_image_smoke_runner_artifacts") >= 2
            and "runs/product_image_smoke_runner_artifacts/**" not in workflow
            and workflow.count("${{ runner.temp }}/product_image_smoke_runner_artifacts/**") >= 2,
            "runner.temp smoke artifact root declared"
            if "PRODUCT_IMAGE_RUNNER_SMOKE_DIR: ${{ runner.temp }}/product_image_smoke_runner_artifacts" in workflow
            else "missing",
            "build and ROCm workflow jobs set the smoke artifact root outside the checkout workspace; uploads collect runner-temp artifacts only",
            ".github/workflows/product-image-smoke.yml",
        ),
        _contract_row(
            "workflow_container_uid_gid_export_declared",
            workflow.count('export PRODUCT_IMAGE_CONTAINER_UID_GID="$(id -u):$(id -g)"') >= 2
            and "PRODUCT_IMAGE_CONTAINER_UID_GID" in workflow,
            "container UID:GID export declared"
            if 'export PRODUCT_IMAGE_CONTAINER_UID_GID="$(id -u):$(id -g)"' in workflow
            else "missing",
            "build and ROCm workflow jobs explicitly pin container bind-mount outputs to the current runner UID:GID",
            ".github/workflows/product-image-smoke.yml",
        ),
        _contract_row(
            "workflow_post_smoke_ownership_normalization_declared",
            workflow.count("Normalize product image smoke artifact ownership") >= 2
            and workflow.count("bash scripts/normalize_product_image_smoke_artifact_ownership.sh") >= 2
            and "runs/product_image_build_smoke.log" in workflow
            and "runs/product_image_rocm_runtime_smoke.log" in workflow
            and "product_image_build_smoke.log" in workflow
            and "product_image_rocm_runtime_smoke.log" in workflow
            and "product_image_smoke_receipt_current.json" in workflow,
            "post-smoke artifact ownership normalization present"
            if "Normalize product image smoke artifact ownership" in workflow
            else "missing",
            "self-hosted jobs normalize receipt, log, and runner-temp smoke artifact ownership before upload and before the next checkout",
            ".github/workflows/product-image-smoke.yml",
        ),
        _contract_row(
            "api_worker_pre_checkout_workspace_artifact_recovery_declared",
            "runs-on: ${{ fromJSON(inputs.runner_labels_json || '[\"self-hosted\",\"linux\"]') }}" in api_worker_workflow
            and "Recover stale product image smoke workspace artifacts" in api_worker_workflow
            and "runs_dir=" in api_worker_workflow
            and "product_image_smoke_runner_artifacts" in api_worker_workflow
            and "receipt_path=" in api_worker_workflow
            and "build_log_path=" in api_worker_workflow
            and "rocm_log_path=" in api_worker_workflow
            and "repair_path()" in api_worker_workflow
            and 'chown "$(id -u):$(id -g)" "${runs_dir}"' in api_worker_workflow
            and 'chmod u+rwx "${runs_dir}"' in api_worker_workflow
            and "sudo -n chown -R" in api_worker_workflow
            and "sudo -n chmod -R u+rwX" in api_worker_workflow
            and 'repair_path "${receipt_path}"' in api_worker_workflow
            and 'repair_path "${build_log_path}"' in api_worker_workflow
            and 'repair_path "${rocm_log_path}"' in api_worker_workflow
            and 'if ! rm -rf "${smoke_dir}"; then' in api_worker_workflow
            and "product_image_smoke_workspace_cleanup_failed" in api_worker_workflow
            and "continuing because product-image-smoke owns the fail-closed hygiene receipt" in api_worker_workflow
            and api_worker_pre_checkout_recovery_ready
            and api_worker_checkout_clean_false_ready
            and api_worker_recovery_shell_syntax_ready,
            "api worker pre-checkout product smoke artifact recovery present"
            if (
                api_worker_pre_checkout_recovery_ready
                and api_worker_recovery_shell_syntax_ready
            )
            else "missing",
            "self-hosted API worker workflow attempts stale product-image smoke workspace artifact recovery before checkout, disables checkout's broad workspace clean, and leaves fail-closed hygiene ownership to product-image-smoke",
            ".github/workflows/product-api-worker.yml",
        ),
        _contract_row(
            "workflow_pull_request_trigger_declared",
            bool(product_image_smoke_pr_trigger_block)
            and not missing_product_image_smoke_pr_trigger_paths,
            "pull_request path trigger present"
            if product_image_smoke_pr_trigger_block and not missing_product_image_smoke_pr_trigger_paths
            else "missing: " + ", ".join(missing_product_image_smoke_pr_trigger_paths or ["pull_request"]),
            "product image smoke runs on PRs for relevant product runtime, ownership-normalization, and preflight contract path changes",
            ".github/workflows/product-image-smoke.yml",
        ),
        _contract_row(
            "workflow_manual_verify_mode_choice_declared",
            "workflow_dispatch:" in workflow
            and "verify_mode:" in workflow
            and "build_runner_labels_json:" in workflow
            and "- build" in workflow
            and "- rocm-runtime" in workflow,
            "workflow_dispatch verify_mode choice present" if "verify_mode:" in workflow else "missing",
            "manual workflow dispatch exposes build vs rocm-runtime mode and explicit build runner labels",
            ".github/workflows/product-image-smoke.yml",
        ),
        _contract_row(
            "workflow_build_smoke_self_hosted_by_default",
            "product-image-build-smoke" in workflow
            and "inputs.build_runner_labels_json" in workflow
            and "'[\"self-hosted\",\"linux\"]'" in workflow
            and "Default self-hosted avoids GitHub-hosted minutes" in workflow,
            "self-hosted build runner default present"
            if "product-image-build-smoke" in workflow
            else "missing",
            "build smoke must default to self-hosted Linux to avoid private-repo GitHub-hosted minutes",
            ".github/workflows/product-image-smoke.yml",
        ),
        _contract_row(
            "workflow_rocm_runtime_self_hosted_runner_declared",
            "product-image-rocm-runtime-smoke" in workflow
            and "runs-on: [self-hosted, linux, rocm]" in workflow
            and "PRODUCT_IMAGE_VERIFY_MODE: rocm-runtime" in workflow,
            "self-hosted rocm runtime job present"
            if "product-image-rocm-runtime-smoke" in workflow
            else "missing",
            "rocm-runtime workflow path must run only on a self-hosted ROCm runner",
            ".github/workflows/product-image-smoke.yml",
        ),
        _contract_row(
            "workflow_hosted_build_summary_not_product_claim",
            "product runtime claim: `false`" in workflow
            and "required runtime claim mode: `rocm-runtime on self-hosted ROCm runner`" in workflow,
            "build summary claim boundary present"
            if "product runtime claim: `false`" in workflow
            else "missing",
            "build smoke summary must state build scope is not product runtime readiness",
            ".github/workflows/product-image-smoke.yml",
        ),
        _contract_row(
            "workflow_artifact_retention_declared",
            workflow.count("retention-days: 14") >= 2
            and "product_image_build_smoke.log" in workflow
            and "product_image_rocm_runtime_smoke.log" in workflow
            and "runs/product_image_smoke_receipt_current.json" in workflow
            and "runner.temp" in workflow
            and workflow.count("${{ runner.temp }}/product_image_smoke_runner_artifacts/**") >= 2,
            f"retention-days occurrences={workflow.count('retention-days: 14')}",
            "build and ROCm runtime artifact uploads retain logs, receipt artifacts, and runner-temp smoke artifacts for at least 14 days",
            ".github/workflows/product-image-smoke.yml",
        ),
        _contract_row(
            "dockerfile_rocm_hip_rust_contract",
            "rocm/pytorch" in dockerfile
            and "torch.version.hip" in dockerfile
            and "tools/build_rust_hip_engine.py --output /app" in dockerfile
            and "requirements-base.txt" in dockerfile
            and "chmod -R a+rwX logs runs" in dockerfile,
            "ROCm/HIP/Rust product Dockerfile" if "rocm/pytorch" in dockerfile else "missing",
            "Dockerfile.product builds ROCm PyTorch and Rust HIP extension, copies split requirement files, and leaves runtime log/run paths writable for non-root smoke UIDs",
            "Dockerfile.product",
        ),
        _contract_row(
            "product_rocm_requirements_no_cpu_torch_pin",
            product_rocm_preserves_base_torch,
            (
                "product_rocm_includes_base="
                f"{'-r requirements-base.txt' in product_rocm_requirement_lines};"
                "product_rocm_includes_rocm="
                f"{'-r requirements-rocm.txt' in product_rocm_requirement_lines};"
                "product_rocm_includes_default="
                f"{'-r requirements.txt' in product_rocm_requirement_lines};"
                "product_rocm_cpu_torch_pin="
                f"{'torch==2.6.0' in product_rocm_requirement_lines};"
                "rocm_includes_base="
                f"{'-r requirements-base.txt' in rocm_requirement_lines};"
                "rocm_includes_default="
                f"{'-r requirements.txt' in rocm_requirement_lines};"
                "rocm_cpu_torch_pin="
                f"{'torch==2.6.0' in rocm_requirement_lines};"
                "rocm_torch_pin="
                f"{'torch==2.6.0+rocm6.1' in rocm_requirement_lines}"
            ),
            "product ROCm requirements must install base dependencies only and preserve Dockerfile.product's ROCm PyTorch base build",
            "requirements-product-rocm.txt",
        ),
    ]
    script_contract_ready = all(row["passed"] for row in rows if row["source"] not in WORKFLOW_SOURCES)
    workflow_contract_ready = all(row["passed"] for row in rows if row["source"] in WORKFLOW_SOURCES)
    runner_smoke_dir_contract_ready = all(
        row["passed"]
        for row in rows
        if row["check_id"]
        in {
            "runner_smoke_dir_ownership_guard_declared",
            "runner_smoke_dir_workspace_fail_closed_declared",
            "exit_trap_runner_artifact_ownership_normalization_declared",
            "workflow_pre_checkout_workspace_artifact_recovery_declared",
            "api_worker_pre_checkout_workspace_artifact_recovery_declared",
            "workflow_runner_temp_artifact_root_declared",
            "workflow_container_uid_gid_export_declared",
            "workflow_post_smoke_ownership_normalization_declared",
        }
    )
    workflow_workspace_artifact_recovery_ready = all(
        row["passed"]
        for row in rows
        if row["check_id"]
        in {
            "workflow_pre_checkout_workspace_artifact_recovery_declared",
            "api_worker_pre_checkout_workspace_artifact_recovery_declared",
            "workflow_runner_temp_artifact_root_declared",
            "workflow_container_uid_gid_export_declared",
            "workflow_post_smoke_ownership_normalization_declared",
        }
    )
    pre_checkout_cleanup_ready = all(
        row["passed"]
        for row in rows
        if row["check_id"]
        in {
            "workflow_pre_checkout_workspace_artifact_recovery_declared",
            "api_worker_pre_checkout_workspace_artifact_recovery_declared",
        }
    )
    receipt_present = bool(receipt)
    receipt_status = str(receipt.get("status") or "")
    receipt_mode = str(receipt.get("mode") or "")
    receipt_simulate_missing_profile_http = _int_value(receipt.get("simulate_missing_profile_http"))
    container_runtime_proof_ready = bool(receipt.get("container_runtime_proof_ready") is True)
    container_runtime_proof_schema_version = str(
        receipt.get("container_runtime_proof_schema_version") or ""
    )
    container_runtime_in_container = bool(receipt.get("container_runtime_in_container") is True)
    container_runtime_device_nodes_ready = bool(receipt.get("container_runtime_device_nodes_ready") is True)
    container_runtime_torch_rocm_ready = bool(receipt.get("container_runtime_torch_rocm_ready") is True)
    container_runtime_torch_cuda_available = bool(
        receipt.get("container_runtime_torch_cuda_available") is True
    )
    container_runtime_visible_device_count = _int_value(
        receipt.get("container_runtime_visible_device_count")
    )
    container_runtime_rust_hip_backend_enabled = bool(
        receipt.get("container_runtime_rust_hip_backend_enabled") is True
    )
    container_runtime_receipt_ready = bool(
        container_runtime_proof_ready
        and container_runtime_proof_schema_version == "rocm_container_runtime_proof_v1"
        and container_runtime_in_container
        and container_runtime_device_nodes_ready
        and container_runtime_torch_rocm_ready
        and container_runtime_torch_cuda_available
        and container_runtime_visible_device_count > 0
        and container_runtime_rust_hip_backend_enabled
    )
    product_runner_smoke_ready = bool(receipt.get("product_runner_smoke_ready") is True)
    product_runner_claim_metadata_ready = bool(receipt.get("product_runner_claim_metadata_ready") is True)
    tier_alpha_manifest_signature_verified = bool(receipt.get("tier_alpha_result_manifest_signature_verified") is True)
    tier_alpha_manifest_status = str(receipt.get("tier_alpha_result_manifest_status") or "")
    backmapping_runner_claim_metadata_ready = bool(receipt.get("backmapping_runner_claim_metadata_ready") is True)
    backmapping_hbond_evidence_schema_version = str(
        receipt.get("backmapping_hbond_evidence_schema_version") or ""
    )
    backmapping_hbond_claim_metadata_schema_version = str(
        receipt.get("backmapping_hbond_claim_metadata_schema_version") or ""
    )
    backmapping_hbond_claim_metadata_schema_ready_row_count = _int_value(
        receipt.get("backmapping_hbond_claim_metadata_schema_ready_row_count")
    )
    backmapping_onsps_backmap_schema_version = str(
        receipt.get("backmapping_onsps_backmap_schema_version") or ""
    )
    backmapping_hbond_evaluated_row_count = _int_value(receipt.get("backmapping_hbond_evaluated_row_count"))
    backmapping_onsps_backmap_claim_safe_row_count = _int_value(
        receipt.get("backmapping_onsps_backmap_claim_safe_row_count")
    )
    backmapping_ligand_topology_valid = bool(receipt.get("backmapping_ligand_topology_valid") is True)
    backmapping_ligand_topology_claim_safe = bool(
        receipt.get("backmapping_ligand_topology_claim_safe") is True
    )
    backmapping_ligand_topology_schema_version = str(
        receipt.get("backmapping_ligand_topology_schema_version") or ""
    )
    backmapping_ligand_topology_schema_ready_row_count = _int_value(
        receipt.get("backmapping_ligand_topology_schema_ready_row_count")
    )
    backmapping_ligand_topology_claim_safe_row_count = _int_value(
        receipt.get("backmapping_ligand_topology_claim_safe_row_count")
    )
    backmapping_ligand_topology_invalid_row_count = _int_value(
        receipt.get("backmapping_ligand_topology_invalid_row_count")
    )
    backmapping_ligand_topology_receipt_ready = bool(
        backmapping_ligand_topology_schema_version == "ligand_topology_validity_v1"
        and backmapping_ligand_topology_schema_ready_row_count >= 1
        and (
            receipt.get("backmapping_ligand_topology_receipt_ready") is True
            or (
                backmapping_ligand_topology_valid
                and backmapping_ligand_topology_claim_safe
                and backmapping_ligand_topology_claim_safe_row_count >= 1
                and backmapping_ligand_topology_invalid_row_count == 0
            )
        )
    )
    backmapping_hbond_evidence_receipt_ready = bool(
        backmapping_hbond_evidence_schema_version == "hbond_evidence_v1"
        and backmapping_hbond_claim_metadata_schema_version == "hbond_evidence_v1"
        and backmapping_hbond_claim_metadata_schema_ready_row_count >= 1
        and backmapping_hbond_evaluated_row_count >= 1
    )
    backmapping_onsps_backmap_receipt_ready = bool(
        backmapping_onsps_backmap_schema_version == "onsps_backmap_evidence_v1"
        and backmapping_onsps_backmap_claim_safe_row_count >= 1
    )
    receipt_clean_container_smoke_ready = bool(receipt.get("clean_container_smoke_ready") is True)
    receipt_runner_hygiene_schema_version = str(
        receipt.get("runner_hygiene_schema_version") or ""
    )
    receipt_runner_hygiene_schema_ready = bool(
        receipt_runner_hygiene_schema_version == RUNNER_HYGIENE_SCHEMA_VERSION
    )
    receipt_runner_smoke_dir = str(receipt.get("runner_smoke_dir") or "")
    receipt_workspace_runner_smoke_dir = str(receipt.get("workspace_runner_smoke_dir") or "")
    receipt_runner_smoke_dir_outside_workspace = bool(
        receipt.get("runner_smoke_dir_outside_workspace") is True
    )
    receipt_container_uid_gid = str(receipt.get("container_uid_gid") or "")
    receipt_host_uid_gid = str(receipt.get("host_uid_gid") or "")
    receipt_container_output_uid_gid_pinned = bool(
        receipt.get("container_output_uid_gid_pinned") is True
    )
    receipt_container_output_uid_gid_matches_host = bool(
        receipt.get("container_output_uid_gid_matches_host") is True
    )
    receipt_container_output_uid_gid_non_root = bool(
        receipt.get("container_output_uid_gid_non_root") is True
    )
    container_output_uid_gid_fixed = bool(
        receipt_container_output_uid_gid_pinned
        and receipt_container_output_uid_gid_matches_host
        and receipt_container_output_uid_gid_non_root
    )
    receipt_workspace_runner_smoke_dir_cleanup_ready = bool(
        receipt.get("workspace_runner_smoke_dir_cleanup_ready") is True
    )
    receipt_workspace_runner_smoke_dir_exists_after_cleanup = bool(
        receipt.get("workspace_runner_smoke_dir_exists_after_cleanup") is True
    )
    receipt_runner_hygiene_applicable = bool(
        receipt_present
        and receipt_mode == "rocm-runtime"
    )
    receipt_runner_hygiene_blockers: list[str] = []
    if receipt_runner_hygiene_applicable:
        if not receipt_runner_hygiene_schema_ready:
            receipt_runner_hygiene_blockers.append("receipt_runner_hygiene_schema_missing")
        if not receipt_runner_smoke_dir_outside_workspace:
            receipt_runner_hygiene_blockers.append("receipt_runner_smoke_dir_inside_workspace")
        if not receipt_container_output_uid_gid_pinned:
            receipt_runner_hygiene_blockers.append("receipt_container_output_uid_gid_not_pinned")
        if not receipt_container_output_uid_gid_matches_host:
            receipt_runner_hygiene_blockers.append("receipt_container_output_uid_gid_not_host")
        if not receipt_container_output_uid_gid_non_root:
            receipt_runner_hygiene_blockers.append("receipt_container_output_uid_gid_root")
        if not receipt_workspace_runner_smoke_dir_cleanup_ready:
            receipt_runner_hygiene_blockers.append("receipt_workspace_runner_smoke_dir_cleanup_not_ready")
        if receipt_workspace_runner_smoke_dir_exists_after_cleanup:
            receipt_runner_hygiene_blockers.append("receipt_workspace_runner_smoke_dir_still_exists_after_cleanup")
    receipt_runner_hygiene_ready = not receipt_runner_hygiene_blockers
    receipt_runner_hygiene_refresh_required = bool(
        receipt_runner_hygiene_applicable and not receipt_runner_hygiene_ready
    )
    receipt_runner_hygiene_verification_command = (
        "PRODUCT_IMAGE_VERIFY_MODE=rocm-runtime "
        "PRODUCT_IMAGE_RUNNER_SMOKE_DIR=${RUNNER_TEMP:-/tmp}/product_image_smoke_runner_artifacts "
        "PRODUCT_IMAGE_CONTAINER_UID_GID=\"$(id -u):$(id -g)\" "
        "bash deploy/verify_product_image.sh"
    )
    receipt_runner_hygiene_required_action = (
        "Refresh the ROCm product image smoke receipt on the self-hosted ROCm runner so it "
        f"records {RUNNER_HYGIENE_SCHEMA_VERSION}, a runner-temp smoke artifact directory, "
        "the host UID:GID, matching non-root container UID:GID, and successful workspace cleanup."
        if receipt_runner_hygiene_refresh_required
        else ""
    )
    clean_container_smoke_ready = bool(
        receipt_status == "product_image_smoke_ready"
        and receipt_mode == "rocm-runtime"
        and receipt_simulate_missing_profile_http == 422
        and product_runner_smoke_ready
        and product_runner_claim_metadata_ready
        and tier_alpha_manifest_signature_verified
        and tier_alpha_manifest_status == "completed"
        and backmapping_runner_claim_metadata_ready
        and backmapping_ligand_topology_receipt_ready
        and backmapping_hbond_evidence_receipt_ready
        and backmapping_onsps_backmap_receipt_ready
        and receipt_clean_container_smoke_ready
        and container_runtime_receipt_ready
        and receipt_runner_hygiene_schema_ready
        and receipt_runner_smoke_dir_outside_workspace
        and receipt_container_output_uid_gid_pinned
        and receipt_container_output_uid_gid_matches_host
        and receipt_container_output_uid_gid_non_root
        and receipt_workspace_runner_smoke_dir_cleanup_ready
        and not receipt_workspace_runner_smoke_dir_exists_after_cleanup
        and receipt.get("rocm_runtime_visible_device_required") is True
    )
    docker_access_ready = bool(docker_cli_present and docker_daemon_ready)
    preflight_ready = bool(
        script_contract_ready
        and workflow_contract_ready
        and workspace_artifact_cleanup_ready
        and (docker_access_ready or clean_container_smoke_ready)
        and receipt_runner_hygiene_ready
    )
    blockers = []
    if not clean_container_smoke_ready and not docker_cli_present:
        blockers.append({"code": "docker_cli_missing"})
    elif not clean_container_smoke_ready and not docker_daemon_ready:
        blockers.append({"code": "docker_daemon_unreachable"})
    for row in rows:
        if not row["passed"]:
            blockers.append({"code": row["check_id"]})
    for blocker in workspace_artifact_blockers:
        blockers.append({"code": blocker})
    for blocker in receipt_runner_hygiene_blockers:
        blockers.append({"code": blocker})
    summary = {
        "packet_type": "product_image_smoke_preflight",
        "status": "product_image_smoke_preflight_ready" if preflight_ready else "blocked_product_image_smoke_preflight",
        "preflight_ready": preflight_ready,
        "docker_cli_present": docker_cli_present,
        "docker_cli_path": docker_cli or "",
        "docker_daemon_reachable": bool(docker_daemon_ready),
        "script_contract_ready": script_contract_ready,
        "workflow_contract_ready": workflow_contract_ready,
        "runner_smoke_dir_contract_ready": runner_smoke_dir_contract_ready,
        "workflow_workspace_artifact_recovery_ready": workflow_workspace_artifact_recovery_ready,
        "pre_checkout_cleanup_ready": pre_checkout_cleanup_ready,
        **workspace_artifact_state,
        "workspace_smoke_artifact_current_blocker_count": len(
            workspace_artifact_blockers
        ),
        "workspace_smoke_artifact_current_blockers": workspace_artifact_blockers,
        "clean_container_smoke_ready": clean_container_smoke_ready,
        "receipt_json": str(receipt_json),
        "receipt_present": receipt_present,
        "receipt_status": receipt_status,
        "receipt_mode": receipt_mode,
        "receipt_simulate_missing_profile_http": receipt_simulate_missing_profile_http,
        "receipt_clean_container_smoke_ready": receipt_clean_container_smoke_ready,
        "required_runner_hygiene_schema_version": RUNNER_HYGIENE_SCHEMA_VERSION,
        "receipt_runner_hygiene_schema_version": receipt_runner_hygiene_schema_version,
        "receipt_runner_hygiene_schema_ready": receipt_runner_hygiene_schema_ready,
        "receipt_runner_smoke_dir": receipt_runner_smoke_dir,
        "receipt_workspace_runner_smoke_dir": receipt_workspace_runner_smoke_dir,
        "receipt_runner_smoke_dir_outside_workspace": receipt_runner_smoke_dir_outside_workspace,
        "receipt_host_uid_gid": receipt_host_uid_gid,
        "receipt_container_uid_gid": receipt_container_uid_gid,
        "receipt_container_output_uid_gid_pinned": receipt_container_output_uid_gid_pinned,
        "receipt_container_output_uid_gid_matches_host": receipt_container_output_uid_gid_matches_host,
        "receipt_container_output_uid_gid_non_root": receipt_container_output_uid_gid_non_root,
        "container_output_uid_gid_fixed": container_output_uid_gid_fixed,
        "receipt_workspace_runner_smoke_dir_cleanup_ready": receipt_workspace_runner_smoke_dir_cleanup_ready,
        "receipt_workspace_runner_smoke_dir_exists_after_cleanup": (
            receipt_workspace_runner_smoke_dir_exists_after_cleanup
        ),
        "receipt_runner_hygiene_applicable": receipt_runner_hygiene_applicable,
        "receipt_runner_hygiene_ready": receipt_runner_hygiene_ready,
        "receipt_runner_hygiene_refresh_required": receipt_runner_hygiene_refresh_required,
        "receipt_runner_hygiene_blocker_count": len(receipt_runner_hygiene_blockers),
        "receipt_runner_hygiene_blockers": receipt_runner_hygiene_blockers,
        "receipt_runner_hygiene_required_action": receipt_runner_hygiene_required_action,
        "receipt_runner_hygiene_verification_command": receipt_runner_hygiene_verification_command,
        "container_runtime_proof_present": bool(receipt.get("container_runtime_proof_present") is True),
        "container_runtime_proof_schema_version": container_runtime_proof_schema_version,
        "container_runtime_proof_ready": container_runtime_proof_ready,
        "container_runtime_receipt_ready": container_runtime_receipt_ready,
        "container_runtime_in_container": container_runtime_in_container,
        "container_runtime_device_nodes_ready": container_runtime_device_nodes_ready,
        "container_runtime_torch_rocm_ready": container_runtime_torch_rocm_ready,
        "container_runtime_torch_cuda_available": container_runtime_torch_cuda_available,
        "container_runtime_visible_device_count": container_runtime_visible_device_count,
        "container_runtime_visible_device_name": str(
            receipt.get("container_runtime_visible_device_name") or ""
        ),
        "container_runtime_rust_hip_backend_enabled": container_runtime_rust_hip_backend_enabled,
        "container_runtime_rust_hip_kernel_name": str(
            receipt.get("container_runtime_rust_hip_kernel_name") or ""
        ),
        "runtime_neighbor_release_scaling_present": bool(
            receipt.get("runtime_neighbor_release_scaling_present") is True
        ),
        "runtime_neighbor_release_scaling_ready": bool(
            receipt.get("runtime_neighbor_release_scaling_ready") is True
        ),
        "runtime_neighbor_release_scaling_status": str(
            receipt.get("runtime_neighbor_release_scaling_status") or ""
        ),
        "runtime_neighbor_release_atom_counts_ready": bool(
            receipt.get("runtime_neighbor_release_atom_counts_ready") is True
        ),
        "runtime_neighbor_release_atom_counts": (
            list(receipt.get("runtime_neighbor_release_atom_counts"))
            if isinstance(receipt.get("runtime_neighbor_release_atom_counts"), list)
            else []
        ),
        "runtime_neighbor_release_pair_count_slope": receipt.get(
            "runtime_neighbor_release_pair_count_slope"
        ),
        "runtime_neighbor_release_pair_count_r2": receipt.get("runtime_neighbor_release_pair_count_r2"),
        "runtime_neighbor_release_nxn_allocation_observed": bool(
            receipt.get("runtime_neighbor_release_nxn_allocation_observed") is True
        ),
        "runtime_neighbor_release_max_memory_peak_mb_per_atom": receipt.get(
            "runtime_neighbor_release_max_memory_peak_mb_per_atom"
        ),
        "product_runner_smoke_ready": product_runner_smoke_ready,
        "product_runner_claim_metadata_ready": product_runner_claim_metadata_ready,
        "tier_alpha_result_manifest_signature_verified": tier_alpha_manifest_signature_verified,
        "tier_alpha_result_manifest_status": tier_alpha_manifest_status,
        "backmapping_runner_claim_metadata_ready": backmapping_runner_claim_metadata_ready,
        "backmapping_hbond_evidence_schema_version": backmapping_hbond_evidence_schema_version,
        "backmapping_hbond_claim_metadata_schema_version": backmapping_hbond_claim_metadata_schema_version,
        "backmapping_hbond_claim_metadata_schema_ready_row_count": (
            backmapping_hbond_claim_metadata_schema_ready_row_count
        ),
        "backmapping_onsps_backmap_schema_version": backmapping_onsps_backmap_schema_version,
        "backmapping_hbond_evaluated_row_count": backmapping_hbond_evaluated_row_count,
        "backmapping_onsps_backmap_claim_safe_row_count": backmapping_onsps_backmap_claim_safe_row_count,
        "backmapping_ligand_topology_valid": backmapping_ligand_topology_valid,
        "backmapping_ligand_topology_claim_safe": backmapping_ligand_topology_claim_safe,
        "backmapping_ligand_topology_schema_version": backmapping_ligand_topology_schema_version,
        "backmapping_ligand_topology_schema_ready_row_count": backmapping_ligand_topology_schema_ready_row_count,
        "backmapping_ligand_topology_claim_safe_row_count": backmapping_ligand_topology_claim_safe_row_count,
        "backmapping_ligand_topology_invalid_row_count": backmapping_ligand_topology_invalid_row_count,
        "backmapping_ligand_topology_receipt_ready": backmapping_ligand_topology_receipt_ready,
        "backmapping_hbond_evidence_receipt_ready": backmapping_hbond_evidence_receipt_ready,
        "backmapping_onsps_backmap_receipt_ready": backmapping_onsps_backmap_receipt_ready,
        "build_contract_command": "PRODUCT_IMAGE_VERIFY_MODE=build bash deploy/verify_product_image.sh",
        "docker_host_setup_command": "bash scripts/prepare_product_docker_host.sh",
        "docker_cmd_override_example": (
            "DOCKER_CMD='sudo docker' PRODUCT_IMAGE_VERIFY_MODE=rocm-runtime bash deploy/verify_product_image.sh"
        ),
        "rocm_runtime_runner_smoke_command": "PRODUCT_IMAGE_VERIFY_MODE=rocm-runtime bash deploy/verify_product_image.sh",
        "required_runtime_mode_for_product_claim": "rocm-runtime",
        "execution_enabled": False,
        "container_build_executed": False,
        "container_runner_smoke_executed": False,
        "container_runner_smoke_receipt_attached": receipt_present,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "Attach clean container smoke receipt to the product evidence bundle."
            if clean_container_smoke_ready and workspace_artifact_cleanup_ready
            else workspace_artifact_state["workspace_smoke_artifact_current_required_action"]
            if not workspace_artifact_cleanup_ready
            else (
                "Run bash scripts/prepare_product_docker_host.sh on this ROCm host, then run "
                "PRODUCT_IMAGE_VERIFY_MODE=rocm-runtime bash deploy/verify_product_image.sh."
                if not docker_cli_present
                else (
                    "Start Docker or refresh this shell's docker group access, then rerun "
                    "PRODUCT_IMAGE_VERIFY_MODE=rocm-runtime bash deploy/verify_product_image.sh."
                    if not docker_daemon_ready
                    else "Run PRODUCT_IMAGE_VERIFY_MODE=rocm-runtime bash deploy/verify_product_image.sh on a Docker-enabled ROCm host."
                )
            )
        ),
    }
    return {"summary": summary, "rows": rows, "blockers": blockers}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build product image smoke preflight evidence.")
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    parser.add_argument(
        "--out-runner-hygiene-work-order-json",
        default=DEFAULT_OUT_RUNNER_HYGIENE_WORK_ORDER_JSON,
    )
    parser.add_argument(
        "--out-runner-hygiene-work-order-csv",
        default=DEFAULT_OUT_RUNNER_HYGIENE_WORK_ORDER_CSV,
    )
    parser.add_argument(
        "--out-runner-hygiene-work-order-md",
        default=DEFAULT_OUT_RUNNER_HYGIENE_WORK_ORDER_MD,
    )
    parser.add_argument(
        "--out-runner-hygiene-command-pack-json",
        default=DEFAULT_OUT_RUNNER_HYGIENE_COMMAND_PACK_JSON,
    )
    parser.add_argument(
        "--out-runner-hygiene-command-pack-sh",
        default=DEFAULT_OUT_RUNNER_HYGIENE_COMMAND_PACK_SH,
    )
    parser.add_argument(
        "--out-runner-hygiene-command-pack-md",
        default=DEFAULT_OUT_RUNNER_HYGIENE_COMMAND_PACK_MD,
    )
    parser.add_argument("--receipt-json", default=DEFAULT_RECEIPT_JSON)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    payload = build_product_image_smoke_preflight(root=args.root, receipt_json=args.receipt_json)
    work_order_payload = build_product_image_smoke_runner_hygiene_work_order(payload)
    command_pack_payload = build_product_image_smoke_runner_hygiene_command_pack(
        payload,
        work_order_payload,
    )
    _write_json(args.out_json, payload)
    _write_markdown(args.out_md, payload)
    _write_json(args.out_runner_hygiene_work_order_json, work_order_payload)
    _write_csv(
        args.out_runner_hygiene_work_order_csv,
        work_order_payload["rows"],
        RUNNER_HYGIENE_WORK_ORDER_FIELDS,
    )
    _write_runner_hygiene_work_order_markdown(
        args.out_runner_hygiene_work_order_md,
        work_order_payload,
    )
    _write_json(args.out_runner_hygiene_command_pack_json, command_pack_payload)
    _write_runner_hygiene_command_pack_text_outputs(
        shell_path_like=args.out_runner_hygiene_command_pack_sh,
        markdown_path_like=args.out_runner_hygiene_command_pack_md,
        payload=command_pack_payload,
    )
    print(json.dumps({"status": payload["summary"]["status"], "out_json": args.out_json}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

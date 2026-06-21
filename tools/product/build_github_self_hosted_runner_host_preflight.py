#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT_JSON = "runs/github_self_hosted_runner_host_preflight_current.json"
DEFAULT_OUT_MD = "runs/github_self_hosted_runner_host_preflight_current.md"
DEFAULT_PRODUCT_IMAGE_PREFLIGHT_JSON = "runs/product_image_smoke_preflight_current.json"
DEFAULT_RUNNER_INVENTORY_JSON = "runs/github_self_hosted_runner_inventory_current.json"

REPO = "betelgeuze-kang/ligand-docking"
REPO_URL = f"https://github.com/{REPO}"
RUNNER_SETTINGS_URL = f"{REPO_URL}/settings/actions/runners"
RUNNER_NEW_URL = f"{RUNNER_SETTINGS_URL}/new?arch=x64&os=linux"
LINUX_LABELS = ["self-hosted", "linux"]
ROCM_LABELS = ["self-hosted", "linux", "rocm"]
INVENTORY_REFRESH_COMMAND = (
    f"gh api repos/{REPO}/actions/runners --paginate > "
    "runs/github_self_hosted_runner_inventory_current.json"
)
API_WORKER_RERUN_COMMAND = (
    "gh workflow run product-api-worker.yml -f runner_labels_json='[\"self-hosted\",\"linux\"]'"
)
ROCM_RUNTIME_RERUN_COMMAND = "gh workflow run product-image-smoke.yml -f verify_mode=rocm-runtime"

CLAIM_BOUNDARY = (
    "Self-hosted runner host preflight only; records local Docker/ROCm product-runner readiness and "
    "read-only GitHub runner inventory evidence. It does not request registration tokens, configure a "
    "runner, start services, dispatch workflows, mutate billing, or change GitHub settings."
)


def _resolve(root: Path, path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else root / path


def _read_json(root: Path, path_like: str | Path) -> dict[str, Any]:
    path = _resolve(root, path_like)
    if not path.exists() or not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _summary(packet: dict[str, Any]) -> dict[str, Any]:
    summary = packet.get("summary")
    return summary if isinstance(summary, dict) else packet


def _label_names(runner: dict[str, Any]) -> set[str]:
    labels = runner.get("labels")
    names: set[str] = set()
    if isinstance(labels, list):
        for label in labels:
            value = label.get("name") if isinstance(label, dict) else label
            if value:
                names.add(str(value).strip().lower())
    elif isinstance(labels, str):
        names.update(part.strip().lower() for part in labels.split(",") if part.strip())
    return names


def _online_runner_count(packet: dict[str, Any], required_labels: list[str]) -> int:
    runners = packet.get("runners")
    if not isinstance(runners, list):
        return 0
    required = {label.lower() for label in required_labels}
    count = 0
    for runner in runners:
        if not isinstance(runner, dict):
            continue
        if str(runner.get("status") or "").lower() != "online":
            continue
        if required <= _label_names(runner):
            count += 1
    return count


def _docker_cli_present() -> bool:
    return shutil.which("docker") is not None


def _docker_daemon_accessible() -> bool:
    if not _docker_cli_present():
        return False
    try:
        return subprocess.run(
            ["docker", "info"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
            timeout=10,
        ).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def _rocm_device_nodes_ready() -> bool:
    return Path("/dev/kfd").exists() and Path("/dev/dri").exists()


def build_github_self_hosted_runner_host_preflight(
    *,
    root: str | Path = ROOT,
    product_image_preflight_json: str | Path = DEFAULT_PRODUCT_IMAGE_PREFLIGHT_JSON,
    runner_inventory_json: str | Path = DEFAULT_RUNNER_INVENTORY_JSON,
    docker_cli_present: bool | None = None,
    docker_daemon_accessible: bool | None = None,
    rocm_device_nodes_ready: bool | None = None,
) -> dict[str, Any]:
    root_path = Path(root)
    product_image_summary = _summary(_read_json(root_path, product_image_preflight_json))
    runner_inventory = _read_json(root_path, runner_inventory_json)
    docker_cli = _docker_cli_present() if docker_cli_present is None else docker_cli_present
    docker_daemon = (
        _docker_daemon_accessible() if docker_daemon_accessible is None else docker_daemon_accessible
    )
    rocm_nodes = _rocm_device_nodes_ready() if rocm_device_nodes_ready is None else rocm_device_nodes_ready

    product_image_rocm_runtime_ready = bool(
        product_image_summary.get("status") == "product_image_smoke_preflight_ready"
        and product_image_summary.get("receipt_status") == "product_image_smoke_ready"
        and product_image_summary.get("receipt_mode") == "rocm-runtime"
        and product_image_summary.get("clean_container_smoke_ready") is True
        and product_image_summary.get("container_runtime_receipt_ready") is True
        and product_image_summary.get("container_runtime_rust_hip_backend_enabled") is True
        and product_image_summary.get("product_runner_claim_metadata_ready") is True
    )
    local_runner_host_ready = bool(docker_cli and docker_daemon and rocm_nodes and product_image_rocm_runtime_ready)
    linux_online_count = _online_runner_count(runner_inventory, LINUX_LABELS)
    rocm_online_count = _online_runner_count(runner_inventory, ROCM_LABELS)
    repo_runner_ready = bool(linux_online_count > 0 and rocm_online_count > 0)
    registration_required = not repo_runner_ready

    blockers: list[dict[str, str]] = []
    if not docker_cli:
        blockers.append({"code": "docker_cli_missing"})
    if not docker_daemon:
        blockers.append({"code": "docker_daemon_unreachable"})
    if not rocm_nodes:
        blockers.append({"code": "rocm_device_nodes_missing"})
    if not product_image_rocm_runtime_ready:
        blockers.append({"code": "product_image_rocm_runtime_receipt_missing"})
    if local_runner_host_ready and registration_required:
        blockers.append({"code": "github_self_hosted_runner_registration_required"})
    if local_runner_host_ready and linux_online_count == 0:
        blockers.append({"code": "github_self_hosted_linux_runner_not_online"})
    if local_runner_host_ready and rocm_online_count == 0:
        blockers.append({"code": "github_self_hosted_rocm_runner_not_online"})

    if local_runner_host_ready and repo_runner_ready:
        status = "github_self_hosted_runner_host_preflight_ready"
    elif local_runner_host_ready:
        status = "blocked_github_self_hosted_runner_registration_required"
    else:
        status = "blocked_github_self_hosted_runner_host_preflight"

    if repo_runner_ready:
        next_required_steps = [
            f"Rerun API worker: {API_WORKER_RERUN_COMMAND}",
            f"Rerun ROCm runtime smoke: {ROCM_RUNTIME_RERUN_COMMAND}",
        ]
    else:
        next_required_steps = [
            f"Open {RUNNER_NEW_URL} as a repo admin and create a Linux x64 self-hosted runner.",
            "Run the GitHub-provided download/config commands on this ROCm host; add custom label: rocm.",
            "Install/start the runner service from the GitHub-provided runner directory.",
            f"Refresh inventory: {INVENTORY_REFRESH_COMMAND}",
            f"Rerun API worker: {API_WORKER_RERUN_COMMAND}",
            f"Rerun ROCm runtime smoke: {ROCM_RUNTIME_RERUN_COMMAND}",
        ]

    summary = {
        "packet_type": "github_self_hosted_runner_host_preflight",
        "status": status,
        "local_runner_host_ready": local_runner_host_ready,
        "repo_self_hosted_runner_ready": repo_runner_ready,
        "repo_runner_registration_required": registration_required,
        "docker_cli_present": docker_cli,
        "docker_daemon_accessible": docker_daemon,
        "rocm_device_nodes_ready": rocm_nodes,
        "product_image_rocm_runtime_ready": product_image_rocm_runtime_ready,
        "product_image_preflight_json": str(product_image_preflight_json),
        "runner_inventory_json": str(runner_inventory_json),
        "runner_inventory_present": bool(runner_inventory),
        "runner_inventory_total_count": int(runner_inventory.get("total_count") or 0),
        "linux_runner_online_count": linux_online_count,
        "rocm_runner_online_count": rocm_online_count,
        "required_linux_runner_labels": LINUX_LABELS,
        "required_rocm_runner_labels": ROCM_LABELS,
        "recommended_rocm_custom_label": "rocm",
        "repo_url": REPO_URL,
        "runner_settings_url": RUNNER_SETTINGS_URL,
        "runner_new_url": RUNNER_NEW_URL,
        "inventory_refresh_command": INVENTORY_REFRESH_COMMAND,
        "product_api_worker_rerun_command": API_WORKER_RERUN_COMMAND,
        "product_image_rocm_runtime_rerun_command": ROCM_RUNTIME_RERUN_COMMAND,
        "github_registration_token_requested": False,
        "runner_configured": repo_runner_ready,
        "runner_service_started": repo_runner_ready,
        "workflow_dispatch_executed": False,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_steps": next_required_steps,
    }
    return {"summary": summary, "blockers": blockers}


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(ROOT, path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_markdown(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(ROOT, path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    s = payload["summary"]
    lines = [
        "# GitHub Self-Hosted Runner Host Preflight",
        "",
        f"- status: `{s['status']}`",
        f"- local_runner_host_ready: `{s['local_runner_host_ready']}`",
        f"- repo_self_hosted_runner_ready: `{s['repo_self_hosted_runner_ready']}`",
        f"- repo_runner_registration_required: `{s['repo_runner_registration_required']}`",
        f"- docker_daemon_accessible: `{s['docker_daemon_accessible']}`",
        f"- rocm_device_nodes_ready: `{s['rocm_device_nodes_ready']}`",
        f"- product_image_rocm_runtime_ready: `{s['product_image_rocm_runtime_ready']}`",
        f"- runner_inventory_total_count: `{s['runner_inventory_total_count']}`",
        f"- linux_runner_online_count: `{s['linux_runner_online_count']}`",
        f"- rocm_runner_online_count: `{s['rocm_runner_online_count']}`",
        "",
        "## Blockers",
        "",
    ]
    blockers = payload.get("blockers") or []
    lines.extend(f"- `{row['code']}`" for row in blockers) if blockers else lines.append("- none")
    lines.extend(["", "## Next Steps", ""])
    lines.extend(f"- {step}" for step in s["next_required_steps"])
    lines.extend(["", "## Claim Boundary", "", s["claim_boundary"], ""])
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build GitHub self-hosted runner host preflight evidence.")
    parser.add_argument("--product-image-preflight-json", default=DEFAULT_PRODUCT_IMAGE_PREFLIGHT_JSON)
    parser.add_argument("--runner-inventory-json", default=DEFAULT_RUNNER_INVENTORY_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    payload = build_github_self_hosted_runner_host_preflight(
        product_image_preflight_json=args.product_image_preflight_json,
        runner_inventory_json=args.runner_inventory_json,
    )
    _write_json(args.out_json, payload)
    _write_markdown(args.out_md, payload)
    print(json.dumps({"status": payload["summary"]["status"], "out_json": args.out_json}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

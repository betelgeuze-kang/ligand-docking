#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import time
from pathlib import Path
from typing import Any

APPROVAL_TOKEN = "APPROVE_PRODUCT_ROLLOUT"


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _quote(command: list[str]) -> str:
    return " ".join(_shell_quote(part) for part in command)


def _shell_quote(value: str) -> str:
    if not value:
        return "''"
    safe = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_/:=.,@%+-"
    if all(ch in safe for ch in value):
        return value
    return "'" + value.replace("'", "'\"'\"'") + "'"


def _command_row(stage: str, command: list[str], *, mutates_external_state: bool) -> dict[str, Any]:
    return {
        "stage": stage,
        "command": command,
        "command_display": _quote(command),
        "mutates_external_state": mutates_external_state,
    }


def build_rollout_plan(args: argparse.Namespace) -> dict[str, Any]:
    root = _repo_root()
    image = str(args.image)
    publish_image = str(args.publish_image or args.image)
    mode = str(args.mode)
    rows: list[dict[str, Any]] = []

    rows.append(
        _command_row(
            "docker_build",
            ["docker", "build", "-f", str(args.dockerfile), "-t", image, "."],
            mutates_external_state=False,
        )
    )
    if publish_image != image:
        rows.append(_command_row("docker_tag", ["docker", "tag", image, publish_image], mutates_external_state=False))
    if args.push:
        rows.append(_command_row("docker_push", ["docker", "push", publish_image], mutates_external_state=True))

    if mode in {"compose", "all"}:
        rows.append(
            _command_row(
                "compose_up",
                ["docker", "compose", "-f", str(args.compose_file), "up", "-d", "--build"],
                mutates_external_state=True,
            )
        )
        rows.append(
            _command_row(
                "compose_metrics_smoke",
                ["curl", "-fsS", f"http://127.0.0.1:{args.compose_api_port}/metrics"],
                mutates_external_state=False,
            )
        )

    if mode in {"k8s", "all"}:
        rows.append(_command_row("k8s_apply", ["kubectl", "apply", "-k", str(args.k8s_dir)], mutates_external_state=True))
        rows.append(
            _command_row(
                "k8s_set_api_image",
                [
                    "kubectl",
                    "-n",
                    str(args.namespace),
                    "set",
                    "image",
                    "deployment/micf-api-server",
                    f"api-server={publish_image}",
                ],
                mutates_external_state=True,
            )
        )
        rows.append(
            _command_row(
                "k8s_set_worker_image",
                [
                    "kubectl",
                    "-n",
                    str(args.namespace),
                    "set",
                    "image",
                    "deployment/micf-api-worker",
                    f"api-worker={publish_image}",
                ],
                mutates_external_state=True,
            )
        )
        for deployment in ("micf-api-server", "micf-api-worker"):
            rows.append(
                _command_row(
                    f"k8s_rollout_status_{deployment}",
                    [
                        "kubectl",
                        "-n",
                        str(args.namespace),
                        "rollout",
                        "status",
                        f"deployment/{deployment}",
                        "--timeout",
                        str(args.rollout_timeout),
                    ],
                    mutates_external_state=False,
                )
            )

    return {
        "plan_version": "product_rollout_plan_v1",
        "status": "planned",
        "mode": mode,
        "dry_run": not bool(args.execute),
        "approval_required": True,
        "approval_token_required": APPROVAL_TOKEN,
        "approval_token_present": str(args.approval_token or "") == APPROVAL_TOKEN,
        "target": {
            "image": image,
            "publish_image": publish_image,
            "compose_file": str(args.compose_file),
            "k8s_dir": str(args.k8s_dir),
            "namespace": str(args.namespace),
        },
        "action": "Build product API image, optionally push it, and roll out compose and/or K8s product API worker units.",
        "impact": "Can publish a container image and restart API server/worker workloads when executed.",
        "risk": "Bad image tags, missing secrets, registry auth, or K8s context mistakes can interrupt the self-hosted product API.",
        "rollback": [
            "Redeploy the previous image digest recorded in the release bundle.",
            "Run deploy/rollback_model.py if the model registry pointer also changed.",
            "Verify /metrics, /product/api-contract, /product/service-boundary, and /product/operations.",
        ],
        "verification": [
            "docker image build exits 0.",
            "compose or K8s rollout status exits 0.",
            "/metrics is reachable after rollout.",
            "API worker smoke remains green against the durable queue.",
        ],
        "commands": rows,
        "external_state_mutation_blocked_by_default": True,
        "claim_boundary": (
            "Product rollout operator plan only. Dry-run mode prints commands and does not build, push, deploy, restart, "
            "or mutate external state. Execute mode requires explicit APPROVE_PRODUCT_ROLLOUT approval."
        ),
    }


def _write_json(path_like: str, payload: dict[str, Any]) -> None:
    if not path_like:
        return
    path = Path(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")


def _run_commands(commands: list[dict[str, Any]], *, cwd: Path) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for row in commands:
        started = time.time()
        completed = subprocess.run(row["command"], cwd=cwd, capture_output=True, text=True, check=False)
        result = {
            "stage": row["stage"],
            "returncode": completed.returncode,
            "elapsed_ms": int((time.time() - started) * 1000),
            "stdout_tail": completed.stdout[-2000:],
            "stderr_tail": completed.stderr[-2000:],
        }
        results.append(result)
        if completed.returncode != 0:
            break
    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Plan or execute product API build/push/deploy rollout.")
    parser.add_argument("--mode", choices=["build-only", "compose", "k8s", "all"], default="build-only")
    parser.add_argument("--image", default="micf-api:product")
    parser.add_argument("--publish-image", default="")
    parser.add_argument("--push", action="store_true")
    parser.add_argument("--dockerfile", default="Dockerfile.product")
    parser.add_argument("--compose-file", default="deploy/docker-compose.product.yml")
    parser.add_argument("--compose-api-port", default=os.getenv("API_PORT", "8000"))
    parser.add_argument("--k8s-dir", default="deploy/k8s")
    parser.add_argument("--namespace", default="micf-product")
    parser.add_argument("--rollout-timeout", default="180s")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--approval-token", default=os.getenv("PRODUCT_ROLLOUT_APPROVAL_TOKEN", ""))
    parser.add_argument("--out-json", default="")
    args = parser.parse_args(argv)

    plan = build_rollout_plan(args)
    if args.execute:
        if args.approval_token != APPROVAL_TOKEN:
            plan["status"] = "blocked_approval_required"
            _write_json(args.out_json, plan)
            print(json.dumps(plan, indent=2, sort_keys=True, ensure_ascii=False))
            return 2
        plan["status"] = "executing"
        plan["results"] = _run_commands(plan["commands"], cwd=_repo_root())
        plan["status"] = "pass" if all(row["returncode"] == 0 for row in plan["results"]) else "fail"
    _write_json(args.out_json, plan)
    print(json.dumps(plan, indent=2, sort_keys=True, ensure_ascii=False))
    return 0 if plan["status"] in {"planned", "pass"} else 1


if __name__ == "__main__":
    raise SystemExit(main())

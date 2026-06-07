#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT_JSON = "runs/cleanup_operations_surface_contract_current.json"
DEFAULT_OUT_CSV = "runs/cleanup_operations_surface_contract_current.csv"
DEFAULT_OUT_MD = "runs/cleanup_operations_surface_contract_current.md"

CLAIM_BOUNDARY = (
    "Cleanup operations surface contract only; it audits whether the repository exposes read-only cleanup operations, "
    "approval-gate, completion, postcheck, payload, protected ligand-heavy review, and protected-policy API surfaces from local files. "
    "It does not approve cleanup, delete, move, archive, externalize, upload, commit, push, or mutate external state."
)


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _file_text(root: Path, path_like: str) -> str:
    path = root / path_like
    if not path.is_file():
        return ""
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def _row(check: str, passed: bool, observed: str, required: str, artifact_path: str, reason: str) -> dict[str, Any]:
    return {
        "check": check,
        "status": "pass" if passed else "fail",
        "observed": observed,
        "required": required,
        "artifact_path": artifact_path,
        "reason": reason,
        "release_blocker": not passed,
        "execution_enabled": False,
        "delete_enabled": False,
        "delete_executed": False,
        "external_state_mutated": False,
    }


def build_cleanup_operations_surface_contract(*, root: str | Path = ".") -> dict[str, Any]:
    root_path = Path(root).resolve()
    api_text = _file_text(root_path, "api/cleanup.py")
    main_text = _file_text(root_path, "api/main.py")
    api_file_present = bool(api_text)
    local_status_cli_present = (root_path / "betelgeuze_cleanup" / "cli.py").is_file()
    router_registered = "cleanup_router" in main_text and "app.include_router(cleanup_router)" in main_text
    operations_endpoint_present = '"/operations"' in api_text
    approval_gate_endpoint_present = '"/approval-gate"' in api_text
    completion_endpoint_present = '"/completion"' in api_text
    postcheck_endpoint_present = '"/postcheck"' in api_text
    payloads_endpoint_present = '"/payloads"' in api_text
    protected_ligand_heavy_review_endpoint_present = '"/protected-ligand-heavy-review"' in api_text
    protected_policy_endpoint_present = '"/protected-policy"' in api_text
    fail_closed_flags_present = all(token in api_text for token in ("delete_executed", "external_state_mutated", "delete_enabled"))

    rows = [
        _row(
            "cleanup_api_file_present",
            api_file_present,
            f"api/cleanup.py={api_file_present}",
            "api/cleanup.py exists",
            "api/cleanup.py",
            "Cleanup operations need a dedicated read-only API surface before operator-facing cleanup status can be inspected consistently.",
        ),
        _row(
            "cleanup_router_registered",
            router_registered,
            f"cleanup_router_registered={router_registered}",
            "api.main imports and includes cleanup_router",
            "api/main.py",
            "The cleanup API must be mounted into the FastAPI app, not only defined as a detached module.",
        ),
        _row(
            "cleanup_local_status_cli_present",
            local_status_cli_present,
            f"betelgeuze_cleanup/cli.py={local_status_cli_present}",
            "betelgeuze_cleanup/cli.py read-only local status surface present",
            "betelgeuze_cleanup/cli.py",
            "Cleanup decisions need a terminal-friendly read-only status surface in addition to the API.",
        ),
        _row(
            "cleanup_operations_endpoint_present",
            operations_endpoint_present,
            f"operations_endpoint={operations_endpoint_present}",
            "/cleanup/operations route present",
            "api/cleanup.py",
            "Operators need a consolidated cleanup operations endpoint before any cleanup execution decision.",
        ),
        _row(
            "cleanup_payloads_endpoint_present",
            payloads_endpoint_present,
            f"payloads_endpoint={payloads_endpoint_present}",
            "/cleanup/payloads route present",
            "api/cleanup.py",
            "Cleanup payload sizes and protected versus approval-gated rows need a read-only inspection surface.",
        ),
        _row(
            "cleanup_postcheck_endpoint_present",
            postcheck_endpoint_present,
            f"postcheck_endpoint={postcheck_endpoint_present}",
            "/cleanup/postcheck route present",
            "api/cleanup.py",
            "Approved cleanup rows need a read-only postcheck contract before cleanup completion can be claimed.",
        ),
        _row(
            "cleanup_completion_endpoint_present",
            completion_endpoint_present,
            f"completion_endpoint={completion_endpoint_present}",
            "/cleanup/completion route present",
            "api/cleanup.py",
            "Cleanup completion needs a direct read-only endpoint that exposes approval, postcheck, execution-completion, and protected-policy stages.",
        ),
        _row(
            "cleanup_approval_gate_endpoint_present",
            approval_gate_endpoint_present,
            f"approval_gate_endpoint={approval_gate_endpoint_present}",
            "/cleanup/approval-gate route present",
            "api/cleanup.py",
            "Operator cleanup approval needs a read-only surface for required columns, valid decisions, tokens, payload fingerprints, and gate rows before execution.",
        ),
        _row(
            "cleanup_protected_policy_endpoint_present",
            protected_policy_endpoint_present,
            f"protected_policy_endpoint={protected_policy_endpoint_present}",
            "/cleanup/protected-policy route present",
            "api/cleanup.py",
            "Protected cleanup rows require a separate policy-decision surface rather than accidental promotion to deletion approval.",
        ),
        _row(
            "cleanup_protected_ligand_heavy_review_endpoint_present",
            protected_ligand_heavy_review_endpoint_present,
            f"protected_ligand_heavy_review_endpoint={protected_ligand_heavy_review_endpoint_present}",
            "/cleanup/protected-ligand-heavy-review route present",
            "api/cleanup.py",
            "Protected ligand-heavy payload rows need a deep review surface that separates known payload children from preservation siblings.",
        ),
        _row(
            "cleanup_fail_closed_flags_present",
            fail_closed_flags_present,
            f"fail_closed_flags_present={fail_closed_flags_present}",
            "delete/execution/external-mutation flags returned as disabled",
            "api/cleanup.py",
            "The cleanup API must be visibly read-only and must not imply that deletion or external mutation happened.",
        ),
    ]
    blockers = [
        {
            "code": f"{row['check']}_not_ready",
            "severity": "hard",
            "check": row["check"],
            "reason": f"{row['reason']} Observed: {row['observed']}; required: {row['required']}.",
        }
        for row in rows
        if row["status"] != "pass"
    ]
    surface_ready = not blockers
    summary = {
        "packet_type": "cleanup_operations_surface_contract",
        "status": "cleanup_operations_surface_contract_ready" if surface_ready else "blocked_cleanup_operations_surface_contract",
        "surface_ready": surface_ready,
        "check_count": len(rows),
        "blocker_count": len(blockers),
        "cleanup_api_file_present": api_file_present,
        "cleanup_local_status_cli_present": local_status_cli_present,
        "cleanup_router_registered": router_registered,
        "cleanup_operations_endpoint_present": operations_endpoint_present,
        "cleanup_approval_gate_endpoint_present": approval_gate_endpoint_present,
        "cleanup_completion_endpoint_present": completion_endpoint_present,
        "cleanup_postcheck_endpoint_present": postcheck_endpoint_present,
        "cleanup_payloads_endpoint_present": payloads_endpoint_present,
        "cleanup_protected_ligand_heavy_review_endpoint_present": protected_ligand_heavy_review_endpoint_present,
        "cleanup_protected_policy_endpoint_present": protected_policy_endpoint_present,
        "cleanup_fail_closed_flags_present": fail_closed_flags_present,
        "execution_enabled": False,
        "delete_enabled": False,
        "delete_executed": False,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "Cleanup operations surface is ready; execution still requires row-specific operator approval and post-execution evidence."
            if surface_ready
            else "Repair failed cleanup API surface rows before treating cleanup operations as operator-visible."
        ),
    }
    return {"summary": summary, "blockers": blockers, "rows": rows}


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_markdown(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    s = payload["summary"]
    lines = [
        "# Cleanup Operations Surface Contract",
        "",
        f"- status: `{s['status']}`",
        f"- surface_ready: `{s['surface_ready']}`",
        f"- blocker_count: `{s['blocker_count']}`",
        f"- cleanup_api_file_present: `{s['cleanup_api_file_present']}`",
        f"- cleanup_local_status_cli_present: `{s['cleanup_local_status_cli_present']}`",
        f"- cleanup_router_registered: `{s['cleanup_router_registered']}`",
        f"- cleanup_operations_endpoint_present: `{s['cleanup_operations_endpoint_present']}`",
        f"- cleanup_approval_gate_endpoint_present: `{s['cleanup_approval_gate_endpoint_present']}`",
        f"- cleanup_completion_endpoint_present: `{s['cleanup_completion_endpoint_present']}`",
        f"- cleanup_postcheck_endpoint_present: `{s['cleanup_postcheck_endpoint_present']}`",
        f"- cleanup_payloads_endpoint_present: `{s['cleanup_payloads_endpoint_present']}`",
        f"- cleanup_protected_ligand_heavy_review_endpoint_present: `{s['cleanup_protected_ligand_heavy_review_endpoint_present']}`",
        f"- cleanup_protected_policy_endpoint_present: `{s['cleanup_protected_policy_endpoint_present']}`",
        f"- cleanup_fail_closed_flags_present: `{s['cleanup_fail_closed_flags_present']}`",
        f"- delete_executed: `{s['delete_executed']}`",
        f"- external_state_mutated: `{s['external_state_mutated']}`",
        "",
        "## Checks",
        "",
        "| check | status | observed | required | artifact | reason |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['check']}` | `{row['status']}` | `{row['observed']}` | "
            f"`{row['required']}` | `{row['artifact_path']}` | {row['reason']} |"
        )
    lines.extend(["", "## Claim Boundary", "", s["claim_boundary"], "", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a cleanup operations API surface contract without executing cleanup.")
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_cleanup_operations_surface_contract(root=args.root)
    _write_json(args.out_json, payload)
    write_csv_rows(_resolve(args.out_csv), payload["rows"])
    _write_markdown(args.out_md, payload)


if __name__ == "__main__":
    main()

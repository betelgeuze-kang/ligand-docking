#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT_JSON = "casp17/casp17_transition_surface_contract_current.json"
DEFAULT_OUT_CSV = "casp17/casp17_transition_surface_contract_current.csv"
DEFAULT_OUT_MD = "casp17/CASP17_TRANSITION_SURFACE_CONTRACT.md"

CLAIM_BOUNDARY = (
    "CASP17 transition surface contract only; it audits whether the repository exposes read-only CASP17 upload and "
    "transition status surfaces from local files. It does not enter operator decisions, serialize an author code, "
    "create final upload files, submit to CASP, compute native accuracy, delete, move, archive, externalize, upload, "
    "or mutate external state."
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
        "upload_executed": False,
        "delete_executed": False,
        "external_state_mutated": False,
    }


def build_casp17_transition_surface_contract(*, root: str | Path = ".") -> dict[str, Any]:
    root_path = Path(root).resolve()
    api_text = _file_text(root_path, "api/casp17.py")
    main_text = _file_text(root_path, "api/main.py")
    api_file_present = bool(api_text)
    router_registered = "casp17_router" in main_text and "app.include_router(casp17_router)" in main_text
    upload_endpoint_present = '"/upload"' in api_text
    transition_endpoint_present = '"/transition"' in api_text
    upload_artifacts_referenced = all(
        token in api_text
        for token in (
            "casp17_current_upload_decision_rule_gate_current.json",
            "casp17_current_upload_operator_action_runway_current.json",
            "casp17_current_upload_active_manifest_lock_current.json",
        )
    )
    cleanup_artifacts_referenced = all(
        token in api_text
        for token in (
            "large_cleanup_surface_drilldown_current.json",
            "protected_cleanup_payload_review_current.json",
        )
    )
    cleanup_gate_artifacts_referenced = all(
        token in api_text
        for token in (
            "cleanup_execution_approval_gate_current.json",
            "cleanup_postcheck_contract_current.json",
            "cleanup_completion_gate_current.json",
        )
    )
    fail_closed_flags_present = all(
        token in api_text
        for token in (
            "upload_executed",
            "delete_executed",
            "external_state_mutated",
            "native_accuracy_computed",
        )
    )

    rows = [
        _row(
            "casp17_api_file_present",
            api_file_present,
            f"api/casp17.py={api_file_present}",
            "api/casp17.py exists",
            "api/casp17.py",
            "CASP17 transition status needs a dedicated read-only API surface before upload and cleanup state can be inspected consistently.",
        ),
        _row(
            "casp17_router_registered",
            router_registered,
            f"casp17_router_registered={router_registered}",
            "api.main imports and includes casp17_router",
            "api/main.py",
            "The CASP17 API must be mounted into the FastAPI app, not only defined as a detached module.",
        ),
        _row(
            "casp17_upload_endpoint_present",
            upload_endpoint_present,
            f"upload_endpoint={upload_endpoint_present}",
            "/casp17/upload route present",
            "api/casp17.py",
            "Operators need a consolidated CASP17 current-upload status endpoint before any human upload decision.",
        ),
        _row(
            "casp17_transition_endpoint_present",
            transition_endpoint_present,
            f"transition_endpoint={transition_endpoint_present}",
            "/casp17/transition route present",
            "api/casp17.py",
            "CASP17 transition and cleanup state need one read-only inspection surface during the move to CAMEO/product validation.",
        ),
        _row(
            "casp17_upload_artifacts_referenced",
            upload_artifacts_referenced,
            f"upload_artifacts_referenced={upload_artifacts_referenced}",
            "decision-rule, action-runway, and active-manifest lock artifacts referenced",
            "api/casp17.py",
            "CASP17 upload status must be grounded in the existing fail-closed upload evidence packets.",
        ),
        _row(
            "casp17_cleanup_artifacts_referenced",
            cleanup_artifacts_referenced,
            f"cleanup_artifacts_referenced={cleanup_artifacts_referenced}",
            "large cleanup drilldown and protected cleanup review artifacts referenced",
            "api/casp17.py",
            "CASP17 transition status must expose the cleanup payload context without promoting deletion.",
        ),
        _row(
            "casp17_cleanup_gate_artifacts_referenced",
            cleanup_gate_artifacts_referenced,
            f"cleanup_gate_artifacts_referenced={cleanup_gate_artifacts_referenced}",
            "cleanup approval gate, postcheck contract, and completion gate artifacts referenced",
            "api/casp17.py",
            "CASP17 transition status must expose cleanup approval, postcheck, and completion gates before cleanup can be claimed.",
        ),
        _row(
            "casp17_fail_closed_flags_present",
            fail_closed_flags_present,
            f"fail_closed_flags_present={fail_closed_flags_present}",
            "upload/delete/native-accuracy/external-mutation flags returned as disabled",
            "api/casp17.py",
            "The CASP17 API must be visibly read-only and must not imply upload, deletion, or native-accuracy computation happened.",
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
        "packet_type": "casp17_transition_surface_contract",
        "status": "casp17_transition_surface_contract_ready" if surface_ready else "blocked_casp17_transition_surface_contract",
        "surface_ready": surface_ready,
        "check_count": len(rows),
        "blocker_count": len(blockers),
        "casp17_api_file_present": api_file_present,
        "casp17_router_registered": router_registered,
        "casp17_upload_endpoint_present": upload_endpoint_present,
        "casp17_transition_endpoint_present": transition_endpoint_present,
        "casp17_upload_artifacts_referenced": upload_artifacts_referenced,
        "casp17_cleanup_artifacts_referenced": cleanup_artifacts_referenced,
        "casp17_cleanup_gate_artifacts_referenced": cleanup_gate_artifacts_referenced,
        "casp17_fail_closed_flags_present": fail_closed_flags_present,
        "upload_executed": False,
        "delete_executed": False,
        "native_accuracy_computed": False,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "CASP17 transition surface is ready; operator decisions, author serialization, upload, and cleanup remain separately gated."
            if surface_ready
            else "Repair failed CASP17 transition API surface rows before treating CASP17 status as operator-visible."
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
        "# CASP17 Transition Surface Contract",
        "",
        f"- status: `{s['status']}`",
        f"- surface_ready: `{s['surface_ready']}`",
        f"- blocker_count: `{s['blocker_count']}`",
        f"- casp17_api_file_present: `{s['casp17_api_file_present']}`",
        f"- casp17_router_registered: `{s['casp17_router_registered']}`",
        f"- casp17_upload_endpoint_present: `{s['casp17_upload_endpoint_present']}`",
        f"- casp17_transition_endpoint_present: `{s['casp17_transition_endpoint_present']}`",
        f"- casp17_upload_artifacts_referenced: `{s['casp17_upload_artifacts_referenced']}`",
        f"- casp17_cleanup_artifacts_referenced: `{s['casp17_cleanup_artifacts_referenced']}`",
        f"- casp17_cleanup_gate_artifacts_referenced: `{s['casp17_cleanup_gate_artifacts_referenced']}`",
        f"- casp17_fail_closed_flags_present: `{s['casp17_fail_closed_flags_present']}`",
        f"- upload_executed: `{s['upload_executed']}`",
        f"- delete_executed: `{s['delete_executed']}`",
        f"- native_accuracy_computed: `{s['native_accuracy_computed']}`",
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
    parser = argparse.ArgumentParser(description="Build a CASP17 transition API surface contract without uploading or cleanup.")
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_casp17_transition_surface_contract(root=args.root)
    _write_json(args.out_json, payload)
    write_csv_rows(_resolve(args.out_csv), payload["rows"])
    _write_markdown(args.out_md, payload)


if __name__ == "__main__":
    main()

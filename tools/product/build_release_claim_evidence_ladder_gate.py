#!/usr/bin/env python3
"""Build the read-only release-claim evidence ladder gate artifact.

Produces ``runs/release_claim_evidence_ladder_gate_current.{json,md,csv}`` consumed by the
``/product/release-claim-evidence-ladder`` surface. Evaluates the three release-claim tiers
(``local_observed_green`` -> ``remote_green`` -> ``runtime_green``) in rank order, binds the
remote/runtime tiers to a GitHub ``workflow_run`` attributed to a supplied merge-commit SHA,
fails closed, and reuses the existing remote-green evidence machinery. Read-only accounting:
``execution_enabled=false``, ``external_state_mutated=false``, no approval token, writes only
under ``runs/``, opens no network requests, and never fabricates evidence.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
from pathlib import Path
from typing import Any

from tools.product.build_release_ci_remote_green_receipt import (
    build_release_ci_remote_green_receipt,
)
from tools.product.release_ci_remote_green_evidence_contract import (
    CONTRACT_SCHEMA_VERSION,
    EVIDENCE_INPUTS,  # noqa: F401 - re-exported for callers/tests; documents reused input specs.
    build_release_ci_remote_green_evidence_contract,  # noqa: F401 - reused contract surface.
    validate_release_ci_remote_green_evidence_files,  # noqa: F401 - reused validator surface.
    validate_release_ci_remote_green_evidence_payload,
)

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT_JSON = "runs/release_claim_evidence_ladder_gate_current.json"
DEFAULT_OUT_MD = "runs/release_claim_evidence_ladder_gate_current.md"
DEFAULT_OUT_CSV = "runs/release_claim_evidence_ladder_gate_current.csv"
DEFAULT_WORKFLOW_YML = ".github/workflows/product-image-smoke.yml"

SCHEMA_VERSION = "release_claim_evidence_ladder_gate_v1"

TIER_LOCAL = "local_observed_green"
TIER_REMOTE = "remote_green"
TIER_RUNTIME = "runtime_green"
TIER_ORDER = (TIER_LOCAL, TIER_REMOTE, TIER_RUNTIME)
TIER_RANK = {TIER_LOCAL: 1, TIER_REMOTE: 2, TIER_RUNTIME: 3}
NONE_CLAIM = "none"

CLAIM_BOUNDARY = (
    "Release-claim evidence ladder gate is read-only accounting. It consumes owner/CI-supplied "
    "evidence JSON, validates and attributes it to a merge-commit SHA, and writes only local "
    "ladder artifacts. It does not submit to GitHub, open network requests to mutate external "
    "state, dispatch workflows, change branch protection, create tags, deploy, publish, submit "
    "to CASP, or fabricate workflow-run or runtime-smoke evidence."
)


# --- Task 2.1: input helpers ------------------------------------------------------------


def _is_merge_commit_sha(value: Any) -> bool:
    text = str(value or "").strip()
    if len(text) != 40:
        return False
    try:
        int(text, 16)
    except ValueError:
        return False
    return True


def _read_json(root: Path, path_like: str | Path | None) -> Any:
    if not path_like:
        return None
    path = Path(path_like)
    if not path.is_absolute():
        path = root / path
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _workflow_run_records(payload: Any) -> list[dict[str, Any]]:
    """Normalize a GitHub workflow-runs payload to a list of run records."""
    if isinstance(payload, dict):
        runs = payload.get("workflow_runs")
        if isinstance(runs, list):
            return [run for run in runs if isinstance(run, dict)]
        return []
    if isinstance(payload, list):
        return [run for run in payload if isinstance(run, dict)]
    return []


def _completion_timestamp(record: dict[str, Any]) -> str:
    # Lexical ISO-8601 ordering is sufficient for tie-breaking; missing -> empty (sorts first).
    for key in ("run_completed_at", "updated_at", "completed_at", "created_at"):
        value = record.get(key)
        if isinstance(value, str) and value:
            return value
    return ""


# --- Task 2.2: workflow-run attribution -------------------------------------------------


def _attributed_run(records: list[dict[str, Any]], merge_commit_sha: str) -> dict[str, Any] | None:
    """Return the most-recently-completed Attributed_Run for the merge commit, or None.

    Attributed_Run := record where head_sha == merge_commit_sha (case-insensitive),
    status == "completed", and conclusion == "success". Mismatched head_sha records are
    Unattributed_Run and excluded. Ties broken by most recent completion timestamp.
    """
    target = str(merge_commit_sha or "").strip().lower()
    if not target:
        return None
    matches = [
        record
        for record in records
        if str(record.get("head_sha", "") or "").strip().lower() == target
        and str(record.get("status", "") or "").strip().lower() == "completed"
        and str(record.get("conclusion", "") or "").strip().lower() == "success"
    ]
    if not matches:
        return None
    return max(matches, key=_completion_timestamp)


# --- Task 3.1: per-tier result ----------------------------------------------------------


def _tier_result(
    tier: str,
    *,
    supported: bool,
    attributed_run: dict[str, Any] | None = None,
    block_reason: str = "",
    validation_error: str = "",
) -> dict[str, Any]:
    run = attributed_run if (supported and attributed_run) else {}
    return {
        "tier": tier,
        "rank": TIER_RANK[tier],
        "result": "supported" if supported else "not_supported",
        "workflow_run_id": run.get("id") if run else None,
        "head_sha": run.get("head_sha") if run else None,
        "block_reason": "" if supported else (block_reason or "not_supported"),
        "validation_error": validation_error,
    }


# --- Task 3.2: local_observed_green -----------------------------------------------------


def _evaluate_local(local_payload: Any) -> dict[str, Any]:
    if local_payload is None:
        return _tier_result(TIER_LOCAL, supported=False, block_reason="missing_evidence")
    if not isinstance(local_payload, dict) or not local_payload:
        return _tier_result(TIER_LOCAL, supported=False, block_reason="validation_error",
                            validation_error="local_evidence_not_object_or_empty")
    # Supported when the local evidence explicitly reports success.
    success = (
        local_payload.get("pass") is True
        or local_payload.get("local_observed_green") is True
        or str(local_payload.get("status", "")).strip().endswith("_green")
        or str(local_payload.get("status", "")).strip() == "local_observed_green_ready"
    )
    if not success:
        return _tier_result(TIER_LOCAL, supported=False, block_reason="evidence_not_green")
    return _tier_result(TIER_LOCAL, supported=True)


# --- Task 3.3: remote_green -------------------------------------------------------------


def _evaluate_remote(
    *,
    root: Path,
    merge_commit_sha: str,
    remote_runs_payload: Any,
    receipt_inputs: dict[str, Any],
) -> tuple[dict[str, Any], str]:
    receipt = build_release_ci_remote_green_receipt(root=root, **receipt_inputs)
    receipt_status = str(receipt["summary"].get("status", ""))
    receipt_pass = receipt["summary"].get("pass") is True
    if not receipt_pass:
        return (
            _tier_result(TIER_REMOTE, supported=False, block_reason="remote_receipt_blocked"),
            receipt_status,
        )
    if not _is_merge_commit_sha(merge_commit_sha):
        return (
            _tier_result(TIER_REMOTE, supported=False, block_reason="invalid_merge_commit_sha"),
            receipt_status,
        )
    run = _attributed_run(_workflow_run_records(remote_runs_payload), merge_commit_sha)
    if run is None:
        return (
            _tier_result(TIER_REMOTE, supported=False, block_reason="unattributed"),
            receipt_status,
        )
    return _tier_result(TIER_REMOTE, supported=True, attributed_run=run), receipt_status


# --- Task 3.4: runtime_green ------------------------------------------------------------


def _evaluate_runtime(*, merge_commit_sha: str, runtime_runs_payload: Any) -> dict[str, Any]:
    if runtime_runs_payload is None:
        return _tier_result(TIER_RUNTIME, supported=False, block_reason="missing_evidence")
    if not _is_merge_commit_sha(merge_commit_sha):
        return _tier_result(TIER_RUNTIME, supported=False, block_reason="invalid_merge_commit_sha")
    run = _attributed_run(_workflow_run_records(runtime_runs_payload), merge_commit_sha)
    if run is None:
        return _tier_result(TIER_RUNTIME, supported=False, block_reason="unattributed")
    return _tier_result(TIER_RUNTIME, supported=True, attributed_run=run)


# --- Task 4: ladder ranking -------------------------------------------------------------


def _rank_ladder(tier_results: dict[str, dict[str, Any]]) -> tuple[str, list[str]]:
    highest = NONE_CLAIM
    gaps: list[str] = []
    stopped = False
    for tier in TIER_ORDER:  # ascending rank
        if tier_results[tier]["result"] == "supported" and not stopped:
            highest = tier
            continue
        stopped = True
        for higher in TIER_ORDER:
            if (
                TIER_RANK[higher] > TIER_RANK[tier]
                and tier_results[higher]["result"] == "supported"
            ):
                gaps.append(f"{higher}_supported_but_{tier}_not_supported")
        break
    return highest, gaps


# --- Task 5: assemble -------------------------------------------------------------------


def build_release_claim_evidence_ladder_gate(
    *,
    root: str | Path = ROOT,
    merge_commit_sha: str = "",
    local_evidence_json: str | Path | None = "",
    remote_runs_json: str | Path | None = "",
    runtime_runs_json: str | Path | None = "",
    runner_inventory_json: str | Path | None = "",
    branch_json: str | Path | None = "",
    required_checks_json: str | Path | None = "",
    schedule_runs_json: str | Path | None = "",
    failed_run_artifacts_json: str | Path | None = "",
    release_tag_runs_json: str | Path | None = "",
    workflow_yml: str | Path | None = DEFAULT_WORKFLOW_YML,
) -> dict[str, Any]:
    root_path = Path(root)
    sha = str(merge_commit_sha or "").strip()
    sha_valid = _is_merge_commit_sha(sha)

    local_payload = _read_json(root_path, local_evidence_json)
    remote_runs_payload = _read_json(root_path, remote_runs_json)
    runtime_runs_payload = _read_json(root_path, runtime_runs_json)

    receipt_inputs = {
        "runner_inventory_json": runner_inventory_json,
        "branch_json": branch_json,
        "required_checks_json": required_checks_json,
        "schedule_runs_json": schedule_runs_json,
        "failed_run_artifacts_json": failed_run_artifacts_json,
        "release_tag_runs_json": release_tag_runs_json,
        "workflow_yml": workflow_yml,
    }

    local_result = _evaluate_local(local_payload)
    remote_result, remote_receipt_status = _evaluate_remote(
        root=root_path,
        merge_commit_sha=sha,
        remote_runs_payload=remote_runs_payload,
        receipt_inputs=receipt_inputs,
    )
    runtime_result = _evaluate_runtime(
        merge_commit_sha=sha,
        runtime_runs_payload=runtime_runs_payload,
    )

    tier_results = {
        TIER_LOCAL: local_result,
        TIER_REMOTE: remote_result,
        TIER_RUNTIME: runtime_result,
    }
    highest, gaps = _rank_ladder(tier_results)
    runtime_claim_allowed = highest == TIER_RUNTIME

    tiers = [tier_results[tier] for tier in TIER_ORDER]
    blockers = [
        {
            "tier": tier_results[tier]["tier"],
            "code": tier_results[tier]["block_reason"],
            "observed": tier_results[tier].get("validation_error") or tier_results[tier]["result"],
        }
        for tier in TIER_ORDER
        if tier_results[tier]["result"] != "supported"
    ]

    status = (
        "release_claim_evidence_ladder_ready"
        if highest == TIER_RUNTIME
        else "blocked_release_claim_evidence_ladder"
    )
    if highest == TIER_RUNTIME:
        next_step = "All ladder tiers attributed and green; runtime claim allowed."
    elif not sha_valid:
        next_step = (
            "Supply a valid 40-hex merge_commit_sha and attributed workflow-run evidence for the "
            "remote/runtime tiers, then rebuild this gate."
        )
    else:
        next_step = (
            "Supply attributed (head_sha == merge_commit_sha, completed/success) workflow-run "
            "evidence for the highest blocked tier, then rebuild this gate."
        )

    summary = {
        "packet_type": "release_claim_evidence_ladder_gate",
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "merge_commit_sha": sha,
        "merge_commit_sha_valid": sha_valid,
        "highest_supported_claim": highest,
        "runtime_claim_allowed": runtime_claim_allowed,
        "local_observed_green_supported": local_result["result"] == "supported",
        "remote_green_supported": remote_result["result"] == "supported",
        "runtime_green_supported": runtime_result["result"] == "supported",
        "contiguity_gap_count": len(gaps),
        "contiguity_gaps": gaps,
        "remote_green_receipt_status": remote_receipt_status or "not_evaluated",
        "evidence_contract_schema_version": CONTRACT_SCHEMA_VERSION,
        "blocker_count": len(blockers),
        "execution_enabled": False,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": next_step,
    }
    return {"summary": summary, "tiers": tiers, "blockers": blockers}


# --- Task 6: deterministic, fail-closed writers -----------------------------------------


def _resolve(root: Path, path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else root / path


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n"
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def _write_csv(path: Path, tiers: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    columns = ["tier", "rank", "result", "workflow_run_id", "head_sha", "block_reason"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for tier in tiers:
            writer.writerow({col: ("" if tier.get(col) is None else tier.get(col)) for col in columns})


def _render_md(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# Release Claim Evidence Ladder Gate",
        "",
        f"- status: `{summary['status']}`",
        f"- merge_commit_sha: `{summary['merge_commit_sha'] or '(none)'}`",
        f"- highest_supported_claim: `{summary['highest_supported_claim']}`",
        f"- runtime_claim_allowed: `{summary['runtime_claim_allowed']}`",
        f"- evidence_contract_schema_version: `{summary['evidence_contract_schema_version']}`",
        f"- remote_green_receipt_status: `{summary['remote_green_receipt_status']}`",
        f"- execution_enabled: `{summary['execution_enabled']}`",
        f"- external_state_mutated: `{summary['external_state_mutated']}`",
        "",
        "## Tiers",
        "",
        "| tier | rank | result | workflow_run_id | head_sha | block_reason |",
        "| --- | ---: | --- | --- | --- | --- |",
    ]
    for tier in payload["tiers"]:
        lines.append(
            f"| `{tier['tier']}` | `{tier['rank']}` | `{tier['result']}` | "
            f"`{tier.get('workflow_run_id')}` | `{tier.get('head_sha')}` | `{tier['block_reason']}` |"
        )
    lines += ["", "## Claim Boundary", "", summary["claim_boundary"], ""]
    return "\n".join(lines)


def write_outputs(
    payload: dict[str, Any],
    *,
    root: str | Path = ROOT,
    out_json: str | Path = DEFAULT_OUT_JSON,
    out_md: str | Path = DEFAULT_OUT_MD,
    out_csv: str | Path = DEFAULT_OUT_CSV,
) -> None:
    root_path = Path(root)
    _write_json_atomic(_resolve(root_path, out_json), payload)
    _write_csv(_resolve(root_path, out_csv), payload["tiers"])
    _resolve(root_path, out_md).write_text(_render_md(payload), encoding="utf-8")


# --- Task 7: CLI ------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build read-only release-claim evidence ladder gate artifact."
    )
    parser.add_argument("--merge-commit-sha", default="")
    parser.add_argument("--local-evidence-json", default="")
    parser.add_argument("--remote-runs-json", default="")
    parser.add_argument("--runtime-runs-json", default="")
    parser.add_argument("--runner-inventory-json", default="")
    parser.add_argument("--branch-json", default="")
    parser.add_argument("--required-checks-json", default="")
    parser.add_argument("--schedule-runs-json", default="")
    parser.add_argument("--failed-run-artifacts-json", default="")
    parser.add_argument("--release-tag-runs-json", default="")
    parser.add_argument("--workflow-yml", default=DEFAULT_WORKFLOW_YML)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    args = parser.parse_args(argv)

    payload = build_release_claim_evidence_ladder_gate(
        merge_commit_sha=args.merge_commit_sha,
        local_evidence_json=args.local_evidence_json,
        remote_runs_json=args.remote_runs_json,
        runtime_runs_json=args.runtime_runs_json,
        runner_inventory_json=args.runner_inventory_json,
        branch_json=args.branch_json,
        required_checks_json=args.required_checks_json,
        schedule_runs_json=args.schedule_runs_json,
        failed_run_artifacts_json=args.failed_run_artifacts_json,
        release_tag_runs_json=args.release_tag_runs_json,
        workflow_yml=args.workflow_yml,
    )
    write_outputs(payload, out_json=args.out_json, out_md=args.out_md, out_csv=args.out_csv)
    print(json.dumps(payload["summary"], indent=2, ensure_ascii=False, sort_keys=True))
    return 0 if payload["summary"]["status"] == "release_claim_evidence_ladder_ready" else 1


if __name__ == "__main__":
    raise SystemExit(main())

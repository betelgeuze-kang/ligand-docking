#!/usr/bin/env python3
"""Release claim evidence-ladder decision gate (read-only).

Implements the ladder described in ``docs/release_claim_evidence_ladder.md``:
local green is not remote green, and remote green is not runtime green. The gate
keeps the three rungs strictly separate and is fail-closed — it never lets a
lower rung satisfy a higher claim, and it never *infers* remote-green for a
``main`` HEAD that has no associated product-image workflow run.

Inputs (all read-only JSON the caller supplies; nothing is fetched or mutated):

- ``local_receipt_json``  — Rung 1. A locally produced receipt. To count, it
  must be green AND explicitly self-labelled ``"evidence_scope":
  "local_observed"`` so a local receipt can never masquerade as remote.
- ``remote_receipt_json`` — Rung 2/3 signals. The output of
  ``build_release_ci_remote_green_receipt`` (its ``summary``).
- ``head_runs_json``      — workflow runs (read-only) used to attribute a
  product-image run to the current ``main`` HEAD (``main_head_sha``). This is
  what closes the "merge commit with no workflow run" gap.

Output: ``{"summary": {...}, "rows": [...], "blockers": [...]}``.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT_JSON = "runs/release_claim_evidence_ladder_gate_current.json"
DEFAULT_OUT_MD = "runs/release_claim_evidence_ladder_gate_current.md"

CLAIM_BOUNDARY = (
    "Release claim evidence-ladder gate only evaluates read-only receipts and workflow-run JSON supplied by the "
    "caller. It separates local-observed, remote-green, and runtime-green evidence and refuses to promote a claim "
    "above its evidence. It does not run tests, dispatch workflows, attribute runs it cannot see, deploy, publish, "
    "or mutate external state."
)

# Ladder rungs, lowest to highest.
CLAIM_NONE = "none"
CLAIM_LOCAL_ONLY = "local_only"
CLAIM_REMOTE_GREEN = "remote_green"
CLAIM_RUNTIME_GREEN = "runtime_green"


def _resolve(root: Path, path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else root / path


def _read_json(root: Path, path_like: str | Path | None) -> Any:
    if not path_like:
        return {}
    path = _resolve(root, path_like)
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(ROOT, path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_markdown(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(ROOT, path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    summary = payload["summary"]
    promotion = summary["claim_promotion"]
    lines = [
        "# Release Claim Evidence Ladder Gate",
        "",
        f"- status: `{summary['status']}`",
        f"- highest_supported_claim: `{summary['highest_supported_claim']}`",
        "",
        "## Rungs",
        "",
        f"- local_observed_green: `{summary['local_observed_green']}`",
        f"- remote_green: `{summary['remote_green']}`",
        f"- merge_commit_workflow_run_present: `{summary['merge_commit_workflow_run_present']}`",
        f"- remote_green_attributable_to_head: `{summary['remote_green_attributable_to_head']}`",
        f"- runtime_green: `{summary['runtime_green']}`",
        "",
        "## Claim promotion (fail-closed)",
        "",
        f"- tests_pass_locally: `{promotion['tests_pass_locally']}`",
        f"- ci_wired_and_green_on_main: `{promotion['ci_wired_and_green_on_main']}`",
        f"- runtime_or_production_claim: `{promotion['runtime_or_production_claim']}`",
        "",
        "## Blockers",
        "",
    ]
    blockers = payload.get("blockers") or []
    if blockers:
        lines.extend(f"- `{row['code']}`: {row['detail']}" for row in blockers)
    else:
        lines.append("- none")
    lines.extend(["", "## Next required step", "", f"- {summary['next_required_step']}", ""])
    lines.extend(["## Claim Boundary", "", summary["claim_boundary"], ""])
    path.write_text("\n".join(lines), encoding="utf-8")


def _as_list(payload: Any, key: str) -> list[Any]:
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict) and isinstance(payload.get(key), list):
        return list(payload[key])
    return []


def _is_local_observed_green(local_receipt: Any) -> tuple[bool, bool, bool]:
    """Return (green, scope_labeled_local, claims_green).

    A local receipt only counts as Rung 1 evidence when it is both green and
    explicitly scoped ``local_observed`` (honest labelling).
    """

    if not isinstance(local_receipt, dict):
        return False, False, False
    summary = local_receipt.get("summary") if isinstance(local_receipt.get("summary"), dict) else local_receipt
    scope = str(summary.get("evidence_scope") or local_receipt.get("evidence_scope") or "")
    scope_labeled_local = scope == "local_observed"
    status = str(summary.get("status") or "")
    claims_green = (
        summary.get("green") is True
        or summary.get("pass") is True
        or status.endswith("ready")
        or status.endswith("green")
    )
    return bool(scope_labeled_local and claims_green), scope_labeled_local, bool(claims_green)


def _remote_summary(remote_receipt: Any) -> dict[str, Any]:
    if isinstance(remote_receipt, dict) and isinstance(remote_receipt.get("summary"), dict):
        return remote_receipt["summary"]
    return remote_receipt if isinstance(remote_receipt, dict) else {}


def _product_image_runs_for_head(head_runs_payload: Any, head_sha: str) -> tuple[bool, bool]:
    """Return (run_present_for_head, run_green_for_head).

    Only runs whose ``head_sha`` matches the current ``main`` HEAD count, so a
    green run on some *other* commit cannot be claimed for this merge.
    """

    head_sha = str(head_sha or "")
    present = False
    green = False
    for run in _as_list(head_runs_payload, "workflow_runs"):
        if not isinstance(run, dict):
            continue
        run_head = str(run.get("head_sha") or run.get("head_commit_sha") or "")
        if not head_sha or run_head != head_sha:
            continue
        name_text = " ".join(str(run.get(key) or "") for key in ("name", "display_title", "workflow_name", "path")).lower()
        if "product-image" not in name_text and "product image" not in name_text:
            continue
        present = True
        if str(run.get("status") or "").lower() == "completed" and str(run.get("conclusion") or "").lower() == "success":
            green = True
    return present, green


def _row(check_id: str, passed: bool, observed: Any, required: str, source: str) -> dict[str, Any]:
    return {
        "check_id": check_id,
        "passed": bool(passed),
        "observed": observed,
        "required": required,
        "source": source,
        "external_state_mutated": False,
    }


def build_release_claim_evidence_ladder_gate(
    *,
    root: str | Path = ROOT,
    local_receipt_json: str | Path | None = "",
    remote_receipt_json: str | Path | None = "",
    head_runs_json: str | Path | None = "",
    main_head_sha: str = "",
) -> dict[str, Any]:
    root_path = Path(root)
    local_receipt = _read_json(root_path, local_receipt_json)
    remote_receipt = _read_json(root_path, remote_receipt_json)
    head_runs = _read_json(root_path, head_runs_json)

    # --- Rung 1: local-observed green ---
    local_observed_green, local_scope_labeled, local_claims_green = _is_local_observed_green(local_receipt)

    # --- Rung 2: remote green (GitHub Actions wired + green) ---
    remote = _remote_summary(remote_receipt)
    remote_green = remote.get("pass") is True or str(remote.get("status") or "") == "release_ci_remote_green_ready"

    # Head attribution: does THIS main HEAD have a product-image workflow run?
    merge_commit_workflow_run_present, head_run_green = _product_image_runs_for_head(head_runs, main_head_sha)
    remote_green_attributable_to_head = bool(remote_green and merge_commit_workflow_run_present and head_run_green)

    # --- Rung 3: runtime green (ROCm runtime executed + green on a GPU runner) ---
    rocm_runner_ready = remote.get("rocm_self_hosted_runner_ready") is True
    rocm_runtime_run_green = remote.get("release_tag_rocm_gate_green") is True or remote.get("weekly_rocm_schedule_green") is True
    runtime_green = bool(rocm_runner_ready and rocm_runtime_run_green and remote_green_attributable_to_head)

    # --- Monotonic claim promotion (fail-closed) ---
    tests_pass_locally = local_observed_green
    ci_wired_and_green_on_main = bool(tests_pass_locally and remote_green and remote_green_attributable_to_head)
    runtime_or_production_claim = bool(ci_wired_and_green_on_main and runtime_green)

    if runtime_or_production_claim:
        highest_supported_claim = CLAIM_RUNTIME_GREEN
    elif ci_wired_and_green_on_main:
        highest_supported_claim = CLAIM_REMOTE_GREEN
    elif tests_pass_locally:
        highest_supported_claim = CLAIM_LOCAL_ONLY
    else:
        highest_supported_claim = CLAIM_NONE

    rows = [
        _row(
            "local_observed_green",
            local_observed_green,
            {"scope_labeled_local": local_scope_labeled, "claims_green": local_claims_green},
            "local receipt is green AND explicitly scoped evidence_scope=local_observed",
            str(local_receipt_json or ""),
        ),
        _row(
            "remote_ci_green",
            remote_green,
            {"status": remote.get("status"), "pass": remote.get("pass")},
            "release_ci_remote_green_receipt reports pass",
            str(remote_receipt_json or ""),
        ),
        _row(
            "merge_commit_workflow_run_present",
            merge_commit_workflow_run_present,
            {"main_head_sha": main_head_sha, "run_present": merge_commit_workflow_run_present},
            "a product-image workflow run exists for the current main HEAD sha",
            str(head_runs_json or ""),
        ),
        _row(
            "remote_green_attributable_to_head",
            remote_green_attributable_to_head,
            {"remote_green": remote_green, "head_run_green": head_run_green},
            "remote CI is green AND a successful product-image run is attributable to the main HEAD",
            f"{remote_receipt_json};{head_runs_json}",
        ),
        _row(
            "runtime_green",
            runtime_green,
            {"rocm_self_hosted_runner_ready": rocm_runner_ready, "rocm_runtime_run_green": rocm_runtime_run_green},
            "ROCm runtime ran green on a self-hosted GPU runner AND is attributable to the main HEAD",
            str(remote_receipt_json or ""),
        ),
    ]

    # Blockers describe the gap to the NEXT rung above the highest supported claim.
    blockers: list[dict[str, Any]] = []
    if not tests_pass_locally:
        if not local_scope_labeled:
            blockers.append({"code": "local_observed_green", "detail": "local receipt missing evidence_scope=local_observed (honest-labelling required)"})
        else:
            blockers.append({"code": "local_observed_green", "detail": "local receipt is not green"})
    elif not ci_wired_and_green_on_main:
        if not remote_green:
            blockers.append({"code": "remote_ci_green", "detail": "remote CI receipt is not green"})
        if not merge_commit_workflow_run_present:
            blockers.append({"code": "merge_commit_workflow_run_present", "detail": "current main HEAD has no product-image workflow run; remote-green must not be inferred"})
        elif not head_run_green:
            blockers.append({"code": "remote_green_attributable_to_head", "detail": "product-image run for main HEAD did not complete successfully"})
    elif not runtime_or_production_claim:
        if not rocm_runner_ready:
            blockers.append({"code": "runtime_green", "detail": "no online self-hosted ROCm runner in remote evidence"})
        if not rocm_runtime_run_green:
            blockers.append({"code": "runtime_green", "detail": "no green ROCm runtime run (weekly schedule or release tag)"})

    next_required_step = {
        CLAIM_RUNTIME_GREEN: "Full ladder green: local, remote, and runtime evidence are present and attributable. Runtime/production claim is supported.",
        CLAIM_REMOTE_GREEN: "Remote CI green and attributable to HEAD. To support a runtime/production claim, obtain a green ROCm runtime run on a self-hosted GPU runner.",
        CLAIM_LOCAL_ONLY: "Only local-observed green. To claim CI green on main, ensure remote CI passes AND a product-image run is attributable to the current main HEAD.",
        CLAIM_NONE: "No honest claim yet. Produce a green, local_observed-scoped local receipt first.",
    }[highest_supported_claim]

    summary = {
        "packet_type": "release_claim_evidence_ladder_gate",
        "schema_version": "release_claim_evidence_ladder_v1",
        "status": "release_claim_ladder_ready" if runtime_or_production_claim else "blocked_release_claim_ladder",
        "pass": runtime_or_production_claim,
        "highest_supported_claim": highest_supported_claim,
        "local_observed_green": local_observed_green,
        "remote_green": remote_green,
        "merge_commit_workflow_run_present": merge_commit_workflow_run_present,
        "remote_green_attributable_to_head": remote_green_attributable_to_head,
        "runtime_green": runtime_green,
        "claim_promotion": {
            "tests_pass_locally": tests_pass_locally,
            "ci_wired_and_green_on_main": ci_wired_and_green_on_main,
            "runtime_or_production_claim": runtime_or_production_claim,
        },
        "blocker_count": len(blockers),
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": next_required_step,
    }
    return {"summary": summary, "rows": rows, "blockers": blockers}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build read-only release claim evidence-ladder gate.")
    parser.add_argument("--local-receipt-json", default="")
    parser.add_argument("--remote-receipt-json", default="")
    parser.add_argument("--head-runs-json", default="")
    parser.add_argument("--main-head-sha", default="")
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    args = parser.parse_args(argv)
    payload = build_release_claim_evidence_ladder_gate(
        local_receipt_json=args.local_receipt_json,
        remote_receipt_json=args.remote_receipt_json,
        head_runs_json=args.head_runs_json,
        main_head_sha=args.main_head_sha,
    )
    _write_json(args.out_json, payload)
    _write_markdown(args.out_md, payload)
    return 0 if payload["summary"]["pass"] else 2


if __name__ == "__main__":
    raise SystemExit(main())

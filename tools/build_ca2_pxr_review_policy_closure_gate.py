#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

DEFAULT_CA2_CAPTURE_JSON = "runs/ca2_negative_evidence_capture_intake_current.json"
DEFAULT_CA2_COMMIT_JSON = "runs/ca2_evidence_closure_commit_packet_current.json"
DEFAULT_PXR_CAPTURE_JSON = "runs/pxr_unresolved_evidence_capture_intake_current.json"
DEFAULT_PXR_COMMIT_JSON = "runs/pxr_pending_resolution_commit_packet_current.json"
DEFAULT_OUT_JSON = "runs/ca2_pxr_review_policy_closure_gate_current.json"
DEFAULT_OUT_CSV = "runs/ca2_pxr_review_policy_closure_gate_current.csv"
DEFAULT_OUT_MD = "runs/ca2_pxr_review_policy_closure_gate_current.md"


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    if path.is_absolute():
        return path
    cwd_path = (Path.cwd() / path).resolve()
    if cwd_path.exists():
        return cwd_path
    return (ROOT / path).resolve()


def _load_json(path_like: str | Path) -> dict[str, Any]:
    with _resolve(path_like).open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _summary(payload: dict[str, Any]) -> dict[str, Any]:
    return dict(payload.get("summary", {}) or {})


def _text(value: Any) -> str:
    return str(value or "").strip()


def _int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    return _text(value).lower() in {"1", "true", "yes", "ok", "pass", "passed"}


def _family_gate(
    family: str,
    capture_summary: dict[str, Any],
    commit_summary: dict[str, Any],
) -> dict[str, Any]:
    validation_error_count = _int(capture_summary.get("validation_error_count"))
    pending_capture_count = _int(capture_summary.get("pending_capture_count"))
    pending_manual_commit_count = _int(commit_summary.get("pending_manual_commit_count"))
    commit_row_count = _int(
        commit_summary.get("commit_row_count", capture_summary.get("confirmed_commit_count", 0))
    )
    confirmed_manual_commit_count = _int(commit_summary.get("confirmed_manual_commit_count"))
    manual_commit_closed = commit_row_count > 0 and confirmed_manual_commit_count >= commit_row_count
    review_only_policy = (
        _bool(capture_summary.get("review_only_conflict_or_gap_only"))
        or _int(commit_summary.get("review_only_row_count")) > 0
        or _int(commit_summary.get("defer_row_count")) > 0
        or _text(commit_summary.get("closure_mode")) == "review_only_conflict_closure"
    )
    binder_gap_count = _int(commit_summary.get("binder_gap_count"))
    closure_allowed = bool(
        validation_error_count == 0
        and pending_capture_count == 0
        and pending_manual_commit_count == 0
        and manual_commit_closed
        and review_only_policy
        and binder_gap_count == 0
    )
    locked_row_count = max(
        _int(commit_summary.get("ready_for_apply_row_count")),
        confirmed_manual_commit_count,
        _int(commit_summary.get("confirm_now_row_count")),
        _int(commit_summary.get("review_only_row_count")) + _int(commit_summary.get("defer_row_count")),
    )
    return {
        "family": family,
        "policy_gate_status": "review_only_policy_closed" if closure_allowed else "review_only_policy_open",
        "closure_allowed": closure_allowed,
        "commit_row_count": commit_row_count,
        "confirmed_manual_commit_count": confirmed_manual_commit_count,
        "locked_review_policy_row_count": locked_row_count,
        "validation_error_count": validation_error_count,
        "pending_capture_count": pending_capture_count,
        "pending_manual_commit_count": pending_manual_commit_count,
        "binder_gap_count": binder_gap_count,
        "review_only_policy": review_only_policy,
        "authoritative_negative_closure_allowed": _bool(
            capture_summary.get("authoritative_negative_closure_allowed")
        ),
        "promotion_allowed": False,
        "next_required_action": (
            "keep_review_only_policy_locked; do not promote these rows as authoritative binders/non-binders"
            if closure_allowed
            else "resolve validation, pending capture, manual commit, or binder gap before closing review-only policy"
        ),
    }


def build_payload(
    ca2_capture_payload: dict[str, Any],
    ca2_commit_payload: dict[str, Any],
    pxr_capture_payload: dict[str, Any],
    pxr_commit_payload: dict[str, Any],
) -> dict[str, Any]:
    rows = [
        _family_gate("ca2", _summary(ca2_capture_payload), _summary(ca2_commit_payload)),
        _family_gate("pxr", _summary(pxr_capture_payload), _summary(pxr_commit_payload)),
    ]
    unresolved = [row for row in rows if not row["closure_allowed"]]
    locked_count = sum(_int(row.get("locked_review_policy_row_count")) for row in rows)
    summary = {
        "policy_gate_ready": True,
        "packet_artifact": "runs/ca2_pxr_review_policy_closure_gate_current.md",
        "family_count": len(rows),
        "families_closed_count": len(rows) - len(unresolved),
        "review_only_policy_locked_row_count": locked_count,
        "unresolved_policy_family_count": len(unresolved),
        "promotion_allowed_count": 0,
        "review_only_policy_closure_allowed": not unresolved,
        "next_required_step": (
            "CA2/PXR review-only/defer evidence policy is closed for commercialization accounting; keep rows locked out of authoritative promotion."
            if not unresolved
            else "Resolve CA2/PXR policy-gate failures before removing the review-only evidence policy blocker."
        ),
    }
    return {"summary": summary, "rows": rows}


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# CA2/PXR Review Policy Closure Gate",
        "",
        f"- policy_gate_ready: `{s['policy_gate_ready']}`",
        f"- families_closed_count: `{s['families_closed_count']}`",
        f"- review_only_policy_locked_row_count: `{s['review_only_policy_locked_row_count']}`",
        f"- unresolved_policy_family_count: `{s['unresolved_policy_family_count']}`",
        f"- promotion_allowed_count: `{s['promotion_allowed_count']}`",
        f"- review_only_policy_closure_allowed: `{s['review_only_policy_closure_allowed']}`",
        "",
        "## Next Step",
        "",
        f"- {s['next_required_step']}",
        "",
        "## Rows",
        "",
        "| family | policy_gate_status | locked_review_policy_row_count | confirmed_manual_commit_count | pending_capture_count | pending_manual_commit_count | binder_gap_count |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['family']}` | `{row['policy_gate_status']}` | {row['locked_review_policy_row_count']} | "
            f"{row['confirmed_manual_commit_count']} | {row['pending_capture_count']} | "
            f"{row['pending_manual_commit_count']} | {row['binder_gap_count']} |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build CA2/PXR review-only policy closure gate.")
    parser.add_argument("--ca2-capture-json", default=DEFAULT_CA2_CAPTURE_JSON)
    parser.add_argument("--ca2-commit-json", default=DEFAULT_CA2_COMMIT_JSON)
    parser.add_argument("--pxr-capture-json", default=DEFAULT_PXR_CAPTURE_JSON)
    parser.add_argument("--pxr-commit-json", default=DEFAULT_PXR_COMMIT_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        _load_json(args.ca2_capture_json),
        _load_json(args.ca2_commit_json),
        _load_json(args.pxr_capture_json),
        _load_json(args.pxr_commit_json),
    )
    out_json = _resolve(args.out_json)
    out_csv = _resolve(args.out_csv)
    out_md = _resolve(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    _write_csv(out_csv, payload["rows"])
    _write_markdown(out_md, payload)


if __name__ == "__main__":
    main()

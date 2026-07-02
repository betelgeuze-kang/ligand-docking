#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]

DEFAULT_WORK_ORDER_JSON = ".betelgeuze/developer_preview_new_user_execution_work_order.json"
DEFAULT_PREFLIGHT_JSON = ".betelgeuze/developer_preview_new_user_execution_preflight.json"
DEFAULT_OUT_JSON = ".betelgeuze/developer_preview_new_user_observation_receipt.json"
DEFAULT_OUT_MD = ".betelgeuze/developer_preview_new_user_observation_receipt.md"

PACKET_TYPE = "developer_preview_new_user_observation_receipt"
SCHEMA_VERSION = "developer_preview_new_user_observation_receipt_v1"

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


def build_developer_preview_new_user_observation_receipt(
    *,
    work_order_json: str | Path = DEFAULT_WORK_ORDER_JSON,
    preflight_json: str | Path = DEFAULT_PREFLIGHT_JSON,
    observer_id: str = "",
    observed_at_utc: str = "",
    anonymized_summary: str = "",
    observer_signoff: bool = False,
    anonymized_notes_only: bool = False,
    hidden_state_blockers: list[str] | None = None,
    root: Path = ROOT,
) -> dict[str, Any]:
    work_order = _summary(_read_json(work_order_json, root=root))
    preflight = _summary(_read_json(preflight_json, root=root))
    hidden_blockers = _split_hidden_blockers(hidden_state_blockers)

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

    blockers: list[str] = []
    if not work_order:
        blockers.append(f"{_display(work_order_json, root=root)}:missing")
    elif not work_order_ready:
        blockers.append(f"{_display(work_order_json, root=root)}:work_order_not_ready")
    if not preflight:
        blockers.append(f"{_display(preflight_json, root=root)}:missing")
    elif not preflight_ready:
        blockers.append(f"{_display(preflight_json, root=root)}:preflight_not_ready")
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

    ready = (
        work_order_ready
        and preflight_ready
        and reviewer_present
        and observed_at_present
        and observer_signoff
        and anonymized_notes_only
        and anonymized_summary_present
        and hidden_state_blocker_count == 0
    )

    rows = [
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
            "check": "observer_review",
            "status": "pass" if ready else "blocked",
            "observer_id_present": reviewer_present,
            "observed_at_utc_present": observed_at_present,
            "observer_signoff": observer_signoff,
            "anonymized_notes_only": anonymized_notes_only,
            "hidden_state_blocker_count": hidden_state_blocker_count,
            "blockers": [
                blocker
                for blocker in blockers
                if blocker not in {
                    f"{_display(work_order_json, root=root)}:missing",
                    f"{_display(work_order_json, root=root)}:work_order_not_ready",
                    f"{_display(preflight_json, root=root)}:missing",
                    f"{_display(preflight_json, root=root)}:preflight_not_ready",
                }
            ],
        },
    ]
    summary = {
        "packet_type": PACKET_TYPE,
        "schema_version": SCHEMA_VERSION,
        "status": "developer_preview_new_user_observation_receipt_ready"
        if ready
        else "blocked_developer_preview_new_user_observation_receipt",
        "observer_signoff": observer_signoff,
        "anonymized_notes_only": anonymized_notes_only,
        "blocker_count": len(blockers),
        "blockers": blockers,
        "hidden_state_blocker_count": hidden_state_blocker_count,
        "hidden_state_blockers": hidden_blockers,
        "work_order_ready": work_order_ready,
        "preflight_ready": preflight_ready,
        "observer_id_present": reviewer_present,
        "observed_at_utc_present": observed_at_present,
        "anonymized_summary_present": anonymized_summary_present,
        "raw_customer_data_stored_in_repo": False,
        "customer_retained_raw_data": True,
        "execution_enabled": False,
        "external_state_mutated": False,
        "claim_promotion_allowed": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": "Attach this observation receipt to the Developer Preview final gate audit."
        if ready
        else (
            "Run an observed new-user workflow session, keep raw data outside the repo, and rebuild this "
            "receipt with observer signoff plus anonymized notes only."
        ),
    }
    return {"summary": summary, "rows": rows}


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
        f"- observer_signoff: `{summary['observer_signoff']}`",
        f"- anonymized_notes_only: `{summary['anonymized_notes_only']}`",
        f"- blocker_count: `{summary['blocker_count']}`",
        f"- hidden_state_blocker_count: `{summary['hidden_state_blocker_count']}`",
        f"- raw_customer_data_stored_in_repo: `{summary['raw_customer_data_stored_in_repo']}`",
        "",
        "| check | status | blockers |",
        "| --- | --- | --- |",
    ]
    for row in payload["rows"]:
        blockers = ";".join(str(item) for item in row.get("blockers", [])) or "-"
        lines.append(f"| `{row['check']}` | `{row['status']}` | `{blockers}` |")
    lines.extend(["", CLAIM_BOUNDARY, ""])
    return "\n".join(lines)


def _write_text(path_like: str | Path, text: str, *, root: Path = ROOT) -> None:
    path = _resolve(path_like, root=root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build a Developer Preview new-user observation receipt.")
    parser.add_argument("--work-order-json", default=DEFAULT_WORK_ORDER_JSON)
    parser.add_argument("--preflight-json", default=DEFAULT_PREFLIGHT_JSON)
    parser.add_argument("--observer-id", default="")
    parser.add_argument("--observed-at-utc", default="")
    parser.add_argument("--anonymized-summary", default="")
    parser.add_argument("--observer-signoff", action="store_true")
    parser.add_argument("--anonymized-notes-only", action="store_true")
    parser.add_argument("--hidden-state-blocker", action="append", default=[])
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    payload = build_developer_preview_new_user_observation_receipt(
        work_order_json=args.work_order_json,
        preflight_json=args.preflight_json,
        observer_id=args.observer_id,
        observed_at_utc=args.observed_at_utc,
        anonymized_summary=args.anonymized_summary,
        observer_signoff=args.observer_signoff,
        anonymized_notes_only=args.anonymized_notes_only,
        hidden_state_blockers=list(args.hidden_state_blocker or []),
    )
    _write_json(args.out_json, payload)
    _write_text(args.out_md, _render_md(payload))
    return 0 if payload["summary"]["status"] == "developer_preview_new_user_observation_receipt_ready" else 1


if __name__ == "__main__":
    raise SystemExit(main())

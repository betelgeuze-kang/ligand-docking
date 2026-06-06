#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[1]

DEFAULT_WETLAB_DASHBOARD_JSON = "runs/wetlab_master_handoff_dashboard_current.json"
DEFAULT_WETLAB_FINAL_JSON = "runs/wetlab_final_campaign_summary_current.json"
DEFAULT_WETLAB_SELECTED_ALLATOM_JSON = "runs/wetlab_selected_allatom_gate_burndown_packet_current.json"
DEFAULT_OUT_JSON = "runs/wetlab_execution_readiness_queue_current.json"
DEFAULT_OUT_CSV = "runs/wetlab_execution_readiness_queue_current.csv"
DEFAULT_OUT_MD = "runs/wetlab_execution_readiness_queue_current.md"


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


def _maybe_load_json(path_like: str | Path) -> dict[str, Any]:
    path = _resolve(path_like)
    if not path.exists():
        return {}
    return _load_json(path)


def _summaryish(payload: dict[str, Any]) -> dict[str, Any]:
    summary = dict(payload.get("summary", {}) or {})
    if summary:
        merged = dict(payload)
        merged.update(summary)
        return merged
    return dict(payload or {})


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
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "pass", "ready"}
    return bool(value)


def _bool_or_none(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if value in {"", None}:
        return None
    if isinstance(value, str):
        text = value.strip().lower()
        if text in {"1", "true", "yes", "y", "pass", "ready", "passed"}:
            return True
        if text in {"0", "false", "no", "n", "fail", "failed", "blocked"}:
            return False
    return None


def _text_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        text = _text(value)
        return [text] if text else []
    if isinstance(value, (list, tuple, set)):
        out: list[str] = []
        for item in value:
            text = _text(item)
            if text and text not in out:
                out.append(text)
        return out
    text = _text(value)
    return [text] if text else []


def _selected_allatom_block_reason(
    *,
    geometry_gate_pass: bool,
    final_gate_pass: bool | None,
    claim_gate_available: bool | None,
    claim_ready_for_allatom: bool | None,
    commercial_hard_gate_pass_v2: bool | None,
    commercial_hard_gate_failed_metrics_v2: list[str],
    effective_execution_gate_pass: bool | None,
    hard_block_count: int,
    semi_hard_block_count: int,
    missing_metric_count: int,
    fallback_reason: str,
) -> str:
    reasons: list[str] = []
    if not geometry_gate_pass:
        reasons.append("geometry wetlab gate failed")
    if final_gate_pass is False:
        reasons.append("final wetlab gate failed")
    if claim_gate_available is False:
        reasons.append("claim/equivalence gate unavailable")
    if claim_ready_for_allatom is False:
        reasons.append("claim/equivalence gate not ready")
    if commercial_hard_gate_pass_v2 is False:
        metric_text = ",".join(commercial_hard_gate_failed_metrics_v2) or "unknown"
        reasons.append(f"commercial hard gate failed ({metric_text})")
    if effective_execution_gate_pass is False and not reasons:
        reasons.append("effective selected all-atom execution gate failed")
    if hard_block_count:
        reasons.append(f"hard blocks={hard_block_count}")
    if semi_hard_block_count:
        reasons.append(f"semi-hard blocks={semi_hard_block_count}")
    if missing_metric_count:
        reasons.append(f"missing metrics={missing_metric_count}")
    return "; ".join(reasons) or fallback_reason


def build_payload(
    wetlab_dashboard_payload: dict[str, Any],
    wetlab_final_payload: dict[str, Any],
    selected_allatom_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    dashboard = _summaryish(wetlab_dashboard_payload)
    final_summary = _summaryish(wetlab_final_payload)
    selected_allatom_summary = _summaryish(selected_allatom_payload or {})

    primary_watch = _text(dashboard.get("broad_screen_primary_watch_liveness")) or "-"
    antitarget_watch = _text(dashboard.get("broad_screen_antitarget_watch_liveness")) or "-"
    primary_watch_attached = primary_watch in {"attached", "healthy"}
    antitarget_watch_attached = antitarget_watch in {"attached", "healthy"}
    primary_ready_now = _int(final_summary.get("broad_screen_execution_ready_now_row_count"))
    antitarget_ready_now = _int(final_summary.get("broad_screen_antitarget_ready_now_row_count"))
    ready_to_send_tracks = _int(final_summary.get("ready_to_send_track_count"))
    primary_dispatch_complete = (
        _text(final_summary.get("campaign_terminal_state")).lower() == "complete"
        and _bool(final_summary.get("broad_screen_execution_queue_ready"))
        and _bool(dashboard.get("broad_screen_throughput_execute_ready"))
    )
    selected_allatom_geometry_gate_pass = _bool(dashboard.get("selected_allatom_wetlab_gate_pass"))
    selected_summary_geometry_gate = _bool_or_none(selected_allatom_summary.get("selected_allatom_wetlab_gate_pass"))
    if selected_summary_geometry_gate is not None:
        selected_allatom_geometry_gate_pass = selected_summary_geometry_gate
    selected_allatom_final_gate_pass = _bool_or_none(
        selected_allatom_summary.get("selected_allatom_final_gate_pass")
    )
    if selected_allatom_final_gate_pass is None:
        selected_allatom_final_gate_pass = _bool_or_none(dashboard.get("selected_allatom_final_gate_pass"))
    selected_allatom_claim_gate_available = _bool_or_none(
        selected_allatom_summary.get("selected_allatom_claim_gate_available")
    )
    if selected_allatom_claim_gate_available is None:
        selected_allatom_claim_gate_available = _bool_or_none(dashboard.get("selected_allatom_claim_gate_available"))
    selected_allatom_claim_ready_for_allatom = _bool_or_none(
        selected_allatom_summary.get("selected_allatom_claim_ready_for_allatom")
    )
    if selected_allatom_claim_ready_for_allatom is None:
        selected_allatom_claim_ready_for_allatom = _bool_or_none(dashboard.get("selected_allatom_claim_ready_for_allatom"))
    selected_allatom_hard_block_count = _int(selected_allatom_summary.get("hard_block_count"))
    selected_allatom_semi_hard_block_count = _int(selected_allatom_summary.get("semi_hard_block_count"))
    selected_allatom_missing_metric_count = _int(selected_allatom_summary.get("missing_metric_count"))
    selected_allatom_effective_execution_gate_pass = _bool_or_none(
        selected_allatom_summary.get("selected_allatom_effective_execution_gate_pass")
    )
    selected_allatom_commercial_hard_gate_pass_v2 = _bool_or_none(
        selected_allatom_summary.get("selected_allatom_commercial_hard_gate_pass_v2")
    )
    selected_allatom_commercial_hard_gate_failed_metrics_v2 = _text_list(
        selected_allatom_summary.get("selected_allatom_commercial_hard_gate_failed_metrics_v2")
    )
    if selected_allatom_summary:
        selected_allatom_gate_pass = bool(
            selected_allatom_geometry_gate_pass
            and selected_allatom_final_gate_pass is True
            and selected_allatom_claim_gate_available is not False
            and selected_allatom_claim_ready_for_allatom is not False
            and selected_allatom_commercial_hard_gate_pass_v2 is not False
            and selected_allatom_effective_execution_gate_pass is not False
            and selected_allatom_hard_block_count == 0
            and selected_allatom_semi_hard_block_count == 0
            and selected_allatom_missing_metric_count == 0
        )
    else:
        selected_allatom_gate_pass = selected_allatom_geometry_gate_pass
    selected_allatom_focus = _text(dashboard.get("selected_allatom_focus_label"))
    selected_allatom_block_reason = _selected_allatom_block_reason(
        geometry_gate_pass=selected_allatom_geometry_gate_pass,
        final_gate_pass=selected_allatom_final_gate_pass,
        claim_gate_available=selected_allatom_claim_gate_available,
        claim_ready_for_allatom=selected_allatom_claim_ready_for_allatom,
        commercial_hard_gate_pass_v2=selected_allatom_commercial_hard_gate_pass_v2,
        commercial_hard_gate_failed_metrics_v2=selected_allatom_commercial_hard_gate_failed_metrics_v2,
        effective_execution_gate_pass=selected_allatom_effective_execution_gate_pass,
        hard_block_count=selected_allatom_hard_block_count,
        semi_hard_block_count=selected_allatom_semi_hard_block_count,
        missing_metric_count=selected_allatom_missing_metric_count,
        fallback_reason=_text(dashboard.get("selected_allatom_actionability_block_reason")),
    )

    rows = [
        {
            "queue_rank": 1,
            "lane_id": "primary_dispatch_lane",
            "status": (
                "ready"
                if primary_ready_now <= 0 and primary_dispatch_complete
                else "blocked"
                if primary_ready_now <= 0
                else "ready"
                if primary_watch_attached
                else "partial"
            ),
            "signal": (
                f"primary_ready_now={primary_ready_now}; primary_watch={primary_watch}; "
                f"primary_dispatch_complete={primary_dispatch_complete}"
            ),
            "next_required_action": (
                "Keep the completed primary dispatch lane warm and reopen only when a new primary retry row is intentionally introduced."
                if primary_ready_now <= 0 and primary_dispatch_complete
                else "Create at least one execution-ready primary row before treating wetlab as commercially dispatchable."
                if primary_ready_now <= 0
                else "Keep at least one primary execution-ready row live while nightly/wetlab blockers are burned down."
                if primary_watch_attached
                else "Recover the primary watch loop or document manual supervision for the execution-ready primary row."
            ),
        },
        {
            "queue_rank": 2,
            "lane_id": "antitarget_dispatch_lane",
            "status": (
                "blocked"
                if antitarget_ready_now <= 0
                else "ready"
                if antitarget_watch_attached
                else "partial"
            ),
            "signal": f"antitarget_ready_now={antitarget_ready_now}; antitarget_watch={antitarget_watch}",
            "next_required_action": (
                "Keep the attached antitarget watch loop healthy while the ready-now counterscreen row stays available."
                if antitarget_ready_now > 0 and antitarget_watch_attached
                else "Recover the detached antitarget watch loop or document a manual supervision path for the ready-now antitarget row."
                if antitarget_ready_now > 0
                else "Create a ready-now antitarget row before calling the counterscreen lane operational."
            ),
        },
        {
            "queue_rank": 3,
            "lane_id": "selected_allatom_gate",
            "status": "ready" if selected_allatom_gate_pass else "blocked",
            "signal": (
                f"selected_allatom_gate_pass={selected_allatom_gate_pass}; "
                f"geometry_gate_pass={selected_allatom_geometry_gate_pass}; "
                f"final_gate_pass={selected_allatom_final_gate_pass}; "
                f"claim_gate_available={selected_allatom_claim_gate_available}; "
                f"claim_ready_for_allatom={selected_allatom_claim_ready_for_allatom}; "
                f"commercial_hard_gate_pass_v2={selected_allatom_commercial_hard_gate_pass_v2}; "
                f"focus={selected_allatom_focus or '-'}; "
                f"block_reason={selected_allatom_block_reason or '-'}"
            ),
            "next_required_action": (
                "Keep the selected all-atom final/claim/commercial execution gate green and preserve the current focus packet."
                if selected_allatom_gate_pass
                else "Resolve the selected all-atom final/claim/commercial gate before calling the wetlab lane execution-ready."
            ),
        },
        {
            "queue_rank": 4,
            "lane_id": "watch_loop_recovery",
            "status": (
                "ready"
                if primary_watch_attached and antitarget_watch_attached
                else "blocked"
            ),
            "signal": (
                f"primary_watch={primary_watch}; antitarget_watch={antitarget_watch}; "
                f"watch_gap_count={sum(v not in {'attached', 'healthy'} for v in (primary_watch, antitarget_watch))}"
            ),
            "next_required_action": (
                "Keep both watch loops attached and healthy."
                if primary_watch_attached and antitarget_watch_attached
                else "Recover stale/detached watch loops before calling the wetlab lane operationally supervised."
            ),
        },
        {
            "queue_rank": 5,
            "lane_id": "partner_send_tracks",
            "status": "ready" if ready_to_send_tracks > 0 else "blocked",
            "signal": f"ready_to_send_track_count={ready_to_send_tracks}",
            "next_required_action": (
                "Keep outbound partner send tracks warm while execution blockers are being cleared."
                if ready_to_send_tracks > 0
                else "Create at least one ready-to-send partner track."
            ),
        },
    ]

    blocked_count = sum(1 for row in rows if row["status"] == "blocked")
    partial_count = sum(1 for row in rows if row["status"] == "partial")
    ready_count = sum(1 for row in rows if row["status"] == "ready")
    watch_gap_count = sum(v not in {"attached", "healthy"} for v in (primary_watch, antitarget_watch))
    summary = {
        "queue_ready": True,
        "queue_artifact": "runs/wetlab_execution_readiness_queue_current.md",
        "row_count": len(rows),
        "blocked_count": blocked_count,
        "partial_count": partial_count,
        "ready_count": ready_count,
        "primary_watch_liveness": primary_watch,
        "antitarget_watch_liveness": antitarget_watch,
        "watch_gap_count": watch_gap_count,
        "execution_ready_now_row_count": primary_ready_now,
        "antitarget_ready_now_row_count": antitarget_ready_now,
        "ready_to_send_track_count": ready_to_send_tracks,
        "selected_allatom_wetlab_gate_pass": selected_allatom_gate_pass,
        "selected_allatom_geometry_wetlab_gate_pass": selected_allatom_geometry_gate_pass,
        "selected_allatom_final_gate_pass": selected_allatom_final_gate_pass,
        "selected_allatom_claim_gate_available": selected_allatom_claim_gate_available,
        "selected_allatom_claim_ready_for_allatom": selected_allatom_claim_ready_for_allatom,
        "selected_allatom_effective_execution_gate_pass": selected_allatom_effective_execution_gate_pass,
        "selected_allatom_commercial_hard_gate_pass_v2": selected_allatom_commercial_hard_gate_pass_v2,
        "selected_allatom_commercial_hard_gate_failed_metrics_v2": selected_allatom_commercial_hard_gate_failed_metrics_v2,
        "selected_allatom_hard_block_count": selected_allatom_hard_block_count,
        "selected_allatom_semi_hard_block_count": selected_allatom_semi_hard_block_count,
        "selected_allatom_missing_metric_count": selected_allatom_missing_metric_count,
        "selected_allatom_focus_label": selected_allatom_focus,
        "selected_allatom_block_reason": selected_allatom_block_reason,
        "status_line": (
            f"send={ready_to_send_tracks} ready | "
            f"primary_exec={primary_ready_now} ready_now ({primary_watch}{'; dispatch_complete' if primary_dispatch_complete else ''}) | "
            f"antitarget_exec={antitarget_ready_now} ready_now ({antitarget_watch}) | "
            f"selected_allatom={'pass' if selected_allatom_gate_pass else 'fail'}"
        ),
        "next_required_step": (
            "Wetlab execution readiness is green for the current local-delivery scope; keep the completed primary dispatch lane warm, keep the ready-now antitarget row supervised, and keep both watch loops attached."
            if watch_gap_count == 0 and primary_dispatch_complete and selected_allatom_gate_pass
            else "Keep the completed primary dispatch lane warm and clear the selected all-atom final/claim/commercial gate while keeping both watch loops attached."
            if watch_gap_count == 0 and primary_dispatch_complete and not selected_allatom_gate_pass
            else "Create at least one primary execution-ready row and clear the selected all-atom final/claim/commercial gate while keeping both watch loops attached."
            if watch_gap_count == 0 and (primary_ready_now <= 0 or not selected_allatom_gate_pass)
            else "Recover the stale/detached watch loops and create at least one primary execution-ready row; keep the selected all-atom gate green."
            if selected_allatom_gate_pass
            else "Recover the stale/detached watch loops, create at least one primary execution-ready row, "
            "and clear the selected all-atom final/claim/commercial gate before calling wetlab commercially execution-ready."
        ),
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# Wetlab Execution Readiness Queue",
        "",
        f"- row_count: `{summary['row_count']}`",
        f"- blocked_count: `{summary['blocked_count']}`",
        f"- partial_count: `{summary['partial_count']}`",
        f"- ready_count: `{summary['ready_count']}`",
        f"- status_line: `{summary['status_line']}`",
        "",
        "## Next Step",
        "",
        f"- {summary['next_required_step']}",
        "",
        "## Queue",
        "",
        "| rank | lane_id | status | signal | next_required_action |",
        "| ---: | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| {row['queue_rank']} | `{row['lane_id']}` | `{row['status']}` | `{row['signal']}` | `{row['next_required_action']}` |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the wetlab execution readiness queue.")
    parser.add_argument("--wetlab-dashboard-json", default=DEFAULT_WETLAB_DASHBOARD_JSON)
    parser.add_argument("--wetlab-final-json", default=DEFAULT_WETLAB_FINAL_JSON)
    parser.add_argument("--wetlab-selected-allatom-json", default=DEFAULT_WETLAB_SELECTED_ALLATOM_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        wetlab_dashboard_payload=_load_json(args.wetlab_dashboard_json),
        wetlab_final_payload=_load_json(args.wetlab_final_json),
        selected_allatom_payload=_maybe_load_json(args.wetlab_selected_allatom_json),
    )
    out_json = _resolve(args.out_json)
    out_csv = _resolve(args.out_csv)
    out_md = _resolve(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    write_csv_rows(out_csv, payload["rows"])
    _write_markdown(out_md, payload)


if __name__ == "__main__":
    main()

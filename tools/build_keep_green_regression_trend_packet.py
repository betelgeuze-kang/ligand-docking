#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

DEFAULT_NIGHTLY_GATE_JSON = "runs/nightly_gate_burndown_packet_current.json"
DEFAULT_VIEWER_REFRESH_JSON = "runs/viewer_smoke_refresh_current.json"
DEFAULT_WETLAB_GATE_JSON = "runs/wetlab_selected_allatom_gate_burndown_packet_current.json"
DEFAULT_REFRESH_JSON = "runs/family_expansion_refresh_current.json"
DEFAULT_LANE_HISTORY_JSONL = "runs/keep_green_lane_history_current.jsonl"
DEFAULT_OUT_JSON = "runs/keep_green_regression_trend_packet_current.json"
DEFAULT_OUT_CSV = "runs/keep_green_regression_trend_packet_current.csv"
DEFAULT_OUT_MD = "runs/keep_green_regression_trend_packet_current.md"
DEFAULT_MINIMUM_REPEATED_SAMPLE_COUNT = 3

NIGHTLY_TOP_LEVEL_RE = re.compile(
    r"^ligand_htvs_nightly_\d{4}-\d{2}-\d{2}(?:_(?:attempt\d+|smoke|stage6_top_level_reentry(?:_[a-z0-9_]+)?|summary))?_summary\.json$"
)


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


def _load_jsonl(path_like: str | Path) -> list[dict[str, Any]]:
    path = _resolve(path_like)
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                rows.append(payload)
    return rows


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for key in row.keys():
            if key not in seen:
                seen.add(key)
                fieldnames.append(key)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


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
    return str(value).strip().lower() in {"1", "true", "yes", "ok", "pass", "passed"}


def _summary(payload: dict[str, Any]) -> dict[str, Any]:
    return dict(payload.get("summary", {}) or {})


def _timestamp_sort_key(value: str) -> str:
    if not value:
        return ""
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).isoformat()
    except ValueError:
        return value


def _nightly_label(path: str) -> str:
    name = Path(path).name
    return name.removeprefix("ligand_htvs_nightly_").removesuffix("_summary.json")


def _load_nightly_history_from_runs(limit: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in sorted((ROOT / "runs").glob("ligand_htvs_nightly_*summary.json")):
        if not NIGHTLY_TOP_LEVEL_RE.match(path.name):
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(payload.get("pass"), bool):
            continue
        rows.append(
            {
                "artifact": str(path.relative_to(ROOT)),
                "run_label": _nightly_label(str(path)),
                "generated_at_local": _text(payload.get("generated_at_local")),
                "pass": bool(payload.get("pass")),
                "latest_failed_stage": _text(payload.get("latest_failed_stage")),
                "error_code": _text(payload.get("error_code")),
            }
        )
    rows.sort(key=lambda row: (_timestamp_sort_key(_text(row.get("generated_at_local"))), _text(row.get("run_label"))))
    return rows[-max(1, limit) :]


def _normalize_nightly_history_rows(history_payloads: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for index, payload in enumerate(history_payloads, start=1):
        rows.append(
            {
                "artifact": _text(payload.get("artifact")) or f"in_memory_nightly_history_{index}",
                "run_label": _text(payload.get("run_label")) or f"sample_{index}",
                "generated_at_local": _text(payload.get("generated_at_local")),
                "pass": _bool(payload.get("pass")),
                "latest_failed_stage": _text(payload.get("latest_failed_stage")),
                "error_code": _text(payload.get("error_code")),
            }
        )
    rows.sort(key=lambda row: (_timestamp_sort_key(_text(row.get("generated_at_local"))), _text(row.get("run_label"))))
    return rows[-max(1, limit) :]


def _normalize_lane_history_rows(history_payloads: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for index, payload in enumerate(history_payloads, start=1):
        lane_id = _text(payload.get("lane_id"))
        if not lane_id:
            continue
        grouped.setdefault(lane_id, []).append(
            {
                "artifact": _text(payload.get("artifact")) or _text(payload.get("primary_artifact")),
                "run_label": _text(payload.get("run_label")) or f"lane_history_{index}",
                "generated_at_local": _text(payload.get("generated_at_local")),
                "lane_id": lane_id,
                "pass": _bool(payload.get("pass")),
                "status": _text(payload.get("status")),
                "status_line": _text(payload.get("status_line")),
            }
        )
    rows: list[dict[str, Any]] = []
    for lane_rows in grouped.values():
        lane_rows.sort(
            key=lambda row: (_timestamp_sort_key(_text(row.get("generated_at_local"))), _text(row.get("run_label")))
        )
        rows.extend(lane_rows[-max(1, limit) :])
    rows.sort(
        key=lambda row: (
            _text(row.get("lane_id")),
            _timestamp_sort_key(_text(row.get("generated_at_local"))),
            _text(row.get("run_label")),
        )
    )
    return rows


def _pass_streak(rows: list[dict[str, Any]]) -> int:
    streak = 0
    for row in reversed(rows):
        if not bool(row.get("pass", False)):
            break
        streak += 1
    return streak


def _lane_status(current_green: bool, repeated_ready: bool) -> str:
    if repeated_ready:
        return "keep_green_history_ready"
    if current_green:
        return "keep_green_needs_more_history"
    return "not_green"


def _lane_history_stats(
    lane_id: str,
    lane_history_rows: list[dict[str, Any]],
    *,
    current_green: bool,
    minimum_repeated_sample_count: int,
    fallback_to_current: bool,
) -> dict[str, Any]:
    rows = [row for row in lane_history_rows if _text(row.get("lane_id")) == lane_id]
    sample_count = len(rows)
    pass_count = sum(1 for row in rows if bool(row.get("pass", False)))
    recent_pass_streak = _pass_streak(rows)
    if sample_count == 0 and fallback_to_current:
        sample_count = 1 if current_green else 0
        pass_count = 1 if current_green else 0
        recent_pass_streak = 1 if current_green else 0
    repeated_ready = current_green and recent_pass_streak >= minimum_repeated_sample_count
    return {
        "sample_count": sample_count,
        "pass_count": pass_count,
        "recent_pass_streak": recent_pass_streak,
        "repeated_history_ready": repeated_ready,
    }


def build_payload(
    nightly_gate_payload: dict[str, Any],
    viewer_refresh_payload: dict[str, Any],
    wetlab_gate_payload: dict[str, Any],
    refresh_payload: dict[str, Any],
    *,
    nightly_history_payloads: list[dict[str, Any]] | None = None,
    lane_history_payloads: list[dict[str, Any]] | None = None,
    minimum_repeated_sample_count: int = DEFAULT_MINIMUM_REPEATED_SAMPLE_COUNT,
) -> dict[str, Any]:
    min_samples = max(1, int(minimum_repeated_sample_count))
    nightly_summary = _summary(nightly_gate_payload)
    viewer_summary = _summary(viewer_refresh_payload)
    wetlab_summary = _summary(wetlab_gate_payload)
    refresh_summary = _summary(refresh_payload)
    history_rows = (
        _normalize_nightly_history_rows(nightly_history_payloads, limit=8)
        if nightly_history_payloads is not None
        else _load_nightly_history_from_runs(limit=8)
    )
    lane_history_rows = (
        _normalize_lane_history_rows(lane_history_payloads, limit=8)
        if lane_history_payloads is not None
        else _normalize_lane_history_rows(_load_jsonl(DEFAULT_LANE_HISTORY_JSONL), limit=8)
    )
    nightly_history_pass_count = sum(1 for row in history_rows if bool(row.get("pass", False)))
    nightly_recent_pass_streak = _pass_streak(history_rows)

    nightly_current_green = (
        _text(nightly_summary.get("status")) == "nightly_gate_green"
        and _bool(nightly_summary.get("downstream_execute_gate_pass"))
        and not _bool(nightly_summary.get("stage6_gate_failed"))
        and _int(nightly_summary.get("gate_failed_metric_count")) == 0
    )
    viewer_current_green = (
        _bool(viewer_refresh_payload.get("overall_ok"))
        and _int(viewer_summary.get("compare_writeback_wrapper_gap_count")) == 0
        and _int(viewer_summary.get("compare_writeback_mesh_probe_unavailable_count")) == 0
    )
    wetlab_current_green = (
        _bool(wetlab_summary.get("selected_allatom_wetlab_gate_pass"))
        and _bool(wetlab_summary.get("selected_allatom_final_gate_pass"))
        and _int(wetlab_summary.get("hard_block_count")) == 0
        and _int(wetlab_summary.get("semi_hard_block_count")) == 0
        and _int(wetlab_summary.get("missing_metric_count")) == 0
    )
    refresh_current_green = _bool(refresh_summary.get("overall_ok")) and _int(refresh_summary.get("failed_count")) == 0
    viewer_stats = _lane_history_stats(
        "viewer",
        lane_history_rows,
        current_green=viewer_current_green,
        minimum_repeated_sample_count=min_samples,
        fallback_to_current=True,
    )
    wetlab_stats = _lane_history_stats(
        "wetlab",
        lane_history_rows,
        current_green=wetlab_current_green,
        minimum_repeated_sample_count=min_samples,
        fallback_to_current=True,
    )
    refresh_stats = _lane_history_stats(
        "refresh",
        lane_history_rows,
        current_green=refresh_current_green,
        minimum_repeated_sample_count=min_samples,
        fallback_to_current=True,
    )

    rows = [
        {
            "lane_id": "nightly",
            "current_green": nightly_current_green,
            "sample_count": len(history_rows),
            "pass_count": nightly_history_pass_count,
            "recent_pass_streak": nightly_recent_pass_streak,
            "minimum_repeated_sample_count": min_samples,
            "repeated_history_ready": nightly_current_green and nightly_recent_pass_streak >= min_samples,
            "status": _lane_status(nightly_current_green, nightly_current_green and nightly_recent_pass_streak >= min_samples),
            "primary_artifact": _text(nightly_summary.get("packet_artifact")) or DEFAULT_NIGHTLY_GATE_JSON.replace(".json", ".md"),
            "status_line": _text(nightly_summary.get("status_line")),
        },
        {
            "lane_id": "viewer",
            "current_green": viewer_current_green,
            "sample_count": viewer_stats["sample_count"],
            "pass_count": viewer_stats["pass_count"],
            "recent_pass_streak": viewer_stats["recent_pass_streak"],
            "minimum_repeated_sample_count": min_samples,
            "repeated_history_ready": viewer_stats["repeated_history_ready"],
            "status": _lane_status(viewer_current_green, bool(viewer_stats["repeated_history_ready"])),
            "primary_artifact": "runs/viewer_smoke_refresh_current.md",
            "status_line": _text(viewer_summary.get("compare_writeback_geometry_burndown_status_line")),
        },
        {
            "lane_id": "wetlab",
            "current_green": wetlab_current_green,
            "sample_count": wetlab_stats["sample_count"],
            "pass_count": wetlab_stats["pass_count"],
            "recent_pass_streak": wetlab_stats["recent_pass_streak"],
            "minimum_repeated_sample_count": min_samples,
            "repeated_history_ready": wetlab_stats["repeated_history_ready"],
            "status": _lane_status(wetlab_current_green, bool(wetlab_stats["repeated_history_ready"])),
            "primary_artifact": _text(wetlab_summary.get("packet_artifact")) or "runs/wetlab_selected_allatom_gate_burndown_packet_current.md",
            "status_line": _text(wetlab_summary.get("next_required_step")),
        },
        {
            "lane_id": "refresh",
            "current_green": refresh_current_green,
            "sample_count": refresh_stats["sample_count"],
            "pass_count": refresh_stats["pass_count"],
            "recent_pass_streak": refresh_stats["recent_pass_streak"],
            "minimum_repeated_sample_count": min_samples,
            "repeated_history_ready": refresh_stats["repeated_history_ready"],
            "status": _lane_status(refresh_current_green, bool(refresh_stats["repeated_history_ready"])),
            "primary_artifact": "runs/family_expansion_refresh_current.md",
            "status_line": _text(refresh_summary.get("next_required_step")),
        },
    ]
    current_green_count = sum(1 for row in rows if bool(row["current_green"]))
    repeated_ready_count = sum(1 for row in rows if bool(row["repeated_history_ready"]))
    all_current_green = current_green_count == len(rows)
    sufficient_repeated_history = repeated_ready_count == len(rows)
    commercial_trend_status = (
        "sufficient_repeated_history"
        if sufficient_repeated_history
        else "baseline_green_needs_repeated_history"
        if all_current_green
        else "current_green_regression_open"
    )
    summary = {
        "packet_ready": True,
        "packet_artifact": "runs/keep_green_regression_trend_packet_current.md",
        "minimum_repeated_sample_count": min_samples,
        "lane_count": len(rows),
        "current_green_lane_count": current_green_count,
        "repeated_history_ready_lane_count": repeated_ready_count,
        "insufficient_history_lane_count": len(rows) - repeated_ready_count,
        "all_current_green": all_current_green,
        "sufficient_repeated_history": sufficient_repeated_history,
        "commercial_trend_status": commercial_trend_status,
        "nightly_history_sample_count": len(history_rows),
        "nightly_history_pass_count": nightly_history_pass_count,
        "nightly_recent_pass_streak": nightly_recent_pass_streak,
        "lane_history_artifact": DEFAULT_LANE_HISTORY_JSONL,
        "lane_history_sample_count": len(lane_history_rows),
        "viewer_history_sample_count": int(viewer_stats["sample_count"]),
        "viewer_recent_pass_streak": int(viewer_stats["recent_pass_streak"]),
        "wetlab_history_sample_count": int(wetlab_stats["sample_count"]),
        "wetlab_recent_pass_streak": int(wetlab_stats["recent_pass_streak"]),
        "refresh_history_sample_count": int(refresh_stats["sample_count"]),
        "refresh_recent_pass_streak": int(refresh_stats["recent_pass_streak"]),
        "viewer_current_green": viewer_current_green,
        "wetlab_current_green": wetlab_current_green,
        "refresh_current_green": refresh_current_green,
        "next_required_step": (
            "Current keep-green lanes are green, but repeated-history sufficiency is not complete; "
            "rerun canonical nightly, viewer, wetlab, and refresh checks and append them to the keep-green lane history until each lane has the required pass streak."
            if all_current_green and not sufficient_repeated_history
            else "Keep the repeated keep-green history attached to the delivery bundle."
            if sufficient_repeated_history
            else "Repair the current non-green keep-green lane before expanding the delivery claim."
        ),
    }
    return {"summary": summary, "rows": rows, "nightly_history_rows": history_rows, "lane_history_rows": lane_history_rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# Keep-Green Regression Trend Packet",
        "",
        f"- packet_ready: `{s['packet_ready']}`",
        f"- minimum_repeated_sample_count: `{s['minimum_repeated_sample_count']}`",
        f"- lane_count: `{s['lane_count']}`",
        f"- current_green_lane_count: `{s['current_green_lane_count']}`",
        f"- repeated_history_ready_lane_count: `{s['repeated_history_ready_lane_count']}`",
        f"- insufficient_history_lane_count: `{s['insufficient_history_lane_count']}`",
        f"- all_current_green: `{s['all_current_green']}`",
        f"- sufficient_repeated_history: `{s['sufficient_repeated_history']}`",
        f"- commercial_trend_status: `{s['commercial_trend_status']}`",
        f"- nightly_history_sample_count: `{s['nightly_history_sample_count']}`",
        f"- nightly_history_pass_count: `{s['nightly_history_pass_count']}`",
        f"- nightly_recent_pass_streak: `{s['nightly_recent_pass_streak']}`",
        f"- lane_history_artifact: `{s['lane_history_artifact']}`",
        f"- lane_history_sample_count: `{s['lane_history_sample_count']}`",
        f"- viewer_recent_pass_streak: `{s['viewer_recent_pass_streak']}/{s['minimum_repeated_sample_count']}`",
        f"- wetlab_recent_pass_streak: `{s['wetlab_recent_pass_streak']}/{s['minimum_repeated_sample_count']}`",
        f"- refresh_recent_pass_streak: `{s['refresh_recent_pass_streak']}/{s['minimum_repeated_sample_count']}`",
        "",
        "## Next Step",
        "",
        f"- {s['next_required_step']}",
        "",
        "## Lanes",
        "",
        "| lane_id | current_green | sample_count | pass_count | recent_pass_streak | repeated_history_ready | status | primary_artifact |",
        "| --- | --- | ---: | ---: | ---: | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['lane_id']}` | `{row['current_green']}` | {row['sample_count']} | {row['pass_count']} | "
            f"{row['recent_pass_streak']} | `{row['repeated_history_ready']}` | `{row['status']}` | `{row['primary_artifact']}` |"
        )
    lines.extend(["", "## Nightly History", ""])
    lines.extend(
        [
            "| run_label | pass | generated_at_local | artifact |",
            "| --- | --- | --- | --- |",
        ]
    )
    for row in payload["nightly_history_rows"]:
        lines.append(
            f"| `{row['run_label']}` | `{row['pass']}` | `{row['generated_at_local'] or '-'}` | `{row['artifact']}` |"
        )
    lines.extend(["", "## Lane History", ""])
    lines.extend(
        [
            "| lane_id | run_label | pass | generated_at_local | artifact |",
            "| --- | --- | --- | --- | --- |",
        ]
    )
    for row in payload["lane_history_rows"]:
        lines.append(
            f"| `{row['lane_id']}` | `{row['run_label']}` | `{row['pass']}` | `{row['generated_at_local'] or '-'}` | `{row['artifact'] or '-'}` |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build keep-green regression trend packet for local delivery lanes.")
    parser.add_argument("--nightly-gate-json", default=DEFAULT_NIGHTLY_GATE_JSON)
    parser.add_argument("--viewer-refresh-json", default=DEFAULT_VIEWER_REFRESH_JSON)
    parser.add_argument("--wetlab-gate-json", default=DEFAULT_WETLAB_GATE_JSON)
    parser.add_argument("--refresh-json", default=DEFAULT_REFRESH_JSON)
    parser.add_argument("--lane-history-jsonl", default=DEFAULT_LANE_HISTORY_JSONL)
    parser.add_argument("--minimum-repeated-sample-count", type=int, default=DEFAULT_MINIMUM_REPEATED_SAMPLE_COUNT)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        _load_json(args.nightly_gate_json),
        _load_json(args.viewer_refresh_json),
        _load_json(args.wetlab_gate_json),
        _load_json(args.refresh_json),
        lane_history_payloads=_load_jsonl(args.lane_history_jsonl),
        minimum_repeated_sample_count=args.minimum_repeated_sample_count,
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

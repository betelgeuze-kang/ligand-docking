#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from tools import build_keep_green_regression_trend_packet as trend

ROOT = Path(__file__).resolve().parents[1]

DEFAULT_NIGHTLY_GATE_JSON = trend.DEFAULT_NIGHTLY_GATE_JSON
DEFAULT_VIEWER_REFRESH_JSON = trend.DEFAULT_VIEWER_REFRESH_JSON
DEFAULT_WETLAB_GATE_JSON = trend.DEFAULT_WETLAB_GATE_JSON
DEFAULT_REFRESH_JSON = trend.DEFAULT_REFRESH_JSON
DEFAULT_HISTORY_JSONL = trend.DEFAULT_LANE_HISTORY_JSONL
DEFAULT_OUT_JSON = "runs/keep_green_lane_history_append_current.json"
DEFAULT_OUT_MD = "runs/keep_green_lane_history_append_current.md"


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


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def _text(value: Any) -> str:
    return str(value or "").strip()


def _dedupe_key(row: dict[str, Any]) -> tuple[str, str]:
    return (_text(row.get("run_label")), _text(row.get("lane_id")))


def build_payload(
    nightly_gate_payload: dict[str, Any],
    viewer_refresh_payload: dict[str, Any],
    wetlab_gate_payload: dict[str, Any],
    refresh_payload: dict[str, Any],
    *,
    existing_history_rows: list[dict[str, Any]] | None = None,
    generated_at_local: str,
    run_label: str,
) -> dict[str, Any]:
    baseline = trend.build_payload(
        nightly_gate_payload,
        viewer_refresh_payload,
        wetlab_gate_payload,
        refresh_payload,
        lane_history_payloads=[],
    )
    existing = list(existing_history_rows or [])
    append_rows = [
        {
            "generated_at_local": generated_at_local,
            "run_label": run_label,
            "lane_id": _text(row.get("lane_id")),
            "pass": bool(row.get("current_green", False)),
            "status": _text(row.get("status")),
            "artifact": _text(row.get("primary_artifact")),
            "status_line": _text(row.get("status_line")),
        }
        for row in baseline.get("rows", [])
    ]
    existing_keys = {_dedupe_key(row) for row in existing}
    new_rows = [row for row in append_rows if _dedupe_key(row) not in existing_keys]
    merged_rows = existing + new_rows
    lane_ids = sorted({_text(row.get("lane_id")) for row in append_rows if _text(row.get("lane_id"))})
    pass_count = sum(1 for row in append_rows if bool(row.get("pass", False)))
    summary = {
        "history_artifact": DEFAULT_HISTORY_JSONL,
        "run_label": run_label,
        "generated_at_local": generated_at_local,
        "lane_count": len(append_rows),
        "lane_pass_count": pass_count,
        "all_lanes_pass": pass_count == len(append_rows),
        "appended_row_count": len(new_rows),
        "history_row_count": len(merged_rows),
        "lane_ids": lane_ids,
        "next_required_step": (
            "Build the keep-green regression trend packet from the updated lane history."
            if new_rows
            else "No new lane-history rows were appended for this run label; use a new run label after rerunning the checks."
        ),
    }
    return {"summary": summary, "append_rows": append_rows, "history_rows": merged_rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# Keep-Green Lane History Append",
        "",
        f"- history_artifact: `{s['history_artifact']}`",
        f"- run_label: `{s['run_label']}`",
        f"- generated_at_local: `{s['generated_at_local']}`",
        f"- lane_count: `{s['lane_count']}`",
        f"- lane_pass_count: `{s['lane_pass_count']}`",
        f"- all_lanes_pass: `{s['all_lanes_pass']}`",
        f"- appended_row_count: `{s['appended_row_count']}`",
        f"- history_row_count: `{s['history_row_count']}`",
        "",
        "## Next Step",
        "",
        f"- {s['next_required_step']}",
        "",
        "## Appended Rows",
        "",
        "| lane_id | pass | status | artifact |",
        "| --- | --- | --- | --- |",
    ]
    for row in payload["append_rows"]:
        lines.append(
            f"| `{row['lane_id']}` | `{row['pass']}` | `{row['status']}` | `{row['artifact'] or '-'}` |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Append current keep-green lane results to a JSONL history ledger.")
    parser.add_argument("--nightly-gate-json", default=DEFAULT_NIGHTLY_GATE_JSON)
    parser.add_argument("--viewer-refresh-json", default=DEFAULT_VIEWER_REFRESH_JSON)
    parser.add_argument("--wetlab-gate-json", default=DEFAULT_WETLAB_GATE_JSON)
    parser.add_argument("--refresh-json", default=DEFAULT_REFRESH_JSON)
    parser.add_argument("--history-jsonl", default=DEFAULT_HISTORY_JSONL)
    parser.add_argument("--run-label", default="")
    parser.add_argument("--generated-at-local", default="")
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    generated_at_local = _text(args.generated_at_local) or datetime.now().astimezone().isoformat(timespec="seconds")
    run_label = _text(args.run_label) or "keep_green_" + generated_at_local.replace(":", "").replace("+", "_")
    payload = build_payload(
        _load_json(args.nightly_gate_json),
        _load_json(args.viewer_refresh_json),
        _load_json(args.wetlab_gate_json),
        _load_json(args.refresh_json),
        existing_history_rows=_load_jsonl(args.history_jsonl),
        generated_at_local=generated_at_local,
        run_label=run_label,
    )
    history_path = _resolve(args.history_jsonl)
    out_json = _resolve(args.out_json)
    out_md = _resolve(args.out_md)
    _write_jsonl(history_path, payload["history_rows"])
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    _write_markdown(out_md, payload)


if __name__ == "__main__":
    main()

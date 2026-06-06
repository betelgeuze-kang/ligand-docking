#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

DEFAULT_ANCHOR_JSON = "config/idp_observable_anchors_expanded_v5.json"
DEFAULT_SLICE_JSONS = [
    "runs/idp_tp53_feature_state_v1_shadow_slice_current.json",
    "runs/idp_hnrnpa1_feature_state_v1_shadow_slice_current.json",
    "runs/idp_tau_k18_feature_state_v1_shadow_slice_current.json",
    "runs/idp_page4_feature_state_v1_shadow_slice_current.json",
]
DEFAULT_OUT_JSON = "runs/idp_feature_state_literature_anchor_summary_current.json"
DEFAULT_OUT_CSV = "runs/idp_feature_state_literature_anchor_summary_current.csv"
DEFAULT_OUT_MD = "runs/idp_feature_state_literature_anchor_summary_current.md"


def _resolve(path_like: str) -> Path:
    path = Path(path_like)
    if path.is_absolute():
        return path
    cwd_path = (Path.cwd() / path).resolve()
    if cwd_path.exists():
        return cwd_path
    return (ROOT / path).resolve()


def _read_json(path_like: str) -> dict[str, Any]:
    with _resolve(path_like).open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _infer_target_name(path: Path, payload: dict[str, Any], anchors: dict[str, Any]) -> str:
    summary = dict(payload.get("summary", {}) or {})
    target_name = str(summary.get("target_name", "") or "")
    if target_name:
        return target_name
    stem = path.name
    stem = stem.removeprefix("idp_")
    stem = stem.removesuffix("_feature_state_v1_shadow_slice_current.json")
    if stem in anchors:
        return stem
    prefix_matches = [name for name in anchors if name.startswith(stem) or stem.startswith(name)]
    if len(prefix_matches) == 1:
        return prefix_matches[0]
    return stem


def build_payload(anchor_payload: dict[str, Any], slice_payloads: list[tuple[Path, dict[str, Any]]]) -> dict[str, Any]:
    anchors = dict(anchor_payload.get("targets", {}) or {})
    rows: list[dict[str, Any]] = []
    for path, payload in slice_payloads:
        summary = dict(payload.get("summary", {}) or {})
        target_name = _infer_target_name(path, payload, anchors)
        anchor_meta = dict(anchors.get(target_name, {}) or {})
        anchor_source = str(anchor_meta.get("source", "missing_anchor"))
        anchor_kind = str(((anchor_meta.get("provenance", {}) or {}).get("kind", "")) or "")
        is_provisional = anchor_source == "branch_family_provisional"
        rows.append(
            {
                "target_name": target_name,
                "anchor_source": anchor_source,
                "anchor_kind": anchor_kind,
                "is_literature_anchor": int(not is_provisional),
                "changed_row_count": int(summary.get("changed_row_count", 0) or 0),
                "target_count": int(summary.get("target_count", 0) or 0),
                "provisional_anchor_row_count": int(summary.get("provisional_anchor_row_count", 0) or 0),
                "would_change_state_count": int(summary.get("would_change_state_count", 0) or 0),
                "would_change_gate_count": int(summary.get("would_change_gate_count", 0) or 0),
                "anchor_feature_count": int(summary.get("anchor_feature_count", 0) or 0),
                "smoothed_feature_count": int(summary.get("smoothed_feature_count", 0) or 0),
                "kalman_status": str(summary.get("kalman_status", "")),
                "kalman_mode": str(summary.get("kalman_mode", "")),
            }
        )
    rows.sort(key=lambda r: (r["is_literature_anchor"] == 0, r["target_name"]))
    literature_rows = [row for row in rows if row["is_literature_anchor"] == 1]
    summary = {
        "slice_count": int(len(rows)),
        "literature_anchor_slice_count": int(len(literature_rows)),
        "literature_anchor_targets": [row["target_name"] for row in literature_rows],
        "literature_anchor_changed_slice_count": int(sum(1 for row in literature_rows if row["changed_row_count"] > 0)),
        "literature_anchor_would_change_state_count": int(sum(row["would_change_state_count"] for row in literature_rows)),
        "literature_anchor_would_change_gate_count": int(sum(row["would_change_gate_count"] for row in literature_rows)),
        "provisional_slice_count": int(sum(1 for row in rows if row["is_literature_anchor"] == 0)),
        "next_required_step": (
            "Use the literature-anchor target set to build a subset holdout scaffold, then run feature_state_v1 shadow on that subset before considering any promotion."
        ),
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    rows = payload["rows"]
    lines = [
        "# IDP Literature-Anchor Feature/State Slice Summary",
        "",
        f"- slice_count: `{summary['slice_count']}`",
        f"- literature_anchor_slice_count: `{summary['literature_anchor_slice_count']}`",
        f"- literature_anchor_changed_slice_count: `{summary['literature_anchor_changed_slice_count']}`",
        f"- literature_anchor_would_change_state_count: `{summary['literature_anchor_would_change_state_count']}`",
        f"- literature_anchor_would_change_gate_count: `{summary['literature_anchor_would_change_gate_count']}`",
        f"- provisional_slice_count: `{summary['provisional_slice_count']}`",
        "",
        "## Literature-Anchor Targets",
        "",
        f"- `{', '.join(summary['literature_anchor_targets'])}`",
        "",
        "## Slices",
        "",
        "| target | anchor_source | lit | changed | state | gate | provisional_rows | anchor_features | smoothed_features |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in rows:
        lines.append(
            f"| {row['target_name']} | {row['anchor_source']} | {row['is_literature_anchor']} | {row['changed_row_count']} | {row['would_change_state_count']} | {row['would_change_gate_count']} | {row['provisional_anchor_row_count']} | {row['anchor_feature_count']} | {row['smoothed_feature_count']} |"
        )
    lines.extend(["", "## Next Step", "", f"- {summary['next_required_step']}"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Summarize literature-anchor IDP feature/state shadow slices.")
    ap.add_argument("--anchor-json", default=DEFAULT_ANCHOR_JSON)
    ap.add_argument("--slice-json", action="append", default=[])
    ap.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    ap.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    ap.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return ap.parse_args()


def main() -> None:
    args = parse_args()
    slice_jsons = list(args.slice_json) if args.slice_json else list(DEFAULT_SLICE_JSONS)
    payload = build_payload(
        _read_json(args.anchor_json),
        [(_resolve(path_like), _read_json(path_like)) for path_like in slice_jsons],
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

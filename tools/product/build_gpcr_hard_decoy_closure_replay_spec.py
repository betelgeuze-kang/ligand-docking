#!/usr/bin/env python3
"""Build the GPCR hard-decoy closure replay spec from candidate sweep evidence.

Read-only: this does not run scoring or change the authoritative suite. It
turns the best local retained ranking candidate into a concrete acceptance spec
for the next replay/rescore attempt.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]

DEFAULT_SWEEP_JSON = "runs/gpcr_hard_decoy_candidate_sweep_current.json"
DEFAULT_OUT_JSON = "runs/gpcr_hard_decoy_closure_replay_spec_current.json"
DEFAULT_OUT_MD = "runs/gpcr_hard_decoy_closure_replay_spec_current.md"
DEFAULT_OUT_CSV = "runs/gpcr_hard_decoy_closure_replay_spec_current.csv"

PACKET_TYPE = "gpcr_hard_decoy_closure_replay_spec"
SCHEMA_VERSION = "gpcr_hard_decoy_closure_replay_spec_v1"

CLAIM_BOUNDARY = (
    "GPCR hard-decoy closure replay spec only; it converts local candidate-sweep evidence into exact next-run "
    "acceptance targets. It does not run scoring, regenerate decoys, restore files, relax thresholds, promote a "
    "broad GPCR claim, fetch external data, or mutate external state."
)

_READ_ONLY_FLAGS = {
    "execution_enabled": False,
    "external_state_mutated": False,
    "scoring_execution_enabled": False,
    "threshold_relaxation_enabled": False,
    "claim_promotion_allowed": False,
}

_CSV_COLUMNS = [
    "target_id",
    "target_status",
    "target_green",
    "best_candidate_path",
    "current_decoys_above_positive_count",
    "required_decoys_above_positive_count",
    "decoys_above_delta_needed",
    "current_anchor_margin_a",
    "required_anchor_margin_min_a",
    "anchor_margin_delta_needed_a",
    "positive_target_rank",
    "positive_anchor_distance_a",
    "top_decoy_anchor_distance_a",
    "top_decoy_ligand_id",
    "blockers",
    "recommended_next_local_action",
    "execution_enabled",
    "external_state_mutated",
    "scoring_execution_enabled",
    "threshold_relaxation_enabled",
    "claim_promotion_allowed",
]


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _display(path_like: str | Path) -> str:
    text = _text(path_like)
    if not text:
        return ""
    path = Path(text)
    if path.is_absolute():
        try:
            return str(path.relative_to(ROOT))
        except ValueError:
            return str(path)
    return text


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _float(value: Any) -> float | None:
    try:
        return None if value in (None, "") else float(value)
    except (TypeError, ValueError):
        return None


def _int(value: Any) -> int | None:
    try:
        return None if value in (None, "") else int(float(value))
    except (TypeError, ValueError):
        return None


def _read_json(path_like: str | Path) -> dict[str, Any]:
    path = _resolve(path_like)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _best_candidate(candidates: list[dict[str, Any]]) -> dict[str, Any]:
    return max(
        candidates,
        key=lambda row: (
            int(row.get("metric_gate_ready") is True),
            int(row.get("target_green_count") or 0),
            -int(row.get("target_blocker_count") or 0),
        ),
        default={},
    )


def _row_action(row: dict[str, Any]) -> str:
    blockers = set(row["blockers"])
    if not blockers:
        return "preserve_green_target_in_next_replay"
    if "decoys_above_positive_present" in blockers and "decoy_over_anchored_vs_positive" in blockers:
        return "rerun_target_rescore_to_rank_positive_first_and_restore_positive_anchor_margin"
    if "decoys_above_positive_present" in blockers:
        return "rerun_target_rescore_to_reduce_decoys_above_positive_to_zero"
    if "decoy_over_anchored_vs_positive" in blockers:
        return "rerun_target_rescore_to_restore_nonnegative_anchor_margin"
    if "top_decoy_anchor_distance_missing" in blockers or "top_decoy_missing_from_candidate_rows" in blockers:
        return "restore_full_rows_or_replay_until_top_decoy_anchor_is_observed"
    return "repair_target_evidence_then_rerun_candidate_sweep"


def _target_spec(target: dict[str, Any], *, best_candidate_path: str) -> dict[str, Any]:
    current_decoys = _int(target.get("decoys_above_positive_count"))
    current_margin = _float(target.get("anchor_margin_a"))
    decoys_delta = None if current_decoys is None else max(0, current_decoys)
    margin_delta = None if current_margin is None else max(0.0, -current_margin)
    row = {
        "target_id": _text(target.get("target_id")),
        "target_status": _text(target.get("target_status")),
        "target_green": bool(target.get("target_green") is True),
        "best_candidate_path": best_candidate_path,
        "current_decoys_above_positive_count": current_decoys,
        "required_decoys_above_positive_count": 0,
        "decoys_above_delta_needed": decoys_delta,
        "current_anchor_margin_a": current_margin,
        "required_anchor_margin_min_a": 0.0,
        "anchor_margin_delta_needed_a": margin_delta,
        "positive_target_rank": target.get("positive_target_rank"),
        "positive_anchor_distance_a": target.get("positive_anchor_distance_a"),
        "top_decoy_anchor_distance_a": target.get("top_decoy_anchor_distance_a"),
        "top_decoy_ligand_id": _text(target.get("top_decoy_ligand_id")),
        "blockers": list(target.get("blockers") or []),
        **_READ_ONLY_FLAGS,
    }
    row["recommended_next_local_action"] = _row_action(row)
    return row


def build_gpcr_hard_decoy_closure_replay_spec(
    *,
    sweep_json: str | Path = DEFAULT_SWEEP_JSON,
) -> dict[str, Any]:
    sweep_path = _resolve(sweep_json)
    sweep = _read_json(sweep_path)
    sweep_summary = sweep.get("summary") if isinstance(sweep.get("summary"), dict) else {}
    candidates = [row for row in sweep.get("candidates", []) or [] if isinstance(row, dict)]
    best = _best_candidate(candidates)
    best_candidate_path = _text(best.get("candidate_path"))
    target_rows = [
        _target_spec(target, best_candidate_path=best_candidate_path)
        for target in best.get("targets", [])
        if isinstance(target, dict)
    ]
    remaining_targets = [row["target_id"] for row in target_rows if not row["target_green"]]
    spec_ready = bool(best and target_rows and not sweep_summary.get("gpcr_actual_closure_ready"))
    status = (
        "gpcr_hard_decoy_closure_replay_spec_ready"
        if spec_ready
        else "blocked_gpcr_hard_decoy_closure_replay_spec_missing_sweep"
    )
    summary = {
        "packet_type": PACKET_TYPE,
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "spec_ready": spec_ready,
        "sweep_json": _display(sweep_path),
        "sweep_status": _text(sweep_summary.get("status")),
        "gpcr_actual_closure_ready": bool(sweep_summary.get("gpcr_actual_closure_ready") is True),
        "best_candidate_path": best_candidate_path,
        "best_candidate_metric_gate_ready": bool(best.get("metric_gate_ready") is True),
        "best_candidate_target_green_count": int(best.get("target_green_count") or 0),
        "required_target_count": int(sweep_summary.get("required_target_count") or len(target_rows)),
        "remaining_target_count": len(remaining_targets),
        "remaining_target_ids": remaining_targets,
        "next_required_step": (
            "Run a targeted replay/rescore that preserves the best candidate's metric gate and green targets while "
            "clearing the remaining target rows in this spec."
            if spec_ready
            else "Regenerate the GPCR candidate sweep, then rebuild this replay spec."
        ),
        "claim_boundary": CLAIM_BOUNDARY,
        **_READ_ONLY_FLAGS,
    }
    return {
        "packet_type": PACKET_TYPE,
        "schema_version": SCHEMA_VERSION,
        "summary": summary,
        "rows": target_rows,
        "claim_boundary": CLAIM_BOUNDARY,
    }


def _fmt(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, float):
        return f"{value:.12g}"
    if isinstance(value, list):
        return ";".join(str(item) for item in value)
    return str(value)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=_CSV_COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow({column: _fmt(row.get(column)) for column in _CSV_COLUMNS})


def _render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# GPCR Hard-Decoy Closure Replay Spec",
        "",
        f"- status: `{summary['status']}`",
        f"- best_candidate_path: `{summary['best_candidate_path'] or '(none)'}`",
        f"- best_candidate_metric_gate_ready: `{str(summary['best_candidate_metric_gate_ready']).lower()}`",
        f"- best_candidate_target_green_count: `{summary['best_candidate_target_green_count']}` / `{summary['required_target_count']}`",
        f"- remaining_target_ids: `{', '.join(summary['remaining_target_ids']) or '(none)'}`",
        "",
        "| target | status | decoys delta | anchor delta A | action |",
        "| --- | --- | ---: | ---: | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            "| `{target}` | `{status}` | `{decoys}` | `{anchor}` | `{action}` |".format(
                target=row["target_id"],
                status=row["target_status"],
                decoys=_fmt(row["decoys_above_delta_needed"]),
                anchor=_fmt(row["anchor_margin_delta_needed_a"]),
                action=row["recommended_next_local_action"],
            )
        )
    lines.extend(["", "## Claim Boundary", "", CLAIM_BOUNDARY, ""])
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build the GPCR hard-decoy closure replay spec.")
    parser.add_argument("--sweep-json", default=DEFAULT_SWEEP_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    args = parser.parse_args(argv)

    payload = build_gpcr_hard_decoy_closure_replay_spec(sweep_json=args.sweep_json)
    out_json = _resolve(args.out_json)
    out_md = _resolve(args.out_md)
    out_csv = _resolve(args.out_csv)
    _write_json(out_json, payload)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text(_render_markdown(payload), encoding="utf-8")
    _write_csv(out_csv, payload["rows"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

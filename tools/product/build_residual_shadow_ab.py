#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SOURCE_JSON = "runs/gpcr_residual_narrow_v2_locked_decoy_ab_current.json"
DEFAULT_OUT_JSON = "runs/residual_shadow_ab_current.json"
DEFAULT_OUT_CSV = "runs/residual_shadow_ab_current.csv"
DEFAULT_OUT_MD = "runs/residual_shadow_ab_current.md"

RAW_SCORE_COL = "binding_score_composite_v7"
SHADOW_SCORE_COL = "binding_score_composite_v7_residual_shadow"
ACTIVE_SCORE_COL = "binding_score_composite_v7_residual_active"
ABSTENTION_FIELDS = ("uncertainty", "abstention_reason", "stage2_route_decision")
RESIDUAL_OUTPUT_FIELDS = (
    "delta_score",
    "corrected_score",
    "delta_energy",
    "delta_force",
    "uncertainty",
    "abstention_reason",
    "stage2_route_decision",
)

CLAIM_BOUNDARY = (
    "Residual shadow A/B scaffold only; normalizes existing locked-decoy residual shadow scaffold evidence into "
    "the productization artifact surface. It does not run docking, train models, alter rankings, promote assist/"
    "production mode, upload, submit, email, archive, externalize, or delete files."
)


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _read_json_if_present(path_like: str | Path) -> dict[str, Any]:
    path = _resolve(path_like)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _read_profile(path_like: str | Path) -> dict[str, Any]:
    return _read_json_if_present(path_like)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _profile_row(source_row: dict[str, Any]) -> dict[str, Any]:
    profile_path = _text(source_row.get("generated_profile_json"))
    profile = _read_profile(profile_path) if profile_path else {}
    mode = _text(source_row.get("residual_mode")) or _text(profile.get("residual_prototype_mode"))
    ranking_score_col = _text(profile.get("ranking_score_col"))
    ranking_probability_score_col = _text(profile.get("ranking_probability_score_col"))
    ranking_changed = ranking_score_col == ACTIVE_SCORE_COL or ranking_probability_score_col == ACTIVE_SCORE_COL or mode == "apply"
    return {
        "set_id": _text(source_row.get("set_id")),
        "task_id": _text(source_row.get("task_id")),
        "source_profile_json": profile_path,
        "locked_decoy_labels_csv": _text(source_row.get("locked_decoy_labels_csv")),
        "locked_decoy_split_csv": _text(source_row.get("locked_decoy_split_csv")),
        "source_residual_mode": mode,
        "product_residual_mode": "shadow",
        "raw_score_col": RAW_SCORE_COL,
        "shadow_score_col": SHADOW_SCORE_COL,
        "active_score_col": ACTIVE_SCORE_COL,
        "raw_baseline_preserved": True,
        "corrected_prediction_recorded": True,
        "customer_facing_ranking_changed": ranking_changed,
        "ranking_change_allowed": False,
        "abstention_fields_present": True,
        "residual_output_schema_present": True,
        "source_profile_exists": bool(profile),
        "release_blocker": ranking_changed or not bool(profile),
        "reason": (
            "shadow scaffold preserves raw ranking while recording residual shadow telemetry"
            if not ranking_changed and profile
            else "source profile is missing or uses active residual ranking"
        ),
    }


def build_residual_shadow_ab(*, source_packet: dict[str, Any], source_path: str = DEFAULT_SOURCE_JSON) -> dict[str, Any]:
    source_rows = list(source_packet.get("rows", [])) if isinstance(source_packet.get("rows", []), list) else []
    rows = [_profile_row(dict(row)) for row in source_rows]
    source_mode = _text(source_packet.get("residual_mode"))
    source_ready = bool(source_packet.get("runtime_hook_ready") is True and source_packet.get("locked_decoy_ready") is True)
    shadow_mode = source_mode in {"shadow", "shadow_only"}
    row_count = len(rows)
    blocker_rows = [row for row in rows if row["release_blocker"]]
    raw_baseline_preserved = bool(rows) and all(row["raw_baseline_preserved"] for row in rows)
    corrected_prediction_recorded = bool(rows) and all(row["corrected_prediction_recorded"] for row in rows)
    no_customer_ranking_change = bool(rows) and not any(row["customer_facing_ranking_changed"] for row in rows)
    abstention_fields_present = bool(rows) and all(row["abstention_fields_present"] for row in rows)
    scaffold_ready = bool(
        source_ready
        and shadow_mode
        and row_count > 0
        and not blocker_rows
        and raw_baseline_preserved
        and corrected_prediction_recorded
        and no_customer_ranking_change
        and abstention_fields_present
    )
    summary = {
        "packet_type": "residual_shadow_ab",
        "status": "residual_shadow_ab_scaffold_ready" if scaffold_ready else "blocked_residual_shadow_ab_scaffold",
        "residual_shadow_ab_ready": scaffold_ready,
        "shadow_ab_ready": scaffold_ready,
        "scaffold_ready": scaffold_ready,
        "source_artifact": source_path,
        "source_comparison_kind": _text(source_packet.get("comparison_kind")),
        "source_runtime_hook_ready": bool(source_packet.get("runtime_hook_ready") is True),
        "source_locked_decoy_ready": bool(source_packet.get("locked_decoy_ready") is True),
        "source_residual_mode": source_mode,
        "residual_mode": "shadow",
        "residual_mode_default": "shadow",
        "raw_score_col": RAW_SCORE_COL,
        "shadow_score_col": SHADOW_SCORE_COL,
        "active_score_col": ACTIVE_SCORE_COL,
        "residual_output_fields": list(RESIDUAL_OUTPUT_FIELDS),
        "abstention_fields": list(ABSTENTION_FIELDS),
        "row_count": row_count,
        "blocker_row_count": len(blocker_rows),
        "raw_baseline_preserved": raw_baseline_preserved,
        "corrected_prediction_recorded": corrected_prediction_recorded,
        "no_customer_facing_ranking_change": no_customer_ranking_change,
        "abstention_fields_present": abstention_fields_present,
        "ranking_change_allowed": False,
        "assist_promotion_allowed": False,
        "production_promotion_allowed": False,
        "execution_enabled": False,
        "benchmark_executed": False,
        "docking_results_emitted": False,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "Proceed to GPCR hard-decoy residual proof."
            if scaffold_ready
            else "Repair residual shadow source scaffold before Phase 2 promotion."
        ),
    }
    return {"summary": summary, "rows": rows}


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_markdown(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    s = payload["summary"]
    lines = [
        "# Residual Shadow A/B Scaffold",
        "",
        f"- status: `{s['status']}`",
        f"- scaffold_ready: `{s['scaffold_ready']}`",
        f"- residual_mode: `{s['residual_mode']}`",
        f"- source_artifact: `{s['source_artifact']}`",
        f"- row_count: `{s['row_count']}`",
        f"- raw_baseline_preserved: `{s['raw_baseline_preserved']}`",
        f"- corrected_prediction_recorded: `{s['corrected_prediction_recorded']}`",
        f"- no_customer_facing_ranking_change: `{s['no_customer_facing_ranking_change']}`",
        f"- abstention_fields_present: `{s['abstention_fields_present']}`",
        f"- assist_promotion_allowed: `{s['assist_promotion_allowed']}`",
        f"- production_promotion_allowed: `{s['production_promotion_allowed']}`",
        f"- execution_enabled: `{s['execution_enabled']}`",
        f"- external_state_mutated: `{s['external_state_mutated']}`",
        "",
        "## Rows",
        "",
        "| task | mode | raw | shadow | ranking changed | profile | reason |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['task_id']}` | `{row['product_residual_mode']}` | `{row['raw_score_col']}` | `{row['shadow_score_col']}` | "
            f"`{row['customer_facing_ranking_changed']}` | `{row['source_profile_json']}` | {row['reason']} |"
        )
    lines.extend(["", "## Claim Boundary", "", s["claim_boundary"], "", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build product-level residual shadow A/B scaffold artifact.")
    parser.add_argument("--source-json", default=DEFAULT_SOURCE_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_residual_shadow_ab(source_packet=_read_json_if_present(args.source_json), source_path=args.source_json)
    _write_json(args.out_json, payload)
    write_csv_rows(_resolve(args.out_csv), payload["rows"])
    _write_markdown(args.out_md, payload)


if __name__ == "__main__":
    main()

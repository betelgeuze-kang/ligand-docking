#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]

DEFAULT_BASE_SUMMARY_JSON = "runs/idp_3bead_holdout_v7_literature_anchor_kfshadow_r1_summary.json"
DEFAULT_BASE_DISAGREEMENT_JSON = "runs/idp_literature_anchor_kfshadow_disagreement_summary_current.json"
DEFAULT_CANDIDATE_SUMMARY_JSON = "runs/idp_3bead_holdout_v7_literature_anchor_kfrgsasa_r1_summary.json"
DEFAULT_CANDIDATE_DISAGREEMENT_JSON = "runs/idp_literature_anchor_kfrgsasa_disagreement_summary_current.json"
DEFAULT_OUT_JSON = "runs/idp_literature_anchor_feature_mask_comparison_current.json"
DEFAULT_OUT_CSV = "runs/idp_literature_anchor_feature_mask_comparison_current.csv"
DEFAULT_OUT_MD = "runs/idp_literature_anchor_feature_mask_comparison_current.md"


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


def _fold_passes(summary: dict[str, Any]) -> int:
    return int(summary.get("corrected_pass_folds", summary.get("baseline_pass_folds", 0)) or 0)


def _fold_count(summary: dict[str, Any]) -> int:
    return int(summary.get("fold_count", 0) or 0)


def _row(mode: str, summary: dict[str, Any], disagreement: dict[str, Any], feature_mask: str) -> dict[str, Any]:
    overall = dict(disagreement.get("overall", {}) or {})
    return {
        "mode": mode,
        "feature_mask": feature_mask,
        "fold_count": _fold_count(summary),
        "corrected_pass_folds": _fold_passes(summary),
        "combined_gate_pass": bool(summary.get("combined_gate_pass", False)),
        "state_changes": int(overall.get("would_have_changed_state_count", 0) or 0),
        "gate_changes": int(overall.get("would_have_changed_gate_count", 0) or 0),
        "feature_state_shadow_rows": int(overall.get("feature_state_shadow_row_count", 0) or 0),
    }


def build_payload(
    base_summary: dict[str, Any],
    base_disagreement: dict[str, Any],
    candidate_summary: dict[str, Any],
    candidate_disagreement: dict[str, Any],
) -> dict[str, Any]:
    rows = [
        _row("baseline_subset", base_summary, base_disagreement, "all"),
        _row("candidate_subset", candidate_summary, candidate_disagreement, "rg_sasa_only"),
    ]
    candidate = rows[1]
    recommended = (
        candidate["combined_gate_pass"]
        and candidate["gate_changes"] == 0
        and candidate["corrected_pass_folds"] >= rows[0]["corrected_pass_folds"]
    )
    decision = "prefer_rg_sasa_only" if recommended else "keep_all_mask_baseline"
    reason = (
        "rg_sasa_only keeps gate changes at zero and matches or improves corrected-pass folds while narrowing the smoothing surface."
        if recommended
        else "Keep the broader all-feature mask as the reference until the narrower rg_sasa_only subset shows at least the same corrected-pass folds with zero gate changes."
    )
    return {"decision": decision, "reason": reason, "rows": rows}


def _write_md(path: Path, payload: dict[str, Any]) -> None:
    lines = [
        "# IDP Literature-Anchor Feature Mask Comparison",
        "",
        f"- decision: `{payload['decision']}`",
        f"- reason: {payload['reason']}",
        "",
        "| mode | feature_mask | fold_count | corrected_pass_folds | combined_gate_pass | state_changes | gate_changes | feature_state_shadow_rows |",
        "| --- | --- | ---: | ---: | --- | ---: | ---: | ---: |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['mode']}` | `{row['feature_mask']}` | {row['fold_count']} | {row['corrected_pass_folds']} | "
            f"`{row['combined_gate_pass']}` | {row['state_changes']} | {row['gate_changes']} | {row['feature_state_shadow_rows']} |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Compare literature-anchor subset runs across feature masks.")
    p.add_argument("--base-summary-json", default=DEFAULT_BASE_SUMMARY_JSON)
    p.add_argument("--base-disagreement-json", default=DEFAULT_BASE_DISAGREEMENT_JSON)
    p.add_argument("--candidate-summary-json", default=DEFAULT_CANDIDATE_SUMMARY_JSON)
    p.add_argument("--candidate-disagreement-json", default=DEFAULT_CANDIDATE_DISAGREEMENT_JSON)
    p.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    p.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    p.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return p


def main() -> None:
    args = build_parser().parse_args()
    payload = build_payload(
        _read_json(args.base_summary_json),
        _read_json(args.base_disagreement_json),
        _read_json(args.candidate_summary_json),
        _read_json(args.candidate_disagreement_json),
    )
    out_json = _resolve(args.out_json)
    out_csv = _resolve(args.out_csv)
    out_md = _resolve(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    _write_csv(out_csv, payload["rows"])
    _write_md(out_md, payload)


if __name__ == "__main__":
    main()

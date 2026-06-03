#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from betelgeuze_product.lit_pcba_scorecard import build_lit_pcba_scorecard, write_scorecard
from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SCORES_CSV = "runs/lit_pcba_scores_current.csv"
DEFAULT_LABELS_CSV = "runs/lit_pcba_labels_current.csv"
DEFAULT_OUT_JSON = "runs/lit_pcba_scorecard_current.json"
DEFAULT_OUT_MD = "runs/lit_pcba_scorecard_current.md"
DEFAULT_ROW_CSV = "runs/lit_pcba_scorecard_row_current.csv"
DEFAULT_DETAIL_CSV = "runs/lit_pcba_ranking_eval_rows_current.csv"
DEFAULT_TOPK_CSV = "runs/lit_pcba_ranking_eval_topk_current.csv"
DEFAULT_UNIQUE_CSV = "runs/lit_pcba_ranking_eval_unique_current.csv"


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _write_markdown(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    s = payload["summary"]
    lines = [
        "# LIT-PCBA Scorecard",
        "",
        f"- status: `{s['status']}`",
        f"- pass: `{s['pass']}`",
        f"- blocker_count: `{s['blocker_count']}`",
        f"- suite_id: `{s['suite_id']}`",
        f"- dataset_source_url: `{s['dataset_source_url']}`",
        f"- primary_metric: `{s['primary_metric']}`",
        f"- primary_metric_value: `{s['primary_metric_value']}`",
        f"- primary_metric_threshold: `{s['primary_metric_threshold']}`",
        f"- eval_unique_keys: `{s['eval_unique_keys']}`",
        f"- min_eval_unique_keys: `{s['min_eval_unique_keys']}`",
        f"- roc_auc: `{s['roc_auc']}`",
        f"- pr_auc: `{s['pr_auc']}`",
        f"- bedroc_alpha20: `{s['bedroc_alpha20']}`",
        f"- scorecard_json: `{s['scorecard_json']}`",
        f"- ranking_eval_json: `{s.get('ranking_eval_json', '')}`",
        f"- regression_baseline_ref: `{s['regression_baseline_ref']}`",
        f"- external_state_mutated: `{s['external_state_mutated']}`",
        "",
        "## Blockers",
        "",
    ]
    blockers = s.get("blockers") or []
    if blockers:
        lines.extend(f"- `{blocker}`" for blocker in blockers)
    else:
        lines.append("- none")
    lines.extend(["", "## Claim Boundary", "", s["claim_boundary"], "", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a LIT-PCBA public benchmark scorecard from local score/label CSVs.")
    parser.add_argument("--scores-csv", default=DEFAULT_SCORES_CSV)
    parser.add_argument("--labels-csv", default=DEFAULT_LABELS_CSV)
    parser.add_argument("--score-col", default="binding_score")
    parser.add_argument("--join-target-col", default="target")
    parser.add_argument("--join-ligand-col", default="ligand_id")
    parser.add_argument("--binder-col", default="is_binder")
    parser.add_argument("--lower-better", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--min-eval-unique-keys", type=int, default=200)
    parser.add_argument("--primary-metric-threshold", type=float, default=1.2)
    parser.add_argument("--regression-baseline-ref", default="lit_pcba:pending_baseline")
    parser.add_argument("--bootstrap-n", type=int, default=100)
    parser.add_argument("--run-command", default="")
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    parser.add_argument("--row-csv", default=DEFAULT_ROW_CSV)
    parser.add_argument("--out-detail-csv", default=DEFAULT_DETAIL_CSV)
    parser.add_argument("--out-topk-csv", default=DEFAULT_TOPK_CSV)
    parser.add_argument("--out-unique-csv", default=DEFAULT_UNIQUE_CSV)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    run_command = args.run_command or (
        "python3 tools/build_lit_pcba_scorecard.py "
        f"--scores-csv {args.scores_csv} --labels-csv {args.labels_csv} --score-col {args.score_col}"
    )
    payload = build_lit_pcba_scorecard(
        scores_csv=_resolve(args.scores_csv),
        labels_csv=_resolve(args.labels_csv),
        score_col=args.score_col,
        lower_better=args.lower_better,
        join_target_col=args.join_target_col,
        join_ligand_col=args.join_ligand_col,
        binder_col=args.binder_col,
        min_eval_unique_keys=args.min_eval_unique_keys,
        primary_metric_threshold=args.primary_metric_threshold,
        regression_baseline_ref=args.regression_baseline_ref,
        bootstrap_n=args.bootstrap_n,
        run_command=run_command,
        out_json=_resolve(args.out_json),
        out_md=_resolve(args.out_md),
        out_detail_csv=_resolve(args.out_detail_csv),
        out_topk_csv=_resolve(args.out_topk_csv),
        out_unique_csv=_resolve(args.out_unique_csv),
    )
    write_scorecard(_resolve(args.out_json), payload)
    write_csv_rows(_resolve(args.row_csv), [payload["scorecard_row"]])
    _write_markdown(args.out_md, payload)


if __name__ == "__main__":
    main()

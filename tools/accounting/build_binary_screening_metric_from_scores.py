#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _text(value: Any) -> str:
    return str(value or "").strip()


def _float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return [{str(k): _text(v) for k, v in row.items()} for row in csv.DictReader(handle)]


def _roc_auc(pairs: list[tuple[float, int]], *, lower_better: bool) -> float:
    positives = [score for score, label in pairs if int(label) == 1]
    negatives = [score for score, label in pairs if int(label) == 0]
    if not positives or not negatives:
        return 0.0
    wins = 0.0
    for positive in positives:
        for negative in negatives:
            if positive == negative:
                wins += 0.5
            elif (positive < negative) if lower_better else (positive > negative):
                wins += 1.0
    return wins / (len(positives) * len(negatives))


def build_metric(args: argparse.Namespace) -> dict[str, Any]:
    scores_path = _resolve(args.scores_csv)
    labels_path = _resolve(args.labels_csv)
    out_json = _resolve(args.out_json)
    out_md = _resolve(args.out_md)
    score_rows = _read_csv(scores_path)
    label_rows = _read_csv(labels_path)
    labels = {
        (_text(row.get(args.target_col)), _text(row.get(args.ligand_col))): int(_float(row.get(args.binder_col)))
        for row in label_rows
        if _text(row.get(args.target_col)) and _text(row.get(args.ligand_col))
    }
    seen: dict[tuple[str, str], tuple[float, int]] = {}
    missing_label_count = 0
    for row in score_rows:
        key = (_text(row.get(args.target_col)), _text(row.get(args.ligand_col)))
        if not key[0] or not key[1] or key in seen:
            continue
        if key not in labels:
            missing_label_count += 1
            continue
        seen[key] = (_float(row.get(args.score_col)), labels[key])

    pairs = list(seen.values())
    positive_count = sum(1 for _, label in pairs if label == 1)
    negative_count = sum(1 for _, label in pairs if label == 0)
    roc_auc = _roc_auc(pairs, lower_better=bool(args.lower_better))
    flipped = _roc_auc(pairs, lower_better=not bool(args.lower_better))
    threshold = _float(args.threshold)
    blockers: list[str] = []
    if not pairs:
        blockers.append("no_scored_labeled_pairs")
    if positive_count <= 0:
        blockers.append("positive_labels_missing")
    if negative_count <= 0:
        blockers.append("negative_labels_missing")
    if roc_auc + 1e-12 < threshold:
        blockers.append("roc_auc_below_threshold")
    summary = {
        "packet_type": "binary_screening_metric_from_scores",
        "suite_id": _text(args.suite_id),
        "status": "binary_screening_metric_pass" if not blockers else "blocked_binary_screening_metric",
        "pass": not blockers,
        "blocker_count": len(blockers),
        "blockers": blockers,
        "scores_csv": str(scores_path),
        "labels_csv": str(labels_path),
        "score_col": _text(args.score_col),
        "metric": "ROC_AUC",
        "primary_metric_value": roc_auc,
        "roc_auc": roc_auc,
        "roc_auc_if_flipped": flipped,
        "threshold": threshold,
        "scored_labeled_pairs": len(pairs),
        "positive_count": positive_count,
        "negative_count": negative_count,
        "missing_label_count": missing_label_count,
        "lower_better": bool(args.lower_better),
        "external_state_mutated": False,
        "next_required_step": (
            "Build the suite scorecard with this ROC_AUC value."
            if not blockers
            else "Improve score orientation/feature weighting or benchmark execution, then rebuild this metric."
        ),
    }
    payload = {"summary": summary}
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text(
        "\n".join(
            [
                "# Binary Screening Metric From Scores",
                "",
                f"- status: `{summary['status']}`",
                f"- suite_id: `{summary['suite_id']}`",
                f"- metric: `{summary['metric']}`",
                f"- primary_metric_value: `{summary['primary_metric_value']}`",
                f"- threshold: `{summary['threshold']}`",
                f"- scored_labeled_pairs: `{summary['scored_labeled_pairs']}`",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return payload


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compute ROC_AUC for a binary screening benchmark result CSV.")
    parser.add_argument("--suite-id", required=True)
    parser.add_argument("--scores-csv", required=True)
    parser.add_argument("--labels-csv", required=True)
    parser.add_argument("--score-col", default="binding_score")
    parser.add_argument("--target-col", default="target")
    parser.add_argument("--ligand-col", default="ligand_id")
    parser.add_argument("--binder-col", default="is_binder")
    parser.add_argument("--threshold", type=float, default=0.6)
    parser.add_argument("--lower-better", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--out-json", default="runs/binary_screening_metric_current.json")
    parser.add_argument("--out-md", default="runs/binary_screening_metric_current.md")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    build_metric(parse_args(argv))


if __name__ == "__main__":
    main()

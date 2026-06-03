from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools import evaluate_ligand_ranking_metrics

SUITE_ID = "lit_pcba_virtual_screening"
BENCHMARK_FAMILY = "protein_ligand_virtual_screening"
DATASET_SOURCE_URL = "https://zenodo.org/records/4588239"
PRIMARY_METRIC = "EF1"
DEFAULT_PRIMARY_METRIC_THRESHOLD = 1.2

CLAIM_BOUNDARY = (
    "LIT-PCBA scorecard only; it evaluates already-materialized score and label CSVs with the local ligand ranking "
    "metric evaluator. It does not download datasets, run docking, alter benchmark labels, submit predictions, send "
    "email, or mutate external state."
)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _float(value: Any) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _int(value: Any) -> int:
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0


def _artifact(path: str | Path) -> str:
    return str(path)


def _metric(eval_payload: dict[str, Any], key: str) -> float:
    for section in ("metrics_unique", "metrics", "metrics_ood_unique"):
        metrics = eval_payload.get(section)
        if isinstance(metrics, dict) and key in metrics:
            return _float(metrics.get(key))
    return 0.0


def _scorecard_row(summary: dict[str, Any]) -> dict[str, Any]:
    return {
        "suite_id": SUITE_ID,
        "benchmark_family": BENCHMARK_FAMILY,
        "dataset_source_url": DATASET_SOURCE_URL,
        "scorecard_json": summary.get("scorecard_json", ""),
        "status": "pass" if summary.get("status") == "lit_pcba_scorecard_pass" else "fail",
        "primary_metric": PRIMARY_METRIC,
        "primary_metric_value": summary.get("primary_metric_value", 0.0),
        "primary_metric_threshold": summary.get("primary_metric_threshold", DEFAULT_PRIMARY_METRIC_THRESHOLD),
        "regression_baseline_ref": summary.get("regression_baseline_ref", ""),
        "run_command": summary.get("run_command", ""),
    }


def _blocked_summary(
    *,
    blockers: list[str],
    scores_csv: str | Path,
    labels_csv: str | Path,
    out_json: str | Path,
    primary_metric_threshold: float,
    min_eval_unique_keys: int,
    regression_baseline_ref: str,
    run_command: str,
) -> dict[str, Any]:
    blocker_text = ",".join(blockers)
    missing_inputs = [
        _artifact(path)
        for path in (scores_csv, labels_csv)
        if not Path(path).exists()
    ]
    return {
        "packet_type": "lit_pcba_scorecard",
        "suite_id": SUITE_ID,
        "status": "blocked_lit_pcba_scorecard",
        "blocker_count": len(blockers),
        "blockers": blockers,
        "dataset_source_url": DATASET_SOURCE_URL,
        "scores_csv": _artifact(scores_csv),
        "labels_csv": _artifact(labels_csv),
        "scorecard_json": _artifact(out_json),
        "operator_input_artifacts": f"{_artifact(scores_csv)};{_artifact(labels_csv)}",
        "operator_output_artifacts": _artifact(out_json),
        "missing_input_artifacts": ";".join(missing_inputs),
        "primary_metric": PRIMARY_METRIC,
        "primary_metric_value": 0.0,
        "primary_metric_threshold": float(primary_metric_threshold),
        "threshold": float(primary_metric_threshold),
        "metric_gap_to_threshold": 0.0 - float(primary_metric_threshold),
        "min_eval_unique_keys": int(min_eval_unique_keys),
        "eval_unique_keys": 0,
        "roc_auc": 0.0,
        "pr_auc": 0.0,
        "bedroc_alpha20": 0.0,
        "regression_baseline_ref": regression_baseline_ref,
        "run_command": run_command,
        "blocker": blocker_text,
        "pass": False,
        "external_state_mutated": False,
        "docking_results_emitted": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": "Materialize LIT-PCBA labels and score CSVs, then rerun this scorecard.",
    }


def build_lit_pcba_scorecard(
    *,
    scores_csv: str | Path,
    labels_csv: str | Path,
    score_col: str,
    out_json: str | Path,
    out_md: str | Path,
    out_detail_csv: str | Path,
    out_topk_csv: str | Path,
    out_unique_csv: str | Path,
    lower_better: bool = True,
    join_target_col: str = "target",
    join_ligand_col: str = "ligand_id",
    binder_col: str = "is_binder",
    min_eval_unique_keys: int = 200,
    primary_metric_threshold: float = DEFAULT_PRIMARY_METRIC_THRESHOLD,
    regression_baseline_ref: str = "lit_pcba:pending_baseline",
    bootstrap_n: int = 100,
    run_command: str = "",
) -> dict[str, Any]:
    blockers: list[str] = []
    scores_path = Path(scores_csv)
    labels_path = Path(labels_csv)
    if not scores_path.exists():
        blockers.append("scores_csv_missing")
    if not labels_path.exists():
        blockers.append("labels_csv_missing")
    if not _text(regression_baseline_ref):
        blockers.append("regression_baseline_ref_missing")
    if not _text(run_command):
        blockers.append("run_command_missing")
    if blockers:
        summary = _blocked_summary(
            blockers=blockers,
            scores_csv=scores_csv,
            labels_csv=labels_csv,
            out_json=out_json,
            primary_metric_threshold=primary_metric_threshold,
            min_eval_unique_keys=min_eval_unique_keys,
            regression_baseline_ref=regression_baseline_ref,
            run_command=run_command,
        )
        return {"summary": summary, "scorecard_row": _scorecard_row(summary), "evaluator": {}}

    eval_args = evaluate_ligand_ranking_metrics.build_parser().parse_args(
        [
            "--scores-csv",
            str(scores_csv),
            "--labels-csv",
            str(labels_csv),
            "--score-col",
            score_col,
            "--join-target-col",
            join_target_col,
            "--join-ligand-col",
            join_ligand_col,
            "--binder-col",
            binder_col,
            "--ref-energy-col",
            "",
            "--topk-list",
            "10,20,50,100",
            "--bootstrap-n",
            str(int(bootstrap_n)),
            "--out-detail-csv",
            str(out_detail_csv),
            "--out-topk-csv",
            str(out_topk_csv),
            "--out-unique-csv",
            str(out_unique_csv),
            "--out-json",
            str(Path(out_json).with_suffix(".ranking_eval.json")),
            "--out-md",
            str(Path(out_md).with_suffix(".ranking_eval.md")),
            "--missing-score-policy",
            "worst",
        ]
        + (["--lower-better"] if lower_better else ["--no-lower-better"])
    )
    eval_payload = evaluate_ligand_ranking_metrics.run_eval(eval_args)
    ef1 = _metric(eval_payload, "ef1")
    roc_auc = _metric(eval_payload, "roc_auc")
    pr_auc = _metric(eval_payload, "pr_auc")
    bedroc = _metric(eval_payload, "bedroc_alpha20")
    eval_unique = _int(eval_payload.get("eval_unique_keys"))
    scorecard_blockers: list[str] = []
    if eval_unique < int(min_eval_unique_keys):
        scorecard_blockers.append("eval_unique_keys_below_minimum")
    if ef1 + 1e-12 < float(primary_metric_threshold):
        scorecard_blockers.append("ef1_below_threshold")
    status = "lit_pcba_scorecard_pass" if not scorecard_blockers else "blocked_lit_pcba_scorecard"
    blocker_text = ",".join(scorecard_blockers)
    summary = {
        "packet_type": "lit_pcba_scorecard",
        "suite_id": SUITE_ID,
        "status": status,
        "blocker_count": len(scorecard_blockers),
        "blockers": scorecard_blockers,
        "dataset_source_url": DATASET_SOURCE_URL,
        "scores_csv": _artifact(scores_csv),
        "labels_csv": _artifact(labels_csv),
        "scorecard_json": _artifact(out_json),
        "operator_input_artifacts": f"{_artifact(scores_csv)};{_artifact(labels_csv)}",
        "operator_output_artifacts": (
            f"{_artifact(out_json)};{_artifact(out_detail_csv)};{_artifact(out_topk_csv)};{_artifact(out_unique_csv)}"
        ),
        "missing_input_artifacts": "",
        "ranking_eval_json": eval_payload.get("artifacts", {}).get("summary_json", ""),
        "ranking_eval_md": eval_payload.get("artifacts", {}).get("summary_md", ""),
        "primary_metric": PRIMARY_METRIC,
        "primary_metric_value": ef1,
        "primary_metric_threshold": float(primary_metric_threshold),
        "threshold": float(primary_metric_threshold),
        "metric_gap_to_threshold": ef1 - float(primary_metric_threshold),
        "min_eval_unique_keys": int(min_eval_unique_keys),
        "eval_unique_keys": eval_unique,
        "roc_auc": roc_auc,
        "pr_auc": pr_auc,
        "bedroc_alpha20": bedroc,
        "regression_baseline_ref": regression_baseline_ref,
        "run_command": run_command,
        "blocker": blocker_text,
        "pass": status == "lit_pcba_scorecard_pass",
        "external_state_mutated": False,
        "docking_results_emitted": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "Append the scorecard row to the product public benchmark scorecard intake CSV."
            if status == "lit_pcba_scorecard_pass"
            else "Improve scoring/docking or expand LIT-PCBA coverage, then rerun this scorecard."
        ),
    }
    return {"summary": summary, "scorecard_row": _scorecard_row(summary), "evaluator": eval_payload}


def write_scorecard(path: str | Path, payload: dict[str, Any]) -> None:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")

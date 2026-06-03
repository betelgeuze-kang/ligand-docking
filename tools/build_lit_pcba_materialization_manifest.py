#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from betelgeuze_product.lit_pcba_materialization import build_lit_pcba_materialization_manifest
from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ARCHIVE_PATH = "data/public_benchmarks/lit_pcba/LIT_PCBA_AVE_docked_released.tar.xz"
DEFAULT_EXTRACTED_DIR = "data/public_benchmarks/lit_pcba/LIT_PCBA_AVE_docked_released"
DEFAULT_SOURCE_SCORE_CSV = "data/public_benchmarks/lit_pcba/lit_pcba_source_scores.csv"
DEFAULT_SOURCE_LABEL_CSV = "data/public_benchmarks/lit_pcba/lit_pcba_source_labels.csv"
DEFAULT_OUT_SCORES_CSV = "runs/lit_pcba_scores_current.csv"
DEFAULT_OUT_LABELS_CSV = "runs/lit_pcba_labels_current.csv"
DEFAULT_OUT_JSON = "runs/lit_pcba_materialization_manifest_current.json"
DEFAULT_OUT_CSV = "runs/lit_pcba_materialization_manifest_current.csv"
DEFAULT_OUT_MD = "runs/lit_pcba_materialization_manifest_current.md"


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_markdown(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    s = payload["summary"]
    lines = [
        "# LIT-PCBA Materialization Manifest",
        "",
        f"- status: `{s['status']}`",
        f"- suite_id: `{s['suite_id']}`",
        f"- materialized: `{s['materialized']}`",
        f"- blocker_count: `{s['blocker_count']}`",
        f"- benchmark_family: `{s['benchmark_family']}`",
        f"- dataset_source_url: `{s['dataset_source_url']}`",
        f"- dataset_record_url: `{s['dataset_record_url']}`",
        f"- dataset_doi: `{s['dataset_doi']}`",
        f"- primary_metric: `{s['primary_metric']}`",
        f"- primary_metric_threshold: `{s['primary_metric_threshold']}`",
        f"- archive_filename: `{s['archive_filename']}`",
        f"- archive_md5_expected: `{s['archive_md5_expected']}`",
        f"- archive_path: `{s['archive_path']}`",
        f"- archive_present: `{s['archive_present']}`",
        f"- out_scores_csv: `{s['out_scores_csv']}`",
        f"- out_scores_csv_present: `{s['out_scores_csv_present']}`",
        f"- out_labels_csv: `{s['out_labels_csv']}`",
        f"- out_labels_csv_present: `{s['out_labels_csv_present']}`",
        f"- operator_input_artifacts: `{s['operator_input_artifacts']}`",
        f"- operator_output_artifacts: `{s['operator_output_artifacts']}`",
        f"- missing_input_artifacts: `{s['missing_input_artifacts']}`",
        f"- missing_output_artifacts: `{s['missing_output_artifacts']}`",
        f"- score_row_count: `{s['score_row_count']}`",
        f"- label_row_count: `{s['label_row_count']}`",
        f"- run_command: `{s['run_command']}`",
        f"- scorecard_run_command_template: `{s['scorecard_run_command_template']}`",
        f"- download_executed: `{s['download_executed']}`",
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
    lines.extend(["", "## Checks", "", "| check | status | observed | required |", "| --- | --- | --- | --- |"])
    for row in payload["rows"]:
        lines.append(f"| `{row['check']}` | `{row['status']}` | `{row['observed']}` | `{row['required']}` |")
    lines.extend(["", "## Claim Boundary", "", s["claim_boundary"], "", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a LIT-PCBA local materialization manifest and optionally standardize local score/label CSVs.")
    parser.add_argument("--archive-path", default=DEFAULT_ARCHIVE_PATH)
    parser.add_argument("--extracted-dir", default=DEFAULT_EXTRACTED_DIR)
    parser.add_argument("--source-score-csv", default=DEFAULT_SOURCE_SCORE_CSV)
    parser.add_argument("--source-label-csv", default=DEFAULT_SOURCE_LABEL_CSV)
    parser.add_argument("--out-scores-csv", default=DEFAULT_OUT_SCORES_CSV)
    parser.add_argument("--out-labels-csv", default=DEFAULT_OUT_LABELS_CSV)
    parser.add_argument("--target-col", default="target")
    parser.add_argument("--ligand-col", default="ligand_id")
    parser.add_argument("--score-col", default="binding_score")
    parser.add_argument("--binder-col", default="is_binder")
    parser.add_argument("--verify-md5", action="store_true")
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_lit_pcba_materialization_manifest(
        archive_path=_resolve(args.archive_path),
        extracted_dir=_resolve(args.extracted_dir),
        source_score_csv=_resolve(args.source_score_csv),
        source_label_csv=_resolve(args.source_label_csv),
        out_scores_csv=_resolve(args.out_scores_csv),
        out_labels_csv=_resolve(args.out_labels_csv),
        target_col=args.target_col,
        ligand_col=args.ligand_col,
        score_col=args.score_col,
        binder_col=args.binder_col,
        verify_md5=args.verify_md5,
    )
    _write_json(args.out_json, payload)
    write_csv_rows(_resolve(args.out_csv), payload["rows"])
    _write_markdown(args.out_md, payload)


if __name__ == "__main__":
    main()

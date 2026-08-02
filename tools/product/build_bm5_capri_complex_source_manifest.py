#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from betelgeuze_product.bm5_capri_complex_source_manifest import build_bm5_capri_complex_source_manifest
from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_BM5_DATASET_DIR = "data/public_benchmarks/protein_protein_docking_benchmark_v5"
DEFAULT_BM5_MATERIALIZATION_MANIFEST = "runs/protein_protein_docking_benchmark_v5_materialization_manifest_current.json"
DEFAULT_BM5_RESULT_PROVENANCE_JSON = "runs/protein_protein_docking_benchmark_v5_result_provenance_current.json"
DEFAULT_BM5_SCORECARD_JSON = "runs/protein_protein_docking_benchmark_v5_scorecard_current.json"
DEFAULT_CAPRI_SCORE_SET_SOURCE_MANIFEST = "data/competition_benchmarks/capri_score_set/source_manifest.csv"
DEFAULT_CAPRI_SCORE_SET_CHECKSUM_MANIFEST = "data/competition_benchmarks/capri_score_set/checksums.sha256"
DEFAULT_CAPRI_SCORE_SET_MATERIALIZATION_MANIFEST = "data/competition_benchmarks/capri_score_set/materialization_manifest.json"
DEFAULT_CAPRI_SCORE_SET_SCORECARD_JSON = "runs/capri_score_set_scorecard_current.json"
DEFAULT_OUT_JSON = "runs/bm5_capri_complex_source_manifest_current.json"
DEFAULT_OUT_CSV = "runs/bm5_capri_complex_source_manifest_current.csv"
DEFAULT_OUT_MD = "runs/bm5_capri_complex_source_manifest_current.md"


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_markdown(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    summary = payload["summary"]
    lines = [
        "# BM5/CAPRI Complex Source Manifest",
        "",
        f"- status: `{summary['status']}`",
        f"- suite_id: `{summary['suite_id']}`",
        f"- competition_credibility_ready: `{summary['competition_credibility_ready']}`",
        f"- bm5_complex_benchmark_ready: `{summary['bm5_complex_benchmark_ready']}`",
        f"- bm5_materialization_ready: `{summary['bm5_materialization_ready']}`",
        f"- bm5_checksum_ready: `{summary['bm5_checksum_ready']}`",
        f"- bm5_scorecard_ready: `{summary['bm5_scorecard_ready']}`",
        f"- capri_score_set_ready: `{summary['capri_score_set_ready']}`",
        f"- capri_source_ready: `{summary['capri_source_ready']}`",
        f"- blocker_count: `{summary['blocker_count']}`",
        f"- bm5_zlab_url: `{summary['bm5_zlab_url']}`",
        f"- bm5_publication_url: `{summary['bm5_publication_url']}`",
        f"- capri_ebi_url: `{summary['capri_ebi_url']}`",
        f"- sbgrid_bm5_capri_url: `{summary['sbgrid_bm5_capri_url']}`",
        f"- bm5_publication_docking_entry_count: `{summary['bm5_publication_docking_entry_count']}`",
        f"- bm5_dataset_dir: `{summary['bm5_dataset_dir']}`",
        f"- bm5_materialization_manifest: `{summary['bm5_materialization_manifest']}`",
        f"- bm5_result_provenance_json: `{summary['bm5_result_provenance_json']}`",
        f"- bm5_result_artifact_sha256: `{summary['bm5_result_artifact_sha256']}`",
        f"- bm5_scorecard_json: `{summary['bm5_scorecard_json']}`",
        f"- capri_score_set_source_manifest: `{summary['capri_score_set_source_manifest']}`",
        f"- capri_score_set_checksum_manifest: `{summary['capri_score_set_checksum_manifest']}`",
        f"- capri_score_set_materialization_manifest: `{summary['capri_score_set_materialization_manifest']}`",
        f"- capri_score_set_scorecard_json: `{summary['capri_score_set_scorecard_json']}`",
        f"- raw_data_git_tracked_file_count: `{summary['raw_data_git_tracked_file_count']}`",
        f"- bm5_raw_data_git_tracked_file_count: `{summary['bm5_raw_data_git_tracked_file_count']}`",
        f"- capri_raw_data_git_tracked_file_count: `{summary['capri_raw_data_git_tracked_file_count']}`",
        f"- run_command: `{summary['run_command']}`",
        f"- bm5_materialization_command: `{summary['bm5_materialization_command']}`",
        f"- bm5_proxy_results_command: `{summary['bm5_proxy_results_command']}`",
        f"- bm5_scorecard_command_template: `{summary['bm5_scorecard_command_template']}`",
        f"- capri_score_set_materialization_command_template: `{summary['capri_score_set_materialization_command_template']}`",
        f"- raw_data_custody_plan_json: `{summary['raw_data_custody_plan_json']}`",
        f"- raw_data_custody_plan_csv: `{summary['raw_data_custody_plan_csv']}`",
        f"- raw_data_custody_plan_command: `{summary['raw_data_custody_plan_command']}`",
        f"- raw_data_committed: `{summary['raw_data_committed']}`",
        f"- download_executed: `{summary['download_executed']}`",
        f"- external_state_mutated: `{summary['external_state_mutated']}`",
        f"- small_molecule_ligand_claim_allowed: `{summary['small_molecule_ligand_claim_allowed']}`",
        "",
        "## Blockers",
        "",
    ]
    blockers = summary.get("blockers") or []
    lines.extend(f"- `{blocker}`" for blocker in blockers) if blockers else lines.append("- none")
    lines.extend(["", "## Checks", "", "| check | status | observed | required |", "| --- | --- | --- | --- |"])
    for row in payload["rows"]:
        lines.append(f"| `{row['check']}` | `{row['status']}` | `{row['observed']}` | `{row['required']}` |")
    lines.extend(["", "## Claim Boundary", "", summary["claim_boundary"], "", "## Next Step", "", f"- {summary['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a BM5/CAPRI complex source-manifest gate without raw data downloads.")
    parser.add_argument("--bm5-dataset-dir", default=DEFAULT_BM5_DATASET_DIR)
    parser.add_argument("--bm5-materialization-manifest", default=DEFAULT_BM5_MATERIALIZATION_MANIFEST)
    parser.add_argument("--bm5-result-provenance-json", default=DEFAULT_BM5_RESULT_PROVENANCE_JSON)
    parser.add_argument("--bm5-scorecard-json", default=DEFAULT_BM5_SCORECARD_JSON)
    parser.add_argument("--capri-score-set-source-manifest", default=DEFAULT_CAPRI_SCORE_SET_SOURCE_MANIFEST)
    parser.add_argument("--capri-score-set-checksum-manifest", default=DEFAULT_CAPRI_SCORE_SET_CHECKSUM_MANIFEST)
    parser.add_argument("--capri-score-set-materialization-manifest", default=DEFAULT_CAPRI_SCORE_SET_MATERIALIZATION_MANIFEST)
    parser.add_argument("--capri-score-set-scorecard-json", default=DEFAULT_CAPRI_SCORE_SET_SCORECARD_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_bm5_capri_complex_source_manifest(
        bm5_dataset_dir=_resolve(args.bm5_dataset_dir),
        bm5_materialization_manifest=_resolve(args.bm5_materialization_manifest),
        bm5_result_provenance_json=_resolve(args.bm5_result_provenance_json),
        bm5_scorecard_json=_resolve(args.bm5_scorecard_json),
        capri_score_set_source_manifest=_resolve(args.capri_score_set_source_manifest),
        capri_score_set_checksum_manifest=_resolve(args.capri_score_set_checksum_manifest),
        capri_score_set_materialization_manifest=_resolve(args.capri_score_set_materialization_manifest),
        capri_score_set_scorecard_json=_resolve(args.capri_score_set_scorecard_json),
    )
    _write_json(args.out_json, payload)
    write_csv_rows(_resolve(args.out_csv), payload["rows"])
    _write_markdown(args.out_md, payload)


if __name__ == "__main__":
    main()

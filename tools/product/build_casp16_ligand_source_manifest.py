#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from betelgeuze_product.casp16_ligand_source_manifest import (
    CHECKSUM_MANIFEST_FORMAT,
    DEFAULT_OPERATOR_CHECKSUM_MANIFEST_TEMPLATE,
    DEFAULT_OPERATOR_RECEIPT_FILL_IN_MD,
    DEFAULT_OPERATOR_SCORECARD_ROWS_TEMPLATE,
    DEFAULT_OPERATOR_SOURCE_MANIFEST_TEMPLATE,
    SCORECARD_ALLOWED_METRICS,
    SCORECARD_ALLOWED_TASK_TYPES,
    SCORECARD_REQUIRED_COLUMNS,
    SOURCE_MANIFEST_REQUIRED_COLUMNS,
    build_casp16_ligand_source_manifest,
)
from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_LOCAL_SOURCE_MANIFEST_CSV = "data/competition_benchmarks/casp16_ligand/source_manifest.csv"
DEFAULT_LOCAL_CHECKSUM_MANIFEST = "data/competition_benchmarks/casp16_ligand/checksums.sha256"
DEFAULT_LOCAL_MATERIALIZATION_MANIFEST = "runs/casp16_ligand_materialization_manifest_current.json"
DEFAULT_SCORECARD_JSON = "runs/casp16_ligand_scorecard_current.json"
DEFAULT_OUT_JSON = "runs/casp16_ligand_source_manifest_current.json"
DEFAULT_OUT_CSV = "runs/casp16_ligand_source_manifest_current.csv"
DEFAULT_OUT_MD = "runs/casp16_ligand_source_manifest_current.md"


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_header_csv(path_like: str | Path, columns: tuple[str, ...]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(",".join(columns) + "\n", encoding="utf-8")


def _write_checksum_template(path_like: str | Path) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(
            [
                "# CASP16 ligand checksum manifest template.",
                f"# Format: {CHECKSUM_MANIFEST_FORMAT}",
                "# Keep raw CASP16 ligand data outside git-tracked repository files.",
                "# Add one reviewed checksum row per operator-retained source/result artifact.",
                "",
            ]
        ),
        encoding="utf-8",
    )


def _write_fill_in_markdown(
    path_like: str | Path,
    *,
    source_template: str,
    checksum_template: str,
    scorecard_template: str,
    materialization_command: str,
    scorecard_command: str,
) -> None:
    path = _resolve(path_like)
    lines = [
        "# CASP16 Ligand Operator Receipt Fill-In",
        "",
        "Fill the template artifacts with operator-reviewed CASP16 ligand source and metric metadata.",
        "Do not copy raw CASP16 ligand structures, model archives, or prediction payloads into git-tracked files.",
        "",
        "## Templates",
        "",
        f"- source manifest CSV: `{source_template}`",
        f"- checksum manifest: `{checksum_template}`",
        f"- scorecard rows CSV: `{scorecard_template}`",
        "",
        "## Required Columns",
        "",
        f"- source manifest: `{';'.join(SOURCE_MANIFEST_REQUIRED_COLUMNS)}`",
        f"- scorecard rows: `{';'.join(SCORECARD_REQUIRED_COLUMNS)}`",
        f"- scorecard task_type values: `{';'.join(SCORECARD_ALLOWED_TASK_TYPES)}`",
        f"- scorecard metric_name values: `{';'.join(SCORECARD_ALLOWED_METRICS)}`",
        f"- checksum format: `{CHECKSUM_MANIFEST_FORMAT}`",
        "",
        "## Rebuild Commands",
        "",
        f"- materialization: `{materialization_command}`",
        f"- scorecard: `{scorecard_command}`",
        "- source manifest: `python3 tools/build_casp16_ligand_source_manifest.py`",
        "",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def _write_operator_templates(
    *,
    source_template: str,
    checksum_template: str,
    scorecard_template: str,
    fill_in_md: str,
    payload: dict[str, Any],
) -> list[str]:
    summary = payload["summary"]
    _write_header_csv(source_template, SOURCE_MANIFEST_REQUIRED_COLUMNS)
    _write_checksum_template(checksum_template)
    _write_header_csv(scorecard_template, SCORECARD_REQUIRED_COLUMNS)
    _write_fill_in_markdown(
        fill_in_md,
        source_template=source_template,
        checksum_template=checksum_template,
        scorecard_template=scorecard_template,
        materialization_command=summary["materialization_command_template"],
        scorecard_command=summary["scorecard_run_command_template"],
    )
    return [source_template, checksum_template, scorecard_template, fill_in_md]


def _write_markdown(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    summary = payload["summary"]
    lines = [
        "# CASP16 Ligand Source Manifest",
        "",
        f"- status: `{summary['status']}`",
        f"- suite_id: `{summary['suite_id']}`",
        f"- competition_credibility_ready: `{summary['competition_credibility_ready']}`",
        f"- source_manifest_ready: `{summary['source_manifest_ready']}`",
        f"- materialization_ready: `{summary['materialization_ready']}`",
        f"- scorecard_ready: `{summary['scorecard_ready']}`",
        f"- blocker_count: `{summary['blocker_count']}`",
        f"- official_format_url: `{summary['official_format_url']}`",
        f"- official_numbers_url: `{summary['official_numbers_url']}`",
        f"- pharma_pose_ligand_target_count: `{summary['pharma_pose_ligand_target_count']}`",
        f"- pharma_affinity_ligand_target_count: `{summary['pharma_affinity_ligand_target_count']}`",
        f"- pharma_affinity_stage2_ligand_target_count: `{summary['pharma_affinity_stage2_ligand_target_count']}`",
        f"- incidental_ligand_target_count: `{summary['incidental_ligand_target_count']}`",
        f"- local_source_manifest_csv: `{summary['local_source_manifest_csv']}`",
        f"- local_checksum_manifest: `{summary['local_checksum_manifest']}`",
        f"- local_materialization_manifest: `{summary['local_materialization_manifest']}`",
        f"- scorecard_json: `{summary['scorecard_json']}`",
        f"- operator_input_schema_ready: `{summary['operator_input_schema_ready']}`",
        f"- source_manifest_required_columns: `{';'.join(summary['source_manifest_required_columns'])}`",
        f"- scorecard_required_columns: `{';'.join(summary['scorecard_required_columns'])}`",
        f"- operator_templates_written: `{summary['operator_templates_written']}`",
        f"- operator_template_artifacts: `{summary['operator_template_artifacts']}`",
        f"- raw_data_git_tracked_file_count: `{summary['raw_data_git_tracked_file_count']}`",
        f"- operator_input_artifacts: `{summary['operator_input_artifacts']}`",
        f"- missing_input_artifacts: `{summary['missing_input_artifacts']}`",
        f"- run_command: `{summary['run_command']}`",
        f"- materialization_command_template: `{summary['materialization_command_template']}`",
        f"- scorecard_run_command_template: `{summary['scorecard_run_command_template']}`",
        f"- raw_data_committed: `{summary['raw_data_committed']}`",
        f"- download_executed: `{summary['download_executed']}`",
        f"- external_state_mutated: `{summary['external_state_mutated']}`",
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
    parser = argparse.ArgumentParser(description="Build a CASP16 ligand source-manifest gate without raw data downloads.")
    parser.add_argument("--local-source-manifest-csv", default=DEFAULT_LOCAL_SOURCE_MANIFEST_CSV)
    parser.add_argument("--local-checksum-manifest", default=DEFAULT_LOCAL_CHECKSUM_MANIFEST)
    parser.add_argument("--local-materialization-manifest", default=DEFAULT_LOCAL_MATERIALIZATION_MANIFEST)
    parser.add_argument("--scorecard-json", default=DEFAULT_SCORECARD_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    parser.add_argument(
        "--operator-source-manifest-template-csv",
        default=DEFAULT_OPERATOR_SOURCE_MANIFEST_TEMPLATE,
    )
    parser.add_argument(
        "--operator-checksum-manifest-template",
        default=DEFAULT_OPERATOR_CHECKSUM_MANIFEST_TEMPLATE,
    )
    parser.add_argument(
        "--operator-scorecard-rows-template-csv",
        default=DEFAULT_OPERATOR_SCORECARD_ROWS_TEMPLATE,
    )
    parser.add_argument(
        "--operator-fill-in-md",
        default=DEFAULT_OPERATOR_RECEIPT_FILL_IN_MD,
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_casp16_ligand_source_manifest(
        local_source_manifest_csv=_resolve(args.local_source_manifest_csv),
        local_checksum_manifest=_resolve(args.local_checksum_manifest),
        local_materialization_manifest=_resolve(args.local_materialization_manifest),
        scorecard_json=_resolve(args.scorecard_json),
    )
    template_artifacts = _write_operator_templates(
        source_template=args.operator_source_manifest_template_csv,
        checksum_template=args.operator_checksum_manifest_template,
        scorecard_template=args.operator_scorecard_rows_template_csv,
        fill_in_md=args.operator_fill_in_md,
        payload=payload,
    )
    payload["summary"].update(
        {
            "operator_source_manifest_template_csv": args.operator_source_manifest_template_csv,
            "operator_checksum_manifest_template": args.operator_checksum_manifest_template,
            "operator_scorecard_rows_template_csv": args.operator_scorecard_rows_template_csv,
            "operator_receipt_fill_in_md": args.operator_fill_in_md,
            "operator_template_artifacts": ";".join(template_artifacts),
            "operator_templates_written": True,
        }
    )
    _write_json(args.out_json, payload)
    write_csv_rows(_resolve(args.out_csv), payload["rows"])
    _write_markdown(args.out_md, payload)


if __name__ == "__main__":
    main()

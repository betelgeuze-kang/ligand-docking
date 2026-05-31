#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]

DEFAULT_SOURCE_CANDIDATES_JSON = (
    "casp17/casp17_historical_seed_strict_blind_replacement_first_slot_official_archive_source_candidates_current.json"
)
DEFAULT_BASELINE_DIR = "casp17/historical_seed_official_archive_baseline_lane"
DEFAULT_OUT_JSON = "casp17/casp17_historical_seed_official_archive_baseline_lane_current.json"
DEFAULT_OUT_CSV = "casp17/casp17_historical_seed_official_archive_baseline_lane_current.csv"
DEFAULT_OUT_MD = "casp17/CASP17_HISTORICAL_SEED_OFFICIAL_ARCHIVE_BASELINE_LANE.md"

LANE_TYPE = "official_archive_baseline_replay"
OFFICIAL_MODEL_LANE = "external_official_casp_archive_model_pool"
COMPETITIVE_PROOF_ELIGIBLE = "False"
STRICT_BLIND_INTAKE_POLICY = "do_not_import_as_internal_prediction"
OTHER_TEAM_MODEL_POLICY = "official_archive_models_are_baseline_only"
MODEL1_SELECTION_POLICY = "model1_and_best_of_5_may_be_scored_only_as_external_baseline"
DOWNLOAD_POLICY = "operator_explicit_download_required_no_automatic_tarball_fetch"

ROW_COLUMNS = [
    "baseline_candidate_id",
    "source_candidate_id",
    "lane_type",
    "competition",
    "target_id",
    "target_description",
    "source_category",
    "prediction_tarball_url",
    "prediction_archive_modified_at",
    "prediction_archive_size",
    "native_pdb_code",
    "native_structure_file_url",
    "native_structure_file_format",
    "native_public_anchor_date",
    "targetlist_url",
    "targetlist_target_url",
    "official_model_lane",
    "competitive_proof_eligible",
    "strict_blind_intake_policy",
    "other_team_model_policy",
    "model1_selection_policy",
    "download_policy",
    "baseline_folder",
    "acquisition_manifest",
    "baseline_candidate_status",
    "next_action",
]

CLAIM_BOUNDARY = (
    "Local CASP17 official-archive baseline replay lane only. It separates official CASP15/16 archive "
    "submissions from strict-blind internal prediction evidence. Rows here may be useful for historical "
    "leaderboard-style baseline replay, model-ranking calibration, and metric-surface smoke tests, but they "
    "are not competitive-proof evidence and must not be imported as internal CASP17 predictions."
)


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _artifact(path_like: str | Path) -> str:
    path = _resolve(path_like).resolve()
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _read_json(path_like: str | Path) -> dict[str, Any]:
    path = _resolve(path_like)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _summary(payload: dict[str, Any]) -> dict[str, Any]:
    summary = payload.get("summary")
    return summary if isinstance(summary, dict) else {}


def _rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = payload.get("rows")
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_csv(path_like: str | Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _safe_slug(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9]+", "_", value.strip()).strip("_").lower()
    return slug[:80] or "target"


def _baseline_folder(base_dir: str | Path, row_rank: int, source: dict[str, Any]) -> Path:
    competition = _safe_slug(_text(source.get("competition")) or "competition")
    target_id = _safe_slug(_text(source.get("target_id")) or "target")
    description = _safe_slug(_text(source.get("target_description")) or target_id)
    return _resolve(base_dir) / f"{row_rank:03d}_{competition}_{target_id}_{description}"


def _ready_source(row: dict[str, Any]) -> bool:
    if _text(row.get("candidate_status")) != "pre_native_archive_candidate_native_authority_ready_for_download":
        return False
    if _text(row.get("pre_native_by_archive_timing")) != "True":
        return False
    return bool(_text(row.get("prediction_tarball_url")) and _text(row.get("native_structure_file_url")))


def _build_baseline_row(row_rank: int, source: dict[str, Any], base_dir: str | Path) -> dict[str, Any]:
    folder = _baseline_folder(base_dir, row_rank, source)
    manifest = folder / "ACQUISITION_MANIFEST.md"
    source_candidate_id = _text(source.get("candidate_id"))
    return {
        "baseline_candidate_id": f"official_archive_baseline_{row_rank:03d}",
        "source_candidate_id": source_candidate_id,
        "lane_type": LANE_TYPE,
        "competition": _text(source.get("competition")),
        "target_id": _text(source.get("target_id")),
        "target_description": _text(source.get("target_description")),
        "source_category": _text(source.get("source_category")),
        "prediction_tarball_url": _text(source.get("prediction_tarball_url")),
        "prediction_archive_modified_at": _text(source.get("prediction_archive_modified_at")),
        "prediction_archive_size": _text(source.get("prediction_archive_size")),
        "native_pdb_code": _text(source.get("native_pdb_code")),
        "native_structure_file_url": _text(source.get("native_structure_file_url")),
        "native_structure_file_format": _text(source.get("native_structure_file_format")),
        "native_public_anchor_date": _text(source.get("native_public_anchor_date")),
        "targetlist_url": _text(source.get("targetlist_url")),
        "targetlist_target_url": _text(source.get("targetlist_target_url")),
        "official_model_lane": OFFICIAL_MODEL_LANE,
        "competitive_proof_eligible": COMPETITIVE_PROOF_ELIGIBLE,
        "strict_blind_intake_policy": STRICT_BLIND_INTAKE_POLICY,
        "other_team_model_policy": OTHER_TEAM_MODEL_POLICY,
        "model1_selection_policy": MODEL1_SELECTION_POLICY,
        "download_policy": DOWNLOAD_POLICY,
        "baseline_folder": _artifact(folder),
        "acquisition_manifest": _artifact(manifest),
        "baseline_candidate_status": "baseline_replay_ready_for_operator_acquisition",
        "next_action": (
            "download/extract official archive models only inside this baseline lane, score model1 and best-of-5 "
            "as external baseline replay, and source internal pre-native predictions separately for competitive proof"
        ),
    }


def _build_rows(source_rows: list[dict[str, Any]], base_dir: str | Path, max_candidates: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for source in source_rows:
        if not _ready_source(source):
            continue
        rows.append(_build_baseline_row(len(rows) + 1, source, base_dir))
        if max_candidates > 0 and len(rows) >= max_candidates:
            break
    return rows


def _status(input_exists: bool, source_count: int, rows: list[dict[str, Any]]) -> str:
    if not input_exists:
        return "blocked_official_archive_source_candidates_missing"
    if source_count and not rows:
        return "blocked_no_official_archive_baseline_candidate_ready"
    if rows:
        return "official_archive_baseline_lane_ready"
    return "blocked_official_archive_source_candidates_empty"


def _build_summary(args: argparse.Namespace, source_payload: dict[str, Any], rows: list[dict[str, Any]], input_exists: bool) -> dict[str, Any]:
    source_rows = _rows(source_payload)
    first = rows[0] if rows else {}
    source_summary = _summary(source_payload)
    return {
        "packet_type": "casp17_historical_seed_official_archive_baseline_lane",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "official_archive_baseline_lane_status": _status(input_exists, len(source_rows), rows),
        "source_candidates_json": _artifact(args.source_candidates_json),
        "source_candidate_board_status": _text(
            source_summary.get("strict_blind_replacement_first_slot_official_archive_source_candidates_status")
        ),
        "source_candidate_count": len(source_rows),
        "source_ready_candidate_count": sum(1 for row in source_rows if _ready_source(row)),
        "baseline_candidate_count": len(rows),
        "ready_count": len(rows),
        "blocked_count": 0 if rows else max(1, len(source_rows)),
        "competitive_proof_eligible_count": sum(1 for row in rows if row["competitive_proof_eligible"] == "True"),
        "strict_blind_import_blocked_count": sum(
            1 for row in rows if row["strict_blind_intake_policy"] == STRICT_BLIND_INTAKE_POLICY
        ),
        "other_team_model_baseline_only_count": sum(
            1 for row in rows if row["other_team_model_policy"] == OTHER_TEAM_MODEL_POLICY
        ),
        "lane_type": LANE_TYPE,
        "official_model_lane": OFFICIAL_MODEL_LANE,
        "strict_blind_intake_policy": STRICT_BLIND_INTAKE_POLICY,
        "download_policy": DOWNLOAD_POLICY,
        "baseline_dir": _artifact(args.baseline_dir),
        "first_baseline_candidate_id": _text(first.get("baseline_candidate_id")),
        "first_source_candidate_id": _text(first.get("source_candidate_id")),
        "first_competition": _text(first.get("competition")),
        "first_target_id": _text(first.get("target_id")),
        "first_native_pdb_code": _text(first.get("native_pdb_code")),
        "first_prediction_tarball_url": _text(first.get("prediction_tarball_url")),
        "first_native_structure_file_url": _text(first.get("native_structure_file_url")),
        "first_acquisition_manifest": _text(first.get("acquisition_manifest")),
        "next_action": (
            "keep official CASP archive submissions in the baseline replay lane; do not feed them into "
            "strict-blind competitive proof or internal prediction dropzones"
        ),
        "claim_boundary": CLAIM_BOUNDARY,
    }


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    input_path = _resolve(args.source_candidates_json)
    source_payload = _read_json(input_path)
    rows = _build_rows(_rows(source_payload), args.baseline_dir, args.max_candidates)
    summary = _build_summary(args, source_payload, rows, input_path.exists())
    return {"summary": summary, "rows": rows}


def _write_acquisition_manifest(row: dict[str, Any]) -> None:
    lines = [
        f"# {row['competition']} {row['target_id']} Official Archive Baseline",
        "",
        f"- baseline_candidate_id: `{row['baseline_candidate_id']}`",
        f"- source_candidate_id: `{row['source_candidate_id']}`",
        f"- lane_type: `{row['lane_type']}`",
        f"- competitive_proof_eligible: `{row['competitive_proof_eligible']}`",
        f"- strict_blind_intake_policy: `{row['strict_blind_intake_policy']}`",
        f"- other_team_model_policy: `{row['other_team_model_policy']}`",
        f"- model1_selection_policy: `{row['model1_selection_policy']}`",
        f"- download_policy: `{row['download_policy']}`",
        f"- prediction_tarball_url: `{row['prediction_tarball_url']}`",
        f"- native_structure_file_url: `{row['native_structure_file_url']}`",
        f"- prediction/native dates: `{row['prediction_archive_modified_at']}` `{row['native_public_anchor_date']}`",
        "",
        "## Operator Acquisition Commands",
        "",
        "Run these only when you intentionally want an external official-archive baseline replay copy.",
        "",
        "```bash",
        f"mkdir -p {row['baseline_folder']}/downloads {row['baseline_folder']}/models {row['baseline_folder']}/native",
        f"curl -L -o {row['baseline_folder']}/downloads/{row['target_id']}.tar.gz '{row['prediction_tarball_url']}'",
        f"curl -L -o {row['baseline_folder']}/native/{row['native_pdb_code'].split(',')[0].upper()}.{row['native_structure_file_format'] or 'pdb'} '{row['native_structure_file_url']}'",
        "```",
        "",
        "## Claim Boundary",
        "",
        CLAIM_BOUNDARY,
        "",
    ]
    folder = _resolve(row["baseline_folder"])
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "ACQUISITION_MANIFEST.md").write_text("\n".join(lines), encoding="utf-8")
    _write_csv(folder / "baseline_candidate.csv", [row], ROW_COLUMNS)


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Historical Seed Official Archive Baseline Lane",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- status: `{summary['official_archive_baseline_lane_status']}`",
        f"- source candidates ready/total: `{summary['source_ready_candidate_count']}/{summary['source_candidate_count']}`",
        f"- baseline candidates: `{summary['baseline_candidate_count']}`",
        f"- competitive proof eligible: `{summary['competitive_proof_eligible_count']}`",
        f"- strict-blind import blocked: `{summary['strict_blind_import_blocked_count']}`",
        f"- other-team baseline-only: `{summary['other_team_model_baseline_only_count']}`",
        f"- lane_type: `{summary['lane_type']}`",
        f"- strict_blind_intake_policy: `{summary['strict_blind_intake_policy']}`",
        f"- download_policy: `{summary['download_policy']}`",
        f"- first baseline: `{summary['first_baseline_candidate_id'] or '-'}` `{summary['first_competition'] or '-'}` `{summary['first_target_id'] or '-'}` `{summary['first_native_pdb_code'] or '-'}`",
        f"- next action: {summary['next_action']}",
        "",
        "## Baseline Candidates",
        "",
        "| baseline | source | target | native | proof | policy | manifest |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['baseline_candidate_id']}` | `{row['source_candidate_id']}` | "
            f"`{row['competition']}/{row['target_id']}` | `{row['native_pdb_code'] or '-'}` | "
            f"`{row['competitive_proof_eligible']}` | `{row['strict_blind_intake_policy']}` | "
            f"`{row['acquisition_manifest']}` |"
        )
    if not payload["rows"]:
        lines.append("| - | - | - | - | `False` | `blocked` | - |")
    lines.extend(["", "## Claim Boundary", "", str(summary["claim_boundary"]), ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def write_outputs(args: argparse.Namespace, payload: dict[str, Any]) -> None:
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"], ROW_COLUMNS)
    _write_md(args.out_md, payload)
    for row in payload["rows"]:
        _write_acquisition_manifest(row)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build an external official CASP archive baseline replay lane.")
    parser.add_argument("--source-candidates-json", default=DEFAULT_SOURCE_CANDIDATES_JSON)
    parser.add_argument("--baseline-dir", default=DEFAULT_BASELINE_DIR)
    parser.add_argument("--max-candidates", type=int, default=24)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_payload(args)
    write_outputs(args, payload)


if __name__ == "__main__":
    main()

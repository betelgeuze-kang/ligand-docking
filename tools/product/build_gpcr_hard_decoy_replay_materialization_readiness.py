#!/usr/bin/env python3
"""Build read-only readiness for the next GPCR hard-decoy closure replay.

This narrows the gap between "candidate almost closes" and "actual replay can
be run" by checking the exact blocker ligands for:

* retained ranking evidence;
* full ranking materialization artifacts;
* ranking input artifacts; and
* label-free feature-cache coverage needed by the DRD2 closure replay.

It does not run scoring, regenerate rows, relax thresholds, edit suite inputs,
or promote a GPCR claim.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
from typing import Any, Iterable, Sequence

ROOT = Path(__file__).resolve().parents[2]

DEFAULT_CLOSURE_SPEC_JSON = "runs/gpcr_hard_decoy_closure_replay_spec_current.json"
DEFAULT_CANDIDATE_SWEEP_JSON = "runs/gpcr_hard_decoy_candidate_sweep_current.json"
DEFAULT_FEATURE_CACHE_GLOBS = (
    "runs/gpcr_cationic_pose_distortion_frozen_feature_cache*current.csv",
    "runs/gpcr_drd2_hard_decoy_slice_packet*_rows_current.csv",
    "runs/gpcr_atom_window_anchor_feature_cache_drd2*current.csv",
    "runs/gpcr_drd2_cationic_center_geometry_cache*current.csv",
    "runs/gpcr_drd2_local_minimization_survival*current.csv",
)
DEFAULT_OUT_JSON = "runs/gpcr_hard_decoy_replay_materialization_readiness_current.json"
DEFAULT_OUT_MD = "runs/gpcr_hard_decoy_replay_materialization_readiness_current.md"
DEFAULT_OUT_CSV = "runs/gpcr_hard_decoy_replay_materialization_readiness_current.csv"

PACKET_TYPE = "gpcr_hard_decoy_replay_materialization_readiness"
SCHEMA_VERSION = "gpcr_hard_decoy_replay_materialization_readiness_v1"

REQUIRED_TARGETS = {
    "CHEMBL217_DRD2_HUMAN": "DRD2",
    "CHEMBL224_HTR2A_HUMAN": "HTR2A",
    "CHEMBL233_OPRM1_HUMAN": "OPRM1",
}

SCORE_COLUMN_PRIORITY = (
    "score_value",
    "binding_score_composite_v7_coverage_v2_crossfit_rank_rescue_shadow",
    "binding_score_composite_v7_coverage_v2_adaptive_rank_rescue_shadow",
    "binding_score_composite_v7_residual_shadow",
    "binding_score_composite_v7_residual_active",
    "binding_score_composite_v7",
    "score",
)

SCORING_FEATURE_COLUMNS = (
    "label_free_penalty_pressure",
    "label_free_support_pressure",
    "valid_anchor_support",
    "pose_distortion_pressure",
)

CLAIM_BOUNDARY = (
    "GPCR hard-decoy replay materialization readiness only; it records exact local input and feature-cache "
    "coverage for the next closure replay. It does not run scoring, regenerate rows, edit suite inputs, "
    "relax thresholds, promote a broad-GPCR claim, fetch external data, or mutate external state."
)

_READ_ONLY_FLAGS = {
    "execution_enabled": False,
    "external_state_mutated": False,
    "scoring_execution_enabled": False,
    "threshold_relaxation_enabled": False,
    "suite_input_write_allowed": False,
    "claim_promotion_allowed": False,
}

_CSV_COLUMNS = [
    "target_id",
    "target_source_id",
    "materialization_role",
    "ligand_id",
    "is_binder",
    "retained_rank",
    "retained_score",
    "positive_score",
    "score_delta_to_positive",
    "anchor_distance_a",
    "positive_anchor_distance_a",
    "anchor_margin_to_positive_a",
    "scoring_feature_cache_ready",
    "scoring_feature_cache_path",
    "scoring_feature_cache_status",
    "label_free_penalty_pressure",
    "label_free_support_pressure",
    "valid_anchor_support",
    "pose_distortion_pressure",
    "atom_anchor_feature_ready",
    "cationic_center_feature_ready",
    "local_min_survival_ready",
    "blockers",
    "execution_enabled",
    "external_state_mutated",
    "scoring_execution_enabled",
    "threshold_relaxation_enabled",
    "suite_input_write_allowed",
    "claim_promotion_allowed",
]


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _display(path_like: str | Path | None) -> str:
    if path_like is None:
        return ""
    path = Path(path_like)
    if path.is_absolute():
        try:
            return str(path.relative_to(ROOT))
        except ValueError:
            return str(path)
    return str(path)


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _float(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _bool(value: Any) -> bool:
    return _text(value).lower() in {"1", "true", "yes", "y"}


def _read_json(path_like: str | Path) -> dict[str, Any]:
    path = _resolve(path_like)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _read_csv(path_like: str | Path) -> list[dict[str, str]]:
    path = _resolve(path_like)
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _glob_paths(patterns: Sequence[str]) -> list[Path]:
    out: list[Path] = []
    seen: set[Path] = set()
    for pattern in patterns:
        pattern_path = Path(pattern)
        matches: Iterable[Path]
        if pattern_path.is_absolute():
            matches = Path("/").glob(str(pattern_path).lstrip("/"))
        else:
            matches = ROOT.glob(pattern)
        for path in sorted(matches):
            resolved = path.resolve()
            if resolved in seen or not path.is_file():
                continue
            seen.add(resolved)
            out.append(path)
    return out


def _summary_path_candidates(candidate_path: Path) -> list[Path]:
    name = candidate_path.name
    replacements = (
        ("_ranking_unique_top_rank_retained_top50_current.csv", "_ranking_summary_current.json"),
        ("_ranking_rows_top_rank_retained_top50_current.csv", "_ranking_summary_current.json"),
        ("_stage5_ranking_unique_top_rank_retained_top50_current.csv", "_stage5_ranking_summary.json"),
        ("_stage5_ranking_rows_top_rank_retained_top50_current.csv", "_stage5_ranking_summary.json"),
        ("_ranking_eval_unique_top_rank_retained_top50_current.csv", "_ranking_eval_current.json"),
        ("_ranking_eval_rows_top_rank_retained_top50_current.csv", "_ranking_eval_current.json"),
        ("_scores_top_rank_retained_top50_current.csv", "_summary_current.json"),
    )
    candidates: list[Path] = []
    for old, new in replacements:
        if name.endswith(old):
            candidates.append(candidate_path.with_name(name[: -len(old)] + new))
    stem = candidate_path.stem.replace("_top_rank_retained_top50_current", "")
    candidates.extend(
        [
            candidate_path.with_name(stem + "_summary_current.json"),
            candidate_path.with_name(stem + "_ranking_summary_current.json"),
            candidate_path.with_name(stem + "_ranking_eval_current.json"),
        ]
    )
    deduped: list[Path] = []
    for candidate in candidates:
        if candidate not in deduped:
            deduped.append(candidate)
    return deduped


def _find_summary(candidate_path: Path) -> tuple[Path | None, dict[str, Any]]:
    for path in _summary_path_candidates(candidate_path):
        if path.exists():
            return path, _read_json(path)
    return None, {}


def _score(row: dict[str, str], fieldnames: Sequence[str]) -> float | None:
    choices: list[str] = []
    score_col = _text(row.get("score_col"))
    if score_col:
        choices.append(score_col)
    choices.extend(SCORE_COLUMN_PRIORITY)
    for column in choices:
        if column in fieldnames:
            value = _float(row.get(column))
            if value is not None:
                return value
    return None


def _anchor(row: dict[str, str]) -> float | None:
    for column in ("mean_min_distance_A", "anchor_distance_a", "native_anchor_mean_distance_a"):
        value = _float(row.get(column))
        if value is not None:
            return value
    return None


def _candidate_target_rows(candidate_path: Path, target_source_id: str) -> list[dict[str, Any]]:
    path = _resolve(candidate_path)
    if not path.exists():
        return []
    out: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = list(reader.fieldnames or [])
        if "target" not in fieldnames or "ligand_id" not in fieldnames or "is_binder" not in fieldnames:
            return []
        for row in reader:
            if _text(row.get("target")) != target_source_id:
                continue
            score = _score(row, fieldnames)
            if score is None:
                continue
            copied: dict[str, Any] = dict(row)
            copied["_score"] = score
            copied["_is_binder"] = _bool(row.get("is_binder"))
            copied["_anchor"] = _anchor(row)
            out.append(copied)
    return out


def _target_source_id(target_id: str) -> str:
    for source_id, short_id in REQUIRED_TARGETS.items():
        if short_id == target_id:
            return source_id
    return target_id


def _blocked_target_ids(closure_spec: dict[str, Any]) -> list[str]:
    rows = closure_spec.get("rows") if isinstance(closure_spec.get("rows"), list) else []
    blocked = [_text(row.get("target_id")) for row in rows if isinstance(row, dict) and row.get("target_green") is False]
    return [target for target in blocked if target]


def _best_candidate_path(closure_spec: dict[str, Any], sweep: dict[str, Any]) -> str:
    summary = closure_spec.get("summary") if isinstance(closure_spec.get("summary"), dict) else {}
    path = _text(summary.get("best_candidate_path"))
    if path:
        return path
    sweep_summary = sweep.get("summary") if isinstance(sweep.get("summary"), dict) else {}
    return _text(sweep_summary.get("best_candidate_path"))


def _artifact_rows(ranking_summary: dict[str, Any]) -> list[dict[str, Any]]:
    artifacts = ranking_summary.get("artifacts") if isinstance(ranking_summary.get("artifacts"), dict) else {}
    rows: list[dict[str, Any]] = []
    for artifact_key in ("detail_csv", "unique_csv"):
        raw = _text(artifacts.get(artifact_key))
        path = _resolve(raw) if raw else Path("")
        rows.append(
            {
                "artifact_key": artifact_key,
                "path": "" if not raw else str(path),
                "exists": bool(raw and path.exists()),
                "required_for": "complete_replay_ranking_evidence",
            }
        )
    for artifact_key in ("expected_keys_csv", "split_csv"):
        raw = _text(ranking_summary.get(artifact_key))
        path = _resolve(raw) if raw else Path("")
        rows.append(
            {
                "artifact_key": artifact_key,
                "path": "" if not raw else str(path),
                "exists": bool(raw and path.exists()),
                "required_for": "ranking_regeneration_or_replay_evaluation",
            }
        )
    return rows


def _feature_lookup(feature_cache_globs: Sequence[str]) -> dict[tuple[str, str], list[dict[str, Any]]]:
    lookup: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for path in _glob_paths(feature_cache_globs):
        rows = _read_csv(path)
        for row in rows:
            target = _text(row.get("target"))
            ligand_id = _text(row.get("ligand_id"))
            if not target or not ligand_id:
                continue
            copied: dict[str, Any] = dict(row)
            copied["_feature_cache_path"] = str(path)
            lookup.setdefault((target, ligand_id), []).append(copied)
    return lookup


def _has_any_float(row: dict[str, Any], columns: Sequence[str]) -> bool:
    return any(_float(row.get(column)) is not None for column in columns)


def _select_scoring_feature(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    for row in rows:
        if not _has_any_float(row, SCORING_FEATURE_COLUMNS):
            continue
        status = _text(row.get("feature_cache_status"))
        if status and status != "ok":
            continue
        return row
    return None


def _feature_presence(rows: list[dict[str, Any]], *columns: str) -> bool:
    return any(_has_any_float(row, columns) for row in rows)


def _materialization_rows_for_target(
    *,
    target_id: str,
    target_source_id: str,
    candidate_rows: list[dict[str, Any]],
    feature_lookup: dict[tuple[str, str], list[dict[str, Any]]],
    lower_better: bool,
) -> list[dict[str, Any]]:
    ranked = sorted(candidate_rows, key=lambda row: row["_score"], reverse=not lower_better)
    positives = [row for row in ranked if bool(row["_is_binder"])]
    positive = positives[0] if positives else None
    if positive is None:
        return []
    positive_rank = ranked.index(positive) + 1
    blocker_rows = [row for row in ranked[: positive_rank - 1] if not bool(row["_is_binder"])]
    selected = [("positive", positive), *[("decoy_above_positive", row) for row in blocker_rows]]
    positive_score = float(positive["_score"])
    positive_anchor = positive.get("_anchor")
    out: list[dict[str, Any]] = []
    for role, row in selected:
        ligand_id = _text(row.get("ligand_id"))
        features = feature_lookup.get((target_source_id, ligand_id), [])
        scoring_feature = _select_scoring_feature(features)
        blockers: list[str] = []
        if scoring_feature is None:
            blockers.append("scoring_feature_cache_missing")
        if role == "decoy_above_positive":
            blockers.append("decoy_currently_above_positive")
        anchor_value = row.get("_anchor")
        if anchor_value is None:
            blockers.append("anchor_distance_missing")
        anchor_margin = None if anchor_value is None or positive_anchor is None else float(anchor_value) - float(positive_anchor)
        if role == "decoy_above_positive" and anchor_margin is not None and anchor_margin < 0.0:
            blockers.append("decoy_over_anchored_vs_positive")
        score_delta = None if role == "positive" else float(positive_score - float(row["_score"]))
        out.append(
            {
                "target_id": target_id,
                "target_source_id": target_source_id,
                "materialization_role": role,
                "ligand_id": ligand_id,
                "is_binder": bool(row["_is_binder"]),
                "retained_rank": row.get("rank"),
                "retained_score": float(row["_score"]),
                "positive_score": positive_score,
                "score_delta_to_positive": score_delta,
                "anchor_distance_a": anchor_value,
                "positive_anchor_distance_a": positive_anchor,
                "anchor_margin_to_positive_a": anchor_margin,
                "scoring_feature_cache_ready": scoring_feature is not None,
                "scoring_feature_cache_path": _display(scoring_feature.get("_feature_cache_path")) if scoring_feature else "",
                "scoring_feature_cache_status": _text(scoring_feature.get("feature_cache_status")) if scoring_feature else "",
                "label_free_penalty_pressure": None if scoring_feature is None else _float(scoring_feature.get("label_free_penalty_pressure")),
                "label_free_support_pressure": None if scoring_feature is None else _float(scoring_feature.get("label_free_support_pressure")),
                "valid_anchor_support": None if scoring_feature is None else _float(scoring_feature.get("valid_anchor_support")),
                "pose_distortion_pressure": None if scoring_feature is None else _float(scoring_feature.get("pose_distortion_pressure")),
                "atom_anchor_feature_ready": _feature_presence(
                    features,
                    "class_a_atom_anchor_mean_distance_A",
                    "atom_anchor_mean_distance_A",
                ),
                "cationic_center_feature_ready": _feature_presence(
                    features,
                    "class_a_cationic_center_mean_distance_A",
                    "cationic_center_mean_distance_A",
                ),
                "local_min_survival_ready": _feature_presence(
                    features,
                    "survival_fraction",
                    "local_min_survival",
                ),
                "blockers": blockers,
                **_READ_ONLY_FLAGS,
            }
        )
    return out


def build_gpcr_hard_decoy_replay_materialization_readiness(
    *,
    closure_spec_json: str | Path = DEFAULT_CLOSURE_SPEC_JSON,
    candidate_sweep_json: str | Path = DEFAULT_CANDIDATE_SWEEP_JSON,
    feature_cache_globs: Sequence[str] | None = None,
) -> dict[str, Any]:
    closure_spec_path = _resolve(closure_spec_json)
    sweep_path = _resolve(candidate_sweep_json)
    closure_spec = _read_json(closure_spec_path)
    sweep = _read_json(sweep_path)
    best_candidate = _best_candidate_path(closure_spec, sweep)
    candidate_path = _resolve(best_candidate) if best_candidate else Path("")
    ranking_summary_path, ranking_summary = _find_summary(candidate_path) if best_candidate else (None, {})
    lower_better = bool(ranking_summary.get("lower_better", True))
    artifact_rows = _artifact_rows(ranking_summary)
    missing_artifacts = [row for row in artifact_rows if not row["exists"]]
    blocked_targets = _blocked_target_ids(closure_spec)
    target_ids = blocked_targets or ["DRD2"]
    feature_lookup = _feature_lookup(tuple(feature_cache_globs or DEFAULT_FEATURE_CACHE_GLOBS))
    rows: list[dict[str, Any]] = []
    missing_target_rows: list[str] = []
    for target_id in target_ids:
        target_source_id = _target_source_id(target_id)
        candidate_target_rows = _candidate_target_rows(candidate_path, target_source_id) if best_candidate else []
        if not candidate_target_rows:
            missing_target_rows.append(target_id)
            continue
        rows.extend(
            _materialization_rows_for_target(
                target_id=target_id,
                target_source_id=target_source_id,
                candidate_rows=candidate_target_rows,
                feature_lookup=feature_lookup,
                lower_better=lower_better,
            )
        )
    missing_feature_rows = [row for row in rows if not row["scoring_feature_cache_ready"]]
    decoy_rows = [row for row in rows if row["materialization_role"] == "decoy_above_positive"]

    if not closure_spec_path.exists():
        status = "blocked_gpcr_hard_decoy_replay_materialization_missing_closure_spec"
    elif not best_candidate or not candidate_path.exists():
        status = "blocked_gpcr_hard_decoy_replay_materialization_missing_candidate"
    elif missing_target_rows:
        status = "blocked_gpcr_hard_decoy_replay_materialization_missing_target_rows"
    elif missing_artifacts:
        status = "blocked_gpcr_hard_decoy_replay_materialization_missing_full_rows"
    elif missing_feature_rows:
        status = "blocked_gpcr_hard_decoy_replay_materialization_missing_feature_rows"
    elif not decoy_rows:
        status = "gpcr_hard_decoy_replay_materialization_no_decoy_blockers"
    else:
        status = "gpcr_hard_decoy_replay_materialization_ready"

    summary = {
        "packet_type": PACKET_TYPE,
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "materialization_ready": status == "gpcr_hard_decoy_replay_materialization_ready",
        "closure_spec_json": str(closure_spec_path),
        "candidate_sweep_json": str(sweep_path),
        "best_candidate_path": _display(candidate_path) if best_candidate else "",
        "ranking_summary_json": _display(ranking_summary_path),
        "blocked_target_ids": target_ids,
        "materialization_row_count": len(rows),
        "decoy_above_positive_row_count": len(decoy_rows),
        "full_artifact_count": len(artifact_rows),
        "missing_full_artifact_count": len(missing_artifacts),
        "missing_full_artifact_keys": [row["artifact_key"] for row in missing_artifacts],
        "scoring_feature_ready_row_count": sum(1 for row in rows if row["scoring_feature_cache_ready"]),
        "missing_scoring_feature_row_count": len(missing_feature_rows),
        "missing_scoring_feature_ligand_ids": [row["ligand_id"] for row in missing_feature_rows],
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "Restore/regenerate the missing full ranking artifacts before running the closure replay."
            if missing_artifacts
            else (
                "Materialize label-free scoring feature-cache rows for every blocker ligand, then rerun this readiness check."
                if missing_feature_rows
                else (
                    "Run the closure replay on complete rows and regenerate the GPCR hard-decoy suite input/report."
                    if status == "gpcr_hard_decoy_replay_materialization_ready"
                    else "Regenerate candidate sweep/closure spec, then rebuild this readiness artifact."
                )
            )
        ),
        **_READ_ONLY_FLAGS,
    }
    return {
        "packet_type": PACKET_TYPE,
        "schema_version": SCHEMA_VERSION,
        "summary": summary,
        "artifact_rows": artifact_rows,
        "rows": rows,
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
        "# GPCR Hard-Decoy Replay Materialization Readiness",
        "",
        f"- status: `{summary['status']}`",
        f"- materialization_ready: `{str(summary['materialization_ready']).lower()}`",
        f"- best_candidate_path: `{summary['best_candidate_path'] or '(none)'}`",
        f"- blocked_target_ids: `{', '.join(summary['blocked_target_ids']) or '(none)'}`",
        f"- decoy_above_positive_row_count: `{summary['decoy_above_positive_row_count']}`",
        f"- missing_full_artifact_count: `{summary['missing_full_artifact_count']}`",
        f"- missing_scoring_feature_row_count: `{summary['missing_scoring_feature_row_count']}`",
        "",
        "## Full Artifacts",
        "",
        "| artifact | exists | path |",
        "| --- | --- | --- |",
    ]
    for row in payload["artifact_rows"]:
        lines.append(f"| `{row['artifact_key']}` | `{str(row['exists']).lower()}` | `{row['path']}` |")
    lines.extend(
        [
            "",
            "## Blocker Ligands",
            "",
            "| target | role | ligand | score delta | anchor margin | scoring feature | blockers |",
            "| --- | --- | --- | ---: | ---: | --- | --- |",
        ]
    )
    for row in payload["rows"]:
        lines.append(
            "| `{target}` | `{role}` | `{ligand}` | `{score_delta}` | `{anchor_margin}` | `{feature}` | {blockers} |".format(
                target=row["target_id"],
                role=row["materialization_role"],
                ligand=row["ligand_id"],
                score_delta=_fmt(row.get("score_delta_to_positive")),
                anchor_margin=_fmt(row.get("anchor_margin_to_positive_a")),
                feature=str(row["scoring_feature_cache_ready"]).lower(),
                blockers=", ".join(row["blockers"]) or "(none)",
            )
        )
    lines.extend(["", "## Claim Boundary", "", CLAIM_BOUNDARY, ""])
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build GPCR hard-decoy closure replay materialization readiness.")
    parser.add_argument("--closure-spec-json", default=DEFAULT_CLOSURE_SPEC_JSON)
    parser.add_argument("--candidate-sweep-json", default=DEFAULT_CANDIDATE_SWEEP_JSON)
    parser.add_argument(
        "--feature-cache-glob",
        action="append",
        dest="feature_cache_globs",
        help="Feature cache glob to inspect. Repeat to add more.",
    )
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    args = parser.parse_args(argv)

    payload = build_gpcr_hard_decoy_replay_materialization_readiness(
        closure_spec_json=args.closure_spec_json,
        candidate_sweep_json=args.candidate_sweep_json,
        feature_cache_globs=args.feature_cache_globs,
    )
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

#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
from pathlib import Path
from statistics import mean
from typing import Any


ROOT = Path(__file__).resolve().parents[2]

DEFAULT_COVERAGE_JSON = "casp17/casp17_protein_complex_massivefold_model_selection_coverage_current.json"
DEFAULT_OUT_DIR = "casp17/protein_complex_massivefold_self_assessment"
DEFAULT_OUT_JSON = "casp17/casp17_protein_complex_massivefold_self_assessment_packet_current.json"
DEFAULT_OUT_CSV = "casp17/casp17_protein_complex_massivefold_self_assessment_packet_current.csv"
DEFAULT_OUT_MD = "casp17/CASP17_PROTEIN_COMPLEX_MASSIVEFOLD_SELF_ASSESSMENT_PACKET.md"

EXTERNAL_ONLY_POLICY = "external_protein_complex_rerank_accuracy_estimation_self_assessment_only"
INTERNAL_PREDICTION_POLICY = "do_not_mark_as_internal_prediction"
SUBMISSION_POLICY = "do_not_submit_without_rule_check_and_operator_approval"
NATIVE_POLICY = "no_native_structure_or_post_release_accuracy_claim"
CLAIM_BOUNDARY = (
    "CASP17 protein/complex MassiveFold self-assessment packet only. It converts organizer-provided "
    "external protein, immune, and complex model1/top5 pointers into no-native confidence, diversity, "
    "and geometry review features for conformation triage and model-selection calibration. It does not "
    "copy coordinates, submit models, use native structures, or create internal competitive-proof evidence."
)

TARGET_COLUMNS = [
    "target_id",
    "target_family",
    "self_assessment_status",
    "model1_filename",
    "model1_protocol",
    "model1_confidence_score",
    "runner_up_confidence_score",
    "confidence_gap",
    "top5_confidence_min",
    "top5_confidence_max",
    "top5_confidence_mean",
    "top5_score_spread",
    "model1_input_count",
    "top5_input_count",
    "missing_artifact_count",
    "mean_diversity_to_model1_rmsd",
    "min_nearest_top5_rmsd",
    "max_geometry_outlier_score",
    "max_low_conf_atom_fraction",
    "min_high_conf_atom_fraction",
    "target_candidate_manifest_csv",
    "target_self_assessment_md",
    "external_only_policy",
    "internal_prediction_policy",
    "submission_policy",
    "native_policy",
    "recommended_next_action",
    "blockers",
    "claim_boundary",
]

CANDIDATE_COLUMNS = [
    "target_id",
    "target_family",
    "input_rank",
    "input_role",
    "filename",
    "rerank_bucket",
    "confidence_score",
    "diversity_to_model1_rmsd",
    "nearest_top5_rmsd",
    "geometry_outlier_score",
    "low_conf_atom_fraction",
    "high_conf_atom_fraction",
    "model_cif_path",
    "viewer_html_path",
    "projection_svg_path",
    "model_review_md_path",
    "source_top5_manifest_csv",
    "claim_boundary",
]


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


def _int(value: Any) -> int:
    try:
        return int(float(str(value).strip()))
    except (TypeError, ValueError):
        return 0


def _float(value: Any) -> float:
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return 0.0


def _float_out(value: float) -> str:
    return f"{value:.6f}".rstrip("0").rstrip(".")


def _read_json(path_like: str | Path) -> dict[str, Any]:
    path = _resolve(path_like)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _coverage_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = payload.get("rows")
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def _read_csv(path_like: str | Path) -> list[dict[str, str]]:
    path = _resolve(path_like)
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_csv(path_like: str | Path, rows: list[dict[str, Any]], columns: list[str]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _target_family(target_id: str) -> str:
    if target_id.startswith("H"):
        return "heteromer_or_immune_complex"
    if target_id.startswith("T"):
        return "protein_monomer_or_homomer_pool"
    return "protein_or_complex_pool"


def _path_present(path_text: str) -> bool:
    return bool(path_text) and _resolve(path_text).exists()


def _top5_rows(manifest_path: str) -> list[dict[str, str]]:
    rows = _read_csv(manifest_path)
    selected = [row for row in rows if _text(row.get("top5_candidate")).lower() == "true"]
    selected.sort(key=lambda row: _int(row.get("top5_selection_rank")) or _int(row.get("quality_rank")))
    return selected[:5]


def _candidate_row(target_id: str, source_manifest: str, row: dict[str, str]) -> dict[str, Any]:
    return {
        "target_id": target_id,
        "target_family": _target_family(target_id),
        "input_rank": _int(row.get("top5_selection_rank")) or _int(row.get("quality_rank")),
        "input_role": "model1" if _text(row.get("model1_candidate")).lower() == "true" else "top5_decoy",
        "filename": _text(row.get("filename")),
        "rerank_bucket": _text(row.get("rerank_bucket")),
        "confidence_score": _float_out(_float(row.get("confidence_score"))),
        "diversity_to_model1_rmsd": _float_out(_float(row.get("diversity_to_model1_rmsd"))),
        "nearest_top5_rmsd": _float_out(_float(row.get("nearest_top5_rmsd"))),
        "geometry_outlier_score": _float_out(_float(row.get("geometry_outlier_score"))),
        "low_conf_atom_fraction": _float_out(_float(row.get("low_conf_atom_fraction"))),
        "high_conf_atom_fraction": _float_out(_float(row.get("high_conf_atom_fraction"))),
        "model_cif_path": _text(row.get("model_cif_path")),
        "viewer_html_path": _text(row.get("viewer_html_path")),
        "projection_svg_path": _text(row.get("projection_svg_path")),
        "model_review_md_path": _text(row.get("model_review_md_path")),
        "source_top5_manifest_csv": _artifact(source_manifest),
        "claim_boundary": CLAIM_BOUNDARY,
    }


def _missing_artifact_count(rows: list[dict[str, Any]]) -> int:
    fields = ["model_cif_path", "viewer_html_path", "projection_svg_path", "model_review_md_path"]
    return sum(1 for row in rows for field in fields if not _path_present(_text(row.get(field))))


def _target_packet(row: dict[str, Any], out_dir: str | Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    target_id = _text(row.get("target_id")).upper()
    manifest_path = _text(row.get("top5_manifest_csv"))
    blockers: list[str] = []
    if row.get("coverage_status") != "ready_review_only":
        blockers.append("coverage_not_ready_review_only")
    if not manifest_path or not _resolve(manifest_path).exists():
        blockers.append("top5_manifest_missing")
    candidates = [_candidate_row(target_id, manifest_path, top5_row) for top5_row in _top5_rows(manifest_path)]
    model1_rows = [candidate for candidate in candidates if candidate["input_role"] == "model1"]
    missing_artifacts = _missing_artifact_count(candidates)
    if len(candidates) != 5:
        blockers.append("top5_input_count_not_5")
    if len(model1_rows) != 1:
        blockers.append("model1_input_count_not_1")
    if missing_artifacts:
        blockers.append("input_artifact_missing")
    scores = [_float(candidate.get("confidence_score")) for candidate in candidates]
    model1 = model1_rows[0] if model1_rows else {}
    model1_score = _float(model1.get("confidence_score"))
    runner_up = max([score for candidate, score in zip(candidates, scores) if candidate["input_role"] != "model1"] or [0.0])
    diversity_values = [_float(candidate.get("diversity_to_model1_rmsd")) for candidate in candidates if _float(candidate.get("diversity_to_model1_rmsd")) > 0]
    nearest_values = [_float(candidate.get("nearest_top5_rmsd")) for candidate in candidates if _float(candidate.get("nearest_top5_rmsd")) > 0]
    geometry_values = [_float(candidate.get("geometry_outlier_score")) for candidate in candidates]
    low_conf_values = [_float(candidate.get("low_conf_atom_fraction")) for candidate in candidates]
    high_conf_values = [_float(candidate.get("high_conf_atom_fraction")) for candidate in candidates]
    target_dir = _resolve(out_dir) / target_id.lower()
    target_row = {
        "target_id": target_id,
        "target_family": _target_family(target_id),
        "self_assessment_status": "ready_external_complex_self_assessment_input" if not blockers else "blocked_or_partial",
        "model1_filename": _text(model1.get("filename")),
        "model1_protocol": _text(model1.get("rerank_bucket")),
        "model1_confidence_score": _float_out(model1_score),
        "runner_up_confidence_score": _float_out(runner_up),
        "confidence_gap": _float_out(model1_score - runner_up if model1 else 0.0),
        "top5_confidence_min": _float_out(min(scores) if scores else 0.0),
        "top5_confidence_max": _float_out(max(scores) if scores else 0.0),
        "top5_confidence_mean": _float_out(mean(scores) if scores else 0.0),
        "top5_score_spread": _float_out((max(scores) - min(scores)) if scores else 0.0),
        "model1_input_count": len(model1_rows),
        "top5_input_count": len(candidates),
        "missing_artifact_count": missing_artifacts,
        "mean_diversity_to_model1_rmsd": _float_out(mean(diversity_values) if diversity_values else 0.0),
        "min_nearest_top5_rmsd": _float_out(min(nearest_values) if nearest_values else 0.0),
        "max_geometry_outlier_score": _float_out(max(geometry_values) if geometry_values else 0.0),
        "max_low_conf_atom_fraction": _float_out(max(low_conf_values) if low_conf_values else 0.0),
        "min_high_conf_atom_fraction": _float_out(min(high_conf_values) if high_conf_values else 0.0),
        "target_candidate_manifest_csv": _artifact(target_dir / "self_assessment_candidates.csv"),
        "target_self_assessment_md": _artifact(target_dir / "SELF_ASSESSMENT.md"),
        "external_only_policy": EXTERNAL_ONLY_POLICY,
        "internal_prediction_policy": INTERNAL_PREDICTION_POLICY,
        "submission_policy": SUBMISSION_POLICY,
        "native_policy": NATIVE_POLICY,
        "recommended_next_action": (
            "triage model1 versus top5 by confidence gap, diversity, and geometry before any CASP rule-checked use"
        ),
        "blockers": ",".join(blockers),
        "claim_boundary": CLAIM_BOUNDARY,
    }
    return target_row, candidates


def _write_target_packet(out_dir: str | Path, target_row: dict[str, Any], candidates: list[dict[str, Any]]) -> None:
    target_dir = _resolve(out_dir) / target_row["target_id"].lower()
    target_dir.mkdir(parents=True, exist_ok=True)
    _write_csv(target_dir / "self_assessment_candidates.csv", candidates, CANDIDATE_COLUMNS)
    lines = [
        f"# {target_row['target_id']} Protein/Complex MassiveFold Self-Assessment",
        "",
        f"- family: `{target_row['target_family']}`",
        f"- status: `{target_row['self_assessment_status']}`",
        f"- model1: `{target_row['model1_filename']}` `{target_row['model1_protocol']}`",
        f"- model1/runner-up/gap: `{target_row['model1_confidence_score']}/{target_row['runner_up_confidence_score']}/{target_row['confidence_gap']}`",
        f"- top5 score mean/spread: `{target_row['top5_confidence_mean']}/{target_row['top5_score_spread']}`",
        f"- diversity/nearest: `{target_row['mean_diversity_to_model1_rmsd']}/{target_row['min_nearest_top5_rmsd']}`",
        "",
        "| rank | role | file | protocol | score | diversity | nearest | geometry | low-conf | high-conf |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for candidate in candidates:
        lines.append(
            f"| `{candidate['input_rank']}` | `{candidate['input_role']}` | `{candidate['filename']}` | "
            f"`{candidate['rerank_bucket']}` | `{candidate['confidence_score']}` | "
            f"`{candidate['diversity_to_model1_rmsd']}` | `{candidate['nearest_top5_rmsd']}` | "
            f"`{candidate['geometry_outlier_score']}` | `{candidate['low_conf_atom_fraction']}` | "
            f"`{candidate['high_conf_atom_fraction']}` |"
        )
    lines.extend(["", "## Claim Boundary", "", CLAIM_BOUNDARY])
    (target_dir / "SELF_ASSESSMENT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    coverage_payload = _read_json(args.coverage_json)
    target_rows: list[dict[str, Any]] = []
    candidate_rows: list[dict[str, Any]] = []
    for row in _coverage_rows(coverage_payload):
        target_row, candidates = _target_packet(row, args.out_dir)
        target_rows.append(target_row)
        candidate_rows.extend(candidates)
    ready_rows = [row for row in target_rows if row["self_assessment_status"] == "ready_external_complex_self_assessment_input"]
    low_margin_rows = [row for row in target_rows if _float(row.get("confidence_gap")) < float(args.low_margin_threshold)]
    first_blocked = next((row for row in target_rows if row["self_assessment_status"] != "ready_external_complex_self_assessment_input"), {})
    summary = {
        "packet_type": "casp17_protein_complex_massivefold_self_assessment_packet",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "protein_complex_massivefold_self_assessment_status": (
            "protein_complex_massivefold_self_assessment_ready_external_only"
            if target_rows and len(ready_rows) == len(target_rows)
            else "protein_complex_massivefold_self_assessment_partial"
        ),
        "coverage_json": _artifact(args.coverage_json),
        "target_count": len(target_rows),
        "ready_target_count": len(ready_rows),
        "blocked_target_count": len(target_rows) - len(ready_rows),
        "heteromer_or_immune_complex_count": sum(1 for row in target_rows if row["target_family"] == "heteromer_or_immune_complex"),
        "candidate_count": len(candidate_rows),
        "model1_input_count": sum(_int(row.get("model1_input_count")) for row in target_rows),
        "top5_input_count": sum(_int(row.get("top5_input_count")) for row in target_rows),
        "missing_artifact_count": sum(_int(row.get("missing_artifact_count")) for row in target_rows),
        "low_margin_threshold": float(args.low_margin_threshold),
        "low_margin_target_count": len(low_margin_rows),
        "external_only_policy": EXTERNAL_ONLY_POLICY,
        "internal_prediction_policy": INTERNAL_PREDICTION_POLICY,
        "submission_policy": SUBMISSION_POLICY,
        "native_policy": NATIVE_POLICY,
        "first_blocked_target_id": _text(first_blocked.get("target_id")),
        "first_blocker": _text(first_blocked.get("blockers")),
        "next_action": (
            "use external-only protein/complex self-assessment features to stress-test model1 selection, "
            "interface triage, and confidence calibration without native or submission claims"
        ),
        "claim_boundary": CLAIM_BOUNDARY,
    }
    return {"summary": summary, "rows": target_rows, "candidate_rows": candidate_rows}


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Protein/Complex MassiveFold Self-Assessment Packet",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- status: `{summary['protein_complex_massivefold_self_assessment_status']}`",
        f"- targets ready/blocked/total: `{summary['ready_target_count']}/{summary['blocked_target_count']}/{summary['target_count']}`",
        f"- heteromer/immune targets: `{summary['heteromer_or_immune_complex_count']}`",
        f"- model1/top5/candidates: `{summary['model1_input_count']}/{summary['top5_input_count']}/{summary['candidate_count']}`",
        f"- low-margin targets: `{summary['low_margin_target_count']}` below `{summary['low_margin_threshold']}`",
        f"- next action: {summary['next_action']}",
        "",
        "## Targets",
        "",
        "| target | family | status | model1 | score gap | top5 mean/spread | diversity/nearest | blockers |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['target_id']}` | `{row['target_family']}` | `{row['self_assessment_status']}` | "
            f"`{row['model1_filename']}` | `{row['confidence_gap']}` | "
            f"`{row['top5_confidence_mean']}/{row['top5_score_spread']}` | "
            f"`{row['mean_diversity_to_model1_rmsd']}/{row['min_nearest_top5_rmsd']}` | "
            f"`{row['blockers'] or '-'}` |"
        )
    lines.extend(["", "## Claim Boundary", "", CLAIM_BOUNDARY])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_outputs(args: argparse.Namespace, payload: dict[str, Any]) -> None:
    for target_row in payload["rows"]:
        candidates = [row for row in payload["candidate_rows"] if row["target_id"] == target_row["target_id"]]
        _write_target_packet(args.out_dir, target_row, candidates)
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"], TARGET_COLUMNS)
    _write_md(args.out_md, payload)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build protein/complex MassiveFold external-only self-assessment packet.")
    parser.add_argument("--coverage-json", default=DEFAULT_COVERAGE_JSON)
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    parser.add_argument("--low-margin-threshold", type=float, default=2.0)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    payload = build_payload(args)
    write_outputs(args, payload)
    print(
        json.dumps(
            {
                "status": payload["summary"]["protein_complex_massivefold_self_assessment_status"],
                "targets": payload["summary"]["target_count"],
                "ready": payload["summary"]["ready_target_count"],
                "blocked": payload["summary"]["blocked_target_count"],
                "candidates": payload["summary"]["candidate_count"],
                "low_margin": payload["summary"]["low_margin_target_count"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

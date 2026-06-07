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

DEFAULT_INPUT_PACKET_JSON = "casp17/casp17_massivefold_rna_model_selection_input_packet_current.json"
DEFAULT_OUT_DIR = "casp17/massivefold_rna_self_assessment"
DEFAULT_OUT_JSON = "casp17/casp17_massivefold_rna_self_assessment_packet_current.json"
DEFAULT_OUT_CSV = "casp17/casp17_massivefold_rna_self_assessment_packet_current.csv"
DEFAULT_OUT_MD = "casp17/CASP17_MASSIVEFOLD_RNA_SELF_ASSESSMENT_PACKET.md"

EXTERNAL_ONLY_POLICY = "external_rerank_accuracy_estimation_self_assessment_only"
INTERNAL_PREDICTION_POLICY = "do_not_mark_as_internal_prediction"
SUBMISSION_POLICY = "do_not_submit_without_rule_check_and_operator_approval"
NATIVE_POLICY = "no_native_structure_or_post_release_accuracy_claim"
R2345_SEQUENCE_GUARD = "ignore_0930_pacific_invalid_dna_t_request_use_1130_replacement_only"
CLAIM_BOUNDARY = (
    "CASP17 MassiveFold RNA self-assessment packet only. It converts organizer-provided external "
    "model1/top5 pointers into no-native confidence, diversity, geometry, and sequence-guard review "
    "features for model-selection calibration. It does not copy coordinates, submit models, use native "
    "structures, or create internal competitive-proof evidence."
)

TARGET_COLUMNS = [
    "target_id",
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
    "mean_diversity_to_model1_rmsd",
    "min_nearest_top5_rmsd",
    "max_geometry_outlier_score",
    "max_low_conf_atom_fraction",
    "r2345_sequence_guard",
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
    "viewer_html_path",
    "model_review_md_path",
    "sequence_guard",
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


def _float(value: Any) -> float:
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return 0.0


def _float_out(value: float) -> str:
    return f"{value:.6f}".rstrip("0").rstrip(".")


def _int(value: Any) -> int:
    try:
        return int(float(str(value).strip()))
    except (TypeError, ValueError):
        return 0


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


def _input_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = payload.get("input_rows")
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def _target_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = payload.get("rows")
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def _by_target(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    targets: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        target_id = _text(row.get("target_id")).upper()
        if target_id:
            targets.setdefault(target_id, []).append(row)
    for target_rows in targets.values():
        target_rows.sort(key=lambda row: _int(row.get("input_rank")))
    return targets


def _source_features(rows: list[dict[str, Any]]) -> dict[str, dict[str, str]]:
    features: dict[str, dict[str, str]] = {}
    manifests = {_text(row.get("source_top5_manifest_csv")) for row in rows}
    for manifest in manifests:
        if not manifest:
            continue
        for source_row in _read_csv(manifest):
            filename = _text(source_row.get("filename"))
            if filename:
                features[filename] = source_row
    return features


def _candidate_row(row: dict[str, Any], source_row: dict[str, str]) -> dict[str, Any]:
    return {
        "target_id": _text(row.get("target_id")).upper(),
        "input_rank": _int(row.get("input_rank")),
        "input_role": _text(row.get("input_role")),
        "filename": _text(row.get("filename")),
        "rerank_bucket": _text(row.get("rerank_bucket")),
        "confidence_score": _float_out(_float(row.get("confidence_score"))),
        "diversity_to_model1_rmsd": _float_out(_float(source_row.get("diversity_to_model1_rmsd"))),
        "nearest_top5_rmsd": _float_out(_float(source_row.get("nearest_top5_rmsd"))),
        "geometry_outlier_score": _float_out(_float(source_row.get("geometry_outlier_score"))),
        "low_conf_atom_fraction": _float_out(_float(source_row.get("low_conf_atom_fraction"))),
        "high_conf_atom_fraction": _float_out(_float(source_row.get("high_conf_atom_fraction"))),
        "viewer_html_path": _text(row.get("viewer_html_path")),
        "model_review_md_path": _text(row.get("model_review_md_path")),
        "sequence_guard": _text(row.get("sequence_guard")),
        "source_top5_manifest_csv": _text(row.get("source_top5_manifest_csv")),
        "claim_boundary": CLAIM_BOUNDARY,
    }


def _target_row(
    target_id: str,
    target_input_row: dict[str, Any],
    rows: list[dict[str, Any]],
    out_dir: str | Path,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    source_features = _source_features(rows)
    candidates = [_candidate_row(row, source_features.get(_text(row.get("filename")), {})) for row in rows]
    scores = [_float(row.get("confidence_score")) for row in candidates]
    model1_rows = [row for row in candidates if row["input_role"] == "model1"]
    model1 = model1_rows[0] if model1_rows else {}
    runner_up_scores = [_float(row.get("confidence_score")) for row in candidates if row["input_role"] != "model1"]
    runner_up = max(runner_up_scores) if runner_up_scores else 0.0
    model1_score = _float(model1.get("confidence_score"))
    confidence_gap = model1_score - runner_up if model1 else 0.0
    diversity_values = [_float(row.get("diversity_to_model1_rmsd")) for row in candidates if _float(row.get("diversity_to_model1_rmsd")) > 0]
    nearest_values = [_float(row.get("nearest_top5_rmsd")) for row in candidates if _float(row.get("nearest_top5_rmsd")) > 0]
    geometry_values = [_float(row.get("geometry_outlier_score")) for row in candidates]
    low_conf_values = [_float(row.get("low_conf_atom_fraction")) for row in candidates]
    blockers: list[str] = []
    if _text(target_input_row.get("input_status")) != "ready_external_model_selection_input":
        blockers.append("model_selection_input_not_ready")
    if len(candidates) != 5:
        blockers.append("top5_input_count_not_5")
    if len(model1_rows) != 1:
        blockers.append("model1_input_count_not_1")
    if _int(target_input_row.get("missing_artifact_count")):
        blockers.append("input_artifact_missing")
    if target_id == "R2345" and _text(target_input_row.get("sequence_guard")) != R2345_SEQUENCE_GUARD:
        blockers.append("r2345_sequence_guard_missing")
    target_dir = _resolve(out_dir) / target_id.lower()
    row = {
        "target_id": target_id,
        "self_assessment_status": "ready_external_self_assessment_input" if not blockers else "blocked_or_partial",
        "model1_filename": _text(model1.get("filename")),
        "model1_protocol": _text(model1.get("rerank_bucket")),
        "model1_confidence_score": _float_out(model1_score),
        "runner_up_confidence_score": _float_out(runner_up),
        "confidence_gap": _float_out(confidence_gap),
        "top5_confidence_min": _float_out(min(scores) if scores else 0.0),
        "top5_confidence_max": _float_out(max(scores) if scores else 0.0),
        "top5_confidence_mean": _float_out(mean(scores) if scores else 0.0),
        "top5_score_spread": _float_out((max(scores) - min(scores)) if scores else 0.0),
        "model1_input_count": len(model1_rows),
        "top5_input_count": len(candidates),
        "mean_diversity_to_model1_rmsd": _float_out(mean(diversity_values) if diversity_values else 0.0),
        "min_nearest_top5_rmsd": _float_out(min(nearest_values) if nearest_values else 0.0),
        "max_geometry_outlier_score": _float_out(max(geometry_values) if geometry_values else 0.0),
        "max_low_conf_atom_fraction": _float_out(max(low_conf_values) if low_conf_values else 0.0),
        "r2345_sequence_guard": _text(target_input_row.get("sequence_guard")),
        "target_candidate_manifest_csv": _artifact(target_dir / "self_assessment_candidates.csv"),
        "target_self_assessment_md": _artifact(target_dir / "SELF_ASSESSMENT.md"),
        "external_only_policy": EXTERNAL_ONLY_POLICY,
        "internal_prediction_policy": INTERNAL_PREDICTION_POLICY,
        "submission_policy": SUBMISSION_POLICY,
        "native_policy": NATIVE_POLICY,
        "recommended_next_action": (
            "rank-review model1 against top5 confidence, diversity, geometry, and sequence guards; "
            "calibrate only as external no-native self-assessment evidence"
        ),
        "blockers": ",".join(blockers),
        "claim_boundary": CLAIM_BOUNDARY,
    }
    return row, candidates


def _write_target_packet(out_dir: str | Path, target_row: dict[str, Any], candidate_rows: list[dict[str, Any]]) -> None:
    target_dir = _resolve(out_dir) / target_row["target_id"].lower()
    target_dir.mkdir(parents=True, exist_ok=True)
    _write_csv(target_dir / "self_assessment_candidates.csv", candidate_rows, CANDIDATE_COLUMNS)
    lines = [
        f"# {target_row['target_id']} MassiveFold RNA Self-Assessment",
        "",
        f"- status: `{target_row['self_assessment_status']}`",
        f"- model1: `{target_row['model1_filename']}` `{target_row['model1_protocol']}`",
        f"- model1/runner-up/gap: `{target_row['model1_confidence_score']}/{target_row['runner_up_confidence_score']}/{target_row['confidence_gap']}`",
        f"- top5 score mean/spread: `{target_row['top5_confidence_mean']}/{target_row['top5_score_spread']}`",
        f"- diversity/nearest: `{target_row['mean_diversity_to_model1_rmsd']}/{target_row['min_nearest_top5_rmsd']}`",
        f"- R2345 guard: `{target_row['r2345_sequence_guard'] or '-'}`",
        "",
        "| rank | role | file | protocol | score | diversity | nearest | geometry | low-conf |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in candidate_rows:
        lines.append(
            f"| `{row['input_rank']}` | `{row['input_role']}` | `{row['filename']}` | "
            f"`{row['rerank_bucket']}` | `{row['confidence_score']}` | "
            f"`{row['diversity_to_model1_rmsd']}` | `{row['nearest_top5_rmsd']}` | "
            f"`{row['geometry_outlier_score']}` | `{row['low_conf_atom_fraction']}` |"
        )
    lines.extend(["", "## Claim Boundary", "", CLAIM_BOUNDARY])
    (target_dir / "SELF_ASSESSMENT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    input_payload = _read_json(args.input_packet_json)
    target_inputs = {_text(row.get("target_id")).upper(): row for row in _target_rows(input_payload)}
    inputs_by_target = _by_target(_input_rows(input_payload))
    target_rows: list[dict[str, Any]] = []
    candidate_rows: list[dict[str, Any]] = []
    for target_id in sorted(inputs_by_target):
        target_row, candidates = _target_row(target_id, target_inputs.get(target_id, {}), inputs_by_target[target_id], args.out_dir)
        target_rows.append(target_row)
        candidate_rows.extend(candidates)
    ready_rows = [row for row in target_rows if row["self_assessment_status"] == "ready_external_self_assessment_input"]
    low_margin_rows = [row for row in target_rows if _float(row.get("confidence_gap")) < float(args.low_margin_threshold)]
    first_blocked = next((row for row in target_rows if row["self_assessment_status"] != "ready_external_self_assessment_input"), {})
    summary = {
        "packet_type": "casp17_massivefold_rna_self_assessment_packet",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "massivefold_rna_self_assessment_status": (
            "massivefold_rna_self_assessment_ready_external_only"
            if target_rows and len(ready_rows) == len(target_rows)
            else "massivefold_rna_self_assessment_partial"
        ),
        "input_packet_json": _artifact(args.input_packet_json),
        "target_count": len(target_rows),
        "ready_target_count": len(ready_rows),
        "blocked_target_count": len(target_rows) - len(ready_rows),
        "candidate_count": len(candidate_rows),
        "model1_input_count": sum(_int(row.get("model1_input_count")) for row in target_rows),
        "top5_input_count": sum(_int(row.get("top5_input_count")) for row in target_rows),
        "low_margin_threshold": float(args.low_margin_threshold),
        "low_margin_target_count": len(low_margin_rows),
        "r2345_sequence_guard": next((row["r2345_sequence_guard"] for row in target_rows if row["target_id"] == "R2345"), ""),
        "external_only_policy": EXTERNAL_ONLY_POLICY,
        "internal_prediction_policy": INTERNAL_PREDICTION_POLICY,
        "submission_policy": SUBMISSION_POLICY,
        "native_policy": NATIVE_POLICY,
        "first_blocked_target_id": _text(first_blocked.get("target_id")),
        "first_blocker": _text(first_blocked.get("blockers")),
        "next_action": (
            "use the external-only self-assessment features to stress-test model1 selection and confidence "
            "calibration while keeping native-free and no-submission boundaries"
        ),
        "claim_boundary": CLAIM_BOUNDARY,
    }
    return {"summary": summary, "rows": target_rows, "candidate_rows": candidate_rows}


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 MassiveFold RNA Self-Assessment Packet",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- status: `{summary['massivefold_rna_self_assessment_status']}`",
        f"- targets ready/blocked/total: `{summary['ready_target_count']}/{summary['blocked_target_count']}/{summary['target_count']}`",
        f"- model1/top5/candidates: `{summary['model1_input_count']}/{summary['top5_input_count']}/{summary['candidate_count']}`",
        f"- low-margin targets: `{summary['low_margin_target_count']}` below `{summary['low_margin_threshold']}`",
        f"- R2345 guard: `{summary['r2345_sequence_guard'] or '-'}`",
        f"- next action: {summary['next_action']}",
        "",
        "## Targets",
        "",
        "| target | status | model1 | score gap | top5 mean/spread | diversity/nearest | blockers |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['target_id']}` | `{row['self_assessment_status']}` | "
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
    parser = argparse.ArgumentParser(description="Build RNA MassiveFold external-only self-assessment packet.")
    parser.add_argument("--input-packet-json", default=DEFAULT_INPUT_PACKET_JSON)
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    parser.add_argument("--low-margin-threshold", type=float, default=1.0)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    payload = build_payload(args)
    write_outputs(args, payload)
    print(
        json.dumps(
            {
                "status": payload["summary"]["massivefold_rna_self_assessment_status"],
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

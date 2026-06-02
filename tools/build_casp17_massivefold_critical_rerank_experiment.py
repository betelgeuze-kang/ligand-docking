#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]

DEFAULT_RISK_QUEUE_JSON = "casp17/casp17_massivefold_model1_risk_queue_current.json"
DEFAULT_OUT_DIR = "casp17/massivefold_critical_rerank_experiments"
DEFAULT_OUT_JSON = "casp17/casp17_massivefold_critical_rerank_experiment_current.json"
DEFAULT_OUT_CSV = "casp17/casp17_massivefold_critical_rerank_experiment_current.csv"
DEFAULT_OUT_MD = "casp17/CASP17_MASSIVEFOLD_CRITICAL_RERANK_EXPERIMENT.md"

CLAIM_BOUNDARY = (
    "CASP17 MassiveFold critical rerank experiment packet only. It converts external no-native model1 "
    "risk rows into rerank and calibration work items for accuracy estimation. It does not copy "
    "coordinates, use native structures, create internal competitive-proof evidence, or submit models."
)
EXTERNAL_ONLY_POLICY = "external_critical_rerank_calibration_experiment_only"
INTERNAL_PREDICTION_POLICY = "do_not_mark_as_internal_prediction"
SUBMISSION_POLICY = "do_not_submit_without_rule_check_and_operator_approval"

ROW_COLUMNS = [
    "experiment_rank",
    "experiment_status",
    "queue_rank",
    "target_group",
    "target_id",
    "target_family",
    "risk_tier",
    "confidence_gap",
    "gap_severity_score",
    "top5_score_spread",
    "top5_confidence_mean",
    "mean_diversity_to_model1_rmsd",
    "min_nearest_top5_rmsd",
    "max_geometry_outlier_score",
    "max_low_conf_atom_fraction",
    "model1_filename",
    "model1_protocol",
    "diversity_review_flag",
    "geometry_review_flag",
    "low_confidence_review_flag",
    "rerank_formula_id",
    "calibration_probe_id",
    "recommended_review_order",
    "experiment_md",
    "source_risk_action_md",
    "source_risk_queue_json",
    "blockers",
    "external_only_policy",
    "internal_prediction_policy",
    "submission_policy",
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


def _rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = payload.get("rows")
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def _summary(payload: dict[str, Any]) -> dict[str, Any]:
    summary = payload.get("summary")
    return summary if isinstance(summary, dict) else {}


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_csv(path_like: str | Path, rows: list[dict[str, Any]]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=ROW_COLUMNS, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _flag_diversity(value: float) -> str:
    if value >= 40.0:
        return "high_diversity_review"
    if value >= 20.0:
        return "moderate_diversity_review"
    return "compact_top5_review"


def _flag_geometry(value: float) -> str:
    return "geometry_outlier_review" if value >= 3.0 else "geometry_watch"


def _flag_low_confidence(value: float) -> str:
    return "low_confidence_atom_review" if value >= 0.04 else "low_confidence_watch"


def _recommended_review_order(row: dict[str, Any]) -> str:
    if row["target_group"] == "protein_complex":
        return "interface_geometry_then_model1_gap_then_top5_diversity"
    if row["diversity_review_flag"] == "high_diversity_review":
        return "top5_diversity_then_geometry_then_model1_gap"
    return "model1_gap_then_geometry_then_top5_diversity"


def _experiment_dir_name(row: dict[str, Any]) -> str:
    return f"{int(row['experiment_rank']):02d}_{row['target_group']}_{row['target_id'].lower()}"


def _build_rows(payload: dict[str, Any], source_json: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for source in _rows(payload):
        if _text(source.get("risk_tier")) != "critical_model1_margin":
            continue
        blockers = _text(source.get("blockers"))
        if _int(source.get("missing_artifact_count")):
            blockers = ",".join(filter(None, [blockers, "input_artifact_missing"]))
        gap = _float(source.get("confidence_gap"))
        diversity = _float(source.get("mean_diversity_to_model1_rmsd"))
        geometry = _float(source.get("max_geometry_outlier_score"))
        low_conf = _float(source.get("max_low_conf_atom_fraction"))
        row = {
            "experiment_rank": 0,
            "experiment_status": (
                "ready_external_no_native_rerank_experiment"
                if not blockers
                else "blocked_external_no_native_rerank_experiment"
            ),
            "queue_rank": _int(source.get("queue_rank")),
            "target_group": _text(source.get("target_group")),
            "target_id": _text(source.get("target_id")).upper(),
            "target_family": _text(source.get("target_family")),
            "risk_tier": _text(source.get("risk_tier")),
            "confidence_gap": _float_out(gap),
            "gap_severity_score": _float_out(max(0.0, (0.1 - gap) / 0.1)),
            "top5_score_spread": _text(source.get("top5_score_spread")),
            "top5_confidence_mean": _text(source.get("top5_confidence_mean")),
            "mean_diversity_to_model1_rmsd": _text(source.get("mean_diversity_to_model1_rmsd")),
            "min_nearest_top5_rmsd": _text(source.get("min_nearest_top5_rmsd")),
            "max_geometry_outlier_score": _text(source.get("max_geometry_outlier_score")),
            "max_low_conf_atom_fraction": _text(source.get("max_low_conf_atom_fraction")),
            "model1_filename": _text(source.get("model1_filename")),
            "model1_protocol": _text(source.get("model1_protocol")),
            "diversity_review_flag": _flag_diversity(diversity),
            "geometry_review_flag": _flag_geometry(geometry),
            "low_confidence_review_flag": _flag_low_confidence(low_conf),
            "rerank_formula_id": "gap_plus_geometry_plus_diversity_penalty_v1",
            "calibration_probe_id": "model1_top5_near_tie_no_native_probe_v1",
            "recommended_review_order": "",
            "experiment_md": "",
            "source_risk_action_md": _text(source.get("target_action_md")),
            "source_risk_queue_json": _artifact(source_json),
            "blockers": blockers,
            "external_only_policy": EXTERNAL_ONLY_POLICY,
            "internal_prediction_policy": INTERNAL_PREDICTION_POLICY,
            "submission_policy": SUBMISSION_POLICY,
            "claim_boundary": CLAIM_BOUNDARY,
        }
        row["recommended_review_order"] = _recommended_review_order(row)
        rows.append(row)
    return sorted(rows, key=lambda row: (row["queue_rank"], row["target_id"]))


def _write_experiment_packets(out_dir: str | Path, rows: list[dict[str, Any]]) -> None:
    for row in rows:
        target_dir = _resolve(out_dir) / _experiment_dir_name(row)
        target_dir.mkdir(parents=True, exist_ok=True)
        row["experiment_md"] = _artifact(target_dir / "EXPERIMENT.md")
        _write_csv(target_dir / "experiment_row.csv", [row])
        lines = [
            f"# {row['target_id']} Critical Rerank Experiment",
            "",
            f"- experiment_rank: `{row['experiment_rank']}`",
            f"- queue_rank: `{row['queue_rank']}`",
            f"- status: `{row['experiment_status']}`",
            f"- target_group: `{row['target_group']}`",
            f"- risk_tier/gap/severity: `{row['risk_tier']}/{row['confidence_gap']}/{row['gap_severity_score']}`",
            f"- model1: `{row['model1_filename']}` `{row['model1_protocol']}`",
            f"- spread/diversity/nearest: `{row['top5_score_spread']}/{row['mean_diversity_to_model1_rmsd']}/{row['min_nearest_top5_rmsd']}`",
            f"- geometry/low_confidence: `{row['max_geometry_outlier_score']}/{row['max_low_conf_atom_fraction']}`",
            f"- review_flags: `{row['diversity_review_flag']}` `{row['geometry_review_flag']}` `{row['low_confidence_review_flag']}`",
            f"- recommended_review_order: `{row['recommended_review_order']}`",
            f"- rerank_formula_id: `{row['rerank_formula_id']}`",
            f"- calibration_probe_id: `{row['calibration_probe_id']}`",
            f"- source_risk_action_md: `{row['source_risk_action_md'] or '-'}`",
            "",
            "## Experiment Contract",
            "",
            "Use model1/top5 self-assessment features only: confidence gap, top5 spread, diversity to model1, "
            "nearest top5 RMSD, geometry outlier score, and low-confidence atom fraction. Keep all native, "
            "submission, and internal-proof lanes closed.",
            "",
            "## Claim Boundary",
            "",
            CLAIM_BOUNDARY,
        ]
        (target_dir / "EXPERIMENT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    risk_payload = _read_json(args.risk_queue_json)
    risk_summary = _summary(risk_payload)
    rows = _build_rows(risk_payload, args.risk_queue_json)
    for rank, row in enumerate(rows, start=1):
        row["experiment_rank"] = rank
    ready_rows = [row for row in rows if not row["blockers"]]
    first = rows[0] if rows else {}
    source_ready = _text(risk_summary.get("massivefold_model1_risk_queue_status")).endswith(
        "ready_external_only"
    )
    summary = {
        "packet_type": "casp17_massivefold_critical_rerank_experiment",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "massivefold_critical_rerank_experiment_status": (
            "massivefold_critical_rerank_experiment_ready_external_only"
            if source_ready and rows and len(ready_rows) == len(rows)
            else "massivefold_critical_rerank_experiment_partial"
        ),
        "risk_queue_json": _artifact(args.risk_queue_json),
        "experiment_count": len(rows),
        "ready_experiment_count": len(ready_rows),
        "blocked_experiment_count": len(rows) - len(ready_rows),
        "rna_hybrid_experiment_count": sum(1 for row in rows if row["target_group"] == "rna_hybrid"),
        "protein_complex_experiment_count": sum(
            1 for row in rows if row["target_group"] == "protein_complex"
        ),
        "high_diversity_review_count": sum(
            1 for row in rows if row["diversity_review_flag"] == "high_diversity_review"
        ),
        "geometry_review_count": sum(
            1 for row in rows if row["geometry_review_flag"] == "geometry_outlier_review"
        ),
        "low_confidence_review_count": sum(
            1 for row in rows if row["low_confidence_review_flag"] == "low_confidence_atom_review"
        ),
        "first_experiment_target_id": _text(first.get("target_id")),
        "first_experiment_group": _text(first.get("target_group")),
        "first_experiment_gap": _text(first.get("confidence_gap")),
        "first_experiment_order": _text(first.get("recommended_review_order")),
        "rerank_formula_id": "gap_plus_geometry_plus_diversity_penalty_v1",
        "calibration_probe_id": "model1_top5_near_tie_no_native_probe_v1",
        "external_only_policy": EXTERNAL_ONLY_POLICY,
        "internal_prediction_policy": INTERNAL_PREDICTION_POLICY,
        "submission_policy": SUBMISSION_POLICY,
        "next_action": (
            "run the critical no-native rerank probes, then promote calibrated model1 selection rules "
            "back into the accuracy-estimation lane"
        ),
        "claim_boundary": CLAIM_BOUNDARY,
    }
    return {"summary": summary, "rows": rows}


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 MassiveFold Critical Rerank Experiment",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- status: `{summary['massivefold_critical_rerank_experiment_status']}`",
        f"- experiments ready/blocked/total: `{summary['ready_experiment_count']}/{summary['blocked_experiment_count']}/{summary['experiment_count']}`",
        f"- RNA/protein-complex experiments: `{summary['rna_hybrid_experiment_count']}/{summary['protein_complex_experiment_count']}`",
        f"- high-diversity/geometry/low-confidence reviews: `{summary['high_diversity_review_count']}/{summary['geometry_review_count']}/{summary['low_confidence_review_count']}`",
        f"- first experiment: `{summary['first_experiment_target_id'] or '-'}` `{summary['first_experiment_group'] or '-'}` `{summary['first_experiment_gap'] or '-'}` `{summary['first_experiment_order'] or '-'}`",
        f"- rerank_formula_id: `{summary['rerank_formula_id']}`",
        f"- calibration_probe_id: `{summary['calibration_probe_id']}`",
        f"- next action: {summary['next_action']}",
        "",
        "## Experiments",
        "",
        "| rank | queue | group | target | gap | severity | diversity | geometry | low-conf | order | packet |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['experiment_rank']}` | `{row['queue_rank']}` | `{row['target_group']}` | "
            f"`{row['target_id']}` | `{row['confidence_gap']}` | `{row['gap_severity_score']}` | "
            f"`{row['diversity_review_flag']}` | `{row['geometry_review_flag']}` | "
            f"`{row['low_confidence_review_flag']}` | `{row['recommended_review_order']}` | "
            f"`{row['experiment_md']}` |"
        )
    lines.extend(["", "## Claim Boundary", "", CLAIM_BOUNDARY])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_outputs(args: argparse.Namespace, payload: dict[str, Any]) -> None:
    _write_experiment_packets(args.out_dir, payload["rows"])
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"])
    _write_md(args.out_md, payload)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build CASP17 MassiveFold critical rerank experiment packet.")
    parser.add_argument("--risk-queue-json", default=DEFAULT_RISK_QUEUE_JSON)
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    payload = build_payload(args)
    write_outputs(args, payload)
    print(
        json.dumps(
            {
                "status": payload["summary"]["massivefold_critical_rerank_experiment_status"],
                "experiments": payload["summary"]["experiment_count"],
                "ready": payload["summary"]["ready_experiment_count"],
                "first": payload["summary"]["first_experiment_target_id"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

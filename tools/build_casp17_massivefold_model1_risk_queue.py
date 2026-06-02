#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]

DEFAULT_RNA_SELF_ASSESSMENT_JSON = "casp17/casp17_massivefold_rna_self_assessment_packet_current.json"
DEFAULT_PROTEIN_COMPLEX_SELF_ASSESSMENT_JSON = (
    "casp17/casp17_protein_complex_massivefold_self_assessment_packet_current.json"
)
DEFAULT_OUT_DIR = "casp17/massivefold_model1_risk_queue"
DEFAULT_OUT_JSON = "casp17/casp17_massivefold_model1_risk_queue_current.json"
DEFAULT_OUT_CSV = "casp17/casp17_massivefold_model1_risk_queue_current.csv"
DEFAULT_OUT_MD = "casp17/CASP17_MASSIVEFOLD_MODEL1_RISK_QUEUE.md"

CLAIM_BOUNDARY = (
    "CASP17 MassiveFold model1 risk queue only. It ranks organizer-provided external RNA, protein, "
    "immune, and complex model1/top5 self-assessment rows for no-native reranking and accuracy-estimation "
    "follow-up. It does not copy coordinates, submit models, use native structures, or create internal "
    "competitive-proof evidence."
)
EXTERNAL_ONLY_POLICY = "external_model1_risk_queue_for_rerank_accuracy_estimation_only"
INTERNAL_PREDICTION_POLICY = "do_not_mark_as_internal_prediction"
SUBMISSION_POLICY = "do_not_submit_without_rule_check_and_operator_approval"

ROW_COLUMNS = [
    "queue_rank",
    "target_group",
    "target_id",
    "target_family",
    "risk_tier",
    "low_margin",
    "confidence_gap",
    "low_margin_threshold",
    "model1_filename",
    "model1_protocol",
    "top5_confidence_mean",
    "top5_score_spread",
    "mean_diversity_to_model1_rmsd",
    "min_nearest_top5_rmsd",
    "max_geometry_outlier_score",
    "max_low_conf_atom_fraction",
    "missing_artifact_count",
    "sequence_guard",
    "source_self_assessment_json",
    "target_action_md",
    "next_action",
    "external_only_policy",
    "internal_prediction_policy",
    "submission_policy",
    "blockers",
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


def _risk_tier(gap: float, threshold: float) -> str:
    if gap < 0.1:
        return "critical_model1_margin"
    if gap < threshold:
        return "high_model1_margin"
    return "watch_model1_margin"


def _next_action(row: dict[str, Any]) -> str:
    if row["low_margin"]:
        return (
            "manually review model1 versus top5 diversity and geometry, then add a rerank/calibration "
            "experiment before treating model1 as stable"
        )
    return "keep as lower-priority external model1 watch item and revisit after low-margin targets"


def _queue_rows_for_payload(
    *,
    payload: dict[str, Any],
    source_json: str,
    target_group: str,
    status_key: str,
    ready_status: str,
) -> list[dict[str, Any]]:
    summary = _summary(payload)
    threshold = _float(summary.get("low_margin_threshold"))
    rows: list[dict[str, Any]] = []
    for row in _rows(payload):
        gap = _float(row.get("confidence_gap"))
        low_margin = gap < threshold if threshold else False
        status = _text(row.get(status_key))
        blockers: list[str] = []
        if status != ready_status:
            blockers.append("self_assessment_not_ready")
        if _int(row.get("missing_artifact_count")):
            blockers.append("input_artifact_missing")
        rows.append(
            {
                "queue_rank": 0,
                "target_group": target_group,
                "target_id": _text(row.get("target_id")).upper(),
                "target_family": _text(row.get("target_family")) or target_group,
                "risk_tier": _risk_tier(gap, threshold),
                "low_margin": low_margin,
                "confidence_gap": _float_out(gap),
                "low_margin_threshold": _float_out(threshold),
                "model1_filename": _text(row.get("model1_filename")),
                "model1_protocol": _text(row.get("model1_protocol")),
                "top5_confidence_mean": _text(row.get("top5_confidence_mean")),
                "top5_score_spread": _text(row.get("top5_score_spread")),
                "mean_diversity_to_model1_rmsd": _text(row.get("mean_diversity_to_model1_rmsd")),
                "min_nearest_top5_rmsd": _text(row.get("min_nearest_top5_rmsd")),
                "max_geometry_outlier_score": _text(row.get("max_geometry_outlier_score")),
                "max_low_conf_atom_fraction": _text(row.get("max_low_conf_atom_fraction")),
                "missing_artifact_count": _int(row.get("missing_artifact_count")),
                "sequence_guard": _text(row.get("r2345_sequence_guard")),
                "source_self_assessment_json": _artifact(source_json),
                "target_action_md": "",
                "next_action": "",
                "external_only_policy": EXTERNAL_ONLY_POLICY,
                "internal_prediction_policy": INTERNAL_PREDICTION_POLICY,
                "submission_policy": SUBMISSION_POLICY,
                "blockers": ",".join(blockers),
                "claim_boundary": CLAIM_BOUNDARY,
            }
        )
    return rows


def _sort_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        rows,
        key=lambda row: (
            0 if row["low_margin"] else 1,
            _float(row.get("confidence_gap")),
            0 if row["target_group"] == "protein_complex" else 1,
            row["target_id"],
        ),
    )


def _target_dir_name(row: dict[str, Any]) -> str:
    return f"{int(row['queue_rank']):02d}_{row['target_group']}_{row['target_id'].lower()}"


def _write_action_packets(out_dir: str | Path, rows: list[dict[str, Any]]) -> None:
    for row in rows:
        target_dir = _resolve(out_dir) / _target_dir_name(row)
        target_dir.mkdir(parents=True, exist_ok=True)
        row["target_action_md"] = _artifact(target_dir / "RISK_ACTION.md")
        _write_csv(target_dir / "risk_queue_row.csv", [row])
        lines = [
            f"# {row['target_id']} Model1 Risk Action",
            "",
            f"- queue_rank: `{row['queue_rank']}`",
            f"- target_group: `{row['target_group']}`",
            f"- target_family: `{row['target_family']}`",
            f"- risk_tier: `{row['risk_tier']}`",
            f"- confidence_gap/threshold: `{row['confidence_gap']}/{row['low_margin_threshold']}`",
            f"- model1: `{row['model1_filename']}` `{row['model1_protocol']}`",
            f"- top5 mean/spread: `{row['top5_confidence_mean']}/{row['top5_score_spread']}`",
            f"- diversity/nearest: `{row['mean_diversity_to_model1_rmsd']}/{row['min_nearest_top5_rmsd']}`",
            f"- sequence_guard: `{row['sequence_guard'] or '-'}`",
            f"- next_action: {row['next_action']}",
            "",
            "## Claim Boundary",
            "",
            CLAIM_BOUNDARY,
        ]
        (target_dir / "RISK_ACTION.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    rna_payload = _read_json(args.rna_self_assessment_json)
    protein_payload = _read_json(args.protein_complex_self_assessment_json)
    rows = [
        *_queue_rows_for_payload(
            payload=rna_payload,
            source_json=args.rna_self_assessment_json,
            target_group="rna_hybrid",
            status_key="self_assessment_status",
            ready_status="ready_external_self_assessment_input",
        ),
        *_queue_rows_for_payload(
            payload=protein_payload,
            source_json=args.protein_complex_self_assessment_json,
            target_group="protein_complex",
            status_key="self_assessment_status",
            ready_status="ready_external_complex_self_assessment_input",
        ),
    ]
    rows = _sort_rows(rows)
    for rank, row in enumerate(rows, start=1):
        row["queue_rank"] = rank
        row["next_action"] = _next_action(row)
    ready_rows = [row for row in rows if not row["blockers"]]
    low_margin_rows = [row for row in rows if row["low_margin"]]
    first = rows[0] if rows else {}
    summary = {
        "packet_type": "casp17_massivefold_model1_risk_queue",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "massivefold_model1_risk_queue_status": (
            "massivefold_model1_risk_queue_ready_external_only"
            if rows and len(ready_rows) == len(rows)
            else "massivefold_model1_risk_queue_partial"
        ),
        "rna_self_assessment_json": _artifact(args.rna_self_assessment_json),
        "protein_complex_self_assessment_json": _artifact(args.protein_complex_self_assessment_json),
        "target_count": len(rows),
        "ready_target_count": len(ready_rows),
        "blocked_target_count": len(rows) - len(ready_rows),
        "low_margin_target_count": len(low_margin_rows),
        "critical_margin_target_count": sum(1 for row in rows if row["risk_tier"] == "critical_model1_margin"),
        "rna_hybrid_target_count": sum(1 for row in rows if row["target_group"] == "rna_hybrid"),
        "protein_complex_target_count": sum(1 for row in rows if row["target_group"] == "protein_complex"),
        "first_priority_target_id": _text(first.get("target_id")),
        "first_priority_group": _text(first.get("target_group")),
        "first_priority_gap": _text(first.get("confidence_gap")),
        "first_priority_risk_tier": _text(first.get("risk_tier")),
        "external_only_policy": EXTERNAL_ONLY_POLICY,
        "internal_prediction_policy": INTERNAL_PREDICTION_POLICY,
        "submission_policy": SUBMISSION_POLICY,
        "next_action": (
            "work low-margin model1 targets first, especially protein/immune complexes, and use the queue "
            "to drive external rerank and self-assessment calibration experiments"
        ),
        "claim_boundary": CLAIM_BOUNDARY,
    }
    return {"summary": summary, "rows": rows}


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 MassiveFold Model1 Risk Queue",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- status: `{summary['massivefold_model1_risk_queue_status']}`",
        f"- targets ready/blocked/total: `{summary['ready_target_count']}/{summary['blocked_target_count']}/{summary['target_count']}`",
        f"- low-margin/critical targets: `{summary['low_margin_target_count']}/{summary['critical_margin_target_count']}`",
        f"- RNA/protein-complex targets: `{summary['rna_hybrid_target_count']}/{summary['protein_complex_target_count']}`",
        f"- first priority: `{summary['first_priority_target_id'] or '-'}` `{summary['first_priority_group'] or '-'}` `{summary['first_priority_gap'] or '-'}` `{summary['first_priority_risk_tier'] or '-'}`",
        f"- next action: {summary['next_action']}",
        "",
        "## Queue",
        "",
        "| rank | group | target | tier | gap | threshold | model1 | spread | diversity | action |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['queue_rank']}` | `{row['target_group']}` | `{row['target_id']}` | "
            f"`{row['risk_tier']}` | `{row['confidence_gap']}` | `{row['low_margin_threshold']}` | "
            f"`{row['model1_filename']}` | `{row['top5_score_spread']}` | "
            f"`{row['mean_diversity_to_model1_rmsd']}` | `{row['target_action_md']}` |"
        )
    lines.extend(["", "## Claim Boundary", "", CLAIM_BOUNDARY])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_outputs(args: argparse.Namespace, payload: dict[str, Any]) -> None:
    _write_action_packets(args.out_dir, payload["rows"])
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"])
    _write_md(args.out_md, payload)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build unified CASP17 MassiveFold model1 risk queue.")
    parser.add_argument("--rna-self-assessment-json", default=DEFAULT_RNA_SELF_ASSESSMENT_JSON)
    parser.add_argument(
        "--protein-complex-self-assessment-json",
        default=DEFAULT_PROTEIN_COMPLEX_SELF_ASSESSMENT_JSON,
    )
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
                "status": payload["summary"]["massivefold_model1_risk_queue_status"],
                "targets": payload["summary"]["target_count"],
                "low_margin": payload["summary"]["low_margin_target_count"],
                "critical": payload["summary"]["critical_margin_target_count"],
                "first": payload["summary"]["first_priority_target_id"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

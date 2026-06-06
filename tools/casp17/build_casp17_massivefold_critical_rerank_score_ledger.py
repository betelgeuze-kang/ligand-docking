#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]

DEFAULT_EXPERIMENT_JSON = "casp17/casp17_massivefold_critical_rerank_experiment_current.json"
DEFAULT_OUT_DIR = "casp17/massivefold_critical_rerank_score_ledger"
DEFAULT_OUT_JSON = "casp17/casp17_massivefold_critical_rerank_score_ledger_current.json"
DEFAULT_OUT_CSV = "casp17/casp17_massivefold_critical_rerank_score_ledger_current.csv"
DEFAULT_OUT_MD = "casp17/CASP17_MASSIVEFOLD_CRITICAL_RERANK_SCORE_LEDGER.md"

CLAIM_BOUNDARY = (
    "CASP17 MassiveFold critical rerank score ledger only. Scores are no-native model-selection risk "
    "scores from external self-assessment features; they are not native accuracy, internal prediction "
    "proof, or CASP submission evidence."
)
EXTERNAL_ONLY_POLICY = "external_no_native_rerank_score_ledger_only"
INTERNAL_PREDICTION_POLICY = "do_not_mark_as_internal_prediction"
SUBMISSION_POLICY = "do_not_submit_without_rule_check_and_operator_approval"

ROW_COLUMNS = [
    "ledger_rank",
    "ledger_status",
    "experiment_rank",
    "queue_rank",
    "target_group",
    "target_id",
    "risk_score",
    "risk_band",
    "rerank_action",
    "gap_component",
    "diversity_component",
    "geometry_component",
    "low_confidence_component",
    "interface_component",
    "confidence_gap",
    "gap_severity_score",
    "diversity_review_flag",
    "geometry_review_flag",
    "low_confidence_review_flag",
    "recommended_review_order",
    "model1_filename",
    "model1_protocol",
    "ledger_md",
    "source_experiment_md",
    "source_experiment_json",
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


def _int(value: Any) -> int:
    try:
        return int(float(str(value).strip()))
    except (TypeError, ValueError):
        return 0


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


def _diversity_penalty(flag: str) -> float:
    if flag == "high_diversity_review":
        return 1.0
    if flag == "moderate_diversity_review":
        return 0.5
    return 0.15


def _geometry_penalty(flag: str) -> float:
    return 1.0 if flag == "geometry_outlier_review" else 0.2


def _low_conf_penalty(flag: str) -> float:
    return 1.0 if flag == "low_confidence_atom_review" else 0.1


def _risk_band(score: float) -> str:
    if score >= 70.0:
        return "immediate_rerank_required"
    if score >= 50.0:
        return "calibrate_before_model1_freeze"
    return "critical_watch_with_targeted_probe"


def _rerank_action(band: str) -> str:
    if band == "immediate_rerank_required":
        return "rerank_top5_before_any_model1_freeze"
    if band == "calibrate_before_model1_freeze":
        return "run_targeted_probe_then_freeze_model1_if_consistent"
    return "keep_in_critical_batch_and_rescore_after_probe"


def _ledger_dir_name(row: dict[str, Any]) -> str:
    return f"{int(row['ledger_rank']):02d}_{row['target_group']}_{row['target_id'].lower()}"


def _build_rows(payload: dict[str, Any], source_json: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for source in _rows(payload):
        blockers = _text(source.get("blockers"))
        gap_component = min(1.0, max(0.0, _float(source.get("gap_severity_score"))))
        diversity_component = _diversity_penalty(_text(source.get("diversity_review_flag")))
        geometry_component = _geometry_penalty(_text(source.get("geometry_review_flag")))
        low_conf_component = _low_conf_penalty(_text(source.get("low_confidence_review_flag")))
        interface_component = 0.15 if _text(source.get("target_group")) == "protein_complex" else 0.0
        risk_score = min(
            100.0,
            100.0
            * (
                0.45 * gap_component
                + 0.25 * diversity_component
                + 0.2 * geometry_component
                + 0.1 * low_conf_component
                + interface_component
            ),
        )
        band = _risk_band(risk_score)
        rows.append(
            {
                "ledger_rank": 0,
                "ledger_status": "ready_external_no_native_rerank_score" if not blockers else "blocked_rerank_score",
                "experiment_rank": _int(source.get("experiment_rank")),
                "queue_rank": _int(source.get("queue_rank")),
                "target_group": _text(source.get("target_group")),
                "target_id": _text(source.get("target_id")).upper(),
                "risk_score": _float_out(risk_score),
                "risk_band": band,
                "rerank_action": _rerank_action(band),
                "gap_component": _float_out(gap_component),
                "diversity_component": _float_out(diversity_component),
                "geometry_component": _float_out(geometry_component),
                "low_confidence_component": _float_out(low_conf_component),
                "interface_component": _float_out(interface_component),
                "confidence_gap": _text(source.get("confidence_gap")),
                "gap_severity_score": _text(source.get("gap_severity_score")),
                "diversity_review_flag": _text(source.get("diversity_review_flag")),
                "geometry_review_flag": _text(source.get("geometry_review_flag")),
                "low_confidence_review_flag": _text(source.get("low_confidence_review_flag")),
                "recommended_review_order": _text(source.get("recommended_review_order")),
                "model1_filename": _text(source.get("model1_filename")),
                "model1_protocol": _text(source.get("model1_protocol")),
                "ledger_md": "",
                "source_experiment_md": _text(source.get("experiment_md")),
                "source_experiment_json": _artifact(source_json),
                "blockers": blockers,
                "external_only_policy": EXTERNAL_ONLY_POLICY,
                "internal_prediction_policy": INTERNAL_PREDICTION_POLICY,
                "submission_policy": SUBMISSION_POLICY,
                "claim_boundary": CLAIM_BOUNDARY,
            }
        )
    return sorted(rows, key=lambda row: (-_float(row["risk_score"]), row["queue_rank"], row["target_id"]))


def _write_ledger_packets(out_dir: str | Path, rows: list[dict[str, Any]]) -> None:
    for row in rows:
        target_dir = _resolve(out_dir) / _ledger_dir_name(row)
        target_dir.mkdir(parents=True, exist_ok=True)
        row["ledger_md"] = _artifact(target_dir / "SCORE_LEDGER.md")
        _write_csv(target_dir / "score_ledger_row.csv", [row])
        lines = [
            f"# {row['target_id']} Critical Rerank Score Ledger",
            "",
            f"- ledger_rank: `{row['ledger_rank']}`",
            f"- source experiment/queue: `{row['experiment_rank']}/{row['queue_rank']}`",
            f"- risk_score/band: `{row['risk_score']}/{row['risk_band']}`",
            f"- rerank_action: `{row['rerank_action']}`",
            f"- components gap/diversity/geometry/low_conf/interface: `{row['gap_component']}/{row['diversity_component']}/{row['geometry_component']}/{row['low_confidence_component']}/{row['interface_component']}`",
            f"- model1: `{row['model1_filename']}` `{row['model1_protocol']}`",
            f"- source_experiment_md: `{row['source_experiment_md'] or '-'}`",
            "",
            "## Claim Boundary",
            "",
            CLAIM_BOUNDARY,
        ]
        (target_dir / "SCORE_LEDGER.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    experiment_payload = _read_json(args.experiment_json)
    experiment_summary = _summary(experiment_payload)
    rows = _build_rows(experiment_payload, args.experiment_json)
    for rank, row in enumerate(rows, start=1):
        row["ledger_rank"] = rank
    ready_rows = [row for row in rows if not row["blockers"]]
    first = rows[0] if rows else {}
    source_ready = _text(
        experiment_summary.get("massivefold_critical_rerank_experiment_status")
    ).endswith("ready_external_only")
    summary = {
        "packet_type": "casp17_massivefold_critical_rerank_score_ledger",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "massivefold_critical_rerank_score_ledger_status": (
            "massivefold_critical_rerank_score_ledger_ready_external_only"
            if source_ready and rows and len(ready_rows) == len(rows)
            else "massivefold_critical_rerank_score_ledger_partial"
        ),
        "experiment_json": _artifact(args.experiment_json),
        "ledger_count": len(rows),
        "ready_ledger_count": len(ready_rows),
        "blocked_ledger_count": len(rows) - len(ready_rows),
        "immediate_rerank_required_count": sum(
            1 for row in rows if row["risk_band"] == "immediate_rerank_required"
        ),
        "calibrate_before_model1_freeze_count": sum(
            1 for row in rows if row["risk_band"] == "calibrate_before_model1_freeze"
        ),
        "critical_watch_count": sum(
            1 for row in rows if row["risk_band"] == "critical_watch_with_targeted_probe"
        ),
        "rna_hybrid_ledger_count": sum(1 for row in rows if row["target_group"] == "rna_hybrid"),
        "protein_complex_ledger_count": sum(1 for row in rows if row["target_group"] == "protein_complex"),
        "top_risk_target_id": _text(first.get("target_id")),
        "top_risk_group": _text(first.get("target_group")),
        "top_risk_score": _text(first.get("risk_score")),
        "top_risk_band": _text(first.get("risk_band")),
        "top_rerank_action": _text(first.get("rerank_action")),
        "external_only_policy": EXTERNAL_ONLY_POLICY,
        "internal_prediction_policy": INTERNAL_PREDICTION_POLICY,
        "submission_policy": SUBMISSION_POLICY,
        "next_action": "review the top score-ledger rows first and promote the scoring rule into model1 selection",
        "claim_boundary": CLAIM_BOUNDARY,
    }
    return {"summary": summary, "rows": rows}


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 MassiveFold Critical Rerank Score Ledger",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- status: `{summary['massivefold_critical_rerank_score_ledger_status']}`",
        f"- ledger rows ready/blocked/total: `{summary['ready_ledger_count']}/{summary['blocked_ledger_count']}/{summary['ledger_count']}`",
        f"- bands immediate/calibrate/watch: `{summary['immediate_rerank_required_count']}/{summary['calibrate_before_model1_freeze_count']}/{summary['critical_watch_count']}`",
        f"- RNA/protein-complex rows: `{summary['rna_hybrid_ledger_count']}/{summary['protein_complex_ledger_count']}`",
        f"- top risk: `{summary['top_risk_target_id'] or '-'}` `{summary['top_risk_group'] or '-'}` `{summary['top_risk_score'] or '-'}` `{summary['top_risk_band'] or '-'}` `{summary['top_rerank_action'] or '-'}`",
        f"- next action: {summary['next_action']}",
        "",
        "## Ledger",
        "",
        "| rank | target | group | score | band | action | gap | diversity | geometry | low-conf | interface | packet |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['ledger_rank']}` | `{row['target_id']}` | `{row['target_group']}` | "
            f"`{row['risk_score']}` | `{row['risk_band']}` | `{row['rerank_action']}` | "
            f"`{row['gap_component']}` | `{row['diversity_component']}` | "
            f"`{row['geometry_component']}` | `{row['low_confidence_component']}` | "
            f"`{row['interface_component']}` | `{row['ledger_md']}` |"
        )
    lines.extend(["", "## Claim Boundary", "", CLAIM_BOUNDARY])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_outputs(args: argparse.Namespace, payload: dict[str, Any]) -> None:
    _write_ledger_packets(args.out_dir, payload["rows"])
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"])
    _write_md(args.out_md, payload)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build CASP17 MassiveFold critical rerank score ledger.")
    parser.add_argument("--experiment-json", default=DEFAULT_EXPERIMENT_JSON)
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
                "status": payload["summary"]["massivefold_critical_rerank_score_ledger_status"],
                "rows": payload["summary"]["ledger_count"],
                "top": payload["summary"]["top_risk_target_id"],
                "top_score": payload["summary"]["top_risk_score"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

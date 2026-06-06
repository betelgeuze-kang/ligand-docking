#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]

DEFAULT_GATE_JSON = "casp17/casp17_massivefold_model1_selection_calibration_gate_current.json"
DEFAULT_OUT_DIR = "casp17/massivefold_model1_probe_worklist"
DEFAULT_OUT_JSON = "casp17/casp17_massivefold_model1_probe_worklist_current.json"
DEFAULT_OUT_CSV = "casp17/casp17_massivefold_model1_probe_worklist_current.csv"
DEFAULT_OUT_MD = "casp17/CASP17_MASSIVEFOLD_MODEL1_PROBE_WORKLIST.md"

CLAIM_BOUNDARY = (
    "CASP17 MassiveFold model1 probe worklist only. It turns external no-native calibration gates "
    "into executable probe workitems for model1 selection. It does not use native structures, copy "
    "coordinates, create internal competitive-proof evidence, or submit models."
)
EXTERNAL_ONLY_POLICY = "external_no_native_model1_probe_worklist_only"
INTERNAL_PREDICTION_POLICY = "do_not_mark_as_internal_prediction"
SUBMISSION_POLICY = "do_not_submit_without_rule_check_and_operator_approval"

ROW_COLUMNS = [
    "workitem_rank",
    "workitem_status",
    "gate_rank",
    "target_group",
    "target_id",
    "risk_score",
    "model1_freeze_decision",
    "probe_type",
    "probe_priority",
    "probe_status",
    "execution_mode",
    "required_inputs",
    "scoring_features",
    "probe_exit_criterion",
    "freeze_after_probe_allowed",
    "model1_filename",
    "model1_protocol",
    "source_calibration_gate_md",
    "source_calibration_gate_json",
    "workitem_md",
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


def _features_for_probe(probe_type: str) -> tuple[str, str]:
    if probe_type == "top5_rerank_consistency_probe":
        return (
            "model1,top5,self_assessment_row,score_ledger_row,calibration_gate_row",
            "confidence_gap,top5_spread,diversity_to_model1,geometry_outlier,low_confidence_fraction",
        )
    return (
        "model1,top5,self_assessment_row,score_ledger_row,calibration_gate_row",
        "confidence_gap,top5_spread,nearest_top5_distance,geometry_outlier",
    )


def _priority_for_decision(decision: str) -> int:
    return 1 if decision.startswith("hold_model1_freeze") else 2


def _workitem_dir_name(row: dict[str, Any]) -> str:
    return f"{int(row['workitem_rank']):02d}_{row['target_group']}_{row['target_id'].lower()}"


def _build_rows(payload: dict[str, Any], source_json: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for source in _rows(payload):
        if _text(source.get("probe_required")).lower() != "true":
            continue
        blockers = _text(source.get("blockers"))
        probe_type = _text(source.get("probe_type"))
        required_inputs, scoring_features = _features_for_probe(probe_type)
        decision = _text(source.get("model1_freeze_decision"))
        rows.append(
            {
                "workitem_rank": 0,
                "workitem_status": "ready_external_no_native_probe" if not blockers else "blocked_external_no_native_probe",
                "gate_rank": _int(source.get("gate_rank")),
                "target_group": _text(source.get("target_group")),
                "target_id": _text(source.get("target_id")).upper(),
                "risk_score": _text(source.get("risk_score")),
                "model1_freeze_decision": decision,
                "probe_type": probe_type,
                "probe_priority": _priority_for_decision(decision),
                "probe_status": "probe_ready" if not blockers else "probe_blocked",
                "execution_mode": "no_native_external_self_assessment_rescore",
                "required_inputs": required_inputs,
                "scoring_features": scoring_features,
                "probe_exit_criterion": _text(source.get("probe_exit_criterion")),
                "freeze_after_probe_allowed": "true_if_exit_criterion_passes",
                "model1_filename": _text(source.get("model1_filename")),
                "model1_protocol": _text(source.get("model1_protocol")),
                "source_calibration_gate_md": _text(source.get("calibration_gate_md")),
                "source_calibration_gate_json": _artifact(source_json),
                "workitem_md": "",
                "blockers": blockers,
                "external_only_policy": EXTERNAL_ONLY_POLICY,
                "internal_prediction_policy": INTERNAL_PREDICTION_POLICY,
                "submission_policy": SUBMISSION_POLICY,
                "claim_boundary": CLAIM_BOUNDARY,
            }
        )
    return sorted(rows, key=lambda row: (row["probe_priority"], -_float(row["risk_score"]), row["gate_rank"]))


def _write_workitem_packets(out_dir: str | Path, rows: list[dict[str, Any]]) -> None:
    for row in rows:
        target_dir = _resolve(out_dir) / _workitem_dir_name(row)
        target_dir.mkdir(parents=True, exist_ok=True)
        row["workitem_md"] = _artifact(target_dir / "PROBE_WORKITEM.md")
        _write_csv(target_dir / "probe_workitem_row.csv", [row])
        lines = [
            f"# {row['target_id']} Model1 Probe Workitem",
            "",
            f"- workitem_rank: `{row['workitem_rank']}`",
            f"- gate_rank: `{row['gate_rank']}`",
            f"- status: `{row['workitem_status']}`",
            f"- risk_score: `{row['risk_score']}`",
            f"- model1_freeze_decision: `{row['model1_freeze_decision']}`",
            f"- probe_type/priority/status: `{row['probe_type']}/{row['probe_priority']}/{row['probe_status']}`",
            f"- execution_mode: `{row['execution_mode']}`",
            f"- required_inputs: `{row['required_inputs']}`",
            f"- scoring_features: `{row['scoring_features']}`",
            f"- probe_exit_criterion: {row['probe_exit_criterion']}",
            f"- freeze_after_probe_allowed: `{row['freeze_after_probe_allowed']}`",
            f"- source_calibration_gate_md: `{row['source_calibration_gate_md'] or '-'}`",
            "",
            "## Claim Boundary",
            "",
            CLAIM_BOUNDARY,
        ]
        (target_dir / "PROBE_WORKITEM.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    gate_payload = _read_json(args.calibration_gate_json)
    gate_summary = _summary(gate_payload)
    rows = _build_rows(gate_payload, args.calibration_gate_json)
    for rank, row in enumerate(rows, start=1):
        row["workitem_rank"] = rank
    ready_rows = [row for row in rows if not row["blockers"]]
    first = rows[0] if rows else {}
    source_ready = _text(
        gate_summary.get("massivefold_model1_selection_calibration_gate_status")
    ).endswith("ready_external_only")
    summary = {
        "packet_type": "casp17_massivefold_model1_probe_worklist",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "massivefold_model1_probe_worklist_status": (
            "massivefold_model1_probe_worklist_ready_external_only"
            if source_ready and rows and len(ready_rows) == len(rows)
            else "massivefold_model1_probe_worklist_partial"
        ),
        "calibration_gate_json": _artifact(args.calibration_gate_json),
        "workitem_count": len(rows),
        "ready_workitem_count": len(ready_rows),
        "blocked_workitem_count": len(rows) - len(ready_rows),
        "top5_rerank_consistency_probe_count": sum(
            1 for row in rows if row["probe_type"] == "top5_rerank_consistency_probe"
        ),
        "lightweight_rescore_probe_count": sum(
            1 for row in rows if row["probe_type"] == "lightweight_rescore_probe"
        ),
        "priority1_workitem_count": sum(1 for row in rows if row["probe_priority"] == 1),
        "priority2_workitem_count": sum(1 for row in rows if row["probe_priority"] == 2),
        "rna_hybrid_workitem_count": sum(1 for row in rows if row["target_group"] == "rna_hybrid"),
        "protein_complex_workitem_count": sum(1 for row in rows if row["target_group"] == "protein_complex"),
        "first_workitem_target_id": _text(first.get("target_id")),
        "first_workitem_group": _text(first.get("target_group")),
        "first_workitem_probe_type": _text(first.get("probe_type")),
        "first_workitem_risk_score": _text(first.get("risk_score")),
        "first_workitem_exit_criterion": _text(first.get("probe_exit_criterion")),
        "freeze_unlock_policy": "freeze_after_probe_allowed_only_if_exit_criterion_passes",
        "external_only_policy": EXTERNAL_ONLY_POLICY,
        "internal_prediction_policy": INTERNAL_PREDICTION_POLICY,
        "submission_policy": SUBMISSION_POLICY,
        "next_action": "execute priority-1 no-native probes and write outcomes into the model1 freeze decision lane",
        "claim_boundary": CLAIM_BOUNDARY,
    }
    return {"summary": summary, "rows": rows}


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 MassiveFold Model1 Probe Worklist",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- status: `{summary['massivefold_model1_probe_worklist_status']}`",
        f"- workitems ready/blocked/total: `{summary['ready_workitem_count']}/{summary['blocked_workitem_count']}/{summary['workitem_count']}`",
        f"- probes top5/lightweight: `{summary['top5_rerank_consistency_probe_count']}/{summary['lightweight_rescore_probe_count']}`",
        f"- priority 1/2: `{summary['priority1_workitem_count']}/{summary['priority2_workitem_count']}`",
        f"- RNA/protein-complex: `{summary['rna_hybrid_workitem_count']}/{summary['protein_complex_workitem_count']}`",
        f"- first workitem: `{summary['first_workitem_target_id'] or '-'}` `{summary['first_workitem_group'] or '-'}` `{summary['first_workitem_risk_score'] or '-'}` `{summary['first_workitem_probe_type'] or '-'}`",
        f"- freeze_unlock_policy: `{summary['freeze_unlock_policy']}`",
        f"- next action: {summary['next_action']}",
        "",
        "## Workitems",
        "",
        "| rank | priority | target | group | score | probe | status | features | exit criterion | packet |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['workitem_rank']}` | `{row['probe_priority']}` | `{row['target_id']}` | "
            f"`{row['target_group']}` | `{row['risk_score']}` | `{row['probe_type']}` | "
            f"`{row['probe_status']}` | `{row['scoring_features']}` | "
            f"{row['probe_exit_criterion']} | `{row['workitem_md']}` |"
        )
    lines.extend(["", "## Claim Boundary", "", CLAIM_BOUNDARY])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_outputs(args: argparse.Namespace, payload: dict[str, Any]) -> None:
    _write_workitem_packets(args.out_dir, payload["rows"])
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"])
    _write_md(args.out_md, payload)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build CASP17 MassiveFold model1 probe worklist.")
    parser.add_argument("--calibration-gate-json", default=DEFAULT_GATE_JSON)
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
                "status": payload["summary"]["massivefold_model1_probe_worklist_status"],
                "workitems": payload["summary"]["workitem_count"],
                "ready": payload["summary"]["ready_workitem_count"],
                "first": payload["summary"]["first_workitem_target_id"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

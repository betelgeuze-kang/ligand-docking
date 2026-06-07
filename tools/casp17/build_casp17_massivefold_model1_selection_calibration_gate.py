#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]

DEFAULT_SCORE_LEDGER_JSON = "casp17/casp17_massivefold_critical_rerank_score_ledger_current.json"
DEFAULT_OUT_DIR = "casp17/massivefold_model1_selection_calibration_gate"
DEFAULT_OUT_JSON = "casp17/casp17_massivefold_model1_selection_calibration_gate_current.json"
DEFAULT_OUT_CSV = "casp17/casp17_massivefold_model1_selection_calibration_gate_current.csv"
DEFAULT_OUT_MD = "casp17/CASP17_MASSIVEFOLD_MODEL1_SELECTION_CALIBRATION_GATE.md"

CLAIM_BOUNDARY = (
    "CASP17 MassiveFold model1 selection calibration gate only. It converts external no-native rerank "
    "score ledger rows into model1 freeze, hold, and probe decisions for accuracy-estimation workflow. "
    "It does not use native structures, copy coordinates, create internal competitive-proof evidence, "
    "or submit models."
)
EXTERNAL_ONLY_POLICY = "external_model1_selection_calibration_gate_only"
INTERNAL_PREDICTION_POLICY = "do_not_mark_as_internal_prediction"
SUBMISSION_POLICY = "do_not_submit_without_rule_check_and_operator_approval"
SELECTION_RULE_ID = "no_native_model1_selection_gate_v1"

ROW_COLUMNS = [
    "gate_rank",
    "gate_status",
    "ledger_rank",
    "target_group",
    "target_id",
    "risk_score",
    "risk_band",
    "rerank_action",
    "model1_freeze_decision",
    "model1_freeze_blocker",
    "probe_required",
    "probe_type",
    "probe_exit_criterion",
    "selection_rule_id",
    "model1_filename",
    "model1_protocol",
    "source_score_ledger_md",
    "source_score_ledger_json",
    "calibration_gate_md",
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


def _decision_for_band(risk_band: str) -> tuple[str, str, str, str]:
    if risk_band == "immediate_rerank_required":
        return (
            "hold_model1_freeze_rerank_required",
            "immediate_rerank_required",
            "full_top5_rerank_probe",
            "rerank_score_below_50_or_model1_selected_by_two_independent_no_native_features",
        )
    if risk_band == "calibrate_before_model1_freeze":
        return (
            "hold_model1_freeze_probe_required",
            "calibration_required_before_freeze",
            "top5_rerank_consistency_probe",
            "model1 remains top candidate after gap, diversity, geometry, and low-confidence rescore",
        )
    return (
        "conditional_watch_probe_before_final_model1",
        "critical_watch_requires_rescore",
        "lightweight_rescore_probe",
        "no new high-risk flag appears after targeted no-native rescore",
    )


def _gate_dir_name(row: dict[str, Any]) -> str:
    return f"{int(row['gate_rank']):02d}_{row['target_group']}_{row['target_id'].lower()}"


def _build_rows(payload: dict[str, Any], source_json: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for source in _rows(payload):
        risk_band = _text(source.get("risk_band"))
        decision, blocker, probe_type, exit_criterion = _decision_for_band(risk_band)
        source_blockers = _text(source.get("blockers"))
        rows.append(
            {
                "gate_rank": 0,
                "gate_status": "ready_external_model1_selection_gate" if not source_blockers else "blocked_model1_selection_gate",
                "ledger_rank": _int(source.get("ledger_rank")),
                "target_group": _text(source.get("target_group")),
                "target_id": _text(source.get("target_id")).upper(),
                "risk_score": _text(source.get("risk_score")),
                "risk_band": risk_band,
                "rerank_action": _text(source.get("rerank_action")),
                "model1_freeze_decision": decision,
                "model1_freeze_blocker": blocker,
                "probe_required": "true",
                "probe_type": probe_type,
                "probe_exit_criterion": exit_criterion,
                "selection_rule_id": SELECTION_RULE_ID,
                "model1_filename": _text(source.get("model1_filename")),
                "model1_protocol": _text(source.get("model1_protocol")),
                "source_score_ledger_md": _text(source.get("ledger_md")),
                "source_score_ledger_json": _artifact(source_json),
                "calibration_gate_md": "",
                "blockers": source_blockers,
                "external_only_policy": EXTERNAL_ONLY_POLICY,
                "internal_prediction_policy": INTERNAL_PREDICTION_POLICY,
                "submission_policy": SUBMISSION_POLICY,
                "claim_boundary": CLAIM_BOUNDARY,
            }
        )
    return sorted(rows, key=lambda row: (-_float(row["risk_score"]), row["ledger_rank"], row["target_id"]))


def _write_gate_packets(out_dir: str | Path, rows: list[dict[str, Any]]) -> None:
    for row in rows:
        target_dir = _resolve(out_dir) / _gate_dir_name(row)
        target_dir.mkdir(parents=True, exist_ok=True)
        row["calibration_gate_md"] = _artifact(target_dir / "CALIBRATION_GATE.md")
        _write_csv(target_dir / "calibration_gate_row.csv", [row])
        lines = [
            f"# {row['target_id']} Model1 Selection Calibration Gate",
            "",
            f"- gate_rank: `{row['gate_rank']}`",
            f"- ledger_rank: `{row['ledger_rank']}`",
            f"- risk_score/band: `{row['risk_score']}/{row['risk_band']}`",
            f"- model1_freeze_decision: `{row['model1_freeze_decision']}`",
            f"- model1_freeze_blocker: `{row['model1_freeze_blocker']}`",
            f"- probe_type: `{row['probe_type']}`",
            f"- probe_exit_criterion: {row['probe_exit_criterion']}",
            f"- selection_rule_id: `{row['selection_rule_id']}`",
            f"- model1: `{row['model1_filename']}` `{row['model1_protocol']}`",
            f"- source_score_ledger_md: `{row['source_score_ledger_md'] or '-'}`",
            "",
            "## Claim Boundary",
            "",
            CLAIM_BOUNDARY,
        ]
        (target_dir / "CALIBRATION_GATE.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    ledger_payload = _read_json(args.score_ledger_json)
    ledger_summary = _summary(ledger_payload)
    rows = _build_rows(ledger_payload, args.score_ledger_json)
    for rank, row in enumerate(rows, start=1):
        row["gate_rank"] = rank
    ready_rows = [row for row in rows if not row["blockers"]]
    hold_rows = [
        row
        for row in rows
        if row["model1_freeze_decision"]
        in {"hold_model1_freeze_rerank_required", "hold_model1_freeze_probe_required"}
    ]
    watch_rows = [
        row
        for row in rows
        if row["model1_freeze_decision"] == "conditional_watch_probe_before_final_model1"
    ]
    first = rows[0] if rows else {}
    source_ready = _text(
        ledger_summary.get("massivefold_critical_rerank_score_ledger_status")
    ).endswith("ready_external_only")
    freeze_gate_status = (
        "model1_freeze_blocked_by_calibration"
        if hold_rows
        else "model1_freeze_watch_probe_required"
        if watch_rows
        else "model1_freeze_ready_external_only"
    )
    summary = {
        "packet_type": "casp17_massivefold_model1_selection_calibration_gate",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "massivefold_model1_selection_calibration_gate_status": (
            "massivefold_model1_selection_calibration_gate_ready_external_only"
            if source_ready and rows and len(ready_rows) == len(rows)
            else "massivefold_model1_selection_calibration_gate_partial"
        ),
        "score_ledger_json": _artifact(args.score_ledger_json),
        "gate_count": len(rows),
        "ready_gate_count": len(ready_rows),
        "blocked_gate_count": len(rows) - len(ready_rows),
        "hold_model1_freeze_count": len(hold_rows),
        "watch_probe_count": len(watch_rows),
        "probe_required_count": sum(1 for row in rows if row["probe_required"] == "true"),
        "freeze_ready_count": sum(
            1 for row in rows if row["model1_freeze_decision"] == "model1_freeze_ready"
        ),
        "rna_hybrid_gate_count": sum(1 for row in rows if row["target_group"] == "rna_hybrid"),
        "protein_complex_gate_count": sum(1 for row in rows if row["target_group"] == "protein_complex"),
        "freeze_gate_status": freeze_gate_status,
        "first_gate_target_id": _text(first.get("target_id")),
        "first_gate_group": _text(first.get("target_group")),
        "first_gate_decision": _text(first.get("model1_freeze_decision")),
        "first_gate_probe_type": _text(first.get("probe_type")),
        "top_risk_score": _text(first.get("risk_score")),
        "selection_rule_id": SELECTION_RULE_ID,
        "external_only_policy": EXTERNAL_ONLY_POLICY,
        "internal_prediction_policy": INTERNAL_PREDICTION_POLICY,
        "submission_policy": SUBMISSION_POLICY,
        "next_action": "run required no-native probes before freezing model1 for the gated critical targets",
        "claim_boundary": CLAIM_BOUNDARY,
    }
    return {"summary": summary, "rows": rows}


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 MassiveFold Model1 Selection Calibration Gate",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- status: `{summary['massivefold_model1_selection_calibration_gate_status']}`",
        f"- freeze_gate_status: `{summary['freeze_gate_status']}`",
        f"- gates ready/blocked/total: `{summary['ready_gate_count']}/{summary['blocked_gate_count']}/{summary['gate_count']}`",
        f"- hold/watch/probe-required/freeze-ready: `{summary['hold_model1_freeze_count']}/{summary['watch_probe_count']}/{summary['probe_required_count']}/{summary['freeze_ready_count']}`",
        f"- RNA/protein-complex gates: `{summary['rna_hybrid_gate_count']}/{summary['protein_complex_gate_count']}`",
        f"- first gate: `{summary['first_gate_target_id'] or '-'}` `{summary['first_gate_group'] or '-'}` `{summary['top_risk_score'] or '-'}` `{summary['first_gate_decision'] or '-'}` `{summary['first_gate_probe_type'] or '-'}`",
        f"- selection_rule_id: `{summary['selection_rule_id']}`",
        f"- next action: {summary['next_action']}",
        "",
        "## Gates",
        "",
        "| rank | target | group | score | decision | blocker | probe | exit criterion | packet |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['gate_rank']}` | `{row['target_id']}` | `{row['target_group']}` | "
            f"`{row['risk_score']}` | `{row['model1_freeze_decision']}` | "
            f"`{row['model1_freeze_blocker']}` | `{row['probe_type']}` | "
            f"{row['probe_exit_criterion']} | `{row['calibration_gate_md']}` |"
        )
    lines.extend(["", "## Claim Boundary", "", CLAIM_BOUNDARY])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_outputs(args: argparse.Namespace, payload: dict[str, Any]) -> None:
    _write_gate_packets(args.out_dir, payload["rows"])
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"])
    _write_md(args.out_md, payload)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build CASP17 MassiveFold model1 selection calibration gate.")
    parser.add_argument("--score-ledger-json", default=DEFAULT_SCORE_LEDGER_JSON)
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
                "status": payload["summary"]["massivefold_model1_selection_calibration_gate_status"],
                "freeze_gate": payload["summary"]["freeze_gate_status"],
                "gates": payload["summary"]["gate_count"],
                "hold": payload["summary"]["hold_model1_freeze_count"],
                "first": payload["summary"]["first_gate_target_id"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

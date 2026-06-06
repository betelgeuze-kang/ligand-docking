#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]

DEFAULT_PROBE_WORKLIST_JSON = "casp17/casp17_massivefold_model1_probe_worklist_current.json"
DEFAULT_RNA_SELF_ASSESSMENT_JSON = "casp17/casp17_massivefold_rna_self_assessment_packet_current.json"
DEFAULT_PROTEIN_COMPLEX_SELF_ASSESSMENT_JSON = (
    "casp17/casp17_protein_complex_massivefold_self_assessment_packet_current.json"
)
DEFAULT_OUT_DIR = "casp17/massivefold_model1_probe_outcomes"
DEFAULT_OUT_JSON = "casp17/casp17_massivefold_model1_probe_outcome_current.json"
DEFAULT_OUT_CSV = "casp17/casp17_massivefold_model1_probe_outcome_current.csv"
DEFAULT_OUT_MD = "casp17/CASP17_MASSIVEFOLD_MODEL1_PROBE_OUTCOME.md"

CLAIM_BOUNDARY = (
    "CASP17 MassiveFold model1 probe outcome packet only. Outcomes are no-native model-selection "
    "consistency checks from external self-assessment features. They are not native accuracy, internal "
    "prediction proof, or CASP submission evidence."
)
EXTERNAL_ONLY_POLICY = "external_no_native_model1_probe_outcome_only"
INTERNAL_PREDICTION_POLICY = "do_not_mark_as_internal_prediction"
SUBMISSION_POLICY = "do_not_submit_without_rule_check_and_operator_approval"
SCORING_RULE_ID = "no_native_probe_rescore_v1"

ROW_COLUMNS = [
    "outcome_rank",
    "outcome_status",
    "workitem_rank",
    "target_group",
    "target_id",
    "probe_type",
    "probe_priority",
    "model1_filename",
    "model1_probe_score",
    "top_candidate_filename",
    "top_candidate_role",
    "top_candidate_probe_score",
    "probe_margin",
    "probe_result",
    "freeze_after_probe_recommendation",
    "confidence_gap",
    "top5_candidate_count",
    "scoring_rule_id",
    "source_probe_workitem_md",
    "outcome_md",
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


def _rows(payload: dict[str, Any], key: str = "rows") -> list[dict[str, Any]]:
    rows = payload.get(key)
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


def _candidate_index(*payloads: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    index: dict[str, list[dict[str, Any]]] = {}
    for payload in payloads:
        for row in _rows(payload, "candidate_rows"):
            target_id = _text(row.get("target_id")).upper()
            if target_id:
                index.setdefault(target_id, []).append(row)
    return index


def _probe_score(candidate: dict[str, Any], probe_type: str) -> float:
    confidence = _float(candidate.get("confidence_score"))
    geometry = _float(candidate.get("geometry_outlier_score"))
    low_conf = _float(candidate.get("low_conf_atom_fraction"))
    diversity = _float(candidate.get("diversity_to_model1_rmsd"))
    if probe_type == "top5_rerank_consistency_probe":
        return confidence - (0.25 * geometry) - (2.0 * low_conf) - (0.01 * diversity)
    return confidence - (0.25 * geometry)


def _recommendation(probe_result: str, source_decision: str) -> str:
    if probe_result == "probe_pass_model1_retained":
        if source_decision.startswith("hold_model1_freeze"):
            return "conditional_model1_freeze_ready_external_only"
        return "watch_model1_freeze_ready_after_probe"
    return "keep_model1_freeze_blocked_and_escalate_manual_review"


def _outcome_dir_name(row: dict[str, Any]) -> str:
    return f"{int(row['outcome_rank']):02d}_{row['target_group']}_{row['target_id'].lower()}"


def _build_rows(
    *,
    worklist_payload: dict[str, Any],
    candidate_rows_by_target: dict[str, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for source in _rows(worklist_payload):
        target_id = _text(source.get("target_id")).upper()
        probe_type = _text(source.get("probe_type"))
        candidates = candidate_rows_by_target.get(target_id, [])
        blockers = _text(source.get("blockers"))
        if not candidates:
            blockers = ",".join(filter(None, [blockers, "candidate_rows_missing"]))
        scored = [
            {
                "candidate": candidate,
                "score": _probe_score(candidate, probe_type),
            }
            for candidate in candidates
        ]
        scored.sort(key=lambda item: (-item["score"], _int(item["candidate"].get("input_rank"))))
        model1 = next(
            (item for item in scored if _text(item["candidate"].get("input_role")) == "model1"),
            None,
        )
        top = scored[0] if scored else None
        best_competitor = next(
            (item for item in scored if _text(item["candidate"].get("input_role")) != "model1"),
            None,
        )
        model1_score = model1["score"] if model1 else 0.0
        top_score = top["score"] if top else 0.0
        competitor_score = best_competitor["score"] if best_competitor else top_score
        probe_margin = model1_score - competitor_score
        probe_result = (
            "probe_pass_model1_retained"
            if model1 is not None and top is not None and _text(top["candidate"].get("input_role")) == "model1"
            else "probe_fail_model1_displaced"
        )
        rows.append(
            {
                "outcome_rank": 0,
                "outcome_status": "ready_external_no_native_probe_outcome" if not blockers else "blocked_probe_outcome",
                "workitem_rank": _int(source.get("workitem_rank")),
                "target_group": _text(source.get("target_group")),
                "target_id": target_id,
                "probe_type": probe_type,
                "probe_priority": _int(source.get("probe_priority")),
                "model1_filename": _text(source.get("model1_filename")),
                "model1_probe_score": _float_out(model1_score),
                "top_candidate_filename": _text(top["candidate"].get("filename")) if top else "",
                "top_candidate_role": _text(top["candidate"].get("input_role")) if top else "",
                "top_candidate_probe_score": _float_out(top_score),
                "probe_margin": _float_out(probe_margin),
                "probe_result": probe_result,
                "freeze_after_probe_recommendation": _recommendation(
                    probe_result,
                    _text(source.get("model1_freeze_decision")),
                ),
                "confidence_gap": "",
                "top5_candidate_count": len(candidates),
                "scoring_rule_id": SCORING_RULE_ID,
                "source_probe_workitem_md": _text(source.get("workitem_md")),
                "outcome_md": "",
                "blockers": blockers,
                "external_only_policy": EXTERNAL_ONLY_POLICY,
                "internal_prediction_policy": INTERNAL_PREDICTION_POLICY,
                "submission_policy": SUBMISSION_POLICY,
                "claim_boundary": CLAIM_BOUNDARY,
            }
        )
    return sorted(rows, key=lambda row: (row["probe_priority"], -_float(row["model1_probe_score"]), row["workitem_rank"]))


def _write_outcome_packets(out_dir: str | Path, rows: list[dict[str, Any]]) -> None:
    for row in rows:
        target_dir = _resolve(out_dir) / _outcome_dir_name(row)
        target_dir.mkdir(parents=True, exist_ok=True)
        row["outcome_md"] = _artifact(target_dir / "PROBE_OUTCOME.md")
        _write_csv(target_dir / "probe_outcome_row.csv", [row])
        lines = [
            f"# {row['target_id']} Model1 Probe Outcome",
            "",
            f"- outcome_rank: `{row['outcome_rank']}`",
            f"- workitem_rank: `{row['workitem_rank']}`",
            f"- status: `{row['outcome_status']}`",
            f"- probe_type: `{row['probe_type']}`",
            f"- model1_score/top_score/margin: `{row['model1_probe_score']}/{row['top_candidate_probe_score']}/{row['probe_margin']}`",
            f"- top_candidate: `{row['top_candidate_filename']}` `{row['top_candidate_role']}`",
            f"- probe_result: `{row['probe_result']}`",
            f"- freeze_after_probe_recommendation: `{row['freeze_after_probe_recommendation']}`",
            f"- scoring_rule_id: `{row['scoring_rule_id']}`",
            f"- source_probe_workitem_md: `{row['source_probe_workitem_md'] or '-'}`",
            "",
            "## Claim Boundary",
            "",
            CLAIM_BOUNDARY,
        ]
        (target_dir / "PROBE_OUTCOME.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    worklist_payload = _read_json(args.probe_worklist_json)
    worklist_summary = _summary(worklist_payload)
    rna_payload = _read_json(args.rna_self_assessment_json)
    protein_payload = _read_json(args.protein_complex_self_assessment_json)
    rows = _build_rows(
        worklist_payload=worklist_payload,
        candidate_rows_by_target=_candidate_index(rna_payload, protein_payload),
    )
    for rank, row in enumerate(rows, start=1):
        row["outcome_rank"] = rank
    ready_rows = [row for row in rows if not row["blockers"]]
    pass_rows = [row for row in rows if row["probe_result"] == "probe_pass_model1_retained"]
    fail_rows = [row for row in rows if row["probe_result"] == "probe_fail_model1_displaced"]
    freeze_ready_rows = [
        row
        for row in rows
        if row["freeze_after_probe_recommendation"]
        in {"conditional_model1_freeze_ready_external_only", "watch_model1_freeze_ready_after_probe"}
    ]
    first = rows[0] if rows else {}
    source_ready = _text(worklist_summary.get("massivefold_model1_probe_worklist_status")).endswith(
        "ready_external_only"
    )
    summary = {
        "packet_type": "casp17_massivefold_model1_probe_outcome",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "massivefold_model1_probe_outcome_status": (
            "massivefold_model1_probe_outcome_ready_external_only"
            if source_ready and rows and len(ready_rows) == len(rows)
            else "massivefold_model1_probe_outcome_partial"
        ),
        "probe_worklist_json": _artifact(args.probe_worklist_json),
        "outcome_count": len(rows),
        "ready_outcome_count": len(ready_rows),
        "blocked_outcome_count": len(rows) - len(ready_rows),
        "probe_pass_count": len(pass_rows),
        "probe_fail_count": len(fail_rows),
        "freeze_ready_recommendation_count": len(freeze_ready_rows),
        "top5_probe_outcome_count": sum(1 for row in rows if row["probe_type"] == "top5_rerank_consistency_probe"),
        "lightweight_probe_outcome_count": sum(1 for row in rows if row["probe_type"] == "lightweight_rescore_probe"),
        "rna_hybrid_outcome_count": sum(1 for row in rows if row["target_group"] == "rna_hybrid"),
        "protein_complex_outcome_count": sum(1 for row in rows if row["target_group"] == "protein_complex"),
        "first_outcome_target_id": _text(first.get("target_id")),
        "first_outcome_group": _text(first.get("target_group")),
        "first_outcome_result": _text(first.get("probe_result")),
        "first_outcome_margin": _text(first.get("probe_margin")),
        "first_freeze_recommendation": _text(first.get("freeze_after_probe_recommendation")),
        "scoring_rule_id": SCORING_RULE_ID,
        "external_only_policy": EXTERNAL_ONLY_POLICY,
        "internal_prediction_policy": INTERNAL_PREDICTION_POLICY,
        "submission_policy": SUBMISSION_POLICY,
        "next_action": "feed probe outcomes into the model1 freeze decision packet while preserving no-native boundaries",
        "claim_boundary": CLAIM_BOUNDARY,
    }
    return {"summary": summary, "rows": rows}


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 MassiveFold Model1 Probe Outcome",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- status: `{summary['massivefold_model1_probe_outcome_status']}`",
        f"- outcomes ready/blocked/total: `{summary['ready_outcome_count']}/{summary['blocked_outcome_count']}/{summary['outcome_count']}`",
        f"- pass/fail/freeze-ready: `{summary['probe_pass_count']}/{summary['probe_fail_count']}/{summary['freeze_ready_recommendation_count']}`",
        f"- probes top5/lightweight: `{summary['top5_probe_outcome_count']}/{summary['lightweight_probe_outcome_count']}`",
        f"- RNA/protein-complex: `{summary['rna_hybrid_outcome_count']}/{summary['protein_complex_outcome_count']}`",
        f"- first outcome: `{summary['first_outcome_target_id'] or '-'}` `{summary['first_outcome_group'] or '-'}` `{summary['first_outcome_result'] or '-'}` margin `{summary['first_outcome_margin'] or '-'}` recommendation `{summary['first_freeze_recommendation'] or '-'}`",
        f"- scoring_rule_id: `{summary['scoring_rule_id']}`",
        f"- next action: {summary['next_action']}",
        "",
        "## Outcomes",
        "",
        "| rank | target | group | probe | model1 score | top score | margin | result | freeze recommendation | packet |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['outcome_rank']}` | `{row['target_id']}` | `{row['target_group']}` | "
            f"`{row['probe_type']}` | `{row['model1_probe_score']}` | "
            f"`{row['top_candidate_probe_score']}` | `{row['probe_margin']}` | "
            f"`{row['probe_result']}` | `{row['freeze_after_probe_recommendation']}` | "
            f"`{row['outcome_md']}` |"
        )
    lines.extend(["", "## Claim Boundary", "", CLAIM_BOUNDARY])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_outputs(args: argparse.Namespace, payload: dict[str, Any]) -> None:
    _write_outcome_packets(args.out_dir, payload["rows"])
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"])
    _write_md(args.out_md, payload)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build CASP17 MassiveFold model1 probe outcome packet.")
    parser.add_argument("--probe-worklist-json", default=DEFAULT_PROBE_WORKLIST_JSON)
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
                "status": payload["summary"]["massivefold_model1_probe_outcome_status"],
                "outcomes": payload["summary"]["outcome_count"],
                "pass": payload["summary"]["probe_pass_count"],
                "fail": payload["summary"]["probe_fail_count"],
                "first": payload["summary"]["first_outcome_target_id"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

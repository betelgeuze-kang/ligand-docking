#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]

DEFAULT_FREEZE_DECISION_JSON = "casp17/casp17_massivefold_model1_freeze_decision_packet_current.json"
DEFAULT_RNA_SELF_ASSESSMENT_JSON = "casp17/casp17_massivefold_rna_self_assessment_packet_current.json"
DEFAULT_PROTEIN_COMPLEX_SELF_ASSESSMENT_JSON = (
    "casp17/casp17_protein_complex_massivefold_self_assessment_packet_current.json"
)
DEFAULT_OUT_DIR = "casp17/massivefold_model_selection_ledger"
DEFAULT_OUT_JSON = "casp17/casp17_massivefold_model_selection_ledger_current.json"
DEFAULT_OUT_CSV = "casp17/casp17_massivefold_model_selection_ledger_current.csv"
DEFAULT_OUT_MD = "casp17/CASP17_MASSIVEFOLD_MODEL_SELECTION_LEDGER.md"

CLAIM_BOUNDARY = (
    "CASP17 MassiveFold model-selection ledger only. It records external no-native model1/top5 "
    "selection state for accuracy-estimation workflow. It is not native accuracy, internal "
    "prediction proof, or CASP submission evidence."
)
EXTERNAL_ONLY_POLICY = "external_no_native_model_selection_ledger_only"
INTERNAL_PREDICTION_POLICY = "do_not_mark_as_internal_prediction"
SUBMISSION_POLICY = "do_not_submit_without_rule_check_and_operator_approval"
LEDGER_RULE_ID = "no_native_massivefold_model_selection_ledger_v1"

ROW_COLUMNS = [
    "ledger_rank",
    "ledger_status",
    "target_group",
    "target_id",
    "target_family",
    "ledger_decision",
    "freeze_decision",
    "freeze_decision_class",
    "model1_freeze_state",
    "selected_model_filename",
    "selected_model_role",
    "alternate_model_filename",
    "model1_filename",
    "model1_protocol",
    "model1_confidence_score",
    "runner_up_confidence_score",
    "confidence_gap",
    "top5_score_spread",
    "mean_diversity_to_model1_rmsd",
    "max_geometry_outlier_score",
    "max_low_conf_atom_fraction",
    "min_nearest_top5_rmsd",
    "probe_result",
    "probe_margin",
    "source_self_assessment_status",
    "source_self_assessment_md",
    "source_candidate_manifest_csv",
    "source_freeze_decision_md",
    "source_freeze_decision_json",
    "ledger_md",
    "required_followup",
    "ledger_rule_id",
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


def _self_assessment_rows(*payloads: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for payload in payloads:
        for row in _rows(payload):
            target_id = _text(row.get("target_id")).upper()
            if target_id:
                rows.append(row)
    return rows


def _freeze_index(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {_text(row.get("target_id")).upper(): row for row in _rows(payload) if _text(row.get("target_id"))}


def _group_for_self_row(row: dict[str, Any]) -> str:
    target_id = _text(row.get("target_id")).upper()
    if target_id.startswith("R") or target_id.startswith("M"):
        return "rna_hybrid"
    return "protein_complex"


def _ledger_decision(freeze_row: dict[str, Any] | None) -> tuple[str, str, str, str]:
    if not freeze_row:
        return (
            "external_model1_review_only_unfrozen",
            "review_only_unfrozen",
            "model1_unfrozen_external_review_only",
            "keep as external review-only model1 until a probe/freeze gate is required",
        )
    decision = _text(freeze_row.get("freeze_decision"))
    decision_class = _text(freeze_row.get("freeze_decision_class"))
    freeze_state = _text(freeze_row.get("model1_freeze_state"))
    if decision_class == "conditional_freeze_ready":
        return (
            "external_model1_selected_conditional",
            decision_class,
            freeze_state,
            "carry conditional freeze into external model-selection ledger; no submission without operator approval",
        )
    if decision_class == "watch_freeze_ready":
        return (
            "external_model1_selected_watch",
            decision_class,
            freeze_state,
            "carry watch freeze into external model-selection ledger and retain final review flag",
        )
    if decision == "freeze_blocked_manual_review":
        return (
            "external_model1_blocked_manual_review",
            decision_class or "manual_review_blocked",
            freeze_state or "freeze_blocked_external_only",
            "manual review alternate top candidate before any freeze or submission formatting",
        )
    return (
        "external_model1_review_only_unfrozen",
        decision_class or "review_only_unfrozen",
        freeze_state or "model1_unfrozen_external_review_only",
        "review decision text before promotion",
    )


def _rank_key(row: dict[str, Any]) -> tuple[int, str, str]:
    priority = {
        "external_model1_selected_conditional": 1,
        "external_model1_selected_watch": 2,
        "external_model1_blocked_manual_review": 3,
        "external_model1_review_only_unfrozen": 4,
    }.get(row["ledger_decision"], 9)
    return (priority, row["target_group"], row["target_id"])


def _ledger_dir_name(row: dict[str, Any]) -> str:
    return f"{int(row['ledger_rank']):02d}_{row['target_group']}_{row['target_id'].lower()}"


def _build_rows(
    *,
    freeze_payload: dict[str, Any],
    self_rows: list[dict[str, Any]],
    freeze_json: str,
) -> list[dict[str, Any]]:
    freeze_by_target = _freeze_index(freeze_payload)
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for source in self_rows:
        target_id = _text(source.get("target_id")).upper()
        seen.add(target_id)
        freeze_row = freeze_by_target.get(target_id)
        ledger_decision, decision_class, freeze_state, followup = _ledger_decision(freeze_row)
        freeze_ready = ledger_decision in {
            "external_model1_selected_conditional",
            "external_model1_selected_watch",
        }
        blocked = _text(source.get("blockers"))
        if freeze_row and _text(freeze_row.get("blockers")):
            blocked = ",".join(filter(None, [blocked, _text(freeze_row.get("blockers"))]))
        selected_model = (
            _text(freeze_row.get("final_model1_filename"))
            if freeze_ready and freeze_row
            else (_text(source.get("model1_filename")) if not freeze_row else "")
        )
        selected_role = "model1" if selected_model and freeze_ready else ("model1_review_only" if selected_model else "")
        rows.append(
            {
                "ledger_rank": 0,
                "ledger_status": "ready_external_no_native_model_selection_ledger" if not blocked else "blocked_model_selection_ledger",
                "target_group": _text(freeze_row.get("target_group")) if freeze_row else _group_for_self_row(source),
                "target_id": target_id,
                "target_family": _text(source.get("target_family")),
                "ledger_decision": ledger_decision,
                "freeze_decision": _text(freeze_row.get("freeze_decision")) if freeze_row else "not_probe_gated",
                "freeze_decision_class": decision_class,
                "model1_freeze_state": freeze_state,
                "selected_model_filename": selected_model,
                "selected_model_role": selected_role,
                "alternate_model_filename": _text(freeze_row.get("alternate_model1_filename")) if freeze_row else "",
                "model1_filename": _text(source.get("model1_filename")),
                "model1_protocol": _text(source.get("model1_protocol")),
                "model1_confidence_score": _text(source.get("model1_confidence_score")),
                "runner_up_confidence_score": _text(source.get("runner_up_confidence_score")),
                "confidence_gap": _text(source.get("confidence_gap")),
                "top5_score_spread": _text(source.get("top5_score_spread")),
                "mean_diversity_to_model1_rmsd": _text(source.get("mean_diversity_to_model1_rmsd")),
                "max_geometry_outlier_score": _text(source.get("max_geometry_outlier_score")),
                "max_low_conf_atom_fraction": _text(source.get("max_low_conf_atom_fraction")),
                "min_nearest_top5_rmsd": _text(source.get("min_nearest_top5_rmsd")),
                "probe_result": _text(freeze_row.get("probe_result")) if freeze_row else "",
                "probe_margin": _text(freeze_row.get("probe_margin")) if freeze_row else "",
                "source_self_assessment_status": _text(source.get("self_assessment_status")),
                "source_self_assessment_md": _text(source.get("target_self_assessment_md")),
                "source_candidate_manifest_csv": _text(source.get("target_candidate_manifest_csv")),
                "source_freeze_decision_md": _text(freeze_row.get("decision_md")) if freeze_row else "",
                "source_freeze_decision_json": _artifact(freeze_json) if freeze_row else "",
                "ledger_md": "",
                "required_followup": followup,
                "ledger_rule_id": LEDGER_RULE_ID,
                "blockers": blocked,
                "external_only_policy": EXTERNAL_ONLY_POLICY,
                "internal_prediction_policy": INTERNAL_PREDICTION_POLICY,
                "submission_policy": SUBMISSION_POLICY,
                "claim_boundary": CLAIM_BOUNDARY,
            }
        )
    for target_id, freeze_row in freeze_by_target.items():
        if target_id in seen:
            continue
        ledger_decision, decision_class, freeze_state, followup = _ledger_decision(freeze_row)
        rows.append(
            {
                "ledger_rank": 0,
                "ledger_status": "blocked_model_selection_ledger",
                "target_group": _text(freeze_row.get("target_group")),
                "target_id": target_id,
                "target_family": "",
                "ledger_decision": ledger_decision,
                "freeze_decision": _text(freeze_row.get("freeze_decision")),
                "freeze_decision_class": decision_class,
                "model1_freeze_state": freeze_state,
                "selected_model_filename": "",
                "selected_model_role": "",
                "alternate_model_filename": _text(freeze_row.get("alternate_model1_filename")),
                "model1_filename": _text(freeze_row.get("final_model1_filename")),
                "model1_protocol": "",
                "model1_confidence_score": "",
                "runner_up_confidence_score": "",
                "confidence_gap": "",
                "top5_score_spread": "",
                "mean_diversity_to_model1_rmsd": "",
                "max_geometry_outlier_score": "",
                "max_low_conf_atom_fraction": "",
                "min_nearest_top5_rmsd": "",
                "probe_result": _text(freeze_row.get("probe_result")),
                "probe_margin": _text(freeze_row.get("probe_margin")),
                "source_self_assessment_status": "",
                "source_self_assessment_md": "",
                "source_candidate_manifest_csv": "",
                "source_freeze_decision_md": _text(freeze_row.get("decision_md")),
                "source_freeze_decision_json": _artifact(freeze_json),
                "ledger_md": "",
                "required_followup": followup,
                "ledger_rule_id": LEDGER_RULE_ID,
                "blockers": "self_assessment_row_missing",
                "external_only_policy": EXTERNAL_ONLY_POLICY,
                "internal_prediction_policy": INTERNAL_PREDICTION_POLICY,
                "submission_policy": SUBMISSION_POLICY,
                "claim_boundary": CLAIM_BOUNDARY,
            }
        )
    return sorted(rows, key=_rank_key)


def _write_ledger_packets(out_dir: str | Path, rows: list[dict[str, Any]]) -> None:
    for row in rows:
        target_dir = _resolve(out_dir) / _ledger_dir_name(row)
        target_dir.mkdir(parents=True, exist_ok=True)
        row["ledger_md"] = _artifact(target_dir / "MODEL_SELECTION_LEDGER.md")
        _write_csv(target_dir / "model_selection_ledger_row.csv", [row])
        lines = [
            f"# {row['target_id']} MassiveFold Model-Selection Ledger",
            "",
            f"- ledger_rank: `{row['ledger_rank']}`",
            f"- status: `{row['ledger_status']}`",
            f"- ledger_decision: `{row['ledger_decision']}`",
            f"- freeze_decision: `{row['freeze_decision']}`",
            f"- model1_freeze_state: `{row['model1_freeze_state']}`",
            f"- selected_model_filename: `{row['selected_model_filename'] or '-'}`",
            f"- alternate_model_filename: `{row['alternate_model_filename'] or '-'}`",
            f"- confidence_gap: `{row['confidence_gap'] or '-'}`",
            f"- probe_result/margin: `{row['probe_result'] or '-'}` `{row['probe_margin'] or '-'}`",
            f"- required_followup: {row['required_followup']}",
            f"- source_self_assessment_md: `{row['source_self_assessment_md'] or '-'}`",
            f"- source_freeze_decision_md: `{row['source_freeze_decision_md'] or '-'}`",
            "",
            "## Claim Boundary",
            "",
            CLAIM_BOUNDARY,
        ]
        (target_dir / "MODEL_SELECTION_LEDGER.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    freeze_payload = _read_json(args.freeze_decision_json)
    freeze_summary = _summary(freeze_payload)
    rna_payload = _read_json(args.rna_self_assessment_json)
    protein_payload = _read_json(args.protein_complex_self_assessment_json)
    rna_summary = _summary(rna_payload)
    protein_summary = _summary(protein_payload)
    rows = _build_rows(
        freeze_payload=freeze_payload,
        self_rows=_self_assessment_rows(rna_payload, protein_payload),
        freeze_json=args.freeze_decision_json,
    )
    for rank, row in enumerate(rows, start=1):
        row["ledger_rank"] = rank
    ready_rows = [row for row in rows if not row["blockers"]]
    conditional_rows = [row for row in rows if row["ledger_decision"] == "external_model1_selected_conditional"]
    watch_rows = [row for row in rows if row["ledger_decision"] == "external_model1_selected_watch"]
    manual_rows = [row for row in rows if row["ledger_decision"] == "external_model1_blocked_manual_review"]
    review_rows = [row for row in rows if row["ledger_decision"] == "external_model1_review_only_unfrozen"]
    first = rows[0] if rows else {}
    source_ready = (
        _text(freeze_summary.get("massivefold_model1_freeze_decision_packet_status")).endswith(
            "ready_external_only"
        )
        and _text(rna_summary.get("massivefold_rna_self_assessment_status")).endswith("ready_external_only")
        and _text(protein_summary.get("protein_complex_massivefold_self_assessment_status")).endswith(
            "ready_external_only"
        )
    )
    summary = {
        "packet_type": "casp17_massivefold_model_selection_ledger",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "massivefold_model_selection_ledger_status": (
            "massivefold_model_selection_ledger_ready_external_only"
            if source_ready and rows and len(ready_rows) == len(rows)
            else "massivefold_model_selection_ledger_partial"
        ),
        "freeze_decision_json": _artifact(args.freeze_decision_json),
        "rna_self_assessment_json": _artifact(args.rna_self_assessment_json),
        "protein_complex_self_assessment_json": _artifact(args.protein_complex_self_assessment_json),
        "ledger_count": len(rows),
        "ready_ledger_count": len(ready_rows),
        "blocked_ledger_count": len(rows) - len(ready_rows),
        "conditional_selected_count": len(conditional_rows),
        "watch_selected_count": len(watch_rows),
        "manual_review_blocked_count": len(manual_rows),
        "review_only_unfrozen_count": len(review_rows),
        "freeze_ready_selected_count": len(conditional_rows) + len(watch_rows),
        "rna_hybrid_ledger_count": sum(1 for row in rows if row["target_group"] == "rna_hybrid"),
        "protein_complex_ledger_count": sum(1 for row in rows if row["target_group"] == "protein_complex"),
        "first_ledger_target_id": _text(first.get("target_id")),
        "first_ledger_group": _text(first.get("target_group")),
        "first_ledger_decision": _text(first.get("ledger_decision")),
        "first_manual_review_target_id": _text(manual_rows[0].get("target_id")) if manual_rows else "",
        "ledger_rule_id": LEDGER_RULE_ID,
        "external_only_policy": EXTERNAL_ONLY_POLICY,
        "internal_prediction_policy": INTERNAL_PREDICTION_POLICY,
        "submission_policy": SUBMISSION_POLICY,
        "next_action": "use this external-only ledger for accuracy-estimation review, then resume strict-blind source-gate closure",
        "claim_boundary": CLAIM_BOUNDARY,
    }
    return {"summary": summary, "rows": rows}


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 MassiveFold Model-Selection Ledger",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- status: `{summary['massivefold_model_selection_ledger_status']}`",
        f"- ledgers ready/blocked/total: `{summary['ready_ledger_count']}/{summary['blocked_ledger_count']}/{summary['ledger_count']}`",
        f"- selected conditional/watch: `{summary['conditional_selected_count']}/{summary['watch_selected_count']}`",
        f"- manual-review/review-only: `{summary['manual_review_blocked_count']}/{summary['review_only_unfrozen_count']}`",
        f"- freeze-ready selected: `{summary['freeze_ready_selected_count']}`",
        f"- RNA/protein-complex: `{summary['rna_hybrid_ledger_count']}/{summary['protein_complex_ledger_count']}`",
        f"- first ledger: `{summary['first_ledger_target_id'] or '-'}` `{summary['first_ledger_group'] or '-'}` `{summary['first_ledger_decision'] or '-'}`",
        f"- first manual review: `{summary['first_manual_review_target_id'] or '-'}`",
        f"- ledger_rule_id: `{summary['ledger_rule_id']}`",
        f"- next action: {summary['next_action']}",
        "",
        "## Ledger Rows",
        "",
        "| rank | target | group | decision | selected model | alternate | confidence gap | probe margin | packet |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['ledger_rank']}` | `{row['target_id']}` | `{row['target_group']}` | "
            f"`{row['ledger_decision']}` | `{row['selected_model_filename'] or '-'}` | "
            f"`{row['alternate_model_filename'] or '-'}` | `{row['confidence_gap'] or '-'}` | "
            f"`{row['probe_margin'] or '-'}` | `{row['ledger_md']}` |"
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
    parser = argparse.ArgumentParser(description="Build CASP17 MassiveFold model-selection ledger.")
    parser.add_argument("--freeze-decision-json", default=DEFAULT_FREEZE_DECISION_JSON)
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
                "status": payload["summary"]["massivefold_model_selection_ledger_status"],
                "ledgers": payload["summary"]["ledger_count"],
                "freeze_ready_selected": payload["summary"]["freeze_ready_selected_count"],
                "manual_review": payload["summary"]["manual_review_blocked_count"],
                "review_only": payload["summary"]["review_only_unfrozen_count"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

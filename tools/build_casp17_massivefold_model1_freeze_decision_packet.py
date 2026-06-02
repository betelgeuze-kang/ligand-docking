#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]

DEFAULT_PROBE_OUTCOME_JSON = "casp17/casp17_massivefold_model1_probe_outcome_current.json"
DEFAULT_OUT_DIR = "casp17/massivefold_model1_freeze_decisions"
DEFAULT_OUT_JSON = "casp17/casp17_massivefold_model1_freeze_decision_packet_current.json"
DEFAULT_OUT_CSV = "casp17/casp17_massivefold_model1_freeze_decision_packet_current.csv"
DEFAULT_OUT_MD = "casp17/CASP17_MASSIVEFOLD_MODEL1_FREEZE_DECISION_PACKET.md"

CLAIM_BOUNDARY = (
    "CASP17 MassiveFold model1 freeze decision packet only. Decisions are external no-native "
    "model-selection controls derived from probe outcomes. They are not native accuracy, internal "
    "prediction proof, or CASP submission evidence."
)
EXTERNAL_ONLY_POLICY = "external_no_native_model1_freeze_decision_only"
INTERNAL_PREDICTION_POLICY = "do_not_mark_as_internal_prediction"
SUBMISSION_POLICY = "do_not_submit_without_rule_check_and_operator_approval"
DECISION_RULE_ID = "no_native_model1_freeze_decision_v1"

ROW_COLUMNS = [
    "decision_rank",
    "decision_status",
    "outcome_rank",
    "target_group",
    "target_id",
    "probe_type",
    "probe_result",
    "probe_margin",
    "freeze_after_probe_recommendation",
    "freeze_decision",
    "freeze_decision_class",
    "model1_freeze_state",
    "final_model1_filename",
    "alternate_model1_filename",
    "alternate_model1_role",
    "top_candidate_filename",
    "top_candidate_role",
    "model1_probe_score",
    "top_candidate_probe_score",
    "decision_reason",
    "required_followup",
    "decision_rule_id",
    "source_probe_outcome_md",
    "source_probe_outcome_json",
    "decision_md",
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


def _decision_from_recommendation(row: dict[str, Any]) -> tuple[str, str, str, str, str]:
    recommendation = _text(row.get("freeze_after_probe_recommendation"))
    probe_result = _text(row.get("probe_result"))
    if recommendation == "conditional_model1_freeze_ready_external_only":
        return (
            "freeze_ready_external_only_conditional",
            "conditional_freeze_ready",
            "freeze_allowed_external_only_conditional",
            "probe retained model1 after critical no-native rescore",
            "preserve external-only boundary and do not submit without operator approval",
        )
    if recommendation == "watch_model1_freeze_ready_after_probe":
        return (
            "freeze_ready_external_only_watch",
            "watch_freeze_ready",
            "freeze_allowed_external_only_watch",
            "probe retained model1 but watch status remains for final review",
            "carry watch flag into model-selection ledger before any submission formatting",
        )
    if probe_result == "probe_pass_model1_retained":
        return (
            "freeze_ready_external_only_watch",
            "watch_freeze_ready",
            "freeze_allowed_external_only_watch",
            "probe retained model1 but recommendation was not a hard freeze",
            "review recommendation text and preserve no-native boundary",
        )
    return (
        "freeze_blocked_manual_review",
        "manual_review_blocked",
        "freeze_blocked_external_only",
        "probe displaced model1 or kept freeze blocked",
        "manual review alternate top candidate and keep model1 freeze blocked",
    )


def _decision_dir_name(row: dict[str, Any]) -> str:
    return f"{int(row['decision_rank']):02d}_{row['target_group']}_{row['target_id'].lower()}"


def _build_rows(payload: dict[str, Any], source_json: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for source in _rows(payload):
        decision, decision_class, freeze_state, reason, followup = _decision_from_recommendation(source)
        source_blockers = _text(source.get("blockers"))
        outcome_status = _text(source.get("outcome_status"))
        blockers = source_blockers
        if outcome_status.startswith("blocked") and "source_probe_outcome_blocked" not in blockers:
            blockers = ",".join(filter(None, [blockers, "source_probe_outcome_blocked"]))
        target_id = _text(source.get("target_id")).upper()
        model1_filename = _text(source.get("model1_filename"))
        top_candidate_filename = _text(source.get("top_candidate_filename"))
        top_candidate_role = _text(source.get("top_candidate_role"))
        freeze_ready = decision_class in {"conditional_freeze_ready", "watch_freeze_ready"}
        rows.append(
            {
                "decision_rank": 0,
                "decision_status": "ready_external_no_native_freeze_decision" if not blockers else "blocked_freeze_decision",
                "outcome_rank": _int(source.get("outcome_rank")),
                "target_group": _text(source.get("target_group")),
                "target_id": target_id,
                "probe_type": _text(source.get("probe_type")),
                "probe_result": _text(source.get("probe_result")),
                "probe_margin": _text(source.get("probe_margin")),
                "freeze_after_probe_recommendation": _text(source.get("freeze_after_probe_recommendation")),
                "freeze_decision": decision,
                "freeze_decision_class": decision_class,
                "model1_freeze_state": freeze_state,
                "final_model1_filename": model1_filename if freeze_ready else "",
                "alternate_model1_filename": top_candidate_filename if not freeze_ready else "",
                "alternate_model1_role": top_candidate_role if not freeze_ready else "",
                "top_candidate_filename": top_candidate_filename,
                "top_candidate_role": top_candidate_role,
                "model1_probe_score": _text(source.get("model1_probe_score")),
                "top_candidate_probe_score": _text(source.get("top_candidate_probe_score")),
                "decision_reason": reason,
                "required_followup": followup,
                "decision_rule_id": DECISION_RULE_ID,
                "source_probe_outcome_md": _text(source.get("outcome_md")),
                "source_probe_outcome_json": _artifact(source_json),
                "decision_md": "",
                "blockers": blockers,
                "external_only_policy": EXTERNAL_ONLY_POLICY,
                "internal_prediction_policy": INTERNAL_PREDICTION_POLICY,
                "submission_policy": SUBMISSION_POLICY,
                "claim_boundary": CLAIM_BOUNDARY,
            }
        )
    return sorted(rows, key=lambda row: (row["outcome_rank"], row["target_id"]))


def _write_decision_packets(out_dir: str | Path, rows: list[dict[str, Any]]) -> None:
    for row in rows:
        target_dir = _resolve(out_dir) / _decision_dir_name(row)
        target_dir.mkdir(parents=True, exist_ok=True)
        row["decision_md"] = _artifact(target_dir / "FREEZE_DECISION.md")
        _write_csv(target_dir / "freeze_decision_row.csv", [row])
        lines = [
            f"# {row['target_id']} Model1 Freeze Decision",
            "",
            f"- decision_rank: `{row['decision_rank']}`",
            f"- outcome_rank: `{row['outcome_rank']}`",
            f"- status: `{row['decision_status']}`",
            f"- probe: `{row['probe_type']}` `{row['probe_result']}` margin `{row['probe_margin']}`",
            f"- freeze_after_probe_recommendation: `{row['freeze_after_probe_recommendation']}`",
            f"- freeze_decision: `{row['freeze_decision']}`",
            f"- freeze_decision_class: `{row['freeze_decision_class']}`",
            f"- model1_freeze_state: `{row['model1_freeze_state']}`",
            f"- final_model1_filename: `{row['final_model1_filename'] or '-'}`",
            f"- alternate_model1_filename: `{row['alternate_model1_filename'] or '-'}` `{row['alternate_model1_role'] or '-'}`",
            f"- decision_rule_id: `{row['decision_rule_id']}`",
            f"- required_followup: {row['required_followup']}",
            f"- source_probe_outcome_md: `{row['source_probe_outcome_md'] or '-'}`",
            "",
            "## Claim Boundary",
            "",
            CLAIM_BOUNDARY,
        ]
        (target_dir / "FREEZE_DECISION.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    probe_payload = _read_json(args.probe_outcome_json)
    probe_summary = _summary(probe_payload)
    rows = _build_rows(probe_payload, args.probe_outcome_json)
    for rank, row in enumerate(rows, start=1):
        row["decision_rank"] = rank
    ready_rows = [row for row in rows if not row["blockers"]]
    conditional_rows = [row for row in rows if row["freeze_decision_class"] == "conditional_freeze_ready"]
    watch_rows = [row for row in rows if row["freeze_decision_class"] == "watch_freeze_ready"]
    manual_review_rows = [row for row in rows if row["freeze_decision_class"] == "manual_review_blocked"]
    freeze_ready_rows = conditional_rows + watch_rows
    first_ready = freeze_ready_rows[0] if freeze_ready_rows else {}
    first_blocked = manual_review_rows[0] if manual_review_rows else {}
    source_ready = _text(probe_summary.get("massivefold_model1_probe_outcome_status")).endswith(
        "ready_external_only"
    )
    summary = {
        "packet_type": "casp17_massivefold_model1_freeze_decision_packet",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "massivefold_model1_freeze_decision_packet_status": (
            "massivefold_model1_freeze_decision_packet_ready_external_only"
            if source_ready and rows and len(ready_rows) == len(rows)
            else "massivefold_model1_freeze_decision_packet_partial"
        ),
        "probe_outcome_json": _artifact(args.probe_outcome_json),
        "decision_count": len(rows),
        "ready_decision_count": len(ready_rows),
        "blocked_decision_count": len(rows) - len(ready_rows),
        "freeze_ready_total_count": len(freeze_ready_rows),
        "freeze_blocked_total_count": len(manual_review_rows),
        "conditional_freeze_ready_count": len(conditional_rows),
        "watch_freeze_ready_count": len(watch_rows),
        "manual_review_blocked_count": len(manual_review_rows),
        "rna_hybrid_decision_count": sum(1 for row in rows if row["target_group"] == "rna_hybrid"),
        "protein_complex_decision_count": sum(1 for row in rows if row["target_group"] == "protein_complex"),
        "first_freeze_ready_target_id": _text(first_ready.get("target_id")),
        "first_freeze_ready_group": _text(first_ready.get("target_group")),
        "first_freeze_ready_decision": _text(first_ready.get("freeze_decision")),
        "first_blocked_target_id": _text(first_blocked.get("target_id")),
        "first_blocked_group": _text(first_blocked.get("target_group")),
        "first_blocked_decision": _text(first_blocked.get("freeze_decision")),
        "decision_rule_id": DECISION_RULE_ID,
        "external_only_policy": EXTERNAL_ONLY_POLICY,
        "internal_prediction_policy": INTERNAL_PREDICTION_POLICY,
        "submission_policy": SUBMISSION_POLICY,
        "next_action": "feed freeze-ready decisions into the external-only model-selection ledger; keep manual-review targets blocked",
        "claim_boundary": CLAIM_BOUNDARY,
    }
    return {"summary": summary, "rows": rows}


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 MassiveFold Model1 Freeze Decision Packet",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- status: `{summary['massivefold_model1_freeze_decision_packet_status']}`",
        f"- decisions ready/blocked/total: `{summary['ready_decision_count']}/{summary['blocked_decision_count']}/{summary['decision_count']}`",
        f"- freeze ready/blocked: `{summary['freeze_ready_total_count']}/{summary['freeze_blocked_total_count']}`",
        f"- conditional/watch/manual-review: `{summary['conditional_freeze_ready_count']}/{summary['watch_freeze_ready_count']}/{summary['manual_review_blocked_count']}`",
        f"- RNA/protein-complex: `{summary['rna_hybrid_decision_count']}/{summary['protein_complex_decision_count']}`",
        f"- first freeze-ready: `{summary['first_freeze_ready_target_id'] or '-'}` `{summary['first_freeze_ready_group'] or '-'}` `{summary['first_freeze_ready_decision'] or '-'}`",
        f"- first blocked: `{summary['first_blocked_target_id'] or '-'}` `{summary['first_blocked_group'] or '-'}` `{summary['first_blocked_decision'] or '-'}`",
        f"- decision_rule_id: `{summary['decision_rule_id']}`",
        f"- next action: {summary['next_action']}",
        "",
        "## Decisions",
        "",
        "| rank | target | group | probe result | margin | freeze decision | final model1 | alternate | packet |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['decision_rank']}` | `{row['target_id']}` | `{row['target_group']}` | "
            f"`{row['probe_result']}` | `{row['probe_margin']}` | `{row['freeze_decision']}` | "
            f"`{row['final_model1_filename'] or '-'}` | `{row['alternate_model1_filename'] or '-'}` | "
            f"`{row['decision_md']}` |"
        )
    lines.extend(["", "## Claim Boundary", "", CLAIM_BOUNDARY])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_outputs(args: argparse.Namespace, payload: dict[str, Any]) -> None:
    _write_decision_packets(args.out_dir, payload["rows"])
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"])
    _write_md(args.out_md, payload)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build CASP17 MassiveFold model1 freeze decision packet.")
    parser.add_argument("--probe-outcome-json", default=DEFAULT_PROBE_OUTCOME_JSON)
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
                "status": payload["summary"]["massivefold_model1_freeze_decision_packet_status"],
                "decisions": payload["summary"]["decision_count"],
                "freeze_ready": payload["summary"]["freeze_ready_total_count"],
                "freeze_blocked": payload["summary"]["freeze_blocked_total_count"],
                "first_blocked": payload["summary"]["first_blocked_target_id"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

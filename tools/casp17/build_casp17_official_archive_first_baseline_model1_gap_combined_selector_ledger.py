#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]

DEFAULT_TRIAGE_JSON = "casp17/casp17_official_archive_first_baseline_model1_gap_triage_current.json"
DEFAULT_FEATURE_PROBE_JSON = "casp17/casp17_official_archive_first_baseline_model1_gap_feature_probe_current.json"
DEFAULT_CONSENSUS_PROBE_JSON = "casp17/casp17_official_archive_first_baseline_model1_gap_consensus_probe_current.json"
DEFAULT_OUT_DIR = "casp17/official_archive_first_baseline_model1_gap_combined_selector_ledger"
DEFAULT_OUT_JSON = "casp17/casp17_official_archive_first_baseline_model1_gap_combined_selector_ledger_current.json"
DEFAULT_OUT_CSV = "casp17/casp17_official_archive_first_baseline_model1_gap_combined_selector_ledger_current.csv"
DEFAULT_OUT_MD = "casp17/CASP17_OFFICIAL_ARCHIVE_FIRST_BASELINE_MODEL1_GAP_COMBINED_SELECTOR_LEDGER.md"

CLAIM_BOUNDARY = (
    "Local CASP17 official-archive first baseline model1 gap combined selector ledger only. It combines "
    "native-free geometry and top5 consensus probe outputs from baseline-only official archive models to "
    "calibrate model1-selection decisions. It is not an official CASP assessment, not strict-blind "
    "competitive proof, does not import official archive models as internal predictions, does not push "
    "remotes, and does not submit to CASP."
)
RULE_ID = "official_archive_first_baseline_model1_gap_combined_selector_ledger_v1"

ROW_COLUMNS = [
    "selector_rank",
    "target_id",
    "group_id",
    "triage_band",
    "best_minus_model1_gdt_ts_proxy",
    "model1_model_id",
    "best_top5_model_id",
    "geometry_signal",
    "geometry_risk_delta_model1_minus_best",
    "consensus_signal",
    "consensus_margin_model1_minus_best",
    "model1_consensus_rank",
    "best_top5_consensus_rank",
    "consensus_top_model_id",
    "selector_decision",
    "selected_model_id",
    "decision_reason",
    "native_proxy_label",
    "baseline_result",
    "selector_status",
    "blockers",
    "review_md",
    "claim_boundary",
    "rule_id",
]


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _artifact(path_like: str | Path) -> str:
    if not str(path_like).strip():
        return ""
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


def _read_json(path_like: str | Path) -> dict[str, Any]:
    path = _resolve(path_like)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _summary(payload: dict[str, Any]) -> dict[str, Any]:
    summary = payload.get("summary")
    return summary if isinstance(summary, dict) else {}


def _rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = payload.get("rows")
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_csv(path_like: str | Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _by_group(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {_text(row.get("group_id")): row for row in rows if _text(row.get("group_id"))}


def _decision(geometry_signal: str, consensus_signal: str) -> tuple[str, str]:
    if geometry_signal == "supports_best_top5" and consensus_signal == "supports_model1":
        return "hold_manual_review", "geometry_best_conflicts_with_consensus_model1"
    if geometry_signal == "supports_model1" and consensus_signal == "supports_best_top5":
        return "hold_manual_review", "geometry_model1_conflicts_with_consensus_best"
    if geometry_signal == "supports_best_top5":
        return "promote_best_top5", "geometry_supports_best_top5"
    if consensus_signal == "supports_best_top5":
        return "promote_best_top5", "consensus_supports_best_top5"
    if geometry_signal == "supports_model1":
        return "retain_model1", "geometry_supports_model1"
    if consensus_signal == "supports_model1":
        return "retain_model1", "consensus_supports_model1"
    return "hold_manual_review", "both_probes_ambiguous"


def _native_proxy_label(delta: float) -> str:
    if delta > 0.0:
        return "best_top5_wins_from_native_proxy"
    if delta < 0.0:
        return "model1_wins_from_native_proxy"
    return "model1_best_top5_tied_from_native_proxy"


def _baseline_result(decision: str, native_label: str) -> str:
    if native_label == "best_top5_wins_from_native_proxy":
        if decision == "promote_best_top5":
            return "corrected_model1_failure_baseline_proxy"
        if decision == "retain_model1":
            return "retained_model1_failure_baseline_proxy"
        return "manual_hold_on_model1_failure_baseline_proxy"
    if native_label == "model1_wins_from_native_proxy":
        if decision == "promote_best_top5":
            return "false_positive_demote_model1_baseline_proxy"
        if decision == "retain_model1":
            return "correctly_retained_model1_baseline_proxy"
        return "manual_hold_on_model1_win_baseline_proxy"
    return "manual_or_tie_baseline_proxy" if decision == "hold_manual_review" else "tie_case_selected_baseline_proxy"


def _write_review(path: Path, row: dict[str, Any]) -> None:
    lines = [
        f"# {row['target_id']} group {row['group_id']} combined selector",
        "",
        f"- decision: `{row['selector_decision']}` selected `{row['selected_model_id']}`",
        f"- reason: `{row['decision_reason']}`",
        f"- baseline result: `{row['baseline_result']}`",
        f"- geometry signal/delta: `{row['geometry_signal']}` `{row['geometry_risk_delta_model1_minus_best']}`",
        f"- consensus signal/margin: `{row['consensus_signal']}` `{row['consensus_margin_model1_minus_best']}`",
        f"- consensus ranks model1/best/top: `{row['model1_consensus_rank']}` `{row['best_top5_consensus_rank']}` `{row['consensus_top_model_id']}`",
        "",
        "## Claim Boundary",
        "",
        CLAIM_BOUNDARY,
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    triage_payload = _read_json(args.triage_json)
    feature_payload = _read_json(args.feature_probe_json)
    consensus_payload = _read_json(args.consensus_probe_json)
    triage_summary = _summary(triage_payload)
    feature_summary = _summary(feature_payload)
    consensus_summary = _summary(consensus_payload)
    feature_by_group = _by_group(_rows(feature_payload))
    consensus_by_group = _by_group(_rows(consensus_payload))
    out_dir = _resolve(args.out_dir)
    triage_rows = [
        row
        for row in _rows(triage_payload)
        if _text(row.get("triage_band")) in {"large_selection_gap", "catastrophic_model1_selection_gap"}
    ][: args.max_cases]

    rows: list[dict[str, Any]] = []
    for rank, triage in enumerate(triage_rows, start=1):
        group_id = _text(triage.get("group_id"))
        feature = feature_by_group.get(group_id, {})
        consensus = consensus_by_group.get(group_id, {})
        blockers: list[str] = []
        if not feature:
            blockers.append("feature_probe_row_missing")
        if not consensus:
            blockers.append("consensus_probe_row_missing")
        geometry_signal = _text(feature.get("geometry_signal")) or "missing"
        consensus_signal = _text(consensus.get("consensus_signal")) or "missing"
        decision, reason = _decision(geometry_signal, consensus_signal)
        model1_id = _text(triage.get("model1_model_id"))
        best_id = _text(triage.get("best_top5_model_id"))
        selected = best_id if decision == "promote_best_top5" else model1_id if decision == "retain_model1" else ""
        delta = _float(triage.get("best_minus_model1_gdt_ts_proxy"))
        native_label = _native_proxy_label(delta)
        case_dir = out_dir / f"{rank:02d}_{_text(triage.get('target_id')).lower()}_group_{group_id}"
        review_md = case_dir / "COMBINED_SELECTOR.md"
        row = {
            "selector_rank": rank,
            "target_id": _text(triage.get("target_id")),
            "group_id": group_id,
            "triage_band": _text(triage.get("triage_band")),
            "best_minus_model1_gdt_ts_proxy": _text(triage.get("best_minus_model1_gdt_ts_proxy")),
            "model1_model_id": model1_id,
            "best_top5_model_id": best_id,
            "geometry_signal": geometry_signal,
            "geometry_risk_delta_model1_minus_best": _text(feature.get("geometry_risk_delta_model1_minus_best")),
            "consensus_signal": consensus_signal,
            "consensus_margin_model1_minus_best": _text(consensus.get("consensus_margin_model1_minus_best")),
            "model1_consensus_rank": _text(consensus.get("model1_consensus_rank")),
            "best_top5_consensus_rank": _text(consensus.get("best_top5_consensus_rank")),
            "consensus_top_model_id": _text(consensus.get("consensus_top_model_id")),
            "selector_decision": decision,
            "selected_model_id": selected,
            "decision_reason": reason,
            "native_proxy_label": native_label,
            "baseline_result": _baseline_result(decision, native_label),
            "selector_status": "selector_ready" if not blockers else "selector_blocked",
            "blockers": ",".join(blockers),
            "review_md": _artifact(review_md),
            "claim_boundary": CLAIM_BOUNDARY,
            "rule_id": RULE_ID,
        }
        _write_review(review_md, row)
        rows.append(row)

    ready_rows = [row for row in rows if row["selector_status"] == "selector_ready"]
    promote_rows = [row for row in ready_rows if row["selector_decision"] == "promote_best_top5"]
    retain_rows = [row for row in ready_rows if row["selector_decision"] == "retain_model1"]
    hold_rows = [row for row in ready_rows if row["selector_decision"] == "hold_manual_review"]
    corrected_rows = [row for row in ready_rows if row["baseline_result"] == "corrected_model1_failure_baseline_proxy"]
    retained_failure_rows = [
        row for row in ready_rows if row["baseline_result"] == "retained_model1_failure_baseline_proxy"
    ]
    manual_failure_rows = [
        row for row in ready_rows if row["baseline_result"] == "manual_hold_on_model1_failure_baseline_proxy"
    ]
    false_positive_rows = [
        row for row in ready_rows if row["baseline_result"] == "false_positive_demote_model1_baseline_proxy"
    ]
    first = ready_rows[0] if ready_rows else (rows[0] if rows else {})
    status = (
        "official_archive_first_baseline_model1_gap_combined_selector_ledger_ready_baseline_only"
        if rows and len(ready_rows) == len(rows)
        else "official_archive_first_baseline_model1_gap_combined_selector_ledger_blocked"
    )
    selector_csv = out_dir / "combined_selector_ledger.csv"
    summary = {
        "packet_type": "casp17_official_archive_first_baseline_model1_gap_combined_selector_ledger",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "official_archive_first_baseline_model1_gap_combined_selector_ledger_status": status,
        "triage_json": _artifact(args.triage_json),
        "triage_status": _text(triage_summary.get("official_archive_first_baseline_model1_gap_triage_status")),
        "feature_probe_json": _artifact(args.feature_probe_json),
        "feature_probe_status": _text(
            feature_summary.get("official_archive_first_baseline_model1_gap_feature_probe_status")
        ),
        "consensus_probe_json": _artifact(args.consensus_probe_json),
        "consensus_probe_status": _text(
            consensus_summary.get("official_archive_first_baseline_model1_gap_consensus_probe_status")
        ),
        "first_baseline_candidate_id": _text(triage_summary.get("first_baseline_candidate_id")),
        "first_competition": _text(triage_summary.get("first_competition")),
        "first_target_id": _text(triage_summary.get("first_target_id")),
        "first_native_pdb_code": _text(triage_summary.get("first_native_pdb_code")),
        "selected_case_count": len(rows),
        "selector_ready_count": len(ready_rows),
        "selector_blocked_count": len(rows) - len(ready_rows),
        "promote_best_top5_count": len(promote_rows),
        "retain_model1_count": len(retain_rows),
        "hold_manual_review_count": len(hold_rows),
        "corrected_model1_failure_count": len(corrected_rows),
        "retained_model1_failure_count": len(retained_failure_rows),
        "manual_hold_model1_failure_count": len(manual_failure_rows),
        "false_positive_demote_count": len(false_positive_rows),
        "baseline_capture_rate": f"{len(corrected_rows) / len(ready_rows):.3f}" if ready_rows else "0.000",
        "baseline_non_capture_rate": (
            f"{(len(retained_failure_rows) + len(manual_failure_rows)) / len(ready_rows):.3f}"
            if ready_rows
            else "0.000"
        ),
        "catastrophic_case_count": sum(1 for row in rows if row["triage_band"] == "catastrophic_model1_selection_gap"),
        "large_case_count": sum(1 for row in rows if row["triage_band"] == "large_selection_gap"),
        "first_selector_group_id": _text(first.get("group_id")),
        "first_selector_decision": _text(first.get("selector_decision")),
        "first_selected_model_id": _text(first.get("selected_model_id")),
        "first_baseline_result": _text(first.get("baseline_result")),
        "combined_selector_csv": _artifact(selector_csv),
        "competitive_proof_eligible": False,
        "strict_blind_intake_policy": "do_not_import_as_internal_prediction",
        "next_action": (
            "apply this conservative combined selector design to external CASP17 MassiveFold model1 freeze ledgers, "
            "then repeat on strict-blind eligible internal predictions before competitive claims"
            if status == "official_archive_first_baseline_model1_gap_combined_selector_ledger_ready_baseline_only"
            else "repair missing feature or consensus probe rows before combined selector calibration"
        ),
        "claim_boundary": CLAIM_BOUNDARY,
        "rule_id": RULE_ID,
    }
    return {"summary": summary, "rows": rows}


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Official Archive First Baseline Model1 Gap Combined Selector Ledger",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- status: `{summary['official_archive_first_baseline_model1_gap_combined_selector_ledger_status']}`",
        f"- first baseline: `{summary['first_baseline_candidate_id']}` `{summary['first_competition']}` `{summary['first_target_id']}` native `{summary['first_native_pdb_code']}`",
        f"- selector ready/blocked/selected: `{summary['selector_ready_count']}/{summary['selector_blocked_count']}/{summary['selected_case_count']}`",
        f"- decisions promote/retain/hold: `{summary['promote_best_top5_count']}/{summary['retain_model1_count']}/{summary['hold_manual_review_count']}`",
        f"- baseline corrected/retained-failure/manual-hold/false-positive: `{summary['corrected_model1_failure_count']}/{summary['retained_model1_failure_count']}/{summary['manual_hold_model1_failure_count']}/{summary['false_positive_demote_count']}`",
        f"- baseline capture/non-capture: `{summary['baseline_capture_rate']}` `{summary['baseline_non_capture_rate']}`",
        f"- catastrophic/large cases: `{summary['catastrophic_case_count']}/{summary['large_case_count']}`",
        f"- first selector: group `{summary['first_selector_group_id'] or '-'}` decision `{summary['first_selector_decision'] or '-'}` selected `{summary['first_selected_model_id'] or '-'}` result `{summary['first_baseline_result'] or '-'}`",
        f"- combined selector csv: `{summary['combined_selector_csv']}`",
        f"- proof eligible: `{summary['competitive_proof_eligible']}` policy `{summary['strict_blind_intake_policy']}`",
        f"- next action: {summary['next_action']}",
        "",
        "## Selector Worklist",
        "",
        "| rank | group | band | delta | geometry | consensus | decision | selected | baseline result |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['selector_rank']}` | `{row['group_id']}` | `{row['triage_band']}` | "
            f"`{row['best_minus_model1_gdt_ts_proxy']}` | `{row['geometry_signal']}` | "
            f"`{row['consensus_signal']}` | `{row['selector_decision']}` | "
            f"`{row['selected_model_id'] or '-'}` | `{row['baseline_result']}` |"
        )
    lines.extend(["", "## Claim Boundary", "", CLAIM_BOUNDARY])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_outputs(args: argparse.Namespace, payload: dict[str, Any]) -> None:
    out_dir = _resolve(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"], ROW_COLUMNS)
    _write_md(args.out_md, payload)
    _write_json(out_dir / "combined_selector_ledger.json", payload)
    _write_csv(out_dir / "combined_selector_ledger.csv", payload["rows"], ROW_COLUMNS)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build combined native-free selector ledger for first official archive baseline model1 gap cases."
    )
    parser.add_argument("--triage-json", default=DEFAULT_TRIAGE_JSON)
    parser.add_argument("--feature-probe-json", default=DEFAULT_FEATURE_PROBE_JSON)
    parser.add_argument("--consensus-probe-json", default=DEFAULT_CONSENSUS_PROBE_JSON)
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    parser.add_argument("--max-cases", type=int, default=14)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    payload = build_payload(args)
    write_outputs(args, payload)
    print(
        json.dumps(
            {
                "status": payload["summary"][
                    "official_archive_first_baseline_model1_gap_combined_selector_ledger_status"
                ],
                "target": payload["summary"]["first_target_id"],
                "ready": payload["summary"]["selector_ready_count"],
                "selected": payload["summary"]["selected_case_count"],
                "corrected": payload["summary"]["corrected_model1_failure_count"],
                "capture_rate": payload["summary"]["baseline_capture_rate"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

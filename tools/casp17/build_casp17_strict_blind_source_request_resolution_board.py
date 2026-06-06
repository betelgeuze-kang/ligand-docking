#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]

DEFAULT_SOURCE_REQUEST_PACKET_JSON = "casp17/casp17_strict_blind_source_gate_source_request_packet_current.json"
DEFAULT_INTERNAL_LIKE_SOURCE_REVIEW_JSON = "casp17/casp17_strict_blind_internal_like_source_review_current.json"
DEFAULT_OUT_JSON = "casp17/casp17_strict_blind_source_request_resolution_board_current.json"
DEFAULT_OUT_CSV = "casp17/casp17_strict_blind_source_request_resolution_board_current.csv"
DEFAULT_OUT_MD = "casp17/CASP17_STRICT_BLIND_SOURCE_REQUEST_RESOLUTION_BOARD.md"

ROW_COLUMNS = [
    "resolution_id",
    "request_id",
    "candidate_target_id",
    "candidate_scope",
    "request_kind",
    "request_status",
    "resolution_status",
    "resolution_class",
    "ready_for_source_gate",
    "current_first_blocker",
    "internal_like_review_status",
    "internal_like_candidate_count",
    "internal_like_pre_native_count",
    "internal_like_post_native_count",
    "native_release_date",
    "current_prediction_pdb",
    "blockers",
    "next_action",
]

CLAIM_BOUNDARY = (
    "CASP17 strict-blind source request resolution board only. It propagates internal-like chronology review "
    "results into source-request resolution classes so post-native local artifacts are not accidentally treated "
    "as strict-blind evidence. It does not fill operator values, approve no-leak evidence, copy files, compute "
    "CASP metrics, push remotes, or submit to CASP."
)


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
        return int(float(_text(value)))
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


def _summary(payload: dict[str, Any]) -> dict[str, Any]:
    summary = payload.get("summary")
    return summary if isinstance(summary, dict) else {}


def _rows(payload: dict[str, Any], key: str = "rows") -> list[dict[str, Any]]:
    rows = payload.get(key)
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


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


def _internal_like_by_target(review_payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        _text(row.get("mapped_target_id")): row
        for row in _rows(review_payload, "target_rows")
        if _text(row.get("mapped_target_id"))
    }


def _classify_request(row: dict[str, Any], target_review: dict[str, Any] | None) -> dict[str, str]:
    scope = _text(row.get("candidate_scope"))
    request_kind = _text(row.get("request_kind"))
    first_blocker = _text(row.get("first_blocker"))
    blockers: list[str] = []
    if scope == "monomer":
        if target_review and _int(target_review.get("pre_native_count")) > 0:
            blockers.extend(["no_leak_evidence_required", "operator_clearance_required"])
            return {
                "resolution_status": "pre_native_candidate_requires_no_leak_review",
                "resolution_class": "operator_review_possible",
                "ready_for_source_gate": "false",
                "blockers": ",".join(blockers),
                "next_action": "attach no-leak evidence and operator clearance before source-gate promotion",
            }
        if target_review and _int(target_review.get("post_native_count")) > 0:
            blockers.extend(["all_internal_like_candidates_post_native", first_blocker or "prediction_not_before_native"])
            return {
                "resolution_status": "requires_new_pre_native_internal_source",
                "resolution_class": "source_replacement_required",
                "ready_for_source_gate": "false",
                "blockers": ",".join(blocker for blocker in blockers if blocker),
                "next_action": "replace this source request with a different internal prediction artifact created before native release",
            }
        blockers.append("internal_like_chronology_review_missing")
        return {
            "resolution_status": "requires_internal_like_chronology_review",
            "resolution_class": "source_review_required",
            "ready_for_source_gate": "false",
            "blockers": ",".join(blockers),
            "next_action": "run internal-like source chronology review or attach a separate pre-native source",
        }
    if request_kind == "candidate_replacement_required" or scope == "complex":
        blockers.append(first_blocker or "native_authority_or_replacement_required")
        return {
            "resolution_status": "requires_authoritative_native_or_replacement_candidate",
            "resolution_class": "candidate_replacement_required",
            "ready_for_source_gate": "false",
            "blockers": ",".join(blockers),
            "next_action": "move this row to a strict ligand/complex authority repair or replace it with an in-scope pre-native source",
        }
    blockers.append(first_blocker or "source_request_unresolved")
    return {
        "resolution_status": "source_request_unresolved",
        "resolution_class": "operator_review_required",
        "ready_for_source_gate": "false",
        "blockers": ",".join(blockers),
        "next_action": "inspect this source request before source-gate use",
    }


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    source_payload = _read_json(args.source_request_packet_json)
    review_payload = _read_json(args.internal_like_source_review_json)
    source_summary = _summary(source_payload)
    review_summary = _summary(review_payload)
    target_review = _internal_like_by_target(review_payload)
    rows: list[dict[str, Any]] = []
    for index, row in enumerate(_rows(source_payload), start=1):
        target_id = _text(row.get("candidate_target_id"))
        review = target_review.get(target_id)
        classification = _classify_request(row, review)
        rows.append(
            {
                "resolution_id": f"source_request_resolution_{index:03d}",
                "request_id": _text(row.get("request_id")),
                "candidate_target_id": target_id,
                "candidate_scope": _text(row.get("candidate_scope")),
                "request_kind": _text(row.get("request_kind")),
                "request_status": _text(row.get("request_status")),
                "resolution_status": classification["resolution_status"],
                "resolution_class": classification["resolution_class"],
                "ready_for_source_gate": classification["ready_for_source_gate"],
                "current_first_blocker": _text(row.get("first_blocker")),
                "internal_like_review_status": _text(review.get("target_review_status")) if review else "",
                "internal_like_candidate_count": _int(review.get("candidate_count")) if review else 0,
                "internal_like_pre_native_count": _int(review.get("pre_native_count")) if review else 0,
                "internal_like_post_native_count": _int(review.get("post_native_count")) if review else 0,
                "native_release_date": _text(row.get("native_release_date")),
                "current_prediction_pdb": _text(row.get("current_prediction_pdb")),
                "blockers": classification["blockers"],
                "next_action": classification["next_action"],
            }
        )
    ready_count = sum(1 for row in rows if row["ready_for_source_gate"] == "true")
    monomer_count = sum(1 for row in rows if row["candidate_scope"] == "monomer")
    complex_count = sum(1 for row in rows if row["candidate_scope"] == "complex")
    all_post_native = sum(1 for row in rows if row["resolution_status"] == "requires_new_pre_native_internal_source")
    replacement_required = sum(
        1 for row in rows if row["resolution_status"] == "requires_authoritative_native_or_replacement_candidate"
    )
    pre_native_review = sum(1 for row in rows if row["resolution_status"] == "pre_native_candidate_requires_no_leak_review")
    chronology_missing = sum(1 for row in rows if row["resolution_status"] == "requires_internal_like_chronology_review")
    if ready_count:
        status = "source_request_resolution_has_source_gate_ready_rows"
    elif all_post_native == monomer_count and replacement_required == complex_count and rows:
        status = "source_request_resolution_all_current_candidates_blocked"
    elif rows:
        status = "source_request_resolution_operator_review_required"
    else:
        status = "source_request_resolution_no_requests"
    first_blocked = next((row for row in rows if row["ready_for_source_gate"] != "true"), rows[0] if rows else {})
    summary = {
        "packet_type": "casp17_strict_blind_source_request_resolution_board",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "source_request_resolution_board_status": status,
        "source_request_packet_status": _text(source_summary.get("source_request_packet_status")),
        "internal_like_source_review_status": _text(review_summary.get("internal_like_source_review_status")),
        "request_count": len(rows),
        "ready_for_source_gate_count": ready_count,
        "blocked_request_count": len(rows) - ready_count,
        "monomer_request_count": monomer_count,
        "complex_request_count": complex_count,
        "all_post_native_monomer_request_count": all_post_native,
        "candidate_replacement_required_count": replacement_required,
        "pre_native_review_possible_count": pre_native_review,
        "chronology_review_missing_count": chronology_missing,
        "internal_like_candidate_count": _int(review_summary.get("internal_like_candidate_count")),
        "internal_like_post_native_candidate_count": _int(review_summary.get("post_native_blocked_count")),
        "internal_like_pre_native_candidate_count": _int(review_summary.get("pre_native_candidate_count")),
        "first_blocked_request_id": _text(first_blocked.get("request_id")),
        "first_blocked_target_id": _text(first_blocked.get("candidate_target_id")),
        "first_blocked_resolution_status": _text(first_blocked.get("resolution_status")),
        "first_blocker": _text(first_blocked.get("blockers")).split(",")[0] if _text(first_blocked.get("blockers")) else "",
        "next_action": (
            "replace the 10 monomer requests with pre-native internal prediction artifacts and repair or replace "
            "the 7 complex native-authority rows before source-gate fulfillment"
            if rows and ready_count == 0
            else "review source-gate-ready rows only after no-leak evidence is attached"
        ),
        "claim_boundary": CLAIM_BOUNDARY,
    }
    return {"summary": summary, "rows": rows}


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Strict-Blind Source Request Resolution Board",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- status: `{summary['source_request_resolution_board_status']}`",
        f"- requests ready/blocked/total: `{summary['ready_for_source_gate_count']}/{summary['blocked_request_count']}/{summary['request_count']}`",
        f"- monomer/complex: `{summary['monomer_request_count']}/{summary['complex_request_count']}`",
        f"- all-post-native monomer/replacement/pre-native-review/missing-review: `{summary['all_post_native_monomer_request_count']}/{summary['candidate_replacement_required_count']}/{summary['pre_native_review_possible_count']}/{summary['chronology_review_missing_count']}`",
        f"- internal-like candidates post/pre: `{summary['internal_like_post_native_candidate_count']}/{summary['internal_like_pre_native_candidate_count']}`",
        f"- first blocker: `{summary['first_blocked_request_id'] or '-'}` `{summary['first_blocked_target_id'] or '-'}` `{summary['first_blocker'] or '-'}`",
        "",
        "## Resolution Rows",
        "",
        "| request | target | scope | resolution | internal-like | blockers | next action |",
        "| --- | --- | --- | --- | ---: | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['request_id']}` | `{row['candidate_target_id']}` | `{row['candidate_scope']}` | "
            f"`{row['resolution_status']}` | {row['internal_like_post_native_count']}/{row['internal_like_pre_native_count']} | "
            f"`{row['blockers'] or '-'}` | {row['next_action']} |"
        )
    lines.extend(["", "## Claim Boundary", "", summary["claim_boundary"], ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def write_outputs(args: argparse.Namespace, payload: dict[str, Any]) -> None:
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"])
    _write_md(args.out_md, payload)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Resolve strict-blind source requests after internal-like review.")
    parser.add_argument("--source-request-packet-json", default=DEFAULT_SOURCE_REQUEST_PACKET_JSON)
    parser.add_argument("--internal-like-source-review-json", default=DEFAULT_INTERNAL_LIKE_SOURCE_REVIEW_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_payload(args)
    write_outputs(args, payload)


if __name__ == "__main__":
    main()

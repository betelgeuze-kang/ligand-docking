#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]

DEFAULT_NEXT_SLICE_JSON = "runs/pxr_next_verification_slice_current.json"
DEFAULT_COMMIT_PACKET_JSON = "runs/pxr_pending_resolution_commit_packet_current.json"
DEFAULT_POLICY_NOTE_JSON = "runs/pxr_pending_policy_note_current.json"
DEFAULT_AUTO_OVERLAY_JSON = "runs/pxr_public_evidence_overlay_current.json"
DEFAULT_OUT_JSON = "runs/pxr_unresolved_evidence_capture_sheet_current.json"
DEFAULT_OUT_CSV = "runs/pxr_unresolved_evidence_capture_sheet_current.csv"
DEFAULT_OUT_MD = "runs/pxr_unresolved_evidence_capture_sheet_current.md"


def _resolve(path_like: str) -> Path:
    path = Path(path_like)
    if path.is_absolute():
        return path
    cwd_path = (Path.cwd() / path).resolve()
    if cwd_path.exists():
        return cwd_path
    return (ROOT / path).resolve()


def _load_json(path_like: str) -> dict[str, Any]:
    with _resolve(path_like).open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as fh:
        return [dict(row) for row in csv.DictReader(fh)]


def _existing_by_step(path: Path) -> dict[str, dict[str, str]]:
    if not path.exists():
        return {}
    return {
        str(row.get("packet_step", "")).strip(): row
        for row in _read_csv(path)
        if str(row.get("packet_step", "")).strip()
    }


def _overlay_by_step(payload: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    payload = payload or {}
    return {
        str(row.get("packet_step", "")).strip(): dict(row)
        for row in payload.get("rows", []) or []
        if str(row.get("packet_step", "")).strip()
    }


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _evidence_need_class(row: dict[str, Any]) -> str:
    binder = int(row.get("binder", 0) or 0)
    resolution_bias = str(row.get("resolution_bias", "")).strip()
    if binder == 1:
        return "target_specific_human_pxr_binder_evidence"
    if resolution_bias == "review_only":
        return "target_specific_human_pxr_negative_like_conflict_resolution"
    return "target_specific_human_pxr_negative_or_conflict_resolution"


def build_payload(
    next_slice_payload: dict[str, Any],
    commit_packet_payload: dict[str, Any],
    policy_note_payload: dict[str, Any],
    existing_sheet: dict[str, dict[str, str]] | None = None,
    overlay_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    existing_sheet = existing_sheet or {}
    overlay_rows = _overlay_by_step(overlay_payload)
    next_rows = {
        str(row.get("packet_step", "")).strip(): dict(row)
        for row in next_slice_payload.get("rows", []) or []
        if str(row.get("packet_step", "")).strip()
    }
    review_only_rows = set(policy_note_payload.get("summary", {}).get("review_only_rows", []) or [])
    defer_rows = set(policy_note_payload.get("summary", {}).get("defer_rows", []) or [])
    rows: list[dict[str, Any]] = []
    for rank, row in enumerate(commit_packet_payload.get("rows", []) or [], start=1):
        packet_step = str(row.get("packet_step", "")).strip()
        ligand = str(row.get("ligand", "")).strip()
        next_row = next_rows.get(packet_step, {})
        existing = existing_sheet.get(packet_step, {})
        overlay = overlay_rows.get(packet_step, {})
        existing_capture_status = str(existing.get("capture_status", "")).strip()
        overlay_supports = str(overlay.get("supports_local_target_specific_human_pxr", "")).strip().lower() in {"yes", "true", "1"}
        existing_manual_blocker = str(existing.get("manual_promotion_blocker", "")).strip()
        use_overlay = bool(overlay) and (
            existing_capture_status in {"", "pending_capture"}
            or (existing_capture_status == "captured_gap" and overlay_supports)
            or (
                existing_capture_status == "captured_conflict"
                and str(overlay.get("capture_status", "")).strip() == "captured_conflict"
                and overlay_supports
            )
            or (
                existing_capture_status == "captured_supportive"
                and overlay_supports
                and existing_manual_blocker == "quantitative_binding_value_or_activity_proxy_missing"
            )
        )
        effective_capture_status = (
            str(overlay.get("capture_status", "")).strip()
            if use_overlay and str(overlay.get("capture_status", "")).strip()
            else existing_capture_status
            if existing_capture_status not in {"", "pending_capture"}
            else str(overlay.get("capture_status", "")).strip() or "pending_capture"
        )
        current_commit_class = str(row.get("commit_class", "")).strip()
        current_resolution_bias = str(row.get("resolution_bias", "")).strip()
        rows.append(
            {
                "priority_rank": int(row.get("priority_rank", rank) or rank),
                "packet_step": packet_step,
                "replacement_ligand_id": ligand,
                "replacement_is_binder": int(row.get("binder", 0) or 0),
                "current_commit_class": current_commit_class,
                "current_resolution_bias": current_resolution_bias,
                "review_reason": str(
                    (overlay.get("source_note") if use_overlay else "")
                    or existing.get("source_note")
                    or existing.get("review_reason")
                    or next_row.get("review_reason")
                    or row.get("commit_note", "")
                ).strip(),
                "assay_type_honesty": str(
                    (overlay.get("manual_assay_type_honesty") if use_overlay else "")
                    or existing.get("manual_assay_type_honesty")
                    or existing.get("assay_type_honesty")
                    or row.get("manual_assay_type_honesty")
                    or row.get("staged_assay_type_honesty")
                    or next_row.get("assay_type_honesty", "")
                ).strip(),
                "evidence_need_class": _evidence_need_class(row),
                "supports_local_target_specific_human_pxr": str(
                    (overlay.get("supports_local_target_specific_human_pxr") if use_overlay else "")
                    or existing.get("supports_local_target_specific_human_pxr")
                    or overlay.get("supports_local_target_specific_human_pxr")
                    or ""
                ).strip(),
                "source_title": str((overlay.get("source_title") if use_overlay else "") or existing.get("source_title") or overlay.get("source_title") or "").strip(),
                "source_url": str((overlay.get("source_url") if use_overlay else "") or existing.get("source_url") or overlay.get("source_url") or "").strip(),
                "source_note": str((overlay.get("source_note") if use_overlay else "") or existing.get("source_note") or overlay.get("source_note") or "").strip(),
                "capture_status": effective_capture_status,
                "next_required_action": str(
                    (overlay.get("manual_next_required_action") if use_overlay else "")
                    or existing.get("next_required_action")
                    or overlay.get("manual_next_required_action")
                    or row.get("manual_next_required_action")
                    or row.get("staged_next_required_action")
                    or next_row.get("next_required_action", "")
                ).strip(),
                "manual_commit_class": str(
                    (overlay.get("manual_commit_class") if use_overlay else "")
                    or existing.get("manual_commit_class")
                    or overlay.get("manual_commit_class")
                    or row.get("manual_commit_class")
                    or current_commit_class
                ).strip(),
                "manual_resolution_bias": str(
                    (overlay.get("manual_resolution_bias") if use_overlay else "")
                    or existing.get("manual_resolution_bias")
                    or overlay.get("manual_resolution_bias")
                    or row.get("manual_resolution_bias")
                    or current_resolution_bias
                ).strip(),
                "manual_assay_type_honesty": str(
                    (overlay.get("manual_assay_type_honesty") if use_overlay else "")
                    or existing.get("manual_assay_type_honesty")
                    or overlay.get("manual_assay_type_honesty")
                    or row.get("manual_assay_type_honesty")
                    or row.get("staged_assay_type_honesty")
                    or next_row.get("assay_type_honesty", "")
                ).strip(),
                "manual_promotion_blocker": str(
                    (overlay.get("manual_promotion_blocker") if use_overlay else "")
                    or existing.get("manual_promotion_blocker")
                    or overlay.get("manual_promotion_blocker")
                    or row.get("manual_promotion_blocker")
                    or row.get("staged_promotion_blocker")
                ).strip(),
                "manual_next_required_action": str(
                    (overlay.get("manual_next_required_action") if use_overlay else "")
                    or existing.get("manual_next_required_action")
                    or overlay.get("manual_next_required_action")
                    or row.get("manual_next_required_action")
                    or row.get("staged_next_required_action")
                    or next_row.get("next_required_action", "")
                ).strip(),
                "manual_commit_class_override": str(
                    (overlay.get("manual_commit_class_override") if use_overlay else "")
                    or existing.get("manual_commit_class_override")
                    or overlay.get("manual_commit_class_override")
                    or ""
                ).strip(),
                "manual_commit_note": str(
                    (overlay.get("manual_commit_note") if use_overlay else "")
                    or existing.get("manual_commit_note")
                    or overlay.get("manual_commit_note")
                    or row.get("manual_commit_note")
                    or row.get("staged_commit_note")
                    or row.get("commit_note")
                ).strip(),
                "commit_status": (
                    (
                        str(overlay.get("commit_status", "")).strip()
                        or (
                            "confirmed_review_only"
                            if current_commit_class == "confirm_now" or current_resolution_bias == "review_only"
                            else "confirmed_defer"
                        )
                    )
                    if use_overlay or existing_capture_status in {"", "pending_capture"}
                    else str(existing.get("commit_status", row.get("commit_status", "pending_manual_commit"))).strip()
                ),
                "policy_bucket": (
                    "review_only"
                    if str(
                        (overlay.get("manual_promotion_blocker") if use_overlay else "")
                        or existing.get("manual_promotion_blocker")
                        or overlay.get("manual_promotion_blocker")
                        or row.get("manual_promotion_blocker")
                        or row.get("staged_promotion_blocker")
                    ).strip()
                    in {
                        "inactive_only_human_pxr_qhts_review_only",
                        "activity_upper_bound_only_not_quantitative_nonbinder",
                        "manual_negative_evidence_review",
                    }
                    or ligand in review_only_rows
                    else "defer"
                    if ligand in defer_rows
                    else current_resolution_bias or "unspecified"
                ),
            }
        )

    rows.sort(key=lambda item: (int(item.get("priority_rank", 999) or 999), str(item.get("packet_step", ""))))
    source_linked_count = sum(1 for row in rows if str(row.get("source_url", "")).strip() or str(row.get("source_title", "")).strip())
    supportive_count = sum(
        1 for row in rows if str(row.get("supports_local_target_specific_human_pxr", "")).strip().lower() in {"yes", "true", "1"}
    )
    summary = {
        "family": "pxr",
        "row_count": len(rows),
        "review_only_candidate_count": sum(1 for row in rows if row["policy_bucket"] == "review_only"),
        "deferred_candidate_count": sum(1 for row in rows if row["policy_bucket"] == "defer"),
        "source_linked_count": source_linked_count,
        "supportive_target_specific_human_count": supportive_count,
        "pending_capture_count": sum(1 for row in rows if str(row.get("capture_status", "")).strip() == "pending_capture"),
        "policy_line": str(policy_note_payload.get("summary", {}).get("policy_line", "")).strip(),
        "next_required_step": (
            "Capture local target-specific human PXR evidence row by row. Keep current review-only rows locked to review-only documentation unless stronger human PXR evidence changes the picture, and keep the remaining rows deferred until blocker-reducing evidence is curated."
        ),
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# PXR Unresolved Evidence Capture Sheet",
        "",
        f"- family: `{summary['family']}`",
        f"- row_count: `{summary['row_count']}`",
        f"- review_only_candidate_count: `{summary['review_only_candidate_count']}`",
        f"- deferred_candidate_count: `{summary['deferred_candidate_count']}`",
        f"- source_linked_count: `{summary['source_linked_count']}`",
        f"- supportive_target_specific_human_count: `{summary['supportive_target_specific_human_count']}`",
        f"- pending_capture_count: `{summary['pending_capture_count']}`",
        "",
        "## Policy Line",
        "",
        f"- {summary['policy_line']}",
        "",
        "## Next Step",
        "",
        f"- {summary['next_required_step']}",
        "",
        "## Rows",
        "",
        "| priority_rank | packet_step | ligand | policy_bucket | capture_status | supportive | source_title | source_url |",
        "| ---: | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| {row['priority_rank']} | `{row['packet_step']}` | `{row['replacement_ligand_id']}` | "
            f"`{row['policy_bucket']}` | `{row['capture_status']}` | "
            f"`{row['supports_local_target_specific_human_pxr'] or '-'}` | "
            f"`{row['source_title'] or '-'}` | `{row['source_url'] or '-'}` |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a PXR unresolved-evidence capture sheet for deferred/review-only rows.")
    parser.add_argument("--next-slice-json", default=DEFAULT_NEXT_SLICE_JSON)
    parser.add_argument("--commit-packet-json", default=DEFAULT_COMMIT_PACKET_JSON)
    parser.add_argument("--policy-note-json", default=DEFAULT_POLICY_NOTE_JSON)
    parser.add_argument("--auto-overlay-json", default=DEFAULT_AUTO_OVERLAY_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    out_csv = _resolve(args.out_csv)
    payload = build_payload(
        _load_json(args.next_slice_json),
        _load_json(args.commit_packet_json),
        _load_json(args.policy_note_json),
        existing_sheet=_existing_by_step(out_csv),
        overlay_payload=_load_json(args.auto_overlay_json) if _resolve(args.auto_overlay_json).exists() else {},
    )
    out_json = _resolve(args.out_json)
    out_md = _resolve(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    _write_csv(out_csv, payload["rows"])
    _write_markdown(out_md, payload)


if __name__ == "__main__":
    main()

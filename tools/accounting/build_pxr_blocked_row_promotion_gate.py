#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_FILL_READINESS_JSON = "runs/pxr_packet_fill_readiness_current.json"
DEFAULT_REVIEW_PACKET_JSON = "runs/pxr_review_packet_current.json"
DEFAULT_PUBLIC_OVERLAY_JSON = "runs/pxr_public_evidence_overlay_current.json"
DEFAULT_CONFLICT_RESOLVER_JSON = "runs/pxr_conflict_resolver_packet_current.json"
DEFAULT_QUANTITATIVE_JSON = "runs/pxr_quantitative_provenance_packet_current.json"
DEFAULT_EXACT_CONFIRMATION_JSON = "runs/pxr_exact_source_confirmation_packet_current.json"
DEFAULT_PENDING_DISPOSITION_JSON = "runs/pxr_pending_row_disposition_current.json"
DEFAULT_OUT_JSON = "runs/pxr_blocked_row_promotion_gate_current.json"
DEFAULT_OUT_CSV = "runs/pxr_blocked_row_promotion_gate_current.csv"
DEFAULT_OUT_MD = "runs/pxr_blocked_row_promotion_gate_current.md"


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    if path.is_absolute():
        return path
    cwd_path = (Path.cwd() / path).resolve()
    if cwd_path.exists():
        return cwd_path
    return (ROOT / path).resolve()


def _load_json(path_like: str | Path) -> dict[str, Any]:
    path = _resolve(path_like)
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _rows_by_step(payload: dict[str, Any], key: str = "packet_step") -> dict[str, dict[str, Any]]:
    return {
        _text(row.get(key)): dict(row)
        for row in payload.get("rows", []) or []
        if isinstance(row, dict) and _text(row.get(key))
    }


def _missing_fields(row: dict[str, Any]) -> list[str]:
    return [field.strip() for field in _text(row.get("required_missing_fields")).split(",") if field.strip()]


def _row_blockers(
    *,
    missing: list[str],
    review_bucket: str,
    promotion_blocker: str,
    binder: str,
    quantitative_row: dict[str, Any],
    conflict_row: dict[str, Any],
) -> list[str]:
    blockers: list[str] = []
    blockers.extend(missing)
    if promotion_blocker:
        blockers.append(promotion_blocker)
    if review_bucket.startswith("review_only"):
        blockers.append("review_only_not_authoritative_apply")
    if review_bucket.startswith("defer"):
        blockers.append("deferred_until_blocker_reducing_human_pxr_evidence")
    if conflict_row:
        recommended = _text(conflict_row.get("recommended_resolution"))
        blockers.append(recommended or "unresolved_human_pxr_conflict")
    if binder == "1" and _text(quantitative_row.get("quantitative_value_found")).lower() != "yes":
        blockers.append("claim_safe_quantitative_value_missing")
    return list(dict.fromkeys(blockers))


def _evidence_signal(
    *,
    review_row: dict[str, Any],
    public_row: dict[str, Any],
    conflict_row: dict[str, Any],
    quantitative_row: dict[str, Any],
    exact_row: dict[str, Any],
    pending_row: dict[str, Any],
) -> str:
    for row, fields in [
        (conflict_row, ["conflict_lane", "recommended_resolution"]),
        (quantitative_row, ["provenance_scope", "quantitative_value_found"]),
        (exact_row, ["confirmation_scope", "manual_promotion_blocker"]),
        (public_row, ["overlay_status", "manual_promotion_blocker"]),
        (pending_row, ["disposition", "promotion_blocker"]),
        (review_row, ["review_bucket", "assay_type_honesty"]),
    ]:
        parts = [_text(row.get(field)) for field in fields if _text(row.get(field))]
        if parts:
            return "::".join(parts)
    return ""


def build_payload(
    fill_readiness: dict[str, Any],
    review_packet: dict[str, Any],
    public_overlay: dict[str, Any],
    conflict_resolver: dict[str, Any],
    quantitative_packet: dict[str, Any],
    exact_confirmation: dict[str, Any],
    pending_disposition: dict[str, Any],
) -> dict[str, Any]:
    fill_summary = fill_readiness.get("summary") if isinstance(fill_readiness.get("summary"), dict) else {}
    review_by_step = _rows_by_step(review_packet)
    public_by_step = _rows_by_step(public_overlay)
    conflict_by_step = _rows_by_step(conflict_resolver)
    quantitative_by_step = _rows_by_step(quantitative_packet)
    exact_by_step = _rows_by_step(exact_confirmation)
    pending_by_step = _rows_by_step(pending_disposition)

    rows: list[dict[str, Any]] = []
    for readiness in fill_readiness.get("readiness_rows", []) or []:
        if _text(readiness.get("ready_for_apply")).lower() == "yes":
            continue
        packet_step = _text(readiness.get("packet_step"))
        review_row = review_by_step.get(packet_step, {})
        public_row = public_by_step.get(packet_step, {})
        conflict_row = conflict_by_step.get(packet_step, {})
        quantitative_row = quantitative_by_step.get(packet_step, {})
        exact_row = exact_by_step.get(packet_step, {})
        pending_row = pending_by_step.get(packet_step, {})

        ligand = _text(review_row.get("ligand")) or _text(pending_row.get("replacement_ligand_id"))
        binder = _text(review_row.get("binder")) or _text(pending_row.get("replacement_is_binder"))
        review_bucket = _text(review_row.get("review_bucket")) or _text(pending_row.get("disposition"))
        promotion_blocker = _text(review_row.get("assay_type_honesty")) or _text(pending_row.get("promotion_blocker"))
        missing = _missing_fields(readiness)
        blockers = _row_blockers(
            missing=missing,
            review_bucket=review_bucket,
            promotion_blocker=promotion_blocker,
            binder=binder,
            quantitative_row=quantitative_row,
            conflict_row=conflict_row,
        )
        claim_safe_quantitative_ready = (
            binder == "1"
            and _text(quantitative_row.get("quantitative_value_found")).lower() == "yes"
            and not missing
            and not review_bucket.startswith("defer")
        )
        authoritative_apply_allowed = not blockers and (
            claim_safe_quantitative_ready or review_bucket == "authoritative_apply"
        )
        rows.append(
            {
                "packet": _text(readiness.get("packet")),
                "packet_step": packet_step,
                "ligand": ligand,
                "binder": binder,
                "review_bucket": review_bucket,
                "readiness_missing_fields": ",".join(missing),
                "promotion_blocker": promotion_blocker,
                "evidence_signal": _evidence_signal(
                    review_row=review_row,
                    public_row=public_row,
                    conflict_row=conflict_row,
                    quantitative_row=quantitative_row,
                    exact_row=exact_row,
                    pending_row=pending_row,
                ),
                "claim_safe_quantitative_ready": claim_safe_quantitative_ready,
                "authoritative_apply_allowed": authoritative_apply_allowed,
                "fail_closed_blockers": ",".join(blockers),
                "next_action": (
                    "exact human NR1I2/PXR quantitative evidence required before promotion"
                    if binder == "1"
                    else "keep review-only/deferred unless blocker-reducing human PXR evidence appears"
                ),
            }
        )

    review_only_rows = [row for row in rows if str(row["review_bucket"]).startswith("review_only")]
    defer_rows = [row for row in rows if str(row["review_bucket"]).startswith("defer")]
    conflict_rows = [row for row in rows if "conflict" in str(row["fail_closed_blockers"])]
    quantitative_ready_rows = [row for row in rows if row["claim_safe_quantitative_ready"]]
    allowed_rows = [row for row in rows if row["authoritative_apply_allowed"]]
    all_fill_rows_ready = (
        _text(fill_summary.get("blocked_row_count")) in {"0", "0.0"}
        and int(fill_summary.get("ready_for_apply_row_count") or 0) > 0
    )
    fill_ready_count = int(fill_summary.get("ready_for_apply_row_count") or 0)
    claim_safe_count = fill_ready_count if all_fill_rows_ready else len(quantitative_ready_rows)
    authoritative_allowed_count = fill_ready_count if all_fill_rows_ready else len(allowed_rows)
    promotion_ready = all_fill_rows_ready or bool(allowed_rows)
    summary = {
        "packet_type": "pxr_blocked_row_promotion_gate",
        "blocked_row_count": len(rows),
        "review_only_row_count": len(review_only_rows),
        "defer_row_count": len(defer_rows),
        "conflict_or_deferred_row_count": len(conflict_rows) + len(defer_rows),
        "claim_safe_quantitative_ready_count": claim_safe_count,
        "authoritative_apply_allowed_count": authoritative_allowed_count,
        "promotion_ready": promotion_ready,
        "primary_blocker": "none" if promotion_ready else "replacement_reference_binding_kcal_mol",
        "primary_blocker_signal": (
            f"blocked_rows={len(rows)};"
            f"review_only={len(review_only_rows)};"
            f"defer={len(defer_rows)};"
            f"claim_safe_quantitative={claim_safe_count};"
            f"authoritative_allowed={authoritative_allowed_count}"
        ),
        "next_required_step": (
            "PXR rows are promotion-ready; rerun packet-fill, reconciliation, exact-review, and scope breadth gates."
            if promotion_ready
            else "Do not promote blocked PXR rows. Resolve them with exact human NR1I2/PXR quantitative evidence or keep review-only/deferred."
        ),
    }
    return {"summary": summary, "rows": rows}


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    s = payload["summary"]
    lines = [
        "# PXR Blocked Row Promotion Gate",
        "",
        f"- blocked_row_count: `{s['blocked_row_count']}`",
        f"- review_only_row_count: `{s['review_only_row_count']}`",
        f"- defer_row_count: `{s['defer_row_count']}`",
        f"- claim_safe_quantitative_ready_count: `{s['claim_safe_quantitative_ready_count']}`",
        f"- authoritative_apply_allowed_count: `{s['authoritative_apply_allowed_count']}`",
        f"- promotion_ready: `{s['promotion_ready']}`",
        f"- primary_blocker: `{s['primary_blocker']}`",
        f"- primary_blocker_signal: `{s['primary_blocker_signal']}`",
        "",
        "## Next Step",
        "",
        f"- {s['next_required_step']}",
        "",
        "## Rows",
        "",
        "| step | ligand | bucket | missing | signal | allowed | blockers |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['packet_step']}` | `{row['ligand']}` | `{row['review_bucket']}` | "
            f"`{row['readiness_missing_fields'] or '-'}` | `{row['evidence_signal'] or '-'}` | "
            f"`{row['authoritative_apply_allowed']}` | `{row['fail_closed_blockers'] or '-'}` |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a fail-closed PXR blocked-row promotion gate.")
    parser.add_argument("--fill-readiness-json", default=DEFAULT_FILL_READINESS_JSON)
    parser.add_argument("--review-packet-json", default=DEFAULT_REVIEW_PACKET_JSON)
    parser.add_argument("--public-overlay-json", default=DEFAULT_PUBLIC_OVERLAY_JSON)
    parser.add_argument("--conflict-resolver-json", default=DEFAULT_CONFLICT_RESOLVER_JSON)
    parser.add_argument("--quantitative-json", default=DEFAULT_QUANTITATIVE_JSON)
    parser.add_argument("--exact-confirmation-json", default=DEFAULT_EXACT_CONFIRMATION_JSON)
    parser.add_argument("--pending-disposition-json", default=DEFAULT_PENDING_DISPOSITION_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_payload(
        _load_json(args.fill_readiness_json),
        _load_json(args.review_packet_json),
        _load_json(args.public_overlay_json),
        _load_json(args.conflict_resolver_json),
        _load_json(args.quantitative_json),
        _load_json(args.exact_confirmation_json),
        _load_json(args.pending_disposition_json),
    )
    _write_json(args.out_json, payload)
    write_csv_rows(_resolve(args.out_csv), payload["rows"])
    _write_md(args.out_md, payload)


if __name__ == "__main__":
    main()

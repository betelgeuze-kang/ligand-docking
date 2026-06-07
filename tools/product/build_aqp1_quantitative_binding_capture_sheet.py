#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]

DEFAULT_EXTERNAL_SEED_JSON = "runs/aqp1_external_evidence_seed_current.json"
DEFAULT_WORKBOOK_JSON = "runs/aqp1_packet_replacement_workbook_current.json"
DEFAULT_OUT_JSON = "runs/aqp1_quantitative_binding_capture_sheet_current.json"
DEFAULT_OUT_CSV = "runs/aqp1_quantitative_binding_capture_sheet_current.csv"
DEFAULT_OUT_MD = "runs/aqp1_quantitative_binding_capture_sheet_current.md"


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


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _extract_signal_value(signal: str) -> tuple[str, str, str]:
    text = str(signal or "").strip()
    if not text:
        return "", "", ""
    match = re.search(r"\b(IC50|EC50|Ki|Kd)\s+([0-9]+(?:\.[0-9]+)?)\s*([numkMμ]+M)\b", text, flags=re.IGNORECASE)
    if match:
        kind = str(match.group(1)).upper()
        value = str(match.group(2))
        units = str(match.group(3)).replace("μ", "u")
        return kind, value, units
    match = re.search(r"\b([0-9]+(?:\.[0-9]+)?)\s*([numkMμ]+M)\b", text, flags=re.IGNORECASE)
    if match:
        return "functional_single_concentration_effect", str(match.group(1)), str(match.group(2)).replace("μ", "u")
    return "", "", ""


def _default_note(row: dict[str, Any]) -> str:
    candidate = str(row.get("candidate_name", "")).strip()
    signal = str(row.get("potency_or_signal", "")).strip()
    return (
        f"{candidate} currently has only functional/modulation evidence (`{signal}`), so "
        "replacement_reference_binding_kcal_mol must remain blank until direct quantitative binding is curated."
    )


def build_payload(
    external_seed_payload: dict[str, Any],
    workbook_payload: dict[str, Any],
    existing_sheet: dict[str, dict[str, str]] | None = None,
) -> dict[str, Any]:
    existing_sheet = existing_sheet or {}
    workbook_by_step = {
        str(row.get("packet_step", "")).strip(): dict(row)
        for row in workbook_payload.get("workbook_rows", []) or []
        if str(row.get("packet_step", "")).strip()
    }
    rows: list[dict[str, Any]] = []
    for row in external_seed_payload.get("rows", []) or []:
        packet_step = str(row.get("proposed_packet_step", "")).strip()
        if not packet_step.startswith("core_binder_"):
            continue
        workbook_row = workbook_by_step.get(packet_step, {})
        existing = existing_sheet.get(packet_step, {})
        quantitative_kind, quantitative_value, quantitative_units = _extract_signal_value(row.get("potency_or_signal", ""))
        support_default = "no"
        capture_default = "captured_review_only_gap"
        next_step_default = "keep_quantitative_binding_blank_until_direct_binding_is_curated"
        rows.append(
            {
                "priority_rank": int(row.get("priority_rank", 0) or 0),
                "packet_step": packet_step,
                "candidate_name": str(row.get("candidate_name", "")).strip(),
                "replacement_ligand_id": str(
                    existing.get("replacement_ligand_id")
                    or workbook_row.get("replacement_ligand_id")
                    or row.get("candidate_name", "")
                ).strip(),
                "current_replacement_reference_binding_kcal_mol": str(
                    workbook_row.get("replacement_reference_binding_kcal_mol", "")
                ).strip(),
                "current_replacement_source": str(workbook_row.get("replacement_source", "")).strip(),
                "evidence_class": str(row.get("evidence_class", "")).strip(),
                "evidence_strength": str(row.get("evidence_strength", "")).strip(),
                "source_anchor": str(existing.get("source_anchor") or row.get("source_anchor", "")).strip(),
                "source_title": str(existing.get("source_title") or row.get("source_title", "")).strip(),
                "source_url": str(existing.get("source_url") or row.get("source_url", "")).strip(),
                "current_signal": str(row.get("potency_or_signal", "")).strip(),
                "assay_type_honesty": str(
                    existing.get("assay_type_honesty") or "functional_not_direct_binding"
                ).strip(),
                "supports_direct_quantitative_binding": str(
                    existing.get("supports_direct_quantitative_binding") or support_default
                ).strip(),
                "quantitative_measure_kind": str(
                    existing.get("quantitative_measure_kind") or quantitative_kind
                ).strip(),
                "quantitative_measure_value": str(
                    existing.get("quantitative_measure_value") or quantitative_value
                ).strip(),
                "quantitative_measure_units": str(
                    existing.get("quantitative_measure_units") or quantitative_units
                ).strip(),
                "replacement_reference_binding_kcal_mol": str(
                    existing.get("replacement_reference_binding_kcal_mol", "")
                ).strip(),
                "capture_status": str(existing.get("capture_status") or capture_default).strip(),
                "next_required_action": str(
                    existing.get("next_required_action") or next_step_default
                ).strip(),
                "source_note": str(existing.get("source_note") or _default_note(row)).strip(),
            }
        )

    rows.sort(key=lambda item: (int(item.get("priority_rank", 999) or 999), str(item.get("packet_step", ""))))
    supportive_count = sum(
        1
        for row in rows
        if str(row.get("supports_direct_quantitative_binding", "")).strip().lower() in {"yes", "true", "1"}
    )
    source_linked_count = sum(
        1 for row in rows if str(row.get("source_title", "")).strip() or str(row.get("source_url", "")).strip()
    )
    summary = {
        "family": "aqp1",
        "binder_row_count": len(rows),
        "source_linked_count": source_linked_count,
        "supportive_direct_quantitative_binding_count": supportive_count,
        "captured_review_only_gap_count": sum(
            1 for row in rows if str(row.get("capture_status", "")).strip() == "captured_review_only_gap"
        ),
        "pending_capture_count": sum(
            1 for row in rows if str(row.get("capture_status", "")).strip() == "pending_capture"
        ),
        "kcal_overlay_ready_count": sum(
            1 for row in rows if str(row.get("replacement_reference_binding_kcal_mol", "")).strip()
        ),
        "next_required_step": (
            "Capture direct quantitative binding evidence for bacopaside II, AqB013, and AqB011. "
            "Until then keep replacement_reference_binding_kcal_mol blank and treat these rows as review-only staged binders."
        ),
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# AQP1 Quantitative-Binding Capture Sheet",
        "",
        f"- family: `{summary['family']}`",
        f"- binder_row_count: `{summary['binder_row_count']}`",
        f"- source_linked_count: `{summary['source_linked_count']}`",
        f"- supportive_direct_quantitative_binding_count: `{summary['supportive_direct_quantitative_binding_count']}`",
        f"- captured_review_only_gap_count: `{summary['captured_review_only_gap_count']}`",
        f"- pending_capture_count: `{summary['pending_capture_count']}`",
        f"- kcal_overlay_ready_count: `{summary['kcal_overlay_ready_count']}`",
        "",
        "## Next Step",
        "",
        f"- {summary['next_required_step']}",
        "",
        "## Rows",
        "",
        "| priority_rank | packet_step | candidate_name | direct_quantitative | capture_status | source_anchor | current_signal | replacement_reference_binding_kcal_mol |",
        "| ---: | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| {row['priority_rank']} | `{row['packet_step']}` | `{row['candidate_name']}` | "
            f"`{row['supports_direct_quantitative_binding']}` | `{row['capture_status']}` | "
            f"`{row['source_anchor']}` | `{row['current_signal']}` | "
            f"`{row['replacement_reference_binding_kcal_mol'] or '-'}` |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build an AQP1 quantitative-binding capture sheet for the three staged binder rows.")
    parser.add_argument("--external-seed-json", default=DEFAULT_EXTERNAL_SEED_JSON)
    parser.add_argument("--workbook-json", default=DEFAULT_WORKBOOK_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    out_csv = _resolve(args.out_csv)
    payload = build_payload(
        _load_json(args.external_seed_json),
        _load_json(args.workbook_json),
        existing_sheet=_existing_by_step(out_csv),
    )
    out_json = _resolve(args.out_json)
    out_md = _resolve(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    _write_csv(out_csv, payload["rows"])
    _write_markdown(out_md, payload)


if __name__ == "__main__":
    main()

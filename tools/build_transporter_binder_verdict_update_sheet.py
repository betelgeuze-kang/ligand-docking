#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

FAMILY_DEFAULTS: dict[str, dict[str, str]] = {
    "aqp1": {
        "queue_json": "runs/aqp1_manual_review_queue_current.json",
        "evidence_json": "runs/aqp1_candidate_evidence_ledger_current.json",
        "out_json": "runs/aqp1_binder_verdict_update_sheet_current.json",
        "out_csv": "runs/aqp1_binder_verdict_update_sheet_current.csv",
        "out_md": "runs/aqp1_binder_verdict_update_sheet_current.md",
        "title": "AQP1 Binder Verdict Update Sheet",
        "family_label": "AQP1",
    },
    "glut1": {
        "queue_json": "runs/glut1_manual_review_queue_current.json",
        "evidence_json": "runs/glut1_external_evidence_seed_current.json",
        "out_json": "runs/glut1_binder_verdict_update_sheet_current.json",
        "out_csv": "runs/glut1_binder_verdict_update_sheet_current.csv",
        "out_md": "runs/glut1_binder_verdict_update_sheet_current.md",
        "title": "GLUT1 Binder Verdict Update Sheet",
        "family_label": "GLUT1",
    },
}


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


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as fh:
        return [dict(row) for row in csv.DictReader(fh)]


def _existing_by_step(path: Path) -> dict[str, dict[str, str]]:
    if not path.exists():
        return {}
    return {str(row.get("packet_step", "")).strip(): row for row in _read_csv(path)}


def _evidence_lookup(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    lookup: dict[str, dict[str, Any]] = {}
    for row in rows:
        key = str(row.get("candidate_name", "")).strip()
        if key:
            lookup[key] = dict(row)
    return lookup


def _infer_verdict(review_bucket: str, explicit_verdict: str) -> str:
    verdict = explicit_verdict.strip()
    if verdict:
        return verdict
    bucket = review_bucket.strip()
    if bucket.startswith("review_only"):
        return "keep_review_only"
    if bucket.startswith("defer"):
        return "defer"
    if "tool_reference" in bucket or bucket == "caution_only":
        return "caution_only"
    return ""


def _suggested_note(
    candidate_name: str,
    evidence_strength: str,
    promotion_blocker: str,
    next_required_action: str,
    potency_or_signal: str,
) -> str:
    evidence_text = potency_or_signal.strip() or "transporter-context evidence exists but is still below authoritative apply."
    blocker_text = promotion_blocker.strip() or "transporter-specific packet evidence is still insufficient"
    next_text = next_required_action.strip() or "manual_curated_search_or_defer"
    strength = evidence_strength.strip() or "unlabeled"
    return (
        f"Suggested hold: keep `{candidate_name}` in manual-review only status. "
        f"Current evidence strength is `{strength}` and the best anchor is `{evidence_text}`. "
        f"Blocker: `{blocker_text}`. Next action: `{next_text}`."
    )


def build_payload(
    family: str,
    queue_payload: dict[str, Any],
    evidence_payload: dict[str, Any],
    existing_sheet: dict[str, dict[str, str]] | None = None,
) -> dict[str, Any]:
    existing_sheet = existing_sheet or {}
    evidence_rows = list(evidence_payload.get("rows", []) or [])
    evidence_by_candidate = _evidence_lookup(evidence_rows)
    sheet_rows: list[dict[str, Any]] = []

    for row in queue_payload.get("rows", []) or []:
        if str(row.get("replacement_is_binder", "")).strip() != "1":
            continue
        packet_step = str(row.get("packet_step", "")).strip()
        existing = existing_sheet.get(packet_step, {})
        candidate_name = str(row.get("suggested_external_candidate", "")).strip()
        evidence = evidence_by_candidate.get(candidate_name, {})
        source_anchor = str(evidence.get("anchor", evidence.get("source_anchor", ""))).strip()
        evidence_class = str(evidence.get("mechanism_bucket", evidence.get("evidence_class", ""))).strip()
        evidence_strength = str(evidence.get("confidence", evidence.get("evidence_strength", ""))).strip()
        review_bucket = str(evidence.get("review_bucket", row.get("suggested_external_review_bucket", ""))).strip()
        current_recommended_verdict = _infer_verdict(
            review_bucket,
            str(evidence.get("recommended_verdict", "")).strip(),
        )
        caution = str(evidence.get("caution", "")).strip()
        source_url = str(evidence.get("source_url", "")).strip()
        potency_or_signal = str(evidence.get("potency_or_signal", "")).strip()
        suggested_manual_verdict = current_recommended_verdict or "keep_review_only"
        suggested_manual_confidence_update = evidence_strength
        suggested_manual_decision_note = _suggested_note(
            candidate_name,
            evidence_strength,
            str(row.get("promotion_blocker", "")).strip(),
            str(row.get("next_required_action", "")).strip(),
            potency_or_signal,
        )
        sheet_rows.append(
            {
                "priority_rank": str(row.get("priority_rank", "")).strip(),
                "target_id": FAMILY_DEFAULTS[family]["family_label"],
                "packet_step": packet_step,
                "current_ligand_id": str(row.get("current_ligand_id", "")).strip(),
                "candidate_name": candidate_name,
                "source_anchor": source_anchor,
                "source_url": source_url,
                "evidence_class": evidence_class,
                "evidence_strength": evidence_strength,
                "potency_or_signal": potency_or_signal,
                "current_review_bucket": review_bucket,
                "current_recommended_verdict": current_recommended_verdict,
                "promotion_blocker": str(row.get("promotion_blocker", "")).strip(),
                "suggested_manual_verdict": suggested_manual_verdict,
                "suggested_manual_confidence_update": suggested_manual_confidence_update,
                "suggested_manual_decision_note": suggested_manual_decision_note,
                "manual_verdict_update": str(existing.get("manual_verdict_update", "")).strip(),
                "manual_confidence_update": str(existing.get("manual_confidence_update", "")).strip(),
                "manual_source_url_override": str(existing.get("manual_source_url_override", "")).strip(),
                "manual_decision_note": str(existing.get("manual_decision_note", "")).strip(),
                "update_status": str(existing.get("update_status", "")).strip() or "pending_manual_verdict",
                "next_required_action": str(row.get("next_required_action", "")).strip(),
                "caution": caution,
            }
        )

    summary = {
        "family": family,
        "binder_slot_count": len(sheet_rows),
        "suggested_prefill_count": sum(1 for row in sheet_rows if row["suggested_manual_verdict"]),
        "pending_manual_verdict_count": sum(1 for row in sheet_rows if row["update_status"] == "pending_manual_verdict"),
        "completed_manual_verdict_count": sum(1 for row in sheet_rows if row["update_status"] != "pending_manual_verdict"),
        "next_required_step": "Fill manual_verdict_update and manual_decision_note for binder slots before any transporter packet promotion discussion.",
    }
    return {"summary": summary, "sheet_rows": sheet_rows}


def _write_markdown(path: Path, payload: dict[str, Any], title: str) -> None:
    lines = [
        f"# {title}",
        "",
        f"- binder_slot_count: `{payload['summary']['binder_slot_count']}`",
        f"- suggested_prefill_count: `{payload['summary']['suggested_prefill_count']}`",
        f"- pending_manual_verdict_count: `{payload['summary']['pending_manual_verdict_count']}`",
        f"- completed_manual_verdict_count: `{payload['summary']['completed_manual_verdict_count']}`",
        "",
        "## Next Step",
        "",
        f"- {payload['summary']['next_required_step']}",
        "",
        "## Binder Verdict Updates",
        "",
        "| priority_rank | packet_step | candidate_name | source_anchor | evidence_strength | current_recommended_verdict | suggested_manual_verdict | manual_verdict_update | update_status |",
        "| ---: | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["sheet_rows"]:
        lines.append(
            f"| {row['priority_rank']} | `{row['packet_step']}` | `{row['candidate_name']}` | `{row['source_anchor']}` | "
            f"`{row['evidence_strength']}` | `{row['current_recommended_verdict']}` | `{row['suggested_manual_verdict']}` | `{row['manual_verdict_update']}` | `{row['update_status']}` |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a transporter binder verdict update sheet for manual review.")
    parser.add_argument("--family", choices=sorted(FAMILY_DEFAULTS.keys()), required=True)
    parser.add_argument("--queue-json")
    parser.add_argument("--evidence-json")
    parser.add_argument("--out-json")
    parser.add_argument("--out-csv")
    parser.add_argument("--out-md")
    args = parser.parse_args()
    defaults = FAMILY_DEFAULTS[args.family]
    for key in ("queue_json", "evidence_json", "out_json", "out_csv", "out_md"):
        if not getattr(args, key):
            setattr(args, key, defaults[key])
    return args


def main() -> None:
    args = parse_args()
    out_csv = _resolve(args.out_csv)
    payload = build_payload(
        args.family,
        _load_json(args.queue_json),
        _load_json(args.evidence_json),
        existing_sheet=_existing_by_step(out_csv),
    )
    out_json = _resolve(args.out_json)
    out_md = _resolve(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    _write_csv(out_csv, payload["sheet_rows"])
    _write_markdown(out_md, payload, FAMILY_DEFAULTS[args.family]["title"])


if __name__ == "__main__":
    main()

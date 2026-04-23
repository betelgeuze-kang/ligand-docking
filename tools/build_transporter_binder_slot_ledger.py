#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_WAVE_DECISION_JSON = "runs/transporter_wave_decision_current.json"
DEFAULT_AQP1_QUEUE_JSON = "runs/aqp1_manual_review_queue_current.json"
DEFAULT_AQP1_LEDGER_JSON = "runs/aqp1_candidate_evidence_ledger_current.json"
DEFAULT_AQP1_VERDICT_JSON = "runs/aqp1_candidate_verdict_sheet_current.json"
DEFAULT_GLUT1_QUEUE_JSON = "runs/glut1_manual_review_queue_current.json"
DEFAULT_GLUT1_SEED_JSON = "runs/glut1_external_evidence_seed_current.json"
DEFAULT_GLUT1_VERDICT_JSON = "runs/glut1_candidate_verdict_sheet_current.json"
DEFAULT_OUT_JSON = "runs/transporter_binder_slot_ledger_current.json"
DEFAULT_OUT_CSV = "runs/transporter_binder_slot_ledger_current.csv"
DEFAULT_OUT_MD = "runs/transporter_binder_slot_ledger_current.md"


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


def _wave_label_for_target(wave_decision: dict[str, Any], target_id: str) -> str:
    for row in wave_decision.get("rows", []) or []:
        if str(row.get("target_id", "")).upper() == target_id.upper():
            return str(row.get("wave_label", "")).strip()
    return ""


def _index_by_key(rows: list[dict[str, Any]], key: str) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for row in rows:
        value = str(row.get(key, "")).strip()
        if value:
            index[value] = dict(row)
    return index


def _binder_rows(queue_payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for row in queue_payload.get("rows", []) or []:
        if str(row.get("replacement_is_binder", "")).strip() == "1":
            rows.append(dict(row))
    return rows


def _build_family_rows(
    target_id: str,
    wave_decision: dict[str, Any],
    queue_payload: dict[str, Any],
    evidence_rows: list[dict[str, Any]],
    verdict_payload: dict[str, Any],
) -> list[dict[str, Any]]:
    evidence_by_candidate = _index_by_key(evidence_rows, "candidate_name")
    verdict_by_candidate = _index_by_key(list(verdict_payload.get("rows", []) or []), "candidate_name")
    wave_label = _wave_label_for_target(wave_decision, target_id)
    rows: list[dict[str, Any]] = []
    for queue_row in _binder_rows(queue_payload):
        candidate = str(queue_row.get("suggested_external_candidate", "")).strip()
        evidence = evidence_by_candidate.get(candidate, {})
        verdict = verdict_by_candidate.get(candidate, {})
        rows.append(
            {
                "target_id": target_id,
                "wave_label": wave_label,
                "packet_step": str(queue_row.get("packet_step", "")).strip(),
                "current_ligand_id": str(queue_row.get("current_ligand_id", "")).strip(),
                "candidate_name": candidate,
                "evidence_anchor": str(evidence.get("anchor", evidence.get("source_anchor", ""))).strip(),
                "evidence_class": str(evidence.get("mechanism_bucket", evidence.get("evidence_class", ""))).strip(),
                "evidence_strength": str(evidence.get("confidence", evidence.get("evidence_strength", ""))).strip(),
                "review_bucket": str(verdict.get("review_bucket", queue_row.get("suggested_external_review_bucket", ""))).strip(),
                "recommended_verdict": str(verdict.get("recommended_verdict", "")).strip(),
                "promotion_blocker": str(queue_row.get("promotion_blocker", "")).strip(),
                "next_required_action": str(queue_row.get("next_required_action", "")).strip(),
                "notes": str(queue_row.get("notes", "")).strip(),
            }
        )
    return rows


def build_payload(
    wave_decision: dict[str, Any],
    aqp1_queue: dict[str, Any],
    aqp1_ledger: dict[str, Any],
    aqp1_verdict: dict[str, Any],
    glut1_queue: dict[str, Any],
    glut1_seed: dict[str, Any],
    glut1_verdict: dict[str, Any],
) -> dict[str, Any]:
    rows = _build_family_rows(
        "AQP1",
        wave_decision,
        aqp1_queue,
        list(aqp1_ledger.get("rows", []) or []),
        aqp1_verdict,
    ) + _build_family_rows(
        "GLUT1",
        wave_decision,
        glut1_queue,
        list(glut1_seed.get("rows", []) or []),
        glut1_verdict,
    )
    summary = {
        "binder_slot_count": len(rows),
        "aqp1_binder_slot_count": sum(1 for row in rows if row["target_id"] == "AQP1"),
        "glut1_binder_slot_count": sum(1 for row in rows if row["target_id"] == "GLUT1"),
        "keep_review_only_count": sum(1 for row in rows if row["recommended_verdict"] == "keep_review_only"),
        "manual_curated_search_count": sum(1 for row in rows if row["next_required_action"] == "manual_curated_search_or_defer"),
        "next_required_step": (
            "Use this binder-slot ledger as the first transporter blocker-closure surface. Keep every slot in reviewer-state only, work AQP1 first-wave before GLUT1, "
            "and do not promote any slot until transporter-specific packet evidence is stronger than the current scaffold-only standard."
        ),
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# Transporter Binder Slot Ledger",
        "",
        f"- binder_slot_count: `{summary['binder_slot_count']}`",
        f"- aqp1_binder_slot_count: `{summary['aqp1_binder_slot_count']}`",
        f"- glut1_binder_slot_count: `{summary['glut1_binder_slot_count']}`",
        f"- keep_review_only_count: `{summary['keep_review_only_count']}`",
        f"- manual_curated_search_count: `{summary['manual_curated_search_count']}`",
        "",
        "## Next Step",
        "",
        f"- {summary['next_required_step']}",
        "",
        "## Binder Slots",
        "",
        "| target_id | wave_label | packet_step | candidate_name | evidence_anchor | evidence_strength | review_bucket | recommended_verdict | promotion_blocker | next_required_action |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['target_id']}` | `{row['wave_label']}` | `{row['packet_step']}` | `{row['candidate_name']}` | `{row['evidence_anchor']}` | "
            f"`{row['evidence_strength']}` | `{row['review_bucket']}` | `{row['recommended_verdict']}` | `{row['promotion_blocker']}` | `{row['next_required_action']}` |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a transporter binder-slot ledger from AQP1 and GLUT1 review artifacts.")
    parser.add_argument("--wave-decision-json", default=DEFAULT_WAVE_DECISION_JSON)
    parser.add_argument("--aqp1-queue-json", default=DEFAULT_AQP1_QUEUE_JSON)
    parser.add_argument("--aqp1-ledger-json", default=DEFAULT_AQP1_LEDGER_JSON)
    parser.add_argument("--aqp1-verdict-json", default=DEFAULT_AQP1_VERDICT_JSON)
    parser.add_argument("--glut1-queue-json", default=DEFAULT_GLUT1_QUEUE_JSON)
    parser.add_argument("--glut1-seed-json", default=DEFAULT_GLUT1_SEED_JSON)
    parser.add_argument("--glut1-verdict-json", default=DEFAULT_GLUT1_VERDICT_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        _load_json(args.wave_decision_json),
        _load_json(args.aqp1_queue_json),
        _load_json(args.aqp1_ledger_json),
        _load_json(args.aqp1_verdict_json),
        _load_json(args.glut1_queue_json),
        _load_json(args.glut1_seed_json),
        _load_json(args.glut1_verdict_json),
    )
    out_json = _resolve(args.out_json)
    out_csv = _resolve(args.out_csv)
    out_md = _resolve(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    _write_csv(out_csv, payload["rows"])
    _write_markdown(out_md, payload)


if __name__ == "__main__":
    main()

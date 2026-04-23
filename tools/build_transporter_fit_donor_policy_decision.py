#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_AQP1_NOTE_JSON = "runs/aqp1_local_evidence_note_current.json"
DEFAULT_GLUT1_NOTE_JSON = "runs/glut1_local_evidence_note_current.json"
DEFAULT_TRANSPORTER_READINESS_JSON = "runs/transporter_membrane_readiness_current.json"
DEFAULT_OUT_JSON = "runs/transporter_fit_donor_policy_decision_current.json"
DEFAULT_OUT_CSV = "runs/transporter_fit_donor_policy_decision_current.csv"
DEFAULT_OUT_MD = "runs/transporter_fit_donor_policy_decision_current.md"


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


def build_payload(aqp1_note: dict[str, Any], glut1_note: dict[str, Any], transporter_readiness: dict[str, Any]) -> dict[str, Any]:
    aqp1 = dict(aqp1_note.get("summary", {}) or {})
    glut1 = dict(glut1_note.get("summary", {}) or {})
    readiness = dict(transporter_readiness.get("summary", {}) or {})
    rows = [
        {
            "decision_scope": "current_scaffold_default",
            "decision": "keep_existing_fit_donor_pool_temporarily",
            "status": "frozen_for_scaffold_only",
            "rationale": "Both AQP1 and GLUT1 remain local-evidence blocked and dry-run only; reusing the existing EGFR_KINASE donor pool is the lower-risk scaffold default until real transporter ligand packets exist.",
        },
        {
            "decision_scope": "future_claim_bearing_transporter_run",
            "decision": "revisit_after_ligand_packet_curation",
            "status": "blocked",
            "rationale": "Do not freeze a claim-bearing donor policy until transporter-specific ligand evidence is curated and the first runnable packet is no longer placeholder-driven.",
        },
    ]
    return {
        "summary": {
            "decision_status": "scaffold_default_keep_existing_fit_donor_pool",
            "scaffold_fit_donor_target": aqp1.get("temporary_fit_donor_target", "") or glut1.get("temporary_fit_donor_target", ""),
            "aqp1_local_evidence_status": aqp1.get("endpoint_status", ""),
            "glut1_local_evidence_status": glut1.get("endpoint_status", ""),
            "transporter_p0_open_count": readiness.get("p0_open_count", ""),
            "next_required_step": "Keep EGFR_KINASE as the temporary scaffold donor pool for transporter dry-run scaffolds only. Re-open the family-level donor policy once AQP1 or GLUT1 ligand packets are no longer placeholder-driven.",
        },
        "rows": rows,
    }


def _write_md(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# Transporter Fit-Donor Policy Decision",
        "",
        f"- decision_status: `{s['decision_status']}`",
        f"- scaffold_fit_donor_target: `{s['scaffold_fit_donor_target']}`",
        f"- aqp1_local_evidence_status: `{s['aqp1_local_evidence_status']}`",
        f"- glut1_local_evidence_status: `{s['glut1_local_evidence_status']}`",
        f"- transporter_p0_open_count: `{s['transporter_p0_open_count']}`",
        "",
        "## Next Step",
        "",
        f"- {s['next_required_step']}",
        "",
        "## Decision Rows",
        "",
        "| decision_scope | decision | status | rationale |",
        "| --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(f"| {row['decision_scope']} | `{row['decision']}` | `{row['status']}` | {row['rationale']} |")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a family-level transporter fit-donor policy decision artifact.")
    parser.add_argument("--aqp1-note-json", default=DEFAULT_AQP1_NOTE_JSON)
    parser.add_argument("--glut1-note-json", default=DEFAULT_GLUT1_NOTE_JSON)
    parser.add_argument("--transporter-readiness-json", default=DEFAULT_TRANSPORTER_READINESS_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        _load_json(args.aqp1_note_json),
        _load_json(args.glut1_note_json),
        _load_json(args.transporter_readiness_json),
    )
    out_json = _resolve(args.out_json)
    out_csv = _resolve(args.out_csv)
    out_md = _resolve(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    _write_csv(out_csv, payload["rows"])
    _write_md(out_md, payload)


if __name__ == "__main__":
    main()

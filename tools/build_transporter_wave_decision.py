#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DASHBOARD_JSON = "runs/transporter_manual_review_dashboard_current.json"
DEFAULT_READINESS_JSON = "runs/transporter_membrane_readiness_current.json"
DEFAULT_OUT_JSON = "runs/transporter_wave_decision_current.json"
DEFAULT_OUT_CSV = "runs/transporter_wave_decision_current.csv"
DEFAULT_OUT_MD = "runs/transporter_wave_decision_current.md"


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


def build_payload(dashboard: dict[str, Any], readiness: dict[str, Any]) -> dict[str, Any]:
    dashboard_rows = {str(row.get("target_id", "")).strip(): row for row in list(dashboard.get("target_rows", []) or [])}
    readiness_rows = {str(row.get("target_id", "")).strip(): row for row in list(readiness.get("target_rows", []) or [])}
    aqp1_d = dashboard_rows.get("AQP1", {})
    glut1_d = dashboard_rows.get("GLUT1", {})
    aqp1_r = readiness_rows.get("Aquaporin_1", {})
    glut1_r = readiness_rows.get("GLUT1_4PYP", {})
    rows = [
        {
            "wave_rank": 1,
            "target_id": "AQP1",
            "wave_label": "first_wave_low_risk",
            "p0_open_count": aqp1_r.get("p0_open_count", ""),
            "local_evidence_status": aqp1_d.get("local_evidence_status", ""),
            "placeholder_rows": aqp1_d.get("placeholder_rows", ""),
            "rationale": "AQP1 already has native target and target-meta scaffold anchors in place and carries the smaller remaining P0 burden, so it is the cleanest low-risk transporter first wave.",
        },
        {
            "wave_rank": 2,
            "target_id": "GLUT1",
            "wave_label": "second_wave_higher_upside",
            "p0_open_count": glut1_r.get("p0_open_count", ""),
            "local_evidence_status": glut1_d.get("local_evidence_status", ""),
            "placeholder_rows": glut1_d.get("placeholder_rows", ""),
            "rationale": "GLUT1 remains the higher-upside transporter expansion target, but it still has more open scaffold blockers and placeholder target metadata, so it should stay second-wave.",
        },
    ]
    return {
        "summary": {
            "decision_status": "aqp1_first_wave_glut1_second_wave",
            "first_wave_target": "AQP1",
            "second_wave_target": "GLUT1",
            "next_required_step": "Keep AQP1 as the first transporter burn-down target and hold GLUT1 as second-wave until AQP1 ligand packets and family donor policy are no longer placeholder-driven.",
        },
        "rows": rows,
    }


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# Transporter Wave Decision",
        "",
        f"- decision_status: `{s['decision_status']}`",
        f"- first_wave_target: `{s['first_wave_target']}`",
        f"- second_wave_target: `{s['second_wave_target']}`",
        "",
        "## Next Step",
        "",
        f"- {s['next_required_step']}",
        "",
        "## Waves",
        "",
        "| wave_rank | target_id | wave_label | p0_open_count | local_evidence_status | placeholder_rows | rationale |",
        "| ---: | --- | --- | ---: | --- | ---: | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| {row['wave_rank']} | {row['target_id']} | `{row['wave_label']}` | {row['p0_open_count']} | `{row['local_evidence_status']}` | {row['placeholder_rows']} | {row['rationale']} |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a transporter wave decision artifact for AQP1 vs GLUT1 sequencing.")
    parser.add_argument("--dashboard-json", default=DEFAULT_DASHBOARD_JSON)
    parser.add_argument("--readiness-json", default=DEFAULT_READINESS_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(_load_json(args.dashboard_json), _load_json(args.readiness_json))
    out_json = _resolve(args.out_json)
    out_csv = _resolve(args.out_csv)
    out_md = _resolve(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    _write_csv(out_csv, payload["rows"])
    _write_markdown(out_md, payload)


if __name__ == "__main__":
    main()

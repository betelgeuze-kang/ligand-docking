#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[1]

DEFAULT_ANCHORS_JSON = "config/idp_observable_anchors_expanded_v5.json"
DEFAULT_SCAFFOLD_JSON = "runs/idp_broader_anchor_shadow_scaffold_current.json"
DEFAULT_OUT_JSON = "runs/idp_anchor_curation_queue_current.json"
DEFAULT_OUT_CSV = "runs/idp_anchor_curation_queue_current.csv"
DEFAULT_OUT_MD = "runs/idp_anchor_curation_queue_current.md"


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


def _artifact_reference_count(target_name: str) -> int:
    count = 0
    runs_dir = ROOT / "runs"
    for path in runs_dir.glob("*current*"):
        try:
            text = path.read_text(encoding="utf-8")
        except Exception:
            continue
        count += text.count(target_name)
    return count


def _priority_band(target_name: str, artifact_reference_count: int) -> str:
    if target_name == "page4":
        return "first_wave_existing_repo_touchpoint"
    if artifact_reference_count > 0:
        return "second_wave_existing_repo_touchpoint"
    return "third_wave_needs_new_curated_anchor"


def _priority_rank(priority_band: str) -> int:
    if priority_band == "first_wave_existing_repo_touchpoint":
        return 0
    if priority_band == "second_wave_existing_repo_touchpoint":
        return 1
    return 2


def build_payload(
    anchors_payload: dict[str, Any],
    scaffold_payload: dict[str, Any],
) -> dict[str, Any]:
    targets = dict((anchors_payload.get("targets", {}) if isinstance(anchors_payload.get("targets", {}), dict) else {}) or {})
    scaffold_rows = [dict(row) for row in scaffold_payload.get("rows", []) or []]
    controlled_targets = {str(row.get("target_name", "")).strip() for row in scaffold_rows if str(row.get("target_name", "")).strip()}

    rows: list[dict[str, Any]] = []
    for name, meta in sorted(targets.items()):
        source = str((meta or {}).get("source", "")).strip()
        if name in controlled_targets or source != "branch_family_provisional":
            continue
        provenance_kind = str((((meta or {}).get("provenance") or {}) if isinstance((meta or {}).get("provenance"), dict) else {}).get("kind", "")).strip()
        artifact_reference_count = _artifact_reference_count(name)
        priority_band = _priority_band(name, artifact_reference_count)
        rows.append(
            {
                "target_name": name,
                "source_class": source,
                "provenance_kind": provenance_kind,
                "artifact_reference_count": artifact_reference_count,
                "priority_band": priority_band,
                "curation_goal": "add one anchor-backed target beyond the current validated 7-target scaffold",
                "next_action": "find local or curated literature-grade anchor evidence and promote only after provenance is explicit",
            }
        )

    rows.sort(key=lambda row: (_priority_rank(str(row["priority_band"])), -int(row["artifact_reference_count"]), row["target_name"]))
    first_wave = [row["target_name"] for row in rows if row["priority_band"] == "first_wave_existing_repo_touchpoint"]
    second_wave_count = sum(1 for row in rows if row["priority_band"] == "second_wave_existing_repo_touchpoint")

    summary = {
        "status": "anchor_curation_queue_ready",
        "candidate_count": len(rows),
        "current_validated_anchor_backed_target_count": len(controlled_targets),
        "additional_anchor_backed_target_count": 0,
        "first_wave_candidate_count": len(first_wave),
        "second_wave_candidate_count": second_wave_count,
        "today_open_now": first_wave[0] if first_wave else (rows[0]["target_name"] if rows else ""),
        "next_required_step": (
            "Start anchor curation with the highest-touch provisional target already seen in current repo artifacts, and only call the roster broader after at least one candidate graduates from provisional-only to anchor-backed."
        ),
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# IDP Anchor Curation Queue",
        "",
        f"- status: `{s['status']}`",
        f"- candidate_count: `{s['candidate_count']}`",
        f"- current_validated_anchor_backed_target_count: `{s['current_validated_anchor_backed_target_count']}`",
        f"- additional_anchor_backed_target_count: `{s['additional_anchor_backed_target_count']}`",
        f"- first_wave_candidate_count: `{s['first_wave_candidate_count']}`",
        f"- second_wave_candidate_count: `{s['second_wave_candidate_count']}`",
        f"- today_open_now: `{s['today_open_now']}`",
        "",
        "## Next Step",
        "",
        f"- {s['next_required_step']}",
        "",
        "## Candidates",
        "",
        "| target_name | priority_band | artifact_reference_count | provenance_kind | next_action |",
        "| --- | --- | ---: | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['target_name']}` | `{row['priority_band']}` | {row['artifact_reference_count']} | `{row['provenance_kind']}` | {row['next_action']} |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the next-wave IDP anchor curation queue from provisional-only targets.")
    parser.add_argument("--anchors-json", default=DEFAULT_ANCHORS_JSON)
    parser.add_argument("--scaffold-json", default=DEFAULT_SCAFFOLD_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        _load_json(args.anchors_json),
        _load_json(args.scaffold_json),
    )
    out_json = _resolve(args.out_json)
    out_csv = _resolve(args.out_csv)
    out_md = _resolve(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    write_csv_rows(out_csv, payload["rows"])
    _write_markdown(out_md, payload)


if __name__ == "__main__":
    main()

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
DEFAULT_REVIEW_PACKET_JSON = "runs/idp_broader_shadow_review_packet_current.json"
DEFAULT_OUT_JSON = "runs/idp_broader_anchor_roster_viability_packet_current.json"
DEFAULT_OUT_CSV = "runs/idp_broader_anchor_roster_viability_packet_current.csv"
DEFAULT_OUT_MD = "runs/idp_broader_anchor_roster_viability_packet_current.md"


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


def _anchor_class(source: str) -> str:
    if source == "branch_family_provisional":
        return "provisional_only"
    return "anchor_backed"


def build_payload(
    anchors_payload: dict[str, Any],
    scaffold_payload: dict[str, Any],
    review_packet: dict[str, Any],
) -> dict[str, Any]:
    targets = dict((anchors_payload.get("targets", {}) if isinstance(anchors_payload.get("targets", {}), dict) else {}) or {})
    scaffold_s = dict(scaffold_payload.get("summary", {}) or {})
    scaffold_rows = [dict(row) for row in scaffold_payload.get("rows", []) or []]
    review_s = dict(review_packet.get("summary", {}) or {})

    controlled_targets = {str(row.get("target_name", "")).strip() for row in scaffold_rows if str(row.get("target_name", "")).strip()}
    rows = []
    anchor_backed_total = 0
    additional_anchor_backed = 0
    provisional_only_total = 0
    for name, payload in sorted(targets.items()):
        source = str(payload.get("source", "")).strip()
        anchor_class = _anchor_class(source)
        in_controlled = name in controlled_targets
        if anchor_class == "anchor_backed":
            anchor_backed_total += 1
            if not in_controlled:
                additional_anchor_backed += 1
        else:
            provisional_only_total += 1
        rows.append(
            {
                "target_name": name,
                "anchor_class": anchor_class,
                "in_controlled_scaffold": in_controlled,
                "source": source,
                "provenance_kind": str(((payload.get("provenance") or {}) if isinstance(payload.get("provenance"), dict) else {}).get("kind", "")).strip(),
            }
        )

    summary = {
        "status": "anchor_backed_broader_roster_viability_assessed",
        "controlled_target_count": len(controlled_targets),
        "local_target_count": len(rows),
        "anchor_backed_target_count": anchor_backed_total,
        "additional_anchor_backed_target_count": additional_anchor_backed,
        "first_additional_anchor_backed_target": (
            next(
                (
                    row["target_name"]
                    for row in rows
                    if row["anchor_class"] == "anchor_backed" and not row["in_controlled_scaffold"]
                ),
                "",
            )
        ),
        "provisional_only_target_count": provisional_only_total,
        "broader_anchor_config_ready": additional_anchor_backed > 0,
        "review_packet_ready": bool(review_s),
        "next_required_step": (
            "Keep broader_full_idp_promotion blocked, but page4 now provides the first additional anchor-backed target beyond the controlled 7-target scaffold; reopen broader-shadow review and freeze roster/guardrails before any true broader rerun."
            if additional_anchor_backed > 0
            else
            "Keep broader_full_idp_promotion blocked. With the current local assets there are no additional anchor-backed targets beyond the controlled 7-target scaffold, "
            "so either approve a same-scope process check only or curate at least one additional anchor-backed target before calling the next run broader."
        ),
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# IDP Broader Anchor Roster Viability Packet",
        "",
        f"- status: `{s['status']}`",
        f"- controlled_target_count: `{s['controlled_target_count']}`",
        f"- local_target_count: `{s['local_target_count']}`",
        f"- anchor_backed_target_count: `{s['anchor_backed_target_count']}`",
        f"- additional_anchor_backed_target_count: `{s['additional_anchor_backed_target_count']}`",
        f"- first_additional_anchor_backed_target: `{s['first_additional_anchor_backed_target']}`",
        f"- provisional_only_target_count: `{s['provisional_only_target_count']}`",
        f"- broader_anchor_config_ready: `{s['broader_anchor_config_ready']}`",
        "",
        "## Next Step",
        "",
        f"- {s['next_required_step']}",
        "",
        "## Targets",
        "",
        "| target_name | anchor_class | in_controlled_scaffold | source | provenance_kind |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['target_name']}` | `{row['anchor_class']}` | `{row['in_controlled_scaffold']}` | `{row['source']}` | `{row['provenance_kind']}` |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Assess whether local IDP assets can support a concrete broader anchor-backed rerun config.")
    p.add_argument("--anchors-json", default=DEFAULT_ANCHORS_JSON)
    p.add_argument("--scaffold-json", default=DEFAULT_SCAFFOLD_JSON)
    p.add_argument("--review-packet-json", default=DEFAULT_REVIEW_PACKET_JSON)
    p.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    p.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    p.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return p.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        _load_json(args.anchors_json),
        _load_json(args.scaffold_json),
        _load_json(args.review_packet_json),
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

#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]

DEFAULT_FILL_DRAFT_JSON = "runs/idp_page4_phosphorylation_fill_draft_current.json"
DEFAULT_OUT_JSON = "runs/idp_page4_ph_high_fill_value_packet_current.json"
DEFAULT_OUT_CSV = "runs/idp_page4_ph_high_fill_value_packet_current.csv"
DEFAULT_OUT_MD = "runs/idp_page4_ph_high_fill_value_packet_current.md"


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


def build_payload(fill_draft_payload: dict[str, Any]) -> dict[str, Any]:
    draft_rows = [dict(row) for row in fill_draft_payload.get("rows", []) or []]
    source_anchor = next(
        (str(row.get("source_anchor", "")).strip() for row in draft_rows if str(row.get("fill_target", "")).strip() == "ph_high_candidate_state_note"),
        "PMID 28289210",
    )

    rows = [
        {
            "fill_field": "ph_high_candidate_state_note",
            "fill_value": "CLK2-like hyperphosphorylation can be treated as a high-phosphorylation PAGE4 state that is more expanded and more random-coil-like than the compact HIPK1-like state when the mapping is explicit and construct-matched.",
            "source_anchor": source_anchor,
            "source_url": "https://pubmed.ncbi.nlm.nih.gov/28289210/",
            "support_level": "abstract_backed_draft",
            "guardrail": "do_not_mix_with_base_or_low_phosphorylation_state",
        },
        {
            "fill_field": "ph_high_candidate_aggregation_note",
            "fill_value": "The high-phosphorylation PAGE4 ensemble is better treated as expanded with diminished AP-1 affinity rather than as direct aggregation-positive evidence; use expansion or aggregation-negative language only when the state mapping is explicit.",
            "source_anchor": source_anchor,
            "source_url": "https://pubmed.ncbi.nlm.nih.gov/28289210/",
            "support_level": "abstract_backed_draft",
            "guardrail": "do_not_convert_expanded_signal_into_true_aggregation_positive",
        },
    ]

    summary = {
        "status": "page4_ph_high_fill_value_packet_ready",
        "target_name": "page4",
        "condition_name": "ph_high",
        "fill_row_count": len(rows),
        "source_anchor": source_anchor,
        "state_mixing_allowed": False,
        "promotion_ready": False,
        "next_required_step": "Use these ph_high fill values only as draft state-specific notes, then review them together with the ph_low packet before any anchor-backed candidate decision.",
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# IDP Page4 ph_high Fill Value Packet",
        "",
        f"- status: `{s['status']}`",
        f"- target_name: `{s['target_name']}`",
        f"- condition_name: `{s['condition_name']}`",
        f"- fill_row_count: `{s['fill_row_count']}`",
        f"- source_anchor: `{s['source_anchor']}`",
        f"- state_mixing_allowed: `{s['state_mixing_allowed']}`",
        f"- promotion_ready: `{s['promotion_ready']}`",
        "",
        "## Fill Values",
        "",
        "| fill_field | source_anchor | support_level | guardrail |",
        "| --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['fill_field']}` | `{row['source_anchor']}` | `{row['support_level']}` | `{row['guardrail']}` |"
        )
    lines.extend(["", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a draft ph_high fill-value packet for page4.")
    parser.add_argument("--fill-draft-json", default=DEFAULT_FILL_DRAFT_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(_load_json(args.fill_draft_json))
    out_json = _resolve(args.out_json)
    out_csv = _resolve(args.out_csv)
    out_md = _resolve(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    write_csv_rows(out_csv, payload["rows"])
    _write_markdown(out_md, payload)


if __name__ == "__main__":
    main()

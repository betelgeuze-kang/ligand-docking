#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REPLACEMENT_CSV = "runs/pxr_packet_replacement_workbook_current.csv"
DEFAULT_PROVENANCE_CSV = "config/biorxiv_temporal_ligand_provenance_v1.csv"
SOURCE_RELEASE_PRIORITY = {
    "binder": ["gpcr_blind_proxy_v1", "chembl_blind_adrb2_v1", "literature_proxy_v2"],
    "non_binder": ["gpcr_blind_proxy_v1", "literature_proxy_v2"],
}


def _resolve(path_like: str) -> Path:
    path = Path(path_like)
    if path.is_absolute():
        return path
    cwd_path = (Path.cwd() / path).resolve()
    if cwd_path.exists():
        return cwd_path
    return (ROOT / path).resolve()


def _load_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as fh:
        return [dict(row) for row in csv.DictReader(fh)]


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _source_family(source_release: str) -> str:
    text = str(source_release or "").strip()
    return text


def _candidate_pool(rows: list[dict[str, str]]) -> dict[tuple[str, str], list[dict[str, str]]]:
    pool: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    seen: set[tuple[str, str, str]] = set()
    for row in rows:
        source_release = _source_family(row.get("source_release", ""))
        if source_release not in {"gpcr_blind_proxy_v1", "chembl_blind_adrb2_v1", "literature_proxy_v2"}:
            continue
        binder_label = "binder" if str(row.get("is_binder", "")).strip() == "1" else "non_binder"
        key = (source_release, binder_label, str(row.get("ligand_id", "")).strip())
        if key in seen:
            continue
        seen.add(key)
        pool[(source_release, binder_label)].append(row)
    return pool


def _pick_exemplar(pool: dict[tuple[str, str], list[dict[str, str]]], binder_label: str, ordinal: int) -> dict[str, str]:
    priorities = SOURCE_RELEASE_PRIORITY[binder_label]
    ranked: list[dict[str, str]] = []
    for source_release in priorities:
        ranked.extend(pool.get((source_release, binder_label), []))
    if not ranked:
        return {}
    return ranked[ordinal % len(ranked)]


def _hint_tier(source_release: str) -> str:
    if source_release == "chembl_blind_adrb2_v1":
        return "chembl_like_item_publication_template"
    if source_release in {"gpcr_blind_proxy_v1", "literature_proxy_v2"}:
        return "named_ligand_item_publication_template"
    return "unknown_template"


def build_payload(replacement_rows: list[dict[str, str]], provenance_rows: list[dict[str, str]]) -> dict[str, Any]:
    pool = _candidate_pool(provenance_rows)
    helper_rows: list[dict[str, Any]] = []
    binder_counter: Counter[str] = Counter()
    source_counter: Counter[str] = Counter()

    per_label_index: defaultdict[str, int] = defaultdict(int)
    for row in replacement_rows:
        packet = str(row.get("packet", "")).strip()
        packet_step = str(row.get("packet_step", "")).strip()
        binder_label = "binder" if str(row.get("replacement_is_binder", "")).strip() == "1" else "non_binder"
        exemplar = _pick_exemplar(pool, binder_label, per_label_index[binder_label])
        per_label_index[binder_label] += 1
        source_release = str(exemplar.get("source_release", "")).strip()
        source_counter[source_release] += 1
        binder_counter[binder_label] += 1
        helper_rows.append(
            {
                "packet": packet,
                "packet_step": packet_step,
                "current_ligand_id": str(row.get("current_ligand_id", "")).strip(),
                "binder_label": binder_label,
                "current_role": str(row.get("current_role", "")).strip(),
                "template_source_release": source_release,
                "template_source_label": str(exemplar.get("source_label", "")).strip(),
                "template_ligand_id": str(exemplar.get("ligand_id", "")).strip(),
                "template_publication_year": str(exemplar.get("publication_year", "")).strip(),
                "template_provenance_url": str(exemplar.get("provenance_url", "")).strip(),
                "template_curation_status": str(exemplar.get("curation_status", "")).strip(),
                "template_provenance_granularity": str(exemplar.get("provenance_granularity", "")).strip(),
                "template_target": str(exemplar.get("target", "")).strip(),
                "template_domain": str(exemplar.get("domain", "")).strip(),
                "hint_tier": _hint_tier(source_release),
                "safe_use_note": (
                    "Template-only local provenance pattern. Do not copy ligand identity as PXR evidence; reuse only source/provenance formatting after curated PXR evidence is found."
                ),
                "next_action": (
                    "Use this row as a local formatting/provenance template while replacing the PXR placeholder with a curated PXR-specific ligand and evidence source."
                ),
            }
        )

    summary = {
        "replacement_row_count": len(replacement_rows),
        "helper_row_count": len(helper_rows),
        "binder_row_count": binder_counter["binder"],
        "non_binder_row_count": binder_counter["non_binder"],
        "template_source_release_count": len([k for k in source_counter if k]),
        "most_used_template_source_release": source_counter.most_common(1)[0][0] if source_counter else "",
        "next_required_step": "Use local template rows only for source/provenance formatting, then replace each PXR placeholder with curated PXR-specific ligand evidence.",
    }
    source_summaries = [
        {"source_release": source_release, "assigned_rows": count}
        for source_release, count in sorted(source_counter.items())
        if source_release
    ]
    return {
        "target": "PXR_NR1I2_BLIND",
        "summary": summary,
        "source_summaries": source_summaries,
        "helper_rows": helper_rows,
    }


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# PXR Local Candidate Source Helper",
        "",
        f"- target: `{payload['target']}`",
        f"- helper_row_count: `{payload['summary']['helper_row_count']}`",
        f"- template_source_release_count: `{payload['summary']['template_source_release_count']}`",
        f"- most_used_template_source_release: `{payload['summary']['most_used_template_source_release']}`",
        "",
        "## Next Step",
        "",
        f"- {payload['summary']['next_required_step']}",
        "",
        "## Template Source Summary",
        "",
        "| source_release | assigned_rows |",
        "| --- | ---: |",
    ]
    for row in payload["source_summaries"]:
        lines.append(f"| {row['source_release']} | {row['assigned_rows']} |")
    lines.extend(
        [
            "",
            "## Helper Rows",
            "",
            "| packet_step | binder_label | current_role | template_source_release | template_ligand_id | template_publication_year | hint_tier |",
            "| --- | --- | --- | --- | --- | ---: | --- |",
        ]
    )
    for row in payload["helper_rows"]:
        lines.append(
            f"| {row['packet_step']} | {row['binder_label']} | {row['current_role']} | {row['template_source_release']} | `{row['template_ligand_id']}` | {row['template_publication_year']} | {row['hint_tier']} |"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a repo-local PXR candidate source helper from replacement rows and local provenance examples.")
    parser.add_argument("--replacement-csv", default=DEFAULT_REPLACEMENT_CSV)
    parser.add_argument("--provenance-csv", default=DEFAULT_PROVENANCE_CSV)
    parser.add_argument("--out-json", default="runs/pxr_local_candidate_source_helper_current.json")
    parser.add_argument("--out-csv", default="runs/pxr_local_candidate_source_helper_current.csv")
    parser.add_argument("--out-md", default="runs/pxr_local_candidate_source_helper_current.md")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    replacement_rows = _load_csv(_resolve(args.replacement_csv))
    provenance_rows = _load_csv(_resolve(args.provenance_csv))
    payload = build_payload(replacement_rows, provenance_rows)
    out_json = _resolve(args.out_json)
    out_csv = _resolve(args.out_csv)
    out_md = _resolve(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    _write_csv(out_csv, payload["helper_rows"])
    _write_markdown(out_md, payload)


if __name__ == "__main__":
    main()

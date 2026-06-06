#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _write_csv(path: Path, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_rows(
    provenance_rows: list[dict[str, str]],
    helper_rows: list[dict[str, str]],
    source_kind: str,
) -> list[dict[str, str]]:
    helper_by_holdout = {row["holdout_name"]: row for row in helper_rows}
    rows: list[dict[str, str]] = []
    for prov in provenance_rows:
        if (prov.get("source_kind") or "").strip() != source_kind:
            continue
        if (prov.get("provenance_granularity") or "").strip().startswith("item"):
            continue
        helper = helper_by_holdout.get(prov["holdout_name"], {})
        rows.append(
            {
                "holdout_name": prov["holdout_name"],
                "source_kind": source_kind,
                "publication_year": prov.get("publication_year", ""),
                "benchmark_inclusion_date": prov.get("benchmark_inclusion_date", ""),
                "corrected_label_freeze_date": prov.get("corrected_label_freeze_date", ""),
                "provenance_granularity": "",
                "provenance_source": "",
                "curation_status": "manual_item_curation_pending",
                "manual_status": "pending",
                "citation_hint": helper.get("citation", ""),
                "notes": helper.get("notes", ""),
                "pdb_header_date": helper.get("pdb_header_date", ""),
                "eval_corrected_csv": helper.get("eval_corrected_csv", ""),
                "anchor_source": helper.get("anchor_source", ""),
            }
        )
    return sorted(rows, key=lambda row: row["holdout_name"])


def _build_summary(rows: list[dict[str, str]], source_kind: str, csv_name: str) -> str:
    holdouts = ", ".join(row["holdout_name"] for row in rows[:10]) if rows else "none"
    lines = [
        f"# IDP Manual Curation: {source_kind}",
        "",
        f"- source_kind: `{source_kind}`",
        f"- row_count: `{len(rows)}`",
        f"- csv: `{csv_name}`",
        f"- example_holdouts: `{holdouts}`",
        "",
        "## Use",
        "",
        "1. Fill `publication_year` when a construct-matched item-level paper or benchmark source can be identified.",
        "2. Set `provenance_granularity` to `item_publication` only when the row is supported by holdout-specific provenance.",
        "3. Leave unresolved rows unchanged rather than inferring dates from weak hints.",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description="Build manual curation templates for unresolved IDP item-level provenance.")
    ap.add_argument("--provenance-csv", default="config/biorxiv_temporal_idp_provenance_v1.csv")
    ap.add_argument("--helper-csv", default="runs/biorxiv_temporal_idp_item_helpers_current.csv")
    ap.add_argument("--out-dir", default="runs/biorxiv_temporal_idp_manual_curation_current")
    args = ap.parse_args()

    provenance_rows = _read_csv((ROOT / args.provenance_csv).resolve())
    helper_rows = _read_csv((ROOT / args.helper_csv).resolve())
    out_dir = (ROOT / args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    readme_lines = ["# IDP Manual Temporal Curation Bundle", ""]
    fieldnames = [
        "holdout_name",
        "source_kind",
        "publication_year",
        "benchmark_inclusion_date",
        "corrected_label_freeze_date",
        "provenance_granularity",
        "provenance_source",
        "curation_status",
        "manual_status",
        "citation_hint",
        "notes",
        "pdb_header_date",
        "eval_corrected_csv",
        "anchor_source",
    ]
    for source_kind in ("pdb", "synthetic"):
        rows = _build_rows(provenance_rows, helper_rows, source_kind)
        csv_path = out_dir / f"biorxiv_temporal_idp_{source_kind}_manual_facts_current.csv"
        md_path = out_dir / f"biorxiv_temporal_idp_{source_kind}_summary_current.md"
        _write_csv(csv_path, rows, fieldnames)
        _write_text(md_path, _build_summary(rows, source_kind, csv_path.name))
        readme_lines.extend(
            [
                f"## {source_kind}",
                "",
                f"- `{csv_path.name}`",
                f"- `{md_path.name}`",
                "",
            ]
        )

    _write_text(out_dir / "README.md", "\n".join(readme_lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

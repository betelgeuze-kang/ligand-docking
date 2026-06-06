#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
from collections import defaultdict
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


def _slug(value: str) -> str:
    return value.replace(":", "_").replace("/", "_").replace(" ", "_")


def _build_family_outputs(rows: list[dict[str, str]], family: str, out_dir: Path) -> list[Path]:
    family_rows = [row for row in rows if row["source_label"] == family]
    if not family_rows:
        return []

    slug = _slug(family)
    unique_by_ligand: dict[str, dict[str, str]] = {}
    for row in family_rows:
        ligand_id = row["ligand_id"]
        if ligand_id in unique_by_ligand:
            existing = unique_by_ligand[ligand_id]
            existing["tasks"] = ", ".join(sorted(set(existing["tasks"].split(", ")) | {row["task_id"]}))
            existing["targets"] = ", ".join(sorted(set(existing["targets"].split(", ")) | {row["target"]}))
            existing["roles"] = ", ".join(sorted(set(existing["roles"].split(", ")) | {row["role"]}))
            continue
        unique_by_ligand[ligand_id] = {
            "ligand_id": ligand_id,
            "targets": row["target"],
            "tasks": row["task_id"],
            "roles": row["role"],
            "source_release": row["source_release"],
            "publication_year": row["publication_year"],
            "release_date": row["release_date"],
            "provenance_date": row["provenance_date"],
            "provenance_url": row["provenance_url"],
            "notes": row["notes"],
        }

    unique_rows = [unique_by_ligand[key] for key in sorted(unique_by_ligand)]
    unique_csv = out_dir / f"biorxiv_temporal_helper_{slug}_unique_ligands_current.csv"
    _write_csv(
        unique_csv,
        unique_rows,
        [
            "ligand_id",
            "targets",
            "tasks",
            "roles",
            "source_release",
            "publication_year",
            "release_date",
            "provenance_date",
            "provenance_url",
            "notes",
        ],
    )

    rowmap_rows = [
        {
            "task_id": row["task_id"],
            "target": row["target"],
            "ligand_id": row["ligand_id"],
            "role": row["role"],
            "source_label": row["source_label"],
            "source_release": row["source_release"],
            "curation_status": row["curation_status"],
            "publication_year": row["publication_year"],
            "release_date": row["release_date"],
            "provenance_date": row["provenance_date"],
        }
        for row in family_rows
    ]
    rowmap_csv = out_dir / f"biorxiv_temporal_helper_{slug}_rowmap_current.csv"
    _write_csv(
        rowmap_csv,
        rowmap_rows,
        [
            "task_id",
            "target",
            "ligand_id",
            "role",
            "source_label",
            "source_release",
            "curation_status",
            "publication_year",
            "release_date",
            "provenance_date",
        ],
    )

    summary_md = out_dir / f"biorxiv_temporal_helper_{slug}_summary_current.md"
    tasks = sorted({row["task_id"] for row in family_rows})
    targets = sorted({row["target"] for row in family_rows})
    summary_lines = [
        f"# Temporal Family Helper: {family}",
        "",
        f"- source_label: `{family}`",
        f"- row_count: `{len(family_rows)}`",
        f"- unique_ligand_count: `{len(unique_rows)}`",
        f"- tasks: `{', '.join(tasks)}`",
        f"- targets: `{', '.join(targets)}`",
        "",
        "## Use",
        "",
        f"1. Fill provenance fields once in `{unique_csv.name}`.",
        f"2. Use `{rowmap_csv.name}` to propagate the same provenance values back to repeated task rows.",
        "",
    ]
    _write_text(summary_md, "\n".join(summary_lines))
    return [unique_csv, rowmap_csv, summary_md]


def main() -> int:
    ap = argparse.ArgumentParser(description="Build family-specific helper files for temporal provenance curation.")
    ap.add_argument("--ligand-csv", default="config/biorxiv_temporal_ligand_provenance_v1.csv")
    ap.add_argument("--families", default="literature_proxy_v2,gpcr_blind_proxy_v1")
    ap.add_argument("--out-dir", default="runs/biorxiv_temporal_family_helpers_current")
    args = ap.parse_args()

    rows = _read_csv((ROOT / args.ligand_csv).resolve())
    families = [item.strip() for item in args.families.split(",") if item.strip()]
    out_dir = (ROOT / args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    index_lines = [
        "# Temporal Family Helpers",
        "",
    ]
    for family in families:
        created = _build_family_outputs(rows, family, out_dir)
        index_lines.append(f"## {family}")
        if not created:
            index_lines.append("")
            index_lines.append("- no matching rows")
            index_lines.append("")
            continue
        index_lines.append("")
        for path in created:
            index_lines.append(f"- `{path.name}`")
        index_lines.append("")

    _write_text(out_dir / "README.md", "\n".join(index_lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

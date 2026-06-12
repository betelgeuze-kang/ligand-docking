#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]

FAMILY_DEFAULTS: dict[str, dict[str, str]] = {
    "ca2": {
        "sheet_csv": "runs/ca2_binding_verification_sheet_current.csv",
        "spec_json": "runs/ca2_verified_binding_sources_current.json",
    },
    "pxr": {
        "sheet_csv": "runs/pxr_binding_verification_sheet_current.csv",
        "spec_json": "runs/pxr_verified_binding_sources_current.json",
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


def _read_csv(path: Path) -> list[dict[str, str]]:
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


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Apply curated binding/provenance verification values to a packet verification sheet.")
    p.add_argument("--family", choices=sorted(FAMILY_DEFAULTS.keys()), required=True)
    p.add_argument("--sheet-csv")
    p.add_argument("--spec-json")
    args = p.parse_args()
    defaults = FAMILY_DEFAULTS[args.family]
    if not args.sheet_csv:
        args.sheet_csv = defaults["sheet_csv"]
    if not args.spec_json:
        args.spec_json = defaults["spec_json"]
    return args


def main() -> None:
    args = parse_args()
    sheet_csv = _resolve(args.sheet_csv)
    spec_json = _resolve(args.spec_json)
    rows = _read_csv(sheet_csv)
    spec = json.loads(spec_json.read_text(encoding="utf-8"))
    verified_rows = {
        str(row.get("packet_step", "")).strip(): row
        for row in spec.get("verified_rows", [])
        if str(row.get("packet_step", "")).strip()
    }

    updated = 0
    for row in rows:
        packet_step = str(row.get("packet_step", "")).strip()
        verified = verified_rows.get(packet_step)
        if not verified:
            continue
        row["verify_reference_binding_kcal_mol"] = str(verified.get("verify_reference_binding_kcal_mol", "")).strip()
        row["verify_provenance_source"] = str(verified.get("verify_provenance_source", "")).strip()
        row["verify_source_url"] = str(verified.get("verify_source_url", "")).strip()
        row["verification_status"] = str(verified.get("verification_status", "")).strip() or "verified_binding_provenance"
        if str(verified.get("notes", "")).strip():
            row["notes"] = str(verified.get("notes", "")).strip()
        updated += 1

    _write_csv(sheet_csv, rows)
    print(json.dumps({"family": args.family, "updated_row_count": updated, "sheet_csv": str(sheet_csv)}, indent=2))


if __name__ == "__main__":
    main()

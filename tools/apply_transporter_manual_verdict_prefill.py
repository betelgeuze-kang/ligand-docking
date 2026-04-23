#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

DEFAULT_SHEETS = {
    "aqp1": "runs/aqp1_binder_verdict_update_sheet_current.csv",
    "glut1": "runs/glut1_binder_verdict_update_sheet_current.csv",
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


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def apply_prefill(rows: list[dict[str, str]], overwrite: bool = False) -> tuple[list[dict[str, str]], int]:
    updated = 0
    out: list[dict[str, str]] = []
    for row in rows:
        next_row = dict(row)
        if not str(row.get("suggested_manual_verdict", "")).strip():
            out.append(next_row)
            continue
        verdict_missing = overwrite or not str(row.get("manual_verdict_update", "")).strip()
        conf_missing = overwrite or not str(row.get("manual_confidence_update", "")).strip()
        note_missing = overwrite or not str(row.get("manual_decision_note", "")).strip()
        if verdict_missing:
            next_row["manual_verdict_update"] = str(row.get("suggested_manual_verdict", "")).strip()
        if conf_missing:
            next_row["manual_confidence_update"] = str(row.get("suggested_manual_confidence_update", "")).strip()
        if note_missing:
            next_row["manual_decision_note"] = str(row.get("suggested_manual_decision_note", "")).strip()
        if verdict_missing or conf_missing or note_missing:
            next_row["update_status"] = "completed_manual_verdict"
            updated += 1
        out.append(next_row)
    return out, updated


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Copy suggested transporter review-only verdicts into manual_* fields.")
    parser.add_argument("--family", choices=sorted(DEFAULT_SHEETS.keys()) + ["all"], default="all")
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    families = sorted(DEFAULT_SHEETS.keys()) if args.family == "all" else [args.family]
    for family in families:
        path = _resolve(DEFAULT_SHEETS[family])
        rows = _read_csv(path)
        updated_rows, updated = apply_prefill(rows, overwrite=args.overwrite)
        _write_csv(path, updated_rows)
        print(f"{family}: updated {updated} row(s)")


if __name__ == "__main__":
    main()

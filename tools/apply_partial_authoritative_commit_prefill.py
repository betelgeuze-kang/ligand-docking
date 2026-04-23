#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

DEFAULT_SHEETS = {
    "ca2": "runs/ca2_evidence_closure_commit_packet_current.csv",
    "pxr": "runs/pxr_pending_resolution_commit_packet_current.csv",
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


def apply_ca2_prefill(rows: list[dict[str, str]], overwrite: bool = False) -> tuple[list[dict[str, str]], int]:
    updated = 0
    out: list[dict[str, str]] = []
    for row in rows:
        next_row = dict(row)
        missing = overwrite or not str(row.get("manual_decision_note", "")).strip()
        if missing:
            next_row["manual_review_bucket"] = str(row.get("staged_review_bucket", "")).strip()
            next_row["manual_assay_type_honesty"] = str(row.get("staged_assay_type_honesty", "")).strip()
            next_row["manual_promotion_blocker"] = str(row.get("staged_promotion_blocker", "")).strip()
            next_row["manual_next_required_action"] = str(row.get("staged_next_required_action", "")).strip()
            next_row["manual_recommended_resolution"] = str(row.get("staged_recommended_resolution", "")).strip()
            next_row["manual_decision_note"] = str(row.get("staged_manual_decision_note", "")).strip()
            next_row["commit_status"] = "confirmed_review_only"
            updated += 1
        out.append(next_row)
    return out, updated


def apply_pxr_prefill(rows: list[dict[str, str]], overwrite: bool = False) -> tuple[list[dict[str, str]], int]:
    updated = 0
    out: list[dict[str, str]] = []
    for row in rows:
        next_row = dict(row)
        missing = overwrite or not str(row.get("manual_commit_note", "")).strip()
        if missing:
            next_row["manual_commit_class"] = str(row.get("staged_commit_class", "")).strip()
            next_row["manual_resolution_bias"] = str(row.get("staged_resolution_bias", "")).strip()
            next_row["manual_assay_type_honesty"] = str(row.get("staged_assay_type_honesty", "")).strip()
            next_row["manual_promotion_blocker"] = str(row.get("staged_promotion_blocker", "")).strip()
            next_row["manual_next_required_action"] = str(row.get("staged_next_required_action", "")).strip()
            next_row["manual_commit_note"] = str(row.get("staged_commit_note", "")).strip()
            next_row["commit_status"] = (
                "confirmed_review_only"
                if str(row.get("staged_resolution_bias", "")).strip() == "review_only"
                else "confirmed_defer"
            )
            updated += 1
        out.append(next_row)
    return out, updated


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Copy staged CA2/PXR pending-row decisions into manual commit fields.")
    parser.add_argument("--family", choices=sorted(DEFAULT_SHEETS.keys()) + ["all"], default="all")
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    families = sorted(DEFAULT_SHEETS.keys()) if args.family == "all" else [args.family]
    for family in families:
        path = _resolve(DEFAULT_SHEETS[family])
        rows = _read_csv(path)
        if family == "ca2":
            updated_rows, updated = apply_ca2_prefill(rows, overwrite=args.overwrite)
        else:
            updated_rows, updated = apply_pxr_prefill(rows, overwrite=args.overwrite)
        _write_csv(path, updated_rows)
        print(f"{family}: updated {updated} row(s)")


if __name__ == "__main__":
    main()

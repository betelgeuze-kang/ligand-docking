from __future__ import annotations

import csv
from pathlib import Path
from typing import Any


def write_csv_rows(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for key in row.keys():
            if key in seen:
                continue
            seen.add(key)
            fieldnames.append(key)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def rows_by_family(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(row.get("family", "")).strip(): dict(row)
        for row in payload.get("rows", []) or []
        if str(row.get("family", "")).strip()
    }

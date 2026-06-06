#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

from betelgeuze_product.license_decision import APPROVAL_TOKEN, DECISION_CREATE_LICENSE
from betelgeuze_product.license_options import LICENSE_OPTIONS

DEFAULT_OUT_CSV = "runs/product_license_decision_operator_intake.csv"
ALLOWED_LICENSE_IDS = tuple(str(option["spdx_license_id"]) for option in LICENSE_OPTIONS)


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else Path.cwd() / path


def _text(value: Any) -> str:
    return str(value or "").strip()


def _validate_year(value: str) -> str:
    year = _text(value)
    if not year.isdigit():
        raise SystemExit("blocked_license_decision_intake_write: effective_year_must_be_numeric")
    numeric = int(year)
    if numeric < 1900 or numeric > 2100:
        raise SystemExit("blocked_license_decision_intake_write: effective_year_out_of_supported_range")
    return year


def build_license_decision_intake_row(
    *,
    approval_token: str,
    spdx_license_id: str,
    license_text_source: str,
    copyright_holder: str,
    effective_year: str,
    notes: str = "",
) -> dict[str, str]:
    token = _text(approval_token)
    license_id = _text(spdx_license_id)
    text_source = _text(license_text_source)
    holder = _text(copyright_holder)
    year = _validate_year(effective_year)
    if token != APPROVAL_TOKEN:
        raise SystemExit(f"blocked_license_decision_intake_write: approval_token_mismatch:{APPROVAL_TOKEN}")
    if license_id not in ALLOWED_LICENSE_IDS:
        raise SystemExit(
            "blocked_license_decision_intake_write: unsupported_spdx_license_id:"
            f"{license_id or 'missing'};allowed={','.join(ALLOWED_LICENSE_IDS)}"
        )
    if not text_source:
        raise SystemExit("blocked_license_decision_intake_write: missing_license_text_source")
    if not holder:
        raise SystemExit("blocked_license_decision_intake_write: missing_copyright_holder")
    return {
        "decision": DECISION_CREATE_LICENSE,
        "approval_token": token,
        "spdx_license_id": license_id,
        "license_text_source": text_source,
        "copyright_holder": holder,
        "effective_year": year,
        "notes": _text(notes),
    }


def write_license_decision_intake(
    *,
    out_csv: str | Path,
    row: dict[str, str],
    force: bool = False,
) -> dict[str, Any]:
    out_path = _resolve(out_csv)
    if out_path.exists() and not force:
        raise SystemExit(f"blocked_license_decision_intake_write: target_exists:{out_path}")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "decision",
        "approval_token",
        "spdx_license_id",
        "license_text_source",
        "copyright_holder",
        "effective_year",
        "notes",
    ]
    with out_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerow({field: row.get(field, "") for field in fieldnames})
    return {
        "status": "product_license_decision_operator_intake_written",
        "operator_intake_csv": str(out_csv),
        "decision": row["decision"],
        "approval_token_required": APPROVAL_TOKEN,
        "spdx_license_id": row["spdx_license_id"],
        "license_text_source": row["license_text_source"],
        "copyright_holder": row["copyright_holder"],
        "effective_year": row["effective_year"],
        "license_file_written": False,
        "external_state_mutated": False,
        "next_command": (
            "python3 tools/build_product_license_decision_gate.py && "
            "python3 tools/build_product_license_file_creation_work_order.py"
        ),
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Write an operator-approved product license decision intake CSV.")
    parser.add_argument("--approval-token", required=True)
    parser.add_argument("--spdx-license-id", required=True, choices=ALLOWED_LICENSE_IDS)
    parser.add_argument("--license-text-source", required=True)
    parser.add_argument("--copyright-holder", required=True)
    parser.add_argument("--effective-year", required=True)
    parser.add_argument("--notes", default="")
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--force", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> dict[str, Any]:
    args = parse_args(argv)
    row = build_license_decision_intake_row(
        approval_token=args.approval_token,
        spdx_license_id=args.spdx_license_id,
        license_text_source=args.license_text_source,
        copyright_holder=args.copyright_holder,
        effective_year=args.effective_year,
        notes=args.notes,
    )
    result = write_license_decision_intake(out_csv=args.out_csv, row=row, force=args.force)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return result


if __name__ == "__main__":
    main()

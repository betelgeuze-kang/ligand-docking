#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

FAMILY_DEFAULTS: dict[str, dict[str, str]] = {
    "ca2": {
        "workbook_csv": "runs/ca2_packet_replacement_workbook_current.csv",
        "sheet_csv": "runs/ca2_binding_verification_sheet_current.csv",
        "out_json": "runs/ca2_verified_binding_promotion_current.json",
        "out_csv": "runs/ca2_verified_binding_promotion_current.csv",
        "out_md": "runs/ca2_verified_binding_promotion_current.md",
        "title": "CA2 Verified Binding Promotion",
        "required_fields": [
            "replacement_ligand_id",
            "replacement_reference_binding_kcal_mol",
            "replacement_source",
            "replacement_smiles",
            "replacement_scaffold",
        ],
    },
    "pxr": {
        "workbook_csv": "runs/pxr_packet_replacement_workbook_current.csv",
        "sheet_csv": "runs/pxr_binding_verification_sheet_current.csv",
        "out_json": "runs/pxr_verified_binding_promotion_current.json",
        "out_csv": "runs/pxr_verified_binding_promotion_current.csv",
        "out_md": "runs/pxr_verified_binding_promotion_current.md",
        "title": "PXR Verified Binding Promotion",
        "required_fields": [
            "replacement_ligand_id",
            "replacement_reference_binding_kcal_mol",
            "replacement_source",
            "replacement_smiles",
            "replacement_scaffold",
        ],
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


def _missing_fields(row: dict[str, Any], required_fields: list[str]) -> list[str]:
    return [field for field in required_fields if not str(row.get(field, "")).strip()]


def _append_note_once(note: str, suffix: str) -> str:
    base = " ".join(str(note or "").split())
    extra = " ".join(str(suffix or "").split())
    if not extra:
        return base
    if extra in base:
        return base
    if not base:
        return extra
    return f"{base} {extra}"


def build_payload(
    workbook_rows: list[dict[str, str]],
    sheet_rows: list[dict[str, str]],
    family: str,
) -> dict[str, Any]:
    required_fields = FAMILY_DEFAULTS[family]["required_fields"]
    sheet_by_step = {
        str(row.get("packet_step", "")).strip(): row
        for row in sheet_rows
        if str(row.get("verification_status", "")).strip().startswith("verified_")
        and str(row.get("replacement_is_binder", "")).strip() == "1"
        and str(row.get("verify_reference_binding_kcal_mol", "")).strip()
    }
    promoted_rows: list[dict[str, Any]] = []
    updated_workbook: list[dict[str, Any]] = []
    promoted_count = 0
    for workbook_row in workbook_rows:
        row = dict(workbook_row)
        packet_step = str(row.get("packet_step", "")).strip()
        verify = sheet_by_step.get(packet_step)
        if verify:
            row["replacement_reference_binding_kcal_mol"] = str(verify.get("verify_reference_binding_kcal_mol", "")).strip()
            row["replacement_source"] = str(verify.get("verify_provenance_source", "")).strip()
            source_url = str(verify.get("verify_source_url", "")).strip()
            suffix = f" Verified binder evidence promoted from verification sheet; source_url={source_url}".strip()
            row["notes"] = _append_note_once(str(row.get("notes", "")).strip(), suffix)
            promoted_count += 1
            promoted_rows.append(
                {
                    "packet_step": packet_step,
                    "replacement_ligand_id": str(row.get("replacement_ligand_id", "")).strip(),
                    "replacement_reference_binding_kcal_mol": str(row.get("replacement_reference_binding_kcal_mol", "")).strip(),
                    "replacement_source": str(row.get("replacement_source", "")).strip(),
                    "verify_source_url": source_url,
                    "verification_status": str(verify.get("verification_status", "")).strip(),
                }
            )
        missing = _missing_fields(row, required_fields)
        row["required_missing_fields"] = ",".join(missing)
        row["row_ready_for_apply"] = "yes" if not missing else "no"
        updated_workbook.append(row)
    summary = {
        "family": family,
        "workbook_row_count": len(updated_workbook),
        "promoted_row_count": promoted_count,
        "ready_row_count": sum(1 for row in updated_workbook if str(row.get("row_ready_for_apply", "")).strip().lower() == "yes"),
        "next_required_step": "Continue filling OOD binders and non-binders; promoted core binders are now ready for workbook apply review.",
    }
    return {
        "summary": summary,
        "promoted_rows": promoted_rows,
        "workbook_rows": updated_workbook,
    }


def _write_markdown(path: Path, payload: dict[str, Any], title: str) -> None:
    lines = [
        f"# {title}",
        "",
        f"- family: `{payload['summary']['family']}`",
        f"- promoted_row_count: `{payload['summary']['promoted_row_count']}`",
        f"- ready_row_count: `{payload['summary']['ready_row_count']}`",
        "",
        "## Next Step",
        "",
        f"- {payload['summary']['next_required_step']}",
        "",
        "## Promoted Rows",
        "",
        "| packet_step | replacement_ligand_id | replacement_reference_binding_kcal_mol |",
        "| --- | --- | ---: |",
    ]
    for row in payload["promoted_rows"]:
        lines.append(
            f"| {row['packet_step']} | `{row['replacement_ligand_id']}` | {row['replacement_reference_binding_kcal_mol']} |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Promote verified binder rows from verification sheets into authoritative workbooks.")
    parser.add_argument("--family", choices=sorted(FAMILY_DEFAULTS.keys()), required=True)
    parser.add_argument("--workbook-csv")
    parser.add_argument("--sheet-csv")
    parser.add_argument("--out-json")
    parser.add_argument("--out-csv")
    parser.add_argument("--out-md")
    parser.add_argument("--freeze-ready-ca2-packets", action=argparse.BooleanOptionalAction, default=False)
    args = parser.parse_args()
    defaults = FAMILY_DEFAULTS[args.family]
    for key in ("workbook_csv", "sheet_csv", "out_json", "out_csv", "out_md"):
        if not getattr(args, key):
            setattr(args, key, defaults[key])
    return args


def main() -> None:
    args = parse_args()
    workbook_csv = _resolve(args.workbook_csv)
    sheet_csv = _resolve(args.sheet_csv)
    workbook_rows = _read_csv(workbook_csv)
    sheet_rows = _read_csv(sheet_csv)
    payload = build_payload(workbook_rows, sheet_rows, args.family)
    _write_csv(workbook_csv, payload["workbook_rows"])
    if args.family == "ca2" and bool(args.freeze_ready_ca2_packets):
        from tools import ca2_packet_bridge as ca2_bridge

        freeze_result = ca2_bridge.materialize_ready_workbook_rows(payload["workbook_rows"], apply_changes=True)
        payload["ca2_freeze_summary"] = freeze_result.get("summary", {})
    out_json = _resolve(args.out_json)
    out_csv = _resolve(args.out_csv)
    out_md = _resolve(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    _write_csv(out_csv, payload["promoted_rows"])
    _write_markdown(out_md, payload, FAMILY_DEFAULTS[args.family]["title"])


if __name__ == "__main__":
    main()

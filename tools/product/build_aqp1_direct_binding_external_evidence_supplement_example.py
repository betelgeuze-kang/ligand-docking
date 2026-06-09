#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]
RUNS = Path("runs")

DEFAULT_GUIDE_JSON = RUNS / "aqp1_direct_binding_external_evidence_operator_fill_guide_current.json"
DEFAULT_OUT_JSON = RUNS / "aqp1_direct_binding_external_evidence_supplement_example_current.json"
DEFAULT_OUT_CSV = RUNS / "aqp1_direct_binding_external_evidence_intake_supplement_example_current.csv"
DEFAULT_OUT_MD = RUNS / "aqp1_direct_binding_external_evidence_supplement_example_current.md"

EXAMPLE_NOTE_PREFIX = "EXAMPLE_ILLUSTRATIVE_ONLY"
ILLUSTRATIVE_KD_NM = "1200"
ILLUSTRATIVE_KCAL = "-8.19"
ILLUSTRATIVE_SOURCE = "https://pubmed.ncbi.nlm.nih.gov/EXAMPLE_REPLACE_WITH_PRIMARY_PMID/"


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _read_json(path_like: str | Path) -> dict[str, Any]:
    path = _resolve(path_like)
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _text(value: Any) -> str:
    return str(value or "").strip()


def build_example_rows(template_rows: list[dict[str, Any]]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for template in template_rows:
        row = {key: _text(value) for key, value in template.items()}
        review_row_id = _text(row.get("review_row_id"))
        if review_row_id == "aqp1_external_direct_binding_core_binder_01":
            row.update(
                {
                    "replacement_reference_binding_kcal_mol": ILLUSTRATIVE_KCAL,
                    "direct_binding_method": "SPR",
                    "standard_type": "Kd",
                    "standard_value_nM": ILLUSTRATIVE_KD_NM,
                    "source_locator_or_raw_report": ILLUSTRATIVE_SOURCE,
                    "target_match_confirmed": "true",
                    "assay_is_direct_binding": "true",
                    "data_validity_accepted": "true",
                    "operator_claim_safe_decision": "APPROVE_CLAIM_SAFE",
                    "review_decision": "APPROVE",
                    "authoritative_apply_requested": "true",
                    "reviewer_notes": (
                        f"{EXAMPLE_NOTE_PREFIX}: Illustrative only. Replace PMID/DOI and numeric Kd/Ki with a "
                        f"verified exact human AQP1 (P29972) direct-binding primary report before copying into "
                        f"runs/aqp1_direct_binding_external_evidence_intake_supplement_current.csv. "
                        f"Functional surrogate kcal ({_text(row.get('functional_surrogate_kcal_mol')) or '-6.47'}) "
                        "must not be promoted to replacement_reference_binding_kcal_mol."
                    ),
                }
            )
        elif review_row_id == "aqp1_operator_validation_chembl20_acetazolamide":
            row["reviewer_notes"] = (
                f"{EXAMPLE_NOTE_PREFIX}: KEEP_BLOCKED example. Do not upgrade CHEMBL20 unless operator confirms "
                "exact human AQP1 direct-binding provenance and assay validity."
            )
        else:
            row["reviewer_notes"] = (
                f"{EXAMPLE_NOTE_PREFIX}: Optional alternate binder path. Fill only if bacopaside II direct binding "
                "cannot be sourced; otherwise KEEP_BLOCKED."
            )
        rows.append(row)
    return rows


def build_payload(guide_payload: dict[str, Any]) -> dict[str, Any]:
    template_rows = [
        dict(row) for row in guide_payload.get("rows", []) or [] if isinstance(row, dict)
    ]
    example_rows = build_example_rows(template_rows)
    summary = {
        "packet_type": "aqp1_direct_binding_external_evidence_supplement_example",
        "status": (
            "aqp1_direct_binding_external_evidence_supplement_example_ready"
            if example_rows
            else "blocked_aqp1_direct_binding_external_evidence_supplement_example"
        ),
        "example_row_count": len(example_rows),
        "illustrative_claim_safe_row_id": "aqp1_external_direct_binding_core_binder_01",
        "illustrative_kd_nM": ILLUSTRATIVE_KD_NM,
        "illustrative_kcal_mol": ILLUSTRATIVE_KCAL,
        "example_note_prefix": EXAMPLE_NOTE_PREFIX,
        "operator_copy_target_csv": "runs/aqp1_direct_binding_external_evidence_intake_supplement_current.csv",
        "next_required_step": (
            "Review the example CSV/MD, replace EXAMPLE_* placeholders with verified primary evidence, "
            "copy approved rows into the live supplement CSV, then run build_aqp1_direct_binding_external_evidence_intake.py "
            "and apply_aqp1_ready_workbook_rows.py."
            if example_rows
            else "Regenerate the operator fill guide before building the supplement example."
        ),
    }
    return {"summary": summary, "rows": example_rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# AQP1 Direct Binding Supplement CSV — Operator Example",
        "",
        f"- status: `{summary['status']}`",
        f"- example_row_count: `{summary['example_row_count']}`",
        f"- illustrative_kd_nM: `{summary['illustrative_kd_nM']}`",
        f"- illustrative_kcal_mol: `{summary['illustrative_kcal_mol']}`",
        "",
        "## Important",
        "",
        f"- This file is **{summary['example_note_prefix']}** documentation only.",
        f"- Do **not** run intake against `{path.name}` directly.",
        f"- Copy verified rows into `{summary['operator_copy_target_csv']}` after replacing example PMID/Kd values.",
        "- Never copy functional IC50-derived surrogate kcal into `replacement_reference_binding_kcal_mol`.",
        "",
        "## How to fill the live supplement CSV",
        "",
        "1. Open `runs/aqp1_direct_binding_external_evidence_intake_supplement_current.csv`.",
        "2. For bacopaside II (`aqp1_external_direct_binding_core_binder_01`), either:",
        "   - **KEEP_BLOCKED**: leave `replacement_reference_binding_kcal_mol` blank / `KEEP_BLOCKED`.",
        "   - **APPROVE_CLAIM_SAFE**: fill exact human AQP1 direct Kd/Ki, primary PMID/DOI, and set all boolean review fields to `true`.",
        "3. Example numeric mapping (illustrative only): Kd = 1200 nM → ΔG ≈ -8.19 kcal/mol at 298 K.",
        "4. Rerun:",
        "   - `python3 tools/product/build_aqp1_direct_binding_external_evidence_intake.py`",
        "   - `python3 tools/product/build_aqp1_packet_replacement_workbook.py`",
        "   - `python3 tools/product/apply_aqp1_ready_workbook_rows.py --no-write-config` (preview)",
        "",
        "## Example rows",
        "",
        "| review_row_id | review_decision | kcal | operator_claim_safe_decision |",
        "| --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['review_row_id']}` | `{row['review_decision']}` | "
            f"`{row['replacement_reference_binding_kcal_mol']}` | `{row['operator_claim_safe_decision']}` |"
        )
    lines.extend(["", "## Next Step", "", f"- {summary['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build illustrative AQP1 external direct-binding supplement CSV example for operators."
    )
    parser.add_argument("--guide-json", default=str(DEFAULT_GUIDE_JSON))
    parser.add_argument("--out-json", default=str(DEFAULT_OUT_JSON))
    parser.add_argument("--out-csv", default=str(DEFAULT_OUT_CSV))
    parser.add_argument("--out-md", default=str(DEFAULT_OUT_MD))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(_read_json(args.guide_json))
    _write_json(args.out_json, payload)
    write_csv_rows(_resolve(args.out_csv), payload["rows"])
    _write_markdown(_resolve(args.out_md), payload)


if __name__ == "__main__":
    main()

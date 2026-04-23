#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

FAMILY_SPECS: dict[str, dict[str, Any]] = {
    "ca2": {
        "target": "CARBONIC_ANHYDRASE_2_ZN_BLIND",
        "default_replacement_csv": "runs/ca2_packet_replacement_workbook_current.csv",
        "default_target_csv": "config/real_drug_targets_blind_ca2_zn_v1.csv",
        "default_out_json": "runs/ca2_curated_candidate_source_seed_current.json",
        "default_out_csv": "runs/ca2_curated_candidate_source_seed_current.csv",
        "default_out_md": "runs/ca2_curated_candidate_source_seed_current.md",
        "family_title": "CA2 Curated Candidate Source Seed",
        "family_note": "Seed-only CA2 candidate list. Use these rows to start curation; verify ligand identity, binding values, and provenance before applying them to the packet.",
        "candidates": {
            "core_binder_01": ("acetazolamide", "known_ca2_inhibitor_seed", "Classical CA2 sulfonamide inhibitor; good first core binder anchor."),
            "core_binder_02": ("methazolamide", "known_ca2_inhibitor_seed", "Classical CA2 sulfonamide inhibitor; good second core binder anchor."),
            "core_binder_03": ("ethoxzolamide", "known_ca2_inhibitor_seed", "Classical CA2 sulfonamide inhibitor; good third core binder anchor."),
            "core_non_binder_01": ("acetaminophen", "generic_negative_seed", "Generic small-molecule negative seed; verify before apply."),
            "core_non_binder_02": ("metformin", "generic_negative_seed", "Generic small-molecule negative seed; verify before apply."),
            "core_non_binder_03": ("caffeine", "generic_negative_seed", "Preferred local negative seed; verify that it remains an acceptable CA2 non-binder."),
            "ood_binder_01": ("dorzolamide", "known_ca2_inhibitor_seed", "Drug-like CA inhibitor candidate for expanded-OOD binder slot."),
            "ood_binder_02": ("brinzolamide", "known_ca2_inhibitor_seed", "Drug-like CA inhibitor candidate for expanded-OOD binder slot."),
            "ood_binder_03": ("chlorzolamide", "known_ca2_inhibitor_seed", "Classical CA inhibitor candidate for expanded-OOD binder slot."),
            "ood_non_binder_01": ("aspirin", "generic_negative_seed", "Generic expanded-OOD negative seed; verify before apply."),
            "ood_non_binder_02": ("ibuprofen", "generic_negative_seed", "Generic expanded-OOD negative seed; verify before apply."),
            "ood_non_binder_03": ("caffeine", "generic_negative_seed", "Preferred local negative seed; verify that it remains an acceptable CA2 non-binder."),
        },
    },
    "pxr": {
        "target": "PXR_NR1I2_BLIND",
        "default_replacement_csv": "runs/pxr_packet_replacement_workbook_current.csv",
        "default_target_csv": "config/real_drug_targets_blind_pxr_nr1i2_v1.csv",
        "default_out_json": "runs/pxr_curated_candidate_source_seed_current.json",
        "default_out_csv": "runs/pxr_curated_candidate_source_seed_current.csv",
        "default_out_md": "runs/pxr_curated_candidate_source_seed_current.md",
        "family_title": "PXR Curated Candidate Source Seed",
        "family_note": "Seed-only PXR candidate list. These suggestions are family-specific starting points; they still require manual ligand verification and source curation before packet apply.",
        "candidates": {
            "core_eval_non_binder_01": ("acetaminophen", "template_negative_seed", "Template-style negative seed from existing local proxy families; verify that it is acceptable as a PXR non-binder."),
            "core_eval_non_binder_02": ("caffeine", "template_negative_seed", "Template-style negative seed from existing local proxy families; verify before apply."),
            "core_eval_binder_01": ("rifampicin", "known_pxr_ligand_seed", "Canonical human PXR agonist/ligand seed for core eval binder slot."),
            "core_eval_binder_02": ("clotrimazole", "known_pxr_ligand_seed", "Known human PXR ligand seed for core eval binder slot."),
            "core_fit_binder_01": ("hyperforin", "known_pxr_ligand_seed", "Known human PXR ligand seed for core fit binder slot."),
            "core_fit_binder_02": ("ketoconazole", "known_pxr_ligand_seed", "Known human PXR ligand seed for core fit binder slot."),
            "ood_fit_binder_01": ("bexarotene", "known_pxr_ligand_seed", "Expanded-OOD binder seed for PXR."),
            "ood_fit_binder_02": ("sr12813", "known_pxr_ligand_seed", "Expanded-OOD binder seed for PXR."),
            "ood_eval_non_binder_01": ("nicotinamide", "template_negative_seed", "Template-style negative seed from existing local proxy families; verify before apply."),
            "ood_eval_non_binder_02": ("ibuprofen", "template_negative_seed", "Template-style negative seed from existing local proxy families; verify before apply."),
            "ood_eval_non_binder_03": ("aspirin", "template_negative_seed", "Template-style negative seed from existing local proxy families; verify before apply."),
            "ood_eval_binder_01": ("nifedipine", "known_pxr_ligand_seed", "Expanded-OOD binder seed for PXR."),
            "ood_eval_binder_02": ("troglitazone", "known_pxr_ligand_seed", "Expanded-OOD binder seed for PXR."),
            "ood_eval_binder_03": ("dexamethasone", "known_pxr_ligand_seed", "Expanded-OOD binder seed for PXR."),
        },
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


def _target_anchor(target_csv: Path, target: str) -> dict[str, str]:
    for row in _read_csv(target_csv):
        if str(row.get("target", "")).strip() == target:
            return row
    return {}


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    spec = FAMILY_SPECS[args.family]
    replacement_rows = _read_csv(_resolve(args.replacement_csv))
    target_row = _target_anchor(_resolve(args.target_csv), spec["target"])
    target_anchor_path = str(target_row.get("native_pdb_path", "")).strip()
    target_anchor_pdb = str(target_row.get("pdb_id", "")).strip()

    helper_rows: list[dict[str, Any]] = []
    assigned = 0
    missing = 0
    for row in replacement_rows:
        packet_step = str(row.get("packet_step", "")).strip()
        candidate_name, candidate_kind, candidate_note = spec["candidates"].get(
            packet_step,
            ("", "missing_seed", "No family-specific seed has been assigned for this slot yet."),
        )
        if candidate_name:
            assigned += 1
        else:
            missing += 1
        helper_rows.append(
            {
                "packet": str(row.get("packet", "")).strip(),
                "packet_step": packet_step,
                "target": spec["target"],
                "current_ligand_id": str(row.get("current_ligand_id", "")).strip(),
                "candidate_ligand_name": candidate_name,
                "candidate_source_kind": candidate_kind,
                "candidate_reference_hint": candidate_note,
                "target_anchor_pdb_id": target_anchor_pdb,
                "target_anchor_native_path": target_anchor_path,
                "candidate_status": "suggested_not_applied",
                "manual_verification_required": "yes",
                "next_action": "Verify ligand evidence and binding value, then copy into the replacement workbook fields before apply.",
            }
        )

    summary = {
        "family": args.family,
        "target": spec["target"],
        "replacement_row_count": len(replacement_rows),
        "candidate_seed_row_count": len(helper_rows),
        "assigned_candidate_count": assigned,
        "missing_candidate_count": missing,
        "target_anchor_pdb_id": target_anchor_pdb,
        "target_anchor_native_path": target_anchor_path,
        "next_required_step": "Use these rows as candidate-source seeds only. Manually verify ligand identity, provenance, and binding values before copying them into the replacement workbook.",
    }
    return {"summary": summary, "helper_rows": helper_rows}


def _write_markdown(path: Path, payload: dict[str, Any], family_title: str, family_note: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    summary = payload["summary"]
    lines = [
        f"# {family_title}",
        "",
        f"- target: `{summary['target']}`",
        f"- candidate_seed_row_count: `{summary['candidate_seed_row_count']}`",
        f"- assigned_candidate_count: `{summary['assigned_candidate_count']}`",
        f"- missing_candidate_count: `{summary['missing_candidate_count']}`",
        f"- target_anchor_pdb_id: `{summary['target_anchor_pdb_id']}`",
        "",
        "## Note",
        "",
        f"- {family_note}",
        "",
        "## Next Step",
        "",
        f"- {summary['next_required_step']}",
        "",
        "## Candidate Rows",
        "",
        "| packet_step | current_ligand_id | candidate_ligand_name | candidate_source_kind | manual_verification_required |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in payload["helper_rows"]:
        lines.append(
            f"| {row['packet_step']} | `{row['current_ligand_id']}` | `{row['candidate_ligand_name']}` | {row['candidate_source_kind']} | {row['manual_verification_required']} |"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build family-specific candidate-source seed rows for CA2 or PXR replacement workbooks.")
    parser.add_argument("--family", choices=sorted(FAMILY_SPECS.keys()), required=True)
    parser.add_argument("--replacement-csv")
    parser.add_argument("--target-csv")
    parser.add_argument("--out-json")
    parser.add_argument("--out-csv")
    parser.add_argument("--out-md")
    args = parser.parse_args()
    spec = FAMILY_SPECS[args.family]
    if not args.replacement_csv:
        args.replacement_csv = spec["default_replacement_csv"]
    if not args.target_csv:
        args.target_csv = spec["default_target_csv"]
    if not args.out_json:
        args.out_json = spec["default_out_json"]
    if not args.out_csv:
        args.out_csv = spec["default_out_csv"]
    if not args.out_md:
        args.out_md = spec["default_out_md"]
    return args


def main() -> None:
    args = parse_args()
    spec = FAMILY_SPECS[args.family]
    payload = build_payload(args)
    out_json = _resolve(args.out_json)
    out_csv = _resolve(args.out_csv)
    out_md = _resolve(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    _write_csv(out_csv, payload["helper_rows"])
    _write_markdown(out_md, payload, spec["family_title"], spec["family_note"])


if __name__ == "__main__":
    main()

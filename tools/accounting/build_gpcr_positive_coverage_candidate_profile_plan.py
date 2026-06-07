#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
from typing import Any

from tools.lib.artifacts import artifact as _artifact
from tools.lib.artifacts import read_csv as _read_csv
from tools.lib.artifacts import resolve as _resolve
from tools.lib.artifacts import text as _text
from tools.lib.artifacts import truthy as _truthy
from tools.lib.artifacts import write_csv as _write_csv
from tools.lib.artifacts import write_json as _write_json

DEFAULT_BASE_REFERENCE_CSV = "runs/gpcr_frozen_candidate_profile_support_current/candidate_reference.csv"
DEFAULT_BASE_SPLITS_CSV = "runs/gpcr_frozen_candidate_profile_support_current/candidate_splits.csv"
DEFAULT_APPEND_REFERENCE_CSV = "runs/gpcr_positive_coverage_candidate_reference_append_current.csv"
DEFAULT_APPEND_SPLITS_CSV = "runs/gpcr_positive_coverage_candidate_splits_append_current.csv"
DEFAULT_OUT_DIR = "runs/gpcr_positive_coverage_candidate_profile_build_plan_current"


def _key(row: dict[str, Any]) -> tuple[str, str]:
    return (_text(row.get("target")), _text(row.get("ligand_id")))


def _key_label(key: tuple[str, str]) -> str:
    target, ligand_id = key
    return f"{target}:{ligand_id}"


def _find_duplicate_keys(rows: list[dict[str, Any]]) -> set[tuple[str, str]]:
    seen: set[tuple[str, str]] = set()
    duplicates: set[tuple[str, str]] = set()
    for row in rows:
        key = _key(row)
        if not all(key):
            continue
        if key in seen:
            duplicates.add(key)
        seen.add(key)
    return duplicates


def _missing_required(row: dict[str, Any], required: list[str]) -> list[str]:
    return [name for name in required if _text(row.get(name)) == ""]


def _with_origin(rows: list[dict[str, Any]], origin: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in rows:
        copied = dict(row)
        copied["build_row_origin"] = origin
        out.append(copied)
    return out


def _positive_count(rows: list[dict[str, Any]]) -> int:
    return sum(1 for row in rows if _truthy(row.get("is_binder")))


def _render_md(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# GPCR Positive Coverage Candidate Profile Build Plan",
        "",
        f"- status: `{summary['status']}`",
        f"- projected_reference_row_count: `{summary['projected_reference_row_count']}`",
        f"- projected_split_row_count: `{summary['projected_split_row_count']}`",
        f"- projected_positive_count: `{summary['projected_positive_count']}`",
        f"- append_far_ood_eval_row_count: `{summary['append_far_ood_eval_row_count']}`",
        f"- claim_promotion_allowed: `{str(summary['claim_promotion_allowed']).lower()}`",
        f"- scorer_apply_allowed: `{str(summary['scorer_apply_allowed']).lower()}`",
        "",
        "## Artifacts",
        "",
        f"- projected_reference_csv: `{summary['projected_reference_csv']}`",
        f"- projected_splits_csv: `{summary['projected_splits_csv']}`",
        "",
        "## Gates",
        "",
    ]
    for name, value in payload["quality_gates"].items():
        lines.append(f"- {name}: `{str(value).lower()}`")
    if payload["blockers"]:
        lines.extend(["", "## Blockers", ""])
        lines.extend(f"- `{blocker}`" for blocker in payload["blockers"])
    lines.extend(["", "## Required Next Artifacts", ""])
    lines.extend(f"- {item}" for item in payload["required_next_artifacts"])
    lines.extend(["", "## Claim Boundary", "", summary["claim_boundary_note"], ""])
    return "\n".join(lines)


def build_plan(
    *,
    base_reference_csv: str | Path = DEFAULT_BASE_REFERENCE_CSV,
    base_splits_csv: str | Path = DEFAULT_BASE_SPLITS_CSV,
    append_reference_csv: str | Path = DEFAULT_APPEND_REFERENCE_CSV,
    append_splits_csv: str | Path = DEFAULT_APPEND_SPLITS_CSV,
    out_dir: str | Path = DEFAULT_OUT_DIR,
    generated_at_local: str | None = None,
) -> dict[str, Any]:
    base_reference_rows = _read_csv(base_reference_csv)
    base_split_rows = _read_csv(base_splits_csv)
    append_reference_rows = _read_csv(append_reference_csv)
    append_split_rows = _read_csv(append_splits_csv)

    blockers: list[str] = []
    if not base_reference_rows:
        blockers.append("missing_or_empty_base_reference_csv")
    if not base_split_rows:
        blockers.append("missing_or_empty_base_splits_csv")
    if not append_reference_rows:
        blockers.append("missing_or_empty_append_reference_csv")
    if not append_split_rows:
        blockers.append("missing_or_empty_append_splits_csv")

    base_reference_keys = {_key(row) for row in base_reference_rows if all(_key(row))}
    base_split_keys = {_key(row) for row in base_split_rows if all(_key(row))}
    append_reference_keys = {_key(row) for row in append_reference_rows if all(_key(row))}
    append_split_keys = {_key(row) for row in append_split_rows if all(_key(row))}

    for label, rows in [
        ("base_reference", base_reference_rows),
        ("base_splits", base_split_rows),
        ("append_reference", append_reference_rows),
        ("append_splits", append_split_rows),
    ]:
        for key in sorted(_find_duplicate_keys(rows)):
            blockers.append(f"{label}:duplicate_target_ligand:{_key_label(key)}")

    for row in append_reference_rows:
        key = _key(row)
        if not all(key):
            blockers.append("append_reference:missing_target_or_ligand_id")
            continue
        missing = _missing_required(
            row,
            [
                "reference_binding_kcal_mol",
                "is_binder",
                "canonical_smiles",
                "uniprot_accession",
                "structure_source_priority",
                "rcsb_first_hit",
            ],
        )
        if missing:
            blockers.append(f"append_reference:missing_required:{_key_label(key)}:{','.join(missing)}")
        if not _truthy(row.get("is_binder")):
            blockers.append(f"append_reference:not_positive_binder:{_key_label(key)}")
        if key in base_reference_keys:
            blockers.append(f"append_reference:already_in_base_reference:{_key_label(key)}")

    for row in append_split_rows:
        key = _key(row)
        if not all(key):
            blockers.append("append_splits:missing_target_or_ligand_id")
            continue
        role = _text(row.get("role"))
        leakage_policy = _text(row.get("leakage_policy"))
        if role != "far_ood_eval":
            blockers.append(f"append_splits:role_not_far_ood_eval:{_key_label(key)}:{role}")
        if leakage_policy != "do_not_fit_or_calibrate":
            blockers.append(f"append_splits:leakage_policy_not_locked:{_key_label(key)}:{leakage_policy}")
        if key in base_split_keys:
            blockers.append(f"append_splits:already_in_base_splits:{_key_label(key)}")

    missing_split_keys = sorted(append_reference_keys - append_split_keys)
    missing_reference_keys = sorted(append_split_keys - append_reference_keys)
    for key in missing_split_keys:
        blockers.append(f"append_splits:missing_for_reference:{_key_label(key)}")
    for key in missing_reference_keys:
        blockers.append(f"append_reference:missing_for_split:{_key_label(key)}")

    projected_reference_rows = _with_origin(base_reference_rows, "base_frozen_candidate_profile_support_current")
    projected_reference_rows.extend(_with_origin(append_reference_rows, "gpcr_positive_coverage_append_v1"))
    projected_split_rows = _with_origin(base_split_rows, "base_frozen_candidate_profile_support_current")
    projected_split_rows.extend(_with_origin(append_split_rows, "gpcr_positive_coverage_append_v1"))

    output_dir = _resolve(out_dir)
    projected_reference_csv = output_dir / "candidate_reference.csv"
    projected_splits_csv = output_dir / "candidate_splits.csv"
    out_json = output_dir / "build_plan.json"
    out_md = output_dir / "build_plan.md"

    append_far_ood_eval_count = sum(1 for row in append_split_rows if _text(row.get("role")) == "far_ood_eval")
    append_locked_count = sum(
        1 for row in append_split_rows if _text(row.get("leakage_policy")) == "do_not_fit_or_calibrate"
    )
    quality_gates = {
        "base_reference_and_split_keys_match": base_reference_keys == base_split_keys,
        "append_reference_and_split_keys_match": append_reference_keys == append_split_keys,
        "append_has_no_base_reference_overlap": not (append_reference_keys & base_reference_keys),
        "append_has_no_base_split_overlap": not (append_split_keys & base_split_keys),
        "append_roles_are_far_ood_eval": append_far_ood_eval_count == len(append_split_rows) and bool(append_split_rows),
        "append_leakage_policy_locked": append_locked_count == len(append_split_rows) and bool(append_split_rows),
        "projected_csvs_are_new_artifacts": _artifact(projected_reference_csv)
        != _artifact(base_reference_csv)
        and _artifact(projected_splits_csv) != _artifact(base_splits_csv),
    }

    status = (
        "gpcr_positive_coverage_candidate_profile_build_plan_ready"
        if not blockers and all(quality_gates.values())
        else "blocked_gpcr_positive_coverage_candidate_profile_build_plan"
    )
    summary = {
        "generated_at_local": generated_at_local or dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "status": status,
        "base_reference_csv": _artifact(base_reference_csv),
        "base_splits_csv": _artifact(base_splits_csv),
        "append_reference_csv": _artifact(append_reference_csv),
        "append_splits_csv": _artifact(append_splits_csv),
        "projected_reference_csv": _artifact(projected_reference_csv),
        "projected_splits_csv": _artifact(projected_splits_csv),
        "base_reference_row_count": len(base_reference_rows),
        "base_split_row_count": len(base_split_rows),
        "append_reference_row_count": len(append_reference_rows),
        "append_split_row_count": len(append_split_rows),
        "projected_reference_row_count": len(projected_reference_rows),
        "projected_split_row_count": len(projected_split_rows),
        "base_positive_count": _positive_count(base_reference_rows),
        "append_positive_count": _positive_count(append_reference_rows),
        "projected_positive_count": _positive_count(projected_reference_rows),
        "append_far_ood_eval_row_count": append_far_ood_eval_count,
        "append_locked_leakage_policy_row_count": append_locked_count,
        "blocker_count": len(blockers),
        "claim_promotion_allowed": False,
        "scorer_apply_allowed": False,
        "existing_frozen_current_mutated": False,
        "claim_boundary_note": (
            "This plan only materializes projected CSV inputs for a new frozen candidate-profile build. "
            "Append rows remain far_ood_eval and must not be used to fit, calibrate, relax thresholds, or promote claims."
        ),
    }
    payload = {
        "packet_type": "gpcr_positive_coverage_candidate_profile_build_plan",
        "summary": summary,
        "quality_gates": quality_gates,
        "blockers": blockers,
        "required_next_artifacts": [
            "matched decoy rows for every appended GPCR target-ligand pair",
            "trajectory or feature-cache rows generated from the projected candidate_reference.csv",
            "guarded 100k shadow review rerun with CI-low gate still enforced",
            "explicit proof that append rows were not used for fitting, calibration, or threshold selection",
        ],
        "claim_boundary": {
            "claim_promotion_allowed": False,
            "scorer_apply_allowed": False,
            "target_identity_feature_allowed": False,
            "threshold_relaxation_allowed": False,
            "append_rows_role": "far_ood_eval",
            "append_rows_leakage_policy": "do_not_fit_or_calibrate",
            "base_artifacts_are_read_only": True,
        },
    }

    _write_csv(projected_reference_csv, projected_reference_rows)
    _write_csv(projected_splits_csv, projected_split_rows)
    _write_json(out_json, payload)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text(_render_md(payload), encoding="utf-8")
    return payload


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a guarded GPCR positive coverage candidate-profile plan.")
    parser.add_argument("--base-reference-csv", default=DEFAULT_BASE_REFERENCE_CSV)
    parser.add_argument("--base-splits-csv", default=DEFAULT_BASE_SPLITS_CSV)
    parser.add_argument("--append-reference-csv", default=DEFAULT_APPEND_REFERENCE_CSV)
    parser.add_argument("--append-splits-csv", default=DEFAULT_APPEND_SPLITS_CSV)
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_plan(
        base_reference_csv=args.base_reference_csv,
        base_splits_csv=args.base_splits_csv,
        append_reference_csv=args.append_reference_csv,
        append_splits_csv=args.append_splits_csv,
        out_dir=args.out_dir,
    )
    print(json.dumps(payload["summary"], indent=2, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()

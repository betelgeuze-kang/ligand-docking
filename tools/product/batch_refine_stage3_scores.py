#!/usr/bin/env python3
"""Batch internal GB/SA physics refinement over local stage3 score CSVs."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[2]

from betelgeuze_engine.product.selection_score_authority import (
    SelectionScoreAuthority,
    load_authority_summary,
)
from betelgeuze_engine.product.implementation_provenance import (
    build_implementation_source_manifest,
    validate_implementation_source_manifest,
)
from betelgeuze_product.pocketmd_lite_contract import PocketMdAdmissionPolicy
from tools.product.build_refine_tier_residual_training_dataset import _refine_output_path


_BACKEND_ALIASES = {
    "deterministic_surrogate_wrapper_v1": "deterministic_surrogate_wrapper_v1",
    "internal_gb_sa": "internal_gb_sa_v1",
    "internal_gb_sa_v1": "internal_gb_sa_v1",
    "internal_full_stack": "internal_full_stack_v1",
    "internal_full_stack_v1": "internal_full_stack_v1",
}


def _normalize_backend(value: str) -> str:
    requested = str(value or "").strip().lower()
    normalized = _BACKEND_ALIASES.get(requested)
    if normalized is None:
        raise ValueError(f"unsupported refinement backend: {requested or '<empty>'}")
    return normalized


def _resolve(path: str | Path) -> Path:
    p = Path(path)
    return p if p.is_absolute() else ROOT / p


def _authority_summary_for_scores(scores_csv: Path) -> Path:
    suffix = "_scores.csv"
    if scores_csv.name.endswith(suffix):
        return scores_csv.with_name(
            f"{scores_csv.name[:-len(suffix)]}_summary.json"
        )
    return scores_csv.with_suffix(".summary.json")


def _validated_selection_authority(path: Path) -> dict[str, Any]:
    return SelectionScoreAuthority.from_mapping(
        load_authority_summary(str(path)),
        require_current=True,
    ).to_dict()


def _read_json_object(path: Path) -> Mapping[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, Mapping) else None


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _cached_refinement_matches(
    *,
    summary_json: Path,
    input_csv: Path,
    output_csv: Path,
    authority_summary_json: Path,
    selection_authority: Mapping[str, Any],
    backend: str,
    refinement_mode: str,
    refined_energy_col: str,
    topk_global: int,
    implementation_manifest: Mapping[str, Any],
) -> bool:
    payload = _read_json_object(summary_json)
    if not payload or payload.get("pass") is not True:
        return False
    try:
        cached_authority = SelectionScoreAuthority.from_mapping(
            payload.get("selection_score_authority", {}),
            require_current=True,
        ).to_dict()
        cached_policy = PocketMdAdmissionPolicy.from_mapping(
            payload.get("pocketmd_admission_policy", {})
        )
        cached_implementation = validate_implementation_source_manifest(
            payload.get("implementation_source_manifest", {})
        )
        expected_policy = PocketMdAdmissionPolicy.create(
            selection_policy_sha256=str(selection_authority.get("policy_sha256") or ""),
            selection_authority_schema_version=str(
                selection_authority.get("schema_version") or ""
            ),
            topk_global=topk_global,
            topk_per_target=0,
            selection_mode="union",
        )
    except ValueError:
        return False
    try:
        expected_fields = {
            "refinement_schema_version": "ligand_physics_refinement_v2",
            "refinement_backend": str(backend),
            "refinement_mode": str(refinement_mode),
            "scores_csv_in": str(input_csv),
            "scores_csv_in_sha256": _sha256_file(input_csv),
            "scores_csv_out": str(output_csv),
            "scores_csv_out_sha256": _sha256_file(output_csv),
            "selection_authority_summary_json": str(authority_summary_json),
            "selection_authority_summary_sha256": _sha256_file(
                authority_summary_json
            ),
            "refined_energy_col": str(refined_energy_col),
            "refined_rank_col": "binding_score_stronger_physics_v1",
            "selection_mode": "union",
            "topk_global_requested": int(topk_global),
            "topk_per_target_requested": 0,
        }
        fields_match = all(
            payload.get(key) == value for key, value in expected_fields.items()
        )
    except OSError:
        return False
    return bool(
        cached_authority == dict(selection_authority)
        and cached_policy.to_dict() == expected_policy.to_dict()
        and cached_implementation == dict(implementation_manifest)
        and payload.get("implementation_fingerprint_sha256")
        == implementation_manifest.get("manifest_sha256")
        and fields_match
    )


def batch_refine_stage3_scores(
    *,
    stage3_glob: str,
    backend: str = "internal_gb_sa_v1",
    refinement_mode: str = "implicit_gb_sa_v1",
    refined_energy_col: str = "deltaG_mm_gbsa_kcal_mol",
    topk_global: int = 128,
    skip_existing: bool = True,
    selection_authority_summary_json: str = "",
) -> dict[str, Any]:
    backend = _normalize_backend(backend)
    implementation_manifest = build_implementation_source_manifest()
    inputs = sorted(ROOT.glob(stage3_glob))
    rows: list[dict[str, Any]] = []
    for src in inputs:
        if "_refine_scores" in src.name:
            continue
        out_csv = _refine_output_path(src)
        authority_summary = (
            _resolve(selection_authority_summary_json)
            if str(selection_authority_summary_json or "").strip()
            else _authority_summary_for_scores(src)
        )
        if not authority_summary.is_file():
            rows.append(
                {
                    "input_csv": str(src),
                    "out_csv": str(out_csv),
                    "selection_authority_summary_json": str(authority_summary),
                    "status": "failed",
                    "returncode": None,
                    "stderr_tail": "selection authority summary is missing",
                }
            )
            continue
        try:
            selection_authority = _validated_selection_authority(authority_summary)
        except ValueError as exc:
            rows.append(
                {
                    "input_csv": str(src),
                    "out_csv": str(out_csv),
                    "selection_authority_summary_json": str(authority_summary),
                    "status": "failed",
                    "returncode": None,
                    "stderr_tail": f"invalid selection authority summary: {exc}",
                }
            )
            continue
        out_summary_json = out_csv.with_suffix(".summary.json")
        if (
            skip_existing
            and out_csv.exists()
            and out_summary_json.exists()
            and min(
                out_csv.stat().st_mtime,
                out_summary_json.stat().st_mtime,
            )
            >= max(src.stat().st_mtime, authority_summary.stat().st_mtime)
            and _cached_refinement_matches(
                summary_json=out_summary_json,
                input_csv=src,
                output_csv=out_csv,
                authority_summary_json=authority_summary,
                selection_authority=selection_authority,
                backend=backend,
                refinement_mode=refinement_mode,
                refined_energy_col=refined_energy_col,
                topk_global=int(topk_global),
                implementation_manifest=implementation_manifest,
            )
        ):
            rows.append(
                {
                    "input_csv": str(src),
                    "out_csv": str(out_csv),
                    "selection_authority_summary_json": str(authority_summary),
                    "status": "skipped_existing",
                }
            )
            continue
        cmd = [
            sys.executable,
            str(ROOT / "tools/run_ligand_physics_refinement.py"),
            "--scores-csv",
            str(src),
            "--selection-authority-summary-json",
            str(authority_summary),
            "--backend",
            str(backend),
            "--refinement-mode",
            str(refinement_mode),
            "--refined-energy-col",
            str(refined_energy_col),
            "--topk-global",
            str(int(topk_global)),
            "--topk-per-target",
            "0",
            "--selection-mode",
            "union",
            "--out-csv",
            str(out_csv),
            "--out-json",
            str(out_summary_json),
        ]
        proc = subprocess.run(cmd, cwd=str(ROOT), text=True, capture_output=True)
        output_valid = bool(
            proc.returncode == 0
            and out_csv.is_file()
            and out_summary_json.is_file()
            and _cached_refinement_matches(
                summary_json=out_summary_json,
                input_csv=src,
                output_csv=out_csv,
                authority_summary_json=authority_summary,
                selection_authority=selection_authority,
                backend=backend,
                refinement_mode=refinement_mode,
                refined_energy_col=refined_energy_col,
                topk_global=int(topk_global),
                implementation_manifest=implementation_manifest,
            )
        )
        ok = proc.returncode == 0 and output_valid
        stderr_tail = "\n".join((proc.stderr or "").splitlines()[-8:])
        if proc.returncode == 0 and not output_valid:
            stderr_tail = "refinement output failed cache/evidence validation"
        rows.append(
            {
                "input_csv": str(src),
                "out_csv": str(out_csv),
                "selection_authority_summary_json": str(authority_summary),
                "status": "refined" if ok else "failed",
                "returncode": int(proc.returncode),
                "stderr_tail": stderr_tail,
            }
        )
    refined = sum(1 for row in rows if row.get("status") == "refined")
    skipped = sum(1 for row in rows if row.get("status") == "skipped_existing")
    failed = sum(1 for row in rows if row.get("status") == "failed")
    return {
        "status": "batch_refine_stage3_ready" if failed == 0 else "blocked_batch_refine_stage3",
        "stage3_glob": stage3_glob,
        "input_count": len(inputs),
        "refined_count": refined,
        "skipped_existing_count": skipped,
        "failed_count": failed,
        "rows": rows,
    }


def main() -> None:
    p = argparse.ArgumentParser(description="Batch refine stage3 score CSVs with internal GB/SA backend.")
    p.add_argument("--stage3-glob", default="runs/ligand_htvs_nightly_*_stage3_scores.csv")
    p.add_argument(
        "--backend",
        default="internal_gb_sa_v1",
        choices=sorted(_BACKEND_ALIASES),
    )
    p.add_argument("--refinement-mode", default="implicit_gb_sa_v1")
    p.add_argument("--refined-energy-col", default="deltaG_mm_gbsa_kcal_mol")
    p.add_argument("--topk-global", type=int, default=128)
    p.add_argument("--selection-authority-summary-json", default="")
    p.add_argument("--no-skip-existing", action="store_true")
    args = p.parse_args()
    summary = batch_refine_stage3_scores(
        stage3_glob=args.stage3_glob,
        backend=args.backend,
        refinement_mode=args.refinement_mode,
        refined_energy_col=args.refined_energy_col,
        topk_global=int(args.topk_global),
        skip_existing=not bool(args.no_skip_existing),
        selection_authority_summary_json=str(args.selection_authority_summary_json),
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    if summary.get("failed_count"):
        raise SystemExit(1)


if __name__ == "__main__":
    main()

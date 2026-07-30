from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from betelgeuze_engine.product.selection_score_authority import SelectionScoreAuthority
from betelgeuze_engine.product.implementation_provenance import (
    HTVS_IMPLEMENTATION_SOURCE_PATHS,
    validate_implementation_source_manifest,
)
import tools.run_ligand_physics_refinement as refinement_module
from tools.run_ligand_physics_refinement import build_parser, run_refinement


def _write_authority(path: Path) -> dict:
    authority = SelectionScoreAuthority.create(
        score_column="binding_score_composite_v7",
        score_direction="ascending",
    ).to_dict()
    path.write_text(
        json.dumps({"selection_score_authority": authority}),
        encoding="utf-8",
    )
    return authority


def _args(tmp_path: Path, scores: Path, authority: Path, *extra: str):
    return build_parser().parse_args(
        [
            "--scores-csv",
            str(scores),
            "--selection-authority-summary-json",
            str(authority),
            "--topk-global",
            "1",
            "--topk-per-target",
            "0",
            "--admission-rank-threshold-pct",
            "1.0",
            "--out-csv",
            str(tmp_path / "refined.csv"),
            "--out-json",
            str(tmp_path / "summary.json"),
            "--out-md",
            str(tmp_path / "summary.md"),
            "--out-shortlist-csv",
            str(tmp_path / "shortlist.csv"),
            "--out-shortlist-json",
            str(tmp_path / "shortlist.json"),
            *extra,
        ]
    )


def test_declared_v7_authority_controls_admission_and_excludes_primary_nan(tmp_path: Path) -> None:
    scores = tmp_path / "scores.csv"
    pd.DataFrame(
        [
            {
                "target": "ADRB2",
                "family": "gpcr",
                "ligand_id": "v7_winner",
                "binding_score_composite_v7": -9.0,
                "binding_score_composite_v3": -1.0,
                "binding_energy_mmpbsa_kcal_mol_proxy": -7.0,
            },
            {
                "target": "ADRB2",
                "family": "gpcr",
                "ligand_id": "v3_winner",
                "binding_score_composite_v7": -1.0,
                "binding_score_composite_v3": -9.0,
                "binding_energy_mmpbsa_kcal_mol_proxy": -8.0,
            },
            {
                "target": "ADRB2",
                "family": "gpcr",
                "ligand_id": "primary_nan",
                "binding_score_composite_v7": None,
                "binding_score_composite_v3": -100.0,
                "binding_energy_mmpbsa_kcal_mol_proxy": -100.0,
            },
        ]
    ).to_csv(scores, index=False)
    authority_path = tmp_path / "authority.json"
    authority = _write_authority(authority_path)

    summary = run_refinement(_args(tmp_path, scores, authority_path))
    out = pd.read_csv(tmp_path / "refined.csv")

    assert summary["selection_score_authority"] == authority
    assert summary["selected_count"] == 1
    assert out.loc[out["pocketmd_admitted"] == 1, "ligand_id"].tolist() == ["v7_winner"]
    assert (
        out.loc[out["ligand_id"] == "primary_nan", "pocketmd_admission_reason"].iloc[0]
        == "primary_score_ineligible"
    )


def test_admission_enforces_target_job_and_budget_caps_in_authority_order(tmp_path: Path) -> None:
    scores = tmp_path / "scores.csv"
    pd.DataFrame(
        [
            {
                "target": target,
                "family": "gpcr",
                "ligand_id": ligand,
                "binding_score_composite_v7": score,
                "binding_energy_mmpbsa_kcal_mol_proxy": score,
            }
            for target, ligand, score in [
                ("A", "a1", -4.0),
                ("A", "a2", -3.0),
                ("B", "b1", -2.0),
                ("C", "c1", -1.0),
            ]
        ]
    ).to_csv(scores, index=False)
    authority_path = tmp_path / "authority.json"
    _write_authority(authority_path)
    args = _args(
        tmp_path,
        scores,
        authority_path,
        "--topk-global",
        "4",
        "--admission-max-per-target",
        "1",
        "--admission-max-per-job",
        "2",
        "--admission-cost-budget",
        "2",
    )

    summary = run_refinement(args)
    out = pd.read_csv(tmp_path / "refined.csv")

    assert out.loc[out["pocketmd_admitted"] == 1, "ligand_id"].tolist() == ["a1", "b1"]
    assert summary["selected_target_counts"] == {"A": 1, "B": 1}
    assert summary["admission_cost_used"] == 2.0
    assert summary["admission_reason_counts"]["target_cap_reached"] == 1
    assert summary["admission_reason_counts"]["job_cap_reached"] == 1


def test_missing_tampered_or_mismatched_authority_fails_closed(tmp_path: Path) -> None:
    scores = tmp_path / "scores.csv"
    pd.DataFrame(
        [
            {
                "target": "ADRB2",
                "family": "gpcr",
                "ligand_id": "lig",
                "binding_score_composite_v7": -1.0,
                "binding_score_composite_v3": -2.0,
                "binding_energy_mmpbsa_kcal_mol_proxy": -3.0,
            }
        ]
    ).to_csv(scores, index=False)
    authority_path = tmp_path / "authority.json"
    authority = _write_authority(authority_path)
    authority["source_stage"] = "tampered"
    authority_path.write_text(
        json.dumps({"selection_score_authority": authority}),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="policy_sha256 mismatch"):
        run_refinement(_args(tmp_path, scores, authority_path))

    _write_authority(authority_path)
    with pytest.raises(ValueError, match="does not match declared"):
        run_refinement(
            _args(
                tmp_path,
                scores,
                authority_path,
                "--score-col",
                "binding_score_composite_v3",
            )
        )


def test_small_population_refines_one_row_and_preserves_nonfinite_base_as_nan(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    scores = tmp_path / "scores.csv"
    pd.DataFrame(
        [
            {
                "target": "A",
                "family": "gpcr",
                "ligand_id": "winner",
                "binding_score_composite_v7": -3.0,
                "binding_energy_mmpbsa_kcal_mol_proxy": -3.0,
            },
            {
                "target": "A",
                "family": "gpcr",
                "ligand_id": "nonfinite_base",
                "binding_score_composite_v7": -2.0,
                "binding_energy_mmpbsa_kcal_mol_proxy": float("inf"),
            },
            {
                "target": "B",
                "family": "gpcr",
                "ligand_id": "tail",
                "binding_score_composite_v7": -1.0,
                "binding_energy_mmpbsa_kcal_mol_proxy": -1.0,
            },
        ]
    ).to_csv(scores, index=False)
    authority_path = tmp_path / "authority.json"
    authority = _write_authority(authority_path)
    calls: list[float] = []

    def fake_refinement_delta(**kwargs):
        calls.append(float(kwargs["base_proxy_kcal"]))
        return {"refinement_delta_kcal_mol": 0.5, "confidence": 0.8}

    monkeypatch.setattr(
        refinement_module,
        "mm_gbsa_refinement_delta",
        fake_refinement_delta,
    )
    args = _args(
        tmp_path,
        scores,
        authority_path,
        "--admission-rank-threshold-pct",
        "0.05",
        "--backend",
        "internal_gb_sa_v1",
    )
    summary = run_refinement(args)
    out = pd.read_csv(tmp_path / "refined.csv")

    assert summary["selected_count"] == 1
    assert calls == [-3.0]
    assert summary["pocketmd_admission_policy"]["selection_policy_sha256"] == authority["policy_sha256"]
    assert summary["pocketmd_admission_policy"]["topk_global"] == 1
    assert summary["pocketmd_admission_policy"]["topk_per_target"] == 0
    implementation = validate_implementation_source_manifest(
        summary["implementation_source_manifest"]
    )
    assert summary["implementation_fingerprint_sha256"] == implementation[
        "manifest_sha256"
    ]
    assert [item["path"] for item in implementation["files"]] == list(
        HTVS_IMPLEMENTATION_SOURCE_PATHS
    )
    assert (
        out["selection_score_authority_schema_version"].unique().tolist()
        == [authority["schema_version"]]
    )
    rejected = out.loc[out["ligand_id"] == "nonfinite_base"].iloc[0]
    assert "base_proxy_ineligible" in rejected["pocketmd_admission_reason_codes"]
    assert pd.isna(rejected["binding_energy_explicit_water_recheck_kcal_mol_proxy"])
    assert pd.isna(rejected["binding_score_stronger_physics_v1"])


def test_refinement_output_cannot_overwrite_authority_column(tmp_path: Path) -> None:
    scores = tmp_path / "scores.csv"
    pd.DataFrame(
        [
            {
                "target": "A",
                "family": "gpcr",
                "ligand_id": "lig",
                "binding_score_composite_v7": -1.0,
                "binding_energy_mmpbsa_kcal_mol_proxy": -1.0,
            }
        ]
    ).to_csv(scores, index=False)
    authority_path = tmp_path / "authority.json"
    _write_authority(authority_path)

    with pytest.raises(ValueError, match="overwrite input evidence"):
        run_refinement(
            _args(
                tmp_path,
                scores,
                authority_path,
                "--refined-rank-col",
                "binding_score_composite_v7",
            )
        )


def test_legacy_v1_authority_is_rejected_before_refinement_output(tmp_path: Path) -> None:
    scores = tmp_path / "scores.csv"
    pd.DataFrame(
        [
            {
                "target": "A",
                "family": "gpcr",
                "ligand_id": "lig",
                "binding_score_composite_v7": -1.0,
                "binding_energy_mmpbsa_kcal_mol_proxy": -1.0,
            }
        ]
    ).to_csv(scores, index=False)
    authority_path = tmp_path / "legacy_authority.json"
    authority_path.write_text(
        json.dumps(
            {
                "selection_score_authority": {
                    "score_column": "binding_score_composite_v7",
                    "score_version": "v7",
                    "score_direction": "ascending",
                    "residual_mode": "base",
                    "source_stage": "stage3_backmapping_scoring",
                    "fallback_used": False,
                    "policy_sha256": "e2858aea7dee99c09a2d7e31ea3db6d6e302c3b6c6ee14f418ebd2109d4a3a00",
                }
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="verification-only"):
        run_refinement(_args(tmp_path, scores, authority_path))
    assert not (tmp_path / "refined.csv").exists()


def test_unknown_backend_cannot_fall_back_to_surrogate(tmp_path: Path) -> None:
    scores = tmp_path / "scores.csv"
    pd.DataFrame(
        [
            {
                "target": "A",
                "family": "gpcr",
                "ligand_id": "lig",
                "binding_score_composite_v7": -1.0,
                "binding_energy_mmpbsa_kcal_mol_proxy": -1.0,
            }
        ]
    ).to_csv(scores, index=False)
    authority_path = tmp_path / "authority.json"
    _write_authority(authority_path)
    args = _args(tmp_path, scores, authority_path)
    args.backend = "internal_full_stack_v99"

    with pytest.raises(ValueError, match="unsupported refinement backend"):
        run_refinement(args)
    assert not (tmp_path / "refined.csv").exists()

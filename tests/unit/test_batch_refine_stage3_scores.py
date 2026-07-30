from __future__ import annotations

import json
from types import SimpleNamespace

from betelgeuze_engine.product.selection_score_authority import SelectionScoreAuthority
from betelgeuze_engine.product.implementation_provenance import (
    build_implementation_source_manifest,
)
from betelgeuze_product.pocketmd_lite_contract import PocketMdAdmissionPolicy
import tools.product.batch_refine_stage3_scores as batch_module


def _write_authority(path) -> dict:
    authority = SelectionScoreAuthority.create(
        score_column="binding_score_composite_v7",
        score_direction="ascending",
    ).to_dict()
    path.write_text(
        json.dumps({"selection_score_authority": authority}),
        encoding="utf-8",
    )
    return authority


def test_batch_refinement_passes_derived_authority_sidecar(tmp_path, monkeypatch) -> None:
    scores = tmp_path / "run_stage3_scores.csv"
    scores.write_text("target,ligand_id\nA,L1\n", encoding="utf-8")
    authority = tmp_path / "run_stage3_summary.json"
    _write_authority(authority)
    commands: list[list[str]] = []

    def fake_run(cmd, **_kwargs):
        commands.append(list(cmd))
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(batch_module, "ROOT", tmp_path)
    monkeypatch.setattr(batch_module.subprocess, "run", fake_run)

    summary = batch_module.batch_refine_stage3_scores(
        stage3_glob="*_stage3_scores.csv",
        skip_existing=False,
    )

    assert summary["failed_count"] == 1
    assert commands
    option_index = commands[0].index("--selection-authority-summary-json")
    assert commands[0][option_index + 1] == str(authority)
    assert commands[0][commands[0].index("--topk-per-target") + 1] == "0"


def test_batch_refinement_does_not_skip_unvalidated_cached_output(tmp_path, monkeypatch) -> None:
    scores = tmp_path / "run_stage3_scores.csv"
    scores.write_text("target,ligand_id\nA,L1\n", encoding="utf-8")
    authority = tmp_path / "run_stage3_summary.json"
    _write_authority(authority)
    out_csv = tmp_path / "run_stage3_refine_scores.csv"
    out_csv.write_text("stale\n", encoding="utf-8")
    out_csv.with_suffix(".summary.json").write_text(
        json.dumps({"pass": True, "refinement_schema_version": "legacy"}),
        encoding="utf-8",
    )
    commands: list[list[str]] = []

    def fake_run(cmd, **_kwargs):
        commands.append(list(cmd))
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(batch_module, "ROOT", tmp_path)
    monkeypatch.setattr(batch_module.subprocess, "run", fake_run)

    summary = batch_module.batch_refine_stage3_scores(
        stage3_glob="*_stage3_scores.csv",
        skip_existing=True,
    )

    assert summary["refined_count"] == 0
    assert summary["skipped_existing_count"] == 0
    assert summary["failed_count"] == 1
    assert commands


def test_batch_refinement_skips_only_matching_hash_bound_cache(tmp_path, monkeypatch) -> None:
    scores = tmp_path / "run_stage3_scores.csv"
    scores.write_text("target,ligand_id\nA,L1\n", encoding="utf-8")
    authority_path = tmp_path / "run_stage3_summary.json"
    authority = _write_authority(authority_path)
    out_csv = tmp_path / "run_stage3_refine_scores.csv"
    out_csv.write_text("cached\n", encoding="utf-8")
    policy = PocketMdAdmissionPolicy.create(
        selection_policy_sha256=authority["policy_sha256"],
        selection_authority_schema_version=authority["schema_version"],
        topk_global=128,
        topk_per_target=0,
        selection_mode="union",
    )
    implementation_manifest = build_implementation_source_manifest()
    out_summary = out_csv.with_suffix(".summary.json")
    out_summary.write_text(
        json.dumps(
            {
                "pass": True,
                "refinement_schema_version": "ligand_physics_refinement_v2",
                "refinement_backend": "internal_gb_sa_v1",
                "refinement_mode": "implicit_gb_sa_v1",
                "scores_csv_in": str(scores),
                "scores_csv_in_sha256": batch_module._sha256_file(scores),
                "scores_csv_out": str(out_csv),
                "scores_csv_out_sha256": batch_module._sha256_file(out_csv),
                "selection_authority_summary_json": str(authority_path),
                "selection_authority_summary_sha256": batch_module._sha256_file(
                    authority_path
                ),
                "selection_score_authority": authority,
                "pocketmd_admission_policy": policy.to_dict(),
                "implementation_source_manifest": implementation_manifest,
                "implementation_fingerprint_sha256": implementation_manifest[
                    "manifest_sha256"
                ],
                "refined_energy_col": "deltaG_mm_gbsa_kcal_mol",
                "refined_rank_col": "binding_score_stronger_physics_v1",
                "selection_mode": "union",
                "topk_global_requested": 128,
                "topk_per_target_requested": 0,
            }
        ),
        encoding="utf-8",
    )

    def unexpected_run(*_args, **_kwargs):
        raise AssertionError("validated cache should not invoke refinement")

    monkeypatch.setattr(batch_module, "ROOT", tmp_path)
    monkeypatch.setattr(batch_module.subprocess, "run", unexpected_run)

    summary = batch_module.batch_refine_stage3_scores(
        stage3_glob="*_stage3_scores.csv",
        skip_existing=True,
    )

    assert summary["skipped_existing_count"] == 1
    assert summary["refined_count"] == 0

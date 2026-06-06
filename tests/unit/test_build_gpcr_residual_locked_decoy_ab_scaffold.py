from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_build_gpcr_residual_locked_decoy_ab_scaffold(tmp_path: Path) -> None:
    baseline_root = tmp_path / "baseline_run"
    baseline_root.mkdir()
    generated_root = tmp_path / "generated"
    source_spec = tmp_path / "source_spec.json"
    out_json = tmp_path / "out.json"
    out_csv = tmp_path / "out.csv"
    out_md = tmp_path / "out.md"

    profile_a = tmp_path / "gpcr_core_profile.json"
    profile_b = tmp_path / "gpcr_ood_profile.json"
    profile_a.write_text(json.dumps({"residual_prototype_enabled": True}), encoding="utf-8")
    profile_b.write_text(json.dumps({"residual_prototype_enabled": True}), encoding="utf-8")

    core_summary = tmp_path / "core_summary.json"
    core_split = tmp_path / "core_hard_decoy_split.csv"
    core_labels = tmp_path / "core_hard_decoy_labels.csv"
    ood_summary = tmp_path / "ood_summary.json"
    ood_split = tmp_path / "ood_hard_decoy_split.csv"
    ood_labels = tmp_path / "ood_hard_decoy_labels.csv"
    for path in [core_summary, core_split, core_labels, ood_summary, ood_split, ood_labels]:
        path.write_text("x", encoding="utf-8")

    (baseline_root / "state.json").write_text(
        json.dumps(
            {
                "sets": [
                    {
                        "set_id": "set1_core_blind",
                        "tasks": [
                            {"task_id": "gpcr_core_full", "summary_json": str(core_summary)},
                        ],
                    },
                    {
                        "set_id": "set2_expanded_ood",
                        "tasks": [
                            {"task_id": "gpcr_chembl50_full", "summary_json": str(ood_summary)},
                        ],
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    source_spec.write_text(
        json.dumps(
            {
                "sets": [
                    {
                        "set_id": "set1_core_blind",
                        "title": "Core Blind Set",
                        "purpose": "test",
                        "tasks": [
                            {
                                "task_id": "gpcr_core_full",
                                "kind": "ligand_stress",
                                "domain": "gpcr",
                                "ligand_sizes": "10000",
                                "profile_json": str(profile_a),
                                "date_tag_suffix": "gpcr-core-full-residualab1",
                            }
                        ],
                    },
                    {
                        "set_id": "set2_expanded_ood",
                        "title": "Expanded OOD Set",
                        "purpose": "test",
                        "tasks": [
                            {
                                "task_id": "gpcr_chembl50_full",
                                "kind": "ligand_stress",
                                "domain": "gpcr",
                                "ligand_sizes": "10000",
                                "profile_json": str(profile_b),
                                "date_tag_suffix": "gpcr-chembl50-full-residualab1",
                            }
                        ],
                    },
                ]
            }
        ),
        encoding="utf-8",
    )

    subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools/product/build_gpcr_residual_locked_decoy_ab_scaffold.py"),
            "--baseline-run-root",
            str(baseline_root),
            "--source-spec-json",
            str(source_spec),
            "--generated-root",
            str(generated_root),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ],
        check=True,
        cwd=ROOT,
    )

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["locked_decoy_ready"] is True
    assert len(payload["rows"]) == 2
    generated_profiles = list((generated_root / "profiles").glob("*_lockeddecoy1.json"))
    assert len(generated_profiles) == 2
    sample_profile = json.loads(generated_profiles[0].read_text(encoding="utf-8"))
    assert sample_profile["build_hard_decoy_benchmark"] is False
    assert sample_profile["locked_decoy_ab_enabled"] is True
    assert payload["residual_mode"] == "shadow_only"


def test_build_gpcr_residual_locked_decoy_apply_scaffold(tmp_path: Path) -> None:
    baseline_root = tmp_path / "baseline_run"
    baseline_root.mkdir()
    generated_root = tmp_path / "generated"
    source_spec = tmp_path / "source_spec.json"
    out_json = tmp_path / "out.json"

    profile_a = tmp_path / "gpcr_core_profile.json"
    profile_a.write_text(json.dumps({"residual_prototype_enabled": True}), encoding="utf-8")
    summary = tmp_path / "core_summary.json"
    split = tmp_path / "core_hard_decoy_split.csv"
    labels = tmp_path / "core_hard_decoy_labels.csv"
    for path in [summary, split, labels]:
        path.write_text("x", encoding="utf-8")

    (baseline_root / "state.json").write_text(
        json.dumps({"sets": [{"set_id": "set1_core_blind", "tasks": [{"task_id": "gpcr_core_full", "summary_json": str(summary)}]}]}),
        encoding="utf-8",
    )
    source_spec.write_text(
        json.dumps(
            {
                "sets": [
                    {
                        "set_id": "set1_core_blind",
                        "title": "Core Blind Set",
                        "purpose": "test",
                        "tasks": [
                            {
                                "task_id": "gpcr_core_full",
                                "kind": "ligand_stress",
                                "domain": "gpcr",
                                "ligand_sizes": "10000",
                                "profile_json": str(profile_a),
                                "date_tag_suffix": "gpcr-core-full-residualab1",
                            }
                        ],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools/product/build_gpcr_residual_locked_decoy_ab_scaffold.py"),
            "--baseline-run-root",
            str(baseline_root),
            "--source-spec-json",
            str(source_spec),
            "--generated-root",
            str(generated_root),
            "--out-json",
            str(out_json),
            "--residual-mode",
            "apply",
            "--profile-suffix",
            "lockeddecoyapply1",
        ],
        check=True,
        cwd=ROOT,
    )
    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["residual_mode"] == "apply"
    profile = json.loads(next((generated_root / "profiles").glob("*_lockeddecoyapply1.json")).read_text(encoding="utf-8"))
    assert profile["ranking_score_col"] == "binding_score_composite_v7_residual_active"
    assert profile["ranking_probability_score_col"] == "binding_score_composite_v7_residual_active"
    assert profile["residual_prototype_mode"] == "apply"


def test_build_gpcr_residual_locked_decoy_scaffold_overrides_spec_json(tmp_path: Path) -> None:
    baseline_root = tmp_path / "baseline_run"
    baseline_root.mkdir()
    generated_root = tmp_path / "generated"
    source_spec = tmp_path / "source_spec.json"
    out_json = tmp_path / "out.json"
    residual_spec = tmp_path / "residual_v2.json"
    residual_spec.write_text("{}", encoding="utf-8")

    profile_a = tmp_path / "gpcr_core_profile.json"
    profile_a.write_text(json.dumps({"residual_prototype_enabled": True, "residual_prototype_spec_json": "old.json"}), encoding="utf-8")
    summary = tmp_path / "core_summary.json"
    split = tmp_path / "core_hard_decoy_split.csv"
    labels = tmp_path / "core_hard_decoy_labels.csv"
    for path in [summary, split, labels]:
        path.write_text("x", encoding="utf-8")

    (baseline_root / "state.json").write_text(
        json.dumps({"sets": [{"set_id": "set1_core_blind", "tasks": [{"task_id": "gpcr_core_full", "summary_json": str(summary)}]}]}),
        encoding="utf-8",
    )
    source_spec.write_text(
        json.dumps(
            {
                "sets": [
                    {
                        "set_id": "set1_core_blind",
                        "title": "Core Blind Set",
                        "purpose": "test",
                        "tasks": [
                            {
                                "task_id": "gpcr_core_full",
                                "kind": "ligand_stress",
                                "domain": "gpcr",
                                "ligand_sizes": "10000",
                                "profile_json": str(profile_a),
                                "date_tag_suffix": "gpcr-core-full-residualab1",
                            }
                        ],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools/product/build_gpcr_residual_locked_decoy_ab_scaffold.py"),
            "--baseline-run-root",
            str(baseline_root),
            "--source-spec-json",
            str(source_spec),
            "--generated-root",
            str(generated_root),
            "--out-json",
            str(out_json),
            "--residual-spec-json",
            str(residual_spec),
        ],
        check=True,
        cwd=ROOT,
    )
    payload = json.loads(out_json.read_text(encoding="utf-8"))
    profile = json.loads(next((generated_root / "profiles").glob("*_lockeddecoy1.json")).read_text(encoding="utf-8"))
    assert payload["residual_spec_json"] == str(residual_spec.resolve())
    assert profile["residual_prototype_spec_json"] == str(residual_spec.resolve())

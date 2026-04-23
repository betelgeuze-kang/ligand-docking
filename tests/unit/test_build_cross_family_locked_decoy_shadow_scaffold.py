from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_build_cross_family_locked_decoy_shadow_scaffold(tmp_path: Path) -> None:
    baseline_root = tmp_path / "baseline_run"
    baseline_root.mkdir()
    generated_root = tmp_path / "generated"
    source_spec = tmp_path / "source_spec.json"
    residual_spec = tmp_path / "residual_spec.json"
    out_json = tmp_path / "out.json"

    residual_spec.write_text(json.dumps({"summary": {"prototype_variant": "narrow_v2"}}), encoding="utf-8")

    ion_core = tmp_path / "ion_core_profile.json"
    ion_ood = tmp_path / "ion_ood_profile.json"
    kin_core = tmp_path / "kin_core_profile.json"
    kin_ood = tmp_path / "kin_ood_profile.json"
    for path in [ion_core, ion_ood, kin_core, kin_ood]:
        path.write_text(json.dumps({"residual_prototype_enabled": True}), encoding="utf-8")

    baseline_sets = []
    for task_id, stem, set_id in [
        ("ion_trpv1_chembl20_full", "ion_core", "set1_core_blind"),
        ("kinase_core_full", "kin_core", "set1_core_blind"),
        ("ion_trpv1_chembl50_full", "ion_ood", "set2_expanded_ood"),
        ("kinase_strict_full", "kin_ood", "set2_expanded_ood"),
    ]:
        summary = tmp_path / f"{stem}_summary.json"
        labels = tmp_path / f"{stem}_hard_decoy_labels.csv"
        split = tmp_path / f"{stem}_hard_decoy_split.csv"
        for p in [summary, labels, split]:
            p.write_text("x", encoding="utf-8")
        baseline_sets.append((set_id, {"task_id": task_id, "summary_json": str(summary)}))

    state = {"sets": []}
    for set_id in ["set1_core_blind", "set2_expanded_ood"]:
        tasks = [task for s, task in baseline_sets if s == set_id]
        state["sets"].append({"set_id": set_id, "tasks": tasks})
    (baseline_root / "state.json").write_text(json.dumps(state), encoding="utf-8")

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
                                "task_id": "ion_trpv1_chembl20_full",
                                "kind": "ligand_stress",
                                "domain": "ion_channel",
                                "ligand_sizes": "10000",
                                "profile_json": str(ion_core),
                                "date_tag_suffix": "ion-trpv1-chembl20-full",
                            },
                            {
                                "task_id": "kinase_core_full",
                                "kind": "ligand_stress",
                                "domain": "kinase",
                                "ligand_sizes": "10000",
                                "profile_json": str(kin_core),
                                "date_tag_suffix": "kinase-core-full",
                            },
                        ],
                    },
                    {
                        "set_id": "set2_expanded_ood",
                        "title": "Expanded OOD Set",
                        "purpose": "test",
                        "tasks": [
                            {
                                "task_id": "ion_trpv1_chembl50_full",
                                "kind": "ligand_stress",
                                "domain": "ion_channel",
                                "ligand_sizes": "10000",
                                "profile_json": str(ion_ood),
                                "date_tag_suffix": "ion-trpv1-chembl50-full",
                            },
                            {
                                "task_id": "kinase_strict_full",
                                "kind": "ligand_stress",
                                "domain": "kinase",
                                "ligand_sizes": "10000",
                                "profile_json": str(kin_ood),
                                "date_tag_suffix": "kinase-strict-full",
                            },
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
            str(ROOT / "tools/build_cross_family_locked_decoy_shadow_scaffold.py"),
            "--baseline-run-root",
            str(baseline_root),
            "--source-spec-json",
            str(source_spec),
            "--generated-root",
            str(generated_root),
            "--residual-spec-json",
            str(residual_spec),
            "--out-json",
            str(out_json),
        ],
        check=True,
        cwd=ROOT,
    )

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["runtime_hook_ready"] is True
    assert payload["locked_decoy_ready"] is True
    assert payload["family_scope"] == ["ion_channel", "kinase"]
    assert len(payload["profile_rows"]) == 4

    generated_profiles = sorted((generated_root / "profiles").glob("*_crossfamshadow1.json"))
    assert len(generated_profiles) == 4
    ion_profile = json.loads(generated_profiles[0].read_text(encoding="utf-8"))
    assert ion_profile["build_hard_decoy_benchmark"] is False
    assert ion_profile["locked_decoy_ab_enabled"] is True
    assert ion_profile["residual_prototype_mode"] == "shadow_only"
    assert ion_profile["residual_prototype_runtime_hook_ready"] is True

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_build_ion_kinase_equal_size_shadow_scaffold(tmp_path: Path) -> None:
    source_spec = tmp_path / "source.json"
    shadow_origin = tmp_path / "origin.json"
    generated_root = tmp_path / "generated"
    out_json = tmp_path / "scaffold.json"
    out_csv = tmp_path / "scaffold.csv"
    out_md = tmp_path / "scaffold.md"

    profile_ion_core = tmp_path / "ion_core.json"
    profile_ion_ood = tmp_path / "ion_ood.json"
    profile_kin_core = tmp_path / "kin_core.json"
    profile_kin_ood = tmp_path / "kin_ood.json"
    for idx, path in enumerate([profile_ion_core, profile_ion_ood, profile_kin_core, profile_kin_ood], start=1):
        path.write_text(json.dumps({"version": idx}), encoding="utf-8")

    source_spec.write_text(
        json.dumps(
            {
                "sets": [
                    {
                        "set_id": "set1_core_blind",
                        "tasks": [
                            {"task_id": "ion_trpv1_chembl20_full", "domain": "ion_channel", "kind": "ligand_stress", "profile_json": str(profile_ion_core), "ligand_sizes": "10000"},
                            {"task_id": "kinase_core_full", "domain": "kinase", "kind": "ligand_stress", "profile_json": str(profile_kin_core), "ligand_sizes": "10000"},
                        ],
                    },
                    {
                        "set_id": "set2_expanded_ood",
                        "tasks": [
                            {"task_id": "ion_trpv1_chembl50_full", "domain": "ion_channel", "kind": "ligand_stress", "profile_json": str(profile_ion_ood), "ligand_sizes": "10000"},
                            {"task_id": "kinase_strict_full", "domain": "kinase", "kind": "ligand_stress", "profile_json": str(profile_kin_ood), "ligand_sizes": "10000"},
                        ],
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    shadow_origin.write_text(json.dumps({"comparison_kind": "equal_size_residual_ab"}), encoding="utf-8")

    subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools/build_ion_kinase_equal_size_shadow_scaffold.py"),
            "--source-spec-json", str(source_spec),
            "--shadow-origin-artifact", str(shadow_origin),
            "--generated-root", str(generated_root),
            "--out-json", str(out_json),
            "--out-csv", str(out_csv),
            "--out-md", str(out_md),
        ],
        check=True,
        cwd=ROOT,
    )

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["comparison_kind"] == "equal_size_cross_family_shadow"
    assert payload["runtime_hook_ready"] is True
    assert payload["scope_summary"]["selected_task_count"] == 4
    assert payload["scope_summary"]["domains_touched"] == ["ion_channel", "kinase"]
    assert "shadow_only_no_active_score_change" in payload["guardrails"]
    generated_profiles = list((generated_root / "profiles").glob("*.json"))
    assert len(generated_profiles) == 4
    one_profile = json.loads(generated_profiles[0].read_text(encoding="utf-8"))
    assert one_profile["residual_prototype_enabled"] is True
    assert one_profile["residual_prototype_mode"] == "shadow_only"
    assert one_profile["residual_prototype_runtime_hook_ready"] is True

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _contains_tokens(text: str, *tokens: str) -> None:
    lowered = text.lower()
    for token in tokens:
        assert token.lower() in lowered


def test_build_gpcr_residual_equal_size_ab_scaffold(tmp_path: Path) -> None:
    source_spec = tmp_path / "source.json"
    prototype_spec = tmp_path / "prototype.json"
    generated_root = tmp_path / "generated"
    out_json = tmp_path / "ab.json"
    out_csv = tmp_path / "ab.csv"
    out_md = tmp_path / "ab.md"

    profile_a = tmp_path / "gpcr_core.json"
    profile_b = tmp_path / "gpcr_ood.json"
    profile_a.write_text(json.dumps({"version": "a"}), encoding="utf-8")
    profile_b.write_text(json.dumps({"version": "b"}), encoding="utf-8")
    source_spec.write_text(
        json.dumps(
            {
                "sets": [
                    {
                        "set_id": "set1_core_blind",
                        "tasks": [
                            {
                                "task_id": "gpcr_core_full",
                                "domain": "gpcr",
                                "kind": "ligand_stress",
                                "profile_json": str(profile_a),
                                "ligand_sizes": "10000",
                            }
                        ],
                    },
                    {
                        "set_id": "set2_expanded_ood",
                        "tasks": [
                            {
                                "task_id": "gpcr_chembl50_full",
                                "domain": "gpcr",
                                "kind": "ligand_stress",
                                "profile_json": str(profile_b),
                                "ligand_sizes": "10000",
                            }
                        ],
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    prototype_spec.write_text(
        json.dumps({"summary": {"prototype_mode": "shadow_only"}}),
        encoding="utf-8",
    )

    subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools/build_gpcr_residual_equal_size_ab_scaffold.py"),
            "--source-spec-json",
            str(source_spec),
            "--prototype-spec-json",
            str(prototype_spec),
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
    assert payload["comparison_kind"] == "equal_size_residual_ab"
    assert payload["runtime_hook_ready"] is True
    assert payload["scope_summary"]["selected_task_count"] == 2
    _contains_tokens(payload["recommended_next_action"], "equal-size", "gpcr", "baseline", "candidate", "a/b")
    generated_profiles = list((generated_root / "profiles").glob("*_residualab1.json"))
    assert len(generated_profiles) == 2
    profile_payload = json.loads(generated_profiles[0].read_text(encoding="utf-8"))
    assert profile_payload["residual_prototype_runtime_hook_ready"] is True
    assert profile_payload["residual_prototype_status"] == "shadow_runtime_ready"

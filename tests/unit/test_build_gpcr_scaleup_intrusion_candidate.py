import json
from pathlib import Path

import pytest

from tools import build_gpcr_scaleup_intrusion_candidate as mod


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def test_build_payload_writes_shadow_profile_and_core_only_100k_spec(tmp_path: Path) -> None:
    base_profile = tmp_path / "config" / "base_gpcr.json"
    residual_spec = tmp_path / "runs" / "gpcr_residual_prototype_spec_core_decoy_intrusion_v1_current.json"
    out_dir = tmp_path / "candidate"
    _write_json(
        base_profile,
        {
            "version": "ligand_htvs_blind_gpcr_adrb2_v4_scorefix3",
            "description": "base profile",
            "ranking_score_col": "binding_score_composite_v7",
            "ranking_probability_score_col": "binding_score_composite_v7",
            "full": {"max_ligands": 10000, "replicas": 10000},
        },
    )
    _write_json(
        residual_spec,
        {
            "summary": {
                "family": "gpcr",
                "prototype_variant": "gpcr_core_decoy_intrusion_v1",
            }
        },
    )

    payload = mod.build_payload(
        out_dir=out_dir,
        spec_json=residual_spec,
        base_profile_json=base_profile,
        tag_suffix="intrusiontest",
    )

    profile_path = Path(payload["profile_json"])
    set_spec_path = Path(payload["set_spec_json"])
    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    set_spec = json.loads(set_spec_path.read_text(encoding="utf-8"))

    assert profile["residual_prototype_enabled"] is True
    assert profile["residual_prototype_mode"] == "shadow_only"
    assert profile["residual_prototype_family"] == "gpcr"
    assert profile["residual_prototype_runtime_hook_ready"] is True
    assert profile["residual_prototype_spec_json"] == str(residual_spec.resolve())
    assert profile["ranking_score_col"] == "binding_score_composite_v7"
    assert profile["ranking_probability_score_col"] == "binding_score_composite_v7"
    assert profile["router_promotion_allowed"] is False

    assert set_spec["global_governance"]["router_promotion_allowed"] is False
    assert set_spec["global_governance"]["prototype_spec_json"] == str(residual_spec.resolve())
    assert [row["set_id"] for row in set_spec["sets"]] == ["set1_core_blind"]
    task = set_spec["sets"][0]["tasks"][0]
    assert task == {
        "task_id": "gpcr_core_full",
        "domain": "gpcr",
        "kind": "ligand_stress",
        "profile_json": str(profile_path.resolve()),
        "ligand_sizes": "100000",
        "date_tag_suffix": "gpcr-core-full-intrusiontest",
    }


def test_build_payload_rejects_non_intrusion_residual_spec(tmp_path: Path) -> None:
    base_profile = tmp_path / "base.json"
    residual_spec = tmp_path / "spec.json"
    _write_json(base_profile, {"ranking_score_col": "binding_score_composite_v7"})
    _write_json(residual_spec, {"summary": {"prototype_variant": "narrow_v2"}})

    with pytest.raises(ValueError, match="gpcr_core_decoy_intrusion_v1"):
        mod.build_payload(
            out_dir=tmp_path / "out",
            spec_json=residual_spec,
            base_profile_json=base_profile,
            tag_suffix="bad",
        )

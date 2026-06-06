from __future__ import annotations

import json
from pathlib import Path

from tools.product import build_residual_shadow_ab as mod


def _source_packet(profile_path: Path, *, residual_mode: str = "shadow_only") -> dict[str, object]:
    return {
        "comparison_kind": "equal_size_residual_ab_locked_decoy",
        "runtime_hook_ready": True,
        "locked_decoy_ready": True,
        "residual_mode": residual_mode,
        "rows": [
            {
                "set_id": "set1_core_blind",
                "task_id": "gpcr_core_full",
                "generated_profile_json": str(profile_path),
                "locked_decoy_labels_csv": "labels.csv",
                "locked_decoy_split_csv": "split.csv",
                "residual_mode": residual_mode,
            }
        ],
    }


def test_build_residual_shadow_ab_scaffold_ready(tmp_path: Path) -> None:
    profile = tmp_path / "profile.json"
    profile.write_text(json.dumps({"residual_prototype_mode": "shadow_only"}), encoding="utf-8")

    payload = mod.build_residual_shadow_ab(source_packet=_source_packet(profile), source_path="source.json")

    summary = payload["summary"]
    assert summary["status"] == "residual_shadow_ab_scaffold_ready"
    assert summary["scaffold_ready"] is True
    assert summary["residual_mode"] == "shadow"
    assert summary["raw_baseline_preserved"] is True
    assert summary["corrected_prediction_recorded"] is True
    assert summary["no_customer_facing_ranking_change"] is True
    assert summary["abstention_fields_present"] is True
    assert summary["assist_promotion_allowed"] is False
    assert summary["production_promotion_allowed"] is False
    assert summary["external_state_mutated"] is False


def test_build_residual_shadow_ab_blocks_apply_mode(tmp_path: Path) -> None:
    profile = tmp_path / "profile.json"
    profile.write_text(
        json.dumps(
            {
                "residual_prototype_mode": "apply",
                "ranking_score_col": "binding_score_composite_v7_residual_active",
                "ranking_probability_score_col": "binding_score_composite_v7_residual_active",
            }
        ),
        encoding="utf-8",
    )

    payload = mod.build_residual_shadow_ab(source_packet=_source_packet(profile, residual_mode="apply"), source_path="source.json")

    summary = payload["summary"]
    assert summary["status"] == "blocked_residual_shadow_ab_scaffold"
    assert summary["scaffold_ready"] is False
    assert summary["blocker_row_count"] == 1
    assert payload["rows"][0]["customer_facing_ranking_changed"] is True


def test_build_residual_shadow_ab_cli_writes_outputs(tmp_path: Path) -> None:
    profile = tmp_path / "profile.json"
    source = tmp_path / "source.json"
    out_json = tmp_path / "out.json"
    out_csv = tmp_path / "out.csv"
    out_md = tmp_path / "out.md"
    profile.write_text(json.dumps({"residual_prototype_mode": "shadow_only"}), encoding="utf-8")
    source.write_text(json.dumps(_source_packet(profile)) + "\n", encoding="utf-8")

    mod.main(["--source-json", str(source), "--out-json", str(out_json), "--out-csv", str(out_csv), "--out-md", str(out_md)])

    assert json.loads(out_json.read_text(encoding="utf-8"))["summary"]["scaffold_ready"] is True
    assert "task_id" in out_csv.read_text(encoding="utf-8")
    assert "Residual Shadow A/B Scaffold" in out_md.read_text(encoding="utf-8")

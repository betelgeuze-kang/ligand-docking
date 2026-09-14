"""Execute canonical HTVS orchestration with fresh synthetic CSVs and compute stubs.

All child commands and inline scoring are intercepted. No model or molecule runs.
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from betelgeuze_engine.product.runners import htvs_pipeline as mod


def _row(queue_id, **overrides):
    row = dict(queue_id=queue_id, target="synthetic_target", ligand_id=queue_id, family="gpcr",
               prior_rank_proxy=.95, affinity_hint=0., onsps_norm=0., mw_norm=0., is_ood=False)
    row.update(overrides)
    return row


def _run_synthetic_consumer(tmp_path, monkeypatch, rows, options=(), stale_manifest=False,
                            manifest_defect=None, raw_payload=False):
    prefix = tmp_path / "synthetic"
    args = mod.build_parser().parse_args([
        "--out-prefix", str(prefix), "--targets", "synthetic_target", "--no-single-instance",
        "--trajectory-engine-mode", "proxy", "--run-trajectory-sim", "--no-require-native-path",
        "--no-auto-heavy-artifacts-root", "--no-reuse-stage1-if-exists", *options,
    ])
    child_commands = []
    trajectory_ids = []
    inline_ids = []
    if stale_manifest:
        pd.DataFrame([dict(queue_id="stale_prior_run")]).to_csv(f"{prefix}_stage2_traj_manifest.csv", index=False)

    def value(cmd, flag):
        return cmd[cmd.index(flag) + 1]

    def fake_child(cmd):
        child_commands.append(list(cmd))
        if cmd[1] == "tools/build_ligand_mapping_queue.py":
            pd.DataFrame(rows).to_csv(value(cmd, "--out-queue-csv"), index=False)
            return {"ok": True, "synthetic_stub": True}
        if cmd[1] == "tools/product/generate_ligand_trajectory_batch.py":
            queue = pd.read_csv(value(cmd, "--queue-csv"), converters={"queue_id": str})
            trajectory_ids.extend(queue["queue_id"].tolist())
            manifest = queue[["queue_id"]]
            if manifest_defect == "partial":
                manifest = manifest.iloc[:0]
            elif manifest_defect == "duplicate":
                manifest = pd.concat([manifest, manifest], ignore_index=True)
            if manifest_defect != "missing":
                manifest.to_csv(value(cmd, "--out-manifest-csv"), index=False)
            return {"ok": True, "synthetic_stub": True}
        assert cmd[1] == "tools/product/run_ligand_residual_meta_cycle.py", cmd
        # Stop at the next orchestration boundary before any training or scoring.
        return {"ok": False, "synthetic_stop": True}

    def fake_inline(skipped_rows, *, out_csv, contact_cutoff_A):
        inline_ids.extend(row["queue_id"] for row in skipped_rows)
        pd.DataFrame([{"queue_id": row["queue_id"], "stage2_skip_applied": True}
                      for row in skipped_rows]).to_csv(out_csv, index=False)
        return {"skip_manifest_csv": out_csv, "skip_row_count": len(skipped_rows), "synthetic_stub": True}

    monkeypatch.setattr(mod, "_run_cmd", fake_child)
    monkeypatch.setattr(mod, "build_skip_inline_manifest", fake_inline)
    monkeypatch.setattr(mod, "_finalize_and_write", lambda _prefix, payload, _args: payload)
    payload = mod.run_pipeline(args)
    if raw_payload:
        return payload, child_commands
    assert payload["failed_stage"] == "stage2_residual_meta"
    assert payload["stages"]["stage2_residual_meta"]["synthetic_stop"] is True
    trajectory = payload["stages"]["stage2_trajectory_generation"]
    return trajectory, trajectory_ids, inline_ids, child_commands


def test_all_skipped_consumer_does_not_replay_original_queue_or_stale_manifest(tmp_path, monkeypatch):
    trajectory, trajectory_ids, inline_ids, commands = _run_synthetic_consumer(
        tmp_path, monkeypatch, [_row("tail_a"), _row("tail_b")], stale_manifest=True)
    assert trajectory_ids == []
    assert not any("generate_ligand_trajectory" in cmd[1] for cmd in commands)
    assert inline_ids == ["tail_a", "tail_b"]
    assert trajectory["skipped"] is True
    assert trajectory["reason"] == "all_candidates_routed_inline"
    meta = trajectory["stage2_router_meta"]
    assert meta["row_count"] == meta["stage2_skip_count"] == 2
    assert meta["stage2_full_count"] == 0
    assert pd.read_csv(meta["routed_queue_csv"]).empty
    merged = pd.read_csv(meta["merged_manifest"]["merged_manifest_csv"])
    assert merged["queue_id"].tolist() == inline_ids


def test_consumer_retains_unknown_auxiliary_ood_nonfinite_and_top_rank(tmp_path, monkeypatch):
    rows = [_row("tail"), _row("missing", mw_norm=None), _row("ood", is_ood=True),
            _row("nonfinite", affinity_hint=float("inf")), _row("top", prior_rank_proxy=0.)]
    trajectory, trajectory_ids, inline_ids, _ = _run_synthetic_consumer(tmp_path, monkeypatch, rows)
    assert trajectory_ids == ["missing", "ood", "nonfinite", "top"]
    assert inline_ids == ["tail"]
    meta = trajectory["stage2_router_meta"]
    assert meta["row_count"] == meta["stage2_full_count"] + meta["stage2_skip_count"] == 5
    merged = pd.read_csv(meta["merged_manifest"]["merged_manifest_csv"])
    assert sorted(merged["queue_id"]) == sorted(row["queue_id"] for row in rows)
    assert merged["queue_id"].is_unique


@pytest.mark.parametrize("options,expected_skip", [
    (["--stage2-skip-fraction-target", "0"], 0),
    (["--stage2-skip-max-fraction", ".5"], 1),
    (["--no-stage2-skip-router-enabled", "--stage2-skip-fraction-target", "1"], 0),
])
def test_consumer_wires_target_hard_cap_and_disable_separately(tmp_path, monkeypatch, options, expected_skip):
    trajectory, trajectory_ids, inline_ids, _ = _run_synthetic_consumer(
        tmp_path, monkeypatch, [_row("tail_a"), _row("tail_b")], options)
    assert len(inline_ids) == expected_skip
    assert len(trajectory_ids) == 2 - expected_skip
    assert set(inline_ids).isdisjoint(trajectory_ids)
    meta = trajectory["stage2_router_meta"]
    assert meta["stage2_skip_count"] == expected_skip
    if "--no-stage2-skip-router-enabled" in options:
        assert meta["enabled"] is meta["router_enabled"] is False
        assert {row["stage2_skip_reason"] for row in meta["routed_rows"]} == {"router_disabled"}


def test_pipeline_preset_and_explicit_cli_control_precedence(tmp_path):
    preset = tmp_path / "synthetic_preset.json"
    preset.write_text(json.dumps({"stage2_skip_router_enabled": True,
                                  "stage2_skip_fraction_target": .7, "stage2_skip_max_fraction": .2}))
    args = mod.build_parser().parse_args(["--pipeline-preset-json", str(preset),
        "--no-stage2-skip-router-enabled", "--stage2-skip-fraction-target", "0"])
    mod._apply_pipeline_preset_json(args)
    assert args.stage2_skip_router_enabled is False
    assert args.stage2_skip_fraction_target == 0.
    assert args.stage2_skip_max_fraction == .2


def test_all_skipped_sla_never_reads_stale_trajectory_telemetry(tmp_path, monkeypatch):
    trajectory, _, _, _ = _run_synthetic_consumer(tmp_path, monkeypatch, [_row("tail")])
    stale_summary = tmp_path / "synthetic_stage2_traj_summary.json"
    stale_summary.write_text(json.dumps({"prod_mode": True, "mean_sim_frames_count": 999.,
                                         "prod_frame_budget_applied_count": 987}))
    def forbidden(_path):
        pytest.fail("all-skipped run attempted to reuse trajectory engine telemetry")
    monkeypatch.setattr(mod, "_traj_stage2_engine_telemetry", forbidden)
    summary = mod._build_sla_summary(
        out_prefix=str(tmp_path / "synthetic"), stage0={}, stage1={}, stage2_traj=trajectory,
        stage2_meta={}, stage3={}, stage3b={}, stage4={}, stage45={}, stage5={},
        gate_summary={"pass": True}, queue_csv=str(tmp_path / "synthetic_stage1_queue.csv"),
        trajectory_root=str(tmp_path / "synthetic_stage2_traj_frames"), heavy_enabled=False,
        traj_stage2_summary_json=str(stale_summary),
    )
    assert summary["stage2_trajectory_skipped_reason"] == "all_candidates_routed_inline"
    assert "traj_stage2_engine_summary" not in summary
    assert "traj_stage2_engine_mean_sim_frames_count" not in summary
    assert summary["queue_rate_stage2_rows_per_sec"] is None


@pytest.mark.parametrize("defect", ["merge_exception", "missing", "partial", "duplicate"])
def test_incomplete_mixed_manifests_stop_before_meta_or_scoring(tmp_path, monkeypatch, defect):
    if defect == "merge_exception":
        def fail_merge(*_args, **_kwargs):
            raise OSError("new synthetic merge failure")
        monkeypatch.setattr(mod, "merge_stage2_manifests", fail_merge)
    payload, commands = _run_synthetic_consumer(
        tmp_path, monkeypatch, [_row("inline"), _row("trajectory", is_ood=True)],
        manifest_defect=defect, raw_payload=True,
    )
    assert payload["pass"] is False
    assert payload["failed_stage"] == "stage2_manifest_validation"
    assert not any(cmd[1] in {"tools/product/run_ligand_residual_meta_cycle.py",
                             "tools/run_ligand_backmapping_scoring.py"} for cmd in commands)
    failure = payload["stages"]["stage2_manifest_validation"]
    assert failure["requested_count"] == failure["not_forwarded_count"] == 2
    assert failure["expected_trajectory_count"] == failure["expected_inline_count"] == 1
    assert failure["reason"]


def test_full_only_missing_manifest_cannot_use_prior_run(tmp_path, monkeypatch):
    payload, commands = _run_synthetic_consumer(
        tmp_path, monkeypatch, [_row("trajectory", is_ood=True)],
        stale_manifest=True, manifest_defect="missing", raw_payload=True,
    )
    assert payload["failed_stage"] == "stage2_manifest_validation"
    assert not any(cmd[1] == "tools/product/run_ligand_residual_meta_cycle.py" for cmd in commands)


def test_matching_prior_ids_do_not_prove_current_manifest_publication(tmp_path, monkeypatch):
    pd.DataFrame([{"queue_id": "trajectory"}]).to_csv(tmp_path / "synthetic_stage2_traj_manifest.csv", index=False)
    payload, commands = _run_synthetic_consumer(
        tmp_path, monkeypatch, [_row("trajectory", is_ood=True)],
        manifest_defect="missing", raw_payload=True,
    )
    assert payload["failed_stage"] == "stage2_manifest_validation"
    assert "did not publish" in payload["stages"]["stage2_manifest_validation"]["reason"]
    assert not any(cmd[1] == "tools/product/run_ligand_residual_meta_cycle.py" for cmd in commands)


@pytest.mark.parametrize("queue_id", ["001", "NA"])
def test_consumer_keeps_literal_queue_ids(tmp_path, monkeypatch, queue_id):
    trajectory, ids, _, _ = _run_synthetic_consumer(tmp_path, monkeypatch, [_row(queue_id, is_ood=True)])
    assert ids == [queue_id]
    assert trajectory["stage2_router_meta"]["merged_manifest"]["queue_coverage_validated"] is True

from __future__ import annotations

import json
import time

import numpy as np
import pandas as pd
import torch

from tools import generate_ligand_trajectory_engine as mod


def test_prod_speedpack_parser_defaults_are_off() -> None:
    args = mod.build_parser().parse_args(["--queue-csv", "q.csv"])
    assert args.prod_mode is False
    assert args.prod_adaptive_frame_budget is False
    assert args.prod_early_stop is False
    assert args.prod_light_artifacts is False


def test_resolve_prod_effective_frames_is_noop_when_disabled() -> None:
    effective, score, applied = mod._resolve_prod_effective_frames(
        requested_frames=120,
        affinity_hint=0.20,
        ligand_mw=180.0,
        strategy_type=str(mod.StrategyType.DIRECT_PERTURBATION_NO_MIN),
        prod_mode=False,
        adaptive_budget_enabled=False,
        prod_min_frames=60,
        prod_frame_budget_tiers=mod._parse_prod_frame_budget_tiers("0.90:1.00,0.00:0.50"),
    )
    assert effective == 120
    assert 0.0 <= score <= 1.0
    assert applied is False


def test_resolve_prod_effective_frames_applies_conservative_cap() -> None:
    effective, score, applied = mod._resolve_prod_effective_frames(
        requested_frames=120,
        affinity_hint=0.15,
        ligand_mw=160.0,
        strategy_type=str(mod.StrategyType.DIRECT_PERTURBATION_NO_MIN),
        prod_mode=True,
        adaptive_budget_enabled=True,
        prod_min_frames=60,
        prod_frame_budget_tiers=mod._parse_prod_frame_budget_tiers("0.90:1.00,0.70:0.80,0.00:0.50"),
    )
    assert 0.0 <= score <= 1.0
    assert effective == 60
    assert applied is True


def test_prod_window_is_stable_requires_low_drift_and_close_mean_distance() -> None:
    assert mod._prod_window_is_stable(
        min_distance_history=[4.22, 4.25, 4.23, 4.24],
        contact_fraction_history=[0.11, 0.115, 0.112, 0.111],
        min_distance_drift_A=0.05,
        contact_fraction_drift=0.01,
        max_mean_min_distance_A=5.0,
    )
    assert not mod._prod_window_is_stable(
        min_distance_history=[6.9, 6.92, 6.91, 6.93],
        contact_fraction_history=[0.01, 0.011, 0.011, 0.01],
        min_distance_drift_A=0.05,
        contact_fraction_drift=0.01,
        max_mean_min_distance_A=5.0,
    )


def test_resolve_prod_artifact_light_settings_disables_optional_outputs_in_prod_mode() -> None:
    settings = mod._resolve_prod_artifact_light_settings(
        prod_mode=True,
        prod_light_artifacts=True,
        manifest_chunk_size=1000,
        progress_every_jobs=25,
        prod_light_progress_every_jobs=250,
    )
    assert settings["enabled"] is True
    assert settings["manifest_chunk_size"] == 0
    assert settings["manifest_chunks_disabled"] is True
    assert settings["target_tail_disabled"] is True
    assert settings["summary_md_disabled"] is True
    assert settings["progress_every_jobs"] == 250


def test_batched_min_distance_contact_fraction_matches_inline_proxy() -> None:
    protein = np.asarray(
        [
            [0.0, 0.0, 0.0],
            [4.0, 0.0, 0.0],
            [0.0, 4.0, 0.0],
        ],
        dtype=np.float32,
    )
    ligand_batch = torch.tensor(
        [
            [[0.5, 0.0, 0.0], [1.0, 0.0, 0.0]],
            [[8.0, 8.0, 8.0], [8.5, 8.0, 8.0]],
        ],
        dtype=torch.float32,
    )

    min_distance, contact_fraction, backend = mod._batched_min_distance_contact_fraction(
        protein,
        ligand_batch,
    )

    expected = [
        mod._inline_frame_mmpbsa_proxy(protein, ligand_batch[idx].numpy(), affinity_hint=0.0, onsps_norm=0.0)
        for idx in range(int(ligand_batch.shape[0]))
    ]
    expected_min_distance = np.asarray([row["min_distance_A"] for row in expected], dtype=np.float32)
    expected_contact_fraction = np.asarray([row["contact_fraction"] for row in expected], dtype=np.float32)

    assert backend == "torch_batch"
    assert np.allclose(min_distance, expected_min_distance, atol=1e-6)
    assert np.allclose(contact_fraction, expected_contact_fraction, atol=1e-6)


def test_register_batch_limit_derate_halves_limit_and_records_event() -> None:
    sig = ("T1", "", (2, 3), (2, 3), "core", 120)
    limits = {sig: 4}
    events: list[dict[str, object]] = []

    next_limit, changed = mod._register_batch_limit_derate(
        batch_limit_by_sig=limits,
        sig=sig,
        attempted_size=4,
        reason="runtime_error:RuntimeError",
        events=events,
    )

    assert changed is True
    assert next_limit == 2
    assert limits[sig] == 2
    assert events == [
        {
            "signature": str(sig),
            "attempted_batch_size": 4,
            "previous_batch_limit": 4,
            "new_batch_limit": 2,
            "reason": "runtime_error:RuntimeError",
        }
    ]


def test_run_batch_records_batch_derate_telemetry(tmp_path, monkeypatch) -> None:
    queue_csv = tmp_path / "queue.csv"
    pd.DataFrame(
        [
            {"queue_id": "q1", "target": "T1", "ligand_id": "L1", "ligand_mw": 200.0},
            {"queue_id": "q2", "target": "T1", "ligand_id": "L2", "ligand_mw": 200.0},
        ]
    ).to_csv(queue_csv, index=False)

    simulate_batch_sizes: list[int] = []

    def _fake_load_protein_coords(target: str, native_path: str) -> np.ndarray:
        return np.zeros((2, 3), dtype=np.float32)

    def _fake_simulate_with_engine_batch(
        protein: np.ndarray,
        ligand0_batch: np.ndarray,
        pocket_batch: np.ndarray,
        **kwargs,
    ):
        batch_size = int(ligand0_batch.shape[0])
        simulate_batch_sizes.append(batch_size)
        if batch_size > 1:
            raise RuntimeError("out of memory")
        selected = np.asarray(ligand0_batch[:, None, :, :], dtype=np.float32)
        frame_idx = np.asarray([0], dtype=np.int32)
        return (
            selected,
            frame_idx,
            "rust_hip",
            1,
            False,
            1,
            {
                "prod_early_stop_metric_backend_counts": {},
                "prod_early_stop_eval_keep_count": 0,
                "prod_early_stop_eval_row_count": 0,
            },
        )

    monkeypatch.setattr(mod, "_load_protein_coords", _fake_load_protein_coords)
    monkeypatch.setattr(mod, "_simulate_with_engine_batch", _fake_simulate_with_engine_batch)

    progress_json = tmp_path / "progress.json"
    summary = mod.run_batch(
        mod.build_parser().parse_args(
            [
                "--queue-csv",
                str(queue_csv),
                "--out-root",
                str(tmp_path / "out"),
                "--out-progress-json",
                str(progress_json),
                "--out-summary-json",
                str(tmp_path / "summary.json"),
                "--out-summary-md",
                str(tmp_path / "summary.md"),
                "--out-manifest-csv",
                str(tmp_path / "manifest.csv"),
                "--frame-output-format",
                "npz_bundle",
                "--job-batch-size",
                "2",
                "--writer-workers",
                "0",
                "--progress-every-jobs",
                "1",
                "--no-fail-on-missing-native",
            ]
        )
    )

    progress = json.loads(progress_json.read_text(encoding="utf-8"))

    assert simulate_batch_sizes == [2, 1, 1]
    assert summary["ok_rows"] == 2
    assert summary["failed_rows"] == 0
    assert summary["job_batch_derate_count"] == 1
    assert len(summary["job_batch_derate_events"]) == 1
    assert list(summary["job_batch_size_resolved"].values()) == [1]
    assert summary["job_batch_derate_events"][0]["new_batch_limit"] == 1
    assert summary["job_batch_derate_events"][0]["reason"] == "runtime_error:RuntimeError"
    assert progress["job_batch_derate_count"] == 1
    assert progress["job_batch_size_resolved_count"] == 1


def test_run_batch_records_prod_early_stop_metric_telemetry(tmp_path, monkeypatch) -> None:
    queue_csv = tmp_path / "queue.csv"
    pd.DataFrame(
        [
            {"queue_id": "q1", "target": "T1", "ligand_id": "L1", "ligand_mw": 200.0},
            {"queue_id": "q2", "target": "T1", "ligand_id": "L2", "ligand_mw": 200.0},
        ]
    ).to_csv(queue_csv, index=False)

    def _fake_load_protein_coords(target: str, native_path: str) -> np.ndarray:
        return np.zeros((2, 3), dtype=np.float32)

    def _fake_simulate_with_engine_batch(
        protein: np.ndarray,
        ligand0_batch: np.ndarray,
        pocket_batch: np.ndarray,
        **kwargs,
    ):
        batch_size = int(ligand0_batch.shape[0])
        selected = np.asarray(ligand0_batch[:, None, :, :], dtype=np.float32)
        frame_idx = np.asarray([0], dtype=np.int32)
        return (
            selected,
            frame_idx,
            "rust_hip",
            1,
            True,
            1,
            {
                "prod_early_stop_metric_backend_counts": {"torch_batch": 1},
                "prod_early_stop_eval_keep_count": 1,
                "prod_early_stop_eval_row_count": batch_size,
            },
        )

    monkeypatch.setattr(mod, "_load_protein_coords", _fake_load_protein_coords)
    monkeypatch.setattr(mod, "_simulate_with_engine_batch", _fake_simulate_with_engine_batch)

    progress_json = tmp_path / "progress.json"
    summary = mod.run_batch(
        mod.build_parser().parse_args(
            [
                "--queue-csv",
                str(queue_csv),
                "--out-root",
                str(tmp_path / "out"),
                "--out-progress-json",
                str(progress_json),
                "--out-summary-json",
                str(tmp_path / "summary.json"),
                "--out-summary-md",
                str(tmp_path / "summary.md"),
                "--out-manifest-csv",
                str(tmp_path / "manifest.csv"),
                "--frame-output-format",
                "npz_bundle",
                "--job-batch-size",
                "2",
                "--writer-workers",
                "0",
                "--progress-every-jobs",
                "1",
                "--no-fail-on-missing-native",
                "--prod-mode",
                "--prod-early-stop",
            ]
        )
    )

    progress = json.loads(progress_json.read_text(encoding="utf-8"))

    assert summary["prod_early_stop_batch_count"] == 1
    assert summary["prod_early_stop_row_count"] == 2
    assert summary["prod_early_stop_eval_keep_count"] == 1
    assert summary["prod_early_stop_eval_row_count"] == 2
    assert summary["prod_early_stop_metric_backend_counts"] == {"torch_batch": 1}
    assert progress["prod_early_stop_eval_keep_count"] == 1
    assert progress["prod_early_stop_eval_row_count"] == 2
    assert progress["prod_early_stop_metric_backend_counts"] == {"torch_batch": 1}


def test_run_batch_records_writer_backpressure_telemetry(tmp_path, monkeypatch) -> None:
    queue_csv = tmp_path / "queue.csv"
    pd.DataFrame(
        [
            {"queue_id": "q1", "target": "T1", "ligand_id": "L1", "ligand_mw": 200.0},
            {"queue_id": "q2", "target": "T1", "ligand_id": "L2", "ligand_mw": 200.0},
        ]
    ).to_csv(queue_csv, index=False)

    def _fake_load_protein_coords(target: str, native_path: str) -> np.ndarray:
        return np.zeros((2, 3), dtype=np.float32)

    def _fake_simulate_with_engine_batch(
        protein: np.ndarray,
        ligand0_batch: np.ndarray,
        pocket_batch: np.ndarray,
        **kwargs,
    ):
        selected = np.asarray(ligand0_batch[:, None, :, :], dtype=np.float32)
        frame_idx = np.asarray([0], dtype=np.int32)
        batch_size = int(ligand0_batch.shape[0])
        return (
            selected,
            frame_idx,
            "rust_hip",
            1,
            False,
            1,
            {
                "prod_early_stop_metric_backend_counts": {},
                "prod_early_stop_eval_keep_count": 0,
                "prod_early_stop_eval_row_count": batch_size,
            },
        )

    def _fake_write_trajectory_artifact(**kwargs) -> int:
        time.sleep(0.02)
        ligand_frames = np.asarray(kwargs["ligand_frames"])
        return int(ligand_frames.shape[0]) if ligand_frames.ndim >= 1 else 0

    monkeypatch.setattr(mod, "_load_protein_coords", _fake_load_protein_coords)
    monkeypatch.setattr(mod, "_simulate_with_engine_batch", _fake_simulate_with_engine_batch)
    monkeypatch.setattr(mod, "_write_trajectory_artifact", _fake_write_trajectory_artifact)

    progress_json = tmp_path / "progress.json"
    summary = mod.run_batch(
        mod.build_parser().parse_args(
            [
                "--queue-csv",
                str(queue_csv),
                "--out-root",
                str(tmp_path / "out"),
                "--out-progress-json",
                str(progress_json),
                "--out-summary-json",
                str(tmp_path / "summary.json"),
                "--out-summary-md",
                str(tmp_path / "summary.md"),
                "--out-manifest-csv",
                str(tmp_path / "manifest.csv"),
                "--frame-output-format",
                "npz_bundle",
                "--job-batch-size",
                "2",
                "--writer-mode",
                "thread",
                "--writer-workers",
                "1",
                "--writer-max-pending",
                "1",
                "--progress-every-jobs",
                "1",
                "--no-fail-on-missing-native",
            ]
        )
    )

    progress = json.loads(progress_json.read_text(encoding="utf-8"))

    assert summary["ok_rows"] == 2
    assert summary["writer_mode"] == "thread"
    assert summary["writer_workers"] == 1
    assert summary["writer_max_pending"] == 1
    assert summary["writer_pending_peak"] >= 2
    assert summary["writer_backpressure_count"] >= 1
    assert progress["writer_pending_peak"] == summary["writer_pending_peak"]
    assert progress["writer_backpressure_count"] == summary["writer_backpressure_count"]


def test_write_trajectory_artifact_accepts_template_dict_for_npz_bundle(tmp_path) -> None:
    npz_path = tmp_path / "traj.npz"
    written = mod._write_trajectory_artifact(
        protein_ca=np.asarray([[0.0, 0.0, 0.0]], dtype=np.float32),
        ligand_frames=np.asarray([[[1.0, 0.0, 0.0], [2.0, 0.0, 0.0]]], dtype=np.float32),
        frame_indices=np.asarray([0], dtype=np.int32),
        frame_output_format="npz_bundle",
        npz_path=str(npz_path),
        tdir=str(tmp_path / "unused"),
        npz_compression="store",
        protein_atom_template={
            "ready": True,
            "template_coords": np.asarray([[0.0, 0.0, 0.0], [0.5, 0.5, 0.5]], dtype=np.float32),
        },
    )

    assert written == 1
    with np.load(npz_path, allow_pickle=False) as bundle:
        assert bundle["protein_atom_frames"].shape == (1, 2, 3)
        assert bundle["protein_atom_template_index"].shape == (2,)
        assert int(bundle["protein_atom_schema_version"]) == 1


def test_run_batch_surfaces_normalized_template_metadata_in_manifest(tmp_path, monkeypatch) -> None:
    queue_csv = tmp_path / "queue.csv"
    pd.DataFrame(
        [
            {
                "queue_id": "q1",
                "target": "T1",
                "ligand_id": "L1",
                "ligand_mw": 200.0,
            }
        ]
    ).to_csv(queue_csv, index=False)

    def _fake_load_protein_coords(target: str, native_path: str) -> np.ndarray:
        return np.zeros((2, 3), dtype=np.float32)

    def _fake_load_protein_atom_template(target: str, native_path: str):
        return {
            "ready": True,
            "source_path": "synthetic_template.pdb",
            "template_coords": np.asarray(
                [
                    [0.0, 0.0, 0.0],
                    [0.5, 0.5, 0.5],
                    [1.0, 1.0, 1.0],
                ],
                dtype=np.float32,
            ),
            "atom_residue_index": np.asarray([0, 1, 1], dtype=np.int32),
            "native_anchor_coords": np.asarray([[0.0, 0.0, 0.0], [1.0, 1.0, 1.0]], dtype=np.float32),
            "residue_count": 2,
            "atom_count": 3,
            "template_atoms": [],
        }

    def _fake_simulate_with_engine_batch(
        protein: np.ndarray,
        ligand0_batch: np.ndarray,
        pocket_batch: np.ndarray,
        **kwargs,
    ):
        selected = np.asarray(ligand0_batch[:, None, :, :], dtype=np.float32)
        frame_idx = np.asarray([0], dtype=np.int32)
        return (
            selected,
            frame_idx,
            "rust_hip",
            1,
            False,
            1,
            {
                "prod_early_stop_metric_backend_counts": {},
                "prod_early_stop_eval_keep_count": 0,
                "prod_early_stop_eval_row_count": 0,
            },
        )

    monkeypatch.setattr(mod, "_load_protein_coords", _fake_load_protein_coords)
    monkeypatch.setattr(mod, "_load_protein_atom_template", _fake_load_protein_atom_template)
    monkeypatch.setattr(mod, "_simulate_with_engine_batch", _fake_simulate_with_engine_batch)

    summary = mod.run_batch(
        mod.build_parser().parse_args(
            [
                "--queue-csv",
                str(queue_csv),
                "--out-root",
                str(tmp_path / "out"),
                "--out-progress-json",
                str(tmp_path / "progress.json"),
                "--out-summary-json",
                str(tmp_path / "summary.json"),
                "--out-summary-md",
                str(tmp_path / "summary.md"),
                "--out-manifest-csv",
                str(tmp_path / "manifest.csv"),
                "--frame-output-format",
                "npz_bundle",
                "--writer-workers",
                "0",
                "--progress-every-jobs",
                "1",
                "--no-fail-on-missing-native",
            ]
        )
    )

    manifest = pd.read_csv(tmp_path / "manifest.csv")

    assert summary["ok_rows"] == 1
    assert summary["protein_atom_template_ready_row_count"] == 1
    assert summary["protein_atom_template_source_type_counts"] == {"dict": 1}
    assert summary["protein_atom_npz_row_count"] == 1
    assert bool(manifest.loc[0, "protein_atom_template_ready"]) is True
    assert manifest.loc[0, "protein_atom_template_source_type"] == "dict"
    assert manifest.loc[0, "protein_atom_template_source_path"] == "synthetic_template.pdb"
    assert manifest.loc[0, "protein_atom_template_count"] == 3
    assert bool(manifest.loc[0, "protein_atom_frames_available"]) is True

"""Canonical backmapping consumer interception; no molecular work is executed."""
from __future__ import annotations

import argparse
import json

import pandas as pd
import pytest

from betelgeuze_engine.product import residual_score_shadow as shadow
from betelgeuze_engine.product.runners import backmapping_scoring as runner
from tests.unit.test_residual_score_shadow_contract import synthetic_checkpoint


def _args(path="", digest=""):
    return argparse.Namespace(residual_score_shadow_checkpoint=str(path), residual_score_shadow_checkpoint_sha256=digest)


def _frame():
    return pd.DataFrame([{"queue_id": "synthetic_a", "family": "synthetic_family", "raw_score": -50.,
                          "binding_score_composite_v4": 6., "mean_min_distance_A": 4., "export_rank": 2},
                         {"queue_id": "synthetic_b", "family": "synthetic_family", "raw_score": -50.,
                          "binding_score_composite_v4": 0., "mean_min_distance_A": 4., "export_rank": 1}], index=[7, 7])


def test_disabled_shadow_does_not_load_or_modify_frame(monkeypatch):
    monkeypatch.setattr(shadow, "load_residual_score_shadow", lambda *a, **kw: pytest.fail("disabled shadow loaded"))
    frame = _frame()
    output, meta = runner._apply_residual_score_model_shadow(frame, _args())
    assert output is frame
    assert meta["status"] == "disabled" and not meta["enabled"]
    assert meta["evaluated_rows"] == meta["rejected_rows"] == 0


def test_exact_saved_score_column_used_after_ranking_and_duplicates_preserved(tmp_path):
    path, digest, _ = synthetic_checkpoint(tmp_path, score_column="binding_score_composite_v4")
    frame = _frame()
    original = frame.copy(deep=True)
    output, meta = runner._apply_residual_score_model_shadow(frame, _args(path, digest))
    pd.testing.assert_frame_equal(output[original.columns], original)
    pd.testing.assert_frame_equal(frame, original)
    assert output["residual_model_shadow_corrected_score"].tolist() == [9., 4.5]
    assert output["residual_model_shadow_delta_force"].isna().all()
    assert output["residual_model_shadow_uncertainty"].isna().all()
    assert meta["requested_rows"] == meta["evaluated_rows"] == 2
    assert meta["rejected_rows"] == 0 and meta["ranking_effect"] == "none"
    assert not meta["production_checkpoint_ready"]


def test_missing_exact_score_source_never_falls_back_to_another_column(tmp_path):
    path, digest, _ = synthetic_checkpoint(tmp_path, score_column="binding_score_composite_v4")
    frame = _frame().drop(columns="binding_score_composite_v4")
    output, meta = runner._apply_residual_score_model_shadow(frame, _args(path, digest))
    assert meta["evaluated_rows"] == 0 and meta["rejected_rows"] == len(frame)
    assert meta["rejection_reason_counts"] == {"missing_required_training_feature:raw_score": 2}
    assert output["residual_model_shadow_corrected_score"].isna().all()


def test_invalid_rows_are_reported_without_dropping_successful_rows(tmp_path):
    path, digest, _ = synthetic_checkpoint(tmp_path, score_column="binding_score_composite_v4")
    frame = _frame()
    frame.iloc[1, frame.columns.get_loc("family")] = "unseen_family"
    output, meta = runner._apply_residual_score_model_shadow(frame, _args(path, digest))
    assert meta["status"] == "partially_evaluated"
    assert meta["requested_rows"] == 2 and meta["evaluated_rows"] == meta["rejected_rows"] == 1
    assert output["residual_model_shadow_status"].tolist() == ["evaluated", "rejected"]
    assert output["queue_id"].tolist() == frame["queue_id"].tolist()


@pytest.mark.parametrize("config", ["missing_hash", "wrong_hash", "missing_path", "legacy_aux"])
def test_bad_config_or_wrong_model_rejected_with_truthful_denominator(tmp_path, config):
    path, digest, _ = synthetic_checkpoint(tmp_path)
    if config == "missing_hash":
        digest = ""
    elif config == "wrong_hash":
        digest = "0" * 64
    elif config == "missing_path":
        path = ""
    else:
        import hashlib
        import torch
        aux = runner._AuxMLP(4, 2)
        torch.save({"state_dict": aux.state_dict(), "feature_names": ["raw_score"] * 4}, path)
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
    frame = _frame()
    output, meta = runner._apply_residual_score_model_shadow(frame, _args(path, digest))
    pd.testing.assert_frame_equal(output[frame.columns], frame)
    assert meta["status"] == "rejected"
    assert meta["evaluated_rows"] == 0 and meta["rejected_rows"] == meta["requested_rows"] == 2
    assert output["residual_model_shadow_delta_score"].isna().all()


@pytest.mark.parametrize("invalid_hash", [False, True])
def test_actual_canonical_pipeline_wires_shadow_without_changing_selection(tmp_path, monkeypatch, invalid_hash):
    queue = tmp_path / "synthetic_queue.csv"
    pd.DataFrame([{"queue_id": "synthetic_a", "target": "synthetic_target", "ligand_id": "literal_a",
                   "family": "synthetic_family", "raw_score": 6., "mean_min_distance_A": 4.,
                   "binding_energy_mmpbsa_kcal_mol_proxy": 0.},
                  {"queue_id": "synthetic_b", "target": "synthetic_target", "ligand_id": "literal_b",
                   "family": "synthetic_family", "raw_score": 0., "mean_min_distance_A": 4.,
                   "binding_energy_mmpbsa_kcal_mol_proxy": 2.}]).to_csv(queue, index=False)
    processed = []
    def synthetic_process(row, cfg):
        assert cfg["score_only"]
        processed.append(row["queue_id"])
        literal_metrics = {name: 0. for name in (
            "binding_energy_proxy", "stability_score", "contact_fraction", "binding_energy_mmpbsa_std",
            "ligand_mw", "ligand_logp", "ligand_rot_bonds", "ligand_h_donors", "ligand_h_acceptors",
            "ligand_affinity_hint", "ligand_onsps_norm")}
        return {**literal_metrics, **row}
    monkeypatch.setattr(runner, "_process_queue_row", synthetic_process)
    for name in ("mm_gbsa_binding_energy", "backmap_4bead_onsps", "ligand_topology_from_smiles", "evaluate_hbond_evidence"):
        monkeypatch.setattr(runner, name, lambda *a, **kw: pytest.fail("molecular work is forbidden"))
    original_rank = runner.rank_selection_frame
    def rank_before_diagnostics(frame, authority):
        assert not any(name.startswith("residual_model_shadow_") for name in frame.columns)
        return original_rank(frame, authority)
    monkeypatch.setattr(runner, "rank_selection_frame", rank_before_diagnostics)
    path, digest, _ = synthetic_checkpoint(tmp_path)
    common = ["--queue-csv", str(queue), "--workers", "1", "--score-only", "--no-two-pass-scoring", "--no-make-bundle-zip"]
    baseline_args = runner.build_parser().parse_args(common + ["--out-dir", str(tmp_path / "baseline")])
    baseline = runner.run_pipeline(baseline_args)["summary"]
    args = runner.build_parser().parse_args(common + ["--out-dir", str(tmp_path / "shadow"),
                                                     "--residual-score-shadow-checkpoint", str(path),
                                                     "--residual-score-shadow-checkpoint-sha256", "0" * 64 if invalid_hash else digest])
    result = runner.run_pipeline(args)["summary"]
    baseline_frame = pd.read_csv(baseline["artifacts"]["scores_csv"])
    result_frame = pd.read_csv(result["artifacts"]["scores_csv"])
    pd.testing.assert_frame_equal(result_frame[baseline_frame.columns], baseline_frame)
    assert result["selection_score_authority"] == baseline["selection_score_authority"]
    meta = result["residual_score_model_shadow"]
    assert meta["evaluated_rows"] == (0 if invalid_hash else 2)
    assert meta["rejected_rows"] == (2 if invalid_hash else 0)
    assert meta["requested_rows"] == result["processed_jobs"] == result["queue_rows"] == 2
    assert result["aux_model"] == baseline["aux_model"]
    assert result["residual_prototype"] == baseline["residual_prototype"]
    assert len(processed) == 4
    saved = json.loads((tmp_path / "shadow" / "summary.json").read_text())
    assert saved["residual_score_model_shadow"] == meta
    if not invalid_hash:
        values = result_frame.set_index("queue_id")["residual_model_shadow_corrected_score"].to_dict()
        assert values == {"synthetic_a": 9., "synthetic_b": 4.5}


def test_actual_synthetic_trainer_checkpoint_roundtrips_into_shadow(tmp_path):
    import hashlib
    import torch
    from tools import train_residual_production_score_model as trainer

    # Eight literal tabular development rows; one CPU epoch validates artifact
    # compatibility, not biochemical performance or real-data training.
    rows = [{"ligand_id": f"fresh_literal_{i}", "target": "synthetic_target", "family": "synthetic_family",
             "role": "fit", "is_binder": i % 2, "raw_score": float(i % 4),
             "mean_min_distance_A": 3., "delta_score": float(i % 3) / 10.} for i in range(8)]
    dataset = tmp_path / "fresh_literal_training.csv"
    pd.DataFrame(rows).to_csv(dataset, index=False)
    checkpoint = tmp_path / "fresh_cpu_candidate.pt"
    summary = trainer.train_residual_production_score_model(
        input_csv=str(dataset), out_checkpoint=str(checkpoint), epochs=1, hidden_dim=2,
        batch_size=4, device_name="cpu", force_derivation_json="/dev/null")
    digest = hashlib.sha256(checkpoint.read_bytes()).hexdigest()
    model = shadow.load_residual_score_shadow(checkpoint, expected_sha256=digest)
    state = torch.load(checkpoint, map_location="cpu", weights_only=True)
    assert summary["shadow_inference_contract"] == state["shadow_inference_contract"] == model.contract
    assert summary["checkpoint_sha256"] == digest
    assert summary["train_fingerprint_digest"] == model.training_fingerprint_digest
    raw, *_, names = trainer._matrix(rows, state["families"], [], refine_fields=[])
    normalized = (raw - state["x_mean"]) / state["x_std"]
    for name in state["neutralized_feature_names"]:
        normalized[:, names.index(name)] = 0.
    independent = trainer.ResidualScoreMLP(len(names), 2)
    independent.load_state_dict(state["state_dict"], strict=True)
    with torch.no_grad():
        logits, delta, _energy, _force = independent(normalized)
    prediction = model.predict_rows(rows)
    assert [item["status"] for item in prediction] == ["evaluated"] * len(rows)
    assert [item["binder_logit"] for item in prediction] == pytest.approx(logits.tolist(), abs=1e-6)
    assert [item["delta_score"] for item in prediction] == pytest.approx(delta.tolist(), abs=1e-6)
    assert [item["corrected_score"] for item in prediction] == pytest.approx((raw[:, 0] + delta).tolist(), abs=1e-6)
    assert all(item["delta_force"] is None and item["uncertainty"] is None for item in prediction)
    assert not summary["production_checkpoint_ready"] and not summary["model_promoted"]

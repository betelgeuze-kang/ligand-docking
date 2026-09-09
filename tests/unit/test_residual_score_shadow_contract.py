"""Fresh tabular CPU controls; synthetic weights only, no data or fitting."""
from __future__ import annotations

import copy
import hashlib
import json

import pytest
import torch

from betelgeuze_engine.product import residual_score_contract as contract
from betelgeuze_engine.product import residual_score_shadow as shadow
from tools import train_residual_production_score_model as trainer


def synthetic_checkpoint(tmp_path, *, mutate=None, score_column="raw_score"):
    """Known affine/ReLU controls, written independently of the trainer save path."""
    families = ["synthetic_family"]
    schema = contract.shadow_contract(rows=[{"score_col": score_column}], families=families,
                                      refine_fields=[], hidden_dim=2)
    with torch.random.fork_rng(devices=[]):
        model = contract.ResidualScoreMLP(4, 2)
    with torch.no_grad():
        for parameter in model.parameters():
            parameter.zero_()
        model.trunk[0].weight.copy_(torch.tensor([[1., 2., 0., 0.], [-1., .5, 0., 0.]]))
        model.trunk[2].weight.copy_(torch.eye(2))
        model.cls_head.weight.copy_(torch.tensor([[1., -1.]]))
        model.cls_head.bias.fill_(2.)
        model.delta_head.weight.copy_(torch.tensor([[.5, 2.]]))
        model.delta_head.bias.fill_(1.)
        model.energy_head.bias.fill_(12.)
        model.force_head.bias.fill_(999.)
        model.forbidden_missing_features[2] = True
    fingerprint = {"input_csv_sha256": "a" * 64, "trainer_source_sha256": "b" * 64,
                   "evaluation_policy_source_sha256": "c" * 64, "hidden_dim": 2,
                   "trainer_contract_version": trainer.TRAINER_CONTRACT_VERSION,
                   "shared_contract_source_sha256": contract.source_sha256()}
    fingerprint["digest"] = hashlib.sha256(json.dumps(fingerprint, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    learned = ["delta_score", "corrected_score"]
    policy = ["abstention_reason", "stage2_route_decision"]
    payload = {"shadow_inference_contract": schema, "model_role": contract.MODEL_ROLE,
               "trainer_contract_version": trainer.TRAINER_CONTRACT_VERSION,
               "feature_names": schema["feature_names"], "families": families, "roles": [],
               "feature_stage": "post_refinement_rescoring", "role_features_used": False,
               "evaluation_only_inputs_rejected": True,
               "feature_missingness_policy": "required_raw_score_optional_value_and_indicator",
               "constant_feature_policy": "zero_normalized_inputs_and_first_layer_weights",
               "unseen_missingness_policy": "reject_for_varying_fully_observed_training_features",
               "neutralized_feature_names": ["mean_min_distance_A_missing", "family=synthetic_family"],
               "forbidden_missing_feature_names": ["mean_min_distance_A_missing"],
               "x_mean": torch.tensor([2., 3., 0., 1.]), "x_std": torch.tensor([2., 1., 1., 1.]),
               "state_dict": copy.deepcopy(model.state_dict()),
               "train_fingerprint": fingerprint, "train_fingerprint_digest": fingerprint["digest"],
               "uncertainty_calibrated": False, "physical_energy_residual_validated": False,
               "delta_force_head_trained": False, "delta_force_head_supervised": False,
               "delta_force_head_derivation_stub": False, "delta_energy_head_trained": False,
               "delta_force_training_status": "not_implemented_no_force_loss_or_coordinate_gradient",
               "learned_output_fields": learned, "policy_output_fields": policy, "output_fields": learned + policy}
    if mutate:
        mutate(payload)
    path = tmp_path / "fresh_synthetic_weights.pt"
    torch.save(payload, path)
    return path, hashlib.sha256(path.read_bytes()).hexdigest(), payload


@pytest.fixture(autouse=True)
def no_fitting(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("real or synthetic fitting is not needed for serving contract controls")
    monkeypatch.setattr(torch.optim, "Adam", forbidden)


def _row(**updates):
    return {"family": "synthetic_family", "raw_score": 6., "mean_min_distance_A": 4., **updates}


def test_saved_statistics_and_exact_weights_match_independent_relu_oracle(tmp_path):
    path, digest, _ = synthetic_checkpoint(tmp_path)
    model = shadow.load_residual_score_shadow(path, expected_sha256=digest)
    row = _row()
    result = model.predict_rows([row])[0]
    # Normalized [2,1,0,0] -> ReLU [4,0] -> cls6, delta3.
    assert result == {"status": "evaluated", "reason": "", "binder_logit": 6., "delta_score": 3.,
                      "corrected_score": 9., "delta_energy": None, "delta_force": None, "uncertainty": None}
    # Inference is per row and independent of other values or batch ordering.
    assert model.predict_rows([_row(raw_score=-999.), row])[1] == result
    assert model.predict_rows([row, row]) == [result, result]
    assert model.std[1].item() == 1.  # Active std=1 was not mistaken for inactive.


def test_loading_does_not_change_rng_and_strict_load_is_cpu(tmp_path):
    path, digest, _ = synthetic_checkpoint(tmp_path)
    rng = torch.random.get_rng_state().clone()
    model = shadow.load_residual_score_shadow(path, expected_sha256=digest)
    assert torch.equal(torch.random.get_rng_state(), rng)
    assert not model.model.training
    assert all(value.device.type == "cpu" for value in model.model.state_dict().values())


def test_shared_encoder_preserves_training_order_and_explicit_zero_missingness():
    rows = [dict(_row(raw_score=0., mean_min_distance_A=0.), role="fit", is_binder=1, delta_score=0., refine_confidence=0.),
            dict(_row(raw_score=2., mean_min_distance_A=None), role="fit", is_binder=0, delta_score=1., refine_confidence="")]
    x, *_, names = trainer._matrix(rows, ["synthetic_family"], [], refine_fields=["refine_confidence"])
    assert names == ["raw_score", "mean_min_distance_A", "mean_min_distance_A_missing", "family=synthetic_family",
                     "refine_confidence", "refine_confidence_missing"]
    assert x.tolist() == [[0., 0., 0., 1., 0., 0.], [2., 0., 1., 1., 0., 1.]]
    assert trainer.ResidualScoreMLP is contract.ResidualScoreMLP


@pytest.mark.parametrize("missing", [None, "", "  "])
def test_raw_missing_indicator_checked_before_neutralization(tmp_path, missing):
    path, digest, _ = synthetic_checkpoint(tmp_path)
    model = shadow.load_residual_score_shadow(path, expected_sha256=digest)
    measured, absent = model.predict_rows([_row(mean_min_distance_A=0.), _row(mean_min_distance_A=missing)])
    assert measured["status"] == "evaluated"
    assert absent["reason"] == "unseen_training_missingness"
    assert absent["delta_score"] is None


def test_seen_missingness_is_encoded_and_distinct_from_measured_zero(tmp_path):
    def seen(payload):
        payload["forbidden_missing_feature_names"] = []
        payload["neutralized_feature_names"] = ["family=synthetic_family"]
        payload["state_dict"]["forbidden_missing_features"].zero_()
        payload["state_dict"]["trunk.0.weight"][0, 2] = 3.
        payload["x_mean"][2] = .5
        payload["x_std"][2] = .5
    path, digest, _ = synthetic_checkpoint(tmp_path, mutate=seen)
    results = shadow.load_residual_score_shadow(path, expected_sha256=digest).predict_rows([
        _row(raw_score=20., mean_min_distance_A=0.), _row(raw_score=20., mean_min_distance_A=None)])
    assert [item["status"] for item in results] == ["evaluated", "evaluated"]
    assert results[0]["delta_score"] != results[1]["delta_score"]


@pytest.mark.parametrize("field,value,reason", [
    ("raw_score", None, "missing_required_training_feature:raw_score"),
    ("raw_score", True, "invalid_training_feature:raw_score"),
    ("raw_score", float("nan"), "invalid_training_feature:raw_score"),
    ("raw_score", float("inf"), "invalid_training_feature:raw_score"),
    ("raw_score", 1e40, "invalid_training_feature:raw_score"),
    ("raw_score", "not-a-score", "invalid_training_feature:raw_score"),
    ("mean_min_distance_A", -1., "invalid_training_feature:mean_min_distance_A"),
    ("mean_min_distance_A", float("nan"), "invalid_training_feature:mean_min_distance_A"),
    ("family", "Synthetic_family", "unseen_family"),
    ("family", " synthetic_family", "unseen_family"),
    ("family", None, "unseen_family"),
])
def test_row_rejection_preserves_denominator_and_order(tmp_path, field, value, reason):
    path, digest, _ = synthetic_checkpoint(tmp_path)
    model = shadow.load_residual_score_shadow(path, expected_sha256=digest)
    result = model.predict_rows([_row(), _row(**{field: value}), _row(raw_score=0.)])
    assert len(result) == 3
    assert [item["status"] for item in result] == ["evaluated", "rejected", "evaluated"]
    assert result[1]["reason"] == reason
    assert result[1]["corrected_score"] is None


@pytest.mark.parametrize("field,value,reason", [
    ("model_role", "aux_binding", "model_role_mismatch"),
    ("trainer_contract_version", "legacy", "trainer_contract_mismatch"),
    ("roles", ["fit"], "role_features_not_allowed"),
    ("feature_names", ["raw_score"], "feature_order_mismatch"),
    ("families", ["other"], "family_vocabulary_mismatch"),
    ("x_mean", torch.zeros(3), "invalid_normalization_mean"),
    ("x_std", torch.ones(4, dtype=torch.float64), "invalid_normalization_std"),
    ("x_std", torch.tensor([0., 1., 1., 1.]), "nonpositive_normalization_std"),
    ("x_std", torch.tensor([float("nan"), 1., 1., 1.]), "invalid_normalization_std"),
    ("delta_force_head_trained", True, "checkpoint_policy_mismatch:delta_force_head_trained"),
    ("uncertainty_calibrated", True, "checkpoint_policy_mismatch:uncertainty_calibrated"),
    ("neutralized_feature_names", ["raw_score"], "inactive_normalization_mismatch"),
    ("forbidden_missing_feature_names", [], "state_missingness_buffer_mismatch"),
    ("state_dict", {"net.0.weight": torch.ones(2, 4)}, "state_keys_mismatch"),
    ("shadow_inference_contract", None, "missing_shadow_inference_contract"),
])
def test_checkpoint_contract_mismatches_fail_closed(tmp_path, field, value, reason):
    path, digest, _ = synthetic_checkpoint(tmp_path, mutate=lambda payload: payload.update({field: value}))
    with pytest.raises(shadow.ResidualScoreShadowError, match=reason):
        shadow.load_residual_score_shadow(path, expected_sha256=digest)


@pytest.mark.parametrize("mutation,reason", [
    (lambda p: p["shadow_inference_contract"].update(shared_source_sha256="d" * 64), "shadow_contract_mismatch:shared_source_sha256"),
    (lambda p: p["shadow_inference_contract"].update(schema_version="future"), "shadow_contract_mismatch:schema_version"),
    (lambda p: p["shadow_inference_contract"].update(in_dim=5), "input_dimension_mismatch"),
    (lambda p: p["shadow_inference_contract"].update(hidden_dim=True), "unsupported_hidden_dimension"),
    (lambda p: p["shadow_inference_contract"].update(input_score_column="affinity"), "unsupported_input_score_column"),
    (lambda p: p["train_fingerprint"].update(input_csv_sha256="d" * 64), "training_fingerprint_digest_mismatch"),
    (lambda p: p["train_fingerprint"].update(shared_contract_source_sha256="d" * 64), "fingerprint_source_mismatch"),
    (lambda p: p["state_dict"].update(**{"cls_head.bias": torch.zeros(2)}), "state_tensor_mismatch:cls_head.bias"),
    (lambda p: p["state_dict"]["trunk.0.weight"].__setitem__((0, 2), 1.), "inactive_weights_not_zero"),
    (lambda p: p["state_dict"]["delta_head.bias"].fill_(float("inf")), "state_tensor_mismatch:delta_head.bias"),
])
def test_bound_source_schema_and_state_rejections(tmp_path, mutation, reason):
    path, digest, _ = synthetic_checkpoint(tmp_path, mutate=mutation)
    with pytest.raises(shadow.ResidualScoreShadowError, match=reason):
        shadow.load_residual_score_shadow(path, expected_sha256=digest)


@pytest.mark.parametrize("digest,reason", [("", "checkpoint_sha256_required"), ("z" * 64, "checkpoint_sha256_required"),
                                          ("0" * 64, "checkpoint_sha256_mismatch")])
def test_hash_checked_before_deserialization(tmp_path, monkeypatch, digest, reason):
    path, _, _ = synthetic_checkpoint(tmp_path)
    monkeypatch.setattr(torch, "load", lambda *a, **kw: pytest.fail("unverified checkpoint deserialized"))
    with pytest.raises(shadow.ResidualScoreShadowError, match=reason):
        shadow.load_residual_score_shadow(path, expected_sha256=digest)


def test_corrupt_verified_bytes_rejected_without_pickle_fallback(tmp_path):
    path = tmp_path / "not_a_checkpoint.pt"
    path.write_bytes(b"synthetic broken archive")
    with pytest.raises(shadow.ResidualScoreShadowError, match="checkpoint_decode_rejected"):
        shadow.load_residual_score_shadow(path, expected_sha256=hashlib.sha256(path.read_bytes()).hexdigest())


@pytest.mark.parametrize("stage", ["normalize", "linear", "corrected"])
def test_finite_inputs_and_weights_cannot_publish_overflow(tmp_path, stage):
    def overflow(payload):
        if stage == "normalize":
            payload["x_mean"][0] = -3e38
        elif stage == "linear":
            payload["state_dict"]["trunk.0.weight"][0, 0] = 3e38
        else:
            payload["state_dict"]["delta_head.weight"].zero_()
            payload["state_dict"]["delta_head.bias"].fill_(3e38)
    path, digest, _ = synthetic_checkpoint(tmp_path, mutate=overflow)
    result = shadow.load_residual_score_shadow(path, expected_sha256=digest).predict_rows([
        _row(raw_score=3e38 if stage != "linear" else 6.)])[0]
    assert result["status"] == "rejected"
    assert result["reason"].startswith("nonfinite_")
    assert result["corrected_score"] is None


def test_energy_only_reported_for_explicit_trained_head_and_remains_diagnostic(tmp_path):
    def energy(payload):
        payload["delta_energy_head_trained"] = True
        payload["delta_energy_train_label_rows"] = 10
        payload["learned_output_fields"].append("delta_energy")
        payload["output_fields"] = payload["learned_output_fields"] + payload["policy_output_fields"]
    path, digest, _ = synthetic_checkpoint(tmp_path, mutate=energy)
    model = shadow.load_residual_score_shadow(path, expected_sha256=digest)
    prediction = model.predict_rows([_row()])[0]
    assert prediction["delta_energy"] == 12.
    assert prediction["delta_force"] is None and prediction["uncertainty"] is None
    assert model.contract["output_semantics"] == "diagnostic_score_proxy_not_affinity_or_physical_energy"


def test_contract_does_not_mix_source_score_endpoints():
    with pytest.raises(ValueError, match="ambiguous_or_unsupported_residual_score_source"):
        contract.shadow_contract(rows=[{"score_col": "raw_score"}, {"score_col": "binding_score_composite_v4"}],
                                 families=["synthetic_family"], refine_fields=[], hidden_dim=2)


@pytest.mark.parametrize("default_dtype", [torch.float32, torch.float64])
def test_shadow_stays_cpu_when_caller_default_device_is_not_cpu(tmp_path, default_dtype):
    path, digest, _ = synthetic_checkpoint(tmp_path)
    # Meta is an allocation-only device; this does not execute a GPU workload.
    previous_dtype = torch.get_default_dtype()
    try:
        torch.set_default_dtype(default_dtype)
        with torch.device("meta"):
            model = shadow.load_residual_score_shadow(path, expected_sha256=digest)
            result = model.predict_rows([_row()])[0]
    finally:
        torch.set_default_dtype(previous_dtype)
    assert result["status"] == "evaluated"
    assert result["corrected_score"] == 9.
    assert all(tensor.device.type == "cpu" for tensor in model.model.state_dict().values())
    assert all(tensor.dtype == torch.float32 for tensor in model.model.parameters())


def test_shadow_float32_contract_is_independent_of_caller_cpu_autocast(tmp_path):
    path, digest, _ = synthetic_checkpoint(tmp_path)
    model = shadow.load_residual_score_shadow(path, expected_sha256=digest)
    row = _row(raw_score=6.1)
    expected = model.predict_rows([row])
    assert expected[0]["binder_logit"] == pytest.approx(6.05, abs=1e-6)
    with torch.autocast(device_type="cpu", dtype=torch.bfloat16):
        actual = model.predict_rows([row])
    assert actual == expected

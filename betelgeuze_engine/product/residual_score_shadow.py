"""Strict CPU diagnostics for the versioned residual score candidate.

This module never selects, ranks, calibrates or promotes a model. A checkpoint
hash is mandatory: loading an arbitrary path is not a serving contract.
"""
from __future__ import annotations

import hashlib
import io
import json
import math
import re
from pathlib import Path
from typing import Any

import torch

from .residual_score_contract import (
    MODEL_ROLE, SCORE_COLUMNS, SHADOW_SCHEMA, ResidualScoreMLP,
    encode_features, feature_schema, source_sha256,
)


class ResidualScoreShadowError(ValueError):
    """The requested diagnostic cannot be evaluated under its saved contract."""


def _require(condition: bool, reason: str) -> None:
    if not condition:
        raise ResidualScoreShadowError(reason)


def _sha(value: Any) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def _names(value: Any, names: list[str], reason: str) -> list[str]:
    _require(isinstance(value, list), reason)
    _require(all(isinstance(item, str) and item in names for item in value), reason)
    _require(value == [name for name in names if name in value], reason)
    return value


def _float_tensor(value: Any, shape: tuple[int, ...], reason: str) -> torch.Tensor:
    _require(isinstance(value, torch.Tensor), reason)
    _require(value.dtype == torch.float32 and value.layout == torch.strided and tuple(value.shape) == shape, reason)
    _require(value.device.type == "cpu" and bool(torch.isfinite(value).all().item()), reason)
    return value


class ResidualScoreShadow:
    def __init__(self, payload: dict[str, Any], checkpoint_sha256: str):
        contract = payload.get("shadow_inference_contract")
        _require(isinstance(contract, dict), "missing_shadow_inference_contract")
        expected = {
            "schema_version": SHADOW_SCHEMA, "architecture": "ResidualScoreMLP_v1",
            "shared_source_sha256": source_sha256(), "dtype": "float32",
            "feature_stage": "post_refinement_rescoring",
            "output_semantics": "diagnostic_score_proxy_not_affinity_or_physical_energy",
            "ranking_effect": "none",
        }
        for key, value in expected.items():
            _require(contract.get(key) == value, f"shadow_contract_mismatch:{key}")
        _require(set(contract) == set(expected) | {"feature_names", "families", "refine_feature_fields",
                                                   "in_dim", "hidden_dim", "input_score_column"},
                 "shadow_contract_schema_mismatch")
        _require(payload.get("model_role") == MODEL_ROLE, "model_role_mismatch")
        _require(payload.get("trainer_contract_version") == "score_candidate_integrity_v3", "trainer_contract_mismatch")
        for key, value in {"feature_stage": "post_refinement_rescoring", "role_features_used": False,
                           "evaluation_only_inputs_rejected": True,
                           "feature_missingness_policy": "required_raw_score_optional_value_and_indicator",
                           "constant_feature_policy": "zero_normalized_inputs_and_first_layer_weights",
                           "unseen_missingness_policy": "reject_for_varying_fully_observed_training_features",
                           "uncertainty_calibrated": False, "physical_energy_residual_validated": False,
                           "delta_force_head_trained": False, "delta_force_head_supervised": False,
                           "delta_force_head_derivation_stub": False,
                           "delta_force_training_status": "not_implemented_no_force_loss_or_coordinate_gradient"}.items():
            _require(payload.get(key) == value and type(payload.get(key)) is type(value), f"checkpoint_policy_mismatch:{key}")
        _require(payload.get("production_checkpoint_ready", False) is False, "production_checkpoint_not_shadow")
        _require(payload.get("roles") == [], "role_features_not_allowed")
        families, refine = contract.get("families"), contract.get("refine_feature_fields")
        try:
            names = feature_schema(families, refine)
        except (ValueError, TypeError) as exc:
            raise ResidualScoreShadowError("invalid_feature_schema") from exc
        _require(bool(families), "empty_family_vocabulary")
        _require(names == payload.get("feature_names") == contract.get("feature_names"), "feature_order_mismatch")
        _require(families == payload.get("families"), "family_vocabulary_mismatch")
        in_dim, hidden_dim = contract.get("in_dim"), contract.get("hidden_dim")
        _require(type(in_dim) is int and in_dim == len(names) and 0 < in_dim <= 128, "input_dimension_mismatch")
        _require(type(hidden_dim) is int and 0 < hidden_dim <= 4096, "unsupported_hidden_dimension")
        _require(contract.get("input_score_column") in SCORE_COLUMNS, "unsupported_input_score_column")
        fingerprint = payload.get("train_fingerprint")
        _require(isinstance(fingerprint, dict), "missing_training_fingerprint")
        _require(fingerprint.get("hidden_dim") == hidden_dim, "fingerprint_dimension_mismatch")
        _require(fingerprint.get("trainer_contract_version") == payload["trainer_contract_version"], "fingerprint_contract_mismatch")
        _require(fingerprint.get("shared_contract_source_sha256") == source_sha256(), "fingerprint_source_mismatch")
        for key in ("input_csv_sha256", "trainer_source_sha256", "evaluation_policy_source_sha256", "digest"):
            _require(_sha(fingerprint.get(key)), f"invalid_training_fingerprint:{key}")
        try:
            raw = json.dumps({key: value for key, value in fingerprint.items() if key != "digest"},
                             sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
        except (TypeError, ValueError) as exc:
            raise ResidualScoreShadowError("invalid_training_fingerprint") from exc
        _require(hashlib.sha256(raw).hexdigest() == fingerprint["digest"] == payload.get("train_fingerprint_digest"),
                 "training_fingerprint_digest_mismatch")
        self.mean = _float_tensor(payload.get("x_mean"), (in_dim,), "invalid_normalization_mean")
        self.std = _float_tensor(payload.get("x_std"), (in_dim,), "invalid_normalization_std")
        _require(bool((self.std > 0).all().item()), "nonpositive_normalization_std")
        inactive = _names(payload.get("neutralized_feature_names"), names, "invalid_neutralized_features")
        forbidden = _names(payload.get("forbidden_missing_feature_names"), names, "invalid_forbidden_missing_features")
        self.inactive = torch.tensor([name in inactive for name in names], dtype=torch.bool, device="cpu")
        self.forbidden = torch.tensor([name in forbidden for name in names], dtype=torch.bool, device="cpu")
        _require(bool((self.std[self.inactive] == 1).all().item()), "inactive_normalization_mismatch")
        for name in forbidden:
            _require(name.endswith("_missing") and name[:-8] in names and name in inactive and name[:-8] not in inactive,
                     "forbidden_missingness_schema_mismatch")
            _require(self.mean[names.index(name)].item() == 0.0, "forbidden_missingness_mean_mismatch")
        state = payload.get("state_dict")
        shapes = {"trunk.0.weight": (hidden_dim, in_dim), "trunk.0.bias": (hidden_dim,),
                  "trunk.2.weight": (hidden_dim, hidden_dim), "trunk.2.bias": (hidden_dim,)}
        for head in ("cls_head", "delta_head", "energy_head", "force_head"):
            shapes[f"{head}.weight"] = (1, hidden_dim)
            shapes[f"{head}.bias"] = (1,)
        _require(isinstance(state, dict) and set(state) == set(shapes) | {"forbidden_missing_features"}, "state_keys_mismatch")
        for key, shape in shapes.items():
            _float_tensor(state[key], shape, f"state_tensor_mismatch:{key}")
        flag = state["forbidden_missing_features"]
        _require(isinstance(flag, torch.Tensor) and flag.dtype == torch.bool and flag.layout == torch.strided and
                 flag.device.type == "cpu" and torch.equal(flag, self.forbidden), "state_missingness_buffer_mismatch")
        _require(bool((state["trunk.0.weight"][:, self.inactive] == 0).all().item()), "inactive_weights_not_zero")
        energy_trained = payload.get("delta_energy_head_trained")
        _require(type(energy_trained) is bool, "missing_energy_head_status")
        learned = ["delta_score", "corrected_score"] + (["delta_energy"] if energy_trained else [])
        _require(payload.get("learned_output_fields") == learned, "learned_outputs_mismatch")
        _require(payload.get("policy_output_fields") == ["abstention_reason", "stage2_route_decision"], "policy_outputs_mismatch")
        _require(payload.get("output_fields") == learned + payload["policy_output_fields"], "output_fields_mismatch")
        if energy_trained:
            count = payload.get("delta_energy_train_label_rows")
            _require(type(count) is int and count >= 10, "energy_training_evidence_missing")
        # Loading must not consume or replace caller RNG state. All weights are
        # checked above and loaded strictly before the model can be evaluated.
        with torch.random.fork_rng(devices=[]), torch.device("cpu"):
            self.model = ResidualScoreMLP(in_dim, hidden_dim).to(dtype=torch.float32)
        self.model.load_state_dict(state, strict=True)
        self.model.eval()
        self.contract = dict(contract)
        self.checkpoint_sha256 = checkpoint_sha256
        self.training_fingerprint_digest = fingerprint["digest"]
        self.energy_trained = energy_trained

    def predict_rows(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        predictions = []
        for row in rows:
            rejected = {"status": "rejected", "reason": "", "binder_logit": None,
                        "delta_score": None, "corrected_score": None, "delta_energy": None,
                        "delta_force": None, "uncertainty": None}
            try:
                _require(isinstance(row, dict), "invalid_input_row")
                family = str(row.get("family") or "unknown")
                _require(family in self.contract["families"], "unseen_family")
                raw, _ = encode_features([row], self.contract["families"], self.contract["refine_feature_fields"])
                # Check original indicators first: those columns were constant
                # zero during fit and will be zeroed by the inactive policy.
                _require(not bool((raw[:, self.forbidden] != 0).any().item()), "unseen_training_missingness")
                normalized = (raw - self.mean) / self.std
                _require(bool(torch.isfinite(normalized).all().item()), "nonfinite_normalized_features")
                normalized[:, self.inactive] = 0.0
                with torch.inference_mode(), torch.autocast(device_type="cpu", enabled=False):
                    outputs = self.model(normalized)
                    _require(all(value.dtype == torch.float32 for value in outputs), "model_output_dtype_mismatch")
                    _require(all(bool(torch.isfinite(value).all().item()) for value in outputs), "nonfinite_model_output")
                    logit, delta, energy, _force = (value.item() for value in outputs)
                    corrected = float((raw[0, 0] + outputs[1][0]).item())
                _require(math.isfinite(corrected), "nonfinite_corrected_score")
                predictions.append({**rejected, "status": "evaluated", "reason": "",
                                    "binder_logit": logit, "delta_score": delta, "corrected_score": corrected,
                                    "delta_energy": energy if self.energy_trained else None})
            except (ValueError, TypeError, OverflowError) as exc:
                predictions.append({**rejected, "reason": str(exc)})
        return predictions


def load_residual_score_shadow(checkpoint_path: str | Path, *, expected_sha256: str) -> ResidualScoreShadow:
    _require(_sha(expected_sha256), "checkpoint_sha256_required")
    try:
        data = Path(checkpoint_path).read_bytes()
    except (OSError, TypeError, ValueError) as exc:
        raise ResidualScoreShadowError("checkpoint_unreadable") from exc
    _require(hashlib.sha256(data).hexdigest() == expected_sha256, "checkpoint_sha256_mismatch")
    try:
        payload = torch.load(io.BytesIO(data), map_location="cpu", weights_only=True)
    except Exception as exc:
        raise ResidualScoreShadowError("checkpoint_decode_rejected") from exc
    _require(isinstance(payload, dict), "checkpoint_payload_not_mapping")
    try:
        return ResidualScoreShadow(payload, expected_sha256)
    except ResidualScoreShadowError:
        raise
    except (ValueError, TypeError, KeyError, RuntimeError, OverflowError) as exc:
        raise ResidualScoreShadowError("checkpoint_contract_validation_failed") from exc

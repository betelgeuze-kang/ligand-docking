from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest


torch = pytest.importorskip("torch")
yaml = pytest.importorskip("yaml")

from betelgeuze_engine_v2.capabilities import (  # noqa: E402
    capability_snapshot,
    require_capability_snapshot,
)
from betelgeuze_engine_v2.runtime import (  # noqa: E402
    RESIDUE_UNK_ID,
    RESIDUE_VOCABULARY,
    RESIDUE_VOCABULARY_SIZE,
    ResidueVocabularyError,
    RuntimeConditioningError,
    build_runtime_conditioning_batch,
    model_architecture_fingerprint,
    normalize_residue_ids,
    residue_one_hot,
    runtime_contract_fingerprint,
    state_dict_fingerprint,
)
from core.ai_correction import NeuralForceCorrection  # noqa: E402
from core.sim_param_schema import ScalarConditioningError, coerce_sim_param_float  # noqa: E402
from train.checkpoint_contracts import (  # noqa: E402
    CheckpointContractError,
    CheckpointStateCoverageError,
    checkpoint_contract_metadata,
    load_checkpoint_payload_fail_closed,
    load_state_dict_fail_closed,
)
from train.runtime_inputs import (  # noqa: E402
    RUNTIME_INPUT_SCHEMA_ID,
    build_runtime_inputs,
    resolve_sim_params,
    resolve_sim_params_batch,
    runtime_input_schema_metadata,
)


def test_residue_vocabulary_has_explicit_unk_and_no_modulo_alias() -> None:
    ids = torch.tensor([[1, 20, 21, 65, -3]], dtype=torch.long)
    normalized, unknown = normalize_residue_ids(ids)
    assert normalized.tolist() == [[1, 20, RESIDUE_UNK_ID, RESIDUE_UNK_ID, RESIDUE_UNK_ID]]
    assert unknown.tolist() == [[False, False, True, True, True]]

    encoded, diagnostics = residue_one_hot(ids, output_width=64)
    assert encoded.shape == (1, 5, 64)
    assert int(encoded[0, 0].argmax()) == 1
    assert int(encoded[0, 3].argmax()) == RESIDUE_UNK_ID
    assert diagnostics["modulo_aliasing_used"] is False
    assert diagnostics["size"] == RESIDUE_VOCABULARY_SIZE
    assert len(diagnostics["fingerprint_sha256"]) == 64

    with pytest.raises(ResidueVocabularyError, match="outside"):
        normalize_residue_ids(ids, unknown_policy="error")


def test_runtime_conditioning_preserves_batch_and_scalar_path_requires_uniformity() -> None:
    conditions = build_runtime_conditioning_batch(
        {"temp": torch.tensor([280.0, 320.0]), "pH": 7.2},
        defaults={"temp": 300.0, "pH": 7.0},
        keys=("temp", "pH"),
        batch_size=2,
        dtype=torch.float64,
        device="cpu",
    )
    assert conditions.values.tolist() == [[280.0, 7.2], [320.0, 7.2]]
    assert conditions.as_mapping()["temp"].tolist() == [280.0, 320.0]
    assert conditions.to_dict()["batch_mean_applied"] is False
    with pytest.raises(RuntimeConditioningError, match="uniform batch"):
        conditions.require_uniform_scalar_mapping()

    uniform = build_runtime_conditioning_batch(
        {"temp": torch.tensor([300.0, 300.0])},
        defaults={"temp": 300.0},
        keys=("temp",),
        batch_size=2,
        dtype=torch.float64,
        device="cpu",
    )
    assert uniform.require_uniform_scalar_mapping() == {"temp": 300.0}
    with pytest.raises(ScalarConditioningError, match="identical"):
        coerce_sim_param_float(torch.tensor([280.0, 320.0]), 300.0)
    with pytest.raises(RuntimeConditioningError, match="uniform batch"):
        resolve_sim_params({"temp": torch.tensor([280.0, 320.0])})


def test_runtime_inputs_use_bounded_neighbors_explicit_vocabulary_and_per_sample_conditions() -> None:
    coords = torch.tensor(
        [
            [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [2.2, 0.0, 0.0]],
            [[0.0, 0.0, 0.0], [0.0, 1.1, 0.0], [0.0, 2.3, 0.0]],
        ],
        dtype=torch.float64,
    )
    residue_ids = torch.tensor([[1, 65, 20], [2, 3, 4]], dtype=torch.long)
    top, neighbors, pe, conditions = build_runtime_inputs(
        coords,
        residue_ids,
        sim_params_batch={
            "temp": torch.tensor([280.0, 320.0]),
            "pH": torch.tensor([6.8, 7.4]),
        },
        neighbor_k=2,
        neighbor_cutoff_angstrom=3.0,
        max_neighbor_candidates=4,
        max_atoms_per_cell=4,
    )

    assert top.residue_types.tolist() == [[1, 0, 20], [2, 3, 4]]
    assert top.residue_diagnostics["modulo_aliasing_used"] is False
    assert top.neighbor_diagnostics["nxn_allocation_observed"] is False
    assert top.neighbor_diagnostics["dense_all_pairs_distance_used"] is False
    assert tuple(top.runtime_conditioning.values.shape) == (2, 13)
    assert conditions["temp"].tolist() == [280.0, 320.0]
    assert conditions["pH"].tolist() == [6.8, 7.4]
    assert neighbors[0].shape == (2, 3, 2)
    assert pe.shape == (2, 1)

    model = NeuralForceCorrection(hidden_dim=32, num_layers=1).double().eval()
    force, aux = model(coords, top, neighbors, pe, conditions)
    assert force.shape == coords.shape
    assert aux["param_temp_by_sample"] == [280.0, 320.0]
    assert aux["runtime_conditioning_batch_preserved"] is True
    assert aux["runtime_conditioning_batch_mean_used"] is False


def _runtime_metadata() -> dict[str, object]:
    return runtime_input_schema_metadata(
        neighbor_k=4,
        cutoff_angstrom=6.0,
        max_neighbor_candidates=8,
        max_atoms_per_cell=8,
    )


def _model() -> torch.nn.Module:
    torch.manual_seed(7)
    return torch.nn.Sequential(
        torch.nn.Linear(3, 5),
        torch.nn.SiLU(),
        torch.nn.Linear(5, 2),
    ).double()


def _payload(model: torch.nn.Module, state: dict[str, torch.Tensor] | None = None) -> dict[str, object]:
    state_dict = deepcopy(dict(model.state_dict()) if state is None else state)
    config = {"model_kind": "unit_mlp", "input_width": 3, "output_width": 2}
    metadata = checkpoint_contract_metadata(
        model,
        state_dict,
        runtime_input_schema=_runtime_metadata(),
        config=config,
    )
    return {
        "state_dict": state_dict,
        "runtime_input_schema": _runtime_metadata(),
        "checkpoint_contract": metadata,
        "config": config,
    }


def test_architecture_runtime_vocabulary_and_state_fingerprints_are_deterministic() -> None:
    first = _model()
    second = _model()
    assert model_architecture_fingerprint(first) == model_architecture_fingerprint(second)
    assert state_dict_fingerprint(first.state_dict()) == state_dict_fingerprint(second.state_dict())

    changed = deepcopy(dict(second.state_dict()))
    changed["0.weight"] = changed["0.weight"].clone()
    changed["0.weight"][0, 0] += 0.25
    assert state_dict_fingerprint(first.state_dict()) != state_dict_fingerprint(changed)

    runtime_a = runtime_contract_fingerprint(
        architecture_fingerprint_sha256=model_architecture_fingerprint(first),
        runtime_input_schema=_runtime_metadata(),
        vocabulary_metadata=RESIDUE_VOCABULARY.to_dict(),
        config={"x": 1, "nested": {"b": 2, "a": 1}},
    )
    runtime_b = runtime_contract_fingerprint(
        architecture_fingerprint_sha256=model_architecture_fingerprint(first),
        runtime_input_schema=_runtime_metadata(),
        vocabulary_metadata=RESIDUE_VOCABULARY.to_dict(),
        config={"nested": {"a": 1, "b": 2}, "x": 1},
    )
    assert runtime_a == runtime_b


def test_strict_checkpoint_contract_accepts_only_full_exact_finite_state() -> None:
    source = _model()
    target = _model()
    payload = _payload(source)
    report = load_checkpoint_payload_fail_closed(
        target,
        payload,
        runtime_input_schema=_runtime_metadata(),
        config=payload["config"],
    )
    assert report["strict"] is True
    assert report["allow_partial"] is False
    assert report["tensor_numel_coverage"] == 1.0
    assert report["state_source"] == "state_dict"

    missing_state = deepcopy(dict(source.state_dict()))
    missing_state.pop("0.bias")
    missing_payload = _payload(source, missing_state)
    with pytest.raises(CheckpointStateCoverageError, match="strict checkpoint coverage"):
        load_checkpoint_payload_fail_closed(
            _model(),
            missing_payload,
            runtime_input_schema=_runtime_metadata(),
            config=missing_payload["config"],
        )

    bad_dtype = deepcopy(dict(source.state_dict()))
    bad_dtype["0.weight"] = bad_dtype["0.weight"].float()
    bad_dtype_payload = _payload(source, bad_dtype)
    with pytest.raises(CheckpointStateCoverageError, match="dtype=1"):
        load_checkpoint_payload_fail_closed(
            _model(),
            bad_dtype_payload,
            runtime_input_schema=_runtime_metadata(),
            config=bad_dtype_payload["config"],
        )

    nonfinite = deepcopy(dict(source.state_dict()))
    nonfinite["0.weight"] = nonfinite["0.weight"].clone()
    nonfinite["0.weight"][0, 0] = float("nan")
    nonfinite_payload = _payload(source, nonfinite)
    with pytest.raises(CheckpointStateCoverageError, match="nonfinite=1"):
        load_checkpoint_payload_fail_closed(
            _model(),
            nonfinite_payload,
            runtime_input_schema=_runtime_metadata(),
            config=nonfinite_payload["config"],
        )

    tampered = _payload(source)
    tampered_state = deepcopy(tampered["state_dict"])
    tampered_state["0.weight"] = tampered_state["0.weight"].clone()
    tampered_state["0.weight"][0, 0] += 1.0
    tampered["state_dict"] = tampered_state
    with pytest.raises(CheckpointContractError, match="fingerprint mismatch"):
        load_checkpoint_payload_fail_closed(
            _model(),
            tampered,
            runtime_input_schema=_runtime_metadata(),
            config=tampered["config"],
        )

    with pytest.raises(CheckpointStateCoverageError, match="partial loading"):
        load_state_dict_fail_closed(_model(), source.state_dict(), allow_partial=True)
    with pytest.raises(CheckpointStateCoverageError, match="strict=False"):
        load_state_dict_fail_closed(_model(), source.state_dict(), strict=False)


def test_runtime_schema_and_capability_blockers_have_no_drift() -> None:
    metadata = _runtime_metadata()
    assert metadata["schema_id"] == RUNTIME_INPUT_SCHEMA_ID
    assert metadata["residue_vocabulary"]["fingerprint_sha256"] == RESIDUE_VOCABULARY.fingerprint_sha256
    assert metadata["residue_modulo_aliasing_used"] is False
    assert metadata["runtime_conditioning_batch_mean_used"] is False
    assert metadata["dense_all_pairs_distance_used"] is False

    path = Path("config/independent_engine_v2_capabilities.yaml")
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    require_capability_snapshot(loaded)
    assert loaded["capabilities"] == capability_snapshot()["capabilities"]

    source = Path("train/runtime_inputs.py").read_text(encoding="utf-8")
    assert "torch.cdist" not in source
    assert ".remainder(" not in source
    assert ".mean().item()" not in source

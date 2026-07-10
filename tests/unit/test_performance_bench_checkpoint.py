from pathlib import Path
from types import SimpleNamespace

import pytest
import torch

import json

from benchmark import performance_bench as performance_bench_module
from benchmark.performance_bench import (
    _clip_tensor_abs,
    _load_ai_router_checkpoint,
    _resolve_ai_router_checkpoint_path,
    _resolve_checkpoint_state_dict,
)
from train.checkpoint_contracts import CheckpointStateCoverageError
from train.runtime_inputs import (
    RuntimeInputSchemaError,
    current_runtime_input_schema_metadata,
)


class _TinyModel(torch.nn.Module):
    def __init__(self):
        super().__init__()
        self.fc = torch.nn.Linear(4, 3)


def test_resolve_checkpoint_state_dict_wrapped():
    model = _TinyModel()
    payload = {"model_state_dict": model.state_dict(), "epoch": 3}
    state, source = _resolve_checkpoint_state_dict(payload)
    assert source == "model_state_dict"
    assert isinstance(state, dict)
    assert "fc.weight" in state


def test_load_ai_router_checkpoint_rejects_plain_state_dict(tmp_path, monkeypatch):
    src = _TinyModel()
    dst = _TinyModel()
    ckpt = Path(tmp_path) / "plain.pth"
    torch.save(src.state_dict(), ckpt)
    monkeypatch.setattr(
        performance_bench_module,
        "config",
        SimpleNamespace(DEVICE=torch.device("cpu")),
    )

    with pytest.raises(RuntimeInputSchemaError, match="legacy/raw checkpoint"):
        _load_ai_router_checkpoint(dst, str(ckpt), strict=True)


def test_load_ai_router_checkpoint_accepts_exact_runtime_schema(tmp_path, monkeypatch):
    src = _TinyModel()
    dst = _TinyModel()
    ckpt = Path(tmp_path) / "wrapped.pth"
    torch.save(
        {
            "state_dict": src.state_dict(),
            "runtime_input_schema": current_runtime_input_schema_metadata(),
        },
        ckpt,
    )
    monkeypatch.setattr(
        performance_bench_module,
        "config",
        SimpleNamespace(DEVICE=torch.device("cpu")),
    )

    info = _load_ai_router_checkpoint(dst, str(ckpt), strict=True)
    assert info["loaded"] is True
    assert info["state_source"] == "state_dict"
    assert info["missing_keys_count"] == 0
    assert info["unexpected_keys_count"] == 0
    assert info["runtime_input_schema"]["legacy_global_knn_compatible"] is False

    for p_src, p_dst in zip(src.parameters(), dst.parameters()):
        assert torch.allclose(p_src, p_dst)


def test_load_ai_router_checkpoint_rejects_empty_schema_wrapped_state(tmp_path, monkeypatch):
    dst = _TinyModel()
    ckpt = Path(tmp_path) / "empty-wrapped.pth"
    torch.save(
        {
            "state_dict": {},
            "runtime_input_schema": current_runtime_input_schema_metadata(),
        },
        ckpt,
    )
    monkeypatch.setattr(
        performance_bench_module,
        "config",
        SimpleNamespace(DEVICE=torch.device("cpu")),
    )

    with pytest.raises(CheckpointStateCoverageError, match="zero compatible keys"):
        _load_ai_router_checkpoint(dst, str(ckpt), strict=False)


def test_resolve_ai_router_checkpoint_path_from_map(tmp_path):
    ckpt_a = Path(tmp_path) / "a.pth"
    ckpt_b = Path(tmp_path) / "b.pth"
    ckpt_a.write_bytes(b"x")
    ckpt_b.write_bytes(b"y")
    mapping = {
        "target_checkpoints": {
            "Chignolin": str(ckpt_a),
            "default": "b.pth",
        }
    }
    map_path = Path(tmp_path) / "map.json"
    map_path.write_text(json.dumps(mapping), encoding="utf-8")

    resolved_1, meta_1 = _resolve_ai_router_checkpoint_path(f"@{map_path}", "Chignolin")
    assert resolved_1 == str(ckpt_a.resolve())
    assert meta_1["is_map"] is True
    assert meta_1["selected_key"] == "Chignolin"

    resolved_2, meta_2 = _resolve_ai_router_checkpoint_path(f"@{map_path}", "Unknown_Target")
    assert resolved_2 == str(ckpt_b.resolve())
    assert meta_2["is_map"] is True
    assert meta_2["selected_key"] == "default"


def test_clip_tensor_abs_returns_hit_count():
    x = torch.tensor([[0.0, 3.0, -5.0], [1.2, -0.5, 4.4]], dtype=torch.float32)
    y, hits = _clip_tensor_abs(x, 2.0)
    assert hits == 3
    assert torch.allclose(
        y,
        torch.tensor([[0.0, 2.0, -2.0], [1.2, -0.5, 2.0]], dtype=torch.float32),
    )


def test_benchmark_ai_inputs_use_exact_checkpoint_runtime_semantics():
    class _Topology:
        def residue_types_for_coordinate_count(self, atom_count):
            assert atom_count == 3
            return torch.tensor([1, 2, 3], dtype=torch.long)

    coordinates = torch.tensor(
        [[[0.0, 0.0, 0.0], [1.5, 0.0, 0.0], [4.0, 0.0, 0.0]]],
        dtype=torch.float32,
    )
    top, neighbors, potential, sim_params = (
        performance_bench_module._build_checkpoint_compatible_ai_inputs(
            coordinates,
            _Topology(),
            {"temp": 305.0, "salt_conc": 0.2, "pH": 7.2, "ionic_strength": 0.3},
        )
    )
    schema = current_runtime_input_schema_metadata()
    assert schema["periodic"] is False
    assert neighbors[0].shape == (1, 3, int(schema["neighbor_k"]))
    assert top.neighbor_diagnostics["source"] == "v2_compact_radius_graph"
    assert top.neighbor_diagnostics["candidate_capacity"] == int(
        schema["max_neighbor_candidates"]
    )
    assert potential.shape == (1, 1)
    assert sim_params["temp"] == pytest.approx(305.0)

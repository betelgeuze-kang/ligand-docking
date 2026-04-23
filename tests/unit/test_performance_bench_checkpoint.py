from pathlib import Path

import torch

import json

from benchmark.performance_bench import (
    _clip_tensor_abs,
    _load_ai_router_checkpoint,
    _resolve_ai_router_checkpoint_path,
    _resolve_checkpoint_state_dict,
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


def test_load_ai_router_checkpoint_plain_state_dict(tmp_path):
    src = _TinyModel()
    dst = _TinyModel()
    ckpt = Path(tmp_path) / "plain.pth"
    torch.save(src.state_dict(), ckpt)

    info = _load_ai_router_checkpoint(dst, str(ckpt), strict=True)
    assert info["loaded"] is True
    assert info["state_source"] == "root"
    assert info["missing_keys_count"] == 0
    assert info["unexpected_keys_count"] == 0

    for p_src, p_dst in zip(src.parameters(), dst.parameters()):
        assert torch.allclose(p_src, p_dst)


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

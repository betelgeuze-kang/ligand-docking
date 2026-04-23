import torch

import run_validation as rv


def test_run_target_placeholder_mode_uses_placeholder(monkeypatch):
    native = torch.zeros((5, 3), dtype=torch.float32)

    monkeypatch.setattr(rv, "load_native_structure", lambda _t: (native, "AAAAA"))
    monkeypatch.setattr(rv, "_run_placeholder_target", lambda *_a, **_k: native + 1.0)

    def _unexpected(*_a, **_k):
        raise AssertionError("physics path should not be called in placeholder mode")

    monkeypatch.setattr(rv, "_run_physics_refinement_target", _unexpected)

    out = rv.run_target("Dummy", mode="placeholder", return_metrics=False)
    assert torch.allclose(out, native + 1.0)


def test_run_target_unrestrained_mode_sets_zero_restraint(monkeypatch):
    native = torch.zeros((5, 3), dtype=torch.float32)
    observed = {}

    monkeypatch.setattr(rv, "load_native_structure", lambda _t: (native, "AAAAA"))
    monkeypatch.setattr(rv, "calculate_proxy_energy", lambda _c: 1.0)

    def _fake_physics(*_a, **kwargs):
        observed["restraint_k"] = kwargs.get("restraint_k")
        return native.clone(), 1.0, 1.0

    monkeypatch.setattr(rv, "_run_physics_refinement_target", _fake_physics)

    out, m = rv.run_target("Dummy", mode="physics_unrestrained", return_metrics=True)
    assert torch.allclose(out, native)
    assert observed["restraint_k"] == 0.0
    assert m["mode"] == "physics_unrestrained"


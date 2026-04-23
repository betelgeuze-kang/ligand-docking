import json

import torch

from benchmark import accuracy_bench as ab


def test_to_refinement_kwargs_from_dt():
    out = ab._to_refinement_kwargs({"dt": 3e-6, "restraint_k": 7.0, "force_clip": 100.0})
    assert out["refinement_dt"] == 3e-6
    assert out["restraint_k"] == 7.0
    assert out["force_clip"] == 100.0


def test_to_refinement_kwargs_refinement_dt_precedence():
    out = ab._to_refinement_kwargs({"dt": 1e-6, "refinement_dt": 2e-6})
    assert out["refinement_dt"] == 2e-6


def test_load_target_profile_normalizes_keys(tmp_path):
    p = tmp_path / "profile.json"
    p.write_text(
        json.dumps(
            {
                "targets": {
                    "Chignolin": {"dt": 3e-6},
                    "WW_Domain_FiP35": {"restraint_k": 8.0},
                }
            }
        ),
        encoding="utf-8",
    )
    profile = ab._load_target_profile(str(p))
    assert "chignolin" in profile
    assert "wwdomainfip35" in profile


def test_expand_ca_to_explicit_2bead_shape():
    ca = torch.zeros((5, 3), dtype=torch.float32)
    out = ab._expand_ca_to_explicit_2bead(ca)
    assert tuple(out.shape) == (10, 3)

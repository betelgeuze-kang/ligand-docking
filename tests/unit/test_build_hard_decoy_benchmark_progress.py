from __future__ import annotations

import random

from tools.build_hard_decoy_benchmark import _generate_synthetic_unique_decoys, _should_switch_to_brics


def test_generate_synthetic_unique_decoys_time_based_progress(monkeypatch) -> None:
    progress_calls: list[tuple[int, int, int]] = []

    monkeypatch.setattr("tools.build_hard_decoy_benchmark.Chem", object())
    monkeypatch.setattr("tools.build_hard_decoy_benchmark._rdkit_desc", lambda _s: (200.0, 2.0, 1, 2, 3))
    monkeypatch.setattr("tools.build_hard_decoy_benchmark._passes_3d_relaxation", lambda _s, max_iters=200: True)
    monkeypatch.setattr("tools.build_hard_decoy_benchmark._derive_scaffold", lambda _s: "scaf")

    canonical_values = iter([f"C{i}" for i in range(20)])
    monkeypatch.setattr("tools.build_hard_decoy_benchmark._canonicalize_smiles", lambda _s: next(canonical_values, ""))

    mono_values = iter([0.0, 0.0, 31.0, 31.0, 62.0, 62.0, 93.0, 93.0, 124.0, 124.0, 155.0, 155.0])
    monkeypatch.setattr("tools.build_hard_decoy_benchmark.time.monotonic", lambda: next(mono_values))

    out = _generate_synthetic_unique_decoys(
        count=5,
        seed_smiles=["CCO"],
        rng=random.Random(13),
        max_attempt_mult=20,
        require_relaxed_3d=True,
        progress_cb=lambda attempt, generated, max_attempts: progress_calls.append((attempt, generated, max_attempts)),
        progress_every=1000,
        progress_max_interval_sec=30.0,
    )

    assert len(out) == 5
    assert progress_calls
    assert any(generated > 0 for _, generated, _ in progress_calls)


def test_should_switch_to_brics_after_stall_window() -> None:
    assert not _should_switch_to_brics(
        attempts=100000,
        last_accept_attempt=90000,
        target_count=50000,
        stall_attempts=250000,
    )
    assert _should_switch_to_brics(
        attempts=600000,
        last_accept_attempt=300000,
        target_count=50000,
        stall_attempts=250000,
    )


def test_generate_synthetic_unique_decoys_reports_brics_switch_diagnostics(monkeypatch) -> None:
    monkeypatch.setattr("tools.build_hard_decoy_benchmark.Chem", object())
    monkeypatch.setattr("tools.build_hard_decoy_benchmark.BRICS", None)
    monkeypatch.setattr("tools.build_hard_decoy_benchmark._rdkit_desc", lambda _s: (200.0, 2.0, 1, 2, 3))
    monkeypatch.setattr("tools.build_hard_decoy_benchmark._passes_3d_relaxation", lambda _s, max_iters=200: True)
    monkeypatch.setattr("tools.build_hard_decoy_benchmark._derive_scaffold", lambda _s: "scaf")
    monkeypatch.setattr("tools.build_hard_decoy_benchmark._canonicalize_smiles", lambda _s: "")

    diagnostics: dict[str, object] = {}
    out = _generate_synthetic_unique_decoys(
        count=5000,
        seed_smiles=["CCO"],
        rng=random.Random(13),
        max_attempt_mult=20,
        require_relaxed_3d=True,
        progress_every=1000,
        progress_max_interval_sec=30.0,
        template_stall_attempts=100000,
        diagnostics=diagnostics,
    )

    assert out == []
    assert diagnostics["template_exit_reason"] == "stall_switch_to_brics"
    assert diagnostics["used_brics_fallback"] is True
    assert diagnostics["template_stall_attempts"] == 100000


def test_generate_synthetic_unique_decoys_enumerates_four_placeholder_templates(monkeypatch) -> None:
    monkeypatch.setattr("tools.build_hard_decoy_benchmark.Chem", object())
    monkeypatch.setattr("tools.build_hard_decoy_benchmark.BRICS", None)
    monkeypatch.setattr(
        "tools.build_hard_decoy_benchmark._template_smiles_candidates",
        lambda: (["C({r1})({r2})({r3}){r4}"], ["F", "Cl"]),
    )
    monkeypatch.setattr("tools.build_hard_decoy_benchmark._rdkit_desc", lambda _s: (200.0, 2.0, 1, 2, 3))
    monkeypatch.setattr("tools.build_hard_decoy_benchmark._passes_3d_relaxation", lambda _s, max_iters=200: True)
    monkeypatch.setattr("tools.build_hard_decoy_benchmark._derive_scaffold", lambda _s: "scaf")
    monkeypatch.setattr("tools.build_hard_decoy_benchmark._canonicalize_smiles", lambda s: str(s))

    diagnostics: dict[str, object] = {}
    out = _generate_synthetic_unique_decoys(
        count=10,
        seed_smiles=["CCO"],
        rng=random.Random(13),
        max_attempt_mult=20,
        require_relaxed_3d=False,
        generation_mode="enumerate",
        diagnostics=diagnostics,
    )

    assert len(out) == 10
    assert diagnostics["template_exit_reason"] == "target_reached"
    assert diagnostics["raw_combo_upper_bound"] == 16


def test_generate_synthetic_unique_decoys_carries_relaxed_bead_coords(monkeypatch) -> None:
    monkeypatch.setattr("tools.build_hard_decoy_benchmark.Chem", object())
    monkeypatch.setattr("tools.build_hard_decoy_benchmark.BRICS", None)
    monkeypatch.setattr(
        "tools.build_hard_decoy_benchmark._template_smiles_candidates",
        lambda: (["C{r1}"], ["C", "N"]),
    )
    monkeypatch.setattr("tools.build_hard_decoy_benchmark._rdkit_desc", lambda _s: (200.0, 2.0, 1, 2, 3))
    monkeypatch.setattr("tools.build_hard_decoy_benchmark._derive_scaffold", lambda _s: "scaf")
    monkeypatch.setattr("tools.build_hard_decoy_benchmark._canonicalize_smiles", lambda s: str(s))
    monkeypatch.setattr(
        "tools.build_hard_decoy_benchmark._relaxed_beads_from_smiles",
        lambda _s, max_iters=200: [[-1.0, 0.0, 0.0], [1.0, 0.0, 0.0]],
    )

    cache: dict[str, object] = {}
    out = _generate_synthetic_unique_decoys(
        count=1,
        seed_smiles=["CCO"],
        rng=random.Random(13),
        max_attempt_mult=20,
        require_relaxed_3d=True,
        relax_cache=cache,
        generation_mode="enumerate",
    )

    assert len(out) == 1
    assert out[0]["bead_coords"] == [[-1.0, 0.0, 0.0], [1.0, 0.0, 0.0]]
    assert any(isinstance(v, list) for v in cache.values())

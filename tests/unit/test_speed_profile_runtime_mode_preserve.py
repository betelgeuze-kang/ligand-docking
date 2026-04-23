from tools import speed_profile as sp


def _resolve_fast(*, preserve: bool):
    return sp.resolve_speed_profile(
        mode="fast",
        ai_interval=1,
        benchmark_replicas=1,
        ai_runtime_mode="eager",
        ai_disable_exploration=True,
        ai_use_hip_graph=False,
        ai_graph_warmup_iters=2,
        track_clip_hits=False,
        profile_components=False,
        disable_stochastic_noise=False,
        precompute_stochastic_noise=False,
        precompute_stochastic_noise_block_steps=0,
        sample_gpu_metrics=False,
        speed_mode_replicas=0,
        speed_profile_max_replicas=128,
        preserve_ai_runtime_mode=preserve,
    )


def test_fast_profile_overrides_runtime_mode_when_not_preserved():
    out = _resolve_fast(preserve=False)
    assert out["ai_runtime_mode"] == "scripted"
    assert out["ai_runtime_mode_requested"] == "eager"
    assert out["ai_runtime_mode_profile"] == "scripted"
    assert out["ai_runtime_mode_preserved"] is False


def test_fast_profile_preserves_requested_runtime_mode_when_enabled():
    out = _resolve_fast(preserve=True)
    assert out["ai_runtime_mode"] == "eager"
    assert out["ai_runtime_mode_requested"] == "eager"
    assert out["ai_runtime_mode_profile"] == "scripted"
    assert out["ai_runtime_mode_preserved"] is True

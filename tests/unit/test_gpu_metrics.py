import json
from types import SimpleNamespace

from core import gpu_metrics as gm


def test_sample_gpu_metrics_prefers_rocm(monkeypatch):
    fake_stdout = json.dumps({"card0": {"GPU use (%)": "37", "GPU memory use (%)": "12"}})

    def _fake_run(*_args, **_kwargs):
        return SimpleNamespace(stdout=fake_stdout)

    monkeypatch.setattr(gm.subprocess, "run", _fake_run)
    out = gm.sample_gpu_metrics()
    assert out["backend"] == "rocm-smi"
    assert out["util_percent"] == 37.0
    assert out["mem_util_percent"] == 12.0


def test_sample_gpu_metrics_fallback_none(monkeypatch):
    monkeypatch.setattr(gm, "_sample_rocm_smi", lambda: None)
    monkeypatch.setattr(gm, "_sample_gputil", lambda: None)
    monkeypatch.setattr(gm, "_sample_torch_memory", lambda: None)
    out = gm.sample_gpu_metrics()
    assert out["backend"] == "none"
    assert out["ok"] is False


def test_async_gpu_sampler_collects(monkeypatch):
    samples = [
        {"util_percent": 10.0, "mem_util_percent": 1.0, "backend": "rocm-smi"},
        {"util_percent": 20.0, "mem_util_percent": 2.0, "backend": "rocm-smi"},
    ]
    idx = {"v": 0}

    def _fake_sample():
        v = samples[min(idx["v"], len(samples) - 1)]
        idx["v"] += 1
        return v

    monkeypatch.setattr(gm, "sample_gpu_metrics", _fake_sample)
    s = gm.AsyncGpuSampler(interval_sec=0.05)
    s.start()
    out = s.stop()
    assert out["backend"] == "rocm-smi"
    assert out["avg_util_percent"] >= 10.0

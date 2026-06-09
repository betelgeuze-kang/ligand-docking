from __future__ import annotations

from tools.product.build_backmapping_scoring_batch_smoke_benchmark import run_smoke_benchmark


def test_backmapping_batch_smoke_benchmark_reports_positive_throughput() -> None:
    payload = run_smoke_benchmark(frame_count=16, repeats=2)
    summary = payload["summary"]
    assert summary["batch_frames_per_sec"] > 0.0
    assert summary["loop_frames_per_sec"] > 0.0
    assert summary["speedup_ratio"] >= 1.0
    assert summary["status"] == "backmapping_scoring_batch_smoke_benchmark_ready"

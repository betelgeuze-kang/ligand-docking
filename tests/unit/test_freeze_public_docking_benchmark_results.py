"""Immutable public docking benchmark result snapshot tests."""

from __future__ import annotations

import csv
import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "tools" / "product" / "freeze_public_docking_benchmark_results.py"


@pytest.fixture(scope="module")
def freezer():
    spec = importlib.util.spec_from_file_location(
        "freeze_public_docking_benchmark_results_under_test", MODULE_PATH
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _write_sources(root: Path, *, metrics_hash: str = "a" * 64) -> None:
    execution = {
        "summary": {
            "suite_complete": True,
            "execution_ready": True,
            "case_set_hash": "a" * 64,
            "frozen_case_count": 2,
            "selected_case_count": 2,
            "primary_engine_surface": "engine_v2",
            "candidate_budget": 5,
            "refinement_max_steps": 8,
        },
        "cases": [{"case_id": "case_1"}, {"case_id": "case_2"}],
    }
    metrics = {
        "case_set_hash": metrics_hash,
        "metrics": {"attempted_case_count": 2},
        "paired_baseline_deltas": [],
        "synthetic_metrics_used": False,
    }
    runs = root / "runs"
    config = root / "config"
    runs.mkdir()
    config.mkdir()
    (runs / "frozen_public_docking_benchmark_execution_current.json").write_text(
        json.dumps(execution), encoding="utf-8"
    )
    with (runs / "frozen_public_docking_benchmark_execution_current.csv").open(
        "w", encoding="utf-8", newline=""
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=["case_id", "engine_surface"])
        writer.writeheader()
        for case_id in ("case_1", "case_2"):
            for surface in ("legacy_product", "engine_v2"):
                writer.writerow({"case_id": case_id, "engine_surface": surface})
    (runs / "frozen_public_docking_benchmark_execution_current.md").write_text(
        "# execution\n", encoding="utf-8"
    )
    (config / "frozen_public_docking_benchmark_metrics_current.json").write_text(
        json.dumps(metrics), encoding="utf-8"
    )


def test_result_snapshot_is_content_addressed_and_immutable(freezer, tmp_path):
    _write_sources(tmp_path)
    manifest = freezer.freeze_public_docking_benchmark_results(
        output_root=tmp_path,
        frozen_at_utc="2026-07-27T01:00:00Z",
    )
    assert manifest["ready"] is True
    assert manifest["immutable"] is True
    assert manifest["case_count"] == 2
    assert manifest["case_set_hash"] == "a" * 64
    assert manifest["paired_baseline_delta_present"] is False
    assert len(manifest["result_snapshot_id"]) == 64
    for artifact in manifest["artifacts"].values():
        assert (tmp_path / artifact["path"]).is_file()
        assert len(artifact["sha256"]) == 64

    repeated = freezer.freeze_public_docking_benchmark_results(
        output_root=tmp_path,
        frozen_at_utc="2099-01-01T00:00:00Z",
    )
    assert repeated == manifest

    execution_path = tmp_path / manifest["artifacts"]["execution_json"]["path"]
    execution_path.write_text("tampered\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="frozen_result_artifact_hash_mismatch"):
        freezer.freeze_public_docking_benchmark_results(output_root=tmp_path)


def test_result_snapshot_rejects_metrics_from_another_case_set(freezer, tmp_path):
    _write_sources(tmp_path, metrics_hash="b" * 64)
    with pytest.raises(RuntimeError, match="metrics_case_set_hash_mismatch"):
        freezer.freeze_public_docking_benchmark_results(output_root=tmp_path)

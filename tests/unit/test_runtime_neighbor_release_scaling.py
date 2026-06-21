from __future__ import annotations

import json
from pathlib import Path

from tools.product import run_runtime_neighbor_release_scaling as mod


def test_runtime_neighbor_release_scaling_payload_ready_for_configured_counts(tmp_path: Path) -> None:
    payload = mod.build_payload(
        atom_counts=[64, 125, 216],
        release_atom_counts=[64, 125, 216],
        repeats=1,
        warmup_repeats=1,
        cutoff=3.1,
        skin=0.0,
        max_neighbor_count=16,
        max_atoms_per_cell=16,
        rebuild_stride=3,
        target_number_density=1.0 / 27.0,
        out_svg=tmp_path / "scaling.svg",
        require_release_counts=True,
    )

    summary = payload["summary"]
    assert payload["packet_type"] == "runtime_neighbor_release_scaling"
    assert summary["status"] == "runtime_neighbor_release_scaling_ready"
    assert summary["ready"] is True
    assert summary["release_atom_counts_ready"] is True
    assert summary["fixed_density_ready"] is True
    assert summary["nxn_allocation_observed"] is False
    assert summary["neighbor_pair_count_slope"] >= 0.85
    assert summary["neighbor_pair_count_slope"] <= 1.15
    assert payload["blockers"] == []
    assert Path(summary["plot_path"]).exists()


def test_runtime_neighbor_release_scaling_blocks_missing_release_counts(tmp_path: Path) -> None:
    payload = mod.build_payload(
        atom_counts=[64, 125, 216],
        release_atom_counts=[1000, 2000, 4000, 8000],
        repeats=1,
        warmup_repeats=1,
        cutoff=3.1,
        skin=0.0,
        max_neighbor_count=16,
        max_atoms_per_cell=16,
        rebuild_stride=3,
        target_number_density=1.0 / 27.0,
        out_svg=tmp_path / "blocked.svg",
        require_release_counts=True,
    )

    assert payload["summary"]["status"] == "blocked_runtime_neighbor_release_scaling"
    assert payload["summary"]["ready"] is False
    assert payload["summary"]["release_atom_counts_ready"] is False
    assert "release_atom_counts_not_covered" in payload["blockers"]


def test_runtime_neighbor_release_scaling_cli_writes_artifacts(tmp_path: Path) -> None:
    out_json = tmp_path / "scaling.json"
    out_md = tmp_path / "scaling.md"
    out_svg = tmp_path / "scaling.svg"

    rc = mod.main(
        [
            "--atom-counts",
            "64,125,216",
            "--release-atom-counts",
            "64,125,216",
            "--repeats",
            "1",
            "--out-json",
            str(out_json),
            "--out-md",
            str(out_md),
            "--out-svg",
            str(out_svg),
        ]
    )

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert rc == 0
    assert payload["summary"]["ready"] is True
    assert out_md.exists()
    assert out_svg.exists()

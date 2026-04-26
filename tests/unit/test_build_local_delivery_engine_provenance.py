from __future__ import annotations

import json
from pathlib import Path

from tools import build_local_delivery_engine_provenance as mod


def _write(path: Path, text: str = "# surface\n") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _seed_repo(tmp_path: Path) -> None:
    for relpath in mod.DEFAULT_ENGINE_SURFACE_FILES:
        _write(tmp_path / relpath)
    _write(
        tmp_path / "tools/generate_ligand_trajectory_engine.py",
        "\n".join(
            [
                "from core.config import config",
                "from core.forcefield import ForceField",
                "from core.integrator import LangevinIntegrator",
                "from core.topology import TopologyFactory",
                "from tools.pdb_loader import load_native_structure",
            ]
        ),
    )
    _write(
        tmp_path / "rust_engine/src/lib.rs",
        "\n".join(
            [
                "use pyo3::prelude::*;",
                "extern \"C\" { fn launch_nonbonded_kernel() -> c_int; }",
                "fn launch_ligand_direct_rollout_kernel() {}",
            ]
        ),
    )


def test_all_required_surfaces_present_reuses_existing_engine(tmp_path: Path, monkeypatch) -> None:
    _seed_repo(tmp_path)
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    monkeypatch.setattr(mod, "RUNS", tmp_path / "runs")

    payload = mod.build_payload()

    summary = payload["summary"]
    assert summary["provenance_ok"] is True
    assert summary["existing_engine_reused"] is True
    assert summary["pipeline_entrypoint"] == "tools/run_ligand_htvs_pipeline.py"
    assert summary["required_surface_count"] == len(mod.DEFAULT_ENGINE_SURFACE_FILES)
    assert summary["present_surface_count"] == len(mod.DEFAULT_ENGINE_SURFACE_FILES)
    assert summary["missing_surface_count"] == 0
    assert summary["import_evidence_count"] >= 6
    assert payload["next_required_step"] == "Use the existing engine surfaces in the local delivery workflow; do not implement a new engine."
    assert payload["negative_claim_guardrail"].startswith("No new engine is created")
    assert all(row["sha256"] for row in payload["required_engine_files"])


def test_missing_core_file_blocks_existing_engine_reuse(tmp_path: Path, monkeypatch) -> None:
    _seed_repo(tmp_path)
    (tmp_path / "core/forcefield.py").unlink()
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    monkeypatch.setattr(mod, "RUNS", tmp_path / "runs")

    payload = mod.build_payload()

    summary = payload["summary"]
    assert summary["provenance_ok"] is False
    assert summary["existing_engine_reused"] is False
    assert summary["missing_surface_count"] == 1
    assert "core/forcefield.py" in payload["engine_surface_files"]["missing"]
    assert "restore/mount existing engine surface" in payload["next_required_step"]


def test_cli_writes_json_and_markdown(tmp_path: Path, monkeypatch) -> None:
    _seed_repo(tmp_path)
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    monkeypatch.setattr(mod, "RUNS", tmp_path / "runs")
    out_json = tmp_path / "runs/provenance.json"
    out_md = tmp_path / "runs/provenance.md"

    rc = mod.main(["--out-json", str(out_json), "--out-md", str(out_md)])

    assert rc == 0
    payload = json.loads(out_json.read_text(encoding="utf-8"))
    markdown = out_md.read_text(encoding="utf-8")
    assert payload["summary"]["existing_engine_reused"] is True
    assert "existing engine reuse" in markdown.lower()
    assert "not a new engine implementation" in markdown.lower()

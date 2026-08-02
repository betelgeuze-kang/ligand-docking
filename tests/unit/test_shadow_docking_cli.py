"""Regression tests for the shadow-docking production entrypoint.

The library path is already covered by ``test_shadow_docking_run.py``; these tests
pin the *entrypoint* so the wiring (single preparation, three surfaces, offline
oracle abstention, artifact shape) cannot silently rot.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
CLI_PATH = ROOT / "tools" / "product" / "run_legacy_v2_oracle_shadow_docking.py"


def _load_cli():
    spec = importlib.util.spec_from_file_location(
        "run_legacy_v2_oracle_shadow_docking", CLI_PATH
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _receptor_pdb_text() -> str:
    body = "".join(
        "ATOM  %5d  CA  ALA A%4d    %8.3f%8.3f%8.3f  1.00  0.00           C\n"
        % (i, i, float(i % 9), float(i % 5), float(i % 3))
        for i in range(1, 41)
    )
    return body + "END\n"


@pytest.fixture(scope="module")
def cli():
    return _load_cli()


@pytest.fixture(scope="module")
def receptor_pdb(tmp_path_factory) -> Path:
    path = tmp_path_factory.mktemp("shadow_cli") / "receptor.pdb"
    path.write_text(_receptor_pdb_text(), encoding="utf-8")
    return path


@pytest.fixture(scope="module")
def payload(cli, receptor_pdb):
    return cli.run_shadow_docking(
        receptor_pdb=str(receptor_pdb),
        ligand_smiles="CCCCCCO",
        target_id="T1",
        ligand_id="L1",
        max_conformers=6,
        seed=7,
    )


def test_entrypoint_runs_three_surfaces_from_one_preparation(payload):
    assert payload["status"] == "shadow_execution_ready"
    assert payload["ready"] is True
    assert payload["violations"] == []
    assert payload["executed_surface_count"] == 3
    assert set(payload["results"]) == {"legacy_product", "engine_v2", "external_oracle"}
    for result in payload["results"].values():
        assert (
            result["prepared_input_hashes"]["prepared_input_hash"]
            == payload["prepared_input_hash"]
        )


def test_entrypoint_carries_conformer_coordinates(payload):
    preparation = payload["preparation"]
    assert preparation["ready"] is True
    assert preparation["blockers"] == []
    assert preparation["conformer_coordinates_carried"] is True
    assert preparation["conformer_count"] > 0
    assert preparation["ligand_atom_element_count"] == preparation["ligand_atom_count"]


def test_entrypoint_keeps_legacy_active_and_shadow_locked(payload):
    assert payload["active_engine_surface"] == "legacy_product"
    assert payload["claim_promotion_allowed"] is False
    assert payload["shadow_only_locked"] is True
    assert sorted(payload["shadow_result_surfaces"]) == ["engine_v2", "external_oracle"]


def test_entrypoint_reports_three_pairwise_deltas(payload):
    deltas = payload["pairwise_deltas"]
    assert len(deltas) == 3
    assert payload["comparison"]["comparable"] is True
    assert payload["comparison"]["pairwise_deltas"] == deltas
    oracle_pairs = [
        delta
        for delta in deltas
        if "external_oracle" in (delta["left_engine_surface"], delta["right_engine_surface"])
    ]
    assert len(oracle_pairs) == 2
    for delta in oracle_pairs:
        assert delta["top_score_delta"] is None


def test_entrypoint_abstains_for_offline_oracle_without_installing(payload):
    oracle = payload["results"]["external_oracle"]
    assert oracle["uncertainty"]["abstained"] is True
    assert oracle["pose_ensemble"]["poses"] == []
    assert payload["offline_baseline"]["installs_binaries"] is False


def test_entrypoint_states_claim_boundary(payload, cli):
    assert payload["claim_boundary"] == cli.CLAIM_BOUNDARY
    assert "not a benchmark result" in payload["claim_boundary"]


def test_entrypoint_writes_json_and_markdown(cli, payload, tmp_path):
    json_path = tmp_path / "shadow.json"
    md_path = tmp_path / "shadow.md"
    cli._write_json(json_path, payload)
    cli._write_markdown(md_path, payload)
    assert json_path.is_file() and md_path.is_file()
    markdown = md_path.read_text(encoding="utf-8")
    assert "## Pairwise Deltas" in markdown
    assert payload["prepared_input_hash"] in markdown


def test_entrypoint_rejects_missing_receptor(cli, tmp_path):
    with pytest.raises(SystemExit) as excinfo:
        cli.run_shadow_docking(
            receptor_pdb=str(tmp_path / "does_not_exist.pdb"),
            ligand_smiles="CCCCCCO",
        )
    assert "receptor_pdb_not_found" in str(excinfo.value)


def test_entrypoint_is_deterministic(cli, receptor_pdb, payload):
    repeat = cli.run_shadow_docking(
        receptor_pdb=str(receptor_pdb),
        ligand_smiles="CCCCCCO",
        target_id="T1",
        ligand_id="L1",
        max_conformers=6,
        seed=7,
    )
    assert repeat["prepared_input_hash"] == payload["prepared_input_hash"]
    assert repeat["status"] == payload["status"]
    for surface, result in payload["results"].items():
        poses = result["pose_ensemble"]["poses"]
        repeat_poses = repeat["results"][surface]["pose_ensemble"]["poses"]
        assert [pose["total_score"] for pose in repeat_poses] == [
            pose["total_score"] for pose in poses
        ]

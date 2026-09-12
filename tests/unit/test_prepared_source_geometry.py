"""Fresh source-coordinate controls; no protected or real molecular fixtures."""
from __future__ import annotations

import copy
from dataclasses import replace
import hashlib
import json
from pathlib import Path

import pytest

from tests.unit.test_score_prepared_cross_interactions import _case, _prepared, _request, _run
from tests.unit.test_v2_prepared_cross_interaction import _pair, _system as _separate_chains
from tools.product import score_prepared_cross_interactions as consumer


def _system(positions, charges):
    from betelgeuze_engine_v2.molecular import Chain
    system = _separate_chains(positions, charges)
    return replace(system, residues=tuple(replace(r, chain_index=0) for r in system.residues),
                   chains=(Chain(0, "A", tuple(range(len(system.residues)))),))


def _replace(ref, text):
    path = Path(ref["path"])
    path.write_text(text)
    ref["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()


def _short_pair(directory, distance=0.63):
    prepared = _prepared(directory)
    pdb = "".join(
        f"ATOM  {i:5d} {name:>4s} {'SYN':>3s} A{1:4d}    {x:8.3f}{0.0:8.3f}{0.0:8.3f}{1.0:6.2f}{0.0:6.2f}          {'H':>2s}  \n"
        for i, name, x in ((1, "H1", 0.0), (2, "H2", distance))) + "END\n"
    _replace(prepared["protein_pdb"], pdb)
    _replace(prepared["protein_atomtypes"], "[ atomtypes ]\nH 1 1.008 0.0 A 0.1 0.1\n")
    _replace(prepared["protein_chains"][0]["molecule_itp"],
             "[ moleculetype ]\nSYN 3\n[ atoms ]\n1 H 1 SYN H1 1 0.0 1.008\n2 H 1 SYN H2 2 0.0 1.008\n[bonds]\n")
    return prepared


def test_source_short_pair_is_observed_in_actual_consumer_without_changing_energy(tmp_path):
    from betelgeuze_engine.product.prepared_gromacs_input import load_prepared_gromacs_components
    from betelgeuze_engine.product.v2_cross_interaction import evaluate_prepared_cross_interaction

    prepared = _short_pair(tmp_path / "source")
    receptor, ligand, rp, lp, provenance = load_prepared_gromacs_components(prepared)
    case = _case(prepared)
    direct = evaluate_prepared_cross_interaction(receptor, ligand, rp, lp,
        source_declarations=prepared["source_declarations"], **case["evaluation"])
    before = {ref["path"]: Path(ref["path"]).read_bytes() for ref in provenance["sources"].values()}
    row = consumer.evaluate_request(_request([case]))["rows"][0]
    assert row["status"] == "evaluated"
    observation = row["source_geometry_observation"]
    assert observation["status"] == "observed"
    group = observation["groups"]["receptor"]
    assert group["pair_count_within_radius"] == group["non_direct_bond_pair_count"] == 1
    assert group["direct_bond_pair_count"] == 0
    assert group["closest_pairs"][0]["distance_angstrom"] == pytest.approx(0.63)
    assert [a["source_serial"] for a in group["closest_pairs"][0]["atoms"]] == [1, 2]
    assert row["result"]["quantities"] == direct["quantities"]
    assert row["result"]["sources"] == direct["sources"]
    assert observation["affects_score_or_admission"] is False
    assert observation["physical_validity_assessed"] is False
    assert all(Path(path).read_bytes() == value for path, value in before.items())


def test_real_module_retains_source_observation_when_original_physical_guard_rejects(tmp_path):
    cases = [_case(_short_pair(tmp_path / "valid")),
             _case(_short_pair(tmp_path / "rejected", distance=0.2)), None]
    request = tmp_path / "request.json"
    output = tmp_path / "output.json"
    request.write_text(json.dumps(_request(cases)))
    process = _run(request, output, tmp_path)
    assert process.returncode == 2
    report = json.loads(output.read_text())
    assert report["denominator"] == {"requested": 3, "evaluated": 1, "failed": 2, "skipped": 0}
    first, rejected, invalid = report["rows"]
    assert first["source_geometry_observation"]["status"] == "observed"
    assert "minimum_pair_distance_angstrom" in rejected["reason"]
    assert rejected["source_geometry_observation"]["groups"]["receptor"]["pair_count_within_radius"] == 1
    assert rejected["preparation_provenance"]["sources"]
    assert invalid["source_geometry_observation"]["groups"] is None
    assert invalid["source_geometry_observation"]["status"] == "unavailable"


def test_diagnostic_exception_is_visible_and_does_not_turn_energy_into_a_failure(tmp_path, monkeypatch):
    from betelgeuze_engine.product import prepared_source_geometry as geometry
    def fail(*args):
        raise RuntimeError("synthetic diagnostic exception")
    monkeypatch.setattr(geometry, "observe_prepared_source_geometry", fail)
    row = consumer.evaluate_request(_request([_case(_prepared(tmp_path / "source"))]))["rows"][0]
    assert row["status"] == "evaluated"
    assert row["source_geometry_observation"]["groups"] is None
    assert row["source_geometry_observation"]["error_type"] == "RuntimeError"
    assert "synthetic diagnostic" in row["source_geometry_observation"]["detail"]


def _provenance(bonds_marker, adjacency):
    return {"original_topologies": {"protein_chain_A": {"sections": bonds_marker},
                                    "ligand_itp": {"sections": {"bonds": []}}},
            "receptor_source_bond_adjacency": adjacency, "ligand_source_bond_adjacency": []}


@pytest.mark.parametrize("sections,adjacency,expected", [({}, [], None), ({"bonds": []}, [], 1),
                                                        ({"bonds": ["explicit"]}, [[0, 1]], 0)])
def test_missing_empty_and_present_source_bonds_stay_distinct(sections, adjacency, expected):
    from betelgeuze_engine.product.prepared_source_geometry import observe_prepared_source_geometry
    receptor = _system([[0, 0, 0], [0.6, 0, 0]], [0, 0])
    ligand = _system([[4, 0, 0]], [0])
    observation = observe_prepared_source_geometry(receptor, ligand, _provenance(sections, adjacency))
    assert observation["status"] == "observed"
    assert observation["groups"]["receptor"]["pair_count_within_radius"] == 1
    assert observation["groups"]["receptor"]["non_direct_bond_pair_count"] == expected
    assert observation["groups"]["cross"]["pair_count_within_radius"] == 0
    assert observation["groups"]["cross"]["direct_bond_pair_count"] is None


def test_one_missing_molecule_bond_section_does_not_qualify_partial_chain_adjacency():
    from betelgeuze_engine.product.prepared_source_geometry import observe_prepared_source_geometry
    receptor = _system([[0, 0, 0], [0.6, 0, 0]], [0, 0])
    ligand = _system([[4, 0, 0]], [0])
    provenance = _provenance({"bonds": []}, [])
    provenance["original_topologies"]["protein_chain_A_molecule_1"] = {"sections": {"atoms": []}}
    group = observe_prepared_source_geometry(receptor, ligand, provenance)["groups"]["receptor"]
    assert group["pair_count_within_radius"] == 1
    assert group["non_direct_bond_pair_count"] is None
    assert group["closest_non_direct_bond_pairs"] is None


def test_graph_overflow_is_unavailable_without_zero_contact_count():
    from betelgeuze_engine.product.prepared_source_geometry import observe_prepared_source_geometry
    receptor = _system([[i / 1000, 0, 0] for i in range(65)], [0] * 65)
    ligand = _system([[4, 0, 0]], [0])
    observation = observe_prepared_source_geometry(receptor, ligand, _provenance({"bonds": []}, []))
    assert observation["status"] == "unavailable"
    assert observation["reason"] == "bounded_neighbor_capacity_exceeded"
    assert observation["groups"] is None
    assert observation["graph_diagnostics"]["overflow"] is True


def test_exact_counts_are_not_limited_to_displayed_nearest_pairs():
    from betelgeuze_engine.product.prepared_source_geometry import observe_prepared_source_geometry
    receptor = _system([[i / 100, 0, 0] for i in range(8)], [0] * 8)
    ligand = _system([[4, 0, 0]], [0])
    group = observe_prepared_source_geometry(receptor, ligand, _provenance({"bonds": []}, []))["groups"]["receptor"]
    assert group["pair_count_within_radius"] == group["non_direct_bond_pair_count"] == 28
    assert len(group["closest_pairs"]) == len(group["closest_non_direct_bond_pairs"]) == 16
    assert group["unlisted_pair_count"] == group["unlisted_non_direct_bond_pair_count"] == 12


def test_successful_zero_observation_keeps_missing_bond_knowledge_unknown():
    from betelgeuze_engine.product.prepared_source_geometry import observe_prepared_source_geometry
    receptor, ligand, _, _ = _pair()
    observation = observe_prepared_source_geometry(receptor, ligand, _provenance({}, []))
    assert observation["status"] == "observed"
    assert observation["groups"]["receptor"]["pair_count_within_radius"] == 0
    assert observation["groups"]["receptor"]["non_direct_bond_pair_count"] is None
    assert observation["groups"]["ligand"]["non_direct_bond_pair_count"] == 0


def test_source_adjacency_errors_are_not_silently_treated_as_empty():
    from betelgeuze_engine.product.prepared_source_geometry import observe_prepared_source_geometry
    receptor, ligand = _system([[0, 0, 0]], [0]), _system([[4, 0, 0]], [0])
    provenance = _provenance({"bonds": []}, [[0, 5]])
    result = observe_prepared_source_geometry(receptor, ligand, copy.deepcopy(provenance))
    assert result["status"] == "unavailable"
    assert result["groups"] is None
    assert result["error_type"] == "ValueError"


@pytest.mark.parametrize("missing", [False, True])
def test_expected_molecule_sources_are_bound_to_canonical_atoms(missing):
    from betelgeuze_engine.product.prepared_source_geometry import observe_prepared_source_geometry
    receptor = _system([[0, 0, 0], [0.6, 0, 0]], [0, 0])
    receptor = replace(receptor, atoms=tuple(replace(atom, metadata={"prepared_gromacs_source": {
        "source_molecule_label": f"protein_chain_A_molecule_{i}"}}) for i, atom in enumerate(receptor.atoms)))
    provenance = _provenance({"bonds": []}, [])
    del provenance["original_topologies"]["protein_chain_A"]
    for i in range(1 if missing else 2):
        provenance["original_topologies"][f"protein_chain_A_molecule_{i}"] = {"sections": {"bonds": []}}
    group = observe_prepared_source_geometry(receptor, _system([[4, 0, 0]], [0]), provenance)["groups"]["receptor"]
    assert group["pair_count_within_radius"] == 1
    assert group["non_direct_bond_pair_count"] == (None if missing else 1)

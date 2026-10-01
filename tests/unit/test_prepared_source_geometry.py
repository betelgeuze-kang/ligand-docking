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
    assert group["supplied_direct_bond_lengths"]["bond_count"] == 0
    assert all(Path(path).read_bytes() == value for path, value in before.items())


def test_explicit_source_equilibrium_is_bound_and_inherited_length_stays_unknown(tmp_path):
    explicit = _short_pair(tmp_path / "explicit", distance=-3.5)
    inherited = _short_pair(tmp_path / "inherited", distance=-3.5)
    explicit_ref = explicit["protein_chains"][0]["molecule_itp"]
    inherited_ref = inherited["protein_chains"][0]["molecule_itp"]
    _replace(explicit_ref, Path(explicit_ref["path"]).read_text() + "1 2 1 .1 100\n")
    _replace(inherited_ref, Path(inherited_ref["path"]).read_text() + "1 2 1\n")
    source_bytes = {ref["path"]: Path(ref["path"]).read_bytes()
                    for prepared in (explicit, inherited)
                    for ref in (prepared["protein_pdb"], prepared["protein_atomtypes"],
                                prepared["protein_chains"][0]["molecule_itp"], prepared["ligand_itp"])}

    rows = consumer.evaluate_request(_request([_case(explicit), _case(inherited)]))["rows"]
    assert [row["status"] for row in rows] == ["evaluated", "evaluated"]
    assert rows[0]["result"]["quantities"] == rows[1]["result"]["quantities"]
    measured, unknown = [row["source_geometry_observation"]["groups"]["receptor"]
                         ["supplied_direct_bond_lengths"] for row in rows]
    assert measured["bond_count"] == unknown["bond_count"] == 1
    assert measured["minimum_angstrom"] == measured["maximum_angstrom"] == pytest.approx(3.5)
    assert measured["explicit_source_equilibrium_count"] == 1
    assert measured["unknown_source_equilibrium_count"] == 0
    assert measured["largest_absolute_measured_minus_source_angstrom"] == pytest.approx(2.5)
    reference = measured["shortest_pairs"][0]["source_equilibrium"]
    assert reference == {
        "status": "explicit", "equilibrium_length_nm_token": ".1",
        "equilibrium_length_angstrom": 1.0,
        "source_topology": "protein_chain_A", "source_line": 7,
        "source_sha256": explicit_ref["sha256"],
        "measured_minus_source_angstrom": pytest.approx(2.5),
    }
    assert unknown["explicit_source_equilibrium_count"] == 0
    assert unknown["unknown_source_equilibrium_count"] == 1
    assert unknown["largest_absolute_measured_minus_source_angstrom"] is None
    assert unknown["shortest_pairs"][0]["source_equilibrium"]["status"] == "inherited_unknown"
    assert unknown["shortest_pairs"][0]["source_equilibrium"]["measured_minus_source_angstrom"] is None
    assert measured["length_validity_assessed"] is unknown["length_validity_assessed"] is False
    assert rows[0]["source_geometry_observation"]["affects_score_or_admission"] is False
    assert all(Path(path).read_bytes() == value for path, value in source_bytes.items())


def _source_angle_triplet(directory, angle_row="1 2 3 1 109.5 100"):
    prepared = _prepared(directory)
    pdb = "".join(
        f"ATOM  {i:5d} {name:>4s} {'SYN':>3s} A{1:4d}    {x:8.3f}{0.0:8.3f}{0.0:8.3f}{1.0:6.2f}{0.0:6.2f}          {'C':>2s}  \n"
        for i, name, x in ((1, "C1", -1.5), (2, "C2", 0.0), (3, "C3", 1.5))) + "END\n"
    _replace(prepared["protein_pdb"], pdb)
    topology = (
        "[ moleculetype ]\nSYN 3\n[ atoms ]\n"
        "1 C 1 SYN C1 1 0.2 12.011\n"
        "2 C 1 SYN C2 2 0.0 12.011\n"
        "3 C 1 SYN C3 3 0.0 12.011\n"
        "[ bonds ]\n1 2 1 .15 100\n2 3 1 .15 100\n"
        "[ angles ]\n" + angle_row + "\n"
    )
    _replace(prepared["protein_chains"][0]["molecule_itp"], topology)
    return prepared


@pytest.mark.parametrize("function_token", ["1", "01"])
def test_explicit_source_angle_detects_collinear_triplet_without_changing_score(tmp_path, function_token):
    from betelgeuze_engine.product.prepared_gromacs_input import load_prepared_gromacs_components
    from betelgeuze_engine.product.v2_cross_interaction import evaluate_prepared_cross_interaction

    prepared = _source_angle_triplet(
        tmp_path / "source", f"1 2 3 {function_token} 109.5 100")
    case = _case(prepared)
    receptor, ligand, rp, lp, provenance = load_prepared_gromacs_components(prepared)
    direct = evaluate_prepared_cross_interaction(receptor, ligand, rp, lp,
        source_declarations=prepared["source_declarations"], **case["evaluation"])
    before = {ref["path"]: Path(ref["path"]).read_bytes() for ref in provenance["sources"].values()}
    row = consumer.evaluate_request(_request([case]))["rows"][0]

    assert row["status"] == "evaluated"
    assert row["result"]["quantities"] == direct["quantities"]
    assert row["result"]["sources"] == direct["sources"]
    observation = row["source_geometry_observation"]
    assert observation["affects_score_or_admission"] is False
    group = observation["groups"]["receptor"]
    assert group["pair_count_within_radius"] == 0
    lengths = group["supplied_direct_bond_lengths"]
    assert lengths["bond_count"] == lengths["explicit_source_equilibrium_count"] == 2
    assert lengths["largest_absolute_measured_minus_source_angstrom"] == pytest.approx(0.0)
    assert group["source_angle_table_status"] == "present_in_all_source_molecules_not_chemical_completeness"
    angles = group["supplied_source_angles"]
    assert angles["angle_count"] == angles["measured_angle_count"] == angles["explicit_source_equilibrium_count"] == 1
    assert angles["unknown_source_equilibrium_count"] == angles["undefined_geometry_count"] == 0
    assert angles["largest_absolute_measured_minus_source_degrees"] == pytest.approx(70.5)
    assert angles["angle_validity_assessed"] is False
    measured = angles["displayed_angles"][0]
    assert measured["measured_angle_degrees"] == pytest.approx(180.0)
    assert [atom["atom_index"] for atom in measured["atoms"]] == [0, 1, 2]
    reference = measured["source_equilibrium"]
    source = prepared["protein_chains"][0]["molecule_itp"]
    assert reference == {
        "status": "explicit", "equilibrium_angle_degrees_token": "109.5",
        "equilibrium_angle_degrees": 109.5, "source_topology": "protein_chain_A",
        "source_line": 11, "source_sha256": source["sha256"],
        "measured_minus_source_degrees": pytest.approx(70.5),
    }
    assert all(Path(path).read_bytes() == content for path, content in before.items())


@pytest.mark.parametrize("angle_row,status", [
    ("1 2 3 1", "inherited_unknown"),
    ("1 2 3 2 109.5 100", "unsupported_source_parameters"),
    ("1 2 3 1 109.5", "unsupported_source_parameters"),
    ("1 2 3 1 nan 100", "unsupported_source_parameters"),
])
def test_inherited_and_unsupported_source_angles_remain_unknown(tmp_path, angle_row, status):
    prepared = _source_angle_triplet(tmp_path / status, angle_row)
    row = consumer.evaluate_request(_request([_case(prepared)]))["rows"][0]
    assert row["status"] == "evaluated"
    angles = row["source_geometry_observation"]["groups"]["receptor"]["supplied_source_angles"]
    assert angles["angle_count"] == angles["measured_angle_count"] == 1
    assert angles["explicit_source_equilibrium_count"] == 0
    assert angles["unknown_source_equilibrium_count"] == 1
    assert angles["largest_absolute_measured_minus_source_degrees"] is None
    displayed = angles["displayed_angles"][0]
    assert displayed["measured_angle_degrees"] == pytest.approx(180.0)
    assert displayed["source_equilibrium"]["status"] == status
    assert displayed["source_equilibrium"]["equilibrium_angle_degrees"] is None
    assert displayed["source_equilibrium"]["measured_minus_source_degrees"] is None


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
    lengths = observation["groups"]["receptor"]["supplied_direct_bond_lengths"]
    if expected is None:
        assert lengths is None
    else:
        assert lengths["bond_count"] == len(adjacency)


def test_supplied_bond_lengths_include_pairs_outside_short_pair_radius():
    from betelgeuze_engine.product.prepared_source_geometry import observe_prepared_source_geometry
    receptor = _system([[0, 0, 0], [1.5, 0, 0], [5, 0, 0]], [0, 0, 0])
    ligand = _system([[10, 0, 0]], [0])
    group = observe_prepared_source_geometry(
        receptor, ligand, _provenance({"bonds": []}, [[0, 1], [1, 2]])
    )["groups"]["receptor"]
    assert group["pair_count_within_radius"] == 0
    lengths = group["supplied_direct_bond_lengths"]
    assert lengths["bond_count"] == 2
    assert lengths["minimum_angstrom"] == pytest.approx(1.5)
    assert lengths["maximum_angstrom"] == pytest.approx(3.5)
    assert [row["distance_angstrom"] for row in lengths["shortest_pairs"]] == pytest.approx([1.5, 3.5])
    assert [row["distance_angstrom"] for row in lengths["longest_pairs"]] == pytest.approx([3.5, 1.5])
    assert [[atom["atom_index"] for atom in row["atoms"]] for row in lengths["longest_pairs"]] == [[1, 2], [0, 1]]
    assert lengths["length_validity_assessed"] is False


def test_bond_length_summary_covers_undisplayed_source_deviation():
    from betelgeuze_engine.product.prepared_source_geometry import observe_prepared_source_geometry

    receptor = _system([[float(i), 0, 0] for i in range(20)], [0] * 20)
    receptor = replace(receptor, atoms=tuple(replace(atom, metadata={
        "prepared_gromacs_source": {"source_atom_index": i + 1,
                                    "source_molecule_label": "protein_chain_A"}})
        for i, atom in enumerate(receptor.atoms)))
    bonds = [[i, i + 1] for i in range(19)]
    rows = [{"line": i + 1, "tokens": [str(i + 1), str(i + 2), "1",
             ".01" if i == 18 else ".1", "100"]} for i in range(19)]
    provenance = _provenance({"bonds": rows}, bonds)
    provenance["sources"] = {"protein_chain_A": {"sha256": "a" * 64}}
    lengths = observe_prepared_source_geometry(
        receptor, _system([[40, 0, 0]], [0]), provenance
    )["groups"]["receptor"]["supplied_direct_bond_lengths"]
    assert lengths["bond_count"] == lengths["explicit_source_equilibrium_count"] == 19
    assert lengths["unknown_source_equilibrium_count"] == 0
    assert lengths["minimum_angstrom"] == lengths["maximum_angstrom"] == 1.0
    assert len(lengths["shortest_pairs"]) == len(lengths["longest_pairs"]) == 16
    assert lengths["unlisted_pair_count"] == 3
    assert all(row["source_equilibrium"]["measured_minus_source_angstrom"] == 0.0
               for row in lengths["shortest_pairs"] + lengths["longest_pairs"])
    assert lengths["largest_absolute_measured_minus_source_angstrom"] == pytest.approx(0.9)


def test_angle_summary_covers_all_source_rows_beyond_bounded_display():
    from betelgeuze_engine.product.prepared_source_geometry import observe_prepared_source_geometry

    receptor = _system([[1.5 * i, 0, 0] for i in range(20)], [0] * 20)
    receptor = replace(receptor, atoms=tuple(replace(atom, metadata={
        "prepared_gromacs_source": {"source_atom_index": i + 1,
                                    "source_molecule_label": "protein_chain_A"}})
        for i, atom in enumerate(receptor.atoms)))
    rows = [{"line": 100 + i,
             "tokens": [str(i + 1), str(i + 2), str(i + 3), "1",
                        "109.5" if i == 17 else "180", "100"]}
            for i in range(18)]
    provenance = _provenance({"bonds": [], "angles": rows}, [])
    provenance["original_topologies"]["ligand_itp"]["sections"]["angles"] = []
    provenance["sources"] = {"protein_chain_A": {"sha256": "a" * 64},
                             "ligand_itp": {"sha256": "c" * 64}}
    provenance["source_hashes_postflight_verified"] = True
    ligand = _system([[40, 0, 0]], [0])
    ligand = replace(ligand, atoms=(replace(ligand.atoms[0], metadata={
        "prepared_gromacs_source": {"source_atom_index": 1}}),))
    observation = observe_prepared_source_geometry(receptor, ligand, provenance)
    assert observation["status"] == "observed"
    angles = observation["groups"]["receptor"]["supplied_source_angles"]
    assert angles["angle_count"] == angles["measured_angle_count"] == angles["explicit_source_equilibrium_count"] == 18
    assert angles["unknown_source_equilibrium_count"] == angles["undefined_geometry_count"] == 0
    assert len(angles["displayed_angles"]) == 16
    assert angles["unlisted_angle_count"] == 2
    assert angles["largest_absolute_measured_minus_source_degrees"] == pytest.approx(70.5)
    assert angles["displayed_angles"][0]["source_equilibrium"]["source_line"] == 117
    assert observation["groups"]["ligand"]["supplied_source_angles"]["angle_count"] == 0


def test_source_angle_missing_compiled_and_zero_vector_stay_unknown():
    from betelgeuze_engine.product.prepared_source_geometry import observe_prepared_source_geometry

    receptor = _system([[0, 0, 0], [0, 0, 0], [1.5, 0, 0]], [0, 0, 0])
    receptor = replace(receptor, atoms=tuple(replace(atom, metadata={
        "prepared_gromacs_source": {"source_atom_index": i + 1,
                                    "source_molecule_label": "protein_chain_A"}})
        for i, atom in enumerate(receptor.atoms)))
    ligand = _system([[4, 0, 0]], [0])
    provenance = _provenance({"bonds": []}, [])
    missing = observe_prepared_source_geometry(receptor, ligand, provenance)
    assert missing["groups"]["receptor"]["source_angle_table_status"] == "missing_in_one_or_more_source_molecules"
    assert missing["groups"]["receptor"]["supplied_source_angles"] is None

    provenance["original_topologies"]["protein_chain_A"]["sections"]["angles"] = [
        {"line": 8, "tokens": ["1", "2", "3", "1", "109.5", "100"]}]
    provenance["sources"] = {"protein_chain_A": {"sha256": "b" * 64}}
    provenance["source_hashes_postflight_verified"] = True
    undefined = observe_prepared_source_geometry(receptor, ligand, provenance)
    assert undefined["status"] == "observed"
    angles = undefined["groups"]["receptor"]["supplied_source_angles"]
    assert angles["angle_count"] == angles["undefined_geometry_count"] == angles["explicit_source_equilibrium_count"] == 1
    assert angles["measured_angle_count"] == 0
    assert angles["explicit_source_equilibrium_count"] + angles["unknown_source_equilibrium_count"] == angles["angle_count"]
    assert angles["measured_angle_count"] + angles["undefined_geometry_count"] == angles["angle_count"]
    assert angles["largest_absolute_measured_minus_source_degrees"] is None
    assert angles["displayed_angles"][0]["geometry_status"] == "undefined_zero_vector"
    assert angles["displayed_angles"][0]["source_equilibrium"]["measured_minus_source_degrees"] is None

    provenance["schema_version"] = "compiled_gromacs_cross_particles_v1"
    compiled = observe_prepared_source_geometry(receptor, ligand, provenance)
    assert compiled["groups"]["receptor"]["source_angle_table_status"] == "compiled_source_angle_mapping_unavailable"
    assert compiled["groups"]["receptor"]["supplied_source_angles"] is None


def test_empty_source_angle_table_requires_verified_source_identity_and_atom_mapping():
    from betelgeuze_engine.product.prepared_source_geometry import observe_prepared_source_geometry

    receptor = _system([[0, 0, 0], [1.5, 0, 0]], [0, 0])
    ligand = _system([[4, 0, 0]], [0])
    provenance = _provenance({"bonds": [], "angles": []}, [])
    provenance["original_topologies"]["ligand_itp"]["sections"]["angles"] = []

    def receptor_group():
        return observe_prepared_source_geometry(receptor, ligand, provenance)["groups"]["receptor"]

    assert receptor_group()["source_angle_table_status"] == "source_angle_identity_unavailable"
    assert receptor_group()["supplied_source_angles"] is None
    provenance["sources"] = {"protein_chain_A": {"sha256": "bad"}}
    provenance["source_hashes_postflight_verified"] = True
    assert receptor_group()["source_angle_table_status"] == "source_angle_identity_unavailable"
    provenance["sources"]["protein_chain_A"]["sha256"] = "a" * 64
    provenance["source_hashes_postflight_verified"] = False
    assert receptor_group()["source_angle_table_status"] == "source_angle_identity_unverified"
    provenance["source_hashes_postflight_verified"] = True
    assert receptor_group()["source_angle_table_status"] == "source_angle_atom_index_unavailable"

    receptor = replace(receptor, atoms=tuple(replace(atom, metadata={
        "prepared_gromacs_source": {"source_atom_index": i + 1,
                                    "source_molecule_label": "protein_chain_A"}})
        for i, atom in enumerate(receptor.atoms)))
    provenance["original_topologies"]["protein_chain_A"]["sections"]["angles"] = {}
    assert receptor_group()["source_angle_table_status"] == "invalid_source_angle_section"
    assert receptor_group()["supplied_source_angles"] is None
    provenance["original_topologies"]["protein_chain_A"]["sections"]["angles"] = []
    group = receptor_group()
    assert group["source_angle_table_status"] == "present_empty_in_all_source_molecules"
    assert group["supplied_source_angles"]["angle_count"] == 0


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

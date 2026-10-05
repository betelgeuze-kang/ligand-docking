"""Fresh synthetic compiled-source controls; no public/protected inputs."""
import copy
import hashlib
from pathlib import Path

import pytest

from betelgeuze_engine.product.compiled_gromacs_cross_input import SCHEMA, SCHEMA_V2, load_compiled_gromacs_cross_particles
from tools.product.score_prepared_cross_interactions import evaluate_request


def _request(tmp_path, *, dummy=False):
    top = """[ defaults ]
1 2 no 1 0.83333333
[ atomtypes ]
C 6 12 0 A .3 .2
H 1 1 0 A .1 0
N 7 14 0 A .3 .3
O 8 16 0 A .3 .4
D AT 0 0 D 0 0
[ moleculetype ]
REC 3
[ atoms ]
1 C 1 REC C1 1 .2 12
2 H 1 REC H1 2 .1 1
{dummy_atom}
[ bonds ]
1 2 1 .1 100
{virtual_site}
[ moleculetype ]
WATER 3
[ atoms ]
1 O 1 SOL O1 1 0 16
#ifndef FLEXIBLE
[ constraints ]
#else
[ bonds ]
#endif
[ moleculetype ]
LIG 3
[ atoms ]
1 N 1 LIG N1 1 -.3 14
2 H 1 LIG H1 2 0 1
[ bonds ]
1 2 1 .1 100
[ system ]
synthetic explicit source
[ molecules ]
REC 1
WATER 1
LIG 1
""".format(dummy_atom="3 D 2 ATT AT1 3 0 0" if dummy else "",
           virtual_site="[ virtual_sites2 ]\n3 1 2 1 .5" if dummy else "")
    records = [(1, "REC", "C1", (0., 0., 0.)), (1, "REC", "H1", (.11, 0., 0.))]
    if dummy:
        records.append((2, "ATT", "AT1", (.055, 0., 0.)))
    records += [(3, "SOL", "O1", (3., 3., 3.)), (4, "LIG", "N1", (.4, 0., 0.)), (4, "LIG", "H1", (.4, .1, 0.))]
    gro = "synthetic\n" + str(len(records)) + "\n"
    for i, (residue, name, atom, xyz) in enumerate(records, 1):
        gro += f"{residue:5d}{name:<5}{atom:>5}{i:5d}{xyz[0]:8.3f}{xyz[1]:8.3f}{xyz[2]:8.3f}\n"
    gro += "4 4 4\n"
    def source(name, text):
        path = tmp_path / name
        path.write_text(text)
        return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "source_id": "synthetic:" + name}
    return {"schema_version": SCHEMA, "topology": source("system.top", top), "coordinates": source("system.gro", gro),
            "selected_molecules": {"receptor": "REC", "ligand": "LIG"}, "excluded_molecules": {"WATER": 1},
            "omitted_inert_sites": {"receptor": [3] if dummy else [], "ligand": []},
            "source_declarations": {k: "synthetic" for k in ["coordinate_frame_id", "prepared_state_id", "parameter_source_id", "charge_source_id"]},
            "source_relationship": "synthetic paired source; no chemical bond-order claim"}


def _edit(request, field, old, new):
    path = Path(request[field]["path"])
    text = path.read_text()
    assert old in text
    path.write_text(text.replace(old, new))
    request[field]["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()


def _refined_request(tmp_path, *, dummy=False):
    request = _request(tmp_path, dummy=dummy)
    original = Path(request["coordinates"]["path"]).read_text().splitlines()
    refined = original[:2]
    for line in original[2:-1]:
        xyz = [float(token) for token in line[20:].split()]
        if line[10:15].strip() == "H1" and line[5:10].strip() == "REC":
            xyz[0] = .1104
        if line[10:15].strip() == "N1":
            xyz[0] = .3997
        refined.append(line[:20] + "".join(f"{value:12.6f}" for value in xyz))
    refined.append(original[-1])
    path = tmp_path / "refined.gro"
    path.write_text("\n".join(refined) + "\n")
    request["schema_version"] = SCHEMA_V2
    request["refined_coordinates"] = {
        "path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "source_id": "synthetic:precision-refinement",
    }
    return request


def test_refined_coordinates_keep_original_source_and_drive_actual_consumer(tmp_path):
    request = _refined_request(tmp_path)
    receptor, ligand, rp, lp, evidence = load_compiled_gromacs_cross_particles(request)
    assert receptor.coordinates[0, 0].tolist() == [0, 0, 0]
    assert receptor.coordinates[0, 1].tolist() == pytest.approx([1.104, 0, 0])
    assert ligand.coordinates[0, 0].tolist() == pytest.approx([3.997, 0, 0])
    assert ligand.coordinates[0, 1].tolist() == [4, 1, 0]
    assert list(evidence["sources"]) == ["topology", "coordinates", "refined_coordinates"]
    observation = evidence["coordinate_refinement_observation"]
    assert observation["source_site_count"] == 5
    assert observation["changed_coordinate_component_count"] == 2
    assert observation["max_component_delta_angstrom"] == pytest.approx(.004)
    assert observation["status"] == "all_source_sites_within_inclusive_half_step_bound"
    assert observation["inclusive_half_step_bound_nm"] == "0.0005"
    assert not observation["exact_original_rounding_reconstruction_verified"]
    assert not observation["source_coordinate_origin_verified"]
    assert not evidence["eligible_for_same_state_assay_join"]
    evaluation = {"pocket_center_angstrom": [4, 0, 0], "pocket_radius_angstrom": 5.,
                  "cutoff_angstrom": 10., "switch_start_angstrom": 8.,
                  "dielectric": 1., "screening_kappa_per_angstrom": 0.}
    result = evaluate_request({"schema_version": "prepared_cross_interaction_request_v1", "cases": [
        {"case_id": "refined", "prepared_input": request, "evaluation": evaluation}]})
    row = result["rows"][0]
    assert row["status"] == "evaluated"
    assert row["source_geometry_observation"]["status"] == "observed"
    # Compiled bond/angle diagnostics from the donor stack are not part of this port.
    for side in ("receptor", "ligand"):
        group = row["source_geometry_observation"]["groups"][side]
        assert group["direct_bond_pair_count"] is None
        assert group["non_direct_bond_pair_count"] is None
    assert receptor.provenance.parser_name == ligand.provenance.parser_name == SCHEMA_V2
    assert receptor.provenance.parser_version == ligand.provenance.parser_version == "2"
    assert receptor.provenance.parent_sha256 == tuple(request[k]["sha256"] for k in ("topology", "coordinates", "refined_coordinates"))
    from tests.unit.test_v2_prepared_cross_interaction import _assert_oracle
    _assert_oracle(row["result"], (receptor, ligand, rp, lp), dielectric=1., kappa=0.)


@pytest.mark.parametrize("defect,field,old,new,reason", [
    ("outside", "refined_coordinates", "0.110400", "0.110600", "half-step bound"),
    ("identity", "refined_coordinates", "1REC     H1", "1REC     X1", "atom identity"),
    ("box", "refined_coordinates", "4 4 4", "5 4 4", "header or box"),
    ("precision", "refined_coordinates", "0.110400", "0.110", "four-to-twelve"),
    ("source_precision", "coordinates", "0.110", "0.11", "three-decimal"),
])
def test_refinement_rejects_unbound_or_ambiguous_coordinates(tmp_path, defect, field, old, new, reason):
    request = _refined_request(tmp_path)
    _edit(request, field, old, new)
    with pytest.raises(ValueError, match=reason):
        load_compiled_gromacs_cross_particles(request)


def test_v1_rejects_refinement_field_and_v2_checks_its_hash(tmp_path):
    request = _refined_request(tmp_path)
    request["schema_version"] = SCHEMA
    with pytest.raises(ValueError, match="exact keys"):
        load_compiled_gromacs_cross_particles(request)
    request["schema_version"] = SCHEMA_V2
    request["refined_coordinates"]["sha256"] = "0" * 64
    with pytest.raises(ValueError, match="source SHA-256 mismatch"):
        load_compiled_gromacs_cross_particles(request)


def test_refinement_parses_adjacent_full_width_original_and_precise_gro_fields(tmp_path):
    request = _refined_request(tmp_path)
    original_path = Path(request["coordinates"]["path"])
    refined_path = Path(request["refined_coordinates"]["path"])
    original = original_path.read_text().splitlines()
    refined = refined_path.read_text().splitlines()
    prefix = original[2][:20]
    original[2] = prefix + "".join(f"{value:8.3f}" for value in (-123.456, -234.567, -345.678))
    refined[2] = prefix + "".join(f"{value:15.10f}" for value in (-123.4561, -234.5671, -345.6781))
    assert len(original[2][20:].split()) == len(refined[2][20:].split()) == 1
    for path, lines, field in ((original_path, original, "coordinates"),
                               (refined_path, refined, "refined_coordinates")):
        path.write_text("\n".join(lines) + "\n")
        request[field]["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    receptor, _, _, _, evidence = load_compiled_gromacs_cross_particles(request)
    assert receptor.coordinates[0, 0].tolist() == pytest.approx([-1234.561, -2345.671, -3456.781])
    assert evidence["coordinate_refinement_observation"]["source_site_count"] == 5


@pytest.mark.parametrize("dummy,atom_name,old,new", [
    (False, "O1", "3.000000", "3.000600"),
    (True, "AT1", "0.055000", "0.055600"),
])
def test_refinement_checks_excluded_and_omitted_sites(tmp_path, dummy, atom_name, old, new):
    request = _refined_request(tmp_path, dummy=dummy)
    path = Path(request["refined_coordinates"]["path"])
    lines = path.read_text().splitlines()
    index = next(index for index, line in enumerate(lines) if line[10:15].strip() == atom_name)
    assert old in lines[index]
    lines[index] = lines[index].replace(old, new)
    path.write_text("\n".join(lines) + "\n")
    request["refined_coordinates"]["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    with pytest.raises(ValueError, match="half-step bound"):
        load_compiled_gromacs_cross_particles(request)


def test_refinement_half_step_endpoint_is_inclusive_without_printout_claim(tmp_path):
    request = _refined_request(tmp_path)
    _edit(request, "refined_coordinates", "0.110400", "0.110500")
    _, _, _, _, evidence = load_compiled_gromacs_cross_particles(request)
    observation = evidence["coordinate_refinement_observation"]
    assert observation["max_component_delta_angstrom"] == pytest.approx(.005)
    assert not observation["exact_original_rounding_reconstruction_verified"]


@pytest.mark.parametrize("dummy", [False, True])
def test_complete_projection_keeps_sources_zeros_and_omissions(tmp_path, dummy):
    request = _request(tmp_path, dummy=dummy)
    receptor, ligand, rp, lp, evidence = load_compiled_gromacs_cross_particles(request)
    assert receptor.atom_count == ligand.atom_count == 2
    assert receptor.coordinates[0].tolist() == [[0, 0, 0], [1.1, 0, 0]]
    assert ligand.coordinates[0].tolist() == [[4, 0, 0], [4, 1, 0]]
    assert rp[1]["epsilon_kcal_per_mol"] == lp[1]["charge_e"] == 0
    assert evidence["site_accounting"] == {"requested_source_sites": 6 if dummy else 5, "selected_physical_sites": 4, "omitted_source_sites": 2 if dummy else 1}
    assert evidence["receptor_source_bond_adjacency"] == evidence["ligand_source_bond_adjacency"] == [[0, 1]]
    assert not receptor.bonds and not ligand.bonds
    assert not evidence["chemical_state_identity_verified"] and not evidence["eligible_for_same_state_assay_join"]
    assert receptor.atoms[0].metadata["formal_charge_observation"] is None
    assert evidence["source_hashes_postflight_verified"]


@pytest.mark.parametrize("defect", ["duplicate_type", "duplicate_molecule", "selected_conditional", "inventory_conditional", "nonfinite_charge", "nonfinite_environment", "name", "residue_partition", "selected_copy_count", "missing_atomtype"])
def test_malformed_or_ambiguous_sources_reject_before_evaluation(tmp_path, defect):
    request = _request(tmp_path)
    if defect == "duplicate_type":
        _edit(request, "topology", "C 6 12 0 A .3 .2", "C 6 12 0 A .3 .2\nC 6 12 0 A .3 .2")
    elif defect == "duplicate_molecule":
        _edit(request, "topology", "WATER 3", "REC 3")
    elif defect == "selected_conditional":
        _edit(request, "topology", "[ atoms ]\n1 C", "#ifndef FLEXIBLE\n[ atoms ]\n1 C")
    elif defect == "inventory_conditional":
        _edit(request, "topology", "WATER 3\n[ atoms ]", "WATER 3\n#ifndef FLEXIBLE\n[ atoms ]")
    elif defect == "nonfinite_charge":
        _edit(request, "topology", "1 C 1 REC C1 1 .2 12", "1 C 1 REC C1 1 nan 12")
    elif defect == "nonfinite_environment":
        _edit(request, "topology", "1 O 1 SOL O1 1 0 16", "1 O 1 SOL O1 1 nan 16")
    elif defect == "name":
        _edit(request, "coordinates", "   C1", "   C2")
    elif defect == "residue_partition":
        _edit(request, "coordinates", "    1REC     H1", "    2REC     H1")
    elif defect == "selected_copy_count":
        _edit(request, "topology", "REC 1\nWATER", "REC 2\nWATER")
    else:
        _edit(request, "topology", "1 C 1 REC", "1 UNKNOWN 1 REC")
    with pytest.raises(ValueError):
        load_compiled_gromacs_cross_particles(request)


@pytest.mark.parametrize("defect", ["charged_dummy", "finite_sigma", "missing_definition", "unlisted_omission", "missing_environment"])
def test_omissions_must_be_explicit_and_inert(tmp_path, defect):
    request = _request(tmp_path, dummy=True)
    if defect == "charged_dummy":
        _edit(request, "topology", "3 D 2 ATT AT1 3 0 0", "3 D 2 ATT AT1 3 .1 0")
    elif defect == "finite_sigma":
        _edit(request, "topology", "D AT 0 0 D 0 0", "D AT 0 0 D inf 0")
    elif defect == "missing_definition":
        _edit(request, "topology", "3 1 2 1 .5", "")
    elif defect == "unlisted_omission":
        request["omitted_inert_sites"]["receptor"] = []
    else:
        request["excluded_molecules"] = {}
    with pytest.raises(ValueError):
        load_compiled_gromacs_cross_particles(request)


def test_actual_consumer_dispatch_retains_failed_case_and_same_kernel(tmp_path):
    good = _request(tmp_path)
    bad = copy.deepcopy(good)
    bad["coordinates"]["sha256"] = "0" * 64
    evaluation = {"pocket_center_angstrom": [4, 0, 0], "pocket_radius_angstrom": 5.,
                  "cutoff_angstrom": 10., "switch_start_angstrom": 8., "dielectric": 1., "screening_kappa_per_angstrom": 0.}
    result = evaluate_request({"schema_version": "prepared_cross_interaction_request_v1", "cases": [
        {"case_id": "positive", "prepared_input": good, "evaluation": evaluation},
        {"case_id": "bad-hash", "prepared_input": bad, "evaluation": evaluation}]})
    assert result["denominator"] == {"requested": 2, "evaluated": 1, "failed": 1, "skipped": 0}
    q = result["rows"][0]["result"]["quantities"]
    assert q["affinity"] is q["strain"] is q["solvation"] is q["residual"] is None
    assert "SHA-256 mismatch" in result["rows"][1]["reason"]
    from tests.unit.test_v2_prepared_cross_interaction import _assert_oracle
    receptor, ligand, rp, lp, _ = load_compiled_gromacs_cross_particles(good)
    _assert_oracle(result["rows"][0]["result"], (receptor, ligand, rp, lp), dielectric=1., kappa=0.)


@pytest.mark.parametrize("schema", [None, True, [], {}, "compiled_gromacs_cross_particles_v3"])
def test_refinement_schema_dispatch_fails_closed(tmp_path, schema):
    request = _refined_request(tmp_path)
    request["schema_version"] = schema
    with pytest.raises(ValueError):
        load_compiled_gromacs_cross_particles(request)


@pytest.mark.parametrize("change", ["missing_refined", "extra_field"])
def test_refinement_v2_exact_request_keys(tmp_path, change):
    request = _refined_request(tmp_path)
    if change == "missing_refined":
        del request["refined_coordinates"]
    else:
        request["unexpected"] = False
    with pytest.raises(ValueError, match="exact keys"):
        load_compiled_gromacs_cross_particles(request)


@pytest.mark.parametrize("field", ["topology", "coordinates", "refined_coordinates"])
def test_refinement_postflight_checks_every_original_source(tmp_path, monkeypatch, field):
    from betelgeuze_engine.product import compiled_gromacs_cross_input as compiled
    request = _refined_request(tmp_path)
    original = compiled._coordinate_refinement

    def mutate_after_initial_read(*args):
        observation = original(*args)
        path = Path(request[field]["path"])
        path.write_bytes(path.read_bytes() + b"\n")
        return observation

    monkeypatch.setattr(compiled, "_coordinate_refinement", mutate_after_initial_read)
    with pytest.raises(ValueError, match="source SHA-256 mismatch"):
        load_compiled_gromacs_cross_particles(request)


@pytest.mark.parametrize("value", ["nan", "inf", "-inf", "0.1104000000000", "0.1104 0.0"])
def test_refinement_rejects_nonfinite_excess_precision_or_extra_coordinates(tmp_path, value):
    request = _refined_request(tmp_path)
    _edit(request, "refined_coordinates", "0.110400", value)
    with pytest.raises(ValueError):
        load_compiled_gromacs_cross_particles(request)


@pytest.mark.parametrize("value", ["0.109500", "0.110500"])
def test_refinement_both_half_step_endpoints_remain_unverified(tmp_path, value):
    request = _refined_request(tmp_path)
    _edit(request, "refined_coordinates", "0.110400", value)
    _, _, _, _, evidence = load_compiled_gromacs_cross_particles(request)
    observation = evidence["coordinate_refinement_observation"]
    assert observation["max_component_delta_angstrom"] == pytest.approx(.005)
    assert not observation["exact_original_rounding_reconstruction_verified"]
    assert not observation["source_coordinate_origin_verified"]
    assert not observation["assay_state_equivalence_verified"]
    assert not evidence["chemical_state_identity_verified"]
    assert not evidence["eligible_for_same_state_assay_join"]
    assert not evidence["source_full_simulation_hamiltonian_reproduced"]


def _negative_fixed_width_refinement(tmp_path, decimals, *, spaced=False):
    request = _refined_request(tmp_path, dummy=True)
    shifts = (-123.456, -234.567, -345.678)
    for field, precision in (("coordinates", 3), ("refined_coordinates", decimals)):
        path = Path(request[field]["path"])
        lines = path.read_text().splitlines()
        for index in range(2, len(lines) - 1):
            line = lines[index]
            values = [float(value) + shift for value, shift in zip(line[20:].split(), shifts)]
            fields = [f"{value:{precision + 5}.{precision}f}" for value in values]
            assert all(len(value) == precision + 5 for value in fields)
            lines[index] = line[:20] + (" ".join(fields) if spaced else "".join(fields))
            assert len(lines[index][20:].split()) == (3 if spaced else 1)
        path.write_text("\n".join(lines) + "\n")
        request[field]["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    return request


@pytest.mark.parametrize("decimals", range(4, 13))
@pytest.mark.parametrize("spaced", [False, True])
def test_every_refined_gro_precision_drives_energy_and_forces(tmp_path, decimals, spaced):
    request = _negative_fixed_width_refinement(tmp_path, decimals, spaced=spaced)
    receptor, ligand, rp, lp, evidence = load_compiled_gromacs_cross_particles(request)
    assert receptor.coordinates[0, 0].tolist() == pytest.approx([-1234.56, -2345.67, -3456.78])
    assert receptor.coordinates[0, 1].tolist() == pytest.approx([-1233.456, -2345.67, -3456.78])
    assert ligand.coordinates[0, 0].tolist() == pytest.approx([-1230.563, -2345.67, -3456.78])
    observation = evidence["coordinate_refinement_observation"]
    assert observation["source_site_count"] == 6  # Includes water and omitted virtual site.
    assert observation["changed_coordinate_component_count"] == 2
    assert observation["max_component_delta_angstrom"] == pytest.approx(.004)
    assert evidence["source_hashes_postflight_verified"]
    assert not evidence["eligible_for_same_state_assay_join"]
    assert not observation["source_coordinate_origin_verified"]
    assert not observation["exact_original_rounding_reconstruction_verified"]
    assert receptor.provenance.parent_sha256 == tuple(
        request[field]["sha256"] for field in ("topology", "coordinates", "refined_coordinates"))
    evaluation = {"pocket_center_angstrom": [-1230.56, -2345.67, -3456.78],
                  "pocket_radius_angstrom": 5., "cutoff_angstrom": 10.,
                  "switch_start_angstrom": 8., "dielectric": 1.,
                  "screening_kappa_per_angstrom": 0.}
    result = evaluate_request({"schema_version": "prepared_cross_interaction_request_v1", "cases": [
        {"case_id": "negative-precise", "prepared_input": request, "evaluation": evaluation}]})
    row = result["rows"][0]
    assert row["status"] == "evaluated"
    from tests.unit.test_v2_prepared_cross_interaction import _assert_oracle
    _assert_oracle(row["result"], (receptor, ligand, rp, lp), dielectric=1., kappa=0.)


@pytest.mark.parametrize("decimals", range(4, 13))
@pytest.mark.parametrize("atom_name", ["C1", "O1", "AT1"])
def test_variable_width_refinement_still_bounds_selected_excluded_omitted_sites(tmp_path, decimals, atom_name):
    request = _negative_fixed_width_refinement(tmp_path, decimals)
    path = Path(request["refined_coordinates"]["path"])
    lines = path.read_text().splitlines()
    index = next(index for index, line in enumerate(lines) if line[10:15].strip() == atom_name)
    width = decimals + 5
    value = float(lines[index][20:20 + width]) + .0006
    lines[index] = lines[index][:20] + f"{value:{width}.{decimals}f}" + lines[index][20 + width:]
    path.write_text("\n".join(lines) + "\n")
    request["refined_coordinates"]["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    with pytest.raises(ValueError, match="half-step bound"):
        load_compiled_gromacs_cross_particles(request)


@pytest.mark.parametrize("decimals", range(4, 13))
@pytest.mark.parametrize("defect", ["velocity", "short_field", "unequal_fields", "nonfinite"])
def test_variable_width_refinement_rejects_malformed_atom_records(tmp_path, decimals, defect):
    request = _negative_fixed_width_refinement(tmp_path, decimals)
    path = Path(request["refined_coordinates"]["path"])
    lines = path.read_text().splitlines()
    width = decimals + 5
    fields = [lines[2][20 + i * width:20 + (i + 1) * width] for i in range(3)]
    if defect == "velocity":
        lines[2] += " 0.1000 0.1000 0.1000"
    elif defect == "short_field":
        lines[2] = lines[2][:-1]
    elif defect == "unequal_fields":
        lines[2] = lines[2][:20] + fields[0] + " " + fields[1] + fields[2][1:]
    else:
        lines[2] = lines[2][:20] + "nan".rjust(width) + "".join(fields[1:])
    path.write_text("\n".join(lines) + "\n")
    request["refined_coordinates"]["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    with pytest.raises(ValueError):
        load_compiled_gromacs_cross_particles(request)


@pytest.mark.parametrize("decimals", [3, 13])
def test_adjacent_refined_precision_outside_profile_still_rejected(tmp_path, decimals):
    request = _negative_fixed_width_refinement(tmp_path, decimals)
    with pytest.raises(ValueError):
        load_compiled_gromacs_cross_particles(request)

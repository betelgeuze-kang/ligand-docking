"""Fresh synthetic compiled-source controls; no public/protected inputs."""
import copy
import hashlib

import pytest

from betelgeuze_engine.product.compiled_gromacs_cross_input import SCHEMA, load_compiled_gromacs_cross_particles
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
    from pathlib import Path
    path = Path(request[field]["path"])
    text = path.read_text()
    assert old in text
    path.write_text(text.replace(old, new))
    request[field]["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()


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

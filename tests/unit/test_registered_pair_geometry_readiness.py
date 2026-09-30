"""Source-frame geometry boundaries on synthetic coordinates; no force/scoring."""
from copy import deepcopy
import csv
import io
import json
from pathlib import Path

import pytest
import torch

from betelgeuze_engine_v2.molecular import AllAtomSystem, Atom, Chain, Residue, StructureProvenance
from betelgeuze_engine_v2.molecular.serialization import canonical_system_json_bytes
from tools.analysis import registered_pair_geometry_readiness as geometry


def document(path, value):
    raw = geometry._canonical(value) + b"\n"
    path.write_bytes(raw)
    return reference(path)


def reference(path):
    import hashlib
    return {"path": str(path.resolve()), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def system(name, points):
    atoms = tuple(Atom(i, f"C{i + 1}", "C", 6, 0, mass_da=12.) for i in range(len(points)))
    return AllAtomSystem(name, atoms, (),
        (Residue(0, "SYN", 0, 1, tuple(range(len(points))), entity_type="non_polymer", hetero=True),),
        (Chain(0, "A", (0,)),), torch.tensor([points], dtype=torch.float64),
        StructureProvenance(source_format="synthetic", source_id=name, source_sha256="0" * 64,
                            parser_name="synthetic-geometry-boundary", parser_version="1"))


def signed(value, field):
    return {**value, field: geometry._sha(value)}


def hexadecimal(points):
    return [[float(value).hex() for value in point] for point in points]


@pytest.fixture
def protocol(tmp_path):
    receptor = system("receptor", [[0., 0., 0.], [0., 10., 0.]])
    ligand = system("control", [[3.4, 0., 0.]])
    far = system("isolated", [[100., 0., 0.]])
    refs = {}
    for name, item in (("receptor", receptor), ("ligand", ligand), ("far", far)):
        path = tmp_path / (name + ".json")
        path.write_bytes(canonical_system_json_bytes(item))
        refs[name] = reference(path)
    cif = tmp_path / "source.cif"
    cif.write_text("""data_test
loop_
_atom_site.id
_atom_site.label_atom_id
_atom_site.type_symbol
_atom_site.label_asym_id
_atom_site.label_comp_id
_atom_site.auth_seq_id
_atom_site.pdbx_PDB_model_num
_atom_site.Cartn_x
_atom_site.Cartn_y
_atom_site.Cartn_z
1 C1 C E SYN 1 1 0.0 0.0 0.0
2 C2 C E SYN 1 1 0.0 10.0 0.0
3 C1 C F SRO 501 1 3.4 0.0 0.0
""")
    rows = [{"prepared_serial": str(i + 1), "prepared_chain": "A", "prepared_residue_number": "1",
             "prepared_residue_name": "SYN", "prepared_atom_name": f"C{i + 1}", "prepared_element": "C",
             "origin": "source_observed_heavy", "source_atom_site_id": str(i + 1)} for i in range(2)]
    mapping = tmp_path / "map.csv"
    with mapping.open("w") as out:
        writer = csv.DictWriter(out, fieldnames=sorted(geometry.MAP_FIELDS))
        writer.writeheader()
        writer.writerows(rows)
    policy = {"all_atom_minimum_distance_angstrom": 1., "heavy_atom_minimum_distance_angstrom": 2.,
              "all_atom_minimum_radius_sum_ratio": .60, "heavy_atom_minimum_radius_sum_ratio": .72,
              "pocket_all_heavy_maximum_radius_angstrom": 10., "radius_table_angstrom": geometry.POLICY["radius_table_angstrom"]}
    policy_ref = document(tmp_path / "geometry-policy.json", policy)
    request = {"schema_id": "cpu_cartesian_registered_pose_request/1.3.0", "receptor": refs["receptor"], "ligand": refs["ligand"]}
    request_ref = document(tmp_path / "request.json", request)
    initial, final = hexadecimal([[3.4, 0., 0.]]), hexadecimal([[3.9, 0., 0.]])
    numerical = signed({"schema_id": "cpu_cartesian_minimization_result/1.3.0", "checkpoint": {
        "state": {"original_coordinates": initial, "current": {"coordinates": final}}}}, "result_sha256")
    result = signed({"schema_id": "cpu_cartesian_registered_pose_result/1.3.0", "execution_complete": True,
                     "binding": signed({"request_sha256": geometry._sha(request)}, "receipt_sha256"),
                     "numerical_result": numerical, "attempt": {"post_coordinates_binary64_hex": final}}, "result_sha256")
    result_ref = document(tmp_path / "result.json", result)
    frame = "source-original-frame"
    def candidate(name, ref, origin, declared_frame):
        return {"candidate_id": name, "input": {"kind": "canonical_all_atom_system", "file": ref},
                "coordinate_origin": origin, "declared_coordinate_frame_id": declared_frame,
                "source_role": None, "assay_microstate_verified": False, "observed_candidate_reference_pose": False}
    return {"schema_version": geometry.PROTOCOL, "source_cif": reference(cif), "receptor": refs["receptor"],
            "receptor_atom_mapping": reference(mapping), "receptor_source_selection": {"model": 1, "label_asym_id": "E"},
            "anchor_selection": {"model": 1, "label_asym_id": "F", "label_comp_id": "SRO", "auth_seq_id": "501", "heavy_atom_count": 1},
            "coordinate_frame_id": frame, "geometry_policy_reference": policy_ref,
            "candidates": [candidate("registered", refs["ligand"], "computational_registered", frame),
                           candidate("isolated", refs["far"], "isolated_ligand_no_receptor_pose", "isolated-frame")],
            "controls": [{"control_id": "SRO_initial_source_heavy_geometry", "input": {
                "kind": "canonical_all_atom_system", "file": refs["ligand"]}, "retained_request": request_ref, "retained_result": result_ref}]}


def test_source_verified_geometry_only_and_separate_control_without_molecular_execution(protocol, monkeypatch):
    from betelgeuze_product.cpu_refinement_v1_2.chemical_features import ExplicitGraphScorer
    from betelgeuze_product.cpu_refinement_v1_2.fixed_receptor import FixedReceptorEvaluator
    from betelgeuze_product.cpu_refinement_v1_3 import minimization, workflow
    def forbidden(*args, **kwargs):
        pytest.fail("geometry arithmetic attempted molecular evaluation")
    for target, name in ((ExplicitGraphScorer, "score_terms"), (FixedReceptorEvaluator, "evaluate"),
                         (minimization, "minimize"), (workflow, "evaluate")):
        monkeypatch.setattr(target, name, forbidden)
    before = deepcopy(protocol)
    result = geometry.evaluate(protocol)
    assert protocol == before
    assert result["receptor_mapping"]["observed_heavy_coordinate_matches"] == 2
    assert result["geometry_ready_candidate_count"] == 1
    assert not result["pair_readiness"]
    assert not result["two_candidate_geometry_passed"]
    assert result["force_evaluations"] == result["score_evaluations"] == 0
    assert result["source_roles_changed"] is False
    assert all(row["source_role"] is None for row in result["candidates"])
    control = result["positive_geometry_controls"][0]
    assert control["initial_direct_source_heavy_rmsd_angstrom"] == 0.
    assert control["retained_final_direct_source_heavy_rmsd_angstrom"] == pytest.approx(.5)
    assert control["candidate_pair_membership"] is False
    assert not control["independent_pose_recovery_admitted"]


def test_frame_relabelling_cannot_move_isolated_coordinates_into_pocket(protocol):
    protocol["candidates"][1]["declared_coordinate_frame_id"] = protocol["coordinate_frame_id"]
    protocol["candidates"][1]["coordinate_origin"] = "computational_registered"
    result = geometry.evaluate(protocol)
    isolated = result["candidates"][1]
    assert isolated["declared_frame_matches"]
    assert not isolated["geometry_ready_only"]
    assert isolated["geometry_blockers"] == ["initial_pose_geometry_not_registered_in_receptor_pocket"]


def test_radius_sum_ratio_is_required_even_when_absolute_distance_passes(protocol):
    ligand = [[2.1, 0., 0.]]
    metrics = geometry._metrics(torch.tensor(ligand).numpy().astype("float64"), ["C"],
                                torch.tensor([[0., 0., 0.]]).numpy().astype("float64"), ["C"],
                                torch.tensor([2.1, 0., 0.]).numpy().astype("float64"))
    assert metrics["checks"]["all_atom_severe_overlap_screen"]
    assert metrics["checks"]["heavy_atom_severe_overlap_screen"]
    assert not metrics["checks"]["heavy_atom_radius_sum_screen"]
    assert not metrics["geometry_screen_passed"]


@pytest.mark.parametrize("change", ["changed_bytes", "duplicate_map", "moved_receptor", "omitted_source_atom",
                                   "observed_reclassified_as_modelled", "weaken_policy", "wrong_anchor"])
def test_hash_or_resealed_source_mapping_policy_tampering_is_rejected(protocol, change):
    if change == "changed_bytes":
        path = Path(protocol["receptor_atom_mapping"]["path"])
        path.write_bytes(path.read_bytes() + b"\n")
    elif change == "duplicate_map":
        path = Path(protocol["receptor_atom_mapping"]["path"])
        rows = list(csv.DictReader(io.StringIO(path.read_text())))
        rows[1]["source_atom_site_id"] = "1"
        with path.open("w") as out:
            writer = csv.DictWriter(out, fieldnames=sorted(geometry.MAP_FIELDS))
            writer.writeheader()
            writer.writerows(rows)
        protocol["receptor_atom_mapping"] = reference(path)
    elif change in {"omitted_source_atom", "observed_reclassified_as_modelled"}:
        path = Path(protocol["receptor_atom_mapping"]["path"])
        rows = list(csv.DictReader(io.StringIO(path.read_text())))
        if change == "omitted_source_atom":
            rows.pop()
            receptor = Path(protocol["receptor"]["path"])
            receptor.write_bytes(canonical_system_json_bytes(system("omitted-receptor", [[0., 0., 0.]])))
            protocol["receptor"] = reference(receptor)
        else:
            rows[1]["origin"] = "explicitly_modelled_heavy"
            rows[1]["source_atom_site_id"] = ""
        with path.open("w") as out:
            writer = csv.DictWriter(out, fieldnames=sorted(geometry.MAP_FIELDS))
            writer.writeheader()
            writer.writerows(rows)
        protocol["receptor_atom_mapping"] = reference(path)
    elif change == "moved_receptor":
        path = Path(protocol["receptor"]["path"])
        path.write_bytes(canonical_system_json_bytes(system("moved-receptor", [[1., 0., 0.], [0., 10., 0.]])))
        protocol["receptor"] = reference(path)
    elif change == "weaken_policy":
        path = Path(protocol["geometry_policy_reference"]["path"])
        value = json.loads(path.read_bytes())
        value["heavy_atom_minimum_radius_sum_ratio"] = .50
        protocol["geometry_policy_reference"] = document(path, value)
    else:
        protocol["anchor_selection"]["label_comp_id"] = "PR49"
    with pytest.raises(ValueError):
        geometry.evaluate(protocol)


@pytest.mark.parametrize("field,value", [("source_role", "fit"), ("assay_microstate_verified", True),
                                          ("observed_candidate_reference_pose", True)])
def test_development_geometry_cannot_promote_roles_or_assay_authority(protocol, field, value):
    protocol["candidates"][0][field] = value
    with pytest.raises(ValueError, match="promotion"):
        geometry.evaluate(protocol)


@pytest.mark.parametrize("change", ["bad_hex", "attempt_mismatch", "initial_source_changed"])
def test_resealed_control_snapshot_cannot_hide_geometry_or_source_change(protocol, change):
    path = Path(protocol["controls"][0]["retained_result"]["path"])
    result = json.loads(path.read_bytes())
    numerical = result["numerical_result"]
    if change == "bad_hex":
        numerical["checkpoint"]["state"]["current"]["coordinates"][0][0] = "nan"
    elif change == "attempt_mismatch":
        result["attempt"]["post_coordinates_binary64_hex"][0][0] = (10.).hex()
    else:
        numerical["checkpoint"]["state"]["original_coordinates"][0][0] = (3.5).hex()
    numerical.pop("result_sha256")
    result["numerical_result"] = signed(numerical, "result_sha256")
    result.pop("result_sha256")
    result = signed(result, "result_sha256")
    protocol["controls"][0]["retained_result"] = document(path, result)
    with pytest.raises(ValueError):
        geometry.evaluate(protocol)


def test_cli_output_is_exclusive_and_keeps_existing_receipt(protocol, tmp_path, capsys):
    source = tmp_path / "protocol.json"
    document(source, protocol)
    output = tmp_path / "receipt.json"
    assert geometry.main(["--protocol", str(source), "--output", str(output)]) == 0
    assert json.loads(capsys.readouterr().out)["pair_readiness"] is False
    before = output.read_bytes()
    with pytest.raises(FileExistsError):
        geometry.main(["--protocol", str(source), "--output", str(output)])
    assert output.read_bytes() == before

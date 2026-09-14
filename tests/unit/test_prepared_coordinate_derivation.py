"""Synthetic coordinate provenance; no minimization or scientific admission."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest
import torch

from betelgeuze_engine.product import prepared_gromacs_input as parser
from betelgeuze_engine_v2.molecular.serialization import canonical_system_sha256
from tests.unit.test_prepared_gromacs_input import request_doc as _legacy_request_doc
from tests.unit.test_prepared_gromacs_input import _ordered_molecule_request
from tests.unit.test_score_prepared_cross_interactions import _case
from tools.product import score_prepared_cross_interactions as consumer


SCHEMA = "prepared_gromacs_coordinate_derivation_v1"


@pytest.fixture
def request_doc(tmp_path):
    return _legacy_request_doc.__wrapped__(tmp_path)


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     allow_nan=False).encode()).hexdigest()


def _source(path, content):
    path.write_text(content)
    return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "source_id": "synthetic:" + path.name}


def _derived(parent, tmp_path):
    pdb = Path(parent["protein_pdb"]["path"]).read_text().splitlines(keepends=True)
    pdb[0] = pdb[0][:38] + f"{0.2:8.3f}" + pdb[0][46:]
    sdf = Path(parent["ligand_sdf"]["path"]).read_text().splitlines(keepends=True)
    sdf[6] = f"{3.1:10.4f}" + sdf[6][10:]
    gro = Path(parent["ligand_gro"]["path"]).read_text().splitlines(keepends=True)
    gro[4] = gro[4][:20] + "0.31000000 0.20000000 0.00000000\n"
    sources = {key: _source(tmp_path / ("derived." + suffix), "".join(lines))
               for key, suffix, lines in [("protein_pdb", "pdb", pdb),
                                         ("ligand_sdf", "sdf", sdf),
                                         ("ligand_gro", "gro", gro)]}
    declarations = {**parent["source_declarations"], "prepared_state_id": "synthetic-derived-1"}
    return {
        "schema_version": SCHEMA,
        "parent_input": copy.deepcopy(parent),
        "derived_coordinates": sources,
        "source_declarations": declarations,
        "coordinate_derivation": {
            "schema_version": "prepared_coordinate_derivation_record_v1",
            "parent_input_sha256": _digest(parent),
            "derived_coordinate_sha256": {key: ref["sha256"] for key, ref in sources.items()},
            "prepared_state_id": declarations["prepared_state_id"],
            "tool": {"name": "synthetic-fixture-writer", "version": "1"},
            "operation": "explicit_synthetic_coordinate_edit",
            "settings": {"fixture_only": True, "new_hydrogen_y_angstrom": 0.2},
            "evidence": {key: _source(tmp_path / (key + ".txt"),
                                      "synthetic fixture; no external solver or physical preparation\n")
                         for key in ("method", "execution", "model")},
            "changed_atom_indices": {"receptor": [0], "ligand": [2]},
            "external_solver_called": False,
        },
    }


@pytest.mark.parametrize("version", [1, 2, 3])
def test_derived_coordinates_retain_parent_and_explicit_origin(request_doc, tmp_path, version):
    if version > 1:
        _ordered_molecule_request(request_doc)
        request_doc["schema_version"] = f"prepared_gromacs_components_v{version}"
    parent = parser.load_prepared_gromacs_components(request_doc)
    request = _derived(request_doc, tmp_path)
    before = copy.deepcopy(request)
    receptor, ligand, rp, lp, evidence = parser.load_prepared_gromacs_components(request)
    assert request == before
    assert rp == parent[2] and lp == parent[3]
    assert receptor.coordinates[0, 0].tolist() == [0.0, 0.2, 0.0]
    assert ligand.coordinates[0, 2].tolist() == [3.1, 2.0, 0.0]
    assert torch.equal(receptor.coordinates[:, 1:], parent[0].coordinates[:, 1:])
    assert torch.equal(ligand.coordinates[:, :2], parent[1].coordinates[:, :2])
    assert evidence["schema_version"] == SCHEMA
    assert evidence["coordinate_origin"] == "locally_derived_computational_coordinates_not_experimental"
    assert evidence["coordinates_generated_upstream"] is True
    assert evidence["coordinates_generated"] is False  # this reader generates none
    assert evidence["external_solver_called"] is False
    assert evidence["upstream_tool_execution_verified"] is False
    assert not any(evidence["claim_policy"].values())
    for side, system, original in [("receptor", receptor, parent[0]), ("ligand", ligand, parent[1])]:
        detail = system.provenance.metadata["coordinate_derivation"]
        assert detail["changed_atom_indices"] == request["coordinate_derivation"]["changed_atom_indices"][side]
        assert detail["parent_system_sha256"] == canonical_system_sha256(original)
        assert detail["parent_system_sha256"] in system.provenance.parent_sha256
        assert system.provenance.metadata["hydrogen_coordinate_origin"] == evidence["coordinate_origin"]
        assert canonical_system_sha256(system) == evidence[side + "_system_sha256"]
        assert not system.provenance.scientifically_validated
    assert parser.load_prepared_gromacs_components(request_doc)[4] == parent[4]


@pytest.mark.parametrize("field,value,match", [
    ("parent_input_sha256", "0" * 64, "parent input SHA-256"),
    ("prepared_state_id", "wrong-state", "prepared state mismatch"),
    ("tool", {"name": "some-tool", "version": ""}, "nonblank"),
    ("operation", "", "nonblank"),
    ("settings", {}, "nonempty"),
    ("settings", {"tolerance": float("nan")}, "finite JSON"),
    ("external_solver_called", 1, "boolean"),
    ("changed_atom_indices", {"receptor": [], "ligand": [2]}, "exactly match"),
    ("changed_atom_indices", {"receptor": [False], "ligand": [2]}, "exactly match"),
    ("changed_atom_indices", {"receptor": [0, 0], "ligand": [2]}, "exactly match"),
    ("changed_atom_indices", {"receptor": [-1], "ligand": [2]}, "exactly match"),
    ("changed_atom_indices", {"receptor": [4], "ligand": [2]}, "exactly match"),
    ("changed_atom_indices", {"receptor": [0], "ligand": [0]}, "exactly match"),
])
def test_inconsistent_or_underspecified_derivation_rejected(request_doc, tmp_path, field, value, match):
    request = _derived(request_doc, tmp_path)
    request["coordinate_derivation"][field] = value
    with pytest.raises(parser.PreparedGromacsInputError, match=match):
        parser.load_prepared_gromacs_components(request)


@pytest.mark.parametrize("key", ["coordinate_frame_id", "parameter_source_id", "charge_source_id", "prepared_state_id"])
def test_only_a_distinct_prepared_state_declaration_is_allowed(request_doc, tmp_path, key):
    request = _derived(request_doc, tmp_path)
    request["source_declarations"][key] = (request_doc["source_declarations"][key]
                                             if key == "prepared_state_id" else "changed")
    with pytest.raises(parser.PreparedGromacsInputError, match="new prepared_state_id"):
        parser.load_prepared_gromacs_components(request)


@pytest.mark.parametrize("role", ["method", "execution", "model"])
def test_every_declared_method_evidence_file_is_required(request_doc, tmp_path, role):
    request = _derived(request_doc, tmp_path)
    del request["coordinate_derivation"]["evidence"][role]
    with pytest.raises(parser.PreparedGromacsInputError, match="exact keys"):
        parser.load_prepared_gromacs_components(request)


def _rewrite_derived(request, key, transform):
    ref = request["derived_coordinates"][key]
    path = Path(ref["path"])
    path.write_text(transform(path.read_text()))
    ref["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    request["coordinate_derivation"]["derived_coordinate_sha256"][key] = ref["sha256"]


@pytest.mark.parametrize("key,transform", [
    ("protein_pdb", lambda text: text[:54] + f"{0.5:6.2f}" + text[60:]),
    ("ligand_sdf", lambda text: text.replace("synthetic prepared ligand", "different source title")),
    ("ligand_sdf", lambda text: text.replace("synthetic-001", "different inert source identity")),
    ("ligand_gro", lambda text: text.replace("synthetic\n", "new title\n")),
    ("ligand_gro", lambda text: text.replace("1.0 1.0 1.0\n", "2.0 2.0 2.0\n")),
])
def test_rehashed_noncoordinate_edits_are_rejected(request_doc, tmp_path, key, transform):
    request = _derived(request_doc, tmp_path)
    _rewrite_derived(request, key, transform)
    with pytest.raises(parser.PreparedGromacsInputError, match="noncoordinate source bytes"):
        parser.load_prepared_gromacs_components(request)


def _selected_ref(request, selection):
    if selection in ("method", "execution", "model"):
        return request["coordinate_derivation"]["evidence"][selection]
    if selection == "parent_topology":
        return request["parent_input"]["ligand_itp"]
    return request["derived_coordinates"][selection]


@pytest.mark.parametrize("selection", ["method", "execution", "model", "parent_topology", "protein_pdb", "ligand_sdf", "ligand_gro"])
def test_all_transitive_file_mutations_are_detected(request_doc, tmp_path, selection):
    request = _derived(request_doc, tmp_path)
    path = Path(_selected_ref(request, selection)["path"])
    path.write_bytes(path.read_bytes() + b"\n")
    with pytest.raises(parser.PreparedGromacsInputError, match="SHA-256 mismatch"):
        parser.load_prepared_gromacs_components(request)


def test_derived_hash_nested_parent_and_forged_claims_rejected(request_doc, tmp_path):
    request = _derived(request_doc, tmp_path)
    mismatch = copy.deepcopy(request)
    mismatch["coordinate_derivation"]["derived_coordinate_sha256"]["protein_pdb"] = "0" * 64
    with pytest.raises(parser.PreparedGromacsInputError, match="output SHA-256 mismatch"):
        parser.load_prepared_gromacs_components(mismatch)
    nested = copy.deepcopy(request)
    nested["parent_input"] = copy.deepcopy(request)
    with pytest.raises(parser.PreparedGromacsInputError, match="nested derivations unsupported"):
        parser.load_prepared_gromacs_components(nested)
    request["coordinate_derivation"]["scientifically_validated"] = True
    with pytest.raises(parser.PreparedGromacsInputError, match="exact keys"):
        parser.load_prepared_gromacs_components(request)


def test_unchanged_coordinates_cannot_be_declared_new_preparation(request_doc, tmp_path):
    request = _derived(request_doc, tmp_path)
    request["derived_coordinates"] = {key: copy.deepcopy(request_doc[key]) for key in request["derived_coordinates"]}
    request["coordinate_derivation"]["derived_coordinate_sha256"] = {
        key: ref["sha256"] for key, ref in request["derived_coordinates"].items()}
    request["coordinate_derivation"]["changed_atom_indices"] = {"receptor": [], "ligand": []}
    with pytest.raises(parser.PreparedGromacsInputError, match="observed coordinate change"):
        parser.load_prepared_gromacs_components(request)


def test_postflight_rechecks_method_files(request_doc, tmp_path, monkeypatch):
    from betelgeuze_engine.product import prepared_coordinate_derivation as derived
    request = _derived(request_doc, tmp_path)
    original = derived._component_derivation
    def changed(*args):
        result = original(*args)
        if args[2] == "receptor":
            path = Path(_selected_ref(request, "execution")["path"])
            path.write_bytes(path.read_bytes() + b"changed after component validation")
        return result
    monkeypatch.setattr(derived, "_component_derivation", changed)
    with pytest.raises(parser.PreparedGromacsInputError, match="SHA-256 mismatch"):
        parser.load_prepared_gromacs_components(request)


def test_method_settings_change_canonical_identity_without_changing_coordinates(request_doc, tmp_path):
    request = _derived(request_doc, tmp_path)
    first = parser.load_prepared_gromacs_components(request)
    request["coordinate_derivation"]["settings"]["declared_second_setting"] = 2
    second = parser.load_prepared_gromacs_components(request)
    assert torch.equal(first[0].coordinates, second[0].coordinates)
    assert first[4]["receptor_system_sha256"] != second[4]["receptor_system_sha256"]
    assert "declared_second_setting" not in first[4]["coordinate_derivation_record"]["settings"]


def test_unchanged_hydrogen_and_heavy_atom_origins_remain_distinct(request_doc, tmp_path):
    request = _derived(request_doc, tmp_path)
    _rewrite_derived(request, "protein_pdb", lambda _: Path(request_doc["protein_pdb"]["path"]).read_text())
    request["coordinate_derivation"]["changed_atom_indices"]["receptor"] = []
    receptor, _, _, _, evidence = parser.load_prepared_gromacs_components(request)
    assert receptor.provenance.metadata["hydrogen_coordinate_origin"] == "published_computational_preparation_not_experimental"
    assert evidence["coordinate_derivation"]["receptor"]["maximum_displacement_angstrom"] == 0.0
    assert evidence["coordinate_derivation"]["ligand"]["changed_heavy_atom_indices"] == []


def test_normal_consumer_retains_derived_provenance_and_failure_denominator(request_doc, tmp_path):
    request = _derived(request_doc, tmp_path)
    invalid = copy.deepcopy(request)
    invalid["coordinate_derivation"]["changed_atom_indices"]["ligand"] = []
    report = consumer.evaluate_request({"schema_version": consumer.SCHEMA,
                                       "cases": [_case(request), _case(invalid)]})
    assert report["denominator"] == {"requested": 2, "evaluated": 1, "failed": 1, "skipped": 0}
    row = report["rows"][0]
    assert row["preparation_provenance"]["schema_version"] == SCHEMA
    assert row["result"]["source_declarations"] == request["source_declarations"]
    assert not report["external_solver_called"] and not report["scientifically_validated"]


def _pose_request(prepared):
    return {"schema_version": "prepared_rigid_pose_cross_request_v1", "prepared_input": prepared,
            "evaluation": _case(prepared)["evaluation"],
            "execution": {"projection_partition": "source_order_v1", "preparation_reuse": "request"},
            "poses": [{"pose_id": str(i), "rotation_matrix": [[1., 0., 0.], [0., 1., 0.], [0., 0., 1.]],
                       "translation_angstrom": [0., 0., float(i)]} for i in range(2)]}


@pytest.mark.parametrize("selection", ["parent_topology", "execution", "protein_pdb"])
def test_resume_retains_derivation_and_rejects_transitive_mutation(request_doc, tmp_path, monkeypatch, selection):
    from betelgeuze_engine.product import prepared_rigid_poses as poses
    request = _pose_request(_derived(request_doc, tmp_path))
    checkpoint = tmp_path / "checkpoint"
    fresh = consumer.evaluate_request(request, checkpoint_dir=checkpoint)
    assert fresh["denominator"]["evaluated"] == 2
    def forbidden(*args, **kwargs):
        pytest.fail("completed resume must not reload or recompute")
    monkeypatch.setattr(poses, "load_prepared_gromacs_components", forbidden)
    resumed = consumer.evaluate_request(request, checkpoint_dir=checkpoint, resume=True)
    assert json.dumps(resumed["rows"], sort_keys=True) == json.dumps(fresh["rows"], sort_keys=True)
    assert resumed["resume_observation"]["restored_rows"] == 2
    path = Path(_selected_ref(request["prepared_input"], selection)["path"])
    path.write_bytes(path.read_bytes() + b"\n")
    with pytest.raises(ValueError, match="input|contract"):
        consumer.evaluate_request(request, checkpoint_dir=checkpoint, resume=True)

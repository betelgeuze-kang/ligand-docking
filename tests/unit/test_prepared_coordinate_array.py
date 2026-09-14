"""Lossless calculation coordinates, source integrity and resume regression tests."""
import copy
import hashlib
import json
import math
from pathlib import Path

import pytest
import torch

from betelgeuze_engine.product import prepared_coordinate_array as arrays
from betelgeuze_engine.product import prepared_coordinate_export as text_export
from betelgeuze_engine.product.prepared_gromacs_input import load_prepared_gromacs_components
from tests.unit.test_prepared_coordinate_derivation import _pose_request
from tests.unit.test_prepared_coordinate_export import make_request
from tools.product import score_prepared_cross_interactions as consumer


def _export(tmp_path):
    request = make_request(tmp_path)
    result = arrays.export_prepared_coordinate_array(request, tmp_path / "array")
    return request, result["prepared_input"]


def _rewrite(prepared, value=None, raw=None):
    ref = prepared["coordinate_array"]
    payload = raw if raw is not None else json.dumps(value).encode()
    Path(ref["path"]).write_bytes(payload)
    ref["sha256"] = hashlib.sha256(payload).hexdigest()
    prepared["coordinate_derivation"]["coordinate_array_sha256"] = ref["sha256"]


@pytest.mark.parametrize("version", [1, 2, 3])
def test_exact_bits_parent_identity_parameters_and_explicit_coordinate_source(tmp_path, version):
    request = make_request(tmp_path, version)
    request["coordinates_angstrom"]["receptor"][0][2] = -0.0
    before = copy.deepcopy(request)
    source_bytes = {str(p): p.read_bytes() for p in tmp_path.iterdir() if p.is_file()}
    parent = load_prepared_gromacs_components(request["parent_input"])
    result = arrays.export_prepared_coordinate_array(request, tmp_path / "array")
    receptor, ligand, rp, lp, provenance = load_prepared_gromacs_components(result["prepared_input"])
    assert request == before
    assert all(Path(p).read_bytes() == raw for p, raw in source_bytes.items())
    assert rp == parent[2] and lp == parent[3]
    for side, system, original in zip(arrays.SIDES, [receptor, ligand], parent[:2]):
        expected = torch.tensor([request["coordinates_angstrom"][side]], dtype=torch.float64)
        assert system.coordinates.dtype == torch.float64
        assert torch.equal(system.coordinates.view(torch.int64), expected.view(torch.int64))
        assert system.atoms == original.atoms and system.bonds == original.bonds
        assert system.provenance.metadata["calculation_coordinate_source"] == "coordinate_array"
        assert not system.provenance.scientifically_validated
    assert result["binary64_coordinate_bits_preserved"]
    assert result["maximum_roundtrip_component_error_angstrom"] == 0.0
    assert not any(result["claim_policy"].values())
    assert provenance["coordinate_source"] == {"receptor": "coordinate_array", "ligand": "coordinate_array"}
    assert provenance["source_declarations"] == request["source_declarations"]
    assert "gro_sdf_max_same_index_coordinate_difference_angstrom" not in provenance
    assert "gro_sdf_max_same_index_coordinate_difference_angstrom" in provenance["parent_coordinate_observations"]
    assert not provenance["external_solver_called"] and not provenance["upstream_tool_execution_verified"]
    assert load_prepared_gromacs_components(request["parent_input"])[4] == parent[4]


def test_sub_text_precision_change_survives_without_relaxing_legacy_writer(tmp_path):
    request = make_request(tmp_path)
    parent = load_prepared_gromacs_components(request["parent_input"])
    request["coordinates_angstrom"] = {s: p.coordinates[0].tolist() for s, p in zip(arrays.SIDES, parent[:2])}
    request["coordinates_angstrom"]["ligand"][0][0] = math.nextafter(request["coordinates_angstrom"]["ligand"][0][0], math.inf)
    with pytest.raises(ValueError, match="vanished"):
        text_export.export_prepared_coordinates(request, tmp_path / "text")
    result = arrays.export_prepared_coordinate_array(request, tmp_path / "array")
    loaded = load_prepared_gromacs_components(result["prepared_input"])
    assert loaded[1].coordinates[0, 0, 0].item() == request["coordinates_angstrom"]["ligand"][0][0]
    assert result["prepared_input"]["coordinate_derivation"]["changed_atom_indices"] == {"receptor": [], "ligand": [0]}


def test_text_rounding_is_not_used_by_array_reader(tmp_path):
    request = make_request(tmp_path)
    text = text_export.export_prepared_coordinates(request, tmp_path / "text")
    array = arrays.export_prepared_coordinate_array(request, tmp_path / "array")
    a = load_prepared_gromacs_components(array["prepared_input"])
    b = load_prepared_gromacs_components(text["prepared_input"])
    assert a[0].coordinates[0, 0, 1].item() == .23456789
    assert b[0].coordinates[0, 0, 1].item() == .235
    assert a[1].coordinates[0, 2, 0].item() == 3.12345678
    assert b[1].coordinates[0, 2, 0].item() == 3.1235


def test_manifest_json_key_order_preserves_canonical_hashes(tmp_path):
    request = make_request(tmp_path)
    for label, ref in request["upstream_method"]["evidence"].items():
        path = Path(ref["path"])
        path.write_text("distinct synthetic evidence: " + label)
        ref["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    result = arrays.export_prepared_coordinate_array(request, tmp_path / "array")
    manifest = json.loads((tmp_path / "array/prepared-input.json").read_text())
    loaded = load_prepared_gromacs_components(manifest)
    for side in arrays.SIDES:
        assert loaded[4][side + "_system_sha256"] == result[side + "_system_sha256"]


@pytest.mark.parametrize("value", [True, "0.2", float("nan"), float("inf"), None, [], 10**400])
def test_invalid_array_numbers_reject_before_output(tmp_path, value):
    request = make_request(tmp_path)
    request["coordinates_angstrom"]["receptor"][0][1] = value
    with pytest.raises(ValueError):
        arrays.export_prepared_coordinate_array(request, tmp_path / "array")
    assert not (tmp_path / "array").exists()


@pytest.mark.parametrize("field,value", [
    ("coordinate_unit", "nanometer"), ("numeric_representation", "binary32"),
    ("atom_order", "source_line"), ("parent_input_sha256", "0" * 64),
    ("parent_system_sha256", {"receptor": "0" * 64, "ligand": "0" * 64}),
    ("coordinates_angstrom", {"receptor": [], "ligand": []}),
    ("coordinates_angstrom", {"receptor": [[1, 2]], "ligand": [[1, 2]]}),
    ("schema_version", "unsupported"),
])
def test_payload_semantics_reject_even_with_rehashed_source(tmp_path, field, value):
    _, prepared = _export(tmp_path)
    payload = json.loads(Path(prepared["coordinate_array"]["path"]).read_text())
    payload[field] = value
    _rewrite(prepared, payload)
    with pytest.raises(ValueError):
        load_prepared_gromacs_components(prepared)


@pytest.mark.parametrize("field,value", [
    ("coordinate_array_sha256", "0" * 64), ("parent_input_sha256", "0" * 64),
    ("prepared_state_id", "wrong"), ("changed_atom_indices", {"receptor": [], "ligand": [2]}),
    ("changed_atom_indices", {"receptor": [False], "ligand": [2]}),
    ("external_solver_called", 1), ("settings", {}),
])
def test_inconsistent_record_rejects(tmp_path, field, value):
    _, prepared = _export(tmp_path)
    prepared["coordinate_derivation"][field] = value
    with pytest.raises(ValueError):
        load_prepared_gromacs_components(prepared)


@pytest.mark.parametrize("key", ["prepared_state_id", "coordinate_frame_id", "parameter_source_id", "charge_source_id"])
def test_state_frame_and_parameter_declarations_remain_strict(tmp_path, key):
    _, prepared = _export(tmp_path)
    prepared["source_declarations"][key] = (prepared["parent_input"]["source_declarations"][key]
                                           if key == "prepared_state_id" else "changed")
    with pytest.raises(ValueError, match="new state"):
        load_prepared_gromacs_components(prepared)


def test_duplicate_payload_keys_reject_even_with_valid_hash(tmp_path):
    _, prepared = _export(tmp_path)
    raw = Path(prepared["coordinate_array"]["path"]).read_bytes()
    _rewrite(prepared, raw=raw.replace(b'{', b'{"coordinate_unit":"nanometer",', 1))
    with pytest.raises(ValueError, match="duplicate"):
        load_prepared_gromacs_components(prepared)


def test_no_change_and_nested_derivation_reject(tmp_path):
    request, prepared = _export(tmp_path)
    nested = copy.deepcopy(request)
    nested["parent_input"] = prepared
    with pytest.raises(ValueError, match="legacy parent"):
        arrays.export_prepared_coordinate_array(nested, tmp_path / "nested")
    parent = load_prepared_gromacs_components(request["parent_input"])
    request["coordinates_angstrom"] = {s: p.coordinates[0].tolist() for s, p in zip(arrays.SIDES, parent[:2])}
    with pytest.raises(ValueError, match="observed coordinate change"):
        arrays.export_prepared_coordinate_array(request, tmp_path / "unchanged")


@pytest.mark.parametrize("selection", ["array", "parent", "execution", "model"])
def test_exact_resume_and_transitive_source_mutation_rejection(tmp_path, monkeypatch, selection):
    from betelgeuze_engine.product import prepared_rigid_poses as poses
    _, prepared = _export(tmp_path)
    request = _pose_request(prepared)
    checkpoint = tmp_path / "checkpoint"
    fresh = consumer.evaluate_request(request, checkpoint_dir=checkpoint)
    assert fresh["denominator"]["evaluated"] == 2
    def forbidden(*args, **kwargs):
        pytest.fail("completed resume must not reload or recompute")
    monkeypatch.setattr(poses, "load_prepared_gromacs_components", forbidden)
    resumed = consumer.evaluate_request(request, checkpoint_dir=checkpoint, resume=True)
    # The journal stores JSON; tuple/list normalization is part of that contract.
    assert json.dumps(resumed["rows"], sort_keys=True) == json.dumps(fresh["rows"], sort_keys=True)
    assert [r["evaluated_ligand_coordinates_angstrom"] for r in resumed["rows"]] == [
        r["evaluated_ligand_coordinates_angstrom"] for r in fresh["rows"]]
    assert resumed["resume_observation"]["restored_rows"] == 2
    sources = {"array": prepared["coordinate_array"], "parent": prepared["parent_input"]["protein_pdb"],
               **prepared["coordinate_derivation"]["evidence"]}
    path = Path(sources[selection]["path"])
    path.write_bytes(path.read_bytes() + b"\n")
    with pytest.raises(ValueError, match="input|contract"):
        consumer.evaluate_request(request, checkpoint_dir=checkpoint, resume=True)


def test_postflight_source_mutation_rejects(tmp_path, monkeypatch):
    _, prepared = _export(tmp_path)
    path = Path(prepared["coordinate_array"]["path"])
    original = arrays._component_derivation
    def mutate(*args, **kwargs):
        result = original(*args, **kwargs)
        path.write_bytes(path.read_bytes() + b"\n")
        return result
    monkeypatch.setattr(arrays, "_component_derivation", mutate)
    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        load_prepared_gromacs_components(prepared)


def test_late_roundtrip_error_never_emits_completed_manifest(tmp_path, monkeypatch):
    request = make_request(tmp_path)
    original = arrays.load_prepared_gromacs_components
    def corrupt(value):
        systems = original(value)
        systems[0].coordinates[0, 0, 1] += .001
        return systems
    monkeypatch.setattr(arrays, "load_prepared_gromacs_components", corrupt)
    with pytest.raises(ValueError, match="roundtrip mismatch"):
        arrays.export_prepared_coordinate_array(request, tmp_path / "array")
    assert not (tmp_path / "array/prepared-input.json").exists()
    assert not (tmp_path / "array/export-report.json").exists()


def test_existing_output_is_preserved_and_cli_duplicate_rejects(tmp_path, capsys):
    request = make_request(tmp_path)
    path = tmp_path / "request.json"
    path.write_text(json.dumps(request))
    args = ["--request", str(path), "--output-dir", str(tmp_path / "array")]
    assert arrays.main(args) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "completed"
    before = {p.name: p.read_bytes() for p in (tmp_path / "array").iterdir()}
    assert arrays.main(args) == 2
    assert json.loads(capsys.readouterr().out)["error_type"] == "FileExistsError"
    assert before == {p.name: p.read_bytes() for p in (tmp_path / "array").iterdir()}
    path.write_text('{"schema_version":"x","schema_version":"y"}')
    assert arrays.main(["--request", str(path), "--output-dir", str(tmp_path / "other")]) == 2
    assert "duplicate" in json.loads(capsys.readouterr().out)["reason"]

"""Source-preserving serialization and consumer checks with synthetic inputs."""
import copy
import hashlib
import json
from pathlib import Path

import pytest

from betelgeuze_engine.product import prepared_coordinate_export as exporter
from betelgeuze_engine.product.prepared_gromacs_input import load_prepared_gromacs_components
from tests.unit.test_prepared_coordinate_derivation import _derived
from tests.unit.test_prepared_gromacs_input import request_doc as _parent_fixture, _ordered_molecule_request
from tests.unit.test_score_prepared_cross_interactions import _case
from tools.product.score_prepared_cross_interactions import evaluate_request, SCHEMA


def make_request(tmp_path, version=1):
    parent = _parent_fixture.__wrapped__(tmp_path)
    if version > 1:
        _ordered_molecule_request(parent)
        parent["schema_version"] = f"prepared_gromacs_components_v{version}"
    fixture = _derived(parent, tmp_path)
    record = fixture["coordinate_derivation"]
    systems = load_prepared_gromacs_components(parent)[:2]
    coordinates = {side: system.coordinates[0].tolist() for side, system in zip(("receptor", "ligand"), systems)}
    coordinates["receptor"][0][1] = 0.23456789
    coordinates["ligand"][2][0] = 3.12345678
    return {"schema_version": exporter.SCHEMA, "parent_input": parent,
            "source_declarations": fixture["source_declarations"], "coordinates_angstrom": coordinates,
            "upstream_method": {key: record[key] for key in ("tool", "operation", "settings", "evidence", "external_solver_called")}}


@pytest.mark.parametrize("version", [1, 2, 3])
def test_export_rounding_parent_bytes_and_consumption(tmp_path, version):
    request = make_request(tmp_path, version)
    before = copy.deepcopy(request)
    original_files = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in tmp_path.iterdir() if p.is_file()}
    dest = tmp_path / "result"
    report = exporter.export_prepared_coordinates(request, dest)
    assert request == before
    assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest() == h for p, h in original_files.items())
    prepared = json.loads((dest / "prepared-input.json").read_text())
    receptor, ligand, _, _, provenance = load_prepared_gromacs_components(prepared)
    assert receptor.coordinates[0, 0, 1].item() == .235
    assert ligand.coordinates[0, 2, 0].item() == 3.1235
    assert prepared["coordinate_derivation"]["changed_atom_indices"] == {"receptor": [0], "ligand": [2]}
    error = report["coordinate_export"]["maximum_roundtrip_component_error_angstrom"]
    assert 0 < error["protein_pdb"] <= .0005
    assert 0 < error["ligand_sdf"] <= .00005
    assert error["ligand_gro"] <= 1e-9
    assert not report["scientifically_validated"] and not any(report["claim_policy"].values())
    assert report["receptor_system_sha256"] == provenance["receptor_system_sha256"]
    assert report["ligand_system_sha256"] == provenance["ligand_system_sha256"]
    result = evaluate_request({"schema_version": SCHEMA, "cases": [_case(prepared)]})
    assert result["denominator"]["evaluated"] == 1


@pytest.mark.parametrize("side,value,match", [
    ("receptor", [], "atom count"), ("ligand", [[0., 0., 0.]], "atom count"),
    ("receptor", "bad", "atom count"),
])
def test_wrong_shape_creates_no_output(tmp_path, side, value, match):
    request = make_request(tmp_path)
    request["coordinates_angstrom"][side] = value
    with pytest.raises(ValueError, match=match):
        exporter.export_prepared_coordinates(request, tmp_path / "result")
    assert not (tmp_path / "result").exists()


@pytest.mark.parametrize("value", [True, float("nan"), float("inf"), "0.2", 10000.0, -1000.0])
def test_nonfinite_boolean_or_overflow_does_not_truncate(tmp_path, value):
    request = make_request(tmp_path)
    request["coordinates_angstrom"]["receptor"][0][0] = value
    with pytest.raises(ValueError):
        exporter.export_prepared_coordinates(request, tmp_path / "result")
    assert not (tmp_path / "result").exists()


def test_changes_lost_to_rounding_are_not_claimed(tmp_path):
    request = make_request(tmp_path)
    systems = load_prepared_gromacs_components(request["parent_input"])[:2]
    request["coordinates_angstrom"] = {side: s.coordinates[0].tolist() for side, s in zip(("receptor", "ligand"), systems)}
    request["coordinates_angstrom"]["receptor"][0][0] += 0.00001
    with pytest.raises(ValueError, match="vanished"):
        exporter.export_prepared_coordinates(request, tmp_path / "result")
    assert not (tmp_path / "result").exists()


def test_existing_destination_is_preserved(tmp_path):
    request = make_request(tmp_path)
    output = tmp_path / "result"
    exporter.export_prepared_coordinates(request, output)
    before = {p.name: p.read_bytes() for p in output.iterdir()}
    with pytest.raises(FileExistsError):
        exporter.export_prepared_coordinates(request, output)
    assert before == {p.name: p.read_bytes() for p in output.iterdir()}


@pytest.mark.parametrize("key", ["prepared_state_id", "coordinate_frame_id", "parameter_source_id", "charge_source_id"])
def test_changed_declarations_fail_before_writing(tmp_path, key):
    request = make_request(tmp_path)
    request["source_declarations"][key] = (request["parent_input"]["source_declarations"][key]
                                            if key == "prepared_state_id" else "changed")
    with pytest.raises(ValueError, match="new state"):
        exporter.export_prepared_coordinates(request, tmp_path / "result")
    assert not (tmp_path / "result").exists()


def test_late_source_mutation_never_emits_completed_input(tmp_path, monkeypatch):
    request = make_request(tmp_path)
    original_write = exporter._write
    def change(path, raw):
        original_write(path, raw)
        if path.suffix == ".pdb":
            parent = Path(request["parent_input"]["protein_pdb"]["path"])
            parent.write_bytes(parent.read_bytes() + b"\n")
    monkeypatch.setattr(exporter, "_write", change)
    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        exporter.export_prepared_coordinates(request, tmp_path / "result")
    assert not (tmp_path / "result/prepared-input.json").exists()
    assert not (tmp_path / "result/export-report.json").exists()


def test_inconsistent_serialization_cannot_emit_completed_input(tmp_path, monkeypatch):
    request = make_request(tmp_path)
    render = exporter._render
    def inconsistent(*args):
        raw, rounded, error = render(*args)
        if args[1] == "protein_pdb":
            rounded[0][1] += .1
        return raw, rounded, error
    monkeypatch.setattr(exporter, "_render", inconsistent)
    with pytest.raises(ValueError, match="roundtrip mismatch"):
        exporter.export_prepared_coordinates(request, tmp_path / "result")
    assert not (tmp_path / "result/prepared-input.json").exists()


def test_cli_success_and_duplicate_json_rejection(tmp_path, capsys):
    request = make_request(tmp_path)
    path = tmp_path / "request.json"
    path.write_text(json.dumps(request))
    assert exporter.main(["--request", str(path), "--output-dir", str(tmp_path / "result")]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "completed"
    path.write_text('{"schema_version":"x","schema_version":"y"}')
    assert exporter.main(["--request", str(path), "--output-dir", str(tmp_path / "other")]) == 2
    assert "duplicate" in json.loads(capsys.readouterr().out)["reason"]
    assert not (tmp_path / "other").exists()

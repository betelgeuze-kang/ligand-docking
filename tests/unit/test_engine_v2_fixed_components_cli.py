"""New synthetic console inputs; no prepared chemistry or protected datasets."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys

import pytest
import torch

from betelgeuze_engine_v2 import cli
from betelgeuze_engine_v2.fixed_components_cli import evaluate_component_documents
from betelgeuze_engine_v2.molecular import (
    AllAtomSystem, Atom, Chain, Residue, StructureProvenance,
    all_atom_system_from_canonical_json, canonical_coordinates_sha256,
    canonical_system_json_bytes, canonical_topology_sha256,
)
from betelgeuze_engine_v2.physics import AtomNonbondedParameter, ReferenceForceFieldParameters


def fresh_documents():
    # Two explicit numerical sites in a common frame, not a protein/ligand support claim.
    document = {}
    coordinate_hashes = {}
    for side, position, charge in (("receptor", 0., 1.), ("ligand", 4., -1.)):
        system = AllAtomSystem(
            system_id="new-console-" + side,
            atoms=(Atom(0, "C0", "C", 6, 0, partial_charge_e=charge),),
            bonds=(), residues=(Residue(0, "SYN", 0, 1, (0,)),),
            chains=(Chain(0, "A", (0,)),),
            coordinates=torch.tensor([[[position, 0., 0.]]], dtype=torch.float64),
            provenance=StructureProvenance(source_format="new_synthetic_control", source_id=side,
                                           metadata={"zero": 0., "evaluation_only": True}),
            metadata={"coordinate_frame_id": "new-console-frame"},
        )
        parameters = ReferenceForceFieldParameters(
            parameter_set_id="new-console-sites", parameter_set_version="1",
            topology_sha256=canonical_topology_sha256(system),
            atom_parameters=(AtomNonbondedParameter(0, 1., 0., charge),),
        )
        document[side + "_system"] = json.loads(canonical_system_json_bytes(system))
        document[side + "_parameters"] = parameters.to_dict()
        coordinate_hashes[side + "_coordinates_sha256"] = canonical_coordinates_sha256(system)
    document["frame_declaration"] = {"coordinate_frame_id": "new-console-frame", **coordinate_hashes}
    document["state_declarations"] = {
        "chemical_state_id": "new-two-site-numerical-state",
        "hydrogen_state": "explicit numerical sites; none inferred",
        "charge_source": "synthetic signed unit charges",
        "parameter_source": "synthetic constants only",
    }
    pocket = {"schema_id": cli.CLI_POCKET_INPUT_SCHEMA_ID,
              "scope": "known_pocket_docking", "method_id": "synthetic-sphere", "method_version": "1",
              "coordinate_frame_id": "new-console-frame", "center_angstrom": [4., 0., 0.],
              "radius_angstrom": 2., "source_artifact_sha256": "a" * 64,
              "implementation_source_sha256": "b" * 64}
    return {"components": json.dumps(document).encode(), "pocket": json.dumps(pocket).encode()}


def _run(tmp_path, documents, *extra):
    arguments = []
    for name, raw in documents.items():
        path = tmp_path / (name + ".json")
        path.write_bytes(raw)
        arguments += ["--" + name, str(path)]
    return subprocess.run(
        [sys.executable, "-B", "-c",
         "from betelgeuze_engine_v2.cli_dispatch import main; raise SystemExit(main())",
         "evaluate-fixed-components", *arguments, *extra],
        capture_output=True, text=True, check=False, timeout=45, env=os.environ.copy(),
    )


def test_actual_dispatch_joins_and_evaluates_explicit_components(tmp_path):
    documents = fresh_documents()
    completed = _run(tmp_path, documents)
    assert completed.returncode == 0, completed.stderr
    result = json.loads(completed.stdout)
    assert result["command_id"].endswith("/evaluate-fixed-components/1.0.0")
    assert result["quantities"]["cross_energy"]["value"] == pytest.approx(-332.063713299 / 4.)
    assert result["quantities"]["total_forces"]["value"][0][0] == pytest.approx(332.063713299 / 16.)
    assert result["requested_count"] == result["evaluated_count"] == 1
    assert result["failure_count"] == 0
    assert result["input_bytes_sha256"] == {k: hashlib.sha256(v).hexdigest() for k, v in documents.items()}
    assert result["not_evaluated"]["strain"] is None
    assert not any(result["claim_policy"].values())
    assert result["consumer_cost"]["wall_seconds"] >= 0
    assert result["consumer_cost"]["peak_rss_bytes"] is None
    evaluated = all_atom_system_from_canonical_json(cli._canonical_bytes(result["evaluated_system"]))
    assert evaluated.coordinates.tolist() == [[[0., 0., 0.], [4., 0., 0.]]]
    for name, raw in documents.items():
        assert (tmp_path / (name + ".json")).read_bytes() == raw


@pytest.mark.parametrize("side", ["receptor", "ligand"])
@pytest.mark.parametrize("defect", ["stale_topology", "missing_charge", "bad_index", "unknown_envelope"])
def test_source_defect_rejected_before_rebinding(side, defect):
    documents = fresh_documents()
    data = json.loads(documents["components"])
    parameters = data[side + "_parameters"]
    if defect == "stale_topology":
        parameters["topology_sha256"] = "0" * 64
    elif defect == "missing_charge":
        del parameters["atom_parameters"][0]["charge_e"]
    elif defect == "bad_index":
        parameters["atom_parameters"][0]["atom_index"] = 1
    else:
        data[side + "_system"]["unsupported_chemical_state"] = True
    with pytest.raises(ValueError):
        evaluate_component_documents(components_raw=json.dumps(data).encode(), pocket_raw=documents["pocket"])


@pytest.mark.parametrize("field", ["coordinate_frame_id", "receptor_coordinates_sha256", "ligand_coordinates_sha256"])
def test_mismatched_frame_declarations_rejected(field):
    documents = fresh_documents()
    data = json.loads(documents["components"])
    data["frame_declaration"][field] = "0" * 64
    with pytest.raises(ValueError):
        evaluate_component_documents(components_raw=json.dumps(data).encode(), pocket_raw=documents["pocket"])


@pytest.mark.parametrize("raw", [b'{"x": 1, "x": 2}', b'{"x": NaN}', b'[]', b'{}'])
def test_invalid_component_json_rejected(raw):
    with pytest.raises(ValueError):
        evaluate_component_documents(components_raw=raw, pocket_raw=fresh_documents()["pocket"])


@pytest.mark.parametrize("name", ["components", "pocket"])
def test_console_never_overwrites_inputs(tmp_path, name):
    documents = fresh_documents()
    completed = _run(tmp_path, documents, "--output", str(tmp_path / (name + ".json")), "--overwrite")
    assert completed.returncode == 2
    failure = json.loads(completed.stderr)
    assert failure["failure_count"] == failure["requested_count"] == 1
    assert failure["evaluated_count"] == 0
    assert "distinct" in failure["reason"]
    for key, raw in documents.items():
        assert (tmp_path / (key + ".json")).read_bytes() == raw


def test_console_failure_keeps_requested_case_in_denominator(tmp_path):
    documents = fresh_documents()
    data = json.loads(documents["components"])
    data["ligand_parameters"]["dielectric"] = 2.
    documents["components"] = json.dumps(data).encode()
    output = tmp_path / "evaluation.json"
    completed = _run(tmp_path, documents, "--output", str(output))
    assert completed.returncode == 2
    failure = json.loads(completed.stderr)
    assert failure["requested_count"] == failure["failure_count"] == 1
    assert failure["evaluated_count"] == 0
    assert failure["failure_stage"] == "input_assembly_or_evaluation"
    assert not output.exists()


def test_console_explicit_output_overwrite_preserves_inputs(tmp_path):
    documents = fresh_documents()
    output = tmp_path / "evaluation.json"
    output.write_text("old-result")
    denied = _run(tmp_path, documents, "--output", str(output))
    assert denied.returncode == 2
    assert json.loads(denied.stderr)["failure_stage"] == "output"
    assert output.read_text() == "old-result"
    completed = _run(tmp_path, documents, "--output", str(output), "--overwrite")
    assert completed.returncode == 0, completed.stderr
    assert json.loads(output.read_bytes())["status"] == "evaluated"
    for key, raw in documents.items():
        assert (tmp_path / (key + ".json")).read_bytes() == raw

"""Fresh synthetic fixed-pose consumer controls, never protected benchmark inputs."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys

import pytest
import torch

from betelgeuze_engine_v2 import cli
from betelgeuze_engine_v2.molecular import (
    AllAtomSystem, Atom, Chain, Residue, StructureProvenance,
    canonical_system_json_bytes, canonical_topology_sha256,
)
from betelgeuze_engine_v2.physics.reference_parameters import (
    AtomNonbondedParameter, ReferenceForceFieldParameters,
)


def fresh_documents():
    # Explicit numerical sites; no protein, binding assay, or verified chemistry claim.
    system = AllAtomSystem(
        system_id="new-fixed-pose-console-control",
        atoms=(Atom(0, "C0", "C", 6, 0, partial_charge_e=1.0),
               Atom(1, "O1", "O", 8, 1, partial_charge_e=-1.0)),
        bonds=(), residues=(Residue(0, "REC", 0, 1, (0,)),
                            Residue(1, "LIG", 1, 1, (1,), entity_type="non-polymer")),
        chains=(Chain(0, "R", (0,)), Chain(1, "L", (1,))),
        coordinates=torch.tensor([[[0., 0., 0.], [4., 0., 0.]]], dtype=torch.float64),
        provenance=StructureProvenance(source_format="new_synthetic_control",
                                      source_id="fixed-pose-console-20260908"),
    )
    parameters = ReferenceForceFieldParameters(
        parameter_set_id="new-console-math-control", parameter_set_version="1",
        topology_sha256=canonical_topology_sha256(system),
        atom_parameters=(AtomNonbondedParameter(0, 1.0, 0.0, 1.0),
                         AtomNonbondedParameter(1, 1.0, 0.0, -1.0)),
    )
    pocket = {"schema_id": cli.CLI_POCKET_INPUT_SCHEMA_ID,
              "scope": "known_pocket_docking", "method_id": "explicit-synthetic-sphere",
              "method_version": "1", "coordinate_frame_id": "synthetic-common-frame",
              "center_angstrom": [4., 0., 0.], "radius_angstrom": 2.,
              "source_artifact_sha256": hashlib.sha256(b"new synthetic sphere declaration").hexdigest(),
              "implementation_source_sha256": hashlib.sha256(b"synthetic literal coordinates v1").hexdigest()}
    partition = {"receptor_atom_indices": [0], "ligand_atom_indices": [1],
                 "state_declarations": {"chemical_state_id": "synthetic-two-site-state",
                                        "hydrogen_state": "explicit numerical sites; no added H",
                                        "charge_source": "synthetic signed unit charges",
                                        "parameter_source": "synthetic math control only"}}
    return {"system": canonical_system_json_bytes(system),
            "parameters": json.dumps(parameters.to_dict()).encode(),
            "pocket": json.dumps(pocket).encode(), "partition": json.dumps(partition).encode()}


def run_console(tmp_path, documents, *extra):
    arguments = []
    for name, raw in documents.items():
        path = tmp_path / (name + ".json")
        path.write_bytes(raw)
        arguments += ["--" + name, str(path)]
    return subprocess.run(
        [sys.executable, "-B", "-c",
         "from betelgeuze_engine_v2.cli_dispatch import main; raise SystemExit(main())",
         "evaluate-fixed-pose", *arguments, *extra],
        capture_output=True, text=True, check=False, timeout=45, env=os.environ.copy())


def test_console_evaluates_new_fixed_pose(tmp_path):
    documents = fresh_documents()
    before = dict(documents)
    completed = run_console(tmp_path, documents)
    assert completed.returncode == 0, completed.stderr
    result = json.loads(completed.stdout)
    assert result["status"] == "evaluated"
    assert result["quantities"]["cross_energy"]["value"] == pytest.approx(-332.063713299 / 4.)
    assert result["quantities"]["total_forces"]["value"][0][0] == pytest.approx(332.063713299 / 16.)
    assert result["not_evaluated"]["strain"] is None
    assert result["not_evaluated"]["pose_retention"] is None
    assert result["input_bytes_sha256"] == {k: hashlib.sha256(v).hexdigest() for k, v in before.items()}
    assert result["evaluated_system"] == json.loads(documents["system"])
    assert result["evaluated_parameters"] == json.loads(documents["parameters"])
    assert result["consumer_cost"]["cpu_seconds"] >= 0
    assert result["consumer_cost"]["peak_rss_bytes"] is None
    assert all((tmp_path / (k + ".json")).read_bytes() == v for k, v in before.items())


@pytest.mark.parametrize("name,mutation", [
    ("partition", lambda d: {**d, "ligand_atom_indices": [0]}),
    ("partition", lambda d: {**d, "state_declarations": {}}),
    ("parameters", lambda d: {k: v for k, v in d.items() if k != "dielectric"}),
    ("parameters", lambda d: {**d, "topology_sha256": "0" * 64}),
    ("pocket", lambda d: {**d, "center_angstrom": [40., 0., 0.]}),
])
def test_console_rejections_keep_request_in_denominator(tmp_path, name, mutation):
    documents = fresh_documents()
    documents[name] = json.dumps(mutation(json.loads(documents[name]))).encode()
    output = tmp_path / "evaluation.json"
    completed = run_console(tmp_path, documents, "--output", str(output))
    assert completed.returncode == 2
    assert not output.exists()
    failure = json.loads(completed.stderr)
    assert failure["status"] == "failure"
    assert failure["requested_count"] == failure["failure_count"] == 1
    assert failure["evaluated_count"] == 0
    assert failure["reason"]
    assert failure["product_qualified"] is False


@pytest.mark.parametrize("name", ["system", "parameters", "pocket", "partition"])
def test_duplicate_json_keys_are_not_last_row_wins(name):
    from betelgeuze_engine_v2.fixed_pose_cli import evaluate_documents
    documents = fresh_documents()
    raw = documents[name]
    key = next(iter(json.loads(raw)))
    documents[name] = b"{" + json.dumps(key).encode() + b":null," + raw[1:]
    with pytest.raises(ValueError, match="duplicate JSON object key"):
        evaluate_documents(**{k + "_raw": v for k, v in documents.items()})


@pytest.mark.parametrize("number", [b"NaN", b"Infinity", b"1e999"])
def test_nonfinite_json_is_rejected_before_evaluation(number):
    from betelgeuze_engine_v2.fixed_pose_cli import evaluate_documents
    documents = fresh_documents()
    documents["partition"] = b'{"receptor_atom_indices":[' + number + b']}'
    with pytest.raises(ValueError):
        evaluate_documents(**{k + "_raw": v for k, v in documents.items()})


def test_explicit_zero_parameter_survives_round_trip():
    from betelgeuze_engine_v2.fixed_pose_cli import parameters_from_document
    document = json.loads(fresh_documents()["parameters"])
    actual = parameters_from_document(document)
    assert actual.to_dict() == document
    assert actual.atom_parameters[0].epsilon_kcal_per_mol == 0.
    assert actual.screening_kappa_per_angstrom == 0.


def test_console_does_not_replace_existing_output_without_flag(tmp_path):
    output = tmp_path / "existing.json"
    output.write_text("user-owned result")
    completed = run_console(tmp_path, fresh_documents(), "--output", str(output))
    assert completed.returncode == 2
    assert output.read_text() == "user-owned result"
    assert "output already exists" in json.loads(completed.stderr)["reason"]


@pytest.mark.parametrize("missing", ["system", "parameters", "pocket", "partition", None])
def test_argument_errors_preserve_failure_accounting(tmp_path, missing):
    documents = fresh_documents()
    if missing:
        del documents[missing]
    completed = run_console(tmp_path, documents, *(["--unknown-option"] if missing is None else []))
    assert completed.returncode == 2
    failure = json.loads(completed.stderr)
    assert failure["error_code"] == "FixedPoseInputError"
    assert failure["requested_count"] == failure["failure_count"] == 1
    assert failure["evaluated_count"] == 0
    assert failure["reason"]


@pytest.mark.parametrize("name", ["system", "parameters", "pocket", "partition"])
def test_output_must_not_replace_input(tmp_path, name):
    documents = fresh_documents()
    completed = run_console(tmp_path, documents, "--output", str(tmp_path / (name + ".json")), "--overwrite")
    assert completed.returncode == 2
    failure = json.loads(completed.stderr)
    assert failure["error_code"] == "FixedPoseInputError"
    assert failure["evaluated_count"] == 0
    assert "input" in failure["reason"]
    assert all((tmp_path / (key + ".json")).read_bytes() == value for key, value in documents.items())


def test_output_parent_alias_cannot_replace_input(tmp_path):
    alias = tmp_path / "directory-alias"
    alias.symlink_to(tmp_path, target_is_directory=True)
    documents = fresh_documents()
    completed = run_console(tmp_path, documents, "--output", str(alias / "system.json"), "--overwrite")
    assert completed.returncode == 2
    assert json.loads(completed.stderr)["evaluated_count"] == 0
    assert (tmp_path / "system.json").read_bytes() == documents["system"]


def test_explicit_overwrite_replaces_only_separate_output(tmp_path):
    documents = fresh_documents()
    output = tmp_path / "old-result.json"
    output.write_text("prior output")
    completed = run_console(tmp_path, documents, "--output", str(output), "--overwrite")
    assert completed.returncode == 0, completed.stderr
    assert json.loads(output.read_text())["status"] == "evaluated"
    assert all((tmp_path / (key + ".json")).read_bytes() == value for key, value in documents.items())


@pytest.mark.parametrize("field", ["unsupported_chemical_state", "evaluation_only"])
def test_system_envelope_cannot_silently_discard_fields(field):
    from betelgeuze_engine_v2.fixed_pose_cli import FixedPoseInputError, evaluate_documents
    documents = fresh_documents()
    system = json.loads(documents["system"])
    system[field] = True
    documents["system"] = json.dumps(system, sort_keys=True, separators=(",", ":")).encode()
    with pytest.raises(FixedPoseInputError, match="canonical system requires exactly"):
        evaluate_documents(**{key + "_raw": raw for key, raw in documents.items()})

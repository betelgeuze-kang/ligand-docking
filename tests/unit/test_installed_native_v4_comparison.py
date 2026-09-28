"""Native v4 source-to-installed-selector and four-arm journal contracts."""

import copy
import json
import shutil
from pathlib import Path

import pytest
from rdkit import Chem
from rdkit.Chem import AllChem

from betelgeuze_product import installed_synthetic_comparison as comparison
from betelgeuze_product import installed_native_v4_comparison as native_cli
from betelgeuze_product import installed_native_v4_source as source_verifier
from betelgeuze_product import installed_native_v4_prepared_binding as binding
from betelgeuze_product import native_v4_chemical_identity as chemical
from tools.product import train_public_chembl_selector as checkout_trainer
from tools.product import public_assay_dataset as common
from tools.product import public_chembl_receptor_intake as checkout_intake
from tests.unit.test_public_chembl_receptor_intake import synthetic_intake
from tests.unit.test_score_prepared_cross_interactions import _prepared, _case


@pytest.fixture
def bounded_source(tmp_path):
    manifest, entries = synthetic_intake.__wrapped__(tmp_path)
    source = tmp_path / "intake"
    checkout_intake.build(manifest["path"], manifest["sha256"], source)
    reference = {
        "schema_version": source_verifier.REFERENCE_SCHEMA,
        "input_dir": str(source),
        "summary_sha256": common.file_sha(source / "summary.json"),
        "phase": "fit",
    }
    return tmp_path, source, reference, entries


def _protocol(reference):
    rows, _ = comparison._native_rows(reference)
    pool = [row["record_id"] for row in rows if row["role"] == "development_test"]
    return {
        "schema_version": comparison.NATIVE_PROTOCOL,
        "source": reference,
        "requests": dict.fromkeys(pool),
        "budget_seconds_per_arm": 20.0,
        "max_engine_calls_per_arm": len(pool),
        "arm_order": ["ai_engine", "similarity", "engine", "similarity_engine"],
        "selection_seed": 17,
        "tie_policy": "seeded_pool_order",
    }


def _bound_request(tmp_path):
    prepared = _prepared(tmp_path / "prepared")
    molecule = Chem.AddHs(Chem.MolFromSmiles("C1CCOCC1"))
    assert AllChem.EmbedMolecule(molecule, randomSeed=17) == 0
    molecule = Chem.RemoveHs(molecule)
    conformer = molecule.GetConformer()
    for index in range(molecule.GetNumAtoms()):
        position = conformer.GetAtomPosition(index)
        conformer.SetAtomPosition(index, (position.x + 4.0, position.y, position.z))
    sdf = Chem.MolToMolBlock(molecule) + "$$$$\n"
    atoms = list(molecule.GetAtoms())
    gro_lines = ["Synthetic prepared ring", str(len(atoms))]
    itp_lines = ["[ moleculetype ]", "LIG 3", "[ atoms ]"]
    for index, atom in enumerate(atoms, 1):
        symbol = atom.GetSymbol()
        pos = conformer.GetAtomPosition(index - 1)
        gro_lines.append(
            f"{1:5d}{'LIG':<5s}{symbol + str(index):>5s}{index:5d}"
            f"{pos.x / 10:8.3f}{pos.y / 10:8.3f}{pos.z / 10:8.3f}")
        itp_lines.append(
            f"{index} {symbol} 1 LIG {symbol}{index} 1 0.0 "
            + ("15.999" if symbol == "O" else "12.011"))
    itp_lines.append("[ bonds ]")
    for bond in molecule.GetBonds():
        itp_lines.append(f"{bond.GetBeginAtomIdx() + 1} {bond.GetEndAtomIdx() + 1} 1")
    contents = {
        "ligand_sdf": sdf,
        "ligand_gro": "\n".join(gro_lines + ["0.0 0.0 0.0", ""]),
        "ligand_itp": "\n".join(itp_lines + [""]),
        "ligand_atomtypes": ("[ atomtypes ]\n"
                             "C 6 12.011 0.0 A 0.300000 0.836800\n"
                             "O 8 15.999 0.0 A 0.300000 0.836800\n"),
    }
    for key, content in contents.items():
        path = prepared[key]["path"]
        with open(path, "w", encoding="utf-8") as stream:
            stream.write(content)
        prepared[key]["sha256"] = common.file_sha(Path(path))
    return {
        "schema_version": "prepared_rigid_pose_cross_request_v1",
        "prepared_input": prepared,
        "evaluation": _case(prepared)["evaluation"],
        "execution": {"projection_partition": "source_order_v1",
                      "preparation_reuse": "request"},
        "poses": [{"pose_id": "synthetic-ring",
                   "rotation_matrix": [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0],
                                       [0.0, 0.0, 1.0]],
                   "translation_angstrom": [0.0, 0.0, 0.0]}],
    }


def _linked_protocol(bounded_source, tmp_path):
    root, _, reference, entries = bounded_source
    request = _bound_request(tmp_path)
    original = source_verifier._verified_intake(reference)[2][-1]
    observation = binding.derive_observation(original, request)
    origin_path = root / "prepared-state-origin.json"
    origin_path.write_bytes(comparison._canonical(observation) + b"\n")
    entries = copy.deepcopy(entries)
    entries[-1][binding.SOURCE_FIELD] = {
        "path": str(origin_path), "sha256": common.file_sha(origin_path),
    }
    metadata_path = root / "metadata.jsonl"
    metadata_path.write_text("".join(json.dumps(row) + "\n" for row in entries))
    manifest_path = root / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["metadata_records"]["sha256"] = common.file_sha(metadata_path)
    manifest_path.write_text(json.dumps(manifest, sort_keys=True, separators=(",", ":")))
    linked_dir = root / "linked-intake"
    checkout_intake.build(str(manifest_path), common.file_sha(manifest_path), linked_dir)
    linked_ref = {**reference, "input_dir": str(linked_dir),
                  "summary_sha256": common.file_sha(linked_dir / "summary.json")}
    protocol = _protocol(linked_ref)
    protocol["schema_version"] = comparison.NATIVE_PROTOCOL_V2
    request_path = tmp_path / "prepared-request.json"
    request_path.write_bytes(comparison._canonical(request) + b"\n")
    candidate = next(iter(protocol["requests"]))
    protocol["requests"][candidate] = {
        "path": str(request_path), "sha256": common.file_sha(request_path),
    }
    return protocol, request, candidate


def test_native_fit_selector_matches_checkout_trainer(bounded_source, tmp_path):
    _, source, reference, _ = bounded_source
    frozen = comparison.freeze(_protocol(reference))
    assert frozen["source_kind"] == comparison.NATIVE_SOURCE_KIND
    assert frozen["source_verification"]["assigned_role_counts"] == {
        "fit": 6, "calibration": 0, "development_test": 1,
    }
    assert frozen["source_verification"]["evaluation_labels_read"] == 0
    expected = checkout_trainer.fit(
        input_dir=source, summary_sha256=reference["summary_sha256"],
        output_dir=tmp_path / "checkout-fit",
    )
    assert expected["evaluation_label_rows_unread"] == 1
    saved = [json.loads(line) for line in
             (tmp_path / "checkout-fit/predictions-before-evaluation-labels.jsonl")
             .read_text().splitlines()]
    actual = comparison._predictions(frozen, "ai_engine")
    for row in saved:
        if row["record_id"] in frozen["pool"]:
            assert actual[row["record_id"]] == pytest.approx(row["predicted"], rel=1e-12)


def test_native_run_rechecks_source_and_reports_zero_engine_calls(bounded_source, tmp_path):
    _, _, reference, _ = bounded_source
    protocol = _protocol(reference)
    root = tmp_path / "native-run"
    result = comparison.run(protocol, root)
    assert result["schema_version"] == comparison.NATIVE_RESULT
    assert result["source_kind"] == comparison.NATIVE_SOURCE_KIND
    assert result["evaluation_labels_read"] == 0
    assert result["scientifically_validated"] is False
    assert result["pool"] == list(protocol["requests"])
    for arm in comparison.ARMS:
        assert result["arms"][arm]["worker_complete"]["engine_calls"] == 0
        assert result["arms"][arm]["denominator"]["requested"] == len(result["pool"])
    assert comparison.verify_run(protocol, root)["status"] == "verified"
    assert comparison.run(protocol, root, resume=True) == result
    changed = copy.deepcopy(protocol)
    changed["source"]["summary_sha256"] = "0" * 64
    assert comparison.verify_run(changed, root)["status"] == "invalid"
    resealed = tmp_path / "resealed-native"
    shutil.copytree(root, resealed)
    priority_path = resealed / "ai_engine/priority.json"
    priority = json.loads(priority_path.read_text())
    candidate = next(iter(priority["predictions"]))
    priority["predictions"][candidate] += 1.0
    priority_path.write_bytes(comparison._canonical(priority) + b"\n")
    result_path = resealed / "comparison.json"
    altered_result = json.loads(result_path.read_text())
    altered_result["arms"]["ai_engine"]["priority"] = priority
    result_path.write_bytes(comparison._canonical(altered_result) + b"\n")
    assert comparison.verify_run(protocol, resealed)["reason"] == (
        "installed_priority_recalculation_mismatch"
    )


def test_native_protocol_rejects_unlinked_prepared_request(bounded_source):
    _, _, reference, _ = bounded_source
    protocol = _protocol(reference)
    protocol["requests"][next(iter(protocol["requests"]))] = {
        "path": "/unopened/prepared-pose.json", "sha256": "0" * 64,
    }
    with pytest.raises(ValueError, match="native_prepared_candidate_identity_link_not_supported"):
        comparison.freeze(protocol)


def test_native_v2_synthetic_structural_binding_run_verify_resume(bounded_source, tmp_path):
    protocol, _, candidate = _linked_protocol(bounded_source, tmp_path)
    assert source_verifier.verify_source(protocol["source"])["assigned_role_counts"] == {
        "fit": 6, "calibration": 0, "development_test": 1,
    }
    frozen = comparison.freeze(protocol)
    assert frozen["prepared_bindings"][candidate]["candidate_prepared_identity_bound"] is True
    assert frozen["same_prepared_assay_state_verified"] is False
    root = tmp_path / "linked-run"
    result = comparison.run(protocol, root)
    assert result["schema_version"] == comparison.NATIVE_RESULT_V2
    assert result["candidate_prepared_identity_bound"] == {candidate: True}
    assert result["same_prepared_assay_state_verified"] is False
    assert result["scientifically_validated"] is False
    assert result["evaluation_labels_read"] == 0
    assert result["arms"]["engine"]["worker_complete"]["engine_calls"] == 1
    assert comparison.verify_run(protocol, root)["status"] == "verified"
    assert comparison.run(protocol, root, resume=True) == result


@pytest.mark.parametrize("change,reason", [
    ("microstate", "native_prepared_source_link_mismatch"),
    ("pocket", "native_prepared_source_link_mismatch"),
    ("parameter", "native_prepared_source_link_mismatch"),
    ("receptor", "native_prepared_source_link_mismatch"),
    ("source_hash", "SHA-256 mismatch"),
    ("origin", "source_sha256_mismatch"),
])
def test_native_v2_rejects_resealed_prepared_mismatches_before_run(
    bounded_source, tmp_path, change, reason,
):
    protocol, request, candidate = _linked_protocol(bounded_source, tmp_path)
    altered = copy.deepcopy(protocol)
    if change == "microstate":
        request["prepared_input"]["source_declarations"]["prepared_state_id"] = "different"
    elif change == "pocket":
        request["evaluation"]["pocket_center_angstrom"] = [1.0, 0.0, 0.0]
    elif change == "parameter":
        request["prepared_input"]["source_declarations"]["parameter_source_id"] = "different"
    elif change == "receptor":
        pdb = Path(request["prepared_input"]["protein_pdb"]["path"])
        pdb.write_text(pdb.read_text().replace("   0.000   0.000   0.000",
                                               "   0.500   0.000   0.000"))
        request["prepared_input"]["protein_pdb"]["sha256"] = common.file_sha(pdb)
    elif change == "source_hash":
        request["prepared_input"]["ligand_itp"]["sha256"] = "0" * 64
    else:
        source_rows = source_verifier._verified_intake(protocol["source"])[2]
        origin_path = source_rows[-1]["source_origins"][binding.SOURCE_FIELD]["path"]
        with open(origin_path, "a", encoding="utf-8") as stream:
            stream.write(" ")
        with pytest.raises(ValueError, match=reason):
            comparison.freeze(altered)
        return
    path = altered["requests"][candidate]["path"]
    with open(path, "wb") as stream:
        stream.write(comparison._canonical(request) + b"\n")
    altered["requests"][candidate]["sha256"] = common.file_sha(Path(path))
    with pytest.raises(ValueError, match=reason):
        comparison.freeze(altered)


@pytest.mark.parametrize("identity", ["C1CCCCC1", "C1CCOCC1"])
def test_native_v2_rejects_candidate_graph_charge_or_stereo_identity(
    bounded_source, tmp_path, identity,
):
    protocol, request, _ = _linked_protocol(bounded_source, tmp_path)
    row = copy.deepcopy(source_verifier._verified_intake(protocol["source"])[2][-1])
    row["chemical_identity"] = chemical.chemical_identity(identity)
    if identity == "C1CCOCC1":
        row["chemical_identity"]["formal_charge"] = 1
    with pytest.raises(ValueError, match="native_prepared_ligand_chemical_identity_mismatch"):
        binding.derive_observation(row, request)


def test_native_v2_rejects_unresolved_candidate_stereo(bounded_source, tmp_path):
    protocol, request, _ = _linked_protocol(bounded_source, tmp_path)
    row = copy.deepcopy(source_verifier._verified_intake(protocol["source"])[2][-1])
    row["chemical_identity"]["stereo_unspecified_count"] = 1
    with pytest.raises(ValueError, match="native_prepared_ligand_chemical_identity_mismatch"):
        binding.derive_observation(row, request)


def test_native_v2_installed_source_rejects_outcome_in_prepared_descriptor(
    bounded_source, tmp_path,
):
    root, _, _, entries = bounded_source
    _linked_protocol(bounded_source, tmp_path)
    origin_path = root / "prepared-state-origin.json"
    descriptor = json.loads(origin_path.read_text())
    descriptor["value"] = "SYNTHETIC_EVALUATION_SENTINEL"
    origin_path.write_text(json.dumps(descriptor, sort_keys=True))
    entries = copy.deepcopy(entries)
    entries[-1][binding.SOURCE_FIELD] = {
        "path": str(origin_path), "sha256": common.file_sha(origin_path),
    }
    metadata_path = root / "metadata.jsonl"
    metadata_path.write_text("".join(json.dumps(row) + "\n" for row in entries))
    manifest_path = root / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["metadata_records"]["sha256"] = common.file_sha(metadata_path)
    manifest_path.write_text(json.dumps(manifest, sort_keys=True))
    poisoned = root / "poisoned-intake"
    checkout_intake.build(str(manifest_path), common.file_sha(manifest_path), poisoned)
    with pytest.raises(ValueError, match="outcome_or_nonmetadata_field_in_prepared_state_origin"):
        source_verifier.verify_source({
            "schema_version": source_verifier.REFERENCE_SCHEMA,
            "input_dir": str(poisoned),
            "summary_sha256": common.file_sha(poisoned / "summary.json"),
            "phase": "fit",
        })


def test_native_v2_unlinked_current_source_stays_null_only(bounded_source, tmp_path):
    _, _, reference, _ = bounded_source
    protocol = _protocol(reference)
    protocol["schema_version"] = comparison.NATIVE_PROTOCOL_V2
    frozen = comparison.freeze(protocol)
    assert all(value is None for value in frozen["prepared_bindings"].values())
    candidate = next(iter(protocol["requests"]))
    request_path = tmp_path / "request.json"
    request_path.write_bytes(comparison._canonical(_bound_request(tmp_path)) + b"\n")
    protocol["requests"][candidate] = {
        "path": str(request_path), "sha256": common.file_sha(request_path),
    }
    with pytest.raises(ValueError, match="native_prepared_source_link_missing"):
        comparison.freeze(protocol)


def test_native_entry_rejects_synthetic_protocol(tmp_path):
    protocol = tmp_path / "protocol.json"
    protocol.write_text(json.dumps({"schema_version": comparison.PROTOCOL}))
    with pytest.raises(ValueError, match="native_v4_comparison_requires_native_protocol"):
        native_cli.main(["verify-run", "--protocol", str(protocol),
                         "--run-dir", str(tmp_path / "absent")])

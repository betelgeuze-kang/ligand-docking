"""Native v4 source-to-installed-selector and four-arm journal contracts."""

import copy
import gzip
import json
import shutil
from pathlib import Path

import pytest
from rdkit import Chem
from rdkit.Chem import AllChem

from betelgeuze_engine.product.prepared_rigid_poses import evaluate_rigid_pose_request
from betelgeuze_product import installed_synthetic_comparison as comparison
from betelgeuze_product import installed_native_v4_comparison as native_cli
from betelgeuze_product import installed_native_v4_protocol_preflight as preflight
from betelgeuze_product import installed_native_v4_source as source_verifier
from betelgeuze_product import installed_native_v4_prepared_binding as binding
from betelgeuze_product import native_v4_chemical_identity as chemical
from tools.product import train_public_chembl_selector as checkout_trainer
from tools.product import public_assay_dataset as common
from tools.product import public_assay_components as components
from tools.product import public_chembl_receptor_intake as checkout_intake
from tests.unit.test_public_chembl_receptor_intake import synthetic_intake, ref as source_ref
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


def _bound_request(tmp_path, smiles="C1CCOCC1", sd_value=None):
    prepared = _prepared(tmp_path / "prepared")
    molecule = Chem.AddHs(Chem.MolFromSmiles(smiles))
    assert AllChem.EmbedMolecule(molecule, randomSeed=17) == 0
    molecule = Chem.RemoveHs(molecule)
    conformer = molecule.GetConformer()
    for index in range(molecule.GetNumAtoms()):
        position = conformer.GetAtomPosition(index)
        conformer.SetAtomPosition(index, (position.x + 4.0, position.y, position.z))
    sdf = Chem.MolToMolBlock(molecule)
    if sd_value is not None:
        sdf += f"> <source_identity>\n{sd_value}\n\n"
    sdf += "$$$$\n"
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


def _two_linked_protocol(tmp_path, *, second_frame=False, second_method=False,
                         second_state=False, missing_origin=False,
                         second_smiles="CC1CCOCC1", sd_value=None):
    root = tmp_path / "source"
    root.mkdir()
    manifest_ref, entries = synthetic_intake.__wrapped__(root)
    original = entries[-1]
    metadata = json.loads(Path(original["metadata_origin"]["path"]).read_text())
    metadata.update(activity_id=8, record_id=108, molecule_chembl_id="CHEMBL708",
                    canonical_smiles=second_smiles)
    role = json.loads(Path(original["role_origin"]["path"]).read_text())
    role.update(record_id="chembl:activity:8", node_id="synthetic:node:7")
    added = copy.deepcopy(original)
    added.update(activity_id=8, node_id=role["node_id"],
                 metadata_origin=source_ref(root, metadata, "metadata7.json"),
                 role_origin=source_ref(root, role, "role7.json"))
    if second_method:
        method = json.loads(Path(original["method_origin"]["path"]).read_text())
        method["description"] += " with alternate incubation"
        added["method_origin"] = source_ref(root, method, "method7.json")
    entries.append(added)
    metadata_path = root / "metadata.jsonl"
    metadata_path.write_text("".join(json.dumps(entry) + "\n" for entry in entries))
    context_path = root / "context.jsonl.gz"
    context = [json.loads(line) for line in
               gzip.decompress(context_path.read_bytes()).decode().splitlines()]
    context.append(components.node_from_raw(
        {"ChEMBL Assay ID": metadata["assay_chembl_id"],
         "ChEMBL Document ID": metadata["document_chembl_id"]},
        common.chemical_identity(metadata["canonical_smiles"]),
        node_id=role["node_id"], record_id=role["record_id"],
        ligand_id="chembl:molecule:" + metadata["molecule_chembl_id"],
        extra_declarations=[{"role": "development_test"}],
    ))
    context_path.write_bytes(gzip.compress(
        "".join(json.dumps(node) + "\n" for node in context).encode(), mtime=0))
    manifest_path = Path(manifest_ref["path"])
    manifest = json.loads(manifest_path.read_text())
    manifest["metadata_records"]["sha256"] = common.file_sha(metadata_path)
    manifest["identity_context"]["sha256"] = common.file_sha(context_path)
    manifest_path.write_text(json.dumps(manifest))
    source_dir = root / "intake"
    checkout_intake.build(str(manifest_path), common.file_sha(manifest_path), source_dir)
    source_reference = {
        "schema_version": source_verifier.REFERENCE_SCHEMA,
        "input_dir": str(source_dir),
        "summary_sha256": common.file_sha(source_dir / "summary.json"),
        "phase": "fit",
    }
    candidate_rows = [row for row in source_verifier._verified_intake(source_reference)[2]
                      if row["assigned_role"] == "development_test"]
    assert len(candidate_rows) == 2
    requests = {}
    for row in candidate_rows:
        rid = row["record_id"]
        if row["prediction_issues"]:
            requests[rid] = None
            continue
        request = _bound_request(tmp_path / rid.replace(":", "-"),
                                 row["chemical_identity"]["canonical_isomeric_smiles"],
                                 sd_value=sd_value)
        if second_frame and rid == "chembl:activity:8":
            request["prepared_input"]["source_declarations"]["coordinate_frame_id"] = (
                "synthetic-other-frame"
            )
        if second_state and rid == "chembl:activity:8":
            request["prepared_input"]["source_declarations"]["prepared_state_id"] = (
                "synthetic-other-ligand-state"
            )
        observation = binding.derive_observation(row, request)
        origin_path = root / (rid.replace(":", "-") + "-prepared-origin.json")
        origin_path.write_bytes(comparison._canonical(observation) + b"\n")
        entry = next(item for item in entries if item["activity_id"] == row["activity_id"])
        if not (missing_origin and rid == "chembl:activity:8"):
            entry[binding.SOURCE_FIELD] = {
                "path": str(origin_path), "sha256": common.file_sha(origin_path)}
        request_path = root / (rid.replace(":", "-") + "-request.json")
        request_path.write_bytes(comparison._canonical(request) + b"\n")
        requests[rid] = {"path": str(request_path),
                         "sha256": common.file_sha(request_path)}
    metadata_path.write_text("".join(json.dumps(entry) + "\n" for entry in entries))
    manifest["metadata_records"]["sha256"] = common.file_sha(metadata_path)
    manifest_path.write_text(json.dumps(manifest))
    linked_dir = root / "linked-intake"
    checkout_intake.build(str(manifest_path), common.file_sha(manifest_path), linked_dir)
    linked_reference = {**source_reference, "input_dir": str(linked_dir),
                        "summary_sha256": common.file_sha(linked_dir / "summary.json")}
    protocol = _protocol(linked_reference)
    protocol["schema_version"] = comparison.NATIVE_PROTOCOL_V2
    protocol["requests"] = requests
    return protocol


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


def test_native_v2_preflight_two_linked_chemicals_run_verify_resume(tmp_path, capsys):
    protocol = _two_linked_protocol(tmp_path)
    readiness = preflight.preflight_v2(protocol)
    assert readiness["status"] == "ready"
    assert readiness["blockers"] == []
    assert readiness["candidate_count"] == 2
    assert readiness["distinct_Ki_chemical_identity_count"] == 2
    assert readiness["assigned_role_counts"] == {
        "fit": 6, "calibration": 0, "development_test": 2}
    assert readiness["protocol"] == protocol
    assert readiness["protocol_sha256"] == comparison._sha(protocol)
    assert readiness["evaluation_labels_read"] == 0
    assert readiness["numeric_validation_completed"] is False
    assert readiness["source_authenticated"] is False
    assert readiness["same_prepared_assay_state_verified"] is False
    assert readiness["scientifically_validated"] is False
    assert readiness["training_admitted"] is False
    assert readiness["product_ranking_enabled"] is False
    draft = tmp_path / "draft-protocol.json"
    draft.write_bytes(comparison._canonical(protocol) + b"\n")
    admitted = tmp_path / "preflight-protocol.json"
    assert native_cli.main(["preflight-v2", "--protocol", str(draft),
                            "--output-protocol", str(admitted)]) == 0
    printed = json.loads(capsys.readouterr().out)
    assert printed["status"] == "ready"
    assert "protocol" not in printed
    assert comparison._read_protocol(admitted) == protocol
    run_dir = tmp_path / "two-candidate-run"
    result = comparison.run(comparison._read_protocol(admitted), run_dir)
    assert set(result["pool"]) == set(protocol["requests"])
    assert len(result["pool"]) == 2
    assert result["budget_seconds_per_arm"] == protocol["budget_seconds_per_arm"]
    assert result["max_engine_calls_per_arm"] == 2
    for arm in comparison.ARMS:
        observed = result["arms"][arm]
        assert {row["record_id"] for row in observed["rows"]} == set(result["pool"])
        assert observed["denominator"] == {"requested": 2, "evaluated": 2}
        assert observed["completion"]["status"] == "complete"
        assert observed["completion"]["budget_seconds"] == protocol["budget_seconds_per_arm"]
        assert observed["worker_complete"]["engine_calls"] == (
            0 if arm == "similarity" else 2
        )
        if arm != "similarity":
            assert all(row["numeric_denominator"]["passed"] == 1
                       for row in observed["rows"])
    assert result["evaluation_labels_read"] == 0
    assert result["scientifically_validated"] is False
    assert comparison.verify_run(protocol, run_dir)["status"] == "verified"
    assert comparison.run(protocol, run_dir, resume=True) == result


def test_native_v2_preflight_allows_distinct_bound_ligand_state_ids(tmp_path):
    protocol = _two_linked_protocol(tmp_path, second_state=True)
    receipt = preflight.preflight_v2(protocol)
    assert receipt["status"] == "ready"
    assert receipt["same_prepared_assay_state_verified"] is False


def test_native_v2_preflight_blocks_unusable_pose_geometry(tmp_path, capsys):
    protocol = _two_linked_protocol(tmp_path)
    for ref in protocol["requests"].values():
        path = Path(ref["path"])
        request = json.loads(path.read_text())
        request["poses"][0]["translation_angstrom"] = [100.0, 0.0, 0.0]
        path.write_bytes(comparison._canonical(request) + b"\n")
        ref["sha256"] = common.file_sha(path)
    receipt = preflight.preflight_v2(protocol)
    assert receipt["status"] == "blocked"
    assert receipt["candidate_count"] == 2
    assert receipt["distinct_Ki_chemical_identity_count"] == 2
    assert {item["record_id"] for item in receipt["blockers"]
            if item["code"] == "prepared_pose_geometry_unusable"} == set(protocol["requests"])
    assert receipt["protocol"] is None
    assert receipt["numeric_validation_completed"] is False
    assert receipt["evaluation_labels_read"] == 0
    assert receipt["scientifically_validated"] is False
    draft = tmp_path / "out-of-pocket-draft.json"
    draft.write_bytes(comparison._canonical(protocol) + b"\n")
    admitted = tmp_path / "must-not-exist.json"
    assert native_cli.main(["preflight-v2", "--protocol", str(draft),
                            "--output-protocol", str(admitted)]) == 2
    assert not admitted.exists()
    assert not (tmp_path / "run").exists()
    assert json.loads(capsys.readouterr().out)["status"] == "blocked"


def test_native_v2_preflight_keeps_candidate_with_one_usable_pose(tmp_path):
    protocol = _two_linked_protocol(tmp_path)
    ref = next(iter(protocol["requests"].values()))
    path = Path(ref["path"])
    request = json.loads(path.read_text())
    unusable = copy.deepcopy(request["poses"][0])
    unusable["pose_id"] = "out-of-pocket"
    unusable["translation_angstrom"] = [100.0, 0.0, 0.0]
    request["poses"].append(unusable)
    path.write_bytes(comparison._canonical(request) + b"\n")
    ref["sha256"] = common.file_sha(path)
    receipt = preflight.preflight_v2(protocol)
    assert receipt["status"] == "ready"
    assert receipt["candidate_count"] == 2
    assert receipt["numeric_validation_completed"] is False


@pytest.mark.parametrize("change,blocker", [
    ("one_identity", "two_distinct_Ki_chemical_identities_required"),
    ("duplicate_identity", "two_distinct_Ki_chemical_identities_required"),
    ("unsupported_selector", "candidate_not_Ki_selector_supported"),
    ("missing_request", "prepared_request_missing"),
    ("missing_origin", "prepared_source_origin_missing"),
    ("changed_request", "prepared_source_binding_failed"),
    ("bad_execution", "prepared_execution_unsupported"),
    ("different_method", "method_or_receptor_pocket_frame_mismatch"),
    ("different_frame", "method_or_receptor_pocket_frame_mismatch"),
    ("short_cap", "engine_call_cap_below_candidate_count"),
])
def test_native_v2_preflight_blocks_incomplete_or_crossed_cohort(tmp_path, change, blocker):
    if change == "one_identity":
        bounded = bounded_source.__wrapped__(tmp_path)
        protocol, _, _ = _linked_protocol(bounded, tmp_path)
    else:
        protocol = _two_linked_protocol(
            tmp_path, second_method=change == "different_method",
            second_frame=change == "different_frame",
            missing_origin=change == "missing_origin",
            second_smiles=("C1CCOCC1" if change == "duplicate_identity" else
                           "C1CCSCC1" if change == "unsupported_selector" else
                           "CC1CCOCC1"),
        )
    if change == "missing_request":
        protocol["requests"]["chembl:activity:8"] = None
    elif change == "changed_request":
        ref = protocol["requests"]["chembl:activity:8"]
        path = Path(ref["path"])
        request = json.loads(path.read_text())
        request["prepared_input"]["source_declarations"]["prepared_state_id"] = "changed"
        path.write_bytes(comparison._canonical(request) + b"\n")
        ref["sha256"] = common.file_sha(path)
    elif change == "bad_execution":
        ref = protocol["requests"]["chembl:activity:8"]
        path = Path(ref["path"])
        request = json.loads(path.read_text())
        request["execution"]["projection_partition"] = "invalid_partition"
        path.write_bytes(comparison._canonical(request) + b"\n")
        ref["sha256"] = common.file_sha(path)
    elif change == "short_cap":
        protocol["max_engine_calls_per_arm"] = 1
    receipt = preflight.preflight_v2(protocol)
    assert receipt["status"] == "blocked"
    assert receipt["protocol"] is None
    assert receipt["protocol_sha256"] is None
    assert blocker in {item["code"] for item in receipt["blockers"]}
    assert receipt["scientifically_validated"] is False
    assert not (tmp_path / "run").exists()
    if change == "missing_request":
        draft = tmp_path / "blocked-draft.json"
        draft.write_bytes(comparison._canonical(protocol) + b"\n")
        output = tmp_path / "must-not-exist.json"
        assert native_cli.main(["preflight-v2", "--protocol", str(draft),
                                "--output-protocol", str(output)]) == 2
        assert not output.exists()


def test_native_v2_resealed_alternate_pose_report_is_rejected(bounded_source, tmp_path):
    protocol, request, candidate = _linked_protocol(bounded_source, tmp_path)
    root = tmp_path / "linked-run"
    result = comparison.run(protocol, root)
    assert result["arms"]["engine"]["rows"][0]["status"] == "evaluated"
    alternate = copy.deepcopy(request)
    alternate["poses"][0]["translation_angstrom"][0] += 0.5
    report = comparison._json(comparison._canonical(evaluate_rigid_pose_request(alternate)))
    assert comparison.check_report(report)["status"] == "passed"
    report_path = root / "engine" / f"{comparison._sha(candidate)}.poses.json"
    report_path.write_bytes(comparison._canonical(report) + b"\n")
    row_path = root / "engine" / f"{comparison._sha(candidate)}.row.json"
    wrapped = json.loads(row_path.read_text())
    wrapped["payload"].update(
        score=min(row["result"]["quantities"]["cross_total_kcal_per_mol"]
                  for row in report["rows"]),
        pose_report=comparison._entry(
            f"engine/{comparison._sha(candidate)}.poses.json", report_path.read_bytes()),
        pose_denominator=report["denominator"],
        numeric_denominator=comparison.check_report(report)["denominator"],
    )
    wrapped["sha256"] = comparison._sha(wrapped["payload"])
    row_path.write_bytes(comparison._canonical(wrapped) + b"\n")
    result_path = root / "comparison.json"
    resealed = json.loads(result_path.read_text())
    resealed["arms"]["engine"]["rows"][0] = wrapped["payload"]
    result_path.write_bytes(comparison._canonical(resealed) + b"\n")
    assert comparison.verify_run(protocol, root)["reason"] == (
        "installed_pose_report_request_mismatch"
    )
    with pytest.raises(ValueError, match="installed_pose_report_request_mismatch"):
        comparison.run(protocol, root, resume=True)


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

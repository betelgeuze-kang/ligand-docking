"""Fully synthetic native-source/registered-D3 integration without admission mocks.

The original synthetic intake supplies every role, source identity and fit
label. Explicit hydrogen completion and zero-charge/zero-LJ parameters below
are test declarations, not preparation or scientific evidence for a real case.
"""
from copy import deepcopy
from dataclasses import replace
import hashlib
from itertools import combinations
import json
import math
from pathlib import Path
import platform
import shutil
import xml.etree.ElementTree as ET

import pytest
from rdkit import Chem
import torch

from betelgeuze_engine_v2.docking import DockingBudget
from betelgeuze_engine_v2.docking.scorer_v1 import ChemistryPoseScorerV1
from betelgeuze_engine_v2.molecular import (
    AllAtomSystem, Atom, Bond, Chain, Residue, StructureProvenance,
    canonical_system_sha256, canonical_topology_sha256,
)
from betelgeuze_engine_v2.molecular.serialization import (
    all_atom_system_from_canonical_json, canonical_system_json_bytes,
)
from betelgeuze_engine_v2.physics.reference_parameters import (
    AtomNonbondedParameter, HarmonicAngleParameter, HarmonicBondParameter,
    PeriodicTorsionParameter, ReferenceForceFieldParameters,
)
from betelgeuze_product import installed_synthetic_comparison as comparison
from betelgeuze_product import installed_native_v4_comparison as native_cli
from betelgeuze_product import installed_native_v4_protocol_preflight as preflight
from betelgeuze_product import installed_native_v4_registered_binding as binding
from betelgeuze_product import installed_native_v4_source as source_verifier
from betelgeuze_product.cpu_refinement.refinement_comparison import RefinementComparisonConfig
from betelgeuze_product.cpu_refinement.reference_minimization_v1_1 import ReferenceMinimizationConfig
from betelgeuze_product.cpu_refinement_v1_2 import registered_policy_adapter as adapter
from betelgeuze_product.cpu_refinement_v1_2.evaluation import ExtendedEvaluator
from betelgeuze_product.cpu_refinement_v1_2.fixed_receptor import (
    FIXED_REPORT_SCHEMA, FixedReceptorEnvironment,
)
from betelgeuze_product.cpu_refinement_v1_2.minimization import SolverConfig
from betelgeuze_product.cpu_refinement_v1_2.refinement import ExtendedRefiner
from betelgeuze_product.cpu_refinement_v1_2.openmm_periodic_extension import OpenMMPeriodicParameters
from betelgeuze_product.cpu_refinement_v1_2.provenance import digest
from betelgeuze_product.cpu_refinement_v1_2.scoring_profile import REGISTERED_REQUEST_SCHEMA
from betelgeuze_product.cpu_refinement_v1_2.selection import SelectionConfig
from tests.unit.test_cpu_fixed_receptor import environment
from tests.unit.test_installed_native_v4_comparison import _two_linked_protocol
from tests.unit.test_public_chembl_receptor_intake import ref as source_ref
from tools.product import public_assay_dataset as common
from tools.product import public_chembl_receptor_intake as checkout_intake


def _write(path, raw):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)
    return {"path": str(path.resolve()), "sha256": hashlib.sha256(raw).hexdigest()}


def _document(path, value):
    return _write(path, comparison._canonical(value) + b"\n")


def _system(mol, *, name, source_sha256, partial_charge=0.0,
            operations=("synthetic_explicit_hydrogen_completion",)):
    Chem.AssignStereochemistry(mol, cleanIt=True, force=True)
    atoms = tuple(Atom(
        index=atom.GetIdx(), name=f"{atom.GetSymbol()}{atom.GetIdx()}",
        element=atom.GetSymbol(), atomic_number=atom.GetAtomicNum(), residue_index=0,
        formal_charge=atom.GetFormalCharge(), partial_charge_e=(partial_charge if atom.GetIdx() == 0 else 0.0),
        isotope_mass_number=atom.GetIsotope() or None, mass_da=atom.GetMass(),
        aromatic=atom.GetIsAromatic(),
        stereo=atom.GetProp("_CIPCode") if atom.HasProp("_CIPCode") else "unspecified",
    ) for atom in mol.GetAtoms())
    edges = sorted((min(b.GetBeginAtomIdx(), b.GetEndAtomIdx()),
                    max(b.GetBeginAtomIdx(), b.GetEndAtomIdx()), b) for b in mol.GetBonds())
    bonds = tuple(Bond(index, first, second, bond.GetBondTypeAsDouble(),
                       aromatic=bond.GetIsAromatic(),
                       stereo=str(bond.GetStereo()).replace("STEREO", ""))
                  for index, (first, second, bond) in enumerate(edges))
    coordinates = torch.tensor([mol.GetConformer().GetPositions().tolist()], dtype=torch.float64)
    return AllAtomSystem(
        name, atoms, bonds,
        (Residue(0, "SYN", 0, 1, tuple(range(len(atoms))), entity_type="non_polymer", hetero=True),),
        (Chain(0, "A", (0,)),), coordinates,
        StructureProvenance(source_format="synthetic", source_id=name,
                            source_sha256=source_sha256, parser_name="synthetic-explicit-graph",
                            parser_version="1", operations=operations),
    )


def _request(directory, rigid, *, partial_charge=0.0):
    """Keep the toy SDF heavy coordinates and explicitly complete its graph."""
    directory.mkdir(parents=True, exist_ok=True)
    prepared = rigid["prepared_input"]
    sdf = Path(prepared["ligand_sdf"]["path"]).read_text()
    mol = Chem.MolFromMolBlock(sdf.split("M  END", 1)[0] + "M  END\n", removeHs=False)
    assert mol is not None and mol.GetNumConformers() == 1
    mol = Chem.AddHs(mol, addCoords=True)
    ligand = _system(mol, name="synthetic-ligand", source_sha256=prepared["ligand_sdf"]["sha256"],
                     partial_charge=partial_charge)
    methane = Chem.AddHs(Chem.MolFromSmiles("C"))
    conformer = Chem.Conformer(methane.GetNumAtoms())
    conformer.Set3D(True)
    for index, xyz in enumerate(((0., 0., 0.), (.63, .63, .63),
                                 (.63, -.63, -.63), (-.63, .63, -.63), (-.63, -.63, .63))):
        # A declared synthetic receptor translation separates its explicit H
        # atoms from both toy ligands without changing any admission threshold.
        conformer.SetAtomPosition(index, (xyz[0] - 4., xyz[1], xyz[2]))
    methane.AddConformer(conformer)
    receptor = _system(methane, name="synthetic-receptor",
                       source_sha256=prepared["protein_pdb"]["sha256"],
                       operations=("synthetic_explicit_hydrogen_completion",
                                   "synthetic_receptor_translation_minus_4_angstrom"))
    atom_parameters = tuple(AtomNonbondedParameter(i, 1., 0., float(atom.partial_charge_e))
                            for i, atom in enumerate(ligand.atoms))
    xyz = ligand.coordinates[0]
    adjacent = {i: set() for i in range(ligand.atom_count)}
    for bond in ligand.bonds:
        adjacent[bond.atom_i].add(bond.atom_j)
        adjacent[bond.atom_j].add(bond.atom_i)
    angles = []
    for center, neighbors in adjacent.items():
        for left, right in combinations(sorted(neighbors), 2):
            first, second = xyz[left] - xyz[center], xyz[right] - xyz[center]
            equilibrium = math.atan2(float(torch.linalg.vector_norm(torch.linalg.cross(first, second))),
                                     float(torch.dot(first, second)))
            angles.append(HarmonicAngleParameter(left, center, right, equilibrium, 1.))
    torsions = set()
    for bond in ligand.bonds:
        for left in adjacent[bond.atom_i] - {bond.atom_j}:
            for right in adjacent[bond.atom_j] - {bond.atom_i}:
                path = (left, bond.atom_i, bond.atom_j, right)
                if len(set(path)) == 4:
                    torsions.add(min(path, tuple(reversed(path))))
    # Every graph-implied term is declared. The synthetic initial state is at
    # bond/angle equilibrium and has explicitly zero torsional amplitudes;
    # applicability coverage and the real force evaluator remain active.
    base = ReferenceForceFieldParameters(
        "synthetic-zero-nonbonded", "1", canonical_topology_sha256(ligand), atom_parameters,
        bonds=tuple(HarmonicBondParameter(b.atom_i, b.atom_j,
                    float(torch.linalg.vector_norm(xyz[b.atom_i] - xyz[b.atom_j])), 1.)
                    for b in ligand.bonds),
        angles=tuple(angles),
        torsions=tuple(PeriodicTorsionParameter(*path, 1, 0., 0.) for path in sorted(torsions)),
        excluded_pairs=tuple((i, j) for i in range(ligand.atom_count)
                             for j in range(i + 1, ligand.atom_count)),
        cutoff_angstrom=10., switch_start_angstrom=8.,
    )
    extension = OpenMMPeriodicParameters(base)
    cross = replace(environment(receptor, ligand, base, epsilon=0.).cross,
                    coordinate_frame_id=prepared["source_declarations"]["coordinate_frame_id"])
    refs = {
        "receptor": _write(directory / "receptor.json", canonical_system_json_bytes(receptor)),
        "ligand": _write(directory / "ligand.json", canonical_system_json_bytes(ligand)),
        "parameters": _document(directory / "parameters.json", base.to_dict()),
        "extensions": _document(directory / "extensions.json", extension.to_dict()),
        "cross_parameters": _document(directory / "cross.json", cross.to_dict()),
    }
    request = {
        "schema_id": REGISTERED_REQUEST_SCHEMA, "backend": "python_cpu_reference", **refs,
        "solvation": None,
        "pocket": {"center_angstrom": rigid["evaluation"]["pocket_center_angstrom"],
                   "radius_angstrom": rigid["evaluation"]["pocket_radius_angstrom"],
                   "coordinate_frame_id": cross.coordinate_frame_id,
                   "source_artifact_sha256": refs["receptor"]["sha256"],
                   "method_id": "synthetic-declared-pocket", "method_version": "1"},
        "receptor_margin_angstrom": 2.,
        "budget": DockingBudget(candidate_count=1, top_k=1, max_torsions=0,
                                translation_radius_angstrom=0., max_refinement_steps=1, seed=17).to_dict(),
        "solver": SolverConfig(ReferenceMinimizationConfig(max_iterations=1, max_backtracks=0)).to_dict(),
        "comparison": vars(RefinementComparisonConfig()),
        "selection": SelectionConfig(1).to_dict(),
    }
    xml = ET.Element("System")
    particles = ET.SubElement(xml, "Particles")
    force = ET.SubElement(ET.SubElement(xml, "Forces"), "Force", type="NonbondedForce")
    charge_particles = ET.SubElement(force, "Particles")
    for atom in ligand.atoms:
        ET.SubElement(particles, "Particle", mass=str(atom.mass_da))
        ET.SubElement(charge_particles, "Particle", q=f"{atom.partial_charge_e:.6f}", sig="0.100000", eps="0.000000")
    xml_ref = _write(directory / "declared-charges.xml", ET.tostring(xml))
    charge_origin = _document(directory / "charge-origin.json", {
        "schema_version": "native_v4_registered_openmm_charge_origin_v1",
        "openmm_system": xml_ref, "ligand_source_sha256": refs["ligand"]["sha256"],
        "ligand_system_sha256": canonical_system_sha256(ligand),
        "atom_mapping": [{"particle_index": i, "ligand_atom_index": i,
                          "atom_name": atom.name, "element": atom.element,
                          "atomic_number": atom.atomic_number,
                          "isotope_mass_number": atom.isotope_mass_number,
                          "formal_charge": atom.formal_charge}
                         for i, atom in enumerate(ligand.atoms)],
    })
    return request, charge_origin


def _protocol(directory, *, second_method=False, second_frame=False, second_charge=0.0,
              second_smiles="CC1CCOCC1"):
    directory.mkdir(parents=True, exist_ok=True)
    protocol = _two_linked_protocol(directory, second_method=second_method,
                                    second_frame=second_frame, second_smiles=second_smiles)
    rows = [row for row in source_verifier._verified_intake(protocol["source"])[2]
            if row["assigned_role"] == "development_test"]
    root = directory / "source"
    metadata_path = root / "metadata.jsonl"
    entries = [json.loads(line) for line in metadata_path.read_text().splitlines()]
    for row in rows:
        rid = row["record_id"]
        rigid = comparison._bound_json(protocol["requests"][rid])
        request, charge = _request(directory / (rid.replace(":", "-") + "-registered"), rigid,
                                   partial_charge=second_charge if row["activity_id"] == 8 else 0.0)
        origin = binding.derive_observation(row, request, charge_origin=charge)
        entry = next(item for item in entries if item["activity_id"] == row["activity_id"])
        entry["prepared_state_origin"] = source_ref(root, origin, rid.replace(":", "-") + "-registered-origin.json")
        protocol["requests"][rid] = _document(root / (rid.replace(":", "-") + "-registered-request.json"), request)
    metadata_path.write_text("".join(json.dumps(entry) + "\n" for entry in entries))
    manifest_path = root / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["metadata_records"]["sha256"] = common.file_sha(metadata_path)
    manifest_path.write_text(json.dumps(manifest))
    intake = root / "registered-intake"
    checkout_intake.build(str(manifest_path), common.file_sha(manifest_path), intake)
    protocol["source"] = {**protocol["source"], "input_dir": str(intake),
                          "summary_sha256": common.file_sha(intake / "summary.json")}
    protocol["schema_version"] = comparison.NATIVE_PROTOCOL_V3
    return protocol


def _forbid_execution(monkeypatch):
    """Allow constructor arithmetic; forbid workers and optimizer/scoring calls."""
    # platform.platform() can lazily spawn uname on Python 3.10. Resolve this
    # read-only runtime metadata before guarding against worker subprocesses.
    platform.platform()
    def forbidden(*args, **kwargs):
        pytest.fail("admission/reuse unexpectedly executed a worker or molecular evaluator")
    monkeypatch.setattr(comparison.subprocess, "Popen", forbidden)
    monkeypatch.setattr(adapter, "evaluate", forbidden)
    monkeypatch.setattr(ExtendedEvaluator, "evaluate", forbidden)
    monkeypatch.setattr(FixedReceptorEnvironment, "evaluate_cross", forbidden)
    monkeypatch.setattr(ExtendedRefiner, "refine", forbidden)
    for method in ("score", "score_terms", "score_batch", "score_terms_batch"):
        monkeypatch.setattr(ChemistryPoseScorerV1, method, forbidden)


def test_real_source_rederivation_preflight_freeze_and_cli(tmp_path, monkeypatch, capsys):
    protocol = _protocol(tmp_path)
    _forbid_execution(monkeypatch)
    readiness = preflight.preflight_v3(protocol)
    assert readiness["status"] == "ready", readiness["blockers"]
    assert readiness["assigned_role_counts"] == {"fit": 6, "calibration": 0, "development_test": 2}
    assert readiness["candidate_count"] == readiness["distinct_Ki_chemical_identity_count"] == 2
    assert readiness["evaluation_labels_read"] == 0
    assert not readiness["numeric_validation_completed"]
    assert not readiness["scientifically_validated"]
    assert not readiness["training_admitted"]
    frozen = comparison.freeze(protocol)
    assert frozen["schema_version"] == comparison.NATIVE_FROZEN_V3
    assert set(frozen["prepared_bindings"]) == set(protocol["requests"])
    assert all(item["candidate_prepared_identity_bound"] for item in frozen["prepared_bindings"].values())
    assert not frozen["same_prepared_assay_state_verified"]
    draft = _document(tmp_path / "draft.json", protocol)
    output = tmp_path / "admitted-protocol.json"
    assert native_cli.main(["preflight-v3", "--protocol", draft["path"], "--output-protocol", str(output)]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "ready"
    assert comparison._read_protocol(output) == protocol


@pytest.mark.parametrize("change", ["swap", "reseal", "denominator", "cap", "missing"])
def test_direct_freeze_cannot_bypass_registered_admission(tmp_path, monkeypatch, change):
    protocol = _protocol(tmp_path)
    ids = list(protocol["requests"])
    if change == "swap":
        protocol["requests"][ids[0]], protocol["requests"][ids[1]] = protocol["requests"][ids[1]], protocol["requests"][ids[0]]
    elif change == "reseal":
        request = comparison._bound_json(protocol["requests"][ids[0]])
        request["comparison"]["require_convergence_for_selection"] = False
        protocol["requests"][ids[0]] = _document(tmp_path / "resealed.json", request)
    elif change == "denominator":
        protocol["requests"].pop(ids[0])
    elif change == "cap":
        protocol["max_engine_calls_per_arm"] = 1
    else:
        protocol["requests"][ids[0]] = None
    _forbid_execution(monkeypatch)
    receipt = preflight.preflight_v3(protocol)
    assert receipt["status"] == "blocked"
    if change in {"cap", "denominator"}:
        assert receipt["candidate_count"] == receipt["distinct_Ki_chemical_identity_count"] == 2
        assert receipt["assigned_role_counts"] == {"fit": 6, "calibration": 0, "development_test": 2}
    with pytest.raises(ValueError):
        comparison.freeze(protocol)
    with pytest.raises(ValueError):
        comparison.run(protocol, tmp_path / "must-not-run")
    assert not (tmp_path / "must-not-run").exists()


@pytest.mark.parametrize("change", ["method", "frame", "charge"])
def test_individually_bound_but_incompatible_candidates_are_blocked(tmp_path, monkeypatch, change):
    protocol = _protocol(tmp_path, second_method=change == "method", second_frame=change == "frame",
                         second_charge=.25 if change == "charge" else 0.0)
    _forbid_execution(monkeypatch)
    receipt = preflight.preflight_v3(protocol)
    assert receipt["status"] == "blocked"
    assert receipt["candidate_count"] == receipt["distinct_Ki_chemical_identity_count"] == 2
    assert receipt["assigned_role_counts"] == {"fit": 6, "calibration": 0, "development_test": 2}
    blocker = ("prepared_ligand_net_charge_rank_ineligible" if change == "charge"
               else "method_or_registered_receptor_pocket_frame_mismatch")
    assert blocker in {item["code"] for item in receipt["blockers"]}
    with pytest.raises(ValueError):
        comparison.freeze(protocol)


def test_failed_source_verification_keeps_candidate_denominators_unknown(tmp_path, monkeypatch):
    protocol = _protocol(tmp_path)
    protocol["source"]["summary_sha256"] = "0" * 64
    _forbid_execution(monkeypatch)
    receipt = preflight.preflight_v3(protocol)
    assert receipt["status"] == "blocked"
    assert receipt["candidate_count"] is None
    assert receipt["distinct_Ki_chemical_identity_count"] is None
    assert receipt["assigned_role_counts"] is None


def test_geometry_stereo_cannot_be_replaced_by_resealed_declared_identity(tmp_path, monkeypatch):
    protocol = _protocol(tmp_path, second_smiles="C[C@H]1CCOC1")
    rid = "chembl:activity:8"
    request = comparison._bound_json(protocol["requests"][rid])
    origin_path = Path(request["ligand"]["path"]).parent / "charge-origin.json"
    charge = json.loads(origin_path.read_bytes())
    ligand = all_atom_system_from_canonical_json(Path(request["ligand"]["path"]).read_bytes())
    xyz = ligand.coordinates.clone()
    xyz[..., 0] *= -1.
    mirrored = ligand.with_coordinates(xyz, operation="synthetic_reflection")
    request["ligand"] = _write(tmp_path / "mirrored.json", canonical_system_json_bytes(mirrored))
    charge.update(ligand_source_sha256=request["ligand"]["sha256"],
                  ligand_system_sha256=canonical_system_sha256(mirrored))
    charge_ref = _document(tmp_path / "mirrored-charge-origin.json", charge)
    row = next(row for row in source_verifier._verified_intake(protocol["source"])[2]
               if row["record_id"] == rid)
    protocol["requests"][rid] = _document(tmp_path / "mirrored-request.json", request)
    _forbid_execution(monkeypatch)
    # Rebind the byte/charge declarations, so a stale digest cannot be the
    # reason that a changed 3D stereoisomer fails this identity check.
    with pytest.raises(ValueError, match="stereo|chemical_identity|chirality"):
        binding.derive_observation(row, request, charge_origin=charge_ref)
    receipt = preflight.preflight_v3(protocol)
    assert receipt["status"] == "blocked"
    with pytest.raises(ValueError):
        comparison.freeze(protocol)


@pytest.fixture(scope="module")
def completed(tmp_path_factory):
    root = tmp_path_factory.mktemp("native-registered-integration")
    protocol = _protocol(root / "input")
    run_dir = root / "run"
    result = comparison.run(protocol, run_dir)
    return protocol, run_dir, result


def test_four_arm_execution_preserves_identity_denominators_and_work(completed):
    protocol, run_dir, result = completed
    assert result["schema_version"] == comparison.NATIVE_RESULT_V3
    assert result["evaluation_labels_read"] == 0
    assert not result["scientifically_validated"]
    for name, arm in result["arms"].items():
        assert arm["completion"]["status"] == "complete"
        assert arm["denominator"] == {"requested": 2, "evaluated": 2}
        assert {row["record_id"] for row in arm["rows"]} == set(protocol["requests"])
        assert arm["worker_complete"]["engine_calls"] == (0 if name == "similarity" else 2)
        if name != "similarity":
            assert arm["score_quantity"] == adapter.SCORE_QUANTITY
            for row in arm["rows"]:
                summary = row["registered_summary"]
                assert row["score"] == summary["score"]
                assert summary["work"]["actual_force_evaluation_calls"] == 1
                assert summary["work"]["failed_force_evaluation_calls"] == 0
                assert summary["work"]["score_evaluation_calls"] == 2
                assert summary["work"]["force_evaluations_reserved"] == 2
                assert not summary["candidate_source_admission_verified"]
            counters = arm["registered_work"]["recorded_call_counters"]
            assert counters["actual_force_evaluation_calls"] == 2
            assert counters["score_evaluation_calls"] == 4
    assert comparison.verify_run(protocol, run_dir)["status"] == "verified"


def test_completed_resume_never_reexecutes_optimizer_or_scores(completed, monkeypatch):
    protocol, run_dir, result = completed
    _forbid_execution(monkeypatch)
    assert comparison.verify_run(protocol, run_dir)["status"] == "verified"
    assert comparison.run(protocol, run_dir, resume=True) == result


@pytest.mark.parametrize("change", ["legacy_report", "row_summary"])
def test_resealed_report_or_summary_tampering_is_detected(completed, tmp_path, change):
    protocol, original, result = completed
    run_dir = tmp_path / "copied-run"
    shutil.copytree(original, run_dir)
    row = result["arms"]["engine"]["rows"][0]
    row_path = run_dir / "engine" / (comparison._sha(row["record_id"]) + ".row.json")
    wrapped = json.loads(row_path.read_bytes())
    if change == "legacy_report":
        ref = wrapped["payload"]["pose_report"]
        path = run_dir / ref["path"]
        report = json.loads(path.read_bytes())
        report["comparison"]["schema_id"] = FIXED_REPORT_SCHEMA
        report["comparison"].pop("proposal_policy")
        report["comparison"].pop("scorer")
        inner = report["comparison"]
        inner["report_sha256"] = digest({k: v for k, v in inner.items() if k != "report_sha256"})
        raw = comparison._canonical(report) + b"\n"
        path.write_bytes(raw)
        wrapped["payload"]["pose_report"] = comparison._entry(ref["path"], raw)
    else:
        wrapped["payload"]["registered_summary"]["work"]["actual_force_evaluation_calls"] += 1
    wrapped["sha256"] = comparison._sha(wrapped["payload"])
    row_path.write_bytes(comparison._canonical(wrapped) + b"\n")
    verification = comparison.verify_run(protocol, run_dir)
    assert verification["status"] != "verified"
    assert verification["exit_code"] != 0


@pytest.mark.parametrize("kind", ["failed_without_report", "similarity_summary", "legacy_field"])
def test_unbacked_or_wrong_backend_work_cannot_enter_a_committed_row(completed, tmp_path, kind):
    _, original, result = completed
    run_dir = tmp_path / "copied-run"
    shutil.copytree(original, run_dir)
    arm = "similarity" if kind == "similarity_summary" else "engine"
    row = result["arms"][arm]["rows"][0]
    row_path = run_dir / arm / (comparison._sha(row["record_id"]) + ".row.json")
    wrapped = json.loads(row_path.read_bytes())
    payload = wrapped["payload"]
    if kind == "failed_without_report":
        ref = payload.pop("pose_report")
        (run_dir / ref["path"]).unlink()
        payload.update(status="failed", score=None, reason="RuntimeError:synthetic unreturned calculation")
        payload["registered_summary"]["work"]["actual_force_evaluation_calls"] = 999
    elif kind == "similarity_summary":
        payload["registered_summary"] = deepcopy(result["arms"]["engine"]["rows"][0]["registered_summary"])
    else:
        payload["numeric_denominator"] = {"requested": 1, "passed": 1, "failed": 0, "not_compared": 0}
    wrapped["sha256"] = comparison._sha(payload)
    row_path.write_bytes(comparison._canonical(wrapped) + b"\n")
    frozen, frozen_binding = comparison._envelope(run_dir)
    # Exercise row validation itself; an unchanged top-level comparison.json
    # must not be the only reason that forged work is rejected.
    with pytest.raises(ValueError):
        comparison._summary(run_dir, arm, frozen, frozen_binding)

"""Synthetic full-stage setup profile; never evaluates force, score or optimizer."""

from __future__ import annotations
from collections import defaultdict
from contextlib import ExitStack
from copy import deepcopy
from dataclasses import replace
import argparse
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import platform
import subprocess
import sys
import time
from unittest.mock import patch
import xml.etree.ElementTree as ET

import numpy
import openmm
import pytest
from rdkit import Chem
import rdkit
import torch

from betelgeuze_product import installed_paper_development_comparison as candidate
from betelgeuze_product.cpu_refinement_v1_2.chemical_features import ExplicitGraphScorer
from betelgeuze_product.cpu_refinement_v1_2 import (
    evaluation,
    fixed_receptor,
    minimization as old_minimization,
)
from betelgeuze_product.cpu_refinement_v1_2.openmm_periodic_extension import (
    OpenMMPeriodicParameters,
)
from betelgeuze_product.cpu_refinement_v1_3 import minimization, workflow
from betelgeuze_product.native_v4_chemical_identity import chemical_identity
from betelgeuze_engine_v2.molecular import (
    AllAtomSystem,
    Atom,
    Bond,
    Chain,
    Residue,
    StructureProvenance,
)
from betelgeuze_engine_v2.molecular import serialization as serial
from betelgeuze_engine_v2.physics.reference_parameters import (
    AtomNonbondedParameter,
    HarmonicBondParameter,
    ReferenceForceFieldParameters,
)
from tests.unit.test_installed_paper_development_comparison import _protocol, _write
from tests.unit.test_cpu_fixed_receptor import environment


def load_baseline(path):
    spec = importlib.util.spec_from_file_location(
        "betelgeuze_product._paper_setup_baseline", path
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def make_system(name, molecule, xyz):
    atoms = tuple(
        Atom(
            i,
            a.GetSymbol() + str(i),
            a.GetSymbol(),
            a.GetAtomicNum(),
            0,
            formal_charge=a.GetFormalCharge(),
            partial_charge_e=0.0,
        )
        for i, a in enumerate(molecule.GetAtoms())
    )
    bonds = tuple(
        Bond(
            i,
            min(b.GetBeginAtomIdx(), b.GetEndAtomIdx()),
            max(b.GetBeginAtomIdx(), b.GetEndAtomIdx()),
            b.GetBondTypeAsDouble(),
        )
        for i, b in enumerate(molecule.GetBonds())
    )
    return AllAtomSystem(
        name,
        atoms,
        bonds,
        (
            Residue(
                0,
                "LIG",
                0,
                1,
                tuple(range(len(atoms))),
                entity_type="non_polymer",
                hetero=True,
            ),
        ),
        (Chain(0, "A", (0,)),),
        torch.tensor([xyz], dtype=torch.float64),
        StructureProvenance("synthetic", name, "a" * 64, "analytic-profile", "1"),
    )


def ligand_system(name, smiles):
    mol = Chem.AddHs(Chem.MolFromSmiles(smiles))
    heavy = [a.GetIdx() for a in mol.GetAtoms() if a.GetAtomicNum() != 1]
    xyz = [[0.0, 0.0, 0.0] for _ in range(mol.GetNumAtoms())]
    for pos, index in enumerate(heavy):
        xyz[index] = [1.5 * (pos - (len(heavy) - 1) / 2), 0.2 * (pos % 2), 0.0]
        hs = [
            a.GetIdx()
            for a in mol.GetAtomWithIdx(index).GetNeighbors()
            if a.GetAtomicNum() == 1
        ]
        for j, h in enumerate(hs):
            angle = 2 * math.pi * j / len(hs)
            xyz[h] = [
                xyz[index][0],
                xyz[index][1] + 0.9 * math.cos(angle),
                0.9 * math.sin(angle),
            ]
    return make_system(name, mol, xyz)


def receptor_system():
    # 323 inner waters + one inner methane = 974 subset atoms. 1134 outer
    # waters bring the complete receptor to 4376 atoms. These are synthetic
    # duplicated coordinates for setup scale only, never physical observations.
    atoms, bonds, residues, xyz = [], [], [], []
    theta = math.radians(104.5)
    parts = [
        (
            Chem.AddHs(Chem.MolFromSmiles("O")),
            [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [math.cos(theta), math.sin(theta), 0.0]],
            [0.0, 9.0, 0.0] if i < 323 else [40.0, 40.0, 40.0],
        )
        for i in range(1457)
    ]
    parts.append(
        (
            Chem.AddHs(Chem.MolFromSmiles("C")),
            [
                [0.0, 0.0, 0.0],
                [1.0, 0.0, 0.0],
                [-1.0, 0.0, 0.0],
                [0.0, 0.0, 1.0],
                [0.0, 0.0, -1.0],
            ],
            [0.0, 9.0, 0.0],
        )
    )
    for residue, (mol, local, shift) in enumerate(parts):
        offset = len(atoms)
        for a in mol.GetAtoms():
            i = len(atoms)
            atoms.append(
                Atom(
                    i,
                    a.GetSymbol() + str(i),
                    a.GetSymbol(),
                    a.GetAtomicNum(),
                    residue,
                    partial_charge_e=0.0,
                )
            )
        for b in mol.GetBonds():
            left, right = sorted(
                (offset + b.GetBeginAtomIdx(), offset + b.GetEndAtomIdx())
            )
            bonds.append(Bond(len(bonds), left, right))
        residues.append(
            Residue(
                residue,
                "HOH" if mol.GetNumAtoms() == 3 else "MET",
                0,
                residue + 1,
                tuple(range(offset, len(atoms))),
                entity_type="non_polymer",
                hetero=True,
            )
        )
        xyz.extend([[v + s for v, s in zip(row, shift)] for row in local])
    return AllAtomSystem(
        "synthetic-profile-receptor",
        tuple(atoms),
        tuple(bonds),
        tuple(residues),
        (Chain(0, "A", tuple(range(len(residues)))),),
        torch.tensor([xyz], dtype=torch.float64),
        StructureProvenance(
            "synthetic", "setup-profile-receptor", "a" * 64, "analytic-profile", "1"
        ),
    )


def representative_protocol(directory, baseline):
    protocol = _protocol(directory)
    receptor = receptor_system()
    receptor_ref = _write(
        directory / "representative-receptor.json",
        serial.canonical_system_json_bytes(receptor),
    )
    for entry, smiles in zip(
        protocol["candidates"], ("CCCCCCCCCCCCO", "CCCCCCCCCCCCCN")
    ):
        child = Path(entry["source"]["path"]).parent
        ligand = ligand_system(child.name, smiles)
        request = json.loads(Path(entry["original_request"]["path"]).read_bytes())
        old_evidence = json.loads(Path(entry["prepared_evidence"]["path"]).read_bytes())
        request["receptor"] = receptor_ref
        request["ligand"] = _write(
            child / "representative-ligand.json",
            serial.canonical_system_json_bytes(ligand),
        )
        base = ReferenceForceFieldParameters(
            "synthetic-profile",
            "1",
            serial.canonical_topology_sha256(ligand),
            tuple(
                AtomNonbondedParameter(i, 1.0, 0.01, 0.0)
                for i in range(ligand.atom_count)
            ),
            bonds=tuple(
                HarmonicBondParameter(
                    b.atom_i,
                    b.atom_j,
                    float(
                        torch.linalg.vector_norm(
                            ligand.coordinates[0, b.atom_i]
                            - ligand.coordinates[0, b.atom_j]
                        )
                    ),
                    50.0,
                )
                for b in ligand.bonds
            ),
            excluded_pairs=tuple((b.atom_i, b.atom_j) for b in ligand.bonds),
            cutoff_angstrom=6.0,
            switch_start_angstrom=5.0,
        )
        cross = replace(
            environment(receptor, ligand, base, block=64, epsilon=0.01).cross,
            coordinate_frame_id=request["pocket"]["coordinate_frame_id"],
        )
        for key, value in (
            ("parameters", base.to_dict()),
            ("extensions", OpenMMPeriodicParameters(base).to_dict()),
            ("cross_parameters", cross.to_dict()),
        ):
            request[key] = _write(child / ("representative-" + key + ".json"), value)
        entry["original_request"] = _write(
            child / "representative-request.json", request
        )
        source = json.loads(Path(entry["source"]["path"]).read_bytes())
        source["chemical_identity"] = chemical_identity(smiles)
        identity = json.loads(
            Path(source["evidence"]["identity_statement"]["path"]).read_bytes()
        )
        identity["chemical_identity"] = deepcopy(source["chemical_identity"])
        source["evidence"]["identity_statement"] = _write(
            child / "representative-identity.json", identity
        )
        entry["source"] = _write(child / "representative-source.json", source)
        xml = ET.Element("System")
        particles = ET.SubElement(xml, "Particles")
        values = ET.SubElement(
            ET.SubElement(ET.SubElement(xml, "Forces"), "Force", type="NonbondedForce"),
            "Particles",
        )
        for _ in ligand.atoms:
            ET.SubElement(particles, "Particle", mass="1")
            ET.SubElement(values, "Particle", q="0.000000", sig="1", eps="0")
        xml_ref = _write(child / "representative-charges.xml", ET.tostring(xml))
        charge = {
            "schema_version": candidate.structural.CHARGE_ORIGIN_SCHEMA,
            "openmm_system": xml_ref,
            "ligand_source_sha256": request["ligand"]["sha256"],
            "ligand_system_sha256": serial.canonical_system_sha256(ligand),
            "atom_mapping": [
                {
                    "particle_index": i,
                    "ligand_atom_index": i,
                    "atom_name": a.name,
                    "element": a.element,
                    "atomic_number": a.atomic_number,
                    "isotope_mass_number": a.isotope_mass_number,
                    "formal_charge": a.formal_charge,
                }
                for i, a in enumerate(ligand.atoms)
            ],
        }
        charge_ref = _write(child / "representative-charge-origin.json", charge)
        evidence = baseline.derive_prepared_evidence(
            entry["source"],
            entry["original_request"],
            charge_ref,
            initial_pose_protocol=old_evidence["initial_pose_protocol"],
            declared_model_evidence=old_evidence["declared_model_evidence"],
        )
        entry["prepared_evidence"] = _write(
            child / "representative-prepared-evidence.json", evidence
        )
    return protocol


def instrument(module, stack, counters):
    targets = {
        "canonical.encode": serial.canonical_json_bytes,
        "canonical.decode": serial.all_atom_system_from_canonical_json,
        "canonical.system_hash": serial.canonical_system_sha256,
        "canonical.payload_hash": serial.sha256_canonical,
        "source.validate": module._source,
        "preparation": module._preparation,
        "source.verify_bytes": module._raw,
        "old_binding": candidate.original_adapter._admit,
        "cartesian_binding": candidate.adapter.input_binding,
        "canonical.json_parse": json.loads,
        "canonical.json_serialize": json.dumps,
    }
    for label, actual in targets.items():

        def wrapped(*args, _actual=actual, _label=label, **kwargs):
            row = counters[_label]
            row["calls"] += 1
            start, cpu = time.perf_counter_ns(), time.process_time_ns()
            try:
                value = _actual(*args, **kwargs)
                row["completed"] += 1
                if _label == "canonical.decode":
                    row["atoms_decoded"] += value.atom_count
                if _label == "source.verify_bytes":
                    row["bytes_verified"] += len(value)
                return value
            except BaseException:
                row["failed"] += 1
                raise
            finally:
                row["wall_ns"] += time.perf_counter_ns() - start
                row["cpu_ns"] += time.process_time_ns() - cpu

        # Patch all already-imported aliases, retaining every implementation.
        for obj in tuple(sys.modules.values()):
            if obj is None:
                continue
            name = getattr(obj, "__name__", "")
            if not (name.startswith("betelgeuze") or obj is json):
                continue
            for key, value in list(vars(obj).items()):
                if value is actual:
                    stack.enter_context(patch.object(obj, key, wrapped))
    actual = ExplicitGraphScorer.__init__

    def constructor(*args, **kwargs):
        row = counters["scorer.construct"]
        row["calls"] += 1
        start, cpu = time.perf_counter_ns(), time.process_time_ns()
        try:
            actual(*args, **kwargs)
            row["completed"] += 1
        except BaseException:
            row["failed"] += 1
            raise
        finally:
            row["wall_ns"] += time.perf_counter_ns() - start
            row["cpu_ns"] += time.process_time_ns() - cpu

    stack.enter_context(patch.object(ExplicitGraphScorer, "__init__", constructor))


def forbidden(stack, calls):
    def fail(*args, **kwargs):
        calls.append("forbidden_molecular_call")
        raise AssertionError(
            "synthetic setup profile attempted force/score/optimizer/OpenMM"
        )

    for obj, name in (
        (ExplicitGraphScorer, "score_terms"),
        (workflow, "evaluate"),
        (minimization, "minimize"),
        (old_minimization, "minimize_extended"),
        (fixed_receptor.FixedReceptorEvaluator, "evaluate"),
        (fixed_receptor.FixedReceptorEnvironment, "evaluate_cross"),
        (evaluation.ExtendedEvaluator, "evaluate"),
        (openmm, "Context"),
    ):
        stack.enter_context(patch.object(obj, name, fail))


def attempt(module, protocol, operation, profiled):
    counters = defaultdict(lambda: defaultdict(int))
    calls = []
    with ExitStack() as stack:
        forbidden(stack, calls)
        if profiled:
            instrument(module, stack, counters)
        start, cpu = time.perf_counter_ns(), time.process_time_ns()
        result = getattr(module, operation)(deepcopy(protocol))
        wall_ns, cpu_ns = time.perf_counter_ns() - start, time.process_time_ns() - cpu
    return result, {
        "operation": operation,
        "profiled": profiled,
        "wall_ns": wall_ns,
        "cpu_ns": cpu_ns,
        "components_are_inclusive_do_not_sum": True,
        "components": dict(counters),
        "forbidden_calls": calls,
        "requested": result["requested_candidate_count"],
        "prepared": result["prepared_candidate_count"],
        "failed": result["requested_candidate_count"]
        - result["prepared_candidate_count"],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--baseline-source", type=Path, required=True)
    parser.add_argument("--baseline-only", action="store_true")
    parser.add_argument("--repeats", type=int, default=3)
    args = parser.parse_args()
    args.output.mkdir(exist_ok=False, parents=True)
    baseline = load_baseline(args.baseline_source)
    start = time.perf_counter_ns()
    with ExitStack() as stack:
        calls = []
        forbidden(stack, calls)
        protocol = representative_protocol(args.output / "inputs", baseline)
    generation_ns = time.perf_counter_ns() - start
    (args.output / "protocol.json").write_bytes(candidate._canonical(protocol) + b"\n")
    receipt = {
        "schema_version": "synthetic_paper_setup_profile_v1",
        "synthetic_only": True,
        "system_scale": {
            "receptor_atoms": 4376,
            "subset_atoms": 974,
            "ligand_atoms": [39, 43],
        },
        "generation_wall_ns": generation_ns,
        "raw_attempts": [],
        "semantic_equality": [],
        "environment": {
            "python": sys.executable,
            "version": platform.python_version(),
            "platform": platform.platform(),
            "torch": torch.__version__,
            "torch_path": torch.__file__,
            "torch_threads": torch.get_num_threads(),
            "rdkit": rdkit.__version__,
            "rdkit_path": rdkit.__file__,
            "numpy": numpy.__version__,
            "pytest": pytest.__version__,
            "openmm": openmm.__version__,
            "gpu_execution_performed": False,
        },
        "source_sha256": {
            "baseline": hashlib.sha256(args.baseline_source.read_bytes()).hexdigest(),
            "candidate": hashlib.sha256(
                Path(candidate.__file__).read_bytes()
            ).hexdigest(),
            "profile_script": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        },
        "source_head": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], text=True
        ).strip(),
        "immutable_dependency_sources": candidate.original_adapter.source_manifest(),
        "synthetic_inputs": {
            str(p.relative_to(args.output / "inputs")): hashlib.sha256(
                p.read_bytes()
            ).hexdigest()
            for p in sorted((args.output / "inputs").rglob("*"))
            if p.is_file()
        },
        "boundary": deepcopy(candidate.BOUNDARY),
        "semantic_exclusions": [
            "runtime_sha256",
            "frozen_sha256 derived only from runtime_sha256",
        ],
        "timing_exclusions": [
            "module_import",
            "fixture_generation",
            "output_receipt_serialization",
        ],
        "constructor_reference_arithmetic_included": True,
        "durations_are_inclusive_do_not_sum": True,
    }
    modules = (
        [("baseline", baseline)]
        if args.baseline_only
        else [("baseline", baseline), ("candidate", candidate)]
    )
    expected = {}
    for repeat in range(args.repeats):
        for label, module in modules if repeat % 2 == 0 else list(reversed(modules)):
            for operation in ("freeze", "preflight"):
                for profiled in (False, True):
                    intent = {
                        "variant": label,
                        "repeat": repeat,
                        "operation": operation,
                        "profiled": profiled,
                        "requested": len(protocol["candidates"]),
                        "prepared": None,
                        "failed": None,
                        "status": "started",
                    }
                    receipt["pending_attempt"] = intent
                    (args.output / "profile.json").write_bytes(
                        candidate._canonical(receipt) + b"\n"
                    )
                    try:
                        result, row = attempt(module, protocol, operation, profiled)
                    except BaseException as exc:
                        intent.update(
                            status="interrupted_unknown"
                            if isinstance(exc, KeyboardInterrupt)
                            else "failed",
                            error=type(exc).__name__ + ":" + str(exc),
                            whole_stage_elapsed_ns=None,
                        )
                        receipt["raw_attempts"].append(intent)
                        receipt.pop("pending_attempt", None)
                        (args.output / "profile.json").write_bytes(
                            candidate._canonical(receipt) + b"\n"
                        )
                        raise
                    row.update(variant=label, repeat=repeat)
                    receipt["raw_attempts"].append(row)
                    receipt.pop("pending_attempt", None)
                    semantic = deepcopy(result)
                    semantic.pop("runtime_sha256", None)
                    semantic.pop("frozen_sha256", None)
                    key = operation
                    if key not in expected:
                        expected[key] = semantic
                    receipt["semantic_equality"].append(
                        {
                            "variant": label,
                            "repeat": repeat,
                            "operation": operation,
                            "profiled": profiled,
                            "equal": semantic == expected[key],
                            "semantic_sha256": candidate._sha(semantic),
                        }
                    )
                    print(
                        json.dumps({k: v for k, v in row.items() if k != "components"}),
                        flush=True,
                    )
                    (args.output / "profile.json").write_bytes(
                        candidate._canonical(receipt) + b"\n"
                    )
                    assert row["requested"] == row["prepared"] == 2
                    assert semantic == expected[key]
                    assert (
                        candidate.original_adapter.source_manifest()
                        == receipt["immutable_dependency_sources"]
                    )
                    assert {
                        str(p.relative_to(args.output / "inputs")): hashlib.sha256(
                            p.read_bytes()
                        ).hexdigest()
                        for p in sorted((args.output / "inputs").rglob("*"))
                        if p.is_file()
                    } == receipt["synthetic_inputs"]
                    assert (
                        hashlib.sha256(
                            Path(candidate.__file__).read_bytes()
                        ).hexdigest()
                        == receipt["source_sha256"]["candidate"]
                    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

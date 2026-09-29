"""Bind the prepared PR49 development complex to the native CPU D3 workflow.

This creates a bounded numerical experiment, never an affinity/pose benchmark.
The frozen request is emitted before energy evaluation. Existing files survive.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import time
import xml.etree.ElementTree as ET

from betelgeuze_engine_v2.docking import DockingBudget
from betelgeuze_engine_v2.molecular import canonical_system_sha256, canonical_topology_sha256
from betelgeuze_engine_v2.molecular.serialization import all_atom_system_from_canonical_json
from betelgeuze_engine_v2.physics.reference_parameters import AtomNonbondedParameter
from betelgeuze_product.cpu_refinement.reference_minimization_v1_1 import ReferenceMinimizationConfig
from betelgeuze_product.cpu_refinement.refinement_comparison import RefinementComparisonConfig
from betelgeuze_product.cpu_refinement_v1_2.fixed_receptor import CrossParameters, FixedReceptorEnvironment, FIXED_REQUEST_SCHEMA
from betelgeuze_product.cpu_refinement_v1_2.minimization import SolverConfig
from betelgeuze_product.cpu_refinement_v1_2.selection import SelectionConfig
from tools.product.openmm_d3_translation import convert_openmm_system, TranslationSettings, OpenMMD3TranslationError

BASE = Path('/mnt/193005ba-8531-4d0b-87c2-43c01ee2ce25/ligand_heavy_runs')
RECEPTOR_XML = BASE / 'engine-v2-7xtb-openmm-projection-20260929/openmm-system.xml'
RECEPTOR_XML_SHA = '7c5aeeeafed880dfee5f294fc34b6a0e2ec5a31d9482245b5cab93c10d4d1cc6'
ORIGINAL_XML = BASE / 'engine-v2-5ht6-pr49-pr59-openff-projection-20260929/PR49/openmm-system.xml'


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def ref(path):
    path = path.resolve(strict=True)
    return {'path': str(path), 'sha256': sha(path.read_bytes())}


def write(path, value):
    with path.open('x') as stream:
        json.dump(value, stream, sort_keys=True, indent=2, allow_nan=False)
        stream.write('\n')


def build(prepared, output):
    started = time.perf_counter()
    manifest = json.loads((prepared / 'manifest.v1.json').read_bytes())
    for name, row in manifest['files'].items():
        data = (prepared / name).read_bytes()
        if sha(data) != row['sha256'] or len(data) != row['bytes']:
            raise ValueError('prepared manifest file mismatch: ' + name)
    receptor = all_atom_system_from_canonical_json((prepared / 'receptor-canonical.json').read_bytes())
    ligand = all_atom_system_from_canonical_json((prepared / 'ligand-canonical.json').read_bytes())
    settings = TranslationSettings('PR49_OpenFF221_unconstrained_development_v1', 100., 90., .35)
    translation = convert_openmm_system((prepared / 'ligand-unconstrained-openmm-system.xml').read_bytes(), ligand, settings)
    try:
        convert_openmm_system(ORIGINAL_XML.read_bytes(), ligand, settings)
    except OpenMMD3TranslationError as error:
        if error.code != 'constrained_bond_terms_missing':
            raise
        refusal = {'source': ref(ORIGINAL_XML), 'executed': True, 'error_code': error.code}
    else:
        raise ValueError('original constrained source unexpectedly admitted')
    receptor_xml = RECEPTOR_XML.read_bytes()
    if sha(receptor_xml) != RECEPTOR_XML_SHA:
        raise ValueError('receptor source XML changed')
    root = ET.fromstring(receptor_xml)
    force = [f for f in root.find('Forces') if f.attrib['type'] == 'NonbondedForce']
    if len(force) != 1:
        raise ValueError('exactly one receptor NonbondedForce required')
    particles = list(force[0].find('Particles'))
    if len(particles) != receptor.atom_count:
        raise ValueError('receptor XML particle coverage mismatch')
    rows = tuple(AtomNonbondedParameter(i, float(p.attrib['sig'])*10.,
        float(p.attrib['eps'])/4.184, float(p.attrib['q'])) for i, p in enumerate(particles))
    registration = json.loads((prepared / 'registration.json').read_bytes())
    frame = '7XTB_original_cartesian_angstrom_development'
    cross = CrossParameters('AMBER14_OpenFF221_fixed_cross_development_v1', sha(receptor_xml),
        canonical_system_sha256(receptor), canonical_topology_sha256(ligand),
        translation.base_parameters.fingerprint_sha256, frame, rows,
        cutoff_angstrom=12., switch_start_angstrom=10., minimum_distance_angstrom=.35,
        dielectric=4., screening_kappa_per_angstrom=0., receptor_block_size=256,
        max_internal_increase_kcal_per_mol=5.)
    FixedReceptorEnvironment(receptor, cross).validate_ligand(ligand, translation.base_parameters)
    output.mkdir(parents=True, exist_ok=False)
    write(output / 'parameters.json', translation.base_parameters.to_dict())
    write(output / 'extensions.json', translation.parameters.to_dict())
    write(output / 'cross-parameters.json', cross.to_dict())
    budget = DockingBudget(candidate_count=2, top_k=1, max_torsions=0,
        max_refinement_steps=32, translation_radius_angstrom=.25, seed=20260929)
    solver = SolverConfig(ReferenceMinimizationConfig(max_iterations=32, max_backtracks=12))
    request = {'schema_id': FIXED_REQUEST_SCHEMA, 'backend': 'python_cpu_reference',
        'receptor': ref(prepared / 'receptor-canonical.json'), 'ligand': ref(prepared / 'ligand-canonical.json'),
        'parameters': ref(output / 'parameters.json'), 'extensions': ref(output / 'extensions.json'),
        'cross_parameters': ref(output / 'cross-parameters.json'), 'solvation': None,
        'pocket': {'center_angstrom': registration['pocket_center_angstrom'], 'radius_angstrom': 10.,
            'coordinate_frame_id': frame, 'source_artifact_sha256': registration['source']['sha256'],
            'method_id': 'public_SRO_centroid_development_anchor_not_PR49_reference', 'method_version': '1'},
        'receptor_margin_angstrom': 4., 'budget': budget.to_dict(), 'solver': solver.to_dict(),
        'comparison': vars(RefinementComparisonConfig()), 'selection': SelectionConfig(1).to_dict()}
    write(output / 'request.json', request)
    plan = {'schema_id': 'pr49_7xtb_d3_development_plan/1.0.0', 'prepared_manifest': ref(prepared / 'manifest.v1.json'),
        'ligand_xml': ref(prepared / 'ligand-unconstrained-openmm-system.xml'), 'receptor_xml': ref(RECEPTOR_XML),
        'request': ref(output / 'request.json'), 'translation': translation.inventory,
        'original_constrained_refusal': refusal, 'numerical_absolute_tolerances': {'energy_kcal_mol': 1e-8, 'force_kcal_mol_angstrom': 1e-8},
        'same_math_vs_source': 'D3 Coulomb constant explicit; original OpenMM built-in constant delta reported separately',
        'registered_pose_execution': {'method': 'native minimize_extended', 'iterations': 32, 'resume_after_accepted_iterations': 3},
        'candidate_comparison': 'two same generated candidates; no AI ordering; convergence required for final refined selection',
        'physical_model': 'fixed fragmented receptor; all ligand internal terms plus finite switched cross LJ/Coulomb; dielectric4 cross; no solvent',
        'excluded_claims': ['observed PR49 pose recovery', 'experimental chemical state equivalence', 'affinity prediction', 'independent benchmark', 'service qualification', 'HIP parity'],
        'same_wall_time_or_same_actual_compute_claimed': False, 'scientifically_validated': False,
        'builder': ref(Path(__file__)), 'build_wall_seconds': time.perf_counter()-started}
    write(output / 'plan.json', plan)
    return {'request': str(output / 'request.json'), 'prepared': str(prepared), 'status': 'DEVELOPMENT_REQUEST_BOUND'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepared', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(build(args.prepared.resolve(), args.output.resolve()), sort_keys=True))

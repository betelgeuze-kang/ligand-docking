"""Bind an independently checked SRO preparation to a frozen same-math audit.

This is numerical development, not source-role admission or pose recovery.
The product minimizer, force model and thresholds are unchanged.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import platform
import time
import xml.etree.ElementTree as ET

BASE = Path('/mnt/193005ba-8531-4d0b-87c2-43c01ee2ce25/ligand_heavy_runs')
RECEPTOR = BASE / 'engine-v2-7xtb-chemical-graph-20260929-final1/receptor-canonical.json'
RECEPTOR_SHA = '2c0970bcaf9e994f382e0f0c0fdacbfd1359bef60a10b879f757b31628658c4c'
RECEPTOR_XML = BASE / 'engine-v2-7xtb-openmm-projection-20260929/openmm-system.xml'
RECEPTOR_XML_SHA = '7c5aeeeafed880dfee5f294fc34b6a0e2ec5a31d9482245b5cab93c10d4d1cc6'
FRAME = '7XTB_original_cartesian_angstrom_development'
AUDIT_PROTOCOL = {'perturbations': 3, 'seed': 20260929, 'perturbation_angstrom': 0.001,
                  'absolute_energy_tolerance_kcal_per_mol': 1e-8,
                  'absolute_force_component_tolerance_kcal_per_mol_angstrom': 1e-8}


def reference(path):
    path = Path(path).resolve(strict=True)
    raw = path.read_bytes()
    return {'path': str(path), 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def checked(reference_document):
    require(reference(reference_document['path']) == reference_document, 'bound_file_changed')


def request_reference(reference_document):
    """The installed workflow accepts exactly path and SHA, not evidence sizes."""
    return {key: reference_document[key] for key in ('path', 'sha256')}


def read_expected(path, expected):
    """Return the exact checked bytes; never reopen them for parsing."""
    path = Path(path).resolve(strict=True)
    raw = path.read_bytes()
    observed = {'path': str(path), 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}
    require(observed['sha256'] == expected['sha256']
            and ('bytes' not in expected or observed['bytes'] == expected['bytes']),
            'verified_preparation_bytes_changed')
    return raw, observed


def publish(path, document):
    raw = (json.dumps(document, indent=2, sort_keys=True, allow_nan=False) + '\n').encode()
    with Path(path).open('xb') as stream:
        stream.write(raw)
    expected = {'path': str(Path(path).resolve()), 'bytes': len(raw),
                'sha256': hashlib.sha256(raw).hexdigest()}
    require(reference(path) == expected, 'published_bytes_changed')
    return expected


def receptor_particles(xml, atom_count):
    """Only fixed-receptor cross interactions use these nonbonded particles.

    Receptor internal energy is explicitly outside this fixed-receptor objective.
    No ligand bonded/exception term is projected by this helper.
    """
    root = ET.fromstring(xml)
    forces = root.find('Forces')
    require(forces is not None, 'receptor_force_inventory_missing')
    matches = [f for f in forces if f.attrib.get('type') == 'NonbondedForce']
    require(len(matches) == 1, 'exactly_one_receptor_nonbonded_force_required')
    particles = matches[0].find('Particles')
    require(particles is not None and len(particles) == atom_count, 'receptor_particle_coverage')
    rows = []
    for index, particle in enumerate(particles):
        sigma, epsilon, charge = (float(particle.attrib[k]) for k in ('sig', 'eps', 'q'))
        require(all(math.isfinite(v) for v in (sigma, epsilon, charge))
                and sigma > 0 and epsilon >= 0, 'invalid_receptor_nonbonded_particle')
        rows.append((index, sigma * 10., epsilon / 4.184, charge))
    return rows


def build(prepared, output, expected_source_sha256):
    from betelgeuze_engine_v2.docking import DockingBudget
    from betelgeuze_engine_v2.molecular import canonical_system_sha256, canonical_topology_sha256
    from betelgeuze_engine_v2.molecular.serialization import all_atom_system_from_canonical_json
    from betelgeuze_engine_v2.physics.reference_parameters import AtomNonbondedParameter
    from betelgeuze_product.cpu_refinement.reference_minimization_v1_1 import ReferenceMinimizationConfig
    from betelgeuze_product.cpu_refinement.refinement_comparison import RefinementComparisonConfig
    from betelgeuze_product.cpu_refinement_v1_2.fixed_receptor import CrossParameters, FixedReceptorEnvironment
    from betelgeuze_product.cpu_refinement_v1_2.minimization import SolverConfig
    from betelgeuze_product.cpu_refinement_v1_2.provenance import digest, source_manifest
    from betelgeuze_product.cpu_refinement_v1_2.scoring_profile import REGISTERED_REQUEST_SCHEMA
    from betelgeuze_product.cpu_refinement_v1_2.selection import SelectionConfig
    from betelgeuze_product.cpu_refinement_v1_2.workflow import REQUEST_SCHEMA, load_request
    from tools.product.openmm_d3_translation import TranslationSettings, convert_openmm_system
    from docs.research.human_5ht6_sro_numerical_preparation import verify_sro
    from docs.research.human_5ht6_d3_complex.product_geometry_audit import ProductGeometryAudit

    started = time.perf_counter()
    sources = source_manifest()
    require(digest(sources) == expected_source_sha256, 'native_source_not_frozen')
    prepared, output = Path(prepared).resolve(strict=True), Path(output).absolute()
    output.mkdir(parents=True, exist_ok=False)
    initial_manifest_ref = reference(prepared / 'manifest.v1.json')
    protocol_ref = publish(output / 'predeclaration.json', {
        'schema_id': 'sro_same_math_audit_predeclaration/1.0.0', 'audit_protocol': AUDIT_PROTOCOL,
        'native_source_sha256': expected_source_sha256, 'prepared_manifest': initial_manifest_ref,
        'source_role': 'numerical_development_only_existing_reservations_unchanged',
        'state': 'one_predeclared_NZ_plus1_computational_state_not_measured_protonation',
        'objective': 'unconstrained_ligand_internal_plus_fixed_receptor_switched_LJ_and_screened_Coulomb',
        'cross': {'cutoff_angstrom': 12., 'switch_start_angstrom': 10., 'minimum_distance_angstrom': .35,
                  'dielectric': 4., 'screening_kappa_per_angstrom': 0., 'max_internal_increase_kcal_per_mol': 5.},
        'physical_scope': 'fixed_fragment_receptor_no_membrane_no_solvent_no_receptor_internal_energy',
        'optimization_or_scoring_requested': False, 'new_training_or_source_admission': False,
        'independent_pose_recovery_or_affinity_evaluation': False})
    stage = 'independent_preparation_verification'
    try:
        verification = verify_sro.verify_packet(prepared)
        require(verification.get('passed') is True and not verification.get('errors'), 'preparation_verification_failed')
        require(verification['manifest'] == initial_manifest_ref, 'verified_manifest_changed')
        raw_manifest, _ = read_expected(prepared / 'manifest.v1.json', initial_manifest_ref)
        manifest = json.loads(raw_manifest)
        ligand_raw, ligand_ref = read_expected(prepared / 'ligand-canonical.json',
                                               manifest['files']['ligand-canonical.json'])
        ligand_xml_raw, ligand_xml_ref = read_expected(prepared / 'ligand-unconstrained-openmm-system.xml',
                                                       manifest['files']['ligand-unconstrained-openmm-system.xml'])
        receptor_raw, receptor_ref = read_expected(RECEPTOR, {'sha256': RECEPTOR_SHA})
        receptor_xml_raw, receptor_xml_ref = read_expected(RECEPTOR_XML, {'sha256': RECEPTOR_XML_SHA})
        verification_ref = publish(output / 'preparation-verification.json', verification)
        refs = {name: reference(path) for name, path in (
            ('builder', __file__), ('verifier', verify_sro.__file__))}
        refs.update(prepared_manifest=initial_manifest_ref, ligand=ligand_ref, ligand_xml=ligand_xml_ref,
                    receptor=receptor_ref, receptor_xml=receptor_xml_ref)
        stage = 'unconstrained_ligand_translation'
        ligand = all_atom_system_from_canonical_json(ligand_raw)
        receptor = all_atom_system_from_canonical_json(receptor_raw)
        require(ligand.atom_count == 26 and sum(a.formal_charge for a in ligand.atoms) == 1,
                'declared_SRO_microstate_mismatch')
        heavy = [a.index for a in ligand.atoms if a.element != 'H']
        require(len(heavy) == 13 and receptor.atom_count == 4376, 'prepared_atom_counts_mismatch')
        translation = convert_openmm_system(ligand_xml_raw, ligand,
            TranslationSettings('SRO_NZ_plus1_OpenFF221_unconstrained_numerical_v1', 100., 90., .35))
        require(not translation.parameters.constraints, 'unconstrained_SRO_required')
        rows = tuple(AtomNonbondedParameter(*row) for row in receptor_particles(receptor_xml_raw, receptor.atom_count))
        cross = CrossParameters('AMBER14_OpenFF221_SRO_fixed_cross_numerical_v1', refs['receptor_xml']['sha256'],
            canonical_system_sha256(receptor), canonical_topology_sha256(ligand),
            translation.base_parameters.fingerprint_sha256, FRAME, rows,
            cutoff_angstrom=12., switch_start_angstrom=10., minimum_distance_angstrom=.35,
            dielectric=4., screening_kappa_per_angstrom=0., receptor_block_size=256,
            max_internal_increase_kcal_per_mol=5.)
        FixedReceptorEnvironment(receptor, cross).validate_ligand(ligand, translation.base_parameters)
        parameters_ref = publish(output / 'parameters.json', translation.base_parameters.to_dict())
        extensions_ref = publish(output / 'extensions.json', translation.parameters.to_dict())
        cross_ref = publish(output / 'cross-parameters.json', cross.to_dict())
        center = ligand.coordinates[0, heavy].mean(dim=0).tolist()
        budget = DockingBudget(candidate_count=1, top_k=1, max_torsions=0, max_refinement_steps=32,
                               translation_radius_angstrom=0., seed=20260929)
        solver = SolverConfig(ReferenceMinimizationConfig(max_iterations=32, max_backtracks=12))
        request = {'schema_id': REGISTERED_REQUEST_SCHEMA, 'backend': 'python_cpu_reference',
            'receptor': request_reference(refs['receptor']), 'ligand': request_reference(refs['ligand']),
            'parameters': request_reference(parameters_ref), 'extensions': request_reference(extensions_ref),
            'cross_parameters': request_reference(cross_ref), 'solvation': None,
            'pocket': {'center_angstrom': center, 'radius_angstrom': 10., 'coordinate_frame_id': FRAME,
                       'source_artifact_sha256': verification['source_ref']['sha256'],
                       'method_id': 'public_SRO_heavy_centroid_same_math_development', 'method_version': '1'},
            'receptor_margin_angstrom': 4., 'budget': budget.to_dict(), 'solver': solver.to_dict(),
            'comparison': vars(RefinementComparisonConfig()), 'selection': SelectionConfig(1).to_dict()}
        stage = 'registered_request_contract'
        internal_request = {k: v for k, v in request.items() if k != 'cross_parameters'}
        internal_request['schema_id'] = REQUEST_SCHEMA
        authority, _, _, _, loaded_budget, *_ = load_request(internal_request, expected_source_sha256)
        baseline_geometry = ProductGeometryAudit(authority, loaded_budget, ligand).baseline_report()
        # A numerical audit checks arithmetic even when a physical-validity gate fails.
        # Preserve this result explicitly; it is not an admission override.
        geometry_ref = publish(output / 'initial-product-geometry.json', baseline_geometry)
        request_ref = publish(output / 'request.json', request)
        for ref in [*refs.values(), protocol_ref, verification_ref, parameters_ref, extensions_ref,
                    cross_ref, geometry_ref, request_ref]:
            checked(ref)
        for ref in verification['validated_outputs'].values():
            checked(ref)
        require(source_manifest() == sources, 'native_source_changed')
        plan = {'schema_id': 'sro_same_math_numerical_plan/1.0.0', 'predeclaration': protocol_ref,
            'independent_preparation_verification': verification_ref, 'inputs': refs, 'request': request_ref,
            'initial_product_geometry': geometry_ref,
            'native_source_sha256': expected_source_sha256, 'audit_protocol': AUDIT_PROTOCOL,
            'translation_inventory': translation.inventory, 'runtime_python': platform.python_version(),
            'initial_heavy_coordinates_preserved_by_independent_verifier': True,
            'build_wall_seconds': time.perf_counter() - started, 'force_or_energy_evaluations': 0,
            'product_qualified': False, 'source_roles_admitted': False}
        publish(output / 'plan.json', plan)
        return {'output': str(output), 'request_bound': True, 'atom_count': ligand.atom_count,
                'force_or_energy_evaluations': 0}
    except Exception as exc:
        publish(output / 'failure.json', {'stage': stage, 'type': type(exc).__name__, 'reason': str(exc),
            'wall_seconds': time.perf_counter() - started, 'product_qualified': False})
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepared', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--expected-source-sha256', required=True)
    args = parser.parse_args()
    print(json.dumps(build(args.prepared, args.output, args.expected_source_sha256), sort_keys=True))


if __name__ == '__main__':
    main()

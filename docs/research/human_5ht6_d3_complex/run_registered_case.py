"""Run and exactly resume native D3 on the registered development coordinates."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import time

import torch
from betelgeuze_engine_v2.molecular import canonical_system_sha256
from betelgeuze_engine_v2.molecular.serialization import canonical_system_json_bytes
from betelgeuze_product.reference_minimization_workflow import _bound
from betelgeuze_product.cpu_refinement_v1_2.workflow import load_request, REQUEST_SCHEMA
from betelgeuze_product.cpu_refinement_v1_2.fixed_receptor import CrossParameters, FixedReceptorEnvironment, FIXED_REQUEST_SCHEMA
from betelgeuze_product.cpu_refinement_v1_2.minimization import minimize_extended
from betelgeuze_product.cpu_refinement_v1_2.provenance import source_manifest, digest


def write(path, document):
    with path.open('x') as stream:
        json.dump(document, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write('\n')


def run(request_path, output):
    started = time.perf_counter()
    request = json.loads(request_path.read_bytes())
    if request['schema_id'] != FIXED_REQUEST_SCHEMA:
        raise ValueError('fixed receptor request required')
    source = source_manifest()
    internal_request = {k: v for k, v in request.items() if k != 'cross_parameters'}
    internal_request['schema_id'] = REQUEST_SCHEMA
    _, receptor, ligand, parameters, _, solver, solvent, _, _ = load_request(internal_request, digest(source))
    if solvent is not None:
        raise ValueError('this experiment excludes implicit solvent')
    fixed = FixedReceptorEnvironment(receptor, CrossParameters.from_dict(_bound(request['cross_parameters'])))
    output.mkdir(parents=True, exist_ok=False)
    write(output / 'request.json', request)
    full_start = time.perf_counter()
    full = minimize_extended(ligand, parameters, solver, fixed_environment=fixed)
    full_seconds = time.perf_counter()-full_start
    write(output / 'full-checkpoint.json', full.checkpoint.to_dict())
    split_start = time.perf_counter()
    paused = minimize_extended(ligand, parameters, solver, fixed_environment=fixed, pause_after_accepted_iterations=3)
    write(output / 'paused-checkpoint.json', paused.checkpoint.to_dict())
    resumed = minimize_extended(ligand, parameters, solver, fixed_environment=fixed,
        checkpoint=json.loads((output / 'paused-checkpoint.json').read_bytes()))
    split_seconds = time.perf_counter()-split_start
    write(output / 'resumed-checkpoint.json', resumed.checkpoint.to_dict())
    exact = full.checkpoint.to_dict() == resumed.checkpoint.to_dict()
    if not exact or not torch.equal(full.system.coordinates, resumed.system.coordinates):
        raise ValueError('continuous and resumed D3 results differ')
    if source != source_manifest():
        raise ValueError('implementation changed during experiment')
    for name in ('receptor', 'ligand', 'parameters', 'extensions', 'cross_parameters'):
        _bound(request[name])
    fixed.assert_intact()
    with (output / 'final-canonical.json').open('xb') as stream:
        stream.write(canonical_system_json_bytes(full.system))
    write(output / 'final-coordinates.json', {'coordinates_angstrom': full.system.coordinates[0].tolist()})
    checkpoint = full.checkpoint.to_dict()
    report = {'schema_id': 'pr49_registered_native_d3_execution/1.0.0',
        'request_sha256': digest(request), 'implementation_source_sha256': digest(source),
        'source_ligand_system_sha256': canonical_system_sha256(ligand),
        'fixed_receptor_system_sha256': canonical_system_sha256(receptor),
        'final_ligand_system_sha256': canonical_system_sha256(full.system),
        'status': checkpoint['status'], 'converged': full.converged,
        'initial_energy_kcal_per_mol': checkpoint['initial_energy'],
        'final_energy_kcal_per_mol': checkpoint['current_energy'],
        'initial_components': checkpoint['initial_components'], 'final_components': checkpoint['current_components'],
        'initial_max_force_kcal_mol_angstrom': checkpoint['initial_max_tangent_force'],
        'final_max_force_kcal_mol_angstrom': checkpoint['current_max_tangent_force'],
        'accepted_iterations': checkpoint['accepted_iterations'], 'force_evaluations': checkpoint['evaluation_count'],
        'continuous_execution': dict(full.execution), 'paused_execution': dict(paused.execution), 'resumed_execution': dict(resumed.execution),
        'exact_continuous_resume_checkpoint_and_coordinates': exact,
        'continuous_wall_seconds': full_seconds, 'paused_plus_resume_wall_seconds': split_seconds,
        'whole_wall_seconds_before_report_publication': time.perf_counter()-started,
        'timing_note': 'continuous and paused-plus-resume are separate repeated executions; nested execution scopes must not be added',
        'observed_reference_pose': False, 'affinity_validated': False, 'scientifically_validated': False,
        'numerical_oracle_required_separately': True}
    write(output / 'report.json', report)
    return {k: report[k] for k in ('status','converged','initial_energy_kcal_per_mol','final_energy_kcal_per_mol','accepted_iterations','force_evaluations','exact_continuous_resume_checkpoint_and_coordinates')}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--request', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    torch.set_num_threads(1)
    print(json.dumps(run(args.request.resolve(), args.output.resolve()), sort_keys=True))

"""Explicit opt-in shape profile over a named, unchanged base model.

Additive binding of unchanged ShapeProfile and durable executor to P1 budgets.
The original parent must be supplied and bound for every run. Frozen APIs stay unchanged.
"""
from dataclasses import asdict
import hashlib
import json
from pathlib import Path

from betelgeuze_engine_v2.molecular import canonical_system_sha256, canonical_topology_sha256
from betelgeuze_product.cpu_refinement_v1_2.provenance import (
    ResearchError, canonical, coordinates_hex, digest,
)
from betelgeuze_product.cpu_refinement_v1_3 import minimization as execution
from betelgeuze_product.cpu_refinement_shape_v1.profile import ShapeProfile
from betelgeuze_product.cpu_prepared_cartesian_budget_v3 import workflow as budget

RESULT_SCHEMA = 'cpu_prepared_shape_budget_result/1.0.0'
BINDING_SCHEMA = 'cpu_prepared_shape_budget_binding/1.0.0'


def implementation_sources(base_profile):
    from betelgeuze_product.cpu_refinement_shape_v1 import cartesian as original
    result = dict(original.implementation_sources(base_profile))
    result.update(budget.implementation_sources())
    from betelgeuze_product.cpu_refinement_diagnostics_v1.contracts import implementation_sources as diagnostic_sources
    result.update(diagnostic_sources())
    for path in sorted(Path(__file__).resolve().parent.glob('*.py')):
        result['betelgeuze_product/cpu_prepared_shape_comparison_v1/' + path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result


def system_identity(system):
    from betelgeuze_product.cpu_refinement_shape_v1.reference import MoleculeIdentity
    # Source atom index, all atom metadata and full canonical topology are bound.
    # Distances never determine mapping or atom selection.
    return {'identity': MoleculeIdentity(
        atom_ids=tuple(digest(asdict(atom)) for atom in system.atoms),
        elements=tuple(atom.element for atom in system.atoms),
        covalent_bonds=tuple(sorted((bond.atom_i, bond.atom_j, digest(asdict(bond)))
                                   for bond in system.bonds)),
        canonical_molecule=canonical_topology_sha256(system))}


def prepare_reference(system, binding):
    from betelgeuze_product.cpu_refinement_shape_v1.reference import ShapeReference
    from betelgeuze_product.cpu_refinement_v1_2.fixed_receptor import require_system
    require_system(system, 256)
    if binding['initial_coordinates_sha256'] != digest(coordinates_hex(system.coordinates)):
        raise ResearchError('reference input coordinates differ from bound original')
    return ShapeReference(system_identity(system)['identity'], system.coordinates[0].tolist(),
        parent_provenance=canonical(asdict(system.provenance)),
        source_identity='prepared_protocol_sha256',
        source_digest=binding['prepared_protocol_sha256'])


def _calculate(contract, coordinates, strength, *, identity):
    if contract.strength != strength:
        raise ResearchError('shape strength changed')
    result = contract.evaluate(coordinates, identity=identity)
    return result.energy, result.forces


def _context(system, parameters, config, fixed_environment, binding, *,
             base_profile, reference, strength):
    from betelgeuze_product.cpu_refinement_shape_v1.reference import ShapeReference, ShapeContract
    if base_profile != binding.get('model') or config.algorithm != 'lbfgs':
        raise ResearchError('explicit matching prepared model and L-BFGS required')
    evaluator, base_identity = budget._context(system, parameters, config, fixed_environment, binding)
    if type(reference) is not ShapeReference:
        raise ResearchError('explicit validated immutable shape reference required')
    reference.validate_integrity()
    if reference.identity != system_identity(system)['identity']:
        raise ResearchError('shape reference atom/topology identity mismatch')
    if coordinates_hex(system.coordinates) != [[v.hex() for v in row] for row in reference.coordinates]:
        raise ResearchError('shape reference must be the original supplied parent')
    if (reference.source_digest != binding['prepared_protocol_sha256']
            or reference.source_identity != 'prepared_protocol_sha256'
            or reference.parent_provenance != canonical(asdict(system.provenance))):
        raise ResearchError('shape parent source role/protocol binding mismatch')
    contract = ShapeContract(reference, strength)
    profile = ShapeProfile(contract, float(strength), system_identity, _calculate,
                           fixed_environment.cross.max_internal_increase_kcal_per_mol)
    def source():
        return implementation_sources(base_profile)
    identity = {'schema_id': BINDING_SCHEMA,
                'source_system_sha256': canonical_system_sha256(system),
                'evaluator': evaluator.identity(), 'config': config.to_dict(),
                'implementation_sha256': digest(source()), 'environment': base_identity['environment'],
                'external_binding': binding, 'base_profile': base_profile,
                'base_binding': base_identity,
                'shape_reference': reference.to_document(),
                'shape_reference_sha256': reference.digest,
                'shape_contract_sha256': contract.digest,
                'strength_kcal_per_mol_per_angstrom_squared': contract.strength.hex(),
                'observation_schema': 'cpu_parent_shape_observation/1.0.0'}
    identity = json.loads(canonical(identity))

    def guard():
        fixed_environment.assert_intact()
        if reference.to_document() != identity['shape_reference']:
            raise ResearchError('original shape reference mutated')
        contract.validate_integrity()
        if contract.digest != identity['shape_contract_sha256']:
            raise ResearchError('shape contract changed')
        if reference.identity != system_identity(system)['identity']:
            raise ResearchError('original topology changed')

    return evaluator, identity, profile, source, guard


def minimize_shape(system, parameters, config, *, fixed_environment, run_dir, binding,
                   base_profile, reference, strength, pause_after_objective_attempts=None,
                   resume=False):
    evaluator, identity, profile, source, guard = _context(
        system, parameters, config, fixed_environment, binding,
        base_profile=base_profile, reference=reference, strength=strength)
    return execution._minimize_profile(system, config, evaluator=evaluator, identity=identity,
        run_dir=run_dir, implementation_sources=source, result_schema=RESULT_SCHEMA,
        model_guard=guard, profile=profile, pause_after_objective_attempts=pause_after_objective_attempts,
        resume=resume)


def verify_shape(system, parameters, config, *, fixed_environment, run_dir, binding,
                 base_profile, reference, strength):
    evaluator, identity, profile, source, guard = _context(
        system, parameters, config, fixed_environment, binding,
        base_profile=base_profile, reference=reference, strength=strength)
    return execution._verify_profile(system, config, evaluator=evaluator, identity=identity,
        run_dir=run_dir, implementation_sources=source, result_schema=RESULT_SCHEMA,
        model_guard=guard, profile=profile)

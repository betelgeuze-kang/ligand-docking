"""Keep full source metadata and integrity, without duplicating it into pair tiles."""
from dataclasses import replace
import pytest
from betelgeuze_engine.product import v2_cross_interaction as adapter
from betelgeuze_engine_v2.molecular import MolecularIntegrityError
from tests.unit.test_v2_prepared_cross_interaction import (
    _pair, _evaluate, _assert_oracle, _state_with_nested_tensor_metadata,
    _mutate_without_parent_tensor_version,
)


def state():
    receptor, ligand, rp, lp = _pair()
    receptor = replace(receptor, atoms=tuple(replace(a, metadata={'source_payload': list(range(500)), 'state_tag': 'original'}) for a in receptor.atoms))
    return receptor, ligand, rp, lp


def test_projection_keeps_source_maps_without_copying_unrelated_source_payload(monkeypatch):
    values = state()
    original = adapter.evaluate_reference_force_field
    observed = []
    def checked(system, graph, params):
        for atom in system.atoms:
            assert set(atom.metadata) == {'projection_source_side', 'projection_source_atom'}
            observed.append(dict(atom.metadata))
        return original(system, graph, params)
    monkeypatch.setattr(adapter, 'evaluate_reference_force_field', checked)
    result = _evaluate(*values)
    assert observed == [{'projection_source_side': 'receptor', 'projection_source_atom': 0},
                        {'projection_source_side': 'ligand', 'projection_source_atom': 0}]
    assert values[0].atoms[0].metadata['source_payload'] == list(range(500))
    assert 'source_payload' in str(result['sources']['receptor']['system'])
    _assert_oracle(result, values)


def test_source_metadata_mutation_during_tile_still_fails_original_guard(monkeypatch):
    values = _state_with_nested_tensor_metadata()
    original = adapter.evaluate_reference_force_field
    def mutated(*args):
        result = original(*args)
        # The original object is frozen; tensor mutation bypasses container guards.
        _mutate_without_parent_tensor_version(values[0], 'atom_metadata')
        return result
    monkeypatch.setattr(adapter, 'evaluate_reference_force_field', mutated)
    with pytest.raises(MolecularIntegrityError):
        _evaluate(*values)

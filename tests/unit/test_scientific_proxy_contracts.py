from __future__ import annotations

import numpy as np
import pytest

from core.allatom_forcefield import (
    allatom_energy,
    partial_charges_from_atom_types,
    topology_nonbonded_rules,
)
from core.explicit_solvent import explicit_solvation_energy
from core.fep import bar_free_energy, estimate_binding_fep
from core.refine_physics import (
    gb_solvation_energy,
    lj_energy,
    lj_force_magnitude,
    sa_surface_energy,
    vdw_params_for_element,
)


def test_severe_overlap_has_large_finite_repulsion() -> None:
    result = allatom_energy(
        np.asarray([[0.0, 0.0, 0.0], [0.5, 0.0, 0.0]]),
        ["C", "C"],
        bonds=[],
    )
    assert np.isfinite(result["e_vdw"])
    assert result["e_vdw"] > 1_000_000.0


def test_halogen_parameters_do_not_collapse_to_carbon() -> None:
    carbon = vdw_params_for_element("C")
    chlorine = vdw_params_for_element("Cl")
    bromine = vdw_params_for_element("Br")
    assert chlorine != carbon
    assert bromine != carbon
    assert chlorine != bromine


def test_topology_rules_exclude_12_13_and_scale_14() -> None:
    excluded, scaled = topology_nonbonded_rules(
        4,
        [(0, 1), (1, 2), (2, 3)],
    )
    assert {(0, 1), (1, 2), (2, 3), (0, 2), (1, 3)} <= excluded
    assert scaled == {(0, 3)}


def test_fragment_ids_prevent_cross_fragment_bond_inference() -> None:
    coords = np.asarray([[0.0, 0.0, 0.0], [1.2, 0.0, 0.0]])
    result = allatom_energy(coords, ["C", "C"], fragment_ids=[0, 1])
    assert result["bond_count"] == 0
    assert result["fragment_count"] == 2
    with pytest.raises(ValueError, match="cross fragment"):
        allatom_energy(
            coords,
            ["C", "C"],
            bonds=[(0, 1)],
            fragment_ids=[0, 1],
        )


def test_allatom_default_does_not_silently_force_net_charge_to_zero() -> None:
    coords = np.asarray([[0.0, 0.0, 0.0], [1.3, 0.0, 0.0]])
    result = allatom_energy(coords, ["N", "H"], bonds=[(0, 1)])
    assert result["charge_model"] == "typed_partial_charge_preserve_net_v2"
    assert abs(float(result["net_charge_e"])) > 1e-8

    atom_types = result["atom_types"]
    neutralized = partial_charges_from_atom_types(atom_types, neutralize=True)
    assert float(np.sum(neutralized)) == pytest.approx(0.0, abs=1e-12)


def test_allatom_proxy_rejects_nonfinite_coordinates_and_charges() -> None:
    coords = np.asarray([[0.0, 0.0, 0.0], [1.4, 0.0, 0.0]], dtype=np.float64)
    with pytest.raises(ValueError, match="finite"):
        allatom_energy(
            np.asarray([[0.0, 0.0, 0.0], [np.nan, 0.0, 0.0]], dtype=np.float64),
            ["C", "C"],
        )
    with pytest.raises(ValueError, match="finite"):
        allatom_energy(coords, ["C", "C"], charges=np.asarray([0.0, np.inf]))


def test_lj_force_matches_negative_energy_derivative() -> None:
    distance = 3.8
    step = 1e-5
    energy_plus = float(lj_energy(np.asarray([distance + step]), 3.5, 0.08)[0])
    energy_minus = float(lj_energy(np.asarray([distance - step]), 3.5, 0.08)[0])
    finite_difference_force = -(energy_plus - energy_minus) / (2.0 * step)
    analytic_force = float(lj_force_magnitude(np.asarray([distance]), 3.5, 0.08)[0])
    assert analytic_force == pytest.approx(finite_difference_force, rel=1e-6, abs=1e-6)


def test_gb_pair_term_depends_on_interatomic_distance() -> None:
    charges = np.asarray([1.0, -1.0])
    radii = np.asarray([1.5, 1.5])
    near = gb_solvation_energy(
        charges,
        radii,
        coords=np.asarray([[0.0, 0.0, 0.0], [2.0, 0.0, 0.0]]),
    )
    far = gb_solvation_energy(
        charges,
        radii,
        coords=np.asarray([[0.0, 0.0, 0.0], [8.0, 0.0, 0.0]]),
    )
    assert near != pytest.approx(far)


def test_bonded_molecule_has_nonzero_accessible_surface() -> None:
    energy = sa_surface_energy(
        np.asarray([[0.0, 0.0, 0.0], [1.54, 0.0, 0.0]]),
        elements=["C", "C"],
    )
    assert energy > 0.0


def test_bar_uses_forward_and_reverse_ensemble_samples() -> None:
    result = bar_free_energy(
        np.asarray([0.9, 1.0, 1.1]),
        np.asarray([-0.9, -1.0, -1.1]),
    )
    assert result == pytest.approx(1.0, abs=1e-8)
    with pytest.raises(ValueError, match="separate forward and reverse"):
        bar_free_energy(np.asarray([0.9, 1.0, 1.1]))


def test_static_alchemical_endpoint_is_blocked_from_fep_claim() -> None:
    protein = np.asarray([[0.0, 0.0, 0.0], [4.0, 0.0, 0.0]])
    ligand = np.asarray([[2.0, 2.0, 0.0], [3.5, 2.0, 0.0]])
    result = estimate_binding_fep(protein, ligand, n_windows=5, n_bootstrap=100)
    assert result["status"] == "blocked_static_alchemical_endpoint_proxy"
    assert result["is_fep"] is False
    assert result["is_binding_free_energy"] is False
    assert result["ensemble_sample_count"] == 0
    assert result["delta_g_fep_kcal_mol"] is None
    assert result["delta_g_fep_std_kcal_mol"] is None


def test_fixed_oxygen_shell_is_not_labeled_tip3p_or_explicit_md() -> None:
    result = explicit_solvation_energy(
        np.asarray([[0.0, 0.0, 0.0], [1.5, 0.0, 0.0]]),
        ["C", "O"],
    )
    assert result["status"] == "fixed_oxygen_shell_proxy_ready"
    assert result["is_tip3p"] is False
    assert result["is_explicit_solvent_md"] is False
    assert result["score_unit"] == "internal_proxy_unit"
    assert result["delta_e_total_kcal_mol"] is None


def test_fixed_oxygen_shell_rejects_invalid_geometry_parameters() -> None:
    from core.explicit_solvent import place_fixed_oxygen_shell

    with pytest.raises(ValueError, match="finite"):
        place_fixed_oxygen_shell(np.asarray([[np.nan, 0.0, 0.0]]))
    with pytest.raises(ValueError, match="spacing_a"):
        place_fixed_oxygen_shell(np.asarray([[0.0, 0.0, 0.0]]), spacing_a=0.0)

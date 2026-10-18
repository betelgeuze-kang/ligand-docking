"""Synthetic geometry only: receptor-frame direction, proper rotation and maps."""

import copy
import math

import pytest
import torch

from tools.pfk_paired_water_eight_dof.metrics import (
    MetricDataError,
    admit_crystal_reference,
    closest_contacts,
    evaluate_structural_diagnostics,
    fit_receptor_frame,
    ring_planarity,
)


DTYPE = torch.float64
CA = torch.tensor([[0., 0., 0.], [2., 0., 0.], [0., 3., 0.], [0., 0., 4.]], dtype=DTYPE)
LIGAND = torch.tensor([[.2, .3, .4], [1.4, -.2, .5], [-.3, 1.1, .7], [.1, -.4, 1.6]], dtype=DTYPE)
MAPS = [[0, 1, 2, 3], [1, 0, 2, 3], [0, 1, 3, 2], [1, 0, 3, 2]]
ROTATION = torch.tensor([[0., 1., 0.], [-1., 0., 0.], [0., 0., 1.]], dtype=DTYPE)
TRANSLATION = torch.tensor([12., -8., 5.], dtype=DTYPE)
FACTS = {"primary_reference_admission_sha256": "a" * 64, "synthetic_fixture": True}
POLICY = "b" * 64


def reference(**changes):
    kwargs = dict(crystal_ca=CA, prepared_ca=CA,
                  crystal_heavy_ccd_order=LIGAND, prepared_heavy_indices=[0, 1, 2, 3],
                  prepared_to_ccd_mappings=MAPS, prepared_atom_count=4,
                  source_facts=FACTS, metric_policy_sha256=POLICY)
    kwargs.update(changes)
    return admit_crystal_reference(**kwargs)


def states(coordinates):
    return dict(P0=coordinates, start=coordinates, final=coordinates)


def test_receptor_kabsch_row_direction_and_fixed_reference_frame():
    moved_ca = CA @ ROTATION + TRANSLATION
    moved_ligand = LIGAND @ ROTATION + TRANSLATION
    ref = reference(prepared_ca=moved_ca)
    fitted = ref.transform
    torch.testing.assert_close(torch.tensor(fitted.rotation, dtype=DTYPE), ROTATION, rtol=0., atol=2e-15)
    torch.testing.assert_close(torch.tensor(fitted.translation, dtype=DTYPE), TRANSLATION, rtol=0., atol=3e-15)
    assert fitted.determinant == pytest.approx(1.)
    assert fitted.receptor_rmsd_angstrom < 3e-15
    report = ref.evaluate_states(states(moved_ligand))
    assert report["states"]["final"]["symmetry_aware_heavy_rmsd_angstrom"] < 5e-15
    assert report["receptor_alignment"]["ligand_used_in_fit"] is False
    assert report["receptor_alignment"]["outlier_removal_performed"] is False


def test_common_receptor_frame_change_preserves_all_mapping_labels():
    displacement = torch.tensor([.7, -.2, .3], dtype=DTYPE)
    original = reference().evaluate_states(states(LIGAND + displacement))
    moved = reference(prepared_ca=CA @ ROTATION + TRANSLATION).evaluate_states(
        states((LIGAND + displacement) @ ROTATION + TRANSLATION))
    assert moved["states"]["final"]["all_graph_mapping_rmsd_angstrom"] == pytest.approx(
        original["states"]["final"]["all_graph_mapping_rmsd_angstrom"], abs=3e-15)


def test_ligand_translation_is_not_fitted_away_and_comparison_uses_raw_states():
    ref = reference()
    start = LIGAND + torch.tensor([3., 4., 0.], dtype=DTYPE)
    final = LIGAND + torch.tensor([0., 0., 2.], dtype=DTYPE)
    report = ref.evaluate_states(dict(P0=LIGAND, start=start, final=final))
    assert report["states"]["start"]["symmetry_aware_heavy_rmsd_angstrom"] == pytest.approx(5.)
    assert report["states"]["final"]["symmetry_aware_heavy_rmsd_angstrom"] == pytest.approx(2.)
    assert report["comparison"]["final_minus_start_reference_rmsd_angstrom"] == pytest.approx(-3.)
    assert report["states"]["final"]["direct_heavy_displacement_from_start_rmsd_angstrom"] == pytest.approx(math.sqrt(29.))
    assert all(row["ligand_fit_performed"] is False for row in report["states"].values())
    assert report["boundary"]["success_threshold_applied"] is False
    assert report["boundary"]["pose_selection_admitted"] is False


def test_reflection_never_becomes_an_improper_rotation():
    reflected = CA.clone()
    reflected[:, 0] *= -1
    transform = fit_receptor_frame(CA, reflected)
    rotation = torch.tensor(transform.rotation, dtype=DTYPE)
    assert torch.det(rotation) == pytest.approx(1.)
    assert transform.receptor_rmsd_angstrom > .5
    assert not torch.allclose(transform.apply(CA), reflected)


def test_all_and_only_admitted_mappings_are_retained_in_their_original_order():
    reordered = [MAPS[2], MAPS[3], MAPS[0], MAPS[1]]
    report = reference(prepared_to_ccd_mappings=reordered).evaluate_states(states(LIGAND))
    values = report["states"]["final"]["all_graph_mapping_rmsd_angstrom"]
    assert len(values) == 4
    assert values[2] == pytest.approx(0., abs=1e-15)
    assert report["states"]["final"]["minimum_mapping_index"] == 2
    assert report["prepared_to_ccd_heavy_index_arrays"] == reordered
    assert values[0] > .5


def test_mapping_direction_is_prepared_heavy_position_to_ccd_row():
    cycle = [1, 2, 0, 3]  # Its inverse differs, so direction mistakes are visible.
    mappings = [cycle, MAPS[0], MAPS[1], MAPS[2]]
    report = reference(prepared_to_ccd_mappings=mappings).evaluate_states(
        states(LIGAND[cycle]))
    values = report["states"]["final"]["all_graph_mapping_rmsd_angstrom"]
    assert values[0] == pytest.approx(0., abs=1e-15)
    assert min(values[1:]) > .5


@pytest.mark.parametrize("maps", [None, [], MAPS[:3], MAPS + [MAPS[0]],
                                  [MAPS[0]] * 4, {"mapping": MAPS}])
def test_missing_unsupported_or_duplicate_map_sets_are_errors(maps):
    with pytest.raises(MetricDataError):
        reference(prepared_to_ccd_mappings=maps)


@pytest.mark.parametrize("bad", [[0, 0, 2, 3], [0, 1, 2], [0, 1, 2, 4],
                                [0, 1, 2, -1], [False, 1, 2, 3], [0., 1, 2, 3]])
def test_incomplete_or_nonbijective_mapping_is_rejected(bad):
    maps = copy.deepcopy(MAPS)
    maps[0] = bad
    with pytest.raises(MetricDataError):
        reference(prepared_to_ccd_mappings=maps)


@pytest.mark.parametrize("indices", [[0, 0, 2, 3], [0, 1, 2], [0, 1, 2, 4],
                                    [False, 1, 2, 3]])
def test_prepared_heavy_subset_requires_unique_exact_coverage(indices):
    with pytest.raises(MetricDataError):
        reference(prepared_heavy_indices=indices)


@pytest.mark.parametrize("coords", [[], [[0., 1.]], [[True, 0., 1.]],
                                   [[float("nan"), 0., 1.]],
                                   [[float("inf"), 0., 1.]],
                                   [[10 ** 1000, 0., 1.]], CA.float()])
def test_nonfinite_malformed_or_lossy_coordinate_inputs_are_errors(coords):
    with pytest.raises(MetricDataError):
        reference(crystal_ca=coords)


def test_missing_ca_pairs_or_degenerate_registration_are_errors():
    with pytest.raises(MetricDataError):
        reference(prepared_ca=CA[:3])
    with pytest.raises(MetricDataError):
        fit_receptor_frame(CA[:2], CA[:2])
    line = [[0., 0., 0.], [1., 0., 0.], [2., 0., 0.]]
    with pytest.raises(MetricDataError, match="rigid frame"):
        fit_receptor_frame(line, line)


def test_state_missing_full_atom_rows_or_required_roles_is_an_error():
    ref = reference()
    with pytest.raises(MetricDataError):
        ref.evaluate_states(dict(P0=LIGAND, final=LIGAND))
    with pytest.raises(MetricDataError):
        ref.evaluate_states(states(LIGAND[:3]))
    bad = LIGAND.clone()
    bad[2, 1] = float("nan")
    with pytest.raises(MetricDataError):
        ref.evaluate_states(states(bad))


def test_missing_final_preserves_start_labels_without_fabricating_endpoint():
    result = reference().evaluate_states(dict(P0=LIGAND, start=LIGAND + 1.))
    assert set(result["states"]) == {"P0", "start"}
    assert result["states"]["start"]["symmetry_aware_heavy_rmsd_angstrom"] > 1.
    assert result["final_state_status"] == "unavailable_not_supplied"
    assert result["comparison"] is None
    with pytest.raises(MetricDataError):
        reference().evaluate_states(dict(P0=LIGAND, start=LIGAND, final=None))


def test_explicit_heavy_subset_ignores_hydrogen_in_reference_label_only():
    full = torch.cat([LIGAND, torch.tensor([[100., 100., 100.]], dtype=DTYPE)])
    report = reference(prepared_atom_count=5).evaluate_states(states(full.tolist()))
    assert report["prepared_atom_count"] == 5
    assert report["states"]["final"]["symmetry_aware_heavy_rmsd_angstrom"] < 1e-15


def test_reference_and_report_are_isolated_from_caller_mutation():
    ligand, facts, maps = LIGAND.clone(), dict(FACTS), copy.deepcopy(MAPS)
    ref = reference(crystal_heavy_ccd_order=ligand, source_facts=facts,
                    prepared_to_ccd_mappings=maps)
    ligand += 50
    facts["synthetic_fixture"] = False
    maps[0][0] = 9
    report = ref.evaluate_states(states(LIGAND))
    assert report["source_facts"]["synthetic_fixture"] is True
    report["prepared_to_ccd_heavy_index_arrays"][0][0] = 9
    assert ref.evaluate_states(states(LIGAND))["prepared_to_ccd_heavy_index_arrays"][0][0] == 0


@pytest.mark.parametrize("changes", [dict(source_facts={}), dict(source_facts={"name": "toy"}),
                                    dict(source_facts={"source_sha256": "bad"}),
                                    dict(metric_policy_sha256="BAD")])
def test_source_and_policy_digests_are_required(changes):
    with pytest.raises(MetricDataError):
        reference(**changes)


def test_source_bound_callback_preserves_original_diagnostics_without_promoting_validity():
    observed = []
    points = LIGAND.clone()

    def diagnostic(name, coordinates):
        observed.append(name)
        coordinates[:] = 100
        return {"original_policy_pass": True, "improper_deviation_degrees": 2.5,
                "contact_count": 3}

    result = evaluate_structural_diagnostics(
        {"P0": points}, diagnostic, criteria_sha256="c" * 64,
        implementation_sha256="d" * 64)
    torch.testing.assert_close(points, LIGAND, rtol=0., atol=0.)
    assert observed == ["P0"]
    assert result["states"]["P0"]["improper_deviation_degrees"] == 2.5
    assert result["boundary"]["chemical_validity"] is None
    assert result["boundary"]["full_PoseBusters"] is False
    assert result["boundary"]["new_success_thresholds_added"] is False


def test_callback_nonfinite_output_or_missing_admission_is_not_null_success():
    with pytest.raises(MetricDataError):
        evaluate_structural_diagnostics(states(LIGAND), lambda *_: {"x": float("nan")},
                                        criteria_sha256="c" * 64,
                                        implementation_sha256="d" * 64)
    with pytest.raises(MetricDataError):
        evaluate_structural_diagnostics(states(LIGAND), None,
                                        criteria_sha256="c" * 64,
                                        implementation_sha256="d" * 64)


@pytest.mark.parametrize("output", [None, {}, [], True])
def test_missing_structural_observations_are_errors(output):
    with pytest.raises(MetricDataError):
        evaluate_structural_diagnostics(states(LIGAND), lambda *_: output,
                                        criteria_sha256="c" * 64,
                                        implementation_sha256="d" * 64)


def test_structural_callback_does_not_run_before_all_coordinates_are_valid():
    called = []
    with pytest.raises(MetricDataError):
        evaluate_structural_diagnostics({"P0": LIGAND, "final": LIGAND[:3]},
                                        lambda *_: called.append(True),
                                        criteria_sha256="c" * 64,
                                        implementation_sha256="d" * 64)
    assert called == []


def rings(points, groups=((0, 1, 2, 3),)):
    return ring_planarity(points, groups, source_sha256="c" * 64, policy_sha256=POLICY)


def contacts(ligand, receptor, radii=None, **changes):
    if radii is None:
        radii = {"ligand": [1.] * len(ligand), "receptor": [1.] * len(receptor)}
    return closest_contacts(ligand, receptor, radii, source_sha256="c" * 64,
                            policy_sha256=POLICY, **changes)


def test_ring_plane_is_rigid_frame_invariant_and_out_of_plane_is_continuous():
    square = torch.tensor([[-1., -1., 0.], [1., -1., 0.], [1., 1., 0.],
                           [-1., 1., 0.]], dtype=DTYPE)
    assert rings(square)["groups"][0]["maximum_plane_distance_angstrom"] == 0.
    puckered = square.clone()
    puckered[3, 2] = 1.
    row = rings(puckered)["groups"][0]
    moved = rings(puckered @ ROTATION + TRANSLATION)["groups"][0]
    assert row["maximum_plane_distance_angstrom"] > .1
    assert row["rms_plane_distance_angstrom"] > 0.
    assert moved["maximum_plane_distance_angstrom"] == pytest.approx(
        row["maximum_plane_distance_angstrom"], abs=3e-15)
    assert moved["rms_plane_distance_angstrom"] == pytest.approx(
        row["rms_plane_distance_angstrom"], abs=3e-15)
    assert rings(puckered)["boundary"]["chemical_validity"] is None
    assert rings(puckered)["source_diagnostic_threshold_angstrom"] == .1


@pytest.mark.parametrize("groups", [None, [[0, 0, 1]], [[0, 1, 9]], [[0, 1]],
                                   [[True, 1, 2]], [[0, 1, 2], [2, 0, 1]]])
def test_invalid_or_duplicate_admitted_ring_groups_are_errors(groups):
    with pytest.raises(MetricDataError):
        rings(CA, groups)


def test_empty_ring_admission_is_explicitly_not_applicable_not_a_validity_pass():
    result = rings(CA, [])
    assert result["status"] == "not_applicable_no_admitted_groups"
    assert result["group_count"] == 0
    assert result["boundary"]["chemical_validity"] is None
    with pytest.raises(MetricDataError, match="degenerate ring"):
        rings([[0., 0., 0.], [1., 0., 0.], [2., 0., 0.]], [[0, 1, 2]])


def test_contact_counts_use_every_pair_before_top_k_and_thresholds_are_strict():
    ligand = [[0., 0., 0.], [10., 0., 0.]]
    receptor = [[1., 0., 0.], [1.6, 0., 0.], [3., 0., 0.]]
    result = contacts(ligand, receptor, max_contact_rows=1)
    assert result["all_pair_denominator"] == 6
    assert result["all_pair_counts_below_ratio"] == {"0.8": 1, "0.85": 2, "0.9": 2}
    assert result["all_pairs_below_selected_ratio"] == 2
    assert result["minimum_vdw_ratio"] == .5
    assert len(result["nearby_contact_rows"]) == 1
    assert result["nearby_contact_rows_truncated"] is True
    assert result["pair_counts_are_complete"] is True
    assert result["boundary"]["chemical_validity"] is None
    no_rows = contacts(ligand, receptor, max_contact_rows=0)
    assert no_rows["all_pair_counts_below_ratio"] == result["all_pair_counts_below_ratio"]
    assert no_rows["nearby_contact_rows"] == []


def test_contact_closest_pair_preserves_negative_overlap_without_fabricated_clash():
    result = contacts([[0., 0., 0.]], [[3., 0., 0.]])
    assert result["closest_pair"]["signed_overlap_angstrom"] == -1.
    assert result["minimum_vdw_ratio"] == 1.5
    assert result["all_pairs_below_selected_ratio"] == 0
    assert result["nearby_contact_rows"] == []


def test_contact_block_boundaries_preserve_denominator_and_deterministic_ties():
    ligand = torch.zeros((129, 3), dtype=DTYPE)
    receptor = torch.zeros((257, 3), dtype=DTYPE)
    receptor[:, 0] = 1.
    result = contacts(ligand, receptor, max_contact_rows=2)
    assert result["all_pair_denominator"] == 129 * 257
    assert result["all_pair_counts_below_ratio"] == {
        str(t): 129 * 257 for t in (.8, .85, .9)}
    assert [(r["ligand_heavy_order_index"], r["receptor_heavy_order_index"])
            for r in result["nearby_contact_rows"]] == [(0, 0), (0, 1)]


@pytest.mark.parametrize("radius", [0., -1., float("nan"), float("inf"), True])
def test_nonpositive_nonfinite_or_boolean_vdw_radii_are_errors(radius):
    with pytest.raises(MetricDataError):
        contacts([[0., 0., 0.]], [[1., 0., 0.]],
                 {"ligand": [radius], "receptor": [1.]})


@pytest.mark.parametrize("radii", [{"ligand": [], "receptor": [1.]},
                                  {"sigma_angstrom": [1.]},
                                  {"ligand": [1.], "receptor": [1., 1.]},
                                  {"ligand": torch.ones(1), "receptor": [1.]}])
def test_radii_coverage_and_semantic_field_misuse_are_errors(radii):
    with pytest.raises(MetricDataError):
        contacts([[0., 0., 0.]], [[1., 0., 0.]], radii)


def test_contact_input_and_output_budgets_and_original_policy_bins_are_enforced():
    point = [[0., 0., 0.]]
    for kwargs in [dict(max_contact_rows=-1), dict(max_contact_rows=True),
                   dict(max_contact_rows=4097), dict(ratio_threshold=.7)]:
        with pytest.raises(MetricDataError):
            contacts(point, point, **kwargs)
    with pytest.raises(MetricDataError, match="budget"):
        contacts(point * 257, point)
    with pytest.raises(MetricDataError, match="budget"):
        contacts(point, point * 8193)


def test_contact_nonfinite_intermediate_arithmetic_is_not_a_zero_ratio_label():
    with pytest.raises(MetricDataError):
        contacts([[1.e308, 0., 0.]], [[-1.e308, 0., 0.]])
    with pytest.raises(MetricDataError):
        contacts([[0., 0., 0.]], [[1., 0., 0.]],
                 {"ligand": [1.e308], "receptor": [1.e308]})

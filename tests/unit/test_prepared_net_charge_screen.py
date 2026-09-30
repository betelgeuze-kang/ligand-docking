"""The portable charge decision must bind its profile and named source roles."""

from copy import deepcopy

import pytest

from betelgeuze_product.prepared_net_charge_screen import ligand_net_charge_screen


SDF_HASH = "a" * 64
ITP_HASH = "b" * 64
TOPOLOGY_HASH = "c" * 64
COORDINATE_HASH = "d" * 64


def _prepared_report(profile):
    source_roles = (("parent_ligand_sdf", "parent_ligand_itp")
                    if profile == "prepared_gromacs_coordinate_array_v1"
                    else ("ligand_sdf", "ligand_itp"))
    atom = {
        "index": 0, "formal_charge": 1,
        "partial_charge_e": {"$float_hex": "0x0.0p+0"},
        "metadata": {"prepared_gromacs_source": {
            "formal_charge_annotation_status": "sdf_v2000_encoded_formal_charge_not_measurement",
            "source_row": {"tokens": ["1", "x", "x", "x", "x", "x", "0.0"]},
        }},
    }
    provenance = {
        "schema_version": profile,
        "sources": {
            source_roles[0]: {"sha256": SDF_HASH},
            source_roles[1]: {"sha256": ITP_HASH},
        },
        "ligand_source_net_charge_observation": {
            "selected_atom_count": 1,
            "sdf_encoded_formal_charge_sum_e": 1,
            "itp_printed_partial_charge_sum_e": "0.0",
            "itp_minus_sdf_charge_sum_e": "-1.0",
            "arithmetic_relation": "different_as_encoded",
            "diagnostic_unavailable_reason": None,
            "sdf_source_sha256": SDF_HASH,
            "itp_source_sha256": ITP_HASH,
        },
    }
    return {
        "preparation": {"preparation_provenance": provenance},
        "rows": [{"result": {"sources": {"ligand": {
            "system": {"system": {"topology": {"atoms": [atom]}}},
            "nonbonded_parameters": [{"charge_e": 0.0}],
        }}}}],
    }


@pytest.mark.parametrize("profile", [
    "prepared_gromacs_components_v1",
    "prepared_gromacs_components_v2",
    "prepared_gromacs_components_v3",
    "prepared_gromacs_coordinate_derivation_v1",
    "prepared_gromacs_coordinate_array_v1",
])
def test_prepared_profiles_require_hashes_for_named_ligand_roles(profile):
    report = _prepared_report(profile)
    assert ligand_net_charge_screen(report)["status"] == "different_integral_state_range"

    swapped = deepcopy(report)
    observation = swapped["preparation"]["preparation_provenance"][
        "ligand_source_net_charge_observation"]
    observation["sdf_source_sha256"] = ITP_HASH
    observation["itp_source_sha256"] = SDF_HASH
    with pytest.raises(ValueError, match="pose_report_ligand_charge_source_mismatch"):
        ligand_net_charge_screen(swapped)


def test_unknown_and_spoofed_compiled_profiles_cannot_skip_prepared_charge_screen():
    report = _prepared_report("prepared_gromacs_components_v1")
    provenance = report["preparation"]["preparation_provenance"]
    provenance["schema_version"] = "unknown_prepared_profile_v1"
    with pytest.raises(ValueError, match="pose_report_ligand_charge_source_mismatch"):
        ligand_net_charge_screen(report)

    provenance["schema_version"] = "compiled_gromacs_cross_particles_v1"
    provenance.pop("ligand_source_net_charge_observation")
    with pytest.raises(ValueError, match="pose_report_ligand_charge_source_mismatch"):
        ligand_net_charge_screen(report)

    provenance["sources"] = {
        "topology": {"sha256": TOPOLOGY_HASH},
        "coordinates": {"sha256": COORDINATE_HASH},
    }
    provenance["source_topology_sha256"] = TOPOLOGY_HASH
    provenance["formal_charge_observations_available"] = False
    with pytest.raises(ValueError, match="pose_report_ligand_charge_source_mismatch"):
        ligand_net_charge_screen(report)


@pytest.mark.parametrize("refined", [False, True])
def test_genuine_compiled_profile_retains_unassessed_ranking(tmp_path, refined):
    from tests.unit.test_compiled_gromacs_cross_input import _refined_request, _request
    from tools.product.score_prepared_cross_interactions import evaluate_request

    request = (_refined_request(tmp_path) if refined else _request(tmp_path))
    result = evaluate_request({
        "schema_version": "prepared_cross_interaction_request_v1",
        "cases": [{
            "case_id": "compiled", "prepared_input": request,
            "evaluation": {
                "pocket_center_angstrom": [4, 0, 0],
                "pocket_radius_angstrom": 5.0,
                "cutoff_angstrom": 10.0,
                "switch_start_angstrom": 8.0,
                "dielectric": 1.0,
                "screening_kappa_per_angstrom": 0.0,
            },
        }],
    })
    source_row = result["rows"][0]
    assert source_row["status"] == "evaluated"
    report = {
        "preparation": {"preparation_provenance": source_row["preparation_provenance"]},
        "rows": [{"result": source_row["result"]}],
    }
    screen = ligand_net_charge_screen(report)
    assert screen["status"] == "not_assessed_compiled_profile"
    assert screen["rank_eligible"] is True

from __future__ import annotations

import json
import math
from pathlib import Path
import stat

import numpy as np
import pytest

import betelgeuze_engine_v2.benchmark as benchmark
from betelgeuze_engine_v2.benchmark import (
    public_posebusters_sulfur_interaction_energy as interaction,
)


def _scf(total_energy: float, *, electrons: int) -> interaction._ScfResult:
    return interaction._ScfResult(
        total_energy_hartree=total_energy,
        dispersion_energy_hartree=-0.001,
        electron_count=electrons,
        cycle_count=8,
        atomic_orbital_count=64,
        integration_grid_point_count=1000,
    )


class _FakeRuntime:
    _energies_kcal = (-0.2, -1.2, -2.0, -1.5, -0.8, -0.1, -1.0)

    def __init__(self) -> None:
        payload = {
            "schema_id": interaction.POSEBUSTERS_SULFUR_INTERACTION_RUNTIME_SCHEMA_ID,
            "test_runtime": True,
        }
        self.identity = {
            **payload,
            "runtime_identity_sha256": interaction._canonical_sha256(payload),
        }
        self.calls = 0

    def run_counterpoise(
        self,
        acceptor_symbols: tuple[str, ...],
        acceptor_coordinates_angstrom: np.ndarray,
        probe_symbols: tuple[str, ...],
        probe_coordinates_angstrom: np.ndarray,
    ) -> interaction._CounterpoiseResult:
        assert acceptor_symbols.count("S") == 1
        assert probe_symbols == ("C", "O", "H", "H", "H", "H")
        assert acceptor_coordinates_angstrom.shape[1] == 3
        assert probe_coordinates_angstrom.shape == (6, 3)
        energy_kcal = self._energies_kcal[self.calls]
        self.calls += 1
        acceptor_energy = -100.0
        probe_energy = -50.0
        complex_energy = (
            acceptor_energy
            + probe_energy
            + energy_kcal / interaction._HARTREE_TO_KCAL_PER_MOL
        )
        return interaction._CounterpoiseResult(
            complex=_scf(complex_energy, electrons=50),
            acceptor_with_probe_ghost_basis=_scf(
                acceptor_energy,
                electrons=32,
            ),
            probe_with_acceptor_ghost_basis=_scf(
                probe_energy,
                electrons=18,
            ),
        )


class _FailingRuntime(_FakeRuntime):
    def run_counterpoise(
        self,
        acceptor_symbols: tuple[str, ...],
        acceptor_coordinates_angstrom: np.ndarray,
        probe_symbols: tuple[str, ...],
        probe_coordinates_angstrom: np.ndarray,
    ) -> interaction._CounterpoiseResult:
        raise RuntimeError("synthetic bounded failure")


class _ControlPreferredRuntime(_FakeRuntime):
    _energies_kcal = (-0.2, -1.2, -2.0, -1.5, -0.8, -0.1, -2.5)


def _protocol_row(
    case_id: str = "7CIJ_G0C",
) -> dict[str, object]:
    scope = interaction.POSEBUSTERS_SULFUR_INTERACTION_SCOPE[case_id]
    return {
        "schema_id": interaction.POSEBUSTERS_SULFUR_INTERACTION_CASE_SCHEMA_ID,
        "case_id": case_id,
        "status": "registered",
        "disposition_code": "neutral_thioether_oh_donor_interaction_model",
        "environment": scope["environment"],
        "target_sulfur": {
            "meeko_ad4_atom_type": "SA",
            "openbabel_ad4_atom_type": "S",
            "source_smiles_atom_index": scope["source_smiles_atom_index"],
        },
        "geometry_binding": interaction._geometry_bindings(scope["model_id"]),
    }


def test_interaction_geometries_are_frozen_and_reconstruct_exactly() -> None:
    for case_id in interaction.POSEBUSTERS_SULFUR_INTERACTION_SCOPE_CASE_IDS:
        row = _protocol_row(case_id)
        binding = row["geometry_binding"]
        assert isinstance(binding, dict)
        assert binding["point_count"] == 7
        assert len(binding["points"]) == 7
        assert binding["selected_primary_axis"] in {
            "lone_pair_positive",
            "lone_pair_negative",
        }
        payloads = interaction._geometry_payloads(row)
        assert set(payloads) == {point["geometry_id"] for point in binding["points"]}
        assert [
            point["distance_angstrom_binary64_hex"] for point in binding["points"][:-1]
        ] == [value.hex() for value in interaction._SCAN_DISTANCES_ANGSTROM]
        assert binding["points"][-1]["orientation"] == ("positive_CSC_plane_normal")


def test_interaction_ad4_pair_formula_matches_frozen_source_constants() -> None:
    optimum_sa = interaction._ad4_pair_terms(2.5)
    assert float.fromhex(
        optimum_sa["raw_SA_HD_hbond_kcal_per_mol_binary64_hex"]
    ) == pytest.approx(-1.0, rel=0.0, abs=1.0e-14)
    assert float.fromhex(
        optimum_sa["weighted_SA_HD_hbond_kcal_per_mol_binary64_hex"]
    ) == pytest.approx(-0.1209, rel=0.0, abs=1.0e-14)

    optimum_s = interaction._ad4_pair_terms(3.0)
    assert float.fromhex(
        optimum_s["raw_S_HD_vdw_kcal_per_mol_binary64_hex"]
    ) == pytest.approx(-math.sqrt(0.2 * 0.02), rel=0.0, abs=1.0e-14)
    assert all(
        float.fromhex(value) == 0.0
        for key, value in interaction._ad4_pair_terms(8.0).items()
        if "kcal_per_mol" in key
    )


def test_interaction_case_reports_preregistered_gates_without_promotion() -> None:
    runtime = _FakeRuntime()
    row = interaction._observed_case(_protocol_row(), runtime)
    assert runtime.calls == 7
    assert row["status"] == "evaluated"
    assert row["qm_failure_point_count"] == 0
    assert row["case_acceptor_support"] is True
    metrics = row["metrics"]
    assert metrics["binding_gates"] == {
        "minimum_energy_gate": True,
        "far_referenced_well_depth_gate": True,
        "minimum_distance_gate": True,
    }
    assert float.fromhex(
        metrics["qm_profile"]["minimum_energy_kcal_per_mol_binary64_hex"]
    ) == pytest.approx(-2.0)
    assert (
        metrics["ad4_pair_profile"]["absolute_pair_magnitude_comparison_is_claimed"]
        is False
    )


def test_interaction_case_preserves_every_qm_failure() -> None:
    row = interaction._observed_case(_protocol_row(), _FailingRuntime())
    assert row["status"] == "qm_failure"
    assert row["qm_failure_point_count"] == 7
    assert row["case_acceptor_support"] is None
    assert len(row["point_rows"]) == 7
    assert all(point["status"] == "qm_failure" for point in row["point_rows"])
    assert all(len(point["error_message_sha256"]) == 64 for point in row["point_rows"])


def test_directionality_counterexample_does_not_promote_local_binding_gate() -> None:
    row = interaction._observed_case(_protocol_row(), _ControlPreferredRuntime())
    assert row["case_acceptor_support"] is True
    metrics = row["metrics"]
    assert float.fromhex(
        metrics["qm_profile"][
            "orientation_control_delta_kcal_per_mol_binary64_hex"
        ]
    ) == pytest.approx(-0.5)
    assert "orientation_control_delta_gate" not in metrics["binding_gates"]
    assert (
        interaction.POSEBUSTERS_SULFUR_INTERACTION_CONFIGURATION[
            "decision_contract"
        ]["chemical_acceptor_semantics_adjudicated"]
        is False
    )


def test_interaction_observation_summary_keeps_claims_closed() -> None:
    evaluated = []
    for case_id in interaction.POSEBUSTERS_SULFUR_INTERACTION_SCOPE_CASE_IDS:
        evaluated.append(
            interaction._observed_case(
                _protocol_row(case_id),
                _FakeRuntime(),
            )
        )
    abstentions = [
        {
            "schema_id": interaction.POSEBUSTERS_SULFUR_INTERACTION_CASE_SCHEMA_ID,
            "case_id": f"outside-{index:03d}",
            "status": "abstain_protocol_scope",
        }
        for index in range(305)
    ]
    runtime = _FakeRuntime().identity
    protocol = {
        "receipt_sha256": "1" * 64,
        "implementation_source_members": [],
        "implementation_source_sha256": "2" * 64,
    }
    receipt = interaction._observation_payload(
        observation_utc="2026-07-23T09:00:00Z",
        protocol=protocol,
        protocol_file_sha256="3" * 64,
        runtime_identity=runtime,
        case_rows=evaluated + abstentions,
    )
    assert receipt["all_scoped_cases_evaluated"] is True
    assert receipt["local_three_model_oh_acceptor_gate_pass"] is True
    assert receipt["scope_abstention_case_count"] == 305
    assert receipt["chemical_acceptor_semantics_adjudicated"] is False
    assert receipt["scientifically_validated"] is False
    assert receipt["product_promotion_allowed"] is False
    assert receipt["claim_safe"] is False


def test_interaction_receipt_write_is_private_and_no_overwrite(
    tmp_path: Path,
) -> None:
    output = tmp_path / "receipt.json"
    payload = {"schema_id": "test", "receipt_sha256": "0" * 64}
    interaction._write_private_no_overwrite(payload, output)
    assert stat.S_IMODE(output.stat().st_mode) == 0o600
    assert json.loads(output.read_text()) == payload
    with pytest.raises(
        interaction.PoseBustersSulfurInteractionError,
        match="already exists",
    ):
        interaction._write_private_no_overwrite(payload, output)


def test_interaction_cli_and_decision_contract_are_explicit() -> None:
    help_text = interaction._parser().format_help()
    assert "neutral-thioether" in help_text
    assert "interaction-energy" in help_text
    assert "register" in help_text
    assert "verify-protocol" in help_text
    assert "observe" in help_text
    assert "verify-observation" in help_text
    decision = interaction.POSEBUSTERS_SULFUR_INTERACTION_CONFIGURATION[
        "decision_contract"
    ]
    assert decision["binding_minimum_at_most_kcal_per_mol"] == float(-1.0).hex()
    assert decision["product_promotion_allowed"] is False
    assert decision["chemical_acceptor_semantics_adjudicated"] is False


def test_interaction_contract_is_exported_from_benchmark_package() -> None:
    required = {
        "POSEBUSTERS_SULFUR_INTERACTION_CONFIGURATION_SHA256",
        "POSEBUSTERS_SULFUR_INTERACTION_PROTOCOL_SCHEMA_ID",
        "POSEBUSTERS_SULFUR_INTERACTION_OBSERVATION_SCHEMA_ID",
        "PoseBustersSulfurInteractionError",
        "materialize_posebusters_sulfur_interaction_protocol",
        "materialize_posebusters_sulfur_interaction_observation",
        "verify_posebusters_sulfur_interaction_protocol",
        "verify_posebusters_sulfur_interaction_observation",
    }
    assert required <= set(benchmark.__all__)
    for name in required:
        assert getattr(benchmark, name) is getattr(interaction, name)

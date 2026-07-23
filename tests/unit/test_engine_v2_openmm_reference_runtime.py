from __future__ import annotations

from copy import deepcopy
import hashlib
import json

import pytest


pytest.importorskip("openmm")
torch = pytest.importorskip("torch")

from betelgeuze_engine_v2.geometry import (  # noqa: E402
    RadiusGraphConfig,
    build_compact_radius_graph,
)
from betelgeuze_engine_v2.molecular import (  # noqa: E402
    AllAtomSystem,
    Atom,
    Bond,
    Chain,
    Residue,
    StructureProvenance,
    canonical_topology_sha256,
)
from betelgeuze_engine_v2.offline import (  # noqa: E402
    openmm_reference_receipts as receipt_module,
)
from betelgeuze_engine_v2.offline.openmm_reference_oracle import (  # noqa: E402
    OPENMM_REFERENCE_REQUIRED_PLATFORM,
    OpenMMReferenceOfflineOracleError,
    OpenMMReferenceSession,
    observe_openmm_reference_runtime_identity,
    require_openmm_reference_runtime_identity_document,
)
from betelgeuze_engine_v2.offline.openmm_reference_receipts import (  # noqa: E402
    OpenMMReferenceReceiptError,
    build_openmm_reference_energy_force_receipt,
    build_openmm_reference_minimization_trace_receipt,
    require_openmm_reference_energy_force_receipt,
    require_openmm_reference_minimization_trace_receipt,
)
from betelgeuze_engine_v2.physics.reference_forcefield_v2 import (  # noqa: E402
    HarmonicOutOfPlaneImproperParameter,
    ReferenceForceFieldV2Parameters,
    evaluate_reference_force_field_v2,
)
from betelgeuze_engine_v2.physics.reference_minimization_validation_materializer import (  # noqa: E402
    materialize_frozen_cpu_minimization_validation_case,
)
from betelgeuze_engine_v2.physics.reference_minimization_validation_protocol import (  # noqa: E402
    cpu_minimization_validation_protocol_document,
)
from betelgeuze_engine_v2.physics.reference_minimization_validation_runner import (  # noqa: E402
    _empty_coordinate_trace,
    _operational_coordinate_trace,
    _run_operational,
)
from betelgeuze_engine_v2.physics.reference_parameters import (  # noqa: E402
    AtomNonbondedParameter,
    HarmonicAngleParameter,
    HarmonicBondParameter,
    ReferenceApplicabilityDomain,
    ReferenceForceFieldParameters,
)


def _canonical_sha256(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("ascii")
    ).hexdigest()


def _refresh_digest(value: dict[str, object], field: str) -> None:
    projection = {key: item for key, item in value.items() if key != field}
    value[field] = _canonical_sha256(projection)


@pytest.fixture(scope="module")
def runtime_identity() -> dict[str, object]:
    return observe_openmm_reference_runtime_identity()


@pytest.fixture(scope="module")
def energy_force_receipt(runtime_identity: dict[str, object]) -> dict[str, object]:
    return build_openmm_reference_energy_force_receipt(
        observed_at_utc="2026-07-22T00:00:00Z",
        runtime_identity=runtime_identity,
    )


@pytest.fixture(scope="module")
def operational_traces() -> tuple[object, ...]:
    traces = []
    protocol = cpu_minimization_validation_protocol_document()
    for row in protocol["case_manifest"]["cases"]:
        case = materialize_frozen_cpu_minimization_validation_case(row["case_id"])
        if row["expected_outcome"] == "pass":
            traces.append(_operational_coordinate_trace(case, _run_operational(case)))
        else:
            traces.append(
                _empty_coordinate_trace(
                    case_id=case.case_id,
                    trace_source="operational",
                    atom_count=case.system.atom_count,
                    expected_fail_closed=True,
                )
            )
    return tuple(traces)


@pytest.fixture(scope="module")
def minimization_trace_receipt(
    runtime_identity: dict[str, object],
    operational_traces: tuple[object, ...],
) -> dict[str, object]:
    return build_openmm_reference_minimization_trace_receipt(
        operational_traces,
        observed_at_utc="2026-07-22T00:00:00Z",
        runtime_identity=runtime_identity,
    )


def test_runtime_identity_binds_reference_distribution_and_native_binary(
    runtime_identity: dict[str, object],
) -> None:
    observed = require_openmm_reference_runtime_identity_document(
        runtime_identity,
        reobserve=True,
    )

    assert observed["distribution"]["distribution_version"] == "8.4.0.post2"
    assert observed["native_build"]["full_version"] == "8.4.0.dev-4768436"
    assert observed["native_build"]["git_revision"] == (
        "47684368dbbe4185d068be77d32a962059cfc37c"
    )
    assert observed["native_build"]["native_extension"]["path"].startswith(
        "openmm/_openmm."
    )
    assert observed["platform"]["selected_name"] == OPENMM_REFERENCE_REQUIRED_PLATFORM
    assert observed["platform"]["cpu_substitution_allowed"] is False
    assert observed["path_values_disclosed"] is False


@pytest.mark.parametrize(
    "mutation",
    (
        "version",
        "platform",
        "native_binary",
        "distribution_name",
        "path_disclosure",
        "cpu_substitution",
    ),
)
def test_runtime_identity_rejects_version_platform_and_binary_tampering(
    runtime_identity: dict[str, object],
    mutation: str,
) -> None:
    observed = deepcopy(runtime_identity)
    if mutation == "version":
        observed["native_build"]["full_version"] = "8.4.1"
    elif mutation == "platform":
        observed["platform"]["selected_name"] = "CPU"
    elif mutation == "native_binary":
        observed["native_build"]["native_extension"]["sha256"] = "0" * 64
    elif mutation == "distribution_name":
        observed["distribution"]["distribution_name"] = "openmm"
        _refresh_digest(observed["distribution"], "manifest_sha256")
    elif mutation == "path_disclosure":
        observed["path_values_disclosed"] = True
    else:
        observed["platform"]["cpu_substitution_allowed"] = True
    _refresh_digest(observed, "runtime_identity_sha256")

    with pytest.raises(OpenMMReferenceOfflineOracleError):
        require_openmm_reference_runtime_identity_document(observed)


@pytest.mark.parametrize("mutation", ("runtime", "source"))
def test_observation_rejects_runtime_or_source_pre_post_drift(
    runtime_identity: dict[str, object],
    monkeypatch: pytest.MonkeyPatch,
    mutation: str,
) -> None:
    source_identity = receipt_module._source_identity()
    monkeypatch.setattr(
        receipt_module,
        "observe_openmm_reference_runtime_identity",
        lambda: deepcopy(runtime_identity),
    )
    if mutation == "runtime":
        drifted_runtime = deepcopy(runtime_identity)
        drifted_runtime["runtime_identity_sha256"] = "0" * 64
        monkeypatch.setattr(
            receipt_module,
            "observe_openmm_reference_runtime_identity",
            lambda: drifted_runtime,
        )
    else:
        drifted_source = dict(source_identity)
        drifted_source["source_identity_sha256"] = "0" * 64
        monkeypatch.setattr(
            receipt_module,
            "_source_identity",
            lambda: drifted_source,
        )

    with pytest.raises(OpenMMReferenceReceiptError):
        receipt_module._require_observation_identity_unchanged(
            runtime_identity=runtime_identity,
            source_identity=source_identity,
        )


def test_all_47_mapped_variants_pass_and_12_failures_remain_na(
    energy_force_receipt: dict[str, object],
) -> None:
    receipt = require_openmm_reference_energy_force_receipt(
        energy_force_receipt,
        reexecute=True,
    )

    assert receipt["status"] == "accepted_offline_reference_agreement"
    assert receipt["summary"]["evaluated_variant_count"] == 47
    assert receipt["summary"]["not_applicable_engine_contract_variant_count"] == 12
    assert receipt["summary"]["skipped_variant_count"] == 0
    assert (
        receipt["summary"]["engine_openmm"]["energy_error_max_kcal_per_mol"] <= 1.0e-10
    )
    assert (
        receipt["summary"]["engine_openmm"]["force_error_max_kcal_per_mol_angstrom"]
        <= 1.0e-8
    )
    assert (
        receipt["summary"]["independent_analytic_openmm"][
            "energy_error_rms_kcal_per_mol"
        ]
        <= 1.0e-10
    )
    assert (
        receipt["summary"]["independent_analytic_openmm"][
            "force_error_rms_kcal_per_mol_angstrom"
        ]
        <= 1.0e-8
    )
    assert receipt["production_protocol_execution"] is False
    assert receipt["scientifically_validated"] is False


@pytest.mark.parametrize(
    "mutation",
    (
        "missing_variant",
        "failure_disposition",
        "nested_output",
        "summary_metric",
        "source_identity",
        "receipt_flag",
    ),
)
def test_energy_force_receipt_rejects_coverage_and_disposition_tampering(
    energy_force_receipt: dict[str, object],
    mutation: str,
) -> None:
    receipt = deepcopy(energy_force_receipt)
    if mutation == "missing_variant":
        receipt["cases"][0]["variants"].pop()
    elif mutation == "failure_disposition":
        failure = next(
            variant
            for case in receipt["cases"]
            for variant in case["variants"]
            if variant["disposition"] == "not_applicable_engine_contract"
        )
        failure["disposition"] = "evaluated_openmm_reference"
    elif mutation == "nested_output":
        evaluated = next(
            variant
            for case in receipt["cases"]
            for variant in case["variants"]
            if variant["disposition"] == "evaluated_openmm_reference"
        )
        evaluated["openmm_reference_evaluation"]["total_energy"]["value"] += 1.0
    elif mutation == "summary_metric":
        receipt["summary"]["engine_openmm"]["energy_error_max_kcal_per_mol"] += 1.0
    elif mutation == "source_identity":
        receipt["source_identity"]["openmm_reference_oracle_source_sha256"] = "0" * 64
    else:
        receipt["signed_result_receipt"] = True
    _refresh_digest(receipt, "receipt_sha256")

    with pytest.raises(OpenMMReferenceReceiptError):
        require_openmm_reference_energy_force_receipt(receipt)


def test_all_14_trace_rows_and_572_supported_coordinates_are_retained(
    minimization_trace_receipt: dict[str, object],
) -> None:
    receipt = require_openmm_reference_minimization_trace_receipt(
        minimization_trace_receipt,
        reexecute=True,
    )

    assert receipt["status"] == "accepted_offline_reference_trace_agreement"
    assert receipt["summary"]["case_count"] == 14
    assert receipt["summary"]["evaluated_case_count"] == 8
    assert receipt["summary"]["not_applicable_engine_contract_case_count"] == 6
    assert receipt["summary"]["evaluated_trace_step_count"] == 572
    assert receipt["summary"]["fixed_born_trace_step_count"] == 246
    assert (
        receipt["summary"]["fixed_born_self_pair_components_recorded_separately"]
        is True
    )
    assert receipt["summary"]["energy_error_max_kcal_per_mol"] <= 1.0e-10
    assert receipt["summary"]["force_error_max_kcal_per_mol_angstrom"] <= 1.0e-8
    assert (
        receipt["summary"][
            "source_trace_engine_recomputed_energy_error_max_kcal_per_mol"
        ]
        == 0.0
    )
    assert receipt["native_minimization_endpoint_executed"] is False
    assert receipt["engine_trace_equivalence_to_openmm_lbfgs_claimed"] is False
    fixed_born_step = next(
        step
        for case in receipt["cases"]
        for step in case["steps"]
        if case["case_id"] == "v2_fixed_born_constrained_energy_decrease"
    )
    component_names = {
        row["name"]
        for row in fixed_born_step["openmm_reference_evaluation"]["component_energies"]
    }
    assert {"fixed_born_self_polar", "fixed_born_pair_polar"} <= component_names


@pytest.mark.parametrize(
    "mutation",
    (
        "failure_disposition",
        "nested_output",
        "summary_metric",
        "step_identity",
        "boundary_flag",
    ),
)
def test_minimization_trace_receipt_rejects_nested_tampering(
    minimization_trace_receipt: dict[str, object],
    mutation: str,
) -> None:
    receipt = deepcopy(minimization_trace_receipt)
    if mutation == "failure_disposition":
        failure = next(
            row
            for row in receipt["cases"]
            if row["disposition"] == "not_applicable_engine_contract"
        )
        failure["disposition"] = "evaluated_openmm_reference_trace_coordinates"
    elif mutation == "nested_output":
        evaluated = next(
            row
            for row in receipt["cases"]
            if row["disposition"] == "evaluated_openmm_reference_trace_coordinates"
        )
        evaluated["steps"][0]["engine_evaluation"]["forces"]["values"][0][0] += 1.0
    elif mutation == "summary_metric":
        receipt["summary"]["force_error_rms_kcal_per_mol_angstrom"] += 1.0
    elif mutation == "step_identity":
        evaluated = next(
            row
            for row in receipt["cases"]
            if row["disposition"] == "evaluated_openmm_reference_trace_coordinates"
        )
        evaluated["steps"][0]["source_step_identity_sha256"] = "0" * 64
    else:
        receipt["engine_trace_equivalence_to_openmm_lbfgs_claimed"] = True
    _refresh_digest(receipt, "receipt_sha256")

    with pytest.raises(OpenMMReferenceReceiptError):
        require_openmm_reference_minimization_trace_receipt(receipt)


def _star_system() -> AllAtomSystem:
    return AllAtomSystem(
        system_id="openmm-improper-star",
        atoms=tuple(
            Atom(
                index=index,
                name=f"C{index}",
                element="C",
                atomic_number=6,
                residue_index=0,
            )
            for index in range(4)
        ),
        bonds=tuple(
            Bond(index=index, atom_i=0, atom_j=index + 1, source="unit")
            for index in range(3)
        ),
        residues=(
            Residue(
                index=0,
                name="LIG",
                chain_index=0,
                sequence_number=1,
                atom_indices=(0, 1, 2, 3),
                entity_type="non_polymer",
                hetero=True,
            ),
        ),
        chains=(Chain(index=0, chain_id="L", residue_indices=(0,)),),
        coordinates=torch.tensor(
            [[[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.4, 0.3, 0.2]]],
            dtype=torch.float64,
        ),
        provenance=StructureProvenance(
            source_format="unit",
            source_id="openmm-improper-star",
            source_sha256="a" * 64,
            parser_name="unit",
            parser_version="1",
            operations=("unit_fixture",),
            source_digest_verified=True,
            transformation_chain_verified=True,
        ),
    )


def _star_parameters(
    system: AllAtomSystem,
) -> tuple[ReferenceForceFieldParameters, ReferenceForceFieldV2Parameters]:
    coordinates = system.coordinates[0]
    vectors = tuple(coordinates[index] - coordinates[0] for index in (1, 2, 3))

    def angle(first: torch.Tensor, second: torch.Tensor) -> float:
        return float(
            torch.acos(
                torch.dot(first, second)
                / (torch.linalg.vector_norm(first) * torch.linalg.vector_norm(second))
            ).item()
        )

    base = ReferenceForceFieldParameters(
        parameter_set_id="openmm-improper-star",
        parameter_set_version="1.0.0",
        topology_sha256=canonical_topology_sha256(system),
        atom_parameters=tuple(
            AtomNonbondedParameter(index, 1.0, 0.0, 0.0) for index in range(4)
        ),
        bonds=tuple(
            HarmonicBondParameter(
                0,
                index,
                float(torch.linalg.vector_norm(vectors[index - 1]).item()),
                100.0,
            )
            for index in (1, 2, 3)
        ),
        angles=(
            HarmonicAngleParameter(1, 0, 2, angle(vectors[0], vectors[1]), 30.0),
            HarmonicAngleParameter(1, 0, 3, angle(vectors[0], vectors[2]), 30.0),
            HarmonicAngleParameter(2, 0, 3, angle(vectors[1], vectors[2]), 30.0),
        ),
        excluded_pairs=((0, 1), (0, 2), (0, 3), (1, 2), (1, 3), (2, 3)),
        cutoff_angstrom=4.0,
        switch_start_angstrom=3.0,
        applicability_domain=ReferenceApplicabilityDomain(max_atoms=8),
    )
    v2 = ReferenceForceFieldV2Parameters(
        base_parameters=base,
        impropers=(HarmonicOutOfPlaneImproperParameter(0, 1, 2, 3, 0.0, 20.0),),
    )
    return base, v2


def test_ordered_star_improper_custom_force_matches_engine_energy_and_force() -> None:
    system = _star_system()
    base, v2 = _star_parameters(system)
    neighbors = build_compact_radius_graph(
        system.coordinates,
        RadiusGraphConfig(
            cutoff_angstrom=4.0,
            max_neighbors=8,
            max_atoms_per_cell=16,
        ),
    )
    engine = evaluate_reference_force_field_v2(system, neighbors, v2)
    with OpenMMReferenceSession(system, base, v2_parameters=v2) as session:
        observed = session.evaluate()

    assert dict(observed.component_energies_kcal_per_mol)[
        "harmonic_out_of_plane_improper"
    ] == pytest.approx(
        float(engine.component_energies["harmonic_out_of_plane_improper"][0]),
        abs=1.0e-10,
    )
    assert observed.total_energy_kcal_per_mol == pytest.approx(
        float(engine.term.energy[0]),
        abs=1.0e-10,
    )
    force_error = max(
        abs(
            observed.forces_kcal_per_mol_angstrom[atom][axis]
            - float(engine.term.forces[0, atom, axis])
        )
        for atom in range(system.atom_count)
        for axis in range(3)
    )
    assert force_error <= 1.0e-8


def test_native_openmm_minimization_is_a_separate_endpoint_only() -> None:
    case = materialize_frozen_cpu_minimization_validation_case(
        "v1_bonded_energy_decrease"
    )
    with OpenMMReferenceSession(case.system, case.base_parameters) as session:
        endpoint = session.native_minimize_endpoint(
            tolerance_kcal_per_mol_angstrom=1.0e-6,
            maximum_iterations=200,
            constraint_tolerance_relative=1.0e-10,
        )

    assert endpoint["algorithm"] == "OpenMM LocalEnergyMinimizer L-BFGS"
    assert endpoint["constraint_tolerance_relative"] == 1.0e-10
    assert endpoint["final_context_constraint_projection_applied"] is True
    assert (
        endpoint["final_evaluation"]["total_energy"]["value"]
        <= endpoint["initial_evaluation"]["total_energy"]["value"]
    )
    assert endpoint["engine_trace_equivalence_claimed"] is False
    assert endpoint["checkpoint_restart_equality_claimed"] is False

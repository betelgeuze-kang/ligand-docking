from __future__ import annotations

import hashlib
import inspect
from pathlib import Path

import pytest


Chem = pytest.importorskip("rdkit.Chem")
AllChem = pytest.importorskip("rdkit.Chem.AllChem")

from benchmarks.docking_search_v2.protocol import (  # noqa: E402
    EXTERNAL_POSEBUSTERS_FACT_ORIGIN,
    EXTERNAL_RMSD_FACT_ORIGIN,
    FROZEN_CASES,
    PREPARATION_FAILURE_CASE_ID,
    PREPARATION_FAILURE_CODE,
)
from tools import run_docking_search_v2_development_cohort as runner  # noqa: E402


def _sdf() -> tuple[bytes, tuple[tuple[float, float, float], ...]]:
    molecule = Chem.AddHs(Chem.MolFromSmiles("CCO"))
    parameters = AllChem.ETKDGv3()
    parameters.randomSeed = 41
    parameters.numThreads = 1
    assert AllChem.EmbedMolecule(molecule, parameters) == 0
    block = Chem.MolToMolBlock(molecule, includeStereo=True, kekulize=True)
    coordinates = tuple(
        tuple(float(value) for value in molecule.GetConformer().GetAtomPosition(index))
        for index in range(molecule.GetNumAtoms())
    )
    return (block.rstrip("\n") + "\n$$$$\n").encode("ascii"), coordinates


def _native_response(coordinates) -> runner.SearchResponse:
    candidates = []
    for slot in range(64):
        shifted = tuple((row[0] + slot * 1.0e-7, row[1], row[2]) for row in coordinates)
        top_k = slot < 10
        native_row = {
            "slot_index": slot,
            "status": "top_k" if top_k else "cluster_representative",
            "reason": None if top_k else "top_k_budget",
            "coordinates_angstrom": [list(row) for row in shifted],
            "final_rank": slot + 1 if top_k else None,
            "energy_kcal_per_mol": float(slot),
            "detailed_score": float(slot),
            "coarse_score": float(slot),
        }
        candidates.append(
            runner.NativeCandidate(
                slot_index=slot,
                status=native_row["status"],
                reason=native_row["reason"],
                coordinates_angstrom=shifted,
                final_rank=native_row["final_rank"],
                energy_kcal_per_mol=float(slot),
                detailed_score=float(slot),
                coarse_score=float(slot),
                native_row=native_row,
            )
        )
    return runner.SearchResponse(
        candidates=tuple(candidates),
        search_implementation_sha256="a" * 64,
        native_extension_sha256="b" * 64,
        search_config_sha256="c" * 64,
        native_search_receipt={"schema_id": "fixture", "receipt_sha256": "d" * 64},
        native_backend_receipt={"receipt_sha256": "f" * 64},
        native_result_sha256="e" * 64,
    )


def _evaluation_batch() -> runner.EvaluationBatch:
    columns = ("rmsd", *runner._CHECK_IDS, "diagnostic_scalar")
    return runner.EvaluationBatch(
        report_columns=columns,
        observations=tuple(
            runner.EvaluationObservation(
                slot_index=slot,
                full_report_facts={
                    "rmsd": float(slot) / 10.0,
                    **{check_id: slot % 2 == 0 for check_id in runner._CHECK_IDS},
                    "diagnostic_scalar": slot,
                },
            )
            for slot in range(64)
        ),
        evaluator_identity={
            "evaluator_id": "posebusters/0.3.1/redock/full_report",
            "posebusters_version": "0.3.1",
            "rmsd_method_id": "posebusters_symmetry_aware_rmsd/0.3.1",
            "full_report": True,
            "implementation_source_sha256": "f" * 64,
            "external_solver_used_for_generation": False,
        },
    )


def test_generation_request_exposes_only_declared_inputs() -> None:
    pocket = runner.SearchPocket(
        center_angstrom=(1.0, 2.0, 3.0),
        radius_angstrom=8.0,
        policy_id=runner.KNOWN_POCKET_POLICY_ID,
        receipt_sha256="1" * 64,
    )
    request, receipt = runner._generation_request(
        case_id="5SD5_HWI",
        case_seed=17,
        source_receipt_sha256="2" * 64,
        payloads={
            "receptor": b"protein",
            "reference": b"reference-must-not-cross-boundary",
            "native": b"native-must-not-cross-boundary",
            "seed": b"start",
        },
        pocket=pocket,
    )

    assert request.candidate_slots == 64
    assert request.receptor_pdb == b"protein"
    assert request.ligand_start_sdf == b"start"
    assert not hasattr(request, "native_sdf")
    assert not hasattr(request, "reference_sdf")
    assert not hasattr(request, "rmsd")
    assert not hasattr(request, "posebusters")
    assert receipt["reference_pose_bytes_exposed_to_search"] is False


def test_known_pocket_is_heavy_atom_derived_and_receipted() -> None:
    sdf, _ = _sdf()
    pocket, receipt = runner.derive_predeclared_known_pocket(
        sdf,
        case_id="5SD5_HWI",
        native_artifact_sha256=hashlib.sha256(sdf).hexdigest(),
        runner_source_sha256="a" * 64,
    )

    molecule = next(
        mol
        for mol in Chem.ForwardSDMolSupplier(
            __import__("io").BytesIO(sdf), removeHs=False
        )
        if mol
    )
    heavy = [
        molecule.GetConformer().GetAtomPosition(atom.GetIdx())
        for atom in molecule.GetAtoms()
        if atom.GetAtomicNum() > 1
    ]
    expected = tuple(
        sum(point[axis] for point in heavy) / len(heavy) for axis in range(3)
    )
    assert pocket.center_angstrom == pytest.approx(expected)
    assert pocket.radius_angstrom >= 6.0
    assert receipt["derived_before_search"] is True
    assert receipt["receipt_sha256"] == pocket.receipt_sha256


def test_exact_64_sdf_coordinate_hashes_and_full_external_facts_are_bound() -> None:
    sdf, coordinates = _sdf()
    artifacts, search_receipt, rank_receipt = runner._seal_candidate_artifacts(
        case_id="5SD5_HWI",
        ligand_start_sdf=sdf,
        generation_input_receipt_sha256="1" * 64,
        known_pocket_receipt_sha256="2" * 64,
        response=_native_response(coordinates),
    )
    protocol_rows, evaluation = runner._bind_evaluation(
        case_id="5SD5_HWI",
        artifacts=artifacts,
        batch=_evaluation_batch(),
    )
    for row in protocol_rows:
        row["candidate_search_receipt_sha256"] = search_receipt["receipt_sha256"]

    assert len(artifacts) == len(protocol_rows) == 64
    assert [row.score_rank for row in artifacts] == list(range(1, 65))
    assert rank_receipt["oracle_fields_used"] == []
    assert rank_receipt["receipt_sha256"] == runner._sha256_json(
        {key: value for key, value in rank_receipt.items() if key != "receipt_sha256"}
    )
    assert search_receipt["native_search_receipt"] == {
        "schema_id": "fixture",
        "receipt_sha256": "d" * 64,
    }
    assert all(
        artifact.proposal_artifact_sha256
        == hashlib.sha256(artifact.sdf_bytes).hexdigest()
        and artifact.coordinate_sha256
        == hashlib.sha256(artifact.coordinate_bytes).hexdigest()
        for artifact in artifacts
    )
    first = protocol_rows[0]
    assert first["rmsd_fact_origin"] == EXTERNAL_RMSD_FACT_ORIGIN
    assert first["posebusters_fact_origin"] == EXTERNAL_POSEBUSTERS_FACT_ORIGIN
    assert (
        first["rmsd_subject_proposal_artifact_sha256"]
        == first["proposal_artifact_sha256"]
    )
    assert first["posebusters_subject_coordinate_sha256"] == first["coordinate_sha256"]
    full = evaluation["candidate_facts"][0]["posebusters_fact"]
    assert full["full_report_facts"]["diagnostic_scalar"] == 0
    assert set(full["check_facts"]) == set(runner._CHECK_IDS)
    assert evaluation["receipt_sha256"] == runner._sha256_json(
        {key: value for key, value in evaluation.items() if key != "receipt_sha256"}
    )


def test_external_fact_drop_and_native_slot_drop_fail_closed() -> None:
    sdf, coordinates = _sdf()
    response = _native_response(coordinates)
    with pytest.raises(
        runner.CohortRunnerError, match="native_candidate_budget_mismatch"
    ):
        runner._seal_candidate_artifacts(
            case_id="5SD5_HWI",
            ligand_start_sdf=sdf,
            response=runner.SearchResponse(
                candidates=response.candidates[:-1],
                search_implementation_sha256=response.search_implementation_sha256,
                native_extension_sha256=response.native_extension_sha256,
                search_config_sha256=response.search_config_sha256,
                native_search_receipt=response.native_search_receipt,
                native_backend_receipt=response.native_backend_receipt,
                native_result_sha256=response.native_result_sha256,
            ),
            generation_input_receipt_sha256="1" * 64,
            known_pocket_receipt_sha256="2" * 64,
        )

    artifacts, _, _ = runner._seal_candidate_artifacts(
        case_id="5SD5_HWI",
        ligand_start_sdf=sdf,
        generation_input_receipt_sha256="1" * 64,
        known_pocket_receipt_sha256="2" * 64,
        response=response,
    )
    batch = _evaluation_batch()
    facts = dict(batch.observations[0].full_report_facts)
    facts.pop(runner._CHECK_IDS[0])
    tampered = runner.EvaluationBatch(
        report_columns=batch.report_columns,
        observations=(runner.EvaluationObservation(0, facts), *batch.observations[1:]),
        evaluator_identity=batch.evaluator_identity,
    )
    with pytest.raises(
        runner.CohortRunnerError, match="external_fact_columns_mismatch"
    ):
        runner._bind_evaluation(case_id="5SD5_HWI", artifacts=artifacts, batch=tampered)


def test_frozen_failure_and_all_nine_receipts_are_preserved() -> None:
    failures = {row.case_id: row.preparation_failure_code for row in FROZEN_CASES}
    assert failures[PREPARATION_FAILURE_CASE_ID] == PREPARATION_FAILURE_CODE
    assert len(FROZEN_CASES) == 9
    assert [row.source_receipt_sha256 for row in FROZEN_CASES] == [
        runner.frozen_public_redocking_materialization_receipt_sha256(row.case_id)
        for row in FROZEN_CASES
    ]


def test_cli_declares_archive_repo_and_exclusive_output_arguments() -> None:
    help_text = runner._parser().format_help()
    assert "--source-archive" in help_text
    assert "--repo-root" in help_text
    assert "--output-root" in help_text
    source = Path("tools/run_docking_search_v2_development_cohort.py").read_text()
    assert "subprocess" not in source
    assert "openmm" not in source.lower()
    assert "vina" not in source.lower()
    assert "gnina" not in source.lower()


def test_public_cohort_runner_has_no_adapter_or_evaluator_injection_surface() -> None:
    signature = inspect.signature(runner.run_development_cohort)
    assert tuple(signature.parameters) == ("source_archive",)
    with pytest.raises(TypeError, match="unexpected keyword argument"):
        runner.run_development_cohort(
            "/does/not/matter.zip",
            search_adapter=object(),  # type: ignore[call-arg]
        )
    with pytest.raises(TypeError, match="unexpected keyword argument"):
        runner.run_development_cohort(
            "/does/not/matter.zip",
            evaluator=object(),  # type: ignore[call-arg]
        )


def test_posebusters_diagnostic_missing_scalar_is_canonical() -> None:
    import pandas as pd

    assert runner._canonical_report_scalar(pd.NA) == {"missing_scalar": "pandas.NA"}

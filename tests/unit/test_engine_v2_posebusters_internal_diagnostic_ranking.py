from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from betelgeuze_engine_v2.benchmark import (
    public_posebusters_internal_diagnostic_ranking_evaluation as diagnostic,
)
from betelgeuze_engine_v2.docking.calibration import PoseRankingCalibrationRow


def _sha(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _atom(
    serial: int,
    *,
    atom_name: str,
    x: float,
    charge: float,
    atom_type: str,
) -> str:
    return (
        f"ATOM  {serial:5d} {atom_name:<4} UNL     1    "
        f"{x:8.3f}{1.0:8.3f}{2.0:8.3f}"
        f"  1.00  0.00    {charge:6.3f} {atom_type:<2}"
    )


def _prepared_ligand_with_g0() -> bytes:
    return (
        "\n".join(
            (
                "REMARK SMILES C",
                "REMARK SMILES IDX 1 1",
                "ROOT",
                _atom(
                    1,
                    atom_name="C",
                    x=0.0,
                    charge=0.0,
                    atom_type="C",
                ),
                _atom(
                    2,
                    atom_name="G0",
                    x=1.0,
                    charge=0.0,
                    atom_type="G0",
                ),
                "ENDROOT",
                "TORSDOF 0",
                "",
            )
        )
    ).encode("ascii")


def _row(
    *,
    case_id: str,
    rank: int | None,
    native_like: bool | None,
) -> PoseRankingCalibrationRow:
    common = {
        "suite_id": "fixture",
        "case_id": case_id,
        "target_id": case_id.split("_", maxsplit=1)[0],
        "target_family": f"proxy:{case_id}",
        "split_role": "test",
        "scoring_protocol_sha256": _sha("source-protocol"),
        "preparation_profile_sha256": _sha("preparation"),
        "receptor_sha256": _sha(f"receptor:{case_id}"),
        "ligand_sha256": _sha(f"ligand:{case_id}"),
        "scaffold_sha256": _sha(f"scaffold:{case_id}"),
    }
    if rank is None:
        return PoseRankingCalibrationRow(
            **common,
            pose_id=f"vina:{case_id}:case_failure",
            pose_sha256=_sha(f"failure:{case_id}"),
            status="failure",
            term_values={},
            native_like=None,
            error_code="chemistry_scope_abstention",
        )
    return PoseRankingCalibrationRow(
        **common,
        pose_id=f"vina:{case_id}:pose:{rank}",
        pose_sha256=_sha(f"pose:{case_id}:{rank}"),
        status="success",
        term_values={"source.term": float(rank)},
        native_like=native_like,
        error_code="",
    )


def _observation(
    *,
    case_id: str,
    rank: int,
    score: float | None,
) -> diagnostic._ScoreObservation:
    if score is None:
        return diagnostic._ScoreObservation(
            engine_id="vina",
            case_id=case_id,
            pose_rank=rank,
            pose_id=f"vina:{case_id}:pose:{rank}",
            pose_coordinate_sha256=_sha(f"pose:{case_id}:{rank}"),
            pose_artifact_sha256=_sha(f"artifact:{case_id}"),
            status="scorer_failure",
            total_score=None,
            terms=(),
            diagnostics=None,
            error_code="internal_diagnostic_scoring_failed",
            error_message_sha256=_sha("scorer failure"),
        )
    return diagnostic._ScoreObservation(
        engine_id="vina",
        case_id=case_id,
        pose_rank=rank,
        pose_id=f"vina:{case_id}:pose:{rank}",
        pose_coordinate_sha256=_sha(f"pose:{case_id}:{rank}"),
        pose_artifact_sha256=_sha(f"artifact:{case_id}"),
        status="scored",
        total_score=score,
        terms=tuple({"term_id": f"term:{index}"} for index in range(4)),
        diagnostics={"complete": True},
        error_code="",
        error_message_sha256="",
    )


def _metadata(case_id: str) -> dict[str, object]:
    return {
        "case_id": case_id,
        "target_id": case_id.split("_", maxsplit=1)[0],
        "observed_sequence_proxy_id": f"proxy:{case_id}",
        "pfam_ids": ("PF00001",),
        "pfam_set_id": "pfam-set",
        "biological_annotation_status": "pfam_annotated",
    }


def test_bound_ligand_excludes_only_exact_zero_charge_g0() -> None:
    ligand = diagnostic._bound_ligand(_prepared_ligand_with_g0())

    assert ligand.parsed.smiles == "C"
    assert ligand.physical_serials == (1,)
    assert ligand.source_serials == (1,)
    assert ligand.pseudoatom_serials == (2,)
    assert ligand.physical_coordinates.tolist() == [[0.0, 1.0, 2.0]]

    source = _prepared_ligand_with_g0().replace(b" 0.000 G0", b" 0.100 G0")
    with pytest.raises(
        diagnostic.PoseBustersInternalDiagnosticRankingError,
        match="zero-charge G0",
    ):
        diagnostic._bound_ligand(source)


def test_test_labels_join_only_after_fixed_scores_and_ties_are_inclusive() -> None:
    case_id = "A001_L001"
    rows = (
        _row(case_id=case_id, rank=1, native_like=True),
        _row(case_id=case_id, rank=2, native_like=False),
    )
    observations = {
        ("vina", case_id, 1): _observation(
            case_id=case_id,
            rank=1,
            score=2.0,
        ),
        ("vina", case_id, 2): _observation(
            case_id=case_id,
            rank=2,
            score=1.0,
        ),
    }
    result = diagnostic._evaluate_case(
        "vina",
        case_id,
        rows,
        observations,
        _metadata(case_id),
    )

    assert [
        row["pose_id"] for row in result["ranked_pose_rows"]
    ] == [
        f"vina:{case_id}:pose:2",
        f"vina:{case_id}:pose:1",
    ]
    assert result["top1_native_like"] is False
    assert result["top5_native_like"] is True
    assert result["test_labels_used_for_score_computation"] is False
    assert result["test_labels_used_for_evaluation"] is True
    assert result["source_order_reproduced"] is False


def test_scorer_and_upstream_failures_remain_explicit_without_labels() -> None:
    scored_case = "A001_L001"
    scorer_failure = diagnostic._evaluate_case(
        "vina",
        scored_case,
        (_row(case_id=scored_case, rank=1, native_like=True),),
        {
            ("vina", scored_case, 1): _observation(
                case_id=scored_case,
                rank=1,
                score=None,
            )
        },
        _metadata(scored_case),
    )
    assert scorer_failure["status"] == "failure"
    assert scorer_failure["scorer_failure_observation_count"] == 1
    assert scorer_failure["failure_observations"][0][
        "native_like_label_exposed_on_failure"
    ] is False
    assert scorer_failure["failure_observations"][0]["stage"] == (
        "internal_diagnostic_scoring"
    )

    upstream_case = "A002_L002"
    upstream_failure = diagnostic._evaluate_case(
        "vina",
        upstream_case,
        (_row(case_id=upstream_case, rank=None, native_like=None),),
        {},
        _metadata(upstream_case),
    )
    assert upstream_failure["upstream_failure_observation_count"] == 1
    assert upstream_failure["failure_observations"][0]["error_code"] == (
        "chemistry_scope_abstention"
    )


def test_score_policy_is_frozen_unfitted_and_receipt_is_private_no_overwrite(
    tmp_path: Path,
) -> None:
    policy = diagnostic._score_policy()
    assert policy["fit_or_calibration_performed"] is False
    assert policy["test_labels_used_to_select_policy"] is False
    assert policy["validated_for_docking_ranking"] is False
    assert policy["policy_sha256"] == diagnostic._score_policy()["policy_sha256"]

    receipt = diagnostic.PoseBustersInternalDiagnosticRankingReceipt(
        {
            "schema_id": (
                diagnostic.POSEBUSTERS_INTERNAL_DIAGNOSTIC_RANKING_RECEIPT_SCHEMA_ID
            ),
            "all_case_denominator": 308,
            "engine_count": 3,
            "split_role": "test",
            "internal_diagnostic_result_materialized": True,
            "complete_public_benchmark_result": False,
            "score_policy_fit_performed": False,
            "test_labels_used_for_score_computation": False,
            "test_labels_used_for_fit": False,
            "test_labels_used_to_select_score_policy": False,
            "test_labels_used_for_evaluation": True,
            "calibrated_internal_scorer": False,
            "leakage_control_passed": False,
            "independent_external_rerun_present": False,
            "scientifically_validated": False,
            "public_docking_claim_authorized": False,
            "claim_safe": False,
        }
    )
    output = tmp_path / "receipt.json"
    receipt.write_json(output)
    assert output.stat().st_mode & 0o777 == 0o600
    assert output.read_bytes() == receipt.canonical_bytes()
    with pytest.raises(
        diagnostic.PoseBustersInternalDiagnosticRankingError,
        match="already exists",
    ):
        receipt.write_json(output)

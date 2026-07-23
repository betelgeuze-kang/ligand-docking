from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest


pytest.importorskip("torch")

from betelgeuze_engine_v2.benchmark.public_posebusters_external_ranking_evaluation import (  # noqa: E402
    POSEBUSTERS_EXTERNAL_RANKING_EVALUATION_CONFIGURATION_SHA256,
    POSEBUSTERS_EXTERNAL_RANKING_EVALUATION_SCIENTIFIC_BLOCKERS,
    POSEBUSTERS_EXTERNAL_RANKING_SCORING_PROTOCOL_SHA256,
    PoseBustersExternalRankingEvaluationError,
    materialize_posebusters_external_ranking_evaluation,
    verify_posebusters_external_ranking_evaluation_receipt,
)
from betelgeuze_engine_v2.benchmark.public_posebusters_pose_ranking_intake import (  # noqa: E402
    POSEBUSTERS_POSE_RANKING_INTAKE_TERM_ORDERS,
)
from betelgeuze_engine_v2.benchmark.public_posebusters_pose_ranking_test_partition import (  # noqa: E402
    POSEBUSTERS_POSE_RANKING_TEST_PARTITION_RECEIPT_SCHEMA_ID,
)
from betelgeuze_engine_v2.docking.calibration import (  # noqa: E402
    PoseRankingCalibrationPartition,
    PoseRankingCalibrationRow,
)


_ENGINES = ("vina", "gnina", "smina")


def _sha(value: str | bytes) -> str:
    source = value.encode("utf-8") if isinstance(value, str) else value
    return hashlib.sha256(source).hexdigest()


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("ascii")


def _canonical_sha(value: object) -> str:
    return _sha(_canonical_bytes(value))


def _write_receipt(
    path: Path,
    payload: dict[str, object],
) -> str:
    receipt_sha = _canonical_sha(payload)
    source = _canonical_bytes({**payload, "receipt_sha256": receipt_sha}) + b"\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(source)
    path.chmod(0o600)
    return receipt_sha


def _case_ids() -> tuple[str, ...]:
    return tuple(f"A{index:03d}_L{index:03d}" for index in range(308))


def _source_score(
    engine: str,
    rank: int,
    *,
    reverse_order: bool,
    tie_scores: bool,
) -> float:
    if tie_scores:
        return 0.0
    if engine == "gnina":
        ordered = (2.0, 1.0)
    else:
        ordered = (-2.0, -1.0)
    if reverse_order:
        ordered = tuple(reversed(ordered))
    return ordered[rank - 1]


def _terms(
    engine: str,
    rank: int,
    *,
    reverse_order: bool,
    tie_scores: bool,
) -> dict[str, float]:
    terms = {
        f"{engine}.{term}": float(index + 1)
        for index, term in enumerate(
            POSEBUSTERS_POSE_RANKING_INTAKE_TERM_ORDERS[engine]
        )
    }
    source_term = {
        "vina": "vina.total",
        "gnina": "gnina.cnn_pose_score",
        "smina": "smina.minimized_affinity_kcal_per_mol",
    }[engine]
    terms[source_term] = _source_score(
        engine,
        rank,
        reverse_order=reverse_order,
        tie_scores=tie_scores,
    )
    return terms


def _row(
    engine: str,
    case_id: str,
    *,
    rank: int | None,
    reverse_order: bool,
    tie_scores: bool,
) -> PoseRankingCalibrationRow:
    common = {
        "suite_id": "posebusters-test-fixture",
        "case_id": case_id,
        "target_id": case_id.split("_", maxsplit=1)[0],
        "target_family": f"proxy_{case_id}",
        "split_role": "test",
        "scoring_protocol_sha256": (
            POSEBUSTERS_EXTERNAL_RANKING_SCORING_PROTOCOL_SHA256[engine]
        ),
        "preparation_profile_sha256": _sha("preparation-profile"),
        "receptor_sha256": _sha(f"receptor:{case_id}"),
        "ligand_sha256": _sha(f"ligand:{case_id}"),
        "scaffold_sha256": _sha(f"scaffold:{case_id}"),
    }
    if rank is not None:
        return PoseRankingCalibrationRow(
            **common,
            pose_id=f"{engine}:{case_id}:pose:{rank}",
            pose_sha256=_sha(f"pose:{engine}:{case_id}:{rank}"),
            status="success",
            term_values=_terms(
                engine,
                rank,
                reverse_order=reverse_order,
                tie_scores=tie_scores,
            ),
            native_like=rank == 1,
        )
    return PoseRankingCalibrationRow(
        **common,
        pose_id=f"{engine}:{case_id}:case_failure",
        pose_sha256=_sha(f"failure:{engine}:{case_id}"),
        status="failure",
        term_values={},
        native_like=None,
        error_code="chemistry_scope_abstention",
    )


def _fixture(
    root: Path,
    *,
    reverse_order: bool = False,
    tie_scores: bool = False,
) -> tuple[Path, str]:
    case_ids = _case_ids()
    case_rows = []
    for index, case_id in enumerate(case_ids):
        annotated = index < 225
        case_rows.append(
            {
                "case_id": case_id,
                "target_id": case_id.split("_", maxsplit=1)[0],
                "observed_sequence_proxy_id": f"proxy_{index:03d}",
                "pfam_ids": ["PF00001"] if annotated else [],
                "pfam_set_id": "pfam_set_fixture" if annotated else None,
                "biological_annotation_status": (
                    "pfam_annotated" if annotated else "uniprot_without_pfam"
                ),
            }
        )

    engine_partitions = []
    engine_summaries = []
    for engine in _ENGINES:
        rows = [
            _row(
                engine,
                case_ids[0],
                rank=rank,
                reverse_order=reverse_order,
                tie_scores=tie_scores,
            )
            for rank in (1, 2)
        ]
        rows.extend(
            _row(
                engine,
                case_id,
                rank=None,
                reverse_order=reverse_order,
                tie_scores=tie_scores,
            )
            for case_id in case_ids[1:]
        )
        partition = PoseRankingCalibrationPartition(
            dataset_id="posebusters-test",
            dataset_version="fixture-v1",
            split_role="test",
            rows=tuple(rows),
        )
        engine_partitions.append(
            {
                "engine_id": engine,
                "split_role": "test",
                "calibration_fit_performed": False,
                "test_labels_used_for_fit": False,
                "all_case_denominator": 308,
                "source_term_order": [
                    f"{engine}.{term}"
                    for term in POSEBUSTERS_POSE_RANKING_INTAKE_TERM_ORDERS[engine]
                ],
                "scoring_protocol_sha256": (
                    POSEBUSTERS_EXTERNAL_RANKING_SCORING_PROTOCOL_SHA256[engine]
                ),
                "partition": partition.to_dict(),
                "partition_fingerprint_sha256": partition.fingerprint_sha256,
                "partition_identity_fingerprint_sha256": (
                    partition.identity_fingerprint_sha256
                ),
                "successful_pose_row_count": 2,
                "failure_observation_row_count": 307,
                "partition_row_count": 309,
            }
        )
        engine_summaries.append(
            {
                "engine_id": engine,
                "successful_pose_row_count": 2,
                "failure_row_count": 307,
                "evaluated_case_count": 1,
                "physically_valid_pose_count": 2,
                "top_1_native_like_case_count": 1,
                "top_5_native_like_case_count": 1,
                "top_1_valid_native_like_case_count": 1,
                "top_5_valid_native_like_case_count": 1,
            }
        )

    payload: dict[str, object] = {
        "schema_id": (POSEBUSTERS_POSE_RANKING_TEST_PARTITION_RECEIPT_SCHEMA_ID),
        "dataset_id": "posebusters-test",
        "dataset_version": "fixture-v1",
        "configuration_sha256": _sha("source-configuration"),
        "implementation_source_sha256": _sha("source-implementation"),
        "split_role": "test",
        "all_case_denominator": 308,
        "test_partition_materialized": True,
        "calibration_partition_materialized": True,
        "fit_partition_present": False,
        "calibration_fit_performed": False,
        "test_labels_used_for_fit": False,
        "case_rows": case_rows,
        "engine_partitions": engine_partitions,
        "ranking_metric_validation": {
            "validated": True,
            "all_case_denominator": 308,
            "source_metric_root_sha256": _sha("source-metric-root"),
            "engine_summaries": engine_summaries,
        },
        "scientifically_validated": False,
        "claim_safe": False,
    }
    path = root / "test-partitions.json"
    return path, _write_receipt(path, payload)


def _metric(result: dict[str, object], metric_id: str) -> dict[str, object]:
    metrics = result["metrics"]
    assert isinstance(metrics, list)
    return next(
        metric
        for metric in metrics
        if isinstance(metric, dict) and metric["metric_id"] == metric_id
    )


def test_materializes_failure_inclusive_external_ranking_result(
    tmp_path: Path,
) -> None:
    source_path, source_sha = _fixture(tmp_path / "inputs")
    receipt = materialize_posebusters_external_ranking_evaluation(
        source_path,
        expected_test_partition_receipt_sha256=source_sha,
    )
    payload = receipt.to_dict()

    assert payload["configuration_sha256"] == (
        POSEBUSTERS_EXTERNAL_RANKING_EVALUATION_CONFIGURATION_SHA256
    )
    assert payload["all_case_denominator"] == 308
    assert payload["engine_count"] == 3
    assert payload["total_successful_pose_count"] == 6
    assert payload["total_failure_observation_count"] == 921
    assert payload["external_reference_result_materialized"] is True
    assert payload["complete_public_benchmark_result"] is False
    assert payload["score_policy_fit_performed"] is False
    assert payload["test_labels_used_to_select_score_policy"] is False
    assert payload["test_labels_used_for_evaluation"] is True
    assert payload["external_model_training_leakage_audit_present"] is False
    assert payload["leakage_control_passed"] is False
    assert payload["scientific_blockers"] == list(
        POSEBUSTERS_EXTERNAL_RANKING_EVALUATION_SCIENTIFIC_BLOCKERS
    )
    assert payload["scientifically_validated"] is False
    assert payload["public_docking_claim_authorized"] is False
    assert payload["claim_safe"] is False

    for result in payload["engine_results"]:
        assert result["scored_case_count"] == 1
        assert result["failure_case_count"] == 307
        assert result["source_order_reproduced_case_count"] == 1
        assert _metric(result, "scored_case_coverage")["numerator"] == 1
        assert (
            _metric(
                result,
                "top1_native_like_rate_all_cases",
            )["denominator"]
            == 308
        )
        assert (
            _metric(
                result,
                "top5_native_like_rate_all_cases",
            )["numerator"]
            == 1
        )
        assert result["pose_curve_metric"]["value"] == 1.0
        assert result["pose_curve_metric"]["positive_pose_count"] == 1
        assert result["pose_curve_metric"]["negative_pose_count"] == 1
        assert result["pose_curve_metric"]["bootstrap_requested_sample_count"] == 2000
        assert 0 < result["pose_curve_metric"]["bootstrap_valid_sample_count"] < 2000
        assert result["pose_curve_metric"]["confidence_interval_low"] == 1.0
        assert result["pose_curve_metric"]["confidence_interval_high"] == 1.0
        assert (
            "case_cluster_bootstrap_dropped_single_class_replicates"
            in result["pose_curve_metric"]["blockers"]
        )
        assert result["case_rows"][0]["source_order_reproduced"] is True
        assert result["case_rows"][1]["source_order_reproduced"] is False
        scopes = {scope["family_kind"]: scope for scope in result["family_scopes"]}
        assert scopes["observed_sequence_proxy"]["all_case_membership_complete"] is True
        assert (
            scopes["exact_pfam_set_or_missing"]["biological_annotation_complete"]
            is False
        )
        assert (
            scopes["pfam_multi_label_or_missing"]["memberships_are_disjoint"] is False
        )


def test_exact_verify_private_mode_and_no_overwrite(tmp_path: Path) -> None:
    source_path, source_sha = _fixture(tmp_path / "inputs")
    receipt = materialize_posebusters_external_ranking_evaluation(
        source_path,
        expected_test_partition_receipt_sha256=source_sha,
    )
    output = tmp_path / "evaluation.json"
    receipt.write_json(output)

    assert output.stat().st_mode & 0o777 == 0o600
    verified = verify_posebusters_external_ranking_evaluation_receipt(
        output,
        source_path,
        expected_test_partition_receipt_sha256=source_sha,
    )
    assert verified.fingerprint_sha256 == receipt.fingerprint_sha256
    with pytest.raises(
        PoseBustersExternalRankingEvaluationError,
        match="already exists",
    ):
        receipt.write_json(output)

    output.chmod(0o644)
    with pytest.raises(
        PoseBustersExternalRankingEvaluationError,
        match="mode-0600",
    ):
        verify_posebusters_external_ranking_evaluation_receipt(
            output,
            source_path,
            expected_test_partition_receipt_sha256=source_sha,
        )


def test_rejects_wrong_pin_and_nonreproducible_source_order(
    tmp_path: Path,
) -> None:
    source_path, source_sha = _fixture(tmp_path / "valid")
    with pytest.raises(
        PoseBustersExternalRankingEvaluationError,
        match="source receipt is invalid",
    ):
        materialize_posebusters_external_ranking_evaluation(
            source_path,
            expected_test_partition_receipt_sha256="0" * 64,
        )

    reversed_path, reversed_sha = _fixture(
        tmp_path / "reversed",
        reverse_order=True,
    )
    with pytest.raises(
        PoseBustersExternalRankingEvaluationError,
        match="fixed policy does not reproduce source pose ordering",
    ):
        materialize_posebusters_external_ranking_evaluation(
            reversed_path,
            expected_test_partition_receipt_sha256=reversed_sha,
        )


def test_tie_boundary_is_inclusive_and_pr_auc_is_tie_invariant(
    tmp_path: Path,
) -> None:
    source_path, source_sha = _fixture(
        tmp_path / "ties",
        tie_scores=True,
    )
    payload = materialize_posebusters_external_ranking_evaluation(
        source_path,
        expected_test_partition_receipt_sha256=source_sha,
    ).to_dict()

    for result in payload["engine_results"]:
        scored_case = result["case_rows"][0]
        assert scored_case["top1_tie_inclusive_pose_count"] == 2
        assert scored_case["top5_tie_inclusive_pose_count"] == 2
        assert scored_case["top1_native_like"] is True
        assert result["pose_curve_metric"]["value"] == 0.5
        assert result["pose_curve_metric"]["confidence_interval_low"] == 0.5
        assert result["pose_curve_metric"]["confidence_interval_high"] == 0.5

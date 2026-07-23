from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import pytest


pytest.importorskip("torch")

from betelgeuze_engine_v2.benchmark.public_posebusters_pose_ranking_intake import (  # noqa: E402
    POSEBUSTERS_POSE_RANKING_INTAKE_CONFIGURATION_SHA256,
    POSEBUSTERS_POSE_RANKING_INTAKE_METRIC_SCHEMA_ID,
    POSEBUSTERS_POSE_RANKING_INTAKE_RECEIPT_SCHEMA_ID,
)
from betelgeuze_engine_v2.benchmark.public_posebusters_pose_ranking_test_partition import (  # noqa: E402
    POSEBUSTERS_POSE_RANKING_TEST_PARTITION_CONFIGURATION_SHA256,
    POSEBUSTERS_POSE_RANKING_TEST_PARTITION_SCIENTIFIC_BLOCKERS,
    PoseBustersPoseRankingTestPartitionError,
    materialize_posebusters_pose_ranking_test_partitions,
    verify_posebusters_pose_ranking_test_partition_receipt,
)
from betelgeuze_engine_v2.benchmark.public_posebusters_pose_scaffold_identity import (  # noqa: E402
    POSEBUSTERS_POSE_SCAFFOLD_IDENTITY_CONFIGURATION_SHA256,
    POSEBUSTERS_POSE_SCAFFOLD_IDENTITY_RECEIPT_SCHEMA_ID,
)
from betelgeuze_engine_v2.benchmark.public_posebusters_rcsb_target_family_binding import (  # noqa: E402
    POSEBUSTERS_RCSB_TARGET_FAMILY_CONFIGURATION_SHA256,
    POSEBUSTERS_RCSB_TARGET_FAMILY_RECEIPT_SCHEMA_ID,
    POSEBUSTERS_RCSB_TARGET_METRIC_SCHEMA_ID,
)
from betelgeuze_engine_v2.benchmark.public_posebusters_target_cluster_binding import (  # noqa: E402
    POSEBUSTERS_TARGET_CLUSTER_CONFIGURATION_SHA256,
    POSEBUSTERS_TARGET_CLUSTER_METRIC_SCHEMA_ID,
    POSEBUSTERS_TARGET_CLUSTER_RECEIPT_SCHEMA_ID,
)


_ENGINES = ("vina", "gnina", "smina")
_TERM_ORDERS = {
    "vina": (
        "vina.total",
        "vina.inter",
        "vina.intra",
        "vina.torsions",
        "vina.intra_best_pose",
    ),
    "gnina": (
        "gnina.minimized_affinity_kcal_per_mol",
        "gnina.cnn_pose_score",
        "gnina.cnn_affinity",
    ),
    "smina": ("smina.minimized_affinity_kcal_per_mol",),
}
_Z = 1.959963984540054


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
) -> tuple[str, str]:
    receipt_sha = _canonical_sha(payload)
    source_payload = {**payload, "receipt_sha256": receipt_sha}
    source = _canonical_bytes(source_payload) + b"\n"
    path.write_bytes(source)
    path.chmod(0o600)
    return receipt_sha, _sha(source)


def _closed(schema_id: str, **values: object) -> dict[str, object]:
    return {
        "schema_id": schema_id,
        **values,
        "scientifically_validated": False,
        "claim_safe": False,
    }


def _wilson(numerator: int, denominator: int) -> tuple[float, float]:
    estimate = numerator / denominator
    z_squared = _Z * _Z
    scale = 1.0 + z_squared / denominator
    center = (estimate + z_squared / (2.0 * denominator)) / scale
    margin = (
        _Z
        * math.sqrt(
            (estimate * (1.0 - estimate) + z_squared / (4.0 * denominator))
            / denominator
        )
        / scale
    )
    return max(0.0, center - margin), min(1.0, center + margin)


def _metric(
    *,
    schema_id: str,
    metric_id: str,
    numerator: int,
    denominator: int,
    denominator_scope: str,
    engine_id: str | None,
    family_id: str | None = None,
    family_kind: str | None = None,
) -> dict[str, object]:
    low, high = _wilson(numerator, denominator)
    row: dict[str, object] = {
        "schema_id": schema_id,
        "metric_id": metric_id,
        "numerator": numerator,
        "denominator": denominator,
        "denominator_scope": denominator_scope,
        "estimate": numerator / denominator,
        "confidence_interval_low": low,
        "confidence_interval_high": high,
        "confidence_interval_method": "wilson_score_binomial",
        "confidence_level": 0.95,
        "engine_id": engine_id,
    }
    if family_id is not None:
        row["family_id"] = family_id
    if family_kind is not None:
        row["family_kind"] = family_kind
    return row


def _case_ids() -> tuple[str, ...]:
    return tuple(f"A{index:03d}_L{index:03d}" for index in range(308))


def _fixture(root: Path) -> dict[str, object]:
    root.mkdir(parents=True)
    case_ids = _case_ids()
    annotated = set(case_ids[:225])
    pfam_id = "PF00001"
    pfam_set_id = f"pfam_set_{_sha('PF00001')}"
    archive_receipt_sha = _sha("archive-receipt")
    archive_file_sha = _sha("archive-file")
    preparation_receipt_sha = _sha("preparation-receipt")
    preparation_file_sha = _sha("preparation-file")

    cluster_cases = []
    cluster_families = []
    cluster_engine_cases = []
    cluster_engine_families = []
    for case_id in case_ids:
        target_id = case_id.split("_", maxsplit=1)[0]
        family_id = f"observed_target_cluster_{_sha(case_id)}"
        receptor_sha = _sha(f"receptor:{case_id}")
        cluster_cases.append(
            {
                "case_id": case_id,
                "pdb_id": target_id,
                "receptor_sha256": receptor_sha,
                "family_id": family_id,
                "target_sequence_set_sha256": _sha(f"sequence-set:{case_id}"),
                "chains": [
                    {
                        "chain_id": "A",
                        "residue_label_sequence_sha256": _sha(f"sequence:{case_id}"),
                    }
                ],
            }
        )
        cluster_families.append(
            {
                "family_id": family_id,
                "member_case_ids": [case_id],
                "member_case_count": 1,
            }
        )
        for engine in _ENGINES:
            success = case_id == case_ids[0]
            cluster_engine_cases.append(
                {
                    "engine_id": engine,
                    "case_id": case_id,
                    "family_id": family_id,
                    "execution_status": (
                        "success" if success else "abstain_chemistry_scope"
                    ),
                    "evaluation_status": (
                        "evaluated" if success else "abstain_chemistry_scope"
                    ),
                    "execution_pose_count": 1 if success else 0,
                    "evaluated_pose_count": 1 if success else 0,
                    "physically_valid_pose_count": 1 if success else 0,
                    "top_1_physically_valid": success,
                    "top_5_physically_valid": success,
                    "top_1_rmsd_hit": success,
                    "top_5_rmsd_hit": success,
                    "top_1_valid_rmsd_hit": success,
                    "top_5_valid_rmsd_hit": success,
                }
            )
            cluster_engine_families.append(
                {
                    "engine_id": engine,
                    "family_id": family_id,
                    "member_case_count": 1,
                    "execution_success_case_count": 1 if success else 0,
                    "top_1_physically_valid_case_count": 1 if success else 0,
                    "top_5_physically_valid_case_count": 1 if success else 0,
                    "top_1_rmsd_hit_case_count": 1 if success else 0,
                    "top_5_rmsd_hit_case_count": 1 if success else 0,
                    "top_1_valid_rmsd_hit_case_count": 1 if success else 0,
                    "top_5_valid_rmsd_hit_case_count": 1 if success else 0,
                    "covered": success,
                    "completely_covered": success,
                }
            )

    execution_receipt_shas = {
        engine: _sha(f"{engine}-execution-receipt") for engine in _ENGINES
    }
    execution_file_shas = {
        engine: _sha(f"{engine}-execution-file") for engine in _ENGINES
    }
    evaluation_receipt_shas = {
        engine: _sha(f"{engine}-evaluation-receipt") for engine in _ENGINES
    }
    evaluation_file_shas = {
        engine: _sha(f"{engine}-evaluation-file") for engine in _ENGINES
    }
    cluster_metrics = []
    all_scope_metrics = {
        "target_cluster_coverage_rate": 1,
        "complete_target_cluster_coverage_rate": 1,
        "target_cluster_with_any_top_1_rmsd_hit_rate": 1,
        "target_cluster_with_any_top_5_rmsd_hit_rate": 1,
        "target_cluster_with_any_top_1_valid_rmsd_hit_rate": 1,
        "target_cluster_with_any_top_5_valid_rmsd_hit_rate": 1,
    }
    covered_metrics = (
        "covered_target_cluster_with_any_top_1_physically_valid_rate",
        "covered_target_cluster_with_any_top_5_physically_valid_rate",
        "covered_target_cluster_with_any_top_1_rmsd_hit_rate",
        "covered_target_cluster_with_any_top_5_rmsd_hit_rate",
        "covered_target_cluster_with_any_top_1_valid_rmsd_hit_rate",
        "covered_target_cluster_with_any_top_5_valid_rmsd_hit_rate",
    )
    for engine in _ENGINES:
        for metric_id, numerator in all_scope_metrics.items():
            cluster_metrics.append(
                _metric(
                    schema_id=POSEBUSTERS_TARGET_CLUSTER_METRIC_SCHEMA_ID,
                    metric_id=metric_id,
                    numerator=numerator,
                    denominator=308,
                    denominator_scope="all_target_clusters",
                    engine_id=engine,
                )
            )
        for metric_id in covered_metrics:
            cluster_metrics.append(
                _metric(
                    schema_id=POSEBUSTERS_TARGET_CLUSTER_METRIC_SCHEMA_ID,
                    metric_id=metric_id,
                    numerator=1,
                    denominator=1,
                    denominator_scope=f"{engine}_covered_target_clusters",
                    engine_id=engine,
                )
            )
    cluster_path = root / "target-clusters.json"
    cluster_sha, _cluster_file_sha = _write_receipt(
        cluster_path,
        _closed(
            POSEBUSTERS_TARGET_CLUSTER_RECEIPT_SCHEMA_ID,
            configuration_sha256=POSEBUSTERS_TARGET_CLUSTER_CONFIGURATION_SHA256,
            all_case_denominator=308,
            archive_intake_receipt_sha256=archive_receipt_sha,
            preparation_receipt_sha256=preparation_receipt_sha,
            case_rows=cluster_cases,
            family_rows=cluster_families,
            engine_case_rows=cluster_engine_cases,
            engine_family_rows=cluster_engine_families,
            metrics=cluster_metrics,
            evaluation_inputs=[
                {
                    "engine_id": engine,
                    "execution_receipt_sha256": execution_receipt_shas[engine],
                    "evaluation_receipt_sha256": evaluation_receipt_shas[engine],
                    "evaluation_receipt_file_sha256": evaluation_file_shas[engine],
                    "generated_pose_count": 1,
                    "evaluated_pose_count": 1,
                }
                for engine in _ENGINES
            ],
        ),
    )

    target_cases = []
    for case_id in case_ids:
        is_annotated = case_id in annotated
        target_cases.append(
            {
                "case_id": case_id,
                "pdb_id": case_id.split("_", maxsplit=1)[0],
                "receptor_sha256": _sha(f"receptor:{case_id}"),
                "reference_ligand_sha256": _sha(f"reference:{case_id}"),
                "mapping_status": "complete",
                "annotation_status": (
                    "pfam_annotated" if is_annotated else "uniprot_without_pfam"
                ),
                "pfam_ids": [pfam_id] if is_annotated else [],
                "pfam_set_id": pfam_set_id if is_annotated else None,
                "uniprot_ids": [f"P{case_ids.index(case_id):05d}"],
            }
        )
    family_members = list(case_ids[:225])
    target_engine_families = []
    for engine in _ENGINES:
        for kind, family_id in (
            ("pfam_multi_label", pfam_id),
            ("pfam_set_partition", pfam_set_id),
        ):
            target_engine_families.append(
                {
                    "engine_id": engine,
                    "family_kind": kind,
                    "family_id": family_id,
                    "member_case_count": 225,
                    "execution_success_case_count": 1,
                    "top_1_rmsd_hit_case_count": 1,
                    "top_5_rmsd_hit_case_count": 1,
                    "top_1_valid_rmsd_hit_case_count": 1,
                    "top_5_valid_rmsd_hit_case_count": 1,
                }
            )
    target_metrics = [
        _metric(
            schema_id=POSEBUSTERS_RCSB_TARGET_METRIC_SCHEMA_ID,
            metric_id=metric_id,
            numerator=numerator,
            denominator=denominator,
            denominator_scope=scope,
            engine_id=None,
            family_id="all_cases",
            family_kind="all_case_annotation",
        )
        for metric_id, numerator, denominator, scope in (
            ("pocket_chain_mapping_complete_rate", 308, 308, "all_cases"),
            ("uniprot_annotation_case_rate", 308, 308, "all_cases"),
            ("pfam_annotation_case_rate", 225, 308, "all_cases"),
            ("removed_rcsb_entry_rate", 0, 308, "all_cases"),
            ("pocket_chain_mapping_failure_rate", 0, 308, "all_cases"),
            (
                "pfam_annotation_rate_among_mapping_complete_cases",
                225,
                308,
                "mapping_complete_cases",
            ),
        )
    ]
    family_metric_fields = (
        "execution_coverage_rate",
        "top_1_rmsd_hit_rate_all_family_members",
        "top_5_rmsd_hit_rate_all_family_members",
        "top_1_valid_rmsd_hit_rate_all_family_members",
        "top_5_valid_rmsd_hit_rate_all_family_members",
    )
    for row in target_engine_families:
        for metric_id in family_metric_fields:
            target_metrics.append(
                _metric(
                    schema_id=POSEBUSTERS_RCSB_TARGET_METRIC_SCHEMA_ID,
                    metric_id=metric_id,
                    numerator=1,
                    denominator=225,
                    denominator_scope="family_all_members",
                    engine_id=str(row["engine_id"]),
                    family_id=str(row["family_id"]),
                    family_kind=str(row["family_kind"]),
                )
            )
    target_path = root / "target-family.json"
    target_sha, target_file_sha = _write_receipt(
        target_path,
        _closed(
            POSEBUSTERS_RCSB_TARGET_FAMILY_RECEIPT_SCHEMA_ID,
            configuration_sha256=(POSEBUSTERS_RCSB_TARGET_FAMILY_CONFIGURATION_SHA256),
            all_case_denominator=308,
            archive_intake_receipt_sha256=archive_receipt_sha,
            target_cluster_receipt_sha256=cluster_sha,
            case_rows=target_cases,
            pfam_family_rows=[
                {
                    "pfam_id": pfam_id,
                    "member_case_ids": family_members,
                    "member_case_count": 225,
                }
            ],
            pfam_set_rows=[
                {
                    "pfam_set_id": pfam_set_id,
                    "pfam_ids": [pfam_id],
                    "member_case_ids": family_members,
                    "member_case_count": 225,
                }
            ],
            engine_family_rows=target_engine_families,
            metrics=target_metrics,
            pfam_annotated_case_count=225,
            mapping_complete_case_count=308,
            uniprot_annotated_case_count=308,
            rcsb_removed_case_count=0,
            pocket_chain_mapping_failure_case_count=0,
        ),
    )

    ranking_inputs = [
        {
            "role": "archive_intake",
            "source_schema_id": "archive",
            "source_receipt_sha256": archive_receipt_sha,
            "source_file_sha256": archive_file_sha,
        },
        {
            "role": "external_preparation",
            "source_schema_id": "preparation",
            "source_receipt_sha256": preparation_receipt_sha,
            "source_file_sha256": preparation_file_sha,
        },
        {
            "role": "rcsb_pfam_target_family",
            "source_schema_id": (POSEBUSTERS_RCSB_TARGET_FAMILY_RECEIPT_SCHEMA_ID),
            "source_receipt_sha256": target_sha,
            "source_file_sha256": target_file_sha,
        },
    ]
    for engine in _ENGINES:
        ranking_inputs.extend(
            (
                {
                    "role": f"{engine}_execution",
                    "source_schema_id": f"{engine}-execution",
                    "source_receipt_sha256": execution_receipt_shas[engine],
                    "source_file_sha256": execution_file_shas[engine],
                },
                {
                    "role": f"{engine}_evaluation",
                    "source_schema_id": f"{engine}-evaluation",
                    "source_receipt_sha256": evaluation_receipt_shas[engine],
                    "source_file_sha256": evaluation_file_shas[engine],
                },
            )
        )
    protocol_shas = {engine: _sha(f"protocol:{engine}") for engine in _ENGINES}
    preparation_profile_sha = _sha("preparation-profile")
    ranking_rows = []
    ranking_case_rows = []
    identity_rows = []
    identity_cases = []
    for case_id in case_ids:
        is_annotated = case_id in annotated
        identity_cases.append(
            {
                "case_id": case_id,
                "accepted_scaffold_sha256": _sha(f"scaffold:{case_id}"),
                "start_ligand_sdf_sha256": _sha(f"ligand:{case_id}"),
            }
        )
        for engine in _ENGINES:
            success = case_id == case_ids[0]
            row_id = (
                f"{engine}:{case_id}:pose:1"
                if success
                else f"{engine}:{case_id}:case_failure"
            )
            failure_code = "" if success else "chemistry_scope_abstention"
            row = {
                "row_id": row_id,
                "engine_id": engine,
                "case_id": case_id,
                "pose_rank": 1 if success else None,
                "status": "success" if success else "failure",
                "failure_code": failure_code,
                "native_like": True if success else None,
                "physically_valid": True if success else None,
                "score_component_order": (
                    list(_TERM_ORDERS[engine]) if success else []
                ),
                "score_components_binary64_hex": (
                    [
                        float(index + 1).hex()
                        for index in range(len(_TERM_ORDERS[engine]))
                    ]
                    if success
                    else []
                ),
                "scoring_protocol_sha256": protocol_shas[engine],
                "preparation_profile_sha256": preparation_profile_sha,
                "receptor_sha256": _sha(f"receptor:{case_id}"),
                "ligand_start_conformer_sha256": _sha(f"ligand:{case_id}"),
                "reference_ligand_sha256": _sha(f"reference:{case_id}"),
                "pose_artifact_sha256": _sha(f"pose:{engine}") if success else None,
                "target_id": case_id.split("_", maxsplit=1)[0],
                "target_family_annotation_status": (
                    "pfam_annotated" if is_annotated else "uniprot_without_pfam"
                ),
                "target_family_id": pfam_set_id if is_annotated else None,
                "pfam_ids": [pfam_id] if is_annotated else [],
                "split_role": "test",
            }
            ranking_rows.append(row)
            ranking_case_rows.append(
                {
                    "engine_id": engine,
                    "case_id": case_id,
                }
            )
            identity_rows.append(
                {
                    "source_ranking_row_id": row_id,
                    "source_ranking_row_sha256": _canonical_sha(row),
                    "engine_id": engine,
                    "case_id": case_id,
                    "accepted_scaffold_sha256": _sha(f"scaffold:{case_id}"),
                    "pose_rank": 1 if success else None,
                    "pose_artifact_sha256": (
                        _sha(f"pose:{engine}") if success else None
                    ),
                    "pose_coordinate_sha256": (
                        _sha(f"coordinate:{engine}") if success else None
                    ),
                    "coordinate_identity_applicable": success,
                    "status": "identified_pose" if success else "upstream_failure",
                    "failure_code": None if success else failure_code,
                }
            )
    ranking_metrics = []
    engine_summaries = []
    for engine in _ENGINES:
        for metric_id, numerator, denominator, scope in (
            ("evaluated_case_rate", 1, 308, "all_cases"),
            ("top_1_native_like_case_rate", 1, 308, "all_cases"),
            ("top_5_native_like_case_rate", 1, 308, "all_cases"),
            ("top_1_valid_native_like_case_rate", 1, 308, "all_cases"),
            ("top_5_valid_native_like_case_rate", 1, 308, "all_cases"),
            ("native_like_pose_rate", 1, 1, "successfully_evaluated_poses"),
            ("physically_valid_pose_rate", 1, 1, "successfully_evaluated_poses"),
        ):
            ranking_metrics.append(
                _metric(
                    schema_id=POSEBUSTERS_POSE_RANKING_INTAKE_METRIC_SCHEMA_ID,
                    metric_id=metric_id,
                    numerator=numerator,
                    denominator=denominator,
                    denominator_scope=scope,
                    engine_id=engine,
                )
            )
        engine_summaries.append(
            {
                "engine_id": engine,
                "evaluated_case_count": 1,
                "failure_row_count": 307,
                "native_like_pose_count": 1,
                "physically_valid_pose_count": 1,
                "successful_pose_row_count": 1,
                "top_1_native_like_case_count": 1,
                "top_1_valid_native_like_case_count": 1,
                "top_5_native_like_case_count": 1,
                "top_5_valid_native_like_case_count": 1,
            }
        )
    ranking_path = root / "ranking.json"
    ranking_sha, ranking_file_sha = _write_receipt(
        ranking_path,
        _closed(
            POSEBUSTERS_POSE_RANKING_INTAKE_RECEIPT_SCHEMA_ID,
            configuration_sha256=(POSEBUSTERS_POSE_RANKING_INTAKE_CONFIGURATION_SHA256),
            all_case_denominator=308,
            dataset_id="posebusters-test",
            dataset_version="fixture-v1",
            split_role="test",
            test_labels_used_for_fit=False,
            calibration_fit_performed=False,
            input_receipts=ranking_inputs,
            case_rows=ranking_case_rows,
            intake_rows=ranking_rows,
            intake_row_count=len(ranking_rows),
            engine_summaries=engine_summaries,
            metrics=ranking_metrics,
        ),
    )
    identity_path = root / "identity.json"
    identity_sha, _identity_file_sha = _write_receipt(
        identity_path,
        _closed(
            POSEBUSTERS_POSE_SCAFFOLD_IDENTITY_RECEIPT_SCHEMA_ID,
            configuration_sha256=(
                POSEBUSTERS_POSE_SCAFFOLD_IDENTITY_CONFIGURATION_SHA256
            ),
            all_case_denominator=308,
            split_role="test",
            test_labels_used_for_fit=False,
            pose_coordinate_identity_complete=True,
            scaffold_identity_complete=True,
            ranking_intake_identity_binding_complete=True,
            input_receipts=[
                {
                    "role": "pose_ranking_intake",
                    "source_schema_id": (
                        POSEBUSTERS_POSE_RANKING_INTAKE_RECEIPT_SCHEMA_ID
                    ),
                    "source_receipt_sha256": ranking_sha,
                    "source_file_sha256": ranking_file_sha,
                }
            ],
            case_rows=identity_cases,
            identity_rows=identity_rows,
            identity_row_count=len(identity_rows),
        ),
    )
    return {
        "ranking_intake_receipt_path": ranking_path,
        "pose_scaffold_identity_receipt_path": identity_path,
        "target_cluster_receipt_path": cluster_path,
        "target_family_receipt_path": target_path,
        "expected_ranking_intake_receipt_sha256": ranking_sha,
        "expected_pose_scaffold_identity_receipt_sha256": identity_sha,
        "expected_target_cluster_receipt_sha256": cluster_sha,
        "expected_target_family_receipt_sha256": target_sha,
    }


def test_materializes_three_failure_inclusive_test_partitions(
    tmp_path: Path,
) -> None:
    fixture = _fixture(tmp_path / "inputs")
    receipt = materialize_posebusters_pose_ranking_test_partitions(**fixture)
    payload = receipt.to_dict()

    assert payload["configuration_sha256"] == (
        POSEBUSTERS_POSE_RANKING_TEST_PARTITION_CONFIGURATION_SHA256
    )
    assert payload["all_case_denominator"] == 308
    assert payload["partition_row_count"] == 924
    assert payload["successful_pose_row_count"] == 3
    assert payload["failure_observation_row_count"] == 921
    assert payload["unique_failure_observation_identity_count"] == 921
    assert payload["test_partition_materialized"] is True
    assert payload["fit_partition_present"] is False
    assert payload["calibration_fit_performed"] is False
    assert payload["test_labels_used_for_fit"] is False
    assert payload["leakage_control_passed"] is False
    assert payload["claim_safe"] is False
    assert payload["scientific_blockers"] == list(
        POSEBUSTERS_POSE_RANKING_TEST_PARTITION_SCIENTIFIC_BLOCKERS
    )
    assert payload["observed_sequence_proxy_metric_validation"]["validated"] is True
    assert payload["rcsb_pfam_metric_validation"]["pfam_annotated_case_count"] == 225
    assert payload["rcsb_pfam_metric_validation"]["pfam_missing_case_count"] == 83

    for engine_partition in payload["engine_partitions"]:
        engine = engine_partition["engine_id"]
        assert engine_partition["all_case_denominator"] == 308
        assert engine_partition["partition_row_count"] == 308
        assert engine_partition["successful_pose_row_count"] == 1
        assert engine_partition["failure_observation_row_count"] == 307
        rows = engine_partition["partition"]["rows"]
        assert {row["case_id"] for row in rows} == set(_case_ids())
        success = next(row for row in rows if row["status"] == "success")
        failure = next(row for row in rows if row["status"] == "failure")
        assert success["pose_sha256"] == _sha(f"coordinate:{engine}")
        assert failure["pose_sha256"] != success["pose_sha256"]
        assert failure["term_values"] == {}
        assert failure["native_like"] is None
        assert failure["error_code"] == "chemistry_scope_abstention"
        assert failure["target_family"].startswith("observed_target_cluster_")

    output = tmp_path / "test-partitions.json"
    receipt.write_json(output)
    assert output.stat().st_mode & 0o777 == 0o600
    verified = verify_posebusters_pose_ranking_test_partition_receipt(
        test_partition_receipt_path=output,
        **fixture,
    )
    assert verified.fingerprint_sha256 == receipt.fingerprint_sha256
    with pytest.raises(
        PoseBustersPoseRankingTestPartitionError,
        match="already exists",
    ):
        receipt.write_json(output)


def test_rejects_wrong_pin_and_ranking_identity_tampering(
    tmp_path: Path,
) -> None:
    fixture = _fixture(tmp_path / "inputs")
    wrong = dict(fixture)
    wrong["expected_target_cluster_receipt_sha256"] = "0" * 64
    with pytest.raises(
        PoseBustersPoseRankingTestPartitionError,
        match="source receipt is invalid",
    ):
        materialize_posebusters_pose_ranking_test_partitions(**wrong)

    identity_path = Path(fixture["pose_scaffold_identity_receipt_path"])
    identity = json.loads(identity_path.read_text(encoding="ascii"))
    identity.pop("receipt_sha256")
    identity["identity_rows"][0]["source_ranking_row_sha256"] = "0" * 64
    identity_sha, _ = _write_receipt(identity_path, identity)
    tampered = dict(fixture)
    tampered["expected_pose_scaffold_identity_receipt_sha256"] = identity_sha
    with pytest.raises(
        PoseBustersPoseRankingTestPartitionError,
        match="ranking row identity",
    ):
        materialize_posebusters_pose_ranking_test_partitions(**tampered)


def test_rejects_non_private_source_receipt(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path / "inputs")
    ranking_path = Path(fixture["ranking_intake_receipt_path"])
    ranking_path.chmod(0o644)
    with pytest.raises(
        PoseBustersPoseRankingTestPartitionError,
        match="source receipt is invalid",
    ):
        materialize_posebusters_pose_ranking_test_partitions(**fixture)

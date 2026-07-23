from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest


pytest.importorskip("torch")

from betelgeuze_engine_v2.benchmark.public_posebusters_external_binary_execution import (  # noqa: E402
    POSEBUSTERS_EXTERNAL_BINARY_EXECUTION_SCHEMA_ID,
)
from betelgeuze_engine_v2.benchmark.public_posebusters_external_generated_pose_evaluation import (  # noqa: E402
    POSEBUSTERS_EXTERNAL_GENERATED_POSE_EVALUATION_SCHEMA_ID,
)
from betelgeuze_engine_v2.benchmark.public_posebusters_external_preparation import (  # noqa: E402
    POSEBUSTERS_EXTERNAL_PREPARATION_SCHEMA_ID,
)
from betelgeuze_engine_v2.benchmark.public_posebusters_generated_pose_evaluation import (  # noqa: E402
    POSEBUSTERS_GENERATED_POSE_EVALUATION_SCHEMA_ID,
)
from betelgeuze_engine_v2.benchmark.public_posebusters_intake import (  # noqa: E402
    POSEBUSTERS_ARCHIVE_INTAKE_SCHEMA_ID,
)
from betelgeuze_engine_v2.benchmark.public_posebusters_pose_ranking_intake import (  # noqa: E402
    POSEBUSTERS_POSE_RANKING_INTAKE_ALL_CASE_DENOMINATOR,
    POSEBUSTERS_POSE_RANKING_INTAKE_CONFIGURATION_SHA256,
    POSEBUSTERS_POSE_RANKING_INTAKE_PARTITION_BLOCKERS,
    PoseBustersPoseRankingIntakeError,
    materialize_posebusters_pose_ranking_intake,
    verify_posebusters_pose_ranking_intake_receipt,
)
from betelgeuze_engine_v2.benchmark.public_posebusters_rcsb_target_family_binding import (  # noqa: E402
    POSEBUSTERS_RCSB_TARGET_FAMILY_RECEIPT_SCHEMA_ID,
)
from betelgeuze_engine_v2.benchmark.public_posebusters_vina_execution import (  # noqa: E402
    POSEBUSTERS_VINA_EXECUTION_SCHEMA_ID,
)


_ENGINES = ("vina", "gnina", "smina")
_TERM_ORDERS = {
    "vina": ("total", "inter", "intra", "torsions", "intra_best_pose"),
    "gnina": (
        "minimized_affinity_kcal_per_mol",
        "cnn_pose_score",
        "cnn_affinity",
    ),
    "smina": ("minimized_affinity_kcal_per_mol",),
}
_COMPONENTS = {
    "vina": tuple(value.hex() for value in (-5.5, -5.8, -0.1, 0.4, -0.1)),
    "gnina": tuple(value.hex() for value in (-5.5, 0.95, 5.1)),
    "smina": ((-5.5).hex(),),
}


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


def _write_receipt(path: Path, payload: dict[str, object]) -> tuple[str, str]:
    source_payload = dict(payload)
    receipt_sha = _sha(_canonical_bytes(source_payload))
    source_payload["receipt_sha256"] = receipt_sha
    source = _canonical_bytes(source_payload) + b"\n"
    path.write_bytes(source)
    path.chmod(0o600)
    return receipt_sha, _sha(source)


def _case_ids() -> tuple[str, ...]:
    return tuple(
        f"A{index:03d}_L{index:03d}"
        for index in range(
            POSEBUSTERS_POSE_RANKING_INTAKE_ALL_CASE_DENOMINATOR
        )
    )


def _archive_artifacts(case_id: str) -> list[dict[str, object]]:
    return [
        {
            "role": role,
            "sha256": _sha(f"{case_id}:{role}"),
        }
        for role in (
            "receptor_pdb",
            "reference_ligand_sdf",
            "reference_ligands_sdf",
            "ligand_start_conformer_sdf",
        )
    ]


def _claim_closed(
    schema_id: str,
    case_rows: list[dict[str, object]],
) -> dict[str, object]:
    return {
        "schema_id": schema_id,
        "all_case_denominator": len(case_rows),
        "case_rows": case_rows,
        "scientifically_validated": False,
        "claim_safe": False,
    }


def _fixture(root: Path) -> dict[str, object]:
    root.mkdir(parents=True, exist_ok=True)
    case_ids = _case_ids()
    first = case_ids[0]
    archive_path = root / "archive.json"
    preparation_path = root / "preparation.json"
    target_path = root / "target.json"
    execution_paths = {engine: root / f"{engine}-execution.json" for engine in _ENGINES}
    evaluation_paths = {engine: root / f"{engine}-evaluation.json" for engine in _ENGINES}

    archive_rows = [
        {
            "case_id": case_id,
            "artifacts": _archive_artifacts(case_id),
        }
        for case_id in case_ids
    ]
    archive_sha, _ = _write_receipt(
        archive_path,
        _claim_closed(
            POSEBUSTERS_ARCHIVE_INTAKE_SCHEMA_ID,
            archive_rows,
        ),
    )
    prepared_ligand_sha = _sha(f"{first}:prepared_ligand")
    prepared_receptor_sha = _sha(f"{first}:prepared_receptor")
    preparation_rows: list[dict[str, object]] = []
    for case_id in case_ids:
        artifacts: list[dict[str, object]] = []
        if case_id == first:
            artifacts = [
                {
                    "role": "prepared_ligand_pdbqt",
                    "sha256": prepared_ligand_sha,
                    "source_role": "ligand_start_conformer_sdf",
                    "source_sha256": _sha(
                        f"{case_id}:ligand_start_conformer_sdf"
                    ),
                },
                {
                    "role": "prepared_receptor_pdbqt",
                    "sha256": prepared_receptor_sha,
                    "source_role": "receptor_pdb",
                    "source_sha256": _sha(f"{case_id}:receptor_pdb"),
                },
            ]
        preparation_rows.append(
            {
                "case_id": case_id,
                "status": (
                    "prepared"
                    if case_id == first
                    else "abstain_chemistry_scope"
                ),
                "artifacts": artifacts,
            }
        )
    preparation_payload = _claim_closed(
        POSEBUSTERS_EXTERNAL_PREPARATION_SCHEMA_ID,
        preparation_rows,
    )
    preparation_payload.update(
        {
            "archive_intake_receipt_sha256": archive_sha,
            "configuration_sha256": _sha("preparation-configuration"),
        }
    )
    preparation_sha, preparation_file_sha = _write_receipt(
        preparation_path,
        preparation_payload,
    )

    evaluation_shas: dict[str, str] = {}
    for engine in _ENGINES:
        execution_rows: list[dict[str, object]] = []
        for case_id in case_ids:
            success = case_id == first
            common: dict[str, object] = {
                "case_id": case_id,
                "status": "success" if success else "abstain_chemistry_scope",
                "pose_count": 1 if success else 0,
                "pose_artifact": (
                    {
                        "sha256": _sha(f"{engine}:{case_id}:poses"),
                        "prepared_ligand_sha256": prepared_ligand_sha,
                        "prepared_receptor_sha256": prepared_receptor_sha,
                    }
                    if success
                    else None
                ),
                "error_code": "",
                "disposition_code": (
                    "" if success else "unsupported_chemistry"
                ),
            }
            if engine == "vina":
                common.update(
                    {
                        "energy_component_order": list(
                            _TERM_ORDERS[engine]
                        ),
                        "energies_binary64_hex": (
                            [list(_COMPONENTS[engine])] if success else []
                        ),
                    }
                )
            else:
                common.update(
                    {
                        "engine_id": engine,
                        "score_component_order": list(
                            _TERM_ORDERS[engine]
                        ),
                        "pose_scores": (
                            [
                                {
                                    "pose_rank": 1,
                                    "score_component_order": list(
                                        _TERM_ORDERS[engine]
                                    ),
                                    "components_binary64_hex": list(
                                        _COMPONENTS[engine]
                                    ),
                                    "components": dict(
                                        zip(
                                            _TERM_ORDERS[engine],
                                            _COMPONENTS[engine],
                                        )
                                    ),
                                }
                            ]
                            if success
                            else []
                        ),
                    }
                )
            execution_rows.append(common)
        execution_schema = (
            POSEBUSTERS_VINA_EXECUTION_SCHEMA_ID
            if engine == "vina"
            else POSEBUSTERS_EXTERNAL_BINARY_EXECUTION_SCHEMA_ID
        )
        execution_payload = _claim_closed(execution_schema, execution_rows)
        execution_payload.update(
            {
                "preparation_receipt_sha256": preparation_sha,
                "preparation_receipt_file_sha256": preparation_file_sha,
                "configuration_sha256": _sha(
                    f"{engine}:execution-configuration"
                ),
                (
                    "engine_identity_sha256"
                    if engine == "vina"
                    else "runtime_identity_sha256"
                ): _sha(f"{engine}:execution-runtime"),
            }
        )
        if engine != "vina":
            execution_payload["engine_id"] = engine
        execution_sha, execution_file_sha = _write_receipt(
            execution_paths[engine],
            execution_payload,
        )

        evaluation_rows: list[dict[str, object]] = []
        for case_id in case_ids:
            success = case_id == first
            pose: dict[str, object] = {
                "pose_rank": 1,
                "status": "evaluated",
                "rmsd_evaluated": True,
                "rmsd_within_2_angstrom": True,
                "all_non_rmsd_binary_tests_pass": True,
                "direct_rmsd_angstrom_binary64_hex": 1.0.hex(),
                "report_sha256": _sha(f"{engine}:{case_id}:report"),
                "diagnostic_sha256": _sha(
                    f"{engine}:{case_id}:diagnostic"
                ),
            }
            if engine == "vina":
                pose.update(
                    {
                        "vina_energy_component_order": list(
                            _TERM_ORDERS[engine]
                        ),
                        "vina_energy_components_binary64_hex": list(
                            _COMPONENTS[engine]
                        ),
                    }
                )
            else:
                pose.update(
                    {
                        "score_component_order": list(
                            _TERM_ORDERS[engine]
                        ),
                        "score_components_binary64_hex": list(
                            _COMPONENTS[engine]
                        ),
                    }
                )
            evaluation_rows.append(
                {
                    "case_id": case_id,
                    "status": (
                        "evaluated"
                        if success
                        else "abstain_chemistry_scope"
                    ),
                    "pose_results": [pose] if success else [],
                    "error_code": "",
                    "disposition_code": (
                        "" if success else "unsupported_chemistry"
                    ),
                    "diagnostic_sha256": _sha(
                        f"{engine}:{case_id}:case-diagnostic"
                    ),
                }
            )
        evaluation_schema = (
            POSEBUSTERS_GENERATED_POSE_EVALUATION_SCHEMA_ID
            if engine == "vina"
            else POSEBUSTERS_EXTERNAL_GENERATED_POSE_EVALUATION_SCHEMA_ID
        )
        evaluation_payload = _claim_closed(
            evaluation_schema,
            evaluation_rows,
        )
        evaluation_payload.update(
            {
                "archive_intake_receipt_sha256": archive_sha,
                "preparation_receipt_sha256": preparation_sha,
                "preparation_receipt_file_sha256": preparation_file_sha,
                "evaluated_pose_count": 1,
                "physically_valid_pose_count": 1,
                "runtime_identity_sha256": _sha(
                    f"{engine}:evaluation-runtime"
                ),
            }
        )
        if engine == "vina":
            evaluation_payload.update(
                {
                    "vina_receipt_sha256": execution_sha,
                    "vina_receipt_file_sha256": execution_file_sha,
                    "configuration_sha256": _sha(
                        "posebusters-evaluation-configuration"
                    ),
                }
            )
        else:
            evaluation_payload.update(
                {
                    "engine_id": engine,
                    "execution_receipt_sha256": execution_sha,
                    "execution_receipt_file_sha256": execution_file_sha,
                    "evaluation_configuration_sha256": _sha(
                        "posebusters-evaluation-configuration"
                    ),
                }
            )
        evaluation_shas[engine], _ = _write_receipt(
            evaluation_paths[engine],
            evaluation_payload,
        )

    target_rows = []
    for case_id in case_ids:
        annotated = case_id == first
        target_rows.append(
            {
                "case_id": case_id,
                "pdb_id": case_id.split("_", 1)[0],
                "receptor_sha256": _sha(f"{case_id}:receptor_pdb"),
                "reference_ligand_sha256": _sha(
                    f"{case_id}:reference_ligand_sdf"
                ),
                "annotation_status": (
                    "pfam_annotated"
                    if annotated
                    else "uniprot_without_pfam"
                ),
                "pfam_ids": ["PF00001"] if annotated else [],
                "pfam_set_id": (
                    f"pfam_set_{_sha('PF00001')}" if annotated else None
                ),
            }
        )
    target_payload = _claim_closed(
        POSEBUSTERS_RCSB_TARGET_FAMILY_RECEIPT_SCHEMA_ID,
        target_rows,
    )
    target_payload.update(
        {
            "archive_intake_receipt_sha256": archive_sha,
            "target_family_metrics_present": True,
            "complete_target_family_annotation_coverage": False,
            "external_fit_training_leakage_audit_present": False,
            "leakage_control_passed": False,
        }
    )
    target_sha, _ = _write_receipt(target_path, target_payload)
    return {
        "archive_intake_receipt_path": archive_path,
        "preparation_receipt_path": preparation_path,
        "execution_receipt_paths": execution_paths,
        "evaluation_receipt_paths": evaluation_paths,
        "target_family_receipt_path": target_path,
        "expected_evaluation_receipt_sha256s": evaluation_shas,
        "expected_target_family_receipt_sha256": target_sha,
    }


def test_materializes_failure_inclusive_test_only_intake(
    tmp_path: Path,
) -> None:
    fixture = _fixture(tmp_path / "inputs")
    receipt = materialize_posebusters_pose_ranking_intake(**fixture)
    payload = receipt.to_dict()

    assert payload["configuration_sha256"] == (
        POSEBUSTERS_POSE_RANKING_INTAKE_CONFIGURATION_SHA256
    )
    assert payload["all_case_denominator"] == 308
    assert payload["engine_case_row_count"] == 924
    assert payload["intake_row_count"] == 924
    assert payload["successful_pose_row_count"] == 3
    assert payload["failure_row_count"] == 921
    assert payload["pfam_annotated_case_count"] == 1
    assert payload["split_role"] == "test"
    assert payload["test_labels_used_for_fit"] is False
    assert payload["calibration_fit_performed"] is False
    assert payload["calibration_partition_materialized"] is False
    assert payload["partition_materialization_blockers"] == list(
        POSEBUSTERS_POSE_RANKING_INTAKE_PARTITION_BLOCKERS
    )
    success_rows = [
        row for row in payload["intake_rows"] if row["status"] == "success"
    ]
    assert [row["engine_id"] for row in success_rows] == list(_ENGINES)
    assert success_rows[0]["score_component_order"] == [
        f"vina.{term}" for term in _TERM_ORDERS["vina"]
    ]
    assert success_rows[0]["pose_coordinate_sha256"] is None
    assert success_rows[0]["scaffold_sha256"] is None
    assert success_rows[0]["native_like"] is True
    failure = next(
        row for row in payload["intake_rows"] if row["status"] == "failure"
    )
    assert failure["score_component_order"] == []
    assert failure["native_like"] is None
    assert failure["failure_code"] == "unsupported_chemistry"
    top_1_metrics = [
        row
        for row in payload["metrics"]
        if row["metric_id"] == "top_1_native_like_case_rate"
    ]
    assert all(row["numerator"] == 1 for row in top_1_metrics)
    assert all(row["denominator"] == 308 for row in top_1_metrics)
    assert all(
        row["confidence_interval_low"]
        <= row["estimate"]
        <= row["confidence_interval_high"]
        for row in top_1_metrics
    )

    output = tmp_path / "intake.json"
    receipt.write_json(output)
    assert output.stat().st_mode & 0o777 == 0o600
    verified = verify_posebusters_pose_ranking_intake_receipt(
        intake_receipt_path=output,
        **fixture,
    )
    assert verified.fingerprint_sha256 == receipt.fingerprint_sha256


def test_rejects_evaluation_score_that_differs_from_execution(
    tmp_path: Path,
) -> None:
    fixture = _fixture(tmp_path / "inputs")
    evaluation_path = fixture["evaluation_receipt_paths"]["gnina"]
    evaluation = json.loads(evaluation_path.read_bytes())
    evaluation.pop("receipt_sha256")
    evaluation["case_rows"][0]["pose_results"][0][
        "score_components_binary64_hex"
    ][0] = (-7.0).hex()
    new_sha, _ = _write_receipt(evaluation_path, evaluation)
    fixture["expected_evaluation_receipt_sha256s"]["gnina"] = new_sha

    with pytest.raises(
        PoseBustersPoseRankingIntakeError,
        match="evaluation score differs from execution",
    ):
        materialize_posebusters_pose_ranking_intake(**fixture)


def test_rejects_wrong_caller_pinned_root_and_output_tampering(
    tmp_path: Path,
) -> None:
    fixture = _fixture(tmp_path / "inputs")
    wrong = dict(fixture)
    wrong["expected_target_family_receipt_sha256"] = "0" * 64
    with pytest.raises(
        PoseBustersPoseRankingIntakeError,
        match="source receipt identity is invalid",
    ):
        materialize_posebusters_pose_ranking_intake(**wrong)

    receipt = materialize_posebusters_pose_ranking_intake(**fixture)
    output = tmp_path / "intake.json"
    receipt.write_json(output)
    tampered = receipt.to_dict()
    tampered["intake_rows"][0]["native_like"] = False
    output.write_bytes(_canonical_bytes(tampered) + b"\n")
    output.chmod(0o600)
    with pytest.raises(
        PoseBustersPoseRankingIntakeError,
        match="differs from exact reconstruction",
    ):
        verify_posebusters_pose_ranking_intake_receipt(
            intake_receipt_path=output,
            **fixture,
        )

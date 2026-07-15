from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from betelgeuze_engine_v2.benchmark import (
    ExternalBaselineCase,
    ExternalBaselineContractError,
    ExternalBaselineEngine,
    ExternalBaselineReceipt,
    ExternalBaselineResultRow,
    ExternalBaselineWorkOrder,
    read_external_baseline_csv,
    validate_external_baseline_results,
)


def _engine() -> ExternalBaselineEngine:
    return ExternalBaselineEngine(
        engine_id="vina",
        engine_version="1.2.5",
        executable_sha256="a" * 64,
        container_image_digest="sha256:" + "b" * 64,
    )


def _cases() -> tuple[ExternalBaselineCase, ...]:
    return (
        ExternalBaselineCase("case-a", "T1", "L1", "c" * 64, "d" * 64),
        ExternalBaselineCase("case-b", "T2", "L2", "e" * 64, "f" * 64),
    )


def _work_order() -> ExternalBaselineWorkOrder:
    return ExternalBaselineWorkOrder(
        work_order_id="vina-fixture",
        engine=_engine(),
        cases=_cases(),
        command_template=(
            "vina",
            "--receptor",
            "{receptor_path}",
            "--ligand",
            "{ligand_path}",
            "--out",
            "{output_path}",
        ),
        score_direction="minimize",
        score_unit="kcal/mol_proxy",
        score_semantics="vina_native_affinity_score",
    )


def test_work_order_is_deterministic_non_executing_and_atomic(tmp_path: Path) -> None:
    work = _work_order()
    assert work.fingerprint_sha256 == _work_order().fingerprint_sha256
    payload = work.to_dict()
    assert payload["engine"] == {
        "engine_id": "vina",
        "engine_version": "1.2.5",
        "executable_sha256": "a" * 64,
        "container_image_digest": "sha256:" + "b" * 64,
    }
    assert payload["cases"][0]["receptor_sha256"] == "c" * 64
    assert payload["cases"][0]["ligand_sha256"] == "d" * 64
    assert payload["score_direction"] == "minimize"
    assert payload["score_unit"] == "kcal/mol_proxy"
    assert payload["score_semantics"] == "vina_native_affinity_score"
    for key in (
        "execution_enabled",
        "scientifically_validated",
        "benchmark_validated",
        "customer_execution_enabled",
        "docking_accuracy_claim_allowed",
        "claim_safe",
    ):
        assert payload[key] is False
    path = work.write_json(tmp_path / "work-order.json")
    assert path.exists()
    assert not list(tmp_path.glob(".work-order.json.tmp-*"))
    assert json.loads(path.read_text(encoding="utf-8"))["engine"]["engine_id"] == "vina"


def test_operator_results_preserve_failures_and_verify_pose_artifacts(tmp_path: Path) -> None:
    root = tmp_path / "artifacts"
    root.mkdir()
    pose = root / "case-a.pdbqt"
    pose.write_text("MODEL 1\nENDMDL\n", encoding="utf-8")
    pose_sha = hashlib.sha256(pose.read_bytes()).hexdigest()
    receipt = validate_external_baseline_results(
        _work_order(),
        (
            {
                "case_id": "case-a",
                "status": "success",
                "score": "-7.4",
                "pose_path": "case-a.pdbqt",
                "pose_sha256": pose_sha,
            },
            {
                "case_id": "case-b",
                "status": "failure",
                "error_code": "engine_exit_nonzero",
            },
        ),
        artifact_root=root,
    )
    assert receipt.success_count == 1
    assert receipt.failure_count == 1
    assert receipt.rows[0].pose_verified is True
    assert receipt.rows[0].pose_size_bytes == len(pose.read_bytes())
    assert receipt.rows[0].pose_sha256 == pose_sha
    assert receipt.rows[1].error_code == "engine_exit_nonzero"
    payload = receipt.to_dict()
    for key in (
        "scientifically_validated",
        "benchmark_validated",
        "customer_execution_enabled",
        "docking_accuracy_claim_allowed",
        "claim_safe",
    ):
        assert payload[key] is False
    assert len(payload["receipt_fingerprint_sha256"]) == 64


def test_result_validation_rejects_missing_duplicate_and_hash_mismatch(
    tmp_path: Path,
) -> None:
    root = tmp_path / "root"
    root.mkdir()
    pose = root / "pose.sdf"
    pose.write_text("pose", encoding="utf-8")
    valid = {
        "case_id": "case-a",
        "status": "success",
        "score": -1.0,
        "pose_path": "pose.sdf",
        "pose_sha256": hashlib.sha256(pose.read_bytes()).hexdigest(),
    }

    with pytest.raises(ExternalBaselineContractError, match="exactly"):
        validate_external_baseline_results(_work_order(), (valid,), artifact_root=root)
    with pytest.raises(ExternalBaselineContractError, match="unique"):
        validate_external_baseline_results(_work_order(), (valid, valid), artifact_root=root)

    mismatch = dict(valid)
    mismatch["pose_sha256"] = "0" * 64
    with pytest.raises(ExternalBaselineContractError, match="SHA-256 mismatch"):
        validate_external_baseline_results(
            _work_order(),
            (
                mismatch,
                {"case_id": "case-b", "status": "failure", "error_code": "blocked"},
            ),
            artifact_root=root,
        )


def test_result_validation_rejects_absolute_traversal_and_symlink_paths(
    tmp_path: Path,
) -> None:
    root = tmp_path / "root"
    root.mkdir()
    outside_dir = tmp_path / "outside"
    outside_dir.mkdir()
    outside = outside_dir / "outside.sdf"
    outside.write_text("secret", encoding="utf-8")
    outside_sha = hashlib.sha256(outside.read_bytes()).hexdigest()

    for pose_path in (str(outside), "../outside/outside.sdf"):
        with pytest.raises(ExternalBaselineContractError, match="relative path"):
            validate_external_baseline_results(
                _work_order(),
                (
                    {
                        "case_id": "case-a",
                        "status": "success",
                        "score": -1.0,
                        "pose_path": pose_path,
                        "pose_sha256": outside_sha,
                    },
                    {
                        "case_id": "case-b",
                        "status": "failure",
                        "error_code": "blocked",
                    },
                ),
                artifact_root=root,
            )

    final_link = root / "link.sdf"
    intermediate_link = root / "linked-directory"
    root_link = tmp_path / "root-link"
    try:
        final_link.symlink_to(outside)
        intermediate_link.symlink_to(outside_dir, target_is_directory=True)
        root_link.symlink_to(root, target_is_directory=True)
    except OSError:
        pytest.skip("symlinks unavailable")

    for pose_root, pose_path in (
        (root, "link.sdf"),
        (root, "linked-directory/outside.sdf"),
        (root_link, "missing.sdf"),
    ):
        with pytest.raises(ExternalBaselineContractError, match="symlink"):
            validate_external_baseline_results(
                _work_order(),
                (
                    {
                        "case_id": "case-a",
                        "status": "success",
                        "score": -1.0,
                        "pose_path": pose_path,
                        "pose_sha256": outside_sha,
                    },
                    {
                        "case_id": "case-b",
                        "status": "failure",
                        "error_code": "blocked",
                    },
                ),
                artifact_root=pose_root,
            )


def test_result_validation_rejects_contradictory_and_unknown_row_fields(
    tmp_path: Path,
) -> None:
    root = tmp_path / "root"
    root.mkdir()
    failure = {
        "case_id": "case-a",
        "status": "failure",
        "error_code": "engine_failed",
    }
    other_failure = {
        "case_id": "case-b",
        "status": "failure",
        "error_code": "blocked",
    }

    contradictory_failure = dict(failure, score=0)
    with pytest.raises(ExternalBaselineContractError, match="cannot contain score"):
        validate_external_baseline_results(
            _work_order(),
            (contradictory_failure, other_failure),
            artifact_root=root,
        )

    pose = root / "pose.sdf"
    pose.write_text("pose", encoding="utf-8")
    contradictory_success = {
        "case_id": "case-a",
        "status": "success",
        "score": -1.0,
        "pose_path": "pose.sdf",
        "pose_sha256": hashlib.sha256(pose.read_bytes()).hexdigest(),
        "error_code": "stale_error",
    }
    with pytest.raises(ExternalBaselineContractError, match="cannot contain error_code"):
        validate_external_baseline_results(
            _work_order(),
            (contradictory_success, other_failure),
            artifact_root=root,
        )

    with pytest.raises(ExternalBaselineContractError, match="unsupported fields"):
        validate_external_baseline_results(
            _work_order(),
            (dict(failure, operator_note="not in schema"), other_failure),
            artifact_root=root,
        )


def test_receipt_rejects_unverified_success_pose() -> None:
    rows = (
        ExternalBaselineResultRow(
            case_id="case-a",
            status="success",
            score=-1.0,
            pose_path="pose.sdf",
            pose_sha256="a" * 64,
            pose_size_bytes=4,
            pose_verified=False,
        ),
        ExternalBaselineResultRow(
            case_id="case-b",
            status="failure",
            error_code="blocked",
        ),
    )
    with pytest.raises(ExternalBaselineContractError, match="verified pose"):
        ExternalBaselineReceipt(work_order=_work_order(), rows=rows)


def test_csv_reader_is_standard_library_and_preserves_rows(tmp_path: Path) -> None:
    csv_path = tmp_path / "results.csv"
    csv_path.write_text(
        "case_id,status,score,pose_path,pose_sha256,error_code\n"
        "case-a,success,-7.0,pose.pdbqt," + "a" * 64 + ",\n"
        "case-b,failure,,,,engine_failed\n",
        encoding="utf-8",
    )
    rows = read_external_baseline_csv(csv_path)
    assert len(rows) == 2
    assert rows[0]["case_id"] == "case-a"
    assert rows[1]["error_code"] == "engine_failed"

    csv_path.write_text(
        "status,case_id,score,pose_path,pose_sha256,error_code\n",
        encoding="utf-8",
    )
    with pytest.raises(ExternalBaselineContractError, match="header"):
        read_external_baseline_csv(csv_path)


def test_engine_contract_rejects_unsupported_or_unfingerprinted_binary() -> None:
    with pytest.raises(ExternalBaselineContractError, match="unsupported"):
        ExternalBaselineEngine("autodock4", "4.2", "a" * 64)
    with pytest.raises(ExternalBaselineContractError, match="executable_sha256"):
        ExternalBaselineEngine("vina", "1.2", "")
    with pytest.raises(ExternalBaselineContractError, match="container_image_digest"):
        ExternalBaselineEngine("vina", "1.2", "a" * 64, "vina:latest")
    with pytest.raises(ExternalBaselineContractError, match="score_unit"):
        ExternalBaselineWorkOrder(
            work_order_id="missing-score-unit",
            engine=_engine(),
            cases=_cases(),
            command_template=(
                "vina",
                "{receptor_path}",
                "{ligand_path}",
                "{output_path}",
            ),
        )


def test_ci_owns_the_contract_without_external_engine_execution() -> None:
    dedicated_path = Path(".github/workflows/ci-engine-v2-external-baseline.yml")
    main_path = Path(".github/workflows/ci-engine-v2-main.yml")
    contract_path = Path("betelgeuze_engine_v2/benchmark/external_baseline.py")
    dedicated = dedicated_path.read_text(encoding="utf-8")
    main = main_path.read_text(encoding="utf-8")
    contract = contract_path.read_text(encoding="utf-8")

    assert "runs-on: ubuntu-latest" in dedicated
    assert "permissions:\n  contents: read" in dedicated
    assert (
        "uses: actions/checkout@34e114876b0b11c390a56381ad16ebd13914f8d5"
        in dedicated
    )
    assert (
        "uses: actions/setup-python@a26af69be951a213d495a4c3e4e4022e16d87065"
        in dedicated
    )
    assert "persist-credentials: false" in dedicated
    assert "clean: true" in dedicated
    assert "fetch-depth: 1" in dedicated
    for engine_id in ("vina", "gnina", "smina"):
        assert engine_id not in dedicated.lower()
    for execution_primitive in ("import subprocess", "os.system(", "Popen("):
        assert execution_primitive not in contract

    test_path = "tests/unit/test_engine_v2_external_baseline.py"
    assert main.count(test_path) >= 2
    assert str(dedicated_path) in main
    assert "from betelgeuze_engine_v2.benchmark import (" in main
    assert "ExternalBaselineEngine," in main

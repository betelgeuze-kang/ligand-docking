from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from betelgeuze_engine_v2.benchmark import (
    ExternalBaselineCase,
    ExternalBaselineContractError,
    ExternalBaselineEngine,
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
    assert work.to_dict()["execution_enabled"] is False
    assert work.to_dict()["claim_safe"] is False
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
    assert receipt.rows[1].error_code == "engine_exit_nonzero"
    payload = receipt.to_dict()
    assert payload["claim_safe"] is False
    assert len(payload["receipt_fingerprint_sha256"]) == 64


def test_result_validation_rejects_missing_duplicate_hash_mismatch_and_symlink(tmp_path: Path) -> None:
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

    outside = tmp_path / "outside.sdf"
    outside.write_text("secret", encoding="utf-8")
    link = root / "link.sdf"
    try:
        link.symlink_to(outside)
    except OSError:
        pytest.skip("symlinks unavailable")
    linked = dict(valid)
    linked["pose_path"] = "link.sdf"
    linked["pose_sha256"] = hashlib.sha256(outside.read_bytes()).hexdigest()
    with pytest.raises(ExternalBaselineContractError, match="symlink"):
        validate_external_baseline_results(
            _work_order(),
            (
                linked,
                {"case_id": "case-b", "status": "failure", "error_code": "blocked"},
            ),
            artifact_root=root,
        )


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


def test_engine_contract_rejects_unsupported_or_unfingerprinted_binary() -> None:
    with pytest.raises(ExternalBaselineContractError, match="unsupported"):
        ExternalBaselineEngine("autodock4", "4.2", "a" * 64)
    with pytest.raises(ExternalBaselineContractError, match="executable_sha256"):
        ExternalBaselineEngine("vina", "1.2", "")

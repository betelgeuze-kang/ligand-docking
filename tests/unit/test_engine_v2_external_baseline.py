from __future__ import annotations

import hashlib
import inspect
import json
from pathlib import Path

import pytest

import betelgeuze_engine_v2.benchmark.external_baseline as external_baseline
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


def test_case_metadata_is_deeply_immutable_and_fingerprint_stable() -> None:
    source = {"nested": {"values": [1, 2]}, "label": "original"}
    case = ExternalBaselineCase(
        "case-a",
        "T1",
        "L1",
        "c" * 64,
        "d" * 64,
        metadata=source,
    )
    work = ExternalBaselineWorkOrder(
        work_order_id="metadata-fixture",
        engine=_engine(),
        cases=(case,),
        command_template=(
            "vina",
            "{receptor_path}",
            "{ligand_path}",
            "{output_path}",
        ),
        score_unit="kcal/mol_proxy",
        score_semantics="vina_native_affinity_score",
    )
    fingerprint = work.fingerprint_sha256

    source["nested"]["values"].append(3)
    source["label"] = "mutated"
    detached = work.to_dict()
    detached["cases"][0]["metadata"]["nested"]["values"].append(4)

    assert work.fingerprint_sha256 == fingerprint
    assert case.to_dict()["metadata"] == {
        "label": "original",
        "nested": {"values": [1, 2]},
    }
    with pytest.raises(TypeError):
        case.metadata["label"] = "forbidden"
    with pytest.raises(TypeError):
        case.metadata["nested"]["extra"] = True


@pytest.mark.parametrize(
    "metadata",
    [
        {1: "numeric-key"},
        {"nested": {False: "boolean-key"}},
    ],
)
def test_case_metadata_rejects_non_string_keys_recursively(metadata: object) -> None:
    with pytest.raises(ExternalBaselineContractError, match="keys must be strings"):
        ExternalBaselineCase(
            "case-a",
            "T1",
            "L1",
            "c" * 64,
            "d" * 64,
            metadata=metadata,
        )


def test_case_metadata_key_order_has_one_canonical_fingerprint() -> None:
    def build(metadata: dict[str, object]) -> ExternalBaselineWorkOrder:
        case = ExternalBaselineCase(
            "case-a",
            "T1",
            "L1",
            "c" * 64,
            "d" * 64,
            metadata=metadata,
        )
        return ExternalBaselineWorkOrder(
            work_order_id="canonical-metadata",
            engine=_engine(),
            cases=(case,),
            command_template=(
                "vina",
                "{receptor_path}",
                "{ligand_path}",
                "{output_path}",
            ),
            score_unit="kcal/mol_proxy",
            score_semantics="vina_native_affinity_score",
        )

    assert build({"a": 1, "b": 2}).fingerprint_sha256 == build(
        {"b": 2, "a": 1}
    ).fingerprint_sha256


def test_case_metadata_rejects_cyclic_containers() -> None:
    cyclic_mapping: dict[str, object] = {}
    cyclic_mapping["self"] = cyclic_mapping
    cyclic_list: list[object] = []
    cyclic_list.append(cyclic_list)

    for metadata in (cyclic_mapping, {"nested": cyclic_list}):
        with pytest.raises(ExternalBaselineContractError, match="cyclic"):
            ExternalBaselineCase(
                "case-a",
                "T1",
                "L1",
                "c" * 64,
                "d" * 64,
                metadata=metadata,
            )


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


def test_result_validation_rejects_root_symlink_hidden_by_parent_component(
    tmp_path: Path,
) -> None:
    base = tmp_path / "base"
    base.mkdir()
    outside = tmp_path / "outside"
    nested = outside / "nested"
    artifacts = outside / "artifacts"
    nested.mkdir(parents=True)
    artifacts.mkdir()
    pose = artifacts / "pose.sdf"
    pose.write_bytes(b"outside pose")
    alias = base / "alias"
    try:
        alias.symlink_to(nested, target_is_directory=True)
    except OSError:
        pytest.skip("symlinks unavailable")

    disguised_root = alias / ".." / "artifacts"
    with pytest.raises(ExternalBaselineContractError, match=r"artifact_root.*'\.\.'"):
        validate_external_baseline_results(
            ExternalBaselineWorkOrder(
                work_order_id="root-parent-bypass",
                engine=_engine(),
                cases=(_cases()[0],),
                command_template=(
                    "vina",
                    "{receptor_path}",
                    "{ligand_path}",
                    "{output_path}",
                ),
                score_unit="kcal/mol_proxy",
                score_semantics="vina_native_affinity_score",
            ),
            (
                {
                    "case_id": "case-a",
                    "status": "success",
                    "score": -1.0,
                    "pose_path": "pose.sdf",
                    "pose_sha256": hashlib.sha256(pose.read_bytes()).hexdigest(),
                },
            ),
            artifact_root=disguised_root,
        )


def test_result_validation_rejects_final_component_swap_before_open(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "root"
    root.mkdir()
    pose = root / "pose.sdf"
    pose.write_bytes(b"inside")
    outside = tmp_path / "outside.sdf"
    outside.write_bytes(b"outside")
    outside_sha = hashlib.sha256(outside.read_bytes()).hexdigest()
    real_open_regular = external_baseline._open_regular_at
    swapped = False

    def racing_open(parent_fd: int, component: str) -> int:
        nonlocal swapped
        if component == "pose.sdf" and not swapped:
            pose.unlink()
            pose.symlink_to(outside)
            swapped = True
        return real_open_regular(parent_fd, component)

    monkeypatch.setattr(external_baseline, "_open_regular_at", racing_open)
    with pytest.raises(ExternalBaselineContractError, match="symlink"):
        validate_external_baseline_results(
            ExternalBaselineWorkOrder(
                work_order_id="final-swap",
                engine=_engine(),
                cases=(_cases()[0],),
                command_template=(
                    "vina",
                    "{receptor_path}",
                    "{ligand_path}",
                    "{output_path}",
                ),
                score_unit="kcal/mol_proxy",
                score_semantics="vina_native_affinity_score",
            ),
            (
                {
                    "case_id": "case-a",
                    "status": "success",
                    "score": -1.0,
                    "pose_path": "pose.sdf",
                    "pose_sha256": outside_sha,
                },
            ),
            artifact_root=root,
        )
    assert swapped is True


def test_result_validation_hashes_open_descriptor_after_path_replacement(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "root"
    root.mkdir()
    pose = root / "pose.sdf"
    original_bytes = b"descriptor-owned pose"
    pose.write_bytes(original_bytes)
    outside = tmp_path / "outside.sdf"
    outside.write_bytes(b"replacement")
    original_sha = hashlib.sha256(original_bytes).hexdigest()
    real_open_regular = external_baseline._open_regular_at
    swapped = False

    def open_then_replace(parent_fd: int, component: str) -> int:
        nonlocal swapped
        file_fd = real_open_regular(parent_fd, component)
        if component == "pose.sdf" and not swapped:
            pose.rename(root / "pose-original.sdf")
            pose.symlink_to(outside)
            swapped = True
        return file_fd

    monkeypatch.setattr(external_baseline, "_open_regular_at", open_then_replace)
    receipt = validate_external_baseline_results(
        ExternalBaselineWorkOrder(
            work_order_id="same-fd-hash",
            engine=_engine(),
            cases=(_cases()[0],),
            command_template=(
                "vina",
                "{receptor_path}",
                "{ligand_path}",
                "{output_path}",
            ),
            score_unit="kcal/mol_proxy",
            score_semantics="vina_native_affinity_score",
        ),
        (
            {
                "case_id": "case-a",
                "status": "success",
                "score": -1.0,
                "pose_path": "pose.sdf",
                "pose_sha256": original_sha,
            },
        ),
        artifact_root=root,
    )
    assert swapped is True
    assert receipt.rows[0].pose_sha256 == original_sha
    assert receipt.rows[0].pose_size_bytes == len(original_bytes)


def test_result_validation_rejects_intermediate_component_swap_before_open(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "root"
    inside = root / "inside"
    inside.mkdir(parents=True)
    (inside / "pose.sdf").write_bytes(b"inside")
    outside = tmp_path / "outside"
    outside.mkdir()
    outside_pose = outside / "pose.sdf"
    outside_pose.write_bytes(b"outside")
    outside_sha = hashlib.sha256(outside_pose.read_bytes()).hexdigest()
    real_open_directory = external_baseline._open_directory_at
    swapped = False

    def racing_open(parent_fd: int, component: str, *, scope: str) -> int:
        nonlocal swapped
        if component == "inside" and not swapped:
            inside.rename(root / "inside-original")
            inside.symlink_to(outside, target_is_directory=True)
            swapped = True
        return real_open_directory(parent_fd, component, scope=scope)

    monkeypatch.setattr(external_baseline, "_open_directory_at", racing_open)
    with pytest.raises(ExternalBaselineContractError, match="symlink"):
        validate_external_baseline_results(
            ExternalBaselineWorkOrder(
                work_order_id="intermediate-swap",
                engine=_engine(),
                cases=(_cases()[0],),
                command_template=(
                    "vina",
                    "{receptor_path}",
                    "{ligand_path}",
                    "{output_path}",
                ),
                score_unit="kcal/mol_proxy",
                score_semantics="vina_native_affinity_score",
            ),
            (
                {
                    "case_id": "case-a",
                    "status": "success",
                    "score": -1.0,
                    "pose_path": "inside/pose.sdf",
                    "pose_sha256": outside_sha,
                },
            ),
            artifact_root=root,
        )
    assert swapped is True


def test_result_validation_keeps_open_intermediate_directory_descriptor(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "root"
    inside = root / "inside"
    inside.mkdir(parents=True)
    original_bytes = b"descriptor-owned directory pose"
    (inside / "pose.sdf").write_bytes(original_bytes)
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "pose.sdf").write_bytes(b"outside replacement")
    probe = tmp_path / "symlink-probe"
    try:
        probe.symlink_to(outside, target_is_directory=True)
        probe.unlink()
    except OSError:
        pytest.skip("symlinks unavailable")

    original_sha = hashlib.sha256(original_bytes).hexdigest()
    real_open_directory = external_baseline._open_directory_at
    swapped = False

    def open_then_replace(parent_fd: int, component: str, *, scope: str) -> int:
        nonlocal swapped
        directory_fd = real_open_directory(parent_fd, component, scope=scope)
        if component == "inside" and not swapped:
            inside.rename(root / "inside-original")
            inside.symlink_to(outside, target_is_directory=True)
            swapped = True
        return directory_fd

    monkeypatch.setattr(external_baseline, "_open_directory_at", open_then_replace)
    receipt = validate_external_baseline_results(
        ExternalBaselineWorkOrder(
            work_order_id="intermediate-same-fd",
            engine=_engine(),
            cases=(_cases()[0],),
            command_template=(
                "vina",
                "{receptor_path}",
                "{ligand_path}",
                "{output_path}",
            ),
            score_unit="kcal/mol_proxy",
            score_semantics="vina_native_affinity_score",
        ),
        (
            {
                "case_id": "case-a",
                "status": "success",
                "score": -1.0,
                "pose_path": "inside/pose.sdf",
                "pose_sha256": original_sha,
            },
        ),
        artifact_root=root,
    )
    assert swapped is True
    assert receipt.rows[0].pose_sha256 == original_sha
    assert receipt.rows[0].pose_size_bytes == len(original_bytes)


def test_final_component_open_uses_nonblocking_nofollow_flags(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    if any(
        not hasattr(external_baseline.os, name)
        for name in ("O_NOFOLLOW", "O_NONBLOCK")
    ):
        pytest.skip("secure POSIX open flags unavailable")
    observed: dict[str, int | str] = {}

    def fake_open(component: str, flags: int, *, dir_fd: int) -> int:
        observed.update(component=component, flags=flags, dir_fd=dir_fd)
        return 23

    monkeypatch.setattr(external_baseline.os, "open", fake_open)
    assert external_baseline._open_regular_at(17, "pose.fifo") == 23
    assert observed == {
        "component": "pose.fifo",
        "flags": observed["flags"],
        "dir_fd": 17,
    }
    assert int(observed["flags"]) & external_baseline.os.O_NOFOLLOW
    assert int(observed["flags"]) & external_baseline.os.O_NONBLOCK


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
        ),
        ExternalBaselineResultRow(
            case_id="case-b",
            status="failure",
            error_code="blocked",
        ),
    )
    with pytest.raises(ExternalBaselineContractError, match="verified pose"):
        ExternalBaselineReceipt(work_order=_work_order(), rows=rows)


def test_direct_verified_row_and_receipt_construction_are_rejected() -> None:
    assert not hasattr(external_baseline, "_VALIDATED_RECEIPT_TOKEN")
    assert inspect.getclosurevars(
        validate_external_baseline_results
    ).nonlocals == {}
    row_parameters = inspect.signature(ExternalBaselineResultRow).parameters
    receipt_parameters = inspect.signature(ExternalBaselineReceipt).parameters
    assert "pose_size_bytes" not in row_parameters
    assert "pose_verified" not in row_parameters
    assert "_verification_token" not in row_parameters
    assert "_validation_token" not in receipt_parameters

    leaked_token = getattr(external_baseline, "_VALIDATED_RECEIPT_TOKEN", object())
    with pytest.raises(TypeError):
        ExternalBaselineResultRow(
            case_id="case-a",
            status="success",
            score=-1.0,
            pose_path="never-existed.sdf",
            pose_sha256="a" * 64,
            pose_size_bytes=123,
            pose_verified=True,
            _verification_token=leaked_token,
        )

    failure_rows = (
        ExternalBaselineResultRow(
            case_id="case-a",
            status="failure",
            error_code="blocked",
        ),
        ExternalBaselineResultRow(
            case_id="case-b",
            status="failure",
            error_code="blocked",
        ),
    )
    with pytest.raises(ExternalBaselineContractError, match="result validation"):
        ExternalBaselineReceipt(work_order=_work_order(), rows=failure_rows)


@pytest.mark.parametrize("score", [True, False])
def test_boolean_scores_are_rejected_by_rows_and_result_validation(
    tmp_path: Path,
    score: bool,
) -> None:
    with pytest.raises(ExternalBaselineContractError, match="non-boolean"):
        ExternalBaselineResultRow(
            case_id="case-a",
            status="success",
            score=score,
            pose_path="pose.sdf",
            pose_sha256="a" * 64,
        )

    root = tmp_path / "root"
    root.mkdir()
    with pytest.raises(ExternalBaselineContractError, match="numeric data"):
        validate_external_baseline_results(
            _work_order(),
            (
                {
                    "case_id": "case-a",
                    "status": "success",
                    "score": score,
                    "pose_path": "pose.sdf",
                    "pose_sha256": "a" * 64,
                },
                {
                    "case_id": "case-b",
                    "status": "failure",
                    "error_code": "blocked",
                },
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
    assert "python -m pip install pip==25.0.1" in dedicated
    for engine_id in ("vina", "gnina", "smina"):
        assert engine_id not in dedicated.lower()
    for execution_primitive in ("import subprocess", "os.system(", "Popen("):
        assert execution_primitive not in contract

    test_path = "tests/unit/test_engine_v2_external_baseline.py"
    assert main.count(test_path) >= 2
    assert str(dedicated_path) in main
    assert "from betelgeuze_engine_v2.benchmark import (" in main
    assert "ExternalBaselineEngine," in main

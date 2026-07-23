from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path
import zipfile

import pytest


pytest.importorskip("torch")

from betelgeuze_engine_v2.benchmark.public_posebusters_external_binary_execution import (  # noqa: E402
    POSEBUSTERS_EXTERNAL_BINARY_EXECUTION_SCHEMA_ID,
)
from betelgeuze_engine_v2.benchmark.public_posebusters_external_preparation import (  # noqa: E402
    POSEBUSTERS_EXTERNAL_PREPARATION_SCHEMA_ID,
)
from betelgeuze_engine_v2.benchmark.public_posebusters_intake import (  # noqa: E402
    POSEBUSTERS_ARCHIVE_INTAKE_SCHEMA_ID,
)
from betelgeuze_engine_v2.benchmark.public_posebusters_pose_ranking_intake import (  # noqa: E402
    POSEBUSTERS_POSE_RANKING_INTAKE_RECEIPT_SCHEMA_ID,
)
from betelgeuze_engine_v2.benchmark.public_posebusters_pose_scaffold_identity import (  # noqa: E402
    POSEBUSTERS_POSE_SCAFFOLD_IDENTITY_CONFIGURATION_SHA256,
    POSEBUSTERS_POSE_SCAFFOLD_IDENTITY_REMAINING_PARTITION_BLOCKERS,
    PoseBustersPoseScaffoldIdentityError,
    _ChemistryIdentity,
    _parse_model,
    _split_models,
    materialize_posebusters_pose_scaffold_identity,
    verify_posebusters_pose_scaffold_identity_receipt,
)
from betelgeuze_engine_v2.benchmark.public_posebusters_prepared_ligand_diagnostic import (  # noqa: E402
    PoseBustersPreparedLigandRuntimeIdentity,
    PoseBustersPreparedLigandRuntimePayload,
)
from betelgeuze_engine_v2.benchmark.public_posebusters_vina_execution import (  # noqa: E402
    POSEBUSTERS_VINA_EXECUTION_SCHEMA_ID,
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
) -> tuple[str, str]:
    source_payload = dict(payload)
    receipt_sha = _canonical_sha(source_payload)
    source_payload["receipt_sha256"] = receipt_sha
    source = _canonical_bytes(source_payload) + b"\n"
    path.write_bytes(source)
    path.chmod(0o600)
    return receipt_sha, _sha(source)


def _claim_closed(
    schema_id: str,
    **values: object,
) -> dict[str, object]:
    return {
        "schema_id": schema_id,
        **values,
        "scientifically_validated": False,
        "claim_safe": False,
    }


def _case_ids() -> tuple[str, ...]:
    return tuple(f"A{index:03d}_L{index:03d}" for index in range(308))


def _pdbqt_model(
    *,
    score_remark: str = "REMARK SCORE 1.0",
    x: str = "0.000",
) -> bytes:
    atom = (
        "ATOM      1  C   UNL     1    "
        f"{float(x):8.3f}{1.0:8.3f}{2.0:8.3f}"
        "  1.00  0.00     0.000 C "
    )
    return (
        "\n".join(
            (
                "MODEL 1",
                score_remark,
                "REMARK SMILES C",
                "REMARK SMILES IDX 1 1",
                "ROOT",
                atom,
                "ENDROOT",
                "TORSDOF 0",
                "ENDMDL",
                "",
            )
        )
    ).encode("ascii")


def _chemistry() -> _ChemistryIdentity:
    scaffold_sha = _canonical_sha(
        {
            "schema_id": ("betelgeuze.engine_v2_ligand_scaffold_identity/1.0.0"),
            "kind": "acyclic_full_heavy_graph",
            "canonical_nonisomeric_smiles": "C",
        }
    )
    return _ChemistryIdentity(
        canonical_isomeric_smiles="C",
        canonical_nonisomeric_smiles="C",
        atomic_numbers=(6,),
        formal_charge=0,
        scaffold_kind="acyclic_full_heavy_graph",
        scaffold_representation="C",
        scaffold_sha256=scaffold_sha,
    )


class _FakeRuntime:
    def __init__(self) -> None:
        payload = PoseBustersPreparedLigandRuntimePayload(
            distribution_name="rdkit",
            distribution_version="2025.9.6",
            payload_sha256=_sha("rdkit-payload"),
            payload_file_count=10,
            payload_size_bytes=100,
        )
        self.identity = PoseBustersPreparedLigandRuntimeIdentity(
            python_implementation="CPython",
            python_version="3.10.12",
            python_cache_tag="cpython-310",
            python_executable_sha256=_sha("python"),
            python_executable_size_bytes=1_000,
            platform_system="Linux",
            platform_machine="x86_64",
            libc_name="glibc",
            libc_version="2.35",
            filesystem_encoding="utf-8",
            rdkit_version="2025.09.6",
            rdkit_build="test-build",
            boost_version="1_85",
            rdkit_payload=payload,
        )

    def from_sdf(self, payload: bytes) -> _ChemistryIdentity:
        assert payload == b"fake-sdf\n"
        return _chemistry()

    def from_smiles(self, smiles: str) -> _ChemistryIdentity:
        assert smiles == "C"
        return _chemistry()


def _fixture(root: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, object]:
    from betelgeuze_engine_v2.benchmark import (
        public_posebusters_pose_scaffold_identity as module,
    )

    root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(module, "_load_scaffold_runtime", _FakeRuntime)
    runtime = _FakeRuntime().identity
    case_ids = _case_ids()
    first = case_ids[0]
    archive_path = root / "posebusters.zip"
    archive_buffer = io.BytesIO()
    archive_rows: list[dict[str, object]] = []
    with zipfile.ZipFile(
        archive_buffer,
        "w",
        compression=zipfile.ZIP_STORED,
    ) as archive:
        for case_id in case_ids:
            artifacts = []
            for role, suffix in (
                ("ligand_start_conformer_sdf", "start.sdf"),
                ("reference_ligand_sdf", "reference.sdf"),
            ):
                member = f"cases/{case_id}/{suffix}"
                payload = b"fake-sdf\n"
                archive.writestr(member, payload)
                artifacts.append(
                    {
                        "role": role,
                        "member_path": member,
                        "sha256": _sha(payload),
                        "size_bytes": len(payload),
                    }
                )
            archive_rows.append(
                {
                    "case_id": case_id,
                    "status": "ready",
                    "artifacts": artifacts,
                }
            )
    archive_source = archive_buffer.getvalue()
    archive_path.write_bytes(archive_source)
    archive_path.chmod(0o600)

    archive_receipt_path = root / "archive.json"
    archive_receipt_sha, archive_receipt_file_sha = _write_receipt(
        archive_receipt_path,
        _claim_closed(
            POSEBUSTERS_ARCHIVE_INTAKE_SCHEMA_ID,
            all_case_denominator=308,
            ready_case_count=308,
            archive_observed_sha256=_sha(archive_source),
            archive_observed_size_bytes=len(archive_source),
            case_rows=archive_rows,
        ),
    )

    preparation_receipt_path = root / "preparation.json"
    preparation_runtime = {
        "dependencies": [
            {
                "distribution_name": "rdkit",
                "version": runtime.rdkit_payload.distribution_version,
                "payload_sha256": runtime.rdkit_payload.payload_sha256,
                "payload_file_count": runtime.rdkit_payload.payload_file_count,
                "payload_size_bytes": runtime.rdkit_payload.payload_size_bytes,
            }
        ],
        "python_implementation": runtime.python_implementation,
        "python_version": runtime.python_version,
        "python_cache_tag": runtime.python_cache_tag,
        "python_executable_sha256": runtime.python_executable_sha256,
        "python_executable_size_bytes": runtime.python_executable_size_bytes,
        "platform_system": runtime.platform_system,
        "platform_machine": runtime.platform_machine,
        "libc_name": runtime.libc_name,
        "libc_version": runtime.libc_version,
        "filesystem_encoding": runtime.filesystem_encoding,
    }
    preparation_receipt_sha, preparation_receipt_file_sha = _write_receipt(
        preparation_receipt_path,
        _claim_closed(
            POSEBUSTERS_EXTERNAL_PREPARATION_SCHEMA_ID,
            all_case_denominator=308,
            archive_intake_receipt_sha256=archive_receipt_sha,
            runtime_identity=preparation_runtime,
            runtime_identity_sha256=_canonical_sha(preparation_runtime),
            case_rows=[
                {
                    "case_id": case_id,
                    "status": (
                        "prepared" if case_id == first else "abstain_chemistry_scope"
                    ),
                }
                for case_id in case_ids
            ],
        ),
    )

    execution_receipt_paths: dict[str, Path] = {}
    execution_artifact_roots: dict[str, Path] = {}
    execution_receipt_shas: dict[str, str] = {}
    execution_receipt_file_shas: dict[str, str] = {}
    for engine in _ENGINES:
        artifact_root = root / f"{engine}-artifacts"
        artifact_root.mkdir(mode=0o700)
        execution_artifact_roots[engine] = artifact_root
        pose_payload = _pdbqt_model(score_remark=f"REMARK {engine} SCORE 1")
        pose_path = artifact_root / first / "poses.pdbqt"
        pose_path.parent.mkdir()
        pose_path.write_bytes(pose_payload)
        pose_path.chmod(0o600)
        execution_rows = []
        for case_id in case_ids:
            success = case_id == first
            execution_rows.append(
                {
                    "case_id": case_id,
                    "status": ("success" if success else "abstain_chemistry_scope"),
                    "pose_count": 1 if success else 0,
                    "pose_artifact": (
                        {
                            "relative_path": f"{case_id}/poses.pdbqt",
                            "sha256": _sha(pose_payload),
                            "size_bytes": len(pose_payload),
                        }
                        if success
                        else None
                    ),
                }
            )
        schema_id = (
            POSEBUSTERS_VINA_EXECUTION_SCHEMA_ID
            if engine == "vina"
            else POSEBUSTERS_EXTERNAL_BINARY_EXECUTION_SCHEMA_ID
        )
        execution_path = root / f"{engine}-execution.json"
        execution_receipt_paths[engine] = execution_path
        (
            execution_receipt_shas[engine],
            execution_receipt_file_shas[engine],
        ) = _write_receipt(
            execution_path,
            _claim_closed(
                schema_id,
                all_case_denominator=308,
                engine_id=engine,
                preparation_receipt_sha256=preparation_receipt_sha,
                preparation_receipt_file_sha256=(preparation_receipt_file_sha),
                case_rows=execution_rows,
            ),
        )

    ranking_receipt_path = root / "ranking.json"
    ranking_inputs = [
        {
            "role": "archive_intake",
            "source_schema_id": POSEBUSTERS_ARCHIVE_INTAKE_SCHEMA_ID,
            "source_receipt_sha256": archive_receipt_sha,
            "source_file_sha256": archive_receipt_file_sha,
        },
        {
            "role": "external_preparation",
            "source_schema_id": POSEBUSTERS_EXTERNAL_PREPARATION_SCHEMA_ID,
            "source_receipt_sha256": preparation_receipt_sha,
            "source_file_sha256": preparation_receipt_file_sha,
        },
    ]
    for engine in _ENGINES:
        ranking_inputs.append(
            {
                "role": f"{engine}_execution",
                "source_schema_id": (
                    POSEBUSTERS_VINA_EXECUTION_SCHEMA_ID
                    if engine == "vina"
                    else POSEBUSTERS_EXTERNAL_BINARY_EXECUTION_SCHEMA_ID
                ),
                "source_receipt_sha256": execution_receipt_shas[engine],
                "source_file_sha256": execution_receipt_file_shas[engine],
            }
        )
    ranking_rows = []
    for engine in _ENGINES:
        for case_id in case_ids:
            success = case_id == first
            ranking_rows.append(
                {
                    "row_id": (
                        f"{engine}:{case_id}:1"
                        if success
                        else f"{engine}:{case_id}:case_failure"
                    ),
                    "engine_id": engine,
                    "case_id": case_id,
                    "pose_rank": 1 if success else None,
                    "status": "success" if success else "failure",
                    "failure_code": (None if success else "unsupported_chemistry"),
                    "source_execution_status": (
                        "success" if success else "abstain_chemistry_scope"
                    ),
                    "source_evaluation_status": (
                        "evaluated" if success else "abstain_chemistry_scope"
                    ),
                    "source_pose_status": "evaluated" if success else None,
                    "source_disposition_code": (
                        "generated_pose_evaluated"
                        if success
                        else "unsupported_chemistry"
                    ),
                    "source_error_stage": "",
                    "source_error_type": "",
                    "source_error_message_sha256": "",
                }
            )
    ranking_receipt_sha, _ranking_file_sha = _write_receipt(
        ranking_receipt_path,
        _claim_closed(
            POSEBUSTERS_POSE_RANKING_INTAKE_RECEIPT_SCHEMA_ID,
            all_case_denominator=308,
            split_role="test",
            test_labels_used_for_fit=False,
            calibration_fit_performed=False,
            input_receipts=ranking_inputs,
            intake_rows=ranking_rows,
        ),
    )
    return {
        "archive_path": archive_path,
        "archive_intake_receipt_path": archive_receipt_path,
        "preparation_receipt_path": preparation_receipt_path,
        "execution_receipt_paths": execution_receipt_paths,
        "execution_artifact_roots": execution_artifact_roots,
        "ranking_intake_receipt_path": ranking_receipt_path,
        "expected_archive_intake_receipt_sha256": archive_receipt_sha,
        "expected_preparation_receipt_sha256": preparation_receipt_sha,
        "expected_execution_receipt_sha256s": execution_receipt_shas,
        "expected_ranking_intake_receipt_sha256": ranking_receipt_sha,
    }


def test_coordinate_projection_ignores_score_remark_but_not_coordinates() -> None:
    runtime = _FakeRuntime()
    first = _split_models(_pdbqt_model(score_remark="REMARK SCORE 1"))[0]
    second = _split_models(_pdbqt_model(score_remark="REMARK SCORE 2"))[0]
    moved = _split_models(_pdbqt_model(x="0.125"))[0]
    first_model = _parse_model(*first, runtime)
    second_model = _parse_model(*second, runtime)
    moved_model = _parse_model(*moved, runtime)

    assert first_model.topology_projection_sha256 == (
        second_model.topology_projection_sha256
    )
    assert first_model.pose_coordinate_sha256 == (second_model.pose_coordinate_sha256)
    assert first_model.pose_coordinate_sha256 != (moved_model.pose_coordinate_sha256)


def test_rejects_incomplete_mapping_and_bytes_outside_models() -> None:
    runtime = _FakeRuntime()
    missing_mapping = _pdbqt_model().replace(
        b"REMARK SMILES IDX 1 1\n",
        b"",
    )
    rank, lines = _split_models(missing_mapping)[0]
    with pytest.raises(
        PoseBustersPoseScaffoldIdentityError,
        match="mapping is incomplete",
    ):
        _parse_model(rank, lines, runtime)

    with pytest.raises(
        PoseBustersPoseScaffoldIdentityError,
        match="outside MODEL",
    ):
        _split_models(b"REMARK outside\n" + _pdbqt_model())


def test_materializes_failure_inclusive_identity_overlay(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _fixture(tmp_path / "inputs", monkeypatch)
    receipt = materialize_posebusters_pose_scaffold_identity(**fixture)
    payload = receipt.to_dict()

    assert payload["configuration_sha256"] == (
        POSEBUSTERS_POSE_SCAFFOLD_IDENTITY_CONFIGURATION_SHA256
    )
    assert payload["all_case_denominator"] == 308
    assert payload["identity_row_count"] == 924
    assert payload["successful_pose_identity_count"] == 3
    assert payload["explicit_failure_identity_count"] == 921
    assert payload["unique_pose_coordinate_count"] == 1
    assert payload["duplicate_pose_coordinate_group_count"] == 1
    assert payload["scaffold_identified_case_count"] == 308
    assert payload["unique_scaffold_count"] == 1
    assert payload["acyclic_full_heavy_graph_case_count"] == 308
    assert payload["pose_coordinate_identity_complete"] is True
    assert payload["scaffold_identity_complete"] is True
    assert payload["ranking_intake_identity_binding_complete"] is True
    assert payload["remaining_partition_materialization_blockers"] == list(
        POSEBUSTERS_POSE_SCAFFOLD_IDENTITY_REMAINING_PARTITION_BLOCKERS
    )
    assert payload["test_labels_used_for_fit"] is False
    assert payload["calibration_partition_materialized"] is False
    success = next(
        row for row in payload["identity_rows"] if row["status"] == "identified_pose"
    )
    assert success["pose_coordinate_sha256"] is not None
    assert success["accepted_scaffold_sha256"] is not None
    failure = next(
        row for row in payload["identity_rows"] if row["status"] == "upstream_failure"
    )
    assert failure["pose_coordinate_sha256"] is None
    assert failure["failure_code"] == "unsupported_chemistry"
    assert failure["source_disposition_code"] == "unsupported_chemistry"

    output = tmp_path / "identity.json"
    receipt.write_json(output)
    assert output.stat().st_mode & 0o777 == 0o600
    verified = verify_posebusters_pose_scaffold_identity_receipt(
        identity_receipt_path=output,
        **fixture,
    )
    assert verified.fingerprint_sha256 == receipt.fingerprint_sha256


def test_rejects_wrong_pin_and_artifact_tampering(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _fixture(tmp_path / "inputs", monkeypatch)
    wrong = dict(fixture)
    wrong["expected_ranking_intake_receipt_sha256"] = "0" * 64
    with pytest.raises(
        PoseBustersPoseScaffoldIdentityError,
        match="source receipt is invalid",
    ):
        materialize_posebusters_pose_scaffold_identity(**wrong)

    pose_path = (
        fixture["execution_artifact_roots"]["vina"] / _case_ids()[0] / "poses.pdbqt"
    )
    pose_path.write_bytes(_pdbqt_model(x="0.125"))
    pose_path.chmod(0o600)
    with pytest.raises(
        PoseBustersPoseScaffoldIdentityError,
        match="artifact identity changed",
    ):
        materialize_posebusters_pose_scaffold_identity(**fixture)

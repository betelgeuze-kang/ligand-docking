from __future__ import annotations

import hashlib
import json
from pathlib import Path
import stat
import zipfile

import pytest


pytest.importorskip("torch")

from betelgeuze_engine_v2.benchmark.public_posebusters_intake import (  # noqa: E402
    OFFICIAL_POSEBUSTERS_ARCHIVE_CONTRACT,
    POSEBUSTERS_ARCHIVE_MEMBER_ROLES,
    POSEBUSTERS_ARCHIVE_ROLE_SUFFIXES,
    PoseBustersArchiveContract,
    PoseBustersArchiveIntakeError,
    materialize_posebusters_archive_intake,
    verify_posebusters_archive_intake_receipt,
)
from betelgeuze_engine_v2.benchmark.public_split_provenance import (  # noqa: E402
    POSEBUSTERS_2023_308_CASE_ID_PROJECTION_SHA256,
    POSEBUSTERS_2023_308_SELECTION_SHA256,
    POSEBUSTERS_2023_ARCHIVE_SHA256,
    POSEBUSTERS_2023_ARCHIVE_SIZE_BYTES,
)


_CASE_IDS = ("1ABC_ABC", "2DEF_DEF")


def _sha(source: bytes) -> str:
    return hashlib.sha256(source).hexdigest()


def _canonical_sha(value: object) -> str:
    source = json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("ascii")
    return _sha(source)


def _fixture(
    root: Path,
    *,
    missing: tuple[str, str] | None = None,
    unsafe_member: bool = False,
) -> tuple[Path, Path, PoseBustersArchiveContract]:
    root.mkdir(parents=True, exist_ok=True)
    archive_path = root / "posebusters.zip"
    selection_path = root / "selection.txt"
    selection = ("\n".join(_CASE_IDS) + "\n").encode("ascii")
    selection_path.write_bytes(selection)
    readme = b"synthetic PoseBusters intake fixture\n"
    embedded_ids = selection
    with zipfile.ZipFile(
        archive_path,
        "w",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=9,
    ) as archive:
        archive.writestr("README.txt", readme)
        archive.writestr("posebusters_benchmark_set_ids.txt", embedded_ids)
        for case_id in _CASE_IDS:
            for role in POSEBUSTERS_ARCHIVE_MEMBER_ROLES:
                if missing == (case_id, role):
                    continue
                member = (
                    f"posebusters_benchmark_set/{case_id}/"
                    f"{case_id}{POSEBUSTERS_ARCHIVE_ROLE_SUFFIXES[role]}"
                )
                archive.writestr(member, f"{case_id}:{role}\n".encode("ascii"))
        if unsafe_member:
            archive.writestr("../escape.txt", b"bounded but unsafe\n")
    archive_source = archive_path.read_bytes()
    with zipfile.ZipFile(archive_path, "r") as archive:
        infos = archive.infolist()
        uncompressed_size = sum(
            info.file_size for info in infos if not info.is_dir()
        )
    return (
        archive_path,
        selection_path,
        PoseBustersArchiveContract(
            dataset_id="synthetic_posebusters_intake",
            archive_sha256=_sha(archive_source),
            archive_size_bytes=len(archive_source),
            selection_sha256=_sha(selection),
            selection_size_bytes=len(selection),
            case_id_projection_sha256=_canonical_sha(list(_CASE_IDS)),
            selected_case_count=len(_CASE_IDS),
            archive_entry_count=len(infos),
            archive_uncompressed_size_bytes=uncompressed_size,
            archive_benchmark_case_count=len(_CASE_IDS),
            benchmark_root="posebusters_benchmark_set",
            embedded_case_list_member="posebusters_benchmark_set_ids.txt",
            embedded_case_list_sha256=_sha(embedded_ids),
            readme_member="README.txt",
            readme_sha256=_sha(readme),
        ),
    )


def test_official_contract_freezes_published_archive_and_308_selection() -> None:
    contract = OFFICIAL_POSEBUSTERS_ARCHIVE_CONTRACT

    assert contract.archive_sha256 == POSEBUSTERS_2023_ARCHIVE_SHA256
    assert contract.archive_size_bytes == POSEBUSTERS_2023_ARCHIVE_SIZE_BYTES
    assert contract.selection_sha256 == POSEBUSTERS_2023_308_SELECTION_SHA256
    assert (
        contract.case_id_projection_sha256
        == POSEBUSTERS_2023_308_CASE_ID_PROJECTION_SHA256
    )
    assert contract.selected_case_count == 308
    assert contract.archive_benchmark_case_count == 428
    assert contract.archive_entry_count == 2570
    assert contract.archive_uncompressed_size_bytes == 214_916_765
    assert contract.to_dict()["archive_extraction_allowed"] is False


def test_extraction_free_intake_streams_every_selected_case_artifact(
    tmp_path: Path,
) -> None:
    archive_path, selection_path, contract = _fixture(tmp_path)

    receipt = materialize_posebusters_archive_intake(
        archive_path,
        selection_path,
        contract=contract,
    )

    assert receipt.global_error_codes == ()
    assert receipt.ready_case_count == 2
    assert [row.case_id for row in receipt.case_rows] == list(_CASE_IDS)
    assert all(row.status == "ready" for row in receipt.case_rows)
    assert all(
        tuple(artifact.role for artifact in row.artifacts)
        == POSEBUSTERS_ARCHIVE_MEMBER_ROLES
        for row in receipt.case_rows
    )
    assert receipt.official_contract is False
    assert receipt.input_identity_ready is False
    payload = receipt.to_dict()
    assert payload["archive_extracted"] is False
    assert payload["network_fetch_performed"] is False
    assert payload["license_acceptance_performed"] is False
    assert payload["pose_generation_performed"] is False
    assert payload["benchmark_executed"] is False
    assert payload["claim_safe"] is False
    assert "non_official_archive_contract" in payload["scientific_blockers"]


def test_receipt_is_private_no_overwrite_and_exactly_reexecutable(
    tmp_path: Path,
) -> None:
    archive_path, selection_path, contract = _fixture(tmp_path / "source")
    receipt = materialize_posebusters_archive_intake(
        archive_path,
        selection_path,
        contract=contract,
    )
    output = tmp_path / "receipts" / "intake.json"

    receipt.write_json(output)

    assert stat.S_IMODE(output.stat().st_mode) == 0o600
    verified = verify_posebusters_archive_intake_receipt(
        output,
        archive_path,
        selection_path,
        contract=contract,
    )
    assert verified.fingerprint_sha256 == receipt.fingerprint_sha256
    with pytest.raises(PoseBustersArchiveIntakeError, match="already exists"):
        receipt.write_json(output)
    output.write_bytes(output.read_bytes().replace(b'"claim_safe":false', b'"claim_safe":true'))
    with pytest.raises(PoseBustersArchiveIntakeError, match="exact reexecution"):
        verify_posebusters_archive_intake_receipt(
            output,
            archive_path,
            selection_path,
            contract=contract,
        )


def test_missing_case_member_retains_all_rows_and_fails_only_that_case(
    tmp_path: Path,
) -> None:
    archive_path, selection_path, contract = _fixture(
        tmp_path,
        missing=("2DEF_DEF", "reference_ligands_sdf"),
    )

    receipt = materialize_posebusters_archive_intake(
        archive_path,
        selection_path,
        contract=contract,
    )

    assert len(receipt.case_rows) == 2
    assert receipt.ready_case_count == 1
    assert receipt.case_rows[0].status == "ready"
    assert receipt.case_rows[1].status == "failure"
    assert receipt.case_rows[1].error_codes == ("reference_ligands_sdf_missing",)
    assert receipt.input_identity_ready is False


def test_unsafe_archive_member_fails_every_selected_case_without_extraction(
    tmp_path: Path,
) -> None:
    archive_path, selection_path, contract = _fixture(
        tmp_path,
        unsafe_member=True,
    )

    receipt = materialize_posebusters_archive_intake(
        archive_path,
        selection_path,
        contract=contract,
    )

    assert receipt.global_error_codes == ("archive_structure_verification_failed",)
    assert receipt.ready_case_count == 0
    assert len(receipt.case_rows) == 2
    assert all(row.status == "failure" for row in receipt.case_rows)
    assert all(
        row.error_codes == ("archive_structure_verification_failed",)
        for row in receipt.case_rows
    )


def test_archive_and_selection_identity_mismatches_fail_closed(tmp_path: Path) -> None:
    archive_path, selection_path, contract = _fixture(tmp_path / "archive")
    with archive_path.open("ab") as handle:
        handle.write(b"tamper")

    receipt = materialize_posebusters_archive_intake(
        archive_path,
        selection_path,
        contract=contract,
    )

    assert receipt.global_error_codes == ("archive_identity_verification_failed",)
    assert len(receipt.case_rows) == 2
    assert all(row.status == "failure" for row in receipt.case_rows)

    archive_path, selection_path, contract = _fixture(tmp_path / "selection")
    selection_path.write_bytes(b"1ABC_ABC\n2DEF_DEX\n")
    with pytest.raises(PoseBustersArchiveIntakeError, match="frozen identity"):
        materialize_posebusters_archive_intake(
            archive_path,
            selection_path,
            contract=contract,
        )

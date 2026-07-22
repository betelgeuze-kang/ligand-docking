from __future__ import annotations

from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path

import pytest

from betelgeuze_engine_v2.benchmark.public_protocol import (
    POSEBUSTERS_SOURCE_COMMIT_SHA,
    FrozenPublicBenchmarkProtocol,
    PublicBenchmarkArtifact,
    PublicBenchmarkCaseDefinition,
)
from betelgeuze_engine_v2.benchmark.public_suite_materialization import (
    PUBLIC_BENCHMARK_SUITE_MATERIALIZATION_SCIENTIFIC_BLOCKERS,
    PublicBenchmarkSuiteMaterializationError,
    PublicBenchmarkSuiteMaterializationReceipt,
    main,
    materialize_public_benchmark_input_suite,
    materialize_public_benchmark_input_suite_from_directory,
    write_public_benchmark_input_suite_receipt,
)


_VALID_SDF = b"""one-carbon
unit-test

  1  0  0  0  0  0            999 V2000
    1.0000    2.0000    3.0000 C   0  0  0  0  0  0  0  0  0  0  0  0
M  END
$$$$
"""


def _artifact(
    pdb_id: str,
    role: str,
    filename: str,
    source: bytes,
) -> PublicBenchmarkArtifact:
    relative_path = f"posebusters/datasets/pdb/{pdb_id}/{pdb_id}_{filename}"
    return PublicBenchmarkArtifact(
        role=role,
        relative_path=relative_path,
        immutable_url=(
            "https://raw.githubusercontent.com/maabuu/posebusters/"
            f"{POSEBUSTERS_SOURCE_COMMIT_SHA}/{relative_path}"
        ),
        sha256=hashlib.sha256(source).hexdigest(),
        size_bytes=len(source),
        media_type=("chemical/x-pdb" if role == "receptor" else "chemical/x-mdl-sdfile"),
    )


def _protocol_and_sources() -> tuple[FrozenPublicBenchmarkProtocol, dict[str, bytes]]:
    cases: list[PublicBenchmarkCaseDefinition] = []
    sources: dict[str, bytes] = {}
    for pdb_id in ("1abc", "2abc", "3abc", "4abc"):
        receptor = f"HEADER {pdb_id}\n".encode("ascii")
        artifacts = (
            _artifact(pdb_id, "receptor", "protein_one_lig_removed.pdb", receptor),
            _artifact(pdb_id, "reference_ligands", "ligands.sdf", _VALID_SDF),
            _artifact(pdb_id, "ligand_identity_seed", "ligand.sdf", _VALID_SDF),
        )
        case = PublicBenchmarkCaseDefinition(
            case_id=f"posebusters-packaged-{pdb_id}",
            pdb_id=pdb_id,
            receptor=artifacts[0],
            reference_ligands=artifacts[1],
            ligand_identity_seed=artifacts[2],
        )
        cases.append(case)
        for artifact, source in zip(
            artifacts,
            (receptor, _VALID_SDF, _VALID_SDF),
            strict=True,
        ):
            sources[artifact.relative_path] = source
    return FrozenPublicBenchmarkProtocol(cases=tuple(cases), scorer_identities=()), sources


def _write_sources(root: Path, sources: dict[str, bytes]) -> None:
    for relative_path, source in sources.items():
        output = root / relative_path
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(source)


def test_suite_verifies_receptors_and_materializes_all_four_failure_denominators() -> None:
    protocol, sources = _protocol_and_sources()

    receipt = materialize_public_benchmark_input_suite(protocol, sources)

    assert receipt.input_materialization_complete
    assert receipt.input_verified_case_count == 4
    assert receipt.ready_for_rmsd_case_count == 4
    assert receipt.failed_case_count == 0
    assert receipt.verified_artifact_count == 12
    assert [row.status for row in receipt.case_rows] == ["materialized_ready"] * 4
    assert all(
        row.artifact_observations[1].role == "receptor"
        and row.artifact_observations[1].verified
        for row in receipt.case_rows
    )
    payload = receipt.to_dict()
    assert payload["denominator"] == "all_protocol_cases"
    assert payload["network_fetch_performed"] is False
    assert payload["docking_predictions_present"] is False
    assert payload["benchmark_executed"] is False
    assert payload["claim_safe"] is False
    assert receipt.scientific_blockers == (
        PUBLIC_BENCHMARK_SUITE_MATERIALIZATION_SCIENTIFIC_BLOCKERS
    )


def test_suite_receipt_round_trip_is_canonical_tamper_evident_and_protocol_bound() -> None:
    protocol, sources = _protocol_and_sources()
    receipt = materialize_public_benchmark_input_suite(protocol, sources)
    raw = receipt.to_json_bytes()

    restored = PublicBenchmarkSuiteMaterializationReceipt.from_json_bytes(raw)

    assert restored.to_json_bytes() == raw
    assert restored.require_protocol(protocol) is restored
    tampered = raw.replace(b'"benchmark_executed":false', b'"benchmark_executed":true')
    with pytest.raises(
        PublicBenchmarkSuiteMaterializationError,
        match="not canonical or is inconsistent",
    ):
        PublicBenchmarkSuiteMaterializationReceipt.from_json_bytes(tampered)
    with pytest.raises(
        PublicBenchmarkSuiteMaterializationError,
        match="cross-protocol materialization",
    ):
        replace(receipt, protocol_sha256="f" * 64).require_protocol(protocol)


def test_missing_and_digest_mismatch_cases_are_retained_as_failures() -> None:
    protocol, sources = _protocol_and_sources()
    first = protocol.cases[0]
    second = protocol.cases[1]
    del sources[first.reference_ligands.relative_path]
    sources[second.receptor.relative_path] = b"X" * second.receptor.size_bytes

    receipt = materialize_public_benchmark_input_suite(protocol, sources)

    assert len(receipt.case_rows) == 4
    assert receipt.ready_for_rmsd_case_count == 2
    assert receipt.failed_case_count == 2
    assert receipt.input_verified_case_count == 2
    assert receipt.case_rows[0].status == "failure_input_verification"
    assert receipt.case_rows[0].artifact_observations[2].status == "missing"
    assert receipt.case_rows[1].status == "failure_input_verification"
    assert receipt.case_rows[1].artifact_observations[1].status == "sha256_mismatch"
    assert receipt.input_materialization_complete is False


def test_directory_reader_rejects_symlinks_and_writer_refuses_overwrite(
    tmp_path: Path,
) -> None:
    protocol, sources = _protocol_and_sources()
    input_root = tmp_path / "inputs"
    _write_sources(input_root, sources)
    receipt = materialize_public_benchmark_input_suite_from_directory(
        protocol,
        input_root,
    )
    assert receipt.input_materialization_complete

    output = write_public_benchmark_input_suite_receipt(
        receipt,
        tmp_path / "receipt.json",
    )
    assert output.read_bytes() == receipt.to_json_bytes()
    assert os.stat(output).st_mode & 0o777 == 0o600
    with pytest.raises(PublicBenchmarkSuiteMaterializationError, match="already exists"):
        write_public_benchmark_input_suite_receipt(receipt, output)

    target = input_root / protocol.cases[0].receptor.relative_path
    original = target.read_bytes()
    target.unlink()
    outside = tmp_path / "outside.pdb"
    outside.write_bytes(original)
    target.symlink_to(outside)
    failed = materialize_public_benchmark_input_suite_from_directory(
        protocol,
        input_root,
    )
    assert failed.case_rows[0].artifact_observations[1].status == "unsafe_path"
    assert failed.case_rows[0].status == "failure_input_verification"


def test_cli_fails_closed_for_missing_root_and_symbols_are_reexported(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(["--input-root", str(tmp_path / "missing")]) == 2
    assert "input root does not exist" in capsys.readouterr().err

    from betelgeuze_engine_v2 import benchmark
    from betelgeuze_engine_v2.benchmark.public_suite_materialization import (
        __all__ as suite_exports,
    )

    assert set(suite_exports) - {"main"} <= set(benchmark.__all__)


def test_serialized_claim_boundaries_cannot_be_promoted() -> None:
    protocol, sources = _protocol_and_sources()
    payload = materialize_public_benchmark_input_suite(protocol, sources).to_dict()

    assert payload["public_holdout_result_established"] is False
    assert payload["pose_validity_evaluated"] is False
    assert payload["scientifically_validated"] is False
    assert payload["benchmark_validated"] is False
    assert payload["customer_execution_enabled"] is False
    assert "same_input_vina_gnina_smina_receipts_missing" in payload["scientific_blockers"]
    assert json.dumps(payload, sort_keys=True)

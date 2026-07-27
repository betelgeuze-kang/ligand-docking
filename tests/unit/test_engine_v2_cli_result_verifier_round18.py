from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import stat

import pytest


torch = pytest.importorskip("torch")

from betelgeuze_engine_v2 import (  # noqa: E402
    AllAtomSystem,
    Atom,
    Bond,
    Chain,
    Residue,
    StructureProvenance,
)
from betelgeuze_engine_v2.cli import (  # noqa: E402
    CLI_POCKET_INPUT_SCHEMA_ID,
    run_canonical_docking,
)
from betelgeuze_engine_v2.cli_dispatch import main as dispatch_main  # noqa: E402
from betelgeuze_engine_v2.molecular import (  # noqa: E402
    write_canonical_system_json,
)
from betelgeuze_engine_v2.result_verifier_strict import (  # noqa: E402
    CliResultVerificationError,
    verify_canonical_cli_result_bytes,
    verify_canonical_cli_result_document,
)


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=True,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("ascii")


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _provenance(name: str, digest: str) -> StructureProvenance:
    return StructureProvenance(
        source_format="unit",
        source_id=name,
        source_sha256=digest,
        parser_name="result-verifier-fixture",
        parser_version="1.0.0",
    )


def _ligand() -> AllAtomSystem:
    elements = ("C", "N", "C", "O")
    return AllAtomSystem(
        system_id="result-verifier-ligand",
        atoms=tuple(
            Atom(
                index=index,
                name=f"L{index}",
                element=element,
                atomic_number={"C": 6, "N": 7, "O": 8}[element],
                residue_index=0,
            )
            for index, element in enumerate(elements)
        ),
        bonds=(
            Bond(index=0, atom_i=0, atom_j=1, order=1.0),
            Bond(index=1, atom_i=1, atom_j=2, order=1.0),
            Bond(index=2, atom_i=2, atom_j=3, order=1.0),
        ),
        residues=(
            Residue(
                index=0,
                name="LIG",
                chain_index=0,
                sequence_number=1,
                atom_indices=(0, 1, 2, 3),
            ),
        ),
        chains=(Chain(index=0, chain_id="L", residue_indices=(0,)),),
        coordinates=torch.tensor(
            [
                [
                    [0.0, 0.0, 0.0],
                    [1.4, 0.0, 0.0],
                    [2.8, 0.3, 0.0],
                    [4.1, 1.0, 0.2],
                ]
            ],
            dtype=torch.float64,
        ),
        provenance=_provenance("result-verifier-ligand-source", "a" * 64),
    )


def _receptor() -> AllAtomSystem:
    coordinates = (
        [0.0, 0.0, 0.0],
        [5.0, 0.0, 0.0],
        [8.0, 7.0, 4.0],
        [-8.0, -7.0, -4.0],
    )
    return AllAtomSystem(
        system_id="result-verifier-receptor",
        atoms=tuple(
            Atom(
                index=index,
                name=f"R{index}",
                element="C",
                atomic_number=6,
                residue_index=0,
            )
            for index in range(len(coordinates))
        ),
        bonds=(),
        residues=(
            Residue(
                index=0,
                name="REC",
                chain_index=0,
                sequence_number=1,
                atom_indices=tuple(range(len(coordinates))),
            ),
        ),
        chains=(Chain(index=0, chain_id="A", residue_indices=(0,)),),
        coordinates=torch.tensor([coordinates], dtype=torch.float64),
        provenance=_provenance("result-verifier-receptor-source", "b" * 64),
    )


def _inputs(tmp_path: Path) -> tuple[Path, Path, Path]:
    tmp_path.mkdir(parents=True, exist_ok=True)
    receptor_path = tmp_path / "receptor.json"
    ligand_path = tmp_path / "ligand.json"
    pocket_path = tmp_path / "pocket.json"
    write_canonical_system_json(_receptor(), receptor_path)
    write_canonical_system_json(_ligand(), ligand_path)
    pocket = {
        "schema_id": CLI_POCKET_INPUT_SCHEMA_ID,
        "scope": "known_pocket_docking",
        "method_id": "result-verifier-reviewed-sphere",
        "method_version": "1.0.0",
        "coordinate_frame_id": "prepared-receptor-frame-v1",
        "center_angstrom": [2.5, 2.0, 0.0],
        "radius_angstrom": 12.0,
        "source_artifact_sha256": "c" * 64,
        "implementation_source_sha256": "d" * 64,
    }
    pocket_path.write_bytes(_canonical_bytes(pocket) + b"\n")
    return receptor_path, ligand_path, pocket_path


def _document(tmp_path: Path) -> dict[str, object]:
    receptor, ligand, pocket = _inputs(tmp_path)
    return run_canonical_docking(
        receptor_path=receptor,
        ligand_path=ligand,
        pocket_path=pocket,
        candidate_count=4,
        top_k=2,
        max_torsions=1,
        translation_radius_angstrom=2.0,
        seed=163,
        receptor_margin_angstrom=4.0,
    )


def _recompute_cli_document_sha(document: dict[str, object]) -> None:
    projection = dict(document)
    projection.pop("document_sha256", None)
    document["document_sha256"] = _sha256(projection)


def _recompute_interpretable_receipt(document: dict[str, object]) -> str:
    result = document["result"]
    assert isinstance(result, dict)
    projection = dict(result)
    projection.pop("receipt_sha256", None)
    projection.pop("rows", None)
    projection.pop("placement_search_result", None)
    result["receipt_sha256"] = _sha256(projection)
    document["result_receipt_sha256"] = result["receipt_sha256"]
    return str(result["receipt_sha256"])


def test_strict_verifier_accepts_a_canonical_cli_result(tmp_path: Path) -> None:
    document = _document(tmp_path)
    raw = _canonical_bytes(document) + b"\n"
    receipt_from_bytes = verify_canonical_cli_result_bytes(raw)
    receipt_from_document = verify_canonical_cli_result_document(document)
    assert receipt_from_bytes.receipt_sha256 == (
        receipt_from_document.receipt_sha256
    )
    assert receipt_from_bytes.candidate_count == 4
    assert receipt_from_bytes.success_count + receipt_from_bytes.failure_count == 4
    verification = receipt_from_bytes.to_dict()
    assert verification["canonical_bytes_verified"] is True
    assert verification["nested_receipts_verified"] is True
    assert verification["failure_denominator_verified"] is True
    assert verification["generic_search_fingerprint_fully_recomputed"] is True
    assert verification["generic_search_fingerprint_crosslinked"] is True
    assert verification["claim_safe"] is False


def test_nested_score_term_tamper_is_rejected_even_with_new_top_sha(
    tmp_path: Path,
) -> None:
    document = deepcopy(_document(tmp_path))
    result = document["result"]
    assert isinstance(result, dict)
    rows = result["rows"]
    assert isinstance(rows, list)
    successful = next(
        row
        for row in rows
        if isinstance(row, dict) and row.get("search_status") == "success"
    )
    terms = successful["terms"]
    assert isinstance(terms, dict)
    terms["total_score_hex"] = (float.fromhex(terms["total_score_hex"]) + 1.0).hex()
    _recompute_cli_document_sha(document)
    with pytest.raises(
        CliResultVerificationError,
        match="score terms receipt SHA does not match",
    ):
        verify_canonical_cli_result_document(document)


def test_generic_search_fingerprint_crosslink_tamper_is_rejected(
    tmp_path: Path,
) -> None:
    document = deepcopy(_document(tmp_path))
    result = document["result"]
    assert isinstance(result, dict)
    result["generic_search_fingerprint_sha256"] = "9" * 64
    _recompute_interpretable_receipt(document)
    _recompute_cli_document_sha(document)
    with pytest.raises(
        CliResultVerificationError,
        match="generic search fingerprint cross-link",
    ):
        verify_canonical_cli_result_document(document)


def test_noncanonical_result_bytes_fail_closed(tmp_path: Path) -> None:
    document = _document(tmp_path)
    noncanonical = json.dumps(document).encode("ascii")
    with pytest.raises(
        CliResultVerificationError,
        match="bytes are not canonical",
    ):
        verify_canonical_cli_result_bytes(noncanonical)


def test_verify_result_console_command_writes_private_receipt(
    tmp_path: Path,
) -> None:
    input_path = tmp_path / "result.json"
    output_path = tmp_path / "verification.json"
    input_path.write_bytes(_canonical_bytes(_document(tmp_path / "inputs")) + b"\n")
    status_code = dispatch_main(
        [
            "verify-result",
            "--input",
            str(input_path),
            "--output",
            str(output_path),
        ]
    )
    assert status_code == 0
    assert stat.S_IMODE(os.stat(output_path).st_mode) == 0o600
    verification = json.loads(output_path.read_bytes())
    assert verification["command_id"] == (
        "betelgeuze-engine-v2/verify-result/1.0.0"
    )
    assert verification["canonical_bytes_verified"] is True
    assert verification["generic_search_fingerprint_fully_recomputed"] is True
    assert verification["claim_safe"] is False
    projection = dict(verification)
    document_sha = projection.pop("document_sha256")
    assert document_sha == _sha256(projection)
    assert dispatch_main(
        [
            "verify-result",
            "--input",
            str(input_path),
            "--output",
            str(output_path),
        ]
    ) == 2

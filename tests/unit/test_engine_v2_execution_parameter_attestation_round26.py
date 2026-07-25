from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest


torch = pytest.importorskip("torch")

from betelgeuze_engine_v2 import (
    ATTESTED_INPUT_BOUND_VERIFICATION_SCHEMA_ID,
    CLI_EXECUTION_PARAMETERS_SCHEMA_ID,
    EXECUTION_PARAMETER_ATTESTATION_SHA256,
    AllAtomSystem,
    Atom,
    AttestedInputBoundVerificationReceipt,
    Bond,
    Chain,
    ExecutionParameterAttestationError,
    Residue,
    StructureProvenance,
)
from betelgeuze_engine_v2.cli import run_canonical_docking
from betelgeuze_engine_v2.input_bound_verifier import (
    INPUT_BOUND_VERIFICATION_SCHEMA_ID,
    verify_input_bound_cli_bundle_bytes,
)
from betelgeuze_engine_v2.molecular import write_canonical_system_json
from betelgeuze_engine_v2.reference_pocket import (
    derive_reference_pocket_from_canonical_bytes,
)
from betelgeuze_engine_v2.result_verifier_strict import (
    verify_canonical_cli_result_bytes,
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
        parser_name="execution-attestation-fixture",
        parser_version="1.0.0",
    )


def _ligand() -> AllAtomSystem:
    elements = ("C", "N", "C", "O")
    return AllAtomSystem(
        system_id="execution-attestation-ligand",
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
            [[[0.0, 0.0, 0.0], [1.4, 0.0, 0.0], [2.8, 0.3, 0.0], [4.1, 1.0, 0.2]]],
            dtype=torch.float64,
        ),
        provenance=_provenance("execution-attestation-ligand-source", "a" * 64),
    )


def _receptor() -> AllAtomSystem:
    coordinates = (
        [0.0, 4.0, 0.0],
        [4.0, 4.0, 0.0],
        [7.0, 0.0, 0.0],
        [9.0, 0.0, 0.0],
        [60.0, 60.0, 60.0],
    )
    return AllAtomSystem(
        system_id="execution-attestation-receptor",
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
        provenance=_provenance("execution-attestation-receptor-source", "b" * 64),
    )


def _bundle(tmp_path: Path):
    tmp_path.mkdir(parents=True, exist_ok=True)
    receptor_path = tmp_path / "receptor.json"
    ligand_path = tmp_path / "ligand.json"
    pocket_path = tmp_path / "pocket.json"
    result_path = tmp_path / "result.json"
    write_canonical_system_json(_receptor(), receptor_path)
    write_canonical_system_json(_ligand(), ligand_path)
    pocket = derive_reference_pocket_from_canonical_bytes(
        ligand_path.read_bytes(),
        coordinate_frame_id="prepared-receptor-frame-v1",
        padding_angstrom=4.0,
        minimum_radius_angstrom=6.0,
    )
    pocket_path.write_bytes(_canonical_bytes(pocket) + b"\n")
    result = run_canonical_docking(
        receptor_path=receptor_path,
        ligand_path=ligand_path,
        pocket_path=pocket_path,
        candidate_count=4,
        top_k=2,
        max_torsions=1,
        translation_radius_angstrom=1.0,
        seed=223,
        receptor_margin_angstrom=4.0,
    )
    result_path.write_bytes(_canonical_bytes(result) + b"\n")
    return result, result_path, receptor_path, ligand_path, pocket_path


def _verify(paths, *, margin: float = 4.0):
    _, result_path, receptor_path, ligand_path, pocket_path = paths
    return verify_input_bound_cli_bundle_bytes(
        result_raw=result_path.read_bytes(),
        receptor_raw=receptor_path.read_bytes(),
        ligand_raw=ligand_path.read_bytes(),
        pocket_raw=pocket_path.read_bytes(),
        receptor_model_index=0,
        ligand_model_index=0,
        receptor_margin_angstrom=margin,
        require_reference_pocket_derivation=True,
    )


def _recompute_result_sha(document: dict[str, object]) -> None:
    projection = dict(document)
    projection.pop("document_sha256", None)
    document["document_sha256"] = _sha256(projection)


def test_new_result_contains_a_canonical_execution_parameter_receipt(
    tmp_path: Path,
) -> None:
    result, *_ = _bundle(tmp_path)
    assert len(EXECUTION_PARAMETER_ATTESTATION_SHA256) == 64
    execution = result["execution_parameters"]
    assert isinstance(execution, dict)
    assert execution["schema_id"] == CLI_EXECUTION_PARAMETERS_SCHEMA_ID
    assert execution["receptor_model_index"] == 0
    assert execution["ligand_model_index"] == 0
    assert execution["receptor_margin_angstrom_binary64_hex"] == (4.0).hex()
    assert execution["model_selection_fixed_by_cli"] is True
    assert execution["parameters_uniquely_attested"] is True
    assert execution["scorer_source_preimport_attested"] is False
    projection = dict(execution)
    receipt = projection.pop("receipt_sha256")
    assert receipt == _sha256(projection)
    assert result["execution_parameters_receipt_sha256"] == receipt
    for field_name in (
        "receptor_artifact_sha256",
        "ligand_artifact_sha256",
        "pocket_artifact_sha256",
        "pocket_definition_sha256",
        "authenticated_input_receipt_sha256",
        "scorer_source_sha256",
    ):
        assert execution[field_name] == result[field_name]
    verify_canonical_cli_result_bytes(_canonical_bytes(result) + b"\n")


def test_input_bound_receipt_promotes_only_verified_parameter_attestation(
    tmp_path: Path,
) -> None:
    receipt = _verify(_bundle(tmp_path))
    assert isinstance(receipt, AttestedInputBoundVerificationReceipt)
    document = receipt.to_dict()
    assert document["schema_id"] == (
        ATTESTED_INPUT_BOUND_VERIFICATION_SCHEMA_ID
    )
    assert document["execution_parameters_fully_verified"] is True
    assert document["receptor_margin_uniquely_attested"] is True
    assert document["model_indices_uniquely_attested"] is True
    assert len(document["execution_parameters_receipt_sha256"]) == 64
    assert len(document["base_verification_receipt_sha256"]) == 64
    assert document["scorer_source_bytes_locally_attested"] is False
    assert document["scientifically_validated"] is False
    assert document["benchmark_validated"] is False
    assert document["product_qualified"] is False
    assert document["customer_execution_enabled"] is False
    assert document["claim_safe"] is False


def test_attested_margin_tamper_fails_even_when_all_document_hashes_are_rebuilt(
    tmp_path: Path,
) -> None:
    result, result_path, receptor_path, ligand_path, pocket_path = _bundle(
        tmp_path
    )
    tampered = deepcopy(result)
    execution = tampered["execution_parameters"]
    assert isinstance(execution, dict)
    execution["receptor_margin_angstrom_binary64_hex"] = (5.0).hex()
    projection = dict(execution)
    projection.pop("receipt_sha256", None)
    execution_receipt = _sha256(projection)
    execution["receipt_sha256"] = execution_receipt
    tampered["execution_parameters_receipt_sha256"] = execution_receipt
    _recompute_result_sha(tampered)
    result_path.write_bytes(_canonical_bytes(tampered) + b"\n")
    with pytest.raises(
        ExecutionParameterAttestationError,
        match="differs from the attested value",
    ):
        verify_input_bound_cli_bundle_bytes(
            result_raw=result_path.read_bytes(),
            receptor_raw=receptor_path.read_bytes(),
            ligand_raw=ligand_path.read_bytes(),
            pocket_raw=pocket_path.read_bytes(),
            receptor_model_index=0,
            ligand_model_index=0,
            receptor_margin_angstrom=4.0,
            require_reference_pocket_derivation=True,
        )


def test_legacy_result_without_execution_extension_retains_false_flags(
    tmp_path: Path,
) -> None:
    result, result_path, receptor_path, ligand_path, pocket_path = _bundle(
        tmp_path
    )
    legacy = dict(result)
    legacy.pop("execution_parameters", None)
    legacy.pop("execution_parameters_receipt_sha256", None)
    _recompute_result_sha(legacy)
    result_path.write_bytes(_canonical_bytes(legacy) + b"\n")
    receipt = verify_input_bound_cli_bundle_bytes(
        result_raw=result_path.read_bytes(),
        receptor_raw=receptor_path.read_bytes(),
        ligand_raw=ligand_path.read_bytes(),
        pocket_raw=pocket_path.read_bytes(),
        receptor_model_index=0,
        ligand_model_index=0,
        receptor_margin_angstrom=4.0,
        require_reference_pocket_derivation=True,
    )
    document = receipt.to_dict()
    assert document["schema_id"] == INPUT_BOUND_VERIFICATION_SCHEMA_ID
    assert "execution_parameters_fully_verified" not in document
    assert document["receptor_margin_uniquely_attested"] is False
    assert document["model_indices_uniquely_attested"] is False
    assert document["claim_safe"] is False

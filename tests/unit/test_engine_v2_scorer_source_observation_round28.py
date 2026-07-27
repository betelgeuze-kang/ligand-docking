from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import stat

import pytest


torch = pytest.importorskip("torch")

from betelgeuze_engine_v2 import (  # noqa: E402
    ATTESTED_INPUT_BOUND_VERIFICATION_SCHEMA_ID,
    SCORER_SOURCE_OBSERVATION_MODE,
    SCORER_SOURCE_OBSERVATION_SCHEMA_ID,
    SCORER_SOURCE_OBSERVATION_SHA256,
    AllAtomSystem,
    Atom,
    AttestedInputBoundVerificationReceipt,
    Bond,
    Chain,
    Residue,
    SourceObservedInputBoundVerificationReceipt,
    StructureProvenance,
)
from betelgeuze_engine_v2.cli import run_canonical_docking  # noqa: E402
from betelgeuze_engine_v2.cli_dispatch import main as dispatch_main  # noqa: E402
from betelgeuze_engine_v2.input_bound_verifier import (  # noqa: E402
    verify_input_bound_cli_bundle_bytes,
)
from betelgeuze_engine_v2.molecular import (  # noqa: E402
    write_canonical_system_json,
)
from betelgeuze_engine_v2.reference_pocket import (  # noqa: E402
    derive_reference_pocket_from_canonical_bytes,
)
from betelgeuze_engine_v2.scorer_source_observation import (  # noqa: E402
    SCORER_SOURCE_OBSERVATION_EXTENSION_SCHEMA_ID,
    ScorerSourceObservationError,
)
import betelgeuze_engine_v2.scorer_source_observation as source_module  # noqa: E402


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
        parser_name="source-observation-fixture",
        parser_version="1.0.0",
    )


def _ligand() -> AllAtomSystem:
    elements = ("C", "N", "C", "O")
    return AllAtomSystem(
        system_id="source-observation-ligand",
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
        provenance=_provenance("source-observation-ligand-source", "a" * 64),
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
        system_id="source-observation-receptor",
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
        provenance=_provenance("source-observation-receptor-source", "b" * 64),
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
        seed=227,
        receptor_margin_angstrom=4.0,
    )
    result_path.write_bytes(_canonical_bytes(result) + b"\n")
    return result, result_path, receptor_path, ligand_path, pocket_path


def _verify(paths):
    _, result_path, receptor_path, ligand_path, pocket_path = paths
    return verify_input_bound_cli_bundle_bytes(
        result_raw=result_path.read_bytes(),
        receptor_raw=receptor_path.read_bytes(),
        ligand_raw=ligand_path.read_bytes(),
        pocket_raw=pocket_path.read_bytes(),
        receptor_model_index=0,
        ligand_model_index=0,
        receptor_margin_angstrom=4.0,
        require_reference_pocket_derivation=True,
    )


def test_installed_source_bytes_match_result_without_preimport_claim(
    tmp_path: Path,
) -> None:
    result, *_ = paths = _bundle(tmp_path)
    receipt = _verify(paths)
    assert isinstance(receipt, SourceObservedInputBoundVerificationReceipt)
    assert isinstance(receipt.base_receipt, AttestedInputBoundVerificationReceipt)
    assert len(SCORER_SOURCE_OBSERVATION_SHA256) == 64
    document = receipt.to_dict()
    assert document["schema_id"] == (
        ATTESTED_INPUT_BOUND_VERIFICATION_SCHEMA_ID
    )
    assert document["scorer_source_observation_extension_schema_id"] == (
        SCORER_SOURCE_OBSERVATION_EXTENSION_SCHEMA_ID
    )
    assert document["scorer_source_observation_mode"] == (
        SCORER_SOURCE_OBSERVATION_MODE
    )
    assert document["scorer_source_sha256"] == result[
        "scorer_source_sha256"
    ]
    assert document["scorer_source_byte_count"] > 0
    assert document["scorer_source_bytes_locally_observed"] is True
    assert document["scorer_source_bytes_sha256_matched_result"] is True
    assert document["scorer_source_bytes_observed_after_import"] is True
    assert document["scorer_source_bytes_locally_attested"] is False
    assert document["scorer_source_execution_preimport_attested"] is False
    assert document["scorer_source_signature_verified"] is False
    assert len(document["scorer_source_observation_receipt_sha256"]) == 64
    observation = document["scorer_source_observation"]
    assert isinstance(observation, dict)
    assert observation["schema_id"] == SCORER_SOURCE_OBSERVATION_SCHEMA_ID
    assert observation["observation_mode"] == SCORER_SOURCE_OBSERVATION_MODE
    assert observation["source_bytes_locally_observed"] is True
    assert observation["source_bytes_sha256_matched_result"] is True
    assert observation["source_bytes_locally_attested"] is False
    assert observation["source_execution_preimport_attested"] is False
    projection = dict(observation)
    observation_receipt = projection.pop("receipt_sha256")
    assert observation_receipt == _sha256(projection)
    assert document["claim_safe"] is False


def test_local_source_sha_mismatch_fails_after_authority_replay(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths = _bundle(tmp_path)
    monkeypatch.setattr(
        source_module,
        "_observe_installed_scorer_source",
        lambda: ("9" * 64, 1),
    )
    with pytest.raises(
        ScorerSourceObservationError,
        match="do not match",
    ):
        _verify(paths)


def test_verify_bundle_writes_source_observation_extension(
    tmp_path: Path,
) -> None:
    _, result_path, receptor_path, ligand_path, pocket_path = _bundle(
        tmp_path / "source"
    )
    output_path = tmp_path / "bundle-verification.json"
    arguments = [
        "verify-bundle",
        "--result",
        str(result_path),
        "--receptor",
        str(receptor_path),
        "--ligand",
        str(ligand_path),
        "--pocket",
        str(pocket_path),
        "--receptor-margin-angstrom",
        "4.0",
        "--require-reference-pocket-derivation",
        "--output",
        str(output_path),
    ]
    assert dispatch_main(arguments) == 0
    assert stat.S_IMODE(os.stat(output_path).st_mode) == 0o600
    raw = output_path.read_bytes()
    assert raw.endswith(b"\n")
    document = json.loads(raw)
    assert document["scorer_source_bytes_locally_observed"] is True
    assert document["scorer_source_bytes_sha256_matched_result"] is True
    assert document["scorer_source_bytes_locally_attested"] is False
    assert document["scorer_source_execution_preimport_attested"] is False
    assert document["scorer_source_signature_verified"] is False
    assert document["execution_parameters_fully_verified"] is True
    assert document["receptor_margin_uniquely_attested"] is True
    assert document["model_indices_uniquely_attested"] is True
    assert document["scientifically_validated"] is False
    assert document["benchmark_validated"] is False
    assert document["product_qualified"] is False
    assert document["customer_execution_enabled"] is False
    assert document["claim_safe"] is False
    projection = dict(document)
    document_sha = projection.pop("document_sha256")
    assert document_sha == hashlib.sha256(
        _canonical_bytes(projection)
    ).hexdigest()
    assert dispatch_main(arguments) == 2

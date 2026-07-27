from __future__ import annotations

from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
import stat

import pytest


torch = pytest.importorskip("torch")

from betelgeuze_engine_v2 import (  # noqa: E402
    ATTESTED_INPUT_BOUND_VERIFICATION_SCHEMA_ID,
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
from betelgeuze_engine_v2.input_bound_verifier import (  # noqa: E402
    InputBoundVerificationError,
    verify_input_bound_cli_bundle_bytes,
)
from betelgeuze_engine_v2 import input_bound_verifier as verifier_module  # noqa: E402
from betelgeuze_engine_v2.molecular import (  # noqa: E402
    write_canonical_system_json,
)
from betelgeuze_engine_v2.reference_pocket import (  # noqa: E402
    derive_reference_pocket_from_canonical_bytes,
)


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=True,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("ascii")


def _provenance(name: str, digest: str) -> StructureProvenance:
    return StructureProvenance(
        source_format="unit",
        source_id=name,
        source_sha256=digest,
        parser_name="input-bound-verifier-fixture",
        parser_version="1.0.0",
    )


def _ligand(*, shift_x: float = 0.0) -> AllAtomSystem:
    elements = ("C", "N", "C", "O")
    coordinates = [
        [0.0 + shift_x, 0.0, 0.0],
        [1.4 + shift_x, 0.0, 0.0],
        [2.8 + shift_x, 0.3, 0.0],
        [4.1 + shift_x, 1.0, 0.2],
    ]
    return AllAtomSystem(
        system_id="input-bound-ligand",
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
        coordinates=torch.tensor([coordinates], dtype=torch.float64),
        provenance=_provenance("input-bound-ligand-source", "a" * 64),
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
        system_id="input-bound-receptor",
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
        provenance=_provenance("input-bound-receptor-source", "b" * 64),
    )


def _write_inputs(
    tmp_path: Path,
    *,
    reference_pocket: bool,
) -> tuple[Path, Path, Path]:
    tmp_path.mkdir(parents=True, exist_ok=True)
    receptor_path = tmp_path / "receptor.json"
    ligand_path = tmp_path / "ligand.json"
    pocket_path = tmp_path / "pocket.json"
    write_canonical_system_json(_receptor(), receptor_path)
    write_canonical_system_json(_ligand(), ligand_path)
    if reference_pocket:
        pocket = derive_reference_pocket_from_canonical_bytes(
            ligand_path.read_bytes(),
            coordinate_frame_id="prepared-receptor-frame-v1",
            padding_angstrom=4.0,
            minimum_radius_angstrom=6.0,
        )
    else:
        pocket = {
            "schema_id": CLI_POCKET_INPUT_SCHEMA_ID,
            "scope": "known_pocket_docking",
            "method_id": "input-bound-manual-sphere",
            "method_version": "1.0.0",
            "coordinate_frame_id": "prepared-receptor-frame-v1",
            "center_angstrom": [2.075, 0.325, 0.05],
            "radius_angstrom": 6.0,
            "source_artifact_sha256": "c" * 64,
            "implementation_source_sha256": "d" * 64,
            "metadata": {"reviewed": True},
        }
    pocket_path.write_bytes(_canonical_bytes(pocket) + b"\n")
    return receptor_path, ligand_path, pocket_path


def _bundle(
    tmp_path: Path,
    *,
    reference_pocket: bool = True,
) -> tuple[Path, Path, Path, Path]:
    receptor_path, ligand_path, pocket_path = _write_inputs(
        tmp_path,
        reference_pocket=reference_pocket,
    )
    result_path = tmp_path / "result.json"
    result = run_canonical_docking(
        receptor_path=receptor_path,
        ligand_path=ligand_path,
        pocket_path=pocket_path,
        candidate_count=4,
        top_k=2,
        max_torsions=1,
        translation_radius_angstrom=1.0,
        seed=197,
        receptor_margin_angstrom=4.0,
    )
    result_path.write_bytes(_canonical_bytes(result) + b"\n")
    return result_path, receptor_path, ligand_path, pocket_path


def _verify(
    paths: tuple[Path, Path, Path, Path],
    *,
    margin: float = 4.0,
    require_reference: bool = True,
):
    result_path, receptor_path, ligand_path, pocket_path = paths
    return verify_input_bound_cli_bundle_bytes(
        result_raw=result_path.read_bytes(),
        receptor_raw=receptor_path.read_bytes(),
        ligand_raw=ligand_path.read_bytes(),
        pocket_raw=pocket_path.read_bytes(),
        receptor_model_index=0,
        ligand_model_index=0,
        receptor_margin_angstrom=margin,
        require_reference_pocket_derivation=require_reference,
    )


def test_reference_bundle_recomputes_derivation_authority_and_scorer(
    tmp_path: Path,
) -> None:
    receipt = _verify(_bundle(tmp_path))
    document = receipt.to_dict()
    assert document["schema_id"] == (
        ATTESTED_INPUT_BOUND_VERIFICATION_SCHEMA_ID
    )
    assert document["reference_pocket_derivation_fully_recomputed"] is True
    assert len(document["reference_pocket_derivation_receipt_sha256"]) == 64
    assert document["input_artifact_sha256s_verified"] is True
    assert document["pocket_definition_fully_recomputed"] is True
    assert document["authority_state_fully_recomputed"] is True
    assert document["scorer_contract_recomputed_from_declared_source_sha"] is True
    assert document["scorer_source_bytes_locally_attested"] is False
    assert document["search_fingerprint_fully_recomputed"] is True
    assert document["execution_parameters_fully_verified"] is True
    assert document["receptor_margin_uniquely_attested"] is True
    assert document["model_indices_uniquely_attested"] is True
    assert len(document["execution_parameters_receipt_sha256"]) == 64
    assert document["candidate_count"] == 4
    assert document["success_count"] + document["failure_count"] == 4
    assert document["chemistry_inference_performed"] is False
    assert document["pocket_prediction_performed"] is False
    assert document["scientifically_validated"] is False
    assert document["benchmark_validated"] is False
    assert document["product_qualified"] is False
    assert document["customer_execution_enabled"] is False
    assert document["claim_safe"] is False
    assert len(receipt.receipt_sha256) == 64


def test_input_bound_receipt_preserves_retained_only_search_status(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths = _bundle(tmp_path)
    original = verifier_module.verify_canonical_cli_result_bytes

    def retained_only_verification(raw: bytes):
        return replace(
            original(raw),
            generic_search_fingerprint_fully_recomputed=False,
        )

    monkeypatch.setattr(
        verifier_module,
        "verify_canonical_cli_result_bytes",
        retained_only_verification,
    )
    document = _verify(paths).to_dict()
    assert document["search_fingerprint_fully_recomputed"] is False


def test_wrong_ligand_artifact_is_rejected_before_authority_replay(
    tmp_path: Path,
) -> None:
    paths = _bundle(tmp_path / "source")
    wrong_ligand = tmp_path / "wrong-ligand.json"
    write_canonical_system_json(_ligand(shift_x=1.0), wrong_ligand)
    result_path, receptor_path, _, pocket_path = paths
    with pytest.raises(
        InputBoundVerificationError,
        match="ligand_artifact_sha256",
    ):
        verify_input_bound_cli_bundle_bytes(
            result_raw=result_path.read_bytes(),
            receptor_raw=receptor_path.read_bytes(),
            ligand_raw=wrong_ligand.read_bytes(),
            pocket_raw=pocket_path.read_bytes(),
            receptor_margin_angstrom=4.0,
            require_reference_pocket_derivation=True,
        )


def test_wrong_margin_fails_authority_receipt_reconstruction(
    tmp_path: Path,
) -> None:
    paths = _bundle(tmp_path)
    with pytest.raises(
        InputBoundVerificationError,
        match="authority receipt",
    ):
        _verify(paths, margin=0.0)


def test_manual_pocket_can_replay_authority_without_claiming_derivation(
    tmp_path: Path,
) -> None:
    paths = _bundle(tmp_path, reference_pocket=False)
    receipt = _verify(paths, require_reference=False)
    document = receipt.to_dict()
    assert document["reference_pocket_derivation_fully_recomputed"] is False
    assert document["reference_pocket_derivation_receipt_sha256"] == ""
    assert document["authority_state_fully_recomputed"] is True
    assert document["execution_parameters_fully_verified"] is True
    assert document["receptor_margin_uniquely_attested"] is True
    assert document["model_indices_uniquely_attested"] is True
    with pytest.raises(
        InputBoundVerificationError,
        match="required reference derivation",
    ):
        _verify(paths, require_reference=True)


def test_verify_bundle_command_writes_private_canonical_receipt(
    tmp_path: Path,
) -> None:
    result_path, receptor_path, ligand_path, pocket_path = _bundle(
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
    assert document["command_id"] == (
        "betelgeuze-engine-v2/verify-bundle/1.0.0"
    )
    assert document["reference_pocket_derivation_fully_recomputed"] is True
    assert document["authority_state_fully_recomputed"] is True
    assert document["search_fingerprint_fully_recomputed"] is True
    assert document["execution_parameters_fully_verified"] is True
    assert document["receptor_margin_uniquely_attested"] is True
    assert document["model_indices_uniquely_attested"] is True
    assert document["claim_safe"] is False
    projection = dict(document)
    document_sha = projection.pop("document_sha256")
    assert document_sha == hashlib.sha256(
        _canonical_bytes(projection)
    ).hexdigest()
    assert dispatch_main(arguments) == 2

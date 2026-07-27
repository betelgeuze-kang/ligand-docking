from __future__ import annotations

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
    CLI_DOCKING_RESULT_SCHEMA_ID,
    CLI_POCKET_INPUT_SCHEMA_ID,
    EngineV2CliError,
    SCORER_SOURCE_BINDING_MODE,
    main,
    run_canonical_docking,
)
from betelgeuze_engine_v2.molecular import (  # noqa: E402
    write_canonical_system_json,
)


ROOT = Path(__file__).resolve().parents[2]


def _provenance(name: str, digest: str) -> StructureProvenance:
    return StructureProvenance(
        source_format="unit",
        source_id=name,
        source_sha256=digest,
        parser_name="canonical-cli-fixture",
        parser_version="1.0.0",
    )


def _ligand() -> AllAtomSystem:
    elements = ("C", "N", "C", "O")
    return AllAtomSystem(
        system_id="canonical-cli-ligand",
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
        provenance=_provenance("canonical-cli-ligand-source", "a" * 64),
    )


def _receptor() -> AllAtomSystem:
    coordinates = (
        [0.0, 0.0, 0.0],
        [5.0, 0.0, 0.0],
        [8.0, 7.0, 4.0],
        [-8.0, -7.0, -4.0],
    )
    return AllAtomSystem(
        system_id="canonical-cli-receptor",
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
        provenance=_provenance("canonical-cli-receptor-source", "b" * 64),
    )


def _canonical_json_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=True,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("ascii") + b"\n"


def _inputs(tmp_path: Path) -> tuple[Path, Path, Path]:
    tmp_path.mkdir(parents=True, exist_ok=True)
    receptor = tmp_path / "receptor.json"
    ligand = tmp_path / "ligand.json"
    pocket = tmp_path / "pocket.json"
    write_canonical_system_json(_receptor(), receptor)
    write_canonical_system_json(_ligand(), ligand)
    pocket.write_bytes(
        _canonical_json_bytes(
            {
                "schema_id": CLI_POCKET_INPUT_SCHEMA_ID,
                "scope": "known_pocket_docking",
                "method_id": "canonical-cli-reviewed-sphere",
                "method_version": "1.0.0",
                "coordinate_frame_id": "prepared-receptor-frame-v1",
                "center_angstrom": [2.5, 2.0, 0.0],
                "radius_angstrom": 12.0,
                "source_artifact_sha256": "c" * 64,
                "implementation_source_sha256": "d" * 64,
                "metadata": {"fixture": True},
            }
        )
    )
    return receptor, ligand, pocket


def _run(tmp_path: Path) -> dict[str, object]:
    receptor, ligand, pocket = _inputs(tmp_path)
    return run_canonical_docking(
        receptor_path=receptor,
        ligand_path=ligand,
        pocket_path=pocket,
        candidate_count=4,
        top_k=2,
        max_torsions=1,
        translation_radius_angstrom=2.0,
        seed=131,
        receptor_margin_angstrom=4.0,
    )


@pytest.mark.parametrize("radius", [True, "12.0"])
def test_canonical_cli_rejects_nonnumeric_pocket_radius(
    tmp_path: Path,
    radius: object,
) -> None:
    receptor, ligand, pocket = _inputs(tmp_path)
    document = json.loads(pocket.read_bytes())
    document["radius_angstrom"] = radius
    pocket.write_bytes(_canonical_json_bytes(document))
    with pytest.raises(EngineV2CliError, match="geometry is invalid"):
        run_canonical_docking(
            receptor_path=receptor,
            ligand_path=ligand,
            pocket_path=pocket,
            candidate_count=1,
            top_k=1,
            max_torsions=1,
            translation_radius_angstrom=0.0,
            seed=131,
            receptor_margin_angstrom=4.0,
        )


def test_canonical_cli_vertical_slice_emits_failure_complete_evidence(
    tmp_path: Path,
) -> None:
    document = _run(tmp_path)
    assert document["schema_id"] == CLI_DOCKING_RESULT_SCHEMA_ID
    assert document["candidate_count"] == 4
    assert document["success_count"] + document["failure_count"] == 4
    assert document["scorer_source_binding_mode"] == SCORER_SOURCE_BINDING_MODE
    assert document["scorer_source_preimport_attested"] is False
    assert document["chemistry_inference_performed"] is False
    assert document["pocket_prediction_performed"] is False
    assert document["calibrated"] is False
    assert document["claim_safe"] is False
    assert len(document["authenticated_input_receipt_sha256"]) == 64
    assert len(document["result_receipt_sha256"]) == 64
    projection = dict(document)
    observed = projection.pop("document_sha256")
    assert observed == hashlib.sha256(
        json.dumps(
            projection,
            ensure_ascii=True,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("ascii")
    ).hexdigest()
    json.dumps(document, allow_nan=False, sort_keys=True)


def test_console_command_writes_private_canonical_output(
    tmp_path: Path,
) -> None:
    receptor, ligand, pocket = _inputs(tmp_path)
    output = tmp_path / "result.json"
    arguments = [
        "dock-canonical",
        "--receptor",
        str(receptor),
        "--ligand",
        str(ligand),
        "--pocket",
        str(pocket),
        "--output",
        str(output),
        "--candidate-count",
        "3",
        "--top-k",
        "2",
        "--max-torsions",
        "1",
        "--translation-radius-angstrom",
        "1.0",
        "--seed",
        "137",
    ]
    assert main(arguments) == 0
    assert stat.S_IMODE(os.stat(output).st_mode) == 0o600
    raw = output.read_bytes()
    assert raw.endswith(b"\n")
    assert json.loads(raw)["schema_id"] == CLI_DOCKING_RESULT_SCHEMA_ID
    assert main(arguments) == 2


def test_noncanonical_pocket_and_symlink_input_fail_closed(
    tmp_path: Path,
) -> None:
    receptor, ligand, pocket = _inputs(tmp_path)
    document = json.loads(pocket.read_bytes())
    pocket.write_text(json.dumps(document), encoding="ascii")
    with pytest.raises(EngineV2CliError, match="not canonical"):
        run_canonical_docking(
            receptor_path=receptor,
            ligand_path=ligand,
            pocket_path=pocket,
            candidate_count=1,
            top_k=1,
            max_torsions=1,
            translation_radius_angstrom=0.0,
            seed=139,
            receptor_margin_angstrom=4.0,
        )

    fresh_receptor, fresh_ligand, canonical_pocket = _inputs(
        tmp_path / "fresh"
    )
    receptor_link = tmp_path / "receptor-link.json"
    receptor_link.symlink_to(fresh_receptor)
    with pytest.raises(EngineV2CliError, match="could not be read"):
        run_canonical_docking(
            receptor_path=receptor_link,
            ligand_path=fresh_ligand,
            pocket_path=canonical_pocket,
            candidate_count=1,
            top_k=1,
            max_torsions=1,
            translation_radius_angstrom=0.0,
            seed=149,
            receptor_margin_angstrom=4.0,
        )


def test_package_declares_the_console_dispatch_entry_point() -> None:
    pyproject = (
        ROOT / "packaging" / "engine-v2" / "pyproject.toml"
    ).read_text(encoding="utf-8")
    assert "[project.scripts]" in pyproject
    assert (
        'betelgeuze-engine-v2 = "betelgeuze_engine_v2.cli_dispatch:main"'
        in pyproject
    )

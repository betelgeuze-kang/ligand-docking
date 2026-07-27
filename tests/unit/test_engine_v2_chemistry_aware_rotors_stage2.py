from __future__ import annotations

from dataclasses import replace

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
from betelgeuze_engine_v2.docking import (  # noqa: E402
    derive_authoritative_torsion_search_space,
)
from betelgeuze_engine_v2.docking.authority import (  # noqa: E402
    TORSION_SEARCH_SPACE_DERIVATION_SCHEMA_ID,
)


_ATOMIC_NUMBERS = {"H": 1, "C": 6, "N": 7, "O": 8, "S": 16}


def _system(
    elements: list[str],
    bonds: list[tuple[int, int, float, str]],
    *,
    formal_charges: list[int] | None = None,
) -> AllAtomSystem:
    atom_count = len(elements)
    charges = formal_charges or [0] * atom_count
    if len(charges) != atom_count:
        raise ValueError("formal charge fixture length mismatch")
    return AllAtomSystem(
        system_id="chemistry-aware-rotor-stage2",
        atoms=tuple(
            Atom(
                index=index,
                name=f"{element}{index}",
                element=element,
                atomic_number=_ATOMIC_NUMBERS[element],
                residue_index=0,
                formal_charge=charges[index],
            )
            for index, element in enumerate(elements)
        ),
        bonds=tuple(
            Bond(
                index=index,
                atom_i=min(first, second),
                atom_j=max(first, second),
                order=order,
                stereo=stereo,
            )
            for index, (first, second, order, stereo) in enumerate(bonds)
        ),
        residues=(
            Residue(
                index=0,
                name="LIG",
                chain_index=0,
                sequence_number=1,
                atom_indices=tuple(range(atom_count)),
            ),
        ),
        chains=(Chain(index=0, chain_id="L", residue_indices=(0,)),),
        coordinates=torch.tensor(
            [
                [
                    [
                        1.3 * index,
                        0.4 * (index % 2),
                        0.2 * (index % 3),
                    ]
                    for index in range(atom_count)
                ]
            ],
            dtype=torch.float64,
        ),
        provenance=StructureProvenance(
            source_format="unit",
            source_id="chemistry-aware-rotor-stage2",
            source_sha256="a" * 64,
            parser_name="chemistry-aware-rotor-stage2-fixture",
            parser_version="1.0.0",
        ),
    )


def _dispositions(system: AllAtomSystem) -> tuple[dict[tuple[int, int], str], int]:
    search_space, receipt = derive_authoritative_torsion_search_space(system)
    return (
        {
            (first, second): disposition
            for first, second, disposition in receipt.rotor_bond_dispositions
        },
        search_space.torsion_count,
    )


@pytest.mark.parametrize(
    ("system", "bond_pair", "expected"),
    [
        (
            _system(
                ["O", "C", "N", "C", "C"],
                [
                    (0, 1, 2.0, "none"),
                    (1, 2, 1.0, "none"),
                    (2, 3, 1.0, "none"),
                    (1, 4, 1.0, "none"),
                ],
            ),
            (1, 2),
            "amide",
        ),
        (
            _system(
                ["O", "C", "N", "C", "N", "C"],
                [
                    (0, 1, 2.0, "none"),
                    (1, 2, 1.0, "none"),
                    (2, 3, 1.0, "none"),
                    (1, 4, 1.0, "none"),
                    (4, 5, 1.0, "none"),
                ],
            ),
            (1, 2),
            "urea",
        ),
        (
            _system(
                ["O", "C", "N", "C", "O", "C"],
                [
                    (0, 1, 2.0, "none"),
                    (1, 2, 1.0, "none"),
                    (2, 3, 1.0, "none"),
                    (1, 4, 1.0, "none"),
                    (4, 5, 1.0, "none"),
                ],
            ),
            (1, 4),
            "carbamate",
        ),
        (
            _system(
                ["O", "S", "O", "N", "C", "C"],
                [
                    (0, 1, 2.0, "none"),
                    (1, 2, 2.0, "none"),
                    (1, 3, 1.0, "none"),
                    (3, 4, 1.0, "none"),
                    (1, 5, 1.0, "none"),
                ],
            ),
            (1, 3),
            "sulfonamide",
        ),
        (
            _system(
                ["C", "C", "C", "C"],
                [
                    (0, 1, 2.0, "none"),
                    (1, 2, 1.0, "none"),
                    (2, 3, 2.0, "none"),
                ],
            ),
            (1, 2),
            "conjugated_bond",
        ),
        (
            _system(
                ["O", "C", "O", "C", "C"],
                [
                    (0, 1, 2.0, "none"),
                    (1, 2, 1.0, "none"),
                    (2, 3, 1.0, "none"),
                    (1, 4, 1.0, "none"),
                ],
            ),
            (1, 2),
            "conjugated_bond",
        ),
        (
            _system(
                ["C", "C", "C", "C"],
                [
                    (0, 1, 1.0, "none"),
                    (1, 2, 1.0, "up"),
                    (2, 3, 1.0, "none"),
                ],
            ),
            (1, 2),
            "stereo_constrained_bond",
        ),
    ],
)
def test_restricted_chemistry_bonds_are_not_rotors(
    system: AllAtomSystem,
    bond_pair: tuple[int, int],
    expected: str,
) -> None:
    dispositions, torsion_count = _dispositions(system)
    assert dispositions[bond_pair] == expected
    assert torsion_count == 0


def test_urea_and_carbamate_classify_each_restricted_center_bond() -> None:
    urea_dispositions, _ = _dispositions(
        _system(
            ["O", "C", "N", "C", "N", "C"],
            [
                (0, 1, 2.0, "none"),
                (1, 2, 1.0, "none"),
                (2, 3, 1.0, "none"),
                (1, 4, 1.0, "none"),
                (4, 5, 1.0, "none"),
            ],
        )
    )
    assert urea_dispositions[(1, 2)] == "urea"
    assert urea_dispositions[(1, 4)] == "urea"

    carbamate_dispositions, _ = _dispositions(
        _system(
            ["O", "C", "N", "C", "O", "C"],
            [
                (0, 1, 2.0, "none"),
                (1, 2, 1.0, "none"),
                (2, 3, 1.0, "none"),
                (1, 4, 1.0, "none"),
                (4, 5, 1.0, "none"),
            ],
        )
    )
    assert carbamate_dispositions[(1, 2)] == "carbamate"
    assert carbamate_dispositions[(1, 4)] == "carbamate"


def test_charge_separated_sulfonamide_is_not_a_rotor() -> None:
    dispositions, torsion_count = _dispositions(
        _system(
            ["O", "S", "O", "N", "C", "C"],
            [
                (0, 1, 1.0, "none"),
                (1, 2, 1.0, "none"),
                (1, 3, 1.0, "none"),
                (3, 4, 1.0, "none"),
                (1, 5, 1.0, "none"),
            ],
            formal_charges=[-1, 2, -1, 0, 0, 0],
        )
    )
    assert dispositions[(1, 3)] == "sulfonamide"
    assert torsion_count == 0


def test_ordinary_nonterminal_aliphatic_single_bonds_remain_rotors() -> None:
    dispositions, torsion_count = _dispositions(
        _system(
            ["C", "C", "C", "C", "C"],
            [
                (0, 1, 1.0, "none"),
                (1, 2, 1.0, "none"),
                (2, 3, 1.0, "none"),
                (3, 4, 1.0, "none"),
            ],
        )
    )
    assert dispositions == {
        (0, 1): "terminal_heavy_atom",
        (1, 2): "rotatable",
        (2, 3): "rotatable",
        (3, 4): "terminal_heavy_atom",
    }
    assert torsion_count == 2


def test_explicit_hydrogens_do_not_turn_a_terminal_heavy_bond_into_a_rotor() -> None:
    dispositions, torsion_count = _dispositions(
        _system(
            ["C", "C", "H", "H", "H", "H"],
            [
                (0, 1, 1.0, "none"),
                (0, 2, 1.0, "none"),
                (0, 3, 1.0, "none"),
                (1, 4, 1.0, "none"),
                (1, 5, 1.0, "none"),
            ],
        )
    )
    assert dispositions[(0, 1)] == "terminal_heavy_atom"
    assert all(
        disposition == "hydrogen_bond"
        for pair, disposition in dispositions.items()
        if pair != (0, 1)
    )
    assert torsion_count == 0


def test_receipt_records_one_canonical_disposition_per_bond() -> None:
    system = _system(
        ["C", "C", "C", "C", "C"],
        [
            (0, 1, 1.0, "none"),
            (1, 2, 1.0, "none"),
            (2, 3, 1.0, "none"),
            (3, 4, 1.0, "none"),
        ],
    )
    _, receipt = derive_authoritative_torsion_search_space(system)
    document = receipt.to_dict()

    assert TORSION_SEARCH_SPACE_DERIVATION_SCHEMA_ID.endswith("/3.0.0")
    assert len(receipt.rotor_bond_dispositions) == len(system.bonds)
    assert document["chemistry_aware_rotor_rules_applied"] is True
    assert document["rotor_perception_chemically_validated"] is False
    assert document["rotor_bond_dispositions"] == [
        {
            "atom_indices": [first, second],
            "disposition": disposition,
        }
        for first, second, disposition in receipt.rotor_bond_dispositions
    ]

    with pytest.raises(
        ValueError,
        match="rotor bond dispositions are invalid",
    ):
        replace(
            receipt,
            rotor_bond_dispositions=receipt.rotor_bond_dispositions[:-1],
        )

    swapped = tuple(
        (
            first,
            second,
            (
                "rotatable"
                if (first, second) == (0, 1)
                else "terminal_heavy_atom"
                if (first, second) == (1, 2)
                else disposition
            ),
        )
        for first, second, disposition in receipt.rotor_bond_dispositions
    )
    with pytest.raises(
        ValueError,
        match="rotatable bond dispositions and child indices disagree",
    ):
        replace(receipt, rotor_bond_dispositions=swapped)

from __future__ import annotations

import json

import pytest


pytest.importorskip("torch")

from betelgeuze_engine_v2.molecular import smirks_pattern_parser as parser  # noqa: E402
from betelgeuze_engine_v2.molecular.smirks_pattern_parser import (  # noqa: E402
    SMIRKS_PATTERN_MAX_MAP_INDEX,
    SMIRKS_PATTERN_PARSER_BLOCKERS,
    SMIRKS_SUPPORTED_ATOM_PRIMITIVE_KINDS,
    SMIRKS_SUPPORTED_BOND_PRIMITIVES,
    SmirksPatternParserError,
    parse_smirks_pattern,
    parse_smirks_patterns,
    require_smirks_query_document,
)


def test_reviewed_offxml_patterns_decompose_into_typed_queries() -> None:
    query = parse_smirks_pattern("[#6X4:1]-[#6X4:2]")
    payload = query.to_dict()

    assert payload["atom_count"] == 2
    assert payload["bond_count"] == 1
    assert payload["mapped_indices"] == [1, 2]
    assert payload["every_atom_mapped"] is True
    assert payload["bond_primitives"] == ["single"]
    assert payload["pattern_parsed"] is True
    assert payload["every_primitive_recognized"] is True
    assert payload["molecules_traversed"] is False
    assert payload["atom_typing_implemented"] is False
    assert payload["parameters_assigned"] is False
    assert payload["scientifically_validated"] is False
    assert payload["claim_safe"] is False
    assert list(payload["scientific_blockers"]) == list(
        SMIRKS_PATTERN_PARSER_BLOCKERS
    )

    first = payload["atoms"][0]
    assert first["map_index"] == 1
    assert first["mapped"] is True
    assert first["matches_any_atom"] is False
    kinds = {row["kind"]: row for row in first["primitives"]}
    assert kinds["atomic_number"]["value"] == 6
    assert kinds["connectivity"]["value"] == 4

    bond = payload["bonds"][0]
    assert (bond["atom_i"], bond["atom_j"]) == (0, 1)
    assert bond["primitive"] == "single"
    assert bond["explicit_in_pattern"] is True


def test_branch_and_any_atom_patterns_are_parsed() -> None:
    payload = parse_smirks_pattern("[*:1]~[#6X3:2](~[*:3])~[*:4]").to_dict()
    assert payload["atom_count"] == 4
    assert payload["bond_count"] == 3
    assert payload["mapped_indices"] == [1, 2, 3, 4]
    assert payload["bond_primitives"] == ["any"]
    assert payload["atoms"][0]["matches_any_atom"] is True

    # The branch must attach both the branch atom and the trailing atom to the
    # central atom, not chain them linearly.
    pairs = {(row["atom_i"], row["atom_j"]) for row in payload["bonds"]}
    assert pairs == {(0, 1), (1, 2), (1, 3)}


def test_implicit_bond_between_adjacent_atoms_is_recorded_as_implicit() -> None:
    payload = parse_smirks_pattern("[#6:1][#8:2]").to_dict()
    assert payload["bond_count"] == 1
    bond = payload["bonds"][0]
    assert bond["primitive"] == "single_or_aromatic"
    assert bond["explicit_in_pattern"] is False
    assert bond["raw"] == ""


def test_every_supported_bond_primitive_round_trips() -> None:
    for token, primitive in SMIRKS_SUPPORTED_BOND_PRIMITIVES.items():
        payload = parse_smirks_pattern(f"[#6:1]{token}[#6:2]").to_dict()
        assert payload["bond_primitives"] == [primitive]
        assert payload["bonds"][0]["raw"] == token


@pytest.mark.parametrize(
    ("pattern", "kind", "value"),
    (
        ("[#7:1]", "atomic_number", 7),
        ("[a:1]", "aromatic", None),
        ("[A:1]", "aliphatic", None),
        ("[#6X3:1]", "connectivity", 3),
        ("[#6D2:1]", "explicit_degree", 2),
        ("[#6H3:1]", "total_hydrogen_count", 3),
        ("[#6R1:1]", "ring_membership_count", 1),
        ("[#6r6:1]", "ring_size", 6),
        ("[#8+1:1]", "formal_charge", 1),
        ("[#8-1:1]", "formal_charge", -1),
        ("[#8+0:1]", "formal_charge", 0),
        ("[#7+:1]", "formal_charge", 1),
        ("[#8--:1]", "formal_charge", -2),
    ),
)
def test_supported_atom_primitives_are_typed(
    pattern: str,
    kind: str,
    value: int | None,
) -> None:
    assert kind in SMIRKS_SUPPORTED_ATOM_PRIMITIVE_KINDS
    payload = parse_smirks_pattern(pattern).to_dict()
    primitives = {row["kind"]: row for row in payload["atoms"][0]["primitives"]}
    assert kind in primitives
    assert primitives[kind]["value"] == value


def test_unmapped_atoms_are_allowed_and_reported() -> None:
    payload = parse_smirks_pattern("[#6X4:1]-[#1]").to_dict()
    assert payload["mapped_indices"] == [1]
    assert payload["mapped_atom_count"] == 1
    assert payload["every_atom_mapped"] is False
    assert payload["atoms"][1]["mapped"] is False
    assert payload["atoms"][1]["map_index"] is None


@pytest.mark.parametrize(
    ("pattern", "message"),
    (
        ("[#6X4:1],[#7:2]", "not in the reviewed SMIRKS subset"),
        ("[!#6:1]", "not in the reviewed subset"),
        ("[$(C=O):1]", "not in the reviewed subset"),
        ("[#6:1]1-[#6:2]1", "not in the reviewed SMIRKS subset"),
        ("[#6:1]", None),
        ("C-C", "not in the reviewed SMIRKS subset"),
        ("[#6:1]-", "dangling bond primitive"),
        ("-[#6:1]", "precedes its first atom"),
        ("[#6:1]-=[#6:2]", "two bond primitives appear in sequence"),
        ("[#6:1]", None),
        ("[#6:1", "not closed with ]"),
        ("[:1]", "atom expression is empty"),
        ("[#6:1](-[#6:2]", "branch is not closed"),
        ("[#6:1])", "branch closes without opening"),
        ("([#6:1])", "branch opens before its first atom"),
        ("[#6:1]-([#6:2])", "branch opens after a dangling bond primitive"),
        ("[#6:1]:1", "not in the reviewed SMIRKS subset"),
        ("[#6:1]-[#6:1]", "map indices must be unique"),
        ("[#6:0]", "outside the reviewed bound"),
        (f"[#6:{SMIRKS_PATTERN_MAX_MAP_INDEX + 1}]", "outside the reviewed bound"),
    ),
)
def test_unsupported_or_malformed_patterns_fail_closed(
    pattern: str,
    message: str | None,
) -> None:
    if message is None:
        parse_smirks_pattern(pattern)
        return
    with pytest.raises(SmirksPatternParserError, match=message):
        parse_smirks_pattern(pattern)


@pytest.mark.parametrize(
    "value",
    ("", "   ", "[#6:1] [#6:2]", "[#6:1]\n", 7, None),
)
def test_pattern_input_must_be_bounded_text(value: object) -> None:
    with pytest.raises(
        SmirksPatternParserError,
        match="bounded whitespace-free text",
    ):
        parse_smirks_pattern(value)


def test_atom_and_bond_bounds_are_enforced() -> None:
    long_chain = "-".join(f"[#6:{i}]" for i in range(1, 5))
    parse_smirks_pattern(long_chain)

    oversized = "-".join("[#6]" for _ in range(parser.SMIRKS_PATTERN_MAX_ATOMS + 1))
    with pytest.raises(SmirksPatternParserError, match="exceeds its atom bound"):
        parse_smirks_pattern(oversized)


def test_batch_parse_fails_closed_on_any_pattern() -> None:
    queries = parse_smirks_patterns(("[#6:1]-[#6:2]", "[#1:1]"))
    assert [row.to_dict()["atom_count"] for row in queries] == [2, 1]

    with pytest.raises(SmirksPatternParserError):
        parse_smirks_patterns(("[#6:1]-[#6:2]", "[!#6:1]"))


def test_query_document_is_deterministic_and_self_authenticating() -> None:
    query = parse_smirks_pattern("[*:1]~[#6X4:2]-[*:3]")
    again = parse_smirks_pattern("[*:1]~[#6X4:2]-[*:3]")
    assert again.to_dict() == query.to_dict()

    payload = query.to_dict()
    validated = require_smirks_query_document(payload)
    assert validated["query_sha256"] == payload["query_sha256"]


def test_query_document_validator_rejects_tamper_and_claim_promotion() -> None:
    payload = parse_smirks_pattern("[#6X4:1]-[#1:2]").to_dict()

    tampered = json.loads(json.dumps(payload))
    tampered["atom_count"] += 1
    with pytest.raises(SmirksPatternParserError, match="digest is invalid"):
        require_smirks_query_document(tampered)

    atom_tamper = json.loads(json.dumps(payload))
    atom_tamper["atoms"][0]["map_index"] = 5
    with pytest.raises(SmirksPatternParserError):
        require_smirks_query_document(atom_tamper)

    promoted = json.loads(json.dumps(payload))
    promoted.pop("query_sha256")
    promoted["atom_typing_implemented"] = True
    promoted["query_sha256"] = parser._sha256(promoted)
    with pytest.raises(
        SmirksPatternParserError,
        match="must keep atom_typing_implemented=false",
    ):
        require_smirks_query_document(promoted)

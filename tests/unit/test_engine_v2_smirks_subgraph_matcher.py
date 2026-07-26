from __future__ import annotations

import json

import pytest


pytest.importorskip("torch")

from betelgeuze_engine_v2.molecular import (  # noqa: E402
    mmcif_nonpoly_parameter_source_binding as binding_module,
)
from betelgeuze_engine_v2.molecular import (  # noqa: E402
    mmcif_nonpoly_preparation_corpus as corpus_module,
)
from betelgeuze_engine_v2.molecular import (  # noqa: E402
    smirks_subgraph_matcher as matcher,
)
from betelgeuze_engine_v2.molecular.smirks_pattern_parser import (  # noqa: E402
    parse_smirks_pattern,
)
from betelgeuze_engine_v2.molecular.smirks_subgraph_matcher import (  # noqa: E402
    SMIRKS_SUBGRAPH_MATCHER_BLOCKERS,
    SmirksSubgraphMatcherError,
    match_smirks_pattern,
    match_smirks_query,
    require_smirks_assignment_document,
    require_smirks_match_set_document,
    resolve_last_match_assignment,
)


@pytest.fixture(scope="module")
def system() -> object:
    """Formaldehyde-like bound system: C(=O)(H)(H) at indices 0..3."""

    for case in corpus_module.mmcif_nonpoly_preparation_corpus_cases():
        snapshot = binding_module.parse_mmcif_nonpoly_parameter_source_bindings(
            case.source_text
        )
        for report in snapshot.instance_reports:
            if report.bound_system is None:
                continue
            elements = [atom.element for atom in report.bound_system.atoms]
            if elements == ["C", "O", "H", "H"]:
                return report.bound_system
    raise AssertionError("corpus has no bound C/O/H/H system")


def test_element_and_bond_patterns_match_expected_atoms(system: object) -> None:
    carbon = match_smirks_pattern("[#6:1]", system).to_dict()
    assert carbon["match_count"] == 1
    assert carbon["matches"][0]["mapped_atom_indices"] == [0]
    assert carbon["atom_typing_implemented"] is True
    assert carbon["parameter_values_applied"] is False
    assert carbon["scientifically_validated"] is False
    assert carbon["claim_safe"] is False
    assert list(carbon["scientific_blockers"]) == list(
        SMIRKS_SUBGRAPH_MATCHER_BLOCKERS
    )

    hydrogens = match_smirks_pattern("[#1:1]", system).to_dict()
    assert [row["mapped_atom_indices"] for row in hydrogens["matches"]] == [[2], [3]]
    assert hydrogens["matched_atom_indices"] == [2, 3]

    double = match_smirks_pattern("[#6:1]=[#8:2]", system).to_dict()
    assert [row["mapped_atom_indices"] for row in double["matches"]] == [[0, 1]]

    single = match_smirks_pattern("[#6:1]-[#1:2]", system).to_dict()
    assert [row["mapped_atom_indices"] for row in single["matches"]] == [
        [0, 2],
        [0, 3],
    ]


def test_bond_order_is_enforced_not_ignored(system: object) -> None:
    assert match_smirks_pattern("[#6:1]-[#8:2]", system).to_dict()["match_count"] == 0
    assert match_smirks_pattern("[#6:1]=[#1:2]", system).to_dict()["match_count"] == 0
    assert match_smirks_pattern("[#6:1]~[#8:2]", system).to_dict()["match_count"] == 1
    assert match_smirks_pattern("[#6:1]#[#8:2]", system).to_dict()["match_count"] == 0


def test_connectivity_hydrogen_and_charge_primitives_are_evaluated(
    system: object,
) -> None:
    assert match_smirks_pattern("[#6X3:1]", system).to_dict()["match_count"] == 1
    assert match_smirks_pattern("[#6X4:1]", system).to_dict()["match_count"] == 0
    assert match_smirks_pattern("[#6H2:1]", system).to_dict()["match_count"] == 1
    assert match_smirks_pattern("[#6H3:1]", system).to_dict()["match_count"] == 0
    assert match_smirks_pattern("[#8X1:1]", system).to_dict()["match_count"] == 1
    assert match_smirks_pattern("[#6+0:1]", system).to_dict()["match_count"] == 1
    assert match_smirks_pattern("[#6+1:1]", system).to_dict()["match_count"] == 0
    assert match_smirks_pattern("[A:1]", system).to_dict()["match_count"] == 4
    assert match_smirks_pattern("[a:1]", system).to_dict()["match_count"] == 0


def test_acyclic_system_reports_no_ring_membership(system: object) -> None:
    assert match_smirks_pattern("[#6R0:1]", system).to_dict()["match_count"] == 1
    assert match_smirks_pattern("[#6R1:1]", system).to_dict()["match_count"] == 0
    ring_query = match_smirks_pattern("[#6R0:1]", system).to_dict()
    assert ring_query["ring_primitives_used"] is True
    assert match_smirks_pattern("[#6:1]", system).to_dict()[
        "ring_primitives_used"
    ] is False


def test_angle_pattern_enumerates_ordered_mapped_tuples(system: object) -> None:
    payload = match_smirks_pattern("[*:1]~[#6:2]~[*:3]", system).to_dict()
    tuples = [row["mapped_atom_indices"] for row in payload["matches"]]
    assert tuples == [
        [1, 0, 2],
        [1, 0, 3],
        [2, 0, 1],
        [2, 0, 3],
        [3, 0, 1],
        [3, 0, 2],
    ]
    assert all(row["mapped_indices"] == [1, 2, 3] for row in payload["matches"])
    assert payload["match_ordering_follows_mapped_indices"] is True


def test_unmapped_query_atoms_are_excluded_from_mapped_tuples(
    system: object,
) -> None:
    payload = match_smirks_pattern("[#6:1]-[#1]", system).to_dict()
    assert payload["match_count"] == 2
    for row in payload["matches"]:
        assert row["mapped_atom_indices"] == [0]
        assert len(row["atom_indices"]) == 2


def test_atoms_are_not_reused_within_one_match(system: object) -> None:
    # A carbon cannot satisfy both mapped atoms of a C-C pattern here.
    assert match_smirks_pattern("[#6:1]~[#6:2]", system).to_dict()["match_count"] == 0


def test_last_declared_parameter_wins_and_records_superseded(
    system: object,
) -> None:
    assignment = resolve_last_match_assignment(
        (
            {"parameter_id": "b-generic", "smirks": "[*:1]~[*:2]"},
            {"parameter_id": "b-specific", "smirks": "[#6:1]=[#8:2]"},
        ),
        system,
    )
    payload = assignment.to_dict()

    assert payload["conflict_resolution"] == "last_declared_matching_parameter_wins"
    assert payload["last_declared_match_wins"] is True
    assert payload["parameter_ids"] == ["b-generic", "b-specific"]
    resolved = {
        tuple(row["mapped_atom_indices"]): row for row in payload["resolved"]
    }

    carbonyl = resolved[(0, 1)]
    assert carbonyl["parameter_id"] == "b-specific"
    assert carbonyl["superseded_parameter_ids"] == ["b-generic"]
    assert carbonyl["declaration_order"] == 1

    ch_bond = resolved[(0, 2)]
    assert ch_bond["parameter_id"] == "b-generic"
    assert ch_bond["superseded_parameter_ids"] == []
    assert payload["superseded_candidate_count"] >= 1
    assert payload["parameter_values_applied"] is False
    assert payload["claim_safe"] is False


def test_declaration_order_reversal_changes_the_winner(system: object) -> None:
    reversed_order = resolve_last_match_assignment(
        (
            {"parameter_id": "b-specific", "smirks": "[#6:1]=[#8:2]"},
            {"parameter_id": "b-generic", "smirks": "[*:1]~[*:2]"},
        ),
        system,
    ).to_dict()
    resolved = {
        tuple(row["mapped_atom_indices"]): row for row in reversed_order["resolved"]
    }
    assert resolved[(0, 1)]["parameter_id"] == "b-generic"
    assert resolved[(0, 1)]["superseded_parameter_ids"] == ["b-specific"]


def test_assignment_rejects_empty_and_duplicate_parameter_ids(
    system: object,
) -> None:
    with pytest.raises(
        SmirksSubgraphMatcherError,
        match="requires at least one parameter",
    ):
        resolve_last_match_assignment((), system)

    with pytest.raises(
        SmirksSubgraphMatcherError,
        match="must be unique within one handler",
    ):
        resolve_last_match_assignment(
            (
                {"parameter_id": "b1", "smirks": "[#6:1]=[#8:2]"},
                {"parameter_id": "b1", "smirks": "[#6:1]-[#1:2]"},
            ),
            system,
        )

    with pytest.raises(
        SmirksSubgraphMatcherError,
        match="non-empty parameter_id",
    ):
        resolve_last_match_assignment(({"smirks": "[#6:1]"},), system)


def test_unsupported_pattern_and_query_type_fail_closed(system: object) -> None:
    with pytest.raises(
        SmirksSubgraphMatcherError,
        match="not in the reviewed subset",
    ):
        match_smirks_pattern("[!#6:1]", system)

    with pytest.raises(
        SmirksSubgraphMatcherError,
        match="must be a parsed SMIRKS query",
    ):
        match_smirks_query("[#6:1]", system)  # type: ignore[arg-type]


def test_match_set_document_is_deterministic_and_self_authenticating(
    system: object,
) -> None:
    query = parse_smirks_pattern("[#6:1]-[#1:2]")
    first = match_smirks_query(query, system)
    second = match_smirks_query(query, system)
    assert first.to_dict() == second.to_dict()
    assert first.query_sha256 == query.query_sha256

    payload = first.to_dict()
    validated = require_smirks_match_set_document(payload)
    assert validated["match_set_sha256"] == payload["match_set_sha256"]


def test_match_set_validator_rejects_tamper_and_claim_promotion(
    system: object,
) -> None:
    payload = match_smirks_pattern("[#6:1]-[#1:2]", system).to_dict()

    tampered = json.loads(json.dumps(payload))
    tampered["match_count"] += 1
    with pytest.raises(SmirksSubgraphMatcherError, match="digest is invalid"):
        require_smirks_match_set_document(tampered)

    row_tamper = json.loads(json.dumps(payload))
    row_tamper["matches"][0]["mapped_atom_indices"] = [9]
    with pytest.raises(SmirksSubgraphMatcherError):
        require_smirks_match_set_document(row_tamper)

    promoted = json.loads(json.dumps(payload))
    promoted.pop("match_set_sha256")
    promoted["parameter_values_applied"] = True
    promoted["match_set_sha256"] = matcher._sha256(promoted)
    with pytest.raises(
        SmirksSubgraphMatcherError,
        match="must keep parameter_values_applied=false",
    ):
        require_smirks_match_set_document(promoted)


def test_assignment_validator_rejects_tamper_and_rule_substitution(
    system: object,
) -> None:
    payload = resolve_last_match_assignment(
        ({"parameter_id": "b1", "smirks": "[*:1]~[*:2]"},),
        system,
    ).to_dict()
    assert require_smirks_assignment_document(payload)["assignment_sha256"] == (
        payload["assignment_sha256"]
    )

    tampered = json.loads(json.dumps(payload))
    tampered["resolved_tuple_count"] += 1
    with pytest.raises(SmirksSubgraphMatcherError, match="digest is invalid"):
        require_smirks_assignment_document(tampered)

    substituted = json.loads(json.dumps(payload))
    substituted.pop("assignment_sha256")
    substituted["conflict_resolution"] = "first_declared_wins"
    substituted["assignment_sha256"] = matcher._sha256(substituted)
    with pytest.raises(
        SmirksSubgraphMatcherError,
        match="declares a different conflict rule",
    ):
        require_smirks_assignment_document(substituted)

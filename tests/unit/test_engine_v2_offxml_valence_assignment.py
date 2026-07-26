from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest


pytest.importorskip("torch")

from betelgeuze_engine_v2.molecular import (  # noqa: E402
    mmcif_nonpoly_parameter_source_binding as binding_module,
)
from betelgeuze_engine_v2.molecular import (  # noqa: E402
    mmcif_nonpoly_preparation_corpus as corpus_module,
)
from betelgeuze_engine_v2.molecular import (  # noqa: E402
    offxml_semantic_parser as offxml_module,
)
from betelgeuze_engine_v2.molecular import (  # noqa: E402
    offxml_valence_assignment as assignment_module,
)
from betelgeuze_engine_v2.molecular.offxml_valence_assignment import (  # noqa: E402
    OFFXML_VALENCE_ASSIGNMENT_BLOCKERS,
    OFFXML_VALENCE_HANDLER_TOPOLOGY,
    OFFXML_VALENCE_REQUIRED_COVERAGE_HANDLERS,
    OffxmlValenceAssignmentError,
    assign_offxml_valence_parameters,
    require_offxml_valence_assignment_document,
)


def _offxml(
    *,
    bond_smirks: str = "[*:1]~[*:2]",
    angle_smirks: str = "[*:1]~[*:2]~[*:3]",
    vdw_extra: str = '<Atom smirks="[*:1]" id="n0" epsilon="0.01 * kilocalorie_per_mole" rmin_half="1.0 * angstrom"/>',
    include_improper: bool = True,
) -> str:
    improper = (
        '  <ImproperTorsions version="0.3" potential="k*(1+cos(periodicity*theta-phase))" default_idivf="auto">\n'
        '    <Improper smirks="[*:1]~[#6X3:2](~[*:3])~[*:4]" id="i1" periodicity1="2"'
        ' phase1="180.0 * degree" k1="1.1 * kilocalorie_per_mole"/>\n'
        "  </ImproperTorsions>\n"
        if include_improper
        else '  <ImproperTorsions version="0.3" potential="k*(1+cos(periodicity*theta-phase))" default_idivf="auto">\n'
        '    <Improper smirks="[#7:1]~[#7X3:2](~[#7:3])~[#7:4]" id="i1" periodicity1="2"'
        ' phase1="180.0 * degree" k1="1.1 * kilocalorie_per_mole"/>\n'
        "  </ImproperTorsions>\n"
    )
    return (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<SMIRNOFF version="0.3" aromaticity_model="OEAroModel_MDL">\n'
        '  <Bonds version="0.4" potential="harmonic">\n'
        f'    <Bond smirks="{bond_smirks}" id="b0" length="1.4 * angstrom"'
        ' k="300.0 * kilocalorie_per_mole/angstrom**2"/>\n'
        '    <Bond smirks="[#6:1]=[#8:2]" id="b1" length="1.22 * angstrom"'
        ' k="600.0 * kilocalorie_per_mole/angstrom**2"/>\n'
        "  </Bonds>\n"
        '  <Angles version="0.3" potential="harmonic">\n'
        f'    <Angle smirks="{angle_smirks}" id="a0" angle="120.0 * degree"'
        ' k="70.0 * kilocalorie_per_mole/radian**2"/>\n'
        "  </Angles>\n"
        '  <ProperTorsions version="0.4" potential="k*(1+cos(periodicity*theta-phase))"'
        ' default_idivf="auto">\n'
        '    <Proper smirks="[*:1]~[*:2]~[*:3]~[*:4]" id="t0" periodicity1="3"'
        ' phase1="0.0 * degree" k1="0.15 * kilocalorie_per_mole" idivf1="1"/>\n'
        "  </ProperTorsions>\n"
        + improper
        + '  <vdW version="0.3" potential="Lennard-Jones-12-6"'
        ' combining_rules="Lorentz-Berthelot" scale12="0.0" scale13="0.0"'
        ' scale14="0.5" scale15="1.0" cutoff="9.0 * angstrom"'
        ' switch_width="1.0 * angstrom" method="cutoff">\n'
        f"    {vdw_extra}\n"
        '    <Atom smirks="[#1:1]" id="n1" epsilon="0.0157 * kilocalorie_per_mole"'
        ' rmin_half="0.6 * angstrom"/>\n'
        "  </vdW>\n"
        '  <Electrostatics version="0.4" scale12="0.0" scale13="0.0"'
        ' scale14="0.833333" scale15="1.0" cutoff="9.0 * angstrom"'
        ' switch_width="0.0 * angstrom"'
        ' periodic_potential="Ewald3D-ConductingBoundary"'
        ' nonperiodic_potential="Coulomb" exception_potential="Coulomb"/>\n'
        "</SMIRNOFF>\n"
    )


def _document(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    text: str,
) -> offxml_module.OffxmlSemanticDocument:
    path = tmp_path / "forcefield.offxml"
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    path.write_bytes(text.encode("utf-8"))
    path.chmod(0o600)
    source = path.read_bytes()
    monkeypatch.setattr(
        offxml_module,
        "PARAMETER_SOURCE_ARTIFACT_SIZE_BYTES",
        len(source),
    )
    monkeypatch.setattr(
        offxml_module,
        "PARAMETER_SOURCE_ARTIFACT_SHA256",
        hashlib.sha256(source).hexdigest(),
    )
    return offxml_module.parse_reviewed_offxml_artifact(path)


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
            if [atom.element for atom in report.bound_system.atoms] == [
                "C",
                "O",
                "H",
                "H",
            ]:
                return report.bound_system
    raise AssertionError("corpus has no bound C/O/H/H system")


def test_every_required_handler_covers_its_topology(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    system: object,
) -> None:
    document = _document(tmp_path, monkeypatch, _offxml())
    payload = assign_offxml_valence_parameters(document, system).to_dict()

    assert payload["system_atom_count"] == 4
    assert payload["offxml_document_sha256"] == document.document_sha256
    assert payload["parameter_assignment_implemented"] is True
    assert payload["required_handler_coverage_complete"] is True
    assert payload["energies_or_forces_evaluated"] is False
    assert payload["partial_charges_assigned"] is False
    assert payload["exclusions_and_one_four_scaling_applied"] is False
    assert payload["scientifically_validated"] is False
    assert payload["claim_safe"] is False
    assert list(payload["scientific_blockers"]) == list(
        OFFXML_VALENCE_ASSIGNMENT_BLOCKERS
    )

    handlers = {row["handler"]: row for row in payload["handlers"]}
    assert set(handlers) == set(OFFXML_VALENCE_HANDLER_TOPOLOGY)
    for handler in OFFXML_VALENCE_REQUIRED_COVERAGE_HANDLERS:
        row = handlers[handler]
        assert row["coverage_required"] is True
        assert row["coverage_complete"] is True
        assert row["unassigned_atom_tuples"] == []

    # Formaldehyde topology: 4 atoms, 3 bonds, 3 angles, 0 propers, 1 improper.
    assert handlers["vdW"]["topology_tuple_count"] == 4
    assert handlers["Bonds"]["topology_tuple_count"] == 3
    assert handlers["Angles"]["topology_tuple_count"] == 3
    assert handlers["ProperTorsions"]["topology_tuple_count"] == 0
    assert handlers["ImproperTorsions"]["topology_tuple_count"] == 1
    assert payload["term_count"] == 4 + 3 + 3 + 0 + 1


def test_last_declared_bond_parameter_wins_and_records_superseded(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    system: object,
) -> None:
    document = _document(tmp_path, monkeypatch, _offxml())
    payload = assign_offxml_valence_parameters(document, system).to_dict()
    bonds = {
        tuple(row["atom_indices"]): row
        for row in next(
            item for item in payload["handlers"] if item["handler"] == "Bonds"
        )["terms"]
    }

    carbonyl = bonds[(0, 1)]
    assert carbonyl["parameter_id"] == "b1"
    assert carbonyl["superseded_parameter_ids"] == ["b0"]
    assert carbonyl["values"]["length"]["unit"] == "angstrom"
    assert float.fromhex(carbonyl["values"]["length"]["value_binary64_hex"]) == 1.22
    assert carbonyl["values_evaluated_in_energy_term"] is False

    ch_bond = bonds[(0, 2)]
    assert ch_bond["parameter_id"] == "b0"
    assert ch_bond["superseded_parameter_ids"] == []
    assert float.fromhex(ch_bond["values"]["length"]["value_binary64_hex"]) == 1.4


def test_angle_terms_use_canonical_endpoint_order(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    system: object,
) -> None:
    document = _document(tmp_path, monkeypatch, _offxml())
    payload = assign_offxml_valence_parameters(document, system).to_dict()
    angles = next(
        item for item in payload["handlers"] if item["handler"] == "Angles"
    )
    tuples = [tuple(row["atom_indices"]) for row in angles["terms"]]
    assert tuples == [(1, 0, 2), (1, 0, 3), (2, 0, 3)]
    assert all(row["topology"] == "angle" for row in angles["terms"])


def test_improper_coverage_is_optional_and_reported(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    system: object,
) -> None:
    document = _document(tmp_path, monkeypatch, _offxml(include_improper=False))
    payload = assign_offxml_valence_parameters(document, system).to_dict()
    impropers = next(
        item
        for item in payload["handlers"]
        if item["handler"] == "ImproperTorsions"
    )
    assert impropers["coverage_required"] is False
    assert impropers["coverage_complete"] is False
    assert impropers["unassigned_atom_tuples"] == [[1, 0, 2, 3]]
    assert payload["required_handler_coverage_complete"] is True


@pytest.mark.parametrize(
    ("kwargs", "handler"),
    (
        ({"bond_smirks": "[#7:1]~[#7:2]"}, "Bonds"),
        ({"angle_smirks": "[#7:1]~[#7:2]~[#7:3]"}, "Angles"),
        ({"vdw_extra": '<Atom smirks="[#7:1]" id="n0" epsilon="0.01 * kilocalorie_per_mole" rmin_half="1.0 * angstrom"/>'}, "vdW"),
    ),
)
def test_incomplete_required_coverage_fails_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    system: object,
    kwargs: dict[str, str],
    handler: str,
) -> None:
    document = _document(tmp_path, monkeypatch, _offxml(**kwargs))
    with pytest.raises(
        OffxmlValenceAssignmentError,
        match=f"handler {handler} leaves its topology partially assigned",
    ):
        assign_offxml_valence_parameters(document, system)


def test_assignment_requires_a_parsed_offxml_document(system: object) -> None:
    with pytest.raises(
        OffxmlValenceAssignmentError,
        match="requires a parsed OFFXML semantic document",
    ):
        assign_offxml_valence_parameters({}, system)  # type: ignore[arg-type]


def test_assignment_document_is_deterministic_and_self_authenticating(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    system: object,
) -> None:
    document = _document(tmp_path, monkeypatch, _offxml())
    first = assign_offxml_valence_parameters(document, system)
    second = assign_offxml_valence_parameters(document, system)
    assert first.to_dict() == second.to_dict()

    payload = first.to_dict()
    validated = require_offxml_valence_assignment_document(payload)
    assert validated["assignment_sha256"] == payload["assignment_sha256"]


def test_assignment_validator_rejects_tamper_and_claim_promotion(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    system: object,
) -> None:
    document = _document(tmp_path, monkeypatch, _offxml())
    payload = assign_offxml_valence_parameters(document, system).to_dict()

    tampered = json.loads(json.dumps(payload))
    tampered["term_count"] += 1
    with pytest.raises(OffxmlValenceAssignmentError, match="digest is invalid"):
        require_offxml_valence_assignment_document(tampered)

    term_tamper = json.loads(json.dumps(payload))
    handler = next(
        row for row in term_tamper["handlers"] if row["handler"] == "Bonds"
    )
    handler["terms"][0]["parameter_id"] = "forged"
    with pytest.raises(OffxmlValenceAssignmentError):
        require_offxml_valence_assignment_document(term_tamper)

    promoted = json.loads(json.dumps(payload))
    promoted.pop("assignment_sha256")
    promoted["energies_or_forces_evaluated"] = True
    promoted["assignment_sha256"] = assignment_module._sha256(promoted)
    with pytest.raises(
        OffxmlValenceAssignmentError,
        match="must keep energies_or_forces_evaluated=false",
    ):
        require_offxml_valence_assignment_document(promoted)


def test_validator_rejects_published_incomplete_required_coverage(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    system: object,
) -> None:
    document = _document(tmp_path, monkeypatch, _offxml())
    payload = json.loads(
        json.dumps(assign_offxml_valence_parameters(document, system).to_dict())
    )
    handler = next(row for row in payload["handlers"] if row["handler"] == "Bonds")
    handler.pop("handler_assignment_sha256")
    handler["coverage_complete"] = False
    handler["handler_assignment_sha256"] = assignment_module._sha256(handler)
    payload.pop("assignment_sha256")
    payload["assignment_sha256"] = assignment_module._sha256(payload)
    with pytest.raises(
        OffxmlValenceAssignmentError,
        match="publishes incomplete required coverage",
    ):
        require_offxml_valence_assignment_document(payload)

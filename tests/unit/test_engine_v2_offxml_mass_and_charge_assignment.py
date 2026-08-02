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
    offxml_mass_and_charge_assignment as assignment_module,
)
from betelgeuze_engine_v2.molecular import (  # noqa: E402
    offxml_semantic_parser as offxml_module,
)
from betelgeuze_engine_v2.molecular.offxml_mass_and_charge_assignment import (  # noqa: E402
    OFFXML_MASS_CHARGE_ASSIGNMENT_BLOCKERS,
    OFFXML_REVIEWED_ATOMIC_WEIGHT_SOURCE_ID,
    OFFXML_REVIEWED_STANDARD_ATOMIC_WEIGHTS_DA,
    OffxmlMassAndChargeAssignmentError,
    assign_offxml_masses_and_charges,
    require_offxml_mass_and_charge_assignment_document,
)


_CARBONYL_LIBRARY = (
    '    <LibraryCharge smirks="[#6:1](=[#8:2])([#1:3])[#1:4]" id="lc-formaldehyde"'
    ' charge1="0.1 * elementary_charge" charge2="-0.3 * elementary_charge"'
    ' charge3="0.1 * elementary_charge" charge4="0.1 * elementary_charge"/>'
)


def _offxml(library_entries: str = _CARBONYL_LIBRARY) -> str:
    return (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<SMIRNOFF version="0.3" aromaticity_model="OEAroModel_MDL">\n'
        '  <Bonds version="0.4" potential="harmonic">\n'
        '    <Bond smirks="[*:1]~[*:2]" id="b0" length="1.4 * angstrom"'
        ' k="300.0 * kilocalorie_per_mole/angstrom**2"/>\n'
        "  </Bonds>\n"
        '  <Angles version="0.3" potential="harmonic">\n'
        '    <Angle smirks="[*:1]~[*:2]~[*:3]" id="a0" angle="120.0 * degree"'
        ' k="70.0 * kilocalorie_per_mole/radian**2"/>\n'
        "  </Angles>\n"
        '  <ProperTorsions version="0.4"'
        ' potential="k*(1+cos(periodicity*theta-phase))" default_idivf="auto">\n'
        '    <Proper smirks="[*:1]~[*:2]~[*:3]~[*:4]" id="t0" periodicity1="3"'
        ' phase1="0.0 * degree" k1="0.15 * kilocalorie_per_mole" idivf1="1"/>\n'
        "  </ProperTorsions>\n"
        '  <ImproperTorsions version="0.3"'
        ' potential="k*(1+cos(periodicity*theta-phase))" default_idivf="auto">\n'
        '    <Improper smirks="[*:1]~[#6X3:2](~[*:3])~[*:4]" id="i1"'
        ' periodicity1="2" phase1="180.0 * degree"'
        ' k1="1.1 * kilocalorie_per_mole"/>\n'
        "  </ImproperTorsions>\n"
        '  <vdW version="0.3" potential="Lennard-Jones-12-6"'
        ' combining_rules="Lorentz-Berthelot" scale12="0.0" scale13="0.0"'
        ' scale14="0.5" scale15="1.0" cutoff="9.0 * angstrom"'
        ' switch_width="1.0 * angstrom" method="cutoff">\n'
        '    <Atom smirks="[*:1]" id="n0" epsilon="0.01 * kilocalorie_per_mole"'
        ' rmin_half="1.0 * angstrom"/>\n'
        "  </vdW>\n"
        '  <LibraryCharges version="0.3">\n'
        + library_entries
        + "\n  </LibraryCharges>\n"
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


def test_every_atom_receives_a_reviewed_mass_and_library_charge(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    system: object,
) -> None:
    document = _document(tmp_path, monkeypatch, _offxml())
    payload = assign_offxml_masses_and_charges(document, system).to_dict()

    assert payload["atom_count"] == 4
    assert payload["assigned_mass_atom_count"] == 4
    assert payload["assigned_charge_atom_count"] == 4
    assert payload["atom_masses_assigned"] is True
    assert payload["partial_charges_assigned"] is True
    assert payload["mass_coverage_complete"] is True
    assert payload["charge_coverage_complete"] is True
    assert payload["total_formal_charge_conserved"] is True
    assert payload["isotope_specific_masses_assigned"] is False
    assert payload["charge_generation_implemented"] is False
    assert payload["energies_or_forces_evaluated"] is False
    assert payload["scientifically_validated"] is False
    assert payload["claim_safe"] is False
    assert list(payload["scientific_blockers"]) == list(
        OFFXML_MASS_CHARGE_ASSIGNMENT_BLOCKERS
    )
    assert payload["offxml_document_sha256"] == document.document_sha256


def test_masses_come_from_the_reviewed_table_keyed_by_atomic_number(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    system: object,
) -> None:
    document = _document(tmp_path, monkeypatch, _offxml())
    payload = assign_offxml_masses_and_charges(document, system).to_dict()
    rows = {row["atom_index"]: row for row in payload["atoms"]}

    assert float.fromhex(rows[0]["mass_da_binary64_hex"]) == (
        OFFXML_REVIEWED_STANDARD_ATOMIC_WEIGHTS_DA[6]
    )
    assert float.fromhex(rows[1]["mass_da_binary64_hex"]) == (
        OFFXML_REVIEWED_STANDARD_ATOMIC_WEIGHTS_DA[8]
    )
    for index in (2, 3):
        assert float.fromhex(rows[index]["mass_da_binary64_hex"]) == (
            OFFXML_REVIEWED_STANDARD_ATOMIC_WEIGHTS_DA[1]
        )
    for row in rows.values():
        assert row["mass_source_id"] == OFFXML_REVIEWED_ATOMIC_WEIGHT_SOURCE_ID
        assert row["isotope_specific_mass_assigned"] is False
        assert row["values_evaluated_in_energy_term"] is False


def test_library_charges_land_on_their_mapped_positions(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    system: object,
) -> None:
    document = _document(tmp_path, monkeypatch, _offxml())
    payload = assign_offxml_masses_and_charges(document, system).to_dict()
    rows = {row["atom_index"]: row for row in payload["atoms"]}

    assert float.fromhex(rows[0]["partial_charge_e_binary64_hex"]) == 0.1
    assert float.fromhex(rows[1]["partial_charge_e_binary64_hex"]) == -0.3
    assert float.fromhex(rows[2]["partial_charge_e_binary64_hex"]) == 0.1
    assert float.fromhex(rows[3]["partial_charge_e_binary64_hex"]) == 0.1
    assert rows[1]["charge_map_position"] == 1
    assert all(
        row["charge_parameter_id"] == "lc-formaldehyde" for row in rows.values()
    )
    assert payload["distinct_charge_parameter_ids"] == ["lc-formaldehyde"]
    assert payload["total_formal_charge"] == 0
    assert abs(
        float.fromhex(payload["assigned_charge_total_e_binary64_hex"])
    ) < 1e-9


def test_last_declared_library_charge_wins(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    system: object,
) -> None:
    generic = (
        '    <LibraryCharge smirks="[#6:1](=[#8:2])([#1:3])[#1:4]" id="lc-first"'
        ' charge1="0.5 * elementary_charge" charge2="-0.9 * elementary_charge"'
        ' charge3="0.2 * elementary_charge" charge4="0.2 * elementary_charge"/>\n'
        + _CARBONYL_LIBRARY
    )
    document = _document(tmp_path, monkeypatch, _offxml(generic))
    payload = assign_offxml_masses_and_charges(document, system).to_dict()
    rows = {row["atom_index"]: row for row in payload["atoms"]}

    assert all(
        row["charge_parameter_id"] == "lc-formaldehyde" for row in rows.values()
    )
    assert rows[0]["superseded_charge_parameter_ids"] == ["lc-first"]
    assert rows[0]["charge_declaration_order"] == 1
    assert float.fromhex(rows[1]["partial_charge_e_binary64_hex"]) == -0.3
    assert payload["superseded_charge_candidate_count"] >= 4


def test_incomplete_charge_coverage_fails_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    system: object,
) -> None:
    partial = (
        '    <LibraryCharge smirks="[#6:1]=[#8:2]" id="lc-partial"'
        ' charge1="0.1 * elementary_charge" charge2="-0.1 * elementary_charge"/>'
    )
    document = _document(tmp_path, monkeypatch, _offxml(partial))
    with pytest.raises(
        OffxmlMassAndChargeAssignmentError,
        match="without a partial charge",
    ):
        assign_offxml_masses_and_charges(document, system)


def test_non_conserving_charge_vector_fails_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    system: object,
) -> None:
    unbalanced = (
        '    <LibraryCharge smirks="[#6:1](=[#8:2])([#1:3])[#1:4]" id="lc-bad"'
        ' charge1="0.4 * elementary_charge" charge2="-0.3 * elementary_charge"'
        ' charge3="0.1 * elementary_charge" charge4="0.1 * elementary_charge"/>'
    )
    document = _document(tmp_path, monkeypatch, _offxml(unbalanced))
    with pytest.raises(
        OffxmlMassAndChargeAssignmentError,
        match="do not conserve the total formal charge",
    ):
        assign_offxml_masses_and_charges(document, system)


@pytest.mark.parametrize(
    ("entry", "message"),
    (
        (
            '    <LibraryCharge smirks="[#6:1](=[#8:2])([#1:3])[#1:4]" id="lc-x"'
            ' charge1="0.1 * elementary_charge" charge2="-0.3 * elementary_charge"'
            ' charge4="0.1 * elementary_charge"/>',
            "ordinals are not contiguous",
        ),
        (
            '    <LibraryCharge smirks="[#6:1](=[#8:2])([#1:3])[#1:4]" id="lc-x"'
            ' charge1="0.1 * kilocalorie_per_mole"'
            ' charge2="-0.3 * elementary_charge"'
            ' charge3="0.1 * elementary_charge"'
            ' charge4="0.1 * elementary_charge"/>',
            "must declare elementary_charge",
        ),
        (
            '    <LibraryCharge smirks="[#6:1](=[#8:2])([#1:3])[#1:4]" id="lc-x"'
            ' epsilon="0.1 * kilocalorie_per_mole"/>',
            "declares no charge value",
        ),
        (
            '    <LibraryCharge smirks="[#6:1]=[#8:2]" id="lc-x"'
            ' charge1="0.1 * elementary_charge"/>',
            "declares 1 charges for 2 mapped atoms",
        ),
    ),
)
def test_malformed_library_charge_entries_fail_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    system: object,
    entry: str,
    message: str,
) -> None:
    document = _document(tmp_path, monkeypatch, _offxml(entry))
    with pytest.raises(OffxmlMassAndChargeAssignmentError, match=message):
        assign_offxml_masses_and_charges(document, system)


def test_missing_library_charges_section_fails_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    system: object,
) -> None:
    text = _offxml()
    start = text.index("  <LibraryCharges")
    end = text.index("  <Electrostatics")
    document = _document(tmp_path, monkeypatch, text[:start] + text[end:])
    with pytest.raises(
        OffxmlMassAndChargeAssignmentError,
        match="omits the LibraryCharges section",
    ):
        assign_offxml_masses_and_charges(document, system)


def test_unreviewed_element_mass_fails_closed() -> None:
    with pytest.raises(
        OffxmlMassAndChargeAssignmentError,
        match="outside the reviewed mass table",
    ):
        assignment_module._reviewed_mass(30)


def test_assignment_requires_a_parsed_offxml_document(system: object) -> None:
    with pytest.raises(
        OffxmlMassAndChargeAssignmentError,
        match="requires a parsed OFFXML semantic document",
    ):
        assign_offxml_masses_and_charges({}, system)  # type: ignore[arg-type]


def test_document_is_deterministic_and_self_authenticating(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    system: object,
) -> None:
    document = _document(tmp_path, monkeypatch, _offxml())
    first = assign_offxml_masses_and_charges(document, system)
    second = assign_offxml_masses_and_charges(document, system)
    assert first.to_dict() == second.to_dict()

    payload = first.to_dict()
    validated = require_offxml_mass_and_charge_assignment_document(payload)
    assert validated["assignment_sha256"] == payload["assignment_sha256"]


def test_validator_rejects_tamper_promotion_and_published_non_conservation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    system: object,
) -> None:
    document = _document(tmp_path, monkeypatch, _offxml())
    payload = assign_offxml_masses_and_charges(document, system).to_dict()

    tampered = json.loads(json.dumps(payload))
    tampered["atom_count"] += 1
    with pytest.raises(
        OffxmlMassAndChargeAssignmentError,
        match="digest is invalid",
    ):
        require_offxml_mass_and_charge_assignment_document(tampered)

    row_tamper = json.loads(json.dumps(payload))
    row_tamper["atoms"][0]["partial_charge_e_binary64_hex"] = float(9.0).hex()
    with pytest.raises(OffxmlMassAndChargeAssignmentError):
        require_offxml_mass_and_charge_assignment_document(row_tamper)

    promoted = json.loads(json.dumps(payload))
    promoted.pop("assignment_sha256")
    promoted["charge_generation_implemented"] = True
    promoted["assignment_sha256"] = assignment_module._sha256(promoted)
    with pytest.raises(
        OffxmlMassAndChargeAssignmentError,
        match="must keep charge_generation_implemented=false",
    ):
        require_offxml_mass_and_charge_assignment_document(promoted)

    drifted = json.loads(json.dumps(payload))
    drifted.pop("assignment_sha256")
    drifted["assigned_charge_total_e_binary64_hex"] = float(0.5).hex()
    drifted["assignment_sha256"] = assignment_module._sha256(drifted)
    with pytest.raises(
        OffxmlMassAndChargeAssignmentError,
        match="non-conserving charge total",
    ):
        require_offxml_mass_and_charge_assignment_document(drifted)


def test_validator_rejects_dropped_atom_rows(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    system: object,
) -> None:
    document = _document(tmp_path, monkeypatch, _offxml())
    payload = json.loads(
        json.dumps(assign_offxml_masses_and_charges(document, system).to_dict())
    )
    payload.pop("assignment_sha256")
    payload["atoms"] = payload["atoms"][:-1]
    payload["assignment_sha256"] = assignment_module._sha256(payload)
    with pytest.raises(
        OffxmlMassAndChargeAssignmentError,
        match="omits atom rows",
    ):
        require_offxml_mass_and_charge_assignment_document(payload)

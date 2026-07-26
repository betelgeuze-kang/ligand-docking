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
    offxml_nonbonded_exclusions as exclusions_module,
)
from betelgeuze_engine_v2.molecular import (  # noqa: E402
    offxml_semantic_parser as offxml_module,
)
from betelgeuze_engine_v2.molecular.offxml_nonbonded_exclusions import (  # noqa: E402
    OFFXML_NONBONDED_EXCLUSIONS_BLOCKERS,
    OFFXML_NONBONDED_SCALED_HANDLERS,
    OFFXML_NONBONDED_SEPARATIONS,
    OffxmlNonbondedExclusionsError,
    derive_offxml_nonbonded_exclusions,
    require_offxml_nonbonded_exclusions_document,
)


def _offxml(
    *,
    vdw_scales: str = 'scale12="0.0" scale13="0.0" scale14="0.5" scale15="1.0"',
    electrostatics_scales: str = (
        'scale12="0.0" scale13="0.0" scale14="0.833333" scale15="1.0"'
    ),
) -> str:
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
        ' combining_rules="Lorentz-Berthelot" '
        + vdw_scales
        + ' cutoff="9.0 * angstrom" switch_width="1.0 * angstrom"'
        ' method="cutoff">\n'
        '    <Atom smirks="[*:1]" id="n0" epsilon="0.01 * kilocalorie_per_mole"'
        ' rmin_half="1.0 * angstrom"/>\n'
        "  </vdW>\n"
        '  <Electrostatics version="0.4" '
        + electrostatics_scales
        + ' cutoff="9.0 * angstrom" switch_width="0.0 * angstrom"'
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


def test_every_intramolecular_pair_is_classified_and_claim_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    system: object,
) -> None:
    document = _document(tmp_path, monkeypatch, _offxml())
    payload = derive_offxml_nonbonded_exclusions(document, system).to_dict()

    assert payload["system_atom_count"] == 4
    assert payload["pair_count"] == 6
    assert payload["expected_pair_count"] == 6
    assert payload["exclusions_and_one_four_scaling_derived"] is True
    assert payload["every_intramolecular_pair_classified"] is True
    assert payload["declared_scale_factors_read_not_assumed"] is True
    assert payload["energies_evaluated"] is False
    assert payload["partial_charges_assigned"] is False
    assert payload["periodic_exclusion_policy_derived"] is False
    assert payload["scientifically_validated"] is False
    assert payload["claim_safe"] is False
    assert list(payload["scientific_blockers"]) == list(
        OFFXML_NONBONDED_EXCLUSIONS_BLOCKERS
    )
    assert payload["offxml_document_sha256"] == document.document_sha256


def test_separations_follow_shortest_bonded_path_length(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    system: object,
) -> None:
    document = _document(tmp_path, monkeypatch, _offxml())
    payload = derive_offxml_nonbonded_exclusions(document, system).to_dict()
    pairs = {
        (row["atom_i"], row["atom_j"]): row for row in payload["pairs"]
    }

    # Central carbon is bonded to O, H, H -> those are 1-2 pairs.
    for partner in (1, 2, 3):
        assert pairs[(0, partner)]["separation"] == "one_two"
        assert pairs[(0, partner)]["bonded_path_length"] == 1

    # Terminal atoms are two bonds apart through the carbon -> 1-3 pairs.
    for pair in ((1, 2), (1, 3), (2, 3)):
        assert pairs[pair]["separation"] == "one_three"
        assert pairs[pair]["bonded_path_length"] == 2

    assert payload["separation_counts"] == {
        "one_two": 3,
        "one_three": 3,
        "one_four": 0,
        "one_five_or_greater": 0,
    }


def test_zero_factors_are_recorded_as_exclusions_per_handler(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    system: object,
) -> None:
    document = _document(tmp_path, monkeypatch, _offxml())
    payload = derive_offxml_nonbonded_exclusions(document, system).to_dict()

    for row in payload["pairs"]:
        assert sorted(row["excluded_handler_ids"]) == sorted(
            OFFXML_NONBONDED_SCALED_HANDLERS
        )
        assert row["scaled_handler_ids"] == []
        assert row["factors_evaluated_in_energy_term"] is False
        for handler in OFFXML_NONBONDED_SCALED_HANDLERS:
            assert float.fromhex(row["factors"][handler]) == 0.0

    assert payload["excluded_pair_counts"] == {"vdW": 6, "Electrostatics": 6}
    assert payload["scaled_pair_counts"] == {"vdW": 0, "Electrostatics": 0}


def test_one_four_scale_factors_are_read_per_handler(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    system: object,
) -> None:
    # Declare non-excluding 1-3 factors so this molecule exercises scaling.
    document = _document(
        tmp_path,
        monkeypatch,
        _offxml(
            vdw_scales='scale12="0.0" scale13="0.5" scale14="0.5" scale15="1.0"',
            electrostatics_scales=(
                'scale12="0.0" scale13="0.833333" scale14="0.833333"'
                ' scale15="1.0"'
            ),
        ),
    )
    payload = derive_offxml_nonbonded_exclusions(document, system).to_dict()
    pairs = {(row["atom_i"], row["atom_j"]): row for row in payload["pairs"]}

    one_three = pairs[(2, 3)]
    assert one_three["separation"] == "one_three"
    assert one_three["scale_attribute"] == "scale13"
    assert float.fromhex(one_three["factors"]["vdW"]) == 0.5
    assert float.fromhex(one_three["factors"]["Electrostatics"]) == 0.833333
    assert sorted(one_three["scaled_handler_ids"]) == sorted(
        OFFXML_NONBONDED_SCALED_HANDLERS
    )
    assert one_three["excluded_handler_ids"] == []

    policies = {row["handler"]: row for row in payload["handler_policies"]}
    assert policies["vdW"]["excluded_separations"] == ["one_two"]
    assert policies["vdW"]["scaled_separations"] == ["one_three", "one_four"]
    assert policies["vdW"]["declared_scale_attributes_complete"] is True
    assert set(policies) == set(OFFXML_NONBONDED_SCALED_HANDLERS)
    assert set(policies["vdW"]["factors"]) == set(OFFXML_NONBONDED_SEPARATIONS)


@pytest.mark.parametrize(
    ("vdw_scales", "message"),
    (
        (
            'scale12="0.0" scale13="0.0" scale15="1.0"',
            r"vdW\.scale14 is missing",
        ),
        (
            'scale12="0.0" scale13="0.0" scale14="" scale15="1.0"',
            r"vdW\.scale14 is missing",
        ),
        (
            'scale12="0.0" scale13="0.0" scale14="half" scale15="1.0"',
            r"vdW\.scale14 is not a finite decimal factor",
        ),
        (
            'scale12="0.0" scale13="0.0" scale14="1.5" scale15="1.0"',
            r"outside \[0, 1\]",
        ),
        (
            'scale12="0.0" scale13="0.0" scale14="-0.5" scale15="1.0"',
            r"outside \[0, 1\]",
        ),
    ),
)
def test_missing_or_out_of_range_scale_attributes_fail_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    system: object,
    vdw_scales: str,
    message: str,
) -> None:
    document = _document(tmp_path, monkeypatch, _offxml(vdw_scales=vdw_scales))
    with pytest.raises(OffxmlNonbondedExclusionsError, match=message):
        derive_offxml_nonbonded_exclusions(document, system)


def test_derivation_requires_a_parsed_offxml_document(system: object) -> None:
    with pytest.raises(
        OffxmlNonbondedExclusionsError,
        match="requires a parsed OFFXML semantic document",
    ):
        derive_offxml_nonbonded_exclusions({}, system)  # type: ignore[arg-type]


def test_document_is_deterministic_and_self_authenticating(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    system: object,
) -> None:
    document = _document(tmp_path, monkeypatch, _offxml())
    first = derive_offxml_nonbonded_exclusions(document, system)
    second = derive_offxml_nonbonded_exclusions(document, system)
    assert first.to_dict() == second.to_dict()

    payload = first.to_dict()
    validated = require_offxml_nonbonded_exclusions_document(payload)
    assert validated["exclusions_sha256"] == payload["exclusions_sha256"]


def test_validator_rejects_tamper_claim_promotion_and_dropped_pairs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    system: object,
) -> None:
    document = _document(tmp_path, monkeypatch, _offxml())
    payload = derive_offxml_nonbonded_exclusions(document, system).to_dict()

    tampered = json.loads(json.dumps(payload))
    tampered["pair_count"] += 1
    with pytest.raises(
        OffxmlNonbondedExclusionsError,
        match="digest is invalid",
    ):
        require_offxml_nonbonded_exclusions_document(tampered)

    pair_tamper = json.loads(json.dumps(payload))
    pair_tamper["pairs"][0]["separation"] = "one_four"
    with pytest.raises(OffxmlNonbondedExclusionsError):
        require_offxml_nonbonded_exclusions_document(pair_tamper)

    promoted = json.loads(json.dumps(payload))
    promoted.pop("exclusions_sha256")
    promoted["energies_evaluated"] = True
    promoted["exclusions_sha256"] = exclusions_module._sha256(promoted)
    with pytest.raises(
        OffxmlNonbondedExclusionsError,
        match="must keep energies_evaluated=false",
    ):
        require_offxml_nonbonded_exclusions_document(promoted)

    dropped = json.loads(json.dumps(payload))
    dropped.pop("exclusions_sha256")
    dropped["pairs"] = dropped["pairs"][:-1]
    dropped["pair_count"] = len(dropped["pairs"])
    dropped["exclusions_sha256"] = exclusions_module._sha256(dropped)
    with pytest.raises(
        OffxmlNonbondedExclusionsError,
        match="omits intramolecular pairs",
    ):
        require_offxml_nonbonded_exclusions_document(dropped)

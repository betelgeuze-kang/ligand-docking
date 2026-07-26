from __future__ import annotations

import hashlib
import json
from pathlib import Path
import stat

import pytest


pytest.importorskip("torch")

from betelgeuze_engine_v2.molecular import offxml_semantic_parser as parser  # noqa: E402
from betelgeuze_engine_v2.molecular.offxml_semantic_parser import (  # noqa: E402
    OFFXML_SEMANTIC_PARSER_ALLOWED_UNITS,
    OFFXML_SEMANTIC_PARSER_BLOCKERS,
    OFFXML_SEMANTIC_PARSER_REQUIRED_HANDLERS,
    OffxmlSemanticParserError,
    parse_reviewed_offxml_artifact,
    require_offxml_semantic_document,
)
from betelgeuze_engine_v2.parameter_source_provenance import (  # noqa: E402
    PARAMETER_SOURCE_ARTIFACT_SHA256,
    PARAMETER_SOURCE_ARTIFACT_SIZE_BYTES,
)


_OFFXML = """<?xml version="1.0" encoding="utf-8"?>
<SMIRNOFF version="0.3" aromaticity_model="OEAroModel_MDL">
  <Bonds version="0.4" potential="harmonic" fractional_bondorder_method="AM1-Wiberg">
    <Bond smirks="[#6X4:1]-[#6X4:2]" id="b1" length="1.52 * angstrom"
          k="419.9 * kilocalorie_per_mole/angstrom**2"/>
    <Bond smirks="[#6X4:1]-[#1:2]" id="b2" length="1.09 * angstrom"
          k="379.1 * kilocalorie_per_mole/angstrom**2"/>
  </Bonds>
  <Angles version="0.3" potential="harmonic">
    <Angle smirks="[*:1]~[#6X4:2]-[*:3]" id="a1" angle="107.7 * degree"
           k="101.7 * kilocalorie_per_mole/radian**2"/>
  </Angles>
  <ProperTorsions version="0.4" potential="k*(1+cos(periodicity*theta-phase))"
                  default_idivf="auto">
    <Proper smirks="[*:1]-[#6X4:2]-[#6X4:3]-[*:4]" id="t1" periodicity1="3"
            phase1="0.0 * degree" k1="0.153 * kilocalorie_per_mole" idivf1="1"/>
  </ProperTorsions>
  <ImproperTorsions version="0.3"
                    potential="k*(1+cos(periodicity*theta-phase))"
                    default_idivf="auto">
    <Improper smirks="[*:1]~[#6X3:2](~[*:3])~[*:4]" id="i1" periodicity1="2"
              phase1="180.0 * degree" k1="1.1 * kilocalorie_per_mole"/>
  </ImproperTorsions>
  <vdW version="0.3" potential="Lennard-Jones-12-6" combining_rules="Lorentz-Berthelot"
       scale12="0.0" scale13="0.0" scale14="0.5" scale15="1.0"
       cutoff="9.0 * angstrom" switch_width="1.0 * angstrom" method="cutoff">
    <Atom smirks="[#1:1]" id="n1" epsilon="0.0157 * kilocalorie_per_mole"
          rmin_half="0.6 * angstrom"/>
    <Atom smirks="[#6X4:1]" id="n2" epsilon="0.1094 * kilocalorie_per_mole"
          rmin_half="1.9080 * angstrom"/>
  </vdW>
  <Electrostatics version="0.4" scale12="0.0" scale13="0.0" scale14="0.833333"
                  scale15="1.0" cutoff="9.0 * angstrom" switch_width="0.0 * angstrom"
                  periodic_potential="Ewald3D-ConductingBoundary"
                  nonperiodic_potential="Coulomb"
                  exception_potential="Coulomb"/>
</SMIRNOFF>
"""


def _write_artifact(path: Path, text: str) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    path.write_bytes(text.encode("utf-8"))
    path.chmod(0o600)


@pytest.fixture()
def artifact(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / "openff_unconstrained-2.2.1.offxml"
    _write_artifact(path, _OFFXML)
    source = path.read_bytes()
    monkeypatch.setattr(
        parser,
        "PARAMETER_SOURCE_ARTIFACT_SIZE_BYTES",
        len(source),
    )
    monkeypatch.setattr(
        parser,
        "PARAMETER_SOURCE_ARTIFACT_SHA256",
        hashlib.sha256(source).hexdigest(),
    )
    return path


def test_parser_reads_handlers_units_and_stays_claim_closed(artifact: Path) -> None:
    document = parse_reviewed_offxml_artifact(artifact)
    payload = document.to_dict()

    assert payload["smirnoff_version"] == "0.3"
    assert payload["required_handlers_present"] is True
    assert set(payload["handler_ids"]) == set(
        OFFXML_SEMANTIC_PARSER_REQUIRED_HANDLERS
    )
    assert payload["handler_ids"] == sorted(payload["handler_ids"])
    assert payload["parameter_count"] == 7
    assert payload["artifact_identity_verified"] is True
    assert payload["declared_units_read_not_inferred"] is True
    assert payload["smirks_matched_against_molecules"] is False
    assert payload["atom_typing_implemented"] is False
    assert payload["parameter_assignment_implemented"] is False
    assert payload["partial_charges_assigned"] is False
    assert payload["scientifically_validated"] is False
    assert payload["claim_safe"] is False
    assert list(payload["scientific_blockers"]) == list(
        OFFXML_SEMANTIC_PARSER_BLOCKERS
    )
    assert set(payload["declared_unit_ids"]) <= set(
        OFFXML_SEMANTIC_PARSER_ALLOWED_UNITS
    )


def test_parameter_rows_carry_smirks_and_exact_values(artifact: Path) -> None:
    payload = parse_reviewed_offxml_artifact(artifact).to_dict()
    handlers = {row["handler"]: row for row in payload["handlers"]}

    bonds = handlers["Bonds"]
    assert bonds["version"] == "0.4"
    assert bonds["section_attributes"]["potential"] == "harmonic"
    assert [row["parameter_id"] for row in bonds["parameters"]] == ["b1", "b2"]
    first = bonds["parameters"][0]
    assert first["smirks"] == "[#6X4:1]-[#6X4:2]"
    quantities = {row["attribute"]: row for row in first["quantities"]}
    assert float.fromhex(quantities["length"]["value_binary64_hex"]) == 1.52
    assert quantities["length"]["unit"] == "angstrom"
    assert quantities["k"]["unit"] == "kilocalorie_per_mole/angstrom**2"
    assert quantities["length"]["unit_declared_in_source"] is True
    assert first["smirks_matched_against_molecules"] is False

    torsion = handlers["ProperTorsions"]["parameters"][0]
    torsion_quantities = {row["attribute"]: row for row in torsion["quantities"]}
    assert float.fromhex(torsion_quantities["periodicity1"]["value_binary64_hex"]) == 3.0
    assert torsion_quantities["periodicity1"]["unit"] == "dimensionless"
    assert torsion_quantities["periodicity1"]["unit_declared_in_source"] is False
    assert float.fromhex(torsion_quantities["phase1"]["value_binary64_hex"]) == 0.0

    electrostatics = handlers["Electrostatics"]
    assert electrostatics["parameter_count"] == 0
    assert electrostatics["section_attributes"]["periodic_potential"] == (
        "Ewald3D-ConductingBoundary"
    )


def test_unreviewed_unit_fails_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    text = _OFFXML.replace("1.52 * angstrom", "1.52 * furlong")
    path = tmp_path / "unit.offxml"
    _write_artifact(path, text)
    source = path.read_bytes()
    monkeypatch.setattr(parser, "PARAMETER_SOURCE_ARTIFACT_SIZE_BYTES", len(source))
    monkeypatch.setattr(
        parser,
        "PARAMETER_SOURCE_ARTIFACT_SHA256",
        hashlib.sha256(source).hexdigest(),
    )
    with pytest.raises(
        OffxmlSemanticParserError,
        match="unreviewed unit furlong",
    ):
        parse_reviewed_offxml_artifact(path)


@pytest.mark.parametrize(
    ("mutation", "message"),
    (
        ("drop_handler", "omits required handler"),
        ("bad_version", "unsupported SMIRNOFF version"),
        ("empty_section", "declares no parameter entries"),
        ("missing_section_version", "does not declare a version"),
        ("doctype", "document type or entity"),
        ("malformed", "not well-formed XML"),
        ("wrong_root", "root element is not SMIRNOFF"),
    ),
)
def test_structural_defects_fail_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mutation: str,
    message: str,
) -> None:
    if mutation == "drop_handler":
        start = _OFFXML.index("  <Angles")
        end = _OFFXML.index("  <ProperTorsions")
        text = _OFFXML[:start] + _OFFXML[end:]
    elif mutation == "bad_version":
        text = _OFFXML.replace('<SMIRNOFF version="0.3"', '<SMIRNOFF version="9.9"')
    elif mutation == "empty_section":
        start = _OFFXML.index("  <Angles")
        end = _OFFXML.index("  <ProperTorsions")
        text = (
            _OFFXML[:start]
            + '  <Angles version="0.3" potential="harmonic"/>\n'
            + _OFFXML[end:]
        )
    elif mutation == "missing_section_version":
        text = _OFFXML.replace('<Angles version="0.3"', "<Angles")
    elif mutation == "doctype":
        text = _OFFXML.replace(
            "<SMIRNOFF",
            "<!DOCTYPE SMIRNOFF []>\n<SMIRNOFF",
            1,
        )
    elif mutation == "malformed":
        text = _OFFXML.replace("</SMIRNOFF>", "")
    else:
        text = _OFFXML.replace("SMIRNOFF version=", "NOTSMIRNOFF version=").replace(
            "</SMIRNOFF>", "</NOTSMIRNOFF>"
        )

    path = tmp_path / f"{mutation}.offxml"
    _write_artifact(path, text)
    source = path.read_bytes()
    monkeypatch.setattr(parser, "PARAMETER_SOURCE_ARTIFACT_SIZE_BYTES", len(source))
    monkeypatch.setattr(
        parser,
        "PARAMETER_SOURCE_ARTIFACT_SHA256",
        hashlib.sha256(source).hexdigest(),
    )
    with pytest.raises(OffxmlSemanticParserError, match=message):
        parse_reviewed_offxml_artifact(path)


def test_artifact_digest_and_size_are_pinned_to_the_reviewed_release(
    tmp_path: Path,
) -> None:
    path = tmp_path / "unreviewed.offxml"
    _write_artifact(path, _OFFXML)
    assert len(path.read_bytes()) != PARAMETER_SOURCE_ARTIFACT_SIZE_BYTES
    with pytest.raises(
        OffxmlSemanticParserError,
        match="size does not match the reviewed artifact",
    ):
        parse_reviewed_offxml_artifact(path)

    padded = tmp_path / "padded.offxml"
    body = _OFFXML.encode("utf-8")
    padding = b" " * (PARAMETER_SOURCE_ARTIFACT_SIZE_BYTES - len(body))
    padded.write_bytes(body + padding)
    padded.chmod(0o600)
    assert len(padded.read_bytes()) == PARAMETER_SOURCE_ARTIFACT_SIZE_BYTES
    assert hashlib.sha256(padded.read_bytes()).hexdigest() != (
        PARAMETER_SOURCE_ARTIFACT_SHA256
    )
    with pytest.raises(
        OffxmlSemanticParserError,
        match="digest does not match the reviewed artifact",
    ):
        parse_reviewed_offxml_artifact(padded)


def test_symlinked_artifact_is_rejected(tmp_path: Path) -> None:
    real = tmp_path / "real.offxml"
    _write_artifact(real, _OFFXML)
    link = tmp_path / "link.offxml"
    link.symlink_to(real)
    with pytest.raises(
        OffxmlSemanticParserError,
        match="non-symlink regular file",
    ):
        parse_reviewed_offxml_artifact(link)


def test_document_is_deterministic_and_self_authenticating(
    artifact: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    document = parse_reviewed_offxml_artifact(artifact)
    again = parse_reviewed_offxml_artifact(artifact)
    assert again.canonical_bytes() == document.canonical_bytes()

    payload = document.to_dict()
    monkeypatch.setattr(
        parser,
        "PARAMETER_SOURCE_ARTIFACT_SHA256",
        payload["artifact_sha256"],
    )
    validated = require_offxml_semantic_document(payload)
    assert validated["document_sha256"] == payload["document_sha256"]


def test_document_validator_rejects_tamper_and_claim_promotion(
    artifact: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = parse_reviewed_offxml_artifact(artifact).to_dict()
    monkeypatch.setattr(
        parser,
        "PARAMETER_SOURCE_ARTIFACT_SHA256",
        payload["artifact_sha256"],
    )

    tampered = json.loads(json.dumps(payload))
    tampered["parameter_count"] += 1
    with pytest.raises(OffxmlSemanticParserError, match="digest is invalid"):
        require_offxml_semantic_document(tampered)

    handler_tamper = json.loads(json.dumps(payload))
    handler_tamper["handlers"][0]["parameter_count"] += 1
    with pytest.raises(OffxmlSemanticParserError):
        require_offxml_semantic_document(handler_tamper)

    promoted = json.loads(json.dumps(payload))
    promoted.pop("document_sha256")
    promoted["parameter_assignment_implemented"] = True
    promoted["document_sha256"] = parser._sha256(promoted)
    with pytest.raises(
        OffxmlSemanticParserError,
        match="must keep parameter_assignment_implemented=false",
    ):
        require_offxml_semantic_document(promoted)


def test_document_must_name_the_reviewed_artifact(
    artifact: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = parse_reviewed_offxml_artifact(artifact).to_dict()

    # Restore the real reviewed digest: a document parsed from any other
    # artifact must not validate against the reviewed release.
    monkeypatch.setattr(
        parser,
        "PARAMETER_SOURCE_ARTIFACT_SHA256",
        PARAMETER_SOURCE_ARTIFACT_SHA256,
    )
    assert payload["artifact_sha256"] != PARAMETER_SOURCE_ARTIFACT_SHA256
    with pytest.raises(
        OffxmlSemanticParserError,
        match="does not name the reviewed artifact",
    ):
        require_offxml_semantic_document(payload)


def test_write_json_is_private_and_refuses_overwrite(
    tmp_path: Path,
    artifact: Path,
) -> None:
    document = parse_reviewed_offxml_artifact(artifact)
    output = tmp_path / "receipts" / "offxml.json"
    document.write_json(output)
    assert stat.S_IMODE(output.stat().st_mode) == 0o600
    assert output.read_bytes() == document.canonical_bytes()

    with pytest.raises(OffxmlSemanticParserError, match="already exists"):
        document.write_json(output)

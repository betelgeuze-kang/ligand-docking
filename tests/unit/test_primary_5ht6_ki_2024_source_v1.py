"""Source-only 2024 paper ledger integrity, with no protected outcomes."""

from copy import deepcopy
import hashlib
import os
from pathlib import Path

import pytest
from rdkit import Chem
from rdkit.Chem import inchi, rdMolDescriptors

from tools.product import primary_5ht6_ki_2024_source_v1 as source


LEDGER = (
    Path(__file__).resolve().parents[2]
    / "docs/evidence/human_5ht6_ki_2024_source_ledger_v1.json"
)


def _official_pdf() -> Path:
    value = os.environ.get("BETELGEUZE_HT6_2024_PDF")
    if not value:
        pytest.skip("official local 2024 PDF was not supplied")
    path = Path(value)
    if not path.is_file():
        pytest.skip("official local 2024 PDF is unavailable")
    return path


def test_committed_ledger_has_exact_reviewed_rows_and_unassigned_authority():
    ledger, digest = source.verify_ledger(LEDGER)
    assert len(digest) == 64
    assert [row["paper_row_id"] for row in ledger["rows"]] == [
        "PR49", "PR58", "PR59"
    ]
    assert [row["reported_ki_mean"] for row in ledger["rows"]] == [
        "0.077", "0.172", "1.964"
    ]
    assert [row["reported_ki_sd"] for row in ledger["rows"]] == [
        "0.018", "0.041", "0.452"
    ]
    assert all(row["assigned_role"] is None
               and row["prepared_state_origin"] is None
               and row["fit_admitted"] is False for row in ledger["rows"])
    assert set(ledger["authority"].values()) == {False}


def test_threshold_projection_keeps_continuous_ki_and_sd_distinct():
    ledger, _ = source.verify_ledger(LEDGER)
    rows = {row["paper_row_id"]: row for row in ledger["rows"]}
    assert source._derived_classes(rows["PR49"]) == ("active", "active")
    assert source._derived_classes(rows["PR58"]) == ("active", "not_stable")
    assert source._derived_classes(rows["PR59"]) == ("inactive", "inactive")
    assert rows["PR58"]["reported_ki_mean"] == "0.172"
    assert rows["PR58"]["reported_ki_sd"] == "0.041"
    assert ledger["threshold_projection"]["context"] == (
        "paper_pharmacophore_model_only"
    )


def test_proposed_neutral_graphs_agree_with_recorded_formula_and_identity():
    ledger, _ = source.verify_ledger(LEDGER)
    keys = set()
    for row in ledger["rows"]:
        graph = row["proposed_neutral_graph"]
        molecule = Chem.MolFromSmiles(graph["canonical_isomeric_smiles"])
        assert molecule is not None
        assert Chem.MolToSmiles(molecule, canonical=True, isomericSmiles=True) == (
            graph["canonical_isomeric_smiles"]
        )
        assert rdMolDescriptors.CalcMolFormula(molecule) == graph["formula"]
        assert inchi.MolToInchiKey(molecule) == graph["inchikey"]
        assert Chem.GetFormalCharge(molecule) == graph["formal_charge"] == 0
        assert len(Chem.GetMolFrags(molecule)) == graph["fragment_count"] == 1
        keys.add(graph["inchikey"])
    assert len(keys) == len(ledger["rows"])


@pytest.mark.parametrize("field,replacement", [
    ("reported_ki_mean", "0.017"),
    ("reported_ki_sd", "0.004"),
    ("reported_ki_unit", "nM"),
    ("exact_published_name", "PR49"),
    ("threshold_derived_class_at_mean", "inactive"),
    ("assigned_role", "development_test"),
    ("prepared_state_origin", {"path": "/invented", "sha256": "f" * 64}),
])
def test_changed_label_units_identity_or_authority_rejected(
    tmp_path, field, replacement,
):
    altered = deepcopy(source.EXPECTED_LEDGER)
    altered["rows"][0][field] = replacement
    path = tmp_path / "altered-ledger.json"
    path.write_bytes(source.canonical_ledger_bytes(altered))
    with pytest.raises(ValueError, match="source_ledger_does_not_match"):
        source.verify_ledger(path)


def test_changed_neutral_graph_rejected(tmp_path):
    altered = deepcopy(source.EXPECTED_LEDGER)
    altered["rows"][1]["proposed_neutral_graph"]["canonical_isomeric_smiles"] = (
        altered["rows"][2]["proposed_neutral_graph"]["canonical_isomeric_smiles"]
    )
    path = tmp_path / "graph-swapped-ledger.json"
    path.write_bytes(source.canonical_ledger_bytes(altered))
    with pytest.raises(ValueError, match="source_ledger_does_not_match"):
        source.verify_ledger(path)


@pytest.mark.parametrize("section,field,replacement", [
    ("authority", "training_admitted", 0),
    ("proposed_neutral_graph", "fragment_count", True),
])
def test_equal_python_values_with_different_json_types_are_rejected(
    tmp_path, section, field, replacement,
):
    altered = deepcopy(source.EXPECTED_LEDGER)
    target = (altered["authority"] if section == "authority"
              else altered["rows"][0]["proposed_neutral_graph"])
    target[field] = replacement
    path = tmp_path / "type-substituted-ledger.json"
    path.write_bytes(source.canonical_ledger_bytes(altered))
    with pytest.raises(ValueError, match="source_ledger_does_not_match"):
        source.verify_ledger(path)


def test_resealed_threshold_class_still_fails_semantic_check(tmp_path, monkeypatch):
    altered = deepcopy(source.EXPECTED_LEDGER)
    altered["rows"][1]["threshold_derived_class_across_one_sd"] = "active"
    path = tmp_path / "wrong-class-ledger.json"
    path.write_bytes(source.canonical_ledger_bytes(altered))
    monkeypatch.setattr(source, "EXPECTED_LEDGER", altered)
    with pytest.raises(ValueError, match="threshold_projection_mismatch"):
        source.verify_ledger(path)


def test_pdf_hash_binding_rejects_tamper_without_external_file(tmp_path, monkeypatch):
    pdf = tmp_path / "synthetic.pdf"
    pdf.write_bytes(b"%PDF-1.7\nsynthetic source bytes\n")
    expected_hash = hashlib.sha256(pdf.read_bytes()).hexdigest()
    altered = deepcopy(source.EXPECTED_LEDGER)
    altered["source"]["pdf_sha256"] = expected_hash
    ledger = tmp_path / "synthetic-ledger.json"
    ledger.write_bytes(source.canonical_ledger_bytes(altered))
    monkeypatch.setattr(source, "PDF_SHA256", expected_hash)
    monkeypatch.setattr(source, "EXPECTED_LEDGER", altered)
    receipt = source.verify_source(pdf, ledger)
    assert receipt["pdf_hash_matched"] and receipt["ledger_exact_match"]
    assert not receipt["source_authenticated"]
    assert not receipt["roles_assigned"]
    assert not receipt["protected_outcomes_read"]
    pdf.write_bytes(pdf.read_bytes() + b"tampered")
    with pytest.raises(ValueError, match="primary_pdf_sha256_mismatch"):
        source.verify_source(pdf, ledger)


def test_official_local_pdf_exact_receipt_when_supplied():
    receipt = source.verify_source(_official_pdf(), LEDGER)
    assert receipt["pdf_sha256"] == source.PDF_SHA256
    assert receipt["paper_row_ids"] == ["PR49", "PR58", "PR59"]
    assert not receipt["source_authenticated"]
    assert not receipt["training_admitted"]
    assert not receipt["scientifically_validated"]


def test_tampered_official_pdf_rejected_when_supplied(tmp_path):
    raw = bytearray(_official_pdf().read_bytes())
    raw[-1] ^= 1
    path = tmp_path / "tampered-official.pdf"
    path.write_bytes(raw)
    with pytest.raises(ValueError, match="primary_pdf_sha256_mismatch"):
        source.verify_source(path, LEDGER)

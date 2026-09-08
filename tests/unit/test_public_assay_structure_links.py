"""Invented identity metadata only; no actual assay, coordinates or fitting."""
from __future__ import annotations

import copy

import pytest

from tools.product import public_assay_dataset as assay
from tools.product import public_assay_structure_links as links
from tools.product.residual_evidence import source_provenance_json

SMILES = "CC[C@H](C)N"


def _save(path, value, *, jsonl=False):
    text = "\n".join(assay.json_text(row) for row in value) + "\n" if jsonl else assay.json_text(value)
    path.write_text(text)
    return {"path": str(path), "sha256": assay.file_sha(path)}


def _raw(**updates):
    row = {"BindingDB Reactant_set_id": "synthetic_1", "BindingDB MonomerID": "synthetic_amine",
           "Ligand SMILES": SMILES, "Curation/DataSource": "BindingDB",
           "Target Name": "synthetic_target", assay.CHAIN_COUNT: "1",
           "UniProt (SwissProt) Primary ID of Target Chain 1": "P12345",
           "BindingDB Target Chain Sequence 1": "ACDEFG", "Article DOI": "synthetic:example",
           "Date of publication": "2000-01-01", "IC50 (nM)": "17",
           "Ligand HET ID in PDB": "TST", "PDB ID(s) for Ligand-Target Complex": "1ABC",
           "role": "fit", "split": "development", "evaluation_only": "false"}
    row.update(updates)
    return row


def _normalized(raw):
    return assay.normalize_record(
        raw, identity=assay.chemical_identity(raw["Ligand SMILES"]),
        assays=[{"mapping_source": {"row": {"role": "development_source"}, "source_sha256": "b" * 64},
                 "description_records": [{"row": {"role": "development_source"}, "source_sha256": "c" * 64}]}],
        origin={"source_sha256": "a" * 64, "source_line": 2, "source_member": "synthetic.tsv"},
    )


@pytest.fixture
def documents(tmp_path):
    row = _normalized(_raw())
    entry = {"rcsb_id": "1ABC", "rcsb_entry_container_identifiers": {
        "entry_id": "1ABC", "polymer_entity_ids": ["1"], "non_polymer_entity_ids": ["2"]}}
    polymer = {"rcsb_id": "1ABC_1", "rcsb_polymer_entity_container_identifiers": {
        "entry_id": "1ABC", "entity_id": "1", "uniprot_ids": ["P12345"]}}
    nonpolymer = {"rcsb_id": "1ABC_2", "rcsb_nonpolymer_entity_container_identifiers": {
        "entry_id": "1ABC", "entity_id": "2", "nonpolymer_comp_id": "TST"},
        "pdbx_entity_nonpoly": {"entity_id": "2", "comp_id": "TST"}}
    component = {"rcsb_id": "TST", "chem_comp": {"id": "TST"},
                 "rcsb_chem_comp_descriptor": {"comp_id": "TST", "SMILES_stereo": SMILES}}
    return tmp_path, row, entry, polymer, nonpolymer, component


def _request(documents):
    path, row, entry, polymer, nonpolymer, component = documents
    refs = {key: _save(path / (key + ".json"), value) for key, value in
            [("entry", entry), ("polymer", polymer), ("nonpolymer", nonpolymer), ("component", component)]}
    return {"records": _save(path / "records.jsonl", [row], jsonl=True), "edges": [{
        "record_id": row["record_id"], "pdb_id": "1ABC", "entry": refs["entry"],
        "polymers": [refs["polymer"]], "nonpolymers": [refs["nonpolymer"]],
        "components": [refs["component"]]}]}


def _edge(request):
    result = links.build_identity_links(**request)
    assert result["requested_edges"] == len(result["edges"]) == 1
    return result["edges"][0]


def _refresh_raw(row, **updates):
    row["source_provenance"]["row"].update(updates)
    row["source_provenance"]["row_sha256"] = assay.digest(assay.json_text(row["source_provenance"]["row"]))


def test_exact_target_and_bound_isomeric_identity_is_only_a_link(documents):
    request = _request(documents)
    result = links.build_identity_links(**request)
    observed = result["edges"][0]
    assert observed["status"] == "identity_link_only"
    assert observed["target"]["matching_entity_ids"] == ["1"]
    assert observed["ligand"]["matching_ccd_ids"] == ["TST"]
    assert observed["source"]["external_split"] is None
    assert observed["source"]["original_row_sha256"] == documents[1]["source_provenance"]["row_sha256"]
    assert observed["source"]["declarations"][1]["values"]["role"] == "fit"
    for key in ["training_admitted", "assay_construct_match_verified", "coordinates_validated",
                "charges_or_forcefield_parameters_validated", "scientifically_validated", "numeric_assay_labels_projected"]:
        assert result[key] is False
    def names(value):
        if isinstance(value, dict):
            yield from value
            for item in value.values():
                yield from names(item)
        elif isinstance(value, list):
            for item in value:
                yield from names(item)
    assert not ({"IC50 (nM)", "observations", "negative_log10_molar", "value", "coordinates", "force_labels"} & set(names(result)))


def test_exact_ligand_in_wrong_protein_is_rejected(documents):
    documents[3]["rcsb_polymer_entity_container_identifiers"]["uniprot_ids"] = ["Q99999"]
    observed = _edge(_request(documents))
    assert observed["target"]["reason"] == "target_uniprot_mismatch"
    assert observed["ligand"]["status"] == "matched"
    assert observed["status"] == "rejected"


@pytest.mark.parametrize("smiles", ["CC[C@@H](C)N", "CCC(C)N", "CC[C@H](C)[NH3+]", "CC[C@H](C)O"])
def test_stereo_protonation_and_composition_are_not_inferred(documents, smiles):
    documents[5]["rcsb_chem_comp_descriptor"]["SMILES_stereo"] = smiles
    observed = _edge(_request(documents))
    assert observed["status"] == "rejected"
    assert observed["ligand"]["reason"] == "ccd_isomeric_chemistry_mismatch"


@pytest.mark.parametrize("missing", ["entry", "polymers", "nonpolymers", "components"])
def test_missing_metadata_never_passes(documents, missing):
    request = _request(documents)
    request["edges"][0][missing] = None if missing == "entry" else []
    assert _edge(request)["status"] == "unknown"


def test_matching_ccd_not_bound_to_entry_is_rejected(documents):
    documents[4]["rcsb_nonpolymer_entity_container_identifiers"]["nonpolymer_comp_id"] = "OTHER"
    documents[4]["pdbx_entity_nonpoly"]["comp_id"] = "OTHER"
    observed = _edge(_request(documents))
    assert observed["ligand"]["reason"] == "declared_ccd_absent_from_entry"


def test_multiple_exact_bound_ccd_ids_are_ambiguous(documents):
    _refresh_raw(documents[1], **{"Ligand HET ID in PDB": "TST TWO"})
    documents[2]["rcsb_entry_container_identifiers"]["non_polymer_entity_ids"].append("3")
    request = _request(documents)
    nonpolymer = copy.deepcopy(documents[4])
    nonpolymer["rcsb_id"] = "1ABC_3"
    nonpolymer["rcsb_nonpolymer_entity_container_identifiers"].update(entity_id="3", nonpolymer_comp_id="TWO")
    nonpolymer["pdbx_entity_nonpoly"].update(entity_id="3", comp_id="TWO")
    component = {"rcsb_id": "TWO", "chem_comp": {"id": "TWO"},
                 "rcsb_chem_comp_descriptor": {"comp_id": "TWO", "SMILES_stereo": SMILES}}
    request["edges"][0]["nonpolymers"].append(_save(documents[0] / "second-nonpolymer.json", nonpolymer))
    request["edges"][0]["components"].append(_save(documents[0] / "second-component.json", component))
    assert _edge(request)["ligand"]["reason"] == "ambiguous_multiple_exact_ccd_matches"


@pytest.mark.parametrize("mode", ["unmapped", "chimeric", "conflicting", "incomplete"])
def test_target_mapping_unknown_is_not_inferred_from_names(documents, mode):
    ids = documents[3]["rcsb_polymer_entity_container_identifiers"]
    if mode == "unmapped":
        ids["uniprot_ids"] = []
        documents[3]["description"] = "synthetic_target P12345"
    elif mode == "chimeric":
        ids["uniprot_ids"] = ["P12345", "Q99999"]
    elif mode == "conflicting":
        documents[3]["rcsb_polymer_entity_align"] = [{"reference_database_name": "UniProt", "reference_database_accession": "Q99999"}]
    else:
        documents[2]["rcsb_entry_container_identifiers"]["polymer_entity_ids"].append("3")
    assert _edge(_request(documents))["status"] in {"unknown", "failed"}


@pytest.mark.parametrize("source", ["entry", "polymer", "nonpolymer", "component"])
def test_hash_mismatch_and_wrong_entity_bindings_fail(documents, source):
    request = _request(documents)
    (documents[0] / (source + ".json")).write_text("{}")
    observed = _edge(request)
    assert observed["status"] == "failed" and "sha256_mismatch" in observed["reason"]


@pytest.mark.parametrize("index,key,value", [
    (2, "rcsb_id", "2ABC"), (3, "rcsb_id", "2ABC_1"),
    (4, "rcsb_id", "1ABC_9"), (5, "rcsb_id", "OTHER"),
])
def test_self_consistent_file_hash_is_not_entity_identity(documents, index, key, value):
    documents[index][key] = value
    assert _edge(_request(documents))["status"] == "failed"


def test_source_hash_mismatch_is_request_failure(documents):
    request = _request(documents)
    request["records"]["sha256"] = "0" * 64
    with pytest.raises(ValueError, match="sha256_mismatch"):
        links.build_identity_links(**request)


@pytest.mark.parametrize("mode", ["row_hash", "chemical_hash", "target_hash", "source_schema"])
def test_inconsistent_normalized_original_binding_rejected(documents, mode):
    row = documents[1]
    if mode == "row_hash":
        row["source_provenance"]["row"]["role"] = "changed_without_hash"
    elif mode == "chemical_hash":
        row["chemical_identity"]["canonical_isomeric_smiles_sha256"] = "0" * 64
    elif mode == "target_hash":
        row["target_accessions"] = ["Q99999"]
    else:
        row["schema_version"] = "unrelated"
    assert _edge(_request(documents))["status"] in {"failed", "rejected"}


@pytest.mark.parametrize("mode", ["edge", "source", "missing_source"])
def test_duplicate_or_missing_inputs_remain_in_denominator(documents, mode):
    request = _request(documents)
    if mode == "edge":
        request["edges"].append(copy.deepcopy(request["edges"][0]))
    elif mode == "source":
        request["records"] = _save(documents[0] / "duplicate.jsonl", [documents[1], documents[1]], jsonl=True)
    else:
        request["edges"][0]["record_id"] = "bindingdb:missing"
    result = links.build_identity_links(**request)
    assert len(result["edges"]) == result["requested_edges"] == len(request["edges"])
    assert all(row["status"] == "rejected" for row in result["edges"])


@pytest.mark.parametrize("carrier", ["raw", "normalized", "assay", "flattened", "split"])
def test_all_original_evaluation_declarations_survive_and_exclude(documents, carrier):
    row = documents[1]
    if carrier == "raw":
        _refresh_raw(row, role="far_ood_eval")
    elif carrier == "normalized":
        row["evaluation_only"] = True
    elif carrier == "assay":
        row["assays"][0]["mapping_source"]["row"]["role"] = "validation"
    elif carrier == "flattened":
        row["source_provenance_json"] = source_provenance_json(
            {"role": "test"}, source_csv="synthetic.csv", source_sha256="d" * 64, source_line=2)
    request = _request(documents)
    if carrier == "split":
        request["split_assignments"] = _save(documents[0] / "split.json", {
            "records_sha256": request["records"]["sha256"],
            "assignments": [{"record_id": row["record_id"], "split": "test"}]})
    observed = _edge(request)
    assert observed["status"] == "excluded"
    assert observed["source"]["evaluation_only_declared"] is True
    assert observed["target"]["status"] == "not_evaluated"


@pytest.mark.parametrize("split", ["fit", "calibration", "development", None])
def test_external_development_splits_are_preserved_without_fit_promotion(documents, split):
    request = _request(documents)
    assignment = {"record_id": documents[1]["record_id"], "split": split, "group": "synthetic_group"}
    request["split_assignments"] = _save(documents[0] / "split.json", {
        "records_sha256": request["records"]["sha256"], "assignments": [] if split is None else [assignment]})
    result = links.build_identity_links(**request)
    observed = result["edges"][0]
    assert observed["status"] == "identity_link_only"
    assert observed["source"]["external_split"] == (None if split is None else assignment)
    assert result["training_admitted"] is False


def test_split_rebound_to_other_normalized_pool_rejected(documents):
    request = _request(documents)
    request["split_assignments"] = _save(documents[0] / "split.json", {"records_sha256": "0" * 64, "assignments": []})
    with pytest.raises(ValueError, match="split_records_source_mismatch"):
        links.build_identity_links(**request)


def test_no_smiles_fallback_when_isomeric_descriptor_absent(documents):
    documents[5]["rcsb_chem_comp_descriptor"] = {"comp_id": "TST", "SMILES": SMILES}
    assert _edge(_request(documents))["ligand"]["reason"] == "ccd_isomeric_descriptor_missing"


def test_unlisted_pdb_edge_not_fabricated(documents):
    _refresh_raw(documents[1], **{"PDB ID(s) for Ligand-Target Complex": "2ABC"})
    assert _edge(_request(documents))["reason"] == "pdb_edge_not_declared_by_source"


def test_postflight_detects_source_mutation(documents, monkeypatch):
    request = _request(documents)
    original = links._ligand
    def mutate(*args, **kwargs):
        result = original(*args, **kwargs)
        (documents[0] / "records.jsonl").write_text("{}\n")
        return result
    monkeypatch.setattr(links, "_ligand", mutate)
    with pytest.raises(ValueError, match="sha256_mismatch"):
        links.build_identity_links(**request)


def test_duplicate_json_keys_are_not_last_write_wins(documents):
    request = _request(documents)
    path = documents[0] / "entry.json"
    path.write_text('{"rcsb_id":"2ABC","rcsb_id":"1ABC"}')
    request["edges"][0]["entry"]["sha256"] = assay.file_sha(path)
    assert _edge(request)["reason"] == "duplicate_json_key"


@pytest.mark.parametrize("where", ["reference", "role", "issues", "member", "split_group"])
def test_malformed_containers_do_not_project_numeric_labels(documents, where):
    hidden = {"IC50": 17, "observations": [{"value": 17}]}
    if where == "role":
        documents[1]["role"] = hidden
    elif where == "issues":
        documents[1]["admission_issues"] = [hidden]
    elif where == "member":
        documents[1]["source_provenance"]["source_member"] = hidden
    request = _request(documents)
    if where == "reference":
        request["edges"][0]["entry"]["observations"] = hidden
        with pytest.raises(ValueError, match="invalid_local_source_binding"):
            links.build_identity_links(**request)
        return
    if where == "split_group":
        request["split_assignments"] = _save(documents[0] / "split.json", {
            "records_sha256": request["records"]["sha256"], "assignments": [{
                "record_id": documents[1]["record_id"], "split": "fit", "group": hidden}]})
    result = links.build_identity_links(**request)
    assert result["edges"][0]["status"] == "failed"
    assert '"IC50"' not in assay.json_text(result)
    assert '"observations"' not in assay.json_text(result)


@pytest.mark.parametrize("field", ["target_state_sha256", "target_state", "ligand_id", "record_id"])
def test_every_normalized_identity_is_bound_to_its_original_source(documents, field):
    row = documents[1]
    row[field] = {"wrong": "state"} if field == "target_state" else "0" * 64
    observed = _edge(_request(documents))
    assert observed["status"] == "failed"


def test_conflicting_nonpolymer_entity_alias_is_rejected(documents):
    documents[4]["pdbx_entity_nonpoly"]["entity_id"] = "9"
    assert _edge(_request(documents))["reason"] == "nonpolymer_component_identity_mismatch"


def test_postflight_rechecks_declared_symlink_path(documents, monkeypatch):
    request = _request(documents)
    original_path = documents[0] / "entry.json"
    alias = documents[0] / "alias.json"
    alias.symlink_to(original_path)
    request["edges"][0]["entry"]["path"] = str(alias)
    other = documents[0] / "other.json"
    other.write_bytes(original_path.read_bytes())
    original = links._ligand
    def mutate(*args, **kwargs):
        result = original(*args, **kwargs)
        alias.unlink()
        alias.symlink_to(other)
        return result
    monkeypatch.setattr(links, "_ligand", mutate)
    with pytest.raises(ValueError, match="source_path_resolution_changed"):
        links.build_identity_links(**request)

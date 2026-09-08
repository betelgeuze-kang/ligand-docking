"""New synthetic assay controls; no protected outcomes or network calls."""

from __future__ import annotations

import json

import pytest

from tools.product import public_assay_dataset as mod
from tools.product.build_public_assay_development_dataset import main
from tools.product.residual_evidence import score_reference_rejection


def source_row(**updates):
    row = {
        "BindingDB Reactant_set_id": "001",
        "BindingDB MonomerID": "NA",
        "Ligand SMILES": "CC[C@H](O)c1ccccc1",
        "Ligand InChI Key": "",
        "Curation/DataSource": "Curated from the literature by BindingDB",
        "Target Name": "synthetic_target",
        "Target Source Organism According to Curator or DataSource": "synthetic",
        mod.CHAIN_COUNT: "1",
        "UniProt (SwissProt) Primary ID of Target Chain 1": "SYNTHETIC",
        "BindingDB Target Chain Sequence 1": "ACDEFG",
        "Article DOI": "synthetic:no-paper",
        "PMID": "",
        "Date of publication": "2020-01-01",
        "Date in BindingDB": "2021-01-01",
        "pH": "0",
        "Temp (C)": "0",
        "Ki (nM)": "10",
        "Kd (nM)": "",
        "IC50 (nM)": "",
        "EC50 (nM)": "",
        "Ligand HET ID in PDB": "",
        "PDB ID(s) for Ligand-Target Complex": "",
        "role": "development_source",
        "split": "",
        "dataset_split": "",
        "evaluation_only": "false",
    }
    row.update(updates)
    return row


def exclusions(**updates):
    return {
        "complete": True,
        "excluded_pdb_ids": [],
        "excluded_ccd_ids": [],
        "excluded_ligand_inchikeys": [],
        "excluded_canonical_isomeric_smiles_sha256": [],
        **updates,
    }


def write_tsv(path, rows):
    header = list(rows[0])
    path.write_text(
        "\t".join(header)
        + "\n"
        + "".join("\t".join(row[k] for k in header) + "\n" for row in rows)
    )
    return path


def inputs(tmp_path, rows=None, policy=None):
    rows = rows or [source_row()]
    source = write_tsv(tmp_path / "source.tsv", rows)
    mapping = write_tsv(
        tmp_path / "mapping.tsv",
        [
            {
                "REACTANT_SET_ID": row["BindingDB Reactant_set_id"],
                "ENTRYID_ASSAYID": "001_01",
            }
            for row in rows
        ],
    )
    assay = write_tsv(
        tmp_path / "assay.tsv",
        [
            {
                "ENTRYID": "001",
                "ASSAYID": "01",
                "ASSAY_NAME": "synthetic",
                "DESCRIPTION": "synthetic binding measurement",
            }
        ],
    )
    return dict(
        source_path=source,
        source_sha256=mod.file_sha(source),
        source_url="https://example.test/synthetic.tsv",
        release="synthetic_v1",
        mapping_path=mapping,
        mapping_sha256=mod.file_sha(mapping),
        assay_path=assay,
        assay_sha256=mod.file_sha(assay),
        exclusions=policy or exclusions(),
        targets={"SYNTHETIC"},
    )


def test_stereo_and_formal_state_survive_canonicalization():
    left = mod.chemical_identity("CC[C@H](O)c1ccccc1")
    right = mod.chemical_identity("CC[C@@H](O)c1ccccc1")
    assert (
        left["canonical_isomeric_smiles_sha256"]
        != right["canonical_isomeric_smiles_sha256"]
    )
    assert left["connectivity_smiles_sha256"] == right["connectivity_smiles_sha256"]
    assert mod.chemical_identity("C[NH3+]")["formal_charge"] == 1
    assert mod.chemical_identity("C[NH3+].[Cl-]")["fragment_count"] == 2


@pytest.mark.parametrize(
    "raw,status,value,relation",
    [
        ("0", "nonpositive_or_nonfinite_assay_concentration", 0, None),
        ("", "missing", None, None),
        (">1000", "censored", 1000, "<"),
        ("<=10", "censored", 10, ">="),
        ("1e9", "exact", 1e9, "="),
        ("NaN", "invalid_numeric_or_relation", None, None),
        ("inf", "invalid_numeric_or_relation", None, None),
        ("1e999", "nonpositive_or_nonfinite_assay_concentration", None, None),
        ("~12", "approximate", 12, "~"),
    ],
)
def test_concentrations_keep_zero_missing_censoring_distinct(
    raw, status, value, relation
):
    result = mod.measurement(raw, "Ki")
    assert (
        result["status"] == status
        and result["value_nm"] == value
        and result["log_relation"] == relation
    )
    if raw == "1e9":
        assert result["negative_log10_molar"] == 0


def test_real_module_preserves_source_and_never_makes_energy_force_labels(tmp_path):
    rows, ledger, summary = mod.build_dataset(**inputs(tmp_path))
    row = rows[0]
    assert row["source_provenance"]["row"] == source_row()
    assert row["record_id"] == "bindingdb:001" and row["ligand_id"] == "bindingdb:NA"
    assert row["assay_conditions"] == {"pH_source": "0", "temperature_c_source": "0"}
    assert row["observations"][0]["negative_log10_molar"] == 8
    assert (
        row["potential_energy"] is None
        and row["force_labels"] is None
        and row["coordinates"] is None
    )
    assert row["eligible_for_split_assignment"] and not row["training_admitted"]
    assert (
        summary["requested_target_rows"]
        == summary["normalized_rows"]
        == len(ledger)
        == 1
    )
    assert score_reference_rejection(row) == "incompatible_score_reference_semantics"


@pytest.mark.parametrize(
    "field,value",
    [
        ("role", "holdout"),
        ("split", "test"),
        ("dataset_split", "far_ood_eval"),
        ("evaluation_only", "true"),
    ],
)
def test_every_original_eval_declaration_excluded_before_label_projection(
    tmp_path, field, value
):
    rows, ledger, summary = mod.build_dataset(
        **inputs(tmp_path, [source_row(**{field: value})])
    )
    assert not rows and summary["requested_target_rows"] == 1
    assert ledger[0]["reason"] == "source_declares_evaluation_only"
    assert "source_provenance" not in ledger[0] and "observations" not in ledger[0]


def test_duplicate_id_excludes_all_instead_of_selecting_largest_or_last(tmp_path):
    rows, ledger, summary = mod.build_dataset(
        **inputs(tmp_path, [source_row(), source_row(**{"Ki (nM)": "900"})])
    )
    assert not rows and len(ledger) == 2
    assert summary["exclusion_counts"] == {
        "duplicate_record_id_all_occurrences_excluded": 2
    }


def test_duplicate_on_other_target_cannot_evade_source_wide_check(tmp_path):
    other = source_row(
        **{"UniProt (SwissProt) Primary ID of Target Chain 1": "OTHER", "role": "test"}
    )
    rows, ledger, summary = mod.build_dataset(**inputs(tmp_path, [source_row(), other]))
    assert not rows and summary["requested_target_rows"] == 1
    assert ledger[0]["reason"] == "duplicate_record_id_all_occurrences_excluded"


def test_inactive_chain_does_not_select_wrong_requested_target():
    row = source_row(
        **{
            "UniProt (SwissProt) Primary ID of Target Chain 1": "OTHER",
            "UniProt (SwissProt) Primary ID of Target Chain 2": "SYNTHETIC",
        }
    )
    assert mod.target_accessions(row) == {"OTHER"}
    assert mod.target_schema_rejection(row) == "nonempty_undeclared_target_chain"


def test_pdb_cross_reference_update_does_not_change_protein_state_hash(tmp_path):
    row = source_row(**{"PDB ID(s) of Target Chain 1": "AAAA"})
    args = inputs(tmp_path, [row])
    normalized, _, _ = mod.build_dataset(**args)
    changed = source_row(**{"PDB ID(s) of Target Chain 1": "BBBB"})
    args = inputs(tmp_path, [changed])
    updated, _, _ = mod.build_dataset(**args)
    assert normalized[0]["target_state_sha256"] == updated[0]["target_state_sha256"]
    assert (
        normalized[0]["source_provenance"]["row"]
        != updated[0]["source_provenance"]["row"]
    )


@pytest.mark.parametrize("source", ["mapping", "assay"])
def test_joined_eval_role_cannot_be_erased(tmp_path, source):
    args = inputs(tmp_path)
    path = args[source + "_path"]
    lines = path.read_text().splitlines()
    path.write_text(
        lines[0] + "\trole\n" + "\n".join(line + "\ttest" for line in lines[1:]) + "\n"
    )
    args[source + "_sha256"] = mod.file_sha(path)
    rows, ledger, summary = mod.build_dataset(**args)
    assert not rows and ledger[0]["reason"] == "evaluation_only_join_source"
    assert summary["excluded_before_observation_projection"] == 1


def test_stereo_independent_exclusion_field_is_consumed(tmp_path):
    identity = mod.chemical_identity(source_row()["Ligand SMILES"])
    policy = exclusions(
        excluded_stereo_independent_smiles_sha256=[
            identity["connectivity_smiles_sha256"]
        ]
    )
    rows, ledger, _ = mod.build_dataset(**inputs(tmp_path, policy=policy))
    assert not rows and ledger[0]["reason"] == "protected_ligand_connectivity"


def test_canonicalizer_mismatch_fails_before_data_use(tmp_path):
    policy = exclusions(
        identity_exclusion_complete=True,
        identity_exclusion_scope="synthetic exact identities",
        normalization={"version": "wrong"},
    )
    with pytest.raises(ValueError, match="canonicalizer_version_mismatch"):
        mod.build_dataset(**inputs(tmp_path, policy=policy))


def test_source_change_during_assay_join_invalidates_bundle(tmp_path, monkeypatch):
    args = inputs(tmp_path)
    original = mod.assay_index

    def replacing(*values):
        result = original(*values)
        args["source_path"].write_text(
            args["source_path"].read_text().replace("\t10\t", "\t20\t")
        )
        return result

    monkeypatch.setattr(mod, "assay_index", replacing)
    with pytest.raises(ValueError, match="source_sha256_mismatch"):
        mod.build_dataset(**args)


@pytest.mark.parametrize(
    "field,key",
    [
        ("excluded_ccd_ids", "Ligand HET ID in PDB"),
        ("excluded_pdb_ids", "PDB ID(s) for Ligand-Target Complex"),
    ],
)
def test_structure_ids_excluded_without_emitting_measurements(tmp_path, field, key):
    rows, ledger, _ = mod.build_dataset(
        **inputs(tmp_path, [source_row(**{key: "AB1"})], exclusions(**{field: ["AB1"]}))
    )
    assert not rows and ledger[0]["reason"] == "protected_structure_or_ligand_id"


def test_cross_db_identity_exclusion_ignores_source_record_id(tmp_path):
    identity = mod.chemical_identity(source_row()["Ligand SMILES"])
    rows, ledger, _ = mod.build_dataset(
        **inputs(
            tmp_path,
            policy=exclusions(
                excluded_canonical_isomeric_smiles_sha256=[
                    identity["canonical_isomeric_smiles_sha256"]
                ]
            ),
        )
    )
    assert not rows and ledger[0]["reason"] == "protected_ligand_smiles"


def test_incomplete_identity_review_blocks_split_and_training(tmp_path):
    rows, _, summary = mod.build_dataset(
        **inputs(tmp_path, policy=exclusions(complete=False))
    )
    assert rows[0]["admission_issues"] == ["protected_identity_audit_incomplete"]
    assert (
        summary["eligible_for_split_assignment"] == 0
        and not rows[0]["training_admitted"]
    )


@pytest.mark.parametrize(
    "source,license,eligible",
    [("ChEMBL", "CC-BY-SA-3.0", True), ("unknown", None, False)],
)
def test_license_follows_each_original_record_not_archive_name(
    tmp_path, source, license, eligible
):
    rows, _, _ = mod.build_dataset(
        **inputs(tmp_path, [source_row(**{"Curation/DataSource": source})])
    )
    assert (
        rows[0]["source_license"] == license
        and rows[0]["eligible_for_split_assignment"] == eligible
    )


def test_each_endpoint_is_separate_and_censored_values_are_not_exact(tmp_path):
    rows, _, _ = mod.build_dataset(
        **inputs(tmp_path, [source_row(**{"Kd (nM)": "20", "IC50 (nM)": ">30"})])
    )
    observations = {item["endpoint"]: item for item in rows[0]["observations"]}
    assert observations["Ki"]["value_nm"] == 10 and observations["Kd"]["value_nm"] == 20
    assert (
        observations["IC50"]["status"] == "censored"
        and observations["EC50"]["status"] == "missing"
    )


def test_missing_assay_and_changed_source_fail_closed(tmp_path):
    args = inputs(tmp_path)
    args["mapping_path"].write_text("REACTANT_SET_ID\tENTRYID_ASSAYID\n999\t001_01\n")
    with pytest.raises(ValueError, match="source_sha256_mismatch"):
        mod.build_dataset(**args)
    args["mapping_sha256"] = mod.file_sha(args["mapping_path"])
    rows, _, _ = mod.build_dataset(**args)
    assert "missing_or_ambiguous_assay_join" in rows[0]["admission_issues"]


def test_duplicate_header_cannot_overwrite_policy(tmp_path):
    path = tmp_path / "bad.tsv"
    path.write_text("role\trole\nholdout\tfit\n")
    with pytest.raises(ValueError, match="duplicate_tsv_header"):
        list(mod.tsv_records(path))


def test_actual_cli_publishes_hash_bound_bundle_and_keeps_existing_output(tmp_path):
    args = inputs(tmp_path)
    policy = tmp_path / "exclusions.json"
    policy.write_text(json.dumps(args["exclusions"]))
    output = tmp_path / "result"
    argv = [
        "--source",
        str(args["source_path"]),
        "--source-sha256",
        args["source_sha256"],
        "--source-url",
        args["source_url"],
        "--release",
        args["release"],
        "--target",
        "SYNTHETIC",
        "--mapping",
        str(args["mapping_path"]),
        "--mapping-sha256",
        args["mapping_sha256"],
        "--assays",
        str(args["assay_path"]),
        "--assays-sha256",
        args["assay_sha256"],
        "--exclusions",
        str(policy),
        "--exclusions-sha256",
        mod.file_sha(policy),
        "--output-dir",
        str(output),
    ]
    assert main(argv) == 0
    summary = json.loads((output / "summary.json").read_text())
    assert summary["records_sha256"] == mod.file_sha(output / "records.jsonl")
    before = (output / "summary.json").read_bytes()
    with pytest.raises(ValueError, match="output_already_exists"):
        main(argv)
    assert (output / "summary.json").read_bytes() == before

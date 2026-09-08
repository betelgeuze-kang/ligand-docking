"""Synthetic learning and serialization controls, independent of public data."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from tools.product import public_assay_dataset as intake
from tools.product import train_public_assay_selector as mod


def rows():
    result = []
    for group in range(12):
        identity = intake.chemical_identity("C" * (group + 5))
        for repeat in range(5):
            result.append(
                {
                    "record_id": f"synthetic:{group:02d}:{repeat}",
                    "schema_version": intake.SCHEMA,
                    "evidence_kind": "experimental_label",
                    "target_state_sha256": "a" * 64,
                    "eligible_for_split_assignment": True,
                    "admission_issues": [],
                    "source_provenance": {
                        "row": {
                            "Article DOI": f"synthetic:doc-{group}",
                            "PMID": "",
                            "role": "development_source",
                        }
                    },
                    "chemical_identity": identity,
                    "assays": [{"entry_assay_id": str(group)}],
                    "observations": [
                        {
                            "endpoint": "IC50",
                            "status": "exact",
                            "negative_log10_molar": 5.0 + 0.1 * group + 0.02 * repeat,
                        }
                    ],
                }
            )
    return result


def test_label_blind_splits_have_no_document_scaffold_or_ligand_overlap():
    values = rows()
    split, group_ids = mod.split_components(values, 1)
    assert sorted(i for indices in split.values() for i in indices) == list(
        range(len(values))
    )
    groups = [{group_ids[i] for i in indices} for indices in split.values()]
    assert all(
        not a.intersection(b) for j, a in enumerate(groups) for b in groups[j + 1 :]
    )
    for value in values:
        value["observations"] = [{"endpoint": "IC50", "negative_log10_molar": -999.0}]
    assert mod.split_components(values, 1) == (split, group_ids)


def test_transitive_document_and_scaffold_links_stay_together():
    values = rows()
    values[5]["source_provenance"]["row"]["Article DOI"] = values[0][
        "source_provenance"
    ]["row"]["Article DOI"]
    values[10]["chemical_identity"] = values[5]["chemical_identity"]
    _, groups = mod.split_components(values, 1)
    assert groups[0] == groups[5] == groups[10]


def test_doi_url_and_pmid_aliases_cannot_cross_splits():
    values = rows()
    values[0]["source_provenance"]["row"].update(
        {"Article DOI": "https://doi.org/10.9999/ABC", "PMID": "00042"}
    )
    values[5]["source_provenance"]["row"].update(
        {"Article DOI": "doi:10.9999/abc", "PMID": ""}
    )
    values[10]["source_provenance"]["row"].update({"Article DOI": "", "PMID": "00042"})
    _, groups = mod.split_components(values, 1)
    assert groups[0] == groups[5] == groups[10]


def test_insufficient_independent_groups_do_not_fall_back_to_random_rows():
    values = rows()
    for value in values:
        value["source_provenance"]["row"]["Article DOI"] = "synthetic:one-document"
    with pytest.raises(ValueError, match="insufficient_independent"):
        mod.split_components(values, 1)


@pytest.mark.parametrize("alias", ["ligand_id", "inchikey"])
def test_ligand_aliases_connect_different_state_representations(alias):
    values = rows()
    if alias == "ligand_id":
        values[0]["ligand_id"] = values[5]["ligand_id"] = "bindingdb:synthetic_alias"
    else:
        values[0]["source_provenance"]["row"]["Ligand InChI Key"] = values[5][
            "chemical_identity"
        ]["rdkit_inchikey"]
    _, groups = mod.split_components(values, 1)
    assert groups[0] == groups[5]


def test_unique_state_budget_does_not_count_repeated_measurements_twice():
    values = rows()[:5]
    report = mod.unique_state_metrics(
        values, np.array([7.0, 7.0, 7.0, 7.0, 7.0]), np.array([6.0] * 5), 6.0
    )
    assert report["requested"] == report["top_budget"] == report["positive_count"] == 1
    assert report["raw_measurement_count"] == 5


def test_censored_and_eval_rows_remain_in_request_denominator():
    values = rows()
    values[0]["observations"][0]["status"] = "censored"
    values[1]["source_provenance"]["row"]["role"] = "test"
    accepted, ledger = mod.cohort(values, "a" * 64, "IC50")
    assert len(accepted) == 58 and len(ledger) == 60
    assert ledger[0]["reason"] == "endpoint_not_exact_observation"
    assert ledger[1]["reason"] == "evaluation_only_source"


def test_input_ids_and_source_roles_are_not_features():
    values = rows()
    x = mod.features(
        [row["chemical_identity"]["canonical_isomeric_smiles"] for row in values]
    )
    for row in values:
        row["record_id"] = "arbitrary-different-id"
        row["source_provenance"]["row"]["role"] = "arbitrary"
    assert np.array_equal(
        x,
        mod.features(
            [row["chemical_identity"]["canonical_isomeric_smiles"] for row in values]
        ),
    )


def test_tied_budget_metric_is_order_independent_and_does_not_inflate_mean_baseline():
    actual = np.array([7.0, 5.0, 5.0, 5.0, 5.0])
    scores = np.full(5, 6.0)
    metric = mod.metrics(actual, scores, 6.0)
    assert metric["recall_at_budget"] == 0.2
    assert mod.metrics(actual[::-1], scores, 6.0) == metric
    failed = mod.metrics(actual, np.array([np.nan, 5.0, 4.0, 3.0, 2.0]), 6.0)
    assert (
        failed["requested"] == 5 and failed["predicted"] == 4 and failed["failed"] == 1
    )
    assert failed["positive_count"] == 1 and failed["recall_at_budget"] == 0


def bundle(tmp_path):
    source = tmp_path / "input"
    source.mkdir()
    (source / "ledger.jsonl").write_text(
        "".join(
            intake.json_text(
                {
                    "record_id": row["record_id"],
                    "status": "normalized",
                    "reason": "",
                    "target_state_sha256": row["target_state_sha256"],
                }
            )
            + "\n"
            for row in rows()
        )
    )
    (source / "records.jsonl").write_text(
        "".join(intake.json_text(row) + "\n" for row in rows())
    )
    (source / "summary.json").write_text(
        json.dumps(
            {
                "records_sha256": intake.file_sha(source / "records.jsonl"),
                "ledger_sha256": intake.file_sha(source / "ledger.jsonl"),
                "implementation_sha256": intake.file_sha(Path(intake.__file__)),
                "requested_target_rows": 60,
            }
        )
    )
    return source


def test_real_fit_saved_checkpoint_and_separate_loader_match(tmp_path):
    source = bundle(tmp_path)
    report = mod.run(
        input_dir=source,
        summary_sha256=intake.file_sha(source / "summary.json"),
        target_state="a" * 64,
        endpoint="IC50",
        output_dir=tmp_path / "trained",
    )
    assert report["training_executed"] and report["model_endpoint_rows"] == 60
    assert sum(report["split_counts"].values()) == 60
    assert (
        not report["docking_recall_measured"] and not report["engine_speedup_measured"]
    )
    model = json.loads((tmp_path / "trained/selector.json").read_text())
    assert np.any(np.asarray(model["coefficients"]) != 0)
    assert model["training_protocol_sha256"] == intake.file_sha(
        tmp_path / "trained/protocol-before-fit.json"
    )
    for split in report["evaluations"].values():
        assert split["morgan_ridge"]["failed"] == 0
    with pytest.raises(ValueError, match="selector_target_or_featurizer_mismatch"):
        mod.predict_checkpoint(
            tmp_path / "trained/selector.json",
            report["checkpoint_sha256"],
            ["CCCCCC"],
            "b" * 64,
            "IC50",
        )
    with pytest.raises(ValueError, match="sha256_mismatch"):
        mod.predict_checkpoint(
            tmp_path / "trained/selector.json", "b" * 64, ["CCCCCC"], "a" * 64, "IC50"
        )
    with pytest.raises(ValueError, match="endpoint_or_quantity_mismatch"):
        mod.predict_checkpoint(
            tmp_path / "trained/selector.json",
            report["checkpoint_sha256"],
            ["CCCCCC"],
            "a" * 64,
            "Ki",
        )


def test_changed_intake_never_creates_model(tmp_path):
    source = bundle(tmp_path)
    (source / "records.jsonl").write_text("[]\n")
    with pytest.raises(ValueError, match="sha256_mismatch"):
        mod.run(
            input_dir=source,
            summary_sha256=intake.file_sha(source / "summary.json"),
            target_state="a" * 64,
            endpoint="IC50",
            output_dir=tmp_path / "trained",
        )
    assert not (tmp_path / "trained").exists()


def test_rejections_before_normalization_stay_in_model_request_denominator(tmp_path):
    source = bundle(tmp_path)
    with (source / "ledger.jsonl").open("a") as fh:
        fh.write(
            intake.json_text(
                {
                    "record_id": "synthetic:rejected",
                    "status": "excluded",
                    "reason": "invalid_smiles",
                    "target_state_sha256": "a" * 64,
                }
            )
            + "\n"
        )
    summary = json.loads((source / "summary.json").read_text())
    summary["ledger_sha256"] = intake.file_sha(source / "ledger.jsonl")
    summary["requested_target_rows"] = 61
    (source / "summary.json").write_text(json.dumps(summary))
    report = mod.run(
        input_dir=source,
        summary_sha256=intake.file_sha(source / "summary.json"),
        target_state="a" * 64,
        endpoint="IC50",
        output_dir=tmp_path / "trained",
    )
    assert (
        report["requested_model_state_rows"] == 61
        and report["normalized_model_state_rows"] == 60
    )
    assert (
        report["excluded_model_state_rows"] == 1
        and report["model_state_exact_endpoint_coverage"] == 60 / 61
    )

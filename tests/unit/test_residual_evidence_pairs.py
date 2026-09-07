"""Synthetic evidence ingestion, not a molecular benchmark or source audit."""
from __future__ import annotations

import csv
import copy
import hashlib
import json
from pathlib import Path

import pytest

from tools.product import build_residual_production_supervised_dataset as builder
from tools.product.residual_evidence import IDENTITY_FIELDS, PAIR_SCHEMA, paired_energy_fields


def _input():
    row = dict(target="synthetic_target", ligand_id="synthetic_ligand", pose_id="pose_1",
               role="fit", is_binder=1, reference_binding_kcal_mol=-9., binding_score_composite_v7=-7.)
    row.update({key: hashlib.sha256(key.encode()).hexdigest() for key in IDENTITY_FIELDS})
    common = {key: row[key] for key in ("target", "ligand_id", "pose_id", *IDENTITY_FIELDS)}
    common.update(status="observed", evidence_kind="synthetic", energy_kind="potential_energy", unit="kcal/mol")
    baseline = dict(common, value=-10., source_sha256="a" * 64, run_id="baseline_run", model_id="baseline_model")
    reference = dict(common, value=-12., source_sha256="b" * 64, run_id="reference_run", model_id="reference_model")
    pair = dict(schema_version=PAIR_SCHEMA, baseline=baseline, reference=reference)
    return row, pair


def _attach(row, pair):
    return dict(row, energy_pair_json=json.dumps(pair))


def _write(path, rows):
    keys = list(dict.fromkeys(key for row in rows for key in row))
    with path.open("w", encoding="utf-8", newline="") as out:
        writer = csv.DictWriter(out, fieldnames=keys)
        writer.writeheader()
        writer.writerows(rows)


def _build(path, rows):
    _write(path / "s_stage5_ranking_rows.csv", rows)
    return builder.build_residual_production_supervised_dataset(
        stage5_glob=str(path / "*stage5_ranking_rows.csv"), min_rows=1, min_targets=1,
    )


def test_residual_is_rederived_from_two_matched_observations():
    row, pair = _input()
    pair["delta_energy"] = 9999.  # Not a trusted input target.
    result = paired_energy_fields(_attach(row, pair))
    assert result["delta_energy"] == -2.
    assert result["baseline_potential_energy_kcal_mol"] == -10.
    assert result["reference_potential_energy_kcal_mol"] == -12.
    assert result["energy_pair_status"] == "declared_identity_matched"
    assert result["physical_energy_residual_validated"] is False
    assert result["energy_evidence_kind"] == "synthetic"


@pytest.mark.parametrize("key", ["target", "ligand_id", "pose_id", *IDENTITY_FIELDS])
@pytest.mark.parametrize("side", ["baseline", "reference"])
def test_different_coordinate_state_environment_or_case_is_not_joined(key, side):
    row, pair = _input()
    pair[side][key] = "c" * 64 if key in IDENTITY_FIELDS else "different"
    result = paired_energy_fields(_attach(row, pair))
    assert result["delta_energy"] == ""
    assert result["energy_pair_status"] == "rejected"
    assert key in result["energy_pair_rejection"]


@pytest.mark.parametrize("key", ["pose_id", *IDENTITY_FIELDS])
def test_missing_stage5_identity_is_not_guessed_from_pair(key):
    row, pair = _input()
    del row[key]
    assert paired_energy_fields(_attach(row, pair))["energy_pair_status"] == "rejected"


@pytest.mark.parametrize("key,value", [
    ("status", "predicted"), ("status", "not_run"), ("evidence_kind", "experimental"),
    ("evidence_kind", "ai_prediction"), ("unit", "kJ/mol"), ("energy_kind", "binding_energy"),
    ("source_sha256", ""), ("source_sha256", "not_a_hash"), ("run_id", ""), ("model_id", ""),
    ("value", True), ("value", "-12"), ("value", float("nan")), ("value", float("inf")),
])
def test_unmeasured_incompatible_or_malformed_observations_are_rejected(key, value):
    row, pair = _input()
    pair["reference"][key] = value
    result = paired_energy_fields(_attach(row, pair))
    assert result["energy_pair_status"] == "rejected"
    assert result["delta_energy"] == ""


def test_synthetic_and_computed_sources_cannot_be_mixed():
    row, pair = _input()
    pair["reference"]["evidence_kind"] = "computed"
    assert paired_energy_fields(_attach(row, pair))["energy_pair_rejection"] == "mixed_synthetic_and_computed_pair"


def test_computed_tag_does_not_grant_scientific_validation():
    row, pair = _input()
    for obs in (pair["baseline"], pair["reference"]):
        obs["evidence_kind"] = "computed"
    result = paired_energy_fields(_attach(row, pair))
    assert result["delta_energy"] == -2.
    assert result["physical_energy_residual_validated"] is False


@pytest.mark.parametrize("text", ["{", "[]", "{}", '{"schema_version":"x","schema_version":"y"}', '"text"'])
def test_bad_json_and_duplicate_keys_are_rejected(text):
    row, _ = _input()
    result = paired_energy_fields(dict(row, energy_pair_json=text))
    assert result["energy_pair_status"] == "rejected"


def test_true_zero_residual_is_kept():
    row, pair = _input()
    pair["reference"]["value"] = pair["baseline"]["value"]
    assert paired_energy_fields(_attach(row, pair))["delta_energy"] == 0.


def test_finite_terms_cannot_overflow_the_residual():
    row, pair = _input()
    pair["baseline"]["value"], pair["reference"]["value"] = -1e308, 1e308
    result = paired_energy_fields(_attach(row, pair))
    assert result["energy_pair_rejection"] == "nonfinite_energy_residual"


def test_pair_fingerprint_is_canonical_and_input_is_not_mutated():
    row, pair = _input()
    supplied = _attach(row, pair)
    before = copy.deepcopy(supplied)
    left = paired_energy_fields(supplied)
    right = paired_energy_fields(dict(row, energy_pair_json=json.dumps(pair, sort_keys=True, indent=2)))
    assert supplied == before
    assert left == right


@pytest.mark.parametrize("role", ["test", "holdout", "validation", "fresh-128", "blind"])
def test_explicit_evaluation_rows_are_not_materialized_for_training(tmp_path, role):
    row, pair = _input()
    row["role"] = role
    payload = _build(tmp_path, [_attach(row, pair)])
    assert payload["rows"] == []
    source = payload["sources"][0]
    assert source["scanned_rows"] == source["skipped_rows"] == 1
    assert source["rejections"][0]["reason"] == "evaluation_only_row"


def test_valid_and_rejected_energy_pairs_do_not_lose_score_rows(tmp_path):
    row, pair = _input()
    other = _attach(row, pair)
    other["coordinate_sha256"] = "d" * 64
    payload = _build(tmp_path, [_attach(row, pair), other])
    assert payload["summary"]["rows_emitted"] == 2
    assert payload["summary"]["delta_energy_label_rows"] == 1
    assert payload["summary"]["energy_pair_rejected_rows"] == 1
    assert payload["rows"][1]["delta_energy"] == ""
    assert payload["rows"][1]["energy_pair_rejection"]
    assert payload["summary"]["production_supervised_dataset_ready"] is False


def test_loose_proxy_join_never_creates_an_energy_residual(tmp_path):
    row, _ = _input()
    _write(tmp_path / "s_stage3_scores.csv", [dict(target=row["target"], ligand_id=row["ligand_id"], binding_energy_proxy=-123.)])
    payload = _build(tmp_path, [row])
    assert payload["rows"][0]["stage3_energy_proxy_value"] == -123.
    assert payload["rows"][0]["delta_energy"] == ""
    assert payload["rows"][0]["refine_tier_label"] == ""
    assert payload["rows"][0]["energy_pair_status"] == "not_supplied"
    assert payload["summary"]["delta_energy_label_rows"] == 0


@pytest.mark.parametrize("values", [[-1., -2.], [-2., -1.], [-1., -1.]])
def test_repeated_proxy_join_keys_are_not_resolved_by_last_row(tmp_path, values):
    row, _ = _input()
    _write(tmp_path / "s_stage3_scores.csv", [dict(target=row["target"], ligand_id=row["ligand_id"], binding_energy_proxy=v) for v in values])
    payload = _build(tmp_path, [row])
    assert payload["rows"][0]["stage3_energy_proxy_value"] == ""
    assert payload["sources"][0]["stage3_ambiguous_join_keys"] == 1


@pytest.mark.parametrize("key,value", [("is_binder", "1.7"), ("is_binder", "inf"),
                                      ("reference_binding_kcal_mol", "nan"), ("binding_score_composite_v7", "inf")])
def test_invalid_labels_are_skipped_with_source_line_accounting(tmp_path, key, value):
    row, _ = _input()
    row[key] = value
    payload = _build(tmp_path, [row])
    assert payload["rows"] == []
    assert payload["sources"][0]["rejections"][0]["source_line"] == 2
    assert payload["sources"][0]["skipped_rows"] == 1


def test_materialized_rows_bind_input_bytes_and_are_not_physical_score_labels(tmp_path):
    row, pair = _input()
    payload = _build(tmp_path, [_attach(row, pair)])
    digest = hashlib.sha256((tmp_path / "s_stage5_ranking_rows.csv").read_bytes()).hexdigest()
    assert payload["rows"][0]["source_sha256"] == digest
    assert payload["sources"][0]["source_sha256"] == digest
    assert payload["rows"][0]["score_residual_semantics"] == "legacy_reference_minus_composite_proxy_not_physical_energy"
    assert "role" not in payload["summary"]["feature_fields"]


def test_row_limit_reports_only_processed_rows(tmp_path):
    row, _ = _input()
    _write(tmp_path / "s_stage5_ranking_rows.csv", [row, row, row])
    payload = builder.build_residual_production_supervised_dataset(
        stage5_glob=str(tmp_path / "*stage5_ranking_rows.csv"), max_rows_per_source=1, min_rows=1, min_targets=1)
    source = payload["sources"][0]
    assert source["scanned_rows"] == source["emitted_rows"] + source["skipped_rows"] == 1
    assert source["stopped_at_row_limit"] is True


def test_cli_preserves_pair_label_and_source_metadata(tmp_path):
    row, pair = _input()
    _write(tmp_path / "s_stage5_ranking_rows.csv", [_attach(row, pair)])
    builder.main(["--stage5-glob", str(tmp_path / "*stage5_ranking_rows.csv"),
                  "--out-json", str(tmp_path / "out.json"), "--out-csv", str(tmp_path / "out.csv"),
                  "--out-md", str(tmp_path / "out.md"), "--min-rows", "1", "--min-targets", "1"])
    with (tmp_path / "out.csv").open() as fh:
        observed = list(csv.DictReader(fh))
    assert float(observed[0]["delta_energy"]) == -2.
    assert observed[0]["delta_energy_unit"] == "kcal/mol"
    assert len(observed[0]["energy_pair_sha256"]) == 64
    assert "not physical energy" in (tmp_path / "out.md").read_text()


def test_materialized_pairs_feed_real_candidate_training_without_promotion(tmp_path):
    from tools import train_residual_production_score_model as trainer
    from tools.builder_table_utils import write_csv_rows
    import torch

    rows = []
    for i in range(24):
        row, pair = _input()
        row.update(ligand_id=f"synthetic_ligand_{i}", is_binder=i % 2)
        for observation in (pair["baseline"], pair["reference"]):
            observation["ligand_id"] = row["ligand_id"]
        pair["reference"]["value"] = -12. + .1 * i
        rows.append(_attach(row, pair))
    payload = _build(tmp_path, rows)
    dataset = tmp_path / "paired_dataset.csv"
    write_csv_rows(dataset, payload["rows"])
    previous = torch.get_num_threads()
    try:
        torch.set_num_threads(1)
        result = trainer.train_residual_production_score_model(
            input_csv=str(dataset), out_checkpoint=str(tmp_path / "candidate.pt"),
            epochs=1, hidden_dim=8, batch_size=8, device_name="cpu",
        )
    finally:
        torch.set_num_threads(previous)
    assert result["training_executed"] is True
    assert result["delta_energy_train_label_rows"] > 10
    assert result["delta_energy_head_trained"] is True
    assert result["physical_energy_residual_validated"] is False
    assert result["delta_force_head_trained"] is False
    assert result["production_checkpoint_ready"] is False
    assert result["model_promoted"] is False

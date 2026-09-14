"""Synthetic P0 input contracts; no protected data or molecular computation."""
from __future__ import annotations

import csv
import json

import pytest

from tools.product import build_refine_tier_residual_training_dataset as refine
from tools.product import build_residual_production_supervised_dataset as base
from tools.product.residual_evidence import declared_evaluation_only


def _write(path, rows):
    fields = list(dict.fromkeys(key for row in rows for key in row))
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _input(**extra):
    return dict(target="synthetic_target", ligand_id="synthetic_ligand", role="fit",
                split="development", dataset_split="train", evaluation_only="false",
                pose_id="pose0", coordinate_sha256="a" * 64, atom_order_sha256="b" * 64,
                chemical_state_sha256="c" * 64, environment_sha256="d" * 64,
                raw_score=-3, delta_score=1, is_binder=1, **extra)


def _stage3(**extra):
    row = _input()
    row.update(binding_energy_mmpbsa_kcal_mol_proxy=-2,
               deltaG_mm_gbsa_kcal_mol=0,
               binding_energy_explicit_water_recheck_kcal_mol_proxy=99,
               physics_refinement_confidence=0,
               run_id="synthetic_run", evidence_kind="own_engine_observation")
    row.update(extra)
    return row


def _enrich(tmp_path, stage3_rows, input_row=None):
    source, stage3, output = (tmp_path / name for name in ("input.csv", "stage3.csv", "output.csv"))
    _write(source, [input_row or _input()])
    _write(stage3, stage3_rows)
    summary = refine.enrich_refine_tier_labels(input_csv=source, stage3_csv=stage3, out_csv=output)
    with output.open(newline="") as stream:
        row = next(csv.DictReader(stream))
    return row, summary, output


def test_zero_is_an_observation_not_a_fallback(tmp_path):
    row, summary, _ = _enrich(tmp_path, [_stage3()])
    assert float(row["refine_tier_label"]) == 0
    assert float(row["refine_confidence"]) == 0
    assert summary["refine_tier_label_rows"] == 1


def test_scalar_energy_difference_is_never_a_force_label(tmp_path):
    row, _, _ = _enrich(tmp_path, [_stage3(deltaG_mm_gbsa_kcal_mol=1)])
    assert row.get("delta_force", "") == ""
    assert row.get("delta_force_label_source", "") == ""
    assert float(row["refine_tier_delta"]) == 3
    assert row["refine_tier_value_semantics"] == "computed_proxy_not_physical_energy_residual"


@pytest.mark.parametrize("reverse", [False, True])
def test_duplicate_join_keys_are_rejected_independent_of_order(tmp_path, reverse):
    rows = [_stage3(deltaG_mm_gbsa_kcal_mol=1), _stage3(deltaG_mm_gbsa_kcal_mol=2)]
    if reverse:
        rows.reverse()
    row, summary, _ = _enrich(tmp_path, rows)
    assert row.get("refine_tier_label", "") == ""
    assert "ambiguous" in row["refine_tier_join_status"]
    assert summary["refine_tier_label_rows"] == 0


def test_duplicate_queue_id_cannot_choose_an_unrelated_row(tmp_path):
    row, _, _ = _enrich(
        tmp_path, [_stage3(queue_id="q", deltaG_mm_gbsa_kcal_mol=1),
                   _stage3(queue_id="q", ligand_id="other", deltaG_mm_gbsa_kcal_mol=2)],
        _input(queue_id="q"),
    )
    assert row.get("refine_tier_label", "") == ""
    assert "ambiguous" in row["refine_tier_join_status"]


def test_source_identity_and_original_declarations_survive_join(tmp_path):
    raw = _stage3(source_csv="original.csv", source_sha256="e" * 64, label_kind="affinity_score")
    row, _, _ = _enrich(tmp_path, [raw])
    provenance = json.loads(row["source_provenance_json"])
    records = provenance["records"]
    assert len(records) == 2
    original = records[-1]["row"]
    assert original == {key: str(value) for key, value in raw.items()}
    assert records[-1]["source_sha256"] and records[-1]["source_line"] == 2
    assert row["role"] == "fit" and row["split"] == "development"
    assert row["refine_tier_evidence_kind"] == "own_engine_observation"


@pytest.mark.parametrize("field,value", [("role", "holdout"), ("split", "test"),
                                         ("dataset_split", "validation"), ("evaluation_only", "true")])
def test_stage3_exclusion_reaches_trainer_and_cache_without_relabeling_fit(tmp_path, field, value):
    row, summary, output = _enrich(tmp_path, [_stage3(**{field: value})])
    assert row["role"] == "fit"
    assert row.get("refine_tier_label", "") == ""
    assert summary["refine_tier_label_rows"] == 0
    assert declared_evaluation_only(row) is True
    from tools import train_residual_production_score_model as trainer
    with pytest.raises(ValueError, match="evaluation_only_training_input"):
        trainer._load_rows(output)
    with pytest.raises(ValueError, match="evaluation_only_training_input"):
        trainer.try_skip_training(
            input_csv=str(output), out_checkpoint=str(tmp_path / "never.pt"),
            out_json=str(tmp_path / "never.json"), force_derivation_json="/dev/null",
            fingerprint_json=str(tmp_path / "fingerprint.json"), epochs=1, hidden_dim=4,
            batch_size=2, lr=.001, weight_decay=0, train_ratio=.8, seed=1,
        )
    assert not (tmp_path / "never.pt").exists()


@pytest.mark.parametrize("field", ["pose_id", "coordinate_sha256", "atom_order_sha256", "chemical_state_sha256", "environment_sha256"])
def test_declared_identity_mismatch_cannot_supply_a_refine_value(tmp_path, field):
    row, _, _ = _enrich(tmp_path, [_stage3(**{field: "different"})])
    assert row.get("refine_tier_label", "") == ""
    assert "identity" in row["refine_tier_join_status"]


@pytest.mark.parametrize("value", ["nan", "inf", "-inf", "invalid"])
def test_invalid_primary_observation_does_not_use_fallback(tmp_path, value):
    row, _, _ = _enrich(tmp_path, [_stage3(deltaG_mm_gbsa_kcal_mol=value)])
    assert row.get("refine_tier_label", "") == ""
    assert "invalid" in row["refine_tier_join_status"]


def test_refine_reader_rejects_duplicate_policy_headers(tmp_path):
    source, stage3, output = (tmp_path / name for name in ("input.csv", "stage3.csv", "output.csv"))
    _write(source, [_input()])
    stage3.write_text("target,ligand_id,deltaG_mm_gbsa_kcal_mol,role,Role\nsynthetic_target,synthetic_ligand,1,holdout,fit\n")
    with pytest.raises(ValueError, match="duplicate_csv_column"):
        refine.enrich_refine_tier_labels(input_csv=source, stage3_csv=stage3, out_csv=output)
    assert not output.exists()


def test_base_builder_rejects_protected_stage3_association(tmp_path):
    source = tmp_path / "synthetic_stage5_ranking_rows.csv"
    stage3 = tmp_path / "synthetic_stage3_scores.csv"
    _write(source, [_input(reference_binding_kcal_mol=-2, binding_score_composite_v7=-3)])
    _write(stage3, [_stage3(role="holdout")])
    result = base.build_residual_production_supervised_dataset(stage5_glob=str(source), min_rows=1, min_targets=1)
    assert result["rows"] == []
    assert result["sources"][0]["rejections"][0]["reason"] == "stage3_evaluation_only_source"


def test_base_builder_preserves_declared_split_and_raw_source_record(tmp_path):
    source = tmp_path / "synthetic_stage5_ranking_rows.csv"
    original = _input(reference_binding_kcal_mol=-2, binding_score_composite_v7=-3, run_id="run")
    _write(source, [original])
    result = base.build_residual_production_supervised_dataset(stage5_glob=str(source), min_rows=1, min_targets=1)
    row = result["rows"][0]
    assert row["split"] == "development" and row["dataset_split"] == "train"
    assert json.loads(row["source_provenance_json"])["records"][0]["row"]["run_id"] == "run"


@pytest.mark.parametrize("kind", ["IC50", "Ki", "Kd", "potential_energy"])
def test_explicit_incompatible_reference_cannot_be_subtracted_from_composite_score(tmp_path, kind):
    source = tmp_path / "synthetic_stage5_ranking_rows.csv"
    _write(source, [_input(reference_binding_kcal_mol=1, binding_score_composite_v7=2,
                          reference_label_kind=kind)])
    result = base.build_residual_production_supervised_dataset(stage5_glob=str(source), min_rows=1, min_targets=1)
    assert result["rows"] == []
    assert result["sources"][0]["rejections"][0]["reason"] == "incompatible_score_reference_semantics"


@pytest.mark.parametrize("value", ["nan", "inf", "invalid"])
def test_base_stage3_reader_uses_same_nonfinite_policy_as_refine(tmp_path, value):
    stage3 = tmp_path / "stage3.csv"
    _write(stage3, [_stage3(deltaG_mm_gbsa_kcal_mol=value)])
    values, source = base._load_energy_proxy_map(stage3)
    assert values == {}
    assert source["stage3_invalid_observation_rows"] == 1


def test_missing_primary_observation_can_use_explicit_fallback(tmp_path):
    row, _, _ = _enrich(tmp_path, [_stage3(deltaG_mm_gbsa_kcal_mol="",
                                         binding_energy_explicit_water_recheck_kcal_mol_proxy=0)])
    assert float(row["refine_tier_label"]) == 0


def test_legacy_generated_scalar_force_is_removed_on_regeneration(tmp_path):
    raw = _input(delta_force=-123, delta_force_label_source="refine_tier_energy_derivation_proxy")
    row, _, _ = _enrich(tmp_path, [_stage3()], raw)
    assert row["delta_force"] == row["delta_force_label_source"] == ""
    assert json.loads(row["source_provenance_json"])["records"][0]["row"]["delta_force"] == "-123"


@pytest.mark.parametrize("provenance", ["{}", "[]", "not json", '{"schema_version":"unknown","records":[]}'])
def test_malformed_provenance_is_not_treated_as_unrestricted(tmp_path, provenance):
    from tools import train_residual_production_score_model as trainer
    path = tmp_path / "malformed.csv"
    _write(path, [_input(source_provenance_json=provenance)])
    with pytest.raises(ValueError, match="invalid_source_provenance"):
        trainer._load_rows(path)


def test_legacy_enriched_dataset_requires_provenance_regeneration(tmp_path):
    from tools import train_residual_production_score_model as trainer
    path = tmp_path / "legacy.csv"
    _write(path, [_input(refine_tier_label=1, refine_tier_label_source="stage3_refine_tier")])
    with pytest.raises(ValueError, match="legacy_refine_source_provenance_missing"):
        trainer._load_rows(path)


@pytest.mark.parametrize("kind", ["experimental_label", "ai_prediction", "heuristic"])
def test_refine_values_preserve_but_do_not_mix_declared_evidence_kinds(tmp_path, kind):
    row, summary, _ = _enrich(tmp_path, [_stage3(evidence_kind=kind)])
    assert row["refine_tier_evidence_kind"] == kind
    assert row["refine_tier_label"] == ""
    assert summary["refine_tier_label_rows"] == 0


def test_direct_trainer_rejects_incompatible_assay_reference(tmp_path):
    from tools import train_residual_production_score_model as trainer
    path = tmp_path / "assay.csv"
    _write(path, [_input(reference_label_kind="IC50")])
    with pytest.raises(ValueError, match="incompatible_score_reference_semantics"):
        trainer._load_rows(path)


@pytest.mark.parametrize("field", ["coordinate_sha256", "atom_order_sha256", "chemical_state_sha256", "environment_sha256"])
def test_matching_but_malformed_hashes_are_not_declared_identity_matches(tmp_path, field):
    primary = _input()
    primary[field] = "not-a-sha"
    row, _, _ = _enrich(tmp_path, [_stage3(**{field: "not-a-sha"})], primary)
    assert row["refine_tier_label"] == ""
    assert row["refine_tier_join_status"].startswith("rejected_invalid_identity")


@pytest.mark.parametrize("malformed", [False, True])
def test_auxiliary_stage3_provenance_is_checked_by_direct_trainer_and_cache(tmp_path, malformed):
    from tools import train_residual_production_score_model as trainer
    from tools.product.residual_evidence import source_provenance_json
    declaration = source_provenance_json({"role": "holdout"}, source_csv="synthetic_stage3.csv",
                                          source_sha256="a" * 64, source_line=2)
    row = _input(stage3_source_provenance_json="invalid JSON" if malformed else declaration)
    path = tmp_path / "auxiliary.csv"
    _write(path, [row])
    reason = "invalid_source_provenance" if malformed else "evaluation_only_training_input"
    with pytest.raises(ValueError, match=reason):
        trainer._load_rows(path)
    with pytest.raises(ValueError, match=reason):
        trainer.try_skip_training(
            input_csv=str(path), out_checkpoint=str(tmp_path / "never.pt"),
            out_json=str(tmp_path / "never.json"), force_derivation_json="/dev/null",
            fingerprint_json=str(tmp_path / "fingerprint.json"), epochs=1, hidden_dim=4,
            batch_size=2, lr=.001, weight_decay=0, train_ratio=.8, seed=1,
        )


def test_base_builder_folds_all_associated_origins_into_canonical_provenance(tmp_path):
    source = tmp_path / "synthetic_stage5_ranking_rows.csv"
    stage3 = tmp_path / "synthetic_stage3_scores.csv"
    _write(source, [_input(reference_binding_kcal_mol=-2, binding_score_composite_v7=-3)])
    _write(stage3, [_stage3()])
    result = base.build_residual_production_supervised_dataset(stage5_glob=str(source), min_rows=1, min_targets=1)
    records = json.loads(result["rows"][0]["source_provenance_json"])["records"]
    assert {record["source_csv"] for record in records} == {str(source), str(stage3)}


@pytest.mark.parametrize("source_pose", ["   ", ""])
def test_whitespace_pose_ids_are_missing_identity(tmp_path, source_pose):
    primary = _input()
    primary["pose_id"] = "   "
    row, _, _ = _enrich(tmp_path, [_stage3(pose_id=source_pose)], primary)
    assert row["refine_tier_identity_status"] == "unverified_missing_identity"
    assert row["refine_tier_join_status"] == "joined"
    original = json.loads(row["source_provenance_json"])["records"][0]["row"]
    assert original["pose_id"] == "   "


@pytest.mark.parametrize("value", ["calibration", "development_test", "calibration_dev"])
@pytest.mark.parametrize("field", ["role", "split", "dataset_split"])
@pytest.mark.parametrize("location", ["row", "source_provenance_json", "stage3_source_provenance_json"])
def test_reserved_learning_roles_reach_every_residual_consumer(tmp_path, value, field, location):
    from tools import train_residual_production_score_model as trainer
    from tools.product.residual_evidence import source_provenance_json
    stage = _stage3()
    if location == "row":
        stage[field] = value
    else:
        stage[location] = source_provenance_json(
            {field: value}, source_csv="synthetic_original_roles.csv",
            source_sha256="e" * 64, source_line=2,
        )
    row, summary, output = _enrich(tmp_path, [stage])
    assert row["role"] == "fit" and row["evaluation_only"] == "false"
    assert row["refine_tier_label"] == "" and summary["refine_tier_label_rows"] == 0
    assert declared_evaluation_only(row)
    origins = json.loads(row["source_provenance_json"])["records"]
    assert any(origin["row"].get(field) == value for origin in origins)
    with pytest.raises(ValueError, match="evaluation_only_training_input"):
        trainer._load_rows(output)
    with pytest.raises(ValueError, match="evaluation_only_training_input"):
        trainer.try_skip_training(
            input_csv=str(output), out_checkpoint=str(tmp_path / "never.pt"),
            out_json=str(tmp_path / "never.json"), force_derivation_json="/dev/null",
            fingerprint_json=str(tmp_path / "fingerprint.json"), epochs=1, hidden_dim=4,
            batch_size=2, lr=.001, weight_decay=0, train_ratio=.8, seed=1,
        )
    assert not (tmp_path / "never.pt").exists()
    row.update(reference_binding_kcal_mol=-2, binding_score_composite_v7=-3)
    source = tmp_path / "direct_stage5_ranking_rows.csv"
    _write(source, [row])
    result = base.build_residual_production_supervised_dataset(stage5_glob=str(source), min_rows=1, min_targets=1)
    assert result["rows"] == []
    assert result["sources"][0]["rejections"][0]["reason"] == "evaluation_only_row"


@pytest.mark.parametrize("value", ["fit", "train", "development_source"])
def test_nonreserved_source_roles_keep_measured_zero(tmp_path, value):
    from tools import train_residual_production_score_model as trainer
    from tools.product.residual_evidence import source_provenance_json
    origin = source_provenance_json(
        {"split": value}, source_csv="synthetic_original_roles.csv",
        source_sha256="e" * 64, source_line=2,
    )
    row, summary, output = _enrich(tmp_path, [_stage3(source_provenance_json=origin)])
    assert float(row["refine_tier_label"]) == 0 and summary["refine_tier_label_rows"] == 1
    assert not declared_evaluation_only(row)
    assert float(trainer._load_rows(output)[0]["refine_tier_label"]) == 0
    assert row.get("delta_force", "") == ""

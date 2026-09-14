"""Synthetic assay declarations must never become composite-score residual labels."""
from __future__ import annotations

import csv
import json

import pytest

from tools.product import build_refine_tier_residual_training_dataset as refine
from tools.product import build_residual_production_supervised_dataset as base
from tools.product import residual_evidence as evidence
from tools import train_residual_production_score_model as trainer


def _row(**updates):
    row = dict(target="synthetic_target", ligand_id="synthetic_ligand", role="fit",
               split="development", dataset_split="train", evaluation_only="false",
               pose_id="synthetic_pose", coordinate_sha256="a" * 64,
               atom_order_sha256="b" * 64, chemical_state_sha256="c" * 64,
               environment_sha256="d" * 64, is_binder=1, raw_score=-3,
               delta_score=1, reference_binding_kcal_mol=-2,
               binding_score_composite_v7=-3)
    row.update(updates)
    return row


def _stage3(**updates):
    return _row(binding_energy_mmpbsa_kcal_mol_proxy=-2,
                deltaG_mm_gbsa_kcal_mol=0, physics_refinement_confidence=0,
                **updates)


def _write(path, rows):
    fields = list(dict.fromkeys(key for row in rows for key in row))
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _origin(declaration):
    return evidence.source_provenance_json(
        declaration, source_csv="synthetic_origin.csv", source_sha256="e" * 64,
        source_line=2,
    )


def _declare(row, declaration, carrier):
    if carrier == "direct":
        row.update(declaration)
    else:
        row[carrier] = _origin(declaration)
    return row


def _cache(path, tmp_path):
    return trainer.try_skip_training(
        input_csv=str(path), out_checkpoint=str(tmp_path / "absent.pt"),
        out_json=str(tmp_path / "absent.json"), force_derivation_json="/dev/null",
        fingerprint_json=str(tmp_path / "absent-fingerprint.json"), epochs=1,
        hidden_dim=4, batch_size=2, lr=.001, weight_decay=0., train_ratio=.8, seed=3,
    )


@pytest.mark.parametrize("declaration", [
    {"evidence_kind": "experimental_label", "endpoint": "IC50", "unit": "nM"},
    {"evidence_kind": "experimental_label"},
    {"endpoint": "IC50"},
    {"declared_endpoint": "EC50"},
    {"endpoint": "pIC50"},
    {"reference_quantity": "negative_log10_molar_IC50"},
    {" Evidence_Kind ": " Experimental_Label ", " ENDPOINT ": " IC50 "},
])
@pytest.mark.parametrize("carrier", ["direct", "source_provenance_json", "stage3_source_provenance_json"])
def test_semantic_declarations_cannot_be_hidden_by_carrier_or_alias(declaration, carrier):
    row = _declare(_row(), declaration, carrier)
    assert evidence.score_reference_rejection(row) == "incompatible_score_reference_semantics"


@pytest.mark.parametrize("pathway", ["base", "trainer", "cache"])
@pytest.mark.parametrize("carrier", ["direct", "source_provenance_json", "stage3_source_provenance_json"])
def test_actual_consumers_reject_declared_assay_before_score_or_energy_use(tmp_path, pathway, carrier):
    declaration = {"evidence_kind": "experimental_label", "endpoint": "IC50", "unit": "nM"}
    raw = _declare(_row(delta_energy=17), declaration, carrier)
    path = tmp_path / "synthetic_stage5_ranking_rows.csv"
    _write(path, [raw])
    if pathway == "base":
        result = base.build_residual_production_supervised_dataset(stage5_glob=str(path), min_rows=1, min_targets=1)
        assert result["rows"] == []
        assert result["sources"][0]["rejections"][0]["reason"] == "incompatible_score_reference_semantics"
    else:
        with pytest.raises(ValueError, match="incompatible_score_reference_semantics"):
            trainer._load_rows(path) if pathway == "trainer" else _cache(path, tmp_path)
    assert not (tmp_path / "absent.pt").exists()


@pytest.mark.parametrize("carrier", ["direct", "source_provenance_json", "stage3_source_provenance_json"])
@pytest.mark.parametrize("source_side", ["primary", "stage3"])
def test_refine_rejects_assay_from_either_original_source_before_materialization(tmp_path, carrier, source_side):
    primary, auxiliary = _row(), _stage3()
    original = {"reference_quantity": "IC50", "evidence_kind": "experimental_label", "role": "development_source"}
    _declare(primary if source_side == "primary" else auxiliary, original, carrier)
    source, stage3, output = [tmp_path / name for name in ("input.csv", "stage3.csv", "enriched.csv")]
    _write(source, [primary])
    _write(stage3, [auxiliary])
    report = refine.enrich_refine_tier_labels(input_csv=source, stage3_csv=stage3, out_csv=output)
    with output.open(newline="") as stream:
        row = next(csv.DictReader(stream))
    assert row["refine_tier_label"] == row["refine_tier_delta"] == row["mm_gbsa_delta"] == ""
    assert row["refine_tier_join_status"].startswith("rejected_incompatible")
    assert report["refine_tier_label_rows"] == 0
    assert row["role"] == primary["role"]
    assert any(r["row"].get("reference_quantity") == "IC50" for r in evidence.provenance_records(row))
    with pytest.raises(ValueError, match="incompatible_score_reference_semantics"):
        trainer._load_rows(output)


@pytest.mark.parametrize("carrier", ["direct", "source_provenance_json"])
def test_base_associated_stage3_assay_is_rejected_with_source_receipt(tmp_path, carrier):
    source, stage3 = tmp_path / "synthetic_stage5_ranking_rows.csv", tmp_path / "synthetic_stage3_scores.csv"
    _write(source, [_row()])
    _write(stage3, [_declare(_stage3(), {"endpoint": "IC50", "evidence_kind": "experimental_label"}, carrier)])
    result = base.build_residual_production_supervised_dataset(
        stage5_glob=str(source), min_rows=1, min_targets=1,
    )
    assert result["rows"] == []
    rejection = result["sources"][0]["rejections"][0]
    assert "incompatible_score_reference_semantics" in rejection["reason"]
    origins = evidence.provenance_records({"source_provenance_json": rejection["source_provenance_json"]})
    assert any(r["row"].get("endpoint") == "IC50" for r in origins)
    assert any(r["row"].get("role") == "fit" for r in origins)


@pytest.mark.parametrize("kind", ["computed", "synthetic", "own_engine_observation"])
def test_computed_refine_zero_and_original_roles_remain_usable(tmp_path, kind):
    source, stage3, output = [tmp_path / name for name in ("input.csv", "stage3.csv", "enriched.csv")]
    _write(source, [_row()])
    _write(stage3, [_stage3(evidence_kind=kind)])
    report = refine.enrich_refine_tier_labels(input_csv=source, stage3_csv=stage3, out_csv=output)
    with output.open(newline="") as stream:
        row = next(csv.DictReader(stream))
    assert report["refine_tier_label_rows"] == 1
    assert float(row["refine_tier_label"]) == float(row["refine_confidence"]) == 0
    assert row["role"] == "fit" and row["split"] == "development"
    assert row["refine_tier_value_semantics"] == "computed_proxy_not_physical_energy_residual"
    assert row.get("delta_force", "") == ""
    assert len(trainer._load_rows(output)) == 1
    assert _cache(output, tmp_path) is None


def test_base_computed_auxiliary_zero_retains_provenance(tmp_path):
    source, stage3 = tmp_path / "synthetic_stage5_ranking_rows.csv", tmp_path / "synthetic_stage3_scores.csv"
    _write(source, [_row()])
    _write(stage3, [_stage3(evidence_kind="computed")])
    result = base.build_residual_production_supervised_dataset(
        stage5_glob=str(source), min_rows=1, min_targets=1,
    )
    row = result["rows"][0]
    assert row["stage3_energy_proxy_value"] == 0
    assert row["delta_score"] == 1
    assert row["refine_tier_label"] == ""
    assert len(json.loads(row["source_provenance_json"])["records"]) == 2

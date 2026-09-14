"""Fresh synthetic state conflicts, including direct training and cache admission."""
import csv
import json
from pathlib import Path
import subprocess
import sys

import pytest

from tests.unit.test_refine_tier_residual_integrity import _enrich, _input, _stage3, _write
from tools import train_residual_production_score_model as trainer
from tools.product import build_residual_production_supervised_dataset as base
from tools.product.residual_evidence import IDENTITY_FIELDS, source_provenance_json


def _origin(field, value):
    return source_provenance_json(
        {field: value, "role": "fit", "evidence_kind": "own_engine_observation"},
        source_csv="synthetic_original_observation.csv", source_sha256="1" * 64,
        source_line=2,
    )


@pytest.mark.parametrize("field", IDENTITY_FIELDS)
def test_nested_original_state_conflict_cannot_be_joined(tmp_path, field):
    stage = _stage3(source_provenance_json=_origin(field, "f" * 64))
    row, summary, _ = _enrich(tmp_path, [stage])
    assert row["refine_tier_label"] == ""
    assert row["refine_tier_join_status"] == "rejected_conflicting_source_identity:" + field
    assert summary["refine_tier_label_rows"] == 0


@pytest.mark.parametrize("field", IDENTITY_FIELDS)
def test_direct_trainer_and_cache_recheck_original_state(tmp_path, field):
    row, _, output = _enrich(tmp_path, [_stage3()])
    row["source_provenance_json"] = _origin(field, "f" * 64)
    _write(output, [row])
    with pytest.raises(ValueError, match="conflicting_source_identity:" + field):
        trainer._load_rows(output)
    with pytest.raises(ValueError, match="conflicting_source_identity:" + field):
        trainer.try_skip_training(
            input_csv=str(output), out_checkpoint=str(tmp_path / "never.pt"),
            out_json=str(tmp_path / "never.json"), force_derivation_json="/dev/null",
            fingerprint_json=str(tmp_path / "fingerprint.json"), epochs=1, hidden_dim=4,
            batch_size=2, lr=.001, weight_decay=0, train_ratio=.8, seed=1,
        )
    assert not (tmp_path / "never.pt").exists()


@pytest.mark.parametrize("field", IDENTITY_FIELDS)
def test_matching_original_state_keeps_zero_and_can_enter_trainer(tmp_path, field):
    row, summary, output = _enrich(tmp_path, [_stage3(source_provenance_json=_origin(field, _input()[field]))])
    assert float(row["refine_tier_label"]) == 0
    assert summary["refine_tier_label_rows"] == 1
    assert trainer._load_rows(output)[0][field] == _input()[field]


def test_base_materializer_uses_same_original_state_policy(tmp_path):
    row, _, _ = _enrich(tmp_path, [_stage3()])
    row.update(source_provenance_json=_origin("chemical_state_sha256", "f" * 64),
               reference_binding_kcal_mol=-2, binding_score_composite_v7=-3)
    source = tmp_path / "synthetic_stage5_ranking_rows.csv"
    _write(source, [row])
    result = base.build_residual_production_supervised_dataset(stage5_glob=str(source), min_rows=1, min_targets=1)
    assert result["rows"] == []
    assert result["sources"][0]["rejections"][0]["reason"] == "conflicting_source_identity:chemical_state_sha256"


def test_actual_cli_keeps_requested_denominator_and_zero_control(tmp_path):
    positive, negative = _input(), _input()
    negative["ligand_id"] = "synthetic_conflicting_ligand"
    good, bad = _stage3(), _stage3(source_provenance_json=_origin("chemical_state_sha256", "f" * 64))
    bad["ligand_id"] = negative["ligand_id"]
    source, stage, output = (tmp_path / p for p in ("input.csv", "stage.csv", "output.csv"))
    _write(source, [positive, negative])
    _write(stage, [good, bad])
    root = Path(base.__file__).resolve().parents[2]
    code = "import sys,runpy;sys.path.insert(0,sys.argv.pop(1));runpy.run_module('tools.product.build_refine_tier_residual_training_dataset',run_name='__main__')"
    result = subprocess.run([sys.executable, "-c", code, str(root), "--input-csv", str(source),
                             "--stage3-csv", str(stage), "--out-csv", str(output)],
                            cwd=str(root), capture_output=True, text=True, check=True)
    summary = json.loads(result.stdout)
    assert summary["row_count"] == 2 and summary["refine_tier_label_rows"] == 1
    assert summary["rejected_or_unmatched_rows"] == 1
    with output.open(newline="") as stream:
        rows = list(csv.DictReader(stream))
    assert float(rows[0]["refine_tier_label"]) == 0
    assert rows[1]["refine_tier_label"] == ""
    assert rows[1]["refine_tier_join_status"] == "rejected_conflicting_source_identity:chemical_state_sha256"

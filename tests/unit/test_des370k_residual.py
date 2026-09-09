"""Independent numerical and admission controls for the fragment shadow."""
import copy

import numpy as np
import pytest

from betelgeuze_engine.product import des370k_residual as residual
from tests.unit.test_des370k_interaction import evaluate, fixture


def fit_rows():
    x = np.random.default_rng(1981).normal(size=(20, len(residual.FEATURE_NAMES)))
    y = 3 * x[:, 0] - 2 * x[:, 3] + 7
    return [{"features": v.tolist(), "reference_kcal_per_mol": float(y[i]),
             "baseline_kcal_per_mol": 0., "role": "fit", "evaluation_only": False,
             "evidence_kind": "external_computed_reference", "geometry_sha256": str(i)}
            for i, v in enumerate(x)]


def fit(rows):
    return residual.fit_energy_residual(rows, runtime_sha256="runtime", plan_sha256="plan")


def test_fixed_ridge_matches_independent_dual_solution():
    rows = fit_rows()
    model = fit(rows)
    x = (np.asarray([r["features"] for r in rows]) - model["center"]) / model["scale"]
    y = np.asarray([r["reference_kcal_per_mol"] for r in rows])
    weights = x.T @ np.linalg.solve(x @ x.T + 10 * np.eye(len(rows)), y - y.mean())
    np.testing.assert_allclose(weights, model["coefficients"], atol=2e-14)
    assert model["intercept"] == pytest.approx(y.mean(), abs=1e-14)
    assert np.mean(np.abs(x @ weights + model["intercept"] - y)) < np.mean(np.abs(y))
    assert model["force_residual"] is None and model["uncertainty_calibrated"] is False


@pytest.mark.parametrize("changes", [{"role": "development"}, {"evaluation_only": True},
                                     {"evaluation_only": 0}, {"evidence_kind": "experimental_label"},
                                     {"evidence_kind": "AI_prediction"}])
def test_fit_rejects_evaluation_and_wrong_evidence(changes):
    rows = fit_rows()
    rows[0].update(changes)
    with pytest.raises(ValueError):
        fit(rows)


def test_duplicate_and_nonfinite_fit_rows_are_rejected():
    rows = fit_rows()
    with pytest.raises(ValueError, match="duplicate"):
        fit(rows + [copy.deepcopy(rows[0])])
    rows[0]["reference_kcal_per_mol"] = float("nan")
    with pytest.raises(ValueError, match="invalid_fit_values"):
        fit(rows)


def test_shadow_preserves_baseline_and_abstains_without_fake_probability():
    score = evaluate(*fixture())
    rows = fit_rows()
    for row in rows:
        row["features"] = (np.asarray(row["features"]) * .001).tolist()
    model = fit(rows)
    original = copy.deepcopy(score)
    result = residual.predict_energy_residual(score, model, runtime_sha256="runtime", plan_sha256="plan")
    assert score == original
    assert result["status"] == "abstained"
    assert result["supported_shadow_energy_kcal_per_mol"] is None
    assert result["baseline_kcal_per_mol"] == score["baseline"]["quantities"]["cross_total_kcal_per_mol"]
    assert result["force_labels"] is None and result["uncertainty"] is None


def test_checkpoint_and_geometry_mutations_are_rejected():
    score = evaluate(*fixture())
    model = fit(fit_rows())
    with pytest.raises(ValueError, match="runtime_or_contract"):
        residual.predict_energy_residual(score, model, runtime_sha256="other", plan_sha256="plan")
    model["intercept"] += 1
    with pytest.raises(ValueError, match="hash_mismatch"):
        residual.predict_energy_residual(score, model, runtime_sha256="runtime", plan_sha256="plan")
    score["native_record"]["xyz"] += " 0"
    with pytest.raises(ValueError, match="geometry_or_baseline"):
        residual.geometry_features(score)


def test_monomer_partition_is_representation_and_stereoisomer_stable():
    for a, b in [("O=CN(C)C", "CN(C)C=O"), ("C[C@H](O)CC", "C[C@@H](O)CC")]:
        assert residual.monomer_identity(a) == residual.monomer_identity(b)
        assert residual.monomer_role(residual.monomer_identity(a)) == residual.monomer_role(residual.monomer_identity(b))


def test_features_use_geometry_not_identifiers_or_labels():
    score = evaluate(*fixture())
    features = residual.geometry_features(score)
    changed = copy.deepcopy(score)
    changed["native_record"].update(geom_id="unrelated", role="holdout", **{"cbs_CCSD(T)_all": -9000})
    changed["reference"]["value"] = 990000
    np.testing.assert_array_equal(features, residual.geometry_features(changed))

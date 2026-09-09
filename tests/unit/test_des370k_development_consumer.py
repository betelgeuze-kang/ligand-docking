"""Fresh metadata-only consumer controls without downloading public data."""
import json

from betelgeuze_engine.product.des370k_interaction import GEOMETRY_FIELDS
from tools.product import run_des370k_residual_development as consumer


def test_selection_never_accesses_labels_and_rejects_all_duplicate_keys(tmp_path, monkeypatch):
    class Guarded(dict):
        def __getitem__(self, key):
            assert key in GEOMETRY_FIELDS, f"reference label accessed during selection: {key}"
            return super().__getitem__(key)
    def row(gid, smi="c1ccccc1", sid="31"):
        return Guarded(smiles0=smi, smiles1=smi, natoms0="12", natoms1="12",
                       charge0="0", charge1="0", system_id=sid, group_orig="synthetic",
                       group_id="9", k_index="0", geom_id=gid, xyz="unused selection geometry",
                       elements="unused selection elements", **{"cbs_CCSD(T)_all": object()})
    rows = [row("101"), row("102"), row("102"), row("103", "O", "32")]
    monkeypatch.setattr(consumer, "native_rows", lambda archive: iter(rows))
    selected = consumer.select_metadata(None, tmp_path, {"systems_per_role_cap": 8,
                                                        "geometries_per_system_cap": 12})
    assert set(selected) == {"101"}
    assert set(selected["101"]["geometry"]) == set(GEOMETRY_FIELDS)
    outcomes = json.loads((tmp_path / "metadata-selection.json").read_text())
    assert outcomes["total_source_rows"] == 4
    assert outcomes["outcomes"]["duplicate_geometry_id_rejected_all"] == 2
    assert sum(outcomes["outcomes"].values()) == 4


def test_metric_denominators_keep_failures_and_abstentions():
    rows = [{"role": "development", "status": "scoring_failed"},
            {"role": "development", "status": "evaluated", "reference": {"value": 0.},
             "shadow": {"status": "abstained", "baseline_kcal_per_mol": 1.,
                        "raw_shadow_energy_kcal_per_mol": 2.}}]
    result = consumer.metrics(rows, "development")
    assert result["requested"] == 2 and result["failed"] == 1
    assert result["shadow_abstained"] == 1 and result["coverage_of_all_requested"] == 0
    assert result["baseline_all_evaluable"]["mae_kcal_per_mol"] == 1.
    assert result["shadow_supported"] is None

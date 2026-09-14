"""Fresh synthetic endpoint controls; never read experimental observations."""
from copy import deepcopy
import csv
import hashlib
import json

import pytest
from rdkit import rdBase

from betelgeuze_engine.product import public_assay_selector_shadow as shadow

ACTUAL = "d5c4c17902ee35c920c2948f445f06b0aba13c4ba02cfa8a13390a18689ff4b3"
OLD_KI = "de9b3e21c93b0f15c02df221d2f8ee9caa3d5e0590442c34efed3394b969ac85"
TARGET = "a" * 64
QUANTITY = "negative_log10_molar_IC50"


def checkpoint(tmp_path, monkeypatch):
    # Start from old Ki registration to reproduce the old consumer's semantic bug.
    binding = deepcopy(shadow._REGISTERED_BINDINGDB_V1[OLD_KI])
    binding.update(endpoint="IC50", prediction_quantity=QUANTITY,
                   target_annotation_sha256=TARGET, mean_baseline=0.,
                   rdkit_version=rdBase.rdkitVersion)
    payload = dict(binding, schema_version=shadow.BINDINGDB_SCHEMA,
                   features=dict(shadow.BINDINGDB_FEATURES), coefficients=[0.] * 1024,
                   intercept=0., uncertainty_calibrated=False,
                   product_ranking_enabled=False, customer_execution=False)
    raw = json.dumps(payload).encode()
    digest = hashlib.sha256(raw).hexdigest()
    monkeypatch.setitem(shadow._REGISTERED_BINDINGDB_V1, digest, binding)
    if ACTUAL in shadow._CHECKPOINT_EVIDENCE:
        monkeypatch.setitem(shadow._CHECKPOINT_EVIDENCE, digest,
                            deepcopy(shadow._CHECKPOINT_EVIDENCE[ACTUAL]))
    path = tmp_path / "synthetic.json"
    path.write_bytes(raw)
    return path, digest


def row(**changes):
    return dict(dict(ligand_id="repeated", smiles="CCCCC", endpoint="IC50",
                     target_annotation_sha256=TARGET), **changes)


def sidecar(tmp_path, path, digest, rows):
    source = tmp_path / "requests.csv"
    with source.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    before = source.read_bytes()
    output = tmp_path / "sidecar.json"
    summary = shadow.run_pre_docking_shadow(ligand_csv=str(source), ligand_sdf="",
        docking_request_json="", resume_stage3_only=False, checkpoint=str(path),
        checkpoint_sha256=digest, output_json=str(output))
    assert source.read_bytes() == before
    return summary, json.loads(output.read_text()), source


def test_ic50_quantity_and_scope_come_from_model_even_for_ki_input(tmp_path, monkeypatch):
    path, digest = checkpoint(tmp_path, monkeypatch)
    model = shadow.load_public_assay_selector(path, expected_sha256=digest)
    result = model.predict_rows([row(), row(endpoint="Ki"), row(), row(smiles="")])
    assert [r["prediction_quantity"] for r in result] == [QUANTITY] * 4
    assert [r["predicted_value"] for r in result] == [0., None, 0., None]
    assert [r["mean_baseline_value"] for r in result] == [0., None, 0., None]
    assert [r["row_index"] for r in result] == [0, 1, 2, 3]
    assert [r["ligand_id"] for r in result] == ["repeated"] * 4
    assert TARGET in model.metadata["prediction_scope"]
    assert model.metadata["prediction_scope"].endswith("_IC50")
    assert "P00742" not in model.metadata["prediction_scope"]


@pytest.mark.parametrize("changes,reason", [
    ({"endpoint": "Ki"}, "endpoint"), ({"endpoint": "Kd"}, "endpoint"),
    ({"endpoint": None}, "endpoint"), ({"target_annotation_sha256": None}, "target_annotation"),
    ({"target_annotation_sha256": "P31749"}, "target_annotation"),
    ({"smiles": "[13CH3]CCCC"}, "isotope"), ({"smiles": "CCCCC.C"}, "multifragment"),
    ({"is_ood": True}, "declared_ood"), ({"is_ood": float("nan")}, "invalid_ood"),
])
def test_ic50_unsupported_is_neither_zero_nor_a_different_endpoint(tmp_path, monkeypatch, changes, reason):
    path, digest = checkpoint(tmp_path, monkeypatch)
    result = shadow.load_public_assay_selector(path, expected_sha256=digest).predict_rows([row(**changes)])[0]
    assert result["status"] == "unsupported" and reason in result["reason"]
    assert result["prediction_quantity"] == QUANTITY
    assert result["predicted_value"] is result["mean_baseline_value"] is None


@pytest.mark.parametrize("kind", ["valid", "bad_bytes", "bad_header", "unknown_hash"])
def test_ic50_sidecar_preserves_model_semantics_and_all_rows(tmp_path, monkeypatch, kind):
    path, digest = checkpoint(tmp_path, monkeypatch)
    rows = [row(), row(endpoint="Ki"), row(smiles="")]
    if kind == "bad_bytes":
        path.write_bytes(path.read_bytes() + b" ")
    elif kind == "bad_header":
        for r in rows:
            r["target_state_sha256"] = r.pop("target_annotation_sha256")
    elif kind == "unknown_hash":
        digest = "unregistered"
    summary, saved, _ = sidecar(tmp_path, path, digest, rows)
    assert summary["requested_rows"] == 3
    assert summary["evaluated_rows"] == (1 if kind == "valid" else 0)
    assert summary["unsupported_rows"] == (2 if kind == "valid" else 3)
    if kind != "unknown_hash":
        assert all(r["prediction_quantity"] == QUANTITY for r in saved["rows"])
    else:
        assert summary["prediction_scope"] is None
    if kind == "valid":
        assert saved["prediction_scope"] == saved["model"]["prediction_scope"]
        evidence = saved["model"]["checkpoint_evidence_observations"]
        assert evidence["promotion_status"] == "NOT_PROMOTED"
        assert evidence["development_recall_and_average_precision"] is None
    assert all(summary[k] is False for k in (
        "product_ranking_enabled", "customer_execution", "uncertainty_calibrated", "scientific_validation"))


def test_actual_registration_is_endpoint_specific_and_negative_observation_only():
    schema, binding = shadow._registration(ACTUAL)
    assert schema == shadow.BINDINGDB_SCHEMA
    assert binding["endpoint"] == "IC50" and binding["prediction_quantity"] == QUANTITY
    assert binding["manifest_sha256"] == "00b5fc2e017b1f00cb336b5e1747c992b21335ebfbfe88f8c893434f9cecb5c7"
    evidence = shadow._CHECKPOINT_EVIDENCE[ACTUAL]
    assert evidence["promotion_status"] == "NOT_PROMOTED"
    assert evidence["checkpoint_rehashed_for_new_runtime"] is False
    assert evidence["primary_per_compound_measurements_verified"] is False


def test_ic50_actual_htvs_entrypoint_keeps_mapping_command_and_input(tmp_path, monkeypatch):
    from betelgeuze_engine.product.runners import htvs_pipeline as pipeline
    path, digest = checkpoint(tmp_path, monkeypatch)
    _, _, source = sidecar(tmp_path, path, digest, [row(), row(endpoint="Ki"), row()])
    before = source.read_bytes()
    commands = []
    def child(command):
        assert command[1] == "tools/build_ligand_mapping_queue.py"
        commands.append(command)
        return {"ok": False, "synthetic_stop_before_mapping": True}
    monkeypatch.setattr(pipeline, "_run_cmd", child)
    monkeypatch.setattr(pipeline, "_finalize_and_write", lambda _prefix, payload, _args: payload)
    prefix = tmp_path / "htvs"
    base = ["--out-prefix", str(prefix), "--no-single-instance", "--no-auto-heavy-artifacts-root",
            "--no-reuse-stage1-if-exists", "--ligand-csv", str(source)]
    pipeline.run_pipeline(pipeline.build_parser().parse_args(base))
    pipeline.run_pipeline(pipeline.build_parser().parse_args(base + [
        "--public-assay-shadow-enabled", "--public-assay-shadow-checkpoint", str(path),
        "--public-assay-shadow-checkpoint-sha256", digest]))
    assert commands[0] == commands[1] and source.read_bytes() == before
    saved = json.loads((tmp_path / "htvs_public_assay_selector_shadow.json").read_text())
    assert (saved["requested_rows"], saved["evaluated_rows"], saved["unsupported_rows"]) == (3, 2, 1)
    assert [r["predicted_value"] for r in saved["rows"]] == [0., None, 0.]
    assert all(r["prediction_quantity"] == QUANTITY for r in saved["rows"])

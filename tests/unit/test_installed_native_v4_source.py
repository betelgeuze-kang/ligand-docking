"""Bounded FIT-only source parity and adversarial resealing controls."""

from copy import deepcopy
import gzip
import json

import pytest

from betelgeuze_product import installed_native_v4_source as installed
from betelgeuze_product import native_v4_chemical_identity as chemical
from betelgeuze_product import native_v4_receptor as wheel_receptor
from tools.product import public_assay_dataset as common
from tools.product import public_chembl_receptor_intake as checkout

from tests.unit.test_public_chembl_receptor_intake import synthetic_intake


@pytest.fixture
def bounded_source(tmp_path):
    manifest, entries = synthetic_intake.__wrapped__(tmp_path)
    source = tmp_path / "intake"
    checkout.build(manifest["path"], manifest["sha256"], source)
    reference = {
        "schema_version": installed.REFERENCE_SCHEMA,
        "input_dir": str(source),
        "summary_sha256": common.file_sha(source / "summary.json"),
        "phase": "fit",
    }
    return tmp_path, source, reference, entries


def _write_json(path, value):
    path.write_text(json.dumps(value, sort_keys=True, separators=(",", ":")))


def _reseal_source(tmp_path, source, reference, entries, *, context=False):
    metadata_path = tmp_path / "metadata.jsonl"
    metadata_path.write_text("".join(json.dumps(row) + "\n" for row in entries))
    manifest_path = tmp_path / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["metadata_records"]["sha256"] = common.file_sha(metadata_path)
    if context:
        manifest["identity_context"]["sha256"] = common.file_sha(
            tmp_path / "context.jsonl.gz"
        )
    _write_json(manifest_path, manifest)
    summary_path = source / "summary.json"
    summary = json.loads(summary_path.read_text())
    summary["manifest_sha256"] = common.file_sha(manifest_path)
    if context:
        summary["identity_context_sha256"] = manifest["identity_context"]["sha256"]
    _write_json(summary_path, summary)
    return {**reference, "summary_sha256": common.file_sha(summary_path)}


def _rebuild_resealed_source(tmp_path, source, reference, entries):
    resealed = _reseal_source(tmp_path, source, reference, entries)
    manifest_path = tmp_path / "manifest.json"
    rebuilt = tmp_path / "rebuilt-intake"
    checkout.build(str(manifest_path), common.file_sha(manifest_path), rebuilt)
    return {
        **resealed,
        "input_dir": str(rebuilt),
        "summary_sha256": common.file_sha(rebuilt / "summary.json"),
    }


def test_installed_source_exact_checkout_row_parity(bounded_source):
    _, source, reference, _ = bounded_source
    summary = installed.verify_source(reference)
    assert summary["assigned_role_counts"] == {
        "fit": 6, "calibration": 0, "development_test": 1
    }
    assert summary["point_eligible"] == 6
    assert summary["evaluation_labels_read"] == 0
    assert not summary["source_authenticated"]
    assert not summary["model_fit_performed"]
    assert summary["engine_calls"] == 0
    checkout_result = checkout.load_intake(source, reference["summary_sha256"], "fit")
    installed_result = wheel_receptor.load_intake(
        source, reference["summary_sha256"], "fit"
    )
    assert installed_result == checkout_result
    assert all(row["native_activity"] is None for row in installed_result[3]
               if row["assigned_role"] != "fit")


@pytest.mark.parametrize("change", ["metadata", "role", "context", "primary"])
def test_resealed_raw_source_change_rejected(bounded_source, change):
    tmp_path, source, reference, entries = bounded_source
    entries = deepcopy(entries)
    if change == "metadata":
        path = tmp_path / "metadata0.json"
        value = json.loads(path.read_text())
        value["canonical_smiles"] = "C1CCCCC1"
        _write_json(path, value)
        entries[0]["metadata_origin"]["sha256"] = common.file_sha(path)
    elif change == "role":
        path = tmp_path / "role0.json"
        value = json.loads(path.read_text())
        value["assigned_role"] = "calibration"
        _write_json(path, value)
        entries[0]["role_origin"]["sha256"] = common.file_sha(path)
    elif change == "context":
        path = tmp_path / "context.jsonl.gz"
        nodes = [json.loads(line) for line in gzip.decompress(path.read_bytes()).decode().splitlines()]
        nodes[0]["policy_declarations"].append({"evaluation_only": True})
        path.write_bytes(gzip.compress("".join(json.dumps(node) + "\n" for node in nodes).encode(), mtime=0))
    else:
        html = tmp_path / "primary0.html"
        html.write_text(html.read_text().replace("</td></tr>", "0</td></tr>"))
        evidence = tmp_path / "evidence0.json"
        value = json.loads(evidence.read_text())
        value["primary_origin"]["sha256"] = common.file_sha(html)
        _write_json(evidence, value)
        entries[0]["primary_origin"]["sha256"] = common.file_sha(evidence)
    resealed = _reseal_source(
        tmp_path, source, reference, entries, context=change == "context"
    )
    with pytest.raises(ValueError):
        installed.verify_source(resealed)


def test_resealed_cached_row_and_summary_rejected(bounded_source):
    _, source, reference, _ = bounded_source
    rows_path = source / "records.jsonl"
    rows = [json.loads(line) for line in rows_path.read_text().splitlines()]
    rows[0]["native_activity"]["value"] = "9999"
    rows_path.write_text("".join(json.dumps(row) + "\n" for row in rows))
    summary_path = source / "summary.json"
    summary = json.loads(summary_path.read_text())
    summary["records_sha256"] = common.file_sha(rows_path)
    _write_json(summary_path, summary)
    with pytest.raises(ValueError, match="cache_does_not_match"):
        installed.verify_source({
            **reference, "summary_sha256": common.file_sha(summary_path)
        })


@pytest.mark.parametrize("field,value", [
    ("schema_version", "installed_synthetic_prepared_comparison_protocol_v1"),
    ("phase", "evaluation"),
])
def test_old_schema_or_evaluation_phase_rejected(bounded_source, field, value):
    _, _, reference, _ = bounded_source
    with pytest.raises(ValueError, match="unsupported_installed"):
        installed.verify_source({**reference, field: value})


def test_nonfit_activity_origin_rejected_before_value_read(bounded_source):
    tmp_path, source, reference, entries = bounded_source
    entries = deepcopy(entries)
    entries[-1]["activity_origin"] = {
        "path": "/intentionally_missing_protected_source",
        "sha256": "f" * 64,
    }
    resealed = _reseal_source(tmp_path, source, reference, entries)
    with pytest.raises(ValueError, match="evaluation_outcome_in_fit_input"):
        installed.verify_source(resealed)


@pytest.mark.parametrize("location", ["flat", "nested", "wrapper"])
def test_nonfit_metadata_origin_rejects_embedded_outcome(bounded_source, location):
    tmp_path, source, reference, entries = bounded_source
    entries = deepcopy(entries)
    path = tmp_path / "metadata6.json"
    metadata = json.loads(path.read_text())
    if location == "flat":
        metadata["value"] = "SYNTHETIC_EVALUATION_SENTINEL"
    elif location == "nested":
        metadata = {"activity_metadata": {
            **metadata, "value": "SYNTHETIC_EVALUATION_SENTINEL",
        }}
    else:
        metadata = {
            "activity_metadata": metadata,
            "value": "SYNTHETIC_EVALUATION_SENTINEL",
        }
    _write_json(path, metadata)
    entries[-1]["metadata_origin"]["sha256"] = common.file_sha(path)
    poisoned_reference = _rebuild_resealed_source(tmp_path, source, reference, entries)
    with pytest.raises(ValueError, match="outcome_or_nonmetadata_field_in_metadata_origin"):
        installed.verify_source(poisoned_reference)


@pytest.mark.parametrize("origin,name", [
    ("role_origin", "role6.json"),
    ("document_origin", "doc6.json"),
])
def test_nonfit_role_or_document_origin_rejects_embedded_outcome(
    bounded_source, origin, name,
):
    tmp_path, source, reference, entries = bounded_source
    entries = deepcopy(entries)
    path = tmp_path / name
    payload = json.loads(path.read_text())
    payload["value"] = "SYNTHETIC_EVALUATION_SENTINEL"
    _write_json(path, payload)
    entries[-1][origin]["sha256"] = common.file_sha(path)
    poisoned_reference = _rebuild_resealed_source(tmp_path, source, reference, entries)
    with pytest.raises(ValueError, match="outcome_or_nonmetadata_field_in_"):
        installed.verify_source(poisoned_reference)


def test_summary_rejects_embedded_outcome(bounded_source):
    _, source, reference, _ = bounded_source
    path = source / "summary.json"
    summary = json.loads(path.read_text())
    summary["value"] = "SYNTHETIC_EVALUATION_SENTINEL"
    _write_json(path, summary)
    with pytest.raises(ValueError, match="unsupported_installed_native_v4_summary"):
        installed.verify_source({
            **reference,
            "summary_sha256": common.file_sha(path),
        })


def test_rdkit_version_drift_rejects_cached_chemical_identity(bounded_source, monkeypatch):
    _, _, reference, _ = bounded_source
    monkeypatch.setattr(chemical.rdBase, "rdkitVersion", "2026.03.6")
    with pytest.raises(ValueError, match="cache_does_not_match"):
        installed.verify_source(reference)

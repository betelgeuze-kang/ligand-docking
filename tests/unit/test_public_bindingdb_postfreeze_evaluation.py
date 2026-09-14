"""Fresh synthetic post-freeze methods, actual model/CLI and access controls."""
from copy import deepcopy
from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
import zipfile

import pytest

from tools.product import public_assay_dataset as common
from tools.product import public_bindingdb_postfreeze_evaluation as post
from tools.product import public_bindingdb_staged_intake as intake
from tools.product import train_public_bindingdb_staged_selector as trainer

spec = importlib.util.spec_from_file_location("bindingdb_synthetic_source", Path(__file__).with_name("test_public_bindingdb_staged_intake.py"))
source = importlib.util.module_from_spec(spec)
spec.loader.exec_module(source)


def make_data(tmp_path, mapping_mutation=None, evaluation_values=None):
    data = source.fixture(tmp_path / "source")
    root, manifest, manifest_ref, _, plan = data
    if evaluation_values:
        ids = [row["record_id"].split(":")[1] for row in plan["assignments"] if row["role"] != "fit"]
        changes = dict(zip(ids, evaluation_values))
        with zipfile.ZipFile(manifest["archive"]["path"]) as archive:
            lines = archive.read("synthetic.tsv").decode().splitlines()
        column = lines[0].split("\t").index("Ki (nM)")
        for i in range(1, len(lines)):
            cells = lines[i].split("\t")
            if cells[0] in changes:
                cells[column] = changes[cells[0]]
                lines[i] = "\t".join(cells)
        source.rebind_native_bytes(data, ("\n".join(lines) + "\n").encode())
    if mapping_mutation:
        mapping = Path(manifest["assay_mapping"]["path"])
        mapping.write_text(mapping_mutation(mapping.read_text(), plan))
        manifest["assay_mapping"]["sha256"] = common.file_sha(mapping)
    methods = source.rows(root / "methods.jsonl")
    by_role = {row["record_id"]: row["role"] for row in plan["assignments"]}
    for method in methods:
        if mapping_mutation:
            method["source_records"][0]["source_sha256"] = manifest["assay_mapping"]["sha256"]
        if by_role[method["record_id"]] != "fit":
            method.update(status="unknown", reason="Not inspected before freeze", assay_keys=[], source_records=[])
    manifest["assay_method_ledger"] = {**source.dump_rows(root / "methods.jsonl", methods), "endpoint": "Ki"}
    source.refresh_manifest(data)
    fitted_intake = source.build(data)
    trainer.fit(input_dir=root / "intake", summary_sha256=common.file_sha(root / "intake/summary.json"), output_dir=root / "model")
    frozen = root / "model/frozen-fit.json"
    assert fitted_intake["labels_withheld"] == 18
    return data, frozen


def capture(data, frozen):
    root, _, ref, _, _ = data
    post.capture_methods(manifest_path=ref["path"], manifest_sha256=ref["sha256"], frozen_fit=frozen,
                         frozen_fit_sha256=common.file_sha(frozen), output_dir=root / "capture")
    return root / "capture/method-capture.json"


def review(path):
    captured = json.loads(path.read_text())
    rows = []
    for rid, assays in json.loads(Path(captured["methods"]["path"]).read_text()).items():
        origins = [{k: item[k] for k in ("source_sha256", "source_member", "source_line")}
                   for assay in assays for item in [assay["mapping_source"], *assay["description_records"]]]
        rows.append({"record_id": rid, "status": "compatible", "reason": "Fresh synthetic method positive control",
                     "assay_keys": [a["entry_assay_id"] for a in assays], "source_records": origins})
    payload = {"schema_version": post.REVIEW_SCHEMA, "capture": {"path": str(path), "sha256": common.file_sha(path)},
               "reviewed_at_utc": datetime.now(timezone.utc).isoformat(), "basis": "internal_development_method_review", "methods": rows}
    output = path.parent / "review.json"
    source.dump(output, payload)
    return output


def evaluate(path, review_path):
    return post.evaluate(capture_path=path, capture_sha256=common.file_sha(path), review_path=review_path,
                         review_sha256=common.file_sha(review_path), output_dir=path.parent.parent / "evaluation")


def forbid_values(*args, **kwargs):
    raise AssertionError("native evaluation values reached before validation")


def test_unknown_at_fit_becomes_reviewed_only_after_freeze(tmp_path):
    data, frozen = make_data(tmp_path)
    model = data[0] / "model/selector.json"
    before = {str(p): common.file_sha(p) for p in [model, frozen, Path(data[2]["path"])]}
    path = capture(data, frozen)
    result = evaluate(path, review(path))
    assert {role: m["exact_supported_rows"] for role, m in result["evaluations"].items()} == {"calibration": 9, "development_test": 9}
    assert result["native_access"]["full_rows_decoded"] == 18
    assert result["requested_target_rows"] == 60 and result["fit_changed"] is False
    assert result["training_executed"] is False and result["full_requested_recall"] is None
    assert before == {name: common.file_sha(Path(name)) for name in before}
    records = source.rows(data[0] / "evaluation/records.jsonl")
    assert all(r["native_bindingdb_row"] is None for r in records if r["assigned_role"] == "fit")
    assert all(r["potential_energy"] is None and r["force_labels"] is None for r in records)


def test_legacy_method_ledger_rewrite_is_rejected_before_values(tmp_path, monkeypatch):
    data, frozen = make_data(tmp_path)
    path = capture(data, frozen)
    reviewed = json.loads(review(path).read_text())
    root, manifest, _, _, _ = data
    original_methods = source.rows(root / "methods.jsonl")
    replacements = {r["record_id"]: r for r in reviewed["methods"]}
    manifest = deepcopy(manifest)
    manifest["assay_method_ledger"] = {**source.dump_rows(root / "rewritten-methods.jsonl",
        [replacements.get(r["record_id"], r) for r in original_methods]), "endpoint": "Ki"}
    changed = source.dump(root / "rewritten-manifest.json", manifest)
    monkeypatch.setattr(intake, "native_rows", forbid_values)
    with pytest.raises(ValueError, match="incompatible_frozen_bindingdb_fit"):
        intake.build(manifest_path=changed["path"], manifest_sha256=changed["sha256"], phase="evaluation",
                     frozen_fit=frozen, frozen_fit_sha256=common.file_sha(frozen), output_dir=root / "legacy-evaluation")


def test_bad_frozen_predictions_prevent_method_capture(tmp_path, monkeypatch):
    data, frozen = make_data(tmp_path)
    payload = json.loads(frozen.read_text())
    prediction_path = Path(payload["predictions"]["path"])
    predictions = source.rows(prediction_path)
    predictions[0]["predicted"] += 1
    payload["predictions"] = source.dump_rows(prediction_path, predictions)
    source.dump(frozen, payload)
    monkeypatch.setattr(post, "method_sources", forbid_values)
    with pytest.raises(ValueError, match="prediction_checkpoint"):
        capture(data, frozen)


@pytest.mark.parametrize("change", ["body", "time", "access", "implementation"])
def test_rehashed_capture_rejected_before_values(tmp_path, monkeypatch, change):
    data, frozen = make_data(tmp_path)
    path = capture(data, frozen)
    review_path = review(path)
    payload = json.loads(path.read_text())
    if change == "body":
        body_path = Path(payload["methods"]["path"])
        body = json.loads(body_path.read_text())
        next(iter(body.values()))[0]["description_records"][0]["row"]["DESCRIPTION"] = "Rewritten method"
        payload["methods"] = source.dump(body_path, body)
    elif change == "time":
        payload["captured_at_utc"] = "2000-01-01T00:00:00+00:00"
    elif change == "access":
        payload["evaluation_values_read"] = 1
    else:
        payload["implementation_hashes"]["postfreeze_adapter"] = "0" * 64
    source.dump(path, payload)
    monkeypatch.setattr(intake, "native_rows", forbid_values)
    with pytest.raises(ValueError):
        evaluate(path, review_path)


@pytest.mark.parametrize("change", ["fit_id", "duplicate", "missing", "origin", "capture", "timestamp", "external_review_claim"])
def test_review_binding_and_complete_coverage_before_values(tmp_path, monkeypatch, change):
    data, frozen = make_data(tmp_path)
    path = capture(data, frozen)
    review_path = review(path)
    payload = json.loads(review_path.read_text())
    if change == "fit_id":
        payload["methods"][0]["record_id"] = next(r["record_id"] for r in data[4]["assignments"] if r["role"] == "fit")
    elif change == "duplicate":
        payload["methods"].append(deepcopy(payload["methods"][0]))
    elif change == "missing":
        payload["methods"].pop()
    elif change == "origin":
        payload["methods"][0]["source_records"][0]["source_line"] += 1
    elif change == "capture":
        payload["capture"]["sha256"] = "0" * 64
    elif change == "timestamp":
        payload["reviewed_at_utc"] = "2000-01-01T00:00:00+00:00"
    else:
        payload["basis"] = "external_independent_approval"
    source.dump(review_path, payload)
    monkeypatch.setattr(intake, "native_rows", forbid_values)
    with pytest.raises(ValueError):
        evaluate(path, review_path)


def test_unknown_method_retained_in_denominator(tmp_path):
    data, frozen = make_data(tmp_path)
    path = capture(data, frozen)
    review_path = review(path)
    payload = json.loads(review_path.read_text())
    payload["methods"][0].update(status="unknown", reason="Fresh unknown-method negative control")
    source.dump(review_path, payload)
    result = evaluate(path, review_path)
    assert sum(r["requested_preassigned_rows"] for r in result["evaluations"].values()) == 18
    assert sum(r["exact_supported_rows"] for r in result["evaluations"].values()) == 17
    assert sum(r["unsupported_or_failed_labels"] for r in result["evaluations"].values()) == 1


def test_zero_censored_and_missing_are_not_negative_labels(tmp_path):
    data, frozen = make_data(tmp_path, evaluation_values=["0", ">100", ""])
    path = capture(data, frozen)
    result = evaluate(path, review(path))
    assert sum(r["requested_preassigned_rows"] for r in result["evaluations"].values()) == 18
    assert sum(r["exact_supported_rows"] for r in result["evaluations"].values()) == 15
    ledger = source.rows(data[0] / "evaluation/evaluation-ledger.jsonl")
    bad = [r for r in ledger if not r["eligible_for_point_model"]]
    assert len(bad) == 3 and all(r["issues"] for r in bad)
    assert result["full_requested_recall"] is None


def test_bad_frozen_capture_header_cannot_open_body(tmp_path, monkeypatch):
    data, frozen = make_data(tmp_path)
    path = capture(data, frozen)
    review_path = review(path)
    payload = json.loads(path.read_text())
    payload["frozen_fit"]["sha256"] = "0" * 64
    source.dump(path, payload)
    original = post.bound.bound_json
    def watched(entry):
        assert entry["path"] != payload["methods"]["path"], "unverified method body accessed"
        return original(entry)
    monkeypatch.setattr(post.bound, "bound_json", watched)
    monkeypatch.setattr(intake, "native_rows", forbid_values)
    with pytest.raises(ValueError):
        evaluate(path, review_path)


@pytest.mark.parametrize("unknown", [False, True])
def test_new_assay_identity_bridge_fails_before_description(tmp_path, monkeypatch, unknown):
    def mutate(text, plan):
        fit = next(r for r in plan["assignments"] if r["role"] == "fit")["record_id"].split(":")[1]
        evaluation = next(r for r in plan["assignments"] if r["role"] == "calibration")["record_id"].split(":")[1]
        if unknown:
            return text + f"999999\t{evaluation}_1\n"
        return text.replace(f"{evaluation}\t{evaluation}_1\n", f"{evaluation}\t{fit}_1\n")
    data, frozen = make_data(tmp_path, mutate)
    monkeypatch.setattr(intake, "phase_assays", forbid_values)
    with pytest.raises(ValueError, match="assay_link|assay_linked_record"):
        capture(data, frozen)


def test_actual_cli_capture_and_evaluate(tmp_path):
    data, frozen = make_data(tmp_path)
    root, _, ref, _, _ = data
    post.main(["capture-methods", "--manifest", ref["path"], "--manifest-sha256", ref["sha256"],
               "--frozen-fit", str(frozen), "--frozen-fit-sha256", common.file_sha(frozen), "--output-dir", str(root / "capture")])
    path = root / "capture/method-capture.json"
    review_path = review(path)
    post.main(["evaluate", "--capture", str(path), "--capture-sha256", common.file_sha(path),
               "--review", str(review_path), "--review-sha256", common.file_sha(review_path), "--output-dir", str(root / "evaluation")])
    assert json.loads((root / "evaluation/summary.json").read_text())["schema_version"] == post.EVALUATION_SCHEMA

"""Fresh synthetic source-native BindingDB phase and fixed-role controls."""
from __future__ import annotations

from copy import deepcopy
import json
import os
from pathlib import Path
import subprocess
import sys
import zipfile

import pytest

from tools.product import public_assay_components as components
from tools.product import public_assay_dataset as common
from tools.product import public_bindingdb_staged_intake as intake
from tools.product import train_public_assay_selector as existing
from tools.product import train_public_bindingdb_staged_selector as trainer


def dump(path, value):
    path.write_text(common.json_text(value) + "\n")
    return {"path": str(path), "sha256": common.file_sha(path)}


def dump_rows(path, rows):
    path.write_text("".join(common.json_text(row) + "\n" for row in rows))
    return {"path": str(path), "sha256": common.file_sha(path)}


def native_zip(path, header, rows):
    lines = ["\t".join(header).encode()]
    for row in rows:
        lines.append(b"\t".join(value if isinstance(value, bytes) else value.encode() for value in row))
    with zipfile.ZipFile(path, "w") as archive:
        info = zipfile.ZipInfo("synthetic.tsv", (2020, 1, 1, 0, 0, 0))
        archive.writestr(info, b"\n".join(lines) + b"\n")
    return {"path": str(path), "sha256": common.file_sha(path), "member": "synthetic.tsv", "expected_rows": len(rows)}


def fixture(root, value="100", *, mutate=None, duplicate_unselected=False):
    """Sixty fresh, distinct acyclic scaffold/document components, no external data."""
    root.mkdir()
    raws = [{"BindingDB Reactant_set_id": str(i + 1), "BindingDB MonomerID": str(1000 + i),
             "Ligand SMILES": "C" * (5 + i), "Ligand InChI Key": "", "Target Name": "synthetic catalogue target",
             "Target Source Organism According to Curator or DataSource": "synthetic",
             common.CHAIN_COUNT: "1", "BindingDB Target Chain Sequence 1": "ACDEFG",
             "UniProt (SwissProt) Primary ID of Target Chain 1": "SYNTHETIC",
             "Curation/DataSource": "BindingDB", "Article DOI": f"10.99999/synthetic-{i}",
             "Date of publication": "2020", "Ki (nM)": value,
             "IC50 (nM)": "", "Kd (nM)": "", "pH": "", "Temp (C)": ""} for i in range(60)]
    if mutate:
        mutate(raws)
    if duplicate_unselected:
        for i in range(2):
            extra = deepcopy(raws[-1])
            extra.update({"BindingDB Reactant_set_id": "999", "BindingDB MonomerID": "1999",
                          "Ligand SMILES": "C" * 65, "Article DOI": "10.99999/duplicate"})
            raws.append(extra)
    header = list(raws[0])
    archive = native_zip(root / "source.zip", header, [[row.get(key, "") for key in header] for row in raws])
    metadata = []
    for line, raw in enumerate(raws, 2):
        projected = {key: val for key, val in raw.items() if intake.metadata_field(key)}
        metadata.append({"record_id": "bindingdb:" + raw["BindingDB Reactant_set_id"],
                         "ligand_id": "bindingdb:" + raw["BindingDB MonomerID"],
                         "identity_context_node_id": "source:" + str(line),
                         "chemical_identity": common.chemical_identity(raw["Ligand SMILES"]),
                         "source_provenance": {"source_sha256": archive["sha256"], "source_member": archive["member"],
                                               "source_line": line, "row": projected}})
    meta_entry = dump_rows(root / "metadata.jsonl", metadata)
    context = [components.normalized_node(row) for row in metadata]
    context_entry = {**dump_rows(root / "context.jsonl", context), "expected_nodes": len(context)}
    selected = metadata[:60]
    splits, group_ids = existing.split_components(selected, 17, identity_context=context)
    plan = {"schema_version": intake.PLAN_SCHEMA, "seed": 17,
            "metadata_sha256": meta_entry["sha256"], "identity_context_sha256": context_entry["sha256"],
            "splitter_sha256": common.file_sha(Path(existing.__file__)),
            "component_implementation_sha256": common.file_sha(Path(components.__file__)),
            "counts": {role: len(indices) for role, indices in splits.items()},
            "assignments": [{"record_id": selected[i]["record_id"],
                             "identity_context_node_id": selected[i]["identity_context_node_id"],
                             "component_id": group_ids[i], "role": role} for role, indices in splits.items() for i in indices]}
    plan_entry = dump(root / "plan.json", plan)
    mapping = root / "mapping.tsv"
    mapping.write_text("REACTANT_SET_ID\tENTRYID_ASSAYID\n" + "".join(f"{i+1}\t{i+1}_1\n" for i in range(60)))
    descriptions = root / "descriptions.tsv"
    descriptions.write_text("ENTRYID\tASSAYID\tDESCRIPTION\n" + "".join(f"{i+1}\t1\tSynthetic biochemical assay methods only.\n" for i in range(60)))
    map_entry = {"path": str(mapping), "sha256": common.file_sha(mapping)}
    desc_entry = {"path": str(descriptions), "sha256": common.file_sha(descriptions)}
    methods = [{"record_id": row["record_id"], "status": "compatible", "reason": "fresh synthetic positive control",
                "assay_keys": [f"{i+1}_1"],
                "source_records": [{"source_sha256": entry["sha256"], "source_member": Path(entry["path"]).name,
                                    "source_line": i + 2} for entry in (map_entry, desc_entry)]}
               for i, row in enumerate(selected)]
    method_entry = {**dump_rows(root / "methods.jsonl", methods), "endpoint": "Ki"}
    target = common.target_state_identity(raws[0])
    manifest = {"schema_version": intake.MANIFEST_SCHEMA, "archive": archive, "normalized_metadata": meta_entry,
                "identity_context": context_entry, "split_plan": plan_entry, "assay_mapping": map_entry,
                "assay_descriptions": desc_entry, "assay_method_ledger": method_entry,
                "requested_target_rows": len(metadata),
                "scope": {"endpoint": "Ki", "source_origins": ["BindingDB"], "source_license": "CC-BY-4.0",
                          "target_annotation": target, "target_annotation_sha256": common.digest(common.json_text(target)),
                          "physical_target_state_verified": False, "positive_threshold_negative_log10_molar": 6.0,
                          "top_fraction": 0.2, "chemistry_scope": {"heavy_atoms_min": 5, "heavy_atoms_max": 70,
                          "fragment_count": 1, "elements": ["H", "C", "N", "O", "F", "P", "S", "Cl", "Br", "I"],
                          "formal_charge_abs_max": 2, "radical_electrons": 0, "isotope_atoms": 0}}}
    manifest_entry = dump(root / "manifest.json", manifest)
    return root, manifest, manifest_entry, metadata, plan


def build(data, suffix="intake", phase="fit", **kwargs):
    root, _, ref, _, _ = data
    return intake.build(manifest_path=ref["path"], manifest_sha256=ref["sha256"], phase=phase,
                        output_dir=root / suffix, **kwargs)


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def refresh_manifest(data):
    data[2].update(dump(Path(data[2]["path"]), data[1]))


def rebind_native_bytes(data, raw_bytes):
    root, manifest, _, metadata, plan = data
    with zipfile.ZipFile(root / "source.zip", "w") as archive:
        archive.writestr("synthetic.tsv", raw_bytes)
    manifest["archive"]["sha256"] = common.file_sha(root / "source.zip")
    for row in metadata:
        row["source_provenance"]["source_sha256"] = manifest["archive"]["sha256"]
    manifest["normalized_metadata"] = dump_rows(root / "metadata.jsonl", metadata)
    context = [components.normalized_node(row) for row in metadata]
    manifest["identity_context"] = {**dump_rows(root / "context.jsonl", context), "expected_nodes": len(context)}
    plan["metadata_sha256"] = manifest["normalized_metadata"]["sha256"]
    plan["identity_context_sha256"] = manifest["identity_context"]["sha256"]
    manifest["split_plan"] = dump(root / "plan.json", plan)
    refresh_manifest(data)


@pytest.mark.parametrize("value", ["", ">100", "NaN", "0", "-2", "1000000000"])
def test_observation_changes_cannot_move_metadata_roles(tmp_path, value):
    original = fixture(tmp_path / "a")
    variant = fixture(tmp_path / "b", value=value)
    left = intake.load_metadata(original[2]["path"], original[2]["sha256"])[1]["assignments"]
    right = intake.load_metadata(variant[2]["path"], variant[2]["sha256"])[1]["assignments"]
    assert left == right
    summary = build(variant)
    assert summary["assigned_role_counts"] == original[4]["counts"]
    assert summary["labels_retrieved"] == original[4]["counts"]["fit"]
    assert all(r["native_bindingdb_row"] is None for r in rows(variant[0] / "intake/records.jsonl") if r["assigned_role"] != "fit")


def test_measured_log_zero_retained_and_nonpositive_concentration_rejected(tmp_path):
    data = fixture(tmp_path / "valid", value="1000000000")
    build(data)
    fit_rows = [r for r in rows(data[0] / "intake/records.jsonl") if r["assigned_role"] == "fit"]
    assert all(r["eligible_for_point_model"] and r["observation"]["negative_log10_molar"] == 0.0 for r in fit_rows)
    invalid = common.measurement("0", "Ki")
    assert invalid["value_nm"] == 0.0 and invalid["negative_log10_molar"] is None
    assert invalid["status"] == "nonpositive_or_nonfinite_assay_concentration"


def test_fit_does_not_decode_wrong_phase_outcomes_or_description_bodies(tmp_path):
    data = fixture(tmp_path / "phase")
    root, manifest, _, _, plan = data
    ids = {a["record_id"].split(":")[1] for a in plan["assignments"] if a["role"] != "fit"}
    with zipfile.ZipFile(root / "source.zip") as archive:
        lines = archive.read("synthetic.tsv").splitlines()
    header = lines[0].decode().split("\t")
    ki = header.index("Ki (nM)")
    for index in range(1, len(lines)):
        cells = lines[index].split(b"\t")
        if cells[0].decode() in ids:
            cells[ki] = b"\xff\xfe"
        lines[index] = b"\t".join(cells)
    rebind_native_bytes(data, b"\n".join(lines) + b"\n")
    description = Path(manifest["assay_descriptions"]["path"])
    lines = description.read_bytes().splitlines()
    lines = [line.rsplit(b"\t", 1)[0] + b"\t\xff\xfe" if line.split(b"\t")[0].decode() in ids else line for line in lines]
    description.write_bytes(b"\n".join(lines) + b"\n")
    manifest["assay_descriptions"]["sha256"] = common.file_sha(description)
    methods = rows(Path(manifest["assay_method_ledger"]["path"]))
    for method in methods:
        method["source_records"][1]["source_sha256"] = manifest["assay_descriptions"]["sha256"]
    manifest["assay_method_ledger"] = {**dump_rows(root / "methods.jsonl", methods), "endpoint": "Ki"}
    refresh_manifest(data)
    summary = build(data)
    assert summary["access"]["full_rows_decoded"] == plan["counts"]["fit"]
    assert summary["access"]["assay_metadata_access"]["description_full_rows_decoded"] == plan["counts"]["fit"]


@pytest.mark.parametrize("change", ["duplicate", "extra", "missing"])
def test_native_record_id_preflight_rejects_before_outcomes(tmp_path, monkeypatch, change):
    data = fixture(tmp_path / "bad")
    with zipfile.ZipFile(data[0] / "source.zip") as archive:
        lines = archive.read("synthetic.tsv").splitlines()
    if change == "duplicate":
        lines.append(lines[1])
        data[1]["archive"]["expected_rows"] += 1
    elif change == "extra":
        lines[1] = b"99999\t" + lines[1].partition(b"\t")[2]
    else:
        lines.pop()
    rebind_native_bytes(data, b"\n".join(lines) + b"\n")
    monkeypatch.setattr(common, "normalize_record", lambda *a, **kw: pytest.fail("outcome normalizer reached"))
    with pytest.raises(ValueError, match="identifier_mismatch|missing_or_duplicate|row_count|source_graph_coverage"):
        build(data)


def test_duplicate_unselected_all_occurrences_retained_in_exclusion_ledger(tmp_path):
    data = fixture(tmp_path / "duplicates", duplicate_unselected=True)
    result = build(data)
    ledger = rows(data[0] / "intake/ledger.jsonl")
    duplicates = [row for row in ledger if row["record_id"] == "bindingdb:999"]
    assert len(duplicates) == 2 and all(row["status"] == "duplicate_record_all_occurrences_excluded" for row in duplicates)
    assert result["requested_target_rows"] == 62 and result["metadata_selected_rows"] == 60
    assert len(rows(data[0] / "intake/identity-context.jsonl")) == 62


def test_reserved_graph_rejected_before_source_read(tmp_path, monkeypatch):
    data = fixture(tmp_path / "reserved")
    root, manifest, _, _, plan = data
    context = rows(root / "context.jsonl")
    context[0]["protected"] = True
    manifest["identity_context"] = {**dump_rows(root / "context.jsonl", context), "expected_nodes": len(context)}
    plan["identity_context_sha256"] = manifest["identity_context"]["sha256"]
    manifest["split_plan"] = dump(root / "plan.json", plan)
    refresh_manifest(data)
    monkeypatch.setattr(intake, "native_rows", lambda *a, **kw: pytest.fail("native reader reached"))
    with pytest.raises(ValueError, match="reserved_metadata_component"):
        build(data)


def test_full_source_graph_bridge_cannot_be_omitted_at_same_context_count(tmp_path, monkeypatch):
    data = fixture(tmp_path / "bridge", duplicate_unselected=True)
    root, manifest, _, _, plan = data
    context = rows(root / "context.jsonl")
    # Keep valid target coverage, but replace one original source vertex with
    # an extra external alias of another row: count alone must not admit it.
    context[-1]["node_id"] = "external:renamed-source"
    manifest["identity_context"] = {**dump_rows(root / "context.jsonl", context), "expected_nodes": len(context)}
    plan["identity_context_sha256"] = manifest["identity_context"]["sha256"]
    manifest["split_plan"] = dump(root / "plan.json", plan)
    refresh_manifest(data)
    # Metadata coverage also catches the vanished source ID; exercise native
    # coverage directly to isolate full-archive guard from selected coverage.
    loaded_context = rows(root / "context.jsonl")
    monkeypatch.setattr(common, "normalize_record", lambda *a, **kw: pytest.fail("normalizer reached"))
    with pytest.raises(ValueError, match="full_native_source_graph_coverage_mismatch"):
        intake.native_rows(manifest, data[3][:60], data[3][:60], plan, "fit", loaded_context)


@pytest.mark.parametrize("field", ["role", "dataset_split", "evaluation_only"])
def test_original_auxiliary_policy_rejected_before_outcome_decode(tmp_path, monkeypatch, field):
    data = fixture(tmp_path / "policy")
    root, manifest, _, _, plan = data
    eval_id = next(a["record_id"].split(":")[1] for a in plan["assignments"] if a["role"] != "fit")
    path = Path(manifest["assay_descriptions"]["path"])
    lines = path.read_text().splitlines()
    lines[0] += "\t" + field
    for i in range(1, len(lines)):
        value = ("true" if field == "evaluation_only" else "test") if lines[i].split("\t")[0] == eval_id else ""
        lines[i] += "\t" + value
    path.write_text("\n".join(lines) + "\n")
    manifest["assay_descriptions"]["sha256"] = common.file_sha(path)
    refresh_manifest(data)
    monkeypatch.setattr(intake, "native_rows", lambda *a, **kw: pytest.fail("native outcomes reached"))
    with pytest.raises(ValueError, match="reserved_or_unknown_assay_source_policy"):
        build(data)


def test_endpoint_method_binding_and_wrong_phase_rejected(tmp_path):
    data = fixture(tmp_path / "endpoint")
    data[1]["assay_method_ledger"]["endpoint"] = "IC50"
    refresh_manifest(data)
    with pytest.raises(ValueError, match="assay_method_ledger_endpoint_mismatch"):
        build(data)
    data[1]["assay_method_ledger"]["endpoint"] = "Ki"
    refresh_manifest(data)
    with pytest.raises(ValueError, match="frozen_predictions_required"):
        build(data, phase="evaluation")


@pytest.mark.parametrize("tamper", ["eligibility", "zero_label", "summary", "extra_record", "wrong_phase", "training_claim"])
def test_rehashed_cached_fields_do_not_override_native_source(tmp_path, tamper):
    data = fixture(tmp_path / "cache")
    result = build(data)
    folder = data[0] / "intake"
    cached = rows(folder / "records.jsonl")
    if tamper == "summary":
        result["labels_retrieved"] -= 1
    elif tamper == "training_claim":
        result["training_executed"] = True
    elif tamper == "extra_record":
        cached.append(deepcopy(cached[0]))
        cached[-1]["record_id"] = "bindingdb:extra"
    elif tamper == "wrong_phase":
        next(r for r in cached if r["assigned_role"] != "fit")["native_bindingdb_row"] = {"Ki (nM)": "1"}
    else:
        row = next(r for r in cached if r["assigned_role"] == "fit")
        if tamper == "eligibility":
            row["eligible_for_point_model"] = False
        else:
            row["observation"]["negative_log10_molar"] = 0.0
    result["records_sha256"] = dump_rows(folder / "records.jsonl", cached)["sha256"]
    ref = dump(folder / "summary.json", result)
    with pytest.raises(ValueError, match="cached_.*does_not_match_native_source"):
        intake.load_intake(folder, ref["sha256"], "fit")


def test_unknown_method_excludes_with_original_role_and_source_vertices(tmp_path):
    data = fixture(tmp_path / "method")
    methods = rows(data[0] / "methods.jsonl")
    for item in methods:
        item["status"] = "unknown"
    data[1]["assay_method_ledger"] = {**dump_rows(data[0] / "methods.jsonl", methods), "endpoint": "Ki"}
    refresh_manifest(data)
    result = build(data)
    assert not result["eligible_role_counts"]
    assert result["assigned_role_counts"] == data[4]["counts"]
    with pytest.raises(ValueError, match="insufficient_supported_fit"):
        trainer.fit(input_dir=data[0] / "intake", summary_sha256=common.file_sha(data[0] / "intake/summary.json"), output_dir=data[0] / "fit")


def test_real_module_cli_fit_freeze_then_evaluate(tmp_path):
    data = fixture(tmp_path / "modules", value="1000000000")
    root, _, ref, _, plan = data
    candidate = Path(intake.__file__).resolve().parents[2]
    env = dict(os.environ, PYTHONPATH=str(candidate), OPENBLAS_NUM_THREADS="1", OMP_NUM_THREADS="1")
    def run(module, args):
        # Python 3.10 has no -P: remove only implicit cwd, then execute the
        # actual module main/argparse from the explicitly bound PYTHONPATH.
        launcher = f'import sys,runpy; sys.path.pop(0); runpy.run_module("tools.product.{module}", run_name="__main__")'
        command = [sys.executable, "-c", launcher, *map(str, args)]
        result = subprocess.run(command, capture_output=True, text=True, env=env, cwd=os.getcwd())
        n = len(list(root.glob("command-*.json")))
        dump(root / f"command-{n}.json", {"command": command, "cwd": os.getcwd(), "exit_code": result.returncode,
             "PYTHONPATH": str(candidate), "python": sys.version})
        (root / f"command-{n}.stdout.log").write_text(result.stdout)
        (root / f"command-{n}.stderr.log").write_text(result.stderr)
        assert result.returncode == 0, result.stderr
    run("public_bindingdb_staged_intake", ["--manifest", ref["path"], "--manifest-sha256", ref["sha256"],
        "--phase", "fit", "--output-dir", root / "intake"])
    run("train_public_bindingdb_staged_selector", ["--phase", "fit", "--input-dir", root / "intake",
        "--summary-sha256", common.file_sha(root / "intake/summary.json"), "--output-dir", root / "model"])
    frozen = root / "model/frozen-fit.json"
    checkpoint = json.loads((root / "model/selector.json").read_text())
    assert checkpoint["features"] == trainer.FEATURES
    assert checkpoint["features"]["target_encoding"] == "one_catalogue_target_annotation_per_model_not_physical_state"
    frozen_sha = common.file_sha(frozen)
    saved = rows(root / "model/predictions-before-evaluation-labels.jsonl")
    assert len(saved) == 60 and all(r["predicted"] == 0.0 and r["mean_baseline"] == 0.0 for r in saved)
    run("public_bindingdb_staged_intake", ["--manifest", ref["path"], "--manifest-sha256", ref["sha256"],
        "--phase", "evaluation", "--output-dir", root / "eval-intake", "--frozen-fit", frozen,
        "--frozen-fit-sha256", frozen_sha])
    run("train_public_bindingdb_staged_selector", ["--phase", "evaluation", "--input-dir", root / "eval-intake",
        "--summary-sha256", common.file_sha(root / "eval-intake/summary.json"), "--output-dir", root / "evaluation"])
    result = json.loads((root / "evaluation/summary.json").read_text())
    eval_records = rows(root / "eval-intake/records.jsonl")
    for record in eval_records:
        if record["assigned_role"] != "fit":
            native = record["normalized_native"]
            assert native["dataset_split"] == record["assigned_role"]
            assert common.declared_evaluation_only(native) and common.declared_evaluation_only(record)
            assert native["eligible_for_split_assignment"] is False
            assert "dataset_split" not in native["source_provenance"]["row"]
    assert result["requested_target_rows"] == 60 and not result["customer_execution"]
    assert common.file_sha(frozen) == frozen_sha
    for role in ("calibration", "development_test"):
        assert result["evaluations"][role]["exact_supported_rows"] == plan["counts"][role]
        assert result["evaluations"][role]["morgan_ridge"]["rmse"] == 0.0
    # A rehashed forged frozen prediction must fail before evaluation source reading.
    frozen_payload = json.loads(frozen.read_text())
    saved[0]["predicted"] = 123.0
    frozen_payload["predictions"] = dump_rows(root / "forged-predictions.jsonl", saved)
    forged = dump(root / "forged-frozen.json", frozen_payload)
    with pytest.raises(ValueError, match="frozen_prediction_checkpoint_mismatch"):
        build(data, suffix="bad-eval", phase="evaluation", frozen_fit=forged["path"], frozen_fit_sha256=forged["sha256"])

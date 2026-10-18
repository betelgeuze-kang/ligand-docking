"""Tiny synthetic files exercise plan admission without opening research inputs."""
import copy
import hashlib
import json
import os
from pathlib import Path
import uuid

import pytest

from tools.pfk_paired_water_eight_dof import protocol as p


def put(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True) + "\n")
    return p.hash_file(path)


@pytest.fixture
def synthetic_plan(tmp_path):
    archive = tmp_path / "archive"
    roots = {"dry": str(archive / "dry"), "heldout": str(archive / "heldout"),
             "water": str(tmp_path / "water")}
    nested_refs = []
    for index in range(16):
        path = Path(roots["dry"]) / "snapshot/evidence/PFKFB3" / (str(index) + "-source.json")
        checksum = put(path, {"opaque_source": index, "historical_path": "/unavailable/opaque/provenance"})
        nested_refs.append({"path": "/unavailable/cloud/snapshot/evidence/PFKFB3/" + path.name, "sha256": checksum})
    source_evidence = {"schema_version": "declared_prepared_source_evidence/1.0.0",
                       "evidence_kind": "prepared_real_development", "source_authenticated": False,
                       "original_simulation_hamiltonian_reproduced": False, "source_files": nested_refs}
    inputs = {}
    for name in p.INPUT_NAMES:
        path = Path(roots["dry"]) / "snapshot/inputs/PFKFB3" / (name + ".json")
        checksum = put(path, source_evidence if name == "source_evidence" else {"synthetic": name})
        inputs[name] = {"path": "/unavailable/cloud/" + name + ".json", "sha256": checksum}
    original = {**inputs, "boundary": {key: p.BOUNDARY[key] for key in (
        "independent_measurement_denominator", "source_authenticated", "scientifically_validated",
        "training_admitted", "product_ranking_enabled", "original_simulation_hamiltonian_reproduced")},
        "accepted_step_budget": 600, "solver": {"force_tolerance": .001}}
    put(Path(roots["dry"]) / "start/protocol.json", original)
    put(Path(roots["dry"]) / "start/chart-contracts.json", {"P0": "synthetic"})
    put(Path(roots["heldout"]) / "start/chart-contracts.json", {"Qplus": "synthetic", "Qminus": "synthetic"})
    checkpoint_path = Path(roots["water"]) / "runs/optimization/final-checkpoint.json"
    state_sha = "c" * 64
    checkpoint_sha = put(checkpoint_path, {"state_sha256": state_sha,
        "solver_status": "current_global_world_torque_converged", "extra_final_objectives": 0,
        "weights_applied": False, "state": {"synthetic": True}})
    receipts = []
    for index, root in enumerate((archive, Path(roots["water"]))):
        paths = sorted(root.rglob("*.json"))
        rows = []
        for path in paths:
            member = str(path.relative_to(root))
            if index == 1:
                member = root.name + "/" + member
            rows.append({"member" if index == 0 else "source_path": member,
                         "sha256": p.hash_file(path), "bytes": path.stat().st_size})
        receipt_path = tmp_path / ("receipt" + str(index) + ".json")
        put(receipt_path, {"restored_parent" if index == 0 else "restored_root": str(root),
                           "regular_files_verified": len(rows), "files": rows})
        receipts.append(str(receipt_path))
    files, closures = p._receipt_sources(receipts)
    for path in receipts:
        files[path] = p.hash_file(path)
    own_root = tmp_path / "own"
    own_files = {}
    for relative in ("tools/pfk_paired_water_eight_dof/protocol.py", "tools/run_pfk_paired_water_eight_dof.py"):
        path = own_root / relative
        own_files[str(path)] = put(path, {"synthetic_source": relative})
    files.update(own_files)
    reference_path = tmp_path / "reference.json"
    reference = {"path": str(reference_path), "sha256": put(reference_path, {"synthetic": True})}
    relocated_path = tmp_path / "relocated.json"
    evidence_document, original_evidence, nested_records = p._relocated_source_evidence(roots, files)
    derived_path = tmp_path / "relocated-source-evidence.json"
    derived_evidence = {"path": str(derived_path), "sha256": put(derived_path, evidence_document)}
    files[str(derived_path)] = derived_evidence["sha256"]
    protocol = {"path": str(relocated_path), "sha256": put(
        relocated_path, p._relocated_protocol(roots, files, source_evidence_binding=derived_evidence))}
    metric_path = tmp_path / "metrics-policy.json"
    metrics = {"path": str(metric_path), "sha256": put(metric_path, {**p.METRICS_POLICY, "reference": reference})}
    structural_path = tmp_path / "structural-policy-inputs.json"
    structural = {"path": str(structural_path), "sha256": put(structural_path, {"synthetic": True})}
    for binding in (reference, protocol, metrics, structural):
        files[binding["path"]] = binding["sha256"]
    plan = {"schema": p.SCHEMA, "run_id": str(uuid.uuid4()), "source_roots": roots,
            "protocol": protocol, "reference": reference, "metrics_policy": metrics, "structural_policy": structural,
            "source_evidence_relocation": p._relocation_record(original_evidence, derived_evidence, nested_records),
            "water_checkpoint": {"path": str(checkpoint_path), "bytes_sha256": checkpoint_sha, "state_sha256": state_sha},
            "runtime": {"python_executable": "/synthetic/python", "python": "3.10.19", "torch": "2.6.0+cpu",
                        "numpy": "1.26.4", "pip_freeze": [], "import_roots": {},
                        "cpu_affinity": [max(os.sched_getaffinity(0))], "cpu_threads": 1, "interop_threads": 1},
            "receipt_paths": receipts, "source_files": files, "source_roots_closure": closures,
            "own_source": {"root": str(own_root), "git_commit": "d" * 40,
                           "branch": p.SOURCE_BRANCH, "files": own_files},
            "phase_order": list(p.PHASE_ORDER), "phases": {x: p.phase_spec(x, roots) for x in p.PHASE_ORDER},
            "stage_caps_by_phase": {x: p.stage_caps(x) for x in p.PHASE_ORDER},
            "limits_by_phase": {x: p.phase_limits(x) for x in p.PHASE_ORDER},
            "geometry_caps_by_phase": {x: dict(p.GEOMETRY_CAPS) for x in p.PHASE_ORDER},
            "aggregate_stage_caps": p.aggregate_caps(), "stopping_policy": copy.deepcopy(p.STOPPING),
            "boundary": copy.deepcopy(p.BOUNDARY),
            "review_requirements": {"root_source_review_before_diagnostics": True,
                                    "independent_source_review_before_diagnostics": True,
                                    "root_and_independent_diagnostic_review_before_optimizer": True,
                                    "automatic_retry_after_unknown_or_failure": False}}
    return plan


def seal(tmp_path, plan):
    path = tmp_path / (str(uuid.uuid4()) + ".json")
    return path, put(path, plan)


def test_valid_synthetic_plan_verifies_complete_tiny_closures(synthetic_plan, tmp_path):
    path, checksum = seal(tmp_path, synthetic_plan)
    assert p.verify_plan(path, checksum) == synthetic_plan


def test_physical_caps_include_all_diagnostics_and_exactly_six_terminal_globals():
    caps = p.aggregate_caps()
    assert caps["objective"] == caps["source_base_full_EF"] == caps["cross_correction_EF"] == caps["internal_correction_EF"] == 3880
    assert caps["WL_EF"] == 1940
    assert caps["backward_WL"] == 9 * 1940
    assert caps["terminal_water_global"] == caps["terminal_water_screen"] == 6
    assert caps["terminal_water_kernel"] == 612
    assert caps["terminal_water_backward"] == 4356
    assert p.phase_limits("P0-dry")["optimizer_budget_seconds"] + p.phase_limits("P0-dry")["terminal_budget_seconds"] == 2400
    assert p.phase_limits("P0-dry") == p.phase_limits("P0-wet")


@pytest.mark.parametrize("mutation", [
    lambda d: d["phases"]["Qplus-dry"].update(start="P0"),
    lambda d: d["phases"]["P0-wet"].update(wet=False),
    lambda d: d["phases"]["P0-wet"].update(objective_cap=642),
    lambda d: d["phases"]["P0-wet"].update(accepted_cap=True),
    lambda d: d["phases"]["diagnostic-dry"].update(kind="optimizer"),
    lambda d: d["stage_caps_by_phase"]["P0-wet"].update(backward_WL=9 * 641 + 1),
    lambda d: d["stage_caps_by_phase"]["diagnostic-wet"].update(terminal_water_global=1),
    lambda d: d["stage_caps_by_phase"]["P0-dry"].update(WL_EF=1),
    lambda d: d["limits_by_phase"]["P0-dry"].update(wall_seconds=2700),
    lambda d: d["limits_by_phase"]["P0-dry"].update(optimizer_budget_seconds=2400),
    lambda d: d["geometry_caps_by_phase"]["P0-dry"].update(geometry_pullback=100001),
    lambda d: d["aggregate_stage_caps"].update(terminal_water_global=7),
    lambda d: d["phase_order"].reverse(),
    lambda d: d["boundary"].update(scientifically_validated=True),
    lambda d: d["stopping_policy"].update(ligand_force_tolerance=.01),
    lambda d: d["runtime"].update(cpu_affinity=[False]),
    lambda d: d["runtime"].update(cpu_affinity=[-1]),
    lambda d: d["runtime"].update(cpu_threads=True),
    lambda d: d["runtime"].update(torch="2.6.0+cu124"),
    lambda d: d.update(limits=d["limits_by_phase"]),
])
def test_arm_budget_boundary_runtime_and_order_tamper_fail(synthetic_plan, mutation):
    mutation(synthetic_plan)
    with pytest.raises(p.PlanError):
        p.validate_plan(synthetic_plan)


def test_wrong_expected_plan_hash_fails_before_source_hashing(synthetic_plan, tmp_path, monkeypatch):
    path, _ = seal(tmp_path, synthetic_plan)
    monkeypatch.setattr(p, "_verify_closure", lambda *a: pytest.fail("source loop should not run"))
    with pytest.raises(p.PlanError, match="plan byte hash"):
        p.verify_plan(path, "a" * 64)


def test_source_byte_tamper_rejected(synthetic_plan, tmp_path):
    path, checksum = seal(tmp_path, synthetic_plan)
    input_path = Path(synthetic_plan["source_roots"]["dry"]) / "snapshot/inputs/PFKFB3/ligand.json"
    input_path.write_text('{"changed":true}\n')
    with pytest.raises(p.PlanError, match="immutable source SHA256"):
        p.verify_plan(path, checksum)


@pytest.mark.parametrize("kind", ["extra", "missing", "symlink", "directory_symlink"])
def test_archive_closure_tamper_rejected(synthetic_plan, tmp_path, kind):
    path, checksum = seal(tmp_path, synthetic_plan)
    root = Path(synthetic_plan["source_roots"]["dry"])
    target = root / "snapshot/inputs/PFKFB3/ligand.json"
    if kind == "extra":
        (root / "unexpected.py").write_text("raise RuntimeError('never imported')")
    elif kind == "missing":
        target.unlink()
    elif kind == "symlink":
        target.unlink()
        target.symlink_to(tmp_path / "reference.json")
    else:
        (root / "unexpected_directory").symlink_to(tmp_path, target_is_directory=True)
    with pytest.raises((p.PlanError, OSError)):
        p.verify_plan(path, checksum)


def test_resealed_plan_cannot_omit_receipt_file_or_closure(synthetic_plan, tmp_path):
    root = next(iter(synthetic_plan["source_roots_closure"]))
    relative = next(name for name in synthetic_plan["source_roots_closure"][root]
                    if name.endswith("/start/chart-contracts.json"))
    del synthetic_plan["source_roots_closure"][root][relative]
    del synthetic_plan["source_files"][str(Path(root) / relative)]
    path, checksum = seal(tmp_path, synthetic_plan)
    with pytest.raises(p.PlanError, match="receipt/archive closure"):
        p.verify_plan(path, checksum)


def test_protocol_only_relocates_four_input_paths_and_rebinds_derived_source_evidence(synthetic_plan, tmp_path):
    binding = synthetic_plan["protocol"]
    document = json.loads(Path(binding["path"]).read_text())
    document["solver"]["force_tolerance"] = .1
    binding["sha256"] = put(Path(binding["path"]), document)
    synthetic_plan["source_files"][binding["path"]] = binding["sha256"]
    path, checksum = seal(tmp_path, synthetic_plan)
    with pytest.raises(p.PlanError, match="beyond four input paths"):
        p.verify_plan(path, checksum)


def test_extra_own_module_is_rejected(synthetic_plan, tmp_path):
    path, checksum = seal(tmp_path, synthetic_plan)
    own = Path(synthetic_plan["own_source"]["root"]) / "tools/pfk_paired_water_eight_dof/extra.py"
    own.write_text("# source added after freeze\n")
    with pytest.raises(p.PlanError, match="own implementation file closure"):
        p.verify_plan(path, checksum)


def test_regular_file_and_parent_symlinks_are_refused(tmp_path):
    directory = tmp_path / "real"
    directory.mkdir()
    source = directory / "source"
    source.write_bytes(b"synthetic")
    alias = tmp_path / "alias"
    alias.symlink_to(directory, target_is_directory=True)
    with pytest.raises(OSError):
        p.hash_file(alias / "source")
    link = tmp_path / "link"
    link.symlink_to(source)
    with pytest.raises(OSError):
        p.hash_file(link)


def test_absent_only_publication_never_overwrites_and_fsyncs(tmp_path, monkeypatch):
    calls = []
    fsync = os.fsync
    monkeypatch.setattr(os, "fsync", lambda fd: (calls.append(fd), fsync(fd))[1])
    path = tmp_path / "new.json"
    checksum = p.write_json_absent(path, {"synthetic": True})
    assert len(calls) == 2 and hashlib.sha256(path.read_bytes()).hexdigest() == checksum
    before = path.read_bytes()
    with pytest.raises(FileExistsError):
        p.write_json_absent(path, {"replacement": True})
    assert path.read_bytes() == before


def test_nested_relocation_preserves_original_digests_boundaries_and_physical_inputs(synthetic_plan):
    relocation = synthetic_plan["source_evidence_relocation"]
    original_path = Path(relocation["original"]["path"])
    before = original_path.read_bytes()
    original = json.loads(before)
    derived = json.loads(Path(relocation["derived"]["path"]).read_text())
    protocol = json.loads(Path(synthetic_plan["protocol"]["path"]).read_text())
    original_protocol = json.loads((Path(synthetic_plan["source_roots"]["dry"]) / "start/protocol.json").read_text())
    assert len(derived["source_files"]) == 16
    for old, new, record in zip(original["source_files"], derived["source_files"], relocation["source_files"]):
        assert old["path"].startswith("/unavailable/cloud/")
        assert old["sha256"] == new["sha256"] == record["sha256"]
        assert new["path"] == record["path"] and old["path"] == record["original_path"]
        assert p.hash_file(new["path"]) == old["sha256"]
    for name in ("ligand", "receptor", "parameters", "cross"):
        assert protocol[name]["sha256"] == original_protocol[name]["sha256"]
    assert protocol["source_evidence"] == relocation["derived"]
    assert protocol["source_evidence"]["sha256"] != original_protocol["source_evidence"]["sha256"]
    assert {k: v for k, v in derived.items() if k != "source_files"} == {
        k: v for k, v in original.items() if k != "source_files"}
    assert original_path.read_bytes() == before


def reseal_derived(synthetic_plan, mutation):
    binding = synthetic_plan["source_evidence_relocation"]["derived"]
    derived = json.loads(Path(binding["path"]).read_text())
    mutation(derived)
    binding["sha256"] = put(Path(binding["path"]), derived)
    synthetic_plan["source_files"][binding["path"]] = binding["sha256"]
    protocol_binding = synthetic_plan["protocol"]
    protocol = json.loads(Path(protocol_binding["path"]).read_text())
    protocol["source_evidence"] = dict(binding)
    protocol_binding["sha256"] = put(Path(protocol_binding["path"]), protocol)
    synthetic_plan["source_files"][protocol_binding["path"]] = protocol_binding["sha256"]


@pytest.mark.parametrize("mutation", [
    lambda d: d.update(source_authenticated=True),
    lambda d: d.update(original_simulation_hamiltonian_reproduced=True),
    lambda d: d.update(evidence_kind="synthetic_control"),
    lambda d: d.update(extra_metadata="not an authorized change"),
    lambda d: d["source_files"][0].update(sha256="a" * 64),
    lambda d: d["source_files"][0].update(path="/unavailable/cloud/snapshot/evidence/PFKFB3/0-source.json"),
    lambda d: d["source_files"][0].update(extra="not an authorized change"),
    lambda d: d["source_files"].reverse(),
    lambda d: d["source_files"].append(dict(d["source_files"][0])),
    lambda d: d["source_files"].pop(),
])
def test_even_resealed_derived_evidence_allows_only_the_sixteen_path_deltas(synthetic_plan, tmp_path, mutation):
    reseal_derived(synthetic_plan, mutation)
    path, checksum = seal(tmp_path, synthetic_plan)
    with pytest.raises(p.PlanError, match="more than sixteen paths"):
        p.verify_plan(path, checksum)


def test_relocation_record_must_match_original_source_paths_not_just_target_hashes(synthetic_plan, tmp_path):
    row = synthetic_plan["source_evidence_relocation"]["source_files"][0]
    row["original_path"] = "/different/prefix/snapshot/evidence/PFKFB3/0-source.json"
    path, checksum = seal(tmp_path, synthetic_plan)
    with pytest.raises(p.PlanError, match="relocation record changed"):
        p.verify_plan(path, checksum)


def test_nested_targets_must_remain_in_admitted_full_file_closure(synthetic_plan):
    files = dict(synthetic_plan["source_files"])
    target = synthetic_plan["source_evidence_relocation"]["source_files"][0]["path"]
    del files[target]
    with pytest.raises(p.PlanError, match="not byte-admitted"):
        p._relocated_source_evidence(synthetic_plan["source_roots"], files)


def test_leaf_source_json_is_opaque_and_its_historical_paths_are_not_recursively_followed(synthetic_plan, monkeypatch):
    original_path = synthetic_plan["source_evidence_relocation"]["original"]["path"]
    read = p._json_file
    opened = []
    def only_evidence_document(path):
        assert str(path) == original_path, "an evidence leaf was unexpectedly parsed"
        opened.append(str(path))
        return read(path)
    monkeypatch.setattr(p, "_json_file", only_evidence_document)
    derived, _, records = p._relocated_source_evidence(synthetic_plan["source_roots"], synthetic_plan["source_files"])
    assert opened == [original_path] and len(records) == 16
    leaf = json.loads(Path(derived["source_files"][0]["path"]).read_text())
    assert leaf["historical_path"] == "/unavailable/opaque/provenance"


@pytest.mark.parametrize("kind", ["missing", "symlink", "hardlink", "oversized"])
def test_local_nested_target_satisfies_original_reader_file_requirements(synthetic_plan, tmp_path, kind):
    target = Path(synthetic_plan["source_evidence_relocation"]["source_files"][0]["path"])
    if kind == "missing":
        target.unlink()
    elif kind == "symlink":
        target.unlink()
        target.symlink_to(tmp_path / "reference.json")
    elif kind == "hardlink":
        os.link(target, tmp_path / "extra_link_outside_archive")
    else:
        # Sparse truncation exercises the size guard without loading 32MiB.
        with target.open("r+b") as handle:
            handle.truncate(32 * 1024 ** 2 + 1)
    with pytest.raises((p.PlanError, OSError)):
        p._relocated_source_evidence(synthetic_plan["source_roots"], synthetic_plan["source_files"])


def test_derived_evidence_cannot_replace_original_evidence_in_place(synthetic_plan):
    relocation = synthetic_plan["source_evidence_relocation"]
    relocation["derived"] = dict(relocation["original"])
    with pytest.raises(p.PlanError, match="fresh sibling"):
        p.validate_plan(synthetic_plan)

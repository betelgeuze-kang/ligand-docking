"""Mock-only cross graph/call tests; no Torch/OpenMM import or molecular body."""
from copy import deepcopy
import importlib.util
from pathlib import Path
import types

import pytest


HERE = Path(__file__).resolve().parent
REPO = Path(__file__).resolve().parents[2]
SOURCE = HERE / "sro_cross_force_decomposition_diagnostic_v1.py"
if not SOURCE.exists():
    SOURCE = REPO / "benchmarks/oracles/sro_cross_force_decomposition_diagnostic_v1.py"
spec = importlib.util.spec_from_file_location("sro_cross_force_decomposition_test", SOURCE)
diag = importlib.util.module_from_spec(spec)
spec.loader.exec_module(diag)

TOY_SOURCE = b'''class FixedReceptorEnvironment:
    def evaluate_cross(self, ligand, base_parameters):
        self.validate_ligand(ligand, base_parameters)
        xyz = self.xyz
        force = torch.zeros_like(xyz)
        lj_sum, q_sum, count = 0.0, 0.0, 0
        for start, end, left, right, lj, electro in self.blocks:
            count += len(left.tolist())
            gradient = torch.autograd.grad(lj + electro, xyz)[0]
            force -= gradient.detach()
            lj_sum += float(lj.detach())
            q_sum += float(electro.detach())
        self.assert_intact()
        return {"cross_lennard_jones": [lj_sum], "cross_screened_coulomb": [q_sum]}, force.unsqueeze(0), count
'''


class ToyVector:
    def __init__(self, rows):
        self.rows = deepcopy(rows)
    def detach(self):
        return self
    def tolist(self):
        return deepcopy(self.rows)
    def __isub__(self, other):
        self.rows = diag.subtract(self.rows, other.rows)
        return self
    def unsqueeze(self, _):
        return [self]


class ToyEnergy:
    def __init__(self, value, gradient):
        self.value, self.gradient = value, gradient
    def __float__(self):
        return float(self.value)
    def detach(self):
        return self
    def __add__(self, other):
        summed = [[a + b for a, b in zip(x, y, strict=True)] for x, y in zip(self.gradient, other.gradient, strict=True)]
        return ToyEnergy(self.value + other.value, summed)


class ToyIndices:
    def __init__(self, values):
        self.values = values
    def tolist(self):
        return self.values[:]


class ToyTorch:
    def __init__(self, failure_call=None, failure_type=RuntimeError):
        self.autograd = types.SimpleNamespace(grad=self.grad)
        self.calls, self.failure_call, self.failure_type = [], failure_call, failure_type
    def zeros_like(self, _):
        return ToyVector([[0.0] * 3 for _ in range(26)])
    def grad(self, energy, xyz, **kwargs):
        self.calls.append(kwargs)
        if len(self.calls) == self.failure_call:
            raise self.failure_type("mock_backward_error")
        return (ToyVector(energy.gradient),)


def xyz(value):
    rows = [[0.0] * 3 for _ in range(26)]
    rows[0][0] = float(value)
    return rows


def fixture(block_gradients=(1.0, 2.0), failure_call=None, failure_type=RuntimeError):
    torch = ToyTorch(failure_call, failure_type)
    environment = types.SimpleNamespace(xyz=ToyVector(xyz(0.0)), blocks=[], checks=[])
    def validate(ligand, parameters):
        environment.checks.append((ligand, parameters))
    environment.validate_ligand = validate
    def intact():
        return None
    environment.assert_intact = intact
    for index, value in enumerate(block_gradients):
        start = index * 512  # Deliberately skip every odd source block.
        environment.blocks.append((start, start + 256, ToyIndices([0]), ToyIndices([0]),
                                   ToyEnergy(1.0, xyz(value)), ToyEnergy(2.0, xyz(0.0))))
    return dict(source=TOY_SOURCE, namespace={"torch": torch}, environment=environment, ligand="mock ligand only",
                base_parameters="mock parameters only", maximum_blocks=6, block_size=256,
                expected_source_sha256=diag.sha(TOY_SOURCE)), torch


def test_exact_baseline_instrumented_outputs_and_known_empty_slots():
    args, torch = fixture()
    original_autograd = torch.autograd
    result = diag.evaluate_pair(**args)
    assert result["status"] == "completed"
    assert result["native_cross_observations"]["baseline"] == result["native_cross_observations"]["diagnostic"]
    assert torch.autograd is original_autograd and args["namespace"]["torch"] is torch
    assert torch.calls[:2] == [{}, {}]
    assert torch.calls[2:] == [{"retain_graph": True}, {"retain_graph": True}, {"retain_graph": False}] * 2
    counts = result["call_accounting"]["counts"]
    assert counts["cross_entry"]["completed"] == 2
    for key in ("baseline.combined", "diagnostic.combined", "diagnostic.lj", "diagnostic.coulomb"):
        assert counts[key] == {"maximum_reserved": 6, "completed": 2, "error": 0, "unknown": 0, "not_dispatched": 4}
    remaining = [r for r in result["call_accounting"]["calls"] if r["status"] == "reserved"]
    assert all(r["not_dispatched_reason"] == "source_skipped_inactive_blocks" for r in remaining)
    assert [row["source_block_index"] for row in result["block_observations"]] == [0, 2]
    assert result["block_observations"][1]["ordered_pairs_ligand_receptor"] == [[0, 512]]
    assert result["completed_native_backward_returns"] == 8
    assert result["new_internal_calls"] == result["new_optimizer_calls"] == result["new_score_calls"] == result["new_openmm_calls"] == 0
    assert args["environment"].checks == [("mock ligand only", "mock parameters only")] * 2


def test_math_fsum_is_observation_and_does_not_overwrite_original_total():
    args, _ = fixture((1e16, 1.0, -1e16))
    result = diag.evaluate_pair(**args)
    assert result["status"] == "completed"
    assert result["native_cross_observations"]["diagnostic"]["force_vectors_binary64_hex"][0][0] == (0.0).hex()
    summed = result["force_sum_observations"]["diagnostic.combined"]
    assert summed["math_fsum_force_sum"]["vectors_binary64_hex"][0][0] == (-1.0).hex()
    assert result["decomposition"]["combined_output_overwritten"] is False


def test_separated_terms_do_not_replace_authoritative_combined_gradient():
    args, _ = fixture((0.0, 1.0))
    first = args["environment"].blocks[0]
    args["environment"].blocks[0] = (*first[:4], ToyEnergy(1.0, xyz(1e16)), ToyEnergy(2.0, xyz(-1e16)))
    result = diag.evaluate_pair(**args)
    assert result["status"] == "completed"
    assert result["native_cross_observations"]["diagnostic"]["force_vectors_binary64_hex"][0][0] == (-1.0).hex()
    assert result["decomposition"]["combined_minus_separately_summed_lj_q"]["max_absolute_component"] == 1.0


@pytest.mark.parametrize("failure_type", [RuntimeError, KeyboardInterrupt])
def test_lj_failure_preserves_completed_combined_and_baseline(failure_type):
    args, torch = fixture(failure_call=4, failure_type=failure_type)
    original = torch.autograd
    events = []
    result = diag.evaluate_pair(**args, sink=events.append)
    assert result["status"] == "failed" and torch.autograd is original
    assert "baseline" in result["native_cross_observations"] and "diagnostic" not in result["native_cross_observations"]
    assert any(row["arm"] == "diagnostic" and row["term"] == "combined" for row in result["backward_observations"])
    assert result["call_accounting"]["counts"]["diagnostic.lj"]["error"] == 1
    assert result["completed_native_backward_returns"] == 3
    assert result["attempted_native_backward_calls"] == 4
    assert result["native_backward_error_calls"] == 1
    assert result["native_backward_internal_work_unknown"]
    assert any(event["event"] == "completed_backward_observation" and event["arm"] == "diagnostic" for event in events)


def test_postprocessing_failure_preserves_all_raw_vectors_and_ledger(monkeypatch):
    args, _ = fixture()
    def failed(_):
        raise ValueError("mock_postprocessing_failure")
    monkeypatch.setattr(diag.Observer, "summary", failed)
    result = diag.evaluate_pair(**args)
    assert result["status"] == "failed" and result["failure"]["reason"] == "mock_postprocessing_failure"
    assert set(result["native_cross_observations"]) == {"baseline", "diagnostic"}
    assert len(result["backward_observations"]) == 8 and result["completed_native_backward_returns"] == 8


def test_cleanup_failure_retains_primary_failure_vectors_and_restores_settings():
    import sys
    args, _ = fixture()
    receipt = diag.evaluate_pair(**args)
    original_vectors = deepcopy(receipt["native_cross_observations"])
    original_path, original_bytecode = list(sys.path), sys.dont_write_bytecode
    class BrokenStream:
        def close(self):
            raise OSError("mock_close_failure")
    sys.path.append("/synthetic-not-a-real-input")
    sys.dont_write_bytecode = not original_bytecode
    errors = diag.restore_runtime(BrokenStream(), original_path, original_bytecode)
    assert sys.path == original_path and sys.dont_write_bytecode == original_bytecode
    primary = {"type": "ValueError", "reason": "mock_primary_failure"}
    result = diag.failure_envelope(receipt, primary, errors)
    assert result["status"] == "failed" and result["primary_post_execution_failure"] == primary
    assert result["cleanup_errors"] == [{"type": "OSError", "reason": "mock_close_failure"}]
    assert result["native_cross_observations"] == original_vectors and result["completed_native_backward_returns"] == 8


def test_journal_secondary_failure_does_not_replace_backward_primary_error():
    ledger = diag.Ledger(1)
    def sink(event):
        if event["event"] == "finished":
            raise OSError("mock_journal_failure")
    ledger.sink = sink
    def failed():
        raise ValueError("mock_backward_primary")
    with pytest.raises(ValueError, match="mock_backward_primary"):
        ledger.call("backward", "diagnostic.lj.0", failed)
    row = next(row for row in ledger.rows if row["key"] == "diagnostic.lj.0")
    assert row["error"]["reason"] == "mock_backward_primary"
    assert row["journal_secondary_error"]["reason"] == "mock_journal_failure"


def test_empty_source_has_zero_completed_backward_calls():
    args, _ = fixture(())
    result = diag.evaluate_pair(**args)
    assert result["status"] == "completed" and result["completed_native_backward_returns"] == 0
    assert all(row["status"] == "reserved" for row in result["call_accounting"]["calls"] if row["kind"] == "backward")


def test_durable_start_survives_interrupt_as_unknown():
    events = []
    ledger = diag.Ledger(18, events.append)
    assert len(events) == 74
    def interrupt(event):
        events.append(event)
        if event["event"] == "started":
            raise KeyboardInterrupt("mock hard interruption")
    ledger.sink = interrupt
    with pytest.raises(KeyboardInterrupt):
        ledger.call("cross_entry", "baseline", lambda: pytest.fail("should not dispatch"))
    assert ledger.receipt()["counts"]["cross_entry"]["unknown"] == 1


def test_source_gradient_operand_mutation_rejected_before_calls():
    args, torch = fixture()
    args["source"] = TOY_SOURCE.replace(b"lj + electro", b"lj * electro")
    args["expected_source_sha256"] = diag.sha(args["source"])
    result = diag.evaluate_pair(**args)
    assert result["status"] == "failed" and result["failure"]["reason"] == "exact_combined_gradient_statement_required"
    assert not torch.calls


def test_frozen_real_source_compiles_without_importing_or_evaluating_torch():
    path = REPO / diag.FIXED_MEMBER
    source = path.read_bytes()  # Source code only, not molecular input.
    fake = ToyTorch()
    observer = diag.Observer(fake, diag.Ledger(18), 256)
    baseline, first = diag.compile_cross(source, {"torch": fake}, observer, diagnostic=False)
    diagnostic, second = diag.compile_cross(source, {"torch": fake}, observer, diagnostic=True)
    assert callable(baseline) and callable(diagnostic)
    assert first["original_method_ast_sha256"] == second["original_method_ast_sha256"]
    assert first["baseline_only_namespace_proxy"] and not second["baseline_only_namespace_proxy"]


@pytest.mark.parametrize("mutation", ["extra", "substitute", "protected", "shape", "budget"])
def test_bad_numerical_roles_rejected_before_body_read(monkeypatch, mutation):
    refs = {name: {"path": "/unopened/" + name + ".json", "bytes": 1, "sha256": "a" * 64}
            for name in ("receptor", "ligand", "parameters", "cross_parameters")}
    case = {"case_id": diag.CASE, "derived_input_refs": refs, "derived_system_sha256": "b" * 64,
            "derived_topology_sha256": "c" * 64, "request_file_ref": {"metadata": "only"}, "expected_binding_ref": {"metadata": "only"}}
    wheel = {"sha256": diag.WHEEL_SHA}
    terminal = {"cases": [case], "wheel_ref": wheel}
    touched = []
    def read(ref):
        touched.append(ref["path"])
        assert ref["path"] == str(diag.R2 / "plan.json"), "numerical body opened"
        return diag.canonical(terminal)
    h = types.SimpleNamespace(read_ref=read)
    plan = {"schema_id": diag.PLAN_SCHEMA, "case_id": diag.CASE, "state_label": "initial", "frozen_campaign_root": str(diag.R2),
            "frozen_gate": 1e-8, "campaign_resume_allowed": False,
            "metadata_refs": {role: {"path": str(diag.R2 / filename), "sha256": diag.METADATA_SHA[role]}
                              for role, filename in (("terminal_plan", "plan.json"), ("oracle_input_spec", "oracle-input-spec.json"))},
            "numerical_refs": {**deepcopy(refs), "endpoint_states": diag.ENDPOINT_REF, "openmm_reference": diag.OPENMM_REF},
            "declared_shape": {"receptor_count": 4376, "receptor_block_size": 256, "maximum_blocks": 18},
            "protocol_budget": {"cross_entries": 2, "baseline_combined_backward": 18, "diagnostic_combined_backward": 18,
                                "diagnostic_lj_backward": 18, "diagnostic_coulomb_backward": 18, "total_reserved": 74},
            "source_closure": {"wheel_ref": wheel}, "source_state_identity": {"derived_system_sha256": case["derived_system_sha256"],
                "derived_topology_sha256": case["derived_topology_sha256"], "request_ref": case["request_file_ref"], "expected_binding_ref": case["expected_binding_ref"]}}
    if mutation == "extra":
        plan["numerical_refs"]["extra"] = refs["ligand"]
    elif mutation == "substitute":
        plan["numerical_refs"]["ligand"]["path"] += "-unapproved"
    elif mutation == "protected":
        refs["ligand"]["path"] = "/unopened/evaluation_only/ligand.json"
        plan["numerical_refs"]["ligand"]["path"] = refs["ligand"]["path"]
    elif mutation == "shape":
        plan["declared_shape"]["receptor_block_size"] = 128
    else:
        plan["protocol_budget"]["total_reserved"] = 73
    with pytest.raises(ValueError):
        diag.validate_roles(plan, h)
    assert touched == [str(diag.R2 / "plan.json")]


def test_execute_requires_authorization_before_helper_source_read(monkeypatch):
    monkeypatch.setattr(diag, "helper", lambda: pytest.fail("no reads before authorization"))
    with pytest.raises(ValueError, match="explicit_numerical_phase"):
        diag.execute_plan("/unopened/plan.json", "a" * 64, "/unopened/output")


def test_openmm_observation_bad_seal_is_rejected():
    saved = {"schema_id": "sro_particle_roundtrip_diagnostic/1", "case_id": diag.CASE, "status": "completed",
             "actual_openmm_observations": True, "receipt_sha256": "bad"}
    with pytest.raises(ValueError, match="newR_receipt_seal"):
        diag.compare_openmm({}, saved)


def test_openmm_force_energy_comparison_retains_fixed_gate():
    args, _ = fixture()
    result = diag.evaluate_pair(**args)
    sums = result["force_sum_observations"]
    energy = result["native_cross_observations"]["diagnostic"]["energy_hex"]
    terms = {}
    for term, key in (("combined", "cross"), ("lj", "cross_lj"), ("coulomb", "cross_coulomb")):
        value = (float.fromhex(energy["cross_lennard_jones"]) + float.fromhex(energy["cross_screened_coulomb"])) if term == "combined" else \
            float.fromhex(energy["cross_lennard_jones" if term == "lj" else "cross_screened_coulomb"])
        terms[key] = {"ligand_force": sums["diagnostic." + term]["original_order_force_sum"], "energy_kcal_per_mol_hex": value.hex()}
    saved = {"schema_id": "sro_particle_roundtrip_diagnostic/1", "case_id": diag.CASE, "status": "completed",
             "actual_openmm_observations": True, "states": {"initial": {"original_xml_particles": {"terms": terms}}}}
    saved["receipt_sha256"] = diag.sha(diag.canonical(saved))
    compared = diag.compare_openmm(result, saved)
    assert all(row["passed_fixed_1e_minus_8_force_gate"] and row["passed_fixed_1e_minus_8_energy_gate"] for row in compared.values())
    assert not result["historical_total_minus_new_cross_is_old_internal"]


def test_stored_initial_energy_comparison_separates_historical_observation():
    args, _ = fixture()
    result = diag.evaluate_pair(**args)
    initial = {"components": {"cross_lennard_jones": (2.0).hex(), "cross_screened_coulomb": (4.0).hex()}}
    compared = diag.compare_stored_initial_energies(result, initial)
    assert all(row["exact_hex_match"] for row in compared.values())
    initial["components"]["cross_lennard_jones"] = (2.0 + 2e-8).hex()
    failed = diag.compare_stored_initial_energies(result, initial)
    assert not failed["cross_lennard_jones"]["passed_fixed_1e_minus_8_energy_gate"]
    assert result["native_graph_build_api_calls"] == 0
    assert result["autograd_graph_construction_is_within_cross_entry_cost"]


@pytest.fixture(autouse=True)
def no_actual_molecular_libraries_loaded():
    import sys
    before = set(sys.modules)
    yield
    assert not {name for name in set(sys.modules) - before if name == "torch" or name.startswith("torch.") or name == "openmm" or name.startswith("openmm.")}


@pytest.mark.parametrize("kind", ["backward", "cross_entry"])
def test_finished_journal_failure_preserves_completed_raw_return(kind):
    args, _ = fixture()
    def sink(event):
        if event["event"] == "finished" and event["kind"] == kind:
            raise OSError("mock_finished_journal_failure")
    result = diag.evaluate_pair(**args, sink=sink)
    assert result["status"] == "failed" and result["failure"]["reason"] == "mock_finished_journal_failure"
    assert result["backward_observations"]
    assert result["completed_native_backward_returns"] == (1 if kind == "backward" else 2)
    assert result["attempted_native_backward_calls"] == result["completed_native_backward_returns"]
    assert result["raw_native_observations_performed"]
    if kind == "cross_entry":
        assert "baseline" in result["native_cross_observations"]


def test_first_backward_failure_does_not_claim_zero_work_or_completed_raw_returns():
    args, _ = fixture(failure_call=1)
    result = diag.evaluate_pair(**args)
    assert result["completed_native_backward_returns"] == 0
    assert result["attempted_native_backward_calls"] == result["dispatched_native_backward_calls"] == 1
    assert result["native_backward_error_calls"] == 1
    assert result["native_backward_work_performed"] == "unknown"
    assert result["native_backward_internal_work_unknown"]
    assert not result["raw_native_observations_performed"]


def test_unknown_start_reports_attempted_boundary_without_false_dispatch():
    ledger = diag.Ledger(1)
    def interrupt(event):
        if event["event"] == "started":
            raise KeyboardInterrupt("mock pre-dispatch journal interruption")
    ledger.sink = interrupt
    with pytest.raises(KeyboardInterrupt):
        ledger.call("backward", "baseline.combined.0", lambda: pytest.fail("must not dispatch"))
    row = next(row for row in ledger.rows if row["key"] == "baseline.combined.0")
    assert row["status"] == "unknown" and not row["dispatch_attempted"]


@pytest.mark.parametrize("path", [str(diag.R2 / "new-output"), str(diag.WORK / "new-output"),
    str(Path(diag.OPENMM_REF["path"]).parents[1] / "new-output"),
    "/tmp/reference/new-output", "/tmp/evaluation_only/new-output", "/tmp/Fresh-128/new-output"])
def test_output_guard_rejects_campaign_source_and_protected_paths_before_helper(path, monkeypatch):
    monkeypatch.setattr(diag, "helper", lambda: pytest.fail("guard must precede source/body reads"))
    with pytest.raises(ValueError, match="new_unprotected_non_source_output_required"):
        diag.prepare_plan(r2=diag.R2, output=path, test_source="unused", document_source="unused",
                          openmm_receipt_ref=diag.OPENMM_REF, receptor_count=4376, receptor_block_size=256)


@pytest.mark.parametrize("mutation", ["protected", "name", "helper", "outside_snapshot"])
def test_source_role_guard_rejects_substitutions_without_body_reads(mutation):
    directory = Path("/unopened/prospective/source")
    names = {"diagnostic": "sro_cross_force_decomposition_diagnostic_v1.py",
             "tests": "test_sro_cross_force_decomposition_diagnostic_v1.py",
             "document": "sro_cross_force_decomposition_diagnostic_plan_20261001.md",
             "stdlib_helper": "sro_particle_roundtrip_diagnostic_v1.py"}
    plan = {"source_refs": {role: {"path": str(directory / name), "bytes": 1,
                "sha256": diag.HELPER_SHA if role == "stdlib_helper" else "a" * 64} for role, name in names.items()}}
    if mutation == "protected":
        plan["source_refs"]["tests"]["path"] = "/unopened/reference/test_sro_cross_force_decomposition_diagnostic_v1.py"
    elif mutation == "name":
        plan["source_refs"]["document"]["path"] += ".wrong"
    elif mutation == "helper":
        plan["source_refs"]["stdlib_helper"]["sha256"] = "b" * 64
    else:
        plan["source_refs"]["tests"]["path"] = "/unopened/other/test_sro_cross_force_decomposition_diagnostic_v1.py"
    with pytest.raises(ValueError):
        diag.validate_source_refs(plan, "/unopened/prospective/plan.json")


def test_dependency_site_mismatch_rejected_using_metadata_only():
    refs = {name: {"path": "/unopened/" + name + ".json", "bytes": 1, "sha256": "a" * 64}
            for name in ("receptor", "ligand", "parameters", "cross_parameters")}
    case = {"case_id": diag.CASE, "derived_input_refs": refs, "derived_system_sha256": "b" * 64,
            "derived_topology_sha256": "c" * 64, "request_file_ref": {}, "expected_binding_ref": {}}
    wheel, python = {"sha256": diag.WHEEL_SHA}, {"path": "/unopened/python", "sha256": "d" * 64}
    old = {"cases": [case], "wheel_ref": wheel, "oracle_phase": {"python_binary_ref": python}}
    plan = {"schema_id": diag.PLAN_SCHEMA, "case_id": diag.CASE, "state_label": "initial", "frozen_campaign_root": str(diag.R2),
            "frozen_gate": 1e-8, "campaign_resume_allowed": False,
            "metadata_refs": {role: {"path": str(diag.R2 / filename), "sha256": diag.METADATA_SHA[role]}
                for role, filename in (("terminal_plan", "plan.json"), ("oracle_input_spec", "oracle-input-spec.json"))},
            "numerical_refs": {**refs, "endpoint_states": diag.ENDPOINT_REF, "openmm_reference": diag.OPENMM_REF},
            "declared_shape": {"receptor_count": 4376, "receptor_block_size": 256, "maximum_blocks": 18},
            "protocol_budget": {"cross_entries": 2, "baseline_combined_backward": 18, "diagnostic_combined_backward": 18,
                                "diagnostic_lj_backward": 18, "diagnostic_coulomb_backward": 18, "total_reserved": 74},
            "source_closure": {"wheel_ref": wheel}, "source_state_identity": {"derived_system_sha256": "b" * 64,
                "derived_topology_sha256": "c" * 64, "request_ref": {}, "expected_binding_ref": {}},
            "dependency_site": "/unapproved/site", "python_binary_ref": python}
    touched = []
    def read(ref):
        touched.append(ref["path"])
        if ref["path"] == str(diag.R2 / "plan.json"):
            return diag.canonical(old)
        assert ref["path"] == str(diag.R2 / "oracle-input-spec.json"), "numerical body opened"
        return diag.canonical({"dependency_site": "/approved/site"})
    with pytest.raises(ValueError, match="pinned_runtime_metadata_required"):
        diag.validate_roles(plan, types.SimpleNamespace(read_ref=read))
    assert touched == [str(diag.R2 / "plan.json"), str(diag.R2 / "oracle-input-spec.json")]


def test_loaded_product_outside_old_wheel_site_rejected(tmp_path, monkeypatch):
    import sys
    site = tmp_path / "source"
    site.mkdir()
    outside = tmp_path / "outside.py"
    outside.write_bytes(b"# synthetic source only\n")
    name = "betelgeuze_product.mock_cross_closure"
    monkeypatch.setitem(sys.modules, name, types.SimpleNamespace(__file__=str(outside)))
    with pytest.raises(ValueError, match="loaded_product_outside_frozen_source_closure"):
        diag.validate_loaded_closure(site, {}, (name,))


def test_required_old_wheel_imports_must_be_present(tmp_path):
    with pytest.raises(ValueError, match="required_frozen_imports_missing"):
        diag.validate_loaded_closure(tmp_path, {}, ("betelgeuze_product.required_mock",))


def test_environment_identity_records_binary_and_loaded_dependency_module_pins(tmp_path, monkeypatch):
    import sys
    source = tmp_path / "synthetic-module.py"
    source.write_bytes(b"# no numerical libraries loaded\n")
    monkeypatch.setitem(sys.modules, "numpy.synthetic_cross_identity", types.SimpleNamespace(__file__=str(source)))
    pins = []
    def pin(path, **kwargs):
        assert kwargs["allowed_paths"] == [path]
        pins.append(str(path))
        return {"path": str(path), "bytes": 1, "sha256": "a" * 64}
    torch = types.SimpleNamespace(__file__=str(source), __version__="mock-only", get_num_threads=lambda: 1,
                                  get_num_interop_threads=lambda: 1)
    binary = {"path": "/unopened/mock-python", "bytes": 1, "sha256": "b" * 64}
    result = diag.environment_identity(torch, binary, types.SimpleNamespace(pin=pin))
    assert result["python_binary_ref"] == binary and result["torch_version"] == "mock-only"
    assert result["dtype"] == "float64" and result["device"] == "cpu"
    assert "numpy.synthetic_cross_identity" in result["loaded_dependency_modules"]
    assert str(source) in pins


@pytest.mark.parametrize("name", ["torch", "numpy", "betelgeuze_product.synthetic_cross_preloaded"])
def test_preloaded_runtime_rejected_without_imports_or_numerical_reads(name):
    import sys
    before = sys.modules.get(name)
    sys.modules[name] = types.SimpleNamespace()
    try:
        with pytest.raises(ValueError, match="product_and_numerical_modules_must_not_be_preloaded"):
            diag.validate_unloaded_runtime()
    finally:
        if before is None:
            del sys.modules[name]
        else:
            sys.modules[name] = before


def test_empty_python_source_pin_and_loaded_manifest_are_retained(tmp_path, monkeypatch):
    import sys
    package = tmp_path / "__init__.py"
    package.write_bytes(b"")
    h = diag.helper()  # Verified stdlib helper source only; no numerical input.
    expected = {"path": str(package), "bytes": 0, "sha256": diag.sha(b"")}
    assert diag.module_source_pin(package, h) == expected
    monkeypatch.setitem(sys.modules, "numpy.synthetic_empty_package", types.SimpleNamespace(__file__=str(package)))
    torch = types.SimpleNamespace(__file__=str(package), __version__="mock-only", get_num_threads=lambda: 1,
                                  get_num_interop_threads=lambda: 1)
    binary = {"path": "/unopened/mock-python", "bytes": 1, "sha256": "b" * 64}
    identity = diag.environment_identity(torch, binary, h)
    assert identity["loaded_dependency_modules"]["numpy.synthetic_empty_package"] == expected
    assert identity["torch_module_ref"] == expected
    assert identity["loaded_dependency_manifest_sha256"] == diag.sha(diag.canonical(identity["loaded_dependency_modules"]))
    assert identity["zero_byte_python_source_pins_allowed"]
    assert not identity["full_shared_library_closure_claimed"] and not identity["complete_provenance_admission_claimed"]
    # The narrow software-source exception does not weaken numerical body guards.
    with pytest.raises(ValueError, match="bounded_input_required"):
        h.read_ref(expected)


@pytest.mark.parametrize("suffix", [".so", ".pyd", ".dll", ".json"])
def test_empty_non_python_module_pin_rejected(tmp_path, suffix):
    source = tmp_path / ("synthetic-empty" + suffix)
    source.write_bytes(b"")
    with pytest.raises(ValueError, match="empty_python_module_source_only"):
        diag.module_source_pin(source, diag.helper())


@pytest.mark.parametrize("role", ["reference", "evaluation_only", "stability_control", "Fresh-128"])
def test_empty_module_protected_path_rejected(tmp_path, role):
    directory = tmp_path / role
    directory.mkdir()
    source = directory / "__init__.py"
    source.write_bytes(b"")
    with pytest.raises(ValueError):
        diag.module_source_pin(source, diag.helper())


def test_empty_module_leaf_and_parent_symlinks_and_noncanonical_path_rejected(tmp_path):
    directory = tmp_path / "package"
    directory.mkdir()
    source = directory / "__init__.py"
    source.write_bytes(b"")
    leaf = tmp_path / "alias.py"
    leaf.symlink_to(source)
    parent = tmp_path / "alias-package"
    parent.symlink_to(directory, target_is_directory=True)
    h = diag.helper()
    for path in (leaf, parent / "__init__.py", directory / ".." / "package" / "__init__.py"):
        with pytest.raises(ValueError, match="canonical_regular_file_required"):
            diag.module_source_pin(path, h)


def test_empty_module_append_during_read_rejected(tmp_path, monkeypatch):
    source = tmp_path / "__init__.py"
    source.write_bytes(b"")
    h = diag.helper()
    original = diag.os.fdopen
    class AppendOnRead:
        def __init__(self, stream):
            self.stream = stream
        def __enter__(self):
            self.stream.__enter__()
            return self
        def __exit__(self, *args):
            return self.stream.__exit__(*args)
        def fileno(self):
            return self.stream.fileno()
        def read(self, count):
            assert count == 1
            raw = self.stream.read(count)
            source.write_bytes(b"# synthetic append\n")
            return raw
    monkeypatch.setattr(diag.os, "fdopen", lambda fd, mode: AppendOnRead(original(fd, mode)))
    with pytest.raises(ValueError, match="module_source_changed_during_read"):
        diag.module_source_pin(source, h)


def test_empty_module_replacement_between_validation_and_open_rejected(tmp_path, monkeypatch):
    source = tmp_path / "__init__.py"
    source.write_bytes(b"")
    h = diag.helper()
    original = diag.os.open
    def replace_then_open(path, flags):
        assert flags == diag.os.O_RDONLY | diag.os.O_NOFOLLOW | diag.os.O_NONBLOCK
        displaced = tmp_path / "displaced.py"
        source.rename(displaced)
        source.write_bytes(b"")
        return original(path, flags)
    monkeypatch.setattr(diag.os, "open", replace_then_open)
    with pytest.raises(ValueError, match="module_source_changed_during_read"):
        diag.module_source_pin(source, h)


def test_empty_module_one_byte_eof_check_is_required(tmp_path, monkeypatch):
    source = tmp_path / "__init__.py"
    source.write_bytes(b"")
    h = diag.helper()
    original = diag.os.fdopen
    class NonEofRead:
        def __init__(self, stream):
            self.stream = stream
        def __enter__(self):
            self.stream.__enter__()
            return self
        def __exit__(self, *args):
            return self.stream.__exit__(*args)
        def fileno(self):
            return self.stream.fileno()
        def read(self, count):
            assert count == 1
            return b"x"  # Synthetic EOF fault with unchanged filesystem metadata.
    monkeypatch.setattr(diag.os, "fdopen", lambda fd, mode: NonEofRead(original(fd, mode)))
    with pytest.raises(ValueError, match="empty_module_source_eof_required"):
        diag.module_source_pin(source, h)


def test_nonempty_module_pin_delegates_frozen_bounded_pin_unchanged(tmp_path):
    source = tmp_path / "synthetic.py"
    source.write_bytes(b"# synthetic module source only\n")
    calls = []
    expected = {"path": str(source), "bytes": source.stat().st_size, "sha256": "a" * 64}
    def pin(path, **kwargs):
        calls.append((path, kwargs))
        return expected
    h = types.SimpleNamespace(pin=pin)
    assert diag.module_source_pin(source, h) is expected
    assert calls == [(source, {"allowed_paths": [source], "max_bytes": 128 * 1024 * 1024})]


def test_environment_records_absent_missing_nonregular_and_nonpath_origins(tmp_path, monkeypatch):
    import sys
    source = tmp_path / "synthetic-module.py"
    source.write_bytes(b"# synthetic source only\n")
    cases = {"absent": types.SimpleNamespace(), "missing": types.SimpleNamespace(__file__=str(tmp_path / "missing.py")),
             "nonregular": types.SimpleNamespace(__file__=str(tmp_path)), "nonpath": types.SimpleNamespace(__file__=7)}
    for label, module in cases.items():
        monkeypatch.setitem(sys.modules, "numpy.synthetic_unresolved_" + label, module)
    torch = types.SimpleNamespace(__file__=str(source), __version__="mock-only", get_num_threads=lambda: 1,
                                  get_num_interop_threads=lambda: 1)
    result = diag.environment_identity(torch, {}, diag.helper())
    origins = result["unresolved_dependency_module_origins"]
    for label in cases:
        assert "numpy.synthetic_unresolved_" + label in origins
        assert "numpy.synthetic_unresolved_" + label not in result["loaded_dependency_modules"]
    assert origins["numpy.synthetic_unresolved_nonregular"]["reason"] == "module_file_nonregular"
    assert result["loaded_dependency_origin_manifest_sha256"] == diag.sha(diag.canonical({
        "files": result["loaded_dependency_modules"], "unresolved": origins}))
    assert not result["full_shared_library_closure_claimed"] and not result["complete_provenance_admission_claimed"]


def test_environment_preserves_and_rejects_original_symlink_origin(tmp_path, monkeypatch):
    import sys
    source = tmp_path / "__init__.py"
    source.write_bytes(b"")
    alias = tmp_path / "alias.py"
    alias.symlink_to(source)
    monkeypatch.setitem(sys.modules, "numpy.synthetic_symlink", types.SimpleNamespace(__file__=str(alias)))
    torch = types.SimpleNamespace(__file__=str(source), __version__="mock-only", get_num_threads=lambda: 1,
                                  get_num_interop_threads=lambda: 1)
    with pytest.raises(ValueError, match="module_file_symlink_forbidden"):
        diag.environment_identity(torch, {}, diag.helper())

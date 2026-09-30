"""Synthetic and mocked QA only: no OpenMM import and no real molecular body."""
from copy import deepcopy
import hashlib
import importlib.util
from pathlib import Path
import shlex
import types

import pytest

from tools import check_external_oracle_architecture as architecture


HERE = Path(__file__).resolve().parent
REPO = Path(__file__).resolve().parents[2]
SOURCE = HERE / "sro_particle_roundtrip_diagnostic_v1.py"
if not SOURCE.exists():
    SOURCE = REPO / "benchmarks/oracles/sro_particle_roundtrip_diagnostic_v1.py"
spec = importlib.util.spec_from_file_location("particle_diagnostic_test", SOURCE)
diag = importlib.util.module_from_spec(spec)
spec.loader.exec_module(diag)
ORACLE = HERE / "sro_recovery_endpoint_numerics_v1.py"
if not ORACLE.exists():
    ORACLE = REPO / "benchmarks/oracles/sro_recovery_endpoint_numerics_v1.py"
oracle = diag.load_oracle(diag.pin(ORACLE, allowed_paths=[ORACLE]))


def _architecture_fixture(root):
    for relative in (".dockerignore", "Dockerfile.product", "pyproject.toml", "packaging/engine-v2/pyproject.toml"):
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((REPO / relative).read_bytes())
    target = root / "benchmarks/oracles/sro_particle_roundtrip_diagnostic_v1.py"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(SOURCE.read_bytes())
    return target


def test_actual_diagnostic_is_benchmark_only_and_product_import_fails_closed(tmp_path):
    benchmark_root = tmp_path / "benchmark"
    relocated = _architecture_fixture(benchmark_root)
    assert hashlib.sha256(relocated.read_bytes()).hexdigest() == "f9d860e150542596457e546802ef8594365c112c424f8a1abf8e82a1734e9c3a"
    assert architecture.inspect_python_boundary(benchmark_root) == []
    assert architecture.inspect_product_import_boundary(benchmark_root) == []
    old_root = tmp_path / "former-product-location"
    old_source = old_root / "tools/research/sro_particle_roundtrip_diagnostic_v1.py"
    old_source.parent.mkdir(parents=True)
    old_source.write_bytes(relocated.read_bytes())
    assert "product_dynamic_code_execution_unresolved" in {
        item.code for item in architecture.inspect_product_import_boundary(old_root)}
    import_root = tmp_path / "attempted-product-import"
    _architecture_fixture(import_root)
    product_source = import_root / "api/start.py"
    product_source.parent.mkdir()
    product_source.write_text("import benchmarks.oracles.sro_particle_roundtrip_diagnostic_v1\n")
    violations = architecture.inspect_product_import_boundary(import_root)
    assert any(item.code == "product_imports_external_oracle"
               and "api.start -> benchmarks.oracles.sro_particle_roundtrip_diagnostic_v1" in item.detail
               for item in violations)


@pytest.mark.parametrize("mutation,code", [
    ("docker-reinclude", "oracle_docker_reincluded"),
    ("docker-copy", "oracle_copied_into_product_image"),
    ("wheel-include", "oracle_wheel_exclusion_missing"),
])
def test_actual_packaging_excludes_diagnostic_and_detects_distribution_leaks(tmp_path, mutation, code):
    _architecture_fixture(tmp_path)
    rules = architecture._dockerignore_rules(tmp_path / ".dockerignore")
    assert architecture._dockerignore_excludes(rules, "benchmarks/oracles/sro_particle_roundtrip_diagnostic_v1.py")
    assert not architecture._dockerignore_excludes(rules, "tools/research/sro_particle_roundtrip_diagnostic_v1.py")
    assert architecture.inspect_packaging_boundary(tmp_path) == []
    if mutation == "docker-reinclude":
        path = tmp_path / ".dockerignore"
        path.write_text(path.read_text() + "!benchmarks/**\n")
    elif mutation == "docker-copy":
        path = tmp_path / "Dockerfile.product"
        path.write_text(path.read_text() + "COPY benchmarks /app/benchmarks\n")
    else:
        path = tmp_path / "pyproject.toml"
        path.write_text(path.read_text().replace('exclude = ["benchmarks*"]', 'exclude = []'))
    assert code in {item.code for item in architecture.inspect_packaging_boundary(tmp_path)}


def test_diagnostic_workflow_registers_only_relocated_lint_and_mock_tests():
    text = (REPO / ".github/workflows/ci-sro-particle-roundtrip-diagnostic.yml").read_text()
    lines = text.splitlines()
    uses = [line.split("uses:", 1)[1].strip() for line in lines if line.lstrip().startswith("- uses:")]
    assert uses == ["actions/checkout@9c091bb21b7c1c1d1991bb908d89e4e9dddfe3e0",
                    "actions/setup-python@ece7cb06caefa5fff74198d8649806c4678c61a1"]
    commands = []
    for index, line in enumerate(lines):
        if not line.startswith("        run: "):
            continue
        command = line.removeprefix("        run: ")
        if command == "|":
            parts = []
            for following in lines[index + 1:]:
                if not following.startswith("          "):
                    break
                parts.append(following[10:])
            command = "\n".join(parts)
        commands.append(shlex.split(command.replace("\\\n", " ")))
    assert commands == [
        ["python", "-m", "pip", "install", "pytest==8.3.5", "ruff==0.11.13"],
        ["python", "-m", "ruff", "check", "--isolated", "--no-cache",
         "benchmarks/oracles/sro_particle_roundtrip_diagnostic_v1.py", "tests/unit/test_sro_particle_roundtrip_diagnostic_v1.py"],
        ["python", "-m", "pytest", "--rootdir=$PWD", "-c", "/dev/null", "--noconftest", "-p", "no:cacheprovider",
         "-W", "error", "-q", "tests/unit/test_sro_particle_roundtrip_diagnostic_v1.py"],
    ]


class FakeBoundary:
    is_real_openmm = False

    def __init__(self, fail_context=None, fail_state=None, malformed=False):
        self.fail_context, self.fail_state, self.malformed = fail_context, fail_state, malformed
        self.context_calls = self.state_calls = 0
        self.released = []

    def build_arms(self, *_):
        return {arm: [(arm, "internal"), (arm, "cross")] for arm in diag.ARMS}, [], {"synthetic_only": True}

    def context(self, system):
        self.context_calls += 1
        if self.context_calls == self.fail_context:
            raise RuntimeError("mock_context_error")
        return [system]

    def positions(self, holder, coordinates):
        holder.append(deepcopy(coordinates))

    def get_state(self, holder, groups):
        self.state_calls += 1
        if self.state_calls == self.fail_state:
            raise RuntimeError("mock_get_state_error")
        arm, scope = holder[0]
        count = len(holder[-1])
        force = [[0.0] * 3 for _ in range(count)]
        energy = 1.0 if scope == "internal" else 2.0 if groups is None else 0.5 if groups == {0} else 1.5
        if arm == diag.ARMS[1] and scope == "internal":
            force[7][2] = 4e-8
            energy += 1e-9
        if self.malformed and scope == "cross":
            force[-1][1] = float("nan")
        return energy, force

    def decode_state(self, state):
        return state

    def release(self, holder):
        self.released.append(holder[0])
        holder.clear()


@pytest.fixture
def inputs():
    coordinates = [[float(i), 0.0, 0.0] for i in range(26)]
    forces = [[0.0] * 3 for _ in range(26)]
    forces[7][2] = 4e-8
    states = [{"label": label, "coordinates": diag.hex_matrix(coordinates), "forces": diag.hex_matrix(forces),
               "energy": (3.0 + 1e-9).hex(), "components": {"ligand_internal": (1.0 + 1e-9).hex(),
                   "cross_lennard_jones": (0.5).hex(), "cross_screened_coulomb": (1.5).hex(),
                   "total": (3.0 + 1e-9).hex()}} for label in diag.LABELS]
    return {"oracle": oracle, "endpoints": {"states": states}, "receptor_coordinates": [[0.0, 50.0, 0.0]],
            "parameters": {"parameters": {"switch_start_angstrom": 90.0},
                           "cross_parameters": {"minimum_distance_angstrom": 0.35}},
            "ligand_xml": b"mock only", "receptor_xml": b"mock only"}


def test_complete_protocol_records_all_vectors_and_preserves_gate(inputs):
    boundary = FakeBoundary()
    result = diag.run_diagnostic(**inputs, backend=boundary)
    assert result["status"] == "completed"
    counts = result["call_accounting"]["counts"]
    for kind, total in (("context_create", 4), ("set_positions", 8), ("get_state", 16)):
        assert counts[kind] == {"reserved_total": total, "completed": total, "error": 0,
                                "unknown": 0, "not_dispatched": 0}
    assert len(boundary.released) == 4
    assert not result["actual_openmm_observations"]
    assert result["frozen_gate"] == 1e-8 and not result["cause_established"]
    assert not result["frozen_campaign_modified_or_resumed"]
    assert result["native_force_calls"] == result["native_score_calls"] == result["native_optimizer_calls"] == 0
    assert not result["native_term_force_vectors_available"]
    for label in diag.LABELS:
        row = result["states"][label]
        old, new = row[diag.ARMS[0]], row[diag.ARMS[1]]
        assert old["fixed_1e_minus_8_comparison"]["passed"] is False
        assert new["fixed_1e_minus_8_comparison"]["passed"] is True
        assert len(old["total_ligand_force"]["vectors_binary64_hex"]) == 26
        assert set(old["terms"]) == set(diag.TERMS)
        delta = row["arm_comparison"]["roundtrip_minus_original_total_force"]
        assert delta["max_absolute_component"] == 4e-8
        assert delta["argmax_atom_index"] == 7 and delta["argmax_axis"] == "z"
        assert row["arm_comparison"]["residual_identity_roundoff"]["max_absolute_component"] == 0.0


@pytest.mark.parametrize("fail_context,fail_state,kind,completed", [(3, None, "context_create", 2),
                                                                  (None, 11, "get_state", 10)])
def test_failures_preserve_error_and_undispatched_work(inputs, fail_context, fail_state, kind, completed):
    boundary = FakeBoundary(fail_context=fail_context, fail_state=fail_state)
    result = diag.run_diagnostic(**inputs, backend=boundary)
    assert result["status"] == "failed"
    count = result["call_accounting"]["counts"][kind]
    assert count["completed"] == completed and count["error"] == 1
    assert count["not_dispatched"] > 0 and count["unknown"] == 0
    errors = [row for row in result["call_accounting"]["calls"] if row["status"] == "error"]
    assert errors[0]["work_quantity"] == "unknown"
    assert len(boundary.released) == boundary.context_calls - int(fail_context is not None)


def test_nonfinite_receptor_output_rejected_after_counted_calls(inputs):
    result = diag.run_diagnostic(**inputs, backend=FakeBoundary(malformed=True))
    assert result["status"] == "failed" and result["failure"]["reason"] == "nonfinite_oracle_output"
    assert result["call_accounting"]["counts"]["get_state"]["completed"] == 4


def test_postprocessing_error_retains_real_observation_flag(inputs, monkeypatch):
    boundary = FakeBoundary()
    boundary.is_real_openmm = True  # Synthetic implementation, flag path coverage only.
    def failed(*_):
        raise ValueError("mock_postprocessing_error")
    monkeypatch.setattr(diag, "arm_comparison", failed)
    result = diag.run_diagnostic(**inputs, backend=boundary)
    assert result["status"] == "failed" and result["actual_openmm_observations"]
    assert result["call_accounting"]["counts"]["get_state"]["completed"] == 16


def test_ledger_interrupt_is_durably_unknown_before_dispatch():
    events = []
    ledger = diag.CallLedger(events.append)
    class Interrupted(BaseException):
        pass
    def terminate(event):
        events.append(event)
        if event["event"] == "started":
            raise Interrupted()
    ledger.event_sink = terminate
    with pytest.raises(Interrupted):
        ledger.call("context_create", diag.ARMS[0] + ".internal", lambda: pytest.fail("must not dispatch"))
    assert ledger.rows[0]["status"] == "unknown"
    assert ledger.receipt()["counts"]["context_create"]["unknown"] == 1
    assert len([row for row in events if row["event"] == "reserved"]) == 28


def test_particle_float_hex_ulp_and_exact_delta():
    sigma = float.fromhex("0x1.3333333333333p-2")
    native_sigma = sigma * 10
    native_sigma = __import__("math").nextafter(native_sigma, float("inf"))
    records, values = diag.particle_table([(0.25, sigma, 0.4)],
        [{"atom_index": 0, "charge_e": 0.25, "sigma_angstrom": native_sigma,
          "epsilon_kcal_per_mol": 0.4 / 4.184}], "synthetic")
    field = records[0]["fields"]["sigma"]
    assert field["changed"] and field["original_vs_roundtrip_ulp_distance"] >= 1
    assert values[0][1] == native_sigma / 10
    assert int(field["roundtrip_minus_original"]["exact_numerator"]) != 0
    assert diag.ulp_distance(-0.0, 0.0) == 1
    assert diag.exact_delta(-0.0, 0.0)["exact_numerator"] == "0"


@pytest.mark.parametrize("mutate_exception", [False, True])
def test_real_boundary_reuses_builder_and_rejects_nonparticle_mutation(mutate_exception):
    class ToyForce:
        def __init__(self, rows):
            self.rows = deepcopy(rows)
        def getNumPerParticleParameters(self):
            return 3
        def getPerParticleParameterName(self, i):
            return ("q", "sig", "eps")[i]
        def getNumParticles(self):
            return len(self.rows)
        def setParticleParameters(self, i, row):
            self.rows[i] = list(row)
    class ToySystem:
        def __init__(self, forces, stable):
            self.forces, self.stable = forces, stable
        def getForces(self):
            return self.forces
    class Serializer:
        @staticmethod
        def serialize(system):
            return diag.canonical({"rows": [f.rows for f in system.forces], "stable": system.stable}).decode()
        @staticmethod
        def deserialize(text):
            if text in ("ligand", "receptor"):
                return text
            value = __import__("json").loads(text)
            return ToySystem([ToyForce(rows) for rows in value["rows"]], value["stable"])
    source_ligand = [(0.25, 0.3, 0.4)] * 26
    source_receptor = [(-0.25, 0.3, 0.4)]
    class Builder:
        mm = types.SimpleNamespace(CustomNonbondedForce=ToyForce, XmlSerializer=Serializer)
        def __init__(self):
            self.calls = []
        def _particles(self, source):
            return source_ligand if source == "ligand" else source_receptor
        def build(self, ligand_xml, receptor_xml, parameters):
            self.calls.append((ligand_xml, receptor_xml, parameters))
            stable = {"exceptions": [1, 4, 0.5, 0.2, 0.9], "bonded": ["unchanged"], "groups": [0, 1], "cutoff": 1.2}
            if mutate_exception and len(self.calls) == 2:
                stable["exceptions"][2] = 0.6
            return (ToySystem([ToyForce(source_ligand)], deepcopy(stable)),
                    ToySystem([ToyForce(source_ligand + source_receptor) for _ in range(2)], deepcopy(stable)))
    boundary = diag.RealBoundary.__new__(diag.RealBoundary)
    boundary.base = Builder()
    sigma = __import__("math").nextafter(3.0, float("inf"))
    def native(rows):
        return [{"atom_index": i, "charge_e": q, "sigma_angstrom": sigma,
                 "epsilon_kcal_per_mol": e / 4.184} for i, (q, _, e) in enumerate(rows)]
    parameters = {"parameters": {"atom_parameters": native(source_ligand)},
                  "cross_parameters": {"receptor_atoms": native(source_receptor)}}
    if mutate_exception:
        with pytest.raises(ValueError, match="nonparticle_intervention"):
            boundary.build_arms(b"ligand", b"receptor", parameters)
        return
    arms, particles, invariants = boundary.build_arms(b"ligand", b"receptor", parameters)
    assert len(boundary.base.calls) == 2 and boundary.base.calls[0] == boundary.base.calls[1]
    assert len(particles) == 27 and particles[-1]["scope"] == "receptor"
    for scope in ("internal", "cross"):
        assert invariants[scope]["all_nonintervened_system_fields_identical"]
    assert arms[diag.ARMS[0]][0].stable == arms[diag.ARMS[1]][0].stable
    assert arms[diag.ARMS[0]][0].forces[0].rows[0][1] != arms[diag.ARMS[1]][0].forces[0].rows[0][1]


@pytest.mark.parametrize("mutation", ["extra", "missing", "hash", "protected", "original_ligand", "wrong_name"])
def test_numerical_roles_rejected_without_body_open(tmp_path, monkeypatch, mutation):
    names = {"ligand_xml": "ligand-unconstrained-openmm-system.xml", "receptor_xml": "openmm-system.xml",
             "receptor_coordinates": "receptor-canonical.json", "parameters": "parameters.json",
             "extensions": "extensions.json", "cross_parameters": "cross-parameters.json"}
    hashes = {**oracle.ORIGINAL_SHA256, "ligand_xml": oracle.XML_SHA256["ligand"], "receptor_xml": oracle.XML_SHA256["receptor"]}
    refs = {}
    for role, name in names.items():
        path = tmp_path / name
        path.write_bytes(b"synthetic metadata stub")
        refs[role] = {"path": str(path), "bytes": path.stat().st_size, "sha256": hashes.get(role, "c" * 64)}
    if mutation == "extra":
        refs["extra"] = refs["parameters"]
    elif mutation == "missing":
        del refs["extensions"]
    elif mutation == "hash":
        refs["parameters"]["sha256"] = "d" * 64
    elif mutation == "protected":
        refs["receptor_coordinates"]["path"] = str(tmp_path / "evaluation_only/receptor-canonical.json")
    elif mutation == "original_ligand":
        refs["receptor_coordinates"]["path"] = str(tmp_path / "ligand-canonical.json")
    else:
        refs["parameters"]["path"] = str(tmp_path / "extensions.json")
    opened = []
    monkeypatch.setattr(diag.os, "open", lambda *args, **kwargs: opened.append(args) or pytest.fail("body open forbidden"))
    with pytest.raises(ValueError):
        diag.validate_numerical_roles(refs, oracle)
    assert opened == []


def test_pin_requires_pathrole_and_rejects_protected_or_nonregular_before_open(tmp_path, monkeypatch):
    source = tmp_path / "a.py"
    source.write_bytes(b"pass")
    opened = []
    monkeypatch.setattr(diag.os, "open", lambda *args, **kwargs: opened.append(args) or pytest.fail("body open forbidden"))
    with pytest.raises(ValueError, match="pin_role"):
        diag.pin(source, allowed_paths=[])
    with pytest.raises(ValueError, match="regular_file"):
        diag.pin(tmp_path, allowed_paths=[tmp_path])
    protected = tmp_path / "evaluation_only/a.py"
    with pytest.raises(ValueError, match="forbidden"):
        diag.pin(protected, allowed_paths=[protected])
    assert opened == []


def test_execute_requires_authorization_before_any_read(monkeypatch):
    monkeypatch.setattr(diag, "pin", lambda *a, **k: pytest.fail("pin before authorization"))
    with pytest.raises(ValueError, match="explicit_numerical_phase_authorization"):
        diag.execute_plan("/never/plan.json", "a" * 64, "/never/output")


def test_prepare_rejects_campaign_output_before_any_body_read(monkeypatch):
    monkeypatch.setattr(diag, "pin", lambda *a, **k: pytest.fail("pin before output boundary"))
    with pytest.raises(ValueError, match="output_inside_frozen_campaign"):
        diag.prepare_plan(diag.FROZEN_R2, diag.FROZEN_R2 / "new-diagnostic-no-create", "/never/test", "/never/doc")


def test_load_oracle_executes_verified_raw_bytes_without_import_cache(tmp_path, monkeypatch):
    source = tmp_path / "oracle.py"
    source.write_bytes(b"SENTINEL = 'verified source'\n")
    ref = diag.pin(source, allowed_paths=[source])
    monkeypatch.setattr(diag, "FROZEN_ORACLE_SHA256", ref["sha256"])
    def verify_then_change(ref):
        raw = source.read_bytes()
        source.write_bytes(b"raise RuntimeError('unverified later source')\n")
        return raw
    monkeypatch.setattr(diag, "read_ref", verify_then_change)
    module = diag.load_oracle(ref)
    assert module.SENTINEL == "verified source"


def test_plan_ref_substitution_fails_before_numerical_read(tmp_path, monkeypatch):
    terminal = tmp_path / "R2"
    monkeypatch.setattr(diag, "FROZEN_R2", terminal)
    metadata = {"terminal_plan": terminal / "plan.json", "oracle_input_spec": terminal / "oracle-input-spec.json",
                "saved_endpoint_states": terminal / "campaign/perturbed_02/native/endpoint-states.json",
                "saved_oracle_receipt": terminal / "campaign/perturbed_02/oracle/numerical-receipt.json"}
    expected = {role: {"path": str(tmp_path / role), "bytes": 1, "sha256": "e" * 64} for role in diag.NUMERICAL_ROLES}
    spec = {"ligand_xml_ref": expected["ligand_xml"], "receptor_xml_ref": expected["receptor_xml"],
            "original_parameter_refs": {role: expected[role] for role in oracle.IDENTITIES}}
    old_plan = {"cases": [{"case_id": diag.CASE, "derived_input_refs": {"receptor": expected["receptor_coordinates"]}}]}
    touched = []
    def read(ref):
        touched.append(ref["path"])
        if ref["path"] == str(metadata["terminal_plan"]):
            return diag.canonical(old_plan)
        if ref["path"] == str(metadata["oracle_input_spec"]):
            return diag.canonical(spec)
        pytest.fail("numerical body opened")
    monkeypatch.setattr(diag, "read_ref", read)
    modified = deepcopy(expected)
    modified["receptor_coordinates"]["path"] += "-unapproved"
    plan = {"frozen_terminal_campaign_root": str(terminal), "metadata_refs": {role: {"path": str(path)} for role, path in metadata.items()},
            "numerical_input_refs": modified}
    with pytest.raises(ValueError, match="exact_terminal_numerical_refs"):
        diag.numerical_inputs(plan, oracle, [])
    assert touched == [str(metadata["terminal_plan"]), str(metadata["oracle_input_spec"])]


@pytest.mark.parametrize("extra_original_role", [False, True])
def test_prepare_reads_metadata_code_and_saved_observations_only(tmp_path, inputs, monkeypatch, extra_original_role):
    r2 = tmp_path / "frozen-terminal"
    r2.mkdir()
    monkeypatch.setattr(diag, "FROZEN_R2", r2)
    source_dir = r2 / "source"
    source_dir.mkdir()
    frozen_source = source_dir / "sro_recovery_endpoint_numerics_v1.py"
    frozen_source.write_bytes(ORACLE.read_bytes())
    oracle_ref = diag.pin(frozen_source, allowed_paths=[frozen_source])
    names = {"ligand_xml": "ligand-unconstrained-openmm-system.xml", "receptor_xml": "openmm-system.xml",
             "receptor_coordinates": "receptor-canonical.json", "parameters": "parameters.json",
             "extensions": "extensions.json", "cross_parameters": "cross-parameters.json"}
    hashes = {**oracle.ORIGINAL_SHA256, "ligand_xml": oracle.XML_SHA256["ligand"], "receptor_xml": oracle.XML_SHA256["receptor"]}
    numeric_refs = {}
    for role, name in names.items():
        path = tmp_path / name
        path.write_bytes(b"synthetic NEVER OPENED")
        numeric_refs[role] = {"path": str(path), "bytes": path.stat().st_size, "sha256": hashes.get(role, "a" * 64)}
    request = {"path": str(r2 / "metadata-request.json"), "bytes": 10, "sha256": "c" * 64}
    endpoints = {"schema_id": oracle.ENDPOINT_SCHEMA, "case_id": diag.CASE,
                 "request_sha256": "d" * 64, "binding_receipt_sha256": "e" * 64,
                 "native_artifact_refs": [], "states": inputs["endpoints"]["states"]}
    endpoint_path = r2 / "campaign/perturbed_02/native/endpoint-states.json"
    endpoint_path.parent.mkdir(parents=True)
    endpoint_path.write_bytes(diag.canonical(endpoints))
    endpoint_ref = diag.pin(endpoint_path, allowed_paths=[endpoint_path])
    receipt = {"schema_id": oracle.SCHEMA, "case_id": diag.CASE, "endpoint_states_ref": endpoint_ref,
               "source_sha256": diag.FROZEN_ORACLE_SHA256, "status": "failed",
               "energy_absolute_tolerance_kcal_per_mol": 1e-8,
               "force_component_absolute_tolerance_kcal_per_mol_angstrom": 1e-8,
               "request_ref": request, "protocol_sha256": oracle.PROTOCOL_SHA256,
               "manifest_sha256": oracle.MANIFEST_SHA256}
    receipt["receipt_sha256"] = oracle.value_hash(receipt)
    receipt_path = r2 / "campaign/perturbed_02/oracle/numerical-receipt.json"
    receipt_path.parent.mkdir(parents=True)
    receipt_path.write_bytes(diag.canonical(receipt))
    old_plan = {"cases": [{"case_id": diag.CASE, "request_file_ref": request,
                            "derived_input_refs": {"receptor": numeric_refs["receptor_coordinates"]},
                            "derived_system_sha256": "f" * 64, "derived_topology_sha256": "b" * 64}],
                "protocol_sha256": oracle.PROTOCOL_SHA256, "manifest_sha256": oracle.MANIFEST_SHA256,
                "oracle_phase": {"python_binary_ref": {"path": "/never/python", "bytes": 1, "sha256": "c" * 64}}}
    spec_data = {"schema_id": "sro_endpoint_oracle_input_spec/1", "dependency_site": "/never/site",
                 "ligand_xml_ref": numeric_refs["ligand_xml"], "receptor_xml_ref": numeric_refs["receptor_xml"],
                 "oracle_source_ref": oracle_ref, "original_parameter_refs": {role: numeric_refs[role] for role in oracle.IDENTITIES}}
    if extra_original_role:
        spec_data["original_parameter_refs"]["unapproved_extra"] = numeric_refs["parameters"]
    (r2 / "plan.json").write_bytes(diag.canonical(old_plan))
    (r2 / "oracle-input-spec.json").write_bytes(diag.canonical(spec_data))
    doc = tmp_path / "sro_particle_roundtrip_diagnostic_plan_20260930.md"
    doc.write_text("synthetic plan document only\n")
    opened = []
    real_open = diag.os.open
    forbidden_paths = {ref["path"] for ref in numeric_refs.values()}
    def checked_open(path, *args, **kwargs):
        opened.append(str(path))
        assert str(path) not in forbidden_paths, "numerical body opened during prepare"
        return real_open(path, *args, **kwargs)
    monkeypatch.setattr(diag.os, "open", checked_open)
    output = tmp_path / "new-prospective-plan"
    if extra_original_role:
        with pytest.raises(ValueError, match="exact_spec_roles"):
            diag.prepare_plan(r2, output, __file__, doc)
        assert not output.exists()
    else:
        ref = diag.prepare_plan(r2, output, __file__, doc)
        plan = __import__("json").loads(diag.read_ref(ref))
        assert plan["protocol_counts"] == {"context_create": 4, "set_positions": 8, "get_state": 16}
        assert plan["numerical_input_refs"] == numeric_refs
        assert not plan["actual_execution_performed"] and not plan["campaign_resume_allowed"]
        assert len(plan["saved_state_pins"]) == 2
    assert not forbidden_paths.intersection(opened)

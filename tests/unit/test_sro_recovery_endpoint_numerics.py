"""Synthetic endpoints and injected boundaries; no real OpenMM/native calls."""

from copy import deepcopy
import importlib.util
from pathlib import Path

import pytest


SOURCE = Path(__file__).resolve().parents[2] / "benchmarks/oracles/sro_recovery_endpoint_numerics_v1.py"
SPEC = importlib.util.spec_from_file_location("sro_endpoint_oracle_test", SOURCE)
oracle = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(oracle)


def pin(path, value, *, raw=False):
    data = value if raw else oracle.canonical(value)
    path.write_bytes(data)
    return {"path": str(path.resolve()), "sha256": oracle.sha(data), "bytes": len(data)}


def hex_matrix(rows):
    return [[float(v).hex() for v in row] for row in rows]


def system_document(rows):
    system = {"coordinates": {"coordinate_unit": "angstrom", "cell_vectors": None,
                              "cell_periodic": None, "coordinates": {"$tensor": {
                                  "dtype": "float64", "shape": [1, len(rows), 3],
                                  "values": [{"$float_hex": float(v).hex()} for row in rows for v in row]}}}}
    return {"schema_id": "betelgeuze.engine_v2_canonical_system/1.0.0",
            "system": system, "system_sha256": oracle.value_hash(system)}


def xml(count, *, ligand):
    particles = "".join('<Particle mass="12"/>' for _ in range(count))
    nb = '<Force type="NonbondedForce" method="0"><Particles>' + ''.join(
        '<Particle q="0" sig=".3" eps=".4"/>' for _ in range(count)) + '</Particles><Exceptions/></Force>'
    bonded = ''.join('<Force type="' + kind + '" usesPeriodic="0"/>' for kind in
                     ("HarmonicBondForce", "HarmonicAngleForce", "PeriodicTorsionForce")) if ligand else ''
    return ('<System><Particles>' + particles + '</Particles><Constraints/><Forces>' +
            bonded + nb + '</Forces></System>').encode()


class FakeBoundary:
    """Only returns supplied scalars; it cannot import or dispatch molecular work."""
    is_real_openmm = False

    def __init__(self, *, fail_context=None, fail_observe=None, energy_delta=0.0,
                 force_delta=0.0, malformed=None, after_observe=None):
        self.context_attempts = 0
        self.observe_attempts = 0
        self.released = []
        self.fail_context = fail_context
        self.fail_observe = fail_observe
        self.energy_delta = energy_delta
        self.force_delta = force_delta
        self.malformed = malformed
        self.after_observe = after_observe

    def build(self, ligand_xml, receptor_xml, derived):
        self.receptor_count = len(derived["cross_parameters"]["receptor_atoms"])
        return "internal", "cross"

    def context(self, system):
        self.context_attempts += 1
        if self.context_attempts == self.fail_context:
            raise RuntimeError("synthetic_context_failure")
        return [system, None]

    def positions(self, holder, coordinates):
        holder[1] = deepcopy(coordinates)

    def observe(self, holder, groups):
        self.observe_attempts += 1
        if self.observe_attempts == self.fail_observe:
            raise RuntimeError("synthetic_get_state_failure")
        count = 26 if holder[0] == "internal" else 26 + self.receptor_count
        energy = 1.0 if holder[0] == "internal" else 2.0 if groups is None else .5 if groups == {0} else 1.5
        if holder[0] == "internal":
            energy += self.energy_delta
        forces = [[0.0, 0.0, 0.0] for _ in range(count)]
        if holder[0] == "internal":
            forces[0][0] = self.force_delta
        if self.malformed == "force_count":
            forces.pop()
        if self.malformed == "nan_receptor" and holder[0] == "cross":
            forces[-1][0] = float("nan")
        if self.malformed == "nan_energy":
            energy = float("nan")
        if self.after_observe is not None:
            self.after_observe(self.observe_attempts)
        return energy, forces

    def get_state(self, holder, groups):
        return self.observe(holder, groups)

    def decode_state(self, state):
        return state

    def release(self, holder):
        self.released.append(holder[0])
        holder.clear()

    def environment(self):
        return {"boundary": "injected_synthetic", "actual_openmm_calls": 0}


@pytest.fixture
def inputs(tmp_path, monkeypatch):
    ligand_xml = pin(tmp_path / "ligand.xml", xml(26, ligand=True), raw=True)
    receptor_xml = pin(tmp_path / "receptor.xml", xml(1, ligand=False), raw=True)
    monkeypatch.setattr(oracle, "XML_SHA256", {"ligand": ligand_xml["sha256"], "receptor": receptor_xml["sha256"]})
    wheel = pin(tmp_path / "old.whl", b"synthetic wheel only", raw=True)
    monkeypatch.setattr(oracle, "OLD_WHEEL_SHA256", wheel["sha256"])
    original_base = {"topology_sha256": "a" * 64, "atom_parameters": [
        {"atom_index": i, "charge_e": 0.0, "sigma_angstrom": 3.0,
         "epsilon_kcal_per_mol": .4 / 4.184} for i in range(26)],
        "dielectric": 1.0, "screening_kappa_per_angstrom": 0.0,
        "switch_start_angstrom": 90.0, "cutoff_angstrom": 100.0,
        "minimum_pair_distance_angstrom": .35, "ordered_terms": [1.0, -0.0]}
    original_ext = {"topology_sha256": "a" * 64,
                    "base_parameter_fingerprint_sha256": oracle.value_hash(original_base),
                    "metadata": {"source_xml_sha256": ligand_xml["sha256"],
                                 "openmm_xml_sha256": ligand_xml["sha256"]},
                    "constraints": [], "impropers": [],
                    "nonbonded_domain": "nocutoff_equivalent_inside_switch"}
    original_cross = {"ligand_topology_sha256": "a" * 64,
                      "ligand_base_parameters_sha256": oracle.value_hash(original_base),
                      "parameter_source_sha256": receptor_xml["sha256"],
                      "receptor_atoms": [{"atom_index": 0, "charge_e": 0.0,
                                          "sigma_angstrom": 3.0, "epsilon_kcal_per_mol": .4 / 4.184}],
                      "mixing_rule": "lorentz_berthelot", "pair_policy": "all_non_covalent_cross_pairs_no_exclusions",
                      "switch_start_angstrom": 10.0, "cutoff_angstrom": 12.0,
                      "dielectric": 4.0, "screening_kappa_per_angstrom": .1,
                      "minimum_distance_angstrom": .35}
    originals = dict(zip(oracle.IDENTITIES, (original_base, original_ext, original_cross), strict=True))
    original_refs = {name: pin(tmp_path / ("original-" + name + ".json"), value)
                     for name, value in originals.items()}
    monkeypatch.setattr(oracle, "ORIGINAL_SHA256", {k: v["sha256"] for k, v in original_refs.items()})
    base = deepcopy(original_base)
    base["topology_sha256"] = "b" * 64
    ext, cross = deepcopy(original_ext), deepcopy(original_cross)
    ext.update(topology_sha256="b" * 64, base_parameter_fingerprint_sha256=oracle.value_hash(base))
    cross.update(ligand_topology_sha256="b" * 64, ligand_base_parameters_sha256=oracle.value_hash(base))
    derived = dict(zip(oracle.IDENTITIES, (base, ext, cross), strict=True))
    ligand_coords = [[float(i), 0.0, 0.0] for i in range(26)]
    files = {"ligand": pin(tmp_path / "derived-ligand.json", system_document(ligand_coords)),
             "receptor": pin(tmp_path / "derived-receptor.json", system_document([[0.0, 10.0, 0.0]]))}
    files.update({name: pin(tmp_path / ("derived-" + name + ".json"), value) for name, value in derived.items()})
    request = {name: {k: v for k, v in ref.items() if k != "bytes"} for name, ref in files.items()}
    request_ref = pin(tmp_path / "request.json", request)
    binding = {"request_sha256": oracle.value_hash(request), "input_files": request}
    binding["receipt_sha256"] = oracle.value_hash(binding)
    binding_ref = pin(tmp_path / "binding.json", {"input_binding": binding, "executed_wheel": wheel})
    native = pin(tmp_path / "native-result.json", {"synthetic_only": True})
    states = [{"label": label, "coordinates": hex_matrix(ligand_coords if label == "initial" else
               [[x + .25, y, z] for x, y, z in ligand_coords]), "energy": (3.0).hex(),
               "forces": hex_matrix([[0.0] * 3 for _ in range(26)]), "components": {
                   "ligand_internal": (1.0).hex(), "cross_lennard_jones": (.5).hex(),
                   "cross_screened_coulomb": (1.5).hex(), "total": (3.0).hex()}} for label in oracle.LABELS]
    endpoints = {"schema_id": oracle.ENDPOINT_SCHEMA, "case_id": "perturbed_01",
                 "request_sha256": binding["request_sha256"], "binding_receipt_sha256": binding["receipt_sha256"],
                 "native_artifact_refs": [native], "states": states}
    endpoint_ref = pin(tmp_path / "endpoint-states.json", endpoints)
    arguments = {"case_id": "perturbed_01", "request_ref": request_ref, "binding_ref": binding_ref,
                 "endpoint_states_ref": endpoint_ref, "ligand_xml_ref": ligand_xml,
                 "receptor_xml_ref": receptor_xml, "original_parameter_refs": original_refs,
                 "wheel_ref": wheel, "protocol_sha256": oracle.PROTOCOL_SHA256,
                 "manifest_sha256": oracle.MANIFEST_SHA256}
    return {"arguments": arguments, "endpoints": endpoints, "originals": originals,
            "derived": derived, "request": request, "binding": binding, "tmp": tmp_path}


def run(inputs, backend=None):
    return oracle.audit_case(**inputs["arguments"], backend=backend or FakeBoundary())


def rewrite_endpoints(inputs):
    old = inputs["arguments"]["endpoint_states_ref"]
    inputs["arguments"]["endpoint_states_ref"] = pin(Path(old["path"]), inputs["endpoints"])


def rewrite_request_binding(inputs):
    args = inputs["arguments"]
    args["request_ref"] = pin(Path(args["request_ref"]["path"]), inputs["request"])
    binding = inputs["binding"]
    binding.update(request_sha256=oracle.value_hash(inputs["request"]), input_files=inputs["request"])
    binding.pop("receipt_sha256")
    binding["receipt_sha256"] = oracle.value_hash(binding)
    args["binding_ref"] = pin(Path(args["binding_ref"]["path"]), {"input_binding": binding, "executed_wheel": args["wheel_ref"]})
    inputs["endpoints"].update(request_sha256=binding["request_sha256"], binding_receipt_sha256=binding["receipt_sha256"])
    rewrite_endpoints(inputs)


def test_two_states_have_two_contexts_eight_states_and_no_real_calls(inputs):
    backend = FakeBoundary()
    result = run(inputs, backend)
    assert result["status"] == "passed"
    assert result["denominator"] == {"requested": 2, "evaluated": 2, "passed": 2, "failed": 0, "unknown": 0}
    counts = result["openmm_accounting"]["counts"]
    assert counts["context_create"] == {"attempted": 2, "completed": 2, "failed": 0}
    assert counts["get_state"] == {"attempted": 8, "completed": 8, "failed": 0}
    assert counts["set_positions"]["completed"] == 4
    assert counts["context_release"]["completed"] == 2
    assert backend.released == ["cross", "internal"]
    assert not result["openmm_observations_performed"]
    assert not result["scientifically_validated"] and not result["actual_execution_authorized"]
    assert result["new_native_force_calls"] == result["new_native_score_calls"] == 0
    assert result["receipt_sha256"] == oracle.value_hash({k: v for k, v in result.items() if k != "receipt_sha256"})


@pytest.mark.parametrize("field,token", [("energy", "nan"), ("energy", "0x1p+0"), ("forces", "inf"), ("coordinates", "nan")])
def test_nonfinite_or_noncanonical_binary64_preflight(inputs, field, token):
    state = inputs["endpoints"]["states"][0]
    if field == "energy":
        state[field] = token
    else:
        state[field][0][0] = token
    rewrite_endpoints(inputs)
    result = run(inputs)
    assert result["status"] == "failed" and result["denominator"]["unknown"] == 2
    assert result["openmm_accounting"]["calls"] == []


@pytest.mark.parametrize("mutation", ["one_state", "reversed", "coordinate_count", "force_count", "initial_changed", "extra_component"])
def test_endpoint_shape_order_and_identity_gates(inputs, mutation):
    states = inputs["endpoints"]["states"]
    if mutation == "one_state":
        states.pop()
    elif mutation == "reversed":
        states.reverse()
    elif mutation == "coordinate_count":
        states[1]["coordinates"].pop()
    elif mutation == "force_count":
        states[1]["forces"].pop()
    elif mutation == "initial_changed":
        states[0]["coordinates"][0][0] = (.5).hex()
    else:
        states[1]["components"]["undeclared"] = (0.0).hex()
    rewrite_endpoints(inputs)
    result = run(inputs)
    assert result["status"] == "failed" and not result["openmm_accounting"]["calls"]


@pytest.mark.parametrize("energy_delta,force_delta", [(1e-6, 0.0), (0.0, 1e-6)])
def test_completed_numerical_failure_retains_both_comparisons(inputs, energy_delta, force_delta):
    result = run(inputs, FakeBoundary(energy_delta=energy_delta, force_delta=force_delta))
    assert result["failure"] is None
    assert result["status"] == "failed"
    assert result["denominator"] == {"requested": 2, "evaluated": 2, "passed": 0, "failed": 2, "unknown": 0}
    assert result["openmm_accounting"]["counts"]["get_state"]["completed"] == 8


@pytest.mark.parametrize("kind", ["force_count", "nan_receptor", "nan_energy"])
def test_all_backend_array_shapes_and_finite_values_checked(inputs, kind):
    result = run(inputs, FakeBoundary(malformed=kind))
    assert result["status"] == "failed" and result["failure"] is not None
    assert result["denominator"]["unknown"] == 1


def test_context_failure_retains_partial_attempts_and_releases_created_context(inputs):
    backend = FakeBoundary(fail_context=2)
    result = run(inputs, backend)
    assert result["denominator"]["unknown"] == 2
    assert result["openmm_accounting"]["counts"]["context_create"] == {"attempted": 2, "completed": 1, "failed": 1}
    assert result["openmm_accounting"]["counts"]["context_release"]["completed"] == 1
    assert backend.released == ["internal"]


def test_get_state_failure_retains_failed_state_and_unknown_denominator(inputs):
    result = run(inputs, FakeBoundary(fail_observe=6))
    assert result["denominator"] == {"requested": 2, "evaluated": 1, "passed": 1, "failed": 1, "unknown": 0}
    assert result["states"][1]["comparison_completed"] is False
    assert result["openmm_accounting"]["counts"]["get_state"] == {"attempted": 6, "completed": 5, "failed": 1}
    assert result["openmm_accounting"]["failed_call_work_quantities_unknown"] == [
        {"kind": "get_state", "label": "last_accepted.cross"}]


def test_file_change_after_observation_fails_publication(inputs):
    path = Path(inputs["arguments"]["original_parameter_refs"]["parameters"]["path"])
    def mutate(attempt):
        if attempt == 8:
            path.write_bytes(path.read_bytes() + b" ")
    result = run(inputs, FakeBoundary(after_observe=mutate))
    assert result["status"] == "failed"
    assert result["failure"]["reason"] == "source_size_changed"
    assert not result["all_same_math_checks_passed"]
    assert result["openmm_accounting"]["counts"]["get_state"]["completed"] == 8


@pytest.mark.parametrize("mutation", ["type", "order", "signed_zero", "value"])
def test_numeric_reproof_rejects_derived_mutations(inputs, mutation):
    value = inputs["derived"]["parameters"]
    if mutation == "type":
        value["ordered_terms"][0] = 1
    elif mutation == "order":
        value["ordered_terms"].reverse()
    elif mutation == "signed_zero":
        value["ordered_terms"][1] = 0.0
    else:
        value["dielectric"] = 2.0
    ref = pin(inputs["tmp"] / "derived-parameters.json", value)
    inputs["request"]["parameters"] = {k: v for k, v in ref.items() if k != "bytes"}
    rewrite_request_binding(inputs)
    result = run(inputs)
    assert result["failure"]["reason"] == "numeric_parameter_mutation"
    assert not result["openmm_accounting"]["calls"]


def test_repinned_original_and_derived_cannot_change_frozen_source(inputs):
    value = inputs["originals"]["parameters"]
    value["dielectric"] = 2.0
    args = inputs["arguments"]
    args["original_parameter_refs"]["parameters"] = pin(Path(args["original_parameter_refs"]["parameters"]["path"]), value)
    inputs["derived"]["parameters"]["dielectric"] = 2.0
    ref = pin(inputs["tmp"] / "derived-parameters.json", inputs["derived"]["parameters"])
    inputs["request"]["parameters"] = {k: v for k, v in ref.items() if k != "bytes"}
    rewrite_request_binding(inputs)
    result = run(inputs)
    assert result["failure"]["reason"] == "frozen_original_parameter_hash_mismatch"
    assert result["openmm_accounting"]["calls"] == []


@pytest.mark.parametrize("field", ["protocol_sha256", "manifest_sha256", "wheel_ref", "ligand_xml_ref", "receptor_xml_ref"])
def test_frozen_contract_and_source_pins(inputs, field):
    if field.endswith("sha256"):
        inputs["arguments"][field] = "f" * 64
    else:
        inputs["arguments"][field]["sha256"] = "f" * 64
    result = run(inputs)
    assert result["status"] == "failed" and result["openmm_accounting"]["calls"] == []


def test_undeclared_xml_terms_rejected_before_context(inputs, monkeypatch):
    args = inputs["arguments"]
    raw = xml(26, ligand=True).replace(b"</Forces>", b'<Force type="CustomExternalForce"/></Forces>')
    args["ligand_xml_ref"] = pin(Path(args["ligand_xml_ref"]["path"]), raw, raw=True)
    monkeypatch.setitem(oracle.XML_SHA256, "ligand", args["ligand_xml_ref"]["sha256"])
    for name in ("extensions",):
        for collection in (inputs["originals"], inputs["derived"]):
            collection[name]["metadata"] = {"source_xml_sha256": args["ligand_xml_ref"]["sha256"],
                                             "openmm_xml_sha256": args["ligand_xml_ref"]["sha256"]}
        args["original_parameter_refs"][name] = pin(Path(args["original_parameter_refs"][name]["path"]), inputs["originals"][name])
        monkeypatch.setitem(oracle.ORIGINAL_SHA256, name, args["original_parameter_refs"][name]["sha256"])
        ref = pin(inputs["tmp"] / ("derived-" + name + ".json"), inputs["derived"][name])
        inputs["request"][name] = {k: v for k, v in ref.items() if k != "bytes"}
    rewrite_request_binding(inputs)
    result = run(inputs)
    assert result["failure"]["reason"] == "unsupported_or_duplicate_source_force"
    assert result["openmm_accounting"]["calls"] == []


def test_reference_and_alias_paths_are_not_read(tmp_path):
    directory = tmp_path / "evaluation_only"
    directory.mkdir()
    ref = pin(directory / "reference.json", {})
    with pytest.raises(oracle.EndpointAuditError, match="reference_body_forbidden"):
        oracle.read_bound(ref)
    target = tmp_path / "target.json"
    ref = pin(target, {})
    alias = tmp_path / "alias.json"
    alias.symlink_to(target)
    with pytest.raises(oracle.EndpointAuditError, match="source_path_alias"):
        oracle.read_bound({**ref, "path": str(alias)})


def test_no_product_or_original_oracle_imports():
    import ast
    tree = ast.parse(SOURCE.read_text())
    imported = [node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)]
    imported += [name.name for node in ast.walk(tree) if isinstance(node, ast.Import) for name in node.names]
    assert all(not name.startswith(("betelgeuze", "tools.analysis")) for name in imported)


@pytest.mark.parametrize("x,expected", [(90.0, "internal_pair_outside_nocutoff_equivalence"),
                                       (100.0, "internal_pair_outside_nocutoff_equivalence")])
def test_internal_pair_domain_rejected_before_contexts(inputs, x, expected):
    inputs["endpoints"]["states"][1]["coordinates"][-1][0] = (x + .25).hex()
    rewrite_endpoints(inputs)
    result = run(inputs)
    assert result["failure"]["reason"] == expected
    assert result["openmm_accounting"]["calls"] == []


def test_cross_minimum_distance_domain_rejected_before_contexts(inputs):
    inputs["endpoints"]["states"][1]["coordinates"][0] = hex_matrix([[0.0, 10.0, 0.0]])[0]
    rewrite_endpoints(inputs)
    result = run(inputs)
    assert result["failure"]["reason"] == "cross_pair_below_native_domain"
    assert result["openmm_accounting"]["calls"] == []


def test_environment_failure_retains_completed_work(inputs):
    backend = FakeBoundary()
    def failure():
        raise RuntimeError("synthetic_environment_failure")
    backend.environment = failure
    result = run(inputs, backend)
    assert result["status"] == "failed" and result["failure"]["reason"] == "synthetic_environment_failure"
    assert result["denominator"]["evaluated"] == 2
    assert result["openmm_accounting"]["counts"]["get_state"]["completed"] == 8
    assert result["openmm_accounting"]["counts"]["environment_inventory"]["failed"] == 1


def test_release_drops_owned_references_in_measured_scope():
    import weakref
    class Owned:
        pass
    holder = [Owned(), Owned()]
    context, integrator = map(weakref.ref, holder)
    boundary = object.__new__(oracle.OpenMMBoundary)
    meter = oracle.Accounting()
    meter.call("context_release", "synthetic", boundary.release, holder)
    assert holder == [] and context() is None and integrator() is None
    assert meter.receipt()["counts"]["context_release"]["completed"] == 1


class Quantity:
    def __init__(self, value):
        self.value = value
    def value_in_unit(self, unit):
        return self.value


class FakeSourceForce:
    def setForceGroup(self, group):
        self.group = group


class FakeNB(FakeSourceForce):
    NoCutoff = 0
    def __init__(self, count):
        self.count = count
        self.exceptions = [(0, 1, 0.0, .3, 0.0), (0, 2, -.2, .3, .1)] if count == 26 else []
    def getNumGlobalParameters(self):
        return 0
    def getNumParticleParameterOffsets(self):
        return 0
    def getNumExceptionParameterOffsets(self):
        return 0
    def getNumParticles(self):
        return self.count
    def getParticleParameters(self, index):
        return tuple(Quantity(v) for v in (0.0, .3, .4))
    def getNonbondedMethod(self):
        return self.NoCutoff
    def getNumExceptions(self):
        return len(self.exceptions)
    def getExceptionParameters(self, index):
        a, b, *values = self.exceptions[index]
        return a, b, *(Quantity(v) for v in values)


class FakeSystem:
    def __init__(self, count=0, *, source=False):
        self.masses = [Quantity(12.0) for _ in range(count)]
        self.forces = [FakeNB(count)] if source else []
        if source and count == 26:
            torsions = FakeSourceForce()
            # Synthetic retained positive, periodic-improper and negative terms.
            torsions.source_terms = [(1, 2, 3, 4, 3, .7), (4, 3, 2, 1, 2, .2), (0, 2, 3, 1, 1, -.4)]
            self.forces += [torsions, FakeSourceForce(), FakeSourceForce()]
    def getForces(self):
        return self.forces
    def getNumParticles(self):
        return len(self.masses)
    def getNumConstraints(self):
        return 0
    def getNumForces(self):
        return len(self.forces)
    def getForce(self, index):
        return self.forces[index]
    def removeForce(self, index):
        self.forces.pop(index)
    def addForce(self, force):
        self.forces.append(force)
    def getParticleMass(self, index):
        return self.masses[index]
    def addParticle(self, mass):
        self.masses.append(mass)


class FakeCustom(FakeSourceForce):
    NoCutoff = 0
    CutoffNonPeriodic = 1
    def __init__(self, expression):
        self.expression = expression
        self.parameters = []
        self.globals = {}
        self.particles = []
        self.exclusions = []
        self.bonds = []
        self.groups = []
    def addPerParticleParameter(self, name):
        self.parameters.append(name)
    def addPerBondParameter(self, name):
        self.parameters.append(name)
    def addGlobalParameter(self, name, value):
        self.globals[name] = value
    def setNonbondedMethod(self, method):
        self.method = method
    def setUseLongRangeCorrection(self, value):
        self.lrc = value
    def addParticle(self, row):
        self.particles.append(row)
    def addExclusion(self, a, b):
        self.exclusions.append((a, b))
    def addBond(self, a, b, row):
        self.bonds.append((a, b, row))
    def addInteractionGroup(self, first, second):
        self.groups.append((first, second))
    def setCutoffDistance(self, value):
        self.cutoff = value
    def setUseSwitchingFunction(self, value):
        self.switch = value


def fake_real_boundary():
    from types import SimpleNamespace
    deserialized = []
    def deserialize(raw):
        import xml.etree.ElementTree as ET
        count = len(ET.fromstring(raw).find("Particles"))
        system = FakeSystem(count, source=True)
        deserialized.append(system)
        return system
    mm = SimpleNamespace(NonbondedForce=FakeNB, CustomNonbondedForce=FakeCustom,
                         CustomBondForce=FakeCustom, System=FakeSystem,
                         XmlSerializer=SimpleNamespace(deserialize=deserialize),
                         unit=SimpleNamespace(elementary_charge=1, nanometer=1, kilojoules_per_mole=1))
    boundary = object.__new__(oracle.OpenMMBoundary)
    boundary.mm = mm
    return boundary, deserialized


def test_real_builder_surface_keeps_source_bonded_terms_and_exception_math(inputs):
    boundary, sources = fake_real_boundary()
    args = inputs["arguments"]
    internal, cross = boundary.build(oracle.read_bound(args["ligand_xml_ref"]),
                                    oracle.read_bound(args["receptor_xml_ref"]), inputs["derived"])
    assert len(sources) == 3
    assert internal is sources[2]
    retained = [force for force in internal.forces if hasattr(force, "source_terms")]
    assert retained[0].source_terms == [(1, 2, 3, 4, 3, .7), (4, 3, 2, 1, 2, .2), (0, 2, 3, 1, 1, -.4)]
    assert all(not isinstance(force, FakeNB) for force in internal.forces)
    nb, exceptions = internal.forces[-2:]
    assert nb.exclusions == [(0, 1), (0, 2)]
    assert exceptions.bonds == [(0, 2, [-.2, .3, .1])]
    assert nb.globals["C"] == oracle.COULOMB * 4.184 / 10
    assert nb.method == FakeCustom.NoCutoff and nb.lrc is False
    assert cross.getNumParticles() == 27
    lj, q = cross.forces
    assert lj.groups == q.groups == [(set(range(26)), {26})]
    assert (lj.group, q.group) == (0, 1)
    assert lj.cutoff == q.cutoff == 1.2
    assert lj.globals["rs"] == q.globals["rs"] == 1.0
    assert q.globals["kappa"] == 1.0 and q.globals["dielectric"] == 4.0
    assert q.globals["C"] == oracle.COULOMB * 4.184 / 10
    assert "s=1-10*t^3+15*t^4-6*t^5" in lj.expression and q.expression.startswith("s*C")
    assert lj.lrc is q.lrc is lj.switch is q.switch is False


def test_builder_rejects_source_particle_parameter_disagreement(inputs):
    boundary, _ = fake_real_boundary()
    inputs["derived"]["parameters"]["atom_parameters"][0]["charge_e"] = .1
    args = inputs["arguments"]
    with pytest.raises(oracle.EndpointAuditError, match="source_particle_parameter_mismatch"):
        boundary.build(oracle.read_bound(args["ligand_xml_ref"]),
                       oracle.read_bound(args["receptor_xml_ref"]), inputs["derived"])


def test_inventory_reports_source_torsions_and_inactive_settings():
    raw = xml(26, ligand=True).replace(b'<Force type="PeriodicTorsionForce" usesPeriodic="0"/>',
          b'<Force type="PeriodicTorsionForce" usesPeriodic="0"><Torsions><Torsion k="-.4"/><Torsion k=".2"/></Torsions></Force>')
    inventory = oracle.source_xml_inventory(raw, True)
    assert inventory["source_term_counts"]["PeriodicTorsionForce"]["Torsions"] == 2
    assert inventory["nocutoff_source_switch_cutoff_dispersion_settings_inactive"] is True


def test_raw_get_state_success_is_preserved_when_array_decode_fails(inputs):
    backend = FakeBoundary()
    def failure(state):
        raise RuntimeError("synthetic_decode_failure")
    backend.decode_state = failure
    result = run(inputs, backend)
    assert result["failure"]["reason"] == "synthetic_decode_failure"
    assert result["openmm_accounting"]["counts"]["get_state"] == {"attempted": 1, "completed": 1, "failed": 0}
    assert result["openmm_accounting"]["counts"]["state_values"]["failed"] == 1
    assert result["openmm_accounting"]["failed_call_work_quantities_unknown"] == []


def test_reference_boundary_get_state_and_unit_conversion_without_real_openmm():
    from types import SimpleNamespace
    class Matrix:
        def __init__(self, values):
            self.values = values
        def __truediv__(self, denominator):
            return Matrix([[v / denominator for v in row] for row in self.values])
        def tolist(self):
            return self.values
    class HolderContext:
        def getState(self, **kwargs):
            self.kwargs = kwargs
            return SimpleNamespace(getPotentialEnergy=lambda: Quantity(12.552),
                                   getForces=lambda **unused: Quantity([[41.84, -83.68, 0.0]]))
    boundary = object.__new__(oracle.OpenMMBoundary)
    boundary.mm = SimpleNamespace(unit=SimpleNamespace(kilojoules_per_mole=1, nanometer=1))
    boundary.np = SimpleNamespace(float64=float, asarray=lambda values, **unused: Matrix(values))
    context = HolderContext()
    state = boundary.get_state([context, object()], {1})
    assert context.kwargs == {"getEnergy": True, "getForces": True, "groups": {1}}
    energy, forces = boundary.decode_state(state)
    assert energy == 3.0
    assert forces == [[1.0, -2.0, 0.0]]


def test_recorded_leaf_intervals_are_nonoverlapping_and_enclosed(inputs):
    ticks = iter(float(i) for i in range(100))
    result = oracle.audit_case(**inputs["arguments"], backend=FakeBoundary(), clock=lambda: next(ticks))
    calls = result["openmm_accounting"]["calls"]
    assert all(row["wall_seconds"] == row["end_monotonic_seconds"] - row["start_monotonic_seconds"] for row in calls)
    assert all(a["end_monotonic_seconds"] <= b["start_monotonic_seconds"] for a, b in zip(calls, calls[1:]))
    assert result["enclosing_start_monotonic_seconds"] <= calls[0]["start_monotonic_seconds"]
    assert calls[-1]["end_monotonic_seconds"] <= result["enclosing_end_monotonic_seconds"]
    assert result["openmm_accounting"]["enclosing_elapsed_must_not_be_added_to_leaf_durations"] is True


def test_same_byte_path_replacement_during_single_fd_read_rejected(tmp_path, monkeypatch):
    path = tmp_path / "source.json"
    ref = pin(path, {"fixed": True})
    raw = path.read_bytes()
    original_fstat = oracle.os.fstat
    attempts = 0
    def replace_after_read(fd):
        nonlocal attempts
        attempts += 1
        if attempts == 2:
            path.rename(tmp_path / "retained-old-source.json")
            path.write_bytes(raw)
        return original_fstat(fd)
    monkeypatch.setattr(oracle.os, "fstat", replace_after_read)
    with pytest.raises(oracle.EndpointAuditError, match="source_changed_during_read"):
        oracle.read_bound(ref)
    assert path.read_bytes() == raw


def test_rejected_default_boundary_does_not_import_openmm(inputs):
    import sys
    before = {name for name in sys.modules if name == "openmm" or name.startswith("openmm.")}
    inputs["arguments"]["protocol_sha256"] = "f" * 64
    result = oracle.audit_case(**inputs["arguments"])
    after = {name for name in sys.modules if name == "openmm" or name.startswith("openmm.")}
    assert after == before
    assert result["openmm_accounting"]["calls"] == []
    assert result["denominator"]["unknown"] == 2

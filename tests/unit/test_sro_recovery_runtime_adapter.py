"""Synthetic contracts only: no SRO preparation, real force/score or optimization."""

from copy import deepcopy
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import zipfile

import pytest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "sro_runtime_adapter_under_test",
    ROOT / "docs/research/human_5ht6_sro_pose_recovery/runtime_adapter.py",
)
adapter = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(adapter)


def primitive_chemistry():
    # Invented graph/charges/coordinates; no observed SRO reference is loaded.
    elements = ["C"] * 10 + ["N", "N", "O"] + ["H"] * 13
    atoms = []
    for i, e in enumerate(elements):
        atoms.append(
            dict(
                index=i,
                name="NZ" if i == 10 else "synthetic_" + str(i),
                element=e,
                atomic_number={"C": 6, "N": 7, "O": 8, "H": 1}[e],
                formal_charge=1 if i == 10 else 0,
                isotope_mass_number=None,
                aromatic=False,
                stereo="unspecified",
                partial_charge_e=1.0 if i == 10 else 0.0,
                mass_da=float({"C": 12, "N": 14, "O": 16, "H": 1}[e]),
            )
        )
    pairs = [(i, i + 1) for i in range(25)] + [(0, 2), (0, 3)]
    return dict(
        schema_id="sro_coordinate_free_chemistry/1",
        atoms=atoms,
        bonds=[
            dict(atom_i=i, atom_j=j, order=1, aromatic=False, stereo="none")
            for i, j in pairs
        ],
        computational_microstate=deepcopy(adapter.STATE),
        coordinate_frame_id=adapter.FRAME,
    )


def water_contracts(path):
    from tests.unit.test_cartesian_workflow import request

    req = request(path)
    originals = {
        name: adapter.loads(Path(req[name]["path"]).read_bytes())
        for name in adapter.IDENTITY_FIELDS
    }
    originals["cross_parameters"]["max_internal_increase_kcal_per_mol"] = 5.0
    return req, originals


def fake_packet(path):
    path.mkdir()
    documents = {name: {"synthetic_only": True} for name in adapter.READABLE_PACKET}
    documents["protocol.json"] = {"synthetic_only": True}
    documents["calculation_inputs/chemistry.json"] = primitive_chemistry()
    files = {}
    for name, document in documents.items():
        dest = path / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(adapter.encoded(document))
        ref = adapter.pin(dest)
        files[name] = {key: ref[key] for key in ("sha256", "bytes")}
    refpath = path / "evaluation_only/reference.json"
    refpath.parent.mkdir()
    refpath.write_bytes(b"NEVER OPEN REFERENCE BODY")
    files["evaluation_only/reference.json"] = {
        "sha256": adapter.digest(refpath.read_bytes()),
        "bytes": refpath.stat().st_size,
    }
    protocol_sha = files["protocol.json"]["sha256"]
    manifest = {
        "schema_id": "sro_prospective_packet_manifest/1",
        "status": "PROSPECTIVE_NOT_EXECUTED",
        "protocol_sha256": protocol_sha,
        "files": files,
    }
    (path / "manifest.json").write_bytes(adapter.encoded(manifest))
    review = dict(
        schema_id="sro_recovery_freeze_review/1",
        protocol_sha256=protocol_sha,
        manifest_sha256=adapter.digest((path / "manifest.json").read_bytes()),
        reviewed_before_execution=True,
        reviewed_at="2026-09-30T00:00:00+00:00",
        reviewer="synthetic unit fixture",
        execution_scope="separately_authorized_future_execution",
    )
    return review


@pytest.mark.parametrize(
    "raw", [b'{"a":1,"a":2}', b'{"n":NaN}', b'{"n":Infinity}', b'{"n":1e999}']
)
def test_duplicate_or_nonfinite_json_rejects(raw):
    with pytest.raises(adapter.AdapterError):
        adapter.loads(raw)


def test_exact_projection_distinguishes_types_signed_zero_and_term_order():
    assert adapter.exact(1) != adapter.exact(1.0)
    assert adapter.exact(0.0) != adapter.exact(-0.0)
    assert adapter.exact([1, 2]) != adapter.exact([2, 1])


def test_reference_free_ligand_is_json_safe_preserves_primitives_and_atom_order():
    chemistry = primitive_chemistry()
    before = adapter.exact(chemistry)
    xyz = [[float(i), float(i % 3), 0.0] for i in range(26)]
    with adapter.forbid_physics():
        document, topology = adapter.ligand_document(chemistry, xyz, "a" * 64)
    raw = adapter.encoded(document)
    from betelgeuze_engine_v2.molecular.serialization import (
        all_atom_system_from_canonical_json,
    )
    from betelgeuze_engine_v2.molecular import canonical_topology_sha256

    system = all_atom_system_from_canonical_json(raw)
    assert len(system.atoms) == 26 and len(system.bonds) == 27
    assert canonical_topology_sha256(system) == topology
    assert system.coordinates.tolist() == [xyz]
    assert [a.name for a in system.atoms] == [a["name"] for a in chemistry["atoms"]]
    assert [a.formal_charge for a in system.atoms] == [
        a["formal_charge"] for a in chemistry["atoms"]
    ]
    assert all(not a.metadata for a in system.atoms)
    assert (
        not system.provenance.metadata
        and system.provenance.source_format == "coordinate_free_packet"
    )
    assert b"evaluation_only" not in raw and b"original" not in raw.replace(
        adapter.FRAME.encode(), b""
    )
    assert adapter.exact(chemistry) == before


@pytest.mark.parametrize(
    "mutation",
    [
        "metadata",
        "index_bool",
        "isotope",
        "stereo",
        "state",
        "charge",
        "bond_order",
        "bond_duplicate",
        "coordinate",
    ],
)
def test_unsupported_chemistry_or_coordinates_fail_closed(mutation):
    chemistry = primitive_chemistry()
    xyz = [[float(i), 0.0, 0.0] for i in range(26)]
    if mutation == "metadata":
        chemistry["atoms"][0]["metadata"] = {"reference_xyz": [0, 0, 0]}
    elif mutation == "index_bool":
        chemistry["atoms"][0]["index"] = False
    elif mutation == "isotope":
        chemistry["atoms"][0]["isotope_mass_number"] = 13
    elif mutation == "stereo":
        chemistry["atoms"][0]["stereo"] = "unrecognized"
    elif mutation == "state":
        chemistry["computational_microstate"]["assay_chemical_state"] = "assumed"
    elif mutation == "charge":
        chemistry["atoms"][0]["partial_charge_e"] = 0.01
    elif mutation == "bond_order":
        chemistry["bonds"][0]["order"] = True
    elif mutation == "bond_duplicate":
        chemistry["bonds"][1] = deepcopy(chemistry["bonds"][0])
    else:
        xyz[0][0] = float("inf")
    with pytest.raises(adapter.AdapterError):
        adapter.ligand_document(chemistry, xyz, "a" * 64)


def test_native_parameter_reseal_changes_exactly_five_identity_fields(tmp_path):
    _, original = water_contracts(tmp_path)
    captured = adapter.exact(original)
    with adapter.forbid_physics():
        derived, proof = adapter.rebind_parameters(original, "b" * 64)
    assert adapter.exact(original) == captured
    assert len(proof["rebound_identity_fields"]) == 5
    assert proof["all_nonidentity_fields_exact"] and proof["molecular_calls"] == 0
    assert (
        derived["extensions"]["topology_sha256"]
        == derived["parameters"]["topology_sha256"]
        == "b" * 64
    )
    assert derived["cross_parameters"]["ligand_topology_sha256"] == "b" * 64
    assert (
        derived["extensions"]["base_parameter_fingerprint_sha256"]
        == derived["cross_parameters"]["ligand_base_parameters_sha256"]
    )
    assert (
        not proof["forcefield_reassignment"]
        and not proof["unsupported_terms_silently_dropped"]
    )


@pytest.mark.parametrize(
    "mutation",
    ["term", "order", "excluded", "signed_zero", "type", "drop", "configuration"],
)
def test_numeric_parameter_mutations_reject(tmp_path, mutation):
    _, original = water_contracts(tmp_path)
    derived, _ = adapter.rebind_parameters(original, "b" * 64)
    if mutation == "term":
        derived["parameters"]["bonds"][0]["force_constant_kcal_per_mol_angstrom2"] += (
            0.125
        )
    elif mutation == "order":
        derived["parameters"]["bonds"].reverse()
    elif mutation == "excluded":
        derived["parameters"]["excluded_pairs"].reverse()
    elif mutation == "signed_zero":
        original["parameters"]["test_zero"] = 0.0
        derived["parameters"]["test_zero"] = -0.0
    elif mutation == "type":
        original["parameters"]["test_integer"] = 1
        derived["parameters"]["test_integer"] = 1.0
    elif mutation == "drop":
        derived["parameters"]["angles"] = []
    else:
        derived["cross_parameters"]["max_internal_increase_kcal_per_mol"] = 4.999
    with pytest.raises(
        adapter.AdapterError, match="numeric_term_or_configuration_changed"
    ):
        adapter.preservation_proof(original, derived)


def test_source_pin_rechecks_bytes_and_rejects_alias(tmp_path):
    path = tmp_path / "source.json"
    path.write_bytes(b'{"n":1}')
    ref = adapter.pin(path)
    assert adapter.read_bound(ref) == {"n": 1}
    path.write_bytes(b'{"n":2}')
    with pytest.raises(adapter.AdapterError, match="source_changed"):
        adapter.read_bound(ref)
    alias = tmp_path / "alias.json"
    alias.symlink_to(path)
    bad = dict(ref, path=str(alias))
    with pytest.raises(adapter.AdapterError, match="source_path_alias"):
        adapter.read_bound(bad)


def test_packet_whitelist_never_reads_reference_body(tmp_path, monkeypatch):
    packet = tmp_path / "packet"
    review = fake_packet(packet)
    original = Path.read_bytes

    def allowed(path):
        assert "evaluation_only" not in path.parts
        return original(path)

    monkeypatch.setattr(Path, "read_bytes", allowed)
    frozen = adapter._freeze(packet, review)
    assert frozen["review"] == review
    assert set(frozen) == set(adapter.READABLE_PACKET) | {"manifest", "review"}


@pytest.mark.parametrize(
    "mutation", ["review", "manifest", "runtime_bytes", "extra_file", "symlink"]
)
def test_packet_freeze_changes_fail_closed(tmp_path, mutation):
    packet = tmp_path / "packet"
    review = fake_packet(packet)
    if mutation == "review":
        review["reviewed_before_execution"] = False
    elif mutation == "manifest":
        (packet / "manifest.json").write_bytes(b"{}")
    elif mutation == "runtime_bytes":
        (packet / "calculation_inputs/chemistry.json").write_bytes(b"{}")
    elif mutation == "extra_file":
        (packet / "extra.json").write_bytes(b"{}")
    else:
        target = packet / "calculation_inputs/chemistry.json"
        raw = target.read_bytes()
        target.unlink()
        outside = tmp_path / "outside.json"
        outside.write_bytes(raw)
        target.symlink_to(outside)
    with pytest.raises(adapter.AdapterError):
        adapter._freeze(packet, review)


@pytest.mark.parametrize(
    "module,name",
    [
        ("betelgeuze_product.synthetic", "evaluate"),
        ("betelgeuze_product.synthetic", "score_terms"),
        ("betelgeuze_product.synthetic", "minimize"),
        ("betelgeuze_engine_v2.geometry", "build_compact_radius_graph"),
        ("betelgeuze_engine_v2.native_graph.synthetic", "constructor"),
        ("openmm.synthetic", "observe"),
        ("betelgeuze_engine_v2.synthetic", "evaluate_independent_analytic_oracle"),
    ],
)
def test_guard_rejects_physics_even_if_caller_catches(module, name):
    namespace = {"__name__": module}
    exec("def " + name + "():\n    return 1\n", namespace)
    with pytest.raises(adapter.AdapterError):
        with adapter.forbid_physics():
            namespace[name]()
    with pytest.raises(
        adapter.AdapterError, match="caught_molecular_execution_attempt"
    ):
        with adapter.forbid_physics():
            try:
                namespace[name]()
            except adapter.AdapterError:
                pass


def test_current_native_synthetic_input_binding_constructs_without_public_calls(
    tmp_path, monkeypatch
):
    from tests.unit.test_cartesian_workflow import (
        request,
        observe_numerical_and_score_calls,
    )
    from betelgeuze_product.cpu_refinement_v1_3 import workflow

    req = request(tmp_path)
    calls = observe_numerical_and_score_calls(monkeypatch)
    with adapter.forbid_physics():
        binding = workflow.input_binding(req)
    assert calls == {"numerical_graph": 0, "force": 0, "score": 0}
    assert binding["schema_id"] == "cpu_cartesian_registered_pose_binding/1.3.0"
    # This is current source parsing only; it makes no old-wheel binding claim.


def test_loaded_origin_rejects_identical_bytes_outside_installed_site(tmp_path):
    site = tmp_path / "site"
    member = "betelgeuze_product/synthetic.py"
    path = site / member
    path.parent.mkdir(parents=True)
    raw = b"# synthetic source\n"
    path.write_bytes(raw)
    wheel = tmp_path / "synthetic.whl"
    with zipfile.ZipFile(wheel, "w") as archive:
        archive.writestr(member, raw)
    module = SimpleNamespace(
        __file__=str(path), __spec__=SimpleNamespace(origin=str(path))
    )
    with zipfile.ZipFile(wheel) as archive:
        origins = adapter._loaded_origins(
            site, {}, archive, modules={"betelgeuze_product.synthetic": module}
        )
        assert origins["betelgeuze_product.synthetic"]["sha256"] == adapter.digest(raw)
        outside = tmp_path / "synthetic.py"
        outside.write_bytes(raw)
        module.__file__ = str(outside)
        module.__spec__.origin = str(outside)
        with pytest.raises(adapter.AdapterError, match="mixed_origin_loaded_module"):
            adapter._loaded_origins(
                site, {}, archive, modules={"betelgeuze_product.synthetic": module}
            )


def test_installed_binding_refuses_workspace_runtime_before_native_construction(
    tmp_path, monkeypatch
):
    from betelgeuze_product.cpu_refinement_v1_3 import workflow

    wheel = tmp_path / "fake.whl"
    wheel.write_bytes(b"not an installed runtime")

    def forbidden(*args, **kwargs):
        pytest.fail("workspace import reached native binding")

    monkeypatch.setattr(workflow, "input_binding", forbidden)
    ref = adapter.pin(wheel)
    with pytest.raises(adapter.AdapterError, match="installed_runtime_required"):
        adapter.installed_input_binding(
            {}, wheel_ref=ref, expected_wheel_sha256=ref["sha256"]
        )


def mocked_derivation(tmp_path, monkeypatch):
    source = tmp_path / "source"
    source.mkdir()
    req, originals = water_contracts(source)
    ligand = adapter.loads(Path(req["ligand"]["path"]).read_bytes())
    frozen = {
        "calculation_inputs/chemistry.json": primitive_chemistry(),
        "calculation_inputs/input_contract.json": {
            "chemistry_sha256": "a" * 64,
            "parameter_refs": {"receptor": adapter.pin(req["receptor"]["path"])},
        },
        "calculation_inputs/candidates.json": {
            "cases": [
                {
                    "case_id": c,
                    "seed": i,
                    "coordinates_angstrom": [[0.0, 0.0, 0.0]] * 26,
                }
                for i, c in enumerate(adapter.CASE_IDS)
            ]
        },
        "lineage.json": {"five_original_inputs": {}},
        "protocol.json": {"future_runtime": {"wheel_sha256": "f" * 64}},
    }
    monkeypatch.setattr(adapter, "_freeze", lambda *args: frozen)
    monkeypatch.setattr(adapter, "_sources", lambda *args: (req, originals))
    monkeypatch.setattr(
        adapter, "ligand_document", lambda *args: (deepcopy(ligand), "b" * 64)
    )
    return req, originals


def test_create_only_publication_writes_four_derivatives_without_native_binding(
    tmp_path, monkeypatch
):
    req, originals = mocked_derivation(tmp_path, monkeypatch)
    snapshot = adapter.exact(originals)
    receipt = adapter.prepare_inputs(
        None,
        {"protocol_sha256": "c" * 64, "manifest_sha256": "d" * 64},
        tmp_path / "out",
    )
    assert (
        len(receipt["cases"]) == 4
        and receipt["native_binding_separate_from_numeric_preservation"]
    )
    assert (
        not receipt["reference_or_original_ligand_bodies_read"]
        and not receipt["actual_execution_authorized"]
    )
    assert (
        receipt["new_force_calls"]
        == receipt["new_score_calls"]
        == receipt["new_optimizer_calls"]
        == 0
    )
    for case in receipt["cases"]:
        actual = adapter.read_bound(case["request_file_ref"])
        assert adapter.exact(actual["solver"]) == adapter.exact(req["solver"])
        assert (
            actual["solvation"] is None and not case["native_input_binding_generated"]
        )
    assert adapter.exact(originals) == snapshot
    with pytest.raises(adapter.AdapterError, match="create_only_output_required"):
        adapter.prepare_inputs(
            None,
            {"protocol_sha256": "c" * 64, "manifest_sha256": "d" * 64},
            tmp_path / "out",
        )


def test_mutation_after_source_read_is_rejected_before_receipt(tmp_path, monkeypatch):
    _, originals = mocked_derivation(tmp_path, monkeypatch)
    real = adapter.rebind_parameters

    def mutate(original, topology):
        original["parameters"]["bonds"][0]["force_constant_kcal_per_mol_angstrom2"] += (
            0.125
        )
        return real(original, topology)

    monkeypatch.setattr(adapter, "rebind_parameters", mutate)
    with pytest.raises(adapter.AdapterError, match="captured_source_mutated"):
        adapter.prepare_inputs(
            None,
            {"protocol_sha256": "c" * 64, "manifest_sha256": "d" * 64},
            tmp_path / "out",
        )
    assert not (tmp_path / "out/derivation.json").exists()


@pytest.mark.parametrize("target_kind", ["force", "score", "graph", "minimize"])
def test_direct_dispatch_sentinels_survive_caught_exceptions(
    tmp_path, monkeypatch, target_kind
):
    from betelgeuze_product.cpu_refinement_v1_3 import workflow, minimization
    from betelgeuze_product.cpu_refinement_v1_2.chemical_features import (
        ExplicitGraphScorer,
    )

    target, attribute = {
        "force": (workflow.FixedReceptorEvaluator, "evaluate"),
        "score": (ExplicitGraphScorer, "score_terms"),
        "graph": (minimization, "build_compact_radius_graph"),
        "minimize": (minimization, "minimize"),
    }[target_kind]
    calls = []

    def spy(*args, **kwargs):
        calls.append(1)

    monkeypatch.setattr(target, attribute, spy)
    with pytest.raises(
        adapter.AdapterError, match="caught_molecular_execution_attempt"
    ):
        with adapter.forbid_physics():
            for _ in range(2):
                try:
                    getattr(target, attribute)()
                except adapter.AdapterError:
                    pass
    assert calls == []
    assert getattr(target, attribute) is spy


def test_resealed_output_term_mutation_fails_fresh_reproof(tmp_path, monkeypatch):
    mocked_derivation(tmp_path, monkeypatch)
    publish = adapter._publish

    def corrupt(path, value):
        if Path(path).name == "parameters.json":
            value = deepcopy(value)
            value["bonds"][0]["force_constant_kcal_per_mol_angstrom2"] += 0.125
        return publish(path, value)

    monkeypatch.setattr(adapter, "_publish", corrupt)
    with pytest.raises(
        adapter.AdapterError, match="numeric_term_or_configuration_changed"
    ):
        adapter.prepare_inputs(
            None,
            {"protocol_sha256": "c" * 64, "manifest_sha256": "d" * 64},
            tmp_path / "out",
        )
    assert not (tmp_path / "out/derivation.json").exists()


def test_sources_bind_request_numeric_config_and_never_open_original_ligand(
    tmp_path, monkeypatch
):
    req, _ = water_contracts(tmp_path)
    from betelgeuze_product.cpu_refinement_v1_3.contracts import SolverConfig

    req["solver"] = SolverConfig(
        max_objective_attempts=417, max_accepted_steps=416
    ).to_dict()
    req["pocket"]["coordinate_frame_id"] = adapter.FRAME
    refs = {
        name: adapter.pin(req[name]["path"])
        for name in (
            "ligand",
            "parameters",
            "extensions",
            "cross_parameters",
            "receptor",
        )
    }
    request_path = tmp_path / "synthetic-retained-request.json"
    request_path.write_bytes(adapter.encoded(req))
    chemistry = primitive_chemistry()
    pool = {
        "schema_id": "sro_perturbed_candidate_pool/1",
        "cases": [
            dict(
                case_id=c,
                role="generated_perturbation",
                seed=2026093001 + i,
                coordinate_frame_id=adapter.FRAME,
                coordinates_angstrom=[[float(j), 0.0, 0.0] for j in range(26)],
            )
            for i, c in enumerate(adapter.CASE_IDS)
        ],
    }
    contract = {
        "source_ligand_or_provenance_or_evaluation_reference_path": None,
        "runtime_adapter_status": "NOT_IMPLEMENTED_NOT_AUTHORIZED_TO_EXECUTE",
        "coordinate_frame_id": adapter.FRAME,
        "chemistry_sha256": adapter.digest(adapter.encoded(chemistry)),
        "candidate_pool_sha256": adapter.digest(adapter.encoded(pool)),
        "parameter_refs": {name: ref for name, ref in refs.items() if name != "ligand"},
        "original_prepared_ligand_sha256_identity_only": refs["ligand"]["sha256"],
        "solver": deepcopy(req["solver"]),
        "pocket": deepcopy(req["pocket"]),
    }
    frozen = {
        "protocol.json": {
            "coordinate_free_chemistry_sha256": contract["chemistry_sha256"],
            "perturbations": [{"seed": c["seed"]} for c in pool["cases"]],
            "original_five_prepared_input_hashes": {
                name: ref["sha256"] for name, ref in refs.items()
            },
            "solver": deepcopy(req["solver"]),
            "pocket": deepcopy(req["pocket"]),
        },
        "lineage.json": {
            "five_original_inputs": refs,
            "retained_request": adapter.pin(request_path),
        },
        "calculation_inputs/input_contract.json": contract,
        "calculation_inputs/chemistry.json": chemistry,
        "calculation_inputs/candidates.json": pool,
    }
    original = Path.read_bytes

    def allowed(path):
        assert str(path) != refs["ligand"]["path"]
        assert "evaluation_only" not in path.parts
        return original(path)

    monkeypatch.setattr(Path, "read_bytes", allowed)
    found, parameters = adapter._sources(frozen)
    assert adapter.exact(found) == adapter.exact(req) and set(parameters) == set(
        adapter.IDENTITY_FIELDS
    )
    frozen["calculation_inputs/input_contract.json"]["solver"]["force_tolerance"] = (
        0.002
    )
    with pytest.raises(adapter.AdapterError, match="frozen_settings_changed"):
        adapter._sources(frozen)

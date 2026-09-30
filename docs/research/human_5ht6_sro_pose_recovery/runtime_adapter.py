"""Reference-free SRO request derivation; no force, score or optimizer command.

Full packet/reference verification belongs to the separate root freeze review.
This module reads only frozen calculation inputs and source parameter/request
files. Numerical preservation and an explicitly installed-wheel input binding
are different receipts. Existing source ligand and evaluation reference bodies
are never opened by this adapter.
"""

from __future__ import annotations

from contextlib import contextmanager, ExitStack
from copy import deepcopy
from datetime import datetime
import hashlib
from collections import Counter
import json
import math
from pathlib import Path
import re
import sys
import zipfile

SCHEMA = "sro_reference_free_runtime_derivation/1"
SHA = re.compile(r"^[0-9a-f]{64}$")
FRAME = "7XTB_original_cartesian_angstrom_development"
ATOM_KEYS = {
    "index",
    "name",
    "element",
    "atomic_number",
    "formal_charge",
    "isotope_mass_number",
    "aromatic",
    "stereo",
    "partial_charge_e",
    "mass_da",
}
BOND_KEYS = {"atom_i", "atom_j", "order", "aromatic", "stereo"}
STATE = {
    "formal_charge_site": "NZ",
    "formal_charge_e": 1,
    "formula": "C10H13N2O+",
    "atom_count": 26,
    "heavy_atom_count": 13,
    "hydrogen_count": 13,
    "terminal_amine_hydrogen_count": 3,
    "indole_NH_retained": True,
    "phenol_OH_retained": True,
    "selection": "single_predeclared_computational_assumption",
    "experimentally_measured_bound_protonation": None,
    "assay_chemical_state": None,
}
CASE_IDS = ["perturbed_01", "perturbed_02", "perturbed_03", "perturbed_04"]
IDENTITY_FIELDS = {
    "parameters": {"topology_sha256"},
    "extensions": {"topology_sha256", "base_parameter_fingerprint_sha256"},
    "cross_parameters": {"ligand_topology_sha256", "ligand_base_parameters_sha256"},
}
READABLE_PACKET = (
    "protocol.json",
    "lineage.json",
    "calculation_inputs/input_contract.json",
    "calculation_inputs/chemistry.json",
    "calculation_inputs/candidates.json",
)


class AdapterError(ValueError):
    pass


def require(condition, reason):
    if not condition:
        raise AdapterError(reason)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def encoded(value):
    # Native molecular readers require compact canonical bytes, not indent JSON.
    if (
        type(value) is dict
        and value.get("schema_id") == "betelgeuze.engine_v2_canonical_system/1.0.0"
    ):
        return json.dumps(
            value,
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("ascii")
    return (
        json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n"
    ).encode()


def _object(pairs):
    value = {}
    for key, item in pairs:
        require(key not in value, "duplicate_json_key")
        value[key] = item
    return value


def _finite(value, depth=0):
    require(depth < 96, "json_depth")
    if type(value) is float:
        require(math.isfinite(value), "nonfinite_json")
    elif type(value) is dict:
        for item in value.values():
            _finite(item, depth + 1)
    elif type(value) is list:
        for item in value:
            _finite(item, depth + 1)
    else:
        require(value is None or type(value) in (str, int, bool), "unsupported_json")
    return value


def loads(raw):
    try:
        return _finite(
            json.loads(
                raw,
                object_pairs_hook=_object,
                parse_constant=lambda _: (_ for _ in ()).throw(
                    AdapterError("nonfinite_json")
                ),
            )
        )
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise AdapterError("invalid_json") from exc


def exact(value):
    """Strict types and binary64 bits, including signed zero, for proofs."""
    if type(value) is float:
        require(math.isfinite(value), "nonfinite_json")
        return ["float", value.hex()]
    if type(value) is dict:
        return ["dict", [[key, exact(value[key])] for key in sorted(value)]]
    if type(value) is list:
        return ["list", [exact(item) for item in value]]
    return [type(value).__name__, value]


def pin(path):
    path = Path(path).resolve(strict=True)
    raw = path.read_bytes()
    return {"path": str(path), "sha256": digest(raw), "bytes": len(raw)}


def read_bound(ref):
    require(
        type(ref) is dict and set(ref) == {"path", "sha256", "bytes"},
        "source_pin_fields",
    )
    require(
        type(ref["path"]) is str and Path(ref["path"]).is_absolute(),
        "absolute_source_path",
    )
    require(type(ref["sha256"]) is str and SHA.fullmatch(ref["sha256"]), "source_sha")
    require(type(ref["bytes"]) is int and 0 < ref["bytes"] <= 32_000_000, "source_size")
    path = Path(ref["path"])
    require(
        not path.is_symlink() and str(path.resolve(strict=True)) == ref["path"],
        "source_path_alias",
    )
    raw = path.read_bytes()
    require(len(raw) == ref["bytes"] and digest(raw) == ref["sha256"], "source_changed")
    return loads(raw)


def _freeze(packet, review):
    packet = Path(packet).resolve(strict=True)
    require(
        type(review) is dict
        and set(review)
        == {
            "schema_id",
            "protocol_sha256",
            "manifest_sha256",
            "reviewed_before_execution",
            "reviewed_at",
            "reviewer",
            "execution_scope",
        },
        "review_fields",
    )
    require(
        review["schema_id"] == "sro_recovery_freeze_review/1"
        and review["reviewed_before_execution"] is True
        and review["reviewer"]
        and review["execution_scope"] == "separately_authorized_future_execution",
        "root_freeze_review_required",
    )
    require(
        datetime.fromisoformat(review["reviewed_at"]).utcoffset() is not None,
        "review_timezone",
    )
    raw = (packet / "manifest.json").read_bytes()
    require(digest(raw) == review["manifest_sha256"], "frozen_manifest_changed")
    manifest = loads(raw)
    require(
        manifest["schema_id"] == "sro_prospective_packet_manifest/1"
        and manifest["status"] == "PROSPECTIVE_NOT_EXECUTED",
        "prospective_packet_required",
    )
    require(
        manifest["protocol_sha256"] == review["protocol_sha256"],
        "frozen_protocol_changed",
    )
    files = manifest["files"]
    require(
        {p.relative_to(packet).as_posix() for p in packet.rglob("*") if p.is_file()}
        == set(files) | {"manifest.json"},
        "packet_file_inventory_changed",
    )
    # No evaluation/reference body reads. Full-body freeze review is external.
    for name, ref in files.items():
        path = packet / name
        require(
            path.resolve().is_relative_to(packet)
            and not path.is_symlink()
            and path.stat().st_size == ref["bytes"],
            "packet_path_or_size_changed",
        )
    result = {}
    for name in READABLE_PACKET:
        raw = (packet / name).read_bytes()
        require(
            digest(raw) == files[name]["sha256"] and len(raw) == files[name]["bytes"],
            "frozen_runtime_packet_changed",
        )
        result[name] = loads(raw)
    result["manifest"] = manifest
    result["review"] = deepcopy(review)
    return result


def _chemistry(chemistry):
    # Standalone primitive-only validation; no protocol/reference imports.
    require(
        type(chemistry) is dict
        and set(chemistry)
        == {
            "schema_id",
            "atoms",
            "bonds",
            "computational_microstate",
            "coordinate_frame_id",
        },
        "chemistry_fields_or_reference_leak",
    )
    require(
        chemistry["schema_id"] == "sro_coordinate_free_chemistry/1"
        and chemistry["coordinate_frame_id"] == FRAME,
        "chemistry_schema_frame",
    )
    require(
        exact(chemistry["computational_microstate"]) == exact(STATE),
        "unsupported_state",
    )
    atoms, bonds = chemistry["atoms"], chemistry["bonds"]
    require(
        type(atoms) is list
        and len(atoms) == 26
        and all(type(a) is dict and set(a) == ATOM_KEYS for a in atoms),
        "atom_fields_or_reference_leak",
    )
    require(
        [a["index"] for a in atoms] == list(range(26))
        and all(type(a["index"]) is int for a in atoms),
        "undeclared_atom_count_or_order",
    )
    require(
        all(type(a["name"]) is str and a["name"] for a in atoms)
        and len({a["name"] for a in atoms}) == 26,
        "duplicate_atom_name",
    )
    require(
        Counter(a["element"] for a in atoms) == {"C": 10, "H": 13, "N": 2, "O": 1},
        "undeclared_elements",
    )
    require(
        sum(a["name"] == "NZ" for a in atoms) == 1
        and all(
            type(a["formal_charge"]) is int
            and a["formal_charge"] == (1 if a["name"] == "NZ" else 0)
            for a in atoms
        ),
        "undeclared_formal_state",
    )
    for atom in atoms:
        require(
            type(atom["atomic_number"]) is int
            and atom["atomic_number"]
            == {"C": 6, "H": 1, "N": 7, "O": 8}[atom["element"]]
            and atom["isotope_mass_number"] is None,
            "unsupported_atom_or_isotope",
        )
        require(
            all(
                type(atom[k]) in (int, float) and math.isfinite(atom[k])
                for k in ("partial_charge_e", "mass_da")
            )
            and atom["mass_da"] > 0,
            "nonfinite_charge_or_mass",
        )
        require(
            type(atom["aromatic"]) is bool
            and atom["stereo"] in ("unspecified", "none", "R", "S"),
            "unsupported_atom_stereo_or_aromatic",
        )
    require(
        abs(math.fsum(a["partial_charge_e"] for a in atoms) - 1) < 1e-10,
        "partial_charge_state",
    )
    require(
        all(a["element"] != "H" for a in atoms[:13])
        and all(a["element"] == "H" for a in atoms[13:]),
        "heavy_atom_order",
    )
    require(type(bonds) is list and len(bonds) == 27, "undeclared_bonds")
    seen = set()
    for bond in bonds:
        require(
            type(bond) is dict and set(bond) == BOND_KEYS,
            "bond_fields_or_reference_leak",
        )
        i, j = bond["atom_i"], bond["atom_j"]
        require(
            type(i) is int and type(j) is int and 0 <= i < j < 26, "bond_atom_mapping"
        )
        require(
            (i, j) not in seen
            and type(bond["order"]) in (int, float)
            and bond["order"] in (1, 2, 3)
            and type(bond["aromatic"]) is bool
            and bond["stereo"] in ("none", "unspecified", "E", "Z"),
            "unsupported_bond_chemistry",
        )
        seen.add((i, j))
    return chemistry


def ligand_document(chemistry, coordinates, chemistry_sha256):
    """Construct from primitives, without opening any original ligand file."""
    _chemistry(chemistry)
    require(
        type(coordinates) is list
        and len(coordinates) == 26
        and all(
            type(p) is list
            and len(p) == 3
            and all(type(v) in (int, float) and math.isfinite(v) for v in p)
            for p in coordinates
        ),
        "candidate_coordinates",
    )
    import torch
    from betelgeuze_engine_v2.molecular import (
        AllAtomSystem,
        Atom,
        Bond,
        Chain,
        Residue,
        StructureProvenance,
    )
    from betelgeuze_engine_v2.molecular.serialization import (
        canonical_system_json_bytes,
        canonical_topology_sha256,
    )

    system = AllAtomSystem(
        "SRO_reference_free_computational_plus1",
        tuple(
            Atom(**atom, residue_index=0, metadata={}) for atom in chemistry["atoms"]
        ),
        tuple(
            Bond(index=i, **bond, source="coordinate_free_packet", metadata={})
            for i, bond in enumerate(chemistry["bonds"])
        ),
        (
            Residue(
                0, "SRO", 0, 1, tuple(range(26)), entity_type="non_polymer", hetero=True
            ),
        ),
        (Chain(0, "L", (0,)),),
        torch.tensor([coordinates], dtype=torch.float64),
        StructureProvenance(
            source_format="coordinate_free_packet",
            source_id="SRO_computational_plus1",
            source_sha256=chemistry_sha256,
            parser_name="sro_runtime_adapter",
            parser_version="1",
            operations=(
                "construct_from_frozen_coordinate_free_chemistry_and_candidate",
            ),
            source_digest_verified=True,
            metadata={},
        ),
        metadata={
            "computational_microstate": deepcopy(chemistry["computational_microstate"]),
            "coordinate_frame_id": chemistry["coordinate_frame_id"],
        },
    )
    return loads(canonical_system_json_bytes(system)), canonical_topology_sha256(system)


def _parameter_api():
    from betelgeuze_product.reference_minimization_workflow import _parameters
    from betelgeuze_product.cpu_refinement_v1_2.workflow import _extension
    from betelgeuze_product.cpu_refinement_v1_2.fixed_receptor import CrossParameters

    return _parameters, _extension, CrossParameters


def preservation_proof(original, derived):
    require(
        set(original) == set(derived) == set(IDENTITY_FIELDS), "parameter_input_set"
    )
    changes = []
    projections = {}
    for name, fields in IDENTITY_FIELDS.items():
        before, after = original[name], derived[name]
        require(
            set(before) == set(after) and fields <= set(before),
            "parameter_fields_changed",
        )
        a = {k: v for k, v in before.items() if k not in fields}
        b = {k: v for k, v in after.items() if k not in fields}
        require(exact(a) == exact(b), "numeric_term_or_configuration_changed")
        projections[name] = digest(encoded(exact(a)))
        changes.extend(
            {
                "field": name + "." + field,
                "before": before[field],
                "after": after[field],
            }
            for field in sorted(fields)
        )
    return {
        "schema_id": "sro_exact_numeric_parameter_preservation/1",
        "comparison": "strict_JSON_types_and_float_hex_including_signed_zero; term_order_preserved",
        "all_nonidentity_fields_exact": True,
        "nonidentity_projection_sha256": projections,
        "rebound_identity_fields": changes,
        "forcefield_reassignment": False,
        "unsupported_terms_silently_dropped": False,
        "molecular_calls": 0,
    }


def rebind_parameters(original, topology_sha256):
    base_parser, extension_parser, cross_type = _parameter_api()
    require(
        type(topology_sha256) is str and SHA.fullmatch(topology_sha256),
        "derived_topology_sha",
    )
    base = base_parser(original["parameters"])
    extension_parser(original["extensions"], base)
    cross = cross_type.from_dict(original["cross_parameters"])
    require(
        original["extensions"]["topology_sha256"]
        == base.topology_sha256
        == cross.ligand_topology_sha256,
        "original_topology_binding",
    )
    require(
        cross.ligand_base_parameters_sha256 == base.fingerprint_sha256,
        "original_base_binding",
    )
    require(
        cross.max_internal_increase_kcal_per_mol == 5.0
        and not original["extensions"]["constraints"],
        "unchanged_strain_and_no_constraints",
    )
    derived = deepcopy(original)
    derived["parameters"]["topology_sha256"] = topology_sha256
    new_base = base_parser(derived["parameters"])
    derived["extensions"]["topology_sha256"] = topology_sha256
    derived["extensions"]["base_parameter_fingerprint_sha256"] = (
        new_base.fingerprint_sha256
    )
    derived["cross_parameters"]["ligand_topology_sha256"] = topology_sha256
    derived["cross_parameters"]["ligand_base_parameters_sha256"] = (
        new_base.fingerprint_sha256
    )
    extension_parser(derived["extensions"], new_base)
    cross_type.from_dict(derived["cross_parameters"])
    return derived, preservation_proof(original, derived)


def _sources(frozen):
    protocol, lineage = frozen["protocol.json"], frozen["lineage.json"]
    contract = frozen["calculation_inputs/input_contract.json"]
    chemistry, pool = (
        frozen["calculation_inputs/chemistry.json"],
        frozen["calculation_inputs/candidates.json"],
    )
    require(
        contract["source_ligand_or_provenance_or_evaluation_reference_path"] is None
        and contract["runtime_adapter_status"]
        == "NOT_IMPLEMENTED_NOT_AUTHORIZED_TO_EXECUTE",
        "runtime_contract_boundary",
    )
    require(
        contract["coordinate_frame_id"] == chemistry["coordinate_frame_id"] == FRAME,
        "frame_changed",
    )
    require(
        digest(encoded(chemistry))
        == contract["chemistry_sha256"]
        == protocol["coordinate_free_chemistry_sha256"],
        "chemistry_binding_changed",
    )
    require(
        digest(encoded(pool)) == contract["candidate_pool_sha256"],
        "candidate_pool_binding_changed",
    )
    _chemistry(chemistry)
    require(
        set(pool) == {"schema_id", "cases"}
        and pool["schema_id"] == "sro_perturbed_candidate_pool/1"
        and [c["case_id"] for c in pool["cases"]] == CASE_IDS,
        "generated_pool_only",
    )
    for case, spec in zip(pool["cases"], protocol["perturbations"]):
        require(
            set(case)
            == {
                "case_id",
                "role",
                "seed",
                "coordinate_frame_id",
                "coordinates_angstrom",
            }
            and case["role"] == "generated_perturbation"
            and case["seed"] == spec["seed"]
            and case["coordinate_frame_id"] == FRAME,
            "case_identity_or_reference_leak",
        )
    require(
        contract["parameter_refs"]
        == {
            k: lineage["five_original_inputs"][k]
            for k in ("parameters", "extensions", "cross_parameters", "receptor")
        },
        "parameter_source_refs_changed",
    )
    require(
        contract["original_prepared_ligand_sha256_identity_only"]
        == lineage["five_original_inputs"]["ligand"]["sha256"],
        "original_identity_changed",
    )
    require(
        protocol["original_five_prepared_input_hashes"]
        == {k: v["sha256"] for k, v in lineage["five_original_inputs"].items()},
        "source_lineage_changed",
    )
    original_request = read_bound(lineage["retained_request"])
    require(
        original_request["schema_id"] == "cpu_cartesian_registered_pose_request/1.3.0"
        and original_request["solvation"] is None
        and original_request["backend"] == "python_cpu_reference",
        "unchanged_request_model_required",
    )
    require(
        exact(original_request["solver"])
        == exact(contract["solver"])
        == exact(protocol["solver"])
        and exact(original_request["pocket"])
        == exact(contract["pocket"])
        == exact(protocol["pocket"]),
        "frozen_settings_changed",
    )
    solver = original_request["solver"]
    require(
        solver["algorithm"] == "lbfgs"
        and solver["max_objective_attempts"] == 417
        and solver["max_accepted_steps"] == 416
        and solver["max_restart_verifications"] == 2
        and solver["force_tolerance"] == 0.001
        and solver["maximum_atom_displacement"] == 0.05,
        "solver_gates_changed",
    )
    for name, ref in contract["parameter_refs"].items():
        require(
            original_request[name] == {k: ref[k] for k in ("path", "sha256")},
            "request_parameter_source_mismatch",
        )
    require(
        original_request["ligand"]["sha256"]
        == contract["original_prepared_ligand_sha256_identity_only"],
        "request_ligand_identity",
    )
    originals = {
        name: read_bound(contract["parameter_refs"][name]) for name in IDENTITY_FIELDS
    }
    # Receptor integrity only here; its body is consumed by installed input_binding.
    read_bound(contract["parameter_refs"]["receptor"])
    return original_request, originals


def _publish(path, value):
    with Path(path).open("xb") as stream:
        stream.write(encoded(value))
    return pin(path)


def _prepare_inputs(packet, review, output):
    """Create four frozen derivatives and proofs. No native binding or execution."""
    frozen = _freeze(packet, review)
    original_request, originals = _sources(frozen)
    captured_request, captured_originals = exact(original_request), exact(originals)
    chemistry = frozen["calculation_inputs/chemistry.json"]
    contract = frozen["calculation_inputs/input_contract.json"]
    output = Path(output).absolute()
    require(not output.exists(), "create_only_output_required")
    output.mkdir(mode=0o700)
    cases = []
    for case in frozen["calculation_inputs/candidates.json"]["cases"]:
        folder = output / case["case_id"]
        folder.mkdir(mode=0o700)
        ligand, topology = ligand_document(
            chemistry, case["coordinates_angstrom"], contract["chemistry_sha256"]
        )
        require(exact(originals) == captured_originals, "captured_source_mutated")
        try:
            derived, proof = rebind_parameters(originals, topology)
        finally:
            require(exact(originals) == captured_originals, "captured_source_mutated")
        preservation_proof(originals, derived)
        refs = {"ligand": _publish(folder / "ligand.json", ligand)}
        refs.update(
            {
                name: _publish(folder / (name + ".json"), value)
                for name, value in derived.items()
            }
        )
        refs["receptor"] = deepcopy(contract["parameter_refs"]["receptor"])
        request = deepcopy(original_request)
        for name, ref in refs.items():
            request[name] = {k: ref[k] for k in ("path", "sha256")}
        request["budget"]["seed"] = case["seed"]
        expected_request = deepcopy(original_request)
        for name in refs:
            expected_request[name] = request[name]
        expected_request["budget"]["seed"] = case["seed"]
        require(
            exact(request) == exact(expected_request), "request_configuration_changed"
        )
        proof_ref = _publish(folder / "numeric-preservation.json", proof)
        request_ref = _publish(folder / "request.json", request)
        cases.append(
            {
                "case_id": case["case_id"],
                "source_candidate_coordinates_sha256": digest(
                    encoded(exact(case["coordinates_angstrom"]))
                ),
                "derived_input_refs": refs,
                "derived_system_sha256": ligand["system_sha256"],
                "derived_topology_sha256": topology,
                "numeric_term_preservation_proof_ref": proof_ref,
                "request_file_ref": request_ref,
                "native_input_binding_generated": False,
            }
        )
    _freeze(packet, review)
    fresh_request, fresh_originals = _sources(frozen)
    require(
        exact(fresh_originals) == captured_originals
        and exact(fresh_request) == captured_request,
        "captured_source_mutated",
    )
    for case in cases:
        refs = case["derived_input_refs"]
        fresh_derived = {name: read_bound(refs[name]) for name in IDENTITY_FIELDS}
        preservation_proof(fresh_originals, fresh_derived)
        for ref in refs.values():
            read_bound(ref)
        read_bound(case["request_file_ref"])
        read_bound(case["numeric_term_preservation_proof_ref"])
    receipt = {
        "schema_id": SCHEMA,
        "prospective_protocol_sha256": review["protocol_sha256"],
        "prospective_manifest_sha256": review["manifest_sha256"],
        "adapter_source_sha256": digest(Path(__file__).read_bytes()),
        "original_input_refs": frozen["lineage.json"]["five_original_inputs"],
        "expected_executed_wheel_sha256": frozen["protocol.json"]["future_runtime"][
            "wheel_sha256"
        ],
        "full_packet_reference_body_verification": "external_root_freeze_review_only",
        "runtime_whitelist_body_verification": True,
        "reference_or_original_ligand_bodies_read": False,
        "native_binding_separate_from_numeric_preservation": True,
        "cases": cases,
        "new_force_calls": 0,
        "new_score_calls": 0,
        "new_optimizer_calls": 0,
        "actual_execution_authorized": False,
        "scientifically_validated": False,
    }
    _publish(output / "derivation.json", receipt)
    return receipt


_PHYSICS_GUARDS = []


def _unguarded_callable(value):
    for state in reversed(_PHYSICS_GUARDS):
        entry = state["sentinels"].get(id(value))
        if entry is not None and entry[0] is value:
            value = entry[1]
    return value


def _guard_alias_slots():
    """All loaded module/class slots; no arbitrary closure/container sandbox."""
    seen = set()
    for module in tuple(sys.modules.values()):
        if module is None:
            continue
        for name, value in tuple(vars(module).items()):
            yield module, name, value
            if issubclass(type(value), type) and id(value) not in seen:
                seen.add(id(value))
                for method, function in tuple(vars(value).items()):
                    yield value, method, function


@contextmanager
def forbid_physics(*, allow_saved_geometry=False):
    """Deny dispatch; optionally reconstruct only known saved-pose geometry.

    The strict default also denies validity methods named evaluate. Saved-result
    verification may admit the exact installed geometry methods, including the
    sparse compatibility installer. Their nested force/score/graph calls remain
    forbidden. This single-thread guard restores imported aliases and prior
    profile/trace state on either exit. Its call-event tracing is guard overhead,
    not evidence about engine performance or scientific qualification.
    """
    from unittest.mock import patch
    from types import MethodType

    require(type(allow_saved_geometry) is bool, "saved_geometry_mode_boolean")
    # Complete known lazy imports BEFORE replacing any exported dispatch alias.
    from betelgeuze_product.cpu_refinement_v1_3 import (
        workflow as workflow,
        minimization as minimization,
    )
    from betelgeuze_product.cpu_refinement import reference_forcefield_v1_1
    from betelgeuze_product.cpu_refinement_v1_2 import openmm_periodic_extension
    from betelgeuze_engine_v2.docking.validity import PoseValidityContext
    from betelgeuze_engine_v2.docking.contact_validity import (
        ElementAwarePoseValidityContext,
    )

    force_original = _unguarded_callable(
        reference_forcefield_v1_1.evaluate_reference_force_field
    )
    require(
        _unguarded_callable(openmm_periodic_extension.evaluate_reference_force_field)
        is force_original,
        "periodic_force_alias_changed",
    )
    allow_saved_geometry = allow_saved_geometry and all(
        state["allow_saved_geometry"] for state in _PHYSICS_GUARDS
    )
    geometry_targets = set()
    geometry_codes = set()
    if allow_saved_geometry:
        known_geometry = {
            ("betelgeuze_engine_v2.docking.validity", "PoseValidityContext.evaluate"),
            (
                "betelgeuze_engine_v2.docking.contact_validity",
                "ElementAwarePoseValidityContext.evaluate",
            ),
            (
                "betelgeuze_engine_v2.docking.sparse_base_validity",
                "install_sparse_element_aware_base_validity.<locals>.evaluate",
            ),
        }
        for cls in (PoseValidityContext, ElementAwarePoseValidityContext):
            function = _unguarded_callable(vars(cls)["evaluate"])
            module = sys.modules.get(getattr(function, "__module__", ""))
            code = getattr(function, "__code__", None)
            require(
                (
                    getattr(function, "__module__", None),
                    getattr(function, "__qualname__", None),
                )
                in known_geometry
                and module is not None
                and code is not None
                and Path(code.co_filename).resolve() == Path(module.__file__).resolve(),
                "unknown_saved_geometry_implementation",
            )
            geometry_targets.add((id(cls), "evaluate"))
            geometry_codes.add(id(code))

    previous_profile, previous_trace = sys.getprofile(), sys.gettrace()
    prohibited = {
        "evaluate",
        "evaluate_cross",
        "evaluate_extension",
        "evaluate_reference_force_field",
        "evaluate_independent_analytic_oracle",
        "evaluate_independent_minimization_oracle",
        "minimize",
        "minimize_extended",
        "minimize_reference_force_field",
        "score_terms",
        "_score_terms_python",
        "_score_terms_rust",
        "_build_rust_native_context",
        "build_compact_radius_graph",
    }
    attempts, targets, sentinels, frame_traces = [], [], {}, {}
    state = {"sentinels": sentinels, "allow_saved_geometry": allow_saved_geometry}

    def deny(label, original):
        def forbidden(*args, **kwargs):
            attempts.append(label)
            raise AdapterError("molecular_execution_forbidden:" + label)

        sentinels[id(forbidden)] = (forbidden, original)
        return forbidden

    def profile(frame, event, arg):
        if event == "call":
            module = frame.f_globals.get("__name__", "")
            name = frame.f_code.co_name
            forbidden = (
                module.startswith("openmm")
                or "native_graph" in module
                or (
                    module.startswith("betelgeuze")
                    and (name in prohibited or name.startswith("minimize"))
                    and id(frame.f_code) not in geometry_codes
                )
            )
            if forbidden:
                attempts.append(module + "." + name)
                raise AdapterError(
                    "molecular_execution_forbidden:" + module + "." + name
                )
        elif event == "c_call" and str(getattr(arg, "__module__", "")).startswith(
            "openmm"
        ):
            attempts.append("OpenMM")
            raise AdapterError("OpenMM_observation_forbidden")
        if previous_profile is not None:
            previous_profile(frame, event, arg)

    def retain_trace(frame, prior):
        frame_traces[frame] = [prior, frame.f_trace_lines, frame.f_trace_opcodes]
        if prior is None:
            frame.f_trace_lines = False
            frame.f_trace_opcodes = False

    def trace(frame, event, arg):
        # A raised profile exception disables profiling in CPython. A trace call
        # runs before the next profile call and keeps repeated caught calls denied.
        if sys.getprofile() is not profile:
            sys.setprofile(profile)
        if frame not in frame_traces:
            retain_trace(frame, previous_trace if event == "call" else frame.f_trace)
        record = frame_traces[frame]
        prior = record[0]
        if prior is not None and prior is not trace:
            record[0] = prior(frame, event, arg)
        if event == "return":
            frame.f_trace_lines, frame.f_trace_opcodes = record[1:]
            frame_traces.pop(frame, None)
            return record[0]
        return trace

    try:
        with ExitStack() as stack:
            seen = set()
            for module_name, module in tuple(sys.modules.items()):
                if module is None or not module_name.startswith("betelgeuze"):
                    continue
                for name, value in tuple(vars(module).items()):
                    if callable(value) and (
                        name in prohibited or name.startswith("minimize")
                    ):
                        target = (id(module), name)
                        if target not in seen:
                            targets.append((module, name, value))
                            stack.enter_context(
                                patch.object(
                                    module, name, deny(module_name + "." + name, value)
                                )
                            )
                            seen.add(target)
                    if isinstance(value, type) and value.__module__.startswith(
                        "betelgeuze"
                    ):
                        for method, function in tuple(vars(value).items()):
                            target = (id(value), method)
                            if (
                                (method in prohibited or method.startswith("minimize"))
                                and target not in seen
                                and target not in geometry_targets
                            ):
                                targets.append((value, method, function))
                                stack.enter_context(
                                    patch.object(
                                        value,
                                        method,
                                        deny(
                                            value.__module__
                                            + "."
                                            + value.__name__
                                            + "."
                                            + method,
                                            function,
                                        ),
                                    )
                                )
                                seen.add(target)
            _PHYSICS_GUARDS.append(state)
            # Existing caller frames also need exception events for caught C calls.
            frame = sys._getframe()
            while frame is not None:
                retain_trace(frame, frame.f_trace)
                frame.f_trace = trace
                frame = frame.f_back
            sys.settrace(trace)
            sys.setprofile(profile)
            try:
                yield
                require(not attempts, "caught_molecular_execution_attempt")
            finally:
                sys.settrace(previous_trace)
                for frame, (prior, lines, opcodes) in tuple(frame_traces.items()):
                    frame.f_trace = prior
                    frame.f_trace_lines, frame.f_trace_opcodes = lines, opcodes
                frame_traces.clear()
                sys.setprofile(previous_profile)
    finally:
        if state in _PHYSICS_GUARDS:
            _PHYSICS_GUARDS.remove(state)
        # Imports may copy a sentinel under any alias, even an unprohibited name.
        # Restore those module/class slots after ExitStack restores original slots.
        for target, name, value in _guard_alias_slots():
            descriptor = (
                type(value) if type(value) in (staticmethod, classmethod) else None
            )
            bound = type(value) is MethodType
            candidate = value.__func__ if descriptor is not None or bound else value
            entry = sentinels.get(id(candidate))
            if entry is not None and entry[0] is candidate:
                restored = entry[1]
                if descriptor is not None:
                    restored = descriptor(restored)
                elif bound:
                    restored = MethodType(restored, value.__self__)
                setattr(target, name, restored)
        require(
            all(
                vars(target).get(name) is original for target, name, original in targets
            ),
            "dispatch_callable_restore_failed",
        )
        for _, _, value in _guard_alias_slots():
            candidate = (
                value.__func__
                if type(value) in (staticmethod, classmethod, MethodType)
                else value
            )
            entry = sentinels.get(id(candidate))
            require(
                entry is None or entry[0] is not candidate, "leaked_dispatch_sentinel"
            )
        require(
            _unguarded_callable(
                openmm_periodic_extension.evaluate_reference_force_field
            )
            is force_original,
            "periodic_force_alias_restore_failed",
        )


def prepare_inputs(packet, review, output):
    """Create-only derivation under a no-physics guard; no execution authority."""
    with forbid_physics():
        return _prepare_inputs(packet, review, output)


def _loaded_origins(installed, sources, archive, *, modules=None):
    """Every actually loaded engine/product module must come from this wheel."""
    origins = {}
    for name, module in sorted(
        tuple((sys.modules if modules is None else modules).items())
    ):
        if (
            name.split(".")[0] not in ("betelgeuze_engine_v2", "betelgeuze_product")
            or module is None
        ):
            continue
        path = getattr(module, "__file__", None)
        origin = getattr(getattr(module, "__spec__", None), "origin", None)
        require(
            type(path) is str
            and type(origin) is str
            and Path(path).resolve() == Path(origin).resolve(),
            "loaded_module_origin_missing:" + name,
        )
        resolved = Path(path).resolve()
        require(
            resolved.is_relative_to(installed), "mixed_origin_loaded_module:" + name
        )
        member = resolved.relative_to(installed).as_posix()
        require(
            member.endswith(".py")
            and digest(resolved.read_bytes()) == digest(archive.read(member)),
            "loaded_module_not_wheel_member:" + name,
        )
        if member in sources:
            require(
                digest(resolved.read_bytes()) == sources[member],
                "loaded_module_closure_changed:" + name,
            )
        origins[name] = {
            "member": member,
            "path": str(resolved),
            "sha256": digest(resolved.read_bytes()),
        }
    return origins


def installed_input_binding(request, *, wheel_ref, expected_wheel_sha256):
    """Explicit installed-only zero-public-call binding; distinct from preparation.

    The entire loaded native source closure must equal the pinned old wheel ZIP.
    Caller runs this in the isolated installed runtime, never a workspace import.
    """
    require(wheel_ref["sha256"] == expected_wheel_sha256, "execution_wheel_changed")
    raw = Path(wheel_ref["path"]).read_bytes()
    require(
        len(raw) == wheel_ref["bytes"] and digest(raw) == expected_wheel_sha256,
        "wheel_bytes_changed",
    )
    from betelgeuze_product.cpu_refinement_v1_3 import workflow

    sources = workflow.source_manifest()
    installed = Path(workflow.__file__).resolve().parents[2]
    require(
        (installed / "betelgeuze_md_product-0.1.0.dist-info").is_dir(),
        "installed_runtime_required",
    )
    with zipfile.ZipFile(wheel_ref["path"]) as archive:
        for name, sha in sources.items():
            require(
                digest(archive.read(name)) == sha
                and digest((installed / name).read_bytes()) == sha,
                "installed_wheel_source_closure_mismatch",
            )
        before_origins = _loaded_origins(installed, sources, archive)
        with forbid_physics():
            binding = workflow.input_binding(deepcopy(request))
        after_origins = _loaded_origins(installed, sources, archive)
        require(
            all(after_origins.get(k) == v for k, v in before_origins.items()),
            "loaded_module_origin_changed",
        )
    require(
        binding["implementation_sources"] == sources, "binding_implementation_changed"
    )
    require(workflow.source_manifest() == sources, "loaded_source_changed")
    raw2 = Path(wheel_ref["path"]).read_bytes()
    require(digest(raw2) == expected_wheel_sha256, "wheel_changed_during_binding")
    return {
        "schema_id": "sro_installed_only_input_binding/1",
        "executed_wheel": deepcopy(wheel_ref),
        "installed_site": str(installed),
        "python_executable": sys.executable,
        "loaded_module_origins": after_origins,
        "loaded_module_origins_verified_against_wheel": True,
        "installed_implementation_sources": sources,
        "installed_implementation_source_sha256": binding[
            "implementation_source_sha256"
        ],
        "input_binding": binding,
        "new_force_calls": 0,
        "new_score_calls": 0,
        "new_optimizer_calls": 0,
        "scorer_constructor_arithmetic_allowed": True,
        "scientifically_validated": False,
        "actual_execution_authorized": False,
    }
